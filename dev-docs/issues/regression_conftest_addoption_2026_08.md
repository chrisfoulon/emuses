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

## RESOLVED 2026-08-25 (`fix/regression-conftest`, merged to `main`)

The `pytest_addoption` block moved from `tests/regression/conftest.py` into `tests/conftest.py`,
which *is* initial under `testpaths = tests`. Fixtures stayed where they were — only the hook has to
live in an initial conftest.

Verified, in the order the plan demanded:

1. Repro before the fix: 2 errors. After: 2 passed.
2. `pytest tests/regression/` → still 14 passed, ~76 s. The targeted path did not regress.
3. Whole-tree run: the 14 errors became 14 passes.
4. **Perturbed.** A shifted baseline (`target_0_Mean_Score` −0.3554 → −0.1777) made the *whole-tree*
   run fail naming the metric and the max absolute difference, with the untouched dataset still
   passing. Deleting the hook restored the original errors; duplicating it failed the new structural
   guard naming both files.

Step 4 was the point: steps 1–3 only restore a passing line. `tests/test_pytest_option_registration.py`
now fails if the hook is ever moved back down beside its fixtures, which is where it looks like it
belongs. Recorded in ADR §2.9d.
