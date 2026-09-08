# Traps

_Consolidated 2026-09-08 from `~/.claude/plans/playful-watching-naur.md` (2026-08-24), which was a
session-private file no other session could read, plus the map/heatmap work of 2026-09._

**Every entry here cost a wrong conclusion at least once.** They are not style preferences. The
common shape is that the wrong thing *succeeds*: a run exits 0, a suite goes green, a check applies
to nothing. None of them raise.

Companion files: `STATUS.md` (current state), `.codebase-memory/adr.md` (why the architecture is
what it is), `dev-docs/test_quality_conventions.md`.

---

## Science and configuration

- **`optim_dict_hcp` and `optim_dict_test` have every parameter fixed.** `UMAP_utils.py:430`
  collapses to a single trial, so raising `--umap_trials` against them does nothing at all. The
  dicts that actually search: `optim_dict_default`, `_range`, `_hard`, `_disconnectome`.
- **`noise_ratio` in `best_trial_info.json` holds `1 − noise_ratio`.** `0.0` means *every* point is
  noise. Use `noise_fraction` from the metrics extractor, which is the honest one.
- **The CLI keyword `mnist` loads digits (1797 × 64)**, not 784-dim MNIST (`inputs_utils.py:74`,
  default `dataset="digits"`). It misleads on every re-reading.
- **Digits is 10-class and `HeatmapStage` expands it to 10 one-vs-rest binary targets**, each with
  5-fold nested CV. Cost scales as classes × folds × n: ~67 min at `optuna_trials=2`, ~3.5 h at 10,
  **~55 h at the 100 of the known-good October command.** Do not plan for the last one.
- **`optim_dict_disconnectome` hardcodes `n_components: {"value": 2}`** (`optim_configs.py:254`).
  Raising it is a config change for the *prediction* path only — the heatmap machinery grids the
  embedding and is 2-D/3-D in practice. Decide the architecture before changing the number
  (see the N-D gate, `emuses/tools/embedding_dimensionality.py`).
- **sklearn 1.7's `PCA` has no `svd_solver_` attribute.** Assert on behaviour, not on that.
- **A `Mock` config fabricates any attribute**, so it is truthy and is not an `int`. That is why
  `heatmap_stage._seeds_from` and `umap_stage._as_jobs` do `isinstance` checks. This has caused
  three separate defects — assume it applies to any new `getattr` on a config object.
- **Predictions and the training target mean must be in the same space.** The grid's corrected map
  is `null + confidence × (prediction − null)`; `final_predictions` is denormalized when a scaler
  exists, so the null has to be pushed through the same transform. Getting this wrong produces a
  plausible-looking array, which is why `_null_level` raises `HeatmapIntegrityError` and stops the
  run rather than recording a per-target error.

## Measurement discipline

- **Check what you fed the model before believing what it returned.** The withdrawn "inference emits
  constant predictions" bug came from feeding a model its own
  `split_dataset/test_features.npy`, which is stored **after** normalization, while the inference
  path normalizes again. Verify the input's scale against the *training input's* scale, never the
  training output's.
- **A dramatic result deserves more scrutiny than a boring one, not less.** The digits finding stood
  for a day because it was alarming. Same shape as the green-test trap, opposite sign.
- **A green suite is not evidence about a coordinate-space change.** `test_data/features.csv` is
  rank-1 synthetic (row *i* is `[1.i, 2.i, … 8.i]`, all 50 points on a line), fits collapse to
  intercept-only at any budget, and the `regression` baselines are pinned at negative R² for exactly
  that reason. On both 40-sample datasets the winning ElasticNet has *all coefficients exactly zero*
  in every fold, so `target_0_*_Score` is mathematically independent of the coordinates.
  **Read the `swiss_roll` row instead** — it was added (2026-09-06) precisely so the suite can see a
  coordinate change. The liveness flag `n_constant_prediction_models` detects a zeroed *linear*
  model only; it cannot see a kernel that went degenerate some other way.
- **Measure, don't infer.** Wall-clock on this machine is useless below a factor of 2: identical
  code measured 138 / 196 / 256 s.
- **Perturb every guard and confirm it fails.** Two guards on one fix are not redundant.
- **Verify the perturbation actually applied**, before reading the test result. A `sed` batch
  silently no-matched and made working guards look toothless, which nearly led to weakening a
  correct test. Use an explicit string replace and assert the patch landed. A perturbation script
  that aborts on an assertion leaves the *original* code in place, so the "4 passed" that follows
  proves nothing.
- **`grep "^FAILED"` returns nothing when pytest colour is on** (ANSI prefix). Use `--color=no`.
  This once produced a comparison that read as "all 22 baseline failures fixed".
