"""Background task management with ProcessPoolExecutor integration.

This module provides hybrid background processing for the EMUSES multi-user service,
using ProcessPoolExecutor for CPU-intensive pipeline execution while maintaining
user context isolation and comprehensive task monitoring.
"""

import asyncio
import os
import psutil
import signal
import time
import threading
from concurrent.futures import ProcessPoolExecutor, Future, as_completed
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Union, Set
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from emuses.multi_user_service.job_manager import MultiUserJobManager
from emuses.foundation_fastapi_service.pipeline_executor import PipelineExecutor


class TaskStatus(Enum):
    """Background task status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundTask:
    """Background task representation.
    
    Attributes
    ----------
    task_id : UUID
        Unique task identifier
    job_id : UUID
        Associated job ID
    user_id : UUID
        User who owns this task
    config : Dict[str, Any]
        Pipeline configuration
    status : TaskStatus
        Current task status
    created_at : datetime
        Task creation timestamp
    started_at : Optional[datetime]
        Task start timestamp
    completed_at : Optional[datetime]
        Task completion timestamp
    progress : float
        Task progress (0.0 to 1.0)
    message : Optional[str]
        Status message
    result : Optional[Dict[str, Any]]
        Task execution result
    error_message : Optional[str]
        Error message if failed
    process_id : Optional[int]
        Process ID when running
    expected_compute_hours : float
        Expected compute time for quota tracking
    expected_storage_gb : float
        Expected storage for quota tracking
    """
    task_id: UUID
    job_id: UUID
    user_id: UUID
    config: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    process_id: Optional[int] = None
    expected_compute_hours: float = 0.0
    expected_storage_gb: float = 0.0


class BackgroundTaskManager:
    """Manages background task execution with ProcessPoolExecutor.
    
    Provides user workspace isolation, resource monitoring, and process
    lifecycle management for EMUSES pipeline execution.
    
    Attributes
    ----------
    job_manager : MultiUserJobManager
        Multi-user job manager instance
    max_workers : int
        Maximum number of worker processes
    task_timeout : float
        Task execution timeout in seconds
    cleanup_interval : float
        Process cleanup check interval
    """
    
    def __init__(
        self,
        job_manager: MultiUserJobManager,
        max_workers: Optional[int] = None,
        task_timeout: float = 3600.0,  # 1 hour default
        cleanup_interval: float = 60.0,  # 1 minute
        process_memory_limit_gb: float = 8.0
    ):
        """Initialize background task manager.
        
        Parameters
        ----------
        job_manager : MultiUserJobManager
            Multi-user job manager for workspace isolation
        max_workers : Optional[int]
            Maximum worker processes (defaults to CPU count)
        task_timeout : float
            Task execution timeout in seconds
        cleanup_interval : float
            Process cleanup check interval in seconds
        process_memory_limit_gb : float
            Memory limit per process in GB
        """
        self.job_manager = job_manager
        self.max_workers = max_workers or min(32, os.cpu_count() + 4)
        self.task_timeout = task_timeout
        self.cleanup_interval = cleanup_interval
        self.process_memory_limit_gb = process_memory_limit_gb
        
        # Task tracking
        self._tasks: Dict[UUID, BackgroundTask] = {}
        self._task_futures: Dict[UUID, Future] = {}
        self._running_processes: Dict[UUID, int] = {}  # task_id -> process_id
        self._task_lock = threading.RLock()
        
        # Process pool management
        self._executor: Optional[ProcessPoolExecutor] = None
        self._shutdown_event = threading.Event()
        self._cleanup_thread: Optional[threading.Thread] = None
        
        # Monitoring
        self._process_monitor_enabled = True
        self._monitor_thread: Optional[threading.Thread] = None
        
    def configure_process_pool(self) -> None:
        """Configure ProcessPoolExecutor with appropriate settings.
        
        Sets up the process pool with security considerations and resource limits.
        """
        if self._executor is not None:
            return
            
        # Create process pool with configured worker count
        self._executor = ProcessPoolExecutor(
            max_workers=self.max_workers,
            # Use spawn method for better isolation on Unix systems
            mp_context=None  # Use default context
        )
        
        # Start cleanup and monitoring threads
        self._start_background_threads()
        
    def _start_background_threads(self) -> None:
        """Start background threads for cleanup and monitoring."""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_worker,
                daemon=True,
                name="TaskCleanupWorker"
            )
            self._cleanup_thread.start()
            
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._monitor_thread = threading.Thread(
                target=self._process_monitor_worker,
                daemon=True,
                name="ProcessMonitorWorker"
            )
            self._monitor_thread.start()
    
    def create_task(
        self,
        job_id: UUID,
        user_id: UUID,
        config: Dict[str, Any],
        expected_compute_hours: float = 0.0,
        expected_storage_gb: float = 0.0,
        db_session: Optional[Session] = None
    ) -> UUID:
        """Create a new background task.
        
        Parameters
        ----------
        job_id : UUID
            Associated job ID
        user_id : UUID
            User who owns this task
        config : Dict[str, Any]
            Pipeline configuration
        expected_compute_hours : float
            Expected compute time for quota tracking
        expected_storage_gb : float
            Expected storage for quota tracking
        db_session : Optional[Session]
            Database session for quota validation
            
        Returns
        -------
        UUID
            Generated task ID
            
        Raises
        ------
        ValueError
            If quota validation fails or task creation is invalid
        """
        # Validate job ownership
        if not self.job_manager.validate_job_ownership(job_id, user_id):
            raise ValueError("User not authorized to create task for this job")
        
        # Validate quotas if database session provided
        if db_session is not None and (expected_compute_hours > 0 or expected_storage_gb > 0):
            if not self.job_manager.quota_manager.is_quota_available(
                db_session, user_id, expected_storage_gb, expected_compute_hours
            ):
                quota_results = self.job_manager.quota_manager.validate_all_quotas(
                    db_session, user_id, expected_storage_gb, expected_compute_hours
                )
                failed_quotas = [
                    name for name, result in quota_results.items() 
                    if not result.is_valid
                ]
                raise ValueError(f"Quota exceeded for: {', '.join(failed_quotas)}")
        
        # Create background task
        task_id = uuid4()
        task = BackgroundTask(
            task_id=task_id,
            job_id=job_id,
            user_id=user_id,
            config=config,
            expected_compute_hours=expected_compute_hours,
            expected_storage_gb=expected_storage_gb
        )
        
        with self._task_lock:
            self._tasks[task_id] = task
            
        # Update job status
        self.job_manager.update_job_status(
            job_id=job_id,
            status="queued",
            message=f"Background task {task_id} created and queued",
            progress=0.0
        )
        
        return task_id
    
    def submit_task(self, task_id: UUID) -> bool:
        """Submit a task for background execution.
        
        Parameters
        ----------
        task_id : UUID
            Task ID to submit
            
        Returns
        -------
        bool
            True if task was submitted successfully
            
        Raises
        ------
        ValueError
            If task not found or already running
        """
        with self._task_lock:
            if task_id not in self._tasks:
                raise ValueError(f"Task {task_id} not found")
                
            task = self._tasks[task_id]
            
            if task.status != TaskStatus.PENDING:
                raise ValueError(f"Task {task_id} is not in pending status")
            
            # Ensure process pool is configured
            self.configure_process_pool()
            
            # Submit task to process pool
            future = self._executor.submit(
                _execute_pipeline_task,
                task.job_id,
                task.user_id,
                task.config,
                str(self.job_manager.base_directory),
                self.process_memory_limit_gb
            )
            
            # Track future and update status
            self._task_futures[task_id] = future
            task.status = TaskStatus.QUEUED
            task.message = "Task submitted to process pool"
            
            # Add future completion callback
            future.add_done_callback(
                lambda fut: self._on_task_completed(task_id, fut)
            )
        
        # Update job status
        self.job_manager.update_job_status(
            job_id=task.job_id,
            status="queued",
            message="Task submitted for background execution"
        )
        
        return True
    
    def _on_task_completed(self, task_id: UUID, future: Future) -> None:
        """Handle task completion callback.
        
        Parameters
        ----------
        task_id : UUID
            Completed task ID
        future : Future
            Completed future object
        """
        with self._task_lock:
            if task_id not in self._tasks:
                return
                
            task = self._tasks[task_id]
            task.completed_at = datetime.utcnow()
            
            # Remove from running processes
            self._running_processes.pop(task_id, None)
            
            try:
                result = future.result()
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.progress = 1.0
                task.message = "Task completed successfully"
                
                # Update job status
                self.job_manager.update_job_status(
                    job_id=task.job_id,
                    status="completed",
                    message="Background task completed successfully",
                    progress=1.0
                )
                
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                task.message = f"Task failed: {str(e)}"
                
                # Update job status
                self.job_manager.update_job_status(
                    job_id=task.job_id,
                    status="failed",
                    message=f"Background task failed: {str(e)}"
                )
                
            finally:
                # Clean up future reference
                self._task_futures.pop(task_id, None)
    
    def get_task(self, task_id: UUID) -> Optional[BackgroundTask]:
        """Get task by ID.
        
        Parameters
        ----------
        task_id : UUID
            Task ID to retrieve
            
        Returns
        -------
        Optional[BackgroundTask]
            Task object if found, None otherwise
        """
        with self._task_lock:
            return self._tasks.get(task_id)
    
    def cancel_task(self, task_id: UUID, user_id: UUID) -> bool:
        """Cancel a background task.
        
        Parameters
        ----------
        task_id : UUID
            Task ID to cancel
        user_id : UUID
            User ID for authorization
            
        Returns
        -------
        bool
            True if task was cancelled successfully
            
        Raises
        ------
        ValueError
            If task not found or user not authorized
        """
        with self._task_lock:
            if task_id not in self._tasks:
                raise ValueError(f"Task {task_id} not found")
                
            task = self._tasks[task_id]
            
            # Validate user authorization
            if task.user_id != user_id:
                raise ValueError("User not authorized to cancel this task")
            
            # Can only cancel pending, queued, or running tasks
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return False
            
            # Cancel future if exists
            future = self._task_futures.get(task_id)
            if future and not future.done():
                cancelled = future.cancel()
                if not cancelled and task.status == TaskStatus.RUNNING:
                    # Try to terminate the process
                    process_id = self._running_processes.get(task_id)
                    if process_id:
                        try:
                            os.kill(process_id, signal.SIGTERM)
                        except (OSError, ProcessLookupError):
                            pass  # Process may have already ended
            
            # Update task status
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            task.message = "Task cancelled by user"
            
            # Clean up references
            self._task_futures.pop(task_id, None)
            self._running_processes.pop(task_id, None)
        
        # Update job status
        self.job_manager.update_job_status(
            job_id=task.job_id,
            status="cancelled",
            message="Background task cancelled by user"
        )
        
        return True
    
    def list_user_tasks(
        self,
        user_id: UUID,
        status: Optional[TaskStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[BackgroundTask]:
        """List tasks for a specific user.
        
        Parameters
        ----------
        user_id : UUID
            User ID to list tasks for
        status : Optional[TaskStatus]
            Optional status filter
        limit : int
            Maximum number of tasks to return
        offset : int
            Number of tasks to skip
            
        Returns
        -------
        List[BackgroundTask]
            List of user's tasks
        """
        with self._task_lock:
            user_tasks = [
                task for task in self._tasks.values()
                if task.user_id == user_id
            ]
            
            # Apply status filter
            if status:
                user_tasks = [task for task in user_tasks if task.status == status]
            
            # Sort by creation time (newest first)
            user_tasks.sort(key=lambda t: t.created_at, reverse=True)
            
            # Apply pagination
            return user_tasks[offset:offset + limit]
    
    def get_task_count(self, status: Optional[TaskStatus] = None) -> int:
        """Get count of tasks with optional status filter.
        
        Parameters
        ----------
        status : Optional[TaskStatus]
            Optional status filter
            
        Returns
        -------
        int
            Number of matching tasks
        """
        with self._task_lock:
            if status:
                return sum(1 for task in self._tasks.values() if task.status == status)
            return len(self._tasks)
    
    def _cleanup_worker(self) -> None:
        """Background worker for cleaning up completed tasks and processes."""
        while not self._shutdown_event.wait(self.cleanup_interval):
            try:
                self._cleanup_completed_tasks()
                self._cleanup_orphaned_processes()
            except Exception:
                pass  # Continue cleanup on errors
    
    def _cleanup_completed_tasks(self) -> None:
        """Clean up old completed tasks."""
        cutoff_time = datetime.utcnow() - timedelta(hours=24)  # Keep for 24 hours
        
        with self._task_lock:
            to_remove = []
            for task_id, task in self._tasks.items():
                if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] 
                    and task.completed_at and task.completed_at < cutoff_time):
                    to_remove.append(task_id)
            
            for task_id in to_remove:
                self._tasks.pop(task_id, None)
                self._task_futures.pop(task_id, None)
                self._running_processes.pop(task_id, None)
    
    def _cleanup_orphaned_processes(self) -> None:
        """Clean up orphaned process references."""
        with self._task_lock:
            to_remove = []
            for task_id, process_id in self._running_processes.items():
                try:
                    # Check if process still exists
                    psutil.Process(process_id)
                except psutil.NoSuchProcess:
                    # Process no longer exists
                    to_remove.append(task_id)
                    
                    # Update task status if task still exists
                    if task_id in self._tasks:
                        task = self._tasks[task_id]
                        if task.status == TaskStatus.RUNNING:
                            task.status = TaskStatus.FAILED
                            task.completed_at = datetime.utcnow()
                            task.error_message = "Process terminated unexpectedly"
            
            for task_id in to_remove:
                self._running_processes.pop(task_id, None)
    
    def _process_monitor_worker(self) -> None:
        """Background worker for monitoring process health and resource usage."""
        while not self._shutdown_event.wait(30.0):  # Check every 30 seconds
            try:
                self._monitor_process_resources()
            except Exception:
                pass  # Continue monitoring on errors
    
    def _monitor_process_resources(self) -> None:
        """Monitor process resource usage and enforce limits."""
        with self._task_lock:
            for task_id, process_id in list(self._running_processes.items()):
                try:
                    process = psutil.Process(process_id)
                    
                    # Check memory usage
                    memory_info = process.memory_info()
                    memory_gb = memory_info.rss / (1024 ** 3)
                    
                    if memory_gb > self.process_memory_limit_gb:
                        # Terminate process due to memory limit
                        process.terminate()
                        
                        # Update task status
                        if task_id in self._tasks:
                            task = self._tasks[task_id]
                            task.status = TaskStatus.FAILED
                            task.completed_at = datetime.utcnow()
                            task.error_message = f"Process terminated due to memory limit ({memory_gb:.1f}GB > {self.process_memory_limit_gb}GB)"
                        
                        self._running_processes.pop(task_id, None)
                        
                except psutil.NoSuchProcess:
                    # Process already terminated
                    self._running_processes.pop(task_id, None)
                except Exception:
                    continue
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status and metrics.
        
        Returns
        -------
        Dict[str, Any]
            System status information
        """
        with self._task_lock:
            status_counts = {}
            for status in TaskStatus:
                status_counts[status.value] = sum(
                    1 for task in self._tasks.values() if task.status == status
                )
            
            return {
                "max_workers": self.max_workers,
                "active_workers": len(self._running_processes),
                "task_counts": status_counts,
                "total_tasks": len(self._tasks),
                "process_memory_limit_gb": self.process_memory_limit_gb,
                "cleanup_interval": self.cleanup_interval,
                "task_timeout": self.task_timeout,
                "executor_active": self._executor is not None and not self._executor._shutdown
            }
    
    def shutdown(self, wait: bool = True, timeout: float = 30.0) -> None:
        """Shutdown the background task manager.
        
        Parameters
        ----------
        wait : bool
            Whether to wait for running tasks to complete
        timeout : float
            Maximum time to wait for shutdown
        """
        self._shutdown_event.set()
        
        if self._executor:
            self._executor.shutdown(wait=wait, timeout=timeout)
            self._executor = None
            
        # Wait for background threads to finish
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5.0)
            
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)


