# `tests/regression` errors out in every whole-tree run

_Found 2026-08-24, during the full-suite run after the extras move. **Pre-existing** — not caused by
that move (`git log main..chore/extras-move -- tests/regression/ tests/conftest.py` is empty)._

## The symptom

Both of these are true at the same commit:

| invocation | result |
|---|---|
| `pytest tests/regression/ -q` | **14 passed**, ~81 s |
| `pytest -q` (whole tree) | **14 errors**, 0 run |

Every error is the same:

```
ValueError: no option named 'regen_baselines'
```

## The cause

`pytest_addoption` is defined in **`tests/regression/conftest.py:26`** and nowhere else.

pytest collects `pytest_addoption` only from *initial* conftest files — the rootdir conftest and the
conftests of the directories named on the command line. `pytest.ini:38` sets `testpaths = tests`, so
a bare `pytest` has `tests` as its initial arg:

- `tests/conftest.py` **is** initial → its hooks are honoured.
- `tests/regression/conftest.py` is **not** → its `pytest_addoption` is silently ignored.

The option is therefore never registered, and every test whose fixture calls
`config.getoption("regen_baselines")` dies at setup. Naming the directory explicitly makes that
conftest initial again, which is why the targeted invocation passes.

## Why this matters more than a 14-error line suggests

`tests/regression/` is the numerical pinning described in `STATUS.md` — prediction scores, composite
score, UMAP/HDBSCAN metrics, cluster count, cluster structure, embedding geometry, all compared
against stored baselines. It is the guard against silent scientific drift, and it has been proven to
catch a real one-line production change.

In any run that does not name the directory, **it does not execute at all**. It does not fail
loudly as a wrong number; it errors during setup, in a suite that already carries ~150 known
failures, where 14 more lines are easy to read past. A guard that reports "error" instead of
"regression detected" is the failure mode this project has already paid for elsewhere.

## Proposed fix (hypothesis — **not yet tested**)

Move the `pytest_addoption` block from `tests/regression/conftest.py` up into `tests/conftest.py`,
leaving the fixtures where they are. `tests/conftest.py` is initial under `testpaths = tests`, so the
option would register in both invocations.

This has **not** been verified. Before believing it:

1. Apply the move.
2. `pytest tests/regression/ -q` → must still be 14 passed (the targeted path must not regress).
3. `pytest -q` → the 14 errors must become 14 passes, not 14 different errors.
4. Perturb it: break one stored baseline and confirm the **whole-tree** run reports a numerical
   failure, not an error. Without step 4 this fix is only assumed to restore the guard.

Step 4 is the point of the exercise. Steps 1–3 restore a passing line; only step 4 shows the guard
can still fail.
