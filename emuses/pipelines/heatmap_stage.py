# pipelines/heatmap_stage.py
#
# import numpy as np
# import logging
#
# from emuses.pipelines.pipeline_stage import PipelineStage
# from emuses.tools.correlation_maps_utils import run_heatmap_analysis
# from emuses.tools.stats_utils import fwhm_to_sigma  # Import the conversion function
# from emuses.tools.visualisation import plot_clustering_interactive_with_hover
#
#
# class HeatmapStage(PipelineStage):
#     def __init__(self, config, output_format_info):
#         super().__init__(config)
#         self.output_format_info = output_format_info
#
#     def run(self, context, progress_queue=None):
#         logger = logging.getLogger(__name__)
#         logger.info("Running Heatmap Stage")
#
#         args = self.config.args
#
#         # Get embeddings and other required data from context
#         embeddings = context.get('embeddings')
#         clusterer = context.get('clusterer')
#         cluster_labels = context.get('cluster_labels')
#         train_labels = context.get('train_labels')
#         train_features = context.get('train_features')
#
#         if train_features is None:
#             raise ValueError("Train features are required for heatmap analysis.")
#
#         # Prepare scores vectors dict
#         score_vectors_dict = None
#         if getattr(args, 'classification', False):
#             unique_labels = np.unique(train_labels)
#             scores_vectors_dict = {
#                 str(score_tag): (train_labels == score_tag).astype(int)
#                 for score_tag in unique_labels
#             }
#         else:
#             if train_labels.ndim == 1:
#                 scores_vectors_dict = {'score': train_labels}
#             else:
#                 scores_vectors_dict = {
#                     f"score_{i}": train_labels[:, i]
#                     for i in range(train_labels.shape[1])
#                 }
#         # add score_vectors_dict to the context
#         context['score_vectors_dict'] = score_vectors_dict
#
#         # Handle sigma and fwhm
#         sigma = self.config.heatmap_params.get('sigma', None)
#         if sigma is None:
#             # sigma = np.geomspace(0.05, 0.3, num=6)
#             sigma = np.linspace(0.01, 0.2, num=8)
#         fwhm = self.config.heatmap_params.get('fwhm', None)
#
#         if sigma is None and fwhm is not None:
#             sigma = fwhm_to_sigma(fwhm)
#             logger.info(f"Converted FWHM {fwhm} to sigma {sigma}")
#         elif sigma is None and fwhm is None:
#             sigma = None
#             logger.info("No sigma or FWHM provided; proceeding without smoothing.")
#
#         # Decide whether to display plots
#         show_plots = getattr(args, 'show_plots', False)
#         context['show_plots'] = show_plots  # Store in context for use in functions
#         generate_plots = True  # Generate plots if we are showing them
#
#         correlation_method = self.config.heatmap_params.get('correlation_method', 'pearson')
#
#         # --- Interactive Clustering Plot Section ---
#         # Now, create an interactive plot of the embeddings colored by scores.
#         # If classification: use train_labels directly; else, iterate over score keys.
#         if getattr(args, 'interactive_plot', False):
#             from pathlib import Path
#             # Ensure the output folder for interactive plots exists.
#             interactive_folder = Path(self.config.output_folder) / "interactive_plots"
#             interactive_folder.mkdir(exist_ok=True)
#             if getattr(args, 'classification', False):
#                 # Classification: one plot using train_labels.
#                 interactive_path = interactive_folder / "interactive_clustering_classification.html"
#                 fig = plot_clustering_interactive_with_hover(
#                     embeddings, train_labels,
#                     output_path=interactive_path,
#                     show_plot=False,
#                     return_plot=True
#                 )
#                 logger.info(f"Interactive clustering plot (classification) saved at: {interactive_path}")
#                 context['interactive_clustering_plot'] = fig
#             else:
#                 # Non-classification: one plot per score key.
#                 interactive_plots = {}
#                 for key, score_vec in scores_vectors_dict.items():
#                     interactive_path = interactive_folder / f"interactive_clustering_{key}.html"
#                     fig = plot_clustering_interactive_with_hover(
#                         embeddings, score_vec,
#                         output_path=interactive_path,
#                         show_plot=False,
#                         return_plot=True
#                     )
#                     logger.info(f"Interactive clustering plot for score {key} saved at: {interactive_path}")
#                     interactive_plots[key] = fig
#                 context['interactive_clustering_plots'] = interactive_plots
#
#         # Run heatmap analysis
#         plots = run_heatmap_analysis(
#             embeddings=embeddings,
#             scores_vectors_dict=scores_vectors_dict,
#             input_matrix=train_features,
#             output_folder=self.config.output_folder,
#             output_format_info=self.output_format_info,
#             clusterer=clusterer,
#             cluster_labels=cluster_labels,
#             input_type=context['dataset_type'],
#             grid_size=100,
#             sigma=sigma,
#             correlation_threshold=0.3,
#             highlight_points=True,
#             show_plots=show_plots,  # For immediate display (e.g., plt.show())
#             generate_plots=generate_plots,  # For returning plots to display in Streamlit
#             correlation_method=correlation_method,
#         )
#         logger.info("Heatmap analysis completed.")
#
#         # Store plots and representative data in context for later use (e.g., in Streamlit)
#         context['heatmap_plots'] = plots
#

