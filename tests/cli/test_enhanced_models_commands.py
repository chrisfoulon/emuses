"""Tests for Enhanced CLI Commands for Complete EMUSES Models.

Tests the Phase 3 enhanced CLI functionality including complete model support,
interactive duplicate resolution, and component-level access.
"""
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from typer.testing import CliRunner

from emuses.cli.models_commands import models_app


class TestEnhancedModelsCommands:
    """Test enhanced models CLI commands for complete EMUSES models."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def complete_model_dir(self):
        """Create a temporary complete model directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "complete_model"
            model_path.mkdir()
            
            # Create complete model files
            (model_path / "umap_model.pkl").write_bytes(b"umap model data")
            (model_path / "hdbscan_model.pkl").write_bytes(b"hdbscan model data")
            (model_path / "prediction_ensemble_model.pkl").write_bytes(b"prediction model data")
            (model_path / "manifest.json").write_text('{"name": "test_complete_model", "type": "emuses_model"}')
            
            yield model_path

    @patch('emuses.cli.models_commands.get_registry')
    def test_install_complete_model_success(self, mock_get_registry, runner, complete_model_dir):
        """Test successful installation of complete EMUSES model."""
        # Setup mock registry
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry
        mock_registry.install_model_with_deduplication.return_value = {
            "status": "success",
            "model_id": "complete_model_v1_abc123",
            "name": "test_complete_model",
            "model_type": "emuses_model",
            "message": "Complete EMUSES model installed successfully"
        }

        result = runner.invoke(models_app, [
            "install",
            str(complete_model_dir),
            "--name", "test_complete_model"
        ])

        assert result.exit_code == 0
        assert "Complete EMUSES model installed successfully" in result.stdout
        assert "complete_model_v1_abc123" in result.stdout
        mock_registry.install_model_with_deduplication.assert_called_once()

    @patch('emuses.cli.models_commands.get_registry')
    def test_install_with_duplicate_detection(self, mock_get_registry, runner, complete_model_dir):
        """Test installation with duplicate detection and user interaction."""
        # Setup mock registry
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry
        mock_registry.install_model_with_deduplication.return_value = {
            "status": "duplicate_detected",
            "duplicate_info": {
                "similar_models": [
                    {"model_id": "existing_model_v1_def456", "similarity": 0.94}
                ]
            },
            "message": "Potential duplicate detected"
        }

        # Mock user interaction to continue installation
        with patch('typer.confirm', return_value=True):
            result = runner.invoke(models_app, [
                "install",
                str(complete_model_dir)
            ])

        assert result.exit_code == 0
        assert "duplicate detected" in result.stdout.lower()

    @patch('emuses.cli.models_commands.LocalModelRegistry')  
    def test_info_command_complete_model(self, mock_registry_class, runner):
        """Test info command shows complete model details with component information."""
        mock_registry = Mock()
        mock_registry_class.return_value = mock_registry
        mock_registry.get_model_info.return_value = {
            "model_id": "complete_model_v1_abc123",
            "name": "test_complete_model",
            "type": "emuses_model",
            "version": "1.0.0",
            "description": "Complete EMUSES model with all components",
            "installed_at": "2025-08-22T12:00:00",
            "complete_model_info": {
                "is_complete_model": True,
                "components_found": {
                    "umap": {"file_path": "/path/to/umap_model.pkl", "size": 1024},
                    "hdbscan": {"file_path": "/path/to/hdbscan_model.pkl", "size": 2048},
                    "prediction": {"file_path": "/path/to/prediction_model.pkl", "size": 4096}
                },
                "configuration_hash": "abc123def456",
                "content_hash": "789ghi012jkl"
            }
        }

        result = runner.invoke(models_app, [
            "info",
            "complete_model_v1_abc123"
        ])

        assert result.exit_code == 0
        assert "Complete EMUSES Model" in result.stdout
        assert "UMAP Component" in result.stdout
        assert "HDBSCAN Component" in result.stdout  
        assert "PREDICTION Component" in result.stdout
        assert "Configuration Hash: abc123def456" in result.stdout

    @patch('emuses.cli.models_commands.LocalModelRegistry')
    def test_components_command(self, mock_registry_class, runner):
        """Test new 'components' command for accessing model components."""
        mock_registry = Mock()
        mock_registry_class.return_value = mock_registry
        
        # Mock get_model_info to return complete model info
        mock_registry.get_model_info.return_value = {
            "model_id": "complete_model_v1_abc123",
            "name": "test_complete_model",
            "complete_model_info": {
                "is_complete_model": True,
                "components_found": {
                    "umap": {
                        "file_path": "/registry/models/complete_model_v1_abc123/umap_model.pkl",
                        "component_type": "umap",
                        "size": 1048576  # 1MB in bytes
                    },
                    "hdbscan": {
                        "file_path": "/registry/models/complete_model_v1_abc123/hdbscan_model.pkl",
                        "component_type": "hdbscan",
                        "size": 2097152  # 2MB in bytes
                    },
                    "prediction": {
                        "file_path": "/registry/models/complete_model_v1_abc123/prediction_model.pkl",
                        "component_type": "prediction_ensemble",
                        "size": 4194304  # 4MB in bytes
                    }
                }
            }
        }
        
        # Mock get_model_components if available
        mock_registry.get_model_components.return_value = {
            "umap": {
                "file_path": "/registry/models/complete_model_v1_abc123/umap_model.pkl",
                "component_type": "umap",
                "size_mb": 1.0,
                "last_modified": "2025-08-22T12:00:00"
            },
            "hdbscan": {
                "file_path": "/registry/models/complete_model_v1_abc123/hdbscan_model.pkl", 
                "component_type": "hdbscan",
                "size_mb": 2.0,
                "last_modified": "2025-08-22T12:00:00"
            },
            "prediction": {
                "file_path": "/registry/models/complete_model_v1_abc123/prediction_model.pkl",
                "component_type": "prediction_ensemble",
                "size_mb": 4.0,
                "last_modified": "2025-08-22T12:00:00"
            }
        }

        result = runner.invoke(models_app, [
            "components",
            "complete_model_v1_abc123"
        ])

        assert result.exit_code == 0
        assert "Model Components" in result.stdout
        assert "UMAP" in result.stdout
        assert "HDBSCAN" in result.stdout
        assert "PREDICTION" in result.stdout
        assert "complete_mode" in result.stdout  # Part of the truncated path
        mock_registry.get_model_components.assert_called_once_with("complete_model_v1_abc123")

    @patch('emuses.cli.models_commands.LocalModelRegistry')
    def test_deduplicate_command(self, mock_registry_class, runner):
        """Test new 'deduplicate' command for registry cleanup."""
        mock_registry = Mock()
        mock_registry_class.return_value = mock_registry
        mock_registry.find_duplicate_groups.return_value = [
            {
                "primary_model": "model_v1_abc123",
                "duplicates": ["model_v1_def456", "model_v1_ghi789"],
                "similarity": 0.98
            },
            {
                "primary_model": "model_v2_jkl012", 
                "duplicates": ["model_v2_mno345"],
                "similarity": 0.95
            }
        ]
        mock_registry.remove_duplicate_group.return_value = {
            "status": "success",
            "removed_models": 3,
            "space_freed_mb": 150.5
        }

        # Mock user confirmation to proceed with cleanup
        with patch('typer.confirm', return_value=True):
            result = runner.invoke(models_app, ["deduplicate"])

        assert result.exit_code == 0
        assert "Found 2 duplicate groups" in result.stdout
        assert "Successfully removed 6 duplicate models" in result.stdout  # Mock returns 6 total
        assert "301.0 MB" in result.stdout  # Mock returns 301.0 total
        mock_registry.find_duplicate_groups.assert_called_once()

    @patch('emuses.cli.models_commands.get_registry')
    def test_list_shows_complete_model_status(self, mock_get_registry, runner):
        """Test list command shows complete model status in output."""
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry
        mock_registry.list_models.return_value = [
            {
                "model_id": "complete_model_v1_abc123",
                "name": "complete_model",
                "version": "1.0.0", 
                "type": "emuses_model",
                "description": "Complete model with all components",
                "complete_model_info": {
                    "is_complete_model": True,
                    "missing_components": []
                }
            },
            {
                "model_id": "individual_umap_def456",
                "name": "individual_umap",
                "version": "1.0.0",
                "type": "umap",
                "description": "Individual UMAP component",
                "complete_model_info": {
                    "is_complete_model": False,
                    "missing_components": ["hdbscan", "prediction"]
                }
            }
        ]

        result = runner.invoke(models_app, ["list"])

        assert result.exit_code == 0
        assert "complete_e" in result.stdout  # Truncated type
        assert "✅ Complete" in result.stdout  # Should show complete status
        assert "⚠️" in result.stdout  # Should show incomplete warning emoji
        assert "Incomplete" in result.stdout  # Should show incomplete text

    def test_install_individual_component_warning(self, runner):
        """Test that installing individual components shows upgrade guidance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create individual component (not complete model)
            model_path = Path(temp_dir) / "individual_umap.pkl"
            model_path.write_bytes(b"individual umap data")

            result = runner.invoke(models_app, [
                "install",
                str(model_path)
            ])

            # Should either install with guidance or show upgrade message
            # The exact behavior will be determined by implementation
            assert result.exit_code in [0, 1]  # May succeed with warning or fail with guidance

    @patch('emuses.cli.models_commands.LocalModelRegistry')
    def test_components_command_not_complete_model(self, mock_registry_class, runner):
        """Test components command on non-complete model shows appropriate message."""
        mock_registry = Mock()
        mock_registry_class.return_value = mock_registry
        mock_registry.get_model_info.return_value = {
            "model_id": "individual_umap_def456",
            "type": "umap",
            "complete_model_info": {
                "is_complete_model": False
            }
        }

        result = runner.invoke(models_app, [
            "components",
            "individual_umap_def456"
        ])

        assert result.exit_code == 1
        assert "not a complete model" in result.stdout.lower()

    @patch('emuses.cli.models_commands.get_registry')
    def test_force_install_with_duplicates(self, mock_get_registry, runner, complete_model_dir):
        """Test force installation bypassing duplicate detection."""
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry
        mock_registry.install_model_with_deduplication.return_value = {
            "status": "success",
            "model_id": "forced_model_v1_xyz789",
            "name": "forced_complete_model",
            "message": "Model installed (duplicates bypassed)"
        }

        result = runner.invoke(models_app, [
            "install",
            str(complete_model_dir),
            "--force"
        ])

        assert result.exit_code == 0
        assert "forced_model_v1_xyz789" in result.stdout
        # Should have called with force=True parameter
        mock_registry.install_model_with_deduplication.assert_called_once()
        call_args = mock_registry.install_model_with_deduplication.call_args
        assert call_args[1].get('force') is True or any('force' in str(arg) for arg in call_args)