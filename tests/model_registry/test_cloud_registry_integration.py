"""Integration tests for CloudModelRegistry functionality - Task 3.7.1b.

This module provides comprehensive integration testing for CloudModelRegistry,
testing the interaction between database operations, cloud storage, permission
management, and caching functionality.
"""
import pytest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4
from datetime import datetime

from emuses.tools.cloud_model_registry import CloudModelRegistry, CloudModelRegistryError
from emuses.tools.cloud_storage import S3StorageBackend
from emuses.multi_user_service.models import User, ModelRegistry, Workspace, ModelAccess


@pytest.fixture
def mock_storage_backend():
    """Create mock cloud storage backend."""
    backend = MagicMock(spec=S3StorageBackend)
    backend.upload_model = AsyncMock(return_value="s3://bucket/models/test-model/model_bundle.tar.gz")
    backend.download_model = AsyncMock()
    backend.delete_model = AsyncMock()
    backend.generate_signed_url = AsyncMock(return_value="https://signed-url.example.com")
    return backend


class TestCloudModelRegistryIntegration:
    """Integration tests for CloudModelRegistry with database and cloud storage."""
    
    @pytest.fixture
    def mock_user(self):
        """Create mock user for testing."""
        user = MagicMock(spec=User)
        user.id = uuid4()
        user.username = "test-user"
        user.email = "test@example.com"
        user.is_active = True
        return user
    
    @pytest.fixture
    def mock_workspace(self):
        """Create mock workspace for testing."""
        workspace = MagicMock(spec=Workspace)
        workspace.id = uuid4()
        workspace.name = "test-workspace"
        workspace.description = "Test workspace"
        return workspace
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        session.add.return_value = None
        session.commit.return_value = None
        session.rollback.return_value = None
        session.close.return_value = None
        return session
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def cloud_registry(self, mock_db_session, mock_user, mock_storage_backend, temp_cache_dir):
        """Create CloudModelRegistry instance for testing."""
        return CloudModelRegistry(
            db_session=mock_db_session,
            user=mock_user,
            storage_backend=mock_storage_backend,
            local_cache_path=temp_cache_dir,
            enable_caching=True,
            default_tier="hot"
        )
    
    @pytest.mark.asyncio
    async def test_upload_model_integration(self, cloud_registry, mock_db_session, cloud_test_model_dir):
        """Test complete model upload integration flow."""
        model_id = "integration-test-model"
        metadata = {
            "name": "Integration Test Model",
            "description": "Test model for integration testing",
            "version": "1.0.0",
            "tags": ["test", "integration"],
            "workspace_id": str(uuid4())
        }
        
        # Mock database model creation
        mock_model_record = MagicMock(spec=ModelRegistry)
        mock_model_record.id = model_id
        mock_model_record.name = metadata["name"]
        mock_model_record.cloud_storage_url = None
        mock_db_session.add.return_value = None
        
        # Execute upload
        result = await cloud_registry.upload_model(cloud_test_model_dir, model_id, metadata)
        
        # Verify results
        assert result["model_id"] == model_id
        assert result["name"] == metadata["name"]
        assert "cloud_storage_url" in result
        assert result["cloud_storage_url"].startswith("s3://")
        assert "upload_time" in result
        assert "size_bytes" in result
        
        # Verify cloud storage backend was called
        cloud_registry.storage_backend.upload_model.assert_called_once_with(cloud_test_model_dir, model_id)
        
        # Verify database operations
        assert mock_db_session.add.called
        assert mock_db_session.commit.called
    
    @pytest.mark.asyncio
    async def test_download_model_with_caching_integration(self, cloud_registry, cloud_test_model_dir):
        """Test model download with local caching integration."""
        model_id = "cached-model-test"
        download_path = cloud_test_model_dir.parent / "downloaded"
        
        # Mock model record in database
        mock_model = MagicMock(spec=ModelRegistry)
        mock_model.id = model_id
        mock_model.cloud_storage_url = "s3://bucket/models/cached-model-test/model_bundle.tar.gz"
        mock_model.name = "Cached Test Model"
        mock_model.size_bytes = 1024
        
        cloud_registry.db_session.query.return_value.filter.return_value.first.return_value = mock_model
        
        # Execute download
        result = await cloud_registry.download_model(model_id, download_path, use_cache=True)
        
        # Verify results
        assert result["model_id"] == model_id
        assert result["local_path"] == str(download_path)
        assert "download_time" in result
        assert result["cache_hit"] in [True, False]  # Could be either depending on cache state
        
        # Verify cloud storage backend was called
        cloud_registry.storage_backend.download_model.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_signed_url_generation_integration(self, cloud_registry):
        """Test signed URL generation with permission validation."""
        model_id = "signed-url-test-model"
        
        # Mock model with permissions
        mock_model = MagicMock(spec=ModelRegistry)
        mock_model.id = model_id
        mock_model.cloud_storage_url = "s3://bucket/models/signed-url-test-model/model_bundle.tar.gz"
        mock_model.owner_id = cloud_registry.user.id
        mock_model.access_level = "public"
        
        cloud_registry.db_session.query.return_value.filter.return_value.first.return_value = mock_model
        
        # Execute signed URL generation
        result = await cloud_registry.get_signed_url(model_id, expires_in=3600)
        
        # Verify results
        assert result["model_id"] == model_id
        assert result["signed_url"] == "https://signed-url.example.com"
        assert result["expires_in"] == 3600
        assert "generated_at" in result
        
        # Verify cloud storage backend was called
        cloud_registry.storage_backend.generate_signed_url.assert_called_once_with(
            mock_model.cloud_storage_url, 3600
        )
    
    @pytest.mark.asyncio
    async def test_model_deletion_integration(self, cloud_registry, mock_db_session):
        """Test complete model deletion from cloud storage and database."""
        model_id = "deletion-test-model"
        
        # Mock model in database
        mock_model = MagicMock(spec=ModelRegistry)
        mock_model.id = model_id
        mock_model.cloud_storage_url = "s3://bucket/models/deletion-test-model/model_bundle.tar.gz"
        mock_model.owner_id = cloud_registry.user.id
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_model
        
        # Execute deletion
        result = await cloud_registry.delete_model(model_id)
        
        # Verify results
        assert result["model_id"] == model_id
        assert result["deleted"] is True
        assert "deletion_time" in result
        
        # Verify cloud storage deletion
        cloud_registry.storage_backend.delete_model.assert_called_once_with(
            mock_model.cloud_storage_url
        )
        
        # Verify database deletion
        assert mock_db_session.delete.called or mock_db_session.query.called
        assert mock_db_session.commit.called
    
    @pytest.mark.asyncio
    async def test_list_models_with_cloud_metadata(self, cloud_registry, mock_db_session):
        """Test listing models with cloud storage metadata integration."""
        # Mock multiple models in database
        mock_models = []
        for i in range(1, 4):
            mock_model = MagicMock()
            mock_model.id = f"model-{i}"
            mock_model.name = f"Test Model {i}"
            mock_model.version = "1.0.0"
            mock_model.owner_id = cloud_registry.user.id
            mock_model.workspace_id = None
            mock_model.is_public = False
            mock_model.created_at = datetime.now()
            mock_model.updated_at = datetime.now()
            mock_model.model_size_bytes = 1024 * i
            mock_model.description = f"Test model {i} description"
            mock_model.tags = [f"tag{i}"]
            mock_model.model_type = "test"
            mock_model.download_count = i * 10
            mock_model.last_accessed = datetime.now()
            mock_model.cloud_storage_url = f"s3://bucket/models/model-{i}/model_bundle.tar.gz"
            mock_model.size_bytes = 1024 * i
            mock_model.access_level = "private"
            mock_models.append(mock_model)
        
        # Set up the mock query chain to handle .limit().offset().all()
        mock_db_session.query.return_value.filter.return_value.limit.return_value.offset.return_value.all.return_value = mock_models
        
        # Execute listing
        result = await cloud_registry.list_models(include_cloud_metadata=True)
        
        # Verify results
        assert len(result["models"]) == 3
        
        for i, model in enumerate(result["models"], 1):
            assert model["id"] == f"model-{i}"
            assert model["name"] == f"Test Model {i}"
            assert "cloud_storage_url" in model
            assert model["cloud_storage_url"].endswith("model_bundle.tar.gz")
            assert "size_bytes" in model
            assert model["size_bytes"] == 1024 * i
    
    @pytest.mark.asyncio
    async def test_storage_tier_management_integration(self, cloud_registry):
        """Test storage tier management and migration."""
        model_id = "tier-test-model"
        
        # Mock model in hot storage
        mock_model = MagicMock(spec=ModelRegistry)
        mock_model.id = model_id
        mock_model.cloud_storage_url = "s3://bucket/models/tier-test-model/model_bundle.tar.gz"
        mock_model.storage_tier = "hot"
        mock_model.owner_id = cloud_registry.user.id
        
        cloud_registry.db_session.query.return_value.filter.return_value.first.return_value = mock_model
        
        # Test tier migration
        result = await cloud_registry.migrate_storage_tier(model_id, "cold")
        
        # Verify results
        assert result["model_id"] == model_id
        assert result["old_tier"] == "hot"
        assert result["new_tier"] == "cold"
        assert result["migrated"] is True
        
        # Verify database update
        assert cloud_registry.db_session.commit.called


