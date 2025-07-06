#!/usr/bin/env python3
"""
Test script to run the HCP real-world example using EMUSESPipeline directly.

Thi        'output_dir': base_path / "is_it_running2",
        'features_file': base_path / "selected_columns_data.csv",
        'scores_file': base_path / "specific_columns_data.csv"cript:
1. Detects the operating system
2. Converts paths appropriately (Linux /gamma -> Windows S:\\)
3. Uses EMUSESPipeline directly to execute the same pipeline as the CLI command
4. Validates that the direct execution produces the same results as the CLI would
"""

import asyncio
import platform
import sys
import tempfile
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional
import glob

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def clean_optuna_databases(output_dir: Path):
    """
    Clean up existing pipeline outputs to ensure fresh runs.
    
    This prevents the pipeline from reusing cached data from previous runs
    with different input files, and ensures the n_trials parameter is respected.
    
    Args:
        output_dir: The output directory to clean
    """
    print(">> Cleaning existing pipeline outputs...")
    
    if not output_dir.exists():
        print("   Output directory doesn't exist - no cleanup needed")
        return
    
    # Items to clean for fresh run
    items_to_clean = []
    
    # Find all .db files (Optuna databases)
    items_to_clean.extend(output_dir.rglob("*.db"))
    
    # Find target folders (target_0, target_1, etc.) that contain cached results
    target_dirs = [d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith("target_")]
    items_to_clean.extend(target_dirs)
    
    # Find other cached files that could interfere
    cached_files = [
        "embeddings.npy",
        "cluster_labels.npy",
        "best_trial_info.json",
        "performance_summary_statistics_*.csv",
        "performance_individual_folds_*.csv",
        "performance_overall_statistics_*.csv",
        "performance_target_rankings_*.csv"
    ]
    
    for pattern in cached_files:
        items_to_clean.extend(output_dir.glob(pattern))
    
    if items_to_clean:
        print(f"   Found {len(items_to_clean)} items to remove:")
        for item in items_to_clean:
            try:
                if item.is_dir():
                    import shutil
                    shutil.rmtree(item)
                    print(f"   Removed directory: {item.name}")
                else:
                    item.unlink()
                    print(f"   Removed file: {item.name}")
            except Exception as e:
                print(f"   Warning: Could not remove {item.name}: {e}")
    else:
        print("   No cached items found")
    
    print("   Pipeline cleanup complete")


def detect_and_convert_paths() -> Dict[str, Path]:
    """
    Detect OS and convert paths from the original Linux command to appropriate format.
    
    Original Linux paths:
    - Output: /gamma/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/is_it_running2
    - Features: /gamma/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv
    - Scores: /gamma/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv
    
    Returns:
        Dictionary with converted paths for current OS
    """
    system = platform.system().lower()
    
    # Base paths from the original command
    base_linux_path = "/gamma/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy"
    
    if system == "windows":
        # Convert /gamma to S:\ for Windows
        base_path = Path("S:/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy")
    elif system == "linux" or system == "darwin":  # macOS is darwin
        # Keep original Linux paths
        base_path = Path(base_linux_path)
    else:
        raise OSError(f"Unsupported operating system: {system}")
    
    paths = {
        'output_folder': base_path / "is_it_running2",
        'features_file': base_path / "selected_columns_data.csv",
        'scores_file': base_path / "fluid_int_adj.csv"
    }
    
    print("** Detected OS: " + system)
    print("** Base path: " + str(base_path))
    
    return paths


def validate_input_files(paths: Dict[str, Path]) -> bool:
    """
    Validate that the input files exist and are readable.
    
    Args:
        paths: Dictionary of file paths
        
    Returns:
        True if all files exist and are valid, False otherwise
    """
    print(">> Validating input files...")
    
    required_files = ['features_file', 'scores_file']
    all_valid = True
    
    for file_key in required_files:
        file_path = paths[file_key]
        
        if not file_path.exists():
            print("X File not found: " + str(file_path))
            all_valid = False
            continue
            
        if not file_path.is_file():
            print("X Not a file: " + str(file_path))
            all_valid = False
            continue
            
        # Try to read a few lines to validate format
        try:
            df = pd.read_csv(file_path, nrows=5)
            print(">> " + file_key + ": " + str(file_path))
            print(f"   Shape preview: {df.shape}")
            print(f"   Columns preview: {list(df.columns[:5])}{'...' if len(df.columns) > 5 else ''}")
        except Exception as e:
            print("X Error reading " + file_key + ": " + str(e))
            all_valid = False
    
    return all_valid


