import argparse
import os
from pathlib import Path
from typing import List, Optional, Tuple

import nibabel as nib
import numpy as np
import pandas as pd
from bcblib.tools.general_utils import file_to_list
from bcblib.tools.nifti_utils import reorient_to_canonical
from bids import BIDSLayout
from PIL import Image
from scipy.sparse import lil_matrix
from sklearn.datasets import fetch_openml, load_digits
from sklearn.preprocessing import RobustScaler, StandardScaler
from tqdm import tqdm

from emuses.tools.data_preproc import find_min_resolution
from emuses.tools.model_io import ModelIOManager


def load_and_preprocess_digits_dataset(dataset="digits"):
    """
    Downloads the specified dataset if it's not already on the machine and preprocesses it to make an input matrix for
    UMAP training.

    Parameters:
    - dataset (str): The name of the dataset to load. Options are 'mnist', 'digits', or 'digits_label_dataset'.
                    When 'digits_label_dataset' is used, it returns the full dataset for UMAP training and
                    a subset of indices (400 samples) for supervised learning.

    Returns:
    - features_normalized (ndarray): The preprocessed feature matrix.
    - labels (ndarray): The labels for the dataset.
    - labeled_indices (ndarray, optional): Only returned when dataset='digits_label_dataset'.
                                         Indices of the subset to use for supervised learning.
    """
    if dataset == "mnist":
        # Download the MNIST dataset
        features, labels = fetch_openml("mnist_784", version=1, return_X_y=True)

        # Normalize the pixel values to be between 0 and 1
        features_normalized = features / 255.0

    elif dataset in ["digits", "digits_label_dataset"]:
        # Load the Digits dataset
        digits = load_digits()
        print(f"Shape of digits data: {digits.data.shape}")
        features = digits.data
        labels = digits.target

        # Normalize the pixel values to be between 0 and 1
        features_normalized = (
            features / 16.0
        )  # Digits data is already scaled between 0 and 16

        # For digits_label_dataset, create a random subset for supervised learning
        if dataset == "digits_label_dataset":
            # Create a deterministic random state for reproducibility
            rng = np.random.RandomState(42)
            n_samples = len(labels)
            # Limit to 400 samples or the max available
            n_labeled = min(400, n_samples)
            # Get random indices without replacement
            labeled_indices = rng.choice(n_samples, size=n_labeled, replace=False)
            return features_normalized, labels, labeled_indices

    else:
        raise ValueError(
            "Unsupported dataset. Choose 'mnist', 'digits', or 'digits_label_dataset'."
        )

    return features_normalized, labels


def mnist_features_to_input_matrix(mnist_features: pd.DataFrame):
    """
    Converts the MNIST features to an input matrix with each column being a flattened image for UMAP training.
    Parameters
    ----------
    mnist_features : pd.DataFrame
        MNIST features

    Returns
    -------
    input_matrix : np.ndarray
        input matrix for UMAP training
    """
    input_matrix = np.zeros((mnist_features.shape[0], 784))
    for i in range(mnist_features.shape[0]):
        input_matrix[i, :] = mnist_features.iloc[i, :].values
    return input_matrix


def detect_dataset_type(file_paths: List[os.PathLike]) -> str:
    """
    Detects the type of dataset from the file paths.
    Parameters
    ----------
    file_paths : list of os.PathLike
        list of file paths

    Returns
    -------
    dataset_type : str
        type of dataset
    """
    dataset_type = None
    for file_path in file_paths:
        file_path = Path(file_path)
        extension = "".join(file_path.suffixes)
        if extension in [".jpg", ".png"]:
            dataset_type = "image"
            break
        elif extension in [".nii", ".nii.gz"]:
            dataset_type = "nifti"
            break
        elif extension in [".csv", ".xlsx", ".xls"]:
            dataset_type = "spreadsheet"
            break
        else:
            raise ValueError(f"Unsupported file format: {extension}")
    return dataset_type


