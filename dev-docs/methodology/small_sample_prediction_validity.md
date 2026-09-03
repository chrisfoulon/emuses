# When is a prediction from EMUSES trustworthy?

_Written 2026-09-03. Measured on `DSD_repro` (133 labelled stroke subjects, 87 neuropsych
measures, 902,629-voxel disconnectomes). Every number below comes from that dataset unless
marked otherwise._

This document exists because a single number was read against the wrong baseline for three
months. It sets out what R² actually measures, the three diagnostics that decide whether a
result can be trusted, what they said about `DSD_repro`, and which design choices follow.

---

## 1. R² = 0 is not the baseline

`sklearn.r2_score` computes `SS_tot` from **the held-out fold's own mean** — a quantity the
model did not have at training time. So R² = 0 means *"as good as an oracle that already knew
the test set's average"*. Nothing honest reaches it reliably at small n.

The thing you would actually do — predict the **training** mean — uses the wrong mean and
therefore scores **below zero** on held-out data:

| baseline | measured on `DSD_repro` |
|---|---|
| predict training mean, within 5-fold CV at n≈88 | median **−0.086**, mean −0.237 |
| predict training mean, 70/30 held-out split | mean **−0.133**, median −0.026 |
| ceiling-bound targets (ARAT family) | floor reaches **−2.5** |

**Consequence.** The June 2026 run reported `Overall_Mean_Performance = −0.1884`. Read against
zero that is a catastrophe; read against the floor it is *approximately break-even*. Same
number, opposite conclusion. Every score EMUSES prints must carry its own floor beside it, and
the floor is per-target — it depends on that target's n, fold structure and distribution.

---

## 2. Three diagnostics, three different questions

They are often conflated. They are not interchangeable.

| diagnostic | question it answers | needs |
|---|---|---|
| **Mean-predictor floor** | Did the model beat guessing *on this data*? | y and folds only. No fitting. |
| **Permutation null** | Would it have beaten guessing *this much* if there were no relationship? | model fits on shuffled y |
| **Sampling SD → minimum detectable effect** | Could this n detect an effect of this size *at all*? | model fits on repeated splits |

A result needs all three. Beating the floor without clearing the null means you found noise.
Clearing the null with an effect below the MDE means the finding is not reproducible even if
it is real.

### 2.1 The floor is a cheap approximation of the null

Measured: permutation null mean **−0.129**, held-out mean-predictor floor **−0.133**. Nearly
identical, and for a good reason — a procedure with no signal to exploit performs about as
well as predicting the mean.

The floor is therefore a free stand-in for the null **when the procedure cannot overfit**. It
stops being one when the procedure has capacity to fit noise, and the gap between floor and
null is precisely how much the procedure overfits. That gap is a measurement worth having.

### 2.2 The permutation null must not be computed after selecting the model on real y

If the model family is chosen using the real `y` and only then permuted, the null does not
include the choosing, so it is too easy and significance is overstated. Two valid options
only:

- fix the model a priori — nothing to account for; **or**
- re-run the entire selection inside every permutation — correct but ~300× the cost.

There is no cheap middle. **Permutation testing is valid and affordable precisely when you are
not searching.**

### 2.3 The permutation null underestimates the error bar

The null holds the folds fixed and shuffles only `y`, so it captures y-noise but not
train/test split noise. Measured: SD of the permutation null **0.064**, SD of the real
held-out estimate across 25 repeated splits **0.142** — the null is low by **1.96×**
(correlation between them 0.55). The error bar has to come from repeated splits, not from
permutation.

