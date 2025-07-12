# EMUSES Foundation FastAPI Service Documentation

<reasoning>
The foundation FastAPI service provides the REST API layer that the new Typer CLI will need to integrate with via HTTP client calls. The key components are:

1. PipelineRunner - Async pipeline execution wrapper that uses EMUSESPipeline internally
2. StageRunners - Individual stage execution with resource monitoring
3. JobManager - Background job tracking and status management
4. FastAPI App - REST endpoints for pipeline execution and job management
5. Pydantic Models - Request/response schemas for API validation

These components are crucial for the CLI integration because the new CLI will make HTTP calls to these endpoints instead of directly instantiating pipeline stages.
</reasoning>

## Level 1: FastAPI Service Overview

The Foundation FastAPI Service provides a REST API wrapper around the existing EMUSES pipeline system, enabling web-based access to dimensionality reduction, clustering, and prediction capabilities. The service implements asynchronous background job execution using ProcessPoolExecutor, comprehensive job management with progress tracking, and artifact handling for model persistence. The architecture preserves the existing EMUSESPipeline orchestration pattern while adding API-specific features like rate limiting, request validation, and structured error responses. The service maintains 100% functional compatibility with the CLI interface by using EMUSESPipeline internally, ensuring identical computational results across interfaces. Key capabilities include full pipeline execution, individual stage execution, job status monitoring, and artifact download endpoints.

## Level 2: Public API Reference

| Symbol | Purpose | Inputs | Outputs | Side-effects |
|--------|---------|--------|---------|--------------|
| `PipelineRunner` | Async pipeline execution with resource management | job_manager, max_workers, memory_limit, timeout | None | Manages background processes |
| `PipelineRunner.execute_pipeline()` | Execute full pipeline in background | job_id, context dict, progress_callback | context dict | Creates job, runs stages |
| `PipelineRunner._context_to_emuses_args()` | Convert API context to EMUSESPipeline args | context: Dict[str, Any] | argparse.Namespace | None |
| `PipelineRunner._create_emuses_progress_adapter()` | Adapter for EMUSESPipeline progress callbacks | api_progress_callback, job_id, rate_limit | Callable | Updates job status |
| `BaseStageRunner` | Base class for stage execution with monitoring | job_manager: JobManager | None | None |
| `BaseStageRunner._execute_with_monitoring()` | Execute stage with resource limits | stage_instance, context, progress_tracker | context dict | Monitors CPU/memory |
| `UMAPStageRunner` | UMAP dimensionality reduction stage execution | job_manager: JobManager | None | None |
| `HeatmapStageRunner` | Multi-target prediction stage execution | job_manager: JobManager | None | None |
| `PredictionStageRunner` | Test evaluation stage execution | job_manager: JobManager | None | None |
| `JobManager` | Background job tracking and status management | max_jobs: int | None | Manages job queue |
| `JobManager.create_job()` | Create new background job | config, job_name, description | job_id: str | Stores job metadata |
| `JobManager.get_job_status()` | Retrieve job status and progress | job_id: str | status dict | None |
| `JobManager.update_job_status()` | Update job progress and status | job_id, status, progress, message | None | Updates job records |
| `app` | FastAPI application instance | None | FastAPI app | None |
| `submit_full_pipeline_job()` | Submit full pipeline for execution | JobSubmissionRequest | JobStatusResponse | Creates background task |
| `submit_stage_specific_job()` | Submit individual stage for execution | stage_name, JobSubmissionRequest | JobStatusResponse | Creates background task |
| `get_job_status()` | Get job status via REST API | job_id: str | JobStatusResponse | None |

<details>
<summary><strong>PipelineRunner Implementation</strong></summary>