def nifti_dataset_to_matrix(
    nifti_list: List[nib.Nifti1Image],
    pre_allocate_memory: bool = True,
    disable_progress: bool = False,
) -> np.ndarray:
    """
    Converts a list of nifti images into a matrix where each row is a flattened nifti image
    after reorienting it to canonical space
    Parameters
    ----------
    nifti_list : list of nibabel.Nifti1Image
        list of nifti images
    pre_allocate_memory : bool, optional
        whether to pre-allocate the memory for the output matrix (default is True)
    disable_progress : bool, optional
        whether to disable the progress bar (default is False)

    Returns
    -------
    out_matrix : np.ndarray
        matrix where each row is a flattened nifti image
    Notes
    -----
    The order of the images in the matrix is the same as the order of the images in the input list
    """
    # reorient the images and then flatten them into a matrix
    out_matrix = None
    for i, nii in tqdm(enumerate(nifti_list), disable=disable_progress):
        nii = reorient_to_canonical(nii)
        flattened_nii = np.ravel(nii.get_fdata())
        if out_matrix is None:
            if pre_allocate_memory:
                out_matrix = np.zeros((len(nifti_list), len(flattened_nii)))
                out_matrix[0, :] = flattened_nii
        else:
            out_matrix[i, :] = flattened_nii
            # out_matrix = np.vstack((out_matrix, flattened_nii))
    return out_matrix


def load_image_list(image_paths: List[str]):
    """
    Load a list of jpg or png images
    Parameters
    ----------
    image_paths

    Returns
    -------

    """
    images = []
    for img_path in image_paths:
        img = Image.open(img_path)
        images.append(img)
    return images


def image_paths_list_to_matrix_old(
    image_paths_list: List[os.PathLike],
    rescale: Optional[bool] = False,
    output_shape: Optional[Tuple[int, int]] = None,
    disable_progress: Optional[bool] = False,
) -> lil_matrix:
    """
    Load a list of jpg or png images loaded with PIL and convert them to a matrix where each row is a flattened image
    Parameters
    ----------
    image_paths_list : list of os.PathLike
    output_shape : tuple of int
        the desired output shape for all images. If None, no rescaling is performed.
    rescale : bool
        whether to rescale the images. If True and output_shape is None, images are rescaled to the shape of the first image.
    disable_progress : bool
        whether to disable the progress bar

    Returns
    -------
    out_matrix : lil_matrix
        matrix where each row is a flattened image
    """
    # Rescale the images if rescale is True
    if rescale:
        if output_shape is None:
            output_shape = find_min_resolution(image_paths_list)
    else:
        # Preallocate the sparse matrix
        first_image = Image.open(str(image_paths_list[0]))
        output_shape = first_image.size
    flattened_size = np.prod((3,) + output_shape)
    out_matrix = lil_matrix((len(image_paths_list), flattened_size))

    print(f"Output shape: {output_shape}")
    print(f"Flattened size: {flattened_size}")
    print(f"out_matrix shape: {out_matrix.shape}")

    print("Converting images to matrix")
    for i, path in tqdm(enumerate(image_paths_list), disable=disable_progress):
        path = str(path)
        img = Image.open(path)
        if rescale:
            img = img.resize(output_shape)
        img_array = np.array(img).ravel()
        out_matrix[i, :] = img_array
    return out_matrix


def load_and_preprocess_image(path, output_shape, rescale):
    with Image.open(str(path)) as img:
        if rescale:
            img = img.resize(output_shape, Image.LANCZOS)
        img_array = np.array(img).ravel()
    return img_array


def process_images(image_list, target_size=(128, 128)):
    images = []
    for img_path in tqdm(image_list):
        with Image.open(img_path) as img:
            img = img.resize(target_size)
            img_array = np.array(img, dtype=np.uint8)  # Use uint8 to save memory
            images.append(
                img_array.flatten()
            )  # Flatten if necessary or adapt based on UMAP needs
    return np.array(images)


