# filepath: s:\GIN Dropbox\Chris Foulon\EMUSE\package\emuses\emuses\tests\test_inference_api.py

"""
Comprehensive tests for the EMUSES Inference API.

This test suite validates:
- EMUSESInferenceAPI class functionality
- sklearn-like interface (.fit() and .predict() methods)
- Integration with existing ModelIOManager and pipeline system
- Feature utilities with inference mode support
- Error handling and edge cases
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import warnings

# Test imports
try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import Ridge, LinearRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

# Import the modules to test
from emuses.inference.api import EMUSESInferenceAPI
from emuses.inference import create_inference_api, get_default_config
from emuses.tools.model_io import ModelIOManager
from emuses.tools.correlation_maps_utils import (
    calculate_correlation_grid,
    calculate_correlation,
)
from emuses.tools.stats_utils import compute_all_gwd, compute_gwd_summary
from emuses.tools.features_utils import PCAGWD, KernelPCAGWD


# Test fixtures
@pytest.fixture
def sample_data():
    """Generate sample data for testing."""
    np.random.seed(42)  # For reproducibility
    n_samples = 100
    n_features = 50

    # Generate synthetic embeddings data
    X = np.random.randn(n_samples, n_features)
    y = np.random.randn(n_samples) + 0.1 * np.sum(
        X[:, :5], axis=1
    )  # y depends on first 5 features

    return X, y


@pytest.fixture
def sample_inference_data():
    """Generate sample inference data for testing."""
    np.random.seed(123)  # Different seed for inference data
    n_samples = 30
    n_features = 50

    X_test = np.random.randn(n_samples, n_features)
    return X_test


@pytest.fixture
def temp_model_dir():
    """Create temporary directory for model storage."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "model_type": "sklearn",
        "pipeline_config": {
            "feature_extraction": ["correlation", "gwd"],
            "dimensionality_reduction": "pca",
        },
        "save_intermediate": True,
        "verbose": True,
    }


