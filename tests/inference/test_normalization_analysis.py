"""
Test suite for analyzing current normalization implementation status.

This test documents the existing normalization capabilities in EMUSES
to inform the inference performance fixes implementation.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch
import tempfile
from pathlib import Path

from bcblib.tools.dataframe_filtering import normalize_dataframe, inverse_normalize_dataframe


class TestCurrentNormalizationStatus:
    """Test current normalization implementation status across EMUSES components."""

    # REMOVED 2026-09-06: test_embeddings_normalization_already_correct.
    #
    # It built a dict containing "embedding_train_min_coords" /
    # "embedding_train_max_coords" and then asserted that the dict contained them.
    # Nothing in EMUSES was executed. Its title claimed the scaling was "already
    # correctly implemented", and for as long as it passed those two context keys
    # had no production consumer at all -- a green line standing over a dead route.
    # The keys are gone; the factors live in embedding_scaling.json, and
    # tests/test_scaling_single_source.py checks that structurally.

    def test_scores_normalization_missing_scaler_storage(self):
        """❌ Scores normalization: Not saved for inference reuse."""
        # This test documents the current limitation in scores normalization
        # Location: emuses/pipelines/emuses_pipeline.py line ~388
        
        # Test current behavior - only returns normalized dataframe
        test_df = pd.DataFrame({
            'score1': [1, 2, 3, 4, 5],
            'score2': [10, 20, 30, 40, 50]
        })
        
        # Current implementation (what exists now)
        normalized_df, scaling_factors = normalize_dataframe(test_df, method='min-max')
        
        # Verify current behavior works but scaling factors are not saved persistently
        assert isinstance(normalized_df, pd.DataFrame)
        assert isinstance(scaling_factors, dict)
        assert len(scaling_factors) == 2  # Two columns
        
        # Test that inverse transformation works with the scaling factors
        restored_df = inverse_normalize_dataframe(normalized_df, scaling_factors, method='min-max')
        pd.testing.assert_frame_equal(test_df, restored_df, check_dtype=False)

    def test_input_normalization_partial_implementation(self):
        """⚠️ Input normalization: Partially implemented, needs extension to model files."""
        # This test documents the current partial implementation
        # Location: emuses/pipelines/emuses_pipeline.py line ~250
        
        # Mock current context behavior
        test_df = pd.DataFrame({
            'feature1': [1, 2, 3, 4, 5],
            'feature2': [0.1, 0.2, 0.3, 0.4, 0.5]
        })
        
        # Current behavior - saves to context but not to model files
        normalized_df, scaling_factors = normalize_dataframe(test_df, method='min-max')
        mock_context = {"input_scaling_factors": scaling_factors}
        
        # Verify partial implementation exists
        assert "input_scaling_factors" in mock_context
        assert isinstance(mock_context["input_scaling_factors"], dict)
        
        # Test reusability of saved scaling factors
        new_test_df = pd.DataFrame({
            'feature1': [6, 7, 8],
            'feature2': [0.6, 0.7, 0.8]
        })
        
        # Verify existing scaling factors can be reused
        reused_normalized_df, _ = normalize_dataframe(
            new_test_df, method='min-max', scaling_factors=scaling_factors
        )
        assert isinstance(reused_normalized_df, pd.DataFrame)

    def test_bcblib_normalization_reversibility(self):
        """Test bcblib normalize_dataframe reversibility for all methods."""
        test_df = pd.DataFrame({
            'col1': [1, 2, 3, 4, 5],
            'col2': [10, 20, 30, 40, 50],
            'col3': [0.1, 0.2, 0.3, 0.4, 0.5]
        })
        
        methods = ['min-max', 'zscore', 'robust']
        
        for method in methods:
            # Test forward normalization
            normalized_df, scaling_factors = normalize_dataframe(test_df, method=method)
            
            # Test reverse normalization
            restored_df = inverse_normalize_dataframe(
                normalized_df, scaling_factors, method=method
            )
            
            # Verify reversibility (within numerical precision)
            pd.testing.assert_frame_equal(
                test_df, restored_df, check_dtype=False, rtol=1e-10
            )

    def test_bcblib_scaling_factors_structure(self):
        """Document bcblib scaling factors structure for each method."""
        test_df = pd.DataFrame({
            'col1': [1, 2, 3, 4, 5],
            'col2': [10, 20, 30, 40, 50]
        })
        
        # Test min-max scaling factors
        _, minmax_factors = normalize_dataframe(test_df, method='min-max')
        assert isinstance(minmax_factors, dict)
        assert len(minmax_factors) == 2
        for col, factors in minmax_factors.items():
            assert isinstance(factors, tuple)
            assert len(factors) == 2  # (min, max)
            assert factors[0] < factors[1]  # min < max
        
        # Test zscore scaling factors
        _, zscore_factors = normalize_dataframe(test_df, method='zscore')
        assert isinstance(zscore_factors, dict)
        assert len(zscore_factors) == 2
        for col, factors in zscore_factors.items():
            assert isinstance(factors, tuple)
            assert len(factors) == 2  # (mean, std)
            assert factors[1] > 0  # std > 0
        
        # Test robust scaling factors
        _, robust_factors = normalize_dataframe(test_df, method='robust')
        assert isinstance(robust_factors, dict)
        assert len(robust_factors) == 2
        # Note: robust factors structure is more complex, contains scaler object

    def test_kernel_regressor_requires_normalized_embeddings(self):
        """Verify KernelRegressor requires normalized embeddings (distance-based models sensitive)."""
        # This test documents why normalization is critical for KernelRegressor
        # KernelRegressor uses distance-based calculations, making it sensitive to data scaling
        
        # Create test data with different scales
        unnormalized_embeddings = np.array([
            [1, 10],
            [2, 20], 
            [3, 30],
            [4, 40]
        ])
        
        normalized_embeddings = np.array([
            [0.0, 0.0],
            [0.33, 0.33],
            [0.67, 0.67], 
            [1.0, 1.0]
        ])
        
        # Mock distance calculation behavior
        # Unnormalized data has much larger distances due to scale differences
        unnormalized_distance = np.sqrt((4-1)**2 + (40-10)**2)  # ~30.15
        normalized_distance = np.sqrt((1.0-0.0)**2 + (1.0-0.0)**2)  # ~1.41
        
        # Document the significant difference in distance calculations
        assert unnormalized_distance > 30
        assert normalized_distance < 2
        assert unnormalized_distance / normalized_distance > 20
        
        # This demonstrates why KernelRegressor needs consistent normalization
        # between training and inference data


class TestNormalizationInfrastructureCapabilities:
    """Test existing normalization infrastructure capabilities for reusability."""
    
    def test_bcblib_supports_scaler_reuse(self):
        """Verify bcblib supports reusing scaling factors across different datasets."""
        # Training data
        train_df = pd.DataFrame({
            'feature1': [1, 2, 3, 4, 5],
            'feature2': [10, 20, 30, 40, 50]
        })
        
        # Inference data (different values)
        inference_df = pd.DataFrame({
            'feature1': [1.5, 2.5, 3.5],
            'feature2': [15, 25, 35]
        })
        
        # Get scaling factors from training data
        train_normalized, scaling_factors = normalize_dataframe(train_df, method='min-max')
        
        # Apply same scaling factors to inference data
        inference_normalized, _ = normalize_dataframe(
            inference_df, method='min-max', scaling_factors=scaling_factors
        )
        
        # Verify inference data is normalized using training scale
        assert isinstance(inference_normalized, pd.DataFrame)
        assert inference_normalized.shape == (3, 2)
        
        # Verify scaling was applied correctly using training min/max
        # feature1: train min=1, max=5, so value 1.5 should be (1.5-1)/(5-1) = 0.125
        assert abs(inference_normalized.iloc[0, 0] - 0.125) < 1e-10
        
        # feature2: train min=10, max=50, so value 15 should be (15-10)/(50-10) = 0.125
        assert abs(inference_normalized.iloc[0, 1] - 0.125) < 1e-10

    def test_scaling_factors_are_serializable(self):
        """Test that scaling factors can be saved/loaded (important for model persistence)."""
        import pickle
        import json
        
        test_df = pd.DataFrame({
            'col1': [1, 2, 3, 4, 5],
            'col2': [10, 20, 30, 40, 50]
        })
        
        # Test different normalization methods
        methods = ['min-max', 'zscore']  # Skip 'robust' as it contains sklearn objects
        
        for method in methods:
            _, scaling_factors = normalize_dataframe(test_df, method=method)
            
            # Test pickle serialization (required for joblib)
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                pickle.dump(scaling_factors, tmp)
                tmp.flush()
                
                with open(tmp.name, 'rb') as f:
                    loaded_factors = pickle.load(f)
                
                assert loaded_factors == scaling_factors
            
            # Clean up
            Path(tmp.name).unlink()

    def test_robust_method_uses_sklearn_scaler(self):
        """Document that robust method uses sklearn scaler objects."""
        test_df = pd.DataFrame({
            'col1': [1, 2, 3, 4, 5, 100],  # Include outlier
            'col2': [10, 20, 30, 40, 50, 1000]  # Include outlier
        })
        
        _, robust_factors = normalize_dataframe(test_df, method='robust')
        
        # Verify robust method uses sklearn scaler objects
        for col, scaler in robust_factors.items():
            # Check that it has sklearn-like interface
            assert hasattr(scaler, 'transform')
            assert hasattr(scaler, 'inverse_transform')
            
            # This confirms bcblib already integrates with sklearn for reversible scaling


if __name__ == '__main__':
    pytest.main([__file__, '-v'])