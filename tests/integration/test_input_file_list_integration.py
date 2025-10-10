"""
Integration tests for --input_file_list flag with full pipeline.

Tests end-to-end functionality of providing file lists (CSV/Excel/TXT)
as input to the EMUSES pipeline.
"""

import numpy as np
import nibabel as nib
import pandas as pd
import pytest
from pathlib import Path
from PIL import Image

from emuses.pipelines.emuses_pipeline import EMUSESPipeline


@pytest.fixture
def nifti_dataset_with_csv_list(tmp_path):
    """Create a complete NIfTI dataset with CSV file list and scores."""
    # Create NIfTI files
    nifti_paths = []
    for i in range(5):
        nifti_path = tmp_path / f"sub-{i:02d}_T1w.nii.gz"
        # Create minimal valid NIfTI with distinct data
        img = nib.Nifti1Image(
            np.random.RandomState(i).rand(10, 10, 10),
            np.eye(4)
        )
        nib.save(img, nifti_path)
        nifti_paths.append(str(nifti_path))

    # Create CSV file list
    csv_path = tmp_path / "nifti_file_list.csv"
    pd.DataFrame({'nifti_path': nifti_paths}).to_csv(csv_path, index=False)

    # Create scores file
    scores_path = tmp_path / "scores.csv"
    scores = np.random.RandomState(42).randn(5)
    pd.DataFrame({'score': scores}).to_csv(scores_path, index=False)

    # Create output directory
    output_path = tmp_path / "output"
    output_path.mkdir()

    return {
        'file_list': csv_path,
        'scores': scores_path,
        'output': output_path,
        'num_files': len(nifti_paths)
    }


@pytest.fixture
def image_dataset_with_excel_list(tmp_path):
    """Create a complete image dataset with Excel file list and scores."""
    # Create image files
    image_paths = []
    for i in range(5):
        img_path = tmp_path / f"image_{i:02d}.jpg"
        img = Image.new("RGB", (28, 28), color=(i * 40, i * 40, i * 40))
        img.save(img_path)
        image_paths.append(str(img_path))

    # Create Excel file list
    excel_path = tmp_path / "image_file_list.xlsx"
    pd.DataFrame({'image_path': image_paths}).to_excel(excel_path, index=False)

    # Create scores file
    scores_path = tmp_path / "scores.csv"
    scores = np.random.RandomState(42).randn(5)
    pd.DataFrame({'score': scores}).to_csv(scores_path, index=False)

    # Create output directory
    output_path = tmp_path / "output"
    output_path.mkdir()

    return {
        'file_list': excel_path,
        'scores': scores_path,
        'output': output_path,
        'num_files': len(image_paths)
    }


def test_pipeline_with_nifti_csv_file_list(nifti_dataset_with_csv_list):
    """Test full pipeline with NIfTI dataset provided via CSV file list."""
    dataset = nifti_dataset_with_csv_list

    # Create args object
    args = type('Args', (), {})()
    args.input_dataset = str(dataset['file_list'])
    args.input_file_list = True  # ← KEY FLAG
    args.scores = str(dataset['scores'])
    args.output_folder = dataset['output']
    args.test_size = 0.2
    args.random_state = 42

    # Parameters that should be passed through
    args.label_dataset = None
    args.load_embeddings = None
    args.bids_filters = None
    args.input_header = 0
    args.input_index_column = None
    args.inputs_columns = None
    args.columns_are_features = False
    args.recursive_input_file_search = False
    args.input_file_types = None
    args.arg_separator = ","
    args.input_normalization = None
    args.scores_header = 0
    args.scores_index_column = None
    args.scores_are_rows = False
    args.scores_column = None
    args.scores_normalization = None
    args.filter_labelled_by_scores = False
    args.output_format_info = None

    # Create pipeline
    pipeline = EMUSESPipeline(args)

    # Verify dataset was processed correctly
    assert pipeline.dataset_type == "nifti", f"Expected 'nifti', got '{pipeline.dataset_type}'"
    assert pipeline.input_matrix is not None, "Input matrix should be populated"
    assert pipeline.input_matrix.shape[0] == dataset['num_files'], \
        f"Expected {dataset['num_files']} samples, got {pipeline.input_matrix.shape[0]}"
    assert pipeline.scores is not None, "Scores should be loaded"
    assert len(pipeline.scores) == dataset['num_files'], \
        f"Expected {dataset['num_files']} scores, got {len(pipeline.scores)}"


