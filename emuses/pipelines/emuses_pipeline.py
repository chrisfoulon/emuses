# pipelines/emuses_pipeline.py

import logging
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split

from emuses.pipelines.pipeline_config import PipelineConfig

from bcblib.tools.general_utils import parse_file_list_argument
from bcblib.tools.dataframe_filtering import normalize_dataframe
from bcblib.tools.nifti_utils import load_nifti
from emuses.tools.inputs_utils import (
    detect_dataset_type,
    process_images,
    nifti_dataset_to_matrix,
    load_and_preprocess_digits_dataset,
    prepare_scores,
    spreadsheet_to_input_df,
    is_bids_dataset,
    handle_bids_dataset
)
from emuses.tools.data_preproc import find_min_resolution

class EMUSESPipeline:
    def __init__(self, args):
        self.config = PipelineConfig(args)
        self.args = args
        self.output_folder = self.config.output_folder

        # In classic mode, these come from the main dataset;
        # in label_dataset mode, the labelled dataset is processed separately.
        self.input_matrix = None
        self.scores = None
        self.dataset_type = None
        self.paths_list = None
        self.output_format_info = None

        # For label_dataset mode
        self.labelled_input_matrix = None
        self.labelled_scores = None

        self.stages = []
        self.results = {}
        self.context = {}  # Shared context for data between stages
        self.logger = logging.getLogger(__name__)

        self.validate_args()
        self.format_args()

        # Update context with common settings.
        self.context.update({
            'config': self.config,
            'args': self.args,
            'output_format_info': self.output_format_info,
            'dataset_type': self.dataset_type,
            'output_folder': self.output_folder,
        })
        if self.args.load_embeddings:
            self.context['embeddings'] = np.load(self.args.load_embeddings)
        self.context["cli_args"] = vars(self.args)

    def validate_args(self):
        # Add any necessary validation here.
        pass

    def format_args(self):
        """
        This method handles both modes:
         • Classic mode: Process the main dataset (fully labelled) and split it.
         • Label_dataset mode: Process the unlabelled dataset for UMAP training (no split)
           and process the separate labelled dataset, filtering it by the scores file if requested,
           then split that labelled dataset into train and test parts.
        """
        # Check if label_dataset mode is active.
        if getattr(self.args, 'label_dataset', None):
            self.logger.info("Labelled dataset mode activated.")
            # Process the main (unlabelled) dataset for UMAP/clustering.
            self.input_matrix, self.dataset_type, self.output_format_info, _ = self.process_dataset(
                self.args.input_dataset, is_labelled=False
            )
            # If filtering is requested, load the scores first.
            if getattr(self.args, 'filter_labelled_by_scores', False):
                self.load_and_process_scores(expected_length=None)

                # Then process the labelled dataset with filtering inside process_dataset.
                self.labelled_input_matrix, _, _, _ = self.process_dataset(
                    self.args.label_dataset, is_labelled=True
                )
            else:
                # Otherwise, process the labelled dataset normally and then load scores.
                self.labelled_input_matrix, _, _, _ = self.process_dataset(
                    self.args.label_dataset, is_labelled=True
                )
                self.load_and_process_scores(expected_length=self.labelled_input_matrix.shape[0])

            self.logger.info(f"Main dataset type: {self.dataset_type}")
            # Now split the labelled dataset (and its scores).
            train_mat, test_mat, train_scores, test_scores = train_test_split(
                self.labelled_input_matrix,
                self.scores,
                test_size=self.args.test_size,
                random_state=42
            )
            # Update context with the split labelled data.
            # Also alias these keys to 'train_labels' and 'test_labels' so downstream stages work as before.
            self.context.update({
                'train_labelled_matrix': train_mat,
                'test_labelled_matrix': test_mat,
                'train_labelled_scores': train_scores,
                'test_labelled_scores': test_scores,
                'train_labels': train_scores,  # alias for downstream compatibility
                'test_labels': test_scores,
                'train_features': self.input_matrix,
            })
            self.logger.info("Processed, filtered, and split labelled dataset.")
        else:
            # Classic mode remains unchanged.
            self.input_matrix, self.dataset_type, self.output_format_info, _ = self.process_dataset(
                self.args.input_dataset, is_labelled=False
            )
            self.load_and_process_scores(expected_length=self.input_matrix.shape[0])
            train_features, test_features, train_labels, test_labels = train_test_split(
                self.input_matrix,
                self.scores,
                test_size=self.args.test_size,
                random_state=42
            )
            self.context.update({
                'train_features': train_features,
                'test_features': test_features,
                'train_labels': train_labels,
                'test_labels': test_labels,
            })
            self.logger.info("Processed and split main dataset in classic mode.")

    def process_dataset(self, dataset_identifier, is_labelled=False):
        """
        Process a dataset (given by dataset_identifier) into an input matrix.
        This function supports all datatypes (images, NIfTI, spreadsheet, etc.) handled in classic mode.
        If is_labelled is True, we ignore any embedded scores (because scores will be loaded from a separate file).
        Returns a tuple: (input_matrix, dataset_type, output_format_info, scores)
        For non-mnist types, scores is always None.
        """
        args = self.args
        # Handle special cases: 'mnist' and 'input_matrix'
        if str(dataset_identifier).lower() == 'mnist':
            dataset_type = 'mnist'
            self.paths_list = None
            features, labels = load_and_preprocess_digits_dataset()
            input_matrix = features
            # Only in classic mode (not labelled) do we return the labels
            scores = labels if not is_labelled else None
            output_format_info = (8, 8) if features[0].shape == (64,) else features[0].shape
            return input_matrix, dataset_type, output_format_info, scores
        elif str(dataset_identifier).lower() == 'input_matrix':
            dataset_type = 'input_matrix'
            self.paths_list = None
            input_matrix = np.load(dataset_identifier)
            output_format_info = args.output_format_info
            return input_matrix, dataset_type, output_format_info, None

        # Otherwise, treat dataset_identifier as a file or folder.
        dataset_path = Path(dataset_identifier).resolve()
        if not dataset_path.exists():
            raise ValueError(f"Dataset {dataset_path} is not a valid path")
        # Check for BIDS dataset
        if is_bids_dataset(dataset_path):
            paths_list = handle_bids_dataset(dataset_path, args.bids_filters, verbose=True)
            dataset_type = 'nifti'
        else:
            if dataset_path.is_file():
                dataset_type = detect_dataset_type([dataset_path])
                paths_list = None
            else:
                paths_list = parse_file_list_argument(
                    dataset_path,
                    recursive_file_search=args.recursive_input_file_search,
                    file_types=args.input_file_types,
                    arg_separator=args.arg_separator
                )
                dataset_type = detect_dataset_type(paths_list)

        if dataset_type in ['image', 'nifti'] and is_labelled and getattr(args, 'filter_labelled_by_scores', False):
            # Assume that valid_ids is derived from the scores file.
            # For example, if the scores file's index contains the valid identifiers.
            valid_ids = set(self.context['scores_indices'].astype(str))
            original_count = len(paths_list)
            filtered_paths = []
            for p in paths_list:
                # Find all valid IDs that appear as substrings in the file's stem.
                matches = [vid for vid in valid_ids if vid in Path(p).stem]
                if len(matches) == 1:
                    filtered_paths.append(p)
                elif len(matches) > 1:
                    self.logger.warning(f"File {p} has multiple valid ID matches: {matches}. Skipping file.")
                # If no matches, the file is not included.
            paths_list = filtered_paths
            self.logger.info(
                f"Filtered labelled dataset: {len(paths_list)} of {original_count} files kept based on scores file.")

        # Process according to dataset type.
        if dataset_type == 'image':
            min_res = find_min_resolution(paths_list)
            input_matrix = process_images(paths_list, min_res)
            output_format_info = min_res
        elif dataset_type == 'nifti':
            input_matrix = nifti_dataset_to_matrix(paths_list)
            first_image = load_nifti(paths_list[0])
            output_shape = first_image.shape
            output_affine = first_image.affine
            output_format_info = (output_shape, output_affine)
        elif dataset_type in ['spreadsheet', 'tabular']:
            inputs_df = spreadsheet_to_input_df(
                dataset_path,
                header=args.input_header,
                index_col=args.input_index_column,
                filter_columns_list=args.inputs_columns,
                filter_rows_list=None,
                columns_are_features=args.columns_are_features
            )
            if args.input_normalization and args.input_normalization.lower() != 'none':
                self.logger.info(f"Normalizing dataset with method={args.input_normalization}")
                before_shape = inputs_df.shape
                inputs_df = normalize_dataframe(inputs_df, method=args.input_normalization)
                after_shape = inputs_df.shape
                if after_shape != before_shape:
                    self.logger.warning(
                        f"DataFrame shape changed after normalization: from {before_shape} to {after_shape}."
                    )
            input_matrix = inputs_df.values
            output_format_info = list(inputs_df.columns)
        else:
            raise ValueError(f"Unsupported dataset type: {dataset_type}")
        # For non-mnist data, we always return scores as None (scores are loaded from a separate file)
        return input_matrix, dataset_type, output_format_info, None

    def load_and_process_scores(self, expected_length=None):
        """
        Load scores from a separate scores file.
        If expected_length is provided, validate that the scores array has that many observations.
        (Scores are always provided via a spreadsheet.)
        """
        args = self.args
        if getattr(args, 'scores', None):
            scores_df = spreadsheet_to_input_df(
                args.scores,
                header=args.scores_header,
                index_col=args.scores_index_column,
                filter_columns_list=args.scores_column,
                filter_rows_list=None,
                columns_are_features=not args.scores_are_rows
            )
            if args.scores_normalization and args.scores_normalization.lower() != 'none':
                self.logger.info(f"Normalizing scores dataframe with method={args.scores_normalization}")
                before_shape = scores_df.shape
                scores_df = normalize_dataframe(scores_df, method=args.scores_normalization)
                after_shape = scores_df.shape
                if after_shape != before_shape:
                    self.logger.warning(
                        f"Scores DataFrame shape changed after normalization: from {before_shape} to {after_shape}."
                    )
            self.scores = prepare_scores(scores_df.values, match_length=expected_length)
            self.context['scores'] = self.scores
            self.context['scores_indices'] = scores_df.index

    def split_dataset(self):
        """
        In classic mode, split the main dataset into training and test sets.
        In label_dataset mode, splitting is handled in format_args() so this function does nothing.
        """
        if getattr(self.args, 'label_dataset', None):
            return

        args = self.args
        test_size = getattr(args, 'test_size', 0.0)
        if test_size > 0:
            self.logger.info(f"Splitting the main dataset with test size of {test_size}")
            train_features, test_features, train_labels, test_labels = train_test_split(
                self.input_matrix,
                self.scores if self.scores is not None else None,
                test_size=test_size,
                random_state=42
            )
            split_folder = self.output_folder / "split_dataset"
            split_folder.mkdir(parents=True, exist_ok=True)
            np.save(split_folder / "train_features.npy", train_features)
            np.save(split_folder / "test_features.npy", test_features)
            np.save(split_folder / "train_labels.npy", train_labels)
            np.save(split_folder / "test_labels.npy", test_labels)
            self.context.update({
                'train_features': train_features,
                'test_features': test_features,
                'train_labels': train_labels,
                'test_labels': test_labels,
            })
        else:
            self.context.update({
                'train_features': self.input_matrix,
                'train_labels': self.scores,
                'test_features': None,
                'test_labels': None,
            })

    def add_stage(self, stage):
        self.stages.append(stage)

    def run(self, progress_callback=None, progress_queue=None):
        total_stages = len(self.stages)
        for i, stage in enumerate(self.stages):
            if progress_callback:
                progress = i / total_stages
                progress_callback(stage_name=stage.__class__.__name__, progress=progress)
            stage.run(self.context, progress_queue=progress_queue)
            if progress_callback:
                progress = (i + 1) / total_stages
                progress_callback(stage_name=stage.__class__.__name__, progress=progress)
