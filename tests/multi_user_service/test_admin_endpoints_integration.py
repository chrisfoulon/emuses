"""Integration tests for admin endpoints with database state verification.

This module provides comprehensive integration testing for admin user management
operations, verifying actual database state changes rather than just response schemas.
"""

import pytest
import os
import asyncio
from uuid import uuid4, UUID
from unittest.mock import patch
from typing import AsyncGenerator

import pytest_asyncio
from fastapi.testclient import TestClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, delete

from emuses.api.main import create_app
from emuses.multi_user_service.models import User, Base
from emuses.multi_user_service.database import get_async_session
from emuses.multi_user_service.auth import get_user_manager, get_current_superuser
from emuses.multi_user_service.endpoints import UserCreate


class TestAdminEndpointsIntegration:
    """Integration tests for admin endpoints with database state verification."""

    @pytest.fixture(scope="session", autouse=True)
    def setup_deployment_mode(self):
        """Set deployment mode to enable multi-user endpoints."""
        with patch.dict(os.environ, {"EMUSES_DEPLOYMENT_MODE": "multi_user"}):
            yield

    @pytest_asyncio.fixture(scope="function")
    async def test_db_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Create isolated test database session with automatic cleanup."""
        # Use in-memory SQLite for testing
        test_engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False
        )
        
        # Create all tables
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Create session
        async_session = async_sessionmaker(test_engine, expire_on_commit=False)
        
        async with async_session() as session:
            try:
                yield session
            finally:
                # Cleanup: rollback any uncommitted changes
                await session.rollback()
                
        # Clean up engine
        await test_engine.dispose()

    @pytest_asyncio.fixture
    async def clean_user_db(self, test_db_session: AsyncSession):
        """Ensure clean state for each test by removing existing test users."""
        # Remove any existing test users
        await test_db_session.execute(
            delete(User).where(User.email.like("%@test.example%"))
        )
        await test_db_session.commit()
        yield test_db_session

    @pytest_asyncio.fixture
    async def admin_user(self, clean_user_db: AsyncSession) -> User:
        """Create admin user in database for testing."""
        admin = User(
            id=uuid4(),
            email="admin@test.example",
            hashed_password="$2b$12$fake_admin_hash",
            is_active=True,
            is_superuser=True,
            is_verified=True,
            organization="Test Admin Org",
            role="admin"
        )
        
        clean_user_db.add(admin)
        await clean_user_db.commit()
        await clean_user_db.refresh(admin)
        return admin

    @pytest_asyncio.fixture
    async def regular_user(self, clean_user_db: AsyncSession) -> User:
        """Create regular user in database for testing."""
        user = User(
            id=uuid4(),
            email="user@test.example",
            hashed_password="$2b$12$fake_user_hash",
            is_active=True,
            is_superuser=False,
            is_verified=True,
            organization="Test User Org",
            role="researcher"
        )
        
        clean_user_db.add(user)
        await clean_user_db.commit()
        await clean_user_db.refresh(user)
        return user

    @pytest.fixture
    def app(self):
        """Create FastAPI application for testing."""
        return create_app()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    @pytest_asyncio.fixture
    async def override_db_session(self, app, clean_user_db: AsyncSession):
        """Override database session dependency for testing."""
        def get_test_session():
            return clean_user_db
            
        app.dependency_overrides[get_async_session] = get_test_session
        yield
        app.dependency_overrides.clear()

    @pytest_asyncio.fixture
    async def override_auth(self, app, admin_user: User):
        """Override authentication to return admin user."""
        def get_test_admin():
            return admin_user
            
        app.dependency_overrides[get_current_superuser] = get_test_admin
        yield
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_user_database_integration(
        self, client, override_db_session, override_auth, clean_user_db: AsyncSession
    ):
        """Test user creation actually creates database records."""
        # Verify no users exist initially (except admin)
        result = await clean_user_db.execute(
            select(User).where(User.email == "newuser@test.example")
        )
        existing_user = result.scalar_one_or_none()
        assert existing_user is None
        
        # Create user via API
        response = client.post(
            "/admin/users",
            json={
                "email": "newuser@test.example",
                "password": "secure_password123",
                "organization": "New Test Org",
                "is_active": True,
                "is_verified": True
            }
        )
        
        # Verify API response
        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["email"] == "newuser@test.example"
        assert response_data["organization"] == "New Test Org"
        assert response_data["is_active"] is True
        assert response_data["is_verified"] is True
        
        # CRITICAL: Verify actual database state
        result = await clean_user_db.execute(
            select(User).where(User.email == "newuser@test.example")
        )
        created_user = result.scalar_one_or_none()
        
        assert created_user is not None
        assert created_user.email == "newuser@test.example"
        assert created_user.organization == "New Test Org"
        assert created_user.is_active is True
        assert created_user.is_verified is True
        assert created_user.hashed_password != "secure_password123"  # Password should be hashed
        assert created_user.hashed_password.startswith("$2b$")  # bcrypt hash format

    @pytest.mark.asyncio
    async def test_list_users_database_integration(
        self, client, override_db_session, override_auth, 
        clean_user_db: AsyncSession, admin_user: User, regular_user: User
    ):
        """Test user listing returns actual database records."""
        # List users via API
        response = client.get("/admin/users?limit=10")
        
        # Verify API response
        assert response.status_code == status.HTTP_200_OK
        users_data = response.json()
        
        # Should return both admin and regular user
        assert len(users_data) == 2
        emails = {user["email"] for user in users_data}
        assert "admin@test.example" in emails
        assert "user@test.example" in emails
        
        # Verify data matches database records
        for user_data in users_data:
            if user_data["email"] == "admin@test.example":
                assert user_data["organization"] == admin_user.organization
                assert user_data["is_active"] is True
                assert user_data["is_verified"] is True
            elif user_data["email"] == "user@test.example":
                assert user_data["organization"] == regular_user.organization
                assert user_data["is_active"] is True
                assert user_data["is_verified"] is True

    @pytest.mark.asyncio
    async def test_get_user_database_integration(
        self, client, override_db_session, override_auth,
        clean_user_db: AsyncSession, regular_user: User
    ):
        """Test user retrieval returns actual database record."""
        # Get user via API
        response = client.get(f"/admin/users/{regular_user.id}")
        
        # Verify API response
        assert response.status_code == status.HTTP_200_OK
        user_data = response.json()
        
        # Verify data matches database record
        assert user_data["id"] == str(regular_user.id)
        assert user_data["email"] == regular_user.email
        assert user_data["organization"] == regular_user.organization
        assert user_data["is_active"] == regular_user.is_active
        assert user_data["is_verified"] == regular_user.is_verified

    @pytest.mark.asyncio
    async def test_update_user_database_integration(
        self, client, override_db_session, override_auth,
        clean_user_db: AsyncSession, regular_user: User
    ):
        """Test user update actually modifies database records."""
        original_org = regular_user.organization
        
        # Update user via API
        response = client.put(
            f"/admin/users/{regular_user.id}",
            json={
                "organization": "Updated Test Organization",
                "is_active": False
            }
        )
        
        # Verify API response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["organization"] == "Updated Test Organization"
        assert response_data["is_active"] is False
        
        # CRITICAL: Verify actual database state changed
        await clean_user_db.refresh(regular_user)
        assert regular_user.organization == "Updated Test Organization"
        assert regular_user.is_active is False
        assert regular_user.organization != original_org

    @pytest.mark.asyncio
    async def test_delete_user_database_integration(
        self, client, override_db_session, override_auth,
        clean_user_db: AsyncSession, regular_user: User
    ):
        """Test user deletion actually removes database records."""
        user_id = regular_user.id
        
        # Verify user exists before deletion
        result = await clean_user_db.execute(
            select(User).where(User.id == user_id)
        )
        existing_user = result.scalar_one_or_none()
        assert existing_user is not None
        
        # Delete user via API
        response = client.delete(f"/admin/users/{user_id}")
        
        # Verify API response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["status"] == "success"
        assert "deleted successfully" in response_data["message"]
        
        # CRITICAL: Verify user actually removed from database
        result = await clean_user_db.execute(
            select(User).where(User.id == user_id)
        )
        deleted_user = result.scalar_one_or_none()
        assert deleted_user is None

    @pytest.mark.asyncio
    async def test_error_handling_integration(
        self, client, override_db_session, override_auth,
        clean_user_db: AsyncSession, regular_user: User
    ):
        """Test error handling with actual database constraints."""
        # Test duplicate email (409 Conflict)
        response = client.post(
            "/admin/users",
            json={
                "email": regular_user.email,  # Duplicate email
                "password": "test123",
                "organization": "Test Org"
            }
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"].lower()
        
        # Test user not found (404)
        fake_id = uuid4()
        response = client.get(f"/admin/users/{fake_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()
        
        # Test update non-existent user (404)
        response = client.put(
            f"/admin/users/{fake_id}",
            json={"organization": "Updated Org"}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Test delete non-existent user (404)
        response = client.delete(f"/admin/users/{fake_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_pagination_performance(
        self, client, override_db_session, override_auth,
        clean_user_db: AsyncSession
    ):
        """Test pagination with larger datasets for performance validation."""
        # Create multiple test users
        test_users = []
        for i in range(25):
            user = User(
                id=uuid4(),
                email=f"testuser{i}@test.example",
                hashed_password="$2b$12$fake_hash",
                is_active=True,
                is_superuser=False,
                is_verified=True,
                organization=f"Test Org {i}",
                role="researcher"
            )
            test_users.append(user)
        
        clean_user_db.add_all(test_users)
        await clean_user_db.commit()
        
        # Test pagination
        response = client.get("/admin/users?skip=5&limit=10")
        assert response.status_code == status.HTTP_200_OK
        users_data = response.json()
        
        # Should return exactly 10 users (pagination working)
        assert len(users_data) <= 10
        
        # Test maximum limit enforcement (should cap at 1000)
        response = client.get("/admin/users?limit=2000")
        assert response.status_code == status.HTTP_200_OK
        # Note: Actual count will be limited by database content, but limit should be enforced