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

---

## 7. Does the disconnection PATTERN add anything over lesion VOLUME?

The question that matters for the project's premise, and the one Chris cannot get a positive
answer to on a different cohort (where percentage-damage-per-structure adds nothing over age,
NIHSS and stroke volume).

DSD_repro has no age or NIHSS, but it has the raw lesion masks, so true lesion volume is
available. Subject ordering was recovered by fingerprinting each matrix row's disconnection
load against the source files — all 133 matched uniquely, and the recovered mapping gives
`corr(lesion volume, disconnection load) = 0.766`, which is the check that it is right.

11 permutation-validated measures, EMUSES' folds, `RidgeCV`, all features standardised:

| representation | measures R² > 0 | median R² |
|---|---|---|
| lesion volume alone (+log) | 2 / 11 | −0.052 |
| disconnection load alone | 5 / 11 | −0.016 |
| volume + load | 4 / 11 | −0.032 |
| **disconnection PATTERN (morphospace PCA-10)** | **8 / 11** | **+0.058** |
| volume + pattern | 9 / 11 | +0.044 |

**Spatial pattern beats volume-only, and volume adds essentially nothing once pattern is
present.** On this dataset the imaging location information is doing real work — which is the
opposite of the null result Chris gets from atlas-percentage features against clinical
variables elsewhere.

Two honest qualifications. The effect is small (median R² +0.058, best 0.25), and across all
87 measures the picture is much thinner: pattern 10/87 above zero against volume's 4/87. And
this comparison has no clinical variables in it — a disconnectome that beats lesion volume
has not been shown to beat age and NIHSS, which is the harder and more relevant bar.

## 8. Correction: the UMAP-vs-PCA gap was overstated

Section 3 reported the June UMAP finding signal in **1 of 11** validated measures against
morphospace PCA-2's 8. That figure came from a custom dual-form ridge with a fixed alpha
grid. Re-run with a standard `RidgeCV`, on the same morphospace, same folds, same measures:

| representation | measures R² > 0 (of 11) | median R² | across all 87 |
|---|---|---|---|
| June UMAP-2, raw coordinates | 6 / 11 | +0.005 | 7/87 |
| June UMAP-2, standardised | 6 / 11 | +0.013 | 7/87 |
| morphospace PCA-2, standardised | **9 / 11** | +0.037 | 10/87 |
| morphospace PCA-10, standardised | 8 / 11 | **+0.058** | 10/87 |

Standardisation is not the cause — raw and z-scored UMAP agree. The estimator is.

**PCA still beats UMAP at matched dimensionality, but by a modest margin, not the 8-to-1
collapse first reported.** The direction of every conclusion above is unchanged; the strength
is not. Any claim resting on the 1/11 figure should be restated with these numbers.

## 9. The bigger loss is the per-fold model search, not the embedding

Sections 3 and 8 attributed EMUSES' weakness to the 2-D embedding. Splitting the gap shows
that is the smaller half. On the 11 validated measures, all on EMUSES' own folds:

| | measures R² > 0 | median R² |
|---|---|---|
| EMUSES June, as it actually ran | 1 / 11 | −0.069 |
| plain `RidgeCV` on EMUSES' **own** UMAP-2 coordinates | 6 / 11 | +0.013 |
| plain `RidgeCV` on morphospace PCA-10 | 8 / 11 | +0.058 |

Swapping the embedding is worth 2 measures. Swapping the *predictor*, on coordinates EMUSES
already computed, is worth 5. **The prediction stage is losing more than the embedding is.**

The mechanism is visible in the saved pipelines. EMUSES re-searches the feature union
(`raw`/`gwd`/`corr`/`pca`/`kpca`/`poly`) and the estimator hyperparameters independently
inside each outer fold. Across all 87 targets × 5 folds:

- **0 of 87 targets have all five folds agree** on a feature-union + estimator combination.
- **79 of 87 produce 4 or 5 distinct configurations** out of 5 folds.
- Selected ElasticNet `alpha` ranges from 0.004 to 9.8 *between folds of the same target*.

At ~70 training subjects per fold, that search space is far larger than the data can resolve.

One qualification that keeps this honest. Across all 87 measures EMUSES (8/87 above zero,
median −0.120) and `RidgeCV` on its coordinates (7/87, median −0.094) are comparable. The
difference is concentrated in the measures that carry real signal, which is what one would
expect: on a noise target every method scores about the same, and only on a signal target does
an unstable selection fail to exploit what a stable estimator captures.

### 9a. It is the *breadth* of the space, not the amount of searching

The paragraph above originally claimed the inner search overfits, so more trials would make
things worse. **Measured, that is wrong.** Replaying EMUSES' own space, objective, folds and
coordinates while varying only the trial budget (TPE is sequential, so the first k trials of a
120-trial study are a k-trial study):