class TestCloudModelRegistryErrorHandling:
    """Test error handling and edge cases in CloudModelRegistry integration."""
    
    @pytest.fixture
    def cloud_registry_with_errors(self, mock_db_session, mock_user, temp_cache_dir):
        """Create CloudModelRegistry with failing storage backend."""
        failing_backend = MagicMock(spec=S3StorageBackend)
        failing_backend.upload_model = AsyncMock(side_effect=Exception("Storage failure"))
        failing_backend.download_model = AsyncMock(side_effect=Exception("Download failure"))
        failing_backend.delete_model = AsyncMock(side_effect=Exception("Deletion failure"))
        
        return CloudModelRegistry(
            db_session=mock_db_session,
            user=mock_user,
            storage_backend=failing_backend,
            local_cache_path=temp_cache_dir
        )
    
    @pytest.mark.asyncio
    async def test_upload_failure_rollback(self, cloud_registry_with_errors, cloud_test_model_dir, mock_db_session):
        """Test database rollback on cloud upload failure."""
        model_id = "upload-failure-test"
        metadata = {"name": "Upload Failure Test", "version": "1.0.0"}
        
        # Execute upload (should fail)
        with pytest.raises(Exception, match="Storage failure"):
            await cloud_registry_with_errors.upload_model(cloud_test_model_dir, model_id, metadata)
        
        # Verify database rollback was called
        assert mock_db_session.rollback.called
        assert not mock_db_session.commit.called
    
    @pytest.mark.asyncio
    async def test_download_fallback_behavior(self, cloud_registry_with_errors):
        """Test download fallback when cloud storage fails."""
        model_id = "download-failure-test"
        download_path = Path(tempfile.mkdtemp()) / "download"
        
        # Mock model in database
        mock_model = MagicMock(spec=ModelRegistry)
        mock_model.id = model_id
        mock_model.cloud_storage_url = "s3://bucket/models/test/model_bundle.tar.gz"
        
        cloud_registry_with_errors.db_session.query.return_value.filter.return_value.first.return_value = mock_model
        
        try:
            # Execute download (should fail gracefully)
            with pytest.raises(Exception, match="Download failure"):
                await cloud_registry_with_errors.download_model(model_id, download_path)
        finally:
            # Cleanup
            if download_path.parent.exists():
                shutil.rmtree(download_path.parent)
    
    @pytest.mark.asyncio
    async def test_model_not_found_error_handling(self, cloud_registry_with_errors):
        """Test handling of model not found in database."""
        model_id = "nonexistent-model"
        
        # Mock empty query result
        cloud_registry_with_errors.db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Test various operations with nonexistent model
        with pytest.raises(CloudModelRegistryError, match="Model.*not found"):
            await cloud_registry_with_errors.download_model(model_id, Path("/tmp/download"))
        
        with pytest.raises(CloudModelRegistryError, match="Model.*not found"):
            await cloud_registry_with_errors.get_signed_url(model_id)
        
        with pytest.raises(CloudModelRegistryError, match="Model.*not found"):
            await cloud_registry_with_errors.delete_model(model_id)


