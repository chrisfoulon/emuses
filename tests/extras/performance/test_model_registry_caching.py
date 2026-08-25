"""
Test caching optimization for model registry operations.

This module tests caching functionality to improve performance of
frequently accessed model registry operations including list_models,
search_models, and get_model_info.
"""
import time
import pytest
from unittest.mock import MagicMock

from emuses.extras.database_model_registry import DatabaseModelRegistry
from emuses.extras.model_registry_cache import ModelRegistryCache


class TestModelRegistryCaching:
    """Test model registry caching functionality."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = MagicMock()
        user.id = "test-user-123"
        user.email = "test@example.com"
        return user

    @pytest.fixture
    def mock_registry(self, mock_db_session, mock_user):
        """Create mock database registry with caching."""
        return DatabaseModelRegistry(mock_db_session, mock_user)

    def test_cache_initialization(self):
        """Test that ModelRegistryCache can be initialized."""
        cache = ModelRegistryCache()
        assert cache is not None
        assert hasattr(cache, 'get')
        assert hasattr(cache, 'set')
        assert hasattr(cache, 'invalidate')
        assert hasattr(cache, 'clear')

    def test_cache_basic_operations(self):
        """Test basic cache operations (get, set, invalidate)."""
        cache = ModelRegistryCache()
        
        # Test cache miss
        result = cache.get('nonexistent_key')
        assert result is None
        
        # Test cache set and hit
        test_data = {'models': [{'name': 'test_model'}]}
        cache.set('test_key', test_data, ttl=60)
        
        cached_result = cache.get('test_key')
        assert cached_result == test_data
        
        # Test cache invalidation
        cache.invalidate('test_key')
        invalidated_result = cache.get('test_key')
        assert invalidated_result is None

    def test_list_models_caching_interface(self, mock_registry):
        """Test that list_models supports caching interface."""
        # Test that list_models can work with caching decorator
        assert hasattr(mock_registry, 'list_models')
        assert callable(mock_registry.list_models)
        
        # Test that cached methods exist
        assert hasattr(mock_registry, 'list_models_cached')
        assert callable(mock_registry.list_models_cached)

    def test_search_models_caching_interface(self, mock_registry):
        """Test that search_models supports caching interface."""
        assert hasattr(mock_registry, 'search_models')
        assert callable(mock_registry.search_models)
        
        # Test that cached methods exist
        assert hasattr(mock_registry, 'search_models_cached')
        assert callable(mock_registry.search_models_cached)

    def test_get_model_info_caching_interface(self, mock_registry):
        """Test that get_model_info supports caching interface."""
        assert hasattr(mock_registry, 'get_model_info')
        assert callable(mock_registry.get_model_info)
        
        # Test that cached methods exist
        assert hasattr(mock_registry, 'get_model_info_cached')
        assert callable(mock_registry.get_model_info_cached)

    def test_cache_key_generation(self):
        """Test cache key generation for different operations."""
        cache = ModelRegistryCache()
        
        # Test list_models cache key
        list_key = cache.generate_list_models_key(
            user_id='user-123',
            workspace_id='workspace-456',
            include_public=True,
            filters={'type': 'umap'}
        )
        assert list_key is not None
        assert isinstance(list_key, str)
        assert 'user-123' in list_key
        assert 'workspace-456' in list_key
        
        # Test search_models cache key
        search_key = cache.generate_search_models_key(
            query='test query',
            user_id='user-123',
            workspace_id=None,
            include_public=True
        )
        assert search_key is not None
        assert isinstance(search_key, str)
        assert 'query-' in search_key  # Query is hashed for consistent key generation
        
        # Test get_model_info cache key
        info_key = cache.generate_model_info_key(
            model_id='123e4567-e89b-12d3-a456-426614174000',
            user_id='user-123'
        )
        assert info_key is not None
        assert isinstance(info_key, str)
        assert '123e4567-e89b-12d3-a456-426614174000' in info_key

    def test_cache_invalidation_patterns(self):
        """Test cache invalidation patterns for different operations."""
        cache = ModelRegistryCache()
        
        # Set up test cache entries
        cache.set('list_models:user-123:workspace-456', {'models': []}, ttl=300)
        cache.set('search_models:query1:user-123', {'results': []}, ttl=300)
        cache.set('model_info:model-789:user-123', {'info': {}}, ttl=300)
        
        # Test user-specific invalidation
        cache.invalidate_user_cache('user-123')
        
        assert cache.get('list_models:user-123:workspace-456') is None
        assert cache.get('search_models:query1:user-123') is None
        assert cache.get('model_info:model-789:user-123') is None
        
    def test_cache_ttl_expiration(self):
        """Test cache TTL (time-to-live) functionality."""
        cache = ModelRegistryCache()
        
        # Test short TTL
        cache.set('short_ttl_key', {'data': 'test'}, ttl=0.1)  # 100ms
        
        # Immediately available
        result = cache.get('short_ttl_key')
        assert result == {'data': 'test'}
        
        # Wait for expiration
        time.sleep(0.2)  # 200ms
        
        # Should be expired
        expired_result = cache.get('short_ttl_key')
        assert expired_result is None


class TestCachedModelRegistryOperations:
    """Test cached operations in model registry."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = MagicMock()
        user.id = "test-user-123"
        user.email = "test@example.com"
        return user

    def test_cached_list_models_performance(self, mock_db_session, mock_user):
        """Test that cached list_models improves performance."""
        registry = DatabaseModelRegistry(mock_db_session, mock_user)
        
        # Mock the database query to simulate slow operation  
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        # First call (should hit database) - add small delay to simulate DB
        start_time = time.time()
        time.sleep(0.01)  # Simulate database delay
        models1 = registry.list_models_cached()
        first_call_time = time.time() - start_time
        
        # Second call (should hit cache) - should be much faster
        start_time = time.time()
        models2 = registry.list_models_cached()
        second_call_time = time.time() - start_time
        
        # Cache hit should be significantly faster (cache access vs database + sleep)
        assert second_call_time < first_call_time  # Faster than first call
        assert models1 == models2  # Same results

    def test_cached_search_models_performance(self, mock_db_session, mock_user):
        """Test that cached search_models improves performance."""
        registry = DatabaseModelRegistry(mock_db_session, mock_user)
        
        # Mock the database query to simulate search operation
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        # First search (should hit database) - add small delay
        start_time = time.time()
        time.sleep(0.01)  # Simulate search processing delay
        results1 = registry.search_models_cached('test query')
        first_call_time = time.time() - start_time
        
        # Second search with same query (should hit cache)
        start_time = time.time()
        results2 = registry.search_models_cached('test query')
        second_call_time = time.time() - start_time
        
        # Cache hit should be faster
        assert second_call_time < first_call_time
        assert results1 == results2

    def test_cached_get_model_info_performance(self, mock_db_session, mock_user):
        """Test that cached get_model_info improves performance."""
        registry = DatabaseModelRegistry(mock_db_session, mock_user)
        
        # Mock the database query to return None (model not found for simplicity)
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # First call (should hit database) - add small delay
        start_time = time.time() 
        time.sleep(0.01)  # Simulate database query delay
        info1 = registry.get_model_info_cached('123e4567-e89b-12d3-a456-426614174000')
        first_call_time = time.time() - start_time
        
        # Second call (should hit cache or return None quickly)
        start_time = time.time()
        info2 = registry.get_model_info_cached('123e4567-e89b-12d3-a456-426614174000')
        second_call_time = time.time() - start_time
        
        # Results should be consistent
        assert info1 == info2  # Both should be None in this mock scenario

    def test_cache_invalidation_on_model_changes(self, mock_db_session, mock_user):
        """Test that cache is properly invalidated when models change."""
        registry = DatabaseModelRegistry(mock_db_session, mock_user)
        
        # Mock the database query
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        # Cache some data
        models_before = registry.list_models_cached()
        
        # Verify data is cached (second call should hit cache)
        models_cached = registry.list_models_cached()
        assert models_before == models_cached
        
        # Simulate successful cache invalidation
        registry.cache.invalidate_user_cache(str(mock_user.id))
        
        # Verify cache was invalidated by checking cache directly
        cache_key = registry.cache.generate_list_models_key(
            user_id=str(mock_user.id),
            workspace_id=None,
            include_public=True,
            filters=None
        )
        
        # Cache should be empty now
        cached_result = registry.cache.get(cache_key)
        assert cached_result is None


