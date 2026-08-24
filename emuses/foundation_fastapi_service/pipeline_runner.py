"""
Pipeline Runner for EMUSES Foundation FastAPI Service

This module provides an async wrapper for EMUSES pipeline execution with:
- ProcessPoolExecutor for background execution and resource isolation
- Context dictionary preservation with deep copy validation
- Progress callback integration with rate limiting
- Error handling and exception capture with job status updates
- Timeout handling and proper cleanup
"""

import argparse
import asyncio
import copy
import logging
import pickle
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from emuses.foundation_fastapi_service.job_manager import JobManager
from emuses.observability import get_logger, track_scientific_operation
from emuses.pipelines.emuses_pipeline import EMUSESPipeline
from emuses.pipelines.pipeline_config import PipelineConfig
from emuses.tools.parallelism_utils import parallelism_backend


class PipelineRunner:
    """Async pipeline runner with background execution and resource management."""

    def __init__(
        self,
        job_manager: JobManager,
        max_workers: int = 4,
        memory_limit_ratio: float = 0.75,
        pipeline_timeout: int = 1800,
    ):
        """Initialize pipeline runner with resource limits.

        Args:
            job_manager: JobManager instance for job lifecycle management
            max_workers: Maximum number of worker processes (default: 4)
            memory_limit_ratio: Memory limit as fraction of total system memory (default: 0.75)
            pipeline_timeout: Pipeline timeout in seconds (default: 1800)
        """
        self.job_manager = job_manager
        self.max_workers = max_workers
        self.memory_limit_ratio = memory_limit_ratio
        self.pipeline_timeout = pipeline_timeout
        self.executor = None  # ProcessPoolExecutor instance, created when needed
        self.logger = get_logger(self.__class__.__name__)

    def _context_to_emuses_args(self, context: Dict[str, Any]) -> argparse.Namespace:
        """Convert context dictionary to EMUSESPipeline arguments format.

        This utility creates an argparse.Namespace object compatible with EMUSESPipeline
        from the API context dictionary, applying appropriate defaults and type conversions.

        Args:
            context: Pipeline context dictionary containing config and data

        Returns:
            argparse.Namespace: Arguments object suitable for EMUSESPipeline

        Raises:
            ValueError: If required configuration values are missing
        """
        import argparse

        # Extract configuration from context
        config_dict = context.get("config", {})

        # Validate required fields
        output_folder = config_dict.get("output_folder")
        if not output_folder:
            raise ValueError("No output_folder specified in context config")

        # Create argparse.Namespace object
        args = argparse.Namespace()

        # Required attributes with type conversion
        args.output_folder = Path(output_folder)  # Convert to Path object

        # Pipeline configuration with defaults and type conversion
        args.umap_trials = int(config_dict.get("umap_trials", 10))
        args.hdbscan_trials = int(config_dict.get("hdbscan_trials", 5))
        args.optuna_trials = int(config_dict.get("optuna_trials", 10))
        args.prediction_optim_dict = str(
            config_dict.get("prediction_optim_dict", "optim_dict_test")
        )
        args.prefix = str(config_dict.get("prefix", "API"))

        # Execution parameters with defaults
        args.random_state = int(config_dict.get("random_state", 42))
        args.test_size = float(config_dict.get("test_size", 0.2))
        args.interactive_plot = bool(config_dict.get("interactive_plot", False))
        args.optim_dict = str(config_dict.get("optim_dict", "optim_dict_hcp"))
        # 1, not 4: serial Optuna search is the reproducible default (ADR 2.9c).
        args.hdbscan_jobs = int(config_dict.get("hdbscan_jobs", 1))
        args.n_jobs = int(config_dict.get("n_jobs", -1))
        args.sigma = config_dict.get("sigma", None)
        args.fwhm = config_dict.get("fwhm", None)
        args.outer_folds = int(config_dict.get("outer_folds", 5))
        args.model_version = str(config_dict.get("model_version", "1.0.0"))
        args.umap_jobs = int(config_dict.get("umap_jobs", 1))

        # Dataset and input configuration
        # Support both file-based (HCP-style) and direct data (API-style) execution
        # Check for input_dataset at top level first, then in config
        input_dataset = context.get("input_dataset") or config_dict.get("input_dataset")
        scores_dataset = context.get("scores_dataset") or config_dict.get("scores")

        if input_dataset:
            # File-based execution (like CLI) - use actual file paths
            args.input_dataset = str(input_dataset)

            # File parsing parameters from CLI
            args.columns_are_features = bool(
                config_dict.get("columns_are_features", False)
            )
            args.input_header = config_dict.get("input_header", None)
            args.input_index_column = config_dict.get("input_index_column", None)
            args.input_normalization = str(
                config_dict.get("input_normalization", "none")
            )
            args.inputs_columns = config_dict.get(
                "inputs_columns", None
            )  # None means use all columns, [] means use no columns
            args.scores_are_rows = bool(config_dict.get("scores_are_rows", False))

            # Scores file configuration
            if scores_dataset:
                args.scores = str(scores_dataset)
                args.scores_header = config_dict.get("scores_header", None)
                args.scores_index_column = config_dict.get("scores_index_column", None)
                args.scores_columns = config_dict.get(
                    "scores_columns", None
                )  # None means use all columns, [] means use no columns
                args.scores_column = config_dict.get(
                    "scores_column", None
                )  # Column(s) for scores
                args.scores_normalization = str(
                    config_dict.get("scores_normalization", "none")
                )  # Normalization for scores
                args.correlation_method = str(
                    config_dict.get("correlation_method", "pearson")
                )  # Correlation method
                args.classification = bool(
                    config_dict.get("classification", False)
                )  # Classification mode
            else:
                args.scores = None
        else:
            # Direct data execution (API-style) - use 'mnist' to bypass file validation
            # We'll override the context with our actual data after initialization
            args.input_dataset = "mnist"
            args.inputs_columns = None
            args.scores_columns = None
            args.scores_are_rows = False
            args.scores_column = None
            args.scores_normalization = "none"
            args.correlation_method = "pearson"
            args.classification = False

        # Additional CLI arguments that EMUSESPipeline expects
        args.load_umap = config_dict.get("load_umap", None)
        args.load_embeddings = config_dict.get("load_embeddings", None)
        args.load_hdbscan = config_dict.get("load_hdbscan", None)
        args.save_embeddings = bool(config_dict.get("save_embeddings", True))
        args.save_umap = bool(config_dict.get("save_umap", True))
        args.save_hdbscan = bool(config_dict.get("save_hdbscan", True))

        # Stage enablement flags
        args.umap_stage_enabled = bool(config_dict.get("umap_stage_enabled", True))
        args.heatmap_stage_enabled = bool(
            config_dict.get("heatmap_stage_enabled", True)
        )
        args.prediction_stage_enabled = bool(
            config_dict.get("prediction_stage_enabled", True)
        )

        # Additional EMUSESPipeline parameters that might be needed
        args.input_file_types = config_dict.get("input_file_types")
        args.arg_separator = str(config_dict.get("arg_separator", ","))
        args.bids_filters = config_dict.get("bids_filters", {})
        args.filter_labelled_by_scores = bool(
            config_dict.get("filter_labelled_by_scores", False)
        )
        args.scores_column = config_dict.get("scores_column", None)
        args.load_embeddings = config_dict.get("load_embeddings", None)
        args.label_dataset = config_dict.get("label_dataset", None)

        # ------------------------------------------------------------------
        # Options the CLI accepts but this mapping used to drop on the floor.
        #
        # Every `emuses full` option travels through here on its way to
        # PipelineConfig. Anything not assigned below never reaches the
        # pipeline at all - it silently falls back to the PipelineConfig
        # dataclass default, so the run quietly ignores the flag instead of
        # failing. These four have real consumers and were being lost:
        #
        #   hdbscan_core_dist_n_jobs     -> umap_stage.py:112
        #   hdbscan_approx_min_span_tree -> umap_stage.py:110
        #   input_file_list              -> emuses_pipeline.py:265
        #   recursive_input_file_search  -> emuses_pipeline.py:327 (see below)
        #
        # tests/test_cli_option_mapping.py fails if a new CLI option is added
        # without either being mapped here or declared as deliberately unmapped.
        # ------------------------------------------------------------------
        args.hdbscan_core_dist_n_jobs = int(
            config_dict.get("hdbscan_core_dist_n_jobs", -1)
        )
        args.hdbscan_approx_min_span_tree = bool(
            config_dict.get("hdbscan_approx_min_span_tree", True)
        )
        args.input_file_list = bool(config_dict.get("input_file_list", False))

        # The CLI flag --recursive-input-file-search binds to the Python
        # parameter `recursive_search`, so it arrives under that key - but the
        # only consumer, emuses_pipeline.py:327, reads
        # `args.recursive_input_file_search`. The flag was therefore always
        # False no matter what the user passed. PipelineConfig declares both
        # names (pipeline_config.py:80 and :97); `recursive_input_file_search`
        # is the live one, so accept either key and feed that attribute.
        args.recursive_input_file_search = bool(
            config_dict.get(
                "recursive_input_file_search",
                config_dict.get("recursive_search", False),
            )
        )

        # Store data references for access during pipeline execution
        # We'll store them as attributes but they won't be used by EMUSESPipeline directly
        # since we'll pass them through context
        if "input_matrix" in context:
            args.input_matrix = context["input_matrix"]
        if "scores" in context:
            args.scores = context["scores"]
        if "output_format_info" in context:
            args.output_format_info = context["output_format_info"]

        return args

    def _cleanup_temp_scores_file(self, context: Dict[str, Any]) -> None:
        """
        Clean up temporary scores file created for special datasets.

        Parameters
        ----------
        context : Dict[str, Any]
            Pipeline context that may contain _temp_scores_file marker
        """
        from pathlib import Path

        config = context.get("config", {})
        temp_scores_file = config.get("_temp_scores_file")

        if temp_scores_file:
            try:
                temp_file_path = Path(temp_scores_file)
                if temp_file_path.exists():
                    temp_file_path.unlink()
                    self.logger.info(f"Cleaned up temporary scores file: {temp_scores_file}")
            except Exception as e:
                self.logger.warning(f"Failed to cleanup temporary scores file {temp_scores_file}: {e}")

    async def execute_pipeline(
        self,
        job_id: str,
        context: Dict[str, Any],
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Execute pipeline asynchronously with ProcessPoolExecutor.

        Args:
            job_id: Job identifier for tracking
            context: Pipeline context dictionary
            progress_callback: Optional progress callback function

        Returns:
            Dict[str, Any]: Updated context after pipeline execution

        Raises:
            asyncio.TimeoutError: If pipeline execution times out
            Exception: Any pipeline execution error
        """
        try:
            # Update job status to running
            self.job_manager.update_job_status(
                job_id, "running", message="Starting pipeline execution"
            )

            # Create deep copy of context to prevent corruption
            context_copy = copy.deepcopy(context)

            # Create progress callback if not provided
            if progress_callback is None:
                progress_callback = self._create_progress_callback(job_id)

            # Execute pipeline with timeout
            result = await asyncio.wait_for(
                self._execute_pipeline_stages(context_copy, progress_callback),
                timeout=self.pipeline_timeout,
            )

            # Update job status to completed
            self.job_manager.update_job_status(
                job_id, "completed", message="Pipeline execution completed"
            )

            return result

        except asyncio.TimeoutError:
            self.job_manager.update_job_status(
                job_id,
                "failed",
                message=f"Pipeline execution timeout after {self.pipeline_timeout} seconds",
            )
            raise
        except Exception as e:
            # Ensure we have a meaningful error message for job status
            error_msg = (
                str(e)
                if str(e)
                else f"{type(e).__name__}: Unknown error during pipeline execution"
            )
            self.job_manager.update_job_status(
                job_id, "failed", message=f"Pipeline execution error: {error_msg}"
            )
            raise
        finally:
            # Cleanup temporary scores file if it was created for special datasets
            self._cleanup_temp_scores_file(context)

    async def _execute_pipeline_stages(
        self, context: Dict[str, Any], progress_callback: Callable
    ) -> Dict[str, Any]:
        """Execute real EMUSES pipeline stages.

        Args:
            context: Pipeline context dictionary
            progress_callback: Progress callback function

        Returns:
            Dict[str, Any]: Updated context after execution
        """
        self.logger.info("Executing real EMUSES pipeline stages")

        # For now, run in the same process to avoid serialization complexity
        # TODO: Later optimize to use ProcessPoolExecutor when serialization is solved
        try:
            # Call the real pipeline execution
            result_context = self._run_pipeline_in_process(
                context, self.memory_limit_ratio
            )

            self.logger.info("Pipeline execution completed successfully")
            return result_context

        except Exception as e:
            import traceback

            error_msg = str(e) if str(e) else f"{type(e).__name__} (no error message)"
            self.logger.error(f"Pipeline execution failed: {error_msg}")
            self.logger.debug(f"Full traceback:\n{traceback.format_exc()}")

            # Ensure we always have a meaningful error message
            if not str(e):
                raise RuntimeError(
                    f"Pipeline stage execution failed: {type(e).__name__} occurred"
                ) from e
            raise

    def _run_pipeline(
        self,
        context: Dict[str, Any],
        memory_limit_ratio: float = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Alias for _run_pipeline_in_process for backward compatibility."""
        if memory_limit_ratio is None:
            memory_limit_ratio = self.memory_limit_ratio
        return self._run_pipeline_in_process(
            context, memory_limit_ratio, progress_callback
        )

    def _run_pipeline_in_process(
        self,
        context: Dict[str, Any],
        memory_limit_ratio: float,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Run pipeline using EMUSESPipeline for consistent execution.

        This method has been refactored to use EMUSESPipeline internally,
        ensuring consistent data preprocessing, context setup, and stage
        orchestration identical to CLI execution path.

        Args:
            context: Pipeline context dictionary
            memory_limit_ratio: Memory limit ratio for resource monitoring
            progress_callback: Optional progress callback for API integration

        Returns:
            Dict[str, Any]: Updated context after pipeline execution
        """
        # Get user and job context for observability
        user_id = context.get("user_id")
        job_id = context.get("job_id", "unknown")
        dataset_name = context.get("config", {}).get("input_dataset", "api_data")

        with track_scientific_operation(
            "pipeline_execution",
            user_id=user_id,
            additional_attributes={
                "job_id": job_id,
                "dataset": dataset_name,
                "execution_method": "pipeline_runner",
            },
        ) as obs_ctx, parallelism_backend("threading"):
            # Pipeline work runs on the threading backend, scoped to this call.
            #
            # This was previously an unconditional
            # `configure_parallelism_backend(force_backend="threading")` justified by
            # "service workers run in subprocess context". Two problems with that: it set a
            # module-level global nothing restored, so the choice leaked into everything
            # sharing the interpreter (a pipeline test demonstrably changed the outcome of an
            # unrelated test that ran afterwards); and the justification stops being true when
            # the pipeline runs in the main process, which both the local CLI path and the
            # tests do.
            #
            # Letting context detection choose instead is wrong here for a reason that only
            # showed up when measured: in the main process it selects loky, which spawns a
            # worker pool that re-imports the scientific stack per worker. For the small,
            # short tasks this pipeline distributes that is pure overhead - it turned a ~110 s
            # test into one still running after 300 s with eight LokyProcess workers alive.
            #
            # So the backend choice is kept, and only its scope is fixed. Whether loky is
            # worth it for realistic workloads is a performance question with its own
            # measurement, deliberately left to the parallelism arm of the reproducibility
            # work rather than changed as a side effect here.
            try:
                config_dict = context.get("config", {})

                # Inference is not a stage sequence: it loads a trained model and applies
                # it. It shares the data preparation with training (the model's saved
                # scaler expects raw input in the training input's space), which is why
                # `run_inference` builds an EMUSESPipeline of its own rather than this
                # method assembling stages for it.
                if config_dict.get("command") == "inference":
                    from emuses.pipelines.inference_runner import run_inference

                    obs_ctx.set_attribute("enabled_stages", ["inference"])
                    results = run_inference(config_dict)
                    obs_ctx.set_attribute("pipeline_success", True)
                    result_context = dict(context)
                    result_context["inference_results"] = results
                    return result_context

                # Convert context to EMUSESPipeline arguments
                args = self._context_to_emuses_args(context)

                # Create EMUSESPipeline instance
                pipeline = EMUSESPipeline(args)

                # Add observability context
                obs_ctx.set_attribute(
                    "num_stages", len(context.get("config", {}).keys())
                )

                # Set up pipeline context based on execution mode
                if context.get("input_dataset"):
                    # File-based execution: EMUSESPipeline will load and process files
                    # Don't override context - let EMUSESPipeline handle file loading
                    obs_ctx.set_attribute("execution_mode", "file_based")
                    pass
                else:
                    # Direct data execution: provide data directly to pipeline context
                    obs_ctx.set_attribute("execution_mode", "direct_data")
                    pipeline.context.update(
                        {
                            "input_matrix": context.get("input_matrix"),
                            "scores": context.get("scores"),
                            "output_format_info": context.get("output_format_info"),
                            "dataset_type": context.get("dataset_type", "api_data"),
                            "paths_list": context.get("paths_list"),
                        }
                    )

                # Add stages based on configuration
                enabled_stages = []

                if config_dict.get("umap_stage_enabled", True):
                    from emuses.pipelines.umap_stage import UMAPStage

                    pipeline.add_stage(UMAPStage(pipeline.config))
                    enabled_stages.append("umap")

                if config_dict.get("heatmap_stage_enabled", True):
                    from emuses.pipelines.heatmap_stage import HeatmapStage

                    output_format_info = context.get("output_format_info", [])
                    pipeline.add_stage(
                        HeatmapStage(pipeline.config, output_format_info)
                    )
                    enabled_stages.append("heatmap")

                # InferenceStage for classic mode validation when test_size > 0
                # Automatically added after HeatmapStage for held-out test set validation
                # InferenceStage validates the prediction models HeatmapStage produces, so
                # it cannot run without them. A UMAP-only job (`emuses umap`) has no
                # prediction stage and no scores, and adding inference to it failed with
                # "No inference features found in context".
                if ("heatmap" in enabled_stages and
                    config_dict.get("inference_stage_enabled", True) and 
                    config_dict.get("test_size", 0.0) > 0.0 and 
                    config_dict.get("label_dataset") is None):  # Classic mode only
                    
                    from emuses.pipelines.inference_stage import InferenceStage
                    
                    # InferenceStage will access prediction_test_features and prediction_test_labels from context
                    pipeline.add_stage(InferenceStage(pipeline.config))
                    enabled_stages.append("inference")
                    
                    self.logger.info(f"Added InferenceStage for automatic validation (test_size={config_dict.get('test_size', 0.0)})")

                # PredictionStage retired - replaced by HeatmapStage + InferenceStage
                if config_dict.get("prediction_stage_enabled", False):  # Disabled by default
                    self.logger.warning("PredictionStage has been retired. Use HeatmapStage for training and InferenceStage for validation.")
                    # from emuses.pipelines.prediction_stage import PredictionStage
                    # pipeline.add_stage(PredictionStage(pipeline.config))
                    # enabled_stages.append("prediction")

                obs_ctx.set_attribute("enabled_stages", enabled_stages)

                # Create progress callback adapter if needed
                emuses_progress_callback = None
                if progress_callback is not None:
                    emuses_progress_callback = self._create_emuses_progress_adapter(
                        progress_callback,
                        job_id=context.get("job_id", "unknown"),
                        rate_limit_seconds=1.0,
                    )

                # Run the pipeline
                pipeline.run(progress_callback=emuses_progress_callback)

                # Merge EMUSESPipeline context back into API context
                result_context = self._merge_pipeline_context(context, pipeline.context)

                # Add final observability metrics
                obs_ctx.set_attribute("pipeline_success", True)
                if "pipeline_metadata" in result_context:
                    metadata = result_context["pipeline_metadata"]
                    # Handle case where metadata might be None
                    if metadata is not None:
                        obs_ctx.set_attribute(
                            "total_runtime", metadata.get("total_runtime", 0)
                        )
                        obs_ctx.set_attribute(
                            "stages_completed", len(metadata.get("stages_completed", []))
                        )

                return result_context

            except Exception as e:
                # Log the error with full traceback and re-raise with preserved context
                import traceback

                error_msg = str(e) if str(e) else f"{type(e).__name__} (no message)"
                full_traceback = traceback.format_exc()

                # Add error context to observability
                obs_ctx.set_attribute("pipeline_success", False)
                obs_ctx.set_attribute("error_type", type(e).__name__)
                obs_ctx.set_attribute("error_message", error_msg)

                self.logger.error(f"EMUSESPipeline execution failed: {error_msg}")
                self.logger.error(f"Full traceback:\n{full_traceback}")

                # Re-raise with enhanced error message if original is empty
                if not str(e):
                    raise RuntimeError(
                        f"Pipeline execution failed: {type(e).__name__} occurred during stage execution"
                    ) from e
                raise

    def _merge_pipeline_context(
        self, api_context: Dict[str, Any], pipeline_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge EMUSESPipeline context back into API context.

        This utility preserves API-specific metadata while incorporating
        pipeline execution results and artifacts.

        Args:
            api_context: Original API context dictionary
            pipeline_context: EMUSESPipeline context after execution

        Returns:
            Dict[str, Any]: Merged context preserving API metadata
        """
        # Start with a copy of the API context
        result_context = api_context.copy()

        # Merge pipeline results, giving priority to pipeline context for execution data
        result_context.update(
            {
                "embeddings": pipeline_context.get("embeddings"),
                "cluster_labels": pipeline_context.get("cluster_labels"),
                "clusterer": pipeline_context.get("clusterer"),
                "umap_model": pipeline_context.get("umap_model"),
                "random_seeds": pipeline_context.get("random_seeds"),
                "pipeline_metadata": pipeline_context.get("pipeline_metadata"),
                "prediction_results": pipeline_context.get("prediction_results"),
                "heatmap_results": pipeline_context.get("heatmap_results"),
            }
        )

        # Preserve original API metadata
        if "api_metadata" in api_context:
            result_context["api_metadata"] = api_context["api_metadata"]

        # Add execution markers
        result_context.update(
            {
                "pipeline_executed": True,
                "api_execution_timestamp": time.time(),
                "execution_method": "EMUSESPipeline",
            }
        )

        return result_context

    def _create_progress_callback(self, job_id: str) -> Callable:
        """Create a progress callback function for the job.

        Args:
            job_id: Job identifier

        Returns:
            Callable: Progress callback function
        """

        def progress_callback(stage_name: str, progress: float, message: str = ""):
            """Progress callback with rate limiting."""
            # Rate limiting could be implemented here
            self.logger.info(f"Job {job_id} - {stage_name}: {progress:.2%} - {message}")

        return progress_callback

    def _serialize_context(self, context: Dict[str, Any]) -> bytes:
        """Serialize context dictionary for ProcessPoolExecutor.

        Args:
            context: Context dictionary to serialize

        Returns:
            bytes: Serialized context data
        """
        return pickle.dumps(context)

    def _deserialize_context(self, data: bytes) -> Dict[str, Any]:
        """Deserialize context dictionary from ProcessPoolExecutor.

        Args:
            data: Serialized context data

        Returns:
            Dict[str, Any]: Deserialized context dictionary
        """
        return pickle.loads(data)

    def _create_emuses_progress_adapter(
        self,
        api_progress_callback: Optional[Callable],
        job_id: str,
        rate_limit_seconds: float = 1.0,
    ) -> Callable:
        """Create progress callback adapter for EMUSESPipeline format.

        This adapter converts between the API progress callback format and
        EMUSESPipeline's expected progress callback format, with rate limiting
        to prevent excessive callback frequency.

        Args:
            api_progress_callback: Original API progress callback function
            job_id: Job identifier for status updates
            rate_limit_seconds: Minimum seconds between progress updates

        Returns:
            Callable: Progress callback function compatible with EMUSESPipeline
        """
        import time

        # Track last callback time for rate limiting
        last_callback_time = {"time": 0.0}

        def emuses_progress_callback(
            stage_name: str, progress: float, message: str = ""
        ):
            """Progress callback compatible with EMUSESPipeline format.

            Args:
                stage_name: Name of the pipeline stage
                progress: Progress as float between 0.0 and 1.0
                message: Optional progress message
            """
            current_time = time.time()

            # Rate limiting - only call if enough time has passed
            if current_time - last_callback_time["time"] >= rate_limit_seconds:
                last_callback_time["time"] = current_time

                # Update job status with progress information
                progress_percent = int(progress * 100)
                status_message = (
                    f"{stage_name}: {progress_percent}% - {message}"
                    if message
                    else f"{stage_name}: {progress_percent}%"
                )

                try:
                    self.job_manager.update_job_status(
                        job_id, "running", message=status_message
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to update job status: {e}")

                # Call the original API callback if provided
                if api_progress_callback is not None:
                    try:
                        # Call with EMUSESPipeline-style arguments
                        api_progress_callback(
                            stage_name=stage_name, progress=progress, message=message
                        )
                    except Exception:
                        # Try alternative calling convention if the above fails
                        try:
                            api_progress_callback(stage_name, progress, message)
                        except Exception as e:
                            self.logger.warning(f"Progress callback failed: {e}")

                # Log progress for debugging
                self.logger.info(
                    f"Job {job_id} - {stage_name}: {progress:.2%} - {message}"
                )

        return emuses_progress_callback
