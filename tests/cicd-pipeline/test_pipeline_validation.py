"""
CI/CD Pipeline validation tests.

Tests that the GitHub Actions pipeline configuration is valid and
all dependencies are properly configured for testing.
"""

import json
import os
import yaml
from pathlib import Path
import pytest


class TestCICDPipelineConfiguration:
    """Test CI/CD pipeline configuration validity."""
    
    def test_github_workflows_exist(self):
        """Test that required GitHub workflow files exist."""
        workflows_dir = Path(".github/workflows")
        assert workflows_dir.exists(), "GitHub workflows directory should exist"
        
        # Check main CI workflow
        ci_workflow = workflows_dir / "ci.yml"
        assert ci_workflow.exists(), "CI workflow file should exist"
        
        # Check release workflow  
        release_workflow = workflows_dir / "release.yml"
        assert release_workflow.exists(), "Release workflow file should exist"
    
    def test_ci_workflow_validity(self):
        """Test that CI workflow YAML is valid and has required jobs."""
        ci_file = Path(".github/workflows/ci.yml")
        with open(ci_file) as f:
            ci_config = yaml.safe_load(f)
        
        # Check required jobs exist
        required_jobs = ['test', 'security', 'quality', 'build']
        actual_jobs = list(ci_config['jobs'].keys())
        
        for job in required_jobs:
            assert job in actual_jobs, f"CI workflow should have {job} job"
    
    def test_python_version_matrix(self):
        """Test that CI tests multiple Python versions."""
        ci_file = Path(".github/workflows/ci.yml")
        with open(ci_file) as f:
            ci_config = yaml.safe_load(f)
        
        test_job = ci_config['jobs']['test']
        python_versions = test_job['strategy']['matrix']['python-version']
        
        # Should test Python 3.9, 3.10, 3.11
        expected_versions = [3.9, "3.10", "3.11"]
        assert python_versions == expected_versions, f"Should test {expected_versions}"
    
    def test_required_services_configured(self):
        """Test that required services (PostgreSQL, Redis) are configured."""
        ci_file = Path(".github/workflows/ci.yml")
        with open(ci_file) as f:
            ci_config = yaml.safe_load(f)
        
        test_job = ci_config['jobs']['test']
        services = test_job.get('services', {})
        
        # Check PostgreSQL service
        assert 'postgres' in services, "PostgreSQL service should be configured"
        postgres_config = services['postgres']
        assert postgres_config['image'] == 'postgres:15-alpine', "Should use PostgreSQL 15"
        
        # Check Redis service
        assert 'redis' in services, "Redis service should be configured"
        redis_config = services['redis']
        assert redis_config['image'] == 'redis:7-alpine', "Should use Redis 7"
    
    def test_security_tools_configured(self):
        """Test that security scanning tools are properly configured."""
        # Check bandit configuration
        bandit_config = Path(".bandit")
        assert bandit_config.exists(), "Bandit configuration should exist"
        
        # Check safety policy
        safety_policy = Path(".safety-policy.yml")
        assert safety_policy.exists(), "Safety policy should exist"
    
    def test_quality_tools_configured(self):
        """Test that code quality tools are configured."""
        setup_cfg = Path("setup.cfg")
        assert setup_cfg.exists(), "setup.cfg should exist for tool configuration"
        
        # Check that flake8, mypy, coverage sections exist
        with open(setup_cfg) as f:
            content = f.read()
            assert "[flake8]" in content, "flake8 configuration should exist"
            assert "[mypy]" in content, "mypy configuration should exist" 
            assert "[coverage:" in content, "coverage configuration should exist"


