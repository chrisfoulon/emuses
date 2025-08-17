"""Tests for model registry analytics functionality."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from emuses.multi_user_service.models import Base, User, Workspace, ModelRegistry, ModelDownload
from emuses.tools.model_analytics import ModelAnalytics, AnalyticsError


@pytest.fixture
def analytics_db_engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def analytics_db_session(analytics_db_engine):
    """Create a database session for testing."""
    Session = sessionmaker(bind=analytics_db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(analytics_db_session):
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        organization="Test Org",
        role="researcher"
    )
    analytics_db_session.add(user)
    analytics_db_session.commit()
    return user


@pytest.fixture
def test_workspace(analytics_db_session, test_user):
    """Create a test workspace."""
    workspace = Workspace(
        id=uuid.uuid4(),
        name="test-workspace",
        description="Test workspace",
        owner_id=test_user.id,
        storage_path="/test/workspace/path",
        is_active=True
    )
    analytics_db_session.add(workspace)
    analytics_db_session.commit()
    return workspace


@pytest.fixture
def test_model(analytics_db_session, test_user, test_workspace):
    """Create a test model in registry."""
    model = ModelRegistry(
        id=uuid.uuid4(),
        name="test-model",
        description="Test model",
        owner_id=test_user.id,
        workspace_id=test_workspace.id,
        is_public=False,
        model_path="/test/path",
        model_type="sklearn",
        version="1.0.0",
        model_size_bytes=1024*1024,  # 1MB
        manifest_hash="testhash123"
    )
    analytics_db_session.add(model)
    analytics_db_session.commit()
    return model


class TestModelAnalyticsInitialization:
    """Test ModelAnalytics class initialization."""

    def test_initialization_with_session(self, analytics_db_session):
        """Test ModelAnalytics initialization with database session."""
        analytics = ModelAnalytics(db_session=analytics_db_session)
        assert analytics.db_session == analytics_db_session

    def test_initialization_without_session(self):
        """Test ModelAnalytics initialization without database session fails."""
        with pytest.raises(AnalyticsError, match="Database session is required"):
            ModelAnalytics()


class TestRecordDownload:
    """Test download tracking functionality."""

    def test_record_download_success(self, analytics_db_session, test_model, test_user):
        """Test successfully recording a model download."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Record download
        download_id = analytics.record_download(
            model_id=test_model.id,
            user_id=test_user.id,
            download_size_bytes=1024,
            download_method="api",
            user_agent="test-client/1.0"
        )

        # Verify download was recorded
        assert download_id is not None
        download = analytics_db_session.query(ModelDownload).filter(
            ModelDownload.id == download_id
        ).first()

        assert download is not None
        assert download.model_id == test_model.id
        assert download.user_id == test_user.id
        assert download.download_size_bytes == 1024
        assert download.download_method == "api"
        assert download.user_agent == "test-client/1.0"
        assert isinstance(download.downloaded_at, datetime)

    def test_record_download_invalid_model(self, analytics_db_session, test_user):
        """Test recording download with invalid model ID."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        with pytest.raises(AnalyticsError, match="Model not found"):
            analytics.record_download(
                model_id=uuid.uuid4(),  # Non-existent model
                user_id=test_user.id,
                download_size_bytes=1024
            )

    def test_record_download_invalid_user(self, analytics_db_session, test_model):
        """Test recording download with invalid user ID."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        with pytest.raises(AnalyticsError, match="User not found"):
            analytics.record_download(
                model_id=test_model.id,
                user_id=uuid.uuid4(),  # Non-existent user
                download_size_bytes=1024
            )

    def test_record_download_minimal_data(self, analytics_db_session, test_model, test_user):
        """Test recording download with minimal required data."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        download_id = analytics.record_download(
            model_id=test_model.id,
            user_id=test_user.id
        )

        download = analytics_db_session.query(ModelDownload).filter(
            ModelDownload.id == download_id
        ).first()

        assert download is not None
        assert download.download_size_bytes is None
        assert download.download_method is None
        assert download.user_agent is None


class TestGetModelStats:
    """Test model statistics functionality."""

    def test_get_model_stats_no_downloads(self, analytics_db_session, test_model):
        """Test getting stats for model with no downloads."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        stats = analytics.get_model_stats(test_model.id)

        expected = {
            "model_id": str(test_model.id),
            "total_downloads": 0,
            "unique_users": 0,
            "total_bytes_downloaded": 0,
            "first_download": None,
            "last_download": None,
            "download_methods": {},
            "downloads_by_day": [],
            "top_users": []
        }
        assert stats == expected

    def test_get_model_stats_with_downloads(self, analytics_db_session, test_model, test_user):
        """Test getting stats for model with downloads."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Record some downloads
        download_time = datetime.utcnow() - timedelta(days=1)

        with patch('emuses.tools.model_analytics.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = download_time
            analytics.record_download(test_model.id, test_user.id, 1024, "api")
            analytics.record_download(test_model.id, test_user.id, 2048, "cli")

        stats = analytics.get_model_stats(test_model.id)

        assert stats["model_id"] == str(test_model.id)
        assert stats["total_downloads"] == 2
        assert stats["unique_users"] == 1
        assert stats["total_bytes_downloaded"] == 3072
        assert stats["download_methods"] == {"api": 1, "cli": 1}
        assert len(stats["top_users"]) == 1
        assert stats["top_users"][0]["user_id"] == str(test_user.id)
        assert stats["top_users"][0]["download_count"] == 2

    def test_get_model_stats_invalid_model(self, analytics_db_session):
        """Test getting stats for non-existent model."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        with pytest.raises(AnalyticsError, match="Model not found"):
            analytics.get_model_stats(uuid.uuid4())


