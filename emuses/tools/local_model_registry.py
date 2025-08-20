"""Local file-based model registry implementation.

This module provides a local model registry that stores models and metadata
in a directory structure on the local filesystem. It serves as the foundation
for more advanced registry implementations.
"""
import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime
from uuid import UUID

from emuses.tools.model_io import ModelIOManager
from emuses.tools.base_model_registry import BaseModelRegistry
from emuses.tools.storage_manager import StorageManager
from emuses.tools.model_registry_metrics import track_list_models, track_install_model, track_search_models, track_get_model_info, track_remove_model, track_model_storage

logger = logging.getLogger(__name__)


class LocalModelRegistry(BaseModelRegistry):
    """Local file-based model registry.
    
    Manages a collection of models stored in a local directory structure
    with JSON-based metadata indexing.
    
    Parameters
    ----------
    registry_path : Path, optional
        Path to the registry directory. Defaults to ~/.emuses/model_registry
        
    Attributes
    ----------
    registry_path : Path
        Path to the registry directory
    models_path : Path
        Path to the models subdirectory
    index_path : Path
        Path to the registry.json index file
    """
    
    REGISTRY_VERSION = "1.0.0"
    
    def __init__(self, registry_path: Optional[Path] = None):
        """Initialize local model registry.
        
        Parameters
        ----------
        registry_path : Path, optional
            Custom registry path. If None, uses default location.
        """
        if registry_path is None:
            registry_path = Path.home() / ".emuses" / "model_registry"
            
        self.registry_path = Path(registry_path)
        self.models_path = self.registry_path / "models"
        self.index_path = self.registry_path / "registry.json"
        
        # Initialize storage manager
        self.storage_manager = StorageManager(self.registry_path)
        
        self._initialize_registry()
        
    def _initialize_registry(self) -> None:
        """Initialize registry directory structure and index file.
        
        Creates the registry directory, models subdirectory, and
        initializes the registry.json index file if they don't exist.
        """
        # Create directory structure
        self.registry_path.mkdir(parents=True, exist_ok=True)
        self.models_path.mkdir(exist_ok=True)
        
        # Initialize registry index if it doesn't exist
        if not self.index_path.exists():
            initial_index = {
                "version": self.REGISTRY_VERSION,
                "created_at": datetime.utcnow().isoformat(),
                "last_updated": datetime.utcnow().isoformat(),
                "models": {}
            }
            self._save_index(initial_index)
            logger.info(f"Initialized new model registry at {self.registry_path}")
        else:
            logger.debug(f"Using existing model registry at {self.registry_path}")
    
    def _load_index(self) -> Dict[str, Any]:
        """Load the registry index from JSON file.
        
        Returns
        -------
        Dict[str, Any]
            Registry index data structure
            
        Raises
        ------
        FileNotFoundError
            If registry.json doesn't exist
        json.JSONDecodeError
            If registry.json contains invalid JSON
        """
        with open(self.index_path, 'r') as f:
            return json.load(f)
    
    def _save_index(self, index_data: Dict[str, Any]) -> None:
        """Save the registry index to JSON file.
        
        Parameters
        ----------
        index_data : Dict[str, Any]
            Registry index data to save
            
        Raises
        ------
        OSError
            If unable to write to registry.json
        """
        index_data["last_updated"] = datetime.utcnow().isoformat()
        with open(self.index_path, 'w') as f:
            json.dump(index_data, f, indent=2, sort_keys=True)
    
    def _model_matches_filters(self, model: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if a model matches the given filters.
        
        Parameters
        ----------
        model : Dict[str, Any]
            Model metadata dictionary
        filters : Dict[str, Any]
            Filter criteria
            
        Returns
        -------
        bool
            True if model matches all filters
        """
        # Type filter
        if "type" in filters and model.get("type") != filters["type"]:
            return False
        
        # Tags filter - all specified tags must be present
        if "tags" in filters:
            model_tags = model.get("tags", [])
            required_tags = filters["tags"]
            if not all(tag in model_tags for tag in required_tags):
                return False
        
        # Name pattern filter
        if "name" in filters:
            model_name = model.get("name", "").lower()
            pattern = filters["name"].lower()
            if pattern not in model_name:
                return False
        
        return True
    
    def get_registry_info(self) -> Dict[str, Any]:
        """Get basic information about the registry.
        
        Returns
        -------
        Dict[str, Any]
            Registry information including version and model count
        """
        try:
            index = self._load_index()
            return {
                "version": index.get("version", "unknown"),
                "created_at": index.get("created_at"),
                "last_updated": index.get("last_updated"),
                "model_count": len(index.get("models", {})),
                "registry_path": str(self.registry_path)
            }
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading registry info: {e}")
            return {
                "version": "unknown",
                "model_count": 0,
                "registry_path": str(self.registry_path),
                "error": str(e)
            }
    
    def backup_index(self) -> bool:
        """Create a backup of the registry index.
        
        Creates a timestamped backup of the registry.json file for recovery purposes.
        
        Returns
        -------
        bool
            True if backup was created successfully, False otherwise
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = self.registry_path / f"registry.json.backup.{timestamp}"
            shutil.copy2(self.index_path, backup_path)
            logger.info(f"Index backup created at {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create index backup: {e}")
            return False
    
    def validate_index(self) -> Tuple[bool, List[str]]:
        """Validate the integrity of the registry index.
        
        Checks for structural issues, missing model files, and data consistency.
        
        Returns
        -------
        Tuple[bool, List[str]]
            (is_valid, list_of_issues) - validation result and any issues found
        """
        issues = []
        
        try:
            index = self._load_index()
        except (FileNotFoundError, json.JSONDecodeError) as e:
            return False, [f"Index file corrupt or missing: {e}"]
        
        # Check required fields
        required_fields = ["version", "models"]
        for field in required_fields:
            if field not in index:
                issues.append(f"Missing required field: {field}")
        
        # Validate model entries
        for model_id, model_data in index.get("models", {}).items():
            required_model_fields = ["model_id", "name", "installed_at"]
            for field in required_model_fields:
                if field not in model_data:
                    issues.append(f"Model {model_id} missing field: {field}")
            
            # Check if model directory exists
            model_dir = self.models_path / model_id
            if not model_dir.exists():
                issues.append(f"Model directory missing for {model_id}")
        
        return len(issues) == 0, issues
    
    def repair_index(self) -> Dict[str, Any]:
        """Repair the registry index by removing invalid entries.
        
        Attempts to fix common index issues by removing broken entries
        and synchronizing with actual model files.
        
        Returns
        -------
        Dict[str, Any]
            Repair results with counts of removed/validated entries
        """
        try:
            index = self._load_index()
        except (FileNotFoundError, json.JSONDecodeError):
            # Rebuild index from scratch
            logger.warning("Index corrupt, rebuilding from model directories")
            index = {
                "version": self.REGISTRY_VERSION,
                "created_at": datetime.utcnow().isoformat(),
                "last_updated": datetime.utcnow().isoformat(),
                "models": {}
            }
        
        removed_count = 0
        validated_count = 0
        
        # Remove models with missing directories
        models_to_remove = []
        for model_id, model_data in index.get("models", {}).items():
            model_dir = self.models_path / model_id
            if not model_dir.exists():
                models_to_remove.append(model_id)
                logger.info(f"Removing missing model {model_id} from index")
            else:
                validated_count += 1
        
        for model_id in models_to_remove:
            del index["models"][model_id]
            removed_count += 1
        
        # Save repaired index
        self._save_index(index)
        
        return {
            "removed": removed_count,
            "validated": validated_count,
            "status": "repaired"
        }
    
    def cleanup_orphaned_models(self) -> Dict[str, Any]:
        """Clean up orphaned model directories.
        
        Removes model directories that exist on the filesystem but are not
        referenced in the registry index.
        
        Returns
        -------
        Dict[str, Any]
            Cleanup results with counts of removed directories
        """
        try:
            index = self._load_index()
            registered_models = set(index["models"].keys())
            
            removed_count = 0
            removed_directories = []
            
            # Check all directories in models path
            if self.models_path.exists():
                for model_dir in self.models_path.iterdir():
                    if model_dir.is_dir() and model_dir.name not in registered_models:
                        try:
                            shutil.rmtree(model_dir)
                            removed_directories.append(model_dir.name)
                            removed_count += 1
                            logger.info(f"Removed orphaned directory: {model_dir}")
                        except Exception as e:
                            logger.warning(f"Failed to remove orphaned directory {model_dir}: {e}")
            
            return {
                "removed_directories": removed_count,
                "directories": removed_directories,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {
                "removed_directories": 0,
                "directories": [],
                "status": "error",
                "error": str(e)
            }
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get detailed statistics about the registry.
        
        Returns comprehensive statistics including model counts, types,
        storage usage, and temporal information.
        
        Returns
        -------
        Dict[str, Any]
            Registry statistics dictionary
        """
        try:
            index = self._load_index()
            models = index.get("models", {})
            
            if not models:
                return {
                    "total_models": 0,
                    "model_types": {},
                    "storage_usage": 0,
                    "newest_model": None,
                    "oldest_model": None
                }
            
            # Count models by type
            model_types = {}
            install_dates = []
            
            for model in models.values():
                model_type = model.get("type", "unknown")
                model_types[model_type] = model_types.get(model_type, 0) + 1
                
                install_date = model.get("installed_at")
                if install_date:
                    install_dates.append((install_date, model.get("name", "unknown")))
            
            # Calculate storage usage
            storage_usage = 0
            if self.models_path.exists():
                for model_dir in self.models_path.iterdir():
                    if model_dir.is_dir():
                        storage_usage += sum(f.stat().st_size for f in model_dir.rglob('*') if f.is_file())
            
            # Find newest and oldest models
            install_dates.sort()
            oldest_model = install_dates[0][1] if install_dates else None
            newest_model = install_dates[-1][1] if install_dates else None
            
            return {
                "total_models": len(models),
                "model_types": model_types,
                "storage_usage": storage_usage,
                "newest_model": newest_model,
                "oldest_model": oldest_model,
                "registry_path": str(self.registry_path)
            }
            
        except Exception as e:
            logger.error(f"Error getting registry stats: {e}")
            return {
                "total_models": 0,
                "model_types": {},
                "storage_usage": 0,
                "error": str(e)
            }
    
    # BaseModelRegistry interface compatibility methods
    
    def get_model_file_path(self, model_name: str, version: Optional[str] = None,
                           user_id: Optional[Union[UUID, str]] = None,
                           workspace_id: Optional[Union[UUID, str]] = None,
                           **kwargs) -> Optional[Path]:
        """Get local file path to a model.
        
        Parameters
        ----------
        model_name : str
            Name of the model
        version : Optional[str]
            Specific version (latest if None)
        user_id : Optional[Union[UUID, str]]
            User ID for permission checking (ignored in local mode)
        workspace_id : Optional[Union[UUID, str]]
            Workspace ID for workspace filtering (ignored in local mode)
        **kwargs
            Additional mode-specific parameters
            
        Returns
        -------
        Optional[Path]
            Path to model file or None if not found
        """
        try:
            # Find model by name (and version if specified)
            index = self._load_index()
            models = index.get("models", {})
            
            # Search for matching model
            for model_id, model in models.items():
                if model.get("name") == model_name:
                    if version is None or model.get("version") == version:
                        model_path = self.models_path / model_id / "model.pkl"
                        if model_path.exists():
                            return model_path
                            
            return None
            
        except Exception as e:
            logger.error(f"Error getting model file path: {e}")
            return None
    
    # Unified interface methods supporting both old and new patterns
    
    def list_models(self, filters: Optional[Dict[str, Any]] = None,
                   user_id: Optional[Union[UUID, str]] = None,
                   workspace_id: Optional[Union[UUID, str]] = None,
                   include_public: bool = True, **kwargs) -> List[Dict[str, Any]]:
        """List models available in the registry.
        
        Supports both original signature with filters and BaseModelRegistry interface.
        
        Parameters
        ----------
        filters : Optional[Dict[str, Any]]
            Filters to apply (original pattern)
        user_id : Optional[Union[UUID, str]]
            User ID for permission filtering (ignored in local mode)
        workspace_id : Optional[Union[UUID, str]]
            Workspace ID for workspace filtering (ignored in local mode)
        include_public : bool, default=True
            Whether to include public models (all models are public in local mode)
        **kwargs
            Additional parameters, including 'filters' for compatibility
            
        Returns
        -------
        List[Dict[str, Any]]
            List of model metadata dictionaries
        """
        user_str = str(user_id) if user_id else None
        
        with track_list_models("LOCAL", user_str):
            # Support filters from kwargs for backward compatibility
            if filters is None and 'filters' in kwargs:
                filters = kwargs['filters']
                
            # Use original implementation
            try:
                index = self._load_index()
                models = list(index["models"].values())
                
                if filters is None:
                    return models
                
                filtered_models = []
                for model in models:
                    if self._model_matches_filters(model, filters):
                        filtered_models.append(model)
                
                return filtered_models
                
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"Error loading registry index: {e}")
                return []
    
    def install_model(self, model_path: Path, name: Optional[str] = None, 
                     model_name: Optional[str] = None, version: Optional[str] = None,
                     description: str = "", tags: Optional[List[str]] = None,
                     user_id: Optional[Union[UUID, str]] = None,
                     workspace_id: Optional[Union[UUID, str]] = None,
                     **kwargs) -> Dict[str, Any]:
        """Install a model into the registry.
        
        Supports both original signature (model_path, name) and BaseModelRegistry 
        interface (model_path, model_name, version).
        
        Parameters
        ----------
        model_path : Path
            Path to the model file or directory
        name : Optional[str]
            Custom name for the model (original pattern)
        model_name : Optional[str] 
            Name of the model (BaseModelRegistry pattern)
        version : Optional[str]
            Version string for the model (BaseModelRegistry pattern)
        description : str, default=""
            Description of the model
        tags : Optional[List[str]]
            Optional tags for categorization
        user_id : Optional[Union[UUID, str]]
            User ID for ownership (ignored in local mode)
        workspace_id : Optional[Union[UUID, str]]
            Workspace ID for workspace association (ignored in local mode)
        **kwargs
            Additional mode-specific parameters
            
        Returns
        -------
        Dict[str, Any]
            Installed model metadata
        """
        # Determine which pattern is being used
        if model_name is not None:
            # New BaseModelRegistry pattern
            effective_name = model_name
        elif name is not None:
            # Original pattern
            effective_name = name
            if version is None:
                version = "1.0.0"  # Default version for old pattern
        else:
            # No name provided, use original behavior (name from manifest)
            effective_name = None
            if version is None:
                version = "1.0.0"  # Default version
        
        user_str = str(user_id) if user_id else None
        
        with track_install_model("LOCAL", "unknown", user_str):
            # Use original implementation with validation
            try:
                # Check storage thresholds before installation
                storage_warning = self.storage_manager.check_storage_thresholds()
                if storage_warning and storage_warning.level == "critical":
                    logger.warning(f"Storage warning: {storage_warning.message}")
                    # Don't block installation, but include warning in response
                    
                # Initialize ModelIOManager with the models path
                model_io = ModelIOManager(self.models_path)
                
                # Validate model and get manifest
                logger.info(f"Validating model at {model_path}")
                manifest = model_io.validate_model(model_path)
                
                # Use provided name or fall back to manifest name
                final_name = effective_name if effective_name is not None else manifest.get("name", "unnamed_model")
                
                # Install model using ModelIOManager
                logger.info(f"Installing model '{final_name}'")
                model_id = model_io.install_model(model_path, self.models_path, name=effective_name)
                
                # Track model storage size for metrics
                model_dir = self.models_path / model_id
                if model_dir.exists():
                    model_size = sum(f.stat().st_size for f in model_dir.rglob('*') if f.is_file())
                    track_model_storage(model_size, manifest.get("type", "unknown"))
                
                # Create model metadata entry
                model_info = {
                    "model_id": model_id,
                    "name": final_name,
                    "version": version,
                    "type": manifest.get("type", "unknown"),
                    "description": description or manifest.get("description", ""),
                    "installed_at": datetime.utcnow().isoformat(),
                    "source_path": str(model_path),
                    "manifest": manifest,
                    "tags": tags or []
                }
                
                # Update registry index
                index = self._load_index()
                index["models"][model_id] = model_info
                self._save_index(index)
                
                logger.info(f"Successfully installed model '{final_name}' with ID {model_id}")
                
                # Check for post-installation storage warnings
                post_warning = self.storage_manager.check_storage_thresholds()
                
                result = {
                    "status": "success",
                    "model_id": model_id,
                    "name": final_name,
                    "model": model_info,
                    "message": f"Model '{final_name}' installed successfully"
                }
                
                # Include storage warning in response if present
                if post_warning:
                    result["storage_warning"] = {
                        "level": post_warning.level,
                        "message": post_warning.message,
                        "usage_percent": post_warning.usage_percent,
                        "registry_size_mb": post_warning.registry_size_mb,
                        "available_space_mb": post_warning.available_space_mb
                    }
                    
                return result
                
            except Exception as e:
                logger.error(f"Error installing model: {e}")
                return {
                    "status": "error",
                    "message": str(e)
                }
    
    def get_model_info(self, model_id: Optional[str] = None, 
                      model_name: Optional[str] = None, version: Optional[str] = None,
                      user_id: Optional[Union[UUID, str]] = None,
                      workspace_id: Optional[Union[UUID, str]] = None,
                      **kwargs) -> Optional[Dict[str, Any]]:
        """Get detailed information about a model.
        
        Supports both original signature (model_id) and BaseModelRegistry 
        interface (model_name, version).
        
        Parameters
        ----------
        model_id : Optional[str]
            ID of the model to retrieve (original pattern)
        model_name : Optional[str]
            Name of the model (BaseModelRegistry pattern)
        version : Optional[str]
            Specific version to retrieve (BaseModelRegistry pattern)
        user_id : Optional[Union[UUID, str]]
            User ID for permission checking (ignored in local mode)
        workspace_id : Optional[Union[UUID, str]]
            Workspace ID for workspace filtering (ignored in local mode)
        **kwargs
            Additional mode-specific parameters
            
        Returns
        -------
        Optional[Dict[str, Any]]
            Model metadata or None if not found
        """
        user_str = str(user_id) if user_id else None
        
        with track_get_model_info("LOCAL", user_str):
            try:
                index = self._load_index()
                models = index.get("models", {})
                
                if model_id is not None:
                    # Original pattern - search by model_id
                    return models.get(model_id)
                elif model_name is not None:
                    # BaseModelRegistry pattern - search by name and version
                    for model_info in models.values():
                        if model_info.get("name") == model_name:
                            if version is None or model_info.get("version") == version:
                                return model_info
                                
                return None
                
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"Error loading registry index: {e}")
                return None
    
    def search_models(self, query: str, limit: int = 20,
                     user_id: Optional[Union[UUID, str]] = None,
                     workspace_id: Optional[Union[UUID, str]] = None,
                     include_public: bool = True, **kwargs) -> List[Dict[str, Any]]:
        """Search for models matching query criteria.
        
        Supports both original signature (query) and BaseModelRegistry interface.
        
        Parameters
        ----------
        query : str
            Search query string
        limit : int, default=20
            Maximum number of results to return (BaseModelRegistry pattern)
        user_id : Optional[Union[UUID, str]]
            User ID for permission filtering (ignored in local mode)
        workspace_id : Optional[Union[UUID, str]]
            Workspace ID for workspace filtering (ignored in local mode)
        include_public : bool, default=True
            Whether to include public models (all models are public in local mode)
        **kwargs
            Additional mode-specific parameters
            
        Returns
        -------
        List[Dict[str, Any]]
            List of matching model metadata
        """
        user_str = str(user_id) if user_id else None
        
        with track_search_models("LOCAL", user_str):
            # Use original implementation
            try:
                index = self._load_index()
                models = list(index.get("models", {}).values())
                
                if not query:
                    # Empty query returns all models (with limit if specified)
                    return models[:limit] if limit > 0 else models
                
                query_lower = query.lower()
                matching_models = []
                
                for model in models:
                    # Search in name and description
                    model_name = model.get("name", "").lower()
                    model_description = model.get("description", "").lower()
                    
                    if query_lower in model_name or query_lower in model_description:
                        matching_models.append(model)
                        
                # Apply limit if specified  
                return matching_models[:limit] if limit > 0 else matching_models
                
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"Error loading registry index: {e}")
                return []
    
    def remove_model(self, model_id: Optional[str] = None, 
                    model_name: Optional[str] = None, version: Optional[str] = None,
                    cleanup_files: bool = True,
                    user_id: Optional[Union[UUID, str]] = None,
                    workspace_id: Optional[Union[UUID, str]] = None,
                    **kwargs) -> Union[bool, Dict[str, Any]]:
        """Remove a model from the registry.
        
        Supports both original signature (model_id, cleanup_files) and BaseModelRegistry 
        interface (model_name, version).
        
        Parameters
        ----------
        model_id : Optional[str]
            ID of the model to remove (original pattern)
        model_name : Optional[str]
            Name of the model to remove (BaseModelRegistry pattern)
        version : Optional[str]
            Specific version to remove (BaseModelRegistry pattern)
        cleanup_files : bool, default=True
            Whether to clean up associated files
        user_id : Optional[Union[UUID, str]]
            User ID for permission checking (ignored in local mode)
        workspace_id : Optional[Union[UUID, str]]
            Workspace ID for workspace filtering (ignored in local mode)
        **kwargs
            Additional mode-specific parameters
            
        Returns
        -------
        Union[bool, Dict[str, Any]]
            Original pattern: Dict with status info
            BaseModelRegistry pattern: bool for success
        """
        user_str = str(user_id) if user_id else None
        model_type = "unknown"
        
        # Try to get model type before removal
        try:
            index = self._load_index()
            models = index.get("models", {})
            if model_id and model_id in models:
                model_type = models[model_id].get("type", "unknown")
            elif model_name:
                for model_info in models.values():
                    if model_info.get("name") == model_name:
                        if version is None or model_info.get("version") == version:
                            model_type = model_info.get("type", "unknown")
                            break
        except Exception:
            pass  # Continue with unknown type if we can't determine it
        
        with track_remove_model("LOCAL", model_type, user_str):
            try:
                index = self._load_index()
                models = index.get("models", {})
                
                if model_id is not None:
                    # Original pattern - remove by model_id
                    if model_id not in models:
                        return {
                            "status": "error",
                            "message": f"Model not found: {model_id}"
                        }
                    
                    # Remove from index
                    model_info = models.pop(model_id, None)
                    
                    # Clean up files if requested
                    if cleanup_files:
                        model_path = self.models_path / model_id
                        if model_path.exists():
                            try:
                                shutil.rmtree(model_path)
                            except Exception as e:
                                logger.warning(f"Error cleaning up model files: {e}")
                    
                    # Save updated index
                    self._save_index(index)
                    
                    return {
                        "status": "success",
                        "model_id": model_id,
                        "removed_model": model_info
                    }
                    
                elif model_name is not None:
                    # BaseModelRegistry pattern - remove by name and version
                    model_ids_to_remove = []
                    for mid, model in models.items():
                        if model.get("name") == model_name:
                            if version is None or model.get("version") == version:
                                model_ids_to_remove.append(mid)
                    
                    if not model_ids_to_remove:
                        return False  # Not found
                    
                    # Remove all matching models
                    success = True
                    for mid in model_ids_to_remove:
                        try:
                            models.pop(mid, None)
                            
                            # Clean up files
                            if cleanup_files:
                                model_path = self.models_path / mid
                                if model_path.exists():
                                    shutil.rmtree(model_path)
                                    
                        except Exception as e:
                            logger.error(f"Error removing model {mid}: {e}")
                            success = False
                    
                    # Save updated index
                    self._save_index(index)
                    return success
                
                else:
                    # Neither model_id nor model_name provided
                    if 'model_id' in kwargs:
                        # Handle case where model_id is in kwargs (for compatibility)
                        return self.remove_model(model_id=kwargs['model_id'], cleanup_files=cleanup_files)
                    else:
                        return False
                    
            except Exception as e:
                logger.error(f"Error removing model: {e}")
                if model_id is not None:
                    return {"status": "error", "message": str(e)}
                else:
                    return False