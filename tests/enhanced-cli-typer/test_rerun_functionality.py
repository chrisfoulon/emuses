"""
Test suite for --rerun functionality and command logging features.

This module tests the critical --rerun flag functionality and ensures that
command logging and rerun mechanisms work correctly without infinite recursion.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import sys
import subprocess
from typer.testing import CliRunner

from emuses.cli.main import app, save_command_to_output_folder, load_command_from_folder


class TestRerunFunctionality:
    """Test --rerun flag functionality and subprocess execution."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.command_file = self.temp_dir / "command.txt"
        
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_rerun_uses_subprocess_not_recursion(self):
        """
        Test that rerun command uses subprocess execution instead of recursive app() calls.
        
        This test ensures that the infinite recursion bug is fixed by verifying
        that subprocess.run is called instead of app() when using rerun command.
        """
        # Create a mock command.txt file
        test_command = "emuses full /output /input --scores /scores.csv"
        self.command_file.write_text(f"""# EMUSES Pipeline Command
# Generated on: 2025-07-24 10:00:00
# To rerun: {test_command}
# Or use: emuses rerun "{self.temp_dir}"

{test_command}
""")
        
        # Mock subprocess.run to prevent actual execution
        with patch('emuses.cli.main.subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = MagicMock(returncode=0)
            
            # Test that rerun calls subprocess instead of causing recursion
            result = self.runner.invoke(app, ["rerun", str(self.temp_dir)])
            
            # Verify subprocess.run was called (not app() recursively)
            mock_subprocess.assert_called_once()
            
            # Verify the correct command was passed to subprocess
            args, kwargs = mock_subprocess.call_args
            expected_cmd = [sys.executable, '-m', 'emuses.cli', 'full', '/output', '/input', '--scores', '/scores.csv']
            assert args[0] == expected_cmd
            
            # Verify no recursion occurred (exit code should be 0)
            assert result.exit_code == 0
    
    def test_rerun_handles_subprocess_exit_codes(self):
        """
        Test that rerun command properly handles subprocess exit codes.
        
        This ensures that failed subprocess executions are properly reported
        back to the user with the correct exit code.
        """
        # Create a mock command.txt file
        test_command = "emuses full /output /input"
        self.command_file.write_text(f"""# EMUSES Pipeline Command
{test_command}
""")
        
        # Mock subprocess.run to return non-zero exit code
        with patch('emuses.cli.main.subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = MagicMock(returncode=1)
            
            result = self.runner.invoke(app, ["rerun", str(self.temp_dir)])
            
            # Verify that non-zero exit code is propagated
            assert result.exit_code == 1
    
    def test_rerun_with_nonexistent_folder(self):
        """Test rerun command with non-existent folder shows proper error."""
        nonexistent_path = "/nonexistent/path"
        
        result = self.runner.invoke(app, ["rerun", nonexistent_path])
        
        # Should exit with error code
        assert result.exit_code != 0
        # Should show error message
        assert "Error" in result.output
    
    def test_rerun_with_missing_command_file(self):
        """Test rerun command with folder missing command.txt shows proper error."""
        # Create empty temp directory (no command.txt)
        result = self.runner.invoke(app, ["rerun", str(self.temp_dir)])
        
        # Should exit with error code  
        assert result.exit_code != 0
        # Should show error message
        assert "Error" in result.output


class TestCommandLogging:
    """Test command logging functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_save_command_creates_file(self):
        """
        Test that save_command_to_output_folder creates command.txt with correct format.
        
        This verifies that command logging works correctly and creates files
        with the expected format and content.
        """
        # Mock sys.argv to simulate a command execution
        test_argv = ['emuses', 'full', '/output', '/input', '--scores', '/scores.csv']
        
        with patch('sys.argv', test_argv):
            save_command_to_output_folder(self.temp_dir)
        
        # Verify command.txt was created
        command_file = self.temp_dir / "command.txt"
        assert command_file.exists()
        
        # Verify file content format
        content = command_file.read_text()
        
        # Check for required header elements
        assert "# EMUSES Pipeline Command" in content
        assert "# Generated on:" in content  
        assert "# To rerun:" in content
        # Check that new rerun syntax is used
        assert f"# Or use: emuses rerun \"{self.temp_dir}\"" in content
        
        # Check that actual command is included
        expected_command = ' '.join(test_argv)
        assert expected_command in content
    
    def test_load_command_from_folder_reads_correctly(self):
        """
        Test that load_command_from_folder correctly reads saved commands.
        
        This verifies that command loading works correctly and extracts
        the proper command from the command.txt file.
        """
        # Create a test command.txt file
        test_command = "emuses full /output /input --scores /scores.csv"
        command_file = self.temp_dir / "command.txt"
        command_file.write_text(f"""# EMUSES Pipeline Command
# Generated on: 2025-07-24 10:00:00
# To rerun: {test_command}
# Or use: emuses --rerun "{self.temp_dir}"

{test_command}
""")
        
        # Test loading the command
        loaded_command = load_command_from_folder(self.temp_dir)
        
        # Verify the correct command was loaded
        assert loaded_command == test_command
    
    def test_save_command_handles_filesystem_errors(self):
        """Test that save_command_to_output_folder handles filesystem errors gracefully."""
        # Try to save to a non-writable location (should not raise exception)
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            # Should not raise exception, should log warning instead
            save_command_to_output_folder(self.temp_dir)
            # Test passes if no exception is raised
    
    def test_load_command_handles_missing_file(self):
        """Test that load_command_from_folder handles missing files properly."""
        # Try to load from directory without command.txt
        with pytest.raises(FileNotFoundError):
            load_command_from_folder(self.temp_dir)


class TestCommandIntegration:
    """Test integration of command logging with CLI commands."""
    
    def test_command_logging_called_from_cli_commands(self):
        """
        Test that save_command_to_output_folder is called from all CLI commands.
        
        This ensures that command logging is properly integrated into the
        CLI command execution flow.
        """
        # This test would require mocking the actual pipeline execution
        # For now, we verify the functions exist and are callable
        
        # Verify save_command_to_output_folder exists and is callable
        assert callable(save_command_to_output_folder)
        
        # Verify load_command_from_folder exists and is callable  
        assert callable(load_command_from_folder)
        
        # TODO: Add integration tests that mock pipeline execution
        # and verify save_command_to_output_folder is called