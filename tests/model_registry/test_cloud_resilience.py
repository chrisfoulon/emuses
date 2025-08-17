"""Tests for cloud storage resilience and error handling.

This module tests retry logic, error categorization, timeout handling,
and circuit breaker patterns for cloud storage operations.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import shutil
import json
import time
from typing import Optional, Dict, Any

# Test will fail initially - imports don't exist yet
try:
    from emuses.tools.cloud_resilience import (
        CloudErrorClassifier,
        RetryConfig,
        CloudOperationTimeout,
        CircuitBreakerError
    )
    RESILIENCE_MODULE_AVAILABLE = True
except ImportError:
    RESILIENCE_MODULE_AVAILABLE = False

from emuses.tools.cloud_storage import S3StorageBackend


@pytest.mark.skipif(not RESILIENCE_MODULE_AVAILABLE, reason="Cloud resilience module not implemented")
class TestCloudErrorClassification:
    """Test cloud error classification and categorization."""

    @pytest.fixture
    def error_classifier(self):
        """Create error classifier for testing."""
        return CloudErrorClassifier()

    def test_transient_error_identification(self, error_classifier):
        """Test identification of transient errors that should be retried.
        
        This test validates that:
        1. Network errors are classified as transient
        2. Timeout errors are classified as transient
        3. Rate limit errors are classified as transient
        4. Server errors (5xx) are classified as transient
        """
        # Network-related errors
        assert error_classifier.is_transient(ConnectionError("Network unreachable"))
        assert error_classifier.is_transient(TimeoutError("Request timeout"))
        
        # HTTP errors that should be retried
        from requests.exceptions import HTTPError
        http_500 = HTTPError()
        http_500.response = MagicMock()
        http_500.response.status_code = 500
        assert error_classifier.is_transient(http_500)
        
        http_502 = HTTPError()
        http_502.response = MagicMock()
        http_502.response.status_code = 502
        assert error_classifier.is_transient(http_502)
        
        http_429 = HTTPError()
        http_429.response = MagicMock()
        http_429.response.status_code = 429  # Rate limit
        assert error_classifier.is_transient(http_429)

    def test_permanent_error_identification(self, error_classifier):
        """Test identification of permanent errors that should NOT be retried.
        
        This test validates that:
        1. Authentication errors are classified as permanent
        2. Permission errors are classified as permanent
        3. Client errors (4xx except 429) are classified as permanent
        4. Invalid parameter errors are classified as permanent
        """
        # Authentication and permission errors
        assert not error_classifier.is_transient(PermissionError("Access denied"))
        
        # HTTP client errors that should not be retried
        from requests.exceptions import HTTPError
        http_401 = HTTPError()
        http_401.response = MagicMock()
        http_401.response.status_code = 401  # Unauthorized
        assert not error_classifier.is_transient(http_401)
        
        http_403 = HTTPError()
        http_403.response = MagicMock()
        http_403.response.status_code = 403  # Forbidden
        assert not error_classifier.is_transient(http_403)
        
        http_404 = HTTPError()
        http_404.response = MagicMock()
        http_404.response.status_code = 404  # Not found
        assert not error_classifier.is_transient(http_404)

    def test_cloud_provider_specific_errors(self, error_classifier):
        """Test classification of cloud provider specific errors."""
        # AWS S3 specific errors
        from botocore.exceptions import ClientError
        s3_throttling = ClientError(
            error_response={'Error': {'Code': 'SlowDown'}},
            operation_name='PutObject'
        )
        assert error_classifier.is_transient(s3_throttling)
        
        s3_no_such_bucket = ClientError(
            error_response={'Error': {'Code': 'NoSuchBucket'}},
            operation_name='PutObject'
        )
        assert not error_classifier.is_transient(s3_no_such_bucket)


@pytest.mark.skipif(not RESILIENCE_MODULE_AVAILABLE, reason="Cloud resilience module not implemented")
class TestExponentialBackoffRetry:
    """Test exponential backoff retry logic implementation."""

    @pytest.fixture
    def temp_model_dir(self):
        """Create temporary model directory for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create model structure
        model_dir = temp_dir / "test-retry-model"
        model_dir.mkdir()
        
        # Create manifest file
        manifest = {"name": "test-retry-model", "version": "1.0.0"}
        (model_dir / "model_manifest.json").write_text(json.dumps(manifest))
        
        yield model_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_successful_operation_no_retry(self):
        """Test that successful operations don't trigger retry logic."""
        # Create a mock that succeeds on first call
        mock_operation = AsyncMock(return_value="success")
        
        # Apply retry decorator (will be implemented)
        from emuses.tools.cloud_resilience import with_exponential_backoff
        
        retried_operation = with_exponential_backoff(
            max_attempts=3,
            base_delay=0.1,
            max_delay=1.0
        )(mock_operation)
        
        # Execute operation
        start_time = time.time()
        result = await retried_operation()
        execution_time = time.time() - start_time
        
        # Verify
        assert result == "success"
        assert mock_operation.call_count == 1
        assert execution_time < 0.2  # No delay for successful operation

    @pytest.mark.asyncio
    async def test_transient_failure_with_eventual_success(self):
        """Test retry logic with transient failures that eventually succeed."""
        # Create a mock that fails twice then succeeds
        mock_operation = AsyncMock(side_effect=[
            ConnectionError("Network error"),
            TimeoutError("Request timeout"),
            "success"
        ])
        
        from emuses.tools.cloud_resilience import with_exponential_backoff
        
        retried_operation = with_exponential_backoff(
            max_attempts=5,
            base_delay=0.01,  # Small delay for test speed
            max_delay=0.1
        )(mock_operation)
        
        # Execute operation
        start_time = time.time()
        result = await retried_operation()
        execution_time = time.time() - start_time
        
        # Verify
        assert result == "success"
        assert mock_operation.call_count == 3
        assert execution_time > 0.01  # Should have some delay from retries

    @pytest.mark.asyncio
    async def test_permanent_failure_no_retry(self):
        """Test that permanent errors are not retried."""
        # Create a mock that raises a permanent error
        mock_operation = AsyncMock(side_effect=PermissionError("Access denied"))
        
        from emuses.tools.cloud_resilience import with_exponential_backoff
        
        retried_operation = with_exponential_backoff(
            max_attempts=5,
            base_delay=0.01,
            max_delay=0.1
        )(mock_operation)
        
        # Execute operation - should fail immediately
        with pytest.raises(PermissionError):
            await retried_operation()
        
        # Verify no retries occurred
        assert mock_operation.call_count == 1

    @pytest.mark.asyncio
    async def test_max_attempts_exhausted(self):
        """Test behavior when maximum retry attempts are exhausted."""
        # Create a mock that always fails with transient error
        mock_operation = AsyncMock(side_effect=ConnectionError("Network error"))
        
        from emuses.tools.cloud_resilience import with_exponential_backoff
        
        retried_operation = with_exponential_backoff(
            max_attempts=3,
            base_delay=0.01,
            max_delay=0.1
        )(mock_operation)
        
        # Execute operation - should fail after max attempts
        with pytest.raises(ConnectionError):
            await retried_operation()
        
        # Verify all attempts were used
        assert mock_operation.call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """Test that retry delays follow exponential backoff pattern."""
        call_times = []
        
        def record_call_time():
            call_times.append(time.time())
            raise ConnectionError("Network error")
        
        mock_operation = AsyncMock(side_effect=record_call_time)
        
        from emuses.tools.cloud_resilience import with_exponential_backoff
        
        retried_operation = with_exponential_backoff(
            max_attempts=4,
            base_delay=0.1,
            max_delay=1.0
        )(mock_operation)
        
        # Execute operation - will fail after all attempts
        with pytest.raises(ConnectionError):
            await retried_operation()
        
        # Analyze timing
        assert len(call_times) == 4
        
        # Calculate delays between calls
        delays = [call_times[i+1] - call_times[i] for i in range(len(call_times)-1)]
        
        # Verify exponential pattern (allowing for some variance)
        assert delays[0] >= 0.08  # ~0.1s base delay
        assert delays[1] >= 0.18  # ~0.2s second delay
        assert delays[2] >= 0.35  # ~0.4s third delay


