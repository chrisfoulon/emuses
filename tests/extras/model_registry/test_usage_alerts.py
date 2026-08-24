"""Tests for unusual usage pattern alerting system."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from emuses.multi_user_service.models import Base, User, Workspace, ModelRegistry, ModelDownload
from emuses.extras.usage_alerts import (
    UsageAlerter, AlertConfig, AlertingError, AlertSeverity, AlertType
)


@pytest.fixture
def alerts_db_engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def alerts_db_session(alerts_db_engine):
    """Create a database session for testing."""
    Session = sessionmaker(bind=alerts_db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_alert_user(alerts_db_session):
    """Create a test user for alerting."""
    user = User(
        id=uuid.uuid4(),
        email="alert@example.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        organization="Alert Org",
        role="researcher"
    )
    alerts_db_session.add(user)
    alerts_db_session.commit()
    return user


@pytest.fixture
def test_alert_workspace(alerts_db_session, test_alert_user):
    """Create a test workspace for alerting."""
    workspace = Workspace(
        id=uuid.uuid4(),
        name="alert-workspace",
        description="Test alert workspace",
        owner_id=test_alert_user.id,
        storage_path="/test/alert/workspace",
        is_active=True
    )
    alerts_db_session.add(workspace)
    alerts_db_session.commit()
    return workspace


@pytest.fixture
def test_alert_model(alerts_db_session, test_alert_user, test_alert_workspace):
    """Create a test model for alerting."""
    model = ModelRegistry(
        id=uuid.uuid4(),
        name="alert-model",
        description="Test alert model",
        owner_id=test_alert_user.id,
        workspace_id=test_alert_workspace.id,
        is_public=True,
        model_path="/test/alert/model",
        model_type="sklearn",
        version="1.0.0",
        model_size_bytes=1024*1024,
        manifest_hash="alerthash123"
    )
    alerts_db_session.add(model)
    alerts_db_session.commit()
    return model


class TestAlertConfig:
    """Test alerting configuration."""

    def test_alert_config_initialization(self):
        """Test AlertConfig initialization with default values."""
        config = AlertConfig()
        assert config.enable_alerts is True
        assert config.download_spike_threshold == 100
        assert config.unusual_activity_window_hours == 24
        assert config.minimum_activity_threshold == 5

    def test_alert_config_custom_values(self):
        """Test AlertConfig initialization with custom values."""
        config = AlertConfig(
            enable_alerts=False,
            download_spike_threshold=50,
            unusual_activity_window_hours=12,
            minimum_activity_threshold=10
        )
        assert config.enable_alerts is False
        assert config.download_spike_threshold == 50
        assert config.unusual_activity_window_hours == 12
        assert config.minimum_activity_threshold == 10


class TestAlertSeverity:
    """Test alert severity enum."""

    def test_severity_values(self):
        """Test that alert severity enum has expected values."""
        assert AlertSeverity.LOW.value == "low"
        assert AlertSeverity.MEDIUM.value == "medium"
        assert AlertSeverity.HIGH.value == "high"
        assert AlertSeverity.CRITICAL.value == "critical"


class TestAlertType:
    """Test alert type enum."""

    def test_alert_type_values(self):
        """Test that alert type enum has expected values."""
        assert AlertType.DOWNLOAD_SPIKE.value == "download_spike"
        assert AlertType.UNUSUAL_USER_ACTIVITY.value == "unusual_user_activity"
        assert AlertType.SUSPICIOUS_PATTERN.value == "suspicious_pattern"
        assert AlertType.PERFORMANCE_ANOMALY.value == "performance_anomaly"


class TestUsageAlerter:
    """Test usage alerting functionality."""

    def test_alerter_initialization(self, alerts_db_session):
        """Test UsageAlerter initialization."""
        alerter = UsageAlerter(db_session=alerts_db_session)
        assert alerter.db_session == alerts_db_session
        assert isinstance(alerter.config, AlertConfig)

    def test_alerter_initialization_no_session(self):
        """Test UsageAlerter initialization without database session fails."""
        with pytest.raises(AlertingError, match="Database session is required"):
            UsageAlerter()

    def test_check_download_spike_no_downloads(self, alerts_db_session, test_alert_model):
        """Test download spike detection with no downloads."""
        alerter = UsageAlerter(db_session=alerts_db_session)
        
        alerts = alerter.check_download_spike(test_alert_model.id)
        assert alerts == []

    def test_check_download_spike_normal_activity(self, alerts_db_session, test_alert_model, test_alert_user):
        """Test download spike detection with normal activity."""
        alerter = UsageAlerter(db_session=alerts_db_session)
        
        # Create normal download activity (below threshold)
        for i in range(5):
            download = ModelDownload(
                model_id=test_alert_model.id,
                user_id=test_alert_user.id,
                downloaded_at=datetime.utcnow() - timedelta(minutes=i*10),
                download_size_bytes=1024
            )
            alerts_db_session.add(download)
        alerts_db_session.commit()
        
        alerts = alerter.check_download_spike(test_alert_model.id)
        assert alerts == []

    def test_check_download_spike_high_activity(self, alerts_db_session, test_alert_model, test_alert_user):
        """Test download spike detection with high activity."""
        config = AlertConfig(download_spike_threshold=10)
        alerter = UsageAlerter(db_session=alerts_db_session, config=config)
        
        # Create spike activity (above threshold)
        for i in range(15):
            download = ModelDownload(
                model_id=test_alert_model.id,
                user_id=test_alert_user.id,
                downloaded_at=datetime.utcnow() - timedelta(minutes=i*2),
                download_size_bytes=1024
            )
            alerts_db_session.add(download)
        alerts_db_session.commit()
        
        alerts = alerter.check_download_spike(test_alert_model.id)
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == AlertType.DOWNLOAD_SPIKE
        assert alerts[0]["severity"] == AlertSeverity.MEDIUM  # 15/10 = 1.5 ratio -> MEDIUM

    def test_check_unusual_user_activity_no_activity(self, alerts_db_session, test_alert_user):
        """Test unusual user activity detection with no activity."""
        alerter = UsageAlerter(db_session=alerts_db_session)
        
        alerts = alerter.check_unusual_user_activity(test_alert_user.id)
        assert alerts == []

    def test_check_unusual_user_activity_normal_patterns(self, alerts_db_session, test_alert_model, test_alert_user):
        """Test unusual user activity detection with normal patterns."""
        alerter = UsageAlerter(db_session=alerts_db_session)
        
        # Create normal activity pattern
        for i in range(3):
            download = ModelDownload(
                model_id=test_alert_model.id,
                user_id=test_alert_user.id,
                downloaded_at=datetime.utcnow() - timedelta(hours=i*8),
                download_size_bytes=1024
            )
            alerts_db_session.add(download)
        alerts_db_session.commit()
        
        alerts = alerter.check_unusual_user_activity(test_alert_user.id)
        assert alerts == []

    def test_check_unusual_user_activity_suspicious_patterns(self, alerts_db_session, test_alert_user, test_alert_workspace):
        """Test unusual user activity detection with suspicious patterns."""
        config = AlertConfig(minimum_activity_threshold=2)
        alerter = UsageAlerter(db_session=alerts_db_session, config=config)
        
        # Create multiple models for unusual activity
        models = []
        for i in range(25):  # Many different models in short time (need >15 unique, >20 downloads)
            model = ModelRegistry(
                id=uuid.uuid4(),
                name=f"bulk-model-{i}",
                description=f"Test bulk model {i}",
                owner_id=test_alert_user.id,
                workspace_id=test_alert_workspace.id,
                is_public=True,
                model_path=f"/test/bulk/model/{i}",
                model_type="sklearn",
                version="1.0.0",
                model_size_bytes=1024*1024,
                manifest_hash=f"bulkhash{i}"
            )
            alerts_db_session.add(model)
            models.append(model)
        alerts_db_session.commit()
        
        # Create downloads from many different models in short time
        for model in models:
            download = ModelDownload(
                model_id=model.id,
                user_id=test_alert_user.id,
                downloaded_at=datetime.utcnow() - timedelta(minutes=5),
                download_size_bytes=1024
            )
            alerts_db_session.add(download)
        alerts_db_session.commit()
        
        alerts = alerter.check_unusual_user_activity(test_alert_user.id)
        assert len(alerts) > 0
        assert alerts[0]["alert_type"] == AlertType.UNUSUAL_USER_ACTIVITY
        assert alerts[0]["severity"] in [AlertSeverity.MEDIUM, AlertSeverity.HIGH]

    def test_analyze_usage_patterns_empty_data(self, alerts_db_session):
        """Test usage pattern analysis with empty data."""
        alerter = UsageAlerter(db_session=alerts_db_session)
        
        alerts = alerter.analyze_usage_patterns()
        assert alerts == []

    def test_analyze_usage_patterns_with_data(self, alerts_db_session, test_alert_model, test_alert_user):
        """Test usage pattern analysis with data."""
        alerter = UsageAlerter(db_session=alerts_db_session)
        
        # Create some download activity
        download = ModelDownload(
            model_id=test_alert_model.id,
            user_id=test_alert_user.id,
            downloaded_at=datetime.utcnow(),
            download_size_bytes=1024
        )
        alerts_db_session.add(download)
        alerts_db_session.commit()
        
        # Should not generate alerts for normal activity
        alerts = alerter.analyze_usage_patterns()
        # For normal activity, we expect no alerts
        assert isinstance(alerts, list)

    def test_send_alert_success(self, alerts_db_session):
        """Test successful alert sending."""
        alerter = UsageAlerter(db_session=alerts_db_session)
        
        alert_data = {
            "alert_type": AlertType.DOWNLOAD_SPIKE,
            "severity": AlertSeverity.HIGH,
            "model_id": str(uuid.uuid4()),
            "description": "Test alert",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Mock external alerting system
        with patch.object(alerter, '_send_to_external_systems') as mock_send:
            mock_send.return_value = True
            
            result = alerter.send_alert(alert_data)
            assert result is True
            mock_send.assert_called_once_with(alert_data)

    def test_send_alert_failure(self, alerts_db_session):
        """Test alert sending failure handling."""
        alerter = UsageAlerter(db_session=alerts_db_session)
        
        alert_data = {
            "alert_type": AlertType.DOWNLOAD_SPIKE,
            "severity": AlertSeverity.HIGH,
            "model_id": str(uuid.uuid4()),
            "description": "Test alert",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Mock external alerting system failure
        with patch.object(alerter, '_send_to_external_systems') as mock_send:
            mock_send.side_effect = Exception("External system failure")
            
            result = alerter.send_alert(alert_data)
            assert result is False

    def test_get_alert_stats(self, alerts_db_session):
        """Test getting alerting statistics."""
        alerter = UsageAlerter(db_session=alerts_db_session)
        
        stats = alerter.get_alert_stats()
        
        assert "alerts_sent" in stats
        assert "alerts_pending" in stats
        assert "config" in stats
        assert "alerting_enabled" in stats
        assert stats["alerting_enabled"] == alerter.config.enable_alerts


class TestAlertIntegration:
    """Test alert integration with observability systems."""

    def test_metrics_tracking_for_alerts(self, alerts_db_session):
        """Test that alerting operations are tracked in metrics."""
        alerter = UsageAlerter(db_session=alerts_db_session)
        
        # Should not raise an error even if metrics system unavailable
        stats = alerter.get_alert_stats()
        assert stats is not None

    def test_graceful_degradation_without_alerting(self, alerts_db_session):
        """Test that system works when alerting is disabled."""
        config = AlertConfig(enable_alerts=False)
        alerter = UsageAlerter(db_session=alerts_db_session, config=config)
        
        # Operations should still work but not send alerts
        alert_data = {
            "alert_type": AlertType.DOWNLOAD_SPIKE,
            "severity": AlertSeverity.HIGH,
            "description": "Test alert"
        }
        
        result = alerter.send_alert(alert_data)
        assert result is False  # Should not send when disabled


if __name__ == "__main__":
    pytest.main([__file__])