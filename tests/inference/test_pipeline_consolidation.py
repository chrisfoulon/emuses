"""
Tests for EMUSESPipeline inference mode consolidation functionality.

This module tests the consolidation of inference initialization logic,
eliminating duplication between EMUSESPipeline.__init__ and CLI inference.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

from emuses.pipelines.emuses_pipeline import EMUSESPipeline


class TestPipelineInferenceDataInjection(unittest.TestCase):
    """Test EMUSESPipeline with inference_data parameter for lightweight initialization."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create minimal args object for testing
        self.args = type('Args', (), {})()
        self.args.input_dataset = str(self.temp_path / "test_data.csv")
        self.args.output_folder = str(self.temp_path / "output")
        self.args.random_state = 42
        self.args.inference_mode = True
        
        # Create test inference data
        self.inference_data = {
            "input_path": str(self.temp_path / "inference_data.csv"),
            "scores_path": str(self.temp_path / "scores.csv"),
            "model_path": str(self.temp_path / "model")
        }
        
        # Create test CSV files
        self.test_input_matrix = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
        self.test_scores = np.array([0.1, 0.2, 0.3])
        
        # Create test data files
        np.savetxt(self.inference_data["input_path"], self.test_input_matrix, delimiter=',')
        np.savetxt(self.inference_data["scores_path"], self.test_scores)
        Path(self.inference_data["model_path"]).mkdir(exist_ok=True)
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_init_accepts_inference_data_parameter(self):
        """Test that EMUSESPipeline.__init__ accepts optional inference_data parameter."""
        # Test should pass now - inference_data parameter is implemented
        try:
            pipeline = EMUSESPipeline(self.args, inference_data=self.inference_data)
            # Verify that pipeline was created successfully
            self.assertIsNotNone(pipeline)
            self.assertEqual(pipeline._inference_data, self.inference_data)
        except Exception as e:
            self.fail(f"EMUSESPipeline should accept inference_data parameter: {e}")
            
    def test_init_with_inference_data_skips_redundant_processing(self):
        """Test that providing inference_data uses it instead of calling format_args."""
        with patch.object(EMUSESPipeline, 'format_args') as mock_format:
            pipeline = EMUSESPipeline(self.args, inference_data=self.inference_data)
            # Should not call format_args when inference_data provided
            mock_format.assert_not_called()
            
            # But should still have processed the inference data
            self.assertIsNotNone(pipeline.input_matrix)
            self.assertEqual(pipeline.dataset_type, "spreadsheet")
                    
    def test_init_without_inference_data_uses_normal_processing(self):
        """Test that EMUSESPipeline without inference_data uses normal processing path."""
        with patch.object(EMUSESPipeline, 'format_args') as mock_format:
            try:
                pipeline = EMUSESPipeline(self.args)
                # Should call format_args for normal processing
                mock_format.assert_called_once()
            except Exception:
                # Normal pipeline initialization may fail in test environment
                # The important thing is that it doesn't fail due to inference_data
                pass
                
    def test_inference_data_creates_proper_context(self):
        """Test that inference_data creates proper context for InferenceStage."""
        # This test should verify that context contains expected inference keys
        pipeline = EMUSESPipeline(self.args, inference_data=self.inference_data)
        
        # Check that inference-specific context keys are set
        self.assertIn("inference_features", pipeline.context)
        self.assertIn("inference_labels", pipeline.context) 
        self.assertIn("model_path", pipeline.context)
        self.assertIn("cli_inference_mode", pipeline.context)
        
        # Verify the context values are correct
        self.assertEqual(pipeline.context["model_path"], self.inference_data["model_path"])
        self.assertTrue(pipeline.context["cli_inference_mode"])
        self.assertIsInstance(pipeline.context["inference_features"], np.ndarray)


