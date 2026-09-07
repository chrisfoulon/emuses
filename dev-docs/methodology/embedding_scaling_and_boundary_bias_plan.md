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
- `emuses_utils.DiscreteLatentSpace` (the class the plan mis-named `EmbeddingSpace`) already uses
  a global scalar. Reconcile it with
  the new convention or document why it differs.

**Verification — DONE 2026-09-06, and item 1 did not go as forecast. Read this before
planning Steps 3-5, because it changes what their verification can rely on.**

1. `pytest tests/regression/ -q` before re-recording. **Forecast: `target_0_*` fail.
   Actual: all 16 passed, bit-identically, on both datasets** — while the narrow axis went
   from spanning 1.0 to spanning 0.24 (anisotropy 4.1). The forecast half that held was the
   invariant: `composite_score`, `metric_*`, `_embedding_distances` and `_cluster_labels`
   stayed bit-identical, confirming the change did not leak into the training path.

   **Cause, measured, not inferred:** on both regression datasets, in every fold, the winning
   ElasticNet has *all coefficients exactly zero*. The L1 penalty zeroes them, the prediction
   is a constant intercept (the training-fold mean), so `target_0_*_Score` is a function of
   the fold split alone and is mathematically independent of the coordinates the models were
   handed. The eight `target_0_*` baselines pin nothing about the coordinate→prediction path.

   **This invalidates the blast-radius table above for every remaining step.** "moves
   `target_0_*`" was the wrong prediction for Step 2 and is the wrong prediction for Steps 3
   and 4 too: local linear (Step 4) changes the `kernel` family, which never wins here, and
   real confidence (Step 3) changes region selection, which feeds the maps rather than the CV
   scores.

   **Fixed the same day, so Steps 3-5 do have an instrument** (`STATUS.md` item 0a, ADR
   §2.9d): `tests/regression` gained a third dataset, `swiss_roll`, whose target is
   recoverable by construction. It scores 0.9962 and **4 of its 5 folds are won by
   `KernelRegressor`** -- which is precisely the family Step 4 replaces, so the blast-radius
   prediction for that step is now testable rather than notional. Reverting the rescale to
   per-axis fails `test_prediction_scores[swiss_roll]` and leaves the two 40-sample datasets
   passing; use that row, not theirs, when judging whether a step moved the science.

2. Re-record with `--regen-baselines` — **not done, and correctly so: nothing moved.** The
   baselines are untouched.
3. Full `--core` green. Done. One expected failure on the way:
   `test_a_training_run_derives_the_factors_from_its_own_embedding` pinned the per-axis
   convention in Step 1 and failed the moment the mode changed, which is what it is for. It
   now asserts the isotropic convention.
4. Rotation invariance: `tests/test_isotropic_rescaling.py`. Preserved to 1e-12 at 15°, 45°,
   90° and 137°, with the per-axis counter-example kept in the suite so the test cannot pass
   vacuously. Perturbation: reverting `isotropic_scaling_factors` to per-axis fails 6 tests.
5. `scripts/swiss_roll_diagnostic.py` re-run: **L0 0.9997, L1 0.9989, L2 0.998**, unchanged
   from per-axis — which is what a similarity transform must do, and is the only place in the
   verification where the prediction path actually fits something. Recorded in `STATUS.md`.

**Also fixed here, and the reason the region mapper was in scope at all:** it was wrong three
ways, not one. Beyond the [0, 1] assumption and the off-by-one that this plan named, it
**compared transposed axes** — `reshape(g, g)` indexes `[y, x]` while `training_embeddings`
columns are `(x, y)`, so every significant region was reflected about the diagonal. Invisible
on a square grid over a square extent, which per-axis always produced. It now maps through the
grid's own axes, recovered from the `grid_coords` the values were evaluated on rather than
reconstructed. Each of the three defects was perturbed separately and each is caught by
`tests/test_region_grid_coordinate_mapping.py`. This overlaps item **G2** in
`heatmaps_clusters_and_effect_size_maps.md`, which that document owns — the transposition is
new information for it.

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

### Done, 2026-09-06 — with three corrections to the plan above

**The stated rationale was wrong, and the real one is worse.** `visualization_threshold` is
not what makes this matter: the pipeline never reads it. It is reached only through
`apply_two_stage_filtering` ← `create_region_statistical_maps` ← `foundation_fastapi_service`,
i.e. the API path. (This confirms the other session's E4, with the nuance that it is live in
the API and dead in the pipeline.) What the pipeline does with confidence is
`combined_heatmap = final_predictions * confidences`, fed to `create_statistical_maps` as
`significance_values` and thresholded **by percentile** — and a percentile is invariant to
multiplication by a positive constant. So the old constant confidence did not merely fail to
filter; it had *exactly zero* effect on which regions were reported. Step 3 is worth doing for
that reason, not for the threshold.

