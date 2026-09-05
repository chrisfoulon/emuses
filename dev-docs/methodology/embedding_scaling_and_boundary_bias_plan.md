# Embedding scaling and kernel boundary bias — implementation plan

_Written 2026-09-06. Supersedes nothing; this is the first record of these decisions.
Rationale for the coordinate-system half is ADR §2.4b. Read this before touching
`umap_stage.py:481-482`, `grid_creator.py`, or `kernel_regression_utils.py`._

## Why this exists

Two independent defects were found in the same audit, both in the path from UMAP output to
the statistical maps. Neither raises an error. Both change published numbers.

1. **The 0–1 rescaling is per-axis**, which is mathematically ill-posed on a UMAP embedding.
2. **The kernel regressor is local-constant** (Nadaraya-Watson), which is biased at the
   edges of the data — and those edges determine which samples enter which region, and
   therefore which voxels come out significant.

A third finding is a live defect that the plan fixes on the way past: for regression
targets the grid's confidence map is a constant, so the confidence threshold filters
nothing.

## What was measured, not assumed

**Per-axis rescaling is not well-defined on a UMAP embedding.** UMAP's loss depends only on
pairwise distances, so a solution is fixed only up to rotation, reflection and translation.
Any rotation is an equally valid output. Per-axis min-max therefore depends on the arbitrary
orientation the optimiser landed in. Rotating the same embedding by 45° and re-normalising:

| | pearson r of pairwise distances | max distortion | mean |
|---|---|---|---|
| per-axis | 0.9598 | **37.0%** | 11.9% |
| isotropic | 1.000000 | 0.0% | 0.0% |

A circle in per-axis space is an ellipse in UMAP space whose orientation is set by the seed.

