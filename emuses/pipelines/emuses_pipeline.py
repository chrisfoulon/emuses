# pipelines/emuses_pipeline.py

import logging
import time
from pathlib import Path

import numpy as np
import joblib
import nibabel as nib
from bcblib.tools.dataframe_filtering import normalize_dataframe
from bcblib.tools.general_utils import file_to_list, parse_file_list_argument, save_json
from bcblib.tools.nifti_utils import load_nifti
from numpy.random import default_rng
from sklearn.model_selection import train_test_split

from emuses.observability import get_logger, track_scientific_operation
from emuses.pipelines.pipeline_config import PipelineConfig
from emuses.tools.data_preproc import find_min_resolution
from emuses.tools.inputs_utils import (detect_dataset_type,
                                       handle_bids_dataset, is_bids_dataset,
                                       load_and_preprocess_digits_dataset,
                                       nifti_dataset_to_matrix, prepare_scores,
                                       process_images, spreadsheet_to_input_df)


class EMUSESPipeline:
    def __init__(self, args, inference_data=None):
        """
        Initialize EMUSESPipeline with optional inference data injection.

        Parameters
        ----------
        args : Namespace
            Pipeline configuration arguments
        inference_data : dict, optional
            Inference-specific data for lightweight initialization.
            If provided, should contain:
            - input_path: str, path to inference input data
            - scores_path: str or None, path to scores for validation
            - model_path: str, path to trained model directory
        """
        self.config = PipelineConfig(args)
        self.args = self.config  # For backward compatibility
        self.output_folder = self.config.output_path  # Use Path object, not string

        # Store inference data for later processing
        self._inference_data = inference_data

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
        self.logger = get_logger(__name__)

        # Initialize pipeline metadata
        self.context["pipeline_metadata"] = {
            "start_time": time.time(),
            "stages_completed": [],
            "stages_runtime": {},
            "dataset_name": getattr(self.config, "input_dataset", "unknown"),
        }

        self.validate_args()
        
        # Always call format_args - it handles both training and inference modes properly
        self.format_args()
        
        master_seed = getattr(self.config, "random_state", 42)
        self.logger.info(
            f"Initializing pipeline with master random seed: {master_seed}"
        )

        # Create component-specific seeds. When master_seed is None, all component seeds
        # are also None so UMAP receives random_state=None and can run with n_jobs > 1.
        if master_seed is not None:
            root_rng = default_rng(master_seed)
            random_seeds = {
                "master_seed": master_seed,
                "split_seed": int(root_rng.integers(0, 2**32)),
                "umap_seed": int(root_rng.integers(0, 2**32)),
                "clustering_seed": int(root_rng.integers(0, 2**32)),
                "prediction_seed": int(root_rng.integers(0, 2**32)),
                "cv_seed": int(root_rng.integers(0, 2**32)),
                "optuna_seed": int(root_rng.integers(0, 2**32)),
            }
        else:
            random_seeds = {
                "master_seed": None,
                "split_seed": None,
                "umap_seed": None,
                "clustering_seed": None,
                "prediction_seed": None,
                "cv_seed": None,
                "optuna_seed": None,
            }

        # Store seeds in config for persistence
        self.config.random_seeds = random_seeds
        # Save the generated seeds to a JSON file for future reference
        self.output_folder.mkdir(
            parents=True, exist_ok=True
        )  # Ensure output folder exists
        seed_file = self.output_folder / "random_seeds.json"
        save_json(seed_file, random_seeds)
        self.logger.info(f"Saved component-specific random seeds to {seed_file}")

        # Update context with common settings.
        self.context.update(
            {
                "output_format_info": self.output_format_info,
                "dataset_type": self.dataset_type,
                "output_folder": self.output_folder,
                "random_seeds": random_seeds,  # Store seeds in context for stage access
            }
        )
        if self.config.load_embeddings:
            self.context["embeddings"] = np.load(self.config.load_embeddings)
            print(
                f"Loaded embeddings from {self.config.load_embeddings} with shape {self.context['embeddings'].shape}"
            )
        self.context["cli_args"] = vars(self.config)

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
          
        Note: Handles both training and inference modes. In inference mode,
        uses simplified processing paths and loads saved scalers.
        """
        if getattr(self.config, "label_dataset", None):
            self.logger.info("Labelled dataset mode activated.")
            self.input_matrix, self.dataset_type, self.output_format_info, _ = (
                self.process_dataset(self.config.input_dataset, is_labelled=False)
            )
            if getattr(self.config, "filter_labelled_by_scores", False):
                self.load_and_process_scores(expected_length=None)
                self.labelled_input_matrix, _, _, _ = self.process_dataset(
                    self.config.label_dataset, is_labelled=True
                )
            else:
                self.labelled_input_matrix, _, _, _ = self.process_dataset(
                    self.config.label_dataset, is_labelled=True
                )
                self.load_and_process_scores(
                    expected_length=self.labelled_input_matrix.shape[0]
                )
            self.logger.info(f"Main dataset type: {self.dataset_type}")
            
            # Add dataset metadata to context for stages to access
            self.context["dataset_type"] = self.dataset_type
            self.context["output_format_info"] = self.output_format_info
        else:
            self.input_matrix, self.dataset_type, self.output_format_info, scores = (
                self.process_dataset(self.config.input_dataset, is_labelled=False)
            )
            if scores is not None:
                self.scores = scores
            else:
                self.load_and_process_scores(expected_length=self.input_matrix.shape[0])
                
            # Add dataset metadata to context for stages to access
            self.context["dataset_type"] = self.dataset_type
            self.context["output_format_info"] = self.output_format_info
        # After processing the datasets, perform the splitting:
        # Skip dataset splitting in inference mode
        if not getattr(self.config, 'inference_mode', False):
            self.split_dataset()
        else:
            # In inference mode, set up context that InferenceStage expects
            self.context.update({
                "inference_features": self.input_matrix,
                "inference_labels": self.scores
            })
            self.logger.info(f"Inference mode data processing complete: {self.input_matrix.shape[0]} samples")

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
        if str(dataset_identifier).lower() == "mnist":
            dataset_type = "mnist"
            self.paths_list = None
            features, labels = load_and_preprocess_digits_dataset()
            input_matrix = features
            # Only in classic mode (not labelled) do we return the labels
            scores = labels if not is_labelled else None
            output_format_info = (
                (8, 8) if features[0].shape == (64,) else features[0].shape
            )
            return input_matrix, dataset_type, output_format_info, scores
        elif str(dataset_identifier).lower() == "digits_label_dataset":
            dataset_type = "digits"
            self.paths_list = None

            # For unlabeled dataset used for UMAP/clustering
            if not is_labelled:
                features, labels, labeled_indices = load_and_preprocess_digits_dataset(
                    "digits_label_dataset"
                )
                input_matrix = features
                scores = (
                    labels  # Include labels for the full dataset in non-labeled mode
                )
                print(
                    f"DEBUG: Processed full digits dataset for UMAP with shape {input_matrix.shape}"
                )
                print(
                    f"DEBUG: Generated labeled subset indices with {len(labeled_indices)} samples"
                )
            # For labeled dataset used for predictive models
            else:
                features, labels, labeled_indices = load_and_preprocess_digits_dataset(
                    "digits_label_dataset"
                )
                input_matrix = features[labeled_indices]
                scores = labels[labeled_indices]
                # Store labeled indices in context for potential later use
                self.context["labeled_indices"] = labeled_indices
                print(
                    f"DEBUG: Processed labeled digits subset with shape {input_matrix.shape}"
                )
                print(
                    f"DEBUG: Scores shape: {scores.shape if scores is not None else None}"
                )

            output_format_info = (
                (8, 8) if features[0].shape == (64,) else features[0].shape
            )
            return input_matrix, dataset_type, output_format_info, scores
        elif str(dataset_identifier).lower() == "input_matrix":
            dataset_type = "input_matrix"
            self.paths_list = None
            input_matrix = np.load(dataset_identifier)
            output_format_info = args.output_format_info
            return input_matrix, dataset_type, output_format_info, None

        # Handle file list mode (CSV/Excel/TXT containing paths to actual data files)
        if getattr(args, 'input_file_list', False):
            list_file_path = Path(dataset_identifier).resolve()
            if not list_file_path.exists():
                raise ValueError(f"File list {list_file_path} does not exist")

            self.logger.info(f"Loading file paths from list file: {list_file_path}")

            # Use bcblib to read the file list
            paths_array = file_to_list(list_file_path)

            # Convert to Path objects and filter out empty/whitespace entries
            paths_list = [Path(p.strip()).resolve() for p in paths_array if p.strip()]

            if len(paths_list) == 0:
                raise ValueError(f"File list {list_file_path} contains no valid paths")

            # Validate that paths exist
            missing_paths = [p for p in paths_list if not p.exists()]
            if missing_paths:
                self.logger.error(
                    f"File list contains {len(missing_paths)} non-existent paths. "
                    f"First few: {[str(p) for p in missing_paths[:3]]}"
                )
                raise ValueError(
                    f"File list contains {len(missing_paths)} non-existent paths. "
                    f"First missing: {missing_paths[0]}"
                )

            # Detect dataset type from the actual files (not the container file)
            dataset_type = detect_dataset_type(paths_list)
            self.logger.info(
                f"Detected dataset type '{dataset_type}' from {len(paths_list)} files in list"
            )

            # Convert to strings for compatibility with existing processing logic
            paths_list = [str(p) for p in paths_list]

            # Continue to processing section based on detected type
            # (skip the normal file/folder detection logic)
        else:
            # Otherwise, treat dataset_identifier as a file or folder.
            dataset_path = Path(dataset_identifier).resolve()
            if not dataset_path.exists():
                raise ValueError(f"Dataset {dataset_path} is not a valid path")
            # Check for BIDS dataset
            if is_bids_dataset(dataset_path):
                paths_list = handle_bids_dataset(
                    dataset_path, args.bids_filters, verbose=True
                )
                dataset_type = "nifti"
            else:
                if dataset_path.is_file():
                    dataset_type = detect_dataset_type([dataset_path])
                    paths_list = None
                else:
                    file_types = args.input_file_types
                    if file_types and not isinstance(file_types[0], list):
                        file_types = [file_types]
                    if file_types and len(file_types) == 1:
                        file_types = None
                    paths_list = parse_file_list_argument(
                        dataset_path,
                        recursive_file_search=args.recursive_input_file_search,
                        file_types=file_types,
                        arg_separator=args.arg_separator,
                    )
                    dataset_type = detect_dataset_type(paths_list)
        if (
            dataset_type in ["image", "nifti"]
            and is_labelled
            and getattr(args, "filter_labelled_by_scores", False)
        ):
            # Use the stored DataFrame directly.
            scores_df = self.context["scores_df"]
            # Derive valid IDs from the DataFrame index.
            valid_ids = set(scores_df.index.astype(str))
            original_count = len(paths_list)
            filtered_paths = []
            matched_ids_list = []  # Record the matched valid ID for each accepted file

            for p in paths_list:
                # Find all valid IDs that appear in the file's stem or name.
                matches = [
                    vid
                    for vid in valid_ids
                    if vid in Path(p).stem or vid in Path(p).name
                ]
                if len(matches) == 1:
                    vid = matches[0]
                    # If scores_column is specified, check if all score values are missing.
                    if hasattr(args, "scores_column") and args.scores_column:
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
                    self.logger.warning(
                        f"File {p} has multiple valid ID matches: {matches}. Skipping file."
                    )
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
            self.context["scores_df"] = filtered_scores_df
            self.context["scores"] = prepare_scores(filtered_scores_df)
            self.context["scores_indices"] = filtered_scores_df.index
            self.scores = prepare_scores(
                filtered_scores_df
            )  # Ensure self.scores matches the filtered scores

            self.logger.info(
                f"Filtered labelled dataset: {len(paths_list)} of {original_count} files kept based on scores file."
            )
            print(
                f"Filtered labelled dataset: {len(paths_list)} of {original_count} files kept based on scores file."
            )

        # Process according to dataset type.
        if dataset_type == "image":
            min_res = find_min_resolution(paths_list)
            input_matrix = process_images(paths_list, min_res)
            output_format_info = min_res
        elif dataset_type == "nifti":
            input_matrix = nifti_dataset_to_matrix(paths_list)
            first_image = load_nifti(paths_list[0])
            canonical_first = nib.as_closest_canonical(first_image)
            output_shape = canonical_first.shape
            output_affine = canonical_first.affine
            output_format_info = (output_shape, output_affine)
        elif dataset_type in ["spreadsheet", "tabular"]:
            inputs_df = spreadsheet_to_input_df(
                dataset_path,
                header=args.input_header,
                index_col=args.input_index_column,
                filter_columns_list=args.inputs_columns,
                filter_rows_list=None,
                columns_are_features=args.columns_are_features,
            )
            if args.input_normalization and args.input_normalization.lower() != "none":
                self.logger.info(
                    f"Normalizing dataset with method={args.input_normalization}"
                )
                before_shape = inputs_df.shape

                if not getattr(args, 'inference_mode', False):
                    # TRAINING MODE: Compute scaling factors for the training dataset or apply precomputed ones
                    if not is_labelled:
                        inputs_df, scaling_factors = normalize_dataframe(
                            inputs_df, method=args.input_normalization
                        )
                        self.context["input_scaling_factors"] = scaling_factors
                        
                        # Save input scaler to model directory for inference reuse
                        self.output_folder.mkdir(parents=True, exist_ok=True)
                        input_scaler_path = self.output_folder / "input_scaler.joblib"
                        joblib.dump(scaling_factors, input_scaler_path)
                        self.logger.info(f"Saved input scaler ({args.input_normalization}) to {input_scaler_path}")
                        
                        # Store scaler info in context for manifest generation
                        self.context["input_scaler_info"] = {
                            "path": "input_scaler.joblib",
                            "method": args.input_normalization,
                            "scaling_factors": scaling_factors
                        }
                    else:
                        scaling_factors = self.context.get("input_scaling_factors", None)
                        if scaling_factors is None:
                            raise ValueError(
                                "Scaling factors are missing for labelled dataset normalization."
                            )
                        inputs_df, _ = normalize_dataframe(
                            inputs_df,
                            method=args.input_normalization,
                            scaling_factors=scaling_factors,
                        )
                        
                        # Save input scaler to model directory for cross-validation denormalization
                        self.output_folder.mkdir(parents=True, exist_ok=True)
                        input_scaler_path = self.output_folder / "input_scaler.joblib"
                        joblib.dump(scaling_factors, input_scaler_path)
                        self.logger.info(f"Saved input scaler ({args.input_normalization}) to {input_scaler_path}")
                        
                        # Store scaler info in context for manifest generation
                        self.context["input_scaler_info"] = {
                            "path": "input_scaler.joblib",
                            "method": args.input_normalization,
                            "scaling_factors": scaling_factors
                        }
                else:
                    # INFERENCE MODE: Load and apply saved scaler
                    # Use model path if available, otherwise fall back to output folder
                    if hasattr(args, 'model_path') and args.model_path:
                        scaler_base_path = Path(args.model_path)
                    else:
                        scaler_base_path = self.output_folder
                    
                    input_scaler_path = scaler_base_path / "input_scaler.joblib"
                    if input_scaler_path.exists():
                        scaling_factors = joblib.load(input_scaler_path)
                        inputs_df, _ = normalize_dataframe(
                            inputs_df,
                            method=args.input_normalization,
                            scaling_factors=scaling_factors
                        )
                        self.logger.info(f"Applied saved input normalization ({args.input_normalization}) during inference")
                    else:
                        self.logger.warning("Input scaler not found, skipping normalization - this may cause inference failures")

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
        if getattr(args, "scores", None):
            scores_df = spreadsheet_to_input_df(
                args.scores,
                header=args.scores_header,
                index_col=args.scores_index_column,
                filter_columns_list=(
                    args.scores_column
                    if args.scores_column is None
                    or isinstance(args.scores_column, list)
                    else [args.scores_column]
                ),
                filter_rows_list=None,
                columns_are_features=not args.scores_are_rows,
            )
            if (
                args.scores_normalization
                and args.scores_normalization.lower() != "none"
            ):
                self.logger.info(
                    f"Normalizing scores dataframe with method={args.scores_normalization}"
                )
                before_shape = scores_df.shape
                
                if not getattr(args, 'inference_mode', False):
                    # TRAINING MODE: Compute and save scores scaling factors
                    scores_df, scores_scaling_factors = normalize_dataframe(
                        scores_df, method=args.scores_normalization
                    )
                    
                    # Save scores scaler to model directory for inference reuse
                    self.output_folder.mkdir(parents=True, exist_ok=True)
                    scores_scaler_path = self.output_folder / "scores_scaler.joblib"
                    joblib.dump(scores_scaling_factors, scores_scaler_path)
                    self.logger.info(f"Saved scores scaler ({args.scores_normalization}) to {scores_scaler_path}")
                    
                    # Store scaler info in context for manifest generation
                    self.context["scores_scaler_info"] = {
                        "path": "scores_scaler.joblib",
                        "method": args.scores_normalization,
                        "scaling_factors": scores_scaling_factors
                    }
                else:
                    # INFERENCE MODE: Load and apply saved scaler
                    # Use model path if available, otherwise fall back to output folder
                    if hasattr(args, 'model_path') and args.model_path:
                        scaler_base_path = Path(args.model_path)
                    else:
                        scaler_base_path = self.output_folder
                    
                    scores_scaler_path = scaler_base_path / "scores_scaler.joblib"
                    if scores_scaler_path.exists():
                        scores_scaling_factors = joblib.load(scores_scaler_path)
                        scores_df, _ = normalize_dataframe(
                            scores_df,
                            method=args.scores_normalization,
                            scaling_factors=scores_scaling_factors
                        )
                        self.logger.info(f"Applied saved scores normalization ({args.scores_normalization}) during inference")
                    else:
                        self.logger.warning("Scores scaler not found, skipping normalization - this may cause inference failures")
                
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
            self.context["scores_df"] = scores_df
            self.context["scores"] = self.scores
            self.context["scores_indices"] = scores_df.index

    def split_dataset(self):
        """
        Splits the dataset and updates self.context with train and test sets,
        handling the special case when test_size is set to 0.

        In label_dataset mode:
          - Process the labelled dataset (and its scores) and split it if test_size > 0.
          - If test_size==0, use the entire labelled dataset for training.
          - Save the splits (if any) in the 'split_dataset' folder.
          - Update context with data using a consistent naming pattern:
            - 'embedding_train_features': Data used to train the UMAP model (unlabelled data)
            - 'embedding_train_indices': Indices of data used to train UMAP
            - 'prediction_train_features': Data used for prediction models (labelled data)
            - 'prediction_train_labels': Labels for prediction training
            - 'prediction_train_indices': Indices for prediction training data
            - 'prediction_test_features': Test data for prediction evaluation
            - 'prediction_test_labels': Test labels for prediction
            - 'prediction_test_indices': Indices for prediction test data

        In classic mode:
          - Splits self.input_matrix and self.scores if test_size > 0.
          - If test_size==0, use the entire input data as the training set.
          - Saves the splits and uses the same naming pattern as above, but
            embedding_train_features and prediction_train_features refer to the same data.
        """
        args = self.args
        test_size = getattr(args, "test_size", 0.2)
        split_folder = self.output_folder / "split_dataset"
        split_folder.mkdir(
            parents=True, exist_ok=True
        )  # Extract indices if available from DataFrames
        scores_indices = self.context.get("scores_indices", None)

        # Get the specific seed for dataset splitting
        random_seeds = getattr(self.config, "random_seeds", {})
        split_seed = random_seeds.get(
            "split_seed", getattr(self.config, "random_state", 42)
        )
        self.logger.info(f"Splitting dataset with seed: {split_seed}")

        if getattr(args, "label_dataset", None):
            self.logger.info("Splitting labelled dataset (label_dataset mode).")
            # Assume self.labelled_input_matrix and self.scores are already available.
            if test_size == 0:
                # Use the entire labelled dataset for training.
                train_mat = self.labelled_input_matrix
                train_scores = self.scores
                test_mat = None
                test_scores = None

                # For indices tracking
                prediction_train_indices = scores_indices
                prediction_test_indices = None
            else:
                if scores_indices is not None:
                    # Split with indices
                    indices = np.arange(len(self.labelled_input_matrix))
                    train_indices, test_indices = train_test_split(
                        indices, test_size=test_size, random_state=split_seed
                    )
                    train_mat = self.labelled_input_matrix[train_indices]
                    test_mat = self.labelled_input_matrix[test_indices]
                    train_scores = (
                        self.scores[train_indices]
                        if isinstance(self.scores, np.ndarray)
                        else self.scores.iloc[train_indices]
                    )
                    test_scores = (
                        self.scores[test_indices]
                        if isinstance(self.scores, np.ndarray)
                        else self.scores.iloc[test_indices]
                    )

                    # Store the actual indices if we have them from scores_df
                    prediction_train_indices = (
                        scores_indices.iloc[train_indices]
                        if hasattr(scores_indices, "iloc")
                        else None
                    )
                    prediction_test_indices = (
                        scores_indices.iloc[test_indices]
                        if hasattr(scores_indices, "iloc")
                        else None
                    )
                else:
                    # Regular split without indices
                    train_mat, test_mat, train_scores, test_scores = train_test_split(
                        self.labelled_input_matrix,
                        self.scores,
                        test_size=test_size,
                        random_state=split_seed,
                    )
                    prediction_train_indices = None
                    prediction_test_indices = None

                np.save(split_folder / "test_labelled_matrix.npy", test_mat)
                np.save(split_folder / "test_labelled_scores.npy", test_scores)

            np.save(split_folder / "train_labelled_matrix.npy", train_mat)
            np.save(split_folder / "train_labelled_scores.npy", train_scores)

            # Track indices for unlabelled data (embedding)
            embedding_train_indices = None
            # embedding_test_indices = None  # Unused variable

            # Update context with new naming scheme only (no backward compatibility)
            self.context.update(
                {
                    # New naming pattern for embedding/UMAP (using unlabelled data)
                    "embedding_train_features": self.input_matrix,
                    "embedding_train_indices": embedding_train_indices,
                    # New naming pattern for prediction (using labelled data)
                    "prediction_train_features": train_mat,
                    "prediction_train_labels": train_scores,
                    "prediction_train_indices": prediction_train_indices,
                    "prediction_test_features": test_mat,
                    "prediction_test_labels": test_scores,
                    "prediction_test_indices": prediction_test_indices,
                }
            )

            # Add structured dataset metadata
            self.context["dataset_metadata"] = {
                "type": self.dataset_type,
                "name": str(getattr(self.config, "input_dataset", "unknown")),
                "label_dataset_name": str(
                    getattr(self.config, "label_dataset", "unknown")
                ),
                "mode": "label_dataset",
                "embedding_train_size": (
                    self.input_matrix.shape[0] if self.input_matrix is not None else 0
                ),
                "embedding_train_dimensions": (
                    self.input_matrix.shape[1] if self.input_matrix is not None else 0
                ),
                "prediction_train_size": (
                    train_mat.shape[0] if train_mat is not None else 0
                ),
                "prediction_test_size": (
                    test_mat.shape[0] if test_mat is not None else 0
                ),
                "prediction_dimensions": (
                    train_mat.shape[1] if train_mat is not None else 0
                ),
                "test_size_proportion": test_size,
            }

            # Add placeholder for performance metrics
            self.context["prediction_performance"] = {
                "train": {},  # Will be populated during model training
                "test": {},  # Will be populated during model evaluation
            }

            self.logger.info(
                "Labelled dataset split and context updated for label_dataset mode."
            )
        else:
            self.logger.info("Splitting main dataset (classic mode).")
            if test_size == 0:
                # Use entire input for training.
                train_features = self.input_matrix
                train_labels = self.scores
                test_features = None
                test_labels = None

                # For indices tracking
                train_indices = scores_indices
                test_indices = None
            else:
                if scores_indices is not None:
                    # Split with indices tracking
                    indices = np.arange(len(self.input_matrix))
                    train_indices_pos, test_indices_pos = train_test_split(
                        indices, test_size=test_size, random_state=split_seed
                    )
                    train_features = self.input_matrix[train_indices_pos]
                    test_features = self.input_matrix[test_indices_pos]
                    train_labels = (
                        self.scores[train_indices_pos]
                        if isinstance(self.scores, np.ndarray)
                        else self.scores.iloc[train_indices_pos]
                    )
                    test_labels = (
                        self.scores[test_indices_pos]
                        if isinstance(self.scores, np.ndarray)
                        else self.scores.iloc[test_indices_pos]
                    )

                    # Store the actual indices
                    train_indices = (
                        scores_indices.iloc[train_indices_pos]
                        if hasattr(scores_indices, "iloc")
                        else None
                    )
                    test_indices = (
                        scores_indices.iloc[test_indices_pos]
                        if hasattr(scores_indices, "iloc")
                        else None
                    )
                else:
                    # Regular split without indices
                    train_features, test_features, train_labels, test_labels = (
                        train_test_split(
                            self.input_matrix,
                            self.scores,
                            test_size=test_size,
                            random_state=split_seed,
                        )
                    )
                    train_indices = None
                    test_indices = None

                np.save(split_folder / "test_features.npy", test_features)
                np.save(split_folder / "test_labels.npy", test_labels)

            np.save(split_folder / "train_features.npy", train_features)
            np.save(split_folder / "train_labels.npy", train_labels)

            # Update context with new naming pattern only (no backward compatibility)
            self.context.update(
                {
                    # New naming pattern (in classic mode, same data used for both purposes)
                    "embedding_train_features": train_features,
                    "embedding_train_indices": train_indices,
                    "embedding_test_features": test_features,
                    "embedding_test_indices": test_indices,
                    "prediction_train_features": train_features,
                    "prediction_train_labels": train_labels,
                    "prediction_train_indices": train_indices,
                    "prediction_test_features": test_features,
                    "prediction_test_labels": test_labels,
                    "prediction_test_indices": test_indices,
                }
            )

            # Add structured dataset metadata
            self.context["dataset_metadata"] = {
                "type": self.dataset_type,
                "name": str(getattr(self.config, "input_dataset", "unknown")),
                "mode": "classic",
                "train_size": (
                    train_features.shape[0] if train_features is not None else 0
                ),
                "test_size": test_features.shape[0] if test_features is not None else 0,
                "dimensions": (
                    train_features.shape[1] if train_features is not None else 0
                ),
                "test_size_proportion": test_size,
            }

            # Add placeholder for performance metrics
            self.context["prediction_performance"] = {
                "train": {},  # Will be populated during model training
                "test": {},  # Will be populated during model evaluation
            }

            self.logger.info("Main dataset split and context updated for classic mode.")

    def add_stage(self, stage):
        self.stages.append(stage)

    def run(self, progress_callback=None, progress_queue=None):
        total_stages = len(self.stages)
        user_id = self.context.get("user_id")
        dataset_name = self.context.get("dataset_name", "unknown")

        with track_scientific_operation(
            "pipeline_stages_execution",
            user_id=user_id,
            additional_attributes={
                "dataset": dataset_name,
                "total_stages": total_stages,
                "pipeline_type": "emuses_full",
            },
        ) as obs_ctx:
            for i, stage in enumerate(self.stages):
                stage_name = stage.__class__.__name__
                stage_start_time = time.time()

                if progress_callback:
                    progress = i / total_stages
                    progress_callback(stage_name=stage_name, progress=progress)

                # Run the stage with individual tracking
                with track_scientific_operation(
                    f"stage_{stage_name.lower()}",
                    user_id=user_id,
                    additional_attributes={
                        "stage_index": i,
                        "stage_name": stage_name,
                        "dataset": dataset_name,
                    },
                ) as stage_obs_ctx:
                    self.logger.info(
                        f"Starting stage {i+1}/{total_stages}: {stage_name}"
                    )
                    stage.run(self.context, progress_queue=progress_queue)
                    self.logger.info(f"Completed stage: {stage_name}")

                # Record stage completion and runtime
                stage_end_time = time.time()
                stage_runtime = stage_end_time - stage_start_time

                # Update pipeline metadata with completion info
                self.context["pipeline_metadata"]["stages_completed"].append(stage_name)
                self.context["pipeline_metadata"]["stages_runtime"][
                    stage_name
                ] = stage_runtime

                # Add stage metrics to observability
                stage_obs_ctx.set_attribute("stage_runtime", stage_runtime)
                stage_obs_ctx.set_attribute("stage_completed", True)

                if progress_callback:
                    progress = (i + 1) / total_stages
                    progress_callback(stage_name=stage_name, progress=progress)

            # Update total pipeline runtime
            self.context["pipeline_metadata"]["end_time"] = time.time()
            self.context["pipeline_metadata"]["total_runtime"] = (
                self.context["pipeline_metadata"]["end_time"]
                - self.context["pipeline_metadata"]["start_time"]
            )

            # Add final observability metrics
            obs_ctx.set_attribute(
                "total_runtime", self.context["pipeline_metadata"]["total_runtime"]
            )
            obs_ctx.set_attribute(
                "stages_completed",
                len(self.context["pipeline_metadata"]["stages_completed"]),
            )

            # Enhance model manifest with pipeline data
            try:
                from emuses.tools.model_io import enhance_model_manifest_with_pipeline_data
                self.logger.info("Enhancing model manifest with pipeline data...")
                success = enhance_model_manifest_with_pipeline_data(self.output_folder)
                if success:
                    self.logger.info("Model manifest successfully enhanced")
                else:
                    self.logger.warning("Model manifest enhancement failed")
            except Exception as e:
                self.logger.warning(f"Could not enhance model manifest: {e}")
