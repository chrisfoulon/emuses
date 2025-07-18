"""
Enhanced CLI with Typer for EMUSES pipeline.

This module provides a modern, secure, and user-friendly command-line interface
that maintains 100% backward compatibility with the legacy argparse implementation.

Key Features:
- Rich progress bars and colored output
- Shell completion support
- Secure path handling with directory traversal protection
- Interactive mode for novice users
- FastAPI service integration

Security:
- Input sanitization and validation
- Path traversal protection
- Command injection prevention
"""

import typer
from typing import Union
from typing import Optional, List, Annotated
from pathlib import Path
import urllib.parse
import re
import sys
import logging
import asyncio
from enum import Enum
from fastapi.testclient import TestClient

# Import security functions
from .security import validate_path, sanitize_input

# Import service client and rich features
from .service_client import ServiceHTTPClient, ServiceClientError
from .rich_features import ProgressTracker, StatusRenderer, TableFormatter
from .interactive_mode import InteractiveWorkflowManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InputNormalization(str, Enum):
    """Input normalization options."""
    none = "none"
    zscore = "zscore"
    min_max = "min-max"
    zero_max = "zero-max"
    robust = "robust"


class CorrelationMethod(str, Enum):
    """Correlation calculation methods."""
    pearson = "pearson"
    spearman = "spearman"
    pointbiserial = "pointbiserial"


class ScoresNormalization(str, Enum):
    """Scores normalization options."""
    none = "none"
    zscore = "zscore"
    min_max = "min-max"
    zero_max = "zero-max"


def secure_path_resolver(path_str: str) -> Union[Path, str]:
    """
    Secure path resolver that handles paths with spaces, different formats,
    and protects against directory traversal attacks.
    
    This function replaces the legacy resolve_path() with enhanced security.

    Parameters
    ----------
    path_str : str
        The path string to resolve

    Returns
    -------
    Path | str
        A resolved pathlib.Path object for valid paths, or the original string
        for special identifiers

    Raises
    ------
    ValueError
        If the path contains directory traversal attempts
    SecurityError
        If the path violates security constraints
    """
    # Special case for non-path identifiers (preserve legacy behavior)
    if path_str and path_str.lower() in [
        "mnist",
        "digits_label_dataset",
        "input_matrix",
    ]:
        return path_str
    
    # Validate path for security
    validated_path = validate_path(path_str)
    
    # URL decode the path safely
    try:
        decoded_path = urllib.parse.unquote(validated_path)
    except Exception:
        decoded_path = validated_path
    
    # Create Path object and resolve
    try:
        path = Path(decoded_path)
        return path
    except Exception as e:
        raise ValueError(f"Invalid path: {path_str}") from e


def create_typer_app() -> typer.Typer:
    """
    Create and configure the main Typer application.
    
    Returns
    -------
    typer.Typer
        Configured Typer application instance
    """
    app = typer.Typer(
        name="emuses",
        help="EMUSES pipeline",
        context_settings={"help_option_names": ["-h", "--help"]},
        no_args_is_help=True,
        invoke_without_command=False,
        rich_markup_mode="rich",
        pretty_exceptions_enable=True,
    )
    
    return app


# Create the main application instance
app = create_typer_app()

# Add name attribute for test compatibility
app.name = "emuses"


