"""FastAPI application for Foundation FastAPI Service.

This module implements the REST API endpoints for the EMUSES pipeline,
providing job management, pipeline execution, and artifact handling capabilities.
"""

import asyncio
import logging
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

# Explicit import for Starlette form parser compatibility
import python_multipart
import uvicorn
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from emuses.foundation_fastapi_service.models import (ErrorResponse,
                                                      FileUploadModel,
                                                      FileUploadResponse,
                                                      InferenceRequest,
                                                      InferenceResponse,
                                                      JobStatusResponse,
                                                      JobSubmissionRequest,
                                                      PipelineConfigRequest)
# Observability imports
from emuses.observability import (get_logger, get_metrics_registry,
                                  setup_structured_logging, track_http_request)
from emuses.observability.logging import clear_context, set_request_context

# Configure structured logging for observability
setup_structured_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)

# Environment-based configuration
TESTING_MODE = os.getenv("TESTING_MODE", "false").lower() == "true"
RATE_LIMITING_ENABLED = (
    os.getenv("RATE_LIMITING_ENABLED", "true").lower() == "true" and not TESTING_MODE
)

# Initialize rate limiter (disabled in testing mode)
limiter = Limiter(key_func=get_remote_address) if RATE_LIMITING_ENABLED else None


# Request size limiting middleware
class RequestSizeLimiterMiddleware:
    """Middleware to limit request size and return 413 for oversized requests."""

    def __init__(
        self, app, max_size: int = 1024 * 1024 * 1024
    ):  # 1GB default for neuroimaging data
        """Initialize request size limiter middleware.

        Parameters
        ----------
        app : FastAPI
            The FastAPI application instance
        max_size : int, optional
            Maximum allowed request size in bytes (default: 1GB for neuroimaging data)
        """
        self.app = app
        self.max_size = max_size

    async def __call__(self, scope, receive, send):
        """Process ASGI request and check size limits.

        Parameters
        ----------
        scope : dict
            ASGI scope containing request metadata
        receive : callable
            ASGI receive callable for getting request body
        send : callable
            ASGI send callable for sending responses
        """
        if scope["type"] == "http":
            # Check content-length header
            headers = dict(scope.get("headers", []))
            content_length_bytes = headers.get(b"content-length")
            if content_length_bytes:
                try:
                    content_length = int(content_length_bytes.decode())
                    if content_length > self.max_size:
                        response = JSONResponse(
                            status_code=413,
                            content={
                                "error_code": "PAYLOAD_TOO_LARGE",
                                "message": f"Request payload exceeds maximum size of {self.max_size} bytes",
                                "timestamp": datetime.now(timezone.utc).isoformat()
                                + "Z",
                            },
                        )
                        await response(scope, receive, send)
                        return
                except (ValueError, UnicodeDecodeError):
                    pass  # Continue if header parsing fails
        await self.app(scope, receive, send)


# Initialize FastAPI app
app = FastAPI(
    title="EMUSES Foundation FastAPI Service",
    description="REST API for EMUSES pipeline execution and job management",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request size limiting middleware (1GB limit for neuroimaging data)
app.add_middleware(RequestSizeLimiterMiddleware, max_size=1024 * 1024 * 1024)

# Add rate limiting middleware (only if not in testing mode)
if RATE_LIMITING_ENABLED and limiter:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Add observability middleware for HTTP request tracking and correlation IDs
@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    """Track HTTP requests with metrics, structured logging, and correlation IDs"""
    import uuid

    method = request.method
    # Sanitize endpoint path for metrics (remove dynamic parts)
    endpoint = str(request.url.path)
    for pattern in [
        "/api/v1/jobs/",
        "/api/jobs/",
        "/api/v1/artifacts/",
        "/api/artifacts/",
    ]:
        if pattern in endpoint:
            endpoint = pattern + "{id}"
            break

    # Generate or extract correlation ID
    correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())

    # Extract user ID if available (from headers or auth context)
    user_id = request.headers.get("x-user-id")

    # Set request context for structured logging
    set_request_context(request_id=correlation_id, user_id=user_id)

    try:
        with track_http_request(method, endpoint):
            response = await call_next(request)

            # Add correlation ID to response headers
            response.headers["x-correlation-id"] = correlation_id

            # Log request completion with correlation info
            logger.info(
                "HTTP request completed",
                method=method,
                endpoint=endpoint,
                status_code=response.status_code,
                user_agent=request.headers.get("user-agent", "unknown"),
            )

            return response
    finally:
        # Always clear context to prevent leaks
        clear_context()


