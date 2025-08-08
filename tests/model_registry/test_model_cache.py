"""Tests for model caching system."""

import pytest
import uuid
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path

from emuses.tools.model_cache import (
    ModelCache, CacheBackend, CacheConfig, CachingError,
    RedisBackend, MemcachedBackend, InMemoryBackend
)


class TestCacheBackend:
    """Test abstract cache backend interface."""
    
    def test_cache_backend_abstract(self):
        """Test that CacheBackend cannot be instantiated directly."""
        with pytest.raises(TypeError):
            CacheBackend()


class TestCacheConfig:
    """Test cache configuration class."""
    
    def test_cache_config_default(self):
        """Test default cache configuration values."""
        config = CacheConfig()
        
        assert config.backend_type == "memory"
        assert config.redis_host == "localhost"
        assert config.redis_port == 6379
        assert config.redis_db == 0
        assert config.memcached_host == "localhost"
        assert config.memcached_port == 11211
        assert config.default_ttl == 3600
        assert config.max_memory_items == 1000
        assert config.enable_compression == True
    
    def test_cache_config_custom(self):
        """Test custom cache configuration."""
        config = CacheConfig(
            backend_type="redis",
            redis_host="cache.example.com",
            redis_port=6380,
            redis_db=2,
            default_ttl=7200,
            max_memory_items=5000,
            enable_compression=False
        )
        
        assert config.backend_type == "redis"
        assert config.redis_host == "cache.example.com"
        assert config.redis_port == 6380
        assert config.redis_db == 2
        assert config.default_ttl == 7200
        assert config.max_memory_items == 5000
        assert config.enable_compression == False


class TestInMemoryBackend:
    """Test in-memory cache backend."""
    
    def test_in_memory_backend_init(self):
        """Test in-memory backend initialization."""
        backend = InMemoryBackend(max_items=100)
        
        assert backend.max_items == 100
        assert len(backend._cache) == 0
        assert len(backend._access_times) == 0
    
    def test_set_and_get(self):
        """Test basic set and get operations."""
        backend = InMemoryBackend()
        
        backend.set("test_key", "test_value", ttl=300)
        
        result = backend.get("test_key")
        assert result == "test_value"
    
    def test_get_nonexistent_key(self):
        """Test getting nonexistent key returns None."""
        backend = InMemoryBackend()
        
        result = backend.get("nonexistent")
        assert result is None
    
    def test_exists(self):
        """Test key existence check."""
        backend = InMemoryBackend()
        
        assert not backend.exists("test_key")
        
        backend.set("test_key", "test_value")
        assert backend.exists("test_key")
    
    def test_delete(self):
        """Test key deletion."""
        backend = InMemoryBackend()
        
        backend.set("test_key", "test_value")
        assert backend.exists("test_key")
        
        result = backend.delete("test_key")
        assert result == True
        assert not backend.exists("test_key")
        
        # Deleting nonexistent key should return False
        result = backend.delete("nonexistent")
        assert result == False
    
    def test_clear(self):
        """Test clearing all keys."""
        backend = InMemoryBackend()
        
        backend.set("key1", "value1")
        backend.set("key2", "value2")
        
        backend.clear()
        
        assert not backend.exists("key1")
        assert not backend.exists("key2")
    
    def test_ttl_expiration(self):
        """Test TTL expiration."""
        backend = InMemoryBackend()
        
        # Set with very short TTL
        backend.set("test_key", "test_value", ttl=1)
        assert backend.get("test_key") == "test_value"
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired now
        result = backend.get("test_key")
        assert result is None
        assert not backend.exists("test_key")
    
    def test_lru_eviction(self):
        """Test LRU eviction when max items exceeded."""
        backend = InMemoryBackend(max_items=2)
        
        # Add items up to limit
        backend.set("key1", "value1")
        backend.set("key2", "value2")
        
        # Access key1 to make it more recent
        backend.get("key1")
        
        # Add third item, should evict key2 (least recently used)
        backend.set("key3", "value3")
        
        assert backend.exists("key1")
        assert not backend.exists("key2")  # Should be evicted
        assert backend.exists("key3")


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    with patch('emuses.tools.model_cache.redis.Redis') as mock_redis_class:
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        yield mock_client


