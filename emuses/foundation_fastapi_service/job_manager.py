"""Job Manager for Foundation FastAPI Service.

This module provides job lifecycle management functionality including:
- Secure UUID generation with entropy validation
- Job directory structure creation with path traversal protection
- Job status persistence and updates with concurrency locks
- Job metadata tracking with sanitization and cleanup policies
"""

import json
import threading
import time
import re
import html
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from uuid import uuid4, UUID
from datetime import datetime, timedelta
import fcntl
import os


class JobManager:
    """Manages job lifecycle including creation, status tracking, and cleanup."""

    def __init__(self, base_directory: Union[str, Path], cleanup_after_days: float = 7.0):
        """Initialize job manager with base directory and cleanup policy.

        Args:
            base_directory: Base directory for job storage
            cleanup_after_days: Days after which completed jobs are cleaned up
        """
        self.base_directory = Path(base_directory)
        self.jobs_directory = self.base_directory / "jobs"
        self.cleanup_after_days = cleanup_after_days
        self._status_locks = {}
        self._locks_lock = threading.Lock()

        # Create base directories
        self.jobs_directory.mkdir(parents=True, exist_ok=True)

    def generate_job_id(self) -> UUID:
        """Generate a secure UUID4 for job identification.

        Returns:
            UUID: Cryptographically secure UUID4
        """
        return uuid4()

    def validate_job_id(self, job_id: Union[str, UUID, None]) -> bool:
        """Validate that a job ID is a valid UUID4.

        Args:
            job_id: Job ID to validate

        Returns:
            bool: True if valid UUID4, False otherwise
        """
        if job_id is None:
            return False

        try:
            if isinstance(job_id, str):
                if not job_id.strip():
                    return False
                uuid_obj = UUID(job_id)
            elif isinstance(job_id, UUID):
                uuid_obj = job_id
            else:
                return False

            # Ensure it's a valid UUID4
            return uuid_obj.version == 4
        except (ValueError, TypeError):
            return False

    def create_job_directory(self, job_id: Union[str, UUID]) -> Path:
        """Create job directory structure with path traversal protection.

        Args:
            job_id: Job ID for directory creation

        Returns:
            Path: Path to created job directory

        Raises:
            ValueError: If job_id is invalid or contains path traversal
        """
        # Validate job ID
        if not self.validate_job_id(job_id):
            raise ValueError("Invalid job ID")

        # Convert to string and check for path traversal
        job_id_str = str(job_id)

        # Check for path traversal attempts
        if (
            ".." in job_id_str or
            "/" in job_id_str or
            "\\" in job_id_str or
            ":" in job_id_str or
            any(ord(c) < 32 for c in job_id_str)  # Control characters
        ):
            raise ValueError("Invalid job ID: contains illegal characters")

        # Create job directory
        job_dir = self.jobs_directory / job_id_str
        job_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (job_dir / "input").mkdir(exist_ok=True)
        (job_dir / "output").mkdir(exist_ok=True)
        (job_dir / "logs").mkdir(exist_ok=True)

        # Set proper permissions (owner read/write/execute only)
        job_dir.chmod(0o700)
        (job_dir / "input").chmod(0o700)
        (job_dir / "output").chmod(0o700)
        (job_dir / "logs").chmod(0o700)

        return job_dir

    def _get_status_lock(self, job_id: Union[str, UUID]) -> threading.Lock:
        """Get or create a lock for job status updates.

        Args:
            job_id: Job ID to get lock for

        Returns:
            threading.Lock: Lock for this job
        """
        job_id_str = str(job_id)

        with self._locks_lock:
            if job_id_str not in self._status_locks:
                self._status_locks[job_id_str] = threading.Lock()
            return self._status_locks[job_id_str]

    def update_job_status(
        self,
        job_id: Union[str, UUID],
        status: str,
        progress: Optional[float] = None,
        current_stage: Optional[str] = None,
        message: Optional[str] = None
    ) -> None:
        """Update job status with concurrency protection.

        Args:
            job_id: Job ID to update
            status: New status
            progress: Optional progress value (0.0 to 1.0)
            current_stage: Optional current stage name
            message: Optional status message

        Raises:
            ValueError: If job doesn't exist
        """
        if not self.job_exists(job_id):
            raise ValueError("Job not found")

        job_id_str = str(job_id)
        status_lock = self._get_status_lock(job_id)

        with status_lock:
            job_dir = self.jobs_directory / job_id_str
            metadata_file = job_dir / "metadata.json"

            # Read existing metadata
            metadata = {}
            if metadata_file.exists():
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)

            # Update status information
            metadata.update({
                "job_id": job_id_str,
                "status": status,
                "updated_at": datetime.now().isoformat()
            })

            if progress is not None:
                metadata["progress"] = progress
            if current_stage is not None:
                metadata["current_stage"] = current_stage
            if message is not None:
                metadata["message"] = message

            # Set timestamps based on status
            if status == "RUNNING" and "started_at" not in metadata:
                metadata["started_at"] = datetime.now().isoformat()
            elif status in ["COMPLETED", "FAILED", "CANCELLED"]:
                metadata["completed_at"] = datetime.now().isoformat()

            # Write atomically using file locking
            temp_file = metadata_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(metadata, f, indent=2)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Atomic rename
            temp_file.replace(metadata_file)

    def get_job_status(self, job_id: Union[str, UUID]) -> Dict[str, Any]:
        """Get current job status.

        Args:
            job_id: Job ID to get status for

        Returns:
            Dict: Job status information

        Raises:
            ValueError: If job doesn't exist
        """
        if not self.job_exists(job_id):
            raise ValueError("Job not found")

        job_id_str = str(job_id)
        job_dir = self.jobs_directory / job_id_str
        metadata_file = job_dir / "metadata.json"

        if not metadata_file.exists():
            # Return minimal status if no metadata file
            return {
                "job_id": job_id_str,
                "status": "UNKNOWN",
                "created_at": datetime.now().isoformat()
            }

        with open(metadata_file, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            metadata = json.load(f)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        return metadata

    def job_exists(self, job_id: Union[str, UUID]) -> bool:
        """Check if a job directory exists.

        Args:
            job_id: Job ID to check

        Returns:
            bool: True if job exists, False otherwise
        """
        if not self.validate_job_id(job_id):
            return False

        job_id_str = str(job_id)
        job_dir = self.jobs_directory / job_id_str
        return job_dir.exists() and job_dir.is_dir()

    def _sanitize_metadata_value(self, value: Any) -> Any:
        """Sanitize metadata values to prevent XSS and other attacks.

        Args:
            value: Value to sanitize

        Returns:
            Any: Sanitized value
        """
        if isinstance(value, str):
            # Remove null bytes and control characters
            value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)

            # HTML escape to prevent XSS
            value = html.escape(value)

            # Remove path traversal attempts
            value = value.replace("../", "").replace("..\\", "")

            return value
        elif isinstance(value, dict):
            return {k: self._sanitize_metadata_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._sanitize_metadata_value(v) for v in value]
        else:
            return value

    def update_job_metadata(self, job_id: Union[str, UUID], metadata: Dict[str, Any]) -> None:
        """Update job metadata with sanitization.

        Args:
            job_id: Job ID to update metadata for
            metadata: Metadata dictionary to update

        Raises:
            ValueError: If job doesn't exist
        """
        if not self.job_exists(job_id):
            raise ValueError("Job not found")

        job_id_str = str(job_id)
        status_lock = self._get_status_lock(job_id)

        with status_lock:
            job_dir = self.jobs_directory / job_id_str
            metadata_file = job_dir / "metadata.json"

            # Read existing metadata
            existing_metadata = {}
            if metadata_file.exists():
                with open(metadata_file, "r") as f:
                    existing_metadata = json.load(f)

            # Sanitize new metadata
            sanitized_metadata = self._sanitize_metadata_value(metadata)

            # Merge with existing metadata
            existing_metadata.update(sanitized_metadata)
            existing_metadata["updated_at"] = datetime.now().isoformat()

            # Write atomically
            temp_file = metadata_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(existing_metadata, f, indent=2)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            temp_file.replace(metadata_file)

    def get_job_metadata(self, job_id: Union[str, UUID]) -> Dict[str, Any]:
        """Get job metadata.

        Args:
            job_id: Job ID to get metadata for

        Returns:
            Dict: Job metadata

        Raises:
            ValueError: If job doesn't exist
        """
        if not self.job_exists(job_id):
            raise ValueError("Job not found")

        job_id_str = str(job_id)
        job_dir = self.jobs_directory / job_id_str
        metadata_file = job_dir / "metadata.json"

        if not metadata_file.exists():
            return {"job_id": job_id_str}

        with open(metadata_file, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            metadata = json.load(f)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        return metadata

    def cleanup_old_jobs(self) -> List[UUID]:
        """Clean up old completed jobs based on cleanup policy.

        Returns:
            List[UUID]: List of cleaned up job IDs
        """
        if self.cleanup_after_days <= 0:
            return []

        cutoff_time = datetime.now() - timedelta(days=self.cleanup_after_days)
        cleaned_jobs = []

        for job_dir in self.jobs_directory.iterdir():
            if not job_dir.is_dir():
                continue

            try:
                job_id = UUID(job_dir.name)
                metadata = self.get_job_metadata(job_id)

                # Check if job is completed and old enough
                if (
                    metadata.get("status") in ["COMPLETED", "FAILED", "CANCELLED"] and
                    "completed_at" in metadata
                ):
                    completed_at = datetime.fromisoformat(metadata["completed_at"])
                    if completed_at < cutoff_time:
                        # Remove job directory
                        import shutil
                        shutil.rmtree(job_dir)
                        cleaned_jobs.append(job_id)

                        # Clean up locks
                        with self._locks_lock:
                            self._status_locks.pop(str(job_id), None)

            except (ValueError, TypeError):
                # Skip invalid job directories
                continue

        return cleaned_jobs
