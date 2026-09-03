# Prediction Validity Reporting — Implementation Plan

_Drafted 2026-09-03, consolidated same day. Not started._

## Read this first (this plan is self-contained; do not reconstruct it from a conversation summary)

- **Why any of this exists**, with every measurement and its references:
  `dev-docs/methodology/small_sample_prediction_validity.md`. Read it before changing a threshold.
- **The audit narrative** (how the conclusions were reached, including three of my own wrong
  conclusions and what overturned them): `dev-docs/issues/disconnectome_design_audit_2026_08.md`.
- **Settled; do not re-litigate.** Automated space-switching or halting on these metrics (measured,
  26 % correct, rejected — STATUS 3g). Simulated effect sizes for the MDE (rejected; both terms are
  measured from real `y`). Shipping `raw_only`+ElasticNet as a default (forbidden by ADR §1.3, and
  narrowing reaches the floor without beating it). Bitwise reproducibility as a goal (ruled out
  previously; use measured tolerances).
- **The one-directional rule**, which governs the wording of every message this feature emits: a
  model's score carries selection inflation from its own max-over-trials, the mean predictor's
  carries none. *Failing* the floor is strong evidence; *passing* it is weak. Never phrase a pass as
  validation.

---

## 0. Order of work

**Step 0 — land PR #10 first.** It is `MERGEABLE` / `CLEAN`, `fast-tests` green, 15 commits ahead of
`main` and 0 behind (checked 2026-09-03). It is the hard prerequisite: ground-truth columns pair with
prediction columns **by position**, `sorted()` puts `target_10` before `target_2`, and at 87 targets
that mis-pairs 85 of them. A validity report built on top would attach correct statistics to the
wrong measures — confidently wrong beats missing, in the bad direction.

Before merging, **fix the PR's own drift**: it carries 1 code commit (`b3d2054`, the multiclass
held-out metrics fix) and 14 docs commits from this audit, while the body describes only the code
fix. Update the title/body to say it also carries the audit and the methodology doc. Not worth
splitting — the docs are `dev-docs/` + `STATUS.md`, touch no code, and conflict with nothing.

**Then, in order:** phase 1 (floor) → phase 2 (pre-flight report) → phase 3 (filter, opt-in) →
phase 4 (stability check, post-hoc). Each is independently landable and independently useful. Phases
1–2 are the pair that would have prevented the June misreading; 3–4 are cost management and are
optional to the scientific fix.

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

Also writes **`prediction_search_space.json`** — the resolved prediction search space actually in
force for this run. Not cosmetic: it is what makes phase 4 honest (see the gap recorded there), and
today the space is recoverable from an output folder only as "the package default on the day".

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

**What "seed spread" is.** The search picks models with Optuna's TPE sampler, which is stochastic:
it draws trials randomly, guided by what it has already seen. A different sampler seed walks a
different path through the search space, lands on a different model, and returns a different score —
same data, same folds, same trial budget, just a different draw.

The audit's core finding is that this dominates. Five independent draws differing **only** in the
sampler seed disagree by a median per-target range of **0.080**, which is the size of the effects
themselves. The R² EMUSES prints for a target is therefore one sample from a distribution about as
wide as the thing being measured, and the ranking built from it does not reproduce: `larapinch` at
#1 was a property of June's seed, not of `larapinch`.

Seed spread means running the search under ≥2 sampler seeds and printing the range beside the score
— a reproducibility error bar. `R² = 0.14 (0.10–0.18 across 2 seeds)` lets a reader see the margin
sits inside the noise. Reporting a rank without it hides exactly the failure this audit found.

### Phase 4 — a post-hoc stability check, NOT a pipeline default (decided 2026-09-03, CF)

Running extra sampler seeds inside the pipeline doubles a 19-hour run. Screening by the floor would
cut that to +25 % (23 of 87 targets on `DSD_repro`), but CF's call is that it is **too heavy to
default on**, and there is a second objection that settles the design:

