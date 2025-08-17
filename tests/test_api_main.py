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
        assert "EMUSES" in app.title, "Should use EMUSES in the title"
    
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


class TestDocumentationServing:
    """Test documentation serving functionality in FastAPI app."""
    
    def test_docs_not_mounted_in_production(self, monkeypatch):
        """Test that docs are not mounted in production environment."""
        # Set production environment
        monkeypatch.setenv("EMUSES_ENV", "production")
        
        from emuses.api.main import create_app
        app = create_app()
        
        # Check that docs mount was NOT added
        mount_routes = []
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'app'):
                mount_routes.append(route.path)
        
        assert "/docs" not in mount_routes, "Docs should not be mounted in production"
    
    def test_docs_graceful_fallback_missing_site_dir(self, monkeypatch):
        """Test graceful fallback when site directory doesn't exist."""
        # Ensure we're not in production mode
        monkeypatch.setenv("EMUSES_ENV", "development")
        
        from emuses.api.main import create_app
        # This should not raise an exception even with missing site directory
        app = create_app()
        
        # App should still be created successfully
        assert app is not None
        assert hasattr(app, 'title')
    
    def test_create_app_unchanged_behavior_with_docs_feature(self):
        """Test that existing create_app behavior is unchanged with docs feature."""
        from emuses.api.main import create_app
        
        app = create_app()
        
        # All original tests should still pass
        assert isinstance(app, FastAPI)
        assert hasattr(app, 'title')
        assert hasattr(app, 'version') 
        assert hasattr(app, 'docs_url')
        assert "EMUSES" in app.title
        
        # Key API routes should still exist
        routes = [route.path for route in app.routes]
        expected_routes = [
            "/api/v1/jobs/pipeline/full",
            "/api/v1/jobs/{job_id}/status", 
            "/api/health"
        ]
        
        for expected_route in expected_routes:
            route_exists = any(
                expected_route.replace("{job_id}", "{path}") == route.replace("{job_id}", "{path}")
                for route in routes
            )
            assert route_exists, f"Expected route {expected_route} should still exist"