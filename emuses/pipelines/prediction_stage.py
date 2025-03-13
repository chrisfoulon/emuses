from pathlib import Path
import logging
import pandas as pd
from bcblib.tools.general_utils import save_json

from emuses.pipelines.pipeline_stage import PipelineStage
from emuses.tools.kernel_regression_utils import evaluate_ensemble_on_test
from emuses.tools.stats_utils import train_and_test_model_per_label


class PredictionStage(PipelineStage):
    def __init__(self, config):
        super().__init__(config)

    def run(self, context, progress_queue=None):
        logger = logging.getLogger(__name__)
        logger.info("Running Prediction Stage (Test Evaluation)")

        args = self.config.args

        if 'train_labelled_embeddings' in context and 'test_labelled_embeddings' in context \
                and 'train_labelled_scores' in context and 'test_labelled_scores' in context:
            train_embeddings = context['train_labelled_embeddings']
            train_labels = context['train_labelled_scores']
            test_embeddings = context['test_labelled_embeddings']
            test_labels = context['test_labelled_scores']
            logger.info(
                "Using labelled dataset split for prediction: training on labelled training data and testing on "
                "labelled test data.")
        else:
            # Fallback: use the default splits from unsupervised data splitting.
            train_embeddings = context.get('embeddings')
            test_embeddings = context.get('test_embeddings')
            train_labels = context.get('train_labels')
            test_labels = context.get('test_labels')

        if train_embeddings is None or test_embeddings is None:
            raise ValueError("Both training and test embeddings are required for prediction.")
        if train_labels is None or test_labels is None:
            raise ValueError("Both training and test labels are required for prediction.")

        # Optional: Run legacy prediction if requested.
        if getattr(args, 'run_old_prediction', False):
            train_and_test_model_per_label(
                train_embeddings=train_embeddings,
                train_labels=train_labels,
                test_embeddings=test_embeddings,
                test_labels=test_labels,
                output_folder=self.config.output_folder / 'prediction_models',
                categorical=getattr(args, 'classification', False),
                show_plot=getattr(args, 'show_plots', False)
            )
            logger.info("Legacy prediction pipeline executed and results saved.")

        # Retrieve the ensemble of kernel regression models from the heatmap stage.
        heatmap_results = context.get('heatmap_plots', {})
        if not heatmap_results:
            raise ValueError("No heatmap results available in context to retrieve kernel regression models.")

        # For classification, iterate over each score tag.
        if getattr(args, 'classification', False):
            results_list = []
            for score_tag in sorted(heatmap_results.keys()):
                models = heatmap_results[score_tag].get('models')
                if models is None:
                    logger.error(f"No kernel regression models found for score tag '{score_tag}'. Skipping.")
                    continue
                try:
                    parts = score_tag.split('_')
                    # If the key is just a number (e.g. "0"), use it directly.
                    if len(parts) == 1:
                        score_index = int(score_tag)
                    else:
                        score_index = int(parts[1])
                except Exception as e:
                    logger.error(f"Failed to extract index from score tag '{score_tag}': {e}. Skipping.")
                    continue

                # If test_labels is multi-column, extract the corresponding column.
                if test_labels.ndim == 1:
                    y_test_column = (test_labels == int(score_tag)).astype(int)
                else:
                    if score_index >= test_labels.shape[1]:
                        logger.error(
                            f"Score index {score_index} out of range for test_labels with shape {test_labels.shape}. "
                            f"Skipping.")
                        continue
                    y_test_column = test_labels[:, score_index]

                performance = evaluate_ensemble_on_test(models, test_embeddings, y_test_column,
                                                        classification=True)
                result = {
                    'score_tag': score_tag,
                    'accuracy': performance.get('accuracy', None),
                    'confusion_matrix': performance.get('confusion_matrix', None),
                    'roc_auc': performance.get('roc_auc', None),
                    'f1_score': performance.get('f1_score', None),
                    'precision': performance.get('precision', None),
                    'recall': performance.get('recall', None)
                }
                results_list.append(result)
                logger.info(f"Test performance for {score_tag}: {result}")

            if not results_list:
                raise ValueError("No test performance results could be computed for classification.")

            # Save results to CSV.
            performance_df = pd.DataFrame(results_list)
            output_folder = Path(self.config.output_folder) / "prediction_performance"
            output_folder.mkdir(parents=True, exist_ok=True)
            perf_csv_file = output_folder / "prediction_performance_classification.csv"
            performance_df.to_csv(perf_csv_file, index=False)
            logger.info(f"Saved test performance metrics (classification) to {perf_csv_file}")

            # Save performance as JSON and CSV
            output_folder = Path(self.config.output_folder) / "prediction_performance"
            output_folder.mkdir(parents=True, exist_ok=True)
            perf_json_file = output_folder / "prediction_performance.json"
            save_json(perf_json_file, results_list)
            logger.info(f"Saved test performance metrics (classification) to {perf_json_file}")
        else:
            # Regression mode: we expect test_labels to have one column per predicted variable.
            results_list = []
            # Iterate over all score tags; assume they are named 'score_i' where i is the column index.
            for score_tag in sorted(heatmap_results.keys()):
                models = heatmap_results[score_tag].get('models')
                if models is None:
                    logger.error(f"No kernel regression models found for score tag '{score_tag}'. Skipping.")
                    continue
                try:
                    # Extract the index from the score tag, e.g., "score_0" -> 0
                    score_index = int(score_tag.split('_')[1])
                except Exception as e:
                    logger.error(f"Failed to extract index from score tag '{score_tag}': {e}. Skipping.")
                    continue

                if test_labels.ndim == 1:
                    y_test_column = test_labels
                else:
                    if score_index >= test_labels.shape[1]:
                        logger.error(
                            f"Score index {score_index} out of range for test_labels with shape {test_labels.shape}. Skipping.")
                        continue
                    y_test_column = test_labels[:, score_index]

                performance = evaluate_ensemble_on_test(models, test_embeddings, y_test_column,
                                                        classification=False)
                # Extract only the metrics we want to save.
                result = {
                    'score_tag': score_tag,
                    'r2': performance.get('r2', None),
                    'mse': performance.get('mse', None),
                    'mae': performance.get('mae', None),
                    'normalized_mse_%': performance.get('normalized_mse_%', None),
                    'normalized_mae_%': performance.get('normalized_mae_%', None)
                }
                results_list.append(result)
                logger.info(f"Test performance for {score_tag}: {result}")

            if not results_list:
                raise ValueError("No test performance results could be computed.")

            # Convert the results list into a DataFrame and save as CSV.
            performance_df = pd.DataFrame(results_list)
            output_folder = Path(self.config.output_folder) / "prediction_performance"
            output_folder.mkdir(parents=True, exist_ok=True)
            perf_csv_file = output_folder / "prediction_performance.csv"
            performance_df.to_csv(perf_csv_file, index=False)
            logger.info(f"Saved test performance metrics (regression) to {perf_csv_file}")

            # Optionally, also save as JSON.
            perf_json_file = output_folder / "prediction_performance.json"
            save_json(perf_json_file, results_list)
            logger.info(f"Saved test performance JSON to {perf_json_file}")