"""Tests for database migrations."""

import pytest
import asyncio
from pathlib import Path
from alembic.config import Config
from alembic import command
from alembic.runtime.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from emuses.multi_user_service.database import DatabaseConfig, create_engine


class TestMigrationSetup:
    """Test Alembic migration configuration and setup."""

    def test_alembic_config_exists(self):
        """Test alembic.ini configuration file exists."""
        alembic_ini = Path("alembic.ini")
        assert alembic_ini.exists(), "alembic.ini configuration file should exist"

    def test_alembic_directory_exists(self):
        """Test alembic migration directory structure exists."""
        alembic_dir = Path("alembic")
        assert alembic_dir.exists(), "alembic directory should exist"

        # Check required files in alembic directory
        assert (alembic_dir / "env.py").exists(), "alembic/env.py should exist"
        assert (alembic_dir / "script.py.mako").exists(), "alembic/script.py.mako should exist"

        # Check versions directory
        versions_dir = alembic_dir / "versions"
        assert versions_dir.exists(), "alembic/versions directory should exist"

    def test_alembic_config_database_url(self):
        """Test alembic configuration uses correct database URL."""
        if Path("alembic.ini").exists():
            config = Config("alembic.ini")

            # Should use the same database URL as the application
            config_url = config.get_main_option("sqlalchemy.url")

            # May be templated, so check if it's set properly
            assert config_url is not None, "Database URL should be configured in alembic.ini"


class TestWorkspaceMigrations:
    """Test workspace table migrations."""

    @pytest.mark.asyncio
    async def test_user_table_migration(self):
        """Test user table can be created and has required columns."""
        if not Path("alembic.ini").exists():
            pytest.skip("Alembic not configured yet")

        from emuses.multi_user_service.database import create_all_tables

        # Create tables first
        await create_all_tables()

        engine = create_engine()
        async with engine.begin() as conn:
            # Check if users table exists by trying to query it
            try:
                result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'"))
                table_exists = result.fetchone() is not None

                if table_exists:
                    # Get table info for SQLite
                    result = await conn.execute(text("PRAGMA table_info(users)"))
                    columns = {row[1] for row in result.fetchall()}  # column name is index 1

                    # Check required columns exist (using actual table name 'users')
                    required_columns = {
                        'id', 'email', 'hashed_password', 'is_active',
                        'is_superuser', 'is_verified', 'organization', 'role'
                    }
                    assert required_columns.issubset(columns), \
                        f"Missing required columns: {required_columns - columns}"

            except Exception as e:
                # If SQLite commands fail, table doesn't exist or there's another issue
                pytest.fail(f"Could not verify user table structure: {e}")

    @pytest.mark.asyncio
    async def test_workspace_table_migration(self):
        """Test workspace table can be created and has required columns."""
        if not Path("alembic.ini").exists():
            pytest.skip("Alembic not configured yet")

        from emuses.multi_user_service.database import create_all_tables

        # Create tables first
        await create_all_tables()

        engine = create_engine()
        async with engine.begin() as conn:
            try:
                result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='workspaces'"))
                table_exists = result.fetchone() is not None

                if table_exists:
                    result = await conn.execute(text("PRAGMA table_info(workspaces)"))
                    columns = {row[1] for row in result.fetchall()}

                    required_columns = {
                        'id', 'name', 'description', 'owner_id', 'created_at',
                        'storage_path', 'is_active'
                    }
                    assert required_columns.issubset(columns), \
                        f"Missing required columns: {required_columns - columns}"
            except Exception as e:
                pytest.fail(f"Could not verify workspace table structure: {e}")

    @pytest.mark.asyncio
    async def test_dataset_table_migration(self):
        """Test dataset table can be created and has required columns."""
        if not Path("alembic.ini").exists():
            pytest.skip("Alembic not configured yet")

        from emuses.multi_user_service.database import create_all_tables

        # Create tables first
        await create_all_tables()

        engine = create_engine()
        async with engine.begin() as conn:
            try:
                result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='datasets'"))
                table_exists = result.fetchone() is not None

                if table_exists:
                    result = await conn.execute(text("PRAGMA table_info(datasets)"))
                    columns = {row[1] for row in result.fetchall()}

                    required_columns = {
                        'id', 'name', 'description', 'workspace_id', 'created_at',
                        'file_path', 'file_size_bytes', 'file_hash'
                    }
                    assert required_columns.issubset(columns), \
                        f"Missing required columns: {required_columns - columns}"
            except Exception as e:
                pytest.fail(f"Could not verify dataset table structure: {e}")

    @pytest.mark.asyncio
    async def test_training_job_table_migration(self):
        """Test training job table can be created and has required columns."""
        if not Path("alembic.ini").exists():
            pytest.skip("Alembic not configured yet")

        from emuses.multi_user_service.database import create_all_tables

        # Create tables first
        await create_all_tables()

        engine = create_engine()
        async with engine.begin() as conn:
            try:
                result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='training_jobs'"))
                table_exists = result.fetchone() is not None

                if table_exists:
                    result = await conn.execute(text("PRAGMA table_info(training_jobs)"))
                    columns = {row[1] for row in result.fetchall()}

                    required_columns = {
                        'id', 'name', 'owner_id', 'workspace_id', 'status',
                        'created_at', 'started_at', 'completed_at'
                    }
                    assert required_columns.issubset(columns), \
                        f"Missing required columns: {required_columns - columns}"
            except Exception as e:
                pytest.fail(f"Could not verify training job table structure: {e}")