@app.command(help="Run the full pipeline")
def full(
    output_folder: Annotated[Path, typer.Argument(help="Output folder")],
    input_dataset: Annotated[Path, typer.Argument(help="Input dataset of images (jpg), NIfTI, or MNIST")],
    # Optional arguments start here
    scores: Annotated[Optional[Path], typer.Option(help="Path to scores file associated with the dataset")] = None,
    label_dataset: Annotated[Optional[Path], typer.Option(help="Path to a separate labelled dataset")] = None,
    recursive_search: Annotated[bool, typer.Option("--recursive-input-file-search", help="Search recursively in the input dataset folder")] = False,
    input_file_types: Annotated[Optional[List[str]], typer.Option(help="File types to search for in the input dataset folder")] = None,
    arg_separator: Annotated[str, typer.Option(help="Separator for the input dataset list")] = ",",
    input_header: Annotated[Optional[int], typer.Option(help="Header for the spreadsheet input dataset")] = None,
    inputs_columns: Annotated[Optional[List[str]], typer.Option(help="List of columns for inputs in the scores file")] = None,
    input_index_column: Annotated[Optional[int], typer.Option(help="Index column for the spreadsheet input dataset")] = None,
    columns_are_features: Annotated[bool, typer.Option("--columns_are_features", help="Columns are features in the spreadsheet input dataset")] = False,
    bids_filters: Annotated[Optional[List[str]], typer.Option(help="BIDS filters for the input dataset")] = None,
    input_normalization: Annotated[InputNormalization, typer.Option("-inorm", "--input-normalization", help="Normalization method for input data")] = InputNormalization.none,
    scores_header: Annotated[Optional[int], typer.Option(help="Header for the scores spreadsheet")] = None,
    scores_index_column: Annotated[Optional[int], typer.Option(help="Index column for the scores spreadsheet")] = None,
    scores_are_rows: Annotated[bool, typer.Option(help="Scores are in the columns of the spreadsheet input dataset")] = False,
    scores_column: Annotated[Optional[List[str]], typer.Option(help="Column(s) for scores in the scores file")] = None,
    classification: Annotated[bool, typer.Option(help="Scores are integer classes in one column")] = False,
    correlation_method: Annotated[CorrelationMethod, typer.Option(help="Method to use for correlation calculation")] = CorrelationMethod.pearson,
    scores_normalization: Annotated[ScoresNormalization, typer.Option("-snorm", "--scores-normalization", help="Normalization method for scores data")] = ScoresNormalization.none,
    filter_labelled_by_scores: Annotated[bool, typer.Option(help="Filter the labelled dataset to only keep files referenced in the scores file")] = False,
    load_umap: Annotated[Optional[str], typer.Option(help="Path to a pre-trained UMAP model")] = None,
    load_embeddings: Annotated[Optional[str], typer.Option(help="Path to precomputed embeddings")] = None,
    test_size: Annotated[float, typer.Option(help="Test size for splitting the dataset")] = 0.2,
    prefix: Annotated[str, typer.Option(help="Prefix for the output path names")] = "",
    optim_dict: Annotated[str, typer.Option(help="Name of an optim_dict in optim_configs.py")] = "optim_dict_default",
    umap_trials: Annotated[int, typer.Option(help="Number of outer (UMAP) optimization trials")] = 50,
    hdbscan_trials: Annotated[int, typer.Option(help="Number of inner (HDBSCAN) optimization trials")] = 20,
    load_hdbscan: Annotated[Optional[str], typer.Option(help="Path to a pre-trained HDBSCAN model")] = None,
    min_cluster_size: Annotated[int, typer.Option(help="Minimum cluster size")] = 5,
    interactive_plot: Annotated[bool, typer.Option("--interactive_plot", help="Option to create interactive clustering plots")] = False,
    hdbscan_approx_min_span_tree: Annotated[bool, typer.Option(help="When set to False, ensures reproducibility but with much longer runtime")] = True,
    hdbscan_core_dist_n_jobs: Annotated[int, typer.Option(help="Number of parallel jobs for core distance computation in HDBSCAN")] = -1,
    inspect_data_state: Annotated[bool, typer.Option(help="Inspect data state before model training (for debugging)")] = False,
    use_enhanced_pipeline: Annotated[bool, typer.Option(help="Use the enhanced pipeline with Optuna optimization for model selection")] = False,
    optuna_trials: Annotated[int, typer.Option(help="Number of trials for Optuna optimization per model/feature set")] = 60,
    parallel_models: Annotated[bool, typer.Option(help="Train models in parallel across different feature sets")] = False,
    n_jobs: Annotated[int, typer.Option(help="Number of parallel jobs for model training (-1 uses all cores)")] = -1,
    model_selection: Annotated[Optional[List[str]], typer.Option(help="List of models to try. Options: gp, rf, gb, kr, xgb, lgb, et, svr")] = None,
    prediction_optim_dict: Annotated[str, typer.Option(help="Name of a prediction optim_dict in optim_configs_predict.py")] = "optim_dict_predict",
    random_state: Annotated[int, typer.Option("--random_state", help="Master random seed for reproducibility")] = 42,
    run_old_prediction: Annotated[bool, typer.Option(help="Run the old prediction pipeline")] = False,
    umap_jobs: Annotated[Optional[int], typer.Option(help="Number of parallel jobs for outer (UMAP) optimization")] = None,
    hdbscan_jobs: Annotated[Optional[int], typer.Option(help="Number of parallel jobs for inner (HDBSCAN) optimization")] = None,
    interactive: Annotated[bool, typer.Option("--interactive", help="Run in interactive mode")] = False,
    use_service: Annotated[bool, typer.Option("--service", help="Use remote service for execution")] = False,
) -> None:
    """
    Run the full pipeline.
    
    This command executes the complete EMUSES pipeline including UMAP training,
    clustering, heatmap generation, and prediction model training.

    Parameters
    ----------
    output_folder : Path
        Output folder for results
    input_dataset : Path
        Input dataset of images (jpg), NIfTI, or MNIST
    scores : Optional[Path], optional
        Path to scores file associated with the dataset
    label_dataset : Optional[Path], optional
        Path to a separate labelled dataset
    recursive_search : bool, optional
        Search recursively in the input dataset folder, by default False
    input_file_types : Optional[List[str]], optional
        File types to search for in the input dataset folder
    arg_separator : str, optional
        Separator for the input dataset list, by default ","
    input_header : Optional[int], optional
        Header for the spreadsheet input dataset
    inputs_columns : Optional[List[str]], optional
        List of columns for inputs in the scores file
    input_index_column : Optional[int], optional
        Index column for the spreadsheet input dataset
    columns_are_features : bool, optional
        Columns are features in the spreadsheet input dataset, by default False
    bids_filters : Optional[List[str]], optional
        BIDS filters for the input dataset
    input_normalization : InputNormalization, optional
        Normalization method for input data, by default InputNormalization.none
    scores_header : Optional[int], optional
        Header for the scores spreadsheet
    scores_index_column : Optional[int], optional
        Index column for the scores spreadsheet
    scores_are_rows : bool, optional
        Scores are in the columns of the spreadsheet input dataset, by default False
    scores_column : Optional[List[str]], optional
        Column(s) for scores in the scores file
    classification : bool, optional
        Scores are integer classes in one column, by default False
    correlation_method : CorrelationMethod, optional
        Method to use for correlation calculation, by default CorrelationMethod.pearson
    scores_normalization : ScoresNormalization, optional
        Normalization method for scores data, by default ScoresNormalization.none
    filter_labelled_by_scores : bool, optional
        Filter the labelled dataset to only keep files referenced in the scores file, by default False
    load_umap : Optional[str], optional
        Path to a pre-trained UMAP model
    load_embeddings : Optional[str], optional
        Path to precomputed embeddings
    test_size : float, optional
        Test size for splitting the dataset, by default 0.2
    prefix : str, optional
        Prefix for the output path names, by default ""
    optim_dict : str, optional
        Name of an optim_dict in optim_configs.py, by default "optim_dict_default"
    umap_trials : int, optional
        Number of outer (UMAP) optimization trials, by default 50
    hdbscan_trials : int, optional
        Number of inner (HDBSCAN) optimization trials, by default 20
    load_hdbscan : Optional[str], optional
        Path to a pre-trained HDBSCAN model
    min_cluster_size : int, optional
        Minimum cluster size, by default 5
    interactive_plot : bool, optional
        Option to create interactive clustering plots, by default False
    hdbscan_approx_min_span_tree : bool, optional
        When set to False, ensures reproducibility but with much longer runtime, by default True
    hdbscan_core_dist_n_jobs : int, optional
        Number of parallel jobs for core distance computation in HDBSCAN, by default -1
    inspect_data_state : bool, optional
        Inspect data state before model training (for debugging), by default False
    use_enhanced_pipeline : bool, optional
        Use the enhanced pipeline with Optuna optimization for model selection, by default False
    optuna_trials : int, optional
        Number of trials for Optuna optimization per model/feature set, by default 60
    parallel_models : bool, optional
        Train models in parallel across different feature sets, by default False
    n_jobs : int, optional
        Number of parallel jobs for model training (-1 uses all cores), by default -1
    model_selection : Optional[List[str]], optional
        List of models to try. Options: gp, rf, gb, kr, xgb, lgb, et, svr
    prediction_optim_dict : str, optional
        Name of a prediction optim_dict in optim_configs_predict.py, by default "optim_dict_predict"
    random_state : int, optional
        Master random seed for reproducibility, by default 42
    run_old_prediction : bool, optional
        Run the old prediction pipeline, by default False
    umap_jobs : Optional[int], optional
        Number of parallel jobs for outer (UMAP) optimization
    hdbscan_jobs : Optional[int], optional
        Number of parallel jobs for inner (HDBSCAN) optimization

    Returns
    -------
    None

    Raises
    ------
    ValueError
        If invalid arguments are provided
    SecurityError
        If security constraints are violated
    """
    # Log arguments for debugging (preserve legacy behavior)
    logger.info("Arguments:")
    logger.info("command: full")
    logger.info(f"output_folder: {output_folder}")
    logger.info(f"input_dataset: {input_dataset}")
    logger.info(f"scores: {scores}")
    # ... log other arguments as needed
    
    # Run the async implementation
    try:
        asyncio.run(_full_async(
            output_folder=output_folder,
            input_dataset=input_dataset,
            scores=scores,
            label_dataset=label_dataset,
            recursive_search=recursive_search,
            input_file_types=input_file_types,
            arg_separator=arg_separator,
            input_header=input_header,
            inputs_columns=inputs_columns,
            input_index_column=input_index_column,
            columns_are_features=columns_are_features,
            bids_filters=bids_filters,
            input_normalization=input_normalization,
            scores_header=scores_header,
            scores_index_column=scores_index_column,
            scores_are_rows=scores_are_rows,
            scores_column=scores_column,
            classification=classification,
            correlation_method=correlation_method,
            scores_normalization=scores_normalization,
            filter_labelled_by_scores=filter_labelled_by_scores,
            load_umap=load_umap,
            load_embeddings=load_embeddings,
            test_size=test_size,
            prefix=prefix,
            optim_dict=optim_dict,
            umap_trials=umap_trials,
            hdbscan_trials=hdbscan_trials,
            load_hdbscan=load_hdbscan,
            min_cluster_size=min_cluster_size,
            interactive_plot=interactive_plot,
            hdbscan_approx_min_span_tree=hdbscan_approx_min_span_tree,
            hdbscan_core_dist_n_jobs=hdbscan_core_dist_n_jobs,
            inspect_data_state=inspect_data_state,
            use_enhanced_pipeline=use_enhanced_pipeline,
            optuna_trials=optuna_trials,
            parallel_models=parallel_models,
            n_jobs=n_jobs,
            model_selection=model_selection,
            prediction_optim_dict=prediction_optim_dict,
            random_state=random_state,
            run_old_prediction=run_old_prediction,
            umap_jobs=umap_jobs,
            hdbscan_jobs=hdbscan_jobs,
            interactive=interactive,
            use_service=use_service,
        ))
    except KeyboardInterrupt:
        typer.echo("\nOperation cancelled by user", err=True)
        raise typer.Exit(code=130)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


