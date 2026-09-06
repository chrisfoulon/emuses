# EMUSES Architecture Decision Record

## Project

EMUSES (Embedding-based Multi-target Unified Statistical and Estimation System) is a neuroimaging research tool implementing a manifold-learning pipeline for dimensionality reduction, clustering, and prediction of behavioural or clinical outcomes from imaging data. It supports three deployment contexts: local single-user, multi-user lab service, and cloud-native.

---

## 1. Scientific Algorithm Choices

### 1.1 Dimensionality Reduction: UMAP

**Decision**: Use UMAP (Uniform Manifold Approximation and Projection) as the primary dimensionality reduction method.

**Rationale**:
- PCA is linear and cannot model emerging properties from complex non-linear interactions in high-dimensional neuroimaging data.
- UMAP outperforms t-SNE on reproducibility and run time. Becht et al. (2019) compared five methods and found UMAP provides "the fastest run times, highest reproducibility and the most meaningful organization of cell clusters."
- The method is not fixed: UMAP is the current choice, but the architecture is designed so that a different embedding model could replace it without structural changes to the pipeline.

**References**:
- McInnes L, Healy J, Melville J. "UMAP: Uniform Manifold Approximation and Projection for Dimension Reduction." arXiv:1802.03426, 2018. https://arxiv.org/abs/1802.03426
- Becht E, McInnes L, Healy J, et al. "Dimensionality reduction for visualizing single-cell data using UMAP." Nature Biotechnology 37(1):38–44, 2019. DOI:10.1038/nbt.4314

**Code**: `emuses/pipelines/umap_stage.py`, `emuses/tools/UMAP_utils.py`

---

### 1.2 Clustering: HDBSCAN

**Decision**: Use HDBSCAN (Hierarchical Density-Based Spatial Clustering of Applications with Noise) for clustering UMAP embeddings, via nested optimisation with UMAP hyperparameters.

**Rationale**:
- HDBSCAN is density-based and handles clusters of varying densities, which matches the heterogeneous structure of neuroimaging cohorts.
- The McInnes et al. (2017) hdbscan library "allows HDBSCAN to find clusters of varying densities (unlike DBSCAN), and be more robust to parameter selection." Noise points are identified explicitly rather than forced into clusters.
- The hdbscan Python library was developed by McInnes and Healy — the same developers who later created UMAP — making it a natural pairing. Note: the HDBSCAN algorithm itself was originally published by Campello, Moulavi, and Sander (2013).
- HDBSCAN parameters are optimised per UMAP embedding in a nested loop, capturing the embedding-specific optimal clustering without overfitting.

**References**:
- McInnes L, Healy J, Astels S. "hdbscan: Hierarchical density based clustering." Journal of Open Source Software 2(11):205, 2017. DOI:10.21105/joss.00205
- Campello RJGB, Moulavi D, Sander J. "Density-Based Clustering Based on Hierarchical Density Estimates." PAKDD 2013, pp. 160–172. DOI:10.1007/978-3-642-37456-2_14

**Code**: `emuses/pipelines/umap_stage.py`, `emuses/tools/clustering_utils.py`

---

### 1.3 Prediction Models: Multi-Model Optimisation

**Decision**: HeatmapStage explores multiple prediction model types and selects the best via Optuna cross-validation, rather than fixing a single model.

**Rationale**:
- Kernel regression is a simple but powerful baseline (e.g., works well predicting MNIST digit labels from image embeddings), but it may underperform on more complex neuroimaging prediction problems.
- The tool explores multiple model types (kernel regression, ElasticNet, others) and picks the best performing one per target variable and feature type.
- This avoids hard-coding a model choice that may not generalise across research questions.

**Code**: `emuses/pipelines/heatmap_stage.py`, `emuses/tools/kernel_regression_utils.py`, `emuses/tools/optim_utils.py`

---

### 1.4 Feature Extraction: PCA, kPCA, Autoencoder

**Decision**: Support multiple feature extraction methods before prediction modelling: raw features, PCA, kernel PCA (kPCA), Geodesic Warping Distance (GWD), and autoencoders.

**Rationale**:
- PCA is linear and insufficient when relationships between UMAP embeddings and target variables are non-linear.
- Kernel PCA (Schölkopf et al. 1998) extends PCA to non-linear associations via the kernel trick, appropriate for the non-linear UMAP embedding space.
- Autoencoders can model complex non-linear interactions that even kPCA may miss.
- Different feature types work better for different problems; Optuna selects the best combination per target.

**Reference**:
- Schölkopf B, Smola A, Müller K-R. "Nonlinear Component Analysis as a Kernel Eigenvalue Problem." Neural Computation 10(5):1299–1319, 1998. DOI:10.1162/089976698300017467

**Code**: `emuses/tools/ae_optuna.py`, `emuses/tools/models_utils.py`, `emuses/tools/optim_utils.py`

---

### 1.5 Hyperparameter Optimisation: Optuna with Nested Cross-Validation

**Decision**: Use Optuna (TPE sampler) with nested cross-validation: outer loop over UMAP+HDBSCAN hyperparameters, inner loop over prediction model hyperparameters.

**Rationale**:
- TPE efficiently explores large conditional hyperparameter spaces.
- Nesting HDBSCAN optimisation inside UMAP trials ensures clustering quality is evaluated on the actual embedding being produced, not a fixed one.
- Trial counts (default 50 outer, 20 inner) are empirical defaults suitable for testing; they should be tuned to data complexity and available compute resources for real analyses.
- Optuna studies persist to SQLite, enabling resumable optimisation.

**Code**: `emuses/tools/UMAP_utils.py` (`train_and_save_umap_optim_with_nested_clustering`), `emuses/tools/optuna_cv.py`

---

### 1.6 Normalisation Options

**Decision**: Provide robust, z-score, and min-max normalisation for input data and scores, with user selection.

**Rationale**:
- Different datasets have different statistical characteristics. Input data may already be z-scored, making re-normalisation inappropriate.
- Robust normalisation (IQR-based) is preferred when outliers are present.
- Z-score is standard for normally distributed data.
- Min-max is suitable when bounded [0,1] range is required.
- All three are made available to accommodate the variety of neuroimaging data formats researchers use.

**Code**: `emuses/tools/data_preproc.py`, `emuses/pipelines/emuses_pipeline.py`

---

### 1.7 Spatial Statistics: Grids and Thresholds

**Decision**: Use 100×100 grid resolution for spatial analysis; use 5th/95th percentile as significance thresholds.

**Rationale**:
- 100×100 is an empirical choice balancing display quality and enough cells for statistical analysis. It is not used in most of the pipeline, only in heatmap and spatial analysis steps.
- 5th/95th percentile thresholds are a simple heuristic. More elaborate thresholds (e.g., permutation-based) could be implemented in future versions.

**Code**: `emuses/tools/grid_creator.py`, `emuses/tools/region_statistical_analyzer.py`

---

## 2. Architectural Decisions

### 2.1 EMUSES Models Are Atomic Folders

**Decision**: A complete EMUSES model is an entire output folder containing all components trained together: UMAP model, HDBSCAN model, prediction pipeline(s), scalers, and metadata. Components are not separable.

**Rationale**:
- UMAP, HDBSCAN, and prediction models are all trained on the same dataset in sequence. A UMAP from one training run and prediction models from another are not compatible.
- The registry acts as a path lookup service only — it maps model IDs to complete folder paths. It does not abstract or wrap components.
- This constraint was previously violated by a CompleteEmusesModel class that tried to treat components as separable. That violation has been corrected.

**Code**: `emuses/tools/local_model_registry.py`, `emuses/tools/model_io.py`, `emuses/pipelines/inference_stage.py`

---

### 2.2 Context Dictionary as Inter-Stage Communication

**Decision**: Pipeline stages communicate exclusively via a shared `context` dictionary, not via direct method calls or message queues.

**Rationale**:
- Simplicity: all data is in one place, inspectable at any point.
- Flexibility: stages can add arbitrary keys without predefined interfaces.
- Debuggability: complete state can be logged or serialised for reconstruction.
- Standardised key naming (e.g., `embedding_train_features`, `prediction_train_coords`) enforces conventions across the codebase.

**Code**: `emuses/pipelines/emuses_pipeline.py`, all stage classes.

---

### 2.3 Dual-Dataset Mode (classic vs label_dataset)

**Decision**: Support two modes: classic (one fully-labelled dataset) and label_dataset (large unlabelled dataset for UMAP/clustering + smaller labelled dataset for prediction).

**Rationale**:
- Common neuroimaging scenario: large resting-state fMRI cohort available for manifold learning, but only a subset of subjects has behavioural or clinical scores.
- Using only labelled subjects for UMAP training would waste data and bias the manifold.
- Keeping embedding and prediction data separate prevents data leakage: the manifold is learned unsupervised, then prediction models are trained on the labelled subset.

**Code**: `emuses/pipelines/emuses_pipeline.py` (`format_args`, `split_dataset`)

---

### 2.4 Embedding Scaling Saved Separately

