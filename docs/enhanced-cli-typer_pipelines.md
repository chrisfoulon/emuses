# EMUSES Pipelines Documentation

<reasoning>
The EMUSES pipelines module contains the core pipeline stages and orchestration logic that both the legacy CLI and new Typer CLI need to understand. Key components include:

1. EMUSESPipeline - Main orchestrator that coordinates stage execution
2. UMAPStage - Dimensionality reduction and clustering with Optuna optimization
3. HeatmapStage - Multi-target prediction with nested cross-validation
4. PredictionStage - Test evaluation and model performance assessment
5. PipelineStage - Abstract base class defining stage interface
6. PipelineConfig - Configuration management for all stages

These are crucial for the CLI because the new implementation needs to understand the pipeline structure to properly translate CLI arguments to API requests.
</reasoning>

## Level 1: Pipeline System Overview

The EMUSES pipelines module implements a modular machine learning pipeline system for neuroimaging data analysis, featuring dimensionality reduction, clustering, and multi-target prediction capabilities. The system uses a shared context dictionary pattern to pass data and results between stages, enabling both sequential execution and individual stage processing. The main orchestrator (EMUSESPipeline) coordinates execution of three primary stages: UMAPStage for dimensionality reduction with joint UMAP+HDBSCAN optimization, HeatmapStage for multi-target prediction with nested cross-validation, and PredictionStage for final test evaluation. Each stage implements the PipelineStage interface with a run() method that takes a context dictionary and optional progress queue. The architecture supports both CLI and API interfaces through consistent parameter handling and progress tracking mechanisms.

## Level 2: Public API Reference

| Symbol | Purpose | Inputs | Outputs | Side-effects |
|--------|---------|--------|---------|--------------|
| `EMUSESPipeline` | Main pipeline orchestrator and data coordinator | args: argparse.Namespace | None | Creates output directories, loads datasets |
| `EMUSESPipeline.init_data()` | Load and preprocess input datasets | None (uses self.config) | None | Populates input_matrix, scores, context |
| `EMUSESPipeline.add_stage()` | Add processing stage to execution queue | stage: PipelineStage | None | Appends to stages list |
| `EMUSESPipeline.run()` | Execute all stages with progress tracking | progress_callback, progress_queue | context dict | Runs stages sequentially, saves metadata |
| `UMAPStage` | UMAP dimensionality reduction with clustering | config: PipelineConfig | None | None |
| `UMAPStage.run()` | Execute joint UMAP+HDBSCAN optimization | context dict, progress_queue | context dict | Saves UMAP model, embeddings, clusters |
| `HeatmapStage` | Multi-target prediction with nested CV | config: PipelineConfig, output_format_info | None | None |
| `HeatmapStage.run()` | Execute kernel regression optimization | context dict, progress_queue | context dict | Saves models, performance metrics |
| `PredictionStage` | Test evaluation with optional GWD features | config: PipelineConfig | None | None |
| `PredictionStage.run()` | Execute prediction evaluation on test data | context dict, progress_queue | context dict | Saves predictions, evaluation metrics |
| `PipelineStage` | Abstract base class for all pipeline stages | config: PipelineConfig | None | None |
| `PipelineStage.run()` | Abstract stage execution method | context dict, progress_queue | context dict | Must be implemented by subclasses |
| `PipelineConfig` | Configuration management for pipeline | args: argparse.Namespace | None | Validates and stores configuration |

<details>
<summary><strong>EMUSESPipeline Orchestrator</strong></summary>

```python
class EMUSESPipeline:
    def __init__(self, args):
        """Initialize pipeline with configuration and data structures.
        
        Parameters
        ----------
        args : argparse.Namespace
            Command-line arguments containing pipeline configuration
        """
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

        # Update total pipeline runtime
        total_runtime = time.time() - self.context["pipeline_metadata"]["start_time"]
        self.context["pipeline_metadata"]["total_runtime"] = total_runtime

        return self.context
```

</details>

<details>
<summary><strong>UMAPStage Implementation</strong></summary>

