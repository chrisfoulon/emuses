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

Those details, the mapping from the generic names below to the real variables, and the linkage
itself live in a **local companion folder outside the repository** on the analysis machine
(`$NEURO_DATA/BBS_emuses_local/`). If you need a detail that is not here, it is there, and it stays
there.

## 1. The question

Can EMUSES, given only 2 mm disconnectomes, predict post-stroke outcomes in BBS above chance, and do
its answers agree with what the disconnection–outcome literature reports for the same instruments?

Secondary: a first real cohort where a *null* result is readable. DSD_repro never allowed that.

## 2. Linkage: images to patients (verified 2026-09-16)

**The subject number in the image folder is the imaging-study number, not the clinical patient id.**
The two differ for most patients, and reading one as the other silently attaches every image to
the wrong person. An earlier export outside this project was mislinked exactly this way. A first
screening in this plan's own drafting made the same mistake, and every number from it is void.
The numbers below replace it.

The linkage used is the clinician-validated lookup maintained with the clinical database, not
anything derived from file names. It was checked independently on this folder's own lesion masks:

| reading | Spearman(mask volume, recorded infarct volume) |
|---|---|
| validated lookup | **+0.995** (331 subjects) |
| folder number read as patient id | +0.075 |

- 331 of 337 imaged subjects link; 6 have no entry in the source tables and are excluded.
- No patient is claimed by two images.
- Four identity collisions the clinical-database audit had left unresolved were checked against
  mask volume, and all four support the existing links.
- 9 subjects have mask volume more than 1.5× away from the recorded volume after scaling. They are
  exactly the clinical database's own verification list (its "check" and "flagged" rows, reviewed
  there), so **they stay in (Chris, 2026-09-16: the clinical database's lists are the source of
  truth)**.
- That verification file is older than the database's last two linkage fixes, so it still marks
  67 now-linked subjects as unresolved and carries one pre-fix identity swap. The fixes are
  right; the verification file is stale. Reported to that project rather than fixed here.
- Outcomes and clinical features join on the patient id. Among the 331: age and sex are present
  for all but a handful of patients, the minimal clinical tier (age, baseline NIHSS, infarct
  volume) is complete for 323, and the full clinical tier for 304.

## 3. Why BBS instead of DSD_repro (decided 2026-09-14)

DSD_repro (n≈88) is dropped entirely, not kept as a comparison.

| | DSD_repro | BBS |
|---|---|---|
| imaged subjects | ≈88 labelled | 331 linked |
| subjects per target | ≈88 | 192–327 across the outcome set in §4 |
| mean-predictor floor, 5-fold CV R² | median −0.086, worst −2.56 | −0.005 to −0.011, every candidate target |
| input grid | 91×109×91 @ 2 mm, 902,629 voxels, [0, 1] | identical |
| voxels nonzero (disconnectome, 25 subjects each) | 17–19 % | 16 % |

The floor row is the decision. At DSD_repro's n an R² had to be read against a floor that moved
per target by more than the effects did (`small_sample_prediction_validity.md`). On BBS the floor
is at zero to two decimals, so R² can be read at face value. Grid and density match, so there is
no preprocessing change and no domain shift to argue about.

**Indicative detection limit.** Simulated power for a *fixed* ridge on 5-fold CV with a
permutation test (400 repetitions, 499 permutations, 80 % power):

| n | 88 | 151 | 225 | 269 | 337 |
|---|---|---|---|---|---|
| smallest detectable R² | 0.13 | 0.09 | 0.06 | 0.06 | 0.04 |

Two limits on this table. It is simulated, and STATUS 3i settled that the MDE EMUSES *reports*
must be measured on real y (`null_p95 + 0.84 × SD`). And it is for a fixed model: at n≈88 the full
search roughly doubled the measured MDE (0.096 → 0.176, `external_evidence_dsd.md`). Expect
EMUSES as it runs today to need true R² near 0.1 at n≈250.

## 4. Scope of the first run: few targets, because the method is not yet trusted

**Decided 2026-09-16 (Chris): the size of the first run depends on whether EMUSES's numbers are
trusted.** If they were, the whole outcome set could run. They are not yet, for reasons that are
recorded rather than suspected:

- **Prediction scores** are verified on a synthetic target that is recoverable by construction
  (swiss roll, R² 0.999) and **never on a real positive control**. The per-fold search is known to
  inflate and destabilise scores at small n (seed spread 0.080 at n≈88, STATUS 3f/3g). Floor,
  permutation p and measured MDE are not in the pipeline (STATUS 3h/3i).
- **Maps** are not trusted at all: region selection still uses the percentile rule item 00b
  replaces, local-linear boundary correction is optional and unbuilt, and PR #19's coordinate and
  shrinkage fixes are not merged.

So run 0 tests the method, not the cohort: **two targets with documented disconnection effects,
one known-positive control and one known-negative control.** A methodological mistake shows up as
a failed positive control, a "significant" negative control, or a literature target far off its
published range. Twelve extra targets would add nothing to that diagnosis and would multiply the
cost of chasing it.

| role | outcome | n | literature anchor (from the project's literature review) |
|---|---|---|---|
| target | **Isaacs set test (semantic category fluency), 3 months** | 282 | normative disconnectomes predicted semantic fluency at r = 0.41 (R² ≈ 0.17), 5-fold CV, n = 1231, ~107 days; latent disconnectome components reached external R² ≈ 0.20 at 1 year |
| target | **Fugl-Meyer motor, 12 months** | 244 | lesion-network features improved 12-month motor prediction beyond direct lesion mapping (external validation, increment not reported); normative CST disconnection vs Fugl-Meyer upper extremity r ≈ −0.50 in chronic stroke (n = 166), with a warning about zero-overlap subjects |
| positive control | **NIHSS, acute** | 323 | structural disconnection R² = 0.29 ([Sperber et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC11756379/), n = 685); disconnection external R² 0.16–0.24 in large cohorts |
| negative control | **HADS depression, 3 months** | 278 | location and network effects weak and unstable; the review treats mood as the negative control |

Notes on the choice:

- **Timepoints follow the literature**, not convenience. The fluency evidence is at ~3.5 months and
  the motor evidence at 12 months/chronic. The same instrument at 3 and 12 months correlates
  r = 0.86–0.90 (Isaac 0.89, FM motor 0.90), so the other timepoint is mostly a repeat measurement,
  not a second question. It is a cheap follow-up once the pair works, not part of run 0.
- **Fugl-Meyer motor is ceiling-heavy** (30 % at maximum). The deficit signal sits in a minority,
  which penalises R². That is the literature's instrument, so it stays, but a weak R² here is less
  surprising than on Isaac.
- **Acute NIHSS is concurrent with imaging.** Success validates the instrument, not a clinical
  claim. If it fails, nothing else in the run is interpretable.
- **Change scores (12 m − 3 m) are not proposed.** With test–retest r ≈ 0.9, a difference score
  keeps mostly measurement noise.
- The positive control may still miss for search reasons: Sperber's figure used richer features
  than two UMAP coordinates. The fixed-model reference (C2) separates "no signal in 2-D" from "the
  search lost it".

### Pre-stated expectations

- NIHSS acute: clearly above the floor and permutation-significant. Failure stops interpretation.
- Isaac 3 m: positive, plausibly R² 0.05–0.15. The literature's 0.17 used full voxelwise SVR.
- FM motor 12 m: positive but possibly weak, given the ceiling.
- HADS-D 3 m: at the floor, not permutation-significant. A "significant" result means an artefact.

### The outcome set held back for later (after run 0 validates the method)

Screened on the verified linkage. Kept here so the choice is visible.

| family | timepoints | n range | usable? |
|---|---|---|---|
| NIHSS | acute, 3 m, 12 m | 252–323 | acute and 3 m; 12 m is 45 % at mode |
| mRS | 3 m, 6 m, 12 m | 218–327 | yes. Two 3-month derivations exist; the one that includes deaths ascertained without a visit is the right default for anything mortality-sensitive |
| Fugl-Meyer total / motor | acute, 3 m, 12 m | 244–307 | yes (motor 30 % at maximum from 3 m) |
| MoCA total | acute, 3 m, 12 m | 241–277 | yes |
| MoCA visuospatial, delayed recall | acute, 3 m, 12 m | 241–277 | yes (23–39 % at mode) |
| MoCA attention | acute, 3 m, 12 m | 241–277 | borderline (42–48 % at mode) |
| MoCA naming, orientation, abstraction, language | all | 241–277 | no: ceiling, 46–86 % at mode |
| Isaacs set test | acute, 3 m, 12 m | 244–282 | yes |
| HADS anxiety / depression | acute, 3 m, 6 m, 12 m | 192–278 | yes |
| TICS (telephone cognitive screen) | 6 m | 242 | yes |
| IADL | acute, 3 m, 12 m | 250–287 | no: over 90 % at mode acutely, 67–71 % later |
| Apathy scale | 3 m | 279 | no: 58 % at mode |

When that run happens, fix its target list before seeing results, and keep it well under the ~75
entries the registry holds. DSD_repro at 87 targets gave rankings that did not reproduce across
sampler seeds (STATUS 3f).

## 5. Run 0: classic EMUSES, disconnectomes only

- **Mode: single dataset, morphospace trained once, reused by `--load_umap`** (changed from dual
  mode after B10). `emuses umap <morphospace> <file list> --test_size 0.2 --random_state S` splits
  the 331 linked disconnectomes and trains UMAP on the 80 %. Every later
  `emuses full <run> <same file list> --scores <labels> --load_umap <morphospace>` with the same
  seed and test size reproduces that split, loads the model instead of training, and reuses the
  recorded scaling and cluster labels. The held-out 20 % never enter the UMAP fit: inductive,
  stricter than dual mode, where they shape the morphospace. Checked on public data (B10):
  training coordinates, cluster labels, scaling and split byte-identical across the morphospace
  folder and two runs with different targets; test coordinates equal to 6.6e-8.
- **The file list must be identical in both commands.** The split is taken over the files the run
  sees, so a different set (the 6 unlinked images, or `--filter_labelled_by_scores` dropping rows)
  gives a different split, and held-out subjects may then have been in the UMAP fit. Nothing
  stops the run: it logs that the morphospace "was built on a different cohort (feature digest
  differs)" and re-derives cluster labels only. Pass the same explicit list of 331 paths
  (`--input_file_list`) to both, keep all 331 rows in the labels CSV with NaN for missing
  outcomes, and treat that log line as a failed run.
