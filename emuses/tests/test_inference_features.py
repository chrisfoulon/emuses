# filepath: s:\GIN Dropbox\Chris Foulon\EMUSE\package\emuses\emuses\tests\test_inference_features.py

"""
Specific tests for enhanced feature utilities with inference mode support.

This test suite validates:
- Correlation functions with inference_mode parameter
- GWD functions with inference_mode and reference_embeddings parameters
- PCAGWD and KernelPCAGWD classes with proper training data storage
- Edge cases and error handling for inference mode
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
import warnings

# Import the enhanced feature utilities
from emuses.tools.correlation_maps_utils import (
    calculate_correlation_grid,
    calculate_correlation,
)
from emuses.tools.stats_utils import compute_all_gwd, compute_gwd_summary
from emuses.tools.features_utils import PCAGWD, KernelPCAGWD


# Test fixtures
@pytest.fixture
def training_embeddings():
    """Generate training embeddings for testing."""
    np.random.seed(42)
    return np.random.randn(80, 64)  # 80 samples, 64 features


@pytest.fixture
def inference_embeddings():
    """Generate inference embeddings for testing."""
    np.random.seed(123)
    return np.random.randn(25, 64)  # 25 samples, 64 features


@pytest.fixture
def small_embeddings():
    """Generate small embeddings for kernel methods."""
    np.random.seed(42)
    return np.random.randn(20, 32)  # Smaller for kernel methods


@pytest.fixture
def small_inference_embeddings():
    """Generate small inference embeddings for kernel methods."""
    np.random.seed(123)
    return np.random.randn(8, 32)


class TestCorrelationFunctionsInferenceMode:
    """Test correlation functions with inference mode support."""

    def test_calculate_correlation_grid_normal_mode(self, training_embeddings):
        """Test calculate_correlation_grid in normal (training) mode."""
        result = calculate_correlation_grid(training_embeddings)

        assert isinstance(result, np.ndarray)
        assert result.shape[0] == len(training_embeddings)
        # Should not require reference_embeddings in normal mode

    def test_calculate_correlation_grid_inference_mode(
        self, training_embeddings, inference_embeddings
    ):
        """Test calculate_correlation_grid in inference mode."""
        result = calculate_correlation_grid(
            inference_embeddings,
            inference_mode=True,
            reference_embeddings=training_embeddings,
        )

        assert isinstance(result, np.ndarray)
        assert result.shape[0] == len(inference_embeddings)
        # Result should be computed relative to training embeddings

    def test_calculate_correlation_grid_inference_mode_no_reference(
        self, inference_embeddings
    ):
        """Test calculate_correlation_grid inference mode without reference embeddings."""
        with pytest.raises(ValueError, match="reference_embeddings must be provided"):
            calculate_correlation_grid(
                inference_embeddings, inference_mode=True, reference_embeddings=None
            )

    def test_calculate_correlation_grid_mismatched_features(self, training_embeddings):
        """Test calculate_correlation_grid with mismatched feature dimensions."""
        # Create inference data with different number of features
        wrong_inference = np.random.randn(10, training_embeddings.shape[1] + 5)

        with pytest.raises(ValueError, match="feature dimensions"):
            calculate_correlation_grid(
                wrong_inference,
                inference_mode=True,
                reference_embeddings=training_embeddings,
            )

    def test_calculate_correlation_normal_mode(self, training_embeddings):
        """Test calculate_correlation in normal (training) mode."""
        result = calculate_correlation(training_embeddings)

        assert isinstance(result, np.ndarray)
        assert result.shape[0] == len(training_embeddings)

    def test_calculate_correlation_inference_mode(
        self, training_embeddings, inference_embeddings
    ):
        """Test calculate_correlation in inference mode."""
        result = calculate_correlation(
            inference_embeddings,
            inference_mode=True,
            reference_embeddings=training_embeddings,
        )

        assert isinstance(result, np.ndarray)
        assert result.shape[0] == len(inference_embeddings)

    def test_calculate_correlation_inference_mode_no_reference(
        self, inference_embeddings
    ):
        """Test calculate_correlation inference mode without reference embeddings."""
        with pytest.raises(ValueError, match="reference_embeddings must be provided"):
            calculate_correlation(
                inference_embeddings, inference_mode=True, reference_embeddings=None
            )


class TestGWDFunctionsInferenceMode:
    """Test GWD functions with inference mode support."""

    def test_compute_all_gwd_normal_mode(self, training_embeddings):
        """Test compute_all_gwd in normal (training) mode."""
        result = compute_all_gwd(training_embeddings)

        assert isinstance(result, dict)
        assert "gwd_matrix" in result
        assert isinstance(result["gwd_matrix"], np.ndarray)

    def test_compute_all_gwd_inference_mode(
        self, training_embeddings, inference_embeddings
    ):
        """Test compute_all_gwd in inference mode."""
        result = compute_all_gwd(
            inference_embeddings,
            inference_mode=True,
            reference_embeddings=training_embeddings,
        )

        assert isinstance(result, dict)
        assert "gwd_matrix" in result
        assert isinstance(result["gwd_matrix"], np.ndarray)
        # Should compute GWD between inference and reference embeddings

    def test_compute_all_gwd_inference_mode_no_reference(self, inference_embeddings):
        """Test compute_all_gwd inference mode without reference embeddings."""
        with pytest.raises(ValueError, match="reference_embeddings must be provided"):
            compute_all_gwd(
                inference_embeddings, inference_mode=True, reference_embeddings=None
            )

    def test_compute_gwd_summary_normal_mode(self, training_embeddings):
        """Test compute_gwd_summary in normal (training) mode."""
        result = compute_gwd_summary(training_embeddings)

        assert isinstance(result, dict)
        # Should contain summary statistics

    def test_compute_gwd_summary_inference_mode(
        self, training_embeddings, inference_embeddings
    ):
        """Test compute_gwd_summary in inference mode."""
        result = compute_gwd_summary(
            inference_embeddings,
            inference_mode=True,
            reference_embeddings=training_embeddings,
        )

        assert isinstance(result, dict)
        # Should compute summary relative to reference embeddings

    def test_compute_gwd_summary_inference_mode_no_reference(
        self, inference_embeddings
    ):
        """Test compute_gwd_summary inference mode without reference embeddings."""
        with pytest.raises(ValueError, match="reference_embeddings must be provided"):
            compute_gwd_summary(
                inference_embeddings, inference_mode=True, reference_embeddings=None
            )

    def test_gwd_functions_mismatched_features(self, training_embeddings):
        """Test GWD functions with mismatched feature dimensions."""
        # Create inference data with different number of features
        wrong_inference = np.random.randn(10, training_embeddings.shape[1] + 3)

        with pytest.raises(ValueError, match="feature dimensions"):
            compute_all_gwd(
                wrong_inference,
                inference_mode=True,
                reference_embeddings=training_embeddings,
            )

        with pytest.raises(ValueError, match="feature dimensions"):
            compute_gwd_summary(
                wrong_inference,
                inference_mode=True,
                reference_embeddings=training_embeddings,
            )


class TestPCAGWDInferenceMode:
    """Test PCAGWD class with inference mode support."""

    def test_pcagwd_fit_stores_training_data(self, training_embeddings):
        """Test that PCAGWD.fit() stores training data."""
        pcagwd = PCAGWD(n_components=10)
        pcagwd.fit(training_embeddings)

        # Check that training data is stored
        assert hasattr(pcagwd, "_X_fit")
        assert pcagwd._X_fit is not None
        assert np.array_equal(pcagwd._X_fit, training_embeddings)

    def test_pcagwd_transform_uses_training_data(
        self, training_embeddings, inference_embeddings
    ):
        """Test that PCAGWD.transform() uses stored training data for GWD computation."""
        pcagwd = PCAGWD(n_components=15)
        pcagwd.fit(training_embeddings)

        # Transform inference data
        result = pcagwd.transform(inference_embeddings)

        assert isinstance(result, np.ndarray)
        assert result.shape[0] == len(inference_embeddings)
        assert result.shape[1] == 15  # n_components

    def test_pcagwd_transform_without_fit(self, inference_embeddings):
        """Test PCAGWD.transform() without fitting first."""
        pcagwd = PCAGWD(n_components=10)

        with pytest.raises(ValueError, match="not been fitted"):
            pcagwd.transform(inference_embeddings)

    def test_pcagwd_transform_mismatched_features(self, training_embeddings):
        """Test PCAGWD.transform() with mismatched feature dimensions."""
        pcagwd = PCAGWD(n_components=10)
        pcagwd.fit(training_embeddings)

        # Create data with wrong number of features
        wrong_data = np.random.randn(15, training_embeddings.shape[1] + 5)

        with pytest.raises(ValueError, match="feature dimensions"):
            pcagwd.transform(wrong_data)

    def test_pcagwd_fit_transform_consistency(self, training_embeddings):
        """Test consistency between fit_transform and separate fit/transform."""
        pcagwd1 = PCAGWD(n_components=8, random_state=42)
        pcagwd2 = PCAGWD(n_components=8, random_state=42)

        # Method 1: fit_transform
        result1 = pcagwd1.fit_transform(training_embeddings)

        # Method 2: separate fit and transform
        pcagwd2.fit(training_embeddings)
        result2 = pcagwd2.transform(training_embeddings)

        # Results should be very similar (allowing for numerical precision)
        np.testing.assert_array_almost_equal(result1, result2, decimal=5)


class TestKernelPCAGWDInferenceMode:
    """Test KernelPCAGWD class with inference mode support."""

    def test_kernel_pcagwd_fit_stores_training_data(self, small_embeddings):
        """Test that KernelPCAGWD.fit() stores training data."""
        kpcagwd = KernelPCAGWD(n_components=5, kernel="rbf")
        kpcagwd.fit(small_embeddings)

        # Check that training data is stored
        assert hasattr(kpcagwd, "_X_fit")
        assert kpcagwd._X_fit is not None
        assert np.array_equal(kpcagwd._X_fit, small_embeddings)

    def test_kernel_pcagwd_transform_uses_training_data(
        self, small_embeddings, small_inference_embeddings
    ):
        """Test that KernelPCAGWD.transform() uses stored training data."""
        kpcagwd = KernelPCAGWD(n_components=5, kernel="rbf")
        kpcagwd.fit(small_embeddings)

        # Transform inference data
        result = kpcagwd.transform(small_inference_embeddings)

        assert isinstance(result, np.ndarray)
        assert result.shape[0] == len(small_inference_embeddings)
        assert result.shape[1] == 5  # n_components

    def test_kernel_pcagwd_transform_without_fit(self, small_inference_embeddings):
        """Test KernelPCAGWD.transform() without fitting first."""
        kpcagwd = KernelPCAGWD(n_components=5, kernel="rbf")

        with pytest.raises(ValueError, match="not been fitted"):
            kpcagwd.transform(small_inference_embeddings)

    def test_kernel_pcagwd_different_kernels(
        self, small_embeddings, small_inference_embeddings
    ):
        """Test KernelPCAGWD with different kernel types."""
        kernels = ["linear", "rbf", "poly"]

        for kernel in kernels:
            kpcagwd = KernelPCAGWD(n_components=3, kernel=kernel)
            kpcagwd.fit(small_embeddings)

            result = kpcagwd.transform(small_inference_embeddings)

            assert isinstance(result, np.ndarray)
            assert result.shape[0] == len(small_inference_embeddings)
            assert result.shape[1] == 3


class TestInferenceModeEdgeCases:
    """Test edge cases and error handling for inference mode."""

    def test_empty_embeddings(self):
        """Test functions with empty embeddings."""
        empty_data = np.array([]).reshape(0, 10)
        reference_data = np.random.randn(20, 10)

        # Test correlation functions
        with pytest.raises(ValueError, match="empty"):
            calculate_correlation_grid(
                empty_data, inference_mode=True, reference_embeddings=reference_data
            )

        with pytest.raises(ValueError, match="empty"):
            calculate_correlation(
                empty_data, inference_mode=True, reference_embeddings=reference_data
            )

    def test_single_sample_embeddings(self):
        """Test functions with single sample embeddings."""
        single_data = np.random.randn(1, 10)
        reference_data = np.random.randn(20, 10)

        # Should work with single sample
        result1 = calculate_correlation_grid(
            single_data, inference_mode=True, reference_embeddings=reference_data
        )
        assert result1.shape[0] == 1

        result2 = calculate_correlation(
            single_data, inference_mode=True, reference_embeddings=reference_data
        )
        assert result2.shape[0] == 1

    def test_very_small_feature_dimensions(self):
        """Test functions with very small feature dimensions."""
        small_data = np.random.randn(10, 2)  # Only 2 features
        reference_data = np.random.randn(15, 2)

        # Should handle small feature dimensions
        result = calculate_correlation_grid(
            small_data, inference_mode=True, reference_embeddings=reference_data
        )
        assert isinstance(result, np.ndarray)
        assert result.shape[0] == len(small_data)

    def test_identical_embeddings(self, training_embeddings):
        """Test functions with identical training and inference embeddings."""
        # Use same data for both training and inference
        result1 = calculate_correlation_grid(
            training_embeddings,
            inference_mode=True,
            reference_embeddings=training_embeddings,
        )

        result2 = calculate_correlation(
            training_embeddings,
            inference_mode=True,
            reference_embeddings=training_embeddings,
        )

        assert isinstance(result1, np.ndarray)
        assert isinstance(result2, np.ndarray)
        assert result1.shape[0] == len(training_embeddings)
        assert result2.shape[0] == len(training_embeddings)

    def test_nan_and_inf_handling(self, training_embeddings):
        """Test handling of NaN and infinite values."""
        # Create data with NaN values
        nan_data = training_embeddings.copy()
        nan_data[0, 0] = np.nan

        # Functions should handle or raise appropriate errors for NaN values
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Suppress warnings for testing

            try:
                result = calculate_correlation_grid(
                    nan_data,
                    inference_mode=True,
                    reference_embeddings=training_embeddings,
                )
                # If it succeeds, check that result is reasonable
                assert isinstance(result, np.ndarray)
            except (ValueError, RuntimeError):
                # It's acceptable to raise an error for NaN values
                pass

    def test_reference_embeddings_validation(self):
        """Test validation of reference embeddings parameter."""
        test_data = np.random.randn(10, 5)

        # Test with invalid reference embeddings type
        with pytest.raises(TypeError, match="numpy array"):
            calculate_correlation_grid(
                test_data, inference_mode=True, reference_embeddings="invalid"
            )

        # Test with reference embeddings having wrong dimensions
        wrong_ref = np.random.randn(15, 8)  # Different feature count

        with pytest.raises(ValueError, match="feature dimensions"):
            calculate_correlation_grid(
                test_data, inference_mode=True, reference_embeddings=wrong_ref
            )


class TestInferenceModePerformance:
    """Test performance-related aspects of inference mode."""

    def test_large_embeddings_inference(self):
        """Test inference mode with larger embedding sets."""
        # Create larger datasets
        large_training = np.random.randn(500, 100)
        large_inference = np.random.randn(100, 100)

        # Test that functions can handle larger datasets
        result1 = calculate_correlation_grid(
            large_inference, inference_mode=True, reference_embeddings=large_training
        )

        result2 = compute_gwd_summary(
            large_inference, inference_mode=True, reference_embeddings=large_training
        )

        assert isinstance(result1, np.ndarray)
        assert isinstance(result2, dict)
        assert result1.shape[0] == len(large_inference)

    def test_memory_efficiency_checks(self, training_embeddings, inference_embeddings):
        """Test that inference mode doesn't create excessive memory usage."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Perform multiple inference operations
        for _ in range(10):
            _ = calculate_correlation_grid(
                inference_embeddings,
                inference_mode=True,
                reference_embeddings=training_embeddings,
            )

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 100MB for this test)
        assert (
            memory_increase < 100 * 1024 * 1024
        ), f"Memory usage increased by {memory_increase / 1024 / 1024:.2f} MB"


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
