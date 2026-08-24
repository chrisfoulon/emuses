# STATUS — EMUSES
_Last touched: 2026-08-24_

## Goal

A predictive modelling tool for neuroimaging research, usable at three scales: local model
development, collaborative sharing within labs, and a public registry with peer review.

Immediate goal: **a tool whose runs you can trust and publish from** — it completes, it does what its
flags say, and the same command twice gives the same answer.

## State of play

**Branch `chore/core-boundary`, pushed, 32 commits ahead of `main`.** Plan:
`~/.claude/plans/playful-watching-naur.md` (consolidated 2026-08-24 — read that, not the older
per-phase notes). Merge to `main` when `full`, `umap` and `inference` run end to end and
`tests/regression` passes — not when every feature is implemented.

### The open defect that matters

**Silent degeneracy: models that know nothing and report certainty.**

The earlier claim on this line — "inference emits constant predictions" — was **withdrawn on
2026-08-24**. Reproducing it contradicted it. The constants come from *training*: every fold
estimator on `test_data/` is an `ElasticNet` with all coefficients zero, returning its intercept
(the training-target mean, 0.807) for any input across a grid spanning [-50, 50]². EMUSES' own
`prediction_values.npy` already holds one unique value across 10 000 grid points, with
`confidence_values.npy` at exactly 1.0. Inference faithfully applies a model that was already
constant. The digits measurement behind the original claim fed the model its own
`split_dataset/test_features.npy`, which is stored *after* normalization while the inference path
normalizes again — the input was normalized twice.

What is real, confirmed, and open:

1. **Nothing reports a degenerate model.** Confidence is `1.0 - std(across fold predictions)`, so
   perfect agreement between useless models reads as perfect confidence. The evidence exists at
   training time — report it there.
2. **Off-manifold input collapses the UMAP transform silently.** The pre-normalized split gives
   **1** distinct embedding, the same rows raw give 10, all 50 raw give 50. No error, exit 0.
3. `.npy` rejected (EMUSES writes its own splits as `.npy`) and header-bearing CSV rejected.

**`test_data/` cannot validate prediction quality** — `features.csv` is a rank-1 synthetic ramp, so
fits collapse at any budget, and `tests/regression` baselines are pinned at negative R². A passing
regression suite is not evidence that prediction works.

Whether digits shows a genuine *inference* defect is unresolved; settling it needs a re-run with raw
input (~3.5 h). `dev-docs/issues/inference_constant_predictions_2026_08.md`, ADR §3.1b.

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

**Test suite collects cleanly and does not crash**: 2592 tests, 0 errors. 22 known failures, 386
passing in the working subset. Core dumps, the missing-package problem, the `enhanced-cli-typer`
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

1. [ ] **Report degenerate models, and guard the UMAP transform collapse** (above). Highest priority.
2. [ ] **Finish the `n_jobs` evidence.** The service fix was measured only at 48 samples. The agreed
       standard was a larger-n arm too, because a misbehaving parallel reduction shows there first.
       Build Arm B: digits as CSV with a **binary** label — 1797 rows kept (so the randomized PCA
       path stays reachable) but one target instead of ten, ~7 min a run. Compare `n_jobs` ∈ {1, 4}.
3. [ ] **Phase 1F — put `emuses inference` on the service.** `_execute_inference_locally` bypasses it
       entirely, which blocks shared-model inference on a server. `/api/v1/inference` and
       `/api/v1/inference/async` already exist, so this is likely wiring. **Do the bug first** —
       wiring a broken path through the service makes it broken in two places.
4. [ ] **Phase 4** — ~33 science-path test failures, triaged by root cause. **Phase 5** — finish the
       `emuses/tools/` → `emuses/extras/` move (22 modules, 8 import rewrites).
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