class TestEMUSESInferenceAPI:
    """Test cases for the EMUSESInferenceAPI class."""

    def test_init_default_config(self):
        """Test initialization with default configuration."""
        api = EMUSESInferenceAPI()

        assert api.config is not None
        assert isinstance(api.config, dict)
        assert api.model_io_manager is not None
        assert isinstance(api.model_io_manager, ModelIOManager)
        assert not api._is_fitted
        assert api._training_embeddings is None
        assert api._model is None

    def test_init_custom_config(self, sample_config):
        """Test initialization with custom configuration."""
        api = EMUSESInferenceAPI(config=sample_config)

        assert api.config == sample_config
        assert api.config["model_type"] == "sklearn"
        assert api._is_fitted == False

    def test_init_custom_model_dir(self, temp_model_dir):
        """Test initialization with custom model directory."""
        api = EMUSESInferenceAPI(model_dir=temp_model_dir)

        assert api.model_io_manager.base_path == temp_model_dir

    @pytest.mark.skipif(not HAS_SKLEARN, reason="sklearn not available")
    def test_fit_basic(self, sample_data):
        """Test basic fit functionality."""
        X, y = sample_data
        api = EMUSESInferenceAPI()

        # Mock the model building to avoid complex dependencies
        with patch.object(api, "_build_model") as mock_build:
            mock_model = Mock()
            mock_model.fit.return_value = mock_model
            mock_build.return_value = mock_model

            # Test fit
            result = api.fit(X, y)

            # Assertions
            assert result == api  # Should return self for chaining
            assert api._is_fitted == True
            assert np.array_equal(api._training_embeddings, X)
            mock_build.assert_called_once()
            mock_model.fit.assert_called_once()

    def test_fit_invalid_input_shapes(self):
        """Test fit with invalid input shapes."""
        api = EMUSESInferenceAPI()

        # Mismatched shapes
        X = np.random.randn(100, 50)
        y = np.random.randn(90)  # Wrong number of samples

        with pytest.raises(ValueError, match="Number of samples"):
            api.fit(X, y)

    def test_fit_invalid_input_types(self):
        """Test fit with invalid input types."""
        api = EMUSESInferenceAPI()

        # Invalid X type
        with pytest.raises(TypeError, match="must be a numpy array"):
            api.fit("invalid", np.array([1, 2, 3]))

        # Invalid y type
        with pytest.raises(TypeError, match="must be a numpy array"):
            api.fit(np.array([[1, 2], [3, 4]]), "invalid")

    @pytest.mark.skipif(not HAS_SKLEARN, reason="sklearn not available")
    def test_predict_after_fit(self, sample_data, sample_inference_data):
        """Test predict functionality after fitting."""
        X, y = sample_data
        X_test = sample_inference_data

        api = EMUSESInferenceAPI()

        # Mock the model
        with patch.object(api, "_build_model") as mock_build:
            mock_model = Mock()
            mock_model.fit.return_value = mock_model
            mock_model.predict.return_value = np.random.randn(len(X_test))
            mock_build.return_value = mock_model

            # Fit first
            api.fit(X, y)

            # Test predict
            predictions = api.predict(X_test)

            # Assertions
            assert isinstance(predictions, np.ndarray)
            assert len(predictions) == len(X_test)
            mock_model.predict.assert_called_once()

    def test_predict_without_fit(self, sample_inference_data):
        """Test predict without fitting first."""
        api = EMUSESInferenceAPI()
        X_test = sample_inference_data

        with pytest.raises(ValueError, match="not been fitted"):
            api.predict(X_test)

    def test_predict_invalid_input_shape(self, sample_data, sample_inference_data):
        """Test predict with invalid input shape."""
        X, y = sample_data
        api = EMUSESInferenceAPI()

        # Mock fit
        with patch.object(api, "_build_model") as mock_build:
            mock_model = Mock()
            mock_model.fit.return_value = mock_model
            mock_build.return_value = mock_model
            api.fit(X, y)

            # Try to predict with wrong number of features
            X_wrong = np.random.randn(10, X.shape[1] + 5)  # Wrong feature count

            with pytest.raises(ValueError, match="feature dimensions"):
                api.predict(X_wrong)

    @pytest.mark.skipif(not HAS_SKLEARN, reason="sklearn not available")
    def test_save_and_load_model(self, sample_data, temp_model_dir):
        """Test model saving and loading functionality."""
        X, y = sample_data

        # Create and fit API
        api1 = EMUSESInferenceAPI(model_dir=temp_model_dir)

        with patch.object(api1, "_build_model") as mock_build:
            mock_model = Mock()
            mock_model.fit.return_value = mock_model
            mock_build.return_value = mock_model

            api1.fit(X, y)

            # Save model
            model_name = "test_model"
            api1.save_model(model_name)

            # Create new API and load model
            api2 = EMUSESInferenceAPI(model_dir=temp_model_dir)
            api2.load_model(model_name)

            # Check that model was loaded
            assert api2._is_fitted == True
            assert np.array_equal(api2._training_embeddings, X)

    def test_load_nonexistent_model(self, temp_model_dir):
        """Test loading a non-existent model."""
        api = EMUSESInferenceAPI(model_dir=temp_model_dir)

        with pytest.raises(FileNotFoundError):
            api.load_model("nonexistent_model")

    @pytest.mark.skipif(not HAS_SKLEARN, reason="sklearn not available")
    def test_build_model_sklearn(self, sample_config):
        """Test building sklearn model."""
        config = sample_config.copy()
        config["model_type"] = "sklearn"
        config["sklearn_model"] = "RandomForestRegressor"
        config["sklearn_params"] = {"n_estimators": 10, "random_state": 42}

        api = EMUSESInferenceAPI(config=config)
        model = api._build_model()

        assert isinstance(model, Pipeline)
        # Check that the final step is the expected model
        assert "model" in model.named_steps

    def test_build_model_invalid_type(self):
        """Test building model with invalid type."""
        config = {"model_type": "invalid_type"}
        api = EMUSESInferenceAPI(config=config)

        with pytest.raises(ValueError, match="Unsupported model type"):
            api._build_model()


