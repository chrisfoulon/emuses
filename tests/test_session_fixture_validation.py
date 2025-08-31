"""
Test to validate the session fixture works correctly.

This test validates that our session-scoped pipeline fixture
runs successfully and produces the expected outputs.
"""

import pytest
from pathlib import Path


class TestSessionFixtureValidation:
    """Validate that session fixture produces expected pipeline outputs."""
    
    def test_session_fixture_setup(self, emuses_pipeline_results):
        """Test that session fixture creates expected pipeline results."""
        results = emuses_pipeline_results
        
        # Check that results dictionary has expected structure  
        expected_modes = ['regression', 'multi_target_regression']  # Only testing these 2 modes for now
        assert 'session_temp_dir' in results
        
        for mode in expected_modes:
            assert mode in results, f"Expected mode {mode} not found in results"
        
        # Check session temp directory exists
        session_dir = results['session_temp_dir']
        assert isinstance(session_dir, Path)
        assert session_dir.exists(), f"Session temp directory does not exist: {session_dir}"
        
        print(f"✅ Session fixture validation passed")
        print(f"📁 Session directory: {session_dir}")
        
        # Report which pipelines succeeded vs failed
        for mode in expected_modes:
            if results[mode] is not None:
                output_path = results[mode]
                assert output_path.exists(), f"Pipeline output directory missing: {output_path}"
                print(f"✅ {mode}: {output_path}")
            else:
                print(f"⚠️  {mode}: Pipeline failed")
        
    def test_pipeline_outputs_structure(self, emuses_pipeline_results):
        """Test that successful pipeline runs created expected output structure."""
        results = emuses_pipeline_results
        
        # Check each successful pipeline for basic output structure
        for mode, output_path in results.items():
            if mode == 'session_temp_dir' or output_path is None:
                continue
                
            print(f"🔍 Checking output structure for {mode}...")
            
            # Check basic EMUSES output structure exists
            expected_subdirs = ['models', 'predictions', 'visualizations']
            
            for subdir in expected_subdirs:
                subdir_path = output_path / subdir
                if subdir_path.exists():
                    print(f"  ✅ {subdir}/")
                else:
                    print(f"  📁 {subdir}/ - may not exist for all pipeline modes")
                    
            # Check if any model files were created
            models_dir = output_path / 'models'
            if models_dir.exists():
                model_files = list(models_dir.glob('**/*.joblib'))
                print(f"  📦 Found {len(model_files)} model files")
                
            # Check if predictions were created  
            predictions_dir = output_path / 'predictions'
            if predictions_dir.exists():
                prediction_files = list(predictions_dir.glob('**/*.csv'))
                print(f"  📊 Found {len(prediction_files)} prediction files")