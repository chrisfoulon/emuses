# Prediction Validity Reporting — Context

## Level 1: Plain English Summary

**Current problem.** EMUSES reports prediction R² against zero and ranks targets by it. Neither is
meaningful at small n. `sklearn.r2_score` builds `SS_tot` from the test fold's own mean, so R²=0 is
an oracle baseline nothing honest reaches; the number you would actually achieve by guessing is
negative and target-specific (median −0.086 on `DSD_repro`, reaching −2.5 for ceiling-bound
measures). Ranking without that baseline sorts on noise. In June 2026 this put `larapinch`, a
ceiling-bound ARAT measure that fails permutation testing, at rank #1, and made an overall score of
−0.1884 read as "poor but plausible" when it was *at* the floor.

Full reasoning, measurements and references: `dev-docs/methodology/small_sample_prediction_validity.md`.

**What this feature adds.** Three diagnostics and a gate on the output. It changes **nothing** about
how models are fitted or selected.

- **Mean-predictor floor**, per target, on that target's own n and folds. Free.
- **Pre-flight power report**, before the search: sampling SD from repeated splits, a permutation
  null, and the minimum detectable effect. Answers *"is there any point running this?"* in minutes
  instead of after 19 hours.
- **Gated ranking**: targets that do not clear their floor are listed, not ranked, in a separate
  file — with the denominator in both headers so a total failure reads "0 of 87" rather than as a
  short clean result.

**Integration strategy: ENHANCE.** Every hook point already exists. No new stage, no change to the
search space, no change to `nested_optuna_cv`'s contract beyond returning the fold indices it
already computes.

## Level 2: API Integration Table

| Symbol | Purpose | Inputs | Outputs | Side-effects |
|---|---|---|---|---|
| `HeatmapStage.run` (`heatmap_stage.py:117`) | Stage entry; embedding available, before the joblib fan-out over targets | context | context | **New**: writes `prediction_power_report.csv` before any search starts |
| `_optimise_target` (`heatmap_stage.py:53`) | Nested Optuna CV for one target, forked by joblib | col_idx, X, Y, cfg | tag, scores, pipes | **New**: also returns the per-target floor |
| `nested_optuna_cv` (`optuna_cv.py:140`) | Outer/inner CV loop | X, y, n_outer, random_state | scores, pipes | **Change**: also return outer fold indices (see trap below) |
| `_generate_performance_csv_files` (`heatmap_stage.py:876`) | Writes the five performance CSVs | context, task, n_targets | files on disk | **Change**: ranking split into two files at line ~1048 |
| `prediction_validity.py` (new) | Floor, repeated-split SD, permutation null, MDE | X, y, folds, seeds | dataclass of per-target stats | Pure; no I/O |

## Level 3: Constraints and Traps

**ADR §1.3 forbids hard-coding a model choice.** "HeatmapStage explores multiple prediction model
types and selects the best via Optuna cross-validation, rather than fixing a single model… This
avoids hard-coding a model choice that may not generalise across research questions." The reference
models here (`RidgeCV`, `KernelRidge`) are **diagnostic instruments, not the reported model**. They
never produce a prediction that reaches the user's results. This distinction must be explicit in the
code, the column names and the ADR entry, or the next reader will take it as a contradiction and
"fix" it. Recorded trap: ADR lines have previously been read as aspirational and cost three reverted
commits (`feedback_confirm_architecture_intent`).

**Do not reconstruct the CV folds in a second place.** `nested_optuna_cv` builds its own
`KFold(shuffle=True, random_state=...)` internally. Computing the floor from a *separately
constructed* `KFold` with the same seed gives the same answer today and silently diverges the day
someone changes one of them — and a floor computed on different folds than the score it is compared
against is worse than no floor. Return the indices from the one place they are made.

**The floor check and the pre-flight are one-directional evidence.** The model's score carries
selection inflation from its own max-over-trials; the mean predictor's carries none. So *failing* is
strong evidence and *passing* is weak. Never treat a pass as validation, in code or in wording.

**Silence must not look like success.** This project's recurring failure mode. A gate that drops
targets, a report that skips a step, a filter that skips a run — each must produce a visible,
counted, explained artefact. See the transparency contract in `plan.md` §4; it is a requirement,
not a nicety.

**Guardrails.** `lad:lad-standards` **G002** (never edit a test to match broken code), **G003**
(never skip a failing test to reach green), **G009** (never invent what real data looks like) apply
throughout. G009 is the live one here: every threshold in this feature is measured on `DSD_repro`
and must be cited as such, never rounded into a plausible-looking constant.
