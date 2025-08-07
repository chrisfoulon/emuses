"""Tests for DatabaseModelRegistry.

This module tests database-backed model registry operations
including model registration, querying, permissions, and storage coordination.
"""

import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from emuses.multi_user_service.models import Base, ModelRegistry, User, Workspace
from emuses.tools.database_model_registry import DatabaseModelRegistry


@pytest.fixture
def test_db():
    """Create test database with tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()


@pytest.fixture
def test_user(test_db):
    """Create test user."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password="hashed_password",
        organization="Test Org",
        role="researcher",
        storage_quota_gb=10.0,
        compute_quota_hours=100.0,
        is_active=True,
        is_superuser=False,
        is_verified=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def test_workspace(test_db, test_user):
    """Create test workspace."""
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Test Workspace",
        description="Test workspace for model registry",
        owner_id=test_user.id,
        storage_path="/tmp/test_workspace",
        is_active=True
    )
    test_db.add(workspace)
    test_db.commit()
    return workspace


@pytest.fixture
def database_registry(test_db, test_user):
    """Create DatabaseModelRegistry instance for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        registry = DatabaseModelRegistry(
            db_session=test_db,
            current_user=test_user,
            base_path=Path(temp_dir)
        )
        yield registry


@pytest.fixture
def sample_model_manifest():
    """Create sample model manifest."""
    return {
        "name": "test_model",
        "version": "1.0.0",
        "model_type": "classification",
        "description": "Test classification model",
        "tags": ["test", "classification"],
        "created_at": "2025-08-07T00:00:00Z"
    }


class TestDatabaseModelRegistryInitialization:
    """Test DatabaseModelRegistry initialization and setup."""
    
    def test_initialization_with_defaults(self, test_db, test_user):
        """Test registry initialization with default parameters."""
        registry = DatabaseModelRegistry(test_db, test_user)
        
        assert registry.db_session == test_db
        assert registry.current_user == test_user
        assert registry.base_path == Path("/shared/emuses/models")
    
    def test_initialization_with_custom_path(self, test_db, test_user):
        """Test registry initialization with custom base path."""
        custom_path = Path("/custom/model/path")
        registry = DatabaseModelRegistry(test_db, test_user, base_path=custom_path)
        
        assert registry.base_path == custom_path
    
    def test_directory_creation(self, test_db, test_user):
        """Test that required directories are created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir) / "test_registry"
            registry = DatabaseModelRegistry(test_db, test_user, base_path=base_path)
            
            assert registry.base_path.exists()
            assert registry.public_path.exists()
            assert registry.temp_path.exists()


class TestDatabaseModelRegistryRegistration:
    """Test model registration operations."""
    
    @patch('emuses.tools.database_model_registry.ModelIOManager')
    def test_register_model_success(self, mock_manager_class, database_registry, sample_model_manifest):
        """Test successful model registration."""
        # Setup mock
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        mock_manifest = Mock()
        mock_manifest.name = sample_model_manifest["name"]
        mock_manifest.version = sample_model_manifest["version"]
        mock_manifest.model_type = sample_model_manifest["model_type"]
        mock_manager.load_manifest.return_value = mock_manifest
        
        # Create temporary model directory
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "test_model"
            model_path.mkdir()
            
            # Create manifest file
            manifest_path = model_path / "model_manifest.json"
            with open(manifest_path, 'w') as f:
                json.dump(sample_model_manifest, f)
            
            # Register model
            result = database_registry.register_model(
                model_path=model_path,
                name="custom_name",
                description="Custom description",
                tags=["custom", "tag"]
            )
        
        assert result["status"] == "success"
        assert result["name"] == "custom_name"
        assert "model_id" in result
        assert "storage_path" in result
    
    @patch('emuses.tools.database_model_registry.ModelIOManager')
    def test_register_model_validation_error(self, mock_manager_class, database_registry):
        """Test model registration with validation error."""
        # Setup mock to raise exception
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        mock_manager.load_manifest.side_effect = ValueError("Invalid manifest")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "invalid_model"
            model_path.mkdir()
            
            result = database_registry.register_model(model_path=model_path)
        
        assert result["status"] == "error"
        assert "Invalid model manifest" in result["message"]
        assert result["error_type"] == "validation_error"
    
    @patch('emuses.tools.database_model_registry.ModelIOManager')
    def test_register_model_with_workspace(self, mock_manager_class, database_registry, test_workspace, sample_model_manifest):
        """Test model registration with workspace assignment."""
        # Setup mock
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        mock_manifest = Mock()
        mock_manifest.name = sample_model_manifest["name"]
        mock_manifest.version = sample_model_manifest["version"]
        mock_manifest.model_type = sample_model_manifest["model_type"]
        mock_manager.load_manifest.return_value = mock_manifest
        
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "test_model"
            model_path.mkdir()
            
            result = database_registry.register_model(
                model_path=model_path,
                workspace_id=str(test_workspace.id)
            )
        
        assert result["status"] == "success"
    
    def test_register_model_invalid_workspace(self, database_registry):
        """Test model registration with invalid workspace ID."""
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "test_model"
            model_path.mkdir()
            
            invalid_workspace_id = str(uuid.uuid4())
            result = database_registry.register_model(
                model_path=model_path,
                workspace_id=invalid_workspace_id
            )
        
        assert result["status"] == "error"
        assert "not found or not accessible" in result["message"]
        assert result["error_type"] == "permission_error"


