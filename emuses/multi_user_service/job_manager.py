"""Multi-User Job Manager with user-scoped storage and ownership validation.

Extends the foundation JobManager with user workspace isolation, quota validation,
and secure user-scoped storage management for EMUSES multi-user environment.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from uuid import UUID, uuid4
from emuses.foundation_fastapi_service.job_manager import JobManager


class MultiUserJobManager(JobManager):
    """Multi-user job manager with user workspace isolation.

    Extends the foundation JobManager to provide user-scoped storage,
    ownership validation, and quota management for multi-user environments.

    Attributes
    ----------
    base_directory : Path
        Base directory for all user storage
    cleanup_after_days : float
        Days after which completed jobs are cleaned up
    """

    def __init__(
        self,
        base_directory: Union[str, Path],
        cleanup_after_days: float = 7.0
    ):
        """Initialize multi-user job manager.

        Parameters
        ----------
        base_directory : Union[str, Path]
            Base directory for user storage
        cleanup_after_days : float
            Days after which completed jobs are cleaned up
        """
        super().__init__(base_directory, cleanup_after_days)

    def create_user_storage_path(self, user_id: UUID) -> Path:
        """Create user-isolated storage path with secure permissions.

        Parameters
        ----------
        user_id : UUID
            User ID for storage isolation

        Returns
        -------
        Path
            Path to user's storage directory

        Raises
        ------
        ValueError
            If user_id is invalid
        """
        if not isinstance(user_id, UUID):
            raise ValueError("user_id must be a UUID")

        # Create user-scoped storage path
        user_storage = self.base_directory / "users" / str(user_id) / "jobs"
        user_storage.mkdir(parents=True, exist_ok=True)

        # Set secure permissions (owner only)
        user_storage.chmod(0o700)
        if user_storage.parent.exists():
            user_storage.parent.chmod(0o700)

        return user_storage

    def create_user_job(
        self,
        user_id: UUID,
        config: Dict[str, Any],
        job_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> UUID:
        """Create a new job with user context and isolation.

        Parameters
        ----------
        user_id : UUID
            User ID for job ownership
        config : Dict[str, Any]
            Job configuration
        job_name : Optional[str]
            Human-readable job name
        description : Optional[str]
            Job description

        Returns
        -------
        UUID
            Generated job ID

        Raises
        ------
        ValueError
            If user_id is invalid or configuration is invalid
        """
        if not isinstance(user_id, UUID):
            raise ValueError("user_id must be a UUID")

        # Create user storage path
        user_storage = self.create_user_storage_path(user_id)

        # Generate job ID
        job_id = self.generate_job_id()

        # Create job directory in user space
        job_dir = user_storage / str(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories with secure permissions
        for subdir in ["input", "output", "logs"]:
            subdir_path = job_dir / subdir
            subdir_path.mkdir(exist_ok=True)
            subdir_path.chmod(0o700)

        job_dir.chmod(0o700)

        # Temporarily update jobs_directory for compatibility with parent methods
        original_jobs_dir = self.jobs_directory
        self.jobs_directory = user_storage

        try:
            # Initialize job status using parent class method
            self.update_job_status(
                job_id=job_id,
                status="submitted",
                message="Job submitted for processing",
                current_stage=None,
                progress=0.0,
            )

            # Save job metadata with user context
            metadata = {
                "user_id": str(user_id),
                "job_name": job_name,
                "description": description,
                "config": config,
            }
            self.update_job_metadata(job_id, metadata)

        finally:
            # Restore original jobs directory
            self.jobs_directory = original_jobs_dir

        return job_id

    def validate_job_ownership(self, job_id: UUID, user_id: UUID) -> bool:
        """Validate that a user owns a specific job.

        Parameters
        ----------
        job_id : UUID
            Job ID to check ownership for
        user_id : UUID
            User ID to validate ownership

        Returns
        -------
        bool
            True if user owns the job, False otherwise
        """
        if not isinstance(job_id, UUID) or not isinstance(user_id, UUID):
            return False

        try:
            user_storage = self.base_directory / "users" / str(user_id) / "jobs"
            job_dir = user_storage / str(job_id)

            # Check if job exists in user's storage
            if not job_dir.exists():
                return False

            # Check metadata for user ownership
            metadata_file = job_dir / "metadata.json"
            if metadata_file.exists():
                import json
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
                return metadata.get("user_id") == str(user_id)

            return True

        except Exception:
            return False

    def check_user_quota(
        self,
        user_id: UUID,
        expected_storage_gb: float = 0.0,
        expected_compute_hours: float = 0.0
    ) -> bool:
        """Check if user has sufficient quota for resource allocation.

        Parameters
        ----------
        user_id : UUID
            User ID to check quota for
        expected_storage_gb : float
            Expected storage usage in GB
        expected_compute_hours : float
            Expected compute hours usage

        Returns
        -------
        bool
            True if user has sufficient quota, False otherwise
        """
        # For now, return True (quota checking will be implemented with database integration)
        # TODO: Implement actual quota checking with user model integration
        return True

    def _get_user_job_dirs(self, user_storage: Path) -> List[Path]:
        """Get valid job directories for a user, sorted by creation time."""
        job_dirs = []
        for item in user_storage.iterdir():
            if item.is_dir():
                try:
                    UUID(item.name)  # Validate UUID format
                    job_dirs.append(item)
                except ValueError:
                    continue

        # Sort by creation time (newest first)
        job_dirs.sort(key=lambda x: x.stat().st_ctime, reverse=True)
        return job_dirs

    def _filter_user_jobs(
        self, job_dirs: List[Path], status: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Filter and create job info for user job directories."""
        jobs = []
        for job_dir in job_dirs:
            job_id = UUID(job_dir.name)
            job_info = self._create_job_info(job_id)

            if job_info is None:
                continue

            # Apply status filter
            if status and job_info.get("status") != status:
                continue

            jobs.append(job_info)
        return jobs

    def list_user_jobs(
        self,
        user_id: UUID,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List jobs for a specific user with filtering and pagination.

        Parameters
        ----------
        user_id : UUID
            User ID to list jobs for
        status : Optional[str]
            Optional status filter
        limit : int
            Maximum number of jobs to return
        offset : int
            Number of jobs to skip

        Returns
        -------
        List[Dict[str, Any]]
            List of user's job information
        """
        if not isinstance(user_id, UUID):
            return []

        user_storage = self.base_directory / "users" / str(user_id) / "jobs"
        if not user_storage.exists():
            return []

        # Get and sort job directories
        job_dirs = self._get_user_job_dirs(user_storage)

        # Temporarily update jobs_directory for compatibility
        original_jobs_dir = self.jobs_directory
        self.jobs_directory = user_storage

        try:
            jobs = self._filter_user_jobs(job_dirs, status)
        finally:
            self.jobs_directory = original_jobs_dir

        # Apply pagination
        return jobs[offset:offset + limit]

    def cancel_user_job(self, job_id: UUID, user_id: UUID) -> bool:
        """Cancel a user's job with ownership validation.

        Parameters
        ----------
        job_id : UUID
            Job ID to cancel
        user_id : UUID
            User ID for ownership validation

        Returns
        -------
        bool
            True if job was cancelled, False if already completed

        Raises
        ------
        ValueError
            If user is not authorized to cancel the job
        """
        # Validate ownership
        if not self.validate_job_ownership(job_id, user_id):
            raise ValueError("User not authorized to cancel this job")

        # Temporarily update jobs_directory for compatibility
        user_storage = self.base_directory / "users" / str(user_id) / "jobs"
        original_jobs_dir = self.jobs_directory
        self.jobs_directory = user_storage

        try:
            # Check if job is already completed
            current_status = self.get_job_status(job_id)
            if current_status["status"] in ["completed", "failed", "cancelled"]:
                return False

            # Update status to cancelled
            self.update_job_status(
                job_id=job_id,
                status="cancelled",
                message="Job cancelled by user"
            )

            self.add_job_log(job_id, "Job cancelled by user", "INFO")
            return True

        finally:
            self.jobs_directory = original_jobs_dir

    def get_user_job_metadata(self, job_id: UUID, user_id: UUID) -> Dict[str, Any]:
        """Get job metadata with user authorization.

        Parameters
        ----------
        job_id : UUID
            Job ID to get metadata for
        user_id : UUID
            User ID for authorization

        Returns
        -------
        Dict[str, Any]
            Job metadata

        Raises
        ------
        ValueError
            If user is not authorized to access the job
        """
        # Validate ownership
        if not self.validate_job_ownership(job_id, user_id):
            raise ValueError("User not authorized to access this job")

        # Temporarily update jobs_directory for compatibility
        user_storage = self.base_directory / "users" / str(user_id) / "jobs"
        original_jobs_dir = self.jobs_directory
        self.jobs_directory = user_storage

        try:
            return self.get_job_metadata(job_id)
        finally:
            self.jobs_directory = original_jobs_dir

    def update_user_resource_usage(
        self,
        job_id: UUID,
        user_id: UUID,
        compute_hours_used: float = 0.0,
        storage_bytes_used: int = 0
    ) -> None:
        """Update user resource usage for a job.

        Parameters
        ----------
        job_id : UUID
            Job ID to update usage for
        user_id : UUID
            User ID for ownership validation
        compute_hours_used : float
            Compute hours used
        storage_bytes_used : int
            Storage bytes used
        """
        # Validate ownership
        if not self.validate_job_ownership(job_id, user_id):
            raise ValueError("User not authorized to update this job")

        # Update job metadata with resource usage
        resource_metadata = {
            "compute_hours_used": compute_hours_used,
            "storage_bytes_used": storage_bytes_used,
        }

        # Temporarily update jobs_directory for compatibility
        user_storage = self.base_directory / "users" / str(user_id) / "jobs"
        original_jobs_dir = self.jobs_directory
        self.jobs_directory = user_storage

        try:
            self.update_job_metadata(job_id, resource_metadata)
        finally:
            self.jobs_directory = original_jobs_dir

    def get_user_resource_usage(self, user_id: UUID) -> Dict[str, float]:
        """Get aggregate resource usage for a user.

        Parameters
        ----------
        user_id : UUID
            User ID to get usage for

        Returns
        -------
        Dict[str, float]
            User's resource usage summary
        """
        user_storage = self.base_directory / "users" / str(user_id) / "jobs"
        if not user_storage.exists():
            return {"compute_hours_used": 0.0, "storage_bytes_used": 0}

        total_compute = 0.0
        total_storage = 0

        # Temporarily update jobs_directory for compatibility
        original_jobs_dir = self.jobs_directory
        self.jobs_directory = user_storage

        try:
            for item in user_storage.iterdir():
                if item.is_dir():
                    try:
                        job_id = UUID(item.name)
                        metadata = self.get_job_metadata(job_id)
                        total_compute += metadata.get("compute_hours_used", 0.0)
                        total_storage += metadata.get("storage_bytes_used", 0)
                    except Exception:
                        continue

        finally:
            self.jobs_directory = original_jobs_dir

        return {
            "compute_hours_used": total_compute,
            "storage_bytes_used": total_storage
        }

    def get_job_directory(self, job_id: Union[str, UUID]) -> Path:
        """Override to handle user-scoped job directories.

        This method attempts to find the job directory across all users
        for system-level operations.

        Parameters
        ----------
        job_id : Union[str, UUID]
            Job ID to get directory for

        Returns
        -------
        Path
            Path to job directory

        Raises
        ------
        ValueError
            If job not found
        """
        if not self.validate_job_id(job_id):
            raise ValueError("Invalid job ID")

        job_id_str = str(job_id)

        # Search in all user directories
        users_dir = self.base_directory / "users"
        if users_dir.exists():
            for user_dir in users_dir.iterdir():
                if user_dir.is_dir():
                    job_dir = user_dir / "jobs" / job_id_str
                    if job_dir.exists():
                        return job_dir

        # Fallback to original behavior
        return super().get_job_directory(job_id)

    def job_exists(self, job_id: Union[str, UUID]) -> bool:
        """Override to check job existence across all user directories.

        Parameters
        ----------
        job_id : Union[str, UUID]
            Job ID to check existence for

        Returns
        -------
        bool
            True if job exists in any user directory, False otherwise
        """
        if not self.validate_job_id(job_id):
            return False

        job_id_str = str(job_id)

        # Search in all user directories
        users_dir = self.base_directory / "users"
        if users_dir.exists():
            for user_dir in users_dir.iterdir():
                if user_dir.is_dir():
                    job_dir = user_dir / "jobs" / job_id_str
                    if job_dir.exists() and job_dir.is_dir():
                        return True

        # Fallback to original behavior
        return super().job_exists(job_id)

    def get_job_status(self, job_id: Union[str, UUID]) -> Dict[str, Any]:
        """Override to get job status from user directories.

        Parameters
        ----------
        job_id : Union[str, UUID]
            Job ID to get status for

        Returns
        -------
        Dict[str, Any]
            Job status information

        Raises
        ------
        ValueError
            If job not found
        """
        if not self.validate_job_id(job_id):
            raise ValueError("Invalid job ID")

        job_id_str = str(job_id)

        # Search in all user directories
        users_dir = self.base_directory / "users"
        if users_dir.exists():
            for user_dir in users_dir.iterdir():
                if user_dir.is_dir():
                    job_dir = user_dir / "jobs" / job_id_str
                    if job_dir.exists():
                        # Temporarily update jobs_directory for compatibility
                        original_jobs_dir = self.jobs_directory
                        self.jobs_directory = user_dir / "jobs"

                        try:
                            return super().get_job_status(job_id)
                        finally:
                            self.jobs_directory = original_jobs_dir

        # Fallback to original behavior
        return super().get_job_status(job_id)

    def add_job_log(
        self, job_id: Union[str, UUID], message: str, level: str = "INFO"
    ) -> None:
        """Override to add job log in user directories.

        Parameters
        ----------
        job_id : Union[str, UUID]
            Job ID to add log for
        message : str
            Log message
        level : str
            Log level (DEBUG, INFO, WARNING, ERROR)
        """
        if not self.validate_job_id(job_id):
            return

        job_id_str = str(job_id)

        # Search in all user directories
        users_dir = self.base_directory / "users"
        if users_dir.exists():
            for user_dir in users_dir.iterdir():
                if user_dir.is_dir():
                    job_dir = user_dir / "jobs" / job_id_str
                    if job_dir.exists():
                        # Temporarily update jobs_directory for compatibility
                        original_jobs_dir = self.jobs_directory
                        self.jobs_directory = user_dir / "jobs"

                        try:
                            super().add_job_log(job_id, message, level)
                            return
                        finally:
                            self.jobs_directory = original_jobs_dir

        # Fallback to original behavior
        super().add_job_log(job_id, message, level)
