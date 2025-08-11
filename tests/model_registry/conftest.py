"""Unified test fixtures for cloud storage integration testing.

This module provides consolidated pytest fixtures for cloud storage emulators
and testing infrastructure. Supports AWS S3 (moto), Azure Blob (Azurite),
and Google Cloud Storage (fake-gcs-server) emulation.
"""
import pytest
import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import json
from unittest.mock import MagicMock
from uuid import uuid4
from sqlalchemy.orm import Session
from emuses.multi_user_service.models import User


# Test markers for different testing modes
pytest_markers = {
    "unit": "Unit tests with mocking",
    "integration": "Integration tests with emulators", 
    "e2e": "End-to-end tests with full workflows",
    "slow": "Tests that take longer than 10 seconds"
}


@pytest.fixture
def cloud_test_model_dir():
    """Create a standardized temporary model directory for cloud testing.
    
    Returns
    -------
    Path
        Path to temporary model directory with standard structure
    """
    temp_dir = Path(tempfile.mkdtemp())
    
    # Create model structure
    model_dir = temp_dir / "cloud-test-model"
    model_dir.mkdir()
    
    # Create standard directories
    (model_dir / "models").mkdir()
    (model_dir / "artifacts").mkdir() 
    (model_dir / "metadata").mkdir()
    
    # Create manifest file
    manifest = {
        "name": "cloud-test-model",
        "version": "1.0.0", 
        "created_at": "2025-01-01T00:00:00Z",
        "description": "Test model for cloud storage integration",
        "framework": "test",
        "metrics": {
            "accuracy": 0.95,
            "f1_score": 0.93
        }
    }
    (model_dir / "model_manifest.json").write_text(json.dumps(manifest, indent=2))
    
    # Create test model files
    (model_dir / "models" / "model.pkl").write_bytes(b"dummy model data for cloud testing")
    (model_dir / "artifacts" / "metrics.json").write_text('{"accuracy": 0.95, "loss": 0.05}')
    (model_dir / "artifacts" / "config.yaml").write_text("model_type: test\nversion: 1.0")
    (model_dir / "metadata" / "training_log.txt").write_text("Training completed successfully")
    
    yield model_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def aws_test_credentials():
    """Set up dummy AWS credentials for testing to prevent accidental real API calls.
    
    Returns
    -------
    Dict[str, str]
        Dictionary of AWS credential environment variables
    """
    # Store original values
    original_vars = {}
    test_vars = {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1"
    }
    
    # Set test credentials
    for var, value in test_vars.items():
        original_vars[var] = os.environ.get(var)
        os.environ[var] = value
    
    yield test_vars
    
    # Restore original values
    for var, original_value in original_vars.items():
        if original_value is not None:
            os.environ[var] = original_value
        else:
            os.environ.pop(var, None)


@pytest.fixture
def cloud_emulator_config():
    """Provide configuration for cloud emulator testing.
    
    Returns
    -------
    Dict[str, Any]
        Configuration dictionary for cloud emulators
    """
    return {
        "aws": {
            "provider": "s3",
            "bucket_name": "test-model-registry-bucket",
            "region": "us-east-1",
            "emulator": "moto"
        },
        "azure": {
            "provider": "azure",
            "container_name": "test-model-registry-container", 
            "emulator": "azurite",
            "connection_string_template": "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://{host}:{port}/devstoreaccount1;"
        },
        "gcs": {
            "provider": "gcs",
            "bucket_name": "test-model-registry-bucket",
            "project_id": "test-project",
            "emulator": "fake-gcs-server",
            "port": 4443
        }
    }


def docker_available() -> bool:
    """Check if Docker is available for container-based testing.
    
    Returns
    -------
    bool
        True if Docker is available and responsive
    """
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def cloud_emulator_available(provider: str) -> bool:
    """Check if a specific cloud emulator is available.
    
    Parameters
    ----------
    provider : str
        Cloud provider name ('aws', 'azure', 'gcs')
        
    Returns
    -------
    bool
        True if emulator dependencies are available
    """
    if provider == "aws":
        try:
            from moto import mock_aws
            import boto3
            return True
        except ImportError:
            return False
    elif provider == "azure":
        try:
            from testcontainers.azurite import AzuriteContainer
            from azure.storage.blob import BlobServiceClient
            return docker_available()
        except ImportError:
            return False
    elif provider == "gcs":
        try:
            from testcontainers.generic import GenericContainer
            from google.cloud import storage
            return docker_available()
        except ImportError:
            return False
    return False


@pytest.fixture(scope="session")
def cloud_test_environment():
    """Provide information about available cloud testing environment.
    
    Returns
    -------
    Dict[str, bool]
        Dictionary indicating which cloud emulators are available
    """
    return {
        "docker": docker_available(),
        "aws_moto": cloud_emulator_available("aws"),
        "azure_azurite": cloud_emulator_available("azure"), 
        "gcs_fake_server": cloud_emulator_available("gcs")
    }


@pytest.fixture
def skip_if_no_docker():
    """Skip test if Docker is not available."""
    if not docker_available():
        pytest.skip("Docker not available for container-based testing")


@pytest.fixture
def skip_if_no_aws_emulator():
    """Skip test if AWS emulator (moto) is not available."""
    if not cloud_emulator_available("aws"):
        pytest.skip("AWS emulator (moto) not available")


@pytest.fixture
def skip_if_no_azure_emulator():
    """Skip test if Azure emulator (Azurite) is not available."""
    if not cloud_emulator_available("azure"):
        pytest.skip("Azure emulator (Azurite) not available")


@pytest.fixture
def skip_if_no_gcs_emulator():
    """Skip test if GCS emulator (fake-gcs-server) is not available."""
    if not cloud_emulator_available("gcs"):
        pytest.skip("GCS emulator (fake-gcs-server) not available")


# Test parametrization helpers
def cloud_provider_params():
    """Generate parametrization for available cloud providers.
    
    Returns
    -------
    List[str]
        List of available cloud provider names for parametrized tests
    """
    available_providers = []
    if cloud_emulator_available("aws"):
        available_providers.append("aws")
    if cloud_emulator_available("azure"):
        available_providers.append("azure")  
    if cloud_emulator_available("gcs"):
        available_providers.append("gcs")
    return available_providers


# Custom pytest markers for cloud testing
def pytest_configure(config):
    """Register custom pytest markers for cloud testing."""
    for marker, description in pytest_markers.items():
        config.addinivalue_line("markers", f"{marker}: {description}")


# Missing fixtures for cloud registry integration tests
@pytest.fixture
def mock_db_session():
    """Mock database session for integration tests."""
    session = MagicMock(spec=Session)
    
    # Create a mock query object that handles the full chain
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.first.return_value = None
    mock_query.all.return_value = []
    
    # Make sure nested attribute access also returns the chainable mock
    mock_query.filter.return_value.limit.return_value = mock_query
    mock_query.filter.return_value.offset.return_value = mock_query
    mock_query.filter.return_value.all.return_value = []
    
    session.query.return_value = mock_query
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.delete = MagicMock()
    return session


@pytest.fixture
def mock_user():
    """Mock user for integration tests."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.username = "test-user"
    user.email = "test@example.com"
    user.is_active = True
    user.is_superuser = True  # Make test user admin for simpler testing
    user.is_verified = True
    return user


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory for testing."""
    temp_dir = Path(tempfile.mkdtemp(prefix="emuses_test_cache_"))
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)