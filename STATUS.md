# STATUS — EMUSES
_Last touched: 2026-07-30_

## Goal
A predictive modelling tool for neuroimaging research, usable at three scales: local model
development by individual researchers, collaborative sharing within labs, and a public model
registry with peer review for the wider community.

## State of play

**Branch**: `fix/security-dependency-updates`, 13 commits ahead of `main`, not yet merged. Despite
the name it is a grab-bag: dependabot fixes, NIfTI affine correction, the workshop poster figure,
ADR tracking, and this session's LAD v2 migration.

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

**Test suite — collects cleanly, does not pass.** 2490 tests collect with 0 errors. A full run has
never completed: two directories hang indefinitely. Measured per directory on 2026-07-31:

| Directory | Time | Result |
|---|---|---|
| `multi-user-service` | **hangs** | killed at 300s |
| `enhanced-cli-typer` | **hangs** | killed at 300s; 6 files use `subprocess`, which `CLAUDE.md` forbids |
| `integration` | 129s | **dumped core** |
| `pipelines` | 41s | **dumped core** |
| `model_registry` | 96s | 73 failed, 621 passed |
| `observability` | 5s | 9 failed, 52 passed |
| `deployment` | 6s | 7 failed, 49 passed |
| `multi_user_service` | 3s | 4 failed, 4 passed, 7 errors |
| `analysis_api`, `cicd-pipeline` | <15s | 3 failed each |
| `security`, `unit`, `compliance` | <20s | 1 failed each |
| `tools`, `performance` | <13s | all pass |

**~102 known failures plus 7 errors**, all pre-existing. The remaining 14 directories finish in
under 20s each, so the suite is not inherently slow — two hanging directories are why it never ends.

Note `tests/multi-user-service/` and `tests/multi_user_service/` both exist, with different
contents. Probably unintended.

`python scripts/dev_test_runner.py` → 13/13 is the pre-push gate and is unaffected by any of this.

## Decided strategy

- **Models are atomic folders**, not separable components. The registry is a folder lookup service
  and nothing more. This was violated once and had to be reverted; see `.codebase-memory/adr.md` §2.1.
- **Test locally before pushing** — `dev_test_runner.py` on feature branches (13 tests, ~1 min),
  full CI reserved for `main` (~30 min). Deliberate, to conserve GitHub education credits.
- **Real data over synthetic** in tests. Converting InferenceStage tests from `np.random.rand()` to
  `test_data/` fixtures took that suite from 44% to 83% passing — the failures were the synthetic
  data, not the code. See `dev-docs/test_quality_conventions.md`.
- **Never hardcode absolute paths.** In-repo paths derive from `PROJECT_ROOT`; external datasets come
  from `EMUSES_TEST_DATA_ROOT`. A hardcoded Windows path had silently broken the session pipeline
  fixture for months.
- **Documentation split**: `docs/` is user-facing, `dev-docs/` is for contributors and sessions.

## Open questions / next

- [ ] Run `/lad:converge` — nine months of accumulated claims have not been checked against the
      code. Two were already found and fixed on 2026-07-30 (a stale "ready for merge" banner, and
      `CLAUDE.md` naming a deleted branch as current); the rest of the sweep has not been done.
- [ ] Decide what to do with `fix/security-dependency-updates` — merge to `main` or split the
      unrelated work out. It is carrying five distinct concerns.
- [ ] Test suite triage — full findings in `dev-docs/issues/test_suite_triage_2026_07.md`.
      One of the two hangs is fixed; the environment was missing 47 pinned packages and now is not.
      Remaining: the `tests/multi-user-service/` directory-level hang, and 36 `model_registry`
      failures whose fixtures encode the pre-ADR-§2.1 component model (the code is right, the tests
      are obsolete — do not "fix" the code to accept them).
- [ ] `dev-docs/issues/synthetic_test_data_conversion.md` — the 2025 "Phase 3" conversion was never
      executed. 208 `np.random.rand()` instances remain across 27 test files. Triage before bulk
      converting; some are legitimately random.
- [ ] `dev-docs/issues/optim_dict_resume_conflict.md` — Optuna parameter space conflicts on resume.
      Deferred, workaround exists.
- [ ] Multi-user admin endpoints (`emuses/multi_user_service/admin_endpoints.py`) are mock
      implementations returning fake data. Documented in
      `docs/multi_user_service_implementation_gap_analysis.md`. Non-blocking for single-user use.
- [ ] Delete or keep `test_name_logic.py` at the repo root — a print-only demo with no assertions.

---
*Long-form history: `dev-docs/project-history/detailed-status-archive-2026-07-30.md`*
*Architecture rationale: `.codebase-memory/adr.md` | Static guidelines: `lad:lad-standards` skill*