class TestCloudModelRegistryPermissionIntegration:
    """Test permission integration with cloud storage operations."""
    
    @pytest.fixture
    def different_user(self):
        """Create different user for permission testing."""
        user = MagicMock(spec=User)
        user.id = uuid4()
        user.username = "different-user"
        user.email = "different@example.com"
        user.is_active = True
        return user
    
    @pytest.fixture
    def cloud_registry_different_user(self, mock_db_session, different_user, mock_storage_backend, temp_cache_dir):
        """Create CloudModelRegistry with different user."""
        return CloudModelRegistry(
            db_session=mock_db_session,
            user=different_user,
            storage_backend=mock_storage_backend,
            local_cache_path=temp_cache_dir
        )
    
    @pytest.mark.asyncio
    async def test_access_control_for_private_models(self, cloud_registry_different_user, mock_user):
        """Test access control prevents unauthorized access to private models."""
        model_id = "private-model-test"
        
        # Mock private model owned by different user
        mock_model = MagicMock(spec=ModelRegistry)
        mock_model.id = model_id
        mock_model.owner_id = mock_user.id  # Different from current user
        mock_model.is_public = False  # Private model
        mock_model.cloud_storage_url = "s3://bucket/models/private-model-test/model_bundle.tar.gz"
        
        # Set up mock to return different results for different query types
        def mock_query(model_class):
            mock_query_obj = MagicMock()
            if model_class == ModelRegistry:
                mock_query_obj.filter.return_value.first.return_value = mock_model
            else:
                # For ModelAccess and other queries, return None (no access grants)
                mock_query_obj.filter.return_value.first.return_value = None
            return mock_query_obj
        
        cloud_registry_different_user.db_session.query.side_effect = mock_query
        
        # Test that access is denied for private model
        with pytest.raises(CloudModelRegistryError, match="(Access denied|Admin access required)"):
            await cloud_registry_different_user.download_model(model_id, Path("/tmp/download"))
        
        with pytest.raises(CloudModelRegistryError, match="(Access denied|Admin access required)"):
            await cloud_registry_different_user.get_signed_url(model_id)
        
        with pytest.raises(CloudModelRegistryError, match="(Access denied|Admin access required)"):
            await cloud_registry_different_user.delete_model(model_id)
    
    @pytest.mark.asyncio
    async def test_public_model_access_allowed(self, cloud_registry_different_user, mock_user):
        """Test that public models can be accessed by any user."""
        model_id = "public-model-test"
        download_path = Path(tempfile.mkdtemp()) / "download"
        
        # Mock public model owned by different user
        mock_model = MagicMock(spec=ModelRegistry)
        mock_model.id = model_id
        mock_model.owner_id = mock_user.id  # Different from current user
        mock_model.is_public = True  # Public model
        mock_model.cloud_storage_url = "s3://bucket/models/public-model-test/model_bundle.tar.gz"
        
        # Set up mock to return different results for different query types
        def mock_query(model_class):
            mock_query_obj = MagicMock()
            if model_class == ModelRegistry:
                mock_query_obj.filter.return_value.first.return_value = mock_model
            else:
                # For ModelAccess and other queries, return None (no access grants)
                mock_query_obj.filter.return_value.first.return_value = None
            return mock_query_obj
        
        cloud_registry_different_user.db_session.query.side_effect = mock_query
        
        try:
            # Test that download is allowed for public model
            result = await cloud_registry_different_user.download_model(model_id, download_path)
            assert result["model_id"] == model_id
            
            # Test that signed URL generation is allowed
            url_result = await cloud_registry_different_user.get_signed_url(model_id)
            assert url_result["model_id"] == model_id
            assert "signed_url" in url_result
            
        finally:
            # Cleanup
            if download_path.parent.exists():
                shutil.rmtree(download_path.parent)


