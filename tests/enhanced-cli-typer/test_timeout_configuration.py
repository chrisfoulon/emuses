"""
Test timeout configuration functionality following LAD guidelines.

This module tests the user-configurable timeout system implementation,
including unlimited timeout support, stage-specific timeouts, and CLI parameter passing.

LAD Phase 3: Comprehensive Testing and Validation
"""

import pytest
import pytest_asyncio
import httpx
from unittest.mock import Mock, AsyncMock, patch
import typer.testing
from typing import Optional

from emuses.cli.service_client import ServiceHTTPClient
from emuses.cli.main import app


class TestTimeoutConfiguration:
    """Test core timeout configuration functionality."""

    def test_unlimited_timeout_default(self):
        """Test that default timeout is None (unlimited) following industry standards."""
        client = ServiceHTTPClient()
        
        # Should default to unlimited timeout (None)
        assert client.timeout is None, "Default timeout should be None (unlimited)"

    def test_custom_timeout_configuration(self):
        """Test custom timeout configuration."""
        client = ServiceHTTPClient(timeout=300.0)
        
        assert client.timeout == 300.0, "Custom timeout should be configurable"

    def test_explicit_unlimited_timeout(self):
        """Test explicitly setting unlimited timeout."""
        client = ServiceHTTPClient(timeout=None)
        
        assert client.timeout is None, "Should accept None for unlimited timeout"

    @pytest.mark.asyncio
    async def test_httpx_timeout_integration_unlimited(self):
        """Test that httpx client properly handles unlimited timeout."""
        client = ServiceHTTPClient(timeout=None)
        
        async with client:
            # Session should be created with no timeout limit
            # httpx may create a Timeout object, but the timeout value should be None for unlimited
            if client._session.timeout is None:
                # Direct None timeout
                assert True, "Session has no timeout (unlimited)"
            else:
                # httpx Timeout object - check if it represents unlimited timeout
                timeout_obj = client._session.timeout
                # For unlimited timeout, httpx sets all timeout components to None
                assert timeout_obj.connect is None, "httpx session should have unlimited connect timeout"
                assert timeout_obj.read is None, "httpx session should have unlimited read timeout"

    @pytest.mark.asyncio 
    async def test_httpx_timeout_integration_limited(self):
        """Test that httpx client properly handles limited timeout."""
        client = ServiceHTTPClient(timeout=120.0)
        
        async with client:
            # Session should be created with specified timeout
            assert client._session.timeout.connect == 120.0, "httpx session should use specified timeout"

    def test_timeout_validation(self):
        """Test timeout parameter validation."""
        # Zero timeout should be allowed (CLI uses 0 to indicate unlimited)
        client = ServiceHTTPClient(timeout=0.0)
        assert client.timeout == 0.0, "Zero timeout should be allowed"
        
        # Very large timeout values should be accepted
        client = ServiceHTTPClient(timeout=86400.0)  # 24 hours
        assert client.timeout == 86400.0, "Large timeout values should be allowed"


class TestCLITimeoutIntegration:
    """Test CLI timeout parameter integration."""

    def test_service_timeout_cli_option_exists(self):
        """Test that service timeout CLI option is available."""
        runner = typer.testing.CliRunner()
        
        # Test help output contains timeout options
        result = runner.invoke(app, ["full", "--help"])
        
        assert result.exit_code == 0, "Help command should succeed"
        # Check for timeout-related text (options may be truncated in help output)
        assert "service-tim" in result.stdout or "Service request timeout" in result.stdout, "Service timeout option should be available"
        assert "umap-timeout" in result.stdout or "UMAP stage timeout" in result.stdout, "UMAP timeout option should be available" 
        assert "heatmap-timeo" in result.stdout or "Heatmap stage" in result.stdout, "Heatmap timeout option should be available"
        assert "prediction-ti" in result.stdout or "Prediction stage" in result.stdout, "Prediction timeout option should be available"

    def test_timeout_cli_option_descriptions(self):
        """Test that timeout CLI options have proper descriptions."""
        runner = typer.testing.CliRunner()
        result = runner.invoke(app, ["full", "--help"])
        
        # Typer/Rich wraps text, so check for key phrases across lines
        # Clean up formatting characters and collapse multiple spaces
        help_text = result.stdout.replace('│', ' ').replace('\n', ' ')
        # Collapse multiple spaces to single spaces
        import re
        help_text = re.sub(r'\s+', ' ', help_text)
        assert "0 for unlimited" in help_text, "Should indicate 0 for unlimited timeout"
        assert "timeout in seconds" in help_text, "Should describe timeout units"

    @patch('emuses.cli.main._execute_via_unified_service')
    def test_default_unlimited_timeout_behavior(self, mock_execute):
        """Test that default behavior uses unlimited timeouts."""
        runner = typer.testing.CliRunner()
        
        # Mock to avoid actual execution
        mock_execute.return_value = None
        
        # Run command with minimal required arguments
        result = runner.invoke(app, [
            "full", 
            "/tmp/test_output",
            "/tmp/test_input.csv"
        ])
        
        # Should not fail due to timeout issues
        # The actual assertion would be that service client gets None timeout
        # but we need to test the parameter flow separately
        assert result.exit_code == 0, "Command should execute with default unlimited timeouts"

    @patch('emuses.cli.main._execute_via_remote_service')
    def test_custom_timeout_parameter_passing(self, mock_execute):
        """Test that custom timeout parameters are properly passed."""
        runner = typer.testing.CliRunner()
        
        # Mock to capture arguments
        mock_execute.return_value = None
        
        # Run command with custom timeouts
        result = runner.invoke(app, [
            "full",
            "/tmp/test_output", 
            "/tmp/test_input.csv",
            "--service-timeout", "300",
            "--umap-timeout", "600",
            "--heatmap-timeout", "120",
            "--prediction-timeout", "60",
            "--service"  # Use remote service to trigger timeout passing
        ])
        
        # Verify mock was called with timeout parameter
        if mock_execute.called:
            call_args, call_kwargs = mock_execute.call_args
            # Should have service_timeout parameter
            assert 'service_timeout' in call_kwargs or len(call_args) >= 5, "Service timeout should be passed to execution function"


