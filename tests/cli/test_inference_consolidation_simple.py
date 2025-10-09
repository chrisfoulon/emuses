"""
Simple integration tests for CLI inference consolidation.

Tests the consolidated approach without complex mocking.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from emuses.pipelines.emuses_pipeline import EMUSESPipeline


class TestCLIConsolidationIntegration(unittest.TestCase):
    """Test that consolidation works end-to-end."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create simple test data files  
        test_data = np.array([[1.0, 2.0], [3.0, 4.0]])  # 2 samples
        test_scores = np.array([0.1, 0.2])  # 2 scores to match
        
        self.data_file = self.temp_path / "data.csv"
        self.scores_file = self.temp_path / "scores.csv"
        self.model_dir = self.temp_path / "model"
        self.output_dir = self.temp_path / "output"
        
        np.savetxt(self.data_file, test_data, delimiter=',')
        np.savetxt(self.scores_file, test_scores)
        self.model_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
        # Create minimal args
        self.args = type('Args', (), {})()
        self.args.input_dataset = str(self.data_file)
        self.args.output_folder = str(self.output_dir)
        self.args.random_state = 42
        self.args.inference_mode = True
        self.args.scores = str(self.scores_file)
        
        # Set other required args
        for attr in ['input_header', 'input_index_column', 'scores_header', 'scores_index_column',
                     'columns_are_features', 'input_normalization', 'inputs_columns', 'classification',
                     'scores_normalization', 'scores_are_rows', 'scores_column', 'filter_labelled_by_scores',
                     'recursive_search', 'input_file_types', 'arg_separator', 'bids_filters']:
            setattr(self.args, attr, None)
        
        # Set defaults for boolean/string args
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
        
    def test_consolidated_pipeline_creates_proper_context(self):
        """Test that consolidated pipeline approach creates proper context."""
        inference_data = {
            "input_path": str(self.data_file),
            "scores_path": str(self.scores_file),
            "model_path": str(self.model_dir)
        }
        
        # Create pipeline with consolidated approach
        pipeline = EMUSESPipeline(self.args, inference_data=inference_data)
        
        # Verify context has inference-specific keys
        self.assertIn("inference_features", pipeline.context)
        self.assertIn("inference_labels", pipeline.context)
        self.assertIn("model_path", pipeline.context)
        self.assertIn("cli_inference_mode", pipeline.context)
        
        # Verify data was processed correctly
        self.assertEqual(pipeline.context["model_path"], str(self.model_dir))
        self.assertTrue(pipeline.context["cli_inference_mode"])
        self.assertIsInstance(pipeline.context["inference_features"], np.ndarray)
        self.assertEqual(pipeline.context["inference_features"].shape[0], 2)  # 2 samples
        
    def test_pipeline_without_inference_data_still_works(self):
        """Test that normal pipeline initialization still works."""
        # Test without inference_data parameter
        with patch.object(EMUSESPipeline, 'process_dataset', return_value=(
            np.array([[1, 2], [3, 4]]), "spreadsheet", None, None
        )):
            with patch.object(EMUSESPipeline, 'load_and_process_scores'):
                pipeline = EMUSESPipeline(self.args)
                self.assertIsNotNone(pipeline)
                self.assertIsNone(pipeline._inference_data)
        
    def test_double_processing_eliminated(self):
        """Test that double processing is eliminated."""
        inference_data = {
            "input_path": str(self.data_file),
            "scores_path": str(self.scores_file),
            "model_path": str(self.model_dir)
        }
        
        # Create pipeline - should process data during init
        pipeline = EMUSESPipeline(self.args, inference_data=inference_data)
        
        # Verify data is already processed
        self.assertIsNotNone(pipeline.input_matrix)
        self.assertIsNotNone(pipeline.dataset_type)
        
        # Mock process_dataset to verify it's not called again
        with patch.object(pipeline, 'process_dataset') as mock_process:
            # Call format_args - should return early
            pipeline.format_args()
            # Should not process dataset again
            mock_process.assert_not_called()


if __name__ == "__main__":
    unittest.main()