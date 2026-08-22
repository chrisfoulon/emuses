# Phase 0 — does the CLI still run? (measured 2026-08-22)

Answer: **`emuses full` works. `emuses umap` and `emuses heatmap` are broken.**

This closes the open question from the plan: after many changes, it was not known whether the tool
still completed from the command line. It does, on the path that matters. The two stage-level
commands do not, for reasons that are fully diagnosed below.

Everything here was run from the CLI against `test_data/` (50 samples, 8 features), not through the
session test fixture. That distinction is the whole point of this phase: the fixture drives the
Python API, while the CLI goes out through HTTP to a FastAPI service, and only the second path was
in question.

## Results

| Command | Exit | Outcome |
|---|---|---|
| `full` (single target) | 0 | ~26 s. Output validates: `is_complete_model=True`, no missing components, no validation errors. |
| `full` (multi target) | 0 | `target_0/` + `target_1/`, validates clean, "Contains: 2 prediction targets". |
| `inference` | 0 | 50 samples in 3.53 s, 3 CSVs written. |
| `umap` | **1** | `400 Bad Request` on `POST /api/v1/jobs/pipeline/full`. |
| `heatmap` | **1** | Same failure, same URL. |

Invocation used for `full`:

```
python -m emuses.cli full <out> test_data/features.csv \
  --scores test_data/regression_scores.csv --columns_are_features \
  --umap_trials 3 --hdbscan_trials 2 --optuna_trials 3 --service-timeout 900
```

`--service-timeout` defaults to `0.0`, meaning **unlimited**. That default is what allows a stalled
run to sit for days rather than failing. Set it explicitly until that is reconsidered.

## Why `umap` and `heatmap` fail

Three independent defects compound. Any one of them alone would break these commands.

**1. The commands take no options at all.** `umap` and `heatmap` are declared with two positional
arguments and nothing else (`emuses/cli/main.py:1861`, `:1901`) — no `--scores`, no
`--columns_are_features`, no seed, no trial counts. `full` has roughly forty. So even reaching a
working endpoint, they could not describe the job.

**2. The pipeline type is discarded on the fallback path.** `_umap_async` (`main.py:1633`) first
tries `_execute_via_remote_service("umap", ...)`; when that fails it falls back to
`_execute_via_unified_service`, which recovers the pipeline type with
`config.get("command", "full")` (`main.py:1405`). Nothing ever sets `"command"` in a config built by
`_convert_typer_args_to_service_config` (`main.py:1131`) — it only copies the Typer kwargs, and
`command` is not one of them. The only assignment of that key is `main.py:1846`, on a different code
path these two commands do not use. So `"umap"` silently becomes `"full"`, and the run is submitted
as a full pipeline. `full` requires scores (`app.py:1102`, `"scores is required (unless using
special datasets like 'mnist')"`) — hence the 400.

**3. The stage URL the client builds does not exist on the server.** Even with the type preserved,
`submit_pipeline_job` constructs `/api/{version}/jobs/pipeline/{pipeline_type}`
(`service_client.py:746`), and `_validate_pipeline_type` (`service_client.py:~660`) happily accepts
`"umap"`, `"clustering"`, `"heatmap"`, `"prediction"`. But the service defines only two job routes:
`/api/v1/jobs/pipeline/full` (`app.py:1039`) and `/api/v1/jobs/pipeline/stage/{stage_name}`
(`app.py:1157`). `/jobs/pipeline/umap` is a 404. The client validates against a set of types the
server never exposed at that path.

Phase 1 (in-process local execution) removes defects 2 and 3 by removing the HTTP hop entirely.
Defect 1 is separate and needs the option lists filled in regardless.

## Leaked service process — found in the act

A **pytest process from 2026-08-19 was still alive**, 3.1 days old, listening on `127.0.0.1:8000`
and answering HTTP:

```
PID 755279  started Wed Aug 19 17:16:28  reparented to systemd (orphan)
cwd: /tmp/pytest-of-chrisfoulon/pytest-28/test_concurrent_job_submission0 (deleted)
GET http://127.0.0.1:8000/api/health -> 500 Internal Server Error
```

This matters beyond tidiness. `_execute_via_remote_service` defaults to
`service_url="http://localhost:8000"` (`main.py:1173`), so **every CLI invocation on this machine
talks to that stale test process first**. Today it returned 500, so the CLI fell through to
auto-starting its own service on 8001. Had it returned 200, a real job would have been submitted
into a test fixture's service.

Two consequences to record:

- **`pgrep -af uvicorn` does not detect these leaks.** The service is a fork of the CLI process, so
  its argv still reads `python -m emuses.cli full`. The plan's step 3 as originally written would
  have reported "clean" with this orphan running. Check listening sockets instead:
  `ss -ltnp | awk '$4 ~ /:80[0-9][0-9]$/'`.
- The leak originates in `test_concurrent_job_submission`, which is a concrete place to look rather
  than the general "six-day hang" mystery.

The run under test cleaned up after itself correctly — port 8001 was released — though the log shows
`Service didn't stop gracefully, forcing kill...`, i.e. SIGTERM was ignored and SIGKILL was needed.

## Two things noticed, not yet chased

- **Constant per-fold predictions.** In the inference output, folds 1, 3 and 4 each predict a single
  value for all 50 samples (`nunique=1`); only folds 0 and 2 vary. The ensemble does vary, so the old
  "all predictions identical" bug has not returned. Most likely degenerate fits from the deliberately
  tiny 3-trial budget used here — but it should be re-checked at a realistic budget before being
  dismissed.
