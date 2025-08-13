"""
Test suite for deployment validation and testing scripts.

Tests validate that deployment validation scripts can properly test
deployment health, connectivity, and readiness across environments.
"""
from pathlib import Path


class TestDeploymentValidation:
    """Test deployment validation and testing scripts."""

    def test_deployment_health_check_script_exists(self):
        """Test that deployment health check script exists."""
        health_script = Path("docker/scripts/health-check.sh")
        assert health_script.exists(), "Health check script should exist"
        assert health_script.is_file(), "Health check should be a file"

        # Check that script is executable
        assert health_script.stat().st_mode & 0o111, "Health check script should be executable"

    def test_connectivity_test_script_exists(self):
        """Test that connectivity test script exists."""
        connectivity_script = Path("docker/scripts/connectivity-test.sh")
        assert connectivity_script.exists(), "Connectivity test script should exist"
        assert connectivity_script.is_file(), "Connectivity test should be a file"

        # Check that script is executable
        assert connectivity_script.stat().st_mode & 0o111, "Connectivity test script should be executable"

    def test_deployment_validation_script_exists(self):
        """Test that main deployment validation script exists."""
        validation_script = Path("docker/scripts/validate-deployment.sh")
        assert validation_script.exists(), "Deployment validation script should exist"
        assert validation_script.is_file(), "Deployment validation should be a file"

        # Check that script is executable
        assert validation_script.stat().st_mode & 0o111, "Deployment validation script should be executable"

    def test_health_check_script_functionality(self):
        """Test that health check script has required functionality."""
        health_script = Path("docker/scripts/health-check.sh")

        with open(health_script, 'r') as f:
            content = f.read()

        # Should check API health endpoint
        assert "/api/v1/registry/health" in content, "Should check registry health endpoint"

        # Should check database connectivity
        assert "postgres" in content.lower() or "postgresql" in content.lower(), \
            "Should include database connectivity check"

        # Should check Redis connectivity
        assert "redis" in content.lower(), "Should include Redis connectivity check"

        # Should have proper exit codes
        assert "exit 0" in content, "Should have success exit code"
        assert "exit 1" in content, "Should have failure exit code"

    def test_connectivity_test_script_functionality(self):
        """Test that connectivity test script has required functionality."""
        connectivity_script = Path("docker/scripts/connectivity-test.sh")

        with open(connectivity_script, 'r') as f:
            content = f.read()

        # Should test network connectivity between services
        required_tests = [
            "api",
            "postgres",
            "redis",
            "nginx"
        ]

        for service in required_tests:
            assert service in content.lower(), f"Should test connectivity to {service}"

        # Should use appropriate tools for connectivity testing
        connectivity_tools = ["curl", "nc", "ping", "telnet"]
        assert any(tool in content for tool in connectivity_tools), \
            "Should use connectivity testing tools"

    def test_deployment_validation_script_completeness(self):
        """Test that deployment validation script performs comprehensive validation."""
        validation_script = Path("docker/scripts/validate-deployment.sh")

        with open(validation_script, 'r') as f:
            content = f.read()

        # Should call other validation scripts
        assert "health-check.sh" in content, "Should run health check validation"
        assert "connectivity-test.sh" in content, "Should run connectivity validation"

        # Should validate environment-specific configurations
        environments = ["development", "staging", "production"]
        environment_mentioned = any(env in content for env in environments)
        assert environment_mentioned, "Should handle environment-specific validation"

        # Should provide clear output
        assert "echo" in content, "Should provide status messages"
        assert "SUCCESS" in content or "PASS" in content, "Should indicate success status"
        assert "ERROR" in content or "FAIL" in content, "Should indicate failure status"

    def test_backup_validation_script_exists(self):
        """Test that backup validation script exists."""
        backup_validation_script = Path("docker/scripts/validate-backup.sh")
        assert backup_validation_script.exists(), "Backup validation script should exist"

    def test_monitoring_setup_validation_script_exists(self):
        """Test that monitoring setup validation script exists."""
        monitoring_script = Path("docker/scripts/validate-monitoring.sh")
        assert monitoring_script.exists(), "Monitoring validation script should exist"

    def test_security_validation_script_exists(self):
        """Test that security validation script exists."""
        security_script = Path("docker/scripts/validate-security.sh")
        assert security_script.exists(), "Security validation script should exist"

        with open(security_script, 'r') as f:
            content = f.read()

        # Should check security configurations
        security_checks = [
            "ssl",
            "https",
            "password",
            "secret",
            "permission"
        ]

        security_mentioned = any(check in content.lower() for check in security_checks)
        assert security_mentioned, "Should include security validation checks"

    def test_performance_baseline_script_exists(self):
        """Test that performance baseline validation script exists."""
        performance_script = Path("docker/scripts/validate-performance.sh")
        assert performance_script.exists(), "Performance validation script should exist"

    def test_validation_scripts_have_proper_structure(self):
        """Test that all validation scripts have proper shell script structure."""
        script_dir = Path("docker/scripts")
        validation_scripts = [
            "health-check.sh",
            "connectivity-test.sh",
            "validate-deployment.sh",
            "validate-backup.sh",
            "validate-monitoring.sh",
            "validate-security.sh",
            "validate-performance.sh"
        ]

        for script_name in validation_scripts:
            script_path = script_dir / script_name

            with open(script_path, 'r') as f:
                content = f.read()

            # Should have proper shebang
            assert content.startswith("#!/bin/bash") or content.startswith("#!/bin/sh"), \
                f"Script {script_name} should have proper shebang"

            # Should have error handling
            assert "set -e" in content or "trap" in content or "||" in content, \
                f"Script {script_name} should have error handling"

    def test_docker_compose_validation_integration(self):
        """Test that scripts work with docker-compose configurations."""
        validation_script = Path("docker/scripts/validate-deployment.sh")

        with open(validation_script, 'r') as f:
            content = f.read()

        # Should support different docker-compose configurations
        compose_configs = [
            "docker-compose.production.yml",
            "docker-compose.staging.yml",
            "docker-compose.backup.yml"
        ]

        compose_mentioned = any(config in content for config in compose_configs)
        assert compose_mentioned, "Should work with docker-compose configurations"
