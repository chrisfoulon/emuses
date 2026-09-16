# BBS disconnectome run — plan, decisions, and what has to exist first

_Opened 2026-09-16. Owner of the decisions: Chris. Supersedes the DSD_repro re-run (STATUS 3e)._

## Read this first: this file is public, BBS is not

The repository is public and BBS cannot be shared. This document explains choices **in terms of
what BBS makes available, at aggregate level only**. It must never contain, and nor may commits,
PR bodies, issues, logs pasted into any of them, figures, test data or baselines:

- subject identifiers, file names or paths from the BBS directories, or anything per subject
  (values, coordinates, cluster labels, predictions, scatter plots of subjects);
- BBS source table names, column names, visit codes or registry keys;
- dates, sites, demographics, or any count small enough to single someone out. Aggregates here are
  over ≥150 subjects; a proportion whose complement would be under ~10 subjects is written as a
  bound ("over 90 %"), not a number.

Those details, and the mapping from the generic names below to the real variables, live in a
**local companion folder outside the repository** on the analysis machine
(`$NEURO_DATA/BBS_emuses_local/`). If you need a detail that is not here, it is there, and it stays
there.

## 1. The question

Can EMUSES, given only 2 mm disconnectomes, predict post-stroke outcomes in BBS above chance, and do
its answers agree with what the disconnection–outcome literature reports for the same instruments?

Secondary: a first real cohort where a *null* result is readable. DSD_repro never allowed that.

## 2. Why BBS instead of DSD_repro (decided 2026-09-14)

DSD_repro (n≈88) is dropped entirely, not kept as a comparison.

| | DSD_repro | BBS |
|---|---|---|
| imaged subjects | ≈88 | 337 |
| subjects per target | ≈88 | 196–271 (targets in §4) |
| mean-predictor floor, 5-fold CV R² | median −0.086, worst −2.56 | −0.007 to −0.014, every target |
| input grid | 91×109×91 @ 2 mm, 902,629 voxels, [0, 1] | identical |
| voxels nonzero (disconnectome, 25 subjects each) | 17–19 % | 16 % |

The floor row is the decision. At DSD_repro's n an R² had to be read against a floor that moved
per target by more than the effects did (`small_sample_prediction_validity.md`). On BBS the floor
is at zero to two decimals for every target, so R² can be read at face value. Grid and density
match, so there is no preprocessing change and no domain shift to argue about.

**Indicative detection limit.** Simulated power for a *fixed* ridge on 5-fold CV with a
permutation test (400 repetitions, 499 permutations, 80 % power):

| n | 88 | 151 | 225 | 269 | 337 |
|---|---|---|---|---|---|
| smallest detectable R² | 0.13 | 0.09 | 0.06 | 0.06 | 0.04 |

Two limits on this table. It is simulated, and STATUS 3i settled that the MDE EMUSES *reports*
must be measured on real y (`null_p95 + 0.84 × SD`) — that measurement is an item in §6. And it is
for a fixed model: at n≈88 the full search roughly doubled the measured MDE (0.096 → 0.176,
`external_evidence_dsd.md`). Expect EMUSES as it runs today to need true R² nearer 0.1 at n≈225.

## 3. Literature anchors, and what we expect before running

