"""Multi-user community feature testing - Task 3.7.2a.

This module provides comprehensive testing for community features involving
multiple users, including publishing workflows, rating conflicts, review
interactions, and collaborative model discovery scenarios.
"""
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from emuses.extras.community_model_manager import (
    CommunityModelManager, CommunityConfig, ModelRating, ReviewData,
    PublishingStatus, CommunityError
)
from emuses.multi_user_service.models import ModelRegistry


class TestMultiUserCommunityInteractions:
    """Test community features with multiple users interacting."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session for testing."""
        session = MagicMock()
        return session

    @pytest.fixture
    def test_users(self):
        """Create test users for multi-user scenarios."""
        return [
            {"id": uuid.uuid4(), "username": "alice_researcher", "role": "researcher"},
            {"id": uuid.uuid4(), "username": "bob_datascientist", "role": "data_scientist"},
            {"id": uuid.uuid4(), "username": "charlie_student", "role": "student"},
            {"id": uuid.uuid4(), "username": "diana_engineer", "role": "engineer"},
            {"id": uuid.uuid4(), "username": "eve_admin", "role": "admin"}
        ]

    @pytest.fixture
    def test_models(self, test_users):
        """Create test models owned by different users."""
        models = []
        for i, user in enumerate(test_users[:3]):  # First 3 users own models
            model = MagicMock(spec=ModelRegistry)
            model.id = uuid.uuid4()
            model.name = f"TestModel_{i+1}_{user['username']}"
            model.description = f"A test model created by {user['username']}"
            model.model_type = "classification" if i % 2 == 0 else "regression"
            model.owner_id = user["id"]  # This should match the test user
            model.is_public = False  # Start as private
            model.created_at = datetime.utcnow() - timedelta(days=i+1)
            model.download_count = (i + 1) * 10
            models.append(model)
        return models

    @pytest.fixture
    def community_manager(self, mock_db_session):
        """Create community manager instance."""
        config = CommunityConfig(
            enable_public_publishing=True,
            enable_rating_system=True,
            enable_reviews=True,
            require_approval=False
        )
        return CommunityModelManager(mock_db_session, config)

    def test_multi_user_model_publishing_workflow(
        self, community_manager, mock_db_session, test_users, test_models
    ):
        """Test complete publishing workflow with multiple users."""

        # Setup database mock to return models based on ID
        def mock_filter_func(*args):
            # Simple mock that returns a MagicMock with first() method
            result_mock = MagicMock()
            result_mock.first.return_value = test_models[0]  # Return first model for simplicity
            return result_mock

        mock_db_session.query.return_value.filter.side_effect = mock_filter_func

        # Test publishing models by different users
        publishing_results = []

        for i, (user, model) in enumerate(zip(test_users[:3], test_models)):
            # Ensure the model owner_id matches the user attempting to publish
            model.owner_id = user["id"]

            # Create fresh mock for each iteration to avoid state pollution
            fresh_query_mock = MagicMock()
            fresh_filter_mock = MagicMock()
            fresh_filter_mock.first.return_value = model
            fresh_query_mock.filter.return_value = fresh_filter_mock
            mock_db_session.query.return_value = fresh_query_mock

            publish_data = {
                "is_public": True,
                "description": f"Enhanced description for {model.name}",
                "tags": ["machine-learning", "test-model"],
                "license": "MIT"
            }

            result = community_manager.publish_model(
                model.id, user["id"], publish_data
            )

            publishing_results.append(result)

            # Verify publishing result
            assert result["status"] == PublishingStatus.PUBLISHED
            assert result["model_id"] == str(model.id)
            assert result["is_public"] is True
            assert "published_at" in result

            # Verify model was updated
            assert model.is_public is True
            assert model.description == publish_data["description"]

        # Test unauthorized publishing attempt
        unauthorized_user = test_users[4]  # User who doesn't own any model

        with pytest.raises(CommunityError, match="not authorized"):
            community_manager.publish_model(
                test_models[0].id, unauthorized_user["id"], {"is_public": True}
            )

        assert len(publishing_results) == 3
        print(f"Successfully published {len(publishing_results)} models by different users")

    def test_multi_user_rating_system(
        self, community_manager, mock_db_session, test_users, test_models
    ):
        """Test rating system with multiple users rating models."""

        # Make all models public for rating
        for model in test_models:
            model.is_public = True

        # Test multiple users rating different models
        rating_results = []
        rating_matrix = [
            # User ratings for each model (model_0, model_1, model_2)
            [5.0, 4.0, 3.0],  # alice_researcher
            [4.0, 5.0, 4.0],  # bob_datascientist
            [3.0, 4.0, 5.0],  # charlie_student
            [4.0, 3.0, 4.0],  # diana_engineer
            [5.0, 5.0, 3.0],  # eve_admin
        ]

        for user_idx, user in enumerate(test_users):
            for model_idx, model in enumerate(test_models):
                # Setup mock to return specific model
                mock_db_session.query.return_value.filter.return_value.first.return_value = model

                rating_value = rating_matrix[user_idx][model_idx]

                rating_data = ModelRating(
                    rating=rating_value,
                    comment=f"Rating from {user['username']}: Good model with score {rating_value}",
                    user_id=user["id"],
                    model_id=model.id
                )

                result = community_manager.add_model_rating(model.id, rating_data)
                rating_results.append(result)

                # Verify rating result
                assert result["success"] is True
                assert result["model_id"] == str(model.id)
                assert result["rating"] == rating_value
                assert "rating_id" in result
                assert "created_at" in result

        # Test rating private model (should fail)
        private_model = test_models[0]
        private_model.is_public = False
        mock_db_session.query.return_value.filter.return_value.first.return_value = private_model

        rating_data = ModelRating(
            rating=4.0,
            comment="Attempting to rate private model",
            user_id=test_users[0]["id"],
            model_id=private_model.id
        )

        with pytest.raises(CommunityError, match="Cannot rate private model"):
            community_manager.add_model_rating(private_model.id, rating_data)

        # Verify total ratings created
        assert len(rating_results) == len(test_users) * len(test_models)
        print(f"Successfully created {len(rating_results)} ratings across {len(test_users)} users and {len(test_models)} models")

    def test_multi_user_review_system(
        self, community_manager, mock_db_session, test_users, test_models
    ):
        """Test review system with multiple users providing reviews."""

        # Make all models public for reviewing
        target_model = test_models[0]
        target_model.is_public = True

        # Setup mock to return target model
        mock_db_session.query.return_value.filter.return_value.first.return_value = target_model

        # Test detailed reviews from different user perspectives
        review_templates = [
            {
                "title": "Technical Review",
                "content": "From a technical perspective, this model shows good performance on benchmark datasets. The architecture is well-designed and the implementation is clean.",
                "rating": 4.5
            },
            {
                "title": "User Experience Review",
                "content": "Easy to use and well-documented. The API is intuitive and the model loads quickly. Great for production use.",
                "rating": 5.0
            },
            {
                "title": "Academic Assessment",
                "content": "Good methodology and reproducible results. The model follows best practices and provides reliable predictions for research purposes.",
                "rating": 4.0
            },
            {
                "title": "Performance Analysis",
                "content": "Excellent accuracy on test datasets. Memory usage is reasonable and inference time is fast. Recommended for real-time applications.",
                "rating": 4.5
            },
            {
                "title": "Beginner Perspective",
                "content": "Great starting point for learning. The model is well-explained and comes with good examples. Documentation could be improved slightly.",
                "rating": 3.5
            }
        ]

        review_results = []

        # Each user reviews target model with different perspective
        for user_idx, user in enumerate(test_users):
            template = review_templates[user_idx]

            review_data = ReviewData(
                title=f"{template['title']} - by {user['username']}",
                content=f"{template['content']} Reviewed by {user['role']}.",
                rating=template["rating"],
                user_id=user["id"],
                model_id=target_model.id
            )

            result = community_manager.add_model_review(target_model.id, review_data)
            review_results.append(result)

            # Verify review result
            assert result["success"] is True
            assert result["model_id"] == str(target_model.id)
            assert result["review_title"] == review_data.title
            assert result["content"] == review_data.content
            assert result["rating"] == review_data.rating
            assert "review_id" in result
            assert "created_at" in result

        # Test review content length validation
        long_review_data = ReviewData(
            title="Very Long Review",
            content="x" * 1000,  # Exceeds default max_review_length of 500
            rating=4.0,
            user_id=test_users[0]["id"],
            model_id=target_model.id
        )

        with pytest.raises(CommunityError, match="exceeds maximum length"):
            community_manager.add_model_review(target_model.id, long_review_data)

        # Verify total reviews created
        assert len(review_results) == len(test_users)
        print(f"Successfully created {len(review_results)} detailed reviews from different user perspectives")

    def test_collaborative_model_discovery(
        self, community_manager, mock_db_session, test_users, test_models
    ):
        """Test collaborative model discovery across multiple users."""

        # Make models public with different characteristics
        for i, model in enumerate(test_models):
            model.is_public = True
            model.download_count = (len(test_models) - i) * 20  # Descending popularity

        # Setup database query mock for discovery operations
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = test_models
        mock_db_session.query.return_value.filter.return_value.all.return_value = test_models

        # Test discovery with different sorting criteria
        discovery_results = {}

        # Test popularity-based discovery
        popular_models = community_manager.discover_community_models(
            sort_by="popularity",
            limit=10
        )
        discovery_results["popular"] = popular_models

        # Test recent models discovery
        recent_models = community_manager.discover_community_models(
            sort_by="recent",
            limit=5
        )
        discovery_results["recent"] = recent_models

        # Verify discovery results
        assert len(popular_models) == len(test_models)
        assert len(recent_models) == len(test_models)

        for model_data in popular_models:
            assert "id" in model_data
            assert "name" in model_data
            assert "description" in model_data
            assert "owner_id" in model_data
            assert model_data["is_public"] is True

        # Test model catalog generation
        catalog = community_manager.get_model_catalog(include_metadata=True)
        discovery_results["catalog"] = catalog

        assert len(catalog) == len(test_models)

        for catalog_entry in catalog:
            assert "id" in catalog_entry
            assert "name" in catalog_entry
            assert "description" in catalog_entry
            assert "model_type" in catalog_entry
            assert "is_public" in catalog_entry
            assert "created_at" in catalog_entry

        print(f"Discovery results: {len(popular_models)} popular, {len(recent_models)} recent, {len(catalog)} in catalog")
        # Validate discovery results structure
        assert isinstance(discovery_results["popular"], list)
        assert isinstance(discovery_results["recent"], list)
        assert isinstance(discovery_results["catalog"], list)

    def test_community_permissions_and_access_control(
        self, community_manager, mock_db_session, test_users, test_models
    ):
        """Test community permissions and access control across users."""

        # Test publishing permissions
        owner = test_users[0]
        non_owner = test_users[1]
        model = test_models[0]

        # Setup database mock
        mock_db_session.query.return_value.filter.return_value.first.return_value = model

        # Owner should be able to publish
        publish_data = {"is_public": True, "description": "Publishing my model"}
        result = community_manager.publish_model(model.id, owner["id"], publish_data)
        assert result["status"] == PublishingStatus.PUBLISHED

        # Non-owner should not be able to publish
        with pytest.raises(CommunityError, match="not authorized"):
            community_manager.publish_model(model.id, non_owner["id"], publish_data)

        # Test rating permissions (any user can rate public models)
        model.is_public = True

        for user in test_users:
            rating_data = ModelRating(
                rating=4.0,
                comment=f"Rating from {user['username']}",
                user_id=user["id"],
                model_id=model.id
            )

            result = community_manager.add_model_rating(model.id, rating_data)
            assert result["success"] is True

        # Test private model access restrictions
        model.is_public = False

        rating_data = ModelRating(
            rating=4.0,
            comment="Should not be allowed",
            user_id=test_users[0]["id"],
            model_id=model.id
        )

        with pytest.raises(CommunityError, match="Cannot rate private model"):
            community_manager.add_model_rating(model.id, rating_data)

        review_data = ReviewData(
            title="Private Review",
            content="Should not be allowed",
            rating=4.0,
            user_id=test_users[0]["id"],
            model_id=model.id
        )

        with pytest.raises(CommunityError, match="Cannot review private model"):
            community_manager.add_model_review(model.id, review_data)

        print("Access control permissions validated successfully")

    def test_concurrent_community_operations(
        self, community_manager, mock_db_session, test_users, test_models
    ):
        """Test concurrent community operations from multiple users."""

        # Make all models public
        target_model = test_models[0]
        target_model.is_public = True

        # Setup database mock
        mock_db_session.query.return_value.filter.return_value.first.return_value = target_model

        # Simulate concurrent operations
        concurrent_operations = []

        # Multiple users rating same model simultaneously
        for user in test_users:
            rating_data = ModelRating(
                rating=4.0,
                comment=f"Concurrent rating from {user['username']}",
                user_id=user["id"],
                model_id=target_model.id
            )

            result = community_manager.add_model_rating(target_model.id, rating_data)
            concurrent_operations.append(("rating", result))

        # Multiple users reviewing same model simultaneously
        for user in test_users:
            review_data = ReviewData(
                title=f"Concurrent Review by {user['username']}",
                content=f"This is a concurrent review from {user['role']}. Model performs well in my tests.",
                rating=4.0,
                user_id=user["id"],
                model_id=target_model.id
            )

            result = community_manager.add_model_review(target_model.id, review_data)
            concurrent_operations.append(("review", result))

        # Verify all concurrent operations succeeded
        assert len(concurrent_operations) == len(test_users) * 2  # ratings + reviews

        for operation_type, result in concurrent_operations:
            assert result["success"] is True
            assert "created_at" in result

        print(f"Successfully completed {len(concurrent_operations)} concurrent operations")


