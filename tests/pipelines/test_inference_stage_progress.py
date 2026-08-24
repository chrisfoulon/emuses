# tests/pipelines/test_inference_stage_progress.py

"""
Test suite for InferenceStage progress indicators.

Tests Rich progress bar integration and real-time metrics display.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from emuses.pipelines.inference_stage import InferenceStage


def predict_result(predictions):
    """A ``_predict`` return value in the shape the real method produces.

    These tests used to patch ``_predict`` with a flat ``predictions`` key, a shape the
    stage stopped returning when multi-target support landed: predictions nest under
    ``target_results[target]``. Everything downstream indexes ``target_results``, so the
    stale stub made all five tests die with ``KeyError: 'target_results'`` in production
    code that was doing exactly the right thing.
    """
    predictions = np.asarray(predictions)
    return {
        'target_results': {
            'target_0': {
                'ensemble_predictions': predictions,
                'normalized_ensemble_predictions': None,
                'individual_predictions': {'stub_model': predictions},
                'confidence_scores': np.full(len(predictions), 0.8),
                'model_count': 1,
                'model_names': ['stub_model'],
                'denormalization_applied': False,
            }
        },
        'target_count': 1,
        'individual_predictions': {'stub_model': predictions},
        'model_count': 1,
        'model_names': ['stub_model'],
    }



class TestInferenceStageProgress(unittest.TestCase):
    """Test progress indicators in InferenceStage."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_path = Path(self.temp_dir.name) / "test_model"
        self.model_path.mkdir(exist_ok=True)
        self.data_path = Path(self.temp_dir.name) / "test_data.csv"
        
        # Create mock data
        import pandas as pd
        test_data = pd.DataFrame({
            'feature1': [1, 2, 3, 4, 5],
            'feature2': [2, 4, 6, 8, 10],
            'feature3': [0.1, 0.2, 0.3, 0.4, 0.5]
        })
        test_data.to_csv(self.data_path, index=False)

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    @patch('emuses.pipelines.inference_stage.Progress')
    def test_inference_stage_creates_progress_context(self, mock_progress):
        """Test that InferenceStage creates a Rich Progress context."""
        # Setup mock progress
        mock_progress_instance = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_instance
        
        # Create a simple mock config object
        config = MagicMock()
        config.model_path = self.model_path
        config.data_path = self.data_path
        config.output_folder = self.temp_dir.name
        config.output_folder = self.temp_dir.name
        config.validate_mode = False
        config.verify_integrity = False
        
        stage = InferenceStage(config)
        
        # Mock the required methods
        with patch.object(stage, '_load_trained_models', return_value={}):
            with patch.object(stage, '_load_features_from_context', return_value=np.array([[1, 2], [3, 4]])):
                with patch.object(stage, '_detect_labels', return_value=False):
                    with patch.object(stage, '_transform_features', return_value=np.array([[0.1, 0.2], [0.3, 0.4]])):
                        with patch.object(stage, '_predict', return_value=predict_result([0.7, 0.8])):
                            with patch.object(stage, '_save_results'):
                                # Run should create progress context
                                stage.run({})
        
        # Verify Progress was instantiated
        mock_progress.assert_called_once()

    @patch('emuses.pipelines.inference_stage.Progress')
    def test_progress_indicators_show_main_tasks(self, mock_progress):
        """Test that progress indicators are created for main inference tasks."""
        mock_progress_instance = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_instance
        
        # Create a simple mock config object
        config = MagicMock()
        config.model_path = self.model_path
        config.data_path = self.data_path
        config.output_folder = self.temp_dir.name
        config.output_folder = self.temp_dir.name
        
        stage = InferenceStage(config)
        
        # Mock all dependencies
        with patch.object(stage, '_load_trained_models', return_value={}):
            with patch.object(stage, '_load_features_from_context', return_value=np.array([[1, 2]])):
                with patch.object(stage, '_detect_labels', return_value=False):
                    with patch.object(stage, '_transform_features', return_value=np.array([[0.1, 0.2]])):
                        with patch.object(stage, '_predict', return_value=predict_result([0.7])):
                            with patch.object(stage, '_save_results'):
                                stage.run({})
        
        # Verify that tasks were added to progress
        self.assertTrue(mock_progress_instance.add_task.called)
        
        # Check that main inference phases are tracked
        task_calls = mock_progress_instance.add_task.call_args_list
        # add_task is called with the description positionally, so reading only
        # call[1]['description'] collected nothing and compared against an empty list.
        task_descriptions = [
            call.args[0] if call.args else call.kwargs.get('description', '')
            for call in task_calls
        ]
        
        expected_tasks = [
            "Loading models",
            "Loading data", 
            "Transforming features",
            "Running predictions",
            "Saving results"
        ]
        
        for expected_task in expected_tasks:
            self.assertTrue(any(expected_task in desc for desc in task_descriptions),
                          f"Expected task '{expected_task}' not found in {task_descriptions}")

    @patch('emuses.pipelines.inference_stage.Progress')
    def test_progress_indicators_update_during_execution(self, mock_progress):
        """Test that progress indicators are updated during task execution."""
        mock_progress_instance = MagicMock()
        mock_task_id = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_instance.add_task.return_value = mock_task_id
        
        # Create a simple mock config object
        config = MagicMock()
        config.model_path = self.model_path
        config.data_path = self.data_path
        config.output_folder = self.temp_dir.name
        
        stage = InferenceStage(config)
        
        # Mock dependencies to track progress updates
        def mock_load_features(*args):
            # Simulate progress update during data loading
            return np.array([[1, 2], [3, 4], [5, 6]])
            
        with patch.object(stage, '_load_trained_models', return_value={}):
            with patch.object(stage, '_load_features_from_context', side_effect=mock_load_features):
                with patch.object(stage, '_detect_labels', return_value=False):
                    with patch.object(stage, '_transform_features', return_value=np.array([[0.1], [0.2], [0.3]])):
                        with patch.object(stage, '_predict', return_value=predict_result([0.7, 0.8, 0.9])):
                            with patch.object(stage, '_save_results'):
                                stage.run({})
        
        # Verify that progress was updated (advanced) during execution
        self.assertTrue(mock_progress_instance.advance.called)

    @patch('emuses.pipelines.inference_stage.Progress')
    def test_progress_indicators_show_throughput_metrics(self, mock_progress):
        """Test that progress indicators include throughput and ETA calculations."""
        mock_progress_instance = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_instance
        
        # Create a simple mock config object
        config = MagicMock()
        config.model_path = self.model_path
        config.data_path = self.data_path
        config.output_folder = self.temp_dir.name
        
        stage = InferenceStage(config)
        
        # Mock with larger dataset to test throughput
        large_dataset = np.random.rand(1000, 10)
        
        with patch.object(stage, '_load_trained_models', return_value={}):
            with patch.object(stage, '_load_features_from_context', return_value=large_dataset):
                with patch.object(stage, '_detect_labels', return_value=False):
                    with patch.object(stage, '_transform_features', return_value=np.random.rand(1000, 2)):
                        with patch.object(stage, '_predict', return_value=predict_result(np.random.rand(1000))):
                            with patch.object(stage, '_save_results'):
                                stage.run({})
        
        # Check that progress was configured with total based on data size
        add_task_calls = mock_progress_instance.add_task.call_args_list
        
        # At least one task should have total set based on dataset size
        totals = [call[1].get('total') for call in add_task_calls if 'total' in call[1]]
        self.assertTrue(any(total > 0 for total in totals if total is not None),
                       "Progress should include tasks with defined totals for throughput calculation")

    @patch('emuses.pipelines.inference_stage.Console')
    @patch('emuses.pipelines.inference_stage.Progress')
    def test_progress_integrates_with_rich_console(self, mock_progress, mock_console):
        """Test that progress indicators integrate with Rich console for display."""
        # Create a simple mock config object
        config = MagicMock()
        config.model_path = self.model_path
        config.data_path = self.data_path
        config.output_folder = self.temp_dir.name
        
        stage = InferenceStage(config)
        
        with patch.object(stage, '_load_trained_models', return_value={}):
            with patch.object(stage, '_load_features_from_context', return_value=np.array([[1, 2]])):
                with patch.object(stage, '_detect_labels', return_value=False):
                    with patch.object(stage, '_transform_features', return_value=np.array([[0.1, 0.2]])):
                        with patch.object(stage, '_predict', return_value=predict_result([0.7])):
                            with patch.object(stage, '_save_results'):
                                stage.run({})
        
        # Verify Rich console integration
        mock_console.assert_called_once()


if __name__ == '__main__':
    unittest.main()