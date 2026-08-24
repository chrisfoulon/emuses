"""
Test suite for rollback and migration procedures.

Tests validate that rollback procedures are properly configured
for safe deployment rollbacks and data migrations.
"""
import pytest
from pathlib import Path

@pytest.fixture(autouse=True)
def _run_from_repo_root(repo_cwd):
    """These tests assert on repo-relative paths (docker/, .github/, emuses/).

    The autouse `_isolate_cwd` fixture in tests/conftest.py runs every test in a
    throwaway directory, which is right for tests that write files but wrong for
    tests that inspect the repository's own layout. `repo_cwd` opts back in.
    """

class TestRollbackProcedures:
    """Test rollback and migration procedure scripts and configurations."""

    def test_rollback_script_exists(self):
        """Test that main rollback script exists."""
        rollback_script = Path("docker/scripts/rollback-deployment.sh")
        assert rollback_script.exists(), "Rollback script should exist"
        assert rollback_script.is_file(), "Rollback should be a file"

        # Check that script is executable
        assert rollback_script.stat().st_mode & 0o111, "Rollback script should be executable"

    def test_database_migration_script_exists(self):
        """Test that database migration script exists."""
        migration_script = Path("docker/scripts/migrate-database.sh")
        assert migration_script.exists(), "Database migration script should exist"
        assert migration_script.is_file(), "Migration script should be a file"

        # Check that script is executable
        assert migration_script.stat().st_mode & 0o111, "Migration script should be executable"

    def test_version_management_script_exists(self):
        """Test that version management script exists."""
        version_script = Path("docker/scripts/manage-versions.sh")
        assert version_script.exists(), "Version management script should exist"
        assert version_script.is_file(), "Version management should be a file"

        # Check that script is executable
        assert version_script.stat().st_mode & 0o111, "Version management script should be executable"

    def test_rollback_script_functionality(self):
        """Test that rollback script has required functionality."""
        rollback_script = Path("docker/scripts/rollback-deployment.sh")

        with open(rollback_script, 'r') as f:
            content = f.read()

        # Should support version targeting
        assert "--version" in content or "-v" in content, "Should support version targeting"

        # Should validate rollback safety
        assert "validate" in content.lower(), "Should validate rollback safety"

        # Should backup current state before rollback
        assert "backup" in content.lower(), "Should backup current state"

        # Should have safety checks
        assert "confirm" in content.lower() or "yes" in content.lower(), \
            "Should have confirmation prompts"

    def test_database_migration_functionality(self):
        """Test that database migration script has required functionality."""
        migration_script = Path("docker/scripts/migrate-database.sh")

        with open(migration_script, 'r') as f:
            content = f.read()

        # Should support forward and backward migrations
        assert "forward" in content.lower() or "up" in content.lower(), \
            "Should support forward migrations"
        assert "backward" in content.lower() or "down" in content.lower(), \
            "Should support backward migrations"

        # Should validate database state
        assert "validate" in content.lower(), "Should validate database state"

        # Should backup before migration
        assert "backup" in content.lower(), "Should backup before migration"

    def test_version_management_functionality(self):
        """Test that version management script has required functionality."""
        version_script = Path("docker/scripts/manage-versions.sh")

        with open(version_script, 'r') as f:
            content = f.read()

        # Should list available versions
        assert "list" in content.lower(), "Should support listing versions"

        # Should tag current deployment
        assert "tag" in content.lower(), "Should support tagging versions"

        # Should show current version
        assert "current" in content.lower(), "Should show current version"

        # Should support cleanup of old versions
        assert "cleanup" in content.lower() or "prune" in content.lower(), \
            "Should support version cleanup"

    def test_rollback_documentation_exists(self):
        """Test that rollback documentation exists."""
        rollback_docs = Path("docs/deployment/ROLLBACK_PROCEDURES.md")
        assert rollback_docs.exists(), "Rollback documentation should exist"

    def test_rollback_checklist_exists(self):
        """Test that rollback checklist exists."""
        rollback_checklist = Path("docs/deployment/ROLLBACK_CHECKLIST.md")
        assert rollback_checklist.exists(), "Rollback checklist should exist"

    def test_rollback_configuration_exists(self):
        """Test that rollback configuration is defined."""
        # Check for rollback configuration in docker-compose
        compose_files = ["docker-compose.production.yml", "docker-compose.staging.yml"]

        rollback_config_found = False
        for compose_file in compose_files:
            compose_path = Path(compose_file)
            if compose_path.exists():
                with open(compose_path, 'r') as f:
                    content = f.read()

                # Should have version labels or tags
                if "version" in content.lower() or "tag" in content.lower():
                    rollback_config_found = True
                    break

        assert rollback_config_found, "Rollback configuration should exist in compose files"

    def test_migration_validation_script_exists(self):
        """Test that migration validation script exists."""
        validation_script = Path("docker/scripts/validate-migration.sh")
        assert validation_script.exists(), "Migration validation script should exist"

    def test_rollback_scripts_have_proper_structure(self):
        """Test that rollback scripts have proper shell script structure."""
        script_dir = Path("docker/scripts")
        rollback_scripts = [
            "rollback-deployment.sh",
            "migrate-database.sh",
            "manage-versions.sh",
            "validate-migration.sh"
        ]

        for script_name in rollback_scripts:
            script_path = script_dir / script_name

            with open(script_path, 'r') as f:
                content = f.read()

            # Should have proper shebang
            assert content.startswith("#!/bin/bash") or content.startswith("#!/bin/sh"), \
                f"Script {script_name} should have proper shebang"

            # Should have error handling
            assert "set -e" in content or "trap" in content or "||" in content, \
                f"Script {script_name} should have error handling"

            # Should have logging/output
            assert "echo" in content or "printf" in content, \
                f"Script {script_name} should provide output"

    def test_rollback_safety_features(self):
        """Test that rollback scripts have proper safety features."""
        rollback_script = Path("docker/scripts/rollback-deployment.sh")

        with open(rollback_script, 'r') as f:
            content = f.read()

        # Should have confirmation prompt
        safety_features = ["confirm", "yes", "prompt", "read -p"]
        safety_found = any(feature in content.lower() for feature in safety_features)
        assert safety_found, "Rollback should have confirmation prompts"

        # Should validate target version exists
        assert "exist" in content.lower() or "available" in content.lower(), \
            "Should validate target version exists"

        # Should have abort mechanism
        abort_mechanisms = ["exit 1", "abort", "cancel", "stop"]
        abort_found = any(mechanism in content.lower() for mechanism in abort_mechanisms)
        assert abort_found, "Should have abort mechanism"

    def test_rollback_supports_different_environments(self):
        """Test that rollback supports different deployment environments."""
        rollback_script = Path("docker/scripts/rollback-deployment.sh")

        with open(rollback_script, 'r') as f:
            content = f.read()

        # Should support environment specification
        environments = ["production", "staging", "development"]
        env_support = any(env in content.lower() for env in environments)
        assert env_support, "Should support different environments"
