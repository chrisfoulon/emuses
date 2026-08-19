# tools/model_io.py

"""
Comprehensive Model I/O Management System for EMUSES

This module provides a standardized approach to model persistence across all pipeline stages
with versioned artifacts, metadata tracking, and automatic fallback mechanisms.

Key Features:
- Versioned model artifacts with backward compatibility
- Comprehensive metadata tracking (timestamps, dependencies, configurations)
- Automatic fallback to compatible versions
- Type-safe model loading with validation
- Consistent error handling and logging
- Support for all model types used in EMUSES (UMAP, HDBSCAN, autoencoders, sklearn pipelines)
"""

import hashlib
import json
import logging
import shutil
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
# Import bcblib save_json for consistent serialization
from bcblib.tools.general_utils import save_json

logger = logging.getLogger(__name__)

# Feature augmentation model patterns for detection
FEATURE_MODEL_PATTERNS = {
    'pca': '*pca_model_*.joblib',
    'kpca': '*kpca_model_*.joblib',
    'autoencoder': '*autoencoder_model_*.joblib'
}


@dataclass
class OptunaTrial:
    """Optuna trial information."""

    trial_number: int
    value: float
    params: Dict[str, Any]
    user_attrs: Dict[str, Any] = None
    system_attrs: Dict[str, Any] = None
    state: str = ""
    datetime_start: str = ""
    datetime_complete: str = ""
    duration: float = 0.0

    def __post_init__(self):
        if self.user_attrs is None:
            self.user_attrs = {}
        if self.system_attrs is None:
            self.system_attrs = {}


@dataclass
class OptunaStudy:
    """Optuna study information."""

    study_name: str
    direction: str
    best_value: float
    best_trial: OptunaTrial
    n_trials: int
    optimization_time: float = 0.0
    sampler_name: str = ""
    pruner_name: str = ""


@dataclass
class ModelMetadata:
    """Enhanced metadata for model artifacts with Optuna support."""

    model_type: str
    version: str
    created_at: str
    emuses_version: str
    joblib_version: str
    dependencies: Dict[str, str]
    config_hash: str
    file_size: int
    description: str = ""
    tags: List[str] = None

    # Optuna-specific metadata
    optuna_study: OptunaStudy = None
    raw_optuna_params: Dict[str, Any] = None
    processed_params: Dict[str, Any] = None

    # Cross-validation info
    cv_score: float = None
    cv_scores: List[float] = None
    cv_folds: int = None
    fold_index: int = None

    # Target-specific info for prediction models
    target_id: int = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class ModelArtifact:
    """Container for model and its metadata."""

    model: Any
    metadata: ModelMetadata
    filepath: Path


@dataclass
class CompleteModelValidation:
    """Enhanced validation result for complete EMUSES models.

    This class provides comprehensive information about EMUSES model
    structure and validation, supporting complete model detection
    for both complete EMUSES models and individual component models.
    """
    is_complete_model: bool
    components_found: Dict[str, Path]
    configuration_hash: str
    content_hash: str
    missing_components: List[str]
    validation_errors: List[str]

    # Basic model information
    name: str
    version: str
    type: str
    description: str


