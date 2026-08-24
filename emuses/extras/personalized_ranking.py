"""Personalized ranking system for model search results.

This module provides personalized ranking capabilities that adapt search results
based on user preferences, interaction history, and contextual factors.
"""

import json
import time
import uuid
import hashlib
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from collections import defaultdict, Counter

try:
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.preprocessing import MinMaxScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from emuses.observability.metrics import get_metrics_registry


class RankingError(Exception):
    """Exception raised for ranking system errors."""
    pass


@dataclass
class UserProfile:
    """User profile for personalized ranking.
    
    Stores user preferences, interaction history, and derived insights
    for personalizing search results and recommendations.
    
    Attributes
    ----------
    user_id : str
        Unique identifier for the user
    preferences : Dict[str, Any]
        User preferences and settings
    interaction_history : List[Dict[str, Any]]
        History of user interactions with models
    model_ratings : Dict[str, float]
        User ratings for specific models
    expertise_level : str
        User's assessed expertise level
    created_at : datetime
        Profile creation timestamp
    updated_at : datetime
        Last profile update timestamp
    """
    user_id: str
    preferences: Dict[str, Any] = field(default_factory=dict)
    interaction_history: List[Dict[str, Any]] = field(default_factory=list)
    model_ratings: Dict[str, float] = field(default_factory=dict)
    expertise_level: str = "beginner"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def update_preference(self, key: str, value: Any) -> None:
        """Update user preference.
        
        Parameters
        ----------
        key : str
            Preference key
        value : Any
            Preference value
        """
        self.preferences[key] = value
        self.updated_at = datetime.utcnow()
    
    def add_interaction(self, model_id: str, action: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add user interaction to history.
        
        Parameters
        ----------
        model_id : str
            ID of the model interacted with
        action : str
            Type of interaction (view, download, rate, etc.)
        metadata : Dict[str, Any], optional
            Additional interaction metadata
        """
        interaction = {
            "model_id": model_id,
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        self.interaction_history.append(interaction)
        self.updated_at = datetime.utcnow()
    
    def add_rating(self, model_id: Union[str, uuid.UUID], rating: float) -> None:
        """Add or update model rating.
        
        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the model to rate
        rating : float
            Rating value (typically 1-5)
        """
        self.model_ratings[str(model_id)] = rating
        self.updated_at = datetime.utcnow()
    
    def get_preferred_model_types(self) -> Dict[str, float]:
        """Get preferred model types based on interaction history.
        
        Returns
        -------
        Dict[str, float]
            Model types with preference scores
        """
        type_interactions = defaultdict(float)
        
        for interaction in self.interaction_history:
            model_type = interaction.get("metadata", {}).get("model_type")
            if model_type:
                # Weight different actions differently
                action_weight = {
                    "view": 1.0,
                    "download": 3.0,
                    "rate": 2.0,
                    "bookmark": 1.5
                }.get(interaction["action"], 1.0)
                
                type_interactions[model_type] += action_weight
        
        # Normalize scores
        if type_interactions:
            max_score = max(type_interactions.values())
            return {k: v / max_score for k, v in type_interactions.items()}
        
        return {}
    
    def get_interaction_score(self, model_id: str) -> float:
        """Calculate interaction score for a specific model.
        
        Parameters
        ----------
        model_id : str
            ID of the model
            
        Returns
        -------
        float
            Interaction score for the model
        """
        score = 0.0
        
        # Score from interactions
        for interaction in self.interaction_history:
            if interaction["model_id"] == model_id:
                action_scores = {
                    "view": 0.1,
                    "download": 0.5,
                    "rate": 0.3,
                    "bookmark": 0.2
                }
                score += action_scores.get(interaction["action"], 0.1)
        
        # Score from ratings
        if model_id in self.model_ratings:
            score += self.model_ratings[model_id] / 5.0  # Normalize to 0-1
        
        return min(score, 1.0)
    
    def get_profile_summary(self) -> Dict[str, Any]:
        """Get profile summary statistics.
        
        Returns
        -------
        Dict[str, Any]
            Profile summary
        """
        return {
            "user_id": self.user_id,
            "total_interactions": len(self.interaction_history),
            "total_ratings": len(self.model_ratings),
            "expertise_level": self.expertise_level,
            "top_preferences": dict(list(self.preferences.items())[:5]),
            "preferred_model_types": self.get_preferred_model_types(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class RankingFeatures:
    """Feature extraction and computation for ranking models.
    
    Extracts various features from models and users to compute
    personalized ranking scores.
    """
    
    def __init__(self):
        """Initialize ranking features with default weights."""
        self.feature_weights = {
            "type_preference": 0.25,
            "quality_score": 0.20,
            "popularity_score": 0.15,
            "recency_score": 0.10,
            "interaction_score": 0.15,
            "complexity_match": 0.10,
            "diversity_boost": 0.05
        }
    
    def extract_model_features(self, model_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract features from model data.
        
        Parameters
        ----------
        model_data : Dict[str, Any]
            Model information
            
        Returns
        -------
        Dict[str, float]
            Extracted model features
        """
        features = {}
        
        # Model type relevance (will be computed against user preferences)
        features["model_type_score"] = 1.0 if model_data.get("model_type") else 0.5
        
        # Popularity score based on downloads
        download_count = model_data.get("download_count", 0)
        features["popularity_score"] = min(download_count / 1000.0, 1.0)  # Normalize
        
        # Quality score based on ratings
        avg_rating = model_data.get("avg_rating", 0.0)
        features["quality_score"] = avg_rating / 5.0 if avg_rating else 0.0
        
        # Recency score based on creation date
        created_at = model_data.get("created_at")
        if created_at:
            try:
                created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                days_old = (datetime.utcnow() - created_date.replace(tzinfo=None)).days
                features["recency_score"] = max(0.0, 1.0 - days_old / 365.0)  # Decay over year
            except (ValueError, TypeError):
                features["recency_score"] = 0.5
        else:
            features["recency_score"] = 0.5
        
        # Name relevance (keyword-based)
        name = model_data.get("name", "").lower()
        description = model_data.get("description", "").lower()
        relevance_keywords = ["neural", "deep", "learning", "classification", "regression", "model"]
        keyword_matches = sum(1 for keyword in relevance_keywords if keyword in name or keyword in description)
        features["name_relevance"] = keyword_matches / len(relevance_keywords)
        
        # Complexity assessment
        complexity_indicators = ["advanced", "complex", "sophisticated", "simple", "basic", "easy"]
        complexity_score = 0.5  # Default neutral
        for indicator in complexity_indicators:
            if indicator in name or indicator in description:
                if indicator in ["advanced", "complex", "sophisticated"]:
                    complexity_score = 0.8
                else:
                    complexity_score = 0.2
                break
        features["complexity_score"] = complexity_score
        
        return features
    
    def extract_user_features(self, user_profile: UserProfile) -> Dict[str, float]:
        """Extract features from user profile.
        
        Parameters
        ----------
        user_profile : UserProfile
            User profile data
            
        Returns
        -------
        Dict[str, float]
            Extracted user features
        """
        features = {}
        
        # Expertise score based on level
        expertise_mapping = {
            "beginner": 0.2,
            "intermediate": 0.5,
            "advanced": 0.8,
            "expert": 1.0
        }
        features["expertise_score"] = expertise_mapping.get(user_profile.expertise_level, 0.2)
        
        # Activity level based on interactions
        interaction_count = len(user_profile.interaction_history)
        features["activity_level"] = min(interaction_count / 100.0, 1.0)  # Normalize
        
        # Preference strength based on number of preferences
        preference_count = len(user_profile.preferences)
        features["preference_strength"] = min(preference_count / 10.0, 1.0)
        
        # Rating behavior (how actively user rates models)
        rating_count = len(user_profile.model_ratings)
        features["rating_activity"] = min(rating_count / 20.0, 1.0)
        
        return features
    
    def compute_compatibility_score(
        self, 
        model_features: Dict[str, float], 
        user_features: Dict[str, float]
    ) -> float:
        """Compute compatibility score between model and user features.
        
        Parameters
        ----------
        model_features : Dict[str, float]
            Model features
        user_features : Dict[str, float]
            User features
            
        Returns
        -------
        float
            Compatibility score between 0 and 1
        """
        # Weighted combination of features
        compatibility = 0.0
        
        # Quality preference (higher expertise users prefer higher quality)
        quality_match = model_features.get("quality_score", 0.5)
        expertise = user_features.get("expertise_score", 0.2)
        quality_weight = 0.3 + expertise * 0.3  # More weight for expert users
        compatibility += quality_match * quality_weight
        
        # Complexity match (match model complexity to user expertise)
        complexity = model_features.get("complexity_score", 0.5)
        complexity_match = 1.0 - abs(complexity - expertise)
        compatibility += complexity_match * 0.2
        
        # Popularity consideration (beginners prefer popular models)
        popularity = model_features.get("popularity_score", 0.5)
        popularity_weight = 0.3 - expertise * 0.2  # Less weight for expert users
        compatibility += popularity * max(popularity_weight, 0.1)
        
        # Recency consideration (active users prefer recent models)
        recency = model_features.get("recency_score", 0.5)
        activity = user_features.get("activity_level", 0.2)
        compatibility += recency * activity * 0.2
        
        return min(compatibility, 1.0)
    
    def normalize_features(self, features: Dict[str, Any]) -> Dict[str, float]:
        """Normalize feature values to [0, 1] range.
        
        Parameters
        ----------
        features : Dict[str, Any]
            Raw feature values
            
        Returns
        -------
        Dict[str, float]
            Normalized features
        """
        normalized = {}
        
        for key, value in features.items():
            try:
                # Convert to float and normalize
                float_value = float(value)
                if float_value < 0:
                    normalized[key] = 0.0
                elif float_value > 1:
                    # Simple normalization for values > 1
                    normalized[key] = min(float_value / 100.0, 1.0)
                else:
                    normalized[key] = float_value
            except (ValueError, TypeError):
                normalized[key] = 0.0
        
        return normalized


class PersonalizedRanker:
    """Personalized ranking system for model search results.
    
    Provides comprehensive personalization including user profiling,
    collaborative filtering, and contextual ranking adjustments.
    
    Examples
    --------
    >>> ranker = PersonalizedRanker()
    >>> results = ranker.rank_models(search_results, user_id)
    >>> explanation = ranker.explain_ranking(results[0], user_id)
    """
    
    def __init__(self):
        """Initialize personalized ranker."""
        self.ranking_features = RankingFeatures()
        self.user_profiles: Dict[str, UserProfile] = {}
        self.metrics_registry = get_metrics_registry()
        
        # Statistics tracking
        self._ranking_stats = {
            "total_rankings": 0,
            "personalized_rankings": 0,
            "avg_score_improvement": 0.0,
            "feature_usage": defaultdict(int)
        }
    
    def get_or_create_user_profile(self, user_id: str) -> UserProfile:
        """Get existing user profile or create new one.
        
        Parameters
        ----------
        user_id : str
            User identifier
            
        Returns
        -------
        UserProfile
            User profile instance
        """
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserProfile(user_id=user_id)
        
        return self.user_profiles[user_id]
    
    def update_user_profile(
        self, 
        user_id: str, 
        preferences: Optional[Dict[str, Any]] = None,
        expertise_level: Optional[str] = None
    ) -> None:
        """Update user profile with new data.
        
        Parameters
        ----------
        user_id : str
            User identifier
        preferences : Dict[str, Any], optional
            User preferences to update
        expertise_level : str, optional
            User expertise level
        """
        profile = self.get_or_create_user_profile(user_id)
        
        if preferences:
            profile.preferences.update(preferences)
        
        if expertise_level:
            profile.expertise_level = expertise_level
        
        profile.updated_at = datetime.utcnow()
    
    def record_user_interaction(
        self, 
        user_id: str, 
        model_id: str, 
        action: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record user interaction with a model.
        
        Parameters
        ----------
        user_id : str
            User identifier
        model_id : str
            Model identifier
        action : str
            Interaction type
        metadata : Dict[str, Any], optional
            Additional interaction metadata
        """
        profile = self.get_or_create_user_profile(user_id)
        profile.add_interaction(model_id, action, metadata)
    
    def rank_models(
        self, 
        search_results: List[Dict[str, Any]], 
        user_id: str,
        diversity_factor: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Rank search results based on user personalization.
        
        Parameters
        ----------
        search_results : List[Dict[str, Any]]
            Original search results
        user_id : str
            User identifier for personalization
        diversity_factor : float, optional
            Factor for diversity injection (0.0 to 1.0)
            
        Returns
        -------
        List[Dict[str, Any]]
            Personalized and ranked results
        """
        if not search_results:
            return []
        
        profile = self.get_or_create_user_profile(user_id)
        user_features = self.ranking_features.extract_user_features(profile)
        
        # Extract model features and compute personalized scores
        for result in search_results:
            model_features = self.ranking_features.extract_model_features(result)
            
            # Base compatibility score
            compatibility = self.ranking_features.compute_compatibility_score(
                model_features, user_features
            )
            
            # Type preference bonus
            model_type = result.get("model_type")
            preferred_types = profile.get_preferred_model_types()
            type_bonus = preferred_types.get(model_type, 0.0) * 0.2
            
            # Interaction history bonus
            interaction_bonus = profile.get_interaction_score(result.get("model_id", "")) * 0.15
            
            # Cold start handling for new users
            cold_start_boost = 0.0
            if len(profile.interaction_history) < 5:
                # Boost popular and highly rated models for new users
                popularity = model_features.get("popularity_score", 0.0)
                quality = model_features.get("quality_score", 0.0)
                cold_start_boost = (popularity + quality) * 0.1
            
            # Combine all factors
            original_score = result.get("score", 0.0)
            personalized_score = (
                original_score * 0.4 +
                compatibility * 0.3 +
                type_bonus +
                interaction_bonus +
                cold_start_boost
            )
            
            # Apply diversity boost if requested
            diversity_boost = 0.0
            if diversity_factor > 0:
                # Simple diversity based on model type variety
                type_count = sum(1 for r in search_results if r.get("model_type") == model_type)
                if type_count == 1:  # Unique model type gets diversity boost
                    diversity_boost = diversity_factor * 0.1
            
            personalized_score += diversity_boost
            
            # Store scores and ranking factors
            result["personalized_score"] = min(personalized_score, 1.0)
            result["rank_factors"] = {
                "original_score": original_score,
                "compatibility": compatibility,
                "type_preference": type_bonus,
                "interaction_history": interaction_bonus,
                "cold_start_boost": cold_start_boost,
                "diversity_boost": diversity_boost
            }
        
        # Sort by personalized score
        ranked_results = sorted(
            search_results, 
            key=lambda x: x.get("personalized_score", 0.0), 
            reverse=True
        )
        
        # Update ranks
        for i, result in enumerate(ranked_results):
            result["rank"] = i + 1
        
        # Update statistics
        self._ranking_stats["total_rankings"] += 1
        self._ranking_stats["personalized_rankings"] += 1
        
        # Update metrics
        try:
            from emuses.observability.metrics import model_analytics_operations_total
            model_analytics_operations_total.labels(
                operation_type="personalized_ranking",
                status="success"
            ).inc()
        except ImportError:
            pass
        
        return ranked_results
    
    def rank_models_with_context(
        self, 
        search_results: List[Dict[str, Any]], 
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Rank models using explicit user context instead of stored profile.
        
        Parameters
        ----------
        search_results : List[Dict[str, Any]]
            Search results to rank
        user_context : Dict[str, Any]
            User context with preferences and metadata
            
        Returns
        -------
        List[Dict[str, Any]]
            Ranked results
        """
        if not search_results:
            return []
        
        # Create temporary profile from context
        user_id = user_context.get("user_id", "temp_user")
        temp_profile = UserProfile(
            user_id=user_id,
            preferences=user_context.get("preferences", {}),
            expertise_level=user_context.get("expertise_level", "beginner")
        )
        
        # Add any provided interaction history
        previous_models = user_context.get("previous_models", [])
        for model_id in previous_models:
            temp_profile.add_interaction(model_id, "previous_interaction")
        
        # Store temporarily and rank
        original_profile = self.user_profiles.get(user_id)
        self.user_profiles[user_id] = temp_profile
        
        try:
            results = self.rank_models(search_results, user_id)
        finally:
            # Restore original profile or remove temporary
            if original_profile:
                self.user_profiles[user_id] = original_profile
            else:
                del self.user_profiles[user_id]
        
        return results
    
    def explain_ranking(self, model_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Generate explanation for why a model was ranked at its position.
        
        Parameters
        ----------
        model_data : Dict[str, Any]
            Model data with ranking information
        user_id : str
            User identifier
            
        Returns
        -------
        Dict[str, Any]
            Ranking explanation
        """
        profile = self.user_profiles.get(user_id)
        if not profile:
            return {"error": "User profile not found"}
        
        rank_factors = model_data.get("rank_factors", {})
        
        explanation = {
            "ranking_factors": rank_factors,
            "user_preferences": dict(profile.preferences),
            "score_breakdown": {
                "original_search_score": rank_factors.get("original_score", 0.0),
                "personalization_boost": (
                    model_data.get("personalized_score", 0.0) - 
                    rank_factors.get("original_score", 0.0)
                ),
                "final_score": model_data.get("personalized_score", 0.0)
            }
        }
        
        # Generate recommendation reason
        reasons = []
        if rank_factors.get("type_preference", 0) > 0.1:
            reasons.append("Matches your preferred model type")
        if rank_factors.get("interaction_history", 0) > 0.1:
            reasons.append("Similar to models you've used before")
        if rank_factors.get("cold_start_boost", 0) > 0.05:
            reasons.append("Popular choice for users with similar interests")
        if rank_factors.get("compatibility", 0.7) > 0.7:
            reasons.append("Well-suited to your expertise level")
        
        explanation["recommendation_reason"] = " | ".join(reasons) if reasons else "General relevance"
        
        return explanation
    
    def get_collaborative_recommendations(
        self, 
        user_id: str, 
        max_recommendations: int = 10
    ) -> List[Dict[str, Any]]:
        """Get collaborative filtering recommendations.
        
        Parameters
        ----------
        user_id : str
            Target user identifier
        max_recommendations : int
            Maximum number of recommendations
            
        Returns
        -------
        List[Dict[str, Any]]
            Collaborative recommendations
        """
        target_profile = self.user_profiles.get(user_id)
        if not target_profile:
            return []
        
        # Find similar users based on preferences and interactions
        similar_users = []
        target_types = target_profile.get_preferred_model_types()
        
        for other_id, other_profile in self.user_profiles.items():
            if other_id == user_id:
                continue
            
            # Calculate similarity based on preferred model types
            other_types = other_profile.get_preferred_model_types()
            
            # Simple Jaccard similarity
            all_types = set(target_types.keys()) | set(other_types.keys())
            if all_types:
                intersection = sum(
                    min(target_types.get(t, 0), other_types.get(t, 0)) 
                    for t in all_types
                )
                union = sum(
                    max(target_types.get(t, 0), other_types.get(t, 0))
                    for t in all_types
                )
                similarity = intersection / union if union > 0 else 0
                
                if similarity > 0.3:  # Threshold for similarity
                    similar_users.append((other_id, similarity))
        
        # Get recommendations from similar users
        recommendations = []
        similar_users.sort(key=lambda x: x[1], reverse=True)
        
        for similar_user_id, similarity in similar_users[:5]:  # Top 5 similar users
            similar_profile = self.user_profiles[similar_user_id]
            
            # Get highly rated models from similar user
            for model_id, rating in similar_profile.model_ratings.items():
                if rating >= 4.0 and model_id not in target_profile.model_ratings:
                    recommendations.append({
                        "model_id": model_id,
                        "predicted_rating": rating * similarity,
                        "confidence": similarity,
                        "source_user_similarity": similarity
                    })
        
        # Sort by predicted rating and return top recommendations
        recommendations.sort(key=lambda x: x["predicted_rating"], reverse=True)
        return recommendations[:max_recommendations]
    
    def _compute_temporal_preferences(self, profile: UserProfile) -> Dict[str, float]:
        """Compute preferences with temporal decay.
        
        Parameters
        ----------
        profile : UserProfile
            User profile
            
        Returns
        -------
        Dict[str, float]
            Temporal preferences
        """
        temporal_preferences = defaultdict(float)
        current_time = datetime.utcnow()
        
        for interaction in profile.interaction_history:
            try:
                interaction_time = datetime.fromisoformat(interaction["timestamp"])
                days_ago = (current_time - interaction_time).days
                
                # Exponential decay: more recent interactions have higher weight
                decay_factor = np.exp(-days_ago / 90.0)  # 90-day half-life
                
                model_type = interaction.get("metadata", {}).get("model_type")
                if model_type:
                    action_weight = {
                        "view": 1.0,
                        "download": 3.0,
                        "rate": 2.0,
                        "bookmark": 1.5
                    }.get(interaction["action"], 1.0)
                    
                    temporal_preferences[model_type] += action_weight * decay_factor
            
            except (ValueError, KeyError):
                continue
        
        # Normalize
        if temporal_preferences:
            max_score = max(temporal_preferences.values())
            return {k: v / max_score for k, v in temporal_preferences.items()}
        
        return {}
    
    def get_ranking_stats(self) -> Dict[str, Any]:
        """Get ranking system statistics.
        
        Returns
        -------
        Dict[str, Any]
            Ranking statistics
        """
        total_users = len(self.user_profiles)
        active_users = sum(
            1 for profile in self.user_profiles.values() 
            if len(profile.interaction_history) > 0
        )
        
        # Calculate average personalization impact
        avg_impact = 0.0
        if self._ranking_stats["personalized_rankings"] > 0:
            avg_impact = self._ranking_stats["avg_score_improvement"] / self._ranking_stats["personalized_rankings"]
        
        return {
            "total_rankings": self._ranking_stats["total_rankings"],
            "personalized_rankings": self._ranking_stats["personalized_rankings"],
            "unique_users": total_users,
            "active_users": active_users,
            "avg_personalization_impact": avg_impact,
            "feature_importance": dict(self.ranking_features.feature_weights),
            "user_engagement": {
                "avg_interactions_per_user": (
                    sum(len(p.interaction_history) for p in self.user_profiles.values()) / 
                    max(total_users, 1)
                ),
                "avg_ratings_per_user": (
                    sum(len(p.model_ratings) for p in self.user_profiles.values()) / 
                    max(total_users, 1)
                )
            }
        }