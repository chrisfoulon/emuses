from pathlib import Path
import json
import logging

from bcblib.tools.general_utils import save_json

from emuses.pipelines.pipeline_stage import PipelineStage
from emuses.tools.kernel_regression_utils import evaluate_ensemble_on_test


class PredictionStage(PipelineStage):
    def __init__(self, config):
        super().__init__(config)

    def run(self, context, progress_queue=None):
        logger = logging.getLogger(__name__)
        logger.info("Running Prediction Stage (Test Evaluation)")

        args = self.config.args

        # Retrieve training and test splits from the context.
        train_embeddings = context.get('embeddings')
        test_embeddings = context.get('test_embeddings')
        train_labels = context.get('train_labels')
        test_labels = context.get('test_labels')

        if train_embeddings is None or test_embeddings is None:
            raise ValueError("Both training and test embeddings are required for prediction.")
        if train_labels is None or test_labels is None:
            raise ValueError("Both training and test labels are required for prediction.")

        # Optional: If the configuration includes 'run_old_prediction', run the legacy prediction pipeline.
        if getattr(args, 'run_old_prediction', False):
            # Import and call the existing function.
            from emuses.tools.stats_utils import train_and_test_model_per_label
            train_and_test_model_per_label(
                train_embeddings=train_embeddings,
                train_labels=train_labels,
                test_embeddings=test_embeddings,
                test_labels=test_labels,
                output_folder=self.config.output_folder / 'prediction_models',
                categorical=getattr(args, 'classification', False),
                show_plot=getattr(args, 'show_plots', False)
            )
            logger.info("Old prediction pipeline executed and results saved.")

        # Retrieve the ensemble of kernel regression models from the heatmap stage.
        heatmap_results = context.get('heatmap_plots', {})
        if not heatmap_results:
            raise ValueError("No heatmap results available in context to retrieve kernel regression models.")

        # For simplicity, select the ensemble from the first score tag.
        first_tag = list(heatmap_results.keys())[0]
        models = heatmap_results[first_tag].get('models')
        if models is None:
            raise ValueError(f"No kernel regression models found for score tag '{first_tag}'.")
        logger.info(f"Using kernel regression ensemble from score tag '{first_tag}' for test evaluation.")

        # Evaluate the ensemble on the test data using the helper function.
        performance = evaluate_ensemble_on_test(models, test_embeddings, test_labels,
                                                classification=getattr(args, 'classification', False))
        logger.info(f"Test Performance: {performance}")

        # Save the performance metrics as a JSON file.
        output_folder = Path(self.config.output_folder) / "prediction_performance"
        output_folder.mkdir(parents=True, exist_ok=True)
        perf_file = output_folder / "prediction_performance.json"
        save_json(perf_file, performance)
        logger.info(f"Saved test performance metrics to {perf_file}")
