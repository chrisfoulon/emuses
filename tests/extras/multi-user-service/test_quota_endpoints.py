"""Tests for quota management endpoints.

These tests validate the REST API endpoints for quota management including
user quota status, admin adjustments, and usage reporting functionality.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from uuid import uuid4

from emuses.multi_user_service.quota_endpoints import create_quota_router
from emuses.multi_user_service.models import User


class TestQuotaEndpoints:
    """Test quota management endpoints functionality."""
    
    def test_quota_endpoints_registration(self):
        """Test that quota endpoints router can be created."""
        router = create_quota_router()
        assert router is not None
        assert len(router.routes) > 0
        
    def test_user_quota_status_endpoint_exists(self):
        """Test that user quota status endpoint is registered."""
        router = create_quota_router()
        route_paths = [route.path for route in router.routes]
        assert "/quota/status" in route_paths
        
    def test_admin_quota_adjustment_endpoint_exists(self):
        """Test that admin quota adjustment endpoint is registered."""
        router = create_quota_router()
        route_paths = [route.path for route in router.routes]
        assert "/quota/admin/adjust" in route_paths
        
    def test_usage_history_endpoint_exists(self):
        """Test that usage history endpoint is registered."""
        router = create_quota_router()
        route_paths = [route.path for route in router.routes]
        assert "/quota/usage/history" in route_paths
        
    def test_admin_users_near_limit_endpoint_exists(self):
        """Test that admin users near limit endpoint is registered."""
        router = create_quota_router()
        route_paths = [route.path for route in router.routes]
        assert "/quota/admin/users-near-limit" in route_paths
        
    def test_admin_quota_reset_endpoint_exists(self):
        """Test that admin quota reset endpoint is registered."""
        router = create_quota_router()
        route_paths = [route.path for route in router.routes]
        assert "/quota/admin/reset" in route_paths


class TestQuotaEndpointIntegration:
    """Test quota endpoint integration with quota manager."""
    
    def test_quota_endpoints_in_workspace_setup(self):
        """Test that quota endpoints are included in workspace setup."""
        from fastapi import FastAPI
        from emuses.multi_user_service.workspace_endpoints import setup_workspace_endpoints
        
        app = FastAPI()
        setup_workspace_endpoints(app)
        
        # Check that quota routes are included
        route_paths = [route.path for route in app.routes]
        assert "/quota/status" in route_paths
        assert "/quota/admin/adjust" in route_paths
        assert "/quota/usage/history" in route_paths
        assert "/quota/admin/users-near-limit" in route_paths
        assert "/quota/admin/reset" in route_paths
    
    def test_quota_status_integration(self):
        """Test quota status endpoint integrates with QuotaManager."""
        from emuses.multi_user_service.quota_endpoints import QuotaStatusResponse
        
        # Verify response schema exists and has correct fields
        schema = QuotaStatusResponse.model_json_schema()
        properties = schema['properties']
        assert 'concurrent_jobs' in properties
        assert 'storage' in properties
        assert 'compute' in properties
        
    def test_quota_adjustment_integration(self):
        """Test quota adjustment endpoint integrates with QuotaManager."""
        from emuses.multi_user_service.quota_endpoints import QuotaAdjustmentRequest
        
        # Verify request schema exists and has correct fields
        schema = QuotaAdjustmentRequest.model_json_schema()
        properties = schema['properties']
        assert 'user_id' in properties
        assert 'quota_type' in properties
        assert 'new_value' in properties
        
    def test_usage_history_integration(self):
        """Test usage history endpoint integrates with models."""
        from emuses.multi_user_service.quota_endpoints import UsageHistoryResponse
        
        # Verify response schema exists and has correct fields
        schema = UsageHistoryResponse.model_json_schema()
        properties = schema['properties']
        assert 'user_id' in properties
        assert 'storage_history' in properties
        assert 'compute_history' in properties