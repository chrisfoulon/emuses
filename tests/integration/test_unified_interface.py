"""Integration tests for unified model registry interface.

This module tests cross-mode integration and unified interface functionality
for the ModelRegistryFactory and BaseModelRegistry interface.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from emuses.tools.model_registry_factory import ModelRegistryFactory, RegistryMode
from emuses.tools.base_model_registry import BaseModelRegistry
from emuses.tools.local_model_registry import LocalModelRegistry


class TestModelRegistryFactory:
    """Test ModelRegistryFactory for cross-mode integration."""

    def test_factory_creates_local_registry_for_local_mode(self):
        """Test factory creates LocalModelRegistry for LOCAL mode."""
        factory = ModelRegistryFactory()
        registry = factory.create_registry(RegistryMode.LOCAL)
        
        assert isinstance(registry, LocalModelRegistry)
        assert isinstance(registry, BaseModelRegistry)

    @patch('emuses.multi_user_service.deployment_config.is_service_mode_enabled')
    @patch('emuses.multi_user_service.deployment_config.detect_deployment_mode')
    def test_factory_auto_detects_local_mode(self, mock_detect, mock_service):
        """Test factory auto-detects LOCAL deployment mode."""
        from emuses.multi_user_service.deployment_config import DeploymentMode
        
        mock_service.return_value = False
        mock_detect.return_value = DeploymentMode.LOCAL
        
        factory = ModelRegistryFactory()
        registry = factory.create_registry()  # Auto-detect mode
        
        assert isinstance(registry, LocalModelRegistry)

    def test_factory_fallback_to_local_on_error(self):
        """Test factory falls back to local registry on detection errors."""
        with patch('emuses.multi_user_service.deployment_config.detect_deployment_mode',
                  side_effect=ImportError("Module not available")):
            factory = ModelRegistryFactory()
            registry = factory.create_registry()
            
            assert isinstance(registry, LocalModelRegistry)

    def test_factory_validates_registry_capabilities(self):
        """Test factory validates registry capabilities."""
        factory = ModelRegistryFactory()
        registry = factory.create_registry(RegistryMode.LOCAL)
        
        # Test capability detection
        assert factory.has_capability(registry, 'list_models')
        assert factory.has_capability(registry, 'install_model')
        assert factory.has_capability(registry, 'search_models')

    def test_factory_mode_configuration_validation(self):
        """Test factory validates mode configuration."""
        factory = ModelRegistryFactory()
        
        # Test valid mode configuration
        config = factory.get_mode_config(RegistryMode.LOCAL)
        assert config is not None
        assert config['requires_auth'] is False
        assert config['requires_database'] is False

    def test_factory_error_handling_for_unavailable_backends(self):
        """Test factory handles unavailable backend gracefully."""
        factory = ModelRegistryFactory()
        
        # Test fallback when database backend unavailable
        with patch('emuses.tools.database_model_registry.DatabaseModelRegistry',
                  side_effect=ImportError("Database backend not available")):
            registry = factory.create_registry(RegistryMode.DATABASE, 
                                             fallback=True)
            assert isinstance(registry, LocalModelRegistry)


class TestBaseModelRegistryInterface:
    """Test BaseModelRegistry interface consistency."""

    def test_local_registry_implements_base_interface(self):
        """Test LocalModelRegistry implements BaseModelRegistry interface."""
        registry = LocalModelRegistry()
        
        # Test interface methods exist
        assert hasattr(registry, 'list_models')
        assert hasattr(registry, 'install_model')
        assert hasattr(registry, 'get_model_info')
        assert hasattr(registry, 'search_models')
        assert hasattr(registry, 'remove_model')

    def test_interface_validation_detects_missing_methods(self):
        """Test interface validation detects missing methods."""
        factory = ModelRegistryFactory()
        
        # Create mock registry with missing methods
        mock_registry = MagicMock()
        delattr(mock_registry, 'list_models')
        
        assert not factory.validate_interface(mock_registry)

    def test_interface_compatibility_checking(self):
        """Test interface compatibility checking across modes."""
        factory = ModelRegistryFactory()
        local_registry = factory.create_registry(RegistryMode.LOCAL)
        
        # Test interface compatibility
        assert factory.is_compatible(local_registry, RegistryMode.LOCAL)
        assert factory.validate_interface(local_registry)