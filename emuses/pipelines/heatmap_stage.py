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
        embeddings = context.get('embeddings')
        clusterer = context.get('clusterer')  # might be None
        cluster_labels = context.get('cluster_labels')  # might be None
        train_labels = context.get('train_labels')
        train_features = context.get('train_features')
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
        heatmaps = run_kernel_heatmap_analysis(
            embeddings=embeddings,
            scores_vectors_dict=scores_vectors_dict,
            input_matrix=train_features,
            output_folder=self.config.output_folder,
            grid_size=100,
            sigma_range=sigma,
            threshold=0.5,
            uncertainty_penalty=0.5,
            input_type=context['dataset_type'],
            cluster_labels=cluster_labels,
            effect_size_test='mann-whitney',
            highlight_points=True,
            show_plots=show_plots,
            generate_plots=generate_plots,
            output_format_info=self.output_format_info
        )
        logger.info("Kernel regression heatmap analysis completed.")

        # Compute out-of-sample performance metrics using the ensemble CV models.
        performance_results = []
        if getattr(args, 'classification', False):
            # Classification branch: use binary metrics.
            for score_tag, heatmap_data in heatmaps.items():
                models = heatmap_data.get('models')
                # Create binary targets based on the score tag.
                try:
                    target = int(score_tag)
                except:
                    target = 1
                y_true = (train_labels == target).astype(int).ravel()
                mean_train_pred, std_train_pred = ensemble_predict(models, embeddings)
                y_pred = (mean_train_pred >= 0.5).astype(int).ravel()
                acc = accuracy_score(y_true, y_pred)
                try:
                    roc_auc = roc_auc_score(y_true, mean_train_pred)
                except Exception as e:
                    roc_auc = None
                f1 = f1_score(y_true, y_pred)
                prec = precision_score(y_true, y_pred)
                rec = recall_score(y_true, y_pred)
                mean_uncertainty = np.mean(std_train_pred)
                std_uncertainty = np.std(std_train_pred)
                cm = confusion_matrix(y_true, y_pred).tolist()
                performance_results.append({
                    'score_tag': score_tag,
                    'accuracy': acc,
                    'roc_auc': roc_auc,
                    'f1_score': f1,
                    'precision': prec,
                    'recall': rec,
                    'mean_uncertainty': mean_uncertainty,
                    'std_uncertainty': std_uncertainty,
                    'confusion_matrix': str(cm)
                })
                logger.info(
                    f"Performance for score tag {score_tag}: Accuracy={acc:.3f}, ROC AUC={roc_auc}, F1={f1:.3f}")
        else:
            # Regression branch: use continuous targets and predictions.
            y_true_cont = train_labels.ravel()  # continuous targets
            # Check for length mismatch between y_true_cont and embeddings.
            if len(y_true_cont) != len(embeddings):
                logger.warning(
                    f"Mismatch in number of training labels ({len(y_true_cont)}) and embeddings ({len(embeddings)}); trimming labels to match embeddings.")
                y_true_cont = y_true_cont[:len(embeddings)]
            for score_tag, heatmap_data in heatmaps.items():
                models = heatmap_data.get('models')
                mean_train_pred, std_train_pred = ensemble_predict(models, embeddings)
                y_pred_cont = mean_train_pred  # continuous predictions
                r2 = r2_score(y_true_cont, y_pred_cont)
                mse = mean_squared_error(y_true_cont, y_pred_cont)
                mae = mean_absolute_error(y_true_cont, y_pred_cont)
                target_range = np.max(y_true_cont) - np.min(y_true_cont)
                normalized_mse = (mse / (target_range ** 2)) * 100 if target_range != 0 else mse
                normalized_mae = (mae / target_range) * 100 if target_range != 0 else mae
                mean_uncertainty = np.mean(std_train_pred)
                std_uncertainty = np.std(std_train_pred)
                performance_results.append({
                    'score_tag': score_tag,
                    'r2': r2,
                    'mse': mse,
                    'mae': mae,
                    'normalized_mse_%': normalized_mse,
                    'normalized_mae_%': normalized_mae,
                    'mean_uncertainty': mean_uncertainty,
                    'std_uncertainty': std_uncertainty
                })
                logger.info(f"Performance for score tag {score_tag}: R²={r2:.3f}, MSE={mse:.3f}, MAE={mae:.3f}")
        # Save performance metrics to a CSV file.
        performance_df = pd.DataFrame(performance_results)
        perf_path = Path(self.config.output_folder) / "cv_performance_metrics.csv"
        performance_df.to_csv(perf_path, index=False)
        logger.info(f"Saved CV performance metrics to {perf_path}")

        # Store heatmap results in the context.
        context['heatmap_plots'] = heatmaps
