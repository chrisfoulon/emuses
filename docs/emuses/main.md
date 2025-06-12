# EMUSES Main Script

The main entry point for the EMUSES pipeline provides a command-line interface for executing different stages of the machine learning workflow, including UMAP dimensionality reduction, clustering, prediction modeling, and heatmap generation. It orchestrates the entire pipeline by parsing command-line arguments and executing the appropriate stages based on user input.

<details><summary>🛠️ Level 2 · Key API table</summary>

| Function/Class | Purpose | Inputs | Outputs | Side-effects |
|---|---|---|---|---|
| `main()` | CLI orchestrator and pipeline entry point | `sys.argv: List[str]` | `None` | Creates output directories, logs commands, runs pipeline stages |
| `resolve_path(path_str)` | Robust path resolver handling spaces and formats | `path_str: str` | `Path \| str` | None |
| `check_for_existing_optuna_databases(output_folder)` | Prevents Optuna study conflicts | `output_folder: Path` | `None` | Exits program if conflicts found |
| `add_*_arguments(parser)` | Add argument groups to ArgumentParser | `parser: ArgumentParser` | `None` | Modifies parser in-place |
| `EMUSESPipeline(args)` | Main pipeline orchestrator | `args: argparse.Namespace` | `EMUSESPipeline` | Initializes stages, manages data flow |

</details>

<details><summary>🔍 Level 3 · Code walk-through</summary>

## Command Structure
The main script supports multiple subcommands for different pipeline workflows:

```python
def main():
    """
    Main entry point for EMUSES pipeline CLI.
    
    Subcommands:
    - full: Complete pipeline (UMAP → clustering → heatmap → prediction)
    - umap: UMAP training and embedding generation
    - clustering: Clustering on pre-computed embeddings  
    - heatmap: Correlation heatmap generation
    - prediction: Prediction model training and evaluation
    
    Returns
    -------
    None
        Executes pipeline and saves results to output_folder
    """
    # Configure logging for both console and file output
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Create argument parser with subcommands
    parser = argparse.ArgumentParser(description="EMUSES pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
```

## Path Resolution
Handles complex path formats including URL encoding and cross-platform compatibility:

```python
def resolve_path(path_str):
    """
    Robust path resolver for handling various path formats.
    
    Parameters
    ----------
    path_str : str
        Input path string that may contain spaces, URL encoding, or platform-specific separators
        
    Returns
    -------
    Path or str
        Resolved pathlib.Path object if valid path found, otherwise original string
        
    Notes
    -----
    Tries multiple path variations:
    - Original path
    - Forward/backward slash conversions  
    - URL-decoded variants
    - Platform-specific separators
    """
    # Special case handling for dataset identifiers
    if path_str and path_str.lower() in ["mnist", "digits_label_dataset", "input_matrix"]:
        return path_str
    
    # Try multiple path format variations
    path_variants = [
        path_str,
        path_str.replace("/", "\\"),
        path_str.replace("\\", "/"), 
        urllib.parse.unquote(path_str),
        # ... additional variants
    ]
```

## Pipeline Stage Orchestration
Determines and executes appropriate stages based on command:

```python
# Create pipeline instance with validated arguments
pipeline = EMUSESPipeline(args)

# Determine stages based on command
stages_to_add = []
if args.command in ["umap", "full", "prediction"]:
    stages_to_add.append(UMAPStage(pipeline.config))

if args.command in ["heatmap", "full"]:
    stages_to_add.append(HeatmapStage(
        pipeline.config,
        output_format_info=pipeline.context.get("output_format_info")
    ))

if args.command in ["prediction", "full"]:
    stages_to_add.append(PredictionStage(pipeline.config))

# Execute pipeline
for stage in stages_to_add:
    pipeline.add_stage(stage)
pipeline.run()
```

## Argument Groups
The script organizes arguments into logical groups for different pipeline aspects:

- **Dataset arguments**: Input/output paths, file types, BIDS filters
- **UMAP arguments**: Optimization parameters, trials, parallelization  
- **Clustering arguments**: HDBSCAN parameters, reproducibility settings
- **Prediction arguments**: Model selection, enhanced pipeline options
- **Enhanced pipeline arguments**: Optuna trials, parallel processing

</details>
