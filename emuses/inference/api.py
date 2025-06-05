# emuses/inference/api_fixed.py

"""
EMUSES Inference API - sklearn-like interface for EMUSES core functionality

This module provides a streamlined, sklearn-like API for EMUSES that focuses on
the core UMAP dimensionality reduction and clustering functionality from UMAPStage,
with optional access to feature engineering utilities from features_utils.py.
"""

import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, Union, Dict, Any, Tuple, List
import warnings
import json
import joblib
from sklearn.base import BaseEstimator

# Import existing EMUSES components
from emuses.tools.model_io import ModelIOManager

# Import core UMAP functionality
from emuses.tools.UMAP_utils import (
    train_and_save_umap_optim_with_nested_clustering,
    load_umap_model,
)
from emuses.tools.clustering_utils import load_hdbscan_model
from emuses.tools.emuses_utils import rescale_embedding

# Import prediction stage functionality
from emuses.pipelines.prediction_stage import PredictionStage
from emuses.pipelines.emuses_pipeline import EMUSESPipeline
from emuses.pipelines.umap_stage import UMAPStage
from emuses.pipelines.heatmap_stage import HeatmapStage
from emuses.pipelines.pipeline_config import PipelineConfig

# Import feature engineering utilities (optional)
from emuses.tools.features_utils import RawCoords, GWD, PCAGWD, KernelPCAGWD, CorrFilter

# Import configuration
from emuses.config.optim_configs import optim_dict_default


