"""Is EMUSES' continuous prediction broken, and if so, where?

Swiss roll is chosen because the answer is known exactly. `make_swiss_roll`
returns each sample's position `t` along the roll -- the generative parameter,
continuous by construction, and certainly recoverable from the 3 coordinates.
Any failure here is EMUSES', not the data's.

The point is to localise, not to score. Three layers are measured separately:

  L0  t from the RAW 3-D input          -- upper bound. If this is low the
                                           harness is wrong, not EMUSES.
  L1  t from the UMAP EMBEDDING EMUSES   -- did the embedding keep the signal?
      actually produced
  L2  what EMUSES' own prediction stage  -- did the prediction path use it?
      reports

L0 high + L1 high + L2 low  =>  the prediction stage is broken.
L0 high + L1 low            =>  the embedding discards it; prediction is
                                innocent and the UMAP config is the suspect.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import make_swiss_roll
from sklearn.model_selection import KFold
from sklearn.neighbors import KNeighborsRegressor

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tests" / "regression"))

N_SAMPLES = 800
SEED = 42


def cv_recover(X, y, k=5, folds=5):
    """How well does a plain kNN recover y from X? Returns Pearson r, out-of-fold.

    Deliberately dumb: no tuning, no scaling beyond what the caller does. It is a
    floor on "is the information present", not a model comparison. If a 5-NN can
    read it, the signal is unambiguously there.
    """
    # Refuse a length mismatch rather than scoring one. Without this the function
    # silently returns a plausible number: `pred` gets sized to y, only len(X) of its
    # entries are ever written, and the rest stay zero. That is how this harness once
    # reported r = 0.0193 for an embedding that is in fact near-perfect -- the
    # embedding covers the 640 training rows while `t` has all 800.
    X, y = np.asarray(X), np.asarray(y).ravel()
    if len(X) != len(y):
        raise ValueError(
            f"length mismatch: X has {len(X)} rows, y has {len(y)}. These must be the "
            f"same samples in the same order -- an embedding covers the TRAIN split "
            f"only, so pair it with split_dataset/train_labels.npy, not the full y."
        )

    pred = np.zeros_like(y, dtype=float)
    for train, test in KFold(n_splits=folds, shuffle=True, random_state=SEED).split(X):
        m = KNeighborsRegressor(n_neighbors=k).fit(X[train], y[train])
        pred[test] = m.predict(X[test])
    return float(np.corrcoef(pred, y)[0, 1])


def main():
    out_root = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/swiss_diag")
    out_root.mkdir(parents=True, exist_ok=True)

    # noise=0.0 on purpose: the cleanest possible case. A failure here cannot be
    # blamed on the data being hard.
    X, t = make_swiss_roll(n_samples=N_SAMPLES, noise=0.0, random_state=SEED)
    print(f"swiss roll: X{X.shape}, t range [{t.min():.2f}, {t.max():.2f}]")

    feats = out_root / "swiss_features.csv"
    scores = out_root / "swiss_scores.csv"
    np.savetxt(feats, X, delimiter=",")
    np.savetxt(scores, t, delimiter=",")

    l0 = cv_recover(X, t)
    print(f"\nL0  t from raw 3-D input          r = {l0:.4f}")
    if l0 < 0.9:
        print("    !! upper bound is already low -- the harness is wrong, stop here")

    import regression_config as rc

    rc.DATASETS["swiss"] = {
        "features": str(feats.relative_to(PROJECT_ROOT))
        if feats.is_relative_to(PROJECT_ROOT)
        else str(feats),
        "scores": str(scores.relative_to(PROJECT_ROOT))
        if scores.is_relative_to(PROJECT_ROOT)
        else str(scores),
    }
    # build_args prefixes PROJECT_ROOT; absolute paths must survive that.
    spec = rc.DATASETS["swiss"]
    if Path(spec["features"]).is_absolute():
        rc.PROJECT_ROOT = Path("/")
        spec["features"] = spec["features"].lstrip("/")
        spec["scores"] = spec["scores"].lstrip("/")

    run_dir = out_root / "run"
    print(f"\nrunning EMUSES into {run_dir} ...")
    rc.run_pipeline("swiss", run_dir)

    emb_files = sorted(run_dir.rglob("embeddings.npy"))
    if not emb_files:
        print("!! no embeddings.npy produced")
        return

    # Via the loader, not np.load. embeddings.npy is RAW and test_embeddings.npy is
    # RESCALED, and reading one as the other is silent -- it scored this very
    # measurement at r = 0.2747 instead of 0.9989 before the cause was found. Naming
    # the space is the point; see ADR 2.4b.
    from emuses.tools.embedding_spaces import RESCALED, load_embeddings

    model_dir = emb_files[0].parent
    emb = load_embeddings(model_dir, space=RESCALED, split="train")

    # The embedding covers the TRAIN split only (test_size 0.2 => 640 of 800), so `t`
    # cannot be used directly. The run writes the corresponding targets alongside the
    # split, aligned row-for-row by construction -- which beats re-deriving the split
    # from a seed and hoping it matches.
    t_train = np.load(model_dir / "split_dataset" / "train_labels.npy").ravel()
    print(f"\nembedding shape {emb.shape} (space={RESCALED}), targets {t_train.shape}")

    l1 = cv_recover(emb, t_train)
    print(f"L1  t from EMUSES' UMAP embedding r = {l1:.4f}")
    for d in range(emb.shape[1]):
        r = abs(np.corrcoef(emb[:, d], t_train)[0, 1])
        print(f"      |corr(t, emb dim {d})| = {r:.4f}")

    print("\nL2  what EMUSES reports:")
    found = False
    for csv_path in sorted(run_dir.rglob("performance_summary_statistics_*.csv")):
        found = True
        print(f"   {csv_path.relative_to(run_dir)}")
        for line in csv_path.read_text().splitlines():
            if line.strip():
                print(f"      {line}")
    if not found:
        print("   !! no performance_summary_statistics_*.csv produced at all")

    print("\n--- reading ---")
    print(f"L0={l0:.4f}  L1={l1:.4f}")
    if l0 > 0.9 and l1 > 0.9:
        print("embedding preserves t. Any L2 failure is the PREDICTION stage.")
    elif l0 > 0.9 and l1 <= 0.9:
        print("embedding LOSES t. Prediction is innocent; suspect the UMAP config.")


if __name__ == "__main__":
    main()
