"""
Network drive detection utilities for EMUSES.

This module provides utilities to detect when paths are on network drives
or cloud storage that may not be compatible with SQLite file locking.
"""

import os
import tempfile
from pathlib import Path
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def is_network_or_cloud_path(path: Path) -> Tuple[bool, str]:
    """
    Detect if a path is on a network drive or cloud storage.
    
    This function identifies paths that may have issues with SQLite
    file locking and journaling.
    
    Parameters
    ----------
    path : Path
        The path to check
        
    Returns
    -------
    Tuple[bool, str]
        (is_network_path, reason_description)
    """
    path_str = str(path.resolve())
    
    # Common cloud storage patterns
    cloud_patterns = [
        ('Dropbox', 'Dropbox cloud storage'),
        ('OneDrive', 'Microsoft OneDrive'),
        ('Google Drive', 'Google Drive'),
        ('iCloud', 'Apple iCloud'),
        ('Box Sync', 'Box cloud storage'),
        ('pCloud', 'pCloud storage'),
        ('MEGA', 'MEGA cloud storage'),
    ]
    
    for pattern, description in cloud_patterns:
        if pattern in path_str:
            return True, description
    
    # Network drive patterns
    network_patterns = [
        ('/mnt/', 'mounted network drive'),
        ('\\\\', 'UNC network path'),
        ('/net/', 'network filesystem'),
        ('/nfs/', 'NFS network filesystem'),
        ('/cifs/', 'CIFS network filesystem'),
        ('/smb/', 'SMB network filesystem'),
    ]
    
    for pattern, description in network_patterns:
        if pattern in path_str:
            return True, description
    
    # Check for network filesystem types on Unix systems
    if os.name == 'posix':
        try:
            # Check if the filesystem type indicates a network drive
            import subprocess
            result = subprocess.run(['df', '-T', str(path)], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output = result.stdout.lower()
                network_fs_types = ['nfs', 'cifs', 'smb', 'fuse', 'sshfs']
                for fs_type in network_fs_types:
                    if fs_type in output:
                        return True, f'{fs_type.upper()} network filesystem'
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            # df command failed or not available, continue with other checks
            pass
    
    return False, ""


def get_sqlite_safe_location(output_folder: Path) -> Tuple[Path, bool, str]:
    """
    Get a safe location for SQLite databases.
    
    If the output folder is on a network drive, returns a local temp location.
    Otherwise, returns the output folder itself.
    
    Parameters
    ----------
    output_folder : Path
        The desired output folder for the pipeline
        
    Returns
    -------
    Tuple[Path, bool, str]
        (sqlite_location, is_relocated, explanation)
    """
    is_network, reason = is_network_or_cloud_path(output_folder)
    
    if not is_network:
        # Safe to use the output folder directly
        return output_folder, False, ""
    
    # Create a local temp directory for SQLite databases
    temp_dir = Path(tempfile.mkdtemp(prefix='emuses_sqlite_'))
    
    explanation = (
        f"Output folder is on {reason}, which may not support SQLite file locking. "
        f"Using local storage ({temp_dir}) for optimization databases. "
        f"Results will still be saved to the output folder."
    )
    
    logger.warning(explanation)
    
    return temp_dir, True, explanation


def setup_optuna_storage_safe(study_name: str, storage_path: Path) -> str:
    """
    Create a safe Optuna storage URL.
    
    Uses the provided path if it's safe for SQLite, otherwise uses
    a local temporary location.
    
    Parameters
    ----------
    study_name : str
        Name for the Optuna study
    storage_path : Path
        Desired path for the storage
        
    Returns
    -------
    str
        SQLite URL for Optuna storage
    """
    sqlite_location, is_relocated, explanation = get_sqlite_safe_location(storage_path)
    
    if is_relocated:
        print(f"⚠️  {explanation}")
        print(f"📁 Optimization database: {sqlite_location}")
        print(f"📁 Results will be saved to: {storage_path}")
    
    # Ensure the directory exists
    sqlite_location.mkdir(parents=True, exist_ok=True)
    
    # Create the SQLite URL
    db_file = sqlite_location / f"{study_name}.db"
    return f"sqlite:///{db_file}"


def cleanup_temp_sqlite_location(temp_location: Path, output_folder: Path) -> None:
    """
    Clean up temporary SQLite location and optionally copy results.
    
    Parameters
    ----------
    temp_location : Path
        The temporary SQLite location to clean up
    output_folder : Path
        The final output folder where results should be saved
    """
    if not temp_location.exists():
        return
    
    try:
        # Copy any important files to the output folder
        # (Optuna databases are typically not needed after completion)
        
        # List what was in the temp directory for debugging
        temp_files = list(temp_location.glob("*"))
        if temp_files:
            logger.info(f"Cleaning up temporary SQLite location: {temp_location}")
            logger.info(f"Temporary files created: {[f.name for f in temp_files]}")
        
        # Remove the temporary directory
        import shutil
        shutil.rmtree(temp_location, ignore_errors=True)
        
    except Exception as e:
        logger.warning(f"Failed to clean up temporary SQLite location {temp_location}: {e}")


def validate_sqlite_compatibility(path: Path) -> Tuple[bool, str]:
    """
    Test if a path supports SQLite operations.
    
    Performs a quick test to see if SQLite file locking works correctly.
    
    Parameters
    ----------
    path : Path
        Path to test
        
    Returns
    -------
    Tuple[bool, str]
        (is_compatible, error_message_if_not)
    """
    try:
        import sqlite3
        import tempfile
        
        # Create a test database
        test_db = path / "test_sqlite_compat.db"
        
        # Ensure directory exists
        path.mkdir(parents=True, exist_ok=True)
        
        # Test basic SQLite operations
        conn = sqlite3.connect(str(test_db))
        cursor = conn.cursor()
        
        # Test table creation and insertion
        cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)")
        cursor.execute("INSERT INTO test (data) VALUES (?)", ("test_data",))
        conn.commit()
        
        # Test reading
        cursor.execute("SELECT data FROM test WHERE id = 1")
        result = cursor.fetchone()
        
        conn.close()
        
        # Clean up test file
        test_db.unlink(missing_ok=True)
        
        if result and result[0] == "test_data":
            return True, ""
        else:
            return False, "SQLite test failed to read data correctly"
            
    except Exception as e:
        # Clean up test file if it exists
        try:
            test_db.unlink(missing_ok=True)
        except:
            pass
        
        return False, f"SQLite compatibility test failed: {e}"