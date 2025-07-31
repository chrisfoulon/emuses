"""Tests for quota management system functionality.

Tests quota validation logic, usage tracking, and quota management endpoints
for the multi-user EMUSES service.
"""

import pytest
from uuid import uuid4, UUID
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from emuses.multi_user_service.models import Base, User, TrainingJob, Workspace
from emuses.multi_user_service.quota_manager import QuotaManager
from emuses.multi_user_service.database import get_async_session
import asyncio
import tempfile
import os


@pytest.fixture
def test_db():
    """Create in-memory test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.fixture
def test_user(test_db):
    """Create test user with quotas."""
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        organization="Test Org",
        role="researcher",
        storage_quota_gb=10.0,
        compute_quota_hours=100.0,
        storage_used_gb=2.0,
        compute_used_hours=10.0
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_workspace(test_db, test_user):
    """Create test workspace."""
    workspace = Workspace(
        name="Test Workspace",
        description="Test workspace for quota tests",
        owner_id=test_user.id,
        storage_path=f"/tmp/test_{test_user.id}"
    )
    test_db.add(workspace)
    test_db.commit()
    test_db.refresh(workspace)
    return workspace


@pytest.fixture
def quota_manager():
    """Create quota manager instance."""
    return QuotaManager()


class TestConcurrentJobLimits:
    """Test concurrent job limit validation."""

    def test_validate_concurrent_job_limit_within_quota(self, test_db, test_user, test_workspace, quota_manager):
        """Test that job submission is allowed when under concurrent job limit."""
        # Create 2 running jobs (under default limit of 5)
        for i in range(2):
            job = TrainingJob(
                name=f"Running Job {i}",
                owner_id=test_user.id,
                workspace_id=test_workspace.id,
                status="running",
                job_config={"test": True}
            )
            test_db.add(job)
        test_db.commit()

        # Should allow new job submission
        result = quota_manager.validate_concurrent_job_limit(test_db, test_user.id)
        assert result.is_valid is True
        assert result.current_jobs == 2
        assert result.limit == 5
        assert "within limit" in result.message

    def test_validate_concurrent_job_limit_at_quota(self, test_db, test_user, test_workspace, quota_manager):
        """Test that job submission is blocked when at concurrent job limit."""
        # Create 5 running jobs (at default limit)
        for i in range(5):
            job = TrainingJob(
                name=f"Running Job {i}",
                owner_id=test_user.id,
                workspace_id=test_workspace.id,
                status="running",
                job_config={"test": True}
            )
            test_db.add(job)
        test_db.commit()

        # Should block new job submission
        result = quota_manager.validate_concurrent_job_limit(test_db, test_user.id)
        assert result.is_valid is False
        assert result.current_jobs == 5
        assert result.limit == 5
        assert "maximum concurrent jobs" in result.message

    def test_validate_concurrent_job_limit_only_counts_active_jobs(self, test_db, test_user, test_workspace, quota_manager):
        """Test that only active jobs count towards concurrent limit."""
        # Create jobs with different statuses
        active_statuses = ["pending", "running"]
        inactive_statuses = ["completed", "failed", "cancelled"]
        
        # Create 3 active jobs and 5 inactive jobs
        for i, status in enumerate(active_statuses * 2):  # 4 active jobs
            if i >= 3:  # Only create 3 active jobs
                break
            job = TrainingJob(
                name=f"Active Job {i}",
                owner_id=test_user.id,
                workspace_id=test_workspace.id,
                status=status,
                job_config={"test": True}
            )
            test_db.add(job)

        for i, status in enumerate(inactive_statuses):
            job = TrainingJob(
                name=f"Inactive Job {i}",
                owner_id=test_user.id,
                workspace_id=test_workspace.id,
                status=status,
                job_config={"test": True}
            )
            test_db.add(job)
        
        test_db.commit()

        # Should only count active jobs (3)
        result = quota_manager.validate_concurrent_job_limit(test_db, test_user.id)
        assert result.is_valid is True
        assert result.current_jobs == 3
        assert result.limit == 5

    def test_validate_concurrent_job_limit_user_specific(self, test_db, test_user, test_workspace, quota_manager):
        """Test that concurrent job limit is user-specific."""
        # Create another user
        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            organization="Other Org",
            role="researcher",
            storage_quota_gb=10.0,
            compute_quota_hours=100.0
        )
        test_db.add(other_user)
        test_db.commit()

        # Create workspace for other user
        other_workspace = Workspace(
            name="Other Workspace",
            owner_id=other_user.id,
            storage_path=f"/tmp/test_{other_user.id}"
        )
        test_db.add(other_workspace)
        test_db.commit()

        # Create 5 running jobs for test_user
        for i in range(5):
            job = TrainingJob(
                name=f"User1 Job {i}",
                owner_id=test_user.id,
                workspace_id=test_workspace.id,
                status="running",
                job_config={"test": True}
            )
            test_db.add(job)

        # Create 3 running jobs for other_user
        for i in range(3):
            job = TrainingJob(
                name=f"User2 Job {i}",
                owner_id=other_user.id,
                workspace_id=other_workspace.id,
                status="running",
                job_config={"test": True}
            )
            test_db.add(job)
        
        test_db.commit()

        # test_user should be at limit (5/5)
        result1 = quota_manager.validate_concurrent_job_limit(test_db, test_user.id)
        assert result1.is_valid is False
        assert result1.current_jobs == 5

        # other_user should be under limit (3/5)
        result2 = quota_manager.validate_concurrent_job_limit(test_db, other_user.id)
        assert result2.is_valid is True
        assert result2.current_jobs == 3

    def test_validate_concurrent_job_limit_custom_limit(self, test_db, test_user, test_workspace, quota_manager):
        """Test concurrent job validation with custom limit."""
        # Create 2 running jobs
        for i in range(2):
            job = TrainingJob(
                name=f"Running Job {i}",
                owner_id=test_user.id,
                workspace_id=test_workspace.id,
                status="running",
                job_config={"test": True}
            )
            test_db.add(job)
        test_db.commit()

        # Should be valid with limit of 5
        result1 = quota_manager.validate_concurrent_job_limit(test_db, test_user.id, limit=5)
        assert result1.is_valid is True

        # Should be invalid with limit of 2
        result2 = quota_manager.validate_concurrent_job_limit(test_db, test_user.id, limit=2)
        assert result2.is_valid is False

        # Should be valid with limit of 3
        result3 = quota_manager.validate_concurrent_job_limit(test_db, test_user.id, limit=3)
        assert result3.is_valid is True

    def test_get_user_concurrent_jobs_count(self, test_db, test_user, test_workspace, quota_manager):
        """Test getting current concurrent jobs count for user."""
        # Initially no jobs
        count = quota_manager.get_user_concurrent_jobs_count(test_db, test_user.id)
        assert count == 0

        # Create some jobs with mixed statuses
        statuses = ["pending", "running", "completed", "running", "failed"]
        for i, status in enumerate(statuses):
            job = TrainingJob(
                name=f"Job {i}",
                owner_id=test_user.id,
                workspace_id=test_workspace.id,
                status=status,
                job_config={"test": True}
            )
            test_db.add(job)
        test_db.commit()

        # Should count only pending and running jobs (3 total)
        count = quota_manager.get_user_concurrent_jobs_count(test_db, test_user.id)
        assert count == 3

    def test_get_active_job_statuses_configuration(self, quota_manager):
        """Test that active job statuses are properly configured."""
        active_statuses = quota_manager.get_active_job_statuses()
        
        # Should include pending and running
        assert "pending" in active_statuses
        assert "running" in active_statuses
        
        # Should not include completed statuses
        assert "completed" not in active_statuses
        assert "failed" not in active_statuses
        assert "cancelled" not in active_statuses
        
        # Should be a reasonable number of statuses
        assert len(active_statuses) >= 2
        assert len(active_statuses) <= 5


class TestStorageQuotas:
    """Test storage quota validation and tracking."""

    def test_validate_storage_quota_within_limit(self, test_db, test_user, quota_manager):
        """Test storage quota validation when within limits."""
        # User has 10GB quota, using 2GB, requesting 3GB more
        result = quota_manager.validate_storage_quota(test_db, test_user.id, additional_gb=3.0)
        
        assert result.is_valid is True
        assert result.current_usage == 5.0  # 2.0 + 3.0
        assert result.limit == 10.0
        assert "within quota" in result.message

    def test_validate_storage_quota_at_limit(self, test_db, test_user, quota_manager):
        """Test storage quota validation when exactly at limit."""
        # User has 10GB quota, using 2GB, requesting exactly 8GB more
        result = quota_manager.validate_storage_quota(test_db, test_user.id, additional_gb=8.0)
        
        assert result.is_valid is True
        assert result.current_usage == 10.0  # 2.0 + 8.0
        assert result.limit == 10.0

    def test_validate_storage_quota_over_limit(self, test_db, test_user, quota_manager):
        """Test storage quota validation when over limit."""
        # User has 10GB quota, using 2GB, requesting 9GB more (exceeds quota)
        result = quota_manager.validate_storage_quota(test_db, test_user.id, additional_gb=9.0)
        
        assert result.is_valid is False
        assert result.current_usage == 11.0  # 2.0 + 9.0
        assert result.limit == 10.0
        assert "quota exceeded" in result.message

    def test_validate_storage_quota_user_not_found(self, test_db, quota_manager):
        """Test storage quota validation with non-existent user."""
        non_existent_user_id = uuid4()
        result = quota_manager.validate_storage_quota(test_db, non_existent_user_id, additional_gb=1.0)
        
        assert result.is_valid is False
        assert result.current_usage == 0.0
        assert result.limit == 0.0
        assert "User not found" in result.message

    def test_get_user_storage_usage(self, test_db, test_user, quota_manager):
        """Test getting user storage usage information."""
        usage_info = quota_manager.get_user_storage_usage(test_db, test_user.id)
        
        assert usage_info["used_gb"] == 2.0
        assert usage_info["quota_gb"] == 10.0
        assert usage_info["percentage"] == 20.0  # 2/10 * 100

    def test_get_user_storage_usage_user_not_found(self, test_db, quota_manager):
        """Test getting storage usage for non-existent user."""
        non_existent_user_id = uuid4()
        usage_info = quota_manager.get_user_storage_usage(test_db, non_existent_user_id)
        
        assert usage_info["used_gb"] == 0.0
        assert usage_info["quota_gb"] == 0.0
        assert usage_info["percentage"] == 0.0

    def test_update_user_storage_usage_positive(self, test_db, test_user, quota_manager):
        """Test updating user storage usage with positive delta."""
        # Increase storage by 1.5GB
        success = quota_manager.update_user_storage_usage(test_db, test_user.id, 1.5)
        assert success is True
        
        # Verify update
        test_db.refresh(test_user)
        assert test_user.storage_used_gb == 3.5  # 2.0 + 1.5

    def test_update_user_storage_usage_negative(self, test_db, test_user, quota_manager):
        """Test updating user storage usage with negative delta."""
        # Decrease storage by 0.5GB
        success = quota_manager.update_user_storage_usage(test_db, test_user.id, -0.5)
        assert success is True
        
        # Verify update
        test_db.refresh(test_user)
        assert test_user.storage_used_gb == 1.5  # 2.0 - 0.5

    def test_update_user_storage_usage_prevent_negative(self, test_db, test_user, quota_manager):
        """Test that storage usage cannot go below zero."""
        # Try to decrease storage by more than current usage
        success = quota_manager.update_user_storage_usage(test_db, test_user.id, -5.0)
        assert success is True
        
        # Verify it's clamped to zero
        test_db.refresh(test_user)
        assert test_user.storage_used_gb == 0.0

    def test_update_user_storage_usage_user_not_found(self, test_db, quota_manager):
        """Test updating storage usage for non-existent user."""
        non_existent_user_id = uuid4()
        success = quota_manager.update_user_storage_usage(test_db, non_existent_user_id, 1.0)
        assert success is False


class TestComputeQuotas:
    """Test compute hour quota validation and tracking."""

    def test_validate_compute_quota_within_limit(self, test_db, test_user, quota_manager):
        """Test compute quota validation when within limits."""
        # User has 100 hour quota, using 10 hours, requesting 30 hours more
        result = quota_manager.validate_compute_quota(test_db, test_user.id, additional_hours=30.0)
        
        assert result.is_valid is True
        assert result.current_usage == 40.0  # 10.0 + 30.0
        assert result.limit == 100.0
        assert "within quota" in result.message

    def test_validate_compute_quota_at_limit(self, test_db, test_user, quota_manager):
        """Test compute quota validation when exactly at limit."""
        # User has 100 hour quota, using 10 hours, requesting exactly 90 hours more
        result = quota_manager.validate_compute_quota(test_db, test_user.id, additional_hours=90.0)
        
        assert result.is_valid is True
        assert result.current_usage == 100.0  # 10.0 + 90.0
        assert result.limit == 100.0

    def test_validate_compute_quota_over_limit(self, test_db, test_user, quota_manager):
        """Test compute quota validation when over limit."""
        # User has 100 hour quota, using 10 hours, requesting 95 hours more (exceeds quota)
        result = quota_manager.validate_compute_quota(test_db, test_user.id, additional_hours=95.0)
        
        assert result.is_valid is False
        assert result.current_usage == 105.0  # 10.0 + 95.0
        assert result.limit == 100.0
        assert "quota exceeded" in result.message

    def test_validate_compute_quota_user_not_found(self, test_db, quota_manager):
        """Test compute quota validation with non-existent user."""
        non_existent_user_id = uuid4()
        result = quota_manager.validate_compute_quota(test_db, non_existent_user_id, additional_hours=10.0)
        
        assert result.is_valid is False
        assert result.current_usage == 0.0
        assert result.limit == 0.0
        assert "User not found" in result.message

    def test_get_user_compute_usage(self, test_db, test_user, quota_manager):
        """Test getting user compute usage information."""
        usage_info = quota_manager.get_user_compute_usage(test_db, test_user.id)
        
        assert usage_info["used_hours"] == 10.0
        assert usage_info["quota_hours"] == 100.0
        assert usage_info["percentage"] == 10.0  # 10/100 * 100

    def test_get_user_compute_usage_user_not_found(self, test_db, quota_manager):
        """Test getting compute usage for non-existent user."""
        non_existent_user_id = uuid4()
        usage_info = quota_manager.get_user_compute_usage(test_db, non_existent_user_id)
        
        assert usage_info["used_hours"] == 0.0
        assert usage_info["quota_hours"] == 0.0
        assert usage_info["percentage"] == 0.0

    def test_update_user_compute_usage_positive(self, test_db, test_user, quota_manager):
        """Test updating user compute usage with positive delta."""
        # Increase compute by 5.5 hours
        success = quota_manager.update_user_compute_usage(test_db, test_user.id, 5.5)
        assert success is True
        
        # Verify update
        test_db.refresh(test_user)
        assert test_user.compute_used_hours == 15.5  # 10.0 + 5.5

    def test_update_user_compute_usage_negative(self, test_db, test_user, quota_manager):
        """Test updating user compute usage with negative delta."""
        # Decrease compute by 2.5 hours
        success = quota_manager.update_user_compute_usage(test_db, test_user.id, -2.5)
        assert success is True
        
        # Verify update
        test_db.refresh(test_user)
        assert test_user.compute_used_hours == 7.5  # 10.0 - 2.5

    def test_update_user_compute_usage_prevent_negative(self, test_db, test_user, quota_manager):
        """Test that compute usage cannot go below zero."""
        # Try to decrease compute by more than current usage
        success = quota_manager.update_user_compute_usage(test_db, test_user.id, -15.0)
        assert success is True
        
        # Verify it's clamped to zero
        test_db.refresh(test_user)
        assert test_user.compute_used_hours == 0.0

    def test_update_user_compute_usage_user_not_found(self, test_db, quota_manager):
        """Test updating compute usage for non-existent user."""
        non_existent_user_id = uuid4()
        success = quota_manager.update_user_compute_usage(test_db, non_existent_user_id, 5.0)
        assert success is False


class TestQuotaIntegration:
    """Test integrated quota management functionality."""

    def test_validate_all_quotas_all_valid(self, test_db, test_user, quota_manager):
        """Test validating all quotas when all are within limits."""
        results = quota_manager.validate_all_quotas(
            test_db, test_user.id, 
            additional_storage_gb=2.0, 
            additional_compute_hours=20.0
        )
        
        assert "concurrent_jobs" in results
        assert "storage" in results
        assert "compute" in results
        
        # All should be valid
        assert results["concurrent_jobs"].is_valid is True
        assert results["storage"].is_valid is True
        assert results["compute"].is_valid is True

    def test_validate_all_quotas_some_invalid(self, test_db, test_user, quota_manager):
        """Test validating all quotas when some exceed limits."""
        results = quota_manager.validate_all_quotas(
            test_db, test_user.id, 
            additional_storage_gb=15.0,  # Would exceed 10GB quota
            additional_compute_hours=20.0  # Still within 100 hour quota
        )
        
        # Storage should be invalid, others valid
        assert results["concurrent_jobs"].is_valid is True
        assert results["storage"].is_valid is False
        assert results["compute"].is_valid is True

    def test_is_quota_available_all_valid(self, test_db, test_user, quota_manager):
        """Test quota availability check when all quotas are available."""
        available = quota_manager.is_quota_available(
            test_db, test_user.id,
            additional_storage_gb=2.0,
            additional_compute_hours=20.0
        )
        
        assert available is True

    def test_is_quota_available_some_invalid(self, test_db, test_user, quota_manager):
        """Test quota availability check when some quotas are exceeded."""
        available = quota_manager.is_quota_available(
            test_db, test_user.id,
            additional_storage_gb=15.0,  # Exceeds quota
            additional_compute_hours=20.0
        )
        
        assert available is False

    def test_get_user_quota_summary(self, test_db, test_user, test_workspace, quota_manager):
        """Test getting complete user quota summary."""
        # Create some running jobs for the test
        for i in range(2):
            job = TrainingJob(
                name=f"Summary Test Job {i}",
                owner_id=test_user.id,
                workspace_id=test_workspace.id,
                status="running",
                job_config={"test": True}
            )
            test_db.add(job)
        test_db.commit()
        
        summary = quota_manager.get_user_quota_summary(test_db, test_user.id)
        
        assert summary["user_id"] == str(test_user.id)
        assert summary["organization"] == "Test Org"
        assert summary["role"] == "researcher"
        
        # Check concurrent jobs
        assert summary["concurrent_jobs"]["current"] == 2
        assert summary["concurrent_jobs"]["limit"] == 5
        assert summary["concurrent_jobs"]["percentage"] == 40.0
        
        # Check storage
        assert summary["storage"]["used_gb"] == 2.0
        assert summary["storage"]["quota_gb"] == 10.0
        assert summary["storage"]["percentage"] == 20.0
        
        # Check compute
        assert summary["compute"]["used_hours"] == 10.0
        assert summary["compute"]["quota_hours"] == 100.0
        assert summary["compute"]["percentage"] == 10.0

    def test_get_user_quota_summary_user_not_found(self, test_db, quota_manager):
        """Test quota summary for non-existent user."""
        non_existent_user_id = uuid4()
        summary = quota_manager.get_user_quota_summary(test_db, non_existent_user_id)
        
        assert "error" in summary
        assert summary["error"] == "User not found"


class TestResourceTracking:
    """Test resource tracking integration with job management."""

    @pytest.fixture
    def job_manager(self):
        """Create MultiUserJobManager for testing."""
        from emuses.multi_user_service.job_manager import MultiUserJobManager
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            return MultiUserJobManager(temp_dir)

    def test_create_user_job_with_quota_validation(self, test_db, test_user, test_workspace, job_manager):
        """Test job creation with quota validation."""
        config = {"pipeline": "test", "data": "sample.nii"}
        
        # Should succeed with valid quotas
        job_id = job_manager.create_user_job(
            user_id=test_user.id,
            config=config,
            job_name="Test Job",
            description="Test job with quota validation",
            db_session=test_db,
            expected_storage_gb=1.0,
            expected_compute_hours=5.0
        )
        
        assert isinstance(job_id, UUID)
        assert job_manager.validate_job_ownership(job_id, test_user.id)

    def test_create_user_job_quota_exceeded(self, test_db, test_user, test_workspace, job_manager):
        """Test job creation fails when quotas are exceeded."""
        config = {"pipeline": "test", "data": "sample.nii"}
        
        # Should fail with excessive storage request
        with pytest.raises(ValueError, match="Quota exceeded for: storage"):
            job_manager.create_user_job(
                user_id=test_user.id,
                config=config,
                job_name="Oversized Job",
                db_session=test_db,
                expected_storage_gb=15.0,  # Exceeds 10GB quota
                expected_compute_hours=5.0
            )

    def test_create_user_job_concurrent_limit_exceeded(self, test_db, test_user, test_workspace, job_manager):
        """Test job creation fails when concurrent job limit is exceeded."""
        # Create 5 running jobs (at limit)
        for i in range(5):
            job = TrainingJob(
                name=f"Concurrent Job {i}",
                owner_id=test_user.id,
                workspace_id=test_workspace.id,
                status="running",
                job_config={"test": True}
            )
            test_db.add(job)
        test_db.commit()
        
        config = {"pipeline": "test", "data": "sample.nii"}
        
        # Should fail due to concurrent job limit
        with pytest.raises(ValueError, match="maximum concurrent jobs"):
            job_manager.create_user_job(
                user_id=test_user.id,
                config=config,
                job_name="Blocked Job",
                db_session=test_db
            )

    def test_start_job_tracking(self, test_db, test_user, job_manager):
        """Test starting resource tracking for a job."""
        # Create a job first
        config = {"pipeline": "test"}
        job_id = job_manager.create_user_job(test_user.id, config, "Tracked Job")
        
        # Start tracking
        job_manager.start_job_tracking(job_id, test_user.id, test_db)
        
        # Verify tracking metadata
        usage = job_manager.get_job_resource_usage(job_id, test_user.id)
        assert usage["tracking_enabled"] is True
        assert usage["tracking_status"] == "active"
        assert usage["tracking_started"] is not None

    def test_update_job_resource_usage(self, test_db, test_user, job_manager):
        """Test updating job resource usage."""
        # Create and start tracking
        config = {"pipeline": "test"}
        job_id = job_manager.create_user_job(test_user.id, config, "Usage Job")
        job_manager.start_job_tracking(job_id, test_user.id, test_db)
        
        # Update resource usage
        job_manager.update_job_resource_usage(
            job_id, test_user.id, 
            compute_hours_delta=2.5,
            storage_bytes_delta=1024*1024*500,  # 500MB
            db_session=test_db
        )
        
        # Verify job-level tracking
        usage = job_manager.get_job_resource_usage(job_id, test_user.id)
        assert usage["compute_hours_used"] == 2.5
        assert usage["storage_bytes_used"] == 1024*1024*500
        
        # Verify user quota was updated
        test_db.refresh(test_user)
        # Storage should increase by ~0.0005GB (500MB converted)
        assert test_user.storage_used_gb > 2.0  # Was 2.0 initially
        assert test_user.compute_used_hours > 10.0  # Was 10.0 initially

    def test_complete_job_tracking(self, test_db, test_user, job_manager):
        """Test completing job resource tracking."""
        # Create and start tracking
        config = {"pipeline": "test"}
        job_id = job_manager.create_user_job(test_user.id, config, "Complete Job")
        job_manager.start_job_tracking(job_id, test_user.id, test_db)
        
        # Update some usage first
        job_manager.update_job_resource_usage(
            job_id, test_user.id,
            compute_hours_delta=1.0,
            storage_bytes_delta=1024*1024*100,  # 100MB
            db_session=test_db
        )
        
        # Complete tracking with final values
        summary = job_manager.complete_job_tracking(
            job_id, test_user.id,
            final_compute_hours=3.5,
            final_storage_bytes=1024*1024*300,  # 300MB
            db_session=test_db
        )
        
        # Verify summary
        assert summary["tracking_completed"] is True
        assert summary["compute_hours_used"] == 3.5
        assert summary["storage_bytes_used"] == 1024*1024*300
        assert summary["compute_hours_delta"] == 2.5  # 3.5 - 1.0
        assert summary["storage_bytes_delta"] == 1024*1024*200  # 300MB - 100MB
        
        # Verify tracking status
        usage = job_manager.get_job_resource_usage(job_id, test_user.id)
        assert usage["tracking_status"] == "completed"
        assert usage["tracking_completed"] is not None

    def test_job_tracking_ownership_validation(self, test_db, test_user, job_manager):
        """Test that job tracking respects ownership validation."""
        # Create another user
        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            organization="Other Org",
            role="researcher"
        )
        test_db.add(other_user)
        test_db.commit()
        
        # Create job for test_user
        config = {"pipeline": "test"}
        job_id = job_manager.create_user_job(test_user.id, config, "Owner Job")
        
        # Other user should not be able to track this job
        with pytest.raises(ValueError, match="not authorized"):
            job_manager.start_job_tracking(job_id, other_user.id, test_db)
        
        with pytest.raises(ValueError, match="not authorized"):
            job_manager.update_job_resource_usage(job_id, other_user.id, 1.0, 1000, test_db)
        
        with pytest.raises(ValueError, match="not authorized"):
            job_manager.complete_job_tracking(job_id, other_user.id, 1.0, 1000, test_db)
        
        with pytest.raises(ValueError, match="not authorized"):
            job_manager.get_job_resource_usage(job_id, other_user.id)

    def test_get_job_resource_usage_inactive_tracking(self, test_db, test_user, job_manager):
        """Test getting resource usage for job without active tracking."""
        # Create job without starting tracking
        config = {"pipeline": "test"}
        job_id = job_manager.create_user_job(test_user.id, config, "Untracked Job")
        
        usage = job_manager.get_job_resource_usage(job_id, test_user.id)
        assert usage["tracking_enabled"] is False
        assert usage["tracking_status"] == "inactive"
        assert usage["compute_hours_used"] == 0.0
        assert usage["storage_bytes_used"] == 0


class TestQuotaResetPolicies:
    """Test quota reset and management policies."""

    def test_reset_user_usage(self, test_db, test_user, quota_manager):
        """Test resetting individual user's usage."""
        # Verify initial usage
        assert test_user.storage_used_gb == 2.0
        assert test_user.compute_used_hours == 10.0
        
        # Reset both storage and compute
        success = quota_manager.reset_user_usage(test_db, test_user.id)
        assert success is True
        
        # Verify reset
        test_db.refresh(test_user)
        assert test_user.storage_used_gb == 0.0
        assert test_user.compute_used_hours == 0.0

    def test_reset_user_usage_selective(self, test_db, test_user, quota_manager):
        """Test selective reset of user usage."""
        # Reset only storage
        success = quota_manager.reset_user_usage(
            test_db, test_user.id, reset_storage=True, reset_compute=False
        )
        assert success is True
        
        test_db.refresh(test_user)
        assert test_user.storage_used_gb == 0.0
        assert test_user.compute_used_hours == 10.0  # Unchanged
        
        # Reset storage back and reset only compute
        test_user.storage_used_gb = 5.0
        test_db.commit()
        
        success = quota_manager.reset_user_usage(
            test_db, test_user.id, reset_storage=False, reset_compute=True
        )
        assert success is True
        
        test_db.refresh(test_user)
        assert test_user.storage_used_gb == 5.0  # Unchanged
        assert test_user.compute_used_hours == 0.0

    def test_reset_user_usage_nonexistent_user(self, test_db, quota_manager):
        """Test reset for non-existent user."""
        non_existent_user_id = uuid4()
        success = quota_manager.reset_user_usage(test_db, non_existent_user_id)
        assert success is False

    def test_reset_all_users_usage(self, test_db, test_user, quota_manager):
        """Test resetting all users' usage."""
        # Create additional users
        user2 = User(
            email="user2@example.com",
            hashed_password="hashed",
            organization="Test Org",
            role="researcher",
            storage_used_gb=5.0,
            compute_used_hours=20.0
        )
        user3 = User(
            email="user3@example.com", 
            hashed_password="hashed",
            organization="Other Org",
            role="admin",
            storage_used_gb=8.0,
            compute_used_hours=30.0
        )
        test_db.add_all([user2, user3])
        test_db.commit()
        
        # Reset all users
        result = quota_manager.reset_all_users_usage(test_db)
        
        assert result["success"] is True
        assert result["users_processed"] == 3
        assert result["users_reset"] == 3
        assert result["users_failed"] == 0
        assert result["reset_storage"] is True
        assert result["reset_compute"] is True
        
        # Verify all users were reset
        test_db.refresh(test_user)
        test_db.refresh(user2)
        test_db.refresh(user3)
        
        assert test_user.storage_used_gb == 0.0
        assert test_user.compute_used_hours == 0.0
        assert user2.storage_used_gb == 0.0
        assert user2.compute_used_hours == 0.0
        assert user3.storage_used_gb == 0.0
        assert user3.compute_used_hours == 0.0

    def test_reset_all_users_usage_with_organization_filter(self, test_db, test_user, quota_manager):
        """Test resetting users in specific organization only."""
        # Create user in different organization
        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            organization="Other Org",
            role="researcher",
            storage_used_gb=5.0,
            compute_used_hours=20.0
        )
        test_db.add(other_user)
        test_db.commit()
        
        # Reset only "Test Org" users
        result = quota_manager.reset_all_users_usage(
            test_db, organization_filter="Test Org"
        )
        
        assert result["success"] is True
        assert result["users_processed"] == 1  # Only test_user
        assert result["users_reset"] == 1
        assert result["organization_filter"] == "Test Org"
        
        # Verify selective reset
        test_db.refresh(test_user)
        test_db.refresh(other_user)
        
        assert test_user.storage_used_gb == 0.0  # Reset
        assert test_user.compute_used_hours == 0.0  # Reset
        assert other_user.storage_used_gb == 5.0  # Unchanged
        assert other_user.compute_used_hours == 20.0  # Unchanged

    def test_schedule_quota_reset(self, test_db, quota_manager):
        """Test quota reset scheduling configuration."""
        config = quota_manager.schedule_quota_reset(
            test_db,
            reset_frequency_days=7,
            reset_storage=True,
            reset_compute=False,
            organization_filter="Test Org"
        )
        
        assert config["scheduled"] is True
        assert config["reset_frequency_days"] == 7
        assert config["reset_storage"] is True
        assert config["reset_compute"] is False
        assert config["organization_filter"] == "Test Org"
        assert "next_reset_date" in config
        assert "In production" in config["note"]

    def test_get_users_near_quota_limit(self, test_db, test_user, quota_manager):
        """Test identifying users near quota limits."""
        # Set test_user to 95% storage usage
        test_user.storage_used_gb = 9.5  # 95% of 10GB quota
        test_user.compute_used_hours = 85.0  # 85% of 100 hour quota
        
        # Create user near compute limit but not storage
        near_compute_user = User(
            email="nearcompute@example.com",
            hashed_password="hashed",
            organization="Test Org",
            role="researcher",
            storage_quota_gb=20.0,
            compute_quota_hours=50.0,
            storage_used_gb=5.0,  # 25% of quota
            compute_used_hours=47.0  # 94% of quota
        )
        
        # Create user well within limits
        safe_user = User(
            email="safe@example.com",
            hashed_password="hashed",
            organization="Test Org", 
            role="researcher",
            storage_quota_gb=15.0,
            compute_quota_hours=80.0,
            storage_used_gb=3.0,  # 20% of quota
            compute_used_hours=20.0  # 25% of quota
        )
        
        test_db.add_all([near_compute_user, safe_user])
        test_db.commit()
        
        # Check users near 90% limit
        near_limit_users = quota_manager.get_users_near_quota_limit(test_db, 90.0, 90.0)
        
        # Should return test_user and near_compute_user
        assert len(near_limit_users) == 2
        
        # Find test_user in results
        test_user_result = next(
            (user for user in near_limit_users if user["email"] == test_user.email), 
            None
        )
        assert test_user_result is not None
        assert test_user_result["storage_percent"] == 95.0
        assert test_user_result["compute_percent"] == 85.0
        assert test_user_result["over_storage_limit"] is True
        assert test_user_result["over_compute_limit"] is False
        
        # Find near_compute_user in results
        compute_user_result = next(
            (user for user in near_limit_users if user["email"] == near_compute_user.email),
            None
        )
        assert compute_user_result is not None
        assert compute_user_result["storage_percent"] == 25.0
        assert compute_user_result["compute_percent"] == 94.0
        assert compute_user_result["over_storage_limit"] is False
        assert compute_user_result["over_compute_limit"] is True

    def test_get_users_near_quota_limit_empty_result(self, test_db, quota_manager):
        """Test quota limit check when no users are near limits."""
        # Create user well within limits
        safe_user = User(
            email="safe@example.com",
            hashed_password="hashed",
            organization="Test Org",
            role="researcher",
            storage_quota_gb=20.0,
            compute_quota_hours=100.0,
            storage_used_gb=2.0,  # 10% of quota
            compute_used_hours=10.0  # 10% of quota
        )
        test_db.add(safe_user)
        test_db.commit()
        
        # Check for users near 90% limit
        near_limit_users = quota_manager.get_users_near_quota_limit(test_db, 90.0, 90.0)
        assert len(near_limit_users) == 0