# pipelines/heatmap_stage.py
import numpy as np
import logging
from pathlib import Path
import pandas as pd

from emuses.pipelines.pipeline_stage import PipelineStage
from emuses.tools.stats_utils import fwhm_to_sigma  # if needed for conversion
from emuses.tools.kernel_regression_utils import run_kernel_heatmap_analysis, ensemble_predict
from emuses.tools.visualisation import plot_clustering_interactive_with_hover, plot_clustering
from sklearn.metrics import accuracy_score, confusion_matrix, roc_auc_score, f1_score, precision_score, recall_score
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error


class HeatmapStage(PipelineStage):
    def __init__(self, config, output_format_info):
        super().__init__(config)
        self.output_format_info = output_format_info

    def run(self, context, progress_queue=None):
        logger = logging.getLogger(__name__)
        logger.info("Running Heatmap Stage (kernel regression version)")

        args = self.config.args

        # Get required data from context
        # --- New: Use labelled training data for heatmap analysis if available ---
        if 'train_labelled_embeddings' in context and 'train_labelled_scores' in context:
            embeddings = context['train_labelled_embeddings']
            train_labels = context['train_labelled_scores']
            train_features = context.get('train_labelled_matrix')
            logger.info("Using labelled training data for heatmap analysis.")
        else:
            # Fallback: use the unsupervised splits (if no separate labelled dataset was provided)
            embeddings = context.get('embeddings')
            train_labels = context.get('train_labels')
            train_features = context.get('train_features')

        clusterer = context.get('clusterer')  # might be None
        cluster_labels = context.get('cluster_labels')  # might be None
        dataset_type = context.get('dataset_type', 'image')

        if train_features is None:
            raise ValueError("Train features are required for heatmap analysis.")

        # Prepare the scores vectors dictionary
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
        context['score_vectors_dict'] = scores_vectors_dict

        # Set candidate sigma values for the kernel regressor.
        sigma = self.config.heatmap_params.get('sigma', None)
        if sigma is None:
            sigma = np.linspace(0.01, 0.2, num=8)
        else:
            if not isinstance(sigma, (list, np.ndarray)):
                sigma = np.array([sigma])

        # Optionally, if fwhm is provided, convert it.
        fwhm = self.config.heatmap_params.get('fwhm', None)
        if fwhm is not None and sigma is None:
            sigma = fwhm_to_sigma(fwhm)
            logger.info(f"Converted FWHM {fwhm} to sigma {sigma}")

        # Decide whether to display plots.
        show_plots = getattr(args, 'show_plots', False)
        context['show_plots'] = show_plots
        generate_plots = True

        # --- Interactive Clustering Plot Section ---
        if getattr(args, 'interactive_plot', False):
            interactive_folder = Path(self.config.output_folder) / "interactive_plots"
            interactive_folder.mkdir(exist_ok=True)
            if getattr(args, 'classification', False):
                interactive_path = interactive_folder / "interactive_clustering_classification.html"
                fig = plot_clustering_interactive_with_hover(
                    embeddings, train_labels,
                    output_path=interactive_path,
                    show_plot=False,
                    return_plot=True
                )
                logger.info(f"Interactive clustering plot (classification) saved at: {interactive_path}")
                context['interactive_clustering_plot'] = fig
            else:
                interactive_plots = {}
                for key, score_vec in scores_vectors_dict.items():
                    interactive_path = interactive_folder / f"interactive_clustering_{key}.html"
                    fig = plot_clustering_interactive_with_hover(
                        embeddings, score_vec,
                        output_path=interactive_path,
                        show_plot=False,
                        return_plot=True
                    )
                    logger.info(f"Interactive clustering plot for score {key} saved at: {interactive_path}")
                    interactive_plots[key] = fig
                context['interactive_clustering_plots'] = interactive_plots

        # Run the kernel regression–based heatmap analysis.
        heatmap_dict, cv_performance_all = run_kernel_heatmap_analysis(
            embeddings=embeddings,
            scores_vectors_dict=scores_vectors_dict,
            input_matrix=train_features,
            output_folder=self.config.output_folder,
            grid_size=100,
            sigma_range=sigma,
            threshold=0.5,
            uncertainty_penalty=0.5,
            input_type=context['dataset_type'],
            classification=getattr(args, 'classification', False),
            cluster_labels=cluster_labels,
            effect_size_test='mann-whitney',
            highlight_points=True,
            show_plots=show_plots,
            generate_plots=generate_plots,
            output_format_info=self.output_format_info
        )
        logger.info("Kernel regression heatmap analysis completed.")

        # Store heatmap results in the context.
        context['heatmap_plots'] = heatmap_dict
        context['cv_performance_all'] = cv_performance_all
