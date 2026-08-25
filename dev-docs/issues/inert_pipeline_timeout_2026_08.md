# The service's pipeline timeout cannot fire (OPEN)

_Found 2026-08-25 while auditing the parallelism backend. Not fixed — the fix is entangled with a
concurrency change that deserves its own decision._

## Symptom

`PipelineRunner.pipeline_timeout` (default 1800 s) has no effect. A pipeline that hangs hangs
forever, and the job stays `running` rather than being failed with
`"Pipeline execution timeout after N seconds"`.

## Cause

`execute_pipeline` wraps the run in a timeout:

```python
result = await asyncio.wait_for(
    self._execute_pipeline_stages(context_copy, progress_callback),
    timeout=self.pipeline_timeout,
)
```

`asyncio.wait_for` schedules the timeout on the event loop and fires it when the loop next gets
control. But `_execute_pipeline_stages` is an `async def` that calls `_run_pipeline_in_process`
**synchronously** — no `await`, no `run_in_executor`. That call blocks the loop for the entire run,
so the loop never regains control, and the timeout callback cannot run until the thing it is timing
has already finished.

The timeout is not merely late. It can only fire after the work completes, which is exactly when it
is worthless.

## Blast radius beyond the timeout

The same blocking call is why jobs never overlap, even though `app.py` dispatches them with
`asyncio.create_task` and several can be in flight. That accidental serialisation was, until
2026-08-25, the only thing preventing overlapping runs from clobbering each other's parallelism
backend — see ADR §2.9e. That specific dependency is now removed (the override is a `ContextVar`),
but it is worth knowing that "this call blocks the loop" is load-bearing in more than one place
before changing it.

Also affected while the loop is blocked: health endpoints, job-status polling, and progress
callbacks for other jobs.

## The timeout is not the only inert control (added 2026-08-25)

Checking what a fix would have to preserve turned up that the service's whole resource-governance
layer is decorative. None of this is enforced anywhere in the live path:

| control | status |
|---|---|
| `pipeline_timeout` (1800 s) | cannot fire — see above |
| `memory_limit_ratio` (0.75) | passed into `_run_pipeline_in_process(context, memory_limit_ratio)` and **never read in the body** |
| `cpu_percent_limit` (90 %) | exists only in `ResourceMonitor`, which lives in the dead `stage_runners.py` |
| `max_workers` (4), `self.executor` | assigned in `__init__` and never used |
| concurrent job admission | **nothing** — no semaphore, no queue bound, no max-concurrent check |

The module docstring advertises "ProcessPoolExecutor for background execution and resource
isolation". There is no executor.

**These are two pieces of work, not one.** The memory and CPU limits are a *researcher's* control —
they matter with a single pipeline on a single machine and are not blocked on anything here. They
have their own write-up: `memory_aware_execution_2026_08.md`. This document covers only the
*operator's* controls: the timeout, job admission, and `max_workers`, all of which only mean
something once someone other than the person who started a run has to clean up after it.

This matters for sequencing: fixing only the timeout moves the service from *no limits but
accidentally serial* to *no limits and genuinely concurrent*, which is strictly worse. The
serialisation is currently doing the job the resource limits are not.

Separately, `multi_user_service/background_tasks.py:737` constructs
`PipelineRunner(input_dir=..., output_dir=...)` and calls `.execute(config)`. The signature is
`(job_manager, max_workers=4, memory_limit_ratio=0.75, pipeline_timeout=1800)` and there is no `execute`
method, so that call raises `TypeError` before doing anything. It is not a working consumer to
design around.

## The trap in "just add a timeout"

A timeout that *reports* is not a timeout that *stops*. `asyncio.wait_for` cancelling a
`run_in_executor` future does not kill the work: `ThreadPoolExecutor` cannot cancel a function that
has already started, so the pipeline keeps running, keeps holding memory, and keeps writing to the
output folder while the job is marked `failed`. That is arguably worse than the current hang,
because the operator now believes the work has stopped.

Actually stopping a runaway pipeline requires running it in a **separate process** that can be
terminated — which reopens the serialisation complexity the existing TODO defers, and is why this is
a design decision rather than a patch.

## What mitigates it today

`--service-timeout` exists (`pipeline_options.py:260`) but defaults to `0.0`, which maps to
`timeout = None`, i.e. unlimited (`main.py:784`). `poll_job_until_completion` has a working 300 s
client-side default. So a user can bound their own wait and Ctrl-C out; the server-side work carries
on regardless. The leak is server-side only.

In the dominant local case this is close to harmless: the CLI auto-starts a service per invocation
(ADR §4), so it is one client to one service and there is nothing to be concurrent with. The problem
is real only for the shared lab/community deployments, which do not exist yet.

## Fix, when someone takes it

Move `_run_pipeline_in_process` onto an executor:

```python
result_context = await loop.run_in_executor(executor, self._run_pipeline_in_process, ...)
```

`stage_runners.py:194` already shows the pattern (`ThreadPoolExecutor(max_workers=1)` plus
`asyncio.wait_for` on the future) — though note that module is **dead code**, referenced only by its
own tests and `tests/test_architecture_boundary.py`, so it is a pattern to copy, not a path to
revive.

Doing this makes concurrent jobs genuinely concurrent, which is a real behaviour change and not just
a bug fix: `--n_jobs` is currently sized against a machine running one pipeline, and nothing bounds
how many jobs may be accepted at once. So the timeout fix has to be taken together with a decision
about how many pipelines the service may run simultaneously.

### Option A — stay serial, but say so (recommended)

Add explicit admission control (`asyncio.Semaphore(1)`, or a queue) so single-file execution is a
decision rather than a side effect, *then* move the call to an executor so the timeout can fire.
Behaviour is unchanged; what changes is that it is now stated and testable. Smallest change that
makes the timeout real, and it does not promise concurrency the resource layer cannot support.

Note this still only gets a timeout that *reports*, unless the pipeline is moved to a killable
subprocess. Decide explicitly which of the two is wanted: marking a hung job failed is useful for the
client even if the work continues, but it must not be described as cancelling the run.

### Option B — bounded concurrency

`Semaphore(N)`, `--n_jobs` sized as roughly `total_cores // N`, and the memory and CPU limits made
real rather than accepted-and-ignored. Substantially more work, and it only pays for itself on a
shared server, which is not a context that exists yet.

### Option C — defer

Leave it. Cost: a hung pipeline holds the service forever and the only recovery is killing the
process. Acceptable while the local one-client-one-service case dominates; not acceptable once a lab
shares one.

Whichever is chosen, the inert knobs (`max_workers`, `memory_limit_ratio`, `cpu_percent_limit`)
should be deleted or wired up. Leaving them reads as a guarantee that is not there — the module
docstring already claims resource isolation the code does not do.

## Verifying a fix

A passing test must show the timeout firing *while the pipeline is still running*, not after it
returns. Set `pipeline_timeout` to something small, submit a job whose stage sleeps well past it,
and assert both that the job reaches `failed` with the timeout message and that it does so before
the stage would have finished. Asserting only the final status would pass against the current
broken code if the stage happens to be slower than the timeout.