**Decision**: UMAP embedding min/max scaling parameters are saved to `embedding_scaling.json` separately from the UMAP model object.

**Rationale**:
- Inference on new data must produce coordinates in exactly the same space as training embeddings, or kernel weights collapse to zero (causing silent identical-prediction failures — this bug was encountered and fixed).
- Storing scaling parameters separately makes them inspectable and independently loadable.
- The UMAP model `transform()` produces raw coordinates; rescaling is a post-processing step that must be applied consistently.

**Code**: `emuses/pipelines/umap_stage.py`, `emuses/pipelines/inference_stage.py`

---

### 2.4b Two Coordinate Systems On Disk; `space` Is a Required Argument

**Decision**: A run folder stores embeddings in two different coordinate systems, and
the way to read them is `emuses.tools.embedding_spaces.load_embeddings(run_dir,
space=...)`, where `space` is keyword-only with **no default**.

| artefact | space |
|---|---|
| `embeddings.npy` | **raw** — UMAP's own output |
| `test_embeddings.npy` | **rescaled** — per-axis onto [0, 1] |

**Rationale**:
- The asymmetry is a consequence of write order, not a decision: `umap_stage` saves the
  training array before it rescales and the test array after. Renaming the artefacts was
  rejected — the regression baselines pin `_embedding_distances` computed from raw
  `embeddings.npy`, so changing what that file holds invalidates them (§2.9d).
- **Mixing the two does not raise.** Per-axis rescaling is idempotent, so a double
  conversion returns the array unchanged, and comparing raw against rescaled yields a
  plausible number rather than an error. Measured 2026-09-05: recovering the swiss-roll
  parameter scored r = 0.2747 with train (raw) against test (rescaled) and r = 0.9989
  once both were in one space. The low value reads exactly like a real negative result;
  it cost two wrong conclusions in one session before the cause was found.
- A required `space` argument converts a silent misreading into a `TypeError` at the
  call site. That is the entire mechanism — there is no runtime signal to detect it
  after the fact.
- `embedding_scaling.json` additionally records `mode`, `margin`,
  `embeddings_npy_space` and `test_embeddings_npy_space`, so a folder describes its own
  conventions to whoever opens it later. Additive; array contents unchanged.

**Two rescaling modes exist and are not interchangeable**, both reached through
`rescale_embedding`: *per-axis* (presets passed as arrays, what the pipeline uses; each
dimension independently spans [0, 1], aspect ratio not preserved) and *global* (presets
omitted, what `EmbeddingSpace` uses; one scalar min/max, proportions preserved). Both are
called "rescaled embeddings" in the code. `mode` in the JSON disambiguates.

**Single implementation**: `rescale_embedding` / `inverse_rescale_embedding` live in
`emuses/tools/embedding_spaces.py` (numpy-only, so scripts and light test runs can reach
the conversions without importing umap/matplotlib/statsmodels) and are re-exported from
`emuses_utils` for the existing call sites.

**Code**: `emuses/tools/embedding_spaces.py`, `tests/unit/test_embedding_spaces.py`

---

### 2.4c The Run That Trained a Morphospace Owns Its Scaling Factors

**Decision**: `UMAPStage` computes the [0, 1] factors from its own embedding **only when
it trained the morphospace**. Every reuse route — `--load_umap`, `--load_embeddings`,
and resuming into an existing output folder — reads the source run's
`embedding_scaling.json` through `embedding_spaces.load_scaling()` and writes it out
again unchanged. A reuse route pointed at a folder with no such file **raises**; it does
not fall back to recomputation. (Closes the gap recorded as open in §2.4b, 2026-09-06.)

**Rationale**:
- The factors are not a summary of the coordinates, they *are* the coordinate system.
  A kernel bandwidth, a grid cell and a region boundary all mean something only relative
  to them.
- On a reuse route the coordinates in hand are *this* cohort pushed through *that*
  model. Recomputing redefines [0, 1] against whoever happens to be in this run, so the
  same subject lands somewhere different depending on its neighbours, and inference —
  which reads the file rather than recomputing — disagrees with the training run it was
  fitted on.
- Nothing errors when this goes wrong. Min-max rescaling a valid embedding always yields
  a valid embedding in exactly the expected range, so the run completes and answers a
  different question. Hence a raise on the missing-file case: a silent fallback here
  reproduces the defect.

**Three mechanisms existed for carrying these factors; two were dead**, and each had a
passing test that made it look wired:

1. `umap_model.min_embeddings_` / `max_embeddings_`, read with `getattr` in
   `inference_stage`. Nothing in `emuses/` ever set them — the only assignment in the
   tree was on a `Mock` in `tests/inference/test_normalization_validation.py`. In
   production the read returned `None`, so **pipeline-integrated inference skipped the
   rescale entirely** and fed raw coordinates to predictors fitted on rescaled ones.
2. Context keys `embedding_train_min_coords` / `embedding_train_max_coords`, published
   by `umap_stage` and read by no stage. Asserted only in
   `tests/inference/test_normalization_analysis.py`, against a context that test built
   itself.
3. `embedding_scaling.json` — the live one, and now the only one.

**The generalisable lesson, which is why this has a structural test rather than a note**:
a test that constructs its own input can validate a *consumer* while no *producer*
exists. It proves "if X were set we would use it"; it never proves "X is set". Review
does not catch it, because every individual site reads correctly.
`tests/test_scaling_single_source.py` asserts, by AST, that the banned attribute names
appear nowhere and that no stage writes a context key nothing reads. Fourteen
pre-existing write-only keys are listed there as known debt, not endorsed.

**Code**: `emuses/pipelines/umap_stage.py`, `emuses/pipelines/inference_stage.py`
(`_scaling_dir` / `_read_scaling_into`, one reader replacing three hand-rolled JSON
parses), `tests/test_reused_morphospace_keeps_its_scaling.py`,
`tests/test_scaling_single_source.py`

---

### 2.5 InferenceStage as a Separate Stage

**Decision**: Inference is implemented as a standalone `InferenceStage` class, not as a method of `EMUSESPipeline`.

**Rationale**:
- Training and inference are fundamentally different workflows: training optimises and fits; inference loads and applies.
- Separation keeps each class focused and independently testable.
- InferenceStage can be composed into a minimal pipeline without the full training scaffolding.

**Code**: `emuses/pipelines/inference_stage.py` (1600+ lines handling full inference workflow)

---

### 2.5b One Inference Result Shape; the Pipeline Normalises, the Stage Does Not

**Decision** (2026-08-24, Phase 4): three contracts around `InferenceStage`, each of which had drifted
and cost failures:

1. **`_predict` always returns `target_results`.** Single-target is the n=1 case; there is no flat
   `ensemble_predictions` at the top level, including in the "no prediction models" and "no targets"
   branches. Every consumer — `_format_results`, `run()`, `_save_results`, the HTTP endpoints —
   indexes `results['target_results'][target]['ensemble_predictions']`.
2. **Normalisation happens exactly once, in `EMUSESPipeline`.** In inference mode it loads the
   model's `input_scaler.joblib` and applies it, so the features in the context are already in the
   training input's space. `InferenceStage._transform_features` forwards them to UMAP untouched.
3. **`InferenceStage` reads `inference_features` / `inference_labels`, never `prediction_test_*`.**
   `HeatmapStage` chooses *which* split to hand over (test or train) and copies it into the handover
   keys. A context holding only the raw split keys is refused, loudly.

**Rationale**: two result shapes for one method is what made `/api/v1/inference` answer 200 with
`predictions: []` (Phase 1F) and what made a no-models run die with `KeyError: 'target_results'`.
Normalising in both the pipeline and the stage scales the data twice and collapses the UMAP transform
— the failure behind the withdrawn "constant predictions" claim (§3.1b). Letting the stage prefer
`prediction_test_features` would silently override HeatmapStage's choice of split.

**Code**: `emuses/pipelines/inference_stage.py`, `emuses/pipelines/emuses_pipeline.py` (~line 470),
`emuses/pipelines/heatmap_stage.py` (~line 784). **Guards**: `tests/inference/test_normalization_fix.py`
(including a double-normalisation guard), `tests/pipelines/test_inference_stage_context_integration.py`,
`tests/flexible-inference-stage/test_semantic_aliasing.py`. Triage:
`dev-docs/issues/phase4_science_path_triage.md`.

**Also removed**: `EMUSESPipeline(args, inference_data=...)`. The parameter was stored and never read
— `inference_mode` on the args plus `emuses/pipelines/inference_runner.py` is the one path.

---

### 2.5c One-vs-Rest Ground Truth Is Expanded at the Handover, Using Training Classes

**Decision** (2026-08-25): when `--classification` expands a multi-class label column into
one-vs-rest targets, `HeatmapStage` must expand the **ground truth** the same way before copying it
into `inference_labels`, and must additionally report a single multi-class score.