def spreadsheet_to_input_df(
    file_path,
    header=None,
    index_col=None,
    filter_columns_list=None,
    filter_rows_list=None,
    columns_are_features=False,
):
    """
    Import a spreadsheet and make an input matrix (observations, features),
    with automatic handling of invalid columns and data conversion.

    Parameters
    ----------
    file_path : str or os.PathLike
        Path to the spreadsheet file.
    header : int, optional
        Row to use as the column names. Default is None.
    index_col : int or list of int, optional
        Column(s) to set as index (MultiIndex). Default is None.
    filter_columns_list : list of str, optional
        Columns to keep in the DataFrame. Default is None.
    filter_rows_list : list of indices, optional
        Rows to keep in the DataFrame. Default is None.
    columns_are_features : bool, optional
        If True, transpose the DataFrame so that columns become features. Default is False.

    Returns
    -------
    pd.DataFrame
        The resulting input matrix with invalid columns removed and data types handled.

    Raises
    ------
    ValueError
        If the resulting DataFrame contains non-numeric columns.

    Examples
    --------
    >>> file_path = 'path_to_your_spreadsheet.xlsx'
    >>> input_matrix = spreadsheet_to_input_df(file_path, header=0, index_col=0,
    ...                                            filter_columns_list=['column1', 'column2'],
    ...                                            filter_rows_list=[0, 1, 2], columns_are_features=True)
    >>> print(input_matrix)
    """

    # Read the spreadsheet into a DataFrame
    if str(file_path).endswith(".csv"):
        df = pd.read_csv(file_path, header=header, index_col=index_col)
    else:
        df = pd.read_excel(file_path, header=header, index_col=index_col)

    # Transpose the DataFrame if columns_are_features is True
    if not columns_are_features:
        df = df.transpose()

    # Filter columns if a list is provided
    if filter_columns_list is not None and len(filter_columns_list) > 0:
        df = df[filter_columns_list]

    # Filter rows if a list is provided
    if filter_rows_list is not None:
        df = df.loc[filter_rows_list]

    # Remove constant columns
    constant_columns = df.columns[df.nunique() <= 1].tolist()
    if constant_columns:
        print(f"Removed constant columns: {constant_columns}")
        df = df.loc[:, df.nunique() > 1]

    # Convert boolean columns to integers
    boolean_columns = df.select_dtypes(include=["bool"]).columns.tolist()
    if boolean_columns:
        print(f"Converted boolean columns to integers: {boolean_columns}")
        for col in boolean_columns:
            df[col] = df[col].astype(int)

    # Handle object columns
    columns_to_remove = []
    unprocessable_examples = {}
    for col in df.select_dtypes(include=["object"]).columns:
        try:
            # Attempt to parse as datetime with a specified format
            df[col] = pd.to_datetime(df[col], format="%Y-%m-%d", errors="raise")
        except (ValueError, TypeError):
            try:
                # Attempt to parse as time-only and convert to timedelta
                df[col] = pd.to_datetime(
                    df[col], format="%H:%M:%S", errors="raise"
                ).dt.time
                df[col] = pd.to_timedelta(df[col].astype(str))
            except (ValueError, TypeError):
                try:
                    # Attempt to parse as timedelta
                    df[col] = pd.to_timedelta(df[col], errors="raise")
                except (ValueError, TypeError):
                    try:
                        # Attempt to convert to numeric
                        df[col] = pd.to_numeric(df[col], errors="raise")
                    except ValueError:
                        # Mark column for removal if all attempts fail
                        columns_to_remove.append(col)
                        unprocessable_examples[col] = (
                            df[col].dropna().unique()[:5].tolist()
                        )

    # Show examples of unprocessable columns
    if unprocessable_examples:
        for col, examples in unprocessable_examples.items():
            print(f"Column '{col}' could not be converted. Examples: {examples}")

    # Remove columns that couldn't be converted
    if columns_to_remove:
        print(f"Removed unprocessable object columns: {columns_to_remove}")

        # Provide helpful warning about common header/index issues
        if header is None:
            print("⚠️  WARNING: No header row specified (header=None).")
            print(
                "   If your file has column names in the first row, try adding: --input_header 0 (for input files) or --scores_header 0 (for scores files)"
            )

        if index_col is None and len(columns_to_remove) > 0:
            print("⚠️  WARNING: No index column specified (index_col=None).")
            print(
                "   If your file has row labels/IDs in the first column, try adding: --input_index_column 0 (for input files) or --scores_index_column 0 (for scores files)"
            )

        # Check if we're removing many columns (likely a header/formatting issue)
        if len(columns_to_remove) > 10:
            print(
                "⚠️  WARNING: Many columns were removed - this might indicate a formatting issue."
            )
            print("   Common causes:")
            print(
                "   - Header row not properly specified (use --input_header 0 or --scores_header 0)"
            )
            print(
                "   - Index column not properly specified (use --input_index_column 0 or --scores_index_column 0)"
            )
            print("   - Wrong file format or encoding")

        df.drop(columns=columns_to_remove, inplace=True)

    # Check if we have any data left after removing unprocessable columns
    if df.empty or df.shape[1] == 0:
        raise ValueError(
            "❌ ERROR: No numeric data remaining after processing the file.\n"
            "🔧 LIKELY CAUSES:\n"
            "   - Header row not properly specified\n"
            "   - Index column not properly specified\n"
            "   - File contains only text data or headers\n"
            "💡 SOLUTIONS:\n"
            "   - Add --input_header 0 (for input files) or --scores_header 0 (for scores files) if your file has headers\n"
            "   - Add --input_index_column 0 (for input files) or --scores_index_column 0 (for scores files) if your file has row labels\n"
            "   - Check that your file contains numeric data\n"
            "📝 EXAMPLE: emuses full ... --input_header 0 --input_index_column 0"
        )

    # Check if all remaining columns are numeric, datetime, or timedelta
    remaining_string_columns = [
        col for col in df.columns if pd.api.types.is_string_dtype(df[col])
    ]
    if remaining_string_columns:
        for col in remaining_string_columns:
            print(f"Unconverted string column detected: {col}")
            print(f"Sample values: {df[col].dropna().unique()[:5].tolist()}")
        raise ValueError(
            "The resulting DataFrame contains unconverted string columns. Please inspect the sample values."
        )

    return df


