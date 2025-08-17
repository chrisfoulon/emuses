"""Test service discovery and load balancing readiness features."""

from unittest.mock import patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from emuses.tools.model_registry_health_endpoints import get_registry_health_router


class TestServiceDiscoveryReadiness:
    """Test service discovery and load balancing readiness features."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI()
        self.app.include_router(get_registry_health_router())
        self.client = TestClient(self.app)
        
    def test_health_endpoint_includes_service_discovery_metadata(self):
        """Test that /health endpoint includes service discovery metadata."""
        response = self.client.get("/api/v1/registry/health?service_discovery=true")
        
        assert response.status_code == 200
        data = response.json()
        
        # Basic health check fields
        assert "status" in data
        assert "registry_modes" in data
        assert "timestamp" in data
        
        # Service discovery specific fields
        assert "service_info" in data
        assert "capabilities" in data
        assert "version" in data
        
        # Service info should include deployment metadata
        service_info = data["service_info"]
        assert "deployment_mode" in service_info
        assert "service_name" in service_info
        assert "instance_id" in service_info
        
        # Capabilities should list available registry modes
        capabilities = data["capabilities"]
        assert "supported_modes" in capabilities
        assert "api_version" in capabilities
        
    def test_ready_endpoint_enhanced_with_load_balancer_hints(self):
        """Test /ready endpoint includes load balancer routing hints."""
        response = self.client.get("/api/v1/registry/ready")
        
        assert response.status_code in [200, 503]  # Ready or not ready
        data = response.json()
        
        # Basic readiness fields
        assert "ready" in data
        assert "dependencies" in data
        
        # Load balancer hints
        assert "load_balancer_hints" in data
        lb_hints = data["load_balancer_hints"]
        assert "capacity" in lb_hints
        assert "performance_tier" in lb_hints
        assert "traffic_weight" in lb_hints
        
    def test_service_discovery_endpoint(self):
        """Test dedicated /service-discovery endpoint."""
        response = self.client.get("/api/v1/registry/service-discovery")
        
        assert response.status_code == 200
        data = response.json()
        
        # Service registration information
        assert "service_registration" in data
        registration = data["service_registration"]
        assert "name" in registration
        assert "version" in registration
        assert "endpoints" in registration
        assert "metadata" in registration
        
        # Load balancing configuration
        assert "load_balancing" in data
        lb_config = data["load_balancing"]
        assert "health_check_interval" in lb_config
        assert "timeout_seconds" in lb_config
        assert "retry_policy" in lb_config
        
    def test_service_mesh_integration_metadata(self):
        """Test service mesh integration metadata in endpoints."""
        response = self.client.get("/api/v1/registry/service-discovery")
        
        assert response.status_code == 200
        data = response.json()
        
        # Service mesh metadata
        assert "service_mesh" in data
        mesh_info = data["service_mesh"]
        assert "annotations" in mesh_info
        assert "labels" in mesh_info
        
        # Common service mesh annotations
        annotations = mesh_info["annotations"]
        assert "prometheus.io/scrape" in annotations
        assert "prometheus.io/path" in annotations
        assert "prometheus.io/port" in annotations
        
    def test_container_orchestration_readiness(self):
        """Test container orchestration (Kubernetes) readiness."""
        response = self.client.get("/api/v1/registry/ready")
        
        data = response.json()
        
        # Kubernetes-specific readiness indicators
        assert "kubernetes" in data
        k8s_info = data["kubernetes"]
        assert "pod_ready" in k8s_info
        assert "service_account" in k8s_info
        
    def test_circuit_breaker_indicators(self):
        """Test circuit breaker status indicators."""
        response = self.client.get("/api/v1/registry/health?include_circuit_breaker=true")
        
        assert response.status_code == 200
        data = response.json()
        
        # Circuit breaker information
        assert "circuit_breaker" in data
        cb_info = data["circuit_breaker"]
        assert "state" in cb_info  # OPEN, CLOSED, HALF_OPEN
        assert "failure_count" in cb_info
        assert "success_threshold" in cb_info
        
    @patch('emuses.tools.model_registry_health.ModelRegistryHealthChecker.check_overall_health')
    def test_degraded_service_discovery_response(self, mock_health_check):
        """Test service discovery response when service is degraded."""
        # Mock degraded health status
        mock_health_check.return_value = {
            "status": "degraded",
            "registry_modes": {
                "LOCAL": {"status": "healthy"},
                "DATABASE": {"status": "unhealthy"}
            }
        }
        
        response = self.client.get("/api/v1/registry/service-discovery")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should indicate degraded capacity
        assert "load_balancing" in data
        lb_config = data["load_balancing"]
        assert "degraded_capacity" in lb_config
        assert lb_config["degraded_capacity"] is True
        
    def test_performance_metrics_for_routing(self):
        """Test performance metrics included for load balancer routing decisions."""
        response = self.client.get("/api/v1/registry/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        
        # Performance metrics for routing
        assert "performance_metrics" in data
        metrics = data["performance_metrics"]
        assert "response_time_ms" in metrics
        
        # Additional routing metrics should be available
        assert "load_balancer_metrics" in data
        lb_metrics = data["load_balancer_metrics"]
        assert "average_response_time" in lb_metrics
        assert "request_rate" in lb_metrics
        assert "error_rate" in lb_metrics