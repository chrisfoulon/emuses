# pipelines/heatmap_stage.py

import numpy as np
import logging

from emuses.pipelines.pipeline_stage import PipelineStage
from emuses.tools.correlation_maps_utils import run_heatmap_analysis
from emuses.tools.stats_utils import fwhm_to_sigma  # Import the conversion function


class HeatmapStage(PipelineStage):
    def __init__(self, config, output_format_info):
        super().__init__(config)
        self.output_format_info = output_format_info

    def run(self, context, progress_queue=None):
        logger = logging.getLogger(__name__)
        logger.info("Running Heatmap Stage")

        args = self.config.args

        # Get embeddings and other required data from context
        embeddings = context.get('embeddings')
        clusterer = context.get('clusterer')
        cluster_labels = context.get('cluster_labels')
        train_labels = context.get('train_labels')
        train_features = context.get('train_features')

        if train_features is None:
            raise ValueError("Train features are required for heatmap analysis.")

        # Prepare scores vectors dict
        score_vectors_dict = None
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
        # add score_vectors_dict to the context
        context['score_vectors_dict'] = score_vectors_dict

        # Handle sigma and fwhm
        sigma = self.config.heatmap_params.get('sigma', None)
        fwhm = self.config.heatmap_params.get('fwhm', None)

        if sigma is None and fwhm is not None:
            sigma = fwhm_to_sigma(fwhm)
            logger.info(f"Converted FWHM {fwhm} to sigma {sigma}")
        elif sigma is None and fwhm is None:
            sigma = None
            logger.info("No sigma or FWHM provided; proceeding without smoothing.")

        # Decide whether to display plots
        show_plots = getattr(args, 'show_plots', False)
        context['show_plots'] = show_plots  # Store in context for use in functions
        generate_plots = True  # Generate plots if we are showing them

        correlation_method = self.config.heatmap_params.get('correlation_method', 'pearson')

        # Run heatmap analysis
        plots = run_heatmap_analysis(
            embeddings=embeddings,
            scores_vectors_dict=scores_vectors_dict,
            input_matrix=train_features,
            output_folder=self.config.output_folder,
            output_format_info=self.output_format_info,
            clusterer=clusterer,
            cluster_labels=cluster_labels,
            grid_size=100,
            sigma=sigma,
            correlation_threshold=0.3,
            highlight_points=True,
            show_plots=show_plots,  # For immediate display (e.g., plt.show())
            generate_plots=generate_plots,  # For returning plots to display in Streamlit
            correlation_method=correlation_method,
        )
        logger.info("Heatmap analysis completed.")

        # Store plots and representative data in context for later use (e.g., in Streamlit)
        context['heatmap_plots'] = plots

