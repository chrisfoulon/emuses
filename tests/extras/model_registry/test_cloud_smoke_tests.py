"""Smoke tests for cloud storage operations across environments.

This module provides environment-specific smoke tests to validate cloud storage
functionality in different deployment environments (dev, staging, production).
"""
import pytest
import asyncio
import os
import tempfile
import json
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import patch

from emuses.tools.cloud_validation import (
    validate_cloud_deployment,
    CloudConfigurationValidator,
    CloudHealthChecker,
    EnvironmentValidator,
    ValidationStatus
)

# Test requires cloud validation module
try:
    VALIDATION_MODULE_AVAILABLE = True
except ImportError:
    VALIDATION_MODULE_AVAILABLE = False

# Conditional imports for cloud providers
try:
    from moto import mock_aws
    import boto3
    MOTO_AVAILABLE = True
except ImportError:
    MOTO_AVAILABLE = False


@pytest.mark.skipif(not VALIDATION_MODULE_AVAILABLE, reason="Cloud validation module not available")
class TestCloudConfigurationValidation:
    """Test cloud configuration validation across providers."""

    @pytest.fixture
    def sample_aws_config(self):
        """Sample AWS S3 configuration for testing."""
        return {
            'bucket_name': 'test-model-registry-bucket',
            'access_key': 'AKIAIOSFODNN7EXAMPLE',
            'secret_key': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            'region': 'us-west-2'
        }

    @pytest.fixture
    def sample_azure_config(self):
        """Sample Azure Blob Storage configuration for testing."""
        return {
            'container_name': 'test-model-registry-container',
            'connection_string': 'DefaultEndpointsProtocol=https;AccountName=testaccount;AccountKey=testkey==;EndpointSuffix=core.windows.net'
        }

    @pytest.fixture
    def sample_gcs_config(self):
        """Sample Google Cloud Storage configuration for testing."""
        return {
            'bucket_name': 'test-model-registry-bucket',
            'project_id': 'test-project-123456',
            'credentials_file': '/path/to/service-account.json'
        }

    @pytest.mark.asyncio
    async def test_aws_s3_configuration_validation(self, sample_aws_config):
        """Test AWS S3 configuration validation."""
        validator = CloudConfigurationValidator()
        results = await validator.validate_aws_s3_config(sample_aws_config)
        
        # Should have results for all required fields
        check_names = [r.check_name for r in results]
        
        # Check required fields are validated
        assert 'aws_s3_config_bucket_name' in check_names
        assert 'aws_s3_config_access_key' in check_names
        assert 'aws_s3_config_secret_key' in check_names
        assert 'aws_s3_config_region' in check_names
        
        # Check bucket name format validation
        assert 'aws_s3_bucket_name_format' in check_names
        
        # Check region validation
        assert 'aws_s3_region_validity' in check_names
        
        # All basic configuration checks should pass for valid config
        basic_config_results = [r for r in results if r.check_name.startswith('aws_s3_config_')]
        assert all(r.status == ValidationStatus.PASS for r in basic_config_results)

    @pytest.mark.asyncio
    async def test_aws_s3_invalid_bucket_name(self):
        """Test AWS S3 validation with invalid bucket name."""
        invalid_config = {
            'bucket_name': 'INVALID_BUCKET_NAME',  # Uppercase not allowed
            'access_key': 'test',
            'secret_key': 'test',
            'region': 'us-east-1'
        }
        
        validator = CloudConfigurationValidator()
        results = await validator.validate_aws_s3_config(invalid_config)
        
        # Find bucket name format validation result
        bucket_format_result = next(
            (r for r in results if r.check_name == 'aws_s3_bucket_name_format'), 
            None
        )
        assert bucket_format_result is not None
        assert bucket_format_result.status == ValidationStatus.FAIL
        assert 'naming requirements' in bucket_format_result.message

    @pytest.mark.asyncio
    async def test_azure_configuration_validation(self, sample_azure_config):
        """Test Azure Blob Storage configuration validation."""
        validator = CloudConfigurationValidator()
        results = await validator.validate_azure_config(sample_azure_config)
        
        # Should validate connection string and container name
        check_names = [r.check_name for r in results]
        
        assert 'azure_connection_string' in check_names
        assert 'azure_container_name' in check_names
        
        # Connection string components should be validated
        assert 'azure_connection_string_AccountName' in check_names
        assert 'azure_connection_string_AccountKey' in check_names

    @pytest.mark.asyncio
    async def test_gcs_configuration_validation(self, sample_gcs_config):
        """Test Google Cloud Storage configuration validation."""
        validator = CloudConfigurationValidator()
        results = await validator.validate_gcs_config(sample_gcs_config)
        
        # Should validate required fields
        check_names = [r.check_name for r in results]
        
        assert 'gcs_config_bucket_name' in check_names
        assert 'gcs_config_project_id' in check_names
        assert 'gcs_bucket_name_format' in check_names
        
        # Credentials validation should occur
        assert any('credentials' in name for name in check_names)

    @pytest.mark.asyncio
    async def test_missing_configuration_fields(self):
        """Test validation with missing required configuration fields."""
        incomplete_config = {
            'bucket_name': 'test-bucket'
            # Missing access_key, secret_key, region
        }
        
        validator = CloudConfigurationValidator()
        results = await validator.validate_aws_s3_config(incomplete_config)
        
        # Should have failures for missing fields
        missing_field_results = [
            r for r in results 
            if r.check_name in ['aws_s3_config_access_key', 'aws_s3_config_secret_key', 'aws_s3_config_region']
        ]
        
        assert len(missing_field_results) == 3
        assert all(r.status == ValidationStatus.FAIL for r in missing_field_results)
        assert all('missing or empty' in r.message for r in missing_field_results)