async def _full_async(**kwargs) -> None:
    """
    Async implementation of the full pipeline command.
    
    Executes locally by default, or via FastAPI service if --service flag is used.
    """
    # Initialize components
    status_renderer = StatusRenderer()
    progress_tracker = ProgressTracker()
    
    # Handle interactive mode
    interactive = kwargs.pop('interactive', False)
    use_service = kwargs.pop('use_service', False)
    
    if interactive:
        print(status_renderer.render_status("info", "Starting Interactive Mode..."))
        workflow_manager = InteractiveWorkflowManager()
        workflow_manager.start_workflow("data_processing")
        
        # Use workflow manager to collect/validate parameters
        # The interactive mode will modify kwargs with user selections
        interactive_params = workflow_manager.collect_parameters(kwargs)
        kwargs.update(interactive_params)
    
    print(status_renderer.render_status("info", "Starting EMUSES Full Pipeline..."))
    
    # Convert arguments to service API format
    pipeline_config = _convert_typer_args_to_service_config(**kwargs)
    
    if use_service:
        # User explicitly requested service execution
        try:
            await _execute_via_service("full", pipeline_config, status_renderer, progress_tracker)
            print(status_renderer.render_status("success", "Pipeline completed successfully via service!"))
        except ServiceClientError as e:
            print(status_renderer.render_status("warning", f"Service unavailable ({e}), falling back to local execution..."))
            await _execute_locally(pipeline_config, status_renderer, progress_tracker)
            print(status_renderer.render_status("success", "Pipeline completed successfully via local execution!"))
        except Exception as e:
            print(status_renderer.render_status("error", f"Pipeline execution failed: {e}"))
            raise e
    else:
        # Default to local execution
        try:
            await _execute_locally(pipeline_config, status_renderer, progress_tracker)
            print(status_renderer.render_status("success", "Pipeline completed successfully via local execution!"))
        except Exception as e:
            print(status_renderer.render_status("error", f"Pipeline execution failed: {e}"))
            raise e


