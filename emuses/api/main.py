"""
FastAPI application factory for EMUSES service.

This module provides the create_app() function that returns a configured
FastAPI application instance for TestClient integration and service deployment.
"""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """
    Create and configure a FastAPI application instance.

    This function provides a factory for creating FastAPI applications,
    enabling TestClient integration for local execution while maintaining
    service consistency with remote deployments.

    Returns
    -------
    FastAPI
        Configured FastAPI application instance with all endpoints and middleware

    Examples
    --------
    >>> from emuses.api.main import create_app
    >>> app = create_app()
    >>> # Use with TestClient
    >>> from fastapi.testclient import TestClient
    >>> client = TestClient(app)
    >>> response = client.get("/api/health")
    >>> assert response.status_code == 200
    """
    # Quick check for service-specific dependencies
    try:
        from emuses.utils.dependency_check import validate_for_service_mode

        if not validate_for_service_mode():
            # Still try to import and return the app, but user was warned
            pass
    except ImportError:
        # Our utils can't be imported, but don't block service startup
        pass

    # Import the pre-configured FastAPI app from the foundation service
    from emuses.foundation_fastapi_service.app import app

    return app
