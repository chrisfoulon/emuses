"""
Tests for EMUSES observability metrics system
"""

import pytest
import time
from unittest.mock import patch, MagicMock

from emuses.observability.metrics import (
    MetricsRegistry, 
    track_pipeline_stage,
    track_dataset_size,
    track_optimization_trial,
    track_http_request,
    get_metrics_registry
)


class TestMetricsRegistry:
    """Test the MetricsRegistry class"""
    
    def test_metrics_registry_initialization(self):
        """Test that MetricsRegistry initializes properly"""
        registry = MetricsRegistry()
        
        # Check that metrics are created
        assert registry.pipeline_duration is not None
        assert registry.pipeline_errors_total is not None
        assert registry.optimization_trials_total is not None
        assert registry.memory_usage_bytes is not None
        assert registry.active_jobs is not None
        assert registry.dataset_size_bytes is not None
        assert registry.http_requests_total is not None
        assert registry.http_request_duration_seconds is not None
        
    def test_get_metrics_output(self):
        """Test that metrics can be exported in Prometheus format"""
        registry = MetricsRegistry()
        metrics_data = registry.get_metrics()
        
        # Should return bytes
        assert isinstance(metrics_data, bytes)
        
        # Should contain some metric names
        metrics_str = metrics_data.decode()
        assert 'emuses_pipeline_duration_seconds' in metrics_str
        assert 'emuses_http_requests_total' in metrics_str
        
    def test_get_content_type(self):
        """Test that correct content type is returned"""
        registry = MetricsRegistry()
        content_type = registry.get_content_type()
        
        assert content_type == 'text/plain; version=0.0.4; charset=utf-8'


class TestPipelineTracking:
    """Test pipeline stage tracking functionality"""
    
    @patch('emuses.observability.metrics.psutil.Process')
    def test_track_pipeline_stage_success(self, mock_process):
        """Test successful pipeline stage tracking"""
        mock_memory_info = MagicMock()
        mock_memory_info.rss = 1024 * 1024 * 100  # 100MB
        mock_process.return_value.memory_info.return_value = mock_memory_info
        
        with track_pipeline_stage('test_stage', 'user123'):
            time.sleep(0.01)  # Small delay to ensure measurable duration
            
        # Get current metrics to verify they were recorded
        registry = get_metrics_registry()
        metrics_data = registry.get_metrics().decode()
        
        # Should contain pipeline duration metric
        assert 'emuses_pipeline_duration_seconds' in metrics_data
        
    @patch('emuses.observability.metrics.psutil.Process')
    def test_track_pipeline_stage_error(self, mock_process):
        """Test pipeline stage tracking with error"""
        mock_memory_info = MagicMock()
        mock_memory_info.rss = 1024 * 1024 * 100  # 100MB
        mock_process.return_value.memory_info.return_value = mock_memory_info
        
        with pytest.raises(ValueError):
            with track_pipeline_stage('test_stage', 'user123'):
                raise ValueError("Test error")
                
        # Get current metrics to verify error was recorded
        registry = get_metrics_registry()
        metrics_data = registry.get_metrics().decode()
        
        # Should contain error metrics
        assert 'emuses_pipeline_errors_total' in metrics_data


class TestDatasetTracking:
    """Test dataset size tracking"""
    
    def test_track_dataset_size(self):
        """Test dataset size tracking"""
        track_dataset_size(1024 * 1024, 'test_dataset')  # 1MB
        
        registry = get_metrics_registry()
        metrics_data = registry.get_metrics().decode()
        
        assert 'emuses_dataset_size_bytes' in metrics_data


class TestOptimizationTracking:
    """Test optimization trial tracking"""
    
    def test_track_optimization_trial(self):
        """Test optimization trial tracking"""
        track_optimization_trial('umap_optimization', 'main')
        
        registry = get_metrics_registry()
        metrics_data = registry.get_metrics().decode()
        
        assert 'emuses_optimization_trials_total' in metrics_data


class TestHTTPTracking:
    """Test HTTP request tracking"""
    
    def test_track_http_request_success(self):
        """Test successful HTTP request tracking"""
        with track_http_request('GET', '/api/health'):
            time.sleep(0.01)  # Small delay
            
        registry = get_metrics_registry()
        metrics_data = registry.get_metrics().decode()
        
        assert 'emuses_http_requests_total' in metrics_data
        assert 'emuses_http_request_duration_seconds' in metrics_data
        
    def test_track_http_request_error(self):
        """Test HTTP request tracking with error"""
        
        class TestHTTPException(Exception):
            def __init__(self):
                self.status_code = 404
                
        with pytest.raises(TestHTTPException):
            with track_http_request('GET', '/api/nonexistent'):
                raise TestHTTPException()
                
        registry = get_metrics_registry()
        metrics_data = registry.get_metrics().decode()
        
        assert 'emuses_http_requests_total' in metrics_data


class TestGlobalRegistry:
    """Test global registry functionality"""
    
    def test_get_metrics_registry_singleton(self):
        """Test that get_metrics_registry returns the same instance"""
        registry1 = get_metrics_registry()
        registry2 = get_metrics_registry()
        
        assert registry1 is registry2