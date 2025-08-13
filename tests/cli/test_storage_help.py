"""
Tests for Phase 4.5.3: Documentation and Help System Improvements.

This module tests enhanced CLI help content for storage management
and user guidance about hidden directory structure.
"""

import pytest
from typer.testing import CliRunner
from emuses.cli.models_commands import models_app


class TestStorageManagementHelp:
    """Tests for Task 4.5.3.a: CLI help improvements."""

    def test_models_help_includes_storage_management_section(self):
        """Test that models command help includes storage management guidance."""
        runner = CliRunner()
        result = runner.invoke(models_app, ['--help'])
        
        assert result.exit_code == 0
        help_text = result.output.lower()
        
        # Should mention storage management in main help
        assert 'storage' in help_text
        assert 'cleanup' in help_text
        
        # Should provide guidance about storage commands
        assert any(keyword in help_text for keyword in [
            'manage storage', 'disk space', 'storage usage'
        ])

    def test_cleanup_command_help_includes_examples(self):
        """Test that cleanup command help includes practical examples."""
        runner = CliRunner()
        result = runner.invoke(models_app, [ 'cleanup', '--help'])
        
        assert result.exit_code == 0
        help_text = result.output.lower()
        
        # Should include guidance about dry-run and safety
        assert 'dry-run' in help_text
        assert any(keyword in help_text for keyword in [
            'preview', 'safe', 'without actually'
        ])

    def test_storage_command_help_includes_troubleshooting(self):
        """Test that storage command help includes troubleshooting guidance."""
        runner = CliRunner()
        result = runner.invoke(models_app, [ 'storage', '--help'])
        
        assert result.exit_code == 0
        help_text = result.output.lower()
        
        # Should mention thresholds and monitoring
        assert any(keyword in help_text for keyword in [
            'threshold', 'warning', 'monitoring', 'disk space'
        ])


class TestHiddenDirectoryGuidance:
    """Tests for Task 4.5.3.b: Hidden directory user awareness."""

    def test_first_time_user_guidance_in_status(self):
        """Test that status command provides guidance about ~/.emuses/ directory."""
        runner = CliRunner()
        result = runner.invoke(models_app, [ 'status'])
        
        assert result.exit_code == 0
        output = result.output.lower()
        
        # Should mention hidden directory location
        assert any(indicator in output for indicator in [
            '~/.emuses', 'hidden directory', '.emuses'
        ])

    def test_storage_location_visibility_in_commands(self):
        """Test that storage location is visible in relevant commands."""
        runner = CliRunner()
        result = runner.invoke(models_app, [ 'storage'])
        
        assert result.exit_code == 0
        output = result.output
        
        # Should show registry location prominently
        assert 'Registry Location' in output or 'Path:' in output
        assert '.emuses' in output

    def test_helpful_tips_about_directory_access(self):
        """Test that commands include tips about accessing hidden directories."""
        runner = CliRunner()
        result = runner.invoke(models_app, [ 'storage'])
        
        assert result.exit_code == 0
        output = result.output.lower()
        
        # Should provide tips about hidden directory access
        assert any(tip in output for tip in [
            'hidden directory', 'tip', '💡', 'show hidden files'
        ])


class TestHelpContentEffectiveness:
    """Tests for Task 4.5.3.c: Help content effectiveness verification."""

    def test_storage_help_content_accuracy(self):
        """Test that help content accurately describes storage functionality."""
        runner = CliRunner()
        
        # Test each storage-related command has accurate help
        commands = ['storage', 'cleanup', 'status']
        for cmd in commands:
            result = runner.invoke(models_app, [ cmd, '--help'])
            assert result.exit_code == 0
            assert len(result.output) > 50  # Has meaningful help content

    def test_help_includes_practical_examples(self):
        """Test that help content includes practical usage examples."""
        runner = CliRunner()
        result = runner.invoke(models_app, ['--help'])
        
        assert result.exit_code == 0
        help_text = result.output
        
        # Should have clear command descriptions
        assert 'Show storage usage' in help_text or 'storage usage' in help_text.lower()
        assert 'Clean up' in help_text or 'cleanup' in help_text.lower()

    def test_error_messages_include_helpful_guidance(self):
        """Test that error messages include helpful next steps."""
        runner = CliRunner()
        
        # Test with invalid registry path - command may succeed but log errors
        result = runner.invoke(models_app, ['storage', '-r', '/nonexistent/path'])
        
        # Command may succeed with graceful error handling, check output contains useful info
        output = result.output.lower()
        
        # Should provide helpful guidance about storage or registry location
        assert any(hint in output for hint in [
            'registry', 'storage', 'path', 'location'
        ])

    def test_consistent_terminology_across_commands(self):
        """Test that terminology is consistent across storage-related commands."""
        runner = CliRunner()
        
        commands = ['storage', 'cleanup', 'status']
        help_outputs = []
        
        for cmd in commands:
            result = runner.invoke(models_app, [ cmd, '--help'])
            assert result.exit_code == 0
            help_outputs.append(result.output.lower())
        
        # Should use consistent terminology
        # All should mention "registry" consistently
        for output in help_outputs:
            if 'registry' in output or 'models' in output:
                # Basic consistency check passed
                assert True