```python
class UMAPStage(PipelineStage):
    def __init__(self, config):
        """Initialize UMAP stage with configuration.
        
        Parameters
        ----------
        config : PipelineConfig
            Pipeline configuration containing UMAP parameters
        """
        super().__init__(config)
        self.trained_umap = None
        self.embeddings = None
        self.test_embeddings = None
        self.umap_model_path = None
        self.embeddings_path = None
        self.test_embeddings_path = None
        self.min_embeddings = None
        self.max_embeddings = None

    def run(self, context, progress_queue=None):
        """Execute UMAP dimensionality reduction and clustering.
        
        Parameters
        ----------
        context : dict
            Shared pipeline context containing input data
        progress_queue : Queue, optional
            Queue for progress updates
            
        Returns
        -------
        dict
            Updated context with UMAP results and clustering
        """
        logger.info("Starting UMAP Stage")
        
        # Load or use existing embeddings
        if getattr(self.config, "load_embeddings", None):
            logger.info(f"Loading precomputed embeddings from {self.config.load_embeddings}")
            self.embeddings = np.load(self.config.load_embeddings)
            context["embeddings"] = self.embeddings
        else:
            # Perform UMAP optimization with Optuna
            logger.info("Starting UMAP optimization with Optuna")
            
            # Get optimization parameters
            umap_trials = getattr(self.config, "umap_trials", 50)
            hdbscan_trials = getattr(self.config, "hdbscan_trials", 20)
            
            # Load optimization dictionary
            optim_dict_name = getattr(self.config, "optim_dict", "optim_dict_default")
            optim_dict = load_optim_dict(optim_dict_name)
            
            # Perform joint UMAP+HDBSCAN optimization
            best_params, study_results = optimize_umap_hdbscan(
                input_matrix=context["input_matrix"],
                optim_dict=optim_dict,
                umap_trials=umap_trials,
                hdbscan_trials=hdbscan_trials,
                output_folder=self.config.output_folder,
                random_state=getattr(self.config, "random_state", 42),
                progress_queue=progress_queue
            )
            
            # Train final UMAP model with best parameters
            self.trained_umap = train_final_umap(
                input_matrix=context["input_matrix"],
                best_params=best_params,
                random_state=getattr(self.config, "random_state", 42)
            )
            
            # Generate embeddings
            self.embeddings = self.trained_umap.transform(context["input_matrix"])
            context["embeddings"] = self.embeddings
            
            # Save UMAP model if requested
            if getattr(self.config, "save_umap", True):
                self.umap_model_path = self.config.output_folder / "umap_model.pkl"
                save_model(self.trained_umap, self.umap_model_path)
                context["umap_model_path"] = self.umap_model_path

        # Perform clustering on embeddings
        logger.info("Performing HDBSCAN clustering")
        cluster_labels, hdbscan_model = perform_clustering(
            embeddings=self.embeddings,
            min_cluster_size=getattr(self.config, "min_cluster_size", 5),
            random_state=getattr(self.config, "random_state", 42)
        )
        
        context["cluster_labels"] = cluster_labels
        context["hdbscan_model"] = hdbscan_model
        
        # Save clustering results
        if getattr(self.config, "save_hdbscan", True):
            hdbscan_path = self.config.output_folder / "hdbscan_model.pkl"
            save_model(hdbscan_model, hdbscan_path)
            context["hdbscan_model_path"] = hdbscan_path

        logger.info("UMAP Stage completed successfully")
        return context
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

<details>
<summary><strong>HeatmapStage Implementation</strong></summary>

```python
class HeatmapStage(PipelineStage):
    def __init__(self, config, output_format_info=None):
        """Initialize heatmap stage for multi-target prediction.
        
        Parameters
        ----------
        config : PipelineConfig
            Pipeline configuration
        output_format_info : list, optional
            Output format information for predictions
        """
        super().__init__(config)
        self.output_format_info = output_format_info or []

    def run(self, context, progress_queue=None):
        """Execute multi-target prediction with nested cross-validation.
        
        Parameters
        ----------
        context : dict
            Pipeline context containing embeddings and scores
        progress_queue : Queue, optional
            Progress monitoring queue
            
        Returns
        -------
        dict
            Updated context with trained models and performance metrics
        """
        logger.info("Starting Heatmap Stage - Multi-target Prediction")
        
        # Get prediction features and targets
        prediction_train_features = context.get("prediction_train_features")
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

        # Perform nested cross-validation for model optimization
        logger.info("Starting nested cross-validation optimization")
        
        models_performance, trained_models = perform_nested_cv_optimization(
            features=prediction_train_features,
            targets=prediction_train_labels,
            optim_dict=optim_dict_predict_selected,
            task_type=task,
            output_folder=self.config.output_folder,
            n_trials=getattr(self.config, "optuna_trials", 60),
            random_state=getattr(self.config, "random_state", 42),
            progress_queue=progress_queue
        )

        # Store results in context
        context["models_performance"] = models_performance
        context["trained_models"] = trained_models
        context["prediction_results"] = models_performance

        # Save performance results
        performance_file = self.config.output_folder / "performance_results.csv"
        save_performance_results(models_performance, performance_file)

        logger.info("Heatmap Stage completed successfully")
        return context
```

</details>

## Context Dictionary Structure

The pipeline system uses a shared context dictionary to pass data between stages:

### Input Data
- `input_matrix`: Preprocessed input features (numpy array)
- `scores`: Target variables for prediction (numpy array or pandas DataFrame)
- `paths_list`: File paths for original data samples
- `dataset_type`: Type identifier for the dataset

### Stage Results
- `embeddings`: UMAP dimensionality reduction results
- `cluster_labels`: HDBSCAN clustering assignments
- `umap_model_path`: Path to saved UMAP model
- `hdbscan_model_path`: Path to saved clustering model
- `trained_models`: Dictionary of optimized prediction models
- `models_performance`: Performance metrics for each model
- `prediction_results`: Final evaluation results

### Metadata
- `pipeline_metadata`: Execution timing and stage completion info
- `prediction_train_features`: Features for model training
- `prediction_train_labels`: Labels for model training

## CLI Integration Requirements

The new Typer CLI must understand this pipeline structure to:

1. **Translate CLI arguments** to pipeline context format
2. **Configure stage enablement** based on command selection
3. **Handle progress tracking** from pipeline execution
4. **Process results** for user feedback and artifact organization
5. **Maintain context consistency** when calling FastAPI service

Coverage context: [coverage_html/index.html](../coverage_html/index.html)