class TestDatabaseModelRegistryQuerying:
    """Test model querying and discovery operations."""
    
    def test_list_models_empty_registry(self, database_registry):
        """Test listing models from empty registry."""
        models = database_registry.list_models()
        assert models == []
    
    def test_list_models_with_user_models(self, database_registry, test_db, test_user):
        """Test listing models owned by current user."""
        # Create test model in database
        model = ModelRegistry(
            id=uuid.uuid4(),
            name="test_model",
            version="1.0.0",
            owner_id=test_user.id,
            model_path="/fake/path",
            manifest_hash="fake_hash",
            model_type="classification"
        )
        test_db.add(model)
        test_db.commit()
        
        models = database_registry.list_models()
        assert len(models) == 1
        assert models[0]["name"] == "test_model"
        assert models[0]["model_id"] == str(model.id)
    
    def test_list_models_with_filters(self, database_registry, test_db, test_user):
        """Test listing models with type and tag filters."""
        # Create test models
        model1 = ModelRegistry(
            id=uuid.uuid4(),
            name="classification_model",
            version="1.0.0",
            owner_id=test_user.id,
            model_path="/fake/path1",
            manifest_hash="hash1",
            model_type="classification",
            tags=["nlp", "sentiment"]
        )
        
        model2 = ModelRegistry(
            id=uuid.uuid4(),
            name="regression_model",
            version="1.0.0",
            owner_id=test_user.id,
            model_path="/fake/path2",
            manifest_hash="hash2",
            model_type="regression",
            tags=["numerical", "prediction"]
        )
        
        test_db.add_all([model1, model2])
        test_db.commit()
        
        # Test type filter
        models = database_registry.list_models(filters={"type": "classification"})
        assert len(models) == 1
        assert models[0]["name"] == "classification_model"
        
        # Test tag filter
        models = database_registry.list_models(filters={"tags": ["nlp"]})
        assert len(models) == 1
        assert models[0]["name"] == "classification_model"
    
    def test_get_model_info_success(self, database_registry, test_db, test_user):
        """Test retrieving detailed model information."""
        model = ModelRegistry(
            id=uuid.uuid4(),
            name="detailed_model",
            version="2.0.0",
            owner_id=test_user.id,
            model_path="/fake/path",
            manifest_hash="detailed_hash",
            model_type="classification",
            description="Detailed test model",
            tags=["test", "detailed"],
            download_count=5,
            model_size_bytes=1024*1024  # 1MB
        )
        test_db.add(model)
        test_db.commit()
        
        info = database_registry.get_model_info(str(model.id))
        
        assert info is not None
        assert info["model_id"] == str(model.id)
        assert info["name"] == "detailed_model"
        assert info["description"] == "Detailed test model"
        assert info["download_count"] == 5
        assert info["size_mb"] == 1.0
    
    def test_get_model_info_not_found(self, database_registry):
        """Test retrieving info for non-existent model."""
        fake_id = str(uuid.uuid4())
        info = database_registry.get_model_info(fake_id)
        assert info is None
    
    def test_search_models_by_name(self, database_registry, test_db, test_user):
        """Test searching models by name."""
        model = ModelRegistry(
            id=uuid.uuid4(),
            name="searchable_model",
            version="1.0.0",
            owner_id=test_user.id,
            model_path="/fake/path",
            manifest_hash="search_hash",
            model_type="classification"
        )
        test_db.add(model)
        test_db.commit()
        
        results = database_registry.search_models("searchable")
        assert len(results) == 1
        assert results[0]["name"] == "searchable_model"
    
    def test_search_models_empty_query(self, database_registry, test_db, test_user):
        """Test search with empty query returns all models."""
        model = ModelRegistry(
            id=uuid.uuid4(),
            name="any_model",
            version="1.0.0",
            owner_id=test_user.id,
            model_path="/fake/path",
            manifest_hash="any_hash",
            model_type="classification"
        )
        test_db.add(model)
        test_db.commit()
        
        results = database_registry.search_models("")
        assert len(results) == 1


