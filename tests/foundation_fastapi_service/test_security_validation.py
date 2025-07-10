#!/usr/bin/env python3
"""
Security Testing and Input Validation

Tests security aspects of the FastAPI service including:
- Path traversal protection
- Input sanitization and validation
- Pydantic deserialization limits
- Negative tests for error responses
"""

import os
import sys
import json
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any
import pytest
import requests
from fastapi.testclient import TestClient

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def client():
    """Create FastAPI test client."""
    from emuses.foundation_fastapi_service.app import app
    return TestClient(app)


@pytest.fixture
def temp_jobs_dir():
    """Create temporary jobs directory."""
    with tempfile.TemporaryDirectory(prefix='test_jobs_') as td:
        yield Path(td)


@pytest.fixture
def malicious_paths():
    """Common path traversal attack patterns."""
    return [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "..%2F..%2F..%2Fetc%2Fpasswd",
        "..%5c..%5c..%5cwindows%5csystem32%5cconfig%5csam",
        "....//....//....//etc/passwd",
        "....\\\\....\\\\....\\\\windows\\\\system32\\\\config\\\\sam",
        "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        "%2e%2e%5c%2e%2e%5c%2e%2e%5cwindows%5csystem32%5cconfig%5csam",
        "../../../../../../proc/self/environ",
        "../../../../../../../../../etc/shadow",
    ]


@pytest.fixture
def malicious_json_payloads():
    """Malicious JSON payloads for testing input validation."""
    return [
        # Oversized string
        {"config": {"prefix": "A" * 10000}},
        # Deeply nested object
        {"config": _create_deeply_nested_dict(100)},
        # Large array
        {"config": {"array_field": list(range(10000))}},
        # Null bytes
        {"config": {"prefix": "test\x00malicious"}},
        # Control characters
        {"config": {"prefix": "test\x01\x02\x03"}},
        # Unicode exploitation attempts
        {"config": {"prefix": "\uFEFF\u200B\u200C\u200D"}},
        # SQL-like injection (though not SQL, tests sanitization)
        {"config": {"prefix": "'; DROP TABLE users; --"}},
        # Script injection attempts
        {"config": {"prefix": "<script>alert('xss')</script>"}},
        # Path injection in config
        {"config": {"output_folder": "../../../sensitive_data"}},
    ]


def _create_deeply_nested_dict(depth: int) -> Dict[str, Any]:
    """Create a deeply nested dictionary for testing."""
    if depth <= 0:
        return "deep_value"
    return {"nested": _create_deeply_nested_dict(depth - 1)}


@pytest.fixture
def invalid_uuids():
    """Invalid UUID formats for testing."""
    return [
        "not-a-uuid",
        "12345",
        "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "12345678-1234-1234-1234-12345678901G",  # Invalid character
        "12345678-1234-1234-1234-123456789012",   # Too long
        "12345678-1234-1234-1234-12345678901",    # Too short
        "../../../etc/passwd",
        "'; DROP TABLE jobs; --",
        "<script>alert('xss')</script>",
        "\x00\x01\x02",
        "",
        None,
    ]


