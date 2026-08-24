"""Analytics accuracy and performance testing - Task 3.7.2b.

This module provides comprehensive testing for ModelAnalytics accuracy and performance,
including large-scale data handling, query performance validation, similarity calculation
efficiency, and real-time streaming capabilities.
"""

import uuid
import time
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from emuses.multi_user_service.models import Base, User, Workspace, ModelRegistry, ModelDownload
from emuses.extras.model_analytics import ModelAnalytics


class TestAnalyticsAccuracy:
    """Test accuracy of analytics calculations and data aggregation."""

    @pytest.fixture
    def analytics_db_engine(self):
        """Create in-memory database for analytics testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def analytics_db_session(self, analytics_db_engine):
        """Create database session for analytics testing."""
        Session = sessionmaker(bind=analytics_db_engine)
        session = Session()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def test_dataset(self, analytics_db_session):
        """Create comprehensive test dataset for accuracy testing."""
        # Create test users
        users = []
        for i in range(20):  # 20 test users
            user = User(
                id=uuid.uuid4(),
                email=f"user_{i}@testorg{i % 5}.com",  # 5 different orgs
                hashed_password="hashed",
                is_active=True,
                is_superuser=False,
                is_verified=True,
                organization=f"TestOrg_{i % 5}",  # 5 organizations
                role=["researcher", "engineer", "student", "admin"][i % 4]  # 4 roles
            )
            users.append(user)
            analytics_db_session.add(user)

        # Create test workspace
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-analytics-workspace",
            description="Analytics testing workspace",
            owner_id=users[0].id,
            storage_path="/test/analytics/path",
            is_active=True
        )
        analytics_db_session.add(workspace)

        # Create test models with different characteristics
        models = []
        model_types = ["sklearn", "tensorflow", "pytorch", "xgboost", "custom"]

        for i in range(50):  # 50 test models
            model = ModelRegistry(
                id=uuid.uuid4(),
                name=f"test-model-{i}",
                description=f"Analytics test model {i} for {model_types[i % len(model_types)]} testing",
                owner_id=users[i % len(users)].id,
                workspace_id=workspace.id,
                is_public=(i % 3 == 0),  # 1/3 public models
                model_path=f"/test/models/model_{i}",
                model_type=model_types[i % len(model_types)],
                version=f"1.{i % 10}.0",
                model_size_bytes=(i + 1) * 1024 * 1024,  # 1MB to 50MB
                manifest_hash=f"hash_{i}",
                tags=["analytics", "testing", model_types[i % len(model_types)], f"category_{i % 10}"],
                created_at=datetime.utcnow() - timedelta(days=i % 30)  # Models created over 30 days
            )
            models.append(model)
            analytics_db_session.add(model)

        analytics_db_session.commit()

        # Create test downloads with realistic patterns
        downloads = []
        download_methods = ["api", "cli", "web", "sdk"]
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124",
            "Mozilla/5.0 (X11; Linux x86_64) Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/14.1.1",
            "python-requests/2.25.1",
            "emuses-cli/1.0.0"
        ]

        # Create download patterns: some models very popular, others rarely downloaded
        for i, model in enumerate(models):
            # Popular models (first 10): 50-200 downloads each
            # Regular models (next 20): 10-50 downloads each
            # Rare models (last 20): 1-10 downloads each
            if i < 10:
                download_count = 50 + (i * 15)  # 50-185 downloads
            elif i < 30:
                download_count = 10 + (i % 20) * 2  # 10-48 downloads
            else:
                download_count = 1 + (i % 10)  # 1-10 downloads

            for j in range(download_count):
                user = users[j % len(users)]
                download = ModelDownload(
                    model_id=model.id,
                    user_id=user.id,
                    downloaded_at=datetime.utcnow() - timedelta(
                        days=j % 60,  # Downloads over 60 days
                        hours=j % 24,
                        minutes=j % 60
                    ),
                    download_size_bytes=model.model_size_bytes,
                    download_method=download_methods[j % len(download_methods)],
                    user_agent=user_agents[j % len(user_agents)]
                )
                downloads.append(download)
                analytics_db_session.add(download)

        analytics_db_session.commit()

        return {
            "users": users,
            "workspace": workspace,
            "models": models,
            "downloads": downloads,
            "expected_totals": {
                "users": len(users),
                "models": len(models),
                "downloads": len(downloads),
                "public_models": len([m for m in models if m.is_public]),
                "private_models": len([m for m in models if not m.is_public])
            }
        }

    def test_download_count_accuracy(self, analytics_db_session, test_dataset):
        """Test accuracy of download count calculations."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Test specific model download counts
        test_model = test_dataset["models"][0]  # First model (most downloads)
        expected_downloads = len([d for d in test_dataset["downloads"] if d.model_id == test_model.id])
        stats = analytics.get_model_stats(test_model.id)

        assert stats["total_downloads"] == expected_downloads
        assert stats["model_id"] == str(test_model.id)

        # Test unique user count accuracy
        unique_users = len(set(d.user_id for d in test_dataset["downloads"] if d.model_id == test_model.id))
        assert stats["unique_users"] == unique_users

        # Test total bytes accuracy
        expected_bytes = sum(
            d.download_size_bytes or 0
            for d in test_dataset["downloads"]
            if d.model_id == test_model.id
        )
        assert stats["total_bytes_downloaded"] == expected_bytes

    def test_popular_models_ranking_accuracy(self, analytics_db_session, test_dataset):
        """Test accuracy of popular models ranking algorithm."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        popular_models = analytics.get_popular_models(limit=10)

        # Verify ranking is correct (most downloads first)
        download_counts = [model["download_count"] for model in popular_models]
        assert download_counts == sorted(download_counts, reverse=True)

        # Verify first model is actually the most downloaded
        most_popular = popular_models[0]

        # Manually count downloads for this model
        model_id = uuid.UUID(most_popular["model_id"])
        actual_downloads = len([
            d for d in test_dataset["downloads"] if d.model_id == model_id
        ])
        assert most_popular["download_count"] == actual_downloads
        assert most_popular["download_count"] >= 50  # Should be a popular model

    def test_time_window_filtering_accuracy(self, analytics_db_session, test_dataset):
        """Test accuracy of time-based filtering for analytics queries."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Test 7-day window
        popular_7d = analytics.get_popular_models(limit=20, days=7)

        # Verify all returned downloads are within 7 days
        cutoff_date = datetime.utcnow() - timedelta(days=7)

        for model_data in popular_7d:
            model_id = uuid.UUID(model_data["model_id"])
            recent_downloads = [
                d for d in test_dataset["downloads"]
                if d.model_id == model_id and d.downloaded_at >= cutoff_date
            ]

            # Download count should match recent downloads only
            assert model_data["download_count"] == len(recent_downloads)

    def test_user_behavior_analysis_accuracy(self, analytics_db_session, test_dataset):
        """Test accuracy of user behavior analysis calculations."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        # Test specific user behavior
        test_user = test_dataset["users"][0]
        user_downloads = [d for d in test_dataset["downloads"] if d.user_id == test_user.id]

        behavior = analytics.analyze_user_behavior(test_user.id)

        # Verify basic counts
        assert behavior["download_patterns"]["total_downloads"] == len(user_downloads)

        unique_models = len(set(d.model_id for d in user_downloads))
        assert behavior["download_patterns"]["unique_models"] == unique_models

        # Verify model type preferences accuracy
        model_type_counts = {}
        for download in user_downloads:
            model = next(m for m in test_dataset["models"] if m.id == download.model_id)
            if model.model_type:
                model_type_counts[model.model_type] = model_type_counts.get(model.model_type, 0) + 1

        # Check top model types match
        if model_type_counts:
            top_types = behavior["preferences"]["model_types"]
            if top_types:
                most_common_type = max(model_type_counts.items(), key=lambda x: x[1])[0]
                assert top_types[0]["type"] == most_common_type

    def test_community_insights_accuracy(self, analytics_db_session, test_dataset):
        """Test accuracy of community insights generation."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        insights = analytics.generate_community_insights(limit=10)

        # Test trending models accuracy
        trending = insights["trending_models"]
        assert isinstance(trending, list)

        # Verify trending models have download activity
        for model_data in trending:
            model_id = uuid.UUID(model_data["model_id"])
            recent_downloads = [
                d for d in test_dataset["downloads"]
                if d.model_id == model_id and d.downloaded_at >= datetime.utcnow() - timedelta(days=30)
            ]
            assert len(recent_downloads) > 0  # Should have recent activity
            assert model_data["recent_downloads"] == len(recent_downloads)

    def test_geographic_insights_privacy_compliance(self, analytics_db_session, test_dataset):
        """Test geographic insights accuracy while maintaining privacy."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        insights = analytics.get_geographic_insights(days=90)

        # Verify structure
        assert "download_patterns" in insights
        assert "by_region" in insights["download_patterns"]
        assert "by_timezone" in insights["download_patterns"]
        assert "privacy_notice" in insights

        # Verify data is aggregated (no specific user identification possible)
        regions = insights["download_patterns"]["by_region"]

        # Should have some geographic categorization
        if regions:
            # Verify regions are generalized categories, not specific locations
            valid_regions = ["North America", "Europe", "Asia-Pacific", "South America", "unknown"]
            for region in regions.keys():
                assert region in valid_regions

    def test_model_similarity_accuracy(self, analytics_db_session, test_dataset):
        """Test accuracy of model similarity calculations."""
        analytics = ModelAnalytics(db_session=analytics_db_session)

        similarities = analytics.calculate_model_similarities(limit=10)

        if similarities:  # Only test if scikit-learn available
            # Test similarity scores are valid
            for similarity_data in similarities:
                scores = similarity_data["similarity_scores"]

                # All scores should be between 0 and 1
                for score in scores:
                    assert 0.0 <= score <= 1.0

                # Scores should be sorted in descending order
                assert scores == sorted(scores, reverse=True)

                # Should not include self-similarity
                model_id = similarity_data["model_id"]
                similar_models = similarity_data["similar_models"]
                assert model_id not in similar_models


class TestAnalyticsPerformance:
    """Test performance characteristics of analytics operations."""

    @pytest.fixture
    def performance_db_engine(self):
        """Create database for performance testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def performance_db_session(self, performance_db_engine):
        """Create database session for performance testing."""
        Session = sessionmaker(bind=performance_db_engine)
        session = Session()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def large_dataset(self, performance_db_session):
        """Create large dataset for performance testing."""
        # Create 100 users
        users = []
        for i in range(100):
            user = User(
                id=uuid.uuid4(),
                email=f"perfuser_{i}@testorg{i % 10}.com",
                hashed_password="hashed",
                is_active=True,
                is_superuser=False,
                is_verified=True,
                organization=f"PerfOrg_{i % 10}",
                role=["researcher", "engineer", "student", "admin", "analyst"][i % 5]
            )
            users.append(user)
            performance_db_session.add(user)

        # Create workspace
        workspace = Workspace(
            id=uuid.uuid4(),
            name="perf-workspace",
            description="Performance testing workspace",
            owner_id=users[0].id,
            storage_path="/test/perf/path",
            is_active=True
        )
        performance_db_session.add(workspace)

        # Create 500 models
        models = []
        model_types = ["sklearn", "tensorflow", "pytorch", "xgboost", "custom", "onnx"]

        for i in range(500):
            model = ModelRegistry(
                id=uuid.uuid4(),
                name=f"perf-model-{i}",
                description=f"Performance test model {i} using {model_types[i % len(model_types)]} framework",
                owner_id=users[i % len(users)].id,
                workspace_id=workspace.id,
                is_public=(i % 4 == 0),  # 1/4 public models
                model_path=f"/test/perf/models/model_{i}",
                model_type=model_types[i % len(model_types)],
                version=f"2.{i % 20}.0",
                model_size_bytes=(i + 1) * 512 * 1024,  # 512KB to 256MB
                manifest_hash=f"perfhash_{i}",
                tags=["performance", "testing", model_types[i % len(model_types)],
                      f"category_{i % 20}", f"subcategory_{i % 50}"],
                created_at=datetime.utcnow() - timedelta(days=i % 90)
            )
            models.append(model)
            performance_db_session.add(model)

        performance_db_session.commit()

        # Create 10,000 downloads (realistic scale)
        downloads = []
        download_methods = ["api", "cli", "web", "sdk", "direct"]
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124",
            "Mozilla/5.0 (X11; Linux x86_64) Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/14.1.1",
            "python-requests/2.25.1",
            "emuses-cli/1.0.0",
            "jupyter-notebook/6.4.0"
        ]

        for i in range(10000):
            model = models[i % len(models)]
            user = users[i % len(users)]

            download = ModelDownload(
                model_id=model.id,
                user_id=user.id,
                downloaded_at=datetime.utcnow() - timedelta(
                    days=i % 120,  # 4 months of data
                    hours=i % 24,
                    minutes=i % 60,
                    seconds=i % 60
                ),
                download_size_bytes=model.model_size_bytes,
                download_method=download_methods[i % len(download_methods)],
                user_agent=user_agents[i % len(user_agents)]
            )
            downloads.append(download)
            performance_db_session.add(download)

        performance_db_session.commit()

        return {
            "users": users,
            "workspace": workspace,
            "models": models,
            "downloads": downloads
        }

    def test_model_stats_query_performance(self, performance_db_session, large_dataset):
        """Test performance of individual model statistics queries."""
        analytics = ModelAnalytics(db_session=performance_db_session)

        # Test performance for popular model (many downloads)
        popular_model = large_dataset["models"][0]  # Should have many downloads

        start_time = time.time()
        stats = analytics.get_model_stats(popular_model.id)
        query_time = time.time() - start_time

        # Should complete within 200ms for single model
        assert query_time < 0.2
        assert stats["total_downloads"] > 0
        print(f"Model stats query took {query_time*1000:.1f}ms for model with {stats['total_downloads']} downloads")

    def test_popular_models_query_performance(self, performance_db_session, large_dataset):
        """Test performance of popular models ranking queries."""
        analytics = ModelAnalytics(db_session=performance_db_session)

        # Test different limit sizes
        limits = [10, 50, 100]

        for limit in limits:
            start_time = time.time()
            popular = analytics.get_popular_models(limit=limit)
            query_time = time.time() - start_time

            # Should scale well with limit size
            expected_max_time = 0.1 + (limit / 1000)  # Base time + scaling factor
            assert query_time < expected_max_time
            assert len(popular) <= limit
            print(f"Popular models query (limit={limit}) took {query_time*1000:.1f}ms")

    def test_time_filtered_query_performance(self, performance_db_session, large_dataset):
        """Test performance of time-filtered analytics queries."""
        analytics = ModelAnalytics(db_session=performance_db_session)

        # Test different time windows
        time_windows = [7, 30, 90]

        for days in time_windows:
            start_time = time.time()
            popular = analytics.get_popular_models(limit=20, days=days)
            query_time = time.time() - start_time

            # Time-filtered queries should complete within 300ms
            assert query_time < 0.3
            assert isinstance(popular, list)
            print(f"Time-filtered query ({days} days) took {query_time*1000:.1f}ms")

    def test_user_behavior_analysis_performance(self, performance_db_session, large_dataset):
        """Test performance of user behavior analysis."""
        analytics = ModelAnalytics(db_session=performance_db_session)

        # Test users with different download volumes
        test_users = large_dataset["users"][:10]  # Test 10 users

        total_time = 0
        for user in test_users:
            start_time = time.time()
            behavior = analytics.analyze_user_behavior(user.id, days=90)
            query_time = time.time() - start_time
            total_time += query_time

            # Individual user analysis should complete within 100ms
            assert query_time < 0.1
            assert behavior["user_id"] == str(user.id)

        avg_time = total_time / len(test_users)
        print(f"User behavior analysis averaged {avg_time*1000:.1f}ms per user")

    def test_community_insights_performance(self, performance_db_session, large_dataset):
        """Test performance of community insights generation."""
        analytics = ModelAnalytics(db_session=performance_db_session)

        start_time = time.time()
        insights = analytics.generate_community_insights(limit=20, days=30)
        query_time = time.time() - start_time

        # Complex community insights should complete within 500ms
        assert query_time < 0.5
        assert "trending_models" in insights
        assert "recommended_models" in insights
        print(f"Community insights generation took {query_time*1000:.1f}ms")

    def test_similarity_calculation_performance(self, performance_db_session, large_dataset):
        """Test performance of model similarity calculations."""
        analytics = ModelAnalytics(db_session=performance_db_session)

        # Test with subset of models for realistic performance testing
        start_time = time.time()
        similarities = analytics.calculate_model_similarities(limit=20)
        calc_time = time.time() - start_time

        # Similarity calculation can be expensive, allow up to 2 seconds
        assert calc_time < 2.0

        if similarities:  # Only if sklearn available
            assert len(similarities) <= 20
            print(f"Similarity calculation took {calc_time*1000:.1f}ms for {len(similarities)} models")
        else:
            print("Similarity calculation skipped (sklearn not available)")

    def test_concurrent_analytics_performance(self, performance_db_session, large_dataset):
        """Test analytics performance under concurrent load."""
        # Note: SQLite has thread safety limitations in testing
        # This test validates sequential performance under load
        analytics = ModelAnalytics(db_session=performance_db_session)

        def run_analytics_operation():
            try:
                # Mix of different operations (sequential execution due to SQLite limitations)
                popular = analytics.get_popular_models(limit=10)
                insights = analytics.generate_community_insights(limit=5, days=30)
                return len(popular) + len(insights.get("trending_models", []))
            except Exception:
                return -1  # Error indicator

        # Run operations sequentially but measure performance
        start_time = time.time()
        results = []
        for i in range(10):
            result = run_analytics_operation()
            results.append(result)
        total_time = time.time() - start_time

        # All operations should succeed
        assert all(result >= 0 for result in results)

        # Total time should be reasonable for 10 sequential operations
        assert total_time < 3.0  # 10 operations in under 3 seconds
        print(f"10 sequential analytics operations completed in {total_time*1000:.1f}ms")

    def test_memory_efficiency_large_dataset(self, performance_db_session, large_dataset):
        """Test memory efficiency with large datasets."""
        analytics = ModelAnalytics(db_session=performance_db_session)

        # Test operations that could potentially load large amounts of data
        operations = [
            lambda: analytics.get_popular_models(limit=100),
            lambda: analytics.generate_community_insights(limit=50, days=60),
            lambda: analytics.get_geographic_insights(days=90),
            lambda: analytics.get_demographic_insights(days=90)
        ]

        for i, operation in enumerate(operations):
            start_time = time.time()
            result = operation()
            exec_time = time.time() - start_time

            # All operations should complete efficiently
            assert exec_time < 1.0
            assert result is not None
            print(f"Operation {i+1} completed in {exec_time*1000:.1f}ms")


