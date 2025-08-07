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
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from emuses.tools.model_io import ModelIOManager

logger = logging.getLogger(__name__)


class LocalModelRegistry:
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
    
    def list_models(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List models in the registry with optional filtering.
        
        Parameters
        ----------
        filters : Dict[str, Any], optional
            Filters to apply to model listing. Supported filters:
            - type: Model type (classification, detection, etc.)
            - tags: List of tags that must be present
            - name: Name pattern to match
            
        Returns
        -------
        List[Dict[str, Any]]
            List of model metadata dictionaries matching filters
        """
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
    
    def install_model(self, model_path: Path, name: Optional[str] = None) -> Dict[str, Any]:
        """Install a model into the registry.
        
        Validates the model, installs it using ModelIOManager, and updates
        the registry index with metadata.
        
        Parameters
        ----------
        model_path : Path
            Path to the model file or directory to install
        name : str, optional
            Custom name for the model. If None, uses name from manifest.
            
        Returns
        -------
        Dict[str, Any]
            Installation result with status, model_id, and details
            
        Examples
        --------
        >>> registry = LocalModelRegistry()
        >>> result = registry.install_model(Path("model.zip"), name="my_model")
        >>> print(result["status"])  # "success" or "error"
        """
        try:
            # Initialize ModelIOManager
            model_io = ModelIOManager()
            
            # Validate model and get manifest
            logger.info(f"Validating model at {model_path}")
            manifest = model_io.validate_model(model_path)
            
            # Use provided name or fall back to manifest name
            model_name = name if name is not None else manifest.get("name", "unnamed_model")
            
            # Install model using ModelIOManager
            logger.info(f"Installing model '{model_name}'")
            model_id = model_io.install_model(model_path, self.models_path)
            
            # Create model metadata entry
            model_metadata = {
                "model_id": model_id,
                "name": model_name,
                "version": manifest.get("version", "unknown"),
                "type": manifest.get("type", "unknown"),
                "description": manifest.get("description", ""),
                "installed_at": datetime.utcnow().isoformat(),
                "source_path": str(model_path),
                "manifest": manifest
            }
            
            # Update registry index
            index = self._load_index()
            index["models"][model_id] = model_metadata
            self._save_index(index)
            
            logger.info(f"Successfully installed model '{model_name}' with ID {model_id}")
            
            return {
                "status": "success",
                "model_id": model_id,
                "name": model_name,
                "message": f"Model '{model_name}' installed successfully"
            }
            
        except Exception as e:
            error_msg = f"Failed to install model: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "error_type": type(e).__name__
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
    
    def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific model.
        
        Parameters
        ----------
        model_id : str
            ID of the model to retrieve information for
            
        Returns
        -------
        Optional[Dict[str, Any]]
            Model metadata dictionary, or None if model not found
        """
        try:
            index = self._load_index()
            return index["models"].get(model_id)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading registry index: {e}")
            return None
    
    def search_models(self, query: str) -> List[Dict[str, Any]]:
        """Search for models by name or description.
        
        Performs case-insensitive search across model names and descriptions.
        
        Parameters
        ----------
        query : str
            Search query string
            
        Returns
        -------
        List[Dict[str, Any]]
            List of models matching the search query
        """
        try:
            index = self._load_index()
            query_lower = query.lower()
            matching_models = []
            
            for model in index["models"].values():
                # Search in name
                if query_lower in model.get("name", "").lower():
                    matching_models.append(model)
                    continue
                
                # Search in description
                if query_lower in model.get("description", "").lower():
                    matching_models.append(model)
                    continue
                
                # Search in tags
                tags = model.get("tags", [])
                if any(query_lower in tag.lower() for tag in tags):
                    matching_models.append(model)
            
            return matching_models
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading registry index: {e}")
            return []
    
    def remove_model(self, model_id: str, cleanup_files: bool = True) -> Dict[str, Any]:
        """Remove a model from the registry.
        
        Removes the model from the registry index and optionally cleans up
        associated files and directories.
        
        Parameters
        ----------
        model_id : str
            ID of the model to remove
        cleanup_files : bool, default=True
            Whether to remove model files and directories
            
        Returns
        -------
        Dict[str, Any]
            Removal result with status and details
        """
        try:
            index = self._load_index()
            
            # Check if model exists
            if model_id not in index["models"]:
                return {
                    "status": "error",
                    "message": f"Model with ID '{model_id}' not found"
                }
            
            model_info = index["models"][model_id]
            model_name = model_info.get("name", "unknown")
            
            # Remove from index
            del index["models"][model_id]
            self._save_index(index)
            
            # Clean up files if requested
            if cleanup_files:
                model_dir = self.models_path / model_id
                if model_dir.exists():
                    shutil.rmtree(model_dir)
                    logger.info(f"Removed model directory: {model_dir}")
            
            logger.info(f"Successfully removed model '{model_name}' (ID: {model_id})")
            
            return {
                "status": "success",
                "model_id": model_id,
                "name": model_name,
                "message": f"Model '{model_name}' removed successfully"
            }
            
        except Exception as e:
            error_msg = f"Failed to remove model: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "error_type": type(e).__name__
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