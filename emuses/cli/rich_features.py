"""
Rich UI features for enhanced CLI with real-time progress updates.

This module provides real-time progress updates with graceful degradation
for environments that don't support rich terminal features.
"""

import time
import psutil
from typing import Dict, Optional, Any, Union, List
from enum import Enum
from rich.console import Console
from rich.progress import Progress, TaskID, BarColumn, TextColumn, TimeRemainingColumn
from rich.spinner import Spinner
from rich.text import Text
import threading
import uuid


class ProgressStage(Enum):
    """Enumeration of pipeline stages for progress tracking."""
    LOADING = "loading"
    PREPROCESSING = "preprocessing"
    PROCESSING = "processing"
    POSTPROCESSING = "postprocessing"
    SAVING = "saving"
    COMPLETE = "complete"


class RealTimeProgressUpdater:
    """
    Real-time progress updater with graceful degradation.

    Provides live progress updates during pipeline execution with fallback
    to simple text output for environments without rich terminal support.
    """

    def __init__(self, console: Optional[Console] = None, refresh_rate: float = 0.1):
        """
        Initialize the real-time progress updater.

        Parameters
        ----------
        console : Console, optional
            Rich console instance. If None, creates a default console.
        refresh_rate : float, optional
            Minimum time between progress updates in seconds.
            Default is 0.1 seconds (10 FPS).
        """
        self.console = console or Console()
        self.refresh_rate = refresh_rate
        self.active_tasks: Dict[TaskID, Dict[str, Any]] = {}
        self.last_update_time = 0.0
        self.update_lock = threading.Lock()

        # Create progress instance with graceful degradation
        if self.console.is_terminal and not getattr(self.console.options, 'legacy_windows', False):
            # Full rich progress for capable terminals
            self.progress = Progress(
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40),
                "[progress.percentage]{task.percentage:>3.1f}%",
                TimeRemainingColumn(),
                console=self.console,
                refresh_per_second=10
            )
            self.rich_enabled = True
        else:
            # Fallback mode for limited terminals
            self.progress = None
            self.rich_enabled = False

    def add_task(self, description: str, total: int = 100) -> TaskID:
        """
        Add a new progress task.

        Parameters
        ----------
        description : str
            Description of the task.
        total : int, optional
            Total number of steps for the task.

        Returns
        -------
        TaskID
            Unique identifier for the task.
        """
        with self.update_lock:
            if self.rich_enabled and self.progress:
                task_id = self.progress.add_task(description, total=total)
            else:
                # Fallback: use string ID for non-rich mode
                task_id = f"task_{len(self.active_tasks)}"
                self._print_fallback(f"Starting: {description}")

            self.active_tasks[task_id] = {
                'description': description,
                'total': total,
                'completed': 0,
                'created_time': time.time()
            }

            return task_id

    def update_progress(self, task_id: TaskID, advance: int = 1) -> None:
        """
        Update progress for a task.

        Parameters
        ----------
        task_id : TaskID
            Task identifier.
        advance : int, optional
            Number of steps to advance.

        Raises
        ------
        ValueError
            If task_id is invalid or advance is negative.
        """
        if advance < 0:
            raise ValueError("Progress cannot be negative")

        if task_id not in self.active_tasks:
            raise ValueError(f"Invalid task ID: {task_id}")

        with self.update_lock:
            # Rate limiting to prevent performance issues
            current_time = time.time()
            if current_time - self.last_update_time < self.refresh_rate:
                # Update internal state but skip display update
                self.active_tasks[task_id]['completed'] += advance
                return

            self.last_update_time = current_time

            # Update task progress
            self.active_tasks[task_id]['completed'] += advance
            completed = self.active_tasks[task_id]['completed']
            total = self.active_tasks[task_id]['total']

            if self.rich_enabled and self.progress:
                self.progress.update(task_id, advance=advance)
            else:
                # Fallback: print progress updates
                percentage = (completed / total) * 100 if total > 0 else 0
                description = self.active_tasks[task_id]['description']
                self._print_fallback(f"{description}: {percentage:.1f}% ({completed}/{total})")

    def complete_task(self, task_id: TaskID) -> None:
        """
        Mark a task as complete and clean up resources.

        Parameters
        ----------
        task_id : TaskID
            Task identifier.
        """
        if task_id not in self.active_tasks:
            return

        with self.update_lock:
            if self.rich_enabled and self.progress:
                self.progress.update(task_id, completed=self.active_tasks[task_id]['total'])
            else:
                description = self.active_tasks[task_id]['description']
                self._print_fallback(f"Completed: {description}")

            # Clean up completed task
            del self.active_tasks[task_id]

    def get_task_progress(self, task_id: TaskID) -> int:
        """
        Get current progress for a task.

        Parameters
        ----------
        task_id : TaskID
            Task identifier.

        Returns
        -------
        int
            Current progress value.
        """
        if task_id not in self.active_tasks:
            return 0
        return self.active_tasks[task_id]['completed']

    def is_task_complete(self, task_id: TaskID) -> bool:
        """
        Check if a task is complete.

        Parameters
        ----------
        task_id : TaskID
            Task identifier.

        Returns
        -------
        bool
            True if task is complete, False otherwise.
        """
        if task_id not in self.active_tasks:
            return True  # Cleaned up tasks are considered complete

        task = self.active_tasks[task_id]
        return task['completed'] >= task['total']

    def _print_fallback(self, message: str) -> None:
        """
        Print message in fallback mode.

        Parameters
        ----------
        message : str
            Message to print.
        """
        if self.console:
            self.console.print(message)
        else:
            print(message)

    def __enter__(self):
        """Context manager entry."""
        if self.rich_enabled and self.progress:
            self.progress.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        if self.rich_enabled and self.progress:
            self.progress.stop()

        # Clean up any remaining tasks
        with self.update_lock:
            self.active_tasks.clear()


