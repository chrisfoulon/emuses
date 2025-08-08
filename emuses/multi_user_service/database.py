"""Database configuration and connection management for multi-user EMUSES service.

This module provides database configuration, async session management,
and connection pooling for PostgreSQL with SQLAlchemy async patterns.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Generator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                    async_sessionmaker, create_async_engine)
from sqlalchemy import create_engine as create_sync_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# Global engine instances  
_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[async_sessionmaker[AsyncSession]] = None
_sync_engine: Optional[Engine] = None
_sync_session_maker: Optional[sessionmaker[Session]] = None


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
        engine_kwargs.update(
            {
                "pool_size": config.pool_size,
                "max_overflow": config.max_overflow,
                "pool_timeout": config.pool_timeout,
                "pool_pre_ping": config.pool_pre_ping,
            }
        )

    _engine = create_async_engine(database_url, **engine_kwargs)

    logger.info(
        f"Database engine created for deployment mode: {config.deployment_mode}"
    )
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


def create_sync_engine() -> Engine:
    """Create synchronous SQLAlchemy engine.
    
    Returns
    -------
    Engine
        Configured synchronous SQLAlchemy engine
    """
    global _sync_engine
    
    if _sync_engine is not None:
        return _sync_engine
    
    config = DatabaseConfig()
    
    # Convert async URL to sync URL 
    sync_url = config.connection_url.replace("postgresql+asyncpg://", "postgresql://")
    
    _sync_engine = create_sync_engine(
        sync_url,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_pre_ping=True,
        pool_recycle=config.pool_recycle,
        echo=config.echo
    )
    
    logger.info("Created sync database engine")
    return _sync_engine


def get_sync_session_maker() -> sessionmaker[Session]:
    """Get or create synchronous session maker.
    
    Returns
    -------
    sessionmaker[Session]
        Configured session maker
    """
    global _sync_session_maker
    
    if _sync_session_maker is not None:
        return _sync_session_maker
        
    engine = create_sync_engine()
    _sync_session_maker = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False
    )
    
    return _sync_session_maker


def get_db() -> Generator[Session, None, None]:
    """Dependency function for FastAPI to get sync database sessions.
    
    Yields
    ------
    Session
        Database session for dependency injection
    """
    session_maker = get_sync_session_maker()
    session = session_maker()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


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


async def create_all_tables():
    """Create all database tables using SQLAlchemy metadata.

    This function is used for database initialization and should be
    called on application startup to ensure all tables exist.
    """
    try:
        from emuses.multi_user_service.models import Base

        engine = create_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise


async def drop_all_tables():
    """Drop all database tables using SQLAlchemy metadata.

    WARNING: This function will delete all data. Use with caution.
    """
    try:
        from emuses.multi_user_service.models import Base

        engine = create_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error(f"Failed to drop database tables: {e}")
        raise


def run_migrations(target_revision: str = "head"):
    """Run database migrations to target revision.

    Parameters
    ----------
    target_revision : str
        Target revision to migrate to (default: "head" for latest)

    Raises
    ------
    Exception
        If migration fails
    """
    try:
        import os

        from alembic import command
        from alembic.config import Config

        # Get alembic configuration
        config = Config("alembic.ini")

        # Set database URL if not already configured
        db_config = DatabaseConfig()
        if db_config.database_url:
            sync_url = db_config.database_url.replace("+asyncpg", "").replace(
                "+aiosqlite", ""
            )
            config.set_main_option("sqlalchemy.url", sync_url)

        # Run migration
        command.upgrade(config, target_revision)
        logger.info(f"Database migration to {target_revision} completed successfully")

    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        raise


def rollback_migration(target_revision: str):
    """Rollback database migration to target revision.

    Parameters
    ----------
    target_revision : str
        Target revision to rollback to

    Raises
    ------
    Exception
        If rollback fails
    """
    try:
        from alembic import command
        from alembic.config import Config

        # Get alembic configuration
        config = Config("alembic.ini")

        # Set database URL if not already configured
        db_config = DatabaseConfig()
        if db_config.database_url:
            sync_url = db_config.database_url.replace("+asyncpg", "").replace(
                "+aiosqlite", ""
            )
            config.set_main_option("sqlalchemy.url", sync_url)

        # Run downgrade
        command.downgrade(config, target_revision)
        logger.info(f"Database rollback to {target_revision} completed successfully")

    except Exception as e:
        logger.error(f"Database rollback failed: {e}")
        raise


def get_migration_status():
    """Get current migration status and available revisions.

    Returns
    -------
    dict
        Dictionary containing current revision, head revision, and pending migrations
    """
    try:
        import io
        import sys

        from sqlalchemy import create_engine as sync_create_engine

        from alembic import command
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        # Get alembic configuration
        config = Config("alembic.ini")

        # Set database URL
        db_config = DatabaseConfig()
        if db_config.database_url:
            sync_url = db_config.database_url.replace("+asyncpg", "").replace(
                "+aiosqlite", ""
            )
        else:
            sync_url = "sqlite:///:memory:"

        config.set_main_option("sqlalchemy.url", sync_url)

        # Get script directory
        script = ScriptDirectory.from_config(config)

        # Get current revision from database
        sync_engine = sync_create_engine(sync_url)
        with sync_engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()

        # Get head revision
        head_rev = script.get_current_head()

        # Get all revisions
        all_revisions = [rev.revision for rev in script.walk_revisions()]

        # Check if database is up to date
        is_up_to_date = current_rev == head_rev

        return {
            "current_revision": current_rev,
            "head_revision": head_rev,
            "all_revisions": all_revisions,
            "is_up_to_date": is_up_to_date,
            "pending_migrations": len(all_revisions) if current_rev is None else 0,
        }

    except Exception as e:
        logger.error(f"Failed to get migration status: {e}")
        raise


def validate_database_schema():
    """Validate that database schema matches SQLAlchemy models.

    Returns
    -------
    dict
        Validation results with any discrepancies found
    """
    try:
        from sqlalchemy import create_engine as sync_create_engine
        from sqlalchemy import inspect

        from emuses.multi_user_service.models import Base

        db_config = DatabaseConfig()
        if db_config.database_url:
            sync_url = db_config.database_url.replace("+asyncpg", "").replace(
                "+aiosqlite", ""
            )
        else:
            sync_url = "sqlite:///:memory:"

        sync_engine = sync_create_engine(sync_url)

        # Get expected tables from models
        expected_tables = set(Base.metadata.tables.keys())

        # Get actual tables from database
        inspector = inspect(sync_engine)
        actual_tables = set(inspector.get_table_names())

        # Compare
        missing_tables = expected_tables - actual_tables
        extra_tables = actual_tables - expected_tables

        return {
            "valid": len(missing_tables) == 0 and len(extra_tables) == 0,
            "expected_tables": list(expected_tables),
            "actual_tables": list(actual_tables),
            "missing_tables": list(missing_tables),
            "extra_tables": list(extra_tables),
        }

    except Exception as e:
        logger.error(f"Schema validation failed: {e}")
        raise