# Set up multi-user service endpoints (conditionally based on deployment mode)
try:
    from emuses.multi_user_service.deployment_config import (
        detect_deployment_mode, is_service_mode_enabled)

    if is_service_mode_enabled():
        deployment_mode = detect_deployment_mode()
        from emuses.multi_user_service.endpoints import setup_auth_endpoints
        from emuses.multi_user_service.workspace_endpoints import \
            setup_workspace_endpoints

        setup_workspace_endpoints(app)
        setup_auth_endpoints(app)
        logger.info(
            f"Multi-user service endpoints enabled for {deployment_mode.value} mode"
        )
    else:
        logger.info("Multi-user service endpoints disabled for local mode")
except ImportError as e:
    logger.warning(f"Multi-user service components not available: {e}")
except Exception as e:
    logger.error(f"Failed to set up multi-user service endpoints: {e}")

# Initialize core components lazily to avoid import issues
job_manager = None
pipeline_runner = None


class StorageDirectoryFactory:
    """Factory for creating appropriate storage directories based on environment."""

    @staticmethod
    def create_job_storage() -> Path:
        """Create appropriate job storage directory based on environment."""
        import tempfile

        # Check testing mode dynamically
        testing_mode = os.getenv("TESTING_MODE", "false").lower() == "true"

        # In testing mode, use temporary directory
        if testing_mode:
            return Path(tempfile.mkdtemp(prefix="emuses_test_jobs_"))

        # For development/production, use environment variable or default
        job_storage = os.getenv("EMUSES_JOB_STORAGE")
        if job_storage:
            return Path(job_storage)

        # Default to user's local data directory in development
        # In production, this should be set via EMUSES_JOB_STORAGE env var
        return Path.home() / ".local" / "share" / "emuses" / "jobs"

    @staticmethod
    def create_upload_directory() -> Path:
        """Create appropriate upload directory based on environment."""
        import tempfile

        # Check testing mode dynamically
        testing_mode = os.getenv("TESTING_MODE", "false").lower() == "true"

        if testing_mode:
            return Path(tempfile.mkdtemp(prefix="emuses_test_uploads_"))

        upload_dir = Path("/tmp/emuses_uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir


def get_job_manager():
    """Get or create the job manager instance."""
    global job_manager
    if job_manager is None:
        from emuses.foundation_fastapi_service.job_manager import JobManager

        job_manager = JobManager(
            base_directory=StorageDirectoryFactory.create_job_storage()
        )
    return job_manager


def get_pipeline_runner():
    """Get or create the pipeline runner instance."""
    global pipeline_runner
    if pipeline_runner is None:
        from emuses.foundation_fastapi_service.pipeline_runner import \
            PipelineRunner

        pipeline_runner = PipelineRunner(get_job_manager())
    return pipeline_runner


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError exceptions as 400 Bad Request."""
    return JSONResponse(
        status_code=400,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        },
    )


@app.exception_handler(FileNotFoundError)
async def file_not_found_handler(request: Request, exc: FileNotFoundError):
    """Handle FileNotFoundError exceptions as 404 Not Found."""
    return JSONResponse(
        status_code=404,
        content={
            "error_code": "ARTIFACT_NOT_FOUND",
            "message": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions as 500 Internal Server Error."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "SYSTEM_ERROR",
            "message": "An internal server error occurred",
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        },
    )


# Utility functions
def validate_job_id(job_id: str) -> UUID:
    """Validate and convert job ID string to UUID.

    Parameters
    ----------
    job_id : str
        Job ID string to validate

    Returns
    -------
    UUID
        Validated UUID object

    Raises
    ------
    ValueError
        If job_id is not a valid UUID format
    """
    try:
        return UUID(job_id)
    except ValueError:
        raise ValueError(f"Invalid job ID format: {job_id}")


def secure_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks.

    Parameters
    ----------
    filename : str
        Original filename

    Returns
    -------
    str
        Sanitized filename safe for filesystem operations
    """
    # Remove path separators and parent directory references
    filename = filename.replace("/", "").replace("\\", "").replace("..", "")
    # Remove any remaining problematic characters
    filename = "".join(c for c in filename if c.isalnum() or c in "._-")
    # Limit length
    if len(filename) > 255:
        filename = filename[:255]
    return filename


def validate_file_path(file_path: str) -> Path:
    """Validate file path exists and is accessible.

    Parameters
    ----------
    file_path : str
        Path to validate

    Returns
    -------
    Path
        Validated Path object

    Raises
    ------
    ValueError
        If file path does not exist or is not accessible
    """
    # Convert Windows paths to WSL paths if necessary
    converted_path = _convert_windows_path_to_wsl(file_path)
    path = Path(converted_path)

    if not path.exists():
        raise ValueError(f"File not found: {file_path} (tried: {converted_path})")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path} (tried: {converted_path})")
    return path


