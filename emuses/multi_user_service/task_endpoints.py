"""Background task management endpoints for multi-user EMUSES service.

This module provides RESTful API endpoints for background task management
including task submission, status checking, cancellation, and monitoring
with proper user context isolation and authentication.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from emuses.multi_user_service.auth import fastapi_users
from emuses.multi_user_service.background_tasks import (BackgroundTask,
                                                        BackgroundTaskManager,
                                                        TaskStatus)
from emuses.multi_user_service.database import get_async_session
from emuses.multi_user_service.job_manager import MultiUserJobManager
from emuses.multi_user_service.models import User

logger = logging.getLogger(__name__)

# Global task manager instance (will be initialized by the application)
_task_manager: Optional[BackgroundTaskManager] = None


def get_task_manager() -> BackgroundTaskManager:
    """Get the global task manager instance.

    Returns
    -------
    BackgroundTaskManager
        Global task manager instance

    Raises
    ------
    HTTPException
        If task manager not initialized
    """
    if _task_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background task manager not initialized",
        )
    return _task_manager


def set_task_manager(task_manager: BackgroundTaskManager) -> None:
    """Set the global task manager instance.

    Parameters
    ----------
    task_manager : BackgroundTaskManager
        Task manager instance to set
    """
    global _task_manager
    _task_manager = task_manager


class TaskSubmitRequest(BaseModel):
    """Background task submission request schema.

    Schema for submitting new background tasks with pipeline configuration.

    Attributes
    ----------
    job_id : str
        Job ID to execute as background task
    config : Dict[str, Any]
        Pipeline configuration for execution
    expected_compute_hours : float, optional
        Expected compute time for quota validation
    expected_storage_gb : float, optional
        Expected storage usage for quota validation
    """

    job_id: str
    config: Dict[str, Any]
    expected_compute_hours: float = Field(default=0.0, ge=0.0)
    expected_storage_gb: float = Field(default=0.0, ge=0.0)


class TaskResponse(BaseModel):
    """Background task response schema.

    Schema for returning task information in API responses.

    Attributes
    ----------
    task_id : str
        Task UUID
    job_id : str
        Associated job UUID
    user_id : str
        Owner user UUID
    status : str
        Current task status
    created_at : datetime
        Task creation timestamp
    started_at : datetime, optional
        Task start timestamp
    completed_at : datetime, optional
        Task completion timestamp
    progress : float
        Task progress (0.0 to 1.0)
    message : str, optional
        Status message
    error_message : str, optional
        Error message if failed
    expected_compute_hours : float
        Expected compute time
    expected_storage_gb : float
        Expected storage usage
    """

    task_id: str
    job_id: str
    user_id: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float
    message: Optional[str] = None
    error_message: Optional[str] = None
    expected_compute_hours: float
    expected_storage_gb: float

    model_config = ConfigDict(from_attributes=True)


class TaskResultResponse(BaseModel):
    """Task execution result response schema.

    Schema for returning task execution results.

    Attributes
    ----------
    task_id : str
        Task UUID
    job_id : str
        Associated job UUID
    status : str
        Task status
    result : Dict[str, Any], optional
        Execution result data
    execution_time_hours : float, optional
        Actual execution time
    storage_bytes : int, optional
        Actual storage usage
    completed_at : datetime, optional
        Completion timestamp
    """

    task_id: str
    job_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    execution_time_hours: Optional[float] = None
    storage_bytes: Optional[int] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SystemStatusResponse(BaseModel):
    """System status response schema.

    Schema for returning background task system status.

    Attributes
    ----------
    max_workers : int
        Maximum number of worker processes
    active_workers : int
        Currently active workers
    task_counts : Dict[str, int]
        Task counts by status
    total_tasks : int
        Total number of tasks
    process_memory_limit_gb : float
        Memory limit per process
    executor_active : bool
        Whether executor is active
    """

    max_workers: int
    active_workers: int
    task_counts: Dict[str, int]
    total_tasks: int
    process_memory_limit_gb: float
    executor_active: bool

    model_config = ConfigDict(from_attributes=True)


def _task_to_response(task: BackgroundTask) -> TaskResponse:
    """Convert BackgroundTask to TaskResponse.

    Parameters
    ----------
    task : BackgroundTask
        Task object to convert

    Returns
    -------
    TaskResponse
        Task response object
    """
    return TaskResponse(
        task_id=str(task.task_id),
        job_id=str(task.job_id),
        user_id=str(task.user_id),
        status=task.status.value,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        progress=task.progress,
        message=task.message,
        error_message=task.error_message,
        expected_compute_hours=task.expected_compute_hours,
        expected_storage_gb=task.expected_storage_gb,
    )


def create_task_router() -> APIRouter:
    """Create background task management router.

    Creates FastAPI router with background task management endpoints
    including task submission, status checking, and cancellation.

    Returns
    -------
    APIRouter
        Configured task management router
    """
    router = APIRouter(
        prefix="/tasks",
        tags=["Background Tasks"],
        responses={404: {"description": "Not found"}},
    )

    current_user = fastapi_users.current_user()

    @router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
    async def submit_task(
        request: TaskSubmitRequest,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(current_user),
        session: AsyncSession = Depends(get_async_session),
        task_manager: BackgroundTaskManager = Depends(get_task_manager),
    ) -> TaskResponse:
        """Submit a new background task for execution.

        Creates a new background task for pipeline execution with user context
        isolation and quota validation.

        Parameters
        ----------
        request : TaskSubmitRequest
            Task submission request
        background_tasks : BackgroundTasks
            FastAPI background tasks for async submission
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session for quota validation
        task_manager : BackgroundTaskManager
            Background task manager instance

        Returns
        -------
        TaskResponse
            Created task information

        Raises
        ------
        HTTPException
            If quota validation fails or task creation fails
        """
        try:
            job_id = UUID(request.job_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job ID format"
            )

        try:
            # Create background task with quota validation
            task_id = task_manager.create_task(
                job_id=job_id,
                user_id=current_user.id,
                config=request.config,
                expected_compute_hours=request.expected_compute_hours,
                expected_storage_gb=request.expected_storage_gb,
                db_session=session,
            )

            # Submit task for execution in background
            background_tasks.add_task(_submit_task_async, task_manager, task_id)

            # Get created task
            task = task_manager.get_task(task_id)
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create task",
                )

            logger.info(
                f"Created background task {task_id} for job {job_id} by user {current_user.id}"
            )
            return _task_to_response(task)

        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to create background task: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create background task",
            )

    @router.get("/", response_model=List[TaskResponse])
    async def list_user_tasks(
        status_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        current_user: User = Depends(current_user),
        task_manager: BackgroundTaskManager = Depends(get_task_manager),
    ) -> List[TaskResponse]:
        """List background tasks for the current user.

        Returns paginated list of user's background tasks with optional
        status filtering.

        Parameters
        ----------
        status_filter : Optional[str]
            Optional status filter (pending, queued, running, completed, failed, cancelled)
        limit : int
            Maximum number of tasks to return (default 50)
        offset : int
            Number of tasks to skip (default 0)
        current_user : User
            Current authenticated user
        task_manager : BackgroundTaskManager
            Background task manager instance

        Returns
        -------
        List[TaskResponse]
            List of user's tasks
        """
        # Parse status filter
        status_enum = None
        if status_filter:
            try:
                status_enum = TaskStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status filter: {status_filter}",
                )

        # Get user tasks
        tasks = task_manager.list_user_tasks(
            user_id=current_user.id, status=status_enum, limit=limit, offset=offset
        )

        return [_task_to_response(task) for task in tasks]

    @router.get("/{task_id}", response_model=TaskResponse)
    async def get_task(
        task_id: str,
        current_user: User = Depends(current_user),
        task_manager: BackgroundTaskManager = Depends(get_task_manager),
    ) -> TaskResponse:
        """Get background task by ID.

        Returns detailed information about a specific background task
        with user ownership validation.

        Parameters
        ----------
        task_id : str
            Task UUID to retrieve
        current_user : User
            Current authenticated user
        task_manager : BackgroundTaskManager
            Background task manager instance

        Returns
        -------
        TaskResponse
            Task information

        Raises
        ------
        HTTPException
            If task not found or user doesn't own it
        """
        try:
            task_uuid = UUID(task_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid task ID format"
            )

        task = task_manager.get_task(task_uuid)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

        # Validate user ownership
        if task.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this task",
            )

        return _task_to_response(task)

    @router.get("/{task_id}/result", response_model=TaskResultResponse)
    async def get_task_result(
        task_id: str,
        current_user: User = Depends(current_user),
        task_manager: BackgroundTaskManager = Depends(get_task_manager),
    ) -> TaskResultResponse:
        """Get background task execution result.

        Returns execution results for a completed background task
        with user ownership validation.

        Parameters
        ----------
        task_id : str
            Task UUID to get result for
        current_user : User
            Current authenticated user
        task_manager : BackgroundTaskManager
            Background task manager instance

        Returns
        -------
        TaskResultResponse
            Task execution result

        Raises
        ------
        HTTPException
            If task not found, user doesn't own it, or task not completed
        """
        try:
            task_uuid = UUID(task_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid task ID format"
            )

        task = task_manager.get_task(task_uuid)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

        # Validate user ownership
        if task.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this task",
            )

        # Check if task is completed
        if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Task is not completed yet"
            )

        # Extract result information
        result_data = task.result if task.status == TaskStatus.COMPLETED else None
        execution_time = None
        storage_bytes = None

        if result_data:
            execution_time = result_data.get("execution_time_hours")
            storage_bytes = result_data.get("storage_bytes")

        return TaskResultResponse(
            task_id=str(task.task_id),
            job_id=str(task.job_id),
            status=task.status.value,
            result=result_data,
            execution_time_hours=execution_time,
            storage_bytes=storage_bytes,
            completed_at=task.completed_at,
        )

    @router.post("/{task_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
    async def cancel_task(
        task_id: str,
        current_user: User = Depends(current_user),
        task_manager: BackgroundTaskManager = Depends(get_task_manager),
    ) -> None:
        """Cancel a background task.

        Cancels a pending, queued, or running background task with user
        ownership validation.

        Parameters
        ----------
        task_id : str
            Task UUID to cancel
        current_user : User
            Current authenticated user
        task_manager : BackgroundTaskManager
            Background task manager instance

        Raises
        ------
        HTTPException
            If task not found, user doesn't own it, or task cannot be cancelled
        """
        try:
            task_uuid = UUID(task_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid task ID format"
            )

        try:
            cancelled = task_manager.cancel_task(task_uuid, current_user.id)
            if not cancelled:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Task cannot be cancelled (already completed or failed)",
                )

            logger.info(
                f"Cancelled background task {task_id} by user {current_user.id}"
            )

        except ValueError as e:
            if "not found" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
                )
            elif "not authorized" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to cancel this task",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
                )

    @router.get("/system/status", response_model=SystemStatusResponse)
    async def get_system_status(
        current_user: User = Depends(current_user),
        task_manager: BackgroundTaskManager = Depends(get_task_manager),
    ) -> SystemStatusResponse:
        """Get background task system status.

        Returns system metrics and status information for background
        task processing. Available to all authenticated users.

        Parameters
        ----------
        current_user : User
            Current authenticated user
        task_manager : BackgroundTaskManager
            Background task manager instance

        Returns
        -------
        SystemStatusResponse
            System status information
        """
        status_info = task_manager.get_system_status()

        return SystemStatusResponse(
            max_workers=status_info["max_workers"],
            active_workers=status_info["active_workers"],
            task_counts=status_info["task_counts"],
            total_tasks=status_info["total_tasks"],
            process_memory_limit_gb=status_info["process_memory_limit_gb"],
            executor_active=status_info["executor_active"],
        )

    return router


def _submit_task_async(task_manager: BackgroundTaskManager, task_id: UUID) -> None:
    """Submit task for execution asynchronously.

    This function is called as a FastAPI background task to submit
    the task for execution without blocking the API response.

    Parameters
    ----------
    task_manager : BackgroundTaskManager
        Task manager instance
    task_id : UUID
        Task ID to submit
    """
    try:
        task_manager.submit_task(task_id)
    except Exception as e:
        logger.error(f"Failed to submit task {task_id} for execution: {e}")

        # Update task status to failed
        task = task_manager.get_task(task_id)
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = f"Failed to submit task: {str(e)}"
            task.completed_at = datetime.utcnow()
