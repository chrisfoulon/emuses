"""
Network drive detection utilities for EMUSES.

This module provides utilities to detect when paths are on network drives
or cloud storage that may not be compatible with SQLite file locking.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

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
        ("Dropbox", "Dropbox cloud storage"),
        ("OneDrive", "Microsoft OneDrive"),
        ("Google Drive", "Google Drive"),
        ("iCloud", "Apple iCloud"),
        ("Box Sync", "Box cloud storage"),
        ("pCloud", "pCloud storage"),
        ("MEGA", "MEGA cloud storage"),
    ]

    for pattern, description in cloud_patterns:
        if pattern in path_str:
            return True, description

    # Network drive patterns
    network_patterns = [
        ("/mnt/", "mounted network drive"),
        ("\\\\", "UNC network path"),
        ("/net/", "network filesystem"),
        ("/nfs/", "NFS network filesystem"),
        ("/cifs/", "CIFS network filesystem"),
        ("/smb/", "SMB network filesystem"),
    ]

    for pattern, description in network_patterns:
        if pattern in path_str:
            return True, description

    # Check for network filesystem types on Unix systems
    if os.name == "posix":
        try:
            # Check if the filesystem type indicates a network drive
            import subprocess

            result = subprocess.run(
                ["df", "-T", str(path)], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                output = result.stdout.lower()
                network_fs_types = ["nfs", "cifs", "smb", "fuse", "sshfs"]
                for fs_type in network_fs_types:
                    if fs_type in output:
                        return True, f"{fs_type.upper()} network filesystem"
        except (
            subprocess.TimeoutExpired,
            subprocess.SubprocessError,
            FileNotFoundError,
        ):
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
    temp_dir = Path(tempfile.mkdtemp(prefix="emuses_sqlite_"))

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


def setup_optuna_storage_with_cleanup_info(
    study_name: str, storage_path: Path
) -> Tuple[str, Optional[Path]]:
    """
    Create a safe Optuna storage URL and return cleanup information.

    This function is similar to setup_optuna_storage_safe but also returns
    the temporary location (if any) for later cleanup.

    Parameters
    ----------
    study_name : str
        Name for the Optuna study
    storage_path : Path
        Desired path for the storage

    Returns
    -------
    Tuple[str, Optional[Path]]
        (SQLite URL for Optuna storage, temp_location_for_cleanup)
        temp_location_for_cleanup is None if no temp location was used
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
    storage_url = f"sqlite:///{db_file}"

    # Return temp location for cleanup if relocated, otherwise None
    temp_location_for_cleanup = sqlite_location if is_relocated else None

    return storage_url, temp_location_for_cleanup


def cleanup_temp_sqlite_location(temp_location: Path, output_folder: Path) -> None:
    """
    Clean up temporary SQLite location and copy SQLite databases to output folder.

    This function preserves important SQLite database files by copying them to the
    output folder before cleaning up the temporary location. This ensures users
    retain access to optimization databases when using network drives.

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
        import shutil

        # List all files in temp directory
        temp_files = list(temp_location.glob("*"))
        sqlite_files = [f for f in temp_files if f.suffix == ".db"]

        if temp_files:
            logger.info(f"Cleaning up temporary SQLite location: {temp_location}")
            logger.info(f"Temporary files found: {[f.name for f in temp_files]}")

        # Copy SQLite database files to output folder
        if sqlite_files:
            # Create databases subdirectory in output folder
            db_output_dir = output_folder / "databases"
            db_output_dir.mkdir(parents=True, exist_ok=True)

            copied_files = []
            for db_file in sqlite_files:
                try:
                    dest_file = db_output_dir / db_file.name
                    shutil.copy2(db_file, dest_file)
                    copied_files.append(dest_file)
                    logger.info(
                        f"Copied SQLite database: {db_file.name} -> {dest_file}"
                    )
                except Exception as copy_error:
                    logger.warning(
                        f"Failed to copy SQLite file {db_file}: {copy_error}"
                    )

            if copied_files:
                print(f"\n📁 SQLite databases preserved in: {db_output_dir}")
                print(f"   Files copied: {[f.name for f in copied_files]}")
                print(f"   Original temp location was: {temp_location}")

        # Remove the temporary directory after copying
        shutil.rmtree(temp_location, ignore_errors=True)
        logger.info(f"Successfully cleaned up temporary location: {temp_location}")

    except Exception as e:
        logger.warning(
            f"Failed to clean up temporary SQLite location {temp_location}: {e}"
        )


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
        except Exception:
            pass

        return False, f"SQLite compatibility test failed: {e}"
