# Disconnectome design audit — answers to four questions

_2026-08-26. Data: `~/Dropbox/EMUSE/DSD_repro/`, run `new_pred_pipeline_12-06-2026`._
_Scripts: `~/.claude/jobs/0d3a7417/tmp/{signal_check2,umap_signal,perm_test,embedding_quality,morphospace_pca}.py`_

---

## 1. How the R² numbers are calculated

Identical protocol to EMUSES' own, deliberately, so the numbers are comparable to
`performance_target_rankings_*.csv`.

**Per measure (target):**

1. Drop the rows where that measure is NaN. 33% of the score matrix is missing, median 45
   of 133 per measure, so effective n is 79–133 (median 88).
2. Split with `KFold(n_splits=5, shuffle=True, random_state=1859786276)` — the same
   splitter class and the same `cv_seed` from `random_seeds.json` that
   `optuna_cv.py:165` uses for the outer loop.
3. For each outer fold: fit on the other four fifths, predict the held-out fifth.
4. Score the held-out fifth with

   ```
   R² = 1 − Σ(y − ŷ)² / Σ(y − ȳ_test)²
   ```

   where **`ȳ_test` is the held-out fold's own mean** — sklearn's `r2_score` convention,
   which is what EMUSES gets via `scoring="r2"`.
5. Report the mean of the five fold scores. That is exactly EMUSES' `Mean_Score`.

**Model.** Ridge regression in dual form (kernel ridge with a linear kernel). With n≈88 and
p=902,629 the dual is both exact and cheap: everything runs off a 133×133 Gram matrix
`K = XXᵀ`. `alpha` is chosen by a *nested inner* 5-fold on the training part only, over 21
log-spaced values from 1e-4 to 1e6. No test data touches model selection.

PCA is likewise derived from the Gram matrix (with n≪p, PCA is an eigendecomposition of the
centred Gram). **That identity was verified against `sklearn.decomposition.PCA` to a relative
error of 1.5e-14 before any result was computed** — an unverified transform producing
plausible numbers is precisely the failure mode this codebase keeps paying for.

### The one thing that changes every interpretation

Because `SS_tot` uses the **test fold's** variance, **R² = 0 is not the right baseline.**

At n≈88 with 5-fold CV, a model that just predicts the training mean scores a *median of
−0.086* (mean −0.237), because each held-out fold's mean differs from the training mean by
chance. So:

| | mean R² | median R² |
|---|---|---|
| predict the training mean — **the real floor** | −0.237 | −0.086 |
| EMUSES, June run | −0.188 | −0.120 |

**EMUSES' `Overall_Mean_Performance = −0.1884` is not a catastrophic failure. It is
approximately the floor.** That is a different problem from the one it looks like, and it is
why every table in this document reports the floor alongside.

The same effect explains the pathological targets. ARAT measures (`larapinch`, `laragrasp`,
`raragrip`, `rarapinch`) are ceiling-bound — most patients score maximum — so a held-out fold
can have almost no variance and the floor collapses to −2.5 or worse. EMUSES ranked
`larapinch` **first** (0.221). It fails permutation testing. Anything that ranks targets by
raw R² will keep promoting these.

---

## 2. Has anything significant changed since the June run?

**No — nothing that changes what the method can do.** Five commits have touched the science
path since 2026-06-12 (out of 70 total):

