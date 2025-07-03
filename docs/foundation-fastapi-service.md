# EMUSES Pipeline Documentation

<reasoning>
The Foundation FastAPI Service feature requires wrapping the existing EMUSES pipeline stages (UMAPStage, HeatmapStage, PredictionStage) without modifying their core logic. The key APIs that need to be documented are:

1. EMUSESPipeline - The main pipeline orchestrator that the FastAPI service will wrap
2. UMAPStage - Performs UMAP dimensionality reduction and HDBSCAN clustering with Optuna optimization
3. HeatmapStage - Runs multi-target prediction with nested cross-validation and kernel regression
4. PredictionStage - Final test evaluation with optional Gaussian weighted distance features
5. PipelineStage - Base class that defines the stage interface

These components maintain a context dictionary pattern that the FastAPI service must preserve, and they support both full pipeline execution and individual stage execution - exactly what the API endpoints need.
</reasoning>

## Level 1: Pipeline Overview

EMUSES (Embedding-based Multi-target Unsupervised Spatial Embedding System) provides a machine learning pipeline for neuroimaging data analysis. The system performs dimensionality reduction using UMAP, clustering with HDBSCAN, and multi-target prediction through kernel regression. The pipeline follows a stage-based architecture where each stage operates on a shared context dictionary, enabling both sequential execution and individual stage resumption.

The pipeline supports two execution modes: **classic mode** using a single dataset for both embedding and prediction, and **label dataset mode** separating unlabeled data for UMAP training from labeled data for prediction tasks. All stages use Optuna for hyperparameter optimization and maintain reproducibility through component-specific random seeds.

## Level 2: Public API Reference

| Symbol | Purpose | Inputs | Outputs | Side-effects |
|--------|---------|--------|---------|--------------|
| `EMUSESPipeline` | Main pipeline orchestrator | args dict with dataset paths, config | Pipeline results dict | Creates output folder structure, saves models |
| `EMUSESPipeline.init_data()` | Load and preprocess datasets | None (uses self.config) | None | Populates self.input_matrix, self.scores, updates context |
| `EMUSESPipeline.add_stage()` | Add processing stage to pipeline | stage: PipelineStage instance | None | Appends to self.stages list |
| `EMUSESPipeline.run()` | Execute all pipeline stages | progress_callback, progress_queue (optional) | context dict | Runs stages sequentially, updates metadata |
| `UMAPStage` | UMAP dimensionality reduction + clustering | config: PipelineConfig | None | Trains UMAP model, performs clustering |
| `UMAPStage.run()` | Execute UMAP optimization and embedding | context dict, progress_queue (optional) | context dict | Saves UMAP model, embeddings, cluster labels |
| `HeatmapStage` | Multi-target prediction with nested CV | config, output_format_info | None | Trains prediction models, generates performance reports |
| `HeatmapStage.run()` | Execute kernel regression optimization | context dict, progress_queue (optional) | context dict | Saves models, CSV performance files |
| `PredictionStage` | Final test evaluation with GWD features | config: PipelineConfig | None | Evaluates trained models on test data |
| `PredictionStage.run()` | Execute prediction evaluation | context dict, progress_queue (optional) | context dict | Saves prediction results, performance metrics |
| `PipelineStage` | Abstract base class for pipeline stages | config: PipelineConfig | None | Defines stage interface |
| `PipelineStage.run()` | Abstract method for stage execution | context dict, progress_queue (optional) | context dict | Must be implemented by subclasses |

<details>
<summary><strong>EMUSESPipeline Implementation</strong></summary>

