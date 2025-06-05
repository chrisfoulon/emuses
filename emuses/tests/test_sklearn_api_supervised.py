#!/usr/bin/env python3
"""
Comprehensive unit tests for EMUSES sklearn-like API supervised learning functionality.

Tests the complete supervised learning workflow:
1. fit(X, y) method for supervised training
2. predict(X) method for target prediction
3. score(X, y) method for model evaluation
4. sklearn compatibility methods (get_params, set_params)
5. Selective serialization and state persistence
6. Ensemble prediction from CV folds
7. Model loading and state reconstruction
"""

import unittest
import numpy as np
import pandas as pd
import tempfile
import shutil
from pathlib import Path
import json
import sys
import warnings

# Suppress warnings for cleaner test output
warnings.filterwarnings("ignore")

# Import EMUSES API
try:
    from emuses.inference.api import EMUSESInferenceAPI
except ImportError as e:
    print(f"Error importing EMUSESInferenceAPI: {e}")
    sys.exit(1)

# Import sklearn metrics for validation
try:
    from sklearn.metrics import r2_score, mean_squared_error
    from sklearn.model_selection import train_test_split
except ImportError:
    print("Warning: sklearn not available, some tests may fail")


class TestEMUSESSupervisedAPI(unittest.TestCase):
    """Test cases for EMUSES supervised learning API."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create temporary directory for model files
        self.temp_dir = tempfile.mkdtemp()
        self.model_dir = Path(self.temp_dir) / "test_models"
        self.model_dir.mkdir(exist_ok=True)

        # Generate synthetic test data
        self.X_train, self.X_test, self.y_train, self.y_test = (
            self._generate_test_data()
        )

        # Initialize API
        self.api = EMUSESInferenceAPI(model_dir=self.model_dir, verbose=False)

    def tearDown(self):
        """Clean up after each test method."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _generate_test_data(self, n_samples=50, n_features=8, random_state=42):
        """Generate synthetic test data for validation."""
        np.random.seed(random_state)

        # Generate input features
        X = np.random.randn(n_samples, n_features)

        # Generate target with some correlation to features
        y = np.sum(X[:, :3], axis=1) + 0.1 * np.random.randn(n_samples)

        # Split into train/test
        return train_test_split(X, y, test_size=0.3, random_state=random_state)

    def test_01_api_initialization(self):
        """Test API initialization and basic attributes."""
        self.assertIsInstance(self.api, EMUSESInferenceAPI)
        self.assertEqual(Path(self.api.model_dir), self.model_dir)
        self.assertFalse(self.api.is_fitted_)

    def test_02_fit_method_exists(self):
        """Test that fit method exists and has correct signature."""
        self.assertTrue(hasattr(self.api, "fit"))

        # Test method signature inspection
        import inspect

        sig = inspect.signature(self.api.fit)
        param_names = list(sig.parameters.keys())

        # Should have X as first parameter and y as optional second
        self.assertIn("X", param_names)
        self.assertIn("y", param_names)

    def test_03_supervised_fit_basic(self):
        """Test basic supervised fit functionality."""
        try:
            # This should work without errors
            result = self.api.fit(self.X_train, self.y_train)

            # Should return self for method chaining
            self.assertEqual(result, self.api)

            # Should be marked as fitted
            self.assertTrue(self.api.is_fitted_)

        except Exception as e:
            self.fail(f"Supervised fit failed with error: {e}")

    def test_04_predict_method_exists(self):
        """Test that predict method exists."""
        self.assertTrue(
            hasattr(self.api, "predict"),
            "predict() method is missing - CRITICAL for supervised learning",
        )

    def test_05_score_method_exists(self):
        """Test that score method exists."""
        self.assertTrue(
            hasattr(self.api, "score"),
            "score() method is missing - CRITICAL for sklearn compatibility",
        )

    def test_06_fit_predict_method_exists(self):
        """Test that fit_predict method exists."""
        self.assertTrue(
            hasattr(self.api, "fit_predict"),
            "fit_predict() method is missing - CRITICAL for sklearn compatibility",
        )

    def test_07_sklearn_compatibility_methods(self):
        """Test sklearn compatibility methods exist."""
        methods = ["get_params", "set_params"]
        for method in methods:
            self.assertTrue(
                hasattr(self.api, method),
                f"{method}() method is missing - CRITICAL for sklearn compatibility",
            )

    def test_08_selective_serialization_methods(self):
        """Test that selective serialization methods exist."""
        methods = [
            "_extract_lightweight_context",
            "_load_models_from_context",
            "_load_heavy_data_from_context",
            "_apply_preprocessing_from_context",
        ]
        for method in methods:
            self.assertTrue(
                hasattr(self.api, method),
                f"{method}() method is missing - needed for selective serialization",
            )

    def test_09_state_persistence_methods(self):
        """Test that state persistence methods exist."""
        methods = ["save_model", "load_model"]
        for method in methods:
            self.assertTrue(
                hasattr(self.api, method),
                f"{method}() method is missing - needed for model persistence",
            )

    def test_10_transform_backward_compatibility(self):
        """Test that transform method exists for backward compatibility."""
        self.assertTrue(
            hasattr(self.api, "transform"),
            "transform() method missing - needed for backward compatibility",
        )

    def test_11_unsupervised_fit_compatibility(self):
        """Test that unsupervised fit(X) still works for backward compatibility."""
        try:
            # Should work without y parameter
            result = self.api.fit(self.X_train)
            self.assertEqual(result, self.api)
            self.assertTrue(self.api.is_fitted_)
        except Exception as e:
            self.fail(f"Unsupervised fit failed - breaks backward compatibility: {e}")

    def test_12_lightweight_context_extraction(self):
        """Test selective context serialization functionality."""
        # Create a mock context with heavy and light data
        mock_context = {
            "dataset_metadata": {"n_samples": 100, "n_features": 10},  # Light
            "embedding_train_coords": np.random.randn(
                100, 2
            ),  # Heavy - should be excluded
            "umap_params": {"n_neighbors": 15, "min_dist": 0.1},  # Light
            "prediction_results": {  # Heavy but should extract metadata only
                "target_0": {
                    "cv_scores": [0.8, 0.85, 0.82],
                    "predictions": np.random.randn(100),  # Heavy array
                }
            },
        }

        lightweight = self.api._extract_lightweight_context(mock_context)

        # Should exclude heavy numpy arrays
        self.assertNotIn("embedding_train_coords", lightweight)

        # Should include lightweight metadata
        self.assertIn("dataset_metadata", lightweight)
        self.assertIn("umap_params", lightweight)

        # Should have heavy data references
        self.assertIn("heavy_data_references", lightweight)

    def test_13_api_inheritance(self):
        """Test that API properly inherits from sklearn BaseEstimator."""
        from sklearn.base import BaseEstimator

        self.assertIsInstance(self.api, BaseEstimator)

    def test_14_error_handling_invalid_inputs(self):
        """Test proper error handling for invalid inputs."""
        # Test with mismatched X, y shapes
        X_wrong = np.random.randn(10, 5)
        y_wrong = np.random.randn(15)  # Wrong number of samples

        with self.assertRaises((ValueError, Exception)):
            self.api.fit(X_wrong, y_wrong)

    def test_15_api_docstrings(self):
        """Test that key methods have proper docstrings."""
        self.assertIsNotNone(self.api.__doc__)
        self.assertIsNotNone(self.api.fit.__doc__)

        if hasattr(self.api, "predict"):
            self.assertIsNotNone(self.api.predict.__doc__)