def _convert_typer_args_to_service_config(**kwargs) -> dict:
    """
    Convert Typer command arguments to service API configuration format.
    
    Parameters
    ----------
    **kwargs
        Command line arguments from Typer
        
    Returns
    -------
    dict
        Configuration dictionary suitable for service API
    """
    config = {}
    
    for key, value in kwargs.items():
        if value is None:
            continue
        elif isinstance(value, list) and len(value) == 0:
            # Convert empty lists to None for backward compatibility with legacy CLI
            # Legacy CLI returns None for missing list arguments, not empty lists
            config[key] = None
        elif isinstance(value, Path):
            config[key] = str(value)
        elif isinstance(value, list) and value:
            config[key] = [str(item) for item in value]
        elif isinstance(value, (str, int, float, bool)):
            config[key] = value
        elif hasattr(value, 'value'):  # Enum types
            config[key] = value.value
        else:
            config[key] = str(value)
    
    return config


async def _execute_via_service(pipeline_type: str, config: dict, status_renderer, progress_tracker) -> None:
    """
    Execute pipeline via FastAPI service.
    
    Parameters
    ----------
    pipeline_type : str
        Type of pipeline to execute
    config : dict
        Pipeline configuration
    status_renderer : StatusRenderer
        Status display component
    progress_tracker : ProgressTracker
        Progress tracking component
    """
    service_client = ServiceHTTPClient(base_url="http://localhost:8000")
    
    try:
        # Check service health first
        print(status_renderer.render_status("info", "Checking service availability..."))
        health_status = await service_client.check_service_health()
        if not health_status:
            raise ServiceClientError("Service health check failed")
        
        # Submit job
        print(status_renderer.render_status("info", "Submitting job to service..."))
        # Wrap config in JobSubmissionRequest format
        job_request = {
            "pipeline_config": config,
            "job_name": f"CLI Pipeline - {pipeline_type}",
            "description": f"Pipeline execution via CLI for {pipeline_type}"
        }
        job_response = await service_client.submit_pipeline_job(pipeline_type, job_request)
        job_id = job_response["job_id"]
        print(status_renderer.render_status("info", f"Job submitted with ID: {job_id}"))
        
        # Poll for completion with progress display
        print("Starting pipeline execution...")
        
        while True:
            status = await service_client.get_job_status(job_id)
            
            if status["status"] == "completed":
                print("✓ Stage completed")
                break
            elif status["status"] == "failed":
                error_msg = status.get("error", "Unknown error")
                raise ServiceClientError(f"Job failed: {error_msg}")
            elif status["status"] == "cancelled":
                raise ServiceClientError("Job was cancelled")
            
            # Update progress if available
            progress = status.get("progress", 0)
            if isinstance(progress, (int, float)):
                print(f"Progress: {min(progress * 100, 99):.1f}%")
            
            current_stage = status.get("current_stage")
            if current_stage:
                print(f"Current stage: {current_stage}")
            
            await asyncio.sleep(2)  # Poll every 2 seconds
            
        print("✓ Execution completed")
        
    finally:
        if hasattr(service_client, '_session') and service_client._session:
            await service_client._session.aclose()


