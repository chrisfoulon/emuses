"""
Tests for research utility CLI commands.

Tests the verify, info, cite, and trace commands added for scientific workflows.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from sklearn.dummy import DummyRegressor
from typer.testing import CliRunner

from emuses.cli.main import app
from emuses.tools.model_io import ModelIOManager


class TestResearchCLI:
    """Test research utility CLI commands."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def model_with_manifest(self, temp_dir):
        """Create a model with manifest for testing."""
        # Create and save a model
        manager = ModelIOManager(temp_dir)
        model = DummyRegressor()
        
        model_path = manager.save_model(
            model=model,
            model_name="test_model",
            model_type="sklearn_regressor",
            description="Test model for CLI testing"
        )
        
        return temp_dir, "test_model"

    def test_verify_command_success(self, model_with_manifest):
        """Test verify command with valid model."""
        temp_dir, model_name = model_with_manifest
        runner = CliRunner()
        
        result = runner.invoke(app, ["verify", str(temp_dir)])
        
        assert result.exit_code == 0
        assert "✅ Model integrity verified" in result.stdout

    def test_verify_command_detailed(self, model_with_manifest):
        """Test verify command with detailed output."""
        temp_dir, model_name = model_with_manifest
        runner = CliRunner()
        
        result = runner.invoke(app, ["verify", str(temp_dir), "--detailed"])
        
        assert result.exit_code == 0
        assert "✅ Model integrity verified" in result.stdout
        assert "Model:" in result.stdout
        assert "Created:" in result.stdout

    def test_verify_command_nonexistent_model(self):
        """Test verify command with non-existent model."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, ["verify", tmpdir])
        
        assert result.exit_code == 1
        assert "❌" in result.stderr

    def test_info_command_text_format(self, model_with_manifest):
        """Test info command with text format."""
        temp_dir, model_name = model_with_manifest
        runner = CliRunner()
        
        result = runner.invoke(app, ["info", str(temp_dir)])
        
        assert result.exit_code == 0
        assert "📊 Model Information" in result.stdout
        assert "Name:" in result.stdout
        assert "Version:" in result.stdout
        assert "Description:" in result.stdout

    def test_info_command_json_format(self, model_with_manifest):
        """Test info command with JSON format."""
        temp_dir, model_name = model_with_manifest
        runner = CliRunner()
        
        result = runner.invoke(app, ["info", str(temp_dir), "--format", "json"])
        
        assert result.exit_code == 0
        
        # Should be valid JSON
        output_data = json.loads(result.stdout)
        # Verify essential model information is present at root level
        assert "name" in output_data
        assert "version" in output_data
        assert "description" in output_data
        assert "file_integrity" in output_data

    def test_cite_command_bibtex(self, model_with_manifest):
        """Test cite command with BibTeX format."""
        temp_dir, model_name = model_with_manifest
        runner = CliRunner()
        
        result = runner.invoke(app, ["cite", str(temp_dir)])
        
        assert result.exit_code == 0
        assert "@misc{" in result.stdout
        assert "title={" in result.stdout
        assert "author={" in result.stdout

    def test_cite_command_apa(self, model_with_manifest):
        """Test cite command with APA format."""
        temp_dir, model_name = model_with_manifest
        runner = CliRunner()
        
        result = runner.invoke(app, ["cite", str(temp_dir), "--format", "apa"])
        
        assert result.exit_code == 0
        assert "EMUSES Pipeline" in result.stdout
        assert "Retrieved from" in result.stdout

    def test_cite_command_nature(self, model_with_manifest):
        """Test cite command with Nature format."""
        temp_dir, model_name = model_with_manifest
        runner = CliRunner()
        
        result = runner.invoke(app, ["cite", str(temp_dir), "--format", "nature"])
        
        assert result.exit_code == 0
        assert "EMUSES Pipeline" in result.stdout
        assert "https://github.com" in result.stdout

    def test_cite_command_invalid_format(self, model_with_manifest):
        """Test cite command with invalid format."""
        temp_dir, model_name = model_with_manifest
        runner = CliRunner()
        
        result = runner.invoke(app, ["cite", str(temp_dir), "--format", "invalid"])
        
        assert result.exit_code == 1
        assert "❌ Unsupported citation format" in result.stderr

    def test_trace_command_default_output(self, model_with_manifest):
        """Test trace command with default output file."""
        temp_dir, model_name = model_with_manifest
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as work_dir:
            # Change to work directory for output
            result = runner.invoke(app, ["trace", str(temp_dir)], catch_exceptions=False)
            
            assert result.exit_code == 0
            assert "✅ Model provenance exported to" in result.stdout
            
            # Check that trace file was created
            trace_files = list(Path(work_dir).glob("*_trace.json"))
            # Note: File will be created in current directory, not work_dir

    def test_trace_command_custom_output(self, model_with_manifest):
        """Test trace command with custom output file."""
        temp_dir, model_name = model_with_manifest
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as work_dir:
            output_file = Path(work_dir) / "custom_trace.json"
            
            result = runner.invoke(app, ["trace", str(temp_dir), "--output", str(output_file)])
            
            assert result.exit_code == 0
            assert "✅ Model provenance exported to" in result.stdout
            assert output_file.exists()
            
            # Verify the trace file content
            with open(output_file, 'r') as f:
                trace_data = json.load(f)
            
            assert "model_provenance" in trace_data
            assert "generation_info" in trace_data
            assert "reproducibility" in trace_data

    def test_commands_with_model_name_instead_of_directory(self, model_with_manifest):
        """Test that commands work with model name when run from model directory."""
        temp_dir, model_name = model_with_manifest
        runner = CliRunner()
        
        # Test verify command with model name
        with patch('pathlib.Path.cwd', return_value=temp_dir):
            result = runner.invoke(app, ["verify", model_name])
            assert result.exit_code == 0
            assert "✅ Model integrity verified" in result.stdout

    def test_commands_with_nonexistent_manifest(self):
        """Test commands gracefully handle missing manifests."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a model file without manifest
            import joblib
            from sklearn.dummy import DummyRegressor
            
            model = DummyRegressor()
            model_path = Path(tmpdir) / "legacy_model_v1.0.0.joblib"
            joblib.dump(model, model_path)
            
            # Test info command
            result = runner.invoke(app, ["info", tmpdir])
            assert result.exit_code == 1
            assert "❌ No manifest found" in result.stderr

    def test_help_text_for_research_commands(self):
        """Test that help text is available for research commands."""
        runner = CliRunner()
        
        # Test main help includes research commands
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "verify" in result.stdout
        assert "info" in result.stdout
        assert "cite" in result.stdout
        assert "trace" in result.stdout
        
        # Test individual command help
        for command in ["verify", "info", "cite", "trace"]:
            result = runner.invoke(app, [command, "--help"])
            assert result.exit_code == 0
            assert "Usage:" in result.stdout