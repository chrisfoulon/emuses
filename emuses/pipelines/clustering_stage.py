import numpy as np
import logging

from emuses.pipelines.pipeline_stage import PipelineStage
from emuses.tools.clustering_utils import load_hdbscan_model, save_hdbscan_model, cluster_coordinates
from bcblib.tools.general_utils import save_json
from emuses.tools.visualisation import plot_clustering_interactive_with_hover

class ClusteringStage(PipelineStage):
    def __init__(self, config):
        super().__init__(config)
        self.clusterer = None
        self.cluster_labels = None
        self.best_params = None

    def run(self, context, progress_queue=None):
        logger = logging.getLogger(__name__)
        logger.info("Running Clustering Stage")

        args = self.config.args

        embeddings = context.get('embeddings')
        if embeddings is None:
            if getattr(args, 'load_embeddings', None):
                embeddings = np.load(args.load_embeddings)
                logger.info(f"Loaded embeddings from: {args.load_embeddings}")
                context['embeddings'] = embeddings
            else:
                raise ValueError("Embeddings are required for clustering. Provide embeddings or run UMAP stage.")

        if getattr(args, 'load_hdbscan', None):
            self.clusterer = load_hdbscan_model(args.load_hdbscan)
            self.cluster_labels = self.clusterer.labels_
            logger.info(f"Loaded pre-trained HDBSCAN model from: {args.load_hdbscan}")
        else:
            min_cluster_size = self.config.clustering_params.get('min_cluster_size', 5)
            self.clusterer, self.cluster_labels, self.best_params = cluster_coordinates(
                embeddings,
            )
            # Save clustering labels
            save_json(self.config.output_folder / 'cluster_labels.json', self.cluster_labels.tolist())
            # Save the best parameters
            save_json(self.config.output_folder / 'best_params.json', self.best_params)
            # Save the HDBSCAN model
            save_hdbscan_model(self.clusterer, self.config.output_folder, prefix=args.prefix)
            logger.info("Clustering completed and saved.")

        if getattr(args, 'interactive_plot', False):
            clustering_plot = plot_clustering_interactive_with_hover(
                embeddings,
                self.cluster_labels,
                output_path=self.config.output_folder / 'clustering_plot.html',
                show_plot=False,
                return_plot=True
            )
            # Send the plot via the queue if available
            if progress_queue:
                progress_queue.put(('plot', 'Clustering Plot', clustering_plot))
            else:
                # Store the plot in context for later use
                context['clustering_plot'] = clustering_plot

        # Update context with clustering results
        context.update({
            'clusterer': self.clusterer,
            'cluster_labels': self.cluster_labels
        })
