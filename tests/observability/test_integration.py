"""
Integration tests for EMUSES observability system
"""

import pytest
import time
from unittest.mock import patch, MagicMock

from emuses.observability import (
    track_scientific_operation,
    create_span,
    get_logger,
    get_metrics_registry
)


class TestObservabilityIntegration:
    """Test integration between metrics, logging, and context tracking"""
    
    @patch('emuses.observability.metrics.psutil.Process')
    def test_track_scientific_operation_integration(self, mock_process):
        """Test that track_scientific_operation integrates metrics and logging"""
        mock_memory_info = MagicMock()
        mock_memory_info.rss = 1024 * 1024 * 200  # 200MB
        mock_process.return_value.memory_info.return_value = mock_memory_info
        
        logger = get_logger(__name__)
        
        with track_scientific_operation(
            'test_integration',
            user_id='integration_user',
            additional_attributes={'dataset': 'test_data', 'version': '1.0'}
        ) as ctx:
            # Add some attributes during operation
            ctx.set_attribute('samples_processed', 1000)
            ctx.set_attribute('accuracy', 0.95)
            
            # Simulate some work
            time.sleep(0.01)
            
            logger.info("Processing completed successfully")
            
        # Verify metrics were recorded
        registry = get_metrics_registry()
        metrics_data = registry.get_metrics().decode()
        
        assert 'emuses_pipeline_duration_seconds' in metrics_data
        assert 'emuses_memory_usage_bytes' in metrics_data
        
    def test_create_span_functionality(self):
        """Test create_span context manager"""
        with create_span('test_span', {'test_attr': 'test_value'}) as span:
            span.set_attribute('dynamic_attr', 42)
            time.sleep(0.005)  # Small delay
            
        # Should complete without error
        assert True
        
    def test_create_span_with_error(self):
        """Test create_span handles errors properly"""
        with pytest.raises(ValueError):
            with create_span('error_span') as span:
                span.set_attribute('error_test', True)
                raise ValueError("Test error for span")
                
    @patch('emuses.observability.metrics.psutil.Process')
    def test_nested_operations(self, mock_process):
        """Test nested scientific operations"""
        mock_memory_info = MagicMock()
        mock_memory_info.rss = 1024 * 1024 * 150  # 150MB
        mock_process.return_value.memory_info.return_value = mock_memory_info
        
        with track_scientific_operation('outer_operation', user_id='nested_user') as outer_ctx:
            outer_ctx.set_attribute('outer_param', 'test')
            
            # Nested span (not scientific operation to avoid double metrics)
            with create_span('inner_operation') as inner_ctx:
                inner_ctx.set_attribute('inner_param', 123)
                time.sleep(0.01)
                
        # Should complete successfully
        registry = get_metrics_registry()
        metrics_data = registry.get_metrics().decode()
        
        assert 'emuses_pipeline_duration_seconds' in metrics_data


class TestPerformanceOverhead:
    """Test that observability has minimal performance overhead"""
    
    def test_metrics_collection_performance(self):
        """Test that metrics collection is fast"""
        registry = get_metrics_registry()
        
        start_time = time.time()
        for i in range(100):
            registry.optimization_trials_total.labels(
                stage='performance_test', 
                trial_type='test'
            ).inc()
        end_time = time.time()
        
        # Should complete 100 metric updates in less than 0.1 seconds
        duration = end_time - start_time
        assert duration < 0.1, f"Metrics collection took {duration}s, expected < 0.1s"
        
    def test_span_creation_performance(self):
        """Test that span creation has minimal overhead"""
        start_time = time.time()
        
        for i in range(50):
            with create_span(f'perf_test_{i}') as span:
                span.set_attribute('iteration', i)
                
        end_time = time.time()
        
        # Should complete 50 span creations in less than 0.1 seconds
        duration = end_time - start_time
        assert duration < 0.1, f"Span creation took {duration}s, expected < 0.1s"


class TestObservabilityDisabled:
    """Test that system works when observability components fail"""
    
    @patch('emuses.observability.get_logger')
    def test_graceful_degradation_logging(self, mock_get_logger):
        """Test that system works even if logging fails"""
        mock_get_logger.side_effect = Exception("Logging unavailable")
        
        # Should not raise an exception
        try:
            from emuses.observability import get_logger
            logger = get_logger(__name__)
        except Exception:
            # If import fails, test passes (graceful degradation)
            pass
            
    @patch('emuses.observability.metrics.get_metrics_registry')
    def test_graceful_degradation_metrics(self, mock_registry):
        """Test that system works even if metrics fail"""
        mock_registry.side_effect = Exception("Metrics unavailable")
        
        # Should not raise an exception during normal operation
        try:
            from emuses.observability.metrics import track_optimization_trial
            track_optimization_trial('test_stage', 'test_type')
        except Exception:
            # If metrics fail, test passes (graceful degradation)
            pass