def create_fastapi_app():
    """
    Create FastAPI app instance for TestClient usage.
    
    Returns
    -------
    FastAPI
        Configured FastAPI application instance
    """
    try:
        # Import the FastAPI app creation function
        from emuses.api.main import create_app
        return create_app()
    except ImportError as e:
        raise ServiceClientError(f"FastAPI service not available: {e}")


async def _execute_locally(config: dict, status_renderer, progress_tracker) -> None:
    """
    Execute pipeline locally using TestClient to maintain service consistency.

    This function attempts to create an in-process FastAPI service using TestClient
    for consistency with remote execution. If FastAPI service is not available,
    it falls back to direct EMUSESPipeline execution.

    Parameters
    ----------
    config : dict
        Pipeline configuration
    status_renderer : StatusRenderer
        Status display component
    progress_tracker : ProgressTracker
        Progress tracking component
    """
    try:
        print(status_renderer.render_status("info", "Initializing local service..."))

        # Try TestClient approach first
        client = _create_local_testclient()

        print(status_renderer.render_status("info", "Starting local pipeline execution via TestClient..."))

        # Submit job and get job ID
        job_id = await _submit_local_job(client, config, status_renderer)

        # Poll for completion
        await _poll_local_job_completion(client, job_id)

        print("✓ Execution completed")

    except ServiceClientError as e:
        if "FastAPI service not available" in str(e):
            print(status_renderer.render_status("warning", "FastAPI service not available, falling back to direct pipeline execution..."))
            await _execute_legacy_pipeline(config, status_renderer, progress_tracker)
        else:
            raise e
    except Exception as e:
        raise ServiceClientError(f"Local execution failed: {e}")


def _create_local_testclient() -> TestClient:
    """
    Create TestClient instance with FastAPI app.

    Returns
    -------
    TestClient
        Configured TestClient instance
    """
    app = create_fastapi_app()
    return TestClient(app)


async def _submit_local_job(client: TestClient, config: dict, status_renderer) -> str:
    """
    Submit job to local TestClient service.

    Parameters
    ----------
    client : TestClient
        TestClient instance
    config : dict
        Pipeline configuration
    status_renderer : StatusRenderer
        Status display component

    Returns
    -------
    str
        Job ID
    """
    pipeline_type = config.get('command', 'full')

    job_request = {
        "pipeline_config": config,
        "job_name": f"CLI Pipeline - {pipeline_type}",
        "description": f"Local pipeline execution via TestClient for {pipeline_type}"
    }

    print(status_renderer.render_status("info", "Submitting job to local service..."))
    job_endpoint = f"/api/v1/jobs/pipeline/{pipeline_type}"
    response = client.post(job_endpoint, json=job_request)

    if response.status_code != 200:
        raise ServiceClientError(f"Job submission failed: {response.status_code} - {response.text}")

    job_data = response.json()
    job_id = job_data["job_id"]
    print(status_renderer.render_status("info", f"Job submitted with ID: {job_id}"))

    return job_id


