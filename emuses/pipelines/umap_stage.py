import json
import logging
from pathlib import Path

import numpy as np

# Import the default optimization dictionary from your configuration module.
from emuses.config.optim_configs import load_optim_dict, optim_dict_default
from emuses.observability import (get_logger, track_optimization_trial,
                                  track_scientific_operation)
from emuses.pipelines.pipeline_stage import PipelineStage
from emuses.tools.clustering_utils import load_hdbscan_model
from emuses.tools.emuses_utils import rescale_embedding
from emuses.tools.UMAP_utils import (
    load_umap_model, train_and_save_umap_optim_with_nested_clustering)


class UMAPStage(PipelineStage):
    def __init__(self, config):
        super().__init__(config)
        self.trained_umap = None
        self.embeddings = None
        self.test_embeddings = None
        self.umap_model_path = None
        self.embeddings_path = None
        self.test_embeddings_path = None
        self.min_embeddings = None
        self.max_embeddings = None
        # Clustering-related attributes:
        self.best_clusterer = None
        self.cluster_labels = None
        self.cluster_model_path = None
        self.cluster_labels_path = None

    def run(self, context, progress_queue=None):
        logger = get_logger(__name__)

        # Get user context for observability
        user_id = context.get("user_id")
        dataset_name = context.get("dataset_name", "unknown")

        with track_scientific_operation(
            "umap_optimization",
            user_id=user_id,
            additional_attributes={"dataset": dataset_name},
        ) as obs_ctx:
            logger.info("Running UMAP Stage", user_id=user_id, dataset=dataset_name)

            # Get component-specific seeds from context
            random_seeds = context.get("random_seeds", {})
            umap_seed = random_seeds.get("umap_seed", 42)
            clustering_seed = random_seeds.get("clustering_seed", 42)
            logger.info(
                f"Using random seeds - UMAP: {umap_seed}, Clustering: {clustering_seed}"
            )

            # Add optimization context to observability
            obs_ctx.set_attribute("umap_seed", umap_seed)
            obs_ctx.set_attribute("clustering_seed", clustering_seed)

            # Use new naming convention only
            train_features = context.get("embedding_train_features")
            test_features = context.get("embedding_test_features")
            # train_indices = context.get("embedding_train_indices")  # Unused variable

            if train_features is not None:
                obs_ctx.set_attribute("train_samples", len(train_features))
            if test_features is not None:
                obs_ctx.set_attribute("test_samples", len(test_features))

        # Determine file paths based on output folder and prefix
        prefix = self.config.prefix if hasattr(self.config, "prefix") else ""
        umap_model_file = self.config.output_folder / f"{prefix}best_umap_model.joblib"
        embeddings_file = self.config.output_folder / f"{prefix}embeddings.npy"
        cluster_model_file = self.config.output_folder / f"{prefix}hdbscan_model.joblib"
        cluster_labels_file = self.config.output_folder / f"{prefix}cluster_labels.npy"

        # If output files exist, load them and skip training.
        if (
            umap_model_file.exists()
            and embeddings_file.exists()
            and cluster_model_file.exists()
            and cluster_labels_file.exists()
        ):
            logger.info(
                f"Found existing output files. Loading UMAP model from: {umap_model_file}"
            )
            self.trained_umap, _ = load_umap_model(umap_model_file)
            self.embeddings = np.load(embeddings_file)
            self.best_clusterer, _ = load_hdbscan_model(
                cluster_model_file.parent, model_name="hdbscan_model"
            )
            self.cluster_labels = np.load(cluster_labels_file)
        else:
            # Load or generate the optimization dictionary.
            if "optim_dict" in context and context["optim_dict"]:
                optim_dict = context["optim_dict"]
            elif "cli_args" in context and "optim_dict" in context["cli_args"]:
                optim_dict_name = context["cli_args"]["optim_dict"]
                try:
                    optim_dict = load_optim_dict(optim_dict_name)
                except Exception as e:
                    logger.error(
                        f"Error loading optim_dict '{optim_dict_name}': {e}. Falling back to default."
                    )
                    optim_dict = optim_dict_default
            else:
                optim_dict = optim_dict_default  # Run nested optimization for UMAP + HDBSCAN.            # Get HDBSCAN reproducibility parameters from config
            approx_min_span_tree = getattr(
                self.config, "hdbscan_approx_min_span_tree", True
            )
            core_dist_n_jobs = getattr(self.config, "hdbscan_core_dist_n_jobs", -1)

            (
                self.trained_umap,
                embeddings,
                umap_path,
                embeddings_path,
                best_clusterer,
                best_labels,
                cluster_model_path,
                cluster_labels_path,
                input_matrix_path,
            ) = train_and_save_umap_optim_with_nested_clustering(
                input_matrix=train_features,
                output_folder=self.config.output_folder,
                optim_dict=optim_dict,
                n_trials=getattr(self.config, "umap_trials", 50),
                n_inner_trials=getattr(self.config, "hdbscan_trials", 20),
                pref=self.config.prefix,
                n_jobs=(
                    self.config.umap_jobs if self.config.umap_jobs is not None else 1
                ),
                inner_n_jobs=(
                    self.config.hdbscan_jobs
                    if self.config.hdbscan_jobs is not None
                    else 1
                ),
                random_state=umap_seed,
                clusterer_random_state=clustering_seed,
                approx_min_span_tree=approx_min_span_tree,
                core_dist_n_jobs=core_dist_n_jobs,
            )
            self.embeddings = embeddings
            logger.info(
                f"UMAP model saved at: {umap_path} and embeddings saved at: {embeddings_path}"
            )

            self.umap_model_path = umap_path
            self.embeddings_path = embeddings_path
            self.best_clusterer = best_clusterer
            self.cluster_labels = best_labels
            self.cluster_model_path = cluster_model_path
            self.cluster_labels_path = cluster_labels_path

            logger.info(f"UMAP model saved at: {umap_path}")
            logger.info(f"Embeddings saved at: {embeddings_path}")
            logger.info(f"HDBSCAN model saved at: {cluster_model_path}")
            logger.info(f"Cluster labels saved at: {cluster_labels_path}")

        # Check if a pre-saved clustering result should be loaded.
        if getattr(self.config, "load_clusterer", None):
            self.cluster_model_path = Path(self.config.load_clusterer).resolve()
            try:
                self.best_clusterer, _ = load_hdbscan_model(
                    self.cluster_model_path.parent, model_name="hdbscan_model"
                )
                logger.info(
                    f"Loaded pre-trained clusterer from: {self.cluster_model_path}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to load clusterer from {self.cluster_model_path}: {e}"
                )
        if getattr(self.config, "load_cluster_labels", None):
            self.cluster_labels_path = Path(self.config.load_cluster_labels).resolve()
            try:
                self.cluster_labels = np.load(self.cluster_labels_path)
                logger.info(
                    f"Loaded pre-trained cluster labels from: {self.cluster_labels_path}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to load cluster labels from {self.cluster_labels_path}: {e}"
                )

        # Load precomputed embeddings if provided.
        if getattr(self.config, "load_embeddings", None):
            self.embeddings = np.load(self.config.load_embeddings)
            logger.info(
                f"Loaded precomputed embeddings from: {self.config.load_embeddings}"
            )
        else:
            self.embeddings = self.trained_umap.transform(train_features)

        # Rescale embeddings.
        self.min_embeddings = self.embeddings.min(axis=0)
        self.max_embeddings = self.embeddings.max(axis=0)
        
        # Save embedding scaling parameters for inference
        embedding_scaling = {
            'min_embeddings': self.min_embeddings.tolist(),
            'max_embeddings': self.max_embeddings.tolist() 
        }
        scaling_file = self.config.output_folder / "embedding_scaling.json"
        with open(scaling_file, 'w') as f:
            json.dump(embedding_scaling, f)
        logger.info(f"Saved embedding scaling parameters to {scaling_file}")
        
        self.embeddings = rescale_embedding(
            self.embeddings,
            preset_min=self.min_embeddings,
            preset_max=self.max_embeddings,
        )

        # Process test embeddings if a test set exists.
        if test_features is not None:
            self.test_embeddings = self.trained_umap.transform(test_features)
            self.test_embeddings = rescale_embedding(
                self.test_embeddings,
                preset_min=self.min_embeddings,
                preset_max=self.max_embeddings,
            )
            # Save test embeddings.
            self.test_embeddings_path = (
                self.config.output_folder / "test_embeddings.npy"
            )
            np.save(self.test_embeddings_path, self.test_embeddings)
            logger.info(f"Test embeddings saved at: {self.test_embeddings_path}")

        # Process labeled data for prediction if available
        prediction_train_features = context.get("prediction_train_features")
        prediction_test_features = context.get("prediction_test_features")

        # Transform prediction data through UMAP
        if prediction_train_features is not None:
            prediction_train_coords = self.trained_umap.transform(
                prediction_train_features
            )
            prediction_train_coords = rescale_embedding(
                prediction_train_coords,
                preset_min=self.min_embeddings,
                preset_max=self.max_embeddings,
            )
            logger.info(
                "Transformed and rescaled prediction training data using the UMAP model."
            )
            context["prediction_train_coords"] = prediction_train_coords

        if prediction_test_features is not None:
            prediction_test_coords = self.trained_umap.transform(
                prediction_test_features
            )
            prediction_test_coords = rescale_embedding(
                prediction_test_coords,
                preset_min=self.min_embeddings,
                preset_max=self.max_embeddings,
            )
            logger.info(
                "Transformed and rescaled prediction test data using the UMAP model."
            )
            context["prediction_test_coords"] = prediction_test_coords

        # Update context with UMAP and clustering outputs using new naming convention
        context.update(
            {
                # Standardized naming for embedding data
                "embedding_train_coords": self.embeddings,
                "embedding_test_coords": self.test_embeddings,
                "embedding_train_umap_model": self.trained_umap,
                # Standardized naming for clustering data
                "embedding_train_clusterer": self.best_clusterer,
                "embedding_train_cluster_labels": self.cluster_labels,
                # Standardized naming for scaling information
                "embedding_train_min_coords": self.min_embeddings,
                "embedding_train_max_coords": self.max_embeddings,
                # File paths - keep naming as is since these are implementation details
                "cluster_model_path": self.cluster_model_path,
                "cluster_labels_path": self.cluster_labels_path,
            }
        )