**The defect this fixes.** The expansion was a local variable `Y` inside the training loop. The test
split was handed over as the original single class column, so `InferenceStage` compared *n* prediction
columns against *one* ground-truth column,
`_calculate_multi_target_validation_metrics` hit its `shape[1] != len(target_results)` branch and
returned `None`. Measured on the digits run (2026-08-25): exit 0, a `validation_metadata.json`
containing only timing, and **no held-out performance at all** — from one WARNING line
(`Ground truth dimensions (1) don't match target count (10)`) inside a 3.7 MB log. The true accuracy,
computed by hand from the predictions CSV, was 0.9750. This is the project's recurring signature: the
run looks successful and the result is silently absent.

**Two constraints that are not optional:**

1. **Expand with the classes seen in *training*, never recomputed from the split being scored.** A
   split missing a class yields a shorter `np.unique` and shifts every column past the gap — the
   metric is still produced and is silently wrong, which is strictly worse than the missing metric it
   replaces. Rows carrying an unseen class are all-zero across every column and are logged.
2. **Order targets numerically, not lexicographically.** `sorted()` places `target_10` before
   `target_2`, so from ten targets upward every prediction column pairs with the wrong class. Ten
   classes (digits) is exactly where this begins to bite. `_order_targets` exists for this.

**A multi-class score is reported alongside the per-target ones.** The per-target binary metrics
answer "does this class-vs-rest model separate its class", which is not what a multi-class run is
asking. `_calculate_multiclass_validation_metrics` takes the argmax across the per-class columns and
scores the recovered class directly, and counts rows where nothing fired or two classes tied, since
argmax resolves both by column order and would otherwise hide them.

**Validation metrics report balanced accuracy, not only accuracy**, because training optimises
balanced accuracy (`optuna_cv.py:41`). On a one-vs-rest target roughly 10 % of rows are positive,
where a model that always answers "no" scores 0.90 on plain accuracy and 0.50 on balanced — reporting
only the first makes a degenerate fit look strong, the same family as §3.1b.

**Code**: `emuses/pipelines/heatmap_stage.py` (`_expand_ovr_labels`, the handover block),
`emuses/pipelines/inference_stage.py` (`_order_targets`,
`_calculate_multiclass_validation_metrics`). **Guards**:
`tests/inference/test_multiclass_holdout_metrics.py` (13 tests, including the missing-class
misalignment trap and the `target_10`/`target_2` ordering). Verified against an oracle computed
independently *before* the fix existed: 0.9750 accuracy, 351/360, on the digits run.

---

### 2.6 Scores Handled Separately from Imaging Features

**Decision**: Behavioural/clinical target variables (scores) are loaded and processed via a dedicated path, separate from imaging features throughout the entire pipeline.

**Rationale**:
- Scores and imaging data have different scales, distributions, and missingness patterns.
- Scores typically contain 1–10 variables; imaging features may be thousands.
- Separate handling makes preprocessing independent and transparent.
- Scaler for scores is saved separately (`scores_scaler.joblib`) and loaded independently during inference.

**Code**: `emuses/pipelines/emuses_pipeline.py` (`load_and_process_scores`)

---

### 2.7 Input File List (--input_file_list)

**Decision**: Support `--input_file_list` for specifying datasets as a list of file paths rather than a directory.

**Rationale**:
- HPC environments and BIDS datasets commonly deliver data as manifest files, not directories.
- Researchers may need to select arbitrary subsets of a larger dataset.
- The flag enables EMUSES to integrate directly into HPC workflows without requiring directory reorganisation.

**Code**: `emuses/pipelines/emuses_pipeline.py` (`process_dataset`), `emuses/cli/main.py`

---

### 2.8 File-Based Model Persistence

**Decision**: Store models as joblib files alongside JSON manifests and NPY arrays.

**Rationale**:
- joblib handles complex nested sklearn pipeline objects reliably.
- File-based storage requires no database for local use.
- Models are self-contained and portable across deployment modes (local → lab → cloud).
- JSON manifests carry metadata (training config, random seeds, Optuna study info) alongside the model.

**Constraint**: not suitable for distributed or concurrent write scenarios without additional locking.

**Code**: `emuses/tools/model_io.py`

---

### 2.8b Artifact Names Carry the Run Prefix; Validation Resolves It

**Decision**: The registry's completeness check resolves the run prefix from
`log/arguments_*.json` rather than assuming default file names or globbing for them.

**Rationale**:
- Training applies `--prefix` to its outputs: `myrun_embeddings.npy`, not `embeddings.npy`
  (`UMAP_utils.py`, `train_and_save_umap_optim`). The validator previously required the
  unprefixed names, so **every model trained with a prefix was rejected as "not a complete EMUSES
  training folder" and could not be registered**. Fixed 2026-08-06.
- The prefix is not recorded in the manifest, and `file_integrity` lists only joblib files. The
  arguments log is the only place it survives.
- Globbing `*embeddings.npy` is **not** an acceptable shortcut: `test_embeddings.npy`,
  `best_embeddings.npy` and `unlabeled_embeddings.npy` are all real outputs and none of them is the
  training embedding matrix, so a glob would accept a folder that is missing the training data.
- This resolves names only. It does not weaken what a complete folder must contain, and so does not
  reopen the §2.1 atomicity constraint.

**Code**: `emuses/tools/model_io.py` (`_resolve_artifact_prefix`,
`_validate_emuses_folder_structure`), `tests/model_registry/test_prefixed_model_validation.py`

---

### 2.8c Output Paths Are Validated Before the Directory Is Created

**Decision**: The CLI validates a user-supplied output folder with `validate_path` at the single
point where it would create it, and refuses rather than sanitising.

**Rationale**:
- `save_command_to_output_folder` calls `output_folder.mkdir(parents=True, exist_ok=True)` and was
  the first statement of `full()`. The CLI therefore created any directory it was handed. Running
  the security test suite produced directories literally named `$(whoami)_output` and
  ``` `cat /etc/passwd` ``` in the working directory, nine of which reached git.
- Nothing was executed — those names are inert on disk — but they are hostile to any later unquoted
  shell expansion, and a Windows checkout cannot represent several of them.
- The guard lives at the creation site, not at each of the four command entry points, so a new
  command cannot forget it.
- **Refuse, don't sanitise.** Silently rewriting a researcher's output path would put results
  somewhere they did not ask for, which is worse than an error for a scientific tool.

**Constraint**: `validate_path` rejects `;`, `&&`, `||`, `|`, `&`, backticks, `$(`, traversal, and
sensitive system directories. None appear in legitimate research paths, but `/root/` is among them,
so running as root with an output folder under `/root/` is now refused.

**Code**: `emuses/cli/main.py` (`validate_output_folder`), `emuses/cli/security.py`
(`validate_path`), `tests/enhanced-cli-typer/test_security_validation.py`

---

### 2.9 Reproducibility: Hierarchical Random Seeds

**Decision**: Derive component-specific random seeds from a master seed (`--random_state`) using
`numpy.random.default_rng`, and persist all seeds to `random_seeds.json`. **This is the only seeding
mechanism in EMUSES.** Anything that needs randomness takes its seed from this derivation; do not
introduce a second scheme, and do not hardcode a seed at a call site.

**Rationale**:
- Reproducibility is required for scientific publication. *Bitwise* reproducibility across machines
  is explicitly out of scope (see §2.9b); reproducibility of a rerun on one machine is not.
- Separate seeds per component (UMAP, clustering, prediction, CV, Optuna) allow individual component
  reproduction.
- Persisting seeds to a JSON file makes them citable and inspectable by reviewers.

**The decision was made in 2025 but only implemented for the UMAP and clustering stages.** On
2026-08-23 the prediction path was found disconnected from it at five points, which is why two
identical invocations at `--random_state 42` produced identical embeddings and different prediction
scores. Fixed in `687f7a9` and `4152635`:

1. `nested_optuna_cv` created its Optuna study with no `sampler`, so it got `TPESampler(seed=None)`.
   Each outer fold now takes its own seed derived from `optuna_seed` — a single shared seed would
   make every fold replay the same TPE startup trials, correlating outer scores that are supposed to
   be independent estimates.
2. `_optimise_target` never passed `random_state` to `nested_optuna_cv`, so CV folds always used the
   hardcoded default of 42 and `--random_state` did not reach them.
3. `build_estimator` hardcoded `random_state=42`; `LogisticRegression(solver="saga")` shuffles.
4. `PCAGWD` / `KernelPCAGWD` were unseeded.
5. `optimize_ae_pretraining` had an unseeded study and a caller passing `random_state=42`.

**The PCA case is the one to remember.** `PCA(svd_solver="auto")` only switches to the *randomized*
solver once `max(X.shape) > 500`, and the GWD kernel matrix is n×n in the number of samples. An
unseeded `PCAGWD` is therefore perfectly reproducible on `test_data`'s 50 samples and irreproducible
on a real cohort — the defect is invisible to the test data by construction and appears first on the
runs worth publishing. It is fixed by seeding, not by pinning `svd_solver="full"`, which would cost
O(n³) on exactly the large inputs the randomized solver exists for.

