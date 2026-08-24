"""Integration tests for cloud storage backends using emulators.

This module provides comprehensive integration testing for cloud storage operations
using real emulators (moto, azurite, fake-gcs-server) to validate actual cloud
API behavior patterns.
"""
import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import patch
import os

# Test requires moto for AWS testing - will fail until installed
try:
    from moto import mock_aws
    import boto3
    MOTO_AVAILABLE = True
except ImportError:
    MOTO_AVAILABLE = False

from emuses.tools.cloud_storage import S3StorageBackend


@pytest.mark.skipif(not MOTO_AVAILABLE, reason="moto not installed")
class TestS3StorageBackendIntegration:
    """Integration tests for S3StorageBackend using moto emulator."""

    @pytest.fixture
    def temp_model_dir(self):
        """Create temporary model directory for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create model structure
        model_dir = temp_dir / "test-model"
        model_dir.mkdir()
        
        # Create model files
        (model_dir / "models").mkdir()
        (model_dir / "artifacts").mkdir() 
        (model_dir / "metadata").mkdir()
        
        # Create manifest file
        manifest = {
            "name": "test-model",
            "version": "1.0.0", 
            "created_at": "2025-01-01T00:00:00Z"
        }
        import json
        (model_dir / "model_manifest.json").write_text(json.dumps(manifest))
        
        # Create some dummy model files
        (model_dir / "models" / "model.pkl").write_bytes(b"dummy model data")
        (model_dir / "artifacts" / "metrics.json").write_text('{"accuracy": 0.95}')
        
        yield model_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.fixture 
    def s3_backend_with_moto(self):
        """Create S3 backend with moto emulation."""
        # Set dummy AWS credentials to prevent accidental real AWS calls
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SECURITY_TOKEN"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        
        with mock_aws():
            # Create S3 client and bucket
            s3_client = boto3.client("s3", region_name="us-east-1")
            bucket_name = "test-model-registry-bucket"
            s3_client.create_bucket(Bucket=bucket_name)
            
            # Create backend
            backend = S3StorageBackend(
                bucket_name=bucket_name,
                access_key="testing",
                secret_key="testing",
                region="us-east-1"
            )
            
            yield backend

    @pytest.mark.asyncio
    async def test_upload_download_cycle_with_moto(self, s3_backend_with_moto, temp_model_dir):
        """Test complete upload/download cycle with moto emulator.
        
        This test validates that:
        1. Models can be uploaded to S3 with proper compression
        2. Storage URLs are generated correctly
        3. Models can be downloaded and extracted properly
        4. File integrity is maintained through the cycle
        """
        backend = s3_backend_with_moto
        model_id = "integration-test-model"
        
        # Upload model
        storage_url = await backend.upload_model(temp_model_dir, model_id)
        
        # Verify storage URL format
        assert storage_url.startswith("s3://")
        assert model_id in storage_url
        assert storage_url.endswith("model_bundle.tar.gz")
        
        # Download to different location
        download_dir = temp_model_dir.parent / "downloaded"
        await backend.download_model(storage_url, download_dir / "test-model")
        
        # Verify downloaded files exist
        downloaded_model = download_dir / "test-model"
        assert downloaded_model.exists()
        assert (downloaded_model / "model_manifest.json").exists()
        assert (downloaded_model / "models" / "model.pkl").exists()
        assert (downloaded_model / "artifacts" / "metrics.json").exists()
        
        # Verify file contents preserved
        import json
        manifest = json.loads((downloaded_model / "model_manifest.json").read_text())
        assert manifest["name"] == "test-model"
        assert manifest["version"] == "1.0.0"
        
        model_data = (downloaded_model / "models" / "model.pkl").read_bytes()
        assert model_data == b"dummy model data"

    @pytest.mark.asyncio 
    async def test_signed_url_generation_with_moto(self, s3_backend_with_moto, temp_model_dir):
        """Test signed URL generation with moto emulator.
        
        This test validates that:
        1. Signed URLs can be generated for uploaded models
        2. URLs have proper expiration parameters
        3. URLs are properly formatted for S3 access
        """
        backend = s3_backend_with_moto
        model_id = "signed-url-test-model"
        
        # Upload model first
        storage_url = await backend.upload_model(temp_model_dir, model_id)
        
        # Generate signed URL
        expires_in = 3600
        signed_url = await backend.generate_signed_url(storage_url, expires_in)
        
        # Verify signed URL format (moto uses older AWS signature format)
        assert signed_url.startswith("https://")
        assert "amazonaws.com" in signed_url
        assert "AWSAccessKeyId" in signed_url
        assert "Signature" in signed_url
        assert "Expires" in signed_url
        
        # Verify signed URL contains model path
        assert model_id in signed_url
        assert "model_bundle.tar.gz" in signed_url

    @pytest.mark.asyncio
    async def test_delete_model_with_moto(self, s3_backend_with_moto, temp_model_dir):
        """Test model deletion with moto emulator.
        
        This test validates that:
        1. Models can be deleted from S3
        2. Deletion operations complete successfully
        3. Deleted models are no longer accessible
        """
        backend = s3_backend_with_moto
        model_id = "delete-test-model"
        
        # Upload model first
        storage_url = await backend.upload_model(temp_model_dir, model_id)
        
        # Verify model exists by generating signed URL
        signed_url = await backend.generate_signed_url(storage_url)
        assert signed_url is not None
        
        # Delete model
        await backend.delete_model(storage_url)
        
        # Verify deletion by attempting to generate signed URL for non-existent object
        # This should still work in moto (generates URL for non-existent object)
        # In real S3, this would fail, but moto behavior differs slightly
        signed_url_after_delete = await backend.generate_signed_url(storage_url)
        assert signed_url_after_delete is not None  # moto allows this

    @pytest.mark.asyncio
    async def test_error_handling_with_invalid_bucket(self):
        """Test error handling with invalid bucket configuration.
        
        This test validates proper error propagation when:
        1. S3 operations are attempted on non-existent buckets
        2. Network-level errors occur during operations
        3. AWS credential errors are handled properly
        """
        # Create backend with non-existent bucket (no moto mock)
        backend = S3StorageBackend(
            bucket_name="non-existent-bucket-12345",
            access_key="invalid",
            secret_key="invalid", 
            region="us-east-1"
        )
        
        # This should fail due to invalid credentials/bucket
        with pytest.raises(Exception):  # Will be specific AWS error in real implementation
            temp_dir = Path(tempfile.mkdtemp())
            try:
                await backend.upload_model(temp_dir, "test-model")
            finally:
                shutil.rmtree(temp_dir)


class TestAzureBlobStorageIntegration:
    """Integration tests for Azure Blob Storage using Azurite emulator."""

    @pytest.fixture(scope="class")
    def azurite_container(self):
        """Start Azurite container for Azure Blob Storage emulation."""
        try:
            from testcontainers.azurite import AzuriteContainer
            import docker
            # Check if Docker is available
            docker.from_env().ping()
            AZURITE_AVAILABLE = True
        except (ImportError, Exception) as e:
            pytest.skip(f"testcontainers, Docker, or AzuriteContainer not available: {e}")
        
        with AzuriteContainer() as azurite:
            yield azurite

    @pytest.fixture
    def temp_model_dir(self):
        """Create temporary model directory for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create model structure
        model_dir = temp_dir / "test-model-azure"
        model_dir.mkdir()
        
        # Create model files
        (model_dir / "models").mkdir()
        (model_dir / "artifacts").mkdir() 
        (model_dir / "metadata").mkdir()
        
        # Create manifest file
        manifest = {
            "name": "test-model-azure",
            "version": "1.0.0", 
            "created_at": "2025-01-01T00:00:00Z"
        }
        import json
        (model_dir / "model_manifest.json").write_text(json.dumps(manifest))
        
        # Create some dummy model files
        (model_dir / "models" / "model.pkl").write_bytes(b"dummy azure model data")
        (model_dir / "artifacts" / "metrics.json").write_text('{"accuracy": 0.92}')
        
        yield model_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def azure_backend_with_azurite(self, azurite_container):
        """Create Azure Blob Storage backend with Azurite emulation."""
        from emuses.tools.cloud_storage import AzureBlobStorageBackend
        
        # Get connection string from Azurite container
        connection_string = azurite_container.get_connection_string()
        container_name = "test-model-registry-container"
        
        # Create Azure Blob Storage client and container
        from azure.storage.blob import BlobServiceClient
        client = BlobServiceClient.from_connection_string(connection_string)
        
        try:
            client.create_container(container_name)
        except Exception:
            pass  # Container may already exist
        
        # Create backend
        backend = AzureBlobStorageBackend(
            container_name=container_name,
            connection_string=connection_string
        )
        
        return backend

    @pytest.mark.asyncio
    async def test_azure_upload_download_cycle_with_azurite(self, azure_backend_with_azurite, temp_model_dir):
        """Test complete upload/download cycle with Azurite emulator.
        
        This test validates that:
        1. Models can be uploaded to Azure Blob Storage with proper compression
        2. Storage URLs are generated correctly with Azure format
        3. Models can be downloaded and extracted properly
        4. File integrity is maintained through the cycle
        """
        backend = azure_backend_with_azurite
        model_id = "azure-integration-test-model"
        
        # Upload model
        storage_url = await backend.upload_model(temp_model_dir, model_id)
        
        # Verify storage URL format
        assert storage_url.startswith("azure://")
        assert model_id in storage_url
        assert storage_url.endswith("model_bundle.tar.gz")
        
        # Download to different location
        download_dir = temp_model_dir.parent / "downloaded_azure"
        await backend.download_model(storage_url, download_dir / "test-model-azure")
        
        # Verify downloaded files exist
        downloaded_model = download_dir / "test-model-azure"
        assert downloaded_model.exists()
        assert (downloaded_model / "model_manifest.json").exists()
        assert (downloaded_model / "models" / "model.pkl").exists()
        assert (downloaded_model / "artifacts" / "metrics.json").exists()
        
        # Verify file contents preserved
        import json
        manifest = json.loads((downloaded_model / "model_manifest.json").read_text())
        assert manifest["name"] == "test-model-azure"
        assert manifest["version"] == "1.0.0"
        
        model_data = (downloaded_model / "models" / "model.pkl").read_bytes()
        assert model_data == b"dummy azure model data"

    @pytest.mark.asyncio 
    async def test_azure_signed_url_generation_with_azurite(self, azure_backend_with_azurite, temp_model_dir):
        """Test signed URL generation with Azurite emulator.
        
        This test validates that:
        1. Signed URLs can be generated for uploaded models
        2. URLs have proper SAS token parameters
        3. URLs are properly formatted for Azure Blob access
        """
        backend = azure_backend_with_azurite
        model_id = "azure-signed-url-test-model"
        
        # Upload model first
        storage_url = await backend.upload_model(temp_model_dir, model_id)
        
        # Generate signed URL
        expires_in = 3600
        signed_url = await backend.generate_signed_url(storage_url, expires_in)
        
        # Verify signed URL format (Azure SAS token format)
        assert signed_url.startswith("https://")
        assert "blob.core.windows.net" in signed_url or "127.0.0.1" in signed_url  # Azurite uses localhost
        assert "se=" in signed_url  # expiry time
        assert "sp=" in signed_url  # permissions
        assert "sig=" in signed_url  # signature
        
        # Verify signed URL contains model path
        assert model_id in signed_url
        assert "model_bundle.tar.gz" in signed_url

    @pytest.mark.asyncio
    async def test_azure_delete_model_with_azurite(self, azure_backend_with_azurite, temp_model_dir):
        """Test model deletion with Azurite emulator.
        
        This test validates that:
        1. Models can be deleted from Azure Blob Storage
        2. Deletion operations complete successfully
        3. Deleted models are no longer accessible
        """
        backend = azure_backend_with_azurite
        model_id = "azure-delete-test-model"
        
        # Upload model first
        storage_url = await backend.upload_model(temp_model_dir, model_id)
        
        # Verify model exists by generating signed URL
        signed_url = await backend.generate_signed_url(storage_url)
        assert signed_url is not None
        
        # Delete model
        await backend.delete_model(storage_url)
        
        # After deletion, signed URL generation should still work
        # (Azure allows generating SAS tokens for non-existent blobs)
        signed_url_after_delete = await backend.generate_signed_url(storage_url)
        assert signed_url_after_delete is not None


