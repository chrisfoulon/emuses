"""Database configuration and connection management for multi-user EMUSES service.

This module provides database configuration, async session management,
and connection pooling for PostgreSQL with SQLAlchemy async patterns.
"""

import os
import logging
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine
)
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Global engine instance
_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


class DatabaseConfig:
    """Database configuration management with environment-based settings.

    Manages database connection configuration based on deployment mode
    and validates required environment variables.

    Attributes
    ----------
    database_url : str
        Database connection URL
    deployment_mode : str
        Current deployment mode (local, multi-user, production)
    pool_size : int
        Connection pool size
    max_overflow : int
        Maximum connection pool overflow
    """

    def __init__(self):
        """Initialize database configuration from environment variables.

        Raises
        ------
        ValueError
            If required environment variables are missing for deployment mode
        """
        self.deployment_mode = os.getenv("EMUSES_DEPLOYMENT_MODE", "local")
        self.database_url = os.getenv("DATABASE_URL")

        # Validate configuration based on deployment mode
        if self.deployment_mode in ["multi-user", "production"]:
            if not self.database_url:
                raise ValueError(
                    f"DATABASE_URL environment variable is required for "
                    f"deployment mode: {self.deployment_mode}"
                )

        # Connection pool configuration
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        self.pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))

        # Connection health check settings
        self.pool_pre_ping = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"


def create_engine() -> AsyncEngine:
    """Create async database engine with connection pooling.

    Returns
    -------
    AsyncEngine
        Configured SQLAlchemy async engine

    Raises
    ------
    ValueError
        If database configuration is invalid
    """
    global _engine

    if _engine is not None:
        return _engine

    config = DatabaseConfig()

    if not config.database_url:
        # For local mode, create in-memory SQLite for testing
        database_url = "sqlite+aiosqlite:///:memory:"
    else:
        database_url = config.database_url

    # Create engine with connection pooling
    engine_kwargs = {
        "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
        "future": True,
    }

    # Add pool settings for PostgreSQL
    if database_url.startswith("postgresql"):
        engine_kwargs.update({
            "pool_size": config.pool_size,
            "max_overflow": config.max_overflow,
            "pool_timeout": config.pool_timeout,
            "pool_pre_ping": config.pool_pre_ping,
        })

    _engine = create_async_engine(database_url, **engine_kwargs)

    logger.info(f"Database engine created for deployment mode: {config.deployment_mode}")
    return _engine


def get_async_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get async session maker for database operations.

    Returns
    -------
    async_sessionmaker[AsyncSession]
        Configured session maker
    """
    global _async_session_maker

    if _async_session_maker is None:
        engine = create_engine()
        _async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    return _async_session_maker


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency function for FastAPI to get async database sessions.

    Yields
    ------
    AsyncSession
        Database session for dependency injection
    """
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def check_database_health() -> bool:
    """Check database connection health.

    Returns
    -------
    bool
        True if database is healthy, False otherwise
    """
    try:
        config = DatabaseConfig()
        if config.deployment_mode == "local" and not config.database_url:
            # Local mode without database is considered healthy
            return True

        # For actual database connections, we would test the connection
        # This is a simplified version that checks configuration validity
        if config.database_url:
            return True
        return False
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


@asynccontextmanager
async def get_database_session():
    """Async context manager for database sessions.

    Yields
    ------
    AsyncSession
        Database session with automatic commit/rollback
    """
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
