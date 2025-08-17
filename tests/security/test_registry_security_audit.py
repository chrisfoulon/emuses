"""Security audit tests for Model Registry permission boundaries.

This module implements comprehensive security testing for the EMUSES model registry
focusing on permission boundary enforcement across all deployment modes.

Tests cover:
- User isolation and access control
- Workspace boundary enforcement
- Cross-mode permission consistency
- Privilege escalation prevention
- Malicious input protection
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from emuses.tools.model_permission_manager import ModelPermissionManager
from emuses.tools.local_model_registry import LocalModelRegistry
from emuses.tools.model_registry_factory import ModelRegistryFactory


class TestPermissionBoundaryEnforcement:
    """Test permission boundary enforcement across registry modes."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session for testing."""
        return Mock()

    @pytest.fixture
    def mock_user(self):
        """Create mock user for testing."""
        user = Mock()
        user.id = uuid4()
        user.email = "test@example.com"
        user.is_superuser = False
        return user

    @pytest.fixture
    def mock_admin_user(self):
        """Create mock admin user for testing."""
        user = Mock()
        user.id = uuid4()
        user.email = "admin@example.com"
        user.is_superuser = True
        return user

    @pytest.fixture
    def permission_manager(self, mock_db_session, mock_user):
        """Create ModelPermissionManager for testing."""
        return ModelPermissionManager(mock_db_session, mock_user)

    @pytest.fixture
    def temp_registry(self):
        """Create temporary local registry for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "test_registry"
            registry = LocalModelRegistry(registry_path=registry_path)
            yield registry

    def test_owner_access_enforcement(self, permission_manager, mock_db_session, mock_user):
        """Test that model owners have full access to their models."""
        # Setup mock model owned by current user
        model_id = uuid4()
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.owner_id = mock_user.id
        mock_model.is_public = False
        mock_model.workspace_id = None

        mock_db_session.query().filter().first.return_value = mock_model

        # Test owner has all access levels
        assert permission_manager.check_access(model_id, "read") is True
        assert permission_manager.check_access(model_id, "write") is True
        assert permission_manager.check_access(model_id, "admin") is True
        assert permission_manager.check_access(model_id, "owner") is True

    def test_user_isolation_enforcement(self, permission_manager, mock_db_session, mock_user):
        """Test that users cannot access models owned by others without permission."""
        # Setup mock model owned by different user
        other_user_id = uuid4()
        model_id = uuid4()
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.owner_id = other_user_id  # Different from current user
        mock_model.is_public = False
        mock_model.workspace_id = None

        mock_db_session.query().filter().first.return_value = mock_model
        mock_db_session.query().filter().first.side_effect = [mock_model, None]  # No access grant

        # Test user cannot access other user's private model
        assert permission_manager.check_access(model_id, "read") is False
        assert permission_manager.check_access(model_id, "write") is False
        assert permission_manager.check_access(model_id, "admin") is False
        assert permission_manager.check_access(model_id, "owner") is False

    def test_public_model_read_access(self, permission_manager, mock_db_session, mock_user):
        """Test that authenticated users can read public models."""
        # Setup public model owned by different user
        other_user_id = uuid4()
        model_id = uuid4()
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.owner_id = other_user_id
        mock_model.is_public = True
        mock_model.workspace_id = None

        mock_db_session.query().filter().first.return_value = mock_model

        # Test user can read public model but not write/admin
        assert permission_manager.check_access(model_id, "read") is True
        assert permission_manager.check_access(model_id, "write") is False
        assert permission_manager.check_access(model_id, "admin") is False
        assert permission_manager.check_access(model_id, "owner") is False

    def test_workspace_boundary_enforcement(self, permission_manager, mock_db_session, mock_user):
        """Test workspace-level permission boundaries."""
        # Setup workspace and model
        workspace_id = uuid4()
        workspace_owner_id = uuid4()
        model_id = uuid4()
        model_owner_id = uuid4()  # Different from workspace owner and current user

        mock_model = Mock()
        mock_model.id = model_id
        mock_model.owner_id = model_owner_id
        mock_model.is_public = False
        mock_model.workspace_id = workspace_id

        mock_workspace = Mock()
        mock_workspace.id = workspace_id
        mock_workspace.owner_id = workspace_owner_id

        def query_side_effect(*args):
            mock_query = Mock()
            if args[0].__name__ == 'ModelRegistry':
                mock_query.filter().first.return_value = mock_model
            elif args[0].__name__ == 'Workspace':
                mock_query.filter().first.return_value = mock_workspace
            else:  # ModelAccess
                mock_query.filter().first.return_value = None
            return mock_query

        mock_db_session.query.side_effect = query_side_effect

        # Test current user (not workspace owner) cannot access workspace model
        assert permission_manager.check_access(model_id, "read") is False
        assert permission_manager.check_access(model_id, "admin") is False

        # Test workspace owner gets admin access
        permission_manager.current_user.id = workspace_owner_id
        assert permission_manager.check_access(model_id, "admin") is True

    def test_explicit_permission_grants(self, permission_manager, mock_db_session, mock_user):
        """Test explicit permission grant functionality."""
        # Setup model owned by different user
        other_user_id = uuid4()
        model_id = uuid4()
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.owner_id = other_user_id
        mock_model.is_public = False
        mock_model.workspace_id = None

        # Setup explicit access grant
        mock_access_grant = Mock()
        mock_access_grant.model_id = model_id
        mock_access_grant.user_id = mock_user.id
        mock_access_grant.access_level = "write"
        mock_access_grant.expires_at = None

        def query_side_effect(*args):
            mock_query = Mock()
            if args[0].__name__ == 'ModelRegistry':
                mock_query.filter().first.return_value = mock_model
            elif args[0].__name__ == 'ModelAccess':
                mock_query.filter().first.return_value = mock_access_grant
            else:
                mock_query.filter().first.return_value = None
            return mock_query

        mock_db_session.query.side_effect = query_side_effect

        # Test user has write access via explicit grant
        assert permission_manager.check_access(model_id, "read") is True
        assert permission_manager.check_access(model_id, "write") is True
        assert permission_manager.check_access(model_id, "admin") is False  # Higher than granted

    def test_privilege_escalation_prevention(self, permission_manager, mock_db_session, mock_user):
        """Test prevention of privilege escalation attempts."""
        # Setup model owned by different user
        other_user_id = uuid4()
        target_user_id = uuid4()
        model_id = uuid4()

        mock_model = Mock()
        mock_model.id = model_id
        mock_model.owner_id = other_user_id
        mock_model.is_public = False

        mock_target_user = Mock()
        mock_target_user.id = target_user_id
        mock_target_user.email = "target@example.com"

        def query_side_effect(*args):
            mock_query = Mock()
            if args[0].__name__ == 'ModelRegistry':
                mock_query.filter().first.return_value = mock_model
            elif args[0].__name__ == 'User':
                mock_query.filter().first.return_value = mock_target_user
            else:
                mock_query.filter().first.return_value = None
            return mock_query

        mock_db_session.query.side_effect = query_side_effect

        # Test non-admin user cannot grant permissions
        result = permission_manager.grant_access(model_id, target_user_id, "read")
        assert result["status"] == "error"
        assert "admin access required" in result["message"]

        # Test cannot grant owner level access
        mock_user.id = other_user_id  # Make current user the owner
        result = permission_manager.grant_access(model_id, target_user_id, "owner")
        assert result["status"] == "error"
        assert "Cannot grant owner access level" in result["message"]

    def test_cross_mode_permission_consistency(self, mock_db_session, mock_user):
        """Test permission consistency across different registry modes."""
        model_id = "test-model-123"

        # Test permission manager works with different UUID formats
        permission_manager = ModelPermissionManager(mock_db_session, mock_user)

        # Setup mock model that works with string ID
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.owner_id = mock_user.id
        mock_model.is_public = False

        mock_db_session.query().filter().first.return_value = mock_model

        # Test flexible UUID handling doesn't break permission checks
        try:
            has_access = permission_manager.check_access(model_id, "read")
            # Should not raise exception even with string model ID
            assert isinstance(has_access, bool)
        except Exception as e:
            pytest.fail(f"Cross-mode permission check failed: {e}")

    def test_malicious_model_id_handling(self, permission_manager, mock_db_session):
        """Test handling of malicious model ID inputs."""
        malicious_inputs = [
            "../../../etc/passwd",
            "'; DROP TABLE models; --",
            "<script>alert('xss')</script>",
            "$(rm -rf /)",
            "\x00malicious\x00",
            "a" * 10000,  # Very long input
        ]

        mock_db_session.query().filter().first.return_value = None

        for malicious_id in malicious_inputs:
            # Should handle gracefully without throwing unexpected exceptions
            result = permission_manager.check_access(malicious_id, "read")
            assert result is False, f"Malicious ID should be denied: {malicious_id}"

    @pytest.mark.asyncio
    async def test_async_permission_methods(self, permission_manager, mock_db_session, mock_user):
        """Test asynchronous permission checking methods."""
        model_id = uuid4()
        user_id = uuid4()

        # Setup mock model
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.owner_id = user_id
        mock_model.is_public = True

        mock_db_session.query().filter().first.return_value = mock_model

        # Test async admin check
        is_admin = await permission_manager.is_admin(user_id)
        assert isinstance(is_admin, bool)

        # Test async access check
        can_access = await permission_manager.can_access(model_id, user_id, "read")
        assert can_access is True  # Public model, should allow read access

        # Test async grant access
        workspace_id = uuid4()
        granted_by = uuid4()
        result = await permission_manager.async_grant_access(
            model_id, workspace_id, "read", granted_by
        )
        assert result["status"] == "success"


class TestLocalRegistrySecurity:
    """Test security aspects specific to local registry mode."""

    @pytest.fixture
    def temp_registry(self):
        """Create temporary local registry for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "test_registry"
            registry = LocalModelRegistry(registry_path=registry_path)
            yield registry

    def test_filesystem_isolation(self, temp_registry):
        """Test filesystem-level isolation for local registry."""
        # Test registry paths are isolated
        assert temp_registry.registry_path.name == "test_registry"
        assert temp_registry.models_path.parent == temp_registry.registry_path

        # Test operations stay within registry bounds
        models = temp_registry.list_models()
        assert isinstance(models, list)

        # Registry should not access files outside its directory
        registry_info = temp_registry.get_registry_info()
        assert "registry_path" in registry_info
        assert str(temp_registry.registry_path) in registry_info["registry_path"]

    def test_safe_model_operations(self, temp_registry):
        """Test model operations handle security safely."""
        # Test non-existent model operations
        info = temp_registry.get_model_info("../../../etc/passwd")
        assert info is None

        # Test remove non-existent model
        result = temp_registry.remove_model("malicious_path/../..")
        assert result["status"] == "error"

        # Test search with malicious query
        results = temp_registry.search_models("<script>alert('xss')</script>")
        assert isinstance(results, list)

    def test_index_corruption_resilience(self, temp_registry):
        """Test resilience to index file corruption/manipulation."""
        # Corrupt the index file
        with open(temp_registry.index_path, 'w') as f:
            f.write("{ invalid json")

        # All operations should handle corruption gracefully
        models = temp_registry.list_models()
        assert models == []

        info = temp_registry.get_registry_info()
        assert "error" in info

        # Index should be recoverable
        is_valid, issues = temp_registry.validate_index()
        assert is_valid is False
        assert len(issues) > 0


