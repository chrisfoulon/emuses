import numpy as np
from PIL import Image
from sklearn.preprocessing import MinMaxScaler
from tqdm import tqdm


def normalize_input_matrix(input_matrix):
    scaler = MinMaxScaler()
    normalised_matrix = scaler.fit_transform(input_matrix)
    return normalised_matrix


def find_min_resolution(image_paths_list):
    min_width = min_height = float("inf")
    for img_path in image_paths_list:
        img = Image.open(img_path)
        width, height = img.size
        min_width = min(min_width, width)
        min_height = min(min_height, height)
    return min_width, min_height


def find_max_resolution(image_paths_list):
    max_width = max_height = 0
    for img_path in image_paths_list:
        img = Image.open(img_path)
        width, height = img.size
        max_width = max(max_width, width)
        max_height = max(max_height, height)
    return max_width, max_height


def rescale_image_array(images_list, output_shape=None):
    """
    Rescale the resolution of all the images in images_array to output_shape. If no output_shape is provided, the
    resolution is rescaled to the minimum resolution of all the images in images_list.
    Modifies the images in place
    Parameters
    ----------
    images_list: list/array of PIL images
        list of images to rescale
    output_shape

    Returns
    -------

    """
    # If output_shape is not provided, find the minimum resolution among all images
    if output_shape is None:
        min_width = min_height = float("inf")
        for img in images_list:
            width, height = img.size
            min_width = min(min_width, width)
            min_height = min(min_height, height)
        output_shape = (min_width, min_height)

    # Rescale each image to output_shape
    for i in tqdm(range(len(images_list))):
        images_list[i] = images_list[i].resize(output_shape)


def normalise_colours_in_array(images_list):
    """
    Normalise the colours in the images in images_list to the range [0, 1] by dividing by 255 (for 8-bit images)
    Modifies the images in place
    Parameters
    ----------
    images_list

    Returns
    -------

    """
    for i in tqdm(range(len(images_list))):
        images_list[i] = np.array(images_list[i]) / 255


def filter_nan_rows(coords: np.ndarray, scores: np.ndarray):
    """
    Remove rows where `scores` is NaN.  Returns (X_clean, y_clean, mask).
    """
    mask = ~np.isnan(scores)
    return coords[mask], scores[mask], mask
