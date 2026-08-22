# STATUS — EMUSES
_Last touched: 2026-08-22_

## Goal
A predictive modelling tool for neuroimaging research, usable at three scales: local model
development by individual researchers, collaborative sharing within labs, and a public model
registry with peer review for the wider community.

## State of play

**Current work: `chore/core-boundary`, 8 commits ahead of `main`, no upstream configured — never
pushed, so it exists only on this machine.** Driving toward a tool that can be trusted to run and to
publish from; plan at `~/.claude/plans/playful-watching-naur.md`, findings in
`dev-docs/issues/phase0_cli_runnability_2026_08.md`.

**`emuses full` runs (verified 2026-08-22).** ~26 s on `test_data/`, single- and multi-target, output
validates via `ModelIOManager.validate_model()`. `inference` works. This was genuinely open: the
session test fixture drives the *Python API*, while the CLI goes out over HTTP to an auto-started
FastAPI service, and only the first had ever been checked.

**`emuses umap` and `emuses heatmap` do not run.** Three compounding defects: they declare no options
at all (`main.py:1861`, `:1901`); the fallback recovers the pipeline type via
`config.get("command", "full")` (`main.py:1405`) but nothing sets `"command"`, so `umap` becomes
`full` and is rejected for having no scores; and the client builds `/api/v1/jobs/pipeline/umap`
(`service_client.py:746`), which the server does not define. Fixing this is Phase 1B/1C.

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

**Test suite — collects cleanly, does not pass, but no longer crashes.** 2499 tests collect with 0
errors. Repaired since 2026-07-31:

- **No more core dumps.** All three were one root cause: `PipelineConfig.__post_init__` built a new
  `logging.handlers.QueueListener` on every instantiation, so listener threads accumulated and raced
  for stderr at shutdown, aborting the process (exit 134) *after* tests had already passed. Fixed by
  a module-level singleton, plus a `multiprocessing.util.Finalize` that stops the listener before
  the queue's pipe closes — `conftest.py` patches `atexit.register` autouse, which had been silently
  swallowing the shutdown registration.
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
- [ ] **Phase 1B — restore in-process local execution.** ADR §4 defines local mode as "CLI,
      file-based storage, in-process execution", but `_full_async` (`main.py:1107`) always forks a
      FastAPI service and submits over HTTP. Reuse `PipelineRunner._run_pipeline_in_process`. Two
      things to decide rather than drift into: keep the endpoint's path validation on the local path,
      and pick a parallelism backend deliberately — the CLI sets loky (`main.py:1044`) and the runner
      then forces threading (`pipeline_runner.py:391`); keep threading initially so results match
      today's, since Phase 2's baseline depends on it.
- [ ] Phase 1C — give `umap`/`heatmap` a real option set, sharing one declaration with `full`.
- [ ] Phase 2 — measure run-to-run variation, then state a tolerance. Unblocked by 1A: both arms
      would previously have run at `core_dist_n_jobs=-1`. UMAP is already deterministic when seeded
      (it forces single-threaded), so HDBSCAN is the remaining suspect.
- [ ] Phase 3 — numerical regression suite. Phase 4 — the ~33 science-path test failures.
      Phase 5 — finish the extras move.

**A stale service process holds port 8000.** A pytest run from 2026-08-19 (PID 755279, orphaned to
systemd, cwd `/tmp/pytest-of-chrisfoulon/pytest-28/test_concurrent_job_submission0`, deleted) is
still listening and answering HTTP with 500. `_execute_via_remote_service` defaults to
`localhost:8000` (`main.py:1173`), so every CLI run contacts it first; had it answered 200, a real
job would have gone into a test fixture's service. `kill 755279` clears it;
`test_concurrent_job_submission` is where the leak comes from. Note **`pgrep -af uvicorn` does not
detect these** — the service is a fork of the CLI process, so its argv still reads
`python -m emuses.cli full`. Use `ss -ltnp | awk '$4 ~ /:80[0-9][0-9]$/'`.

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