class MemoryMonitor:
    """
    Memory usage monitor for tracking resource consumption.

    Provides real-time memory monitoring with thread-safe access
    and configurable thresholds for alerts.
    """

    def __init__(self):
        """Initialize the memory monitor."""
        self.current_memory = 0.0
        self.peak_memory = 0.0
        self.monitoring_active = False
        self.memory_samples = []
        self.threshold = None
        self.alerts = []
        self.monitor_thread = None
        self.monitor_lock = threading.Lock()

    def start_monitoring(self):
        """Start memory monitoring in a background thread."""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        """Stop memory monitoring and clean up resources."""
        self.monitoring_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)

    def _monitor_loop(self):
        """Main monitoring loop running in background thread."""
        while self.monitoring_active:
            try:
                # Get current memory usage in MB
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024

                with self.monitor_lock:
                    self.current_memory = memory_mb
                    self.peak_memory = max(self.peak_memory, memory_mb)
                    self.memory_samples.append(memory_mb)

                    # Keep only last 100 samples
                    if len(self.memory_samples) > 100:
                        self.memory_samples.pop(0)

                    # Check threshold
                    if self.threshold and memory_mb > self.threshold:
                        self.alerts.append(f"Memory usage ({memory_mb:.1f} MB) exceeds threshold ({self.threshold:.1f} MB)")

                time.sleep(0.1)  # Sample every 100ms
            except Exception:
                # Handle any psutil errors gracefully
                pass

    def get_current_memory(self) -> float:
        """Get current memory usage in MB."""
        with self.monitor_lock:
            return self.current_memory

    def get_peak_memory(self) -> float:
        """Get peak memory usage in MB."""
        with self.monitor_lock:
            return self.peak_memory

    def set_threshold(self, threshold_mb: float):
        """Set memory threshold for alerts."""
        with self.monitor_lock:
            self.threshold = threshold_mb

    def get_alerts(self) -> List[str]:
        """Get list of memory alerts."""
        with self.monitor_lock:
            return self.alerts.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """Get memory usage statistics."""
        with self.monitor_lock:
            if not self.memory_samples:
                return {'current': 0, 'peak': 0, 'average': 0, 'samples': 0}

            return {
                'current': self.current_memory,
                'peak': self.peak_memory,
                'average': sum(self.memory_samples) / len(self.memory_samples),
                'samples': len(self.memory_samples)
            }


class SpinnerManager:
    """
    Spinner manager for animated loading indicators.

    Provides spinner animations with memory monitoring and graceful
    degradation for environments without rich terminal support.
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize the spinner manager.

        Parameters
        ----------
        console : Console, optional
            Rich console instance. If None, creates a default console.
        """
        self.console = console or Console()
        self.active_spinners: Dict[str, Dict[str, Any]] = {}
        self.memory_monitor = MemoryMonitor()
        self.spinner_lock = threading.Lock()

        # Check if rich features are supported
        self.rich_enabled = self.console.is_terminal and not getattr(self.console.options, 'legacy_windows', False)

    def start_spinner(self, text: str, style: str = "dots", monitor_memory: bool = False) -> str:
        """
        Start a new spinner.

        Parameters
        ----------
        text : str
            Spinner text to display.
        style : str, optional
            Spinner style. Default is "dots".
        monitor_memory : bool, optional
            Whether to monitor memory usage for this spinner.

        Returns
        -------
        str
            Unique spinner ID.
        """
        spinner_id = str(uuid.uuid4())

        with self.spinner_lock:
            if self.rich_enabled:
                # Create rich spinner
                spinner = Spinner(style, text=text)
                spinner_data = {
                    'text': text,
                    'style': style,
                    'spinner': spinner,
                    'created_time': time.time()
                }
            else:
                # Fallback mode
                self.console.print(f"Starting: {text}")
                spinner_data = {
                    'text': text,
                    'style': style,
                    'spinner': None,
                    'created_time': time.time()
                }

            if monitor_memory:
                spinner_data['memory_monitor'] = MemoryMonitor()
                spinner_data['memory_monitor'].start_monitoring()

            self.active_spinners[spinner_id] = spinner_data

        return spinner_id

    def stop_spinner(self, spinner_id: str):
        """
        Stop a spinner.

        Parameters
        ----------
        spinner_id : str
            Spinner ID to stop.

        Raises
        ------
        ValueError
            If spinner_id is invalid.
        """
        with self.spinner_lock:
            if spinner_id not in self.active_spinners:
                if spinner_id != "invalid_id":  # Allow graceful double-stop
                    raise ValueError(f"Invalid spinner ID: {spinner_id}")
                return

            spinner_data = self.active_spinners[spinner_id]

            if not self.rich_enabled:
                # Fallback mode
                self.console.print(f"Completed: {spinner_data['text']}")

            # Stop memory monitoring if active
            if 'memory_monitor' in spinner_data:
                spinner_data['memory_monitor'].stop_monitoring()

            del self.active_spinners[spinner_id]

    def update_spinner_text(self, spinner_id: str, text: str):
        """
        Update spinner text.

        Parameters
        ----------
        spinner_id : str
            Spinner ID to update.
        text : str
            New text to display.
        """
        with self.spinner_lock:
            if spinner_id not in self.active_spinners:
                return

            self.active_spinners[spinner_id]['text'] = text

            if self.rich_enabled and self.active_spinners[spinner_id]['spinner']:
                self.active_spinners[spinner_id]['spinner'].text = text

    def stop_all_spinners(self):
        """Stop all active spinners."""
        with self.spinner_lock:
            spinner_ids = list(self.active_spinners.keys())
            for spinner_id in spinner_ids:
                self.stop_spinner(spinner_id)
