# Main script for EMUSE pipeline integrating full functionality
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from bcblib.tools.general_utils import open_json, parse_file_list_argument, save_json
from tools.UMAP_utils import train_and_save_umap_and_embeddings, load_umap_model
from tools.inputs_utils import (create_heatmap_data, detect_dataset_type, \
                                process_images, nifti_dataset_to_matrix, mnist_features_to_input_matrix,
                                load_and_preprocess_digits_dataset,
                                prepare_scores, spreadsheet_to_input_df,
                                is_bids_dataset, handle_bids_dataset)
from tools.data_preproc import find_min_resolution
from tools.correlation_maps_utils import cluster_coordinates
from tools.visualisation import plot_clustering_interactive_with_hover, plot_clustering
from tools.correlation_maps_utils import run_heatmap_analysis
from tools.stats_utils import train_model
from sklearn.model_selection import train_test_split
from tools.emuses_utils import rescale_embedding


def main():
    parser = argparse.ArgumentParser(description='EMUSE pipeline')
    parser.add_argument('output_folder', help='Output folder')
    subparsers = parser.add_subparsers(dest='command')
    # , choices = ['full', 'umap', 'heatmap', 'clustering', 'prediction']

    # Command for the full pipeline
    full_parser = subparsers.add_parser('full', help='Run the full pipeline')
    full_parser.add_argument('input_dataset', help='Input dataset of either images (jpg), NIfTI, or MNIST')
    full_parser.add_argument('-bf', '--bids_filters', nargs='+', default=None,
                                help='BIDS filters for the input dataset')
    full_parser.add_argument('--input_header', default=None,
                             help='Header for the spreadsheet input dataset')
    full_parser.add_argument('--inputs_columns', nargs='+',
                             help='List of columns for inputs in the scores file')
    full_parser.add_argument('--input_index_column', default=None,
                             help='Index column for the spreadsheet input dataset')
    full_parser.add_argument('--columns_as_features', action='store_true',
                             help='Columns are features in the spreadsheet input dataset')
    full_parser.add_argument('-rs', '--recursive_input_file_search', action='store_true',
                             help='Search for files recursively in the input dataset folder')
    full_parser.add_argument('--input_file_types', nargs='+', default=None,
                             help='File types to search for in the input dataset folder')
    full_parser.add_argument('--arg_separator', default=',',
                             help='Separator for the input dataset list')
    full_parser.add_argument('--prefix', default='', help='Prefix for the output path names')
    full_parser.add_argument('--new_dataset', help='New dataset for creating the heatmaps')
    full_parser.add_argument('--scores', help='Path to scores file associated with the dataset')
    full_parser.add_argument('--scores_header', default=None, help='Header for the scores spreadsheet')
    full_parser.add_argument('--scores_index_column', default=None,
                             help='Index column for the scores spreadsheet')
    full_parser.add_argument('--scores_are_columns', action='store_true',
                             help='Scores are in the columns of the spreadsheet input dataset')
    full_parser.add_argument('--scores_column', help='Column for scores in the scores file')
    full_parser.add_argument('--interactive_plot', action='store_true',
                             help='Option to create interactive clustering plots')
    full_parser.add_argument('--test_size', type=float, default=0.2,
                             help='Test size for splitting the dataset')
    full_parser.add_argument('--load_umap', help='Path to a pre-trained UMAP model')
    full_parser.add_argument('--load_hdbscan', help='Path to a pre-trained HDBSCAN model')
    full_parser.add_argument('--load_rf', help='Path to a pre-trained Random Forest model')
    full_parser.add_argument('--load_embeddings', help='Path to precomputed embeddings')
    full_parser.add_argument('--sigma', type=float, help='Sigma value for the smoothing')
    full_parser.add_argument('--fwhm', type=float,
                             help='Full width at half maximum value for the smoothing')
    full_parser.add_argument('--classification', action='store_true',
                                help='The scores are only one column with multiple integer values (classes)')

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
    umap_parser.add_argument('--test_size', type=float, default=0.0,
                             help='Test size for splitting the dataset (default is 0 for UMAP only)')

    # Command for creating heatmaps
    heatmap_parser = subparsers.add_parser('heatmap', help='Create a heatmap')
    heatmap_parser.add_argument('embeddings', help='Embeddings from the UMAP')
    heatmap_parser.add_argument('--new_dataset', help='New dataset for creating the heatmaps')
    heatmap_parser.add_argument('--scores', nargs='+', help='Scores associated with the new dataset')
    heatmap_parser.add_argument('--classification', action='store_true',
                                help='The scores are only one column with multiple integer values (classes)')
    smoothing_group = heatmap_parser.add_mutually_exclusive_group()
    smoothing_group.add_argument('--sigma', type=float, help='Sigma value for the smoothing')
    smoothing_group.add_argument('--fwhm', type=float,
                                 help='Full width at half maximum value for the smoothing')

    # Command for clustering
    clustering_parser = subparsers.add_parser('clustering', help='Perform clustering on embeddings')
    clustering_parser.add_argument('embeddings', help='Path to the embeddings to cluster')
    clustering_parser.add_argument('output_folder', help='Output folder')
    clustering_parser.add_argument('--min_cluster_size', type=int, default=5, help='Minimum cluster size')

    # Command for prediction
    prediction_parser = subparsers.add_parser('prediction', help='Train a prediction model')
    prediction_parser.add_argument('embeddings', help='Path to the embeddings to use for training the model')
    prediction_parser.add_argument('scores', help='Path to the scores associated with the embeddings')
    prediction_parser.add_argument('output_folder', help='Output folder')

    args = parser.parse_args()

    # Output folder is THE argument that is common to all commands and does not change
    args.output_folder = Path(args.output_folder).resolve()
    Path(args.output_folder).mkdir(parents=True, exist_ok=True)
    if not args.output_folder.is_dir():
        raise ValueError(f"Output folder {args.output_folder} is not a valid path")
    if args.input_dataset.lower() == 'mnist':
        dataset_type = 'mnist'
    else:
        args.input_dataset = Path(args.input_dataset).resolve()
        if not args.input_dataset.exists():
            raise ValueError(f"Input dataset {args.input_dataset} is not a valid path")
        if not is_bids_dataset(args.input_dataset):
            paths_list = parse_file_list_argument(args.input_dataset,
                                                  recursive_file_search=args.recursive_input_file_search,
                                                  file_types=args.input_file_types,
                                                  arg_separator=args.arg_separator)
            dataset_type = detect_dataset_type(paths_list)
        else:
            # TODO needs to be tested
            paths_list = handle_bids_dataset(args.input_dataset, args.bids_filters, verbose=True)
            dataset_type = 'nifti'
    scores = None
    if dataset_type == 'image':
        min_res = find_min_resolution(paths_list)
        input_matrix = process_images(paths_list, min_res)
        output_format_info = min_res
    elif dataset_type == 'nifti':
        input_matrix = nifti_dataset_to_matrix(paths_list)
        output_format_info = input_matrix.affine
    elif dataset_type == 'mnist':
        mnist_features_normalized, mnist_labels = load_and_preprocess_digits_dataset()
        if not isinstance(mnist_features_normalized, np.ndarray):
            mnist_features_normalized = mnist_features_normalized.to_numpy()
        if not isinstance(mnist_labels, np.ndarray):
            mnist_labels = mnist_labels.to_numpy()
        # convert labels to integers
        mnist_labels = mnist_labels.astype(int)
        input_matrix = mnist_features_normalized
        if mnist_features_normalized[0].shape == (64,):
            output_format_info = (8, 8)
        else:
            output_format_info = mnist_features_normalized[0].shape  # Extracting shape from the first image
        print(f'Shape of output_format_info: {output_format_info}')
    elif dataset_type == 'spreadsheet':
        inputs_df = spreadsheet_to_input_df(args.input_dataset,
                                                header=args.input_header,
                                                index_col=args.input_index_column,
                                                filter_columns_list=args.scores_column,
                                                filter_rows_list=None, # TODO: add this option
                                                columns_are_features=args.columns_as_features)
        input_matrix = inputs_df.values
        output_format_info = input_matrix.shape[1]  # Length of one column in the input_matrix
    else:
        raise ValueError(f"Unsupported dataset type: {dataset_type}")

    # Load scores if provided separately
    if args.scores:
        scores_df = spreadsheet_to_input_df(args.scores,
                                            header=args.scores_header,
                                            index_col=args.scores_index_column,
                                            filter_columns_list=args.scores_column,
                                            filter_rows_list=None, # TODO: add this option
                                            columns_are_features=args.scores_are_columns)
        scores = prepare_scores(scores_df.values, input_matrix.shape[0])
    if dataset_type == 'mnist':
        scores = mnist_labels

    # If the user wants to split the dataset, do so
    if args.command == 'umap' and '--test_size' not in args:
        test_size = 0.0
    else:
        test_size = args.test_size
    if test_size > 0:
        print(f"Splitting the dataset with test size of {test_size}")
    train_features, test_features, train_labels, test_labels = train_test_split(
        input_matrix, scores if scores is not None else None, test_size=test_size, random_state=42)

    # Load pre-trained UMAP model if provided
    if args.command in ['full', 'heatmap', 'clustering', 'prediction'] and args.load_umap:
        umap_model_path = Path(args.load_umap).resolve()
        trained_umap = load_umap_model(umap_model_path)
    elif args.command in ['full', 'umap']:
        # Train UMAP
        trained_umap, embeddings, umap_path, embeddings_path, input_matrix_path = train_and_save_umap_and_embeddings(
            train_features, args.output_folder, pref=args.prefix)
        print(f"UMAP model saved at: {umap_path}")
        print(f"Embeddings saved at: {embeddings_path}")
        print(f"Input matrix saved at: {input_matrix_path}")

    # Load precomputed embeddings if provided
    if args.load_embeddings:
        embeddings = np.load(args.load_embeddings)
    else:
        embeddings = trained_umap.transform(train_features)

    min_embeddings = embeddings.min(axis=0)
    max_embeddings = embeddings.max(axis=0)
    rescaled_embeddings = rescale_embedding(embeddings, preset_min=min_embeddings, preset_max=max_embeddings)

    training_embeddings = rescaled_embeddings

    if test_size > 0:
        test_embeddings = rescale_embedding(trained_umap.transform(test_features), preset_max=max_embeddings,
                                            preset_min=min_embeddings)
    else:
        test_embeddings = None

    # Clustering section
    if args.command in ['full', 'clustering']:
        if args.load_hdbscan:
            clusterer = load_hdbscan_model(args.load_hdbscan)
            cluster_labels = clusterer.labels_
        else:
            # TODO add args.min_cluster_size
            clusterer, cluster_labels = cluster_coordinates(training_embeddings, min_cluster_size=5)
            save_json(args.output_folder / 'cluster_labels.json', cluster_labels.tolist())
            print("Clustering completed and saved.")

        if args.interactive_plot:
            plot_clustering_interactive_with_hover(training_embeddings, cluster_labels,
                                                   output_path=args.output_folder / 'clustering_plot.html',
                                                   show_plot=True,
                                                   return_plot=False)

    # Heatmap analysis
    if args.command in ['full', 'heatmap']:
        # TODO that's if the scores are actually classes and were given in one column, but not if they are continuous
        # and were given in multiple columns
        # TODO implement the new_dataset option
        if args.new_dataset:
            new_dataset = Path(args.new_dataset).resolve()
            if not new_dataset.exists():
                raise ValueError(f"New dataset {new_dataset} is not a valid path")
            if not is_bids_dataset(new_dataset):
                new_paths_list = parse_file_list_argument(new_dataset,
                                                        recursive_file_search=args.recursive_input_file_search,
                                                        file_types=args.input_file_types,
                                                        arg_separator=args.arg_separator)
                new_dataset_type = detect_dataset_type(new_paths_list)
            else:
                new_paths_list = handle_bids_dataset(new_dataset, args.bids_filters, verbose=True)
                new_dataset_type = 'nifti'
            if new_dataset_type == 'image':
                new_input_matrix = process_images(new_paths_list, min_res)
                new_output_format_info = min_res
            elif new_dataset_type == 'nifti':
                new_input_matrix = nifti_dataset_to_matrix(new_paths_list)
                new_output_format_info = new_input_matrix.affine
            elif new_dataset_type == 'spreadsheet':
                new_inputs_df = spreadsheet_to_input_df(args.new_dataset,
                                                        header=args.input_header,
                                                        index_col=args.input_index_column,
                                                        filter_columns_list=args.scores_column,
                                                        filter_rows_list=None, # TODO: add this option
                                                        columns_are_features=args.columns_as_features)
                new_input_matrix = new_inputs_df.values
                new_output_format_info = new_input_matrix.shape[1]

        if args.classification:
            scores_vectors_dict = {
                score_tag: (train_labels == score_tag).astype(int) for score_tag in np.unique(train_labels)
            }
        else:
            scores_vectors_dict = {score_tag: train_labels[score_tag] for score_tag in train_labels}
        run_heatmap_analysis(
            embeddings=training_embeddings,
            scores_vectors_dict=scores_vectors_dict,
            input_matrix=train_features,  # Assuming embeddings are now the input for analysis
            output_folder=args.output_folder,
            clusterer=clusterer,
            cluster_labels=cluster_labels,
            output_format_info=output_format_info,
            grid_size=100,
            sigma=args.sigma if args.sigma else None,
            correlation_threshold=0.3,
            highlight_points=True
        )

    # Prediction section
    if args.command in ['full', 'prediction']:
        train_df = pd.DataFrame(data={'embeddings': [tuple(coord) for coord in training_embeddings]})
        train_df['scores'] = train_labels
        if test_size > 0:
            test_df = pd.DataFrame(data={'embeddings': [tuple(coord) for coord in test_embeddings]})
            test_df['scores'] = test_labels
        else:
            test_df = None

        # TODO if test_embeddings is None, or test_df is None we need to throw an error because it's not implemented
        if test_df is None or test_embeddings is None:
            raise NotImplementedError("Empty test sets are not yet supported.")
        train_and_test_model_per_label(
            train_embeddings=training_embeddings,
            train_labels=train_labels,
            test_embeddings=test_embeddings,
            test_labels=test_labels,
            output_folder=output_folder / 'prediction_models',
        )
        print("Prediction model trained and saved.")


if __name__ == '__main__':
    main()
