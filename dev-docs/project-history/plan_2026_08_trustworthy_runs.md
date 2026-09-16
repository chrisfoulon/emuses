# ARCHIVED — EMUSES: a tool whose runs you can trust and publish from

_Archived into the repo on 2026-09-08 from `~/.claude/plans/playful-watching-naur.md`, which was
then deleted. It lived in a session-private directory where no other session could see it, which is
the wrong home for material this durable._

**Do not work from this file.** It is the state of play as of 2026-08-25 and is superseded by
`STATUS.md`. Two parts were extracted because they are still live and belong somewhere people read:

- the **traps** and **standing decisions** → `dev-docs/traps.md`
- the phase-by-phase outcomes → already folded into `STATUS.md`

Kept whole rather than pruned so the reasoning behind each decision stays recoverable.

---

_Consolidated 2026-08-24. Supersedes all earlier versions of this file and
`i-ll-go-to-bed-hazy-hickey.md`. Current state of play, not a journal — newer information replaces
older rather than being appended._

## Goal

It completes, it does what its flags say, and the same command twice gives the same answer.

**Merged to `main` 2026-08-24** (PR #8, merge commit `acc0e30`) — the end-to-end bar was met and
`tests/regression` passes on `main` itself. `chore/core-boundary` is spent; branch fresh from `main`
for the next piece.

---

## Five branches in flight, and the one conflict between them

As of 2026-08-25 11:00, nothing below has merged. Chris decides when.

| branch | commits ahead of `main` | based on |
|---|---|---|
| `feat/inference-on-service` | 1 | `main` — **PR #9, open** |
| `fix/science-path-tests` | 3 | *stacked on* `feat/inference-on-service` |
| `chore/extras-move` | 5 | `main` — independent |
| `fix/regression-conftest` | 2 | `main` — independent |
| `docs/njobs-arm-b` | 1 | `main` — independent, docs only |

Suggested order: PR #9, then `fix/science-path-tests`, then the three independents (extras-move last
— 87-file diff, wants a clean base). Any order produces the same single conflict.

**Recompute the conflict before merging.** The recipe below was measured when `chore/extras-move`
was at 2 commits; it is now at 5, and two branches did not exist. Re-run
`git merge-tree --write-tree --name-only <a> <b>` rather than trusting the recipe verbatim — the
*shape* (one file, the numbered list) is expected to hold, the exact hunk may not.

`fix/regression-conftest` and `docs/njobs-arm-b` were deliberately kept out of the conflicted hunk
where possible: the conftest fix records itself in the *State of play* pinning paragraph instead.
`docs/njobs-arm-b` does touch the numbered list (item 2, marked done), which is exactly the kind of
edit the recipe below handles.

### Resolving the STATUS.md conflict — measured with `git merge-tree`, not guessed

**Exactly one file conflicts: `STATUS.md`. One hunk.** `.codebase-memory/adr.md` auto-merges clean
(§2.5b from Phase 4 and §2.10 from Phase 5 sit in different regions), and so does the
"Parked features live in `emuses/extras/`" bullet under *Decided strategy*. Do not go looking for
more than the one hunk.

The hunk is in the **"Open questions / next"** numbered list:

- **Take the `fix/science-path-tests` side verbatim.** It is items 3 (the two error messages) and 4
  (recorded, not being acted on). The `chore/extras-move` side is the *older* list — it still
  carries "Phase 1F — put `emuses inference` on the service" as pending, which is done. Deleting
  that side loses nothing.
- **Then fix item 1 by hand**, because the correct text exists on neither side. The
  `fix/science-path-tests` version reads:

      1. [x] ~~**Phase 4** — science-path test failures~~ done 2026-08-24 (`fix/science-path-tests`).
             [ ] **Phase 5** — finish the `emuses/tools/` → `emuses/extras/` move (22 modules, 8 import
             rewrites). `tests/test_architecture_boundary.py` verifies it.
             [ ] The 33 remaining failures in `tests/cli` / `tests/foundation_fastapi_service` ...

  Phase 5 is **done** (`chore/extras-move`, commit `e6bfcf1`). Replace that middle line with a `[x]`
  and the commit, and keep the third line — those 33 failures are still untriaged.

