"""Tests for ModelPermissionManager.

This module tests multi-user access control for model registry
including permission granting, revocation, and validation.
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from emuses.multi_user_service.models import Base, ModelAccess, ModelRegistry, User, Workspace
from emuses.tools.model_permission_manager import ModelPermissionManager


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
    """Create test user (current user)."""
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
def other_user(test_db):
    """Create another test user."""
    user = User(
        id=uuid.uuid4(),
        email="other@example.com",
        hashed_password="hashed_password",
        organization="Other Org",
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
def third_user(test_db):
    """Create third test user."""
    user = User(
        id=uuid.uuid4(),
        email="third@example.com",
        hashed_password="hashed_password",
        organization="Third Org",
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
        description="Test workspace for permissions",
        owner_id=test_user.id,
        storage_path="/tmp/test_workspace",
        is_active=True
    )
    test_db.add(workspace)
    test_db.commit()
    return workspace


@pytest.fixture
def test_model(test_db, test_user):
    """Create test model owned by test_user."""
    model = ModelRegistry(
        id=uuid.uuid4(),
        name="test_model",
        version="1.0.0",
        owner_id=test_user.id,
        model_path="/fake/path",
        manifest_hash="test_hash",
        model_type="classification"
    )
    test_db.add(model)
    test_db.commit()
    return model


@pytest.fixture
def public_model(test_db, other_user):
    """Create public model owned by other_user."""
    model = ModelRegistry(
        id=uuid.uuid4(),
        name="public_model",
        version="1.0.0",
        owner_id=other_user.id,
        model_path="/fake/public_path",
        manifest_hash="public_hash",
        model_type="classification",
        is_public=True
    )
    test_db.add(model)
    test_db.commit()
    return model


@pytest.fixture
def workspace_model(test_db, other_user, test_workspace):
    """Create model in test workspace."""
    model = ModelRegistry(
        id=uuid.uuid4(),
        name="workspace_model",
        version="1.0.0",
        owner_id=other_user.id,
        workspace_id=test_workspace.id,
        model_path="/fake/workspace_path",
        manifest_hash="workspace_hash",
        model_type="classification"
    )
    test_db.add(model)
    test_db.commit()
    return model


@pytest.fixture
def permission_manager(test_db, test_user):
    """Create ModelPermissionManager instance."""
    return ModelPermissionManager(test_db, test_user)


class TestPermissionManagerInitialization:
    """Test ModelPermissionManager initialization."""
    
    def test_initialization(self, test_db, test_user):
        """Test permission manager initialization."""
        manager = ModelPermissionManager(test_db, test_user)
        
        assert manager.db_session == test_db
        assert manager.current_user == test_user
    
    def test_access_levels_definition(self, permission_manager):
        """Test access levels are properly defined."""
        expected_levels = ["read", "write", "admin", "owner"]
        assert permission_manager.ACCESS_LEVELS == expected_levels


class TestAccessChecking:
    """Test access permission checking functionality."""
    
    def test_check_access_owner(self, permission_manager, test_model):
        """Test access check for model owner."""
        model_id = str(test_model.id)
        
        # Owner should have all access levels
        assert permission_manager.check_access(model_id, "read") == True
        assert permission_manager.check_access(model_id, "write") == True
        assert permission_manager.check_access(model_id, "admin") == True
        assert permission_manager.check_access(model_id, "owner") == True
    
    def test_check_access_public_model(self, permission_manager, public_model):
        """Test access check for public model."""
        model_id = str(public_model.id)
        
        # Should have read access to public model
        assert permission_manager.check_access(model_id, "read") == True
        # Should not have higher access levels
        assert permission_manager.check_access(model_id, "write") == False
        assert permission_manager.check_access(model_id, "admin") == False
        assert permission_manager.check_access(model_id, "owner") == False
    
    def test_check_access_workspace_model(self, permission_manager, workspace_model):
        """Test access check for model in user's workspace."""
        model_id = str(workspace_model.id)
        
        # Workspace owner should have admin access
        assert permission_manager.check_access(model_id, "read") == True
        assert permission_manager.check_access(model_id, "write") == True
        assert permission_manager.check_access(model_id, "admin") == True
        assert permission_manager.check_access(model_id, "owner") == False
    
    def test_check_access_nonexistent_model(self, permission_manager):
        """Test access check for non-existent model."""
        fake_id = str(uuid.uuid4())
        assert permission_manager.check_access(fake_id, "read") == False
    
    def test_check_access_with_explicit_grant(self, permission_manager, test_db, public_model, test_user):
        """Test access check with explicit permission grant."""
        model_id = str(public_model.id)
        
        # Create explicit access grant
        access_grant = ModelAccess(
            model_id=public_model.id,
            user_id=test_user.id,
            access_level="write",
            granted_by_id=public_model.owner_id
        )
        test_db.add(access_grant)
        test_db.commit()
        
        # Should now have write access
        assert permission_manager.check_access(model_id, "read") == True
        assert permission_manager.check_access(model_id, "write") == True
        assert permission_manager.check_access(model_id, "admin") == False
    
    def test_check_access_expired_grant(self, permission_manager, test_db, public_model, test_user):
        """Test access check with expired permission grant."""
        model_id = str(public_model.id)
        
        # Create expired access grant
        expired_time = datetime.utcnow() - timedelta(hours=1)
        access_grant = ModelAccess(
            model_id=public_model.id,
            user_id=test_user.id,
            access_level="write",
            granted_by_id=public_model.owner_id,
            expires_at=expired_time
        )
        test_db.add(access_grant)
        test_db.commit()
        
        # Should not have write access (expired)
        assert permission_manager.check_access(model_id, "read") == True  # Public access
        assert permission_manager.check_access(model_id, "write") == False  # Expired grant
    
    def test_check_access_different_user(self, permission_manager, test_db, public_model, third_user):
        """Test access check for different user."""
        model_id = str(public_model.id)
        user_id = str(third_user.id)
        
        # Third user should have read access to public model
        assert permission_manager.check_access(model_id, "read", user_id) == True
        assert permission_manager.check_access(model_id, "write", user_id) == False


