"""Local file-based model registry implementation.

This module provides a local model registry that stores models and metadata
in a directory structure on the local filesystem. It serves as the foundation
for more advanced registry implementations.
"""
import json
import logging
import shutil
import uuid
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager

# File locking support - fallback for Windows
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

from emuses.tools.model_io import ModelIOManager
from emuses.tools.base_model_registry import BaseModelRegistry
from emuses.tools.storage_manager import StorageManager
from emuses.tools.model_registry_metrics import track_list_models, track_install_model, track_search_models, track_get_model_info, track_remove_model, track_model_storage

logger = logging.getLogger(__name__)


class TransactionState(Enum):
    """Transaction state enumeration."""
    PENDING = "pending"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"


@dataclass
class RegistryOperation:
    """Registry operation with rollback information.

    Represents a single atomic operation within a registry transaction,
    including the information needed to rollback the operation if needed.
    """
    operation_type: str
    target_path: Path
    rollback_info: Dict[str, Any]


@dataclass
class RegistryTransaction:
    """Atomic registry transaction.

    Manages a sequence of registry operations that must be executed
    atomically - either all operations succeed or all are rolled back.
    """
    transaction_id: str
    operations: List[RegistryOperation] = field(default_factory=list)
    rollback_data: Dict[str, Any] = field(default_factory=dict)
    state: TransactionState = TransactionState.PENDING


# Complex deduplication classes removed - simplified to basic skip_duplicates flag


