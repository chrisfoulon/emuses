"""
Unit tests for --input_file_list functionality.

Tests the ability to provide CSV/Excel/TXT files containing paths to images or NIfTI files,
with automatic dataset type detection based on the actual file extensions (not the container file).
"""

import numpy as np
import nibabel as nib
import pandas as pd
import pytest
from pathlib import Path
from PIL import Image

from bcblib.tools.general_utils import file_to_list
from emuses.tools.inputs_utils import detect_dataset_type


@pytest.fixture
def nifti_files_with_csv_list(tmp_path):
    """Create NIfTI files and a CSV list containing their paths."""
    nifti_paths = []
    for i in range(3):
        nifti_path = tmp_path / f"sub-{i:02d}_T1w.nii.gz"
        # Create minimal valid NIfTI
        img = nib.Nifti1Image(np.random.rand(5, 5, 5), np.eye(4))
        nib.save(img, nifti_path)
        nifti_paths.append(str(nifti_path))

    # Create CSV file list
    csv_path = tmp_path / "file_list.csv"
    pd.DataFrame({'path': nifti_paths}).to_csv(csv_path, index=False)

    return csv_path, nifti_paths


@pytest.fixture
def image_files_with_excel_list(tmp_path):
    """Create image files and an Excel list containing their paths."""
    image_paths = []
    for i in range(3):
        img_path = tmp_path / f"image_{i:02d}.jpg"
        img = Image.new("RGB", (28, 28), color=(i * 40, i * 40, i * 40))
        img.save(img_path)
        image_paths.append(str(img_path))

    # Create Excel file list
    excel_path = tmp_path / "file_list.xlsx"
    pd.DataFrame({'path': image_paths}).to_excel(excel_path, index=False)

    return excel_path, image_paths


@pytest.fixture
def nifti_files_with_txt_list(tmp_path):
    """Create NIfTI files and a text file list (newline-delimited)."""
    nifti_paths = []
    for i in range(3):
        nifti_path = tmp_path / f"sub-{i:02d}_T1w.nii.gz"
        img = nib.Nifti1Image(np.random.rand(5, 5, 5), np.eye(4))
        nib.save(img, nifti_path)
        nifti_paths.append(str(nifti_path))

    # Create text file list (newline-delimited)
    txt_path = tmp_path / "file_list.txt"
    txt_path.write_text('\n'.join(nifti_paths))

    return txt_path, nifti_paths


def test_csv_file_list_loads_correctly(nifti_files_with_csv_list):
    """Test that file_to_list correctly reads CSV file."""
    csv_path, expected_paths = nifti_files_with_csv_list

    # Load paths using file_to_list
    paths_array = file_to_list(csv_path)

    # Verify we got the right number of paths
    assert len(paths_array) == len(expected_paths)

    # Verify paths match (convert to Path for comparison)
    loaded_paths = [str(Path(p)) for p in paths_array if p.strip()]
    assert set(loaded_paths) == set(expected_paths)


def test_csv_file_list_nifti_detection(nifti_files_with_csv_list):
    """CSV with NIfTI paths should detect as 'nifti' dataset."""
    csv_path, _ = nifti_files_with_csv_list

    # Load paths and detect type
    paths_array = file_to_list(csv_path)
    paths = [Path(p) for p in paths_array if p.strip()]
    dataset_type = detect_dataset_type(paths)

    assert dataset_type == "nifti", f"Expected 'nifti', got '{dataset_type}'"


def test_excel_file_list_image_detection(image_files_with_excel_list):
    """Excel with image paths should detect as 'image' dataset."""
    excel_path, _ = image_files_with_excel_list

    # Load paths and detect type
    paths_array = file_to_list(excel_path)
    paths = [Path(p) for p in paths_array if p.strip()]
    dataset_type = detect_dataset_type(paths)

    assert dataset_type == "image", f"Expected 'image', got '{dataset_type}'"


def test_txt_file_list_nifti_detection(nifti_files_with_txt_list):
    """Text file with NIfTI paths should detect as 'nifti' dataset."""
    txt_path, _ = nifti_files_with_txt_list

    # Load paths and detect type
    # Note: numpy.loadtxt reads line-by-line by default with dtype=str
    paths_array = file_to_list(txt_path)
    paths = [Path(p) for p in paths_array if p.strip()]
    dataset_type = detect_dataset_type(paths)

    assert dataset_type == "nifti", f"Expected 'nifti', got '{dataset_type}'"