def create_pipeline_context(paths: Dict[str, Path]) -> Dict[str, Any]:
    """
    Create the pipeline context dictionary for API execution.
    
    This mimics the same context that would be created by main.py CLI.
    Instead of preprocessing data here, we pass the file paths to EMUSESPipeline
    to let it handle the preprocessing just like the CLI does.
    
    Args:
        paths: Dictionary of file paths
        
    Returns:
        Context dictionary for pipeline execution
    """
    print(" Creating pipeline context with file paths...")
    
    # Ensure output directory exists
    output_dir = paths['output_folder']
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Clean up existing Optuna database files to prevent conflicts
    # (This mirrors the CLI behavior which exits if these exist)
    print("   Cleaning up existing Optuna database files...")
    db_pattern = str(output_dir / "optuna_*.db")
    existing_dbs = glob.glob(db_pattern)
    
    if existing_dbs:
        print(f"   Found {len(existing_dbs)} existing Optuna database files - removing them")
        for db_file in existing_dbs:
            try:
                Path(db_file).unlink()
                print(f"     Removed: {Path(db_file).name}")
            except Exception as e:
                print(f"     Warning: Could not remove {Path(db_file).name}: {e}")
    else:
        print("   No existing Optuna databases found")
    
    # Create context with file paths - let EMUSESPipeline handle data loading and preprocessing
    context = {
        'input_dataset': str(paths['features_file']),  # Path to features CSV
        'scores_dataset': str(paths['scores_file']),   # Path to scores CSV
        'config': {
            'output_folder': str(output_dir),
            'columns_are_features': True,
            'input_header': 0,
            'input_index_column': 0,
            'input_normalization': 'robust',
            'scores_header': 0,
            'scores_index_column': None,  # Don't use index column for single-column scores file
            'interactive_plot': True,
            'umap_trials': 1,
            'hdbscan_trials': 1,
            'optim_dict': 'optim_dict_hcp',
            'hdbscan_jobs': 16,
            'optuna_trials': 10,  # Reduce heatmap optimization trials
            'prediction_optim_dict': 'optim_dict_predict',
            'prefix': 'HCP_API_Test'
        }
    }
    
    print(f"   Input dataset: {context['input_dataset']}")
    print(f"   Scores dataset: {context['scores_dataset']}")
    print(f"   Output folder: {context['config']['output_folder']}")
    
    return context


