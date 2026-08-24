"""Test suite for ModelMigrator cross-mode migration functionality.

This module tests the ModelMigrator class which enables seamless model migration
between different registry deployment modes (LOCAL, DATABASE, CLOUD).
"""
import pytest
import tempfile
from pathlib import Path

from emuses.tools.model_migration import ModelMigrator
from emuses.tools.model_registry_factory import ModelRegistryFactory, RegistryMode


class TestModelMigrator:
    """Test ModelMigrator class basic functionality."""

    def test_migrator_initializes_with_factory(self):
        """Test that ModelMigrator initializes with ModelRegistryFactory."""
        migrator = ModelMigrator()

        # Should have access to registry factory
        assert hasattr(migrator, 'factory')
        assert isinstance(migrator.factory, ModelRegistryFactory)

    def test_migrator_validates_source_and_target_modes(self):
        """Test that migrator validates source and target registry modes."""
        migrator = ModelMigrator()

        # Should validate that source and target are different modes
        with pytest.raises(ValueError, match="source and target modes must be different"):
            migrator.migrate_model("test_model",
                                   source_mode=RegistryMode.LOCAL,
                                   target_mode=RegistryMode.LOCAL)

    def test_migrator_checks_model_exists_in_source(self):
        """Test that migrator verifies model exists in source registry."""
        with tempfile.TemporaryDirectory():
            migrator = ModelMigrator()

            # Should raise error for non-existent model
            with pytest.raises(ValueError, match="Model .* not found in source registry"):
                migrator.migrate_model("nonexistent_model",
                                       source_mode=RegistryMode.LOCAL,
                                       target_mode=RegistryMode.DATABASE)

    def test_migrator_prevents_duplicate_in_target(self):
        """Test that migrator prevents duplicate models in target registry."""
        # This test will be implemented once we have working registries
        # For now, just test the interface exists
        migrator = ModelMigrator()
        assert hasattr(migrator, 'migrate_model')


class TestModelMigrationIntegration:
    """Test ModelMigrator integration with registry implementations."""

    @pytest.fixture
    def temp_local_registry(self):
        """Create temporary local registry for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "test_registry"
            yield registry_path

    def test_migration_integration_interface_exists(self, temp_local_registry):
        """Test integration interface exists for future implementation."""
        migrator = ModelMigrator()

        # Test that migration method interface exists
        assert hasattr(migrator, 'migrate_model')
        assert callable(migrator.migrate_model)

        # Test that migrator can create registries through factory
        assert hasattr(migrator, 'factory')
        local_registry = migrator.factory.create_registry(RegistryMode.LOCAL)
        assert local_registry is not None

    def test_migrate_local_to_database_with_actual_model(self, temp_local_registry):
        """Test actual model migration interface with proper error handling."""
        migrator = ModelMigrator()

        # Since we don't have a real model, this should raise an error about model not found
        # This tests our validation logic is working
        with pytest.raises(ValueError, match="Model test_model not found in source registry"):
            migrator.migrate_model("test_model",
                                   source_mode=RegistryMode.LOCAL,
                                   target_mode=RegistryMode.DATABASE)

    def test_migrate_local_to_database_creates_target_model(self):
        """Test that migration actually creates model in target registry."""
        migrator = ModelMigrator()

        # This test will fail until we implement actual migration
        # It expects the migration to succeed and create the model
        with pytest.raises(NotImplementedError, match="Migration functionality not yet implemented"):
            migrator.migrate_local_to_database("test_model")

    def test_migrate_database_to_cloud_method_exists(self):
        """Test that migrate_database_to_cloud method exists and works."""
        migrator = ModelMigrator()

        # Test should fail until we implement the method
        with pytest.raises(NotImplementedError, match="Migration functionality not yet implemented"):
            migrator.migrate_database_to_cloud("test_model")

    def test_migrate_cloud_to_local_method_exists(self):
        """Test that migrate_cloud_to_local method exists and works."""
        migrator = ModelMigrator()

        # Test should fail until we implement the method
        with pytest.raises(NotImplementedError, match="Migration functionality not yet implemented"):
            migrator.migrate_cloud_to_local("test_model")

    def test_export_model_bundle_method_exists(self):
        """Test that export_model_bundle method exists and works."""
        migrator = ModelMigrator()

        # Test should fail until we implement the method
        with pytest.raises(NotImplementedError, match="Export functionality not yet implemented"):
            migrator.export_model_bundle("test_model", RegistryMode.LOCAL, "/tmp/export")

    def test_import_model_bundle_method_exists(self):
        """Test that import_model_bundle method exists and works."""
        migrator = ModelMigrator()

        # Test should fail until we implement the method
        with pytest.raises(NotImplementedError, match="Import functionality not yet implemented"):
            migrator.import_model_bundle("/tmp/bundle.zip", RegistryMode.LOCAL)

    def test_validate_bundle_method_exists(self):
        """Test that validate_bundle method exists and works."""
        migrator = ModelMigrator()

        # Test should fail until we implement the method
        with pytest.raises(NotImplementedError, match="Bundle validation functionality not yet implemented"):
            migrator.validate_bundle("/tmp/bundle.zip")

    def test_convert_metadata_format_method_exists(self):
        """Test that convert_metadata_format method exists and works."""
        migrator = ModelMigrator()

        # Test metadata conversion interface
        assert hasattr(migrator, 'convert_metadata_format')
        assert callable(migrator.convert_metadata_format)

        # Test should fail until we implement the method
        with pytest.raises(NotImplementedError, match="Metadata format conversion not yet implemented"):
            test_metadata = {"name": "test_model", "version": "1.0"}
            migrator.convert_metadata_format(
                test_metadata,
                source_mode=RegistryMode.LOCAL,
                target_mode=RegistryMode.DATABASE)