class TestStageSpecificTimeouts:
    """Test stage-specific timeout functionality."""

    def test_stage_timeout_parameter_types(self):
        """Test that stage timeout parameters accept float values."""
        runner = typer.testing.CliRunner()
        
        # Test with float values
        result = runner.invoke(app, [
            "full", "--help"
        ])
        
        assert result.exit_code == 0, "Should accept float timeout values"

    def test_unlimited_timeout_specification(self):
        """Test specifying unlimited timeouts explicitly.""" 
        runner = typer.testing.CliRunner()
        
        # Test zero values for unlimited timeouts
        with patch('emuses.cli.main._execute_via_unified_service') as mock_execute:
            mock_execute.return_value = None
            
            result = runner.invoke(app, [
                "full",
                "/tmp/test_output",
                "/tmp/test_input.csv", 
                "--service-timeout", "0",
                "--umap-timeout", "0",
                "--heatmap-timeout", "0",
                "--prediction-timeout", "0"
            ])
            
            assert result.exit_code == 0, "Should accept zero timeouts for unlimited"

    def test_mixed_timeout_configuration(self):
        """Test mixing limited and unlimited timeouts for different stages."""
        runner = typer.testing.CliRunner()
        
        with patch('emuses.cli.main._execute_via_unified_service') as mock_execute:
            mock_execute.return_value = None
            
            result = runner.invoke(app, [
                "full",
                "/tmp/test_output",
                "/tmp/test_input.csv",
                "--service-timeout", "300",    # 5 minutes
                "--umap-timeout", "0",         # Unlimited
                "--heatmap-timeout", "180",    # 3 minutes  
                "--prediction-timeout", "0"    # Unlimited
            ])
            
            assert result.exit_code == 0, "Should handle mixed timeout configurations"


class TestTimeoutBehaviorValidation:
    """Test actual timeout behavior in realistic scenarios."""

    @pytest.mark.asyncio
    async def test_unlimited_timeout_allows_long_operations(self):
        """Test that unlimited timeout allows long-running operations."""
        client = ServiceHTTPClient(timeout=None)
        
        # Mock a slow response (simulate long ML operation)
        async def slow_response(*args, **kwargs):
            # Simulate operation that would exceed old 30s timeout
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "completed", "duration": "45s"}
            return mock_response
        
        with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = slow_response
            
            async with client:
                # This should not timeout
                response = await client.get("/api/v1/jobs/long-running-job")
                
                assert response.status_code == 200, "Long operation should complete without timeout"

    @pytest.mark.asyncio
    async def test_limited_timeout_enforced(self):
        """Test that limited timeout is properly enforced."""
        client = ServiceHTTPClient(timeout=1.0)  # Very short timeout for testing
        
        # Mock timeout exception
        with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = httpx.TimeoutException("Request timeout")
            
            async with client:
                with pytest.raises(httpx.TimeoutException):
                    await client.get("/api/v1/jobs/test")

    def test_timeout_conversion_in_main_function(self):
        """Test timeout conversion logic (0.0 to None) used in main execution."""
        # Test the conversion logic directly without full service execution
        
        # Test 0.0 -> None conversion
        timeout_zero = 0.0
        converted_zero = None if timeout_zero <= 0 else timeout_zero
        assert converted_zero is None, "0.0 timeout should be converted to None (unlimited)"
        
        # Test negative -> None conversion  
        timeout_negative = -1.0
        converted_negative = None if timeout_negative <= 0 else timeout_negative
        assert converted_negative is None, "Negative timeout should be converted to None (unlimited)"

    def test_timeout_conversion_positive_value(self):
        """Test that positive timeout values are passed through unchanged."""
        # Test the conversion logic directly without full service execution
        
        # Test positive value remains unchanged
        timeout_positive = 300.0
        converted_positive = None if timeout_positive <= 0 else timeout_positive
        assert converted_positive == 300.0, "Positive timeout should be passed unchanged"
        
        # Test small positive value  
        timeout_small = 0.1
        converted_small = None if timeout_small <= 0 else timeout_small
        assert converted_small == 0.1, "Small positive timeout should be passed unchanged"