```python
class PipelineRunner:
    """Async pipeline runner with background execution and resource management."""

    def __init__(
        self,
        job_manager: JobManager,
        max_workers: int = 4,
        memory_limit_ratio: float = 0.75,
        pipeline_timeout: int = 1800,
    ):
        self.job_manager = job_manager
        self.max_workers = max_workers
        self.memory_limit_ratio = memory_limit_ratio
        self.pipeline_timeout = pipeline_timeout
        self.executor = ProcessPoolExecutor(max_workers=max_workers)
        self.logger = logging.getLogger(__name__)

    async def execute_pipeline(
        self,
        job_id: str,
        context: Dict[str, Any],
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Execute pipeline in background with progress tracking.
        
        Parameters
        ----------
        job_id : str
            Unique identifier for the job
        context : Dict[str, Any]
            Pipeline execution context with config and data
        progress_callback : Optional[Callable]
            Function called with progress updates
            
        Returns
        -------
        Dict[str, Any]
            Updated context dictionary with results
            
        Raises
        ------
        Exception
            If pipeline execution fails
        """
        try:
            self.logger.info(f"Starting pipeline execution for job {job_id}")
            
            # Update job status to running
            self.job_manager.update_job_status(job_id, "RUNNING", 0.0, "Starting pipeline")
            
            # Execute pipeline stages
            result_context = await self._execute_pipeline_stages(context, progress_callback)
            
            # Mark job as completed
            self.job_manager.update_job_status(job_id, "COMPLETED", 1.0, "Pipeline completed successfully")
            
            return result_context
            
        except Exception as e:
            self.logger.error(f"Pipeline execution failed for job {job_id}: {e}")
            self.job_manager.update_job_status(job_id, "FAILED", None, f"Error: {str(e)}")
            raise
```

</details>

<details>
<summary><strong>Context to Args Conversion</strong></summary>

```python
    def _context_to_emuses_args(self, context: Dict[str, Any]) -> argparse.Namespace:
        """Convert API context to EMUSESPipeline args format.
        
        Parameters
        ----------
        context : Dict[str, Any]
            API context dictionary with configuration
            
        Returns
        -------
        argparse.Namespace
            Args object compatible with EMUSESPipeline
        """
        config_dict = context.get("config", {})
        args = argparse.Namespace()

        # Required paths
        args.output_folder = str(config_dict.get("output_folder", ""))
        args.input_dataset = config_dict.get("input_file", "")
        args.scores = config_dict.get("scores_file", "")
        args.label_dataset = config_dict.get("label_dataset_file", "")

        # UMAP optimization parameters
        args.umap_trials = int(config_dict.get("umap_trials", 50))
        args.hdbscan_trials = int(config_dict.get("hdbscan_trials", 20))
        args.optim_dict = str(config_dict.get("optim_dict", "optim_dict_default"))

        # Test/train split
        args.test_size = float(config_dict.get("test_size", 0.2))

        # Model saving options
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

        return args
```

</details>

<details>
<summary><strong>Progress Callback Adapter</strong></summary>

```python
    def _create_emuses_progress_adapter(
        self,
        api_progress_callback: Optional[Callable],
        job_id: str,
        rate_limit_seconds: float = 1.0,
    ) -> Callable:
        """Create adapter between EMUSESPipeline and API progress callbacks.
        
        Parameters
        ----------
        api_progress_callback : Optional[Callable]
            Original API progress callback function
        job_id : str
            Job identifier for status updates
        rate_limit_seconds : float
            Minimum interval between progress updates
            
        Returns
        -------
        Callable
            Progress callback compatible with EMUSESPipeline
        """
        last_update_time = 0

        def emuses_progress_callback(
            stage_name: str, progress: float, message: str = ""
        ):
            nonlocal last_update_time
            current_time = time.time()

            # Rate limit progress updates
            if current_time - last_update_time >= rate_limit_seconds:
                last_update_time = current_time

                # Update job status in job manager
                progress_percent = int(progress * 100)
                status_message = (
                    message
                    if message
                    else f"{stage_name}: {progress_percent}%"
                )

                try:
                    self.job_manager.update_job_status(
                        job_id, "RUNNING", message=status_message
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
```

</details>

<details>
<summary><strong>FastAPI Endpoints</strong></summary>

```python
@app.post("/api/v1/jobs/pipeline/full", status_code=201)
@conditional_rate_limit(
    "50/hour"
)  # Rate limit: 50 jobs per hour per IP (more realistic for EMUSES)
async def submit_full_pipeline_job(
    request: Request, job_request: JobSubmissionRequest
) -> JobStatusResponse:
    """Submit a full pipeline job for background execution.
    
    Parameters
    ----------
    request : Request
        FastAPI request object
    job_request : JobSubmissionRequest
        Pipeline configuration and job metadata
        
    Returns
    -------
    JobStatusResponse
        Initial job status with job ID
        
    Raises
    ------
    HTTPException
        If validation fails or files don't exist
    """
    try:
        config = job_request.pipeline_config

        # Validate required fields
        if "input_file" not in config:
            raise ValueError("input_file is required")
        if "scores_file" not in config:
            raise ValueError("scores_file is required")
        if "output_folder" not in config:
            raise ValueError("output_folder is required")

        # Validate file paths exist
        validate_file_path(config["input_file"])
        validate_file_path(config["scores_file"])
        if config.get("label_dataset_file"):
            validate_file_path(config["label_dataset_file"])

        # Create job
        job_id = get_job_manager().create_job(
            config=config,
            job_name=job_request.job_name,
            description=job_request.description,
        )

        # Wrap config in the expected structure for pipeline runner
        pipeline_context = {
            "config": config,
            "input_dataset": config.get("input_file"),
            "scores_dataset": config.get("scores_file"),
        }

        # Submit for background execution
        asyncio.create_task(
            get_pipeline_runner().execute_pipeline(job_id, pipeline_context)
        )

        # Return initial status
        status = get_job_manager().get_job_status(job_id)
        return JobStatusResponse(**status)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "VALIDATION_ERROR",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            },
        )
```

