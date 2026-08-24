"""Pydantic models for Foundation FastAPI Service.

This module contains all request and response models for the FastAPI service,
including configuration models that inherit from the existing PipelineConfig,
job management models, error responses, and file upload models.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PipelineConfigRequest(BaseModel):
    """API model for pipeline configuration requests.

    This model inherits the structure from emuses.pipelines.pipeline_config.PipelineConfig
    and provides Pydantic validation for API requests.
    """

    # Input data files
    input_file: str = Field(..., description="Path to the input data file")
    scores_file: str = Field(..., description="Path to the scores data file")
    label_dataset_file: Optional[str] = Field(
        default=None,
        description="Optional path to label dataset file for supervised mode",
    )

    # Output configuration
    output_folder: str = Field(..., description="Path to the output folder")

    # Pipeline stage controls
    umap_stage_enabled: bool = Field(
        default=True, description="Enable UMAP dimensionality reduction stage"
    )
    heatmap_stage_enabled: bool = Field(
        default=True, description="Enable heatmap generation stage"
    )
    prediction_stage_enabled: bool = Field(
        default=True, description="Enable prediction/classification stage"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "input_file": "data/input.csv",
                "scores_file": "data/scores.csv",
                "label_dataset_file": "data/labels.csv",
                "output_folder": "~/emuses_outputs/experiment_001",
                "umap_stage_enabled": True,
                "heatmap_stage_enabled": True,
                "prediction_stage_enabled": True,
            }
        }
    )


# Placeholder models for other tasks - to be implemented in subsequent tasks
class JobSubmissionRequest(BaseModel):
    """Job submission request model - Task 1.2."""

    pipeline_config: dict = Field(..., description="Pipeline configuration dictionary")
    job_name: Optional[str] = Field(
        default=None, description="Optional human-readable name for the job"
    )
    description: Optional[str] = Field(
        default=None, description="Optional description of the job"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pipeline_config": {
                    "input_file": "data/input.csv",
                    "scores_file": "data/scores.csv",
                    "output_folder_path": "~/emuses_outputs/job_001",
                },
                "job_name": "Experiment 001",
                "description": "Initial analysis of dataset A",
            }
        }
    )


class JobStatusResponse(BaseModel):
    """Job status response model - Task 1.2."""

    job_id: UUID = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status")
    created_at: Union[datetime, str] = Field(..., description="Job creation timestamp")
    started_at: Optional[Union[datetime, str]] = Field(
        default=None, description="Job start timestamp"
    )
    completed_at: Optional[Union[datetime, str]] = Field(
        default=None, description="Job completion timestamp"
    )
    progress: Optional[float] = Field(
        default=None, description="Job progress percentage (0.0 to 1.0)", ge=0.0, le=1.0
    )
    current_stage: Optional[str] = Field(
        default=None, description="Current pipeline stage being processed"
    )
    total_stages: Optional[int] = Field(
        default=None, description="Total number of pipeline stages"
    )
    message: Optional[str] = Field(
        default=None, description="Current status message or error details"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "running",
                "created_at": "2025-07-03T10:30:00Z",
                "started_at": "2025-07-03T10:30:15Z",
                "progress": 0.65,
                "current_stage": "umap_stage",
                "total_stages": 3,
                "message": "Processing UMAP dimensionality reduction",
            }
        }
    )


class ErrorResponse(BaseModel):
    """Error response model - Task 1.3."""

    error_code: str = Field(..., description="Standardized error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[str] = Field(
        default=None, description="Detailed error information"
    )
    request_id: Optional[str] = Field(
        default=None, description="Request identifier for error tracking"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_code": "VALIDATION_ERROR",
                "message": "Invalid input configuration",
                "details": "The field 'input_file' is required but was not provided",
                "request_id": "req_123456789",
            }
        }
    )


class FileUploadModel(BaseModel):
    """File upload model - Task 1.4."""

    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type of the file")
    size: int = Field(
        ..., description="File size in bytes", gt=0, le=100 * 1024 * 1024  # 100MB limit
    )
    field_name: Optional[str] = Field(
        default=None, description="Form field name for the upload"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "filename": "data.csv",
                "content_type": "text/csv",
                "size": 1024000,
                "field_name": "input_file",
            }
        }
    )


class FileUploadResponse(BaseModel):
    """Response model for file upload endpoints."""

    file_id: str = Field(..., description="Unique identifier for the uploaded file")
    filename: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Server path to the uploaded file")
    content_type: str = Field(..., description="MIME type of the file")
    size: int = Field(..., description="File size in bytes")
    upload_time: str = Field(..., description="ISO timestamp of upload")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_id": "upload_123456_features.csv",
                "filename": "patient_features.csv",
                "file_path": "/tmp/emuses_uploads/job_123/features.csv",
                "content_type": "text/csv",
                "size": 1024000,
                "upload_time": "2024-01-15T10:30:00Z",
            }
        }
    )


class InferenceRequest(BaseModel):
    """
    API model for inference requests.

    This model defines the request structure for running inference
    on trained EMUSES models with validation and format options.
    Supports both traditional model paths and complete model IDs from registry.
    """

    model_path: Optional[str] = Field(None, description="Path to trained model directory (for traditional models)")
    model_id: Optional[str] = Field(None, description="Registry model ID (alternative to model_path)")
    data_path: str = Field(..., description="Path to input data for inference")
    output_path: Optional[str] = Field(
        default=None,
        description="Output path for results (default: model_dir/inference_results)"
    )
    validation_mode: bool = Field(
        default=False,
        description="Force validation mode (requires ground truth)"
    )
    verify_integrity: bool = Field(
        default=True,
        description="Verify model integrity before inference"
    )
    output_format: str = Field(
        default="csv",
        description="Output format (csv or npy)"
    )

    # Preprocessing options. These are not cosmetic: inference applies the model's saved
    # scaler, so the data has to be read and scaled exactly as the training data was. A
    # request that omits `columns_are_features` or `input_normalization` when the model was
    # trained with them produces a run that completes and is wrong.
    input_header: Optional[int] = Field(
        default=None, description="Header row for input dataset (0-based)"
    )
    input_index_column: Optional[int] = Field(
        default=None, description="Index column for input dataset (0-based)"
    )
    columns_are_features: bool = Field(
        default=False, description="Columns represent features (not samples)"
    )
    input_normalization: str = Field(
        default="none",
        description="Input normalization method, matching the model's training run"
    )
    inputs_columns: Optional[List[str]] = Field(
        default=None, description="Columns to use as inputs"
    )
    classification: bool = Field(
        default=False, description="Classification mode instead of regression"
    )
    scores: Optional[str] = Field(
        default=None, description="Path to a scores file, for validation mode"
    )
    scores_header: Optional[int] = Field(
        default=None, description="Header row for the scores file (0-based)"
    )
    scores_index_column: Optional[int] = Field(
        default=None, description="Index column for the scores file (0-based)"
    )
    scores_normalization: str = Field(
        default="none", description="Normalization method for scores data"
    )

    def model_post_init(self, __context):
        """Validate that exactly one of model_path or model_id is provided."""
        if not self.model_path and not self.model_id:
            raise ValueError("Either model_path or model_id must be provided")
        if self.model_path and self.model_id:
            raise ValueError("Cannot specify both model_path and model_id")

    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "model_path": "/path/to/trained/models",
                "data_path": "/path/to/new/data.csv",
                "output_path": "/path/to/inference/results",
                "validation_mode": False,
                "verify_integrity": True,
                "output_format": "csv"
            }
        }
    )


class InferenceResponse(BaseModel):
    """
    API response model for inference results.

    This model defines the response structure containing inference
    results, metadata, and performance information.
    """

    status: str = Field(..., description="Inference execution status")
    mode: str = Field(..., description="Inference mode (inference or validation)")
    samples_processed: int = Field(..., description="Number of samples processed")
    predictions: List[float] = Field(
        ...,
        description=(
            "Ensemble predictions for the first target. Multi-target runs should read "
            "target_results, which carries every target"
        )
    )
    confidence_scores: Optional[List[float]] = Field(
        default=None,
        description="Confidence scores for the predictions above"
    )
    target_count: int = Field(
        default=1, description="Number of prediction targets the model produced"
    )
    target_results: Dict[str, Any] = Field(
        default_factory=dict,
        description="Per-target predictions and confidence scores, keyed by target name"
    )
    processing_time_ms: float = Field(..., description="Total processing time in milliseconds")
    throughput_samples_per_sec: float = Field(..., description="Processing throughput")
    model_info: Dict[str, Any] = Field(..., description="Model metadata information")
    output_files: Dict[str, str] = Field(..., description="Generated output file paths")
    validation_metrics: Optional[Dict[str, float]] = Field(
        default=None,
        description="Validation metrics (only for validation mode)"
    )

    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "status": "completed",
                "mode": "inference",
                "samples_processed": 100,
                "predictions": [0.75, 0.23, 0.91],
                "confidence_scores": [0.85, 0.72, 0.94],
                "processing_time_ms": 1250.5,
                "throughput_samples_per_sec": 80.0,
                "model_info": {
                    "model_path": "/path/to/models",
                    "loaded_models": 3
                },
                "output_files": {
                    "predictions_csv": "/results/predictions_20250805.csv",
                    "metadata_file": "/results/metadata_20250805.json"
                },
                "validation_metrics": None
            }
        }
    )


class StatisticalMapsRequest(BaseModel):
    """
    API model for statistical maps analysis requests.

    This model defines the request structure for creating region-based statistical maps
    using two-stage filtering, HDBSCAN clustering, and statistical analysis.
    """

    model_path: Optional[str] = Field(None, description="Path to trained model directory")
    model_id: Optional[str] = Field(None, description="Registry model ID (alternative to model_path)")
    input_data_path: str = Field(..., description="Path to input data file")
    output_folder: str = Field(..., description="Output folder for statistical maps")
    targets: List[str] = Field(..., description="Target variable names for analysis")

    # Statistical analysis parameters
    statistical_test: str = Field(
        default="mann-whitney",
        description="Statistical test method",
        pattern="^(mann-whitney|t-test)$"
    )
    visualization_threshold: float = Field(
        default=0.2,
        description="Confidence threshold for visualization filtering",
        ge=0.0
    )
    effect_size_threshold: float = Field(
        default=0.5,
        description="Prediction threshold for effect size filtering",
        ge=0.0
    )
    min_cluster_size: int = Field(
        default=3,
        description="Minimum cluster size for HDBSCAN clustering",
        gt=0
    )

    # Data format information
    input_type: str = Field(
        default="spreadsheet",
        description="Input data format type",
        pattern="^(nifti|image|spreadsheet)$"
    )

    def model_post_init(self, __context):
        """Validate that exactly one of model_path or model_id is provided."""
        if not self.model_path and not self.model_id:
            raise ValueError("Either model_path or model_id must be provided")
        if self.model_path and self.model_id:
            raise ValueError("Cannot specify both model_path and model_id")

    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "model_path": "/path/to/trained/model",
                "input_data_path": "/path/to/input/data.csv",
                "output_folder": "/path/to/statistical/maps/output",
                "targets": ["target_0", "target_1"],
                "statistical_test": "mann-whitney",
                "visualization_threshold": 0.2,
                "effect_size_threshold": 0.5,
                "min_cluster_size": 3,
                "input_type": "spreadsheet"
            }
        }
    )


class StatisticalMapsResponse(BaseModel):
    """
    API model for statistical maps analysis responses.

    This model defines the response structure containing statistical analysis results
    and metadata from region-based statistical maps generation.
    """

    statistical_results: Dict[str, Dict] = Field(
        ...,
        description="Statistical analysis results per target"
    )
    analysis_metadata: Dict[str, Any] = Field(
        ...,
        description="Analysis parameters and metadata"
    )
    processing_info: Dict[str, Any] = Field(
        ...,
        description="Processing information and performance metrics"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "statistical_results": {
                    "target_0": {
                        "clusters_analyzed": 2,
                        "filtering_results": {
                            "total_grid_points": 100,
                            "points_after_filtering": 25,
                            "clusters_found": 2,
                            "valid_clusters": 2
                        }
                    }
                },
                "analysis_metadata": {
                    "visualization_threshold": 0.2,
                    "effect_size_threshold": 0.5,
                    "min_cluster_size": 3,
                    "statistical_test": "mann-whitney"
                },
                "processing_info": {
                    "processing_time_ms": 5400.2,
                    "grid_points_generated": 10000,
                    "targets_processed": 2
                }
            }
        }
    )


class HeatmapsRequest(BaseModel):
    """
    API model for heatmaps analysis requests.

    This model defines the request structure for creating prediction and correlation
    grids using GridCreator and CorrelationGridCreator.
    """

    model_path: Optional[str] = Field(None, description="Path to trained model directory")
    model_id: Optional[str] = Field(None, description="Registry model ID (alternative to model_path)")
    input_data_path: str = Field(..., description="Path to input data file")
    output_folder: str = Field(..., description="Output folder for heatmaps")
    targets: List[str] = Field(..., description="Target variable names for analysis")

    # Grid generation parameters
    grid_size: tuple = Field(
        default=(100, 100),
        description="Grid size for coordinate generation"
    )
    denormalize_predictions: bool = Field(
        default=True,
        description="Apply denormalization to prediction values"
    )

    # Correlation analysis parameters
    correlation_methods: List[str] = Field(
        default=["pearson"],
        description="Correlation methods to use"
    )
    sigma_optimization: bool = Field(
        default=True,
        description="Enable sigma optimization for correlation grids"
    )
    max_sigma_trials: int = Field(
        default=100,
        description="Maximum trials for sigma optimization",
        gt=0
    )

    def model_post_init(self, __context):
        """Validate that exactly one of model_path or model_id is provided."""
        if not self.model_path and not self.model_id:
            raise ValueError("Either model_path or model_id must be provided")
        if self.model_path and self.model_id:
            raise ValueError("Cannot specify both model_path and model_id")

        # Validate correlation methods
        valid_methods = ["pearson", "spearman", "point-biserial"]
        for method in self.correlation_methods:
            if method not in valid_methods:
                raise ValueError(f"Invalid correlation method '{method}'. Valid methods: {valid_methods}")

    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "model_path": "/path/to/trained/model",
                "input_data_path": "/path/to/input/data.csv",
                "output_folder": "/path/to/heatmaps/output",
                "targets": ["target_0", "target_1"],
                "grid_size": [100, 100],
                "denormalize_predictions": True,
                "correlation_methods": ["pearson", "spearman"],
                "sigma_optimization": True,
                "max_sigma_trials": 100
            }
        }
    )


class HeatmapsResponse(BaseModel):
    """
    API model for heatmaps analysis responses.

    This model defines the response structure containing prediction grids
    and correlation grids results with metadata.
    """

    prediction_results: Dict[str, Dict] = Field(
        ...,
        description="Prediction grid results per target"
    )
    correlation_results: Dict[str, Dict] = Field(
        ...,
        description="Correlation grid results per target"
    )
    analysis_metadata: Dict[str, Any] = Field(
        ...,
        description="Analysis parameters and metadata"
    )
    processing_info: Dict[str, Any] = Field(
        ...,
        description="Processing information and performance metrics"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "prediction_results": {
                    "target_0": {
                        "grid_points_generated": 10000,
                        "prediction_range": [0.1, 0.9],
                        "confidence_range": [0.3, 1.0],
                        "output_files": ["prediction_grids/target_0_grid.csv"]
                    }
                },
                "correlation_results": {
                    "target_0": {
                        "correlation_methods": ["pearson", "spearman"],
                        "optimal_sigma": 0.15,
                        "correlation_range": [-0.8, 0.8],
                        "output_files": ["correlation_grids/target_0_pearson.csv"]
                    }
                },
                "analysis_metadata": {
                    "grid_size": [100, 100],
                    "denormalize_predictions": True,
                    "sigma_optimization": True
                },
                "processing_info": {
                    "processing_time_ms": 8500.3,
                    "targets_processed": 2,
                    "total_grid_points": 20000
                }
            }
        }
    )
