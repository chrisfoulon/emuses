"""
Stage Runners for EMUSES Pipeline

This module provides wrappers for individual pipeline stages that can be executed
independently with parameter validation, resource limits, and progress tracking.
"""

import asyncio
import copy
import logging
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import psutil

from emuses.foundation_fastapi_service.job_manager import JobManager
from emuses.pipelines.heatmap_stage import HeatmapStage
# from emuses.pipelines.prediction_stage import PredictionStage  # Retired - use HeatmapStage
from emuses.pipelines.umap_stage import UMAPStage


class ResourceMonitor:
    """Monitor resource usage for stage execution"""

    def __init__(
        self, memory_limit_ratio: float = 0.75, cpu_percent_limit: float = 90.0
    ):
        """Initialize resource monitor with system-proportional limits.

        Args:
            memory_limit_ratio: Fraction of total system memory to use (default: 75%)
            cpu_percent_limit: Maximum CPU usage percentage (default: 90%)
        """
        total_memory = psutil.virtual_memory().total
        self.memory_limit_bytes = int(total_memory * memory_limit_ratio)
        self.cpu_percent_limit = cpu_percent_limit
        self.monitoring = False
        self.exceeded_limits = False

    def start_monitoring(self):
        """Start monitoring resource usage"""
        self.monitoring = True
        self.exceeded_limits = False

    def stop_monitoring(self):
        """Stop monitoring resource usage"""
        self.monitoring = False

    def check_resources(self) -> bool:
        """Check if resource limits are exceeded"""
        if not self.monitoring:
            return True

        try:
            # Check memory usage
            memory_info = psutil.virtual_memory()
            if memory_info.used > self.memory_limit_bytes:
                self.exceeded_limits = True
                return False

            # Check CPU usage (average over 1 second)
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > self.cpu_percent_limit:
                self.exceeded_limits = True
                return False

            return True
        except Exception:
            # If we can't monitor, assume resources are OK
            return True


class ProgressTracker:
    """Rate-limited progress tracking for stage execution"""

    def __init__(
        self,
        job_manager: JobManager,
        job_id: str,
        stage_name: str,
        max_update_rate: float = 1.0,
    ):
        """Initialize progress tracker with rate limiting.

        Parameters
        ----------
        job_manager : JobManager
            The job manager instance for updating job progress
        job_id : str
            Unique identifier for the job being tracked
        stage_name : str
            Name of the pipeline stage being executed
        max_update_rate : float, optional
            Maximum updates per second to prevent flooding (default: 1.0)
        """
        self.job_manager = job_manager
        self.job_id = job_id
        self.stage_name = stage_name
        self.max_update_rate = max_update_rate  # Max updates per second
        self.last_update_time = 0.0
        self.lock = threading.Lock()

    def update_progress(self, progress: float, message: Optional[str] = None):
        """Update progress with rate limiting"""
        current_time = time.time()

        with self.lock:
            # Rate limiting check
            if current_time - self.last_update_time < (1.0 / self.max_update_rate):
                return

            self.last_update_time = current_time

        # Update job status
        self.job_manager.update_job_status(
            self.job_id,
            "running",
            progress=progress,
            current_stage=self.stage_name,
            message=message,
        )


