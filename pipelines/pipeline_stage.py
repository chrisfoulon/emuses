# pipelines/pipeline_stage.py

class PipelineStage:
    def __init__(self, config):
        self.config = config

    def run(self, context):
        raise NotImplementedError("Each stage must implement a run method.")
