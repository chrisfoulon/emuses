"""
Tests for observability middleware integration
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from emuses.foundation_fastapi_service.app import app


class TestObservabilityMiddleware:
    """Test observability middleware functionality"""
    
    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)
    
    def test_correlation_id_generation(self):
        """Test that correlation ID is generated when not provided"""
        response = self.client.get("/api/health")
        
        # Should have correlation ID in response headers
        assert "x-correlation-id" in response.headers
        correlation_id = response.headers["x-correlation-id"]
        
        # Should be UUID format (36 characters with dashes)
        assert len(correlation_id) == 36
        assert correlation_id.count("-") == 4
    
    def test_correlation_id_passthrough(self):
        """Test that provided correlation ID is passed through"""
        test_correlation_id = "test-correlation-123"
        
        response = self.client.get(
            "/api/health",
            headers={"x-correlation-id": test_correlation_id}
        )
        
        # Should return the same correlation ID
        assert response.headers["x-correlation-id"] == test_correlation_id
    
    def test_user_id_context(self):
        """Test that user ID is properly set in context"""
        test_user_id = "test-user-456"
        test_correlation_id = "test-correlation-789"
        
        with patch('emuses.foundation_fastapi_service.app.set_request_context') as mock_set_context:
            response = self.client.get(
                "/api/health",
                headers={
                    "x-user-id": test_user_id,
                    "x-correlation-id": test_correlation_id
                }
            )
            
            # Verify context was set with both IDs
            mock_set_context.assert_called_once_with(
                request_id=test_correlation_id,
                user_id=test_user_id
            )
    
    def test_context_clearing(self):
        """Test that context is properly cleared after request"""
        with patch('emuses.foundation_fastapi_service.app.clear_context') as mock_clear_context:
            response = self.client.get("/api/health")
            
            # Verify context was cleared
            mock_clear_context.assert_called_once()
    
    def test_http_request_tracking(self):
        """Test that HTTP requests are tracked with metrics"""
        with patch('emuses.foundation_fastapi_service.app.track_http_request') as mock_track:
            response = self.client.get("/api/health")
            
            # Verify HTTP request was tracked
            mock_track.assert_called_once_with("GET", "/api/health")
    
    def test_endpoint_sanitization(self):
        """Test that dynamic endpoints are sanitized for metrics"""
        # Test job endpoint sanitization
        with patch('emuses.foundation_fastapi_service.app.track_http_request') as mock_track:
            # This would normally fail since the job doesn't exist, but middleware runs first
            try:
                response = self.client.get("/api/v1/jobs/123-456-789/status")
            except:
                pass  # We expect this to fail, we just want to test middleware
            
            # Verify endpoint was sanitized
            mock_track.assert_called_once_with("GET", "/api/v1/jobs/{id}")
    
    def test_structured_logging_integration(self):
        """Test that structured logging includes correlation info"""
        from emuses.observability.logging import get_logger
        
        # This is more of an integration test - verify logger is properly configured
        logger = get_logger(__name__)
        
        # Logger should be a structured logger
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')
        
        # Should be able to log with additional context
        logger.info("Test message", test_key="test_value")


class TestMetricsEndpoint:
    """Test metrics endpoint functionality"""
    
    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)
    
    def test_metrics_endpoint_availability(self):
        """Test that metrics endpoint is available"""
        response = self.client.get("/metrics")
        
        assert response.status_code == 200
        assert "emuses_" in response.text  # Should contain EMUSES metrics
    
    def test_metrics_content_type(self):
        """Test that metrics endpoint returns correct content type"""
        response = self.client.get("/metrics")
        
        # Prometheus metrics should be plain text
        assert "text/plain" in response.headers.get("content-type", "")