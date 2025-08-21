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
                      name: Optional[str] = None) -> str:
        """
        Install model from source to destination directory.

        Args:
            source_path: Path to source model directory/file
            destination_path: Base directory for model installation
            name: Optional custom name for the model

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

        # Copy model files
        try:
            if source_path.is_file():
                # Single file model
                target_path.mkdir()
                shutil.copy2(source_path, target_path / source_path.name)
            else:
                # Directory model
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

        # Basic manifest structure
        return {
            "name": model_path.name,
            "version": "1.0.0",
            "type": "unknown",  # Would need more sophisticated detection
            "description": f"Model from {model_path.name}",
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
        Analyze directory structure for complete EMUSES model components.
        
        Detects UMAP, HDBSCAN, and prediction components, calculates hashes,
        and provides comprehensive validation information.

        Parameters
        ----------
        model_path : Path
            Path to model directory to analyze

        Returns
        -------
        CompleteModelValidation
            Complete analysis result with component detection and hashes
        """
        components_found = {}
        missing_components = []
        validation_errors = []
        
        # Load manifest for metadata
        try:
            manifest = self._load_or_generate_manifest(model_path)
        except ValueError as e:
            # Handle directories with no model files
            validation_errors.append(f"No model files found: {str(e)}")
            manifest = {
                "name": model_path.name,
                "version": "1.0.0",
                "model_type": "unknown",
                "description": f"Empty directory: {model_path.name}"
            }
        
        # Detect UMAP components
        umap_component = self._detect_umap_component(model_path)
        if umap_component:
            components_found["umap"] = umap_component
        else:
            missing_components.append("umap")
        
        # Detect HDBSCAN components
        hdbscan_component = self._detect_hdbscan_component(model_path)
        if hdbscan_component:
            components_found["hdbscan"] = hdbscan_component
        else:
            missing_components.append("hdbscan")
        
        # Detect prediction components
        prediction_component = self._detect_prediction_component(model_path)
        if prediction_component:
            components_found["prediction"] = prediction_component
        else:
            missing_components.append("prediction")
        
        # Determine if this is a complete model
        is_complete = len(missing_components) == 0
        
        # Calculate configuration hash from manifest
        config_hash = self._extract_configuration_hash(manifest)
        
        # Calculate content hash from all components
        content_hash = self._calculate_content_hash(model_path, components_found)
        
        # Adjust model type for complete models
        model_type = manifest.get("model_type", "unknown")
        if is_complete and model_type not in ["complete_emuses_model"]:
            model_type = "complete_emuses_model"
        
        return CompleteModelValidation(
            is_complete_model=is_complete,
            components_found=components_found,
            configuration_hash=config_hash,
            content_hash=content_hash,
            missing_components=missing_components,
            validation_errors=validation_errors,
            name=manifest.get("name", "unknown_model"),
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
    
    def _detect_umap_component(self, model_path: Path) -> Optional[Path]:
        """Detect UMAP model component in directory."""
        # Standard patterns for UMAP models
        umap_patterns = [
            "umap_model.pkl",
            "*umap*.pkl", 
            "best_umap_model.pkl",
            "dimension_reducer.pkl"
        ]
        
        for pattern in umap_patterns:
            matches = list(model_path.glob(pattern))
            if matches:
                return matches[0]  # Return first match
        
        return None
    
    def _detect_hdbscan_component(self, model_path: Path) -> Optional[Path]:
        """Detect HDBSCAN model component in directory."""
        # Standard patterns for HDBSCAN models
        hdbscan_patterns = [
            "hdbscan_model.pkl",
            "*hdbscan*.pkl",
            "best_hdbscan_model.pkl", 
            "clustering_model.pkl",
            "*cluster*.pkl"
        ]
        
        for pattern in hdbscan_patterns:
            matches = list(model_path.glob(pattern))
            if matches:
                return matches[0]  # Return first match
        
        return None
    
    def _detect_prediction_component(self, model_path: Path) -> Optional[Path]:
        """Detect prediction model component(s) in directory."""
        # Check for prediction ensemble directory
        prediction_dirs = [
            model_path / "prediction_ensemble",
            model_path / "predictions",
            model_path / "models"
        ]
        
        for pred_dir in prediction_dirs:
            if pred_dir.exists() and pred_dir.is_dir():
                # Check if directory contains model files
                model_files = list(pred_dir.glob("*.pkl")) + list(pred_dir.glob("*.joblib"))
                if model_files:
                    return pred_dir
        
        # Check for individual prediction model files
        prediction_patterns = [
            "*prediction*.pkl",
            "ensemble_model.pkl",
            "best_prediction_model*.pkl"
        ]
        
        for pattern in prediction_patterns:
            matches = list(model_path.glob(pattern))
            if matches:
                return matches[0]
        
        return None
    
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
    
    def _calculate_content_hash(self, model_path: Path, components: Dict[str, Path]) -> str:
        """Calculate content hash from model components."""
        hasher = hashlib.sha256()
        
        # Hash each component file/directory
        for component_type, component_path in sorted(components.items()):
            hasher.update(component_type.encode())
            
            if component_path.is_file():
                # Hash file contents
                with open(component_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hasher.update(chunk)
            elif component_path.is_dir():
                # Hash directory contents recursively
                for file_path in sorted(component_path.rglob("*")):
                    if file_path.is_file():
                        hasher.update(str(file_path.relative_to(component_path)).encode())
                        with open(file_path, 'rb') as f:
                            for chunk in iter(lambda: f.read(4096), b""):
                                hasher.update(chunk)
        
        return hasher.hexdigest()[:16]

    def _create_metadata(
        self,
        model_type: str,
        config: Optional[Dict],
        description: str,
        tags: List[str],
        force_version: Optional[str],
        optuna_study: Optional[Any] = None,
        optuna_trial: Optional[Any] = None,
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
                optuna_study, optuna_trial
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

    def _extract_optuna_study_metadata(self, study: Any, trial: Any) -> OptunaStudy:
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

    def _calculate_file_hash(self, filepath: Path) -> str:
        """Calculate SHA-256 hash of a file."""
        hash_sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

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
