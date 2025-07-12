# EMUSES Scripts Main CLI Documentation

<reasoning>
The enhanced CLI Typer feature needs to replicate all functionality from emuses/scripts/main.py. Based on the feature variables and context, the key elements are:

1. Main CLI entry point with argparse structure that needs to be replicated in Typer
2. Five command subparsers: full, umap, clustering, heatmap, prediction
3. Extensive argument parsing functions that handle different parameter types
4. Path resolution logic for cross-platform file handling  
5. Integration with EMUSESPipeline orchestrator
6. Service integration requirements for FastAPI consistency

The documentation should focus on the public functions and classes that the new Typer CLI will need to understand or potentially reuse.
</reasoning>

## Level 1: Legacy CLI Overview

The `emuses/scripts/main.py` module implements the current argparse-based command-line interface for the EMUSES pipeline system. It provides a multi-command structure with extensive parameter validation, cross-platform path resolution, and direct integration with the EMUSESPipeline orchestrator. This CLI serves as the reference implementation that the new Typer-based CLI must replicate exactly for backward compatibility. The module handles five main commands (full, umap, clustering, heatmap, prediction) with over 40 different configuration parameters across different pipeline stages. The implementation includes custom path resolution for handling URLs and platform-specific path formats, comprehensive argument validation, and direct instantiation of pipeline stages.

## Level 2: Public API Reference

| Symbol | Purpose | Inputs | Outputs | Side-effects |
|--------|---------|--------|---------|--------------|
| `main()` | Primary CLI entry point with argument parsing | None (reads sys.argv) | None | Creates output folders, runs pipeline |
| `resolve_path()` | Cross-platform path resolution with URL support | path_str: str | Path object or original string | None |
| `check_for_existing_optuna_databases()` | Prevent Optuna study conflicts | output_folder: Path | None | Exits program if conflicts found |
| `add_output_folder_argument()` | Add output folder positional argument | parser: ArgumentParser | None | Modifies parser in-place |
| `add_input_dataset_argument()` | Add input dataset positional argument | parser: ArgumentParser | None | Modifies parser in-place |
| `add_label_dataset_argument()` | Add optional label dataset argument | parser: ArgumentParser | None | Modifies parser in-place |
| `add_input_dataset_optional_arguments()` | Add input dataset configuration arguments | parser: ArgumentParser | None | Modifies parser in-place |
| `add_scores_arguments()` | Add scores file and processing arguments | parser: ArgumentParser | None | Modifies parser in-place |
| `add_random_state_argument()` | Add reproducibility seed argument | parser: ArgumentParser | None | Modifies parser in-place |
| `add_umap_arguments()` | Add UMAP stage configuration arguments | parser: ArgumentParser | None | Modifies parser in-place |
| `add_clustering_arguments()` | Add clustering configuration arguments | parser: ArgumentParser | None | Modifies parser in-place |
| `add_smoothing_arguments()` | Add data smoothing configuration arguments | parser: ArgumentParser | None | Modifies parser in-place |
| `add_enhanced_pipeline_arguments()` | Add enhanced pipeline optimization arguments | parser: ArgumentParser | None | Modifies parser in-place |

<details>
<summary><strong>Path Resolution Implementation</strong></summary>

```python
def resolve_path(path_str):
    """
    Robust path resolver that handles paths with spaces and different formats.
    Tries multiple variations to find a valid path.

    Args:
        path_str: The path string to resolve

    Returns:
        Path: A resolved pathlib.Path object, or the original string if no valid path is found
    """
    # Special case for non-path identifiers
    if path_str and path_str.lower() in [
        "mnist",
        "digits_label_dataset", 
        "input_matrix",
    ]:
        return path_str

    # List of path variations to try
    path_variants = [
        path_str,  # Original path
        path_str.replace("/", "\\"),  # Convert forward slashes to backslashes
        path_str.replace("\\", "/"),  # Convert backslashes to forward slashes
        urllib.parse.unquote(path_str),  # URL-decoded path
        urllib.parse.unquote(path_str).replace(
            "/", "\\"
        ),  # URL-decoded with slash conversion
        urllib.parse.unquote(path_str).replace(
            "\\", "/"
        ),  # URL-decoded with backslash conversion
    ]

    # Try each variant
    for variant in path_variants:
        try:
            p = Path(variant)
            # Only return if the path exists
            if p.exists():
                return p
        except Exception:
            pass

    # If we get here, no variant worked - return the original string
    # This lets argparse continue and the error will be handled later when the path is used
    return path_str
```

</details>

<details>
<summary><strong>Main CLI Entry Point</strong></summary>

```python
def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Create the top-level parser
    parser = argparse.ArgumentParser(description="EMUSES pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Create a common parser for parallelization options.
    common_parallel = argparse.ArgumentParser(add_help=False)
    parallel_group = common_parallel.add_mutually_exclusive_group()
    parallel_group.add_argument(
        "--umap_jobs",
        type=int,
        help="Number of parallel jobs for outer (UMAP) optimization. "
        "If set, inner optimization runs sequentially.",
    )
    parallel_group.add_argument(
        "--hdbscan_jobs", 
        type=int,
        help="Number of parallel jobs for inner (HDBSCAN) optimization. "
        "If set, outer optimization runs sequentially.",
    )

    # Subparser for the 'full' command
    full_parser = subparsers.add_parser(
        "full", parents=[common_parallel], help="Run the full pipeline"
    )
    
    add_output_folder_argument(full_parser)  # Positional argument
    add_input_dataset_argument(full_parser)  # Positional argument
    # Add optional arguments
    add_input_dataset_optional_arguments(full_parser)
    add_scores_arguments(full_parser)
    add_label_dataset_argument(full_parser)
    add_umap_arguments(full_parser)
    add_clustering_arguments(full_parser)
    add_smoothing_arguments(full_parser)
    add_enhanced_pipeline_arguments(full_parser)  # Add enhanced pipeline arguments
    full_parser.add_argument(
        "--prediction_optim_dict",
        default="optim_dict_predict",
        help="Name of a prediction optim_dict in optim_configs_predict.py (e.g., 'optim_dict_predict', 'optim_dict_phase1')",
    )
    add_random_state_argument(
        full_parser
    )  # Add random state argument for reproducibility
```

