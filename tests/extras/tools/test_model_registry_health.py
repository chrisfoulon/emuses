"""Test model registry health check endpoints."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from emuses.api.main import create_app


class TestModelRegistryHealthChecks:
    """Test health check endpoints for model registry."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = create_app()
        self.client = TestClient(self.app)
    
    def test_registry_health_check_endpoint_exists(self):
        """Test that registry health check endpoint exists."""
        response = self.client.get("/api/v1/registry/health")
        
        # Should not return 404 - endpoint should exist
        assert response.status_code != 404, "Registry health check endpoint should exist"
        
        # Should return valid health status
        assert response.status_code == 200
        
        health_data = response.json()
        assert "status" in health_data
        assert "registry_modes" in health_data
        assert "timestamp" in health_data
    
    def test_registry_health_check_local_mode(self):
        """Test health check for LOCAL registry mode."""
        response = self.client.get("/api/v1/registry/health")
        assert response.status_code == 200
        
        health_data = response.json()
        assert health_data["status"] in ["healthy", "degraded", "unhealthy"]
        
        # Should include LOCAL mode status
        registry_modes = health_data["registry_modes"]
        assert "LOCAL" in registry_modes
        assert registry_modes["LOCAL"]["status"] in ["healthy", "degraded", "unhealthy"]
        assert "storage_accessible" in registry_modes["LOCAL"]
    
    @patch('emuses.multi_user_service.database.get_db')
    def test_registry_health_check_database_mode(self, mock_get_db):
        """Test health check for DATABASE registry mode."""
        # Mock successful database connection
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])
        mock_session.execute.return_value.scalar.return_value = 1
        
        response = self.client.get("/api/v1/registry/health")
        assert response.status_code == 200
        
        health_data = response.json()
        
        # Should include DATABASE mode status if available
        registry_modes = health_data["registry_modes"]
        if "DATABASE" in registry_modes:
            assert registry_modes["DATABASE"]["status"] in ["healthy", "degraded", "unhealthy"]
            assert "database_connection" in registry_modes["DATABASE"]
    
    def test_registry_health_check_detailed_endpoint(self):
        """Test detailed health check endpoint."""
        response = self.client.get("/api/v1/registry/health/detailed")
        assert response.status_code == 200
        
        health_data = response.json()
        assert "overall_status" in health_data
        assert "registry_modes" in health_data
        assert "system_info" in health_data
        assert "performance_metrics" in health_data
        
        # Check system info includes relevant details
        system_info = health_data["system_info"]
        assert "version" in system_info
        assert "uptime" in system_info
        
        # Check performance metrics
        performance = health_data["performance_metrics"]
        assert "response_time_ms" in performance
    
    def test_registry_readiness_check_endpoint(self):
        """Test readiness check endpoint for service discovery."""
        response = self.client.get("/api/v1/registry/ready")
        assert response.status_code in [200, 503]  # Ready or not ready
        
        readiness_data = response.json()
        assert "ready" in readiness_data
        assert isinstance(readiness_data["ready"], bool)
        assert "dependencies" in readiness_data
        
        # Dependencies should include registry modes
        dependencies = readiness_data["dependencies"]
        assert isinstance(dependencies, dict)
    
    def test_registry_liveness_check_endpoint(self):
        """Test liveness check endpoint for load balancing."""
        response = self.client.get("/api/v1/registry/live")
        assert response.status_code == 200
        
        liveness_data = response.json()
        assert "alive" in liveness_data
        assert liveness_data["alive"] is True
        assert "timestamp" in liveness_data
    
    @patch('emuses.multi_user_service.database.get_db')
    def test_registry_health_check_database_failure(self, mock_get_db):
        """Test health check when database is unavailable."""
        # Mock database connection failure
        mock_get_db.side_effect = Exception("Database connection failed")
        
        response = self.client.get("/api/v1/registry/health")
        # Should still return 200 but with degraded status
        assert response.status_code == 200
        
        health_data = response.json()
        # Overall status should be degraded due to database failure
        assert health_data["status"] in ["degraded", "unhealthy"]
        
        # DATABASE mode should show unhealthy status
        if "DATABASE" in health_data["registry_modes"]:
            assert health_data["registry_modes"]["DATABASE"]["status"] == "unhealthy"
    
    def test_registry_health_check_with_storage_issues(self, tmp_path):
        """Test health check when storage has issues."""
        # This would be tested with actual storage permission issues
        # For now, verify endpoint handles storage checks
        response = self.client.get("/api/v1/registry/health")
        assert response.status_code == 200
        
        health_data = response.json()
        local_status = health_data["registry_modes"]["LOCAL"]
        
        # Should include storage accessibility check
        assert "storage_accessible" in local_status
        assert isinstance(local_status["storage_accessible"], bool)
    
    def test_registry_health_check_response_format(self):
        """Test health check response has correct format."""
        response = self.client.get("/api/v1/registry/health")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        health_data = response.json()
        
        # Validate response structure
        required_fields = ["status", "registry_modes", "timestamp"]
        for field in required_fields:
            assert field in health_data, f"Missing required field: {field}"
        
        # Validate status values
        valid_statuses = ["healthy", "degraded", "unhealthy"]
        assert health_data["status"] in valid_statuses
        
        # Validate timestamp format
        import datetime
        timestamp = health_data["timestamp"]
        assert timestamp.endswith("Z"), "Timestamp should be in UTC format"
        
        # Should be parseable as ISO datetime
        datetime.datetime.fromisoformat(timestamp.rstrip("Z"))