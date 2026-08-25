# Memory-aware execution: a user-facing control that does not exist (OPEN)

_Split out from `inert_pipeline_timeout_2026_08.md` on 2026-08-25. Those findings were recorded
together because they were found together, but they are separate pieces of work with different
owners, different blockers, and different priorities._

## The distinction that matters

`PipelineRunner` advertises `memory_limit_ratio` and `cpu_percent_limit` alongside
`pipeline_timeout`, which makes them look like one "service governance" feature. They are not:

- **Memory and CPU limits are a researcher's control.** They matter with a single pipeline on a
  single laptop or a shared workstation — "do not take the whole machine, I am also using it". They
  have nothing to do with how many jobs the service accepts.
- **The timeout is an operator's control.** It only means something when someone other than the
  person who started the run has to clean up after it, i.e. a shared deployment.

Only the second is blocked on the concurrency decision in
`inert_pipeline_timeout_2026_08.md`. This one is not blocked on anything.

## Where each actually stands

**CPU: largely already covered, by `--n_jobs`.** It is a real, documented option
(`pipeline_options.py:253`), and since the service became its own process (2026-08-24) it is no
longer silently clamped to 1 — measured at CPU 124 % → 161 % between `--n_jobs 1` and `4`
(`njobs_arm_b_2026_08.md`). The default is `-1`, meaning take every core. What
`cpu_percent_limit` would add on top is a ceiling enforced regardless of what `n_jobs` asked for,
which is marginal next to just setting `--n_jobs`. The more useful change here is arguably the
**default**: `-1` is a poor default for a tool people run on their own laptop while doing other
things.

**Memory: entirely absent.** Nothing in `emuses/pipelines/` or `emuses/tools/` imports `psutil`,
reads `virtual_memory()`, or bounds allocation in any way (verified 2026-08-25). The only
`ResourceMonitor` in the tree lives in `stage_runners.py`, which is dead code — referenced by its
own tests and `tests/test_architecture_boundary.py`, nothing else. `memory_limit_ratio` is passed
into `_run_pipeline_in_process` and never read.

So a run that does not fit in RAM does not get a clear error. It gets whatever the OS does — swap
thrash, or the OOM killer terminating the process, which on the CLI path looks like the service
dying for no stated reason.

## What "useful" looks like here

Worth deciding deliberately, because the obvious reading ("kill the run at 75 % of RAM") is the
least useful version:

1. **Refuse early with a real number.** Estimate the requirement from dataset shape and stage
   configuration, compare against available memory, and fail before starting with "this needs
   ~N GB, you have M". Most valuable and least invasive: no monitoring, no killing, no async
   changes. Requires knowing the pipeline's actual footprint, which nobody has measured.
2. **Size the work to fit.** Derive an `n_jobs` ceiling from available memory rather than core
   count, since each parallel worker multiplies the footprint. Connects directly to the existing
   `--n_jobs` seam.
3. **Abort on breach.** What `memory_limit_ratio` currently implies. Needs the pipeline to be
   killable, which has the same problem described in `inert_pipeline_timeout_2026_08.md` — a thread
   cannot be cancelled once started. Least valuable of the three and the most machinery.

(1) and (2) need no concurrency work at all.

## Prerequisite nobody has done

All three need a measured memory profile of a real run — peak RSS by stage, and how it scales with
sample count, feature count and `n_jobs`. Without that, any limit is a guess presented as a
guarantee, which is the failure mode this project has paid for repeatedly. The profiling is worth
doing on the scientific-validity runs that are already planned, since those are real-data runs at
realistic size: capture peak RSS per stage while they happen, rather than staging a separate
exercise later.

## Sequencing

Not now. The current priority is running pipelines to judge scientific validity, and this work does
not unblock that. But it is cheap to gather the input for it *during* those runs, and doing so is
what makes the feature a measurement rather than a guess.

Do not ship `memory_limit_ratio` / `cpu_percent_limit` as options until they enforce something.
Until then they should be deleted from `PipelineRunner.__init__`, along with the module docstring's
claim of "resource isolation", so nothing reads as a guarantee that is not there.