class BaseStageRunner:
    """Base class for stage runners with common functionality"""

    def __init__(self, job_manager: JobManager):
        """Initialize base stage runner.

        Parameters
        ----------
        job_manager : JobManager
            The job manager instance for tracking job status and progress
        """
        self.job_manager = job_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    def _validate_context(self, context: Dict[str, Any], required_keys: list) -> None:
        """Validate that context contains required keys"""
        missing_keys = [key for key in required_keys if key not in context]
        if missing_keys:
            raise ValueError(f"Missing required context keys: {missing_keys}")

    def _validate_breaking_parameters(
        self, config: Any, breaking_checks: Dict[str, Callable]
    ) -> None:
        """Validate stage parameters against breaking conditions only.

        Args:
            config: Configuration object with parameters
            breaking_checks: Dict mapping parameter names to validation functions
                           that return True if value is valid, False if breaking
        """
        for param_name, check_func in breaking_checks.items():
            if hasattr(config, param_name):
                value = getattr(config, param_name)
                if not check_func(value):
                    raise ValueError(
                        f"Parameter {param_name}={value} would cause breaking behavior"
                    )

    async def _execute_with_monitoring(
        self,
        stage_instance,
        context: Dict[str, Any],
        progress_tracker: ProgressTracker,
        timeout_seconds: int = 1800,
        memory_limit_ratio: float = 0.75,
        cpu_percent_limit: float = 90.0,
    ) -> Dict[str, Any]:
        """Execute stage with resource monitoring and timeout"""
        resource_monitor = ResourceMonitor(memory_limit_ratio, cpu_percent_limit)
        resource_monitor.start_monitoring()

        try:
            # Create a copy of context to prevent corruption
            context_copy = copy.deepcopy(context)

            # Run stage in thread pool to enable timeout and monitoring
            loop = asyncio.get_event_loop()

            # Create a progress queue for the stage
            progress_queue = asyncio.Queue()

            # Start progress monitoring task
            progress_task = asyncio.create_task(
                self._monitor_progress(progress_queue, progress_tracker)
            )

            # Execute stage in thread pool
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = loop.run_in_executor(
                    executor, stage_instance.run, context_copy, progress_queue
                )

                # Wait for completion with timeout
                try:
                    result_context = await asyncio.wait_for(
                        future, timeout=timeout_seconds
                    )
                except asyncio.TimeoutError:
                    # Send sentinel to stop monitoring gracefully
                    await progress_queue.put(None)
                    progress_task.cancel()
                    # Await the cancelled task to ensure cleanup
                    try:
                        await progress_task
                    except asyncio.CancelledError:
                        pass  # Expected when task is cancelled
                    raise TimeoutError(
                        f"Stage execution exceeded {timeout_seconds} seconds"
                    )

            return result_context

        finally:
            # Clean up progress monitoring gracefully
            try:
                await progress_queue.put(None)  # Send sentinel to stop monitoring

                # Wait for progress task to complete naturally or cancel if needed
                try:
                    await asyncio.wait_for(progress_task, timeout=1.0)
                except asyncio.TimeoutError:
                    # Progress task didn't finish naturally, cancel it
                    progress_task.cancel()
                    try:
                        await progress_task
                    except asyncio.CancelledError:
                        pass  # Expected when task is cancelled
            except Exception:
                # If cleanup fails, still cancel the task
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass  # Expected when task is cancelled

            resource_monitor.stop_monitoring()
            if resource_monitor.exceeded_limits:
                raise RuntimeError("Resource limits exceeded during stage execution")

    async def _monitor_progress(
        self, progress_queue: asyncio.Queue, progress_tracker: ProgressTracker
    ):
        """Monitor progress updates from stage execution"""
        try:
            while True:
                try:
                    # Wait for progress update with timeout
                    progress_data = await asyncio.wait_for(
                        progress_queue.get(), timeout=1.0
                    )
                    if progress_data is None:  # Sentinel to stop monitoring
                        break

                    progress, message = progress_data
                    progress_tracker.update_progress(progress, message)

                except asyncio.TimeoutError:
                    # No progress update, continue monitoring
                    continue

        except asyncio.CancelledError:
            # Progress monitoring was cancelled, exit gracefully
            pass

    def _is_safe_path(self, path: Path) -> bool:
        """Validate path to prevent directory traversal"""
        try:
            # Convert to string and check for obvious traversal attempts
            path_str = str(path)
            if ".." in path_str:
                return False

            # Resolve the path and check it doesn't escape expected boundaries
            resolved = path.resolve()
            # Check if resolved path contains parent directory traversals
            resolved_str = str(resolved)
            if ".." in resolved_str:
                return False

            # Additional check: path should not resolve to critical system directories
            # Allow temporary directories and user directories
            system_dirs = ["/etc", "/usr", "/bin", "/sbin", "/root"]
            if any(resolved_str.startswith(sys_dir) for sys_dir in system_dirs):
                return False

            return True
        except (OSError, ValueError):
            return False