</details>

<details>
<summary><strong>Database Conflict Prevention</strong></summary>

```python
def check_for_existing_optuna_databases(output_folder):
    """
    Check for existing Optuna database files in the output folder and exit if found.
    This prevents conflicts from running the pipeline multiple times in the same directory.

    Args:
        output_folder: Path to the output directory
    """
    # Look for Optuna database files with the pattern optuna_target_*.db
    db_pattern = str(output_folder / "optuna_target_*.db")
    existing_dbs = glob.glob(db_pattern)

    if existing_dbs:
        print("\n" + "=" * 70)
        print("ERROR: EXISTING OPTUNA DATABASE FILES DETECTED")
        print("=" * 70)
        print(
            f"Found {len(existing_dbs)} existing Optuna database file(s) in output directory:"
        )
        for db_file in existing_dbs:
            print(f"  - {db_file}")
        print(
            "\nThis indicates that the pipeline has been run previously in this directory."
        )
        print(
            "Running the pipeline again without cleanup will cause Optuna study conflicts."
        )
        print("\nTo resolve this issue, please choose one of the following options:")
        print("  1. Use a different output directory for this run")
        print("  2. Delete the existing database files if you want to start fresh:")
        for db_file in existing_dbs:
            print(f'     rm "{db_file}"')
        print("  3. Move the existing files to a backup location")
        print(
            "\nFor more information about this issue, see the pipeline documentation."
        )
        print("=" * 70)
        sys.exit(1)
```

</details>

<details>
<summary><strong>Pipeline Execution Logic</strong></summary>

```python
    # Parse the command-line arguments
    args = parser.parse_args()

    # Set show_plots to False for CLI
    args.show_plots = False

    # Optional: Print the arguments for debugging
    logger.info("Arguments:")
    for k, v in vars(args).items():
        logger.info(f"{k}: {v}")

    # Create the output folder if it doesn't exist
    output_folder = Path(args.output_folder).resolve()
    output_folder.mkdir(parents=True, exist_ok=True)

    # Check for existing Optuna database files to prevent conflicts
    check_for_existing_optuna_databases(output_folder)

    command_file = output_folder / "command.txt"
    with open(command_file, "w") as f:
        f.write(" ".join(sys.argv))

    # Create the pipeline instance
    pipeline = EMUSESPipeline(args)

    # Determine which stages to add based on the command
    stages_to_add = []
    # TODO make a parameter for the random state
    args.random_state = 42  # Set the random state for reproducibility

    if args.command in ["umap", "full", "prediction"]:
        stages_to_add.append(UMAPStage(pipeline.config))

    if args.command in ["heatmap", "full"]:
        stages_to_add.append(
            HeatmapStage(
                pipeline.config,
                output_format_info=pipeline.context.get("output_format_info"),
            )
        )

    if args.command in ["prediction", "full"]:
        stages_to_add.append(PredictionStage(pipeline.config))

    # Add the stages to the pipeline
    for stage in stages_to_add:
        pipeline.add_stage(stage)

    # Run the pipeline
    pipeline.run()
```

</details>

## Command Structure

The legacy CLI supports five main commands with their respective arguments:

### Full Pipeline Command
- **Usage**: `python main.py full <output_folder> <input_dataset> [options]`
- **Purpose**: Execute complete EMUSES pipeline with all stages
- **Arguments**: All available pipeline arguments (40+ options)

### UMAP Command  
- **Usage**: `python main.py umap <output_folder> <input_dataset> [options]`
- **Purpose**: Run only UMAP dimensionality reduction and clustering
- **Arguments**: Input dataset, UMAP optimization, clustering parameters

### Clustering Command
- **Usage**: `python main.py clustering <output_folder> [options]`
- **Purpose**: Perform clustering on precomputed embeddings  
- **Arguments**: Precomputed embeddings path, clustering parameters

### Heatmap Command
- **Usage**: `python main.py heatmap <output_folder> <input_dataset> [options]`
- **Purpose**: Generate prediction heatmaps and model optimization
- **Arguments**: Input dataset, scores, embedding paths, prediction parameters

### Prediction Command
- **Usage**: `python main.py prediction <output_folder> <input_dataset> [options]`
- **Purpose**: Train prediction models and evaluate performance
- **Arguments**: Input dataset, scores, UMAP parameters, prediction optimization

## Context for Enhanced CLI Implementation

The new Typer-based CLI must:

1. **Replicate exact command structure** - All five commands with identical argument names
2. **Preserve path resolution logic** - Handle URL decoding and cross-platform paths
3. **Maintain parameter validation** - All current validation rules and error messages  
4. **Integrate with FastAPI service** - Replace direct EMUSESPipeline calls with HTTP requests
5. **Add rich features** - Progress bars, colored output, interactive prompts
6. **Support shell completion** - For bash, zsh, powershell
7. **Provide interactive mode** - Guided parameter entry for novice users

Coverage context: [coverage_html/index.html](../coverage_html/index.html)
