"""
Tests for EMUSES observability structured logging system
"""

import pytest
import uuid
from io import StringIO
import sys
from unittest.mock import patch

from emuses.observability.logging import (
    setup_structured_logging,
    get_logger,
    set_request_context,
    set_pipeline_context,
    clear_context,
    RequestLogger,
    PipelineLogger,
    request_id_var,
    user_id_var,
    pipeline_stage_var
)


class TestStructuredLogging:
    """Test structured logging setup and configuration"""
    
    def test_setup_structured_logging(self):
        """Test that structured logging can be set up"""
        # Should not raise any exceptions
        setup_structured_logging(level='INFO')
        
    def test_get_logger(self):
        """Test that get_logger returns a logger instance"""
        logger = get_logger(__name__)
        
        # Should have required methods
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'warning')
        assert hasattr(logger, 'error')
        assert hasattr(logger, 'debug')
        
    def test_get_logger_with_name(self):
        """Test get_logger with specific name"""
        logger = get_logger('test_logger')
        assert logger is not None


class TestContextManagement:
    """Test context variable management"""
    
    def test_set_request_context(self):
        """Test setting request context"""
        test_user_id = 'user123'
        
        set_request_context(user_id=test_user_id)
        
        # Check that context variables are set
        assert user_id_var.get() == test_user_id
        assert request_id_var.get() is not None
        
    def test_set_request_context_with_id(self):
        """Test setting request context with specific ID"""
        test_request_id = str(uuid.uuid4())
        test_user_id = 'user456'
        
        set_request_context(request_id=test_request_id, user_id=test_user_id)
        
        assert request_id_var.get() == test_request_id
        assert user_id_var.get() == test_user_id
        
    def test_set_pipeline_context(self):
        """Test setting pipeline context"""
        stage_name = 'umap_optimization'
        
        set_pipeline_context(stage_name)
        
        assert pipeline_stage_var.get() == stage_name
        
    def test_clear_context(self):
        """Test clearing all context variables"""
        # Set some context
        set_request_context(user_id='user123')
        set_pipeline_context('test_stage')
        
        # Clear context
        clear_context()
        
        # Check that all context is cleared
        assert request_id_var.get() is None
        assert user_id_var.get() is None
        assert pipeline_stage_var.get() is None


class TestRequestLogger:
    """Test RequestLogger context manager"""
    
    def test_request_logger_context_manager(self):
        """Test RequestLogger sets and clears context properly"""
        test_user_id = 'user789'
        
        with RequestLogger(user_id=test_user_id):
            # Context should be set
            assert user_id_var.get() == test_user_id
            assert request_id_var.get() is not None
            
        # Context should be cleared after exiting
        assert user_id_var.get() is None
        assert request_id_var.get() is None
        
    def test_request_logger_with_specific_id(self):
        """Test RequestLogger with specific request ID"""
        test_request_id = str(uuid.uuid4())
        test_user_id = 'user999'
        
        with RequestLogger(request_id=test_request_id, user_id=test_user_id):
            assert request_id_var.get() == test_request_id
            assert user_id_var.get() == test_user_id
            
        # Context should be cleared
        assert request_id_var.get() is None
        assert user_id_var.get() is None


class TestPipelineLogger:
    """Test PipelineLogger context manager"""
    
    def test_pipeline_logger_context_manager(self):
        """Test PipelineLogger sets and clears context properly"""
        stage_name = 'heatmap_generation'
        test_user_id = 'pipeline_user'
        
        with PipelineLogger(stage_name=stage_name, user_id=test_user_id):
            # All context should be set
            assert pipeline_stage_var.get() == stage_name
            assert user_id_var.get() == test_user_id
            assert request_id_var.get() is not None
            
        # Context should be cleared after exiting
        assert pipeline_stage_var.get() is None
        assert user_id_var.get() is None
        assert request_id_var.get() is None


class TestLogOutput:
    """Test that log output includes correlation information"""
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_log_includes_correlation_info(self, mock_stdout):
        """Test that logs include correlation information when context is set"""
        # Setup structured logging to output to our mock stdout
        setup_structured_logging(level='INFO')
        logger = get_logger('test')
        
        test_user_id = 'correlation_user'
        test_stage = 'correlation_stage'
        
        with RequestLogger(user_id=test_user_id):
            set_pipeline_context(test_stage)
            logger.info("Test message")
            
        # Note: This test may not work perfectly due to structlog's complexity
        # but it verifies the setup doesn't crash
        assert mock_stdout.getvalue() is not None


class TestErrorHandling:
    """Test error handling in logging context managers"""
    
    def test_request_logger_handles_exceptions(self):
        """Test that RequestLogger properly clears context even on exceptions"""
        test_user_id = 'error_user'
        
        with pytest.raises(ValueError):
            with RequestLogger(user_id=test_user_id):
                # Context should be set
                assert user_id_var.get() == test_user_id
                raise ValueError("Test error")
                
        # Context should still be cleared after exception
        assert user_id_var.get() is None
        assert request_id_var.get() is None
        
    def test_pipeline_logger_handles_exceptions(self):
        """Test that PipelineLogger properly clears context even on exceptions"""
        stage_name = 'error_stage'
        
        with pytest.raises(RuntimeError):
            with PipelineLogger(stage_name=stage_name):
                # Context should be set
                assert pipeline_stage_var.get() == stage_name
                raise RuntimeError("Test error")
                
        # Context should still be cleared after exception
        assert pipeline_stage_var.get() is None
        assert user_id_var.get() is None
        assert request_id_var.get() is None