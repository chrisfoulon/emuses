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
            print(f"Loaded embeddings from {self.args.load_embeddings} with shape {self.context['embeddings'].shape}")
        self.context["cli_args"] = vars(self.args)

    def validate_args(self):
        # Add any necessary validation here.
        pass

    def format_args(self):
        """
        Process the dataset based on the mode and update context.
        For label_dataset mode:
          - Process both the main (unlabelled) dataset for UMAP/clustering and the separate labelled dataset.
        For classic mode:
          - Process the main (fully labelled) dataset.
        Then, call split_dataset() to perform the splitting, save the files, and update the context.
        """
        if getattr(self.args, 'label_dataset', None):
            self.logger.info("Labelled dataset mode activated.")
            self.input_matrix, self.dataset_type, self.output_format_info, _ = self.process_dataset(
                self.args.input_dataset, is_labelled=False
            )
            if getattr(self.args, 'filter_labelled_by_scores', False):
                self.load_and_process_scores(expected_length=None)
                self.labelled_input_matrix, _, _, _ = self.process_dataset(
                    self.args.label_dataset, is_labelled=True
                )
            else:
                self.labelled_input_matrix, _, _, _ = self.process_dataset(
                    self.args.label_dataset, is_labelled=True
                )
                self.load_and_process_scores(expected_length=self.labelled_input_matrix.shape[0])
            self.logger.info(f"Main dataset type: {self.dataset_type}")
        else:
            self.input_matrix, self.dataset_type, self.output_format_info, scores = self.process_dataset(
                self.args.input_dataset, is_labelled=False
            )
            if scores is not None:
                self.scores = scores
            else:
                self.load_and_process_scores(expected_length=self.input_matrix.shape[0])
        # After processing the datasets, perform the splitting:
        self.split_dataset()


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
            # Use the stored DataFrame directly.
            scores_df = self.context['scores_df']
            # Derive valid IDs from the DataFrame index.
            valid_ids = set(scores_df.index.astype(str))
            original_count = len(paths_list)
            filtered_paths = []
            matched_ids_list = []  # Record the matched valid ID for each accepted file

            for p in paths_list:
                # Find all valid IDs that appear in the file's stem or name.
                matches = [vid for vid in valid_ids if vid in Path(p).stem or vid in Path(p).name]
                if len(matches) == 1:
                    vid = matches[0]
                    # If scores_column is specified, check if all score values are missing.
                    if hasattr(args, 'scores_column') and args.scores_column:
                        score_row = scores_df.loc[vid]
                        if score_row[args.scores_column].isna().all():
                            self.logger.warning(
                                f"File {p} (ID: {vid}) has no score value in any of the specified columns. "
                                f"Dropping file."
                            )
                            continue  # Skip this file if all values are missing
                    filtered_paths.append(p)
                    matched_ids_list.append(vid)
                elif len(matches) > 1:
                    self.logger.warning(f"File {p} has multiple valid ID matches: {matches}. Skipping file.")
                # Files with no matches are simply ignored.

            paths_list = filtered_paths
            # Reindex the scores DataFrame so that it contains only rows for the matched IDs,
            # ensuring that the order and number of rows exactly match the filtered files.
            filtered_scores_df = scores_df.loc[matched_ids_list].copy()
            if len(filtered_scores_df) != len(paths_list):
                self.logger.warning(
                    f"After reindexing, there is a mismatch: {len(filtered_scores_df)} observations in scores vs {len(paths_list)} files."
                )
            else:
                self.logger.info(
                    f"Scores successfully reindexed to match filtered files: {len(filtered_scores_df)} observations."
                )
            # Update both the context and the pipeline's self.scores attribute.
            self.context['scores_df'] = filtered_scores_df
            self.context['scores'] = prepare_scores(filtered_scores_df)
            self.context['scores_indices'] = filtered_scores_df.index
            self.scores = prepare_scores(filtered_scores_df)  # Ensure self.scores matches the filtered scores

            self.logger.info(
                f"Filtered labelled dataset: {len(paths_list)} of {original_count} files kept based on scores file."
            )
            print(f"Filtered labelled dataset: {len(paths_list)} of {original_count} files kept based on scores file.")


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

                # Compute scaling factors for the training dataset or apply precomputed ones
                if not is_labelled:
                    inputs_df, scaling_factors = normalize_dataframe(inputs_df, method=args.input_normalization)
                    self.context['input_scaling_factors'] = scaling_factors
                else:
                    scaling_factors = self.context.get('input_scaling_factors', None)
                    if scaling_factors is None:
                        raise ValueError("Scaling factors are missing for labelled dataset normalization.")
                    inputs_df, _ = normalize_dataframe(inputs_df, method=args.input_normalization, scaling_factors=scaling_factors)

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
                filter_columns_list=args.scores_column
                if args.scores_column is None or isinstance(args.scores_column, list) else [args.scores_column],
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
            # TODO handle the case where we change the size of the scores_df with expected_length
            # Check if the scores_df index matches the input_matrix index
            if expected_length is not None:
                if len(scores_df) != expected_length:
                    raise ValueError(
                        f"Scores file has {len(scores_df)} rows, but expected {expected_length} rows."
                    )
            self.context['scores_df'] = scores_df
            self.context['scores'] = self.scores
            self.context['scores_indices'] = scores_df.index

    def split_dataset(self):
        """
        Splits the dataset and updates self.context with train and test sets,
        handling the special case when test_size is set to 0.

        In label_dataset mode:
          - Process the labelled dataset (and its scores) and split it if test_size > 0.
          - If test_size==0, use the entire labelled dataset for training.
          - Save the splits (if any) in the 'split_dataset' folder.
          - Update context with keys 'train_labelled_matrix', 'test_labelled_matrix',
            'train_labelled_scores', 'test_labelled_scores' and aliases 'train_labels' and 'test_labels'.
          - Also update 'train_features' using the main (unlabelled) dataset.

        In classic mode:
          - Splits self.input_matrix and self.scores if test_size > 0.
          - If test_size==0, use the entire input data as the training set.
          - Saves the splits and updates context with 'train_features', 'test_features', 'train_labels', and 'test_labels'.
        """
        args = self.args
        test_size = getattr(args, 'test_size', 0.2)
        split_folder = self.output_folder / "split_dataset"
        split_folder.mkdir(parents=True, exist_ok=True)

        if getattr(args, 'label_dataset', None):
            self.logger.info("Splitting labelled dataset (label_dataset mode).")
            # Assume self.labelled_input_matrix and self.scores are already available.
            if test_size == 0:
                # Use the entire labelled dataset for training.
                train_mat = self.labelled_input_matrix
                train_scores = self.scores
                test_mat = None
                test_scores = None
            else:
                train_mat, test_mat, train_scores, test_scores = train_test_split(
                    self.labelled_input_matrix,
                    self.scores,
                    test_size=test_size,
                    random_state=42
                )
                np.save(split_folder / "test_labelled_matrix.npy", test_mat)
                np.save(split_folder / "test_labelled_scores.npy", test_scores)
            np.save(split_folder / "train_labelled_matrix.npy", train_mat)
            np.save(split_folder / "train_labelled_scores.npy", train_scores)
            self.context.update({
                'train_labelled_matrix': train_mat,
                'test_labelled_matrix': test_mat,
                'train_labelled_scores': train_scores,
                'test_labelled_scores': test_scores,
                'train_labels': train_scores,  # alias for downstream compatibility
                'test_labels': test_scores,
                'train_features': self.input_matrix,  # unlabelled data used for UMAP/clustering
            })
            self.logger.info("Labelled dataset split and context updated for label_dataset mode.")
        else:
            self.logger.info("Splitting main dataset (classic mode).")
            if test_size == 0:
                # Use entire input for training.
                train_features = self.input_matrix
                train_labels = self.scores
                test_features = None
                test_labels = None
            else:
                train_features, test_features, train_labels, test_labels = train_test_split(
                    self.input_matrix,
                    self.scores,
                    test_size=test_size,
                    random_state=42
                )
                np.save(split_folder / "test_features.npy", test_features)
                np.save(split_folder / "test_labels.npy", test_labels)
            np.save(split_folder / "train_features.npy", train_features)
            np.save(split_folder / "train_labels.npy", train_labels)
            self.context.update({
                'train_features': train_features,
                'test_features': test_features,
                'train_labels': train_labels,
                'test_labels': test_labels,
            })
            self.logger.info("Main dataset split and context updated for classic mode.")

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
