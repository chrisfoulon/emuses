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

import asyncio
import logging
import re
import subprocess
import sys
import time
import urllib.parse
import warnings
from enum import Enum
from multiprocessing import Process
from pathlib import Path
from typing import Annotated, List, Optional, Union

# Suppress sklearn warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn.pipeline")
# Suppress sklearn deprecation warnings from dependencies (UMAP, HDBSCAN) until they update
warnings.filterwarnings("ignore", message="'force_all_finite' was renamed to 'ensure_all_finite'")

import requests
import typer
import uvicorn

from emuses import __version__
from .interactive_mode import InteractiveWorkflowManager
from .rich_features import ProgressTracker, StatusRenderer
# Import security functions
from .security import validate_path
# Import service client and rich features
from .service_client import ServiceClientError, ServiceHTTPClient

# Note: Logging is configured by pipeline_config to ensure file output
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
    robust = "robust"


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

        # Get the original command from sys.argv with cross-platform quoting
        def quote_argument_cross_platform(arg: str) -> str:
            """
            Quote a command-line argument in a cross-platform way.

            This function handles file paths and arguments safely across Unix, Linux,
            macOS, and Windows systems without relying on shlex.quote (which is Unix-only).

            For file paths, we use simple double-quote wrapping since:
            1. Double quotes work on both Unix and Windows shells
            2. Double quote is a reserved character in all major filesystems,
               so no valid file path can contain it
            3. This avoids the complex platform-specific quoting rules

            Parameters
            ----------
            arg : str
                The argument to quote

            Returns
            -------
            str
                Safely quoted argument
            """
            # If argument doesn't need quoting, return as-is
            if not any(
                char in arg
                for char in [
                    " ",
                    "\t",
                    "\n",
                    '"',
                    "'",
                    "\\",
                    "&",
                    "|",
                    ";",
                    "<",
                    ">",
                    "(",
                    ")",
                    "$",
                    "`",
                ]
            ):
                return arg

            # For arguments that need quoting, use double quotes
            # Handle any existing double quotes and backslashes properly
            escaped_arg = arg.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped_arg}"'

        # Apply cross-platform quoting to all arguments
        quoted_args = [quote_argument_cross_platform(arg) for arg in sys.argv]

        # Normalize direct __main__.py calls to proper module invocation
        if (
            quoted_args
            and "__main__.py" in quoted_args[0]
            and "emuses/cli" in quoted_args[0]
        ):
            quoted_args[0] = "python -m emuses.cli"

        command = " ".join(quoted_args)

        # Save command to command.txt
        command_file = output_folder / "command.txt"
        with open(command_file, "w", encoding="utf-8") as f:
            f.write("# EMUSES Pipeline Command\n")
            f.write(f"# Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# To rerun: {command}\n")
            f.write(f'# Or use: emuses rerun "{output_folder}"\n\n')
            f.write(command + "\n")

        logger.info(f"Command saved to: {command_file}")

    except Exception as e:
        logger.warning(f"Failed to save command to output folder: {e}")


def load_command_from_folder(folder_path: Path) -> str:
    """
    Load a previously saved command from an output folder.

    Handles both new (properly quoted) and old (unquoted) command formats
    for backward compatibility with existing command files.

    Parameters
    ----------
    folder_path : Path
        Path to folder containing command.txt

    Returns
    -------
    str
        The command string to execute, with proper quoting applied

    Raises
    ------
    FileNotFoundError
        If command.txt doesn't exist in the folder
    ValueError
        If no valid command found or command cannot be parsed
    """
    command_file = folder_path / "command.txt"

    if not command_file.exists():
        raise FileNotFoundError(f"No command.txt found in {folder_path}")

    with open(command_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find the actual command line (last non-comment line)
    command_line = None
    for line in reversed(lines):
        line = line.strip()
        if line and not line.startswith("#"):
            command_line = line
            break

    if not command_line:
        raise ValueError(f"No valid command found in {command_file}")

    # Try to parse with shlex first (handles new quoted format)
    import shlex

    try:
        parsed_parts = shlex.split(command_line)

        # Check if the command has intact paths with spaces
        # If paths with spaces are properly quoted, they should appear as single parts
        has_split_paths = False
        for part in parsed_parts:
            # Look for typical signs of split paths
            if (
                "Dropbox/Chris" in part
                and not part.startswith("/mnt/s/GIN")
                or "Foulon/EMUSE" in part
                and not part.startswith("/mnt/")
                or part.endswith("/selected_columns_data.csv")
                and not part.startswith("/mnt/")
                or part.endswith("/fluid_int_adj.csv")
                and not part.startswith("/mnt/")
            ):
                has_split_paths = True
                break

        # If no split paths detected and parsing succeeded, command is properly quoted
        if not has_split_paths and len(parsed_parts) >= 3:
            return command_line

    except ValueError:
        # Parsing failed, probably due to unmatched quotes or other issues
        pass

    # If we reach here, we have an old unquoted command that needs fixing
    # Apply heuristic reconstruction for backward compatibility
    try:
        fixed_command = _fix_unquoted_command(command_line)
        return fixed_command
    except Exception as e:
        raise ValueError(f"Could not parse command from {command_file}: {e}")


def _fix_unquoted_command(command_line: str) -> str:
    """
    Fix old command files that don't have proper quoting for paths with spaces.

    This function handles backward compatibility with command files created
    before the cross-platform quoting fix was implemented.

    Parameters
    ----------
    command_line : str
        The unquoted command line from an old command file

    Returns
    -------
    str
        The command line with proper quoting applied

    Algorithm
    ---------
    Uses regex pattern matching to identify and reconstruct split file paths
    while preserving all other command line arguments.
    """
    import re

    # Pattern to match file paths that got split by spaces
    # Look for patterns like: /mnt/s/GIN Dropbox/Chris Foulon/...filename.ext
    path_pattern = r"(/mnt/s/GIN)\s+(Dropbox/\S+)\s+(Foulon/\S+\.csv)"

    def replace_split_path(match):
        """Reconstruct and quote a split path."""
        prefix = match.group(1)  # /mnt/s/GIN
        middle = match.group(2)  # Dropbox/Chris
        suffix = match.group(3)  # Foulon/EMUSE/HCP_psy/filename.csv

        full_path = f"{prefix} {middle} {suffix}"
        return f'"{full_path}"'

    # Apply the pattern replacement
    fixed_command = re.sub(path_pattern, replace_split_path, command_line)

    return fixed_command


def _is_complete_file_path(path_str: str) -> bool:
    """
    Check if a string looks like a complete file path.

    Used to detect when we've successfully reconstructed a full path.
    """
    # Must end with a file extension
    if not re.search(r"\.[a-zA-Z0-9]{1,6}$", path_str):
        return False

    # Check for reasonable path patterns
    if path_str.endswith(
        (".csv", ".json", ".txt", ".py", ".db", ".xlsx", ".parquet")
    ) and ("/" in path_str or "\\" in path_str):
        return True

    return False


def _looks_like_reasonable_path(path_str: str) -> bool:
    """
    Check if a string looks like a reasonable file path.

    Used for heuristic path reconstruction when paths don't exist yet.
    """
    # Check for common path patterns
    if (
        path_str.endswith((".csv", ".json", ".txt", ".py", ".db"))
        or "/mnt/" in path_str
        or "Dropbox" in path_str
        or "GIN" in path_str
        or "EMUSE" in path_str
        or "HCP" in path_str
    ):
        return True

    # Check for reasonable path structure (more than just spaces)
    if "/" in path_str and not path_str.count("/") == path_str.count(" "):
        return True

    return False


def _quote_path_if_needed(path_str: str) -> str:
    """Apply quoting to a path if it contains spaces or special characters."""
    if " " in path_str or any(
        char in path_str
        for char in ['"', "'", "\\", "&", "|", ";", "<", ">", "(", ")", "$", "`"]
    ):
        escaped_path = path_str.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped_path}"'
    return path_str


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


def _version_callback(value: bool):
    """Callback to show version and exit."""
    if value:
        typer.echo(f"emuses {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version", "-V",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit"
        )
    ] = None,
):
    """
    EMUSES - Enhanced Multimodal Unified Statistical Embedding System

    A comprehensive neuroimaging analysis pipeline for dimensionality reduction,
    clustering, and predictive modeling.
    """
    pass


