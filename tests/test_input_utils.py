import os
import sys
import numpy as np
import nibabel as nib
import pandas as pd
import pytest
from unittest.mock import patch
from pathlib import Path
from PIL import Image

from tools.inputs_utils import detect_dataset_type, process_images, mnist_features_to_input_matrix, \
    load_and_preprocess_digits_dataset, nifti_dataset_to_matrix, load_inputs_scores_spreadsheet, prepare_input_matrix


@pytest.fixture
def sample_image_files(tmp_path):
    # Creating some dummy image files for testing
    for i in range(3):
        img_path = tmp_path / f"image_{i}.jpg"
        img = Image.new("RGB", (28, 28), color=(i * 40, i * 40, i * 40))  # Create a simple image
        img.save(img_path)
    return tmp_path


@pytest.fixture
def sample_nifti_file(tmp_path):
    # Creating a dummy NIfTI image for testing
    data = np.random.rand(5, 5, 5)
    nifti_img = nib.Nifti1Image(data, affine=np.eye(4))
    nifti_path = tmp_path / "sample.nii"
    nib.save(nifti_img, nifti_path)
    return nifti_path


@pytest.fixture
def sample_csv_file(tmp_path):
    # Creating a dummy CSV file for testing
    csv_content = "input1,input2,score\n1,2,0.5\n3,4,0.8\n5,6,0.2"
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(csv_content)
    return csv_path


@pytest.fixture
def sample_mnist_data():
    # Generating synthetic MNIST-like data for testing
    features = np.random.rand(100, 28 * 28)  # 100 samples of flattened 28x28 images
    labels = np.random.randint(0, 10, 100)  # 100 labels between 0 and 9
    return features, labels


def test_detect_dataset_type(sample_image_files):
    # Test the dataset type detection function
    paths = list(sample_image_files.glob("*.jpg"))
    dataset_type = detect_dataset_type(paths)
    assert dataset_type == "image", f"Expected dataset type to be 'image', but got '{dataset_type}'"


def test_process_images(sample_image_files):
    # Test the image processing function
    paths = list(sample_image_files.glob("*.jpg"))
    min_res = (28, 28)  # Example resolution
    processed_images = process_images(paths, min_res)
    assert processed_images.shape[0] == len(paths), "Number of processed images does not match number of input images."
    assert not np.isnan(processed_images).any(), "Processed images contain NaN values."


def test_mnist_features_to_input_matrix(sample_mnist_data):
    # Test the MNIST features to input matrix conversion
    features, _ = sample_mnist_data
    input_matrix = mnist_features_to_input_matrix(pd.DataFrame(features))
    assert input_matrix.shape == features.shape, "Input matrix shape does not match features shape."
    assert not np.isnan(input_matrix).any(), "Input matrix contains NaN values."


def test_load_and_preprocess_digits_dataset():
    # Mock the dataset download to avoid repeated downloads
    with patch("tools.inputs_utils.fetch_openml") as mock_fetch_openml:
        mock_fetch_openml.return_value = (np.random.rand(100, 784), np.random.randint(0, 10, 100))
        features, labels = load_and_preprocess_digits_dataset()

    assert features.shape[0] == labels.shape[0], "Number of features does not match number of labels."
    assert features.ndim == 2, "Features should be a 2D array."
    assert labels.ndim == 1, "Labels should be a 1D array."
    assert not np.isnan(features).any(), "Features contain NaN values."
    assert not np.isnan(labels).any(), "Labels contain NaN values."


def test_nifti_dataset_to_matrix(sample_nifti_file):
    # Test the NIfTI dataset to matrix conversion
    nifti_list = [nib.load(str(sample_nifti_file))]
    output_matrix = nifti_dataset_to_matrix(nifti_list)
    assert output_matrix.shape == (1, 5 * 5 * 5), "NIfTI output matrix shape is incorrect."
    assert not np.isnan(output_matrix).any(), "Output matrix contains NaN values."


def test_load_inputs_scores_spreadsheet(sample_csv_file):
    # Test loading inputs and scores from a spreadsheet
    inputs_scores_df = load_inputs_scores_spreadsheet(str(sample_csv_file), header=0)
    expected_columns = pd.read_csv(sample_csv_file).columns.tolist()

    assert inputs_scores_df.shape[1] == len(
        expected_columns), "The number of columns in the loaded DataFrame is incorrect."
    for column in expected_columns:
        assert column in inputs_scores_df.columns, f"Column '{column}' not loaded properly from CSV."
    assert not inputs_scores_df.isnull().values.any(), "DataFrame contains NaN values."


def test_prepare_input_matrix(sample_image_files):
    # Test the prepare_input_matrix function for 'image' dataset type
    paths = list(sample_image_files.glob("*.jpg"))
    input_matrix = prepare_input_matrix(paths, dataset_type="image")
    assert input_matrix.shape[0] == len(paths), "Prepared input matrix does not match the number of image files."
    assert not np.isnan(input_matrix).any(), "Input matrix contains NaN values."


if __name__ == "__main__":
    pytest.main()