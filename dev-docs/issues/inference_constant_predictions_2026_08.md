# Inference emits constant predictions for some targets, while CV says 0.99+

_Measured 2026-08-24 on sklearn digits (1797 x 64). Confirms and upgrades an observation first
made in Phase 0 on `test_data/`._

## The finding

A digits model trained by `emuses full` (10-class, one-vs-rest, 5 outer folds, seed 42) was asked
to predict on its own held-out test split (360 samples). **Two of ten targets emitted a single
constant value for every sample, in every one of their five fold pipelines.**

| target | inference output | unique values | true positives in the test set | training CV score |
|---|---|---|---|---|
| target_7 | `0.0` for all 360 | **1** | 34 (9.4 %) | 0.9896 – 1.0000 |
| target_8 | `0.0` for all 360 | **1** | 30 (8.3 %) | 0.9930 – 1.0000 |

Every true positive is missed, silently. The run exits 0, writes its CSVs, and reports nothing
wrong. Targets 0–6 and 9 produced varying predictions in the same run, so this is not a
whole-pipeline failure.

**The training scores make it worse, not better.** These targets cross-validated at 0.9896–1.0000
across five folds. Whatever fails, it fails *between* the model that was scored and the model that
is loaded and applied — not during fitting.

Partial degeneracy is visible either side of the hard cases: `target_3` and `target_5` produce
varying predictions but a **constant confidence score**, and `target_9` predicts positive for ~0.9 %
of samples where 11 % are truly positive. The failure is a spectrum, not a binary.

## Why this matters more than the numbers suggest

This is the deployment EMUSES is aimed at: one person trains a model, other people run inference
against it. A model that scores 0.99 in cross-validation and then predicts a constant is the worst
kind of defect for a scientific tool — the run looks successful and the result is wrong.

## What is already known

ADR §2.4 ("Embedding Scaling Saved Separately") records a previous, closely related fix: inference
used **raw** UMAP embeddings while training used **rescaled** ones,
so kernel weights went to zero and every prediction came out identical. That was fixed by having
`UMAPStage` persist min/max to `embedding_scaling.json` for `InferenceStage` to reload.

The symptom here is the same shape. It is *not* proof the same cause has returned — that fix is in
the tree and the majority of targets work — but it is the first place to look, and it establishes
that a train/inference representation mismatch is a defect class this codebase has already had once.

## How to reproduce cheaply

Do **not** start from digits: that run costs ~3.5 h and 1.3 GB. Phase 0 saw the same symptom on
`test_data/` ("three of five inference folds emitted a constant prediction"), which is ~30 s a run.

1. `emuses full` on `test_data/` at the regression config, then `emuses inference` against the
   resulting model using its own `split_dataset/test_features.npy` contents.
2. Assert per-target, per-fold that predictions have more than one unique value.
3. If it reproduces there, diagnose there.

Two obstacles found while doing this on digits, both worth fixing regardless:

- **`emuses inference` rejects `.npy`** ("Unsupported file format: .npy"), although EMUSES writes
  its own split data as `.npy`. A model's own `split_dataset/test_features.npy` cannot be fed back
  in without converting it first.
- **A CSV with a header fails** with "No numeric data remaining after processing the file", because
  `input_header` defaults to `None` and the header row is parsed as data. A headerless CSV works.

## Status

**Open.** The digits model was deleted after metrics extraction (disk was at 94 %), so diagnosis
starts from a fresh reproduction. Evidence retained: inference predictions, per-fold training
scores, `best_trial_info.json`, `random_seeds.json` and the test labels.
