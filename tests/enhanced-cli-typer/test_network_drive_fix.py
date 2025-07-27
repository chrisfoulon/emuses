"""
Tests for network drive SQLite compatibility fix.

This module tests the network drive detection and SQLite storage workaround
to prevent database I/O errors on cloud storage and network drives.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from emuses.utils.network_drive_detection import (
    is_network_or_cloud_path,
    get_sqlite_safe_location,
    setup_optuna_storage_safe,
    validate_sqlite_compatibility,
    cleanup_temp_sqlite_location
)


class TestNetworkDriveDetection:
    """Test cases for network drive detection."""

    def test_dropbox_path_detection(self):
        """Test detection of Dropbox cloud storage paths."""
        test_cases = [
            ("/mnt/s/GIN Dropbox/Chris Foulon/EMUSE", True, "Dropbox cloud storage"),
            ("/home/user/Dropbox/project", True, "Dropbox cloud storage"),
            ("/Users/user/Dropbox/files", True, "Dropbox cloud storage"),
            ("C:\\Users\\user\\Dropbox\\project", True, "Dropbox cloud storage"),
        ]
        
        for path_str, expected_is_network, expected_reason in test_cases:
            path = Path(path_str)
            is_network, reason = is_network_or_cloud_path(path)
            assert is_network == expected_is_network, f"Failed for path: {path_str}"
            if expected_is_network:
                assert expected_reason in reason, f"Wrong reason for {path_str}: {reason}"

    def test_network_drive_detection(self):
        """Test detection of various network drive patterns."""
        test_cases = [
            # Mounted drives
            ("/mnt/server/share", True, "mounted"),
            ("/mnt/c/Users", True, "mounted"),
            
            # UNC paths  
            ("\\\\server\\share\\folder", True, "network"),
            
            # Network filesystems
            ("/net/server/share", True, "network"),
            ("/nfs/mount/point", True, "nfs"),
            ("/cifs/mount", True, "cifs"),
            ("/smb/share", True, "smb"),
        ]
        
        for path_str, expected_is_network, expected_keyword in test_cases:
            path = Path(path_str)
            is_network, reason = is_network_or_cloud_path(path)
            assert is_network == expected_is_network, f"Failed for path: {path_str}"
            if expected_is_network:
                assert expected_keyword in reason.lower(), f"Wrong reason for {path_str}: {reason}"

    def test_local_path_detection(self):
        """Test that local paths are correctly identified as non-network."""
        local_paths = [
            "/home/user/documents",
            "/tmp/test",
            "/usr/local/bin",
            "/var/log",
            # Note: We exclude Windows paths like C:\ because they might be detected
            # as mounted drives in WSL environments, which is actually correct behavior
        ]
        
        for path_str in local_paths:
            path = Path(path_str)
            is_network, reason = is_network_or_cloud_path(path)
            assert not is_network, f"Local path incorrectly detected as network: {path_str} ({reason})"

    def test_cloud_storage_detection(self):
        """Test detection of various cloud storage services."""
        cloud_patterns = [
            ("/home/user/OneDrive/project", "Microsoft OneDrive"),
            ("/Users/user/Google Drive/files", "Google Drive"),
            ("/mnt/iCloud/documents", "Apple iCloud"),
            ("C:\\Users\\user\\Box Sync\\project", "Box cloud storage"),
            ("/home/user/pCloud/files", "pCloud storage"),
            ("/Users/user/MEGA/backup", "MEGA cloud storage"),
        ]
        
        for path_str, expected_service in cloud_patterns:
            path = Path(path_str)
            is_network, reason = is_network_or_cloud_path(path)
            assert is_network, f"Cloud path not detected: {path_str}"
            assert expected_service in reason, f"Wrong service for {path_str}: {reason}"


class TestSQLiteSafeLocation:
    """Test cases for SQLite safe location selection."""

    def test_safe_location_for_local_path(self):
        """Test that local paths use themselves as SQLite location."""
        local_path = Path("/tmp/test_local")
        safe_location, is_relocated, explanation = get_sqlite_safe_location(local_path)
        
        assert safe_location == local_path
        assert not is_relocated
        assert explanation == ""

    def test_safe_location_for_network_path(self):
        """Test that network paths get relocated to local temp storage."""
        network_path = Path("/mnt/s/GIN Dropbox/test")
        safe_location, is_relocated, explanation = get_sqlite_safe_location(network_path)
        
        assert is_relocated
        assert safe_location != network_path
        assert safe_location.parts[1] == "tmp"  # Should be in /tmp/
        assert "emuses_sqlite_" in safe_location.name
        assert "Dropbox cloud storage" in explanation
        assert "local storage" in explanation
        # Note: The explanation contains generic text, not the specific path

    def test_optuna_storage_setup(self):
        """Test Optuna storage URL generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir)
            
            # Test local path - should use provided path
            storage_url = setup_optuna_storage_safe("test_study", local_path)
            assert storage_url.startswith("sqlite:///")
            assert str(local_path) in storage_url
            assert "test_study.db" in storage_url
            
            # Test network path - should use temp location
            network_path = Path("/mnt/s/GIN Dropbox/test")
            with patch('builtins.print'):  # Suppress warning output
                storage_url = setup_optuna_storage_safe("test_study", network_path)
            
            assert storage_url.startswith("sqlite:///")
            assert "/tmp/emuses_sqlite_" in storage_url
            assert "test_study.db" in storage_url
            assert str(network_path) not in storage_url

    def test_temp_location_cleanup(self):
        """Test cleanup of temporary SQLite locations."""
        # Create a temporary directory to simulate SQLite temp location
        temp_location = Path(tempfile.mkdtemp(prefix='emuses_sqlite_'))
        test_file = temp_location / "test.db"
        test_file.write_text("test data")
        
        assert temp_location.exists()
        assert test_file.exists()
        
        # Test cleanup
        output_folder = Path("/tmp/test_output")
        cleanup_temp_sqlite_location(temp_location, output_folder)
        
        assert not temp_location.exists()

    def test_cleanup_nonexistent_location(self):
        """Test cleanup with non-existent location."""
        nonexistent = Path("/tmp/does_not_exist_12345")
        output_folder = Path("/tmp/test_output")
        
        # Should not raise exception
        cleanup_temp_sqlite_location(nonexistent, output_folder)


