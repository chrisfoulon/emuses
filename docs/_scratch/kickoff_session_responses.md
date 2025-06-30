# Foundation FastAPI Service - Kickoff Session Responses

**Date**: 30 June 2025  
**Feature**: Foundation FastAPI Service  
**Branch**: feat/foundation-fastapi-service

## User Responses to Design Questions

### 1. API Authentication & Security

**Should endpoints be public or require authentication?**
- They should be public.

**Any rate limiting requirements for long-running optimization tasks?**
- No, but if it would make it simpler for the future we can have options that would be disabled by default

**CORS policy for web frontend integration?**
- Yes if that doesn't negatively interact with local CLI or GUI uses

### 2. Data Input/Output Format

**Should endpoints accept file uploads (NIfTI, CSV) or only JSON arrays?**
- Yes and more, the inputs can be everything accepted in EMUSESPipeline (there can be folders and eventually we'll add more file types so it need to be easily scalable)

**Preferred response format for large embeddings/predictions (JSON, binary download, streaming)?**
- For EMUSES's mix of very large artifacts (multi-GB joblib models, hundreds-MB NIfTI images) and moderate-sized data (JSON metadata, CSVs, JPEG/HTML plots, tens-of-thousands-point embeddings), the optimal FastAPI response types are:
  - JSON/ORJSONResponse for small-to-medium JSON payloads (<10–20 MB)
  - FileResponse for disk-based downloads of single files (models, images, CSVs, plots)
  - StreamingResponse for chunked transfer of very large payloads (GB-scale binaries or array streams) to minimize memory usage

**Maximum request size limits for feature matrices?**
- Put an optional limit but there is none for now as it will run in local

### 3. Background Task Management

**Progress tracking requirements (websockets, polling endpoints, webhooks)?**
- Start with polling endpoints (GET /jobs/{id}/status) for immediate local feedback.
- Layer in WebSockets after you containerize or deploy EMUSES on a server—this requires only adding a WebSocketEndpoint and minor client code changes.
- Defer webhooks until you have a public-facing deployment and real external integration needs.

**Task cancellation support needed?**
- Yes, but we'd just resume with the files that were created before using the IO. We don't need an absolutely perfect resume function if we provide decent checkpoint file saving it should be fine.

**Result persistence duration (temporary, configurable retention)?**
- Results should be fully saved on disk and forever (at the discretion of the user)

### 4. Error Handling & Edge Cases

**How to handle Optuna optimization failures mid-trial?**
- We don't. The data preprocessing should ensure the training can run to completion. Failure to converge would just result is bad models, right? We can save the unique warnings to report them at the end though or if we can report them as they come in a way that would not spam the user.

**Memory constraints for large feature matrices?**
- Replied above. No constraint on size.

**Timeout handling for long-running optimizations?**
- No timeout but we should show the progress to the user (we should be able to count the max number of trials and number of variables to create models for to compute the number of iterations)

### 5. Performance Requirements

**Expected concurrent request load?**
- Keep defaults: 1 Uvicorn worker, 40-thread pool.
- Expect <5 heavy operations and up to ~50 lightweight polls in flight.

**Memory/CPU resource constraints?**
- Configurable within the machine limits.

**Caching strategy for repeated optimizations?**
- If the core code is not already doing it we should save the best model and parameters as we go but we don't need anything more complex than what Optuna provide.

## Design Fork Decisions

### 1. Path Handling: pathlib vs os.path
**Decision**: Yes, use pathlib.

### 2. Async Framework: asyncio vs synchronous
**Decision**: Convert the endpoint to async def and call Optuna via await loop.run_in_executor(ProcessPoolExecutor(), optimize_func, args…) to leverage all CPU cores while keeping the event loop free for status or health checks

### 3. Model Storage: In-memory vs File-based
**Decision**: Keep file-based storage with download endpoints (it's a research tool so we need high traceability)

### 4. Configuration Injection: Environment vs Request
**Decision**: Recommended Layered Configuration Strategy

1. **Code Defaults**: Continue defining your default hyperparameter dictionaries in .py files. These serve as the base layer of configuration, ensuring your pipeline always has sensible defaults.

2. **Configuration File**: Introduce a single YAML file (e.g. config.yaml) for environment-specific defaults and grouping of related settings. Unlike ad-hoc multiple files, this file is version-controlled and centrally located.

3. **Environment Variables**: Load secrets and deployment-specific values (API keys, database URIs, toggle flags) via environment variables, adhering to the Twelve-Factor App methodology's "store config in the environment" principle.

4. **CLI Overrides**: Use a CLI library (Typer) to accept hyperparameter overrides at runtime. CLI flags should take precedence over both file and env-var defaults, enabling quick experimentation without editing files.

5. **Request-Body Overrides**: For FastAPI endpoints, accept a (possibly partial) JSON payload that merges into your in-memory config object. This layer allows per-request customization when EMUSES is surfaced as an API.

## Key Implementation Principles

- **100% Backward Compatibility**: Existing CLI and Python imports must continue working unchanged
- **Context Pattern Preservation**: Maintain the exact context dictionary passing pattern between stages
- **File-Based Storage**: Keep all model artifacts on disk for research traceability
- **Async with ProcessPool**: Use async endpoints with ProcessPoolExecutor for CPU-intensive work
- **Polling-Based Progress**: Start with GET /jobs/{id}/status, add WebSockets later
- **Layered Configuration**: Code → YAML → env → CLI → request body hierarchy
- **Scalable Input Handling**: Support all current formats plus easy extension for future types
- **No Artificial Limits**: Let the machine resources be the constraint
- **Research-Focused Design**: Prioritize traceability and reproducibility over performance optimization
