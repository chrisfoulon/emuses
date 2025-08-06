# tests/pipelines/test_inference_stage.py

"""
Test suite for InferenceStage implementation.

Tests inference pipeline functionality including model loading, mode detection,
feature transformation, and result formatting.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from emuses.pipelines.inference_stage import InferenceStage
from emuses.pipelines.pipeline_config import PipelineConfig


class TestInferenceStageBasic(unittest.TestCase):
    """Basic InferenceStage functionality tests."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for test models
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_path = Path(self.temp_dir.name) / "test_model"
        self.model_path.mkdir(exist_ok=True)
        
        # Create minimal config for testing
        self.config = PipelineConfig(
            output_folder=self.temp_dir.name,
            model_path=str(self.model_path),
            data_path="test_data.csv",
            validate_mode=False
        )

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    def test_inference_stage_initialization(self):
        """Test InferenceStage can be initialized with valid config."""
        stage = InferenceStage(self.config)
        
        # Verify basic attributes are set
        self.assertEqual(stage.model_path, str(self.model_path))
        self.assertEqual(stage.data_path, "test_data.csv")
        self.assertFalse(stage.validate_mode)
        self.assertTrue(hasattr(stage, 'config'))

    def test_inference_stage_inherits_from_pipeline_stage(self):
        """Test InferenceStage properly inherits from PipelineStage."""
        stage = InferenceStage(self.config)
        
        # Should have run method from PipelineStage interface
        self.assertTrue(hasattr(stage, 'run'))
        self.assertTrue(callable(stage.run))
        
        # Should have config attribute from base class
        self.assertIs(stage.config, self.config)


