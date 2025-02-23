# pipelines/emuses_pipeline.py

import logging
import numpy as np
from pathlib import Path

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
from sklearn.model_selection import train_test_split

class EMUSESPipeline:
    def __init__(self, args):
        self.config = PipelineConfig(args)
        self.args = args
        self.output_folder = self.config.output_folder
        self.dataset_type = None
        self.paths_list = None
        self.input_matrix = None
        self.scores = None
        self.output_format_info = None
        self.stages = []
        self.results = {}
        self.context = {}  # Shared context for data between stages
        self.logger = logging.getLogger(__name__)

        self.validate_args()
        self.format_args()

        # Initialize context with initial data
        self.context.update({
            'config': self.config,
            'args': self.args,
            'input_matrix': self.input_matrix,
            'scores': self.scores,
            'output_format_info': self.output_format_info,
            'dataset_type': self.dataset_type,
            'output_folder': self.output_folder,
        })
        # Load embeddings if provided
        if args.load_embeddings:
            self.context['embeddings'] = np.load(args.load_embeddings)

    def validate_args(self):
        # Validation logic if needed
        pass

    def format_args(self):
        # Process input dataset
        self.process_input_dataset()
        # Load and process scores
        self.load_and_process_scores()
        # Split dataset
        self.split_dataset()

    def process_input_dataset(self):
        args = self.args
        if str(args.input_dataset).lower() == 'mnist':
            self.dataset_type = 'mnist'
            self.paths_list = None
            mnist_features_normalized, mnist_labels = load_and_preprocess_digits_dataset()
            self.input_matrix = mnist_features_normalized
            self.scores = mnist_labels
            if mnist_features_normalized[0].shape == (64,):
                self.output_format_info = (8, 8)
            else:
                self.output_format_info = mnist_features_normalized[0].shape
        elif str(args.input_dataset).lower() == 'input_matrix':
            self.dataset_type = 'input_matrix'
            self.paths_list = None
            self.input_matrix = np.load(args.input_dataset)
            self.output_format_info = args.output_format_info
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
                # Handle BIDS dataset
                self.paths_list = handle_bids_dataset(args.input_dataset, args.bids_filters, verbose=True)
                self.dataset_type = 'nifti'

            # Process the input matrix based on dataset type
            if self.dataset_type == 'image':
                min_res = find_min_resolution(self.paths_list)
                self.input_matrix = process_images(self.paths_list, min_res)
                self.output_format_info = min_res
            elif self.dataset_type == 'nifti':
                self.input_matrix = nifti_dataset_to_matrix(self.paths_list)
                self.output_format_info = load_nifti(self.paths_list[0]).affine
            elif self.dataset_type in ['spreadsheet', 'tabular']:
                if args.input_file_types is None:
                    inputs_df = spreadsheet_to_input_df(
                        args.input_dataset,
                        header=args.input_header,
                        index_col=args.input_index_column,
                        filter_columns_list=args.inputs_columns,
                        filter_rows_list=None,  # TODO: add this option
                        columns_are_features=args.columns_as_features
                    )

                    # Apply normalization if requested
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

                    self.input_matrix = inputs_df.values
                    self.output_format_info = list(inputs_df.columns)
                    self.paths_list = None
                    # TODO add a way to detect files in the spreadsheet
            else:
                raise ValueError(f"Unsupported dataset type: {self.dataset_type}")

        # Update context with input data
        self.context.update({
            'input_matrix': self.input_matrix,
            'output_format_info': self.output_format_info,
            'dataset_type': self.dataset_type,
        })

    def load_and_process_scores(self):
        args = self.args
        if getattr(args, 'scores', None):
            scores_df = spreadsheet_to_input_df(
                args.scores,
                header=args.scores_header,
                index_col=args.scores_index_column,
                filter_columns_list=args.scores_column,
                filter_rows_list=None,  # TODO: add this option
                columns_are_features=not args.scores_are_rows
            )

            if args.scores_normalization and args.scores_normalization.lower() != 'none':
                self.logger.info(f"Normalizing scores dataframe with method={args.scores_normalization}")
                before_shape = scores_df.shape
                scores_df = normalize_dataframe(scores_df, method=args.scores_normalization)
                after_shape = scores_df.shape
                if after_shape != before_shape:
                    self.logger.warning(
                        f"Scores DataFrame shape changed after normalization (unexpected). "
                        f"Shape changed from {before_shape} to {after_shape}."
                    )

            self.scores = prepare_scores(scores_df.values, self.input_matrix.shape)

            # Update context with scores
            self.context['scores'] = self.scores

    def split_dataset(self):
        args = self.args
        test_size = getattr(args, 'test_size', 0.0)
        if test_size > 0:
            self.logger.info(f"Splitting the dataset with test size of {test_size}")
            train_features, test_features, train_labels, test_labels = train_test_split(
                self.input_matrix,
                self.scores if self.scores is not None else None,
                test_size=test_size,
                # TODO change that
                # random_state=42
            )

            # Create the split_dataset subfolder
            split_folder = self.output_folder / "split_dataset"
            split_folder.mkdir(parents=True, exist_ok=True)

            # Save the splits
            np.save(split_folder / "train_features.npy", train_features)
            np.save(split_folder / "test_features.npy", test_features)
            np.save(split_folder / "train_labels.npy", train_labels)
            np.save(split_folder / "test_labels.npy", test_labels)
        else:
            train_features = self.input_matrix
            train_labels = self.scores
            test_features = None
            test_labels = None

        # Update context with split data
        self.context.update({
            'train_features': train_features,
            'test_features': test_features,
            'train_labels': train_labels,
            'test_labels': test_labels,
        })

    def add_stage(self, stage):
        self.stages.append(stage)

    def run(self, progress_callback=None, progress_queue=None):
        total_stages = len(self.stages)
        for i, stage in enumerate(self.stages):
            # Update progress before running the stage
            if progress_callback:
                progress = i / total_stages
                progress_callback(stage_name=stage.__class__.__name__, progress=progress)
            # Run the stage
            stage.run(self.context, progress_queue=progress_queue)
            # Update progress after running the stage
            if progress_callback:
                progress = (i + 1) / total_stages
                progress_callback(stage_name=stage.__class__.__name__, progress=progress)

