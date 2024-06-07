import os
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import nibabel as nib
import pandas as pd
from bcblib.tools.nifti_utils import reorient_to_canonical, file_to_list
from bcblib.tools.spreadsheet_io_utils import str_to_column_id
from tqdm import tqdm
from PIL import Image
from scipy.sparse import lil_matrix
from sklearn.datasets import fetch_openml

from tools.data_preproc import normalise_colours_in_array, rescale_image_array, find_min_resolution


from sklearn.datasets import fetch_openml


def load_and_preprocess_mnist_dataset():
    """
    Downloads the MNIST dataset if it's not already on the machine and preprocesses it to make an input matrix for
    UMAP training.
    """
    # Download the MNIST dataset
    mnist_features, mnist_labels = fetch_openml('mnist_784', version=1, return_X_y=True)

    # Preprocess the MNIST dataset
    # Normalize the pixel values to be between 0 and 1
    mnist_features_normalized = mnist_features / 255.0

    return mnist_features_normalized, mnist_labels


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


def load_inputs_scores_spreadsheet(file_path, inputs_columns=None, scores_column=None, header=None, index_col=None):
    """
    Load the inputs and scores from a spreadsheet.

    Parameters:
    ----------
    file_path : str
        Path to the spreadsheet.
    inputs_columns : list of int or list of str
        List of indices or names of the columns containing the inputs.
    scores_column : int or str
        Index or name of the column containing the scores.
    header : int, optional
        Index of the header row.
    index_col : int, optional
        Index of the column containing the row indices.

    Returns:
    -------
    inputs : np.ndarray
        Matrix containing the inputs.
    scores : np.ndarray
        Array containing the scores.
    """

    path = Path(file_path)
    if path.suffix == '.csv':
        df = pd.read_csv(path, header=header, index_col=index_col)
    elif path.suffix in ['.xlsx', '.xls']:
        df = pd.read_excel(path, header=header, index_col=index_col)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")

    # Determine scores column
    if scores_column is None:
        scores_column = df.columns[-1]
    else:
        scores_column = str_to_column_id(scores_column, df)

    # Determine inputs columns
    if inputs_columns is None:
        inputs_columns = [col for col in df.columns if col != scores_column]
    else:
        inputs_columns = [str_to_column_id(col, df) for col in inputs_columns]

    # Filter out rows where scores are NaN
    df = df.dropna(subset=[scores_column])

    # Extract inputs and scores in a filtered df
    filtered_df = df[inputs_columns + [scores_column]]

    return filtered_df


def create_heatmap_data(dls, new_dataset, scores_file=None):
    """
    Prepare the DataFrame with embeddings and scores for creating a heatmap.
    Parameters:
    - dls: DiscreteLatentSpace
        The DLS object.
    - new_dataset: str
        Path to the new dataset (spreadsheet or text file).
    - scores_file: str, optional
        Separate file for scores if not in new_dataset.

    Returns:
    - embeddings, scores: np.ndarray, np.ndarray
    """
    if scores_file and new_dataset is None:  # Case 1: Separate scores file
        scores = file_to_list(scores_file)
        embeddings = dls.raw_embeddings
        if len(scores) != len(embeddings):
            raise ValueError("Scores and embeddings must have the same length.")
    else:  # Case 2: Spreadsheet with inputs and scores
        inputs, scores = load_inputs_scores_spreadsheet(new_dataset)
        # if inputs are just a list of paths we need to use one of the functions to create an input matrix
        # otherwise, we need to make a matrix with the values in the inputs
        if isinstance(inputs, list):
            if inputs[0].endswith('.nii') or inputs[0].endswith('.nii.gz'):
                inputs = nifti_dataset_to_matrix([nib.load(p) for p in inputs])
            elif inputs[0].endswith('.jpg') or inputs[0].endswith('.png'):
                inputs = process_images(inputs)
            else:
                raise ValueError(f"Unsupported file format: {Path(inputs[0]).suffix}")
        embeddings = dls.trained_umap.transform(inputs)

    return embeddings, scores

