"""Tests for personalized ranking system."""

import pytest
import uuid
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List, Any

from emuses.extras.advanced_search import AdvancedModelSearch, SearchConfig
from emuses.extras.personalized_ranking import (
    PersonalizedRanker, UserProfile, RankingFeatures, RankingError
)


class TestUserProfile:
    """Test user profile functionality."""
    
    def test_user_profile_init(self):
        """Test user profile initialization."""
        user_id = str(uuid.uuid4())
        profile = UserProfile(user_id=user_id)
        
        assert profile.user_id == user_id
        assert isinstance(profile.preferences, dict)
        assert isinstance(profile.interaction_history, list)
        assert isinstance(profile.model_ratings, dict)
        assert profile.expertise_level == "beginner"
    
    def test_user_profile_with_data(self):
        """Test user profile with initialization data."""
        user_id = str(uuid.uuid4())
        preferences = {"model_type": "classification", "framework": "pytorch"}
        history = [{"model_id": str(uuid.uuid4()), "action": "download"}]
        ratings = {str(uuid.uuid4()): 4.5}
        
        profile = UserProfile(
            user_id=user_id,
            preferences=preferences,
            interaction_history=history,
            model_ratings=ratings,
            expertise_level="intermediate"
        )
        
        assert profile.preferences == preferences
        assert profile.interaction_history == history
        assert profile.model_ratings == ratings
        assert profile.expertise_level == "intermediate"
    
    def test_update_preference(self):
        """Test updating user preferences."""
        profile = UserProfile(user_id=str(uuid.uuid4()))
        
        profile.update_preference("model_type", "classification")
        profile.update_preference("accuracy_importance", 0.8)
        
        assert profile.preferences["model_type"] == "classification"
        assert profile.preferences["accuracy_importance"] == 0.8
    
    def test_add_interaction(self):
        """Test adding interaction to history."""
        profile = UserProfile(user_id=str(uuid.uuid4()))
        model_id = str(uuid.uuid4())
        
        profile.add_interaction(model_id, "download", {"timestamp": "2024-01-01"})
        
        assert len(profile.interaction_history) == 1
        assert profile.interaction_history[0]["model_id"] == model_id
        assert profile.interaction_history[0]["action"] == "download"
        assert profile.interaction_history[0]["metadata"]["timestamp"] == "2024-01-01"
    
    def test_add_rating(self):
        """Test adding model rating."""
        profile = UserProfile(user_id=str(uuid.uuid4()))
        model_id = str(uuid.uuid4())
        
        profile.add_rating(model_id, 4.2)
        
        assert profile.model_ratings[str(model_id)] == 4.2
    
    def test_get_preferred_model_types(self):
        """Test getting preferred model types from interactions."""
        profile = UserProfile(user_id=str(uuid.uuid4()))
        
        # Add interactions with different model types
        profile.add_interaction(str(uuid.uuid4()), "download", {"model_type": "classification"})
        profile.add_interaction(str(uuid.uuid4()), "download", {"model_type": "classification"})
        profile.add_interaction(str(uuid.uuid4()), "view", {"model_type": "regression"})
        
        preferred_types = profile.get_preferred_model_types()
        
        assert isinstance(preferred_types, dict)
        assert "classification" in preferred_types
        assert "regression" in preferred_types
        assert preferred_types["classification"] > preferred_types["regression"]
    
    def test_get_interaction_score(self):
        """Test calculating interaction score for a model."""
        profile = UserProfile(user_id=str(uuid.uuid4()))
        model_id = str(uuid.uuid4())
        
        # Add multiple interactions
        profile.add_interaction(model_id, "view")
        profile.add_interaction(model_id, "download") 
        profile.add_rating(model_id, 4.5)
        
        score = profile.get_interaction_score(str(model_id))
        
        assert isinstance(score, float)
        assert score > 0
    
    def test_get_profile_summary(self):
        """Test getting profile summary."""
        profile = UserProfile(user_id=str(uuid.uuid4()))
        profile.update_preference("model_type", "classification")
        profile.add_interaction(str(uuid.uuid4()), "download")
        profile.add_rating(str(uuid.uuid4()), 4.0)
        
        summary = profile.get_profile_summary()
        
        assert isinstance(summary, dict)
        assert "user_id" in summary
        assert "total_interactions" in summary
        assert "total_ratings" in summary
        assert "expertise_level" in summary
        assert "top_preferences" in summary


