"""Tests for model registry metrics integration."""

import pytest
import time
from unittest.mock import patch, MagicMock
from pathlib import Path

from emuses.tools.model_registry_metrics import (
    ModelRegistryMetrics,
    get_registry_metrics,
    track_list_models,
    track_install_model,
    track_search_models,
    track_get_model_info,
    track_remove_model,
    track_model_download,
    update_registry_size,
    track_model_storage,
    track_cache_hit,
    track_cache_miss,
    track_cache_set,
    track_cache_invalidate
)


class TestModelRegistryMetrics:
    """Test model registry metrics functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ModelRegistryMetrics()

    def test_track_operation_success(self):
        """Test successful operation tracking."""
        # Get initial count
        initial_samples = list(self.metrics.registry_operations_total.collect())
        initial_count = sum(sample.value for metric_family in initial_samples 
                          for sample in metric_family.samples)
        
        with self.metrics.track_operation("list_models", "LOCAL", "user123"):
            # Simulate successful operation
            pass
        
        # Verify metrics were recorded
        final_samples = list(self.metrics.registry_operations_total.collect())
        final_count = sum(sample.value for metric_family in final_samples 
                        for sample in metric_family.samples)
        
        assert final_count > initial_count, "Operation metric should have increased"

    def test_track_operation_error(self):
        """Test error operation tracking."""
        with pytest.raises(ValueError, match="test error"):
            with self.metrics.track_operation("install_model", "DATABASE", "user456"):
                raise ValueError("test error")
        
        # Verify error metrics were recorded
        registry_ops = self.metrics.registry_operations_total._value._value
        assert any(
            labels.get('operation') == 'install_model' and 
            labels.get('registry_mode') == 'DATABASE' and
            labels.get('status') == 'error'
            for labels, value in registry_ops.items()
            if value > 0
        )

    def test_track_model_download(self):
        """Test model download tracking."""
        self.metrics.track_model_download(
            "model123", 
            "classifier", 
            "user789",
            "registry"
        )
        
        # Verify download was tracked (implementation-specific verification)
        # Since we're using prometheus_client metrics, we check the internal state
        from emuses.observability.metrics import model_downloads_total
        downloads = model_downloads_total._value._value
        assert any(
            labels.get('model_id') == 'model123' and
            labels.get('model_type') == 'classifier' and
            labels.get('user_id') == 'user789' and
            labels.get('download_method') == 'registry'
            for labels, value in downloads.items()
            if value > 0
        )

    def test_update_registry_size(self):
        """Test registry size updates."""
        self.metrics.update_registry_size("LOCAL", "private", 42)
        
        # Verify size was updated
        from emuses.observability.metrics import model_registry_size
        size_metrics = model_registry_size._value._value
        assert any(
            labels.get('registry_type') == 'LOCAL' and
            labels.get('visibility') == 'private'
            for labels, value in size_metrics.items()
            if value == 42
        )

    def test_track_model_storage(self):
        """Test model storage tracking."""
        self.metrics.track_model_storage(1024*1024, "deep_learning")  # 1MB
        
        # Verify storage was tracked in histogram
        from emuses.observability.metrics import model_storage_bytes
        assert model_storage_bytes._sum._value > 0

    def test_track_cache_operation(self):
        """Test cache operation tracking."""
        self.metrics.track_cache_operation("get", "hit")
        self.metrics.track_cache_operation("get", "miss")
        self.metrics.track_cache_operation("set", "success")
        self.metrics.track_cache_operation("invalidate", "success")
        
        # Verify cache operations were tracked
        cache_ops = self.metrics.cache_operations_total._value._value
        
        # Check for hit operation
        assert any(
            labels.get('operation') == 'get' and labels.get('result') == 'hit'
            for labels, value in cache_ops.items()
            if value > 0
        )
        
        # Check for miss operation
        assert any(
            labels.get('operation') == 'get' and labels.get('result') == 'miss'
            for labels, value in cache_ops.items()
            if value > 0
        )

    def test_context_manager_timing(self):
        """Test that context manager tracks timing."""
        start_time = time.perf_counter()
        
        with self.metrics.track_operation("search_models", "CLOUD", "user999"):
            time.sleep(0.01)  # Sleep 10ms
        
        end_time = time.perf_counter()
        duration = end_time - start_time
        
        # Verify timing was recorded (check if histogram has samples)
        duration_histogram = self.metrics.registry_operation_duration
        assert duration_histogram._count._value > 0
        assert duration_histogram._sum._value > 0

    def test_user_activity_tracking(self):
        """Test user activity tracking."""
        with self.metrics.track_operation("remove_model", "DATABASE", "user111", "classifier"):
            pass
        
        # Verify user activity was tracked
        user_activity = self.metrics.user_registry_activity._value._value
        assert any(
            labels.get('user_id') == 'user111' and
            labels.get('operation') == 'remove_model' and
            labels.get('registry_mode') == 'DATABASE'
            for labels, value in user_activity.items()
            if value > 0
        )

    def test_model_operation_tracking(self):
        """Test model operation tracking with type."""
        with self.metrics.track_operation("install_model", "LOCAL", "user222", "regression"):
            pass
        
        # Verify model operation was tracked
        model_ops = self.metrics.model_operations_total._value._value
        assert any(
            labels.get('operation') == 'install_model' and
            labels.get('model_type') == 'regression' and
            labels.get('status') == 'success' and
            labels.get('registry_mode') == 'LOCAL'
            for labels, value in model_ops.items()
            if value > 0
        )


class TestConvenienceFunctions:
    """Test convenience functions for common operations."""

    def test_track_list_models(self):
        """Test list_models tracking convenience function."""
        with track_list_models("DATABASE", "user333"):
            pass
        
        metrics = get_registry_metrics()
        registry_ops = metrics.registry_operations_total._value._value
        assert any(
            labels.get('operation') == 'list_models' and
            labels.get('registry_mode') == 'DATABASE'
            for labels, value in registry_ops.items()
            if value > 0
        )

    def test_track_install_model(self):
        """Test install_model tracking convenience function."""
        with track_install_model("CLOUD", "neural_network", "user444"):
            pass
        
        metrics = get_registry_metrics()
        model_ops = metrics.model_operations_total._value._value
        assert any(
            labels.get('operation') == 'install_model' and
            labels.get('model_type') == 'neural_network' and
            labels.get('registry_mode') == 'CLOUD'
            for labels, value in model_ops.items()
            if value > 0
        )

    def test_track_search_models(self):
        """Test search_models tracking convenience function."""
        with track_search_models("LOCAL", "user555"):
            pass
        
        metrics = get_registry_metrics()
        registry_ops = metrics.registry_operations_total._value._value
        assert any(
            labels.get('operation') == 'search_models' and
            labels.get('registry_mode') == 'LOCAL'
            for labels, value in registry_ops.items()
            if value > 0
        )

    def test_track_get_model_info(self):
        """Test get_model_info tracking convenience function."""
        with track_get_model_info("DATABASE", "user666"):
            pass
        
        metrics = get_registry_metrics()
        registry_ops = metrics.registry_operations_total._value._value
        assert any(
            labels.get('operation') == 'get_model_info' and
            labels.get('registry_mode') == 'DATABASE'
            for labels, value in registry_ops.items()
            if value > 0
        )

    def test_track_remove_model(self):
        """Test remove_model tracking convenience function."""
        with track_remove_model("CLOUD", "ensemble", "user777"):
            pass
        
        metrics = get_registry_metrics()
        model_ops = metrics.model_operations_total._value._value
        assert any(
            labels.get('operation') == 'remove_model' and
            labels.get('model_type') == 'ensemble' and
            labels.get('registry_mode') == 'CLOUD'
            for labels, value in model_ops.items()
            if value > 0
        )

    def test_track_model_download_function(self):
        """Test model download tracking convenience function."""
        track_model_download("model999", "transformer", "user888", "direct")
        
        from emuses.observability.metrics import model_downloads_total
        downloads = model_downloads_total._value._value
        assert any(
            labels.get('model_id') == 'model999' and
            labels.get('model_type') == 'transformer' and
            labels.get('user_id') == 'user888' and
            labels.get('download_method') == 'direct'
            for labels, value in downloads.items()
            if value > 0
        )

    def test_update_registry_size_function(self):
        """Test registry size update convenience function."""
        update_registry_size("LOCAL", "public", 150)
        
        from emuses.observability.metrics import model_registry_size
        size_metrics = model_registry_size._value._value
        assert any(
            labels.get('registry_type') == 'LOCAL' and
            labels.get('visibility') == 'public'
            for labels, value in size_metrics.items()
            if value == 150
        )

    def test_track_model_storage_function(self):
        """Test model storage tracking convenience function."""
        track_model_storage(2048*1024, "cnn")  # 2MB
        
        from emuses.observability.metrics import model_storage_bytes
        assert model_storage_bytes._sum._value > 0

    def test_cache_tracking_functions(self):
        """Test cache tracking convenience functions."""
        track_cache_hit()
        track_cache_miss()
        track_cache_set()
        track_cache_invalidate()
        
        metrics = get_registry_metrics()
        cache_ops = metrics.cache_operations_total._value._value
        
        # Check all operations were recorded
        operations = [('get', 'hit'), ('get', 'miss'), ('set', 'success'), ('invalidate', 'success')]
        for operation, result in operations:
            assert any(
                labels.get('operation') == operation and labels.get('result') == result
                for labels, value in cache_ops.items()
                if value > 0
            ), f"Cache operation {operation}:{result} not found"


class TestMetricsIntegration:
    """Test metrics integration with actual registry operations."""
    
    @pytest.fixture
    def temp_registry_path(self, tmp_path):
        """Create temporary registry path."""
        return tmp_path / "test_registry"

    def test_local_registry_metrics_integration(self, temp_registry_path):
        """Test metrics integration with LocalModelRegistry."""
        from emuses.tools.local_model_registry import LocalModelRegistry
        
        # Create registry instance
        registry = LocalModelRegistry(registry_path=temp_registry_path)
        
        # Test list_models with metrics
        models = registry.list_models(user_id="test_user")
        assert isinstance(models, list)
        
        # Verify metrics were recorded
        metrics = get_registry_metrics()
        registry_ops = metrics.registry_operations_total._value._value
        assert any(
            labels.get('operation') == 'list_models' and
            labels.get('registry_mode') == 'LOCAL'
            for labels, value in registry_ops.items()
            if value > 0
        )

    def test_cache_metrics_integration(self):
        """Test metrics integration with ModelRegistryCache."""
        from emuses.tools.model_registry_cache import ModelRegistryCache
        
        # Create cache instance
        cache = ModelRegistryCache()
        
        # Test cache operations with metrics
        cache.set("test_key", {"data": "test"})
        result = cache.get("test_key")  # Should be a hit
        assert result == {"data": "test"}
        
        result = cache.get("nonexistent_key")  # Should be a miss
        assert result is None
        
        cache.invalidate("test_key")
        
        # Verify cache metrics were recorded
        metrics = get_registry_metrics()
        cache_ops = metrics.cache_operations_total._value._value
        
        # Should have recorded hit, miss, set, and invalidate
        operations = [('get', 'hit'), ('get', 'miss'), ('set', 'success'), ('invalidate', 'success')]
        for operation, result in operations:
            assert any(
                labels.get('operation') == operation and labels.get('result') == result
                for labels, value in cache_ops.items()
                if value > 0
            ), f"Cache operation {operation}:{result} not recorded"

    def test_error_tracking_integration(self, temp_registry_path):
        """Test error tracking in registry operations."""
        from emuses.tools.local_model_registry import LocalModelRegistry
        
        registry = LocalModelRegistry(registry_path=temp_registry_path)
        
        # Try to get info for nonexistent model
        result = registry.get_model_info(model_name="nonexistent", user_id="test_user")
        assert result is None
        
        # Verify operation was tracked (even though it returned None)
        metrics = get_registry_metrics()
        registry_ops = metrics.registry_operations_total._value._value
        assert any(
            labels.get('operation') == 'get_model_info' and
            labels.get('registry_mode') == 'LOCAL'
            for labels, value in registry_ops.items()
            if value > 0
        )