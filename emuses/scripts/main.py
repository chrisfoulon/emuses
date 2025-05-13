# main.py

import argparse
import logging
import sys
from pathlib import Path

# Import pipeline classes
from emuses.pipelines.emuses_pipeline import EMUSESPipeline
from emuses.pipelines.umap_stage import UMAPStage
from emuses.pipelines.heatmap_stage import HeatmapStage
from emuses.pipelines.prediction_stage import PredictionStage


def add_output_folder_argument(parser):
    """
    Adds the 'output_folder' positional argument to the parser.
    """
    parser.add_argument('output_folder', help='Output folder')


def add_input_dataset_argument(parser):
    """
    Adds the 'input_dataset' positional argument to the parser.
    """
    parser.add_argument('input_dataset', help='Input dataset of images (jpg), NIfTI, or MNIST')


def add_label_dataset_argument(parser):
    """
    Adds an optional argument for specifying a separate labelled dataset.
    """
    parser.add_argument('--label_dataset',
                        help='Path to a separate labelled dataset (e.g., folder containing NIfTI files)')


def add_input_dataset_optional_arguments(parser):
    """
    Adds optional arguments related to the input dataset to the parser.
    Note: Does NOT add positional arguments.
    """
    parser.add_argument('-rs', '--recursive_input_file_search', action='store_true',
                        help='Search recursively in the input dataset folder')
    parser.add_argument('--input_file_types', nargs='+', default=None,
                        help='File types to search for in the input dataset folder')
    parser.add_argument('--arg_separator', default=',',
                        help='Separator for the input dataset list')
    parser.add_argument('--input_header', default=None, type=int,
                        help='Header for the spreadsheet input dataset')
    parser.add_argument('--inputs_columns', nargs='+',
                        help='List of columns for inputs in the scores file')
    parser.add_argument('--input_index_column', default=None, type=int,
                        help='Index column for the spreadsheet input dataset')
    parser.add_argument('--columns_are_features', action='store_true',
                        help='Columns are features in the spreadsheet input dataset')
    parser.add_argument('--bids_filters', nargs='+', default=None,
                        help='BIDS filters for the input dataset')
    # Add normalization argument for input data
    parser.add_argument('--input_normalization', '-inorm', default='none',
                        choices=['none', 'zscore', 'min-max', 'zero-max', 'robust'],
                        help='Normalization method for input data.')


def add_scores_arguments(parser):
    """
    Adds optional arguments related to the scores file to the parser.
    """
    parser.add_argument('--scores', help='Path to scores file associated with the dataset')
    parser.add_argument('--scores_header', type=int, default=None,
                        help='Header for the scores spreadsheet')
    parser.add_argument('--scores_index_column', type=int, default=None,
                        help='Index column for the scores spreadsheet')
    parser.add_argument('--scores_are_rows', action='store_true',
                        help='Scores are in the columns of the spreadsheet input dataset')
    parser.add_argument('--scores_column', nargs='+', help='Column(s) for scores in the scores file')
    parser.add_argument('--classification', action='store_true',
                        help='Scores are integer classes in one column')
    parser.add_argument('--correlation_method', default='pearson', choices=['pearson', 'spearman', 'pointbiserial'],
                        help='Method to use for correlation calculation (default: pearson)')
    # Add normalization argument for scores data
    parser.add_argument('--scores_normalization', '-snorm', default='none',
                        choices=['none', 'zscore', 'min-max', 'zero-max'],
                        help='Normalization method for scores data.')
    parser.add_argument('--filter_labelled_by_scores', action='store_true',
                        help='If set, filter the labelled dataset to only keep files referenced in the scores file.')


def add_random_state_argument(parser):
    """
    Adds random_state parameter for reproducibility
    """
    parser.add_argument('--random_state', type=int, default=42,
                        help='Master random seed for reproducibility (default: 42)')


def add_umap_arguments(parser):
    """
    Adds optional arguments related to the UMAP stage to the parser.
    """
    parser.add_argument('--load_umap', help='Path to a pre-trained UMAP model')
    parser.add_argument('--load_embeddings', help='Path to precomputed embeddings')
    parser.add_argument('--test_size', type=float, default=0.2,
                        help='Test size for splitting the dataset')
    parser.add_argument('--prefix', default='', help='Prefix for the output path names')
    parser.add_argument('--optim_dict', default='optim_dict_default',
                        help='Name of an optim_dict in optim_configs.py of Path to the optimization dictionary')
    parser.add_argument('--umap_trials', type=int, default=50,
                        help='Number of outer (UMAP) optimization trials')
    parser.add_argument('--hdbscan_trials', type=int, default=20,
                        help='Number of inner (HDBSCAN) optimization trials')


def add_clustering_arguments(parser):
    """
    Adds optional arguments related to the clustering stage to the parser.
    """
    parser.add_argument('--load_hdbscan', help='Path to a pre-trained HDBSCAN model')
    parser.add_argument('--min_cluster_size', type=int, default=5, help='Minimum cluster size')
    parser.add_argument('--interactive_plot', action='store_true',
                        help='Option to create interactive clustering plots')


def add_smoothing_arguments(parser):
    """
    Adds mutually exclusive optional arguments related to smoothing to the parser.
    """
    smoothing_group = parser.add_mutually_exclusive_group()
    smoothing_group.add_argument('--sigma', type=float, help='Sigma value for the smoothing')
    smoothing_group.add_argument('--fwhm', type=float,
                                 help='Full width at half maximum value for the smoothing')