class TestInferenceFeatureUtilities:
    """Test cases for feature utilities with inference mode support."""

    def test_correlation_grid_inference_mode(self):
        """Test correlation grid calculation in inference mode."""
        # Training data
        train_embeddings = np.random.randn(50, 100)

        # Inference data
        test_embeddings = np.random.randn(20, 100)

        # Test inference mode
        result = calculate_correlation_grid(
            test_embeddings, inference_mode=True, reference_embeddings=train_embeddings
        )

        assert isinstance(result, np.ndarray)
        assert result.shape[0] == len(test_embeddings)

    def test_correlation_inference_mode(self):
        """Test correlation calculation in inference mode."""
        # Training data
        train_embeddings = np.random.randn(50, 100)

        # Inference data
        test_embeddings = np.random.randn(20, 100)

        # Test inference mode
        result = calculate_correlation(
            test_embeddings, inference_mode=True, reference_embeddings=train_embeddings
        )

        assert isinstance(result, np.ndarray)
        assert result.shape[0] == len(test_embeddings)

    def test_gwd_functions_inference_mode(self):
        """Test GWD functions in inference mode."""
        # Training data
        train_embeddings = np.random.randn(50, 100)

        # Inference data
        test_embeddings = np.random.randn(20, 100)

        # Test compute_all_gwd in inference mode
        gwd_result = compute_all_gwd(
            test_embeddings, inference_mode=True, reference_embeddings=train_embeddings
        )

        assert isinstance(gwd_result, dict)
        assert "gwd_matrix" in gwd_result

        # Test compute_gwd_summary in inference mode
        summary_result = compute_gwd_summary(
            test_embeddings, inference_mode=True, reference_embeddings=train_embeddings
        )

        assert isinstance(summary_result, dict)

    def test_pcagwd_inference_mode(self):
        """Test PCAGWD class in inference mode."""
        # Training data
        train_embeddings = np.random.randn(50, 100)

        # Inference data
        test_embeddings = np.random.randn(20, 100)

        # Fit on training data
        pcagwd = PCAGWD(n_components=10)
        pcagwd.fit(train_embeddings)

        # Transform inference data (should compute GWD relative to training data)
        result = pcagwd.transform(test_embeddings)

        assert isinstance(result, np.ndarray)
        assert result.shape[0] == len(test_embeddings)
        assert result.shape[1] == 10  # n_components

    def test_kernel_pcagwd_inference_mode(self):
        """Test KernelPCAGWD class in inference mode."""
        # Training data
        train_embeddings = np.random.randn(30, 50)  # Smaller for kernel methods

        # Inference data
        test_embeddings = np.random.randn(10, 50)

        # Fit on training data
        kpcagwd = KernelPCAGWD(n_components=5, kernel="rbf")
        kpcagwd.fit(train_embeddings)

        # Transform inference data
        result = kpcagwd.transform(test_embeddings)

        assert isinstance(result, np.ndarray)
        assert result.shape[0] == len(test_embeddings)
        assert result.shape[1] == 5  # n_components