# def create_heatmap_data(dls, new_dataset, scores_file=None):
#     """
#     Prepare the DataFrame with embeddings and scores for creating a heatmap.
#     Parameters:
#     - dls: DiscreteLatentSpace
#         The DLS object.
#     - new_dataset: str
#         Path to the new dataset (spreadsheet or text file).
#     - scores_file: str, optional
#         Separate file for scores if not in new_dataset.
#
#     Returns:
#     - embeddings, scores: np.ndarray, np.ndarray
#     """
#     if scores_file and new_dataset is None:  # Case 1: Separate scores file
#         scores = file_to_list(scores_file)
#         embeddings = dls.raw_embeddings
#         if len(scores) != len(embeddings):
#             raise ValueError("Scores and embeddings must have the same length.")
#     else:  # Case 2: Spreadsheet with inputs and scores
#         inputs, scores = load_inputs_scores_spreadsheet(new_dataset)
#         # if inputs are just a list of paths we need to use one of the functions to create an input matrix
#         # otherwise, we need to make a matrix with the values in the inputs
#         if isinstance(inputs, list):
#             if inputs[0].endswith('.nii') or inputs[0].endswith('.nii.gz'):
#                 inputs = nifti_dataset_to_matrix([nib.load(p) for p in inputs])
#             elif inputs[0].endswith('.jpg') or inputs[0].endswith('.png'):
#                 inputs = process_images(inputs)
#             else:
#                 raise ValueError(f"Unsupported file format: {Path(inputs[0]).suffix}")
#         embeddings = dls.trained_umap.transform(inputs)
#
#     return embeddings, scores