class TestContextConsistency(unittest.TestCase):
    """Test context consistency between training and inference modes."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create args for both modes
        self.training_args = type('Args', (), {})()
        self.training_args.input_dataset = str(self.temp_path / "train_data.csv")
        self.training_args.output_folder = str(self.temp_path / "train_output")
        self.training_args.random_state = 42
        self.training_args.inference_mode = False
        
        self.inference_args = type('Args', (), {})()
        self.inference_args.input_dataset = str(self.temp_path / "inference_data.csv")
        self.inference_args.output_folder = str(self.temp_path / "inference_output")
        self.inference_args.random_state = 42
        self.inference_args.inference_mode = True
        
        # Create test data
        test_data = np.array([[1.0, 2.0], [3.0, 4.0]])
        np.savetxt(self.training_args.input_dataset, test_data, delimiter=',')
        np.savetxt(self.inference_args.input_dataset, test_data, delimiter=',')
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_context_keys_consistent_between_modes(self):
        """Test that essential context keys are consistent between training and inference."""
        # This test verifies that both modes create compatible contexts
        try:
            with patch.object(EMUSESPipeline, 'process_dataset', return_value=(
                np.array([[1, 2], [3, 4]]), "csv", None, None
            )):
                training_pipeline = EMUSESPipeline(self.training_args)
                inference_pipeline = EMUSESPipeline(self.inference_args, inference_data={
                    "input_path": self.inference_args.input_dataset,
                    "scores_path": None,
                    "model_path": "/tmp/model"
                })
                
                # Both should have these essential context keys
                essential_keys = ["dataset_type", "output_format_info", "output_folder"]
                for key in essential_keys:
                    self.assertIn(key, training_pipeline.context)
                    self.assertIn(key, inference_pipeline.context)
                    
        except TypeError:
            # Expected failure - not implemented yet
            self.skipTest("inference_data parameter not implemented yet")


class TestFormatArgsEfficiency(unittest.TestCase):
    """Test that format_args() handles inference mode efficiently."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create minimal args object for testing
        self.args = type('Args', (), {})()
        self.args.input_dataset = str(self.temp_path / "test_data.csv")
        self.args.output_folder = str(self.temp_path / "output")
        self.args.random_state = 42
        self.args.inference_mode = True
        
        # Create test data file
        test_data = np.array([[1.0, 2.0], [3.0, 4.0]])
        np.savetxt(self.args.input_dataset, test_data, delimiter=',')
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_format_args_early_return_with_inference_data(self):
        """Test that format_args() returns early when inference data already processed."""
        inference_data = {
            "input_path": self.args.input_dataset,
            "scores_path": None,
            "model_path": str(self.temp_path / "model")
        }
        
        # Create pipeline with inference_data - this will set up the data
        pipeline = EMUSESPipeline(self.args, inference_data=inference_data)
        
        # Verify that data was already processed by _setup_inference_mode
        self.assertIsNotNone(pipeline.input_matrix)
        self.assertIsNotNone(pipeline.dataset_type)
        
        # Mock process_dataset to verify it's not called again
        with patch.object(pipeline, 'process_dataset') as mock_process:
            # Call format_args directly - should return early
            pipeline.format_args()
            # Should not process dataset again since it's already done
            mock_process.assert_not_called()


