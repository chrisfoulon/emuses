# STATUS — EMUSES
_Last touched: 2026-08-23_

## Goal
A predictive modelling tool for neuroimaging research, usable at three scales: local model
development by individual researchers, collaborative sharing within labs, and a public model
registry with peer review for the wider community.

## State of play

**Current work: `chore/core-boundary`, 22 commits ahead of `main`.** Driving toward a tool
that can be trusted to run and to publish from; plan at
`~/.claude/plans/playful-watching-naur.md`, findings in
`dev-docs/issues/phase0_cli_runnability_2026_08.md` and
`dev-docs/issues/parallelism_backend_analysis_2026_08.md`.

**Prediction is now reproducible** (Phase 1D, `687f7a9` + `4152635`). Two identical
`emuses full` invocations at `--random_state 42` produce bitwise identical prediction scores,
`best_trial_info.json` and `embeddings.npy`. Previously the scores differed (`Mean_Score` −0.5575 vs
−0.5829) while UMAP/HDBSCAN matched. **Prediction numbers moved** relative to any run before
2026-08-23, because the CV folds no longer use the hardcoded 42.

Five disconnections, all in the prediction path, all now fed by the master-seed derivation that
already existed in `emuses_pipeline.py:87` — **there is one seeding mechanism, do not add a second**:

- `nested_optuna_cv` created its study with no `sampler` → `TPESampler(seed=None)`. Each outer fold
  now gets its own derived sampler seed; one shared seed would make every fold replay the same TPE
  startup trials.
- `_optimise_target` never passed `random_state`, so CV folds always used the default 42.
- `build_estimator` hardcoded `random_state=42`, and `LogisticRegression(solver="saga")` shuffles.
- `PCAGWD`/`KernelPCAGWD` were unseeded. **This was invisible on `test_data` by construction**:
  `svd_solver="auto"` only switches to the randomized solver once `max(X.shape) > 500`, and the GWD
  matrix is n×n in the samples. Reproducible on 50 samples, irreproducible on a real cohort.
- `optimize_ae_pretraining` had an unseeded study and a hardcoded `random_state=42` caller.

Guarded by `tests/test_seed_wiring.py`, each guard confirmed to fail when its fix is reverted. The
strongest is "no `optuna.create_study` in `emuses/` without an explicit sampler", which admits no
exemptions. The seed-audit test ("every key in `random_seeds.json` is read") is deliberately labelled
weak in its own docstring: it would **not** have caught this bug, because `prediction_seed` and
`cv_seed` already had readers in `robust_ood_evaluation` while the main path ignored them.

**Reproducibility is not finished: `optuna.optimize(n_jobs>1)` is nondeterministic** (Phase 2,
`b28e664`). Phase 1D fixed the prediction path; the UMAP/HDBSCAN *search* still varies run to run at
a fixed seed whenever there is something to search. Optuna's parallel mode runs trials concurrently,
so TPE's suggestion depends on which trials have finished when each one asks — thread timing, which
no seed controls. The sampler *is* seeded (`UMAP_utils.py:633`); that is not enough. Three repeats at
seed 42, one variable changed:

| `umap_jobs` / `hdbscan_jobs` | metrics identical |
|---|---|
| 4 | 10 of 20 |
| 1 | 20 of 20 |

**Fixed** (`bec42c9`): `umap_jobs`/`hdbscan_jobs` now default to 1, declared in `PipelineConfig`
and decided in one place (`umap_stage._resolve_search_jobs`). Parallel search stays an opt-in that
warns. Three things surfaced doing it: `umap_jobs` was *already* serial by an undeclared `None -> 1`
mapping; **`hdbscan_jobs` is inert** (`parallel_mode="umap"` is never overridden, so the inner search
always runs serially — documented and guarded, not wired, same treatment as the five
`NOT_IMPLEMENTED` options); and `--help` told users a seed forces `n_jobs` to 1, which nothing does.
UMAP's *own* `n_jobs` is overridden when seeded, which is where the confusion came from — optuna's
is not, and optuna's is the one that decides the search.

**CLI runs were reproducible before that only by accident** — the fork clamps jobs to 1, and Phase
1B2 removes that clamp. Numbers and the rest of the arms in
`dev-docs/issues/reproducibility_tolerances_2026_08.md`. `hdbscan_core_dist_n_jobs` was re-measured
on a properly clustering config (20/20 across 1 vs −1); its earlier weak-evidence caveat is closed.

