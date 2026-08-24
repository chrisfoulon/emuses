"""Usage pattern alerting system for EMUSES model registry.

This module provides alerting capabilities for unusual usage patterns,
download spikes, and suspicious activities in the model registry.
"""

import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any, Optional, Union
from collections import Counter

from sqlalchemy.orm import Session

from emuses.multi_user_service.models import ModelRegistry, ModelDownload, User
from emuses.observability.metrics import get_metrics_registry


class AlertingError(Exception):
    """Exception raised for alerting system errors."""
    pass


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts that can be generated."""
    DOWNLOAD_SPIKE = "download_spike"
    UNUSUAL_USER_ACTIVITY = "unusual_user_activity"
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    PERFORMANCE_ANOMALY = "performance_anomaly"


@dataclass
class AlertConfig:
    """Configuration for usage alerting system.

    Attributes
    ----------
    enable_alerts : bool
        Whether alerting system is enabled
    download_spike_threshold : int
        Number of downloads per hour to trigger spike alert
    unusual_activity_window_hours : int
        Time window to analyze for unusual activity
    minimum_activity_threshold : int
        Minimum activity level to consider for analysis
    alert_cooldown_minutes : int
        Minimum time between similar alerts
    """
    enable_alerts: bool = True
    download_spike_threshold: int = 100
    unusual_activity_window_hours: int = 24
    minimum_activity_threshold: int = 5
    alert_cooldown_minutes: int = 60


class UsageAlerter:
    """Usage pattern alerting system.

    Monitors model registry usage for unusual patterns and generates alerts
    for suspicious activities, download spikes, and anomalous behavior.

    Parameters
    ----------
    db_session : Session
        Database session for analytics operations
    config : AlertConfig, optional
        Alerting configuration settings

    Attributes
    ----------
    db_session : Session
        Database session reference
    config : AlertConfig
        Alerting configuration

    Examples
    --------
    >>> alerter = UsageAlerter(db_session)
    >>> alerts = alerter.check_download_spike(model_id)
    >>> if alerts:
    ...     for alert in alerts:
    ...         alerter.send_alert(alert)
    """

    def __init__(self, db_session: Optional[Session] = None, config: Optional[AlertConfig] = None):
        if db_session is None:
            raise AlertingError("Database session is required")

        self.db_session = db_session
        self.config = config or AlertConfig()
        self.metrics_registry = get_metrics_registry()

        # Internal state for tracking
        self._alerts_sent = 0
        self._last_alert_times = {}  # Track last alert time by type+resource

    def check_download_spike(self, model_id: Union[str, uuid.UUID], hours_back: int = 1) -> List[Dict[str, Any]]:
        """Check for unusual download spikes for a specific model.

        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the model to check
        hours_back : int, optional
            Number of hours to look back for spike detection

        Returns
        -------
        List[Dict[str, Any]]
            List of alerts generated for download spikes
        """
        if not self.config.enable_alerts:
            return []

        # Normalize UUID
        if isinstance(model_id, str):
            model_id = uuid.UUID(model_id)

        # Check if model exists
        model = self.db_session.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            return []

        # Calculate time window
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

        # Count downloads in the time window
        download_count = self.db_session.query(ModelDownload).filter(
            ModelDownload.model_id == model_id,
            ModelDownload.downloaded_at >= cutoff_time
        ).count()

        alerts = []

        # Check if download count exceeds threshold
        if download_count > self.config.download_spike_threshold:
            # Determine severity based on how far over threshold
            ratio = download_count / self.config.download_spike_threshold
            if ratio >= 3.0:
                severity = AlertSeverity.CRITICAL
            elif ratio >= 2.0:
                severity = AlertSeverity.HIGH
            elif ratio >= 1.5:
                severity = AlertSeverity.MEDIUM
            else:
                severity = AlertSeverity.LOW

            alert = {
                "alert_type": AlertType.DOWNLOAD_SPIKE,
                "severity": severity,
                "model_id": str(model_id),
                "model_name": model.name,
                "download_count": download_count,
                "threshold": self.config.download_spike_threshold,
                "time_window_hours": hours_back,
                "description": f"Model '{model.name}' has {download_count} downloads in {hours_back} hour(s), exceeding threshold of {self.config.download_spike_threshold}",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    "model_type": model.model_type,
                    "is_public": model.is_public,
                    "ratio": ratio
                }
            }
            alerts.append(alert)

        return alerts

    def check_unusual_user_activity(self, user_id: Union[str, uuid.UUID]) -> List[Dict[str, Any]]:
        """Check for unusual activity patterns for a specific user.

        Parameters
        ----------
        user_id : Union[str, UUID]
            ID of the user to check

        Returns
        -------
        List[Dict[str, Any]]
            List of alerts generated for unusual user activity
        """
        if not self.config.enable_alerts:
            return []

        # Normalize UUID
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)

        # Check if user exists
        user = self.db_session.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        # Calculate time window
        cutoff_time = datetime.utcnow() - timedelta(hours=self.config.unusual_activity_window_hours)

        # Get user's downloads in the time window
        downloads = self.db_session.query(ModelDownload).filter(
            ModelDownload.user_id == user_id,
            ModelDownload.downloaded_at >= cutoff_time
        ).all()

        if len(downloads) < self.config.minimum_activity_threshold:
            return []

        alerts = []

        # Check for bulk downloading (many different models in short time)
        unique_models = len(set(download.model_id for download in downloads))
        download_count = len(downloads)

        # Suspicious if downloading many different models
        if unique_models > 15 and download_count > 20:
            # Check time distribution - suspicious if all downloads in very short time
            download_times = [download.downloaded_at for download in downloads]
            time_span = max(download_times) - min(download_times)

            if time_span.total_seconds() < 3600:  # All downloads within 1 hour
                severity = AlertSeverity.HIGH
            elif time_span.total_seconds() < 7200:  # All downloads within 2 hours
                severity = AlertSeverity.MEDIUM
            else:
                severity = AlertSeverity.LOW

            alert = {
                "alert_type": AlertType.UNUSUAL_USER_ACTIVITY,
                "severity": severity,
                "user_id": str(user_id),
                "user_email": user.email,
                "user_organization": user.organization,
                "download_count": download_count,
                "unique_models": unique_models,
                "time_window_hours": self.config.unusual_activity_window_hours,
                "time_span_minutes": int(time_span.total_seconds() / 60),
                "description": f"User '{user.email}' downloaded {download_count} models ({unique_models} unique) in {int(time_span.total_seconds() / 60)} minutes",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    "download_rate_per_hour": download_count / max(time_span.total_seconds() / 3600, 0.1),
                    "model_diversity_ratio": unique_models / download_count
                }
            }
            alerts.append(alert)

        return alerts

    def analyze_usage_patterns(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """Analyze overall usage patterns for anomalies.

        Parameters
        ----------
        hours_back : int, optional
            Number of hours to analyze

        Returns
        -------
        List[Dict[str, Any]]
            List of alerts generated from pattern analysis
        """
        if not self.config.enable_alerts:
            return []

        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

        # Get all downloads in the time window
        downloads = self.db_session.query(ModelDownload).filter(
            ModelDownload.downloaded_at >= cutoff_time
        ).all()

        if len(downloads) < self.config.minimum_activity_threshold:
            return []

        alerts = []

        # Analyze download patterns
        user_download_counts = Counter(download.user_id for download in downloads)
        model_download_counts = Counter(download.model_id for download in downloads)

        # Check for suspicious patterns
        # 1. Single user downloading excessively
        for user_id, count in user_download_counts.most_common(5):
            if count > self.config.download_spike_threshold:
                user_alerts = self.check_unusual_user_activity(user_id)
                alerts.extend(user_alerts)

        # 2. Single model being downloaded excessively
        for model_id, count in model_download_counts.most_common(5):
            if count > self.config.download_spike_threshold:
                model_alerts = self.check_download_spike(model_id, hours_back)
                alerts.extend(model_alerts)

        return alerts

    def send_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Send an alert to configured external systems.

        Parameters
        ----------
        alert_data : dict
            Alert data to send

        Returns
        -------
        bool
            True if alert was sent successfully, False otherwise
        """
        if not self.config.enable_alerts:
            return False

        try:
            # Check cooldown period
            alert_key = f"{alert_data.get('alert_type', 'unknown')}_{alert_data.get('model_id', alert_data.get('user_id', 'unknown'))}"
            last_alert_time = self._last_alert_times.get(alert_key, datetime.min)

            if datetime.utcnow() - last_alert_time < timedelta(minutes=self.config.alert_cooldown_minutes):
                return False  # Still in cooldown period

            # Send to external systems
            success = self._send_to_external_systems(alert_data)

            if success:
                self._alerts_sent += 1
                self._last_alert_times[alert_key] = datetime.utcnow()

                # Track in metrics
                try:
                    from emuses.observability.metrics import model_analytics_operations_total
                    model_analytics_operations_total.labels(
                        operation_type="alert_sent",
                        status="success"
                    ).inc()
                except ImportError:
                    pass

            return success

        except Exception:
            # Log error but don't raise (graceful degradation)
            try:
                from emuses.observability.metrics import model_analytics_operations_total
                model_analytics_operations_total.labels(
                    operation_type="alert_sent",
                    status="error"
                ).inc()
            except ImportError:
                pass
            return False

    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alerting system statistics.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing alerting statistics
        """
        return {
            "alerts_sent": self._alerts_sent,
            "alerts_pending": 0,  # Placeholder for queue-based alerting
            "config": {
                "enable_alerts": self.config.enable_alerts,
                "download_spike_threshold": self.config.download_spike_threshold,
                "unusual_activity_window_hours": self.config.unusual_activity_window_hours,
                "minimum_activity_threshold": self.config.minimum_activity_threshold,
                "alert_cooldown_minutes": self.config.alert_cooldown_minutes
            },
            "alerting_enabled": self.config.enable_alerts,
            "last_analysis": datetime.utcnow().isoformat()
        }

    def _send_to_external_systems(self, alert_data: Dict[str, Any]) -> bool:
        """Send alert to external alerting systems.

        Parameters
        ----------
        alert_data : dict
            Alert data to send

        Returns
        -------
        bool
            True if sent successfully, False otherwise

        Notes
        -----
        This is a placeholder for integration with external alerting systems like:
        - Slack/Teams webhooks for team notifications
        - Email alerts for administrators
        - PagerDuty for critical alerts
        - Custom webhook endpoints
        - SIEM systems for security alerts
        """
        # Placeholder implementation - in production, integrate with:
        # - Slack webhooks for team alerts
        # - Email system for administrator notifications
        # - PagerDuty for critical production alerts
        # - Custom webhook endpoints for external systems
        # - SIEM integration for security alerts

        # For now, just log the alert (would be replaced with actual sending)
        try:
            # In production, this would send to configured alert channels
            # For example:
            # - POST to Slack webhook
            # - Send email via SMTP
            # - POST to PagerDuty API
            # - Send to custom webhook endpoints

            return True  # Simulated success

        except Exception:
            return False