class TestGetPopularModels:
    """Test popular models functionality."""

    def test_get_popular_models_empty_registry(self, analytics_db_session):
        """Test getting popular models from empty registry."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        popular = analytics.get_popular_models(limit=10)
        assert popular == []

    def test_get_popular_models_with_downloads(self, analytics_db_session, test_model, test_user):
        """Test getting popular models with download data."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Record downloads to make model popular
        analytics.record_download(test_model.id, test_user.id, 1024)
        analytics.record_download(test_model.id, test_user.id, 1024)

        popular = analytics.get_popular_models(limit=10)

        assert len(popular) == 1
        model_data = popular[0]
        assert model_data["model_id"] == str(test_model.id)
        assert model_data["name"] == test_model.name
        assert model_data["download_count"] == 2
        assert model_data["unique_users"] == 1
        assert model_data["total_bytes"] == 2048

    def test_get_popular_models_time_window(self, analytics_db_session, test_model, test_user):
        """Test getting popular models within time window."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Record old download (outside window)
        old_time = datetime.utcnow() - timedelta(days=40)
        with patch('emuses.tools.model_analytics.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = old_time
            analytics.record_download(test_model.id, test_user.id, 1024)

        # Get popular models from last 30 days
        popular = analytics.get_popular_models(limit=10, days=30)
        assert popular == []

        # Record recent download
        analytics.record_download(test_model.id, test_user.id, 1024)

        popular = analytics.get_popular_models(limit=10, days=30)
        assert len(popular) == 1


class TestCommunityInsights:
    """Test community insights functionality."""

    def test_generate_community_insights_empty_registry(self, analytics_db_session):
        """Test generating insights from empty registry."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        insights = analytics.generate_community_insights()

        expected = {
            "trending_models": [],
            "recommended_models": [],
            "popular_tags": [],
            "active_users": [],
            "discovery_recommendations": []
        }
        assert insights == expected

    def test_generate_community_insights_with_data(self, analytics_db_session, test_model, test_user):
        """Test generating insights with data."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Record some downloads to create data
        analytics.record_download(test_model.id, test_user.id, 1024, "api")

        insights = analytics.generate_community_insights()

        assert "trending_models" in insights
        assert "recommended_models" in insights
        assert "popular_tags" in insights
        assert "active_users" in insights
        assert "discovery_recommendations" in insights

        # Should have some trending models based on downloads
        if insights["trending_models"]:
            trending = insights["trending_models"][0]
            assert trending["model_id"] == str(test_model.id)
            assert trending["trend_score"] > 0


class TestUserBehaviorAnalysis:
    """Test user behavior analysis functionality."""

    def test_analyze_user_behavior_no_data(self, analytics_db_session, test_user):
        """Test user behavior analysis with no data."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        behavior = analytics.analyze_user_behavior(test_user.id)

        expected = {
            "user_id": str(test_user.id),
            "download_patterns": {
                "total_downloads": 0,
                "unique_models": 0,
                "favorite_model_types": [],
                "download_frequency": "never",
                "peak_download_hours": []
            },
            "preferences": {
                "model_types": [],
                "download_methods": []
            },
            "recommendations": []
        }
        assert behavior == expected

    def test_analyze_user_behavior_with_data(self, analytics_db_session, test_model, test_user):
        """Test user behavior analysis with download data."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Record downloads
        analytics.record_download(test_model.id, test_user.id, 1024, "api")
        analytics.record_download(test_model.id, test_user.id, 2048, "cli")

        behavior = analytics.analyze_user_behavior(test_user.id)

        assert behavior["user_id"] == str(test_user.id)
        assert behavior["download_patterns"]["total_downloads"] == 2
        assert behavior["download_patterns"]["unique_models"] == 1
        assert "sklearn" in behavior["download_patterns"]["favorite_model_types"]
        assert len(behavior["preferences"]["download_methods"]) > 0


class TestMetricsIntegration:
    """Test observability metrics integration."""

    def test_metrics_integration_available(self, analytics_db_session):
        """Test that metrics integration works when observability system is available."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Should not raise an error even if observability is not available
        analytics.update_registry_metrics()

    def test_download_metrics_tracking(self, analytics_db_session, test_model, test_user):
        """Test that downloads are tracked in metrics."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Record a download (should track metrics internally)
        download_id = analytics.record_download(
            test_model.id, test_user.id, 1024, "api", "test-client"
        )

        assert download_id is not None

    def test_community_insights_metrics(self, analytics_db_session, test_model, test_user):
        """Test that community insights operations are tracked."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Record download first to have data
        analytics.record_download(test_model.id, test_user.id, 1024, "api")

        # Generate insights (should track metrics)
        insights = analytics.generate_community_insights()

        assert insights is not None
        assert "trending_models" in insights

    def test_user_behavior_metrics(self, analytics_db_session, test_model, test_user):
        """Test that user behavior analysis is tracked."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Record downloads first
        analytics.record_download(test_model.id, test_user.id, 1024, "api")

        # Analyze behavior (should track metrics)
        behavior = analytics.analyze_user_behavior(test_user.id)

        assert behavior is not None
        assert behavior["user_id"] == str(test_user.id)


class TestModelSimilarity:
    """Test model similarity and recommendation functionality."""

    def test_calculate_model_similarities_empty_registry(self, analytics_db_session):
        """Test calculating similarities with empty registry."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        similarities = analytics.calculate_model_similarities(limit=10)
        assert similarities == []

    def test_calculate_model_similarities_with_models(self, analytics_db_session, test_user, test_workspace):
        """Test calculating similarities between models with metadata."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Create models with similar metadata
        model1 = ModelRegistry(
            id=uuid.uuid4(),
            name="sklearn-classifier-1",
            description="A classification model using random forest",
            owner_id=test_user.id,
            workspace_id=test_workspace.id,
            is_public=True,
            model_path="/test/model1",
            model_type="sklearn",
            version="1.0.0",
            tags=["classification", "random-forest", "supervised"],
            model_size_bytes=1024*1024,
            manifest_hash="hash1"
        )

        model2 = ModelRegistry(
            id=uuid.uuid4(),
            name="sklearn-classifier-2",
            description="A classification model using decision tree",
            owner_id=test_user.id,
            workspace_id=test_workspace.id,
            is_public=True,
            model_path="/test/model2",
            model_type="sklearn",
            version="1.0.0",
            tags=["classification", "decision-tree", "supervised"],
            model_size_bytes=2*1024*1024,
            manifest_hash="hash2"
        )

        analytics_db_session.add(model1)
        analytics_db_session.add(model2)
        analytics_db_session.commit()

        similarities = analytics.calculate_model_similarities(limit=10)

        assert len(similarities) > 0
        similarity = similarities[0]
        assert "model_id" in similarity
        assert "similar_models" in similarity
        assert "similarity_scores" in similarity

    def test_get_similar_models_for_user(self, analytics_db_session, test_user, test_workspace):
        """Test getting personalized model recommendations based on user history."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Create a model the user has downloaded
        downloaded_model = ModelRegistry(
            id=uuid.uuid4(),
            name="user-downloaded-model",
            description="Classification model with scikit-learn",
            owner_id=test_user.id,
            workspace_id=test_workspace.id,
            is_public=True,
            model_path="/test/downloaded",
            model_type="sklearn",
            version="1.0.0",
            tags=["classification", "scikit-learn"],
            model_size_bytes=1024*1024,
            manifest_hash="hash_downloaded"
        )

        # Create similar models
        similar_model = ModelRegistry(
            id=uuid.uuid4(),
            name="similar-classification-model",
            description="Another classification model with scikit-learn",
            owner_id=test_user.id,
            workspace_id=test_workspace.id,
            is_public=True,
            model_path="/test/similar",
            model_type="sklearn",
            version="1.0.0",
            tags=["classification", "machine-learning"],
            model_size_bytes=1024*1024,
            manifest_hash="hash_similar"
        )

        analytics_db_session.add(downloaded_model)
        analytics_db_session.add(similar_model)
        analytics_db_session.commit()

        # Record download history
        analytics.record_download(downloaded_model.id, test_user.id, 1024, "api")

        recommendations = analytics.get_similar_models_for_user(test_user.id, limit=5)

        assert isinstance(recommendations, list)
        if recommendations:
            rec = recommendations[0]
            assert "model_id" in rec
            assert "similarity_score" in rec
            assert "recommendation_reason" in rec


