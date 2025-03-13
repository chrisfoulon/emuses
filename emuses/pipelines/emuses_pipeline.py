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

        # In classic mode these come from the main dataset;
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
           and process the separate labelled dataset (with scores coming from a separate scores file),
           then split that labelled dataset into train and test parts.
        """
        # Check if label_dataset mode is active.
        if getattr(self.args, 'label_dataset', None):
            self.logger.info("Labelled dataset mode activated.")
            # Process the main (unlabelled) dataset for UMAP/clustering.
            self.input_matrix, self.dataset_type, self.output_format_info, _ = self.process_main_dataset()
            # Process the separate labelled dataset (we use the same processing as for spreadsheets, etc.)
            self.labelled_input_matrix, _, _, _ = self.process_labelled_dataset()
            self.logger.info(f"Main dataset type: {self.dataset_type}")
            # Now load scores from the scores file using the shape of the labelled dataset.
            self.load_and_process_scores(labelled=True)
            # Split the labelled dataset (and its scores) using --test_size.
            train_mat, test_mat, train_scores, test_scores = train_test_split(
                self.labelled_input_matrix,
                self.scores,  # self.scores was set using the labelled dataset shape.
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
                'train_labels': train_scores,
                'test_labels': test_scores,
            })
            self.logger.info("Processed and split labelled dataset.")
        else:
            # Classic mode: Process the main dataset (which is fully labelled) and split it.
            self.input_matrix, self.dataset_type, self.output_format_info, _ = self.process_main_dataset()
            self.load_and_process_scores(labelled=False)
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

    def process_main_dataset(self):
        """
        Process the main dataset (args.input_dataset) and return a tuple:
        (input_matrix, dataset_type, output_format_info, scores)
        In classic mode, the dataset is expected to be fully labelled.
        In label_dataset mode, this dataset is used as unlabelled data for UMAP training.
        """
        args = self.args
        if str(args.input_dataset).lower() == 'mnist':
            self.dataset_type = 'mnist'
            self.paths_list = None
            mnist_features_normalized, mnist_labels = load_and_preprocess_digits_dataset()
            input_matrix = mnist_features_normalized
            scores = mnist_labels
            if mnist_features_normalized[0].shape == (64,):
                output_format_info = (8, 8)
            else:
                output_format_info = mnist_features_normalized[0].shape
            return input_matrix, self.dataset_type, output_format_info, scores
        elif str(args.input_dataset).lower() == 'input_matrix':
            self.dataset_type = 'input_matrix'
            self.paths_list = None
            input_matrix = np.load(args.input_dataset)
            output_format_info = args.output_format_info
            return input_matrix, self.dataset_type, output_format_info, None
        else:
            args.input_dataset = Path(args.input_dataset).resolve()
            if not args.input_dataset.exists():
                raise ValueError(f"Input dataset {args.input_dataset} is not a valid path")
            if not is_bids_dataset(args.input_dataset):
                if args.input_dataset.is_file():
                    self.dataset_type = detect_dataset_type([args.input_dataset])
                else:
                    self.paths_list = parse_file_list_argument(
                        args.input_dataset,
                        recursive_file_search=args.recursive_input_file_search,
                        file_types=args.input_file_types,
                        arg_separator=args.arg_separator
                    )
                    self.dataset_type = detect_dataset_type(self.paths_list)
            else:
                self.paths_list = handle_bids_dataset(args.input_dataset, args.bids_filters, verbose=True)
                self.dataset_type = 'nifti'

            if self.dataset_type == 'image':
                min_res = find_min_resolution(self.paths_list)
                input_matrix = process_images(self.paths_list, min_res)
                output_format_info = min_res
            elif self.dataset_type == 'nifti':
                input_matrix = nifti_dataset_to_matrix(self.paths_list)
                output_format_info = load_nifti(self.paths_list[0]).affine
            elif self.dataset_type in ['spreadsheet', 'tabular']:
                # For spreadsheets, we assume the file contains all the data.
                inputs_df = spreadsheet_to_input_df(
                    args.input_dataset,
                    header=args.input_header,
                    index_col=args.input_index_column,
                    filter_columns_list=args.inputs_columns,
                    filter_rows_list=None,
                    columns_are_features=args.columns_are_features
                )
                if args.input_normalization and args.input_normalization.lower() != 'none':
                    self.logger.info(f"Normalizing input dataframe with method={args.input_normalization}")
                    before_shape = inputs_df.shape
                    inputs_df = normalize_dataframe(inputs_df, method=args.input_normalization)
                    after_shape = inputs_df.shape
                    if after_shape != before_shape:
                        self.logger.warning(
                            f"Input DataFrame shape changed after normalization (unexpected). "
                            f"Shape changed from {before_shape} to {after_shape}."
                        )
                input_matrix = inputs_df.values
                output_format_info = list(inputs_df.columns)
            else:
                raise ValueError(f"Unsupported dataset type: {self.dataset_type}")
            return input_matrix, self.dataset_type, output_format_info, None

    def process_labelled_dataset(self):
        """
        Process the separate labelled dataset (args.label_dataset) into an input matrix.
        In this mode the dataset is assumed to be a spreadsheet that already contains scores,
        but we ignore the scores here (they will come from a separate scores file).
        We return (input_matrix, dataset_type, output_format_info, None).
        """
        args = self.args
        label_dataset_path = Path(args.label_dataset).resolve()
        if not label_dataset_path.exists():
            raise ValueError(f"Labelled dataset {label_dataset_path} is not a valid path")
        if label_dataset_path.suffix in ['.csv', '.xlsx', '.xls']:
            labelled_df = spreadsheet_to_input_df(
                label_dataset_path,
                header=args.input_header,
                index_col=args.input_index_column,
                filter_columns_list=args.inputs_columns,
                columns_are_features=args.columns_are_features
            )
            # Here we assume that the labelled dataset already has its scores in the last column,
            # but because the scores are loaded separately from --scores, we ignore them here.
            input_matrix = labelled_df.values[:, :]  # keep all columns (features only)
            output_format_info = list(labelled_df.columns)
            return input_matrix, 'spreadsheet', output_format_info, None
        else:
            raise NotImplementedError("Labelled dataset type not implemented yet.")

    def load_and_process_scores(self, labelled=False):
        """
        Load scores from a separate scores file.
        If labelled is True, use the shape of the labelled dataset; otherwise, use the main dataset.
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
            # In label_dataset mode, associate scores with the labelled dataset.
            if labelled and self.labelled_input_matrix is not None:
                self.scores = prepare_scores(scores_df.values, self.labelled_input_matrix.shape)
            else:
                self.scores = prepare_scores(scores_df.values, self.input_matrix.shape)
            self.context['scores'] = self.scores

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
