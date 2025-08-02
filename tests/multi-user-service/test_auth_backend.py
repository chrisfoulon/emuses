"""Test suite for multi-user service JWT authentication backend.

This module tests the JWT authentication system using FastAPI-Users
with secure token management and user management functionality.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestJWTAuthenticationBackend:
    """Test suite for JWT authentication backend and user management."""

    def test_jwt_authentication_backend_creation(self):
        """Test that JWT authentication backend can be created."""
        from emuses.multi_user_service.auth import get_auth_backend
        
        with patch.dict(os.environ, {
            'EMUSES_JWT_SECRET': 'test-secret-key',
            'EMUSES_DEPLOYMENT_MODE': 'multi-user'
        }):
            auth_backend = get_auth_backend()
            
            assert auth_backend is not None
            assert hasattr(auth_backend, 'name')
            assert auth_backend.name == 'jwt'

    def test_user_manager_creation(self):
        """Test that user manager with EMUSES-specific logic can be created."""
        from emuses.multi_user_service.auth import UserManager
        
        # Test user manager creation
        manager = UserManager(None)  # Mock user db
        
        assert hasattr(manager, 'on_after_register')
        assert hasattr(manager, 'on_after_login')
        assert callable(manager.on_after_register)
        assert callable(manager.on_after_login)

    def test_fastapi_users_instance(self):
        """Test that FastAPI-Users instance can be created."""
        from emuses.multi_user_service.auth import get_fastapi_users
        
        with patch.dict(os.environ, {
            'EMUSES_JWT_SECRET': 'test-secret-key'
        }):
            fastapi_users = get_fastapi_users()
            
            assert fastapi_users is not None
            assert hasattr(fastapi_users, 'get_auth_router')
            assert hasattr(fastapi_users, 'get_register_router')
            assert hasattr(fastapi_users, 'get_users_router')

    def test_user_dependency_functions(self):
        """Test that user dependency functions exist for FastAPI."""
        from emuses.multi_user_service.auth import (
            get_current_user,
            get_current_active_user,
            get_current_superuser
        )
        
        # These should be callable dependency functions
        assert callable(get_current_user)
        assert callable(get_current_active_user)
        assert callable(get_current_superuser)

    def test_optional_authentication_dependency(self):
        """Test optional authentication dependency for backward compatibility."""
        from emuses.multi_user_service.auth import get_current_user_optional
        
        # This should be a callable dependency that can return None
        assert callable(get_current_user_optional)

    def test_jwt_secret_validation(self):
        """Test JWT secret key validation."""
        from emuses.multi_user_service.auth import get_jwt_secret
        
        # Test that missing EMUSES_JWT_SECRET in production mode raises error
        with patch.dict(os.environ, {
            'EMUSES_DEPLOYMENT_MODE': 'production'
        }, clear=True):
            with pytest.raises(ValueError, match="EMUSES_JWT_SECRET.*required"):
                get_jwt_secret()
                
        # Test that missing EMUSES_JWT_SECRET in local mode works (uses default)
        with patch.dict(os.environ, {
            'EMUSES_DEPLOYMENT_MODE': 'local'
        }, clear=True):
            secret = get_jwt_secret()
            assert secret is not None
            assert secret == "development-secret-key-change-in-production"