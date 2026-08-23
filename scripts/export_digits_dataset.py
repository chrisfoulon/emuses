#!/usr/bin/env python
"""Write sklearn's ``load_digits`` out as ordinary EMUSES input CSVs.

Why not just use the ``mnist`` CLI keyword? Because that keyword is a
special-cased loader (``emuses_pipeline.py`` -> ``load_and_preprocess_digits_dataset``)
that bypasses the normal file-reading path. Measurements are supposed to
characterise the path a real user takes, which is a CSV on disk.

Naming trap, recorded here because it misleads on every re-reading: the CLI
keyword is ``mnist`` but it loads **digits** (1797 x 64, 8x8 images), not the
784-dim MNIST -- ``load_and_preprocess_digits_dataset`` defaults to
``dataset="digits"``. Old runs under ~/Dropbox/EMUSE/mnist_numbers/ are digits
runs; their ``input_matrix.npy`` is (1437, 64), the 80% train split.

The dataset ships with sklearn, so this needs no download and no external data.
At 1797 samples it is also the smallest thing we have that crosses sklearn's
``svd_solver="auto"`` threshold (max(X.shape) > 500), which is what makes the
randomized-PCA path reachable at all.

    python scripts/export_digits_dataset.py --out-dir /path/to/dir
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True)
    opts = parser.parse_args()

    out_dir = Path(opts.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    digits = load_digits()
    # Match the keyword loader's normalisation so the two routes are comparable:
    # digits pixel values are 0-16, and load_and_preprocess_digits_dataset
    # divides by 16.0.
    features = digits.data / 16.0
    labels = digits.target

    features_path = out_dir / "digits_features.csv"
    labels_path = out_dir / "digits_labels.csv"

    header = ",".join(f"px{i}" for i in range(features.shape[1]))
    np.savetxt(features_path, features, delimiter=",", header=header, comments="",
               fmt="%.10g")
    np.savetxt(labels_path, labels, delimiter=",", header="digit", comments="",
               fmt="%d")

    print(f"features: {features_path}  {features.shape}")
    print(f"labels:   {labels_path}  {labels.shape}, "
          f"{len(set(labels.tolist()))} classes")
    print(f"max(X.shape) = {max(features.shape)} "
          f"({'crosses' if max(features.shape) > 500 else 'DOES NOT cross'} "
          f"sklearn's randomized-solver threshold of 500)")


if __name__ == "__main__":
    main()