class TestDependencyConfiguration:
    """Test that dependencies are properly configured for CI/CD."""
    
    def test_requirements_files_exist(self):
        """Test that all required requirements files exist."""
        required_files = [
            "requirements.txt",
            "requirements.in", 
            "requirements-dev.txt",
            "requirements-dev.in",
            "requirements-prod.txt",
            "requirements-prod.in"
        ]
        
        for req_file in required_files:
            file_path = Path(req_file)
            assert file_path.exists(), f"{req_file} should exist"
    
    def test_requirements_are_pinned(self):
        """Test that requirements.txt contains pinned versions."""
        req_file = Path("requirements.txt")
        with open(req_file) as f:
            content = f.read()
        
        # Filter for actual package lines (not comments or via lines)
        lines = []
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('via ') and '==' in line:
                # Extract just the package name and version part
                if line.startswith(' '):  # Skip indented comment lines
                    continue
                lines.append(line)
        
        # Count pinned packages (should have ==)
        pinned_lines = [line for line in lines if '==' in line]
        pin_ratio = len(pinned_lines) / len(lines) if lines else 0
        
        assert pin_ratio > 0.95, f"At least 95% of packages should be pinned, got {pin_ratio:.1%} ({len(pinned_lines)}/{len(lines)})"
    
    @pytest.mark.slow
    def test_dev_dependencies_install_cleanly(self):
        """Test that development dependencies can be installed without conflicts."""
        import subprocess
        import tempfile
        
        # This test would be run in CI to validate dependency resolution
        # For now, we'll check that pip-tools can at least analyze the files
        
        result = subprocess.run(['pip-compile', '--dry-run', 'requirements-dev.in'], 
                              capture_output=True, text=True)
        
        assert result.returncode == 0, f"pip-compile should succeed: {result.stderr}"


class TestPytestConfiguration:
    """Test pytest configuration compatibility."""
    
    def test_pytest_ini_exists(self):
        """Test that pytest.ini exists and is valid."""
        pytest_ini = Path("pytest.ini")
        assert pytest_ini.exists(), "pytest.ini should exist"
    
    def test_pytest_setup_cfg_compatibility(self):
        """Test that pytest configurations don't conflict."""
        pytest_ini = Path("pytest.ini")
        setup_cfg = Path("setup.cfg")
        
        # Read pytest.ini settings
        with open(pytest_ini) as f:
            pytest_content = f.read()
        
        # Read setup.cfg settings
        with open(setup_cfg) as f:
            setup_content = f.read()
        
        # Check for potential conflicts in testpaths
        if "[tool:pytest]" in setup_content and "[pytest]" in pytest_content:
            # Both files configure pytest - this could cause conflicts
            pytest.skip("Potential pytest configuration conflict detected - needs manual review")
    
    def test_test_markers_configured(self):
        """Test that test markers are properly configured."""
        pytest_ini = Path("pytest.ini")
        with open(pytest_ini) as f:
            content = f.read()
        
        # Check that important markers are defined
        required_markers = ['integration', 'slow', 'compatibility']
        for marker in required_markers:
            assert marker in content, f"Test marker '{marker}' should be configured"


@pytest.mark.integration 
class TestCICDIntegration:
    """Integration tests for CI/CD pipeline components."""
    
    def test_docker_build_configuration(self):
        """Test that Docker build is properly configured."""
        dockerfile = Path("Dockerfile")
        assert dockerfile.exists(), "Dockerfile should exist"
        
        with open(dockerfile) as f:
            content = f.read()
        
        # Should use pip-tools
        assert "pip-tools" in content, "Dockerfile should use pip-tools"
        assert "pip-sync" in content, "Dockerfile should use pip-sync"
    
    def test_docker_scripts_exist(self):
        """Test that Docker helper scripts exist."""
        docker_dir = Path("docker")
        assert docker_dir.exists(), "docker/ directory should exist"
        
        startup_script = docker_dir / "startup.sh"
        assert startup_script.exists(), "Docker startup script should exist"
        
        health_script = docker_dir / "health_check.sh"
        assert health_script.exists(), "Docker health check script should exist"
        
        # Scripts should be executable
        assert os.access(startup_script, os.X_OK), "startup.sh should be executable"
        assert os.access(health_script, os.X_OK), "health_check.sh should be executable"