class TestAccessGranting:
    """Test access permission granting functionality."""
    
    def test_grant_access_success(self, permission_manager, test_model, other_user):
        """Test successful access granting."""
        model_id = str(test_model.id)
        user_id = str(other_user.id)
        
        result = permission_manager.grant_access(
            model_id=model_id,
            user_id=user_id,
            access_level="write"
        )
        
        assert result["status"] == "success"
        assert "granted" in result["message"]
        assert result["action"] == "granted"
        
        # Verify access was granted
        assert permission_manager.check_access(model_id, "write", user_id) == True
    
    def test_grant_access_invalid_level(self, permission_manager, test_model, other_user):
        """Test granting invalid access level."""
        model_id = str(test_model.id)
        user_id = str(other_user.id)
        
        result = permission_manager.grant_access(
            model_id=model_id,
            user_id=user_id,
            access_level="invalid_level"
        )
        
        assert result["status"] == "error"
        assert "Invalid access level" in result["message"]
    
    def test_grant_access_owner_level(self, permission_manager, test_model, other_user):
        """Test attempting to grant owner access level."""
        model_id = str(test_model.id)
        user_id = str(other_user.id)
        
        result = permission_manager.grant_access(
            model_id=model_id,
            user_id=user_id,
            access_level="owner"
        )
        
        assert result["status"] == "error"
        assert "Cannot grant owner access level" in result["message"]
    
    def test_grant_access_nonexistent_model(self, permission_manager, other_user):
        """Test granting access to non-existent model."""
        fake_model_id = str(uuid.uuid4())
        user_id = str(other_user.id)
        
        result = permission_manager.grant_access(
            model_id=fake_model_id,
            user_id=user_id,
            access_level="read"
        )
        
        assert result["status"] == "error"
        assert "not found" in result["message"]
    
    def test_grant_access_nonexistent_user(self, permission_manager, test_model):
        """Test granting access to non-existent user."""
        model_id = str(test_model.id)
        fake_user_id = str(uuid.uuid4())
        
        result = permission_manager.grant_access(
            model_id=model_id,
            user_id=fake_user_id,
            access_level="read"
        )
        
        assert result["status"] == "error"
        assert "not found" in result["message"]
    
    def test_grant_access_permission_denied(self, test_db, other_user, third_user, test_model):
        """Test granting access without admin permissions."""
        # Create permission manager for other_user (not owner of test_model)
        manager = ModelPermissionManager(test_db, other_user)
        
        model_id = str(test_model.id)
        user_id = str(third_user.id)
        
        result = manager.grant_access(
            model_id=model_id,
            user_id=user_id,
            access_level="read"
        )
        
        assert result["status"] == "error"
        assert "Permission denied" in result["message"]
    
    def test_grant_access_with_expiration(self, permission_manager, test_model, other_user):
        """Test granting access with expiration time."""
        model_id = str(test_model.id)
        user_id = str(other_user.id)
        expires_at = datetime.utcnow() + timedelta(days=1)
        
        result = permission_manager.grant_access(
            model_id=model_id,
            user_id=user_id,
            access_level="read",
            expires_at=expires_at
        )
        
        assert result["status"] == "success"
        
        # Verify access exists and has expiration
        assert permission_manager.check_access(model_id, "read", user_id) == True
    
    def test_update_existing_grant(self, permission_manager, test_db, test_model, other_user):
        """Test updating existing access grant."""
        model_id = str(test_model.id)
        user_id = str(other_user.id)
        
        # First grant read access
        result1 = permission_manager.grant_access(model_id, user_id, "read")
        assert result1["status"] == "success"
        assert result1["action"] == "granted"
        
        # Then update to write access
        result2 = permission_manager.grant_access(model_id, user_id, "write")
        assert result2["status"] == "success"
        assert result2["action"] == "updated"
        
        # Verify updated access
        assert permission_manager.check_access(model_id, "write", user_id) == True