| outcome | published result | source |
|---|---|---|
| acute stroke severity (NIHSS) from structural disconnection | R² = 0.29 (lesion topography 0.41), n = 685 | [Sperber et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC11756379/) |
| NIHSS at 3 months from disconnection | R² ≈ 0 | same |
| mRS at 3 months | 59.9 % accuracy, near chance | same |
| prediction from the published 2-D DSD morphospace, independent cohort | R = 0.31 out of sample (R² ≈ 0.10), n = 314 | Hope et al. 2024; outcome and details in `external_evidence_dsd.md` |
| post-stroke cognition from lesion/disconnection | no single figure carried over; references for the cognitive targets | [Kolskår et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC9392540/), [Stroke 2023](https://www.ahajournals.org/doi/10.1161/STROKEAHA.122.042127) |

**Stated before the run:**

- **Acute NIHSS is the positive control.** It is concurrent with imaging, so success validates the
  instrument rather than producing a clinical finding. If it fails, the run says nothing about the
  other targets.
- **3-month NIHSS and 3-month mRS are expected near zero.** A null there, with a positive acute
  NIHSS in the same run, replicates Sperber et al. It is not a failure.
- **Mood (HADS) is expected weak.** No strong prior for a lesion-only signal.
- The positive control may still miss: Sperber's 0.29 used far richer features than two UMAP
  coordinates, and Hope's 2-D result (R² ≈ 0.10) sits near the full-search MDE. That is why the
  fixed-model reference in §6 matters. It separates "no signal in 2-D" from "the search lost it".

## 4. Outcomes

### Available in BBS, and what was done with each

| family | timepoints | n range | decision |
|---|---|---|---|
| NIHSS | acute, 3 m, 12 m | 206–269 | **include** acute (positive control) and 3 m (pre-stated null). 12 m is 45 % at mode: excluded |
| mRS | 3 m, 6 m, 12 m | 205–271 | **include** 3 m and 12 m. Two 3-month derivations exist (B4) |
| Fugl-Meyer total | acute, 3 m, 12 m | 151–258 | **include** acute and 3 m |
| Fugl-Meyer motor subscale | acute, 3 m, 12 m | 198–228 | exclude: 28–29 % at mode at 3 m/12 m; the total carries it with less inflation |
| MoCA total | acute, 3 m, 12 m | 151–225 | **include** acute and 3 m |
| MoCA visuospatial, delayed recall | acute, 3 m, 12 m | 151–225 | **include** 3 m (23–38 % at mode, usable) |
| MoCA attention | acute, 3 m | 221–225 | exclude: 44–45 % at mode, borderline |
| MoCA naming, orientation, abstraction, language | all | — | exclude: ceiling, 45–88 % at mode |
| Isaacs set test | acute, 3 m, 12 m | 150–230 | **include** acute and 3 m |
| HADS anxiety / depression | acute, 3 m, 6 m, 12 m | 185–226 | **include** 3 m |
| TICS (telephone cognitive screen) | 6 m | 202 | **include**: clean distribution, not on the original list |
| IADL | acute, 3 m, 12 m | 229–234 | exclude: ceiling, over 90 % at mode acutely and 68–71 % later |
| Apathy scale | 3 m | 225 | exclude: 56 % at mode |

All included targets have floors between −0.007 and −0.011 and at most 37 % at mode.

### Proposed target list — 15, fixed before the run (A1)

Acute: NIHSS, Fugl-Meyer total, MoCA total, Isaacs.
3 months: mRS, NIHSS, Fugl-Meyer total, Isaacs, MoCA total, MoCA visuospatial, MoCA delayed
recall, HADS anxiety, HADS depression.
Later: TICS 6 m, mRS 12 m.

**Why 15 and not the ~75 the registry holds.** DSD_repro at 87 targets gave rankings that did not
reproduce across sampler seeds (STATUS 3f). With floors near zero, multiplicity takes over as the
main source of false positives. Every target added costs power in the correction, and choosing
the list after seeing results is the selective reporting STATUS 3f warns against.

## 5. Run 0: classic EMUSES, disconnectomes only

- **Mode:** single dataset. UMAP and HDBSCAN on all 337 disconnectomes (unsupervised, so subjects
  with missing outcomes still help shape the morphospace). Each target is fitted on its own non-NaN
  subjects; `_optimise_target` already filters NaN rows per target (`heatmap_stage.py`).
- **Inputs:** disconnectomes only. No clinical covariates (§7).
- **Labels:** one CSV, one row per imaged subject, one column per target, built locally. **Its
  index must be the full subject string, not a bare number**: see the substring-matching trap in
  `dev-docs/traps.md`.
- **Flags that matter:** `--filter_labelled_by_scores`, `--scores_index_column`,
  `--scores_column` (15 values), `--random_state` fixed and recorded, `--test_size` (B2).
  **Never `--record_cohort_ids`.**
- **Output folder outside the repository** (companion folder). It holds the training matrix inside
  the UMAP model and per-subject predictions. It is not shareable (see traps).
- **What to read from it:** per-target CV R² against the floor, then permutation p. **Not the
  effect-size maps**: region selection still uses the percentile rule item 00b replaces (B1).

## 6. Checklist: what has to be built or decided

Grouped by when it blocks. Tick here, and mirror the state in STATUS.md.

### Before run 0

- [ ] **A1** Chris confirms the target list in §4 (add/drop, then freeze).
- [ ] **B1** Merge PR #19 (isotropic rescale, real confidence, shrinkage toward the null,
      `HeatmapIntegrityError`). A run from before it builds maps with defects already measured.