- **In single-dataset mode labels are aligned to files by row order.** The ID filter
  (`--filter_labelled_by_scores`, substring match) only runs on a label dataset, so nothing checks
  that row *i* of the labels is the subject of file *i*. Write the file list and the labels CSV
  from the same linkage table in one script, and assert the order there, per row, before the run.
- Each target is fitted on its own non-NaN subjects; `_optimise_target` already filters NaN rows
  per target (`heatmap_stage.py`).
- **Where:** the lab compute node (72 cores, 125 GB RAM). Code cloned from the public repository;
  only the 331 disconnectome volumes and the labels CSV copied there, outside any synced folder.
- **Inputs:** disconnectomes only. No clinical covariates (§7).
- **Labels:** one CSV, one row per linked subject, four target columns, built locally **through
  the validated lookup**, never by reading the folder number as a patient id. Its index must be
  the full subject string, not a bare number (substring-matching trap, `dev-docs/traps.md`).
- **Flags that matter:** `--input_file_list` (same list in both commands), `--scores_header`,
  `--scores_index_column`, `--random_state` fixed and recorded, `--test_size` (B2), the same
  `--optim_dict` in both. **Never `--record_cohort_ids`.**
- **Output folder outside the repository** (companion folder). It holds the training matrix inside
  the UMAP model and per-subject predictions. It is not shareable (see traps).
- **What to read from it:** per-target CV R² against the floor, then permutation p, compared with
  the pre-stated expectations. **Not the effect-size maps** (B1, D2).

## 6. Checklist: what has to be built or decided

Grouped by when it blocks. Tick here, and mirror the state in STATUS.md.

### Before run 0

- [x] **A0** Linkage verified on this folder (§2).
- [x] **A1** The four run-0 outcomes in §4 — confirmed by Chris, 2026-09-16.
- [x] **B1** Merge PR #19 (isotropic rescale, real confidence, shrinkage toward the null,
      `HeatmapIntegrityError`). Local `--core` passed 17/17 and CI passed; merged 2026-09-16.
- [x] **B2** `--test_size 0.2` — confirmed by Chris, 2026-09-16. Costs ~50 subjects per target and
      gives the held-out check June lacked.
