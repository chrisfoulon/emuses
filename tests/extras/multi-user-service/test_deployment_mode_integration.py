"""Integration tests for deployment mode configuration and service startup.

Tests the complete integration between deployment mode detection and 
FastAPI service endpoint registration for both solo and enterprise use cases.
"""

import os
import sys
import pytest
import importlib
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


class TestDeploymentModeIntegration:
    """Test deployment mode integration with FastAPI service startup."""
    
    def teardown_method(self):
        """Clean up after each test."""
        # Clear any modules that might have been imported
        modules_to_remove = [
            mod for mod in list(sys.modules.keys()) 
            if 'foundation_fastapi_service.app' in mod
        ]
        for mod in modules_to_remove:
            del sys.modules[mod]
    
    def test_local_mode_disables_multi_user_endpoints(self):
        """Test that local mode properly disables multi-user endpoints."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "local"}):
            # Import fresh app instance
            import sys
            if 'emuses.foundation_fastapi_service.app' in sys.modules:
                del sys.modules['emuses.foundation_fastapi_service.app']
            
            from emuses.foundation_fastapi_service.app import app
            client = TestClient(app)
            
            # Test that multi-user endpoints are not available
            response = client.get("/admin/users")
            assert response.status_code == 404  # Not found in local mode
    
    def test_multi_user_mode_with_hyphen_enables_endpoints(self):
        """Test that multi-user mode with hyphen format enables endpoints."""
        with patch.dict(os.environ, {
            "EMUSES_DEPLOYMENT_MODE": "multi-user",
            "EMUSES_JWT_SECRET": "test-secret-for-testing",
            "EMUSES_DATABASE_URL": "sqlite:///:memory:"
        }):
            # Mock both workspace and auth endpoints setup to avoid actual import
            with patch('emuses.multi_user_service.workspace_endpoints.setup_workspace_endpoints') as mock_workspace_setup, \
                 patch('emuses.multi_user_service.endpoints.setup_auth_endpoints') as mock_auth_setup:
                # Import fresh app instance
                import sys
                if 'emuses.foundation_fastapi_service.app' in sys.modules:
                    del sys.modules['emuses.foundation_fastapi_service.app']
                
                from emuses.foundation_fastapi_service.app import app
                
                # Verify that both setup functions were called
                mock_workspace_setup.assert_called_once_with(app)
                mock_auth_setup.assert_called_once_with(app)
    
    def test_multi_user_mode_with_underscore_enables_endpoints(self):
        """Test that multi-user mode with underscore format enables endpoints."""
        with patch.dict(os.environ, {
            "EMUSES_DEPLOYMENT_MODE": "multi_user",  # POSIX-compliant format
            "EMUSES_JWT_SECRET": "test-secret-for-testing",
            "EMUSES_DATABASE_URL": "sqlite:///:memory:"
        }):
            # Mock both workspace and auth endpoints setup to avoid actual import
            with patch('emuses.multi_user_service.workspace_endpoints.setup_workspace_endpoints') as mock_workspace_setup, \
                 patch('emuses.multi_user_service.endpoints.setup_auth_endpoints') as mock_auth_setup:
                # Import fresh app instance
                import sys
                if 'emuses.foundation_fastapi_service.app' in sys.modules:
                    del sys.modules['emuses.foundation_fastapi_service.app']
                
                from emuses.foundation_fastapi_service.app import app
                
                # Verify that both setup functions were called
                mock_workspace_setup.assert_called_once_with(app)
                mock_auth_setup.assert_called_once_with(app)
    
    def test_production_mode_enables_endpoints(self):
        """Test that production mode enables multi-user endpoints."""
        with patch.dict(os.environ, {
            "EMUSES_DEPLOYMENT_MODE": "production",
            "EMUSES_JWT_SECRET": "test-secret-for-testing",
            "EMUSES_DATABASE_URL": "postgresql://test:test@localhost/test"
        }):
            # Mock both workspace and auth endpoints setup to avoid actual import
            with patch('emuses.multi_user_service.workspace_endpoints.setup_workspace_endpoints') as mock_workspace_setup, \
                 patch('emuses.multi_user_service.endpoints.setup_auth_endpoints') as mock_auth_setup:
                # Import fresh app instance
                import sys
                if 'emuses.foundation_fastapi_service.app' in sys.modules:
                    del sys.modules['emuses.foundation_fastapi_service.app']
                
                from emuses.foundation_fastapi_service.app import app
                
                # Verify that both setup functions were called
                mock_workspace_setup.assert_called_once_with(app)
                mock_auth_setup.assert_called_once_with(app)
    
    def test_both_formats_case_insensitive(self):
        """Test that both underscore and hyphen formats work case-insensitively."""
        test_cases = [
            "multi_user",
            "MULTI_USER",
            "Multi_User",
            "multi-user", 
            "MULTI-USER",
            "Multi-User"
        ]
        
        for deployment_mode in test_cases:
            with patch.dict(os.environ, {
                "EMUSES_DEPLOYMENT_MODE": deployment_mode,
                "EMUSES_JWT_SECRET": "test-secret-for-testing",
                "EMUSES_DATABASE_URL": "sqlite:///:memory:"
            }):
                # Mock both workspace and auth endpoints setup
                with patch('emuses.multi_user_service.workspace_endpoints.setup_workspace_endpoints') as mock_workspace_setup, \
                     patch('emuses.multi_user_service.endpoints.setup_auth_endpoints') as mock_auth_setup:
                    # Import fresh app instance
                    import sys
                    if 'emuses.foundation_fastapi_service.app' in sys.modules:
                        del sys.modules['emuses.foundation_fastapi_service.app']
                    
                    from emuses.foundation_fastapi_service.app import app
                    
                    # Verify that both setup functions were called
                    mock_workspace_setup.assert_called_once_with(app)
                    mock_auth_setup.assert_called_once_with(app)
    
    def test_invalid_deployment_mode_falls_back_to_local(self):
        """Test that invalid deployment mode falls back to local mode."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "invalid_mode"}):
            # Mock both endpoint setup functions to ensure they're not called
            with patch('emuses.multi_user_service.workspace_endpoints.setup_workspace_endpoints') as mock_workspace_setup, \
                 patch('emuses.multi_user_service.endpoints.setup_auth_endpoints') as mock_auth_setup:
                # Import fresh app instance
                import sys
                if 'emuses.foundation_fastapi_service.app' in sys.modules:
                    del sys.modules['emuses.foundation_fastapi_service.app']
                
                from emuses.foundation_fastapi_service.app import app
                
                # Verify that neither setup function was called
                mock_workspace_setup.assert_not_called()
                mock_auth_setup.assert_not_called()


