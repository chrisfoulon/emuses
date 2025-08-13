"""
Test suite for environment-specific configuration templates.

Tests validate that environment templates are properly configured
for development, staging, and production environments.
"""
from pathlib import Path


class TestEnvironmentTemplates:
    """Test environment-specific configuration templates."""

    def test_development_environment_template_configuration(self):
        """Test development environment template has appropriate development settings."""
        dev_env_path = Path("docker/environments/.env.development.template")

        with open(dev_env_path, 'r') as f:
            content = f.read()

        # Development should have relaxed security for ease of development
        assert "EMUSES_DEPLOYMENT_MODE=development" in content
        assert "LOG_LEVEL=DEBUG" in content
        assert "JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440" in content  # 24 hours
        assert "DEV_RELOAD=true" in content
        assert "DEV_DEBUG_MODE=true" in content

        # Development should use local/minimal resources
        assert "EMUSES_MAX_WORKERS=2" in content
        assert "MAX_CONCURRENT_JOBS=2" in content
        assert "FEATURE_CLOUD_SYNC=false" in content

    def test_staging_environment_template_configuration(self):
        """Test staging environment template has appropriate staging settings."""
        staging_env_path = Path("docker/environments/.env.staging.template")

        with open(staging_env_path, 'r') as f:
            content = f.read()

        # Staging should be production-like but with test configurations
        assert "EMUSES_DEPLOYMENT_MODE=staging" in content
        assert "LOG_LEVEL=DEBUG" in content  # More verbose than prod
        assert "JWT_ACCESS_TOKEN_EXPIRE_MINUTES=120" in content  # Less strict than prod
        assert "emuses_db_staging" in content  # Separate database

        # Staging should have moderate resource limits
        assert "EMUSES_MAX_WORKERS=4" in content
        assert "MAX_CONCURRENT_JOBS=5" in content
        assert "BACKUP_RETENTION_DAYS=7" in content  # Shorter than prod

    def test_production_environment_template_configuration(self):
        """Test production environment template has appropriate production settings."""
        prod_env_path = Path("docker/environments/.env.production.template")

        with open(prod_env_path, 'r') as f:
            content = f.read()

        # Production should have secure, optimized settings
        assert "EMUSES_DEPLOYMENT_MODE=production" in content
        assert "LOG_LEVEL=INFO" in content
        assert "JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30" in content  # Strict security
        assert "emuses_db" in content  # Production database name

        # Production should have high resource limits
        assert "EMUSES_MAX_WORKERS=8" in content
        assert "MAX_CONCURRENT_JOBS=10" in content
        assert "BACKUP_RETENTION_DAYS=30" in content  # Long retention

    def test_environment_template_security_progression(self):
        """Test that security settings become more restrictive from dev to prod."""
        environments = {
            'development': Path("docker/environments/.env.development.template"),
            'staging': Path("docker/environments/.env.staging.template"),
            'production': Path("docker/environments/.env.production.template")
        }

        jwt_expiry = {}
        rate_limits = {}

        for env_name, env_path in environments.items():
            with open(env_path, 'r') as f:
                content = f.read()

            # Extract JWT expiry times
            for line in content.split('\n'):
                if 'JWT_ACCESS_TOKEN_EXPIRE_MINUTES=' in line:
                    value = line.split('=')[1].split()[0]  # Take first word, ignore comments
                    jwt_expiry[env_name] = int(value)
                if 'SECURITY_RATE_LIMIT_PER_MINUTE=' in line:
                    value = line.split('=')[1].split()[0]  # Take first word, ignore comments
                    rate_limits[env_name] = int(value)

        # Security should become more restrictive: dev > staging > production
        assert jwt_expiry['development'] > jwt_expiry['staging']
        assert jwt_expiry['staging'] > jwt_expiry['production']
        assert rate_limits['development'] > rate_limits['staging']
        assert rate_limits['staging'] > rate_limits['production']

    def test_environment_template_resource_scaling(self):
        """Test that resource allocations scale appropriately across environments."""
        environments = {
            'development': Path("docker/environments/.env.development.template"),
            'staging': Path("docker/environments/.env.staging.template"),
            'production': Path("docker/environments/.env.production.template")
        }

        max_workers = {}
        max_jobs = {}

        for env_name, env_path in environments.items():
            with open(env_path, 'r') as f:
                content = f.read()

            # Extract resource settings
            for line in content.split('\n'):
                if 'EMUSES_MAX_WORKERS=' in line:
                    value = line.split('=')[1].split()[0]  # Take first word, ignore comments
                    max_workers[env_name] = int(value)
                if 'MAX_CONCURRENT_JOBS=' in line:
                    value = line.split('=')[1].split()[0]  # Take first word, ignore comments
                    max_jobs[env_name] = int(value)

        # Resources should scale: development < staging < production
        assert max_workers['development'] < max_workers['staging']
        assert max_workers['staging'] < max_workers['production']
        assert max_jobs['development'] < max_jobs['staging']
        assert max_jobs['staging'] < max_jobs['production']

    def test_environment_template_feature_flags(self):
        """Test that feature flags are appropriately configured per environment."""
        dev_path = Path("docker/environments/.env.development.template")
        staging_path = Path("docker/environments/.env.staging.template")
        prod_path = Path("docker/environments/.env.production.template")

        with open(dev_path, 'r') as f:
            dev_content = f.read()
        with open(staging_path, 'r') as f:
            staging_content = f.read()
        with open(prod_path, 'r') as f:
            prod_content = f.read()

        # Cloud sync should be disabled in development but enabled elsewhere
        assert "FEATURE_CLOUD_SYNC=false" in dev_content
        assert "FEATURE_CLOUD_SYNC=true" in staging_content
        assert "FEATURE_CLOUD_SYNC=true" in prod_content

        # All environments should have analytics and search enabled
        for content in [dev_content, staging_content, prod_content]:
            assert "FEATURE_ANALYTICS=true" in content
            assert "FEATURE_ADVANCED_SEARCH=true" in content
            assert "FEATURE_MODEL_SHARING=true" in content

    def test_environment_template_database_configuration(self):
        """Test that database configurations are environment-specific."""
        environments = {
            'development': ('emuses_db_dev', 5433),
            'staging': ('emuses_db_staging', 5432),
            'production': ('emuses_db', 5432)
        }

        for env_name, (expected_db, expected_port) in environments.items():
            env_path = Path(f"docker/environments/.env.{env_name}.template")

            with open(env_path, 'r') as f:
                content = f.read()

            assert f"POSTGRES_DB={expected_db}" in content
            if env_name == 'development':
                assert f"POSTGRES_PORT={expected_port}" in content

    def test_environment_template_completeness(self):
        """Test that all required environment variables are present in each template."""
        required_vars = [
            'POSTGRES_PASSWORD',
            'JWT_SECRET',
            'EMUSES_DEPLOYMENT_MODE',
            'EMUSES_SERVICE_HOST',
            'EMUSES_SERVICE_PORT',
            'LOG_LEVEL'
        ]

        environments = ['development', 'staging', 'production']

        for env_name in environments:
            env_path = Path(f"docker/environments/.env.{env_name}.template")

            with open(env_path, 'r') as f:
                content = f.read()

            for var in required_vars:
                assert f"{var}=" in content, f"Variable {var} missing from {env_name} template"
