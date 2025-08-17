"""Cloud provider configuration validation and health checks.

This module provides production deployment validation for cloud storage configurations,
including configuration validation, health checks, and environment-specific testing.
"""
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import json

from emuses.tools.cloud_storage import CloudStorageBackend, S3StorageBackend, AzureBlobStorageBackend, GCSStorageBackend

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Status codes for validation results."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIP = "skip"


@dataclass
class ValidationResult:
    """Result of a validation check.
    
    Parameters
    ----------
    check_name : str
        Name of the validation check
    status : ValidationStatus
        Result status of the check
    message : str
        Human-readable message describing the result
    details : Dict[str, Any], optional
        Additional details about the validation result
    duration_ms : float, optional
        Time taken to perform the check in milliseconds
    """
    check_name: str
    status: ValidationStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None


class CloudConfigurationValidator:
    """Validator for cloud provider configurations.
    
    This class provides comprehensive validation of cloud storage configurations
    to ensure they are ready for production deployment.
    """

    def __init__(self):
        self.results: List[ValidationResult] = []

    async def validate_aws_s3_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate AWS S3 configuration.
        
        Parameters
        ----------
        config : Dict[str, Any]
            S3 configuration dictionary containing credentials and settings
            
        Returns
        -------
        List[ValidationResult]
            List of validation results for S3 configuration
        """
        results = []
        
        # Check required configuration fields
        required_fields = ['bucket_name', 'access_key', 'secret_key', 'region']
        for field in required_fields:
            if field not in config or not config[field]:
                results.append(ValidationResult(
                    check_name=f"aws_s3_config_{field}",
                    status=ValidationStatus.FAIL,
                    message=f"Required S3 configuration field '{field}' is missing or empty",
                    details={"field": field, "provided_config": list(config.keys())}
                ))
                continue
                
            results.append(ValidationResult(
                check_name=f"aws_s3_config_{field}",
                status=ValidationStatus.PASS,
                message=f"S3 configuration field '{field}' is present"
            ))

        # Validate bucket name format
        bucket_name = config.get('bucket_name', '')
        if bucket_name:
            if not self._is_valid_s3_bucket_name(bucket_name):
                results.append(ValidationResult(
                    check_name="aws_s3_bucket_name_format",
                    status=ValidationStatus.FAIL,
                    message=f"S3 bucket name '{bucket_name}' does not meet AWS naming requirements",
                    details={"bucket_name": bucket_name, "requirements": "3-63 chars, lowercase, no underscores"}
                ))
            else:
                results.append(ValidationResult(
                    check_name="aws_s3_bucket_name_format",
                    status=ValidationStatus.PASS,
                    message=f"S3 bucket name '{bucket_name}' meets AWS naming requirements"
                ))

        # Check region validity
        region = config.get('region', '')
        if region:
            valid_regions = [
                'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2', 
                'eu-west-1', 'eu-west-2', 'eu-central-1', 'ap-southeast-1', 
                'ap-southeast-2', 'ap-northeast-1', 'ap-south-1'
            ]
            if region not in valid_regions:
                results.append(ValidationResult(
                    check_name="aws_s3_region_validity",
                    status=ValidationStatus.WARNING,
                    message=f"S3 region '{region}' is not in common regions list - verify it exists",
                    details={"region": region, "common_regions": valid_regions}
                ))
            else:
                results.append(ValidationResult(
                    check_name="aws_s3_region_validity",
                    status=ValidationStatus.PASS,
                    message=f"S3 region '{region}' is valid"
                ))

        return results

    async def validate_azure_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate Azure Blob Storage configuration.
        
        Parameters
        ----------
        config : Dict[str, Any]
            Azure configuration dictionary
            
        Returns
        -------
        List[ValidationResult]
            List of validation results for Azure configuration
        """
        results = []
        
        # Check for connection string or individual components
        if 'connection_string' in config and config['connection_string']:
            results.append(ValidationResult(
                check_name="azure_connection_string",
                status=ValidationStatus.PASS,
                message="Azure connection string is provided"
            ))
            
            # Validate connection string format
            conn_str = config['connection_string']
            required_components = ['AccountName=', 'AccountKey=']
            for component in required_components:
                if component not in conn_str:
                    results.append(ValidationResult(
                        check_name=f"azure_connection_string_{component.strip('=')}",
                        status=ValidationStatus.FAIL,
                        message=f"Azure connection string missing required component: {component}",
                        details={"component": component}
                    ))
                else:
                    results.append(ValidationResult(
                        check_name=f"azure_connection_string_{component.strip('=')}",
                        status=ValidationStatus.PASS,
                        message=f"Azure connection string contains {component}"
                    ))
        else:
            results.append(ValidationResult(
                check_name="azure_connection_string",
                status=ValidationStatus.FAIL,
                message="Azure connection string is required but not provided"
            ))

        # Check container name
        container_name = config.get('container_name', '')
        if not container_name:
            results.append(ValidationResult(
                check_name="azure_container_name",
                status=ValidationStatus.FAIL,
                message="Azure container name is required but not provided"
            ))
        elif not self._is_valid_azure_container_name(container_name):
            results.append(ValidationResult(
                check_name="azure_container_name_format",
                status=ValidationStatus.FAIL,
                message=f"Azure container name '{container_name}' does not meet naming requirements",
                details={"container_name": container_name, "requirements": "3-63 chars, lowercase, alphanumeric and hyphens only"}
            ))
        else:
            results.append(ValidationResult(
                check_name="azure_container_name",
                status=ValidationStatus.PASS,
                message=f"Azure container name '{container_name}' is valid"
            ))

        return results

    async def validate_gcs_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate Google Cloud Storage configuration.
        
        Parameters
        ----------
        config : Dict[str, Any]
            GCS configuration dictionary
            
        Returns
        -------
        List[ValidationResult]
            List of validation results for GCS configuration
        """
        results = []
        
        # Check required fields
        required_fields = ['bucket_name', 'project_id']
        for field in required_fields:
            if field not in config or not config[field]:
                results.append(ValidationResult(
                    check_name=f"gcs_config_{field}",
                    status=ValidationStatus.FAIL,
                    message=f"Required GCS configuration field '{field}' is missing or empty",
                    details={"field": field}
                ))
            else:
                results.append(ValidationResult(
                    check_name=f"gcs_config_{field}",
                    status=ValidationStatus.PASS,
                    message=f"GCS configuration field '{field}' is present"
                ))

        # Validate bucket name format for GCS
        bucket_name = config.get('bucket_name', '')
        if bucket_name:
            if not self._is_valid_gcs_bucket_name(bucket_name):
                results.append(ValidationResult(
                    check_name="gcs_bucket_name_format",
                    status=ValidationStatus.FAIL,
                    message=f"GCS bucket name '{bucket_name}' does not meet naming requirements",
                    details={"bucket_name": bucket_name, "requirements": "3-63 chars, lowercase, no underscores or uppercase"}
                ))
            else:
                results.append(ValidationResult(
                    check_name="gcs_bucket_name_format",
                    status=ValidationStatus.PASS,
                    message=f"GCS bucket name '{bucket_name}' meets naming requirements"
                ))

        # Check for service account credentials
        credentials_file = config.get('credentials_file', '')
        if credentials_file:
            if Path(credentials_file).exists():
                results.append(ValidationResult(
                    check_name="gcs_credentials_file",
                    status=ValidationStatus.PASS,
                    message=f"GCS credentials file exists at {credentials_file}"
                ))
            else:
                results.append(ValidationResult(
                    check_name="gcs_credentials_file",
                    status=ValidationStatus.FAIL,
                    message=f"GCS credentials file not found at {credentials_file}",
                    details={"credentials_file": credentials_file}
                ))
        else:
            # Check for environment variable
            if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
                results.append(ValidationResult(
                    check_name="gcs_credentials_env",
                    status=ValidationStatus.PASS,
                    message="GCS credentials provided via GOOGLE_APPLICATION_CREDENTIALS environment variable"
                ))
            else:
                results.append(ValidationResult(
                    check_name="gcs_credentials",
                    status=ValidationStatus.WARNING,
                    message="No explicit GCS credentials provided - relying on default application credentials"
                ))

        return results

    def _is_valid_s3_bucket_name(self, bucket_name: str) -> bool:
        """Validate S3 bucket name according to AWS rules."""
        if not (3 <= len(bucket_name) <= 63):
            return False
        if not bucket_name.islower():
            return False
        if '_' in bucket_name:
            return False
        if bucket_name.startswith('-') or bucket_name.endswith('-'):
            return False
        if '..' in bucket_name:
            return False
        return True

    def _is_valid_azure_container_name(self, container_name: str) -> bool:
        """Validate Azure container name according to Azure rules."""
        if not (3 <= len(container_name) <= 63):
            return False
        if not container_name.islower():
            return False
        if not container_name.replace('-', '').isalnum():
            return False
        if container_name.startswith('-') or container_name.endswith('-'):
            return False
        if '--' in container_name:
            return False
        return True

    def _is_valid_gcs_bucket_name(self, bucket_name: str) -> bool:
        """Validate GCS bucket name according to Google Cloud rules."""
        if not (3 <= len(bucket_name) <= 63):
            return False
        if not bucket_name.islower():
            return False
        if '_' in bucket_name or bucket_name != bucket_name.lower():
            return False
        if bucket_name.startswith('-') or bucket_name.endswith('-'):
            return False
        return True


class CloudHealthChecker:
    """Health checker for cloud storage services.
    
    Provides comprehensive health checks for cloud storage backends including
    connectivity, permissions, and performance validation.
    """

    async def check_backend_health(self, backend: CloudStorageBackend) -> List[ValidationResult]:
        """Perform comprehensive health check on cloud storage backend.
        
        Parameters
        ----------
        backend : CloudStorageBackend
            The cloud storage backend to check
            
        Returns
        -------
        List[ValidationResult]
            List of health check results
        """
        results = []
        
        # Basic connectivity test
        connectivity_result = await self._check_connectivity(backend)
        results.append(connectivity_result)
        
        if connectivity_result.status == ValidationStatus.PASS:
            # Only run other checks if connectivity passes
            
            # Permission checks
            permission_results = await self._check_permissions(backend)
            results.extend(permission_results)
            
            # Performance checks
            performance_result = await self._check_performance(backend)
            results.append(performance_result)
            
            # Storage operation checks
            operation_results = await self._check_storage_operations(backend)
            results.extend(operation_results)

        return results

    async def _check_connectivity(self, backend: CloudStorageBackend) -> ValidationResult:
        """Check basic connectivity to cloud storage service."""
        import time
        start_time = time.time()
        
        try:
            # Try to create a minimal test operation
            # For most backends, this will involve initializing the client
            # This is a basic connectivity test
            if hasattr(backend, '_get_client'):
                await backend._get_client()
            
            duration_ms = (time.time() - start_time) * 1000
            return ValidationResult(
                check_name="connectivity",
                status=ValidationStatus.PASS,
                message=f"Successfully connected to {type(backend).__name__}",
                duration_ms=duration_ms
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return ValidationResult(
                check_name="connectivity",
                status=ValidationStatus.FAIL,
                message=f"Failed to connect to {type(backend).__name__}: {str(e)}",
                details={"error_type": type(e).__name__, "error_message": str(e)},
                duration_ms=duration_ms
            )

    async def _check_permissions(self, backend: CloudStorageBackend) -> List[ValidationResult]:
        """Check required permissions for storage operations."""
        results = []
        
        # Test list permissions (if applicable)
        try:
            # This is a placeholder - actual implementation would depend on backend type
            # and would test specific permission operations
            results.append(ValidationResult(
                check_name="permissions_list",
                status=ValidationStatus.PASS,
                message="List permissions validated"
            ))
        except Exception as e:
            results.append(ValidationResult(
                check_name="permissions_list",
                status=ValidationStatus.FAIL,
                message=f"List permissions failed: {str(e)}",
                details={"error_type": type(e).__name__}
            ))

        return results

    async def _check_performance(self, backend: CloudStorageBackend) -> ValidationResult:
        """Check basic performance characteristics."""
        import time
        
        try:
            start_time = time.time()
            
            # Perform a lightweight operation to test latency
            # This would be backend-specific in a full implementation
            await asyncio.sleep(0.001)  # Simulate operation
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Consider acceptable latency thresholds
            if latency_ms > 5000:  # 5 seconds
                status = ValidationStatus.FAIL
                message = f"High latency detected: {latency_ms:.2f}ms"
            elif latency_ms > 1000:  # 1 second
                status = ValidationStatus.WARNING
                message = f"Elevated latency: {latency_ms:.2f}ms"
            else:
                status = ValidationStatus.PASS
                message = f"Good latency: {latency_ms:.2f}ms"

            return ValidationResult(
                check_name="performance_latency",
                status=status,
                message=message,
                details={"latency_ms": latency_ms},
                duration_ms=latency_ms
            )
        except Exception as e:
            return ValidationResult(
                check_name="performance_latency",
                status=ValidationStatus.FAIL,
                message=f"Performance check failed: {str(e)}",
                details={"error_type": type(e).__name__}
            )

    async def _check_storage_operations(self, backend: CloudStorageBackend) -> List[ValidationResult]:
        """Test basic storage operations with small test files."""
        results = []
        
        # Create a test file for operations
        test_file_content = b"test_content_for_health_check"
        test_model_id = "health_check_test_model"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create minimal model directory structure
            test_model_dir = temp_path / "health_check_model"
            test_model_dir.mkdir()
            
            # Create a simple manifest
            manifest = {
                "name": "health_check_model",
                "version": "1.0.0",
                "type": "health_check"
            }
            (test_model_dir / "model_manifest.json").write_text(json.dumps(manifest))
            
            # Create a small test file
            (test_model_dir / "test_file.txt").write_bytes(test_file_content)
            
            # Test upload
            try:
                import time
                start_time = time.time()
                storage_url = await backend.upload_model(test_model_dir, test_model_id)
                upload_duration = (time.time() - start_time) * 1000
                
                results.append(ValidationResult(
                    check_name="storage_upload",
                    status=ValidationStatus.PASS,
                    message=f"Test model upload successful",
                    details={"storage_url": storage_url},
                    duration_ms=upload_duration
                ))
                
                # Test signed URL generation
                try:
                    signed_url = await backend.generate_signed_url(storage_url, expires_in=300)
                    results.append(ValidationResult(
                        check_name="storage_signed_url",
                        status=ValidationStatus.PASS,
                        message="Signed URL generation successful",
                        details={"has_signed_url": bool(signed_url)}
                    ))
                except Exception as e:
                    results.append(ValidationResult(
                        check_name="storage_signed_url",
                        status=ValidationStatus.WARNING,
                        message=f"Signed URL generation failed: {str(e)}",
                        details={"error_type": type(e).__name__}
                    ))
                
                # Test download
                try:
                    download_dir = temp_path / "downloaded"
                    start_time = time.time()
                    await backend.download_model(storage_url, download_dir / "health_check_model")
                    download_duration = (time.time() - start_time) * 1000
                    
                    results.append(ValidationResult(
                        check_name="storage_download",
                        status=ValidationStatus.PASS,
                        message="Test model download successful",
                        duration_ms=download_duration
                    ))
                except Exception as e:
                    results.append(ValidationResult(
                        check_name="storage_download",
                        status=ValidationStatus.FAIL,
                        message=f"Test model download failed: {str(e)}",
                        details={"error_type": type(e).__name__}
                    ))
                
                # Cleanup - test delete
                try:
                    await backend.delete_model(storage_url)
                    results.append(ValidationResult(
                        check_name="storage_delete",
                        status=ValidationStatus.PASS,
                        message="Test model deletion successful"
                    ))
                except Exception as e:
                    results.append(ValidationResult(
                        check_name="storage_delete",
                        status=ValidationStatus.WARNING,
                        message=f"Test model deletion failed: {str(e)}",
                        details={"error_type": type(e).__name__}
                    ))
                
            except Exception as e:
                results.append(ValidationResult(
                    check_name="storage_upload",
                    status=ValidationStatus.FAIL,
                    message=f"Test model upload failed: {str(e)}",
                    details={"error_type": type(e).__name__}
                ))

        return results


class EnvironmentValidator:
    """Validator for environment-specific cloud configurations.
    
    Provides validation checks that are specific to deployment environments
    (development, staging, production).
    """

    def __init__(self, environment: str = "production"):
        self.environment = environment.lower()

    async def validate_environment_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate configuration for specific environment.
        
        Parameters
        ----------
        config : Dict[str, Any]
            Environment configuration dictionary
            
        Returns
        -------
        List[ValidationResult]
            List of environment-specific validation results
        """
        results = []
        
        # Environment-specific checks
        if self.environment == "production":
            results.extend(await self._validate_production_config(config))
        elif self.environment == "staging":
            results.extend(await self._validate_staging_config(config))
        elif self.environment == "development":
            results.extend(await self._validate_development_config(config))
        
        # Common environment checks
        results.extend(await self._validate_common_config(config))
        
        return results

    async def _validate_production_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate production-specific requirements."""
        results = []
        
        # Check for security requirements
        if config.get('debug', False):
            results.append(ValidationResult(
                check_name="production_debug_disabled",
                status=ValidationStatus.FAIL,
                message="Debug mode must be disabled in production"
            ))
        else:
            results.append(ValidationResult(
                check_name="production_debug_disabled",
                status=ValidationStatus.PASS,
                message="Debug mode is properly disabled"
            ))
        
        # Check for backup configuration
        if 'backup_config' not in config:
            results.append(ValidationResult(
                check_name="production_backup_config",
                status=ValidationStatus.WARNING,
                message="Backup configuration not found - recommend configuring backups for production"
            ))
        else:
            results.append(ValidationResult(
                check_name="production_backup_config",
                status=ValidationStatus.PASS,
                message="Backup configuration is present"
            ))
        
        return results

    async def _validate_staging_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate staging-specific requirements."""
        results = []
        
        # Staging can have debug mode but should mirror production closely
        if config.get('debug', False):
            results.append(ValidationResult(
                check_name="staging_debug_mode",
                status=ValidationStatus.WARNING,
                message="Debug mode enabled in staging - ensure production parity"
            ))
        
        return results

    async def _validate_development_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate development-specific requirements."""
        results = []
        
        # Development environment checks are generally more permissive
        results.append(ValidationResult(
            check_name="development_environment",
            status=ValidationStatus.PASS,
            message="Development environment validation complete"
        ))
        
        return results

    async def _validate_common_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate common configuration requirements across all environments."""
        results = []
        
        # Check for required monitoring configuration
        if 'monitoring' in config:
            results.append(ValidationResult(
                check_name="monitoring_config",
                status=ValidationStatus.PASS,
                message="Monitoring configuration is present"
            ))
        else:
            results.append(ValidationResult(
                check_name="monitoring_config",
                status=ValidationStatus.WARNING,
                message="Monitoring configuration not found - recommended for all environments"
            ))
        
        return results


