import numpy as np
import logging
from pathlib import Path

from emuses.pipelines.pipeline_stage import PipelineStage
from emuses.tools.UMAP_utils import train_and_save_umap_and_embeddings, load_umap_model
from emuses.tools.emuses_utils import rescale_embedding

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

    def run(self, context, progress_queue=None):
        logger = logging.getLogger(__name__)
        logger.info("Running UMAP Stage")

        args = self.config.args

        train_features = context.get('train_features')
        test_features = context.get('test_features')

        if getattr(args, 'load_umap', None):
            self.umap_model_path = Path(args.load_umap).resolve()
            self.trained_umap, _ = load_umap_model(self.umap_model_path)
            logger.info(f"Loaded pre-trained UMAP model from: {self.umap_model_path}")
        else:
            # Train UMAP
            self.trained_umap, embeddings, umap_path, embeddings_path, input_matrix_path = (
                train_and_save_umap_and_embeddings(
                train_features,
                self.config.output_folder,
                pref=args.prefix
            ))
            self.umap_model_path = umap_path
            self.embeddings_path = embeddings_path
            logger.info(f"UMAP model saved at: {umap_path}")
            logger.info(f"Embeddings saved at: {embeddings_path}")

        # Load precomputed embeddings if provided
        if getattr(args, 'load_embeddings', None):
            self.embeddings = np.load(args.load_embeddings)
            logger.info(f"Loaded precomputed embeddings from: {args.load_embeddings}")
        else:
            self.embeddings = self.trained_umap.transform(train_features)

        # Rescale embeddings
        self.min_embeddings = self.embeddings.min(axis=0)
        self.max_embeddings = self.embeddings.max(axis=0)
        self.embeddings = rescale_embedding(
            self.embeddings,
            preset_min=self.min_embeddings,
            preset_max=self.max_embeddings
        )

        # Process test embeddings if test set exists
        if test_features is not None:
            self.test_embeddings = self.trained_umap.transform(test_features)
            self.test_embeddings = rescale_embedding(
                self.test_embeddings,
                preset_min=self.min_embeddings,
                preset_max=self.max_embeddings
            )
            # Save test embeddings
            self.test_embeddings_path = self.config.output_folder / 'test_embeddings.npy'
            np.save(self.test_embeddings_path, self.test_embeddings)
            logger.info(f"Test embeddings saved at: {self.test_embeddings_path}")

        # Update context with embeddings
        context.update({
            'embeddings': self.embeddings,
            'test_embeddings': self.test_embeddings,
            'trained_umap': self.trained_umap,
            'min_embeddings': self.min_embeddings,
            'max_embeddings': self.max_embeddings
        })