- **Compare the failure *set*, not the count.** A count can match while membership differs.
- **`np.std` on a constant array is not exactly 0.** A map holding 10 000 copies of one value
  (`np.unique` → 1, `np.ptp` → exactly 0) returned `std = 1.97e-31`, so an `== 0.0` constancy check
  called it "varying" and produced a confident-looking negative finding. Use `np.ptp(x) < 1e-9`.
- **`manage_adr(mode="update", sections=[...])` replaces the WHOLE `adr.md`** and returns
  `{"status": "updated"}` either way. It took the ADR from 653 lines to 113 on 2026-08-24;
  `git checkout .codebase-memory/adr.md` restored it. Edit the file directly, use `manage_adr` only
  to read, and check `git diff --stat` after any write.
- **Never pipe a long pytest run to `tail`** — output redirected to a file is block-buffered. Use
  the background runner, not `&`. A foreground call is capped at 2 minutes.
- **A per-target `except Exception` turns a science failure into a log line.** `KeyError:
  'combined_range'` in the heatmap logger surfaced as `{'error': ...}` on the target and made the
  tests fail three steps downstream, hiding the real cause.

## Environment

- **Interpreter: `/home/chrisfoulon/miniconda3/envs/emuses/bin/python`.** NOT miniforge3, which
  shadows `PATH`. Bare `python` in a subprocess is the same class of bug.
- **Disk is the binding constraint** (~3.6 GB free at 91 %). A `test_data` run is ~70 MB; **a digits
  run is ~1.3 GB** — an estimate of 100–200 MB took the disk to 94 %. Extract metrics and delete
  each run folder immediately.
- **Leaked services:** `ss -ltnp | awk '$4 ~ /:80[0-9][0-9]$/'` is the reliable check, because it
  asks whether a port is held. Since Phase 1E the service names itself, so `pgrep -af
  service_process` works too. **Port 8080 belongs to another user on this machine**, not EMUSES.
- **Spawning loky workers from an already-forked process hangs** — reproduced directly. That is why
  the `get_safe_n_jobs` clamp exists and must not simply be deleted.
- **UMAP forces single-threaded execution whenever a seed is set** — the runs say so:
  `n_jobs value 1 overridden to 1 by setting random_state`. So UMAP is not a source of run-to-run
  variation, and `--n_jobs` cannot speed it up. HDBSCAN's `core_dist_n_jobs=-1` is the remaining
  parallel path in that stage.
- **CI cannot see the numerical baselines.** It runs `--core --foreign-machine`, which deselects the
  `machine_specific` tests. On a different CPU numba compiles UMAP's kernels differently, the
  embedding shifts in the last bits, HDBSCAN's cluster count changes, a different Optuna trial wins,
  and `composite_score` becomes a *different quantity* rather than a drifted one — no tolerance
  covers an argmax flip. Run plain `--core` locally if you touched the science path.

---

## Standing decisions — do not re-litigate

- **Scientific plausibility is Chris's call.** Fix anything obviously broken; do not build quality
  gates, degeneracy detectors or plausibility checks on your own initiative. Record such
  observations for him instead of acting on them.
- **One execution path: every mode goes through the service** (ADR §4); local auto-starts one. A
  separate local path was built on 2026-08-23 and reverted the same day — within forty lines it had
  produced a third progress mechanism, a leaked temp file, no timeout, and a CLI where `full`
  behaved differently from `umap`/`heatmap`. Going over HTTP locally also catches real bugs.
- **The service is its own interpreter, not a fork** (Phase 1E). `get_safe_n_jobs` is correct and
  unchanged; the process identity was the bug.
- **Serial Optuna search is the default** (ADR §2.9c). `optuna.optimize(n_jobs>1)` is
  nondeterministic and no seed fixes it. Parallel is an opt-in that warns.
- **`--hdbscan_jobs` is inert** and is documented and guarded, **not wired or removed**. Same for
  the five `NOT_IMPLEMENTED` options (`--min_cluster_size`, `--model_selection`,
  `--use_enhanced_pipeline`, `--parallel_models`, `--inspect_data_state`). Do not implement or
  remove them without asking.
- **Bitwise reproducibility across platforms is out of scope** (ADR §2.9b). Every tolerance in
  `tests/regression/` is *chosen*, not measured — local variation is exactly zero.
- **The master-seed derivation is the only seeding mechanism** (ADR §2.9). Never invent a second.
- **An EMUSES model is an entire folder** (ADR §2.1). The registry is a path lookup service.
- **Standalone `emuses heatmap` is architecturally unsupported** (ADR §2.11) — it fits against UMAP
  embeddings, and `--load_umap`/`--load_embeddings` are read by `UMAPStage`, which a heatmap-only
  run never executes. It fails fast with an actionable message. Do not "fix" it by loosening the
  check.
- **Never fix a core-contract failure by removing a suite from `CORE_SUITES`**, and never widen a
  regression tolerance to make a runner green. Baselines regenerate only via
  `pytest tests/regression --regen-baselines`, and the commit message must say what moved the
  numbers and why.
