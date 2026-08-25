"""Tests for cloud storage abstraction layer."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
import tempfile
import shutil

from emuses.extras.cloud_storage import (
    CloudStorageBackend, 
    S3StorageBackend, 
    AzureBlobStorageBackend,
    GCSStorageBackend
)


class TestCloudStorageBackend:
    """Tests for abstract CloudStorageBackend class."""
    
    def test_abstract_base_class_cannot_be_instantiated(self):
        """Test that CloudStorageBackend cannot be instantiated directly."""
        with pytest.raises(TypeError):
            CloudStorageBackend()
    
    @pytest.mark.asyncio
    async def test_abstract_methods_must_be_implemented(self):
        """Test that concrete implementations must implement all abstract methods."""
        
        # Create a concrete implementation that doesn't implement all methods
        class IncompleteBackend(CloudStorageBackend):
            # Missing implementations
            pass
        
        with pytest.raises(TypeError):
            IncompleteBackend()


class TestS3StorageBackend:
    """Tests for S3StorageBackend implementation."""
    
    @pytest.fixture
    def s3_backend(self):
        """Create S3StorageBackend for testing."""
        return S3StorageBackend(
            bucket_name="test-bucket",
            access_key="test-key",
            secret_key="test-secret",
            region="us-east-1"
        )
    
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
        
        yield model_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_upload_model_success(self, s3_backend, temp_model_dir):
        """Test successful model upload to S3."""
        model_id = "test-model-123"
        
        # Mock S3 client
        with patch.object(s3_backend, '_get_s3_client') as mock_s3:
            mock_client = MagicMock()
            mock_s3.return_value = mock_client
            mock_client.upload_file.return_value = None
            
            # Test upload
            storage_url = await s3_backend.upload_model(temp_model_dir, model_id)
            
            # Verify result
            assert storage_url.startswith("s3://")
            assert model_id in storage_url
            assert mock_client.upload_file.called
    
    @pytest.mark.asyncio
    async def test_download_model_success(self, s3_backend, temp_model_dir):
        """Test successful model download from S3."""
        storage_url = "s3://test-bucket/models/test-model-123/model_bundle.tar.gz"
        local_path = temp_model_dir.parent / "downloaded"
        
        with patch.object(s3_backend, '_get_s3_client') as mock_s3:
            mock_client = MagicMock()
            mock_s3.return_value = mock_client
            mock_client.download_file.return_value = None
            
            # Mock tar extraction
            with patch('tarfile.open') as mock_tar:
                mock_tar_obj = MagicMock()
                mock_tar.return_value.__enter__.return_value = mock_tar_obj
                
                await s3_backend.download_model(storage_url, local_path)
                
                # Verify download was called
                assert mock_client.download_file.called
                # Verify extraction was called  
                assert mock_tar_obj.extractall.called
    
    @pytest.mark.asyncio
    async def test_delete_model_success(self, s3_backend):
        """Test successful model deletion from S3."""
        storage_url = "s3://test-bucket/models/test-model-123/model_bundle.tar.gz"
        
        with patch.object(s3_backend, '_get_s3_client') as mock_s3:
            mock_client = MagicMock()
            mock_s3.return_value = mock_client
            mock_client.delete_object.return_value = None
            
            await s3_backend.delete_model(storage_url)
            
            # Verify deletion was called
            assert mock_client.delete_object.called
    
    @pytest.mark.asyncio
    async def test_generate_signed_url_success(self, s3_backend):
        """Test successful signed URL generation."""
        storage_url = "s3://test-bucket/models/test-model-123/model_bundle.tar.gz"
        expires_in = 3600
        
        with patch.object(s3_backend, '_get_s3_client') as mock_s3:
            mock_client = MagicMock()
            mock_s3.return_value = mock_client
            mock_client.generate_presigned_url.return_value = "https://signed-url.example.com"
            
            signed_url = await s3_backend.generate_signed_url(storage_url, expires_in)
            
            # Verify signed URL generation
            assert signed_url == "https://signed-url.example.com"
            assert mock_client.generate_presigned_url.called
    
    def test_parse_s3_url(self, s3_backend):
        """Test S3 URL parsing."""
        storage_url = "s3://test-bucket/models/test-model-123/model_bundle.tar.gz"
        
        bucket, key = s3_backend._parse_s3_url(storage_url)
        
        assert bucket == "test-bucket"
        assert key == "models/test-model-123/model_bundle.tar.gz"
    
    def test_invalid_s3_url_raises_error(self, s3_backend):
        """Test that invalid S3 URLs raise appropriate errors."""
        invalid_urls = [
            "https://example.com/file.tar.gz",  # Not S3
            "s3://",  # No bucket/key
            "file:///local/path.tar.gz"  # Local file
        ]
        
        for invalid_url in invalid_urls:
            with pytest.raises(ValueError, match="Invalid S3 URL"):
                s3_backend._parse_s3_url(invalid_url)


class TestAzureBlobStorageBackend:
    """Tests for Azure Blob Storage backend implementation."""
    
    @pytest.fixture
    def azure_backend(self):
        """Create AzureBlobStorageBackend for testing."""
        return AzureBlobStorageBackend(
            container_name="test-container",
            connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net"
        )
    
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
        
        yield model_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_upload_model_success(self, azure_backend, temp_model_dir):
        """Test successful model upload to Azure Blob Storage."""
        model_id = "test-model-123"
        
        # Mock Azure client
        with patch.object(azure_backend, '_get_blob_client') as mock_azure:
            mock_client = MagicMock()
            mock_azure.return_value = mock_client
            mock_client.upload_blob.return_value = None
            
            # Test upload
            storage_url = await azure_backend.upload_model(temp_model_dir, model_id)
            
            # Verify result
            assert storage_url.startswith("azure://")
            assert model_id in storage_url
            assert mock_client.upload_blob.called
    
    def test_parse_azure_url(self, azure_backend):
        """Test Azure URL parsing."""
        storage_url = "azure://test-container/models/test-model-123/model_bundle.tar.gz"
        
        container, blob_name = azure_backend._parse_azure_url(storage_url)
        
        assert container == "test-container"
        assert blob_name == "models/test-model-123/model_bundle.tar.gz"


class TestGCSStorageBackend:
    """Tests for Google Cloud Storage backend implementation."""
    
    @pytest.fixture
    def gcs_backend(self):
        """Create GCSStorageBackend for testing."""
        return GCSStorageBackend(
            bucket_name="test-bucket",
            project_id="test-project",
            credentials_path="/path/to/credentials.json"
        )
    
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
        
        yield model_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_upload_model_success(self, gcs_backend, temp_model_dir):
        """Test successful model upload to Google Cloud Storage."""
        model_id = "test-model-123"
        
        # Mock GCS client
        with patch.object(gcs_backend, '_get_storage_client') as mock_gcs:
            mock_client = MagicMock()
            mock_gcs.return_value = mock_client
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            mock_client.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            mock_blob.upload_from_filename.return_value = None
            
            # Test upload
            storage_url = await gcs_backend.upload_model(temp_model_dir, model_id)
            
            # Verify result
            assert storage_url.startswith("gs://")
            assert model_id in storage_url
            assert mock_blob.upload_from_filename.called
    
    def test_parse_gcs_url(self, gcs_backend):
        """Test GCS URL parsing."""
        storage_url = "gs://test-bucket/models/test-model-123/model_bundle.tar.gz"
        
        bucket, object_name = gcs_backend._parse_gcs_url(storage_url)
        
        assert bucket == "test-bucket"
        assert object_name == "models/test-model-123/model_bundle.tar.gz"


class TestCloudStorageIntegration:
    """Integration tests for cloud storage operations."""
    
    @pytest.mark.asyncio
    async def test_backend_factory_creates_correct_type(self):
        """Test that backend factory creates correct storage backend type."""
        from emuses.extras.cloud_storage import create_storage_backend
        
        # Test S3 creation
        s3_config = {
            "provider": "s3",
            "bucket_name": "test-bucket",
            "access_key": "key",
            "secret_key": "secret",
            "region": "us-east-1"
        }
        
        backend = create_storage_backend(s3_config)
        assert isinstance(backend, S3StorageBackend)
        assert backend.bucket_name == "test-bucket"
        
        # Test Azure creation
        azure_config = {
            "provider": "azure",
            "container_name": "test-container",
            "connection_string": "test-connection-string"
        }
        
        backend = create_storage_backend(azure_config)
        assert isinstance(backend, AzureBlobStorageBackend)
        assert backend.container_name == "test-container"
        
        # Test GCS creation
        gcs_config = {
            "provider": "gcs",
            "bucket_name": "test-bucket",
            "project_id": "test-project",
            "credentials_path": "/path/to/creds.json"
        }
        
        backend = create_storage_backend(gcs_config)
        assert isinstance(backend, GCSStorageBackend)
        assert backend.bucket_name == "test-bucket"
    
    @pytest.mark.asyncio
    async def test_unsupported_provider_raises_error(self):
        """Test that unsupported provider raises appropriate error."""
        from emuses.extras.cloud_storage import create_storage_backend
        
        unsupported_config = {
            "provider": "dropbox",  # Not supported
            "access_token": "token"
        }
        
        with pytest.raises(ValueError, match="Unsupported storage provider"):
            create_storage_backend(unsupported_config)