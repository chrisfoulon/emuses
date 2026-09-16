# Several distinct profiles for one deficit — and why not HYDRA

_Written 2026-09-08. Renamed 2026-09-09: the file was `hydra_evaluation.md`, which named the method
looked at rather than the question asked, and made a rejected method look like part of the plan._

**What this file is for.** It records the design question behind clustering in EMUSES, and closes
one candidate answer so it is not re-proposed. **HYDRA was evaluated and does not fit** — the
verdict and the three structural reasons are below. Two ideas from it are worth taking, and those
two are the only part of this file that touches the actual plan; everything else is here so the
rejection stays recoverable.

The live plan is `heatmaps_clusters_and_effect_size_maps.md` and
`embedding_scaling_and_boundary_bias_plan.md`. Nothing here is scheduled work.

## The question

Chris's argument for why EMUSES clusters at all, in his words: for a given target score there may be
**several distinct disconnection profiles** associated with the same deficit. Classical mass-univariate
methods put those profiles in competition, so what you recover is their overlap, or one profile's
residual after another has absorbed the shared part — never a true profile. Segregating observations
into groups first is what lets an individual profile survive.

This is a real methodological problem with a published literature, so it was worth checking that
literature before designing anything ourselves.

## The candidate: HYDRA

[HYDRA](https://pmc.ncbi.nlm.nih.gov/articles/PMC5408358/) (Varol, Sotiras & Davatzikos,
*NeuroImage* 2017) exists for precisely that argument. It was built because a single discriminative
pattern between patients and controls averages over multiple distinct disease patterns.

## What HYDRA is

Simultaneous classification and clustering. Instead of one hyperplane separating patients from
controls, it fits **K hyperplanes forming a convex polytope**; each face defines a subtype, and each
patient is assigned to the face that best separates it from the controls. Clustering and
discrimination are solved together under one objective, so the K profiles are estimated jointly
rather than one at a time.

Objective (their Eq. 1), minimised over hyperplanes `{W, b}` and a soft assignment matrix `S⁻`:

```
Σⱼ ‖wⱼ‖²/2  +  C Σ max{0, 1 − wⱼᵀxᵢ − bⱼ}      (controls, +1)
            +  C Σ sᵢⱼ max{0, 1 + wⱼᵀxᵢ + bⱼ}   (patients, −1)
```

---

## The seven steps, applied to EMUSES

### Step 0 — Define the two groups

HYDRA requires **binary labels**. EMUSES has a continuous score, so it must be dichotomised:
"controls" = normal-range scores, "patients" = the extreme group.

**HYDRA does not remove the need for an extremeness threshold — it consumes one.** Whether that cut
comes from a normative reference or a cohort percentile is a separate decision it cannot make.

Run **once per direction** (high-vs-normal, then low-vs-normal). Putting both extremes in as
"patients" would probably work — they differ from normal in opposite ways, so the polytope would
likely split them — but then a high subtype and a low subtype are indistinguishable without
inspecting weight vectors, and the margin is doing two jobs at once.

### Step 1 — Assemble the feature matrix

`X ∈ ℝ^(n×d)`: exactly the existing `input_matrix` (`prediction_train_features`, one flattened
disconnectome per subject) that currently feeds `input_matrix_stat_map`.

**Architectural consequence:** HYDRA must run on the voxel-level features, not on UMAP coordinates,
because its weight vectors *are* the profiles and a direction in 2D UMAP space is not a disconnection
pattern. So HYDRA **bypasses UMAP for subtyping**. UMAP would retain three jobs — predicting the
score, embedding new subjects, display — but would no longer be where clusters come from.

### Step 2 — Correct for covariates first

HYDRA does not model confounds; the paper pre-corrects the features and lists this as a limitation.
For disconnectomes the obvious confound is **lesion volume** — a larger lesion disconnects more of
everything, and uncorrected, the first hyperplane will most likely just find lesion size.

### Step 3 — Choose K by stability

Fit for K = 1…8 under 10-fold cross-validation, compute the Adjusted Rand Index between fold
clusterings, take the peak. (The paper used 100 realisations of 10-fold CV; K = 3 on AD imaging,
K = 2 on genetics.)

**This step is worth more than it appears.** K = 1 is a plain SVM — the single-profile null. So the
ARI curve answers *"is there more than one profile at all?"*, which is the premise the whole
clustering argument rests on, tested rather than assumed.

### Step 4 — Fit at the chosen K

Alternating optimisation:

- fix `S⁻`, solve `{W, b}` → decomposes into K independent **weighted** SVMs (modified LIBSVM)
- fix `{W, b}`, solve `S⁻` → `sᵢⱼ ∝ (1 + wⱼᵀxᵢ + bⱼ)` where the loss is non-zero, else 0