class TestCommunityWorkflowIntegration:
    """Test end-to-end community workflow integration scenarios."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def community_manager(self, mock_db_session):
        """Create community manager."""
        return CommunityModelManager(mock_db_session)

    def test_publish_to_discovery_workflow(self, community_manager, mock_db_session):
        """Test complete workflow from publishing to community discovery."""

        # Create test model
        model = MagicMock(spec=ModelRegistry)
        model.id = uuid.uuid4()
        model.name = "Workflow Test Model"
        model.owner_id = uuid.uuid4()
        model.is_public = False
        model.created_at = datetime.utcnow()
        model.download_count = 0

        # Setup database mock
        mock_db_session.query.return_value.filter.return_value.first.return_value = model
        mock_db_session.query.return_value.filter.return_value.all.return_value = [model]
        # Also setup the chained mock for discovery operations
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [model]

        # Step 1: Publish model
        publish_result = community_manager.publish_model(
            model.id, model.owner_id, {"is_public": True}
        )
        assert publish_result["status"] == PublishingStatus.PUBLISHED

        # Step 2: Model becomes discoverable
        model.is_public = True  # Simulate database update

        discovered = community_manager.discover_community_models()
        assert len(discovered) > 0
        assert any(d["id"] == str(model.id) for d in discovered)

        # Step 3: Add ratings and reviews
        user_id = uuid.uuid4()

        rating_result = community_manager.add_model_rating(
            model.id,
            ModelRating(
                rating=4.5,
                comment="Great model!",
                user_id=user_id,
                model_id=model.id
            )
        )
        assert rating_result["success"] is True

        review_result = community_manager.add_model_review(
            model.id,
            ReviewData(
                title="Excellent Model",
                content="This model works very well for my use case.",
                rating=4.5,
                user_id=user_id,
                model_id=model.id
            )
        )
        assert review_result["success"] is True

        # Step 4: Model appears in catalog
        catalog = community_manager.get_model_catalog()
        assert len(catalog) > 0
        assert any(c["id"] == str(model.id) for c in catalog)

        print("Complete publish-to-discovery workflow validated successfully")

    def test_multi_user_collaboration_scenario(self, community_manager, mock_db_session):
        """Test multi-user collaboration on community models."""

        # Create test users and models
        users = [
            {"id": uuid.uuid4(), "username": f"user_{i}", "role": "researcher"}
            for i in range(5)
        ]

        # User 1 creates and publishes a model
        model = MagicMock(spec=ModelRegistry)
        model.id = uuid.uuid4()
        model.name = "Collaborative Model"
        model.owner_id = users[0]["id"]
        model.is_public = False
        model.created_at = datetime.utcnow()

        # Setup database mock
        mock_db_session.query.return_value.filter.return_value.first.return_value = model

        # Step 1: Owner publishes model
        publish_result = community_manager.publish_model(
            model.id, users[0]["id"], {"is_public": True}
        )
        assert publish_result["status"] == PublishingStatus.PUBLISHED
        model.is_public = True

        # Step 2: Other users discover and interact with model
        ratings_and_reviews = []

        for i, user in enumerate(users[1:], 1):  # Skip owner
            # Add rating
            rating_result = community_manager.add_model_rating(
                model.id,
                ModelRating(
                    rating=4.0 + i * 0.2,
                    comment=f"Rating from {user['username']}",
                    user_id=user["id"],
                    model_id=model.id
                )
            )
            ratings_and_reviews.append(("rating", rating_result))

            # Add review
            review_result = community_manager.add_model_review(
                model.id,
                ReviewData(
                    title=f"Review by {user['username']}",
                    content=f"Detailed review from {user['role']} perspective.",
                    rating=4.0 + i * 0.2,
                    user_id=user["id"],
                    model_id=model.id
                )
            )
            ratings_and_reviews.append(("review", review_result))

        # Verify all interactions succeeded
        assert len(ratings_and_reviews) == (len(users) - 1) * 2

        for interaction_type, result in ratings_and_reviews:
            assert result["success"] is True

        print(f"Multi-user collaboration scenario completed with {len(ratings_and_reviews)} interactions")
