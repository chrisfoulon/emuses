import numpy as np
import pytest
import joblib
import optuna
from unittest.mock import patch, MagicMock

# Importing the functions from your module (adjust the import as needed)
from emuses.tools.UMAP_utils import (
    evaluate_embedding_statistics,
    train_and_save_umap_with_bayesian_search,
    is_umap_file,
    load_umap_model
)


@pytest.fixture
def small_input_data():
    # A small random input matrix (10 samples, 5 features)
    return np.random.rand(10, 5)


@pytest.fixture
def small_embeddings():
    # A tiny embedding (10 samples, 2D)
    return np.random.rand(10, 2)


def test_evaluate_embedding_statistics(small_embeddings):
    metrics_dict = {
        "spread": {"weight": 1.0, "target": 1.0, "epsilon": 0.1},
        "density_variability": {"weight": 1.2, "target": 0.4, "epsilon": 0.1},
        "entropy": {"weight": 1.5}
    }
    metrics = evaluate_embedding_statistics(small_embeddings, metrics_dict)
    expected_keys = {
        "spread",
        "density_variability",
        "entropy",
    }
    assert set(metrics.keys()) == expected_keys
    # Check that the values are numeric
    for val in metrics.values():
        assert isinstance(val, float) or isinstance(val, np.floating)


def test_is_umap_file():
    assert is_umap_file("model.joblib") is True
    assert is_umap_file("model.txt") is False
    assert is_umap_file("umap_model.joblib") is True
    assert is_umap_file("umap_model.jobli") is False


def test_load_umap_model_no_file(tmp_path):
    # No files exist, should return None and a next available filename
    loaded_model, filepath = load_umap_model(tmp_path)
    assert loaded_model is None
    assert filepath.exists() is False
    # filepath should be a generated name ending with .joblib
    assert filepath.suffix == ".joblib"


def test_load_umap_model_existing_file(tmp_path):
    # Create a fake joblib file
    dummy_model = {"umap": "fake_model"}
    filename = tmp_path / "umap_model_joblib1.3.2.joblib"  # adjust joblib version if needed
    joblib.dump(dummy_model, filename)

    loaded_model, filepath = load_umap_model(tmp_path, joblib_version_override="1.3.2")
    assert loaded_model is not None
    assert loaded_model["umap"] == "fake_model"
    assert filepath == filename


def test_load_umap_model_failing_file(tmp_path):
    # Create a file that is not actually a joblib object
    filename = tmp_path / "umap_model_joblib1.3.2.joblib"
    filename.write_text("Not a joblib model")

    # Determine the local joblib version
    local_joblib_version = joblib.__version__

    # Call the function to load the UMAP model
    loaded_model, filepath = load_umap_model(tmp_path, joblib_version_override="1.3.2")

    # Check that loading failed and the function returns None
    assert loaded_model is None, "The loaded model should be None when the file cannot be loaded."

    # Ensure the filepath corresponds to the file that would be saved for the local joblib version
    expected_filepath = tmp_path / f"umap_model_joblib{local_joblib_version}.joblib"
    assert str(filepath) == str(expected_filepath), (
        f"The filepath should point to the file for the local joblib version, "
        f"but got {filepath} instead of {expected_filepath}."
    )


@patch("emuses.tools.UMAP_utils.optuna.create_study")
@patch("emuses.tools.UMAP_utils.plot_embeddings", MagicMock())
def test_train_and_save_umap_with_bayesian_search(mock_study, small_input_data, tmp_path):
    # Mock study to return a simple best_params and best_value
    mock_study_instance = MagicMock()
    mock_study_instance.best_params = {"n_neighbors": 5, "min_dist": 0.1}
    mock_study_instance.best_value = 1.0
    mock_study.return_value = mock_study_instance

    # Set param_ranges for minimal search
    param_ranges = {
        "n_neighbors": {"type": "int", "low": 5, "high": 5},
        "min_dist": {"type": "float", "low": 0.1, "high": 0.1}
    }

    # Use minimal trials and fixed parameters to avoid heavy computation
    umap_model, embeddings, model_path, embeddings_path, input_matrix_path = train_and_save_umap_with_bayesian_search(
        small_input_data,
        tmp_path,
        param_ranges,
        n_trials=1,
        maximize_metrics={"spread": True}  # Just one metric for simplicity
    )

    # Check that files are saved
    assert model_path.exists()
    assert embeddings_path.exists()
    assert input_matrix_path.exists()

    # Check model and embeddings shape
    assert umap_model is not None
    # Since UMAP is run with fixed params, embeddings should have shape (10, 2) by default
    assert embeddings.shape[0] == small_input_data.shape[0]
    # We don't know the exact dimensionality but typically UMAP default is 2D
    assert embeddings.shape[1] == 2