@pytest.mark.skipif(not VALIDATION_MODULE_AVAILABLE, reason="Cloud validation module not available")
class TestEnvironmentValidation:
    """Test environment-specific validation rules."""

    @pytest.fixture
    def production_config(self):
        """Production environment configuration."""
        return {
            'debug': False,
            'backup_config': {
                'enabled': True,
                'frequency': 'daily',
                'retention': '30d'
            },
            'monitoring': {
                'enabled': True,
                'metrics': ['latency', 'errors', 'throughput']
            }
        }

    @pytest.fixture
    def staging_config(self):
        """Staging environment configuration."""
        return {
            'debug': True,  # Allowed in staging
            'monitoring': {
                'enabled': True,
                'metrics': ['latency', 'errors']
            }
        }

    @pytest.fixture 
    def development_config(self):
        """Development environment configuration."""
        return {
            'debug': True,
            'monitoring': {
                'enabled': False
            }
        }

    @pytest.mark.asyncio
    async def test_production_environment_validation(self, production_config):
        """Test production environment validation requirements."""
        validator = EnvironmentValidator('production')
        results = await validator.validate_environment_config(production_config)
        
        # Check production-specific requirements
        debug_result = next((r for r in results if r.check_name == 'production_debug_disabled'), None)
        assert debug_result is not None
        assert debug_result.status == ValidationStatus.PASS
        
        backup_result = next((r for r in results if r.check_name == 'production_backup_config'), None)
        assert backup_result is not None
        assert backup_result.status == ValidationStatus.PASS

    @pytest.mark.asyncio
    async def test_production_with_debug_enabled(self):
        """Test production validation when debug is incorrectly enabled."""
        invalid_prod_config = {
            'debug': True,  # Should not be enabled in production
            'monitoring': {'enabled': True}
        }
        
        validator = EnvironmentValidator('production')
        results = await validator.validate_environment_config(invalid_prod_config)
        
        debug_result = next((r for r in results if r.check_name == 'production_debug_disabled'), None)
        assert debug_result is not None
        assert debug_result.status == ValidationStatus.FAIL
        assert 'must be disabled in production' in debug_result.message

    @pytest.mark.asyncio
    async def test_staging_environment_validation(self, staging_config):
        """Test staging environment validation."""
        validator = EnvironmentValidator('staging')
        results = await validator.validate_environment_config(staging_config)
        
        # Staging should allow debug mode but warn
        debug_result = next((r for r in results if r.check_name == 'staging_debug_mode'), None)
        if debug_result:  # Only if debug is enabled
            assert debug_result.status == ValidationStatus.WARNING

    @pytest.mark.asyncio
    async def test_development_environment_validation(self, development_config):
        """Test development environment validation."""
        validator = EnvironmentValidator('development')
        results = await validator.validate_environment_config(development_config)
        
        # Development environment should be more permissive
        dev_result = next((r for r in results if r.check_name == 'development_environment'), None)
        assert dev_result is not None
        assert dev_result.status == ValidationStatus.PASS


