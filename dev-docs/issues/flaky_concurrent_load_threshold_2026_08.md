# `test_workload_pattern_validation` is flaky — do not attribute it to a branch

_Found 2026-08-24 while diffing full-suite runs across `main` and `chore/extras-move`._

## The test

`tests/model_registry/test_concurrent_load_validation.py::TestConcurrentLoadValidation::test_workload_pattern_validation`

It asserts, at `test_concurrent_load_validation.py:442`:

```python
assert success_rate >= 0.98, f"{pattern_name} {op} success rate: {success_rate:.2%}"
```

## Why it looks like a regression and is not

In a full-suite run it appeared on `chore/extras-move` and not on `main`, as the *only* difference
between two 1500-test runs — exactly the shape of a real regression introduced by a branch.

It is not. Measured:

| invocation | main | chore/extras-move |
|---|---|---|
| the test alone, ×3 | 3 passed (0.78 s) | 3 passed (0.79 s) |
| `pytest tests/model_registry/` ×2 | **1 of 2 failed** (95.59%) | 2 of 2 passed |

It fails on `main` too. The observed values sit just under the bar — 97.40% (75/77) and 95.59% — so
the outcome turns on one or two operations out of ~77 under concurrent load.

There is also no mechanism: the test drives `emuses.tools.local_model_registry`, which **did not
move** in the extras split. Only the cloud and database backends moved, and they are not on this
path.

## What to do with it

Not fixed. Recorded so the next full-suite diff does not spend an hour attributing it to a branch.
If it is ever worth fixing, the question is whether 0.98 is a meaningful contract at n≈77 — at that
sample size the threshold cannot distinguish 98% from 96%, so it is closer to a coin-flip than a
guarantee. Either raise the operation count until the rate is measurable, or assert on something
that is actually deterministic.

**General rule this cost:** a single-test difference between two large runs is not evidence of a
regression until it has been rerun on the baseline branch. Isolation passing on both sides does not
settle it either — this one passes alone on both and still fails in company.
