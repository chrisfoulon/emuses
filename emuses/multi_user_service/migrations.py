"""Database migration setup and management for multi-user EMUSES service.

This module provides Alembic migration configuration, environment setup,
and migration generation functionality for database schema management.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Any
from alembic.config import Config
from alembic import command
from alembic.runtime.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import MetaData

from emuses.multi_user_service.models import Base
from emuses.multi_user_service.database import create_engine

logger = logging.getLogger(__name__)

# Migration directory path
MIGRATION_DIR = Path(__file__).parent / "alembic"


def get_alembic_config() -> Config:
    """Get Alembic configuration for database migrations.

    Creates and configures Alembic Config instance with appropriate
    settings for the multi-user service database.

    Returns
    -------
    Config
        Configured Alembic configuration instance
    """
    # Create alembic configuration
    alembic_cfg = Config()

    # Set configuration values
    alembic_cfg.set_main_option("script_location", str(MIGRATION_DIR))
    alembic_cfg.set_main_option("file_template", "%%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s")
    alembic_cfg.set_main_option("timezone", "UTC")

    # Set database URL
    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    # Convert async URL to sync for Alembic
    sync_database_url = database_url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")
    alembic_cfg.set_main_option("sqlalchemy.url", sync_database_url)

    return alembic_cfg


def create_migration_environment() -> bool:
    """Create migration environment and directory structure.

    Sets up the Alembic migration environment with proper directory
    structure and configuration files.

    Returns
    -------
    bool
        True if environment created successfully, False otherwise
    """
    try:
        # Create migration directory if it doesn't exist
        MIGRATION_DIR.mkdir(parents=True, exist_ok=True)

        # Create versions directory
        versions_dir = MIGRATION_DIR / "versions"
        versions_dir.mkdir(exist_ok=True)

        # Create env.py file if it doesn't exist
        env_py_path = MIGRATION_DIR / "env.py"
        if not env_py_path.exists():
            create_env_py_file(env_py_path)

        # Create script.py.mako template if it doesn't exist
        script_mako_path = MIGRATION_DIR / "script.py.mako"
        if not script_mako_path.exists():
            create_script_mako_file(script_mako_path)

        logger.info(f"Migration environment created at {MIGRATION_DIR}")
        return True

    except Exception as e:
        logger.error(f"Failed to create migration environment: {e}")
        return False


def setup_migration_directory() -> Path:
    """Set up migration directory structure.

    Creates the necessary directory structure for Alembic migrations
    and returns the migration directory path.

    Returns
    -------
    Path
        Path to the migration directory
    """
    create_migration_environment()
    return MIGRATION_DIR


def generate_initial_migration() -> Optional[str]:
    """Generate initial database migration.

    Creates the initial migration file with user and user_settings tables
    based on the SQLAlchemy models.

    Returns
    -------
    Optional[str]
        Migration file path if successful, None otherwise
    """
    try:
        # Ensure migration environment exists
        create_migration_environment()

        # Get Alembic configuration
        alembic_cfg = get_alembic_config()

        # Generate initial migration
        command.revision(
            alembic_cfg,
            message="Initial migration: users and user_settings tables",
            autogenerate=True
        )

        logger.info("Initial migration generated successfully")
        return "initial_migration_generated"

    except Exception as e:
        logger.error(f"Failed to generate initial migration: {e}")
        return None


def run_migrations() -> bool:
    """Run database migrations to latest version.

    Executes all pending migrations to bring the database schema
    up to the latest version.

    Returns
    -------
    bool
        True if migrations ran successfully, False otherwise
    """
    try:
        # Ensure migration environment exists
        create_migration_environment()

        # Get Alembic configuration
        alembic_cfg = get_alembic_config()

        # Run migrations
        command.upgrade(alembic_cfg, "head")

        logger.info("Migrations ran successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to run migrations: {e}")
        return False


def get_database_metadata() -> MetaData:
    """Get database metadata for migration generation.

    Returns the SQLAlchemy metadata containing all table definitions
    for the multi-user service models.

    Returns
    -------
    MetaData
        SQLAlchemy metadata with table definitions
    """
    return Base.metadata


def create_env_py_file(env_py_path: Path) -> None:
    """Create env.py file for Alembic migrations.

    Parameters
    ----------
    env_py_path : Path
        Path where env.py file should be created
    """
    env_py_content = '''"""Alembic environment configuration for multi-user EMUSES service."""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add the parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from emuses.multi_user_service.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''

    with open(env_py_path, 'w') as f:
        f.write(env_py_content)


def create_script_mako_file(script_mako_path: Path) -> None:
    """Create script.py.mako template file for Alembic migrations.

    Parameters
    ----------
    script_mako_path : Path
        Path where script.py.mako file should be created
    """
    script_mako_content = '''"""Migration script template for multi-user EMUSES service.

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    """Upgrade database schema."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrade database schema."""
    ${downgrades if downgrades else "pass"}
'''

    with open(script_mako_path, 'w') as f:
        f.write(script_mako_content)