class TestRankingFeatures:
    """Test ranking features extraction."""
    
    def test_ranking_features_init(self):
        """Test ranking features initialization."""
        features = RankingFeatures()
        
        assert isinstance(features.feature_weights, dict)
        assert len(features.feature_weights) > 0
    
    def test_extract_model_features(self):
        """Test extracting features from model data."""
        features = RankingFeatures()
        
        model_data = {
            "model_id": str(uuid.uuid4()),
            "name": "neural_network_classifier",
            "model_type": "classification",
            "description": "A neural network for classification tasks",
            "download_count": 150,
            "avg_rating": 4.2,
            "created_at": "2024-01-01T00:00:00"
        }
        
        extracted = features.extract_model_features(model_data)
        
        assert isinstance(extracted, dict)
        assert "model_type_score" in extracted
        assert "popularity_score" in extracted
        assert "quality_score" in extracted
        assert "recency_score" in extracted
        assert "name_relevance" in extracted
        assert extracted["model_type_score"] >= 0
        assert extracted["popularity_score"] >= 0
        assert extracted["quality_score"] >= 0
    
    def test_extract_user_features(self):
        """Test extracting features from user profile."""
        features = RankingFeatures()
        
        profile = UserProfile(user_id=str(uuid.uuid4()))
        profile.update_preference("model_type", "classification")
        profile.update_preference("accuracy_importance", 0.8)
        profile.add_interaction(str(uuid.uuid4()), "download")
        
        extracted = features.extract_user_features(profile)
        
        assert isinstance(extracted, dict)
        assert "expertise_score" in extracted
        assert "activity_level" in extracted
        assert "preference_strength" in extracted
        assert extracted["expertise_score"] >= 0
        assert extracted["activity_level"] >= 0
    
    def test_compute_compatibility_score(self):
        """Test computing compatibility between user and model."""
        features = RankingFeatures()
        
        model_features = {
            "model_type_score": 0.8,
            "popularity_score": 0.7,
            "quality_score": 0.9,
            "recency_score": 0.6
        }
        
        user_features = {
            "expertise_score": 0.5,
            "activity_level": 0.8,
            "preference_strength": 0.7
        }
        
        compatibility = features.compute_compatibility_score(model_features, user_features)
        
        assert isinstance(compatibility, float)
        assert 0.0 <= compatibility <= 1.0
    
    def test_normalize_features(self):
        """Test feature normalization."""
        features = RankingFeatures()
        
        raw_features = {
            "feature1": 100,
            "feature2": 0.5,
            "feature3": -10
        }
        
        normalized = features.normalize_features(raw_features)
        
        assert isinstance(normalized, dict)
        assert all(0.0 <= value <= 1.0 for value in normalized.values())


