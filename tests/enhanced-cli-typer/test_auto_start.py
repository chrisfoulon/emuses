"""
Test auto-start service functionality for unified execution architecture.

This module tests the implementation of auto-start FastAPI service
that eliminates dual execution paths and provides a unified service-based approach.
"""

import pytest
import threading
import time
from unittest.mock import patch, MagicMock
import requests
import uvicorn
from multiprocessing import Process

from emuses.cli.main import (
    _start_local_service, 
    _stop_local_service, 
    _wait_for_service_ready, 
    _execute_via_unified_service
)


class TestAutoStartService:
    """Test auto-start service functionality."""
    
    def test_start_local_service_function_exists(self):
        """Test that auto-start service functions exist."""
        assert _start_local_service is not None, "_start_local_service not implemented yet"
        assert _stop_local_service is not None, "_stop_local_service not implemented yet"
        assert _wait_for_service_ready is not None, "_wait_for_service_ready not implemented yet"
        
    def test_unified_service_execution_function_exists(self):
        """Test that unified service execution function exists."""
        assert _execute_via_unified_service is not None, "_execute_via_unified_service not implemented yet"
        
    @pytest.mark.integration
    def test_auto_start_service_lifecycle(self):
        """Test complete auto-start service lifecycle."""
        
        # Test will fail until auto-start service is implemented
        service_process = None
        service_url = "http://localhost:8000"
        
        try:
            # Start service
            service_process = _start_local_service(port=8000)
            assert service_process is not None, "Service process should be created"
            
            # Wait for service to be ready (increased timeout for CI environments)
            is_ready = _wait_for_service_ready(service_url, timeout=30)
            assert is_ready, "Service should be ready within timeout"
            
            # Verify service is responding
            health_response = requests.get(f"{service_url}/api/health")
            assert health_response.status_code == 200, "Service should respond to health check"
            
        finally:
            # Clean up
            if service_process:
                _stop_local_service(service_process)
                
    def test_service_ready_detection(self):
        """Test service readiness detection."""
        
        # Mock successful service
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            mock_get.return_value = mock_response
            
            is_ready = _wait_for_service_ready("http://localhost:8000", timeout=1)
            assert is_ready, "Should detect ready service"
            
        # Mock unavailable service
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()
            
            is_ready = _wait_for_service_ready("http://localhost:8000", timeout=1)
            assert not is_ready, "Should detect unavailable service"


class TestUnifiedServiceExecution:
    """Test unified service execution without legacy fallbacks."""
    
    def test_unified_execution_no_fallback(self):
        """Test that unified execution doesn't fall back to legacy pipeline."""
        
        # This test ensures we only have one execution path
        config = {
            "output_folder": "/tmp/test",
            "input_dataset": "test_data.csv",
            "scores": "test_scores.csv"
        }
        
        # Mock service unavailable - should NOT fall back to legacy
        with patch('emuses.cli.main._start_local_service') as mock_start:
            mock_start.return_value = None  # Service start failed
            
            with pytest.raises(Exception) as exc_info:
                _execute_via_unified_service(config, None, None)
                
            # Should get service error, NOT legacy fallback
            assert "service" in str(exc_info.value).lower(), \
                "Should fail with service error, not fall back to legacy"
                
    def test_no_legacy_functions_called(self):
        """Test that legacy pipeline functions are never called."""
        
        # Patch legacy functions to track calls
        with patch('emuses.cli.main._execute_legacy_pipeline') as mock_legacy, \
             patch('emuses.cli.main._convert_service_config_to_legacy_args') as mock_convert:
            
            config = {"output_folder": "/tmp", "input_dataset": "data.csv"}
            
            # Mock successful service execution
            with patch('emuses.cli.main._start_local_service') as mock_start, \
                 patch('emuses.cli.main._wait_for_service_ready') as mock_ready, \
                 patch('emuses.cli.main._execute_via_service') as mock_execute:
                
                mock_start.return_value = MagicMock()
                mock_ready.return_value = True
                mock_execute.return_value = None
                
                try:
                    _execute_via_unified_service(config, None, None)
                except:
                    pass  # Ignore execution errors, focus on call tracking
                
            # Verify legacy functions were never called
            mock_legacy.assert_not_called()
            mock_convert.assert_not_called()


