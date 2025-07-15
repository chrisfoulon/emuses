"""
Test FastAPI service HTTP client with robust error handling.

This module tests the HTTP client class for communicating with the EMUSES
FastAPI service, including connection pooling, circuit breaker patterns,
and comprehensive error handling.
"""

import pytest
import pytest_asyncio
import asyncio
import httpx
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, Optional
import time
import json

from emuses.cli.service_client import ServiceHTTPClient, CircuitBreaker, CircuitBreakerError


class TestHTTPClientCore:
    """Test core HTTP client functionality with connection pooling and circuit breaker."""

    def test_http_client_class_creation(self):
        """Test that HTTP client class can be instantiated with proper configuration."""
        # This test will fail until the client class is implemented
        from emuses.cli.service_client import ServiceHTTPClient

        # Test basic instantiation
        client = ServiceHTTPClient(
            base_url="http://localhost:8000",
            timeout=30.0,
            max_retries=3
        )

        assert client is not None, "ServiceHTTPClient should be instantiable"
        assert client.base_url == "http://localhost:8000", "Base URL should be stored"
        assert client.timeout == 30.0, "Timeout should be configurable"
        assert client.max_retries == 3, "Max retries should be configurable"

    @pytest.mark.asyncio
    async def test_connection_pooling_configuration(self):
        """Test that connection pooling is properly configured."""
        from emuses.cli.service_client import ServiceHTTPClient

        client = ServiceHTTPClient(
            base_url="http://localhost:8000",
            pool_connections=20,
            pool_maxsize=100
        )

        # Session should be created when entering context or first used
        async with client:
            # Verify connection pool configuration
            assert hasattr(client, '_session'), "Client should have session attribute"
            assert isinstance(client._session, httpx.AsyncClient), "Session should be httpx AsyncClient"

            # Check connection pool limits (httpx uses _transport attribute)
            assert hasattr(client._session, '_transport'), "Session should have transport"
            # Verify pool configuration is stored in client
            assert client.pool_connections == 20, "Should store pool connections setting"
            assert client.pool_maxsize == 100, "Should store pool maxsize setting"

    def test_circuit_breaker_initialization(self):
        """Test that circuit breaker is properly initialized."""
        from emuses.cli.service_client import ServiceHTTPClient

        client = ServiceHTTPClient(
            base_url="http://localhost:8000",
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=60.0
        )

        assert hasattr(client, '_circuit_breaker'), "Client should have circuit breaker"
        assert client._circuit_breaker.failure_threshold == 5, "Threshold should be configurable"
        assert client._circuit_breaker.reset_timeout == 60.0, "Timeout should be configurable"

    def test_client_initialization_with_defaults(self):
        """Test client initialization with default values."""
        from emuses.cli.service_client import ServiceHTTPClient

        client = ServiceHTTPClient()

        # Verify reasonable defaults
        assert client.base_url == "http://localhost:8000", "Should have default base URL"
        assert client.timeout >= 30.0, "Should have reasonable default timeout"
        assert client.max_retries >= 1, "Should have default retry count"

    @pytest.mark.asyncio
    async def test_session_lifecycle_management(self):
        """Test proper session lifecycle management."""
        from emuses.cli.service_client import ServiceHTTPClient

        client = ServiceHTTPClient()

        # Test context manager usage
        async with client:
            assert client._session is not None, "Session should be active in context"
            assert not client._session.is_closed, "Session should be open"

        # Session should be closed after context exit
        assert client._session.is_closed, "Session should be closed after context exit"

    def test_client_configuration_validation(self):
        """Test validation of client configuration parameters."""
        from emuses.cli.service_client import ServiceHTTPClient

        # Test invalid timeout
        with pytest.raises(ValueError, match="timeout must be positive"):
            ServiceHTTPClient(timeout=-1.0)

        # Test invalid retry count
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            ServiceHTTPClient(max_retries=-1)

        # Test invalid circuit breaker threshold
        with pytest.raises(ValueError, match="circuit_breaker_threshold must be positive"):
            ServiceHTTPClient(circuit_breaker_threshold=0)