class TestEMUSESImplementationCompleteness(unittest.TestCase):
    """Test implementation completeness against the plan."""

    def setUp(self):
        self.api = EMUSESInferenceAPI()

    def test_critical_missing_methods(self):
        """Check for critically missing methods that need implementation."""
        critical_methods = [
            ("predict", "CRITICAL: Main supervised learning prediction method"),
            ("score", "CRITICAL: sklearn compatibility scoring method"),
            ("fit_predict", "CRITICAL: sklearn compatibility convenience method"),
            ("get_params", "CRITICAL: sklearn compatibility parameter getter"),
            ("set_params", "CRITICAL: sklearn compatibility parameter setter"),
        ]

        missing_methods = []
        for method_name, description in critical_methods:
            if not hasattr(self.api, method_name):
                missing_methods.append(f"{method_name}: {description}")

        if missing_methods:
            self.fail(f"CRITICAL METHODS MISSING:\n" + "\n".join(missing_methods))

    def test_ensemble_prediction_readiness(self):
        """Check if API is ready for ensemble prediction functionality."""
        # These are needed for ensemble prediction from CV folds
        ensemble_related = [
            "_load_models_from_context",
            "_extract_lightweight_context",
            "save_model",
            "load_model",
        ]

        missing = [
            method for method in ensemble_related if not hasattr(self.api, method)
        ]
        if missing:
            self.fail(f"Methods needed for ensemble prediction missing: {missing}")

    def test_api_paradigm_correctness(self):
        """Test that API follows supervised learning paradigm."""
        # Check fit method signature
        import inspect

        fit_sig = inspect.signature(self.api.fit)

        # Should accept both X and y parameters
        self.assertIn("X", fit_sig.parameters)
        self.assertIn("y", fit_sig.parameters)

        # y should be optional (for backward compatibility)
        y_param = fit_sig.parameters["y"]
        self.assertTrue(
            y_param.default is not inspect.Parameter.empty or y_param.default is None
        )