**The seed clash.** EMUSES lets the user fix seeds: `--random_state` → `master_seed` →
`default_rng(master_seed)` draws `prediction_seed`, `cv_seed`, `optuna_seed` in that order
(`emuses_pipeline.py:76-92`). A user who fixes the seed is asking for the same answer every time.
Varying the sampler seed inside that run answers a *different* question — how much the answer depends
on the seed — and a user could reasonably read it as EMUSES ignoring the seed they set.

Note what this objection is **not**: it is not a determinism problem. Appending a fourth draw to that
same `root_rng` sequence leaves the first three untouched, so extra sampler seeds would be a
deterministic function of `master_seed`, reproducible and backward compatible. The problem is
conceptual, not technical — which is precisely why it belongs in an explicitly invoked tool rather
than silently inside every run.

**So build it as a separate command over an existing output folder.** `emuses stability-check
<model_or_output_folder> --n_seeds 3`:

- reads the saved embedding, scores and fold seeds from the folder. **Verified present** in a real
  run folder (2026-09-03, June's `new_pred_pipeline_12-06-2026`): `embeddings.npy`,
  `split_dataset/train_labelled_scores.npy`, and `random_seeds.json` carrying `master_seed`,
  `cv_seed`, `optuna_seed`, `prediction_seed`. The folds are exactly reconstructible.
- **Reuse `emuses rerun`** (`emuses/cli/main.py:495`), which already reconstructs an invocation from
  an output folder, and follow the existing subcommand pattern (`workspace_app`, `admin_app`,
  `models_app`). No new CLI architecture.

**Gap found, and it must be fixed in phase 1 or 2, not phase 4.** The *prediction* search space is
**not persisted**. `command.txt` records `--optim_dict optim_dict_disconnectome` (UMAP/clustering) and
`--optuna_trials 60`, but carries no `--prediction_optim_dict`, so the space is recoverable only as
"whatever the package default was on the day of the run". If `optim_dict_predict` changes later,
`stability-check` on an old folder silently re-runs a **different space** and reports a spread that
conflates seed variation with space variation — a plausible wrong number, which is the failure class
this whole feature exists to stop.

So: **phase 1 or 2 writes the resolved prediction search space to `prediction_search_space.json`** in
the output folder. Cheap, and it is the enabling change for phase 4. For folders that predate it —
June's included, permanently — `stability-check` must **state which default it assumed** and mark the
result as such, never silently assume today's.
- re-runs the search under K additional sampler seeds derived from the stored `master_seed`;
- reports per target: the original score, the range across seeds, and whether the lift over floor
  survives the spread.

Three advantages over a flag: nobody pays for it who does not ask; it runs on **June's existing
output right now**, without re-running 19 hours; and it cannot be confused with the seed the user
fixed, because they invoked it themselves.

Keep `--seed_spread [off|screened|all]` as an in-pipeline option **defaulting to `off`** for users who
want it in one pass. Document both, and document that the spread is deterministic given
`--random_state`.

**The hint (this is the part that makes it discoverable).** After training, when a target's lift over
floor is smaller than its sampling SD, emit: *"this result may not reproduce across sampler seeds —
run `emuses stability-check` to quantify it."*

Use the **phase-2 repeated-split SD** for this comparison, not the across-fold SD. This is not a
style preference. The across-fold SD understates the true error bar (Varoquaux 2018; measured here,
the permutation null understates it by 1.96×), so a trigger built on it fires **too rarely** and
makes fragile results look reliable — failing in the one direction that matters. The repeated-split
SD is already computed by phase 2 and costs nothing extra. If phase 2 was skipped
(`--power_report off`), emit the hint unconditionally rather than computing a dishonest one.

---

## 2. CLI surface

Typer, `--snake_case`, str-Enum for choices — matching `emuses/cli/pipeline_options.py`.

```
--power_report [off|report|filter]     default: report
--power_permutations INT               default: 1000   (0 = skip the permutation part, keep SD/MDE)
--seed_spread [off|screened|all]       default: off    (decided: too heavy to default on)

emuses stability-check <folder> --n_seeds 3               # phase 4, post-hoc, no pipeline re-run
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
| at CSV generation | gated two-file ranking, `WARNING.txt`, summary block | milliseconds |
| at CSV generation | the phase-4 **hint** where lift < SD | free |
| **separately, on demand** | phase 4 — `emuses stability-check` on an existing folder | ~+25 % of a search per extra seed, screened |

Phases 1 + 2 together cost **under 0.1 %** of a full run. Phase 4 costs nothing unless invoked.

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
  loudly, in the log *and* in `WARNING.txt`. A near-empty file that reads like a small clean result
  is the failure mode.
- **P4** (phase 4) — run `stability-check` twice with the same `--random_state` and confirm the two
  reports are **identical**. The seeds are drawn from the stored `master_seed`, so a difference means
  the derivation escaped the seeded RNG. Then confirm the first three derived seeds
  (`prediction_seed`, `cv_seed`, `optuna_seed`) are **unchanged** from before the feature: appending
  draws to `root_rng` must not shift them, or every existing seeded run silently changes its results.

**End-to-end**: re-run `DSD_repro` with `--test_size 0.2` (June used 0.0 and so produced no held-out
evaluation at all), ~19 h / 9.6 GB peak. Expected: 13 targets pass permutation at q<0.10, 0 exceed
their MDE, `larapinch` in the below-floor file rather than at rank #1.

---

## 6. Decisions taken (2026-09-03, CF)

**Warnings surface in both places.** The run log *and* a top-level `WARNING.txt` in the output
folder. The log is where a warning belongs; the file is what actually gets read. `WARNING.txt` is
written only when there is something to say, and its absence must not be load-bearing — the
end-of-run summary block (§4.5) is written unconditionally either way.

**`--power_report report` is the default.** 2.5 minutes against a 19-hour run. This **changes the
output contract of every existing workflow**, which CF flagged as the thing to be careful about, so:

- Any existing test asserting on the *set* of files in an output folder, or on the *columns* of the
  performance CSVs, will fail. Those failures are expected and legitimate to update, because the
  contract intentionally changed. **G002 still applies**: a test updated to match an intended
  contract change is fine; a test weakened until it passes is not. Each such edit must be justified
  in the commit message by naming the contract change, not by naming the failure.
- **Affected tests, enumerated 2026-09-03 — the blast radius is near zero.** Four files reference
  the performance CSVs, and none of them breaks:
  - `tests/regression/regression_metrics.py:91` reads the summary CSV by **header name**
    (`dict(zip(header, row))`) and keeps only the fields in `SCORE_FIELDS` (line 31). Added columns
    are ignored, so nothing breaks — **and adding `Floor`/`Lift` to `SCORE_FIELDS` is how the floor
    gets pinned by the existing numerical guard.** That is the extension point for phase 1's
    regression test; prefer it to a new file.
  - `tests/integration/test_hcp_api_current.py:132` and `test_hcp_api_real.py:164` list the summary
    CSV in a *download-if-present* block guarded by `if any(...)`. Not assertions.
  - `tests/integration/test_real_world_pipeline.py:290` is a comment.
  - **Nothing in `tests/` reads `performance_target_rankings` at all**, so the phase-1 ranking split
    — the one genuine contract change — breaks no existing test. That is a gap, not a licence: the
    split is exactly what needs a new test.
  Re-run this enumeration if the phase order changes; a count discovered mid-refactor is how "just
  update the tests" turns into G002.
- The new files are **additive**. Nothing existing is renamed or removed in phase 2. The one genuine
  breaking change is the ranking split in phase 1/§4.3, and it lands separately so its blast radius
  is legible in its own commit.

**`--seed_spread` defaults to `off`, and phase 4 becomes a post-hoc command.** Two reasons, both
CF's: the cost is too heavy to impose on every run, and varying a sampler seed inside a run where the
user fixed `--random_state` invites exactly the wrong reading. Discoverability is handled by the hint
(§1 phase 4) rather than by the default. Full reasoning in phase 4.

### Nothing is open. Anything new goes here rather than into the phases above.

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