**`1 − std(predictions)` alone reproduces the metric ADR §3.1b already condemns.** Constant
models agree with each other perfectly, so agreement alone scores them at the maximum —
measured 0.908 on the `regression` fixture, whose 5 folds are all-zero-coefficient
ElasticNets. Confidence is therefore `agreement × variability`:

- `agreement` = `1 − clip(std(all_predictions, axis=0) / target_sd, 0, 1)`, per grid point.
- `variability` = `clip(std(ensemble) / target_sd, 0, 1)`, one scalar for the grid.

`target_sd` is the training target's SD, compared against the **pre-denormalization**
predictions because `prediction_train_labels` is exactly what the models were fitted on, so
both sides carry whatever `--scores_normalization` did. `max_possible_std = 0.5` is gone; it
was calibrated against nothing.

**Only `agreement` can move region selection** — by the same percentile-invariance argument,
the scalar `variability` cannot. Its job is to collapse a degenerate map to zero so the run
says so. Documented in `aggregate_confidence`; do not read it as a second signal.

Measured, `swiss_roll`: agreement 0.000–0.999, variability 0.814, confidence 0.000–0.813
(mean 0.634, **std 0.201 — not constant**). Mean confidence inside the training hull 0.663 vs
0.583 outside; corr(distance to nearest training sample, confidence) = **−0.583**, monotone
across the first four quintiles (0.783 → 0.749 → 0.659 → 0.484). `regression`: agreement
0.908 flat, variability 0.000, confidence 0 everywhere with a warning naming the numbers.

**Nothing was re-recorded.** All 25 existing regression assertions passed unchanged: confidence
feeds the maps, not the CV scores, so no `target_0_*` moved. The baselines gained three new
keys (`n_confidence_maps`, `n_constant_confidence_maps`, `confidence_falls_with_sparsity`) and
a new non-parametrized guard, `test_some_dataset_has_a_confidence_map_that_participates`.

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

### Amendment, 2026-09-07 — Step 5 absorbs a defect Step 3 exposed

**Measured first, so this is not a design preference.** Running `swiss_roll` twice, identical
except that one used the pre-Step-3 constant confidence, the *high* regions came out identical
(prediction 45 samples, correlation 34) and the *low* prediction region went from 29 samples to
**77**, the old set a strict subset of the new — 48 added, 0 removed, Jaccard 0.377.

The cause is not Step 3. It is `combined = predictions × confidence`
(`grid_creator.py:517`), which Step 3 merely made visible. On `swiss_roll` every prediction is
positive (4.875–14.093), so multiplying by a confidence in [0, 0.813] pushes low-confidence
points *toward zero* and therefore into the bottom tail. The "low significance region" — meant
to mean *the model predicts a low value here* — silently became partly *we do not trust it
here*. **The artefact is sign-dependent, which is the tell:** on a target with negative
predictions the same multiplication pulls them *up* toward zero, so untrusted points would
*leave* the low tail instead. Before Step 3 the factor was constant, hence a pure rescale, hence
invisible.

**The fix is shrinkage toward the null, not multiplication:**

```
combined = null + confidence × (prediction − null)
```

`confidence = 1` gives the prediction unchanged; `confidence = 0` gives the null, i.e. no claim;
and `null = 0` reduces to `prediction × confidence`. So multiplication is not a method — it is
this formula with the null hardcoded to zero, which is correct only for a centred quantity. That
is exactly why the correlation map needed no fix (its null *is* 0, no association) and why
z-scoring the targets would appear to fix the prediction map: z-scoring moves the null to 0.

**Z-scoring is not the fix, though `--scores_normalization zscore` exists.** The map is built
from `final_predictions`, which is the *denormalized* array (`grid_creator.py:514`), so training
on z-scores still produces a raw-units map and the same artefact.

`null` = the training target mean: the prediction you would make knowing nothing about position
in the morphospace, which is literally what a constant model predicts (cf. ADR §3.1b, where the
degenerate fixtures return exactly this value). Median if robustness is wanted; that is the only
real choice here.

**Three parts, all needed:**

1. **Mask** grid points outside the training support: NaN, and `np.nanpercentile`. Shrinkage
   decides what value an untrusted point takes; it does not decide whether that point belongs in
   the distribution the threshold is computed over. Points shrunk to the null pile up in the
   middle, fattening it, which pushes the cut-offs outward and makes both tails *more* extreme
   than they should be. Masking is binary (in/out of support); shrinkage is continuous (within
   support, trust still varies). Neither replaces the other.