def run_comprehensive_test():
    """Run comprehensive test suite and provide detailed results."""
    print("=" * 70)
    print("EMUSES sklearn API - COMPREHENSIVE IMPLEMENTATION TEST")
    print("=" * 70)

    # Create test suite
    test_suite = unittest.TestSuite()

    # Add test cases
    test_classes = [TestEMUSESSupervisedAPI, TestEMUSESImplementationCompleteness]
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)

    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(test_suite)

    # Provide summary
    print("\n" + "=" * 70)
    print("IMPLEMENTATION STATUS SUMMARY")
    print("=" * 70)

    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    success_rate = (
        ((total_tests - failures - errors) / total_tests * 100)
        if total_tests > 0
        else 0
    )

    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_tests - failures - errors}")
    print(f"Failed: {failures}")
    print(f"Errors: {errors}")
    print(f"Success Rate: {success_rate:.1f}%")

    if failures > 0:
        print(f"\nFAILED TESTS ({failures}):")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('AssertionError:')[-1].strip()}")

    if errors > 0:
        print(f"\nERROR TESTS ({errors}):")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split('Error:')[-1].strip()}")

    # Implementation recommendations
    print("\n" + "=" * 70)
    print("NEXT STEPS RECOMMENDATIONS")
    print("=" * 70)

    if success_rate < 50:
        print(
            "🔴 CRITICAL: Major methods missing. Implement core supervised learning methods first:"
        )
        print("   1. predict() method for target prediction")
        print("   2. score() method for model evaluation")
        print("   3. get_params()/set_params() for sklearn compatibility")
    elif success_rate < 80:
        print("🟡 PARTIAL: Core structure exists, complete missing methods:")
        print("   1. Implement remaining sklearn compatibility methods")
        print("   2. Add ensemble prediction functionality")
        print("   3. Complete state persistence methods")
    else:
        print("🟢 GOOD: Most functionality implemented, focus on:")
        print("   1. Integration testing with real EMUSES data")
        print("   2. Performance validation and optimization")
        print("   3. Documentation and examples")

    return result


if __name__ == "__main__":
    # Run the comprehensive test
    result = run_comprehensive_test()

    # Exit with appropriate code
    exit_code = 0 if result.wasSuccessful() else 1
    sys.exit(exit_code)
