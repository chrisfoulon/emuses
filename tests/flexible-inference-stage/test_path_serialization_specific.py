"""
Test to reproduce the exact JSON serialization issue from the main test suite.
"""
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import MagicMock

from emuses.pipelines.inference_stage import InferenceStage
from emuses.pipelines.pipeline_config import PipelineConfig


class TestPathSerializationIssue(unittest.TestCase):
    """Test to reproduce PosixPath JSON serialization issue"""

    def setUp(self):
        """Set up test environment exactly like the failing tests."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_path = Path(self.temp_dir.name) / "test_model"
        self.model_path.mkdir(exist_ok=True)
        
        # Use PipelineConfig like the failing tests
        self.config = PipelineConfig(
            output_folder=self.temp_dir.name,
            model_path=str(self.model_path),
            data_path="test_data.csv",
            validate_mode=False
        )

    def tearDown(self):
        """Clean up test environment.""" 
        self.temp_dir.cleanup()

    def test_inference_stage_paths_are_not_posixpath_objects(self):
        """Test that InferenceStage stores paths as strings, not Path objects"""
        stage = InferenceStage(self.config)
        
        # The problem: if these are Path objects, they can't be JSON serialized
        # We need to ensure they are strings
        self.assertIsInstance(stage.model_path, str, "model_path should be string for JSON serialization")
        self.assertIsInstance(stage.data_path, str, "data_path should be string for JSON serialization")
        
        # Test JSON serialization of stage attributes
        stage_data = {
            'model_path': stage.model_path,
            'data_path': stage.data_path,
            'output_path': stage.output_path,
            'validate_mode': stage.validate_mode
        }
        
        # This should not raise TypeError: Object of type PosixPath is not JSON serializable
        try:
            json.dumps(stage_data)
        except TypeError as e:
            if "PosixPath" in str(e):
                self.fail(f"JSON serialization failed due to PosixPath object: {e}")
            else:
                raise