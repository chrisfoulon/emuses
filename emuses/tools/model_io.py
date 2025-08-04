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
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
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
    ) -> Optional[ModelArtifact]:
        """
        Load a model with simplified loading mechanism.

        Args:
            model_name: Base name of the model
            model_type: Expected model type for validation
            prefix: Optional prefix used when saving

        Returns:
            ModelArtifact containing model and metadata, or None if loading failed
        """
        try:
            # Try exact match first
            artifact = self._try_load_exact_match(
                self.base_path, model_name, model_type, prefix
            )
            if artifact:
                return artifact

            # Try pattern matching
            artifact = self._try_load_with_pattern(
                self.base_path, model_name, model_type, prefix
            )
            if artifact:
                return artifact

            logger.warning(f"Could not find model: {model_name}")
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
