# Resolving the `STATUS.md` conflict between the three 2026-08-24 branches

_Delete this file once all three have merged. It exists because the conflict is predictable and the
resolution is not obvious from the diff._

## The branches

| branch | commits ahead of `main` | based on |
|---|---|---|
| `feat/inference-on-service` | 1 | `main` — PR #9 |
| `fix/science-path-tests` | 3 | *stacked on* `feat/inference-on-service` |
| `chore/extras-move` | 2 | `main` — independent |

`chore/extras-move` was branched from `main`, whose `STATUS.md` predates the Phase 4 update. That
was a deliberate trade: an independently mergeable branch is worth one predictable doc conflict. It
does mean this branch's `STATUS.md` is **stale by construction**.

## What actually conflicts

Measured with `git merge-tree chore/extras-move fix/science-path-tests`, not guessed:

- **`STATUS.md`, one hunk.** That is all.
- `.codebase-memory/adr.md` **auto-merges cleanly** — §2.5b (Phase 4) and §2.10 (Phase 5) are in
  different regions.
- The "Parked features live in `emuses/extras/`" bullet under *Decided strategy* also merges
  cleanly.

Do not go looking for more than the one hunk.

## The resolution

The hunk is in the **"Open questions / next"** numbered list.

1. **Take the `fix/science-path-tests` side verbatim** — items 3 (the two error messages) and 4
   (recorded, not being acted on). The `chore/extras-move` side is the older list; it still carries
   "Phase 1F — put `emuses inference` on the service" as pending, which is done. Nothing is lost by
   dropping that side.

2. **Then fix item 1 by hand**, because the correct text exists on neither side. The
   `fix/science-path-tests` version reads:

   ```
   1. [x] ~~**Phase 4** — science-path test failures~~ done 2026-08-24 (`fix/science-path-tests`).
          [ ] **Phase 5** — finish the `emuses/tools/` → `emuses/extras/` move (22 modules, 8 import
          rewrites). `tests/test_architecture_boundary.py` verifies it.
          [ ] The 33 remaining failures in `tests/cli` / `tests/foundation_fastapi_service` are
          untriaged: ...
   ```

   Phase 5 **is done** (`chore/extras-move`, commit `e6bfcf1`). Mark that middle line `[x]` with the
   commit. Keep the third line — those 33 failures are still untriaged.

**Rule of thumb if anything else diverges:** the `fix/science-path-tests` side is the newer text.

Longer form, including what each phase actually did:
`~/.claude/plans/playful-watching-naur.md`.