def test_pipeline_with_image_excel_file_list(image_dataset_with_excel_list):
    """Test full pipeline with image dataset provided via Excel file list."""
    dataset = image_dataset_with_excel_list

    # Create args object
    args = type('Args', (), {})()
    args.input_dataset = str(dataset['file_list'])
    args.input_file_list = True  # ← KEY FLAG
    args.scores = str(dataset['scores'])
    args.output_folder = dataset['output']
    args.test_size = 0.2
    args.random_state = 42

    # Parameters that should be passed through
    args.label_dataset = None
    args.load_embeddings = None
    args.bids_filters = None
    args.input_header = 0
    args.input_index_column = None
    args.inputs_columns = None
    args.columns_are_features = False
    args.recursive_input_file_search = False
    args.input_file_types = None
    args.arg_separator = ","
    args.input_normalization = None
    args.scores_header = 0
    args.scores_index_column = None
    args.scores_are_rows = False
    args.scores_column = None
    args.scores_normalization = None
    args.filter_labelled_by_scores = False
    args.output_format_info = None

    # Create pipeline
    pipeline = EMUSESPipeline(args)

    # Verify dataset was processed correctly
    assert pipeline.dataset_type == "image", f"Expected 'image', got '{pipeline.dataset_type}'"
    assert pipeline.input_matrix is not None, "Input matrix should be populated"
    assert pipeline.input_matrix.shape[0] == dataset['num_files'], \
        f"Expected {dataset['num_files']} samples, got {pipeline.input_matrix.shape[0]}"
    assert pipeline.scores is not None, "Scores should be loaded"
    assert len(pipeline.scores) == dataset['num_files'], \
        f"Expected {dataset['num_files']} scores, got {len(pipeline.scores)}"


def test_pipeline_without_flag_uses_normal_behavior(tmp_path):
    """Test that omitting --input_file_list flag preserves normal CSV behavior."""
    # Create a CSV with numeric data (normal spreadsheet dataset)
    csv_path = tmp_path / "numeric_data.csv"
    data = np.random.rand(10, 5)
    pd.DataFrame(data, columns=[f'feature_{i}' for i in range(5)]).to_csv(
        csv_path, index=False
    )

    # Create scores
    scores_path = tmp_path / "scores.csv"
    scores = np.random.randn(10)
    pd.DataFrame({'score': scores}).to_csv(scores_path, index=False)

    # Create output directory
    output_folder = tmp_path / "output"
    output_folder.mkdir()

    # Create args object WITHOUT input_file_list flag
    args = type('Args', (), {})()
    args.input_dataset = str(csv_path)
    args.input_file_list = False  # ← Normal behavior
    args.scores = str(scores_path)
    args.output_folder = output_folder
    args.test_size = 0.2
    args.random_state = 42

    # Parameters for spreadsheet processing
    args.label_dataset = None
    args.load_embeddings = None
    args.bids_filters = None
    args.input_header = 0  # CSV has headers
    args.input_index_column = None
    args.inputs_columns = None
    args.columns_are_features = True  # Columns are features (normal)
    args.recursive_input_file_search = False
    args.input_file_types = None
    args.arg_separator = ","
    args.input_normalization = None
    args.scores_header = 0
    args.scores_index_column = None
    args.scores_are_rows = False
    args.scores_column = None
    args.scores_normalization = None
    args.filter_labelled_by_scores = False
    args.output_format_info = None

    # Create pipeline
    pipeline = EMUSESPipeline(args)

    # Verify it was treated as spreadsheet, not file list
    assert pipeline.dataset_type == "spreadsheet", \
        f"Expected 'spreadsheet', got '{pipeline.dataset_type}'"
    assert pipeline.input_matrix is not None
    assert pipeline.input_matrix.shape == (10, 5), \
        f"Expected shape (10, 5), got {pipeline.input_matrix.shape}"


def test_pipeline_file_list_with_missing_files_raises_error(tmp_path):
    """Test that file lists with missing files raise appropriate errors."""
    # Create CSV with non-existent paths
    csv_path = tmp_path / "fake_file_list.csv"
    fake_paths = [
        "/nonexistent/sub-01.nii.gz",
        "/nonexistent/sub-02.nii.gz"
    ]
    pd.DataFrame({'path': fake_paths}).to_csv(csv_path, index=False)

    # Create output directory
    output_folder = tmp_path / "output"
    output_folder.mkdir()

    # Create args object
    args = type('Args', (), {})()
    args.input_dataset = str(csv_path)
    args.input_file_list = True
    args.scores = None
    args.output_folder = output_folder
    args.test_size = 0.0  # No splitting to avoid score requirement
    args.random_state = 42

    args.label_dataset = None
    args.load_embeddings = None
    args.bids_filters = None
    args.input_header = 0
    args.input_index_column = None
    args.inputs_columns = None
    args.columns_are_features = False
    args.recursive_input_file_search = False
    args.input_file_types = None
    args.arg_separator = ","
    args.input_normalization = None
    args.scores_header = None
    args.scores_index_column = None
    args.scores_are_rows = False
    args.scores_column = None
    args.scores_normalization = None
    args.filter_labelled_by_scores = False
    args.output_format_info = None

    # Should raise ValueError about missing files
    with pytest.raises(ValueError, match="non-existent paths"):
        EMUSESPipeline(args)