class UMAPStageRunner(BaseStageRunner):
    """Runner for UMAP dimensionality reduction and clustering stage"""

    def __init__(self, job_manager: JobManager):
        """Initialize UMAP stage runner.

        Parameters
        ----------
        job_manager : JobManager
            The job manager instance for tracking job status and progress
        """
        super().__init__(job_manager)

    async def run_stage(self, job_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute UMAP stage with validation and monitoring"""
        self.logger.info(f"Starting UMAP stage for job {job_id}")

        # Validate required context keys
        required_keys = ["embedding_train_features", "config"]
        self._validate_context(context, required_keys)

        config = context["config"]

        # Validate only breaking parameters (not arbitrary ranges)
        breaking_checks = {
            "n_components": lambda x: isinstance(x, int)
            and x > 0,  # Must be positive integer
            "n_neighbors": lambda x: isinstance(x, int)
            and x > 0,  # Must be positive integer
            "min_dist": lambda x: isinstance(x, (int, float))
            and x >= 0,  # Must be non-negative
            "min_cluster_size": lambda x: isinstance(x, int)
            and x > 1,  # Must be > 1 for clustering
        }
        self._validate_breaking_parameters(config, breaking_checks)

        # Create progress tracker
        progress_tracker = ProgressTracker(self.job_manager, job_id, "umap_stage")

        # Update initial status
        progress_tracker.update_progress(0.0, "Initializing UMAP stage")

        try:
            # Create UMAP stage instance
            umap_stage = UMAPStage(config)

            # Execute with monitoring (30 minute timeout for UMAP)
            result_context = await self._execute_with_monitoring(
                umap_stage, context, progress_tracker, timeout_seconds=1800
            )

            # Update completion status
            progress_tracker.update_progress(1.0, "UMAP stage completed successfully")

            # Organize artifacts
            await self._organize_umap_artifacts(job_id, result_context)

            return result_context

        except Exception as e:
            self.logger.error(f"UMAP stage failed for job {job_id}: {str(e)}")
            self.job_manager.update_job_status(
                job_id,
                "failed",
                current_stage="umap_stage",
                message=f"UMAP stage error: {str(e)}",
            )
            raise

    async def _organize_umap_artifacts(self, job_id: str, context: Dict[str, Any]):
        """Organize UMAP artifacts with secure file handling"""
        job_dir = self.job_manager.get_job_directory(job_id)
        umap_output_dir = job_dir / "output" / "umap"
        umap_output_dir.mkdir(parents=True, exist_ok=True)

        # Expected UMAP artifacts
        artifacts = [
            "best_umap_model.joblib",
            "embeddings.npy",
            "hdbscan_model.joblib",
            "cluster_labels.npy",
        ]

        config = context.get("config")
        if config and hasattr(config, "output_folder"):
            source_dir = Path(config.output_folder)

            # Copy artifacts to job output directory
            for artifact in artifacts:
                source_file = source_dir / artifact
                if source_file.exists():
                    dest_file = umap_output_dir / artifact
                    # Secure copy with path validation
                    if self._is_safe_path(source_file) and self._is_safe_path(
                        dest_file
                    ):
                        dest_file.write_bytes(source_file.read_bytes())


class HeatmapStageRunner(BaseStageRunner):
    """Runner for heatmap multi-target prediction stage"""

    def __init__(self, job_manager: JobManager):
        """Initialize heatmap stage runner.

        Parameters
        ----------
        job_manager : JobManager
            The job manager instance for tracking job status and progress
        """
        super().__init__(job_manager)

    async def run_stage(self, job_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute heatmap stage with optimization progress tracking"""
        self.logger.info(f"Starting heatmap stage for job {job_id}")

        # Validate required context keys
        required_keys = ["embeddings", "scores", "config"]
        self._validate_context(context, required_keys)

        config = context["config"]

        # Validate only breaking parameters (not arbitrary ranges)
        breaking_checks = {
            "cv_folds": lambda x: isinstance(x, int)
            and x >= 2,  # Must be at least 2 for CV
            "test_size": lambda x: isinstance(x, (int, float))
            and 0 < x < 1,  # Must be valid proportion
            "max_iter": lambda x: isinstance(x, int)
            and x > 0,  # Must be positive integer
        }
        self._validate_breaking_parameters(config, breaking_checks)

        # Create progress tracker
        progress_tracker = ProgressTracker(self.job_manager, job_id, "heatmap_stage")

        # Update initial status
        progress_tracker.update_progress(0.0, "Initializing heatmap stage")

        try:
            # Create heatmap stage instance
            heatmap_stage = HeatmapStage(config)

            # Execute with monitoring (30 minute timeout for heatmap)
            result_context = await self._execute_with_monitoring(
                heatmap_stage, context, progress_tracker, timeout_seconds=1800
            )

            # Update completion status
            progress_tracker.update_progress(
                1.0, "Heatmap stage completed successfully"
            )

            # Organize artifacts
            await self._organize_heatmap_artifacts(job_id, result_context)

            return result_context

        except Exception as e:
            self.logger.error(f"Heatmap stage failed for job {job_id}: {str(e)}")
            self.job_manager.update_job_status(
                job_id,
                "failed",
                current_stage="heatmap_stage",
                message=f"Heatmap stage error: {str(e)}",
            )
            raise

    async def _organize_heatmap_artifacts(self, job_id: str, context: Dict[str, Any]):
        """Organize heatmap artifacts with secure file handling"""
        job_dir = self.job_manager.get_job_directory(job_id)
        heatmap_output_dir = job_dir / "output" / "heatmap"
        heatmap_output_dir.mkdir(parents=True, exist_ok=True)

        config = context.get("config")
        if config and hasattr(config, "output_folder"):
            source_dir = Path(config.output_folder)

            # Copy model files and performance reports
            for item in source_dir.rglob("*"):
                if item.is_file() and (
                    item.suffix in [".pkl", ".csv", ".json"]
                    or "model" in item.name.lower()
                    or "performance" in item.name.lower()
                ):
                    if self._is_safe_path(item):
                        # Maintain directory structure
                        rel_path = item.relative_to(source_dir)
                        dest_file = heatmap_output_dir / rel_path
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        dest_file.write_bytes(item.read_bytes())