class TestCircuitBreakerFunctionality:
    """Test circuit breaker pattern implementation."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self):
        """Test that circuit breaker opens after consecutive failures."""
        from emuses.cli.service_client import ServiceHTTPClient

        client = ServiceHTTPClient(
            base_url="http://localhost:8000",
            circuit_breaker_threshold=3
        )

        # Mock session to simulate failures
        with patch.object(client, '_session') as mock_session:
            mock_session.get = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

            async with client:
                # First 3 failures should be attempted
                for i in range(3):
                    with pytest.raises(httpx.ConnectError):
                        await client.get("/api/health")

                # 4th call should raise CircuitBreakerError
                with pytest.raises(CircuitBreakerError, match="Circuit breaker is open"):
                    await client.get("/api/health")

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_state(self):
        """Test circuit breaker half-open state behavior."""
        from emuses.cli.service_client import ServiceHTTPClient

        client = ServiceHTTPClient(
            base_url="http://localhost:8000",
            circuit_breaker_threshold=2,
            circuit_breaker_timeout=0.1  # Short timeout for testing
        )

        # Mock successful response for recovery test
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}

        async with client:
            with patch.object(client._session, 'request', new_callable=AsyncMock) as mock_request:
                # Simulate failures to open circuit
                mock_request.side_effect = httpx.ConnectError("Connection failed")

                for i in range(2):
                    with pytest.raises(httpx.ConnectError):
                        await client.get("/api/health")

                # Wait for circuit breaker timeout
                await asyncio.sleep(0.2)

                # Next call should attempt connection (half-open state)
                mock_request.side_effect = None
                mock_request.return_value = mock_response

                response = await client.get("/api/health")
                assert response.status_code == 200, "Should succeed in half-open state"


class TestBasicHTTPMethods:
    """Test basic HTTP method implementations."""

    @pytest.mark.asyncio
    async def test_get_method_implementation(self):
        """Test GET method with proper error handling."""
        from emuses.cli.service_client import ServiceHTTPClient

        client = ServiceHTTPClient()

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "success"}

        async with client:
            with patch.object(client._session, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response

                response = await client.get("/api/test")

                assert response.status_code == 200
                mock_request.assert_called_once_with(
                    "GET",
                    "http://localhost:8000/api/test",
                    timeout=client.timeout
                )

    @pytest.mark.asyncio
    async def test_post_method_implementation(self):
        """Test POST method with JSON data."""
        from emuses.cli.service_client import ServiceHTTPClient

        client = ServiceHTTPClient()

        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "123"}

        test_data = {"key": "value"}

        async with client:
            with patch.object(client._session, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response

                response = await client.post("/api/create", json=test_data)

                assert response.status_code == 201
                mock_request.assert_called_once_with(
                    "POST",
                    "http://localhost:8000/api/create",
                    json=test_data,
                    timeout=client.timeout
                )


class TestJobSubmissionMethods:
    """Test job submission methods with API versioning support."""

    @pytest_asyncio.fixture
    async def http_client(self):
        """Create HTTP client for testing."""
        client = ServiceHTTPClient("http://localhost:8000")
        async with client as session_client:
            yield session_client

    @pytest.mark.asyncio
    async def test_submit_full_pipeline_job(self, http_client):
        """Test submitting a full pipeline job with proper API versioning."""
        job_request = {
            "pipeline_type": "full",
            "features_file": "/path/to/features.csv",
            "scores_file": "/path/to/scores.csv",
            "output_folder": "/path/to/output",
            "parameters": {
                "umap_trials": 10,
                "hdbscan_trials": 5,
                "random_state": 42
            }
        }

        mock_response = httpx.Response(
            status_code=201,
            json={"job_id": "test-job-123", "status": "queued"},
            request=httpx.Request("POST", "http://localhost:8000/api/v1/jobs/pipeline/full")
        )

        with patch.object(http_client._session, "request", return_value=mock_response) as mock_request:
            result = await http_client.submit_pipeline_job("full", job_request)

            # Verify API versioning
            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args
            assert args[0] == "POST"
            assert "/api/v1/jobs/pipeline/full" in args[1]
            assert kwargs["json"] == job_request

            # Verify response processing
            assert result["job_id"] == "test-job-123"
            assert result["status"] == "queued"

    @pytest.mark.asyncio
    async def test_submit_stage_specific_job(self, http_client):
        """Test submitting stage-specific jobs (umap, clustering, etc.)."""
        stage_types = ["umap", "clustering", "heatmap", "prediction"]

        for stage in stage_types:
            job_request = {
                "stage": stage,
                "input_file": f"/path/to/{stage}_input.csv",
                "parameters": {"test_param": "value"}
            }

            mock_response = httpx.Response(
                status_code=201,
                json={"job_id": f"{stage}-job-456", "stage": stage},
                request=httpx.Request("POST", f"http://localhost:8000/api/v1/jobs/stage/{stage}")
            )

            with patch.object(http_client._session, "request", return_value=mock_response) as mock_request:
                result = await http_client.submit_stage_job(stage, job_request)

                # Verify correct endpoint construction
                mock_request.assert_called_once()
                args, kwargs = mock_request.call_args
                assert f"/api/v1/jobs/stage/{stage}" in args[1]

                assert result["job_id"] == f"{stage}-job-456"
                assert result["stage"] == stage

    @pytest.mark.asyncio
    async def test_api_version_configuration(self, http_client):
        """Test API version configuration and endpoint construction."""
        # Test default API version
        assert http_client.api_version == "v1"

        # Test custom API version
        custom_client = ServiceHTTPClient("http://localhost:8000", api_version="v2")
        await custom_client.__aenter__()

        try:
            assert custom_client.api_version == "v2"

            job_request = {"test": "data"}
            mock_response = httpx.Response(
                status_code=201,
                json={"success": True},
                request=httpx.Request("POST", "http://localhost:8000/api/v2/jobs/pipeline/full")
            )

            with patch.object(custom_client._session, "request", return_value=mock_response) as mock_request:
                await custom_client.submit_pipeline_job("full", job_request)

                args, kwargs = mock_request.call_args
                assert "/api/v2/jobs/pipeline/full" in args[1]

        finally:
            await custom_client.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_job_submission_error_handling(self, http_client):
        """Test error handling for job submission failures."""
        job_request = {"invalid": "request"}

        # Test HTTP error responses
        mock_response = httpx.Response(
            status_code=400,
            json={"error": "Invalid job request", "details": "Missing required fields"},
            request=httpx.Request("POST", "http://localhost:8000/api/v1/jobs/pipeline/full")
        )

        with patch.object(http_client._session, "request", return_value=mock_response):
            with pytest.raises(httpx.HTTPStatusError):
                await http_client.submit_pipeline_job("full", job_request)

    @pytest.mark.asyncio
    async def test_job_submission_with_file_uploads(self, http_client):
        """Test job submission with file upload support."""
        files = {
            "features": ("features.csv", b"feature,data\n1,2\n3,4", "text/csv"),
            "scores": ("scores.csv", b"score\n0.5\n0.8", "text/csv")
        }

        job_request = {
            "pipeline_type": "full",
            "parameters": {"test": "value"}
        }

        mock_response = httpx.Response(
            status_code=201,
            json={"job_id": "upload-job-789", "files_uploaded": 2},
            request=httpx.Request("POST", "http://localhost:8000/api/v1/jobs/pipeline/full")
        )

        with patch.object(http_client._session, "request", return_value=mock_response) as mock_request:
            result = await http_client.submit_pipeline_job("full", job_request, files=files)

            # Verify files were included in request
            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args
            assert "files" in kwargs
            assert kwargs["files"] == files

            assert result["job_id"] == "upload-job-789"
            assert result["files_uploaded"] == 2

    @pytest.mark.asyncio
    async def test_job_request_validation(self, http_client):
        """Test job request validation before submission."""
        # Test empty request
        with pytest.raises(ValueError, match="Job request cannot be empty"):
            await http_client.submit_pipeline_job("full", {})

        # Test None request
        with pytest.raises(ValueError, match="Job request cannot be None"):
            await http_client.submit_pipeline_job("full", None)

        # Test invalid pipeline type
        with pytest.raises(ValueError, match="Invalid pipeline type"):
            await http_client.submit_pipeline_job("invalid_type", {"test": "data"})

        # Test invalid stage type
        with pytest.raises(ValueError, match="Invalid stage type"):
            await http_client.submit_stage_job("invalid_stage", {"test": "data"})


class TestJobStatusPolling:
    """Test job status polling with rate limiting and concurrent handling."""

    @pytest_asyncio.fixture
    async def http_client(self):
        """Create HTTP client for testing."""
        client = ServiceHTTPClient("http://localhost:8000")
        async with client as session_client:
            yield session_client

    @pytest.mark.asyncio
    async def test_get_job_status_basic(self, http_client):
        """Test basic job status retrieval."""
        job_id = "test-job-123"

        mock_response = httpx.Response(
            status_code=200,
            json={
                "job_id": job_id,
                "status": "running",
                "progress": 45.5,
                "created_at": "2025-07-13T10:00:00Z",
                "updated_at": "2025-07-13T10:05:00Z"
            },
            request=httpx.Request("GET", f"http://localhost:8000/api/v1/jobs/{job_id}/status")
        )

        with patch.object(http_client._session, "request", return_value=mock_response) as mock_request:
            result = await http_client.get_job_status(job_id)

            # Verify API endpoint construction
            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args
            assert args[0] == "GET"
            assert f"/api/v1/jobs/{job_id}/status" in args[1]

            # Verify response processing
            assert result["job_id"] == job_id
            assert result["status"] == "running"
            assert result["progress"] == 45.5

    @pytest.mark.asyncio
    async def test_poll_job_until_completion(self, http_client):
        """Test polling job status until completion with rate limiting."""
        job_id = "test-job-456"

        # Mock sequence of status responses
        status_responses = [
            {"job_id": job_id, "status": "queued", "progress": 0},
            {"job_id": job_id, "status": "running", "progress": 25},
            {"job_id": job_id, "status": "running", "progress": 75},
            {"job_id": job_id, "status": "completed", "progress": 100}
        ]

        mock_responses = []
        for status_data in status_responses:
            mock_responses.append(httpx.Response(
                status_code=200,
                json=status_data,
                request=httpx.Request("GET", f"http://localhost:8000/api/v1/jobs/{job_id}/status")
            ))

        with patch.object(http_client._session, "request", side_effect=mock_responses) as mock_request:
            # Test with short polling interval for testing
            result = await http_client.poll_job_until_completion(
                job_id,
                poll_interval=0.1,  # 100ms for testing
                timeout=5.0
            )

            # Verify polling behavior
            assert mock_request.call_count == 4  # 4 status checks
            assert result["status"] == "completed"
            assert result["progress"] == 100

    @pytest.mark.asyncio
    async def test_poll_job_timeout(self, http_client):
        """Test polling timeout when job doesn't complete."""
        job_id = "test-job-timeout"

        # Always return running status
        mock_response = httpx.Response(
            status_code=200,
            json={"job_id": job_id, "status": "running", "progress": 50},
            request=httpx.Request("GET", f"http://localhost:8000/api/v1/jobs/{job_id}/status")
        )

        with patch.object(http_client._session, "request", return_value=mock_response):
            with pytest.raises(asyncio.TimeoutError):
                await http_client.poll_job_until_completion(
                    job_id,
                    poll_interval=0.1,
                    timeout=0.5  # Short timeout for testing
                )

    @pytest.mark.asyncio
    async def test_concurrent_job_polling(self, http_client):
        """Test concurrent polling of multiple jobs with rate limiting."""
        job_ids = ["job-1", "job-2", "job-3"]

        # Mock responses for each job
        def create_mock_response(job_id):
            return httpx.Response(
                status_code=200,
                json={"job_id": job_id, "status": "completed", "progress": 100},
                request=httpx.Request("GET", f"http://localhost:8000/api/v1/jobs/{job_id}/status")
            )

        mock_responses = [create_mock_response(job_id) for job_id in job_ids]

        with patch.object(http_client._session, "request", side_effect=mock_responses) as mock_request:
            # Poll all jobs concurrently
            results = await http_client.poll_multiple_jobs(
                job_ids,
                poll_interval=0.1,
                timeout=5.0,
                max_concurrent=2  # Rate limiting
            )

            # Verify all jobs completed
            assert len(results) == 3
            for job_id in job_ids:
                assert job_id in results
                assert results[job_id]["status"] == "completed"

            # Verify rate limiting (should have made 3 calls total)
            assert mock_request.call_count == 3

    @pytest.mark.asyncio
    async def test_rate_limiting_configuration(self, http_client):
        """Test rate limiting configuration and enforcement."""
        # Test default rate limiting
        assert hasattr(http_client, '_rate_limiter')

        # Test custom rate limiting
        custom_client = ServiceHTTPClient(
            "http://localhost:8000",
            rate_limit_per_second=5.0,
            max_concurrent_requests=3
        )
        async with custom_client as session_client:
            assert session_client._rate_limiter.max_requests_per_second == 5.0
            assert session_client._max_concurrent == 3

    @pytest.mark.asyncio
    async def test_job_status_error_handling(self, http_client):
        """Test error handling for job status operations."""
        job_id = "nonexistent-job"

        # Test 404 response
        mock_response = httpx.Response(
            status_code=404,
            json={"error": "Job not found"},
            request=httpx.Request("GET", f"http://localhost:8000/api/v1/jobs/{job_id}/status")
        )

        with patch.object(http_client._session, "request", return_value=mock_response):
            with pytest.raises(httpx.HTTPStatusError):
                await http_client.get_job_status(job_id)

    @pytest.mark.asyncio
    async def test_job_status_caching(self, http_client):
        """Test job status caching to reduce API calls."""
        job_id = "test-job-cache"

        mock_response = httpx.Response(
            status_code=200,
            json={"job_id": job_id, "status": "completed", "progress": 100},
            request=httpx.Request("GET", f"http://localhost:8000/api/v1/jobs/{job_id}/status")
        )

        with patch.object(http_client._session, "request", return_value=mock_response) as mock_request:
            # Get status twice quickly
            result1 = await http_client.get_job_status(job_id, use_cache=True)
            result2 = await http_client.get_job_status(job_id, use_cache=True)

            # Should only make one API call due to caching
            assert mock_request.call_count == 1
            assert result1 == result2


