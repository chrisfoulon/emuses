"""
Test TestClient integration for local execution in enhanced CLI.

This module tests the implementation of FastAPI TestClient for local execution
to replace direct EMUSESPipeline usage while maintaining service consistency.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Import modules to test
from emuses.cli.main import _execute_stage_locally
from emuses.cli.service_client import ServiceHTTPClient, ServiceClientError


class TestTestClientIntegration:
    """Test TestClient integration for local execution."""
    
    @pytest.mark.asyncio
    async def test_execute_locally_uses_testclient(self):
        """Test that _execute_locally uses TestClient when FastAPI service is available."""
        
        # Mock components
        mock_status_renderer = Mock()
        mock_progress_tracker = Mock()
        
        # Sample pipeline configuration
        test_config = {
            "output_folder": "test_output",
            "input_dataset": "test_input.csv",
            "scores": "test_scores.csv",
            "random_state": 42
        }
        
        # Patch TestClient to track its usage
        with patch('emuses.cli.main.TestClient') as mock_testclient_class:
            mock_testclient = Mock()
            mock_testclient_class.return_value = mock_testclient
            
            # Mock the FastAPI app
            with patch('emuses.cli.main.create_fastapi_app') as mock_create_app:
                mock_app = Mock()
                mock_create_app.return_value = mock_app
                
                # Mock TestClient response
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "job_id": "test_job_123",
                    "status": "submitted"
                }
                mock_testclient.post.return_value = mock_response
                
                # Mock job polling
                mock_status_response = Mock()
                mock_status_response.status_code = 200
                mock_status_response.json.return_value = {
                    "status": "completed",
                    "progress": 100
                }
                mock_testclient.get.return_value = mock_status_response
                
                # Execute the function
                await _execute_locally(test_config, mock_status_renderer, mock_progress_tracker)
                
                # Verify TestClient was used
                mock_testclient_class.assert_called_once()
                mock_create_app.assert_called_once()
                
                # Verify TestClient was used for job submission
                mock_testclient.post.assert_called()
                
                # Verify job polling was done via TestClient
                mock_testclient.get.assert_called()
                
    @pytest.mark.asyncio
    async def test_execute_locally_fallback_to_legacy(self):
        """Test that _execute_locally falls back to legacy pipeline when FastAPI service is not available."""
        
        # Mock components
        mock_status_renderer = Mock()
        mock_progress_tracker = Mock()
        
        # Sample pipeline configuration
        test_config = {
            "output_folder": "test_output",
            "input_dataset": "test_input.csv",
            "scores": "test_scores.csv",
            "random_state": 42
        }
        
        # Mock FastAPI app creation to fail
        with patch('emuses.cli.main.create_fastapi_app') as mock_create_app:
            mock_create_app.side_effect = ServiceClientError("FastAPI service not available: No module named 'emuses.api.main'")
            
            # Mock legacy pipeline execution
            with patch('emuses.cli.main._execute_legacy_pipeline') as mock_legacy_execute:
                mock_legacy_execute.return_value = None
                
                # Execute the function
                await _execute_locally(test_config, mock_status_renderer, mock_progress_tracker)
                
                # Verify fallback to legacy pipeline was called
                mock_legacy_execute.assert_called_once_with(test_config, mock_status_renderer, mock_progress_tracker)
                
                # Verify warning message was shown
                mock_status_renderer.render_status.assert_any_call("warning", "FastAPI service not available, falling back to direct pipeline execution...")
        
    @pytest.mark.asyncio
    async def test_execute_locally_job_submission_format(self):
        """Test that job submission uses proper service API format."""
        
        # Mock components
        mock_status_renderer = Mock()
        mock_progress_tracker = Mock()
        
        # Sample pipeline configuration
        test_config = {
            "output_folder": "test_output",
            "input_dataset": "test_input.csv",
            "command": "full"
        }
        
        with patch('emuses.cli.main.TestClient') as mock_testclient_class:
            mock_testclient = Mock()
            mock_testclient_class.return_value = mock_testclient
            
            with patch('emuses.cli.main.create_fastapi_app') as mock_create_app:
                mock_app = Mock()
                mock_create_app.return_value = mock_app
                
                # Mock successful job submission
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "job_id": "test_job_123",
                    "status": "submitted"
                }
                mock_testclient.post.return_value = mock_response
                
                # Mock job completion
                mock_status_response = Mock()
                mock_status_response.status_code = 200
                mock_status_response.json.return_value = {
                    "status": "completed",
                    "progress": 100
                }
                mock_testclient.get.return_value = mock_status_response
                
                # Execute the function
                await _execute_locally(test_config, mock_status_renderer, mock_progress_tracker)
                
                # Verify job was submitted with correct format
                mock_testclient.post.assert_called_once()
                call_args = mock_testclient.post.call_args
                
                # Check endpoint format
                endpoint = call_args[0][0]  # First positional argument
                assert endpoint.startswith('/api/'), "Should use API endpoint format"
                assert 'jobs' in endpoint, "Should use jobs endpoint"
                
                # Check request format
                kwargs = call_args[1]  # Keyword arguments
                assert 'json' in kwargs, "Should send JSON payload"
                
                job_request = kwargs['json']
                assert 'pipeline_config' in job_request, "Should include pipeline_config"
                assert 'job_name' in job_request, "Should include job_name"
                
    @pytest.mark.asyncio
    async def test_execute_locally_error_handling(self):
        """Test that TestClient errors are properly handled."""
        
        # Mock components
        mock_status_renderer = Mock()
        mock_progress_tracker = Mock()
        
        test_config = {
            "output_folder": "test_output",
            "input_dataset": "test_input.csv",
        }
        
        with patch('emuses.cli.main.TestClient') as mock_testclient_class:
            mock_testclient = Mock()
            mock_testclient_class.return_value = mock_testclient
            
            with patch('emuses.cli.main.create_fastapi_app') as mock_create_app:
                mock_app = Mock()
                mock_create_app.return_value = mock_app
                
                # Mock TestClient failure
                mock_testclient.post.side_effect = Exception("TestClient connection failed")
                
                # Execute should raise ServiceClientError
                from emuses.cli.service_client import ServiceClientError
                with pytest.raises(ServiceClientError) as exc_info:
                    await _execute_locally(test_config, mock_status_renderer, mock_progress_tracker)
                
                # Verify error message mentions TestClient
                assert "TestClient" in str(exc_info.value) or "Local execution failed" in str(exc_info.value)
                
    @pytest.mark.asyncio
    async def test_execute_locally_progress_tracking(self):
        """Test that progress tracking works with TestClient."""
        
        # Mock components
        mock_status_renderer = Mock()
        mock_progress_tracker = Mock()
        
        test_config = {
            "output_folder": "test_output",
            "input_dataset": "test_input.csv",
        }
        
        with patch('emuses.cli.main.TestClient') as mock_testclient_class:
            mock_testclient = Mock()
            mock_testclient_class.return_value = mock_testclient
            
            with patch('emuses.cli.main.create_fastapi_app') as mock_create_app:
                mock_app = Mock()
                mock_create_app.return_value = mock_app
                
                # Mock job submission
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "job_id": "test_job_123",
                    "status": "submitted"
                }
                mock_testclient.post.return_value = mock_response
                
                # Mock progressive status updates
                status_sequence = [
                    {"status": "running", "progress": 0.2, "current_stage": "Loading data"},
                    {"status": "running", "progress": 0.5, "current_stage": "Training UMAP"},
                    {"status": "running", "progress": 0.8, "current_stage": "Clustering"},
                    {"status": "completed", "progress": 1.0, "current_stage": "Finished"}
                ]
                
                mock_status_responses = []
                for status in status_sequence:
                    mock_resp = Mock()
                    mock_resp.status_code = 200
                    mock_resp.json.return_value = status
                    mock_status_responses.append(mock_resp)
                
                mock_testclient.get.side_effect = mock_status_responses
                
                # Execute the function
                await _execute_locally(test_config, mock_status_renderer, mock_progress_tracker)
                
                # Verify progress polling occurred
                assert mock_testclient.get.call_count >= 2, "Should poll for progress updates"
                
                # Verify status renderer was called for progress updates
                mock_status_renderer.render_status.assert_called()


class TestLocalServiceClient:
    """Test the LocalServiceClient wrapper class."""
    
    def test_local_service_client_creation(self):
        """Test that LocalServiceClient can be created."""
        
        # This test will fail initially - it validates that we need to implement
        # a LocalServiceClient class that wraps TestClient
        
        # Try to import LocalServiceClient
        try:
            from emuses.cli.service_client import LocalServiceClient
            
            # Create instance
            client = LocalServiceClient()
            
            # Verify it has the same interface as ServiceHTTPClient
            assert hasattr(client, 'submit_pipeline_job'), "Should have submit_pipeline_job method"
            assert hasattr(client, 'get_job_status'), "Should have get_job_status method"
            assert hasattr(client, 'check_service_health'), "Should have check_service_health method"
            
        except ImportError:
            pytest.fail("LocalServiceClient not implemented yet")
            
    def test_local_service_client_interface_compatibility(self):
        """Test that LocalServiceClient has same interface as ServiceHTTPClient."""
        
        # This test validates interface compatibility
        try:
            from emuses.cli.service_client import LocalServiceClient
            
            # Get methods from ServiceHTTPClient
            http_client_methods = [
                method for method in dir(ServiceHTTPClient) 
                if not method.startswith('_') and callable(getattr(ServiceHTTPClient, method))
            ]
            
            # Check LocalServiceClient has same methods
            local_client = LocalServiceClient()
            local_client_methods = [
                method for method in dir(local_client) 
                if not method.startswith('_') and callable(getattr(local_client, method))
            ]
            
            # Verify key methods exist
            required_methods = [
                'submit_pipeline_job', 
                'get_job_status', 
                'check_service_health'
            ]
            
            for method in required_methods:
                assert hasattr(local_client, method), f"LocalServiceClient missing method: {method}"
                
        except ImportError:
            pytest.fail("LocalServiceClient not implemented yet")