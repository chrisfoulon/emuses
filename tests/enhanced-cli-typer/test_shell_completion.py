"""
Tests for Shell completion functionality (Task 7).

This module tests shell completion features including completion scripts
generation, command and argument completion, and file path completion.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import typer
from typer.testing import CliRunner

from emuses.cli.shell_completion import (
    ShellCompletionManager,
    CompletionScriptGenerator,
    CommandCompleter,
    FilePathCompleter
)


class TestShellCompletionManager:
    """Test the shell completion manager."""
    
    @pytest.fixture
    def completion_manager(self):
        """Create a completion manager instance."""
        return ShellCompletionManager()
    
    def test_completion_manager_creation(self, completion_manager):
        """Test that completion manager initializes correctly."""
        assert completion_manager is not None
        assert hasattr(completion_manager, 'supported_shells')
        assert hasattr(completion_manager, 'script_generator')
        assert hasattr(completion_manager, 'command_completer')
        assert hasattr(completion_manager, 'file_completer')
    
    def test_supported_shells(self, completion_manager):
        """Test that supported shells are configured."""
        shells = completion_manager.get_supported_shells()
        assert isinstance(shells, list)
        assert len(shells) > 0
        
        # Check for common shell support
        shell_names = [shell['name'] for shell in shells]
        assert 'bash' in shell_names
        assert 'zsh' in shell_names
        assert 'powershell' in shell_names
    
    def test_generate_completion_script(self, completion_manager):
        """Test generating completion scripts."""
        script = completion_manager.generate_completion_script('bash')
        assert script is not None
        assert isinstance(script, str)
        assert len(script) > 0
        
        # Check for bash-specific completion syntax
        assert 'complete' in script or 'compgen' in script
    
    def test_install_completion(self, completion_manager):
        """Test installing completion scripts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test installation
            result = completion_manager.install_completion(
                shell='bash',
                install_dir=temp_dir
            )
            assert result is True
            
            # Verify script was created
            script_files = list(Path(temp_dir).glob('*completion*'))
            assert len(script_files) > 0


class TestCompletionScriptGenerator:
    """Test completion script generation."""
    
    @pytest.fixture
    def script_generator(self):
        """Create a script generator instance."""
        return CompletionScriptGenerator()
    
    def test_script_generator_creation(self, script_generator):
        """Test that script generator initializes correctly."""
        assert script_generator is not None
        assert hasattr(script_generator, 'shell_templates')
        assert hasattr(script_generator, 'command_registry')
    
    def test_bash_script_generation(self, script_generator):
        """Test generating bash completion scripts."""
        script = script_generator.generate_bash_script('emuses')
        assert script is not None
        assert isinstance(script, str)
        assert '_emuses_completion' in script
        assert 'complete -F' in script
    
    def test_zsh_script_generation(self, script_generator):
        """Test generating zsh completion scripts."""
        script = script_generator.generate_zsh_script('emuses')
        assert script is not None
        assert isinstance(script, str)
        assert '_emuses' in script
        assert 'compdef' in script
    
    def test_powershell_script_generation(self, script_generator):
        """Test generating powershell completion scripts."""
        script = script_generator.generate_powershell_script('emuses')
        assert script is not None
        assert isinstance(script, str)
        assert 'Register-ArgumentCompleter' in script
    
    def test_register_command(self, script_generator):
        """Test registering commands for completion."""
        script_generator.register_command('process', {
            'description': 'Process data files',
            'arguments': ['--input', '--output', '--format'],
            'subcommands': []
        })
        
        commands = script_generator.get_registered_commands()
        assert 'process' in commands
        assert commands['process'].description == 'Process data files'
    
    def test_register_subcommand(self, script_generator):
        """Test registering subcommands for completion."""
        script_generator.register_command('data', {
            'description': 'Data operations',
            'arguments': ['--verbose'],
            'subcommands': ['process', 'validate', 'convert']
        })
        
        commands = script_generator.get_registered_commands()
        assert 'data' in commands
        assert 'process' in commands['data'].subcommands


class TestCommandCompleter:
    """Test command completion functionality."""
    
    @pytest.fixture
    def command_completer(self):
        """Create a command completer instance."""
        return CommandCompleter()
    
    def test_command_completer_creation(self, command_completer):
        """Test that command completer initializes correctly."""
        assert command_completer is not None
        assert hasattr(command_completer, 'commands')
        assert hasattr(command_completer, 'arguments')
    
    def test_complete_command(self, command_completer):
        """Test completing command names."""
        # Register test commands
        command_completer.register_command('process')
        command_completer.register_command('predict')
        command_completer.register_command('visualize')
        
        # Test completion
        completions = command_completer.complete_command('pro')
        assert 'process' in completions
        assert 'visualize' not in completions
        
        # Test prefix matching for predict
        pred_completions = command_completer.complete_command('pred')
        assert 'predict' in pred_completions
    
    def test_complete_arguments(self, command_completer):
        """Test completing command arguments."""
        # Register command with arguments
        command_completer.register_command('process', [
            '--input', '--output', '--format', '--verbose'
        ])
        
        # Test argument completion
        completions = command_completer.complete_arguments('process', '--in')
        assert '--input' in completions
        assert '--output' not in completions
    
    def test_complete_argument_values(self, command_completer):
        """Test completing argument values."""
        # Register command with argument options
        command_completer.register_command('process', [
            '--format'
        ])
        command_completer.register_argument_values('process', '--format', [
            'csv', 'json', 'parquet'
        ])
        
        # Test value completion
        completions = command_completer.complete_argument_values('process', '--format', 'cs')
        assert 'csv' in completions
        assert 'json' not in completions
    
    def test_contextual_completion(self, command_completer):
        """Test contextual completion based on current input."""
        command_completer.register_command('process', ['--input', '--output'])
        
        # Test completion in different contexts
        context = {'command': 'process', 'partial': '--in'}
        completions = command_completer.get_completions(context)
        assert '--input' in completions