class TestInferenceStageModelLoading(unittest.TestCase):
    """Test model loading functionality."""

    def setUp(self):
        """Set up test environment with mock models."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_path = Path(self.temp_dir.name) / "trained_models"
        self.model_path.mkdir(exist_ok=True)
        
        self.config = PipelineConfig(
            output_folder=self.temp_dir.name,
            model_path=str(self.model_path)
        )

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    def test_load_trained_models_detects_missing_model_directory(self):
        """Test error handling when model directory is missing."""
        # Use non-existent model path
        self.config.model_path = str(Path(self.temp_dir.name) / "nonexistent")
        stage = InferenceStage(self.config)
        
        with self.assertRaises(FileNotFoundError):
            stage._load_trained_models()

    @patch('emuses.pipelines.inference_stage.load_umap_model')
    @patch('emuses.pipelines.inference_stage.ModelIOManager')
    def test_load_trained_models_uses_model_io_manager(self, mock_manager_class, mock_load_umap):
        """Test that model loading uses ModelIOManager."""
        # Create mock model manager
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        
        # Mock UMAP loading to return a mock model
        mock_umap_model = MagicMock()
        mock_load_umap.return_value = (mock_umap_model, Path('/test/path'))
        
        stage = InferenceStage(self.config)
        result = stage._load_trained_models()
        
        # Verify ModelIOManager was instantiated
        mock_manager_class.assert_called_once_with(base_path=Path(self.temp_dir.name) / "trained_models")
        
        # Verify UMAP loading was attempted
        mock_load_umap.assert_called_once()
        
        # Verify result structure
        self.assertIsNotNone(result)
        self.assertIn('umap_model', result)
        self.assertIn('prediction_models', result)
        self.assertIn('metadata', result)


class TestInferenceStageEnsemblePrediction(unittest.TestCase):
    """Test ensemble prediction functionality."""

    def setUp(self):
        """Set up test environment with mock models and embeddings."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_path = Path(self.temp_dir.name) / "trained_models"
        self.model_path.mkdir(exist_ok=True)
        
        self.config = PipelineConfig(
            output_folder=self.temp_dir.name,
            model_path=str(self.model_path),
            data_path="test_data.csv"
        )

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    def test_predict_with_ensemble_models(self):
        """Test prediction with multiple ensemble models."""
        stage = InferenceStage(self.config)
        
        # Mock embeddings (output from UMAP transformation)
        embeddings = np.random.rand(50, 2)  # 50 samples, 2D embeddings
        
        # Mock trained models with prediction models
        mock_models = {
            'umap_model': MagicMock(),
            'prediction_models': [
                {'model': MagicMock(), 'name': 'model_1', 'score': 0.85},
                {'model': MagicMock(), 'name': 'model_2', 'score': 0.78}
            ],
            'metadata': {}
        }
        
        # Configure mock predictions (must match number of input samples)
        mock_models['prediction_models'][0]['model'].predict.return_value = np.random.rand(50)
        mock_models['prediction_models'][1]['model'].predict.return_value = np.random.rand(50)
        
        # Test prediction
        predictions = stage._predict(embeddings, mock_models)
        
        # Verify prediction structure
        self.assertIsInstance(predictions, dict)
        self.assertIn('ensemble_predictions', predictions)
        self.assertIn('individual_predictions', predictions)
        self.assertIn('confidence_scores', predictions)
        
        # Verify ensemble predictions shape
        ensemble_pred = predictions['ensemble_predictions']
        self.assertEqual(len(ensemble_pred), 50)  # Same as input embeddings
        
    def test_predict_with_confidence_scoring(self):
        """Test that prediction includes confidence scores."""
        stage = InferenceStage(self.config)
        embeddings = np.random.rand(10, 2)
        
        mock_models = {
            'prediction_models': [
                {'model': MagicMock(), 'name': 'model_1', 'score': 0.90}
            ]
        }
        
        # Mock prediction with confidence
        mock_models['prediction_models'][0]['model'].predict.return_value = np.random.rand(10)
        if hasattr(mock_models['prediction_models'][0]['model'], 'predict_proba'):
            mock_models['prediction_models'][0]['model'].predict_proba.return_value = np.random.rand(10, 2)
        
        predictions = stage._predict(embeddings, mock_models)
        
        # Verify confidence scores are included
        self.assertIn('confidence_scores', predictions)
        confidence = predictions['confidence_scores']
        self.assertEqual(len(confidence), 10)  # One per sample
        
    def test_predict_handles_empty_prediction_models(self):
        """Test error handling when no prediction models are available."""
        stage = InferenceStage(self.config)
        embeddings = np.random.rand(10, 2)
        
        mock_models = {
            'prediction_models': [],  # No prediction models
            'metadata': {}
        }
        
        # Should return dummy predictions instead of raising an error
        results = stage._predict(embeddings, mock_models)
        
        # Verify dummy prediction structure
        self.assertIn('ensemble_predictions', results)
        self.assertIn('individual_predictions', results)
        self.assertIn('confidence_scores', results)
        self.assertIn('model_count', results)
        self.assertIn('model_names', results)
        
        # Check that dummy predictions have correct shape and values
        self.assertEqual(len(results['ensemble_predictions']), 10)  # Same as embeddings
        self.assertEqual(results['model_count'], 0)
        self.assertEqual(results['model_names'], [])


