"""Cloud storage resilience and error handling utilities.

This module provides comprehensive error handling, retry logic, timeout management,
and circuit breaker patterns for cloud storage operations using industry best practices.
"""

import asyncio
import logging
import time
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional
from functools import wraps

import tenacity
from tenacity import (
    stop_after_attempt, wait_exponential, before_sleep_log
)

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories for cloud storage errors."""

    TRANSIENT = "transient"      # Temporary errors that should be retried
    PERMANENT = "permanent"      # Permanent errors that should not be retried
    RATE_LIMIT = "rate_limit"    # Rate limiting that requires exponential backoff
    AUTH = "authentication"      # Authentication/authorization errors


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: int = 2
    jitter: bool = True

    def to_tenacity_config(self) -> Dict[str, Any]:
        """Convert to tenacity configuration dictionary.

        Returns
        -------
        Dict[str, Any]
            Dictionary suitable for tenacity retry decorator
        """
        wait_strategy = wait_exponential(
            multiplier=self.base_delay,
            min=self.base_delay,
            max=self.max_delay
        )

        if self.jitter:
            # Add jitter to prevent thundering herd
            wait_strategy = wait_strategy + tenacity.wait_random(0, 1)

        return {
            "stop": stop_after_attempt(self.max_attempts),
            "wait": wait_strategy,
            "before_sleep": before_sleep_log(logger, logging.WARNING)
        }


class CloudErrorClassifier:
    """Classifier for categorizing cloud storage errors.

    Provides intelligent error classification to determine appropriate
    retry strategies and error handling approaches.
    """

    # Network and connection errors (always transient)
    TRANSIENT_NETWORK_ERRORS = (
        ConnectionError,
        TimeoutError,
        OSError,  # Network-related OS errors
    )

    # Authentication and permission errors (always permanent)
    PERMANENT_AUTH_ERRORS = (
        PermissionError,
        FileNotFoundError,  # Often indicates missing resources
    )

    # HTTP status codes for classification
    TRANSIENT_HTTP_CODES = {429, 500, 502, 503, 504}  # Rate limit + server errors
    PERMANENT_HTTP_CODES = {400, 401, 403, 404, 409}  # Client errors (except 429)

    # Cloud provider specific error codes
    AWS_TRANSIENT_CODES = {
        "SlowDown", "RequestTimeout", "ServiceUnavailable",
        "InternalError", "RequestTimeTooSkewed"
    }

    AWS_PERMANENT_CODES = {
        "NoSuchBucket", "NoSuchKey", "AccessDenied", "InvalidAccessKeyId",
        "SignatureDoesNotMatch", "BucketAlreadyExists", "InvalidBucketName"
    }

    AZURE_TRANSIENT_CODES = {
        "InternalError", "ServerBusy", "RequestTimeout"
    }

    AZURE_PERMANENT_CODES = {
        "AuthenticationFailed", "AuthorizationFailure", "ContainerNotFound",
        "BlobNotFound", "ContainerAlreadyExists", "InvalidStorageAccount"
    }

    GCS_TRANSIENT_CODES = {
        "internalError", "backendError", "rateLimitExceeded", "userRateLimitExceeded"
    }

    GCS_PERMANENT_CODES = {
        "invalid", "notFound", "forbidden", "unauthorized", "conflict"
    }

    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify an error into appropriate category.

        Parameters
        ----------
        error : Exception
            The exception to classify

        Returns
        -------
        ErrorCategory
            The appropriate category for the error
        """
        # Check HTTP errors first (before generic OSError check)
        if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            status_code = error.response.status_code

            if status_code == 429:
                return ErrorCategory.RATE_LIMIT
            elif status_code in self.TRANSIENT_HTTP_CODES:
                return ErrorCategory.TRANSIENT
            elif status_code in self.PERMANENT_HTTP_CODES:
                return ErrorCategory.PERMANENT

        # Check authentication/permission errors
        if isinstance(error, self.PERMANENT_AUTH_ERRORS):
            return ErrorCategory.PERMANENT

        # Check network/connection errors (but exclude HTTP errors handled above)
        if isinstance(error, self.TRANSIENT_NETWORK_ERRORS) and not hasattr(error, 'response'):
            return ErrorCategory.TRANSIENT

        # Check cloud provider specific errors
        error_category = self._classify_cloud_provider_error(error)
        if error_category:
            return error_category

        # Default to permanent for unknown errors (conservative approach)
        logger.warning(f"Unknown error type, classifying as permanent: {type(error).__name__}: {error}")
        return ErrorCategory.PERMANENT

    def is_transient(self, error: Exception) -> bool:
        """Check if an error should be retried.

        Parameters
        ----------
        error : Exception
            The exception to check

        Returns
        -------
        bool
            True if the error is transient and should be retried
        """
        category = self.classify_error(error)
        return category in (ErrorCategory.TRANSIENT, ErrorCategory.RATE_LIMIT)

    def _classify_cloud_provider_error(self, error: Exception) -> Optional[ErrorCategory]:
        """Classify cloud provider specific errors.

        Parameters
        ----------
        error : Exception
            The exception to classify

        Returns
        -------
        Optional[ErrorCategory]
            Error category if recognized, None otherwise
        """
        # Delegate to provider-specific methods to reduce complexity
        aws_category = self._classify_aws_error(error)
        if aws_category:
            return aws_category

        azure_category = self._classify_azure_error(error)
        if azure_category:
            return azure_category

        gcs_category = self._classify_gcs_error(error)
        if gcs_category:
            return gcs_category

        return None

    def _classify_aws_error(self, error: Exception) -> Optional[ErrorCategory]:
        """Classify AWS specific errors."""
        if error.__class__.__name__ != 'ClientError':
            return None

        try:
            error_code = error.response['Error']['Code']
            if error_code in self.AWS_TRANSIENT_CODES:
                return ErrorCategory.TRANSIENT
            elif error_code in self.AWS_PERMANENT_CODES:
                return ErrorCategory.PERMANENT
        except (KeyError, AttributeError):
            pass

        return None

    def _classify_azure_error(self, error: Exception) -> Optional[ErrorCategory]:
        """Classify Azure specific errors."""
        if 'azure' not in str(type(error)).lower():
            return None

        try:
            if hasattr(error, 'error_code'):
                error_code = error.error_code
                if error_code in self.AZURE_TRANSIENT_CODES:
                    return ErrorCategory.TRANSIENT
                elif error_code in self.AZURE_PERMANENT_CODES:
                    return ErrorCategory.PERMANENT
        except AttributeError:
            pass

        return None

    def _classify_gcs_error(self, error: Exception) -> Optional[ErrorCategory]:
        """Classify Google Cloud Storage specific errors."""
        if 'google' not in str(type(error)).lower():
            return None

        try:
            error_message = str(error).lower()
            for code in self.GCS_TRANSIENT_CODES:
                if code.lower() in error_message:
                    return ErrorCategory.TRANSIENT
            for code in self.GCS_PERMANENT_CODES:
                if code.lower() in error_message:
                    return ErrorCategory.PERMANENT
        except (AttributeError, TypeError):
            pass

        return None


