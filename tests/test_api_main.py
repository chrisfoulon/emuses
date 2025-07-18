"""
Test module for emuses.api.main FastAPI app factory.

This module tests the create_app() function that provides the FastAPI app
instance for TestClient integration.
"""

import pytest
from fastapi import FastAPI


class TestCreateApp:
    """Test the create_app() function."""
    
    def test_create_app_import(self):
        """Test that create_app can be imported from emuses.api.main."""
        try:
            from emuses.api.main import create_app
            assert callable(create_app), "create_app should be callable"
        except ImportError:
            pytest.fail("create_app function not found in emuses.api.main")
    
    def test_create_app_returns_fastapi_instance(self):
        """Test that create_app returns a FastAPI application instance."""
        from emuses.api.main import create_app
        
        app = create_app()
        
        # Verify it's a FastAPI instance
        assert isinstance(app, FastAPI), "create_app should return a FastAPI instance"
        
        # Verify it has the expected attributes
        assert hasattr(app, 'title'), "FastAPI app should have a title"
        assert hasattr(app, 'version'), "FastAPI app should have a version"
        assert hasattr(app, 'docs_url'), "FastAPI app should have docs_url"
        
        # Verify it has the expected title from the foundation service
        assert app.title == "EMUSES Foundation FastAPI Service", "Should use the foundation service title"
    
    def test_create_app_has_expected_routes(self):
        """Test that the created app has the expected API routes."""
        from emuses.api.main import create_app
        
        app = create_app()
        
        # Get all routes
        routes = [route.path for route in app.routes]
        
        # Check for key API endpoints
        expected_routes = [
            "/api/v1/jobs/pipeline/full",
            "/api/v1/jobs/{job_id}/status",
            "/api/health"
        ]
        
        for expected_route in expected_routes:
            # Check if route exists (allowing for path parameters)
            route_exists = any(
                expected_route.replace("{job_id}", "{path}") == route.replace("{job_id}", "{path}")
                for route in routes
            )
            assert route_exists, f"Expected route {expected_route} not found in app routes"
    
    def test_create_app_idempotent(self):
        """Test that create_app() calls return independent instances."""
        from emuses.api.main import create_app
        
        app1 = create_app()
        app2 = create_app()
        
        # Should return FastAPI instances
        assert isinstance(app1, FastAPI)
        assert isinstance(app2, FastAPI)
        
        # Should have the same configuration
        assert app1.title == app2.title
        assert app1.version == app2.version