class ModelIOManager:
    """
    Centralized model I/O management with versioning and metadata tracking.

    This manager handles:
    - Model saving with automatic versioning
    - Model loading with fallback mechanisms
    - Metadata persistence and validation
    - Backward compatibility checking
    """

    def __init__(self, base_path: Union[str, Path], version: str = "1.0.0"):
        """
        Initialize the Model I/O Manager.

        Args:
            base_path: Base directory for model storage
            version: EMUSES version for compatibility tracking
        """
        self.base_path = Path(base_path)
        self.version = version
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Create metadata directory
        self.metadata_path = self.base_path / ".metadata"
        self.metadata_path.mkdir(exist_ok=True)

    def save_model(
        self,
        model: Any,
        model_name: str,
        model_type: str,
        config: Optional[Dict] = None,
        description: str = "",
        tags: Optional[List[str]] = None,
        prefix: str = "",
        force_version: Optional[str] = None,
        # Optuna-specific parameters
        optuna_study: Optional[Any] = None,
        optuna_trial: Optional[Any] = None,
        optimization_time: Optional[float] = None,
        cv_score: Optional[float] = None,
        cv_scores: Optional[List[float]] = None,
        cv_folds: Optional[int] = None,
        fold_index: Optional[int] = None,
        # Target-specific parameter for prediction models
        target_id: Optional[int] = None,
    ) -> Path:
        """
        Save a model with comprehensive metadata including Optuna information.

        Args:
            model: The model object to save
            model_name: Base name for the model file
            model_type: Type of model (umap, hdbscan, autoencoder, sklearn_pipeline, etc.)
            config: Configuration dictionary used to train the model
            description: Human-readable description
            tags: List of tags for categorization
            prefix: Optional prefix for the filename
            force_version: Force a specific version (for testing/compatibility)
            optuna_study: Optuna study object with optimization results
            optuna_trial: Optuna trial object (best trial)
            cv_score: Cross-validation score for this model
            cv_scores: List of all CV fold scores
            cv_folds: Number of CV folds used
            fold_index: Index of the current fold (for CV models)
            target_id: Target ID for prediction models (enables standardized naming)

        Returns:
            Path to the saved model file
        """
        try:
            # Generate metadata
            metadata = self._create_metadata(
                model_type=model_type,
                config=config,
                description=description,
                tags=tags or [],
                force_version=force_version,
                optuna_study=optuna_study,
                optuna_trial=optuna_trial,
                optimization_time=optimization_time,
                cv_score=cv_score,
                cv_scores=cv_scores,
                cv_folds=cv_folds,
                fold_index=fold_index,
                target_id=target_id,
            )

            # Generate filename
            filename = self._generate_filename(
                model_name=model_name, metadata=metadata, prefix=prefix
            )

            filepath = self.base_path / filename

            # Save the model
            joblib.dump(model, filepath)

            # Update metadata with file size
            metadata.file_size = filepath.stat().st_size

            # Save metadata
            self._save_metadata(filepath, metadata)

            # Generate manifest for model integrity
            self._generate_manifest(filepath, metadata)

            logger.info(f"Successfully saved {model_type} model: {filepath}")
            if optuna_study:
                logger.info(
                    f"Optuna optimization: {len(optuna_study.trials)} trials, best value: {optuna_study.best_value:.4f}"
                )

            return filepath

        except Exception as e:
            logger.error(f"Failed to save model {model_name}: {e}")
            raise

    def load_model(
        self,
        model_name: str,
        model_type: Optional[str] = None,
        prefix: str = "",
        verify_integrity: bool = True,
    ) -> Optional[ModelArtifact]:
        """
        Load a model with simplified loading mechanism.

        Args:
            model_name: Base name of the model
            model_type: Expected model type for validation
            prefix: Optional prefix used when saving
            verify_integrity: Whether to verify model integrity using manifest

        Returns:
            ModelArtifact containing model and metadata, or None if loading failed
        """
        try:
            # Try exact match first
            artifact = self._try_load_exact_match(
                self.base_path, model_name, model_type, prefix
            )
            if artifact:
                # Verify integrity if requested
                if verify_integrity:
                    self._verify_model_integrity(artifact.filepath)
                return artifact

            # Try pattern matching
            artifact = self._try_load_with_pattern(
                self.base_path, model_name, model_type, prefix
            )
            if artifact:
                # Verify integrity if requested
                if verify_integrity:
                    self._verify_model_integrity(artifact.filepath)
                return artifact

            logger.warning(f"Could not find model: {model_name}")
            return None

        except ValueError as e:
            # Re-raise integrity verification errors
            if "integrity verification failed" in str(e):
                raise
            logger.error(f"Failed to load model {model_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            return None

    def list_models(
        self, model_type: Optional[str] = None, tags: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        List all available models with their metadata.

        Args:
            model_type: Filter by model type
            tags: Filter by tags (all must be present)

        Returns:
            List of model information dictionaries
        """
        models = []

        for joblib_file in self.base_path.glob("*.joblib"):
            try:
                metadata = self._load_metadata(joblib_file)
                if metadata:
                    # Apply filters
                    if model_type and metadata.model_type != model_type:
                        continue

                    if tags and not all(tag in metadata.tags for tag in tags):
                        continue

                    models.append(
                        {"filepath": joblib_file, "metadata": asdict(metadata)}
                    )
            except Exception as e:
                logger.warning(f"Failed to load metadata for {joblib_file}: {e}")

        return models

    def cleanup_old_versions(
        self, model_name: str, keep_latest: int = 3, prefix: str = ""
    ) -> List[Path]:
        """
        Clean up old versions of a model, keeping only the latest N versions.

        Args:
            model_name: Base name of the model
            keep_latest: Number of latest versions to keep
            prefix: Optional prefix used when saving

        Returns:
            List of paths that were deleted
        """
        deleted = []

        try:
            # Find all versions of this model
            pattern_base = f"{prefix}_{model_name}" if prefix else model_name
            pattern = f"{pattern_base}_v*.joblib"

            model_files = list(self.base_path.glob(pattern))

            # Sort by creation time (newest first)
            model_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            # Delete old versions
            for old_file in model_files[keep_latest:]:
                try:
                    # Delete metadata first
                    metadata_file = self.metadata_path / f"{old_file.stem}.json"
                    if metadata_file.exists():
                        metadata_file.unlink()

                    # Delete model file
                    old_file.unlink()
                    deleted.append(old_file)
                    logger.info(f"Deleted old model version: {old_file}")

                except Exception as e:
                    logger.warning(f"Failed to delete {old_file}: {e}")

        except Exception as e:
            logger.error(f"Failed to cleanup old versions for {model_name}: {e}")

        return deleted

    def validate_model(self, model_path: Path) -> CompleteModelValidation:
        """
        Validate model directory structure with complete model detection.

        Parameters
        ----------
        model_path : Path
            Path to model directory or file

        Returns
        -------
        CompleteModelValidation
            Complete validation result with detailed analysis

        Raises
        ------
        ValueError
            If model structure is invalid
        FileNotFoundError
            If required model files are missing
        """
        if not model_path.exists():
            raise FileNotFoundError(f"Model path does not exist: {model_path}")

        if model_path.is_file():
            model_path = model_path.parent

        # Perform complete model analysis
        return self._analyze_complete_model_structure(model_path)

    def install_model(self, source_path: Path, destination_path: Path,
                      name: Optional[str] = None, use_shared_storage: bool = True,
                      registry_base_path: Optional[Path] = None) -> str:
        """
        Install model from source to destination directory.

        Args:
            source_path: Path to source model directory/file
            destination_path: Base directory for model installation
            name: Optional custom name for the model
            use_shared_storage: Enable storage optimization with shared components
            registry_base_path: Registry base path for shared storage (defaults to destination_path parent)

        Returns:
            Unique model_id string for the installed model

        Raises:
            ValueError: If source model is invalid
            PermissionError: If destination is not writable
            FileExistsError: If model already exists and force=False
        """
        # Validate source model
        validation_result = self.validate_model(source_path)

        # Generate unique model ID
        model_name = name or validation_result.name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_id = f"{model_name}_{timestamp}_{uuid.uuid4().hex[:8]}"

        # Create destination directory
        destination_path.mkdir(parents=True, exist_ok=True)
        target_path = destination_path / model_id

        if target_path.exists():
            raise FileExistsError(f"Model already exists: {target_path}")

        # Determine registry base path for shared storage
        if use_shared_storage:
            if registry_base_path is None:
                # Default to parent of destination_path (assuming destination is 'models' subdirectory)
                registry_base_path = destination_path.parent

        # Copy model files with optional storage optimization
        try:
            if source_path.is_file():
                # Single file model
                target_path.mkdir()
                if use_shared_storage:
                    self._install_file_with_shared_storage(
                        source_path, target_path / source_path.name, registry_base_path
                    )
                else:
                    shutil.copy2(source_path, target_path / source_path.name)
            else:
                # Directory model
                if use_shared_storage:
                    self._install_directory_with_shared_storage(
                        source_path, target_path, registry_base_path
                    )
                else:
                    shutil.copytree(source_path, target_path)

            # Update manifest with installation metadata
            manifest_path = target_path / "model_manifest.json"

            # Create manifest from validation result
            base_manifest = {
                "name": validation_result.name,
                "version": validation_result.version,
                "type": validation_result.type,
                "description": validation_result.description
            }

            updated_manifest = {
                **base_manifest,
                "installed_at": datetime.now(timezone.utc).isoformat() + "Z",
                "model_id": model_id,
                "installation_path": str(target_path),
                "integrity_hash": self._calculate_directory_hash(target_path)
            }

            with open(manifest_path, 'w') as f:
                json.dump(updated_manifest, f, indent=2)

            logger.info(f"Model installed successfully: {model_id}")
            return model_id

        except (shutil.Error, OSError, IOError) as e:
            # Cleanup on failure
            if target_path.exists():
                shutil.rmtree(target_path, ignore_errors=True)
            raise ValueError(f"Model installation failed: {str(e)}")

    def _generate_manifest_from_directory(self, model_path: Path) -> Dict[str, Any]:
        """Generate manifest from model directory structure."""

        # Detect model type from files
        model_files = list(model_path.glob("*.pkl")) + list(model_path.glob("*.joblib"))
        if not model_files:
            raise ValueError(f"No model files found in {model_path}")

        # Use the folder name as the model name (more descriptive than hardcoded defaults)
        folder_name = model_path.name
        
        # Basic manifest structure
        return {
            "name": folder_name,
            "version": "1.0.0",
            "type": "unknown",  # Would need more sophisticated detection
            "description": f"Model from {folder_name}",
            "created_at": datetime.now(timezone.utc).isoformat() + "Z"
        }

    def _calculate_directory_hash(self, directory: Path) -> str:
        """Calculate SHA-256 hash of directory contents."""
        hasher = hashlib.sha256()

        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file():
                with open(file_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hasher.update(chunk)
                hasher.update(str(file_path.relative_to(directory)).encode())

        return hasher.hexdigest()

    def _analyze_complete_model_structure(self, model_path: Path) -> CompleteModelValidation:
        """
        Validate EMUSES folder structure following architectural guardrails.

        EMUSES models are complete training folder units - this method validates
        the folder contains necessary EMUSES structure without treating components
        as separable entities.

        Parameters
        ----------
        model_path : Path
            Path to EMUSES model directory to validate

        Returns
        -------
        CompleteModelValidation
            Validation result for complete EMUSES folder
        """
        validation_errors = []

        # Load manifest for metadata - EMUSES folders have manifests
        try:
            manifest = self._load_or_generate_manifest(model_path)
        except ValueError as e:
            validation_errors.append(f"Invalid EMUSES folder: {str(e)}")
            manifest = {
                "name": model_path.name,
                "version": "1.0.0",
                "model_type": "unknown",
                "description": f"Invalid EMUSES folder: {model_path.name}"
            }

        # Validate this is a complete EMUSES training folder
        # EMUSES folders contain: manifest, model files, embeddings, and target directories
        is_complete = self._validate_emuses_folder_structure(model_path)

        if not is_complete:
            validation_errors.append("Not a complete EMUSES training folder")

        # Calculate configuration hash from manifest (EMUSES-native metadata)
        config_hash = self._extract_configuration_hash(manifest)

        # Calculate content hash from entire folder (treated as atomic unit)
        content_hash = self._calculate_folder_content_hash(model_path)

        # Detect feature augmentation models (optional)
        feature_models = self._detect_feature_models(model_path)

        # Override metadata for complete EMUSES models to prevent component metadata confusion
        if is_complete:
            model_type = "emuses_model"
            # Generate EMUSES-specific manifest metadata
            emuses_description = self._generate_emuses_model_description(model_path, feature_models)
            manifest_override = {
                "name": manifest.get("name", model_path.name),
                "version": manifest.get("version", "1.0.0"),
                "model_type": model_type,
                "description": emuses_description,
                "created_at": manifest.get("created_at", datetime.now(timezone.utc).isoformat() + "Z")
            }
            manifest.update(manifest_override)
        else:
            model_type = manifest.get("model_type", "unknown")

        # Build components found dictionary
        components_found = {}
        if is_complete:
            components_found["emuses_folder"] = model_path
            # Add feature models to components if found
            for feature_type, model_files in feature_models.items():
                if model_files:  # Only include if files were found
                    components_found[f"{feature_type}_models"] = model_files

        return CompleteModelValidation(
            is_complete_model=is_complete,
            components_found=components_found,
            configuration_hash=config_hash,
            content_hash=content_hash,
            missing_components=[] if is_complete else ["emuses_structure"],
            validation_errors=validation_errors,
            name=manifest.get("name", model_path.name),
            version=manifest.get("version", "1.0.0"),
            type=model_type,
            description=manifest.get("description", "")
        )

    def _load_or_generate_manifest(self, model_path: Path) -> Dict[str, Any]:
        """Load existing manifest or generate one from directory structure."""
        # Try standard manifest locations
        manifest_candidates = [
            model_path / "manifest.json",
            model_path / "model_manifest.json"
        ]

        for manifest_path in manifest_candidates:
            if manifest_path.exists():
                try:
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                    logger.debug(f"Loaded manifest from {manifest_path}")
                    return manifest
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Failed to read manifest {manifest_path}: {e}")
                    continue

        # Generate manifest from directory structure
        logger.debug(f"Generating manifest for {model_path}")
        return self._generate_manifest_from_directory(model_path)
    
    def _generate_emuses_model_description(self, model_path: Path, feature_models: Dict[str, List[Path]]) -> str:
        """
        Generate description for complete EMUSES models using path-based heuristics.
        
        Args:
            model_path: Path to EMUSES model directory
            feature_models: Dictionary of detected feature augmentation models
            
        Returns:
            Description derived from directory name and structure
        """
        # Use directory name as base description
        base_name = model_path.name
        description_parts = [f"Complete EMUSES analysis model: {base_name}"]
        
        # Analyze actual model components found
        components = []
        
        # Check for core EMUSES components
        if (model_path / "umap_model.joblib").exists():
            components.append("UMAP")
        if (model_path / "hdbscan_model.joblib").exists():
            components.append("HDBSCAN")
            
        # Count prediction targets
        target_dirs = [d for d in model_path.iterdir() if d.is_dir() and d.name.startswith("target_")]
        if target_dirs:
            components.append(f"{len(target_dirs)} prediction targets")
            
        # Add feature augmentation if detected
        for feature_type, models in feature_models.items():
            if models:
                components.append(f"{feature_type.upper()}")
                
        if components:
            description_parts.append(f"Contains: {', '.join(components)}")
            
        return ". ".join(description_parts)

    def _resolve_artifact_prefix(self, model_path: Path) -> str:
        """
        Recover the run prefix that training applied to output file names.

        A run started with ``--prefix myrun`` writes ``myrun_embeddings.npy`` and
        ``myrun_input_matrix.npy``; a run without one writes ``embeddings.npy`` and
        ``input_matrix.npy`` (see ``UMAP_utils.py``, ``train_and_save_umap_optim``).
        Assuming the unprefixed names made every prefixed model fail validation and so
        impossible to register.

        The prefix is not recorded in the manifest, but the pipeline saves its arguments
        to ``log/arguments_<timestamp>.json``. Globbing for ``*embeddings.npy`` instead
        would be wrong: ``test_embeddings.npy``, ``best_embeddings.npy`` and
        ``unlabeled_embeddings.npy`` are all real EMUSES outputs and none of them is the
        training embedding matrix.

        Parameters
        ----------
        model_path : Path
            Path to the model folder

        Returns
        -------
        str
            The prefix without its trailing separator, or "" if the run used none or
            the arguments log is missing or unreadable.
        """
        arg_files = sorted(model_path.glob("log/arguments_*.json"))
        if not arg_files:
            return ""

        try:
            with open(arg_files[-1], "r") as f:
                saved_args = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.debug(f"Could not read training arguments from {arg_files[-1]}: {e}")
            return ""

        prefix = saved_args.get("prefix") or ""
        return prefix.strip().rstrip("_")

    def _validate_emuses_folder_structure(self, model_path: Path) -> bool:
        """
        Validate that folder contains complete EMUSES training output structure.

        EMUSES training folders contain specific files and directories that
        indicate a complete training run. This validates the folder as an
        atomic unit without separating components.

        Parameters
        ----------
        model_path : Path
            Path to folder to validate

        Returns
        -------
        bool
            True if folder contains complete EMUSES structure
        """
        # EMUSES folders must have a root manifest
        manifest_files = list(model_path.glob("*manifest*.json"))
        if not manifest_files:
            return False

        # EMUSES folders contain model files (.joblib files)
        model_files = list(model_path.glob("*.joblib"))
        if len(model_files) < 2:  # At least UMAP and HDBSCAN
            return False

        # EMUSES folders contain embeddings and training data. Training applies the run
        # prefix to these names, so resolve it rather than assuming the default.
        prefix = self._resolve_artifact_prefix(model_path)
        for stem in ("embeddings.npy", "input_matrix.npy"):
            candidates = [stem]
            if prefix:
                candidates.insert(0, f"{prefix}_{stem}")
            if not any((model_path / name).exists() for name in candidates):
                return False

        # EMUSES folders contain target prediction directories
        target_dirs = list(model_path.glob("target_*"))
        if not target_dirs:
            return False

        # Each target directory should have its own manifest and models
        for target_dir in target_dirs:
            target_manifest = target_dir / "model_manifest.json"
            if not target_manifest.exists():
                return False

            target_models = list(target_dir.glob("*.joblib"))
            if not target_models:
                return False

        return True

    def _detect_feature_models(self, model_path: Path) -> Dict[str, List[Path]]:
        """
        Detect feature augmentation models in EMUSES folder.

        Feature models are optional components that may be present for
        feature preprocessing (PCA, kPCA, autoencoders). This method
        identifies which feature models are available.

        Parameters
        ----------
        model_path : Path
            Path to EMUSES folder to search

        Returns
        -------
        Dict[str, List[Path]]
            Dictionary mapping feature model types to found model files

        Example
        -------
        {
            'pca': [Path('/models/pca_model_v1_0_0.joblib')],
            'autoencoder': [Path('/models/autoencoder_model_v1_0_0.joblib')],
            'kpca': []  # None found
        }
        """
        detected_models = {}

        for model_type, pattern in FEATURE_MODEL_PATTERNS.items():
            model_files = list(model_path.glob(pattern))
            detected_models[model_type] = model_files

            if model_files:
                logger.info(f"Found {len(model_files)} {model_type} feature model(s) in {model_path.name}")
                for model_file in model_files:
                    logger.debug(f"  - {model_file.name}")

        return detected_models

    def _extract_configuration_hash(self, manifest: Dict[str, Any]) -> str:
        """Extract configuration hash from manifest metadata."""
        # Look for pipeline configuration in manifest
        config_sources = [
            manifest.get("pipeline_config", {}),
            manifest.get("config", {}),
            manifest.get("training_config", {}),
            manifest.get("parameters", {})
        ]

        # Combine all configuration sources
        combined_config = {}
        for config in config_sources:
            if isinstance(config, dict):
                combined_config.update(config)

        # Generate hash from configuration
        if combined_config:
            config_str = json.dumps(combined_config, sort_keys=True, default=str)
            return hashlib.sha256(config_str.encode()).hexdigest()[:16]

        # Fallback: generate hash from manifest metadata
        stable_fields = {
            "name": manifest.get("name", ""),
            "version": manifest.get("version", ""),
            "model_type": manifest.get("model_type", "")
        }
        config_str = json.dumps(stable_fields, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]

    def _calculate_folder_content_hash(self, model_path: Path) -> str:
        """
        Calculate filesystem-independent content hash for complete EMUSES folder.

        Uses Git-style content-addressable storage approach for cross-platform stability.
        Ignores file paths and filesystem artifacts to ensure consistent hashes
        when models are transferred between machines or operating systems.

        Treats the entire EMUSES folder as an atomic unit following architectural
        guardrails - no component separation.

        Parameters
        ----------
        model_path : Path
            Path to complete EMUSES model directory.

        Returns
        -------
        str
            16-character hex hash string that remains consistent across
            filesystem operations, transfers, and different operating systems.
        """
        hasher = hashlib.sha256()

        # Hash the entire folder contents as atomic unit
        self._hash_directory_content_stable(hasher, model_path)

        return hasher.hexdigest()[:16]

    def _hash_file_content(self, hasher, file_path: Path) -> None:
        """
        Hash file contents without path information.

        Parameters
        ----------
        hasher : hashlib object
            Hash object to update with file content.
        file_path : Path
            Path to the file to hash.
        """
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)

    def _hash_directory_content_stable(self, hasher, directory_path: Path) -> None:
        """
        Hash directory contents with filesystem independence.

        Only hashes actual file contents, ignoring paths and filesystem artifacts.
        Ensures consistent hashes across different operating systems and transfers.

        Parameters
        ----------
        hasher : hashlib object
            Hash object to update with directory content.
        directory_path : Path
            Path to the directory to hash.
        """
        for file_path in sorted(directory_path.rglob("*")):
            if file_path.is_file() and not self._is_filesystem_artifact(file_path):
                # Hash only file contents, no path information
                self._hash_file_content(hasher, file_path)

    def _is_filesystem_artifact(self, file_path: Path) -> bool:
        """
        Identify filesystem artifacts to exclude from hashing.

        These files are created by operating systems or applications and should
        not affect model content hashes as they vary across platforms.

        Parameters
        ----------
        file_path : Path
            Path to check for filesystem artifacts.

        Returns
        -------
        bool
            True if the file is a filesystem artifact that should be ignored.
        """
        name = file_path.name.lower()
        return (
            name.startswith('.ds_store') or      # macOS Finder metadata
            name.startswith('._') or            # macOS resource forks
            name == 'thumbs.db' or              # Windows thumbnail cache
            name == 'desktop.ini' or           # Windows folder settings
            name.startswith('.trash') or        # Linux trash metadata
            name == '.directory' or            # KDE folder metadata
            name.endswith('.tmp') or           # Temporary files
            name.startswith('~') or            # Backup files
            name.startswith('.git')            # Git repository files
        )

    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate SHA256 hash for a single file.

        Used for identifying identical components across models
        for storage optimization purposes.

        Parameters
        ----------
        file_path : Path
            Path to the file to hash.

        Returns
        -------
        str
            SHA256 hash of the file content as hexadecimal string.
        """
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _calculate_content_hash(self, model_path: Path, components: Dict[str, Path]) -> str:
        """
        Calculate content hash for EMUSES model with component awareness.
        
        This method provides component-aware hashing for model registry duplicate 
        detection and hash indexing. It builds on the existing folder hashing 
        infrastructure while supporting the test interface expectations.
        
        Parameters
        ----------
        model_path : Path
            Path to complete EMUSES model directory.
        components : Dict[str, Path]
            Dictionary mapping component names to their file paths.
            Used for component-aware analysis.
        
        Returns
        -------
        str
            SHA256 hex digest of the model content.
            
        Notes
        -----
        For now, uses the folder-based approach for consistency with existing
        hash calculation infrastructure. Component-specific hashing could be
        added later if needed for more granular duplicate detection.
        """
        # For complete EMUSES models, use the existing folder hash approach
        # This ensures consistency with the current hash indexing system
        return self._calculate_folder_content_hash(model_path)

    def _install_file_with_shared_storage(self, source_file: Path, target_file: Path,
                                          registry_path: Path) -> None:
        """
        Install a single file using shared storage optimization.

        If an identical file already exists in shared storage, creates a symlink.
        Otherwise, stores the file in shared storage and creates a symlink.

        Parameters
        ----------
        source_file : Path
            Source file to install.
        target_file : Path
            Target location for the file.
        registry_path : Path
            Registry base path for shared storage.
        """
        # Calculate file hash
        file_hash = self._calculate_file_hash(source_file)

        # Set up shared storage structure
        shared_storage_path = registry_path / "shared_components"
        shared_storage_path.mkdir(exist_ok=True)

        # Use first 2 chars of hash for directory sharding (Git-style)
        shard_dir = shared_storage_path / file_hash[:2]
        shard_dir.mkdir(exist_ok=True)

        # Full hash directory
        hash_dir = shard_dir / file_hash
        shared_file_path = hash_dir / source_file.name

        if not shared_file_path.exists():
            # First time seeing this content - store it
            hash_dir.mkdir(exist_ok=True)
            shutil.copy2(source_file, shared_file_path)
            logger.debug(f"Stored new shared component: {file_hash[:8]}")
        else:
            logger.debug(f"Reusing shared component: {file_hash[:8]}")

        # Create symlink from target to shared storage
        target_file.parent.mkdir(parents=True, exist_ok=True)
        if target_file.exists():
            target_file.unlink()

        try:
            target_file.symlink_to(shared_file_path)
        except OSError:
            # Fallback to hard copy if symlinks aren't supported
            logger.warning("Symlinks not supported, falling back to copy")
            shutil.copy2(shared_file_path, target_file)

    def _install_directory_with_shared_storage(self, source_dir: Path, target_dir: Path,
                                               registry_path: Path) -> None:
        """
        Install a directory using shared storage optimization.

        Recursively processes directory, optimizing storage for individual files
        while preserving directory structure.

        Parameters
        ----------
        source_dir : Path
            Source directory to install.
        target_dir : Path
            Target directory location.
        registry_path : Path
            Registry base path for shared storage.
        """
        target_dir.mkdir(parents=True, exist_ok=True)

        for item in source_dir.iterdir():
            if item.is_file() and not self._is_filesystem_artifact(item):
                # Install file with shared storage
                target_file = target_dir / item.name
                self._install_file_with_shared_storage(item, target_file, registry_path)
            elif item.is_dir():
                # Recursively install subdirectory
                self._install_directory_with_shared_storage(
                    item, target_dir / item.name, registry_path
                )

    def _create_metadata(
        self,
        model_type: str,
        config: Optional[Dict],
        description: str,
        tags: List[str],
        force_version: Optional[str],
        optuna_study: Optional[Any] = None,
        optuna_trial: Optional[Any] = None,
        optimization_time: Optional[float] = None,
        cv_score: Optional[float] = None,
        cv_scores: Optional[List[float]] = None,
        cv_folds: Optional[int] = None,
        fold_index: Optional[int] = None,
        target_id: Optional[int] = None,
    ) -> ModelMetadata:
        """Create metadata for a model with Optuna support."""
        # Get dependency versions
        dependencies = self._get_dependencies()

        # Generate config hash
        config_hash = self._hash_config(config) if config else "no_config"

        # Use forced version or current version
        version = force_version or self.version

        # Process Optuna information
        optuna_study_metadata = None
        if optuna_study:
            optuna_study_metadata = self._extract_optuna_study_metadata(
                optuna_study, optuna_trial, optimization_time
            )

        return ModelMetadata(
            model_type=model_type,
            version=version,
            created_at=datetime.now().isoformat(),
            emuses_version=self.version,
            joblib_version=joblib.__version__,
            dependencies=dependencies,
            config_hash=config_hash,
            file_size=0,  # Will be updated after saving
            description=description,
            tags=tags,
            # Optuna metadata
            optuna_study=optuna_study_metadata,
            raw_optuna_params=optuna_trial.params if optuna_trial else None,
            processed_params=config,
            # CV metadata
            cv_score=cv_score,
            cv_scores=cv_scores,
            cv_folds=cv_folds,
            fold_index=fold_index,
            # Target metadata
            target_id=target_id,
        )

    def _extract_optuna_study_metadata(self, study: Any, trial: Any, optimization_time: Optional[float] = None) -> OptunaStudy:
        """Extract metadata from Optuna study and trial objects."""
        try:
            # Extract best trial information
            best_trial_data = OptunaTrial(
                trial_number=trial.number if trial else study.best_trial.number,
                value=trial.value if trial else study.best_trial.value,
                params=trial.params if trial else study.best_trial.params,
                user_attrs=(
                    getattr(trial, "user_attrs", {})
                    if trial
                    else getattr(study.best_trial, "user_attrs", {})
                ),
                system_attrs=(
                    getattr(trial, "system_attrs", {})
                    if trial
                    else getattr(study.best_trial, "system_attrs", {})
                ),
                state=(
                    str(trial.state)
                    if trial and hasattr(trial, "state")
                    else str(study.best_trial.state)
                ),
                datetime_start=(
                    str(trial.datetime_start)
                    if trial and hasattr(trial, "datetime_start")
                    else str(getattr(study.best_trial, "datetime_start", ""))
                ),
                datetime_complete=(
                    str(trial.datetime_complete)
                    if trial and hasattr(trial, "datetime_complete")
                    else str(getattr(study.best_trial, "datetime_complete", ""))
                ),
                duration=(
                    getattr(trial, "duration", 0.0)
                    if trial
                    else getattr(study.best_trial, "duration", 0.0)
                ),
            )

            # Extract study information
            study_metadata = OptunaStudy(
                study_name=study.study_name,
                direction=str(study.direction),
                best_value=study.best_value,
                best_trial=best_trial_data,
                n_trials=len(study.trials),
                optimization_time=optimization_time or 0.0,
                sampler_name=(
                    str(type(study.sampler).__name__)
                    if hasattr(study, "sampler")
                    else ""
                ),
                pruner_name=(
                    str(type(study.pruner).__name__) if hasattr(study, "pruner") else ""
                ),
            )

            return study_metadata

        except Exception as e:
            logger.warning(f"Failed to extract Optuna metadata: {e}")
            # Return minimal metadata
            return OptunaStudy(
                study_name=getattr(study, "study_name", "unknown"),
                direction=str(getattr(study, "direction", "minimize")),
                best_value=getattr(study, "best_value", 0.0),
                best_trial=OptunaTrial(
                    trial_number=0,
                    value=0.0,
                    params={},
                ),
                n_trials=len(getattr(study, "trials", [])),
            )

    def _generate_filename(
        self, model_name: str, metadata: ModelMetadata, prefix: str
    ) -> str:
        """Generate a versioned filename for the model with standardized naming."""
        # Clean version string for filename
        version_str = metadata.version.replace(".", "_")
        joblib_version_str = metadata.joblib_version.replace(".", "_")

        # Build filename components
        components = []
        if prefix:
            components.append(prefix)

        # Check if this is a prediction model with target_id and fold_index
        if (
            metadata.target_id is not None
            and metadata.fold_index is not None
            and "prediction" in model_name.lower()
        ):
            # Use standardized prediction model naming
            components.extend(
                [
                    "best_prediction_model",
                    f"target_{metadata.target_id}",
                    f"fold_{metadata.fold_index}",
                    f"v{version_str}",
                    f"joblib{joblib_version_str}",
                ]
            )
        else:
            # Use traditional naming for backward compatibility
            components.extend(
                [model_name, f"v{version_str}", f"joblib{joblib_version_str}"]
            )

        return "_".join(components) + ".joblib"

    def _save_metadata(self, model_filepath: Path, metadata: ModelMetadata) -> None:
        """Save metadata to a JSON file with custom serialization for complex objects."""
        metadata_file = self.metadata_path / f"{model_filepath.stem}.json"

        # Use bcblib save_json for consistent serialization and numpy array support
        save_json(metadata_file, asdict(metadata))

    def _load_metadata(self, model_filepath: Path) -> Optional[ModelMetadata]:
        """Load metadata from a JSON file with support for complex nested structures."""
        metadata_file = self.metadata_path / f"{model_filepath.stem}.json"

        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, "r") as f:
                data = json.load(f)

            # Handle nested Optuna structures
            if data.get("optuna_study"):
                study_data = data["optuna_study"]
                if study_data.get("best_trial"):
                    trial_data = study_data["best_trial"]
                    study_data["best_trial"] = OptunaTrial(**trial_data)
                data["optuna_study"] = OptunaStudy(**study_data)

            return ModelMetadata(**data)
        except Exception as e:
            logger.warning(f"Failed to load metadata from {metadata_file}: {e}")
            # Try to load with backward compatibility (old format)
            try:
                with open(metadata_file, "r") as f:
                    data = json.load(f)
                # Remove any new fields that don't exist in old format
                old_fields = {
                    "model_type",
                    "version",
                    "created_at",
                    "emuses_version",
                    "joblib_version",
                    "dependencies",
                    "config_hash",
                    "file_size",
                    "description",
                    "tags",
                }
                filtered_data = {k: v for k, v in data.items() if k in old_fields}
                return ModelMetadata(**filtered_data)
            except Exception as e2:
                logger.warning(
                    f"Failed to load metadata with backward compatibility: {e2}"
                )
                return None

    def _try_load_exact_match(
        self, search_path: Path, model_name: str, model_type: Optional[str], prefix: str
    ) -> Optional[ModelArtifact]:
        """Try to load a model with exact version match."""
        current_joblib = joblib.__version__.replace(".", "_")
        version_str = self.version.replace(".", "_")

        # Try exact match with current version
        components = []
        if prefix:
            components.append(prefix)
        components.extend([model_name, f"v{version_str}", f"joblib{current_joblib}"])

        filename = "_".join(components) + ".joblib"
        filepath = search_path / filename

        if filepath.exists():
            return self._load_model_file(filepath, model_type)

        return None

    def _try_load_with_pattern(
        self, search_path: Path, model_name: str, model_type: Optional[str], prefix: str
    ) -> Optional[ModelArtifact]:
        """Try to load a model using pattern matching."""
        # Build pattern for this model
        pattern_base = f"{prefix}_{model_name}" if prefix else model_name
        pattern = f"{pattern_base}_v*.joblib"

        # Find all matching files
        matching_files = list(search_path.glob(pattern))

        if not matching_files:
            return None

        # Sort by modification time (newest first)
        matching_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Try loading the newest file
        for filepath in matching_files:
            artifact = self._load_model_file(filepath, model_type)
            if artifact:
                logger.info(f"Loaded model using pattern matching: {filepath}")
                return artifact

        return None

    def _try_load_with_fallback(
        self,
        search_path: Path,
        model_name: str,
        model_type: Optional[str],
        prefix: str,
        max_attempts: int,
        allow_version_mismatch: bool,
    ) -> Optional[ModelArtifact]:
        """Try to load a model with version fallback."""
        # Build pattern for this model
        pattern_base = f"{prefix}_{model_name}" if prefix else model_name
        pattern = f"{pattern_base}_v*.joblib"

        # Find all matching files
        matching_files = list(search_path.glob(pattern))

        if not matching_files:
            return None

        # Sort by modification time (newest first)
        matching_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Try loading each file
        for attempt, filepath in enumerate(matching_files[:max_attempts]):
            try:
                artifact = self._load_model_file(filepath, model_type)
                if artifact:
                    # Check version compatibility if required
                    if (
                        not allow_version_mismatch
                        and artifact.metadata.version != self.version
                    ):
                        logger.warning(
                            f"Version mismatch for {filepath}: "
                            f"expected {self.version}, got {artifact.metadata.version}"
                        )
                        continue

                    if attempt > 0:
                        logger.info(
                            f"Loaded model from fallback version: {filepath} "
                            f"(attempt {attempt + 1})"
                        )

                    return artifact

            except Exception as e:
                logger.warning(
                    f"Failed to load {filepath} (attempt {attempt + 1}): {e}"
                )

        return None

    def _try_legacy_loading(
        self, model_name: str, prefix: str, search_paths: List[Path]
    ) -> Optional[ModelArtifact]:
        """Try to load legacy models without versioning."""
        # Try legacy patterns
        legacy_patterns = [
            f"{prefix}_{model_name}.joblib" if prefix else f"{model_name}.joblib",
            f"{model_name}_joblib*.joblib",
            f"{prefix}_{model_name}_joblib*.joblib" if prefix else None,
        ]

        # Remove None patterns
        legacy_patterns = [p for p in legacy_patterns if p is not None]

        for search_path in search_paths:
            for pattern in legacy_patterns:
                for filepath in search_path.glob(pattern):
                    try:
                        # Load without metadata (legacy mode)
                        model = joblib.load(filepath)

                        # Create minimal metadata
                        metadata = ModelMetadata(
                            model_type="unknown",
                            version="legacy",
                            created_at=datetime.fromtimestamp(
                                filepath.stat().st_mtime
                            ).isoformat(),
                            emuses_version="unknown",
                            joblib_version="unknown",
                            dependencies={},
                            config_hash="unknown",
                            file_size=filepath.stat().st_size,
                            description="Legacy model loaded without metadata",
                            tags=["legacy"],
                        )

                        logger.info(f"Loaded legacy model: {filepath}")
                        return ModelArtifact(
                            model=model, metadata=metadata, filepath=filepath
                        )

                    except Exception as e:
                        logger.debug(f"Failed to load legacy model {filepath}: {e}")

        return None

    def _load_model_file(
        self, filepath: Path, expected_type: Optional[str]
    ) -> Optional[ModelArtifact]:
        """Load a model file with metadata validation."""
        try:
            # Load the model
            model = joblib.load(filepath)

            # Load metadata
            metadata = self._load_metadata(filepath)

            if metadata is None:
                logger.warning(
                    f"No metadata found for {filepath}, creating minimal metadata"
                )
                metadata = ModelMetadata(
                    model_type="unknown",
                    version="unknown",
                    created_at=datetime.fromtimestamp(
                        filepath.stat().st_mtime
                    ).isoformat(),
                    emuses_version="unknown",
                    joblib_version="unknown",
                    dependencies={},
                    config_hash="unknown",
                    file_size=filepath.stat().st_size,
                    description="Model loaded without metadata",
                )

            # Validate model type if expected
            if expected_type and metadata.model_type != expected_type:
                logger.warning(
                    f"Model type mismatch for {filepath}: "
                    f"expected {expected_type}, got {metadata.model_type}"
                )

            return ModelArtifact(model=model, metadata=metadata, filepath=filepath)

        except Exception as e:
            logger.error(f"Failed to load model from {filepath}: {e}")
            return None

    def _get_dependencies(self) -> Dict[str, str]:
        """Get versions of key dependencies."""
        dependencies = {}

        # Key packages to track
        packages = [
            "numpy",
            "scipy",
            "sklearn",
            "umap-learn",
            "hdbscan",
            "pandas",
            "matplotlib",
            "seaborn",
            "torch",
            "tensorflow",
        ]

        for package in packages:
            try:
                if package in sys.modules:
                    module = sys.modules[package]
                    if hasattr(module, "__version__"):
                        dependencies[package] = module.__version__
            except Exception:
                pass  # Package not available or no version info

        return dependencies

    def _hash_config(self, config: Dict) -> str:
        """Generate a hash of the configuration for tracking."""
        if not config:
            return "no_config"

        # Convert config to a stable string representation
        config_str = json.dumps(config, sort_keys=True, default=str)
        return hashlib.md5(config_str.encode()).hexdigest()[:16]

    # Utility methods for standardized naming
    @staticmethod
    def get_standardized_prediction_model_name(target_id: int, fold: int) -> str:
        """Generate standardized prediction model name for internal use."""
        return f"best_prediction_model_target_{target_id}_fold_{fold}"

    @staticmethod
    def extract_target_and_fold_from_filename(
        filename: str,
    ) -> Tuple[Optional[int], Optional[int]]:
        """Extract target_id and fold from standardized filename."""
        try:
            parts = filename.replace(".joblib", "").split("_")
            target_id = None
            fold = None

            # Look for target_X pattern
            for i, part in enumerate(parts):
                if part == "target" and i + 1 < len(parts):
                    target_id = int(parts[i + 1])
                elif part == "fold" and i + 1 < len(parts):
                    fold = int(parts[i + 1])

            return target_id, fold
        except (ValueError, IndexError):
            return None, None

    def load_all_cv_fold_models(
        self, target_id: int, expected_folds: int = 5
    ) -> List[ModelArtifact]:
        """
        Load all CV fold models for a specific target.

        Args:
            target_id: Target ID to load models for
            expected_folds: Expected number of folds (default 5)

        Returns:
            List of ModelArtifact objects, sorted by fold index
        """
        models = []

        for fold in range(expected_folds):
            model_name = self.get_standardized_prediction_model_name(target_id, fold)
            artifact = self.load_model(model_name, "sklearn_pipeline")

            if artifact:
                models.append(artifact)
                logger.debug(f"Loaded model for target {target_id}, fold {fold}")
            else:
                logger.warning(
                    f"Could not load model for target {target_id}, fold {fold}"
                )

        # Sort by fold index
        models.sort(key=lambda x: x.metadata.fold_index or 0)
        return models

    # Manifest generation and verification methods

    def _generate_manifest(self, model_filepath: Path, metadata: ModelMetadata) -> None:
        """
        Generate model manifest compatible with validate_model() method.

        Creates a manifest with top-level keys that can be validated by the
        install_model workflow.

        Args:
            model_filepath: Path to the saved model file
            metadata: Model metadata
        """
        try:
            manifest_path = self.base_path / "model_manifest.json"

            # Extract base name for the model
            base_name = model_filepath.stem.split('_v')[0]

            # Create new standardized manifest format
            manifest = {
                "name": base_name,
                "version": self._get_next_version(base_name),
                "model_type": metadata.model_type,
                "description": metadata.description,
                "created_at": metadata.created_at,
                "emuses_version": metadata.emuses_version,

                # File integrity information
                "file_integrity": {
                    model_filepath.name: {
                        "size": metadata.file_size,
                        "sha256": self._calculate_file_hash(model_filepath),
                        "modified": metadata.created_at
                    }
                },

                # Training context
                "training_context": {
                    "config_hash": metadata.config_hash,
                    "dependencies": metadata.dependencies,
                    "random_seeds": {}  # Will be enhanced with actual seeds
                },

                # Compatibility information
                "compatibility": {
                    "min_emuses_version": "2.0.0",
                    "python_version": f"{sys.version_info.major}.{sys.version_info.minor}+",
                    "required_packages": list(metadata.dependencies.keys())
                }
            }

            # If there's an existing manifest, preserve any additional file integrity info
            if manifest_path.exists():
                try:
                    with open(manifest_path, 'r') as f:
                        existing_manifest = json.load(f)

                    # Preserve file integrity for other models in the directory
                    if "file_integrity" in existing_manifest:
                        # Keep existing entries, but update current model
                        existing_integrity = existing_manifest["file_integrity"]
                        existing_integrity[model_filepath.name] = manifest["file_integrity"][model_filepath.name]
                        manifest["file_integrity"] = existing_integrity

                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Could not load existing manifest, creating new one: {e}")

            # Save updated manifest
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2, sort_keys=True)

            logger.debug(f"Generated standardized manifest for model: {model_filepath.name}")

        except Exception as e:
            logger.warning(f"Failed to generate manifest: {e}")
            # Don't fail the save operation if manifest generation fails

    def _get_next_version(self, model_name: str) -> str:
        """Get next version number for a model."""
        manifest_path = self.base_path / "model_manifest.json"

        if not manifest_path.exists():
            return "1.0.0"

        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            current_version = manifest.get("model_info", {}).get("version", "1.0.0")
            major, minor, patch = map(int, current_version.split('.'))

            # Increment patch version
            return f"{major}.{minor}.{patch + 1}"

        except (json.JSONDecodeError, ValueError, KeyError):
            return "1.0.0"

    def _verify_model_integrity(self, model_filepath: Path) -> None:
        """
        Verify model integrity using manifest.

        Args:
            model_filepath: Path to model file to verify

        Raises:
            ValueError: If integrity verification fails
        """
        manifest_path = self.base_path / "model_manifest.json"

        if not manifest_path.exists():
            logger.warning(f"No manifest found for {model_filepath.name}, skipping integrity check")
            return

        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            file_integrity = manifest.get("file_integrity", {})

            if model_filepath.name not in file_integrity:
                logger.warning(f"No integrity information for {model_filepath.name}")
                return

            expected_hash = file_integrity[model_filepath.name]["sha256"]
            actual_hash = self._calculate_file_hash(model_filepath)

            if actual_hash != expected_hash:
                raise ValueError(
                    f"Model integrity verification failed for {model_filepath.name}: "
                    f"expected {expected_hash}, got {actual_hash}"
                )

            logger.debug(f"Integrity verified for {model_filepath.name}")

        except json.JSONDecodeError:
            logger.warning("Corrupted manifest file, skipping integrity check")
        except Exception as e:
            logger.error(f"Integrity verification failed: {e}")
            raise

    def get_manifest_info(self, model_name: str) -> Optional[Dict]:
        """
        Get manifest information for a model without loading it.

        Args:
            model_name: Name of the model

        Returns:
            Manifest dictionary or None if not found
        """
        manifest_path = self.base_path / "model_manifest.json"

        if not manifest_path.exists():
            return None

        try:
            with open(manifest_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    def verify_model_integrity(self, model_name: str) -> bool:
        """
        Standalone function to verify model integrity.

        Args:
            model_name: Name of the model to verify

        Returns:
            True if integrity check passes, False otherwise
        """
        try:
            # Find the model file
            if model_name == "*":
                # Use all .joblib files
                matches = list(self.base_path.glob("*.joblib"))
            else:
                pattern = f"{model_name}*.joblib"
                matches = list(self.base_path.glob(pattern))

            if not matches:
                logger.warning(f"No model file found matching pattern: {pattern}")
                return False

            # Use the first match (most recent by default)
            model_filepath = matches[0]
            self._verify_model_integrity(model_filepath)
            return True

        except Exception as e:
            logger.error(f"Integrity verification failed for {model_name}: {e}")
            return False


# Convenience functions for backward compatibility and ease of use


def save_model(
    model: Any,
    filepath: Union[str, Path],
    model_type: str,
    config: Optional[Dict] = None,
    description: str = "",
    tags: Optional[List[str]] = None,
    version: str = "1.0.0",
) -> Path:
    """
    Convenience function to save a model with metadata.

    Args:
        model: Model object to save
        filepath: Full path or directory where to save the model
        model_type: Type of model (umap, hdbscan, autoencoder, etc.)
        config: Configuration used for training
        description: Human-readable description
        tags: List of tags for categorization
        version: Version string for the model

    Returns:
        Path to saved model file
    """
    filepath = Path(filepath)

    if filepath.is_dir():
        # Generate a default filename
        model_name = f"{model_type}_model"
        manager = ModelIOManager(filepath, version)
    else:
        # Use provided filename
        model_name = filepath.stem
        manager = ModelIOManager(filepath.parent, version)

    return manager.save_model(
        model=model,
        model_name=model_name,
        model_type=model_type,
        config=config,
        description=description,
        tags=tags,
    )


def load_model(
    filepath: Union[str, Path],
    model_type: Optional[str] = None,
) -> Optional[Any]:
    """
    Convenience function to load a model.

    Args:
        filepath: Path to model file or directory containing models
        model_type: Expected model type for validation

    Returns:
        Loaded model object or None if loading failed
    """
    filepath = Path(filepath)

    if filepath.is_file():
        # Direct file loading
        try:
            return joblib.load(filepath)
        except Exception as e:
            logger.error(f"Failed to load model from {filepath}: {e}")
            return None
    else:
        # Directory-based loading with manager
        manager = ModelIOManager(filepath)
        artifact = manager.load_model(
            model_name="*",  # Will use pattern matching
            model_type=model_type,
        )
        return artifact.model if artifact else None


def enhance_model_manifest_with_pipeline_data(output_folder: Union[str, Path]) -> bool:
    """
    Enhance model_manifest.json with rich information from EMUSES pipeline output files.
    
    Reads existing JSON files produced by EMUSES pipeline and adds comprehensive
    metadata sections to the model manifest. Uses graceful degradation - missing
    files or fields result in "Not Found" entries rather than errors.
    
    Parameters
    ----------
    output_folder : Union[str, Path]
        Path to EMUSES pipeline output directory containing model artifacts
        
    Returns
    -------
    bool
        True if manifest was successfully enhanced, False otherwise
    """
    output_folder = Path(output_folder)
    manifest_path = output_folder / "model_manifest.json"
    
    logger.info(f"Enhancing model manifest: {manifest_path}")
    
    try:
        # Load existing manifest
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
        else:
            logger.warning(f"No existing manifest found at {manifest_path}")
            return False
        
        # Helper function to get latest file matching pattern
        def get_latest_file(pattern: str) -> Optional[Path]:
            """Get the most recent file matching the glob pattern."""
            files = list(output_folder.glob(pattern))
            if not files:
                return None
            # Sort by modification time, return newest
            return max(files, key=lambda f: f.stat().st_mtime)
        
        # Helper function to safely load JSON
        def load_json_safe(filepath: Optional[Path]) -> Dict[str, Any]:
            """Safely load JSON file, return empty dict if failed."""
            if not filepath or not filepath.exists():
                return {}
            try:
                with open(filepath, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load JSON from {filepath}: {e}")
                return {}
        
        # 1. Extract component configuration from best_trial_info.json
        best_trial_file = output_folder / "best_trial_info.json" 
        best_trial_data = load_json_safe(best_trial_file)
        
        component_config = {}
        if best_trial_data and "param" in best_trial_data:
            component_config = {
                "umap": best_trial_data.get("param", {}).get("umap", "Not Found"),
                "hdbscan": best_trial_data.get("param", {}).get("hdbscan", "Not Found")
            }
        else:
            component_config = {
                "umap": "Not Found",
                "hdbscan": "Not Found"
            }
        
        # 2. Extract performance metrics from best_trial_info.json
        performance_metrics = {
            "optimization": {
                "composite_score": best_trial_data.get("composite_score", "Not Found"),
                "umap_metrics": best_trial_data.get("metrics", {}).get("umap", "Not Found"),
                "hdbscan_metrics": best_trial_data.get("metrics", {}).get("hdbscan", "Not Found")
            },
            "prediction": {"targets": []}
        }
        
        # 3. Extract prediction performance and model details from target directories
        target_dirs = list(output_folder.glob("target_*"))
        for target_dir in sorted(target_dirs):
            if not target_dir.is_dir():
                continue
                
            # Get all pipeline metadata files from this target
            metadata_files = list(target_dir.glob(".metadata/best_pipeline_fold*_v*.json"))
            if not metadata_files:
                continue
            
            # Extract target ID from directory name
            target_id = target_dir.name.replace("target_", "")
            
            # Analyze all CV fold models for this target
            fold_data = []
            model_types = set()
            total_size = 0
            cv_scores = []
            
            for meta_file in metadata_files:
                pipeline_data = load_json_safe(meta_file)
                if pipeline_data:
                    fold_data.append(pipeline_data)
                    
                    # Collect model type
                    model_type = pipeline_data.get("processed_params", {}).get("model", {}).get("model_type", "Unknown")
                    model_types.add(model_type)
                    
                    # Collect file size
                    total_size += pipeline_data.get("file_size", 0)
                    
                    # Collect CV scores
                    cv_scores.append(pipeline_data.get("cv_score", 0))
            
            if fold_data:
                # Use first fold for representative data (all folds have same structure)
                representative_fold = fold_data[0]
                
                target_metrics = {
                    "target_id": target_id,
                    "cv_folds": len(fold_data),
                    "model_types": list(model_types),
                    "avg_cv_score": sum(cv_scores) / len(cv_scores) if cv_scores else "Not Found",
                    "cv_score_range": [min(cv_scores), max(cv_scores)] if cv_scores else "Not Found",
                    "inner_cv_score": representative_fold.get("optuna_study", {}).get("best_value", "Not Found"),
                    "optimization_trials": representative_fold.get("optuna_study", {}).get("n_trials", "Not Found"),
                    "scoring_metric": representative_fold.get("optuna_study", {}).get("best_trial", {}).get("user_attrs", {}).get("scoring_metric", "Not Found"),
                    "cv_std": representative_fold.get("optuna_study", {}).get("best_trial", {}).get("user_attrs", {}).get("cv_std", "Not Found"),
                    "total_size_kb": round(total_size / 1024, 1),
                    "model_parameters": representative_fold.get("processed_params", "Not Found")
                }
                performance_metrics["prediction"]["targets"].append(target_metrics)
        
        # If no target data found
        if not performance_metrics["prediction"]["targets"]:
            performance_metrics["prediction"]["targets"] = ["Not Found"]
        
        # 4. Extract training context from various files
        training_context = manifest.get("training_context", {})
        
        # Get random seeds
        random_seeds_file = output_folder / "random_seeds.json"
        random_seeds_data = load_json_safe(random_seeds_file)
        if random_seeds_data:
            training_context["random_seeds"] = random_seeds_data
        else:
            training_context["random_seeds"] = "Not Found"
        
        # Get training arguments (latest log file)  
        log_pattern = "log/arguments_*.json"
        latest_args_file = get_latest_file(log_pattern)
        args_data = load_json_safe(latest_args_file)
        
        if args_data:
            # Extract dataset info and training config
            training_context.update({
                "dataset": args_data.get("input_dataset", "Not Found"),
                "training_date": args_data.get("datetime", "Not Found"),
                "optimization_config": {
                    "umap_trials": args_data.get("umap_trials", "Not Found"),
                    "hdbscan_trials": args_data.get("hdbscan_trials", "Not Found"),
                    "prediction_trials": args_data.get("optuna_trials", "Not Found"),
                    "cv_folds": args_data.get("outer_folds", "Not Found")
                }
            })
        else:
            training_context.update({
                "dataset": "Not Found",
                "training_date": "Not Found", 
                "optimization_config": {
                    "umap_trials": "Not Found",
                    "hdbscan_trials": "Not Found",
                    "prediction_trials": "Not Found",
                    "cv_folds": "Not Found"
                }
            })
        
        # 5. Calculate enhanced file statistics from existing file_integrity and prediction models
        file_stats = {"total_size_mb": 0, "file_count": 0, "components": {}}
        
        # Start with core model files from file_integrity
        core_size = 0
        core_count = 0
        if "file_integrity" in manifest:
            for filename, file_info in manifest["file_integrity"].items():
                size_bytes = file_info.get("size", 0)
                core_size += size_bytes
                core_count += 1
                
                # Categorize by component type
                if "umap" in filename.lower():
                    file_stats["components"]["umap_model_size_mb"] = round(size_bytes / (1024 * 1024), 3)
                elif "hdbscan" in filename.lower():
                    file_stats["components"]["hdbscan_model_size_mb"] = round(size_bytes / (1024 * 1024), 3)
                elif "input_scaler" in filename.lower():
                    file_stats["components"]["input_scaler_size_kb"] = round(size_bytes / 1024, 3)
                elif "scores_scaler" in filename.lower():
                    file_stats["components"]["scores_scaler_size_kb"] = round(size_bytes / 1024, 3)
        
        # Add prediction model statistics
        prediction_size = 0
        prediction_count = 0
        num_targets = 0
        
        if performance_metrics["prediction"]["targets"] != ["Not Found"]:
            for target_info in performance_metrics["prediction"]["targets"]:
                if isinstance(target_info, dict) and "total_size_kb" in target_info:
                    target_size_bytes = target_info["total_size_kb"] * 1024
                    prediction_size += target_size_bytes
                    prediction_count += target_info.get("cv_folds", 0)
                    num_targets += 1
        
        # Calculate totals
        total_size = core_size + prediction_size
        total_count = core_count + prediction_count
        
        file_stats.update({
            "total_size_mb": round(total_size / (1024 * 1024), 3),
            "file_count": total_count,
            "components": {
                **file_stats.get("components", {}),
                "prediction_models_mb": round(prediction_size / (1024 * 1024), 3),
                "prediction_targets": num_targets,
                "prediction_cv_folds_total": prediction_count
            }
        })
        
        if total_size == 0:
            file_stats = "Not Found"
        
        # 6. Detect normalization scalers from saved scaler files
        normalization_info = {}
        
        # Check for scores scaler
        scores_scaler_path = output_folder / "scores_scaler.joblib"
        if scores_scaler_path.exists():
            try:
                import joblib
                scaler_data = joblib.load(scores_scaler_path)
                normalization_info["scores_scaler"] = "scores_scaler.joblib"
                
                # Try to detect method from scaler structure or filename patterns
                if isinstance(scaler_data, dict):
                    # bcblib scaling factors format - detect method from structure
                    sample_factors = next(iter(scaler_data.values())) if scaler_data else None
                    if isinstance(sample_factors, tuple) and len(sample_factors) == 2:
                        # Could be min-max (min, max) or zscore (mean, std)
                        normalization_info["scores_method"] = "detected_from_factors"
                    else:
                        normalization_info["scores_method"] = "robust"  # likely sklearn scaler object
                else:
                    normalization_info["scores_method"] = "unknown"
                    
                # Add file size for statistics
                scaler_size = scores_scaler_path.stat().st_size
                file_stats["components"]["scores_scaler_size_mb"] = round(scaler_size / (1024 * 1024), 6)
                logger.info(f"Detected scores scaler: {scores_scaler_path}")
            except Exception as e:
                logger.warning(f"Failed to analyze scores scaler {scores_scaler_path}: {e}")
        
        # Check for input scaler  
        input_scaler_path = output_folder / "input_scaler.joblib"
        if input_scaler_path.exists():
            try:
                import joblib
                scaler_data = joblib.load(input_scaler_path)
                normalization_info["input_scaler"] = "input_scaler.joblib"
                
                # Detect method from scaler structure
                if isinstance(scaler_data, dict):
                    sample_factors = next(iter(scaler_data.values())) if scaler_data else None
                    if isinstance(sample_factors, tuple) and len(sample_factors) == 2:
                        normalization_info["input_method"] = "detected_from_factors"
                    else:
                        normalization_info["input_method"] = "robust"
                else:
                    normalization_info["input_method"] = "unknown"
                    
                # Add file size for statistics
                scaler_size = input_scaler_path.stat().st_size
                file_stats["components"]["input_scaler_size_mb"] = round(scaler_size / (1024 * 1024), 6)
                logger.info(f"Detected input scaler: {input_scaler_path}")
            except Exception as e:
                logger.warning(f"Failed to analyze input scaler {input_scaler_path}: {e}")
        
        # UMAP rescaling is standard in EMUSES (handled by UMAPStage)
        if normalization_info:
            normalization_info["embeddings_rescaling"] = True
        
        # 7. Add enhanced sections to manifest
        manifest["component_configuration"] = component_config
        manifest["performance_metrics"] = performance_metrics  
        manifest["training_context"] = training_context
        manifest["file_statistics"] = file_stats
        if normalization_info:
            manifest["normalization"] = normalization_info
        
        # 8. Save enhanced manifest
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"Successfully enhanced manifest with pipeline data: {manifest_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to enhance manifest: {e}")
        return False
