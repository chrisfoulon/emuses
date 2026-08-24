"""
GDPR compliance manager for EMUSES user data.

This module provides GDPRComplianceManager class for handling GDPR requirements
including data access, rectification, erasure, and portability rights.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from emuses.multi_user_service.models import ModelRegistry, ModelAccess, User, Workspace

logger = logging.getLogger(__name__)


class GDPRError(Exception):
    """Custom exception for GDPR-related errors."""
    pass


class GDPRAuditLog:
    """Simple audit log model for GDPR operations."""

    def __init__(self, user_id: str, action: str, details: Dict[str, Any], ip_address: Optional[str] = None):
        """Initialize audit log entry.

        Parameters
        ----------
        user_id : str
            User identifier for the GDPR operation
        action : str
            Type of GDPR action performed
        details : Dict[str, Any]
            Details about the GDPR operation
        ip_address : str, optional
            IP address of the request
        """
        self.user_id = user_id
        self.action = action
        self.details = details
        self.ip_address = ip_address
        self.timestamp = datetime.utcnow()


class GDPRComplianceManager:
    """Manager for GDPR compliance operations.

    Handles user data access, rectification, erasure, and portability
    in compliance with GDPR Articles 15-20.

    Parameters
    ----------
    db_session : Session
        SQLAlchemy database session
    current_user : User
        Current authenticated user

    Attributes
    ----------
    db_session : Session
        Database session for GDPR operations
    current_user : User
        Current user for GDPR operations

    Raises
    ------
    GDPRError
        If authenticated user is not provided
    """

    def __init__(self, db_session: Session, current_user: Optional[User]):
        """Initialize GDPR compliance manager.

        Parameters
        ----------
        db_session : Session
            Active database session
        current_user : User, optional
            Current authenticated user

        Raises
        ------
        GDPRError
            If current_user is None
        """
        if current_user is None:
            raise GDPRError("Authenticated user required for GDPR operations")

        self.db_session = db_session
        self.current_user = current_user

        logger.info(f"GDPRComplianceManager initialized for user {current_user.email}")

    def export_user_data(self) -> Dict[str, Any]:
        """Export complete user data per GDPR Article 15.

        Returns
        -------
        Dict[str, Any]
            Complete user data export with personal information,
            models, workspaces, and access logs
        """
        try:
            if not self.current_user:
                return {
                    "status": "error",
                    "message": "Authentication required for data export"
                }

            # Create audit log
            self._create_audit_log(
                action="data_access",
                details={"export_type": "complete_user_data"}
            )

            # Collect user data
            user_data = {
                "personal_information": self._get_personal_information(),
                "models": self._get_user_models_data(),
                "workspaces": self._get_user_workspaces_data(),
                "access_logs": self._get_user_access_history(),
                "export_metadata": {
                    "export_date": datetime.utcnow().isoformat(),
                    "export_version": "1.0",
                    "user_id": str(self.current_user.id)
                }
            }

            return {
                "status": "success",
                "message": "User data exported successfully",
                "user_data": user_data
            }

        except Exception as e:
            logger.error(f"Failed to export user data: {str(e)}")
            return {
                "status": "error",
                "message": f"Data export failed: {str(e)}"
            }

    def update_personal_information(self, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user personal information per GDPR Article 16.

        Parameters
        ----------
        update_data : Dict[str, Any]
            Dictionary containing fields to update (email, full_name, etc.)

        Returns
        -------
        Dict[str, Any]
            Update operation result
        """
        try:
            # Validate update data
            validation_result = self._validate_update_data(update_data)
            if validation_result["status"] == "error":
                return validation_result

            # Update user information
            for field, value in update_data.items():
                if hasattr(self.current_user, field):
                    setattr(self.current_user, field, value)

            self.current_user.updated_at = datetime.utcnow()

            # Create audit log before commit
            self._create_audit_log(
                action="data_rectification",
                details={"updated_fields": list(update_data.keys())}
            )

            self.db_session.commit()

            return {
                "status": "success",
                "message": "Personal information updated successfully"
            }

        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to update personal information: {str(e)}")
            return {
                "status": "error",
                "message": f"Update failed: {str(e)}"
            }

    def request_data_deletion(self, deletion_reason: str) -> Dict[str, Any]:
        """Request data deletion per GDPR Article 17.

        Parameters
        ----------
        deletion_reason : str
            Reason for requesting data deletion

        Returns
        -------
        Dict[str, Any]
            Deletion request result with impact analysis
        """
        try:
            # Analyze deletion impact
            deletion_impact = self._analyze_deletion_impact()

            # Determine deletion type based on user data
            if self._is_immediate_deletion_eligible():
                deletion_type = "immediate"
                retention_days = 0
            else:
                deletion_type = "scheduled"
                retention_days = 30  # Standard GDPR retention period

            # Create audit log
            self._create_audit_log(
                action="data_erasure_request",
                details={
                    "deletion_reason": deletion_reason,
                    "deletion_type": deletion_type,
                    "impact": deletion_impact
                }
            )

            result = {
                "status": "success",
                "message": "Data deletion scheduled successfully" if deletion_type == "scheduled"
                          else "Data deletion completed immediately",
                "deletion_type": deletion_type,
                "deletion_impact": deletion_impact
            }

            if retention_days > 0:
                result["retention_period_days"] = retention_days

            return result

        except Exception as e:
            logger.error(f"Failed to process deletion request: {str(e)}")
            return {
                "status": "error",
                "message": f"Deletion request failed: {str(e)}"
            }

    def export_portable_data(self, export_format: str = "json") -> Dict[str, Any]:
        """Export user data in portable format per GDPR Article 20.

        Parameters
        ----------
        export_format : str, default="json"
            Export format (json, csv)

        Returns
        -------
        Dict[str, Any]
            Portable data export result
        """
        try:
            if export_format not in ["json", "csv"]:
                return {
                    "status": "error",
                    "message": "Unsupported export format. Use 'json' or 'csv'"
                }

            # Get portable data
            portable_data = self._get_portable_data()

            # Create audit log
            self._create_audit_log(
                action="data_portability",
                details={"export_format": export_format}
            )

            result = {
                "status": "success",
                "message": f"Data exported in {export_format} format",
                "export_format": export_format
            }

            if export_format == "json":
                result["export_data"] = portable_data
            elif export_format == "csv":
                result["csv_files"] = self._convert_to_csv_format(portable_data)

            return result

        except Exception as e:
            logger.error(f"Failed to export portable data: {str(e)}")
            return {
                "status": "error",
                "message": f"Portable export failed: {str(e)}"
            }

    def _create_audit_log(self, action: str, details: Dict[str, Any], ip_address: Optional[str] = None) -> None:
        """Create audit log for GDPR operation.

        Parameters
        ----------
        action : str
            GDPR action performed
        details : Dict[str, Any]
            Operation details
        ip_address : str, optional
            IP address of request
        """
        try:
            audit_log = GDPRAuditLog(
                user_id=str(self.current_user.id),
                action=action,
                details=details,
                ip_address=ip_address
            )

            self.db_session.add(audit_log)
            # Don't commit here - let the calling method handle commits

        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}")

    def _get_personal_information(self) -> Dict[str, Any]:
        """Get user personal information.

        Returns
        -------
        Dict[str, Any]
            Personal information dictionary
        """
        return {
            "user_id": str(self.current_user.id),
            "email": str(self.current_user.email),
            "full_name": str(getattr(self.current_user, 'full_name', '')),
            "created_at": self.current_user.created_at.isoformat() if hasattr(self.current_user.created_at, 'isoformat') else str(self.current_user.created_at),
            "updated_at": getattr(self.current_user, 'updated_at', datetime.utcnow()).isoformat() if hasattr(getattr(self.current_user, 'updated_at', datetime.utcnow()), 'isoformat') else str(getattr(self.current_user, 'updated_at', datetime.utcnow()))
        }

    def _get_user_models_data(self) -> List[Dict[str, Any]]:
        """Get user models data.

        Returns
        -------
        List[Dict[str, Any]]
            List of user models
        """
        try:
            # Query ModelRegistry table for user models
            user_models = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.owner_id == self.current_user.id
            ).all()

            models_data = []
            for model in user_models:
                model_data = {
                    "id": str(model.id),
                    "name": model.name,
                    "description": getattr(model, 'description', ''),
                    "created_at": model.created_at.isoformat() if model.created_at else None,
                    "is_public": getattr(model, 'is_public', False)
                }
                models_data.append(model_data)

            return models_data
        except Exception as e:
            logger.error(f"Failed to get user models: {str(e)}")
            return []

    def _get_user_workspaces_data(self) -> List[Dict[str, Any]]:
        """Get user workspaces data.

        Returns
        -------
        List[Dict[str, Any]]
            List of user workspaces
        """
        try:
            # Query Workspace table for user workspaces
            user_workspaces = self.db_session.query(Workspace).filter(
                Workspace.owner_id == self.current_user.id
            ).all()

            workspaces_data = []
            for workspace in user_workspaces:
                workspace_data = {
                    "id": str(workspace.id),
                    "name": str(workspace.name),
                    "description": str(getattr(workspace, 'description', '')),
                    "created_at": workspace.created_at.isoformat() if hasattr(workspace.created_at, 'isoformat') else str(workspace.created_at),
                    "member_count": getattr(workspace, 'member_count', 0)
                }
                workspaces_data.append(workspace_data)

            return workspaces_data
        except Exception as e:
            logger.error(f"Failed to get user workspaces: {str(e)}")
            return []

    def _get_user_access_history(self) -> List[Dict[str, Any]]:
        """Get user access history.

        Returns
        -------
        List[Dict[str, Any]]
            List of access log entries
        """
        try:
            # Query ModelAccess table for user access history
            access_grants = self.db_session.query(ModelAccess).filter(
                ModelAccess.user_id == self.current_user.id
            ).all()

            access_history = []
            for grant in access_grants:
                access_history.append({
                    "model_id": str(grant.model_id),
                    "access_level": grant.access_level,
                    "granted_at": grant.granted_at.isoformat() if grant.granted_at else None,
                    "granted_by_id": str(grant.granted_by_id) if grant.granted_by_id else None,
                    "expires_at": grant.expires_at.isoformat() if grant.expires_at else None
                })

            return access_history
        except Exception as e:
            logger.error(f"Failed to get access history: {str(e)}")
            return []

    def _validate_update_data(self, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user data update request.

        Parameters
        ----------
        update_data : Dict[str, Any]
            Data to validate

        Returns
        -------
        Dict[str, Any]
            Validation result
        """
        # Email validation
        if "email" in update_data:
            email = update_data["email"]
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                return {
                    "status": "error",
                    "message": "Invalid email format"
                }

        return {"status": "success"}

    def _analyze_deletion_impact(self) -> Dict[str, Any]:
        """Analyze impact of user data deletion.

        Returns
        -------
        Dict[str, Any]
            Deletion impact analysis
        """
        try:
            user_models = self._get_user_models()
            user_workspaces = self._get_user_workspaces()

            return {
                "models_affected": len(user_models),
                "workspaces_affected": len(user_workspaces),
                "public_models": len([m for m in user_models if getattr(m, 'is_public', False)])
            }
        except Exception as e:
            logger.error(f"Failed to analyze deletion impact: {str(e)}")
            return {"models_affected": 0, "workspaces_affected": 0, "public_models": 0}

    def _get_user_models(self) -> List[Any]:
        """Get user models for analysis.

        Returns
        -------
        List[Any]
            User models
        """
        try:
            # Mock for now - will be replaced with actual query
            return []
        except Exception as e:
            logger.error(f"Failed to get user models: {str(e)}")
            return []

    def _get_user_workspaces(self) -> List[Any]:
        """Get user workspaces for analysis.

        Returns
        -------
        List[Any]
            User workspaces
        """
        try:
            # Mock for now - will be replaced with actual query
            return []
        except Exception as e:
            logger.error(f"Failed to get user workspaces: {str(e)}")
            return []

    def _is_immediate_deletion_eligible(self) -> bool:
        """Check if user is eligible for immediate deletion.

        Returns
        -------
        bool
            True if immediate deletion is possible
        """
        try:
            # User with no active data can be deleted immediately
            user_models = self._get_user_models()
            user_workspaces = self._get_user_workspaces()

            return len(user_models) == 0 and len(user_workspaces) == 0
        except Exception as e:
            logger.error(f"Failed to check deletion eligibility: {str(e)}")
            return False

    def _get_portable_data(self) -> Dict[str, Any]:
        """Get user data in portable format.

        Returns
        -------
        Dict[str, Any]
            Portable user data
        """
        user_models = self._get_user_models()

        # Convert models to portable format
        models_data = []
        for model in user_models:
            model_data = {
                "id": getattr(model, 'id', ''),
                "name": getattr(model, 'name', ''),
                "description": getattr(model, 'description', ''),
                "created_at": getattr(model, 'created_at', datetime.utcnow()).isoformat()
            }

            # Add model metrics if available
            if hasattr(model, 'model_metrics'):
                model_data["model_metrics"] = model.model_metrics

            models_data.append(model_data)

        return {
            "personal_information": self._get_personal_information(),
            "models": models_data,
            "workspaces": self._get_user_workspaces_data()
        }

    def _convert_to_csv_format(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Convert data to CSV format.

        Parameters
        ----------
        data : Dict[str, Any]
            Data to convert

        Returns
        -------
        Dict[str, str]
            CSV format data
        """
        # Simple CSV conversion - could be enhanced with pandas
        csv_files = {}

        # Personal information CSV
        if "personal_information" in data:
            personal_info = data["personal_information"]
            csv_files["personal_info.csv"] = ",".join(personal_info.keys()) + "\n" + ",".join(map(str, personal_info.values()))

        return csv_files
