# STATUS — EMUSES
_Last touched: 2026-08-24_

## Goal

A predictive modelling tool for neuroimaging research, usable at three scales: local model
development, collaborative sharing within labs, and a public registry with peer review.

Immediate goal: **a tool whose runs you can trust and publish from** — it completes, it does what its
flags say, and the same command twice gives the same answer.

## State of play

**On `main`, plus `feat/inference-on-service` (Phase 1F, PR #9 open) and `fix/science-path-tests`
stacked on it (Phase 4).** Plan:
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

### What works now

`emuses full`, `umap` and `inference` all run. `heatmap` refuses with an actionable message, which is
correct: it fits against UMAP embeddings and cannot obtain them standalone (ADR §2.11).

**Prediction is reproducible** — two identical invocations at `--random_state 42` give bitwise
identical scores. Five disconnections from the seed system were found and fixed; there is **one**
seeding mechanism and no second may be invented (ADR §2.9).

**Search is serial by default**, because `optuna.optimize(n_jobs>1)` is nondeterministic and no seed
fixes it. Parallel remains an opt-in that warns (ADR §2.9c).

**Numbers are pinned.** `tests/regression/` compares prediction scores, composite score, UMAP/HDBSCAN
metrics, cluster count, cluster structure (adjusted Rand index) and embedding geometry (pairwise
distances) against stored baselines. ~80 s. Proven to fail: a one-line production change failed
composite/cluster/embedding assertions while prediction scores did *not* move, so pinning only "the
number that matters" would have missed it. Every float tolerance is *chosen*, not measured — local
variation is zero; they are cross-machine allowances.

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

**Test suite collects cleanly and does not crash**: 2608 tests, 0 errors. In the working subset
(`tests/pipelines tests/inference tests/flexible-inference-stage tests/foundation_fastapi_service
tests/tools tests/cli` + the six guard files): **33 failed / 540 passed / 2 skipped**, down from 68
before Phase 4, with no new failures. What remains is entirely in `tests/cli` and
`tests/foundation_fastapi_service` — the science path is clean. Core dumps, the missing-package problem, the `enhanced-cli-typer`
hang and repo pollution by test output are all fixed.

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

## Open questions / next

1. [ ] **Phase 5** — finish the `emuses/tools/` → `emuses/extras/` move (22 modules, 8 import
       rewrites). `tests/test_architecture_boundary.py` verifies it.
2. [ ] The 33 remaining failures in `tests/cli` / `tests/foundation_fastapi_service` are
       untriaged: 6 `test_enhanced_models_commands`, 5 `test_models_hdbscan`,
       5 `test_inference_preprocessing_params`, 3 each in `test_security_validation`,
       `test_models_commands`, `test_inference_integration`, and singles elsewhere.
3. [ ] **Two error messages.** A header-bearing CSV fails with "No numeric data remaining" and never
       mentions `--input_header`, which works. `.npy` is refused as an unsupported format, when the
       real problem is that the file people reach for (`split_dataset/test_features.npy`) is stored
       *after* normalization and is the wrong input regardless of format.
4. [ ] **Recorded, not being acted on** (result-quality judgements are Chris's call): degenerate
       fits are never reported, and off-manifold input collapses the UMAP transform silently.
       Supersedes the older "highest priority" framing — revisit once a real-data run is stable.
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