| commit | what it does | affects results? |
|---|---|---|
| `687f7a9` | connect the prediction stage to derived seeds | numerically, not in kind |
| `4152635` | seed the estimators and PCA transformers in prediction | numerically, not in kind |
| `bec42c9` | make serial search the declared default | reproducibility only |
| `d23adc9` | let an unsupervised run run; refuse heatmap-only clearly | no |
| `b3d2054` | write held-out metrics for one-vs-rest runs (PR #10) | **reporting only** |

Two consequences worth stating plainly:

- **A re-run today would give different numbers but the same conclusion.** The seed commits
  fixed parts of the prediction path that were previously unseeded, so the June run was not
  reproducible in the first place. Nothing in that list improves predictive capability.
- **PR #10 changes what you can *see*, not what the model can do.** June used `--test_size 0.0`,
  so it produced no held-out evaluation at all. And at 87 targets the lexicographic ordering
  bug would have mis-paired 85 of them the moment a held-out set existed.

---

## 3. Could a "bad" UMAP explain these results?

This is the right question, and the answer is more interesting than yes or no: **the embedding
is geometrically excellent and predictively useless.** Those are not the same property.

### The UMAP is not broken

Trustworthiness of the 133 labelled subjects' coordinates against their true
902,629-dimensional neighbourhoods (1.0 = perfect neighbourhood preservation):

| embedding | k=5 | k=10 | k=20 |
|---|---|---|---|
| **June UMAP-2** (fitted on the 1333, `transform()`d) | **0.9605** | **0.9426** | **0.9230** |
| UMAP-2 refitted directly on these 133 (best case) | 0.9589 | 0.9625 | 0.9574 |
| PCA-2 | 0.8941 | 0.9063 | 0.9194 |

So: `transform()` is not degrading the labelled subjects — projecting them into the
morphospace is as faithful as fitting UMAP on them directly. And the UMAP preserves local
structure **better than PCA does**. The morphospace also has sensible cluster structure
(20 HDBSCAN clusters, 9.6% noise). By every geometric criterion the embedding is good.

### And yet PCA beats it decisively, at the same dimensionality

Apples-to-apples: every representation below is fitted on the **same 1333-subject
morphospace**, then the 133 labelled subjects are projected in — exactly what the UMAP does.
Same folds, same ridge, same alpha selection. Scored on the 11 permutation-validated measures.

| representation | measures with R² > 0 | median R² |
|---|---|---|
| **June UMAP-2** | **1 / 11** | **−0.028** |
| morphospace PCA-2 — *same 2 dimensions, linear* | **8 / 11** | +0.032 |
| morphospace PCA-5 | **10 / 11** | +0.049 |
| morphospace PCA-10 | 9 / 11 | +0.053 |
| morphospace PCA-20 | 8 / 11 | +0.056 |

**At identical dimensionality, on identical data, linear PCA finds signal in 8 of 11 measures
where UMAP finds it in 1.** Dimensionality is a second-order effect (PCA-2 → PCA-20 barely
moves); the embedding *method* is the first-order one.

### Why both can be true

UMAP's objective is neighbourhood membership — which points are near which — and it is
explicitly licensed to distort global and metric structure to achieve it. Trustworthiness
measures exactly what UMAP optimises, so a high score is close to tautological.

Predicting a continuous score from coordinates needs the opposite thing: that *distance and
direction* in the embedding map monotonically onto the outcome. UMAP does not promise that,
and here it does not deliver it. The information survives the projection to 2 linear
dimensions and does not survive the projection to 2 UMAP dimensions.

**This is not a bad fit that better hyperparameters would repair.** It is the method doing its
job. Re-running with more `umap_trials` will not change it — the composite score being
optimised (`eigen_spread`, `density_variability`, `entropy`) rewards a well-spread, well-clustered
map, and none of those terms has anything to do with predicting an outcome.

---

## 4. Is there a fundamental flaw in the design?

Short answer: **the premise is sound and the implementation is what is failing.** That is good
news, and it is a narrower problem than "the idea doesn't work".

### The premise survives its hardest test

The claim is that *complex disconnection patterns* carry information about cognition. The
obvious deflationary alternative is that any apparent signal is really just lesion burden —
bigger stroke, worse everything. Tested directly, using total disconnection load as a single
predictor:

| representation | measures with R² > 0 | median R² |
|---|---|---|
| total disconnection load (one number per subject) | **0 / 11** | −0.047 |
| morphospace PCA-5 (spatial pattern) | **10 / 11** | +0.049 |

**Lesion burden predicts nothing. Spatial pattern predicts something.** The premise is
supported: there is pattern information beyond lesion size, and it is what PCA-5 is picking
up. (This also refutes a hypothesis I raised earlier — that the SIP subscales were predictable
merely because they track global severity. They are not.)

### What the measurement does not support

The specific claim that this method does what other methods cannot. On this dataset a
**linear** PCA on the same morphospace outperforms the nonlinear embedding 10/11 vs 1/11. A
reviewer asking "did you compare against PCA?" is asking the question that breaks the paper,
and right now the honest answer goes the wrong way.

Framed fairly, there are two different products being conflated:

- **As an interpretable stratification map** — a 2-D space where patients cluster and effect
  sizes can be drawn back into brain space — 2-D is a deliberate, defensible choice. Talozzi
  et al. say so explicitly: a two-latent-variable configuration "was preferred to provide a
  more intuitive space facilitating clinically meaningful interpretation". PCA-5 gives you no
  such map.
- **As a predictor** — it loses to a linear baseline, and R² caps around 0.2 on the best
  measure.

The design is fine for the first and does not currently support a claim about the second.

### The comparison with the published numbers cannot be made directly

Talozzi et al. (Brain 2023) report their headline as *mean absolute error*: "average MAE of
16.1±7% across 83 neuropsychological measures; 65 scores (78%) predicted with MAE<20%".

**That figure and the R² values in this document are not comparable, for two reasons Chris
confirmed (2026-08-26):** the scores were not normalised, and no R² was computed because the
validation set (n=20) was too small to estimate one. So a like-for-like restatement of that
paper's result in R² does not exist, and the MAE percentages are not on the
range-normalised scale used here.

An earlier version of this document computed the MAE of a mean-predictor on the DSD_repro
scores (median 14.3% of range, clearing 20% on 65 of 87 measures) and presented it as
reproducing the published criterion. **That comparison was not valid** — different cohort,
different normalisation — and it is withdrawn.

What survives is narrower and still worth acting on: **MAE on bounded neuropsychological
scores is weakly sensitive to whether a model has learned anything**, because a
mean-predictor already achieves a low absolute error when the score range is small. Any
new claim from this pipeline should therefore be stated in cross-validated R² against the
mean-predictor floor, on a test set large enough to estimate it — which is exactly what the
n=20 validation set could not support, and what a larger cohort would fix.

The two R² values Talozzi et al. do report (0.201 semantic fluency, 0.1797 Bells Test) sit
in the same range as the best result measured here (`lpegs` 0.203–0.246).

### Constraints that are real but not flaws

- **n is the binding limit.** 133 labelled subjects, ~88 per measure after NaN removal, against
  87 outcomes. At that sample size R² ≈ 0.2 is close to the ceiling of what is estimable, and
  multiple-comparison burden across 87 measures is severe. Talozzi trained on 119. No modelling
  choice fixes this.
- **33% missing scores** is handled correctly (per-target row dropping,
  `heatmap_stage.py:72`), but it is what drives n down to ~88.
- **No masking**: `inputs_utils.py:207` keeps all 902,629 voxels though only 1.8% are nonzero,
  giving a 9.6 GB dense float64 matrix. That is a cost problem, not a correctness one.

---

---

## 5. Is ridge the best possible model? Does it capture interactions?

A fair challenge: the ridge used throughout is linear in whatever representation it is given.
If the scores depend on interactions among many imaging variables rather than a few additive
factors, a linear model cannot express that. Tested directly on morphospace PCA-10, EMUSES'
outer folds, 11 validated measures:

| model | measures with R² > 0 | median R² |
|---|---|---|
| **ridge** (linear) | **10 / 11** | **+0.073** |
| kernel ridge, RBF (all-order interactions) | 0 / 11 | −0.405 |
| random forest (300 trees) | 2 / 11 | −0.059 |
| gradient boosting | 1 / 11 | −0.169 |

**Every model that can express interactions does dramatically worse.** This is not evidence
that interactions are absent. It is the standard small-n result: with ~70 training subjects
per fold, a flexible model has enough freedom to fit noise, and cross-validation charges it
for that. Ridge wins because it is the most constrained thing on the list.

The literature shows the flip clearly. Benchmarking six algorithms for language outcome after
stroke (N=238 for Aphasia Quotient), random forest reached r=0.73±0.09 while linear
regression managed only r=0.24±0.21 — the opposite ordering to the one measured here, at
roughly three times the sample size. **So the answer is sample-size-dependent: at n≈88 ridge
is near the ceiling; at n≈250 it would probably not be.**

## 6. Would more data improve the results?

Yes, and this is the clearest result in the audit. Learning curve on morphospace PCA-10:
fixed 25% held out, 200 random draws per measure, training set grown from 20 to 60.

| n_train | 20 | 30 | 40 | 50 | 60 |
|---|---|---|---|---|---|
| mean R² | −0.219 | −0.063 | −0.015 | +0.011 | +0.033 |
| median R² | −0.204 | −0.074 | −0.020 | −0.005 | +0.015 |
| measures with R² > 0 | 1/11 | 2/11 | 4/11 | 5/11 | **7/11** |

**Every one of the 11 measures rises monotonically with n, and none has flattened at n=60.**
The curve is still climbing at the largest sample available.

Fitting the standard form `R²(n) = R²∞ − a/n` per measure to estimate where it levels off:

| measure | R² at n=60 | fitted ceiling | n for 90% of ceiling |
|---|---|---|---|
| lpegs | 0.252 | **0.368** | ~177 |
| sip_body | 0.120 | 0.301 | ~317 |
| sip_psychosoc | 0.114 | 0.263 | ~341 |
| rpegs | 0.073 | 0.208 | ~374 |
| sip_emo | 0.012 | 0.168 | ~488 |
| *(9 of 11 have a fitted ceiling above 0.1; 4 of 11 above 0.2)* | | | |

Extrapolating a curve fitted over n=20–60 is indicative, not a promise. But the direction is
unambiguous and the implied scale is actionable: **roughly 300–500 labelled subjects to
approach the ceiling, against 133 today.**

Two effects would compound at that sample size. The linear fits improve directly, *and*
nonlinear models become viable — which is where the largest published gains in this
literature come from. The interactions question and the sample-size question are the same
question.

### Is R² ≈ 0.2 worth publishing?

Calibration against the field, since "0.1 is pointless" is the right instinct but the bar
depends on the outcome:

- Lesion location and volume together are generally reported to account for **10–35% of
  variance** in motor and cognitive performance — so R² 0.10–0.35 is the established band.
- **Cognitive** outcomes are the hard end: one lesion-network study reports R² < 0.1 across
  all cognitive domains, and another is titled "improved accuracy yet still low deficit
  prediction".
- **Motor** outcomes are the easy end: thresholded structural disconnection maps reach
  R² ≈ 0.95 (left) and 0.69 (right) for motor deficits.

That the single best result here is `lpegs` — a pegboard, i.e. motor — fits that pattern
exactly. It also suggests where a strong result is most likely to be found: **the motor
measures, with enough subjects, are the defensible target**; 87 mixed neuropsych scores at
n=88 is the configuration least likely to produce a publishable effect.

One caveat worth carrying: prediction performance in independent datasets is consistently
*worse* than within-dataset cross-validation in this literature, so a held-out cohort should
be planned rather than assumed.

## What I would do next, in order

1. **Merge PR #10.** Prerequisite for any 87-target run that has a held-out set.
2. **Settle the MAE question** against Talozzi's exact protocol. It determines whether the
   target is "beat the published result" or "the published result needs restating".
3. **Add the linear baseline to the pipeline as a reported control.** PCA-k at matched
   dimensionality, every run. If UMAP cannot beat it, that needs to be visible immediately
   rather than discovered by a reviewer.
4. **Decide the embedding question** (STATUS 3c). The options are genuinely different:
   - keep 2-D UMAP for the map, use PCA-k or more components for prediction — two
     representations, one pipeline;
   - **supervised UMAP** (`umap.UMAP(...).fit(X, y=scores)`), which targets exactly the
     mismatch identified here. It must be fitted *inside* each CV fold or it leaks the outcome,
     and with 87 targets it means one embedding per target — expensive, and it gives up the
     single shared morphospace that makes the map interpretable;
   - accept 2-D as an interpretability choice and stop making predictive claims for it.
5. **Fix the ranking** so degenerate-floor targets cannot top it (STATUS 3d): report R²
   relative to the mean-predictor floor, and permutation-test before ranking.

## Sources

- Talozzi L, Forkel SJ, Pacella V, Nozais V, Allart E, Piscicelli C, Pérennou D, Tranel D,
  Boes A, Corbetta M, Nachev P, Thiebaut de Schotten M. *Latent disconnectome prediction of
  long-term cognitive-behavioural symptoms in stroke.* Brain 146(5):1963–1978, 2023.
  <https://academic.oup.com/brain/article/146/5/1963/7079039>
