"""Test suite for multi-user service authentication models.

This module tests the user models and database schema for the multi-user
EMUSES service, including SQLAlchemy models extending FastAPI-Users.
"""

import pytest
from sqlalchemy import Column, String, Integer, Float
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4


class TestUserModels:
    """Test suite for user authentication models."""

    def test_user_model_creation(self):
        """Test that User model can be created with EMUSES-specific fields."""
        # This test will fail initially as we haven't created the User model yet
        from emuses.multi_user_service.models import User
        
        # Test basic user creation
        user_data = {
            "email": "test@example.com",
            "hashed_password": "hashed_password_here",
            "organization": "Test Organization",
            "role": "researcher",
            "storage_quota_gb": 10.0,
            "compute_quota_hours": 100.0,
            "storage_used_gb": 0.0,
            "compute_used_hours": 0.0
        }
        
        user = User(**user_data)
        
        # Verify EMUSES-specific fields exist
        assert hasattr(user, 'organization')
        assert hasattr(user, 'role')
        assert hasattr(user, 'storage_quota_gb')
        assert hasattr(user, 'compute_quota_hours')
        assert hasattr(user, 'storage_used_gb')
        assert hasattr(user, 'compute_used_hours')
        
        # Verify inherited fields from FastAPI-Users
        assert hasattr(user, 'email')
        assert hasattr(user, 'hashed_password')
        assert hasattr(user, 'id')
        assert hasattr(user, 'is_active')
        assert hasattr(user, 'is_superuser')
        assert hasattr(user, 'is_verified')

    def test_user_settings_model_creation(self):
        """Test that UserSettings model can be created."""
        from emuses.multi_user_service.models import UserSettings
        
        settings_data = {
            "user_id": uuid4(),
            "default_n_jobs": 4,
            "default_optuna_trials": 100,
            "notification_email": True,
            "notification_slack": False,
            "ui_theme": "light"
        }
        
        settings = UserSettings(**settings_data)
        
        # Verify settings fields exist
        assert hasattr(settings, 'user_id')
        assert hasattr(settings, 'default_n_jobs')
        assert hasattr(settings, 'default_optuna_trials')
        assert hasattr(settings, 'notification_email')
        assert hasattr(settings, 'notification_slack')
        assert hasattr(settings, 'ui_theme')

    def test_user_model_table_structure(self):
        """Test that User model has proper table structure."""
        from emuses.multi_user_service.models import User
        
        # Verify table name
        assert User.__tablename__ == 'users'
        
        # Verify key columns exist in table structure
        column_names = [col.name for col in User.__table__.columns]
        expected_columns = [
            'id', 'email', 'hashed_password', 'is_active', 'is_superuser', 'is_verified',
            'organization', 'role', 'storage_quota_gb', 'compute_quota_hours',
            'storage_used_gb', 'compute_used_hours'
        ]
        
        for col in expected_columns:
            assert col in column_names, f"Missing column: {col}"