```python
class EMUSESPipeline:
    def __init__(self, args):
        self.config = PipelineConfig(args)
        self.args = self.config  # For backward compatibility
        self.output_folder = self.config.output_folder

        # In classic mode, these come from the main dataset;
        # in label_dataset mode, the labelled dataset is processed separately.
        self.input_matrix = None
        self.scores = None
        self.dataset_type = None
        self.paths_list = None
        self.output_format_info = None

        # For label_dataset mode
        self.labelled_input_matrix = None
        self.labelled_scores = None

        self.stages = []
        self.results = {}
        self.context = {}  # Shared context for data between stages
        self.logger = logging.getLogger(__name__)

        # Initialize pipeline metadata
        self.context["pipeline_metadata"] = {
            "start_time": time.time(),
            "stages_completed": [],
            "stages_runtime": {},
            "dataset_name": getattr(self.config, "input_dataset", "unknown"),
        }

    def add_stage(self, stage):
        """Add a processing stage to the pipeline.
        
        Parameters
        ----------
        stage : PipelineStage
            The stage instance to add to the pipeline
        """
        self.stages.append(stage)

    def run(self, progress_callback=None, progress_queue=None):
        """Execute all pipeline stages sequentially.
        
        Parameters
        ----------
        progress_callback : callable, optional
            Function called with stage progress updates
        progress_queue : Queue, optional
            Queue for sending progress messages
            
        Returns
        -------
        dict
            Updated context dictionary with all stage results
        """
        total_stages = len(self.stages)

        for i, stage in enumerate(self.stages):
            stage_name = stage.__class__.__name__
            stage_start_time = time.time()

            if progress_callback:
                progress = i / total_stages
                progress_callback(stage_name=stage_name, progress=progress)

            # Run the stage
            stage.run(self.context, progress_queue=progress_queue)

            # Record stage completion and runtime
            stage_end_time = time.time()
            stage_runtime = stage_end_time - stage_start_time

            # Update pipeline metadata with completion info
            self.context["pipeline_metadata"]["stages_completed"].append(stage_name)
            self.context["pipeline_metadata"]["stages_runtime"][
                stage_name
            ] = stage_runtime
```

</details>

<details>
<summary><strong>UMAPStage Implementation</strong></summary>

```python
class UMAPStage(PipelineStage):
    def __init__(self, config):
        super().__init__(config)
        self.trained_umap = None
        self.embeddings = None
        self.test_embeddings = None
        self.umap_model_path = None
        self.embeddings_path = None
        self.test_embeddings_path = None
        self.min_embeddings = None
        self.max_embeddings = None
        # Clustering-related attributes:
        self.best_clusterer = None
        self.cluster_labels = None
        self.cluster_model_path = None
        self.cluster_labels_path = None

    def run(self, context, progress_queue=None):
        """Execute UMAP dimensionality reduction with nested HDBSCAN clustering.
        
        Performs joint optimization of UMAP and HDBSCAN parameters using Optuna,
        then transforms data and updates context with embeddings and models.
        
        Parameters
        ----------
        context : dict
            Pipeline context containing input features and configuration
        progress_queue : Queue, optional
            Queue for sending progress updates
            
        Returns
        -------
        dict
            Updated context with UMAP embeddings, models, and cluster labels
        """
        logger = logging.getLogger(__name__)
        logger.info("Running UMAP Stage")

        # Get component-specific seeds from context
        random_seeds = context.get("random_seeds", {})
        umap_seed = random_seeds.get("umap_seed", 42)
        clustering_seed = random_seeds.get("clustering_seed", 42)

        # Use new naming convention only
        train_features = context.get("embedding_train_features")
        test_features = context.get("embedding_test_features")
        train_indices = context.get("embedding_train_indices")  # May be None

        # Load or generate the optimization dictionary.
        if "optim_dict" in context and context["optim_dict"]:
            optim_dict = context["optim_dict"]
        elif "cli_args" in context and "optim_dict" in context["cli_args"]:
            optim_dict_name = context["cli_args"]["optim_dict"]
            try:
                optim_dict = load_optim_dict(optim_dict_name)
            except Exception as e:
                logger.error(
                    f"Error loading optim_dict '{optim_dict_name}': {e}. Falling back to default."
                )
                optim_dict = optim_dict_default
        else:
            optim_dict = optim_dict_default
```

</details>

<details>
<summary><strong>HeatmapStage Implementation</strong></summary>

```python
class HeatmapStage(PipelineStage):
    def __init__(self, config, output_format_info):
        super().__init__(config)
        self.output_format_info = output_format_info

    def run(self, context, progress_queue=None):
        """Execute multi-target prediction with kernel regression and nested CV.
        
        Performs hyperparameter optimization using Optuna for multiple prediction
        targets, with optional autoencoder pretraining for feature extraction.
        
        Parameters
        ----------
        context : dict
            Pipeline context containing embeddings and labels
        progress_queue : Queue, optional
            Queue for sending progress updates
            
        Returns
        -------
        dict
            Updated context with prediction results and performance metrics
        """
        logger = logging.getLogger(__name__)
        logger.info("Running Heatmap Stage (kernel regression version)")

        # Get prediction coordinates (UMAP embeddings for labeled data)
        prediction_train_coords = context.get("prediction_train_coords")
        prediction_train_labels = context.get("prediction_train_labels")

        # Decide whether we are in regression or classification mode
        task = "clf" if getattr(self.config, "classification", False) else "reg"

        # Load or generate the prediction optimization dictionary
        if "optim_dict_predict" in context and context["optim_dict_predict"]:
            optim_dict_predict_selected = context["optim_dict_predict"]
        elif "cli_args" in context and "prediction_optim_dict" in context["cli_args"]:
            prediction_optim_dict_name = context["cli_args"]["prediction_optim_dict"]
            try:
                optim_dict_predict_selected = load_optim_dict_predict(
                    prediction_optim_dict_name
                )
            except Exception as e:
                logger.error(f"Error loading prediction optim_dict: {e}")
                optim_dict_predict_selected = optim_dict_predict
        else:
            optim_dict_predict_selected = optim_dict_predict
```