class EMUSESInferenceAPI:
    """
    sklearn-like inference API for EMUSES core functionality.

    This class provides a simplified interface to EMUSES core UMAP and clustering
    functionality, allowing users to fit UMAP models and transform new data with
    a simple .fit() and .transform() interface. Optionally provides access to
    feature engineering utilities.

    The API focuses on the core EMUSES workflow:
    1. UMAP dimensionality reduction with optimization
    2. HDBSCAN clustering
    3. Optional feature engineering on input data

    Example usage:
        >>> api = EMUSESInferenceAPI(model_dir="./models")
        >>> embeddings = api.fit_transform(X_train)
        >>> new_embeddings = api.transform(X_test)

    Or with feature engineering:
        >>> features = api.extract_features(X_train, method="gwd")
        >>> embeddings = api.fit_transform(features)
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        model_dir: Union[str, Path] = "./emuses_models",
        verbose: bool = False,
    ):
        """
        Initialize the EMUSES Inference API.

        Parameters
        ----------
        config : dict, optional
            Configuration dictionary for the API. If None, uses default configuration.
        model_dir : str or Path, optional
            Directory for model storage. Default: "./emuses_models"
        verbose : bool, optional
            Whether to enable verbose logging. Default: False
        """
        self.config = config or self._get_default_config()
        self.model_dir = Path(model_dir)
        self.verbose = verbose

        # Set up logging
        if verbose:
            logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # Initialize ModelIOManager
        self.model_manager = ModelIOManager(str(self.model_dir))

        # Initialize state
        self.is_fitted_ = False

        # Core UMAP/clustering components
        self.umap_model_ = None
        self.clusterer_ = None
        self.cluster_labels_ = None
        self.min_embeddings_ = None
        self.max_embeddings_ = None

        # Supervised learning components (new)
        self.prediction_models_ = {}  # Dictionary to store prediction models per target
        self.preprocessing_params_ = {}  # Store preprocessing parameters
        self.embeddings_train_ = None  # Store training embeddings for reference
        self.target_names_ = None  # Store target variable names
        self.is_supervised_fitted_ = False  # Track supervised fitting state

        # Feature engineering components (optional)
        self.feature_transformers_ = {}

        # Create model directory if it doesn't exist
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for the API."""
        return {
            # UMAP optimization parameters
            "umap_trials": 50,
            "umap_jobs": 1,
            "random_state": 42,
            # HDBSCAN optimization parameters
            "hdbscan_trials": 20,
            "hdbscan_jobs": 1,
            "hdbscan_approx_min_span_tree": True,
            "hdbscan_core_dist_n_jobs": -1,
            # Feature engineering options
            "enable_feature_engineering": False,
            "feature_methods": ["raw", "gwd"],  # raw coords, GWD features
            "gwd_sigma": 0.1,
            "pcagwd_n_components": 10,
            "kernelpca_n_components": 30,
            "correlation_threshold": 0.25,
            # Optimization dictionary
            "optim_dict": optim_dict_default,
        }

    def fit(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Optional[Union[np.ndarray, pd.DataFrame]] = None,
        prefix: str = "",
    ) -> "EMUSESInferenceAPI":
        """
        Fit the EMUSES model on training data.

        If y is provided, fits a complete supervised learning pipeline:
        1. UMAP dimensionality reduction with clustering optimization
        2. Prediction model training using nested cross-validation
        3. Model ensemble creation for robust predictions

        If y is None, fits only the unsupervised components (UMAP + clustering).

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            Training input samples.
        y : array-like of shape (n_samples,) or (n_samples, n_targets), optional
            Target values for supervised learning. If None, only unsupervised learning.
        prefix : str, optional
            Prefix for saved model files. Default: ""

        Returns
        -------
        self : EMUSESInferenceAPI
            Returns self for method chaining.
        """
        # Input validation
        X = self._validate_input(X, "X")

        if y is not None:
            y = self._validate_input(y, "y")
            if y.ndim == 1:
                y = y.reshape(-1, 1)

            self.logger.info(
                f"Fitting EMUSES supervised pipeline on data with shape {X.shape} and targets {y.shape}"
            )

            # Store target names
            if hasattr(y, "columns"):
                self.target_names_ = list(y.columns)
            else:
                self.target_names_ = [f"target_{i}" for i in range(y.shape[1])]

            # Fit complete supervised pipeline using existing EMUSES infrastructure
            return self._fit_supervised_pipeline(X, y, prefix)
        else:
            self.logger.info(
                f"Fitting EMUSES unsupervised pipeline on data with shape {X.shape}"
            )

            # Fit only unsupervised components (existing functionality)
            return self._fit_unsupervised_pipeline(X, prefix)

    def _fit_supervised_pipeline(
        self, X: np.ndarray, y: np.ndarray, prefix: str = ""
    ) -> "EMUSESInferenceAPI":
        """
        Fit the complete supervised EMUSES pipeline.

        This method uses the existing EMUSES pipeline infrastructure to:
        1. Set up pipeline configuration
        2. Run UMAP stage (dimensionality reduction + clustering)
        3. Run HeatmapStage (embedding coordinate preparation)
        4. Run PredictionStage (model training with nested CV)
        5. Save all models and metadata with selective serialization
        """  # Create temporary workspace for pipeline
        temp_workspace = self.model_dir / f"temp_supervised_{prefix}"
        temp_workspace.mkdir(exist_ok=True, parents=True)

        try:
            # Set up pipeline configuration with required output_folder_path
            config = PipelineConfig(output_folder_path=str(temp_workspace))
            config.random_state = self.config.get("random_state", 42)

            # Enhanced pipeline settings for supervised learning
            config.use_enhanced_pipeline = True
            config.optuna_trials = self.config.get("umap_trials", 50)
            config.n_jobs = self.config.get("umap_jobs", 1)
            config.parallel_models = self.config.get("parallel_models", False)

            # Initialize context for pipeline stages
            context = {}
            context["random_seeds"] = {
                "prediction_seed": config.random_state,
                "cv_seed": config.random_state + 1,
                "optuna_seed": config.random_state + 2,
                "umap_seed": config.random_state + 3,
                "hdbscan_seed": config.random_state + 4,
            }

            # Store input data and targets in context
            context["input_matrix"] = X
            context["prediction_train_labels"] = y
            context["target_names"] = self.target_names_

            # Run UMAP Stage
            self.logger.info("Running UMAP stage for dimensionality reduction...")
            umap_stage = UMAPStage(config)
            umap_stage.run(context)

            # Extract embeddings from context
            train_embeddings = context.get("embedding_train_coords")
            if train_embeddings is None:
                raise ValueError("UMAP stage failed to generate embeddings")

            # Store embeddings and rescaling parameters
            self.embeddings_train_ = train_embeddings
            self.min_embeddings_ = train_embeddings.min(axis=0)
            self.max_embeddings_ = train_embeddings.max(axis=0)

            # Apply rescaling
            self.embeddings_ = rescale_embedding(
                train_embeddings,
                preset_min=self.min_embeddings_,
                preset_max=self.max_embeddings_,
            )

            # Store UMAP model and clustering results
            self.umap_model_ = context.get("embedding_train_umap_model")
            self.clusterer_ = context.get("embedding_train_clusterer")
            self.cluster_labels_ = context.get("embedding_train_cluster_labels")

            # Prepare data for prediction stage
            context["prediction_train_coords"] = self.embeddings_

            # Run Prediction Stage
            self.logger.info(
                "Running prediction stage for supervised model training..."
            )
            prediction_stage = PredictionStage(config)
            prediction_stage.run(context)

            # Extract prediction models from context and workspace
            self._extract_prediction_models(temp_workspace, context)

            # Save lightweight context with selective serialization
            self._save_supervised_state(context, prefix)

            # Mark as fitted
            self.is_fitted_ = True
            self.is_supervised_fitted_ = True

            self.logger.info(
                "EMUSES supervised pipeline fitting completed successfully"
            )

        except Exception as e:
            self.logger.error(f"Error during supervised pipeline fitting: {e}")
            raise
        finally:
            # Clean up temporary workspace
            import shutil

            if temp_workspace.exists():
                shutil.rmtree(temp_workspace)

        return self

    def _fit_unsupervised_pipeline(
        self, X: np.ndarray, prefix: str = ""
    ) -> "EMUSESInferenceAPI":
        """
        Fit only the unsupervised components (existing functionality).

        This is the original fit method for UMAP + clustering only.
        """
        # Store original data for reference
        self.X_fit_ = X.copy()

        # Create temporary directory for UMAP training
        temp_dir = self.model_dir / "temp_training"
        temp_dir.mkdir(exist_ok=True)

        try:
            # Train UMAP with nested clustering optimization
            (
                self.umap_model_,
                embeddings,
                umap_path,
                embeddings_path,
                self.clusterer_,
                self.cluster_labels_,
                cluster_model_path,
                cluster_labels_path,
                input_matrix_path,
            ) = train_and_save_umap_optim_with_nested_clustering(
                input_matrix=X,
                output_folder=temp_dir,
                optim_dict=self.config["optim_dict"],
                n_trials=self.config["umap_trials"],
                n_inner_trials=self.config["hdbscan_trials"],
                pref=prefix,
                n_jobs=self.config["umap_jobs"],
                inner_n_jobs=self.config["hdbscan_jobs"],
                random_state=self.config["random_state"],
                clusterer_random_state=self.config["random_state"],
                approx_min_span_tree=self.config["hdbscan_approx_min_span_tree"],
                core_dist_n_jobs=self.config["hdbscan_core_dist_n_jobs"],
            )

            # Calculate rescaling parameters
            self.min_embeddings_ = embeddings.min(axis=0)
            self.max_embeddings_ = embeddings.max(axis=0)

            # Rescale embeddings
            self.embeddings_ = rescale_embedding(
                embeddings,
                preset_min=self.min_embeddings_,
                preset_max=self.max_embeddings_,
            )

            # Move models to final location
            final_umap_path = self.model_dir / f"{prefix}umap_model.joblib"
            final_cluster_path = self.model_dir / f"{prefix}hdbscan_model.joblib"
            final_embeddings_path = self.model_dir / f"{prefix}embeddings.npy"
            final_labels_path = self.model_dir / f"{prefix}cluster_labels.npy"

            # Copy files to final location
            import shutil

            shutil.move(str(umap_path), str(final_umap_path))
            shutil.move(str(cluster_model_path), str(final_cluster_path))
            shutil.move(str(embeddings_path), str(final_embeddings_path))
            shutil.move(str(cluster_labels_path), str(final_labels_path))

            # Clean up temp directory
            shutil.rmtree(temp_dir)

            self.logger.info(f"UMAP model saved to: {final_umap_path}")
            self.logger.info(f"HDBSCAN model saved to: {final_cluster_path}")

        except Exception as e:
            self.logger.error(f"Error during UMAP fitting: {e}")
            # Clean up temp directory on error
            import shutil

            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            raise

        # Mark as fitted
        self.is_fitted_ = True

        self.logger.info("EMUSES unsupervised API fitting completed successfully")
        return self

    def _extract_prediction_models(
        self, workspace: Path, context: Dict[str, Any]
    ) -> None:
        """Extract prediction models from workspace and context after PredictionStage."""
        self.prediction_models_ = {}

        # Look for models saved by PredictionStage
        model_dirs = list(workspace.glob("prediction_models/*/"))
        for model_dir in model_dirs:
            target_name = model_dir.name

            # Look for model files in different patterns
            model_patterns = ["final_model.joblib", "best_model*.joblib", "*.joblib"]
            for pattern in model_patterns:
                model_files = list(model_dir.glob(pattern))
                if model_files:
                    try:
                        # Load the first available model
                        model = joblib.load(model_files[0])
                        self.prediction_models_[target_name] = model
                        self.logger.info(
                            f"Extracted prediction model for {target_name}"
                        )
                        break
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to load model for {target_name}: {e}"
                        )

        # Store preprocessing parameters
        self.preprocessing_params_ = {
            "sigma": context.get("prediction_train_sigma"),
            "embedding_sigma": context.get("embedding_train_sigma"),
            "random_state": context.get("random_seeds", {}).get("prediction_seed", 42),
        }

    def _save_supervised_state(self, context: Dict[str, Any], prefix: str = "") -> None:
        """Save supervised learning state with selective serialization."""
        # Extract lightweight context
        lightweight_context = self._extract_lightweight_context(context)

        # Add API-specific metadata
        api_metadata = {
            "api_version": "1.0.0",
            "fit_timestamp": pd.Timestamp.now().isoformat(),
            "is_supervised": True,
            "target_names": self.target_names_,
            "model_counts": {
                "prediction_models": len(self.prediction_models_),
                "umap_model": 1 if self.umap_model_ is not None else 0,
                "clustering_model": 1 if self.clusterer_ is not None else 0,
            },
            "preprocessing_params": self.preprocessing_params_,
            "embedding_rescaling": {
                "min_embeddings": (
                    self.min_embeddings_.tolist()
                    if self.min_embeddings_ is not None
                    else None
                ),
                "max_embeddings": (
                    self.max_embeddings_.tolist()
                    if self.max_embeddings_ is not None
                    else None
                ),
            },
        }
        lightweight_context["api_metadata"] = api_metadata

        # Save lightweight context as JSON
        state_file = self.model_dir / f"{prefix}emuses_training_state.json"
        with open(state_file, "w") as f:
            json.dump(lightweight_context, f, indent=2, default=str)

        # Save models separately using ModelIOManager
        for target_name, model in self.prediction_models_.items():
            model_name = f"{prefix}prediction_model_{target_name}"
            try:
                self.model_manager.save_model(
                    model=model,
                    model_name=model_name,
                    model_type="prediction",
                    description=f"Prediction model for {target_name}",
                    tags=["supervised", "prediction", target_name],
                )
            except Exception as e:
                self.logger.warning(f"Failed to save model for {target_name}: {e}")

        # Save UMAP and clustering models
        if self.umap_model_ is not None:
            umap_path = self.model_dir / f"{prefix}umap_model.joblib"
            joblib.dump(self.umap_model_, umap_path)

        if self.clusterer_ is not None:
            cluster_path = self.model_dir / f"{prefix}hdbscan_model.joblib"
            joblib.dump(self.clusterer_, cluster_path)

        # Save embeddings and labels as numpy arrays
        if self.embeddings_train_ is not None:
            np.save(
                self.model_dir / f"{prefix}train_embeddings.npy", self.embeddings_train_
            )
        if self.cluster_labels_ is not None:
            np.save(
                self.model_dir / f"{prefix}cluster_labels.npy", self.cluster_labels_
            )

        self.logger.info(
            f"Saved supervised state to {state_file} (size: {state_file.stat().st_size / 1024:.1f} KB)"
        )

    def transform(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """
        Transform new data using the fitted UMAP model.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            Input samples for transformation.

        Returns
        -------
        embeddings : ndarray of shape (n_samples, n_components)
            Transformed embeddings.
        """
        if not self.is_fitted_:
            raise ValueError(
                "This model has not been fitted yet. "
                "Call 'fit' with appropriate arguments before using transform."
            )

        # Input validation
        X = self._validate_input(X, "X")

        self.logger.info(f"Transforming data with shape {X.shape}")

        # Transform using fitted UMAP model
        embeddings = self.umap_model_.transform(X)

        # Rescale using fitted parameters
        embeddings = rescale_embedding(
            embeddings,
            preset_min=self.min_embeddings_,
            preset_max=self.max_embeddings_,
        )

        return embeddings

    def fit_transform(
        self, X: Union[np.ndarray, pd.DataFrame], prefix: str = ""
    ) -> np.ndarray:
        """
        Fit the model and transform the training data.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            Training input samples.
        prefix : str, optional
            Prefix for saved model files. Default: ""

        Returns
        -------
        embeddings : ndarray of shape (n_samples, n_components)
            Transformed embeddings of the training data.
        """
        self.fit(X, prefix=prefix)
        return self.embeddings_

    def extract_features(
        self, X: Union[np.ndarray, pd.DataFrame], method: str = "raw", **kwargs
    ) -> np.ndarray:
        """
        Extract features from input data using EMUSES feature engineering utilities.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            Input data for feature extraction.
        method : str, optional
            Feature extraction method. Options: 'raw', 'gwd', 'pcagwd', 'kernelpca', 'corrfilter'
            Default: 'raw'
        **kwargs
            Additional parameters for the feature extraction method.

        Returns
        -------
        features : ndarray
            Extracted features.
        """
        # Input validation
        X = self._validate_input(X, "X")

        self.logger.info(f"Extracting features using method: {method}")

        if method == "raw":
            # Raw coordinates - just return input as-is
            transformer = RawCoords()
            features = transformer.fit_transform(X)

        elif method == "gwd":
            # Geodesic Wasserstein Distance features
            sigma = kwargs.get("sigma", self.config.get("gwd_sigma", 0.1))
            transformer = GWD(sigma=sigma)
            features = transformer.fit_transform(X)

        elif method == "pcagwd":
            # PCA + GWD features
            n_components = kwargs.get(
                "n_components", self.config.get("pcagwd_n_components", 10)
            )
            sigma = kwargs.get("sigma", self.config.get("gwd_sigma", 0.1))
            transformer = PCAGWD(n_components=n_components, sigma=sigma)
            features = transformer.fit_transform(X)

        elif method == "kernelpca":
            # Kernel PCA + GWD features
            n_components = kwargs.get(
                "n_components", self.config.get("kernelpca_n_components", 30)
            )
            sigma = kwargs.get("sigma", self.config.get("gwd_sigma", 0.1))
            transformer = KernelPCAGWD(n_components=n_components, sigma=sigma)
            features = transformer.fit_transform(X)

        elif method == "corrfilter":
            # Correlation filter
            threshold = kwargs.get(
                "threshold", self.config.get("correlation_threshold", 0.25)
            )
            transformer = CorrFilter(threshold=threshold)
            features = transformer.fit_transform(X)

        else:
            raise ValueError(f"Unknown feature extraction method: {method}")

        # Store transformer for later use
        self.feature_transformers_[method] = transformer

        self.logger.info(f"Extracted features with shape: {features.shape}")
        return features

    def predict_clusters(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """
        Predict cluster labels for new data.

        Note: This uses the fitted clusterer to predict labels for new embeddings.
        The clusterer was trained on the training embeddings.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            Input samples for cluster prediction.

        Returns
        -------
        labels : ndarray of shape (n_samples,)
            Predicted cluster labels.
        """
        if not self.is_fitted_:
            raise ValueError(
                "This model has not been fitted yet. "
                "Call 'fit' with appropriate arguments before using predict_clusters."
            )

        if self.clusterer_ is None:
            raise ValueError(
                "No clusterer available. Clustering may have failed during fitting."
            )

        # Transform to embeddings first
        embeddings = self.transform(X)

        # Predict clusters using the fitted clusterer
        # Note: HDBSCAN doesn't have a predict method, so we use approximate_predict
        try:
            if hasattr(self.clusterer_, "approximate_predict"):
                labels = self.clusterer_.approximate_predict(embeddings)[0]
            else:
                # Fallback: assign to nearest training cluster
                from sklearn.neighbors import NearestNeighbors

                nn = NearestNeighbors(n_neighbors=1)
                nn.fit(self.embeddings_)
                distances, indices = nn.kneighbors(embeddings)
                labels = self.cluster_labels_[indices.flatten()]
        except Exception as e:
            self.logger.warning(
                f"Cluster prediction failed: {e}. Returning -1 for all samples."
            )
            labels = np.full(embeddings.shape[0], -1)

        return labels

    def get_cluster_labels(self) -> np.ndarray:
        """
        Get cluster labels for the training data.

        Returns
        -------
        labels : ndarray of shape (n_training_samples,)
            Cluster labels for training data.
        """
        if not self.is_fitted_:
            raise ValueError("Model not fitted yet. Call fit() first.")

        if self.cluster_labels_ is None:
            raise ValueError("No cluster labels available.")

        return self.cluster_labels_.copy()

    def get_embeddings(self) -> np.ndarray:
        """
        Get embeddings for the training data.

        Returns
        -------
        embeddings : ndarray of shape (n_training_samples, n_components)
            Embeddings for training data.
        """
        if not self.is_fitted_:
            raise ValueError("Model not fitted yet. Call fit() first.")

        if self.embeddings_ is None:
            raise ValueError("No embeddings available.")

        return self.embeddings_.copy()

    def _extract_lightweight_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only lightweight metadata from EMUSES context, excluding heavy objects
        already saved as separate files.

        Based on systematic analysis of EMUSES modules, this function excludes:
        - Large numpy arrays (embeddings, matrices, cluster labels)
        - Trained models (UMAP, HDBSCAN, prediction models)
        - Heavy optimization results (Optuna studies, parameter logs)

        Parameters
        ----------
        context : dict
            Full EMUSES context object

        Returns
        -------
        lightweight_context : dict
            Context containing only lightweight metadata and file references
        """
        lightweight_context = {}

        # Model parameters (lightweight)
        model_params = {}
        if "umap_params" in context:
            model_params["umap_params"] = context["umap_params"]
        if "hdbscan_params" in context:
            model_params["hdbscan_params"] = context["hdbscan_params"]
        if "prediction_params" in context:
            model_params["prediction_params"] = context["prediction_params"]
        if model_params:
            lightweight_context["model_parameters"] = model_params

        # Performance metrics (lightweight)
        metrics = {}
        for key in context:
            if any(
                metric_key in key.lower()
                for metric_key in [
                    "r2",
                    "mse",
                    "mae",
                    "accuracy",
                    "f1",
                    "precision",
                    "recall",
                    "silhouette",
                    "dbcv",
                    "score",
                    "metric",
                ]
            ):
                if isinstance(context[key], (int, float, str, bool, list, dict)):
                    # Only include if it's lightweight (not large arrays)
                    if (
                        not isinstance(context[key], np.ndarray)
                        or context[key].size < 100
                    ):
                        metrics[key] = context[key]
        if metrics:
            lightweight_context["performance_metrics"] = metrics

        # Configuration settings (lightweight)
        config_keys = [
            "random_state",
            "random_seeds",
            "n_trials",
            "n_jobs",
            "cv_folds",
            "grid_size",
            "threshold",
            "dataset_type",
            "stage_completion_status",
            "processing_flags",
            "optimization_params",
            "sigma",
            "alpha",
            "kernel",
            "prediction_train_sigma",
            "embedding_train_sigma",
        ]
        config_settings = {}
        for key in config_keys:
            if key in context:
                config_settings[key] = context[key]
        if config_settings:
            lightweight_context["configuration"] = config_settings

        # File path references (lightweight - paths only, not the data)
        file_refs = {}
        for key in context:
            if any(
                path_key in key.lower()
                for path_key in ["path", "file", "folder", "dir"]
            ):
                if isinstance(context[key], (str, Path)):
                    file_refs[key] = str(context[key])
        if file_refs:
            lightweight_context["file_references"] = file_refs

        # Small computed values (lightweight)
        small_values = {}
        for key in context:
            if key.endswith(
                (
                    "_min",
                    "_max",
                    "_mean",
                    "_std",
                    "_count",
                    "_size",
                    "_length",
                    "_percentage",
                    "_ratio",
                    "_factor",
                )
            ):
                if isinstance(context[key], (int, float, str, bool)):
                    small_values[key] = context[key]
        if small_values:
            lightweight_context["computed_values"] = small_values

        # Target information (lightweight)
        target_info = {}
        for key in ["target_names", "score_names", "label_names", "column_names"]:
            if key in context and isinstance(context[key], (list, tuple, str)):
                target_info[key] = context[key]
        if target_info:
            lightweight_context["target_information"] = target_info

        return lightweight_context

    def _load_models_from_context(
        self, lightweight_context: Dict[str, Any], model_dir: Path
    ) -> None:
        """
        Load trained models from files using references in lightweight context.

        This method attempts to load models using EMUSES naming patterns:
        - UMAP models: umap_model.joblib, *umap*.joblib
        - HDBSCAN models: hdbscan_model.joblib, *hdbscan*.joblib
        - Prediction models: best_prediction_model_*.joblib, best_model_*.joblib
        - Autoencoder models: best_ae_model.joblib, ae_model.joblib

        Parameters
        ----------
        lightweight_context : dict
            Lightweight context with file references
        model_dir : Path
            Directory containing saved models
        """
        file_refs = lightweight_context.get("file_references", {})

        # Load UMAP model
        umap_patterns = [
            "umap_model.joblib",
            "*umap*.joblib",
            "embedding_train_umap_model.joblib",
        ]
        for pattern in umap_patterns:
            umap_files = list(model_dir.glob(pattern))
            if umap_files:
                try:
                    self.umap_model_, _ = load_umap_model(umap_files[0])
                    self.logger.info(f"Loaded UMAP model from {umap_files[0]}")
                    break
                except Exception as e:
                    self.logger.warning(
                        f"Failed to load UMAP model from {umap_files[0]}: {e}"
                    )

        # Load HDBSCAN model
        hdbscan_patterns = [
            "hdbscan_model.joblib",
            "*hdbscan*.joblib",
            "clustering_model.joblib",
        ]
        for pattern in hdbscan_patterns:
            hdbscan_files = list(model_dir.glob(pattern))
            if hdbscan_files:
                try:
                    self.clusterer_, _ = load_hdbscan_model(
                        hdbscan_files[0].parent, model_name=hdbscan_files[0].stem
                    )
                    self.logger.info(f"Loaded HDBSCAN model from {hdbscan_files[0]}")
                    break
                except Exception as e:
                    self.logger.warning(
                        f"Failed to load HDBSCAN model from {hdbscan_files[0]}: {e}"
                    )

        # Load prediction models using ModelIOManager patterns
        prediction_patterns = [
            "best_prediction_model_*.joblib",
            "best_model_*.joblib",
            "*prediction*.joblib",
            "final_model.joblib",
        ]
        self.prediction_models_ = {}

        for pattern in prediction_patterns:
            pred_files = list(model_dir.glob(pattern))
            for pred_file in pred_files:
                try:
                    # Extract target name from filename
                    filename = pred_file.stem
                    if "target_" in filename:
                        target_name = filename.split("target_")[-1].split("_")[0]
                    elif "fold" in filename:
                        target_name = filename.split("_fold")[0].split("_")[-1]
                    else:
                        target_name = filename.replace("best_model_", "").replace(
                            "prediction_", ""
                        )

                    model = joblib.load(pred_file)
                    self.prediction_models_[target_name] = model
                    self.logger.info(
                        f"Loaded prediction model for {target_name} from {pred_file}"
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to load prediction model from {pred_file}: {e}"
                    )

    def _load_heavy_data_from_context(
        self, lightweight_context: Dict[str, Any], model_dir: Path
    ) -> None:
        """
        Load heavy data arrays from files using references in lightweight context.

        This method loads numpy arrays using EMUSES naming patterns:
        - Embeddings: embeddings.npy, train_embeddings.npy, *embedding*.npy
        - Cluster labels: cluster_labels.npy, *labels*.npy
        - Input matrices: input_matrix.npy, *matrix*.npy
        - Feature arrays: *features*.npy, *gwd*.npy

        Parameters
        ----------
        lightweight_context : dict
            Lightweight context with file references
        model_dir : Path
            Directory containing saved arrays
        """
        file_refs = lightweight_context.get("file_references", {})

        # Load embeddings
        embedding_patterns = [
            "embeddings.npy",
            "train_embeddings.npy",
            "*embedding*.npy",
            "prediction_train_coords.npy",
            "embedding_train_coords.npy",
        ]
        for pattern in embedding_patterns:
            embedding_files = list(model_dir.glob(pattern))
            if embedding_files:
                try:
                    self.embeddings_train_ = np.load(embedding_files[0])
                    self.logger.info(f"Loaded embeddings from {embedding_files[0]}")
                    break
                except Exception as e:
                    self.logger.warning(
                        f"Failed to load embeddings from {embedding_files[0]}: {e}"
                    )

        # Load cluster labels
        label_patterns = ["cluster_labels.npy", "*labels*.npy", "clustering_labels.npy"]
        for pattern in label_patterns:
            label_files = list(model_dir.glob(pattern))
            if label_files:
                try:
                    self.cluster_labels_ = np.load(label_files[0])
                    self.logger.info(f"Loaded cluster labels from {label_files[0]}")
                    break
                except Exception as e:
                    self.logger.warning(
                        f"Failed to load cluster labels from {label_files[0]}: {e}"
                    )

        # Load preprocessing parameters from lightweight context
        config = lightweight_context.get("configuration", {})
        if "prediction_train_sigma" in config:
            self.preprocessing_params_["sigma"] = config["prediction_train_sigma"]
        if "embedding_train_sigma" in config:
            self.preprocessing_params_["embedding_sigma"] = config[
                "embedding_train_sigma"
            ]

        # Load rescaling parameters
        computed_values = lightweight_context.get("computed_values", {})
        for key in ["min_embeddings", "max_embeddings"]:
            if key in computed_values:
                setattr(self, f"{key}_", computed_values[key])

    def _apply_preprocessing_from_context(
        self, X: np.ndarray, lightweight_context: Dict[str, Any]
    ) -> np.ndarray:
        """
        Apply preprocessing steps to new data based on saved parameters.

        This method applies the same preprocessing pipeline used during training:
        1. Data normalization/scaling (if applicable)
        2. Feature engineering (if applicable)
        3. UMAP transformation to embedding space
        4. Embedding rescaling using saved min/max values

        Parameters
        ----------
        X : np.ndarray
            New input data to preprocess
        lightweight_context : dict
            Context containing preprocessing parameters

        Returns
        -------
        X_processed : np.ndarray
            Preprocessed data ready for prediction
        """
        X_processed = X.copy()

        # Apply feature engineering if transformers were saved
        if hasattr(self, "feature_transformers_") and self.feature_transformers_:
            # Apply the same feature transformations used during training
            for transformer_name, transformer in self.feature_transformers_.items():
                if hasattr(transformer, "transform"):
                    X_processed = transformer.transform(X_processed)
                    self.logger.info(
                        f"Applied {transformer_name} feature transformation"
                    )
                    break  # Use the first available transformer

        # Transform to embedding space using UMAP
        if self.umap_model_ is not None:
            X_processed = self.umap_model_.transform(X_processed)
            self.logger.info("Transformed to embedding space using UMAP")

            # Apply rescaling using saved parameters
            if hasattr(self, "min_embeddings_") and hasattr(self, "max_embeddings_"):
                if (
                    self.min_embeddings_ is not None
                    and self.max_embeddings_ is not None
                ):
                    X_processed = rescale_embedding(
                        X_processed,
                        preset_min=self.min_embeddings_,
                        preset_max=self.max_embeddings_,
                    )
                    self.logger.info("Applied embedding rescaling")

        return X_processed

    def save_model(self, model_name: str = "emuses_inference_model"):
        """
        Save the fitted model to disk.

        Parameters
        ----------
        model_name : str, optional
            Name for the saved model. Default: "emuses_inference_model"
        """
        if not self.is_fitted_:
            raise ValueError("Cannot save unfitted model. Call fit() first.")

        model_data = {
            "config": self.config,
            "is_fitted": self.is_fitted_,
            "feature_transformers": self.feature_transformers_,
            "min_embeddings": self.min_embeddings_,
            "max_embeddings": self.max_embeddings_,
            "cluster_labels": self.cluster_labels_,
            "embeddings": self.embeddings_,
        }

        # Use ModelIOManager to save
        self.model_manager.save_model(model_data, model_name)
        self.logger.info(f"Model saved as {model_name}")

    def load_model(self, model_name: str = "emuses_inference_model"):
        """
        Load a previously saved model from disk.

        Parameters
        ----------
        model_name : str, optional
            Name of the model to load. Default: "emuses_inference_model"
        """
        # Use ModelIOManager to load
        model_data = self.model_manager.load_model(model_name)

        if model_data is None:
            raise FileNotFoundError(f"Model '{model_name}' not found")

        # Restore state
        self.config = model_data["config"]
        self.is_fitted_ = model_data["is_fitted"]
        self.feature_transformers_ = model_data["feature_transformers"]
        self.min_embeddings_ = model_data["min_embeddings"]
        self.max_embeddings_ = model_data["max_embeddings"]
        self.cluster_labels_ = model_data["cluster_labels"]
        self.embeddings_ = model_data["embeddings"]

        # Load the actual UMAP and HDBSCAN models from disk
        try:
            umap_path = self.model_dir / "umap_model.joblib"
            cluster_path = self.model_dir / "hdbscan_model.joblib"

            if umap_path.exists():
                self.umap_model_, _ = load_umap_model(umap_path)
            if cluster_path.exists():
                self.clusterer_, _ = load_hdbscan_model(
                    cluster_path.parent, model_name="hdbscan_model"
                )
        except Exception as e:
            self.logger.warning(f"Could not load UMAP/HDBSCAN models: {e}")

        self.logger.info(f"Model {model_name} loaded successfully")

    def save_context(self, file_path: Union[str, Path]):
        """
        Save the lightweight context of the fitted model to a JSON file.

        Parameters
        ----------
        file_path : str or Path
            Path to the output JSON file.
        """
        if not self.is_fitted_:
            raise ValueError("Cannot save context of unfitted model. Call fit() first.")

        context_data = {
            "min_embeddings": self.min_embeddings_,
            "max_embeddings": self.max_embeddings_,
            "cluster_labels": self.cluster_labels_,
            "embeddings": self.embeddings_,
        }

        # Save to JSON file
        with open(file_path, "w") as json_file:
            json.dump(context_data, json_file)

        self.logger.info(f"Context saved to: {file_path}")

    def load_context(self, file_path: Union[str, Path]):
        """
        Load the lightweight context of the model from a JSON file.

        Parameters
        ----------
        file_path : str or Path
            Path to the input JSON file.
        """
        # Load from JSON file
        with open(file_path, "r") as json_file:
            context_data = json.load(json_file)

        # Restore state
        self.min_embeddings_ = np.array(context_data["min_embeddings"])
        self.max_embeddings_ = np.array(context_data["max_embeddings"])
        self.cluster_labels_ = np.array(context_data["cluster_labels"])
        self.embeddings_ = np.array(context_data["embeddings"])

        self.is_fitted_ = True  # Mark as fitted after loading context

        self.logger.info(f"Context loaded from: {file_path}")

    def serialize(self) -> dict:
        """
        Serialize the EMUSESInferenceAPI object to a dictionary.

        Returns
        -------
        state : dict
            Dictionary containing the serialized state of the object.
        """
        state = {
            "config": self.config,
            "is_fitted": self.is_fitted_,
            "min_embeddings": self.min_embeddings_,
            "max_embeddings": self.max_embeddings_,
            "cluster_labels": self.cluster_labels_,
            "embeddings": self.embeddings_,
        }

        return state

    def deserialize(self, state: dict):
        """
        Deserialize and restore the EMUSESInferenceAPI object from a dictionary.

        Parameters
        ----------
        state : dict
            Dictionary containing the serialized state of the object.
        """
        # Restore state
        self.config = state["config"]
        self.is_fitted_ = state["is_fitted"]
        self.min_embeddings_ = state["min_embeddings"]
        self.max_embeddings_ = state["max_embeddings"]
        self.cluster_labels_ = state["cluster_labels"]
        self.embeddings_ = state["embeddings"]

        self.logger.info("State deserialized and restored successfully")

    # =================== SUPERVISED LEARNING API METHODS ===================

    def predict(
        self,
        X: np.ndarray,
        target_tag: str = None,
        ensemble_method: str = "mean",
        confidence_interval: bool = False,
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        """
        Make predictions using the trained supervised learning models.

        This is the core supervised learning method that returns target predictions
        (not UMAP embeddings - use transform() for embeddings).

        Parameters
        ----------
        X : ndarray of shape (n_samples, n_features)
            Input data for prediction.
        target_tag : str, optional
            Specific target to predict. If None, uses first available target.
        ensemble_method : str, default="mean"
            Method for ensemble prediction ("mean" or "median").
        confidence_interval : bool, default=False
            Whether to return confidence intervals from CV fold variance.

        Returns
        -------
        predictions : ndarray of shape (n_samples,)
            Predicted target values.
        confidence : ndarray of shape (n_samples,), optional
            Confidence intervals (only if confidence_interval=True).
        """
        if not self.is_fitted_:
            raise ValueError("Model not fitted. Call fit() first.")

        # Load training state if not already loaded
        if not hasattr(self, "context_") or self.context_ is None:
            raise ValueError(
                "Training context not available. Ensure fit() completed successfully."
            )

        # Validate input
        X = self._validate_input(X, "X")

        # If target_tag not specified, use first available target
        if target_tag is None:
            heavy_refs = getattr(self.context_, "heavy_data_references", {})
            pred_metadata = heavy_refs.get("prediction_results_metadata", {})
            if not pred_metadata:
                raise ValueError("No prediction targets found in trained model")
            target_tag = list(pred_metadata.keys())[0]

        # Apply preprocessing pipeline using lightweight context parameters
        X_processed = self._apply_preprocessing_from_context(X, self.context_)

        # Transform to embedding space using loaded UMAP model
        if not hasattr(self, "models_") or "umap" not in self.models_:
            raise ValueError("UMAP model not found. Ensure model was trained properly.")
        X_embedded = self.models_["umap"].transform(X_processed)

        # Apply coordinate rescaling if needed
        X_embedded = self._apply_preprocessing_from_context(X_embedded, self.context_)

        # Make ensemble predictions using loaded CV fold models
        predictions = self._ensemble_predict_from_models(
            X_embedded,
            target_tag,
            method=ensemble_method,
            return_individual=confidence_interval,
        )

        if confidence_interval:
            ensemble_pred, individual_preds = predictions
            confidence = self._compute_prediction_confidence(individual_preds)
            return ensemble_pred, confidence

        return predictions

    def score(self, X: np.ndarray, y: np.ndarray, target_tag: str = None) -> float:
        """
        Return the coefficient of determination R^2 of the prediction.

        Parameters
        ----------
        X : ndarray of shape (n_samples, n_features)
            Test samples.
        y : ndarray of shape (n_samples,)
            True values for X.
        target_tag : str, optional
            Specific target to evaluate. If None, uses first available target.

        Returns
        -------
        score : float
            R^2 coefficient of determination.
        """
        from sklearn.metrics import r2_score

        # Make predictions
        y_pred = self.predict(X, target_tag=target_tag)

        # Validate targets
        y = self._validate_input(y, "y")

        # Calculate R^2 score
        return r2_score(y, y_pred)

    def fit_predict(self, X: np.ndarray, y: np.ndarray, **kwargs) -> np.ndarray:
        """
        Fit the model and make predictions on the same data.

        Parameters
        ----------
        X : ndarray of shape (n_samples, n_features)
            Input training data.
        y : ndarray of shape (n_samples,)
            Target values.
        **kwargs
            Additional arguments passed to fit().

        Returns
        -------
        predictions : ndarray of shape (n_samples,)
            Predicted target values for X.
        """
        # Fit the model
        self.fit(X, y, **kwargs)

        # Make predictions
        return self.predict(X)

    def get_params(self, deep: bool = True) -> Dict[str, Any]:
        """
        Get parameters for this estimator.

        Parameters
        ----------
        deep : bool, default=True
            If True, will return the parameters for this estimator and
            contained subobjects that are estimators.

        Returns
        -------
        params : dict
            Parameter names mapped to their values.
        """
        params = {}

        # Get basic configuration parameters
        if hasattr(self, "config") and self.config:
            params.update(self.config)

        # Get model directory
        params["model_dir"] = str(self.model_dir)
        params["verbose"] = self.verbose

        # Get pipeline-specific parameters if available
        if hasattr(self, "context_") and self.context_:
            # Extract lightweight parameters from context
            if hasattr(self.context_, "umap_params"):
                params["umap_params"] = self.context_.umap_params
            if hasattr(self.context_, "clustering_params"):
                params["clustering_params"] = self.context_.clustering_params
            if hasattr(self.context_, "prediction_params"):
                params["prediction_params"] = self.context_.prediction_params

        return params

    def set_params(self, **params) -> "EMUSESInferenceAPI":
        """
        Set the parameters of this estimator.

        Parameters
        ----------
        **params : dict
            Estimator parameters.

        Returns
        -------
        self : object
            Estimator instance.
        """
        valid_params = {}

        # Handle basic parameters
        if "model_dir" in params:
            self.model_dir = Path(params["model_dir"])
            valid_params["model_dir"] = params["model_dir"]

        if "verbose" in params:
            self.verbose = params["verbose"]
            valid_params["verbose"] = params["verbose"]

        # Update config parameters
        config_params = {
            k: v for k, v in params.items() if k not in ["model_dir", "verbose"]
        }
        if config_params:
            if not hasattr(self, "config") or self.config is None:
                self.config = {}
            self.config.update(config_params)
            valid_params.update(config_params)

        # Reset fitted state if parameters changed
        if valid_params:
            self.is_fitted_ = False
            if hasattr(self, "context_"):
                delattr(self, "context_")
            if hasattr(self, "models_"):
                delattr(self, "models_")

        return self

    # =================== ENSEMBLE PREDICTION UTILITIES ===================

    def _ensemble_predict_from_models(
        self,
        X: np.ndarray,
        target_tag: str,
        method: str = "mean",
        return_individual: bool = False,
    ) -> Union[np.ndarray, Tuple[np.ndarray, List[np.ndarray]]]:
        """Make ensemble predictions from CV fold models."""
        fold_predictions = []

        # Get prediction models for this target
        if (
            not hasattr(self, "models_")
            or f"prediction_{target_tag}" not in self.models_
        ):
            raise ValueError(f"No prediction models found for target {target_tag}")

        prediction_models = self.models_[f"prediction_{target_tag}"]

        for fold_name, model in prediction_models.items():
            if fold_name.startswith("fold_"):
                pred = model.predict(X)
                fold_predictions.append(pred)

        if len(fold_predictions) == 0:
            raise ValueError(f"No prediction models found for target {target_tag}")

        # Compute ensemble prediction
        if method == "mean":
            ensemble_pred = np.mean(fold_predictions, axis=0)
        elif method == "median":
            ensemble_pred = np.median(fold_predictions, axis=0)
        else:
            raise ValueError(f"Unknown ensemble method: {method}")

        if return_individual:
            return ensemble_pred, fold_predictions
        return ensemble_pred

    def _compute_prediction_confidence(
        self, predictions: List[np.ndarray], confidence_level: float = 0.95
    ) -> np.ndarray:
        """Compute prediction confidence intervals from ensemble variance."""
        from scipy import stats

        pred_std = np.std(predictions, axis=0)
        z_score = stats.norm.ppf(1 - (1 - confidence_level) / 2)
        confidence_intervals = z_score * pred_std
        return confidence_intervals

    # =================== STATE PERSISTENCE METHODS ===================

    def save_context(self, output_dir: Union[str, Path]) -> None:
        """
        Save training context using selective serialization.

        Parameters
        ----------
        output_dir : str or Path
            Directory to save the training state.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not hasattr(self, "context_") or self.context_ is None:
            raise ValueError("No training context to save. Fit the model first.")

        # Extract lightweight context
        lightweight_context = self._extract_lightweight_context(self.context_)

        # Save state
        state = {
            "context_lightweight": lightweight_context,
            "config": self.config if hasattr(self, "config") else {},
            "api_version": "1.0.0",
            "timestamp": str(pd.Timestamp.now()),
        }

        state_file = output_dir / "emuses_training_state.json"
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2, default=str)

    def load_training_state(self, output_dir: Union[str, Path]) -> None:
        """
        Load training state from selective context serialization.

        Parameters
        ----------
        output_dir : str or Path
            Directory containing the saved training state.
        """
        output_dir = Path(output_dir)

        # Load lightweight context and config
        state_file = output_dir / "emuses_training_state.json"
        if not state_file.exists():
            raise FileNotFoundError(f"Training state file not found: {state_file}")

        with open(state_file, "r") as f:
            state = json.load(f)

        # Recreate context and config objects
        self.context_ = type("Context", (), state["context_lightweight"])()
        self.config = state.get("config", {})

        # Load models using context references
        self.models_ = self._load_models_from_context(self.context_, output_dir)

        # Load heavy data arrays from file references if needed
        self.heavy_data_ = self._load_heavy_data_from_context(self.context_, output_dir)

        # Mark as fitted
        self.is_fitted_ = True

    def _validate_input(
        self, X: Union[np.ndarray, pd.DataFrame], name: str = "X"
    ) -> np.ndarray:
        """
        Validate and convert input data to numpy array.

        Parameters
        ----------
        X : array-like
            Input data to validate.
        name : str, optional
            Name of the input for error messages. Default: "X"

        Returns
        -------
        X_validated : ndarray
            Validated input as numpy array.

        Raises
        ------
        ValueError
            If input contains invalid values or has invalid shape.
        """
        # Convert to numpy array if needed
        if hasattr(X, "values"):  # pandas DataFrame/Series
            X = X.values
        elif not isinstance(X, np.ndarray):
            X = np.asarray(X)

        # Basic shape validation
        if X.ndim == 0:
            raise ValueError(f"{name} cannot be a scalar")

        # Ensure 2D for consistency
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        # Check for finite values
        if not np.isfinite(X).all():
            n_infinite = np.isinf(X).sum()
            n_nan = np.isnan(X).sum()
            if n_infinite > 0:
                self.logger.warning(
                    f"{name} contains {n_infinite} infinite values. Replacing with zeros."
                )
            if n_nan > 0:
                self.logger.warning(
                    f"{name} contains {n_nan} NaN values. Replacing with zeros."
                )
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        # Check for empty array
        if X.size == 0:
            raise ValueError(f"{name} is empty")

        self.logger.debug(f"Validated {name} with shape {X.shape}")
        return X