**Enforced invariant**: no `optuna.create_study` anywhere in `emuses/` without an explicit `sampler`.
No exemptions — a study whose result is only logged still costs one line to seed. Guarded by
`tests/test_seed_wiring.py::test_no_unseeded_optuna_study`.

A weaker companion guard checks that every key in `random_seeds.json` is read somewhere. It is
documented as weak in its own docstring, because it would **not** have caught the above:
`prediction_seed` and `cv_seed` already had readers in `robust_ood_evaluation` while the main
prediction path ignored them. Only `optuna_seed` was derived and read by nothing.

**Known residual**: `load_if_exists=True` with RDB storage means a *resumed* study still diverges —
the sampler is re-seeded while the trial history is not. Related to §3.2.

**Code**: `emuses/pipelines/emuses_pipeline.py` (`__init__`), `emuses/pipelines/heatmap_stage.py`
(`_seeds_from`, `_optimise_target`), `emuses/tools/optuna_cv.py`, `emuses/tools/models_utils.py`,
`emuses/tools/features_utils.py`, `emuses/tools/ae_optuna.py`

### 2.9c Optuna Parallel Search Forfeits Reproducibility; Serial Is the Default

**Decision**: `umap_jobs` / `hdbscan_jobs` default to **1**. Parallel Optuna search is available as
an explicit opt-in that warns it forfeits reproducibility.

**Rationale**: `optuna.study.optimize(n_jobs>1)` runs trials concurrently, so TPE's suggestion
depends on which trials have completed when each one asks — thread timing. Seeding the sampler does
not help, and EMUSES does seed it (`UMAP_utils.py:633`). Measured 2026-08-23, three repeats at seed
42 with one variable changed: jobs=4 gave 10 of 20 metrics identical, jobs=1 gave 20 of 20
(`dev-docs/issues/reproducibility_tolerances_2026_08.md`).

Reproducibility wins because EMUSES exists to produce results people publish. A faster search that
cannot be rerun is worth less than a slower one that can.

**Trap worth knowing**: CLI runs were reproducible before this decision *by accident* — the CLI forks
a service, so `is_subprocess_context()` is True and `get_safe_n_jobs()` clamps jobs to 1. Moving
local execution in-process (§4, Phase 1B2) removes that clamp and would have silently made CLI runs
nondeterministic.

**Related trap**: `optim_dict_hcp` and `optim_dict_test` have every parameter fixed, and
`UMAP_utils.py:430` deliberately collapses to a single trial in that case. Raising `umap_trials`
against them changes nothing, and a config built on them cannot exhibit search nondeterminism at
all — which is why the test fixture showed perfect reproducibility while the problem was live.

**Implemented 2026-08-23** (`bec42c9`). Three things surfaced while doing it:

- `umap_jobs` was *already* serial, by a `None -> 1` mapping inside `UMAPStage` rather than by
  declaration. A default nothing declares is a default nothing guards. There is now one place that
  decides search parallelism, `umap_stage._resolve_search_jobs`.
- **`hdbscan_jobs` is inert.** `train_and_save_umap_optim_with_nested_clustering` takes
  `parallel_mode="umap"` and no caller overrides it, so `inner_n_jobs` is only read in the
  `"hdbscan"` branch; the inner search always runs at `inner_optimize_hdbscan`'s own `n_jobs=1`.
  Decided to document and guard it rather than wire or remove it — the same treatment as the five
  `NOT_IMPLEMENTED` CLI options. `tests/test_search_jobs_default.py` fails if anyone wires
  `parallel_mode`, so the decision gets revisited rather than drifted past.
- **`--help` claimed the opposite of the truth.** The `--random_state` help text, the
  `PipelineConfig` comment and the `UMAP_utils` docstring all said that setting a seed forces UMAP
  `n_jobs` to 1. Nothing does. The confusion is understandable — UMAP's *own* `n_jobs` is overridden
  when seeded, and it warns so — but optuna's is not, and optuna's is the one that decides the
  search.

**`hdbscan_core_dist_n_jobs` is exonerated** (re-measured 2026-08-23 at the regression config, 3
clusters, 20/20 identical across 1 vs −1). The first measurement ran on an all-noise clustering and
was recorded as weak evidence; that caveat is closed.

### 2.9d What Is Pinned Numerically, and at What Tolerance

**Decision**: `tests/regression/` pins prediction scores, composite score, the UMAP/HDBSCAN metrics,
cluster count, cluster structure and embedding geometry, on **its own config**
(`tests/regression/regression_config.py`) rather than the shared `emuses_pipeline_results` fixture.

**Rationale for the separate config**: the shared fixture runs `optim_dict_hcp`, which returns zero
clusters with all 40 points labelled noise. An adjusted Rand index between two all-noise labellings
is 1.0 by construction, so a cluster assertion there could never fail. The regression config is the
`midbudget-serial` arm — the only measured config that is both reproducible (20/20 over three
repeats) and non-degenerate (3 clusters, `noise_fraction` 0.1). `test_baseline_is_not_degenerate`
fails if it ever drifts back.

**Rationale for the comparison forms**: cluster ids are arbitrary, so structure is compared by
adjusted Rand index rather than label equality. UMAP is defined only up to rotation and reflection,
so embeddings are compared through pairwise distances, never coordinates.

**Where the tolerances come from**: `dev-docs/issues/reproducibility_tolerances_2026_08.md`. Local
run-to-run variation is exactly **zero** on every metric, so every float tolerance is a *chosen*
cross-machine allowance (per §2.9b), not a measured one, and each is labelled as such in the test
file. `rtol=1e-3` on prediction scores (the CSVs are written to 4 dp), `rtol=1e-6` on the search
metrics, ARI ≥ 0.95, distance correlation ≥ 0.999, cluster count exact. **They are not
cross-machine allowances in practice** — see the same-machine paragraph below, added 2026-09-05
after the first real cross-machine measurement showed the failure is not of a kind tolerance can
absorb.

**Regenerating a baseline is a deliberate act** recorded in the commit message. A missing baseline
fails rather than being written silently, otherwise the suite ratchets to whatever the code
currently does. Each baseline records the config that produced it and fails if the two drift apart.

**This is a same-machine instrument, and CI does not gate on the numbers** (decided 2026-09-05).
Every test comparing a recorded value carries `machine_specific`; CI runs
`dev_test_runner.py --core --foreign-machine`, which deselects them. Measured, with both sides on
identical pinned versions and the same seed: this machine reproduces the baseline **exactly**, the
GitHub runner does not. The mechanism is amplification through an argmax — numba compiles UMAP's
kernels for the host CPU, the embedding shifts in its last bits (distance correlation 0.990299),
that crosses an HDBSCAN boundary (3 → 4 clusters), every Optuna trial's score changes, and **a
different trial wins**; `composite_score` 0.4914 → 0.5297 is then a different quantity, not a
drifted one. No tolerance covers an argmax flip. §2.9b already put bitwise-across-platforms out of
scope; what is added here is that "not bitwise" does **not** degrade gracefully into "within
tolerance" once a search selects on the result.

The distinction is measurable, which is why the tolerances stay tight rather than being widened:
varying only the master seed on one machine gives distance correlation 0.043–0.176 and cluster ARI
≈ 0, two orders of magnitude away from the 0.990 a different CPU produces. On 40 samples this
config has **no stable cluster structure across seeds at all**, so the route to a genuine
cross-machine gate is a config whose search converges to the same optimum from either side of a
last-bit perturbation — not a looser floor, which would make the assertions pass on anything.

**The cost, stated plainly: a green PR does not mean the numbers held.** Numerical pinning is
enforced by the developer's pre-push `--core`. To stop CI deselecting its way to a fast green that
executes nothing, `test_pipeline_produces_the_expected_outputs` is deliberately *not*
`machine_specific`: it compares the output's **shape** against the baseline and never a value, so
CI still runs the pipeline and catches a stage that stopped writing, a metric dropped from the
search, or an embedding that changed dimensionality.

**Baselines record their provenance** (added 2026-09-05, `tests/regression/regression_provenance.py`):
`llvm_cpu_name` — the codegen target, the prime suspect — plus a digest of the CPU feature flags,
Python version, platform, and the numerical stack versions. Every numerical failure appends a diff
against the current environment, so it states either "identical to the baseline's, this is a code
change" or exactly which of those moved. Recording only *what* the numbers were, and nothing about
where they came from, is what made the 2026-09-05 diagnosis cost a day.

**Worth knowing before trusting a pass**: a one-line production change (UMAP model seed shifted by
one) failed the composite score, cluster structure and embedding geometry — while prediction scores
and cluster count did **not** move. Pinning only "the number that matters" would have missed a real
change to the science.

**The `--regen-baselines` option must stay in `tests/conftest.py`** (fixed 2026-08-25,
`fix/regression-conftest`). pytest honours `pytest_addoption` only from *initial* conftests, and
with `testpaths = tests` a subdirectory conftest is not one. While the hook lived in
`tests/regression/conftest.py` — beside the fixtures that read it, which is where it looks like it
belongs — this entire suite **did not execute** under a bare `pytest`: all 14 tests died at setup
with `ValueError: no option named 'regen_baselines'`. Measured at one commit: 14 passed as
`pytest tests/regression/`, 14 errors as `pytest`.

