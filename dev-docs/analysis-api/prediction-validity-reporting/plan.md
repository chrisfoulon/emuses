# Prediction Validity Reporting — Implementation Plan

_Drafted 2026-09-03. Not started. Rationale and every number cited here:
`dev-docs/methodology/small_sample_prediction_validity.md`._

**Prerequisite: PR #10 must merge first.** At 87 targets the lexicographic ordering bug mis-pairs 85
of them, so any validity report built on top of it would attach the right statistics to the wrong
measures — the worst possible version of this feature.

---

## 1. What gets built

Four pieces, each independently landable and independently useful. Phases 1–2 are the ones that
would have prevented the June misreading; phases 3–4 are cost management.

### Phase 1 — the mean-predictor floor (free, no behaviour change)

New `emuses/tools/prediction_validity.py`:

```python
def mean_predictor_floor(y, folds) -> float
```

Predict the *training* mean, score with `r2_score` on each held-out fold, average. The point is that
this uses the training mean while `SS_tot` uses the test mean, which is exactly why it lands below
zero.

- `nested_optuna_cv` returns its outer fold indices alongside `scores` and `pipes`.
- `_optimise_target` computes the floor from **those** indices and returns it.
- The floor and the lift (`score − floor`) join the per-target performance CSVs.

**Cost:** 0.02 s for 87 targets. No fitting. **This is the single number whose absence caused the
whole audit.** It also lands per-target *before* that target's search, so a run that dies at hour 12
still leaves the floors on disk.

### Phase 2 — the pre-flight power report

New function called from `HeatmapStage.run` after the embedding exists and **before** the joblib
fan-out. Fixed reference models on the embedding, per target:

| quantity | how | why not something cheaper |
|---|---|---|
| sampling SD | 20 repeated 70/30 splits, real `y` | across-fold SD understates it (Varoquaux 2018); the permutation null understates it by a **measured 1.96×** |
| permutation null → p, q | 1000 shuffles of `y`, folds fixed, BH across targets | only valid because the model is fixed (§2.2 of the rationale); with a 60-trial search inside each permutation it costs ~300× |
| MDE | `null_p95 + 0.84 × SD` | 0.84 = one-sided z at 80 % power. Both terms measured. **No simulated effect sizes** — an earlier simulated version was rejected, correctly |

Two reference models, `RidgeCV` and a fixed RBF `KernelRidge` (median-heuristic gamma, small
alpha/gamma grid inside the development split). The kernel arm exists to answer the one real
objection to a linear pre-flight: the search space contains kernel and RF estimators precisely
because the relationship might not be linear.

Writes `prediction_power_report.csv` **before the search starts**, one row per target:
`target, measure, n, floor, ref_ridge, ref_kernel, sd, null_p95, p, q, mde, detectable`.

On `DSD_repro` this would have printed, in about 2.5 minutes, that 13 of 87 measures carry signal
and **0 of 87 are detectable by the configuration EMUSES actually runs** — before spending 19 hours.

**Cost:** ~2.5 min for 87 targets on 8 cores (floor 0.02 s, repeated splits 13 s, kernel 49 s,
permutations 1.3 min).

**Warns; does not halt.** STATUS 3g, measured and rejected: a completed run with a loud warning is
diagnosable, a halted one is not.

### Phase 3 — filter mode (opt-in, and it stays opt-in)

`--power_report filter` skips the expensive search for targets where **neither** reference model
clears its floor.

The failure that matters is the false negative — a target the reference models cannot see but the
search would have found. Measured on `DSD_repro`, 87 targets × 25 held-out splits:

| gate | kept | run saved | false negatives | of those, detectable |
|---|---|---|---|---|
| `RidgeCV` only | 18/87 | 79 % | 4 | **0** |
| `RidgeCV` **or** `KernelRidge` | 26/87 | 70 % | 3 | **0** |
| gate on MDE instead of floor | 2/87 | 98 % | 0 | 0 |

Four false negatives is 25 % of what the full search finds, and none of them is a result anyone
would report: `laragrasp` at −0.803 against a floor of −0.968, `walk_total` at −0.018 against
−0.023, permutation q between 0.65 and 0.99. The filter discards noise-level floor crossings on
targets with no signal.

**Two decisions this settles:**

- **Gate on the floor, not the MDE.** The MDE gate also loses nothing but keeps 2 of 87. A criterion
  that discards 98 % of a run leaves no margin if the reference model is wrong for some future
  dataset. Floor gate: 70 % saved, slack to spare. Report the MDE; filter on the floor.
