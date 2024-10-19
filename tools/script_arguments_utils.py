# emuses_pipeline.py

import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from bcblib.tools.general_utils import open_json, parse_file_list_argument, save_json
from bcblib.tools.nifti_utils import load_nifti

from tools.UMAP_utils import train_and_save_umap_and_embeddings, load_umap_model
from tools.clustering_utils import load_hdbscan_model, save_hdbscan_model, cluster_coordinates
from tools.inputs_utils import (
    detect_dataset_type,
    process_images,
    nifti_dataset_to_matrix,
    load_and_preprocess_digits_dataset,
    prepare_scores,
    spreadsheet_to_input_df,
    is_bids_dataset,
    handle_bids_dataset
)
from tools.data_preproc import find_min_resolution
from tools.visualisation import plot_clustering_interactive_with_hover
from tools.correlation_maps_utils import run_heatmap_analysis
from tools.stats_utils import train_and_test_model_per_label
from tools.emuses_utils import rescale_embedding


class EMUSESPipeline:
    def __init__(self, args):
        self.args = args
        self.output_folder = None
        self.output_format_info = None
        self.dataset_type = None
        self.paths_list = None
        self.input_matrix = None
        self.scores = None
        self.train_features = None
        self.test_features = None
        self.train_labels = None
        self.test_labels = None
        self.trained_umap = None
        self.embeddings = None
        self.test_embeddings = None
        self.clusterer = None
        self.cluster_labels = None
        self.min_embeddings = None
        self.max_embeddings = None
        self.umap_model_path = None
        self.embeddings_path = None
        self.test_embeddings_path = None  # New attribute for storing test embeddings path
        self.input_matrix_path = None

        self.validate_args()
        self.format_args()

    def validate_args(self):
        """
        Validate the arguments provided to the pipeline.
        """
        # Validate the output folder
        self.output_folder = Path(self.args.output_folder).resolve()
        self.output_folder.mkdir(parents=True, exist_ok=True)
        if not self.output_folder.is_dir():
            raise ValueError(f"Output folder {self.output_folder} is not a valid path")

        # Save the arguments to a log file
        os.makedirs(self.output_folder / 'log', exist_ok=True)
        dict_args = vars(self.args)
        dict_args['datetime'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_json(self.output_folder / 'log' / f'arguments_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.json',
                  dict_args)

        # Additional validations can be added here as needed
        # For example, check that required arguments are provided
        if self.args.command in ['full', 'umap', 'prediction'] and not self.args.input_dataset:
            raise ValueError("Input dataset is required for the selected command.")

    def format_args(self):
        """
        Format the arguments into inputs for the main functions.
        """
        # Process the input dataset
        if str(self.args.input_dataset).lower() == 'mnist':
            self.dataset_type = 'mnist'
            self.paths_list = None
        elif str(self.args.input_dataset).lower() == 'input_matrix':
            self.dataset_type = 'input_matrix'
            self.paths_list = None
        else:
            self.args.input_dataset = Path(self.args.input_dataset).resolve()
            if not self.args.input_dataset.exists():
                raise ValueError(f"Input dataset {self.args.input_dataset} is not a valid path")
            if not is_bids_dataset(self.args.input_dataset):
                self.paths_list = parse_file_list_argument(
                    self.args.input_dataset,
                    recursive_file_search=self.args.recursive_input_file_search,
                    file_types=self.args.input_file_types,
                    arg_separator=self.args.arg_separator
                )
                self.dataset_type = detect_dataset_type(self.paths_list)
            else:
                # TODO: Needs to be tested
                self.paths_list = handle_bids_dataset(self.args.input_dataset, self.args.bids_filters, verbose=True)
                self.dataset_type = 'nifti'

        # Process the input matrix based on dataset type
        if self.dataset_type == 'image':
            min_res = find_min_resolution(self.paths_list)
            self.input_matrix = process_images(self.paths_list, min_res)
            self.output_format_info = min_res
        elif self.dataset_type == 'nifti':
            self.input_matrix = nifti_dataset_to_matrix(self.paths_list)
            self.output_format_info = load_nifti(self.paths_list[0]).affine
        elif self.dataset_type == 'mnist':
            mnist_features_normalized, mnist_labels = load_and_preprocess_digits_dataset()
            if not isinstance(mnist_features_normalized, np.ndarray):
                mnist_features_normalized = mnist_features_normalized.to_numpy()
            if not isinstance(mnist_labels, np.ndarray):
                mnist_labels = mnist_labels.to_numpy()
            # Convert labels to integers
            mnist_labels = mnist_labels.astype(int)
            self.input_matrix = mnist_features_normalized
            if mnist_features_normalized[0].shape == (64,):
                self.output_format_info = (8, 8)
            else:
                self.output_format_info = mnist_features_normalized[0].shape
            self.scores = mnist_labels
        elif self.dataset_type in ['spreadsheet', 'tabular']:
            inputs_df = spreadsheet_to_input_df(
                self.args.input_dataset,
                header=self.args.input_header,
                index_col=self.args.input_index_column,
                filter_columns_list=self.args.inputs_columns,
                filter_rows_list=None,  # TODO: add this option
                columns_are_features=self.args.columns_as_features
            )
            self.input_matrix = inputs_df.values
            self.output_format_info = self.input_matrix.shape[1]
        elif self.dataset_type == 'input_matrix':
            self.input_matrix = np.load(self.args.input_dataset)
            self.output_format_info = self.args.output_format_info
        else:
            raise ValueError(f"Unsupported dataset type: {self.dataset_type}")

        # Load scores if provided separately
        if self.args.scores:
            scores_df = spreadsheet_to_input_df(
                self.args.scores,
                header=self.args.scores_header,
                index_col=self.args.scores_index_column,
                filter_columns_list=self.args.scores_column,
                filter_rows_list=None,  # TODO: add this option
                columns_are_features=self.args.scores_are_columns
            )
            self.scores = prepare_scores(scores_df.values, self.input_matrix.shape[0])

        # Handle test size and split the dataset
        test_size = getattr(self.args, 'test_size', 0.0)
        if test_size > 0:
            print(f"Splitting the dataset with test size of {test_size}")
            self.train_features, self.test_features, self.train_labels, self.test_labels = train_test_split(
                self.input_matrix,
                self.scores if self.scores is not None else None,
                test_size=test_size,
                random_state=42
            )
        else:
            self.train_features = self.input_matrix
            self.train_labels = self.scores
            self.test_features = None
            self.test_labels = None

    def run(self):
        """
        Run the pipeline based on the command.
        """
        if self.args.command == 'full':
            self.run_full_pipeline()
        elif self.args.command == 'umap':
            self.run_umap()
        elif self.args.command == 'clustering':
            self.run_clustering()
        elif self.args.command == 'heatmap':
            self.run_heatmap()
        elif self.args.command == 'prediction':
            self.run_prediction()
        else:
            raise ValueError(f"Unknown command: {self.args.command}")

    def run_full_pipeline(self):
        """
        Run the full EMUSES pipeline.
        """
        self.run_umap()
        self.run_clustering()
        self.run_heatmap()
        self.run_prediction()

    def run_umap(self):
        """
        Train and save UMAP model and embeddings.
        """
        # Load pre-trained UMAP model if provided
        if getattr(self.args, 'load_umap', None):
            self.umap_model_path = Path(self.args.load_umap).resolve()
            self.trained_umap, _ = load_umap_model(self.umap_model_path)
            print(f"Loaded pre-trained UMAP model from: {self.umap_model_path}")
        else:
            # Train UMAP
            self.trained_umap, embeddings, umap_path, embeddings_path, input_matrix_path = train_and_save_umap_and_embeddings(
                self.train_features,
                self.output_folder,
                pref=self.args.prefix
            )
            self.umap_model_path = umap_path
            self.embeddings_path = embeddings_path
            self.input_matrix_path = input_matrix_path
            print(f"UMAP model saved at: {umap_path}")
            print(f"Embeddings saved at: {embeddings_path}")
            print(f"Input matrix saved at: {input_matrix_path}")

        # Load precomputed embeddings if provided
        if getattr(self.args, 'load_embeddings', None):
            self.embeddings = np.load(self.args.load_embeddings)
            print(f"Loaded precomputed embeddings from: {self.args.load_embeddings}")
        else:
            self.embeddings = self.trained_umap.transform(self.train_features)

        # Rescale embeddings
        self.min_embeddings = self.embeddings.min(axis=0)
        self.max_embeddings = self.embeddings.max(axis=0)
        self.embeddings = rescale_embedding(self.embeddings, preset_min=self.min_embeddings, preset_max=self.max_embeddings)

        # Process test embeddings if test set exists
        if self.test_features is not None:
            self.test_embeddings = self.trained_umap.transform(self.test_features)
            self.test_embeddings = rescale_embedding(
                self.test_embeddings,
                preset_min=self.min_embeddings,
                preset_max=self.max_embeddings
            )
            # Save test embeddings
            self.test_embeddings_path = self.output_folder / 'test_embeddings.npy'
            np.save(self.test_embeddings_path, self.test_embeddings)
            print(f"Test embeddings saved at: {self.test_embeddings_path}")

    def run_clustering(self):
        """
        Perform clustering on embeddings.
        """
        # Load pre-trained HDBSCAN model if provided
        if getattr(self.args, 'load_hdbscan', None):
            self.clusterer = load_hdbscan_model(self.args.load_hdbscan)
            self.cluster_labels = self.clusterer.labels_
            print(f"Loaded pre-trained HDBSCAN model from: {self.args.load_hdbscan}")
        else:
            min_cluster_size = getattr(self.args, 'min_cluster_size', 5)
            self.clusterer, self.cluster_labels = cluster_coordinates(
                self.embeddings,
                min_cluster_size=min_cluster_size
            )
            # Save clustering labels
            save_json(self.output_folder / 'cluster_labels.json', self.cluster_labels.tolist())
            # Save the HDBSCAN model
            save_hdbscan_model(self.clusterer, self.output_folder, prefix=self.args.prefix)
            print("Clustering completed and saved.")

        if getattr(self.args, 'interactive_plot', False):
            plot_clustering_interactive_with_hover(
                self.embeddings,
                self.cluster_labels,
                output_path=self.output_folder / 'clustering_plot.html',
                show_plot=True,
                return_plot=False
            )

    def run_heatmap(self):
        """
        Run heatmap analysis.
        """
        if self.clusterer is None and not getattr(self.args, 'load_hdbscan', None):
            raise ValueError("Clustering is required for heatmap analysis.")

        if self.clusterer is None:
            self.clusterer = load_hdbscan_model(self.args.load_hdbscan)
            self.cluster_labels = self.clusterer.labels_

        if getattr(self.args, 'classification', False):
            unique_labels = np.unique(self.train_labels)
            scores_vectors_dict = {
                str(score_tag): (self.train_labels == score_tag).astype(int)
                for score_tag in unique_labels
            }
        else:
            # Assuming continuous scores
            if self.train_labels.ndim == 1:
                scores_vectors_dict = {'score': self.train_labels}
            else:
                scores_vectors_dict = {
                    f"score_{i}": self.train_labels[:, i]
                    for i in range(self.train_labels.shape[1])
                }

        run_heatmap_analysis(
            embeddings=self.embeddings,
            scores_vectors_dict=scores_vectors_dict,
            input_matrix=self.train_features,
            output_folder=self.output_folder,
            clusterer=self.clusterer,
            cluster_labels=self.cluster_labels,
            output_format_info=self.output_format_info,
            grid_size=100,
            sigma=self.args.sigma if self.args.sigma else None,
            correlation_threshold=0.3,
            highlight_points=True
        )

    def run_prediction(self):
        """
        Train and test prediction models.
        """
        if self.train_labels is None or self.test_labels is None:
            raise ValueError("Both training and test labels are required for prediction.")

        train_embeddings = self.embeddings
        test_embeddings = self.test_embeddings

        if train_embeddings is None or test_embeddings is None:
            raise ValueError("Both training and test embeddings are required for prediction.")

        if getattr(self.args, 'classification', False):
            # Classification
            train_and_test_model_per_label(
                train_embeddings=train_embeddings,
                train_labels=self.train_labels,
                test_embeddings=test_embeddings,
                test_labels=self.test_labels,
                output_folder=self.output_folder / 'prediction_models',
            )
            print("Classification model trained and saved.")
        else:
            # Regression (Not implemented in the original code)
            raise NotImplementedError("Regression prediction is not implemented yet.")
