"""
HTTP client for EMUSES FastAPI service with robust error handling.

This module provides a comprehensive HTTP client class for communicating with the
EMUSES FastAPI service, featuring connection pooling, circuit breaker patterns,
retry logic, and comprehensive error handling.

Key Features:
- Connection pooling for efficient resource usage
- Circuit breaker pattern for resilience
- Retry logic with exponential backoff
- Timeout management and error handling
- Async/await support with proper session lifecycle
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union
from urllib.parse import urljoin, urlparse

import httpx
from fastapi.testclient import TestClient

logger = logging.getLogger(__name__)


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""

    pass


class ServiceClientError(Exception):
    """Base exception for service client errors."""

    pass


@dataclass
class CircuitBreakerState:
    """Circuit breaker state management."""

    failure_count: int = 0
    last_failure_time: Optional[float] = None
    state: str = "closed"  # closed, open, half-open


class CircuitBreaker:
    """Circuit breaker implementation for HTTP client."""

    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 60.0):
        """
        Initialize circuit breaker.

        Parameters
        ----------
        failure_threshold : int
            Number of failures before opening the circuit
        reset_timeout : float
            Time in seconds before attempting to reset the circuit
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.state = CircuitBreakerState()

    def can_proceed(self) -> bool:
        """
        Check if the circuit breaker allows requests to proceed.

        Returns
        -------
        bool
            True if requests can proceed, False if circuit is open
        """
        current_time = time.time()

        # Check if circuit is open and can be reset
        if self.state.state == "open":
            if (
                self.state.last_failure_time
                and current_time - self.state.last_failure_time > self.reset_timeout
            ):
                self.state.state = "half-open"
                self.state.failure_count = 0
                return True
            else:
                return False

        return True

    def record_success(self):
        """Record a successful request."""
        if self.state.state == "half-open":
            self.state.state = "closed"
        self.state.failure_count = 0

    def record_failure(self):
        """Record a failed request."""
        self.state.failure_count += 1
        self.state.last_failure_time = time.time()

        if self.state.failure_count >= self.failure_threshold:
            self.state.state = "open"

    async def call(self, func, *args, **kwargs):
        """
        Execute function with circuit breaker protection.

        Parameters
        ----------
        func : callable
            Function to execute
        *args
            Function arguments
        **kwargs
            Function keyword arguments

        Returns
        -------
        Any
            Function result

        Raises
        ------
        CircuitBreakerError
            If circuit breaker is open
        """
        if not self.can_proceed():
            raise CircuitBreakerError("Circuit breaker is open")

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise e


class RateLimiter:
    """Rate limiter for HTTP requests."""

    def __init__(self, max_requests_per_second: float = 10.0):
        """
        Initialize rate limiter.

        Parameters
        ----------
        max_requests_per_second : float
            Maximum requests allowed per second
        """
        self.max_requests_per_second = max_requests_per_second
        self.min_interval = (
            1.0 / max_requests_per_second if max_requests_per_second > 0 else 0
        )
        self.last_request_time = 0.0

    async def acquire(self):
        """
        Acquire permission to make a request.

        This method enforces rate limiting by adding delays between requests
        if necessary to maintain the specified rate limit.
        """
        if self.min_interval <= 0:
            return

        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()


