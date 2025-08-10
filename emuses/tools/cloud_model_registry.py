"""Cloud-based model registry implementation.

This module provides a cloud model registry that extends database-backed
model storage with cloud storage capabilities. It integrates with multiple
cloud providers for scalable, reliable model storage and distribution.
"""

import asyncio
import hashlib
import logging
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from emuses.tools.cloud_storage import CloudStorageBackend, S3StorageBackend, AzureBlobStorageBackend, GCSStorageBackend
from emuses.multi_user_service.models import User, ModelRegistry, ModelAccess, ModelDownload, Workspace
from emuses.tools.model_permission_manager import ModelPermissionManager
from emuses.tools.local_model_registry import LocalModelRegistry

logger = logging.getLogger(__name__)


class CloudModelRegistryError(Exception):
    """Base exception for cloud model registry operations."""
    pass


class CloudStorageError(CloudModelRegistryError):
    """Exception for cloud storage operations."""
    pass


class CloudModelNotFoundError(CloudModelRegistryError):
    """Exception when a model is not found in cloud storage."""
    pass


class CloudModelAccessError(CloudModelRegistryError):
    """Exception for cloud model access permissions."""
    pass


class StorageTier:
    """Enumeration of storage tiers for model organization."""
    
    HOT = "hot"        # Frequently accessed models
    WARM = "warm"      # Occasionally accessed models  
    COLD = "cold"      # Rarely accessed models
    ARCHIVE = "archive"  # Long-term storage