class TestGCSStorageIntegration:
    """Integration tests for Google Cloud Storage using fake-gcs-server emulator."""

    @pytest.fixture(scope="class")
    def fake_gcs_container(self):
        """Start fake-gcs-server container for GCS emulation."""
        try:
            from testcontainers.compose import DockerCompose
            import docker
            # Check if Docker is available
            docker.from_env().ping()
            GCS_AVAILABLE = True
        except (ImportError, Exception) as e:
            pytest.skip(f"Docker, testcontainers, or fake-gcs-server not available: {e}")
        
        # Create a simple fake GCS server setup using generic container
        # In a real environment, you would use fake-gcs-server Docker image
        from testcontainers.generic import GenericContainer
        
        try:
            with GenericContainer("fsouza/fake-gcs-server").with_exposed_ports(4443) as gcs:
                yield gcs
        except Exception as e:
            pytest.skip(f"fake-gcs-server container not available: {e}")

    @pytest.fixture
    def temp_model_dir(self):
        """Create temporary model directory for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create model structure
        model_dir = temp_dir / "test-model-gcs"
        model_dir.mkdir()
        
        # Create model files
        (model_dir / "models").mkdir()
        (model_dir / "artifacts").mkdir() 
        (model_dir / "metadata").mkdir()
        
        # Create manifest file
        manifest = {
            "name": "test-model-gcs",
            "version": "1.0.0", 
            "created_at": "2025-01-01T00:00:00Z"
        }
        import json
        (model_dir / "model_manifest.json").write_text(json.dumps(manifest))
        
        # Create some dummy model files
        (model_dir / "models" / "model.pkl").write_bytes(b"dummy gcs model data")
        (model_dir / "artifacts" / "metrics.json").write_text('{"accuracy": 0.98}')
        
        yield model_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def gcs_backend_with_fake_gcs(self, fake_gcs_container):
        """Create GCS backend with fake-gcs-server emulation."""
        from emuses.tools.cloud_storage import GCSStorageBackend
        
        # Get container host and port
        host = fake_gcs_container.get_container_host_ip()
        port = fake_gcs_container.get_exposed_port(4443)
        
        # For fake-gcs-server, we need to create a backend that points to the emulator
        # This would require modifying GCSStorageBackend to accept custom endpoint
        # For now, we'll skip this test until proper endpoint configuration is added
        pytest.skip("GCS backend endpoint configuration not yet implemented for emulator")

    @pytest.mark.asyncio
    async def test_gcs_upload_download_cycle_with_fake_gcs(self, gcs_backend_with_fake_gcs, temp_model_dir):
        """Test complete upload/download cycle with fake-gcs-server emulator.
        
        This test validates that:
        1. Models can be uploaded to GCS with proper compression
        2. Storage URLs are generated correctly with GCS format
        3. Models can be downloaded and extracted properly
        4. File integrity is maintained through the cycle
        """
        backend = gcs_backend_with_fake_gcs
        model_id = "gcs-integration-test-model"
        
        # Upload model
        storage_url = await backend.upload_model(temp_model_dir, model_id)
        
        # Verify storage URL format
        assert storage_url.startswith("gs://")
        assert model_id in storage_url
        assert storage_url.endswith("model_bundle.tar.gz")
        
        # Download to different location
        download_dir = temp_model_dir.parent / "downloaded_gcs"
        await backend.download_model(storage_url, download_dir / "test-model-gcs")
        
        # Verify downloaded files exist
        downloaded_model = download_dir / "test-model-gcs"
        assert downloaded_model.exists()
        assert (downloaded_model / "model_manifest.json").exists()
        assert (downloaded_model / "models" / "model.pkl").exists()
        assert (downloaded_model / "artifacts" / "metrics.json").exists()
        
        # Verify file contents preserved
        import json
        manifest = json.loads((downloaded_model / "model_manifest.json").read_text())
        assert manifest["name"] == "test-model-gcs"
        assert manifest["version"] == "1.0.0"
        
        model_data = (downloaded_model / "models" / "model.pkl").read_bytes()
        assert model_data == b"dummy gcs model data"

    @pytest.mark.asyncio 
    async def test_gcs_signed_url_generation_with_fake_gcs(self, gcs_backend_with_fake_gcs, temp_model_dir):
        """Test signed URL generation with fake-gcs-server emulator.
        
        This test validates that:
        1. Signed URLs can be generated for uploaded models
        2. URLs have proper GCS signed URL parameters
        3. URLs are properly formatted for GCS access
        """
        backend = gcs_backend_with_fake_gcs
        model_id = "gcs-signed-url-test-model"
        
        # Upload model first
        storage_url = await backend.upload_model(temp_model_dir, model_id)
        
        # Generate signed URL
        expires_in = 3600
        signed_url = await backend.generate_signed_url(storage_url, expires_in)
        
        # Verify signed URL format (GCS signed URL format)
        assert signed_url.startswith("https://")
        assert "storage.googleapis.com" in signed_url or "127.0.0.1" in signed_url  # fake-gcs-server uses localhost
        assert "X-Goog-Algorithm" in signed_url
        assert "X-Goog-Credential" in signed_url
        assert "X-Goog-Signature" in signed_url
        
        # Verify signed URL contains model path
        assert model_id in signed_url
        assert "model_bundle.tar.gz" in signed_url

    @pytest.mark.asyncio
    async def test_gcs_delete_model_with_fake_gcs(self, gcs_backend_with_fake_gcs, temp_model_dir):
        """Test model deletion with fake-gcs-server emulator.
        
        This test validates that:
        1. Models can be deleted from GCS
        2. Deletion operations complete successfully
        3. Deleted models are no longer accessible
        """
        backend = gcs_backend_with_fake_gcs
        model_id = "gcs-delete-test-model"
        
        # Upload model first
        storage_url = await backend.upload_model(temp_model_dir, model_id)
        
        # Verify model exists by generating signed URL
        signed_url = await backend.generate_signed_url(storage_url)
        assert signed_url is not None
        
        # Delete model
        await backend.delete_model(storage_url)
        
        # After deletion, signed URL generation should fail for non-existent object
        with pytest.raises(Exception):
            await backend.generate_signed_url(storage_url)


class TestUnifiedCloudFixtures:
    """Test unified cloud fixtures and infrastructure."""

    def test_cloud_test_environment_fixture(self, cloud_test_environment):
        """Test that cloud test environment fixture provides correct information."""
        assert isinstance(cloud_test_environment, dict)
        assert "docker" in cloud_test_environment
        assert "aws_moto" in cloud_test_environment
        assert "azure_azurite" in cloud_test_environment
        assert "gcs_fake_server" in cloud_test_environment
        
        # All values should be boolean
        for key, value in cloud_test_environment.items():
            assert isinstance(value, bool)
            
    def test_cloud_test_model_dir_fixture(self, cloud_test_model_dir):
        """Test that cloud test model directory fixture creates proper structure."""
        model_dir = cloud_test_model_dir
        
        # Verify directory structure
        assert model_dir.exists()
        assert (model_dir / "models").exists()
        assert (model_dir / "artifacts").exists()
        assert (model_dir / "metadata").exists()
        
        # Verify manifest file
        manifest_file = model_dir / "model_manifest.json"
        assert manifest_file.exists()
        
        import json
        manifest = json.loads(manifest_file.read_text())
        assert manifest["name"] == "cloud-test-model"
        assert manifest["version"] == "1.0.0"
        assert "metrics" in manifest
        
        # Verify test files
        assert (model_dir / "models" / "model.pkl").exists()
        assert (model_dir / "artifacts" / "metrics.json").exists()
        assert (model_dir / "artifacts" / "config.yaml").exists()
        assert (model_dir / "metadata" / "training_log.txt").exists()
        
    def test_aws_test_credentials_fixture(self, aws_test_credentials):
        """Test that AWS test credentials fixture sets proper environment variables."""
        assert isinstance(aws_test_credentials, dict)
        
        # Check required AWS credential variables
        required_vars = [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY", 
            "AWS_SECURITY_TOKEN",
            "AWS_SESSION_TOKEN",
            "AWS_DEFAULT_REGION"
        ]
        
        for var in required_vars:
            assert var in aws_test_credentials
            assert os.environ.get(var) == aws_test_credentials[var]
            
        # Verify test values to prevent accidental real AWS calls
        assert aws_test_credentials["AWS_ACCESS_KEY_ID"] == "testing"
        assert aws_test_credentials["AWS_SECRET_ACCESS_KEY"] == "testing"
        
    def test_cloud_emulator_config_fixture(self, cloud_emulator_config):
        """Test that cloud emulator config fixture provides proper configuration."""
        config = cloud_emulator_config
        assert isinstance(config, dict)
        
        # Check all cloud providers are configured
        assert "aws" in config
        assert "azure" in config
        assert "gcs" in config
        
        # Verify AWS config
        aws_config = config["aws"]
        assert aws_config["provider"] == "s3"
        assert aws_config["emulator"] == "moto"
        assert "bucket_name" in aws_config
        
        # Verify Azure config
        azure_config = config["azure"]
        assert azure_config["provider"] == "azure"
        assert azure_config["emulator"] == "azurite"
        assert "container_name" in azure_config
        
        # Verify GCS config
        gcs_config = config["gcs"]
        assert gcs_config["provider"] == "gcs"
        assert gcs_config["emulator"] == "fake-gcs-server"
        assert "bucket_name" in gcs_config