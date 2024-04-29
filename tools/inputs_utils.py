import os
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor
from typing import List, Optional, Tuple

import numpy as np
import nibabel as nib
from bcblib.tools.nifti_utils import reorient_to_canonical
from tqdm import tqdm
from PIL import Image
from scipy.sparse import lil_matrix

from tools.data_preproc import normalise_colours_in_array, rescale_image_array, find_min_resolution


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
