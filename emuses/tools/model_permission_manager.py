"""Model permission management for multi-user EMUSES environment.

This module provides ModelPermissionManager class for handling granular
model access permissions with support for different access levels.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

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

    def _normalize_uuid(self, uuid_input: Union[str, UUID]) -> UUID:
        """Convert string UUID to UUID object if needed.
        
        Parameters
        ----------
        uuid_input : Union[str, UUID]
            UUID as string or UUID object
            
        Returns
        -------
        UUID
            UUID object
            
        Raises
        ------
        ValueError
            If the input is not a valid UUID
        """
        if isinstance(uuid_input, str):
            try:
                return UUID(uuid_input)
            except ValueError:
                raise ValueError(f"Invalid UUID format: {uuid_input}")
        return uuid_input
    
    def check_access(
        self,
        model_id: Union[str, UUID],
        access_level: str = "read",
        user_id: Optional[Union[str, UUID]] = None
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
            # Normalize UUID input
            model_uuid = self._normalize_uuid(model_id)
            
            # Get model
            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == model_uuid
            ).first()
            
            if not model:
                logger.warning(f"Model {model_id} not found for access check")
                return False
            
            # Use current user if not specified  
            if user_id:
                check_user_uuid = self._normalize_uuid(user_id)
            else:
                check_user_uuid = self.current_user.id
            
            # Owner always has full access
            if model.owner_id == check_user_uuid:
                return True
            
            # Public models allow read access to all authenticated users
            if model.is_public and access_level == "read":
                return True
            
            # Check workspace access
            if model.workspace_id:
                workspace = self.db_session.query(Workspace).filter(
                    Workspace.id == model.workspace_id
                ).first()
                
                if workspace and workspace.owner_id == check_user_uuid:
                    # Workspace owner has admin access to all models in workspace
                    return self._access_level_sufficient("admin", access_level)
            
            # Check explicit access grants
            access_grant = self.db_session.query(ModelAccess).filter(
                and_(
                    ModelAccess.model_id == model.id,
                    ModelAccess.user_id == check_user_uuid,
                    # Check if access hasn't expired
                    ModelAccess.expires_at.is_(None) | 
                    (ModelAccess.expires_at > datetime.utcnow())
                )
            ).first()
            
            if access_grant:
                return self._access_level_sufficient(access_grant.access_level, access_level)
            
            # No access found
            return False
            
        except Exception as e:
            logger.error(f"Error checking access for model {model_id}: {str(e)}")
            return False
    
    def grant_access(
        self,
        model_id: Union[str, UUID],
        user_id: Union[str, UUID],
        access_level: str,
        expires_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Grant access to a model for a user.
        
        Parameters
        ----------
        model_id : Union[str, UUID]
            Model identifier
        user_id : Union[str, UUID]
            User ID to grant access to
        access_level : str
            Access level to grant (read, write, admin)
        expires_at : datetime, optional
            When access expires (None for permanent)
            
        Returns
        -------
        Dict[str, Any]
            Grant operation result
        """
        try:
            # Normalize UUID inputs
            model_uuid = self._normalize_uuid(model_id)
            user_uuid = self._normalize_uuid(user_id)
            
            # Validate access level
            if access_level not in self.ACCESS_LEVELS:
                return {
                    "status": "error",
                    "message": f"Invalid access level: {access_level}. Must be one of {self.ACCESS_LEVELS}"
                }
            
            # Cannot grant owner level (only one owner per model)
            if access_level == "owner":
                return {
                    "status": "error",
                    "message": "Cannot grant owner access level. Transfer ownership instead."
                }
            
            # Get model and check permission to grant access
            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == model_uuid
            ).first()
            
            if not model:
                return {
                    "status": "error",
                    "message": f"Model {model_id} not found"
                }
            
            # Check if current user can grant access (must have admin+ access)
            if not self.check_access(model_uuid, "admin"):
                return {
                    "status": "error",
                    "message": "Permission denied: admin access required to grant permissions"
                }
            
            # Verify target user exists
            target_user = self.db_session.query(User).filter(
                User.id == user_uuid
            ).first()
            
            if not target_user:
                return {
                    "status": "error",
                    "message": f"User {user_id} not found"
                }
            
            # Check for existing access grant
            existing_grant = self.db_session.query(ModelAccess).filter(
                and_(
                    ModelAccess.model_id == model.id,
                    ModelAccess.user_id == user_uuid
                )
            ).first()
            
            if existing_grant:
                # Update existing grant
                existing_grant.access_level = access_level
                existing_grant.granted_by_id = self.current_user.id
                existing_grant.granted_at = datetime.utcnow()
                existing_grant.expires_at = expires_at
                
                action = "updated"
            else:
                # Create new grant
                new_grant = ModelAccess(
                    model_id=model.id,
                    user_id=user_uuid,
                    access_level=access_level,
                    granted_by_id=self.current_user.id,
                    expires_at=expires_at
                )
                self.db_session.add(new_grant)
                action = "granted"
            
            self.db_session.commit()
            
            logger.info(f"Access {action} for user {target_user.email} on model {model.name}: {access_level}")
            return {
                "status": "success",
                "message": f"{access_level.title()} access {action} to {target_user.email}",
                "action": action
            }
            
        except IntegrityError as e:
            self.db_session.rollback()
            return {
                "status": "error",
                "message": f"Database constraint error: {str(e)}"
            }
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to grant access: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to grant access: {str(e)}"
            }
    
    def revoke_access(
        self,
        model_id: Union[str, UUID],
        user_id: Union[str, UUID]
    ) -> Dict[str, Any]:
        """Revoke access to a model for a user.
        
        Parameters
        ----------
        model_id : Union[str, UUID]
            Model identifier
        user_id : Union[str, UUID]
            User ID to revoke access from
            
        Returns
        -------
        Dict[str, Any]
            Revoke operation result
        """
        try:
            # Normalize UUID inputs
            model_uuid = self._normalize_uuid(model_id)
            user_uuid = self._normalize_uuid(user_id)
            
            # Get model and check permission to revoke access
            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == model_uuid
            ).first()
            
            if not model:
                return {
                    "status": "error",
                    "message": f"Model {model_id} not found"
                }
            
            # Check if current user can revoke access (must have admin+ access)
            if not self.check_access(model_uuid, "admin"):
                return {
                    "status": "error",
                    "message": "Permission denied: admin access required to revoke permissions"
                }
            
            # Cannot revoke access from owner
            if model.owner_id == user_uuid:
                return {
                    "status": "error",
                    "message": "Cannot revoke access from model owner"
                }
            
            # Find and remove access grant
            access_grant = self.db_session.query(ModelAccess).filter(
                and_(
                    ModelAccess.model_id == model.id,
                    ModelAccess.user_id == user_uuid
                )
            ).first()
            
            if not access_grant:
                return {
                    "status": "error",
                    "message": "No explicit access grant found for this user"
                }
            
            # Get user info for logging
            user = self.db_session.query(User).filter(
                User.id == user_uuid
            ).first()
            
            # Remove access grant
            self.db_session.delete(access_grant)
            self.db_session.commit()
            
            user_email = user.email if user else f"user-{user_id}"
            logger.info(f"Access revoked for user {user_email} on model {model.name}")
            
            return {
                "status": "success",
                "message": f"Access revoked from {user_email}"
            }
            
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to revoke access: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to revoke access: {str(e)}"
            }
    
    def list_permissions(
        self,
        model_id: Union[str, UUID]
    ) -> Dict[str, Any]:
        """List all permissions for a model.
        
        Parameters
        ----------
        model_id : Union[str, UUID]
            Model identifier
            
        Returns
        -------
        Dict[str, Any]
            List of permissions and access details
        """
        try:
            # Normalize UUID input
            model_uuid = self._normalize_uuid(model_id)
            
            # Get model and check access
            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == model_uuid
            ).first()
            
            if not model:
                return {
                    "status": "error",
                    "message": f"Model {model_id} not found"
                }
            
            # Check if current user can view permissions (must have read+ access)
            if not self.check_access(model_uuid, "read"):
                return {
                    "status": "error",
                    "message": "Permission denied: no access to model"
                }
            
            permissions = []
            
            # Add owner permission
            owner = self.db_session.query(User).filter(
                User.id == model.owner_id
            ).first()
            
            if owner:
                permissions.append({
                    "user_id": str(owner.id),
                    "user_email": owner.email,
                    "access_level": "owner",
                    "granted_by": "system",
                    "granted_at": model.created_at.isoformat(),
                    "expires_at": None,
                    "is_owner": True
                })
            
            # Add workspace access if applicable
            if model.workspace_id:
                workspace = self.db_session.query(Workspace).filter(
                    Workspace.id == model.workspace_id
                ).first()
                
                if workspace and workspace.owner_id != model.owner_id:
                    workspace_owner = self.db_session.query(User).filter(
                        User.id == workspace.owner_id
                    ).first()
                    
                    if workspace_owner:
                        permissions.append({
                            "user_id": str(workspace_owner.id),
                            "user_email": workspace_owner.email,
                            "access_level": "admin",
                            "granted_by": "workspace",
                            "granted_at": model.created_at.isoformat(),
                            "expires_at": None,
                            "is_workspace_owner": True
                        })
            
            # Add explicit access grants (using separate queries to avoid join issues)
            access_grants = self.db_session.query(ModelAccess).filter(
                ModelAccess.model_id == model.id
            ).all()
            
            for grant in access_grants:
                # Get the user for this grant
                user = self.db_session.query(User).filter(
                    User.id == grant.user_id
                ).first()
                
                if not user:
                    # Skip grants for users that no longer exist
                    continue
                
                # Get the user who granted access
                granted_by_user = self.db_session.query(User).filter(
                    User.id == grant.granted_by_id
                ).first()
                
                permissions.append({
                    "user_id": str(user.id),
                    "user_email": user.email,
                    "access_level": grant.access_level,
                    "granted_by": granted_by_user.email if granted_by_user else f"user-{grant.granted_by_id}",
                    "granted_at": grant.granted_at.isoformat(),
                    "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
                    "is_explicit": True
                })
            
            return {
                "status": "success",
                "model_id": str(model_uuid),
                "model_name": model.name,
                "is_public": model.is_public,
                "workspace_id": str(model.workspace_id) if model.workspace_id else None,
                "permissions": permissions
            }
            
        except Exception as e:
            logger.error(f"Failed to list permissions for model {model_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to list permissions: {str(e)}"
            }
    
    def transfer_ownership(
        self,
        model_id: Union[str, UUID],
        new_owner_id: Union[str, UUID]
    ) -> Dict[str, Any]:
        """Transfer model ownership to another user.
        
        Parameters
        ----------
        model_id : Union[str, UUID]
            Model identifier
        new_owner_id : Union[str, UUID]
            New owner user ID
            
        Returns
        -------
        Dict[str, Any]
            Transfer operation result
        """
        try:
            # Normalize UUID inputs
            model_uuid = self._normalize_uuid(model_id)
            new_owner_uuid = self._normalize_uuid(new_owner_id)
            
            # Get model
            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == model_uuid
            ).first()
            
            if not model:
                return {
                    "status": "error",
                    "message": f"Model {model_id} not found"
                }
            
            # Only current owner can transfer ownership
            if model.owner_id != self.current_user.id:
                return {
                    "status": "error",
                    "message": "Permission denied: only model owner can transfer ownership"
                }
            
            # Verify new owner exists
            new_owner = self.db_session.query(User).filter(
                User.id == new_owner_uuid
            ).first()
            
            if not new_owner:
                return {
                    "status": "error",
                    "message": f"New owner {new_owner_id} not found"
                }
            
            # Cannot transfer to same user
            if model.owner_id == new_owner_uuid:
                return {
                    "status": "error",
                    "message": "Cannot transfer ownership to current owner"
                }
            
            # Update model owner
            old_owner_email = self.current_user.email
            model.owner_id = new_owner_uuid
            model.updated_at = datetime.utcnow()
            
            # Remove any explicit access grants for the new owner
            # (they now have owner access)
            existing_grant = self.db_session.query(ModelAccess).filter(
                and_(
                    ModelAccess.model_id == model.id,
                    ModelAccess.user_id == new_owner_uuid
                )
            ).first()
            
            if existing_grant:
                self.db_session.delete(existing_grant)
            
            self.db_session.commit()
            
            logger.info(f"Model {model.name} ownership transferred from {old_owner_email} to {new_owner.email}")
            
            return {
                "status": "success",
                "message": f"Ownership transferred to {new_owner.email}",
                "old_owner": old_owner_email,
                "new_owner": new_owner.email
            }
            
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to transfer ownership: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to transfer ownership: {str(e)}"
            }
    
    def make_public(self, model_id: Union[str, UUID], is_public: bool = True) -> Dict[str, Any]:
        """Make a model public or private.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        is_public : bool, default=True
            Whether to make model public or private
            
        Returns
        -------
        Dict[str, Any]
            Operation result
        """
        try:
            # Normalize UUID input
            model_uuid = self._normalize_uuid(model_id)
            
            # Get model
            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == model_uuid
            ).first()
            
            if not model:
                return {
                    "status": "error",
                    "message": f"Model {model_id} not found"
                }
            
            # Check if current user has admin access
            if not self.check_access(model_uuid, "admin"):
                return {
                    "status": "error",
                    "message": "Permission denied: admin access required to change public status"
                }
            
            # Update public status
            old_status = model.is_public
            model.is_public = is_public
            model.updated_at = datetime.utcnow()
            
            self.db_session.commit()
            
            status_word = "public" if is_public else "private"
            action = "made" if old_status != is_public else "already"
            
            logger.info(f"Model {model.name} {action} {status_word}")
            
            return {
                "status": "success",
                "message": f"Model {action} {status_word}",
                "is_public": is_public
            }
            
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to change public status: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to change public status: {str(e)}"
            }
    
    def _access_level_sufficient(self, granted_level: str, required_level: str) -> bool:
        """Check if granted access level is sufficient for required level.
        
        Parameters
        ----------
        granted_level : str
            Access level that user has
        required_level : str
            Access level that is required
            
        Returns
        -------
        bool
            Whether granted level is sufficient
        """
        try:
            granted_index = self.ACCESS_LEVELS.index(granted_level)
            required_index = self.ACCESS_LEVELS.index(required_level)
            return granted_index >= required_index
        except ValueError:
            # Invalid access level
            return False