class CloudModelRegistry:
    """Cloud-based model registry with database coordination.
    
    Provides scalable model storage using cloud backends with database
    metadata management. Supports multiple cloud providers, caching,
    and tier-based storage optimization.
    
    Parameters
    ----------
    db_session : Session
        SQLAlchemy database session
    user : User
        Current user for access control
    storage_backend : CloudStorageBackend
        Cloud storage backend implementation
    local_cache_path : Path, optional
        Local cache directory path. Defaults to ~/.emuses/model_cache
    enable_caching : bool, default=True
        Enable local model caching for performance
    default_tier : str, default="hot"
        Default storage tier for new models
        
    Attributes
    ----------
    db : Session
        Database session
    current_user : User
        Current user context
    storage : CloudStorageBackend
        Cloud storage backend
    permission_manager : ModelPermissionManager
        Model permission management
    local_cache_path : Path
        Local cache directory
    enable_caching : bool
        Whether caching is enabled
    default_tier : str
        Default storage tier
    """
    
    def __init__(
        self,
        db_session: Session,
        user: User,
        storage_backend: CloudStorageBackend,
        local_cache_path: Optional[Path] = None,
        enable_caching: bool = True,
        default_tier: str = StorageTier.HOT
    ):
        """Initialize cloud model registry.
        
        Parameters
        ----------
        db_session : Session
            Database session for metadata operations
        user : User
            Current user for permission context
        storage_backend : CloudStorageBackend
            Configured cloud storage backend
        local_cache_path : Path, optional
            Custom cache path. If None, uses default location
        enable_caching : bool, default=True
            Enable local caching for performance
        default_tier : str, default="hot"
            Default storage tier for new models
        """
        self.db = db_session
        self.current_user = user
        self.storage = storage_backend
        self.permission_manager = ModelPermissionManager(db_session, user)
        self.default_tier = default_tier
        self.enable_caching = enable_caching
        
        # Initialize cache directory
        if local_cache_path is None:
            local_cache_path = Path.home() / ".emuses" / "model_cache"
        self.local_cache_path = Path(local_cache_path)
        
        if self.enable_caching:
            self._initialize_cache()
            
        logger.info(f"Initialized CloudModelRegistry with {type(storage_backend).__name__}")
    
    def _initialize_cache(self) -> None:
        """Initialize local cache directory structure.
        
        Creates cache directory and subdirectories for different
        storage tiers if caching is enabled.
        """
        try:
            self.local_cache_path.mkdir(parents=True, exist_ok=True)
            
            # Create tier-based cache directories
            for tier in [StorageTier.HOT, StorageTier.WARM, StorageTier.COLD]:
                tier_path = self.local_cache_path / tier
                tier_path.mkdir(exist_ok=True)
                
            # Create metadata cache directory
            metadata_path = self.local_cache_path / "metadata"
            metadata_path.mkdir(exist_ok=True)
            
            logger.debug(f"Initialized cache directories at {self.local_cache_path}")
            
        except OSError as e:
            logger.warning(f"Failed to initialize cache directory: {e}")
            self.enable_caching = False
    
    @classmethod
    def from_config(
        cls,
        db_session: Session,
        user: User,
        config: Dict[str, Any]
    ) -> "CloudModelRegistry":
        """Create registry from configuration dictionary.
        
        Convenience method to create registry from configuration
        with automatic storage backend initialization.
        
        Parameters
        ----------
        db_session : Session
            Database session
        user : User  
            Current user
        config : Dict[str, Any]
            Configuration dictionary with storage backend settings
            
        Returns
        -------
        CloudModelRegistry
            Configured registry instance
            
        Raises
        ------
        CloudModelRegistryError
            If configuration is invalid or backend initialization fails
        """
        try:
            provider = config.get("provider", "s3").lower()
            
            if provider == "s3":
                backend = S3StorageBackend(
                    bucket_name=config["bucket_name"],
                    access_key=config["access_key"],
                    secret_key=config["secret_key"],
                    region=config.get("region", "us-east-1")
                )
            elif provider == "azure":
                backend = AzureBlobStorageBackend(
                    account_name=config["account_name"],
                    account_key=config["account_key"],
                    container_name=config["container_name"]
                )
            elif provider == "gcs":
                backend = GCSStorageBackend(
                    bucket_name=config["bucket_name"],
                    credentials_path=config.get("credentials_path"),
                    project_id=config["project_id"]
                )
            else:
                raise CloudModelRegistryError(f"Unsupported storage provider: {provider}")
                
            return cls(
                db_session=db_session,
                user=user,
                storage_backend=backend,
                local_cache_path=config.get("cache_path"),
                enable_caching=config.get("enable_caching", True),
                default_tier=config.get("default_tier", StorageTier.HOT)
            )
            
        except KeyError as e:
            raise CloudModelRegistryError(f"Missing required configuration key: {e}")
        except Exception as e:
            raise CloudModelRegistryError(f"Failed to initialize from config: {e}")
    
    def _get_cache_path(self, model_id: str, tier: str = None) -> Path:
        """Get local cache path for a model.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        tier : str, optional
            Storage tier. If None, uses model's current tier
            
        Returns
        -------
        Path
            Local cache path for the model
        """
        if tier is None:
            tier = StorageTier.HOT  # Default for cache path computation
            
        return self.local_cache_path / tier / model_id
    
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

    async def upload_model(
        self,
        model_path: Path,
        name: str,
        version: str = "1.0.0",
        workspace_id: Optional[UUID] = None,
        is_public: bool = False,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        storage_tier: str = None
    ) -> str:
        """Upload model to cloud storage with database registration.
        
        Uploads a local model to cloud storage and registers metadata
        in the database. Handles compression, integrity verification,
        and permission setup.
        
        Parameters
        ----------
        model_path : Path
            Path to local model directory
        name : str
            Model name for registration
        version : str, default="1.0.0"
            Model version string
        workspace_id : UUID, optional
            Workspace ID for workspace-scoped models
        is_public : bool, default=False
            Whether model should be publicly accessible
        description : str, optional
            Model description
        tags : List[str], optional
            Model tags for categorization
        storage_tier : str, optional
            Storage tier (defaults to registry default tier)
            
        Returns
        -------
        str
            Model ID of the uploaded and registered model
            
        Raises
        ------
        CloudStorageError
            If cloud upload fails
        CloudModelRegistryError
            If database registration fails
        FileNotFoundError
            If model path doesn't exist
        """
        if not model_path.exists():
            raise FileNotFoundError(f"Model path does not exist: {model_path}")
            
        if not model_path.is_dir():
            raise CloudModelRegistryError(f"Model path must be a directory: {model_path}")
            
        if storage_tier is None:
            storage_tier = self.default_tier
            
        if tags is None:
            tags = []
            
        try:
            # Generate model ID
            model_id = str(uuid4())
            
            # Compute model metadata
            model_hash = self._compute_model_hash(model_path)
            model_size = self._get_model_size(model_path)
            
            logger.info(f"Uploading model {name} v{version} (ID: {model_id}) to cloud storage")
            
            # Upload to cloud storage
            storage_url = await self.storage.upload_model(model_path, model_id)
            
            # Create database record
            model_record = ModelRegistry(
                id=UUID(model_id),
                name=name,
                version=version,
                owner_id=self.current_user.id,
                workspace_id=workspace_id,
                is_public=is_public,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                model_path=str(storage_url),  # Store cloud URL instead of local path
                manifest_hash=model_hash,
                model_size_bytes=model_size,
                description=description or "",
                tags=tags,
                model_type="unknown",  # TODO: Detect from manifest
                download_count=0,
                last_accessed=datetime.utcnow()
            )
            
            # Add custom fields for cloud storage
            if hasattr(model_record, 'storage_tier'):
                model_record.storage_tier = storage_tier
            if hasattr(model_record, 'storage_url'):
                model_record.storage_url = storage_url
            if hasattr(model_record, 'is_cached'):
                model_record.is_cached = False
                
            self.db.add(model_record)
            self.db.commit()
            
            # Set up permissions
            if workspace_id:
                # Grant workspace access
                await self.permission_manager.grant_access(
                    model_id, workspace_id, "read", granted_by=self.current_user.id
                )
            
            logger.info(f"Successfully uploaded and registered model {model_id}")
            return model_id
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to upload model: {e}")
            
            # Clean up cloud storage if database registration failed
            try:
                if 'storage_url' in locals():
                    await self.storage.delete_model(storage_url)
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup cloud storage after error: {cleanup_error}")
                
            if isinstance(e, (CloudStorageError, CloudModelRegistryError)):
                raise
            else:
                raise CloudModelRegistryError(f"Upload failed: {e}")

    async def download_model(
        self,
        model_id: str,
        local_path: Optional[Path] = None,
        use_cache: bool = None,
        progress_callback: Optional[callable] = None
    ) -> Path:
        """Download model from cloud storage with caching optimization.
        
        Downloads model from cloud storage to local filesystem with
        intelligent caching and permission verification.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        local_path : Path, optional
            Custom download path. If None, uses cache directory
        use_cache : bool, optional
            Whether to use local cache. If None, uses registry default
        progress_callback : callable, optional
            Progress callback function for download tracking
            
        Returns
        -------
        Path
            Local path to downloaded model
            
        Raises
        ------
        CloudModelNotFoundError
            If model is not found
        CloudModelAccessError
            If user lacks download permission
        CloudStorageError
            If cloud download fails
        """
        if use_cache is None:
            use_cache = self.enable_caching
            
        # Get model record from database
        model_record = self.db.query(ModelRegistry).filter(
            ModelRegistry.id == UUID(model_id)
        ).first()
        
        if not model_record:
            raise CloudModelNotFoundError(f"Model not found: {model_id}")
            
        # Check download permission
        if not await self.permission_manager.can_access(model_id, self.current_user.id, "read"):
            raise CloudModelAccessError(f"Access denied for model: {model_id}")
            
        # Determine download path
        if local_path is None:
            if use_cache:
                tier = getattr(model_record, 'storage_tier', StorageTier.HOT)
                local_path = self._get_cache_path(model_id, tier)
            else:
                # Create temporary directory
                temp_dir = Path(tempfile.mkdtemp(prefix=f"emuses_model_{model_id}_"))
                local_path = temp_dir / model_id
                
        # Check if already cached and valid
        if use_cache and local_path.exists():
            try:
                # Verify cache integrity with stored hash
                cached_hash = self._compute_model_hash(local_path)
                if cached_hash == model_record.manifest_hash:
                    logger.info(f"Using cached model {model_id} from {local_path}")
                    
                    # Update access tracking
                    await self._record_model_access(model_id)
                    return local_path
                else:
                    logger.warning(f"Cache hash mismatch for model {model_id}, re-downloading")
                    shutil.rmtree(local_path)
            except Exception as e:
                logger.warning(f"Cache validation failed for model {model_id}: {e}")
                if local_path.exists():
                    shutil.rmtree(local_path)
                    
        try:
            # Create parent directories
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Downloading model {model_id} from cloud storage")
            
            # Download from cloud storage
            storage_url = model_record.model_path  # This contains the cloud URL
            await self.storage.download_model(storage_url, local_path)
            
            # Verify download integrity
            downloaded_hash = self._compute_model_hash(local_path)
            if downloaded_hash != model_record.manifest_hash:
                raise CloudStorageError(
                    f"Download integrity check failed for model {model_id}: "
                    f"expected {model_record.manifest_hash}, got {downloaded_hash}"
                )
                
            # Update cache status in database
            if use_cache and hasattr(model_record, 'is_cached'):
                model_record.is_cached = True
                self.db.commit()
                
            # Record download and access
            await self._record_model_download(model_id)
            await self._record_model_access(model_id)
            
            logger.info(f"Successfully downloaded model {model_id} to {local_path}")
            return local_path
            
        except Exception as e:
            logger.error(f"Failed to download model {model_id}: {e}")
            
            # Clean up partial download
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)
                
            if isinstance(e, (CloudStorageError, CloudModelAccessError)):
                raise
            else:
                raise CloudStorageError(f"Download failed: {e}")

    async def get_signed_url(
        self,
        model_id: str,
        expires_in: int = 3600,
        operation: str = "download"
    ) -> str:
        """Generate time-limited signed URL for model access.
        
        Creates a time-limited URL for direct model access without
        going through the registry download process.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        expires_in : int, default=3600
            URL expiration time in seconds
        operation : str, default="download"
            Operation type (download, upload, delete)
            
        Returns
        -------
        str
            Signed URL for time-limited access
            
        Raises
        ------
        CloudModelNotFoundError
            If model is not found
        CloudModelAccessError
            If user lacks required permission
        CloudStorageError
            If signed URL generation fails
        """
        # Get model record
        model_record = self.db.query(ModelRegistry).filter(
            ModelRegistry.id == UUID(model_id)
        ).first()
        
        if not model_record:
            raise CloudModelNotFoundError(f"Model not found: {model_id}")
            
        # Check permission based on operation
        required_permission = {
            "download": "read",
            "upload": "write", 
            "delete": "admin"
        }.get(operation, "read")
        
        if not await self.permission_manager.can_access(
            model_id, self.current_user.id, required_permission
        ):
            raise CloudModelAccessError(
                f"Access denied for {operation} operation on model: {model_id}"
            )
            
        try:
            # Generate signed URL from cloud storage
            storage_url = model_record.model_path
            signed_url = await self.storage.generate_signed_url(storage_url, expires_in)
            
            logger.info(f"Generated signed URL for model {model_id}, expires in {expires_in}s")
            return signed_url
            
        except Exception as e:
            logger.error(f"Failed to generate signed URL for model {model_id}: {e}")
            raise CloudStorageError(f"Signed URL generation failed: {e}")

    async def migrate_model_tier(
        self,
        model_id: str,
        target_tier: str,
        force: bool = False
    ) -> bool:
        """Migrate model between storage tiers.
        
        Moves model between different storage tiers (hot/warm/cold/archive)
        for cost optimization and performance tuning.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        target_tier : str
            Target storage tier (hot, warm, cold, archive)
        force : bool, default=False
            Force migration even if not beneficial
            
        Returns
        -------
        bool
            True if migration was successful
            
        Raises
        ------
        CloudModelNotFoundError
            If model is not found
        CloudModelAccessError
            If user lacks admin permission
        CloudStorageError
            If migration fails
        ValueError
            If target tier is invalid
        """
        if target_tier not in [StorageTier.HOT, StorageTier.WARM, StorageTier.COLD, StorageTier.ARCHIVE]:
            raise ValueError(f"Invalid storage tier: {target_tier}")
            
        # Get model record
        model_record = self.db.query(ModelRegistry).filter(
            ModelRegistry.id == UUID(model_id)
        ).first()
        
        if not model_record:
            raise CloudModelNotFoundError(f"Model not found: {model_id}")
            
        # Check admin permission for migration
        if not await self.permission_manager.can_access(model_id, self.current_user.id, "admin"):
            raise CloudModelAccessError(f"Admin access required for tier migration: {model_id}")
            
        current_tier = getattr(model_record, 'storage_tier', StorageTier.HOT)
        
        if current_tier == target_tier and not force:
            logger.info(f"Model {model_id} already in target tier {target_tier}")
            return True
            
        try:
            logger.info(f"Migrating model {model_id} from {current_tier} to {target_tier}")
            
            # For cloud storage, this typically involves changing storage class
            # Implementation depends on specific cloud provider capabilities
            
            # Download model to temporary location
            temp_path = Path(tempfile.mkdtemp(prefix=f"emuses_migrate_{model_id}_"))
            try:
                storage_url = model_record.model_path
                await self.storage.download_model(storage_url, temp_path / model_id)
                
                # Re-upload with new tier configuration
                # Note: This is a simplified approach - real implementations
                # might use cloud provider-specific tier migration APIs
                new_storage_url = await self.storage.upload_model(
                    temp_path / model_id,
                    f"{model_id}_{target_tier}"
                )
                
                # Delete old storage
                await self.storage.delete_model(storage_url)
                
                # Update database record
                model_record.model_path = new_storage_url
                if hasattr(model_record, 'storage_tier'):
                    model_record.storage_tier = target_tier
                model_record.updated_at = datetime.utcnow()
                
                # Invalidate cache
                if self.enable_caching:
                    cache_path = self._get_cache_path(model_id, current_tier)
                    if cache_path.exists():
                        shutil.rmtree(cache_path, ignore_errors=True)
                    
                    if hasattr(model_record, 'is_cached'):
                        model_record.is_cached = False
                
                self.db.commit()
                
                logger.info(f"Successfully migrated model {model_id} to tier {target_tier}")
                return True
                
            finally:
                # Clean up temporary files
                if temp_path.exists():
                    shutil.rmtree(temp_path, ignore_errors=True)
                    
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to migrate model {model_id} to tier {target_tier}: {e}")
            
            if isinstance(e, (CloudStorageError, CloudModelAccessError)):
                raise
            else:
                raise CloudStorageError(f"Migration failed: {e}")

    async def _record_model_download(self, model_id: str) -> None:
        """Record model download in analytics tracking.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        """
        try:
            # Create download record
            download_record = ModelDownload(
                id=uuid4(),
                model_id=UUID(model_id),
                user_id=self.current_user.id,
                downloaded_at=datetime.utcnow(),
                download_size_bytes=0,  # TODO: Track actual download size
                client_info=""  # TODO: Capture client information
            )
            
            self.db.add(download_record)
            
            # Update model download count
            model_record = self.db.query(ModelRegistry).filter(
                ModelRegistry.id == UUID(model_id)
            ).first()
            
            if model_record:
                model_record.download_count += 1
                
            self.db.commit()
            
        except Exception as e:
            logger.warning(f"Failed to record download for model {model_id}: {e}")
            self.db.rollback()

    async def _record_model_access(self, model_id: str) -> None:
        """Record model access timestamp.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        """
        try:
            model_record = self.db.query(ModelRegistry).filter(
                ModelRegistry.id == UUID(model_id)
            ).first()
            
            if model_record:
                model_record.last_accessed = datetime.utcnow()
                self.db.commit()
                
        except Exception as e:
            logger.warning(f"Failed to record access for model {model_id}: {e}")
            self.db.rollback()

    # Database-Cloud Storage Coordination Methods

    async def list_models(
        self,
        workspace_id: Optional[UUID] = None,
        is_public: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List models with cloud storage metadata.
        
        Lists models accessible to the current user with cloud storage
        information and download statistics.
        
        Parameters
        ----------
        workspace_id : UUID, optional
            Filter by workspace ID
        is_public : bool, optional
            Filter by public visibility
        tags : List[str], optional
            Filter by tags (models must have all specified tags)
        limit : int, default=100
            Maximum number of results
        offset : int, default=0
            Result offset for pagination
            
        Returns
        -------
        List[Dict[str, Any]]
            List of model metadata dictionaries
        """
        query = self.db.query(ModelRegistry)
        
        # Apply filters based on user permissions
        if not await self.permission_manager.is_admin(self.current_user.id):
            # Non-admin users see only their models, workspace models, and public models
            query = query.filter(
                (ModelRegistry.owner_id == self.current_user.id) |
                (ModelRegistry.is_public == True) |
                (ModelRegistry.workspace_id.in_(
                    self.db.query(Workspace.id).filter(
                        Workspace.owner_id == self.current_user.id
                    )
                ))
            )
        
        if workspace_id:
            query = query.filter(ModelRegistry.workspace_id == workspace_id)
            
        if is_public is not None:
            query = query.filter(ModelRegistry.is_public == is_public)
            
        if tags:
            for tag in tags:
                query = query.filter(ModelRegistry.tags.contains([tag]))
                
        models = query.limit(limit).offset(offset).all()
        
        result = []
        for model in models:
            model_dict = {
                "id": str(model.id),
                "name": model.name,
                "version": model.version,
                "owner_id": str(model.owner_id),
                "workspace_id": str(model.workspace_id) if model.workspace_id else None,
                "is_public": model.is_public,
                "created_at": model.created_at.isoformat(),
                "updated_at": model.updated_at.isoformat(),
                "model_size_bytes": model.model_size_bytes,
                "description": model.description,
                "tags": model.tags,
                "model_type": model.model_type,
                "download_count": model.download_count,
                "last_accessed": model.last_accessed.isoformat() if model.last_accessed else None,
            }
            
            # Add cloud-specific metadata if available
            if hasattr(model, 'storage_tier'):
                model_dict['storage_tier'] = model.storage_tier
            if hasattr(model, 'is_cached'):
                model_dict['is_cached'] = model.is_cached
            if hasattr(model, 'storage_url'):
                model_dict['storage_url'] = model.storage_url
                
            result.append(model_dict)
            
        return result

    async def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """Get detailed model information including cloud metadata.
        
        Parameters
        ----------
        model_id : str
            Model identifier
            
        Returns
        -------
        Dict[str, Any]
            Detailed model information
            
        Raises
        ------
        CloudModelNotFoundError
            If model is not found
        CloudModelAccessError
            If user lacks read permission
        """
        model_record = self.db.query(ModelRegistry).filter(
            ModelRegistry.id == UUID(model_id)
        ).first()
        
        if not model_record:
            raise CloudModelNotFoundError(f"Model not found: {model_id}")
            
        if not await self.permission_manager.can_access(model_id, self.current_user.id, "read"):
            raise CloudModelAccessError(f"Access denied for model: {model_id}")
            
        # Build comprehensive model information
        info = {
            "id": str(model_record.id),
            "name": model_record.name,
            "version": model_record.version,
            "owner_id": str(model_record.owner_id),
            "workspace_id": str(model_record.workspace_id) if model_record.workspace_id else None,
            "is_public": model_record.is_public,
            "created_at": model_record.created_at.isoformat(),
            "updated_at": model_record.updated_at.isoformat(),
            "model_size_bytes": model_record.model_size_bytes,
            "description": model_record.description,
            "tags": model_record.tags,
            "model_type": model_record.model_type,
            "download_count": model_record.download_count,
            "last_accessed": model_record.last_accessed.isoformat() if model_record.last_accessed else None,
            "manifest_hash": model_record.manifest_hash,
        }
        
        # Add cloud-specific metadata
        if hasattr(model_record, 'storage_tier'):
            info['storage_tier'] = model_record.storage_tier
        if hasattr(model_record, 'is_cached'):
            info['is_cached'] = model_record.is_cached
        if hasattr(model_record, 'storage_url'):
            info['storage_url'] = model_record.storage_url
            
        # Add storage backend information
        info['storage_backend'] = type(self.storage).__name__
        info['caching_enabled'] = self.enable_caching
        
        # Check cache status if caching is enabled
        if self.enable_caching:
            cache_path = self._get_cache_path(model_id)
            info['cached_locally'] = cache_path.exists()
            if cache_path.exists():
                info['cache_size_bytes'] = self._get_model_size(cache_path)
                
        return info

    async def delete_model(self, model_id: str, force: bool = False) -> bool:
        """Delete model from both cloud storage and database.
        
        Removes model data from cloud storage and database metadata
        with proper permission checks and cleanup.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        force : bool, default=False
            Force deletion even if model is being used
            
        Returns
        -------
        bool
            True if deletion was successful
            
        Raises
        ------
        CloudModelNotFoundError
            If model is not found
        CloudModelAccessError
            If user lacks admin permission
        CloudStorageError
            If cloud deletion fails
        """
        model_record = self.db.query(ModelRegistry).filter(
            ModelRegistry.id == UUID(model_id)
        ).first()
        
        if not model_record:
            raise CloudModelNotFoundError(f"Model not found: {model_id}")
            
        if not await self.permission_manager.can_access(model_id, self.current_user.id, "admin"):
            raise CloudModelAccessError(f"Admin access required for model deletion: {model_id}")
            
        try:
            logger.info(f"Deleting model {model_id} from cloud storage and database")
            
            # Delete from cloud storage
            storage_url = model_record.model_path
            await self.storage.delete_model(storage_url)
            
            # Clean up local cache
            if self.enable_caching:
                cache_path = self._get_cache_path(model_id)
                if cache_path.exists():
                    shutil.rmtree(cache_path, ignore_errors=True)
                    
            # Delete database records (cascading deletes will handle related records)
            self.db.delete(model_record)
            self.db.commit()
            
            logger.info(f"Successfully deleted model {model_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete model {model_id}: {e}")
            
            if isinstance(e, (CloudStorageError, CloudModelAccessError)):
                raise
            else:
                raise CloudStorageError(f"Deletion failed: {e}")

    async def validate_storage_consistency(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Validate consistency between database and cloud storage.
        
        Checks for inconsistencies between database metadata and actual
        cloud storage state. Can validate a specific model or all models.
        
        Parameters
        ----------
        model_id : str, optional
            Specific model ID to validate. If None, validates all models
            
        Returns
        -------
        Dict[str, Any]
            Validation report with found inconsistencies
        """
        report = {
            "validation_timestamp": datetime.utcnow().isoformat(),
            "validated_by": str(self.current_user.id),
            "total_models": 0,
            "consistent_models": 0,
            "inconsistent_models": 0,
            "issues": [],
            "summary": {}
        }
        
        try:
            # Get models to validate
            if model_id:
                models = [self.db.query(ModelRegistry).filter(
                    ModelRegistry.id == UUID(model_id)
                ).first()]
                if not models[0]:
                    raise CloudModelNotFoundError(f"Model not found: {model_id}")
            else:
                # Validate all accessible models
                models = self.db.query(ModelRegistry).filter(
                    (ModelRegistry.owner_id == self.current_user.id) |
                    (ModelRegistry.is_public == True)
                ).all()
                
            report["total_models"] = len(models)
            
            for model in models:
                model_issues = []
                
                try:
                    # Check if cloud storage exists
                    storage_url = model.model_path
                    # Note: This is a simplified check - real implementation would
                    # use cloud provider APIs to verify existence
                    
                    # Check cache consistency if cached
                    if self.enable_caching and hasattr(model, 'is_cached') and model.is_cached:
                        cache_path = self._get_cache_path(str(model.id))
                        if cache_path.exists():
                            cached_hash = self._compute_model_hash(cache_path)
                            if cached_hash != model.manifest_hash:
                                model_issues.append({
                                    "type": "cache_hash_mismatch",
                                    "description": f"Cache hash mismatch for model {model.id}",
                                    "expected": model.manifest_hash,
                                    "actual": cached_hash
                                })
                        else:
                            model_issues.append({
                                "type": "cache_missing",
                                "description": f"Model {model.id} marked as cached but cache not found"
                            })
                            
                    # Check for orphaned cache files
                    if self.enable_caching:
                        cache_path = self._get_cache_path(str(model.id))
                        if cache_path.exists() and (not hasattr(model, 'is_cached') or not model.is_cached):
                            model_issues.append({
                                "type": "orphaned_cache",
                                "description": f"Cache exists for model {model.id} but not marked as cached"
                            })
                            
                except Exception as e:
                    model_issues.append({
                        "type": "validation_error",
                        "description": f"Failed to validate model {model.id}: {e}"
                    })
                    
                if model_issues:
                    report["inconsistent_models"] += 1
                    report["issues"].extend([
                        {
                            "model_id": str(model.id),
                            "model_name": model.name,
                            **issue
                        }
                        for issue in model_issues
                    ])
                else:
                    report["consistent_models"] += 1
                    
            # Generate summary
            report["summary"] = {
                "consistency_rate": report["consistent_models"] / report["total_models"] if report["total_models"] > 0 else 1.0,
                "issue_types": list(set(issue["type"] for issue in report["issues"])),
                "total_issues": len(report["issues"])
            }
            
            logger.info(f"Storage consistency validation complete: {report['consistent_models']}/{report['total_models']} models consistent")
            return report
            
        except Exception as e:
            logger.error(f"Storage consistency validation failed: {e}")
            report["issues"].append({
                "type": "validation_failed",
                "description": f"Validation process failed: {e}"
            })
            return report

    async def repair_storage_consistency(self, validation_report: Dict[str, Any]) -> Dict[str, Any]:
        """Repair storage consistency issues found during validation.
        
        Attempts to fix inconsistencies identified in a validation report.
        
        Parameters
        ----------
        validation_report : Dict[str, Any]
            Validation report from validate_storage_consistency()
            
        Returns
        -------
        Dict[str, Any]
            Repair report with results of fix attempts
        """
        repair_report = {
            "repair_timestamp": datetime.utcnow().isoformat(),
            "repaired_by": str(self.current_user.id),
            "issues_addressed": 0,
            "successful_repairs": 0,
            "failed_repairs": 0,
            "repair_actions": []
        }
        
        try:
            for issue in validation_report.get("issues", []):
                issue_type = issue.get("type")
                model_id = issue.get("model_id")
                
                repair_action = {
                    "model_id": model_id,
                    "issue_type": issue_type,
                    "action_taken": None,
                    "success": False,
                    "error": None
                }
                
                try:
                    if issue_type == "cache_hash_mismatch":
                        # Remove invalid cache
                        cache_path = self._get_cache_path(model_id)
                        if cache_path.exists():
                            shutil.rmtree(cache_path)
                        
                        # Update database to mark as not cached
                        model_record = self.db.query(ModelRegistry).filter(
                            ModelRegistry.id == UUID(model_id)
                        ).first()
                        if model_record and hasattr(model_record, 'is_cached'):
                            model_record.is_cached = False
                            self.db.commit()
                            
                        repair_action["action_taken"] = "Removed invalid cache"
                        repair_action["success"] = True
                        repair_report["successful_repairs"] += 1
                        
                    elif issue_type == "cache_missing":
                        # Update database to mark as not cached
                        model_record = self.db.query(ModelRegistry).filter(
                            ModelRegistry.id == UUID(model_id)
                        ).first()
                        if model_record and hasattr(model_record, 'is_cached'):
                            model_record.is_cached = False
                            self.db.commit()
                            
                        repair_action["action_taken"] = "Updated cache status in database"
                        repair_action["success"] = True
                        repair_report["successful_repairs"] += 1
                        
                    elif issue_type == "orphaned_cache":
                        # Either remove cache or mark as cached in database
                        cache_path = self._get_cache_path(model_id)
                        if cache_path.exists():
                            # Verify cache integrity before marking as cached
                            model_record = self.db.query(ModelRegistry).filter(
                                ModelRegistry.id == UUID(model_id)
                            ).first()
                            
                            if model_record:
                                cached_hash = self._compute_model_hash(cache_path)
                                if cached_hash == model_record.manifest_hash:
                                    # Cache is valid, mark as cached
                                    if hasattr(model_record, 'is_cached'):
                                        model_record.is_cached = True
                                        self.db.commit()
                                    repair_action["action_taken"] = "Marked valid cache as cached in database"
                                else:
                                    # Cache is invalid, remove it
                                    shutil.rmtree(cache_path)
                                    repair_action["action_taken"] = "Removed invalid orphaned cache"
                                    
                                repair_action["success"] = True
                                repair_report["successful_repairs"] += 1
                            else:
                                # Model not found, remove orphaned cache
                                shutil.rmtree(cache_path)
                                repair_action["action_taken"] = "Removed cache for non-existent model"
                                repair_action["success"] = True
                                repair_report["successful_repairs"] += 1
                                
                    else:
                        repair_action["action_taken"] = f"No automatic repair available for {issue_type}"
                        repair_action["success"] = False
                        repair_report["failed_repairs"] += 1
                        
                except Exception as e:
                    repair_action["error"] = str(e)
                    repair_action["success"] = False
                    repair_report["failed_repairs"] += 1
                    logger.error(f"Failed to repair {issue_type} for model {model_id}: {e}")
                    
                repair_report["repair_actions"].append(repair_action)
                repair_report["issues_addressed"] += 1
                
            logger.info(f"Storage consistency repair complete: {repair_report['successful_repairs']}/{repair_report['issues_addressed']} issues repaired")
            return repair_report
            
        except Exception as e:
            logger.error(f"Storage consistency repair failed: {e}")
            repair_report["repair_actions"].append({
                "error": f"Repair process failed: {e}",
                "success": False
            })
            return repair_report

    async def get_storage_statistics(self) -> Dict[str, Any]:
        """Get comprehensive storage statistics for cloud registry.
        
        Returns detailed statistics about storage usage, caching,
        and model distribution across tiers.
        
        Returns
        -------
        Dict[str, Any]
            Storage statistics and metrics
        """
        stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "storage_backend": type(self.storage).__name__,
            "caching_enabled": self.enable_caching,
            "total_models": 0,
            "total_size_bytes": 0,
            "cache_statistics": {},
            "tier_distribution": {},
            "user_statistics": {},
            "recent_activity": {}
        }
        
        try:
            # Get all accessible models
            models = self.db.query(ModelRegistry).filter(
                (ModelRegistry.owner_id == self.current_user.id) |
                (ModelRegistry.is_public == True)
            ).all()
            
            stats["total_models"] = len(models)
            
            # Calculate storage statistics
            total_size = sum(model.model_size_bytes for model in models)
            stats["total_size_bytes"] = total_size
            stats["total_size_gb"] = round(total_size / (1024**3), 2)
            
            # Cache statistics
            if self.enable_caching:
                cached_models = 0
                cached_size = 0
                
                for model in models:
                    cache_path = self._get_cache_path(str(model.id))
                    if cache_path.exists():
                        cached_models += 1
                        cached_size += self._get_model_size(cache_path)
                        
                stats["cache_statistics"] = {
                    "cached_models": cached_models,
                    "cache_hit_rate": round(cached_models / len(models), 2) if models else 0,
                    "cached_size_bytes": cached_size,
                    "cached_size_gb": round(cached_size / (1024**3), 2),
                    "cache_efficiency": round(cached_size / total_size, 2) if total_size > 0 else 0
                }
                
            # Tier distribution (if supported)
            tier_counts = {}
            for model in models:
                tier = getattr(model, 'storage_tier', 'unknown')
                tier_counts[tier] = tier_counts.get(tier, 0) + 1
                
            stats["tier_distribution"] = tier_counts
            
            # User statistics
            user_models = [m for m in models if m.owner_id == self.current_user.id]
            public_models = [m for m in models if m.is_public]
            
            stats["user_statistics"] = {
                "owned_models": len(user_models),
                "public_models_accessible": len(public_models),
                "owned_size_bytes": sum(m.model_size_bytes for m in user_models),
                "average_model_size_bytes": round(sum(m.model_size_bytes for m in user_models) / len(user_models)) if user_models else 0
            }
            
            # Recent activity
            recent_downloads = self.db.query(ModelDownload).filter(
                ModelDownload.user_id == self.current_user.id
            ).order_by(ModelDownload.downloaded_at.desc()).limit(10).all()
            
            stats["recent_activity"] = {
                "recent_downloads": len(recent_downloads),
                "total_downloads": len(self.db.query(ModelDownload).filter(
                    ModelDownload.user_id == self.current_user.id
                ).all())
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to generate storage statistics: {e}")
            stats["error"] = str(e)
            return stats