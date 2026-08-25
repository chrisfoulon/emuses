# `n_jobs` Arm B: the larger-n arm, and why an identical result nearly proved nothing

_Measured 2026-08-25. Closes the "finish the `n_jobs` evidence" item. Arm A (Phase 1E) was measured
only at the regression config, 48 samples._

## What was asked, and why

1E fixed `--n_jobs` being silently inert on the CLI: the service was a *fork*, so
`get_safe_n_jobs` saw a worker process and clamped any request to 1. It was then verified at 48
samples — 18/18 scalar metrics identical, ARI 1.0, distance correlation 1.0.

The agreed standard was "the regression suite **and** a larger-n arm", because float
non-associativity in a parallel reduction shows at larger n first. That arm had not been run.

## Setup

Digits, 1797 × 64, exported to CSV with a **binary** label (`digit < 5`), so all rows are kept and
the randomized-PCA path stays reachable (`svd_solver="auto"` switches above `max(X.shape) > 500`),
but there is **one** target instead of ten — roughly a tenth of the cost of the 10-class run.

Everything held identical except `--n_jobs` ∈ {1, 4}, including `--random_state 42` and serial
search (`--umap_jobs 1 --hdbscan_jobs 1`, per ADR §2.9c). Run through the **CLI**, therefore through
the service — deliberately, because the Python API path bypasses the process-identity mechanism that
1E fixed, and measuring it would have produced a reassuring number about nothing.

Input verified before trusting any output: shape 1797 × 64, values 0–16, classes balanced 896/901,
and both CSVs round-tripped against the arrays in memory.

The run is **non-degenerate** — 14 clusters at 5.1 % noise, `target_0_Mean_Score` 0.847. This
matters: an "identical" verdict on a degenerate run is the all-noise ARI = 1.0 trap in a new place.

## Result

| comparison | outcome |
|---|---|
| scalar metrics | **18/18 identical** |
| cluster ARI (n_jobs 1 vs 4) | **1.0** |
| embedding distance correlation | **1.0** |
| max abs pairwise-distance difference | **0.000e+00** |

Same 18 metrics as Arm A, via the same `tests/regression/regression_metrics.py::compare`, so the two
arms are stated in the same units rather than by two hand-maintained comparisons.

## The part that nearly went wrong

**An identical result is equally consistent with "the parallel reduction is numerically safe" and
with "`--n_jobs 4` never engaged".** The second is exactly the pre-1E bug. Reporting 18/18 without
separating them would have re-certified the bug the arm exists to rule out.

Wall clock does not separate them: 314 s vs 246 s in the main pair, a ratio of 1.28, well inside the
factor-of-2 that is noise on this machine (identical code has measured 138/196/256 s).

**Positive control** — same run at a smaller budget under `/usr/bin/time -v`:

| | n_jobs=1 | n_jobs=4 |
|---|---|---|
| Percent of CPU | 124 % | **161 %** |
| wall | 3:33 | 2:52 |
| user time | 219 s | 232 s |

More concurrent work at `n_jobs=4`, replicated in direction by the main pair. The comparison is not
vacuous.

## Why 161 % and not ~400 %, and why there are no worker processes

`create_safe_parallel` picks its backend from `get_safe_parallel_backend()`, and the service path
scopes the backend to **threading** on purpose (`pipeline_runner.py:422`). The comment there records
the measurement behind it: loky re-imports the scientific stack per worker, which turned a ~110 s
test into one still running after 300 s with eight LokyProcess workers alive.

So `--n_jobs 4` buys **threads, not processes**. Sampling the process tree during an `n_jobs=4` run
found **0 loky workers**, which is the correct result, not a failure — and a check written before
reading the code would have been misread as one. Thread counts on the service process (68–82) are
dominated by BLAS pools and cannot isolate the four, which is why CPU% is the usable signal.

**This also explains the identical numbers mechanistically:** joblib's `Parallel` returns results in
submission order regardless of backend, so the reduction consuming them runs in a fixed order
whatever the worker count. Float non-associativity was never likely to bite here. The measurement is
what settles it; the mechanism is why the answer is unsurprising.

## Conclusion

`--n_jobs` reaches its consumer, does measurably more concurrent work at 4 than at 1, and changes
**no** number at n = 1797. Combined with Arm A at n = 48, the `n_jobs` evidence is complete.

Had they differed, that would have been a finding about parallel reductions — not a reason to widen
a tolerance.