- **UMAP is already deterministic.** The runs emit
  `n_jobs value 1 overridden to 1 by setting random_state. Use no seed for parallelism.` UMAP forces
  single-threaded execution whenever a seed is set, so it is not a source of run-to-run variation.
  That leaves HDBSCAN's `core_dist_n_jobs=-1` as the remaining suspect for Phase 2, which narrows
  that measurement usefully.

## Disk

Root filesystem 90% full, 3.9G free. One `full` run plus its inference costs ~69 MB, so Phase 2's
three runs fit — but the margin is small enough to check before starting rather than during.

---

# Phase 1A — the dropped CLI options (fixed 2026-08-22)

Found while checking whether the planned Phase 1 would actually fix the `umap`/`heatmap` breakage.
It would not have, and this is the larger problem: **options accepted by `emuses full` that never
reached the pipeline at all**.

Every option travels CLI -> `_convert_typer_args_to_service_config` -> `_context_to_emuses_args`
(`pipeline_runner.py:54–208`) -> `PipelineConfig` -> stages. The middle step assigns args by hand,
one line each. An option nobody remembered to add there is not an error — it is silently discarded,
and the run falls back to the `PipelineConfig` dataclass default. No warning is printed. The run
looks successful and computes something other than what was asked for, which is the worst failure
mode available to a scientific tool.

## Correction to the initial count

The first pass reported nine dropped scientific options. That was the count of *unmapped* options,
not of *broken* ones. Checking each for an actual consumer changes the picture: **four were live and
are now fixed; five are dead flags that nothing anywhere reads.** Mapping the dead five would have
achieved nothing while looking like a fix.

**Fixed — accepted, dropped, and genuinely consumed:**

| Option | Consumer | Was silently using |
|---|---|---|
| `--hdbscan_core_dist_n_jobs` | `umap_stage.py:112` | `-1` (all cores) |
| `--hdbscan_approx_min_span_tree` | `umap_stage.py:110` | `True` |
| `--input_file_list` | `emuses_pipeline.py:265` | `False` |
| `--recursive-input-file-search` | `emuses_pipeline.py:327` | `False` |

The last one is a name mismatch rather than an omission. The flag is spelled
`--recursive-input-file-search`, Typer binds it to the Python parameter `recursive_search`, so it
arrives under that key — but the only consumer reads `recursive_input_file_search`. `PipelineConfig`
declares *both* names (`:80` and `:97`), which is how the two drifted apart. The mapping now accepts
either key and feeds the live attribute.

**Not fixed — CLI accepts them, nothing reads them:** `--min_cluster_size`, `--model_selection`,
`--use_enhanced_pipeline`, `--parallel_models`, `--inspect_data_state`. These need an implementation
or removal from the CLI, which is a product decision. They are listed as `NOT_IMPLEMENTED` in the
test so they stay visible rather than blending in.

`--min_cluster_size` is the clearest of the five: HDBSCAN's `min_cluster_size` is chosen by Optuna
over `[5, 50]` (`UMAP_utils.py:73`), so a user-supplied fixed value is overwritten by the search. The
flag cannot work as written without deciding what "fix this parameter" should mean for the
optimisation.

**Correctly not mapped** (transport and display, not computation): `--service`, `--service-url`,
`--token`, `--interactive`, `--service-timeout`, `--umap-timeout`, `--heatmap-timeout`,
`--prediction-timeout`.

## Evidence

The config snapshot `PipelineConfig` writes to `<output>/log/arguments_*.json` settles it. From the
Phase 0 run, before the fix:

```
hdbscan_core_dist_n_jobs:     <ABSENT>
hdbscan_approx_min_span_tree: <ABSENT>
input_file_list:              <ABSENT>
recursive_input_file_search:  False
```

Absent entirely — the attributes never existed on the config, so `getattr(self.config, ...)` in
`umap_stage.py` took its hardcoded fallback. After the fix, running with
`--hdbscan_core_dist_n_jobs 1 --recursive-input-file-search`:

```
hdbscan_core_dist_n_jobs:     1
hdbscan_approx_min_span_tree: True
input_file_list:              False
recursive_input_file_search:  True
clustering_params: {'hdbscan_approx_min_span_tree': True, 'hdbscan_core_dist_n_jobs': 1}
```

`clustering_params` is the dict `umap_stage.py` actually consumes, so the value now reaches HDBSCAN.
The run completes (exit 0) and the output still validates as a complete model.

## Guard

`tests/test_cli_option_mapping.py` derives the `full` signature via `inspect.signature` and the
assigned args via AST, then asserts the difference is exactly the two declared exception lists. The
cause was two independently-maintained lists; without a check that relates them, the next option
added to the CLI is dropped the same way.

It also pins the four fixed options individually — a general count can be satisfied by widening an
exception list — and verifies each named consumer still references the attribute, so an option
mapped into a config nobody reads any more is caught too. `test_the_checker_has_teeth` confirms the
rule fails on a simulated drop, so a broken AST walk cannot make the suite silently vacuous.

## What this means for Phase 2

Phase 2 planned to measure run-to-run variation crossed with `--hdbscan_core_dist_n_jobs` at 1 vs -1.
Before this fix both arms would have run at `-1`, and the measurement would have shown no difference
— correctly, and completely misleadingly. That phase is now unblocked.
