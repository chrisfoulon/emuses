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
a bug fix:

- resource limits (`memory_limit_ratio`, `cpu_percent_limit`) are currently computed per run with
  one run assumed;
- `--n_jobs` is currently sized against a machine running one pipeline;
- nothing bounds how many jobs may be accepted at once.

So the timeout fix should be taken together with a decision about how many pipelines the service is
allowed to run simultaneously. That is why it was not done as a drive-by.

## Verifying a fix

A passing test must show the timeout firing *while the pipeline is still running*, not after it
returns. Set `pipeline_timeout` to something small, submit a job whose stage sleeps well past it,
and assert both that the job reaches `failed` with the timeout message and that it does so before
the stage would have finished. Asserting only the final status would pass against the current
broken code if the stage happens to be slower than the timeout.
