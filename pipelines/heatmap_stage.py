# pipelines/heatmap_stage.py

import numpy as np
import logging

from pipelines.pipeline_stage import PipelineStage
from tools.correlation_maps_utils import run_heatmap_analysis
from tools.clustering_utils import load_hdbscan_model
from tools.stats_utils import fwhm_to_sigma  # Import the conversion function

class HeatmapStage(PipelineStage):
    def __init__(self, config, output_format_info):
        super().__init__(config)
        self.output_format_info = output_format_info

    def run(self, context):
        logger = logging.getLogger(__name__)
        logger.info("Running Heatmap Stage")

        args = self.config.args

        embeddings = context.get('embeddings')
        if embeddings is None:
            if getattr(args, 'embeddings', None):
                embeddings = np.load(args.embeddings)
                logger.info(f"Loaded embeddings from: {args.embeddings}")
                context['embeddings'] = embeddings
            else:
                raise ValueError("Embeddings are required for heatmap analysis.")

        clusterer = context.get('clusterer')
        cluster_labels = context.get('cluster_labels')
        if clusterer is None or cluster_labels is None:
            if getattr(args, 'load_hdbscan', None):
                clusterer = load_hdbscan_model(args.load_hdbscan)
                cluster_labels = clusterer.labels_
                logger.info(f"Loaded pre-trained HDBSCAN model from: {args.load_hdbscan}")
                context['clusterer'] = clusterer
                context['cluster_labels'] = cluster_labels
            else:
                raise ValueError("Clustering results are required for heatmap analysis.")

        train_labels = context.get('train_labels')
        if train_labels is None:
            raise ValueError("Train labels are required for heatmap analysis.")

        train_features = context.get('train_features')
        if train_features is None:
            raise ValueError("Train features are required for heatmap analysis.")

        # Prepare scores vectors dict
        if getattr(args, 'classification', False):
            unique_labels = np.unique(train_labels)
            scores_vectors_dict = {
                str(score_tag): (train_labels == score_tag).astype(int)
                for score_tag in unique_labels
            }
        else:
            if train_labels.ndim == 1:
                scores_vectors_dict = {'score': train_labels}
            else:
                scores_vectors_dict = {
                    f"score_{i}": train_labels[:, i]
                    for i in range(train_labels.shape[1])
                }

        # Handle sigma and fwhm
        sigma = self.config.heatmap_params.get('sigma', None)
        fwhm = self.config.heatmap_params.get('fwhm', None)

        if sigma is None and fwhm is not None:
            sigma = fwhm_to_sigma(fwhm)
            logger.info(f"Converted FWHM {fwhm} to sigma {sigma}")
        elif sigma is None and fwhm is None:
            # Use a default sigma value or set to None
            sigma = None
            logger.info("No sigma or FWHM provided; proceeding without smoothing.")
        # Decide whether to display plots
        show_plots = getattr(args, 'show_plots', False)
        context['show_plots'] = show_plots  # Store in context for use in functions

            # Run heatmap analysis
        plots = run_heatmap_analysis(
            embeddings=embeddings,
            scores_vectors_dict=scores_vectors_dict,
            input_matrix=train_features,
            output_folder=self.config.output_folder,
            clusterer=clusterer,
            cluster_labels=cluster_labels,
            output_format_info=self.output_format_info,
            grid_size=100,
            sigma=sigma,
            correlation_threshold=0.3,
            highlight_points=True
        )
        logger.info("Heatmap analysis completed.")
        # Store plots in context for later use (e.g., in Streamlit)
        context['heatmap_plots'] = plots
        logger.info(f"Stored heatmap_plots in context: {context['heatmap_plots']}")