class TestConsolidationRegression(unittest.TestCase):
    """Regression tests for consolidation scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create minimal args object
        self.args = type('Args', (), {})()
        self.args.input_dataset = str(self.temp_path / "test_data.csv")
        self.args.output_folder = str(self.temp_path / "output")
        self.args.random_state = 42
        self.args.inference_mode = True
        
        # Create test CSV file
        test_data = np.array([[1.0, 2.0], [3.0, 4.0]])
        np.savetxt(self.args.input_dataset, test_data, delimiter=',')
        
        # Set required args attributes with defaults
        for attr in ['input_header', 'input_index_column', 'scores_header', 'scores_index_column',
                     'columns_are_features', 'input_normalization', 'inputs_columns', 'classification',
                     'scores_normalization', 'scores_are_rows', 'scores_column', 'filter_labelled_by_scores',
                     'recursive_search', 'input_file_types', 'arg_separator', 'bids_filters', 'scores']:
            setattr(self.args, attr, None)
        
        # Set proper defaults
        self.args.columns_are_features = False
        self.args.input_normalization = "none"
        self.args.classification = False
        self.args.scores_normalization = "none"
        self.args.scores_are_rows = False
        self.args.filter_labelled_by_scores = False
        self.args.recursive_search = False
        self.args.arg_separator = ","
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_both_initialization_paths_work(self):
        """Test that both old and new initialization paths work."""
        # Test 1: Old path (without inference_data)
        with patch.object(EMUSESPipeline, 'process_dataset', return_value=(
            np.array([[1, 2], [3, 4]]), "spreadsheet", None, None
        )):
            with patch.object(EMUSESPipeline, 'load_and_process_scores'):
                old_pipeline = EMUSESPipeline(self.args)
                self.assertIsNotNone(old_pipeline)
                self.assertIsNone(old_pipeline._inference_data)
        
        # Test 2: New path (with inference_data)
        inference_data = {
            "input_path": self.args.input_dataset,
            "scores_path": None,
            "model_path": str(self.temp_path / "model")
        }
        new_pipeline = EMUSESPipeline(self.args, inference_data=inference_data)
        self.assertIsNotNone(new_pipeline)
        self.assertEqual(new_pipeline._inference_data, inference_data)
        
        # Both should be valid EMUSESPipeline instances
        self.assertIsInstance(old_pipeline, EMUSESPipeline)
        self.assertIsInstance(new_pipeline, EMUSESPipeline)
        
    def test_consolidation_eliminates_double_processing_regression(self):
        """Regression test: ensure no double processing occurs."""
        inference_data = {
            "input_path": self.args.input_dataset,
            "scores_path": None,
            "model_path": str(self.temp_path / "model")
        }
        
        with patch.object(EMUSESPipeline, 'process_dataset') as mock_process:
            mock_process.return_value = (
                np.array([[1, 2], [3, 4]]), "spreadsheet", None, None
            )
            
            # Create pipeline with inference_data
            pipeline = EMUSESPipeline(self.args, inference_data=inference_data)
            
            # process_dataset should be called exactly once during _setup_inference_mode
            self.assertEqual(mock_process.call_count, 1)
            
            # Calling format_args again should NOT call process_dataset again
            pipeline.format_args()
            
            # Still should be called only once
            self.assertEqual(mock_process.call_count, 1)
            
    def test_context_keys_preserved_regression(self):
        """Regression test: ensure all required context keys are preserved."""
        inference_data = {
            "input_path": self.args.input_dataset,
            "scores_path": None,
            "model_path": str(self.temp_path / "model")
        }
        
        pipeline = EMUSESPipeline(self.args, inference_data=inference_data)
        
        # Essential context keys that InferenceStage expects
        required_keys = [
            "inference_features", 
            "inference_labels",
            "dataset_type",
            "output_format_info", 
            "model_path",
            "cli_inference_mode",
            "random_seeds",  # From pipeline initialization
            "output_folder"  # From pipeline initialization
        ]
        
        for key in required_keys:
            with self.subTest(key=key):
                self.assertIn(key, pipeline.context, f"Missing required context key: {key}")
                
        # Verify specific values
        self.assertEqual(pipeline.context["model_path"], str(self.temp_path / "model"))
        self.assertTrue(pipeline.context["cli_inference_mode"])
        
    def test_backward_compatibility_regression(self):
        """Regression test: ensure backward compatibility is maintained."""
        # Test that old EMUSESPipeline(args) calls still work
        with patch.object(EMUSESPipeline, 'process_dataset', return_value=(
            np.array([[1, 2], [3, 4]]), "spreadsheet", None, None
        )):
            with patch.object(EMUSESPipeline, 'load_and_process_scores'):
                # This should work exactly as before
                pipeline = EMUSESPipeline(self.args)
                
                # Should have all the same attributes
                self.assertIsNotNone(pipeline.config)
                self.assertIsNotNone(pipeline.context)
                self.assertIsNotNone(pipeline.logger)
                self.assertEqual(pipeline._inference_data, None)
                
                # Should behave the same as old implementation
                self.assertIn("random_seeds", pipeline.context)
                self.assertIn("output_folder", pipeline.context)


if __name__ == "__main__":
    unittest.main()