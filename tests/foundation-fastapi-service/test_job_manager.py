"""Test suite for JobManager - Task 2.

This module contains tests for the job lifecycle management functionality,
including UUID generation, status tracking, directory organization, and
security features.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from uuid import UUID
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import threading
import time
import os

from emuses.foundation_fastapi_service.job_manager import JobManager


class TestJobManager:
    """Test suite for JobManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.job_manager = JobManager(base_directory=self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)


class TestUUIDGeneration:
    """Test suite for secure UUID job ID generation - Task 2.1."""
    
    def test_generate_job_id_returns_valid_uuid(self):
        """Test that generate_job_id returns a valid UUID4."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            job_manager = JobManager(base_directory=temp_dir)
            job_id = job_manager.generate_job_id()
            
            # Should be a valid UUID4
            assert isinstance(job_id, UUID)
            assert job_id.version == 4
            
            # Should be unique on repeated calls
            job_id2 = job_manager.generate_job_id()
            assert job_id != job_id2
        finally:
            shutil.rmtree(temp_dir)
    
    def test_generate_job_id_entropy_check(self):
        """Test that UUID generation has sufficient entropy."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            job_manager = JobManager(base_directory=temp_dir)
            
            # Generate multiple UUIDs and ensure they're all different
            uuids = [job_manager.generate_job_id() for _ in range(100)]
            
            # All should be unique
            assert len(set(uuids)) == 100
            
            # Check that they have reasonable entropy (no obvious patterns)
            uuid_strings = [str(uuid) for uuid in uuids]
            
            # No two UUIDs should share the same first 8 characters
            prefixes = [uuid_str[:8] for uuid_str in uuid_strings]
            assert len(set(prefixes)) == 100
        finally:
            shutil.rmtree(temp_dir)
    
    def test_job_id_validation(self):
        """Test job ID validation functionality."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            job_manager = JobManager(base_directory=temp_dir)
            
            # Valid UUID should pass validation
            valid_uuid = job_manager.generate_job_id()
            assert job_manager.validate_job_id(valid_uuid) is True
            
            # Invalid UUID should fail validation
            assert job_manager.validate_job_id("invalid-uuid") is False
            assert job_manager.validate_job_id(None) is False
            assert job_manager.validate_job_id("") is False
        finally:
            shutil.rmtree(temp_dir)


class TestJobDirectoryStructure:
    """Test suite for job directory structure creation - Task 2.2."""
    
    def test_create_job_directory_structure(self):
        """Test that job directories are created with proper structure."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            job_manager = JobManager(base_directory=temp_dir)
            job_id = job_manager.generate_job_id()
            
            # Create job directory
            job_dir = job_manager.create_job_directory(job_id)
            
            # Verify structure
            assert job_dir.exists()
            assert (job_dir / "input").exists()
            assert (job_dir / "output").exists()
            assert (job_dir / "logs").exists()
            
            # Verify it's within the expected base directory
            assert job_dir.parent == temp_dir / "jobs"
            assert job_dir.name == str(job_id)
        finally:
            shutil.rmtree(temp_dir)
    
    def test_path_traversal_protection(self):
        """Test that path traversal attacks are prevented."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            job_manager = JobManager(base_directory=temp_dir)
            
            # Attempt path traversal attacks
            malicious_paths = [
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32",
                "/etc/passwd",
                "C:\\Windows\\System32",
                "job_id/../../../sensitive_file"
            ]
            
            for malicious_path in malicious_paths:
                with pytest.raises(ValueError, match="Invalid job ID"):
                    job_manager.create_job_directory(malicious_path)
        finally:
            shutil.rmtree(temp_dir)
    
    def test_job_directory_permissions(self):
        """Test that job directories have proper permissions."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            job_manager = JobManager(base_directory=temp_dir)
            job_id = job_manager.generate_job_id()
            
            job_dir = job_manager.create_job_directory(job_id)
            
            # Check that directories are readable and writable by owner
            assert job_dir.stat().st_mode & 0o700  # Owner read/write/execute
            assert (job_dir / "input").stat().st_mode & 0o700
            assert (job_dir / "output").stat().st_mode & 0o700
            assert (job_dir / "logs").stat().st_mode & 0o700
        finally:
            shutil.rmtree(temp_dir)