class TestPersonalizedRanker:
    """Test personalized ranking functionality."""
    
    def test_personalized_ranker_init(self):
        """Test personalized ranker initialization."""
        ranker = PersonalizedRanker()
        
        assert isinstance(ranker.ranking_features, RankingFeatures)
        assert isinstance(ranker.user_profiles, dict)
        assert hasattr(ranker, '_ranking_stats')
    
    def test_get_or_create_user_profile(self):
        """Test getting or creating user profile."""
        ranker = PersonalizedRanker()
        user_id = str(uuid.uuid4())
        
        # First call should create profile
        profile1 = ranker.get_or_create_user_profile(user_id)
        assert isinstance(profile1, UserProfile)
        assert profile1.user_id == user_id
        assert len(ranker.user_profiles) == 1
        
        # Second call should return existing profile
        profile2 = ranker.get_or_create_user_profile(user_id)
        assert profile1 is profile2
        assert len(ranker.user_profiles) == 1
    
    def test_update_user_profile(self):
        """Test updating user profile."""
        ranker = PersonalizedRanker()
        user_id = str(uuid.uuid4())
        
        ranker.update_user_profile(user_id, preferences={"model_type": "regression"})
        
        profile = ranker.user_profiles[user_id]
        assert profile.preferences["model_type"] == "regression"
    
    def test_record_user_interaction(self):
        """Test recording user interaction."""
        ranker = PersonalizedRanker()
        user_id = str(uuid.uuid4())
        model_id = str(uuid.uuid4())
        
        ranker.record_user_interaction(user_id, model_id, "download", {"score": 0.8})
        
        profile = ranker.user_profiles[user_id]
        assert len(profile.interaction_history) == 1
        assert profile.interaction_history[0]["model_id"] == model_id
    
    def test_rank_models_basic(self):
        """Test basic model ranking."""
        ranker = PersonalizedRanker()
        user_id = str(uuid.uuid4())
        
        # Create user profile with preferences
        profile = ranker.get_or_create_user_profile(user_id)
        profile.update_preference("model_type", "classification")
        profile.add_interaction(str(uuid.uuid4()), "download", {"model_type": "classification"})
        
        # Mock search results
        search_results = [
            {
                "model_id": str(uuid.uuid4()),
                "name": "classifier_model",
                "model_type": "classification",
                "score": 0.8,
                "download_count": 100,
                "avg_rating": 4.0
            },
            {
                "model_id": str(uuid.uuid4()),
                "name": "regression_model", 
                "model_type": "regression",
                "score": 0.9,
                "download_count": 50,
                "avg_rating": 3.5
            }
        ]
        
        ranked_results = ranker.rank_models(search_results, user_id)
        
        assert len(ranked_results) == 2
        assert all("personalized_score" in result for result in ranked_results)
        assert all("rank_factors" in result for result in ranked_results)
        # Classification model should rank higher due to user preference
        assert ranked_results[0]["model_type"] == "classification"
    
    def test_rank_models_with_user_context(self):
        """Test model ranking with explicit user context."""
        ranker = PersonalizedRanker()
        
        user_context = {
            "user_id": str(uuid.uuid4()),
            "preferences": {"model_type": "classification", "accuracy_importance": 0.9},
            "expertise_level": "advanced"
        }
        
        search_results = [
            {
                "model_id": str(uuid.uuid4()),
                "name": "simple_classifier",
                "model_type": "classification",
                "score": 0.7,
                "avg_rating": 4.0,
                "complexity": "low"
            },
            {
                "model_id": str(uuid.uuid4()),
                "name": "advanced_classifier",
                "model_type": "classification", 
                "score": 0.8,
                "avg_rating": 4.5,
                "complexity": "high"
            }
        ]
        
        ranked_results = ranker.rank_models_with_context(search_results, user_context)
        
        assert len(ranked_results) == 2
        assert all("personalized_score" in result for result in ranked_results)
        # Advanced user should prefer complex models
        assert "advanced" in ranked_results[0]["name"]
    
    def test_explain_ranking(self):
        """Test ranking explanation generation."""
        ranker = PersonalizedRanker()
        user_id = str(uuid.uuid4())
        
        # Create user profile
        profile = ranker.get_or_create_user_profile(user_id)
        profile.update_preference("model_type", "classification")
        
        model_data = {
            "model_id": str(uuid.uuid4()),
            "name": "test_classifier",
            "model_type": "classification",
            "score": 0.8,
            "personalized_score": 0.85,
            "rank_factors": {
                "type_match": 0.9,
                "quality": 0.8,
                "popularity": 0.7
            }
        }
        
        explanation = ranker.explain_ranking(model_data, user_id)
        
        assert isinstance(explanation, dict)
        assert "ranking_factors" in explanation
        assert "user_preferences" in explanation
        assert "score_breakdown" in explanation
        assert "recommendation_reason" in explanation
    
    def test_get_ranking_stats(self):
        """Test getting ranking statistics."""
        ranker = PersonalizedRanker()
        
        # Perform some ranking operations to generate stats
        user_id = str(uuid.uuid4())
        ranker.get_or_create_user_profile(user_id)
        
        search_results = [{"model_id": str(uuid.uuid4()), "score": 0.8}]
        ranker.rank_models(search_results, user_id)
        
        stats = ranker.get_ranking_stats()
        
        assert isinstance(stats, dict)
        assert "total_rankings" in stats
        assert "unique_users" in stats
        assert "avg_personalization_impact" in stats
        assert "feature_importance" in stats
    
    def test_collaborative_filtering_recommendations(self):
        """Test collaborative filtering recommendations."""
        ranker = PersonalizedRanker()
        
        # Create multiple users with similar preferences
        user1_id = str(uuid.uuid4())
        user2_id = str(uuid.uuid4())
        target_user_id = str(uuid.uuid4())
        
        # User 1 and 2 have similar preferences and interactions
        for user_id in [user1_id, user2_id]:
            profile = ranker.get_or_create_user_profile(user_id)
            profile.update_preference("model_type", "classification")
            profile.add_rating(str(uuid.uuid4()), 4.5)
        
        # Target user has similar but incomplete preferences
        target_profile = ranker.get_or_create_user_profile(target_user_id)
        target_profile.update_preference("model_type", "classification")
        
        recommendations = ranker.get_collaborative_recommendations(target_user_id, max_recommendations=5)
        
        assert isinstance(recommendations, list)
        assert len(recommendations) <= 5
        for rec in recommendations:
            assert "model_id" in rec
            assert "predicted_rating" in rec
            assert "confidence" in rec
    
    def test_diversity_injection(self):
        """Test diversity injection in ranking."""
        ranker = PersonalizedRanker()
        user_id = str(uuid.uuid4())
        
        # Create results that are all very similar
        search_results = []
        for i in range(10):
            search_results.append({
                "model_id": str(uuid.uuid4()),
                "name": f"classifier_{i}",
                "model_type": "classification",
                "score": 0.8 + i * 0.01,
                "personalized_score": 0.85 + i * 0.01
            })
        
        # Rank with diversity injection
        ranked_results = ranker.rank_models(
            search_results, 
            user_id, 
            diversity_factor=0.3
        )
        
        assert len(ranked_results) == 10
        # Check that diversity was considered (not just pure score ordering)
        assert any("diversity_boost" in result.get("rank_factors", {}) for result in ranked_results)
    
    def test_cold_start_handling(self):
        """Test handling of new users (cold start problem)."""
        ranker = PersonalizedRanker()
        new_user_id = str(uuid.uuid4())
        
        # New user with minimal data
        search_results = [
            {
                "model_id": str(uuid.uuid4()),
                "name": "popular_model",
                "score": 0.7,
                "download_count": 1000,
                "avg_rating": 4.5
            },
            {
                "model_id": str(uuid.uuid4()),
                "name": "niche_model",
                "score": 0.9,
                "download_count": 10,
                "avg_rating": 3.8
            }
        ]
        
        ranked_results = ranker.rank_models(search_results, new_user_id)
        
        assert len(ranked_results) == 2
        # For new users, should favor popular/highly-rated models
        assert ranked_results[0]["name"] == "popular_model"
        assert all("cold_start_boost" in result.get("rank_factors", {}) for result in ranked_results)
    
    def test_temporal_decay(self):
        """Test temporal decay in user preferences."""
        ranker = PersonalizedRanker()
        user_id = str(uuid.uuid4())
        
        profile = ranker.get_or_create_user_profile(user_id)
        
        # Add old interaction (should have less weight)
        old_interaction = {
            "model_id": str(uuid.uuid4()),
            "action": "download",
            "timestamp": "2023-01-01T00:00:00",
            "metadata": {"model_type": "regression"}
        }
        profile.interaction_history.append(old_interaction)
        
        # Add recent interaction (should have more weight)
        recent_interaction = {
            "model_id": str(uuid.uuid4()),
            "action": "download", 
            "timestamp": "2024-01-01T00:00:00",
            "metadata": {"model_type": "classification"}
        }
        profile.interaction_history.append(recent_interaction)
        
        # Get preferences with temporal decay
        preferences = ranker._compute_temporal_preferences(profile)
        
        assert isinstance(preferences, dict)
        # Recent preferences should have higher weight
        assert preferences.get("classification", 0) > preferences.get("regression", 0)