def reshape_input_matrix_data(input_matrix, original_shape, indices=None):
    # If indices are provided, filter the input matrix
    if indices is not None:
        input_matrix = input_matrix[:, indices]

    # Initialize a list to store the reshaped inputs
    reshaped_inputs = []

    # Reshape each column and add it to the list
    for i in range(input_matrix.shape[1]):
        reshaped_input = np.reshape(input_matrix[:, i], original_shape)
        reshaped_inputs.append(reshaped_input)

    return reshaped_inputs


def prepare_input_matrix(paths_list, dataset_type):
    """Prepare the input matrix based on the dataset type."""
    if dataset_type == "image":
        min_res = find_min_resolution(paths_list)
        return process_images(paths_list, min_res)
    elif dataset_type == "nifti":
        return nifti_dataset_to_matrix(paths_list)
    elif dataset_type == "mnist":
        mnist_features_normalized, _ = load_and_preprocess_digits_dataset()
        return mnist_features_to_input_matrix(mnist_features_normalized)
    elif dataset_type == "digits_label_dataset":
        # Get the full dataset for UMAP training
        features, _, _ = load_and_preprocess_digits_dataset("digits_label_dataset")
        return features
    else:
        raise ValueError(f"Unsupported dataset type: {dataset_type}")


def prepare_scores(scores, match_length=None):
    """Prepare and validate the scores.

    Converts scores to float and reshapes to (-1, 1) if necessary.
    If match_length is provided, checks that scores has at least that many rows.
    If there are more rows than match_length, only the first match_length observations are kept.
    """
    # Check for empty scores array (common when headers aren't handled correctly)
    if scores.size == 0:
        raise ValueError(
            "❌ ERROR: No numeric data found in scores file after processing.\n"
            "🔧 LIKELY CAUSE: Header row not properly specified.\n"
            "💡 SOLUTION: Add --scores_header 0 to your command if your scores file has a header row.\n"
            "             Also consider --scores_index_column 0 if your file has row labels in the first column.\n"
            "📝 EXAMPLE: emuses full ... --scores /path/to/scores.csv --scores_header 0"
        )

    scores = np.vectorize(float)(scores)
    print(f"Scores shape: {scores.shape}")
    if scores.ndim == 1:
        scores = scores.reshape(-1, 1)
    if match_length is not None:
        if scores.shape[0] < match_length:
            raise ValueError("Scores length is less than the expected match length")
        elif scores.shape[0] > match_length:
            print(
                f"Warning: More scores ({scores.shape[0]}) than expected ({match_length}). "
                f"Filtering to first {match_length} observations."
            )
            scores = scores[:match_length, :]
    return scores


def handle_bids_dataset(folder_path, filters=None, verbose=True):
    """
    Handles loading a BIDS dataset using PyBIDS.

    Args:
        folder_path (Path): The folder path where the BIDS dataset is located.
        filters (dict): A dictionary of filters to be applied (e.g., {'modality': 'T1w', 'session': '1'}).
        verbose (bool): If True, prints additional information about the dataset.

    Returns:
        list: A list of paths for the selected attributes.
    """
    try:
        layout = BIDSLayout(folder_path)
        # Apply filters if provided
        if filters:
            files = layout.get(**filters, extension=[".nii", ".nii.gz"])
        else:
            files = layout.get(extension=[".nii", ".nii.gz"])
        paths_list = [f.path for f in files]

        if verbose:
            print(
                f"Found {len(paths_list)} files with filters {filters} in BIDS dataset at {folder_path}"
            )

        if len(paths_list) == 0:
            raise argparse.ArgumentTypeError(
                f"No files found with filters {filters} in BIDS dataset at {folder_path}"
            )

        return paths_list

    except Exception as e:
        raise argparse.ArgumentTypeError(f"Error handling BIDS dataset: {e}")