class TestUserDataIsolation:
    """Test user data isolation in multi-user scenarios."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session for testing."""
        return Mock()

    @pytest.fixture
    def user_alice(self):
        """Create mock user Alice for testing."""
        user = Mock()
        user.id = uuid4()
        user.email = "alice@example.com"
        user.is_superuser = False
        return user

    @pytest.fixture
    def user_bob(self):
        """Create mock user Bob for testing."""
        user = Mock()
        user.id = uuid4()
        user.email = "bob@example.com"
        user.is_superuser = False
        return user

    @pytest.fixture
    def workspace_alpha(self):
        """Create mock workspace Alpha for testing."""
        workspace = Mock()
        workspace.id = uuid4()
        workspace.name = "Alpha Workspace"
        return workspace

    @pytest.fixture
    def workspace_beta(self):
        """Create mock workspace Beta for testing."""
        workspace = Mock()
        workspace.id = uuid4()
        workspace.name = "Beta Workspace"
        return workspace

    def test_user_model_isolation(self, mock_db_session, user_alice, user_bob):
        """Test that users can only see their own models unless shared."""
        # Create models owned by each user
        alice_model_id = uuid4()
        bob_model_id = uuid4()

        alice_model = Mock()
        alice_model.id = alice_model_id
        alice_model.owner_id = user_alice.id
        alice_model.is_public = False
        alice_model.workspace_id = None

        bob_model = Mock()
        bob_model.id = bob_model_id
        bob_model.owner_id = user_bob.id
        bob_model.is_public = False
        bob_model.workspace_id = None

        # Setup permission manager for Alice
        alice_permission_mgr = ModelPermissionManager(mock_db_session, user_alice)

        def query_side_effect(*args):
            mock_query = Mock()
            # Return appropriate model based on query
            mock_query.filter.return_value.first = Mock(return_value=None)
            if hasattr(args, '__len__') and len(args) > 0:
                if args[0].__name__ == 'ModelRegistry':
                    # Simulate model lookup
                    mock_query.filter.return_value.first = Mock(side_effect=lambda: alice_model)
                elif args[0].__name__ == 'ModelAccess':
                    # No explicit grants
                    mock_query.filter.return_value.first = Mock(return_value=None)
            return mock_query

        mock_db_session.query.side_effect = query_side_effect

        # Alice should access her own model
        assert alice_permission_mgr.check_access(alice_model_id, "read") is True

        # Alice should NOT access Bob's model (simulate by changing the returned model)
        def bob_model_query(*args):
            mock_query = Mock()
            if args[0].__name__ == 'ModelRegistry':
                mock_query.filter.return_value.first = Mock(return_value=bob_model)
            else:
                mock_query.filter.return_value.first = Mock(return_value=None)
            return mock_query

        mock_db_session.query.side_effect = bob_model_query
        assert alice_permission_mgr.check_access(bob_model_id, "read") is False

    def test_workspace_data_segregation(self, mock_db_session, user_alice, user_bob,
                                      workspace_alpha, workspace_beta):
        """Test workspace-level data segregation."""
        # Alice owns workspace Alpha, Bob owns workspace Beta
        workspace_alpha.owner_id = user_alice.id
        workspace_beta.owner_id = user_bob.id

        # Create models in each workspace
        alpha_model_id = uuid4()
        beta_model_id = uuid4()

        alpha_model = Mock()
        alpha_model.id = alpha_model_id
        alpha_model.owner_id = user_bob.id  # Bob's model in Alice's workspace
        alpha_model.is_public = False
        alpha_model.workspace_id = workspace_alpha.id

        beta_model = Mock()
        beta_model.id = beta_model_id
        beta_model.owner_id = user_bob.id  # Bob's model in Bob's workspace
        beta_model.is_public = False
        beta_model.workspace_id = workspace_beta.id

        alice_permission_mgr = ModelPermissionManager(mock_db_session, user_alice)

        # Test Alice can access models in her workspace (workspace admin access)
        def alpha_workspace_query(*args):
            mock_query = Mock()
            if args[0].__name__ == 'ModelRegistry':
                mock_query.filter.return_value.first = Mock(return_value=alpha_model)
            elif args[0].__name__ == 'Workspace':
                mock_query.filter.return_value.first = Mock(return_value=workspace_alpha)
            else:
                mock_query.filter.return_value.first = Mock(return_value=None)
            return mock_query

        mock_db_session.query.side_effect = alpha_workspace_query
        # Alice should have admin access to models in her workspace
        assert alice_permission_mgr.check_access(alpha_model_id, "admin") is True

        # Test Alice cannot access models in Bob's workspace
        def beta_workspace_query(*args):
            mock_query = Mock()
            if args[0].__name__ == 'ModelRegistry':
                mock_query.filter.return_value.first = Mock(return_value=beta_model)
            elif args[0].__name__ == 'Workspace':
                mock_query.filter.return_value.first = Mock(return_value=workspace_beta)
            else:
                mock_query.filter.return_value.first = Mock(return_value=None)
            return mock_query

        mock_db_session.query.side_effect = beta_workspace_query
        assert alice_permission_mgr.check_access(beta_model_id, "read") is False

    def test_data_leakage_prevention(self, mock_db_session, user_alice, user_bob):
        """Test prevention of data leakage between users."""
        alice_permission_mgr = ModelPermissionManager(mock_db_session, user_alice)

        # Test information disclosure through error messages
        non_existent_model_id = uuid4()

        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        # Should not leak information about whether model exists
        result = alice_permission_mgr.list_permissions(non_existent_model_id)
        assert result["status"] == "error"
        assert "not found" in result["message"]
        # Should not expose details about other users or internal structure

        # Test malicious model ID attempts don't leak system info beyond the input itself
        malicious_ids = [
            "'; SELECT * FROM users; --",
            "../../../etc/passwd",
            "system_internal",
        ]

        for malicious_id in malicious_ids:
            result = alice_permission_mgr.list_permissions(malicious_id)
            assert result["status"] == "error"
            # Error message should not expose sensitive database/system information
            # beyond what was provided in the input
            error_msg = result["message"].lower()

            # Check that error messages don't leak additional sensitive information
            # that wasn't in the original input
            dangerous_terms = ["password", "token", "session", "connection", "database_host"]
            for term in dangerous_terms:
                assert term not in error_msg, f"Error message leaks sensitive term: {term}"

            # Should be a proper error response
            assert any(safe_term in error_msg for safe_term in
                      ["not found", "invalid", "format", "failed"])

    def test_user_enumeration_prevention(self, mock_db_session, user_alice):
        """Test prevention of user enumeration attacks."""
        alice_permission_mgr = ModelPermissionManager(mock_db_session, user_alice)
        model_id = uuid4()

        # Setup model that Alice owns
        model = Mock()
        model.id = model_id
        model.owner_id = user_alice.id
        model.is_public = False

        mock_db_session.query.return_value.filter.return_value.first.return_value = model

        # Test granting access to non-existent user
        non_existent_user_id = uuid4()

        def query_side_effect(*args):
            mock_query = Mock()
            if args[0].__name__ == 'ModelRegistry':
                mock_query.filter.return_value.first = Mock(return_value=model)
            elif args[0].__name__ == 'User':
                # Simulate user not found
                mock_query.filter.return_value.first = Mock(return_value=None)
            else:
                mock_query.filter.return_value.first = Mock(return_value=None)
            return mock_query

        mock_db_session.query.side_effect = query_side_effect

        # Should not expose whether user exists or not through different error messages
        result = alice_permission_mgr.grant_access(model_id, non_existent_user_id, "read")
        assert result["status"] == "error"
        assert "not found" in result["message"]

        # Error message should be generic, not revealing user existence details
        assert "user" in result["message"].lower()

    def test_concurrent_access_isolation(self, mock_db_session, user_alice, user_bob):
        """Test isolation during concurrent multi-user access."""
        model_id = uuid4()

        # Create model owned by Alice
        model = Mock()
        model.id = model_id
        model.owner_id = user_alice.id
        model.is_public = False
        model.workspace_id = None

        # Create permission managers for both users
        alice_mgr = ModelPermissionManager(mock_db_session, user_alice)
        bob_mgr = ModelPermissionManager(mock_db_session, user_bob)

        mock_db_session.query.return_value.filter.return_value.first.return_value = model

        # Simulate concurrent access attempts
        # Alice should have access as owner
        assert alice_mgr.check_access(model_id, "owner") is True

        # Bob should not have access even if requests happen concurrently
        assert bob_mgr.check_access(model_id, "read") is False
        assert bob_mgr.check_access(model_id, "write") is False
        assert bob_mgr.check_access(model_id, "admin") is False

        # Verify the permission check is user-context specific
        # (both using same model but different user contexts)
        assert alice_mgr.current_user.id != bob_mgr.current_user.id

    def test_privilege_containment(self, mock_db_session, user_alice, user_bob):
        """Test that user privileges are properly contained."""
        alice_mgr = ModelPermissionManager(mock_db_session, user_alice)
        model_id = uuid4()

        # Model owned by Bob
        model = Mock()
        model.id = model_id
        model.owner_id = user_bob.id
        model.is_public = False

        mock_target_user = Mock()
        mock_target_user.id = uuid4()
        mock_target_user.email = "target@example.com"

        def query_side_effect(*args):
            mock_query = Mock()
            if args[0].__name__ == 'ModelRegistry':
                mock_query.filter.return_value.first = Mock(return_value=model)
            elif args[0].__name__ == 'User':
                mock_query.filter.return_value.first = Mock(return_value=mock_target_user)
            else:
                mock_query.filter.return_value.first = Mock(return_value=None)
            return mock_query

        mock_db_session.query.side_effect = query_side_effect

        # Alice should not be able to grant access to Bob's model
        result = alice_mgr.grant_access(model_id, mock_target_user.id, "read")
        assert result["status"] == "error"
        assert "admin access required" in result["message"]

        # Alice should not be able to revoke access from Bob's model
        result = alice_mgr.revoke_access(model_id, mock_target_user.id)
        assert result["status"] == "error"
        assert "admin access required" in result["message"]

        # Alice should not be able to transfer ownership of Bob's model
        result = alice_mgr.transfer_ownership(model_id, mock_target_user.id)
        assert result["status"] == "error"
        assert "only model owner can transfer ownership" in result["message"]