def _convert_windows_path_to_wsl(file_path: str) -> str:
    """Convert Windows path to WSL path if needed.

    Only performs conversion in WSL environment to avoid breaking
    other deployment scenarios.

    Parameters
    ----------
    file_path : str
        Original file path (may be Windows or Linux format)

    Returns
    -------
    str
        Path converted to WSL format if necessary
    """
    import os

    # Only convert if we're in WSL environment
    if not (os.path.exists("/mnt/c") or "microsoft" in os.uname().release.lower()):
        return file_path

    # Clean up any combined paths that got corrupted
    # Handle case where working directory got prepended to Windows path
    if "/mnt/c/Users/" in file_path and ":\\" in file_path:
        # Extract just the Windows path part after the last occurrence of drive letter pattern
        import re

        match = re.search(r'([A-Za-z]):\\([^"]*)', file_path)
        if match:
            drive_letter = match.group(1).lower()
            rest_of_path = match.group(2).replace("\\", "/")
            return f"/mnt/{drive_letter}/{rest_of_path}"

    # Check if it's a Windows path (contains drive letter)
    if len(file_path) >= 3 and file_path[1] == ":" and file_path[2] == "\\":
        # Convert Windows path like "S:\folder\file.txt" to "/mnt/s/folder/file.txt"
        drive_letter = file_path[0].lower()
        rest_of_path = file_path[3:].replace("\\", "/")
        return f"/mnt/{drive_letter}/{rest_of_path}"

    # Already in Linux/WSL format or relative path
    return file_path


# Conditional rate limiting helper function
def conditional_rate_limit(rate_limit_str: str):
    """Apply rate limiting only if enabled (not in testing mode)."""

    def decorator(func):
        """Conditional decorator for rate limiting.

        Parameters
        ----------
        func : callable
            The function to potentially apply rate limiting to

        Returns
        -------
        callable
            The function with or without rate limiting applied
        """
        if RATE_LIMITING_ENABLED and limiter:
            return limiter.limit(rate_limit_str)(func)
        return func

    return decorator