@app.command()
def rerun(
    output_folder: Annotated[
        Path, typer.Argument(help="Output folder containing command.txt file")
    ],
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

        # Remove executable path (emuses or absolute path) from the beginning
        command_parts = shlex.split(command)
        if command_parts and (
            "emuses" in command_parts[0] or command_parts[0].startswith("/")
        ):
            command_parts = command_parts[1:]  # Remove first element (executable path)

        # Execute in subprocess to prevent infinite recursion
        result = subprocess.run(
            [sys.executable, "-m", "emuses.cli"] + command_parts, check=False
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
    input_dataset: Annotated[
        Path, typer.Argument(help="Input dataset of images (jpg), NIfTI, or MNIST")
    ],
    # Optional arguments start here
    scores: Annotated[
        Optional[Path],
        typer.Option(help="Path to scores file associated with the dataset"),
    ] = None,
    label_dataset: Annotated[
        Optional[Path], typer.Option("--label_dataset", help="Path to a separate labelled dataset")
    ] = None,
    recursive_search: Annotated[
        bool,
        typer.Option(
            "--recursive-input-file-search",
            help="Search recursively in the input dataset folder",
        ),
    ] = False,
    input_file_types: Annotated[
        Optional[List[str]],
        typer.Option(
            "--input_file_types",
            help="File types to search for in the input dataset folder",
        ),
    ] = None,
    arg_separator: Annotated[
        str,
        typer.Option("--arg_separator", help="Separator for the input dataset list"),
    ] = ",",
    input_header: Annotated[
        Optional[int],
        typer.Option("--input_header", help="Header for the spreadsheet input dataset"),
    ] = None,
    inputs_columns: Annotated[
        Optional[List[str]],
        typer.Option(
            "--inputs_columns", help="List of columns for inputs in the scores file"
        ),
    ] = None,
    input_index_column: Annotated[
        Optional[int],
        typer.Option(
            "--input_index_column",
            help="Index column for the spreadsheet input dataset",
        ),
    ] = None,
    columns_are_features: Annotated[
        bool,
        typer.Option(
            "--columns_are_features",
            help="Columns are features in the spreadsheet input dataset",
        ),
    ] = False,
    bids_filters: Annotated[
        Optional[List[str]], typer.Option(help="BIDS filters for the input dataset")
    ] = None,
    input_normalization: Annotated[
        InputNormalization,
        typer.Option(
            "-inorm",
            "--input_normalization",
            help="Normalization method for input data",
        ),
    ] = InputNormalization.none,
    scores_header: Annotated[
        Optional[int],
        typer.Option("--scores_header", help="Header for the scores spreadsheet"),
    ] = None,
    scores_index_column: Annotated[
        Optional[int],
        typer.Option(
            "--scores_index_column", help="Index column for the scores spreadsheet"
        ),
    ] = None,
    scores_are_rows: Annotated[
        bool,
        typer.Option(
            "--scores_are_rows",
            help="Scores are in the columns of the spreadsheet input dataset",
        ),
    ] = False,
    scores_column: Annotated[
        Optional[List[str]],
        typer.Option("--scores_column", help="Column(s) for scores in the scores file"),
    ] = None,
    classification: Annotated[
        bool, typer.Option(help="Scores are integer classes in one column")
    ] = False,
    correlation_method: Annotated[
        CorrelationMethod,
        typer.Option(
            "--correlation_method", help="Method to use for correlation calculation"
        ),
    ] = CorrelationMethod.pearson,
    scores_normalization: Annotated[
        ScoresNormalization,
        typer.Option(
            "-snorm",
            "--scores_normalization",
            help="Normalization method for scores data",
        ),
    ] = ScoresNormalization.none,
    filter_labelled_by_scores: Annotated[
        bool,
        typer.Option(
            "--filter_labelled_by_scores",
            help="Filter the labelled dataset to only keep files referenced in the scores file",
        ),
    ] = False,
    load_umap: Annotated[
        Optional[str], typer.Option(help="Path to a pre-trained UMAP model")
    ] = None,
    load_embeddings: Annotated[
        Optional[str], typer.Option(help="Path to precomputed embeddings")
    ] = None,
    test_size: Annotated[
        float, typer.Option("--test_size", help="Test size for splitting the dataset")
    ] = 0.2,
    prefix: Annotated[str, typer.Option(help="Prefix for the output path names")] = "",
    optim_dict: Annotated[
        str,
        typer.Option("--optim_dict", help="Name of an optim_dict in optim_configs.py"),
    ] = "optim_dict_default",
    umap_trials: Annotated[
        int,
        typer.Option(
            "--umap_trials", help="Number of outer (UMAP) optimization trials"
        ),
    ] = 50,
    hdbscan_trials: Annotated[
        int,
        typer.Option(
            "--hdbscan_trials", help="Number of inner (HDBSCAN) optimization trials"
        ),
    ] = 20,
    load_hdbscan: Annotated[
        Optional[str], typer.Option(help="Path to a pre-trained HDBSCAN model")
    ] = None,
    min_cluster_size: Annotated[
        int, typer.Option("--min_cluster_size", help="Minimum cluster size")
    ] = 5,
    interactive_plot: Annotated[
        bool,
        typer.Option(
            "--interactive_plot", help="Option to create interactive clustering plots"
        ),
    ] = False,
    hdbscan_approx_min_span_tree: Annotated[
        bool,
        typer.Option(
            "--hdbscan_approx_min_span_tree",
            help="When set to False, ensures reproducibility but with much longer runtime",
        ),
    ] = True,
    hdbscan_core_dist_n_jobs: Annotated[
        int,
        typer.Option(
            "--hdbscan_core_dist_n_jobs",
            help="Number of parallel jobs for core distance computation in HDBSCAN",
        ),
    ] = -1,
    inspect_data_state: Annotated[
        bool,
        typer.Option(
            "--inspect_data_state",
            help="Inspect data state before model training (for debugging)",
        ),
    ] = False,
    use_enhanced_pipeline: Annotated[
        bool,
        typer.Option(
            "--use_enhanced_pipeline",
            help="Use the enhanced pipeline with Optuna optimization for model selection",
        ),
    ] = False,
    optuna_trials: Annotated[
        int,
        typer.Option(
            "--optuna_trials",
            help="Number of trials for Optuna optimization per model/feature set",
        ),
    ] = 60,
    parallel_models: Annotated[
        bool,
        typer.Option(
            "--parallel_models",
            help="Train models in parallel across different feature sets",
        ),
    ] = False,
    n_jobs: Annotated[
        int,
        typer.Option(
            "--n_jobs",
            help="Number of parallel jobs for model training (-1 uses all cores)",
        ),
    ] = -1,
    service_timeout: Annotated[
        float,
        typer.Option(
            "--service-timeout",
            help="Service request timeout in seconds (0 for unlimited)",
        ),
    ] = 0.0,
    umap_timeout: Annotated[
        float,
        typer.Option(
            "--umap-timeout", help="UMAP stage timeout in seconds (0 for unlimited)"
        ),
    ] = 0.0,
    heatmap_timeout: Annotated[
        float,
        typer.Option(
            "--heatmap-timeout",
            help="Heatmap stage timeout in seconds (0 for unlimited)",
        ),
    ] = 0.0,
    prediction_timeout: Annotated[
        float,
        typer.Option(
            "--prediction-timeout",
            help="Prediction stage timeout in seconds (0 for unlimited)",
        ),
    ] = 0.0,
    model_selection: Annotated[
        Optional[List[str]],
        typer.Option(
            "--model_selection",
            help="List of models to try. Options: gp, rf, gb, kr, xgb, lgb, et, svr",
        ),
    ] = None,
    prediction_optim_dict: Annotated[
        str,
        typer.Option(
            "--prediction_optim_dict",
            help="Name of a prediction optim_dict in optim_configs_predict.py",
        ),
    ] = "optim_dict_predict",
    random_state: Annotated[
        int,
        typer.Option("--random_state", help="Master random seed for reproducibility. Note: Setting this will disable UMAP parallel processing (n_jobs=1) to ensure reproducible results. For faster UMAP training at the cost of reproducibility, consider using different seeds for different runs."),
    ] = 42,
    umap_jobs: Annotated[
        Optional[int],
        typer.Option(
            "--umap_jobs", help="Number of parallel jobs for outer (UMAP) optimization"
        ),
    ] = None,
    hdbscan_jobs: Annotated[
        Optional[int],
        typer.Option(
            "--hdbscan_jobs",
            help="Number of parallel jobs for inner (HDBSCAN) optimization",
        ),
    ] = None,
    interactive: Annotated[
        bool, typer.Option("--interactive", help="Run in interactive mode")
    ] = False,
    use_service: Annotated[
        bool, typer.Option("--service", help="Use remote service for execution")
    ] = False,
    service_url: Annotated[
        Optional[str],
        typer.Option(
            "--service-url",
            help="URL of the remote service (auto-detected in multi-user mode)",
        ),
    ] = None,
    token: Annotated[
        Optional[str],
        typer.Option("--token", help="Authentication token for multi-user mode"),
    ] = None,
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
        asyncio.run(
            _full_async(
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
                umap_jobs=umap_jobs,
                hdbscan_jobs=hdbscan_jobs,
                interactive=interactive,
                use_service=use_service,
                service_url=service_url,
                token=token,
            )
        )
    except KeyboardInterrupt:
        typer.echo("\n🛑 Operation cancelled by user", err=True)
        raise typer.Exit(code=130)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


async def _full_async(**kwargs) -> None:
    """
    Async implementation of the full pipeline command.

    Executes based on deployment mode detection and handles authentication if required.
    """
    # Import deployment configuration
    from emuses.multi_user_service.deployment_config import (
        get_deployment_config, get_service_discovery_url,
        validate_deployment_config)
    # Configure parallelism context for CLI environment
    from emuses.tools.parallelism_utils import configure_parallelism_backend

    # CLI runs in main process context - use default (loky) backend
    configure_parallelism_backend(force_backend=None)

    # Initialize components
    status_renderer = StatusRenderer()
    progress_tracker = ProgressTracker()

    # Get deployment configuration
    deployment_config = get_deployment_config()
    config_validation = validate_deployment_config(deployment_config)

    if not config_validation["valid"]:
        print(
            status_renderer.render_status(
                "error", "Deployment configuration validation failed:"
            )
        )
        for error in config_validation["errors"]:
            print(status_renderer.render_status("error", f"  - {error}"))
        raise typer.Exit(code=1)

    print(
        status_renderer.render_status(
            "info", f"Running in {deployment_config.mode.value} mode"
        )
    )

    # Handle interactive mode
    interactive = kwargs.pop("interactive", False)
    kwargs.pop("use_service", False)  # Remove unused parameter
    service_url = kwargs.pop("service_url", None)
    token = kwargs.pop("token", None)

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

    # Determine service URL based on deployment mode and parameters
    if service_url is None:
        service_url = get_service_discovery_url() or "http://localhost:8000"

    # Handle authentication for multi-user modes
    if deployment_config.requires_auth and token:
        print(
            status_renderer.render_status("info", "Using provided authentication token")
        )
        # Token will be handled by the service client

    # Execution logic based on deployment mode
    try:
        if deployment_config.mode.value == "local":
            # Local mode - auto-start local service
            await _execute_via_unified_service(
                pipeline_config, status_renderer, progress_tracker
            )
        else:
            # Multi-user or production mode - use remote service
            service_timeout = kwargs.get("service_timeout", 0.0)
            await _execute_via_remote_service(
                "full",
                pipeline_config,
                status_renderer,
                progress_tracker,
                service_url=service_url,
                service_timeout=service_timeout,
                auth_token=token,
            )

        print(
            status_renderer.render_status("success", "Pipeline completed successfully!")
        )
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
        elif hasattr(value, "value"):  # Enum types - check before str types since str enums are also str
            config[key] = value.value
        elif isinstance(value, (str, int, float, bool)):
            config[key] = value
        else:
            config[key] = str(value)

    return config


async def _execute_via_remote_service(
    pipeline_type: str,
    config: dict,
    status_renderer,
    progress_tracker,
    service_url: str = "http://localhost:8000",
    service_timeout: float = 0.0,
    auth_token: Optional[str] = None,
) -> None:
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
    service_client = ServiceHTTPClient(
        base_url=service_url, timeout=timeout, auth_token=auth_token
    )
    shutdown_handler = None

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
            "description": f"Pipeline execution via CLI for {pipeline_type}",
        }

        job_response = await service_client.submit_pipeline_job(
            pipeline_type, job_request
        )
        job_id = job_response["job_id"]
        print(status_renderer.render_status("info", f"Job submitted with ID: {job_id}"))

        # Initialize shutdown handler for graceful interruption
        from emuses.cli.shutdown_handler import SimpleShutdownHandler

        shutdown_handler = SimpleShutdownHandler(service_client, job_id)

        # Poll for completion with progress display and interrupt handling
        print("Starting pipeline execution...")
        await _poll_job_completion(service_client, job_id, shutdown_handler)

        print("✓ Execution completed")

    except KeyboardInterrupt:
        if shutdown_handler:
            should_stop = await shutdown_handler.handle_interruption()
            if should_stop:
                await shutdown_handler.cleanup_and_stop()
                print("✅ Shutdown completed gracefully")
                raise typer.Exit(code=130)
            else:
                print("▶️  Resuming execution...")
                # Continue polling - resume the job completion wait
                await _poll_job_completion(service_client, job_id, shutdown_handler)
        else:
            # Fallback to existing behavior if shutdown_handler not ready
            print("\nOperation cancelled by user")
            raise typer.Exit(code=130)

    finally:
        if hasattr(service_client, "_session") and service_client._session:
            await service_client._session.aclose()


async def _poll_job_completion(service_client, job_id: str, shutdown_handler) -> None:
    """
    Poll for job completion with graceful interrupt handling.

    This function can be resumed after a user chooses to continue
    following a Ctrl+C interruption.

    Parameters
    ----------
    service_client : ServiceHTTPClient
        Client for service communication
    job_id : str
        ID of job to monitor
    shutdown_handler : SimpleShutdownHandler
        Handler for graceful interruptions
    """
    start_time = time.time()
    last_progress = -1
    poll_count = 0

    while True:
        try:
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
                if (
                    abs(progress_pct - last_progress) >= 5 or poll_count % 15 == 0
                ):  # Show every 5% or every 30 seconds
                    print(f"Progress: {progress_pct:.1f}%")
                    last_progress = progress_pct

            current_stage = status.get("current_stage")
            if current_stage:
                print(f"Current stage: {current_stage}")

            # Check for timeout (30 minutes max)
            if time.time() - start_time > 1800:
                raise ServiceClientError(
                    "Pipeline execution timed out after 30 minutes"
                )

            await asyncio.sleep(2)  # Poll every 2 seconds

        except KeyboardInterrupt:
            # Handle nested interrupts during polling
            if shutdown_handler:
                should_stop = await shutdown_handler.handle_interruption()
                if should_stop:
                    await shutdown_handler.cleanup_and_stop()
                    print("✅ Shutdown completed gracefully")
                    raise typer.Exit(code=130)
                else:
                    print("▶️  Resuming execution...")
                    # Continue the polling loop
                    continue
            else:
                # Fallback behavior
                print("\nOperation cancelled by user")
                raise typer.Exit(code=130)


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


async def _execute_via_unified_service(
    config: dict, status_renderer, progress_tracker
) -> None:
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
        print(
            status_renderer.render_status(
                "info", "Auto-starting local EMUSES service..."
            )
        )

        # Find available port for service
        from emuses.cli.service_manager import ServiceManager

        service_manager = ServiceManager()
        available_port = service_manager.find_available_port()
        service_url = f"http://localhost:{available_port}"

        print(
            status_renderer.render_status(
                "info", f"Starting FastAPI service on port {available_port}..."
            )
        )

        # Start local service
        service_process = _start_local_service(port=available_port)
        if not service_process:
            raise ServiceClientError("Failed to start local service")

        # Wait for service to be ready
        print(
            status_renderer.render_status("info", "Waiting for service to be ready...")
        )
        if not _wait_for_service_ready(service_url, timeout=30):
            raise ServiceClientError("Service failed to become ready within timeout")

        print(
            status_renderer.render_status(
                "success", "Local service started successfully!"
            )
        )

        # Execute via the service (determine pipeline type from config)
        pipeline_type = config.get("command", "full")
        await _execute_via_remote_service(
            pipeline_type, config, status_renderer, progress_tracker, service_url
        )

    finally:
        # Always clean up the service
        if service_process:
            print(
                status_renderer.render_status("info", "Shutting down local service...")
            )
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
            """Run the FastAPI service with graceful shutdown support."""
            import signal
            import sys
            
            def signal_handler(signum, frame):
                """Handle termination signals gracefully."""
                logger.info(f"Service received signal {signum}, shutting down gracefully...")
                sys.exit(0)
            
            # Register signal handlers for graceful shutdown
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
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

        # Start service in background process (non-daemon to receive signals)
        service_process = Process(target=run_service, daemon=False)
        service_process.start()
        
        # Register emergency cleanup handler as safety net
        # This ensures cleanup even if finally block doesn't run (rare edge cases)
        import atexit
        
        def emergency_cleanup():
            """Emergency cleanup if normal shutdown fails."""
            if service_process and service_process.is_alive():
                logger.warning("Emergency cleanup: Force-killing orphaned service process")
                try:
                    service_process.kill()
                    service_process.join(timeout=2)
                except Exception as e:
                    logger.error(f"Emergency cleanup failed: {e}")
        
        atexit.register(emergency_cleanup)

        # Give the process more time to start up
        time.sleep(2)

        if service_process.is_alive():
            logger.info(
                f"Service process started successfully (PID: {service_process.pid})"
            )
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
    Stop local FastAPI service process with graceful shutdown.
    
    Attempts graceful termination first (SIGTERM), then force-kills if needed.
    With daemon=False, the service can now receive and respond to SIGTERM.

    Parameters
    ----------
    service_process : Process
        Service process to stop
    """
    try:
        if service_process and service_process.is_alive():
            logger.info(f"Stopping service process (PID: {service_process.pid})...")
            
            # Try graceful shutdown first (service now receives SIGTERM)
            service_process.terminate()
            service_process.join(timeout=5)

            if service_process.is_alive():
                logger.warning("Service didn't stop gracefully, forcing kill...")
                service_process.kill()  # Force kill if needed
                service_process.join(timeout=2)
                
            if service_process.is_alive():
                logger.error("Failed to kill service process - may require manual cleanup")
            else:
                logger.info("Service process stopped successfully")

    except Exception as e:
        logger.error(f"Error stopping service: {e}")
        # Don't re-raise - this is cleanup code


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
        await _execute_via_remote_service(
            "umap", pipeline_config, status_renderer, progress_tracker
        )
        print(
            status_renderer.render_status(
                "success", "UMAP training completed successfully via service!"
            )
        )
    except ServiceClientError as e:
        print(
            status_renderer.render_status(
                "warning",
                f"Service unavailable ({e}), falling back to local execution...",
            )
        )
        await _execute_via_unified_service(
            pipeline_config, status_renderer, progress_tracker
        )
        print(
            status_renderer.render_status(
                "success", "UMAP training completed successfully via local execution!"
            )
        )


async def _heatmap_async(**kwargs) -> None:
    """Async implementation of the heatmap generation command."""
    status_renderer = StatusRenderer()
    progress_tracker = ProgressTracker()

    print(status_renderer.render_status("info", "Starting heatmap generation..."))

    pipeline_config = _convert_typer_args_to_service_config(**kwargs)

    try:
        await _execute_via_remote_service(
            "heatmap", pipeline_config, status_renderer, progress_tracker
        )
        print(
            status_renderer.render_status(
                "success", "Heatmap generation completed successfully via service!"
            )
        )
    except ServiceClientError as e:
        print(
            status_renderer.render_status(
                "warning",
                f"Service unavailable ({e}), falling back to local execution...",
            )
        )
        await _execute_via_unified_service(
            pipeline_config, status_renderer, progress_tracker
        )
        print(
            status_renderer.render_status(
                "success",
                "Heatmap generation completed successfully via local execution!",
            )
        )


async def _inference_async(**kwargs) -> None:
    """Async implementation of the inference command."""
    status_renderer = StatusRenderer()
    # progress_tracker = ProgressTracker()  # Currently unused

    # Execute inference locally using InferenceStage (handles its own status messages)
    try:
        await _execute_inference_locally(kwargs, status_renderer)
        print(
            status_renderer.render_status(
                "success", "Inference completed successfully!"
            )
        )
    except Exception as e:
        print(status_renderer.render_status("error", f"Inference failed: {e}"))
        raise


async def _execute_inference_locally(config: dict, status_renderer) -> None:
    """
    Execute inference locally using EMUSESPipeline with InferenceStage.

    Parameters
    ----------
    config : dict
        Inference configuration
    status_renderer : StatusRenderer
        Status display component
    """
    try:
        from emuses.pipelines.inference_stage import InferenceStage
        from emuses.pipelines.emuses_pipeline import EMUSESPipeline

        # InferenceStage will handle pipeline status messages
        # Removed redundant "Initializing inference pipeline..." message

        # Create args object for EMUSESPipeline (consolidated approach)
        args = type('Args', (), {})()
        args.input_dataset = str(config["data"])  # Still needed for PipelineConfig
        args.output_folder = str(config["output"])
        args.random_state = 42
        args.load_embeddings = None
        args.bids_filters = None

        # Critical preprocessing parameters for data processing
        args.input_header = config.get("input_header")
        args.input_index_column = config.get("input_index_column")
        args.scores_header = config.get("scores_header")
        args.scores_index_column = config.get("scores_index_column")
        args.scores = str(config["scores"]) if config.get("scores") else None

        # Additional preprocessing parameters
        args.columns_are_features = config.get("columns_are_features", False)
        args.input_normalization = config.get("input_normalization", "none")
        args.inputs_columns = config.get("inputs_columns")
        args.classification = config.get("classification", False)
        
        # Advanced processing parameters
        args.scores_normalization = config.get("scores_normalization", "none")
        args.scores_are_rows = config.get("scores_are_rows", False)
        args.scores_column = config.get("scores_column")
        args.filter_labelled_by_scores = config.get("filter_labelled_by_scores", False)
        args.recursive_search = config.get("recursive_search", False)
        args.input_file_types = config.get("input_file_types")
        args.arg_separator = config.get("arg_separator", ",")
        args.bids_filters = config.get("bids_filters")

        # Set inference mode to skip training-specific operations
        args.inference_mode = True
        
        # Set model path for scaler loading in inference mode
        if config.get("model"):
            args.model_path = str(config["model"])

        # Create EMUSESPipeline - format_args will handle inference mode properly
        pipeline = EMUSESPipeline(args)
        
        # Use pipeline context directly - no duplicate processing
        context = pipeline.context.copy()  # Copy to avoid modifying pipeline context
        context.update({
            "verify_integrity": config.get("verify", True),
            "output_format": config.get("output_format", "csv"),
            "model_path": str(config["model"]) if config.get("model") else None,
            "cli_inference_mode": True
        })

        # Create inference stage with proper configuration
        inference_stage = InferenceStage(pipeline.config)
        inference_stage.model_path = str(config["model"])
        inference_stage.output_path = str(config["output"])
        inference_stage.validate_mode = config.get("validate", False)

        # Run inference stage with processed data in context (standard pattern)
        results = inference_stage.run(context)

        # InferenceStage already provides comprehensive output including sample count and mode
        mode = results.get("mode", "inference")

        # Show validation results if available
        if mode == "validation" and "validation_metrics" in results:
            metrics = results["validation_metrics"]
            print(status_renderer.render_status("info", "Validation metrics:"))
            for metric, value in metrics.items():
                print(status_renderer.render_status("info", f"  {metric}: {value:.4f}"))

    except ImportError as e:
        raise ServiceClientError(f"Inference stage not available: {e}")
    except Exception as e:
        raise ServiceClientError(f"Local inference execution failed: {e}")


async def _execute_stage_locally(
    stage: str, config: dict, status_renderer, progress_tracker
) -> None:
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
            "prediction": "PredictionStage",
        }

        if stage not in stage_classes:
            raise ServiceClientError(f"Unknown stage: {stage}")

        # For individual stages, fall back to full pipeline execution
        # This ensures all the context and dependencies are properly set up
        stage_config = config.copy()
        stage_config["command"] = stage
        await _execute_via_unified_service(
            stage_config, status_renderer, progress_tracker
        )

        print("✓ Stage completed")
        print("✓ Execution completed")

    except ImportError as e:
        raise ServiceClientError(f"Local {stage} stage not available: {e}")
    except Exception as e:
        raise ServiceClientError(f"Local {stage} execution failed: {e}")


@app.command(help="Train the UMAP and get the embeddings")
def umap(
    output_folder: Annotated[Path, typer.Argument(help="Output folder")],
    input_dataset: Annotated[
        Path, typer.Argument(help="Input dataset of images (jpg), NIfTI, or MNIST")
    ],
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
        asyncio.run(
            _umap_async(
                output_folder=output_folder,
                input_dataset=input_dataset,
            )
        )
    except KeyboardInterrupt:
        typer.echo("\n🛑 Operation cancelled by user", err=True)
        raise typer.Exit(code=130)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(help="Create a heatmap")
def heatmap(
    output_folder: Annotated[Path, typer.Argument(help="Output folder")],
    input_dataset: Annotated[
        Path, typer.Argument(help="Input dataset of images (jpg), NIfTI, or MNIST")
    ],
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
        asyncio.run(
            _heatmap_async(
                output_folder=output_folder,
                input_dataset=input_dataset,
            )
        )
    except KeyboardInterrupt:
        typer.echo("\n🛑 Operation cancelled by user", err=True)
        raise typer.Exit(code=130)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(help="Run inference on trained model")
def inference(
    output: Annotated[Path, typer.Argument(help="Output path for results (REQUIRED for data privacy)")],
    data: Annotated[Path, typer.Argument(help="Path to input data for inference")],
    model: Annotated[
        Optional[Path],
        typer.Option("--model", help="Path to trained model directory")
    ] = None,
    model_id: Annotated[
        Optional[str],
        typer.Option("--model-id", help="Registry model ID for trained model")
    ] = None,
    validate: Annotated[
        bool,
        typer.Option("--validate", help="Force validation mode (requires ground truth)")
    ] = False,
    verify: Annotated[
        bool,
        typer.Option("--verify/--no-verify", help="Verify model integrity before inference")
    ] = True,
    output_format: Annotated[
        str,
        typer.Option("--format", help="Output format (csv or npy)")
    ] = "csv",
    # Phase 1: Critical preprocessing parameters
    input_header: Annotated[
        Optional[int],
        typer.Option("--input_header", help="Header row for input dataset (0-based)")
    ] = None,
    input_index_column: Annotated[
        Optional[int],
        typer.Option("--input_index_column", help="Index column for input dataset (0-based)")
    ] = None,
    scores_header: Annotated[
        Optional[int],
        typer.Option("--scores_header", help="Header row for scores file (0-based)")
    ] = None,
    scores_index_column: Annotated[
        Optional[int],
        typer.Option("--scores_index_column", help="Index column for scores file (0-based)")
    ] = None,
    scores: Annotated[
        Optional[Path],
        typer.Option("--scores", help="Path to scores file for validation mode")
    ] = None,
    # Additional critical preprocessing parameters
    columns_are_features: Annotated[
        bool,
        typer.Option("--columns_are_features", help="Columns represent features (not samples)")
    ] = False,
    input_normalization: Annotated[
        InputNormalization,
        typer.Option("--input_normalization", help="Input normalization method")
    ] = InputNormalization.none,
    inputs_columns: Annotated[
        Optional[List[str]],
        typer.Option("--inputs_columns", help="List of columns for inputs in the dataset")
    ] = None,
    classification: Annotated[
        bool,
        typer.Option("--classification", help="Use classification mode instead of regression")
    ] = False,
    # Phase 3: Advanced scores processing parameters
    scores_normalization: Annotated[
        ScoresNormalization,
        typer.Option("--scores_normalization", help="Normalization method for scores data")
    ] = ScoresNormalization.none,
    scores_are_rows: Annotated[
        bool,
        typer.Option("--scores_are_rows", help="Whether scores data has observations in rows")
    ] = False,
    scores_column: Annotated[
        Optional[List[str]],
        typer.Option("--scores_column", help="List of columns for scores in the dataset")
    ] = None,
    filter_labelled_by_scores: Annotated[
        bool,
        typer.Option("--filter_labelled_by_scores", help="Filter data to include only labelled observations")
    ] = False,
    # Phase 3: Advanced input processing parameters
    recursive_search: Annotated[
        bool,
        typer.Option("--recursive-input-file-search", help="Search recursively in the input dataset folder")
    ] = False,
    input_file_types: Annotated[
        Optional[List[str]],
        typer.Option("--input_file_types", help="File types to search for in the input dataset folder")
    ] = None,
    arg_separator: Annotated[
        str,
        typer.Option("--arg_separator", help="Separator for the input dataset list")
    ] = ",",
    bids_filters: Annotated[
        Optional[List[str]],
        typer.Option("--bids_filters", help="BIDS filters for the input dataset")
    ] = None,
) -> None:
    """
    Run inference on trained EMUSES model.

    This command loads a trained model and runs inference on new data,
    automatically detecting validation vs pure inference modes.

    Model specification (exactly one required):
    - Use --model for direct path to model directory
    - Use --model-id for registry-based model lookup

    Parameters
    ----------
    data : Path
        Path to input data for inference
    output : Path
        Output path for results (REQUIRED for data privacy protection)
    model : Optional[Path]
        Path to trained model directory (use with --model)
    model_id : Optional[str]
        Registry model ID for trained model (use with --model-id)
    validate : bool
        Force validation mode (requires ground truth)
    verify : bool
        Verify model integrity before inference
    output_format : str
        Output format (csv or npy)
    input_header : Optional[int]
        Header row for input dataset (0-based), use when CSV has header row
    input_index_column : Optional[int]
        Index column for input dataset (0-based), use when CSV has row labels/IDs
    scores_header : Optional[int]
        Header row for scores file (0-based), use when scores CSV has header row
    scores_index_column : Optional[int]
        Index column for scores file (0-based), use when scores CSV has row labels/IDs
    scores : Optional[Path]
        Path to scores file for validation mode, enables ground truth comparison
    columns_are_features : bool
        Whether columns represent features (not samples), affects data interpretation
    input_normalization : InputNormalization
        Input normalization method (none, zscore, robust, min-max, zero-max)
    inputs_columns : Optional[List[str]]
        List of specific columns to use for inputs in the dataset
    classification : bool
        Use classification mode instead of regression for model predictions
    scores_normalization : ScoresNormalization
        Normalization method for scores data (none, zscore, min-max, zero-max, robust)
    scores_are_rows : bool
        Whether scores data has observations in rows (not columns)
    scores_column : Optional[List[str]]
        List of specific columns to use for scores in the dataset
    filter_labelled_by_scores : bool
        Filter data to include only labelled observations from scores
    recursive_search : bool
        Search recursively in the input dataset folder for files
    input_file_types : Optional[List[str]]
        File types to search for in the input dataset folder
    arg_separator : str
        Separator for the input dataset list parsing
    bids_filters : Optional[List[str]]
        BIDS filters for the input dataset processing

    Returns
    -------
    None
    """
    # Validate model specification: exactly one of --model or --model-id required
    if model and model_id:
        typer.echo("❌ Cannot specify both --model and --model-id. Use exactly one.", err=True)
        raise typer.Exit(code=1)
    elif model_id:
        # Registry-based model lookup
        try:
            from emuses.tools.local_model_registry import LocalModelRegistry
            registry = LocalModelRegistry()
            model = registry.get_model_path(model_id)
            typer.echo(f"🔍 Registry lookup: {model_id} -> {model}")
        except Exception as e:
            typer.echo(f"❌ Registry lookup failed for model ID '{model_id}': {e}", err=True)
            raise typer.Exit(code=1)
    elif not model:
        typer.echo("❌ Model specification required. Use --model <path> or --model-id <id>", err=True)
        raise typer.Exit(code=1)

    # Validate resolved model path exists
    if not model.exists():
        typer.echo(f"❌ Model directory not found: {model}", err=True)
        raise typer.Exit(code=1)

    # Validate input data
    if not data.exists():
        typer.echo(f"❌ Input data not found: {data}", err=True)
        raise typer.Exit(code=1)

    if output_format not in ["csv", "npy"]:
        typer.echo(f"❌ Unsupported output format: {output_format}. Use 'csv' or 'npy'", err=True)
        raise typer.Exit(code=1)

    # Output path is now required - no default to prevent data privacy issues

    # Save command for easy rerun (use output directory for command saving)
    save_command_to_output_folder(output)

    # Run the async implementation
    try:
        asyncio.run(
            _inference_async(
                model=model,
                data=data,
                output=output,
                validate=validate,
                verify=verify,
                output_format=output_format,
                # Phase 1: Critical preprocessing parameters
                input_header=input_header,
                input_index_column=input_index_column,
                scores_header=scores_header,
                scores_index_column=scores_index_column,
                scores=scores,
                # Additional critical preprocessing parameters
                columns_are_features=columns_are_features,
                input_normalization=input_normalization,
                inputs_columns=inputs_columns,
                classification=classification,
                # Phase 3: Advanced scores processing parameters
                scores_normalization=scores_normalization,
                scores_are_rows=scores_are_rows,
                scores_column=scores_column,
                filter_labelled_by_scores=filter_labelled_by_scores,
                # Phase 3: Advanced input processing parameters
                recursive_search=recursive_search,
                input_file_types=input_file_types,
                arg_separator=arg_separator,
                bids_filters=bids_filters,
            )
        )
    except KeyboardInterrupt:
        typer.echo("\n🛑 Operation cancelled by user", err=True)
        raise typer.Exit(code=130)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


# Research Utility Commands for Scientific Workflows

@app.command(help="Verify model integrity using manifest")
def verify(
    model: Annotated[str, typer.Argument(help="Path to model directory or model name")],
    detailed: Annotated[bool, typer.Option("--detailed", help="Show detailed verification results")] = False,
    strict: Annotated[bool, typer.Option("--strict", help="Perform strict cryptographic verification")] = False,
) -> None:
    """
    Verify model integrity using manifest-based SHA-256 checking.

    Parameters
    ----------
    model : str
        Path to model directory or model name
    detailed : bool
        Show detailed verification results
    strict : bool
        Perform strict cryptographic verification
    """
    try:
        from ..tools.model_io import ModelIOManager
        from pathlib import Path

        model_path = Path(model)

        if model_path.is_dir():
            # Directory path provided
            manager = ModelIOManager(model_path)
            model_name = "*"  # Will use pattern matching
        else:
            # Model name provided, assume current directory
            manager = ModelIOManager(Path.cwd())
            model_name = model

        is_valid = manager.verify_model_integrity(model_name)

        if is_valid:
            typer.echo(f"✅ Model integrity verified: {model}")
            if detailed:
                manifest_info = manager.get_manifest_info(model_name)
                if manifest_info:
                    model_info = manifest_info.get("model_info", {})
                    typer.echo(f"   Model: {model_info.get('name', 'Unknown')} v{model_info.get('version', 'Unknown')}")
                    typer.echo(f"   Created: {model_info.get('created_at', 'Unknown')}")
                    typer.echo(f"   EMUSES: {model_info.get('emuses_version', 'Unknown')}")
        else:
            typer.echo(f"❌ Model integrity verification failed: {model}", err=True)
            raise typer.Exit(code=1)

    except Exception as e:
        typer.echo(f"Error verifying model: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(help="Get model information and metadata")
def info(
    model: Annotated[str, typer.Argument(help="Path to model directory or model name")],
    format: Annotated[str, typer.Option("--format", help="Output format (text, json)")] = "text",
) -> None:
    """
    Display model metadata and information.

    Parameters
    ----------
    model : str
        Path to model directory or model name
    format : str
        Output format (text or json)
    """
    try:
        from ..tools.model_io import ModelIOManager
        from pathlib import Path
        import json

        model_path = Path(model)

        if model_path.is_dir():
            manager = ModelIOManager(model_path)
            model_name = "*"
        else:
            manager = ModelIOManager(Path.cwd())
            model_name = model

        manifest_info = manager.get_manifest_info(model_name)

        if not manifest_info:
            typer.echo(f"❌ No manifest found for model: {model}", err=True)
            raise typer.Exit(code=1)

        if format == "json":
            typer.echo(json.dumps(manifest_info, indent=2))
        else:
            # Text format
            model_info = manifest_info.get("model_info", {})
            compatibility = manifest_info.get("compatibility", {})

            typer.echo("📊 Model Information")
            typer.echo(f"   Name: {model_info.get('name', 'Unknown')}")
            typer.echo(f"   Version: {model_info.get('version', 'Unknown')}")
            typer.echo(f"   Created: {model_info.get('created_at', 'Unknown')}")
            typer.echo(f"   Description: {model_info.get('description', 'No description')}")
            typer.echo(f"   EMUSES Version: {model_info.get('emuses_version', 'Unknown')}")
            typer.echo(f"   Minimum EMUSES: {compatibility.get('min_emuses_version', 'Unknown')}")
            typer.echo(f"   Python Version: {compatibility.get('python_version', 'Unknown')}")

            file_integrity = manifest_info.get("file_integrity", {})
            if file_integrity:
                typer.echo(f"   Files: {len(file_integrity)} tracked files")

    except Exception as e:
        typer.echo(f"Error getting model info: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(help="Generate publication citation for model")
def cite(
    model: Annotated[str, typer.Argument(help="Path to model directory or model name")],
    format: Annotated[str, typer.Option("--format", help="Citation format (bibtex, apa, nature)")] = "bibtex",
) -> None:
    """
    Generate publication-ready citation for a model.

    Parameters
    ----------
    model : str
        Path to model directory or model name
    format : str
        Citation format (bibtex, apa, nature)
    """
    try:
        from ..tools.model_io import ModelIOManager
        from pathlib import Path
        from datetime import datetime

        model_path = Path(model)

        if model_path.is_dir():
            manager = ModelIOManager(model_path)
            model_name = "*"
        else:
            manager = ModelIOManager(Path.cwd())
            model_name = model

        manifest_info = manager.get_manifest_info(model_name)

        if not manifest_info:
            typer.echo(f"❌ No manifest found for model: {model}", err=True)
            raise typer.Exit(code=1)

        model_info = manifest_info.get("model_info", {})
        model_name = model_info.get("name", "unknown_model")
        version = model_info.get("version", "1.0.0")
        created_at = model_info.get("created_at", "")
        description = model_info.get("description", "EMUSES neuroimaging model")

        # Parse creation date
        try:
            created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            year = created_date.year
            date_str = created_date.strftime("%Y-%m-%d")
        except Exception:
            year = datetime.now().year
            date_str = datetime.now().strftime("%Y-%m-%d")

        if format == "bibtex":
            citation = f"""@misc{{{model_name}_{version.replace('.', '_')},
    title={{{model_name.replace('_', ' ').title()} v{version}: {description}}},
    author={{EMUSES Pipeline}},
    year={{{year}}},
    note={{Neuroimaging model generated using EMUSES framework, created {date_str}}},
    howpublished={{\\url{{https://github.com/your-org/emuses}}}}
}}"""
        elif format == "apa":
            citation = f"EMUSES Pipeline. ({year}). {model_name.replace('_', ' ').title()} v{version}: {description}. Retrieved from https://github.com/your-org/emuses"
        elif format == "nature":
            citation = f"EMUSES Pipeline. {model_name.replace('_', ' ').title()} v{version}: {description} (2024). https://github.com/your-org/emuses"
        else:
            typer.echo(f"❌ Unsupported citation format: {format}", err=True)
            raise typer.Exit(code=1)

        typer.echo(citation)

    except Exception as e:
        typer.echo(f"Error generating citation: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(help="Export complete model provenance")
def trace(
    model: Annotated[str, typer.Argument(help="Path to model directory or model name")],
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file path")] = None,
) -> None:
    """
    Export complete model provenance for supplementary materials.

    Parameters
    ----------
    model : str
        Path to model directory or model name
    output : Optional[str]
        Output file path (default: model_trace.json)
    """
    try:
        from ..tools.model_io import ModelIOManager
        from pathlib import Path
        import json

        model_path = Path(model)

        if model_path.is_dir():
            manager = ModelIOManager(model_path)
            model_name = "*"
        else:
            manager = ModelIOManager(Path.cwd())
            model_name = model

        manifest_info = manager.get_manifest_info(model_name)

        if not manifest_info:
            typer.echo(f"❌ No manifest found for model: {model}", err=True)
            raise typer.Exit(code=1)

        # Create enhanced provenance report
        from datetime import datetime
        provenance = {
            "model_provenance": manifest_info,
            "generation_info": {
                "exported_at": datetime.now().isoformat(),
                "emuses_version": manifest_info.get("model_info", {}).get("emuses_version", "unknown"),
                "export_version": "1.0.0"
            },
            "reproducibility": {
                "config_hash": manifest_info.get("training_context", {}).get("config_hash"),
                "random_seeds": manifest_info.get("training_context", {}).get("random_seeds", {}),
                "environment": {
                    "python_version": manifest_info.get("compatibility", {}).get("python_version"),
                    "required_packages": manifest_info.get("compatibility", {}).get("required_packages", [])
                }
            }
        }

        # Determine output path
        if output:
            output_path = Path(output)
        else:
            model_name_clean = manifest_info.get("model_info", {}).get("name", "model")
            output_path = Path(f"{model_name_clean}_trace.json")

        # Write provenance report
        with open(output_path, 'w') as f:
            json.dump(provenance, f, indent=2, sort_keys=True)

        typer.echo(f"✅ Model provenance exported to: {output_path}")

    except Exception as e:
        typer.echo(f"Error exporting provenance: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def reproduce(
    model: Annotated[str, typer.Argument(help="Path to model directory or model name")],
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file path for reproduction guide")] = None,
) -> None:
    """
    Generate reproduction guide for a model.

    This command creates a comprehensive markdown guide that enables exact
    reproduction of the model training process, including environment setup,
    configuration details, and step-by-step instructions.

    Parameters
    ----------
    model : str
        Path to model directory or model name to generate reproduction guide for
    output : str, optional
        Output file path for the reproduction guide (default: model_dir/reproduction_guide.md)

    Returns
    -------
    None
    """
    try:
        # Determine if model is a path or name
        model_path = Path(model)
        if not model_path.exists():
            typer.echo(f"❌ Model path not found: {model}", err=True)
            raise typer.Exit(code=1)

        # Load manifest
        manifest_path = model_path / "model_manifest.json"
        if not manifest_path.exists():
            typer.echo(f"❌ No manifest found at: {manifest_path}", err=True)
            typer.echo("Model must have a manifest for reproduction guide generation")
            raise typer.Exit(code=1)

        import json
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        # Determine output path
        if output is None:
            output_path = model_path / "reproduction_guide.md"
        else:
            output_path = Path(output)

        # Generate reproduction guide
        guide_content = _generate_reproduction_guide(manifest, model_path)

        # Write guide to file
        with open(output_path, 'w') as f:
            f.write(guide_content)

        typer.echo(f"✅ Reproduction guide generated: {output_path}")

    except Exception as e:
        typer.echo(f"❌ Error generating reproduction guide: {e}", err=True)
        raise typer.Exit(code=1)


def _generate_reproduction_guide(manifest: dict, model_path: Path) -> str:
    """
    Generate reproduction guide content from manifest.

    Parameters
    ----------
    manifest : dict
        Model manifest containing metadata and training context
    model_path : Path
        Path to model directory

    Returns
    -------
    str
        Markdown content for reproduction guide
    """
    model_info = manifest.get("model_info", {})
    training_context = manifest.get("training_context", {})
    compatibility = manifest.get("compatibility", {})

    guide_content = f"""# Model Reproduction Guide

## Model Information

- **Model Name**: {model_info.get('name', 'Unknown')}
- **Version**: v{model_info.get('version', '1.0.0')}
- **Created**: {model_info.get('created_at', 'Unknown')}
- **EMUSES Version**: {model_info.get('emuses_version', 'Unknown')}
- **Description**: {model_info.get('description', 'No description available')}

## Environment Setup

### Python Environment
- **Python Version**: {compatibility.get('python_version', '3.9+')}
- **Minimum EMUSES Version**: {compatibility.get('min_emuses_version', '2.0.0')}

### Required Packages
"""

    # Add required packages
    packages = compatibility.get('required_packages', [])
    for package in packages:
        guide_content += f"- {package}\n"

    guide_content += """
### Installation Commands
```bash
# Create virtual environment
python -m venv emuses_env
source emuses_env/bin/activate  # On Windows: emuses_env\\Scripts\\activate

# Install EMUSES and dependencies
pip install emuses>=""" + compatibility.get('min_emuses_version', '2.0.0') + '"'

    for package in packages:
        guide_content += f"\npip install {package}"

    guide_content += """
```

## Reproduction Steps

### Random Seeds
The following random seeds must be used for exact reproduction:
"""

    # Add random seeds
    seeds = training_context.get('random_seeds', {})
    for seed_name, seed_value in seeds.items():
        guide_content += f"- **{seed_name}**: {seed_value}\n"

    guide_content += f"""

### Configuration
- **Config Hash**: {training_context.get('config_hash', 'Not available')}

### Training Command
```bash
# Navigate to your data directory
cd /path/to/your/data

# Run EMUSES training with exact reproduction settings
emuses full \\
    --input your_input_file \\
    --scores your_scores_file \\
    --output_directory {model_path.name} \\
    --random_seed {seeds.get('master', 42)}
```

## Verification

After training, verify the model matches by:

1. Checking model integrity:
```bash
emuses verify --model {model_path.name}
```

2. Comparing model information:
```bash
emuses info --model {model_path.name}
```

## Notes

- Ensure exact same input data and preprocessing steps
- Use identical random seeds as specified above
- Environment should match the requirements exactly
- Any deviations may result in slightly different model parameters

---
*Generated by EMUSES reproduction utility*
"""

    return guide_content


@app.command()
def diff(
    model: Annotated[str, typer.Argument(help="Path to model directory or model name")],
    detailed: Annotated[bool, typer.Option("--detailed", help="Show detailed change information")] = False,
) -> None:
    """
    Check for modifications since model creation.

    This command compares current files with manifest checksums to detect
    any changes, additions, or deletions since the model was created.

    Parameters
    ----------
    model : str
        Path to model directory or model name to check for changes
    detailed : bool, optional
        Show detailed change information including file sizes and checksums

    Returns
    -------
    None
    """
    try:
        # Determine if model is a path or name
        model_path = Path(model)
        if not model_path.exists():
            typer.echo(f"❌ Model path not found: {model}", err=True)
            raise typer.Exit(code=1)

        # Load manifest
        manifest_path = model_path / "model_manifest.json"
        if not manifest_path.exists():
            typer.echo(f"❌ No manifest found at: {manifest_path}", err=True)
            typer.echo("Model must have a manifest for change detection")
            raise typer.Exit(code=1)

        import json
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        # Get file integrity information from manifest
        file_integrity = manifest.get("file_integrity", {})

        # Analyze changes
        changes = _analyze_file_changes(model_path, file_integrity)

        # Display results
        if not changes["modified"] and not changes["added"] and not changes["deleted"]:
            typer.echo("✅ No changes detected - model files match manifest")
        else:
            typer.echo("📝 Changes detected:")

            # Show modified files
            for file_path, change_info in changes["modified"]:
                if detailed:
                    typer.echo(f"   MODIFIED: {file_path}")
                    typer.echo(f"     - Expected size: {change_info['expected_size']}, Current size: {change_info['current_size']}")
                    typer.echo(f"     - Expected SHA256: {change_info['expected_sha256'][:16]}...")
                    typer.echo(f"     - Current SHA256:  {change_info['current_sha256'][:16]}...")
                else:
                    typer.echo(f"   MODIFIED: {file_path}")

            # Show added files
            for file_path in changes["added"]:
                typer.echo(f"   ADDED: {file_path}")

            # Show deleted files
            for file_path in changes["deleted"]:
                typer.echo(f"   DELETED: {file_path}")

    except Exception as e:
        typer.echo(f"❌ Error analyzing changes: {e}", err=True)
        raise typer.Exit(code=1)


def _analyze_file_changes(model_path: Path, file_integrity: dict) -> dict:
    """
    Analyze file changes compared to manifest.

    Parameters
    ----------
    model_path : Path
        Path to model directory
    file_integrity : dict
        File integrity information from manifest

    Returns
    -------
    dict
        Dictionary containing lists of modified, added, and deleted files
    """
    import hashlib

    changes = {
        "modified": [],
        "added": [],
        "deleted": []
    }

    # Get current files (excluding manifest itself)
    current_files = set()
    for file_path in model_path.iterdir():
        if file_path.is_file() and file_path.name != "model_manifest.json":
            current_files.add(file_path.name)

    # Get expected files from manifest
    expected_files = set(file_integrity.keys())

    # Check for deleted files
    for expected_file in expected_files:
        if expected_file not in current_files:
            changes["deleted"].append(expected_file)

    # Check for added files
    for current_file in current_files:
        if current_file not in expected_files:
            changes["added"].append(current_file)

    # Check for modified files
    for file_name in expected_files.intersection(current_files):
        file_path = model_path / file_name
        expected_info = file_integrity[file_name]

        # Calculate current file hash
        with open(file_path, 'rb') as f:
            current_content = f.read()
            current_sha256 = hashlib.sha256(current_content).hexdigest()
            current_size = len(current_content)

        # Compare with expected values
        expected_sha256 = expected_info.get("sha256", "")
        expected_size = expected_info.get("size", 0)

        if current_sha256 != expected_sha256 or current_size != expected_size:
            changes["modified"].append((file_name, {
                "expected_sha256": expected_sha256,
                "current_sha256": current_sha256,
                "expected_size": expected_size,
                "current_size": current_size
            }))

    return changes


@app.command()
def compare(
    model1: Annotated[str, typer.Argument(help="Path to first model directory")],
    model2: Annotated[str, typer.Argument(help="Path to second model directory")],
) -> None:
    """
    Compare two model versions.

    This command provides a side-by-side comparison of two model versions,
    including manifest differences, configuration changes, and dependency updates.

    Parameters
    ----------
    model1 : str
        Path to first model directory for comparison
    model2 : str
        Path to second model directory for comparison

    Returns
    -------
    None
    """
    try:
        # Validate model paths
        model1_path = Path(model1)
        model2_path = Path(model2)

        if not model1_path.exists():
            typer.echo(f"❌ Model 1 path not found: {model1}", err=True)
            raise typer.Exit(code=1)

        if not model2_path.exists():
            typer.echo(f"❌ Model 2 path not found: {model2}", err=True)
            raise typer.Exit(code=1)

        # Load manifests
        manifest1_path = model1_path / "model_manifest.json"
        manifest2_path = model2_path / "model_manifest.json"

        if not manifest1_path.exists():
            typer.echo(f"❌ No manifest found for model 1: {manifest1_path}", err=True)
            raise typer.Exit(code=1)

        if not manifest2_path.exists():
            typer.echo(f"❌ No manifest found for model 2: {manifest2_path}", err=True)
            raise typer.Exit(code=1)

        import json
        with open(manifest1_path, 'r') as f:
            manifest1 = json.load(f)

        with open(manifest2_path, 'r') as f:
            manifest2 = json.load(f)

        # Generate comparison report
        _display_model_comparison(manifest1, manifest2, model1_path.name, model2_path.name)

    except Exception as e:
        typer.echo(f"❌ Error comparing models: {e}", err=True)
        raise typer.Exit(code=1)


def _display_model_comparison(manifest1: dict, manifest2: dict, name1: str, name2: str) -> None:
    """
    Display side-by-side comparison of two models.

    Parameters
    ----------
    manifest1 : dict
        First model's manifest data
    manifest2 : dict
        Second model's manifest data
    name1 : str
        First model's display name
    name2 : str
        Second model's display name

    Returns
    -------
    None
    """
    typer.echo("🔍 Model Version Comparison")
    typer.echo("=" * 50)

    # Model information comparison
    info1 = manifest1.get("model_info", {})
    info2 = manifest2.get("model_info", {})

    typer.echo("\n📊 Model Information")
    typer.echo(f"   Model 1 ({name1}): {info1.get('name', 'Unknown')} v{info1.get('version', '1.0.0')}")
    typer.echo(f"   Model 2 ({name2}): {info2.get('name', 'Unknown')} v{info2.get('version', '1.0.0')}")

    typer.echo("\n   Created:")
    typer.echo(f"     Model 1: {info1.get('created_at', 'Unknown')}")
    typer.echo(f"     Model 2: {info2.get('created_at', 'Unknown')}")

    typer.echo("\n   Description:")
    typer.echo(f"     Model 1: {info1.get('description', 'No description')}")
    typer.echo(f"     Model 2: {info2.get('description', 'No description')}")

    # Configuration comparison
    training1 = manifest1.get("training_context", {})
    training2 = manifest2.get("training_context", {})

    typer.echo("\n⚙️ Configuration Changes")
    config1 = training1.get("config_hash", "Unknown")
    config2 = training2.get("config_hash", "Unknown")

    if config1 != config2:
        typer.echo(f"   Config Hash: {config1} → {config2}")
    else:
        typer.echo(f"   Config Hash: {config1} (unchanged)")

    # Random seeds comparison
    seeds1 = training1.get("random_seeds", {})
    seeds2 = training2.get("random_seeds", {})

    typer.echo("\n🎲 Random Seeds")
    all_seed_keys = set(seeds1.keys()) | set(seeds2.keys())

    for seed_key in sorted(all_seed_keys):
        val1 = seeds1.get(seed_key, "N/A")
        val2 = seeds2.get(seed_key, "N/A")

        if val1 != val2:
            typer.echo(f"   {seed_key}: {val1} → {val2}")
        else:
            typer.echo(f"   {seed_key}: {val1} (unchanged)")

    # Compatibility comparison
    compat1 = manifest1.get("compatibility", {})
    compat2 = manifest2.get("compatibility", {})

    typer.echo("\n📦 Dependency Changes")

    # Python version
    py1 = compat1.get("python_version", "Unknown")
    py2 = compat2.get("python_version", "Unknown")
    if py1 != py2:
        typer.echo(f"   Python Version: {py1} → {py2}")
    else:
        typer.echo(f"   Python Version: {py1} (unchanged)")

    # EMUSES version
    emuses1 = compat1.get("min_emuses_version", "Unknown")
    emuses2 = compat2.get("min_emuses_version", "Unknown")
    if emuses1 != emuses2:
        typer.echo(f"   Min EMUSES Version: {emuses1} → {emuses2}")
    else:
        typer.echo(f"   Min EMUSES Version: {emuses1} (unchanged)")

    # Required packages
    packages1 = set(compat1.get("required_packages", []))
    packages2 = set(compat2.get("required_packages", []))

    # Show package changes
    added_packages = packages2 - packages1
    removed_packages = packages1 - packages2

    # Check for version updates in existing packages
    common_package_names = set()
    for p1 in packages1:
        name1 = p1.split(">=")[0] if ">=" in p1 else p1.split("==")[0] if "==" in p1 else p1
        for p2 in packages2:
            name2 = p2.split(">=")[0] if ">=" in p2 else p2.split("==")[0] if "==" in p2 else p2
            if name1 == name2:
                if p1 != p2:
                    typer.echo(f"   Package Updated: {p1} → {p2}")
                common_package_names.add(name1)

    if added_packages:
        for package in sorted(added_packages):
            typer.echo(f"   Package Added: {package}")

    if removed_packages:
        for package in sorted(removed_packages):
            typer.echo(f"   Package Removed: {package}")

    # Summary
    typer.echo("\n📋 Summary")
    if (config1 == config2 and seeds1 == seeds2 and py1 == py2 and
            emuses1 == emuses2 and packages1 == packages2):
        typer.echo("   ✅ Models appear to have identical configurations")
    else:
        typer.echo("   📝 Models have different configurations")
        typer.echo("   ⚠️ Results may differ due to configuration changes")


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


# Add admin subcommand
try:
    from .admin_commands import admin_app

    app.add_typer(admin_app, name="admin")
except ImportError:
    # Admin commands not available (likely missing dependencies)
    pass

# Add workspace subcommand
try:
    from .workspace_commands import workspace_app

    app.add_typer(workspace_app, name="workspace")
except ImportError:
    # Workspace commands not available (likely missing dependencies)
    pass

# Add models subcommand
try:
    from .models_commands import models_app

    app.add_typer(models_app, name="models")
except ImportError:
    # Models commands not available (likely missing dependencies)
    pass

# Aliases for command functions (for testing)
full_command = full
umap_command = umap
heatmap_command = heatmap
inference_command = inference


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