class TestPathTraversalProtection:
    """Test path traversal protection for file operations."""

    def test_job_directory_creation_protection(self, client, malicious_paths):
        """Test that job directory creation prevents path traversal."""
        # This test ensures that job IDs cannot contain path traversal sequences
        for malicious_path in malicious_paths:
            # Try to create a job with malicious path elements
            # The system should either reject it or sanitize the path
            response = client.post("/api/v1/jobs/pipeline/full", json={
                "input_matrix": [[1, 2], [3, 4]],
                "scores": [[0.5], [1.0]],
                "config": {
                    "output_folder": f"/tmp/test_{malicious_path}",
                    "prefix": "security_test"
                }
            })

            # Should either succeed with sanitized path or fail safely
            if response.status_code == 201:  # Created status
                job_data = response.json()
                job_id = job_data["job_id"]
                # Ensure job ID is a valid UUID and doesn't contain path elements
                assert uuid.UUID(job_id)  # Should not raise exception
                assert "/" not in job_id
                assert "\\" not in job_id
                assert ".." not in job_id
            else:
                # If it fails, should be a proper error response
                assert response.status_code in [400, 422]
                assert "error" in response.json() or "detail" in response.json()

    def test_artifact_download_path_protection(self, client, malicious_paths):
        """Test that artifact downloads prevent path traversal."""
        # First create a legitimate job
        job_response = client.post("/api/v1/jobs/pipeline/full", json={
            "input_matrix": [[1, 2], [3, 4]],
            "scores": [[0.5], [1.0]],
            "config": {"prefix": "security_test"}
        })

        if job_response.status_code == 201:
            job_data = job_response.json()
            job_id = job_data["job_id"]

            # Try to access files outside job directory
            for malicious_path in malicious_paths:
                response = client.get(f"/api/v1/jobs/{job_id}/artifacts/{malicious_path}")

                # Should return 404 or 403, never 200 with sensitive data
                assert response.status_code in [404, 403, 422]

                # Ensure error doesn't leak sensitive information
                response_text = response.text.lower()
                assert "passwd" not in response_text
                assert "shadow" not in response_text
                assert "system32" not in response_text

    def test_file_upload_path_protection(self, client, malicious_paths):
        """Test that file uploads prevent path traversal in filenames."""
        # Note: The FastAPI service doesn't have a general file upload endpoint
        # File uploads are handled through job creation with embedded data
        # This test verifies that malicious filenames in job configs are handled safely

        for malicious_path in malicious_paths:
            # Test malicious paths in job configuration
            response = client.post("/api/v1/jobs/pipeline/full", json={
                "input_matrix": [[1, 2], [3, 4]],
                "scores": [[0.5], [1.0]],
                "config": {
                    "output_folder": f"/tmp/test_{malicious_path}",
                    "prefix": "security_test"
                }
            })

            # Should either sanitize path or reject with proper error
            if response.status_code == 201:
                result = response.json()
                # Ensure job ID is safe
                job_id = result.get("job_id", "")
                assert uuid.UUID(job_id)  # Should be valid UUID
                assert ".." not in job_id
                assert "/" not in job_id
                assert "\\" not in job_id
            else:
                # If rejected, should be proper validation error
                assert response.status_code in [400, 422]


class TestInputSanitization:
    """Test input sanitization and validation."""

    def test_malformed_json_handling(self, client):
        """Test handling of malformed JSON requests."""
        malformed_json_strings = [
            '{"incomplete":',
            '{"trailing_comma":123,}',
            '{"unquoted": key}',
            '{"duplicate":"key","duplicate":"value"}',
            '{invalid json}',
            '',
            'not json at all',
            '{"nested":{"too":"deep"' * 100,  # Incomplete nesting
        ]

        for malformed_json in malformed_json_strings:
            response = client.post(
                "/api/v1/jobs/pipeline/full",
                content=malformed_json,
                headers={"Content-Type": "application/json"}
            )

            # Should return 422 (Unprocessable Entity) for malformed JSON
            assert response.status_code == 422

            # Error message should not leak internal details
            error_msg = response.text.lower()
            assert "traceback" not in error_msg
            assert "internal" not in error_msg

    def test_oversized_payload_handling(self, client):
        """Test handling of oversized request payloads."""
        # Create an oversized matrix (should be rejected)
        oversized_matrix = [[1.0] * 10000] * 1000  # 10M elements

        response = client.post("/api/v1/jobs/pipeline/full", json={
            "input_matrix": oversized_matrix,
            "scores": [[0.5]],
            "config": {"prefix": "oversized_test"}
        })

        # Should be rejected due to size
        assert response.status_code in [413, 422]  # Payload too large or validation error

    def test_invalid_uuid_handling(self, client, invalid_uuids):
        """Test handling of invalid UUID formats."""
        for invalid_uuid in invalid_uuids:
            if invalid_uuid is None:
                continue

            try:
                # Test job status endpoint with invalid UUID
                response = client.get(f"/api/v1/jobs/{invalid_uuid}/status")

                # Should return 400/404/405/422 for invalid UUID format
                assert response.status_code in [400, 404, 405, 422]

                # Test job deletion with invalid UUID
                response = client.delete(f"/api/v1/jobs/{invalid_uuid}")
                assert response.status_code in [400, 404, 405, 422]

            except Exception as e:
                # If the URL is so malformed that the client rejects it,
                # that's also acceptable security behavior
                error_message = str(e).lower()
                acceptable_errors = [
                    "invalid url",
                    "invalid non-printable ascii character",
                    "url parsing",
                    "malformed url"
                ]
                assert any(err in error_message for err in acceptable_errors), f"Unexpected error: {e}"

    def test_pydantic_deserialization_limits(self, client, malicious_json_payloads):
        """Test Pydantic model deserialization with malicious payloads."""
        for payload in malicious_json_payloads:
            response = client.post("/api/v1/jobs/pipeline/full", json=payload)

            # Should either validate and sanitize, or reject with proper error
            if response.status_code == 201:
                # If accepted, verify sanitization occurred
                job_data = response.json()
                assert "job_id" in job_data
                # Should be valid UUID
                uuid.UUID(job_data["job_id"])
            else:
                # If rejected, should be proper validation error
                assert response.status_code in [400, 422]
                error_response = response.json()
                assert "error" in error_response or "detail" in error_response