def _execute_pipeline_task(
    job_id: UUID,
    user_id: UUID,
    config: Dict[str, Any],
    base_directory: str,
    memory_limit_gb: float
) -> Dict[str, Any]:
    """Execute pipeline task in separate process.
    
    This function runs in a separate process and executes the EMUSES pipeline
    with user context isolation and resource monitoring.
    
    Parameters
    ----------
    job_id : UUID
        Job ID for execution
    user_id : UUID
        User ID for workspace isolation
    config : Dict[str, Any]
        Pipeline configuration
    base_directory : str
        Base directory for user storage
    memory_limit_gb : float
        Memory limit for this process
        
    Returns
    -------
    Dict[str, Any]
        Execution result
        
    Raises
    ------
    Exception
        If pipeline execution fails
    """
    import os
    import resource
    from pathlib import Path
    
    try:
        # Set up process-level resource limits
        if hasattr(resource, 'RLIMIT_AS'):
            # Set memory limit (in bytes)
            memory_limit_bytes = int(memory_limit_gb * 1024 ** 3)
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
        
        # Create job manager for this process
        job_manager = MultiUserJobManager(base_directory)
        
        # Validate job ownership in process
        if not job_manager.validate_job_ownership(job_id, user_id):
            raise ValueError("Job ownership validation failed in process")
        
        # Get job directory for execution
        user_storage = Path(base_directory) / "users" / str(user_id) / "jobs"
        job_dir = user_storage / str(job_id)
        
        if not job_dir.exists():
            raise ValueError(f"Job directory not found: {job_dir}")
        
        # Start resource tracking
        job_manager.start_job_tracking(job_id, user_id)
        
        # Update job status to running
        job_manager.update_job_status(
            job_id=job_id,
            status="running",
            message="Pipeline execution started in background process",
            progress=0.1
        )
        
        # Create pipeline executor with job directory context
        executor = PipelineExecutor(
            input_dir=job_dir / "input",
            output_dir=job_dir / "output"
        )
        
        start_time = datetime.utcnow()
        
        # Execute pipeline with progress tracking
        result = executor.execute(config)
        
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds() / 3600.0  # Convert to hours
        
        # Calculate storage usage
        storage_bytes = sum(
            f.stat().st_size for f in (job_dir / "output").rglob("*") if f.is_file()
        )
        
        # Complete resource tracking
        usage_summary = job_manager.complete_job_tracking(
            job_id, user_id, execution_time, storage_bytes
        )
        
        # Update final job status
        job_manager.update_job_status(
            job_id=job_id,
            status="completed",
            message="Pipeline execution completed successfully",
            progress=1.0
        )
        
        return {
            "success": True,
            "job_id": str(job_id),
            "user_id": str(user_id),
            "execution_time_hours": execution_time,
            "storage_bytes": storage_bytes,
            "result": result,
            "usage_summary": usage_summary,
            "completed_at": end_time.isoformat()
        }
        
    except Exception as e:
        # Update job status on failure
        try:
            job_manager.update_job_status(
                job_id=job_id,
                status="failed",
                message=f"Pipeline execution failed: {str(e)}"
            )
        except:
            pass  # Ignore status update errors during exception handling
            
        raise e