class TestAnalyticsStreaming:
    """Test real-time streaming analytics capabilities."""

    @pytest.fixture
    def streaming_db_engine(self):
        """Create database for streaming tests."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def streaming_db_session(self, streaming_db_engine):
        """Create database session for streaming tests."""
        Session = sessionmaker(bind=streaming_db_engine)
        session = Session()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def streaming_test_data(self, streaming_db_session):
        """Create minimal test data for streaming tests."""
        user = User(
            id=uuid.uuid4(),
            email="streaming@test.com",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
            is_verified=True,
            organization="Streaming Test Org",
            role="researcher"
        )
        streaming_db_session.add(user)

        workspace = Workspace(
            id=uuid.uuid4(),
            name="streaming-workspace",
            description="Streaming test workspace",
            owner_id=user.id,
            storage_path="/test/streaming/path",
            is_active=True
        )
        streaming_db_session.add(workspace)

        model = ModelRegistry(
            id=uuid.uuid4(),
            name="streaming-test-model",
            description="Model for streaming analytics tests",
            owner_id=user.id,
            workspace_id=workspace.id,
            is_public=True,
            model_path="/test/streaming/model",
            model_type="sklearn",
            version="1.0.0",
            model_size_bytes=1024*1024,
            manifest_hash="streaminghash"
        )
        streaming_db_session.add(model)
        streaming_db_session.commit()

        return {"user": user, "workspace": workspace, "model": model}

    def test_analytics_initialization_with_streaming(self, streaming_db_session):
        """Test ModelAnalytics initialization with streaming enabled."""
        # Test streaming initialization works
        analytics = ModelAnalytics(db_session=streaming_db_session, enable_streaming=True)

        assert analytics.db_session == streaming_db_session
        # Streaming should be available since dependencies exist
        assert analytics.streamer is not None  # Streaming system should be initialized

    def test_download_recording_performance(self, streaming_db_session, streaming_test_data):
        """Test performance of download recording with potential streaming."""
        analytics = ModelAnalytics(db_session=streaming_db_session, enable_streaming=True)

        model = streaming_test_data["model"]
        user = streaming_test_data["user"]

        # Test rapid download recording
        download_count = 100
        start_time = time.time()

        for i in range(download_count):
            download_id = analytics.record_download(
                model_id=model.id,
                user_id=user.id,
                download_size_bytes=1024 * (i + 1),
                download_method="api",
                user_agent="performance-test/1.0"
            )
            assert download_id is not None

        total_time = time.time() - start_time

        # Should handle 100 downloads in under 2 seconds
        assert total_time < 2.0

        # Verify all downloads were recorded
        stats = analytics.get_model_stats(model.id)
        assert stats["total_downloads"] == download_count
        print(f"Recorded {download_count} downloads in {total_time*1000:.1f}ms")

    def test_streaming_graceful_degradation(self, streaming_db_session, streaming_test_data):
        """Test that analytics work correctly when streaming fails."""
        analytics = ModelAnalytics(db_session=streaming_db_session, enable_streaming=True)

        # Even if streaming is enabled but fails, core analytics should work
        model = streaming_test_data["model"]
        user = streaming_test_data["user"]

        # Record download (streaming should fail gracefully)
        download_id = analytics.record_download(
            model_id=model.id,
            user_id=user.id,
            download_size_bytes=2048,
            download_method="cli"
        )

        assert download_id is not None

        # Analytics should still work
        stats = analytics.get_model_stats(model.id)
        assert stats["total_downloads"] > 0

        # Community insights should work
        insights = analytics.generate_community_insights(limit=5)
        assert "trending_models" in insights


if __name__ == "__main__":
    pytest.main([__file__])
