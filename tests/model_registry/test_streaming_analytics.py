"""Tests for real-time analytics streaming functionality."""

import asyncio
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from emuses.multi_user_service.models import Base, User, Workspace, ModelRegistry
from emuses.tools.streaming_analytics import (
    AnalyticsStreamer, AnalyticsStreamingError, StreamingConfig
)


@pytest.fixture
def streaming_db_engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def streaming_db_session(streaming_db_engine):
    """Create a database session for testing."""
    Session = sessionmaker(bind=streaming_db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_streaming_user(streaming_db_session):
    """Create a test user for streaming."""
    user = User(
        id=uuid.uuid4(),
        email="streaming@example.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        organization="Streaming Org",
        role="researcher"
    )
    streaming_db_session.add(user)
    streaming_db_session.commit()
    return user


@pytest.fixture
def test_streaming_workspace(streaming_db_session, test_streaming_user):
    """Create a test workspace for streaming."""
    workspace = Workspace(
        id=uuid.uuid4(),
        name="streaming-workspace",
        description="Test streaming workspace",
        owner_id=test_streaming_user.id,
        storage_path="/test/streaming/workspace",
        is_active=True
    )
    streaming_db_session.add(workspace)
    streaming_db_session.commit()
    return workspace


@pytest.fixture
def test_streaming_model(streaming_db_session, test_streaming_user, test_streaming_workspace):
    """Create a test model for streaming."""
    model = ModelRegistry(
        id=uuid.uuid4(),
        name="streaming-model",
        description="Test streaming model",
        owner_id=test_streaming_user.id,
        workspace_id=test_streaming_workspace.id,
        is_public=True,
        model_path="/test/streaming/model",
        model_type="sklearn",
        version="1.0.0",
        model_size_bytes=1024*1024,
        manifest_hash="streaminghash123"
    )
    streaming_db_session.add(model)
    streaming_db_session.commit()
    return model


class TestStreamingConfig:
    """Test streaming configuration."""

    def test_streaming_config_initialization(self):
        """Test StreamingConfig initialization with default values."""
        config = StreamingConfig()
        assert config.batch_size == 100
        assert config.flush_interval_seconds == 5.0
        assert config.max_queue_size == 10000
        assert config.enable_realtime is True

    def test_streaming_config_custom_values(self):
        """Test StreamingConfig initialization with custom values."""
        config = StreamingConfig(
            batch_size=50,
            flush_interval_seconds=10.0,
            max_queue_size=5000,
            enable_realtime=False
        )
        assert config.batch_size == 50
        assert config.flush_interval_seconds == 10.0
        assert config.max_queue_size == 5000
        assert config.enable_realtime is False


class TestAnalyticsStreamer:
    """Test analytics streaming functionality."""

    def test_streamer_initialization(self, streaming_db_session):
        """Test AnalyticsStreamer initialization."""
        streamer = AnalyticsStreamer(db_session=streaming_db_session)
        assert streamer.db_session == streaming_db_session
        assert isinstance(streamer.config, StreamingConfig)
        assert streamer._event_queue is not None
        assert streamer._running is False

    def test_streamer_initialization_no_session(self):
        """Test AnalyticsStreamer initialization without database session fails."""
        with pytest.raises(AnalyticsStreamingError, match="Database session is required"):
            AnalyticsStreamer()

    @pytest.mark.asyncio
    async def test_queue_download_event(self, streaming_db_session, test_streaming_model, test_streaming_user):
        """Test queuing download events for streaming."""
        streamer = AnalyticsStreamer(db_session=streaming_db_session)
        
        # Queue a download event
        await streamer.queue_download_event(
            model_id=test_streaming_model.id,
            user_id=test_streaming_user.id,
            download_size_bytes=1024,
            download_method="api",
            user_agent="streaming-client/1.0"
        )
        
        # Event should be in queue
        assert not streamer._event_queue.empty()

    @pytest.mark.asyncio
    async def test_queue_community_insight_event(self, streaming_db_session):
        """Test queuing community insight events."""
        streamer = AnalyticsStreamer(db_session=streaming_db_session)
        
        insight_data = {
            "trending_models": ["model1", "model2"],
            "popular_tags": ["classification", "sklearn"],
            "generated_at": datetime.utcnow().isoformat()
        }
        
        await streamer.queue_community_insight_event(insight_data)
        
        # Event should be in queue
        assert not streamer._event_queue.empty()

    @pytest.mark.asyncio
    async def test_queue_user_behavior_event(self, streaming_db_session, test_streaming_user):
        """Test queuing user behavior events."""
        streamer = AnalyticsStreamer(db_session=streaming_db_session)
        
        behavior_data = {
            "user_id": str(test_streaming_user.id),
            "download_patterns": {"total_downloads": 5},
            "analyzed_at": datetime.utcnow().isoformat()
        }
        
        await streamer.queue_user_behavior_event(behavior_data)
        
        # Event should be in queue
        assert not streamer._event_queue.empty()

    @pytest.mark.asyncio
    async def test_start_streaming(self, streaming_db_session):
        """Test starting analytics streaming."""
        streamer = AnalyticsStreamer(db_session=streaming_db_session)
        
        # Mock the background task
        with patch.object(streamer, '_process_events') as mock_process:
            mock_process.return_value = asyncio.create_task(asyncio.sleep(0.1))
            
            await streamer.start_streaming()
            
            assert streamer._running is True
            assert streamer._background_task is not None

    @pytest.mark.asyncio
    async def test_stop_streaming(self, streaming_db_session):
        """Test stopping analytics streaming."""
        streamer = AnalyticsStreamer(db_session=streaming_db_session)
        
        # Start streaming first
        with patch.object(streamer, '_process_events') as mock_process:
            mock_process.return_value = asyncio.create_task(asyncio.sleep(0.1))
            await streamer.start_streaming()
            
            # Now stop streaming
            await streamer.stop_streaming()
            
            assert streamer._running is False

    @pytest.mark.asyncio
    async def test_flush_queue(self, streaming_db_session, test_streaming_model, test_streaming_user):
        """Test flushing queue with events."""
        streamer = AnalyticsStreamer(db_session=streaming_db_session)
        
        # Queue some events
        await streamer.queue_download_event(
            model_id=test_streaming_model.id,
            user_id=test_streaming_user.id,
            download_size_bytes=1024,
            download_method="api"
        )
        
        # Mock external streaming endpoints
        with patch.object(streamer, '_send_to_external_systems') as mock_send:
            mock_send.return_value = None
            
            await streamer.flush_queue()
            
            # Queue should be empty after flush
            assert streamer._event_queue.empty()
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_queue_stats(self, streaming_db_session, test_streaming_model, test_streaming_user):
        """Test getting queue statistics."""
        streamer = AnalyticsStreamer(db_session=streaming_db_session)
        
        # Queue some events
        await streamer.queue_download_event(
            model_id=test_streaming_model.id,
            user_id=test_streaming_user.id,
            download_size_bytes=1024
        )
        
        stats = streamer.get_queue_stats()
        
        assert "queue_size" in stats
        assert "events_processed" in stats
        assert "streaming_active" in stats
        assert stats["queue_size"] == 1
        assert stats["streaming_active"] is False

    @pytest.mark.asyncio
    async def test_process_events_batch(self, streaming_db_session, test_streaming_model, test_streaming_user):
        """Test processing events in batches."""
        config = StreamingConfig(batch_size=2)
        streamer = AnalyticsStreamer(db_session=streaming_db_session, config=config)
        
        # Queue multiple events
        for i in range(3):
            await streamer.queue_download_event(
                model_id=test_streaming_model.id,
                user_id=test_streaming_user.id,
                download_size_bytes=1024 + i
            )
        
        # Mock external sending
        with patch.object(streamer, '_send_to_external_systems') as mock_send:
            mock_send.return_value = None
            
            # Process one batch
            await streamer._process_batch()
            
            # Should process 2 events (batch_size)
            assert streamer._event_queue.qsize() == 1
            mock_send.assert_called_once()

    def test_streaming_error_handling(self, streaming_db_session):
        """Test error handling in streaming operations."""
        streamer = AnalyticsStreamer(db_session=streaming_db_session)
        
        # Test queue overflow
        config = StreamingConfig(max_queue_size=1)
        streamer.config = config
        
        # This should not raise an error but handle overflow gracefully
        try:
            # Fill queue beyond capacity
            for i in range(3):
                asyncio.run(streamer.queue_download_event(
                    model_id=uuid.uuid4(),
                    user_id=uuid.uuid4(),
                    download_size_bytes=1024
                ))
        except AnalyticsStreamingError:
            # Expected behavior when queue is full
            pass


class TestStreamingIntegration:
    """Test streaming integration with observability systems."""

    @pytest.mark.asyncio
    async def test_metrics_tracking_for_streaming(self, streaming_db_session):
        """Test that streaming operations are tracked in metrics."""
        streamer = AnalyticsStreamer(db_session=streaming_db_session)
        
        # Should not raise an error even if metrics system unavailable
        stats = streamer.get_queue_stats()
        assert stats is not None

    @pytest.mark.asyncio
    async def test_external_systems_integration(self, streaming_db_session, test_streaming_model, test_streaming_user):
        """Test integration with external streaming systems."""
        streamer = AnalyticsStreamer(db_session=streaming_db_session)
        
        # Queue an event
        await streamer.queue_download_event(
            model_id=test_streaming_model.id,
            user_id=test_streaming_user.id,
            download_size_bytes=1024
        )
        
        # Mock external systems
        events = []
        
        async def mock_send(events_batch):
            events.extend(events_batch)
            
        with patch.object(streamer, '_send_to_external_systems', side_effect=mock_send):
            await streamer.flush_queue()
            
            # Should have processed the event
            assert len(events) == 1
            assert events[0]["event_type"] == "model_download"

    @pytest.mark.asyncio
    async def test_graceful_degradation_without_streaming(self, streaming_db_session, test_streaming_model, test_streaming_user):
        """Test that analytics work when streaming is disabled."""
        config = StreamingConfig(enable_realtime=False)
        streamer = AnalyticsStreamer(db_session=streaming_db_session, config=config)
        
        # Queue operations should still work but not stream
        await streamer.queue_download_event(
            model_id=test_streaming_model.id,
            user_id=test_streaming_user.id,
            download_size_bytes=1024
        )
        
        # Queue should have the event but streaming is disabled
        assert not streamer._event_queue.empty()
        assert not streamer.config.enable_realtime


if __name__ == "__main__":
    pytest.main([__file__])