# STATUS — EMUSES
_Last touched: 2026-09-05_

## Goal

A predictive modelling tool for neuroimaging research, usable at three scales: local model
development, collaborative sharing within labs, and a public registry with peer review.

Immediate goal: **a tool whose runs you can trust and publish from** — it completes, it does what its
flags say, and the same command twice gives the same answer.

## State of play

**One branch outstanding: `fix/nd-embedding-gate-and-load-umap`** (2026-09-04, unpushed) — the N-D
gate and its opt-in, the `--load_umap` and resume fixes, cohort identity, per-target resume and the
run index. Everything else is on `main`; six branches converged on 2026-08-25 — Phase 1F (PR #9),
Phase 4, Phase 5 (the extras move), the `n_jobs` Arm B evidence, the regression conftest fix and the
parallelism backend scope. Plan: `~/.claude/plans/playful-watching-naur.md` (consolidated
2026-08-24 — read that, not the older per-phase notes).

### EMUSES runs end to end (measured 2026-08-24)

| check | result |
|---|---|
| `emuses full` | exit 0 |
| `emuses umap` | exit 0 |
| `emuses inference`, headerless CSV | exit 0 |
| `emuses inference`, CSV with header + `--input_header 0` | exit 0 |
| `ModelIOManager.validate_model` on the `full` output | `is_complete_model=True`, no errors |
| `tests/regression` | 14 passed, 90 s |
| `scripts/dev_test_runner.py` | 13/13 |
| listeners left on 8000–8010 | none |

**Merged to `main` on 2026-08-24** (PR #8, `acc0e30`); `tests/regression` passes on `main` itself
(14 passed, 83 s).

**Phase 1F done (2026-08-24): `emuses inference` goes through the service.** It submits to
`/api/v1/jobs/pipeline/inference` like every other command; `KNOWN_LOCAL_EXECUTION` is now empty, so
no CLI path runs a pipeline in-process (ADR §4). The pre-existing `/api/v1/inference` endpoints
**could never have worked** — they handed `InferenceStage` a context with no data in it and returned
422 for every request (measured). All three now call one implementation,
`emuses/pipelines/inference_runner.py::run_inference`. Outputs are unchanged: the same CLI command
before and after produced bitwise identical prediction and confidence CSVs.

**Phase 4 done (2026-08-24): the science-path failures are gone — 33 → 0** across
`tests/pipelines`, `tests/inference` and `tests/flexible-inference-stage` (185 passing). They were
seven causes, five of them one design change the tests never followed: `_predict` returns
`target_results[target]['ensemble_predictions']`, not a flat key — the same family as the empty HTTP
responses fixed in 1F. Five production defects came out of the triage: the no-models branch still
returned the old flat shape (so it died with `KeyError` instead of returning zeros); an empty
ensemble surfaced as a numpy "zero-size array" error; a log line reported the *input* count as
"predictions generated", which is what hid it; `output_path` stayed a `PosixPath` and broke JSON
serialisation; and `EMUSESPipeline(args, inference_data=...)` was dead — stored, never read, now
removed. Three contracts are now recorded in ADR §2.5b, including that **normalisation happens once,
in the pipeline** — doing it in the stage as well is what the withdrawn "constant predictions" claim
was really about. Details: `dev-docs/issues/phase4_science_path_triage.md`.

### First full real-data run: digits, 10 classes (2026-08-25)

`emuses full` on sklearn digits (1797 x 64, exported to CSV by `scripts/export_digits_dataset.py`),
`--classification` with 10 classes, `--umap_trials 100 --hdbscan_trials 100 --optuna_trials 15`.
**3 h 35 m wall, 1413 % CPU, peak RSS 3.03 GB, exit 0** — the first measured memory profile at
realistic size, which is what item 4 below was waiting on. 30 GB is not the binding constraint for
data of this shape.

**Held-out accuracy 97.50 % (351/360)**, balanced 97.61 %, against **93.33 % in the arXiv preprint**
(arXiv 2406.14309, Fig. 1c). Errors concentrate on 8→1 (x3) and 9→{4,5,7}; digits 0, 2, 3 perfect.

Two measurements worth not re-deriving:

- **The UMAP/HDBSCAN search is cheap; the prediction stage is not.** 100x100 trials took 17 minutes.
  The remaining 3 h 18 m was 10 targets x 5 folds x 15 Optuna trials x 5 inner folds. At the default
  `--optuna_trials 60` this run would take ~10-11 h, and at 3 trials the per-fold balanced accuracy
  was already 0.9895-1.0000 — the search saturates early on this data.
- **The prediction stage reproduced kNN exactly.** `KNeighborsClassifier(3)` on the same embedding
  gives the same 97.50 %, the same 9 errors, and **agrees on all 360 predictions** (1.0000), in
  0.01 s. Mechanism: 24 of the 50 winning folds were `kernel` with median sigma 0.0585 on a unit-square
  embedding, which is a nearest-neighbour lookup in disguise. This does *not* generalise to
  "the prediction stage is redundant" — digits is ten tight islands, where kNN is near-optimal and
  nothing can beat it by much. It is untested on a continuous target, which is the regime the
  neuroimaging application needs. On raw 61-D features an RBF SVM gets 98.61 % in 0.04 s; the 1.1-point
  gap is the 2-D bottleneck, not the classifier.

**Held-out metrics now actually get written (2026-08-25, ADR §2.5c).** The one-vs-rest expansion was
a local variable, so 10 prediction columns met a 1-column ground truth,
`_calculate_multi_target_validation_metrics` bailed, and the run wrote a metadata file containing
**only timing** — no held-out performance at all, announced by one WARNING inside a 3.7 MB log with
exit 0. The 97.50 % above had to be computed by hand from the predictions CSV. `HeatmapStage` now
expands the ground truth at the handover using the **training** classes (recomputing them from the
split silently shifts every column when a class is missing), targets are ordered numerically
(`sorted()` puts `target_10` before `target_2`, mis-scoring 10 of 12 targets — perturbed and
confirmed), a multi-class argmax score is reported alongside the per-target ones, and validation
reports balanced accuracy since that is what training optimises. Verified against an oracle computed
*before* the fix existed, and end-to-end on a 3-class run.

**Scope decision (2026-08-24): scientific plausibility is Chris's call, and not now.** The goal is
that the pipelines run; Chris judges the results once he can train and infer freely. Observations
about result *quality* get recorded, not acted on.

The earlier "inference emits constant predictions" claim was **withdrawn** — the constants came from
training (`ElasticNet` fits collapsing to intercept-only on rank-1 synthetic data), and the digits
measurement behind it fed the model its own pre-normalized split. Recorded, not being fixed:
degenerate fits are never reported (`confidence = 1.0 - std(across folds)`, so agreement between
useless models reads as certainty), and off-manifold input collapses the UMAP transform silently.
`test_data/` is rank-1 and `tests/regression` baselines sit at negative R², so a passing suite is not
evidence that prediction works. `dev-docs/issues/inference_constant_predictions_2026_08.md`, ADR §3.1b.

### Disconnectome signal audit (2026-08-26) — the real test, measured

`DSD_repro` is the target dataset: 1333 unlabelled + 133 labelled subjects, 902,629 voxels each
(no masking, 1.8% nonzero, 9.6 GB dense), 87 neuropsych measures, **33% of the score matrix NaN**
(median 45 missing per measure, so effective n ≈ 88 per target). The June 2026 run
(`new_pred_pipeline_12-06-2026`, ~19 h) reported `Overall_Mean_Performance = -0.1884`.

**That number was read against the wrong baseline.** At n≈88 with 5-fold CV the floor is not
R²=0: simply predicting the training mean scores median **−0.086**, mean −0.237. EMUSES' −0.188
is therefore roughly *at* the floor, not far below it.

**There is real signal, but it is weak and EMUSES is largely finding the wrong targets.**
1000-permutation test per measure, BH-corrected across 87: **13 survive q<0.10, 6 at q<0.05**
(18 at p<0.05 vs 4.4 expected). Strongest: `lpegs` R²=0.245 (q=0.017), then the `sip_*` family
(`sip_psychosoc` 0.153, `sip_body` 0.146, `sip_emo` 0.117). Of the 11 validated measures with a
non-degenerate floor, **EMUSES June scored >0 on 1** (`lpegs`); its median on them is −0.069
against PCA-10's +0.063.

**Disconnection PATTERN beats lesion VOLUME — the project's premise survives.** On the 11 validated
measures (RidgeCV, EMUSES' folds): lesion volume alone **2/11** (median −0.052), disconnection load
alone 5/11 (−0.016), volume+load 4/11 (−0.032), **pattern (morphospace PCA-10) 8/11 (+0.058)**,
volume+pattern 9/11 (+0.044). Volume adds essentially nothing once pattern is present, so spatial
location carries information burden does not. Effect is small and thins out across all 87
(pattern 10/87 vs volume 4/87). DSD_repro has **no age/NIHSS**, so "imaging beats clinical" is
*untested* here — only "pattern beats volume". Subject order recovered by fingerprinting
disconnection load; all 133 matched uniquely, corr(volume, load)=0.766 as the check.

**EMUSES' own top-6 is all left-side motor** (larapinch 0.221, lpegs 0.181, lgrip, lshflex,
laragrip, laragrasp) and **only `lpegs` overlaps the permutation-validated set**. The other five
are ARAT/motor measures with ceiling-bound distributions where the mean-predictor floor is
catastrophic (larapinch floor −2.56); a positive R² there is not evidence of prediction. Any
future ranking must exclude degenerate-floor targets or it will keep promoting them.
Lesion laterality does *not* explain the left-motor pattern — the cohort is mixed (72 right /
57 left / 4 bilateral).

**The per-fold model search costs more than the embedding does.** Splitting the gap on the 11
validated measures, all on EMUSES' own folds: EMUSES as it ran **1/11** (median −0.069); a plain
`RidgeCV` on **EMUSES' own UMAP-2 coordinates** **6/11** (+0.013); `RidgeCV` on morphospace PCA-10
**8/11** (+0.058). Changing the embedding buys 2 measures; changing the *predictor* on coordinates
EMUSES already has buys 5. Cause is visible in the saved pipelines — the feature union
(`raw`/`gwd`/`corr`/`pca`/`kpca`/`poly`) and hyperparameters are re-searched inside each outer fold,
and **0 of 87 targets have all five folds agree**, 79/87 give 4–5 distinct configs, ElasticNet
`alpha` swinging 0.004→9.8 between folds of one target.

**It is the breadth of the space, not the amount of searching — and June is not reproducible.**
More trials *help* monotonically (mean outer R² −0.379 at 1 trial → −0.010 at 60 → −0.005 at 120)
and the inner/outer gap stays flat at ~0.01, so the search is **not** overfitting its inner CV; an
earlier revision of this file claimed it was. What works is narrowing: five independent draws at
June's 60 trials give full space 2–5/11 (−0.004 to −0.028) against **`raw_only`+ElasticNet 7/11 on
every draw (+0.020 to +0.024, spread 0.004)** and fixed `RidgeCV` 6/11 (+0.019). The full space
injects the variance — median per-target range across draws **0.080**, the size of the effects
themselves. June (1/11, −0.072) sits **outside all five draws**, with `sip_house` −0.344 against a
draw range of −0.062..−0.021. Not a data difference: n and fold sizes match exactly, and the
coordinates match those stored in June's own fitted `GWD` transformers to 1.6e-07 over 206 points.
June's sampler seeds could not be reproduced, so **its per-target ranking is one unreproduced draw
and should not be read as a result** — which alone explains `larapinch` at #1. Cheapest real fix:
narrow `optim_dict_predict` to one feature recipe + one estimator. (Also corrected: an earlier
revision said UMAP-2 scored 1/11 as a *representation* — that was a custom-solver artefact.)

**Held-out test (2026-09-02) — narrowing prevents losses, it does not create gains.** 25 repeats ×
87 targets, 70/30 split, hyperparameter search *and* space choice made inside the 70% only.
Mean held-out R²: full space **−0.221**, `raw_only`+ElasticNet **−0.131**, fixed `RidgeCV` −0.135,
**mean predictor −0.133**. So the narrow config is indistinguishable from predicting the mean; what
it avoids is the tail (8.7% of full-space splits below −0.5 vs 4.7%). It beats the full space on
only 43% of paired splits while the paired mean difference is +0.090 (SE 0.017) — usually slightly
worse, occasionally avoiding a catastrophe. **`auto` (pick the space by development CV) chose the
narrow space in only 26% of splits and scored −0.227, i.e. no better than the full space — so the
fix CANNOT be automated from the data, and `raw_only`+ElasticNet is a hindsight choice that must not
be shipped as a default** (it would also contradict ADR §1.3). §9c's in-sample ranking was inflated:
`rarapinch`, ranked #1 there at 0.144, scores −0.253 held-out against a floor of −0.323.
**Only `lpegs` survives cleanly** — held-out R² 0.173, +0.219 over floor, q=0.017, and plain
`RidgeCV` reproduces it (0.184). 9 of the 13 validated measures beat their own floor, 7 by >0.05,
but as lifts over negative floors rather than real explained variance. Ship the stability guard, not
the configuration. Detail: `dev-docs/issues/disconnectome_design_audit_2026_08.md` §10.

**2-D still costs something, just less.** Full raw voxels are *worse* than PCA-10 (ridge at p≫n),
so the optimum is a handful of components, not two and not 902,629. `optim_dict_disconnectome` hardcodes
`n_components: {"value": 2}` (`optim_configs.py:254`). Raising it is a config change for the
*prediction* path, but the heatmap/effect-size machinery grids the embedding
(`emuses_utils.py:113`) and is 2-D/3-D in practice — **decide the architecture before changing
it, do not just raise the number** (cf. ADR, atomic-model constraint).

Method: `~/.claude/jobs/0d3a7417/tmp/{signal_check2,umap_signal,perm_test}.py`. All comparisons use
EMUSES' own protocol (per-target NaN drop, `KFold(5, shuffle, random_state=1859786276)`, r2). PCA is
derived from the 133×133 Gram matrix and **verified against sklearn to 1.5e-14** before use.
Permutation nulls reuse each fold's PCA, so only the y-correspondence is broken.

`--test_size 0.0` in the June command means that run produced **no held-out evaluation at all**.

### The effect EMUSES is missing is real, and EMUSES is not broken (2026-09-04)

Settled by checking the DSD literature rather than by reasoning about EMUSES. Full write-up, with
every number and the design conclusions: **`dev-docs/methodology/external_evidence_dsd.md`** — read
that before re-opening "is the method sound", the DSD/Talozzi/Matsulevits papers, MAE%, whether to
keep the model search, or UMAP dimensionality.

- **The effect is real.** Hope et al. 2024 (*Brain* 147:e11–e13) ran the frozen, published DSD model
  as a black box on PLORAS: naming R=0.31, fluency R=0.34, **n=314, p<0.001**, different cohort,
  segmentation and instrument. A frozen model cannot overfit new data. That is **R² ≈ 0.10**.
- **EMUSES is at the edge of its resolution, not broken.** Measured MDE at n≈88: **0.096 with a
  fixed model, 0.176 with the full search.** The true effect sits exactly at the first and below the
  second. The search is what turns a just-detectable effect into an undetectable one.
- **The published metrics are inflated.** The MAE% both DSD papers report has a floor at
  **85.0% mean / 86.3% median**, measured on `DSD_repro` by predicting the mean — Matsulevits'
  out-of-sample 80.67% is *below* it. Their `t(85)=−1.663` is **p=0.100**, not the reported 0.009;
  their in-sample R² is circular (|R|>0.2 voxel selection on y); their out-of-sample R² is on N=20,
  which Talozzi explicitly refuses to do on that same cohort. Only a sign test survives (p=0.023).
- **The two papers disagree on which domain predicts best** (Talozzi: language/visuospatial;
  Matsulevits: motor). That is our own seed-spread instability appearing in print. Treat any
  per-domain ranking at this n as unstable, ours included.

### What works now

`emuses full`, `umap` and `inference` all run. `heatmap` refuses with an actionable message, which is
correct: it fits against UMAP embeddings and cannot obtain them standalone (ADR §2.11).

**N-D is gated rather than silently broken** (2026-09-04). UMAP and the prediction search are both
dimension-agnostic; the heatmap is not. Before this, `n_components: 5` produced a run that trained
the morphospace, completed the **entire** nested-CV search, failed the grid on every target, and
**exited 0 with no heatmaps** — the grid's own `ValueError` was correct but fired per target after
the search, and was caught by bare `except Exception` at both call sites *and* around the whole grid
section. Now `emuses/tools/embedding_dimensionality.py` refuses the combination at configuration
time, before anything trains, naming the optim_dict to change and `emuses umap` as what does work.
A UMAP-only run may be N-D — that is a supported output. `HeatmapStage` carries the same check
independently for direct drivers (`tests/regression`), and `HeatmapStage.run` re-raises that one
error specifically while still tolerating genuine grid failures. Every guard is
perturbation-verified in `tests/test_embedding_dimensionality.py` (37 tests).

**`--allow_nd_without_heatmaps` is the way to run the N-D experiment** (2026-09-04). The gate as
first built refused the very run item 3c needs — comparing prediction quality at d ∈ {2,3,5,10} —
because the shipped dicts enable the heatmap and the flag to say "I know, skip them" did not exist.
The opt-in **does not fork the pipeline**: the full training stage runs unchanged at any width, and
only the 2-D-only grid section is skipped, so there is one code path to maintain and the d=2 and
d=5 arms of the comparison differ in the embedding alone. The default still refuses; the skip
writes `heatmaps_skipped.json` naming the width, so a folder without heatmaps says why. The trap
here is that the natural implementation — return early from the skip branch — also skips the
`inference_features` handoff below it, silently dropping held-out validation on exactly the runs
being compared. `TestSkipDoesNotStealTheInferenceHandoff` reads the source with `ast` and fails if
that return comes back.

**`test_data` cannot answer the dimensionality question.** d=2 and d=5 give bit-identical scores
there, which looks like the flag doing nothing. It is not: max |r| between any feature and any
target is **0.090**, the mean-predictor 5-fold R² is **−0.187**, and every fold model collapses to
its training mean. Identical scores are the correct answer on signal-free data. Run item 3c on
`DSD_repro`; a null on `test_data` would prove nothing.

**`emuses umap` genuinely runs at N-D** (2026-09-04, measured on `test_data`, not read off code):
d = 2, 3, 5 and 10 each produce a valid morphospace with clusters. Three things had to be fixed to
get there, each of them a silent-degradation instance rather than a crash:

- **The `entropy` UMAP metric is unusable above 2-D**, and every shipped optim dict carries it. It
  calls `np.histogramdd(emb, bins=n)`, which allocates n^d cells; at d=4 on 1333 points, 1332 sit
  alone in their own cell, so entropy stops discriminating between trials **while still returning a
  number** — the search would optimise noise. `validate_metrics_for_dimensionality` now refuses the
  combination up front, and `optim_dict_nd` (disconnectome minus entropy, weights `eigen_spread`
  3.0 / `density_variability` 2.0 / `spread` 1.0) is the N-D configuration. It is **not** a
  numerical match for the 2-D dicts — do not compare scores across them.
- **The output-folder resume path was dead code and always had been.** It tested for
  `best_umap_model.joblib`, but saved models carry a version suffix
  (`best_umap_model_v1_0_0_joblib1_5_2.joblib`), so the four-file condition could never be true and
  every "resume" silently retrained. Detection now globs for the newest match. I had reported this
  path as working from reading the code; running it is what showed otherwise.
- **Reuse runs wrote no `embeddings.npy` / `cluster_labels.npy`** — those were saved only inside the
  training function. Saving is now idempotent and outside it, so a resumed run leaves a complete
  folder for the next stage.

`--load_umap <folder-or-file>` now reuses rather than retrains (0.0 s vs 12.1 s), raises instead of
falling back to training when the path is unusable, and assigns cluster labels for the current
cohort via `hdbscan.approximate_predict`. `--umap_n_components N` overrides the dict on a deep copy
(optim dicts are module globals and the service is long-lived). A 5-D morphospace loaded with the
heatmap enabled is refused by the actual-embedding-width check, before any prediction search.

**Prediction is reproducible** — two identical invocations at `--random_state 42` give bitwise
identical scores. Five disconnections from the seed system were found and fixed; there is **one**
seeding mechanism and no second may be invented (ADR §2.9).

**Search is serial by default**, because `optuna.optimize(n_jobs>1)` is nondeterministic and no seed
fixes it. Parallel remains an opt-in that warns (ADR §2.9c).

**The backend override is per-context, not process-wide** (2026-08-25, ADR §2.9e). It was a module
global with save/restore, which is correct only under strict LIFO unwinding: two overlapping runs
would have had the first to exit restore the value captured before either started, dropping the
other back to **loky** mid-run — several times slower, with no exception and no changed number. It
was not failing only because `_run_pipeline_in_process` blocks the event loop, so nothing overlaps;
that is a side effect of blocking code in an `async def`, not a decision, and the obvious tidy-up
would have removed it. Now a `ContextVar`. The same blocking call makes the service's
`pipeline_timeout` **inert** — a hung pipeline hangs forever and the job stays `running`. Not fixed:
the fix also makes jobs genuinely concurrent, and nothing bounds how many the service accepts
(`dev-docs/issues/inert_pipeline_timeout_2026_08.md`, ADR §3.5). Found alongside it: the service's
`memory_limit_ratio` / `cpu_percent_limit` enforce nothing either, and **nothing in EMUSES is
memory-aware at all** — an oversized run dies as an OOM kill, not a stated error. That one is a
*researcher's* control rather than an operator's, blocked on nothing, and wants a measured memory
profile first — worth capturing **during** the scientific-validity runs
(`dev-docs/issues/memory_aware_execution_2026_08.md`, ADR §3.6). **loky runs in no shipped
path**: there is now exactly one place that forces the backend, in `pipeline_runner.py`, since
Phase 1F removed the last pipeline execution that bypassed the service. It is still what
`tests/regression` runs on, since that drives `EMUSESPipeline` directly — so the two backends have
never been compared numerically, the baselines having been generated on loky either way.

**Numbers are pinned.** `tests/regression/` compares prediction scores, composite score, UMAP/HDBSCAN
metrics, cluster count, cluster structure (adjusted Rand index) and embedding geometry (pairwise
distances) against stored baselines. ~80 s. Proven to fail: a one-line production change failed
composite/cluster/embedding assertions while prediction scores did *not* move, so pinning only "the
number that matters" would have missed it. Every float tolerance is *chosen*, not measured — local
variation is zero; they are cross-machine allowances. **The pinning now actually runs in a
whole-tree `pytest`** (fixed 2026-08-25, `fix/regression-conftest`): `--regen-baselines` was
declared in `tests/regression/conftest.py`, which pytest does not treat as an initial conftest, so
all 14 tests errored at setup in any run that did not name the directory — the guard was reporting
`error` rather than "regression detected" inside ~150 known failures. Verified by perturbation, and
`tests/test_pytest_option_registration.py` fails if the hook moves back. ADR §2.9d.

**Every mode goes through the service**, including local, which auto-starts one (ADR §4). A separate
in-process local path was built and reverted the same day: within forty lines it had produced a third
progress mechanism, a leaked temp file, no timeout, and a CLI where `full` behaved differently from
`umap`/`heatmap`. Submitting over HTTP locally also catches real bugs — a missing service route was
found on a laptop because of it.

**The service is its own interpreter, not a fork** (2026-08-24). That fixed three things at once:
`--n_jobs` had been silently inert on the CLI (the fork looked like a joblib worker, so
`get_safe_n_jobs` clamped it to 1); a SIGKILLed CLI used to orphan the service, which then held a
port for over an hour; and the service was invisible to `pgrep` because its argv read
`emuses.cli full`. `get_safe_n_jobs` is unchanged — the clamp was right, the process identity was
wrong.

**`--n_jobs` does not move the numbers** (Arm B, 2026-08-25). Digits, 1797 rows, binary label, one
target, through the CLI/service with only `--n_jobs` varying: **18/18 scalar metrics identical, ARI
1.0, distance correlation 1.0, max pairwise-distance diff 0**. A positive control was included
because an identical result equally fits "`--n_jobs 4` never engaged" — the pre-1E bug — and CPU
124 % → 161 % confirms it does engage. `--n_jobs` buys *threads*, not processes: the service scopes
the backend to threading on purpose, so 0 loky workers is correct rather than a failure.
`dev-docs/issues/njobs_arm_b_2026_08.md`.

**Whole-tree suite on merged `main`** (measured 2026-08-25, `pytest -q -p no:randomly`, 16 m 48 s):
**114 failed / 1416 passed / 14 skipped / 1 error**, against 150 / 1343 / 14 / 15 before the six
branches merged. Compared as failure *sets*, not counts: **zero new failures**, 50 cleared — the 115
remaining are a strict subset of the previous 165. The one surviving error is
`tests/unit/test_umap_utils.py`'s teardown. The science path is clean; what remains is concentrated
in `tests/cli`, `tests/model_registry` and `tests/deployment`. Core dumps, the missing-package
problem, the `enhanced-cli-typer` hang and repo pollution by test output are all fixed.

## Decided strategy

- **Models are atomic folders**, not separable components (ADR §2.1). Violated once and reverted.
- **One execution path** through the service, for every deployment mode (ADR §4).
- **Measure, don't infer**, and **perturb every guard** to confirm it can fail. Wall-clock on this
  machine is useless below a factor of 2 (identical code: 138/196/256 s).
- **Real data over synthetic** in tests (`dev-docs/test_quality_conventions.md`). Converting the
  InferenceStage tests from `np.random.rand()` to `test_data/` took that suite from 44% to 83%.
- **Never hardcode absolute paths.** In-repo paths derive from `PROJECT_ROOT`; external datasets come
  from the environment. Bare `python` in a subprocess is the same class of bug.
- **Test locally before pushing** — `dev_test_runner.py` on feature branches (13 tests, ~1 min), full
  CI reserved for `main`.
- **Documentation split**: `docs/` user-facing, `dev-docs/` for contributors and sessions.
- **Parked features live in `emuses/extras/`** (moved 2026-08-24, ADR §2.10). The core/extras line
  used to be 22 module names typed into `tests/test_architecture_boundary.py`, describing files that
  sat in `emuses/tools/` next to core code; it is now package layout. Core may still reach into
  extras *lazily* — `model_registry_factory` loads the cloud and database backends inside functions,
  which is why the move needed no change to core.

## Open questions / next

1. [~] **Known failures are now fenced off rather than gating (2026-09-05).** CI was red on
       every push to `main` for months, which made the red X meaningless — a genuine breakage
       would have looked identical. Two causes, both measured:
       - `production_tests.yml` installed `.[test]`; the extra in `setup.py` is named **`dev`**.
         pip warns on an unknown extra and carries on, so pytest was never installed and every
         run died at exit **127** — that workflow has **never executed a single test**. Fixed.
       - `ci.yml` gated on the whole tree, which carries known failures unrelated to the pipeline.
       Now there is a **core contract** — the suites that must stay green — defined once in
       `scripts/dev_test_runner.py::CORE_SUITES` and run by all three workflows *and* the local
       pre-push command, so "passes locally" and "passes in CI" cannot drift. Measured green
       2026-09-05, 2 m 36 s: `tests/regression` 14, `tests/pipelines` 118, `tests/inference` 65,
       `tests/flexible-inference-stage` 16, `tests/tools` 99, `tests/unit` 37, plus the
       option-registration guard. The whole-tree sweep still runs on `main` under
       `continue-on-error`, so the numbers stay visible without turning it red.
       **Never fix a core-contract failure by removing a suite from the list** — that converts a
       real failure into an invisible one, which is what the regression-conftest bug already cost.
       A branch that adds tests adds them to `CORE_SUITES` in its own commit; nothing in the list
       may name a path that does not exist yet, since pytest exits 4 on a missing path and the
       whole contract would then fail for a bookkeeping reason.
       - **What turning it on immediately found: the baselines belonged to an environment the
         lockfile did not describe.** The first CI run of `tests/regression` failed **10 of 14** —
         structurally, not by rounding. HDBSCAN found **4 clusters instead of 3**, adjusted Rand
         index **0.21** against a floor of 0.95, `target_0_Mean_Score` −0.3554 → **−0.4272**, while
         the embedding itself moved only slightly (pairwise-distance correlation 0.994). That
         pattern — a small numerical perturbation crossing a clustering decision boundary and being
         amplified downstream — is what to look for if this recurs.
         **Cause: the host CPU. Library drift and thread count were both ruled out by
         measurement** (supersedes the earlier "environment drift, not hardware" reading here,
         which was wrong). Five pins were out of date and bumping them to the validated
         combination did fix the *prediction scores*; the lockfile follows the validated
         environment, so no pinned scientific number changed. But with both sides then on
         identical versions, CI still diverged, and thread count had already been excluded (14/14
         locally pinned to 4 cores). Two further experiments settled it:
         - **Seeds, 5 runs, one machine, only `random_state` varying.** Seed 42 reproduced the
           baseline exactly (so the experiment is sound); the other four gave cluster ARI −0.004 /
           −0.030 / −0.027 / 0.059 and embedding distance correlation 0.043 / 0.050 / 0.062 /
           0.176. **On 40 samples this config has no stable cluster structure at all.**
         - **CI, same seed, same versions:** distance correlation **0.990299** — the same
           embedding, perturbed in the last bits. Two orders of magnitude away from a reseed, so
           the two causes *are* distinguishable, and this one is numba compiling UMAP's kernels
           for a different `llvm_cpu_name`.
         **Why no tolerance fixes it:** the perturbation crosses an HDBSCAN boundary (3 → 4
         clusters), which changes every Optuna trial's score, so **a different trial wins**.
         `composite_score` 0.4914 → 0.5297 is a different quantity, not a drifted one, and an
         argmax flip has no tolerance. Bitwise-across-platforms was already out of scope (ADR
         §2.9b); what is new is that "not bitwise" does **not** degrade into "within tolerance"
         once a search selects on the result.
         **Decided 2026-09-05:** the value comparisons are marked `machine_specific` and gate only
         on the machine that owns the baselines — your pre-push `--core`. CI runs
         `--core --foreign-machine` and deselects them. **The consequence to keep in mind: a green
         PR does not mean the numbers held; your local `--core` is the numerical gate.**
         `test_pipeline_produces_the_expected_outputs` replaces the lost CI coverage by comparing
         the output's *shape* against the baseline and never a value, so CI still executes the
         pipeline (~84 s) instead of deselecting its way to a 0.06 s green.
         The lockfile header still says it was compiled under **Python 3.12** while CI and the dev
         env both run 3.11 — a proper `pip-compile` under 3.11 is still owed.
       - [x] **Baselines now record their provenance** (2026-09-05): `llvm_cpu_name` (the codegen
         target — the prime suspect), a digest of the CPU feature flags, Python, platform, and the
         numerical stack versions. Every numerical failure appends a diff of that against the
         current environment, so it now says either "identical, this is a code change" or exactly
         which of those moved. Regenerated and verified byte-identical across all 23 and 31
         metrics — only the provenance block was added.
       Remaining, outside the contract and untriaged: `tests/model_registry` **32**,
       `tests/cli` **16**, `tests/foundation_fastapi_service` **10**, `tests/integration` **1**,
       `tests/security` **1**.
2. [~] **Error messages. The big one is FIXED (2026-09-05); one remains.**
       - **FIXED: every pipeline failure reached the user as `Job failed: Unknown error`.** The
         earlier note here — that the header-bearing-CSV error "never mentions `--input_header`" —
         was **wrong about the cause**. The diagnostic is excellent and does name `--input_header 0`,
         the file, the parsed shape and the dropped columns; the CLI was simply throwing it away.
         The service records the reason under `message` (`JobManager.update_job_status`) and
         `main.py:873` read only `error`, a key nothing ever writes. This affected **all** pipeline
         failures, not just CSV headers. Verified by running a header CSV through `emuses umap`
         before and after; `tests/cli` failure set unchanged (16, identical).
       - [ ] `.npy` is refused as an unsupported format, when the real problem is that the file
         people reach for (`split_dataset/test_features.npy`) is stored *after* normalization and is
         the wrong input regardless of format.
3. [ ] **Recorded, not being acted on** (result-quality judgements are Chris's call): degenerate
       fits are never reported, and off-manifold input collapses the UMAP transform silently.
       Supersedes the older "highest priority" framing — revisit once a real-data run is stable.
3b. [ ] **The continuous-target gap — the one that blocks publication.** The preprint's three datasets
       already separate by target type: digits (categorical, ten tight clusters) 93.3 % → now 97.5 %;
       stroke disconnectomes (continuous CoC) r = 0.65; **Chicago faces (continuous attractiveness)
       r = 0.09**, i.e. nothing. Digits therefore does not license "statistics can be extracted from
       UMAP space" in general — it licenses it for well-separated categorical targets, and the same
       pipeline's own counterexample is in Fig. 2c. Reviewers will find it. The missing control is a
       **continuous target with known ground truth** — cheapest version: predict a continuous property
       of the digit images that is certainly present in the pixels (ink quantity = mean pixel value,
       or stroke width), reusing the saved UMAP model. Recovers well → the regression path works and
       faces was a data/embedding problem; fails → the faces failure reproduces where the signal is
       known to exist, which is far easier to debug. Either outcome is publishable.
3c. [ ] **Disconnectome: the embedding dimensionality decision — DOWNGRADED 2026-09-04, do not act
       on this before reading `dev-docs/methodology/external_evidence_dsd.md` §7.2.** The 2026-08-26
       audit shows PCA-10 recovering signal UMAP-2 returns ≈0 on, and that still stands as a
       measurement. What changed is its interpretation: **Hope et al. 2024 obtained R=0.31
       out-of-sample at n=314 from a 2-D morphospace**, so 2-D demonstrably carries the real effect
       in this data and the binding constraint is n, not dimensions. The argument that 2-D was a
       bottleneck came from the digits run (61-D → 2-D cost 1.1 points) and does not transfer.
       **The "grid explodes as r^d" line previously here was wrong and named the wrong file**
       (corrected 2026-09-04, measured): the adaptive grid in `emuses_utils.py` *shrinks* with
       dimension — its criterion is point overlap, and 133 points in 10-D never collide, so it
       settles on 2 bins/axis. It degrades to a meaningless resolution rather than exploding, and
       that code is unreachable anyway (`DiscreteLatentSpace` is never instantiated). The live path
       is `GridCreator`/`CorrelationGridCreator` at a fixed 100×100 over two axes. So the real
       obstacle is conceptual: clustering in N-D with a 2-D projection for display puts separate
       clusters on top of each other, and the heatmap stops explaining the prediction beside it.
       **Confirm the architectural intent first — do not just raise the number.** Cheap precondition
       before any of it: UMAP at `n_components` ∈ {2,3,5,10}, fixed ridge, the 13 validated
       measures. If 5-D does not beat 2-D the question is moot. Fixing the search (3f–3i) outranks
       this. **N-D is now refused rather than silently broken** — see "N-D is gated" below.
3d. [ ] **Degenerate-floor targets poison the ranking.** ARAT-family measures (larapinch, laragrasp,
       raragrip, rarapinch …) are ceiling-bound; their mean-predictor floor reaches −2.5, so they
       surface at the top of `performance_target_rankings` on noise. EMUSES ranked larapinch #1
       (0.221) and it fails permutation testing. Either exclude targets whose floor is below some
       threshold, or report R² relative to the mean-predictor floor rather than to 0 — the latter
       half is now folded into 3f. Note the §10 held-out test found `larapinch`-style targets sort
       to the *bottom* under a stable configuration, so this is a ranking-hygiene fix rather than
       the sole explanation for June's ordering (that was irreproducibility — §9b).
   **Implementation plan for 3d/3f/3g/3h/3i — read this instead of re-deriving:**
   `dev-docs/analysis-api/prediction-validity-reporting/{context,plan,feature_vars}.md` (2026-09-03,
   consolidated, **no open questions**). Ordered: **step 0 = merge PR #10** (ready: MERGEABLE/CLEAN,
   fast-tests green, 15 ahead / 0 behind; fix its body first — it carries 1 code commit and 14 docs
   commits from this audit) → phase 1 floor → phase 2 pre-flight power report (default on, ~2.5 min)
   → phase 3 filter mode (opt-in, stays opt-in until replayed on a second dataset) → phase 4
   `emuses stability-check`, a **post-hoc command, not a pipeline default**. PR #10 is a hard
   prerequisite: at 87 targets the ordering bug would attach correct statistics to the wrong measures.
   Decided: warnings go to both the log and a top-level `WARNING.txt`; `--seed_spread` defaults to
   `off` (too heavy, and it clashes with a user-fixed `--random_state` conceptually — though not
   technically, see phase 4). Phase 2 also writes `search_spaces.json` (resolved dicts + hash, reusing
   `ModelIOManager._hash_config`): the spaces are currently persisted by **name only**
   (`log/arguments_*.json`), and a name does not pin a definition.
3j. [ ] **`model_manifest.json` under-describes its own run** (found 2026-09-03, pre-existing, small).
       `training_context.random_seeds` is `{}` in June's folder while `random_seeds.json` at the root
       is fully populated. `model_io.py:2018-2026` is meant to fill it by reading that file. Unrelated
       to the validity feature but it lives in the same code path, so fix it in its own commit.
3k. [~] **Stage separation ("build a morphospace now, add labelled data later") — dead flag wired,
       cohort defect closed, product decision still open.** Found and fixed 2026-09-04.
       - **`emuses umap` standalone works** — trains and saves the four morphospace artefacts.
       - **`emuses heatmap` standalone still refuses**, by architecture (ADR §2.11), which names the
         resolution as *a deliberately open product decision*. **Unchanged, and still open** — this
         workflow is the use case that decides it. Do not loosen the check; pick one of the three
         resolutions the ADR lists.
       - **FIXED: `--load_umap` was never read.** Declared `cli/pipeline_options.py:173`, stored
         `pipeline_config.py:110`, plumbed `pipeline_runner.py:168`, and **recommended by
         `heatmap_stage.py`'s own error message as the fix** — while no code read
         `config.load_umap`, so it silently retrained. Now handled first in `UMAPStage.run`, ahead
         of the output-folder detection: it loads the model, takes the sibling `hdbscan_model` from
         the same directory (which is how `emuses umap` writes them), and **raises rather than
         falling back to training if the path is missing** — reusing a specific morphospace and
         building a new one are different experiments.
       - **FIXED: cluster labels were the previous cohort's.** Coordinates were always re-derived
         for the current subjects (`trained_umap.transform`), but labels were loaded wholesale from
         `cluster_labels.npy`, so a reuse run with a different cohort paired n_old labels with n_new
         coordinates. `UMAPStage` now assigns the current subjects via `hdbscan.approximate_predict`
         whenever the count disagrees, and raises a named error if the saved clusterer lacks
         `prediction_data=True`. The equal-size-cohort hole this left is closed below by
         `cohort.json`.
       - **FIXED: the output-folder detection was dead code.** It looked for the bare filename
         `best_umap_model.joblib`; saved models are version-suffixed, so the branch was unreachable
         and every implicit resume retrained in silence. Now globs for the newest match. Pinned by
         `TestResumeDetectionMatchesWhatIsActuallyWritten`, which reads the source with comments and
         docstrings stripped — an earlier version of that test passed by matching the comment
         *explaining* the bug.
       - **FIXED: reuse runs left an incomplete folder** — `embeddings.npy` and `cluster_labels.npy`
         were written only inside the training function, so a resumed run produced neither. Saving
         is now idempotent and outside it.
       - **Run end to end** (2026-09-04, `test_data`): reuse via `--load_umap` takes 0.0 s against
         12.1 s to train, produces aligned embeddings and labels for the current cohort, and a 5-D
         morphospace with the heatmap enabled is refused before any prediction search.
       - **FIXED: the equal-size cohort gap is closed.** `cohort.json` identifies the cohort by a
         SHA-256 over the feature matrix. It stores **no per-subject data by default** — that file
         ships inside the shared model folder, and hashing clinical ids would not help, since they
         come from small guessable spaces and per-subject digests are recoverable by enumeration.
         `--record_cohort_ids` opts in. Unknown counts as a mismatch, so pre-existing folders
         re-derive rather than trust. Verified on a real second cohort of identical shape: same
         subjects reuse, different subjects are caught. Side effect: `--load_umap` can now reuse
         HDBSCAN's *fitted* labels when the cohort matches, which it previously always discarded.
       - **FIXED: `--resume_targets` reuses finished prediction searches.** Per target, opt-in, and
         only when the coordinates, target values, search space, fold count, trial budget and seeds
         are all unchanged. Full-precision `cv_scores.npy` is written because the per-fold CSV
         rounds to 4 dp. Per-fold or partial-study resume is deliberately **not** attempted — it
         means owning Optuna's study state machine for a much smaller saving.
       - **FIXED: several runs in one folder can be told apart.** `performance_summary/runs.json`
         records each run's embedding width, search spaces, budgets and seeds, with `latest` naming
         the current results. The timestamped aggregates are kept, not pruned: comparing
         configurations is why a folder holds more than one.
       - **Documented** in `docs/CLI_REFERENCE.md` under "Reusing Work Between Runs", including the
         implicit output-folder resume, which was previously invisible to users.
       - **`emuses inference` already runs standalone** and is verified: `--model <folder>` loads,
         scales, predicts and writes predictions plus confidence. Caveat for anyone testing it on
         `test_data`: every prediction comes out identical there, which looks exactly like the
         2025-08-27 "all predictions identical" bug and is not. The fold models genuinely are
         constant — they return one value for coordinates spanning the whole morphospace, and those
         constants are the per-fold training means of a target whose raw mean is 0.8146. That is
         correct behaviour on a signal-free target, and it means `test_data` cannot verify that
         predictions *vary*.
       - **Open**: those constant models report a confidence score of 0.9934. A mean-predictor
         claiming 99.3% confidence is misleading and deserves its own look.
   **Rationale for 3f–3i in one place:** `dev-docs/methodology/small_sample_prediction_validity.md`
   (2026-09-03) — what R² measures against, the three diagnostics and how they differ, the
   `DSD_repro` numbers, the six verified references. Read that rather than re-deriving from the
   550-line audit narrative.
3f. [ ] **Two numbers every prediction score should be printed next to** (2026-09-02, the fix the
       §10 held-out test argues for — see `disconnectome_design_audit_2026_08.md` §10). Supersedes
       the "report R² relative to the floor" half of 3d.
       - [ ] **Mean-predictor floor** per target, on that target's own n and folds. R²=0 is not the
             baseline at n≈88 (median −0.086), and for ceiling-bound targets it reaches −2.5. This
             is the single number whose absence caused this whole audit: June's −0.1884 was read as
             "poor but plausible" when it was *at* the floor.
       - [ ] **Spread across ≥2 sampler seeds.** June's per-target ranking does not reproduce; five
             independent draws of the same procedure disagree by a median of 0.080, the size of the
             effects themselves.
       - [ ] **Gate the *ranking*, not the run.** A target that does not beat its floor gets listed
             as "not predictable at this n" instead of receiving a rank. No fitting changes.
       - [ ] **Split the output into two files, and keep the denominator in both.**
             `performance_target_rankings` holds only targets that clear their floor, *ranked*.
             `performance_targets_below_floor` holds the rest as an **unranked list** — a rank
             implies an ordering by quality, and ordering noise is what put `larapinch` at #1.
             Both carry a header line naming the split: "13 of 87 targets exceeded their floor".
             **Do not simply drop the below-floor targets.** Two reasons, both load-bearing:
             (i) "87 tested, 13 carry signal" is the scientific claim; "here are 13 measures" with
             no denominator is selective reporting and a reviewer will treat it as such;
             (ii) if a run fails entirely, silently dropping everything yields a near-empty file
             that reads like a small clean result — the exact silence-looks-like-success failure
             this project keeps paying for. "0 of 87" must be impossible to miss.
       - [ ] **Show the margin, don't just threshold it.** Lift over floor is an estimate; a target
             just above and one just below are not different. Report lift *and* the seed spread so
             the margin can be compared against the noise. Held-out reference: 23/87 beat their
             floor but only 13 by more than 0.05.
       - [ ] ADR entry recording the above, and recording that automated space-switching was
             **measured and rejected** (below).
       **Working mode when this is implemented: accept-edits, not auto.** This is reporting on
       scientific output, where "it ran and looks finished" is exactly the untrustworthy signal.
3g. [ ] **Do NOT automate space-switching, narrowing, or halting on these metrics — measured.**
       The `auto` arm of the §10 test did exactly that (pick the space by development CV) and chose
       correctly in **26 %** of splits, scoring −0.227 against the full space's −0.221: no better
       than not trying. Reason it fails: a wide space's dev-CV score is inflated by its own
       max-over-60-trials selection, and a narrow space's is inflated less, so the comparison is
       biased toward the wider space by precisely the amount that makes it look good.
       The floor check is only trustworthy **in one direction** — the model's score carries that
       same selection inflation while the mean predictor carries none, so *failing* the floor is
       strong evidence and *passing* it is weak. Flag failures; never treat a pass as validation.
       If space breadth is ever tied to `n`, it must be a **documented default visible in the
       manifest**, not a silent runtime switch, and sold as tail-risk reduction (catastrophic splits
       8.7 % → 4.7 %) rather than as improvement — narrowing reaches the floor, it does not beat it.
       **Never hard-stop a run on a noisy metric**: a completed run with a loud warning is
       diagnosable, a halted one is not, and silence is this project's recurring failure mode.
3h. [ ] **Permutation testing is what actually establishes signal, and EMUSES does not do it.**
       The floor check says a model beat guessing; only a permutation null says the association is
       real. The 13-survivor result quoted throughout this audit came from a *scratch* script
       (`~/.claude/jobs/0d3a7417/tmp/perm_test.py`), not from EMUSES. Worth adding — and it is only
       affordable **with a fixed model**: 1000 permutations × 87 targets is trivial when each
       permutation refits one estimator on precomputed folds, and prohibitive if it re-runs a
       60-trial search each time. Another reason the search is the wrong place to spend compute.
3i. [ ] **Report the minimum detectable effect, and warn when nothing clears it.** `MDE = null_p95 +
       0.84 × SD`, both terms measured — no simulated effect sizes (the earlier simulated version was
       rejected by CF, correctly). SD comes from **repeated splits**, not from the across-fold SD and
       not from the permutation null: measured, the null's SD is 0.064 against the real 0.142, low by
       **1.96×**, because it holds the folds fixed and shuffles only y. On `DSD_repro` the MDE median
       is 0.096 and **1 of 13** permutation-validated measures exceeds its own MDE (`lpegs`, by
       0.029). This is the diagnostic that says *"no model would have worked"* rather than *"this
       model didn't"*. It needs fits on real y, so it cannot run before training — but with a fixed
       model those fits cost seconds, so it can run before committing to the expensive search.
3e. [ ] **Re-run DSD_repro properly** once PR #10 is merged: `--test_size 0.2` (June used 0.0 and so
       produced no held-out evaluation at all) and expect ~19 h / 9.6 GB peak. PR #10 is a hard
       prerequisite: at 87 targets the lexicographic ordering bug mis-pairs 85 of them.
4. [ ] **Resource controls.** Two separate pieces (2026-08-25): *memory-aware execution* is a
       researcher's control, blocked on nothing. **Peak RSS is now measured: 3.03 GB for the 10-class
       digits run** (1797 x 64, 3 h 35 m), so the profile that was blocking it exists
       (`memory_aware_execution_2026_08.md`). The *service
       timeout* is an operator's control and is blocked on deciding how many pipelines the service
       may run at once (`inert_pipeline_timeout_2026_08.md`). Until either enforces something,
       `memory_limit_ratio` / `cpu_percent_limit` / `max_workers` should be deleted rather than
       left reading as guarantees.
5. [ ] Run `/lad:converge` — nine months of accumulated claims unchecked against the code.
6. [ ] `tests/multi-user-service/` hangs **as a directory**; root cause unknown. Measure on a quiet
       machine. Note `tests/multi_user_service/` also exists with different contents.
7. [ ] 36 `model_registry` failures encoding the pre-ADR-§2.1 component model. **The code is right
       and the tests are obsolete — do not "fix" the code to accept them.**
8. [ ] `dev-docs/issues/optim_dict_resume_conflict.md` (deferred, workaround exists);
       `synthetic_test_data_conversion.md` (208 `np.random.rand()` across 27 files, triage first);
       multi-user admin endpoints return mock data.

---
*Long-form history: `dev-docs/project-history/detailed-status-archive-2026-07-30.md`*
*Architecture rationale: `.codebase-memory/adr.md` | Static guidelines: `lad:lad-standards` skill*
