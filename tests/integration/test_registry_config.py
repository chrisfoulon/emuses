"""Test suite for RegistryConfig unified configuration management.

This module tests the RegistryConfig class which provides centralized configuration
management across all EMUSES deployment modes.
"""
import pytest
import tempfile
from pathlib import Path

from emuses.tools.registry_config import RegistryConfig


class TestRegistryConfig:
    """Test RegistryConfig class basic functionality."""

    def test_config_initializes_with_default_path(self):
        """Test that RegistryConfig initializes with default configuration path."""
        config = RegistryConfig()

        # Should have access to configuration attributes
        assert hasattr(config, 'config_path')
        assert hasattr(config, 'deployment_mode')
        assert hasattr(config, 'config_data')

    def test_config_initializes_with_custom_path(self):
        """Test that RegistryConfig can be initialized with custom config path."""
        custom_path = "/tmp/custom_config.yaml"
        config = RegistryConfig(config_path=custom_path)

        assert config.config_path == custom_path

    def test_detect_deployment_mode_method_exists(self):
        """Test that deployment mode detection method exists."""
        config = RegistryConfig()

        # Should fail until we implement the method
        with pytest.raises(NotImplementedError, match="Mode detection functionality not yet implemented"):
            config._detect_deployment_mode()

    def test_get_registry_settings_method_exists(self):
        """Test that registry settings retrieval method exists."""
        config = RegistryConfig()

        # Should fail until we implement the method
        with pytest.raises(NotImplementedError, match="Settings retrieval functionality not yet implemented"):
            config.get_registry_settings()

    def test_validate_configuration_method_exists(self):
        """Test that configuration validation method exists and works."""
        config = RegistryConfig()

        # Method now works and returns a list
        issues = config.validate_configuration()
        assert isinstance(issues, list)

    def test_validate_configuration_returns_list(self):
        """Test that validate_configuration returns a list of issues."""
        config = RegistryConfig()

        # Now that method is implemented, should return a list
        issues = config.validate_configuration()
        assert isinstance(issues, list)

        # Should have issues for default empty config
        assert len(issues) > 0
        assert "Configuration data not loaded" in issues
        assert "Deployment mode not detected" in issues

    def test_validate_configuration_with_initialized_data(self):
        """Test validation with some initialized configuration data."""
        from emuses.tools.model_registry_factory import RegistryMode

        config = RegistryConfig()
        # Manually set attributes to simulate loaded config
        config.config_data = {"test": "data"}
        config.deployment_mode = RegistryMode.LOCAL

        issues = config.validate_configuration()
        assert isinstance(issues, list)

        # Should have no issues with basic config data and mode set
        assert len(issues) == 0

    def test_setup_registry_environment_method_exists(self):
        """Test that environment setup method exists."""
        config = RegistryConfig()

        # Should fail due to invalid configuration (not implemented error)
        with pytest.raises(ValueError, match="Cannot setup environment with invalid configuration"):
            config.setup_registry_environment()

    def test_setup_registry_environment_works_with_valid_config(self):
        """Test that environment setup works with valid configuration."""
        from emuses.tools.model_registry_factory import RegistryMode

        config = RegistryConfig()
        # Set up valid config to avoid validation issues
        config.config_data = {"local": {"registry_path": "/tmp/test"}}
        config.deployment_mode = RegistryMode.LOCAL

        # Should work without raising errors now that it's implemented
        config.setup_registry_environment()  # Should complete successfully

    def test_setup_registry_environment_handles_different_modes(self):
        """Test that environment setup handles different deployment modes."""
        from emuses.tools.model_registry_factory import RegistryMode

        # Test LOCAL mode
        config = RegistryConfig()
        config.config_data = {"local": {"registry_path": "/tmp/test"}}
        config.deployment_mode = RegistryMode.LOCAL
        config.setup_registry_environment()  # Should succeed

        # Test DATABASE mode
        config.deployment_mode = RegistryMode.DATABASE
        config.setup_registry_environment()  # Should succeed

        # Test CLOUD mode
        config.deployment_mode = RegistryMode.CLOUD
        config.setup_registry_environment()  # Should succeed

    def test_migrate_configuration_method_exists(self):
        """Test that configuration migration method exists."""
        from emuses.tools.model_registry_factory import RegistryMode

        config = RegistryConfig()

        # Method should exist but fail with unimplemented
        assert hasattr(config, 'migrate_configuration')
        assert callable(config.migrate_configuration)

        with pytest.raises(NotImplementedError, match="Configuration migration not yet implemented"):
            config.migrate_configuration(RegistryMode.LOCAL, RegistryMode.DATABASE)

    def test_export_configuration_method_exists(self):
        """Test that configuration export method exists."""
        config = RegistryConfig()

        # Method should exist but fail with unimplemented
        assert hasattr(config, 'export_configuration')
        assert callable(config.export_configuration)

        with pytest.raises(NotImplementedError, match="Configuration export not yet implemented"):
            config.export_configuration("/tmp/config.yaml")

    def test_import_configuration_method_exists(self):
        """Test that configuration import method exists."""
        config = RegistryConfig()

        # Method should exist but fail with unimplemented
        assert hasattr(config, 'import_configuration')
        assert callable(config.import_configuration)

        with pytest.raises(NotImplementedError, match="Configuration import not yet implemented"):
            config.import_configuration("/tmp/config.yaml")


class TestRegistryConfigIntegration:
    """Test RegistryConfig integration functionality."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary configuration directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            yield config_dir

    def test_config_integration_interface_exists(self, temp_config_dir):
        """Test integration interface exists for future implementation."""
        config = RegistryConfig()

        # Test that configuration methods interface exists
        assert hasattr(config, 'get_registry_settings')
        assert callable(config.get_registry_settings)

        # Test that validation interface exists
        assert hasattr(config, 'validate_configuration')
        assert callable(config.validate_configuration)

    def test_config_loads_from_file_path(self, temp_config_dir):
        """Test that config can be initialized with file path."""
        config_file = temp_config_dir / "registry.yaml"
        config = RegistryConfig(config_path=str(config_file))

        assert config.config_path == str(config_file)
        # Further tests will be implemented once we have file loading

    def test_config_handles_different_deployment_modes(self):
        """Test that config can handle different deployment modes."""
        config = RegistryConfig()

        # Test that config has deployment mode attribute
        assert hasattr(config, 'deployment_mode')
        # Once implemented, this will test mode-specific configuration
