# tests/cli/test_research_utilities_reproduce.py

"""
Test suite for reproduce command in research utilities.

Tests reproduction guide generation functionality.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from emuses.cli.main import app
from typer.testing import CliRunner


class TestReproduceCommand(unittest.TestCase):
    """Test reproduce command functionality."""

    def setUp(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_path = Path(self.temp_dir.name) / "test_model"
        self.model_path.mkdir(exist_ok=True)
        
        # Create mock manifest
        manifest_content = {
            "model_info": {
                "name": "test_model",
                "version": "1.0.0",
                "created_at": "2025-01-15T14:30:00Z",
                "emuses_version": "2.1.0",
                "description": "Test model for reproduction"
            },
            "training_context": {
                "config_hash": "abc123def456",
                "random_seeds": {"master": 42, "umap": 12345}
            },
            "compatibility": {
                "min_emuses_version": "2.0.0",
                "python_version": "3.9+",
                "required_packages": ["umap-learn>=0.5.0", "hdbscan>=0.8.0"]
            }
        }
        
        import json
        manifest_path = self.model_path / "model_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest_content, f)

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    def test_reproduce_command_exists(self):
        """Test that reproduce command is available in CLI."""
        result = self.runner.invoke(app, ["reproduce", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Generate reproduction guide", result.stdout)

    def test_reproduce_command_requires_model_path(self):
        """Test that reproduce command requires model path argument."""
        result = self.runner.invoke(app, ["reproduce"])
        self.assertEqual(result.exit_code, 2)  # Missing required argument
        self.assertIn("Missing argument", result.stdout)

    def test_reproduce_command_generates_markdown_guide(self):
        """Test that reproduce command generates markdown reproduction guide."""
        output_path = self.temp_dir.name / Path("reproduction_guide.md")
        
        result = self.runner.invoke(app, [
            "reproduce", 
            str(self.model_path),
            "--output", str(output_path)
        ])
        
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(output_path.exists())
        
        # Verify content includes key sections
        with open(output_path, 'r') as f:
            content = f.read()
            
        self.assertIn("# Model Reproduction Guide", content)
        self.assertIn("## Environment Setup", content)
        self.assertIn("## Model Information", content)
        self.assertIn("## Reproduction Steps", content)
        self.assertIn("test_model", content)
        self.assertIn("v1.0.0", content)

    def test_reproduce_command_includes_environment_requirements(self):
        """Test that reproduction guide includes environment requirements."""
        output_path = Path(self.temp_dir.name) / "reproduction_guide.md"
        
        result = self.runner.invoke(app, [
            "reproduce",
            str(self.model_path),
            "--output", str(output_path)
        ])
        
        self.assertEqual(result.exit_code, 0)
        
        with open(output_path, 'r') as f:
            content = f.read()
            
        self.assertIn("**Python Version**: 3.9+", content)
        self.assertIn("umap-learn>=0.5.0", content)
        self.assertIn("hdbscan>=0.8.0", content)
        self.assertIn("**EMUSES Version**: 2.1.0", content)

    def test_reproduce_command_includes_random_seeds(self):
        """Test that reproduction guide includes random seeds for reproducibility."""
        output_path = Path(self.temp_dir.name) / "reproduction_guide.md"
        
        result = self.runner.invoke(app, [
            "reproduce",
            str(self.model_path),
            "--output", str(output_path)
        ])
        
        self.assertEqual(result.exit_code, 0)
        
        with open(output_path, 'r') as f:
            content = f.read()
            
        self.assertIn("Random Seeds", content)
        self.assertIn("**master**: 42", content)
        self.assertIn("**umap**: 12345", content)

    def test_reproduce_command_handles_missing_manifest(self):
        """Test that reproduce command handles missing manifest gracefully."""
        # Remove manifest
        manifest_path = self.model_path / "model_manifest.json"
        manifest_path.unlink()
        
        output_path = Path(self.temp_dir.name) / "reproduction_guide.md"
        
        result = self.runner.invoke(app, [
            "reproduce",
            str(self.model_path),
            "--output", str(output_path)
        ])
        
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("manifest", result.stdout.lower())

    def test_reproduce_command_default_output_path(self):
        """Test that reproduce command uses default output path when not specified."""
        result = self.runner.invoke(app, [
            "reproduce",
            str(self.model_path)
        ])
        
        self.assertEqual(result.exit_code, 0)
        
        # Should create reproduction_guide.md in model directory
        expected_path = self.model_path / "reproduction_guide.md"
        self.assertTrue(expected_path.exists())


if __name__ == '__main__':
    unittest.main()