- [ ] **B2** Decide `--test_size`. 0.0 keeps n (MDE ≈0.06 fixed-model at n≈225) and gives no
      held-out check, the June mistake. 0.2 costs ~45 subjects per target (MDE ≈0.08) and gives
      one. *Recommendation: 0.2.*
- [ ] **B3** Decide whether phases 1–2 of `dev-docs/analysis-api/prediction-validity-reporting/`
      (floor in the output; pre-flight report with fixed ridge/kernel references, permutation p,
      measured MDE) land **before** run 0 or are computed alongside it by a local script on the
      saved embedding. *Recommendation: alongside.* Run 0 then becomes the second dataset that
      plan asks for before phase 3's filter can be trusted.
- [ ] **B4** Which 3-month mRS derivation. The two differ by 14 subjects and the difference in
      definition has not been checked.
- [ ] **B5** Build the labels CSV locally, with full subject strings, and verify the pipeline
      matched all 337 files, with no "multiple valid ID matches" warnings. Perturb it: a
      deliberately bare-number index must visibly fail.
- [ ] **B6** Fix the data naming: the 2 mm files carry a resolution tag that says 1 mm, and their
      names are identical to the 1 mm directory's. Data-side, not code. The same tag is what makes
      B5's bare-number index dangerous.

### Alongside run 0

- [ ] **C1** Per target: floor, CV R², lift, permutation p with BH across the 15, and **measured**
      MDE (real y, repeated splits). Local script if B3 says so.
- [ ] **C2** Fixed-model reference (ridge and RBF kernel ridge) on the same embedding and folds.
      This separates "the morphospace has no signal" from "the search lost it" (§3).
- [ ] **C3** Spread across at least two sampler seeds for any target that clears its floor
      (STATUS 3f). A pass on one seed is weak evidence (STATUS 3g).
- [ ] **C4** Record wall-clock and peak RSS. DSD_repro's 19 h / 9.6 GB was 87 targets at n≈88; no
      estimate for 15 targets at 337 has been measured.

### After run 0

- [ ] **D1** Compare against §3's pre-stated expectations, target by target, before any
      interpretation.
- [ ] **D2** Build item 00b (threshold observed scores; permutation as a global gate; cluster
      after thresholding) before reading any effect-size map from BBS.
- [ ] **D3** Feature-space support check for new subjects (flagged for BBS in
      `heatmaps_clusters_and_effect_size_maps.md`, C-section on soft clustering).
- [ ] **D4** Write the result here in aggregate form and update STATUS.md.

### Later: clinical features as model input (not built)

Confirmed absent: predictors receive the two embedding coordinates only
(`heatmap_stage.py`, `prediction_X = prediction_train_coords`, shape `(n_samples, 2)`).

- **Before UMAP** (concatenate onto the voxel features): possible with no code change, and useless.
  Ten columns next to 902,629 voxels do not move the neighbourhood graph.
- **After UMAP** (concatenate onto `prediction_X`): the right place. It collides with the heatmap,
  which evaluates predictors on a 2-D grid. With extra columns the value at a pixel is undefined
  until someone decides what the extra columns hold there (cohort mean? marginalised? one map per
  stratum?). This is the same design question the N-D gate raises (STATUS 3c) and should be
  settled once for both.
- **Scientific reason to want it:** 3-month outcomes are driven largely by lesion-independent
  factors (Sperber et al.'s explanation of their R² ≈ 0). Lesion-plus-baseline-severity is the
  model that could beat that, and the literature has comparisons for it.
- [ ] **E1** Design note: the grid semantics with covariates, decided jointly with N-D.
- [ ] **E2** Implementation, after run 0 has established what disconnectomes alone give. That
      result is the baseline any covariate model has to beat.

## 7. Settled here, do not re-open

- DSD_repro is not used, not even as a comparison (Chris, 2026-09-14).
- No UMAP dimensionality change for this run (`external_evidence_dsd.md` §7.2).
- No automated target filtering or halting on the floor/MDE (STATUS 3g).
- Target list fixed before results are seen.