2. **Shrink** toward the null as above.
3. **Report three maps, and rename.** `prediction_values.npy` and `confidence_values.npy` are
   already written alongside `combined_values.npy`. Write the shrunk map as a **new**
   `corrected_values.npy` rather than redefining `combined_values.npy` in place — same filename,
   different quantity, is how a model folder written last month gets misread next month. Record
   the null value and the shrinkage form in the metadata so a saved map stays interpretable.
   Regions are defined on the masked+shrunk map; the two component maps are what you interpret
   with.

**The honest limit:** no single scalar map can separate "low because the value is low" from "low
because we do not trust it" — two numbers into one. Shrinkage guarantees an untrusted point
cannot *enter* a tail. It does not decompose a point that is already in one. That is what the
three-map output is for.

**Consequence for Step 3 that must be settled at the same time.** Under multiplication the global
`variability` scalar was provably free (percentile-invariant). Under shrinkage it is not: it caps
confidence at 0.814 on `swiss_roll`, so *every* point including the best-supported is pulled 19%
toward the null, systematically compressing both tails. So `variability` comes **out** of the
map-facing confidence and becomes a separately reported degeneracy flag — which is the cleaner
framing anyway, since it was never an uncertainty. Map-facing confidence becomes `agreement`
alone. This makes Steps 3 and 5 one piece of work, not two.

### Part 2 (shrink) + the rename half of part 3 — done, 2026-09-07

`corrected_heatmap = null + confidence * (prediction - null)`, with `null` from `_null_level`
(`grid_creator.py`). `corrected_values.npy` is written; `combined_values.npy` is **not** written
any more, so a pre-2026-09-07 model folder fails loudly at the consumer instead of being read as
the new quantity. Metadata gained `combination: shrink_to_null` and `null_level`.

Parts 1 (mask) and 3-proper (the confidence map as a first-class output to interpret with), and
the `variability` change below, are still to do.

**What it did to region selection**, `swiss_roll`, real confidence vs. a constant-confidence
control (which under shrinkage reproduces the raw prediction map *exactly* — verified, and pinned
by `test_full_confidence_leaves_the_map_exactly_alone`):

| bottom-5% grid cells | multiplication (old) | shrinkage (new) |
|---|---|---|
| kept from control | 0 / 500 | **377 / 500** |
| entered | 500 | 123 |
| mean confidence of cells that entered | **0.06** | **0.79** (grid mean 0.63) |
| mean confidence of cells that left | — | 0.60 |

Under multiplication the "low prediction" region was, in substance, the low-*confidence* region:
it replaced the entire tail with the least-trusted cells on the grid. Under shrinkage the cells
entering are *more* trusted than average and genuinely low (mean prediction 5.65 against a null
of 9.36), and the cells leaving are the untrusted ones. The mechanism is inverted, which is the
result that matters — not the sample count, which moved 29 → 43 (from 77 under multiplication)
because trusted low cells took the vacated places.

Pinned by `TestShrinkageTowardTheNull` in `tests/analysis_api/test_prediction_grid.py`, on both a
positive- and a negative-valued target so the sign-dependence cannot come back. Perturbation
check: reinstating `final_predictions * confidences` fails exactly those two tests and nothing
else. `--core` green; no regression baseline moved.

### How this interacts with replacing the percentile (their §2)

Checked against the permutation proposal, because "we are moving off percentiles" would
otherwise look like it makes this moot. It does not:

- **Tiers 1+2 — the recommended pair — permute and recompute the *correlation* grid only.** They
  are cheap precisely because that grid fits nothing. The **prediction** map is Tier 3, which
  needs a nested-CV refit per permutation and is explicitly *not* the default. So under the
  recommended plan the prediction map keeps a percentile threshold, and it is the prediction map
  that carries this defect. The two changes are close to orthogonal: permutation fixes the
  correlation map's threshold, this fixes the prediction map's statistic.
- **D4 dissolves into Tier 1.** The signed 95th-percentile threshold that can never select
  r = −0.8 stops existing once the correlation map is tested two-sided against a permutation null.
- **If Tier 3 is ever run, one hard requirement:** confidence must be recomputed *inside* each
  permutation, not computed once on the real fit and reused. Confidence depends on the models,
  which depend on the labels; reusing it across permutations makes it a fixed label-dependent
  weighting that does not cancel between the observed statistic and its null, and the test is
  then invalid. If it *is* recomputed per permutation, a global factor cancels on both sides and
  per-point agreement stays part of the statistic, which is correct.
- **Masking is permutation-safe by construction.** The support mask depends on the embedding
  only, and UMAP is unsupervised, so permuting scores leaves the embedding — and therefore the
  mask — identical. The same fixed mask applies to observed and null, exactly like a brain mask
  in the Nichols & Holmes framework, including for Tier 2's cluster-extent search volume.

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
