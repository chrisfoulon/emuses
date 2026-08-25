# Merge plan for the six open branches

_Computed 2026-08-25 with `git merge-tree --write-tree --name-only`, chained in sequence rather than
pairwise, because each merge changes what the next one sees. **Supersedes
`status_merge_note_2026_08.md`** (on `chore/extras-move`), which was measured when
`chore/extras-move` had 2 commits and three of these branches did not exist. Delete that file when
the branches converge._

## The branches

| branch | commits | files | notes |
|---|---|---|---|
| `feat/inference-on-service` | 1 | 15 | PR #9 open. Phase 1F. |
| `fix/science-path-tests` | 3 | 34 | **stacked on PR #9** — must follow it |
| `docs/njobs-arm-b` | 1 | 2 | |
| `fix/regression-conftest` | 2 | 5 | |
| `fix/parallelism-backend-scope` | 6 | 10 | |
| `chore/extras-move` | 5 | 93 | largest; merge last |

All six touch `STATUS.md`; five touch `.codebase-memory/adr.md`.

## Result in this order

```
feat/inference-on-service      CLEAN
fix/science-path-tests         CLEAN
docs/njobs-arm-b               CONFLICT  STATUS.md
fix/regression-conftest        CLEAN
fix/parallelism-backend-scope  CONFLICT  .codebase-memory/adr.md  emuses/cli/main.py
chore/extras-move              CONFLICT  STATUS.md
```

Three conflicts, not six. The `STATUS.md` ones are the familiar numbered-list hunk under "Open
questions / next" and are mechanical. The ADR one is two sections appended at different offsets —
take both.

## The one conflict that is not mechanical

`emuses/cli/main.py`, merging `fix/parallelism-backend-scope`.

**Take the deletion.** `feat/inference-on-service` removes `_execute_inference_locally` entirely and
routes inference through `_execute_via_unified_service` / `_execute_via_remote_service`.
`fix/parallelism-backend-scope` added a `with parallelism_backend("threading"):` scope *inside* that
function. Once inference goes through the service it is covered by the scope at
`pipeline_runner.py:422`, so the CLI-side one is redundant. Do not try to preserve it.

**Follow-up required after resolving**: ADR §2.9e and the "Where loky still runs" paragraph both
state that the CLI inference path was scoped to threading on 2026-08-25. That stops being true the
moment PR #9 lands. Correct it in the same commit — an ADR sentence that quietly goes false is the
exact drift this file is meant to prevent.

## Ordering notes

- `fix/science-path-tests` is stacked on `feat/inference-on-service` and cannot go first.
- `chore/extras-move` last is deliberate: 93 files, mostly renames, and putting it last means every
  other branch resolves against unmoved paths.
- Reordering does not remove the `main.py` conflict — it is a genuine semantic overlap between a
  branch that scopes a function and a branch that deletes it. Only the side reporting it changes.

## Before merging

The two full-suite baselines to compare against, both measured on this machine:

- `main`: 150 failed / 1343 passed / 14 skipped / 15 errors / 950.72 s
- `fix/parallelism-backend-scope`: 150 failed / **1347** passed / 14 skipped / 15 errors / 928.34 s
  (+4 = the four tests that branch adds; failure sets identical, 165 each)

Compare failure **sets** with `comm`, not counts, and strip ANSI *before* filtering — doing it after
yields an empty set that reads as "everything cleared".

---

## Executed 2026-08-25

All six landed. PR #9 merged on GitHub (`eb069ce`), the other five locally in the order above,
pushed as `a256502`. The three predicted conflicts were the only ones, and `emuses/cli/main.py`
resolved as planned — took the deletion, dropped the CLI-side scope, corrected ADR §2.9e and the
matching `STATUS.md` line in the same commit.

Measured on the merged tree before pushing: **114 failed / 1416 passed / 14 skipped / 1 error** in
16 m 48 s, against 150 / 1343 / 14 / 15 before. Compared as failure *sets*: **zero new failures**,
50 cleared, the remaining 115 a strict subset of the previous 165. `tests/regression` 14 passed in
75.7 s; `dev_test_runner` green.

`status_merge_note_2026_08.md` deleted in the same commit — superseded, and its branches are gone.