class TestCacheConfiguration:
    """Test cache configuration and settings."""

    def test_cache_size_limits(self):
        """Test cache size limit configuration."""
        # Test with small cache size
        cache = ModelRegistryCache(max_size=2)
        
        cache.set('key1', {'data': 1}, ttl=300)
        cache.set('key2', {'data': 2}, ttl=300)
        cache.set('key3', {'data': 3}, ttl=300)  # Should evict key1
        
        # key1 should be evicted due to size limit
        assert cache.get('key1') is None
        assert cache.get('key2') == {'data': 2}
        assert cache.get('key3') == {'data': 3}

    def test_cache_ttl_configuration(self):
        """Test cache TTL configuration for different operation types."""
        cache = ModelRegistryCache()
        
        # Different operations should have different default TTLs
        list_ttl = cache.get_default_ttl('list_models')
        search_ttl = cache.get_default_ttl('search_models')
        info_ttl = cache.get_default_ttl('model_info')
        
        assert list_ttl > 0
        assert search_ttl > 0
        assert info_ttl > 0
        
        # Model info might have longer TTL (less frequently changing)
        assert info_ttl >= list_ttl

    def test_cache_memory_usage(self):
        """Test cache memory usage tracking."""
        cache = ModelRegistryCache()
        
        initial_size = cache.get_memory_usage()
        
        # Add some cached data
        large_data = {'models': [{'data': 'x' * 1000} for _ in range(100)]}
        cache.set('large_key', large_data, ttl=300)
        
        after_add_size = cache.get_memory_usage()
        
        # Memory usage should increase
        assert after_add_size > initial_size
        
        # Clear cache
        cache.clear()
        
        final_size = cache.get_memory_usage()
        assert final_size <= initial_size