class TestInferenceStageResultFormatting(unittest.TestCase):
    """Test inference result formatting and output functionality."""

    def setUp(self):
        """Set up test environment with mock complete pipeline."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_path = Path(self.temp_dir.name) / "trained_models"
        self.model_path.mkdir(exist_ok=True)
        
        # Create output directory for results
        self.output_path = Path(self.temp_dir.name) / "inference_output"
        self.output_path.mkdir(exist_ok=True)
        
        self.config = PipelineConfig(
            output_folder=self.temp_dir.name,
            model_path=str(self.model_path),
            data_path="test_data.csv",
            output_path=str(self.output_path)
        )

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    def test_format_results_includes_performance_breakdown(self):
        """Test that result formatting includes detailed performance breakdown."""
        stage = InferenceStage(self.config)
        
        # Mock prediction results
        predictions = {
            'ensemble_predictions': np.array([0.5, 0.7, 0.3]),
            'individual_predictions': {'model_1': np.array([0.4, 0.8, 0.2])},
            'confidence_scores': np.array([0.9, 0.8, 0.7]),
            'model_count': 1,
            'model_names': ['model_1']
        }
        
        # Mock performance data
        performance_data = {
            'data_load_duration_ms': 50.0,
            'transform_duration_ms': 100.0,
            'prediction_duration_ms': 75.0,
            'total_duration_ms': 225.0,
            'throughput_samples_per_sec': 13.3
        }
        
        # Test result formatting
        formatted_results = stage._format_results(predictions, "inference", performance_data)
        
        # Verify result structure
        self.assertIsInstance(formatted_results, dict)
        self.assertIn('predictions', formatted_results)
        self.assertIn('performance_breakdown', formatted_results)
        self.assertIn('metadata', formatted_results)
        
        # Verify performance breakdown
        perf = formatted_results['performance_breakdown']
        self.assertIn('data_load_ms', perf)
        self.assertIn('transform_ms', perf)
        self.assertIn('prediction_ms', perf)
        self.assertIn('total_ms', perf)
        self.assertIn('throughput_samples_per_sec', perf)

    def test_save_results_creates_output_files(self):
        """Test that result saving creates proper output files."""
        stage = InferenceStage(self.config)
        
        # Mock formatted results
        results = {
            'predictions': np.array([0.5, 0.7, 0.3]),
            'confidence_scores': np.array([0.9, 0.8, 0.7]),
            'performance_breakdown': {'total_ms': 200.0},
            'metadata': {'mode': 'inference', 'samples_processed': 3}
        }
        
        # Test result saving with default CSV format
        output_paths = stage._save_results(results)
        
        # Verify output files were created (CSV format by default)
        self.assertIsInstance(output_paths, dict)
        self.assertIn('predictions_csv', output_paths)
        self.assertIn('metadata_file', output_paths)
        
        # Verify files exist
        predictions_file = Path(output_paths['predictions_csv'])
        metadata_file = Path(output_paths['metadata_file'])
        
        self.assertTrue(predictions_file.exists())
        self.assertTrue(metadata_file.exists())
        self.assertEqual(predictions_file.suffix, '.csv')
        
        # Test NPY format explicitly
        output_paths_npy = stage._save_results(results, output_format='npy')
        
        # Verify NPY files were created
        self.assertIn('predictions_file', output_paths_npy)
        self.assertIn('metadata_file', output_paths_npy)
        
        predictions_npy = Path(output_paths_npy['predictions_file'])
        self.assertTrue(predictions_npy.exists())
        self.assertEqual(predictions_npy.suffix, '.npy')

    def test_format_results_handles_validation_mode(self):
        """Test result formatting includes validation metrics when available."""
        stage = InferenceStage(self.config)
        
        # Mock prediction results for validation mode
        predictions = {
            'ensemble_predictions': np.array([0.5, 0.7, 0.3]),
            'confidence_scores': np.array([0.9, 0.8, 0.7])
        }
        
        # Mock validation metrics
        validation_metrics = {
            'accuracy': 0.85,
            'mse': 0.12,
            'r2_score': 0.78
        }
        
        performance_data = {'total_duration_ms': 200.0}
        
        # Test formatting with validation metrics
        formatted_results = stage._format_results(
            predictions, "validation", performance_data, validation_metrics
        )
        
        # Verify validation metrics are included
        self.assertIn('validation_metrics', formatted_results)
        validation = formatted_results['validation_metrics']
        self.assertEqual(validation['accuracy'], 0.85)
        self.assertEqual(validation['mse'], 0.12)
        self.assertEqual(validation['r2_score'], 0.78)


class TestInferenceStageCSVOutput(unittest.TestCase):
    """Test CSV output format functionality."""

    def setUp(self):
        """Set up test environment with mock complete pipeline."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_path = Path(self.temp_dir.name) / "trained_models"
        self.model_path.mkdir(exist_ok=True)
        
        # Create output directory for results
        self.output_path = Path(self.temp_dir.name) / "inference_output"
        self.output_path.mkdir(exist_ok=True)
        
        self.config = PipelineConfig(
            output_folder=self.temp_dir.name,
            model_path=str(self.model_path),
            data_path="test_data.csv",
            output_path=str(self.output_path)
        )

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    def test_save_results_creates_csv_by_default(self):
        """Test that result saving creates CSV files by default."""
        stage = InferenceStage(self.config)
        
        # Mock formatted results with sample data
        results = {
            'predictions': np.array([0.5, 0.7, 0.3]),
            'confidence_scores': np.array([0.9, 0.8, 0.7]),
            'individual_predictions': {
                'model_1': np.array([0.4, 0.8, 0.2]),
                'model_2': np.array([0.6, 0.6, 0.4])
            },
            'performance_breakdown': {'total_ms': 200.0},
            'metadata': {'mode': 'inference', 'samples_processed': 3}
        }
        
        # Test result saving with default CSV format
        output_paths = stage._save_results(results)
        
        # Verify CSV files were created
        self.assertIn('predictions_csv', output_paths)
        self.assertIn('confidence_csv', output_paths)
        
        # Verify CSV files exist and have correct extension
        predictions_csv = Path(output_paths['predictions_csv'])
        confidence_csv = Path(output_paths['confidence_csv'])
        
        self.assertTrue(predictions_csv.exists())
        self.assertTrue(confidence_csv.exists())
        self.assertEqual(predictions_csv.suffix, '.csv')
        self.assertEqual(confidence_csv.suffix, '.csv')

    def test_save_results_csv_format_matches_training_scores(self):
        """Test that CSV format is consistent with training scores format."""
        stage = InferenceStage(self.config)
        
        # Mock results with multiple samples and models
        results = {
            'predictions': np.array([0.5, 0.7, 0.3, 0.8]),
            'confidence_scores': np.array([0.9, 0.8, 0.7, 0.85]),
            'individual_predictions': {
                'model_rf': np.array([0.4, 0.8, 0.2, 0.9]),
                'model_gb': np.array([0.6, 0.6, 0.4, 0.7])
            },
            'performance_breakdown': {'total_ms': 150.0},
            'metadata': {
                'mode': 'inference', 
                'samples_processed': 4,
                'model_names': ['model_rf', 'model_gb']
            }
        }
        
        # Save results and read CSV content
        output_paths = stage._save_results(results)
        
        # Read and verify predictions CSV structure
        import pandas as pd
        predictions_df = pd.read_csv(output_paths['predictions_csv'])
        
        # Verify CSV has proper structure similar to training scores
        self.assertIn('sample_id', predictions_df.columns)
        self.assertIn('ensemble_prediction', predictions_df.columns)
        self.assertIn('confidence_score', predictions_df.columns)
        
        # Verify individual model columns are present
        for model_name in results['metadata']['model_names']:
            self.assertIn(model_name, predictions_df.columns)
        
        # Verify correct number of rows
        self.assertEqual(len(predictions_df), 4)

    def test_save_results_with_npy_option(self):
        """Test that NPY format can still be used when explicitly requested."""
        stage = InferenceStage(self.config)
        
        # Mock results
        results = {
            'predictions': np.array([0.5, 0.7, 0.3]),
            'confidence_scores': np.array([0.9, 0.8, 0.7]),
            'performance_breakdown': {'total_ms': 100.0},
            'metadata': {'mode': 'inference', 'samples_processed': 3}
        }
        
        # Test result saving with NPY format option
        output_paths = stage._save_results(results, output_format='npy')
        
        # Verify NPY files were created
        self.assertIn('predictions_file', output_paths)
        
        # Verify NPY files exist and have correct extension
        predictions_npy = Path(output_paths['predictions_file'])
        self.assertTrue(predictions_npy.exists())
        self.assertEqual(predictions_npy.suffix, '.npy')