That is the failure mode this section exists to prevent, arriving through the test harness instead
of the science: the guard reported `error`, not "regression detected", inside a suite already
carrying ~150 known failures, so it read as one more piece of known breakage. Restoring it was
verified by perturbation — a drifted baseline now fails the **whole-tree** run naming the metric.
`tests/test_pytest_option_registration.py` fails if the hook is ever moved back down.

**Every install path uses `pip install --no-deps`, and that is a decision, not a shortcut**
(recorded 2026-09-05). `gpy` 1.13.2 declares `scipy<=1.12.0`; the pipeline pins scipy 1.17.1
because that is what the baselines were validated against. The bound is conservative rather than
real — measured against 1.17.1, `GPRegression` fits and predicts finite values with positive
variance and `SparseGPClassification` trains — and it **cannot be resolved away**: `gpy` 1.14.2
drops the bound but requires `paramz>0.9.6`, and the only such `paramz` (0.10.0) requires
`numpy>=2` against our pinned 1.26.4. No `gpy` release accepts both. Any tool that *resolves*
rather than installing the pinned set therefore fails by construction, which is exactly how the
`Dockerfile`'s `pip-sync` behaved — it had never once succeeded. Moving to numpy 2 to clear this
is a baseline-regeneration decision, not a dependency fix.

**`requirements-prod.txt` is derived from `requirements.txt`, not compiled beside it.** It was an
independent compiled lockfile until 2026-09-05 and it rotted invisibly, because its only consumer
was a Docker build that had never succeeded: 46 packages that `requirements.txt` carried were
missing from it, including the whole authentication stack, and it pinned `numba` 0.61.2 /
`llvmlite` 0.44.0 against the validated 0.62.1 / 0.45.1 — the compiled-kernel path this very
section is about. An image built from it would have run the pipeline on a stack no baseline had
ever seen. It is now `-r requirements.txt` plus the handful of server-only packages, so the two
cannot diverge; `pip-compile requirements-prod.in` must not be run. The general rule this
instantiates: **two lockfiles that must agree should not be two lockfiles.**

### 2.9e The Backend Override Is Per-Context, Not Process-Wide

**Decision**: `parallelism_utils._FORCED_BACKEND` is a `contextvars.ContextVar`, and
`parallelism_backend()` unwinds it with `ContextVar.reset(token)`. It was a plain module global with
save/restore until 2026-08-25.

**Rationale**: save/restore is correct only under strict LIFO unwinding. Two pipeline runs
overlapping in one interpreter break it — the first to *exit* restores the value it captured before
either started, and the run still in progress falls back to auto-detection, which in a main process
is **loky**. Nothing raises and no number changes; the run just takes several times longer, because
loky re-imports the scientific stack in every worker (measured: a ~110 s test still going past 300 s
with eight `LokyProcess` workers alive). That is a defect whose only signature is a slow run, which
is close to unattributable after the fact.

**Why it was not already failing**: nothing overlaps today, because
`PipelineRunner._run_pipeline_in_process` is a synchronous call inside an `async def` and blocks the
event loop for the whole run, so a second `asyncio.create_task` job cannot start. That is a side
effect of blocking code in an async function, not a decision, and the obvious tidy-up — moving it to
`run_in_executor`, a pattern already present in `stage_runners.py` — would silently remove the
protection. The same blocking call also makes `asyncio.wait_for(..., timeout=pipeline_timeout)` in
`execute_pipeline` inert; see the note at that call site.

**Consequence, accepted**: a newly spawned *thread* starts with a fresh context and sees the default
rather than its parent's override. Every path from the scope in `pipeline_runner.py` to the four
`create_safe_parallel` call sites is synchronous and single-threaded (verified 2026-08-25), so this
does not arise. If a stage ever hands joblib work to a thread of its own, that thread must enter the
scope itself. `tests/tools/test_parallelism_utils.py::test_a_new_thread_does_not_inherit_the_override`
pins this so it is a decision and not a surprise.

**Where loky still runs**: nowhere in a shipped run, and now for a simpler reason than when this was
written. A CLI-side scope was added to `_execute_inference_locally` on 2026-08-25 because it was the
one pipeline execution not going through the service; Phase 1F (PR #9) then deleted that function
outright, so inference submits to the service like everything else and is covered by the single
scope in `pipeline_runner.py`. The CLI-side scope was dropped in the merge rather than carried
forward — there is **one** place that forces the backend, matching ADR §4's one execution path.

loky remains the auto-detect default in a main process, so it is what `tests/regression` runs on,
since that drives `EMUSESPipeline` directly. **The two backends have never been compared
numerically** — the baselines were generated through the same loky test path, so they do not test
the difference.

**Do not** replace this with `joblib.parallel_backend`. EMUSES never calls it, deliberately: the
override is meant to steer `create_safe_parallel` only, and sklearn's internal joblib calls pin
`n_jobs=1` on purpose (`optim_utils.py`: "Use 1 here since we parallelize at the Optuna level").

### 2.9b Bitwise Reproducibility Is Out of Scope

**Decision**: EMUSES targets reproducibility within a machine and environment, verified against
*measured* tolerances, not bitwise identity across platforms.

**Rationale**: parallel floating-point reductions are not associative, so results legitimately differ
with thread count and BLAS build. Chasing bitwise identity would mean forcing single-threaded
execution everywhere, at a large and permanent performance cost, to remove differences that are below
scientific significance. Tolerances are to be derived from measurement and cited where they are
pinned, rather than guessed.

**Do not re-litigate this.** It was decided deliberately after the alternative was considered.

### 2.11 Pipeline Commands Share One Option Declaration; `heatmap` Cannot Run Standalone

**Decision (2026-08-23, Phase 1C).** `full`, `umap` and `heatmap` take their CLI options from a
single declaration in `emuses/cli/pipeline_options.py`, stamped onto each command by
`@with_pipeline_options`. Typer builds its CLI from `inspect.signature()` and honours a
programmatically assigned `__signature__` (verified against typer 0.19.2), so the options stay
ordinary readable Python in one place rather than three lists that drift.

**Why not three copies.** `umap` and `heatmap` previously declared only `output_folder` and
`input_dataset` — every other flag worked on `full` and did not exist on the other two. Copying
`full`'s block twice would have fixed the symptom and reproduced the Phase 1A defect (options
accepted and silently discarded) in three places instead of one. `tests/test_cli_option_mapping.py`
pins that all three commands expose exactly the shared set, and that each command's signature *is*
the shared object.

**`emuses heatmap` standalone is unsupported, by architecture rather than omission.** `HeatmapStage`
fits prediction models against UMAP embedding coordinates (`prediction_train_coords`), which only
`UMAPStage` produces. `--load_umap` and `--load_embeddings` are both read by `UMAPStage`, so a
heatmap-only run cannot obtain its input by any route. It fails fast with a message naming the
missing context key, the stage that produces it, and `emuses full` as the working command. Do not
"fix" this by loosening the check — the correct resolutions are to make `heatmap` imply UMAP, to
teach HeatmapStage to load a trained model, or to remove the command. That is a product decision and
is deliberately still open.

**Consequences.** Unsupervised runs are now a real path: `split_dataset` no longer passes
`self.scores` into `train_test_split` when there are no scores, and `InferenceStage` is only added
when `HeatmapStage` ran, since it exists to validate that stage's models. `PredictionStage` is
retired and no longer advertised anywhere (`app.py` `valid_stages`, `service_client.py`
`valid_types`, `main.py` `stage_classes`); requesting it is rejected rather than accepted and failed
at run time. The service defines `/api/v1/jobs/pipeline/{umap,heatmap}` as thin aliases onto the
stage endpoint, not copies of it.

**Update (2026-09-04): `--load_umap` now genuinely works.** This entry previously rested on the flag
existing; it did not. `--load_umap` was declared in `cli/pipeline_options.py`, stored on
`PipelineConfig`, plumbed through `pipeline_runner`, and named by `HeatmapStage`'s own refusal
message as the remedy — while **no code read `config.load_umap`**, so a run that asked to reuse a
morphospace silently retrained one. It is now handled first in `UMAPStage.run`, ahead of the
implicit output-folder detection, and raises rather than falling back to training when the path is
missing: reusing a specific morphospace and building a new one are different experiments, and
silently substituting the second is how a run looks successful while answering another question.
The standalone-`heatmap` decision above is **unchanged and still open**.

### 2.12 An N-Dimensional Embedding Is Refused at Configuration Time, Not Discovered at Grid Time

**Decision**: UMAP may be configured to produce any `n_components`, and a **UMAP-only run with an
N-D morphospace is supported**. A run that also enables a stage requiring 2-D (currently the
heatmap) is **refused before anything is trained**, by
`emuses/tools/embedding_dimensionality.py`, with a message naming the optim_dict to change and
`emuses umap` as the working alternative.