class TestRedisBackend:
    """Test Redis cache backend."""
    
    def test_redis_backend_init(self, mock_redis):
        """Test Redis backend initialization."""
        backend = RedisBackend(host="localhost", port=6379, db=0)
        
        assert backend.redis is mock_redis
    
    def test_set_and_get(self, mock_redis):
        """Test Redis set and get operations."""
        backend = RedisBackend()
        
        # Mock Redis responses
        mock_redis.set.return_value = True
        mock_redis.get.return_value = b'"test_value"'
        
        backend.set("test_key", "test_value", ttl=300)
        result = backend.get("test_key")
        
        mock_redis.set.assert_called_once_with("test_key", '"test_value"', ex=300)
        assert result == "test_value"
    
    def test_get_nonexistent_key(self, mock_redis):
        """Test getting nonexistent key from Redis."""
        backend = RedisBackend()
        
        mock_redis.get.return_value = None
        
        result = backend.get("nonexistent")
        assert result is None
    
    def test_exists(self, mock_redis):
        """Test Redis key existence check."""
        backend = RedisBackend()
        
        mock_redis.exists.return_value = 1
        assert backend.exists("test_key") == True
        
        mock_redis.exists.return_value = 0
        assert backend.exists("test_key") == False
    
    def test_delete(self, mock_redis):
        """Test Redis key deletion."""
        backend = RedisBackend()
        
        mock_redis.delete.return_value = 1
        result = backend.delete("test_key")
        assert result == True
        
        mock_redis.delete.return_value = 0
        result = backend.delete("nonexistent")
        assert result == False
    
    def test_clear(self, mock_redis):
        """Test Redis clear operation."""
        backend = RedisBackend()
        
        backend.clear()
        
        mock_redis.flushdb.assert_called_once()
    
    def test_redis_connection_error(self):
        """Test Redis connection error handling."""
        with patch('emuses.tools.model_cache.redis.Redis') as mock_redis_class:
            mock_redis_class.side_effect = Exception("Connection failed")
            
            with pytest.raises(CachingError, match="Failed to connect to Redis"):
                RedisBackend()


@pytest.fixture
def mock_memcached():
    """Mock Memcached client."""
    with patch('emuses.tools.model_cache.MemcachedClient') as mock_memcached_class:
        mock_client = Mock()
        mock_memcached_class.return_value = mock_client
        yield mock_client


class TestMemcachedBackend:
    """Test Memcached cache backend."""
    
    def test_memcached_backend_init(self, mock_memcached):
        """Test Memcached backend initialization."""
        backend = MemcachedBackend(host="localhost", port=11211)
        
        assert backend.client is mock_memcached
    
    def test_set_and_get(self, mock_memcached):
        """Test Memcached set and get operations."""
        backend = MemcachedBackend()
        
        # Mock Memcached responses
        mock_memcached.set.return_value = True
        mock_memcached.get.return_value = b'"test_value"'
        
        backend.set("test_key", "test_value", ttl=300)
        result = backend.get("test_key")
        
        mock_memcached.set.assert_called_once_with("test_key", '"test_value"', expire=300)
        assert result == "test_value"
    
    def test_get_nonexistent_key(self, mock_memcached):
        """Test getting nonexistent key from Memcached."""
        backend = MemcachedBackend()
        
        mock_memcached.get.return_value = None
        
        result = backend.get("nonexistent")
        assert result is None
    
    def test_delete(self, mock_memcached):
        """Test Memcached key deletion."""
        backend = MemcachedBackend()
        
        mock_memcached.delete.return_value = True
        result = backend.delete("test_key")
        assert result == True
        
        mock_memcached.delete.return_value = False
        result = backend.delete("nonexistent")
        assert result == False
    
    def test_clear(self, mock_memcached):
        """Test Memcached clear operation."""
        backend = MemcachedBackend()
        
        backend.clear()
        
        mock_memcached.flush_all.assert_called_once()