# Pipeline Execution Endpoints
@app.post("/api/v1/jobs/pipeline/full", status_code=201)
@conditional_rate_limit(
    "50/hour"
)  # Rate limit: 50 jobs per hour per IP (more realistic for EMUSES)
async def submit_full_pipeline_job(
    request: Request, job_request: JobSubmissionRequest
) -> JobStatusResponse:
    """Submit a full pipeline job for execution.

    This endpoint accepts a complete pipeline configuration and submits it
    for background execution. All pipeline stages (UMAP, Heatmap, Prediction)
    will be executed based on the configuration.

    Parameters
    ----------
    job_request : JobSubmissionRequest
        Job submission request containing pipeline configuration and metadata

    Returns
    -------
    JobStatusResponse
        Initial job status with job ID and submission details

    Raises
    ------
    HTTPException
        400: Invalid configuration or validation errors
        500: Internal server error during job creation
    """
    try:
        # Validate pipeline configuration
        config = job_request.pipeline_config

        # Validate required fields
        if "input_dataset" not in config:
            raise ValueError("input_dataset is required")
        if "scores" not in config:
            raise ValueError("scores is required")
        if "output_folder" not in config:
            raise ValueError("output_folder is required")

        # Validate file paths exist
        validate_file_path(config["input_dataset"])
        validate_file_path(config["scores"])
        if config.get("label_dataset"):
            validate_file_path(config["label_dataset"])

        # Create job with original config (for logging/tracking)
        job_id = get_job_manager().create_job(
            config=config,
            job_name=job_request.job_name,
            description=job_request.description,
        )

        # Create a converted copy of config for pipeline execution only
        pipeline_config = config.copy()
        pipeline_config["input_dataset"] = _convert_windows_path_to_wsl(
            config["input_dataset"]
        )
        pipeline_config["scores"] = _convert_windows_path_to_wsl(config["scores"])
        if pipeline_config.get("output_folder"):
            pipeline_config["output_folder"] = _convert_windows_path_to_wsl(
                config["output_folder"]
            )
        if pipeline_config.get("label_dataset"):
            pipeline_config["label_dataset"] = _convert_windows_path_to_wsl(
                config["label_dataset"]
            )

        # Wrap converted config in the expected structure for pipeline runner
        pipeline_context = {
            "config": pipeline_config,  # Use converted paths for pipeline
            "input_dataset": pipeline_config.get("input_dataset"),
            "scores_dataset": pipeline_config.get("scores"),
        }

        # Submit for background execution
        asyncio.create_task(
            get_pipeline_runner().execute_pipeline(job_id, pipeline_context)
        )

        # Return initial status
        status = get_job_manager().get_job_status(job_id)
        return JobStatusResponse(**status)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "VALIDATION_ERROR",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            },
        )


@app.post("/api/v1/jobs/pipeline/stage/{stage_name}", status_code=201)
@conditional_rate_limit("100/hour")  # Rate limit: 100 stage jobs per hour per IP
async def submit_stage_specific_job(
    request: Request, stage_name: str, job_request: JobSubmissionRequest
) -> JobStatusResponse:
    """Submit a single stage pipeline job for execution.

    This endpoint accepts a pipeline configuration and executes only the
    specified stage (umap, heatmap, or prediction).

    Parameters
    ----------
    stage_name : str
        Name of the stage to execute (umap, heatmap, prediction)
    job_request : JobSubmissionRequest
        Job submission request containing pipeline configuration and metadata

    Returns
    -------
    JobStatusResponse
        Initial job status with job ID and submission details

    Raises
    ------
    HTTPException
        400: Invalid stage name or configuration
        500: Internal server error during job creation
    """
    valid_stages = ["umap", "heatmap", "prediction"]
    if stage_name not in valid_stages:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "VALIDATION_ERROR",
                "message": f"Invalid stage name: {stage_name}. Valid stages: {valid_stages}",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        )

    try:
        # Modify config to enable only the specified stage
        config = job_request.pipeline_config.copy()
        config["umap_stage_enabled"] = stage_name == "umap"
        config["heatmap_stage_enabled"] = stage_name == "heatmap"
        config["prediction_stage_enabled"] = stage_name == "prediction"

        # Validate required fields
        if "input_dataset" not in config:
            raise ValueError("input_dataset is required")
        if "scores" not in config:
            raise ValueError("scores is required")
        if "output_folder" not in config:
            raise ValueError("output_folder is required")

        # Validate file paths exist
        validate_file_path(config["input_dataset"])
        validate_file_path(config["scores"])

        # Create job
        job_id = get_job_manager().create_job(
            config=config,
            job_name=job_request.job_name or f"{stage_name.title()} Stage Job",
            description=job_request.description,
        )

        # Wrap config in the expected structure for pipeline runner
        pipeline_context = {
            "config": config,
            "input_dataset": config.get("input_dataset"),
            "scores_dataset": config.get("scores"),
        }

        # Submit for background execution
        asyncio.create_task(
            get_pipeline_runner().execute_pipeline(job_id, pipeline_context)
        )

        # Return initial status
        status = get_job_manager().get_job_status(job_id)
        return JobStatusResponse(**status)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "VALIDATION_ERROR",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        )