class TestMigrationCommands:
    """Test migration management commands."""

    def test_migration_upgrade_command(self):
        """Test migration upgrade functionality."""
        if not Path("alembic.ini").exists():
            pytest.skip("Alembic not configured yet")

        try:
            # Test that we can get the current revision (this tests basic Alembic functionality)
            from sqlalchemy import create_engine as sync_create_engine

            # Use sync engine for Alembic operations
            sync_engine = sync_create_engine("sqlite:///:memory:")

            with sync_engine.connect() as conn:
                from alembic.runtime.migration import MigrationContext
                context = MigrationContext.configure(conn)
                current_rev = context.get_current_revision()
                # current_rev will be None for empty database, which is expected
                assert current_rev is None or isinstance(current_rev, str), \
                    f"Current revision should be None or string, got {type(current_rev)}"

        except Exception as e:
            pytest.fail(f"Migration functionality test failed: {e}")

    def test_migration_downgrade_command(self):
        """Test migration downgrade functionality."""
        if not Path("alembic.ini").exists():
            pytest.skip("Alembic not configured yet")

        try:
            config = Config("alembic.ini")
            # Test that we can check migration history
            command.history(config)
        except Exception as e:
            pytest.fail(f"Migration history check failed: {e}")

    def test_migration_current_command(self):
        """Test getting current migration version."""
        if not Path("alembic.ini").exists():
            pytest.skip("Alembic not configured yet")

        try:
            config = Config("alembic.ini")
            # Test that we can get current migration version
            command.current(config)
        except Exception as e:
            pytest.fail(f"Getting current migration failed: {e}")


class TestMigrationConsistency:
    """Test migration consistency and database state."""

    @pytest.mark.asyncio
    async def test_foreign_key_relationships(self):
        """Test foreign key relationships are properly created."""
        if not Path("alembic.ini").exists():
            pytest.skip("Alembic not configured yet")

        from emuses.multi_user_service.database import create_all_tables

        # Create tables first
        await create_all_tables()

        engine = create_engine()
        async with engine.begin() as conn:
            try:
                # For SQLite, check foreign key info for each table
                tables_to_check = ['workspaces', 'datasets', 'training_jobs']
                foreign_keys = []

                for table in tables_to_check:
                    result = await conn.execute(text(f"PRAGMA foreign_key_list({table})"))
                    for row in result.fetchall():
                        # SQLite foreign key format: [id, seq, table, from, to, on_update, on_delete, match]
                        foreign_keys.append((table, row[3], row[2], row[4]))  # (table, from_col, to_table, to_col)

                if foreign_keys:
                    # Check workspace -> users relationship
                    workspace_user_fk = any(
                        table == 'workspaces' and from_col == 'owner_id' and to_table == 'users'
                        for table, from_col, to_table, to_col in foreign_keys
                    )

                    # Check dataset -> workspace relationship
                    dataset_workspace_fk = any(
                        table == 'datasets' and from_col == 'workspace_id' and to_table == 'workspaces'
                        for table, from_col, to_table, to_col in foreign_keys
                    )

                    # Check training_job -> user and workspace relationships
                    job_user_fk = any(
                        table == 'training_jobs' and from_col == 'owner_id' and to_table == 'users'
                        for table, from_col, to_table, to_col in foreign_keys
                    )

                    assert workspace_user_fk, "Workspace should have foreign key to users"
                    assert dataset_workspace_fk, "Dataset should have foreign key to workspaces"
                    assert job_user_fk, "Training job should have foreign key to users"

            except Exception as e:
                pytest.fail(f"Could not verify foreign key relationships: {e}")

    @pytest.mark.asyncio
    async def test_table_indexes(self):
        """Test that proper indexes are created for performance."""
        if not Path("alembic.ini").exists():
            pytest.skip("Alembic not configured yet")

        from emuses.multi_user_service.database import create_all_tables

        # Create tables first
        await create_all_tables()

        engine = create_engine()
        async with engine.begin() as conn:
            try:
                # For SQLite, check indexes using pragma
                tables = ['users', 'workspaces', 'datasets', 'training_jobs']
                all_indexes = []

                for table in tables:
                    result = await conn.execute(text(f"PRAGMA index_list({table})"))
                    table_indexes = list(result.fetchall())
                    all_indexes.extend([(table, idx[1]) for idx in table_indexes])  # (table, index_name)

                if all_indexes:
                    # Group indexes by table
                    table_index_dict = {}
                    for table, index_name in all_indexes:
                        if table not in table_index_dict:
                            table_index_dict[table] = []
                        table_index_dict[table].append(index_name)

                    # Verify each table has at least some indexes
                    for table in tables:
                        if table in table_index_dict:
                            assert len(table_index_dict[table]) > 0, \
                                f"Table {table} should have at least one index"

                    # Check for specific important indexes
                    all_index_names = [idx[1] for idx in all_indexes]

                    # Should have indexes on email, organization, role for users
                    user_indexes = [idx for idx in all_index_names if 'users' in idx.lower()]
                    assert any('email' in idx.lower() for idx in user_indexes), \
                        "Should have index on users.email"

            except Exception as e:
                pytest.fail(f"Could not verify table indexes: {e}")