</details>

<details>
<summary><strong>PredictionStage Implementation</strong></summary>

```python
class PredictionStage(PipelineStage):
    """
    Stage to train models for predicting target variables from embeddings,
    optionally including Gaussian weighted distances (GWD) features.
    """

    def __init__(self, config):
        super().__init__(config)

    def run(self, context, progress_queue=None):
        """Execute final prediction evaluation with test data.
        
        Trains prediction models using embeddings and optional GWD features,
        evaluates on test set, and saves performance metrics.
        
        Parameters
        ----------
        context : dict
            Pipeline context containing train/test embeddings and labels
        progress_queue : Queue, optional
            Queue for sending progress updates
            
        Returns
        -------
        dict
            Updated context with prediction results and saved metrics
        """
        logger = logging.getLogger(__name__)
        logger.info("Running Prediction Stage (Test Evaluation)")

        # Get component-specific seeds from context
        random_seeds = context.get("random_seeds", {})
        prediction_seed = random_seeds.get("prediction_seed", 42)
        cv_seed = random_seeds.get("cv_seed", 42)
        optuna_seed = random_seeds.get("optuna_seed", 42)

        # Extract embeddings and labels from context using new naming convention only
        train_embeddings = context.get("prediction_train_coords")
        test_embeddings = context.get("prediction_test_coords")
        train_labels = context.get("prediction_train_labels")
        test_labels = context.get("prediction_test_labels")

        if train_embeddings is None:
            raise ValueError("prediction_train_coords is required for prediction.")
        if train_labels is None:
            raise ValueError("prediction_train_labels is required for prediction.")

        # Determine if we use enhanced pipeline with Optuna
        use_enhanced_pipeline = getattr(self.config, "use_enhanced_pipeline", False)
        n_jobs = getattr(self.config, "n_jobs", -1)
        optuna_trials = getattr(self.config, "optuna_trials", 50)
        parallel_models = getattr(self.config, "parallel_models", False)
        model_selection = getattr(self.config, "model_selection", None)
```

</details>

<details>
<summary><strong>PipelineStage Base Class</strong></summary>

```python
class PipelineStage:
    def __init__(self, config):
        """Initialize pipeline stage with configuration.
        
        Parameters
        ----------
        config : PipelineConfig
            Configuration object containing stage parameters
        """
        self.config = config

    def run(self, context, progress_queue=None):
        """Execute the pipeline stage.
        
        This method must be implemented by all concrete stage classes.
        
        Parameters
        ----------
        context : dict
            Shared pipeline context dictionary
        progress_queue : Queue, optional
            Queue for sending progress updates to monitoring systems
            
        Returns
        -------
        dict
            Updated context dictionary with stage results
            
        Raises
        ------
        NotImplementedError
            If not implemented by subclass
        """
        raise NotImplementedError("Each stage must implement a run method.")
```

</details>

## Context Dictionary Structure

The pipeline uses a shared context dictionary to pass data between stages. Key context variables include:

**Input Data (populated by EMUSESPipeline.init_data())**:
- `embedding_train_features`: Unlabeled features for UMAP training
- `prediction_train_features`: Labeled features for prediction
- `prediction_train_labels`: Target labels for prediction
- `prediction_test_features`: Test features (optional)
- `prediction_test_labels`: Test labels (optional)

**UMAP Stage Outputs**:
- `embedding_train_coords`: 2D UMAP embeddings
- `embedding_train_umap_model`: Trained UMAP model
- `embedding_train_clusterer`: HDBSCAN clustering model
- `embedding_train_cluster_labels`: Cluster assignments
- `prediction_train_coords`: Transformed labeled data coordinates

**Configuration and Metadata**:
- `random_seeds`: Component-specific random seeds
- `output_folder`: Output directory path
- `pipeline_metadata`: Execution timing and status
- `optim_dict`: UMAP optimization parameters
- `optim_dict_predict`: Prediction optimization parameters

**Results**:
- `prediction_results`: Performance metrics per target
- `ae_pretraining_results`: Autoencoder training results (if enabled)

This context pattern enables the FastAPI service to run individual stages by preserving and passing the appropriate context state between API calls.