# Job Management Endpoints
@app.get("/api/v1/jobs/{job_id}/status")
@conditional_rate_limit("300/minute")  # Rate limit: 300 status checks per minute per IP
async def get_job_status(request: Request, job_id: str) -> JobStatusResponse:
    """Get status and progress information for a job.

    This endpoint returns the current status, progress, and metadata
    for the specified job.

    Parameters
    ----------
    job_id : str
        UUID of the job to query

    Returns
    -------
    JobStatusResponse
        Current job status including progress and stage information

    Raises
    ------
    HTTPException
        400: Invalid job ID format
        404: Job not found
    """
    try:
        # Validate job ID format
        job_uuid = validate_job_id(job_id)

        # Get job status
        status = get_job_manager().get_job_status(job_uuid)
        return JobStatusResponse(**status)

    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "JOB_NOT_FOUND",
                    "message": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                },
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "VALIDATION_ERROR",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
            )


@app.get("/api/v1/jobs/{job_id}/logs")
@conditional_rate_limit("100/minute")  # Rate limit: 100 log requests per minute per IP
async def get_job_logs(request: Request, job_id: str) -> Dict[str, List[str]]:
    """Get execution logs for a job.

    This endpoint returns the execution logs for the specified job,
    including timestamps and log levels.

    Parameters
    ----------
    job_id : str
        UUID of the job to query

    Returns
    -------
    Dict[str, List[str]]
        Dictionary containing list of log entries

    Raises
    ------
    HTTPException
        400: Invalid job ID format
        404: Job not found
    """
    try:
        # Validate job ID format
        job_uuid = validate_job_id(job_id)

        # Get job logs
        logs = get_job_manager().get_job_logs(job_uuid)
        return {"logs": logs}

    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "JOB_NOT_FOUND",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "VALIDATION_ERROR",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
            )


@app.delete("/api/v1/jobs/{job_id}")
@conditional_rate_limit("50/minute")  # Rate limit: 50 cancellations per minute per IP
async def cancel_job(request: Request, job_id: str) -> Dict[str, str]:
    """Cancel or delete a job.

    This endpoint cancels a running job or deletes a completed job
    and its associated artifacts.

    Parameters
    ----------
    job_id : str
        UUID of the job to cancel/delete

    Returns
    -------
    Dict[str, str]
        Confirmation message

    Raises
    ------
    HTTPException
        400: Invalid job ID format
        404: Job not found
    """
    try:
        # Validate job ID format
        job_uuid = validate_job_id(job_id)

        # Cancel job
        success = get_job_manager().cancel_job(job_uuid)
        if success:
            return {"message": "Job cancelled successfully"}
        else:
            return {"message": "Job deletion completed"}

    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "JOB_NOT_FOUND",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "VALIDATION_ERROR",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
            )


@app.get("/api/v1/jobs")
@conditional_rate_limit("100/minute")  # Rate limit: 100 list requests per minute per IP
async def list_jobs(
    request: Request, status: Optional[str] = None, limit: int = 50, offset: int = 0
) -> Dict[str, Any]:
    """List jobs with optional filtering.

    This endpoint returns a list of jobs, optionally filtered by status,
    with pagination support.

    Parameters
    ----------
    status : Optional[str]
        Filter jobs by status (SUBMITTED, RUNNING, COMPLETED, FAILED, CANCELLED)
    limit : int
        Maximum number of jobs to return (default: 50, max: 100)
    offset : int
        Number of jobs to skip for pagination (default: 0)

    Returns
    -------
    Dict[str, Any]
        Dictionary containing job list and pagination metadata
    """
    # Validate parameters
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1
    if offset < 0:
        offset = 0

    valid_statuses = ["submitted", "running", "completed", "failed", "cancelled"]
    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "VALIDATION_ERROR",
                "message": f"Invalid status filter: {status}. Valid statuses: {valid_statuses}",
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            },
        )

    # Get job list
    jobs = get_job_manager().list_jobs(status=status, limit=limit, offset=offset)
    total_count = get_job_manager().count_jobs(status=status)

    return {
        "jobs": jobs,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total_count,
    }


