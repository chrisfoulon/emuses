"""CLI commands for cloud storage validation and health checks.

This module provides command-line interface for validating cloud storage
configurations and performing health checks on cloud storage backends.
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import click

from emuses.extras.cloud_validation import (
    validate_cloud_deployment,
    CloudConfigurationValidator,
    CloudHealthChecker,
    EnvironmentValidator,
    ValidationStatus
)


@click.group()
def cloud():
    """Cloud storage validation and health check commands."""
    pass


@cloud.command()
@click.option(
    '--config-file', '-c',
    type=click.Path(exists=True),
    required=True,
    help='Path to cloud configuration JSON file'
)
@click.option(
    '--environment', '-e',
    type=click.Choice(['development', 'staging', 'production']),
    default='production',
    help='Target deployment environment'
)
@click.option(
    '--provider', '-p',
    type=click.Choice(['aws', 's3', 'azure', 'azure_blob', 'gcs', 'google_cloud', 'all']),
    default='all',
    help='Specific cloud provider to validate'
)
@click.option(
    '--output-format', '-f',
    type=click.Choice(['text', 'json']),
    default='text',
    help='Output format for validation results'
)
@click.option(
    '--fail-on-warning',
    is_flag=True,
    help='Exit with error code if any warnings are found'
)
def validate(config_file: str, environment: str, provider: str, output_format: str, fail_on_warning: bool):
    """Validate cloud storage configuration for deployment.
    
    Performs comprehensive validation of cloud storage configurations including:
    - Configuration field validation
    - Naming convention compliance
    - Environment-specific requirements
    - Health checks and connectivity tests
    
    Examples:
        # Validate all providers for production
        emuses cloud validate -c config/cloud.json -e production
        
        # Validate only AWS S3 configuration
        emuses cloud validate -c config/cloud.json -p aws
        
        # Output results as JSON
        emuses cloud validate -c config/cloud.json -f json
    """
    try:
        # Load configuration file
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Filter configuration by provider if specified
        if provider != 'all':
            if provider in config:
                config = {provider: config[provider]}
            else:
                click.echo(f"Error: Provider '{provider}' not found in configuration file", err=True)
                sys.exit(1)
        
        # Run validation
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(
            validate_cloud_deployment(config, environment)
        )
        
        # Process and display results
        if output_format == 'json':
            _output_json_results(results)
        else:
            _output_text_results(results, environment)
        
        # Determine exit code
        exit_code = _calculate_exit_code(results, fail_on_warning)
        sys.exit(exit_code)
        
    except FileNotFoundError:
        click.echo(f"Error: Configuration file '{config_file}' not found", err=True)
        sys.exit(1)
    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON in configuration file: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: Validation failed: {e}", err=True)
        sys.exit(1)


@cloud.command()
@click.option(
    '--provider', '-p',
    type=click.Choice(['aws', 's3', 'azure', 'azure_blob', 'gcs', 'google_cloud']),
    required=True,
    help='Cloud provider to test'
)
@click.option(
    '--bucket-name', '-b',
    required=True,
    help='Bucket or container name for testing'
)
@click.option(
    '--region', '-r',
    help='AWS region or Azure location (required for AWS)'
)
@click.option(
    '--access-key', '-k',
    help='Access key or account name'
)
@click.option(
    '--secret-key', '-s',
    help='Secret key or account key'
)
@click.option(
    '--connection-string',
    help='Azure Blob Storage connection string (alternative to access/secret keys)'
)
@click.option(
    '--project-id',
    help='Google Cloud project ID (required for GCS)'
)
@click.option(
    '--credentials-file',
    type=click.Path(exists=True),
    help='Path to GCS service account credentials file'
)
@click.option(
    '--timeout', '-t',
    type=int,
    default=60,
    help='Timeout for health check operations in seconds'
)
def health_check(
    provider: str, 
    bucket_name: str,
    region: Optional[str],
    access_key: Optional[str],
    secret_key: Optional[str],
    connection_string: Optional[str],
    project_id: Optional[str],
    credentials_file: Optional[str],
    timeout: int
):
    """Perform health check on cloud storage backend.
    
    Tests connectivity, permissions, and basic operations on the specified
    cloud storage backend.
    
    Examples:
        # Test AWS S3 health
        emuses cloud health-check -p aws -b my-bucket -r us-west-2 -k ACCESS_KEY -s SECRET_KEY
        
        # Test Azure Blob Storage health
        emuses cloud health-check -p azure -b my-container --connection-string "DefaultEndpointsProtocol=..."
        
        # Test Google Cloud Storage health
        emuses cloud health-check -p gcs -b my-bucket --project-id my-project --credentials-file /path/to/creds.json
    """
    try:
        # Create backend instance based on provider
        backend = _create_backend_from_params(
            provider, bucket_name, region, access_key, secret_key,
            connection_string, project_id, credentials_file
        )
        
        # Perform health check
        click.echo(f"Performing health check for {provider} backend...")
        
        health_checker = CloudHealthChecker()
        
        # Run health check with timeout
        loop = asyncio.get_event_loop()
        try:
            results = loop.run_until_complete(
                asyncio.wait_for(
                    health_checker.check_backend_health(backend),
                    timeout=timeout
                )
            )
        except asyncio.TimeoutError:
            click.echo(f"Error: Health check timed out after {timeout} seconds", err=True)
            sys.exit(1)
        
        # Display results
        _display_health_check_results(results, provider)
        
        # Calculate exit code
        failed_checks = [r for r in results if r.status == ValidationStatus.FAIL]
        if failed_checks:
            click.echo(f"\n❌ Health check failed: {len(failed_checks)} checks failed")
            sys.exit(1)
        else:
            click.echo("\n✅ Health check passed: All checks successful")
            
    except Exception as e:
        click.echo(f"Error: Health check failed: {e}", err=True)
        sys.exit(1)


@cloud.command()
@click.argument('bucket_name')
@click.option(
    '--provider', '-p',
    type=click.Choice(['aws', 's3', 'azure', 'azure_blob', 'gcs', 'google_cloud']),
    default='aws',
    help='Cloud provider to validate bucket name for'
)
def validate_name(bucket_name: str, provider: str):
    """Validate bucket or container name according to provider rules.
    
    Checks if the provided name meets the naming requirements for the
    specified cloud provider.
    
    Examples:
        # Validate S3 bucket name
        emuses cloud validate-name my-bucket-name -p aws
        
        # Validate Azure container name
        emuses cloud validate-name my-container-name -p azure
        
        # Validate GCS bucket name
        emuses cloud validate-name my-bucket-name -p gcs
    """
    validator = CloudConfigurationValidator()
    
    if provider.lower() in ['aws', 's3']:
        is_valid = validator._is_valid_s3_bucket_name(bucket_name)
        rules = "3-63 characters, lowercase, no underscores, no consecutive periods"
    elif provider.lower() in ['azure', 'azure_blob']:
        is_valid = validator._is_valid_azure_container_name(bucket_name)
        rules = "3-63 characters, lowercase, alphanumeric and hyphens only, no consecutive hyphens"
    elif provider.lower() in ['gcs', 'google_cloud']:
        is_valid = validator._is_valid_gcs_bucket_name(bucket_name)
        rules = "3-63 characters, lowercase, no underscores or uppercase letters"
    else:
        click.echo(f"Error: Unknown provider '{provider}'", err=True)
        sys.exit(1)
    
    if is_valid:
        click.echo(f"✅ '{bucket_name}' is a valid {provider.upper()} name")
    else:
        click.echo(f"❌ '{bucket_name}' is not a valid {provider.upper()} name")
        click.echo(f"Rules: {rules}")
        sys.exit(1)


def _create_backend_from_params(
    provider: str, bucket_name: str, region: Optional[str],
    access_key: Optional[str], secret_key: Optional[str],
    connection_string: Optional[str], project_id: Optional[str],
    credentials_file: Optional[str]
):
    """Create cloud storage backend from command line parameters."""
    if provider.lower() in ['aws', 's3']:
        from emuses.extras.cloud_storage import S3StorageBackend
        
        if not all([access_key, secret_key, region]):
            raise click.ClickException("AWS S3 requires --access-key, --secret-key, and --region")
        
        return S3StorageBackend(
            bucket_name=bucket_name,
            access_key=access_key,
            secret_key=secret_key,
            region=region
        )
        
    elif provider.lower() in ['azure', 'azure_blob']:
        from emuses.extras.cloud_storage import AzureBlobStorageBackend
        
        if not connection_string:
            raise click.ClickException("Azure Blob Storage requires --connection-string")
        
        return AzureBlobStorageBackend(
            container_name=bucket_name,
            connection_string=connection_string
        )
        
    elif provider.lower() in ['gcs', 'google_cloud']:
        from emuses.extras.cloud_storage import GCSStorageBackend
        
        if not project_id:
            raise click.ClickException("Google Cloud Storage requires --project-id")
        
        return GCSStorageBackend(
            bucket_name=bucket_name,
            project_id=project_id,
            credentials_file=credentials_file
        )
    else:
        raise click.ClickException(f"Unknown provider: {provider}")


def _output_json_results(results: Dict[str, Any]):
    """Output validation results in JSON format."""
    json_results = {}
    
    for provider, provider_results in results.items():
        json_results[provider] = []
        for result in provider_results:
            json_results[provider].append({
                'check_name': result.check_name,
                'status': result.status.value,
                'message': result.message,
                'details': result.details,
                'duration_ms': result.duration_ms
            })
    
    click.echo(json.dumps(json_results, indent=2))


def _output_text_results(results: Dict[str, Any], environment: str):
    """Output validation results in text format."""
    click.echo(f"\n🔍 Cloud Storage Validation Report")
    click.echo(f"Environment: {environment.upper()}")
    click.echo(f"Timestamp: {click.DateTime().convert(None, None, None)}")
    click.echo("=" * 60)
    
    total_checks = 0
    total_passed = 0
    total_failed = 0
    total_warnings = 0
    
    for provider, provider_results in results.items():
        click.echo(f"\n📁 {provider.upper()} Provider")
        click.echo("-" * 40)
        
        passed = failed = warnings = 0
        
        for result in provider_results:
            total_checks += 1
            
            if result.status == ValidationStatus.PASS:
                icon = "✅"
                passed += 1
                total_passed += 1
            elif result.status == ValidationStatus.FAIL:
                icon = "❌"
                failed += 1
                total_failed += 1
            elif result.status == ValidationStatus.WARNING:
                icon = "⚠️ "
                warnings += 1
                total_warnings += 1
            else:  # SKIP
                icon = "⏭️ "
            
            duration_info = f" ({result.duration_ms:.1f}ms)" if result.duration_ms else ""
            click.echo(f"  {icon} {result.check_name}: {result.message}{duration_info}")
            
            if result.details:
                click.echo(f"     Details: {result.details}")
        
        # Provider summary
        click.echo(f"\n  Summary: {passed} passed, {failed} failed, {warnings} warnings")
    
    # Overall summary
    click.echo("\n" + "=" * 60)
    click.echo(f"📊 Overall Summary")
    click.echo(f"Total Checks: {total_checks}")
    click.echo(f"✅ Passed: {total_passed}")
    click.echo(f"❌ Failed: {total_failed}")
    click.echo(f"⚠️  Warnings: {total_warnings}")
    
    if total_failed == 0 and total_warnings == 0:
        click.echo("\n🎉 All validation checks passed!")
    elif total_failed == 0:
        click.echo("\n⚠️  Validation completed with warnings")
    else:
        click.echo("\n💥 Validation failed - please address the failed checks")


def _calculate_exit_code(results: Dict[str, Any], fail_on_warning: bool = False) -> int:
    """Calculate appropriate exit code based on validation results."""
    has_failures = False
    has_warnings = False
    
    for provider_results in results.values():
        for result in provider_results:
            if result.status == ValidationStatus.FAIL:
                has_failures = True
            elif result.status == ValidationStatus.WARNING:
                has_warnings = True
    
    if has_failures:
        return 1
    elif has_warnings and fail_on_warning:
        return 1
    else:
        return 0


def _display_health_check_results(results, provider: str):
    """Display health check results in formatted output."""
    click.echo(f"\n🏥 Health Check Results for {provider.upper()}")
    click.echo("=" * 50)
    
    for result in results:
        if result.status == ValidationStatus.PASS:
            icon = "✅"
        elif result.status == ValidationStatus.FAIL:
            icon = "❌"
        elif result.status == ValidationStatus.WARNING:
            icon = "⚠️ "
        else:
            icon = "⏭️ "
        
        duration_info = f" ({result.duration_ms:.1f}ms)" if result.duration_ms else ""
        click.echo(f"  {icon} {result.check_name}: {result.message}{duration_info}")
        
        if result.details:
            for key, value in result.details.items():
                click.echo(f"     {key}: {value}")


if __name__ == '__main__':
    cloud()