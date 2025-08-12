"""Database-backed model registry implementation.

This module provides a database-backed model registry for multi-user EMUSES
environments with comprehensive permission management, workspace integration,
and full-text search capabilities.
"""

import hashlib
import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from emuses.multi_user_service.models import (
    User, ModelRegistry, ModelAccess, ModelDownload, Workspace
)
from emuses.tools.model_permission_manager import ModelPermissionManager
from emuses.tools.local_model_registry import LocalModelRegistry
from emuses.tools.model_registry_cache import ModelRegistryCache

logger = logging.getLogger(__name__)


class DatabaseModelRegistryError(Exception):
    """Base exception for database model registry operations."""
    pass


class ModelNotFoundError(DatabaseModelRegistryError):
    """Exception when a model is not found in the registry."""
    pass


class ModelAccessError(DatabaseModelRegistryError):
    """Exception for model access permissions."""
    pass


class ModelValidationError(DatabaseModelRegistryError):
    """Exception for model validation errors."""
    pass


class DatabaseModelRegistry:
    """Database-backed model registry with multi-user support.
    
    Provides comprehensive model management with database persistence,
    user-based permissions, workspace integration, and full-text search.
    
    Parameters
    ----------
    db_session : Session
        SQLAlchemy database session
    current_user : User
        Current user for access control context
    storage_path : Path, optional
        Base storage path for model files. Defaults to ~/.emuses/models
    
    Attributes
    ----------
    db : Session
        Database session
    current_user : User
        Current user context
    storage_path : Path
        Base storage directory
    permission_manager : ModelPermissionManager
        Permission management system
    """
    
    def __init__(
        self, 
        db_session: Session, 
        current_user: User, 
        base_path: Optional[Path] = None,
        cache: Optional[ModelRegistryCache] = None
    ):
        """Initialize database model registry.
        
        Parameters
        ----------
        db_session : Session
            Database session for persistence operations
        current_user : User
            Current user for permission context
        base_path : Path, optional
            Custom base storage path. If None, uses default location
        cache : ModelRegistryCache, optional
            Cache instance for performance optimization. Creates default if None
        """
        self.db_session = db_session
        self.current_user = current_user
        self.permission_manager = ModelPermissionManager(db_session, current_user)
        self.cache = cache or ModelRegistryCache()
        
        # Initialize storage directory
        if base_path is None:
            base_path = Path("/shared/emuses/models")
        self.base_path = Path(base_path)
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            # For testing or environments where /shared is not available
            logger.warning(f"Could not create default path {base_path}: {e}")
            # Fall back to user directory
            fallback_path = Path.home() / ".emuses" / "models"
            fallback_path.mkdir(parents=True, exist_ok=True)
            self.base_path = fallback_path
        
        logger.info(f"Initialized DatabaseModelRegistry for user {current_user.email}")
    
    def _compute_model_hash(self, model_path: Path) -> str:
        """Compute SHA-256 hash of model directory.
        
        Parameters
        ----------
        model_path : Path
            Path to model directory
            
        Returns
        -------
        str
            SHA-256 hash hex string
        """
        hasher = hashlib.sha256()
        
        for file_path in sorted(model_path.rglob("*")):
            if file_path.is_file():
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hasher.update(chunk)
                        
        return hasher.hexdigest()
    
    def _get_model_size(self, model_path: Path) -> int:
        """Calculate total size of model directory in bytes.
        
        Parameters
        ----------
        model_path : Path
            Path to model directory
            
        Returns
        -------
        int
            Total size in bytes
        """
        total_size = 0
        for file_path in model_path.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size
    
    def _get_user_storage_path(self, user_id: UUID) -> Path:
        """Get storage path for a specific user.
        
        Parameters
        ----------
        user_id : UUID
            User identifier
            
        Returns
        -------
        Path
            User-specific storage path
        """
        user_path = self.base_path / str(user_id)
        user_path.mkdir(exist_ok=True)
        return user_path
    
    def register_model(
        self,
        model_path: Path,
        name: Optional[str] = None,
        version: str = "1.0.0",
        workspace_id: Optional[str] = None,
        is_public: bool = False,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        model_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register a model in the database registry.
        
        Stores model files and metadata in the database with proper
        permission setup and integrity verification.
        
        Parameters
        ----------
        model_path : Path
            Path to model files or directory
        name : str, optional
            Custom model name. If None, uses directory name
        version : str, default="1.0.0"
            Model version string
        workspace_id : str, optional
            Workspace ID for workspace-scoped models
        is_public : bool, default=False
            Whether model should be publicly accessible
        description : str, optional
            Model description
        tags : List[str], optional
            Model tags for categorization
        model_type : str, optional
            Type of model (auto-detected if None)
            
        Returns
        -------
        Dict[str, Any]
            Registration result with model_id and status
            
        Raises
        ------
        ModelValidationError
            If model validation fails
        DatabaseModelRegistryError
            If registration fails
        """
        try:
            # Validate input
            if not model_path.exists():
                return {
                    "status": "error",
                    "error_type": "validation_error",
                    "message": f"Model path does not exist: {model_path}"
                }
            
            # Handle both files and directories
            if model_path.is_file():
                # Extract file to temporary directory
                temp_dir = Path(tempfile.mkdtemp(prefix="emuses_model_"))
                try:
                    if model_path.suffix in ['.tar', '.tar.gz', '.zip']:
                        # Extract archive
                        import tarfile
                        import zipfile
                        
                        if model_path.suffix == '.zip':
                            with zipfile.ZipFile(model_path, 'r') as zip_ref:
                                zip_ref.extractall(temp_dir)
                        else:
                            with tarfile.open(model_path, 'r:*') as tar:
                                tar.extractall(temp_dir)
                        
                        # Find the extracted model directory
                        extracted_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]
                        if extracted_dirs:
                            model_path = extracted_dirs[0]
                        else:
                            model_path = temp_dir
                    else:
                        # Single file, copy to temp directory
                        single_file_dir = temp_dir / "model"
                        single_file_dir.mkdir()
                        shutil.copy2(model_path, single_file_dir)
                        model_path = single_file_dir
                finally:
                    # Cleanup will happen after processing
                    pass
            
            # Generate model ID and determine name
            model_id = str(uuid4())
            if name is None:
                name = model_path.name
            
            if tags is None:
                tags = []
            
            # Compute model metadata
            model_hash = self._compute_model_hash(model_path)
            model_size = self._get_model_size(model_path)
            
            # Validate workspace access if specified
            if workspace_id:
                workspace = self.db_session.query(Workspace).filter(
                    Workspace.id == UUID(workspace_id),
                    Workspace.owner_id == self.current_user.id
                ).first()
                
                if not workspace:
                    return {
                        "status": "error",
                        "error_type": "permission_error",
                        "message": f"Workspace not found or access denied: {workspace_id}"
                    }
            
            # Check for duplicate models (same name and version in same workspace/user scope)
            existing_query = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.name == name,
                ModelRegistry.version == version,
                ModelRegistry.owner_id == self.current_user.id
            )
            
            if workspace_id:
                existing_query = existing_query.filter(ModelRegistry.workspace_id == UUID(workspace_id))
            else:
                existing_query = existing_query.filter(ModelRegistry.workspace_id.is_(None))
            
            existing_model = existing_query.first()
            if existing_model:
                return {
                    "status": "error",
                    "error_type": "conflict_error",
                    "message": f"Model {name} v{version} already exists"
                }
            
            # Copy model to user storage
            user_storage = self._get_user_storage_path(self.current_user.id)
            target_path = user_storage / model_id
            
            if target_path.exists():
                shutil.rmtree(target_path)
            
            shutil.copytree(model_path, target_path)
            
            # Auto-detect model type if not specified
            if model_type is None:
                model_type = self._detect_model_type(target_path)
            
            # Create database record
            model_record = ModelRegistry(
                id=UUID(model_id),
                name=name,
                version=version,
                owner_id=self.current_user.id,
                workspace_id=UUID(workspace_id) if workspace_id else None,
                is_public=is_public,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                model_path=str(target_path),
                manifest_hash=model_hash,
                model_size_bytes=model_size,
                description=description or "",
                tags=tags,
                model_type=model_type,
                download_count=0,
                last_accessed=datetime.utcnow()
            )
            
            self.db_session.add(model_record)
            self.db_session.commit()
            
            logger.info(f"Registered model {name} v{version} with ID {model_id}")
            
            return {
                "status": "success",
                "model_id": model_id,
                "message": f"Model {name} v{version} registered successfully",
                "model_size_bytes": model_size,
                "storage_path": str(target_path)
            }
            
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to register model: {e}")
            return {
                "status": "error",
                "error_type": "internal_error",
                "message": f"Registration failed: {str(e)}"
            }
    
    def _detect_model_type(self, model_path: Path) -> str:
        """Auto-detect model type from files.
        
        Parameters
        ----------
        model_path : Path
            Path to model directory
            
        Returns
        -------
        str
            Detected model type
        """
        # Check for common model files
        files = [f.name.lower() for f in model_path.rglob("*") if f.is_file()]
        
        if any("umap" in f for f in files):
            return "umap"
        elif any(f.endswith(('.pkl', '.joblib')) for f in files):
            return "scikit-learn"
        elif any(f.endswith('.h5') or f.endswith('.keras') for f in files):
            return "tensorflow"
        elif any(f.endswith('.pth') or f.endswith('.pt') for f in files):
            return "pytorch"
        elif any("model.json" in f for f in files):
            return "keras"
        else:
            return "unknown"
    
    def list_models(
        self,
        workspace_id: Optional[str] = None,
        include_public: bool = True,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """List models accessible to the current user.
        
        Parameters
        ----------
        workspace_id : str, optional
            Filter to specific workspace
        include_public : bool, default=True
            Whether to include public models
        filters : Dict[str, Any], optional
            Additional filters (type, tags, etc.)
            
        Returns
        -------
        List[Dict[str, Any]]
            List of accessible models
        """
        query = self.db_session.query(ModelRegistry)
        
        # Base access control
        access_conditions = [ModelRegistry.owner_id == self.current_user.id]
        
        if include_public:
            access_conditions.append(ModelRegistry.is_public == True)
        
        # Add workspace access for models in user's workspaces
        user_workspaces = self.db_session.query(Workspace.id).filter(
            Workspace.owner_id == self.current_user.id
        ).subquery()
        
        access_conditions.append(ModelRegistry.workspace_id.in_(user_workspaces))
        
        query = query.filter(or_(*access_conditions))
        
        # Apply filters
        if workspace_id:
            query = query.filter(ModelRegistry.workspace_id == UUID(workspace_id))
        
        if filters:
            if "type" in filters:
                query = query.filter(ModelRegistry.model_type == filters["type"])
            
            if "tags" in filters:
                for tag in filters["tags"]:
                    query = query.filter(ModelRegistry.tags.contains([tag]))
        
        models = query.order_by(ModelRegistry.created_at.desc()).all()
        
        # Convert to dictionaries
        result = []
        for model in models:
            result.append({
                "model_id": str(model.id),
                "name": model.name,
                "version": model.version,
                "type": model.model_type,
                "description": model.description,
                "tags": model.tags,
                "is_public": model.is_public,
                "owner_id": str(model.owner_id),
                "workspace_id": str(model.workspace_id) if model.workspace_id else None,
                "created_at": model.created_at,
                "updated_at": model.updated_at,
                "download_count": model.download_count,
                "size_mb": round(model.model_size_bytes / 1024 / 1024, 2) if model.model_size_bytes else None
            })
        
        return result
    
    def search_models(
        self,
        query: str,
        workspace_id: Optional[str] = None,
        include_public: bool = True
    ) -> List[Dict[str, Any]]:
        """Search models by name, description, and tags.
        
        Parameters
        ----------
        query : str
            Search query string
        workspace_id : str, optional
            Limit search to specific workspace
        include_public : bool, default=True
            Whether to include public models
            
        Returns
        -------
        List[Dict[str, Any]]
            List of matching models ordered by relevance
        """
        # Get base accessible models
        models = self.list_models(workspace_id=workspace_id, include_public=include_public)
        
        if not query.strip():
            return models
        
        # Simple text search implementation
        query_lower = query.lower()
        scored_models = []
        
        for model in models:
            score = 0
            
            # Name match (highest priority)
            if query_lower in model["name"].lower():
                score += 10
            
            # Description match
            if model["description"] and query_lower in model["description"].lower():
                score += 5
            
            # Tag match
            if model["tags"]:
                for tag in model["tags"]:
                    if query_lower in tag.lower():
                        score += 3
            
            # Type match
            if model["type"] and query_lower in model["type"].lower():
                score += 2
            
            if score > 0:
                model["relevance_score"] = score
                scored_models.append(model)
        
        # Sort by relevance score
        scored_models.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        # Remove relevance score from results
        for model in scored_models:
            del model["relevance_score"]
        
        return scored_models
    
    def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific model.
        
        Parameters
        ----------
        model_id : str
            Model identifier
            
        Returns
        -------
        Dict[str, Any] or None
            Detailed model information or None if not found/accessible
        """
        model = self.db_session.query(ModelRegistry).filter(
            ModelRegistry.id == UUID(model_id)
        ).first()
        
        if not model:
            return None
        
        # Check access permission
        if not self._can_access_model(model):
            return None
        
        # Get additional information
        total_downloads = self.db_session.query(ModelDownload).filter(
            ModelDownload.model_id == UUID(model_id)
        ).count()
        
        # Get workspace info if applicable
        workspace_info = None
        if model.workspace_id:
            workspace = self.db_session.query(Workspace).filter(
                Workspace.id == model.workspace_id
            ).first()
            if workspace:
                workspace_info = {
                    "id": str(workspace.id),
                    "name": workspace.name,
                    "description": workspace.description
                }
        
        return {
            "model_id": str(model.id),
            "name": model.name,
            "version": model.version,
            "type": model.model_type,
            "description": model.description,
            "tags": model.tags or [],
            "is_public": model.is_public,
            "owner_id": str(model.owner_id),
            "workspace": workspace_info,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
            "last_accessed": model.last_accessed,
            "model_size_bytes": model.model_size_bytes,
            "size_mb": round(model.model_size_bytes / 1024 / 1024, 2) if model.model_size_bytes else None,
            "download_count": model.download_count,
            "total_downloads": total_downloads,
            "manifest_hash": model.manifest_hash,
            "storage_path": model.model_path
        }
    
    def _can_access_model(self, model: ModelRegistry) -> bool:
        """Check if current user can access a model.
        
        Parameters
        ----------
        model : ModelRegistry
            Model record to check
            
        Returns
        -------
        bool
            True if user has access
        """
        # Owner access
        if model.owner_id == self.current_user.id:
            return True
        
        # Public access
        if model.is_public:
            return True
        
        # Workspace access
        if model.workspace_id:
            workspace = self.db_session.query(Workspace).filter(
                Workspace.id == model.workspace_id,
                Workspace.owner_id == self.current_user.id
            ).first()
            if workspace:
                return True
        
        # Explicit access grant
        access_grant = self.db_session.query(ModelAccess).filter(
            ModelAccess.model_id == model.id,
            ModelAccess.user_id == self.current_user.id
        ).first()
        
        if access_grant:
            # Check if access has expired
            if access_grant.expires_at is None or access_grant.expires_at > datetime.utcnow():
                return True
        
        return False
    
    def remove_model(self, model_id: str, cleanup_files: bool = True) -> Dict[str, Any]:
        """Remove a model from the registry.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        cleanup_files : bool, default=True
            Whether to remove model files from storage
            
        Returns
        -------
        Dict[str, Any]
            Removal result status
        """
        try:
            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == UUID(model_id)
            ).first()
            
            if not model:
                return {
                    "status": "error",
                    "message": "Model not found"
                }
            
            # Check permission (only owner can delete)
            if model.owner_id != self.current_user.id:
                return {
                    "status": "error",
                    "message": "Permission denied: only model owner can delete"
                }
            
            model_name = model.name
            model_path = Path(model.model_path)
            
            # Delete database record (cascading deletes will handle related records)
            self.db_session.delete(model)
            self.db_session.commit()
            
            # Clean up files if requested
            if cleanup_files and model_path.exists():
                try:
                    shutil.rmtree(model_path)
                    logger.info(f"Removed model files: {model_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove model files {model_path}: {e}")
            
            logger.info(f"Removed model {model_name} (ID: {model_id})")
            
            return {
                "status": "success",
                "message": f"Model {model_name} removed successfully"
            }
            
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to remove model {model_id}: {e}")
            return {
                "status": "error",
                "message": f"Failed to remove model: {str(e)}"
            }
    
    def track_download(
        self,
        model_id: str,
        download_method: str = "api",
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """Track a model download for analytics.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        download_method : str, default="api"
            Download method (api, cli, web)
        user_agent : str, optional
            User agent string
            
        Returns
        -------
        Dict[str, Any]
            Download tracking result
        """
        try:
            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == UUID(model_id)
            ).first()
            
            if not model:
                return {
                    "status": "error",
                    "message": "Model not found or not accessible"
                }
            
            if not self._can_access_model(model):
                return {
                    "status": "error",
                    "message": "Model not accessible"
                }
            
            # Create download record
            download_record = ModelDownload(
                id=uuid4(),
                model_id=UUID(model_id),
                user_id=self.current_user.id,
                downloaded_at=datetime.utcnow(),
                download_size_bytes=model.model_size_bytes or 0,
                download_method=download_method,
                user_agent=user_agent or ""
            )
            
            self.db_session.add(download_record)
            
            # Update model download count and last accessed
            model.download_count += 1
            model.last_accessed = datetime.utcnow()
            
            self.db_session.commit()
            
            return {
                "status": "success",
                "message": "Download tracked successfully",
                "download_count": model.download_count
            }
            
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to track download for model {model_id}: {e}")
            return {
                "status": "error",
                "message": f"Failed to track download: {str(e)}"
            }
    
    def get_model_path(self, model_id: str) -> Optional[Path]:
        """Get local filesystem path for a model.
        
        Parameters
        ----------
        model_id : str
            Model identifier
            
        Returns
        -------
        Path or None
            Local path to model files or None if not accessible
        """
        model = self.db_session.query(ModelRegistry).filter(
            ModelRegistry.id == UUID(model_id)
        ).first()
        
        if not model or not self._can_access_model(model):
            return None
        
        model_path = Path(model.model_path)
        
        if model_path.exists():
            return model_path
        
        return None
    
    # Cached Methods for Performance Optimization
    
    def list_models_cached(
        self,
        workspace_id: Optional[str] = None,
        include_public: bool = True,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Cached version of list_models for improved performance.
        
        Parameters
        ----------
        workspace_id : str, optional
            Filter to specific workspace
        include_public : bool, default=True
            Whether to include public models
        filters : Dict[str, Any], optional
            Additional filters (type, tags, etc.)
            
        Returns
        -------
        List[Dict[str, Any]]
            List of accessible models
        """
        # Generate cache key
        cache_key = self.cache.generate_list_models_key(
            user_id=str(self.current_user.id),
            workspace_id=workspace_id,
            include_public=include_public,
            filters=filters
        )
        
        # Check cache first
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit for list_models: {cache_key}")
            return cached_result
        
        # Cache miss - call original method
        result = self.list_models(
            workspace_id=workspace_id,
            include_public=include_public,
            filters=filters
        )
        
        # Cache the result
        ttl = self.cache.get_default_ttl('list_models')
        self.cache.set(cache_key, result, ttl=ttl)
        logger.debug(f"Cached list_models result: {cache_key}")
        
        return result
    
    def search_models_cached(
        self,
        query: str,
        workspace_id: Optional[str] = None,
        include_public: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Cached version of search_models for improved performance.
        
        Parameters
        ----------
        query : str
            Search query string
        workspace_id : str, optional
            Limit search to specific workspace
        include_public : bool, default=True
            Whether to include public models
            
        Returns
        -------
        List[Dict[str, Any]]
            List of matching models ordered by relevance
        """
        # Generate cache key
        cache_key = self.cache.generate_search_models_key(
            query=query,
            user_id=str(self.current_user.id),
            workspace_id=workspace_id,
            include_public=include_public
        )
        
        # Check cache first
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit for search_models: {cache_key}")
            return cached_result
        
        # Cache miss - call original method
        result = self.search_models(
            query=query,
            workspace_id=workspace_id,
            include_public=include_public
        )
        
        # Cache the result
        ttl = self.cache.get_default_ttl('search_models')
        self.cache.set(cache_key, result, ttl=ttl)
        logger.debug(f"Cached search_models result: {cache_key}")
        
        return result
    
    def get_model_info_cached(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Cached version of get_model_info for improved performance.
        
        Parameters
        ----------
        model_id : str
            Model identifier
            
        Returns
        -------
        Dict[str, Any] or None
            Detailed model information or None if not found/accessible
        """
        # Generate cache key
        cache_key = self.cache.generate_model_info_key(
            model_id=model_id,
            user_id=str(self.current_user.id)
        )
        
        # Check cache first
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit for get_model_info: {cache_key}")
            return cached_result
        
        # Cache miss - call original method
        result = self.get_model_info(model_id)
        
        # Only cache non-null results
        if result is not None:
            ttl = self.cache.get_default_ttl('model_info')
            self.cache.set(cache_key, result, ttl=ttl)
            logger.debug(f"Cached get_model_info result: {cache_key}")
        
        return result
    
    def register_model_with_cache_invalidation(
        self,
        model_path: Path,
        name: Optional[str] = None,
        version: str = "1.0.0",
        workspace_id: Optional[str] = None,
        is_public: bool = False,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        model_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register model and invalidate related cache entries.
        
        Parameters
        ----------
        Same as register_model method
            
        Returns
        -------
        Dict[str, Any]
            Registration result with model_id and status
        """
        # Call original registration method
        result = self.register_model(
            model_path=model_path,
            name=name,
            version=version,
            workspace_id=workspace_id,
            is_public=is_public,
            description=description,
            tags=tags,
            model_type=model_type
        )
        
        # Invalidate user cache if registration was successful
        if result.get('status') == 'success':
            self.cache.invalidate_user_cache(str(self.current_user.id))
            logger.debug(f"Invalidated user cache after model registration")
        
        return result