"""
Test suite for GDPR compliance features.

This module tests the GDPR compliance framework including user data access,
modification, deletion, and portability rights as required by GDPR Articles 15-20.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

from emuses.tools.gdpr_compliance import GDPRComplianceManager, GDPRError


class TestGDPRDataAccess:
    """Test GDPR Article 15 - Right to Access personal data."""

    def test_user_data_export_complete(self):
        """Test complete user data export includes all personal data."""
        # Create mock database session and user
        mock_db = Mock()
        mock_user = Mock()
        mock_user.id = str(uuid4())
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"
        mock_user.created_at = datetime.utcnow()

        # Create GDPR manager
        gdpr_manager = GDPRComplianceManager(mock_db, mock_user)

        # Mock user data queries
        mock_db.query.return_value.filter.return_value.all.return_value = [
            Mock(id="model1", name="User Model 1", created_at=datetime.utcnow()),
            Mock(id="model2", name="User Model 2", created_at=datetime.utcnow())
        ]

        # Test data export
        result = gdpr_manager.export_user_data()

        # Verify export contains required sections
        assert result["status"] == "success"
        data = result["user_data"]
        assert "personal_information" in data
        assert "models" in data
        assert "workspaces" in data
        assert "access_logs" in data
        assert "export_metadata" in data

        # Verify personal information
        personal_info = data["personal_information"]
        assert personal_info["email"] == "test@example.com"
        assert personal_info["full_name"] == "Test User"
        assert "user_id" in personal_info

    def test_user_data_export_authentication_required(self):
        """Test data export requires proper authentication."""
        mock_db = Mock()
        unauthenticated_user = None

        with pytest.raises(GDPRError, match="Authenticated user required"):
            GDPRComplianceManager(mock_db, unauthenticated_user)

    def test_user_data_export_includes_model_access_history(self):
        """Test export includes comprehensive model access history."""
        mock_db = Mock()
        mock_user = Mock()
        mock_user.id = str(uuid4())
        mock_user.email = "test@example.com"

        # Mock access grants from database
        mock_access_grant1 = Mock()
        mock_access_grant1.model_id = "model1"
        mock_access_grant1.access_level = "read"
        mock_access_grant1.granted_at = datetime.utcnow()
        mock_access_grant1.granted_by_id = "user2"
        mock_access_grant1.expires_at = None

        mock_access_grant2 = Mock()
        mock_access_grant2.model_id = "model2"
        mock_access_grant2.access_level = "write"
        mock_access_grant2.granted_at = datetime.utcnow() - timedelta(days=30)
        mock_access_grant2.granted_by_id = "user3"
        mock_access_grant2.expires_at = None

        # Mock database query chain
        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_access_grant1, mock_access_grant2
        ]

        gdpr_manager = GDPRComplianceManager(mock_db, mock_user)
        result = gdpr_manager.export_user_data()

        assert result["status"] == "success"
        access_logs = result["user_data"]["access_logs"]
        assert len(access_logs) == 2
        assert access_logs[0]["access_level"] == "read"
        assert access_logs[1]["access_level"] == "write"


class TestGDPRDataRectification:
    """Test GDPR Article 16 - Right to Rectification of personal data."""

    def test_update_personal_information_success(self):
        """Test successful update of user personal information."""
        mock_db = Mock()
        mock_user = Mock()
        mock_user.id = str(uuid4())
        mock_user.email = "old@example.com"
        mock_user.full_name = "Old Name"

        gdpr_manager = GDPRComplianceManager(mock_db, mock_user)

        update_data = {
            "email": "new@example.com",
            "full_name": "New Name"
        }

        result = gdpr_manager.update_personal_information(update_data)

        assert result["status"] == "success"
        assert "updated" in result["message"].lower()

        # Verify database commit was called
        mock_db.commit.assert_called_once()

    def test_update_personal_information_validation(self):
        """Test validation of personal information updates."""
        mock_db = Mock()
        mock_user = Mock()
        mock_user.id = str(uuid4())

        gdpr_manager = GDPRComplianceManager(mock_db, mock_user)

        # Test invalid email format
        invalid_update = {"email": "invalid-email"}
        result = gdpr_manager.update_personal_information(invalid_update)

        assert result["status"] == "error"
        assert "invalid email format" in result["message"].lower()

    def test_update_personal_information_audit_logging(self):
        """Test personal information updates create audit logs."""
        mock_db = Mock()
        mock_user = Mock()
        mock_user.id = str(uuid4())

        gdpr_manager = GDPRComplianceManager(mock_db, mock_user)

        update_data = {"full_name": "Updated Name"}

        with patch.object(gdpr_manager, '_create_audit_log') as mock_audit:
            result = gdpr_manager.update_personal_information(update_data)

            assert result["status"] == "success"
            mock_audit.assert_called_once()
            audit_call = mock_audit.call_args[1]
            assert audit_call["action"] == "data_rectification"
            assert "updated_fields" in audit_call["details"]
            assert "full_name" in audit_call["details"]["updated_fields"]


class TestGDPRDataErasure:
    """Test GDPR Article 17 - Right to Erasure of personal data."""

    def test_request_data_deletion_soft_delete(self):
        """Test soft deletion process with retention period."""
        mock_db = Mock()
        mock_user = Mock()
        mock_user.id = str(uuid4())

        # Mock user models for cascade analysis
        mock_models = [
            Mock(id="model1", name="User Model", is_public=False),
            Mock(id="model2", name="Public Model", is_public=True)
        ]

        gdpr_manager = GDPRComplianceManager(mock_db, mock_user)

        # Mock user has models, so deletion should be scheduled
        with patch.object(gdpr_manager, '_get_user_models', return_value=mock_models):
            with patch.object(gdpr_manager, '_get_user_workspaces', return_value=[]):
                result = gdpr_manager.request_data_deletion(deletion_reason="user_request")

                assert result["status"] == "success"
                assert result["deletion_type"] == "scheduled"
                assert "retention_period_days" in result
                assert result["retention_period_days"] == 30  # Standard retention

    def test_request_data_deletion_impact_analysis(self):
        """Test deletion impact analysis for models and workspaces."""
        mock_db = Mock()
        mock_user = Mock()
        mock_user.id = str(uuid4())

        gdpr_manager = GDPRComplianceManager(mock_db, mock_user)

        # Mock complex user data scenario
        mock_user_models = [Mock(id="model1", is_public=True), Mock(id="model2", is_public=False)]
        mock_user_workspaces = [Mock(id="workspace1", member_count=5)]

        with patch.object(gdpr_manager, '_get_user_models', return_value=mock_user_models):
            with patch.object(gdpr_manager, '_get_user_workspaces', return_value=mock_user_workspaces):
                result = gdpr_manager.request_data_deletion(deletion_reason="user_request")

                assert result["status"] == "success"
                impact = result["deletion_impact"]
                assert "models_affected" in impact
                assert "workspaces_affected" in impact
                assert impact["models_affected"] == 2
                assert impact["workspaces_affected"] == 1

    def test_immediate_deletion_for_inactive_users(self):
        """Test immediate deletion for users with no active data."""
        mock_db = Mock()
        mock_user = Mock()
        mock_user.id = str(uuid4())
        mock_user.last_login = datetime.utcnow() - timedelta(days=365)  # Inactive user

        gdpr_manager = GDPRComplianceManager(mock_db, mock_user)

        # Mock no user data
        with patch.object(gdpr_manager, '_get_user_models', return_value=[]):
            with patch.object(gdpr_manager, '_get_user_workspaces', return_value=[]):
                result = gdpr_manager.request_data_deletion(deletion_reason="user_request")

                assert result["status"] == "success"
                assert result["deletion_type"] == "immediate"
                assert "retention_period_days" not in result


class TestGDPRDataPortability:
    """Test GDPR Article 20 - Right to Data Portability."""

    def test_export_portable_data_format(self):
        """Test data export in portable, machine-readable format."""
        mock_db = Mock()
        mock_user = Mock()
        mock_user.id = str(uuid4())
        mock_user.email = "user@example.com"
        mock_user.full_name = "Test User"
        mock_user.created_at = datetime.utcnow()
        mock_user.updated_at = datetime.utcnow()

        gdpr_manager = GDPRComplianceManager(mock_db, mock_user)

        # Mock database queries to return empty results (3 queries: access history, models, workspaces)
        query_mock = Mock()
        filter_mock = Mock()
        query_mock.filter = Mock(return_value=filter_mock)
        filter_mock.all = Mock(side_effect=[[], [], []])  # Three empty results
        mock_db.query = Mock(return_value=query_mock)

        result = gdpr_manager.export_portable_data(export_format="json")

        assert result["status"] == "success"
        assert result["export_format"] == "json"
        assert "export_data" in result

        # Verify JSON structure is valid
        export_data = result["export_data"]
        # Should be valid JSON (no Mock objects)
        json.loads(json.dumps(export_data))

    def test_export_portable_data_csv_format(self):
        """Test data export in CSV format for external systems."""
        mock_db = Mock()
        mock_user = Mock()
        mock_user.id = str(uuid4())

        gdpr_manager = GDPRComplianceManager(mock_db, mock_user)

        result = gdpr_manager.export_portable_data(export_format="csv")

        assert result["status"] == "success"
        assert result["export_format"] == "csv"
        assert "export_url" in result or "csv_files" in result

    def test_export_includes_model_metadata(self):
        """Test portable export includes complete model metadata."""
        mock_db = Mock()
        mock_user = Mock()
        mock_user.id = str(uuid4())

        gdpr_manager = GDPRComplianceManager(mock_db, mock_user)

        # Mock database query for user models
        mock_model = Mock()
        mock_model.id = "model1"
        mock_model.name = "Test Model"
        mock_model.description = "Test Description"
        mock_model.created_at = datetime.utcnow()
        mock_model.is_public = False
        mock_model.model_metrics = {"accuracy": 0.95}

        # The portable data method makes 3 separate database calls:
        # 1. _get_user_access_history() -> ModelAccess query
        # 2. _get_user_models_data() -> ModelRegistry query
        # 3. _get_user_workspaces_data() -> Workspace query

        query_mock = Mock()
        filter_mock = Mock()
        query_mock.filter = Mock(return_value=filter_mock)

        # The _get_portable_data method calls _get_user_models() which is different from _get_user_models_data()
        # So we need to mock the _get_user_models() method directly
        with patch.object(gdpr_manager, '_get_user_models', return_value=[mock_model]):
            result = gdpr_manager.export_portable_data(export_format="json")

        assert result["status"] == "success"
        models_data = result["export_data"]["models"]
        assert len(models_data) == 1
        assert models_data[0]["name"] == "Test Model"
        assert models_data[0]["description"] == "Test Description"


class TestGDPRComplianceManager:
    """Test core GDPRComplianceManager functionality."""

    def test_gdpr_manager_initialization(self):
        """Test GDPR manager initializes with required dependencies."""
        mock_db = Mock()
        mock_user = Mock()

        gdpr_manager = GDPRComplianceManager(mock_db, mock_user)

        assert gdpr_manager.db_session == mock_db
        assert gdpr_manager.current_user == mock_user
        assert hasattr(gdpr_manager, '_create_audit_log')

    def test_gdpr_manager_without_user_fails(self):
        """Test GDPR manager requires authenticated user."""
        mock_db = Mock()

        with pytest.raises(GDPRError, match="Authenticated user required"):
            GDPRComplianceManager(mock_db, None)

    def test_audit_log_creation(self):
        """Test audit logging for GDPR operations."""
        mock_db = Mock()
        mock_user = Mock()
        mock_user.id = str(uuid4())

        gdpr_manager = GDPRComplianceManager(mock_db, mock_user)

        # Test audit log creation
        gdpr_manager._create_audit_log(
            action="data_access",
            details={"requested_data": ["personal_info", "models"]},
            ip_address="192.168.1.1"
        )

        # Verify audit log was saved to database
        mock_db.add.assert_called_once()
        # Note: _create_audit_log doesn't commit - that's handled by calling methods

        # Verify audit log contains required fields
        audit_log = mock_db.add.call_args[0][0]
        assert audit_log.user_id == mock_user.id
        assert audit_log.action == "data_access"
        assert "requested_data" in audit_log.details