</details>

<details>
<summary><strong>Stage-Specific Endpoints</strong></summary>

```python
@app.post("/api/v1/jobs/pipeline/stage/{stage_name}", status_code=201)
@conditional_rate_limit("100/hour")  # Rate limit: 100 stage jobs per hour per IP
async def submit_stage_specific_job(
    request: Request, stage_name: str, job_request: JobSubmissionRequest
) -> JobStatusResponse:
    """Submit a stage-specific job for background execution.
    
    Parameters
    ----------
    request : Request
        FastAPI request object
    stage_name : str
        Name of the stage to execute (umap, heatmap, prediction)
    job_request : JobSubmissionRequest
        Pipeline configuration and job metadata
        
    Returns
    -------
    JobStatusResponse
        Initial job status with job ID
        
    Raises
    ------
    HTTPException
        If stage name is invalid or validation fails
    """
    valid_stages = ["umap", "heatmap", "prediction"]
    if stage_name not in valid_stages:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "VALIDATION_ERROR",
                "message": f"Invalid stage name: {stage_name}. Valid stages: {valid_stages}",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        )

    try:
        # Modify config to enable only the specified stage
        config = job_request.pipeline_config.copy()
        config["umap_stage_enabled"] = stage_name == "umap"
        config["heatmap_stage_enabled"] = stage_name == "heatmap"
        config["prediction_stage_enabled"] = stage_name == "prediction"

        # Validate required fields
        if "input_file" not in config:
            raise ValueError("input_file is required")
        if "scores_file" not in config:
            raise ValueError("scores_file is required")
        if "output_folder" not in config:
            raise ValueError("output_folder is required")

        # Validate file paths exist
        validate_file_path(config["input_file"])
        validate_file_path(config["scores_file"])

        # Create job
        job_id = get_job_manager().create_job(
            config=config,
            job_name=job_request.job_name or f"{stage_name.title()} Stage Job",
            description=job_request.description,
        )

        # Wrap config in the expected structure for pipeline runner
        pipeline_context = {
            "config": config,
            "input_dataset": config.get("input_file"),
            "scores_dataset": config.get("scores_file"),
        }

        # Submit for background execution
        asyncio.create_task(
            get_pipeline_runner().execute_pipeline(job_id, pipeline_context)
        )

        # Return initial status
        status = get_job_manager().get_job_status(job_id)
        return JobStatusResponse(**status)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "VALIDATION_ERROR",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        )
```

</details>

## API Integration for Enhanced CLI

The new Typer CLI will integrate with the FastAPI service via HTTP client calls:

### Full Pipeline Execution
- **Endpoint**: `POST /api/v1/jobs/pipeline/full`
- **Purpose**: Submit complete pipeline job
- **CLI Integration**: Replace direct EMUSESPipeline instantiation

### Stage-Specific Execution  
- **Endpoint**: `POST /api/v1/jobs/pipeline/stage/{stage_name}`
- **Purpose**: Execute individual stages (umap, heatmap, prediction)
- **CLI Integration**: Enable granular pipeline control

### Job Status Monitoring
- **Endpoint**: `GET /api/v1/jobs/{job_id}/status`
- **Purpose**: Monitor job progress and completion
- **CLI Integration**: Provide real-time progress updates

### Configuration Translation
The CLI will need to translate command-line arguments to the API's expected JSON format, handling:
- Path resolution and validation
- Parameter type conversion  
- Stage enablement flags
- Progress callback integration

Coverage context: [coverage_html/index.html](../coverage_html/index.html)
