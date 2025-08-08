"""
Model Registry Analytics Module

Provides comprehensive analytics and usage tracking for the EMUSES model registry,
including download statistics, community insights, and observability integration.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from emuses.multi_user_service.models import ModelRegistry, ModelDownload, User
from emuses.observability.metrics import get_metrics_registry


class AnalyticsError(Exception):
    """Base exception for model analytics operations."""
    pass


class ModelAnalytics:
    """
    Model registry analytics and usage tracking.

    Provides functionality for tracking model downloads, generating usage statistics,
    identifying popular models, and integrating with the observability system.

    Parameters
    ----------
    db_session : Session
        Database session for analytics operations
    """

    def __init__(self, db_session: Optional[Session] = None, enable_streaming: bool = False):
        """
        Initialize ModelAnalytics instance.

        Parameters
        ----------
        db_session : Session, optional
            Database session for analytics operations
        enable_streaming : bool, optional
            Whether to enable real-time streaming of analytics events

        Raises
        ------
        AnalyticsError
            If db_session is not provided
        """
        if db_session is None:
            raise AnalyticsError("Database session is required")

        self.db_session = db_session
        self.metrics_registry = get_metrics_registry()

        # Initialize streaming if enabled
        self.streamer = None
        if enable_streaming:
            try:
                from .streaming_analytics import AnalyticsStreamer, StreamingConfig
                config = StreamingConfig(enable_realtime=True)
                self.streamer = AnalyticsStreamer(db_session=db_session, config=config)
            except ImportError:
                # Graceful degradation if streaming dependencies unavailable
                pass

    def record_download(
        self,
        model_id: Union[str, uuid.UUID],
        user_id: Union[str, uuid.UUID],
        download_size_bytes: Optional[int] = None,
        download_method: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> uuid.UUID:
        """
        Record a model download for analytics tracking.

        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the downloaded model
        user_id : Union[str, UUID]
            ID of the user downloading the model
        download_size_bytes : int, optional
            Size of downloaded content in bytes
        download_method : str, optional
            Download method (api, cli, web)
        user_agent : str, optional
            User agent string from download request

        Returns
        -------
        UUID
            ID of the created download record

        Raises
        ------
        AnalyticsError
            If model or user is not found
        """
        # Normalize UUIDs
        if isinstance(model_id, str):
            model_id = uuid.UUID(model_id)
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)

        # Verify model exists
        model = self.db_session.query(ModelRegistry).filter(
            ModelRegistry.id == model_id
        ).first()
        if not model:
            raise AnalyticsError(f"Model not found: {model_id}")

        # Verify user exists
        user = self.db_session.query(User).filter(
            User.id == user_id
        ).first()
        if not user:
            raise AnalyticsError(f"User not found: {user_id}")

        # Create download record
        download = ModelDownload(
            model_id=model_id,
            user_id=user_id,
            downloaded_at=datetime.utcnow(),
            download_size_bytes=download_size_bytes,
            download_method=download_method,
            user_agent=user_agent
        )

        self.db_session.add(download)
        self.db_session.commit()

        # Track metrics
        try:
            from emuses.observability.metrics import model_downloads_total, model_analytics_operations_total

            # Get model for type information
            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == model_id
            ).first()

            model_downloads_total.labels(
                model_id=str(model_id),
                model_type=model.model_type if model else "unknown",
                user_id=str(user_id),
                download_method=download_method or "unknown"
            ).inc()

            model_analytics_operations_total.labels(
                operation_type="record_download",
                status="success"
            ).inc()

        except ImportError:
            # Observability system not available
            pass

        # Queue for real-time streaming if enabled
        if self.streamer:
            try:
                import asyncio
                asyncio.create_task(self.streamer.queue_download_event(
                    model_id=model_id,
                    user_id=user_id,
                    download_size_bytes=download_size_bytes,
                    download_method=download_method,
                    user_agent=user_agent
                ))
            except Exception:
                # Graceful degradation if streaming fails
                pass

        return download.id

    def get_model_stats(self, model_id: Union[str, uuid.UUID]) -> Dict[str, Any]:
        """
        Get detailed usage statistics for a specific model.

        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the model to get statistics for

        Returns
        -------
        Dict[str, Any]
            Dictionary containing comprehensive model statistics

        Raises
        ------
        AnalyticsError
            If model is not found
        """
        # Normalize UUID
        if isinstance(model_id, str):
            model_id = uuid.UUID(model_id)

        # Verify model exists
        model = self.db_session.query(ModelRegistry).filter(
            ModelRegistry.id == model_id
        ).first()
        if not model:
            raise AnalyticsError(f"Model not found: {model_id}")

        # Get download statistics
        downloads = self.db_session.query(ModelDownload).filter(
            ModelDownload.model_id == model_id
        ).all()

        if not downloads:
            return {
                "model_id": str(model_id),
                "total_downloads": 0,
                "unique_users": 0,
                "total_bytes_downloaded": 0,
                "first_download": None,
                "last_download": None,
                "download_methods": {},
                "downloads_by_day": [],
                "top_users": []
            }

        # Calculate statistics
        total_downloads = len(downloads)
        unique_users = len(set(d.user_id for d in downloads))
        total_bytes = sum(d.download_size_bytes or 0 for d in downloads)

        # Download methods breakdown
        method_counts = {}
        for download in downloads:
            method = download.download_method or "unknown"
            method_counts[method] = method_counts.get(method, 0) + 1

        # Top users by download count
        user_counts = {}
        for download in downloads:
            user_counts[download.user_id] = user_counts.get(download.user_id, 0) + 1

        top_users = [
            {"user_id": str(user_id), "download_count": count}
            for user_id, count in sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        # Time range
        download_times = [d.downloaded_at for d in downloads]
        first_download = min(download_times) if download_times else None
        last_download = max(download_times) if download_times else None

        return {
            "model_id": str(model_id),
            "total_downloads": total_downloads,
            "unique_users": unique_users,
            "total_bytes_downloaded": total_bytes,
            "first_download": first_download,
            "last_download": last_download,
            "download_methods": method_counts,
            "downloads_by_day": [],  # TODO: Implement daily breakdown
            "top_users": top_users
        }

    def get_popular_models(
        self,
        limit: int = 10,
        days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get popular models based on download statistics.

        Parameters
        ----------
        limit : int, default=10
            Maximum number of models to return
        days : int, optional
            Only consider downloads from the last N days

        Returns
        -------
        List[Dict[str, Any]]
            List of popular models with statistics
        """
        query = self.db_session.query(
            ModelRegistry,
            func.count(ModelDownload.id).label('download_count'),
            func.count(func.distinct(ModelDownload.user_id)).label('unique_users'),
            func.coalesce(func.sum(ModelDownload.download_size_bytes), 0).label('total_bytes')
        ).outerjoin(
            ModelDownload, ModelRegistry.id == ModelDownload.model_id
        )

        # Apply time window filter
        if days is not None:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(
                (ModelDownload.downloaded_at >= cutoff_date) | (ModelDownload.downloaded_at.is_(None))
            )

        query = query.group_by(ModelRegistry.id).order_by(desc('download_count')).limit(limit)

        results = []
        for model, download_count, unique_users, total_bytes in query.all():
            results.append({
                "model_id": str(model.id),
                "name": model.name,
                "description": model.description,
                "download_count": download_count,
                "unique_users": unique_users,
                "total_bytes": int(total_bytes),
                "owner_id": str(model.owner_id),
                "is_public": model.is_public,
                "model_type": model.model_type,
                "version": model.version
            })

        return results

    def generate_community_insights(
        self,
        limit: int = 10,
        days: Optional[int] = 30
    ) -> Dict[str, Any]:
        """
        Generate community insights for model discovery and recommendations.

        Parameters
        ----------
        limit : int, default=10
            Maximum number of items to return in each category
        days : int, optional
            Time window for trending analysis (default 30 days)

        Returns
        -------
        Dict[str, Any]
            Community insights including trending models, recommendations, and analytics
        """
        insights = {
            "trending_models": [],
            "recommended_models": [],
            "popular_tags": [],
            "active_users": [],
            "discovery_recommendations": []
        }

        # Get trending models (models with recent growth in downloads)
        trending_models = self._calculate_trending_models(limit=limit, days=days)
        insights["trending_models"] = trending_models

        # Get recommended models (diverse, high-quality models)
        recommended_models = self._get_recommended_models(limit=limit)
        insights["recommended_models"] = recommended_models

        # Get popular tags from model metadata
        popular_tags = self._get_popular_tags(limit=limit)
        insights["popular_tags"] = popular_tags

        # Get most active users
        active_users = self._get_active_users(limit=limit, days=days)
        insights["active_users"] = active_users

        # Generate discovery recommendations
        discovery_recommendations = self._generate_discovery_recommendations(limit=limit)
        insights["discovery_recommendations"] = discovery_recommendations

        # Track metrics
        try:
            from emuses.observability.metrics import model_analytics_operations_total, model_recommendation_requests_total

            model_analytics_operations_total.labels(
                operation_type="community_insights",
                status="success"
            ).inc()

            model_recommendation_requests_total.labels(
                recommendation_type="community"
            ).inc()

        except ImportError:
            # Observability system not available
            pass

        return insights

    def analyze_user_behavior(
        self,
        user_id: Union[str, uuid.UUID],
        days: Optional[int] = 90
    ) -> Dict[str, Any]:
        """
        Analyze user behavior and preferences for personalized recommendations.

        Parameters
        ----------
        user_id : Union[str, UUID]
            ID of the user to analyze
        days : int, optional
            Time window for analysis (default 90 days)

        Returns
        -------
        Dict[str, Any]
            User behavior analysis and personalized recommendations
        """
        # Normalize UUID
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)

        # Verify user exists
        user = self.db_session.query(User).filter(User.id == user_id).first()
        if not user:
            raise AnalyticsError(f"User not found: {user_id}")

        # Get user downloads
        query = self.db_session.query(ModelDownload).filter(
            ModelDownload.user_id == user_id
        )

        if days is not None:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(ModelDownload.downloaded_at >= cutoff_date)

        downloads = query.all()

        if not downloads:
            return {
                "user_id": str(user_id),
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

        # Analyze download patterns
        unique_model_ids = set(d.model_id for d in downloads)
        total_downloads = len(downloads)

        # Get model types from downloads
        model_type_counts = {}
        download_method_counts = {}

        for download in downloads:
            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == download.model_id
            ).first()
            if model and model.model_type:
                model_type_counts[model.model_type] = model_type_counts.get(model.model_type, 0) + 1

            method = download.download_method or "unknown"
            download_method_counts[method] = download_method_counts.get(method, 0) + 1

        # Sort by frequency
        favorite_model_types = [
            {"type": model_type, "count": count}
            for model_type, count in sorted(model_type_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        preferred_methods = [
            {"method": method, "count": count}
            for method, count in sorted(download_method_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        # Calculate frequency
        if days:
            downloads_per_day = total_downloads / days
            if downloads_per_day >= 1:
                frequency = "daily"
            elif downloads_per_day >= 0.25:
                frequency = "weekly"
            elif downloads_per_day >= 0.07:
                frequency = "monthly"
            else:
                frequency = "occasional"
        else:
            frequency = "unknown"

        # Generate personalized recommendations
        recommendations = self._generate_user_recommendations(user_id, model_type_counts)

        behavior_data = {
            "user_id": str(user_id),
            "download_patterns": {
                "total_downloads": total_downloads,
                "unique_models": len(unique_model_ids),
                "favorite_model_types": [item["type"] for item in favorite_model_types[:3]],
                "download_frequency": frequency,
                "peak_download_hours": []  # TODO: Implement hour analysis
            },
            "preferences": {
                "model_types": favorite_model_types,
                "download_methods": preferred_methods
            },
            "recommendations": recommendations
        }

        # Track metrics
        try:
            from emuses.observability.metrics import model_analytics_operations_total, model_recommendation_requests_total

            model_analytics_operations_total.labels(
                operation_type="user_behavior",
                status="success"
            ).inc()

            if recommendations:
                model_recommendation_requests_total.labels(
                    recommendation_type="personalized"
                ).inc()

        except ImportError:
            # Observability system not available
            pass

        return behavior_data

    def _calculate_trending_models(self, limit: int = 10, days: int = 30) -> List[Dict[str, Any]]:
        """Calculate trending models based on recent download growth."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Get recent downloads
        recent_query = self.db_session.query(
            ModelRegistry,
            func.count(ModelDownload.id).label('recent_downloads')
        ).outerjoin(
            ModelDownload,
            (ModelRegistry.id == ModelDownload.model_id) &
            (ModelDownload.downloaded_at >= cutoff_date)
        ).group_by(ModelRegistry.id).order_by(desc('recent_downloads')).limit(limit)

        results = []
        for model, recent_downloads in recent_query.all():
            if recent_downloads > 0:
                # Simple trend score based on recent activity
                trend_score = recent_downloads * (1.0 + (1.0 / (days + 1)))

                results.append({
                    "model_id": str(model.id),
                    "name": model.name,
                    "trend_score": trend_score,
                    "recent_downloads": recent_downloads,
                    "model_type": model.model_type,
                    "is_public": model.is_public
                })

        return results

    def _get_recommended_models(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get diverse, high-quality models for recommendations."""
        # For now, return popular public models
        query = self.db_session.query(
            ModelRegistry,
            func.count(ModelDownload.id).label('download_count')
        ).outerjoin(
            ModelDownload, ModelRegistry.id == ModelDownload.model_id
        ).filter(
            ModelRegistry.is_public.is_(True)
        ).group_by(ModelRegistry.id).order_by(desc('download_count')).limit(limit)

        results = []
        for model, download_count in query.all():
            results.append({
                "model_id": str(model.id),
                "name": model.name,
                "description": model.description,
                "model_type": model.model_type,
                "download_count": download_count,
                "quality_score": min(download_count * 0.1, 5.0)  # Simple quality estimate
            })

        return results

    def _get_popular_tags(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get popular tags from model metadata."""
        # Get all models with tags
        models_with_tags = self.db_session.query(ModelRegistry).filter(
            ModelRegistry.tags.isnot(None)
        ).all()

        tag_counts = {}
        for model in models_with_tags:
            if model.tags:
                for tag in model.tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

        return [
            {"tag": tag, "count": count}
            for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        ]

    def _get_active_users(self, limit: int = 10, days: int = 30) -> List[Dict[str, Any]]:
        """Get most active users in the time window."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = self.db_session.query(
            User,
            func.count(ModelDownload.id).label('download_count'),
            func.count(func.distinct(ModelDownload.model_id)).label('unique_models')
        ).join(
            ModelDownload, User.id == ModelDownload.user_id
        ).filter(
            ModelDownload.downloaded_at >= cutoff_date
        ).group_by(User.id).order_by(desc('download_count')).limit(limit)

        results = []
        for user, download_count, unique_models in query.all():
            results.append({
                "user_id": str(user.id),
                "download_count": download_count,
                "unique_models": unique_models,
                "activity_score": download_count + (unique_models * 2)
            })

        return results

    def _generate_discovery_recommendations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Generate recommendations for model discovery."""
        # Simple discovery: recommend models with good ratings but few downloads
        query = self.db_session.query(
            ModelRegistry,
            func.count(ModelDownload.id).label('download_count')
        ).outerjoin(
            ModelDownload, ModelRegistry.id == ModelDownload.model_id
        ).filter(
            ModelRegistry.is_public.is_(True)
        ).group_by(ModelRegistry.id).having(
            func.count(ModelDownload.id) < 10  # Low download count
        ).order_by(desc(ModelRegistry.created_at)).limit(limit)

        results = []
        for model, download_count in query.all():
            results.append({
                "model_id": str(model.id),
                "name": model.name,
                "description": model.description,
                "model_type": model.model_type,
                "reason": "Recent addition with potential",
                "discovery_score": 5.0 - (download_count * 0.2)
            })

        return results

    def _generate_user_recommendations(
        self,
        user_id: uuid.UUID,
        model_type_preferences: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        """Generate personalized recommendations for a user."""
        if not model_type_preferences:
            return []

        # Find models of preferred types that user hasn't downloaded
        favorite_types = list(model_type_preferences.keys())

        # Get user's downloaded model IDs
        downloaded_models = set(
            download.model_id for download in
            self.db_session.query(ModelDownload).filter(ModelDownload.user_id == user_id).all()
        )

        # Find popular models of preferred types that user hasn't downloaded
        query = self.db_session.query(
            ModelRegistry,
            func.count(ModelDownload.id).label('download_count')
        ).outerjoin(
            ModelDownload, ModelRegistry.id == ModelDownload.model_id
        ).filter(
            ModelRegistry.model_type.in_(favorite_types),
            ModelRegistry.is_public.is_(True),
            ~ModelRegistry.id.in_(downloaded_models)
        ).group_by(ModelRegistry.id).order_by(desc('download_count')).limit(5)

        results = []
        for model, download_count in query.all():
            results.append({
                "model_id": str(model.id),
                "name": model.name,
                "model_type": model.model_type,
                "reason": f"Popular {model.model_type} model",
                "relevance_score": model_type_preferences.get(model.model_type, 0) + download_count
            })

        return results

    def update_registry_metrics(self):
        """
        Update Prometheus metrics for model registry size and storage.

        This method should be called periodically to update gauge metrics
        that reflect the current state of the model registry.
        """
        try:
            from emuses.observability.metrics import model_registry_size, model_storage_bytes

            # Count models by visibility
            public_count = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.is_public.is_(True)
            ).count()

            private_count = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.is_public.is_(False)
            ).count()

            # Update registry size metrics
            model_registry_size.labels(
                registry_type="database",
                visibility="public"
            ).set(public_count)

            model_registry_size.labels(
                registry_type="database",
                visibility="private"
            ).set(private_count)

            # Update storage metrics by model type
            model_types = self.db_session.query(ModelRegistry.model_type).distinct().all()

            for (model_type,) in model_types:
                if model_type:
                    models = self.db_session.query(ModelRegistry).filter(
                        ModelRegistry.model_type == model_type,
                        ModelRegistry.model_size_bytes.isnot(None)
                    ).all()

                    for model in models:
                        if model.model_size_bytes:
                            model_storage_bytes.labels(
                                model_type=model_type
                            ).observe(model.model_size_bytes)

        except ImportError:
            # Observability system not available
            pass

    def calculate_model_similarities(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Calculate similarity scores between models based on metadata.

        Uses TF-IDF and cosine similarity on model metadata (description, tags, type)
        to find similar models for recommendation purposes.

        Parameters
        ----------
        limit : int, default=10
            Maximum number of model similarity results to return

        Returns
        -------
        List[Dict[str, Any]]
            List of model similarity data with similar models and scores
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
        except ImportError:
            # sklearn not available, return empty list
            return []

        # Get all public models with metadata
        models = self.db_session.query(ModelRegistry).filter(
            ModelRegistry.is_public.is_(True)
        ).all()

        if len(models) < 2:
            return []

        # Create text features for each model
        model_features = []
        model_ids = []

        for model in models:
            # Combine description, tags, and type into feature text
            feature_text = []

            if model.description:
                feature_text.append(model.description)

            if model.tags:
                feature_text.extend(model.tags)

            if model.model_type:
                feature_text.append(model.model_type)

            # Join all features into single text
            combined_text = " ".join(feature_text)
            model_features.append(combined_text)
            model_ids.append(model.id)

        if not model_features:
            return []

        # Create TF-IDF matrix
        try:
            vectorizer = TfidfVectorizer(
                stop_words='english',
                max_features=1000,
                lowercase=True,
                token_pattern=r'[a-zA-Z][a-zA-Z-]*'
            )
            tfidf_matrix = vectorizer.fit_transform(model_features)

            # Calculate cosine similarity
            similarity_matrix = cosine_similarity(tfidf_matrix)

            results = []

            for i, model_id in enumerate(model_ids):
                # Get similarity scores for this model
                similarity_scores = similarity_matrix[i]

                # Find most similar models (excluding self)
                similar_indices = []
                similar_scores = []

                for j, score in enumerate(similarity_scores):
                    if i != j and score > 0.1:  # Minimum similarity threshold
                        similar_indices.append(j)
                        similar_scores.append(score)

                if similar_indices:
                    # Sort by similarity score descending
                    sorted_pairs = sorted(
                        zip(similar_indices, similar_scores),
                        key=lambda x: x[1],
                        reverse=True
                    )[:5]  # Top 5 similar models

                    similar_models = []
                    scores = []

                    for idx, score in sorted_pairs:
                        similar_model_id = model_ids[idx]
                        similar_models.append(str(similar_model_id))
                        scores.append(float(score))

                    if similar_models:
                        results.append({
                            "model_id": str(model_id),
                            "similar_models": similar_models,
                            "similarity_scores": scores,
                            "similarity_method": "tfidf_cosine"
                        })

            # Track metrics
            try:
                from emuses.observability.metrics import model_analytics_operations_total

                model_analytics_operations_total.labels(
                    operation_type="similarity_calculation",
                    status="success"
                ).inc()

            except ImportError:
                # Observability system not available
                pass

            return results[:limit]

        except Exception:
            # TF-IDF calculation failed
            return []

    def get_similar_models_for_user(
        self,
        user_id: Union[str, uuid.UUID],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get personalized model recommendations based on user's download history.

        Analyzes user's downloaded models to find similar models they haven't downloaded yet.

        Parameters
        ----------
        user_id : Union[str, UUID]
            ID of the user to get recommendations for
        limit : int, default=5
            Maximum number of recommendations to return

        Returns
        -------
        List[Dict[str, Any]]
            List of recommended models with similarity scores and reasons

        Raises
        ------
        AnalyticsError
            If user is not found
        """
        # Normalize UUID
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)

        # Verify user exists
        user = self.db_session.query(User).filter(User.id == user_id).first()
        if not user:
            raise AnalyticsError(f"User not found: {user_id}")

        # Get user's downloaded models
        downloaded_models = self.db_session.query(ModelDownload).filter(
            ModelDownload.user_id == user_id
        ).all()

        if not downloaded_models:
            return []

        downloaded_model_ids = set(d.model_id for d in downloaded_models)

        # Get all similarity data
        all_similarities = self.calculate_model_similarities(limit=100)

        recommendations = []
        seen_recommendations = set()

        # Find similar models to user's downloaded models
        for similarity_data in all_similarities:
            source_model_id = uuid.UUID(similarity_data["model_id"])

            # If user downloaded this model, recommend its similar models
            if source_model_id in downloaded_model_ids:
                for i, similar_model_id in enumerate(similarity_data["similar_models"]):
                    similar_uuid = uuid.UUID(similar_model_id)

                    # Don't recommend already downloaded models
                    if similar_uuid not in downloaded_model_ids and similar_uuid not in seen_recommendations:
                        # Get model details
                        similar_model = self.db_session.query(ModelRegistry).filter(
                            ModelRegistry.id == similar_uuid
                        ).first()

                        if similar_model and similar_model.is_public:
                            score = similarity_data["similarity_scores"][i]

                            recommendations.append({
                                "model_id": similar_model_id,
                                "name": similar_model.name,
                                "model_type": similar_model.model_type,
                                "similarity_score": score,
                                "recommendation_reason": f"Similar to {similarity_data['model_id'][:8]}... (downloaded)",
                                "source_model_id": str(source_model_id)
                            })

                            seen_recommendations.add(similar_uuid)

                            if len(recommendations) >= limit:
                                break

            if len(recommendations) >= limit:
                break

        # Sort by similarity score
        recommendations.sort(key=lambda x: x["similarity_score"], reverse=True)

        # Track metrics
        try:
            from emuses.observability.metrics import model_recommendation_requests_total

            if recommendations:
                model_recommendation_requests_total.labels(
                    recommendation_type="similarity_based"
                ).inc()

        except ImportError:
            # Observability system not available
            pass

        return recommendations[:limit]

    def get_geographic_insights(self, days: Optional[int] = 90) -> Dict[str, Any]:
        """
        Generate privacy-aware geographic analytics from user agent data.

        Analyzes geographic patterns in model downloads while protecting user privacy
        through aggregation and avoiding direct IP tracking.

        Parameters
        ----------
        days : int, optional
            Time window for analysis (default 90 days)

        Returns
        -------
        Dict[str, Any]
            Geographic insights with privacy protections
        """
        # Get downloads with user agent data
        query = self.db_session.query(ModelDownload).filter(
            ModelDownload.user_agent.isnot(None)
        )

        if days is not None:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(ModelDownload.downloaded_at >= cutoff_date)

        downloads = query.all()

        insights = {
            "download_patterns": {
                "by_region": {},
                "by_timezone": {},
                "total_unique_locations": 0
            },
            "privacy_notice": "Location data is inferred from user agents and aggregated for privacy"
        }

        if not downloads:
            return insights

        # Analyze user agents for geographic patterns (privacy-aware)
        platform_regions = {}
        timezone_patterns = {}
        unique_patterns = set()

        for download in downloads:
            if download.user_agent:
                user_agent = download.user_agent.lower()

                # Infer broad geographic regions from user agent patterns
                region = "unknown"
                if any(indicator in user_agent for indicator in ["en-us", "en_us", "united states"]):
                    region = "North America"
                elif any(indicator in user_agent for indicator in ["en-gb", "en_gb", "europe"]):
                    region = "Europe"
                elif any(indicator in user_agent for indicator in ["zh-cn", "zh_cn", "china"]):
                    region = "Asia-Pacific"
                elif any(indicator in user_agent for indicator in ["ja-jp", "ja_jp", "japan"]):
                    region = "Asia-Pacific"
                elif any(indicator in user_agent for indicator in ["pt-br", "pt_br", "brazil"]):
                    region = "South America"

                # Infer timezone patterns from download times (hourly distribution)
                hour = download.downloaded_at.hour
                timezone_bucket = f"UTC_{hour//4*4}-{(hour//4+1)*4}h"

                # Aggregate patterns to protect privacy
                platform_regions[region] = platform_regions.get(region, 0) + 1
                timezone_patterns[timezone_bucket] = timezone_patterns.get(timezone_bucket, 0) + 1

                # Track unique patterns (but don't expose raw data)
                pattern_key = f"{region}_{timezone_bucket}_{download.download_method}"
                unique_patterns.add(pattern_key)

        insights["download_patterns"]["by_region"] = platform_regions
        insights["download_patterns"]["by_timezone"] = timezone_patterns
        insights["download_patterns"]["total_unique_locations"] = len(unique_patterns)

        # Track metrics
        try:
            from emuses.observability.metrics import model_analytics_operations_total

            model_analytics_operations_total.labels(
                operation_type="geographic_insights",
                status="success"
            ).inc()

        except ImportError:
            # Observability system not available
            pass

        return insights

    def get_demographic_insights(self, days: Optional[int] = 90) -> Dict[str, Any]:
        """
        Generate privacy-aware demographic analytics from user data.

        Analyzes user demographics and usage patterns while protecting individual
        privacy through aggregation and anonymization.

        Parameters
        ----------
        days : int, optional
            Time window for analysis (default 90 days)

        Returns
        -------
        Dict[str, Any]
            Demographic insights with privacy protections
        """
        # Get downloads within time window
        query = self.db_session.query(
            ModelDownload,
            User.organization,
            User.role
        ).join(User, ModelDownload.user_id == User.id)

        if days is not None:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(ModelDownload.downloaded_at >= cutoff_date)

        download_data = query.all()

        insights = {
            "usage_patterns": {
                "by_organization_type": {},
                "by_user_role": {},
                "by_platform": {},
                "total_organizations": 0
            },
            "privacy_notice": "Demographic data is aggregated and anonymized to protect user privacy"
        }

        if not download_data:
            return insights

        # Aggregate demographic patterns (privacy-aware)
        org_types = {}
        role_patterns = {}
        platform_patterns = {}
        unique_orgs = set()

        for download, organization, role in download_data:
            # Categorize organizations by type (generalized for privacy)
            org_type = "other"
            if organization:
                org_lower = organization.lower()
                if any(keyword in org_lower for keyword in ["university", "college", "research", "academic"]):
                    org_type = "academic"
                elif any(keyword in org_lower for keyword in ["company", "corp", "inc", "ltd", "tech"]):
                    org_type = "commercial"
                elif any(keyword in org_lower for keyword in ["gov", "government", "public"]):
                    org_type = "government"
                elif any(keyword in org_lower for keyword in ["non-profit", "nonprofit", "ngo"]):
                    org_type = "non-profit"

                unique_orgs.add(organization)

            # Aggregate role patterns
            if role:
                role_patterns[role] = role_patterns.get(role, 0) + 1

            # Analyze platform usage from user agents and download methods
            platform = "unknown"
            if download.user_agent:
                user_agent = download.user_agent.lower()
                if "windows" in user_agent:
                    platform = "windows"
                elif any(os in user_agent for os in ["linux", "ubuntu", "debian"]):
                    platform = "linux"
                elif "mac" in user_agent or "darwin" in user_agent:
                    platform = "macos"
                elif "python" in user_agent:
                    platform = "python-client"

            org_types[org_type] = org_types.get(org_type, 0) + 1
            platform_patterns[platform] = platform_patterns.get(platform, 0) + 1

        # Only include patterns with sufficient data to protect privacy (minimum 3 occurrences)
        filtered_org_types = {k: v for k, v in org_types.items() if v >= 3}
        filtered_role_patterns = {k: v for k, v in role_patterns.items() if v >= 3}
        filtered_platform_patterns = {k: v for k, v in platform_patterns.items() if v >= 3}

        insights["usage_patterns"]["by_organization_type"] = filtered_org_types
        insights["usage_patterns"]["by_user_role"] = filtered_role_patterns
        insights["usage_patterns"]["by_platform"] = filtered_platform_patterns
        insights["usage_patterns"]["total_organizations"] = len(unique_orgs)

        # Track metrics
        try:
            from emuses.observability.metrics import model_analytics_operations_total

            model_analytics_operations_total.labels(
                operation_type="demographic_insights",
                status="success"
            ).inc()

        except ImportError:
            # Observability system not available
            pass

        return insights
