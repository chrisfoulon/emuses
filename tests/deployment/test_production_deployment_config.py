"""
Test suite for production deployment configurations.

Tests validate that production deployment configurations are complete,
secure, and follow best practices for EMUSES production deployment.
"""
import pytest
import yaml
from pathlib import Path

@pytest.fixture(autouse=True)
def _run_from_repo_root(repo_cwd):
    """These tests assert on repo-relative paths (docker/, .github/, emuses/).

    The autouse `_isolate_cwd` fixture in tests/conftest.py runs every test in a
    throwaway directory, which is right for tests that write files but wrong for
    tests that inspect the repository's own layout. `repo_cwd` opts back in.
    """

class TestProductionDeploymentConfig:
    """Test production deployment configuration completeness and security."""

    def test_production_docker_compose_exists(self):
        """Test that production docker-compose configuration exists."""
        prod_compose_path = Path("docker-compose.production.yml")
        assert prod_compose_path.exists(), "Production docker-compose.yml should exist"

    def test_production_docker_compose_structure(self):
        """Test production docker-compose has required services and configurations."""
        prod_compose_path = Path("docker-compose.production.yml")

        with open(prod_compose_path, 'r') as f:
            config = yaml.safe_load(f)

        # Validate required services exist
        required_services = ['api', 'postgres', 'nginx', 'redis']
        for service in required_services:
            assert service in config['services'], f"Service {service} should be in production config"

        # Validate production-specific configurations
        api_service = config['services']['api']
        assert 'EMUSES_DEPLOYMENT_MODE=production' in str(api_service.get('environment', [])), \
            "API should be configured for production mode"

        # Validate resource limits are set for production
        assert 'deploy' in api_service, "API service should have deployment constraints"
        assert 'resources' in api_service['deploy'], "API service should have resource limits"

    def test_staging_docker_compose_exists(self):
        """Test that staging docker-compose configuration exists."""
        staging_compose_path = Path("docker-compose.staging.yml")
        assert staging_compose_path.exists(), "Staging docker-compose.yml should exist"

    def test_environment_files_exist(self):
        """Test that environment template files exist for different stages."""
        env_files = [
            "docker/environments/.env.production.template",
            "docker/environments/.env.staging.template",
            "docker/environments/.env.development.template"
        ]

        for env_file in env_files:
            env_path = Path(env_file)
            assert env_path.exists(), f"Environment template {env_file} should exist"

    def test_production_environment_variables(self):
        """Test production environment template has required security variables."""
        prod_env_path = Path("docker/environments/.env.production.template")

        with open(prod_env_path, 'r') as f:
            content = f.read()

        required_vars = [
            'POSTGRES_PASSWORD',
            'JWT_SECRET',
            'REDIS_PASSWORD',
            'SSL_CERT_PATH',
            'SSL_KEY_PATH',
            'BACKUP_ENCRYPTION_KEY'
        ]

        for var in required_vars:
            assert var in content, f"Production environment should include {var}"

    def test_production_security_configurations(self):
        """Test production configurations include security best practices."""
        prod_compose_path = Path("docker-compose.production.yml")

        with open(prod_compose_path, 'r') as f:
            config = yaml.safe_load(f)

        # Check PostgreSQL security
        postgres_config = config['services']['postgres']
        postgres_env = postgres_config.get('environment', [])

        # Should use scram-sha-256 authentication
        assert any('scram-sha-256' in str(env) for env in postgres_env), \
            "PostgreSQL should use scram-sha-256 authentication"

    def test_backup_configuration_exists(self):
        """Test that backup configuration is included in production setup."""
        backup_compose_path = Path("docker-compose.backup.yml")
        assert backup_compose_path.exists(), "Backup docker-compose configuration should exist"

    def test_production_health_checks(self):
        """Test that all production services have proper health checks."""
        prod_compose_path = Path("docker-compose.production.yml")

        with open(prod_compose_path, 'r') as f:
            config = yaml.safe_load(f)

        critical_services = ['api', 'postgres', 'nginx', 'redis']

        for service in critical_services:
            service_config = config['services'][service]
            assert 'healthcheck' in service_config, \
                f"Service {service} should have health check configuration"

            healthcheck = service_config['healthcheck']
            assert 'test' in healthcheck, f"Service {service} health check should have test command"
            assert 'interval' in healthcheck, f"Service {service} health check should have interval"
            assert 'retries' in healthcheck, f"Service {service} health check should have retries"

    def test_production_volume_configurations(self):
        """Test that production volumes are properly configured for persistence."""
        prod_compose_path = Path("docker-compose.production.yml")

        with open(prod_compose_path, 'r') as f:
            config = yaml.safe_load(f)

        # Check that persistent volumes are defined
        assert 'volumes' in config, "Production config should define volumes"

        required_volumes = ['postgres_data', 'redis_data', 'model_storage', 'backup_storage']
        for volume in required_volumes:
            assert volume in config['volumes'], f"Volume {volume} should be defined"

    def test_production_network_configuration(self):
        """Test that production network is properly configured."""
        prod_compose_path = Path("docker-compose.production.yml")

        with open(prod_compose_path, 'r') as f:
            config = yaml.safe_load(f)

        # Check network configuration
        assert 'networks' in config, "Production config should define networks"
        assert 'emuses-production' in config['networks'], "Should have production network"

        # Verify services use the production network
        for service_name, service_config in config['services'].items():
            assert 'networks' in service_config, f"Service {service_name} should specify networks"
            assert 'emuses-production' in service_config['networks'], \
                f"Service {service_name} should use production network"