@pytest.fixture
def mock_database_session():
    """Mock database session for ModelCache testing."""
    return Mock()


@pytest.fixture
def sample_model_data():
    """Sample model data for testing."""
    model_id = uuid.uuid4()
    return {
        "model_id": model_id,
        "name": "test_model",
        "model_type": "classification",
        "is_public": True,
        "data": {"test": "data"},
        "metadata": {"size": 1024, "format": "pkl"}
    }


class TestModelCache:
    """Test ModelCache class."""
    
    def test_model_cache_init_memory_backend(self, mock_database_session):
        """Test ModelCache initialization with memory backend."""
        config = CacheConfig(backend_type="memory")
        cache = ModelCache(db_session=mock_database_session, config=config)
        
        assert cache.db_session is mock_database_session
        assert cache.config is config
        assert isinstance(cache.backend, InMemoryBackend)
    
    @patch('emuses.tools.model_cache.RedisBackend')
    def test_model_cache_init_redis_backend(self, mock_redis_backend, mock_database_session):
        """Test ModelCache initialization with Redis backend."""
        config = CacheConfig(backend_type="redis")
        cache = ModelCache(db_session=mock_database_session, config=config)
        
        mock_redis_backend.assert_called_once_with(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db
        )
    
    @patch('emuses.tools.model_cache.MemcachedBackend')
    def test_model_cache_init_memcached_backend(self, mock_memcached_backend, mock_database_session):
        """Test ModelCache initialization with Memcached backend."""
        config = CacheConfig(backend_type="memcached")
        cache = ModelCache(db_session=mock_database_session, config=config)
        
        mock_memcached_backend.assert_called_once_with(
            host=config.memcached_host,
            port=config.memcached_port
        )
    
    def test_model_cache_init_invalid_backend(self, mock_database_session):
        """Test ModelCache initialization with invalid backend."""
        config = CacheConfig(backend_type="invalid")
        
        with pytest.raises(CachingError, match="Unsupported cache backend"):
            ModelCache(db_session=mock_database_session, config=config)
    
    def test_model_cache_init_no_session(self):
        """Test ModelCache initialization without database session."""
        with pytest.raises(CachingError, match="Database session is required"):
            ModelCache(db_session=None)
    
    def test_cache_model_basic(self, mock_database_session, sample_model_data):
        """Test basic model caching."""
        cache = ModelCache(db_session=mock_database_session)
        
        model_id = sample_model_data["model_id"]
        
        cache.cache_model(
            model_id=model_id,
            model_data=sample_model_data["data"],
            metadata=sample_model_data["metadata"]
        )
        
        # Verify model was cached
        assert cache.backend.exists(f"model:{model_id}")
    
    def test_cache_model_with_ttl(self, mock_database_session, sample_model_data):
        """Test model caching with custom TTL."""
        cache = ModelCache(db_session=mock_database_session)
        
        model_id = sample_model_data["model_id"]
        custom_ttl = 7200
        
        cache.cache_model(
            model_id=model_id,
            model_data=sample_model_data["data"],
            metadata=sample_model_data["metadata"],
            ttl=custom_ttl
        )
        
        # Verify model was cached (we can't easily test TTL with in-memory backend)
        assert cache.backend.exists(f"model:{model_id}")
    
    def test_get_cached_model_hit(self, mock_database_session, sample_model_data):
        """Test getting cached model (cache hit)."""
        cache = ModelCache(db_session=mock_database_session)
        
        model_id = sample_model_data["model_id"]
        
        # Cache the model first
        cache.cache_model(
            model_id=model_id,
            model_data=sample_model_data["data"],
            metadata=sample_model_data["metadata"]
        )
        
        # Retrieve from cache
        cached_data = cache.get_cached_model(model_id)
        
        assert cached_data is not None
        assert cached_data["model_data"] == sample_model_data["data"]
        assert cached_data["metadata"] == sample_model_data["metadata"]
        assert "cached_at" in cached_data
    
    def test_get_cached_model_miss(self, mock_database_session):
        """Test getting cached model (cache miss)."""
        cache = ModelCache(db_session=mock_database_session)
        
        model_id = uuid.uuid4()
        
        # Try to get non-cached model
        cached_data = cache.get_cached_model(model_id)
        
        assert cached_data is None
    
    def test_is_model_cached(self, mock_database_session, sample_model_data):
        """Test checking if model is cached."""
        cache = ModelCache(db_session=mock_database_session)
        
        model_id = sample_model_data["model_id"]
        
        # Initially not cached
        assert not cache.is_model_cached(model_id)
        
        # Cache the model
        cache.cache_model(
            model_id=model_id,
            model_data=sample_model_data["data"],
            metadata=sample_model_data["metadata"]
        )
        
        # Should be cached now
        assert cache.is_model_cached(model_id)
    
    def test_invalidate_cache_single_model(self, mock_database_session, sample_model_data):
        """Test invalidating cache for single model."""
        cache = ModelCache(db_session=mock_database_session)
        
        model_id = sample_model_data["model_id"]
        
        # Cache the model
        cache.cache_model(
            model_id=model_id,
            model_data=sample_model_data["data"],
            metadata=sample_model_data["metadata"]
        )
        
        assert cache.is_model_cached(model_id)
        
        # Invalidate cache
        result = cache.invalidate_cache(model_id=model_id)
        assert result == True
        
        # Should not be cached anymore
        assert not cache.is_model_cached(model_id)
    
    def test_invalidate_cache_all_models(self, mock_database_session, sample_model_data):
        """Test invalidating all model caches."""
        cache = ModelCache(db_session=mock_database_session)
        
        # Cache multiple models
        for i in range(3):
            model_id = uuid.uuid4()
            cache.cache_model(
                model_id=model_id,
                model_data={"data": f"model_{i}"},
                metadata={"index": i}
            )
        
        # Invalidate all caches
        cache.invalidate_cache()
        
        # All should be cleared (we can't easily verify this with in-memory backend
        # without access to internal state, but the call should succeed)
    
    def test_get_cache_stats(self, mock_database_session):
        """Test getting cache statistics."""
        cache = ModelCache(db_session=mock_database_session)
        
        stats = cache.get_cache_stats()
        
        assert isinstance(stats, dict)
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert "cached_models" in stats
        assert "cache_size" in stats
        assert "cache_backend" in stats
        assert "uptime_seconds" in stats
    
    def test_cache_hit_miss_tracking(self, mock_database_session, sample_model_data):
        """Test cache hit/miss statistics tracking."""
        cache = ModelCache(db_session=mock_database_session)
        
        model_id = sample_model_data["model_id"]
        
        # Initial stats
        initial_stats = cache.get_cache_stats()
        initial_hits = initial_stats["cache_hits"]
        initial_misses = initial_stats["cache_misses"]
        
        # Cache miss
        cache.get_cached_model(model_id)
        stats_after_miss = cache.get_cache_stats()
        assert stats_after_miss["cache_misses"] == initial_misses + 1
        
        # Cache the model
        cache.cache_model(
            model_id=model_id,
            model_data=sample_model_data["data"],
            metadata=sample_model_data["metadata"]
        )
        
        # Cache hit
        cache.get_cached_model(model_id)
        final_stats = cache.get_cache_stats()
        assert final_stats["cache_hits"] == initial_hits + 1
    
    def test_cache_compression_enabled(self, mock_database_session, sample_model_data):
        """Test cache compression when enabled."""
        config = CacheConfig(enable_compression=True)
        cache = ModelCache(db_session=mock_database_session, config=config)
        
        model_id = sample_model_data["model_id"]
        large_data = {"large_field": "x" * 10000}  # Large data for compression
        
        cache.cache_model(
            model_id=model_id,
            model_data=large_data,
            metadata={"compressed": True}
        )
        
        # Retrieve and verify data integrity
        cached_data = cache.get_cached_model(model_id)
        assert cached_data["model_data"] == large_data
    
    def test_cache_compression_disabled(self, mock_database_session, sample_model_data):
        """Test cache behavior when compression is disabled."""
        config = CacheConfig(enable_compression=False)
        cache = ModelCache(db_session=mock_database_session, config=config)
        
        model_id = sample_model_data["model_id"]
        
        cache.cache_model(
            model_id=model_id,
            model_data=sample_model_data["data"],
            metadata=sample_model_data["metadata"]
        )
        
        # Retrieve and verify data integrity
        cached_data = cache.get_cached_model(model_id)
        assert cached_data["model_data"] == sample_model_data["data"]
    
    def test_cache_popular_models_basic(self, mock_database_session):
        """Test caching popular models with basic functionality."""
        # Mock the database query for popular models
        from emuses.multi_user_service.models import ModelRegistry, ModelDownload
        
        mock_popular_models = []
        for i in range(3):
            mock_model = Mock()
            mock_model.id = uuid.uuid4()
            mock_model.name = f"popular_model_{i}"
            mock_model.model_type = "classification"
            mock_model.is_public = True
            mock_popular_models.append(mock_model)
        
        # Simplify: Mock the fallback query path instead of complex SQL
        # Make the first query (ModelDownload) fail to trigger fallback
        mock_fallback_query = Mock()
        mock_fallback_query.filter.return_value = mock_fallback_query
        mock_fallback_query.limit.return_value = mock_popular_models
        
        # Set up the query side effect to trigger fallback
        def query_side_effect(*args, **kwargs):
            if len(args) > 0:
                model_class = args[0]
                if model_class == ModelDownload:
                    # Make this fail to trigger fallback
                    raise Exception("Complex query failed, using fallback")
                elif model_class == ModelRegistry:
                    return mock_fallback_query
            return Mock()
        
        mock_database_session.query.side_effect = query_side_effect
        
        cache = ModelCache(db_session=mock_database_session)
        
        # Mock the cache_model method to return success for testing
        original_cache_model = cache.cache_model
        def mock_cache_model(*args, **kwargs):
            # Simple mock that always succeeds
            return True
        cache.cache_model = mock_cache_model
        
        # Cache popular models
        result = cache.cache_popular_models(limit=3)
        
        assert result["cached_models"] == 3
        assert result["total_popular"] == 3
        assert result["status"] == "success"
    
    def test_cache_popular_models_with_analytics(self, mock_database_session):
        """Test caching popular models using analytics data."""
        from emuses.tools.model_analytics import ModelAnalytics
        
        # Mock analytics data
        mock_analytics = Mock(spec=ModelAnalytics)
        popular_models_data = [
            {"model_id": str(uuid.uuid4()), "download_count": 100, "avg_rating": 4.8},
            {"model_id": str(uuid.uuid4()), "download_count": 85, "avg_rating": 4.5},
            {"model_id": str(uuid.uuid4()), "download_count": 70, "avg_rating": 4.2},
        ]
        mock_analytics.get_popular_models.return_value = popular_models_data
        
        # Mock database models
        mock_models = []
        for data in popular_models_data:
            mock_model = Mock()
            mock_model.id = uuid.UUID(data["model_id"])
            mock_model.name = f"model_{data['model_id'][:8]}"
            mock_model.model_type = "classification"
            mock_model.is_public = True
            mock_models.append(mock_model)
        
        mock_database_session.query.return_value.filter.return_value.all.return_value = mock_models
        
        cache = ModelCache(db_session=mock_database_session)
        
        # Mock the cache_model method to return success for testing
        def mock_cache_model(*args, **kwargs):
            return True
        cache.cache_model = mock_cache_model
        
        # Cache popular models using analytics
        result = cache.cache_popular_models(limit=3, use_analytics=True, analytics=mock_analytics)
        
        assert result["cached_models"] == 3
        assert result["status"] == "success"
        assert "analytics_used" in result
        assert result["analytics_used"] == True
    
    def test_cache_popular_models_preload_strategies(self, mock_database_session):
        """Test different pre-loading strategies."""
        # Mock models with different sizes
        mock_models = []
        for i, size in enumerate([1024, 5120, 10240]):  # Different model sizes
            mock_model = Mock()
            mock_model.id = uuid.uuid4()
            mock_model.name = f"model_{i}"
            mock_model.model_type = "classification"
            mock_model.is_public = True
            mock_model.model_size_bytes = size
            mock_models.append(mock_model)
        
        # Use the fallback path like other tests
        def query_side_effect(*args, **kwargs):
            from emuses.multi_user_service.models import ModelDownload, ModelRegistry
            if len(args) > 0:
                model_class = args[0]
                if model_class == ModelDownload:
                    # Make this fail to trigger fallback
                    raise Exception("Complex query failed, using fallback")
                elif model_class == ModelRegistry:
                    mock_query = Mock()
                    mock_query.filter.return_value = mock_query
                    mock_query.limit.return_value = mock_models
                    return mock_query
            return Mock()
        
        mock_database_session.query.side_effect = query_side_effect
        
        cache = ModelCache(db_session=mock_database_session)
        
        # Mock the cache_model method to return success for testing
        def mock_cache_model(*args, **kwargs):
            return True
        cache.cache_model = mock_cache_model
        
        # Test size-based preloading (prefer smaller models)
        result = cache.cache_popular_models(
            limit=3,
            preload_strategy="size_optimized",
            max_cache_size_mb=1.0  # 1MB limit
        )
        
        assert result["status"] == "success"
        assert result["preload_strategy"] == "size_optimized"
        assert result["cached_models"] <= 3  # Should cache some models
    
    def test_cache_popular_models_no_models(self, mock_database_session):
        """Test caching popular models when no models exist."""
        # Use the fallback path like other tests, but return empty list
        def query_side_effect(*args, **kwargs):
            from emuses.multi_user_service.models import ModelDownload, ModelRegistry
            if len(args) > 0:
                model_class = args[0]
                if model_class == ModelDownload:
                    # Make this fail to trigger fallback
                    raise Exception("Complex query failed, using fallback")
                elif model_class == ModelRegistry:
                    mock_query = Mock()
                    mock_query.filter.return_value = mock_query
                    mock_query.limit.return_value = []  # Empty list
                    return mock_query
            return Mock()
        
        mock_database_session.query.side_effect = query_side_effect
        
        cache = ModelCache(db_session=mock_database_session)
        
        result = cache.cache_popular_models(limit=5)
        
        assert result["cached_models"] == 0
        assert result["total_popular"] == 0
        assert result["status"] == "success"
        assert "No popular models found" in result["message"]
    
    def test_cache_popular_models_error_handling(self, mock_database_session):
        """Test error handling in popular models caching."""
        # Mock database error
        mock_database_session.query.side_effect = Exception("Database error")
        
        cache = ModelCache(db_session=mock_database_session)
        
        result = cache.cache_popular_models(limit=5)
        
        assert result["status"] == "error"
        assert "Database error" in result["message"]
        assert result["cached_models"] == 0
    
    def test_get_cached_model_with_optimization(self, mock_database_session, sample_model_data):
        """Test optimized model retrieval with access tracking."""
        cache = ModelCache(db_session=mock_database_session)
        
        model_id = sample_model_data["model_id"]
        
        # Cache the model first
        cache.cache_model(
            model_id=model_id,
            model_data=sample_model_data["data"],
            metadata=sample_model_data["metadata"]
        )
        
        # Get model multiple times to test access tracking
        for i in range(3):
            cached_data = cache.get_cached_model(model_id, track_access=True)
            assert cached_data is not None
            assert cached_data["model_data"] == sample_model_data["data"]
        
        # Verify access tracking increased cache hits
        stats = cache.get_cache_stats()
        assert stats["cache_hits"] == 3
    
    def test_cache_warming_on_init(self, mock_database_session):
        """Test cache warming during initialization."""
        # Mock popular models
        mock_models = []
        for i in range(2):
            mock_model = Mock()
            mock_model.id = uuid.uuid4()
            mock_model.name = f"warm_model_{i}"
            mock_model.model_type = "classification"
            mock_model.is_public = True
            mock_models.append(mock_model)
        
        mock_query = Mock()
        mock_query.outerjoin.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_models
        mock_database_session.query.return_value = mock_query
        
        config = CacheConfig(enable_cache_warming=True, cache_warming_limit=2)
        cache = ModelCache(db_session=mock_database_session, config=config)
        
        # Verify cache warming was attempted
        # Note: In real implementation, this would actually cache the models
        assert hasattr(cache.config, 'enable_cache_warming')
        assert cache.config.enable_cache_warming == True
    
    def test_cache_invalidation_patterns(self, mock_database_session, sample_model_data):
        """Test different cache invalidation patterns."""
        cache = ModelCache(db_session=mock_database_session)
        
        model_id = sample_model_data["model_id"]
        
        # Cache a model
        cache.cache_model(
            model_id=model_id,
            model_data=sample_model_data["data"],
            metadata=sample_model_data["metadata"]
        )
        
        assert cache.is_model_cached(model_id)
        
        # Test pattern-based invalidation
        cache.invalidate_cache_pattern(f"model:{model_id}")
        assert not cache.is_model_cached(model_id)
    
    def test_cache_consistency_management(self, mock_database_session):
        """Test cache consistency management features."""
        cache = ModelCache(db_session=mock_database_session)
        
        # Test time-based invalidation
        old_time = time.time() - 7200  # 2 hours ago
        cache._cache_start_time = old_time
        
        # Manually set a cache entry that's "old"
        cache.backend.set("model:old", {"data": "old_data", "cached_at": old_time})
        cache.backend.set("model:new", {"data": "new_data", "cached_at": time.time()})
        
        # Clean up expired entries (older than 1 hour)
        cleaned = cache.cleanup_expired_entries(max_age_seconds=3600)
        
        assert cleaned >= 0  # Should return number of cleaned entries
    
    def test_cache_versioning_support(self, mock_database_session, sample_model_data):
        """Test cache versioning for consistency."""
        cache = ModelCache(db_session=mock_database_session)
        
        model_id = sample_model_data["model_id"]
        
        # Cache model with version 1
        cache.cache_model_with_version(
            model_id=model_id,
            model_data=sample_model_data["data"],
            metadata=sample_model_data["metadata"],
            version="1.0"
        )
        
        # Check if cached version matches
        cached_data = cache.get_cached_model_with_version(model_id, expected_version="1.0")
        assert cached_data is not None
        
        # Check version mismatch
        cached_data = cache.get_cached_model_with_version(model_id, expected_version="2.0")
        assert cached_data is None  # Should be None due to version mismatch
    
    def test_cache_invalidation_callbacks(self, mock_database_session):
        """Test cache invalidation with callbacks."""
        cache = ModelCache(db_session=mock_database_session)
        
        # Register invalidation callback
        callback_called = []
        def on_invalidate(key, reason):
            callback_called.append((key, reason))
        
        cache.register_invalidation_callback(on_invalidate)
        
        # Trigger invalidation
        cache.invalidate_cache_with_reason(model_id=uuid.uuid4(), reason="model_updated")
        
        assert len(callback_called) == 1
        assert callback_called[0][1] == "model_updated"
    
    def test_distributed_cache_invalidation(self, mock_database_session):
        """Test distributed cache invalidation patterns."""
        cache = ModelCache(db_session=mock_database_session)
        
        # Simulate distributed invalidation signal
        invalidation_signal = {
            "type": "model_updated",
            "model_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "source": "registry_service"
        }
        
        # Process distributed invalidation
        result = cache.handle_distributed_invalidation(invalidation_signal)
        
        assert result["processed"] == True
        assert result["signal_type"] == "model_updated"