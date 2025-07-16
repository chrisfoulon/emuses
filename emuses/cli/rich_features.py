"""
Rich UI features for enhanced CLI experience.

This module provides Rich-based progress bars, status indicators, and formatting
for improved user experience with stage-specific tracking and graceful degradation.

Key Features:
- Stage-specific progress tracking
- Colored output with rate limiting
- Table formatting for results
- Real-time updates with fallback support
- Memory-efficient animations
"""

from typing import List, Optional, Union, Dict
import time
import sys
import os
from dataclasses import dataclass, field


@dataclass
class StageInfo:
    """Information about a pipeline stage."""

    name: str
    progress: float = 0.0
    completed: bool = False
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class ProgressTracker:
    """
    Stage-specific progress tracker for CLI operations.

    Tracks progress across multiple stages of a pipeline with individual
    stage progress and overall completion tracking.

    Attributes
    ----------
    stages : List[StageInfo]
        List of pipeline stages with their progress information
    current_stage_index : int
        Index of the currently active stage
    """

    def __init__(self):
        """
        Initialize the progress tracker.

        Returns
        -------
        None
        """
        self.stages: List[StageInfo] = []
        self.current_stage_index: int = 0
        self._start_time: Optional[float] = None

    def set_stages(self, stage_names: List[str]) -> None:
        """
        Set the stages for progress tracking.

        Parameters
        ----------
        stage_names : List[str]
            List of stage names to track

        Returns
        -------
        None
        """
        self.stages = [StageInfo(name=name) for name in stage_names]
        self.current_stage_index = 0
        self._start_time = time.time()

        # Mark the first stage as started
        if self.stages:
            self.stages[0].start_time = self._start_time

    @property
    def current_stage(self) -> str:
        """
        Get the name of the current stage.

        Returns
        -------
        str
            Name of the current stage, or empty string if no stages
        """
        if 0 <= self.current_stage_index < len(self.stages):
            return self.stages[self.current_stage_index].name
        return ""

    def next_stage(self) -> bool:
        """
        Advance to the next stage.

        Returns
        -------
        bool
            True if advanced to next stage, False if already at last stage
        """
        if self.current_stage_index < len(self.stages) - 1:
            self.current_stage_index += 1
            # Mark new stage as started
            if self.current_stage_index < len(self.stages):
                self.stages[self.current_stage_index].start_time = time.time()
            return True
        return False

    def set_stage_index(self, index: int) -> None:
        """
        Set the current stage index.

        Parameters
        ----------
        index : int
            Stage index to set as current

        Returns
        -------
        None
        """
        if 0 <= index < len(self.stages):
            self.current_stage_index = index
            # Mark stage as started if not already
            if not self.stages[index].start_time:
                self.stages[index].start_time = time.time()

    def update_stage_progress(self, progress: float) -> None:
        """
        Update the progress of the current stage.

        Parameters
        ----------
        progress : float
            Progress value between 0.0 and 1.0

        Returns
        -------
        None
        """
        if 0 <= self.current_stage_index < len(self.stages):
            # Clamp progress between 0 and 1
            progress = max(0.0, min(1.0, progress))
            self.stages[self.current_stage_index].progress = progress

    def complete_current_stage(self) -> None:
        """
        Mark the current stage as completed and advance to next.

        Returns
        -------
        None
        """
        if 0 <= self.current_stage_index < len(self.stages):
            current_stage = self.stages[self.current_stage_index]
            current_stage.progress = 1.0
            current_stage.completed = True
            current_stage.end_time = time.time()

            # Advance to next stage if not at the last stage
            if self.current_stage_index < len(self.stages) - 1:
                self.next_stage()

    def get_overall_progress(self) -> float:
        """
        Calculate overall progress across all stages.

        Returns
        -------
        float
            Overall progress value between 0.0 and 1.0
        """
        if not self.stages:
            return 0.0

        total_progress = 0.0
        for i, stage in enumerate(self.stages):
            if i < self.current_stage_index:
                # Completed stages count as 1.0
                total_progress += 1.0
            elif i == self.current_stage_index:
                # Current stage contributes its progress
                total_progress += stage.progress
            # Future stages contribute 0.0

        return total_progress / len(self.stages)

    def is_complete(self) -> bool:
        """
        Check if all stages are completed.

        Returns
        -------
        bool
            True if all stages are completed
        """
        if not self.stages:
            return False

        return all(stage.completed for stage in self.stages)

    def get_stage_info(self, stage_index: int) -> Optional[StageInfo]:
        """
        Get information about a specific stage.

        Parameters
        ----------
        stage_index : int
            Index of the stage to get information for

        Returns
        -------
        Optional[StageInfo]
            Stage information or None if index is invalid
        """
        if 0 <= stage_index < len(self.stages):
            return self.stages[stage_index]
        return None

    def get_elapsed_time(self) -> float:
        """
        Get total elapsed time since tracking started.

        Returns
        -------
        float
            Elapsed time in seconds, or 0.0 if not started
        """
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time


