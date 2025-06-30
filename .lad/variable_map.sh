#!/bin/bash
# LAD Variable Map for Foundation FastAPI Service Feature
# Generated on 30 June 2025
# Use: source .lad/variable_map.sh to load variables in shell scripts

# Core Feature Identity
export FEATURE_SLUG="foundation-fastapi-service"
export FEATURE_NAME="Foundation FastAPI Service"
export FEATURE_BRANCH="feat/foundation-fastapi-service"
export FEATURE_DESCRIPTION="FastAPI service layer wrapping EMUSES pipeline stages with REST endpoints, background tasks, and 100% backward compatibility"

# Implementation Paths
export SERVICE_LAYER_PATH="emuses/services/"
export API_LAYER_PATH="emuses/api/"
export MAIN_ENDPOINTS="embedding,heatmap,prediction"
export BACKGROUND_TASK_STRATEGY="async_with_process_pool"

# Security & Access
export AUTH_STRATEGY="public_endpoints"
export CORS_ENABLED="true"
export RATE_LIMITING="optional_disabled_by_default"

# Data Handling Configuration
export INPUT_FORMATS="json_arrays,file_uploads,nifti,csv,folders"
export RESPONSE_STRATEGY="json_small,file_response_medium,streaming_large"
export MAX_REQUEST_SIZE="configurable_no_default_limit"
export STORAGE_STRATEGY="file_based_with_download_endpoints"

# Background Tasks & Progress Tracking
export PROGRESS_TRACKING="polling_endpoints"
export TASK_CANCELLATION="checkpoint_resume"
export RESULT_PERSISTENCE="permanent_disk_storage"
export WEBSOCKET_SUPPORT="future_layer"
export WEBHOOK_SUPPORT="deferred"

# Performance & Concurrency
export CONCURRENCY_MODEL="1_uvicorn_worker_40_thread_pool"
export EXPECTED_LOAD="5_heavy_50_lightweight_polls"
export PATH_LIBRARY="pathlib"
export ASYNC_STRATEGY="run_in_executor_process_pool"
export CONFIG_STRATEGY="layered_code_yaml_env_cli_request"

# Error Handling Strategy
export OPTUNA_FAILURE_STRATEGY="no_special_handling"
export MEMORY_CONSTRAINTS="none_configurable_within_machine"
export TIMEOUT_STRATEGY="no_timeout_show_progress"
export WARNING_STRATEGY="collect_and_report"

# Backward Compatibility Requirements
export BACKWARD_COMPATIBILITY="100_percent_required"
export CLI_INTEGRATION="unchanged_existing_main_py"
export PYTHON_IMPORTS="unchanged_existing_imports"
export PIPELINE_CONTEXT="preserve_exact_context_pattern"

# Template Substitution Variables (for use in LAD prompts)
export DOC_BASENAME="foundation_fastapi_service_analysis"
export FEATURE_DRAFT_PARAGRAPH="Create a FastAPI service layer that wraps the existing EMUSES pipeline stages (EmbeddingStage for joint UMAP+HDBSCAN optimization, HeatmapStage for multi-target prediction, PredictionStage for inference) without modifying their core logic. The service should provide REST endpoints that accept Pydantic-validated requests containing optimization configurations (not individual parameters), call the existing stage.run() methods with proper context setup, and return structured responses. The EmbeddingStage performs joint UMAP+HDBSCAN optimization using Optuna nested trials and parameter dictionaries from config files. Include background task support for long-running operations like hyperparameter optimization. Must maintain 100% backward compatibility - existing CLI and Python imports continue working unchanged. The service acts as a thin translation layer between HTTP requests and the current pipeline context pattern, reusing 90%+ of existing computational code."

# Implementation Priority Files (from LAD guide)
export CONTEXT_FILES_FOR_EXPLORATION="emuses/pipelines/emuses_pipeline.py,emuses/pipelines/umap_stage.py,emuses/pipelines/heatmap_stage.py,emuses/pipelines/prediction_stage.py,emuses/config/optim_configs.py,emuses/tools/UMAP_utils.py,emuses/scripts/main.py,docs/LAD_Implementation_Guide.md"

echo "LAD Variable Map loaded for $FEATURE_NAME"
echo "Current branch: $(git branch --show-current)"
echo "Ready for implementation phase"
