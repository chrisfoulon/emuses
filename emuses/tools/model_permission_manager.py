"""Model permission management for multi-user EMUSES environment.

This module provides ModelPermissionManager class for handling granular
model access permissions with support for different access levels.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from emuses.multi_user_service.models import ModelAccess, ModelRegistry, User, Workspace

logger = logging.getLogger(__name__)


class ModelPermissionManager:
    """Manager for model access permissions and security.
    
    Provides granular permission management for model access including
    owner-level, workspace-level, and public access controls.
    
    Parameters
    ----------
    db_session : Session
        SQLAlchemy database session
    current_user : User
        Current authenticated user
        
    Attributes
    ----------
    db_session : Session
        Database session for permission operations
    current_user : User
        Current user for permission checks
    """
    
    # Access levels in order of increasing privilege
    ACCESS_LEVELS = ["read", "write", "admin", "owner"]
    
    def __init__(self, db_session: Session, current_user: User):
        """Initialize permission manager.
        
        Parameters
        ----------
        db_session : Session
            Active database session
        current_user : User
            Current authenticated user
        """
        self.db_session = db_session
        self.current_user = current_user
        
        logger.info(f"ModelPermissionManager initialized for user {current_user.email}")
    
    def check_access(
        self,
        model_id: str,
        access_level: str = "read",
        user_id: Optional[str] = None
    ) -> bool:
        """Check if user has required access level to model.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        access_level : str, default="read"
            Required access level (read, write, admin, owner)
        user_id : str, optional
            User ID to check (defaults to current user)
            
        Returns
        -------
        bool
            Whether user has required access level
        """
        try:
            # Get model
            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == model_id
            ).first()
            
            if not model:
                logger.warning(f"Model {model_id} not found for access check")
                return False
            
            # Use current user if not specified
            check_user_id = user_id or str(self.current_user.id)
            
            # Owner always has full access
            if str(model.owner_id) == check_user_id:
                return True
            
            # Public models allow read access to all authenticated users
            if model.is_public and access_level == "read":
                return True
            
            # Check workspace access
            if model.workspace_id:
                workspace = self.db_session.query(Workspace).filter(
                    Workspace.id == model.workspace_id
                ).first()
                
                if workspace and str(workspace.owner_id) == check_user_id:
                    # Workspace owner has admin access to all models in workspace
                    return self._access_level_sufficient("admin", access_level)
            
            # Check explicit access grants
            access_grant = self.db_session.query(ModelAccess).filter(\n                and_(\n                    ModelAccess.model_id == model.id,\n                    ModelAccess.user_id == check_user_id,\n                    # Check if access hasn't expired\n                    ModelAccess.expires_at.is_(None) | \n                    (ModelAccess.expires_at > datetime.utcnow())\n                )\n            ).first()\n            \n            if access_grant:\n                return self._access_level_sufficient(access_grant.access_level, access_level)\n            \n            # No access found\n            return False\n            \n        except Exception as e:\n            logger.error(f"Error checking access for model {model_id}: {str(e)}")\n            return False\n    \n    def grant_access(\n        self,\n        model_id: str,\n        user_id: str,\n        access_level: str,\n        expires_at: Optional[datetime] = None\n    ) -> Dict[str, Any]:\n        """Grant access to a model for a user.\n        \n        Parameters\n        ----------\n        model_id : str\n            Model identifier\n        user_id : str\n            User ID to grant access to\n        access_level : str\n            Access level to grant (read, write, admin)\n        expires_at : datetime, optional\n            When access expires (None for permanent)\n            \n        Returns\n        -------\n        Dict[str, Any]\n            Grant operation result\n        """\n        try:\n            # Validate access level\n            if access_level not in self.ACCESS_LEVELS:\n                return {\n                    "status": "error",\n                    "message": f"Invalid access level: {access_level}. Must be one of {self.ACCESS_LEVELS}"\n                }\n            \n            # Cannot grant owner level (only one owner per model)\n            if access_level == "owner":\n                return {\n                    "status": "error",\n                    "message": "Cannot grant owner access level. Transfer ownership instead."\n                }\n            \n            # Get model and check permission to grant access\n            model = self.db_session.query(ModelRegistry).filter(\n                ModelRegistry.id == model_id\n            ).first()\n            \n            if not model:\n                return {\n                    "status": "error",\n                    "message": f"Model {model_id} not found"\n                }\n            \n            # Check if current user can grant access (must have admin+ access)\n            if not self.check_access(model_id, "admin"):\n                return {\n                    "status": "error",\n                    "message": "Permission denied: admin access required to grant permissions"\n                }\n            \n            # Verify target user exists\n            target_user = self.db_session.query(User).filter(\n                User.id == user_id\n            ).first()\n            \n            if not target_user:\n                return {\n                    "status": "error",\n                    "message": f"User {user_id} not found"\n                }\n            \n            # Check for existing access grant\n            existing_grant = self.db_session.query(ModelAccess).filter(\n                and_(\n                    ModelAccess.model_id == model.id,\n                    ModelAccess.user_id == user_id\n                )\n            ).first()\n            \n            if existing_grant:\n                # Update existing grant\n                existing_grant.access_level = access_level\n                existing_grant.granted_by_id = self.current_user.id\n                existing_grant.granted_at = datetime.utcnow()\n                existing_grant.expires_at = expires_at\n                \n                action = "updated"\n            else:\n                # Create new grant\n                new_grant = ModelAccess(\n                    model_id=model.id,\n                    user_id=user_id,\n                    access_level=access_level,\n                    granted_by_id=self.current_user.id,\n                    expires_at=expires_at\n                )\n                self.db_session.add(new_grant)\n                action = "granted"\n            \n            self.db_session.commit()\n            \n            logger.info(f"Access {action} for user {target_user.email} on model {model.name}: {access_level}")\n            return {\n                "status": "success",\n                "message": f"{access_level.title()} access {action} to {target_user.email}",\n                "action": action\n            }\n            \n        except IntegrityError as e:\n            self.db_session.rollback()\n            return {\n                "status": "error",\n                "message": f"Database constraint error: {str(e)}\"\n            }\n        except Exception as e:\n            self.db_session.rollback()\n            logger.error(f"Failed to grant access: {str(e)}")\n            return {\n                "status": "error",\n                "message": f"Failed to grant access: {str(e)}\"\n            }\n    \n    def revoke_access(\n        self,\n        model_id: str,\n        user_id: str\n    ) -> Dict[str, Any]:\n        """Revoke access to a model for a user.\n        \n        Parameters\n        ----------\n        model_id : str\n            Model identifier\n        user_id : str\n            User ID to revoke access from\n            \n        Returns\n        -------\n        Dict[str, Any]\n            Revoke operation result\n        """\n        try:\n            # Get model and check permission to revoke access\n            model = self.db_session.query(ModelRegistry).filter(\n                ModelRegistry.id == model_id\n            ).first()\n            \n            if not model:\n                return {\n                    "status": "error",\n                    "message": f"Model {model_id} not found"\n                }\n            \n            # Check if current user can revoke access (must have admin+ access)\n            if not self.check_access(model_id, "admin"):\n                return {\n                    "status": "error",\n                    "message": "Permission denied: admin access required to revoke permissions"\n                }\n            \n            # Cannot revoke access from owner\n            if str(model.owner_id) == user_id:\n                return {\n                    "status": "error",\n                    "message": "Cannot revoke access from model owner"\n                }\n            \n            # Find and remove access grant\n            access_grant = self.db_session.query(ModelAccess).filter(\n                and_(\n                    ModelAccess.model_id == model.id,\n                    ModelAccess.user_id == user_id\n                )\n            ).first()\n            \n            if not access_grant:\n                return {\n                    "status": "error",\n                    "message": "No explicit access grant found for this user"\n                }\n            \n            # Get user info for logging\n            user = self.db_session.query(User).filter(\n                User.id == user_id\n            ).first()\n            \n            # Remove access grant\n            self.db_session.delete(access_grant)\n            self.db_session.commit()\n            \n            user_email = user.email if user else f"user-{user_id}"\n            logger.info(f"Access revoked for user {user_email} on model {model.name}")\n            \n            return {\n                "status": "success",\n                "message": f"Access revoked from {user_email}"\n            }\n            \n        except Exception as e:\n            self.db_session.rollback()\n            logger.error(f"Failed to revoke access: {str(e)}")\n            return {\n                "status": "error",\n                "message": f"Failed to revoke access: {str(e)}\"\n            }\n    \n    def list_permissions(\n        self,\n        model_id: str\n    ) -> Dict[str, Any]:\n        """List all permissions for a model.\n        \n        Parameters\n        ----------\n        model_id : str\n            Model identifier\n            \n        Returns\n        -------\n        Dict[str, Any]\n            List of permissions and access details\n        """\n        try:\n            # Get model and check access\n            model = self.db_session.query(ModelRegistry).filter(\n                ModelRegistry.id == model_id\n            ).first()\n            \n            if not model:\n                return {\n                    "status": "error",\n                    "message": f"Model {model_id} not found"\n                }\n            \n            # Check if current user can view permissions (must have read+ access)\n            if not self.check_access(model_id, "read"):\n                return {\n                    "status": "error",\n                    "message": "Permission denied: no access to model"\n                }\n            \n            permissions = []\n            \n            # Add owner permission\n            owner = self.db_session.query(User).filter(\n                User.id == model.owner_id\n            ).first()\n            \n            if owner:\n                permissions.append({\n                    "user_id": str(owner.id),\n                    "user_email": owner.email,\n                    "access_level": "owner",\n                    "granted_by": "system",\n                    "granted_at": model.created_at.isoformat(),\n                    "expires_at": None,\n                    "is_owner": True\n                })\n            \n            # Add workspace access if applicable\n            if model.workspace_id:\n                workspace = self.db_session.query(Workspace).filter(\n                    Workspace.id == model.workspace_id\n                ).first()\n                \n                if workspace and workspace.owner_id != model.owner_id:\n                    workspace_owner = self.db_session.query(User).filter(\n                        User.id == workspace.owner_id\n                    ).first()\n                    \n                    if workspace_owner:\n                        permissions.append({\n                            "user_id": str(workspace_owner.id),\n                            "user_email": workspace_owner.email,\n                            "access_level": "admin",\n                            "granted_by": "workspace",\n                            "granted_at": model.created_at.isoformat(),\n                            "expires_at": None,\n                            "is_workspace_owner": True\n                        })\n            \n            # Add explicit access grants\n            access_grants = self.db_session.query(ModelAccess, User).join(\n                User, ModelAccess.user_id == User.id\n            ).filter(\n                ModelAccess.model_id == model.id\n            ).all()\n            \n            for grant, user in access_grants:\n                granted_by_user = self.db_session.query(User).filter(\n                    User.id == grant.granted_by_id\n                ).first()\n                \n                permissions.append({\n                    "user_id": str(user.id),\n                    "user_email": user.email,\n                    "access_level": grant.access_level,\n                    "granted_by": granted_by_user.email if granted_by_user else f"user-{grant.granted_by_id}",\n                    "granted_at": grant.granted_at.isoformat(),\n                    "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,\n                    "is_explicit": True\n                })\n            \n            return {\n                "status": "success",\n                "model_id": model_id,\n                "model_name": model.name,\n                "is_public": model.is_public,\n                "workspace_id": str(model.workspace_id) if model.workspace_id else None,\n                "permissions": permissions\n            }\n            \n        except Exception as e:\n            logger.error(f"Failed to list permissions for model {model_id}: {str(e)}")\n            return {\n                "status": "error",\n                "message": f"Failed to list permissions: {str(e)}\"\n            }\n    \n    def transfer_ownership(\n        self,\n        model_id: str,\n        new_owner_id: str\n    ) -> Dict[str, Any]:\n        """Transfer model ownership to another user.\n        \n        Parameters\n        ----------\n        model_id : str\n            Model identifier\n        new_owner_id : str\n            New owner user ID\n            \n        Returns\n        -------\n        Dict[str, Any]\n            Transfer operation result\n        """\n        try:\n            # Get model\n            model = self.db_session.query(ModelRegistry).filter(\n                ModelRegistry.id == model_id\n            ).first()\n            \n            if not model:\n                return {\n                    "status": "error",\n                    "message": f"Model {model_id} not found"\n                }\n            \n            # Only current owner can transfer ownership\n            if str(model.owner_id) != str(self.current_user.id):\n                return {\n                    "status": "error",\n                    "message": "Permission denied: only model owner can transfer ownership"\n                }\n            \n            # Verify new owner exists\n            new_owner = self.db_session.query(User).filter(\n                User.id == new_owner_id\n            ).first()\n            \n            if not new_owner:\n                return {\n                    "status": "error",\n                    "message": f"New owner {new_owner_id} not found"\n                }\n            \n            # Cannot transfer to same user\n            if str(model.owner_id) == new_owner_id:\n                return {\n                    "status": "error",\n                    "message": "Cannot transfer ownership to current owner"\n                }\n            \n            # Update model owner\n            old_owner_email = self.current_user.email\n            model.owner_id = new_owner.id\n            model.updated_at = datetime.utcnow()\n            \n            # Remove any explicit access grants for the new owner\n            # (they now have owner access)\n            existing_grant = self.db_session.query(ModelAccess).filter(\n                and_(\n                    ModelAccess.model_id == model.id,\n                    ModelAccess.user_id == new_owner_id\n                )\n            ).first()\n            \n            if existing_grant:\n                self.db_session.delete(existing_grant)\n            \n            self.db_session.commit()\n            \n            logger.info(f"Model {model.name} ownership transferred from {old_owner_email} to {new_owner.email}")\n            \n            return {\n                "status": "success",\n                "message": f"Ownership transferred to {new_owner.email}",\n                "old_owner": old_owner_email,\n                "new_owner": new_owner.email\n            }\n            \n        except Exception as e:\n            self.db_session.rollback()\n            logger.error(f"Failed to transfer ownership: {str(e)}")\n            return {\n                "status": "error",\n                "message": f"Failed to transfer ownership: {str(e)}\"\n            }\n    \n    def make_public(self, model_id: str, is_public: bool = True) -> Dict[str, Any]:\n        """Make a model public or private.\n        \n        Parameters\n        ----------\n        model_id : str\n            Model identifier\n        is_public : bool, default=True\n            Whether to make model public or private\n            \n        Returns\n        -------\n        Dict[str, Any]\n            Operation result\n        """\n        try:\n            # Get model\n            model = self.db_session.query(ModelRegistry).filter(\n                ModelRegistry.id == model_id\n            ).first()\n            \n            if not model:\n                return {\n                    "status": "error",\n                    "message": f"Model {model_id} not found"\n                }\n            \n            # Check if current user has admin access\n            if not self.check_access(model_id, "admin"):\n                return {\n                    "status": "error",\n                    "message": "Permission denied: admin access required to change public status"\n                }\n            \n            # Update public status\n            old_status = model.is_public\n            model.is_public = is_public\n            model.updated_at = datetime.utcnow()\n            \n            self.db_session.commit()\n            \n            status_word = "public" if is_public else "private"\n            action = "made" if old_status != is_public else "already"\n            \n            logger.info(f"Model {model.name} {action} {status_word}")\n            \n            return {\n                "status": "success",\n                "message": f"Model {action} {status_word}",\n                "is_public": is_public\n            }\n            \n        except Exception as e:\n            self.db_session.rollback()\n            logger.error(f"Failed to change public status: {str(e)}")\n            return {\n                "status": "error",\n                "message": f"Failed to change public status: {str(e)}\"\n            }\n    \n    def _access_level_sufficient(self, granted_level: str, required_level: str) -> bool:\n        """Check if granted access level is sufficient for required level.\n        \n        Parameters\n        ----------\n        granted_level : str\n            Access level that user has\n        required_level : str\n            Access level that is required\n            \n        Returns\n        -------\n        bool\n            Whether granted level is sufficient\n        """\n        try:\n            granted_index = self.ACCESS_LEVELS.index(granted_level)\n            required_index = self.ACCESS_LEVELS.index(required_level)\n            return granted_index >= required_index\n        except ValueError:\n            # Invalid access level\n            return False