class TestDeploymentModeLogging:
    """Test deployment mode logging behavior."""
    
    def test_multi_user_mode_logs_correct_message(self):
        """Test that multi-user mode logs the correct enable message.""" 
        # Clear module first to ensure clean slate
        import sys
        if 'emuses.foundation_fastapi_service.app' in sys.modules:
            del sys.modules['emuses.foundation_fastapi_service.app']
            
        with patch.dict(os.environ, {
            "EMUSES_DEPLOYMENT_MODE": "multi_user", 
            "EMUSES_JWT_SECRET": "test-secret",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            with patch('emuses.multi_user_service.workspace_endpoints.setup_workspace_endpoints'), \
                 patch('emuses.multi_user_service.endpoints.setup_auth_endpoints'), \
                 patch('emuses.observability.get_logger') as mock_get_logger:
                
                mock_logger = mock_get_logger.return_value
                
                # Import triggers the logging during module initialization
                from emuses.foundation_fastapi_service.app import app
                
                # Check that the correct log message was called
                mock_logger.info.assert_any_call("Multi-user service endpoints enabled for multi-user mode")
    
    def test_local_mode_logs_disabled_message(self):
        """Test that local mode logs the correct disabled message."""
        # Clear module first to ensure clean slate
        import sys
        if 'emuses.foundation_fastapi_service.app' in sys.modules:
            del sys.modules['emuses.foundation_fastapi_service.app']
            
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "local"}):
            with patch('emuses.observability.get_logger') as mock_get_logger:
                mock_logger = mock_get_logger.return_value
                
                # Import triggers the logging during module initialization
                from emuses.foundation_fastapi_service.app import app
                
                # Check that the correct log message was called
                mock_logger.info.assert_any_call("Multi-user service endpoints disabled for local mode")


# Add sys import needed for module cleanup
import sys