# Artifact Management Endpoints
@app.get("/api/v1/jobs/{job_id}/artifacts")
@conditional_rate_limit(
    "100/minute"
)  # Rate limit: 100 artifact list requests per minute per IP
async def list_job_artifacts(
    request: Request, job_id: str
) -> Dict[str, List[Dict[str, Any]]]:
    """List available artifacts for a job.

    This endpoint returns a list of all artifacts (output files) generated
    by the specified job, including file metadata.

    Parameters
    ----------
    job_id : str
        UUID of the job to query

    Returns
    -------
    Dict[str, List[Dict[str, Any]]]
        Dictionary containing list of artifact metadata

    Raises
    ------
    HTTPException
        400: Invalid job ID format
        404: Job not found
    """
    try:
        # Validate job ID format
        job_uuid = validate_job_id(job_id)

        # Get job output directory
        output_dir = get_job_manager().get_job_output_dir(job_uuid)
        if not output_dir.exists():
            return {"artifacts": []}

        # List artifacts
        artifacts = []
        for file_path in output_dir.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                artifacts.append(
                    {
                        "filename": file_path.name,
                        "size": stat.st_size,
                        "modified_at": datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat()
                        + "Z",
                        "content_type": mimetypes.guess_type(str(file_path))[0]
                        or "application/octet-stream",
                    }
                )

        return {"artifacts": artifacts}

    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "JOB_NOT_FOUND",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "VALIDATION_ERROR",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
            )


@app.get("/api/v1/jobs/{job_id}/artifacts/{filename}")
@conditional_rate_limit("200/minute")  # Rate limit: 200 downloads per minute per IP
async def download_job_artifact(
    request: Request, job_id: str, filename: str
) -> FileResponse:
    """Download a specific artifact from a job.

    This endpoint provides secure download access to job artifacts,
    with path traversal protection and proper content-type headers.

    Parameters
    ----------
    job_id : str
        UUID of the job
    filename : str
        Name of the artifact file to download

    Returns
    -------
    FileResponse
        File response with appropriate headers and content-type

    Raises
    ------
    HTTPException
        400: Invalid job ID format or filename
        404: Job or artifact not found
    """
    try:
        # Validate job ID format
        job_uuid = validate_job_id(job_id)

        # Sanitize filename to prevent path traversal
        safe_filename = secure_filename(filename)
        if not safe_filename or safe_filename != filename:
            raise ValueError(f"Invalid filename: {filename}")

        # Get job output directory and construct file path
        output_dir = get_job_manager().get_job_output_dir(job_uuid)
        file_path = output_dir / safe_filename

        # Ensure file exists and is within job directory
        if not file_path.exists():
            raise FileNotFoundError(f"Artifact not found: {filename}")

        # Resolve path and check it's still within job directory (prevent symlink attacks)
        resolved_path = file_path.resolve()
        resolved_output_dir = output_dir.resolve()
        if not str(resolved_path).startswith(str(resolved_output_dir)):
            raise ValueError(f"Invalid file path: {filename}")

        # Determine content type
        content_type = (
            mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        )

        return FileResponse(
            path=str(file_path), filename=filename, media_type=content_type
        )

    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "JOB_NOT_FOUND",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "VALIDATION_ERROR",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
            )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "ARTIFACT_NOT_FOUND",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            },
        )


# File Upload Endpoints - Task 9


def create_upload_directory() -> Path:
    """Create and return the upload directory path."""
    return StorageDirectoryFactory.create_upload_directory()


def validate_csv_file(file: UploadFile) -> None:
    """Validate that uploaded file is a valid CSV.

    Parameters
    ----------
    file : UploadFile
        The uploaded file to validate

    Raises
    ------
    HTTPException
        If file is not a valid CSV
    """
    if not file.content_type or "text/csv" not in file.content_type.lower():
        if not file.filename or not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files are allowed")


def generate_upload_file_path(upload_dir: Path, filename: str, file_type: str) -> Path:
    """Generate a unique file path for uploaded file.

    Parameters
    ----------
    upload_dir : Path
        Base upload directory
    filename : str
        Original filename
    file_type : str
        Type of file (features, scores, labels)

    Returns
    -------
    Path
        Unique file path for the upload
    """
    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S_%f"
    )  # Include microseconds
    file_id = f"{timestamp}_{file_type}"
    safe_filename = secure_filename(filename)

    # Create job-specific subdirectory
    job_dir = upload_dir / file_id
    job_dir.mkdir(parents=True, exist_ok=True)

    return job_dir / safe_filename


