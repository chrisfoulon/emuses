# STATUS — EMUSES
_Last touched: 2026-09-02_

## Goal

A predictive modelling tool for neuroimaging research, usable at three scales: local model
development, collaborative sharing within labs, and a public registry with peer review.

Immediate goal: **a tool whose runs you can trust and publish from** — it completes, it does what its
flags say, and the same command twice gives the same answer.

## State of play

**All work is on `main`; no branches outstanding** (2026-08-25). Six branches converged that day —
Phase 1F (PR #9), Phase 4, Phase 5 (the extras move), the `n_jobs` Arm B evidence, the regression
conftest fix and the parallelism backend scope. Plan:
`~/.claude/plans/playful-watching-naur.md` (consolidated 2026-08-24 — read that, not the older
per-phase notes).

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
`alpha` swinging 0.004→9.8 between folds of one target. At ~70 training rows that search is fitting
selection noise. Cheapest real fix available: fix the feature union and estimator, tune one
regularisation parameter. (Earlier revisions of this file said UMAP-2 scored 1/11 as a
*representation* and blamed the embedding alone — that figure was a custom-solver artefact;
corrected above.)

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

### What works now

`emuses full`, `umap` and `inference` all run. `heatmap` refuses with an actionable message, which is
correct: it fits against UMAP embeddings and cannot obtain them standalone (ADR §2.11).

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

1. [ ] The 33 remaining failures in `tests/cli` / `tests/foundation_fastapi_service` are
       untriaged: 6 `test_enhanced_models_commands`, 5 `test_models_hdbscan`,
       5 `test_inference_preprocessing_params`, 3 each in `test_security_validation`,
       `test_models_commands`, `test_inference_integration`, and singles elsewhere.
2. [ ] **Two error messages.** A header-bearing CSV fails with "No numeric data remaining" and never
       mentions `--input_header`, which works. `.npy` is refused as an unsupported format, when the
       real problem is that the file people reach for (`split_dataset/test_features.npy`) is stored
       *after* normalization and is the wrong input regardless of format.
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
3c. [ ] **Disconnectome: the embedding dimensionality decision.** The 2026-08-26 audit (above) shows
       PCA-10 recovering signal that UMAP-2 returns ≈0 on, so `n_components: 2` is costing real
       results on the target dataset. This is the same continuous-target gap as 3b, now measured on
       the data that matters. Before changing anything, decide: does the heatmap/effect-size stage
       stay 2-D while prediction uses more components, or does the whole embedding move? The grid in
       `emuses_utils.py:113` is generic but explodes as r^d, and every plot path assumes 2-D/3-D.
       **Confirm the architectural intent first — do not just raise the number.**
3d. [ ] **Degenerate-floor targets poison the ranking.** ARAT-family measures (larapinch, laragrasp,
       raragrip, rarapinch …) are ceiling-bound; their mean-predictor floor reaches −2.5, so they
       surface at the top of `performance_target_rankings` on noise. EMUSES ranked larapinch #1
       (0.221) and it fails permutation testing. Either exclude targets whose floor is below some
       threshold, or report R² relative to the mean-predictor floor rather than to 0.
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