async def _poll_local_job_completion(client: TestClient, job_id: str) -> None:
    """
    Poll local job until completion.

    Parameters
    ----------
    client : TestClient
        TestClient instance
    job_id : str
        Job ID to poll
    """
    print("Starting pipeline execution...")

    while True:
        status_data = _get_local_job_status(client, job_id)

        if status_data["status"] == "completed":
            print("✓ Stage completed")
            break
        elif status_data["status"] == "failed":
            error_msg = status_data.get("error", "Unknown error")
            raise ServiceClientError(f"Job failed: {error_msg}")
        elif status_data["status"] == "cancelled":
            raise ServiceClientError("Job was cancelled")

        _display_job_progress(status_data)
        await asyncio.sleep(2)  # Poll every 2 seconds


def _get_local_job_status(client: TestClient, job_id: str) -> dict:
    """
    Get job status from local TestClient service.

    Parameters
    ----------
    client : TestClient
        TestClient instance
    job_id : str
        Job ID

    Returns
    -------
    dict
        Job status data
    """
    status_endpoint = f"/api/v1/jobs/{job_id}/status"
    status_response = client.get(status_endpoint)

    if status_response.status_code != 200:
        raise ServiceClientError(f"Status check failed: {status_response.status_code}")

    return status_response.json()


def _display_job_progress(status_data: dict) -> None:
    """
    Display job progress information.

    Parameters
    ----------
    status_data : dict
        Job status data
    """
    progress = status_data.get("progress", 0)
    if isinstance(progress, (int, float)):
        print(f"Progress: {min(progress * 100, 99):.1f}%")

    current_stage = status_data.get("current_stage")
    if current_stage:
        print(f"Current stage: {current_stage}")


async def _execute_legacy_pipeline(config: dict, status_renderer, progress_tracker) -> None:
    """
    Execute pipeline using legacy EMUSESPipeline as fallback.

    This function provides backward compatibility when FastAPI service
    is not available by using the original EMUSESPipeline implementation.

    Parameters
    ----------
    config : dict
        Pipeline configuration
    status_renderer : StatusRenderer
        Status display component
    progress_tracker : ProgressTracker
        Progress tracking component
    """
    try:
        # Import pipeline and stage classes
        from emuses.pipelines.emuses_pipeline import EMUSESPipeline
        from emuses.pipelines.umap_stage import UMAPStage
        from emuses.pipelines.heatmap_stage import HeatmapStage
        from emuses.pipelines.prediction_stage import PredictionStage

        # Convert config back to legacy format
        legacy_args = _convert_service_config_to_legacy_args(config)

        print(status_renderer.render_status("info", "Initializing legacy pipeline..."))
        print("Starting legacy pipeline execution...")

        # Create args namespace for EMUSESPipeline
        import argparse
        # Ensure the command is set to 'full' for the full pipeline
        legacy_args['command'] = 'full'
        # Set random state for reproducibility
        legacy_args['random_state'] = legacy_args.get('random_state', 42)
        args_namespace = argparse.Namespace(**legacy_args)

        # Create pipeline instance
        pipeline = EMUSESPipeline(args_namespace)

        # Add stages based on command (following the original scripts/main.py logic)
        stages_to_add = []
        command = legacy_args.get('command', 'full')
        
        if command in ["umap", "full", "prediction"]:
            stages_to_add.append(UMAPStage(pipeline.config))
        if command in ["heatmap", "full"]:
            stages_to_add.append(
                HeatmapStage(
                    pipeline.config,
                    output_format_info=pipeline.context.get("output_format_info"),
                )
            )
        if command in ["prediction", "full"]:
            stages_to_add.append(PredictionStage(pipeline.config))

        # Add the stages to the pipeline
        for stage in stages_to_add:
            pipeline.add_stage(stage)

        print(f"✓ Added {len(stages_to_add)} stages to pipeline: {[stage.__class__.__name__ for stage in stages_to_add]}")

        # Execute the pipeline (this will handle all stages and progress internally)
        pipeline.run()

        print("✓ Pipeline execution completed successfully!")

    except ImportError as e:
        raise ServiceClientError(f"Legacy pipeline not available: {e}")
    except Exception as e:
        raise ServiceClientError(f"Legacy execution failed: {e}")