**Why the conflict exists at all:** `chore/extras-move` was branched from `main`, whose `STATUS.md`
predates the Phase 4 update. That was the right trade — an independent branch is worth one
predictable doc conflict — but it means the extras branch's `STATUS.md` is *stale by construction*.
When in doubt, the science-path side is the newer text.

---

## Priorities now

**Scope for this stretch: make the pipelines run, not make them right.** See the standing decision.

1. ~~**Phase 4** — the science-path test failures. **Phase 5** — the extras move.~~ **Both done
   2026-08-24**, unmerged. See §3 and §4.
2. ~~**Re-arm `tests/regression` in whole-tree runs.**~~ **Done 2026-08-25**, branch
   `fix/regression-conftest` (off `main`, merges independently), commits `f1233e9` + `ef15097`.
   See §5.
3. ~~**Finish the `n_jobs` evidence**~~ **done 2026-08-25** (`docs/njobs-arm-b`, `7530e2a`). See §2.
4. **Small runnability fixes** — see §1.

**Phase 1F is done** (2026-08-24, branch `feat/inference-on-service`) — see §3.

**End-to-end status, measured 2026-08-24 via the CLI (service path):**

| check | result |
|---|---|
| `emuses full` | exit 0 |
| `emuses umap` | exit 0 |
| `emuses inference`, headerless CSV | exit 0 |
| `emuses inference`, CSV with header + `--input_header 0` | exit 0 |
| `ModelIOManager.validate_model` on the `full` output | `is_complete_model=True`, no errors |
| listeners left on 8000–8010 | none |
| `tests/regression` on `main` after the merge | 14 passed, 83 s |

So EMUSES **runs end to end on `main`**.

### 1. Small runnability fixes, and what is deliberately NOT being fixed

**Fix (cheap, in scope):**

- **The header-CSV error message.** A CSV with a header fails with "No numeric data remaining after
  processing the file", which does not mention `--input_header`. The option exists and
  `--input_header 0` works — this is a bad message, not a bug. It cost real time twice.
- **The `.npy` rejection message.** `emuses inference` refuses `.npy` with "Unsupported file format".
  Note the file people reach for is `split_dataset/test_features.npy`, which is stored **after**
  normalization and is the wrong input regardless of format, so the message should say that rather
  than the format simply being accepted.

**Recorded for Chris, NOT to be acted on** (per the standing decision — these are judgements about
result quality, which is his call):

- Fits can collapse to intercept-only and nothing says so. On `test_data/` every fold estimator is an
  `ElasticNet` with all coefficients zero, returning the training-target mean for any input;
  `prediction_values.npy` holds one value across 10 000 grid points and `confidence_values.npy` is
  exactly 1.0. Confidence is `1.0 - std(across folds)`, so agreement between useless models reads as
  certainty. **This is expected on `test_data/`** — it is a rank-1 synthetic ramp with no signal.
- Off-manifold input collapses the UMAP transform to a single point silently (pre-normalized split →
  **1** distinct embedding; the same rows raw → 10; all 50 raw → 50). Worth a guard eventually, but a
  guard that fails runs is the wrong thing to add while the goal is getting runs to complete.
- `tests/regression` baselines are pinned at negative R² (mean -0.3554, min -0.9809), so a passing
  suite is not evidence that prediction works. It is still valid for what it is for.

### 2. The `n_jobs` evidence — COMPLETE

1E (Arm A) was measured **only at the regression config, 48 samples**: 18/18 scalar metrics
identical against both the API baseline and the pre-1E forked CLI, ARI 1.0, distance correlation
1.0. The agreed standard was "regression suite **and** a larger-n arm", because float
non-associativity in a parallel reduction shows at larger n first.