class ServiceHTTPClient:
    """
    HTTP client for EMUSES FastAPI service with robust error handling.

    Features connection pooling, circuit breaker pattern, retry logic,
    and comprehensive error handling for resilient service communication.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: Optional[float] = None,
        max_retries: int = 3,
        pool_connections: int = 20,
        pool_maxsize: int = 100,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
        api_version: str = "v1",
        rate_limit_per_second: float = 10.0,
        max_concurrent_requests: int = 5,
        enable_offline_fallback: bool = False,
        max_retries_before_offline: int = 3,
        health_check_interval: float = 30.0,
        retry_backoff_factor: float = 2.0,
        max_retry_delay: float = 60.0,
        enable_request_timeout_scaling: bool = False,
        enable_advanced_error_categorization: bool = False,
        auth_token: Optional[str] = None,
        auto_token_management: bool = True,
    ):
        """
        Initialize the HTTP client.

        Parameters
        ----------
        base_url : str
            Base URL for the FastAPI service
        timeout : float
            Request timeout in seconds
        max_retries : int
            Maximum number of retries for failed requests
        pool_connections : int
            Maximum number of connections in the pool
        pool_maxsize : int
            Maximum size of the connection pool
        circuit_breaker_threshold : int
            Number of failures before opening circuit breaker
        circuit_breaker_timeout : float
            Time to wait before attempting circuit breaker reset
        api_version : str
            API version to use
        rate_limit_per_second : float
            Maximum requests per second for rate limiting
        max_concurrent_requests : int
            Maximum number of concurrent requests
        enable_offline_fallback : bool
            Enable offline fallback mode when service is unavailable
        max_retries_before_offline : int
            Maximum retries before activating offline mode
        health_check_interval : float
            Interval between health checks in offline mode
        retry_backoff_factor : float
            Multiplier for exponential backoff between retries
        max_retry_delay : float
            Maximum delay between retry attempts in seconds
        enable_request_timeout_scaling : bool
            Enable increasing timeout for retry attempts
        enable_advanced_error_categorization : bool
            Enable advanced error categorization for retry decisions

        Raises
        ------
        ValueError
            If any parameter is invalid
        """
        # Validate parameters
        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be non-negative or None for unlimited")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if circuit_breaker_threshold <= 0:
            raise ValueError("circuit_breaker_threshold must be positive")
        if retry_backoff_factor <= 1.0:
            raise ValueError("retry_backoff_factor must be greater than 1.0")
        if max_retry_delay <= 0:
            raise ValueError("max_retry_delay must be positive")

        # Validate and store base URL
        parsed_url = urlparse(base_url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Invalid base URL: {base_url}")

        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self.timeout = timeout
        self.max_retries = max_retries
        self.pool_connections = pool_connections
        self.pool_maxsize = pool_maxsize

        # Comprehensive error handling parameters
        self.retry_backoff_factor = retry_backoff_factor
        self.max_retry_delay = max_retry_delay
        self.enable_request_timeout_scaling = enable_request_timeout_scaling
        self.enable_advanced_error_categorization = enable_advanced_error_categorization

        # Initialize retry state tracking
        self._request_response_times = []
        self._adaptive_timeout_enabled = False
        self._adaptive_timeout_config = {}
        self._rate_limiting_config = {}
        self._batching_config = {}
        self._batched_requests = []

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            reset_timeout=circuit_breaker_timeout,
        )

        # Initialize rate limiting
        self._rate_limiter = RateLimiter(rate_limit_per_second)
        self._max_concurrent = max_concurrent_requests

        # Initialize offline fallback functionality
        self.enable_offline_fallback = enable_offline_fallback
        self.max_retries_before_offline = max_retries_before_offline
        self.health_check_interval = health_check_interval
        self.is_offline_mode = False
        self.offline_reason: Optional[str] = None
        self._last_health_check: Optional[float] = None

        # Authentication configuration
        self.auth_token = auth_token
        self.auto_token_management = auto_token_management
        self._token_manager = None

        if self.auto_token_management:
            try:
                from emuses.multi_user_service.token_manager import \
                    TokenManager

                self._token_manager = TokenManager()
            except ImportError:
                logger.warning(
                    "Token manager not available, automatic token management disabled"
                )
                self.auto_token_management = False

        self._session: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session and not self._session.is_closed:
            await self._session.aclose()

    async def _ensure_session(self):
        """Ensure HTTP session is created and configured."""
        if self._session is None or self._session.is_closed:
            limits = httpx.Limits(
                max_connections=self.pool_connections,
                max_keepalive_connections=min(self.pool_connections, 20),
            )

            self._session = httpx.AsyncClient(
                limits=limits,
                timeout=(
                    httpx.Timeout(self.timeout) if self.timeout is not None else None
                ),
            )

    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint."""
        return urljoin(self.base_url + "/", endpoint.lstrip("/"))

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for requests.

        Returns
        -------
        Dict[str, str]
            Authentication headers dictionary
        """
        headers = {}

        # Use provided token first
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
            return headers

        # Fall back to stored token if auto-management is enabled
        if self.auto_token_management and self._token_manager:
            auth_header = self._token_manager.get_auth_header()
            if auth_header:
                headers["Authorization"] = auth_header

        return headers

    def set_auth_token(self, token: str) -> None:
        """Set authentication token for requests.

        Parameters
        ----------
        token : str
            JWT authentication token
        """
        self.auth_token = token

    def clear_auth_token(self) -> None:
        """Clear authentication token."""
        self.auth_token = None
        if self._token_manager:
            self._token_manager.clear_token()

    async def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """
        Make HTTP request with comprehensive retry logic and error handling.

        Parameters
        ----------
        method : str
            HTTP method
        endpoint : str
            API endpoint
        **kwargs
            Additional request parameters

        Returns
        -------
        httpx.Response
            HTTP response object

        Raises
        ------
        CircuitBreakerError
            If circuit breaker is open
        ServiceClientError
            If request fails after retries
        """
        # Check circuit breaker
        if not self._circuit_breaker.can_proceed():
            raise CircuitBreakerError("Circuit breaker is open")

        # Apply rate limiting if configured
        await self._apply_rate_limiting()

        await self._ensure_session()
        url = self._build_url(endpoint)
        base_timeout = kwargs.get("timeout", self.timeout)

        # Add authentication headers
        auth_headers = self._get_auth_headers()
        if auth_headers:
            existing_headers = kwargs.get("headers", {})
            kwargs["headers"] = {**existing_headers, **auth_headers}

        for attempt in range(self.max_retries + 1):
            try:
                # Set timeout for this attempt
                self._set_timeout_for_attempt(kwargs, base_timeout, attempt)

                # Make the request and handle response
                response = await self._make_single_request(method, url, kwargs)

                # Handle HTTP errors with advanced categorization
                if self.enable_advanced_error_categorization:
                    if await self._handle_http_error_response(response, attempt):
                        continue  # Retry

                # Success
                self._circuit_breaker.record_success()
                return response

            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.RequestError,
            ) as e:
                if await self._handle_request_exception(e, attempt):
                    continue  # Retry
                else:
                    raise  # Don't retry or max retries reached
            except Exception as e:
                # Unexpected error - don't retry
                logger.error(f"Unexpected error during request: {e}")
                self._circuit_breaker.record_failure()
                raise e

        # This should never be reached
        raise ServiceClientError("Request failed after all retry attempts")

    async def _apply_rate_limiting(self) -> None:
        """Apply rate limiting if configured."""
        if not self._rate_limiting_config.get("enabled", False):
            return

        current_time = time.time()
        max_rps = self._rate_limiting_config["max_requests_per_second"]
        request_times = self._rate_limiting_config["request_times"]

        # Clean old request times (older than 1 second)
        cutoff_time = current_time - 1.0
        self._rate_limiting_config["request_times"] = [
            t for t in request_times if t > cutoff_time
        ]

        # Check if we need to wait
        recent_requests = len(self._rate_limiting_config["request_times"])
        if recent_requests >= max_rps:
            # Calculate wait time
            oldest_request = min(self._rate_limiting_config["request_times"])
            wait_time = 1.0 - (current_time - oldest_request)
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        # Record this request
        self._rate_limiting_config["request_times"].append(time.time())

    def _set_timeout_for_attempt(
        self, kwargs: dict, base_timeout: float, attempt: int
    ) -> None:
        """Set timeout for current retry attempt."""
        if self.enable_request_timeout_scaling and attempt > 0:
            current_timeout = base_timeout * (1.5**attempt)
            kwargs["timeout"] = min(current_timeout, base_timeout * 3)
        else:
            kwargs["timeout"] = base_timeout

    async def _make_single_request(
        self, method: str, url: str, kwargs: dict
    ) -> httpx.Response:
        """Make a single HTTP request and record timing."""
        start_time = time.time()
        response = await self._session.request(method, url, **kwargs)
        response_time = time.time() - start_time
        self._record_response_time(response_time)
        return response

    async def _handle_http_error_response(
        self, response: httpx.Response, attempt: int
    ) -> bool:
        """
        Handle HTTP error responses with advanced categorization.

        Returns True if request should be retried, False otherwise.
        """
        if response.status_code < 400:
            return False  # No error

        if 400 <= response.status_code < 500 and response.status_code != 429:
            # Client errors (4xx) - don't retry except for rate limiting (429)
            response.raise_for_status()
            return False
        elif response.status_code >= 500 or response.status_code == 429:
            # Server errors (5xx) or rate limiting (429) - retry
            if attempt < self.max_retries:
                logger.warning(
                    f"HTTP {response.status_code} error, retrying (attempt {attempt + 1}/{self.max_retries + 1})"
                )
                await self._wait_for_retry(attempt)
                return True
            else:
                response.raise_for_status()
                return False
        return False

    async def _handle_request_exception(self, error: Exception, attempt: int) -> bool:
        """
        Handle request exceptions with retry logic.

        Returns True if request should be retried, False otherwise.
        """
        # Check if this error type should be retried
        if self.enable_advanced_error_categorization:
            should_retry = self._should_retry_error(error)
            if not should_retry:
                logger.warning(f"Non-retryable error: {error}")
                self._circuit_breaker.record_failure()
                return False

        if attempt < self.max_retries:
            logger.warning(
                f"Request failed, retrying (attempt {attempt + 1}/{self.max_retries + 1}): {error}"
            )
            await self._wait_for_retry(attempt)
            return True
        else:
            logger.error(
                f"Request failed after {self.max_retries + 1} attempts: {error}"
            )
            self._circuit_breaker.record_failure()
            return False

    async def _wait_for_retry(self, attempt: int) -> None:
        """
        Wait before retrying with exponential backoff.

        Parameters
        ----------
        attempt : int
            Current attempt number (0-based)
        """
        delay = min(self.retry_backoff_factor**attempt, self.max_retry_delay)
        logger.debug(f"Waiting {delay:.2f}s before retry attempt {attempt + 1}")
        await asyncio.sleep(delay)

    def _should_retry_error(self, error: Exception) -> bool:
        """
        Determine if an error should be retried based on advanced categorization.

        Parameters
        ----------
        error : Exception
            The error to categorize

        Returns
        -------
        bool
            True if the error should be retried
        """
        if isinstance(error, httpx.ConnectError):
            error_str = str(error).lower()
            # Don't retry SSL/TLS errors
            if any(
                ssl_term in error_str
                for ssl_term in ["ssl", "tls", "certificate", "handshake"]
            ):
                return False
            # Retry network and DNS errors
            return True
        elif isinstance(error, (httpx.TimeoutException, httpx.RequestError)):
            # Retry timeout and general request errors
            return True
        else:
            # Don't retry other error types
            return False

    def _record_response_time(self, response_time: float) -> None:
        """
        Record response time for adaptive timeout management.

        Parameters
        ----------
        response_time : float
            Response time in seconds
        """
        self._request_response_times.append(response_time)
        # Keep only the last 100 response times
        if len(self._request_response_times) > 100:
            self._request_response_times.pop(0)

    async def get(self, endpoint: str, **kwargs) -> httpx.Response:
        """
        Make GET request.

        Parameters
        ----------
        endpoint : str
            API endpoint
        **kwargs
            Additional request parameters

        Returns
        -------
        httpx.Response
            HTTP response object
        """
        return await self._request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> httpx.Response:
        """
        Make POST request.

        Parameters
        ----------
        endpoint : str
            API endpoint
        **kwargs
            Additional request parameters

        Returns
        -------
        httpx.Response
            HTTP response object
        """
        return await self._request("POST", endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs) -> httpx.Response:
        """
        Make PUT request.

        Parameters
        ----------
        endpoint : str
            API endpoint
        **kwargs
            Additional request parameters

        Returns
        -------
        httpx.Response
            HTTP response object
        """
        return await self._request("PUT", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> httpx.Response:
        """
        Make DELETE request.

        Parameters
        ----------
        endpoint : str
            API endpoint
        **kwargs
            Additional request parameters

        Returns
        -------
        httpx.Response
            HTTP response object
        """
        return await self._request("DELETE", endpoint, **kwargs)

    # Job Submission Methods

    async def submit_pipeline_job(
        self,
        pipeline_type: str,
        job_request: Dict[str, Any],
        files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Submit a pipeline job to the EMUSES service.

        Parameters
        ----------
        pipeline_type : str
            Type of pipeline ('full', 'umap', 'clustering', 'heatmap', 'prediction')
        job_request : Dict[str, Any]
            Job configuration and parameters
        files : Optional[Dict[str, Any]], optional
            Files to upload with the job

        Returns
        -------
        Dict[str, Any]
            Job submission response with job_id and status

        Raises
        ------
        ValueError
            If job request is invalid or pipeline type is not supported
        httpx.HTTPStatusError
            If the service returns an error response
        """
        # Check if client is in offline mode
        self._check_offline_mode()

        # Validate inputs
        self._validate_job_request(job_request)
        self._validate_pipeline_type(pipeline_type)

        # Construct API endpoint with versioning
        endpoint = f"/api/{self.api_version}/jobs/pipeline/{pipeline_type}"

        # Prepare request parameters
        request_kwargs = {"json": job_request}
        if files:
            request_kwargs["files"] = files

        # Submit job
        response = await self.post(endpoint, **request_kwargs)
        response.raise_for_status()

        return response.json()

    async def submit_stage_job(
        self,
        stage: str,
        job_request: Dict[str, Any],
        files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Submit a stage-specific job to the EMUSES service.

        Parameters
        ----------
        stage : str
            Processing stage ('umap', 'clustering', 'heatmap', 'prediction')
        job_request : Dict[str, Any]
            Job configuration and parameters
        files : Optional[Dict[str, Any]], optional
            Files to upload with the job

        Returns
        -------
        Dict[str, Any]
            Job submission response with job_id and status

        Raises
        ------
        ValueError
            If job request is invalid or stage type is not supported
        httpx.HTTPStatusError
            If the service returns an error response
        """
        # Validate inputs
        self._validate_job_request(job_request)
        self._validate_stage_type(stage)

        # Construct API endpoint with versioning
        endpoint = f"/api/{self.api_version}/jobs/stage/{stage}"

        # Prepare request parameters
        request_kwargs = {"json": job_request}
        if files:
            request_kwargs["files"] = files

        # Submit job
        response = await self.post(endpoint, **request_kwargs)
        response.raise_for_status()

        return response.json()

    def _validate_job_request(self, job_request: Optional[Dict[str, Any]]) -> None:
        """
        Validate job request parameters.

        Parameters
        ----------
        job_request : Optional[Dict[str, Any]]
            Job request to validate

        Raises
        ------
        ValueError
            If job request is None or empty
        """
        if job_request is None:
            raise ValueError("Job request cannot be None")
        if not job_request:
            raise ValueError("Job request cannot be empty")

    def _validate_pipeline_type(self, pipeline_type: str) -> None:
        """
        Validate pipeline type.

        Parameters
        ----------
        pipeline_type : str
            Pipeline type to validate

        Raises
        ------
        ValueError
            If pipeline type is not supported
        """
        valid_types = ["full", "umap", "clustering", "heatmap", "prediction"]
        if pipeline_type not in valid_types:
            raise ValueError(
                f"Invalid pipeline type '{pipeline_type}'. "
                f"Must be one of: {', '.join(valid_types)}"
            )

    def _validate_stage_type(self, stage: str) -> None:
        """
        Validate stage type.

        Parameters
        ----------
        stage : str
            Stage type to validate

        Raises
        ------
        ValueError
            If stage type is not supported
        """
        valid_stages = ["umap", "clustering", "heatmap", "prediction"]
        if stage not in valid_stages:
            raise ValueError(
                f"Invalid stage type '{stage}'. "
                f"Must be one of: {', '.join(valid_stages)}"
            )

    # Job Status Polling Methods

    async def get_job_status(
        self, job_id: str, use_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Get the status of a job.

        Parameters
        ----------
        job_id : str
            Unique identifier for the job
        use_cache : bool, optional
            Whether to use cached status if available (default: False)

        Returns
        -------
        Dict[str, Any]
            Job status information including status, progress, timestamps

        Raises
        ------
        ValueError
            If job_id is empty or None
        httpx.HTTPStatusError
            If the service returns an error response
        """
        # Check if client is in offline mode
        self._check_offline_mode()

        if not job_id or not job_id.strip():
            raise ValueError("Job ID cannot be empty")

        # Check cache if enabled
        if use_cache and hasattr(self, "_status_cache"):
            cached_status = self._status_cache.get(job_id)
            if cached_status and (time.time() - cached_status["_cached_at"]) < 30:
                return {k: v for k, v in cached_status.items() if k != "_cached_at"}

        # Construct API endpoint
        endpoint = f"/api/{self.api_version}/jobs/{job_id}/status"

        # Get job status
        response = await self.get(endpoint)
        response.raise_for_status()

        status_data = response.json()

        # Cache the result if caching is enabled
        if use_cache:
            if not hasattr(self, "_status_cache"):
                self._status_cache = {}
            cached_data = status_data.copy()
            cached_data["_cached_at"] = time.time()
            self._status_cache[job_id] = cached_data

        return status_data

    async def poll_job_until_completion(
        self,
        job_id: str,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
        completion_states: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Poll job status until completion or timeout.

        Parameters
        ----------
        job_id : str
            Unique identifier for the job
        poll_interval : float, optional
            Seconds between status checks (default: 5.0)
        timeout : float, optional
            Maximum time to wait in seconds (default: 300.0)
        completion_states : Optional[list], optional
            States that indicate completion (default: ["completed", "failed", "cancelled"])

        Returns
        -------
        Dict[str, Any]
            Final job status information

        Raises
        ------
        asyncio.TimeoutError
            If timeout is reached before completion
        ValueError
            If job_id is invalid
        httpx.HTTPStatusError
            If the service returns an error response
        """
        if completion_states is None:
            completion_states = ["completed", "failed", "cancelled"]

        start_time = time.time()

        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                raise asyncio.TimeoutError(
                    f"Job {job_id} did not complete within {timeout} seconds"
                )

            # Get current status
            status = await self.get_job_status(job_id)

            # Check if job is complete
            if status.get("status") in completion_states:
                return status

            # Wait before next poll (rate limiting)
            await asyncio.sleep(poll_interval)

    async def poll_multiple_jobs(
        self,
        job_ids: list,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
        max_concurrent: int = 5,
        completion_states: Optional[list] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Poll multiple jobs concurrently with rate limiting.

        Parameters
        ----------
        job_ids : list
            List of job IDs to monitor
        poll_interval : float, optional
            Seconds between status checks (default: 5.0)
        timeout : float, optional
            Maximum time to wait in seconds (default: 300.0)
        max_concurrent : int, optional
            Maximum concurrent polling operations (default: 5)
        completion_states : Optional[list], optional
            States that indicate completion (default: ["completed", "failed", "cancelled"])

        Returns
        -------
        Dict[str, Dict[str, Any]]
            Final status for each job, keyed by job_id

        Raises
        ------
        asyncio.TimeoutError
            If timeout is reached before all jobs complete
        ValueError
            If job_ids list is empty
        """
        if not job_ids:
            raise ValueError("Job IDs list cannot be empty")

        if completion_states is None:
            completion_states = ["completed", "failed", "cancelled"]

        # Use semaphore for concurrent limiting
        semaphore = asyncio.Semaphore(max_concurrent)

        async def poll_single_job(job_id: str) -> tuple:
            async with semaphore:
                try:
                    result = await self.poll_job_until_completion(
                        job_id, poll_interval, timeout, completion_states
                    )
                    return job_id, result
                except Exception as e:
                    return job_id, {"status": "error", "error": str(e)}

        # Poll all jobs concurrently
        tasks = [poll_single_job(job_id) for job_id in job_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        job_results = {}
        for result in results:
            if isinstance(result, Exception):
                # Handle exceptions
                continue
            job_id, status = result
            job_results[job_id] = status

        return job_results

    # Offline Fallback Functionality

    async def check_service_health(self) -> bool:
        """
        Check if the service is healthy and available.

        Performs a health check request to the service health endpoint
        and handles failures gracefully with optional offline fallback.

        Returns
        -------
        bool
            True if service is healthy, False otherwise

        Raises
        ------
        ServiceClientError
            If health check fails and offline fallback is disabled
        """
        retry_count = 0
        max_retries = (
            self.max_retries_before_offline
            if self.enable_offline_fallback
            else self.max_retries
        )

        while retry_count <= max_retries:
            try:
                await self._rate_limiter.acquire()
                await self._ensure_session()

                # Make health check request
                response = await self._session.get(
                    f"{self.base_url}/api/health", timeout=self.timeout
                )

                # Check if response indicates healthy service
                if response.status_code == 200:
                    # Service is healthy - exit offline mode if enabled
                    if self.is_offline_mode and self.enable_offline_fallback:
                        self._exit_offline_mode()

                    self._last_health_check = time.time()
                    return True
                else:
                    # Service responded but is unhealthy
                    logger.warning(
                        f"Service health check failed with status {response.status_code}"
                    )
                    if retry_count >= max_retries and self.enable_offline_fallback:
                        self._activate_offline_mode(
                            f"Service unhealthy: HTTP {response.status_code}"
                        )
                    return False

            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.RequestError,
            ) as e:
                logger.warning(f"Health check attempt {retry_count + 1} failed: {e}")
                retry_count += 1

                if retry_count > max_retries:
                    # All retries exhausted
                    if self.enable_offline_fallback:
                        self._activate_offline_mode(
                            f"Service unavailable after {max_retries} retries: {e}"
                        )
                    return False

                # Wait before retry
                await asyncio.sleep(min(2**retry_count, 10))

        return False

    def _activate_offline_mode(self, reason: str) -> None:
        """
        Activate offline fallback mode.

        Parameters
        ----------
        reason : str
            Reason for going offline

        Examples
        --------
        >>> client._activate_offline_mode("Service connection failed")
        """
        if not self.enable_offline_fallback:
            logger.warning(
                f"Offline mode activation requested but not enabled: {reason}"
            )
            return

        logger.warning(f"Activating offline mode: {reason}")
        self.is_offline_mode = True
        self.offline_reason = reason
        self._last_health_check = time.time()

    def _exit_offline_mode(self) -> None:
        """
        Exit offline fallback mode when service recovers.

        Examples
        --------
        >>> client._exit_offline_mode()
        """
        if self.is_offline_mode:
            logger.info("Service recovered - exiting offline mode")
            self.is_offline_mode = False
            self.offline_reason = None

    async def attempt_service_recovery(self) -> bool:
        """
        Attempt to recover from offline mode by checking service health.

        Returns
        -------
        bool
            True if service has recovered, False otherwise

        Examples
        --------
        >>> recovery_success = await client.attempt_service_recovery()
        >>> if recovery_success:
        ...     print("Service has recovered!")
        """
        if not self.is_offline_mode:
            logger.debug("Not in offline mode, no recovery needed")
            return True

        logger.info("Attempting service recovery from offline mode")

        # Try health check without triggering offline mode again
        original_enable_offline = self.enable_offline_fallback
        self.enable_offline_fallback = False

        try:
            health_status = await self.check_service_health()
            if health_status:
                self._exit_offline_mode()
                return True
            else:
                logger.info(
                    "Service recovery attempt failed - remaining in offline mode"
                )
                return False
        except ServiceClientError:
            logger.info("Service recovery attempt failed - remaining in offline mode")
            return False
        finally:
            # Restore original setting
            self.enable_offline_fallback = original_enable_offline

    def _check_offline_mode(self) -> None:
        """
        Check if client is in offline mode and raise appropriate error.

        Raises
        ------
        ServiceClientError
            If client is in offline mode
        """
        if self.is_offline_mode:
            raise ServiceClientError(
                f"Service is in offline mode: {self.offline_reason}. "
                f"Use attempt_service_recovery() to check if service has recovered."
            )

    # ========================================
    # Comprehensive Error Handling Features
    # ========================================

    def configure_rate_limiting(self, max_requests_per_second: float) -> None:
        """
        Configure rate limiting for requests.

        Parameters
        ----------
        max_requests_per_second : float
            Maximum number of requests per second
        """
        self._rate_limiting_config = {
            "max_requests_per_second": max_requests_per_second,
            "request_times": [],
            "enabled": True,
        }

    def enable_request_batching(self, batch_size: int, max_wait_time: float) -> None:
        """
        Enable request batching capabilities.

        Parameters
        ----------
        batch_size : int
            Maximum number of requests per batch
        max_wait_time : float
            Maximum time to wait before processing a batch
        """
        self._batching_config = {
            "batch_size": batch_size,
            "max_wait_time": max_wait_time,
            "enabled": True,
        }

    def queue_batch_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """
        Queue a request for batching.

        Parameters
        ----------
        method : str
            HTTP method
        endpoint : str
            API endpoint
        **kwargs
            Additional request parameters

        Returns
        -------
        dict
            Queued request information
        """
        request_info = {
            "method": method,
            "endpoint": endpoint,
            "kwargs": kwargs,
            "queued_at": time.time(),
        }
        self._batched_requests.append(request_info)
        return request_info

    async def process_batched_requests(self) -> list:
        """
        Process all queued batched requests.

        Returns
        -------
        list
            List of responses from batched requests
        """
        if not self._batched_requests:
            return []

        responses = []
        batch_size = self._batching_config.get("batch_size", 10)

        # Process requests in batches
        for i in range(0, len(self._batched_requests), batch_size):
            batch = self._batched_requests[i : i + batch_size]
            batch_responses = await self._process_request_batch(batch)
            responses.extend(batch_responses)

        # Clear processed requests
        self._batched_requests.clear()
        return responses

    async def _process_request_batch(self, batch: list) -> list:
        """
        Process a single batch of requests.

        Parameters
        ----------
        batch : list
            List of request information dictionaries

        Returns
        -------
        list
            List of responses
        """
        tasks = []
        for request_info in batch:
            task = asyncio.create_task(
                self._request(
                    request_info["method"],
                    request_info["endpoint"],
                    **request_info["kwargs"],
                )
            )
            tasks.append(task)

        return await asyncio.gather(*tasks, return_exceptions=True)

    def enable_adaptive_timeout_management(
        self, min_timeout: float, max_timeout: float, timeout_adjustment_factor: float
    ) -> None:
        """
        Enable adaptive timeout management based on response times.

        Parameters
        ----------
        min_timeout : float
            Minimum timeout value
        max_timeout : float
            Maximum timeout value
        timeout_adjustment_factor : float
            Factor for adjusting timeout based on response times
        """
        self._adaptive_timeout_enabled = True
        self._adaptive_timeout_config = {
            "min_timeout": min_timeout,
            "max_timeout": max_timeout,
            "adjustment_factor": timeout_adjustment_factor,
        }

    def get_current_adaptive_timeout(self) -> float:
        """
        Get current adaptive timeout based on response time history.

        Returns
        -------
        float
            Current adaptive timeout value
        """
        if not self._adaptive_timeout_enabled or not self._request_response_times:
            return self.timeout

        # Calculate adaptive timeout based on recent response times
        recent_times = self._request_response_times[-10:]  # Last 10 requests
        avg_response_time = sum(recent_times) / len(recent_times)

        config = self._adaptive_timeout_config
        adaptive_timeout = avg_response_time * config["adjustment_factor"]

        # Clamp to min/max bounds
        adaptive_timeout = max(adaptive_timeout, config["min_timeout"])
        adaptive_timeout = min(adaptive_timeout, config["max_timeout"])

        return adaptive_timeout


class LocalServiceClient:
    """
    TestClient-based service client for local execution.

    This class provides the same interface as ServiceHTTPClient but uses
    FastAPI TestClient for in-process execution, maintaining service
    consistency while eliminating external service dependencies.
    """

    def __init__(self, api_version: str = "v1"):
        """
        Initialize the local service client.

        Parameters
        ----------
        api_version : str, optional
            API version to use, by default "v1"
        """
        self.api_version = api_version
        self._client: Optional[TestClient] = None
        self._app = None

    def _ensure_client(self) -> TestClient:
        """
        Ensure TestClient is created and configured.

        Returns
        -------
        TestClient
            Configured TestClient instance
        """
        if self._client is None:
            # Import and create FastAPI app
            try:
                from emuses.api.main import create_app

                self._app = create_app()
                self._client = TestClient(self._app)
            except ImportError as e:
                raise ServiceClientError(f"FastAPI service not available: {e}")

        return self._client

    async def submit_pipeline_job(
        self,
        pipeline_type: str,
        job_request: Dict[str, Any],
        files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Submit a pipeline job to the local service.

        Parameters
        ----------
        pipeline_type : str
            Type of pipeline ('full', 'umap', 'clustering', 'heatmap', 'prediction')
        job_request : Dict[str, Any]
            Job configuration and parameters
        files : Optional[Dict[str, Any]], optional
            Files to upload with the job

        Returns
        -------
        Dict[str, Any]
            Job submission response with job_id and status

        Raises
        ------
        ValueError
            If job request is invalid or pipeline type is not supported
        ServiceClientError
            If the service returns an error response
        """
        # Validate inputs
        self._validate_job_request(job_request)
        self._validate_pipeline_type(pipeline_type)

        # Get TestClient
        client = self._ensure_client()

        # Construct API endpoint
        endpoint = f"/api/{self.api_version}/jobs/pipeline/{pipeline_type}"

        # Make request
        response = client.post(endpoint, json=job_request)

        if response.status_code != 200:
            raise ServiceClientError(
                f"Job submission failed: {response.status_code} - {response.text}"
            )

        return response.json()

    async def get_job_status(
        self, job_id: str, use_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Get the status of a job.

        Parameters
        ----------
        job_id : str
            Unique identifier for the job
        use_cache : bool, optional
            Whether to use cached status (not implemented for local client)

        Returns
        -------
        Dict[str, Any]
            Job status information including status, progress, timestamps

        Raises
        ------
        ValueError
            If job_id is empty or None
        ServiceClientError
            If the service returns an error response
        """
        if not job_id or not job_id.strip():
            raise ValueError("Job ID cannot be empty")

        # Get TestClient
        client = self._ensure_client()

        # Construct API endpoint
        endpoint = f"/api/{self.api_version}/jobs/{job_id}/status"

        # Make request
        response = client.get(endpoint)

        if response.status_code != 200:
            raise ServiceClientError(
                f"Status check failed: {response.status_code} - {response.text}"
            )

        return response.json()

    async def check_service_health(self) -> bool:
        """
        Check if the local service is healthy.

        Returns
        -------
        bool
            True if service is healthy, False otherwise
        """
        try:
            # Get TestClient
            client = self._ensure_client()

            # Make health check request
            response = client.get("/api/health")

            return response.status_code == 200

        except Exception as e:
            logger.warning(f"Local service health check failed: {e}")
            return False

    def _validate_job_request(self, job_request: Optional[Dict[str, Any]]) -> None:
        """
        Validate job request parameters.

        Parameters
        ----------
        job_request : Optional[Dict[str, Any]]
            Job request to validate

        Raises
        ------
        ValueError
            If job request is None or empty
        """
        if job_request is None:
            raise ValueError("Job request cannot be None")
        if not job_request:
            raise ValueError("Job request cannot be empty")

    def _validate_pipeline_type(self, pipeline_type: str) -> None:
        """
        Validate pipeline type.

        Parameters
        ----------
        pipeline_type : str
            Pipeline type to validate

        Raises
        ------
        ValueError
            If pipeline type is not supported
        """
        valid_types = ["full", "umap", "clustering", "heatmap", "prediction"]
        if pipeline_type not in valid_types:
            raise ValueError(
                f"Invalid pipeline type '{pipeline_type}'. "
                f"Must be one of: {', '.join(valid_types)}"
            )
