"""Model caching system for EMUSES model registry.

This module provides caching capabilities for model data and metadata,
supporting multiple backends including Redis, Memcached, and in-memory caching.
"""

import json
import gzip
import uuid
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, Any, Optional, Union, List
from collections import OrderedDict

from sqlalchemy.orm import Session

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from pymemcache.client.base import Client as MemcachedClient
    MEMCACHED_AVAILABLE = True
except ImportError:
    MEMCACHED_AVAILABLE = False

from emuses.multi_user_service.models import ModelRegistry
from emuses.observability.metrics import get_metrics_registry


class CachingError(Exception):
    """Exception raised for caching system errors."""
    pass


@dataclass
class CacheConfig:
    """Configuration for model caching system.

    Attributes
    ----------
    backend_type : str
        Type of cache backend ('redis', 'memcached', 'memory')
    redis_host : str
        Redis server hostname
    redis_port : int
        Redis server port
    redis_db : int
        Redis database number
    memcached_host : str
        Memcached server hostname
    memcached_port : int
        Memcached server port
    default_ttl : int
        Default time-to-live in seconds
    max_memory_items : int
        Maximum items for in-memory cache
    enable_compression : bool
        Whether to enable data compression
    enable_cache_warming : bool
        Whether to enable cache warming on initialization
    cache_warming_limit : int
        Number of popular models to cache during warming
    """
    backend_type: str = "memory"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    memcached_host: str = "localhost"
    memcached_port: int = 11211
    default_ttl: int = 3600
    max_memory_items: int = 1000
    enable_compression: bool = True
    enable_cache_warming: bool = False
    cache_warming_limit: int = 10


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set key-value pair with optional TTL."""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete key."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all keys."""
        pass


