"""Test suite for models CLI commands.

This module tests the command-line interface for model registry operations.
"""
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from emuses.cli.models_commands import models_app


class TestModelsCliCommands:
    """Test models CLI command functionality."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_model_file(self):
        """Create a temporary model file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            f.write(b"dummy model data")
            yield Path(f.name)
        # Cleanup
        Path(f.name).unlink(missing_ok=True)

    def test_status_command(self, runner):
        """Test the status command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(models_app, ["status", "--registry", temp_dir])
            assert result.exit_code == 0
            assert "Model Registry Status" in result.stdout
            assert "Model Count: 0" in result.stdout

    def test_list_empty_registry(self, runner):
        """Test listing models in empty registry."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(models_app, ["list", "--registry", temp_dir])
            assert result.exit_code == 0
            assert "No models found in registry" in result.stdout

    @patch('emuses.cli.models_commands.LocalModelRegistry')
    def test_install_command_success(self, mock_registry_class, runner, temp_model_file):
        """Test successful model installation."""
        # Setup mock
        mock_registry = Mock()
        mock_registry_class.return_value = mock_registry
        mock_registry.install_model.return_value = {
            "status": "success",
            "model_id": "test_123",
            "name": "test_model"
        }
        
        result = runner.invoke(models_app, [
            "install", 
            str(temp_model_file),
            "--name", "test_model"
        ])
        
        assert result.exit_code == 0
        assert "Successfully installed model" in result.stdout
        assert "test_model" in result.stdout
        mock_registry.install_model.assert_called_once()

    @patch('emuses.cli.models_commands.LocalModelRegistry')
    def test_install_command_failure(self, mock_registry_class, runner, temp_model_file):
        """Test failed model installation."""
        # Setup mock
        mock_registry = Mock()
        mock_registry_class.return_value = mock_registry
        mock_registry.install_model.return_value = {
            "status": "error",
            "message": "Invalid model format"
        }
        
        result = runner.invoke(models_app, [
            "install", 
            str(temp_model_file)
        ])
        
        assert result.exit_code == 1
        assert "Installation failed" in result.stdout

    @patch('emuses.cli.models_commands.LocalModelRegistry')
    def test_list_command_with_models(self, mock_registry_class, runner):
        """Test listing models with data."""
        # Setup mock
        mock_registry = Mock()
        mock_registry_class.return_value = mock_registry
        mock_registry.list_models.return_value = [
            {
                "name": "test_model",
                "version": "1.0.0",
                "type": "classification",
                "description": "Test model",
                "model_id": "test_123"
            }
        ]
        
        result = runner.invoke(models_app, ["list"])
        
        assert result.exit_code == 0
        assert "test_model" in result.stdout
        assert "1.0.0" in result.stdout

    @patch('emuses.cli.models_commands.LocalModelRegistry')
    def test_list_command_with_filters(self, mock_registry_class, runner):
        """Test listing models with filters."""
        # Setup mock
        mock_registry = Mock()
        mock_registry_class.return_value = mock_registry
        mock_registry.list_models.return_value = []
        
        result = runner.invoke(models_app, [
            "list", 
            "--type", "classification",
            "--tag", "brain"
        ])
        
        assert result.exit_code == 0
        mock_registry.list_models.assert_called_once()
        # Verify filters were passed
        call_args = mock_registry.list_models.call_args[1]
        assert call_args["filters"]["type"] == "classification"
        assert "brain" in call_args["filters"]["tags"]

    @patch('emuses.cli.models_commands.LocalModelRegistry')
    def test_info_command_success(self, mock_registry_class, runner):
        """Test getting model info."""
        # Setup mock
        mock_registry = Mock()
        mock_registry_class.return_value = mock_registry
        mock_registry.get_model_info.return_value = {
            "name": "test_model",
            "model_id": "test_123",
            "version": "1.0.0",
            "type": "classification",
            "description": "Test classification model",
            "tags": ["brain", "fMRI"],
            "installed_at": "2025-01-01T10:00:00"
        }
        
        result = runner.invoke(models_app, ["info", "test_123"])
        
        assert result.exit_code == 0
        assert "Model Information" in result.stdout
        assert "test_model" in result.stdout
        assert "classification" in result.stdout

    @patch('emuses.cli.models_commands.LocalModelRegistry')
    def test_info_command_not_found(self, mock_registry_class, runner):
        """Test getting info for non-existent model."""
        # Setup mock
        mock_registry = Mock()
        mock_registry_class.return_value = mock_registry
        mock_registry.get_model_info.return_value = None
        
        result = runner.invoke(models_app, ["info", "nonexistent"])
        
        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch('emuses.cli.models_commands.LocalModelRegistry')
    def test_search_command(self, mock_registry_class, runner):
        """Test searching models."""
        # Setup mock
        mock_registry = Mock()
        mock_registry_class.return_value = mock_registry
        mock_registry.search_models.return_value = [
            {
                "name": "brain_classifier",
                "version": "2.0.0",
                "type": "classification",
                "description": "Brain classification model",
                "model_id": "brain_123"
            }
        ]
        
        result = runner.invoke(models_app, ["search", "brain"])
        
        assert result.exit_code == 0
        assert "Search Results" in result.stdout
        assert "brain_classifier" in result.stdout
        mock_registry.search_models.assert_called_once_with("brain")

    @patch('emuses.cli.models_commands.LocalModelRegistry')
    def test_search_command_no_results(self, mock_registry_class, runner):
        """Test search with no results."""
        # Setup mock
        mock_registry = Mock()
        mock_registry_class.return_value = mock_registry
        mock_registry.search_models.return_value = []
        
        result = runner.invoke(models_app, ["search", "nonexistent"])
        
        assert result.exit_code == 0
        assert "No models found matching" in result.stdout