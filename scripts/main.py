# Main script for EMUSE pipeline integrating full functionality
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from bcblib.tools.general_utils import open_json, parse_file_list_argument
from tools.UMAP_utils import train_and_save_umap_and_embeddings, load_umap_model
from tools.inputs_utils import create_heatmap_data, detect_dataset_type, \
    process_images, nifti_dataset_to_matrix, mnist_features_to_input_matrix, load_and_preprocess_digits_dataset
from tools.data_preproc import find_min_resolution
from tools.correlation_maps_utils import cluster_coordinates
from tools.visualisation import plot_clustering_interactive_with_hover
from sklearn.model_selection import train_test_split
from tools.emuses_utils import rescale_embedding
import importlib


def main():
    parser = argparse.ArgumentParser(description='EMUSE pipeline')
    subparsers = parser.add_subparsers(dest='command')

    # Command for the full pipeline
    full_parser = subparsers.add_parser('full', help='Run the full pipeline')
    full_parser.add_argument('input_dataset', help='Input dataset of either images (jpg), NIfTI, or MNIST')
    full_parser.add_argument('output_folder', help='Output folder')
    full_parser.add_argument('-rs', '--recursive_input_file_search', action='store_true',
                             help='Search for files recursively in the input dataset folder')
    full_parser.add_argument('--input_file_types', nargs='+', default=None,
                             help='File types to search for in the input dataset folder')
    full_parser.add_argument('--arg_separator', default=',',
                             help='Separator for the input dataset list')
    full_parser.add_argument('--prefix', default='', help='Prefix for the output path names')
    full_parser.add_argument('--stat_function', default='mean', help='Statistical function name for the heatmaps')
    full_parser.add_argument('--new_dataset', help='New dataset for creating the heatmaps')
    full_parser.add_argument('--scores', nargs='+', help='Scores associated with the new dataset')
    full_parser.add_argument('--interactive_plot', action='store_true', help='Option to create interactive clustering plots')

    # Command for training the UMAP and getting the embeddings
    umap_parser = subparsers.add_parser('umap', help='Train the UMAP and get the embeddings')
    umap_parser.add_argument('input_dataset', type=str,
                             help='Input dataset of either images (jpg), NIfTI, or MNIST')
    umap_parser.add_argument('output_folder', help='Output folder')
    umap_parser.add_argument('-rs', '--recursive_input_file_search', action='store_true',
                             help='Search for files recursively in the input dataset folder')
    umap_parser.add_argument('--input_file_types', nargs='+', default=None,
                             help='File types to search for in the input dataset folder')
    umap_parser.add_argument('--arg_separator', default=',',
                             help='Separator for the input dataset list')
    umap_parser.add_argument('--prefix', default='', help='Prefix for the output path names')

    # Command for creating heatmaps
    heatmap_parser = subparsers.add_parser('heatmap', help='Create a heatmap')
    heatmap_parser.add_argument('embeddings', help='Embeddings from the UMAP')
    heatmap_parser.add_argument('--stat_function', default='mean',
                                help='Statistical function name for the heatmaps')
    heatmap_parser.add_argument('--new_dataset', help='New dataset for creating the heatmaps')
    heatmap_parser.add_argument('--scores', nargs='+', help='Scores associated with the new dataset')
    smoothing_group = heatmap_parser.add_mutually_exclusive_group()
    smoothing_group.add_argument('--sigma', type=float, help='Sigma value for the smoothing')
    smoothing_group.add_argument('--fwhm', type=float,
                                 help='Full width at half maximum value for the smoothing')

    args = parser.parse_args()

    # Input dataset and output folder validation
    args.input_dataset = Path(args.input_dataset).resolve()
    if not args.input_dataset.is_dir() or not args.input_dataset.exists():
        raise ValueError(f"Input dataset {args.input_dataset} is not a valid path")

    args.output_folder = Path(args.output_folder).resolve()
    Path(args.output_folder).mkdir(parents=True, exist_ok=True)
    if not args.output_folder.is_dir():
        raise ValueError(f"Output folder {args.output_folder} is not a valid path")

    # Split dataset into training and testing sets
    if args.command == 'full' or args.command == 'umap':
        # Parsing the dataset
        paths_list = parse_file_list_argument(args.input_dataset,
                                              recursive_file_search=args.recursive_input_file_search,
                                              file_types=args.input_file_types,
                                              arg_separator=args.arg_separator)

        # Detect dataset type and process
        dataset_type = detect_dataset_type(paths_list)
        if dataset_type == 'image':
            min_res = find_min_resolution(paths_list)
            input_matrix = process_images(paths_list, min_res)
        elif dataset_type == 'nifti':
            input_matrix = nifti_dataset_to_matrix(paths_list)
        elif dataset_type == 'mnist':
            mnist_features_normalized, mnist_labels = load_and_preprocess_digits_dataset()
            input_matrix = mnist_features_to_input_matrix(mnist_features_normalized)
        else:
            raise ValueError(f"Unsupported dataset type: {dataset_type}")

        # Split the data into training and test sets
        train_features, test_features, train_labels, test_labels = train_test_split(
            input_matrix, mnist_labels if dataset_type == 'mnist' else None, test_size=0.2, random_state=42)

        # Train and save UMAP embeddings
        trained_umap, embeddings, umap_path, embeddings_path, input_matrix_path = train_and_save_umap_and_embeddings(train_features, args.output_folder, pref=args.prefix)
        print(f"UMAP model saved at: {umap_path}")
        print(f"Embeddings saved at: {embeddings_path}")
        print(f"Input matrix saved at: {input_matrix_path}")

        # Rescale embeddings
        min_embeddings = embeddings.min(axis=0)
        max_embeddings = embeddings.max(axis=0)
        rescaled_embeddings = rescale_embedding(embeddings, preset_min=min_embeddings, preset_max=max_embeddings)

        training_embeddings = rescaled_embeddings
        test_embeddings = rescale_embedding(trained_umap.transform(test_features), preset_max=max_embeddings, preset_min=min_embeddings)

        # Prepare DataFrames for training and test sets
        train_df = pd.DataFrame(data={'embeddings': [tuple(coord) for coord in training_embeddings]})
        train_df['scores'] = train_labels

        test_df = pd.DataFrame(data={'embeddings': [tuple(coord) for coord in test_embeddings]})
        test_df['scores'] = test_labels

        # If interactive plot option is set, create an interactive clustering plot
        if args.interactive_plot:
            try:
                clusterer, cluster_labels = cluster_coordinates(embeddings, min_cluster_size=5)
                plot_clustering_interactive_with_hover(embeddings, cluster_labels)
            except Exception as e:
                print(f"Failed to create an interactive clustering plot: {e}")

    if args.command == 'full' or args.command == 'heatmap':
        # Create heatmaps using UMAP embeddings
        embeddings_path = Path(args.embeddings)
        if embeddings_path.suffix == '.npy' and embeddings_path.exists():
            embeddings = np.load(embeddings_path)
        else:
            raise ValueError(f'Embeddings file {embeddings_path} does not exist or is not a .npy file')

        # Prepare DataFrame for heatmap
        embeddings, scores = create_heatmap_data(embeddings, args.new_dataset, args.scores[0] if args.scores else None)
        df = pd.DataFrame(embeddings, columns=['embedding'])
        df['scores'] = scores

        # TODO: Implement smoothing and heatmap visualization based on provided arguments
        # Smoothing heatmap based on provided arguments (e.g., sigma or fwhm)
        # TODO: Call a function like create_heatmap and implement visualization


if __name__ == '__main__':
    main()
