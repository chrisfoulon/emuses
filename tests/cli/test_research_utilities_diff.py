# tests/cli/test_research_utilities_diff.py

"""
Test suite for diff command in research utilities.

Tests file change detection functionality.
"""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from emuses.cli.main import app
from typer.testing import CliRunner


class TestDiffCommand(unittest.TestCase):
    """Test diff command functionality."""

    def setUp(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_path = Path(self.temp_dir.name) / "test_model"
        self.model_path.mkdir(exist_ok=True)
        
        # Create test files
        self.test_file1 = self.model_path / "umap_model.pkl"
        self.test_file2 = self.model_path / "hdbscan_model.pkl"
        self.test_file1.write_text("test content 1")
        self.test_file2.write_text("test content 2")
        
        # Create manifest with file checksums
        manifest_content = {
            "model_info": {
                "name": "test_model",
                "version": "1.0.0",
                "created_at": "2025-01-15T14:30:00Z"
            },
            "file_integrity": {
                "umap_model.pkl": {
                    "size": len("test content 1"),
                    "sha256": hashlib.sha256("test content 1".encode()).hexdigest(),
                    "modified": "2025-01-15T14:25:00Z"
                },
                "hdbscan_model.pkl": {
                    "size": len("test content 2"),
                    "sha256": hashlib.sha256("test content 2".encode()).hexdigest(),
                    "modified": "2025-01-15T14:26:00Z"
                }
            }
        }
        
        manifest_path = self.model_path / "model_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest_content, f)

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    def test_diff_command_exists(self):
        """Test that diff command is available in CLI."""
        result = self.runner.invoke(app, ["diff", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Check for modifications", result.stdout)

    def test_diff_command_requires_model_path(self):
        """Test that diff command requires model path argument."""
        result = self.runner.invoke(app, ["diff"])
        self.assertEqual(result.exit_code, 2)  # Missing required argument
        self.assertIn("Missing argument", result.stdout)

    def test_diff_command_detects_no_changes(self):
        """Test that diff command detects no changes when files are unchanged."""
        result = self.runner.invoke(app, ["diff", str(self.model_path)])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("✅", result.stdout)  # Success indicator
        self.assertIn("No changes detected", result.stdout)

    def test_diff_command_detects_modified_file(self):
        """Test that diff command detects when a file is modified."""
        # Modify one of the files
        self.test_file1.write_text("modified content")
        
        result = self.runner.invoke(app, ["diff", str(self.model_path)])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("📝", result.stdout)  # Change indicator
        self.assertIn("umap_model.pkl", result.stdout)
        self.assertIn("MODIFIED", result.stdout)

    def test_diff_command_detects_added_file(self):
        """Test that diff command detects when a file is added."""
        # Add a new file
        new_file = self.model_path / "new_file.pkl"
        new_file.write_text("new content")
        
        result = self.runner.invoke(app, ["diff", str(self.model_path)])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("📝", result.stdout)  # Change indicator
        self.assertIn("new_file.pkl", result.stdout)
        self.assertIn("ADDED", result.stdout)

    def test_diff_command_detects_deleted_file(self):
        """Test that diff command detects when a file is deleted."""
        # Delete one of the files
        self.test_file1.unlink()
        
        result = self.runner.invoke(app, ["diff", str(self.model_path)])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("📝", result.stdout)  # Change indicator
        self.assertIn("umap_model.pkl", result.stdout)
        self.assertIn("DELETED", result.stdout)

    def test_diff_command_handles_missing_manifest(self):
        """Test that diff command handles missing manifest gracefully."""
        # Remove manifest
        manifest_path = self.model_path / "model_manifest.json"
        manifest_path.unlink()
        
        result = self.runner.invoke(app, ["diff", str(self.model_path)])
        
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("manifest", result.stdout.lower())

    def test_diff_command_with_detailed_output(self):
        """Test that diff command provides detailed output when requested."""
        # Modify one file
        self.test_file1.write_text("modified content")
        
        result = self.runner.invoke(app, ["diff", str(self.model_path), "--detailed"])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Expected size", result.stdout)
        self.assertIn("SHA256", result.stdout)
        self.assertIn("umap_model.pkl", result.stdout)


if __name__ == '__main__':
    unittest.main()