@pytest.mark.skipif(not RESILIENCE_MODULE_AVAILABLE, reason="Cloud resilience module not implemented")
class TestS3BackendWithRetry:
    """Test S3 backend integration with retry logic."""

    @pytest.fixture
    def s3_backend_with_retry(self):
        """Create S3 backend with retry capabilities."""
        # Will be updated once resilience module is implemented
        backend = S3StorageBackend(
            bucket_name="test-bucket",
            access_key="test-key", 
            secret_key="test-secret",
            region="us-east-1"
        )
        
        # Apply retry capabilities (placeholder - will be implemented)
        from emuses.tools.cloud_resilience import add_retry_capabilities
        return add_retry_capabilities(backend)

    @pytest.mark.asyncio
    async def test_s3_upload_with_transient_failure_recovery(self, s3_backend_with_retry):
        """Test S3 upload that recovers from transient failures."""
        # This test will validate end-to-end retry integration
        # Implementation depends on resilience module
        pytest.skip("Integration test - implement after resilience module is ready")


@pytest.mark.skipif(not RESILIENCE_MODULE_AVAILABLE, reason="Cloud resilience module not implemented")
class TestTimeoutHandling:
    """Test timeout configuration and handling."""

    def test_timeout_configuration_validation(self):
        """Test validation of timeout configuration values."""
        from emuses.tools.cloud_resilience import CloudOperationTimeout
        
        # Valid configuration
        timeout = CloudOperationTimeout(
            connection_timeout=10,
            read_timeout=30,
            total_timeout=300
        )
        assert timeout.connection_timeout == 10
        assert timeout.read_timeout == 30
        assert timeout.total_timeout == 300
        
        # Invalid configuration - total < read + connection
        with pytest.raises(ValueError):
            CloudOperationTimeout(
                connection_timeout=10,
                read_timeout=30,
                total_timeout=20  # Too small
            )