class TestNegativeResponses:
    """Test negative cases and error response handling."""

    def test_missing_required_fields(self, client):
        """Test requests with missing required fields."""
        incomplete_payloads = [
            {},  # Empty payload
            {"input_matrix": [[1, 2]]},  # Missing scores
            {"scores": [[0.5]]},  # Missing input_matrix
            {"input_matrix": [], "scores": []},  # Empty arrays
            {"input_matrix": [[]], "scores": [[]]},  # Arrays with empty subarrays
        ]

        for payload in incomplete_payloads:
            response = client.post("/api/v1/jobs/pipeline/full", json=payload)

            # Should return 422 for validation errors
            assert response.status_code == 422

            # Should have proper error structure
            error_response = response.json()
            assert "detail" in error_response
            assert isinstance(error_response["detail"], list)

    def test_nonexistent_job_operations(self, client):
        """Test operations on non-existent jobs."""
        fake_job_id = str(uuid.uuid4())

        # Test status of non-existent job
        response = client.get(f"/api/v1/jobs/{fake_job_id}/status")
        assert response.status_code == 404

        # Test deletion of non-existent job
        response = client.delete(f"/api/v1/jobs/{fake_job_id}")
        assert response.status_code == 404

        # Test artifacts of non-existent job
        response = client.get(f"/api/v1/jobs/{fake_job_id}/artifacts/some_file.txt")
        assert response.status_code == 404

    def test_unsupported_http_methods(self, client):
        """Test unsupported HTTP methods return proper errors."""
        # Test unsupported methods on job endpoints
        fake_job_id = str(uuid.uuid4())

        # PATCH on job creation endpoint (should be POST only)
        response = client.patch("/api/v1/jobs/pipeline/full", json={})
        assert response.status_code == 405  # Method Not Allowed

        # PUT on job status endpoint (should be GET/DELETE only)
        response = client.put(f"/api/v1/jobs/{fake_job_id}/status", json={})
        assert response.status_code == 405

    def test_error_message_security(self, client):
        """Test that error messages don't leak sensitive information."""
        # Test with various malformed requests
        test_cases = [
            ("/api/v1/jobs/malformed-uuid/status", "GET"),
            ("/api/v1/jobs/pipeline/full", "POST"),  # Empty POST
            ("/nonexistent/endpoint", "GET"),
        ]

        for endpoint, method in test_cases:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={})

            # Error responses should not contain sensitive info
            response_text = response.text.lower()
            sensitive_patterns = [
                "password", "secret", "key", "token",
                "internal", "debug", "traceback",
                "file://", "http://", "ftp://",
                "c:\\", "/etc/", "/var/", "/tmp/",
            ]

            for pattern in sensitive_patterns:
                assert pattern not in response_text, f"Sensitive pattern '{pattern}' found in error response"

    def test_request_size_limits(self, client):
        """Test request size limits are enforced."""
        # Test header size limits
        large_headers = {"X-Large-Header": "A" * 8192}
        response = client.get("/", headers=large_headers)
        # Should either work or return 431 (Request Header Fields Too Large)
        assert response.status_code in [200, 404, 431]

        # Test URL length limits
        long_path = "/jobs/" + "a" * 2000
        response = client.get(long_path)
        # Should return 414 (URI Too Long) or 404
        assert response.status_code in [404, 414, 422]


class TestConcurrencySecurityAspects:
    """Test security aspects under concurrent access."""

    def test_race_condition_job_creation(self, client):
        """Test that concurrent job creation doesn't cause security issues."""
        import threading
        import time

        results = []

        def create_job():
            response = client.post("/api/v1/jobs/pipeline/full", json={
                "input_matrix": [[1, 2], [3, 4]],
                "scores": [[0.5], [1.0]],
                "config": {"prefix": "concurrent_test"}
            })
            results.append(response.json() if response.status_code == 201 else None)

        # Create multiple jobs concurrently
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=create_job)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify all successful responses have unique job IDs
        successful_jobs = [r for r in results if r and "job_id" in r]
        job_ids = [job["job_id"] for job in successful_jobs]

        # All job IDs should be unique (no race condition in ID generation)
        assert len(job_ids) == len(set(job_ids))

        # All should be valid UUIDs
        for job_id in job_ids:
            uuid.UUID(job_id)  # Should not raise exception


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