**The pipeline currently disagrees with itself about distance.** HDBSCAN clusters at
`umap_stage.py:302` and `approximate_predict` runs at `:409`, both *before* the rescale at
`:510`. So clustering, DBCV and the composite score use raw coordinates (UMAP's true metric)
while the predictors and grids use per-axis-distorted ones.

**Nadaraya-Watson is boundary-biased here.** LOO on the swiss run, isotropic rescaling,
edge = lowest quartile of distance-to-hull:

| σ | estimator | edge bias | interior bias | edge RMSE |
|---|---|---|---|---|
| 0.05 | Nadaraya-Watson | +0.0565 | −0.0580 | 0.2816 |
| 0.05 | local linear | −0.0007 | −0.0069 | 0.1240 |
| 0.10 | Nadaraya-Watson | +0.2152 | −0.1239 | 0.4909 |
| 0.10 | local linear | +0.0110 | −0.0329 | 0.2204 |

The edge/interior sign flip under NW is the boundary effect. Local linear removes it.
**Caveat:** swiss-roll `t` is near-linear along the manifold, which flatters local linear.
The bias correction is the robust finding; do not expect the RMSE halving to transfer.

**Local linear is the right instrument, not reflection or boundary kernels.** Those assume a
known, usually rectangular support. EMUSES' boundary is the data's own irregular hull. Local
polynomial fitting is design-adaptive and boundary-bias-free with no geometric assumption
(Fan & Gijbels). References at the end.

## Blast radius — which baselines actually move

This was checked against `tests/regression/regression_metrics.py`, not assumed.

| baseline | derived from | isotropic switch | local linear |
|---|---|---|---|
| `_embedding_distances` | `pairwise_distances` on **raw** `embeddings.npy` (`:80-87`) | **unchanged** | unchanged |
| `composite_score`, `metric_*` | UMAP/HDBSCAN search, pre-rescale | **unchanged** | unchanged |
| `_cluster_labels`, `n_clusters`, `noise_fraction`, `hdbscan_params` | pre-rescale | **unchanged** | unchanged |
| `target_0_*_Score` (8 values/dataset) | prediction models on rescaled coords | **moves** | moves *if* `kernel` wins |

Asserted tolerances: `PREDICTION_RTOL = 1e-3` for the score block, `SEARCH_RTOL = 1e-6` for
the search block (`test_numerical_regression.py:74-77`).

**Use this as a check, not just a forecast.** After the isotropic switch, everything in the
"unchanged" rows must be *bit-identical*. If `composite_score` or `_embedding_distances`
moves, the change leaked somewhere it should not have. That is a stronger test than the
re-recorded numbers themselves.

**Scope note on local linear:** the prediction search picks among three model families —
`kernel`, `rf`, `elastic` (`optim_configs_predict.py:5`). Local linear changes only the
`kernel` family. Masking and real confidence are model-agnostic and therefore apply to every
run regardless of which family wins. That is why they rank above local linear in value even
though local linear is the more interesting fix.

## The dead routes this plan must not recreate

Three mechanisms exist for carrying scaling factors. **Two are dead**, and both were
invisible because a test made them look wired:

1. **`min_embeddings_` / `max_embeddings_` on the UMAP model object**
   (`inference_stage.py:263-264`). Nothing in `emuses/` ever sets these. The only assignment
   in the tree is `tests/inference/test_normalization_validation.py:63-64` — **on a mock**.
   In production the `getattr` always returns `None` and is overwritten two lines later.
2. **Context keys `embedding_train_min_coords` / `embedding_train_max_coords`**
   (`umap_stage.py:579-580`). No production consumer. Asserted only in
   `tests/inference/test_normalization_analysis.py`, which builds its own mock context.
3. **`embedding_scaling.json`** — the live one. Written by `umap_stage`, read **only** by
   `inference_stage`. The training path never reads back what it writes, which is the
   `--load_umap` defect.

**Root-cause pattern, and the thing to guard against:** a test that constructs its own input
can validate a consumer while no producer exists. It proves "if X were set we would use it",
never "X is set". Prose does not catch this; the repo already uses structural AST tests for
exactly this class of problem (`tests/test_architecture_boundary.py`,
`tests/test_pytest_option_registration.py`). Follow that pattern.

---

## Step 1 — Reuse wiring. Baseline-neutral.

**Change**

- `umap_stage.py:481-482` — on the reuse paths (`--load_umap`, `--load_embeddings`, and the
  output-folder resume), load the source run's factors via
  `embedding_spaces.load_scaling()` instead of recomputing from the current cohort. Only
  compute fresh factors when the morphospace was actually trained in this run.
- Delete dead route 1: `inference_stage.py:263-264`, and the mock lines in
  `tests/inference/test_normalization_validation.py:63-64` that made it look alive.
- Delete dead route 2: `umap_stage.py:579-580` and the assertions in
  `tests/inference/test_normalization_analysis.py` that only ever saw a mock context.

**Why it is baseline-neutral:** the regression suite trains fresh
(`regression_config.py:48`, `load_embeddings: False`), so no reuse path is exercised and no
recorded number can move. Verify this rather than trust it — a full `--core` must be green
with the baselines untouched.

**Verification**

1. Full local `--core` green, **baselines unmodified**. Any movement here means the change
   reached the training path, which it must not.
2. New end-to-end test: train run A on cohort 1; run B with `--load_umap` pointing at A on a
   *different* cohort; assert `B/embedding_scaling.json == A/embedding_scaling.json` and that
   a fixed raw coordinate maps to the same rescaled coordinate in both.
3. **Perturbation:** revert the loading so B recomputes. Test (2) must fail. Restore.
   Without this the test may be asserting something that was already true.

**Structural guard — new file `tests/test_scaling_single_source.py`:**

- AST, not substring matching (a comment mentioning a name must not satisfy it — this repo
  has already been bitten by a colour-blind grep faking a clean result).
- Assert `min_embeddings_` / `max_embeddings_` appear **nowhere** in `emuses/` or `tests/`.
- Assert every context key written by a stage is read by some stage. This is the generic
  form of dead route 2 and would have caught it. Literal string keys only; document the
  limitation in the test.
- Failure message must name the dead-route pattern and point here.

---

## Step 2 — Isotropic rescaling. Moves the prediction scores only.

**Change**

- `umap_stage.py:481-482` → isotropic, option C: subtract each axis's own minimum, divide by
  a **single** global range (`(X - X.min(0)) / (X.max(0) - X.min(0)).max()`). Proportions
  preserved, both axes anchored at 0, tighter grid packing than a plain global scalar.
  Record `"mode": "isotropic_global_range"` in `embedding_scaling.json` — the `mode` field
  added in ADR §2.4b exists for exactly this.
- `grid_creator.py:82-83` — **drop the 0.05 padding.** It is inert today (with per-axis
  scaling the data spans exactly [0,1] and the clamps cancel it exactly), matplotlib's
  default `axes.xmargin`/`axes.ymargin` is already 0.05, and after this switch it would wake
  up **asymmetrically**: 0 at the bottom, +0.05 at the top of the narrow axis.
- `region_statistical_analyzer.py:295` — `region_coords / grid_size` assumes the grid spans
  exactly [0,1]. True today *only because of* per-axis scaling. Derive coordinates from the
  grid's actual bounds. (It is also off by one — index 99 maps to 0.99 where `linspace` put
  it at 1.0. ~1% today; ~20% wrong after the switch.)
- `emuses_utils.EmbeddingSpace` (`:400-401`) already uses a global scalar. Reconcile it with
  the new convention or document why it differs.

**Verification**

1. `pytest tests/regression/ -q` **before** re-recording. Expect: `target_0_*` fail;
   `composite_score`, `metric_*`, `_embedding_distances`, `_cluster_labels` **all pass
   untouched**. If any of the latter move, stop — the change leaked.
2. Re-record with `--regen-baselines`. **Commit the old baseline file first** so the diff is
   reviewable and the before/after is recoverable.
3. Full `--core` green.
4. Rotation invariance test: rotate an embedding, rescale, assert pairwise-distance structure
   is preserved to 1e-12. This is the property per-axis lacked and is the reason for the
   change; it belongs in the suite, not just in this document.