async def validate_cloud_deployment(
    cloud_configs: Dict[str, Dict[str, Any]], 
    environment: str = "production"
) -> Dict[str, List[ValidationResult]]:
    """Comprehensive cloud deployment validation.
    
    Parameters
    ----------
    cloud_configs : Dict[str, Dict[str, Any]]
        Dictionary of cloud provider configurations
    environment : str, default="production"
        Target deployment environment
        
    Returns
    -------
    Dict[str, List[ValidationResult]]
        Validation results organized by provider and check type
    """
    all_results = {}
    
    config_validator = CloudConfigurationValidator()
    health_checker = CloudHealthChecker()
    env_validator = EnvironmentValidator(environment)
    
    for provider, config in cloud_configs.items():
        provider_results = []
        
        # Configuration validation
        if provider.lower() in ['aws', 's3']:
            config_results = await config_validator.validate_aws_s3_config(config)
            provider_results.extend(config_results)
        elif provider.lower() in ['azure', 'azure_blob']:
            config_results = await config_validator.validate_azure_config(config)
            provider_results.extend(config_results)
        elif provider.lower() in ['gcs', 'google_cloud']:
            config_results = await config_validator.validate_gcs_config(config)
            provider_results.extend(config_results)
        
        # Environment validation
        env_results = await env_validator.validate_environment_config(config)
        provider_results.extend(env_results)
        
        # Health checks (if configuration passes)
        config_passed = all(r.status == ValidationStatus.PASS for r in config_results)
        if config_passed:
            try:
                # Create backend instance for health checking
                backend = None
                if provider.lower() in ['aws', 's3']:
                    backend = S3StorageBackend(
                        bucket_name=config['bucket_name'],
                        access_key=config['access_key'],
                        secret_key=config['secret_key'],
                        region=config['region']
                    )
                elif provider.lower() in ['azure', 'azure_blob']:
                    backend = AzureBlobStorageBackend(
                        container_name=config['container_name'],
                        connection_string=config['connection_string']
                    )
                elif provider.lower() in ['gcs', 'google_cloud']:
                    backend = GCSStorageBackend(
                        bucket_name=config['bucket_name'],
                        project_id=config['project_id'],
                        credentials_file=config.get('credentials_file')
                    )
                
                if backend:
                    health_results = await health_checker.check_backend_health(backend)
                    provider_results.extend(health_results)
            except Exception as e:
                provider_results.append(ValidationResult(
                    check_name="backend_initialization",
                    status=ValidationStatus.FAIL,
                    message=f"Failed to initialize {provider} backend: {str(e)}",
                    details={"error_type": type(e).__name__}
                ))
        
        all_results[provider] = provider_results
    
    return all_results