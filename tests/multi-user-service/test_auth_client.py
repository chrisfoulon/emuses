"""Tests for authentication in HTTP client and CLI integration.

This module tests token management, authentication headers, and CLI
integration with the multi-user authentication system.
"""

import pytest
import os
import json
import asyncio
from unittest.mock import patch, Mock, AsyncMock, MagicMock
from pathlib import Path
from datetime import datetime, timedelta

from emuses.multi_user_service.token_manager import TokenManager, TokenInfo
from emuses.cli.service_client import ServiceHTTPClient


class TestTokenManager:
    """Test token management functionality."""
    
    def test_token_manager_init(self, tmp_path):
        """Test token manager initialization."""
        token_dir = tmp_path / "emuses_test"
        manager = TokenManager(token_dir=token_dir)
        
        assert manager.token_dir == token_dir
        assert manager.token_file == token_dir / "token.json"
        assert token_dir.exists()
        
        # Check directory permissions
        stat = token_dir.stat()
        assert oct(stat.st_mode)[-3:] == "700"
    
    def test_store_and_load_token(self, tmp_path):
        """Test storing and loading authentication tokens."""
        token_dir = tmp_path / "emuses_test"
        manager = TokenManager(token_dir=token_dir)
        
        # Create test token
        expires_at = datetime.now() + timedelta(hours=1)
        token_info = TokenInfo(
            access_token="test_jwt_token",
            token_type="bearer",
            expires_at=expires_at,
            user_id="user123",
            email="test@example.com"
        )
        
        # Store token
        manager.store_token(token_info)
        
        # Verify file exists and has correct permissions
        assert manager.token_file.exists()
        stat = manager.token_file.stat()
        assert oct(stat.st_mode)[-3:] == "600"
        
        # Load token
        loaded_token = manager.load_token()
        
        assert loaded_token is not None
        assert loaded_token.access_token == "test_jwt_token"
        assert loaded_token.token_type == "bearer"
        assert loaded_token.user_id == "user123"
        assert loaded_token.email == "test@example.com"
        assert abs((loaded_token.expires_at - expires_at).total_seconds()) < 1
    
    def test_token_validation(self, tmp_path):
        """Test token validation functionality."""
        token_dir = tmp_path / "emuses_test"
        manager = TokenManager(token_dir=token_dir)
        
        # Test valid token
        valid_token = TokenInfo(
            access_token="valid_token",
            expires_at=datetime.now() + timedelta(hours=1)
        )
        manager.store_token(valid_token)
        assert manager.is_token_valid() is True
        
        # Test expired token
        expired_token = TokenInfo(
            access_token="expired_token",
            expires_at=datetime.now() - timedelta(hours=1)
        )
        manager.store_token(expired_token)
        assert manager.is_token_valid() is False
    
    def test_clear_token(self, tmp_path):
        """Test token clearing functionality."""
        token_dir = tmp_path / "emuses_test"
        manager = TokenManager(token_dir=token_dir)
        
        # Store a token
        token_info = TokenInfo(access_token="test_token")
        manager.store_token(token_info)
        assert manager.token_file.exists()
        
        # Clear token
        manager.clear_token()
        assert not manager.token_file.exists()
        assert manager.load_token() is None
    
    def test_get_auth_header(self, tmp_path):
        """Test getting authorization header."""
        token_dir = tmp_path / "emuses_test"
        manager = TokenManager(token_dir=token_dir)
        
        # No token stored
        assert manager.get_auth_header() is None
        
        # Valid token stored
        token_info = TokenInfo(
            access_token="test_jwt_token",
            token_type="bearer",
            expires_at=datetime.now() + timedelta(hours=1)
        )
        manager.store_token(token_info)
        
        auth_header = manager.get_auth_header()
        assert auth_header == "bearer test_jwt_token"
        
        # Expired token
        expired_token = TokenInfo(
            access_token="expired_token",
            expires_at=datetime.now() - timedelta(hours=1)
        )
        manager.store_token(expired_token)
        assert manager.get_auth_header() is None