class TestJobStatusPersistence:
    """Test suite for job status persistence and updates - Task 2.3."""
    
    def test_job_status_persistence(self):
        """Test that job status is properly persisted to disk."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            job_manager = JobManager(base_directory=temp_dir)
            job_id = job_manager.generate_job_id()
            
            # Create job and set initial status
            job_manager.create_job_directory(job_id)
            job_manager.update_job_status(job_id, "SUBMITTED")
            
            # Verify status is persisted
            status = job_manager.get_job_status(job_id)
            assert status["status"] == "SUBMITTED"
            assert status["job_id"] == str(job_id)
            
            # Update status and verify persistence
            job_manager.update_job_status(job_id, "RUNNING", progress=0.5)
            status = job_manager.get_job_status(job_id)
            assert status["status"] == "RUNNING"
            assert status["progress"] == 0.5
        finally:
            shutil.rmtree(temp_dir)
    
    def test_concurrent_status_updates(self):
        """Test that concurrent status updates are handled safely."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            job_manager = JobManager(base_directory=temp_dir)
            job_id = job_manager.generate_job_id()
            job_manager.create_job_directory(job_id)
            job_manager.update_job_status(job_id, "SUBMITTED")
            
            # Simulate concurrent updates
            def update_status(status_suffix):
                for i in range(10):
                    job_manager.update_job_status(
                        job_id, 
                        f"RUNNING_{status_suffix}",
                        progress=i * 0.1
                    )
                    time.sleep(0.01)
            
            # Start multiple threads updating status
            threads = []
            for i in range(5):
                thread = threading.Thread(target=update_status, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Verify final status is consistent
            status = job_manager.get_job_status(job_id)
            assert status["status"].startswith("RUNNING_")
            assert isinstance(status["progress"], float)
        finally:
            shutil.rmtree(temp_dir)
    
    def test_status_update_with_invalid_job_id(self):
        """Test that updating non-existent job raises appropriate error."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            job_manager = JobManager(base_directory=temp_dir)
            fake_job_id = job_manager.generate_job_id()
            
            # Should raise error for non-existent job
            with pytest.raises(ValueError, match="Job not found"):
                job_manager.update_job_status(fake_job_id, "RUNNING")
        finally:
            shutil.rmtree(temp_dir)


class TestJobMetadataTracking:
    """Test suite for job metadata tracking - Task 2.4."""
    
    def test_job_metadata_sanitization(self):
        """Test that job metadata is properly sanitized."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            job_manager = JobManager(base_directory=temp_dir)
            job_id = job_manager.generate_job_id()
            job_manager.create_job_directory(job_id)
            
            # Test metadata with potentially dangerous content
            metadata = {
                "user_input": "<script>alert('xss')</script>",
                "file_path": "../../../etc/passwd",
                "description": "Job with\x00null\x01bytes",
                "normal_field": "normal_value"
            }
            
            job_manager.update_job_metadata(job_id, metadata)
            
            # Verify metadata is sanitized
            stored_metadata = job_manager.get_job_metadata(job_id)
            
            # XSS should be escaped/removed
            assert "<script>" not in stored_metadata["user_input"]
            
            # Path traversal should be sanitized
            assert "../" not in stored_metadata["file_path"]
            
            # Null bytes should be removed
            assert "\x00" not in stored_metadata["description"]
            assert "\x01" not in stored_metadata["description"]
            
            # Normal content should be preserved
            assert stored_metadata["normal_field"] == "normal_value"
        finally:
            shutil.rmtree(temp_dir)
    
    def test_job_cleanup_policies(self):
        """Test that job cleanup policies are enforced."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create job manager with short cleanup policy
            job_manager = JobManager(
                base_directory=temp_dir,
                cleanup_after_days=0.001  # Very short for testing
            )
            
            job_id = job_manager.generate_job_id()
            job_manager.create_job_directory(job_id)
            job_manager.update_job_status(job_id, "COMPLETED")
            
            # Job should exist initially
            assert job_manager.job_exists(job_id)
            
            # Manually set an old completion time to simulate an old job
            old_time = datetime.now() - timedelta(days=1)
            job_manager.update_job_metadata(job_id, {"completed_at": old_time.isoformat()})
            
            # Run cleanup
            cleaned_jobs = job_manager.cleanup_old_jobs()
            
            # Job should be cleaned up
            assert job_id in cleaned_jobs
            assert not job_manager.job_exists(job_id)
        finally:
            shutil.rmtree(temp_dir)
    
    def test_job_metadata_tracking_comprehensive(self):
        """Test comprehensive job metadata tracking."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            job_manager = JobManager(base_directory=temp_dir)
            job_id = job_manager.generate_job_id()
            job_manager.create_job_directory(job_id)
            
            # Test full metadata lifecycle
            initial_metadata = {
                "created_by": "test_user",
                "pipeline_config": {"input_file": "test.csv"},
                "priority": "normal"
            }
            
            job_manager.update_job_metadata(job_id, initial_metadata)
            
            # Verify metadata is stored
            metadata = job_manager.get_job_metadata(job_id)
            assert metadata["created_by"] == "test_user"
            assert metadata["pipeline_config"]["input_file"] == "test.csv"
            assert metadata["priority"] == "normal"
            
            # Update metadata
            job_manager.update_job_metadata(job_id, {"status": "running"})
            
            # Verify both old and new metadata exist
            metadata = job_manager.get_job_metadata(job_id)
            assert metadata["created_by"] == "test_user"  # Old metadata preserved
            assert metadata["status"] == "running"  # New metadata added
        finally:
            shutil.rmtree(temp_dir)