**Rationale**: UMAP and the prediction search are dimension-agnostic; `GridCreator` and
`CorrelationGridCreator` are not, and already raised `ValueError` on `d != 2`. That check was
correct and nearly worthless: it fired **per target, after the full nested-CV search** (~19 h on
`DSD_repro`), and `heatmap_stage.py` caught bare `Exception` at both grid call sites *and* around
the whole grid section — so an N-D run **completed with exit 0 and no heatmaps**, announced only by
error lines inside a multi-MB log. The defect was never the missing check; it was the placement and
the four handlers above it. `HeatmapStage` therefore carries the check independently (for direct
drivers such as `tests/regression`), and `HeatmapStage.run` re-raises `EmbeddingDimensionalityError`
specifically while still tolerating genuine grid failures, which it is right to survive.

**Do not resolve a refusal by loosening the check.** Making the heatmap N-D is a design question.
Two measured facts (2026-09-04) that a future reader will otherwise re-derive wrongly:

- The **adaptive** grid (`emuses_utils.compute_discrete_space` / `optimize_discrete_space`) is N-D
  generic and does **not** explode with dimension — it *shrinks*. Its criterion is point overlap,
  and 133 points in a 10-D cube never collide, so it settles at 50×50 for d=2, 5⁵ for d=5 and
  **2¹⁰ for d=10**. The failure mode is resolution collapse, not memory. That code is also currently
  unreachable: `DiscreteLatentSpace` is never instantiated. Earlier revisions of `STATUS.md` and the
  methodology docs asserted an `r^d` explosion citing `emuses_utils.py:113`; that was wrong on both
  the behaviour and the file.
- Only a **fixed** grid is exponential, which is what the live creators use at `grid_size=100`:
  d=4 is 10⁸ cells (0.8 GB, allocates), d=5 is 10¹⁰ (80 GB, fails).

So the obstacle is conceptual rather than computational: clustering in N-D and projecting to 2-D for
display would place genuinely separate clusters on top of each other, and the heatmap would stop
explaining the prediction beside it. Evidence that 2-D is not the binding constraint on this data
(an independent out-of-sample test recovered R=0.31 at n=314 from a 2-D morphospace):
`dev-docs/methodology/external_evidence_dsd.md` §7.2.

**Consequences.** `UMAPStage` assigns cluster labels for the **current** cohort via
`hdbscan.approximate_predict` whenever the stored labels do not belong to it — previously
coordinates were re-derived for the new subjects while labels were loaded wholesale from the
previous run. "Do not belong to it" is decided by §2.13's cohort record, not by count alone.
Guards are perturbation-verified in `tests/test_embedding_dimensionality.py`.

**The refusal has an opt-in, and the opt-in does not fork the pipeline.**
`--allow_nd_without_heatmaps` is what makes the dimensionality experiment (STATUS 3c: does d>2
predict better?) runnable at all — without it the gate refuses every shipped dict, because they all
enable the heatmap. The flag is deliberately **not** a separate N-D code path: the training stage,
the nested-CV search and the inference handoff run unchanged at any width, and only the 2-D grid
section is skipped, so the d=2 and d=5 arms of a comparison differ in the embedding and nothing
else. The default still refuses; `heatmaps_skipped.json` records the width so a heatmap-less folder
explains itself.

**The skip must not become an early return.** The obvious implementation — return from `run()`
once heatmaps are skipped — also skips the code *below* the grid section that populates
`inference_features` / `inference_labels` for `InferenceStage`. The result is a run that completes,
looks correct, and silently has no held-out validation, on exactly the N-D runs the flag exists to
compare. This was written and caught in review, not hypothesised.
`tests/test_embedding_dimensionality.py::TestSkipDoesNotStealTheInferenceHandoff` parses the source
with `ast` and fails if that return returns.

**`test_data` cannot validate this flag's effect.** d=2 and d=5 produce identical scores there;
max |r| between any feature and any target is 0.090 and the mean-predictor 5-fold R² is −0.187, so
every model collapses to its training mean and identical scores are the *correct* answer. Any
dimensionality comparison must run on `DSD_repro`.

**The `entropy` UMAP metric is 2-D only, and refusing it is part of this gate.** It scores a trial
with `np.histogramdd(emb, bins=n)`, allocating n^d cells. Measured on `DSD_repro` (1333 points): at
d=4, 1332 points occupy a cell of their own, so the metric returns a value that no longer varies
with embedding quality — the search would then optimise noise for the ~19 h it takes, and report a
best trial. Every shipped optim_dict weights `entropy`, so an N-D run with any of them would have
hit this. `validate_metrics_for_dimensionality` refuses the combination at configuration time
(`GRID_BINNED_METRICS`), and `optim_configs.optim_dict_nd` is the N-D configuration: the
disconnectome dict minus entropy, reweighted `eigen_spread` 3.0 / `density_variability` 2.0 /
`spread` 1.0. **It is not a numerical match for the 2-D dicts** — scores from it are not comparable
with scores from `optim_dict_default` or `optim_dict_disconnectome`. `--umap_n_components N`
overrides `n_components` on a `deepcopy` of the dict, because optim dicts are module-level globals
and the service process is long-lived; mutating one in place would leak into every later run.

**Resume detection must match the filenames actually written.** The output-folder branch tested for
`best_umap_model.joblib`, but `ModelIOManager` writes version-suffixed names
(`best_umap_model_v1_0_0_joblib1_5_2.joblib`), so the branch was unreachable from the day it was
written and every implicit resume silently retrained. Detection now globs for the newest match, and
`tests/test_embedding_dimensionality.py::TestResumeDetectionMatchesWhatIsActuallyWritten` pins it
against the source with comments and docstrings stripped. Reuse runs also wrote no `embeddings.npy`
or `cluster_labels.npy`, because saving lived inside the training function; it is now idempotent and
outside it, so a resumed run leaves a folder the next stage can consume. Both defects were reported
as working from reading the code, and only a real run exposed them.

### 2.13 Reuse Between Runs Is Opt-In, Fingerprinted, and Refuses When It Cannot Confirm

**Decision**: Anything a run reuses from a previous run — a morphospace, its cluster labels, a
finished prediction search — is reused **only when a stored fingerprint proves it answers this
run's question**. Every failure to confirm (missing file, damaged JSON, older schema, unreadable
model) means *recompute*, never *assume*. Files are `cohort.json`
(`emuses/tools/cohort_identity.py`), `<target>/search_fingerprint.json` +
`<target>/cv_scores.npy` (`emuses/tools/target_resume.py`) and
`performance_summary/runs.json` (`emuses/tools/run_index.py`).

