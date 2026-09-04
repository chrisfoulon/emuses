# What the DSD literature actually shows, and what it means for EMUSES

_Written 2026-09-04. Companion to `small_sample_prediction_validity.md`, which covers the statistics;
this covers the **external evidence** — whether the effects EMUSES is failing to find are real — and
the design conclusions that follow._

**Search this file when any of these come up:** DSD, Disconnectome Symptom Discoverer, Talozzi,
Matsulevits, deep-disconnectome, Hope et al., PLORAS, "is the effect real", "is EMUSES broken",
MAE%, whether to keep the model search, UMAP dimensionality / 2-D vs N-D, exploration vs
confirmation mode.

---

## 1. The question this settles

EMUSES works on the digits toy problem and finds almost nothing on `DSD_repro`. Two readings:
either the published disconnectome results are spurious, or EMUSES is broken on real data. The
answer is **neither**, and the numbers pin it down precisely.

## 2. The three papers

| | what it is | key claim |
|---|---|---|
| **Talozzi et al. 2023**, *Brain* 146:1963–1978, [10.1093/brain/awad013](https://doi.org/10.1093/brain/awad013) | the original DSD | external R²=0.201 semantic fluency, R²=0.1797 Bells test; training average R² = 0.19 ± 0.09 (range 0.05–0.67) |
| **Matsulevits et al. 2024**, *Brain Commun* 6(5):fcae338, [10.1093/braincomms/fcae338](https://doi.org/10.1093/braincomms/fcae338) | same data, deep-learning disconnectomes | deep beats conventional: R² 0.191→0.208, accuracy 83.7%→85.2% |
| **Hope et al. 2024**, *Brain* 147:e11–e13, [10.1093/brain/awad352](https://doi.org/10.1093/brain/awad352) | **independent out-of-sample test of the frozen, published DSD model** | it generalises |

## 3. The reported metrics are inflated — four findings, three of them hard

**3.1 The MAE% metric has a floor at ~85 %, measured on our own data.** Both DSD papers report
`accuracy = 1 − MAE/max(score)`. Predicting the mean every time, on the same 87 `DSD_repro`
measures:

- **mean 85.0 %, median 86.3 %** (IQR 80.5–90.8; 56 % of measures above 85 % from the mean alone)

Against which: Matsulevits reports 85.7 % in-sample, **80.67 % out-of-sample**, 85.2 % headline;
Talozzi reports "MAE below 20 %", i.e. >80 %. **The out-of-sample figure is below what predicting
the mean achieves.** This is the same error as reading EMUSES's −0.1884 against zero instead of
against its floor (§1 of the companion doc), in a different costume.

**3.2 Matsulevits' significance test is arithmetically wrong.** Reported: `t(85) = −1.663,
P = 0.009`, starred as *P*<0.01. For t=1.663 at df=85 the two-tailed **p = 0.100** (one-tailed
0.050). The headline claim — deep-disconnectomes significantly outperform conventional ones — is a
null result by their own statistic. A secondary sign test does survive (54/86 scores improved,
binomial p = 0.023, 95 % CI on the proportion 0.52–0.73), so the *direction* has weak support; the
claimed significance does not.

**3.3 Their in-sample R² = 0.208 is circular.** Voxels are kept at |R|>0.2 *against the outcome*,
PCA'd, regressed on the outcome, and the fit reported on the same N=119 (Kriegeskorte et al. 2009;
Vul et al. 2009). Note this affects both arms roughly equally, so it does **not** by itself
invalidate the deep-vs-conventional comparison — 3.2 does that.

**3.4 Their out-of-sample R² is computed on N=20 — which the original authors explicitly refused to
do.** Talozzi, verbatim:

> "Such a measure was calculated only when the number of subjects included was more than 20. Thus,
> R² is provided for all the datasets except dataset 2-validation, where individual MAE % measures
> are reported."

Matsulevits reports out-of-sample R² on exactly N=20, on the same cohort.

## 4. But the underlying effect is real

**Hope et al. 2024 is the decisive evidence**, and it is not in either paper above. An independent
group ran the **already-published, frozen** DSD model as a black box on PLORAS data it had never
seen — different cohort, different lesion segmentation (algorithmic vs manual), different outcome
instrument (CAT vs WAB):

| | Washington (original) | PLORAS 1 yr (**n=314**) | PLORAS 5+ yrs (n=340) |
|---|---|---|---|
| Naming | R=0.35 | **R=0.31, p<0.001** | R=0.00, p=0.86 |
| Fluency | R=0.41 | **R=0.34, p<0.001** | R=0.19, p<0.001 |

A frozen model cannot overfit new data. R≈0.31–0.34 at n=314 with p<0.001 is a real effect,
i.e. **R² ≈ 0.10–0.12**.

Two honest qualifications. Hope et al. do not appear to control for lesion volume in that table, and
their own reference 1 (DeMarco & Turkeltaub) is about lesion-volume bias in lesion-symptom mapping.
And naming at 5+ years is **R=0.00** — the effect is fragile. They also note themselves that other
models explain ~60 % of variance in these skills where DSD explains <20 % of it.

Our own audit points the same way: §7 of `disconnectome_design_audit_2026_08.md` found disconnection
*pattern* beat lesion volume (8/11 vs 2/11 measures above floor), with volume adding nothing once
pattern was present.

## 5. The reconciliation — EMUSES is not broken, it is out of resolution

| quantity | value |
|---|---|
| real effect size, from the well-powered independent test | **R² ≈ 0.10** |
| EMUSES's measured MDE at n≈88, **fixed model** | **0.096** |
| EMUSES's measured MDE at n≈88, **full search** | **0.176** |

The true effect sits *exactly at* the fixed-model detection threshold and *below* the searched-model
one. EMUSES is behaving as a correctly calibrated instrument at the edge of its resolution — and it
did detect `lpegs` at R²=0.245, permutation q=0.017.

**The sharp version, and the part that is genuinely EMUSES's fault:** the model search raises the
detection threshold from 0.096 to 0.176 — from *just detectable* to *not detectable* — and returns
nothing for it (full search −0.221 against the floor's −0.133). The search is spending the little
statistical power n≈88 provides on a choice it cannot make.

## 6. The published domain rankings do not reproduce each other

- **Talozzi**: headline external results are **semantic fluency** (language) and the **Bells test**
  (visuospatial).
- **Matsulevits**: best domain **motor** (R²=0.31), worst visuospatial memory (0.11) — and
  conventional disconnectomes *beat* deep ones on visuospatial memory (0.16 vs 0.11).
- **EMUSES on `DSD_repro`**: the permutation-validated set is `lpegs`, `rarapinch`, `rpegs`,
  `raragrasp` (pegboard and ARAT — motor) plus the SIP scales.

Two analyses of essentially the same cohort disagree about which domain is most predictable. That is
our seed-spread finding appearing in the literature: we measured that per-target rankings do not
reproduce across sampler seeds (median per-target range **0.080**, the size of the effects). Treat
any published per-domain ranking at this n as unstable, including our own.

## 7. Design conclusions

**7.1 Keep the search; it is badly designed, not a bad idea.** Positive evidence: on the digits run
the search reached 97.50 % held-out against the preprint's 93.33 %, and picked genuinely appropriate
models. ADR §1.3's rationale stands. Three specific defects, all measured:

1. **It selects per outer fold**, so there is no single model to report: 0 of 87 targets had all five
   folds agree on a configuration, 79 of 87 produced 4–5 distinct ones. The reported score averages
   five different models, and the variance includes model-switching noise.
2. **The space is too wide for a 2-D input** (4 feature recipes × 3 estimators × 7 hyperparameters).
   Note this is **selection variance, not selection bias**: more trials help monotonically (−0.379 at
   1 trial → −0.005 at 120) with the inner/outer gap flat at ~0.01. That is why "more trials" was the
   wrong fix and narrowing was the right one (Cawley & Talbot 2010).
3. **The budget is on the wrong stage**: ~95 % of compute chooses between models, ~1 % chooses the
   representation they see (digits: 17 min UMAP/HDBSCAN of a 3 h 35 m run).

Proposed direction: **select once, not per fold** — choose on the whole training set, then use that
model in every fold. Loses the unbiased-estimate-of-the-procedure property; gains a model you can
name, permutation-test cheaply, and report a spread for. Given the MDE arithmetic that trade is
clearly worth it here.

**7.2 Do NOT change the UMAP dimensionality. (Correction — I argued the opposite and was wrong.)**
The bottleneck case was built on the digits run (61-D → 2-D cost 1.1 points) and does not transfer.
**Hope et al. got R=0.31 out-of-sample at n=314 from a 2-D morphospace**: two dimensions
demonstrably carry the real effect in this data. What EMUSES lacks is n, not dimensions.

If N-D is ever revisited, the blocker is specific: the heatmap turns each patient's coordinate into a
probability map over a **grid**, and grids are exponential in dimension (100 bins/axis: 2-D = 10⁴
cells, 3-D = 10⁶, 5-D = 10¹⁰). Clustering in N-D and projecting to 2-D for display would work for the
clusters but **breaks the thing that makes EMUSES worth using** — the heatmap would no longer explain
the prediction, and a 2-D projection can place genuinely separate clusters on top of each other. A
cleaner formulation exists (evaluate the correlation field at sample points in N-D, interpolate onto
the 2-D projection for display only), but it changes what the heatmap *means*. Before any of it, run
the cheap check: UMAP at `n_components` ∈ {2,3,5,10}, fixed ridge, the 13 validated measures. If 5-D
does not beat 2-D the question is moot.

**7.3 Exploration mode vs confirmation mode.** The wide space exists because shotgunning a new
dataset is a legitimate thing to want. It should be an explicit mode, not the default:

- **exploration** — wide space, output labelled as *design evidence*, never as findings;
- **confirmation** — narrow space, longer search, lower spread, reportable.

**The condition that makes or breaks this: the two phases cannot use the same data for the final
number.** Shotgun on `DSD_repro`, observe raw+ElasticNet wins, narrow to it, then report on
`DSD_repro` — that is selecting on the data, and it is exactly how §9c's ranking got inflated before
the held-out test overturned it. Three legitimate versions: (a) explore on a development cohort and
confirm on a separate one; (b) treat the narrowed space as a **prior for the next dataset**, not a
result on this one; (c) explore inside training folds on every fold — which is what EMUSES does now,
and is what costs the variance.

## 8. Open

- **Stage separation** (see `STATUS.md` 3k): `emuses heatmap` standalone is unsupported *by
  architecture* (ADR §2.11), and that ADR entry names the resolution as a deliberately open product
  decision. The "build a morphospace now, add labelled data later" workflow is the use case that
  decides it.
- The lesion-volume confound in Hope et al. is unresolved and would need their data to settle.
- Attenuation ceiling from instrument reliability: still unmeasurable from `DSD_repro`
  (no repeat measurements). Published SIP/ARAT reliabilities would supply it.

## References

- Talozzi L, Forkel SJ, Pacella V, et al. (2023). Latent disconnectome prediction of long-term
  cognitive-behavioural symptoms in stroke. *Brain* 146(5):1963–1978.
  <https://doi.org/10.1093/brain/awad013>
- Matsulevits A, Coupé P, Nguyen H-D, et al. (2024). Deep learning disconnectomes to accelerate and
  improve long-term predictions for post-stroke symptoms. *Brain Communications* 6(5):fcae338.
  <https://doi.org/10.1093/braincomms/fcae338>
- Hope TMH, Neville D, Talozzi L, Foulon C, Forkel SJ, Thiebaut de Schotten M, Price CJ (2024).
  Testing the disconnectome symptom discoverer model on out-of-sample post-stroke language outcomes.
  *Brain* 147(2):e11–e13. <https://doi.org/10.1093/brain/awad352>
- Kriegeskorte N, Simmons WK, Bellgowan PSF, Baker CI (2009). Circular analysis in systems
  neuroscience: the dangers of double dipping. *Nature Neuroscience* 12(5):535–540.
- Vul E, Harris C, Winkielman P, Pashler H (2009). Puzzlingly high correlations in fMRI studies of
  emotion, personality, and social cognition. *Perspectives on Psychological Science* 4(3):274–290.
- Cawley GC, Talbot NLC (2010). On over-fitting in model selection and subsequent selection bias in
  performance evaluation. *JMLR* 11(70):2079–2107.