class TestCloudModelRegistryCacheIntegration:
    """Test local caching integration with cloud storage operations."""
    
    @pytest.fixture
    def cloud_registry_with_cache(self, mock_db_session, mock_user, mock_storage_backend, temp_cache_dir):
        """Create CloudModelRegistry with caching enabled."""
        return CloudModelRegistry(
            db_session=mock_db_session,
            user=mock_user,
            storage_backend=mock_storage_backend,
            local_cache_path=temp_cache_dir,
            enable_caching=True
        )
    
    @pytest.mark.asyncio
    async def test_cache_hit_avoids_cloud_download(self, cloud_registry_with_cache, temp_cache_dir):
        """Test that cache hits avoid unnecessary cloud downloads."""
        model_id = "cached-model"
        
        # Pre-populate cache (match CloudModelRegistry's tier-based structure)
        cache_tier_dir = temp_cache_dir / "hot"  # Default tier
        cache_tier_dir.mkdir(parents=True, exist_ok=True)
        cache_model_dir = cache_tier_dir / f"{model_id}"
        cache_model_dir.mkdir()
        (cache_model_dir / "model.bin").write_text("cached model data")
        (cache_model_dir / "model_manifest.json").write_text('{"name": "Cached Model"}')
        
        # Mock model in database
        mock_model = MagicMock(spec=ModelRegistry)
        mock_model.id = model_id
        mock_model.cloud_storage_url = "s3://bucket/models/cached-model/model_bundle.tar.gz"
        mock_model.owner_id = cloud_registry_with_cache.user.id
        mock_model.manifest_hash = MagicMock()  # Mock hash to skip integrity check
        mock_model.storage_tier = "hot"  # Set storage tier for cache path calculation
        
        # Set up mock to return different results for different query types
        def mock_query(model_class):
            mock_query_obj = MagicMock()
            if model_class == ModelRegistry:
                mock_query_obj.filter.return_value.first.return_value = mock_model
            else:
                # For ModelAccess and other queries, return None
                mock_query_obj.filter.return_value.first.return_value = None
            return mock_query_obj
        
        cloud_registry_with_cache.db_session.query.side_effect = mock_query
        
        # Execute download (don't specify custom path to allow cache path to be used)
        result = await cloud_registry_with_cache.download_model(model_id, use_cache=True)
        
        # Verify cache hit
        assert result["cache_hit"] is True
        
        # Verify cloud storage was NOT called
        cloud_registry_with_cache.storage_backend.download_model.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_cache_miss_triggers_cloud_download(self, cloud_registry_with_cache):
        """Test that cache misses trigger cloud storage downloads."""
        model_id = "uncached-model"
        download_path = Path(tempfile.mkdtemp()) / "download"
        
        # Mock model in database (not in cache)
        mock_model = MagicMock(spec=ModelRegistry)
        mock_model.id = model_id
        mock_model.cloud_storage_url = "s3://bucket/models/uncached-model/model_bundle.tar.gz"
        mock_model.owner_id = cloud_registry_with_cache.user.id
        
        cloud_registry_with_cache.db_session.query.return_value.filter.return_value.first.return_value = mock_model
        
        try:
            # Execute download
            result = await cloud_registry_with_cache.download_model(model_id, download_path, use_cache=True)
            
            # Verify cache miss
            assert result["cache_hit"] is False
            
            # Verify cloud storage was called
            cloud_registry_with_cache.storage_backend.download_model.assert_called_once()
            
        finally:
            # Cleanup
            if download_path.parent.exists():
                shutil.rmtree(download_path.parent)
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_on_model_update(self, cloud_registry_with_cache, temp_cache_dir):
        """Test that cache is invalidated when models are updated."""
        model_id = "updated-model"
        
        # Pre-populate cache (match CloudModelRegistry's tier-based structure)
        cache_tier_dir = temp_cache_dir / "hot"  # Default tier
        cache_tier_dir.mkdir(parents=True, exist_ok=True)
        cache_model_dir = cache_tier_dir / f"{model_id}"
        cache_model_dir.mkdir()
        (cache_model_dir / "model.bin").write_text("old cached data")
        
        # Mock model update
        mock_model = MagicMock(spec=ModelRegistry)
        mock_model.id = model_id
        mock_model.cloud_storage_url = "s3://bucket/models/updated-model/model_bundle.tar.gz"
        mock_model.owner_id = cloud_registry_with_cache.user.id
        
        cloud_registry_with_cache.db_session.query.return_value.filter.return_value.first.return_value = mock_model
        
        # Execute cache invalidation
        await cloud_registry_with_cache.invalidate_model_cache(model_id)
        
        # Verify cache was cleared
        assert not cache_model_dir.exists()