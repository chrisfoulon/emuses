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

### 2.5 InferenceStage as a Separate Stage

**Decision**: Inference is implemented as a standalone `InferenceStage` class, not as a method of `EMUSESPipeline`.

**Rationale**:
- Training and inference are fundamentally different workflows: training optimises and fits; inference loads and applies.
- Separation keeps each class focused and independently testable.
- InferenceStage can be composed into a minimal pipeline without the full training scaffolding.

**Code**: `emuses/pipelines/inference_stage.py` (1600+ lines handling full inference workflow)

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

### 2.9b Bitwise Reproducibility Is Out of Scope

**Decision**: EMUSES targets reproducibility within a machine and environment, verified against
*measured* tolerances, not bitwise identity across platforms.

**Rationale**: parallel floating-point reductions are not associative, so results legitimately differ
with thread count and BLAS build. Chasing bitwise identity would mean forcing single-threaded
execution everywhere, at a large and permanent performance cost, to remove differences that are below
scientific significance. Tolerances are to be derived from measurement and cited where they are
pinned, rather than guessed.

**Do not re-litigate this.** It was decided deliberately after the alternative was considered.

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

**Parked**: the model marketplace (`advanced_search`, `model_analytics`, `personalized_ranking`,
`model_benchmarking`, `community_model_manager`, `streaming_analytics`, `usage_alerts`,
`model_compression`, `model_migration`, `registry_config`), the publication/compliance scaffolding
(`academic_features`, `academic_compliance`, `gdpr_compliance`), the cloud and database registry
backends, and `multi_user_service/` in full.

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
core, move it out of `EXTRAS_MODULES` deliberately and record why here. The declaration is a product
decision, not a graph property — deriving it from reachability would make the test circular and
unable to fail.

**Code**: `tests/test_architecture_boundary.py`, `tests/extras/conftest.py`, `pytest.ini`

---

## 3. Known Constraints and Open Issues

### 3.1 Feature Augmentation Models Not Persisted (OPEN)

**Issue**: PCA, kPCA, and autoencoder models fitted during HeatmapStage optimisation are likely not saved to disk. Detection code (`_detect_feature_models` in `model_io.py`) exists but no evidence of saving in HeatmapStage training.

**Impact**: Inference on new data cannot apply the identical feature transformations used during training, breaking reproducibility for non-raw feature types.

**Required fix**: HeatmapStage must save fitted feature models to a `feature_models/` subdirectory; InferenceStage must load and apply them before prediction.

**Status**: Unresolved. Needs verification and implementation.

---

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

## 4. Deployment Architecture

Three deployment modes share the same pipeline core:
- **Local**: CLI, file-based storage, in-process execution
- **Lab (multi-user)**: FastAPI service, SQLite/PostgreSQL job persistence, background workers
- **Cloud-native**: Kubernetes, distributed job queue, cloud object storage

Models created in any mode are portable to any other mode. No deployment-specific model formats.