- [ ] **B8** Morphospace search space. Chris asked for `optim_dict_hard`, remembered as tuned for
      noisier problems. In the code it is nearly `optim_dict_default` and has been since it was
      created (March 2025), with a *coarser* `n_neighbors` grid (5/25/45 only).
      `optim_dict_disconnectome` is the dict written for this data (`n_neighbors` 15–50
      continuous, `min_cluster_size` 15–100). *Recommendation: disconnectome.* Chris decides.
- [x] **B10** Reuse path exercised on `swiss_roll` (2026-09-16), single-dataset mode: `emuses umap`,
      then `emuses full --load_umap` with two different targets. No retraining, same
      `cohort.json` digest, identical coordinates, labels and split (§5). Perturbation (10 rows of
      the features shifted): the model is still loaded and the run exits 0; only the digest
      warning and re-derived cluster labels show it. Hence the file-list rule in §5.
- [ ] **B9** Trial budget for the morphospace search: time a few trials on the compute node first,
      then set the number from the measured cost. Seeded UMAP runs single-threaded (traps.md), so
      the cores do not shorten a trial.
- [ ] **B3** Floor, permutation p and measured MDE: computed **alongside** run 0 by a local script
      on the saved embedding (agreed 2026-09-16), then built into the core pipeline (§6, "Core").
- [ ] **B5** Build the file list and the labels CSV locally from the linkage table, in one script,
      same row order asserted per row (§5). Perturb it: a shuffled labels file must fail the
      assertion. Check the run logs 331 subjects and no "different cohort" line.
- [ ] **B6** Fix the data naming: the 2 mm files carry a resolution tag that says 1 mm, and their
      names are identical to the 1 mm directory's. Data-side, not code.
- [x] **B7** The 9 volume outliers (§2): kept, per the clinical database's own lists.

### Alongside run 0

- [ ] **C1** Per target: floor, CV R², lift, permutation p, **measured** MDE (real y, repeated
      splits).
- [ ] **C2** Fixed-model reference (ridge and RBF kernel ridge) on the same embedding and folds.
- [ ] **C3** Spread across at least two sampler seeds for any target that clears its floor.
- [ ] **C4** Record wall-clock and peak RSS.

### After run 0

- [ ] **D1** Compare against §4's pre-stated expectations before any interpretation. If the
      controls behave, widen to the held-back outcome set. If not, the run has found the
      methodological problem to chase, and nothing else runs until it is found.
- [ ] **D2** Build item 00b before reading any effect-size map from BBS.
- [ ] **D3** Feature-space support check for new subjects (flagged for BBS in
      `heatmaps_clusters_and_effect_size_maps.md`, C-section on soft clustering).
- [ ] **D4** Write the result here in aggregate form and update STATUS.md.

### Core: validity reporting in the pipeline

The local script in B3 is scaffolding, not the destination. Phases 1–2 of
`dev-docs/analysis-api/prediction-validity-reporting/plan.md` (floor in the output; pre-flight
report with fixed references, permutation p, measured MDE) are designed as pipeline defaults, and
run 0 is the second real dataset that plan asks for.

- [ ] **F1** Implement phases 1–2 in core.
- [ ] **F2** Cross-check the in-pipeline numbers against the B3 script on BBS, locally. They must
      agree within the permutation's Monte Carlo error before the script is retired.
- [ ] **F3** The committed tests use public data only (swiss roll, digits). BBS numbers are a
      local cross-check and never become baselines.

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
- **Scientific reason to want it:** later outcomes are driven largely by lesion-independent
  factors. The literature review's required test is nested: clinical baseline → + lesion volume →
  + direct lesion overlap → + disconnectome, under identical resampling, reporting the held-out
  difference. The clinical tiers are available for 304–323 of the 331 (§2).
- [ ] **E1** Design note: the grid semantics with covariates, decided jointly with N-D.
- [ ] **E2** Implementation, after run 0 has established what disconnectomes alone give.

## 7. Settled here, do not re-open

- DSD_repro is not used, not even as a comparison (Chris, 2026-09-14).
- The first run is two literature targets plus one positive and one negative control, because the
  method is not yet trusted (Chris, 2026-09-16). The full outcome set waits for D1.
- Linkage goes through the validated lookup, never through folder numbers (§2).
- No UMAP dimensionality change for this run (`external_evidence_dsd.md` §7.2).
- No automated target filtering or halting on the floor/MDE (STATUS 3g).
- Target lists are fixed before results are seen.