# Parser arguments related to model optimization and parallelization
def add_enhanced_pipeline_arguments(parser):
    """
    Adds optional arguments related to the enhanced pipeline with Optuna optimization.
    """
    parser.add_argument('--use_enhanced_pipeline', action='store_true',
                      help='Use the enhanced pipeline with Optuna optimization for model selection')
    parser.add_argument('--optuna_trials', type=int, default=50,
                      help='Number of trials for Optuna optimization per model/feature set')
    parser.add_argument('--parallel_models', action='store_true',
                      help='Train models in parallel across different feature sets')
    parser.add_argument('--n_jobs', type=int, default=-1,
                      help='Number of parallel jobs for model training (-1 uses all cores)')
    parser.add_argument('--model_selection', nargs='+', default=None,
                      help='List of models to try. Options: gp, rf, gb, kr, xgb, lgb, et, svr')

def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Create the top-level parser
    parser = argparse.ArgumentParser(description='EMUSES pipeline')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Create a common parser for parallelization options.
    common_parallel = argparse.ArgumentParser(add_help=False)
    parallel_group = common_parallel.add_mutually_exclusive_group()
    parallel_group.add_argument('--umap_jobs', type=int,
                                help='Number of parallel jobs for outer (UMAP) optimization. '
                                     'If set, inner optimization runs sequentially.')
    parallel_group.add_argument('--hdbscan_jobs', type=int,
                                help='Number of parallel jobs for inner (HDBSCAN) optimization. '
                                     'If set, outer optimization runs sequentially.')

    # Subparser for the 'full' command
    full_parser = subparsers.add_parser('full', parents=[common_parallel], help='Run the full pipeline')

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
    add_random_state_argument(full_parser)  # Add random state argument for reproducibility
    add_random_state_argument(full_parser)  # Add random state argument

    # Subparser for the 'umap' command
    umap_parser = subparsers.add_parser('umap', help='Train the UMAP and get the embeddings')
    add_output_folder_argument(umap_parser)  # Positional argument
    add_input_dataset_argument(umap_parser)  # Positional argument
    # Add optional arguments
    add_input_dataset_optional_arguments(umap_parser)
    add_umap_arguments(umap_parser)
    add_random_state_argument(umap_parser)  # Add random state argument for reproducibility
    add_random_state_argument(umap_parser)  # Add random state argument

    # Subparser for the 'clustering' command
    clustering_parser = subparsers.add_parser('clustering', help='Perform clustering on embeddings')
    add_output_folder_argument(clustering_parser)  # Positional argument
    # No 'input_dataset' positional argument here
    # Add optional arguments
    clustering_parser.add_argument('--load_embeddings', help='Path to precomputed embeddings')
    add_clustering_arguments(clustering_parser)
    add_random_state_argument(clustering_parser)  # Add random state argument for reproducibility

    # Subparser for the 'heatmap' command
    heatmap_parser = subparsers.add_parser('heatmap', help='Create a heatmap')
    add_output_folder_argument(heatmap_parser)  # Positional argument
    add_input_dataset_argument(heatmap_parser)  # Positional argument
    # Add optional arguments
    add_input_dataset_optional_arguments(heatmap_parser)
    add_scores_arguments(heatmap_parser)
    add_smoothing_arguments(heatmap_parser)
    heatmap_parser.add_argument('--load_embeddings', help='Embeddings from the UMAP')
    heatmap_parser.add_argument('--load_hdbscan', help='Path to a pre-trained HDBSCAN model')
    heatmap_parser.add_argument('--output_format_info', help='Output format information needed')
    add_random_state_argument(heatmap_parser)  # Add random state argument for reproducibility

    # Subparser for the 'prediction' command
    prediction_parser = subparsers.add_parser('prediction', help='Train a prediction model')
    add_output_folder_argument(prediction_parser)  # Positional argument
    add_input_dataset_argument(prediction_parser)  # Positional argument
    # Add optional arguments
    add_input_dataset_optional_arguments(prediction_parser)
    add_scores_arguments(prediction_parser)
    add_umap_arguments(prediction_parser)
    add_enhanced_pipeline_arguments(prediction_parser)  # Add enhanced pipeline arguments
    add_random_state_argument(prediction_parser)  # Add random state argument

    # add run_old_prediction argument
    full_parser.add_argument('--run_old_prediction', action='store_true',
                            help='Run the old prediction pipeline')

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

    command_file = output_folder / 'command.txt'
    with open(command_file, 'w') as f:
        f.write(' '.join(sys.argv))

    # Create the pipeline instance
    pipeline = EMUSESPipeline(args)

    # Determine which stages to add based on the command
    stages_to_add = []
    # TODO make a parameter for the random state
    args.random_state = 42  # Set the random state for reproducibility

    if args.command in ['umap', 'full', 'prediction']:
        stages_to_add.append(UMAPStage(pipeline.config))

    if args.command in ['heatmap', 'full']:
        stages_to_add.append(HeatmapStage(
            pipeline.config,
            output_format_info=pipeline.context.get('output_format_info')
        ))

    if args.command in ['prediction', 'full']:
        stages_to_add.append(PredictionStage(pipeline.config))

    # Add the stages to the pipeline
    for stage in stages_to_add:
        pipeline.add_stage(stage)

    # Run the pipeline
    pipeline.run()


if __name__ == '__main__':
    main()