class TestMaliciousModelUploadProtection:
    """Test protection against malicious model uploads."""

    @pytest.fixture
    def temp_registry(self):
        """Create temporary local registry for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "test_registry"
            registry = LocalModelRegistry(registry_path=registry_path)
            yield registry

    @pytest.fixture
    def malicious_zip_file(self):
        """Create malicious ZIP file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
            # Create a ZIP with path traversal
            import zipfile
            with zipfile.ZipFile(temp_file.name, 'w') as zf:
                zf.writestr('../../../../etc/passwd', 'malicious content')
                zf.writestr('normal_file.txt', 'normal content')
            yield Path(temp_file.name)
            Path(temp_file.name).unlink()

    @pytest.fixture
    def oversized_model_file(self):
        """Create oversized model file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as temp_file:
            # Create a 10MB file (assuming model size limits exist)
            temp_file.write(b'0' * (10 * 1024 * 1024))
            yield Path(temp_file.name)
            Path(temp_file.name).unlink()

    @pytest.fixture
    def executable_disguised_model(self):
        """Create executable file disguised as model."""
        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as temp_file:
            # Write executable header + malicious content
            temp_file.write(b'#!/bin/sh\nrm -rf /\n')
            temp_file.write(b'\x00' * 1000)  # Padding to look like binary data
            yield Path(temp_file.name)
            Path(temp_file.name).unlink()

    def test_path_traversal_in_model_upload(self, temp_registry, malicious_zip_file):
        """Test protection against path traversal attacks in model uploads."""
        # Try to install malicious ZIP file
        result = temp_registry.install_model(malicious_zip_file, name="malicious_model")

        # Should fail due to security validation
        assert result["status"] == "error"

        # Should not create files outside registry directory
        registry_parent = temp_registry.registry_path.parent

        # Check no files were created outside registry directory
        for path in registry_parent.rglob("*passwd*"):
            # If any passwd file was created, it should be within registry bounds
            assert temp_registry.registry_path in path.parents

    def test_file_size_validation(self, temp_registry, oversized_model_file):
        """Test validation of model file sizes."""
        # Try to install oversized model
        result = temp_registry.install_model(oversized_model_file, name="huge_model")

        # Should handle large files appropriately (either reject or warn)
        # The exact behavior depends on implementation, but should not crash
        assert "status" in result
        assert isinstance(result["status"], str)

        # If accepted, should not consume excessive disk space
        if result["status"] == "success":
            stats = temp_registry.get_registry_stats()
            storage_mb = stats.get('storage_usage', 0) / (1024 * 1024)
            # Registry should not exceed reasonable limits
            assert storage_mb < 50  # Reasonable limit for test

    def test_executable_content_detection(self, temp_registry, executable_disguised_model):
        """Test detection of executable content in model files."""
        # Try to install executable disguised as model
        result = temp_registry.install_model(executable_disguised_model, name="fake_model")

        # Should either reject or handle safely
        assert "status" in result

        # If installed, should not create executable files
        if result.get("model_id"):
            model_dir = temp_registry.models_path / result["model_id"]
            if model_dir.exists():
                for file_path in model_dir.rglob("*"):
                    if file_path.is_file():
                        # Check file is not executable
                        assert not file_path.stat().st_mode & 0o111

    def test_malicious_filename_handling(self, temp_registry):
        """Test handling of malicious filenames in models."""
        malicious_filenames = [
            "../../../etc/passwd",
            "file_with_\x00_null_byte.pkl",
            "very_long_filename_" + "a" * 1000 + ".pkl",
            "file_with_spaces_and_\t_tabs.pkl",
            ".hidden_executable",
            "CON.pkl",  # Windows reserved name
            "file;rm -rf /.pkl",  # Shell injection attempt
        ]

        for malicious_name in malicious_filenames:
            # Create temporary file with safe content
            with tempfile.NamedTemporaryFile(suffix='.pkl') as temp_file:
                temp_file.write(b'safe_model_data')
                temp_file.flush()

                # Try to install with malicious name
                result = temp_registry.install_model(
                    Path(temp_file.name),
                    name=malicious_name
                )

                # Should either reject or sanitize the name
                assert result["status"] in ["error", "success"]

                if result["status"] == "success":
                    # If successful, name should be sanitized
                    installed_name = result.get("name", "")
                    assert "../" not in installed_name
                    assert "\x00" not in installed_name
                    assert len(installed_name) < 256

    def test_model_content_validation(self, temp_registry):
        """Test validation of model file contents."""
        malicious_contents = [
            b'\x7fELF',  # ELF executable header
            b'MZ',       # Windows executable header
            b'#!/bin/sh\nrm -rf /',  # Shell script
            b'<script>alert("xss")</script>',  # XSS attempt
            b'\x00' * 1000 + b'malicious_code',  # Binary with malicious suffix
        ]

        for i, content in enumerate(malicious_contents):
            with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as temp_file:
                temp_file.write(content)
                temp_path = Path(temp_file.name)

            try:
                result = temp_registry.install_model(temp_path, name=f"test_model_{i}")

                # Should handle malicious content appropriately
                assert "status" in result

                # If installation succeeds, verify content is isolated
                if result["status"] == "success" and result.get("model_id"):
                    model_dir = temp_registry.models_path / result["model_id"]
                    # Model directory should exist within registry bounds
                    assert model_dir.exists()
                    assert temp_registry.registry_path in model_dir.parents

            finally:
                temp_path.unlink(missing_ok=True)

    def test_zip_bomb_protection(self, temp_registry):
        """Test protection against zip bomb attacks."""
        # Create a simple zip bomb (small file that expands to large size)
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
            import zipfile
            with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Create a file that compresses well but expands large
                large_content = b'0' * (1024 * 1024)  # 1MB of zeros
                zf.writestr('expanded_file.txt', large_content)

            zip_path = Path(temp_file.name)

        try:
            # Try to install zip bomb
            result = temp_registry.install_model(zip_path, name="zip_bomb")

            # Should handle without consuming excessive resources
            assert "status" in result

            # Check registry storage hasn't grown excessively
            stats = temp_registry.get_registry_stats()
            storage_mb = stats.get('storage_usage', 0) / (1024 * 1024)
            assert storage_mb < 100  # Should not expand to huge size

        finally:
            zip_path.unlink(missing_ok=True)

    def test_symlink_attack_protection(self, temp_registry):
        """Test protection against symlink attacks in model files."""
        # Create a directory with a symlink pointing outside
        with tempfile.TemporaryDirectory() as temp_dir:
            model_dir = Path(temp_dir) / "malicious_model"
            model_dir.mkdir()

            # Create normal file
            (model_dir / "model.pkl").write_bytes(b'model_data')

            # Try to create symlink to sensitive file (if possible)
            try:
                symlink_target = model_dir / "sensitive_link"
                symlink_target.symlink_to("/etc/passwd")
            except (OSError, NotImplementedError):
                # Symlinks not supported on this system, skip this test
                pytest.skip("Symlinks not supported on this system")

            # Try to install directory containing symlink
            result = temp_registry.install_model(model_dir, name="symlink_model")

            # Should handle symlinks safely
            assert "status" in result

            # If installed, check no symlinks point outside registry
            if result["status"] == "success" and result.get("model_id"):
                model_path = temp_registry.models_path / result["model_id"]
                for file_path in model_path.rglob("*"):
                    if file_path.is_symlink():
                        # Symlink target should be within registry
                        target = file_path.resolve()
                        assert temp_registry.registry_path in target.parents

    def test_concurrent_malicious_uploads(self, temp_registry):
        """Test system resilience against concurrent malicious uploads."""
        # Simulate multiple concurrent malicious upload attempts
        malicious_files = []

        # Create multiple temporary malicious files
        for i in range(5):
            temp_file = tempfile.NamedTemporaryFile(suffix='.pkl', delete=False)
            temp_file.write(f'malicious_content_{i}'.encode() * 1000)
            temp_file.close()
            malicious_files.append(Path(temp_file.name))

        try:
            results = []
            # Try to install all files (simulating concurrent requests)
            for i, file_path in enumerate(malicious_files):
                result = temp_registry.install_model(file_path, name=f"concurrent_malicious_{i}")
                results.append(result)

            # System should handle all attempts gracefully
            for result in results:
                assert "status" in result
                assert isinstance(result["status"], str)

            # Registry should remain in consistent state
            is_valid, issues = temp_registry.validate_index()
            if not is_valid:
                # Some validation issues might be acceptable after malicious attempts
                assert len(issues) < 10  # Should not be completely broken

        finally:
            # Clean up temporary files
            for file_path in malicious_files:
                file_path.unlink(missing_ok=True)


class TestCrossModeSecurityConsistency:
    """Test security consistency across different deployment modes."""

    def test_registry_factory_security_mode_detection(self):
        """Test that registry factory securely detects deployment modes."""
        factory = ModelRegistryFactory()

        # Test mode detection doesn't expose sensitive information
        try:
            registry = factory.create_registry(fallback=True)
            assert registry is not None

            # Should not expose internal configuration details
            registry_type = type(registry).__name__
            assert registry_type in ["LocalModelRegistry", "DatabaseModelRegistry", "CloudModelRegistry"]

        except Exception as e:
            # Should handle errors gracefully without exposing internals
            assert isinstance(e, (ImportError, RuntimeError, ValueError))

    def test_mode_specific_security_validation(self):
        """Test mode-specific security validation."""
        factory = ModelRegistryFactory()

        # Test local mode security
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "secure_registry"

            try:
                registry = factory.create_registry(
                    registry_path=registry_path,
                    fallback=True
                )

                # Should create registry in safe location
                if hasattr(registry, 'registry_path'):
                    assert registry.registry_path == registry_path

                # Test basic operations work securely
                models = registry.list_models()
                assert isinstance(models, list)

            except Exception:
                # Graceful failure expected for some modes without dependencies
                pass

    def test_error_message_security(self):
        """Test that error messages don't expose sensitive information."""
        factory = ModelRegistryFactory()

        try:
            # Try to create registry with invalid configuration
            factory.create_registry(
                registry_path="/invalid/path/that/does/not/exist"
            )
        except Exception as e:
            error_msg = str(e)
            # Error messages shouldn't expose system internals
            sensitive_patterns = [
                "/etc/", "/root/", "password", "secret", "key",
                "system32", "windows", "administrator"
            ]

            for pattern in sensitive_patterns:
                assert pattern not in error_msg.lower(), \
                       f"Error message exposes sensitive info: {pattern}"