@dataclass
class CloudOperationTimeout:
    """Configuration for cloud operation timeouts.

    Parameters
    ----------
    connection_timeout : float
        Maximum time to wait for connection establishment
    read_timeout : float
        Maximum time to wait for reading response data
    total_timeout : float
        Maximum total time for entire operation

    Raises
    ------
    ValueError
        If timeout values are invalid or inconsistent
    """

    connection_timeout: float = 10.0
    read_timeout: float = 30.0
    total_timeout: float = 300.0

    def __post_init__(self):
        """Validate timeout configuration."""
        if self.connection_timeout <= 0:
            raise ValueError("Connection timeout must be positive")
        if self.read_timeout <= 0:
            raise ValueError("Read timeout must be positive")
        if self.total_timeout <= 0:
            raise ValueError("Total timeout must be positive")
        if self.total_timeout < (self.connection_timeout + self.read_timeout):
            raise ValueError("Total timeout must be >= connection + read timeouts")


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open and blocking operations."""
    pass


class CircuitBreakerState(Enum):
    """States for circuit breaker pattern."""

    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failing fast, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker implementation for cloud operations.

    Prevents cascading failures by failing fast when a service is down.

    Parameters
    ----------
    failure_threshold : int
        Number of failures before opening circuit
    recovery_timeout : float
        Time to wait before attempting recovery
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()

    async def execute(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute an operation with circuit breaker protection.

        Parameters
        ----------
        operation : Callable
            The operation to execute
        *args, **kwargs
            Arguments to pass to the operation

        Returns
        -------
        Any
            Result of the operation

        Raises
        ------
        CircuitBreakerError
            If circuit breaker is open and blocking requests
        """
        async with self._lock:
            await self._check_state()

            if self._state == CircuitBreakerState.OPEN:
                raise CircuitBreakerError(
                    f"Circuit breaker is open. Last failure: {self._last_failure_time}"
                )

        try:
            result = await operation(*args, **kwargs)
            await self._record_success()
            return result
        except Exception:
            await self._record_failure()
            raise

    async def _check_state(self):
        """Check and update circuit breaker state."""
        if self._state == CircuitBreakerState.OPEN:
            if (self._last_failure_time and
                    time.time() - self._last_failure_time >= self.recovery_timeout):
                self._state = CircuitBreakerState.HALF_OPEN
                logger.info("Circuit breaker transitioning to half-open state")

    async def _record_success(self):
        """Record a successful operation."""
        async with self._lock:
            self._failure_count = 0
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.CLOSED
                logger.info("Circuit breaker closed after successful recovery")

    async def _record_failure(self):
        """Record a failed operation."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if (self._state in (CircuitBreakerState.CLOSED, CircuitBreakerState.HALF_OPEN)
                    and self._failure_count >= self.failure_threshold):
                self._state = CircuitBreakerState.OPEN
                logger.warning(
                    f"Circuit breaker opened after {self._failure_count} failures"
                )


def with_exponential_backoff(
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    error_classifier: Optional[CloudErrorClassifier] = None
) -> Callable:
    """Decorator to add exponential backoff retry logic to functions.

    Parameters
    ----------
    max_attempts : int, default=5
        Maximum number of retry attempts
    base_delay : float, default=1.0
        Base delay between retries in seconds
    max_delay : float, default=60.0
        Maximum delay between retries in seconds
    error_classifier : CloudErrorClassifier, optional
        Custom error classifier, uses default if None

    Returns
    -------
    Callable
        Decorated function with retry logic
    """
    if error_classifier is None:
        error_classifier = CloudErrorClassifier()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # Check if error should be retried
                    if not error_classifier.is_transient(e):
                        # Permanent error - don't retry
                        raise

                    # Check if we've exhausted attempts
                    if attempt == max_attempts - 1:
                        # Last attempt - re-raise the error
                        raise

                    # Calculate delay with exponential backoff and jitter
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = random.uniform(0, delay * 0.1)  # 10% jitter
                    total_delay = delay + jitter

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed with {type(e).__name__}: {e}. "
                        f"Retrying in {total_delay:.2f} seconds."
                    )

                    await asyncio.sleep(total_delay)

            # This should never be reached due to the raise in the loop
            raise RuntimeError("Retry loop completed unexpectedly")

        return wrapper
    return decorator


def add_retry_capabilities(backend_instance):
    """Add retry capabilities to an existing cloud storage backend.

    This is a placeholder function that would enhance existing backends
    with retry logic. The actual implementation would wrap methods
    with the retry decorator.

    Parameters
    ----------
    backend_instance
        Cloud storage backend instance to enhance

    Returns
    -------
    Enhanced backend instance with retry capabilities
    """
    # For now, return the original instance
    # In a full implementation, this would wrap methods with retry logic
    logger.info(f"Adding retry capabilities to {type(backend_instance).__name__}")
    return backend_instance
