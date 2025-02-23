import numpy as np
import logging
from pathlib import Path

from emuses.pipelines.pipeline_stage import PipelineStage
from emuses.tools.UMAP_utils import (
    train_and_save_umap_optim_with_nested_clustering,
    load_umap_model
)
from emuses.tools.clustering_utils import load_hdbscan_model
from emuses.tools.emuses_utils import rescale_embedding
# Import the default optimization dictionary from your configuration module.
from emuses.config.optim_configs import optim_dict_default, optim_dict_test


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
        logger = logging.getLogger(__name__)
        logger.info("Running UMAP Stage")

        args = self.config.args

        train_features = context.get('train_features')
        test_features = context.get('test_features')

        # First, check if we are loading a pre-trained UMAP model.
        if getattr(args, 'load_umap', None):
            self.umap_model_path = Path(args.load_umap).resolve()
            self.trained_umap, _ = load_umap_model(self.umap_model_path)
            logger.info(f"Loaded pre-trained UMAP model from: {self.umap_model_path}")
        else:
            # Use the provided optimization dictionary or fallback to default.
            if 'optim_dict' not in context or not context['optim_dict']:
                optim_dict = optim_dict_default  # or optim_dict_default as needed
                # optim_dict = optim_dict_test  # or optim_dict_default as needed
            else:
                optim_dict = context['optim_dict']

            # Run nested optimization for UMAP + HDBSCAN.
            (self.trained_umap,
             embeddings,
             umap_path,
             embeddings_path,
             best_clusterer,
             best_labels,
             cluster_model_path,
             cluster_labels_path,
             input_matrix_path) = train_and_save_umap_optim_with_nested_clustering(
                    input_matrix=train_features,
                    output_folder=self.config.output_folder,
                    optim_dict=optim_dict,
                    n_trials=100,
                    n_inner_trials=100,  # Adjust as needed
                    pref=args.prefix,
                    random_state=getattr(args, 'random_state', None)
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
        if getattr(args, 'load_clusterer', None):
            self.cluster_model_path = Path(args.load_clusterer).resolve()
            try:
                self.best_clusterer = load_hdbscan_model(self.cluster_model_path)
                logger.info(f"Loaded pre-trained clusterer from: {self.cluster_model_path}")
            except Exception as e:
                logger.error(f"Failed to load clusterer from {self.cluster_model_path}: {e}")
        if getattr(args, 'load_cluster_labels', None):
            self.cluster_labels_path = Path(args.load_cluster_labels).resolve()
            try:
                self.cluster_labels = np.load(self.cluster_labels_path)
                logger.info(f"Loaded pre-trained cluster labels from: {self.cluster_labels_path}")
            except Exception as e:
                logger.error(f"Failed to load cluster labels from {self.cluster_labels_path}: {e}")

        # Load precomputed embeddings if provided.
        if getattr(args, 'load_embeddings', None):
            self.embeddings = np.load(args.load_embeddings)
            logger.info(f"Loaded precomputed embeddings from: {args.load_embeddings}")
        else:
            self.embeddings = self.trained_umap.transform(train_features)

        # Rescale embeddings.
        self.min_embeddings = self.embeddings.min(axis=0)
        self.max_embeddings = self.embeddings.max(axis=0)
        self.embeddings = rescale_embedding(
            self.embeddings,
            preset_min=self.min_embeddings,
            preset_max=self.max_embeddings
        )

        # Process test embeddings if a test set exists.
        if test_features is not None:
            self.test_embeddings = self.trained_umap.transform(test_features)
            self.test_embeddings = rescale_embedding(
                self.test_embeddings,
                preset_min=self.min_embeddings,
                preset_max=self.max_embeddings
            )
            # Save test embeddings.
            self.test_embeddings_path = self.config.output_folder / 'test_embeddings.npy'
            np.save(self.test_embeddings_path, self.test_embeddings)
            logger.info(f"Test embeddings saved at: {self.test_embeddings_path}")

        # Update context with UMAP and clustering outputs.
        # Use keys that downstream stages (e.g., HeatmapStage) expect.
        context.update({
            'embeddings': self.embeddings,
            'test_embeddings': self.test_embeddings,
            'trained_umap': self.trained_umap,
            'min_embeddings': self.min_embeddings,
            'max_embeddings': self.max_embeddings,
            'clusterer': self.best_clusterer,  # Using 'clusterer' as the key
            'cluster_labels': self.cluster_labels,
            'cluster_model_path': self.cluster_model_path,
            'cluster_labels_path': self.cluster_labels_path
        })