@app.post("/api/v1/upload/features", status_code=201)
@conditional_rate_limit("10/minute")  # Rate limit: 10 uploads per minute per IP
async def upload_features_file(
    file: UploadFile = File(..., description="Features CSV file to upload"),
    request: Request = None,
) -> FileUploadResponse:
    """Upload features file for pipeline processing.

    Task 9.1: Features file upload endpoint with CSV validation and temporary storage

    Parameters
    ----------
    file : UploadFile
        The features CSV file to upload
    request : Request
        FastAPI request object for rate limiting

    Returns
    -------
    FileUploadResponse
        Information about the uploaded file
    """

    try:
        # Validate file
        validate_csv_file(file)

        # Check file size (up to 1GB for neuroimaging data)
        if file.size and file.size > 1024 * 1024 * 1024:  # 1GB
            raise HTTPException(
                status_code=413, detail="File too large. Maximum size is 1GB."
            )

        # Create upload directory and generate file path
        upload_dir = create_upload_directory()
        file_path = generate_upload_file_path(upload_dir, file.filename, "features")

        # Save uploaded file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # Generate response
        file_id = file_path.parent.name
        upload_time = datetime.now(timezone.utc).isoformat() + "Z"

        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            file_path=str(file_path),
            content_type=file.content_type or "text/csv",
            size=len(content),
            upload_time=upload_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading features file: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to upload features file: {str(e)}"
        )


@app.post("/api/v1/upload/scores", status_code=201)
@conditional_rate_limit("10/minute")  # Rate limit: 10 uploads per minute per IP
async def upload_scores_file(
    file: UploadFile = File(..., description="Scores CSV file to upload"),
    request: Request = None,
) -> FileUploadResponse:
    """Upload scores file for pipeline processing.

    Task 9.2: Scores file upload endpoint with proper content-type validation

    Parameters
    ----------
    file : UploadFile
        The scores CSV file to upload
    request : Request
        FastAPI request object for rate limiting

    Returns
    -------
    FileUploadResponse
        Information about the uploaded file
    """

    try:
        # Validate file
        validate_csv_file(file)

        # Check file size (up to 1GB for neuroimaging data)
        if file.size and file.size > 1024 * 1024 * 1024:  # 1GB
            raise HTTPException(
                status_code=413, detail="File too large. Maximum size is 1GB."
            )

        # Create upload directory and generate file path
        upload_dir = create_upload_directory()
        file_path = generate_upload_file_path(upload_dir, file.filename, "scores")

        # Save uploaded file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # Generate response
        file_id = file_path.parent.name
        upload_time = datetime.utcnow().isoformat() + "Z"

        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            file_path=str(file_path),
            content_type=file.content_type or "text/csv",
            size=len(content),
            upload_time=upload_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading scores file: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to upload scores file: {str(e)}"
        )


@app.post("/api/v1/upload/labels", status_code=201)
@conditional_rate_limit("10/minute")  # Rate limit: 10 uploads per minute per IP
async def upload_labels_file(
    file: UploadFile = File(..., description="Labels CSV file to upload (optional)"),
    request: Request = None,
) -> FileUploadResponse:
    """Upload labels file for supervised learning.

    Task 9.3: Optional labels file upload endpoint for supervised learning

    Parameters
    ----------
    file : UploadFile
        The labels CSV file to upload
    request : Request
        FastAPI request object for rate limiting

    Returns
    -------
    FileUploadResponse
        Information about the uploaded file
    """

    try:
        # Validate file
        validate_csv_file(file)

        # Check file size (up to 1GB for neuroimaging data)
        if file.size and file.size > 1024 * 1024 * 1024:  # 1GB
            raise HTTPException(
                status_code=413, detail="File too large. Maximum size is 1GB."
            )

        # Create upload directory and generate file path
        upload_dir = create_upload_directory()
        file_path = generate_upload_file_path(upload_dir, file.filename, "labels")

        # Save uploaded file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # Generate response
        file_id = file_path.parent.name
        upload_time = datetime.utcnow().isoformat() + "Z"

        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            file_path=str(file_path),
            content_type=file.content_type or "text/csv",
            size=len(content),
            upload_time=upload_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading labels file: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to upload labels file: {str(e)}"
        )


