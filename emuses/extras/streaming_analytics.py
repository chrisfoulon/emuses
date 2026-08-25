"""Real-time analytics streaming for EMUSES model registry.

This module provides real-time streaming capabilities for model registry analytics,
enabling live dashboards, alerts, and external system integration.
"""

import asyncio
import uuid
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from emuses.multi_user_service.models import ModelRegistry, User
from emuses.observability.metrics import get_metrics_registry


class AnalyticsStreamingError(Exception):
    """Exception raised for analytics streaming errors."""
    pass


@dataclass
class StreamingConfig:
    """Configuration for analytics streaming.

    Attributes
    ----------
    batch_size : int
        Number of events to process in each batch
    flush_interval_seconds : float
        Interval between batch processing
    max_queue_size : int
        Maximum number of events to queue
    enable_realtime : bool
        Whether to enable real-time streaming
    """
    batch_size: int = 100
    flush_interval_seconds: float = 5.0
    max_queue_size: int = 10000
    enable_realtime: bool = True


class AnalyticsStreamer:
    """Real-time analytics streaming system.

    Provides queuing, batching, and streaming of analytics events to external
    systems like Kafka, Redis, or webhook endpoints for real-time dashboards.

    Parameters
    ----------
    db_session : Session
        Database session for analytics operations
    config : StreamingConfig, optional
        Streaming configuration settings

    Attributes
    ----------
    db_session : Session
        Database session reference
    config : StreamingConfig
        Streaming configuration

    Examples
    --------
    >>> streamer = AnalyticsStreamer(db_session)
    >>> await streamer.start_streaming()
    >>> await streamer.queue_download_event(model_id, user_id, 1024)
    >>> await streamer.stop_streaming()
    """

    def __init__(self, db_session: Optional[Session] = None, config: Optional[StreamingConfig] = None):
        if db_session is None:
            raise AnalyticsStreamingError("Database session is required")

        self.db_session = db_session
        self.config = config or StreamingConfig()
        self.metrics_registry = get_metrics_registry()

        # Internal state
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=self.config.max_queue_size)
        self._running: bool = False
        self._background_task: Optional[asyncio.Task] = None
        self._events_processed: int = 0

    async def queue_download_event(
        self,
        model_id: uuid.UUID,
        user_id: uuid.UUID,
        download_size_bytes: Optional[int] = None,
        download_method: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """Queue a model download event for streaming.

        Parameters
        ----------
        model_id : uuid.UUID
            ID of the downloaded model
        user_id : uuid.UUID
            ID of the user who downloaded
        download_size_bytes : int, optional
            Size of downloaded content
        download_method : str, optional
            Download method (api, cli, web)
        user_agent : str, optional
            User agent string

        Raises
        ------
        AnalyticsStreamingError
            If queue is full or other streaming errors
        """
        try:
            # Validate model and user exist
            model = self.db_session.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
            if not model:
                raise AnalyticsStreamingError("Model not found")

            user = self.db_session.query(User).filter(User.id == user_id).first()
            if not user:
                raise AnalyticsStreamingError("User not found")

            event = {
                "event_type": "model_download",
                "timestamp": datetime.utcnow().isoformat(),
                "model_id": str(model_id),
                "user_id": str(user_id),
                "download_size_bytes": download_size_bytes,
                "download_method": download_method,
                "user_agent": user_agent,
                "model_type": model.model_type,
                "model_name": model.name
            }

            # Try to put event in queue
            try:
                self._event_queue.put_nowait(event)
            except asyncio.QueueFull:
                # Handle overflow by dropping oldest events
                try:
                    self._event_queue.get_nowait()
                    self._event_queue.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass  # Race condition, queue became empty

        except Exception as e:
            raise AnalyticsStreamingError(f"Failed to queue download event: {str(e)}")

    async def queue_community_insight_event(self, insight_data: Dict[str, Any]) -> None:
        """Queue a community insight event for streaming.

        Parameters
        ----------
        insight_data : dict
            Community insight data to stream

        Raises
        ------
        AnalyticsStreamingError
            If queue is full or other streaming errors
        """
        try:
            event = {
                "event_type": "community_insight",
                "timestamp": datetime.utcnow().isoformat(),
                "data": insight_data
            }

            try:
                self._event_queue.put_nowait(event)
            except asyncio.QueueFull:
                # Handle overflow
                try:
                    self._event_queue.get_nowait()
                    self._event_queue.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass

        except Exception as e:
            raise AnalyticsStreamingError(f"Failed to queue community insight event: {str(e)}")

    async def queue_user_behavior_event(self, behavior_data: Dict[str, Any]) -> None:
        """Queue a user behavior event for streaming.

        Parameters
        ----------
        behavior_data : dict
            User behavior analysis data to stream

        Raises
        ------
        AnalyticsStreamingError
            If queue is full or other streaming errors
        """
        try:
            event = {
                "event_type": "user_behavior",
                "timestamp": datetime.utcnow().isoformat(),
                "data": behavior_data
            }

            try:
                self._event_queue.put_nowait(event)
            except asyncio.QueueFull:
                # Handle overflow
                try:
                    self._event_queue.get_nowait()
                    self._event_queue.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass

        except Exception as e:
            raise AnalyticsStreamingError(f"Failed to queue user behavior event: {str(e)}")

    async def start_streaming(self) -> None:
        """Start the real-time streaming background task.

        Raises
        ------
        AnalyticsStreamingError
            If streaming is already running or fails to start
        """
        if self._running:
            raise AnalyticsStreamingError("Streaming is already running")

        if not self.config.enable_realtime:
            return  # Streaming disabled

        self._running = True
        self._background_task = asyncio.create_task(self._process_events())

    async def stop_streaming(self) -> None:
        """Stop the real-time streaming and flush remaining events.

        Raises
        ------
        AnalyticsStreamingError
            If error occurs during shutdown
        """
        if not self._running:
            return

        self._running = False

        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass

        # Flush remaining events
        await self.flush_queue()

    async def flush_queue(self) -> None:
        """Flush all queued events to external systems.

        Raises
        ------
        AnalyticsStreamingError
            If flushing fails
        """
        try:
            events = []

            # Drain the queue
            while not self._event_queue.empty():
                try:
                    event = self._event_queue.get_nowait()
                    events.append(event)
                except asyncio.QueueEmpty:
                    break

            if events:
                await self._send_to_external_systems(events)
                self._events_processed += len(events)

        except Exception as e:
            raise AnalyticsStreamingError(f"Failed to flush queue: {str(e)}")

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get current queue and streaming statistics.

        Returns
        -------
        dict
            Statistics including queue size, events processed, and streaming status
        """
        return {
            "queue_size": self._event_queue.qsize(),
            "events_processed": self._events_processed,
            "streaming_active": self._running,
            "max_queue_size": self.config.max_queue_size,
            "batch_size": self.config.batch_size,
            "flush_interval": self.config.flush_interval_seconds
        }

    async def _process_events(self) -> None:
        """Background task for processing events in batches."""
        while self._running:
            try:
                await self._process_batch()
                await asyncio.sleep(self.config.flush_interval_seconds)
            except Exception:
                # Log error but continue processing
                try:
                    # Track errors in metrics if available
                    pass
                except Exception:
                    pass  # Avoid cascading failures

                await asyncio.sleep(self.config.flush_interval_seconds)

    async def _process_batch(self) -> None:
        """Process a batch of events from the queue."""
        events = []
        batch_size = min(self.config.batch_size, self._event_queue.qsize())

        # Collect events for batch
        for _ in range(batch_size):
            try:
                event = self._event_queue.get_nowait()
                events.append(event)
            except asyncio.QueueEmpty:
                break

        if events:
            await self._send_to_external_systems(events)
            self._events_processed += len(events)

    async def _send_to_external_systems(self, events: List[Dict[str, Any]]) -> None:
        """Send events to external streaming systems.

        Parameters
        ----------
        events : list
            List of events to send to external systems

        Notes
        -----
        This is a placeholder for integration with external systems like:
        - Apache Kafka for high-throughput streaming
        - Redis Streams for lightweight streaming
        - Webhooks for external system integration
        - WebSocket connections for real-time dashboards
        """
        # Placeholder implementation - in production, integrate with:
        # - Kafka producer for scalable streaming
        # - Redis streams for caching layer
        # - WebSocket broadcasts for real-time dashboards
        # - Webhook endpoints for external integrations

        # Track streaming metrics
        try:
            # Update metrics about streaming operations
            streaming_metrics = self.metrics_registry
            if hasattr(streaming_metrics, 'model_analytics_operations_total'):
                streaming_metrics.model_analytics_operations_total.labels(
                    operation_type="streaming",
                    status="success"
                ).inc()
        except Exception:
            # Graceful degradation if metrics unavailable
            pass

        # Log events for debugging (would be replaced with actual streaming)
        for event in events:
            # In production, send to external systems here
            pass