**Rationale**: the cost of recomputing is time; the cost of wrongly reusing is a run that completes
and reports another experiment's numbers. Those are not comparable, so the tie always breaks the
same way. This is why `cohorts_match` returns `True`/`False`/**`None` for unknown** and the caller
treats `None` like `False`: a folder written before this file existed is not evidence that nothing
changed.

**Cohort identity, and why it is a digest rather than ids.** Nothing in the morphospace artefacts
carried subject identity, so two cohorts of equal size were indistinguishable and a reuse run paired
one cohort's labels with another's coordinates. `cohort.json` stores a SHA-256 over the feature
matrix (shape, dtype, C-contiguous bytes), and **no per-subject data by default**. That file ships
inside the shared model folder, and hashing clinical ids would not make them safe: ids come from
small, guessable spaces (sequential integers, site prefixes, a known cohort list), so per-subject
digests are recoverable by enumeration in seconds. `--record_cohort_ids` is the explicit opt-in for
users who can share them. Side effect worth keeping: when the cohort *does* match, `--load_umap`
can now reuse HDBSCAN's **fitted** labels, which it previously always discarded in favour of
`approximate_predict` — the two can disagree near cluster boundaries.

**Prediction resume is per target, and no finer.** `--resume_targets` skips `nested_optuna_cv` for
a target whose coordinates, target values, resolved search space, fold count, trial budget and
seeds are all unchanged. Targets are independent, so "already done" is answerable one column at a
time with no reasoning about partial state. Per-fold or mid-study resume is **deliberately
declined**: it means owning Optuna's study state machine for a much smaller saving. Scores are
reloaded from `cv_scores.npy` at full precision — the per-fold CSV rounds to 4 dp, so resuming from
it would quietly change the numbers a run reports. Verified decisively by rigging `nested_optuna_cv`
to raise: a resumed run completes without ever calling it, while changing `--optuna_trials`
correctly rejects the stored result. Identical scores alone prove nothing here, since the search is
seeded.

**Several runs may share one output folder, and the folder must say which is which.**
`performance_summary/` accumulates timestamped aggregates; nothing distinguished them, and the
per-target files under `target_N/performance/` are overwritten by whichever run went last.
`runs.json` records each run's embedding width, sample count, search spaces, budgets, seeds and
whether it skipped heatmaps, with `latest` naming the current results. Older files are **kept, not
pruned** — comparing configurations is the reason a folder holds more than one. The index is
descriptive only: nothing reads it back to make a decision, so a damaged index costs information,
not correctness, and both it and the target artefacts are written inside `try/except` that never
raises. Losing an hours-long search to a bookkeeping error would be the worse trade by a wide
margin.

**Documented for users** in `docs/CLI_REFERENCE.md` § "Reusing Work Between Runs", which also
documents the *implicit* output-folder resume — reusing a morphospace merely because the output
folder happens to contain one, which had never been stated anywhere.

### 2.10 Core / Extras Boundary: Parked Features Stay, But Cost Nothing

**Decision**: EMUSES has a declared **core** and a set of **parked (extras)** features. Parked code
stays in the tree and remains importable and testable, but is excluded from the default test run and
must not be imported by core at module level. The boundary is enforced mechanically by
`tests/test_architecture_boundary.py`.

**Core**: `pipelines/`, `cli/` (except `cloud_validation.py`), `config/`, `utils/`, `observability/`
(every pipeline stage imports it), `foundation_fastapi_service/` (except the orphaned
`stage_runners.py`), and in `tools/` the science modules plus `model_io`, `local_model_registry`,
`base_model_registry`, `storage_manager`, `model_registry_factory`, `model_registry_metrics`,
`model_registry_health`.

**Parked**: everything in `emuses/extras/` — the model marketplace (`advanced_search`,
`model_analytics`, `personalized_ranking`, `model_benchmarking`, `community_model_manager`,
`streaming_analytics`, `usage_alerts`, `model_compression`, `model_migration`, `registry_config`),
the publication/compliance scaffolding (`academic_features`, `academic_compliance`,
`gdpr_compliance`), and the cloud and database registry backends — plus `multi_user_service/` in
full, and two modules parked in place because each sits inside an otherwise-core package:
`cli/cloud_validation.py` and `foundation_fastapi_service/stage_runners.py`.

**The parked modules live in `emuses/extras/`** (moved 2026-08-24: 22 modules, 17,552 lines, out of
`emuses/tools/`). The boundary was originally 22 names typed into the test, describing files that
sat next to core code; membership now follows from where a file lives. Only three production files
referenced any of them, and `model_registry_factory` already loaded the cloud and database backends
lazily, so core needed no change.

The move opens one hole the list did not have, and it is guarded. Measured by removing
`"emuses.extras"` from `EXTRAS_PACKAGES`: the real core→extras violation stops being reported, and
about fifteen *legitimate* extras→`multi_user_service` imports start being reported in its place.
The failure is loud but points everywhere except at the cause — the kind of report that gets "fixed"
by loosening something. `test_the_extras_package_is_actually_declared` names it directly.

**Rationale**:
- Measured 2026-08-19: 16,585 LOC (22% of the package) was unreachable from *every* entry point, and
  1,071 of 2,499 tests exercised it. The registry those features would serve holds one model.
- The maintenance cost was real and the benefit was zero, but the work is not worthless — it is
  unfinished. Deleting it would discard genuine effort; leaving it in the default path made the
  suite too large to keep trustworthy. Parking resolves both.
- `model_analytics` had 32 references and still looked alive; every one came from another parked
  module. A self-referential cluster cannot be spotted by counting references, which is why the
  boundary must be declared rather than inferred.
- The seam already existed: `DeploymentMode` and `is_service_mode_enabled()`, with
  `foundation_fastapi_service/app.py` wiring the multi-user endpoints behind
  `try/except ImportError`. This decision makes that existing pattern explicit and enforced.

**The rule**: core must not import parked code *at module level*. Lazy imports — inside a function,
or behind `try/except ImportError` — are the sanctioned way to wire an optional feature, and
`model_registry_factory.py` already loads the cloud and database backends that way.

**Do not** relax the boundary to make a test pass. If a parked feature turns out to be genuinely
core, move its file out of `emuses/extras/` deliberately and record why here. The declaration is a
product decision, not a graph property — deriving it from reachability would make the test circular
and unable to fail.

**Code**: `emuses/extras/__init__.py`, `tests/test_architecture_boundary.py`,
`tests/extras/conftest.py`, `pytest.ini`

---

## 3. Known Constraints and Open Issues

### 3.1 Feature Augmentation Models Not Persisted (OPEN)

**Issue**: PCA, kPCA, and autoencoder models fitted during HeatmapStage optimisation are likely not saved to disk. Detection code (`_detect_feature_models` in `model_io.py`) exists but no evidence of saving in HeatmapStage training.

**Impact**: Inference on new data cannot apply the identical feature transformations used during training, breaking reproducibility for non-raw feature types.

**Required fix**: HeatmapStage must save fitted feature models to a `feature_models/` subdirectory; InferenceStage must load and apply them before prediction.

**Status**: Unresolved. Needs verification and implementation.

---

### 3.1b Constant Predictions Are Degenerate Models, Not an Inference Bug (OPEN, corrected)

**Opened and corrected on 2026-08-24.** The original entry claimed inference emitted constant
predictions for some digits targets while cross-validating at 0.99+. That claim is **withdrawn**:
both pieces of evidence for it were compromised.

- The digits inference was fed the model's own `split_dataset/test_features.npy`, which is written
  **after** input normalization, while the inference path applies the saved scaler again. The input
  was normalized twice.
- The `test_data/` reproduction shows the constants come from **training**, not inference. Every fold
  estimator is an `ElasticNet` with all coefficients zero, returning its intercept (the training-target
  mean, 0.807) for any input across a grid spanning [-50, 50]^2. `prediction_values.npy` holds one
  unique value across 10 000 grid points and `confidence_values.npy` is exactly 1.0. Inference is
  faithfully applying a model that was already constant.

The fit itself is defensible - `quick_train_dict` searches alpha up to 1.0, and on 40 samples of 2-D
embeddings with target std 0.07 there is no signal, so zeroing the coefficients minimises CV error.

**What is actually wrong, and is still open:**

1. **Degenerate models are never reported.** All-zero coefficients, a constant prediction grid, and
   `confidence = 1.0` describe a model that knows nothing and claims certainty. Confidence is
   `1.0 - std(across fold predictions)` (`inference_stage.py:1455`), so perfect agreement between
   useless models reads as perfect confidence. The evidence exists at training time; report it there.
   **Reproduced end to end on 2026-09-04** while verifying standalone `emuses inference`: all 50
   predictions identical, at confidence **0.9934**. The models are genuinely constant — isolated
   from the pipeline, each fold estimator returns one value for coordinates spanning the whole
   morphospace, and those values are the per-fold **training means** of a target whose raw mean is
   0.8146. So inference is reporting faithfully and the number is still misleading. Note for anyone
   testing inference: on `test_data` this outcome is *expected*, and looks exactly like the
   2025-08-27 "all predictions identical" bug. Do not diagnose it as that bug again.
2. **Feeding EMUSES' own splits back into inference silently double-normalizes.** Measured: the
   pre-normalized split yields **1** distinct embedding from `umap.transform`, the same rows raw yield
   10, all 50 raw rows yield 50. Off-manifold input collapses the transform with no error.
3. `.npy` rejected and header-bearing CSV rejected (`input_header` defaults to `None`). Accepting
   `.npy` makes (2) easier to hit, so the collapse guard lands first or alongside.

**`test_data/` cannot validate prediction behaviour**: `features.csv` is a synthetic ramp (row i is
`[1.i, 2.i, ... 8.i]`), rank-1 by construction, and yields degenerate fits at any budget. Related:
`tests/regression/` baselines pin per-fold scores of mean -0.3554 / min -0.9809 (negative R^2), so a
passing regression suite is **not** evidence that prediction works - it is pinned at the floor.

Whether digits shows a genuine inference defect is **unresolved**; its models were not degenerate, but
its input was double-normalized. Settling it needs a re-run with raw inference input (~3.5 h). Details
in `dev-docs/issues/inference_constant_predictions_2026_08.md`.

### 3.2 Optuna Parameter Space Conflict on Resume (OPEN)

**Issue**: Resuming training in an existing output directory with a different `--prediction_optim_dict` crashes because the loaded Optuna study expects the original parameter space.

**Workaround**: Use a different output directory, or manually delete the Optuna SQLite file.

**Proposed fix**: Detect optim_dict change via saved metadata and auto-create a timestamped output folder.

**Status**: Solution designed, not yet implemented. See `dev-docs/issues/optim_dict_resume_conflict.md`.

---

### 3.3 Timedelta Columns in Spreadsheet Input (OPEN)

**Issue**: Time-formatted columns (e.g., `22:30:00`) are parsed as Timedelta objects during spreadsheet loading, causing UMAP transform to fail on non-numeric input.

**Status**: Root cause identified, fix not yet implemented.

---

### 3.4 GridCreator Interface Mismatch (STATUS UNKNOWN)

**Issue**: HeatmapStage passes sklearn Pipeline objects to GridCreator, which expects a dictionary interface. Tests pass dicts; production uses Pipeline objects.

**Status**: Needs verification — may have been fixed without being documented.

---

### 3.5 The Service's Pipeline Timeout Cannot Fire (OPEN)

`PipelineRunner.pipeline_timeout` has no effect. `execute_pipeline` wraps the run in
`asyncio.wait_for`, but `_execute_pipeline_stages` calls `_run_pipeline_in_process` synchronously,
so the event loop is blocked for the whole run and the timeout callback cannot execute until the
work it is timing has already finished. A hung pipeline hangs forever and the job stays `running`.

Not fixed as a drive-by: the fix (move the call to an executor) also makes concurrent jobs genuinely
concurrent, and nothing bounds how many the service accepts. Note also that a `wait_for` over a
thread executor yields a timeout that *reports* without *stopping* — a thread cannot be cancelled
once started — so a job would show `failed` while the pipeline kept running. Found 2026-08-25 while
auditing the parallelism backend; options and the trap in verifying a fix in
`dev-docs/issues/inert_pipeline_timeout_2026_08.md`.

### 3.6 Resource Limits Are Advertised but Not Enforced (OPEN)

`memory_limit_ratio` and `cpu_percent_limit` are constructor options on `PipelineRunner` that
nothing reads. The only `ResourceMonitor` lives in `stage_runners.py`, which is dead code. Nothing
in `emuses/pipelines/` or `emuses/tools/` is memory-aware at all, so a run that does not fit in RAM
fails as an OOM kill rather than a stated error.

**These are a researcher's control, not an operator's**, and so are *separate* from §3.5 despite
being found with it: they matter with one pipeline on one machine and are blocked on nothing. The
CPU half is largely covered already by `--n_jobs` (real since the service became its own process);
memory has no equivalent. Any limit needs a measured memory profile first — peak RSS by stage and
how it scales with samples, features and `n_jobs` — which is worth capturing during the planned
scientific-validity runs rather than as a separate exercise. Until a limit enforces something, the
options should be removed rather than left reading as a guarantee.
`dev-docs/issues/memory_aware_execution_2026_08.md`.

## 4. Deployment Architecture

Three deployment modes share the same pipeline core:
- **Local**: CLI, file-based storage, auto-started local service (see below — this bullet used to
  say "in-process execution", which was never true and is no longer the intent)
- **Lab (multi-user)**: FastAPI service, SQLite/PostgreSQL job persistence, background workers
- **Cloud-native**: Kubernetes, distributed job queue, cloud object storage

Models created in any mode are portable to any other mode. No deployment-specific model formats.

**Every deployment mode executes through the EMUSES service, including local (decided 2026-08-23).**
Local mode auto-starts a service and submits to it rather than calling the pipeline directly. The
bullet above once read "in-process execution"; that was aspirational, never true, and after being
briefly implemented it was reverted the same day.

**Why one path, and not a direct local call.** The reason is maintenance, not purity. A local path
means every change to logging, progress reporting, job status or error handling has to be made twice.
That was measured rather than predicted: moving `full` in-process took about forty lines and
immediately produced a **third** progress mechanism (the service writes into the job record, the CLI
polls and prints, the local path printed directly), with no interrupt handling and no job record; a
leaked temp scores file, because `_cleanup_temp_scores_file` lives in `execute_pipeline`'s `finally`
and a direct call to `_run_pipeline_in_process` bypasses it; no timeout, applied in the same place;
and a CLI where `full` behaved one way and `umap`/`heatmap` another.

**Going over HTTP locally also catches real bugs.** Phase 1C: `/api/v1/jobs/pipeline/umap` did not
exist on the server. The CLI built that URL, got a 404, and the defect was found on a laptop. Executed
in-process, a missing route stays invisible until someone deploys. What HTTP does *not* catch is
configuration errors - `JobSubmissionRequest.pipeline_config` is an untyped `dict`, so Pydantic
validates nothing about its contents. It catches transport bugs: route existence, JSON
serializability, error-to-status mapping.

**Known cost, accepted deliberately.** The pipeline runs in a `multiprocessing.Process` child, so
`is_subprocess_context()` is True and `get_safe_n_jobs()` clamps `n_jobs` to 1: **`--n_jobs` does
nothing on the CLI** while working normally through the Python API. Measured directly -
`get_safe_n_jobs(4)` returns 4 in the main process and 1 in a forked child. The fix is to make the
clamp precise, not to bypass the service: its documented hazard is spawning *loky* workers from an
already-forked process, while `_run_pipeline_in_process` forces the **threading** backend, where that
hazard does not apply. That needs its own measurement and is tracked as open.

**Validation is a named function, not a route body.** `prepare_pipeline_context` (`app.py`) holds the
required-field checks, special-dataset handling and the output-path checks added after the
shell-injection cleanup. Kept from the reverted work because it is right regardless: those checks
should be callable and testable rather than reachable only by making an HTTP request.

`tests/test_single_execution_path.py` guards this decision. Its list of declared exceptions
(`KNOWN_LOCAL_EXECUTION`) is **empty as of 2026-08-24**: `_execute_inference_locally` was the last
entry and is gone.

`--service-url` opts into a remote service. `--service` is redundant now that every mode uses one, so
it warns instead of sitting there looking wired.

**Inference is a job, not a special case (decided 2026-08-24, Phase 1F).** `emuses inference` submits
to `/api/v1/jobs/pipeline/inference`, so it inherits the job record, progress polling, timeout and
interrupt handling the other commands already had. It used to build an `EMUSESPipeline` and run
`InferenceStage` in the CLI process, which is what stopped a lab from having one person train a model
and others run inference against it on a server.

Three things worth knowing about how it was done:

- **The pre-existing `/api/v1/inference` endpoints could never have worked**, so "the endpoints
  already exist, this is just wiring" was wrong. They built a bare `PipelineConfig` and handed
  `InferenceStage` a context containing only `verify_integrity` and `output_format`; nothing in that
  path ever loaded the data file. Measured 2026-08-24: every request returned **422 "No inference
  features found in context"**. Nothing caught it because nothing exercised them - the endpoint test
  asserted a 422 and got one.
- **There is now one implementation**, `emuses/pipelines/inference_runner.py::run_inference`. The
  inference job, `/api/v1/inference` and `/api/v1/inference/async` all call it. Data preparation is
  not incidental to inference: the stage applies the model's *saved* scaler, so the features it
  receives must be raw input in the training input's space, which is what
  `EMUSESPipeline(inference_mode=True)` produces. An endpoint that skips it produces an empty result
  at best and a silently wrong one at worst (§3.1b).
- **Inference cannot reuse `prepare_pipeline_context`**: that requires `scores`, and inference on new
  data has no ground truth. What it requires instead is a model, so the inference endpoint has its
  own validation and explicitly disables the training stages - without that, the runner's defaults
  (`umap_stage_enabled` and `heatmap_stage_enabled` both default to True) would have an inference
  request retrain the model it was asked to apply.

**The response was empty and said 200.** Both endpoints read `results["predictions"]` and
`results["prediction_details"]`, neither of which `InferenceStage` returns - predictions nest per
target under `target_results`. So a completed run answered with `predictions: []` and
`confidence_scores: null` alongside a correct sample count. Shaping now goes through
`_inference_results_to_response`, which carries every target and converts numpy **recursively** (a
shallow conversion still returned 400 "Unable to serialize unknown type", because each target holds
per-fold arrays of its own).

Verified not to move results: the same command through the CLI before and after the change produced
**bitwise identical** prediction and confidence CSVs on `test_data/` (50 samples, 8 columns, maximum
absolute difference 0.0); only timestamps and timings differ.

**The service is its own interpreter, not a fork (decided 2026-08-24, Phase 1E).**
`_start_local_service` launches `python -m emuses.cli.service_process --port N` via
`subprocess.Popen(sys.executable, ...)`. It used `multiprocessing.Process`, and that had three
consequences, only one of which was visible:

- **`--n_jobs` was inert on the CLI.** `is_subprocess_context()` is
  `mp.current_process().name != "MainProcess"`, true in any forked child, so `get_safe_n_jobs()`
  clamped to 1 inside the service while the Python API was unaffected. **The clamp is not the bug** -
  spawning loky workers from an already-forked process genuinely hangs, and that was reproduced
  directly. The process *identity* was wrong. Fixing it leaves `get_safe_n_jobs` untouched.
- **A SIGKILLed CLI orphaned the service**, which then held its port for over an hour and ignored
  SIGTERM; `atexit` does not run when the parent is killed. `service_process` now dies with its
  parent via `prctl(PR_SET_PDEATHSIG)` on Linux, with a pid-watchdog fallback and a guard for the
  race where the parent dies first.
- **The service was invisible to `pgrep`**, because as a fork its argv still read
  `python -m emuses.cli full`. It now names itself.

The entry point binds `127.0.0.1` and takes an explicit `--port`. It deliberately does not reuse
`foundation_fastapi_service/app.py`'s `__main__`, which hardcodes port 8000 and binds `0.0.0.0`.
The macOS `_macos_service_worker` branch is deleted: it existed only to satisfy `multiprocessing`
spawn-pickling, and a subprocess needs no picklable target.

Verified not to move results: 18/18 scalar metrics identical against both the API baseline and the
pre-change forked CLI, cluster ARI 1.0, embedding distance correlation 1.0.