Non-convex: initialised with Determinantal Point Processes, run from multiple starts with a consensus
step. High-dimensional data uses the dual formulation, operating in inner-product space — so
d ≈ 10⁵ voxels is fine. This regime is what the method was designed for.

### Step 5 — Read out the profiles

Each `wⱼ` lives in voxel space and **is** subtype *j*'s disconnection profile. This replaces
`perform_region_clustering` + `input_matrix_stat_map` + the per-cluster effect-size map, in one step.

Because the K profiles are fitted **jointly under one objective**, no profile is another's residual
and none is the overlap. That is the direct answer to the motivating argument.

### Step 6 — Assign new and unlabelled subjects

Evaluate the hyperplanes; the subject belongs to the face that separates it best. An explicit linear
rule.

**This dissolves the HDBSCAN refit question entirely** — no `approximate_predict` unreliability, no
refit-or-assign dilemma, and unlabelled subjects can be assigned exactly rather than approximately.

### Step 7 — What UMAP would still be for

Score prediction (unchanged), embedding new subjects, and display. Plus one new and genuinely useful
check: **colour the morphospace by HYDRA subtype.** Spatially coherent subtypes mean the two views
corroborate each other; scattered ones mean the morphospace is not capturing what separates the
profiles — worth knowing either way.

---

## What HYDRA does not solve

1. **Double dipping remains.** The paper states it: comparisons between inferred subtypes "may be
   biased due to sample splitting", and voxel-based comparisons serve a "qualitative rather than
   quantitative" function. The weight vectors are a model output, not a tested map. P-values on
   profiles still require held-out data.
2. **Weight-vector interpretation is discouraged when covariates are present** — the authors use
   post-hoc analysis on held-out features instead. Step 5's readout needs the same care.
3. **It needs the extremeness definition as an input** (Step 0).

---

## Verdict: not a fit for EMUSES

Three incompatibilities, and they are structural rather than fixable by configuration:

| | HYDRA requires | EMUSES is built on |
|---|---|---|
| **Target** | binary labels (patient / control) | a continuous score; dichotomising discards the pipeline's central object |
| **Model class** | linear, piecewise via the polytope | non-linearity — which is *why* UMAP was chosen over PCA |
| **Feature space** | voxel-level features directly | UMAP coordinates as the space everything happens in |

Plus a practical collision: the AD study used **123 patients vs 177 controls** to find K = 3. A 5 %
tail of a few hundred subjects gives ~15 "patients" to split into 2–3 subtypes. The ARI stability
curve would almost certainly refuse K > 1. For HYDRA to have anything to work with, "affected" would
have to be a generous clinical cut-off capturing a substantial fraction of the cohort, not a
distributional tail — which is a scientific question about what the score means, not a parameter.

So adopting HYDRA would not be "EMUSES with better clustering". It would be a second, parallel
analysis with a different premise, sharing only the input matrix.

## What is transferable

**The principle, not the package: fit the multiple profiles jointly under one objective, rather than
estimating each independently and letting them compete.**

That is what actually answers the motivating argument, and it does not require HYDRA's linearity or
its binary framing. The current pipeline violates it — each cluster's effect-size map is computed
separately by `input_matrix_stat_map`, against a reference group that contains the other clusters
(the other session's D1), which is exactly the competition the argument objects to.

Two cheaper moves in that direction, neither requiring a new algorithm:

- **Fix the reference group** (their D1/D2): compare each subcluster against *neutral* subjects
  rather than against everyone-else-including-siblings. This alone removes the mechanism by which a
  shared component gets suppressed.
- **Model the profiles together** rather than running independent voxelwise tests — a single
  multi-group model in place of K separate two-group comparisons.

The second is the real version of HYDRA's idea inside EMUSES's own architecture. It is a design
question, not yet a proposal.

## Open, if this is pursued further

- Does any variant handle a **continuous outcome** directly? Not checked. Related work from the same
  group: [MAGIC](https://www.sciencedirect.com/science/article/abs/pii/S1361841521003492)
  (multi-scale successor), [CHIMERA](https://www.med.upenn.edu/cbica/sbia/chimera.html) (generative
  counterpart). A Python implementation of HYDRA exists in
  [MLNI](https://github.com/anbai106/mlni); the original CBICA release is MATLAB.
- The ARI-stability idea from Step 3 is worth stealing regardless of HYDRA: EMUSES currently has no
  test of whether more than one profile exists.

## Sources

- [HYDRA — PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC5408358/) ·
  [NeuroImage](https://www.sciencedirect.com/science/article/abs/pii/S1053811916001506)
- [Subtyping brain diseases from imaging data](https://arxiv.org/pdf/2202.10945) (review)
- [MLNI](https://github.com/anbai106/mlni) ·
  [MAGIC](https://www.sciencedirect.com/science/article/abs/pii/S1361841521003492) ·
  [CHIMERA](https://www.med.upenn.edu/cbica/sbia/chimera.html)
