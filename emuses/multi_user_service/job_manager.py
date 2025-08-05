"""Multi-User Job Manager with user-scoped storage and ownership validation.

Extends the foundation JobManager with user workspace isolation, quota validation,
and secure user-scoped storage management for EMUSES multi-user environment.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from emuses.foundation_fastapi_service.job_manager import JobManager
from emuses.multi_user_service.quota_manager import QuotaManager


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
        self, base_directory: Union[str, Path], cleanup_after_days: float = 7.0
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
        self.quota_manager = QuotaManager()

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
        db_session: Optional[Session] = None,
        expected_storage_gb: float = 0.0,
        expected_compute_hours: float = 0.0,
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
        db_session : Optional[Session]
            Database session for quota validation
        expected_storage_gb : float
            Expected storage usage for quota validation
        expected_compute_hours : float
            Expected compute hours for quota validation

        Returns
        -------
        UUID
            Generated job ID

        Raises
        ------
        ValueError
            If user_id is invalid, configuration is invalid, or quota exceeded
        """
        if not isinstance(user_id, UUID):
            raise ValueError("user_id must be a UUID")

        # Validate quotas if database session provided
        if db_session is not None:
            # Check concurrent job limit
            concurrent_result = self.quota_manager.validate_concurrent_job_limit(
                db_session, user_id
            )
            if not concurrent_result.is_valid:
                raise ValueError(f"Quota exceeded: {concurrent_result.message}")

            # Check storage and compute quotas if specified
            if expected_storage_gb > 0 or expected_compute_hours > 0:
                if not self.quota_manager.is_quota_available(
                    db_session, user_id, expected_storage_gb, expected_compute_hours
                ):
                    quota_results = self.quota_manager.validate_all_quotas(
                        db_session, user_id, expected_storage_gb, expected_compute_hours
                    )
                    failed_quotas = [
                        name
                        for name, result in quota_results.items()
                        if not result.is_valid
                    ]
                    raise ValueError(f"Quota exceeded for: {', '.join(failed_quotas)}")

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
        expected_compute_hours: float = 0.0,
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
        offset: int = 0,
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
        return jobs[offset : offset + limit]

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
                job_id=job_id, status="cancelled", message="Job cancelled by user"
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
        storage_bytes_used: int = 0,
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
            "storage_bytes_used": total_storage,
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

    def start_job_tracking(
        self, job_id: UUID, user_id: UUID, db_session: Optional[Session] = None
    ) -> None:
        """Start tracking job execution time and resource usage.

        Parameters
        ----------
        job_id : UUID
            Job ID to start tracking for
        user_id : UUID
            User ID for ownership validation
        db_session : Optional[Session]
            Database session for updating job records
        """
        # Validate ownership
        if not self.validate_job_ownership(job_id, user_id):
            raise ValueError("User not authorized to track this job")

        # Record start time in job metadata
        start_metadata = {
            "tracking_started_at": datetime.utcnow().isoformat(),
            "resource_tracking_enabled": True,
        }

        # Temporarily update jobs_directory for compatibility
        user_storage = self.base_directory / "users" / str(user_id) / "jobs"
        original_jobs_dir = self.jobs_directory
        self.jobs_directory = user_storage

        try:
            self.update_job_metadata(job_id, start_metadata)
            self.add_job_log(job_id, "Started resource usage tracking", "INFO")
        finally:
            self.jobs_directory = original_jobs_dir

    def update_job_resource_usage(
        self,
        job_id: UUID,
        user_id: UUID,
        compute_hours_delta: float = 0.0,
        storage_bytes_delta: int = 0,
        db_session: Optional[Session] = None,
    ) -> None:
        """Update job's resource usage and sync with user quotas.

        Parameters
        ----------
        job_id : UUID
            Job ID to update usage for
        user_id : UUID
            User ID for ownership validation
        compute_hours_delta : float
            Change in compute hours used
        storage_bytes_delta : int
            Change in storage bytes used
        db_session : Optional[Session]
            Database session for updating user quotas
        """
        # Validate ownership
        if not self.validate_job_ownership(job_id, user_id):
            raise ValueError("User not authorized to update this job")

        # Update job-level resource tracking
        self.update_user_resource_usage(
            job_id, user_id, compute_hours_delta, storage_bytes_delta
        )

        # Update user-level quotas if database session provided
        if db_session is not None:
            # Convert bytes to GB for storage quota update
            storage_gb_delta = storage_bytes_delta / (1024**3)

            if compute_hours_delta != 0:
                self.quota_manager.update_user_compute_usage(
                    db_session, user_id, compute_hours_delta
                )

            if storage_gb_delta != 0:
                self.quota_manager.update_user_storage_usage(
                    db_session, user_id, storage_gb_delta
                )

    def complete_job_tracking(
        self,
        job_id: UUID,
        user_id: UUID,
        final_compute_hours: float,
        final_storage_bytes: int,
        db_session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Complete job tracking and finalize resource usage.

        Parameters
        ----------
        job_id : UUID
            Job ID to complete tracking for
        user_id : UUID
            User ID for ownership validation
        final_compute_hours : float
            Final compute hours used by job
        final_storage_bytes : int
            Final storage bytes used by job
        db_session : Optional[Session]
            Database session for updating user quotas

        Returns
        -------
        Dict[str, Any]
            Resource usage summary
        """
        # Validate ownership
        if not self.validate_job_ownership(job_id, user_id):
            raise ValueError("User not authorized to complete tracking for this job")

        # Get current metadata to calculate deltas
        current_metadata = self.get_user_job_metadata(job_id, user_id)
        current_compute = current_metadata.get("compute_hours_used", 0.0)
        current_storage = current_metadata.get("storage_bytes_used", 0)

        # Calculate deltas
        compute_delta = final_compute_hours - current_compute
        storage_delta = final_storage_bytes - current_storage

        # Update resource usage
        completion_metadata = {
            "tracking_completed_at": datetime.utcnow().isoformat(),
            "compute_hours_used": final_compute_hours,
            "storage_bytes_used": final_storage_bytes,
            "resource_tracking_completed": True,
        }

        # Temporarily update jobs_directory for compatibility
        user_storage = self.base_directory / "users" / str(user_id) / "jobs"
        original_jobs_dir = self.jobs_directory
        self.jobs_directory = user_storage

        try:
            self.update_job_metadata(job_id, completion_metadata)
            self.add_job_log(
                job_id,
                f"Completed tracking: {final_compute_hours:.2f}h compute, "
                f"{final_storage_bytes / (1024**3):.2f}GB storage",
                "INFO",
            )
        finally:
            self.jobs_directory = original_jobs_dir

        # Update user-level quotas
        if db_session is not None and (compute_delta != 0 or storage_delta != 0):
            self.update_job_resource_usage(
                job_id, user_id, compute_delta, storage_delta, db_session
            )

        # Return usage summary
        return {
            "job_id": str(job_id),
            "user_id": str(user_id),
            "compute_hours_used": final_compute_hours,
            "storage_bytes_used": final_storage_bytes,
            "compute_hours_delta": compute_delta,
            "storage_bytes_delta": storage_delta,
            "tracking_completed": True,
        }

    def get_job_resource_usage(self, job_id: UUID, user_id: UUID) -> Dict[str, Any]:
        """Get current resource usage for a job.

        Parameters
        ----------
        job_id : UUID
            Job ID to get usage for
        user_id : UUID
            User ID for ownership validation

        Returns
        -------
        Dict[str, Any]
            Current resource usage information
        """
        # Validate ownership
        if not self.validate_job_ownership(job_id, user_id):
            raise ValueError("User not authorized to access this job")

        metadata = self.get_user_job_metadata(job_id, user_id)

        return {
            "job_id": str(job_id),
            "compute_hours_used": metadata.get("compute_hours_used", 0.0),
            "storage_bytes_used": metadata.get("storage_bytes_used", 0),
            "tracking_started": metadata.get("tracking_started_at"),
            "tracking_completed": metadata.get("tracking_completed_at"),
            "tracking_enabled": metadata.get("resource_tracking_enabled", False),
            "tracking_status": (
                "completed"
                if metadata.get("resource_tracking_completed")
                else (
                    "active"
                    if metadata.get("resource_tracking_enabled")
                    else "inactive"
                )
            ),
        }