class TestServiceStartupShutdown:
    """Test service startup/shutdown with offline fallback mode."""

    @pytest.mark.asyncio
    async def test_service_health_check_basic(self):
        """Test basic service health check functionality."""
        from emuses.cli.service_client import ServiceHTTPClient

        client = ServiceHTTPClient(
            base_url="http://localhost:8000",
            timeout=5.0
        )

        # Mock successful health check response
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy", "version": "1.0.0"}
            mock_get.return_value = mock_response

            async with client:
                health_status = await client.check_service_health()

            assert health_status is True, "Health check should return True for healthy service"
            mock_get.assert_called_once_with("http://localhost:8000/api/health", timeout=5.0)

    @pytest.mark.asyncio
    async def test_service_health_check_unhealthy(self):
        """Test service health check when service is unhealthy."""
        from emuses.cli.service_client import ServiceHTTPClient

        client = ServiceHTTPClient(
            base_url="http://localhost:8000",
            timeout=5.0
        )

        # Mock unhealthy service response
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 503
            mock_response.json.return_value = {"status": "unhealthy", "error": "Database connection failed"}
            mock_get.return_value = mock_response

            async with client:
                health_status = await client.check_service_health()

            assert health_status is False, "Health check should return False for unhealthy service"

    @pytest.mark.asyncio
    async def test_service_health_check_connection_error(self):
        """Test service health check when service is completely unavailable."""
        from emuses.cli.service_client import ServiceHTTPClient

        client = ServiceHTTPClient(
            base_url="http://localhost:8000",
            timeout=5.0
        )

        # Mock connection error (service unavailable)
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection failed")

            async with client:
                health_status = await client.check_service_health()

            assert health_status is False, "Health check should return False when service is unavailable"

    @pytest.mark.asyncio
    async def test_offline_fallback_mode_activation(self):
        """Test that offline fallback mode is properly activated when service is unavailable."""
        from emuses.cli.service_client import ServiceHTTPClient

        client = ServiceHTTPClient(
            base_url="http://localhost:8000",
            enable_offline_fallback=True
        )

        # Mock connection error to trigger offline mode
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.ConnectError("Service unavailable")

            async with client:
                # Attempt health check should trigger offline mode
                health_status = await client.check_service_health()

                # Verify offline mode is activated
                assert health_status is False, "Health check should fail"
                assert client.is_offline_mode is True, "Client should be in offline mode"
                assert client.offline_reason is not None, "Offline reason should be set"

    @pytest.mark.asyncio
    async def test_offline_fallback_mode_behavior(self):
        """Test behavior of client when in offline fallback mode."""
        from emuses.cli.service_client import ServiceHTTPClient, ServiceClientError

        client = ServiceHTTPClient(
            base_url="http://localhost:8000",
            enable_offline_fallback=True
        )

        # Manually activate offline mode
        client._activate_offline_mode("Service unavailable for testing")

        async with client:
            # Job submission should raise appropriate error in offline mode
            with pytest.raises(ServiceClientError, match="Service is in offline mode"):
                await client.submit_pipeline_job("full", {
                    "input_file": "test.csv",
                    "output_folder": "/tmp/test"
                })

            # Job status polling should raise appropriate error in offline mode
            with pytest.raises(ServiceClientError, match="Service is in offline mode"):
                await client.get_job_status("test-job-id")

    @pytest.mark.asyncio
    async def test_service_recovery_detection(self):
        """Test detection of service recovery from offline mode."""
        from emuses.cli.service_client import ServiceHTTPClient

        client = ServiceHTTPClient(
            base_url="http://localhost:8000",
            enable_offline_fallback=True,
            health_check_interval=1.0  # Quick interval for testing
        )

        # Start in offline mode
        client._activate_offline_mode("Initial offline state")
        assert client.is_offline_mode is True

        # Mock successful health check on recovery attempt
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            mock_get.return_value = mock_response

            async with client:
                # Attempt recovery
                recovery_success = await client.attempt_service_recovery()

                assert recovery_success is True, "Service recovery should succeed"
                assert client.is_offline_mode is False, "Client should exit offline mode"
                assert client.offline_reason is None, "Offline reason should be cleared"

    @pytest.mark.asyncio
    async def test_graceful_degradation_with_retry(self):
        """Test graceful degradation with retry logic before going offline."""
        from emuses.cli.service_client import ServiceHTTPClient

        client = ServiceHTTPClient(
            base_url="http://localhost:8000",
            enable_offline_fallback=True,
            max_retries_before_offline=3
        )

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # First 2 calls fail
                raise httpx.ConnectError("Temporary connection issue")
            # Third call succeeds
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            return mock_response

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = side_effect

            async with client:
                health_status = await client.check_service_health()

                # Should succeed after retries
                assert health_status is True, "Health check should succeed after retries"
                assert client.is_offline_mode is False, "Client should not be in offline mode"
                assert call_count == 3, "Should have retried exactly 3 times"


