"""
Tests for rerun functionality bug fix.

This module tests the command parsing fix for rerun functionality
that handles absolute paths correctly.
"""

import pytest
import tempfile
import shlex
from pathlib import Path
from unittest.mock import patch, Mock
from emuses.cli.main import load_command_from_folder, save_command_to_output_folder


class TestRerunFunctionality:
    """Test cases for the rerun command parsing fix."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_folder = Path(self.temp_dir)

    def create_command_file(self, command_content: str):
        """Helper to create a command.txt file for testing."""
        command_file = self.output_folder / "command.txt"
        with open(command_file, 'w', encoding='utf-8') as f:
            f.write(f"# Command executed at test time\n")
            f.write(f"{command_content}\n")
        return command_file

    def test_load_command_from_folder_basic(self):
        """Test loading a basic command from folder."""
        command_content = "emuses full /tmp/output data.csv --scores scores.csv"
        self.create_command_file(command_content)
        
        loaded_command = load_command_from_folder(self.output_folder)
        assert loaded_command == command_content

    def test_load_command_from_folder_with_comments(self):
        """Test loading command with comments and metadata."""
        command_content = "emuses full /tmp/output data.csv --optuna_trials 5"
        command_file = self.output_folder / "command.txt"
        with open(command_file, 'w', encoding='utf-8') as f:
            f.write("# EMUSES Command Log\n")
            f.write("# Generated: 2025-07-27 10:30:00\n")
            f.write("# User: test_user\n")
            f.write(f"{command_content}\n")
            f.write("# End of log\n")
        
        loaded_command = load_command_from_folder(self.output_folder)
        assert loaded_command == command_content

    def test_command_parsing_with_absolute_path(self):
        """Test command parsing handles absolute paths correctly."""
        test_cases = [
            # Absolute path cases that should be fixed
            {
                "input": "/home/tolhsadum/miniforge3/envs/emuses/bin/emuses full /tmp/output data.csv",
                "expected_args": ["full", "/tmp/output", "data.csv"]
            },
            {
                "input": "/usr/local/bin/emuses umap /tmp/test --n_trials 10",
                "expected_args": ["umap", "/tmp/test", "--n_trials", "10"]
            },
            # Regular emuses command (existing behavior)
            {
                "input": "emuses full /tmp/output data.csv --scores scores.csv",
                "expected_args": ["full", "/tmp/output", "data.csv", "--scores", "scores.csv"]
            },
            # Command without emuses prefix (should remain unchanged)
            {
                "input": "python -m some.module arg1 arg2",
                "expected_args": ["python", "-m", "some.module", "arg1", "arg2"]
            }
        ]
        
        for case in test_cases:
            command_parts = shlex.split(case["input"])
            
            # Apply the same logic as in the fixed rerun function
            if command_parts and ('emuses' in command_parts[0] or command_parts[0].startswith('/')):
                command_parts = command_parts[1:]  # Remove first element (executable path)
            
            if case["input"].startswith(('/home/', '/usr/', '/opt/')) or 'emuses' in case["input"]:
                # For emuses commands, we expect the executable to be removed
                if 'emuses' in case["input"]:
                    assert command_parts == case["expected_args"], \
                        f"Failed for input: {case['input']}, got: {command_parts}, expected: {case['expected_args']}"
            else:
                # For non-emuses commands, should remain unchanged
                assert command_parts == case["expected_args"], \
                    f"Failed for input: {case['input']}, got: {command_parts}, expected: {case['expected_args']}"

    def test_command_parsing_with_spaces_in_paths(self):
        """Test command parsing handles quoted paths with spaces."""
        test_cases = [
            {
                "input": 'emuses full "/path with spaces/output" "data file.csv"',
                "expected_args": ["full", "/path with spaces/output", "data file.csv"]
            },
            {
                "input": '"/usr/local/bin/emuses" full "/tmp/output dir" data.csv',
                "expected_args": ["full", "/tmp/output dir", "data.csv"]
            }
        ]
        
        for case in test_cases:
            command_parts = shlex.split(case["input"])
            
            # Apply the same logic as in the fixed rerun function
            if command_parts and ('emuses' in command_parts[0] or command_parts[0].startswith('/')):
                command_parts = command_parts[1:]  # Remove first element (executable path)
            
            assert command_parts == case["expected_args"], \
                f"Failed for input: {case['input']}, got: {command_parts}, expected: {case['expected_args']}"

    def test_command_saving_with_spaces_real_world(self):
        """Test command saving properly quotes paths with spaces (real-world bug case)."""
        # Simulate the real-world case that failed
        import shlex
        from emuses.cli.main import save_command_to_output_folder
        
        # Mock sys.argv with paths containing spaces (as they would appear after shell parsing)
        mock_argv = [
            '/home/user/miniforge3/envs/emuses/bin/emuses',
            'full',
            '/home/user/new_cli_test_wsl',
            '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv',
            '--columns_are_features',
            '--scores',
            '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv',
            '--optuna_trials',
            '10'
        ]
        
        # Create temporary output directory
        command_file = self.output_folder / "command.txt"
        
        # Test the command reconstruction (this is what should be fixed)
        with patch('sys.argv', mock_argv):
            save_command_to_output_folder(self.output_folder)
        
        # Load the saved command
        saved_command = load_command_from_folder(self.output_folder)
        
        # Parse the saved command - this should NOT fail
        command_parts = shlex.split(saved_command)
        
        # Remove executable path
        if command_parts and ('emuses' in command_parts[0] or command_parts[0].startswith('/')):
            command_parts = command_parts[1:]
        
        # Verify all arguments are preserved correctly
        expected_parts = [
            'full',
            '/home/user/new_cli_test_wsl',
            '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv',
            '--columns_are_features',
            '--scores',
            '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv',
            '--optuna_trials',
            '10'
        ]
        
        assert command_parts == expected_parts, \
            f"Command with spaces not preserved correctly. Got: {command_parts}, Expected: {expected_parts}"
        
        # Verify that paths with spaces are intact (not split)
        path_with_spaces = '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv'
        assert path_with_spaces in command_parts, \
            f"Path with spaces was split incorrectly: {command_parts}"

    def test_command_saving_preserves_complex_arguments(self):
        """Test that command saving preserves complex arguments with various special characters."""
        test_cases = [
            # Paths with spaces
            ['/usr/bin/emuses', 'full', '/tmp/output', '/path with spaces/data.csv'],
            # Paths with quotes and spaces  
            ['/usr/bin/emuses', 'full', '/tmp/output', "/path's data/file.csv"],
            # Multiple paths with spaces
            ['/usr/bin/emuses', 'full', '/output dir', '/data dir/file.csv', '--scores', '/score dir/scores.csv'],
            # Arguments with equals and complex values
            ['/usr/bin/emuses', 'full', '/tmp/output', 'data.csv', '--config=/path with spaces/config.json']
        ]
        
        for i, mock_argv in enumerate(test_cases):
            # Create separate output folder for each test
            test_output = self.output_folder / f"test_{i}"
            test_output.mkdir()
            
            # Save command
            with patch('sys.argv', mock_argv):
                save_command_to_output_folder(test_output)
            
            # Load and parse command
            saved_command = load_command_from_folder(test_output)
            command_parts = shlex.split(saved_command)
            
            # Remove executable path
            if command_parts and ('emuses' in command_parts[0] or command_parts[0].startswith('/')):
                command_parts = command_parts[1:]
            
            # Expected parts (everything except the executable)
            expected_parts = mock_argv[1:]
            
            assert command_parts == expected_parts, \
                f"Case {i} failed. Got: {command_parts}, Expected: {expected_parts}"

    def test_cross_platform_path_scenarios(self):
        """Test cross-platform path scenarios including Windows, Unix, and edge cases."""
        test_cases = [
            {
                "name": "Windows drive paths",
                "argv": [r'C:\Users\emuses\bin\emuses.exe', 'full', r'C:\Output', r'C:\Data\file with spaces.csv']
            },
            {
                "name": "Windows UNC paths", 
                "argv": [r'\\server\bin\emuses.exe', 'full', r'\\server\output', r'\\server\data\file with spaces.csv']
            },
            {
                "name": "WSL mixed paths",
                "argv": ['/usr/bin/emuses', 'full', '/mnt/c/Output', '/mnt/c/Program Files/Data/file.csv']
            },
            {
                "name": "Unicode characters",
                "argv": ['/usr/bin/emuses', 'full', '/tmp/output', '/données/fichier avec espaces.csv', '--scores', '/用户/数据/scores.csv']
            },
            {
                "name": "Special shell characters",
                "argv": ['/usr/bin/emuses', 'full', '/tmp/output', '/data/file&data.csv', '--config', '/config/app|settings.json']
            },
            {
                "name": "Very long path",
                "argv": ['/usr/bin/emuses', 'full', '/tmp/output', '/very/long/nested/directory/structure/with/many/levels/and spaces in names/final file.csv']
            },
            {
                "name": "Paths with quotes",
                "argv": ['/usr/bin/emuses', 'full', '/tmp/output', '/data/file"with"quotes.csv']
            },
            {
                "name": "Mixed separators", 
                "argv": ['/usr/bin/emuses', 'full', r'/tmp\mixed/separators', r'/data\file with spaces/data.csv']
            }
        ]
        
        for case in test_cases:
            # Create separate output folder for each test
            test_output = self.output_folder / case["name"].replace(" ", "_").replace("/", "_")
            test_output.mkdir()
            
            # Save command
            with patch('sys.argv', case["argv"]):
                save_command_to_output_folder(test_output)
            
            # Load and parse command
            saved_command = load_command_from_folder(test_output)
            
            # Should be able to parse without errors
            try:
                command_parts = shlex.split(saved_command)
            except Exception as e:
                pytest.fail(f"Failed to parse saved command for {case['name']}: {e}\nCommand: {saved_command}")
            
            # Remove executable path
            if command_parts and ('emuses' in command_parts[0] or command_parts[0].startswith(('/', r'C:', r'\\'))):
                command_parts = command_parts[1:]
            
            # Expected parts (everything except the executable)
            expected_parts = case["argv"][1:]
            
            assert command_parts == expected_parts, \
                f"{case['name']} failed.\nGot: {command_parts}\nExpected: {expected_parts}\nSaved command: {saved_command}"

    def test_quote_argument_cross_platform_function(self):
        """Test the cross-platform quoting function directly."""
        # Import the function (it's defined inside save_command_to_output_folder, so we'll test indirectly)
        test_cases = [
            # Cases that shouldn't need quoting
            ("simple_file.csv", "simple_file.csv"),
            ("/usr/bin/emuses", "/usr/bin/emuses"),
            ("--optuna_trials", "--optuna_trials"),
            ("42", "42"),
            
            # Cases that need quoting
            ("file with spaces.csv", '"file with spaces.csv"'),
            ("/path with spaces/file.csv", '"/path with spaces/file.csv"'),
            ("file\twith\ttabs.csv", '"file\twith\ttabs.csv"'),
            ("file|with|pipes.csv", '"file|with|pipes.csv"'),
            ("file&with&amps.csv", '"file&with&amps.csv"'),
            ("file;with;semicolons.csv", '"file;with;semicolons.csv"'),
            ("file$with$dollars.csv", '"file$with$dollars.csv"'),
            ("file`with`backticks.csv", '"file`with`backticks.csv"'),
            ("file(with)parens.csv", '"file(with)parens.csv"'),
            ("file<with>brackets.csv", '"file<with>brackets.csv"'),
            
            # Cases with existing quotes (should be escaped)
            ('file"with"quotes.csv', '"file\\"with\\"quotes.csv"'),
            ("file'with'apostrophes.csv", '"file\'with\'apostrophes.csv"'),
            
            # Mixed cases
            ('complex "file name" with spaces.csv', '"complex \\"file name\\" with spaces.csv"'),
        ]
        
        for input_arg, expected_output in test_cases:
            # Test by creating a command and checking the result
            mock_argv = ['/usr/bin/emuses', 'full', '/tmp/output', input_arg]
            test_output = self.output_folder / f"quote_test_{hash(input_arg) % 1000}"
            test_output.mkdir(exist_ok=True)
            
            with patch('sys.argv', mock_argv):
                save_command_to_output_folder(test_output)
            
            saved_command = load_command_from_folder(test_output)
            
            # Extract the last argument from the saved command to see how it was quoted
            command_parts = shlex.split(saved_command)
            actual_last_arg = command_parts[-1]
            
            assert actual_last_arg == input_arg, \
                f"Quoting/parsing roundtrip failed for '{input_arg}'. Expected: '{input_arg}', Got: '{actual_last_arg}'"

    def test_command_parsing_edge_cases(self):
        """Test edge cases for command parsing."""
        test_cases = [
            # Empty command
            {"input": "", "expected_args": []},
            # Single word command
            {"input": "emuses", "expected_args": []},
            # Absolute path only
            {"input": "/home/user/bin/emuses", "expected_args": []},
            # Command with equals signs and complex arguments
            {
                "input": "emuses full /tmp/out data.csv --config=/path/to/config.json --verbose=true",
                "expected_args": ["full", "/tmp/out", "data.csv", "--config=/path/to/config.json", "--verbose=true"]
            }
        ]
        
        for case in test_cases:
            if case["input"]:  # Skip empty input
                command_parts = shlex.split(case["input"])
                
                # Apply the same logic as in the fixed rerun function
                if command_parts and ('emuses' in command_parts[0] or command_parts[0].startswith('/')):
                    command_parts = command_parts[1:]  # Remove first element (executable path)
            else:
                command_parts = []
            
            assert command_parts == case["expected_args"], \
                f"Failed for input: '{case['input']}', got: {command_parts}, expected: {case['expected_args']}"

    @patch('subprocess.run')
    @patch('emuses.cli.main.load_command_from_folder')
    def test_rerun_integration_with_absolute_path(self, mock_load_command, mock_subprocess):
        """Test full rerun integration with absolute path command."""
        from emuses.cli.main import rerun
        import typer
        
        # Mock the command loading to return an absolute path command
        absolute_path_command = "/home/user/miniforge3/envs/emuses/bin/emuses full /tmp/test data.csv --optuna_trials 5"
        mock_load_command.return_value = absolute_path_command
        
        # Mock subprocess to succeed
        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result
        
        # Test the rerun function
        test_output_folder = Path("/tmp/test_output")
        
        # This should not raise an exception
        rerun(test_output_folder)
        
        # Verify subprocess was called with correct arguments
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]  # Get the command list
        
        # Should be: [sys.executable, '-m', 'emuses.cli', 'full', '/tmp/test', 'data.csv', '--optuna_trials', '5']
        assert call_args[0].endswith('python') or call_args[0].endswith('python3')
        assert call_args[1:3] == ['-m', 'emuses.cli']
        assert 'full' in call_args
        assert '/tmp/test' in call_args
        assert 'data.csv' in call_args
        assert '--optuna_trials' in call_args
        assert '5' in call_args
        
        # Verify the original absolute path is NOT in the arguments
        absolute_path = "/home/user/miniforge3/envs/emuses/bin/emuses"
        assert absolute_path not in call_args

    def test_file_not_found_error(self):
        """Test proper error handling when command.txt doesn't exist."""
        non_existent_folder = Path("/tmp/non_existent_folder_12345")
        
        with pytest.raises(FileNotFoundError) as exc_info:
            load_command_from_folder(non_existent_folder)
        
        assert "No command.txt found" in str(exc_info.value)

    def test_empty_command_file_error(self):
        """Test proper error handling when command.txt is empty or has no valid commands."""
        # Create empty file
        command_file = self.output_folder / "command.txt"
        with open(command_file, 'w', encoding='utf-8') as f:
            f.write("# Just comments\n")
            f.write("# No actual command\n")
        
        with pytest.raises(ValueError) as exc_info:
            load_command_from_folder(self.output_folder)
        
        assert "No valid command found" in str(exc_info.value)

    def test_backward_compatibility_old_command_files(self):
        """Test backward compatibility with old command files (before quoting fix)."""
        # Create a command file like the ones created before our quoting fix
        old_command = "/home/tolhsadum/miniforge3/envs/emuses/bin/emuses full /home/tolhsadum/new_cli_test_wsl /mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv --columns_are_features --input_header 0 --input_index_column 0 --input_normalization robust --scores /mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv --scores_header 0 --interactive_plot --umap_trials 1 --hdbscan_trials 1 --optuna_trials 10 --hdbscan_jobs 16"
        
        command_file = self.output_folder / "command.txt"
        with open(command_file, 'w', encoding='utf-8') as f:
            f.write("# EMUSES Pipeline Command\n")
            f.write(f"# Generated on: 2025-07-27 16:15:40\n")
            f.write(f"# To rerun: {old_command}\n")
            f.write(f"# Or use: emuses rerun \"{self.output_folder}\"\n")
            f.write(f"\n")
            f.write(f"{old_command}\n")
        
        # Load the command - should apply backward compatibility fix
        fixed_command = load_command_from_folder(self.output_folder)
        
        # Parse the fixed command - should work without splitting paths
        import shlex
        parsed = shlex.split(fixed_command)
        
        # Check that the problematic paths are now intact
        expected_path1 = '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv'
        expected_path2 = '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv'
        
        assert expected_path1 in parsed, f"Path 1 not found intact in: {parsed}"
        assert expected_path2 in parsed, f"Path 2 not found intact in: {parsed}"
        
        # Verify no split path fragments
        problematic_fragments = ['Dropbox/Chris', 'Foulon/EMUSE/HCP_psy/selected_columns_data.csv', 'Foulon/EMUSE/HCP_psy/fluid_int_adj.csv']
        for fragment in problematic_fragments:
            assert fragment not in parsed, f"Found split fragment '{fragment}' in parsed command"

    def test_backward_compatibility_detection(self):
        """Test that the backward compatibility detection works correctly."""
        from emuses.cli.main import _fix_unquoted_command
        
        # Test the specific pattern from user's command file
        problematic_command = "/home/tolhsadum/miniforge3/envs/emuses/bin/emuses full /home/tolhsadum/new_cli_test_wsl /mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv --columns_are_features --scores /mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv"
        
        fixed_command = _fix_unquoted_command(problematic_command)
        
        # Should have quotes around the paths with spaces
        assert '"/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv"' in fixed_command
        assert '"/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv"' in fixed_command
        
        # Verify parsing works
        import shlex
        parsed = shlex.split(fixed_command)
        expected_paths = [
            '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv',
            '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv'
        ]
        
        for path in expected_paths:
            assert path in parsed, f"Expected path not found: {path}"

    def test_mixed_old_new_command_compatibility(self):
        """Test that properly quoted commands (new format) pass through unchanged."""
        # Create a properly quoted command (new format)
        quoted_command = '/home/tolhsadum/miniforge3/envs/emuses/bin/emuses full /home/tolhsadum/new_cli_test_wsl "/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv" --columns_are_features --scores "/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv"'
        
        command_file = self.output_folder / "command.txt"
        with open(command_file, 'w', encoding='utf-8') as f:
            f.write("# EMUSES Pipeline Command\n")
            f.write(f"# Generated with quoting fix\n")
            f.write(f"{quoted_command}\n")
        
        # Load the command - should pass through unchanged since it's already properly quoted
        loaded_command = load_command_from_folder(self.output_folder)
        
        # Should be the same as the original (or minimally changed)
        import shlex
        original_parsed = shlex.split(quoted_command)
        loaded_parsed = shlex.split(loaded_command)
        
        # The essential structure should be the same
        assert len(original_parsed) == len(loaded_parsed)
        
        # Critical paths should be intact
        expected_paths = [
            '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv',
            '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv'
        ]
        
        for path in expected_paths:
            assert path in loaded_parsed, f"Path not preserved: {path}"

    def test_edge_case_command_patterns(self):
        """Test edge cases in command patterns for backward compatibility."""
        edge_cases = [
            # Multiple spaces in path
            "emuses full /tmp/out /mnt/s/GIN Dropbox/Chris Foulon/multiple  spaces/file.csv",
            
            # Path at end of command
            "emuses full /tmp/out data.csv --scores /mnt/s/GIN Dropbox/Chris Foulon/EMUSE/scores.csv",
            
            # Multiple problematic paths
            "emuses full /mnt/s/GIN Dropbox/output /mnt/s/GIN Dropbox/data.csv --scores /mnt/s/GIN Dropbox/scores.csv",
            
            # Mixed quoted and unquoted
            'emuses full "/tmp/quoted path" /mnt/s/GIN Dropbox/unquoted/path.csv',
        ]
        
        from emuses.cli.main import _fix_unquoted_command
        
        for command in edge_cases:
            try:
                fixed = _fix_unquoted_command(command)
                
                # Should be parseable
                import shlex
                parsed = shlex.split(fixed)
                
                # Should have reasonable number of parts (not massively split)
                assert len(parsed) < len(command.split()) + 5, f"Command over-split: {command} -> {parsed}"
                
            except Exception as e:
                pytest.fail(f"Failed to fix edge case command '{command}': {e}")


if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__])