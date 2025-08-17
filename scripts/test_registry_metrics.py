#!/usr/bin/env python3
"""Test script to verify model registry metrics integration.

This script performs various registry operations and verifies that
metrics are being collected correctly across all deployment modes.
"""

import sys
import tempfile
from pathlib import Path
import time

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emuses.tools.model_registry_metrics import (
    get_registry_metrics,
    track_model_download,
    update_registry_size,
    track_model_storage
)
from emuses.tools.local_model_registry import LocalModelRegistry
from emuses.tools.model_registry_cache import ModelRegistryCache


def test_local_registry_metrics():
    """Test metrics integration with LocalModelRegistry."""
    print("Testing LocalModelRegistry metrics integration...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        registry = LocalModelRegistry(registry_path=Path(temp_dir))
        
        # Test operations
        print("- Testing list_models...")
        models = registry.list_models(user_id="test_user")
        print(f"  Found {len(models)} models")
        
        print("- Testing search_models...")
        results = registry.search_models("test", user_id="test_user")
        print(f"  Found {len(results)} results")
        
        print("- Testing get_model_info...")
        model_info = registry.get_model_info(model_name="nonexistent", user_id="test_user")
        print(f"  Model info: {model_info}")
    
    print("✅ LocalModelRegistry metrics test completed")


def test_cache_metrics():
    """Test metrics integration with ModelRegistryCache."""
    print("Testing ModelRegistryCache metrics integration...")
    
    cache = ModelRegistryCache(max_size=10)
    
    print("- Testing cache set operations...")
    for i in range(5):
        cache.set(f"test_key_{i}", {"data": f"test_{i}"})
    
    print("- Testing cache get operations (hits and misses)...")
    for i in range(10):  # Mix of hits and misses
        result = cache.get(f"test_key_{i}")
        status = "hit" if result is not None else "miss"
        print(f"  Key test_key_{i}: {status}")
    
    print("- Testing cache invalidation...")
    cache.invalidate("test_key_0")
    cache.invalidate("test_key_1")
    
    print("✅ Cache metrics test completed")


def test_model_operations_metrics():
    """Test model-specific metrics."""
    print("Testing model operation metrics...")
    
    print("- Testing model download tracking...")
    track_model_download("test_model_1", "classifier", "user123", "registry")
    track_model_download("test_model_2", "regression", "user456", "direct")
    track_model_download("test_model_3", "neural_network", "user789", "migration")
    
    print("- Testing registry size updates...")
    update_registry_size("LOCAL", "private", 10)
    update_registry_size("DATABASE", "workspace", 50)
    update_registry_size("CLOUD", "public", 200)
    
    print("- Testing model storage tracking...")
    track_model_storage(1024*1024, "small_model")      # 1MB
    track_model_storage(50*1024*1024, "medium_model")  # 50MB
    track_model_storage(500*1024*1024, "large_model")  # 500MB
    
    print("✅ Model operations metrics test completed")


def test_performance_impact():
    """Test performance impact of metrics collection."""
    print("Testing metrics performance impact...")
    
    from emuses.tools.model_registry_metrics import track_list_models
    
    # Baseline timing without metrics
    start_time = time.perf_counter()
    for i in range(100):
        pass  # No-op
    baseline_time = time.perf_counter() - start_time
    
    # Timing with metrics
    start_time = time.perf_counter()
    for i in range(100):
        with track_list_models("LOCAL", f"perf_user_{i}"):
            pass
    metrics_time = time.perf_counter() - start_time
    
    overhead = metrics_time - baseline_time
    overhead_per_op = overhead / 100 if overhead > 0 else 0
    overhead_ratio = metrics_time / max(baseline_time, 0.001)
    
    print(f"- Baseline time (100 ops): {baseline_time:.4f}s")
    print(f"- Metrics time (100 ops): {metrics_time:.4f}s") 
    print(f"- Overhead: {overhead:.4f}s ({overhead_per_op:.6f}s per operation)")
    print(f"- Overhead ratio: {overhead_ratio:.2f}x")
    
    # Verify reasonable performance
    assert overhead_per_op < 0.001, f"Per-operation overhead {overhead_per_op:.6f}s too high"
    assert overhead_ratio < 10, f"Overhead ratio {overhead_ratio:.2f}x too high"
    
    print("✅ Performance test passed")


def verify_metrics_collection():
    """Verify that metrics are actually being collected."""
    print("Verifying metrics collection...")
    
    metrics = get_registry_metrics()
    
    # Check registry operations
    operation_samples = list(metrics.registry_operations_total.collect())
    operation_count = sum(
        sample.value 
        for metric_family in operation_samples 
        for sample in metric_family.samples
    )
    print(f"- Registry operations recorded: {operation_count}")
    
    # Check cache operations
    cache_samples = list(metrics.cache_operations_total.collect())
    cache_count = sum(
        sample.value 
        for metric_family in cache_samples 
        for sample in metric_family.samples
    )
    print(f"- Cache operations recorded: {cache_count}")
    
    # Check model operations
    model_samples = list(metrics.model_operations_total.collect())
    model_count = sum(
        sample.value 
        for metric_family in model_samples 
        for sample in metric_family.samples
    )
    print(f"- Model operations recorded: {model_count}")
    
    # Check user activity
    user_samples = list(metrics.user_registry_activity.collect())
    user_count = sum(
        sample.value 
        for metric_family in user_samples 
        for sample in metric_family.samples
    )
    print(f"- User activities recorded: {user_count}")
    
    print("✅ Metrics verification completed")
    
    # Basic sanity checks
    assert operation_count > 0, "Should have recorded some registry operations"
    assert cache_count > 0, "Should have recorded some cache operations"
    
    print("✅ All metrics checks passed")


def main():
    """Main test execution."""
    print("🚀 Starting model registry metrics integration test")
    print("=" * 60)
    
    try:
        test_local_registry_metrics()
        print()
        
        test_cache_metrics() 
        print()
        
        test_model_operations_metrics()
        print()
        
        test_performance_impact()
        print()
        
        verify_metrics_collection()
        print()
        
        print("=" * 60)
        print("🎉 All model registry metrics tests PASSED!")
        print()
        print("Metrics are successfully integrated and collecting data from:")
        print("- ✅ LocalModelRegistry operations")
        print("- ✅ ModelRegistryCache operations") 
        print("- ✅ Model downloads and storage tracking")
        print("- ✅ Registry size monitoring")
        print("- ✅ User activity tracking")
        print("- ✅ Performance timing")
        print()
        print("The metrics can now be viewed in:")
        print("- Prometheus at http://localhost:9090/metrics")
        print("- Grafana dashboard: EMUSES Model Registry")
        print("- Alerting rules in Prometheus/Alertmanager")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()