class TestSQLiteCompatibility:
    """Test cases for SQLite compatibility validation."""

    def test_sqlite_compatibility_local_path(self):
        """Test SQLite compatibility on local filesystem."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir)
            is_compatible, error_msg = validate_sqlite_compatibility(test_path)
            
            assert is_compatible
            assert error_msg == ""

    def test_sqlite_compatibility_creates_directory(self):
        """Test that compatibility test creates necessary directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir) / "subdir" / "nested"
            
            assert not test_path.exists()
            
            is_compatible, error_msg = validate_sqlite_compatibility(test_path)
            
            assert test_path.exists()
            assert is_compatible

    @patch('sqlite3.connect')
    def test_sqlite_compatibility_connection_failure(self, mock_connect):
        """Test SQLite compatibility when connection fails."""
        mock_connect.side_effect = Exception("Connection failed")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir)
            is_compatible, error_msg = validate_sqlite_compatibility(test_path)
            
            assert not is_compatible
            assert "Connection failed" in error_msg

    @patch('sqlite3.connect')
    def test_sqlite_compatibility_operation_failure(self, mock_connect):
        """Test SQLite compatibility when operations fail."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # Simulate read failure
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir)
            is_compatible, error_msg = validate_sqlite_compatibility(test_path)
            
            assert not is_compatible
            assert "failed to read data correctly" in error_msg


class TestIntegration:
    """Integration tests for the complete network drive fix."""

    def test_end_to_end_dropbox_scenario(self):
        """Test complete workflow for Dropbox path scenario."""
        # Simulate user's exact problem scenario
        dropbox_path = Path("/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/output")
        
        # 1. Detection should identify it as Dropbox
        is_network, reason = is_network_or_cloud_path(dropbox_path)
        assert is_network
        assert "Dropbox" in reason
        
        # 2. Safe location should be local temp
        safe_location, is_relocated, explanation = get_sqlite_safe_location(dropbox_path)
        assert is_relocated
        assert "/tmp/" in str(safe_location)
        assert "emuses_sqlite_" in str(safe_location)
        
        # 3. Optuna storage should use safe location
        with patch('builtins.print'):  # Suppress warning output
            storage_url = setup_optuna_storage_safe("umap_nested_optimization", dropbox_path)
        
        assert "sqlite:///" in storage_url
        assert "/tmp/emuses_sqlite_" in storage_url
        assert "umap_nested_optimization.db" in storage_url
        
        # 4. Storage location should exist after setup
        db_path = Path(storage_url.replace("sqlite:///", ""))
        assert db_path.parent.exists()
        
        # 5. Cleanup should work
        cleanup_temp_sqlite_location(db_path.parent, dropbox_path)

    def test_end_to_end_local_scenario(self):
        """Test complete workflow for local path scenario."""
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir)
            
            # 1. Detection should identify it as local
            is_network, reason = is_network_or_cloud_path(local_path)
            assert not is_network
            
            # 2. Safe location should be the same path
            safe_location, is_relocated, explanation = get_sqlite_safe_location(local_path)
            assert not is_relocated
            assert safe_location == local_path
            
            # 3. Optuna storage should use the original path
            storage_url = setup_optuna_storage_safe("test_study", local_path)
            assert str(local_path) in storage_url
            assert "test_study.db" in storage_url

    def test_real_world_paths(self):
        """Test with real-world problematic paths."""
        problematic_paths = [
            # User's exact paths from bug report
            "/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv",
            "/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv",
            
            # Other common network/cloud patterns
            "/home/user/Dropbox/research/project",
            "/mnt/server/shared/analysis",
            "\\\\fileserver\\data\\experiments",
        ]
        
        for path_str in problematic_paths:
            path = Path(path_str).parent if path_str.endswith('.csv') else Path(path_str)
            
            # Should be detected as network/cloud
            is_network, reason = is_network_or_cloud_path(path)
            assert is_network, f"Path should be detected as network/cloud: {path_str}"
            
            # Should get safe relocation
            safe_location, is_relocated, explanation = get_sqlite_safe_location(path)
            assert is_relocated, f"Path should be relocated: {path_str}"
            assert "/tmp/" in str(safe_location), f"Should use temp location: {path_str}"


if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__])