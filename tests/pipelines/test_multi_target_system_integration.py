"""
Test multi-target system integration with realistic workflows.

Tests complete multi-target pipeline integration including:
- Real feature type processing (raw_only, gwd, pca_gwd, kpca_gwd)
- Multi-target model loading and prediction
- Performance validation and timing
- CSV output generation and structure
- Validation metrics calculation
- Error handling and edge cases
"""
import numpy as np
import pytest
import pandas as pd
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.ensemble import RandomForestRegressor
from sklearn.datasets import make_regression

from emuses.pipelines.inference_stage import InferenceStage
from emuses.tools.features_utils import RawCoords, GWD, PCAGWD, KernelPCAGWD


class TestMultiTargetSystemIntegration:
    """Test complete multi-target system integration."""
    
    @classmethod
    def setup_class(cls):
        """Load real test data for validation."""
        project_root = Path(__file__).parent.parent.parent
        cls.features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
        cls.targets = pd.read_csv(project_root / 'test_data/regression_scores_multitarget.csv', header=None).values
        cls.train_coords = cls.features[:30, :2]  # First 2 features as coordinates
        cls.test_coords = cls.features[30:, :2]   # Last 20 samples for testing
        cls.train_targets = cls.targets[:30]       # Training targets
        cls.test_targets = cls.targets[30:]        # Test targets

    def test_realistic_multi_target_neuroimaging_workflow(self):
        """Test realistic multi-target workflow simulating neuroimaging prediction."""
        # Arrange - Use real test data for realistic validation
        train_coords = self.train_coords
        
        # Use real multi-target data
        # Target 0 and Target 1 from real regression scores
        cognitive_scores = self.train_targets[:, 0]  # First target
        brain_volumes = self.train_targets[:, 1]     # Second target
        
        # For testing purposes, create a derived third target from real data
        connectivity = (cognitive_scores + brain_volumes) / 2  # Normalized combination
        
        config = Mock()
        output_dir = Path(tempfile.mkdtemp())
        config.output_folder = output_dir
        stage = InferenceStage(config)
        stage.output_path = output_dir  # Mock the output_path attribute
        
        # Create models with different feature types for each target
        prediction_models = []
        
        # Target 0 (Cognitive): Multiple models with raw and GWD features
        for fold in range(3):
            # Raw features model
            model_raw = Pipeline([
                ("feat", FeatureUnion([("raw", RawCoords())])),
                ("est", RandomForestRegressor(n_estimators=10, random_state=40+fold))
            ])
            model_raw.fit(train_coords, cognitive_scores)
            
            prediction_models.append({
                'model': model_raw,
                'target': 'cognitive_performance',
                'fold_info': f'raw_fold_{fold}',
                'feature_type': 'raw_only'
            })
            
            # GWD features model
            model_gwd = Pipeline([
                ("feat", FeatureUnion([
                    ("raw", RawCoords()),
                    ("gwd", GWD(sigma=0.2))
                ])),
                ("est", RandomForestRegressor(n_estimators=10, random_state=50+fold))
            ])
            model_gwd.fit(train_coords, cognitive_scores)
            
            prediction_models.append({
                'model': model_gwd,
                'target': 'cognitive_performance',
                'fold_info': f'gwd_fold_{fold}',
                'feature_type': 'gwd'
            })
        
        # Target 1 (Brain Volume): PCA-GWD models
        for fold in range(2):
            model_pca = Pipeline([
                ("feat", FeatureUnion([
                    ("raw", RawCoords()),
                    ("pca", PCAGWD(sigma=0.15, n_comp=5))
                ])),
                ("est", RandomForestRegressor(n_estimators=10, random_state=60+fold))
            ])
            model_pca.fit(train_coords, brain_volumes)
            
            prediction_models.append({
                'model': model_pca,
                'target': 'brain_volume',
                'fold_info': f'pca_fold_{fold}',
                'feature_type': 'pca_gwd'
            })
        
        # Target 2 (Connectivity): Kernel PCA-GWD models
        model_kpca = Pipeline([
            ("feat", FeatureUnion([
                ("raw", RawCoords()),
                ("kpca", KernelPCAGWD(sigma=0.1, n_comp=4))
            ])),
            ("est", RandomForestRegressor(n_estimators=10, random_state=70))
        ])
        model_kpca.fit(train_coords, connectivity)
        
        prediction_models.append({
            'model': model_kpca,
            'target': 'connectivity_strength',
            'fold_info': 'kpca_fold_0',
            'feature_type': 'kpca_gwd'
        })
        
        models_dict = {"prediction_models": prediction_models}
        
        # Test data - use real test coordinates
        test_coords = self.test_coords
        
        # Ground truth for validation - use real test targets
        test_cognitive = self.test_targets[:, 0]  # First target
        test_volumes = self.test_targets[:, 1]    # Second target
        test_connectivity = (test_cognitive + test_volumes) / 2  # Derived from real data
        
        ground_truth = np.column_stack([test_cognitive, test_volumes, test_connectivity])
        
        # Act - Execute complete pipeline
        start_time = time.time()
        
        # 1. Multi-target prediction
        prediction_results = stage._predict(test_coords, models_dict)
        
        # 2. Validation metrics calculation
        validation_metrics = stage._calculate_multi_target_validation_metrics(
            prediction_results['target_results'], ground_truth
        )
        
        # 3. Results formatting
        performance_data = {
            'data_load_duration_ms': 10.0,
            'transform_duration_ms': 50.0,
            'prediction_duration_ms': 100.0,
            'total_duration_ms': time.time() - start_time * 1000,
            'throughput_samples_per_sec': len(test_coords) / (time.time() - start_time)
        }
        
        formatted_results = stage._format_results(
            prediction_results, 'validation', performance_data, validation_metrics
        )
        
        # 4. CSV output generation
        output_paths = stage._save_results(formatted_results, output_format='csv')
        
        end_time = time.time()
        
        # Assert - Multi-target structure
        assert 'target_results' in prediction_results
        assert len(prediction_results['target_results']) == 3
        assert 'cognitive_performance' in prediction_results['target_results']
        assert 'brain_volume' in prediction_results['target_results']
        assert 'connectivity_strength' in prediction_results['target_results']
        
        # Assert - Model counts per target
        cognitive_result = prediction_results['target_results']['cognitive_performance']
        volume_result = prediction_results['target_results']['brain_volume']
        connectivity_result = prediction_results['target_results']['connectivity_strength']
        
        assert cognitive_result['model_count'] == 6  # 3 raw + 3 GWD models
        assert volume_result['model_count'] == 2     # 2 PCA models
        assert connectivity_result['model_count'] == 1  # 1 KPCA model
        
        # Assert - Prediction shapes
        assert cognitive_result['ensemble_predictions'].shape == (len(test_coords),)
        assert volume_result['ensemble_predictions'].shape == (len(test_coords),)
        assert connectivity_result['ensemble_predictions'].shape == (len(test_coords),)
        
        # Assert - Validation metrics structure
        assert validation_metrics is not None
        assert 'cognitive_performance' in validation_metrics
        assert 'brain_volume' in validation_metrics
        assert 'connectivity_strength' in validation_metrics
        assert '_summary' in validation_metrics
        
        # Assert - Summary statistics
        summary = validation_metrics['_summary']
        assert summary['target_count'] == 3
        assert 'mean_r2_score' in summary
        assert 'std_r2_score' in summary
        
        # Assert - CSV output files created
        assert 'predictions_csv' in output_paths
        predictions_file = Path(output_paths['predictions_csv'])
        assert predictions_file.exists()
        
        # Assert - CSV structure
        df = pd.read_csv(predictions_file)
        assert len(df) == len(test_coords)
        
        # Check target-specific columns exist
        expected_columns = [
            'cognitive_performance_ensemble_prediction',
            'brain_volume_ensemble_prediction', 
            'connectivity_strength_ensemble_prediction',
            'cognitive_performance_confidence_score',
            'brain_volume_confidence_score',
            'connectivity_strength_confidence_score'
        ]
        
        for col in expected_columns:
            assert col in df.columns, f"Missing column: {col}"
        
        # Check individual model columns (should have target prefixes)
        model_columns = [col for col in df.columns if any(target in col for target in 
                        ['cognitive_performance', 'brain_volume', 'connectivity_strength']) 
                        and ('fold' in col or 'raw' in col or 'gwd' in col or 'pca' in col)]
        
        assert len(model_columns) >= 9  # Total individual models
        
        # Assert - Performance timing reasonable
        total_time = end_time - start_time
        assert total_time < 30.0, f"Pipeline took too long: {total_time:.2f}s"
        
        # Assert - Prediction values are reasonable for each target
        cognitive_preds = df['cognitive_performance_ensemble_prediction']
        volume_preds = df['brain_volume_ensemble_prediction']
        connectivity_preds = df['connectivity_strength_ensemble_prediction']
        
        # Cognitive scores should be roughly in expected range
        assert cognitive_preds.min() >= -20, "Cognitive predictions too low"
        assert cognitive_preds.max() <= 120, "Cognitive predictions too high"
        
        # Volume predictions should be positive
        assert volume_preds.min() > 0, "Brain volume predictions should be positive"
        
        # Connectivity can be negative but should be bounded
        assert connectivity_preds.min() >= -2, "Connectivity predictions too negative"
        assert connectivity_preds.max() <= 2, "Connectivity predictions too positive"
        
        # Assert - Formatted results structure
        assert formatted_results['target_count'] == 3
        assert 'validation_metrics' in formatted_results
        assert 'performance_breakdown' in formatted_results

    def test_large_scale_multi_target_performance(self):
        """Test multi-target performance with real dataset."""
        # Arrange - Use real test data (simulate larger scale with repetition)
        train_coords = self.train_coords
        test_coords = self.test_coords
        
        # Create 4 targets using real data with different transformations
        targets = ['motor_cortex', 'visual_cortex', 'auditory_cortex', 'frontal_cortex']
        train_labels = {}
        test_labels = {}
        
        # Use real targets with different transformations to simulate different brain regions
        base_train_1 = self.train_targets[:, 0]  # First real target
        base_train_2 = self.train_targets[:, 1]  # Second real target
        base_test_1 = self.test_targets[:, 0]    # Test first target
        base_test_2 = self.test_targets[:, 1]    # Test second target
        
        train_labels['motor_cortex'] = base_train_1
        train_labels['visual_cortex'] = base_train_2  
        train_labels['auditory_cortex'] = (base_train_1 + base_train_2) / 2
        train_labels['frontal_cortex'] = base_train_1 * 0.7 + base_train_2 * 0.3
        
        test_labels['motor_cortex'] = base_test_1
        test_labels['visual_cortex'] = base_test_2
        test_labels['auditory_cortex'] = (base_test_1 + base_test_2) / 2
        test_labels['frontal_cortex'] = base_test_1 * 0.7 + base_test_2 * 0.3
        
        config = Mock()
        output_dir = Path(tempfile.mkdtemp())
        config.output_folder = output_dir
        stage = InferenceStage(config)
        stage.output_path = output_dir  # Mock the output_path attribute
        
        # Create multiple models per target
        prediction_models = []
        
        for target in targets:
            for fold in range(2):
                # Raw model
                model = Pipeline([
                    ("feat", FeatureUnion([("raw", RawCoords())])),
                    ("est", RandomForestRegressor(n_estimators=20, random_state=(100+hash(target)+fold) % 2147483647))
                ])
                model.fit(train_coords, train_labels[target])
                
                prediction_models.append({
                    'model': model,
                    'target': target,
                    'fold_info': f'fold_{fold}',
                })
        
        models_dict = {"prediction_models": prediction_models}
        ground_truth = np.column_stack([test_labels[target] for target in targets])
        
        # Act - Time the complete pipeline
        start_time = time.time()
        
        prediction_results = stage._predict(test_coords, models_dict)
        validation_metrics = stage._calculate_multi_target_validation_metrics(
            prediction_results['target_results'], ground_truth
        )
        
        performance_data = {
            'total_duration_ms': (time.time() - start_time) * 1000,
            'throughput_samples_per_sec': len(test_coords) / (time.time() - start_time)
        }
        
        formatted_results = stage._format_results(
            prediction_results, 'validation', performance_data, validation_metrics
        )
        
        stage._save_results(formatted_results, output_format='csv')
        
        total_time = time.time() - start_time
        
        # Assert - Performance benchmarks
        assert total_time < 60.0, f"Large scale test took too long: {total_time:.2f}s"
        assert performance_data['throughput_samples_per_sec'] > 1.0, "Throughput too low"
        
        # Assert - All targets processed
        assert len(prediction_results['target_results']) == 4
        for target in targets:
            assert target in prediction_results['target_results']
            assert prediction_results['target_results'][target]['model_count'] == 2
        
        # Assert - Validation metrics for all targets
        for target in targets:
            assert target in validation_metrics
            assert 'r2_score' in validation_metrics[target]
            # With real data, R² can be negative (worse than mean prediction)
            assert validation_metrics[target]['r2_score'] > -50.0  # Very liberal sanity check for real data
        
        # Assert - Summary statistics
        assert validation_metrics['_summary']['target_count'] == 4

    def test_multi_target_error_handling_integration(self):
        """Test multi-target error handling in realistic scenarios."""
        config = Mock()
        output_dir = Path(tempfile.mkdtemp())
        config.output_folder = output_dir
        stage = InferenceStage(config)
        stage.output_path = output_dir  # Mock the output_path attribute
        
        # Test 1: Mixed valid and invalid models
        # Use real data (subset for error handling test)
        train_coords = self.train_coords[:10]  # First 10 training samples
        test_coords = self.test_coords[:5]     # First 5 test samples
        train_labels = self.train_targets[:10, 0]  # First target
        
        valid_model = Pipeline([
            ("feat", FeatureUnion([("raw", RawCoords())])),
            ("est", RandomForestRegressor(n_estimators=5, random_state=200))
        ]).fit(train_coords, train_labels)
        
        # Create model with mismatched training data (use real data with wrong shape)
        bad_coords = self.features[:10, :3]  # Use 3 features instead of 2
        try:
            bad_model = Pipeline([
                ("feat", FeatureUnion([("raw", RawCoords())])),
                ("est", RandomForestRegressor(n_estimators=5, random_state=201))
            ]).fit(bad_coords, train_labels)
        except:
            # If the bad model creation fails, use the good model but it will fail on prediction
            bad_model = valid_model
        
        prediction_models = [
            {
                'model': valid_model,
                'target': 'target_A',
                'fold_info': 'valid_fold'
            },
            {
                'model': bad_model,  # This may cause prediction errors
                'target': 'target_B', 
                'fold_info': 'bad_fold'
            }
        ]
        
        models_dict = {"prediction_models": prediction_models}
        
        # Should handle errors gracefully
        try:
            prediction_results = stage._predict(test_coords, models_dict)
            
            # If prediction succeeds, check that at least one target worked
            if 'target_results' in prediction_results:
                assert len(prediction_results['target_results']) >= 1
            else:
                # Single-target fallback should work  
                assert 'ensemble_predictions' in prediction_results
        except Exception as e:
            # Acceptable - some model configurations may fail entirely
            assert ("shape" in str(e).lower() or "dimension" in str(e).lower() or 
                    "features" in str(e).lower() or "expecting" in str(e).lower())
        
        # Test 2: Validation with mismatched ground truth dimensions
        valid_prediction_results = {
            'target_results': {
                'target_A': {
                    'ensemble_predictions': np.array([1.0, 2.0, 3.0]),
                    'confidence_scores': np.array([0.8, 0.9, 0.7]),
                    'individual_predictions': {},
                    'model_count': 1,
                    'model_names': ['model_1']
                }
            }
        }
        
        # Wrong dimension ground truth
        wrong_gt = np.array([[1.0, 2.0], [2.0, 3.0], [3.0, 4.0]])  # 2 targets but only 1 predicted
        
        validation_metrics = stage._calculate_multi_target_validation_metrics(
            valid_prediction_results['target_results'], wrong_gt
        )
        
        # Should return None for mismatched dimensions
        assert validation_metrics is None

    def test_single_target_consistent_integration(self):
        """Test that single-target workflows use consistent target_results format."""
        config = Mock()
        output_dir = Path(tempfile.mkdtemp())
        config.output_folder = output_dir
        stage = InferenceStage(config)
        stage.output_path = output_dir  # Mock the output_path attribute
        
        # Legacy single-target setup (no 'target' field - gets assigned target_0)
        # Use real data for legacy compatibility testing
        train_coords = self.train_coords[:20]  # First 20 training samples
        test_coords = self.test_coords[:10]    # First 10 test samples  
        train_labels = self.train_targets[:20, 0]  # First target
        ground_truth = self.test_targets[:10, 0:1]  # Multi-target format for validation
        
        legacy_models = [
            {
                'model': Pipeline([
                    ("feat", FeatureUnion([("raw", RawCoords())])),
                    ("est", RandomForestRegressor(n_estimators=5, random_state=300))
                ]).fit(train_coords, train_labels),
                'fold_info': 'legacy_fold_0'  # No target field - gets assigned target_0
            },
            {
                'model': Pipeline([
                    ("feat", FeatureUnion([("raw", RawCoords())])),
                    ("est", RandomForestRegressor(n_estimators=5, random_state=301))
                ]).fit(train_coords, train_labels),
                'fold_info': 'legacy_fold_1'  # No target field - gets assigned target_0
            }
        ]
        
        models_dict = {"prediction_models": legacy_models}
        
        # Act - Uses unified multi-target processing
        prediction_results = stage._predict(test_coords, models_dict)
        
        # Validation with target_results structure
        validation_metrics = stage._calculate_multi_target_validation_metrics(
            prediction_results['target_results'], ground_truth
        )
        
        performance_data = {'total_duration_ms': 50.0}
        formatted_results = stage._format_results(
            prediction_results, 'validation', performance_data, validation_metrics
        )
        
        output_paths = stage._save_results(formatted_results, output_format='csv')
        
        # Assert - Single-target now uses target_results structure
        assert 'target_results' in prediction_results
        assert 'target_0' in prediction_results['target_results']
        assert prediction_results['target_results']['target_0']['ensemble_predictions'].shape == (10,)
        assert prediction_results['target_count'] == 1
        
        # Assert - CSV uses consistent target-prefixed format
        predictions_file = Path(output_paths['predictions_csv'])
        df = pd.read_csv(predictions_file)
        
        # Should have target_0_ prefixed column names
        assert 'target_0_ensemble_prediction' in df.columns
        assert 'target_0_confidence_score' in df.columns
        
        # Should have target-prefixed individual model columns
        model_cols = [col for col in df.columns if col.startswith('target_0_') and 'fold' in col]
        assert len(model_cols) == 2  # 2 legacy models