# Constant predictions: NOT an inference bug — degenerate models, reported silently

_Opened 2026-08-24 on a digits measurement. **Substantially corrected the same day** after the
`test_data/` reproduction contradicted it. Read the correction before acting on the original claim._

## Corrected finding

Constant predictions are real, but **inference is not where they come from**. On `test_data/` at the
regression config, every fold's estimator is an **`ElasticNet` whose coefficients are all zero**. It
returns its intercept — the training-target mean — for any input whatsoever:

| evidence | value |
|---|---|
| each fold estimator over a grid spanning [-50, 50]² | **1 unique output** (0.7981 – 0.8159 per fold) |
| `target_0/prediction-heatmaps/prediction_values.npy`, 10 000 grid points | **1 unique value**, 0.807000 |
| `confidence_values.npy` | **1.0 exactly**, at every grid point |
| `train_labels` mean | **0.8070** — the constant *is* the mean |

The training-time artifacts already show the degeneracy. Inference faithfully applies a model that
was constant when it was fitted, so it reproduces the constant exactly.

**The fit is not itself a bug.** `quick_train_dict` searches ElasticNet `alpha` up to 1.0; on 40
samples of 2-D embeddings whose target has std 0.07, zeroing the coefficients genuinely minimises
cross-validated error. Optuna is answering correctly that there is no signal to fit.

**The bug is that nothing says so.** A model that predicts the mean everywhere is reported with
`confidence = 1.0` — the maximum — and the run exits 0.

## Why the original claim was wrong

Two independent flaws, both in the measurement rather than in EMUSES:

1. **The digits inference was fed the model's own pre-normalized split.** The recorded command was
   `np.load(armA/split_dataset/test_features.npy)` → CSV → `emuses inference`. But
   `split_dataset/*.npy` is written **after** input normalization, while the inference path applies
   the saved training scaler again. The data was normalized twice.
2. **`test_data/` cannot demonstrate prediction behaviour.** `features.csv` is a synthetic ramp —
   row *i* is `[1.i, 2.i, … 8.i]` — so all 50 points lie on a line in 8-D. It is rank-1 by
   construction and yields degenerate fits. Phase 0's guess ("degenerate fits from the tiny budget")
   was right about the cause and wrong only about the budget: this is a realistic budget
   (`optuna_trials=15`) and it still collapses.

The digits result was accepted because it was alarming, not because its input had been checked. It
is the same failure the project keeps meeting: **the encouraging-or-dramatic reading gets less
scrutiny than the boring one.**

## What IS confirmed, and worth fixing

**1. Degenerate models are never reported (highest value).** All-zero coefficients, a constant
prediction grid, and `confidence = 1.0` together describe a model that knows nothing and says it is
certain. Confidence is computed as `1.0 - std(across fold predictions)`
(`inference_stage.py:1455`), so **perfect agreement between useless models reads as perfect
confidence**. Detect and report at training time, where the evidence already exists.

**2. Feeding EMUSES' own splits back in silently double-normalizes.** Measured on `test_data/`:

| inference input | distinct embeddings from `umap.transform` |
|---|---|
| `split_dataset/test_features.npy` (pre-normalized) | **1** — total collapse |
| the same 10 rows, raw from `features.csv` | 10 |
| all 50 rows, raw | 50 |

Off-manifold input collapses the UMAP transform to a single point, with no error and exit 0. This
did not change the *predictions* on `test_data/` only because the models were already constant; on a
model that had learned something it would silently destroy the result.

**3. Two input defects.** `emuses inference` **rejects `.npy`** although EMUSES writes its splits as
`.npy`; and a **header-bearing CSV** fails with "No numeric data remaining" because `input_header`
defaults to `None`. Note the ordering constraint: accepting `.npy` makes defect 2 *easier* to hit,
so the collapse guard should land first or alongside.

## Consequence for the regression suite

`tests/regression/baselines/*.json` pin per-fold prediction scores of mean **-0.3554**, min
**-0.9809** — negative R², i.e. worse than predicting the mean, which is what intercept-only models
give on held-out folds. The suite remains valid for what it is for (those numbers must not move),
but it **cannot detect a prediction-quality regression, because it is already at the floor**. Do not
read a passing regression suite as evidence that prediction works.

## Still open

Whether digits shows a genuine inference defect **is unresolved**. Its models were not degenerate
(CV 0.9895–1.0 with real spread, above the ~0.90 one-vs-rest base rate), so the constant `0.0` on
targets 7 and 8 is not explained by the ElasticNet collapse seen here — but the input was
double-normalized, which is sufficient on its own to produce it. Settling it needs a digits model
re-run with **raw** inference input (~3.5 h, ~1.5 GB); the original model was deleted.

Until then, treat "inference is broken" as **unproven**, and the two silent-failure defects above as
the real, confirmed work.