@pytest.mark.skipif(not RESILIENCE_MODULE_AVAILABLE, reason="Cloud resilience module not implemented")
class TestCircuitBreakerPattern:
    """Test circuit breaker implementation."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_threshold(self):
        """Test circuit breaker opens after failure threshold is reached."""
        from emuses.tools.cloud_resilience import CircuitBreaker, CircuitBreakerError
        
        # Create circuit breaker with low threshold for testing
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=1.0
        )
        
        mock_operation = AsyncMock(side_effect=ConnectionError("Service down"))
        
        # First 3 calls should execute and fail
        for i in range(3):
            with pytest.raises(ConnectionError):
                await circuit_breaker.execute(mock_operation)
        
        # 4th call should be blocked by circuit breaker
        with pytest.raises(CircuitBreakerError):
            await circuit_breaker.execute(mock_operation)
        
        # Verify circuit breaker blocked the call
        assert mock_operation.call_count == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery after timeout period."""
        from emuses.tools.cloud_resilience import CircuitBreaker
        
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1  # Short timeout for testing
        )
        
        # Mock that fails initially then succeeds
        mock_operation = AsyncMock(side_effect=[
            ConnectionError("Fail 1"),
            ConnectionError("Fail 2"), 
            "success"  # After recovery
        ])
        
        # Trigger circuit breaker opening
        for i in range(2):
            with pytest.raises(ConnectionError):
                await circuit_breaker.execute(mock_operation)
        
        # Wait for recovery period
        await asyncio.sleep(0.15)
        
        # Should allow one test call and succeed
        result = await circuit_breaker.execute(mock_operation)
        assert result == "success"
        assert mock_operation.call_count == 3