This reproduces [Varoquaux (2018)](https://doi.org/10.1016/j.neuroimage.2017.06.061), whose
central claim is that "the standard error across folds strongly underestimates" the true error
bars, and who reports ±10% error bars at 100 samples.

---

## 3. What this means for `DSD_repro`

### 3.1 The error bar is larger than every effect

SD of a single held-out R² across 25 repeats: **median 0.142** (IQR 0.106–0.282).
A single estimate therefore carries a 95% CI of roughly **±0.28**.

### 3.2 Minimum detectable effect

`MDE = null_p95 + 0.84 × SD` (0.84 = one-sided z at 80% power). Both terms measured, no
simulated effect sizes:

- critical value (null p95), median across 87 targets: **−0.021** (all 87 below zero)
- **MDE, median: 0.096** (IQR 0.065–0.214)

Observed effect vs what this n can detect, for the 13 permutation-validated measures:

| measure | observed | SD | MDE | exceeds MDE? |
|---|---|---|---|---|
| `lpegs` | 0.173 | 0.199 | 0.143 | **yes, +0.029** |
| `sip_mob` | 0.050 | 0.081 | 0.052 | no (−0.002) |
| `sip_psychosoc` | 0.006 | 0.114 | 0.082 | no |
| `sip_body` | −0.015 | 0.148 | 0.102 | no |
| `sip_com` | −0.020 | 0.132 | 0.096 | no |
| `sip_physical` | −0.027 | 0.122 | 0.085 | no |
| `raragrasp` | −0.010 | 0.288 | 0.230 | no |
| `rpegs` | −0.066 | 0.275 | 0.210 | no |
| `sip_emo` | −0.075 | 0.631 | 0.512 | no |
| `rarapinch` | −0.253 | 1.298 | 1.068 | no |

**1 of 13**, and `lpegs` clears its own threshold by 0.029 with an SD of 0.199 — marginal.
If anything this is optimistic: the 25 repeats resample within the same 133 subjects rather
than drawing fresh ones, so true between-study variability is larger.

**`DSD_repro` at n≈88 is underpowered for every measure except possibly `lpegs`.**

The SD above is the `raw_only`+ElasticNet arm. The MDE depends on **which model you intend to
report**, because a wider search is noisier:

| SD measured from | median per-target SD | resulting median MDE |
|---|---|---|
| fixed `RidgeCV`, no search | 0.132 | **0.089** |
| `raw_only` + ElasticNet, 60 trials | 0.142 | 0.096 |
| full search space, 60 trials | **0.236** | **0.176** |

The full search is **1.49×** noisier per target than the fixed model, so its detection threshold is
roughly **double**. This matters for implementation: an MDE computed cheaply from a fixed reference
model is a *lower bound* on the searched model's MDE. Like the floor check (§4.4), it is therefore
trustworthy **in one direction only** — failing it means no model could have worked; passing it does
not mean the searched model can detect the effect.

This is consistent with the field, not a peculiarity of EMUSES.
[Poldrack, Huckins & Varoquaux (2020)](https://doi.org/10.1001/jamapsychiatry.2019.3671) state
that "prediction analyses should not be performed with samples smaller than several hundred
observations". [Marek et al. (2022)](https://doi.org/10.1038/s41586-022-04492-9) show
brain-wide association studies need thousands, and that underpowered studies are "susceptible
to uncovering strong but spurious associations by chance" — which is what put the
ceiling-bound `larapinch` at rank #1 in June.

### 3.3 Model selection is not available at this n

Three independent measurements:

- Choosing the search space by development-set CV picked correctly in **26 %** of splits, and
  scored **−0.227** against the full space's −0.221 — no better than not trying.
- Five independent draws of the same nested search disagree by a **median per-target range of
  0.080**, the size of the effects themselves.
- Across all 87 targets, **0 have all five outer folds agree** on a feature-union + estimator
  combination; 79 of 87 produce 4–5 distinct configurations out of 5.

You cannot rank models when the yardstick is noisier than the differences being ranked. This
is the variance mechanism of
[Cawley & Talbot (2010)](https://jmlr.org/papers/v11/cawley10a.html), whose result is that a
model-selection criterion's *variance* matters at least as much as its bias, because
non-negligible variance lets the selection itself over-fit.

### 3.4 Searching costs more than it returns

Held-out, 25 repeats × 87 targets, 70/30, all selection inside the development set:

| configuration | mean R² | median | splits < −0.5 |
|---|---|---|---|
| full search space, 60 trials | −0.221 | −0.042 | 8.7 % |
| `raw_only` + ElasticNet | −0.131 | −0.028 | 4.7 % |
| fixed `RidgeCV`, no search | −0.135 | −0.025 | 4.8 % |
| **mean predictor (floor)** | **−0.133** | −0.026 | 3.7 % |

Narrowing the space does not create gains — it reaches the floor, it does not beat it. What it
removes is the tail: medians differ by 0.014 while catastrophic splits nearly double. The full
search is the only configuration meaningfully *worse* than doing nothing.

---

## 4. Design decisions that follow

1. **Print the floor next to every score.** Per target, from its own n and folds. Free
   (0.02 s for all 87). This is the single number whose absence caused the misreading in §1.

2. **Print the error bar from repeated splits, never from across-fold SD.** §2.3 and
   Varoquaux (2018). 13 s for all 87 at 20 repeats.

3. **Gate the ranking, not the run.** A target that does not beat its floor is listed as
   "not predictable at this n" rather than ranked — a rank implies an ordering by quality, and
   ordering noise is what produced June's top-6. Emit two files, both carrying the denominator
   ("13 of 87 targets exceeded their floor"), so a total failure reads as "0 of 87" instead of
   as a short clean result.

4. **Do not automate space-switching or halting on these metrics.** Measured and rejected
   (§3.3, 26 %). The failure is structural: a wide space's development score is inflated by its
   own max-over-trials selection and a narrow space's is inflated less, biasing the comparison
   toward the wider space by exactly the amount that makes it look good. The floor check is
   trustworthy in **one direction only** — the model's score carries selection inflation, the
   mean predictor's carries none, so *failing* is strong evidence and *passing* is weak.
   Flag failures; never treat a pass as validation.

5. **Nesting is required if you select, unnecessary if you do not.** Dropping the nesting while
   keeping the search yields a better-looking, wrong number (Cawley & Talbot 2010). The valid
   simplification is the other order: fix the model a priori, then plain repeated k-fold is
   unbiased — and it buys larger training folds, plus a permutation null that is both valid
   (§2.2) and affordable (§5).

6. **Warn rather than adapt.** When the observed effect is below the MDE, report that the data
   cannot support model selection and fall back to one fixed regularised model. There is no
   configuration of cross-validation that overcomes a resolution limit.

### What this does not cover

Measurement reliability sets a second, independent ceiling: classical attenuation bounds the
achievable correlation by √(reliability of y), so an instrument with test–retest reliability
0.8 caps R² near 0.8 regardless of sample size. **This cannot be estimated from `DSD_repro`** —
it needs repeat measurements or item-level responses, and the dataset has neither. Published
reliabilities for the SIP and ARAT would supply it.

Also uncovered: the permutation null here fixes the embedding, so it tests "given this
embedding, is there an association?" It does **not** test whether the UMAP hyperparameter
search found structure by chance.

---

## 5. Cost

Measured on this dataset, 87 targets, fixed `RidgeCV` on the 2-D embedding:

| step | 1 core | 8 cores |
|---|---|---|
| mean-predictor floor | 0.02 s | — |
| repeated CV × 20 (gives the SD and MDE) | 13 s | ~2 s |
| permutation null, 1000 × 87 targets | 10.7 min | **1.3 min** |
| **total** | **~11 min** | **~1.5 min** |

Against a ~19-hour pipeline run, the full diagnostic suite costs **under 0.1 % of runtime**.

The earlier scratch implementation took 4 h 28 m because it re-ran a 21-alpha × 5-inner-fold
selection inside every permutation. `RidgeCV`'s efficient leave-one-out removes that.
Note the cost is only this low because the model is fixed — a 60-trial search inside each
permutation multiplies it by roughly 300.

---

## References

All verified against the published record on 2026-09-03.

- Cawley, G. C., & Talbot, N. L. C. (2010). On over-fitting in model selection and subsequent
  selection bias in performance evaluation. *Journal of Machine Learning Research*, 11(70),
  2079–2107. <https://jmlr.org/papers/v11/cawley10a.html>
- Varoquaux, G. (2018). Cross-validation failure: Small sample sizes lead to large error bars.
  *NeuroImage*, 180, 68–77. <https://doi.org/10.1016/j.neuroimage.2017.06.061>
- Poldrack, R. A., Huckins, G., & Varoquaux, G. (2020). Establishment of best practices for
  evidence for prediction: A review. *JAMA Psychiatry*, 77(5), 534–540.
  <https://doi.org/10.1001/jamapsychiatry.2019.3671>
- Marek, S., Tervo-Clemmens, B., Calabro, F. J., … Dosenbach, N. U. F. (2022). Reproducible
  brain-wide association studies require thousands of individuals. *Nature*, 603, 654–660.
  <https://doi.org/10.1038/s41586-022-04492-9>
- Nichols, T. E., & Holmes, A. P. (2002). Nonparametric permutation tests for functional
  neuroimaging: A primer with examples. *Human Brain Mapping*, 15(1), 1–25.
  <https://doi.org/10.1002/hbm.1058>
- Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate: a practical and
  powerful approach to multiple testing. *JRSS Series B*, 57(1), 289–300.

**Working scripts** (not in the package):
`~/.claude/jobs/0d3a7417/tmp/{perm_test,holdout_test,search_variance,trials_sweep}.py`.
Full audit narrative: `dev-docs/issues/disconnectome_design_audit_2026_08.md`.
