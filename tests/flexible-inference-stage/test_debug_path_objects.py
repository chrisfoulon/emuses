"""
Debug test to identify which attributes in InferenceStage are Path objects.
"""
import tempfile
import unittest
from pathlib import Path

from emuses.pipelines.inference_stage import InferenceStage
from emuses.pipelines.pipeline_config import PipelineConfig


class TestDebugPathObjects(unittest.TestCase):
    """Debug test to find Path objects in InferenceStage"""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_path = Path(self.temp_dir.name) / "test_model"
        self.model_path.mkdir(exist_ok=True)
        
        self.config = PipelineConfig(
            output_folder=self.temp_dir.name,
            model_path=str(self.model_path),
            data_path="test_data.csv",
            validate_mode=False
        )

    def tearDown(self):
        """Clean up test environment.""" 
        self.temp_dir.cleanup()

    def test_debug_path_objects_in_inference_stage(self):
        """Debug test to find all Path objects in InferenceStage"""
        stage = InferenceStage(self.config)
        
        # Check all attributes and identify Path objects
        path_attributes = []
        for attr_name in dir(stage):
            if not attr_name.startswith('_'):  # Skip private attributes
                try:
                    attr_value = getattr(stage, attr_name)
                    if isinstance(attr_value, Path):
                        path_attributes.append(f"{attr_name}: {attr_value}")
                except:
                    pass  # Skip attributes that can't be accessed
        
        # Print findings for debugging
        print(f"Found {len(path_attributes)} Path attributes:")
        for attr in path_attributes:
            print(f"  - {attr}")
            
        # Check the specific attributes we're trying to serialize
        print(f"model_path type: {type(stage.model_path)}, value: {stage.model_path}")
        print(f"data_path type: {type(stage.data_path)}, value: {stage.data_path}")  
        print(f"output_path type: {type(stage.output_path)}, value: {stage.output_path}")
        
        # This test should pass - it's for debugging only
        self.assertTrue(True)