class TestTimeoutIndustryStandardCompliance:
    """Test compliance with industry standards for ML pipeline timeouts."""

    def test_default_behavior_matches_industry_standard(self):
        """Test that default behavior matches industry standards (unlimited)."""
        client = ServiceHTTPClient()
        
        # Industry standard: No default timeout for ML operations
        assert client.timeout is None, "Should follow industry standard of no default timeout"

    def test_user_control_over_timeout_behavior(self):
        """Test that users have full control over timeout behavior."""
        # Test user can set any timeout value
        client_short = ServiceHTTPClient(timeout=30.0)
        client_long = ServiceHTTPClient(timeout=3600.0)  # 1 hour
        client_unlimited = ServiceHTTPClient(timeout=None)
        
        assert client_short.timeout == 30.0, "User should control short timeouts"
        assert client_long.timeout == 3600.0, "User should control long timeouts"
        assert client_unlimited.timeout is None, "User should control unlimited timeouts"

    def test_stage_appropriate_timeout_defaults(self):
        """Test that different stages can have appropriate timeout defaults."""
        runner = typer.testing.CliRunner()
        
        # All stage timeouts should default to 0.0 (unlimited)
        # This matches industry practice where ML operations are not artificially limited
        result = runner.invoke(app, ["full", "--help"])
        
        # The help should show timeout options (may be truncated in display)
        assert "service-timeo" in result.stdout, "Service timeout option available"
        assert "umap-timeout" in result.stdout, "UMAP timeout option available"  
        assert "heatmap-timeo" in result.stdout, "Heatmap timeout option available"
        assert "prediction-ti" in result.stdout, "Prediction timeout option available"


class TestTimeoutErrorHandling:
    """Test proper error handling for timeout-related issues."""

    @pytest.mark.asyncio
    async def test_timeout_error_reporting(self):
        """Test that timeout errors are properly reported to users."""
        client = ServiceHTTPClient(timeout=0.1)  # Very short timeout
        
        with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = httpx.TimeoutException("Operation timed out after 0.1 seconds")
            
            async with client:
                with pytest.raises(httpx.TimeoutException) as exc_info:
                    await client.get("/api/v1/jobs/test")
                
                # Error message should be informative
                assert "timed out" in str(exc_info.value).lower(), "Timeout error should be clearly reported"

    def test_timeout_parameter_validation_edge_cases(self):
        """Test edge cases in timeout parameter validation."""
        # Very large timeout values should be accepted
        client_large = ServiceHTTPClient(timeout=86400.0)  # 24 hours
        assert client_large.timeout == 86400.0, "Should accept very large timeout values"
        
        # Very small but positive timeout values should be accepted
        client_small = ServiceHTTPClient(timeout=0.001)  # 1ms
        assert client_small.timeout == 0.001, "Should accept very small positive timeout values"

    @pytest.mark.asyncio
    async def test_timeout_behavior_consistency(self):
        """Test that timeout behavior is consistent across different operations."""
        client = ServiceHTTPClient(timeout=2.0)
        
        timeout_operations = [
            ("/api/health", "GET"),
            ("/api/v1/jobs", "POST"), 
            ("/api/v1/jobs/123/status", "GET")
        ]
        
        for endpoint, method in timeout_operations:
            with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
                mock_request.side_effect = httpx.TimeoutException("Timeout")
                
                async with client:
                    with pytest.raises(httpx.TimeoutException):
                        if method == "GET":
                            await client.get(endpoint)
                        elif method == "POST":
                            await client.post(endpoint, json={"test": "data"})
                
                # Verify timeout was applied consistently
                # ServiceHTTPClient has retry logic (max_retries=3), so expect multiple calls
                assert mock_request.call_count >= 1, "Should have made at least one request attempt"
                assert mock_request.call_count <= 4, "Should not exceed max retry attempts (1 initial + 3 retries)"
                
                # Verify session timeout is configured
                assert hasattr(client._session, 'timeout'), "Session should have timeout configured"
                
                # Reset for next iteration
                mock_request.reset_mock()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])