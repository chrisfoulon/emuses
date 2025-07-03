# Foundation FastAPI Service - Feature Variables

**Date**: 1 July 2025  
**Feature**: Foundation FastAPI Service  
**Branch**: feat/foundation-fastapi-service

## Variable Map

```bash
FEATURE_SLUG=foundation-fastapi-service
PROJECT_NAME=emuses
API_PREFIX=/api/v1
BACKGROUND_EXECUTOR=ProcessPoolExecutor
PROGRESS_METHOD=polling
CONFIG_STRATEGY=pydantic-settings
STORAGE_STRATEGY=job-scoped-folders
RESPONSE_FORMAT=versioned-json-envelopes
```

## Implementation Details

### API Endpoints
- **Full Pipeline**: `POST /api/v1/pipeline/jobs`
- **Single Stage**: `POST /api/v1/{stage}/jobs` (stage=umap|hdbscan|heat-map|prediction)
- **Status Check**: `GET /api/v1/jobs/{job_id}/status`
- **Live Progress**: `WS /api/v1/jobs/{job_id}/stream`
- **List Artifacts**: `GET /api/v1/jobs/{job_id}/artifacts`
- **Download**: `GET /api/v1/jobs/{job_id}/download/{filename}`

### Configuration & Processing
- **Background Processing**: ProcessPoolExecutor via `await loop.run_in_executor`
- **Configuration**: Pydantic BaseSettings + pydantic-settings-yaml plugin
- **Job IDs**: UUID-v4 for collision-safe generation
- **File Uploads**: Stream to temp dir, then move to `runs/{job_id}/input/`

### Storage & Artifacts
- **Job Folders**: `runs/{job_id}/{stage}/` with persistent `jobs.json`
- **Artifact Organization**: Stage-based subdirectories (umap/, hdbscan/, heat-map/, prediction/)
- **Downloads**: FileResponse locally, optional pre-signed URLs for cloud

### Progress & Error Handling
- **Polling**: Stage-level percentage via `GET /jobs/{job_id}/status`
- **WebSocket**: Real-time Optuna trial results and log streaming
- **Error Format**: HTTP status + JSON envelope with error codes
- **Failure Strategy**: Abort entire pipeline, mark job "error", save error.log

### Compatibility
- **100% Backward Compatible**: Existing CLI and Python imports unchanged
- **Context Pattern**: Maintain exact dictionary passing between stages
