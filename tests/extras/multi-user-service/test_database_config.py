"""Test suite for multi-user service database configuration.

This module tests the database connection setup, configuration management,
and session handling for the multi-user EMUSES service.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession


class TestDatabaseConfiguration:
    """Test suite for database configuration and connection setup."""

    def test_database_config_creation(self):
        """Test that DatabaseConfig can be created with environment variables."""
        from emuses.multi_user_service.database import DatabaseConfig
        
        # Test with mock environment variables
        with patch.dict(os.environ, {
            'DATABASE_URL': 'postgresql+asyncpg://user:pass@localhost/test',
            'EMUSES_DEPLOYMENT_MODE': 'multi-user'
        }):
            config = DatabaseConfig()
            
            assert hasattr(config, 'database_url')
            assert hasattr(config, 'deployment_mode')
            assert config.database_url == 'postgresql+asyncpg://user:pass@localhost/test'
            assert config.deployment_mode == 'multi-user'

    def test_database_config_validation(self):
        """Test database configuration validation."""
        from emuses.multi_user_service.database import DatabaseConfig
        
        # Test validation requires DATABASE_URL in auth-required modes
        with patch.dict(os.environ, {
            'EMUSES_DEPLOYMENT_MODE': 'production'
        }, clear=True):
            with pytest.raises(ValueError, match="DATABASE_URL.*required"):
                DatabaseConfig()

    def test_async_session_creation(self):
        """Test that async database sessions can be created."""
        from emuses.multi_user_service.database import get_async_session
        import types
        
        # Test session creation (this will be an async generator)
        session_gen = get_async_session()
        assert isinstance(session_gen, types.AsyncGeneratorType)

    def test_database_engine_creation(self):
        """Test that database engine can be created."""
        from emuses.multi_user_service.database import create_engine
        
        with patch.dict(os.environ, {
            'DATABASE_URL': 'postgresql+asyncpg://user:pass@localhost/test'
        }):
            engine = create_engine()
            assert engine is not None
            assert hasattr(engine, 'url')

    def test_connection_health_check(self):
        """Test database connection health check functionality."""
        from emuses.multi_user_service.database import check_database_health
        
        # This should not raise an exception even if database is not connected
        # (it should handle connection errors gracefully)
        result = check_database_health()
        assert isinstance(result, bool)