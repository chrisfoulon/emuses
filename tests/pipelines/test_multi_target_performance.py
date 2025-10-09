"""
Test multi-target performance validation.

Compares performance characteristics between single-target and multi-target
prediction scenarios to ensure multi-target support doesn't degrade performance.
"""
import time
import numpy as np
import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.ensemble import RandomForestRegressor

from emuses.pipelines.inference_stage import InferenceStage
from emuses.tools.features_utils import RawCoords, GWD


class TestMultiTargetPerformance:
    """Test multi-target vs single-target performance characteristics."""
    
    def create_test_models(self, n_models_per_target, targets, train_coords, train_labels, feature_type='raw'):
        """Helper to create test models with specified feature types."""
        models = []
        
        for target_idx, target in enumerate(targets):
            target_labels = train_labels[target_idx] if isinstance(train_labels, list) else train_labels
            
            for fold in range(n_models_per_target):
                if feature_type == 'raw':
                    features = FeatureUnion([("raw", RawCoords())])
                elif feature_type == 'gwd':
                    features = FeatureUnion([
                        ("raw", RawCoords()),
                        ("gwd", GWD(sigma=0.1))
                    ])
                else:
                    features = FeatureUnion([("raw", RawCoords())])
                
                model = Pipeline([
                    ("feat", features),
                    ("est", RandomForestRegressor(n_estimators=5, random_state=100+target_idx*10+fold))
                ])
                model.fit(train_coords, target_labels)
                
                model_info = {
                    'model': model,
                    'fold_info': f'fold_{fold}'
                }
                
                # Add target info for multi-target scenarios
                if len(targets) > 1:
                    model_info['target'] = target
                    
                models.append(model_info)
        
        return models

    def test_single_target_vs_multi_target_prediction_timing(self):
        """Compare prediction timing between single-target and multi-target scenarios."""
        # Arrange - Create test data
        np.random.seed(42)
        n_train, n_test = 50, 30
        n_features = 2
        
        train_coords = np.random.randn(n_train, n_features)
        test_coords = np.random.randn(n_test, n_features)
        
        # Create training labels
        train_labels_single = np.random.randn(n_train)
        train_labels_multi = [
            np.random.randn(n_train),  # Target 0
            np.random.randn(n_train),  # Target 1  
            np.random.randn(n_train)   # Target 2
        ]
        
        config = Mock()
        output_dir = Path(tempfile.mkdtemp())
        config.output_folder = output_dir
        stage = InferenceStage(config)
        stage.output_path = output_dir
        
        n_models_per_target = 3
        
        # Test 1: Single-target performance
        single_target_models = self.create_test_models(
            n_models_per_target, ['single'], train_coords, train_labels_single
        )
        single_models_dict = {"prediction_models": single_target_models}
        
        # Time single-target prediction
        start_time = time.time()
        single_results = stage._predict(test_coords, single_models_dict)
        single_prediction_time = time.time() - start_time
        
        # Test 2: Multi-target performance (3 targets, same total number of models)
        multi_target_models = self.create_test_models(
            n_models_per_target, ['target_0', 'target_1', 'target_2'], 
            train_coords, train_labels_multi
        )
        multi_models_dict = {"prediction_models": multi_target_models}
        
        # Time multi-target prediction
        start_time = time.time()
        multi_results = stage._predict(test_coords, multi_models_dict)
        multi_prediction_time = time.time() - start_time
        
        # Assert - Performance comparison
        print(f"Single-target prediction time: {single_prediction_time:.4f}s")
        print(f"Multi-target prediction time: {multi_prediction_time:.4f}s")
        print(f"Multi-target overhead: {(multi_prediction_time / single_prediction_time - 1) * 100:.1f}%")
        
        # Multi-target should not be significantly slower (allow up to 6x overhead for organization)
        assert multi_prediction_time < single_prediction_time * 6.0, \
            f"Multi-target too slow: {multi_prediction_time:.4f}s vs {single_prediction_time:.4f}s"
        
        # Both should complete reasonably quickly
        assert single_prediction_time < 10.0, "Single-target prediction too slow"
        assert multi_prediction_time < 15.0, "Multi-target prediction too slow"
        
        # Assert - Result structure correctness
        # Single-target: now has target_results with target_0
        assert 'target_results' in single_results
        assert 'target_0' in single_results['target_results']
        assert single_results['target_count'] == 1
        assert single_results['model_count'] == n_models_per_target
        
        # Multi-target: has target_results key
        assert 'target_results' in multi_results
        assert len(multi_results['target_results']) == 3
        assert multi_results['target_count'] == 3
        assert multi_results['model_count'] == n_models_per_target * 3

    def test_validation_timing_comparison(self):
        """Compare validation timing between single-target and multi-target."""
        # Arrange
        np.random.seed(123)
        n_samples = 100
        
        config = Mock()
        stage = InferenceStage(config)
        
        # Single-target validation data
        single_target_results = {
            'ensemble_predictions': np.random.randn(n_samples),
            'confidence_scores': np.random.rand(n_samples),
            'individual_predictions': {},
            'model_count': 5,
            'model_names': ['model_1', 'model_2', 'model_3', 'model_4', 'model_5']
        }
        single_ground_truth = np.random.randn(n_samples)
        
        # Multi-target validation data
        multi_target_results = {
            'target_0': {
                'ensemble_predictions': np.random.randn(n_samples),
                'confidence_scores': np.random.rand(n_samples),
                'individual_predictions': {},
                'model_count': 2,
                'model_names': ['t0_model_1', 't0_model_2']
            },
            'target_1': {
                'ensemble_predictions': np.random.randn(n_samples),
                'confidence_scores': np.random.rand(n_samples),
                'individual_predictions': {},
                'model_count': 2,
                'model_names': ['t1_model_1', 't1_model_2']
            },
            'target_2': {
                'ensemble_predictions': np.random.randn(n_samples),
                'confidence_scores': np.random.rand(n_samples),
                'individual_predictions': {},
                'model_count': 1,
                'model_names': ['t2_model_1']
            }
        }
        multi_ground_truth = np.random.randn(n_samples, 3)
        
        # Time single-target validation (wrap single results in target_results format)
        single_wrapped_results = {'target_0': single_target_results}
        single_ground_truth_2d = single_ground_truth.reshape(-1, 1)  # Make 2D for single target
        
        start_time = time.time()
        single_validation = stage._calculate_multi_target_validation_metrics(
            single_wrapped_results, single_ground_truth_2d
        )
        single_validation_time = time.time() - start_time
        
        # Time multi-target validation  
        start_time = time.time()
        multi_validation = stage._calculate_multi_target_validation_metrics(
            multi_target_results, multi_ground_truth
        )
        multi_validation_time = time.time() - start_time
        
        # Assert - Performance comparison
        print(f"Single-target validation time: {single_validation_time:.4f}s")
        print(f"Multi-target validation time: {multi_validation_time:.4f}s")
        
        # Multi-target validation should not be excessively slower (allow 20x for per-target processing)
        assert multi_validation_time < single_validation_time * 20.0, \
            f"Multi-target validation too slow: {multi_validation_time:.4f}s vs {single_validation_time:.4f}s"
        
        # Both should complete quickly  
        assert single_validation_time < 1.0, "Single-target validation too slow"
        assert multi_validation_time < 3.0, "Multi-target validation too slow"
        
        # Assert - Result correctness
        assert single_validation is not None
        assert multi_validation is not None
        assert '_summary' not in single_validation  # Single-target doesn't have summary
        assert '_summary' in multi_validation      # Multi-target has summary

    def test_csv_output_timing_comparison(self):
        """Compare CSV output timing between single-target and multi-target."""
        # Arrange
        np.random.seed(456)
        n_samples = 200
        
        config = Mock()
        output_dir = Path(tempfile.mkdtemp())
        config.output_folder = output_dir
        stage = InferenceStage(config)
        stage.output_path = output_dir
        
        # Single-target results (now in target_results format)
        single_results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': np.random.randn(n_samples),
                    'confidence_scores': np.random.rand(n_samples),
                    'individual_predictions': {
                        f'model_{i}': np.random.randn(n_samples) for i in range(5)
                    }
                }
            }
        }
        
        # Multi-target results
        multi_results = {
            'target_results': {
                'target_A': {
                    'ensemble_predictions': np.random.randn(n_samples),
                    'confidence_scores': np.random.rand(n_samples),
                    'individual_predictions': {
                        'model_1': np.random.randn(n_samples),
                        'model_2': np.random.randn(n_samples)
                    }
                },
                'target_B': {
                    'ensemble_predictions': np.random.randn(n_samples),
                    'confidence_scores': np.random.rand(n_samples),
                    'individual_predictions': {
                        'model_3': np.random.randn(n_samples),
                        'model_4': np.random.randn(n_samples)
                    }
                },
                'target_C': {
                    'ensemble_predictions': np.random.randn(n_samples),
                    'confidence_scores': np.random.rand(n_samples),
                    'individual_predictions': {
                        'model_5': np.random.randn(n_samples)
                    }
                }
            }
        }
        
        # Time single-target CSV generation
        single_output_file = output_dir / "single_test.csv"
        start_time = time.time()
        stage._save_predictions_csv(single_results, single_output_file)
        single_csv_time = time.time() - start_time
        
        # Time multi-target CSV generation
        multi_output_file = output_dir / "multi_test.csv"
        start_time = time.time()
        stage._save_predictions_csv(multi_results, multi_output_file)
        multi_csv_time = time.time() - start_time
        
        # Assert - Performance comparison
        print(f"Single-target CSV time: {single_csv_time:.4f}s")
        print(f"Multi-target CSV time: {multi_csv_time:.4f}s")
        
        # Multi-target CSV should not be excessively slower
        assert multi_csv_time < single_csv_time * 3.0, \
            f"Multi-target CSV too slow: {multi_csv_time:.4f}s vs {single_csv_time:.4f}s"
        
        # Both should complete quickly
        assert single_csv_time < 2.0, "Single-target CSV too slow"
        assert multi_csv_time < 6.0, "Multi-target CSV too slow"
        
        # Assert - Files created successfully
        assert single_output_file.exists()
        assert multi_output_file.exists()
        
        # Assert - File sizes reasonable (multi-target should be larger due to more columns)
        single_size = single_output_file.stat().st_size
        multi_size = multi_output_file.stat().st_size
        
        assert multi_size > single_size, "Multi-target CSV should be larger"
        assert multi_size < single_size * 5, "Multi-target CSV shouldn't be excessively larger"

    def test_memory_usage_comparison(self):
        """Compare memory characteristics of single-target vs multi-target processing."""
        import psutil
        import os
        
        # Arrange
        np.random.seed(789)
        n_train, n_test = 100, 80
        n_features = 2
        
        train_coords = np.random.randn(n_train, n_features)
        test_coords = np.random.randn(n_test, n_features)
        
        config = Mock()
        output_dir = Path(tempfile.mkdtemp())
        config.output_folder = output_dir
        stage = InferenceStage(config)
        stage.output_path = output_dir
        
        process = psutil.Process(os.getpid())
        
        # Baseline memory
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Test single-target memory usage
        single_models = self.create_test_models(
            4, ['single'], train_coords, np.random.randn(n_train)
        )
        single_models_dict = {"prediction_models": single_models}
        
        memory_before_single = process.memory_info().rss / 1024 / 1024
        single_results = stage._predict(test_coords, single_models_dict)
        memory_after_single = process.memory_info().rss / 1024 / 1024
        single_memory_usage = memory_after_single - memory_before_single
        
        # Test multi-target memory usage 
        multi_models = self.create_test_models(
            4, ['target_A', 'target_B'], train_coords, 
            [np.random.randn(n_train), np.random.randn(n_train)]
        )
        multi_models_dict = {"prediction_models": multi_models}
        
        memory_before_multi = process.memory_info().rss / 1024 / 1024
        multi_results = stage._predict(test_coords, multi_models_dict)
        memory_after_multi = process.memory_info().rss / 1024 / 1024
        multi_memory_usage = memory_after_multi - memory_before_multi
        
        # Assert - Memory usage comparison
        print(f"Baseline memory: {baseline_memory:.1f}MB")
        print(f"Single-target memory usage: {single_memory_usage:.1f}MB")
        print(f"Multi-target memory usage: {multi_memory_usage:.1f}MB")
        
        # Memory usage should be reasonable
        assert single_memory_usage < 100, f"Single-target using too much memory: {single_memory_usage:.1f}MB"
        assert multi_memory_usage < 200, f"Multi-target using too much memory: {multi_memory_usage:.1f}MB"
        
        # Multi-target shouldn't use dramatically more memory (allow 5x for overhead, handle 0 baseline)
        if single_memory_usage > 0.1:  # Only compare if there's measurable memory usage
            assert multi_memory_usage < single_memory_usage * 5, \
                f"Multi-target memory overhead too high: {multi_memory_usage:.1f}MB vs {single_memory_usage:.1f}MB"
        else:
            # If memory usage is negligible, just ensure it's reasonable
            assert multi_memory_usage < 50, f"Multi-target memory usage too high: {multi_memory_usage:.1f}MB"

    def test_throughput_scalability(self):
        """Test throughput scalability with increasing number of targets and models."""
        # Arrange - Different scale scenarios
        scenarios = [
            {"n_targets": 1, "models_per_target": 2, "name": "small_single"},
            {"n_targets": 3, "models_per_target": 2, "name": "small_multi"},
            {"n_targets": 1, "models_per_target": 6, "name": "medium_single"}, 
            {"n_targets": 3, "models_per_target": 6, "name": "medium_multi"},
            {"n_targets": 5, "models_per_target": 4, "name": "large_multi"}
        ]
        
        np.random.seed(999)
        n_train, n_test = 80, 60
        train_coords = np.random.randn(n_train, 2)
        test_coords = np.random.randn(n_test, 2)
        
        config = Mock()
        output_dir = Path(tempfile.mkdtemp())
        config.output_folder = output_dir
        stage = InferenceStage(config)
        stage.output_path = output_dir
        
        results = {}
        
        for scenario in scenarios:
            n_targets = scenario["n_targets"]
            models_per_target = scenario["models_per_target"]
            name = scenario["name"]
            
            # Create target names
            if n_targets == 1:
                targets = ['single']
                train_labels = np.random.randn(n_train)
            else:
                targets = [f'target_{i}' for i in range(n_targets)]
                train_labels = [np.random.randn(n_train) for _ in range(n_targets)]
            
            # Create models
            models = self.create_test_models(models_per_target, targets, train_coords, train_labels)
            models_dict = {"prediction_models": models}
            
            # Time prediction
            start_time = time.time()
            prediction_results = stage._predict(test_coords, models_dict)
            prediction_time = time.time() - start_time
            
            # Calculate metrics
            total_models = n_targets * models_per_target
            samples_per_second = n_test / prediction_time
            models_per_second = total_models / prediction_time
            
            results[name] = {
                'prediction_time': prediction_time,
                'total_models': total_models,
                'samples_per_second': samples_per_second,
                'models_per_second': models_per_second,
                'n_targets': n_targets
            }
            
            print(f"{name}: {prediction_time:.3f}s, {samples_per_second:.1f} samples/s, {models_per_second:.1f} models/s")
        
        # Assert - Throughput should scale reasonably
        # Single-target scenarios
        small_single = results['small_single']
        medium_single = results['medium_single']
        
        # Multi-target scenarios  
        small_multi = results['small_multi']
        medium_multi = results['medium_multi']
        large_multi = results['large_multi']
        
        # Small multi vs small single (same total models) - allow reasonable overhead
        assert small_multi['prediction_time'] < small_single['prediction_time'] * 5.0, \
            "Small multi-target significantly slower than equivalent single-target"
        
        # Throughput should not degrade catastrophically with more targets
        assert large_multi['samples_per_second'] > 1.0, "Large multi-target throughput too low"
        
        # All scenarios should complete in reasonable time
        for name, result in results.items():
            assert result['prediction_time'] < 20.0, f"{name} took too long: {result['prediction_time']:.3f}s"
            assert result['samples_per_second'] > 0.5, f"{name} throughput too low: {result['samples_per_second']:.1f}"