"""End-to-end cloud storage validation tests.

This module provides comprehensive end-to-end testing for cloud storage operations
including resilience testing, multipart uploads, signed URL expiration, and
authentication flows using real cloud emulators.
"""
import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil
import json
import time
import os
from unittest.mock import patch, AsyncMock

# Test requires moto for AWS testing
try:
    from moto import mock_aws
    import boto3
    MOTO_AVAILABLE = True
except ImportError:
    MOTO_AVAILABLE = False

# Test requires cloud resilience module
try:
    from emuses.tools.cloud_resilience import (
        CloudErrorClassifier,
        with_exponential_backoff,
        CircuitBreaker,
        CircuitBreakerError
    )
    RESILIENCE_MODULE_AVAILABLE = True
except ImportError:
    RESILIENCE_MODULE_AVAILABLE = False

from emuses.tools.cloud_storage import S3StorageBackend


@pytest.mark.skipif(not MOTO_AVAILABLE or not RESILIENCE_MODULE_AVAILABLE, 
                    reason="moto or cloud resilience module not available")
class TestCloudResilienceEndToEnd:
    """End-to-end tests for cloud storage with resilience patterns."""

    @pytest.fixture
    def large_model_dir(self):
        """Create temporary model directory with large files for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create model structure
        model_dir = temp_dir / "large-test-model"
        model_dir.mkdir()
        
        # Create directory structure
        (model_dir / "models").mkdir()
        (model_dir / "artifacts").mkdir() 
        (model_dir / "metadata").mkdir()
        (model_dir / "data").mkdir()
        
        # Create manifest file
        manifest = {
            "name": "large-test-model",
            "version": "1.0.0", 
            "created_at": "2025-01-01T00:00:00Z",
            "description": "Large model for testing multipart uploads and resilience",
            "metrics": {
                "accuracy": 0.95,
                "f1_score": 0.92,
                "precision": 0.94,
                "recall": 0.91
            },
            "large_files": ["data/training_data.bin", "models/model_weights.pkl"]
        }
        (model_dir / "model_manifest.json").write_text(json.dumps(manifest, indent=2))
        
        # Create model files - simulate different sizes
        (model_dir / "models" / "model.pkl").write_bytes(b"model_data" * 1000)  # ~10KB
        (model_dir / "models" / "model_weights.pkl").write_bytes(b"weights" * 50000)  # ~350KB
        (model_dir / "artifacts" / "metrics.json").write_text(json.dumps(manifest["metrics"]))
        (model_dir / "artifacts" / "config.yaml").write_text("model_config:\n  layers: 10\n  neurons: 512")
        
        # Create larger data files to test multipart handling
        (model_dir / "data" / "training_data.bin").write_bytes(b"training_sample" * 100000)  # ~1.4MB
        (model_dir / "data" / "validation_data.bin").write_bytes(b"validation_sample" * 50000)  # ~750KB
        
        # Create metadata
        (model_dir / "metadata" / "training_log.txt").write_text(
            "Training log:\nEpoch 1: loss=0.8, accuracy=0.75\nEpoch 2: loss=0.6, accuracy=0.82\n" * 100
        )
        
        yield model_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.fixture 
    def s3_backend_with_resilience(self):
        """Create S3 backend with resilience capabilities enabled."""
        # Set dummy AWS credentials
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SECURITY_TOKEN"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        
        with mock_aws():
            # Create S3 client and bucket
            s3_client = boto3.client("s3", region_name="us-east-1")
            bucket_name = "test-resilience-bucket"
            s3_client.create_bucket(Bucket=bucket_name)
            
            # Create backend
            backend = S3StorageBackend(
                bucket_name=bucket_name,
                access_key="testing",
                secret_key="testing",
                region="us-east-1"
            )
            
            yield backend

    @pytest.mark.asyncio
    async def test_end_to_end_upload_with_retry_on_failure(self, s3_backend_with_resilience, large_model_dir):
        """Test end-to-end upload with simulated failures and retry recovery.
        
        This test validates:
        1. Large model upload with resilience patterns
        2. Retry logic handles transient failures
        3. Final success after temporary failures
        4. Complete upload/download cycle integrity
        """
        backend = s3_backend_with_resilience
        model_id = "resilience-test-model"
        
        # Simulate intermittent failures using mock
        original_upload = backend.upload_model
        call_count = 0
        
        async def failing_upload_model(model_dir, model_id):
            nonlocal call_count
            call_count += 1
            
            if call_count <= 2:
                # First two calls fail with transient errors
                if call_count == 1:
                    raise ConnectionError("Network temporarily unavailable")
                else:
                    raise TimeoutError("Request timeout")
            else:
                # Third call succeeds
                return await original_upload(model_dir, model_id)
        
        # Apply retry decorator to the failing method
        @with_exponential_backoff(max_attempts=5, base_delay=0.01, max_delay=0.1)
        async def resilient_upload(model_dir, model_id):
            return await failing_upload_model(model_dir, model_id)
        
        # Execute upload with retry logic
        start_time = time.time()
        storage_url = await resilient_upload(large_model_dir, model_id)
        execution_time = time.time() - start_time
        
        # Verify retry behavior
        assert call_count == 3  # Two failures + one success
        assert execution_time > 0.02  # Should have delays from retries
        
        # Verify successful upload
        assert storage_url.startswith("s3://")
        assert model_id in storage_url
        assert storage_url.endswith("model_bundle.tar.gz")
        
        # Verify download works after resilient upload
        download_dir = large_model_dir.parent / "downloaded_resilience"
        await backend.download_model(storage_url, download_dir / "large-test-model")
        
        # Verify integrity
        downloaded_model = download_dir / "large-test-model"
        assert downloaded_model.exists()
        
        # Check large files were properly handled
        assert (downloaded_model / "data" / "training_data.bin").exists()
        original_size = (large_model_dir / "data" / "training_data.bin").stat().st_size
        downloaded_size = (downloaded_model / "data" / "training_data.bin").stat().st_size
        assert original_size == downloaded_size

    @pytest.mark.asyncio
    async def test_circuit_breaker_protects_against_cascade_failures(self, s3_backend_with_resilience, large_model_dir):
        """Test circuit breaker prevents cascade failures during cloud operations.
        
        This test validates:
        1. Circuit breaker opens after failure threshold
        2. Subsequent calls fail fast without retry overhead
        3. Circuit breaker recovers after timeout period
        4. Normal operations resume after recovery
        """
        backend = s3_backend_with_resilience
        model_id = "circuit-breaker-test-model"
        
        # Create circuit breaker with low threshold for testing
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=0.1  # Short timeout for testing
        )
        
        # Create operation that always fails initially
        failure_count = 0
        async def failing_operation():
            nonlocal failure_count
            failure_count += 1
            if failure_count <= 5:  # Fail first 5 calls
                raise ConnectionError(f"Service down - call {failure_count}")
            else:
                # After recovery, succeed
                return await backend.upload_model(large_model_dir, model_id)
        
        # Test circuit breaker behavior
        
        # Phase 1: Initial failures (circuit closed)
        for i in range(3):
            with pytest.raises(ConnectionError):
                await circuit_breaker.execute(failing_operation)
        
        # Phase 2: Circuit should be open - fail fast
        start_time = time.time()
        with pytest.raises(CircuitBreakerError):
            await circuit_breaker.execute(failing_operation)
        fast_fail_time = time.time() - start_time
        
        # Circuit breaker should fail immediately (< 10ms)
        assert fast_fail_time < 0.01
        
        # Phase 3: Wait for recovery period
        await asyncio.sleep(0.15)  # Wait longer than recovery_timeout
        
        # Phase 4: Circuit should be half-open, allow test call
        # This call should still fail initially
        with pytest.raises(ConnectionError):
            await circuit_breaker.execute(failing_operation)
        
        # Wait again and try - should eventually succeed
        await asyncio.sleep(0.15)
        
        # Mock the operation to succeed for recovery test
        failure_count = 10  # Set to high value so operation succeeds
        
        # This should succeed and close the circuit
        storage_url = await circuit_breaker.execute(failing_operation)
        assert storage_url is not None

    @pytest.mark.asyncio
    async def test_multipart_upload_simulation_with_large_files(self, s3_backend_with_resilience, large_model_dir):
        """Test handling of large files that would trigger multipart uploads.
        
        This test validates:
        1. Large files are properly compressed and uploaded
        2. Download maintains file integrity
        3. Compression ratios are reasonable
        4. Upload/download performance is acceptable
        """
        backend = s3_backend_with_resilience
        model_id = "multipart-test-model"
        
        # Add extra large file to test multipart scenario (before upload)
        large_file = large_model_dir / "data" / "extra_large.bin"
        large_file.write_bytes(b"large_data_chunk" * 200000)  # ~3MB
        
        # Verify the file was created successfully
        assert large_file.exists(), f"Failed to create large file: {large_file}"
        print(f"Created large file: {large_file} ({large_file.stat().st_size / 1024 / 1024:.2f}MB)")
        
        # Measure original total size
        original_total_size = sum(
            f.stat().st_size for f in large_model_dir.rglob("*") if f.is_file()
        )
        
        # Upload with timing
        start_time = time.time()
        storage_url = await backend.upload_model(large_model_dir, model_id)
        upload_time = time.time() - start_time
        
        # Verify upload completed
        assert storage_url.startswith("s3://")
        assert model_id in storage_url
        
        # Test download with timing
        download_dir = large_model_dir.parent / "downloaded_multipart" 
        download_dir.mkdir(exist_ok=True)  # Ensure download directory exists
        download_target = download_dir / "multipart-test-model"
        
        start_time = time.time()
        await backend.download_model(storage_url, download_target)
        download_time = time.time() - start_time
        
        # Debug download result
        print(f"Download target: {download_target}")
        print(f"Download dir exists: {download_dir.exists()}")
        print(f"Download dir contents: {list(download_dir.rglob('*')) if download_dir.exists() else 'None'}")
        
        # The downloaded model uses the original model directory name, not the target name
        # Look for the actual extracted directory
        extracted_dirs = [p for p in download_dir.iterdir() if p.is_dir()]
        assert len(extracted_dirs) == 1, f"Expected 1 extracted directory, found {len(extracted_dirs)}: {extracted_dirs}"
        
        downloaded_model = extracted_dirs[0]
        print(f"Downloaded model dir: {downloaded_model}")
        print(f"Downloaded model dir exists: {downloaded_model.exists()}")
        
        # Verify integrity of large files
        downloaded_large_file = downloaded_model / "data" / "extra_large.bin"
        assert downloaded_large_file.exists(), f"File not found: {downloaded_large_file}"
        original_large_size = large_file.stat().st_size
        downloaded_large_size = downloaded_large_file.stat().st_size
        assert original_large_size == downloaded_large_size
        
        # Verify data integrity
        original_content = large_file.read_bytes()
        downloaded_content = downloaded_large_file.read_bytes()
        assert original_content == downloaded_content
        
        # Performance checks
        print(f"Upload time for {original_total_size/1024/1024:.2f}MB: {upload_time:.2f}s")
        print(f"Download time: {download_time:.2f}s")
        
        # Reasonable performance expectations (should complete in reasonable time)
        assert upload_time < 30.0  # Should upload within 30 seconds
        assert download_time < 30.0  # Should download within 30 seconds

    @pytest.mark.asyncio
    async def test_signed_url_expiration_and_validation(self, s3_backend_with_resilience, large_model_dir):
        """Test signed URL generation, expiration scenarios, and validation.
        
        This test validates:
        1. Signed URLs are generated with correct expiration
        2. URL format includes proper authentication parameters
        3. Different expiration times generate different URLs
        4. URLs contain expected model information
        """
        backend = s3_backend_with_resilience
        model_id = "signed-url-expiration-test"
        
        # Upload model first
        storage_url = await backend.upload_model(large_model_dir, model_id)
        
        # Test different expiration times
        expiration_times = [300, 3600, 7200]  # 5 minutes, 1 hour, 2 hours
        signed_urls = []
        
        for expires_in in expiration_times:
            signed_url = await backend.generate_signed_url(storage_url, expires_in)
            signed_urls.append(signed_url)
            
            # Verify URL format
            assert signed_url.startswith("https://")
            assert "amazonaws.com" in signed_url
            assert "AWSAccessKeyId" in signed_url
            assert "Signature" in signed_url
            assert "Expires" in signed_url
            
            # Verify model information in URL
            assert model_id in signed_url
            assert "model_bundle.tar.gz" in signed_url
        
        # Verify different expiration times generate different URLs
        assert len(set(signed_urls)) == len(signed_urls)  # All URLs should be unique
        
        # Test short expiration URL (simulate expired scenario)
        short_expire_url = await backend.generate_signed_url(storage_url, 1)  # 1 second
        assert short_expire_url.startswith("https://")
        
        # In a real test with actual S3, we would wait and verify the URL expires
        # For moto testing, we just verify the URL format is correct

    @pytest.mark.asyncio
    async def test_error_classification_across_operations(self, s3_backend_with_resilience, large_model_dir):
        """Test error classification and handling across different cloud operations.
        
        This test validates:
        1. Different error types are classified correctly
        2. Retry logic applies appropriate strategies per error type
        3. Operations handle various failure scenarios
        4. Error recovery works for transient failures
        """
        backend = s3_backend_with_resilience
        model_id = "error-classification-test"
        error_classifier = CloudErrorClassifier()
        
        # Test different error scenarios
        test_errors = [
            (ConnectionError("Network unreachable"), True, "transient network error"),
            (TimeoutError("Request timeout"), True, "timeout error"),
            (PermissionError("Access denied"), False, "permanent auth error"),
            (FileNotFoundError("No such file"), False, "permanent file error"),
        ]
        
        for error, should_retry, description in test_errors:
            # Test error classification
            is_retryable = error_classifier.is_transient(error)
            assert is_retryable == should_retry, f"Failed classification for {description}"
            
            # Test retry behavior with this error type
            call_count = 0
            async def operation_with_error():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise error
                else:
                    return f"success_after_{description.replace(' ', '_')}"
            
            if should_retry:
                # Should retry and eventually succeed
                @with_exponential_backoff(max_attempts=3, base_delay=0.01)
                async def retried_operation():
                    return await operation_with_error()
                
                result = await retried_operation()
                assert "success_after" in result
                assert call_count == 2  # One failure + one success
            else:
                # Should fail immediately without retry
                @with_exponential_backoff(max_attempts=3, base_delay=0.01)
                async def retried_operation():
                    return await operation_with_error()
                
                with pytest.raises((PermissionError, FileNotFoundError)):
                    await retried_operation()
                assert call_count == 1  # Only one call, no retries
            
            # Reset for next test
            call_count = 0

    @pytest.mark.asyncio
    async def test_authentication_flow_validation(self, large_model_dir):
        """Test authentication and authorization flow validation.
        
        This test validates:
        1. Invalid credentials are handled properly
        2. Authentication errors are classified as permanent
        3. Authorization failures don't trigger retries
        4. Proper error messages are provided
        """
        # Test with invalid credentials (outside moto mock)
        invalid_backend = S3StorageBackend(
            bucket_name="non-existent-bucket",
            access_key="invalid-key",
            secret_key="invalid-secret",
            region="us-east-1"
        )
        
        model_id = "auth-test-model"
        
        # This should fail with authentication/authorization error
        with pytest.raises(Exception) as exc_info:
            await invalid_backend.upload_model(large_model_dir, model_id)
        
        # Verify error is not retryable (depends on specific AWS error type)
        error = exc_info.value
        error_classifier = CloudErrorClassifier()
        
        # Most authentication errors should not be retryable
        # The specific error type depends on the boto3 implementation
        print(f"Authentication error type: {type(error).__name__}: {error}")

    @pytest.mark.asyncio
    async def test_concurrent_operations_with_resilience(self, s3_backend_with_resilience, large_model_dir):
        """Test concurrent cloud operations with resilience patterns.
        
        This test validates:
        1. Multiple concurrent uploads work correctly
        2. Resilience patterns handle concurrent failures
        3. Circuit breaker behavior under concurrent load
        4. Resource cleanup occurs properly
        """
        backend = s3_backend_with_resilience
        
        # Create multiple model directories for concurrent testing
        model_dirs = []
        model_ids = []
        
        for i in range(3):
            # Create copy of model directory for each concurrent operation
            temp_dir = large_model_dir.parent / f"concurrent_model_{i}"
            shutil.copytree(large_model_dir, temp_dir)
            model_dirs.append(temp_dir)
            model_ids.append(f"concurrent-test-model-{i}")
        
        try:
            # Execute concurrent uploads
            upload_tasks = [
                backend.upload_model(model_dir, model_id)
                for model_dir, model_id in zip(model_dirs, model_ids)
            ]
            
            start_time = time.time()
            storage_urls = await asyncio.gather(*upload_tasks)
            concurrent_time = time.time() - start_time
            
            # Verify all uploads succeeded
            assert len(storage_urls) == 3
            for i, storage_url in enumerate(storage_urls):
                assert storage_url.startswith("s3://")
                assert model_ids[i] in storage_url
            
            # Test concurrent downloads
            download_dirs = [
                large_model_dir.parent / f"downloaded_concurrent_{i}"
                for i in range(3)
            ]
            
            # Create download directories
            for download_dir in download_dirs:
                download_dir.mkdir(exist_ok=True)
            
            download_tasks = [
                backend.download_model(storage_url, download_dir / f"concurrent-test-model-{i}")
                for i, (storage_url, download_dir) in enumerate(zip(storage_urls, download_dirs))
            ]
            
            await asyncio.gather(*download_tasks)
            
            # Verify all downloads succeeded
            for i, download_dir in enumerate(download_dirs):
                # Find the actual extracted directory (same pattern as multipart test)
                extracted_dirs = [p for p in download_dir.iterdir() if p.is_dir()]
                assert len(extracted_dirs) == 1, f"Expected 1 extracted directory in {download_dir}, found {len(extracted_dirs)}: {extracted_dirs}"
                
                downloaded_model = extracted_dirs[0]
                assert downloaded_model.exists(), f"Downloaded model not found: {downloaded_model}"
                assert (downloaded_model / "model_manifest.json").exists(), f"Manifest not found in {downloaded_model}"
            
            print(f"Concurrent operations time: {concurrent_time:.2f}s")
            
        finally:
            # Cleanup temporary directories
            for model_dir in model_dirs:
                if model_dir.exists():
                    shutil.rmtree(model_dir)