class TestAccessRevoking:
    """Test access permission revoking functionality."""
    
    def test_revoke_access_success(self, permission_manager, test_db, test_model, other_user):
        """Test successful access revocation."""
        model_id = str(test_model.id)
        user_id = str(other_user.id)
        
        # First grant access
        permission_manager.grant_access(model_id, user_id, "write")
        assert permission_manager.check_access(model_id, "write", user_id) == True
        
        # Then revoke access
        result = permission_manager.revoke_access(model_id, user_id)
        
        assert result["status"] == "success"
        assert "revoked" in result["message"]
        
        # Verify access was revoked
        assert permission_manager.check_access(model_id, "write", user_id) == False
    
    def test_revoke_access_nonexistent_model(self, permission_manager, other_user):
        """Test revoking access from non-existent model."""
        fake_model_id = str(uuid.uuid4())
        user_id = str(other_user.id)
        
        result = permission_manager.revoke_access(fake_model_id, user_id)
        
        assert result["status"] == "error"
        assert "not found" in result["message"]
    
    def test_revoke_access_from_owner(self, permission_manager, test_model, test_user):
        """Test attempting to revoke access from model owner."""
        model_id = str(test_model.id)
        user_id = str(test_user.id)  # Owner
        
        result = permission_manager.revoke_access(model_id, user_id)
        
        assert result["status"] == "error"
        assert "Cannot revoke access from model owner" in result["message"]
    
    def test_revoke_access_no_grant_exists(self, permission_manager, test_model, other_user):
        """Test revoking access when no explicit grant exists."""
        model_id = str(test_model.id)
        user_id = str(other_user.id)
        
        result = permission_manager.revoke_access(model_id, user_id)
        
        assert result["status"] == "error"
        assert "No explicit access grant found" in result["message"]
    
    def test_revoke_access_permission_denied(self, test_db, other_user, third_user, test_model):
        """Test revoking access without admin permissions."""
        # Create permission manager for other_user (not owner or admin of test_model)
        manager = ModelPermissionManager(test_db, other_user)
        
        model_id = str(test_model.id)
        user_id = str(third_user.id)
        
        result = manager.revoke_access(model_id, user_id)
        
        assert result["status"] == "error"
        assert "Permission denied" in result["message"]


