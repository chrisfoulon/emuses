"""Model registry caching system for performance optimization.

This module provides caching functionality to improve performance of
frequently accessed model registry operations including list_models,
search_models, and get_model_info.
"""
import hashlib
import json
import time
from typing import Any, Dict, Optional
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


class ModelRegistryCache:
    """In-memory cache for model registry operations with TTL and size limits.

    Provides caching for expensive model registry operations like database
    queries and search operations to improve response times.

    Parameters
    ----------
    max_size : int, default=1000
        Maximum number of cache entries to store
    default_ttl : int, default=300
        Default TTL in seconds for cache entries

    Attributes
    ----------
    _cache : OrderedDict
        Internal cache storage with LRU eviction
    _timestamps : Dict[str, float]
        Cache entry timestamps for TTL tracking
    _memory_usage : int
        Approximate memory usage in bytes
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """Initialize model registry cache.

        Parameters
        ----------
        max_size : int, default=1000
            Maximum number of cache entries
        default_ttl : int, default=300
            Default TTL in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        self._ttls: Dict[str, float] = {}
        self._memory_usage = 0

        logger.debug(f"Initialized ModelRegistryCache with "
                     f"max_size={max_size}, default_ttl={default_ttl}")

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Parameters
        ----------
        key : str
            Cache key

        Returns
        -------
        Optional[Any]
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            return None

        # Check TTL expiration
        current_time = time.time()
        if key in self._ttls and current_time > self._ttls[key]:
            # Entry expired, remove it
            self._remove_entry(key)
            return None

        # Move to end (LRU)
        value = self._cache.pop(key)
        self._cache[key] = value

        logger.debug(f"Cache hit for key: {key[:50]}...")
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache.

        Parameters
        ----------
        key : str
            Cache key
        value : Any
            Value to cache
        ttl : int, optional
            Time to live in seconds. Uses default_ttl if None
        """
        if ttl is None:
            ttl = self.default_ttl

        current_time = time.time()

        # Remove existing entry if present
        if key in self._cache:
            self._remove_entry(key)

        # Enforce size limit
        while len(self._cache) >= self.max_size:
            oldest_key = next(iter(self._cache))
            self._remove_entry(oldest_key)

        # Add new entry
        self._cache[key] = value
        self._timestamps[key] = current_time
        self._ttls[key] = current_time + ttl

        # Estimate memory usage (rough approximation)
        try:
            entry_size = len(str(value)) + len(key)
            self._memory_usage += entry_size
        except Exception:
            # If size estimation fails, use default
            self._memory_usage += 1000

        logger.debug(f"Cached key: {key[:50]}... (TTL: {ttl}s)")

    def _remove_entry(self, key: str) -> None:
        """Remove entry from all cache structures.

        Parameters
        ----------
        key : str
            Cache key to remove
        """
        if key in self._cache:
            value = self._cache.pop(key)
            # Update memory usage estimate
            try:
                entry_size = len(str(value)) + len(key)
                self._memory_usage = max(0, self._memory_usage - entry_size)
            except Exception:
                self._memory_usage = max(0, self._memory_usage - 1000)

        self._timestamps.pop(key, None)
        self._ttls.pop(key, None)

    def invalidate(self, key: str) -> None:
        """Invalidate specific cache entry.

        Parameters
        ----------
        key : str
            Cache key to invalidate
        """
        if key in self._cache:
            self._remove_entry(key)
            logger.debug(f"Invalidated cache key: {key[:50]}...")

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._timestamps.clear()
        self._ttls.clear()
        self._memory_usage = 0
        logger.debug("Cleared all cache entries")

    def invalidate_user_cache(self, user_id: str) -> None:
        """Invalidate all cache entries for a specific user.

        Parameters
        ----------
        user_id : str
            User ID whose cache entries should be invalidated
        """
        keys_to_remove = []
        # Create list to avoid modification during iteration
        for key in list(self._cache.keys()):
            # Check for various user ID patterns in cache keys
            if (f"user-{user_id}" in key or
                f":{user_id}:" in key or
                key.endswith(f":{user_id}") or
                    key.startswith(f"{user_id}:")):
                keys_to_remove.append(key)

        for key in keys_to_remove:
            self._remove_entry(key)

        logger.debug(f"Invalidated {len(keys_to_remove)} cache entries "
                     f"for user {user_id}")

    def generate_list_models_key(
        self,
        user_id: str,
        workspace_id: Optional[str] = None,
        include_public: bool = True,
        filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate cache key for list_models operation.

        Parameters
        ----------
        user_id : str
            User ID
        workspace_id : str, optional
            Workspace ID
        include_public : bool, default=True
            Whether to include public models
        filters : Dict[str, Any], optional
            Additional filters

        Returns
        -------
        str
            Generated cache key
        """
        key_parts = [
            "list_models",
            f"user-{user_id}",
            f"workspace-{workspace_id}" if workspace_id else "workspace-none",
            f"public-{include_public}",
        ]

        if filters:
            # Sort filters for consistent key generation
            filter_str = json.dumps(filters, sort_keys=True)
            filter_hash = hashlib.md5(filter_str.encode()).hexdigest()[:8]
            key_parts.append(f"filters-{filter_hash}")

        return ":".join(key_parts)

    def generate_search_models_key(
        self,
        query: str,
        user_id: str,
        workspace_id: Optional[str] = None,
        include_public: bool = True
    ) -> str:
        """Generate cache key for search_models operation.

        Parameters
        ----------
        query : str
            Search query
        user_id : str
            User ID
        workspace_id : str, optional
            Workspace ID
        include_public : bool, default=True
            Whether to include public models

        Returns
        -------
        str
            Generated cache key
        """
        # Hash query for consistent key generation
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]

        key_parts = [
            "search_models",
            f"query-{query_hash}",
            f"user-{user_id}",
            f"workspace-{workspace_id}" if workspace_id else "workspace-none",
            f"public-{include_public}",
        ]

        return ":".join(key_parts)

    def generate_model_info_key(self, model_id: str, user_id: str) -> str:
        """Generate cache key for get_model_info operation.

        Parameters
        ----------
        model_id : str
            Model ID
        user_id : str
            User ID

        Returns
        -------
        str
            Generated cache key
        """
        return f"model_info:model-{model_id}:user-{user_id}"

    def get_default_ttl(self, operation_type: str) -> int:
        """Get default TTL for different operation types.

        Parameters
        ----------
        operation_type : str
            Type of operation (list_models, search_models, model_info)

        Returns
        -------
        int
            TTL in seconds
        """
        ttl_map = {
            'list_models': 300,      # 5 minutes
            'search_models': 180,    # 3 minutes (searches change more frequently)
            'model_info': 600,       # 10 minutes (individual models change less)
        }

        return ttl_map.get(operation_type, self.default_ttl)

    def get_memory_usage(self) -> int:
        """Get approximate memory usage of the cache.

        Returns
        -------
        int
            Approximate memory usage in bytes
        """
        return self._memory_usage

    def cleanup_expired(self) -> int:
        """Clean up expired cache entries.

        Returns
        -------
        int
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = []

        for key, expire_time in self._ttls.items():
            if current_time > expire_time:
                expired_keys.append(key)

        for key in expired_keys:
            self._remove_entry(key)

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)