class TestFilePathCompleter:
    """Test file path completion functionality."""
    
    @pytest.fixture
    def file_completer(self):
        """Create a file path completer instance."""
        return FilePathCompleter()
    
    def test_file_completer_creation(self, file_completer):
        """Test that file completer initializes correctly."""
        assert file_completer is not None
        assert hasattr(file_completer, 'allowed_extensions')
        assert hasattr(file_completer, 'base_directory')
    
    def test_complete_file_path(self, file_completer):
        """Test completing file paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            (Path(temp_dir) / "test1.csv").write_text("data")
            (Path(temp_dir) / "test2.txt").write_text("data")
            (Path(temp_dir) / "other.json").write_text("data")
            
            # Test completion
            completions = file_completer.complete_path(
                partial_path=f"{temp_dir}/test",
                allowed_extensions=['.csv', '.txt']
            )
            
            assert any('test1.csv' in comp for comp in completions)
            assert any('test2.txt' in comp for comp in completions)
            assert not any('other.json' in comp for comp in completions)
    
    def test_complete_directory_path(self, file_completer):
        """Test completing directory paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test directories
            (Path(temp_dir) / "data").mkdir()
            (Path(temp_dir) / "output").mkdir()
            (Path(temp_dir) / "logs").mkdir()
            
            # Test completion
            completions = file_completer.complete_path(
                partial_path=f"{temp_dir}/d",
                directories_only=True
            )
            
            assert any('data' in comp for comp in completions)
            assert not any('output' in comp for comp in completions)
    
    def test_complete_relative_path(self, file_completer):
        """Test completing relative paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change to test directory
            old_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                # Create test files
                Path("file1.txt").write_text("data")
                Path("file2.csv").write_text("data")
                
                # Test completion
                completions = file_completer.complete_path("file")
                
                assert any('file1.txt' in comp for comp in completions)
                assert any('file2.csv' in comp for comp in completions)
            finally:
                os.chdir(old_cwd)
    
    def test_security_filtering(self, file_completer):
        """Test security filtering in path completion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files including potentially dangerous paths
            (Path(temp_dir) / "safe.txt").write_text("data")
            (Path(temp_dir) / "..hidden").write_text("data")
            
            # Test completion with security filtering
            completions = file_completer.complete_path(
                partial_path=f"{temp_dir}/",
                security_filter=True
            )
            
            assert any('safe.txt' in comp for comp in completions)
            assert not any('..hidden' in comp for comp in completions)
    
    def test_extension_filtering(self, file_completer):
        """Test extension-based filtering."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files with different extensions
            (Path(temp_dir) / "data.csv").write_text("data")
            (Path(temp_dir) / "config.json").write_text("data")
            (Path(temp_dir) / "script.py").write_text("data")
            
            # Test with extension filter
            completions = file_completer.complete_path(
                partial_path=f"{temp_dir}/",
                allowed_extensions=['.csv', '.json']
            )
            
            assert any('data.csv' in comp for comp in completions)
            assert any('config.json' in comp for comp in completions)
            assert not any('script.py' in comp for comp in completions)


class TestShellCompletionIntegration:
    """Test integration between completion components."""
    
    @pytest.fixture
    def completion_manager(self):
        """Create a completion manager with all components."""
        return ShellCompletionManager()
    
    def test_full_completion_workflow(self, completion_manager):
        """Test complete workflow from registration to completion."""
        # Register commands
        completion_manager.register_command('process', {
            'arguments': ['--input', '--output'],
            'description': 'Process data files'
        })
        
        # Test command completion
        completions = completion_manager.get_command_completions('proc')
        assert 'process' in completions
        
        # Test argument completion
        arg_completions = completion_manager.get_argument_completions('process', '--in')
        assert '--input' in arg_completions
    
    def test_cross_platform_compatibility(self, completion_manager):
        """Test completion works across different platforms."""
        # Test on different shell types
        for shell in ['bash', 'zsh', 'powershell']:
            script = completion_manager.generate_completion_script(shell)
            assert script is not None
            assert len(script) > 0
    
    def test_completion_caching(self, completion_manager):
        """Test completion result caching."""
        # Register command
        completion_manager.register_command('test_cmd', {'description': 'Test command'})
        
        # Test caching behavior
        completions1 = completion_manager.get_command_completions('test')
        completions2 = completion_manager.get_command_completions('test')
        
        assert completions1 == completions2
        assert 'test_cmd' in completions1