class StatusRenderer:
    """
    Colored output and status indicator renderer with rate limiting.

    Provides colored status messages with appropriate symbols and implements
    rate limiting to prevent performance issues during rapid status updates.

    Attributes
    ----------
    rate_limit_ms : int
        Minimum time between renders in milliseconds
    supports_color : bool
        Whether the current terminal supports color output
    """

    def __init__(self, rate_limit_ms: int = 50, force_no_color: bool = False):
        """
        Initialize the status renderer.

        Parameters
        ----------
        rate_limit_ms : int, optional
            Minimum time between renders in milliseconds, by default 50
        force_no_color : bool, optional
            Force disable color output for testing, by default False

        Returns
        -------
        None
        """
        self.rate_limit_ms = rate_limit_ms
        self._last_render_time = 0.0
        self._force_no_color = force_no_color

        # Detect color support
        self.supports_color = self._detect_color_support() and not force_no_color

        # Status symbols and colors
        self._status_config = {
            "success": {"symbol": "✓", "fallback": "SUCCESS", "color": "\033[92m"},
            "error": {"symbol": "✗", "fallback": "ERROR", "color": "\033[91m"},
            "warning": {"symbol": "⚠", "fallback": "WARNING", "color": "\033[93m"},
            "info": {"symbol": "ℹ", "fallback": "INFO", "color": "\033[94m"}
        }
        self._reset_color = "\033[0m"

    def _detect_color_support(self) -> bool:
        """
        Detect if the current terminal supports color output.

        Returns
        -------
        bool
            True if color is supported, False otherwise
        """
        # Check common environment variables
        if os.getenv("NO_COLOR") or os.getenv("TERM") == "dumb":
            return False

        # Check if stdout is a TTY
        if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
            return False

        # Check TERM environment variable for color capability
        term = os.getenv("TERM", "")
        return "color" in term or "xterm" in term or "screen" in term

    def _should_render(self) -> bool:
        """
        Check if enough time has passed since last render (rate limiting).

        Returns
        -------
        bool
            True if rendering is allowed, False if rate limited
        """
        current_time = time.time()
        time_since_last = (current_time - self._last_render_time) * 1000  # Convert to ms

        if time_since_last >= self.rate_limit_ms:
            self._last_render_time = current_time
            return True
        return False

    def render_status(self, level: str, message: str, force_render: bool = False) -> str:
        """
        Render a status message with appropriate color and symbol.

        Parameters
        ----------
        level : str
            Status level (success, error, warning, info)
        message : str
            Status message to display
        force_render : bool, optional
            Force rendering even if rate limited, by default False

        Returns
        -------
        str
            Formatted status string with color and symbol

        Raises
        ------
        ValueError
            If level is not a supported status level
        """
        if level not in self._status_config:
            raise ValueError(f"Unsupported status level: {level}")

        # Apply rate limiting (except for errors which should always show or force_render)
        if not force_render and level != "error" and not self._should_render():
            return ""  # Rate limited - return empty string

        config = self._status_config[level]

        if self.supports_color:
            # Use colored output with symbols
            formatted = f"{config['color']}{config['symbol']}{self._reset_color} {message}"
        else:
            # Use fallback text-only format
            formatted = f"[{config['fallback']}] {message}"

        return formatted

    def get_status_levels(self) -> List[str]:
        """
        Get list of supported status levels.

        Returns
        -------
        List[str]
            List of supported status level names
        """
        return list(self._status_config.keys())