- **Filter mode does not become a default.** "The filter is safe" is currently generalised from
  **one** dataset (n≈88, 2-D embedding, 87 targets). Replay it on a second dataset — the 10-class
  digits run (1797×64, peak RSS 3.03 GB) is the obvious candidate — before that is even discussed.

### Phase 4 — seed spread, screened by the floor

The audit's core finding is that the per-target ranking does not reproduce: five independent draws
of the same nested search disagree by a median per-target range of **0.080**, the size of the effects
themselves. Reporting a rank without that spread hides it.

Running two sampler seeds doubles a 19-hour run. Screening fixes that: run the second seed **only
for targets that cleared their floor on pass one**. On `DSD_repro` that is 23 of 87, so **+25 %**
rather than +100 %, and the spread only matters for targets you would actually report.

---

## 2. CLI surface

Typer, `--snake_case`, str-Enum for choices — matching `emuses/cli/pipeline_options.py`.

```
--power_report [off|report|filter]     default: report
--power_permutations INT               default: 1000   (0 = skip the permutation part, keep SD/MDE)
--seed_spread [off|screened|all]       default: off    (see open question 1)
```

**Every knob must enforce something.** STATUS item 4 records `memory_limit_ratio` /
`cpu_percent_limit` / `max_workers` sitting in the config reading as guarantees while enforcing
nothing. Do not add a fourth. If a mode is not implemented, it is not in the enum.

**Scaling is the reason these are toggleable, and the reason the defaults go in the manifest.**
The floor is O(n); the `RidgeCV` arm is O(n·d²) in embedding dimension d — both negligible at any n
EMUSES will see. The `KernelRidge` arm is **O(n³)** on an n×n matrix: 49 s at n≈88, infeasible at
n=10,000. Above roughly n=2,000 the kernel arm needs a subsample cap or Nyström, and
`--power_permutations` needs to come down. Implement the cap in phase 2; do not ship the kernel arm
uncapped.

---

## 3. Where each step happens

| when | step | cost (8 cores) |
|---|---|---|
| after UMAP, before the target fan-out | phase 2 — power report; warn if nothing clears its MDE | ~2.5 min |
| immediately after, only if `filter` | phase 3 — drop targets no reference model can see | saves ~70 % of the next row |
| per target, before its own search | phase 1 — floor from the actual outer folds | 0.02 s total |
| — | the search itself, unchanged | ~19 h |
| second pass, floor-clearing targets only | phase 4 — seed spread | +25 % of the search |
| at CSV generation | gated two-file ranking | milliseconds |

Phases 1 + 2 together cost **under 0.1 %** of a full run.

---

## 4. The transparency contract

*"EMUSES only outputted 3 out of 25 targets wtf!!!!"* is the failure this section exists to prevent.
It is a requirement, not polish. **A user must never have to ask where a target went.**

1. **Every target appears in the output, always.** Nothing is dropped, ever. A target that is
   filtered, floored, or undetectable gets a **row with a reason**, not an absence.
2. **The denominator is in every header.** `"13 of 87 targets exceeded their floor"`. Two reasons,
   both load-bearing: "87 tested, 13 carry signal" is the scientific claim, and "here are 13
   measures" with no denominator is selective reporting a reviewer will treat as such; and a run
   that fails entirely must read as **"0 of 87"**, not as a short clean file.
3. **Two ranking files, not one.** `performance_target_rankings` holds only targets that cleared
   their floor, *ranked*. `performance_targets_below_floor` holds the rest as an **unranked list** —
   a rank implies an ordering by quality, and ordering noise is what put `larapinch` at #1.
4. **Filter mode writes what it skipped and why**, with the numbers:
   `not searched — no reference model cleared the floor (ridge −0.094, kernel −0.136, floor −0.070)`.
   An explanation, not a gap.
5. **An end-of-run summary block** in the log and in `context["performance_summary"]`: how many
   targets were tested, cleared their floor, passed permutation at q<0.10, exceeded their MDE — and
   for `DSD_repro` that last number is 0, which is the honest headline.
6. **The manifest records the mode and the counts**, so a model folder can be traced back to which
   diagnostics ran and which defaults were in force.
7. **Show the margin, not just the verdict.** Lift over floor is an estimate; a target just above
   and one just below are not different. Report lift *and* the spread so the margin can be compared
   against the noise. Held-out reference: 23/87 beat their floor, only 13 by more than 0.05.

---

## 5. Verification

