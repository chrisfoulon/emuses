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
    predictions: List[float] = Field(..., description="Ensemble predictions")
    confidence_scores: Optional[List[float]] = Field(
        default=None, 
        description="Confidence scores for predictions"
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