**Numbers are pinned** (Phase 3, `9108107`). `tests/regression/` compares prediction scores, composite
score, the UMAP/HDBSCAN metrics, cluster count, cluster structure (adjusted Rand index — ids are
arbitrary) and embedding geometry (pairwise distances — UMAP is fixed only up to rotation and
reflection) against stored baselines. ~80 s, its own config, `--regen-baselines` to regenerate
deliberately. **Proven to fail**: a one-line production change (UMAP model seed shifted by one)
failed composite score, cluster structure and embedding geometry — while prediction scores and
cluster count did *not* move, so pinning only "the number that matters" would have missed it. Every
float tolerance is *chosen*, not measured: local variation is exactly zero, so they are cross-machine
allowances for CI. The first CI run is the real test of them.

Two traps recorded there, each of which cost a wrong conclusion or nearly did: `optim_dict_hcp` (the
fixture's dict) has **all parameters fixed**, so `UMAP_utils.py:430` collapses it to a single trial
and raising `umap_trials` against it does nothing; and `noise_ratio` in `best_trial_info.json` holds
`1 − noise_ratio`, so **0.0 means every point is noise**. At the fixture config HDBSCAN returns zero
clusters, all 40 points noise — so the regression suite cannot pin cluster structure from it.

**`emuses full` runs (verified 2026-08-22).** ~26 s on `test_data/`, single- and multi-target, output
validates via `ModelIOManager.validate_model()`. `inference` works. This was genuinely open: the
session test fixture drives the *Python API*, while the CLI goes out over HTTP to an auto-started
FastAPI service, and only the first had ever been checked.

**`emuses umap` now runs; `emuses heatmap` cannot, and that is architectural** (Phase 1C). The three
CLI defects are fixed: `umap`/`heatmap` declared no options at all, nothing set the `"command"` key
the service-fallback path reads (so `umap` silently became `full`), and the client posted to
`/api/v1/jobs/pipeline/umap` which the server never defined. All three commands are now stamped from
**one** option declaration (`emuses/cli/pipeline_options.py`) — Typer honours a programmatically
assigned `__signature__`, so the options stay ordinary readable Python in a single place instead of
three copies that drift. `full --help` is byte-identical to before; `umap`/`heatmap` went from 13 to
67 lines of help.

**The CLI wiring was the smaller half.** Fixing it only got the run as far as the pipeline, where
three further defects appeared — none of them findable by reading, each surfaced by running the
command:

- `split_dataset` passed `self.scores` straight into `train_test_split`; unsupervised runs have no
  scores, so sklearn indexed `None`.
- `InferenceStage` was added whenever `test_size > 0`, including to a UMAP-only job that has no
  prediction models for it to validate.
- `HeatmapStage` consumed `prediction_train_coords` unchecked, dying as `TypeError: 'NoneType'
  object is not subscriptable` four frames inside a joblib worker.

**Standalone `heatmap` is unsupported by design, not merely unwired.** HeatmapStage fits against
UMAP embedding coordinates, and `--load_umap`/`--load_embeddings` are read by UMAPStage — which a
heatmap-only run does not execute. There is no route by which it can obtain its input. It now fails
fast naming the missing context key, the stage that produces it, and `emuses full` as the command
that works. Whether `heatmap` should imply UMAP, require a trained model, or be removed is a product
decision, deliberately not taken.

`PredictionStage` is retired but was still advertised in three places (`app.py` `valid_stages`,
`service_client.py` `valid_types`, `main.py` `stage_classes`); all three corrected.

**Four CLI options were silently discarded** and are now fixed (`9c1ce71`).
`--hdbscan_core_dist_n_jobs`, `--hdbscan_approx_min_span_tree`, `--input_file_list` and
`--recursive-input-file-search` were accepted, dropped in `_context_to_emuses_args`, and replaced by
`PipelineConfig` defaults with no warning. Five more (`--min_cluster_size`, `--model_selection`,
`--use_enhanced_pipeline`, `--parallel_models`, `--inspect_data_state`) are advertised but read by
nothing — they need implementing or removing, which is a product decision, and are declared as
`NOT_IMPLEMENTED` in `tests/test_cli_option_mapping.py` so they stay visible.

PR #5 was squash-merged on 2026-08-19 (`015a307`), carrying the LAD
v2 migration, CI trigger/concurrency fixes, dependency declarations, and the test-suite repairs
below. Squash was required: that branch's history contained the injection-named directories.

**Branches pruned to three** (2026-08-19). Nine local and twelve remote branches were deleted after
checking each with `git rev-list --count main..<branch>` — all were genuinely contained in `main`.
What remains on the remote: `main`, `gh-pages` (vestigial; Pages runs on `build_type: workflow` via
`docs.yml`, not from the branch), and whatever dependabot currently has open. `origin/fix/app-validation-and-error-handlers`
went too: PR #4 was closed as superseded and its content is on `main` (`app.py:362`, `app.py:499`).

**Repo root holds four `.md` files** (2026-08-19): `CHANGELOG`, `CLAUDE`, `README`, `STATUS`. Nineteen
files of session working notes were deleted and two still-live documents moved into `dev-docs/`. The
practice that generated them is fixed at source: `test_quality_implementation_guide.md` instructed
sessions to append PDCA results to the repo root, and now points at `dev-docs/`.

**Core system is built and merged.** Model registry (all three deployment modes), scientific
pipeline, inference, multi-user auth, observability and CI/CD are all on `main`.

**Web GUI is not implemented.** Both `feature/web-gui-gradio` and
`feature/web-gui-gradio-implementation` merged, but they carried planning documents only — there is
no gradio code or dependency anywhere in the tree. Planning lives in `dev-docs/web-gui-gradio/`.

**Tooling**: LAD is now a Claude Code plugin (`lad@lad` 2.1.0), not a `.lad/` subtree. Static
guidelines are in the `lad:lad-standards` skill. The codebase is indexed in codebase-memory-mcp as
`home-chrisfoulon-neuro_apps-emuses` (14k nodes), with rationale in `.codebase-memory/adr.md`.

**Environment**: `conda activate emuses` (it lives in the old `~/miniconda3`, registered in
`~/.condarc` so it resolves by name). Python 3.11, editable install pointing at this repo.

**Test suite — collects cleanly, does not pass, but no longer crashes.** 2563 tests collect with 0
errors. That was briefly untrue and unnoticed: from Phase 1B1 until 2026-08-23,
`tests/integration/test_cli_api_parallelism.py` imported a function 1B1 had deleted, which failed
collection for the **whole** run. Fixed in `bec42c9`. Repaired since 2026-07-31:

- **No more core dumps.** All three were one root cause: `PipelineConfig.__post_init__` built a new
  `logging.handlers.QueueListener` on every instantiation, so listener threads accumulated and raced
  for stderr at shutdown, aborting the process (exit 134) *after* tests had already passed. Fixed by
  a module-level singleton, plus a `multiprocessing.util.Finalize` that stops the listener before
  the queue's pipe closes. `conftest.py` used to patch `atexit.register` autouse, which silently
  swallowed that registration; that patch was removed on 2026-08-22 (`31546b5`) once its cause was
  fixed — it had also been disabling the CLI's own service-cleanup safety net during tests.
- **Environment was missing 47 pinned packages**, plus undeclared `aiosqlite` and a `bcblib` pin
  three versions stale. A large share of "failures" were missing imports.
- **`enhanced-cli-typer` no longer hangs** — one test patched a mock session that `__aenter__`
  discarded, so it retried a dead port forever.
- **Session pipeline fixture repaired** (2026-08-06). It set `args.scores_dataset` where the
  pipeline reads `args.scores`, never called `add_stage()`, and used a prefix that renames the files
  the registry looks for. Its test passed throughout because it tolerated the fixture failing.
- **The suite no longer pollutes the repo** (2026-08-19). Nine directories with shell-injection
  payloads for names (`` `cat /etc/passwd` ``, `$(whoami)_output`, …) were found *tracked in git*,
  created by running the CLI security tests from the repo root. Removed; the CLI now validates
  output paths before creating them; and two autouse fixtures run every test in `tmp_path` and fail
  the session if anything appears in the repo root.
- **Repo root cleaned** (2026-08-19). Nine injection-named directories plus ~14 stale test-output
  files were removed, most of them tracked. Several referenced
  `/mnt/c/Users/Tolhsadum/PycharmProjects/emuses` — a machine this repo has not lived on for a long
  time. `test_name_logic.py` went with them, closing that open question.
- **One flaky test fixed** — it asserted that a 100-sample unseeded draw reproduced its population
  parameters, which fails 46% of the time.

Still open: `tests/multi-user-service/` hangs **as a directory** (no single file does), and ~100
pre-existing failures, of which 36 in `model_registry` are one cluster — see the triage doc.

Note `tests/multi-user-service/` and `tests/multi_user_service/` both exist, with different
contents. Probably unintended, but deliberately not merged while one of them hangs.

`python scripts/dev_test_runner.py` → 13/13 is the pre-push gate. **It was running against the wrong
interpreter until 2026-08-19** — bare `python`/`pytest` on `PATH` resolved to miniforge3 (Python
3.12, pytest 9), not the `emuses` env the suite uses. It now runs `sys.executable -m pytest`. Both
environments pass 13/13, so nothing was hidden, but the gate was not testing what it claimed to.

## Decided strategy

- **Models are atomic folders**, not separable components. The registry is a folder lookup service
  and nothing more. This was violated once and had to be reverted; see `.codebase-memory/adr.md` §2.1.
- **Test locally before pushing** — `dev_test_runner.py` on feature branches (13 tests, ~1 min),
  full CI reserved for `main` (~30 min). Deliberate, to conserve GitHub education credits.
- **Real data over synthetic** in tests. Converting InferenceStage tests from `np.random.rand()` to
  `test_data/` fixtures took that suite from 44% to 83% passing — the failures were the synthetic
  data, not the code. See `dev-docs/test_quality_conventions.md`.
- **Never hardcode absolute paths.** In-repo paths derive from `PROJECT_ROOT`; external datasets come
  from the environment (`EMUSES_TEST_DATA_ROOT`, and `EMUSES_DSD_ROOT` / `EMUSES_FIGURE_OUT` for the
  figure script). A hardcoded Windows path had silently broken the session pipeline fixture for
  months, and on 2026-08-19 three more live files were found still pinning
  `/mnt/c/Users/Tolhsadum/PycharmProjects/emuses` — including the coverage script `CLAUDE.md`
  advertises, which therefore could not run at all. All fixed. Bare `python` in a subprocess is the
  same class of bug: it resolves to whatever is first on `PATH`, not the running interpreter.
- **Documentation split**: `docs/` is user-facing, `dev-docs/` is for contributors and sessions.

## Open questions / next

**Current sequence** (plan: `~/.claude/plans/playful-watching-naur.md`):

- [x] ~~Phase 0 — does `emuses full` still run from the CLI?~~ Yes. `umap`/`heatmap` do not.
- [x] ~~Phase 1A — reconnect the dropped CLI options~~ (`9c1ce71`).
- [x] ~~Phase 1B1 — repair the parallelism layer~~ (`512aad8`). `get_process_hierarchy_depth()`
      had never worked (walked a `.parent` attribute `multiprocessing.Process` lacks), so backend
      selection always returned `loky`, including in workers. Its tests mocked `current_process`
      with a `MagicMock`, which fabricates the missing attribute — they asserted against an object
      model that does not exist. The `force_backend="threading"` override is kept but now scoped
      via a `parallelism_backend()` context manager, because removing it let detection pick `loky`
      in the main process and spawn eight worker processes for millisecond tasks.
      **Machine timing is unusable for decisions here**: identical code measured 138s/196s/256s for
      the same test.
- [x] ~~Phase 1D — finish the seed derivation wiring~~ (`687f7a9`, `4152635`). See above.
- [x] ~~Phase 2 — measure run-to-run variation~~ (`b28e664`). Harness:
      `scripts/measure_reproducibility.py`. Found the remaining nondeterminism (see above).
      `n_jobs` (model training) and `hdbscan_core_dist_n_jobs` both changed nothing — but the
      latter was measured on a degenerate zero-cluster result, so it is weak evidence.
- [x] ~~Default `umap_jobs` / `hdbscan_jobs` to 1~~ (`bec42c9`). See above. Also unblocked
      whole-suite collection: `tests/integration/test_cli_api_parallelism.py` still imported
      `get_process_hierarchy_depth`, deleted in 1B1, which failed collection for the entire run.
- [x] ~~Phase 3 — numerical regression suite~~ (`9108107`), on its own config. See above.
- [ ] **Phase 1B2 — restore in-process local execution.** Deliberately sequenced *after* Phase 3, so
      that switching real parallelism on happens with a suite able to detect whether it moved
      anything. Open decision when it comes up: `--service` / `--service-url` in local mode is
      currently popped and ignored (`main.py:1071`, `:1074`) — wire it or remove it. ADR §4 defines local mode as "CLI,
      file-based storage, in-process execution", but `_full_async` (`main.py:1107`) always forks a
      FastAPI service and submits over HTTP. Reuse `PipelineRunner._run_pipeline_in_process`. Two
      things to decide rather than drift into: keep the endpoint's path validation on the local path,
      and pick a parallelism backend deliberately — the CLI sets loky (`main.py:1044`) and the runner
      then forces threading (`pipeline_runner.py:391`); keep threading initially so results match
      today's, since Phase 2's baseline depends on it.
- [x] ~~Phase 1C — give `umap`/`heatmap` a real option set, sharing one declaration with `full`.~~
      Done. `umap` runs; `heatmap` cannot without UMAP embeddings and now says so. See above.
      Guards: `tests/test_cli_option_mapping.py` 8 -> 20 tests, new `tests/test_stage_only_commands.py`.
- [ ] Phase 4 — the ~33 science-path test failures. Phase 5 — finish the extras move.

Order is **1D → 2 → 3 → 1C → 1B2 → 4 → 2C-bis → 5** (decided 2026-08-23): build the detector before the event
it exists to detect.

**Leaked test services: fixed and guarded** (`31546b5`). `test_concurrent_job_submission` spawned
real services and left them running; one from 2026-08-19 held port 8000 for days, answering HTTP
with 500. Since `_execute_via_remote_service` defaults to `localhost:8000` (`main.py:1173`), every
CLI run contacted it first — had it answered 200, a real job would have gone into a test fixture's
service. The test now patches the service lifecycle, and a session-scoped autouse fixture in
`tests/conftest.py` fails the session on leaked children. Nothing is listening on 8000–8010 as of
2026-08-23. **`pgrep -af uvicorn` does not detect these** — the service is a fork of the CLI
process, so its argv still reads `python -m emuses.cli full`. Use
`ss -ltnp | awk '$4 ~ /:80[0-9][0-9]$/'`.

- [ ] Run `/lad:converge` — nine months of accumulated claims have not been checked against the
      code. Two were already found and fixed on 2026-07-30 (a stale "ready for merge" banner, and
      `CLAUDE.md` naming a deleted branch as current); the rest of the sweep has not been done.
- [x] ~~Merge PR #5~~ — squash-merged 2026-08-19 as `015a307`.
- [ ] **Test suite triage** — full findings in `dev-docs/issues/test_suite_triage_2026_07.md`.
      Remaining, in order:
      - [ ] `tests/multi-user-service/` hangs as a directory. Not the QueueListener leak (still
            hangs after that fix), not any single file. A 9-file prefix reproduces it. Root cause
            unknown. **Measure this on a quiet machine** — a run on 2026-08-06 died with a
            `MemoryError` while swap was 100% full from unrelated desktop processes, at a different
            point than the previous run.
      - [x] `test_performance_stress.py` — now 16 passed (was 2 failed/14 passed), ~163s, exits
            cleanly. The 6-day `epoll` orphan does **not** reproduce and its cause was not
            identified; `pytest.ini` now carries a global `timeout = 600` net so a future hang
            fails the same day instead of running for a week.
      - [ ] Mark the remaining slow tests. `enhanced-cli-typer` is still the bulk of the runtime;
            only `test_performance_stress.py` is marked `slow` so far.
      - [ ] 36 `model_registry` failures whose fixtures encode the pre-ADR-§2.1 component model
            (`.pkl` files, `prediction_ensemble/`). **The code is right and the tests are obsolete —
            do not "fix" the code to accept them.** Now unblocked: the session fixture produces a
            genuine complete folder to derive replacements from.
- [ ] `dev-docs/issues/synthetic_test_data_conversion.md` — the 2025 "Phase 3" conversion was never
      executed. 208 `np.random.rand()` instances remain across 27 test files. Triage before bulk
      converting; some are legitimately random.
- [ ] `dev-docs/issues/optim_dict_resume_conflict.md` — Optuna parameter space conflicts on resume.
      Deferred, workaround exists.
- [ ] Multi-user admin endpoints (`emuses/multi_user_service/admin_endpoints.py`) are mock
      implementations returning fake data. Documented in
      `docs/multi_user_service_implementation_gap_analysis.md`. Non-blocking for single-user use.

---
*Long-form history: `dev-docs/project-history/detailed-status-archive-2026-07-30.md`*
*Architecture rationale: `.codebase-memory/adr.md` | Static guidelines: `lad:lad-standards` skill*
