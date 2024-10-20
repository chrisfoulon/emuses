import logging

from pipelines.pipeline_stage import PipelineStage
from tools.stats_utils import train_and_test_model_per_label

class PredictionStage(PipelineStage):
    def __init__(self, config):
        super().__init__(config)

    def run(self, context):
        logger = logging.getLogger(__name__)
        logger.info("Running Prediction Stage")

        args = self.config.args

        train_embeddings = context.get('embeddings')
        test_embeddings = context.get('test_embeddings')
        train_labels = context.get('train_labels')
        test_labels = context.get('test_labels')

        if train_embeddings is None or test_embeddings is None:
            raise ValueError("Both training and test embeddings are required for prediction.")

        if train_labels is None or test_labels is None:
            raise ValueError("Both training and test labels are required for prediction.")

        if getattr(args, 'classification', False):
            # Classification
            train_and_test_model_per_label(
                train_embeddings=train_embeddings,
                train_labels=train_labels,
                test_embeddings=test_embeddings,
                test_labels=test_labels,
                output_folder=self.config.output_folder / 'prediction_models',
            )
            logger.info("Prediction model trained and saved.")
        else:
            # Regression (Not implemented in the original code)
            raise NotImplementedError("Regression prediction is not implemented yet.")