def test_file_list_with_missing_paths(tmp_path):
    """File list with non-existent paths should be detectable."""
    # Create CSV with fake paths
    fake_paths = [
        "/nonexistent/path/sub-01.nii.gz",
        "/nonexistent/path/sub-02.nii.gz",
        "/nonexistent/path/sub-03.nii.gz"
    ]
    csv_path = tmp_path / "fake_list.csv"
    pd.DataFrame({'path': fake_paths}).to_csv(csv_path, index=False)

    # Load paths
    paths_array = file_to_list(csv_path)
    paths = [Path(p) for p in paths_array if p.strip()]

    # Verify we can detect missing paths
    missing_paths = [p for p in paths if not p.exists()]
    assert len(missing_paths) == 3, "Should detect all missing paths"


def test_file_list_empty(tmp_path):
    """Empty file list should return empty array."""
    csv_path = tmp_path / "empty_list.csv"
    pd.DataFrame({'path': []}).to_csv(csv_path, index=False)

    paths_array = file_to_list(csv_path)
    paths = [Path(p) for p in paths_array if p.strip()]

    assert len(paths) == 0, "Empty file list should yield empty path array"


def test_file_list_with_whitespace(tmp_path):
    """File list with whitespace should be handled correctly."""
    # Create one real NIfTI file
    nifti_path = tmp_path / "test.nii.gz"
    img = nib.Nifti1Image(np.random.rand(5, 5, 5), np.eye(4))
    nib.save(img, nifti_path)

    # Create CSV with whitespace
    csv_path = tmp_path / "list_with_whitespace.csv"
    csv_content = f"path\n  {nifti_path}  \n"
    csv_path.write_text(csv_content)

    # Load and clean paths
    paths_array = file_to_list(csv_path)
    paths = [Path(p.strip()) for p in paths_array if p.strip()]

    assert len(paths) == 1
    assert paths[0] == nifti_path


def test_csv_multicolumn_flattens(tmp_path):
    """CSV with multiple columns should flatten all values."""
    # Create a few NIfTI files
    nifti_paths_col1 = []
    nifti_paths_col2 = []
    for i in range(2):
        path1 = tmp_path / f"sub-{i:02d}_T1w.nii.gz"
        path2 = tmp_path / f"sub-{i:02d}_T2w.nii.gz"
        img = nib.Nifti1Image(np.random.rand(5, 5, 5), np.eye(4))
        nib.save(img, path1)
        nib.save(img, path2)
        nifti_paths_col1.append(str(path1))
        nifti_paths_col2.append(str(path2))

    # Create CSV with two columns
    csv_path = tmp_path / "multicolumn_list.csv"
    pd.DataFrame({
        'T1w': nifti_paths_col1,
        'T2w': nifti_paths_col2
    }).to_csv(csv_path, index=False)

    # Load paths - should get all 4 paths (flattened)
    paths_array = file_to_list(csv_path)
    # Filter out potential header text
    paths = [Path(p) for p in paths_array if p.strip() and Path(p).exists()]

    # Should have 4 NIfTI files total (2 from each column)
    assert len(paths) == 4, f"Expected 4 paths, got {len(paths)}"
    assert all(p.exists() for p in paths), "All paths should exist"


def test_mixed_file_types_first_wins(tmp_path):
    """File list with mixed types should detect based on first file."""
    # Create one image and one NIfTI
    img_path = tmp_path / "image.jpg"
    img = Image.new("RGB", (28, 28), color=(100, 100, 100))
    img.save(img_path)

    nifti_path = tmp_path / "scan.nii.gz"
    nifti_img = nib.Nifti1Image(np.random.rand(5, 5, 5), np.eye(4))
    nib.save(nifti_img, nifti_path)

    # CSV with image first
    csv_path_image_first = tmp_path / "image_first.csv"
    pd.DataFrame({'path': [str(img_path), str(nifti_path)]}).to_csv(
        csv_path_image_first, index=False
    )

    paths_array = file_to_list(csv_path_image_first)
    paths = [Path(p) for p in paths_array if p.strip()]
    dataset_type = detect_dataset_type(paths)

    assert dataset_type == "image", "First file type should win (image)"

    # CSV with NIfTI first
    csv_path_nifti_first = tmp_path / "nifti_first.csv"
    pd.DataFrame({'path': [str(nifti_path), str(img_path)]}).to_csv(
        csv_path_nifti_first, index=False
    )

    paths_array = file_to_list(csv_path_nifti_first)
    paths = [Path(p) for p in paths_array if p.strip()]
    dataset_type = detect_dataset_type(paths)

    assert dataset_type == "nifti", "First file type should win (nifti)"


def test_file_list_nonexistent_list_file():
    """Attempting to load non-existent file list should raise ValueError."""
    with pytest.raises(ValueError, match="does not exist"):
        file_to_list("/nonexistent/file_list.csv")
