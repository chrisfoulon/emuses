# Heatmaps, clusters and effect-size maps — working document

_Opened 2026-09-06. **Temporary.** This exists to hold one discussion in one place until each item
below is decided; when an item is settled it moves to `.codebase-memory/adr.md` and is struck from
here. Delete the file when the list is empty._

_Companion to `dev-docs/methodology/embedding_scaling_and_boundary_bias_plan.md`, which owns the
coordinate-space work. Two items here depend on it and say so._

---

## Why this exists

Attention has been on prediction performance for a long time. The map/cluster/effect-size side was
not touched in that period, and it drifted: the wiring that implemented the intended design was
commented out, a simplified fallback took its place, and roughly 1400 lines of the original
implementation are still in the tree, imported but never called. Nothing here is a new idea — most
of it is recovering a design that already existed and deciding which parts to keep.

**Complexity note, since this is the stated worry:** the net effect of the whole list is to *remove*
code. Deletions ≈ 1400 lines; additions ≈ 150. Two items replace a heuristic with a test rather than
adding a layer on top of one.

---

## The list

Status key: **AGREED** = settled in discussion · **OPEN** = recommendation made, awaiting a call ·
**SURFACED** = not yet discussed, no decision taken.

### A. What the maps are for

| # | Item | Status | Section |
|---|---|---|---|
| A1 | Maps are **descriptive / localisation**, not a prediction tool. Per-subject prediction is `InferenceStage` and never reads the grid. | AGREED | [§1](#1-what-the-live-path-actually-does) |
| A2 | ADR records this only as a clause inside a grid-resolution decision (§1.7). Needs its own entry. | OPEN | [§1](#1-what-the-live-path-actually-does) |
| A3 | ADR §1.3 frames the kernel as a *competing predictor judged on CV score*, which is not the same intent. Reconcile. | OPEN | [§1](#1-what-the-live-path-actually-does) |

### B. Significance and the percentile heuristic

| # | Item | Status | Section |
|---|---|---|---|
| B1 | The 5th/95th percentile is not a test. Replace with a **permutation threshold**. | AGREED in principle, cost to confirm | [§2](#2-permutation-instead-of-percentiles) |
| B2 | The permutation on the **correlation** grid is nearly free (one matmul per batch); on the prediction grid it needs refits and is expensive. Tiered plan. | OPEN — pick tiers | [§2](#2-permutation-instead-of-percentiles) |
| B3 | The `pval_map` from `input_matrix_stat_map` is **invalid as inference** (double dipping) and is currently written to disk. | AGREED (Chris: "I was not really considering the pvals anyway") — decide whether to stop writing it | [§3](#3-the-circularity-and-what-it-does-and-doesnt-invalidate) |
| B4 | Multiple comparisons: **not pursued**. Grid size is chosen, so counting grid cells as tests is meaningless (10×10 would "fix" it). Sound for the grid; note the max-statistic permutation handles within-map multiplicity natively anyway. Voxel-level and across-target multiplicity remain unaddressed but are moot if `pval_map` goes. | CLOSED | [§2](#2-permutation-instead-of-percentiles) |

### C. Clustering

| # | Item | Status | Section |
|---|---|---|---|
| C1 | **Split the two operations.** *Defining* clusters → fit once on the labelled training cohort, frozen. *Assigning* a new subject → `membership_vector`, never a refit. | AGREED | [§4](#4-clustering-new-points), [§9](#9-cluster-belonging-for-ood-subjects-without-refitting) |
| C2 | `min_cluster_size` scaling question is **moot under C1** — the definition fit never sees a second cohort. Keep the ARI diagnostic only if a union refit is ever offered as an option. | RESOLVED by C1 | [§4](#4-clustering-new-points) |
| C3 | The **optimised HDBSCAN never reaches the effect-size maps**. `RegionStatisticalAnalyzer` fits a fresh one with hard-coded `min_cluster_size=3`, `min_samples=1`. Optuna searches 5–50 and 1–10. | AGREED — use the optimised parameters | [§4](#4-clustering-new-points) |
| C4 | `min_cluster_size=3` is too small for a stable voxelwise effect size, independently of C3. Optuna's floor of 5 is also low for this purpose. | OPEN | [§4](#4-clustering-new-points) |
| C5 | Under C1 the cluster definition stays a model artefact, so atomic folders (ADR §2.1) and reuse fingerprinting (§2.13) are **unaffected**. | RESOLVED by C1 | [§9](#9-cluster-belonging-for-ood-subjects-without-refitting) |
| C6 | HDBSCAN runs on the **raw** embedding; everything downstream is rescaled. Under the current per-axis rescale these are different metrics. | AGREED — fixed by the proportion-preserving rescale; do that branch first | [§6](#6-smaller-defects-found-while-tracing) |
| C7 | Unlabelled subjects may be **assigned** to already-defined clusters and included in the descriptive statistics, but must **not** join the HDBSCAN fit that defines them. | OPEN — follows from C1 | [§9](#9-cluster-belonging-for-ood-subjects-without-refitting) |

### D. Effect-size maps

| # | Item | Status | Section |
|---|---|---|---|
| D1 | Reference group: each subcluster is currently tested against **every other subject**, including its own siblings and the opposite extreme. | OPEN — recommendation below | [§5](#5-what-each-effect-size-map-is-compared-against) |
| D2 | Recommend **subcluster vs neutral** (subjects in no extreme region) as primary, plus **all-high vs all-low** as one summary contrast. | OPEN | [§5](#5-what-each-effect-size-map-is-compared-against) |
| D3 | Region → subject mapping uses a **bounding box**. A rectangle is meaningless in a non-linear UMAP space; it also silently admits subjects outside the region. Needs rework, not a patch. | AGREED — rework | [§6](#6-smaller-defects-found-while-tracing) |
| D5 | **Planned feature:** at inference, report which high/low cluster a new subject belongs to, alongside the prediction, with that cluster's stored effect-size map as the "driving factors". §9 supplies the mechanism. | NOTED — later | [§9](#9-cluster-belonging-for-ood-subjects-without-refitting) |
| D4 | Intent is **high absolute** correlation; the code thresholds the **signed** value at the 95th percentile, so a region of r = −0.8 is never selected. | AGREED — include negative correlations | [§6](#6-smaller-defects-found-while-tracing) |

### E. Dead code

| # | Item | Status | Section |
|---|---|---|---|
| E1 | Use the trained/optimised models, not a separate kernel regressor. The live grid **already does**; every hand-rolled kernel CV is in dead code. | AGREED — the fix is deletion | [§7](#7-the-dead-code) |
| E2 | `run_kernel_heatmap_analysis` (~700 lines) contains a working implementation of C1 (`cluster_predict_method="fit_predict"`). **Salvage before deleting.** | SURFACED | [§7](#7-the-dead-code) |
| E3 | `heatmap_stage.py:635-714` is the commented-out wiring for C1 + the unlabelled-subject idea. | SURFACED | [§7](#7-the-dead-code) |
| E4 | `RegionStatisticalAnalyzer` is constructed with `visualization_threshold=0.2, effect_size_threshold=0.5` which the live method never reads. The dead method that reads them applies `prediction >= 0.5` as an **absolute** threshold on an arbitrary score scale. | SURFACED | [§7](#7-the-dead-code) |
| E5 | Keep the **correlation** grid model-free. Using the trained model there would just duplicate the prediction map. | AGREED | [§7](#7-the-dead-code) |

### F. Unlabelled subjects

| # | Item | Status | Section |
|---|---|---|---|
| F1 | Running unlabelled subjects through the heatmap to "include them" is a **no-op**: region membership is decided by coordinates. | AGREED | [§8](#8-unlabelled-subjects) |
| F2 | Adding them **by coordinate membership**, for the descriptive statistics only, is legitimate and increases stability. | OPEN | [§8](#8-unlabelled-subjects) |
| F3 | Selecting them by *predicted* score would be pseudo-labelling with zero independent information and would worsen §3. | AGREED — do not | [§8](#8-unlabelled-subjects) |

### G. Not discussed at all

| # | Item | Status | Section |
|---|---|---|---|
| G1 | Two different GWD bandwidths for related purposes: correlation grid uses the 25th percentile of pairwise distances; the prediction search optimises `sigma_gwd` over 0.05–0.2. | SURFACED | [§6](#6-smaller-defects-found-while-tracing) |
| G2 | `region_coords / grid_size` is off by one (should be `/(grid_size-1)`) — a half-cell shift in every region→subject mapping. | SURFACED | [§6](#6-smaller-defects-found-while-tracing) |
| G3 | Regression confidence is a constant, so `cv_ensemble` returns 1.0 everywhere. Currently harmless (the consumer is dead) but the number is still written and displayed. | SURFACED | [§6](#6-smaller-defects-found-while-tracing) |

---

## 1. What the live path actually does

1. **UMAP stage** — Optuna jointly optimises UMAP and HDBSCAN (`min_cluster_size` 5–50,
   `min_samples` 1–10; objective weights cluster persistence, noise ratio, DBCV). The winner is
   refit with `prediction_data=True` (`clustering_utils.py:250`) and saved with its labels.
   Runs on the **raw** embedding.
2. **Heatmap stage** — nested-CV Optuna over `kernel`/`rf`/`elastic` ×
   `raw`/`gwd`/`pca_gwd`/`kpca_gwd`, on the **rescaled** coordinates.
3. **Two grids**, different in kind:
   - *prediction* — `model.predict(grid_coords)` on 100×100, averaged over folds
     (`grid_creator.py:190-226`);
   - *correlation* — **no model**. Per grid point, a Gaussian weight vector over subjects
     (`stats_utils.py:1068`) correlated against the scores (`correlation_grid_creator.py:208-217`).
     Explicitly "no kernel regression" (`heatmap_stage.py:1330`).
4. **`RegionStatisticalAnalyzer.create_statistical_maps`** — threshold at the 5th/95th percentile →
   `scipy.ndimage.label` connected components → per component take a **bounding box** → collect
   training subjects inside → refit HDBSCAN on those subjects → per subcluster with ≥
   `min_cluster_size` points, `input_matrix_stat_map` = voxelwise Mann-Whitney of **that subcluster
   vs every other subject** → effect-size map.

**A2/A3.** ADR §1.7 says the grid is *"an empirical choice balancing display quality and enough
cells for statistical analysis… not used in most of the pipeline, only in heatmap and spatial
analysis steps"* — the descriptive intent, recorded once, in passing. ADR §1.3 separately frames
kernel regression as one predictor among several *"picked by best performing"*. Both are true of
different objects, but the second is the frame that has driven the work, and it is why the
regression baselines are pinned at negative R² (§3.1b). Worth writing down which frame governs.

---

## 2. Permutation instead of percentiles

The percentile threshold answers "where is the surface highest", not "is anything here". A
permutation answers the second, and the standard framework is the neuroimaging one
([Nichols & Holmes 2002](https://www.fil.ion.ucl.ac.uk/spm/doc/papers/NicholsHolmes.pdf)):
shuffle the labels, recompute the map, keep a summary statistic per shuffle, threshold the real map
against that null.

**The cost is very asymmetric, and this is the whole practical point.**

| Tier | What is permuted | Cost | Buys |
|---|---|---|---|
| **1** | Scores, recomputing only the **correlation** grid | ~free | A real threshold on the correlation map, and a valid answer to "is score associated with morphospace position at all" |
| **2** | Same shuffles, keeping max cluster-extent | free once Tier 1 exists | "Is this region bigger than chance" — cluster-extent FWE |
| **3** | Scores, re-running the full chain incl. model fitting and voxelwise stats | hours to days | Valid p-values on the effect-size maps themselves |

Tier 1 is cheap because the correlation grid fits nothing. The GWD matrix (10 000 × n) is already
computed; a permutation batch is that matrix times a matrix of shuffled, standardised score vectors
— one `matmul`. For n≈300 and 1000 permutations this is seconds. Spearman needs ranks, but the ranks
of a permuted vector are a permutation of the ranks, so it is the same matmul.

Tier 3 is where the money goes, because every permutation needs the nested CV refit and ~10⁵
Mann-Whitney tests. **Recommendation: do Tiers 1+2, treat Tier 3 as an optional reporting mode, not
a default.**

Tiers 1+2 *replace* the percentile heuristic rather than adding to it, and reuse
`scipy.ndimage.label`, which is already imported. This is the "data-driven definition of a
significantly off-distribution region" without new machinery. It also delivers what ADR §1.7 already
flags as future work: *"More elaborate thresholds (e.g., permutation-based) could be implemented."*

**B4 (surfaced).** Nothing anywhere corrects across targets × high/low × subclusters. A max-statistic
permutation naturally handles the within-map multiplicity; the across-target multiplicity is a
separate decision.

---

## 3. The circularity, and what it does and doesn't invalidate

Subjects enter a region **by their embedding coordinates**; the embedding is a function of the input
features; the test then compares **those same features** between the selected subjects and the rest.
Under the null — scores unrelated to imaging — the test still rejects, because UMAP places subjects
by feature similarity, so any spatially coherent subset of morphospace differs in features from its
complement by construction. Textbook double dipping: selection and selective analysis on the same
data, with a statistic not independent of the selection criterion under the null
([Kriegeskorte et al. 2009](https://www.nature.com/articles/nn.2303)).

**What this does not invalidate:** the maps as *description*. "These are the disconnections that
characterise this region" is a legitimate readout, and it is what the maps are for (§1).

**What it does invalidate:** the `pval_map`. It is currently computed and saved.

**What fixes the inference:** Tier 1/2 above certifies that the *region* is score-related before any
feature-space description is attached to it. Tier 3 would additionally validate the map. Note the
two are separable — Tier 1/2 is the cheap half and buys most of the credibility.

---

## 4. Clustering new points

**C1 — the resolution is to stop treating this as one operation.** Two things were sharing a
mechanism and pulling in opposite directions:

| Operation | When | Requirement | Tool |
|---|---|---|---|
| **Define** the high/low subclusters | Once, at training | Must be **frozen** — the effect-size maps *are* the descriptions of these clusters, so a changed definition invalidates every stored map | `fit` on the labelled training cohort, with the **optimised** parameters |
| **Assign** a new subject to them | At inference, per subject | Must not alter the definition; must be able to say "none of them" | `membership_vector` — see [§9](#9-cluster-belonging-for-ood-subjects-without-refitting) |

The earlier "refit on the union" recommendation was answering the wrong question. Refitting is the
right move *if the goal is to describe the density structure of a combined cohort*. It is the wrong
move here, because the effect-size maps are published descriptions attached to specific clusters,
and refitting redefines what they describe. `approximate_predict` was rejected for good reason (it
is tight and dumps everything else to noise), but the alternative is not a refit — it is soft
membership.

**Consequence for C2 and C5:** both dissolve. There is no union refit, so `min_cluster_size` never
faces a second cohort and needs no scaling rule; and cluster labels stay a property of the model, so
atomic model folders and reuse fingerprinting are untouched. Keep the ARI diagnostic in the back
pocket only if a union refit is ever offered as an explicit *exploratory* mode, clearly separated
from the frozen definition.

**C3 (agreed).** The optimised clusterer, saved to disk with `prediction_data=True`, is never
consulted by `RegionStatisticalAnalyzer`, which fits its own with `min_cluster_size=3, min_samples=1`
(`region_statistical_analyzer.py:137-140`). Optuna searches 5–50 and 1–10. So the subclustering that
produces every effect-size map uses parameters that were never optimised and sit outside the searched
range. `min_samples=1` is also HDBSCAN's most noise-permissive setting; the comment calls it
"default", but the library default is `min_samples = min_cluster_size`. **Use the optimised
parameters.**

One wrinkle to decide with C4: the optimised parameters were selected for clustering the **whole**
embedding, while the subclustering runs on a *subset* (the subjects inside one extreme region). A
`min_cluster_size` tuned on 1333 subjects may leave a 40-subject region with no clusters at all.
Options: reuse as-is and accept that some regions yield nothing; re-run the same Optuna objective on
the subset; or set a separate, explicitly-justified floor. Not decided.

**C4 (open).** Three subjects is too few for a stable voxelwise effect size regardless of C3, and
Optuna's own floor of 5 is not obviously enough either. This is a *statistical* floor, separate from
the clustering parameter, and could be enforced independently.

---

## 5. What each effect-size map is compared against

`input_matrix_stat_map(input_matrix, indices)` masks out `indices` and compares against **all
remaining subjects** (`stats_utils.py:157-159`). So a high-region subcluster is currently tested
against: the other high subclusters, every low-region subject, and everyone neutral.

The stated goal is *different disconnection patterns explaining the same increase or decrease*. Four
candidate references:

| | Reference group | Consequence |
|---|---|---|
| (a) | Everyone else — **current** | Siblings are in the reference, so the component *shared* by two profiles of the same effect is suppressed. Worst fit to the goal. |
| (b) | **Neutral only** (in no extreme region) | Every map means "what distinguishes this profile from typical". High-A, High-B and Low-C maps are mutually comparable, which is the point of decomposing into profiles. |
| (c) | Everyone outside its own extreme group — **Chris's proposal** | Fixes the sibling problem. Reference still contains the opposite extreme, so effect sizes are inflated and each map mixes "what makes A high" with "what makes lows low". |
| (d) | All-high vs all-low | Highest-powered single contrast; answers "is there any imaging difference between the extremes at all". Loses the profile decomposition. |

**Recommendation: (b) as the primary, plus (d) once per target as a summary contrast.**

The power objection to (b) turns out to be negligible: with 5% tails, neutral is ~90% of subjects
against ~95% for (c). It costs essentially nothing and removes the mixed reference.

Both high and low regions are handled symmetrically under (b) — a low subcluster is also compared
against neutral, so its map reads "what distinguishes this low profile from typical" rather than
being contaminated by the highs.

---

## 6. Smaller defects found while tracing

- **D3 — bounding box, not region** (`region_statistical_analyzer.py:293-305`). Each connected
  component is reduced to its min/max corner and every subject inside that rectangle is taken. The
  code says so: *"For simple regions, use all candidates in bounding box (More sophisticated
  point-in-polygon could be added later)."* For a curved or diagonal region this admits subjects
  who are not in the region. The mask is already in hand, so testing membership directly is cheaper
  than the bounding box, not more expensive.
- **D3 — bounding box, and a rectangle is the wrong shape here.** `region_statistical_analyzer.py:293-305`
  reduces each connected component to its min/max corner and takes every subject inside that
  rectangle. Beyond admitting subjects who are not in the region, an axis-aligned box has no meaning
  in a non-linear UMAP embedding — the axes are not interpretable directions, so a rectangle is not
  a neighbourhood of anything. This needs reworking rather than patching. The connected-component
  mask is already computed, so direct membership is both correct and cheaper; the open question is
  what "in the region" should mean for a subject sitting between grid cells.
- **D4 — intent and code disagree on "high correlation".** The intent is *high absolute* correlation:
  a region where position strongly predicts the score, in either direction, is interesting; a region
  near zero is not. The code takes `np.percentile(significance_values, 95)` of the **signed**
  correlation and keeps cells above it (`region_statistical_analyzer.py:278-284`), with the low
  branch reached only for `significance_source == 'prediction'`. So a region at r = −0.8 is
  discarded and a region at r = +0.1 can be kept if the map happens to be mostly negative. The fix
  matching the stated intent is to threshold `|r|` for the correlation source. Cheap; changes which
  regions are analysed.
- **G2 — off by one.** `region_coords / grid_size` maps grid index `grid_size-1` to
  `(grid_size-1)/grid_size`, not to 1.0. Every region→subject mapping is shifted by half a cell.
- **C6 — raw vs rescaled.** HDBSCAN is optimised and fitted on the raw embedding; the grid, the
  regions and the analyzer all live in rescaled coordinates. Under the current **per-axis** rescale
  this is an anisotropic change of metric, so the clusters were selected under a different geometry
  than the maps use. Under the **proportion-preserving** rescale planned in the companion document
  it becomes a similarity transform and the mismatch largely disappears. Cheapest resolution is to
  land that branch first.
- **G1 — two bandwidths.** The correlation grid picks σ at the 25th percentile of pairwise distances
  (`heatmap_stage.py:1348-1351`, chosen for sharper local patterns); the prediction search optimises
  `sigma_gwd` over 0.05–0.2. Two related smoothing scales set by unrelated rules.
- **G3 — constant confidence.** For regression, `grid_creator.py:200-202` assigns
  `confidence = 0.8` to every point, so the `cv_ensemble` aggregation takes the standard deviation of
  identical constants and returns 1.0 everywhere. `all_predictions` (`:226`) holds the real
  between-fold spread and is discarded. The docstring at `:243` already claims the intended
  behaviour ("1 - standard deviation of ensemble predictions"). Currently the only consumer is dead
  code (E4), but the value is saved and plotted.

---

## 7. The dead code

| Symbol | Lines | State |
|---|---|---|
| `run_kernel_heatmap_analysis` (`kernel_regression_utils.py:641`) | ~700 | Imported at `heatmap_stage.py:37`, **never called** |
| `robust_ood_evaluation` (`heatmap_stage.py:1718-2207`) | ~490 | Called only from commented-out lines `:748`, `:861` |
| `train_prediction_models`, `evaluate_models` (`kernel_regression_utils.py`) | — | No callers |
| `run_heatmap_analysis` (`correlation_maps_utils.py:205`) | — | No callers |
| `create_region_statistical_maps`, `apply_two_stage_filtering` | — | Not on the live path |
| `heatmap_stage.py:635-714` | ~90 | Commented out |

> **Risk note — do not act on this table.** "Dead" here was established by grepping for call sites,
> which is necessary and not sufficient: it misses dynamic dispatch, `getattr`, string-named entry
> points, and tests that import by name. ~1400 lines is a large blast radius for a conclusion drawn
> that way. Before any deletion: re-derive the call graph from the code (not from this document),
> check a coverage run over `--core`, grep for the symbols as *strings*, and lift anything worth
> keeping (E2) into a live module or a documented reference file first. Deletion is the last item in
> the sequencing list for this reason.

**E1.** Every hand-rolled kernel CV — `KernelLogisticRegressor` at `:1972`/`:1987`, `KernelRegressor`
at `:2137`/`:2147`, each with its own `np.logspace(-2, 0, 10)` sigma sweep — lives inside
`robust_ood_evaluation`, i.e. inside dead code. The live prediction grid already uses the
Optuna-selected models. So "use the optimised model, not a separate kernel regressor" is already
true of the running system, and the fix is deletion.

**E2 — salvage before deleting.** `run_kernel_heatmap_analysis` contains, at `:1136-1170`, an
explicit `cluster_predict_method ∈ {"fit_predict", "approximate", "kdtree"}`, where `"fit_predict"`
refits a deep copy of the clusterer on the union. That is C1, already written. Lift it before the
file goes.

**E3.** `heatmap_stage.py:635-714` is the commented-out wiring:

```python
# clusterer = context.get("embedding_train_clusterer")
# combined = np.concatenate([full_embeddings, embeddings_labelled], axis=0)
# context["prediction_train_cluster_labels"] = clusterer.fit_predict(combined)
```

C1 and F2 together, switched off. Note C5 before switching it back on.

**E4.** `RegionStatisticalAnalyzer(visualization_threshold=0.2, effect_size_threshold=0.5,
min_cluster_size=3)` — the live method reads only `min_cluster_size`. The other two are read by
`apply_two_stage_filtering`, which the live path does not call, and which applies
`prediction_values >= 0.5` as an **absolute** threshold on whatever scale the target happens to be
on. Dead, but a trap for the next reader.

**E5.** The correlation grid stays model-free. Substituting the trained model would collapse it into
a duplicate of the prediction map, and it would lose the property that makes Tier 1 permutation cheap.

---

## 8. Unlabelled subjects

**F1.** Region membership is decided by coordinates (`region_statistical_analyzer.py:302`). An
unlabelled subject whose coordinates fall in a region is in that region whether or not a score is
predicted for it. Passing unlabelled subjects through the heatmap first therefore adds **nothing**
to the assignment.

**F2.** Adding them by coordinate membership, for the descriptive voxelwise statistics only, is
legitimate and does stabilise the description — more subjects per group means a better estimate of
"what characterises this region". It must not feed back into model fitting or region definition.
The commented-out block in E3 was already set up for exactly this.

**F3.** Selecting them by *predicted* score would be pseudo-labelling where the pseudo-label is a
smooth function of the coordinates and carries no independent information — sharper than the usual
confirmation-bias failure mode ([Arazo et al. 2019](https://arxiv.org/pdf/1908.02983)), and it would
strengthen precisely the artefact in §3.

---

## 9. Cluster belonging for OOD subjects, without refitting

The requirement: a new subject arrives, gets a prediction, and should also be told **which high/low
cluster it belongs to** — with that cluster's stored effect-size map serving as the "driving
factors" a human then interprets ("the commissural disconnection cluster"). The cluster definitions
and their maps must stay fixed, or the description no longer matches what is being described.

**`approximate_predict` is the wrong tool and the observed tightness is real**: it locates the point
in the *unchanged* condensed tree, cannot create clusters, and returns `-1` for anything not clearly
inside one ([prediction tutorial](https://hdbscan.readthedocs.io/en/latest/prediction_tutorial.html)).

**`hdbscan.membership_vector(clusterer, points)` is the tool that matches the requirement.** It
returns, per new point, a probability of membership in each *existing* cluster. The mechanism
combines two things
([soft clustering explanation](https://hdbscan.readthedocs.io/en/latest/soft_clustering_explanation.html)):

1. a **distance** term to each cluster's exemplars, and
2. an **outlier/merge-height** term — where the point would join each cluster in the condensed tree,
   scored GLOSH-style as `max_lambda / (max_lambda - height)`;

then multiplies by `prob_in_some_cluster`, so a point far from everything gets **genuinely low
probabilities across the board** rather than a normalised vector forced to sum to 1. That last step
is the property this feature needs: it can honestly answer *"none of them"*.

`hdbscan.approximate_predict_scores(clusterer, points)` separately gives a GLOSH outlier score per
point — a direct "this subject is unlike the training cohort" flag.

**Availability is not a problem, and no version bump is needed.** hdbscan 0.8.40 is installed and
already exposes `membership_vector`, `all_points_membership_vectors`, `approximate_predict` and
`approximate_predict_scores`. The saved clusterer is already fitted with `prediction_data=True`
(`clustering_utils.py:250`), which is the only precondition. No new dependency, no refit,
definitions untouched.

**On bumping versions to get a less experimental implementation — it would not help, and it is not
free.** Three separate facts:

- The current hdbscan docs still call soft clustering *"new (and still somewhat experimental)"*.
  0.8.44 (vs the pinned 0.8.40) does not change that label; there is no newer, blessed
  implementation to move to.
- **Do not migrate to `sklearn.cluster.HDBSCAN`.** Checked against the installed scikit-learn 1.7.2:
  its public surface is `fit`, `fit_predict`, `dbscan_clustering` and the params helpers — **no soft
  clustering and no `approximate_predict` at all**. Moving there would delete the capability this
  section depends on.
- Bumping `umap-learn` (0.5.9.post2 → 0.5.12) or `hdbscan` (0.8.40 → 0.8.44) is a **scientific**
  change, not a maintenance one. `requirements.txt:7-30` records what happened the last time this
  stack moved: a numba/llvmlite bump left the embedding almost unchanged (pairwise-distance
  correlation 0.994) but **HDBSCAN found 4 clusters instead of 3**, ARI against the baseline
  clustering fell to 0.21 against a floor of 0.95, and every downstream score shifted. "No users
  yet" is a good argument that nothing external breaks; it is not an argument that nothing breaks.
  A bump means regenerating `tests/regression/baselines/` in the same commit, which changes what the
  numerical pinning asserts.

So: bump only for a specific measured gain, and treat baseline regeneration as part of the same
change. Nothing in this document requires one.

**Caveats to state in the output, not to hide:**

- The library calls soft clustering *"still somewhat experimental"* and notes the framework applies
  primarily within the training manifold. A probability is not a guarantee.
- Membership is computed in the **embedding**, so it inherits `umap.transform()`. If the subject is
  off-manifold in *feature* space, transform has already placed it somewhere arbitrary and no
  clustering method can recover from that. The honest check is therefore two-stage:
  **(i) feature-space** — is the transform trustworthy at all (this is the support/boundary problem
  owned by the companion scaling document, and the same check flagged for BBS);
  **(ii) embedding-space** — `membership_vector` + `approximate_predict_scores`.
  Reporting (ii) without (i) will confidently place an unrelated subject inside a cluster.
- Related evidence that distance-to-cluster in an embedding is a workable OOD signal, but needs a
  calibrated reference distribution rather than a raw threshold:
  [Sipple & Youssef 2022](https://arxiv.org/pdf/2203.08549).

**C7 — the rule this forces for unlabelled subjects (§8/F2).** Earlier, F2 proposed letting
unlabelled subjects join region groups to stabilise the descriptive statistics. That is compatible
with a frozen definition **only** if they are *assigned* to already-defined clusters and never
participate in the fit that defines them. Concretely: fit on labelled training subjects → freeze →
`membership_vector` for the unlabelled → include those above a membership threshold in the voxelwise
comparison. If they were instead added to the HDBSCAN fit, the definition would move and every
stored map would describe something else. Threshold choice is open.

**E2 connects here.** `run_kernel_heatmap_analysis`'s `cluster_predict_method ∈ {"fit_predict",
"approximate", "kdtree"}` is the record of this exact question being explored before: refit the
union, use `approximate_predict`, or fall back to nearest labelled neighbour. All three are the
options considered above; **soft membership is the one that was not tried**, and it is the one that
answers the requirement. Worth reading that block before deleting it, and worth recording why the
fourth option wins.

## Open decisions, collected

1. **B2** — which permutation tiers to implement. Recommendation: 1+2 now, 3 as an opt-in mode.
2. **B3** — stop writing `pval_map`, or keep it with a clear "descriptive, not inferential" label.
3. **C4** — the statistical floor on cluster size, and whether the optimised `min_cluster_size`
   (tuned on the whole embedding) transfers to subclustering a small region.
4. **C7** — membership threshold above which an unlabelled subject joins a cluster's statistics.
5. **D1/D2** — reference group. Recommendation: (b) subcluster-vs-neutral primary + (d) all-high
   vs all-low as a summary contrast.
6. **D3** — replace the bounding box with direct mask membership.
7. **D4** — threshold `|r|` for the correlation source, to match the stated intent.
8. **E2/E4** — salvage before deleting; and whether the dead two-stage filter has any future.
9. **A2/A3** — which ADR frame governs, and write the maps' purpose as its own entry.
10. **Ordering** — C6 puts the embedding-scaling branch first; §9 puts the feature-space support
    check before any inference-time cluster reporting.

## Sequencing (proposed)

1. **Proportion-preserving rescale** (companion doc). Unblocks C6 and makes HDBSCAN's metric agree
   with the maps'.
2. **Small corrections**, independently verifiable: C3 (optimised parameters), D3 (mask not bbox),
   D4 (`|r|`), G2 (off-by-one). Each changes which subjects enter a map, so each needs a before/after
   on a real run, not just a passing test.
3. **Permutation tiers 1+2**, replacing the percentile.
4. **Reference group** (D2).
5. **Dead-code audit and salvage** (§7) — last, and planned from the code rather than from this
   document. See the risk note there.
6. **Inference-time cluster reporting** (§9 / D5) — a feature, after the above.