class TableFormatter:
    """
    Table formatting for results summary and data display.

    Provides flexible table formatting with alignment options, titles,
    and compact mode for different terminal sizes and capabilities.

    Attributes
    ----------
    force_simple : bool
        Whether to force simple text-only table format
    """

    def __init__(self, force_simple: bool = False):
        """
        Initialize the table formatter.

        Parameters
        ----------
        force_simple : bool, optional
            Force simple text-only table format, by default False

        Returns
        -------
        None
        """
        self.force_simple = force_simple
        self._default_alignment = "left"

    def create_table(
        self,
        headers: List[str],
        rows: List[List[str]],
        title: Optional[str] = None,
        alignments: Optional[List[str]] = None,
        compact_mode: bool = False
    ) -> str:
        """
        Create a formatted table from headers and rows.

        Parameters
        ----------
        headers : List[str]
            Column headers for the table
        rows : List[List[str]]
            Table rows, each row is a list of cell values
        title : Optional[str], optional
            Table title to display above the table, by default None
        alignments : Optional[List[str]], optional
            Column alignments ("left", "center", "right"), by default None
        compact_mode : bool, optional
            Use compact formatting for narrow terminals, by default False

        Returns
        -------
        str
            Formatted table as a string

        Raises
        ------
        ValueError
            If headers and row columns don't match
        """
        if not headers or not rows:
            return ""

        # Validate column count consistency
        expected_cols = len(headers)
        for i, row in enumerate(rows):
            if len(row) != expected_cols:
                raise ValueError(f"Row {i} has {len(row)} columns, expected {expected_cols}")

        # Set default alignments if not provided
        if alignments is None:
            alignments = [self._default_alignment] * len(headers)
        elif len(alignments) != len(headers):
            # Extend or truncate alignments to match headers
            alignments = (alignments + [self._default_alignment] * len(headers))[:len(headers)]

        if self.force_simple or compact_mode:
            return self._create_simple_table(headers, rows, title)
        else:
            return self._create_formatted_table(headers, rows, title, alignments)

    def _create_simple_table(
        self,
        headers: List[str],
        rows: List[List[str]],
        title: Optional[str] = None
    ) -> str:
        """
        Create a simple text-only table.

        Parameters
        ----------
        headers : List[str]
            Column headers
        rows : List[List[str]]
            Table rows
        title : Optional[str], optional
            Table title, by default None

        Returns
        -------
        str
            Simple formatted table
        """
        lines = []

        # Add title if provided
        if title:
            lines.append(title)
            lines.append("=" * len(title))

        # Calculate column widths
        col_widths = [len(header) for header in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

        # Create header row
        header_row = " | ".join(header.ljust(col_widths[i]) for i, header in enumerate(headers))
        lines.append(header_row)

        # Create separator
        separator = "-+-".join("-" * width for width in col_widths)
        lines.append(separator)

        # Create data rows
        for row in rows:
            data_row = " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
            lines.append(data_row)

        return "\n".join(lines)

    def _create_formatted_table(
        self,
        headers: List[str],
        rows: List[List[str]],
        title: Optional[str] = None,
        alignments: Optional[List[str]] = None
    ) -> str:
        """
        Create a formatted table with alignment support.

        Parameters
        ----------
        headers : List[str]
            Column headers
        rows : List[List[str]]
            Table rows
        title : Optional[str], optional
            Table title, by default None
        alignments : Optional[List[str]], optional
            Column alignments, by default None

        Returns
        -------
        str
            Formatted table with alignment
        """
        lines = []

        # Add title if provided
        if title:
            lines.append(title)
            lines.append("=" * len(title))

        # Calculate column widths
        col_widths = self._calculate_column_widths(headers, rows)

        # Create table structure
        lines.extend(self._create_table_header(headers, col_widths, alignments))
        lines.extend(self._create_table_rows(rows, col_widths, alignments))
        lines.append(self._create_table_footer(col_widths))

        return "\n".join(lines)

    def _calculate_column_widths(self, headers: List[str], rows: List[List[str]]) -> List[int]:
        """Calculate optimal column widths for table."""
        col_widths = [len(header) for header in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        return col_widths

    def _align_cell(self, text: str, width: int, alignment: str) -> str:
        """Align text within specified width."""
        if alignment == "center":
            return text.center(width)
        elif alignment == "right":
            return text.rjust(width)
        else:  # left or default
            return text.ljust(width)

    def _create_table_header(self, headers: List[str], col_widths: List[int], alignments: Optional[List[str]]) -> List[str]:
        """Create formatted table header."""
        header_cells = []
        for i, header in enumerate(headers):
            align = alignments[i] if alignments else "left"
            cell = self._align_cell(header, col_widths[i], align)
            header_cells.append(cell)

        header_row = " │ ".join(header_cells)
        return [
            "┌" + "─┬─".join("─" * width for width in col_widths) + "┐",
            "│ " + header_row + " │",
            "├" + "─┼─".join("─" * width for width in col_widths) + "┤"
        ]

    def _create_table_rows(self, rows: List[List[str]], col_widths: List[int], alignments: Optional[List[str]]) -> List[str]:
        """Create formatted table data rows."""
        data_lines = []
        for row in rows:
            data_cells = []
            for i, cell in enumerate(row):
                align = alignments[i] if alignments else "left"
                formatted_cell = self._align_cell(str(cell), col_widths[i], align)
                data_cells.append(formatted_cell)

            data_row = " │ ".join(data_cells)
            data_lines.append("│ " + data_row + " │")
        return data_lines

    def _create_table_footer(self, col_widths: List[int]) -> str:
        """Create table footer border."""
        return "└" + "─┴─".join("─" * width for width in col_widths) + "┘"

    def get_optimal_width(self, headers: List[str], rows: List[List[str]]) -> int:
        """
        Calculate the optimal width for the table.

        Parameters
        ----------
        headers : List[str]
            Column headers
        rows : List[List[str]]
            Table rows

        Returns
        -------
        int
            Optimal table width in characters
        """
        if not headers or not rows:
            return 0

        # Calculate column widths
        col_widths = [len(header) for header in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))

        # Calculate total width including separators
        if self.force_simple:
            # Simple format: " | " between columns
            total_width = sum(col_widths) + (len(col_widths) - 1) * 3
        else:
            # Formatted table: " │ " between columns plus borders
            total_width = sum(col_widths) + (len(col_widths) - 1) * 3 + 4  # borders

        return total_width


class RealTimeProgressUpdater:
    """
    Real-time progress updater with graceful degradation for different terminal environments.

    Provides real-time progress updates using ANSI escape sequences with automatic
    fallback for environments that don't support real-time updates (CI, redirected output).
    Includes performance optimizations to prevent terminal flooding.

    Attributes
    ----------
    supports_real_time : bool
        Whether the current environment supports real-time updates
    rate_limit_ms : int
        Minimum time between updates in milliseconds
    buffer_size : int
        Size of the update buffer for performance optimization
    terminal_width : int
        Current terminal width in characters
    terminal_height : int
        Current terminal height in characters
    """

    def __init__(self, rate_limit_ms: int = 50, force_fallback: bool = False):
        """
        Initialize the real-time progress updater.

        Parameters
        ----------
        rate_limit_ms : int, optional
            Minimum time between updates in milliseconds, by default 50
        force_fallback : bool, optional
            Force fallback mode for testing/compatibility, by default False

        Returns
        -------
        None
        """
        self.rate_limit_ms = rate_limit_ms
        self._last_update_time = 0.0
        self._force_fallback = force_fallback
        self.buffer_size = 1024  # Buffer size for performance optimization

        # Detect real-time update capability
        self.supports_real_time = self._detect_real_time_support() and not force_fallback

        # Terminal dimensions
        self.terminal_width, self.terminal_height = self._get_terminal_size()

        # ANSI escape sequences for real-time updates
        self._ansi_codes = {
            "clear_line": "\033[2K",
            "cursor_up": "\033[1A",
            "cursor_to_start": "\r",
            "save_cursor": "\033[s",
            "restore_cursor": "\033[u"
        }

    def _detect_real_time_support(self) -> bool:
        """
        Detect if the current environment supports real-time terminal updates.

        Returns
        -------
        bool
            True if real-time updates are supported, False otherwise
        """
        # Check for CI environments
        ci_indicators = ["CI", "CONTINUOUS_INTEGRATION", "BUILD_NUMBER", "GITHUB_ACTIONS"]
        for indicator in ci_indicators:
            if os.getenv(indicator):
                return False

        # Check if stdout is a TTY
        if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
            return False

        # Check for output redirection
        if os.getenv("TERM") == "dumb":
            return False

        # Check for NO_COLOR or similar environment variables
        if os.getenv("NO_COLOR") or os.getenv("EMUSES_SIMPLE_OUTPUT"):
            return False

        return True

    def _get_terminal_size(self) -> tuple:
        """
        Get the current terminal dimensions.

        Returns
        -------
        tuple
            (width, height) of the terminal, defaults to (80, 24) if detection fails
        """
        try:
            import shutil
            size = shutil.get_terminal_size(fallback=(80, 24))
            return size.columns, size.lines
        except Exception:
            return 80, 24

    def _should_update(self) -> bool:
        """
        Check if enough time has passed since last update (rate limiting).

        Returns
        -------
        bool
            True if update is allowed, False if rate limited
        """
        current_time = time.time()
        time_since_last = (current_time - self._last_update_time) * 1000  # Convert to ms

        if time_since_last >= self.rate_limit_ms:
            self._last_update_time = current_time
            return True
        return False

    def update_progress(self, tracker: ProgressTracker, output_stream=None) -> None:
        """
        Update progress display with real-time updates or fallback.

        Parameters
        ----------
        tracker : ProgressTracker
            Progress tracker instance to get current progress
        output_stream : file-like object, optional
            Output stream for testing, uses sys.stdout by default

        Returns
        -------
        None
        """
        # Apply rate limiting
        if not self._should_update():
            return

        if output_stream is None:
            output_stream = sys.stdout

        if self.supports_real_time:
            self._update_real_time(tracker, output_stream)
        else:
            self._update_fallback(tracker, output_stream)

    def _update_real_time(self, tracker: ProgressTracker, output_stream) -> None:
        """
        Update progress using ANSI escape sequences for real-time display.

        Parameters
        ----------
        tracker : ProgressTracker
            Progress tracker instance
        output_stream : file-like object
            Output stream to write to

        Returns
        -------
        None
        """
        # Clear current line and move cursor to start
        output_stream.write(self._ansi_codes["cursor_to_start"])
        output_stream.write(self._ansi_codes["clear_line"])

        # Generate progress display
        progress_text = self._generate_progress_text(tracker)

        # Write the updated progress
        output_stream.write(progress_text)
        output_stream.flush()

    def _update_fallback(self, tracker: ProgressTracker, output_stream) -> None:
        """
        Update progress using fallback method for non-real-time environments.

        Parameters
        ----------
        tracker : ProgressTracker
            Progress tracker instance
        output_stream : file-like object
            Output stream to write to

        Returns
        -------
        None
        """
        # Generate progress text
        progress_text = self._generate_progress_text(tracker)

        # Write progress as a new line (no real-time update)
        output_stream.write(progress_text + "\n")
        output_stream.flush()

    def _generate_progress_text(self, tracker: ProgressTracker) -> str:
        """
        Generate progress text display.

        Parameters
        ----------
        tracker : ProgressTracker
            Progress tracker instance

        Returns
        -------
        str
            Formatted progress text
        """
        if not tracker.stages:
            return "No stages configured"

        current_stage = tracker.current_stage
        overall_progress = tracker.get_overall_progress()
        stage_progress = 0.0

        if 0 <= tracker.current_stage_index < len(tracker.stages):
            stage_progress = tracker.stages[tracker.current_stage_index].progress

        # Create progress bar
        bar_width = min(30, self.terminal_width - 40)  # Leave space for text
        filled_width = int(bar_width * overall_progress)
        bar = "█" * filled_width + "░" * (bar_width - filled_width)

        # Format progress text
        progress_text = (
            f"[{bar}] {overall_progress:.1%} | "
            f"{current_stage}: {stage_progress:.1%}"
        )

        return progress_text

    def handle_terminal_resize(self, width: int, height: int) -> None:
        """
        Handle terminal resize events.

        Parameters
        ----------
        width : int
            New terminal width
        height : int
            New terminal height

        Returns
        -------
        None
        """
        self.terminal_width = width
        self.terminal_height = height

    def cleanup(self) -> None:
        """
        Clean up resources and reset terminal state if needed.

        Returns
        -------
        None
        """
        if self.supports_real_time:
            # Move cursor to new line to avoid overwriting
            sys.stdout.write("\n")
            sys.stdout.flush()
