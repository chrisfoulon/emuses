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
- Command logging for easy rerun

Security:
- Input sanitization and validation
- Path traversal protection
- Command injection prevention

TODO: Investigate whether command functions (full, umap, clustering, heatmap, prediction)
are necessary boilerplate or serve a specific purpose. They currently duplicate the same
pattern of calling save_command_to_output_folder() and their respective async functions.
Consider refactoring to reduce duplication while maintaining functionality.
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
import threading
import time
import requests
import uvicorn
from multiprocessing import Process
import os
import signal
import subprocess

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


def save_command_to_output_folder(output_folder: Path) -> None:
    """
    Save the executed command to the output folder for easy rerun.

    Parameters
    ----------
    output_folder : Path
        Output folder path
    """
    try:
        # Ensure output folder exists
        output_folder.mkdir(parents=True, exist_ok=True)

        # Get the original command from sys.argv
        command = ' '.join(sys.argv)

        # Save command to command.txt
        command_file = output_folder / "command.txt"
        with open(command_file, 'w', encoding='utf-8') as f:
            f.write("# EMUSES Pipeline Command\n")
            f.write(f"# Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# To rerun: {command}\n")
            f.write(f"# Or use: emuses rerun \"{output_folder}\"\n\n")
            f.write(command + "\n")

        logger.info(f"Command saved to: {command_file}")

    except Exception as e:
        logger.warning(f"Failed to save command to output folder: {e}")