def is_bids_dataset(folder_path):
    """
    Checks if the given folder is a BIDS dataset.

    Args:
        folder_path (Path): The folder path to check.

    Returns:
        bool: True if the folder is a BIDS dataset, False otherwise.
    """
    return (folder_path / "dataset_description.json").exists()


def load_or_check_umap_outputs(
    output_paths, data_dict, umap_params, force_recompute=False
):
    """
    Load or generate UMAP model and embeddings.

    This function checks if UMAP model and embeddings files exist at the specified paths.
    If they exist and force_recompute is False, it loads them.
    Otherwise, it generates new UMAP model and embeddings.

    Parameters:
    -----------
    output_paths : dict
        Dictionary with paths to output files, must contain 'umap_model' and 'embeddings' keys
    data_dict : dict
        Dictionary with data to use for UMAP, must contain 'train_features_array' key
        and optionally 'test_features_array' key
    umap_params : dict
        Dictionary with UMAP parameters to use if generating new model
    force_recompute : bool, optional (default=False)
        Whether to force recomputation even if files exist

    Returns:
    --------
    dict
        Dictionary containing:
        - 'reducer': UMAP reducer object
        - 'train_embeddings': UMAP embeddings for training data
        - 'test_embeddings': UMAP embeddings for test data (if available)
        - 'status': Dictionary with info on what was loaded vs. generated
    """
    import time
    from pathlib import Path

    import joblib
    import numpy as np
    import umap

    # Initialize results dictionary
    results = {
        "reducer": None,
        "train_embeddings": None,
        "test_embeddings": None,
        "status": {"loaded": [], "generated": []},
    }

    # Check if output paths exist
    model_path = Path(output_paths["umap_model"])
    embeddings_path = Path(output_paths["embeddings"])

    model_exists = model_path.exists() and not force_recompute
    embeddings_exist = embeddings_path.exists() and not force_recompute

    # If both files exist and we're not forcing recomputation, load them
    if model_exists and embeddings_exist:
        print(f"Loading existing UMAP model from {model_path}")

        # Try to load using new I/O system first, then fallback to legacy
        try:
            manager = ModelIOManager(model_path.parent)
            model_name = model_path.stem.replace("_model", "").replace(".joblib", "")

            artifact = manager.load_model(model_name=model_name, model_type="umap")

            if artifact:
                reducer = artifact.model
                print(
                    f"Successfully loaded UMAP model using ModelIOManager: {artifact.filepath}"
                )
            else:
                # Fallback to legacy loading
                reducer = joblib.load(model_path)
                print(f"Loaded UMAP model using legacy method from {model_path}")
        except Exception as e:
            print(f"ModelIOManager loading failed: {e}, falling back to legacy method")
            reducer = joblib.load(model_path)

        results["reducer"] = reducer
        results["status"]["loaded"].append("reducer")

        print(f"Loading existing embeddings from {embeddings_path}")
        embeddings_data = np.load(embeddings_path)
        results["train_embeddings"] = embeddings_data["train_embeddings"]
        results["status"]["loaded"].append("train_embeddings")

        if "test_embeddings" in embeddings_data:
            results["test_embeddings"] = embeddings_data["test_embeddings"]
            results["status"]["loaded"].append("test_embeddings")

    # Otherwise, generate new model and embeddings
    else:
        # Check what to generate
        if not model_exists or force_recompute:
            print(
                f"Generating new UMAP model (existing: {model_exists}, force: {force_recompute})"
            )

            # Create UMAP reducer with specified parameters
            reducer = umap.UMAP(
                n_neighbors=umap_params.get("n_neighbors", 15),
                min_dist=umap_params.get("min_dist", 0.1),
                n_components=umap_params.get("n_components", 2),
                metric=umap_params.get("metric", "euclidean"),
                random_state=umap_params.get("random_state", 42),
            )

            # Fit UMAP model
            start_time = time.time()
            print("Fitting UMAP model...")

            # Check for NaN or Inf values in training data
            train_data = data_dict["train_features_array"]
            if np.isnan(train_data).any() or np.isinf(train_data).any():
                print("Warning: NaN or Inf values detected. Replacing with zeros.")
                train_data = np.nan_to_num(train_data, nan=0.0, posinf=0.0, neginf=0.0)

            # Fit the model
            reducer.fit(train_data)
            end_time = time.time()
            print(f"UMAP fitting completed in {end_time - start_time:.2f} seconds")

            # Save the model using ModelIOManager
            try:
                manager = ModelIOManager(model_path.parent)
                model_name = model_path.stem.replace("_model", "").replace(
                    ".joblib", ""
                )

                saved_path = manager.save_model(
                    model=reducer,
                    model_name=model_name,
                    model_type="umap",
                    config=umap_params,
                    description="UMAP model trained on input features",
                    tags=["input_processing", "feature_reduction"],
                )
                print(f"UMAP model saved using ModelIOManager: {saved_path}")
            except Exception as e:
                print(
                    f"ModelIOManager saving failed: {e}, falling back to legacy method"
                )
                joblib.dump(reducer, model_path)
                print(f"UMAP model saved to {model_path}")

            results["reducer"] = reducer
            results["status"]["generated"].append("reducer")
        else:
            print(f"Using existing UMAP model from {model_path}")

            # Try to load using new I/O system first, then fallback to legacy
            try:
                manager = ModelIOManager(model_path.parent)
                model_name = model_path.stem.replace("_model", "").replace(
                    ".joblib", ""
                )

                artifact = manager.load_model(model_name=model_name, model_type="umap")

                if artifact:
                    reducer = artifact.model
                    print(
                        f"Successfully loaded UMAP model using ModelIOManager: {artifact.filepath}"
                    )
                else:
                    # Fallback to legacy loading
                    reducer = joblib.load(model_path)
                    print(f"Loaded UMAP model using legacy method from {model_path}")
            except Exception as e:
                print(
                    f"ModelIOManager loading failed: {e}, falling back to legacy method"
                )
                reducer = joblib.load(model_path)

            results["reducer"] = reducer
            results["status"]["loaded"].append("reducer")

        # Generate embeddings
        if not embeddings_exist or force_recompute:
            print(
                f"Generating new embeddings (existing: {embeddings_exist}, force: {force_recompute})"
            )

            # Transform training data
            print("Transforming training data...")
            train_data = data_dict["train_features_array"]
            # Handle NaN or Inf values if present
            if np.isnan(train_data).any() or np.isinf(train_data).any():
                print(
                    "Warning: NaN or Inf values detected in training data. Replacing with zeros."
                )
                train_data = np.nan_to_num(train_data, nan=0.0, posinf=0.0, neginf=0.0)

            train_embeddings = reducer.transform(train_data)
            print(f"Training embeddings shape: {train_embeddings.shape}")

            # Transform test data if available
            test_embeddings = None
            if (
                "test_features_array" in data_dict
                and data_dict["test_features_array"] is not None
            ):
                print("Transforming test data...")
                test_data = data_dict["test_features_array"]
                # Handle NaN or Inf values if present
                if np.isnan(test_data).any() or np.isinf(test_data).any():
                    print(
                        "Warning: NaN or Inf values detected in test data. Replacing with zeros."
                    )
                    test_data = np.nan_to_num(
                        test_data, nan=0.0, posinf=0.0, neginf=0.0
                    )

                test_embeddings = reducer.transform(test_data)
                print(f"Test embeddings shape: {test_embeddings.shape}")

            # Save embeddings
            if test_embeddings is not None:
                np.savez(
                    embeddings_path,
                    train_embeddings=train_embeddings,
                    test_embeddings=test_embeddings,
                )
                print(f"Embeddings saved to {embeddings_path}")
                results["test_embeddings"] = test_embeddings
                results["status"]["generated"].append("test_embeddings")
            else:
                np.savez(embeddings_path, train_embeddings=train_embeddings)
                print(f"Training embeddings saved to {embeddings_path}")

            results["train_embeddings"] = train_embeddings
            results["status"]["generated"].append("train_embeddings")
        else:
            print(f"Using existing embeddings from {embeddings_path}")
            embeddings_data = np.load(embeddings_path)
            results["train_embeddings"] = embeddings_data["train_embeddings"]
            results["status"]["loaded"].append("train_embeddings")

            if "test_embeddings" in embeddings_data:
                results["test_embeddings"] = embeddings_data["test_embeddings"]
                results["status"]["loaded"].append("test_embeddings")

    return results


