"""Tests for deployment mode detection and configuration.

This module tests the deployment mode configuration system that supports
local, multi-user, and production deployment modes.
"""

import os
import pytest
from unittest.mock import patch

from emuses.multi_user_service.deployment_config import (
    DeploymentMode,
    DeploymentConfig,
    detect_deployment_mode,
    get_deployment_config,
    validate_deployment_config,
    is_service_mode_enabled,
    get_service_discovery_url,
)


class TestDeploymentModeDetection:
    """Test deployment mode detection from environment variables."""
    
    def test_detect_deployment_mode_local_default(self):
        """Test default deployment mode is local."""
        with patch.dict(os.environ, {}, clear=True):
            mode = detect_deployment_mode()
            assert mode == DeploymentMode.LOCAL
    
    def test_detect_deployment_mode_from_env(self):
        """Test deployment mode detection from environment variable."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "production"}):
            mode = detect_deployment_mode()
            assert mode == DeploymentMode.PRODUCTION
    
    def test_detect_deployment_mode_case_insensitive(self):
        """Test deployment mode detection is case insensitive."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "MULTI-USER"}):
            mode = detect_deployment_mode()
            assert mode == DeploymentMode.MULTI_USER
    
    def test_detect_deployment_mode_invalid_fallback(self):
        """Test invalid deployment mode falls back to local."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "invalid"}):
            mode = detect_deployment_mode()
            assert mode == DeploymentMode.LOCAL


class TestDeploymentConfiguration:
    """Test deployment configuration for different modes."""
    
    def test_local_mode_config(self):
        """Test local mode configuration."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "local"}):
            config = get_deployment_config()
            
            assert config.mode == DeploymentMode.LOCAL
            assert config.requires_auth is False
            assert config.requires_database is False
            assert config.service_url == "http://localhost:8000"
            assert config.health_check_enabled is False
    
    def test_multi_user_mode_config(self):
        """Test multi-user mode configuration."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "multi-user"}):
            config = get_deployment_config()
            
            assert config.mode == DeploymentMode.MULTI_USER
            assert config.requires_auth is True
            assert config.requires_database is True
            assert config.service_url == "http://localhost:8000"  # Default
            assert config.health_check_enabled is True
    
    def test_multi_user_mode_config_custom_url(self):
        """Test multi-user mode with custom service URL."""
        with patch.dict(os.environ, {
            "EMUSES_DEPLOYMENT_MODE": "multi-user",
            "EMUSES_SERVICE_URL": "http://emuses-dev.example.com"
        }):
            config = get_deployment_config()
            
            assert config.service_url == "http://emuses-dev.example.com"
    
    def test_production_mode_config(self):
        """Test production mode configuration."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "production"}):
            config = get_deployment_config()
            
            assert config.mode == DeploymentMode.PRODUCTION
            assert config.requires_auth is True
            assert config.requires_database is True
            assert config.service_url == "https://emuses.example.com"  # Default
            assert config.health_check_enabled is True


