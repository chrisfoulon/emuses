"""
Tests for graceful shutdown functionality in EMUSES CLI.

This module tests the SimpleShutdownHandler and KeyboardInterrupt enhancements
to ensure proper graceful shutdown behavior with user confirmation.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from emuses.cli.shutdown_handler import SimpleShutdownHandler, ShutdownError


class TestSimpleShutdownHandler:
    """Test cases for the SimpleShutdownHandler class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_service_client = Mock()
        self.test_job_id = "test_job_123"
        self.handler = SimpleShutdownHandler(self.mock_service_client, self.test_job_id)

    @pytest.mark.asyncio
    async def test_shutdown_confirmation_yes(self):
        """Test user confirms shutdown - should return True."""
        # Mock service response
        self.mock_service_client.get_job_status = AsyncMock(return_value={
            "status": "running",
            "progress": 0.45,  # 45%
            "message": "HCP optimization (Trial 23/50)",
            "current_stage": "umap_optimization"
        })
        
        # Mock user input 'yes'
        with patch('builtins.input', return_value='y'):
            result = await self.handler.handle_interruption()
            
        assert result is True
        self.mock_service_client.get_job_status.assert_called_once_with(self.test_job_id)

    @pytest.mark.asyncio
    async def test_shutdown_confirmation_no(self):
        """Test user cancels shutdown - should return False."""
        # Mock service response
        self.mock_service_client.get_job_status = AsyncMock(return_value={
            "status": "running",
            "progress": 0.75,  # 75%
            "message": "Prediction model training (Fold 3/5)"
        })
        
        # Mock user input 'no'
        with patch('builtins.input', return_value='n'):
            result = await self.handler.handle_interruption()
            
        assert result is False
        self.mock_service_client.get_job_status.assert_called_once_with(self.test_job_id)

    @pytest.mark.asyncio
    async def test_shutdown_confirmation_empty_input(self):
        """Test empty input (default 'no') - should return False."""
        # Mock service response
        self.mock_service_client.get_job_status = AsyncMock(return_value={
            "status": "running",
            "message": "Processing..."
        })
        
        # Mock empty user input (default to 'no')
        with patch('builtins.input', return_value=''):
            result = await self.handler.handle_interruption()
            
        assert result is False

    @pytest.mark.asyncio
    async def test_shutdown_confirmation_yes_variations(self):
        """Test various 'yes' input variations."""
        # Mock service response
        self.mock_service_client.get_job_status = AsyncMock(return_value={
            "status": "running"
        })
        
        # Test different yes variations
        yes_inputs = ['y', 'Y', 'yes', 'YES', 'Yes', ' y ', ' yes ']
        
        for yes_input in yes_inputs:
            with patch('builtins.input', return_value=yes_input):
                result = await self.handler.handle_interruption()
            assert result is True, f"Input '{yes_input}' should be interpreted as 'yes'"

    @pytest.mark.asyncio
    async def test_shutdown_service_unavailable(self):
        """Test graceful degradation when service status fails."""
        # Mock service client to raise exception
        self.mock_service_client.get_job_status = AsyncMock(
            side_effect=Exception("Service unreachable")
        )
        
        # Mock user input 'yes' despite service error
        with patch('builtins.input', return_value='y'):
            result = await self.handler.handle_interruption()
            
        assert result is True
        self.mock_service_client.get_job_status.assert_called_once_with(self.test_job_id)

    @pytest.mark.asyncio
    async def test_shutdown_service_unavailable_cancel(self):
        """Test graceful degradation when service fails but user cancels."""
        # Mock service client to raise exception
        self.mock_service_client.get_job_status = AsyncMock(
            side_effect=Exception("Connection timeout")
        )
        
        # Mock user input 'no' despite service error
        with patch('builtins.input', return_value='n'):
            result = await self.handler.handle_interruption()
            
        assert result is False

    @pytest.mark.asyncio
    async def test_display_progress_percentage(self):
        """Test proper display of progress percentage."""
        # Mock service response with decimal progress
        self.mock_service_client.get_job_status = AsyncMock(return_value={
            "status": "running",
            "progress": 0.67,  # Should display as 67.0%
            "message": "Optimization in progress"
        })
        
        with patch('builtins.input', return_value='n'), \
             patch('builtins.print') as mock_print:
            await self.handler.handle_interruption()
            
        # Check that progress was formatted correctly
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        progress_printed = any("67.0% complete" in call for call in print_calls)
        assert progress_printed, "Progress percentage should be displayed correctly"

    @pytest.mark.asyncio
    async def test_display_current_stage(self):
        """Test display of current stage information."""
        # Mock service response with stage information
        self.mock_service_client.get_job_status = AsyncMock(return_value={
            "status": "running",
            "current_stage": "heatmap_optimization",
            "message": "Training prediction models"
        })
        
        with patch('builtins.input', return_value='n'), \
             patch('builtins.print') as mock_print:
            await self.handler.handle_interruption()
            
        # Check that stage information was displayed
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        stage_printed = any("heatmap_optimization" in call for call in print_calls)
        assert stage_printed, "Current stage should be displayed"

    @pytest.mark.asyncio
    async def test_cleanup_and_stop_success(self):
        """Test successful cleanup and service stop."""
        # Mock successful operations
        self.mock_service_client.cancel_job = AsyncMock()
        
        with patch('emuses.cli.service_manager.ServiceManager') as mock_service_manager_class, \
             patch('builtins.print') as mock_print:
            mock_service_manager = Mock()
            mock_service_manager_class.return_value = mock_service_manager
            
            await self.handler.cleanup_and_stop()
            
        # Verify operations were called
        self.mock_service_client.cancel_job.assert_called_once_with(self.test_job_id)
        mock_service_manager.stop_service.assert_called_once()
        
        # Check success message was printed
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        success_printed = any("successfully" in call for call in print_calls)
        assert success_printed, "Success message should be displayed"

    @pytest.mark.asyncio
    async def test_cleanup_and_stop_failure(self):
        """Test cleanup handles failures gracefully."""
        # Mock operations to fail
        self.mock_service_client.cancel_job = AsyncMock(
            side_effect=Exception("Cancel failed")
        )
        
        with patch('emuses.cli.service_manager.ServiceManager') as mock_service_manager_class, \
             patch('builtins.print') as mock_print:
            mock_service_manager = Mock()
            mock_service_manager.stop_service.side_effect = Exception("Stop failed")
            mock_service_manager_class.return_value = mock_service_manager
            
            # Should not raise exception, just print warning
            await self.handler.cleanup_and_stop()
            
        # Check warning message was printed
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        warning_printed = any("warning" in call.lower() for call in print_calls)
        assert warning_printed, "Warning message should be displayed on failure"

    @pytest.mark.asyncio
    async def test_progress_display_edge_cases(self):
        """Test progress display with edge case values."""
        test_cases = [
            {"progress": 1.0, "expected": "100.0%"},  # Full completion
            {"progress": 0.0, "expected": "0.0%"},   # Just started
            {"progress": 100, "expected": "100.0%"},  # Already percentage format (>1, so used as-is)
            {"progress": None, "expected": None},     # No progress available
        ]
        
        for case in test_cases:
            self.mock_service_client.get_job_status = AsyncMock(return_value={
                "status": "running",
                "progress": case["progress"],
                "message": "Test case"
            })
            
            with patch('builtins.input', return_value='n'), \
                 patch('builtins.print') as mock_print:
                await self.handler.handle_interruption()
                
            if case["expected"]:
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                progress_printed = any(case["expected"] in call for call in print_calls)
                assert progress_printed, f"Progress {case['progress']} should display as {case['expected']}"


class TestShutdownIntegration:
    """Integration tests for shutdown handler in CLI context."""

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_integration(self):
        """Test that KeyboardInterrupt is properly handled in CLI context."""
        # This test would require more complex mocking of the full CLI flow
        # For now, we verify the handler can be imported and instantiated
        from emuses.cli.shutdown_handler import SimpleShutdownHandler
        
        mock_client = Mock()
        handler = SimpleShutdownHandler(mock_client, "test_job")
        
        assert handler.service_client == mock_client
        assert handler.job_id == "test_job"

    def test_shutdown_error_exception(self):
        """Test ShutdownError exception class."""
        from emuses.cli.shutdown_handler import ShutdownError
        
        error = ShutdownError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)


if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__])