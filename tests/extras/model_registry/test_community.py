"""Tests for community model management system."""
import pytest
import uuid
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from sqlalchemy.orm import Session

from emuses.tools.community_model_manager import (
    CommunityModelManager,
    CommunityConfig,
    CommunityError,
    PublishingStatus,
    ModelRating,
    ReviewData
)


class TestCommunityModelManager:
    """Tests for CommunityModelManager class."""
    
    @pytest.fixture
    def db_session(self):
        """Mock database session for testing."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def community_config(self):
        """Create CommunityConfig for testing."""
        return CommunityConfig(
            enable_public_publishing=True,
            enable_rating_system=True,
            enable_reviews=True,
            min_rating=1.0,
            max_rating=5.0,
            require_approval=False,
            max_review_length=1000
        )
    
    @pytest.fixture
    def community_manager(self, db_session, community_config):
        """Create CommunityModelManager instance."""
        return CommunityModelManager(db_session, community_config)
    
    def test_community_manager_initialization(self, community_manager):
        """Test CommunityModelManager initialization."""
        assert community_manager.db_session is not None
        assert community_manager.config is not None
        assert isinstance(community_manager.config, CommunityConfig)
    
    def test_publish_model_basic(self, community_manager, db_session):
        """Test basic model publishing functionality."""
        model_id = uuid.uuid4()
        user_id = uuid.uuid4()
        publish_data = {
            "description": "Test model for community",
            "tags": ["test", "machine-learning"],
            "license": "MIT",
            "is_public": True
        }
        
        # Mock database query
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.owner_id = user_id
        mock_model.name = "test_model"
        db_session.query().filter().first.return_value = mock_model
        
        result = community_manager.publish_model(model_id, user_id, publish_data)
        
        assert result["status"] == PublishingStatus.PUBLISHED
        assert result["model_id"] == str(model_id)
        assert result["is_public"] is True
    
    def test_publish_model_unauthorized(self, community_manager, db_session):
        """Test publishing model by unauthorized user."""
        model_id = uuid.uuid4()
        user_id = uuid.uuid4()
        wrong_user_id = uuid.uuid4()
        publish_data = {
            "description": "Test model",
            "is_public": True
        }
        
        # Mock model owned by different user
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.owner_id = user_id  # Different from requester
        db_session.query().filter().first.return_value = mock_model
        
        with pytest.raises(CommunityError):
            community_manager.publish_model(model_id, wrong_user_id, publish_data)
    
    def test_add_model_rating(self, community_manager, db_session):
        """Test adding rating to a model."""
        model_id = uuid.uuid4()
        user_id = uuid.uuid4()
        rating_data = ModelRating(
            rating=4.5,
            comment="Great model!",
            user_id=user_id,
            model_id=model_id
        )
        
        # Mock model exists and is public
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.is_public = True
        db_session.query().filter().first.return_value = mock_model
        
        result = community_manager.add_model_rating(model_id, rating_data)
        
        assert result["success"] is True
        assert result["rating"] == 4.5
        assert "rating_id" in result
    
    def test_get_model_ratings(self, community_manager, db_session):
        """Test retrieving model ratings."""
        model_id = uuid.uuid4()
        
        # Mock ratings data
        mock_ratings = [
            Mock(id=uuid.uuid4(), rating=4.5, comment="Good", created_at=datetime.utcnow()),
            Mock(id=uuid.uuid4(), rating=5.0, comment="Excellent", created_at=datetime.utcnow())
        ]
        db_session.query().filter().all.return_value = mock_ratings
        
        ratings = community_manager.get_model_ratings(model_id)
        
        assert len(ratings) == 2
        assert ratings[0]["rating"] == 4.5
        assert ratings[1]["rating"] == 5.0
    
    def test_discover_community_models(self, community_manager, db_session):
        """Test community model discovery."""
        # Mock query results
        mock_model_1 = Mock()
        mock_model_1.id = uuid.uuid4()
        mock_model_1.name = "Model 1"
        mock_model_1.is_public = True
        mock_model_1.download_count = 100
        
        mock_model_2 = Mock()
        mock_model_2.id = uuid.uuid4()
        mock_model_2.name = "Model 2"
        mock_model_2.is_public = True
        mock_model_2.download_count = 75
        
        mock_models = [mock_model_1, mock_model_2]
        db_session.query().filter().order_by().limit().all.return_value = mock_models
        
        discovered = community_manager.discover_community_models(
            category="machine-learning",
            sort_by="popularity",
            limit=10
        )
        
        assert len(discovered) == 2
        assert discovered[0]["name"] == "Model 1"
        assert discovered[1]["name"] == "Model 2"
    
    def test_get_model_catalog(self, community_manager, db_session):
        """Test getting community model catalog."""
        # Mock catalog data
        mock_owner = Mock()
        mock_owner.username = "test_user"
        
        mock_model = Mock()
        mock_model.id = uuid.uuid4()
        mock_model.name = "Test Model"
        mock_model.description = "Test description"
        mock_model.is_public = True
        mock_model.created_at = datetime.utcnow()
        mock_model.owner = mock_owner
        
        mock_models = [mock_model]
        db_session.query().filter().all.return_value = mock_models
        
        catalog = community_manager.get_model_catalog()
        
        assert len(catalog) == 1
        assert catalog[0]["name"] == "Test Model"
        assert catalog[0]["description"] == "Test description"
    
    def test_add_model_review(self, community_manager, db_session):
        """Test adding a review to a model."""
        model_id = uuid.uuid4()
        review_data = ReviewData(
            title="Excellent Performance",
            content="This model exceeded my expectations. Great accuracy and speed.",
            rating=4.8,
            user_id=uuid.uuid4(),
            model_id=model_id
        )
        
        # Mock model exists and is public
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.is_public = True
        db_session.query().filter().first.return_value = mock_model
        
        result = community_manager.add_model_review(model_id, review_data)
        
        assert result["success"] is True
        assert result["review_title"] == "Excellent Performance"
        assert result["rating"] == 4.8
        assert "review_id" in result
    
    def test_get_model_reviews(self, community_manager, db_session):
        """Test retrieving model reviews."""
        model_id = uuid.uuid4()
        
        # Mock reviews data
        mock_review_1 = Mock()
        mock_review_1.id = uuid.uuid4()
        mock_review_1.title = "Great Model"
        mock_review_1.content = "Works perfectly"
        mock_review_1.rating = 5.0
        mock_review_1.created_at = datetime.utcnow()
        
        mock_review_2 = Mock()
        mock_review_2.id = uuid.uuid4()
        mock_review_2.title = "Good but slow"
        mock_review_2.content = "Accurate but takes time"
        mock_review_2.rating = 3.5
        mock_review_2.created_at = datetime.utcnow()
        
        mock_reviews = [mock_review_1, mock_review_2]
        db_session.query().filter().all.return_value = mock_reviews
        
        reviews = community_manager.get_model_reviews(model_id)
        
        assert len(reviews) == 2
        assert reviews[0]["title"] == "Great Model"
        assert reviews[0]["rating"] == 5.0
        assert reviews[1]["title"] == "Good but slow"
        assert reviews[1]["rating"] == 3.5
    
    def test_calculate_model_rating_average(self, community_manager, db_session):
        """Test calculating average rating for a model."""
        model_id = uuid.uuid4()
        
        # Mock ratings data
        mock_ratings = [
            Mock(rating=4.0),
            Mock(rating=5.0),
            Mock(rating=3.5),
            Mock(rating=4.5)
        ]
        db_session.query().filter().all.return_value = mock_ratings
        
        avg_rating = community_manager.calculate_model_rating_average(model_id)
        
        assert avg_rating == 4.25  # (4.0 + 5.0 + 3.5 + 4.5) / 4


class TestCommunityConfig:
    """Tests for CommunityConfig class."""
    
    def test_default_config(self):
        """Test default community configuration."""
        config = CommunityConfig()
        
        assert config.enable_public_publishing is True
        assert config.enable_rating_system is True
        assert config.enable_reviews is True
        assert config.min_rating == 1.0
        assert config.max_rating == 5.0
        assert config.require_approval is False
        assert config.max_review_length == 500
    
    def test_custom_config(self):
        """Test custom community configuration."""
        config = CommunityConfig(
            enable_public_publishing=False,
            enable_rating_system=False,
            min_rating=0.0,
            max_rating=10.0,
            require_approval=True,
            max_review_length=2000
        )
        
        assert config.enable_public_publishing is False
        assert config.enable_rating_system is False
        assert config.min_rating == 0.0
        assert config.max_rating == 10.0
        assert config.require_approval is True
        assert config.max_review_length == 2000


class TestModelRating:
    """Tests for ModelRating dataclass."""
    
    def test_rating_initialization(self):
        """Test ModelRating initialization."""
        rating = ModelRating(
            rating=4.5,
            comment="Great model",
            user_id=uuid.uuid4(),
            model_id=uuid.uuid4()
        )
        
        assert rating.rating == 4.5
        assert rating.comment == "Great model"
        assert isinstance(rating.user_id, uuid.UUID)
        assert isinstance(rating.model_id, uuid.UUID)
    
    def test_rating_validation(self):
        """Test rating value validation."""
        with pytest.raises(ValueError):
            ModelRating(
                rating=6.0,  # Invalid rating > 5.0
                comment="Test",
                user_id=uuid.uuid4(),
                model_id=uuid.uuid4()
            )


class TestPublishingStatus:
    """Tests for PublishingStatus enum."""
    
    def test_publishing_status_values(self):
        """Test PublishingStatus enum values."""
        assert PublishingStatus.DRAFT.value == "draft"
        assert PublishingStatus.PENDING_APPROVAL.value == "pending_approval"
        assert PublishingStatus.PUBLISHED.value == "published"
        assert PublishingStatus.REJECTED.value == "rejected"


class TestReviewData:
    """Tests for ReviewData dataclass."""
    
    def test_review_data_initialization(self):
        """Test ReviewData initialization."""
        review = ReviewData(
            title="Excellent Model",
            content="This model works perfectly for my use case.",
            rating=5.0,
            user_id=uuid.uuid4(),
            model_id=uuid.uuid4()
        )
        
        assert review.title == "Excellent Model"
        assert review.content == "This model works perfectly for my use case."
        assert review.rating == 5.0
        assert isinstance(review.user_id, uuid.UUID)
        assert isinstance(review.model_id, uuid.UUID)