def get_array_info(arr, detailed=True):
    """
    Get detailed information about a numpy array.

    Parameters
    ----------
    arr : np.ndarray or None
        The array to profile
    detailed : bool, default=False
        Whether to include detailed statistics for each dimension

    Returns
    -------
    dict
        Dictionary with array information and statistics
    """
    if arr is None:
        return {"shape": None, "dtype": None, "is_none": True}

    info = {
        "shape": arr.shape,
        "dtype": str(arr.dtype),
        "is_none": False,
        "ndim": arr.ndim,
        "size": arr.size,
    }

    # Basic statistics for the entire array
    if np.issubdtype(arr.dtype, np.number):  # Only compute stats for numeric arrays
        info.update(
            {
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr)),
                "median": float(np.median(arr)),
                "is_normalized": float(np.min(arr)) >= 0 and float(np.max(arr)) <= 1,
                "appears_zscored": abs(float(np.mean(arr))) < 0.1
                and 0.9 < float(np.std(arr)) < 1.1,
                "sparsity": float(np.sum(arr == 0) / arr.size),
            }
        )

        # Check for NaN and Inf values
        info["contains_nan"] = bool(np.isnan(arr).any())
        info["contains_inf"] = bool(np.isinf(arr).any())

        # If detailed is True and it's a 2D array, add per-dimension statistics
        if detailed and arr.ndim > 1:
            # Stats for each dimension
            dim_stats = {}

            # For dimension 0 (samples/rows)
            if arr.shape[0] > 1:  # Only if we have more than one sample
                row_means = np.mean(arr, axis=1)
                row_stds = np.std(arr, axis=1)
                dim_stats["dim0"] = {
                    "means": {
                        "min": float(np.min(row_means)),
                        "max": float(np.max(row_means)),
                        "mean": float(np.mean(row_means)),
                        "std": float(np.std(row_means)),
                    },
                    "stds": {
                        "min": float(np.min(row_stds)),
                        "max": float(np.max(row_stds)),
                        "mean": float(np.mean(row_stds)),
                        "std": float(np.std(row_stds)),
                    },
                }

            # For dimension 1 (features/columns)
            if arr.shape[1] > 1:  # Only if we have more than one feature
                col_means = np.mean(arr, axis=0)
                col_stds = np.std(arr, axis=0)
                dim_stats["dim1"] = {
                    "means": {
                        "min": float(np.min(col_means)),
                        "max": float(np.max(col_means)),
                        "mean": float(np.mean(col_means)),
                        "std": float(np.std(col_means)),
                    },
                    "stds": {
                        "min": float(np.min(col_stds)),
                        "max": float(np.max(col_stds)),
                        "mean": float(np.mean(col_stds)),
                        "std": float(np.std(col_stds)),
                    },
                }

            info["dimensions"] = dim_stats
    else:
        # For non-numeric arrays, just count unique values
        try:
            info["unique_values"] = len(np.unique(arr))
        except Exception:
            info["unique_values"] = "Could not compute"

    return info