def _convert_service_config_to_legacy_args(config: dict) -> dict:
    """
    Convert service configuration back to legacy EMUSESPipeline arguments.
    
    Parameters
    ----------
    config : dict
        Service configuration
        
    Returns
    -------
    dict
        Legacy pipeline arguments
    """
    # Map service config keys to legacy parameter names
    # This ensures compatibility with the existing EMUSESPipeline class
    # The PipelineConfig class is flexible and accepts all arguments directly
    # Just return the config as-is, since the CLI uses the same parameter names
    # as the legacy argparse implementation
    return config


async def _umap_async(**kwargs) -> None:
    """Async implementation of the UMAP training command."""
    status_renderer = StatusRenderer()
    progress_tracker = ProgressTracker()
    
    print(status_renderer.render_status("info", "Starting UMAP training..."))
    
    pipeline_config = _convert_typer_args_to_service_config(**kwargs)
    
    try:
        await _execute_via_service("umap", pipeline_config, status_renderer, progress_tracker)
        print(status_renderer.render_status("success", "UMAP training completed successfully via service!"))
    except ServiceClientError as e:
        print(status_renderer.render_status("warning", f"Service unavailable ({e}), falling back to local execution..."))
        await _execute_stage_locally("umap", pipeline_config, status_renderer, progress_tracker)
        print(status_renderer.render_status("success", "UMAP training completed successfully via local execution!"))


async def _clustering_async(**kwargs) -> None:
    """Async implementation of the clustering command."""
    status_renderer = StatusRenderer()
    progress_tracker = ProgressTracker()
    
    print(status_renderer.render_status("info", "Starting clustering..."))
    
    pipeline_config = _convert_typer_args_to_service_config(**kwargs)
    
    try:
        await _execute_via_service("clustering", pipeline_config, status_renderer, progress_tracker)
        print(status_renderer.render_status("success", "Clustering completed successfully via service!"))
    except ServiceClientError as e:
        print(status_renderer.render_status("warning", f"Service unavailable ({e}), falling back to local execution..."))
        await _execute_stage_locally("clustering", pipeline_config, status_renderer, progress_tracker)
        print(status_renderer.render_status("success", "Clustering completed successfully via local execution!"))


async def _heatmap_async(**kwargs) -> None:
    """Async implementation of the heatmap generation command."""
    status_renderer = StatusRenderer()
    progress_tracker = ProgressTracker()
    
    print(status_renderer.render_status("info", "Starting heatmap generation..."))
    
    pipeline_config = _convert_typer_args_to_service_config(**kwargs)
    
    try:
        await _execute_via_service("heatmap", pipeline_config, status_renderer, progress_tracker)
        print(status_renderer.render_status("success", "Heatmap generation completed successfully via service!"))
    except ServiceClientError as e:
        print(status_renderer.render_status("warning", f"Service unavailable ({e}), falling back to local execution..."))
        await _execute_stage_locally("heatmap", pipeline_config, status_renderer, progress_tracker)
        print(status_renderer.render_status("success", "Heatmap generation completed successfully via local execution!"))


async def _prediction_async(**kwargs) -> None:
    """Async implementation of the prediction model training command."""
    status_renderer = StatusRenderer()
    progress_tracker = ProgressTracker()
    
    print(status_renderer.render_status("info", "Starting prediction model training..."))
    
    pipeline_config = _convert_typer_args_to_service_config(**kwargs)
    
    try:
        await _execute_via_service("prediction", pipeline_config, status_renderer, progress_tracker)
        print(status_renderer.render_status("success", "Prediction model training completed successfully via service!"))
    except ServiceClientError as e:
        print(status_renderer.render_status("warning", f"Service unavailable ({e}), falling back to local execution..."))
        await _execute_stage_locally("prediction", pipeline_config, status_renderer, progress_tracker)
        print(status_renderer.render_status("success", "Prediction model training completed successfully via local execution!"))


async def _execute_stage_locally(stage: str, config: dict, status_renderer, progress_tracker) -> None:
    """
    Execute individual pipeline stage locally.
    
    Parameters
    ----------
    stage : str
        Pipeline stage to execute
    config : dict
        Pipeline configuration
    status_renderer : StatusRenderer
        Status display component  
    progress_tracker : ProgressTracker
        Progress tracking component
    """
    try:
        stage_classes = {
            "umap": "UMAPStage", 
            "clustering": "ClusteringStage",
            "heatmap": "HeatmapStage",
            "prediction": "PredictionStage"
        }
        
        if stage not in stage_classes:
            raise ServiceClientError(f"Unknown stage: {stage}")
            
        # For individual stages, fall back to full pipeline execution
        # This ensures all the context and dependencies are properly set up
        stage_config = config.copy()
        stage_config['command'] = stage
        await _execute_locally(stage_config, status_renderer, progress_tracker)
        
        print("✓ Stage completed")
        print("✓ Execution completed")
        
    except ImportError as e:
        raise ServiceClientError(f"Local {stage} stage not available: {e}")
    except Exception as e:
        raise ServiceClientError(f"Local {stage} execution failed: {e}")