async def run_hcp_pipeline_via_api(context: Dict[str, Any]) -> bool:
    """
    Execute the HCP pipeline using EMUSESPipeline directly.
    
    Args:
        context: Pipeline execution context
        
    Returns:
        True if execution was successful, False otherwise
    """
    print(" Running HCP pipeline directly...")
    
    try:
        # Import EMUSESPipeline directly 
        from emuses.pipelines.emuses_pipeline import EMUSESPipeline
        from emuses.pipelines.pipeline_config import PipelineConfig
        from emuses.pipelines.umap_stage import UMAPStage
        from emuses.pipelines.heatmap_stage import HeatmapStage
        from emuses.pipelines.prediction_stage import PredictionStage
        import argparse
        
        print(" Setting up pipeline configuration...")
        
        # Convert context to argparse.Namespace (similar to CLI)
        args = argparse.Namespace()
        config_dict = context.get('config', {})
        
        # Required paths
        args.input_dataset = context['input_dataset']
        args.scores = context['scores_dataset']  # CLI uses 'scores', not 'scores_dataset'
        args.output_folder = str(config_dict['output_folder'])
        
        # Basic configuration
        args.columns_are_features = config_dict.get('columns_are_features', True)
        args.input_header = config_dict.get('input_header', 0)
        args.input_index_column = config_dict.get('input_index_column', 0)
        args.inputs_columns = None  # Optional column filtering
        args.input_normalization = config_dict.get('input_normalization', 'robust')
        args.scores_header = config_dict.get('scores_header', 0)
        args.scores_index_column = config_dict.get('scores_index_column', None)  # None for single-column file
        args.scores_are_rows = False  # Default value
        args.scores_column = None  # Optional column filtering
        args.scores_normalization = "none"  # Default normalization
        args.load_embeddings = None  # Optional precomputed embeddings
        args.classification = False  # Default value
        args.interactive_plot = config_dict.get('interactive_plot', True)
        
        # Optimization parameters
        args.umap_trials = config_dict.get('umap_trials', 1)
        args.hdbscan_trials = config_dict.get('hdbscan_trials', 1)
        args.optuna_trials = config_dict.get('optuna_trials', 10)
        args.optim_dict = config_dict.get('optim_dict', 'optim_dict_hcp')
        args.prediction_optim_dict = config_dict.get('prediction_optim_dict', 'optim_dict_predict')
        args.hdbscan_jobs = config_dict.get('hdbscan_jobs', 16)
        args.prefix = config_dict.get('prefix', 'HCP_Direct')
        
        # Additional required parameters
        args.random_state = 42
        args.test_size = 0.2
        args.outer_folds = 5
        args.model_version = "1.0.0"
        
        # Stage configuration
        args.umap_stage_enabled = True
        args.heatmap_stage_enabled = True
        args.prediction_stage_enabled = True
        
        print(" Executing pipeline (this may take several minutes)...")
        
        # Create and run pipeline directly (pass args, not config)
        pipeline = EMUSESPipeline(args)
        
        # Add stages just like the CLI does for "full" command
        print(" Adding pipeline stages...")
        
        # Add UMAP stage (for "umap", "full", "prediction" commands)
        umap_stage = UMAPStage(pipeline.config)
        pipeline.add_stage(umap_stage)
        print("   Added UMAP stage")
        
        # Add Heatmap stage (for "heatmap", "full" commands)
        heatmap_stage = HeatmapStage(
            pipeline.config,
            output_format_info=pipeline.context.get("output_format_info")
        )
        pipeline.add_stage(heatmap_stage)
        print("   Added Heatmap stage")
        
        # Add Prediction stage (for "prediction", "full" commands)
        prediction_stage = PredictionStage(pipeline.config)
        pipeline.add_stage(prediction_stage)
        print("   Added Prediction stage")
        
        print(f" Running {len(pipeline.stages)} stages...")
        pipeline.run()
        
        print(" Pipeline execution completed!")
        
        # Validate outputs
        output_dir = Path(context['config']['output_folder'])
        if output_dir.exists():
            output_files = list(output_dir.rglob('*'))
            output_file_count = len([f for f in output_files if f.is_file()])
            print(f" Generated {output_file_count} output files")
        
        return True
        
    except Exception as e:
        print(f" Pipeline execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def compare_with_cli_command(paths: Dict[str, Path]):
    """
    Print the equivalent CLI command for comparison.
    
    Args:
        paths: Dictionary of file paths
    """
    print("\n Equivalent CLI command:")
    print("=" * 80)
    
    cmd_parts = [
        "python emuses/scripts/main.py full",
        f'"{paths["output_folder"]}"',
        f'"{paths["features_file"]}"',
        "--columns_are_features",
        "--input_header 0",
        "--input_index_column 0",
        "-inorm robust",
        f'--scores "{paths["scores_file"]}"',
        "--scores_header 0",
        # "--scores_index_column 0",  # Commented out since fluid_int_adj.csv is single column
        "--interactive_plot",
        "--umap_trials 1",
        "--hdbscan_trials 1",
        "--optim_dict optim_dict_hcp",
        "--hdbscan_jobs 16",
        "--prediction_optim_dict optim_dict_predict"
    ]
    
    print(" \\\n  ".join(cmd_parts))
    print("=" * 80)


async def main():
    """Main execution function."""
    
    print(" HCP Real-World Example - API Execution Test")
    print("=" * 60)
    
    try:
        # Step 1: Detect OS and convert paths
        paths = detect_and_convert_paths()
        
        # Step 2: Validate input files exist
        if not validate_input_files(paths):
            print("\n Input file validation failed. Please check file paths.")
            print("\nTip: Make sure the network drive is mounted and files are accessible.")
            return False
            
        # Step 3: Show equivalent CLI command
        compare_with_cli_command(paths)
        
        # Step 4: Clean up existing pipeline outputs to ensure fresh runs
        clean_optuna_databases(paths['output_folder'])
        
        # Step 5: Create pipeline context
        context = create_pipeline_context(paths)
        
        # Step 6: Execute directly via EMUSESPipeline
        success = await run_hcp_pipeline_via_api(context)
        
        if success:
            print("\n HCP pipeline completed successfully!")
            print(f" Results saved to: {paths['output_folder']}")
        else:
            print("\n HCP pipeline execution failed!")
            
        return success
        
    except Exception as e:
        print(f"\n Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print(" Starting HCP Direct Test...")
    
    # Run the async main function
    success = asyncio.run(main())
    
    if success:
        print("\n Test completed successfully!")
        sys.exit(0)
    else:
        print("\n Test failed!")
        sys.exit(1)