class TestComprehensiveErrorHandlingRetryTimeout:
    """Test comprehensive error handling, retry logic, and timeout management (Task 3.5)."""

    @pytest.fixture
    def http_client(self):
        """Create HTTP client for comprehensive error handling tests."""
        return ServiceHTTPClient(
            base_url="http://localhost:8000",
            timeout=5.0,
            max_retries=3,
            retry_backoff_factor=1.5,
            max_retry_delay=10.0,
            enable_request_timeout_scaling=True,
            enable_advanced_error_categorization=True
        )

    @pytest.mark.asyncio
    async def test_exponential_backoff_retry_logic(self, http_client):
        """Test exponential backoff retry logic with configurable parameters."""
        call_times = []

        def side_effect(*args, **kwargs):
            call_times.append(time.time())
            if len(call_times) <= 2:  # First 2 calls fail
                raise httpx.ConnectError("Temporary connection issue")
            # Third call succeeds
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"job_id": "test-123"}
            return mock_response

        with patch('httpx.AsyncClient.request') as mock_request:
            mock_request.side_effect = side_effect

            async with http_client:
                response = await http_client.get("/api/v1/jobs/test")

                # Should succeed after retries
                assert response.status_code == 200
                assert len(call_times) == 3, "Should have retried exactly 3 times"

                # Check exponential backoff timing
                if len(call_times) >= 3:
                    delay1 = call_times[1] - call_times[0]
                    delay2 = call_times[2] - call_times[1]

                    # Delay should increase exponentially (with some tolerance for test timing)
                    assert delay2 > delay1 * 1.2, f"Exponential backoff not working: delay1={delay1:.2f}s, delay2={delay2:.2f}s"
                    assert delay2 < 10.0, "Delay should be capped at max_retry_delay"

    @pytest.mark.asyncio
    async def test_timeout_scaling_for_retry_attempts(self, http_client):
        """Test that timeout increases for retry attempts."""
        call_count = 0
        timeout_values = []

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Record timeout value from kwargs
            if 'timeout' in kwargs:
                timeout_values.append(kwargs['timeout'])

            if call_count <= 2:  # First 2 calls timeout
                raise httpx.TimeoutException("Request timeout")
            # Third call succeeds
            mock_response = Mock()
            mock_response.status_code = 200
            return mock_response

        with patch('httpx.AsyncClient.request') as mock_request:
            mock_request.side_effect = side_effect

            async with http_client:
                response = await http_client.get("/api/v1/jobs/test")

                assert response.status_code == 200
                assert len(timeout_values) >= 2, "Should have recorded timeout values"

                # Timeout should scale up for retries
                if len(timeout_values) >= 2:
                    assert timeout_values[1] > timeout_values[0], "Timeout should increase for retries"

    @pytest.mark.asyncio
    async def test_error_categorization_and_retry_decisions(self, http_client):
        """Test advanced error categorization for retry decisions."""
        # Test different error types and their retry behavior

        # Non-retryable error (4xx client error)
        with patch('httpx.AsyncClient.request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not Found", request=Mock(), response=mock_response
            )
            mock_request.return_value = mock_response

            async with http_client:
                with pytest.raises(httpx.HTTPStatusError):
                    await http_client.get("/api/v1/jobs/nonexistent")

                # Should not retry 4xx errors
                assert mock_request.call_count == 1, "Should not retry 4xx client errors"

        # Retryable error (5xx server error)
        mock_request.reset_mock()
        call_count = 0

        def server_error_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # First 2 calls fail with server error
                mock_response = Mock()
                mock_response.status_code = 503
                mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "Service Unavailable", request=Mock(), response=mock_response
                )
                return mock_response
            # Third call succeeds
            mock_response = Mock()
            mock_response.status_code = 200
            return mock_response

        with patch('httpx.AsyncClient.request') as mock_request:
            mock_request.side_effect = server_error_side_effect

            async with http_client:
                response = await http_client.get("/api/v1/jobs/test")

                assert response.status_code == 200
                assert call_count == 3, "Should retry 5xx server errors"

    @pytest.mark.asyncio
    async def test_concurrent_request_rate_limiting(self, http_client):
        """Test rate limiting for concurrent requests."""
        request_times = []

        def side_effect(*args, **kwargs):
            request_times.append(time.time())
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok"}
            return mock_response

        with patch('httpx.AsyncClient.request') as mock_request:
            mock_request.side_effect = side_effect

            async with http_client:
                # Configure rate limiting (e.g., max 5 requests per second)
                http_client.configure_rate_limiting(max_requests_per_second=5.0)

                # Make multiple concurrent requests
                tasks = []
                for i in range(10):
                    task = asyncio.create_task(http_client.get(f"/api/v1/jobs/{i}"))
                    tasks.append(task)

                responses = await asyncio.gather(*tasks)

                # All requests should succeed
                assert len(responses) == 10
                assert all(r.status_code == 200 for r in responses)

                # Check rate limiting timing
                if len(request_times) >= 2:
                    time_span = request_times[-1] - request_times[0]
                    # With 5 requests per second and 10 requests, minimum time should be ~1.8 seconds
                    # But allow some tolerance for test timing and overlapping requests
                    expected_min_time = (len(request_times) - 5) / 5.0  # First 5 can be immediate
                    assert time_span >= expected_min_time * 0.5, f"Rate limiting should throttle requests: got {time_span:.3f}s, expected >= {expected_min_time * 0.5:.3f}s"

    @pytest.mark.asyncio
    async def test_request_queuing_and_batching(self, http_client):
        """Test request queuing and batching capabilities."""
        request_count = 0

        def side_effect(*args, **kwargs):
            nonlocal request_count
            request_count += 1
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"batch_id": f"batch-{request_count}"}
            return mock_response

        with patch('httpx.AsyncClient.request') as mock_request:
            mock_request.side_effect = side_effect

            async with http_client:
                # Enable request batching
                http_client.enable_request_batching(batch_size=3, max_wait_time=1.0)

                # Submit multiple requests that should be queued
                batch_requests = []
                for i in range(5):
                    request = http_client.queue_batch_request("GET", f"/api/v1/jobs/{i}")
                    batch_requests.append(request)

                # Verify requests are queued
                assert len(batch_requests) == 5, "All requests should be queued"
                assert len(http_client._batched_requests) == 5, "Requests should be stored in batch queue"

                # Process batched requests
                responses = await http_client.process_batched_requests()

                assert len(responses) == 5, "All requests should be processed"
                assert request_count == 5, "Each request should result in one HTTP call"

                # Verify batch queue is cleared after processing
                assert len(http_client._batched_requests) == 0, "Batch queue should be cleared"

    @pytest.mark.asyncio
    async def test_adaptive_timeout_management(self, http_client):
        """Test adaptive timeout management based on request history."""

        def side_effect(*args, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            return mock_response

        with patch('httpx.AsyncClient.request') as mock_request:
            mock_request.side_effect = side_effect

            async with http_client:
                # Manually set up response time history to simulate previous requests
                http_client._request_response_times = [0.5, 0.7, 0.9]  # Increasing response times

                # Enable adaptive timeout management
                http_client.enable_adaptive_timeout_management(
                    min_timeout=1.0,
                    max_timeout=30.0,
                    timeout_adjustment_factor=1.5
                )

                # Test adaptive timeout calculation
                current_timeout = http_client.get_current_adaptive_timeout()
                assert current_timeout >= 1.0, "Timeout should be at least minimum"
                assert current_timeout <= 30.0, "Timeout should not exceed maximum"

                # With response times [0.5, 0.7, 0.9], average is 0.7, so timeout should be 0.7 * 1.5 = 1.05
                # But clamped to minimum of 1.0
                expected_timeout = max(0.7 * 1.5, 1.0)  # Should be 1.05, clamped to 1.0 minimum
                assert abs(current_timeout - expected_timeout) < 0.1, f"Expected timeout ~{expected_timeout}, got {current_timeout}"

    @pytest.mark.asyncio
    async def test_comprehensive_error_recovery_scenarios(self, http_client):
        """Test comprehensive error recovery scenarios with different failure types."""

        # Test 1: Network failure recovery (should retry and succeed)
        call_count = 0

        def network_failure_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # First 2 calls fail
                raise httpx.ConnectError("Network unreachable")
            # Third call succeeds
            mock_response = Mock()
            mock_response.status_code = 200
            return mock_response

        with patch('httpx.AsyncClient.request') as mock_request:
            mock_request.side_effect = network_failure_side_effect
            async with http_client:
                response = await http_client.get("/api/v1/test")
                assert response.status_code == 200
                assert call_count == 3, "Should retry network failures"

        # Test 2: SSL/TLS failure (should not retry with advanced categorization)
        call_count = 0

        def ssl_failure_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise httpx.ConnectError("SSL handshake failed")

        with patch('httpx.AsyncClient.request') as mock_request:
            mock_request.side_effect = ssl_failure_side_effect
            async with http_client:
                with pytest.raises(httpx.ConnectError):
                    await http_client.get("/api/v1/test")
                assert call_count == 1, "Should not retry SSL failures"

        # Test 3: Timeout recovery (should retry and succeed)
        call_count = 0

        def timeout_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # First 2 calls timeout
                raise httpx.TimeoutException("Request timeout")
            # Third call succeeds
            mock_response = Mock()
            mock_response.status_code = 200
            return mock_response

        with patch('httpx.AsyncClient.request') as mock_request:
            mock_request.side_effect = timeout_side_effect
            async with http_client:
                response = await http_client.get("/api/v1/test")
                assert response.status_code == 200
                assert call_count == 3, "Should retry timeout failures"