class TestDatabaseModelRegistryManagement:
    """Test model management operations."""
    
    def test_remove_model_success(self, database_registry, test_db, test_user):
        """Test successful model removal."""
        model = ModelRegistry(
            id=uuid.uuid4(),
            name="removable_model",
            version="1.0.0",
            owner_id=test_user.id,
            model_path="/fake/path",
            manifest_hash="remove_hash",
            model_type="classification"
        )
        test_db.add(model)
        test_db.commit()
        model_id = str(model.id)
        
        result = database_registry.remove_model(model_id, cleanup_files=False)
        
        assert result["status"] == "success"
        assert "removed successfully" in result["message"]
        
        # Verify model is removed from database
        remaining_model = test_db.query(ModelRegistry).filter_by(id=model.id).first()
        assert remaining_model is None
    
    def test_remove_model_not_found(self, database_registry):
        """Test removing non-existent model."""
        fake_id = str(uuid.uuid4())
        result = database_registry.remove_model(fake_id)
        
        assert result["status"] == "error"
        assert "not found" in result["message"]
    
    def test_remove_model_permission_denied(self, database_registry, test_db):
        """Test removing model owned by different user."""
        # Create different user
        other_user = User(
            id=uuid.uuid4(),
            email="other@example.com",
            hashed_password="hashed_password",
            organization="Other Org",
            role="researcher",
            is_active=True,
            is_superuser=False,
            is_verified=True
        )
        test_db.add(other_user)
        
        # Create model owned by other user
        model = ModelRegistry(
            id=uuid.uuid4(),
            name="other_model",
            version="1.0.0",
            owner_id=other_user.id,
            model_path="/fake/path",
            manifest_hash="other_hash",
            model_type="classification"
        )
        test_db.add(model)
        test_db.commit()
        
        result = database_registry.remove_model(str(model.id))
        
        assert result["status"] == "error"
        assert "Permission denied" in result["message"]
    
    def test_track_download(self, database_registry, test_db, test_user):
        """Test download tracking."""
        model = ModelRegistry(
            id=uuid.uuid4(),
            name="downloadable_model",
            version="1.0.0",
            owner_id=test_user.id,
            model_path="/fake/path",
            manifest_hash="download_hash",
            model_type="classification",
            download_count=0
        )
        test_db.add(model)
        test_db.commit()
        
        result = database_registry.track_download(
            str(model.id),
            download_method="api",
            user_agent="test-agent"
        )
        
        assert result["status"] == "success"
        assert "download_id" in result
        
        # Verify download count updated
        test_db.refresh(model)
        assert model.download_count == 1
    
    def test_get_registry_stats(self, database_registry, test_db, test_user):
        """Test registry statistics calculation."""
        # Create test models
        model1 = ModelRegistry(
            id=uuid.uuid4(),
            name="stats_model_1",
            version="1.0.0",
            owner_id=test_user.id,
            model_path="/fake/path1",
            manifest_hash="stats_hash1",
            model_type="classification",
            model_size_bytes=1024*1024,  # 1MB
            download_count=3
        )
        
        model2 = ModelRegistry(
            id=uuid.uuid4(),
            name="stats_model_2",
            version="1.0.0",
            owner_id=test_user.id,
            model_path="/fake/path2",
            manifest_hash="stats_hash2",
            model_type="regression",
            model_size_bytes=2*1024*1024,  # 2MB
            download_count=5
        )
        
        test_db.add_all([model1, model2])
        test_db.commit()
        
        stats = database_registry.get_registry_stats()
        
        assert stats["user_models"] == 2
        assert stats["accessible_models"] == 2
        assert stats["storage_usage_bytes"] == 3*1024*1024  # 3MB
        assert stats["storage_usage_mb"] == 3.0
        assert stats["total_downloads"] == 8
        assert "classification" in stats["model_types"]
        assert "regression" in stats["model_types"]
        assert stats["model_types"]["classification"] == 1
        assert stats["model_types"]["regression"] == 1