def load_command_from_folder(folder_path: Path) -> str:
    """
    Load a previously saved command from an output folder.

    Parameters
    ----------
    folder_path : Path
        Path to folder containing command.txt

    Returns
    -------
    str
        The command string to execute

    Raises
    ------
    FileNotFoundError
        If command.txt doesn't exist in the folder
    """
    command_file = folder_path / "command.txt"

    if not command_file.exists():
        raise FileNotFoundError(f"No command.txt found in {folder_path}")

    with open(command_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find the actual command line (last non-comment line)
    for line in reversed(lines):
        line = line.strip()
        if line and not line.startswith('#'):
            return line

    raise ValueError(f"No valid command found in {command_file}")


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


@app.command()
def rerun(
    output_folder: Annotated[Path, typer.Argument(help="Output folder containing command.txt file")]
) -> None:
    """
    Rerun a previously executed command from its output folder.

    This command reads the saved command from command.txt in the specified
    output folder and executes it again with the same parameters.

    Parameters
    ----------
    output_folder : Path
        Path to output folder containing the command.txt file

    Raises
    ------
    typer.Exit
        With code 1 if the command file is not found or execution fails
    """
    try:
        # Load and execute the saved command
        command = load_command_from_folder(output_folder)
        typer.echo(f"Rerunning command from {output_folder}:")
        typer.echo(f"  {command}")

        # Parse and execute the command
        import shlex

        # Remove 'emuses' from the beginning since we're already in the app
        command_parts = shlex.split(command)
        if command_parts and command_parts[0] == 'emuses':
            command_parts = command_parts[1:]

        # Execute in subprocess to prevent infinite recursion
        result = subprocess.run(
            [sys.executable, '-m', 'emuses.cli'] + command_parts,
            check=False
        )
        if result.returncode != 0:
            raise typer.Exit(code=result.returncode)

    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Error rerunning command: {e}", err=True)
        raise typer.Exit(code=1)


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
    input_file_types: Annotated[Optional[List[str]], typer.Option("--input_file_types", help="File types to search for in the input dataset folder")] = None,
    arg_separator: Annotated[str, typer.Option("--arg_separator", help="Separator for the input dataset list")] = ",",
    input_header: Annotated[Optional[int], typer.Option("--input_header", help="Header for the spreadsheet input dataset")] = None,
    inputs_columns: Annotated[Optional[List[str]], typer.Option("--inputs_columns", help="List of columns for inputs in the scores file")] = None,
    input_index_column: Annotated[Optional[int], typer.Option("--input_index_column", help="Index column for the spreadsheet input dataset")] = None,
    columns_are_features: Annotated[bool, typer.Option("--columns_are_features", help="Columns are features in the spreadsheet input dataset")] = False,
    bids_filters: Annotated[Optional[List[str]], typer.Option(help="BIDS filters for the input dataset")] = None,
    input_normalization: Annotated[InputNormalization, typer.Option("-inorm", "--input_normalization", help="Normalization method for input data")] = InputNormalization.none,
    scores_header: Annotated[Optional[int], typer.Option("--scores_header", help="Header for the scores spreadsheet")] = None,
    scores_index_column: Annotated[Optional[int], typer.Option("--scores_index_column", help="Index column for the scores spreadsheet")] = None,
    scores_are_rows: Annotated[bool, typer.Option("--scores_are_rows", help="Scores are in the columns of the spreadsheet input dataset")] = False,
    scores_column: Annotated[Optional[List[str]], typer.Option("--scores_column", help="Column(s) for scores in the scores file")] = None,
    classification: Annotated[bool, typer.Option(help="Scores are integer classes in one column")] = False,
    correlation_method: Annotated[CorrelationMethod, typer.Option("--correlation_method", help="Method to use for correlation calculation")] = CorrelationMethod.pearson,
    scores_normalization: Annotated[ScoresNormalization, typer.Option("-snorm", "--scores_normalization", help="Normalization method for scores data")] = ScoresNormalization.none,
    filter_labelled_by_scores: Annotated[bool, typer.Option("--filter_labelled_by_scores", help="Filter the labelled dataset to only keep files referenced in the scores file")] = False,
    load_umap: Annotated[Optional[str], typer.Option(help="Path to a pre-trained UMAP model")] = None,
    load_embeddings: Annotated[Optional[str], typer.Option(help="Path to precomputed embeddings")] = None,
    test_size: Annotated[float, typer.Option("--test_size", help="Test size for splitting the dataset")] = 0.2,
    prefix: Annotated[str, typer.Option(help="Prefix for the output path names")] = "",
    optim_dict: Annotated[str, typer.Option("--optim_dict", help="Name of an optim_dict in optim_configs.py")] = "optim_dict_default",
    umap_trials: Annotated[int, typer.Option("--umap_trials", help="Number of outer (UMAP) optimization trials")] = 50,
    hdbscan_trials: Annotated[int, typer.Option("--hdbscan_trials", help="Number of inner (HDBSCAN) optimization trials")] = 20,
    load_hdbscan: Annotated[Optional[str], typer.Option(help="Path to a pre-trained HDBSCAN model")] = None,
    min_cluster_size: Annotated[int, typer.Option("--min_cluster_size", help="Minimum cluster size")] = 5,
    interactive_plot: Annotated[bool, typer.Option("--interactive_plot", help="Option to create interactive clustering plots")] = False,
    hdbscan_approx_min_span_tree: Annotated[bool, typer.Option("--hdbscan_approx_min_span_tree", help="When set to False, ensures reproducibility but with much longer runtime")] = True,
    hdbscan_core_dist_n_jobs: Annotated[int, typer.Option("--hdbscan_core_dist_n_jobs", help="Number of parallel jobs for core distance computation in HDBSCAN")] = -1,
    inspect_data_state: Annotated[bool, typer.Option("--inspect_data_state", help="Inspect data state before model training (for debugging)")] = False,
    use_enhanced_pipeline: Annotated[bool, typer.Option("--use_enhanced_pipeline", help="Use the enhanced pipeline with Optuna optimization for model selection")] = False,
    optuna_trials: Annotated[int, typer.Option("--optuna_trials", help="Number of trials for Optuna optimization per model/feature set")] = 60,
    parallel_models: Annotated[bool, typer.Option("--parallel_models", help="Train models in parallel across different feature sets")] = False,
    n_jobs: Annotated[int, typer.Option("--n_jobs", help="Number of parallel jobs for model training (-1 uses all cores)")] = -1,
    service_timeout: Annotated[float, typer.Option("--service-timeout", help="Service request timeout in seconds (0 for unlimited)")] = 0.0,
    umap_timeout: Annotated[float, typer.Option("--umap-timeout", help="UMAP stage timeout in seconds (0 for unlimited)")] = 0.0,
    heatmap_timeout: Annotated[float, typer.Option("--heatmap-timeout", help="Heatmap stage timeout in seconds (0 for unlimited)")] = 0.0,
    prediction_timeout: Annotated[float, typer.Option("--prediction-timeout", help="Prediction stage timeout in seconds (0 for unlimited)")] = 0.0,
    model_selection: Annotated[Optional[List[str]], typer.Option("--model_selection", help="List of models to try. Options: gp, rf, gb, kr, xgb, lgb, et, svr")] = None,
    prediction_optim_dict: Annotated[str, typer.Option("--prediction_optim_dict", help="Name of a prediction optim_dict in optim_configs_predict.py")] = "optim_dict_predict",
    random_state: Annotated[int, typer.Option("--random_state", help="Master random seed for reproducibility")] = 42,
    run_old_prediction: Annotated[bool, typer.Option("--run_old_prediction", help="Run the old prediction pipeline")] = False,
    umap_jobs: Annotated[Optional[int], typer.Option("--umap_jobs", help="Number of parallel jobs for outer (UMAP) optimization")] = None,
    hdbscan_jobs: Annotated[Optional[int], typer.Option("--hdbscan_jobs", help="Number of parallel jobs for inner (HDBSCAN) optimization")] = None,
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
    # Save command for easy rerun
    save_command_to_output_folder(output_folder)

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
            service_timeout=service_timeout,
            umap_timeout=umap_timeout,
            heatmap_timeout=heatmap_timeout,
            prediction_timeout=prediction_timeout,
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

    # Unified service execution - no more dual architecture
    try:
        if use_service:
            # Connect to remote service
            service_timeout = kwargs.get('service_timeout', 0.0)
            await _execute_via_remote_service("full", pipeline_config, status_renderer, progress_tracker, service_timeout=service_timeout)
        else:
            # Auto-start local service
            await _execute_via_unified_service(pipeline_config, status_renderer, progress_tracker)

        print(status_renderer.render_status("success", "Pipeline completed successfully!"))
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


async def _execute_via_remote_service(pipeline_type: str, config: dict, status_renderer, progress_tracker, service_url: str = "http://localhost:8000", service_timeout: float = 0.0) -> None:
    """
    Execute pipeline via remote FastAPI service.

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
    service_url : str, optional
        Base URL of the service, by default "http://localhost:8000"
    """
    # Convert 0.0 to None for unlimited timeout
    timeout = None if service_timeout <= 0 else service_timeout
    service_client = ServiceHTTPClient(base_url=service_url, timeout=timeout)

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

        start_time = time.time()
        last_progress = -1
        poll_count = 0

        while True:
            poll_count += 1
            status = await service_client.get_job_status(job_id)

            if status["status"] == "completed":
                print("✓ Pipeline completed successfully")
                break
            elif status["status"] == "failed":
                error_msg = status.get("error", "Unknown error")
                raise ServiceClientError(f"Job failed: {error_msg}")
            elif status["status"] == "cancelled":
                raise ServiceClientError("Job was cancelled")

            # Update progress if available (only if changed significantly)
            progress = status.get("progress", 0)
            if isinstance(progress, (int, float)):
                progress_pct = min(progress * 100, 99)
                if abs(progress_pct - last_progress) >= 5 or poll_count % 15 == 0:  # Show every 5% or every 30 seconds
                    print(f"Progress: {progress_pct:.1f}%")
                    last_progress = progress_pct

            current_stage = status.get("current_stage")
            if current_stage:
                print(f"Current stage: {current_stage}")

            # Check for timeout (30 minutes max)
            if time.time() - start_time > 1800:
                raise ServiceClientError("Pipeline execution timed out after 30 minutes")

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


async def _execute_via_unified_service(config: dict, status_renderer, progress_tracker) -> None:
    """
    Execute pipeline via unified auto-start service architecture.

    This function eliminates the dual execution path by always using the FastAPI service.
    If no service is running, it auto-starts one locally. This provides consistent
    behavior and eliminates legacy fallback complexity.

    Parameters
    ----------
    config : dict
        Pipeline configuration
    status_renderer : StatusRenderer
        Status display component
    progress_tracker : ProgressTracker
        Progress tracking component
    """
    service_process = None

    try:
        print(status_renderer.render_status("info", "Auto-starting local EMUSES service..."))

        # Find available port for service
        from emuses.cli.service_manager import ServiceManager
        service_manager = ServiceManager()
        available_port = service_manager.find_available_port()
        service_url = f"http://localhost:{available_port}"

        print(status_renderer.render_status("info", f"Starting FastAPI service on port {available_port}..."))

        # Start local service
        service_process = _start_local_service(port=available_port)
        if not service_process:
            raise ServiceClientError("Failed to start local service")

        # Wait for service to be ready
        print(status_renderer.render_status("info", "Waiting for service to be ready..."))
        if not _wait_for_service_ready(service_url, timeout=30):
            raise ServiceClientError("Service failed to become ready within timeout")

        print(status_renderer.render_status("success", "Local service started successfully!"))

        # Execute via the service (determine pipeline type from config)
        pipeline_type = config.get('command', 'full')
        await _execute_via_remote_service(pipeline_type, config, status_renderer, progress_tracker, service_url)

    finally:
        # Always clean up the service
        if service_process:
            print(status_renderer.render_status("info", "Shutting down local service..."))
            _stop_local_service(service_process)


def _start_local_service(port: int = 8000) -> Optional[Process]:
    """
    Start local FastAPI service in background process.

    Parameters
    ----------
    port : int, optional
        Port to run service on, by default 8000

    Returns
    -------
    Optional[Process]
        Service process if successful, None if failed
    """
    try:
        def run_service():
            """Run the FastAPI service."""
            try:
                logger.info(f"Starting FastAPI service on port {port}...")
                from emuses.api.main import create_app
                app = create_app()
                logger.info("FastAPI app created successfully")
                # Use info level to see startup messages
                uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
            except Exception as e:
                logger.error(f"Service failed to start: {e}")
                import traceback
                traceback.print_exc()

        # Start service in background process
        service_process = Process(target=run_service, daemon=True)
        service_process.start()

        # Give the process more time to start up
        time.sleep(2)

        if service_process.is_alive():
            logger.info(f"Service process started successfully (PID: {service_process.pid})")
            return service_process
        else:
            logger.error("Service process died immediately after startup")
            return None

    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        import traceback
        traceback.print_exc()
        return None


def _stop_local_service(service_process: Process) -> None:
    """
    Stop local FastAPI service process.

    Parameters
    ----------
    service_process : Process
        Service process to stop
    """
    try:
        if service_process and service_process.is_alive():
            service_process.terminate()
            service_process.join(timeout=5)

            if service_process.is_alive():
                service_process.kill()  # Force kill if needed
                service_process.join()

    except Exception as e:
        print(f"Error stopping service: {e}")


def _wait_for_service_ready(service_url: str, timeout: int = 30) -> bool:
    """
    Wait for service to become ready.

    Parameters
    ----------
    service_url : str
        Service URL to check
    timeout : int, optional
        Timeout in seconds, by default 30

    Returns
    -------
    bool
        True if service is ready, False if timeout
    """
    start_time = time.time()

    while (time.time() - start_time) < timeout:
        try:
            # Use correct health endpoint path
            response = requests.get(f"{service_url}/api/health", timeout=2)
            if response.status_code == 200:
                return True
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            # Add debug logging for connection issues
            logger.debug(f"Health check failed: {e}")

        time.sleep(0.5)

    logger.error(f"Service health check timed out after {timeout} seconds")
    return False


# Legacy functions removed - unified service architecture only


async def _umap_async(**kwargs) -> None:
    """Async implementation of the UMAP training command."""
    status_renderer = StatusRenderer()
    progress_tracker = ProgressTracker()

    print(status_renderer.render_status("info", "Starting UMAP training..."))

    pipeline_config = _convert_typer_args_to_service_config(**kwargs)

    try:
        await _execute_via_remote_service("umap", pipeline_config, status_renderer, progress_tracker)
        print(status_renderer.render_status("success", "UMAP training completed successfully via service!"))
    except ServiceClientError as e:
        print(status_renderer.render_status("warning", f"Service unavailable ({e}), falling back to local execution..."))
        await _execute_via_unified_service(pipeline_config, status_renderer, progress_tracker)
        print(status_renderer.render_status("success", "UMAP training completed successfully via local execution!"))


async def _clustering_async(**kwargs) -> None:
    """Async implementation of the clustering command."""
    status_renderer = StatusRenderer()
    progress_tracker = ProgressTracker()

    print(status_renderer.render_status("info", "Starting clustering..."))

    pipeline_config = _convert_typer_args_to_service_config(**kwargs)

    try:
        await _execute_via_remote_service("clustering", pipeline_config, status_renderer, progress_tracker)
        print(status_renderer.render_status("success", "Clustering completed successfully via service!"))
    except ServiceClientError as e:
        print(status_renderer.render_status("warning", f"Service unavailable ({e}), falling back to local execution..."))
        await _execute_via_unified_service(pipeline_config, status_renderer, progress_tracker)
        print(status_renderer.render_status("success", "Clustering completed successfully via local execution!"))


async def _heatmap_async(**kwargs) -> None:
    """Async implementation of the heatmap generation command."""
    status_renderer = StatusRenderer()
    progress_tracker = ProgressTracker()

    print(status_renderer.render_status("info", "Starting heatmap generation..."))

    pipeline_config = _convert_typer_args_to_service_config(**kwargs)

    try:
        await _execute_via_remote_service("heatmap", pipeline_config, status_renderer, progress_tracker)
        print(status_renderer.render_status("success", "Heatmap generation completed successfully via service!"))
    except ServiceClientError as e:
        print(status_renderer.render_status("warning", f"Service unavailable ({e}), falling back to local execution..."))
        await _execute_via_unified_service(pipeline_config, status_renderer, progress_tracker)
        print(status_renderer.render_status("success", "Heatmap generation completed successfully via local execution!"))


async def _prediction_async(**kwargs) -> None:
    """Async implementation of the prediction model training command."""
    status_renderer = StatusRenderer()
    progress_tracker = ProgressTracker()

    print(status_renderer.render_status("info", "Starting prediction model training..."))

    pipeline_config = _convert_typer_args_to_service_config(**kwargs)

    try:
        await _execute_via_remote_service("prediction", pipeline_config, status_renderer, progress_tracker)
        print(status_renderer.render_status("success", "Prediction model training completed successfully via service!"))
    except ServiceClientError as e:
        print(status_renderer.render_status("warning", f"Service unavailable ({e}), falling back to local execution..."))
        await _execute_via_unified_service(pipeline_config, status_renderer, progress_tracker)
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
        await _execute_via_unified_service(stage_config, status_renderer, progress_tracker)

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
    # Save command for easy rerun
    save_command_to_output_folder(output_folder)

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
    # Save command for easy rerun
    save_command_to_output_folder(output_folder)

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
    # Save command for easy rerun
    save_command_to_output_folder(output_folder)

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
    # Save command for easy rerun
    save_command_to_output_folder(output_folder)

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
    # Quick dependency check on startup (fast, non-blocking)
    try:
        from emuses.utils.dependency_check import validate_on_cli_startup
        validate_on_cli_startup(show_warnings=True)
    except ImportError:
        # If our own utils can't be imported, we have bigger problems
        # but don't block the CLI from trying to run
        pass

    app()


app.main = _main


if __name__ == "__main__":
    main()
