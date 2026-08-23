"""Guards on the seed derivation, in the shape of tests/test_cli_option_mapping.py.

Background: two identical invocations at --random_state 42 produced identical
UMAP/HDBSCAN results and different prediction scores, because the prediction
path was never connected to the seeds EMUSESPipeline derives. See
dev-docs/issues/parallelism_backend_analysis_2026_08.md.

Three separate questions are asked here, because they have different teeth:

1. Is every derived seed read by something?  Weak on its own -- it would NOT
   have caught the bug that prompted this file, because prediction_seed and
   cv_seed already had readers in robust_ood_evaluation while the main
   prediction path ignored them.  It only catches "derived and read nowhere",
   which is what optuna_seed was.

2. Does every optuna.create_study in emuses/ pass a sampler?  This is the one
   with teeth: an unseeded study is the exact defect that was measured, and the
   rule admits no exemptions.

3. Do the seed-taking builders actually put the seed on the object?  Verified
   structurally.  The PCA case cannot be verified by re-running, because
   sklearn only selects the randomized solver on inputs far larger than the
   test data -- the nondeterminism is real but not reproducible here.
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EMUSES_ROOT = PROJECT_ROOT / "emuses"
PIPELINE_FILE = EMUSES_ROOT / "pipelines" / "emuses_pipeline.py"

# master_seed is the value the user passed as --random_state, recorded in
# random_seeds.json for provenance. It is not consumed from the dict because
# it is already available as config.random_state. Every other key is a derived
# seed and must be read by something, or it is decoration.
RECORD_ONLY = {"master_seed"}


def _python_files():
    return sorted(EMUSES_ROOT.rglob("*.py"))


def _derived_seed_names():
    """The keys EMUSESPipeline actually writes, read out of the source.

    Read from the AST rather than hardcoded, so adding a seed to the pipeline
    without wiring it up fails here instead of passing silently.
    """
    tree = ast.parse(PIPELINE_FILE.read_text())
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if "random_seeds" not in targets or not isinstance(node.value, ast.Dict):
            continue
        for key in node.value.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                names.add(key.value)
    return names


def test_the_pipeline_still_derives_seeds():
    """Guard the guard: if this returns nothing, the tests below are vacuous."""
    names = _derived_seed_names()
    assert "optuna_seed" in names, f"expected derived seeds, found {names}"
    assert len(names) >= 5, f"suspiciously few derived seeds: {names}"


@pytest.mark.parametrize("seed_name", sorted(_derived_seed_names() - RECORD_ONLY))
def test_every_derived_seed_is_read_somewhere(seed_name):
    """A seed that is derived and never read is a seed that does nothing."""
    readers = []
    for path in _python_files():
        if path == PIPELINE_FILE:
            # The pipeline writes the dict; reading it back there still counts
            # (split_seed is consumed in emuses_pipeline itself), so only skip
            # the literal that defines the keys.
            text = path.read_text()
            if f'.get(\n            "{seed_name}"' in text or f'.get("{seed_name}"' in text:
                readers.append(path)
            continue
        text = path.read_text()
        if f'"{seed_name}"' in text or f"'{seed_name}'" in text:
            readers.append(path)
    assert readers, (
        f"{seed_name!r} is derived in emuses_pipeline.py and written to "
        f"random_seeds.json, but nothing reads it. Either wire it up or stop "
        f"deriving it."
    )


def _create_study_calls():
    """(file, lineno, has_sampler) for every optuna.create_study call."""
    calls = []
    for path in _python_files():
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:  # pragma: no cover - would fail elsewhere first
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name != "create_study":
                continue
            has_sampler = any(kw.arg == "sampler" for kw in node.keywords)
            calls.append((path.relative_to(PROJECT_ROOT), node.lineno, has_sampler))
    return calls


def test_create_study_calls_are_findable():
    """Guard the guard: an AST walk that finds nothing proves nothing."""
    calls = _create_study_calls()
    assert len(calls) >= 8, f"expected the known create_study sites, found {calls}"


def test_no_unseeded_optuna_study():
    """An Optuna study without an explicit sampler gets TPESampler(seed=None).

    That is what made prediction scores differ between two runs at the same
    --random_state. There are no exemptions: a study whose result is only
    logged still costs one line to seed.
    """
    unseeded = [
        f"{path}:{lineno}" for path, lineno, seeded in _create_study_calls() if not seeded
    ]
    assert not unseeded, (
        "optuna.create_study without an explicit sampler defaults to "
        "TPESampler(seed=None), making the search nondeterministic:\n  "
        + "\n  ".join(unseeded)
    )


# --------------------------------------------------------------------------
# The builders put the seed on the object they build.
# --------------------------------------------------------------------------


def test_build_estimator_uses_the_seed_it_is_given():
    from emuses.tools.models_utils import build_estimator

    cfg = {"model_type": "rf", "n_estimators": 5, "max_depth": 3}
    assert build_estimator(cfg, "reg", 1, random_state=7).random_state == 7
    assert build_estimator(cfg, "reg", 1, random_state=8).random_state == 8


def test_build_estimator_default_matches_the_old_hardcoded_value():
    """Callers that pass no seed must keep their previous results."""
    from emuses.tools.models_utils import build_estimator

    cfg = {"model_type": "rf", "n_estimators": 5, "max_depth": 3}
    assert build_estimator(cfg, "reg", 1).random_state == 42


def test_linear_models_are_seeded():
    """saga shuffles, so LogisticRegression is genuinely nondeterministic."""
    from emuses.tools.models_utils import build_estimator

    clf = build_estimator({"model_type": "elastic", "C": 1.0, "penalty": "l2"}, "clf", 1, 7)
    assert clf.random_state == 7
    reg = build_estimator(
        {"model_type": "elastic", "alpha": 0.1, "l1_ratio": 0.5}, "reg", 1, 7
    )
    assert reg.random_state == 7


@pytest.mark.parametrize(
    "feat_cfg, step_name",
    [
        ({"feat_type": "pca_gwd", "sigma_gwd": 0.1, "n_comp": 2, "use_raw": False}, "pca"),
        (
            {
                "feat_type": "kpca_gwd",
                "sigma_gwd": 0.1,
                "n_comp": 2,
                "feat_gamma": 0.5,
                "use_raw": False,
            },
            "kpca",
        ),
    ],
)
def test_pca_transformers_carry_the_seed(feat_cfg, step_name):
    """sklearn picks a randomized solver only on large inputs.

    On this size of input the solver is deterministic, so re-running proves
    nothing. Assert the seed reached the object instead.
    """
    from emuses.tools.models_utils import build_feature_union

    union = build_feature_union(feat_cfg, random_state=7)
    transformer = dict(union.transformer_list)[step_name]
    assert transformer.random_state == 7

    unseeded = dict(build_feature_union(feat_cfg).transformer_list)[step_name]
    assert unseeded.random_state is None


def test_pca_seed_reaches_the_fitted_sklearn_estimator():
    """The seed must survive as far as the sklearn object that consumes it."""
    import numpy as np

    from emuses.tools.models_utils import build_feature_union

    cfg = {"feat_type": "pca_gwd", "sigma_gwd": 0.5, "n_comp": 2, "use_raw": False}
    union = build_feature_union(cfg, random_state=7)
    X = np.random.default_rng(0).normal(size=(20, 2))
    union.fit(X)
    assert dict(union.transformer_list)["pca"].pca_.random_state == 7
