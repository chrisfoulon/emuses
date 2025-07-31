"""Tests for MultiUserJobManager with user-scoped storage.

Tests user workspace isolation in job management with secure storage paths,
user quota validation, and ownership verification.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from uuid import UUID, uuid4
from emuses.multi_user_service.job_manager import MultiUserJobManager
from emuses.multi_user_service.models import User


@pytest.fixture
def temp_base_dir():
    """Create temporary base directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_user_id():
    """Create test user ID."""
    return uuid4()


@pytest.fixture
def job_manager(temp_base_dir):
    """Create MultiUserJobManager instance."""
    return MultiUserJobManager(base_directory=temp_base_dir)


@pytest.fixture
def mock_user():
    """Create mock user for testing."""
    return User(
        id=uuid4(),
        email="test@example.com",
        hashed_password="hashed",
        organization="Test Org",
        role="researcher",
        storage_quota_gb=10.0,
        compute_quota_hours=100.0
    )


class TestMultiUserJobManager:
    """Test multi-user job manager functionality."""

    def test_multi_user_job_manager_creation(self, temp_base_dir):
        """Test MultiUserJobManager creation and initialization."""
        job_manager = MultiUserJobManager(
            base_directory=temp_base_dir,
            cleanup_after_days=7.0
        )
        
        assert job_manager.base_directory == temp_base_dir
        assert job_manager.cleanup_after_days == 7.0
        assert job_manager.base_directory.exists()
        assert (job_manager.base_directory / "jobs").exists()

    def test_user_workspace_storage_factory(self, job_manager, test_user_id):
        """Test user-isolated storage path creation."""
        storage_path = job_manager.create_user_storage_path(test_user_id)
        
        # Verify user isolation pattern
        expected_pattern = f"users/{test_user_id}/jobs"
        assert expected_pattern in str(storage_path)
        assert storage_path.exists()
        
        # Verify secure permissions (0o700)
        if hasattr(storage_path, 'stat'):
            mode = storage_path.stat().st_mode & 0o777
            assert mode == 0o700

    def test_user_scoped_job_creation(self, job_manager, mock_user):
        """Test job creation with user context."""
        config = {"param1": "value1", "n_trials": 100}
        
        job_id = job_manager.create_user_job(
            user_id=mock_user.id,
            config=config,
            job_name="Test User Job",
            description="Test job with user scope"
        )
        
        # Verify job creation
        assert isinstance(job_id, UUID)
        assert job_manager.job_exists(job_id)
        
        # Verify user ownership
        assert job_manager.validate_job_ownership(job_id, mock_user.id)
        
        # Verify user-scoped storage path
        job_dir = job_manager.get_job_directory(job_id)
        assert f"users/{mock_user.id}/jobs" in str(job_dir)

    def test_user_quota_validation(self, job_manager, mock_user):
        """Test user quota validation before job creation."""
        # Test within quota limits
        config = {"param1": "value1"}
        
        # This should succeed (within quota)
        job_id = job_manager.create_user_job(
            user_id=mock_user.id,
            config=config,
            job_name="Within Quota Job"
        )
        assert job_id is not None
        
        # Test quota validation method
        assert job_manager.check_user_quota(mock_user.id, expected_storage_gb=1.0)
        assert job_manager.check_user_quota(mock_user.id, expected_compute_hours=10.0)

    def test_user_job_ownership_validation(self, job_manager, mock_user):
        """Test job ownership validation and enforcement."""
        # Create job with user
        config = {"param1": "value1"}
        job_id = job_manager.create_user_job(
            user_id=mock_user.id,
            config=config,
            job_name="Ownership Test Job"
        )
        
        # Test ownership validation
        assert job_manager.validate_job_ownership(job_id, mock_user.id)
        
        # Test with different user
        other_user_id = uuid4()
        assert not job_manager.validate_job_ownership(job_id, other_user_id)

    def test_user_scoped_job_listing(self, job_manager, mock_user):
        """Test user-scoped job listing and filtering."""
        # Create multiple jobs for user
        job_ids = []
        for i in range(3):
            config = {"param1": f"value{i}"}
            job_id = job_manager.create_user_job(
                user_id=mock_user.id,
                config=config,
                job_name=f"User Job {i}"
            )
            job_ids.append(job_id)
        
        # Test user job listing
        user_jobs = job_manager.list_user_jobs(mock_user.id)
        assert len(user_jobs) == 3
        
        # Verify all jobs belong to user
        for job in user_jobs:
            job_id = job["job_id"]
            if isinstance(job_id, str):
                job_id = UUID(job_id)
            assert job_manager.validate_job_ownership(job_id, mock_user.id)

    def test_user_scoped_job_cancellation(self, job_manager, mock_user):
        """Test job cancellation with ownership validation."""
        # Create job
        config = {"param1": "value1"}
        job_id = job_manager.create_user_job(
            user_id=mock_user.id,
            config=config,
            job_name="Cancellation Test Job"
        )
        
        # Test cancellation with correct ownership
        result = job_manager.cancel_user_job(job_id, mock_user.id)
        assert result is True
        
        # Verify job status
        status = job_manager.get_job_status(job_id)
        assert status["status"] == "cancelled"

    def test_user_scoped_job_cancellation_wrong_owner(self, job_manager, mock_user):
        """Test job cancellation fails with wrong owner."""
        # Create job
        config = {"param1": "value1"}
        job_id = job_manager.create_user_job(
            user_id=mock_user.id,
            config=config,
            job_name="Wrong Owner Test Job"
        )
        
        # Test cancellation with wrong owner
        other_user_id = uuid4()
        with pytest.raises(ValueError, match="not authorized"):
            job_manager.cancel_user_job(job_id, other_user_id)

    def test_user_storage_isolation(self, job_manager, temp_base_dir):
        """Test user storage isolation and security boundaries."""
        user1_id = uuid4()
        user2_id = uuid4()
        
        # Create storage paths for different users
        storage1 = job_manager.create_user_storage_path(user1_id)
        storage2 = job_manager.create_user_storage_path(user2_id)
        
        # Verify paths are different and isolated
        assert storage1 != storage2
        assert str(user1_id) in str(storage1)
        assert str(user2_id) in str(storage2)
        assert str(user1_id) not in str(storage2)
        assert str(user2_id) not in str(storage1)

    def test_user_job_metadata_privacy(self, job_manager, mock_user):
        """Test user job metadata privacy and access control."""
        # Create job with metadata
        config = {"param1": "value1"}
        job_id = job_manager.create_user_job(
            user_id=mock_user.id,
            config=config,
            job_name="Privacy Test Job",
            description="Sensitive user data"
        )
        
        # Verify metadata access with correct user
        metadata = job_manager.get_user_job_metadata(job_id, mock_user.id)
        assert metadata["job_name"] == "Privacy Test Job"
        assert metadata["description"] == "Sensitive user data"
        
        # Test access with wrong user
        other_user_id = uuid4()
        with pytest.raises(ValueError, match="not authorized"):
            job_manager.get_user_job_metadata(job_id, other_user_id)

    def test_user_resource_tracking(self, job_manager, mock_user):
        """Test user resource usage tracking and quota updates."""
        # Create job
        config = {"param1": "value1"}
        job_id = job_manager.create_user_job(
            user_id=mock_user.id,
            config=config,
            job_name="Resource Tracking Job"
        )
        
        # Update resource usage
        job_manager.update_user_resource_usage(
            job_id=job_id,
            user_id=mock_user.id,
            compute_hours_used=2.5,
            storage_bytes_used=1048576  # 1MB
        )
        
        # Verify resource tracking
        usage = job_manager.get_user_resource_usage(mock_user.id)
        assert usage["compute_hours_used"] >= 2.5
        assert usage["storage_bytes_used"] >= 1048576

    def test_user_job_directory_permissions(self, job_manager, mock_user):
        """Test user job directory has secure permissions."""
        config = {"param1": "value1"}
        job_id = job_manager.create_user_job(
            user_id=mock_user.id,
            config=config,
            job_name="Permissions Test Job"
        )
        
        job_dir = job_manager.get_job_directory(job_id)
        
        # Verify directory exists and has secure permissions
        assert job_dir.exists()
        if hasattr(job_dir, 'stat'):
            mode = job_dir.stat().st_mode & 0o777
            assert mode == 0o700  # Owner read/write/execute only