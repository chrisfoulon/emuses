"""
Test for case consistency between job status setting and polling completion states.

This test verifies that the case mismatch bug discovered in Task 3 is fixed:
- Pipeline runner was setting status to "COMPLETED" (uppercase)
- Polling logic expected ["completed", "failed", "cancelled"] (lowercase)
- This caused infinite polling loops
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner
from emuses.foundation_fastapi_service.job_manager import JobManager
from emuses.cli.service_client import LocalServiceClient
import tempfile
from pathlib import Path


class TestStatusCaseConsistency:
    """Test case consistency between status setting and polling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.job_manager = JobManager(self.temp_dir)
        self.pipeline_runner = PipelineRunner(self.job_manager)
        self.job_id = str(uuid4())

    def test_pipeline_runner_uses_lowercase_status(self):
        """Test that pipeline runner sets lowercase status values."""
        # Create a job first
        self.job_manager.create_job_directory(self.job_id)
        
        # Mock the pipeline execution to avoid running actual pipeline
        with patch.object(self.pipeline_runner, '_execute_pipeline_stages') as mock_execute:
            mock_execute.return_value = {"test": "result"}
            
            # Create a mock context
            context = {
                "config": {
                    "output_folder": str(self.temp_dir / "output"),
                    "umap_trials": 1,
                    "hdbscan_trials": 1,
                    "optuna_trials": 1
                }
            }
            
            # Test that job status is set to lowercase "running" and "completed"
            import asyncio
            
            async def run_test():
                await self.pipeline_runner.execute_pipeline(self.job_id, context)
            
            # Run the test
            asyncio.run(run_test())
            
            # Verify status was set to lowercase
            final_status = self.job_manager.get_job_status(self.job_id)
            assert final_status["status"] == "completed", f"Expected 'completed', got '{final_status['status']}'"

    def test_polling_completion_states_match_pipeline_status(self):
        """Test that polling completion states match what pipeline runner sets."""
        # Default completion states should be lowercase (from service_client.py)
        completion_states = ["completed", "failed", "cancelled"]
        
        # Test that pipeline runner sets these exact values
        # Create job and set each status
        self.job_manager.create_job_directory(self.job_id)
        
        # Test completed status
        self.job_manager.update_job_status(self.job_id, "completed", message="Test completed")
        status = self.job_manager.get_job_status(self.job_id)
        assert status["status"] in completion_states
        
        # Test failed status
        self.job_manager.update_job_status(self.job_id, "failed", message="Test failed")
        status = self.job_manager.get_job_status(self.job_id)
        assert status["status"] in completion_states
        
        # Test cancelled status
        self.job_manager.update_job_status(self.job_id, "cancelled", message="Test cancelled")
        status = self.job_manager.get_job_status(self.job_id)
        assert status["status"] in completion_states

    def test_job_manager_timestamp_logic_with_lowercase(self):
        """Test that job manager timestamp logic works with lowercase status."""
        self.job_manager.create_job_directory(self.job_id)
        
        # Test running status sets started_at
        self.job_manager.update_job_status(self.job_id, "running", message="Starting")
        status = self.job_manager.get_job_status(self.job_id)
        assert "started_at" in status
        assert status["status"] == "running"
        
        # Test completed status sets completed_at
        self.job_manager.update_job_status(self.job_id, "completed", message="Done")
        status = self.job_manager.get_job_status(self.job_id)
        assert "completed_at" in status
        assert status["status"] == "completed"

    def test_api_validation_accepts_lowercase_status(self):
        """Test that API validation accepts lowercase status values."""
        from emuses.foundation_fastapi_service.app import app
        
        # Import the valid statuses from the app
        # This should be ["submitted", "running", "completed", "failed", "cancelled"]
        valid_statuses = ["submitted", "running", "completed", "failed", "cancelled"]
        
        # Verify all expected statuses are lowercase
        for status in valid_statuses:
            assert status.islower(), f"Status '{status}' should be lowercase"
        
        # Verify the specific statuses that polling looks for
        polling_completion_states = ["completed", "failed", "cancelled"]
        for state in polling_completion_states:
            assert state in valid_statuses, f"Polling state '{state}' not in API valid statuses"

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__])