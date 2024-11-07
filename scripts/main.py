# main.py

import argparse
import logging
from pathlib import Path

# Import pipeline classes
from pipelines.emuses_pipeline import EMUSESPipeline
from pipelines.umap_stage import UMAPStage
from pipelines.clustering_stage import ClusteringStage
from pipelines.heatmap_stage import HeatmapStage
from pipelines.prediction_stage import PredictionStage


def get_input_dataset_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('input_dataset', help='Input dataset of images (jpg), NIfTI, or MNIST')
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
    parser.add_argument('--columns_as_features', action='store_true',
                        help='Columns are features in the spreadsheet input dataset')
    parser.add_argument('--bids_filters', nargs='+', default=None,
                        help='BIDS filters for the input dataset')
    return parser


def get_scores_parser():
    parser = argparse.ArgumentParser(add_help=False)
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
    return parser


def get_umap_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--load_umap', help='Path to a pre-trained UMAP model')
    parser.add_argument('--load_embeddings', help='Path to precomputed embeddings')
    parser.add_argument('--test_size', type=float, default=0.2,
                        help='Test size for splitting the dataset')
    parser.add_argument('--prefix', default='', help='Prefix for the output path names')
    return parser


def get_clustering_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--load_hdbscan', help='Path to a pre-trained HDBSCAN model')
    parser.add_argument('--min_cluster_size', type=int, default=5, help='Minimum cluster size')
    parser.add_argument('--interactive_plot', action='store_true',
                        help='Option to create interactive clustering plots')
    return parser


def get_smoothing_parser():
    parser = argparse.ArgumentParser(add_help=False)
    smoothing_group = parser.add_mutually_exclusive_group()
    smoothing_group.add_argument('--sigma', type=float, help='Sigma value for the smoothing')
    smoothing_group.add_argument('--fwhm', type=float,
                                 help='Full width at half maximum value for the smoothing')
    return parser


def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Create the top-level parser
    parser = argparse.ArgumentParser(description='EMUSES pipeline')
    parser.add_argument('output_folder', help='Output folder')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Parent parsers for common arguments
    input_dataset_parser = get_input_dataset_parser()
    scores_parser = get_scores_parser()
    umap_parser = get_umap_parser()
    clustering_parser = get_clustering_parser()
    smoothing_parser = get_smoothing_parser()

    # Subparsers for commands
    # Subparser for the 'full' command
    full_parser = subparsers.add_parser(
        'full',
        parents=[input_dataset_parser, scores_parser, umap_parser, clustering_parser, smoothing_parser],
        help='Run the full pipeline',
        add_help=True
    )

    # Subparser for the 'umap' command
    umap_cmd_parser = subparsers.add_parser(
        'umap',
        parents=[input_dataset_parser, umap_parser],
        help='Train the UMAP and get the embeddings',
        add_help=True
    )

    # Subparser for the 'clustering' command
    clustering_cmd_parser = subparsers.add_parser(
        'clustering',
        parents=[clustering_parser],
        help='Perform clustering on embeddings',
        add_help=True
    )
    clustering_cmd_parser.add_argument('--load_embeddings', help='Path to precomputed embeddings')

    # Subparser for the 'heatmap' command
    heatmap_parser = subparsers.add_parser(
        'heatmap',
        parents=[input_dataset_parser, scores_parser, smoothing_parser],
        help='Create a heatmap',
        add_help=True
    )
    heatmap_parser.add_argument('--load_embeddings', help='Embeddings from the UMAP')
    heatmap_parser.add_argument('--load_hdbscan', help='Path to a pre-trained HDBSCAN model')
    heatmap_parser.add_argument('--output_format_info', help='Output format information needed')

    # Subparser for the 'prediction' command
    prediction_parser = subparsers.add_parser(
        'prediction',
        parents=[input_dataset_parser, scores_parser, umap_parser],
        help='Train a prediction model',
        add_help=True
    )

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

    # Create the pipeline instance
    pipeline = EMUSESPipeline(args)

    # Determine which stages to add based on the command
    stages_to_add = []

    if args.command in ['umap', 'full', 'prediction']:
        stages_to_add.append(UMAPStage(pipeline.config))

    if args.command in ['clustering', 'full']:
        stages_to_add.append(ClusteringStage(pipeline.config))

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
