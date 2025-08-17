# tests/cli/test_research_utilities_compare.py

"""
Test suite for compare command in research utilities.

Tests model version comparison functionality.
"""

import json
import tempfile
import unittest
from pathlib import Path

import pytest

from emuses.cli.main import app
from typer.testing import CliRunner


class TestCompareCommand(unittest.TestCase):
    """Test compare command functionality."""

    def setUp(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Create two model directories
        self.model1_path = Path(self.temp_dir.name) / "model_v1"
        self.model2_path = Path(self.temp_dir.name) / "model_v2"
        self.model1_path.mkdir(exist_ok=True)
        self.model2_path.mkdir(exist_ok=True)
        
        # Create manifests for both models
        manifest1_content = {
            "model_info": {
                "name": "test_model",
                "version": "1.0.0",
                "created_at": "2025-01-15T14:30:00Z",
                "emuses_version": "2.1.0",
                "description": "First version"
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
        
        manifest2_content = {
            "model_info": {
                "name": "test_model",
                "version": "2.0.0",
                "created_at": "2025-01-16T10:15:00Z",
                "emuses_version": "2.1.0", 
                "description": "Second version with improvements"
            },
            "training_context": {
                "config_hash": "def456ghi789",
                "random_seeds": {"master": 123, "umap": 54321}
            },
            "compatibility": {
                "min_emuses_version": "2.0.0",
                "python_version": "3.10+",
                "required_packages": ["umap-learn>=0.5.1", "hdbscan>=0.8.1"]
            }
        }
        
        # Write manifests
        with open(self.model1_path / "model_manifest.json", 'w') as f:
            json.dump(manifest1_content, f)
            
        with open(self.model2_path / "model_manifest.json", 'w') as f:
            json.dump(manifest2_content, f)

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    def test_compare_command_exists(self):
        """Test that compare command is available in CLI."""
        result = self.runner.invoke(app, ["compare", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Compare two model versions", result.stdout)

    def test_compare_command_requires_two_models(self):
        """Test that compare command requires two model path arguments."""
        result = self.runner.invoke(app, ["compare"])
        self.assertEqual(result.exit_code, 2)  # Missing required arguments
        
        result = self.runner.invoke(app, ["compare", str(self.model1_path)])
        self.assertEqual(result.exit_code, 2)  # Missing second model
        self.assertIn("Missing argument", result.stderr)

    def test_compare_command_shows_version_differences(self):
        """Test that compare command shows version differences."""
        result = self.runner.invoke(app, [
            "compare", 
            str(self.model1_path), 
            str(self.model2_path)
        ])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Model Version Comparison", result.stdout)
        self.assertIn("v1.0.0", result.stdout)
        self.assertIn("v2.0.0", result.stdout)

    def test_compare_command_shows_config_differences(self):
        """Test that compare command shows configuration differences."""
        result = self.runner.invoke(app, [
            "compare",
            str(self.model1_path),
            str(self.model2_path)
        ])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Configuration Changes", result.stdout)
        self.assertIn("abc123def456", result.stdout)  # Old config hash
        self.assertIn("def456ghi789", result.stdout)  # New config hash

    def test_compare_command_shows_dependency_changes(self):
        """Test that compare command shows dependency changes."""
        result = self.runner.invoke(app, [
            "compare",
            str(self.model1_path),
            str(self.model2_path)
        ])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Dependency Changes", result.stdout)
        self.assertIn("umap-learn>=0.5.0", result.stdout)  # Old version
        self.assertIn("umap-learn>=0.5.1", result.stdout)  # New version

    def test_compare_command_shows_random_seed_changes(self):
        """Test that compare command shows random seed changes."""
        result = self.runner.invoke(app, [
            "compare",
            str(self.model1_path),
            str(self.model2_path)
        ])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Random Seeds", result.stdout)
        self.assertIn("42 → 123", result.stdout)  # Master seed change
        self.assertIn("12345 → 54321", result.stdout)  # UMAP seed change

    def test_compare_command_handles_missing_model1(self):
        """Test that compare command handles missing first model gracefully."""
        nonexistent_path = Path(self.temp_dir.name) / "nonexistent"
        
        result = self.runner.invoke(app, [
            "compare",
            str(nonexistent_path),
            str(self.model2_path)
        ])
        
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.stderr.lower())

    def test_compare_command_handles_missing_model2(self):
        """Test that compare command handles missing second model gracefully."""
        nonexistent_path = Path(self.temp_dir.name) / "nonexistent"
        
        result = self.runner.invoke(app, [
            "compare",
            str(self.model1_path),
            str(nonexistent_path)
        ])
        
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.stderr.lower())

    def test_compare_command_handles_missing_manifest(self):
        """Test that compare command handles missing manifest gracefully."""
        # Remove manifest from model1
        (self.model1_path / "model_manifest.json").unlink()
        
        result = self.runner.invoke(app, [
            "compare",
            str(self.model1_path),
            str(self.model2_path)
        ])
        
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("manifest", result.stderr.lower())


if __name__ == '__main__':
    unittest.main()