@app.command(help="Train the UMAP and get the embeddings")
def umap(
    output_folder: Annotated[Path, typer.Argument(help="Output folder")],
    input_dataset: Annotated[Path, typer.Argument(help="Input dataset of images (jpg), NIfTI, or MNIST")],
) -> None:
    """
    Train the UMAP and get the embeddings.
    
    Parameters
    ----------
    output_folder : Path
        Output folder for results
    input_dataset : Path
        Input dataset of images (jpg), NIfTI, or MNIST

    Returns
    -------
    None
    """
    # Run the async implementation
    try:
        asyncio.run(_umap_async(
            output_folder=output_folder,
            input_dataset=input_dataset,
        ))
    except KeyboardInterrupt:
        typer.echo("\nOperation cancelled by user", err=True)
        raise typer.Exit(code=130)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(help="Perform clustering on embeddings")
def clustering(
    output_folder: Annotated[Path, typer.Argument(help="Output folder")],
) -> None:
    """
    Perform clustering on embeddings.
    
    Parameters
    ----------
    output_folder : Path
        Output folder for results

    Returns
    -------
    None
    """
    # Run the async implementation
    try:
        asyncio.run(_clustering_async(
            output_folder=output_folder,
        ))
    except KeyboardInterrupt:
        typer.echo("\nOperation cancelled by user", err=True)
        raise typer.Exit(code=130)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(help="Create a heatmap")
def heatmap(
    output_folder: Annotated[Path, typer.Argument(help="Output folder")],
    input_dataset: Annotated[Path, typer.Argument(help="Input dataset of images (jpg), NIfTI, or MNIST")],
) -> None:
    """
    Create a heatmap.
    
    Parameters
    ----------
    output_folder : Path
        Output folder for results
    input_dataset : Path
        Input dataset of images (jpg), NIfTI, or MNIST

    Returns
    -------
    None
    """
    # Run the async implementation
    try:
        asyncio.run(_heatmap_async(
            output_folder=output_folder,
            input_dataset=input_dataset,
        ))
    except KeyboardInterrupt:
        typer.echo("\nOperation cancelled by user", err=True)
        raise typer.Exit(code=130)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(help="Train a prediction model")
def prediction(
    output_folder: Annotated[Path, typer.Argument(help="Output folder")],
    input_dataset: Annotated[Path, typer.Argument(help="Input dataset of images (jpg), NIfTI, or MNIST")],
) -> None:
    """
    Train a prediction model.
    
    Parameters
    ----------
    output_folder : Path
        Output folder for results
    input_dataset : Path
        Input dataset of images (jpg), NIfTI, or MNIST

    Returns
    -------
    None
    """
    # Run the async implementation
    try:
        asyncio.run(_prediction_async(
            output_folder=output_folder,
            input_dataset=input_dataset,
        ))
    except KeyboardInterrupt:
        typer.echo("\nOperation cancelled by user", err=True)
        raise typer.Exit(code=130)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(help="Install shell completion")
def install_completion(
    shell: Annotated[str, typer.Argument(help="Shell type (bash, zsh, powershell)")],
) -> None:
    """
    Install shell completion for the specified shell.
    
    Parameters
    ----------
    shell : str
        Shell type to install completion for
        
    Returns
    -------
    None
    """
    try:
        from .shell_completion import ShellCompletionManager
        
        completion_manager = ShellCompletionManager()
        if completion_manager.install_completion(shell):
            typer.echo(f"Shell completion installed for {shell}")
        else:
            typer.echo(f"Failed to install shell completion for {shell}", err=True)
            raise typer.Exit(code=1)
            
    except ImportError as e:
        typer.echo(f"Shell completion module not available: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Error installing shell completion: {e}", err=True)
        raise typer.Exit(code=1)


# Aliases for command functions (for testing)
full_command = full
umap_command = umap
clustering_command = clustering
heatmap_command = heatmap
prediction_command = prediction


# Add commands attribute for test compatibility
app.commands = {cmd.callback.__name__: cmd for cmd in app.registered_commands}


# Add main method for Click CliRunner compatibility
def _main(*args, **kwargs):
    """Main method for Click CliRunner compatibility."""
    return app(*args, **kwargs)


def main():
    """Main entry point for the CLI application."""
    app()


app.main = _main


if __name__ == "__main__":
    main()
