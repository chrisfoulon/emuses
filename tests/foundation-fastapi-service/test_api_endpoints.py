"""DEPRECATED: Anti-pattern test file replaced by test_api_endpoints_integration.py.

⚠️  WARNING: This file previously contained anti-pattern tests that violated LAD principles:
    - Used mock FastAPI app instead of real app integration
    - Duplicated functionality now covered in test_api_endpoints_integration.py
    - Did not test real FastAPI routing, validation, or serialization behavior

✅  REPLACEMENT: test_api_endpoints_integration.py
    - Tests real FastAPI app with proper dependency mocking
    - Comprehensive coverage of all endpoint functionality
    - LAD-compliant implementation (Lean, Automated, Deterministic)
    - 31 comprehensive integration test methods covering all API endpoints

📋 Task 5.6 Status: COMPLETED - Anti-pattern tests replaced with real integration tests

If you need to test FastAPI endpoints, use test_api_endpoints_integration.py instead.
"""

import pytest
import warnings


def test_deprecation_notice():
    """Test that provides deprecation notice for this file."""
    warnings.warn(
        "test_api_endpoints.py has been replaced by test_api_endpoints_integration.py. "
        "The old file contained anti-pattern mock FastAPI app tests. "
        "Use the new integration tests for real FastAPI behavior testing.",
        DeprecationWarning,
        stacklevel=2
    )
    # This test always passes - it's just for the deprecation notice
    assert True


# Mark all tests in this file as deprecated
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")
