"""Tests for FastAPI Pydantic models for foundation-fastapi-service."""

import pytest
from pydantic import BaseModel, ValidationError
from typing import Optional
from uuid import UUID, uuid4

from emuses.foundation_fastapi_service.models import (
    PipelineConfigRequest,
    JobSubmissionRequest,
    JobStatusResponse,
    ErrorResponse,
    FileUploadModel
)


class TestPipelineConfigModels:
    """Test suite for pipeline configuration models inheriting from PipelineConfig."""
    
    def test_pipeline_config_request_valid_classic_mode(self):
        """Test PipelineConfigRequest with valid classic mode configuration."""
        config_data = {
            "input_file": "data.csv",
            "scores_file": "scores.csv",
            "output_folder": "results",
            "umap_stage_enabled": True,
            "heatmap_stage_enabled": True,
            "prediction_stage_enabled": True
        }
        
        config = PipelineConfigRequest(**config_data)
        
        assert config.input_file == "data.csv"
        assert config.scores_file == "scores.csv"
        assert config.label_dataset_file is None
        assert config.output_folder == "results"
        assert config.umap_stage_enabled is True
        assert config.heatmap_stage_enabled is True
        assert config.prediction_stage_enabled is True
    
    def test_pipeline_config_request_valid_label_dataset_mode(self):
        """Test PipelineConfigRequest with valid label dataset mode configuration."""
        config_data = {
            "input_file": "data.csv",
            "scores_file": "scores.csv",
            "label_dataset_file": "labels.csv",
            "output_folder": "results"
        }
        
        config = PipelineConfigRequest(**config_data)
        
        assert config.label_dataset_file == "labels.csv"
        assert config.umap_stage_enabled is True  # default
        assert config.heatmap_stage_enabled is True  # default
        assert config.prediction_stage_enabled is True  # default
    
    def test_pipeline_config_request_missing_required_fields(self):
        """Test PipelineConfigRequest validation with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            PipelineConfigRequest()
        
        errors = exc_info.value.errors()
        required_fields = {"input_file", "scores_file", "output_folder"}
        error_fields = {error["loc"][0] for error in errors if error["type"] == "missing"}
        
        assert required_fields.issubset(error_fields)
    
    def test_pipeline_config_request_inherits_from_pipeline_config(self):
        """Test that PipelineConfigRequest properly inherits PipelineConfig structure."""
        from emuses.pipelines.pipeline_config import PipelineConfig
        
        # Create a PipelineConfigRequest
        api_config = PipelineConfigRequest(
            input_file="data.csv",
            scores_file="scores.csv",
            output_folder="results"
        )
        
        # Should be convertible to original PipelineConfig format
        config_dict = api_config.model_dump()
        
        # Filter to only include fields that PipelineConfig understands
        pipeline_config_fields = {
            'output_folder', 'sigma', 'fwhm', 'outer_folds', 'optuna_trials',
            'model_version', 'prefix', 'umap_jobs', 'hdbscan_jobs', 'umap_trials', 'hdbscan_trials'
        }
        
        # Extract only the fields that PipelineConfig expects
        filtered_config = {k: v for k, v in config_dict.items() if k in pipeline_config_fields}
        
        original_config = PipelineConfig(**filtered_config)
        
        # Verify that the key field is properly mapped
        assert original_config.output_folder == "results"
    
    def test_pipeline_config_request_stage_toggles(self):
        """Test that stage enable/disable flags work correctly."""
        config = PipelineConfigRequest(
            input_file="data.csv",
            scores_file="scores.csv",
            output_folder="results",
            umap_stage_enabled=False,
            heatmap_stage_enabled=True,
            prediction_stage_enabled=False
        )
        
        assert config.umap_stage_enabled is False
        assert config.heatmap_stage_enabled is True
        assert config.prediction_stage_enabled is False


class TestJobSubmissionAndStatusModels:
    """Test suite for job submission, status, and artifact response models."""
    
    def test_job_submission_request_valid(self):
        """Test JobSubmissionRequest with valid data."""
        from emuses.foundation_fastapi_service.models import JobSubmissionRequest
        
        # Valid job submission request
        job_request = JobSubmissionRequest(
            pipeline_config={
                "input_file": "data.csv",
                "scores_file": "scores.csv",
                "output_folder": "results"
            },
            job_name="test_job",
            description="Test job submission"
        )
        
        assert job_request.pipeline_config["input_file"] == "data.csv"
        assert job_request.job_name == "test_job"
        assert job_request.description == "Test job submission"
        
        # Test optional fields
        job_request_minimal = JobSubmissionRequest(
            pipeline_config={
                "input_file": "data.csv",
                "scores_file": "scores.csv",
                "output_folder": "results"
            }
        )
        assert job_request_minimal.job_name is None
        assert job_request_minimal.description is None
    
    def test_job_status_response_valid(self):
        """Test JobStatusResponse with valid data."""
        from emuses.foundation_fastapi_service.models import JobStatusResponse
        from datetime import datetime
        from uuid import uuid4
        
        job_id = uuid4()
        created_at = datetime.now()
        
        # Valid job status response
        status_response = JobStatusResponse(
            job_id=job_id,
            status="RUNNING",
            created_at=created_at,
            progress=0.65,
            current_stage="umap_stage",
            total_stages=3,
            message="Processing UMAP stage"
        )
        
        assert status_response.job_id == job_id
        assert status_response.status == "RUNNING"
        assert status_response.created_at == created_at
        assert status_response.progress == 0.65
        assert status_response.current_stage == "umap_stage"
        assert status_response.total_stages == 3
        assert status_response.message == "Processing UMAP stage"
        
        # Test with minimal fields
        status_minimal = JobStatusResponse(
            job_id=job_id,
            status="SUBMITTED",
            created_at=created_at
        )
        assert status_minimal.progress is None
        assert status_minimal.current_stage is None
        assert status_minimal.message is None


class TestErrorResponseModels:
    """Test suite for error response models with standardized error codes."""
    
    def test_error_response_valid(self):
        """Test ErrorResponse with valid data."""
        from emuses.foundation_fastapi_service.models import ErrorResponse
        
        # Valid error response
        error_response = ErrorResponse(
            error_code="VALIDATION_ERROR",
            message="Invalid input configuration",
            details="The field 'input_file' is required but was not provided",
            request_id="req_123456789"
        )
        
        assert error_response.error_code == "VALIDATION_ERROR"
        assert error_response.message == "Invalid input configuration"
        assert error_response.details == "The field 'input_file' is required but was not provided"
        assert error_response.request_id == "req_123456789"
        
        # Test with minimal fields
        error_minimal = ErrorResponse(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred"
        )
        assert error_minimal.error_code == "INTERNAL_ERROR"
        assert error_minimal.message == "An unexpected error occurred"
        assert error_minimal.details is None
        assert error_minimal.request_id is None


class TestFileUploadModels:
    """Test suite for file upload and multipart form data models with size limits."""
    
    def test_file_upload_model_valid(self):
        """Test FileUploadModel with valid data."""
        from emuses.foundation_fastapi_service.models import FileUploadModel
        
        # Valid file upload model
        file_upload = FileUploadModel(
            filename="data.csv",
            content_type="text/csv",
            size=1024000,  # 1MB
            field_name="input_file"
        )
        
        assert file_upload.filename == "data.csv"
        assert file_upload.content_type == "text/csv"
        assert file_upload.size == 1024000
        assert file_upload.field_name == "input_file"
        
        # Test size validation - should raise error for files over 100MB
        from pydantic import ValidationError
        import pytest
        
        with pytest.raises(ValidationError) as exc_info:
            FileUploadModel(
                filename="large_file.csv",
                content_type="text/csv",
                size=200 * 1024 * 1024,  # 200MB
                field_name="input_file"
            )
        
        assert "size" in str(exc_info.value)
        
        # Test with minimal fields
        file_upload_minimal = FileUploadModel(
            filename="data.csv",
            content_type="text/csv",
            size=1024
        )
        assert file_upload_minimal.filename == "data.csv"
        assert file_upload_minimal.field_name is None