@pytest.fixture
def mock_database_session():
    """Mock database session for testing."""
    return Mock()


@pytest.fixture 
def sample_user_context():
    """Sample user context for testing."""
    return {
        "user_id": str(uuid.uuid4()),
        "preferences": {
            "model_type": "classification",
            "accuracy_importance": 0.8,
            "speed_importance": 0.6
        },
        "expertise_level": "intermediate",
        "previous_models": [str(uuid.uuid4()), str(uuid.uuid4())]
    }


class TestPersonalizedSearchIntegration:
    """Test integration of personalized ranking with advanced search."""
    
    def test_search_with_personalization_enabled(self, mock_database_session, sample_user_context):
        """Test search with personalization enabled."""
        config = SearchConfig(enable_personalized_ranking=True)
        search = AdvancedModelSearch(db_session=mock_database_session, config=config)
        
        # Create a user profile with strong classification preference
        user_id = sample_user_context["user_id"]
        
        # Pre-populate user profile with classification interactions
        search.personalized_ranker.update_user_profile(
            user_id=user_id,
            preferences={"model_type": "classification"},
            expertise_level="advanced"
        )
        
        # Add interaction history favoring classification
        for _ in range(3):
            search.personalized_ranker.record_user_interaction(
                user_id, str(uuid.uuid4()), "download", {"model_type": "classification"}
            )
        
        # Mock search results with similar base scores
        mock_results = [
            {
                "model_id": str(uuid.uuid4()),
                "name": "classifier_a",
                "model_type": "classification",
                "score": 0.7,
                "download_count": 50,
                "avg_rating": 4.0
            },
            {
                "model_id": str(uuid.uuid4()),
                "name": "regressor_b", 
                "model_type": "regression",
                "score": 0.8,
                "download_count": 100,
                "avg_rating": 4.2
            }
        ]
        
        with patch.object(search.backend, 'search', return_value=mock_results):
            results = search.search(
                query="machine learning model",
                user_context=sample_user_context
            )
            
            assert len(results) == 2
            assert all("personalized_score" in result for result in results)
            
            # Find the classification model in results
            classification_result = None
            regression_result = None
            for result in results:
                if result["model_type"] == "classification":
                    classification_result = result
                elif result["model_type"] == "regression":
                    regression_result = result
            
            # With strong user preferences, classification should win despite lower base score
            assert classification_result is not None
            assert regression_result is not None
            assert classification_result["personalized_score"] > regression_result["personalized_score"]
    
    def test_semantic_search_with_personalization(self, mock_database_session, sample_user_context):
        """Test semantic search with personalized ranking."""
        config = SearchConfig(enable_semantic_search=True, enable_personalized_ranking=True)
        search = AdvancedModelSearch(db_session=mock_database_session, config=config)
        
        # Mock database models for semantic search
        mock_models = [
            Mock(id=uuid.uuid4(), name="neural_classifier", description="Neural network classifier", 
                 model_type="classification", is_public=True, created_at=None),
            Mock(id=uuid.uuid4(), name="linear_regressor", description="Linear regression model",
                 model_type="regression", is_public=True, created_at=None)
        ]
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_models
        mock_database_session.query.return_value = mock_query
        
        # Mock semantic embeddings
        with patch.object(search.semantic_embeddings, 'generate_embedding') as mock_generate:
            with patch.object(search.semantic_embeddings, 'find_similar_embeddings') as mock_find:
                mock_generate.return_value = np.array([0.1, 0.2, 0.3], dtype=np.float32)
                mock_find.return_value = [(0, 0.8), (1, 0.7)]
                
                results = search.semantic_search(
                    query="neural network classifier",
                    user_context=sample_user_context
                )
                
                assert len(results) == 2
                assert all("semantic_score" in result for result in results)
                assert all("personalized_score" in result for result in results)
                # Classification model should rank higher
                assert results[0]["model_type"] == "classification"
    
    def test_personalization_statistics_integration(self, mock_database_session, sample_user_context):
        """Test personalization statistics integration with search stats."""
        config = SearchConfig(enable_personalized_ranking=True)
        search = AdvancedModelSearch(db_session=mock_database_session, config=config)
        
        mock_results = [{"model_id": str(uuid.uuid4()), "score": 0.8}]
        
        with patch.object(search.backend, 'search', return_value=mock_results):
            search.search(query="test", user_context=sample_user_context)
        
        stats = search.get_search_stats()
        
        assert "personalized_ranking_enabled" in stats
        assert stats["personalized_ranking_enabled"] == True