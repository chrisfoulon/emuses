import argparse
import os
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import nibabel as nib
import pandas as pd
from bcblib.tools.nifti_utils import reorient_to_canonical
from bcblib.tools.general_utils import file_to_list
from tqdm import tqdm
from PIL import Image
from scipy.sparse import lil_matrix
from bids import BIDSLayout

from emuses.tools.data_preproc import find_min_resolution


from sklearn.datasets import fetch_openml, load_digits


def load_and_preprocess_digits_dataset(dataset='digits'):
    """
    Downloads the specified dataset if it's not already on the machine and preprocesses it to make an input matrix for
    UMAP training.

    Parameters:
    - dataset (str): The name of the dataset to load. Options are 'mnist' or 'digits'.

    Returns:
    - features (ndarray): The preprocessed feature matrix.
    - labels (ndarray): The labels for the dataset.
    """
    if dataset == 'mnist':
        # Download the MNIST dataset
        features, labels = fetch_openml('mnist_784', version=1, return_X_y=True)

        # Normalize the pixel values to be between 0 and 1
        features_normalized = features / 255.0

    elif dataset == 'digits':
        # Load the Digits dataset
        digits = load_digits()
        print(f'Shape of digits data: {digits.data.shape}')
        features = digits.data
        labels = digits.target

        # Normalize the pixel values to be between 0 and 1
        features_normalized = features / 16.0  # Digits data is already scaled between 0 and 16

    else:
        raise ValueError("Unsupported dataset. Choose 'mnist' or 'digits'.")

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
        extension = ''.join(file_path.suffixes)
        if extension in ['.jpg', '.png']:
            dataset_type = 'image'
            break
        elif extension in ['.nii', '.nii.gz']:
            dataset_type = 'nifti'
            break
        elif extension in ['.csv', '.xlsx', '.xls']:
            dataset_type = 'spreadsheet'
            break
        else:
            raise ValueError(f"Unsupported file format: {extension}")
    return dataset_type


def nifti_dataset_to_matrix(nifti_list: List[nib.Nifti1Image], pre_allocate_memory: bool = True,
                            disable_progress: bool = False) -> np.ndarray:
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


def image_paths_list_to_matrix_old(image_paths_list: List[os.PathLike], rescale: Optional[bool] = False,
                               output_shape: Optional[Tuple[int, int]] = None,
                               disable_progress: Optional[bool] = False) -> lil_matrix:
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

    print(f'Output shape: {output_shape}')
    print(f'Flattened size: {flattened_size}')
    print(f'out_matrix shape: {out_matrix.shape}')

    print('Converting images to matrix')
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
            images.append(img_array.flatten())  # Flatten if necessary or adapt based on UMAP needs
    return np.array(images)


def spreadsheet_to_input_df(file_path, header=None, index_col=None, filter_columns_list=None,
                            filter_rows_list=None, columns_are_features=False):
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
    if str(file_path).endswith('.csv'):
        df = pd.read_csv(file_path, header=header, index_col=index_col)
    else:
        df = pd.read_excel(file_path, header=header, index_col=index_col)

    # Filter columns if a list is provided
    if filter_columns_list is not None:
        df = df[filter_columns_list]

    # Filter rows if a list is provided
    if filter_rows_list is not None:
        df = df.loc[filter_rows_list]

    # Transpose the DataFrame if columns_are_features is True
    if not columns_are_features:
        df = df.transpose()

    # Remove constant columns
    constant_columns = df.columns[df.nunique() <= 1].tolist()
    if constant_columns:
        print(f"Removed constant columns: {constant_columns}")
        df = df.loc[:, df.nunique() > 1]

    # Convert boolean columns to integers
    boolean_columns = df.select_dtypes(include=['bool']).columns.tolist()
    if boolean_columns:
        print(f"Converted boolean columns to integers: {boolean_columns}")
        for col in boolean_columns:
            df[col] = df[col].astype(int)

    # Handle object columns
    columns_to_remove = []
    unprocessable_examples = {}
    for col in df.select_dtypes(include=['object']).columns:
        try:
            # Attempt to parse as datetime with a specified format
            df[col] = pd.to_datetime(df[col], format='%Y-%m-%d', errors='raise')
        except (ValueError, TypeError):
            try:
                # Attempt to parse as time-only and convert to timedelta
                df[col] = pd.to_datetime(df[col], format='%H:%M:%S', errors='raise').dt.time
                df[col] = pd.to_timedelta(df[col].astype(str))
            except (ValueError, TypeError):
                try:
                    # Attempt to parse as timedelta
                    df[col] = pd.to_timedelta(df[col], errors='raise')
                except (ValueError, TypeError):
                    try:
                        # Attempt to convert to numeric
                        df[col] = pd.to_numeric(df[col], errors='raise')
                    except ValueError:
                        # Mark column for removal if all attempts fail
                        columns_to_remove.append(col)
                        unprocessable_examples[col] = df[col].dropna().unique()[:5].tolist()

    # Show examples of unprocessable columns
    if unprocessable_examples:
        for col, examples in unprocessable_examples.items():
            print(f"Column '{col}' could not be converted. Examples: {examples}")

    # Remove columns that couldn't be converted
    if columns_to_remove:
        print(f"Removed unprocessable object columns: {columns_to_remove}")
        df.drop(columns=columns_to_remove, inplace=True)

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
    if dataset_type == 'image':
        min_res = find_min_resolution(paths_list)
        return process_images(paths_list, min_res)
    elif dataset_type == 'nifti':
        return nifti_dataset_to_matrix(paths_list)
    elif dataset_type == 'mnist':
        mnist_features_normalized, _ = load_and_preprocess_digits_dataset()
        return mnist_features_to_input_matrix(mnist_features_normalized)
    else:
        raise ValueError(f"Unsupported dataset type: {dataset_type}")


def prepare_scores(scores, embeddings_shape):
    """Prepare and validate the scores."""
    scores = np.vectorize(float)(scores)
    print(f"Scores shape: {scores.shape}")
    print(f"Embeddings shape: {embeddings_shape}")
    if scores.ndim == 1:
        scores = scores.reshape(-1, 1)
    if scores.shape[0] != embeddings_shape[0]:
        raise ValueError("Scores length must match the number of embeddings")
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
            files = layout.get(**filters, extension=['.nii', '.nii.gz'])
        else:
            files = layout.get(extension=['.nii', '.nii.gz'])
        paths_list = [f.path for f in files]

        if verbose:
            print(f'Found {len(paths_list)} files with filters {filters} in BIDS dataset at {folder_path}')

        if len(paths_list) == 0:
            raise argparse.ArgumentTypeError(f"No files found with filters {filters} in BIDS dataset at {folder_path}")

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
    return (folder_path / 'dataset_description.json').exists()
