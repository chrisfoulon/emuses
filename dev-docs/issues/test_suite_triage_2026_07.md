# Test suite triage — 2026-07-31

Diagnostic pass over the test suite. Measured, not estimated. Nothing here was fixed by
guesswork or by weakening an assertion.

**Environment matters for reproducing any of this**: `conda activate emuses`. The env had drifted
badly from `requirements-dev.txt` — 47 packages the lockfile pins were simply absent. They are now
installed. Before that, a large share of "failures" were missing imports rather than defects.

## Fixed in this pass

**`test_circuit_breaker_opens_on_failures` no longer hangs.** It patched `client._session` before
`async with client`; `__aenter__` → `_ensure_session()` replaces the session when it is `None` or
`is_closed`, and a MagicMock's `.is_closed` is a truthy Mock — so the double was discarded, a real
`httpx.AsyncClient` was created, and requests to a dead `localhost:8000` looped through exponential
backoff forever. It also patched `.get` when `client.get()` delegates to `_session.request`. Fixed
by adopting the pattern the next test in the same file already used.
`tests/enhanced-cli-typer/test_service_client.py`: never terminated → 84s, 2 failed, 35 passed.

**47 missing packages installed** (`redis`, `hvac`, `google-cloud-storage`, `azure-storage-blob`,
`docker`, `authlib`, `testcontainers`, `pytest-cov`, `coverage`, `moto`, …). In `model_registry`
alone this took 74 failed / 620 passed → 65 failed / 645 passed, and cleared
`test_model_cache.py` entirely (12 failures, all `redis` absent).

## Open — needs real work

### 1. `tests/multi-user-service/` hangs as a directory (P2)

Every one of its 18 files passes or fails in ≤3s alone. Run together, the directory exceeds 900s,
stalling on `test_deployment_mode_integration.py` — which by itself finishes in 0.84s.

- No single pair reproduces it; a 9-file cumulative prefix does (>300s). So it is cumulative state,
  not one bad neighbour.
- Suspect, **unproven**: `test_deployment_mode_integration.py:90` sets `EMUSES_DATABASE_URL` to
  `postgresql://test:test@localhost/test`, a database that is not running, and the file builds
  `TestClient(app)`. Combined with engine/pool state left by earlier files, that could block.
- Next step: bisect the 9-file prefix further, then instrument with `faulthandler` to get the stack
  at the point of stall.

### 2. The 36× `assert 'error' == 'success'` cluster is obsolete tests, not broken code (P2)

36 of the 65 remaining `model_registry` failures share one assertion. `install_model()` returns
`{"status": "error"}` with `Invalid EMUSES folder: Not a complete EMUSES training folder`.

**The code is right and the tests are wrong.** ADR §2.1 (`.codebase-memory/adr.md`) states that a
complete EMUSES model is an entire output folder — UMAP, HDBSCAN, prediction pipelines, scalers,
metadata, trained together — and that components are *not* separable. It records that this was
"previously violated by a CompleteEmusesModel class" and that "that violation has been corrected".

The fixtures (e.g. `sklearn_model_dir` in `test_local_registry_real.py`) build a bare sklearn
`Pipeline` directory — a component. Validation correctly rejects it.

**Do not make the code accept these folders.** That would re-introduce the violation the ADR
records as corrected. The fix is to rebuild the fixtures as complete EMUSES folders — and per
guardrail G009, derived from a real EMUSES output folder rather than invented, so the fixture
actually reflects what the pipeline produces.

Affected: `test_local_registry_real.py` (8), `test_simplified_installation.py` (7),
`test_enhanced_schema.py` (7), `test_storage_optimization.py` (5), `test_hash_indexing.py` (5),
`test_enhanced_metadata_storage.py` (5), `test_concurrent_access.py` (5), and others.

### 3. Slow-but-passing tests (P3)

Not broken, but they dominate runtime. `enhanced-cli-typer` alone:
`test_service_client.py` 84s, `test_performance_stress.py` 163s, `test_cli_integration.py` 51s,
`test_security_validation.py` 43s, `test_timeout_configuration.py` 39s.

Much of this is real retry/backoff delay being waited out. Injecting the backoff parameters, or
marking these `@pytest.mark.slow` and excluding them from the default run, would cut the suite
substantially. `pytest.ini` already declares a `slow` marker that nothing uses.

### 4. Leaked daemon monitor threads abort the interpreter (P1)

**One root cause behind at least four directories.** Confirmed by capturing the crash:

```
Fatal Python error: _enter_buffered_busy: could not acquire lock for
<_io.BufferedWriter name='<stderr>'> at interpreter shutdown,
possibly due to daemon threads
Exception in thread Thread-1 (_monitor)   [also Thread-2, -4, -6, -7]
```

**The tests pass first.** `tests/flexible-inference-stage/test_explicit_validation_flag.py` reports
`1 failed, 3 passed in 6.61s` and *then* the process aborts with exit code 134 (SIGABRT). So results
are correct but the exit status is a crash — which any CI system reads as failure. This is why
several directories reported "dumped core" while apparently having run fine.

Affected: `flexible-inference-stage` and `foundation_fastapi_service` abort outright; `cli` and
`inference` emit thread tracebacks (same leak, just fewer threads).

**Mechanism**: `ResourceMonitor.start_monitoring()` (`emuses/cli/rich_features.py:1142-1144`) starts
a `daemon=True` thread. The matching `stop_monitoring()` is called at line 1437 — inside
`stop_spinner`, **not in a `finally`**. Any path that starts a spinner with memory monitoring and
does not reach a clean stop leaks a thread that lives until interpreter shutdown, where it races
the finalizer for the stderr lock.

Tests make it worse but are not the whole story: `tests/foundation_fastapi_service/test_stage_runners.py`
calls `start_monitoring()` five times and `stop_monitoring()` once. But `flexible-inference-stage`
starts no monitors of its own — those come from production code paths, so this is a real leak in
the CLI, not only a test hygiene problem.

**Fix (production code, not a test change)**: guarantee the stop. Wrap the spinner lifecycle in
`try/finally`, and have `stop_monitoring()` `join()` the thread with a timeout rather than relying
on daemon semantics. An autouse conftest fixture that stops lingering monitors between tests would
contain the blast radius but would be papering over a genuine CLI defect.

Ranked P1 rather than P2 because it exits the process abnormally, and because a leaked monitor
thread in the real CLI is a defect users could hit, not merely a test artefact.

### 5. Two multi-user test directories (P4)

`tests/multi-user-service/` and `tests/multi_user_service/` both exist with different contents.
Probably unintended.

### 6. `subprocess` use inside tests (P3)

Six files under `tests/enhanced-cli-typer/` invoke `subprocess`. `CLAUDE.md` states: "Never run
`subprocess.run(["pytest", ...])` from within test files." Worth auditing which of those spawn
pytest specifically, since that both slows runs and escapes `pytest-timeout`.

## Measured failure counts (post-dependency-install)

| Area | Result |
|---|---|
| `model_registry` | 65 failed, 645 passed, 7 skipped, 3 errors — 36 are the ADR cluster above |
| `multi-user-service` | 52 failed across 5 files; directory hangs |
| `enhanced-cli-typer` | ~11 failed; no longer hangs |
| `observability` | 9 failed, 52 passed |
| `deployment` | 7 failed, 49 passed |
| `analysis_api`, `cicd-pipeline` | 3 failed each |
| `security`, `unit`, `compliance` | 1 failed each |
| `tools`, `performance` | all pass |

Counts for areas other than `model_registry` predate the dependency install and will be lower now.
Re-measure before acting on them.