| trials | inner CV (believed) | outer fold (truth) | gap | measures > 0 |
|---|---|---|---|---|
| 1 | −0.361 | −0.379 | 0.018 | 0/11 |
| 5 | −0.079 | −0.075 | −0.004 | 1/11 |
| 10 | −0.064 | −0.055 | −0.009 | 3/11 |
| 30 | −0.035 | −0.025 | −0.010 | 5/11 |
| **60** (June's setting) | −0.022 | −0.010 | −0.012 | 6/11 |
| 120 | −0.015 | −0.005 | −0.010 | 6/11 |

More trials help monotonically, and the inner/outer gap stays flat at ~0.01 rather than
widening — so the search is **not** overfitting its inner CV. What more trials buy, though, is
only a return to the floor: at 120 trials the mean is −0.005, while a fixed `RidgeCV` on the
same coordinates is already at +0.019 with no search at all.

**Narrowing the space is what actually works.** Five independent draws of the whole nested
search at June's 60 trials, full space versus one feature recipe and one estimator family
(`raw_only` + ElasticNet):

| configuration | measures > 0 | mean R² | spread over 5 draws |
|---|---|---|---|
| June, as it actually ran | 1 / 11 | −0.072 | (single draw) |
| full space, 60 trials | 2–5 / 11 | −0.004 to −0.028 | mean range 0.024 |
| **`raw_only` + ElasticNet, 60 trials** | **7 / 11, every draw** | **+0.020 to +0.024** | **mean range 0.004** |
| fixed `RidgeCV`, no search | 6 / 11 | +0.019 | — |

Restricting the space beats both the full search and the fixed ridge, and it is *stable*:
7/11 on every seed, mean varying by 0.004. The full space is what injects the variance —
median per-target range across draws **0.080**, comparable to the size of the effects being
measured (0.05–0.15).

### 9b. June sits outside the range of the procedure that produced it

June scored worse than all five draws (worst draw −0.028, 2/11; June −0.072, 1/11), and two
of its targets are far outside anything reproduced: `sip_house` −0.344 against a draw range of
−0.062 to −0.021, `pos_acc_disengage` −0.240 against −0.062 to −0.043.

This is not a data or fold difference. Non-NaN counts and fold sizes match June exactly
(target_77 n=86, fold-0 train 68; target_43 n=88, train 70), and the coordinates match the
ones stored inside June's own fitted `GWD` transformers to **1.6e-07** across 206 checked
points. The divergence is in the Optuna trajectory: June's sampler seeds could not be
reproduced from the recorded configuration, so June is one unreproduced draw among many.
**Its per-target ranking should not be read as a result** — which is a sufficient explanation
for `larapinch` landing at #1 without invoking the degenerate-floor argument of §4.

**This is the most actionable finding in this document**, because unlike sample size it costs
nothing: narrow `optim_dict_predict` to one feature recipe and one estimator, and re-run. No
new subjects, no architecture change. Whether it composes with the PCA-10 representation of §7
(8/11, +0.058) is untested — the two fixes are independent, so it is worth trying together.

### 9c. The ranking under `raw_only` + ElasticNet

All 87 measures, mean of 3 independent draws, EMUSES' own coordinates and folds.
`floor` is the mean-predictor baseline for that measure's own n and folds; `q` is the
BH-corrected permutation q-value from the 1000-permutation test. Full table:
`~/.claude/jobs/0d3a7417/tmp/rank_raw_elastic.csv`.

| # | measure | n | R² | spread | floor | q |
|---|---|---|---|---|---|---|
| 1 | `rarapinch` | 93 | 0.144 | 0.011 | −0.026 | **0.017** |
| 2 | `lpegs` | 87 | 0.144 | 0.016 | −0.092 | **0.017** |
| 3 | `lshflex` | 84 | 0.112 | 0.005 | −0.109 | 0.348 |
| 4 | `sip_mob` | 86 | 0.083 | 0.001 | −0.035 | **0.077** |
| 5 | `sip_emo` | 86 | 0.076 | 0.005 | −0.042 | **0.029** |
| 6 | `raragrasp` | 93 | 0.073 | 0.015 | −0.125 | **0.087** |
| 7 | `sip_psychosoc` | 86 | 0.057 | 0.008 | −0.045 | **0.017** |
| 8 | `sip_body` | 86 | 0.043 | 0.004 | −0.075 | **0.017** |
| 9 | `sip_social` | 86 | 0.029 | 0.010 | −0.044 | 0.116 |
| 10 | `sip_com` | 86 | 0.023 | 0.002 | −0.060 | **0.087** |
| 11 | `sip_physical` | 86 | 0.008 | 0.002 | −0.049 | **0.087** |

**11 of 87 clear zero; 9 of those also clear q<0.10.** Against June's 8/87, none of
which were permutation-validated except `lpegs`.

Three things worth noting.

**The degenerate-floor targets sort themselves out.** `larapinch`, which June ranked #1
at 0.221, lands at −2.262 here (floor −2.563), and `raragrip` at −3.714 (floor −4.157).
They sit at the bottom instead of the top. §4's warning about excluding them from the
ranking still holds in principle, but this configuration does not manufacture the
spurious positives that made the warning urgent.

**`lshflex` at #3 is the one not to trust.** R²=0.112 looks respectable and it is stable
across draws, but q=0.348 — it does not survive permutation testing. R² and significance
are answering different questions and this row is where they disagree.

**Stability is the real gain.** Median spread across three independent draws is **0.003**.
Two exceptions: `laragrasp` (0.410) and `pos_acc_lv` (0.074), both deep in negative
territory where nothing is being learned anyway.

The surviving set is coherent: left/right pegboard and ARAT pinch/grasp on the motor
side, and the SIP family (mobility, emotion, psychosocial, body care, communication,
physical) on the self-reported function side. Effects remain small — 0.14 at best.

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