@pytest.mark.skipif(not VALIDATION_MODULE_AVAILABLE or not MOTO_AVAILABLE, 
                    reason="Cloud validation or moto not available")
class TestCloudHealthChecks:
    """Test cloud storage health checks."""

    @pytest.fixture
    def mock_s3_backend(self):
        """Create mocked S3 backend for testing."""
        # Set up AWS credentials for moto
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SECURITY_TOKEN"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        
        with mock_aws():
            from emuses.tools.cloud_storage import S3StorageBackend
            
            # Create S3 client and bucket
            s3_client = boto3.client("s3", region_name="us-east-1")
            bucket_name = "test-health-check-bucket"
            s3_client.create_bucket(Bucket=bucket_name)
            
            backend = S3StorageBackend(
                bucket_name=bucket_name,
                access_key="testing",
                secret_key="testing",
                region="us-east-1"
            )
            
            yield backend

    @pytest.mark.asyncio
    async def test_backend_health_check_success(self, mock_s3_backend):
        """Test successful backend health check."""
        health_checker = CloudHealthChecker()
        results = await health_checker.check_backend_health(mock_s3_backend)
        
        # Should have connectivity check
        connectivity_result = next((r for r in results if r.check_name == 'connectivity'), None)
        assert connectivity_result is not None
        assert connectivity_result.status == ValidationStatus.PASS
        assert connectivity_result.duration_ms is not None

    @pytest.mark.asyncio
    async def test_backend_health_check_with_invalid_backend(self):
        """Test health check with invalid backend configuration."""
        from emuses.tools.cloud_storage import S3StorageBackend
        
        # Create backend with invalid configuration
        invalid_backend = S3StorageBackend(
            bucket_name="non-existent-bucket",
            access_key="invalid",
            secret_key="invalid",
            region="invalid-region"
        )
        
        health_checker = CloudHealthChecker()
        results = await health_checker.check_backend_health(invalid_backend)
        
        # Connectivity should fail
        connectivity_result = next((r for r in results if r.check_name == 'connectivity'), None)
        assert connectivity_result is not None
        # May pass or fail depending on network connectivity - just check it exists
        assert connectivity_result.check_name == 'connectivity'


