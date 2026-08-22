# Parallelism handling: what is actually happening, and what to do about it

_Analysed 2026-08-22, ahead of Phase 1B (in-process local execution)._

The question was whether the parallelism handling is two sessions' solutions clashing. Partly. The
git history cannot confirm it — all three of the relevant lines landed in one squashed commit
(`9482192`, 2025-07-28, misleadingly titled "complete API documentation recovery"). But the code
contains **two independent mechanisms for the same decision, one of which has never worked**, plus a
hard override that papers over the broken one. That is the fingerprint of layered fixes regardless of
who wrote them.

The important finding is not the untidiness. It is that **Phase 1B would silently switch on
parallelism that is currently disabled**, which changes results.

## The intended design

`emuses/tools/parallelism_utils.py` chooses joblib settings by context:

- **backend**: `loky` (process-based) in the main process, `threading` in a subprocess
- **n_jobs**: clamped to `1` in a subprocess

The rationale is sound. Spawning loky worker processes from inside an already-forked process is a
known source of hangs and resource exhaustion.

## Fault 1 — the backend detector has never worked

```python
def get_process_hierarchy_depth():
    current = mp.current_process()
    depth = 0
    while hasattr(current, "parent") and current.parent is not None:
        ...
```

`multiprocessing.Process` objects have no `parent` attribute. `hasattr` is always `False`, the loop
body never executes, and the function **always returns 0**. Therefore `get_safe_parallel_backend()`
always returns `loky`, including in the subprocess case it exists to catch.

Measured:

```
[main]          name='MainProcess' has_parent_attr=False depth=0 is_subproc=False backend=loky n_jobs(-1)->-1
[forked-child]  name='Process-1'   has_parent_attr=False depth=0 is_subproc=True  backend=loky n_jobs(-1)->1
```

The child is correctly identified as a subprocess by one check and not by the other.

## Fault 2 — there are two detectors and only one works

`get_safe_n_jobs()` uses `is_subprocess_context()`, which compares
`mp.current_process().name != "MainProcess"`. That is valid and does work. So half the mechanism
functions (n_jobs clamps correctly) while the other half is dead (backend selection). Two
implementations of one concept, silently disagreeing.

## Fault 3 — a hard override hides fault 1

`PipelineRunner._run_pipeline_in_process` sets:

```python
# Service workers run in subprocess context - use threading backend
configure_parallelism_backend(force_backend="threading")
```

unconditionally. This is what actually delivers the threading backend in the service today; the
auto-detection would have said `loky`. The override produces the right answer for the wrong reason,
which is why the underlying bug survived.

Its comment also stops being true the moment execution moves in-process, which is exactly what
Phase 1B does.

## Fault 4 — process-wide mutable global, never restored

`_force_backend` is a module-level global. Production code writes it and nothing ever puts it back,
so the setting outlives whatever set it and leaks into everything sharing the interpreter.

Measured, and reproducible:

```
pytest tests/tools/test_parallelism_utils.py                    -> 13 passed
pytest <one pipeline test> tests/tools/test_parallelism_utils.py -> 1 failed, 13 passed
```

The failure is `test_enhanced_backend_selection_by_depth`, and its cause is that a pipeline test ran
first and left `_force_backend = "threading"` behind. A test failing because of an unrelated test's
side effect is the kind of thing that gets marked flaky and ignored.

## Fault 5 — the test for the broken function cannot detect the break

`test_enhanced_backend_selection_by_depth` mocks `get_process_hierarchy_depth` and asserts how
`get_safe_parallel_backend` branches on its return value. It never calls the real function, so it
passes regardless of the fact that it always returns 0. It validates the consumer while the producer
is dead — full green, zero coverage of the actual defect.

## The consequence that matters: `--n_jobs` is currently inert

Follow it through. `emuses full` starts a FastAPI service as a `multiprocessing.Process`; uvicorn and
the whole pipeline run inside that child; in the child `mp.current_process().name` is `Process-N`, so
`is_subprocess_context()` is `True`, so **every `get_safe_n_jobs()` call clamps n_jobs to 1**.

That covers all the joblib parallelism in the science path: `heatmap_stage.py:385`,
`optim_utils.py:792`, `stats_utils.py:169` and `:1909`, `models_utils.py:177`, `optuna_cv.py:35`
and `:132`.

**So every CLI pipeline run is effectively serial for joblib work today, whatever `--n_jobs` says.**
That is a performance loss, and it means `--n_jobs` joins the list of flags that do not do what they
claim.

Now the Phase 1B consequence: running in-process puts the pipeline back in `MainProcess`,
`is_subprocess_context()` becomes `False`, and n_jobs becomes `-1`. Parallelism switches on for the
first time. Runs get faster, and floating-point reduction order changes, so **numbers can move**.
Doing this immediately before taking a reproducibility baseline would contaminate the baseline with a
change of our own making, and we would have no way to tell later which difference came from where.

## Recommended solutions

| # | Change | Complexity | Risk | Phase |
|---|---|---|---|---|
| A | Fix the detector: delete `get_process_hierarchy_depth`, use `is_subprocess_context()` | **Low** — ~10 lines, plus rewriting the test that mocks it | Low; makes auto-detection agree with what the override already forces | **1B** |
| B | Drop the hard `force_backend="threading"` from `pipeline_runner` once A works | **Low** — delete 3 lines | Low, but only after A | **1B** |
| C | Replace the global with a scoped context manager | **Medium** — ~8 call sites | Low; removes cross-test pollution at the source | **1B** |
| D | Decide the n_jobs policy deliberately, and warn when clamping overrides a user value | **Medium** | **Changes results** | **2** |
| E | Autouse fixture restoring `_force_backend` between tests | Low | None | **done** |

### Why each sits where it does

**A and B belong in Phase 1B, before the move.** Phase 1B changes which branch of this logic runs, so
the logic must be correct and legible first. Fixing them afterwards means debugging a behaviour change
on top of a known-broken detector.

**C belongs with them** — it is the same code, and a global that production mutates is what made the
test failure order-dependent. A context manager (`with parallelism_backend("threading"): ...`) scopes
the override to the work it applies to.

**D belongs in Phase 2, not 1B.** The n_jobs flip is a scientific change, not plumbing. Phase 2 already
plans to measure run-to-run variation; add `n_jobs` at 1 vs -1 as a second arm alongside
`hdbscan_core_dist_n_jobs`. Then the tolerance in Phase 3 cites a measurement rather than a guess.

### Recommendation for Phase 1B specifically

Make Phase 1B **behaviour-preserving on purpose**: after moving in-process, set the clamp explicitly
so joblib still sees `n_jobs=1`, and record why in a comment. That keeps the Phase 2 baseline clean —
one variable at a time. Then let Phase 2 measure the flip and Phase 3 pin whichever is chosen.

The alternative — flipping to real parallelism in 1B because it is obviously faster — is tempting and
wrong. It would improve runtime and move the numbers in the same commit, leaving no way to attribute
a later discrepancy.

## Also worth fixing while here

- `optim_utils.py:792` and `stats_utils.py:1907` call `get_safe_n_jobs()` and then pass the result to
  `create_safe_parallel()`, which calls it again. Idempotent, so harmless, but it suggests neither
  caller was sure what the helper does.
- The comment at `pipeline_runner.py:426` ("Service workers run in subprocess context") becomes false
  under Phase 1B and should not survive the move unedited.