class TestInferenceStageIntegration(unittest.TestCase):
    """Integration tests for InferenceStage with realistic model artifacts."""

    def setUp(self):
        """Set up test environment with mock model artifacts."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_path = Path(self.temp_dir.name) / "trained_models"
        self.model_path.mkdir(exist_ok=True)
        
        # Create output directory for results
        self.output_path = Path(self.temp_dir.name) / "inference_output"
        self.output_path.mkdir(exist_ok=True)
        
        self.config = PipelineConfig(
            output_folder=self.temp_dir.name,
            model_path=str(self.model_path),
            data_path="test_data.csv",
            output_path=str(self.output_path)
        )

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    def test_full_inference_workflow_with_mock_artifacts(self):
        """Test complete inference workflow with mock model artifacts."""
        stage = InferenceStage(self.config)
        
        # Create context with realistic settings
        context = {
            "verify_integrity": False,  # Skip integrity check for mock models
            "output_format": "csv"
        }
        
        # Mock the model loading to return realistic model structure
        def mock_load_models():
            from unittest.mock import MagicMock
            mock_umap = MagicMock()
            mock_umap.transform.return_value = np.random.rand(20, 2)
            
            mock_model_1 = MagicMock()
            mock_model_1.predict.return_value = np.random.rand(20)
            
            mock_model_2 = MagicMock()
            mock_model_2.predict.return_value = np.random.rand(20)
            
            return {
                'umap_model': mock_umap,
                'prediction_models': [
                    {'model': mock_model_1, 'name': 'random_forest', 'score': 0.85},
                    {'model': mock_model_2, 'name': 'gradient_boost', 'score': 0.82}
                ],
                'metadata': {
                    'min_embeddings': np.array([0.0, 0.0]),
                    'max_embeddings': np.array([1.0, 1.0])
                }
            }
        
        # Mock the feature loading to return realistic data
        def mock_load_features(data_path):
            return np.random.rand(20, 50)  # 20 samples, 50 features
        
        # Patch methods for testing
        stage._load_trained_models = mock_load_models
        stage._load_features = mock_load_features
        
        # Run inference
        results = stage.run(context)
        
        # Verify results structure
        self.assertIsInstance(results, dict)
        self.assertIn('mode', results)
        self.assertIn('status', results)
        self.assertIn('samples_processed', results)
        self.assertIn('predictions', results)
        self.assertIn('performance_breakdown', results)
        self.assertIn('output_files', results)
        
        # Verify inference mode (no labels detected)
        self.assertEqual(results['mode'], 'inference')
        self.assertEqual(results['status'], 'completed')
        self.assertEqual(results['samples_processed'], 20)
        
        # Verify output files were created
        output_files = results['output_files']
        self.assertIn('predictions_csv', output_files)
        self.assertIn('metadata_file', output_files)
        
        # Verify files exist
        for file_path in output_files.values():
            self.assertTrue(Path(file_path).exists())

    def test_validation_mode_with_metrics(self):
        """Test inference in validation mode with performance metrics."""
        stage = InferenceStage(self.config)
        stage.validate_mode = True  # Force validation mode
        
        context = {
            "verify_integrity": False,
            "output_format": "csv"
        }
        
        # Mock components for validation mode
        def mock_load_models():
            from unittest.mock import MagicMock
            mock_umap = MagicMock()
            mock_umap.transform.return_value = np.random.rand(15, 2)
            
            mock_model = MagicMock()
            mock_model.predict.return_value = np.random.rand(15)
            
            return {
                'umap_model': mock_umap,
                'prediction_models': [
                    {'model': mock_model, 'name': 'test_model', 'score': 0.90}
                ],
                'metadata': {}
            }
        
        def mock_load_features(data_path):
            return np.random.rand(15, 30)
        
        stage._load_trained_models = mock_load_models
        stage._load_features = mock_load_features
        
        # Run inference in validation mode
        results = stage.run(context)
        
        # Verify validation mode
        self.assertEqual(results['mode'], 'validation')
        self.assertEqual(results['samples_processed'], 15)
        
        # Verify performance tracking
        performance = results['performance_breakdown']
        self.assertIn('total_duration_ms', performance)
        self.assertIn('throughput_samples_per_sec', performance)
        self.assertGreater(performance['total_duration_ms'], 0)
        self.assertGreater(performance['throughput_samples_per_sec'], 0)

    def test_error_handling_with_missing_models(self):
        """Test error handling when model files are missing."""
        stage = InferenceStage(self.config)
        
        context = {"verify_integrity": True}
        
        # Run inference with missing models (should raise ValueError for UMAP model not available)
        with self.assertRaises(ValueError) as cm:
            stage.run(context)
        
        # Verify error message is about UMAP model
        self.assertIn("UMAP model not available for transformation", str(cm.exception))

    def test_output_format_selection(self):
        """Test that output format selection works correctly."""
        stage = InferenceStage(self.config)
        
        # Mock components
        def mock_load_models():
            from unittest.mock import MagicMock
            mock_umap = MagicMock()
            mock_umap.transform.return_value = np.random.rand(10, 2)
            
            mock_model = MagicMock()
            mock_model.predict.return_value = np.random.rand(10)
            
            return {
                'umap_model': mock_umap,
                'prediction_models': [
                    {'model': mock_model, 'name': 'test_model', 'score': 0.85}
                ],
                'metadata': {}
            }
        
        def mock_load_features(data_path):
            return np.random.rand(10, 25)
        
        stage._load_trained_models = mock_load_models
        stage._load_features = mock_load_features
        
        # Test CSV format
        context_csv = {"verify_integrity": False, "output_format": "csv"}
        results_csv = stage.run(context_csv)
        
        output_files_csv = results_csv['output_files']
        self.assertIn('predictions_csv', output_files_csv)
        self.assertTrue(output_files_csv['predictions_csv'].endswith('.csv'))
        
        # Test NPY format
        context_npy = {"verify_integrity": False, "output_format": "npy"}
        results_npy = stage.run(context_npy)
        
        output_files_npy = results_npy['output_files']
        self.assertIn('predictions_file', output_files_npy)
        self.assertTrue(output_files_npy['predictions_file'].endswith('.npy'))

    def test_confidence_scoring_accuracy(self):
        """Test that confidence scoring produces reasonable values."""
        stage = InferenceStage(self.config)
        
        # Create mock models with varying prediction consistency
        def mock_load_models():
            from unittest.mock import MagicMock
            mock_umap = MagicMock()
            mock_umap.transform.return_value = np.random.rand(5, 2)
            
            # Create models with different prediction patterns
            mock_model_1 = MagicMock()
            mock_model_1.predict.return_value = np.array([0.8, 0.2, 0.9, 0.1, 0.7])
            
            mock_model_2 = MagicMock()
            mock_model_2.predict.return_value = np.array([0.75, 0.25, 0.85, 0.15, 0.65])  # Similar to model 1
            
            mock_model_3 = MagicMock()
            mock_model_3.predict.return_value = np.array([0.1, 0.9, 0.2, 0.8, 0.3])  # Very different
            
            return {
                'umap_model': mock_umap,
                'prediction_models': [
                    {'model': mock_model_1, 'name': 'model_1', 'score': 0.85},
                    {'model': mock_model_2, 'name': 'model_2', 'score': 0.83},
                    {'model': mock_model_3, 'name': 'model_3', 'score': 0.78}
                ],
                'metadata': {}
            }
        
        def mock_load_features(data_path):
            return np.random.rand(5, 20)
        
        stage._load_trained_models = mock_load_models
        stage._load_features = mock_load_features
        
        context = {"verify_integrity": False}
        results = stage.run(context)
        
        # Verify confidence scores are computed
        prediction_details = results['prediction_details']
        confidence_scores = prediction_details['confidence_scores']
        
        self.assertEqual(len(confidence_scores), 5)
        
        # Confidence scores should be between 0 and 1
        for score in confidence_scores:
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)
        
        # For samples where models agree (0 and 1), confidence should be higher
        # For samples where models disagree (first sample), confidence should be lower
        # Note: confidence = 1.0 - std, so lower std = higher confidence


if __name__ == '__main__':
    unittest.main()