class TestPermissionListing:
    """Test permission listing functionality."""
    
    def test_list_permissions_owner_only(self, permission_manager, test_model):
        """Test listing permissions for model with only owner."""
        model_id = str(test_model.id)
        
        result = permission_manager.list_permissions(model_id)
        
        assert result["status"] == "success"
        assert len(result["permissions"]) == 1
        
        owner_perm = result["permissions"][0]
        assert owner_perm["access_level"] == "owner"
        assert owner_perm["is_owner"] == True
        assert owner_perm["user_email"] == "test@example.com"
    
    def test_list_permissions_with_explicit_grants(self, permission_manager, test_db, test_model, other_user):
        """Test listing permissions including explicit grants."""
        model_id = str(test_model.id)
        
        # Grant access to other user
        grant_result = permission_manager.grant_access(model_id, str(other_user.id), "write")
        
        result = permission_manager.list_permissions(model_id)
        
        assert result["status"] == "success"
        assert len(result["permissions"]) == 2
        
        # Find owner and granted permissions
        owner_perm = next(p for p in result["permissions"] if p["access_level"] == "owner")
        granted_perm = next(p for p in result["permissions"] if p["access_level"] == "write")
        
        assert owner_perm["user_email"] == "test@example.com"
        assert granted_perm["user_email"] == "other@example.com"
        assert granted_perm["is_explicit"] == True
    
    def test_list_permissions_workspace_model(self, permission_manager, workspace_model):
        """Test listing permissions for workspace model."""
        model_id = str(workspace_model.id)
        
        result = permission_manager.list_permissions(model_id)
        
        assert result["status"] == "success"
        assert len(result["permissions"]) >= 2  # Owner + workspace owner
        
        # Should include workspace owner with admin access
        workspace_perm = next(
            (p for p in result["permissions"] if p.get("is_workspace_owner")), 
            None
        )
        assert workspace_perm is not None
        assert workspace_perm["access_level"] == "admin"
    
    def test_list_permissions_nonexistent_model(self, permission_manager):
        """Test listing permissions for non-existent model."""
        fake_model_id = str(uuid.uuid4())
        
        result = permission_manager.list_permissions(fake_model_id)
        
        assert result["status"] == "error"
        assert "not found" in result["message"]
    
    def test_list_permissions_no_access(self, test_db, other_user, test_model):
        """Test listing permissions without access to model."""
        # Create permission manager for other_user (no access to private model)
        manager = ModelPermissionManager(test_db, other_user)
        model_id = str(test_model.id)
        
        result = manager.list_permissions(model_id)
        
        assert result["status"] == "error"
        assert "Permission denied" in result["message"]


class TestOwnershipTransfer:
    """Test model ownership transfer functionality."""
    
    def test_transfer_ownership_success(self, permission_manager, test_db, test_model, other_user):
        """Test successful ownership transfer."""
        model_id = str(test_model.id)
        new_owner_id = str(other_user.id)
        old_owner_id = str(test_model.owner_id)
        
        result = permission_manager.transfer_ownership(model_id, new_owner_id)
        
        assert result["status"] == "success"
        assert "transferred" in result["message"]
        assert result["new_owner"] == "other@example.com"
        
        # Verify ownership was transferred in database
        test_db.refresh(test_model)
        assert str(test_model.owner_id) == new_owner_id
    
    def test_transfer_ownership_nonexistent_model(self, permission_manager, other_user):
        """Test transferring ownership of non-existent model."""
        fake_model_id = str(uuid.uuid4())
        new_owner_id = str(other_user.id)
        
        result = permission_manager.transfer_ownership(fake_model_id, new_owner_id)
        
        assert result["status"] == "error"
        assert "not found" in result["message"]
    
    def test_transfer_ownership_nonexistent_user(self, permission_manager, test_model):
        """Test transferring ownership to non-existent user."""
        model_id = str(test_model.id)
        fake_user_id = str(uuid.uuid4())
        
        result = permission_manager.transfer_ownership(model_id, fake_user_id)
        
        assert result["status"] == "error"
        assert "not found" in result["message"]
    
    def test_transfer_ownership_same_user(self, permission_manager, test_model, test_user):
        """Test transferring ownership to same user."""
        model_id = str(test_model.id)
        same_user_id = str(test_user.id)
        
        result = permission_manager.transfer_ownership(model_id, same_user_id)
        
        assert result["status"] == "error"
        assert "Cannot transfer ownership to current owner" in result["message"]
    
    def test_transfer_ownership_permission_denied(self, test_db, other_user, test_model, third_user):
        """Test transferring ownership without owner permissions."""
        # Create permission manager for other_user (not owner)
        manager = ModelPermissionManager(test_db, other_user)
        
        model_id = str(test_model.id)
        new_owner_id = str(third_user.id)
        
        result = manager.transfer_ownership(model_id, new_owner_id)
        
        assert result["status"] == "error"
        assert "Permission denied" in result["message"]
    
    def test_transfer_ownership_removes_explicit_grant(self, permission_manager, test_db, test_model, other_user, third_user):
        """Test that transferring ownership removes explicit grants for new owner."""
        model_id = str(test_model.id)
        new_owner_id = str(other_user.id)
        
        # First grant explicit access to future owner
        permission_manager.grant_access(model_id, new_owner_id, "write")
        
        # Verify explicit grant exists
        grant = test_db.query(ModelAccess).filter_by(
            model_id=test_model.id,
            user_id=other_user.id
        ).first()
        assert grant is not None
        
        # Transfer ownership
        result = permission_manager.transfer_ownership(model_id, new_owner_id)
        assert result["status"] == "success"
        
        # Verify explicit grant was removed
        grant = test_db.query(ModelAccess).filter_by(
            model_id=test_model.id,
            user_id=other_user.id
        ).first()
        assert grant is None


