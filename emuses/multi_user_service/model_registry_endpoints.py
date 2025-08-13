"""Model registry endpoints for multi-user EMUSES service.

This module provides RESTful API endpoints for model registry operations
including model registration, discovery, permission management, and download tracking
with proper authentication and user isolation.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from emuses.multi_user_service.auth import fastapi_users
from emuses.multi_user_service.database import get_db
from emuses.multi_user_service.models import User
from emuses.tools.database_model_registry import DatabaseModelRegistry
from emuses.tools.model_permission_manager import ModelPermissionManager
from emuses.tools.model_registry_health import get_health_checker

logger = logging.getLogger(__name__)


class ModelRegisterRequest(BaseModel):
    """Model registration request schema.
    
    Schema for registering new models in the registry.
    
    Attributes
    ----------
    name : str, optional
        Custom model name (uses manifest name if not provided)
    workspace_id : str, optional
        Workspace ID for workspace-scoped models
    is_public : bool, default=False
        Whether model should be publicly accessible
    tags : List[str], optional
        Model tags for categorization
    description : str, optional
        Model description
    """
    name: Optional[str] = None
    workspace_id: Optional[str] = None
    is_public: bool = False
    tags: Optional[List[str]] = Field(default_factory=list)
    description: Optional[str] = None


class ModelResponse(BaseModel):
    """Model information response schema.
    
    Schema for returning model information in API responses.
    
    Attributes
    ----------
    model_id : str
        Model UUID
    name : str
        Model name
    version : str
        Model version
    type : str, optional
        Model type
    description : str, optional
        Model description
    tags : List[str]
        Model tags
    is_public : bool
        Whether model is public
    owner_id : str
        Owner user UUID
    workspace_id : str, optional
        Workspace UUID if workspace-scoped
    created_at : datetime
        Creation timestamp
    updated_at : datetime
        Last update timestamp
    download_count : int
        Number of downloads
    size_mb : float, optional
        Model size in MB
    """
    model_id: str
    name: str
    version: str
    type: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    is_public: bool = False
    owner_id: str
    workspace_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    download_count: int = 0
    size_mb: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ModelSearchQuery(BaseModel):
    """Model search query parameters.
    
    Attributes
    ----------
    query : str
        Search query string
    workspace_id : str, optional
        Limit search to specific workspace
    include_public : bool, default=True
        Whether to include public models
    model_type : str, optional
        Filter by model type
    tags : List[str], optional
        Filter by tags
    limit : int, default=50
        Maximum number of results
    """
    query: str = ""
    workspace_id: Optional[str] = None
    include_public: bool = True
    model_type: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    limit: int = Field(default=50, le=100)


class AccessGrantRequest(BaseModel):
    """Access grant request schema.
    
    Attributes
    ----------
    user_id : str
        User ID to grant access to
    access_level : str
        Access level (read, write, admin)
    expires_at : datetime, optional
        When access expires
    """
    user_id: str
    access_level: str = Field(pattern=r"^(read|write|admin)$")
    expires_at: Optional[datetime] = None


class PermissionResponse(BaseModel):
    """Permission information response schema.
    
    Attributes
    ----------
    user_id : str
        User UUID
    user_email : str
        User email
    access_level : str
        Access level
    granted_by : str
        Who granted the access
    granted_at : datetime
        When access was granted
    expires_at : datetime, optional
        When access expires
    """
    user_id: str
    user_email: str
    access_level: str
    granted_by: str
    granted_at: datetime
    expires_at: Optional[datetime] = None


def get_model_registry_router() -> APIRouter:
    """Get model registry API router.
    
    Returns
    -------
    APIRouter
        Configured model registry router with all endpoints
    """
    router = APIRouter(prefix="/api/v1/models", tags=["Model Registry"])

    @router.post("/register", response_model=Dict[str, Any])
    async def register_model(
        model_file: UploadFile = File(..., description="Model file or archive"),
        name: Optional[str] = Form(None),
        workspace_id: Optional[str] = Form(None),
        is_public: bool = Form(False),
        tags: Optional[str] = Form(None, description="Comma-separated tags"),
        description: Optional[str] = Form(None),
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        db: Session = Depends(get_db)
    ):
        """Register a new model in the registry.
        
        Upload and register a model file or archive with metadata.
        Supports workspace-scoped models and public sharing.
        
        Parameters
        ----------
        model_file : UploadFile
            Model file or archive to upload
        name : str, optional
            Custom model name
        workspace_id : str, optional
            Workspace ID for workspace models
        is_public : bool, default=False
            Whether to make model publicly accessible
        tags : str, optional
            Comma-separated list of tags
        description : str, optional
            Model description
        current_user : User
            Current authenticated user
        db : Session
            Database session
            
        Returns
        -------
        Dict[str, Any]
            Registration result with model_id and status
            
        Raises
        ------
        HTTPException
            If registration fails or validation errors occur
        """
        try:
            import tempfile
            from pathlib import Path
            
            # Parse tags if provided
            tag_list = []
            if tags:
                tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            
            # Save uploaded file to temporary location
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{model_file.filename}") as tmp_file:
                content = await model_file.read()
                tmp_file.write(content)
                tmp_path = Path(tmp_file.name)
            
            try:
                # Initialize registry
                registry = DatabaseModelRegistry(db, current_user)
                
                # Register model
                result = registry.register_model(
                    model_path=tmp_path,
                    name=name,
                    workspace_id=workspace_id,
                    is_public=is_public,
                    tags=tag_list,
                    description=description
                )
                
                if result["status"] == "error":
                    if result.get("error_type") == "validation_error":
                        raise HTTPException(status_code=400, detail=result["message"])
                    elif result.get("error_type") == "permission_error":
                        raise HTTPException(status_code=403, detail=result["message"])
                    elif result.get("error_type") == "conflict_error":
                        raise HTTPException(status_code=409, detail=result["message"])
                    else:
                        raise HTTPException(status_code=500, detail=result["message"])
                
                return result
                
            finally:
                # Cleanup temporary file
                if tmp_path.exists():
                    tmp_path.unlink()
                    
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error registering model: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

    @router.get("/", response_model=List[ModelResponse])
    async def list_models(
        workspace_id: Optional[str] = Query(None, description="Filter by workspace"),
        include_public: bool = Query(True, description="Include public models"),
        model_type: Optional[str] = Query(None, description="Filter by model type"),
        tags: Optional[List[str]] = Query(None, description="Filter by tags"),
        limit: int = Query(50, le=100, description="Maximum number of results"),
        offset: int = Query(0, ge=0, description="Number of results to skip for pagination"),
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        db: Session = Depends(get_db)
    ):
        """List models accessible to the current user.
        
        Returns models owned by the user, in their workspaces, or public models
        with optional filtering by workspace, type, and tags.
        
        Parameters
        ----------
        workspace_id : str, optional
            Filter to specific workspace
        include_public : bool, default=True
            Whether to include public models
        model_type : str, optional
            Filter by model type
        tags : List[str], optional
            Filter by tags (all must be present)
        limit : int, default=50
            Maximum number of results (max 100)
        offset : int, default=0
            Number of results to skip for pagination
        current_user : User
            Current authenticated user
        db : Session
            Database session
            
        Returns
        -------
        List[ModelResponse]
            List of accessible models
        """
        try:
            registry = DatabaseModelRegistry(db, current_user)
            
            # Build filters
            filters = {}
            if model_type:
                filters["type"] = model_type
            if tags:
                filters["tags"] = tags
            
            # Get models with database-level pagination
            models = registry.list_models(
                workspace_id=workspace_id,
                include_public=include_public,
                filters=filters,
                limit=limit,
                offset=offset
            )
            
            return [ModelResponse(**model) for model in models]
            
        except Exception as e:
            logger.error(f"Error listing models: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")

    @router.get("/search", response_model=List[ModelResponse])
    async def search_models(
        query: str = Query(..., description="Search query"),
        workspace_id: Optional[str] = Query(None, description="Filter by workspace"),
        include_public: bool = Query(True, description="Include public models"),
        limit: int = Query(50, le=100, description="Maximum number of results"),
        offset: int = Query(0, ge=0, description="Number of results to skip for pagination"),
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        db: Session = Depends(get_db)
    ):
        """Search models by name, description, and tags.
        
        Performs full-text search across model metadata with relevance ranking.
        
        Parameters
        ----------
        query : str
            Search query string
        workspace_id : str, optional
            Limit search to specific workspace
        include_public : bool, default=True
            Whether to include public models
        limit : int, default=50
            Maximum number of results (max 100)
        offset : int, default=0
            Number of results to skip for pagination
        current_user : User
            Current authenticated user
        db : Session
            Database session
            
        Returns
        -------
        List[ModelResponse]
            List of matching models ordered by relevance
        """
        try:
            registry = DatabaseModelRegistry(db, current_user)
            
            # Search models with database-level pagination
            models = registry.search_models(
                query=query,
                workspace_id=workspace_id,
                include_public=include_public,
                limit=limit,
                offset=offset
            )
            
            return [ModelResponse(**model) for model in models]
            
        except Exception as e:
            logger.error(f"Error searching models: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    @router.get("/{model_id}", response_model=Dict[str, Any])
    async def get_model_info(
        model_id: str,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        db: Session = Depends(get_db)
    ):
        """Get detailed information about a specific model.
        
        Returns comprehensive model metadata including manifest information,
        permission details, and usage statistics.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        current_user : User
            Current authenticated user
        db : Session
            Database session
            
        Returns
        -------
        Dict[str, Any]
            Detailed model information
            
        Raises
        ------
        HTTPException
            If model not found or not accessible
        """
        try:
            registry = DatabaseModelRegistry(db, current_user)
            
            model_info = registry.get_model_info(model_id)
            
            if not model_info:
                raise HTTPException(status_code=404, detail="Model not found or not accessible")
            
            return model_info
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting model info: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get model info: {str(e)}")

    @router.delete("/{model_id}", response_model=Dict[str, Any])
    async def remove_model(
        model_id: str,
        cleanup_files: bool = Query(True, description="Whether to remove model files"),
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        db: Session = Depends(get_db)
    ):
        """Remove a model from the registry.
        
        Removes model from database and optionally cleans up associated files.
        Only model owners can remove models.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        cleanup_files : bool, default=True
            Whether to remove model files from storage
        current_user : User
            Current authenticated user
        db : Session
            Database session
            
        Returns
        -------
        Dict[str, Any]
            Removal result status
            
        Raises
        ------
        HTTPException
            If model not found or permission denied
        """
        try:
            registry = DatabaseModelRegistry(db, current_user)
            
            result = registry.remove_model(model_id, cleanup_files=cleanup_files)
            
            if result["status"] == "error":
                if "not found" in result["message"]:
                    raise HTTPException(status_code=404, detail=result["message"])
                elif "Permission denied" in result["message"]:
                    raise HTTPException(status_code=403, detail=result["message"])
                else:
                    raise HTTPException(status_code=500, detail=result["message"])
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error removing model: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to remove model: {str(e)}")

    @router.post("/{model_id}/download", response_model=Dict[str, Any])
    async def track_download(
        model_id: str,
        download_method: str = Query("api", description="Download method"),
        user_agent: Optional[str] = Query(None, description="User agent string"),
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        db: Session = Depends(get_db)
    ):
        """Track a model download for analytics.
        
        Records download event with metadata for usage tracking and analytics.
        Updates model download count and last accessed timestamp.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        download_method : str, default="api"
            Download method (api, cli, web)
        user_agent : str, optional
            User agent string from request
        current_user : User
            Current authenticated user
        db : Session
            Database session
            
        Returns
        -------
        Dict[str, Any]
            Download tracking result
            
        Raises
        ------
        HTTPException
            If model not found or not accessible
        """
        try:
            registry = DatabaseModelRegistry(db, current_user)
            
            result = registry.track_download(
                model_id=model_id,
                download_method=download_method,
                user_agent=user_agent
            )
            
            if result["status"] == "error":
                if "not found" in result["message"] or "not accessible" in result["message"]:
                    raise HTTPException(status_code=404, detail=result["message"])
                else:
                    raise HTTPException(status_code=500, detail=result["message"])
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error tracking download: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to track download: {str(e)}")

    @router.get("/{model_id}/permissions", response_model=Dict[str, Any])
    async def list_model_permissions(
        model_id: str,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        db: Session = Depends(get_db)
    ):
        """List all permissions for a model.
        
        Shows owner, workspace, and explicit access permissions.
        Requires read access to the model.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        current_user : User
            Current authenticated user
        db : Session
            Database session
            
        Returns
        -------
        Dict[str, Any]
            List of permissions and access details
            
        Raises
        ------
        HTTPException
            If model not found or permission denied
        """
        try:
            permission_manager = ModelPermissionManager(db, current_user)
            
            result = permission_manager.list_permissions(model_id)
            
            if result["status"] == "error":
                if "not found" in result["message"]:
                    raise HTTPException(status_code=404, detail=result["message"])
                elif "Permission denied" in result["message"]:
                    raise HTTPException(status_code=403, detail=result["message"])
                else:
                    raise HTTPException(status_code=500, detail=result["message"])
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error listing permissions: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to list permissions: {str(e)}")

    @router.post("/{model_id}/permissions", response_model=Dict[str, Any])
    async def grant_model_access(
        model_id: str,
        request: AccessGrantRequest,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        db: Session = Depends(get_db)
    ):
        """Grant access to a model for a user.
        
        Grants specified access level to a user for a model.
        Requires admin access to the model.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        request : AccessGrantRequest
            Access grant details
        current_user : User
            Current authenticated user
        db : Session
            Database session
            
        Returns
        -------
        Dict[str, Any]
            Grant operation result
            
        Raises
        ------
        HTTPException
            If model not found, permission denied, or invalid request
        """
        try:
            permission_manager = ModelPermissionManager(db, current_user)
            
            result = permission_manager.grant_access(
                model_id=model_id,
                user_id=request.user_id,
                access_level=request.access_level,
                expires_at=request.expires_at
            )
            
            if result["status"] == "error":
                if "not found" in result["message"]:
                    raise HTTPException(status_code=404, detail=result["message"])
                elif "Permission denied" in result["message"]:
                    raise HTTPException(status_code=403, detail=result["message"])
                elif "Invalid access level" in result["message"]:
                    raise HTTPException(status_code=400, detail=result["message"])
                else:
                    raise HTTPException(status_code=500, detail=result["message"])
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error granting access: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to grant access: {str(e)}")

    @router.delete("/{model_id}/permissions/{user_id}", response_model=Dict[str, Any])
    async def revoke_model_access(
        model_id: str,
        user_id: str,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        db: Session = Depends(get_db)
    ):
        """Revoke access to a model for a user.
        
        Removes explicit access grant for a user to a model.
        Requires admin access to the model.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        user_id : str
            User ID to revoke access from
        current_user : User
            Current authenticated user
        db : Session
            Database session
            
        Returns
        -------
        Dict[str, Any]
            Revoke operation result
            
        Raises
        ------
        HTTPException
            If model not found, permission denied, or no grant exists
        """
        try:
            permission_manager = ModelPermissionManager(db, current_user)
            
            result = permission_manager.revoke_access(model_id, user_id)
            
            if result["status"] == "error":
                if "not found" in result["message"]:
                    raise HTTPException(status_code=404, detail=result["message"])
                elif "Permission denied" in result["message"]:
                    raise HTTPException(status_code=403, detail=result["message"])
                elif "No explicit access grant" in result["message"]:
                    raise HTTPException(status_code=400, detail=result["message"])
                else:
                    raise HTTPException(status_code=500, detail=result["message"])
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error revoking access: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to revoke access: {str(e)}")

    @router.put("/{model_id}/public", response_model=Dict[str, Any])
    async def set_model_public_status(
        model_id: str,
        is_public: bool = Query(..., description="Whether to make model public"),
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        db: Session = Depends(get_db)
    ):
        """Change public status of a model.
        
        Makes a model public or private. Public models are accessible
        to all authenticated users for read access.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        is_public : bool
            Whether to make model public or private
        current_user : User
            Current authenticated user
        db : Session
            Database session
            
        Returns
        -------
        Dict[str, Any]
            Operation result
            
        Raises
        ------
        HTTPException
            If model not found or permission denied
        """
        try:
            permission_manager = ModelPermissionManager(db, current_user)
            
            result = permission_manager.make_public(model_id, is_public)
            
            if result["status"] == "error":
                if "not found" in result["message"]:
                    raise HTTPException(status_code=404, detail=result["message"])
                elif "Permission denied" in result["message"]:
                    raise HTTPException(status_code=403, detail=result["message"])
                else:
                    raise HTTPException(status_code=500, detail=result["message"])
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error setting public status: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to set public status: {str(e)}")

    # Health check endpoints for registry monitoring
    @router.get("/health", response_model=Dict[str, Any])
    async def registry_health_check():
        """Check health status of model registry across all deployment modes.
        
        Provides overall health status with mode-specific details for monitoring
        and service discovery purposes.
        
        Returns
        -------
        Dict[str, Any]
            Health status including overall status and registry mode details
        """
        try:
            health_checker = get_health_checker()
            return health_checker.check_overall_health()
        except Exception as e:
            logger.error(f"Error checking registry health: {str(e)}")
            # Return degraded status instead of failing completely
            return {
                "status": "unhealthy",
                "registry_modes": {},
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/health/detailed", response_model=Dict[str, Any])
    async def registry_detailed_health_check():
        """Check detailed health status with system information and metrics.
        
        Provides comprehensive health information including system details,
        performance metrics, and extended diagnostic information.
        
        Returns
        -------
        Dict[str, Any]
            Detailed health status with system and performance information
        """
        try:
            health_checker = get_health_checker()
            return health_checker.check_detailed_health()
        except Exception as e:
            logger.error(f"Error checking detailed registry health: {str(e)}")
            return {
                "overall_status": "unhealthy",
                "registry_modes": {},
                "system_info": {},
                "performance_metrics": {},
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/ready", response_model=Dict[str, Any])
    async def registry_readiness_check():
        """Check if registry is ready to handle requests.
        
        Used for service discovery and rolling deployments to determine
        when the service is ready to receive traffic.
        
        Returns
        -------
        Dict[str, Any]
            Readiness status with dependency information
        """
        try:
            health_checker = get_health_checker()
            readiness = health_checker.check_readiness()
            
            # Return appropriate HTTP status
            status_code = 200 if readiness["ready"] else 503
            return JSONResponse(
                status_code=status_code,
                content=readiness
            )
        except Exception as e:
            logger.error(f"Error checking registry readiness: {str(e)}")
            return JSONResponse(
                status_code=503,
                content={
                    "ready": False,
                    "dependencies": {},
                    "error": str(e),
                    "timestamp": datetime.now().isoformat() + "Z"
                }
            )

    @router.get("/live", response_model=Dict[str, Any])
    async def registry_liveness_check():
        """Check if registry is alive and responsive.
        
        Used for load balancing and health monitoring to determine
        if the service is functioning properly.
        
        Returns
        -------
        Dict[str, Any]
            Liveness status
        """
        try:
            health_checker = get_health_checker()
            return health_checker.check_liveness()
        except Exception as e:
            logger.error(f"Error checking registry liveness: {str(e)}")
            return {
                "alive": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    return router


def setup_model_registry_endpoints(app):
    """Set up model registry endpoints on FastAPI application.
    
    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance to configure
    """
    logger.info("Setting up model registry endpoints")
    
    router = get_model_registry_router()
    app.include_router(router)
    
    logger.info("Model registry endpoints configured")