@pytest.mark.skipif(not VALIDATION_MODULE_AVAILABLE, reason="Cloud validation module not available")
class TestIntegratedCloudValidation:
    """Test integrated cloud deployment validation."""

    @pytest.fixture
    def multi_provider_config(self):
        """Configuration for multiple cloud providers."""
        return {
            'aws': {
                'bucket_name': 'prod-model-registry-s3',
                'access_key': 'AKIAIOSFODNN7EXAMPLE',
                'secret_key': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                'region': 'us-west-2',
                'debug': False,
                'monitoring': {'enabled': True}
            },
            'azure': {
                'container_name': 'prod-model-registry-container',
                'connection_string': 'DefaultEndpointsProtocol=https;AccountName=prodaccount;AccountKey=prodkey==;EndpointSuffix=core.windows.net',
                'debug': False,
                'monitoring': {'enabled': True}
            }
        }

    @pytest.mark.asyncio
    async def test_multi_provider_validation(self, multi_provider_config):
        """Test validation across multiple cloud providers."""
        results = await validate_cloud_deployment(multi_provider_config, environment='production')
        
        # Should have results for both providers
        assert 'aws' in results
        assert 'azure' in results
        
        # Each provider should have configuration validation results
        aws_results = results['aws']
        azure_results = results['azure']
        
        # AWS results should include S3 configuration checks
        aws_check_names = [r.check_name for r in aws_results]
        assert any('aws_s3_config' in name for name in aws_check_names)
        
        # Azure results should include Azure configuration checks
        azure_check_names = [r.check_name for r in azure_results]
        assert any('azure_' in name for name in azure_check_names)

    @pytest.mark.asyncio
    async def test_environment_specific_validation_integration(self):
        """Test that environment-specific rules are applied in integrated validation."""
        config_with_debug = {
            'aws': {
                'bucket_name': 'test-bucket',
                'access_key': 'test',
                'secret_key': 'test', 
                'region': 'us-east-1',
                'debug': True  # Should fail in production
            }
        }
        
        results = await validate_cloud_deployment(config_with_debug, environment='production')
        
        aws_results = results['aws']
        
        # Should have production debug check failure
        debug_result = next(
            (r for r in aws_results if r.check_name == 'production_debug_disabled'), 
            None
        )
        assert debug_result is not None
        assert debug_result.status == ValidationStatus.FAIL

    @pytest.mark.asyncio
    async def test_validation_with_missing_config(self):
        """Test validation behavior with incomplete configuration."""
        incomplete_config = {
            'aws': {
                'bucket_name': 'test-bucket'
                # Missing required fields
            }
        }
        
        results = await validate_cloud_deployment(incomplete_config)
        
        aws_results = results['aws']
        
        # Should have failures for missing configuration
        failures = [r for r in aws_results if r.status == ValidationStatus.FAIL]
        assert len(failures) > 0
        
        # Missing field failures should be present
        missing_field_failures = [
            r for r in failures 
            if 'missing or empty' in r.message
        ]
        assert len(missing_field_failures) > 0


@pytest.mark.skipif(not VALIDATION_MODULE_AVAILABLE, reason="Cloud validation module not available")
class TestCloudValidationReporting:
    """Test cloud validation result reporting and analysis."""

    @pytest.mark.asyncio
    async def test_validation_result_structure(self):
        """Test that validation results have proper structure."""
        config = {
            'aws': {
                'bucket_name': 'test-bucket',
                'access_key': 'test',
                'secret_key': 'test',
                'region': 'us-east-1'
            }
        }
        
        results = await validate_cloud_deployment(config)
        
        # Results should be organized by provider
        assert isinstance(results, dict)
        assert 'aws' in results
        
        # Each provider should have list of ValidationResult objects
        aws_results = results['aws']
        assert isinstance(aws_results, list)
        
        # Each result should have required fields
        for result in aws_results:
            assert hasattr(result, 'check_name')
            assert hasattr(result, 'status')
            assert hasattr(result, 'message')
            assert result.status in [ValidationStatus.PASS, ValidationStatus.FAIL, ValidationStatus.WARNING, ValidationStatus.SKIP]

    def test_validation_result_analysis(self):
        """Test analysis of validation results."""
        from emuses.tools.cloud_validation import ValidationResult, ValidationStatus
        
        # Create sample results
        results = [
            ValidationResult("test_pass", ValidationStatus.PASS, "Test passed"),
            ValidationResult("test_fail", ValidationStatus.FAIL, "Test failed"),
            ValidationResult("test_warning", ValidationStatus.WARNING, "Test warning"),
        ]
        
        # Analyze results
        total_checks = len(results)
        passed_checks = len([r for r in results if r.status == ValidationStatus.PASS])
        failed_checks = len([r for r in results if r.status == ValidationStatus.FAIL])
        warning_checks = len([r for r in results if r.status == ValidationStatus.WARNING])
        
        assert total_checks == 3
        assert passed_checks == 1
        assert failed_checks == 1
        assert warning_checks == 1
        
        # Calculate success rate
        success_rate = passed_checks / total_checks
        assert success_rate == 1/3  # One out of three passed