class LocalModelRegistry(BaseModelRegistry):
    """Local file-based model registry with thread-safe operations.

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

        # Thread-safe access control
        self._index_lock = threading.RLock()  # Reentrant lock for nested operations

        self._initialize_registry()

    @contextmanager
    def _safe_index_access(self, mode='r'):
        """
        Context manager for thread-safe and file-safe index access.

        Provides both thread-level locking and file-level locking to prevent
        race conditions during concurrent registry operations.

        Parameters
        ----------
        mode : str
            File access mode ('r' for read, 'w' for write, 'r+' for read/write)
        """
        with self._index_lock:  # Thread-level synchronization
            # Ensure index file exists before attempting to lock it
            if not self.index_path.exists() and 'r' in mode:
                # Create empty index if it doesn't exist for read operations
                self._create_empty_index()

            try:
                # File-level locking for cross-process safety
                with open(self.index_path, mode) as f:
                    try:
                        if HAS_FCNTL:
                            if 'w' in mode or '+' in mode:
                                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock for writes
                            else:
                                fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reads

                        yield f

                    finally:
                        if HAS_FCNTL:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Always unlock

            except (OSError, IOError) as e:
                if 'w' in mode and not self.index_path.exists():
                    # Create the index file if it doesn't exist for write operations
                    self._create_empty_index()
                    with open(self.index_path, mode) as f:
                        if HAS_FCNTL:
                            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                        yield f
                        if HAS_FCNTL:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                else:
                    raise

    def _create_empty_index(self) -> None:
        """Create an empty registry index file."""
        empty_index = {
            "version": self.REGISTRY_VERSION,
            "created": datetime.utcnow().isoformat() + "Z",
            "last_modified": datetime.utcnow().isoformat() + "Z",
            "models": {}
        }

        self.registry_path.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, 'w') as f:
            json.dump(empty_index, f, indent=2)

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
        """Load the registry index from JSON file with thread-safe access.

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
        try:
            with self._safe_index_access('r') as f:
                content = f.read().strip()
                if not content:
                    # Handle empty file - return default structure
                    return {
                        "version": self.REGISTRY_VERSION,
                        "created": datetime.utcnow().isoformat() + "Z",
                        "last_modified": datetime.utcnow().isoformat() + "Z",
                        "models": {}
                    }
                return json.loads(content)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading registry index: {e}")
            # Return empty structure on error
            return {
                "version": self.REGISTRY_VERSION,
                "created": datetime.utcnow().isoformat() + "Z",
                "last_modified": datetime.utcnow().isoformat() + "Z",
                "models": {}
            }

    def _save_index(self, index_data: Dict[str, Any]) -> None:
        """Save the registry index to JSON file with thread-safe access.

        Parameters
        ----------
        index_data : Dict[str, Any]
            Registry index data to save

        Raises
        ------
        OSError
            If unable to write to registry.json
        """
        index_data["last_modified"] = datetime.utcnow().isoformat() + "Z"

        with self._safe_index_access('w') as f:
            f.truncate(0)  # Clear file content completely before writing
            f.seek(0)      # Reset file position to beginning
            json.dump(index_data, f, indent=2, sort_keys=True)
            f.flush()      # Ensure data is written to disk

    def _atomic_index_update(self, update_func) -> None:
        """
        Atomically update the registry index using a function.

        This ensures the load-modify-save cycle is atomic to prevent
        race conditions during concurrent operations.

        Parameters
        ----------
        update_func : callable
            Function that takes the index dict and modifies it in place
        """
        with self._safe_index_access('r+') as f:
            # Read current index
            content = f.read().strip()
            if content:
                index = json.loads(content)
            else:
                index = {
                    "version": self.REGISTRY_VERSION,
                    "created": datetime.utcnow().isoformat() + "Z",
                    "last_modified": datetime.utcnow().isoformat() + "Z",
                    "models": {}
                }

            # Apply update function
            update_func(index)

            # Update timestamp and write back atomically
            index["last_modified"] = datetime.utcnow().isoformat() + "Z"

            # Write back to file
            f.seek(0)
            f.truncate(0)
            json.dump(index, f, indent=2, sort_keys=True)
            f.flush()

    def _add_model_to_index(self, index: Dict[str, Any], model_id: str, model_info: Dict[str, Any]) -> None:
        """Add a model to the registry index."""
        if "models" not in index:
            index["models"] = {}
        index["models"][model_id] = model_info

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
        for required_field in required_fields:
            if required_field not in index:
                issues.append(f"Missing required field: {required_field}")

        # Validate model entries
        for model_id, model_data in index.get("models", {}).items():
            required_model_fields = ["model_id", "name", "installed_at"]
            for model_field in required_model_fields:
                if model_field not in model_data:
                    issues.append(f"Model {model_id} missing field: {model_field}")

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

    def install_model(self, model_path: Path, model_name: Optional[str] = None,
                     version: Optional[str] = None, description: str = "",
                     tags: Optional[List[str]] = None,
                     user_id: Optional[Union[UUID, str]] = None,
                     workspace_id: Optional[Union[UUID, str]] = None,
                     transaction: Optional[RegistryTransaction] = None,
                     **kwargs) -> Dict[str, Any]:
        """Install a model into the registry.

        Parameters
        ----------
        model_path : Path
            Path to the model file or directory
        model_name : Optional[str]
            Name of the model. If not provided, uses name from model manifest.
        version : Optional[str]
            Version string for the model. If not provided, uses version from model manifest.
        description : str, default=""
            Description of the model
        tags : Optional[List[str]]
            Optional tags for categorization
        user_id : Optional[Union[UUID, str]]
            User ID for ownership (ignored in local mode)
        workspace_id : Optional[Union[UUID, str]]
            Workspace ID for workspace association (ignored in local mode)
        transaction : Optional[RegistryTransaction]
            Transaction for atomic operations. If provided, changes are not
            committed until transaction.commit() is called.
        **kwargs
            Additional mode-specific parameters

        Returns
        -------
        Dict[str, Any]
            Installed model metadata
        """
        # Use provided model_name or fall back to name from manifest
        effective_name = model_name

        # Set default version if not provided
        if version is None:
            version = "1.0.0"

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

                # Validate model and get enhanced information
                logger.info(f"Validating model at {model_path}")
                validation_result = model_io.validate_model(model_path)

                # Reject invalid EMUSES folders
                if not validation_result.is_complete_model:
                    error_msg = f"Invalid EMUSES folder: {'; '.join(validation_result.validation_errors)}"
                    logger.error(error_msg)
                    return {
                        "status": "error",
                        "message": error_msg
                    }

                # Extract basic manifest information from validation result
                manifest = {
                    "name": validation_result.name,
                    "version": validation_result.version,
                    "type": validation_result.type,
                    "description": validation_result.description
                }

                # Use provided name or fall back to validation result name
                final_name = effective_name if effective_name is not None else validation_result.name

                # Install model using ModelIOManager with shared storage optimization
                logger.info(f"Installing model '{final_name}'")
                model_id = model_io.install_model(
                    source_path=model_path,
                    destination_path=self.models_path,
                    name=effective_name,
                    use_shared_storage=True,
                    registry_base_path=self.registry_path
                )

                # Record operation for transaction rollback
                if transaction:
                    model_dir = self.models_path / model_id
                    transaction.operations.append(RegistryOperation(
                        operation_type="copy_files",
                        target_path=model_dir,
                        rollback_info={"model_id": model_id}
                    ))

                # Track model storage size for metrics
                model_dir = self.models_path / model_id
                if model_dir.exists():
                    model_size = sum(f.stat().st_size for f in model_dir.rglob('*') if f.is_file())
                    track_model_storage(model_size, manifest.get("type", "unknown"))

                # Create model metadata entry for complete EMUSES folder
                model_info = {
                    "model_id": model_id,
                    "name": final_name,
                    "version": version,
                    "type": manifest.get("type", "emuses_model"),
                    "description": description or manifest.get("description", ""),
                    "installed_at": datetime.utcnow().isoformat(),
                    "source_path": str(model_path),
                    "manifest": manifest,
                    "tags": tags or [],
                    # Simple validation info - treat folder as atomic unit
                    "validation_info": {
                        "is_valid_emuses_folder": validation_result.is_complete_model,
                        "configuration_hash": validation_result.configuration_hash,
                        "content_hash": validation_result.content_hash,
                        "validation_errors": validation_result.validation_errors,
                        # Feature augmentation models detected (optional components)
                        "feature_models": self._extract_feature_model_info(validation_result.components_found)
                    }
                }

                if transaction:
                    # Store index update for later commit
                    if "pending_index_updates" not in transaction.rollback_data:
                        transaction.rollback_data["pending_index_updates"] = {}
                    transaction.rollback_data["pending_index_updates"][model_id] = model_info
                else:
                    # Update registry index atomically
                    self._atomic_index_update(lambda index: self._add_model_to_index(index, model_id, model_info))

                logger.info(f"Successfully installed model '{final_name}' with ID {model_id}")

                # Enhance model manifest with pipeline data
                try:
                    from emuses.tools.model_io import enhance_model_manifest_with_pipeline_data
                    logger.info("Enhancing installed model manifest with pipeline data...")
                    success = enhance_model_manifest_with_pipeline_data(model_path)
                    if success:
                        logger.info("Installed model manifest successfully enhanced")
                    else:
                        logger.warning("Installed model manifest enhancement failed")
                except Exception as e:
                    logger.warning(f"Could not enhance installed model manifest: {e}")

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
                # Enhanced error reporting for better debugging
                error_message = str(e) if str(e) and str(e) != "message" else f"{type(e).__name__}: {repr(e)}"
                logger.error(f"Error installing model: {error_message}")

                # Rollback transaction on error
                if transaction:
                    try:
                        self.rollback_transaction(transaction)
                    except Exception as rollback_error:
                        logger.error(f"Rollback failed: {rollback_error}")

                return {
                    "status": "error",
                    "message": error_message
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

    # REMOVED: get_model_components() method
    # This method violated EMUSES architecture by treating models as collections
    # of separable components. EMUSES models are complete training folder units.
    # Use get_model_path() to access the complete folder instead.

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

    # Atomic Transaction Framework

    def begin_transaction(self) -> RegistryTransaction:
        """
        Begin a new atomic transaction for registry operations.

        Returns
        -------
        RegistryTransaction
            New transaction object with unique ID
        """
        transaction_id = str(uuid.uuid4())
        transaction = RegistryTransaction(transaction_id=transaction_id)

        logger.debug(f"Started registry transaction: {transaction_id}")
        return transaction

    def commit_transaction(self, transaction: RegistryTransaction) -> bool:
        """
        Commit a transaction, making all pending operations permanent.

        Parameters
        ----------
        transaction : RegistryTransaction
            Transaction to commit

        Returns
        -------
        bool
            True if commit succeeded, False otherwise
        """
        if transaction.state != TransactionState.PENDING:
            logger.error(f"Cannot commit transaction {transaction.transaction_id}: state is {transaction.state}")
            return False

        try:
            # Apply all pending index updates atomically
            if "pending_index_updates" in transaction.rollback_data:
                pending_updates = transaction.rollback_data["pending_index_updates"]

                def apply_updates(index):
                    """Apply all pending updates to the index."""
                    for model_id, model_info in pending_updates.items():
                        self._add_model_to_index(index, model_id, model_info)

                self._atomic_index_update(apply_updates)

            # Mark transaction as committed
            transaction.state = TransactionState.COMMITTED
            logger.info(f"Committed transaction {transaction.transaction_id} with {len(transaction.operations)} operations")

            return True

        except Exception as e:
            logger.error(f"Failed to commit transaction {transaction.transaction_id}: {e}")
            # Attempt rollback
            try:
                self.rollback_transaction(transaction)
            except Exception as rollback_error:
                logger.error(f"Rollback also failed: {rollback_error}")
            return False

    def rollback_transaction(self, transaction: RegistryTransaction) -> bool:
        """
        Rollback a transaction, undoing all operations.

        Parameters
        ----------
        transaction : RegistryTransaction
            Transaction to rollback

        Returns
        -------
        bool
            True if rollback succeeded, False otherwise
        """
        if transaction.state == TransactionState.ROLLED_BACK:
            logger.warning(f"Transaction {transaction.transaction_id} already rolled back")
            return True

        if transaction.state == TransactionState.COMMITTED:
            logger.error(f"Cannot rollback committed transaction {transaction.transaction_id}")
            return False

        try:
            # Rollback operations in reverse order
            for operation in reversed(transaction.operations):
                self._rollback_operation(operation)

            # Mark transaction as rolled back
            transaction.state = TransactionState.ROLLED_BACK
            logger.info(f"Rolled back transaction {transaction.transaction_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to rollback transaction {transaction.transaction_id}: {e}")
            return False

    def _rollback_operation(self, operation: RegistryOperation) -> None:
        """
        Rollback a specific registry operation.

        Parameters
        ----------
        operation : RegistryOperation
            Operation to rollback
        """
        try:
            if operation.operation_type == "create_directory":
                # Remove created directory
                if operation.target_path.exists():
                    shutil.rmtree(operation.target_path, ignore_errors=True)
                    logger.debug(f"Removed directory: {operation.target_path}")

            elif operation.operation_type == "copy_files":
                # Remove copied files/directories
                if operation.target_path.exists():
                    if operation.target_path.is_dir():
                        shutil.rmtree(operation.target_path, ignore_errors=True)
                    else:
                        operation.target_path.unlink(missing_ok=True)
                    logger.debug(f"Removed copied files: {operation.target_path}")

            # Additional operation types can be added here

        except Exception as e:
            logger.warning(f"Failed to rollback operation {operation.operation_type} on {operation.target_path}: {e}")
            # Continue with other operations even if one fails

    # Hash-based Duplicate Detection

    def find_duplicates_by_configuration_hash(self, configuration_hash: str) -> List[Dict[str, Any]]:
        """
        Find all EMUSES folders with the given configuration hash.

        Parameters
        ----------
        configuration_hash : str
            Configuration hash to search for

        Returns
        -------
        List[Dict[str, Any]]
            List of EMUSES models with matching configuration hash
        """
        try:
            index = self._load_index()
            models = index.get("models", {})

            matching_models = []
            for model_id, model_info in models.items():
                validation_info = model_info.get("validation_info", {})
                model_config_hash = validation_info.get("configuration_hash", "")

                if model_config_hash == configuration_hash:
                    matching_models.append(model_info)

            logger.debug(f"Found {len(matching_models)} models with configuration hash {configuration_hash}")
            return matching_models

        except Exception as e:
            logger.error(f"Error finding duplicates by configuration hash: {e}")
            return []

    def find_duplicates_by_content_hash(self, content_hash: str) -> List[Dict[str, Any]]:
        """
        Find all EMUSES folders with the given content hash.

        Parameters
        ----------
        content_hash : str
            Content hash to search for

        Returns
        -------
        List[Dict[str, Any]]
            List of EMUSES models with matching content hash
        """
        try:
            index = self._load_index()
            models = index.get("models", {})

            matching_models = []
            for model_id, model_info in models.items():
                validation_info = model_info.get("validation_info", {})
                model_content_hash = validation_info.get("content_hash", "")

                if model_content_hash == content_hash:
                    matching_models.append(model_info)

            logger.debug(f"Found {len(matching_models)} models with content hash {content_hash}")
            return matching_models

        except Exception as e:
            logger.error(f"Error finding duplicates by content hash: {e}")
            return []

    def get_duplicate_summary(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        Get a comprehensive summary of all duplicate models in the registry.

        Returns
        -------
        Dict[str, Dict[str, List[Dict[str, Any]]]]
            Dictionary with 'configuration_duplicates' and 'content_duplicates' keys,
            each containing hash -> list of models mappings
        """
        try:
            index = self._load_index()
            models = index.get("models", {})

            # Group models by configuration hash
            config_hash_groups = {}
            content_hash_groups = {}

            for model_id, model_info in models.items():
                validation_info = model_info.get("validation_info", {})

                config_hash = validation_info.get("configuration_hash", "")
                content_hash = validation_info.get("content_hash", "")

                # Lightweight model info for summary
                model_summary = {
                    "model_id": model_info.get("model_id", model_id),
                    "name": model_info.get("name", "unknown"),
                    "version": model_info.get("version", "unknown"),
                    "type": model_info.get("type", "unknown"),
                    "installed_at": model_info.get("installed_at", "unknown")
                }

                # Group by configuration hash
                if config_hash:
                    if config_hash not in config_hash_groups:
                        config_hash_groups[config_hash] = []
                    config_hash_groups[config_hash].append(model_summary)

                # Group by content hash
                if content_hash:
                    if content_hash not in content_hash_groups:
                        content_hash_groups[content_hash] = []
                    content_hash_groups[content_hash].append(model_summary)

            # Filter to only include groups with duplicates (>1 model)
            config_duplicates = {h: models for h, models in config_hash_groups.items() if len(models) > 1}
            content_duplicates = {h: models for h, models in content_hash_groups.items() if len(models) > 1}

            return {
                "configuration_duplicates": config_duplicates,
                "content_duplicates": content_duplicates
            }

        except Exception as e:
            logger.error(f"Error getting duplicate summary: {e}")
            return {
                "configuration_duplicates": {},
                "content_duplicates": {}
            }

    def find_potential_duplicates(self, model_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Find potential duplicates for a specific model.

        Parameters
        ----------
        model_id : str
            ID of the model to find duplicates for

        Returns
        -------
        Dict[str, List[Dict[str, Any]]]
            Dictionary with 'configuration_matches' and 'content_matches' keys
        """
        try:
            model_info = self.get_model_info(model_id)
            if not model_info:
                return {"configuration_matches": [], "content_matches": []}

            validation_info = model_info.get("validation_info", {})
            config_hash = validation_info.get("configuration_hash", "")
            content_hash = validation_info.get("content_hash", "")

            config_matches = []
            content_matches = []

            if config_hash:
                config_matches = [
                    m for m in self.find_duplicates_by_configuration_hash(config_hash)
                    if m.get("model_id") != model_id
                ]

            if content_hash:
                content_matches = [
                    m for m in self.find_duplicates_by_content_hash(content_hash)
                    if m.get("model_id") != model_id
                ]

            return {
                "configuration_matches": config_matches,
                "content_matches": content_matches
            }

        except Exception as e:
            logger.error(f"Error finding potential duplicates for {model_id}: {e}")
            return {"configuration_matches": [], "content_matches": []}

    # Enhanced Installation Workflow with Deduplication Integration

    def install_model_with_deduplication(self, model_path: Path,
                                       skip_duplicates: bool = True,
                                       transaction: Optional[RegistryTransaction] = None,
                                       **kwargs) -> Dict[str, Any]:
        """
        Install a model with simple duplicate detection based on exact hash matching.

        Uses stable content and configuration hashes to detect exact duplicates.
        When duplicates are found, provides clear messaging and skips installation.

        Parameters
        ----------
        model_path : Path
            Path to the model file or directory to install
        skip_duplicates : bool, default=True
            Whether to skip installation if exact duplicate found
        transaction : Optional[RegistryTransaction]
            Optional transaction for atomic operations
        **kwargs
            Additional parameters passed to base install_model

        Returns
        -------
        Dict[str, Any]
            Installation result with duplicate status information
        """
        try:
            # Initialize ModelIOManager for validation
            model_io = ModelIOManager(self.models_path)

            # Validate the model to get stable hashes
            logger.info(f"Validating model at {model_path}")
            validation_result = model_io.validate_model(model_path)

            # Check for exact duplicate using stable hashes
            if skip_duplicates:
                duplicate_check = self._check_exact_duplicate(validation_result)
                if duplicate_check["duplicate_found"]:
                    existing_info = duplicate_check["existing_model"]
                    print(f"✓ Model already installed as '{existing_info['name']}' ({existing_info['model_id']})")
                    return {
                        "status": "skipped",
                        "reason": "duplicate_model",
                        "existing_model_id": existing_info["model_id"],
                        "existing_model_name": existing_info["name"]
                    }

            # No duplicate found or skip_duplicates=False, proceed with installation
            result = self.install_model(
                model_path=model_path,
                transaction=transaction,
                **kwargs
            )

            return result

        except Exception as e:
            # Enhanced error reporting for better debugging
            error_message = str(e) if str(e) and str(e) != "message" else f"{type(e).__name__}: {repr(e)}"
            logger.error(f"Error in model installation: {error_message}")
            return {
                "status": "error",
                "message": error_message
            }

    def _check_exact_duplicate(self, validation_result) -> Dict[str, Any]:
        """
        Simple exact hash matching for complete EMUSES folder duplicates.

        Uses stable content and configuration hashes to identify exact duplicates
        of complete EMUSES training folders. Treats folders as atomic units.

        Parameters
        ----------
        validation_result : CompleteModelValidation
            EMUSES folder validation result with stable hashes

        Returns
        -------
        Dict[str, Any]
            Duplicate check result with existing model info if found
        """
        existing_models = self._load_index().get("models", {})

        for model_id, model_info in existing_models.items():
            validation_info = model_info.get("validation_info", {})
            existing_config = validation_info.get("configuration_hash", "")
            existing_content = validation_info.get("content_hash", "")

            # Check for exact match on both configuration and content hashes
            if (validation_result.configuration_hash == existing_config and
                validation_result.content_hash == existing_content):
                return {
                    "duplicate_found": True,
                    "existing_model": {
                        "model_id": model_id,
                        "name": model_info.get("name", "unknown"),
                        "version": model_info.get("version", "unknown"),
                        "created_at": model_info.get("installed_at", "unknown")
                    }
                }

        return {"duplicate_found": False}

    # Removed complex _check_for_duplicates method - replaced with _check_exact_duplicate

    # Removed complex _resolve_duplicates method - replaced with simple skip_duplicates flag

    # Removed complex _handle_batch_resolution method - replaced with simple batch handling

    def _generate_unique_model_name(self, validation_result) -> str:
        """
        Generate a unique model name when forcing installation of duplicates.

        Parameters
        ----------
        validation_result : CompleteModelValidation
            Model validation result

        Returns
        -------
        str
            Unique model name
        """
        base_name = validation_result.name
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_suffix = uuid.uuid4().hex[:8]

        return f"{base_name}_{timestamp}_{unique_suffix}"

    def _extract_feature_model_info(self, components_found: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Extract feature model information from validation components.

        This method processes the components found during model validation
        and extracts information about feature augmentation models (PCA,
        kPCA, autoencoder) that are part of the EMUSES folder.

        Parameters
        ----------
        components_found : Dict[str, Any]
            Components dictionary from model validation

        Returns
        -------
        Dict[str, List[str]]
            Dictionary mapping feature model types to lists of model filenames

        Example
        -------
        {
            'pca': ['pca_model_v1_0_0.joblib'],
            'autoencoder': ['autoencoder_model_v1_0_0.joblib'],
            'kpca': []  # None found
        }
        """
        feature_info = {
            'pca': [],
            'kpca': [],
            'autoencoder': []
        }

        # Process components to extract feature model filenames
        for key, value in components_found.items():
            if key.endswith('_models'):
                # Extract model type from key (e.g., 'pca_models' -> 'pca')
                model_type = key[:-7]  # Remove '_models' suffix

                if model_type in feature_info and isinstance(value, list):
                    # Extract filenames from Path objects
                    feature_info[model_type] = [
                        path.name if hasattr(path, 'name') else str(path)
                        for path in value
                    ]

        return feature_info

    def generate_semantic_model_id(self, validation_result, suffix_counter: int = 1) -> str:
        """
        Generate semantic model ID with meaningful version detection.

        Creates human-readable model IDs that incorporate model name, version,
        and configuration information for better identification and management.

        Parameters
        ----------
        validation_result : CompleteModelValidation
            Model validation result with metadata
        suffix_counter : int, default=1
            Counter for generating unique IDs when duplicates exist

        Returns
        -------
        str
            Semantic model ID
        """
        # Extract base components
        name = validation_result.name.replace(" ", "_").lower()
        version = validation_result.version.replace(".", "_")
        config_hash_short = validation_result.configuration_hash[:8]

        # Build semantic ID components
        id_components = [name, f"v{version}"]

        # Add configuration hash for uniqueness
        if config_hash_short:
            id_components.append(config_hash_short)

        # Add counter suffix if needed for uniqueness
        if suffix_counter > 1:
            id_components.append(f"n{suffix_counter}")

        # Join and ensure reasonable length
        semantic_id = "_".join(id_components)

        # Truncate if too long while preserving key information
        if len(semantic_id) > 64:
            # Keep name_version and hash, truncate middle if needed
            semantic_id = f"{name}_v{version}_{config_hash_short}"
            if suffix_counter > 1:
                semantic_id += f"_n{suffix_counter}"

        return semantic_id

    def install_model_with_interactive_resolution(self, model_path: Path,
                                                 options: Optional[Dict[str, Any]] = None,
                                                 transaction: Optional[RegistryTransaction] = None,
                                                 **kwargs) -> Dict[str, Any]:
        """
        Install a model with interactive CLI duplicate resolution.

        NOTE: Interactive workflows have been simplified. This method now
        delegates to the basic deduplication workflow for consistent behavior.

        Parameters
        ----------
        model_path : Path
            Path to the model file or directory to install
        options : Optional[Dict[str, Any]]
            Installation options (ignored - simplified behavior)
        transaction : Optional[RegistryTransaction]
            Optional transaction for atomic operations
        **kwargs
            Additional parameters passed to base install_model

        Returns
        -------
        Dict[str, Any]
            Installation result with duplicate status information
        """
        # Interactive workflows have been simplified - delegate to basic deduplication
        return self.install_model_with_deduplication(
            model_path=model_path,
            skip_duplicates=True,
            transaction=transaction,
            **kwargs
        )

    # Removed complex interactive resolution methods - replaced with simple deduplication

    def install_model_with_batch_deduplication(self, model_path: Path,
                                              options: Optional[Dict[str, Any]] = None,
                                              transaction: Optional[RegistryTransaction] = None,
                                              **kwargs) -> Dict[str, Any]:
        """
        Install a model with batch duplicate resolution using simple policies.

        NOTE: Batch workflows have been simplified. This method now delegates
        to the basic deduplication workflow for consistent behavior.

        Parameters
        ----------
        model_path : Path
            Path to the model directory to install
        options : Optional[Dict[str, Any]], optional
            Installation options (ignored - simplified behavior)
        transaction : RegistryTransaction, optional
            Existing transaction to use for atomic operations

        Returns
        -------
        Dict[str, Any]
            Installation result with batch processing status
        """
        # Simplified batch processing - delegate to basic deduplication
        return self.install_model_with_deduplication(
            model_path=model_path,
            skip_duplicates=True,
            transaction=transaction,
            **kwargs
        )

    def batch_install_models_with_deduplication(self, model_paths: List[Path],
                                               batch_policies: Dict[str, str] = None,
                                               continue_on_error: bool = False) -> List[Dict[str, Any]]:
        """
        Install multiple models with simplified batch duplicate resolution.

        NOTE: Batch policies have been simplified. This method now uses
        basic deduplication for all models in the batch.

        Parameters
        ----------
        model_paths : List[Path]
            List of model directory paths to install
        batch_policies : Dict[str, str], optional
            Batch policies (ignored - simplified behavior)
        continue_on_error : bool, optional
            Whether to continue processing if one model fails

        Returns
        -------
        List[Dict[str, Any]]
            List of installation results for each model
        """
        results = []

        for model_path in model_paths:
            try:
                # Use simplified deduplication for each model in batch
                result = self.install_model_with_deduplication(
                    model_path=model_path,
                    skip_duplicates=True
                )
                result["batch_processed"] = True
                results.append(result)

            except Exception as e:
                error_result = {
                    "model_path": str(model_path),
                    "status": "error",
                    "error": str(e),
                    "batch_processed": False
                }
                results.append(error_result)

                if not continue_on_error:
                    break

        return results

    def get_model_path(self, model_id: str) -> Path:
        """Resolve model ID to complete EMUSES training folder path.

        This is the core registry functionality - simple path lookup service.
        Following architectural guardrails: Registry as lookup service ONLY.

        Parameters
        ----------
        model_id : str
            ID of the registered model

        Returns
        -------
        Path
            Path to complete EMUSES folder containing all components

        Raises
        ------
        KeyError
            If model_id is not found in registry
        FileNotFoundError
            If model path no longer exists on disk
        """
        try:
            index = self._load_index()
            models = index.get("models", {})

            if model_id not in models:
                raise KeyError(f"Model not found: {model_id}")

            model_info = models[model_id]
            model_path_str = model_info.get("source_path")

            if not model_path_str:
                raise KeyError(f"Model path not found for ID: {model_id}")

            model_path = Path(model_path_str)

            # Verify path still exists
            if not model_path.exists():
                raise FileNotFoundError(f"Model path no longer exists: {model_path}")

            logger.info(f"Resolved model ID '{model_id}' to path: {model_path}")
            return model_path

        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading registry index: {e}")
            raise KeyError(f"Registry error for model {model_id}: {e}")

    # Removed complex batch policy method - replaced with simple batch processing
