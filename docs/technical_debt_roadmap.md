# Technical Debt and Improvement Roadmap

## Overview
This document tracks technical debt and improvement opportunities identified during real-world testing and cross-platform development of the EMUSES FastAPI service.

## High Priority Items

### 1. API/CLI Execution Path Unification
**Status**: 🔄 HIGH PRIORITY - Requires Implementation  
**Priority**: **CRITICAL** - Blocking production deployment with real-world datasets
**Impact**: Data consistency, user experience, maintenance burden, production readiness

**Problem Statement**:
- CLI uses `EMUSESPipeline` class for orchestration and data management
- API uses `PipelineRunner` that executes stages directly
- This divergence causes different data preprocessing, context setup, and validation behaviors
- **Real-world datasets fail** due to data alignment and missing value handling differences

**Root Cause Analysis**:
- `EMUSESPipeline.load_and_process_data()` handles comprehensive data preprocessing, normalization, and validation
- `EMUSESPipeline.split_and_prepare_data()` provides proper train/test splits with index tracking
- `EMUSESPipeline.run()` orchestrates stage execution with complete context setup (15+ keys)
- API bypasses this orchestration, leading to context and data alignment issues that break with complex datasets

**Proposed Solution**:
```python
# Current API approach (problematic):
class PipelineRunner:
    def _run_pipeline_in_process(self, context):
        # Manual argparse.Namespace construction
        args = argparse.Namespace()
        args.output_folder = str(output_folder)
        # Manual context setup with limited keys
        context.update({'prediction_train_features': ...})
        # Direct stage execution bypassing EMUSESPipeline
        umap_stage.run(context)
        heatmap_stage.run(context)
        prediction_stage.run(context)

# Proposed API approach (unified with CLI):
class PipelineRunner:
    def _run_pipeline_in_process(self, context):
        # Convert API context to EMUSESPipeline args
        args = self._context_to_emuses_args(context)
        
        # Create EMUSESPipeline instance  
        pipeline = EMUSESPipeline(args)
        
        # Set API-provided preprocessed data
        pipeline.input_matrix = context['input_matrix']
        pipeline.scores = context['scores']
        if 'labelled_input_matrix' in context:
            pipeline.labelled_input_matrix = context['labelled_input_matrix']
            
        # Let EMUSESPipeline handle all orchestration, context setup, and validation
        result_context = pipeline.run(progress_callback=self._api_progress_adapter)
        
        # Preserve API-specific metadata
        return self._merge_api_context(context, result_context)
```

**Implementation Steps**:
1. **Create args conversion utility**: `_context_to_emuses_args()` to map API configurations to EMUSESPipeline constructor parameters
2. **Implement progress callback adapter**: Bridge between EMUSESPipeline and API progress callback formats  
3. **Refactor PipelineRunner._run_pipeline_in_process()**: Use EMUSESPipeline internally while preserving API features
4. **Add context merge utility**: Combine EMUSESPipeline context with API-specific metadata (job_id, etc.)
5. **Update integration tests**: Enhance CLI vs API comparison to verify identical context and preprocessing
6. **Validate with real-world datasets**: Test HCP and other complex datasets through both interfaces
7. **Performance regression testing**: Ensure no API performance degradation from integration

**Acceptance Criteria**:
- ✅ API and CLI produce identical outputs for same inputs (numerical precision 1e-10)
- ✅ Real-world datasets (HCP, synthetic) process identically through both interfaces  
- ✅ All 15+ context keys properly set in API execution (matching CLI)
- ✅ Data preprocessing, normalization, and validation identical between API and CLI
- ✅ Random seed management consistent (reproducible results)
- ✅ No performance regression in API execution (< 5% overhead)
- ✅ All existing API tests continue to pass
- ✅ Background execution and job management features preserved

### 2. Cross-Platform File Locking
**Status**: ✅ COMPLETED
**Priority**: MEDIUM
**Impact**: Windows developer experience, CI/CD compatibility

**Implementation**:
- Added platform detection for file locking mechanisms
- Windows: Uses `msvcrt.locking()` for exclusive file access
- Unix/Linux: Uses `fcntl.LOCK_EX` for atomic metadata updates
- Graceful fallback when native file locking unavailable

**Files Modified**:
- `emuses/foundation_fastapi_service/job_manager.py`

### 3. Real-World Data Validation Enhancement
**Status**: 🔄 PENDING
**Priority**: MEDIUM
**Impact**: Production robustness, error reporting quality

**Problem Statement**:
- Synthetic test data doesn't expose validation edge cases
- Real datasets have missing values, type inconsistencies, alignment issues
- Error messages are not informative for data scientists

**Proposed Improvements**:
1. **Enhanced Data Validation Pipeline**:
   - Missing value detection and reporting
   - Data type validation and coercion
   - Index alignment verification
   - Shape consistency checks

2. **Improved Error Reporting**:
   - Specific error messages about data issues
   - Suggestions for data preparation
   - Column/feature-level error details

3. **Graceful Data Handling**:
   - Configurable missing value strategies
   - Automatic type coercion with warnings
   - Data quality reporting

## Medium Priority Items

### 4. Optuna Trial Optimization
**Status**: ✅ COMPLETED
**Priority**: LOW
**Impact**: Development velocity, CI performance

**Implementation**:
- Configurable trial counts for different environments
- Development default: 10 trials (vs 50+ in production)
- Faster iteration cycles during testing

### 5. Enhanced Integration Testing
**Status**: 🔄 ONGOING
**Priority**: MEDIUM
**Impact**: Regression prevention, confidence in releases

**Current State**:
- Basic CLI vs API comparison exists
- Real-world dataset testing ad-hoc

**Proposed Improvements**:
1. **Automated Real-World Testing**:
   - HCP dataset integration tests
   - Cross-platform test matrix
   - Performance regression detection

2. **Data Quality Testing**:
   - Edge case dataset generation
   - Boundary condition testing
   - Error scenario validation

## Technical Standards

### File Locking Standards
- **Unix/Linux**: Use `fcntl.LOCK_EX` for exclusive locking
- **Windows**: Use `msvcrt.locking()` with `msvcrt.LK_LOCK`
- **Fallback**: Thread-based locking when native mechanisms unavailable
- **Testing**: Verify locking behavior on target platforms

### Data Validation Standards
- **Input Validation**: Comprehensive checks before processing
- **Error Reporting**: Specific, actionable error messages
- **Context Preservation**: Maintain compatibility with existing patterns
- **Performance**: Validation overhead < 5% of total processing time

### Cross-Platform Compatibility
- **Development**: Support Windows, macOS, Linux
- **Production**: Primary target Linux, Windows compatibility for development
- **Testing**: CI matrix covering major platforms
- **Dependencies**: Platform-specific imports handled gracefully

## Monitoring and Metrics

### Success Metrics
- **API/CLI Consistency**: 100% identical outputs for same inputs
- **Cross-Platform Success Rate**: 100% test pass rate on Windows/Linux
- **Real-World Dataset Success**: >95% processing success rate
- **Error Report Quality**: User actionable error messages

### Technical Debt Metrics
- **Code Duplication**: API/CLI shared logic percentage
- **Test Coverage**: >95% coverage for core data handling
- **Platform-Specific Code**: Isolated to compatibility layers
- **Performance Impact**: <5% overhead from compatibility layers

## Review Schedule
- **Weekly**: Progress on high-priority items
- **Monthly**: Technical debt metrics review
- **Quarterly**: Complete roadmap reassessment
- **Release**: Acceptance criteria verification

---
*Last Updated*: Following HCP dataset integration testing and Windows compatibility improvements
*Next Review*: After API/CLI unification implementation