class TestDatabaseModelRegistryPermissions:
    """Test permission-related operations."""
    
    def test_check_model_access_owner(self, database_registry, test_db, test_user):
        """Test access check for model owner."""
        model = ModelRegistry(
            id=uuid.uuid4(),
            name="owner_model",
            version="1.0.0",
            owner_id=test_user.id,
            model_path="/fake/path",
            manifest_hash="owner_hash",
            model_type="classification"
        )
        test_db.add(model)
        test_db.commit()
        
        # Owner should have access
        assert database_registry._check_model_access(model, "read") == True
        assert database_registry._check_model_access(model, "write") == True
        assert database_registry._check_model_access(model, "admin") == True
        assert database_registry._check_model_access(model, "owner") == True
    
    def test_check_model_access_public(self, database_registry, test_db):
        """Test access check for public model."""
        # Create different user as owner
        other_user = User(
            id=uuid.uuid4(),
            email="other@example.com",
            hashed_password="hashed_password",
            organization="Other Org",
            role="researcher",
            is_active=True,
            is_superuser=False,
            is_verified=True
        )
        test_db.add(other_user)
        
        model = ModelRegistry(
            id=uuid.uuid4(),
            name="public_model",
            version="1.0.0",
            owner_id=other_user.id,
            model_path="/fake/path",
            manifest_hash="public_hash",
            model_type="classification",
            is_public=True
        )
        test_db.add(model)
        test_db.commit()
        
        # Should have read access to public model
        assert database_registry._check_model_access(model, "read") == True
        # Should not have write access
        assert database_registry._check_model_access(model, "write") == False
    
    def test_check_model_access_workspace(self, database_registry, test_db, test_user, test_workspace):
        """Test access check for workspace model."""
        # Create different user as model owner
        other_user = User(
            id=uuid.uuid4(),
            email="other@example.com",
            hashed_password="hashed_password",
            organization="Other Org",
            role="researcher",
            is_active=True,
            is_superuser=False,
            is_verified=True
        )
        test_db.add(other_user)
        
        model = ModelRegistry(
            id=uuid.uuid4(),
            name="workspace_model",
            version="1.0.0",
            owner_id=other_user.id,
            workspace_id=test_workspace.id,
            model_path="/fake/path",
            manifest_hash="workspace_hash",
            model_type="classification"
        )
        test_db.add(model)
        test_db.commit()
        
        # Workspace owner should have admin access
        assert database_registry._check_model_access(model, "read") == True
        assert database_registry._check_model_access(model, "write") == True
        assert database_registry._check_model_access(model, "admin") == True
    
    def test_calculate_manifest_hash(self, database_registry):
        """Test manifest hash calculation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir)
            manifest_path = model_path / "model_manifest.json"
            
            # Test with no manifest
            hash_result = database_registry._calculate_manifest_hash(model_path)
            assert hash_result == "no-manifest"
            
            # Test with manifest
            manifest_data = {"name": "test", "version": "1.0.0"}
            with open(manifest_path, 'w') as f:
                json.dump(manifest_data, f)
            
            hash_result = database_registry._calculate_manifest_hash(model_path)
            assert len(hash_result) == 64  # SHA-256 hex length
            assert hash_result != "no-manifest"
    
    def test_calculate_directory_size(self, database_registry):
        """Test directory size calculation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir)
            
            # Empty directory
            size = database_registry._calculate_directory_size(model_path)
            assert size == 0
            
            # Directory with files
            (model_path / "file1.txt").write_text("hello")
            (model_path / "file2.txt").write_text("world")
            
            size = database_registry._calculate_directory_size(model_path)
            assert size == 10  # "hello" + "world" = 10 bytes
            
            # Non-existent directory
            fake_path = Path("/fake/nonexistent/path")
            size = database_registry._calculate_directory_size(fake_path)
            assert size == 0