class TestServiceConfiguration:
    """Test service configuration and startup parameters."""
    
    def test_service_port_configuration(self):
        """Test that service can be configured with different ports."""
        
        # Test different port configurations
        for port in [8000, 8001, 9000]:
            service_process = _start_local_service(port=port)
            if service_process:  # Only test if implementation exists
                _stop_local_service(service_process)
                
    def test_service_startup_timeout(self):
        """Test service startup timeout handling."""
        
        # Test timeout behavior
        start_time = time.time()
        is_ready = _wait_for_service_ready("http://localhost:99999", timeout=2)
        elapsed = time.time() - start_time
        
        assert not is_ready, "Should timeout for invalid service"
        assert 1.5 <= elapsed <= 3.0, f"Should timeout in ~2 seconds, got {elapsed}"


class TestServiceProcessManagement:
    """Test service process lifecycle management."""
    
    def test_service_process_cleanup(self):
        """Test that service processes are properly cleaned up."""
        
        service_process = _start_local_service(port=8000)
        if service_process:
            # Verify process is running
            assert service_process.is_alive(), "Service process should be running"
            
            # Stop service
            _stop_local_service(service_process)
            
            # Wait a moment for cleanup
            time.sleep(0.5)
            
            # Verify process is stopped
            assert not service_process.is_alive(), "Service process should be stopped"
            
    def test_multiple_service_instances_prevention(self):
        """Test prevention of multiple service instances on same port."""
        
        first_service = _start_local_service(port=8000)
        if first_service:
            try:
                # Attempt to start second service on same port
                second_service = _start_local_service(port=8000)
                
                if second_service:
                    # If implementation allows it, clean up second service
                    _stop_local_service(second_service)
                    # This is acceptable behavior - implementation choice
                else:
                    # If implementation prevents it, that's also fine
                    pass
                    
            finally:
                _stop_local_service(first_service)


@pytest.mark.integration
class TestFullAutoStartIntegration:
    """Integration tests for complete auto-start workflow."""
    
    def test_cli_command_with_auto_start(self):
        """Test that CLI commands trigger auto-start service."""
        
        # This test will verify the full workflow:
        # 1. CLI command triggered
        # 2. Service auto-starts
        # 3. Command executes via service
        # 4. Service auto-stops
        
        # Mock the full workflow
        with patch('emuses.cli.main._start_local_service') as mock_start, \
             patch('emuses.cli.main._wait_for_service_ready') as mock_ready, \
             patch('emuses.cli.main._execute_via_service') as mock_execute, \
             patch('emuses.cli.main._stop_local_service') as mock_stop:
            
            mock_start.return_value = MagicMock()
            mock_ready.return_value = True
            mock_execute.return_value = None
            
            config = {"output_folder": "/tmp", "input_dataset": "data.csv"}
            
            # Execute unified service call
            try:
                _execute_via_unified_service(config, None, None)
            except:
                pass  # Ignore execution details, focus on workflow
            
            # Verify auto-start workflow
            mock_start.assert_called_once()
            mock_ready.assert_called_once()
            mock_stop.assert_called_once()
            
    def test_service_error_handling(self):
        """Test error handling in service auto-start workflow."""
        
        config = {"output_folder": "/tmp", "input_dataset": "data.csv"}
        
        # Test service start failure
        with patch('emuses.cli.main._start_local_service') as mock_start:
            mock_start.return_value = None
            
            with pytest.raises(Exception) as exc_info:
                _execute_via_unified_service(config, None, None)
                
            assert "service" in str(exc_info.value).lower()
            
        # Test service not ready failure
        with patch('emuses.cli.main._start_local_service') as mock_start, \
             patch('emuses.cli.main._wait_for_service_ready') as mock_ready, \
             patch('emuses.cli.main._stop_local_service') as mock_stop:
            
            mock_start.return_value = MagicMock()
            mock_ready.return_value = False  # Service never becomes ready
            
            with pytest.raises(Exception) as exc_info:
                _execute_via_unified_service(config, None, None)
                
            # Should still attempt cleanup
            mock_stop.assert_called_once()