5. Re-run `scripts/swiss_roll_diagnostic.py`; L0/L1/L2 recorded in STATUS.md.

---

## Step 3 — Real confidence. Model-agnostic, cheap, fixes a live defect.

**Change** — `grid_creator.py:200-206` and `:275-287`.

Regression currently gets `confidence = np.ones(...) * 0.8`; `cv_ensemble` then takes the std
across models of identical constants → exactly 0 → confidence 1.0 everywhere, so
`visualization_threshold` filters nothing. Replace with the **ensemble spread of the
predictions** — `np.std(all_predictions, axis=0)`, already computed at `:226` and discarded.

Note the docstring at `:243` already claims "1 − standard deviation of ensemble predictions".
The code passes `model_confidences`. Make the code match the documented intent.

Ensemble spread grows wherever data is sparse — edges *and* interior holes — so this gives
the threshold something real and partially subsumes Step 4.

**Verification**

- Assert confidence is **not constant** on a real run (the exact defect: a constant map
  passes every threshold).
- Assert confidence is monotonically lower outside the hull than inside.
- Decide and document what `visualization_threshold = 0.2` means against the new scale. The
  old threshold was calibrated against a constant, i.e. against nothing.
- Re-record: this changes region selection, so `target_0_*` may move. Same protocol.

---

## Step 4 — Local linear. Only the `kernel` family.

**Change** — `KernelRegressor` (`kernel_regression_utils.py:35-109`): replace the
local-constant weighted mean with a local *linear* fit — weighted least squares on
`[1, (xᵢ − x)]`, prediction is the intercept.

`KernelLogisticRegressor` (`:112`) stays Nadaraya-Watson for now; the analogous fix is local
logistic regression, which is a larger change. **Document the asymmetry explicitly** so it is
a recorded decision rather than an oversight someone finds later.

**Verification**

1. Port the LOO edge-vs-interior bias measurement above into a test. Assert local linear's
   edge bias is materially smaller than NW's on a synthetic set with a known boundary.
2. Assert local linear reproduces NW exactly when the target is constant (degenerate check).
3. Guard against singularity: with few neighbours the WLS design can be rank-deficient. Use
   `lstsq`, and add a test with a grid point having < 3 effective neighbours.
4. Re-record `target_0_*` — **only for datasets where `kernel` actually won**. Record which
   family won in the baseline, or this is unattributable.

---

## Step 5 — Support masking. Model-agnostic, highest value of the edge fixes.

**Change** — grid points outside the training embedding's support are extrapolation for
*every* model family (RF extrapolates flat, ElasticNet extrapolates unbounded), so this
matters regardless of which won. Compute the convex hull of the training embedding (α-shape
later if the hull proves too permissive), set outside points to NaN, exclude them from
thresholding and region formation.

This refuses to extrapolate; it does not correct bias. Complementary to Step 4, not a
substitute.

**Verification**

- Assert masked points are excluded from regions, not silently treated as zero — a NaN read
  as 0 would pass a threshold test and look like a valid region.
- Assert region membership changes only at the boundary, not in the interior.
- Re-record.

---

## Sequencing, and why not all at once

Steps 2–5 each move the maps. Doing them together needs one re-record instead of four, but
makes "did this change the science" unanswerable. Since these numbers are heading for
publication, keep them attributable: re-record and measure after each.

Step 1 first regardless — it is baseline-neutral, so it is free to land and removes the dead
routes before anything else touches this code.

## What not to do

- **Do not pad the grid bounds** and do not repurpose `margin` for edge effects. Neither
  addresses boundary bias; padding makes the outermost cells worse by evaluating where there
  are even fewer neighbours.
- **Do not widen `PREDICTION_RTOL`** to absorb a change. These are different quantities, not
  drifted ones. Re-record deliberately.
- **Do not delete a suite from `CORE_SUITES`** to get green.
- **Do not trust a green runner on a foreign machine.** CI runs `--foreign-machine`, which
  deselects the `machine_specific` numerical tests. Every step here must be verified with a
  full local `--core`.

## Open questions

- Does the isotropic switch actually change prediction performance, or only the coordinates?
  Measurable at Step 2; worth knowing before deciding how much the rest matters.
- Is the convex hull too permissive for a curved morphospace? α-shape is the fallback, but it
  adds a tuning parameter — prefer the hull until it demonstrably fails.
- `visualization_threshold` and `effect_size_threshold` (0.2 / 0.5) were calibrated against a
  constant confidence map and predictions in unknown units. Both need re-derivation after
  Step 3, and that is a scientific decision, not a code change.

## References

- [Fan & Gijbels — local polynomial fitting, boundary behaviour](https://users.ssc.wisc.edu/~behansen/718/NonParametrics2.pdf)
- [Upper bound of Nadaraya-Watson bias](https://arxiv.org/html/2001.10972)
- [alphahull — generalizing the convex hull](https://cran.r-project.org/web/packages/alphahull/vignettes/alphahull.pdf)
- [Kernel smoothing for irregular 2-d data](https://rdrr.io/cran/fields/man/smooth.2d.html)