Per `dev-docs/test_quality_conventions.md`, and note the environment traps already paid for:
interpreter is `/home/chrisfoulon/miniconda3/envs/emuses/bin/python` (bare `python` is base conda
and produces fake collection errors); `-p no:randomly`; redirect long runs to a file, never pipe to
`tail`; `run_in_background: true` rather than `&`.

**Unit** (`tests/unit/test_prediction_validity.py`):
- floor of a constant `y` → `nan`, not a crash or a silent 0
- floor on synthetic data with a **known** analytic answer, not a recorded one
- permutation p is uniform under a true null (a seeded synthetic case where there is genuinely no
  relationship — this catches a p-value computation that is subtly off by one)
- BH correction against a hand-checked vector
- MDE is monotone in SD and in `null_p95`

**Regression** (`tests/regression/test_validity_report.py`): pin the floor for two `DSD_repro`
targets. The floor is deterministic given y and folds, so this pins the fold-index plumbing — the
trap in `context.md`. Note `tests/regression/` only runs when its directory is named on the command
line until the `fix/regression-conftest` work lands (`~/.claude/plans/i-ll-go-to-bed-hazy-hickey.md`);
this is a reason to prefer that branch landing first.

**Perturbation — the step that decides whether any of this is load-bearing.** Commit first, since
`git checkout <file>` to undo a perturbation also discards uncommitted work in that file. Assert
each patch actually applied before running it: a perturbation that silently did not land reports a
clean pass and proves nothing (`feedback_silent_verification_failure`).

- **P1** — shift the fold seed in one of the two places the folds could be built. If phase 1 was
  done correctly there *is* only one place, and the floor moves together with the score. If a
  divergence is possible, this must fail.
- **P2** — feed a target whose reference models both sit below the floor with `--power_report
  filter`. It must appear in the output with a reason and be counted in the denominator. An absence
  is a failure.
- **P3** — force zero targets to clear their floor. The run must complete and say **"0 of 87"**
  loudly. A near-empty file that reads like a small clean result is the failure mode.

**End-to-end**: re-run `DSD_repro` with `--test_size 0.2` (June used 0.0 and so produced no held-out
evaluation at all), ~19 h / 9.6 GB peak. Expected: 13 targets pass permutation at q<0.10, 0 exceed
their MDE, `larapinch` in the below-floor file rather than at rank #1.

---

## 6. Open questions — need Chris's call before phase 4

1. **Default for `--seed_spread`.** `screened` costs +25 % on every run but means users stop reading
   rankings that do not reproduce, which is the audit's central finding. `off` keeps runs at today's
   cost and leaves the spread invisible unless asked for. Recommendation: `screened`, with the cost
   in the log line — but silently making every run 25 % longer is a real UX change and it is your
   call, not mine.
2. **Where the warning surfaces.** Log only, or also a top-level `WARNING.txt` in the output folder?
   The log is where it belongs; the file is what actually gets read.
3. **Should `report` mode be the default at all**, or should the first release be `off` by default
   with the report opt-in? 2.5 minutes on 19 hours argues for on-by-default, but it changes the
   output contract of every existing workflow.

---

## 7. Wrap-up (do not skip — recorded discipline)

- **ADR**: new §2.x recording (a) the reference models are diagnostic instruments and do not
  contradict §1.3, (b) automated space-switching was measured and rejected at 26 %, (c) the
  one-directional nature of the floor and pre-flight evidence. Edit `.codebase-memory/adr.md`
  **directly** — `manage_adr(mode="update")` replaces the whole file — and check the diffstat
  afterwards (`feedback_manage_adr_overwrites`).
- **Re-index the graph** (`detect_changes` or `index_repository`) after the new module lands, so
  `search_graph`/`trace_path` do not return stale results.
- **STATUS.md**: close items 3d, 3f, 3g, 3h, 3i as they land. Expect the known one-hunk conflict —
  recipe in `dev-docs/issues/status_merge_note_2026_08.md`, do not re-derive it.

---

## Working mode

**Accept-edits, not auto** — and this is the one line in this plan not to override casually.

The global rule is that autonomy is right when something outside my control decides whether the work
is correct, and accept-edits is right when "it looks done" is the only signal. This feature is
*entirely* reporting on scientific output. Its defect signature is precisely "the run looks
successful and the result is wrong" — which is the thing that happened, for three months, and is
why this plan exists. Auto mode's safety classifier catches **dangerous**, not **wrong**.

The exception: the phase-5 unit tests are mechanical and checked by their own assertions. That part
is worth switching to auto for, then switching back.