class TestServiceHTTPClientAuth:
    """Test authentication in ServiceHTTPClient."""
    
    @pytest.fixture
    def mock_token_manager(self):
        """Mock token manager for testing."""
        mock = Mock()
        mock.get_auth_header.return_value = "Bearer test_token"
        return mock
    
    def test_client_auth_initialization(self):
        """Test client initialization with authentication."""
        # Without auth token
        client = ServiceHTTPClient()
        assert client.auth_token is None
        assert client.auto_token_management is True
        
        # With auth token
        client = ServiceHTTPClient(auth_token="test_token")
        assert client.auth_token == "test_token"
    
    def test_get_auth_headers_with_token(self):
        """Test getting auth headers with provided token."""
        client = ServiceHTTPClient(auth_token="test_jwt_token")
        headers = client._get_auth_headers()
        
        assert headers == {"Authorization": "Bearer test_jwt_token"}
    
    def test_get_auth_headers_with_token_manager(self):
        """Test getting auth headers with token manager."""
        with patch('emuses.multi_user_service.token_manager.TokenManager') as mock_tm_class:
            mock_tm = Mock()
            mock_tm.get_auth_header.return_value = "Bearer stored_token"
            mock_tm_class.return_value = mock_tm
            
            client = ServiceHTTPClient(auto_token_management=True)
            client._token_manager = mock_tm
            
            headers = client._get_auth_headers()
            assert headers == {"Authorization": "Bearer stored_token"}
    
    def test_set_and_clear_auth_token(self):
        """Test setting and clearing auth tokens."""
        client = ServiceHTTPClient()
        
        # Set token
        client.set_auth_token("new_token")
        assert client.auth_token == "new_token"
        
        # Clear token
        client.clear_auth_token()
        assert client.auth_token is None
    
    @pytest.mark.asyncio
    async def test_request_includes_auth_headers(self):
        """Test that requests include authentication headers."""
        with patch('emuses.cli.service_client.httpx.AsyncClient') as mock_client_class:
            mock_session = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_session.request.return_value = mock_response
            mock_client_class.return_value = mock_session
            
            client = ServiceHTTPClient(auth_token="test_token")
            
            # Mock the _apply_rate_limiting method
            client._apply_rate_limiting = AsyncMock()
            
            await client._request("GET", "/test/endpoint")
            
            # Verify request was called with auth headers
            mock_session.request.assert_called_once()
            call_args = mock_session.request.call_args
            assert call_args[1]['headers']['Authorization'] == 'Bearer test_token'


class TestCLIDeploymentModeIntegration:
    """Test CLI integration with deployment modes and authentication."""
    
    @patch('emuses.multi_user_service.deployment_config.get_deployment_config')
    @patch('emuses.multi_user_service.deployment_config.validate_deployment_config')
    def test_deployment_mode_detection(self, mock_validate, mock_get_config):
        """Test CLI deployment mode detection."""
        from emuses.multi_user_service.deployment_config import DeploymentMode, DeploymentConfig
        
        # Mock configuration
        mock_config = DeploymentConfig(
            mode=DeploymentMode.MULTI_USER,
            requires_auth=True,
            requires_database=True,
            service_url="http://localhost:8000"
        )
        mock_get_config.return_value = mock_config
        mock_validate.return_value = {"valid": True, "errors": []}
        
        # Test the import and configuration
        from emuses.cli.main import _full_async
        
        # Verify the function exists and can be called
        assert callable(_full_async)
    
    def test_cli_parameter_validation(self):
        """Test CLI parameter validation for multi-user mode."""
        from emuses.cli.main import full
        import inspect
        
        # Get function signature
        sig = inspect.signature(full)
        param_names = list(sig.parameters.keys())
        
        # Check that service_url and token parameters exist
        assert "service_url" in param_names
        assert "token" in param_names


class TestErrorHandling:
    """Test error handling in authentication flow."""
    
    def test_token_manager_import_error(self):
        """Test handling of token manager import errors."""
        with patch('emuses.multi_user_service.token_manager.TokenManager', side_effect=ImportError):
            client = ServiceHTTPClient(auto_token_management=True)
            assert client.auto_token_management is False
            assert client._token_manager is None
    
    def test_invalid_token_file(self, tmp_path):
        """Test handling of corrupted token files."""
        token_dir = tmp_path / "emuses_test"
        manager = TokenManager(token_dir=token_dir)
        
        # Create invalid JSON file
        with open(manager.token_file, 'w') as f:
            f.write("invalid json")
        
        # Should return None for invalid file
        assert manager.load_token() is None
    
    def test_jwt_decode_error(self, tmp_path):
        """Test handling of JWT decode errors."""
        token_dir = tmp_path / "emuses_test"
        manager = TokenManager(token_dir=token_dir)
        
        # Test with invalid JWT token
        payload = manager.decode_token_payload("invalid.jwt.token")
        assert payload is None