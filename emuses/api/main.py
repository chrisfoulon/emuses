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

    # Mount MkDocs documentation if available in development
    _mount_documentation_if_available(app)

    return app


def _mount_documentation_if_available(app: FastAPI) -> None:
    """
    Mount MkDocs documentation if available in development mode.
    
    This function serves built MkDocs documentation at /docs/ when:
    - Not in production environment (EMUSES_ENV != "production")
    - site/ directory exists with documentation
    - FastAPI StaticFiles is available
    
    Gracefully handles missing dependencies or directories.
    
    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance to mount documentation to
    """
    import os
    from pathlib import Path
    
    # Only serve docs in development mode (not production)
    if os.getenv("EMUSES_ENV") == "production":
        return
    
    try:
        from fastapi.staticfiles import StaticFiles
        
        # Path to built MkDocs site (relative to project root)
        project_root = Path(__file__).parent.parent.parent
        site_dir = project_root / "site"
        
        if site_dir.exists() and site_dir.is_dir():
            app.mount("/docs", StaticFiles(directory=str(site_dir), html=True), name="documentation")
            # Only print in development (not during tests)
            if os.getenv("PYTEST_CURRENT_TEST") is None:
                print(f"📚 Documentation served at /docs/")
    except ImportError:
        # StaticFiles not available, gracefully skip
        pass
    except Exception:
        # Any other error, gracefully skip to avoid breaking app startup
        pass