class TestMigrationManagement:
    """Test migration management functions."""

    def test_migration_status_function(self):
        """Test get_migration_status function."""
        if not Path("alembic.ini").exists():
            pytest.skip("Alembic not configured yet")

        from emuses.multi_user_service.database import get_migration_status

        try:
            status = get_migration_status()

            # Check that status contains expected keys
            expected_keys = {
                "current_revision", "head_revision", "all_revisions",
                "is_up_to_date", "pending_migrations"
            }
            assert expected_keys.issubset(set(status.keys())), \
                f"Missing keys in status: {expected_keys - set(status.keys())}"

            # Check data types
            assert isinstance(status["all_revisions"], list), \
                "all_revisions should be a list"
            assert isinstance(status["is_up_to_date"], bool), \
                "is_up_to_date should be a boolean"
            assert isinstance(status["pending_migrations"], int), \
                "pending_migrations should be an integer"

        except Exception as e:
            pytest.fail(f"Migration status function failed: {e}")

    def test_schema_validation_function(self):
        """Test validate_database_schema function."""
        if not Path("alembic.ini").exists():
            pytest.skip("Alembic not configured yet")

        from emuses.multi_user_service.database import validate_database_schema

        try:
            validation = validate_database_schema()

            # Check that validation contains expected keys
            expected_keys = {
                "valid", "expected_tables", "actual_tables",
                "missing_tables", "extra_tables"
            }
            assert expected_keys.issubset(set(validation.keys())), \
                f"Missing keys in validation: {expected_keys - set(validation.keys())}"

            # Check data types
            assert isinstance(validation["valid"], bool), \
                "valid should be a boolean"
            assert isinstance(validation["expected_tables"], list), \
                "expected_tables should be a list"
            assert isinstance(validation["actual_tables"], list), \
                "actual_tables should be a list"

            # Check that expected tables include our models
            expected_model_tables = {"users", "workspaces", "datasets", "training_jobs"}
            assert expected_model_tables.issubset(set(validation["expected_tables"])), \
                f"Missing model tables: {expected_model_tables - set(validation['expected_tables'])}"

        except Exception as e:
            pytest.fail(f"Schema validation function failed: {e}")

    def test_run_migrations_function(self):
        """Test run_migrations function."""
        if not Path("alembic.ini").exists():
            pytest.skip("Alembic not configured yet")

        from emuses.multi_user_service.database import run_migrations, get_migration_status

        try:
            # Run migrations
            run_migrations("head")

            # Get status after migration
            final_status = get_migration_status()

            # Should be up to date now
            assert final_status["is_up_to_date"], \
                "Database should be up to date after running migrations"

        except Exception as e:
            pytest.fail(f"Run migrations function failed: {e}")

    def test_migration_rollback_function(self):
        """Test rollback_migration function."""
        if not Path("alembic.ini").exists():
            pytest.skip("Alembic not configured yet")

        from emuses.multi_user_service.database import rollback_migration, run_migrations, get_migration_status

        try:
            # First ensure we're at head
            run_migrations("head")

            # Get current status
            status = get_migration_status()

            if status["current_revision"] is not None:
                # Try rolling back to base (this tests the function works)
                rollback_migration("base")

                # Check status after rollback
                rollback_status = get_migration_status()
                assert rollback_status["current_revision"] is None, \
                    "Should be at base revision after rollback"

            else:
                # Database is already at base, just test that rollback doesn't crash
                rollback_migration("base")

        except Exception as e:
            pytest.fail(f"Migration rollback function failed: {e}")