class TestConfigurationValidation:
    """Test deployment configuration validation."""
    
    def test_validate_local_config_no_requirements(self):
        """Test local config validation with no requirements."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "local"}):
            config = get_deployment_config()
            result = validate_deployment_config(config)
            
            assert result["valid"] is True
            assert len(result["errors"]) == 0
    
    def test_validate_multi_user_config_missing_jwt_secret(self):
        """Test multi-user config validation missing JWT secret."""
        with patch.dict(os.environ, {
            "EMUSES_DEPLOYMENT_MODE": "multi-user"
        }, clear=True):
            config = get_deployment_config()
            result = validate_deployment_config(config)
            
            assert result["valid"] is False
            assert "JWT_SECRET environment variable is required for authentication" in result["errors"]
            assert "DATABASE_URL environment variable is required" in result["errors"]
    
    def test_validate_multi_user_config_valid(self):
        """Test multi-user config validation with all requirements."""
        with patch.dict(os.environ, {
            "EMUSES_DEPLOYMENT_MODE": "multi-user",
            "JWT_SECRET": "test-secret",
            "DATABASE_URL": "postgresql://user:pass@localhost/emuses"
        }):
            config = get_deployment_config()
            result = validate_deployment_config(config)
            
            assert result["valid"] is True
            assert len(result["errors"]) == 0
    
    def test_validate_config_invalid_database_url(self):
        """Test config validation with invalid database URL."""
        with patch.dict(os.environ, {
            "EMUSES_DEPLOYMENT_MODE": "production",
            "JWT_SECRET": "test-secret",
            "DATABASE_URL": "invalid-url"
        }):
            config = get_deployment_config()
            result = validate_deployment_config(config)
            
            assert result["valid"] is False
            assert any("DATABASE_URL must be a valid URL" in error for error in result["errors"])


class TestServiceModeDetection:
    """Test service mode detection and discovery."""
    
    def test_is_service_mode_enabled_local(self):
        """Test service mode is disabled in local mode."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "local"}):
            assert is_service_mode_enabled() is False
    
    def test_is_service_mode_enabled_multi_user(self):
        """Test service mode is enabled in multi-user mode."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "multi-user"}):
            assert is_service_mode_enabled() is True
    
    def test_is_service_mode_enabled_production(self):
        """Test service mode is enabled in production mode."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "production"}):
            assert is_service_mode_enabled() is True
    
    def test_get_service_discovery_url_local(self):
        """Test service discovery URL is None in local mode."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "local"}):
            url = get_service_discovery_url()
            assert url is None
    
    def test_get_service_discovery_url_multi_user(self):
        """Test service discovery URL in multi-user mode."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "multi-user"}):
            url = get_service_discovery_url()
            assert url == "http://localhost:8000"
    
    def test_get_service_discovery_url_production(self):
        """Test service discovery URL in production mode."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "production"}):
            url = get_service_discovery_url()
            assert url == "https://emuses.example.com"


class TestDeploymentModeEnum:
    """Test deployment mode enum functionality."""
    
    def test_deployment_mode_values(self):
        """Test deployment mode enum values."""
        assert DeploymentMode.LOCAL.value == "local"
        assert DeploymentMode.MULTI_USER.value == "multi-user"
        assert DeploymentMode.PRODUCTION.value == "production"
    
    def test_deployment_mode_from_string(self):
        """Test creating deployment mode from string."""
        assert DeploymentMode("local") == DeploymentMode.LOCAL
        assert DeploymentMode("multi-user") == DeploymentMode.MULTI_USER
        assert DeploymentMode("production") == DeploymentMode.PRODUCTION
    
    def test_deployment_mode_invalid_string(self):
        """Test invalid deployment mode string raises ValueError."""
        with pytest.raises(ValueError):
            DeploymentMode("invalid")


class TestConfigurationDataclass:
    """Test deployment configuration dataclass."""
    
    def test_deployment_config_creation(self):
        """Test deployment config creation."""
        config = DeploymentConfig(
            mode=DeploymentMode.LOCAL,
            requires_auth=False,
            requires_database=False,
        )
        
        assert config.mode == DeploymentMode.LOCAL
        assert config.requires_auth is False
        assert config.requires_database is False
        assert config.service_url is None
        assert config.health_check_enabled is True  # Default value
    
    def test_deployment_config_with_all_params(self):
        """Test deployment config with all parameters."""
        config = DeploymentConfig(
            mode=DeploymentMode.PRODUCTION,
            requires_auth=True,
            requires_database=True,
            service_url="https://api.example.com",
            health_check_enabled=False,
        )
        
        assert config.mode == DeploymentMode.PRODUCTION
        assert config.requires_auth is True
        assert config.requires_database is True
        assert config.service_url == "https://api.example.com"
        assert config.health_check_enabled is False