class TestPublicStatusManagement:
    """Test public status management functionality."""
    
    def test_make_public_success(self, permission_manager, test_db, test_model):
        """Test making model public."""
        model_id = str(test_model.id)
        
        result = permission_manager.make_public(model_id, True)
        
        assert result["status"] == "success"
        assert "made public" in result["message"]
        assert result["is_public"] == True
        
        # Verify in database
        test_db.refresh(test_model)
        assert test_model.is_public == True
    
    def test_make_private_success(self, permission_manager, test_db, public_model):
        """Test making model private."""
        model_id = str(public_model.id)
        
        # Create manager for model owner
        owner = test_db.query(User).filter_by(id=public_model.owner_id).first()
        manager = ModelPermissionManager(test_db, owner)
        
        result = manager.make_public(model_id, False)
        
        assert result["status"] == "success"
        assert "made private" in result["message"]
        assert result["is_public"] == False
        
        # Verify in database
        test_db.refresh(public_model)
        assert public_model.is_public == False
    
    def test_make_public_nonexistent_model(self, permission_manager):
        """Test making non-existent model public."""
        fake_model_id = str(uuid.uuid4())
        
        result = permission_manager.make_public(fake_model_id, True)
        
        assert result["status"] == "error"
        assert "not found" in result["message"]
    
    def test_make_public_permission_denied(self, test_db, other_user, test_model):
        """Test making model public without admin permissions."""
        # Create manager for other_user (no admin access to private model)
        manager = ModelPermissionManager(test_db, other_user)
        model_id = str(test_model.id)
        
        result = manager.make_public(model_id, True)
        
        assert result["status"] == "error"
        assert "Permission denied" in result["message"]
    
    def test_make_public_already_public(self, permission_manager, test_db, public_model):
        """Test making already public model public."""
        # Create manager for model owner
        owner = test_db.query(User).filter_by(id=public_model.owner_id).first()
        manager = ModelPermissionManager(test_db, owner)
        
        model_id = str(public_model.id)
        
        result = manager.make_public(model_id, True)
        
        assert result["status"] == "success"
        assert "already public" in result["message"]


class TestAccessLevelValidation:
    """Test access level validation functionality."""
    
    def test_access_level_sufficient_same_level(self, permission_manager):
        """Test access level sufficiency with same levels."""
        assert permission_manager._access_level_sufficient("read", "read") == True
        assert permission_manager._access_level_sufficient("write", "write") == True
        assert permission_manager._access_level_sufficient("admin", "admin") == True
        assert permission_manager._access_level_sufficient("owner", "owner") == True
    
    def test_access_level_sufficient_higher_level(self, permission_manager):
        """Test access level sufficiency with higher granted level."""
        assert permission_manager._access_level_sufficient("write", "read") == True
        assert permission_manager._access_level_sufficient("admin", "read") == True
        assert permission_manager._access_level_sufficient("admin", "write") == True
        assert permission_manager._access_level_sufficient("owner", "admin") == True
        assert permission_manager._access_level_sufficient("owner", "read") == True
    
    def test_access_level_sufficient_lower_level(self, permission_manager):
        """Test access level sufficiency with lower granted level."""
        assert permission_manager._access_level_sufficient("read", "write") == False
        assert permission_manager._access_level_sufficient("read", "admin") == False
        assert permission_manager._access_level_sufficient("write", "admin") == False
        assert permission_manager._access_level_sufficient("admin", "owner") == False
    
    def test_access_level_sufficient_invalid_levels(self, permission_manager):
        """Test access level sufficiency with invalid levels."""
        assert permission_manager._access_level_sufficient("invalid", "read") == False
        assert permission_manager._access_level_sufficient("read", "invalid") == False
        assert permission_manager._access_level_sufficient("invalid", "invalid") == False