class TestInferenceAPIIntegration:
    """Integration tests for the complete inference API workflow."""

    @pytest.mark.skipif(not HAS_SKLEARN, reason="sklearn not available")
    def test_complete_workflow(
        self, sample_data, sample_inference_data, temp_model_dir
    ):
        """Test complete fit -> predict -> save -> load workflow."""
        X_train, y_train = sample_data
        X_test = sample_inference_data

        # Create API with comprehensive config
        config = {
            "model_type": "sklearn",
            "sklearn_model": "LinearRegression",
            "pipeline_config": {
                "feature_extraction": ["correlation"],
                "standardize": True,
            },
        }

        api = EMUSESInferenceAPI(config=config, model_dir=temp_model_dir)

        # Mock feature extraction to avoid complexity
        with patch("emuses.inference.api.calculate_correlation") as mock_corr:
            mock_corr.return_value = np.random.randn(len(X_train), 10)

            # Fit the model
            api.fit(X_train, y_train)

            # Make predictions
            with patch("emuses.inference.api.calculate_correlation") as mock_corr_pred:
                mock_corr_pred.return_value = np.random.randn(len(X_test), 10)
                predictions = api.predict(X_test)

            assert isinstance(predictions, np.ndarray)
            assert len(predictions) == len(X_test)

            # Save model
            model_name = "integration_test_model"
            api.save_model(model_name)

            # Load model in new API instance
            api2 = EMUSESInferenceAPI(config=config, model_dir=temp_model_dir)
            api2.load_model(model_name)

            # Make predictions with loaded model
            with patch("emuses.inference.api.calculate_correlation") as mock_corr_pred2:
                mock_corr_pred2.return_value = np.random.randn(len(X_test), 10)
                predictions2 = api2.predict(X_test)

            assert isinstance(predictions2, np.ndarray)
            assert len(predictions2) == len(X_test)


class TestConvenienceFunctions:
    """Test cases for convenience functions in inference module."""

    def test_create_inference_api_default(self):
        """Test creating inference API with default settings."""
        api = create_inference_api()

        assert isinstance(api, EMUSESInferenceAPI)
        assert api.config is not None

    def test_create_inference_api_custom_config(self, sample_config):
        """Test creating inference API with custom config."""
        api = create_inference_api(config=sample_config)

        assert isinstance(api, EMUSESInferenceAPI)
        assert api.config == sample_config

    def test_get_default_config(self):
        """Test getting default configuration."""
        config = get_default_config()

        assert isinstance(config, dict)
        assert "model_type" in config
        assert "pipeline_config" in config


@pytest.mark.skipif(not HAS_SKLEARN, reason="sklearn not available")
class TestRealWorldScenario:
    """Test with more realistic scenarios."""

    def test_brain_embedding_like_workflow(self, temp_model_dir):
        """Test workflow that mimics brain embedding analysis."""
        # Simulate brain region embeddings (e.g., 100 regions, 512-dim embeddings)
        np.random.seed(42)
        n_regions = 100
        embed_dim = 128  # Reduced for testing

        # Training data: embeddings and behavioral scores
        X_train = np.random.randn(n_regions, embed_dim)
        y_train = np.random.randn(n_regions) * 10 + 50  # Behavioral scores

        # Test data: new embeddings
        X_test = np.random.randn(30, embed_dim)

        # Configure API for brain embedding analysis
        config = {
            "model_type": "sklearn",
            "sklearn_model": "Ridge",
            "sklearn_params": {"alpha": 1.0},
            "pipeline_config": {
                "feature_extraction": ["correlation", "gwd"],
                "standardize": True,
            },
        }

        api = EMUSESInferenceAPI(config=config, model_dir=temp_model_dir)

        # Mock feature extraction methods
        def mock_correlation(*args, **kwargs):
            n_samples = args[0].shape[0] if len(args) > 0 else 100
            return np.random.randn(n_samples, 20)

        def mock_gwd(*args, **kwargs):
            n_samples = args[0].shape[0] if len(args) > 0 else 100
            return {"gwd_summary": np.random.randn(n_samples, 15)}

        with patch(
            "emuses.inference.api.calculate_correlation", side_effect=mock_correlation
        ), patch("emuses.inference.api.compute_gwd_summary", side_effect=mock_gwd):

            # Fit model
            api.fit(X_train, y_train)

            # Make predictions
            predictions = api.predict(X_test)

            # Validate results
            assert isinstance(predictions, np.ndarray)
            assert len(predictions) == len(X_test)
            assert not np.isnan(predictions).any()

            # Save and reload
            api.save_model("brain_embedding_model")

            api2 = EMUSESInferenceAPI(config=config, model_dir=temp_model_dir)
            api2.load_model("brain_embedding_model")

            # Make predictions with reloaded model
            predictions2 = api2.predict(X_test)

            assert isinstance(predictions2, np.ndarray)
            assert len(predictions2) == len(X_test)


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