@app.post("/api/v1/inference", status_code=200)
@conditional_rate_limit("20/hour")  # Rate limit: 20 inference requests per hour per IP
async def run_inference(
    request: Request, inference_request: InferenceRequest
) -> InferenceResponse:
    """
    Run inference on trained EMUSES model.
    
    This endpoint executes inference using the InferenceStage pipeline component,
    supporting both inference and validation modes with comprehensive error handling.
    
    Parameters
    ----------
    inference_request : InferenceRequest
        Inference request containing model path, data path, and configuration options
        
    Returns
    -------
    InferenceResponse
        Inference results including predictions, performance metrics, and output files
    
    Raises
    ------
    HTTPException
        422: Validation error or inference execution failure
        500: Internal server error during inference
    """
    request_id = str(uuid4())
    set_request_context(request_id=request_id, user_id="inference_user")
    
    try:
        with track_http_request(
            method="POST", 
            endpoint="/api/v1/inference"
        ):
            logger.info(
                "Starting inference request",
                extra={
                    "request_id": request_id,
                    "model_path": inference_request.model_path,
                    "data_path": inference_request.data_path,
                    "output_format": inference_request.output_format,
                    "validation_mode": inference_request.validation_mode
                }
            )
            
            # Import inference components
            from emuses.pipelines.inference_stage import InferenceStage
            from emuses.pipelines.pipeline_config import PipelineConfig
            
            # Create pipeline configuration
            inference_config = PipelineConfig(
                model_path=inference_request.model_path,
                data_path=inference_request.data_path,
                output_path=inference_request.output_path,
                validate_mode=inference_request.validation_mode,
                output_folder=inference_request.output_path or (inference_request.model_path + "/inference_results")
            )
            
            # Create and run inference stage
            stage = InferenceStage(inference_config)
            
            # Prepare execution context
            context = {
                "verify_integrity": inference_request.verify_integrity,
                "output_format": inference_request.output_format
            }
            
            # Execute inference
            results = stage.run(context)
            
            # Extract results for response
            predictions = results.get("predictions", [])
            if hasattr(predictions, 'tolist'):
                predictions = predictions.tolist()
                
            confidence_scores = None
            if "prediction_details" in results:
                confidence_scores = results["prediction_details"].get("confidence_scores", [])
                if hasattr(confidence_scores, 'tolist'):
                    confidence_scores = confidence_scores.tolist()
            
            performance = results.get("performance_breakdown", {})
            
            # Create response
            response = {
                "status": results.get("status", "completed"),
                "mode": results.get("mode", "inference"),
                "samples_processed": results.get("samples_processed", 0),
                "predictions": predictions,
                "confidence_scores": confidence_scores,
                "processing_time_ms": performance.get("total_duration_ms", 0.0),
                "throughput_samples_per_sec": performance.get("throughput_samples_per_sec", 0.0),
                "model_info": results.get("model_info", {}),
                "output_files": results.get("output_files", {}),
                "validation_metrics": results.get("validation_metrics")
            }
            
            logger.info(
                "Inference request completed successfully",
                extra={
                    "request_id": request_id,
                    "samples_processed": response["samples_processed"],
                    "processing_time_ms": response["processing_time_ms"],
                    "mode": response["mode"]
                }
            )
            
            return response
            
    except FileNotFoundError as e:
        logger.error(
            "Model or data file not found",
            extra={"request_id": request_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "FILE_NOT_FOUND",
                "message": f"Required file not found: {str(e)}",
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
            }
        )
    except ValueError as e:
        logger.error(
            "Inference validation error",
            extra={"request_id": request_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "INFERENCE_VALIDATION_ERROR", 
                "message": f"Inference validation failed: {str(e)}",
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
            }
        )
    except Exception as e:
        logger.error(
            "Inference execution failed",
            extra={"request_id": request_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "INFERENCE_EXECUTION_ERROR",
                "message": f"Inference execution failed: {str(e)}",
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
            }
        )
    finally:
        clear_context()


# Health check endpoint
@app.get("/api/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint.

    Returns
    -------
    Dict[str, str]
        Health status information
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "version": "1.0.0",
    }


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint for monitoring and observability.

    Returns
    -------
    Response
        Prometheus-formatted metrics data
    """
    from fastapi import Response

    metrics_registry = get_metrics_registry()
    metrics_data = metrics_registry.get_metrics()

    return Response(
        content=metrics_data, media_type=metrics_registry.get_content_type()
    )


# Add request size limiting middleware
app.add_middleware(
    RequestSizeLimiterMiddleware, max_size=10 * 1024 * 1024
)  # 10MB limit

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
