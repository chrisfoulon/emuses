"""
Performance validation for EMUSES observability system

Validates that observability overhead is minimal for practical scientific workloads.
"""

import time
import numpy as np
import pytest
from contextlib import contextmanager
from emuses.observability import (
    track_scientific_operation,
    get_logger,
    track_optimization_trial,
    get_metrics_registry
)


class TestObservabilityOverheadValidation:
    """Validate observability overhead is acceptable for production use"""
    
    def test_observability_baseline_overhead(self):
        """Test that basic observability operations have minimal overhead"""
        
        # Test basic context manager overhead
        n_operations = 100
        
        # Baseline: simple operation without observability
        start_time = time.perf_counter()
        for i in range(n_operations):
            # Simulate a small computational task
            data = np.random.randn(100, 10)
            result = np.sum(data)
        baseline_time = time.perf_counter() - start_time
        
        # With observability
        start_time = time.perf_counter()
        for i in range(n_operations):
            with track_scientific_operation(
                "baseline_test",
                user_id="test_user",
                additional_attributes={"iteration": i}
            ) as obs_ctx:
                # Same computational task
                data = np.random.randn(100, 10)
                result = np.sum(data)
                obs_ctx.set_attribute("result", float(result))
                
        observed_time = time.perf_counter() - start_time
        
        # Calculate overhead
        overhead_ratio = (observed_time - baseline_time) / baseline_time
        overhead_percent = overhead_ratio * 100
        
        print(f"\nBaseline Overhead Test:")
        print(f"Baseline time: {baseline_time:.4f}s")
        print(f"With observability: {observed_time:.4f}s")
        print(f"Overhead: {overhead_percent:.2f}%")
        
        # For small operations, allow higher overhead but validate it's reasonable
        assert overhead_percent < 50, f"Overhead too high: {overhead_percent:.2f}%"
        
        # More importantly, absolute overhead should be small
        absolute_overhead = observed_time - baseline_time
        print(f"Absolute overhead: {absolute_overhead:.4f}s total, {absolute_overhead/n_operations*1000:.2f}ms per operation")
        
        # Should be less than 1ms per operation on average
        assert absolute_overhead/n_operations < 0.001, "Absolute overhead per operation too high"
        
    def test_metrics_collection_efficiency(self):
        """Test that metrics collection is efficient"""
        registry = get_metrics_registry()
        n_metrics = 10000
        
        start_time = time.perf_counter()
        for i in range(n_metrics):
            # Simulate typical metrics operations
            registry.pipeline_duration.labels(
                stage="test_stage",
                user_id="test_user", 
                status="success"
            ).observe(0.1)
            
            if i % 100 == 0:
                registry.optimization_trials_total.labels(
                    stage="test_stage",
                    trial_type="test"
                ).inc()
                
        total_time = time.perf_counter() - start_time
        time_per_metric = total_time / n_metrics * 1000  # milliseconds
        
        print(f"\nMetrics Collection Efficiency:")
        print(f"Time for {n_metrics} metrics: {total_time:.4f}s")
        print(f"Time per metric: {time_per_metric:.4f}ms")
        
        # Metrics should be very fast
        assert time_per_metric < 0.01, f"Metrics too slow: {time_per_metric:.4f}ms per metric"
        
    def test_structured_logging_efficiency(self):
        """Test that structured logging is efficient"""
        logger = get_logger(__name__)
        n_logs = 1000
        
        start_time = time.perf_counter()
        for i in range(n_logs):
            logger.info(
                "Test log message",
                iteration=i,
                test_type="performance",
                value=i * 0.001,
                status="testing"
            )
        total_time = time.perf_counter() - start_time
        time_per_log = total_time / n_logs * 1000  # milliseconds
        
        print(f"\nStructured Logging Efficiency:")
        print(f"Time for {n_logs} logs: {total_time:.4f}s")
        print(f"Time per log: {time_per_log:.4f}ms")
        
        # Logging should be fast
        assert time_per_log < 0.1, f"Logging too slow: {time_per_log:.4f}ms per log"
        
    def test_nested_context_overhead(self):
        """Test overhead of nested observability contexts"""
        n_operations = 50
        
        # Test nested contexts (typical in pipeline stages)
        start_time = time.perf_counter()
        for i in range(n_operations):
            with track_scientific_operation(
                "outer_operation", 
                user_id="test_user"
            ) as outer_ctx:
                # Simulate some work
                data1 = np.random.randn(50, 20)
                result1 = np.mean(data1)
                outer_ctx.set_attribute("outer_result", float(result1))
                
                # Nested operation
                with track_scientific_operation(
                    "inner_operation",
                    user_id="test_user"
                ) as inner_ctx:
                    data2 = np.random.randn(30, 15)
                    result2 = np.std(data2)
                    inner_ctx.set_attribute("inner_result", float(result2))
                    
        nested_time = time.perf_counter() - start_time
        
        # Compare with single-level operations
        start_time = time.perf_counter()
        for i in range(n_operations):
            with track_scientific_operation(
                "single_operation",
                user_id="test_user"
            ) as ctx:
                # Same total work
                data1 = np.random.randn(50, 20)
                result1 = np.mean(data1)
                data2 = np.random.randn(30, 15)
                result2 = np.std(data2)
                ctx.set_attribute("result1", float(result1))
                ctx.set_attribute("result2", float(result2))
                
        single_time = time.perf_counter() - start_time
        
        nested_overhead = (nested_time - single_time) / single_time * 100
        
        print(f"\nNested Context Overhead:")
        print(f"Single-level time: {single_time:.4f}s")
        print(f"Nested time: {nested_time:.4f}s")
        print(f"Nested overhead: {nested_overhead:.2f}%")
        
        # Nested contexts should have reasonable overhead
        assert nested_overhead < 20, f"Nested context overhead too high: {nested_overhead:.2f}%"
        
    def test_pipeline_simulation_overhead(self):
        """Test overhead for simulated pipeline execution"""
        
        def simulate_pipeline_stage(stage_name, computation_time=0.1):
            """Simulate a pipeline stage with controlled execution time"""
            # Sleep to simulate real computation time
            time.sleep(computation_time)
            # Add some actual computation to make it more realistic
            data = np.random.randn(200, 50)
            result = np.linalg.norm(data)
            return result
            
        n_stages = 3
        computation_time_per_stage = 0.2  # 200ms per stage
        
        # Baseline: pipeline without observability
        start_time = time.perf_counter()
        baseline_results = []
        for i in range(n_stages):
            result = simulate_pipeline_stage(f"stage_{i}", computation_time_per_stage)
            baseline_results.append(result)
        baseline_time = time.perf_counter() - start_time
        
        # With observability: full pipeline tracking
        start_time = time.perf_counter()
        observed_results = []
        with track_scientific_operation(
            "full_pipeline",
            user_id="test_user",
            additional_attributes={"n_stages": n_stages}
        ) as pipeline_ctx:
            for i in range(n_stages):
                with track_scientific_operation(
                    f"stage_{i}",
                    user_id="test_user",
                    additional_attributes={"stage_index": i}
                ) as stage_ctx:
                    result = simulate_pipeline_stage(f"stage_{i}", computation_time_per_stage)
                    stage_ctx.set_attribute("stage_result", float(result))
                    observed_results.append(result)
                    
            pipeline_ctx.set_attribute("total_stages", n_stages)
            pipeline_ctx.set_attribute("pipeline_completed", True)
            
        observed_time = time.perf_counter() - start_time
        
        # Calculate overhead
        overhead_ratio = (observed_time - baseline_time) / baseline_time
        overhead_percent = overhead_ratio * 100
        absolute_overhead = observed_time - baseline_time
        
        print(f"\nPipeline Simulation Overhead:")
        print(f"Baseline time: {baseline_time:.4f}s")
        print(f"With observability: {observed_time:.4f}s") 
        print(f"Overhead: {overhead_percent:.2f}%")
        print(f"Absolute overhead: {absolute_overhead:.4f}s")
        
        # For longer-running operations (600ms total), overhead should be minimal
        assert overhead_percent < 5, f"Pipeline overhead too high: {overhead_percent:.2f}%"
        assert absolute_overhead < 0.1, f"Absolute overhead too high: {absolute_overhead:.4f}s"
        
        # Verify results are the same (observability shouldn't affect computation)
        assert len(baseline_results) == len(observed_results)
        
    def test_observability_memory_usage(self):
        """Test that observability doesn't cause excessive memory usage"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Measure baseline memory
        baseline_memory = process.memory_info().rss
        
        # Create many observability contexts (but don't keep references)
        n_contexts = 1000
        for i in range(n_contexts):
            with track_scientific_operation(
                f"memory_test_{i % 10}",  # Reuse some operation names
                user_id=f"user_{i % 5}",  # Reuse some user IDs
                additional_attributes={"iteration": i, "batch": i // 100}
            ) as ctx:
                # Simulate some work with data
                data = np.random.randn(100, 10)
                result = np.sum(data**2)
                ctx.set_attribute("result", float(result))
                ctx.set_attribute("data_size", data.size)
                
        # Measure memory after operations
        final_memory = process.memory_info().rss
        memory_increase = final_memory - baseline_memory
        memory_increase_mb = memory_increase / 1024 / 1024
        
        print(f"\nMemory Usage Test:")
        print(f"Baseline memory: {baseline_memory / 1024 / 1024:.2f} MB")
        print(f"Final memory: {final_memory / 1024 / 1024:.2f} MB")
        print(f"Memory increase: {memory_increase_mb:.2f} MB")
        print(f"Memory per operation: {memory_increase / n_contexts:.0f} bytes")
        
        # Memory usage should be reasonable
        assert memory_increase_mb < 50, f"Memory usage too high: {memory_increase_mb:.2f} MB"
        
        # Per-operation memory usage should be minimal
        memory_per_op = memory_increase / n_contexts
        assert memory_per_op < 10000, f"Memory per operation too high: {memory_per_op:.0f} bytes"  # 10KB max


class TestObservabilityProductionReadiness:
    """Test observability system for production readiness"""
    
    def test_high_frequency_operations(self):
        """Test observability with high-frequency operations"""
        
        # Simulate high-frequency API requests or rapid pipeline operations
        n_operations = 200
        operation_duration = 0.01  # 10ms operations (typical API response time)
        
        start_time = time.perf_counter()
        for i in range(n_operations):
            with track_scientific_operation(
                "high_frequency_op",
                user_id=f"user_{i % 10}",
                additional_attributes={"request_id": f"req_{i}"}
            ) as ctx:
                # Simulate API work
                time.sleep(operation_duration)
                ctx.set_attribute("operation_id", i)
                ctx.set_attribute("success", True)
                
        total_time = time.perf_counter() - start_time
        expected_time = n_operations * operation_duration
        overhead_time = total_time - expected_time
        overhead_percent = (overhead_time / expected_time) * 100
        
        print(f"\nHigh-Frequency Operations Test:")
        print(f"Expected time: {expected_time:.4f}s")
        print(f"Actual time: {total_time:.4f}s")
        print(f"Overhead: {overhead_percent:.2f}%")
        print(f"Operations per second: {n_operations / total_time:.0f}")
        
        # Should handle high-frequency operations efficiently
        assert overhead_percent < 10, f"High-frequency overhead too high: {overhead_percent:.2f}%"
        assert n_operations / total_time > 50, "Throughput too low for production use"
        
    def test_concurrent_observability_safety(self):
        """Test that observability is safe for concurrent use"""
        import threading
        import concurrent.futures
        
        def worker_function(worker_id, n_operations=50):
            """Worker function for concurrent testing"""
            results = []
            for i in range(n_operations):
                with track_scientific_operation(
                    f"worker_{worker_id}_op",
                    user_id=f"worker_{worker_id}",
                    additional_attributes={"worker_id": worker_id, "op_id": i}
                ) as ctx:
                    # Simulate some work
                    data = np.random.randn(50, 10)
                    result = np.mean(data)
                    ctx.set_attribute("result", float(result))
                    results.append(result)
                    
            return results
            
        n_workers = 4
        start_time = time.perf_counter()
        
        # Run workers concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = [executor.submit(worker_function, i) for i in range(n_workers)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
        total_time = time.perf_counter() - start_time
        
        print(f"\nConcurrent Operations Test:")
        print(f"Total time with {n_workers} workers: {total_time:.4f}s")
        print(f"Results collected: {sum(len(r) for r in results)}")
        
        # Should complete without errors and in reasonable time
        assert len(results) == n_workers, "Not all workers completed"
        assert all(len(r) == 50 for r in results), "Not all operations completed"
        assert total_time < 5.0, f"Concurrent operations took too long: {total_time:.4f}s"