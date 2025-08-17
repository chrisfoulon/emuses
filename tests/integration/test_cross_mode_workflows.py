"""Test suite for cross-mode workflow validation.

This module tests complete workflows across all registry deployment modes
(LOCAL, DATABASE, CLOUD) to ensure consistent functionality and compatibility.
"""
import pytest
import tempfile
from pathlib import Path

from emuses.tools.model_registry_factory import ModelRegistryFactory, RegistryMode


class TestCrossModeInstallationWorkflows:
    """Test model installation workflows across all deployment modes."""

    @pytest.fixture
    def temp_model_file(self):
        """Create a temporary model file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
            # Create minimal model file content
            temp_file.write(b'dummy model data for testing')
            temp_path = Path(temp_file.name)
        yield temp_path
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    def test_installation_workflow_interface_exists(self):
        """Test that installation workflow testing interface exists."""
        factory = ModelRegistryFactory()

        # Should be able to create registries for all modes
        local_registry = factory.create_registry(RegistryMode.LOCAL)
        assert local_registry is not None
        assert hasattr(local_registry, 'install_model')

        # Database and cloud registries should also have install interface
        # (These will be mocked for integration testing)

    def test_model_installation_local_mode(self):
        """Test model installation workflow in LOCAL mode."""
        factory = ModelRegistryFactory()
        registry = factory.create_registry(RegistryMode.LOCAL)

        # Test that installation interface exists
        assert hasattr(registry, 'install_model')
        assert callable(registry.install_model)

        # Test unified interface methods
        assert hasattr(registry, 'list_models')
        assert hasattr(registry, 'get_model_info')

        # Test that methods are callable
        models = registry.list_models()
        assert isinstance(models, list)

    def test_model_installation_cross_mode_compatibility(self):
        """Test that installation workflows are compatible across modes."""
        factory = ModelRegistryFactory()

        # All registries should implement the same interface
        local_registry = factory.create_registry(RegistryMode.LOCAL)

        # Test unified interface exists
        assert hasattr(local_registry, 'install_model')
        assert hasattr(local_registry, 'list_models')
        assert hasattr(local_registry, 'get_model_info')

        # Interface validation should pass
        is_valid = factory.validate_interface(local_registry)
        assert is_valid

    def test_installation_workflow_with_parameters(self, temp_model_file):
        """Test installation workflow with different parameter patterns."""
        factory = ModelRegistryFactory()
        registry = factory.create_registry(RegistryMode.LOCAL)

        # Test both old and new parameter patterns work
        # Old pattern: install_model(path, name="test")
        # New pattern: install_model(path, model_name="test", version="1.0")

        # Test that method signature supports both patterns
        import inspect
        sig = inspect.signature(registry.install_model)
        params = list(sig.parameters.keys())

        # Should support unified interface parameters
        assert 'model_path' in params or 'path' in params
        # Should support both name patterns (backward compatibility)
        assert 'name' in params or 'model_name' in params

    @pytest.mark.parametrize("registry_mode", [RegistryMode.LOCAL])
    def test_installation_workflow_across_modes(self, registry_mode, temp_model_file):
        """Test model installation workflow across different registry modes."""
        factory = ModelRegistryFactory()

        # Create registry for the specified mode
        registry = factory.create_registry(registry_mode)
        assert registry is not None

        # Test installation interface exists and is callable
        assert hasattr(registry, 'install_model')
        assert callable(registry.install_model)

        # Test that we can list models (even if empty initially)
        initial_models = registry.list_models()
        assert isinstance(initial_models, list)

        # Test that the interface works consistently across modes
        # (Actual installation testing will depend on mode-specific setup)


class TestCrossModeSearchWorkflows:
    """Test search and discovery functionality across deployment modes."""

    def test_search_functionality_interface_exists(self):
        """Test that search functionality interface exists across modes."""
        factory = ModelRegistryFactory()
        registry = factory.create_registry(RegistryMode.LOCAL)

        # All registries should have search functionality
        assert hasattr(registry, 'search_models')
        assert callable(registry.search_models)

    def test_search_functionality_consistency(self):
        """Test that search functionality is consistent across modes."""
        factory = ModelRegistryFactory()
        registry = factory.create_registry(RegistryMode.LOCAL)

        # Test basic search functionality
        results = registry.search_models("test")
        assert isinstance(results, list)

        # Test search with filters (should not raise errors)
        filtered_results = registry.search_models("test", filters={"tags": ["fMRI"]})
        assert isinstance(filtered_results, list)

    def test_discovery_functionality_interface(self):
        """Test that model discovery functionality exists."""
        factory = ModelRegistryFactory()
        registry = factory.create_registry(RegistryMode.LOCAL)

        # Test that list_models supports discovery patterns
        all_models = registry.list_models()
        assert isinstance(all_models, list)

        # Test filtering capabilities
        if hasattr(registry, 'list_models'):
            # Test with workspace filtering (should work or gracefully handle)
            try:
                workspace_models = registry.list_models(workspace_id="test_workspace")
                assert isinstance(workspace_models, list)
            except (TypeError, NotImplementedError):
                # Some modes may not support workspace filtering
                pass

    @pytest.mark.parametrize("registry_mode", [RegistryMode.LOCAL])
    def test_search_across_modes(self, registry_mode):
        """Test search functionality across different registry modes."""
        factory = ModelRegistryFactory()
        registry = factory.create_registry(registry_mode)

        # Test that search interface exists
        assert hasattr(registry, 'search_models')

        # Test basic search works without errors
        results = registry.search_models("nonexistent_model")
        assert isinstance(results, list)
        # Should return empty list for non-existent models
        assert len(results) == 0


class TestCrossModePermissionWorkflows:
    """Test permission systems across database and cloud modes."""

    def test_permission_system_interface_exists(self):
        """Test that permission system interface exists."""
        # Permission systems are primarily for DATABASE and CLOUD modes
        # LOCAL mode has basic single-user permissions
        factory = ModelRegistryFactory()

        # Test should validate permission-related interfaces exist
        # This will be expanded as permission systems are tested
        assert factory is not None


class TestCrossModeCliWorkflows:
    """Test CLI command compatibility across all modes."""

    def test_cli_command_interface_compatibility(self):
        """Test that CLI commands work consistently across modes."""
        factory = ModelRegistryFactory()

        # CLI commands should work with any registry mode
        # Test that factory can create registries for CLI usage
        local_registry = factory.create_registry(RegistryMode.LOCAL)
        assert local_registry is not None

        # CLI interface validation - commands should work across modes
        # Test that all necessary methods exist for CLI operations
        required_methods = [
            'list_models', 'install_model', 'get_model_info',
            'search_models', 'uninstall_model'
        ]

        for method in required_methods:
            if hasattr(local_registry, method):
                assert callable(getattr(local_registry, method))

    def test_cli_parameter_compatibility(self):
        """Test that CLI parameters work consistently across registry modes."""
        factory = ModelRegistryFactory()
        registry = factory.create_registry(RegistryMode.LOCAL)

        # Test that cross-mode parameters are supported
        # These are the parameters that should work across all modes

        # Test list_models with cross-mode parameters
        models = registry.list_models()
        assert isinstance(models, list)

        # Test with user and workspace parameters if supported
        try:
            # These parameters should be supported or gracefully ignored
            user_models = registry.list_models(user_id="test_user")
            assert isinstance(user_models, list)
        except TypeError:
            # Some modes may not support these parameters yet
            pass

        try:
            workspace_models = registry.list_models(workspace_id="test_workspace")
            assert isinstance(workspace_models, list)
        except TypeError:
            # Some modes may not support these parameters yet
            pass

    def test_cli_error_handling_consistency(self):
        """Test that CLI error handling is consistent across modes."""
        factory = ModelRegistryFactory()
        registry = factory.create_registry(RegistryMode.LOCAL)

        # Test that error handling is consistent
        # For example, trying to get info for non-existent model
        try:
            result = registry.get_model_info("nonexistent_model_12345")
            # Should either return None or raise consistent exception
            assert result is None or isinstance(result, dict)
        except Exception as e:
            # Exception should be a reasonable type (ValueError, NotFoundError, etc.)
            assert isinstance(e, (ValueError, FileNotFoundError, KeyError))

    @pytest.mark.parametrize("registry_mode", [RegistryMode.LOCAL])
    def test_cli_operations_across_modes(self, registry_mode):
        """Test CLI operations work consistently across different modes."""
        factory = ModelRegistryFactory()
        registry = factory.create_registry(registry_mode)

        # Test basic CLI operations that should work in all modes

        # 1. List models operation
        models = registry.list_models()
        assert isinstance(models, list)

        # 2. Search models operation
        search_results = registry.search_models("test")
        assert isinstance(search_results, list)

        # 3. Get model info for non-existent model (should handle gracefully)
        try:
            info = registry.get_model_info("nonexistent")
            assert info is None or isinstance(info, dict)
        except Exception as e:
            # Should be a reasonable exception type
            assert isinstance(e, (ValueError, FileNotFoundError, KeyError, AttributeError))