**Arm B — DONE 2026-08-25**, branch `docs/njobs-arm-b` (off `main`), commit `7530e2a`. Full
write-up: `dev-docs/issues/njobs_arm_b_2026_08.md`.

Digits 1797 × 64, binary label (`digit < 5`), one target, run **through the CLI/service** — the
Python API path would have bypassed the process-identity mechanism 1E fixed. Only `--n_jobs` varied.
Non-degenerate (14 clusters, 5.1 % noise, Mean_Score 0.847), so the verdict is not the all-noise
ARI = 1.0 trap. **18/18 scalar metrics identical, ARI 1.0, distance correlation 1.0, max abs
distance difference 0.000e+00** — same 18 metrics and same `compare()` as Arm A.

**The trap this arm walked into, and out of:** an identical result is equally consistent with "the
parallel reduction is numerically safe" and with "`--n_jobs 4` never engaged" — the pre-1E bug
itself. Reporting 18/18 without separating them would have re-certified the bug the arm exists to
rule out. Wall clock cannot separate them (314 s vs 246 s, ratio 1.28, inside this machine's noise).
A **CPU-percent control** does: 124 % at `n_jobs=1` vs **161 %** at `n_jobs=4`.

Two things worth not re-deriving:
- **`--n_jobs` buys threads, not processes.** The service scopes the joblib backend to `threading`
  on purpose (`pipeline_runner.py:422`; loky re-imports the scientific stack per worker and turned a
  ~110 s test into >300 s with eight workers alive). Sampling found **0 loky workers**, which is
  correct — a worker-process check written before reading that code reads as a failure.
- **The identical numbers have a mechanism.** joblib returns results in submission order whatever
  the backend, so the reduction order is fixed regardless of worker count. Non-associativity was
  never likely to bite here; the measurement settles it, the mechanism explains it.

If a future arm ever differs, that is a finding about parallel reductions, not a reason to widen a
tolerance.

### 3. Phase 1F — `emuses inference` onto the service — **DONE 2026-08-24**

`emuses inference` submits to `/api/v1/jobs/pipeline/inference`. `KNOWN_LOCAL_EXECUTION` is empty:
no CLI path executes a pipeline in-process. ADR §4 records the decision and the detail.

What the plan got wrong going in: **"the endpoints already exist, so this is wiring" was false.**
`/api/v1/inference` and `/api/v1/inference/async` existed and could never have worked — they handed
`InferenceStage` a context holding only `verify_integrity` and `output_format`, and nothing in that
path loaded the data file. Every request returned 422 "No inference features found in context"
(measured before touching anything). Their own endpoint test asserted a 422 and got one, so nothing
ever noticed. **An endpoint existing is not an endpoint working** — probe it before planning around it.

There is now one implementation, `emuses/pipelines/inference_runner.py::run_inference`, called by the
inference job and by both HTTP endpoints. Their responses were also empty (`predictions: []` with a
correct sample count, because they read `results["predictions"]` while `InferenceStage` nests
predictions under `target_results`); `_inference_results_to_response` fixes that and converts numpy
recursively.

Verified: the same CLI command before and after produced **bitwise identical** prediction and
confidence CSVs (50×8, max abs diff 0.0). Both HTTP endpoints now return 50 predictions matching the
CLI. New guards perturbed and confirmed failing: route renamed, CLI sending the wrong pipeline type,
a training stage left enabled on an inference job, three option-mapping breaks.

### 4. Phases 4 and 5

**Phase 4 — DONE 2026-08-24** (branch `fix/science-path-tests`, commit `d147063`, stacked on
`feat/inference-on-service`). 33 failed / 155 passed → **185 passed, 0 failed**; across the wider
subset 68 → 33 with **no new failures**, `tests/regression` 14/14, `dev_test_runner` 13/13,
collection 2608 / 0 errors. Seven root causes, written up in
`dev-docs/issues/phase4_science_path_triage.md`; three contracts now in **ADR §2.5b**:

1. `_predict` always returns `target_results` — single-target is the n=1 case, no flat key anywhere,
   including the no-models branch (which used to die with `KeyError: 'target_results'`).
2. **Normalisation happens once, in `EMUSESPipeline`**, which loads the model's `input_scaler.joblib`
   in inference mode. `InferenceStage._transform_features` forwards features untouched. Nine tests
   asserted the opposite; doing both is what the withdrawn "constant predictions" claim was about.
   There is now an explicit double-normalisation guard.
3. `InferenceStage` reads `inference_features`/`inference_labels`, never `prediction_test_*` —
   **HeatmapStage** chooses which split to hand over. Two tests in the suite contradicted each other
   on this; the refusal wins, because preferring the test split would silently override that choice.

Also fixed: an empty ensemble surfaced as numpy's "zero-size array to reduction operation minimum";
the log line reported the *input* count as "predictions generated" (it said 5 while the ensemble was
empty); `output_path` stayed a `PosixPath`, breaking JSON serialisation; `EMUSESPipeline(args,
inference_data=...)` was dead code and is gone.

**Trap this cost an hour:** `git checkout <file>` to undo a perturbation **also discards uncommitted
work in that file**. It reverted nine production edits mid-perturbation; the next patches then failed
to apply, their `assert` fired unseen inside a heredoc, and the tests failed anyway — for the missing
work, not the perturbation. It read exactly like a successful perturbation. Commit first, then
perturb.

**Phase 5 — DONE 2026-08-24** (branch `chore/extras-move`, commit `e6bfcf1`, **branched off `main`**
so it merges independently of the Phase 1F/4 stack). 22 modules, 17,552 lines out of `emuses/tools/`
into `emuses/extras/`. The point was not tidiness: the boundary was 22 names typed into
`tests/test_architecture_boundary.py`, describing files sitting next to core code, and a list like
that is correct only while someone remembers it. It now follows from where a file lives, and
`EXTRAS_MODULES` collapses to the two modules that could not move (`cli/cloud_validation.py`,
`foundation_fastapi_service/stage_runners.py`, each inside an otherwise-core package).

Core needed no change — `model_registry_factory` already loaded the cloud and database backends
inside functions, which is the sanctioned lazy pattern.

**Measured, before → after, on the 12 test directories that reference a moved module:**
12 failed / 847 passed / 6 skipped / 17 errors → *exactly the same*, same 29 items, no drift.
All 22 modules import. Collection identical to `main` (1521/2592, 1071 deselected).
`tests/regression` 14 passed; `dev_test_runner` 13/13.

**The move opened one hole a list did not have, and it is now guarded.** Measured, not assumed:
delete `"emuses.extras"` from `EXTRAS_PACKAGES` and the real core→extras violation stops being
reported, while ~15 *legitimate* extras→`multi_user_service` imports start being reported instead —
loud, but pointing everywhere except at the cause. `test_the_extras_package_is_actually_declared`
names it, and fails under all three perturbations (entry removed, package widened to swallow core,
parked code deleted).

`dev-docs/project-history/` deliberately keeps the old `emuses.tools.*` paths: it records what
happened, and the files were called that at the time.

**Closed with a whole-suite before/after, 2026-08-24 (23:23).** The targeted 12-directory run above
cannot see cross-directory effects, so the full default suite was run on both trees — `main` in a
throwaway worktree, `chore/extras-move` in place, same flags, `-p no:randomly`:

| | main | chore/extras-move |
|---|---|---|
| result | 150 failed / 1343 passed / 14 skipped / 15 errors | 151 failed / 1343 passed / 14 skipped / 15 errors |
| wall | 950.72 s | 950.39 s |

**Set-diff: one line, and it is a known flake.** `test_workload_pattern_validation` asserts a
≥0.98 success rate over ~77 concurrent operations; it failed at 97.40% (75/77), and rerunning
`tests/model_registry/` on **`main`** reproduced it there at 95.59%. It passes alone on both trees.
No mechanism either — it drives `local_model_registry`, which did not move.
`dev-docs/issues/flaky_concurrent_load_threshold_2026_08.md`, commit `3cce4b9`.

Note the pass counts match at 1343 *because* the branch gained the new boundary test and lost the
flake — the branch collects one more test than `main` (1523 vs 1522). That arithmetic is the
confirmation that `test_the_extras_package_is_actually_declared` passes in a full run.

**The full run also surfaced a pre-existing hole that has nothing to do with the move:**
`tests/regression` gives 14 passed as `pytest tests/regression/` and **14 errors** as a bare
`pytest`, all `ValueError: no option named 'regen_baselines'`. `pytest_addoption` lives only in
`tests/regression/conftest.py`, and pytest honours that hook only from *initial* conftests; with
`testpaths = tests`, that file is not one. So the numerical pinning that guards against silent
scientific drift **does not execute at all** in any run that does not name its directory — and it
reports "error", not "regression detected", inside a suite already carrying ~150 known failures.
Untouched, written up with an untested fix and the perturbation that would prove it:
`dev-docs/issues/regression_conftest_addoption_2026_08.md`, commit `99719ff`.

---

## 5. The numerical pinning was switched off, and nobody could have seen it

**Done 2026-08-25**, branch `fix/regression-conftest` (off `main`, so it merges on its own),
commits `f1233e9` (fix + guard) and `ef15097` (ADR §2.9d, STATUS).

`--regen-baselines` was declared in `tests/regression/conftest.py`. pytest honours
`pytest_addoption` only from *initial* conftests, and `testpaths = tests` means a subdirectory
conftest is not one. Measured at a single commit: **14 passed** as `pytest tests/regression/`,
**14 errors** as a bare `pytest` — `ValueError: no option named 'regen_baselines'`, every test dead
at setup because all of them reach the `regenerating` fixture.

So the suite that pins prediction scores, composite score, UMAP/HDBSCAN metrics, cluster count,
cluster structure and embedding geometry **did not execute at all** in whole-tree runs. It said
`error`, not "regression detected", inside a suite already carrying ~150 known failures — which is
exactly why it survived: it read as one more piece of known breakage.

The hook moved to `tests/conftest.py`; the fixtures stayed put. The help text was **moved as a
literal, not imported** — `tests/conftest.py` loads on every invocation including the `fast-tests`
CI job that installs `--no-deps`, and importing from `tests/regression/` would drag the scientific
stack in there (that file's own comment records a previous instance of exactly that).

**Perturbed, each patch confirmed applied before the run:**

- **P1, the one that matters** — shifted `target_0_Mean_Score` −0.3554 → −0.1777 in the stored
  baseline. The **whole-tree** run failed with `target_0_Mean_Score moved beyond the chosen
  tolerance`, max abs diff 0.1777, untouched dataset still passing. That assertion was unreachable
  before the fix.
- **P2** — hook deleted from `tests/conftest.py`: original errors return, both guard tests fail.
- **P3** — hook duplicated back into `tests/regression/conftest.py`: structural test fails naming
  both files; the live check correctly still passes.

**Full default suite, `main` → `fix/regression-conftest`:** 150 failed / 1343 passed / 14 skipped /
**15 errors** → 150 failed / **1359** passed / 14 skipped / **1 error**. Set-diff over test IDs:
the 14 regression errors gone, **nothing added**. The +16 is 14 regression tests + 2 guard tests;
the surviving error is the pre-existing `tests/unit/test_umap_utils.py` teardown.

`tests/test_pytest_option_registration.py` is the standing guard — `pytest_addoption` must be in
`tests/conftest.py` and no other conftest under `tests/`, checked with `ast` rather than a substring
so a comment cannot satisfy it, plus a live check that the option registered in whatever invocation
is running. It fails in *every* invocation, unlike the 14 regression tests, which only complain in
the whole-tree run nobody watches.

**Loose end for whoever merges:** `dev-docs/issues/regression_conftest_addoption_2026_08.md` lives
on `chore/extras-move` and still describes the fix as an **untested hypothesis**. It is now tested.
Delete it or reduce it to the resolution once the branches converge — `fix/regression-conftest`
cannot touch it, the file does not exist there.

---

## Standing decisions — do not re-litigate

- **Scientific plausibility is Chris's call, and not now** (decided 2026-08-24). The goal for this
  stretch is that the pipelines **run end to end**. Do not spend time assessing whether predictions
  are plausible, on synthetic or real data — Chris has had runs with plausible predictions before,
  and will judge the results himself once he can train and infer freely. Fix anything *obviously*
  broken; do not build quality gates, degeneracy detectors, or plausibility checks on your own
  initiative. Record such observations for him instead of acting on them.
- **One execution path: every mode goes through the service** (ADR §4). Local auto-starts one. A
  separate local path was built on 2026-08-23 and **reverted the same day**: inside forty lines it
  had produced a third progress mechanism, a leaked temp file, no timeout, and a CLI where `full`
  behaved differently from `umap`/`heatmap`. Going over HTTP locally also catches real bugs — Phase
  1C's missing `/api/v1/jobs/pipeline/umap` route was found on a laptop *because* of it.
- **The service is its own interpreter, not a fork** (ADR §4, Phase 1E). `get_safe_n_jobs` is
  correct and unchanged; the process identity was the bug.
- **Serial Optuna search is the default** (ADR §2.9c). `optuna.optimize(n_jobs>1)` is
  nondeterministic and no seed fixes it. Parallel is an opt-in that warns.
- **`--hdbscan_jobs` is inert** (`parallel_mode="umap"` is never overridden) and is documented and
  guarded, **not wired or removed**. Same for the five `NOT_IMPLEMENTED` options
  (`--min_cluster_size`, `--model_selection`, `--use_enhanced_pipeline`, `--parallel_models`,
  `--inspect_data_state`) — **do not implement or remove without asking.**
- **Bitwise-across-platforms is out of scope** (ADR §2.9b). Every float tolerance in
  `tests/regression/` is *chosen*, not measured — local variation is exactly zero.
- **The master-seed derivation is the ONLY seeding mechanism** (ADR §2.9). Never invent a second.
- **An EMUSES model is an entire folder** (ADR §2.1). The registry is a path lookup service.
- **Standalone `emuses heatmap` is architecturally unsupported** (ADR §2.11) — it fits against UMAP
  embeddings and `--load_umap`/`--load_embeddings` are read by UMAPStage, which a heatmap-only run
  does not execute. It fails fast with an actionable message. Do not "fix" it by loosening the check.

---

## Traps — each of these cost a wrong conclusion

**Science / config**
- `optim_dict_hcp` and `optim_dict_test` have **all parameters fixed**; `UMAP_utils.py:430` collapses
  to a single trial, so raising `umap_trials` against them does nothing. Dicts that search:
  `optim_dict_default`, `_range`, `_hard`, `_disconnectome`.
- `noise_ratio` in `best_trial_info.json` holds **`1 − noise_ratio`**: `0.0` means EVERY point is
  noise. (`noise_fraction` from the metrics extractor is the honest one.)
- The CLI keyword **`mnist` loads digits (1797 × 64)**, not the 784-dim MNIST
  (`inputs_utils.py:74`, default `dataset="digits"`). Misleads on every re-reading.
- Digits is **10-class**, and `HeatmapStage` expands it to **10 one-vs-rest binary targets**, each
  with 5-fold nested CV. Cost scales as classes × folds × n: ~67 min at `optuna_trials=2`, ~3.5 h at
  10, **~55 h at the 100 of the known-good October command** (infeasible — do not plan for it).
- sklearn 1.7 `PCA` has **no `svd_solver_` attribute**. Assert on behaviour.
- A `Mock` config **fabricates any attribute**, so it is truthy and not an int. Hence `isinstance`
  checks in `heatmap_stage._seeds_from` and `umap_stage._as_jobs`. This has caused three separate
  defects — assume it applies to any new `getattr` on a config.

**Measurement discipline**
- **Check what you fed the model before believing what it returned.** The withdrawn inference bug
  came from feeding a model its own `split_dataset/test_features.npy`, which is stored **after**
  normalization; the inference path normalizes again. Verify the input's scale matches the training
  input's scale, not the training *output's*.
- **A dramatic result deserves more scrutiny than a boring one, not less.** The digits finding was
  accepted for a day because it was alarming. Same shape as the green-test trap, opposite sign.
- **`test_data/features.csv` is rank-1 synthetic** — row *i* is `[1.i, 2.i, … 8.i]`, so all 50 points
  lie on a line. Fits collapse to intercept-only at any budget. Fine for plumbing, useless for any
  claim about prediction quality. `tests/regression` baselines are pinned at negative R² for exactly
  this reason, so **passing it says nothing about whether prediction works**.
- **Measure, don't infer.** Wall-clock here is useless below a factor of 2 — identical code measured
  138/196/256 s.
- **Perturb every guard and confirm it fails.** Two guards on one fix are not redundant.
- **Verify a perturbation actually applied.** A batch applied with `sed` silently no-matched and made
  working guards look toothless — nearly led to weakening a correct test. Use an explicit string
  replace and assert the patch landed.
- **`grep "^FAILED"` returns nothing when pytest colour is on** (ANSI prefix). Use `--color=no`.
  This once produced a comparison that read as "all 22 baseline failures fixed".
- **Compare the failure *set*, not the count.** A count can match while membership differs.
- **`manage_adr(mode="update", sections=[...])` replaces the WHOLE `adr.md`**, and returns
  `{"status":"updated"}` either way. It took the ADR from 653 lines to 113 on 2026-08-24;
  `git checkout .codebase-memory/adr.md` restored it. Edit the file directly with `Edit`, use
  `manage_adr` only to read, and check `git diff --stat` after any write to it.
- Never pipe long pytest runs to `tail`; output redirected to a file is **block-buffered**. Use
  `run_in_background`, not `&`. The Bash tool's own limit is 2 min — long runs must be backgrounded.

**Environment**
- Interpreter: `/home/chrisfoulon/miniconda3/envs/emuses/bin/python`. **NOT miniforge3**, which
  shadows `PATH`. Bare `python` in a subprocess is the same class of bug.
- **Disk is the binding constraint**: ~3.6 GB free at 91 %. A `test_data` run is ~70 MB; **a digits
  run is ~1.3 GB** (I estimated 100–200 MB and took the disk to 94 %). Extract metrics and delete
  each run folder immediately.
- Leaked services: `ss -ltnp | awk '$4 ~ /:80[0-9][0-9]$/'` is the reliable check — it asks whether a
  port is held. Since 1E the service also names itself, so `pgrep -af service_process` now works too.
  **Port 8080 belongs to another user on this machine, not EMUSES.**
- Spawning **loky workers from an already-forked process hangs** — reproduced directly. This is why
  the `get_safe_n_jobs` clamp exists and must not simply be deleted.

---

## Baselines to compare against

| check | expected |
|---|---|
| `tests/pipelines tests/foundation_fastapi_service tests/tools` + the 6 guard files | **22 failed / 386 passed / 2 skipped**, set byte-identical |
| `tests/regression` | 14 passed, ~80 s |
| `scripts/dev_test_runner.py` | 13/13 |
| whole-suite collection | 2592 tests, 0 errors |
| CLI vs Python API at the regression config | 18/18 scalar metrics identical |

Guard files: `test_cli_option_mapping.py` (20), `test_search_jobs_default.py` (15),
`test_seed_wiring.py` (16), `test_stage_only_commands.py` (4), `test_single_execution_path.py` (6),
`test_service_process_identity.py` (6).

`tests/regression/` baselines regenerate **only** via `pytest tests/regression --regen-baselines`,
and doing so is deliberate — the commit message must say what moved the numbers and why.

---

## Done

| phase | commit | outcome |
|---|---|---|
| 0 | — | `full`/`inference` run; `umap`/`heatmap` did not |
| 1A | `9c1ce71` | four dropped CLI options reconnected; five declared `NOT_IMPLEMENTED` |
| 1B1 | `512aad8` | parallelism detector fixed (it had never worked); backend override scoped |
| 1D | `687f7a9`, `4152635` | seed derivation finished — **five** disconnections, not four; prediction now bitwise reproducible |
| 2 | `b28e664` | run-to-run variation measured; cause is `optuna.optimize(n_jobs>1)` |
| Step A | `bec42c9` | serial search made the *declared* default; also unblocked whole-suite collection |
| 3 | `9108107` | numerical regression suite, proven to fail three ways |
| 1C | `5d20fad`, `d23adc9`, `4509e26` | `umap` runs; one shared option declaration; three runtime defects fixed; `heatmap` refuses clearly |
| 1B2 | `f827000`, `aa6eb14` | attempted, **reverted by decision**; `prepare_pipeline_context` kept |
| 1E | `d9536bd`, `12adb9e` | service is its own process; `--n_jobs` works; orphan fixed; `pgrep` works |
| 2C-bis Arm A | — | digits healthy in training (11 clusters, 0.9 % noise); **found the inference bug** |
| 1F | (branch `feat/inference-on-service`) | inference goes through the service; one implementation; both HTTP endpoints fixed — they had never worked |

---

## Verification checklist

1. `emuses full`, `umap`, `inference` complete from a clean directory; `full` validates via
   `ModelIOManager.validate_model()`.
2. No listener on 8000–8010 afterwards (`ss -ltnp`).
3. Two identical invocations produce identical prediction scores.
4. Every key in `random_seeds.json` has a consumer; no `optuna.create_study` without an explicit
   sampler.
5. `--n_jobs` and `--hdbscan_core_dist_n_jobs` demonstrably reach their consumers.
6. CLI and Python API agree — **done**, 18/18.
7. `pytest tests/regression/` passes **and fails when perturbed**.
8. Every tolerance cites its measurement in `dev-docs/issues/`.
9. `pytest tests/pipelines/ tests/inference/` failure count measured before and after Phase 4.
10. `dev_test_runner.py` → 13/13.
11. No CLI code path constructs an `EMUSESPipeline` directly; `KNOWN_LOCAL_EXECUTION` empty after 1F.
12. `is_subprocess_context()` True in a real `LokyProcess`/`ForkProcess`, False in the service —
    measured by spawning, never mocked.
13. **Inference predictions are non-constant per target per fold** — the open bug.
14. The randomized PCA solver is genuinely exercised (needs Arm B; assert on behaviour, not
    `svd_solver_`).

---

## Open, untouched

- `tests/multi-user-service/` hangs **as a directory** (no single file does). Root cause unknown.
  Measure on a quiet machine — one run died with `MemoryError` while swap was full from unrelated
  desktop processes.
- 36 `model_registry` failures whose fixtures encode the pre-ADR-§2.1 component model. **The code is
  right and the tests are obsolete — do not "fix" the code to accept them.**
- Two `test_enhanced_metadata_storage` failures: `configuration_hash` does not respond to manifest
  edits.
- `dev-docs/issues/optim_dict_resume_conflict.md` — Optuna parameter-space conflict on resume.
  Deferred, workaround exists.
- Multi-user admin endpoints return mock data (`docs/multi_user_service_implementation_gap_analysis.md`).
- `dev-docs/issues/synthetic_test_data_conversion.md` — 208 `np.random.rand()` across 27 test files.
  Triage before bulk converting; some are legitimately random.
- Mark the remaining slow tests; `enhanced-cli-typer` is the bulk of suite runtime.
