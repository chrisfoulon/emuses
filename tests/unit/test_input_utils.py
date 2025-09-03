import numpy as np
import nibabel as nib
import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from emuses.tools.inputs_utils import detect_dataset_type, process_images, mnist_features_to_input_matrix, \
    load_and_preprocess_digits_dataset, nifti_dataset_to_matrix, spreadsheet_to_input_df, prepare_input_matrix


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
    # Creating a dummy NIfTI image using real test data
    project_root = Path(__file__).parent.parent.parent
    features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
    # Use real data reshaped to 5x5x5 (125 total values needed)
    flat_data = features.flatten()  # Flatten all real data
    data = np.tile(flat_data, (125 // len(flat_data) + 1))[:125].reshape(5, 5, 5)
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
    # Use real test data for MNIST-like testing
    project_root = Path(__file__).parent.parent.parent
    real_features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
    real_targets = pd.read_csv(project_root / 'test_data/regression_scores_multitarget.csv', header=None).values
    
    # Create MNIST-like data by tiling and reshaping real data
    n_samples = 100
    mnist_size = 28 * 28  # 784 features
    
    # Tile real features to create enough data
    real_flat = real_features.flatten()
    tiles_needed = (n_samples * mnist_size) // len(real_flat) + 1
    features = np.tile(real_flat, tiles_needed)[:n_samples * mnist_size]
    features = features.reshape(n_samples, mnist_size)
    
    # Create labels from real targets (scaled to 0-9 range)
    labels = np.tile(real_targets[:, 0], (n_samples // len(real_targets) + 1))[:n_samples]
    labels = ((labels - labels.min()) / (labels.max() - labels.min()) * 9).astype(int)
    
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
    with patch("emuses.tools.inputs_utils.fetch_openml") as mock_fetch_openml:
        # Use real test data for mock return
        project_root = Path(__file__).parent.parent.parent
        real_features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
        real_targets = pd.read_csv(project_root / 'test_data/regression_scores_multitarget.csv', header=None).values
        
        # Create realistic mock data
        real_flat = real_features.flatten()
        tiles_needed = (100 * 784) // len(real_flat) + 1
        mock_features = np.tile(real_flat, tiles_needed)[:100 * 784].reshape(100, 784)
        mock_labels = np.tile(real_targets[:, 0], (100 // len(real_targets) + 1))[:100]
        mock_labels = ((mock_labels - mock_labels.min()) / (mock_labels.max() - mock_labels.min()) * 9).astype(int)
        
        mock_fetch_openml.return_value = (mock_features, mock_labels)
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


def test_spreadsheet_to_input_df(sample_csv_file):
    # Test the spreadsheet to input matrix conversion
    inputs_df = spreadsheet_to_input_df(sample_csv_file, header=0)
    expected_columns = pd.read_csv(sample_csv_file, header=0).T.columns.tolist()

    print(inputs_df.columns.tolist())
    print(expected_columns)

    assert inputs_df.shape[1] == len(expected_columns), "The number of columns in the loaded DataFrame is incorrect."
    for column in expected_columns:
        assert column in inputs_df.columns.tolist(), f"Column '{column}' not loaded properly from CSV."
    assert not inputs_df.isnull().values.any(), "DataFrame contains NaN values."


def test_prepare_input_matrix(sample_image_files):
    # Test the prepare_input_matrix function for 'image' dataset type
    paths = list(sample_image_files.glob("*.jpg"))
    input_matrix = prepare_input_matrix(paths, dataset_type="image")
    assert input_matrix.shape[0] == len(paths), "Prepared input matrix does not match the number of image files."
    assert not np.isnan(input_matrix).any(), "Input matrix contains NaN values."


if __name__ == "__main__":
    pytest.main()