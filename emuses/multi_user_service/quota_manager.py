"""Quota management system for multi-user EMUSES service.

Provides quota validation, usage tracking, and enforcement for user resources
including concurrent jobs, storage quotas, and compute hour limits.
"""

from typing import Dict, Any, List, Optional, NamedTuple
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from emuses.multi_user_service.models import User, TrainingJob


class QuotaValidationResult(NamedTuple):
    """Result of quota validation check.
    
    Attributes
    ----------
    is_valid : bool
        Whether the quota check passed
    current_usage : float
        Current usage amount
    limit : float
        Quota limit
    message : str
        Human-readable validation message
    """
    is_valid: bool
    current_usage: float
    limit: float
    message: str


class ConcurrentJobValidationResult(NamedTuple):
    """Result of concurrent job limit validation.
    
    Attributes
    ----------
    is_valid : bool
        Whether the concurrent job limit check passed
    current_jobs : int
        Current number of active jobs
    limit : int
        Concurrent job limit
    message : str
        Human-readable validation message
    """
    is_valid: bool
    current_jobs: int
    limit: int
    message: str


class QuotaManager:
    """Quota management system for user resource limits.
    
    Handles validation and tracking of user quotas including concurrent jobs,
    storage limits, and compute hour allocations.
    """

    def __init__(self):
        """Initialize quota manager with default configurations."""
        self.default_concurrent_job_limit = 5
        self.active_job_statuses = {"pending", "running"}

    def get_active_job_statuses(self) -> set:
        """Get set of job statuses considered active for quota purposes.
        
        Returns
        -------
        set
            Set of status strings that count as active jobs
        """
        return self.active_job_statuses.copy()

    def get_user_concurrent_jobs_count(self, db: Session, user_id: UUID) -> int:
        """Get current count of active jobs for a user.
        
        Parameters
        ----------
        db : Session
            Database session
        user_id : UUID
            User ID to check jobs for
        
        Returns
        -------
        int
            Number of active jobs for the user
        """
        return db.query(TrainingJob).filter(
            TrainingJob.owner_id == user_id,
            TrainingJob.status.in_(self.active_job_statuses)
        ).count()

    def validate_concurrent_job_limit(
        self, 
        db: Session, 
        user_id: UUID, 
        limit: Optional[int] = None
    ) -> ConcurrentJobValidationResult:
        """Validate user's concurrent job limit.
        
        Parameters
        ----------
        db : Session
            Database session
        user_id : UUID
            User ID to validate quota for
        limit : Optional[int]
            Custom concurrent job limit (uses default if None)
        
        Returns
        -------
        ConcurrentJobValidationResult
            Validation result with current usage and status
        """
        if limit is None:
            limit = self.default_concurrent_job_limit
        
        current_jobs = self.get_user_concurrent_jobs_count(db, user_id)
        is_valid = current_jobs < limit
        
        if is_valid:
            message = f"Concurrent jobs ({current_jobs}/{limit}) within limit"
        else:
            message = f"User has reached maximum concurrent jobs ({current_jobs}/{limit})"
        
        return ConcurrentJobValidationResult(
            is_valid=is_valid,
            current_jobs=current_jobs,
            limit=limit,
            message=message
        )

    def get_user_storage_usage(self, db: Session, user_id: UUID) -> Dict[str, float]:
        """Get user's current storage usage.
        
        Parameters
        ----------
        db : Session
            Database session
        user_id : UUID
            User ID to get storage usage for
        
        Returns
        -------
        Dict[str, float]
            Dictionary with storage usage information
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {
                "used_gb": 0.0,
                "quota_gb": 0.0,
                "percentage": 0.0
            }
        
        percentage = (user.storage_used_gb / user.storage_quota_gb * 100) if user.storage_quota_gb > 0 else 0.0
        
        return {
            "used_gb": user.storage_used_gb,
            "quota_gb": user.storage_quota_gb,
            "percentage": percentage
        }

    def validate_storage_quota(
        self, 
        db: Session, 
        user_id: UUID, 
        additional_gb: float = 0.0
    ) -> QuotaValidationResult:
        """Validate user's storage quota for additional usage.
        
        Parameters
        ----------
        db : Session
            Database session
        user_id : UUID
            User ID to validate quota for
        additional_gb : float
            Additional storage in GB to check against quota
        
        Returns
        -------
        QuotaValidationResult
            Validation result with current usage and status
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return QuotaValidationResult(
                is_valid=False,
                current_usage=0.0,
                limit=0.0,
                message="User not found"
            )
        
        projected_usage = user.storage_used_gb + additional_gb
        is_valid = projected_usage <= user.storage_quota_gb
        
        if is_valid:
            message = f"Storage usage ({projected_usage:.2f}/{user.storage_quota_gb:.2f} GB) within quota"
        else:
            message = f"Storage quota exceeded ({projected_usage:.2f}/{user.storage_quota_gb:.2f} GB)"
        
        return QuotaValidationResult(
            is_valid=is_valid,
            current_usage=projected_usage,
            limit=user.storage_quota_gb,
            message=message
        )

    def get_user_compute_usage(self, db: Session, user_id: UUID) -> Dict[str, float]:
        """Get user's current compute hour usage.
        
        Parameters
        ----------
        db : Session
            Database session
        user_id : UUID
            User ID to get compute usage for
        
        Returns
        -------
        Dict[str, float]
            Dictionary with compute usage information
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {
                "used_hours": 0.0,
                "quota_hours": 0.0,
                "percentage": 0.0
            }
        
        percentage = (user.compute_used_hours / user.compute_quota_hours * 100) if user.compute_quota_hours > 0 else 0.0
        
        return {
            "used_hours": user.compute_used_hours,
            "quota_hours": user.compute_quota_hours,
            "percentage": percentage
        }

    def validate_compute_quota(
        self, 
        db: Session, 
        user_id: UUID, 
        additional_hours: float = 0.0
    ) -> QuotaValidationResult:
        """Validate user's compute quota for additional usage.
        
        Parameters
        ----------
        db : Session
            Database session
        user_id : UUID
            User ID to validate quota for
        additional_hours : float
            Additional compute hours to check against quota
        
        Returns
        -------
        QuotaValidationResult
            Validation result with current usage and status
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return QuotaValidationResult(
                is_valid=False,
                current_usage=0.0,
                limit=0.0,
                message="User not found"
            )
        
        projected_usage = user.compute_used_hours + additional_hours
        is_valid = projected_usage <= user.compute_quota_hours
        
        if is_valid:
            message = f"Compute usage ({projected_usage:.2f}/{user.compute_quota_hours:.2f} hours) within quota"
        else:
            message = f"Compute quota exceeded ({projected_usage:.2f}/{user.compute_quota_hours:.2f} hours)"
        
        return QuotaValidationResult(
            is_valid=is_valid,
            current_usage=projected_usage,
            limit=user.compute_quota_hours,
            message=message
        )

    def validate_all_quotas(
        self, 
        db: Session, 
        user_id: UUID,
        additional_storage_gb: float = 0.0,
        additional_compute_hours: float = 0.0
    ) -> Dict[str, QuotaValidationResult]:
        """Validate all user quotas at once.
        
        Parameters
        ----------
        db : Session
            Database session
        user_id : UUID
            User ID to validate quotas for
        additional_storage_gb : float
            Additional storage in GB to check
        additional_compute_hours : float
            Additional compute hours to check
        
        Returns
        -------
        Dict[str, QuotaValidationResult]
            Dictionary with validation results for each quota type
        """
        concurrent_result = self.validate_concurrent_job_limit(db, user_id)
        storage_result = self.validate_storage_quota(db, user_id, additional_storage_gb)
        compute_result = self.validate_compute_quota(db, user_id, additional_compute_hours)
        
        return {
            "concurrent_jobs": concurrent_result,
            "storage": storage_result,
            "compute": compute_result
        }

    def is_quota_available(
        self, 
        db: Session, 
        user_id: UUID,
        additional_storage_gb: float = 0.0,
        additional_compute_hours: float = 0.0
    ) -> bool:
        """Check if user has quota available for resource allocation.
        
        Parameters
        ----------
        db : Session
            Database session
        user_id : UUID
            User ID to check quotas for
        additional_storage_gb : float
            Additional storage in GB to check
        additional_compute_hours : float
            Additional compute hours to check
        
        Returns
        -------
        bool
            True if all quotas allow the additional usage, False otherwise
        """
        results = self.validate_all_quotas(
            db, user_id, additional_storage_gb, additional_compute_hours
        )
        
        return all(result.is_valid for result in results.values())

    def update_user_storage_usage(
        self, 
        db: Session, 
        user_id: UUID, 
        storage_delta_gb: float
    ) -> bool:
        """Update user's storage usage by delta amount.
        
        Parameters
        ----------
        db : Session
            Database session
        user_id : UUID
            User ID to update usage for
        storage_delta_gb : float
            Change in storage usage (positive or negative)
        
        Returns
        -------
        bool
            True if update successful, False otherwise
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        # Prevent negative usage
        new_usage = max(0.0, user.storage_used_gb + storage_delta_gb)
        user.storage_used_gb = new_usage
        
        try:
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False

    def update_user_compute_usage(
        self, 
        db: Session, 
        user_id: UUID, 
        compute_delta_hours: float
    ) -> bool:
        """Update user's compute usage by delta amount.
        
        Parameters
        ----------
        db : Session
            Database session
        user_id : UUID
            User ID to update usage for
        compute_delta_hours : float
            Change in compute usage (positive or negative)
        
        Returns
        -------
        bool
            True if update successful, False otherwise
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        # Prevent negative usage
        new_usage = max(0.0, user.compute_used_hours + compute_delta_hours)
        user.compute_used_hours = new_usage
        
        try:
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False

    def get_user_quota_summary(self, db: Session, user_id: UUID) -> Dict[str, Any]:
        """Get complete quota summary for a user.
        
        Parameters
        ----------
        db : Session
            Database session
        user_id : UUID
            User ID to get quota summary for
        
        Returns
        -------
        Dict[str, Any]
            Complete quota usage and limit information
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}
        
        concurrent_jobs = self.get_user_concurrent_jobs_count(db, user_id)
        storage_info = self.get_user_storage_usage(db, user_id)
        compute_info = self.get_user_compute_usage(db, user_id)
        
        return {
            "user_id": str(user_id),
            "concurrent_jobs": {
                "current": concurrent_jobs,
                "limit": self.default_concurrent_job_limit,
                "percentage": (concurrent_jobs / self.default_concurrent_job_limit * 100)
            },
            "storage": storage_info,
            "compute": compute_info,
            "organization": user.organization,
            "role": user.role
        }

    def reset_user_usage(
        self, 
        db: Session, 
        user_id: UUID, 
        reset_storage: bool = True, 
        reset_compute: bool = True
    ) -> bool:
        """Reset user's usage counters to zero.
        
        Parameters
        ----------
        db : Session
            Database session
        user_id : UUID
            User ID to reset usage for
        reset_storage : bool
            Whether to reset storage usage
        reset_compute : bool
            Whether to reset compute usage
        
        Returns
        -------
        bool
            True if reset successful, False otherwise
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        try:
            if reset_storage:
                user.storage_used_gb = 0.0
            if reset_compute:
                user.compute_used_hours = 0.0
            
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False

    def reset_all_users_usage(
        self, 
        db: Session, 
        reset_storage: bool = True, 
        reset_compute: bool = True,
        organization_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reset usage counters for all users or users in specific organization.
        
        Parameters
        ----------
        db : Session
            Database session
        reset_storage : bool
            Whether to reset storage usage
        reset_compute : bool
            Whether to reset compute usage
        organization_filter : Optional[str]
            Only reset users in this organization (None for all users)
        
        Returns
        -------
        Dict[str, Any]
            Reset operation summary
        """
        query = db.query(User)
        if organization_filter:
            query = query.filter(User.organization == organization_filter)
        
        users = query.all()
        
        reset_count = 0
        failed_count = 0
        
        for user in users:
            try:
                if reset_storage:
                    user.storage_used_gb = 0.0
                if reset_compute:
                    user.compute_used_hours = 0.0
                reset_count += 1
            except Exception:
                failed_count += 1
                continue
        
        try:
            db.commit()
            return {
                "success": True,
                "users_processed": len(users),
                "users_reset": reset_count,
                "users_failed": failed_count,
                "reset_storage": reset_storage,
                "reset_compute": reset_compute,
                "organization_filter": organization_filter,
                "reset_timestamp": datetime.utcnow().isoformat()
            }
        except Exception:
            db.rollback()
            return {
                "success": False,
                "error": "Database transaction failed",
                "users_processed": len(users),
                "users_reset": 0,
                "users_failed": len(users)
            }

    def schedule_quota_reset(
        self, 
        db: Session, 
        reset_frequency_days: int = 30,
        reset_storage: bool = True,
        reset_compute: bool = True,
        organization_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Schedule automatic quota reset (for future implementation).
        
        This method provides the interface for scheduling regular quota resets.
        In a production system, this would integrate with a task scheduler like Celery.
        
        Parameters
        ----------
        db : Session
            Database session
        reset_frequency_days : int
            How often to reset quotas (in days)
        reset_storage : bool
            Whether to reset storage usage
        reset_compute : bool
            Whether to reset compute usage
        organization_filter : Optional[str]
            Only reset users in this organization
        
        Returns
        -------
        Dict[str, Any]
            Scheduling configuration
        """
        next_reset = datetime.utcnow() + timedelta(days=reset_frequency_days)
        
        # In a production system, this would create a scheduled task
        # For now, return the configuration that would be used
        return {
            "scheduled": True,
            "reset_frequency_days": reset_frequency_days,
            "next_reset_date": next_reset.isoformat(),
            "reset_storage": reset_storage,
            "reset_compute": reset_compute,
            "organization_filter": organization_filter,
            "note": "In production, this would integrate with task scheduler"
        }

    def get_users_near_quota_limit(
        self, 
        db: Session, 
        storage_threshold_percent: float = 90.0,
        compute_threshold_percent: float = 90.0
    ) -> List[Dict[str, Any]]:
        """Get list of users approaching their quota limits.
        
        Parameters
        ----------
        db : Session
            Database session
        storage_threshold_percent : float
            Storage usage percentage threshold
        compute_threshold_percent : float
            Compute usage percentage threshold
        
        Returns
        -------
        List[Dict[str, Any]]
            List of users near quota limits
        """
        users = db.query(User).all()
        near_limit_users = []
        
        for user in users:
            storage_percent = (user.storage_used_gb / user.storage_quota_gb * 100) if user.storage_quota_gb > 0 else 0
            compute_percent = (user.compute_used_hours / user.compute_quota_hours * 100) if user.compute_quota_hours > 0 else 0
            
            if storage_percent >= storage_threshold_percent or compute_percent >= compute_threshold_percent:
                near_limit_users.append({
                    "user_id": str(user.id),
                    "email": user.email,
                    "organization": user.organization,
                    "storage_percent": storage_percent,
                    "compute_percent": compute_percent,
                    "storage_usage": f"{user.storage_used_gb:.2f}/{user.storage_quota_gb:.2f} GB",
                    "compute_usage": f"{user.compute_used_hours:.2f}/{user.compute_quota_hours:.2f} hours",
                    "over_storage_limit": storage_percent >= storage_threshold_percent,
                    "over_compute_limit": compute_percent >= compute_threshold_percent
                })
        
        return near_limit_users