class InMemoryBackend(CacheBackend):
    """In-memory cache backend with LRU eviction and TTL support."""

    def __init__(self, max_items: int = 1000):
        """Initialize in-memory cache backend.

        Parameters
        ----------
        max_items : int
            Maximum number of items to store
        """
        self.max_items = max_items
        self._cache: OrderedDict = OrderedDict()
        self._access_times: Dict[str, datetime] = {}
        self._expiration_times: Dict[str, Optional[datetime]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        # Check expiration first
        if self._is_expired(key):
            self._remove_key(key)
            return None

        if key not in self._cache:
            return None

        # Update access time and move to end (most recent)
        self._access_times[key] = datetime.utcnow()
        self._cache.move_to_end(key)

        return json.loads(self._cache[key])

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set key-value pair with optional TTL."""
        # Remove expired items first
        self._cleanup_expired()

        # Calculate expiration time
        expiration_time = None
        if ttl is not None and ttl > 0:
            expiration_time = datetime.utcnow() + timedelta(seconds=ttl)

        # Store the value
        serialized_value = json.dumps(value)
        self._cache[key] = serialized_value
        self._access_times[key] = datetime.utcnow()
        self._expiration_times[key] = expiration_time

        # Move to end (most recent)
        self._cache.move_to_end(key)

        # Enforce size limit with LRU eviction
        while len(self._cache) > self.max_items:
            oldest_key = next(iter(self._cache))
            self._remove_key(oldest_key)

        return True

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        if self._is_expired(key):
            self._remove_key(key)
            return False
        return key in self._cache

    def delete(self, key: str) -> bool:
        """Delete key."""
        if key in self._cache:
            self._remove_key(key)
            return True
        return False

    def clear(self) -> None:
        """Clear all keys."""
        self._cache.clear()
        self._access_times.clear()
        self._expiration_times.clear()

    def _is_expired(self, key: str) -> bool:
        """Check if key is expired."""
        if key not in self._expiration_times:
            return False

        expiration_time = self._expiration_times[key]
        if expiration_time is None:
            return False

        return datetime.utcnow() > expiration_time

    def _remove_key(self, key: str) -> None:
        """Remove key from all internal structures."""
        self._cache.pop(key, None)
        self._access_times.pop(key, None)
        self._expiration_times.pop(key, None)

    def _cleanup_expired(self) -> None:
        """Remove expired keys."""
        expired_keys = [
            key for key in self._cache
            if self._is_expired(key)
        ]
        for key in expired_keys:
            self._remove_key(key)


class RedisBackend(CacheBackend):
    """Redis cache backend."""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        """Initialize Redis backend.

        Parameters
        ----------
        host : str
            Redis server hostname
        port : int
            Redis server port
        db : int
            Redis database number
        """
        if not REDIS_AVAILABLE:
            raise CachingError("Redis package not available. Install with: pip install redis")

        try:
            self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=False)
            # Test connection
            self.redis.ping()
        except Exception as e:
            raise CachingError(f"Failed to connect to Redis: {str(e)}")

    def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        try:
            value = self.redis.get(key)
            if value is None:
                return None
            return json.loads(value.decode('utf-8'))
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set key-value pair with optional TTL."""
        try:
            serialized_value = json.dumps(value)
            result = self.redis.set(key, serialized_value, ex=ttl)
            return bool(result)
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            return bool(self.redis.exists(key))
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """Delete key."""
        try:
            result = self.redis.delete(key)
            return result > 0
        except Exception:
            return False

    def clear(self) -> None:
        """Clear all keys."""
        try:
            self.redis.flushdb()
        except Exception:
            pass


class MemcachedBackend(CacheBackend):
    """Memcached cache backend."""

    def __init__(self, host: str = "localhost", port: int = 11211):
        """Initialize Memcached backend.

        Parameters
        ----------
        host : str
            Memcached server hostname
        port : int
            Memcached server port
        """
        if not MEMCACHED_AVAILABLE:
            raise CachingError("Pymemcache package not available. Install with: pip install pymemcache")

        try:
            self.client = MemcachedClient((host, port))
        except Exception as e:
            raise CachingError(f"Failed to connect to Memcached: {str(e)}")

    def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        try:
            value = self.client.get(key)
            if value is None:
                return None
            if isinstance(value, bytes):
                value = value.decode('utf-8')
            return json.loads(value)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set key-value pair with optional TTL."""
        try:
            serialized_value = json.dumps(value)
            result = self.client.set(key, serialized_value, expire=ttl or 0)
            return bool(result)
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            value = self.client.get(key)
            return value is not None
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """Delete key."""
        try:
            result = self.client.delete(key)
            return bool(result)
        except Exception:
            return False

    def clear(self) -> None:
        """Clear all keys."""
        try:
            self.client.flush_all()
        except Exception:
            pass


class ModelCache:
    """Model caching system for performance optimization.

    Provides caching capabilities for model data and metadata with support
    for multiple backends, compression, and intelligent cache management.

    Parameters
    ----------
    db_session : Session
        Database session for model operations
    config : CacheConfig, optional
        Cache configuration settings

    Attributes
    ----------
    db_session : Session
        Database session reference
    config : CacheConfig
        Cache configuration
    backend : CacheBackend
        Cache backend instance

    Examples
    --------
    >>> cache = ModelCache(db_session)
    >>> cache.cache_model(model_id, model_data, metadata)
    >>> cached_data = cache.get_cached_model(model_id)
    >>> cache.invalidate_cache(model_id)
    """

    def __init__(self, db_session: Optional[Session] = None, config: Optional[CacheConfig] = None):
        if db_session is None:
            raise CachingError("Database session is required")

        self.db_session = db_session
        self.config = config or CacheConfig()
        self.metrics_registry = get_metrics_registry()

        # Initialize backend
        self.backend = self._create_backend()

        # Statistics tracking
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_start_time = time.time()

        # Invalidation callbacks
        self._invalidation_callbacks = []

        # Cache warming on initialization
        if self.config.enable_cache_warming:
            try:
                self._warm_cache()
            except Exception:
                # Graceful degradation if cache warming fails
                pass

    def _create_backend(self) -> CacheBackend:
        """Create appropriate cache backend based on configuration."""
        if self.config.backend_type == "redis":
            return RedisBackend(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db
            )
        elif self.config.backend_type == "memcached":
            return MemcachedBackend(
                host=self.config.memcached_host,
                port=self.config.memcached_port
            )
        elif self.config.backend_type == "memory":
            return InMemoryBackend(max_items=self.config.max_memory_items)
        else:
            raise CachingError(f"Unsupported cache backend: {self.config.backend_type}")

    def cache_model(
        self,
        model_id: Union[str, uuid.UUID],
        model_data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None
    ) -> bool:
        """Cache model data and metadata.

        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the model to cache
        model_data : Any
            Model data to cache
        metadata : Dict[str, Any], optional
            Model metadata to cache
        ttl : int, optional
            Time-to-live in seconds (uses default if not specified)

        Returns
        -------
        bool
            True if caching was successful, False otherwise
        """
        try:
            # Normalize UUID
            if isinstance(model_id, str):
                model_id = uuid.UUID(model_id)

            # Prepare cache data
            cache_data = {
                "model_data": model_data,
                "metadata": metadata or {},
                "cached_at": datetime.utcnow().isoformat(),
                "model_id": str(model_id)
            }

            # Apply compression if enabled
            if self.config.enable_compression:
                cache_data = self._compress_data(cache_data)

            # Use default TTL if not specified
            effective_ttl = ttl or self.config.default_ttl

            # Cache the model
            cache_key = f"model:{model_id}"
            success = self.backend.set(cache_key, cache_data, ttl=effective_ttl)

            # Update metrics
            try:
                from emuses.observability.metrics import model_analytics_operations_total
                model_analytics_operations_total.labels(
                    operation_type="cache_set",
                    status="success" if success else "error"
                ).inc()
            except ImportError:
                pass

            return success

        except Exception:
            # Update error metrics
            try:
                from emuses.observability.metrics import model_analytics_operations_total
                model_analytics_operations_total.labels(
                    operation_type="cache_set",
                    status="error"
                ).inc()
            except ImportError:
                pass
            return False

    def get_cached_model(self, model_id: Union[str, uuid.UUID], track_access: bool = False) -> Optional[Dict[str, Any]]:
        """Get cached model data.

        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the model to retrieve
        track_access : bool, optional
            Whether to track access for cache optimization

        Returns
        -------
        Dict[str, Any] or None
            Cached model data if found, None otherwise
        """
        try:
            # Normalize UUID
            if isinstance(model_id, str):
                model_id = uuid.UUID(model_id)

            cache_key = f"model:{model_id}"
            cached_data = self.backend.get(cache_key)

            if cached_data is None:
                self._cache_misses += 1
                # Update metrics
                try:
                    from emuses.observability.metrics import model_analytics_operations_total
                    model_analytics_operations_total.labels(
                        operation_type="cache_get",
                        status="miss"
                    ).inc()
                except ImportError:
                    pass
                return None

            # Decompress if needed
            if self.config.enable_compression:
                cached_data = self._decompress_data(cached_data)

            self._cache_hits += 1
            # Update metrics
            try:
                from emuses.observability.metrics import model_analytics_operations_total
                model_analytics_operations_total.labels(
                    operation_type="cache_get",
                    status="hit"
                ).inc()
            except ImportError:
                pass

            return cached_data

        except Exception:
            self._cache_misses += 1
            # Update error metrics
            try:
                from emuses.observability.metrics import model_analytics_operations_total
                model_analytics_operations_total.labels(
                    operation_type="cache_get",
                    status="error"
                ).inc()
            except ImportError:
                pass
            return None

    def is_model_cached(self, model_id: Union[str, uuid.UUID]) -> bool:
        """Check if model is cached.

        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the model to check

        Returns
        -------
        bool
            True if model is cached, False otherwise
        """
        try:
            # Normalize UUID
            if isinstance(model_id, str):
                model_id = uuid.UUID(model_id)

            cache_key = f"model:{model_id}"
            return self.backend.exists(cache_key)

        except Exception:
            return False

    def invalidate_cache(self, model_id: Optional[Union[str, uuid.UUID]] = None) -> bool:
        """Invalidate cached model(s).

        Parameters
        ----------
        model_id : Union[str, UUID], optional
            ID of specific model to invalidate. If None, clears all cache.

        Returns
        -------
        bool
            True if invalidation was successful, False otherwise
        """
        try:
            if model_id is None:
                # Clear all cache
                self.backend.clear()
                return True
            else:
                # Clear specific model
                if isinstance(model_id, str):
                    model_id = uuid.UUID(model_id)

                cache_key = f"model:{model_id}"
                return self.backend.delete(cache_key)

        except Exception:
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing cache statistics
        """
        uptime_seconds = time.time() - self._cache_start_time

        # Try to get cache size (backend specific)
        cache_size = 0
        cached_models = 0
        try:
            if hasattr(self.backend, '_cache'):
                # In-memory backend
                cache_size = len(self.backend._cache)
                cached_models = cache_size
            # For Redis/Memcached, we'd need to implement key counting
        except Exception:
            pass

        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": (
                self._cache_hits / max(self._cache_hits + self._cache_misses, 1)
            ),
            "cached_models": cached_models,
            "cache_size": cache_size,
            "cache_backend": self.config.backend_type,
            "compression_enabled": self.config.enable_compression,
            "uptime_seconds": int(uptime_seconds)
        }

    def _compress_data(self, data: Any) -> Dict[str, Any]:
        """Compress data if compression is enabled.

        Parameters
        ----------
        data : Any
            Data to compress

        Returns
        -------
        Dict[str, Any]
            Compressed data wrapper or original data
        """
        try:
            # For simplicity, we'll use JSON + gzip compression
            json_data = json.dumps(data)
            compressed_data = gzip.compress(json_data.encode('utf-8'))

            return {
                "compressed": True,
                "data": compressed_data.hex(),  # Store as hex string for JSON compatibility
                "original_size": len(json_data),
                "compressed_size": len(compressed_data)
            }
        except Exception:
            # Fall back to uncompressed data
            return {
                "compressed": False,
                "data": data
            }

    def _decompress_data(self, data: Dict[str, Any]) -> Any:
        """Decompress data if it was compressed.

        Parameters
        ----------
        data : Dict[str, Any]
            Data to decompress

        Returns
        -------
        Any
            Decompressed data or original data
        """
        try:
            if not isinstance(data, dict) or not data.get("compressed", False):
                # Return data as-is if not compressed
                if isinstance(data, dict) and "data" in data and not data.get("compressed", False):
                    return data["data"]
                return data

            # Decompress the data
            compressed_hex = data["data"]
            compressed_data = bytes.fromhex(compressed_hex)
            decompressed_data = gzip.decompress(compressed_data)
            return json.loads(decompressed_data.decode('utf-8'))

        except Exception:
            # Fall back to returning data as-is
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return data

    def cache_popular_models(
        self,
        limit: int = 10,
        use_analytics: bool = False,
        analytics: Optional[Any] = None,
        preload_strategy: str = "download_count",
        max_cache_size_mb: Optional[float] = None
    ) -> Dict[str, Any]:
        """Cache popular models with intelligent pre-loading strategies.

        Parameters
        ----------
        limit : int, optional
            Maximum number of popular models to cache
        use_analytics : bool, optional
            Whether to use analytics data for popularity ranking
        analytics : ModelAnalytics, optional
            Analytics instance for popularity data
        preload_strategy : str, optional
            Strategy for preloading ('download_count', 'size_optimized', 'balanced')
        max_cache_size_mb : float, optional
            Maximum total cache size in MB

        Returns
        -------
        Dict[str, Any]
            Results of the caching operation
        """
        try:
            popular_models = []
            
            if use_analytics and analytics:
                # Use analytics to get popular models
                try:
                    analytics_data = analytics.get_popular_models(limit=limit)
                    model_ids = [uuid.UUID(item["model_id"]) for item in analytics_data]
                    
                    # Get model objects from database
                    popular_models = self.db_session.query(ModelRegistry).filter(
                        ModelRegistry.id.in_(model_ids)
                    ).all()
                    
                except Exception:
                    # Fall back to database query if analytics fails
                    use_analytics = False

            if not use_analytics:
                # Query database for popular models based on download counts
                try:
                    from sqlalchemy import func, desc
                    from emuses.multi_user_service.models import ModelDownload
                    
                    download_counts = (
                        self.db_session.query(
                            ModelDownload.model_id,
                            func.count(ModelDownload.id).label('download_count')
                        )
                        .group_by(ModelDownload.model_id)
                        .subquery()
                    )
                    
                    popular_models = (
                        self.db_session.query(ModelRegistry)
                        .outerjoin(download_counts, ModelRegistry.id == download_counts.c.model_id)
                        .group_by(ModelRegistry.id)
                        .order_by(desc(func.coalesce(download_counts.c.download_count, 0)))
                        .limit(limit)
                    )
                except Exception:
                    # Fallback: get all models if complex query fails
                    popular_models = (
                        self.db_session.query(ModelRegistry)
                        .filter(ModelRegistry.is_public == True)
                        .limit(limit)
                    )

            if not popular_models:
                return {
                    "status": "success",
                    "cached_models": 0,
                    "total_popular": 0,
                    "message": "No popular models found to cache",
                    "analytics_used": use_analytics
                }

            # Apply preloading strategy
            models_to_cache = self._apply_preloading_strategy(
                popular_models, preload_strategy, max_cache_size_mb
            )

            # Cache the selected models
            cached_count = 0
            total_size_cached = 0
            cache_size_limit_applied = False

            for model in models_to_cache:
                try:
                    # Simple model data structure for caching
                    model_data = {
                        "name": model.name,
                        "model_type": model.model_type,
                        "is_public": model.is_public,
                        "cached_via_preload": True
                    }
                    
                    metadata = {
                        "preload_strategy": preload_strategy,
                        "model_size_bytes": getattr(model, 'model_size_bytes', 0)
                    }
                    
                    # Check size limit if specified
                    if max_cache_size_mb:
                        model_size_mb = metadata["model_size_bytes"] / (1024 * 1024)
                        if (total_size_cached + model_size_mb) > max_cache_size_mb:
                            cache_size_limit_applied = True
                            break
                        total_size_cached += model_size_mb
                    
                    # Cache the model
                    success = self.cache_model(
                        model_id=model.id,
                        model_data=model_data,
                        metadata=metadata,
                        ttl=self.config.default_ttl * 2  # Longer TTL for popular models
                    )
                    
                    if success:
                        cached_count += 1

                except Exception:
                    # Continue with other models if one fails
                    continue

            result = {
                "status": "success",
                "cached_models": cached_count,
                "total_popular": len(popular_models),
                "preload_strategy": preload_strategy,
                "analytics_used": use_analytics
            }
            
            if cache_size_limit_applied:
                result["cache_size_limit_applied"] = True
                result["total_size_cached_mb"] = total_size_cached

            return result

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to cache popular models: {str(e)}",
                "cached_models": 0,
                "analytics_used": use_analytics
            }

    def _apply_preloading_strategy(
        self,
        models: List[Any],
        strategy: str,
        max_cache_size_mb: Optional[float] = None
    ) -> List[Any]:
        """Apply intelligent preloading strategy to select models for caching.

        Parameters
        ----------
        models : List[ModelRegistry]
            List of models to consider for caching
        strategy : str
            Preloading strategy to apply
        max_cache_size_mb : float, optional
            Maximum cache size limit

        Returns
        -------
        List[ModelRegistry]
            Filtered and ordered list of models to cache
        """
        if strategy == "size_optimized":
            # Prefer smaller models for faster cache loading
            return sorted(
                models,
                key=lambda m: getattr(m, 'model_size_bytes', 0)
            )
        elif strategy == "balanced":
            # Balance between popularity and size
            def balanced_score(model):
                size_bytes = getattr(model, 'model_size_bytes', 1024)
                # Lower size penalty, higher score for smaller models
                size_penalty = size_bytes / (1024 * 1024)  # Size in MB
                return 100 - min(size_penalty, 50)  # Score between 50-100
            
            return sorted(models, key=balanced_score, reverse=True)
        else:  # "download_count" or default
            # Keep original order (already sorted by popularity)
            return models

    def _warm_cache(self) -> None:
        """Warm the cache by pre-loading popular models."""
        try:
            # Use existing cache_popular_models method for warming
            result = self.cache_popular_models(
                limit=self.config.cache_warming_limit,
                preload_strategy="balanced"  # Use balanced strategy for warming
            )
            
            # Track warming results in metrics if available
            try:
                from emuses.observability.metrics import model_analytics_operations_total
                model_analytics_operations_total.labels(
                    operation_type="cache_warming",
                    status="success" if result["status"] == "success" else "error"
                ).inc()
            except ImportError:
                pass

        except Exception:
            # Graceful degradation - cache warming failure shouldn't break initialization
            pass

    def invalidate_cache_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching a pattern.

        Parameters
        ----------
        pattern : str
            Pattern to match cache keys (supports wildcards for compatible backends)

        Returns
        -------
        int
            Number of entries invalidated
        """
        try:
            # For in-memory backend, we can implement pattern matching
            if isinstance(self.backend, InMemoryBackend):
                keys_to_delete = []
                if hasattr(self.backend, '_cache'):
                    for key in self.backend._cache.keys():
                        if pattern in key or key.startswith(pattern.rstrip('*')):
                            keys_to_delete.append(key)
                
                for key in keys_to_delete:
                    self.backend.delete(key)
                
                return len(keys_to_delete)
            else:
                # For Redis/Memcached, we'd need specific pattern support
                # For now, fall back to single key deletion if pattern is exact
                if '*' not in pattern:
                    success = self.backend.delete(pattern)
                    return 1 if success else 0
                return 0

        except Exception:
            return 0

    def cleanup_expired_entries(self, max_age_seconds: int = 3600) -> int:
        """Clean up expired cache entries.

        Parameters
        ----------
        max_age_seconds : int
            Maximum age in seconds before entries are considered expired

        Returns
        -------
        int
            Number of entries cleaned up
        """
        try:
            if isinstance(self.backend, InMemoryBackend):
                # In-memory backend already handles TTL expiration
                # This method can force cleanup of old entries
                self.backend._cleanup_expired()
                return 0  # InMemoryBackend doesn't track cleanup count
            else:
                # For Redis/Memcached, we'd need custom logic
                # This is a placeholder implementation
                return 0

        except Exception:
            return 0

    def cache_model_with_version(
        self,
        model_id: Union[str, uuid.UUID],
        model_data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        version: str = "1.0",
        ttl: Optional[int] = None
    ) -> bool:
        """Cache model with version information for consistency.

        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the model to cache
        model_data : Any
            Model data to cache
        metadata : Dict[str, Any], optional
            Model metadata
        version : str
            Version identifier for the cached model
        ttl : int, optional
            Time-to-live in seconds

        Returns
        -------
        bool
            True if caching was successful
        """
        # Add version to metadata
        enhanced_metadata = metadata.copy() if metadata else {}
        enhanced_metadata["cache_version"] = version
        enhanced_metadata["versioned_cache"] = True

        return self.cache_model(
            model_id=model_id,
            model_data=model_data,
            metadata=enhanced_metadata,
            ttl=ttl
        )

    def get_cached_model_with_version(
        self,
        model_id: Union[str, uuid.UUID],
        expected_version: str,
        track_access: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get cached model with version validation.

        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the model to retrieve
        expected_version : str
            Expected version of the cached model
        track_access : bool, optional
            Whether to track access for optimization

        Returns
        -------
        Dict[str, Any] or None
            Cached model data if version matches, None otherwise
        """
        cached_data = self.get_cached_model(model_id, track_access=track_access)
        
        if cached_data is None:
            return None
        
        # Check version in metadata
        metadata = cached_data.get("metadata", {})
        if metadata.get("versioned_cache") and metadata.get("cache_version") == expected_version:
            return cached_data
        
        return None

    def register_invalidation_callback(self, callback: callable) -> None:
        """Register a callback for cache invalidation events.

        Parameters
        ----------
        callback : callable
            Function to call when invalidation occurs. 
            Should accept (key, reason) parameters.
        """
        if callable(callback):
            self._invalidation_callbacks.append(callback)

    def invalidate_cache_with_reason(
        self,
        model_id: Optional[Union[str, uuid.UUID]] = None,
        reason: str = "unknown"
    ) -> bool:
        """Invalidate cache with reason tracking and callbacks.

        Parameters
        ----------
        model_id : Union[str, UUID], optional
            ID of specific model to invalidate
        reason : str
            Reason for invalidation

        Returns
        -------
        bool
            True if invalidation was successful
        """
        try:
            # Determine cache key
            if model_id is not None:
                if isinstance(model_id, str):
                    try:
                        model_id = uuid.UUID(model_id)
                    except (ValueError, TypeError):
                        # Invalid UUID string, still proceed with string key
                        pass
                cache_key = f"model:{model_id}"
            else:
                cache_key = "all"

            # Perform invalidation
            if model_id is None:
                self.backend.clear()
                success = True
            else:
                success = self.backend.delete(cache_key)
                # For in-memory backend, delete might return False even if key didn't exist
                # Consider this successful for distributed invalidation
                success = True

            # Call registered callbacks
            for callback in self._invalidation_callbacks:
                try:
                    callback(cache_key, reason)
                except Exception:
                    # Continue with other callbacks if one fails
                    pass

            return success

        except Exception:
            return False

    def handle_distributed_invalidation(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Handle distributed cache invalidation signals.

        Parameters
        ----------
        signal : Dict[str, Any]
            Invalidation signal with type, model_id, timestamp, source

        Returns
        -------
        Dict[str, Any]
            Processing result
        """
        try:
            signal_type = signal.get("type", "unknown")
            model_id = signal.get("model_id")
            source = signal.get("source", "unknown")
            
            # Process different signal types
            if signal_type == "model_updated":
                success = self.invalidate_cache_with_reason(
                    model_id=model_id,
                    reason=f"distributed_update_from_{source}"
                )
            elif signal_type == "model_deleted":
                success = self.invalidate_cache_with_reason(
                    model_id=model_id,
                    reason=f"distributed_delete_from_{source}"
                )
            elif signal_type == "registry_cleared":
                success = self.invalidate_cache_with_reason(
                    model_id=None,
                    reason=f"distributed_clear_from_{source}"
                )
            else:
                # For unknown signal types, still return successful processing
                success = True

            return {
                "processed": success,
                "signal_type": signal_type,
                "source": source,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            return {
                "processed": False,
                "error": str(e),
                "signal_type": signal.get("type", "unknown"),
                "timestamp": datetime.utcnow().isoformat()
            }