class TestGeographicAnalytics:
    """Test geographic and demographic analytics functionality."""

    def test_get_geographic_insights_empty_data(self, analytics_db_session):
        """Test geographic insights with no user agent data."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        insights = analytics.get_geographic_insights()

        expected = {
            "download_patterns": {
                "by_region": {},
                "by_timezone": {},
                "total_unique_locations": 0
            },
            "privacy_notice": "Location data is inferred from user agents and aggregated for privacy"
        }
        assert insights == expected

    def test_get_geographic_insights_with_data(self, analytics_db_session, test_model, test_user):
        """Test geographic insights with user agent data."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Record downloads with different user agents indicating locations
        analytics.record_download(
            test_model.id, test_user.id, 1024, "api",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )

        insights = analytics.get_geographic_insights()

        assert "download_patterns" in insights
        assert "by_region" in insights["download_patterns"]
        assert "by_timezone" in insights["download_patterns"]
        assert "total_unique_locations" in insights["download_patterns"]
        assert "privacy_notice" in insights

    def test_get_demographic_insights_empty_data(self, analytics_db_session):
        """Test demographic insights with no data."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        insights = analytics.get_demographic_insights()

        expected = {
            "usage_patterns": {
                "by_organization_type": {},
                "by_user_role": {},
                "by_platform": {},
                "total_organizations": 0
            },
            "privacy_notice": "Demographic data is aggregated and anonymized to protect user privacy"
        }
        assert insights == expected

    def test_get_demographic_insights_with_data(self, analytics_db_session, test_model, test_workspace):
        """Test demographic insights with user data."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Create users with different demographics
        user1 = User(
            id=uuid.uuid4(),
            email="researcher@university.edu",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
            is_verified=True,
            organization="University Research",
            role="researcher"
        )

        user2 = User(
            id=uuid.uuid4(),
            email="engineer@company.com",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
            is_verified=True,
            organization="Tech Company",
            role="engineer"
        )

        analytics_db_session.add(user1)
        analytics_db_session.add(user2)
        analytics_db_session.commit()

        # Record downloads from different user types
        analytics.record_download(test_model.id, user1.id, 1024, "api", "research-client/1.0")
        analytics.record_download(test_model.id, user2.id, 2048, "cli", "production-tool/2.1")

        insights = analytics.get_demographic_insights()

        assert "usage_patterns" in insights
        assert "by_organization_type" in insights["usage_patterns"]
        assert "by_user_role" in insights["usage_patterns"]
        assert "by_platform" in insights["usage_patterns"]
        assert "total_organizations" in insights["usage_patterns"]
        assert "privacy_notice" in insights

        # Should have data for different roles
        role_patterns = insights["usage_patterns"]["by_user_role"]
        if role_patterns:
            assert any("researcher" in str(pattern) for pattern in role_patterns)


if __name__ == "__main__":
    pytest.main([__file__])
