# EMUSESPipeline Integration Implementation Guide

## Overview
This document provides detailed implementation guidance for refactoring the EMUSES FastAPI service to use `EMUSESPipeline` internally, ensuring identical behavior between API and CLI execution paths.

## Current Architecture Issues

### API Execution Path (Problematic)
```python
# emuses/foundation_fastapi_service/pipeline_runner.py
class PipelineRunner:
    def _run_pipeline_in_process(self, context):
        # 1. Manual argparse.Namespace construction
        args = argparse.Namespace()
        args.output_folder = str(output_folder)
        args.umap_trials = config_dict.get('umap_trials', 10)
        # ... manual field assignment
        
        # 2. Limited context setup (5 keys vs EMUSESPipeline's 15+)
        context.update({
            'prediction_train_features': input_matrix,
            'prediction_train_labels': scores,
        })
        
        # 3. Direct stage execution bypassing EMUSESPipeline orchestration
        umap_stage.run(context)
        heatmap_stage.run(context)
        prediction_stage.run(context)
```

### CLI Execution Path (Correct)
```python
# emuses/main.py -> emuses/pipelines/emuses_pipeline.py
class EMUSESPipeline:
    def __init__(self, args):
        # Comprehensive configuration setup
        self.config = PipelineConfig(args)
        # Random seed management
        # Context initialization with metadata
        
    def load_and_process_data(self):
        # Data loading, normalization, validation
        # Dataset type detection
        # Preprocessing pipeline
        
    def split_and_prepare_data(self):
        # Train/test splitting with index tracking
        # Complete context setup with 15+ keys
        # Metadata preservation
        
    def run(self, progress_callback=None):
        # Stage orchestration with unified context
        # Progress tracking
        # Error handling and cleanup
```

## Implementation Strategy

### Phase 1: Core Integration

**Step 1: Create EMUSESPipeline Arguments Converter**
```python
# emuses/foundation_fastapi_service/pipeline_runner.py

def _context_to_emuses_args(self, context: Dict[str, Any]) -> argparse.Namespace:
    """Convert API context to EMUSESPipeline compatible arguments."""
    config_dict = context.get('config', {})
    
    args = argparse.Namespace()
    
    # Core paths and configuration
    args.output_folder = str(config_dict.get('output_folder'))
    args.input_dataset = "api_provided"  # Placeholder since data comes preprocessed
    
    # Optimization parameters
    args.umap_trials = config_dict.get('umap_trials', 10)
    args.hdbscan_trials = config_dict.get('hdbscan_trials', 5)
    args.optuna_trials = config_dict.get('optuna_trials', 10)
    
    # Prediction configuration
    args.prediction_optim_dict = config_dict.get('prediction_optim_dict', 'optim_dict_test')
    
    # Reproducibility
    args.random_state = config_dict.get('random_state', 42)
    args.test_size = config_dict.get('test_size', 0.2)
    
    # API-specific settings
    args.interactive_plot = False  # Always False for API
    args.prefix = config_dict.get('prefix', 'API')
    
    # Default values for required EMUSESPipeline args
    args.optim_dict = 'optim_dict_hcp'
    args.hdbscan_jobs = 4
    args.sigma = None
    args.fwhm = None
    args.outer_folds = 5
    args.model_version = "1.0.0"
    args.umap_jobs = None
    
    # Stage enablement
    args.umap_stage_enabled = config_dict.get('umap_stage_enabled', True)
    args.heatmap_stage_enabled = config_dict.get('heatmap_stage_enabled', True) 
    args.prediction_stage_enabled = config_dict.get('prediction_stage_enabled', True)
    
    # Label dataset mode (if applicable)
    args.label_dataset = context.get('label_dataset_path')
    
    return args
```

**Step 2: Create Progress Callback Adapter**
```python
def _create_emuses_progress_adapter(self, api_progress_callback):
    """Adapt EMUSESPipeline progress format to API format."""
    def emuses_progress_callback(stage_name=None, progress=None, message=None, **kwargs):
        """
        EMUSESPipeline calls: callback(stage_name="UMAPStage", progress=0.5, message="Trial 25/50")
        API expects: callback(progress=0.5, message="UMAPStage: Trial 25/50")
        """
        if progress is not None:
            formatted_message = f"{stage_name}: {message}" if stage_name and message else (message or "")
            api_progress_callback(progress, formatted_message)
    
    return emuses_progress_callback
```

**Step 3: Refactor Pipeline Execution**
```python
def _run_pipeline_in_process(self, context: Dict[str, Any], memory_limit_ratio: float) -> Dict[str, Any]:
    """Execute pipeline using EMUSESPipeline for CLI consistency."""
    
    try:
        # Convert API context to EMUSESPipeline arguments
        args = self._context_to_emuses_args(context)
        
        # Create EMUSESPipeline instance
        pipeline = EMUSESPipeline(args)
        
        # Set API-provided data directly (bypass EMUSESPipeline data loading)
        pipeline.input_matrix = context['input_matrix']
        pipeline.scores = context['scores']
        pipeline.dataset_type = context.get('dataset_type', 'matrix')
        
        # Handle label dataset mode if applicable
        if 'labelled_input_matrix' in context:
            pipeline.labelled_input_matrix = context['labelled_input_matrix']
            
        # Set paths and metadata that API manages differently
        pipeline.paths_list = context.get('paths_list', [])
        pipeline.output_format_info = context.get('output_format_info', [])
        
        # Create progress callback adapter
        progress_adapter = self._create_emuses_progress_adapter(
            lambda progress, message: self.logger.info(f"Progress: {progress:.1%} - {message}")
        )
        
        # Execute pipeline with EMUSESPipeline orchestration
        result_context = pipeline.run(progress_callback=progress_adapter)
        
        # Merge API-specific context with EMUSESPipeline results
        final_context = self._merge_api_emuses_context(context, result_context)
        
        self.logger.info("EMUSESPipeline execution completed successfully")
        return final_context
        
    except Exception as e:
        self.logger.error(f"EMUSESPipeline execution failed: {e}")
        raise
```

**Step 4: Context Merging Utility**
```python
def _merge_api_emuses_context(self, api_context: Dict[str, Any], emuses_context: Dict[str, Any]) -> Dict[str, Any]:
    """Merge API context with EMUSESPipeline context, preserving API metadata."""
    
    # Start with EMUSESPipeline context (complete stage outputs)
    merged_context = emuses_context.copy()
    
    # Preserve API-specific metadata
    merged_context.update({
        'job_id': api_context.get('job_id'),
        'api_request_metadata': api_context.get('api_metadata', {}),
        'original_api_config': api_context.get('config', {}),
    })
    
    # Ensure pipeline metadata is preserved and enhanced
    pipeline_metadata = merged_context.get('pipeline_metadata', {})
    pipeline_metadata.update({
        'execution_method': 'EMUSESPipeline_via_API',
        'api_integration_version': '1.0.0',
    })
    merged_context['pipeline_metadata'] = pipeline_metadata
    
    return merged_context
```

### Phase 2: Testing and Validation

**Step 1: Enhanced Integration Tests**
```python
# tests/integration/test_emuses_integration.py

class TestEMUSESPipelineIntegration:
    """Test suite for EMUSESPipeline integration in API."""
    
    def test_api_cli_numerical_equivalence(self):
        """Verify API using EMUSESPipeline produces identical numerical results to CLI."""
        # Prepare identical test dataset
        test_data = self.load_test_dataset()
        
        # Execute via CLI
        cli_results = self.run_cli_pipeline(test_data)
        
        # Execute via API with EMUSESPipeline integration
        api_results = self.run_api_pipeline_with_emuses(test_data)
        
        # Assert numerical equivalence
        self.assert_numerical_equivalence(cli_results, api_results, tolerance=1e-10)
        
    def test_context_completeness(self):
        """Verify API context contains all keys expected by stages."""
        api_context = self.run_api_get_context()
        cli_context = self.run_cli_get_context()
        
        # Check all CLI context keys present in API context
        missing_keys = set(cli_context.keys()) - set(api_context.keys())
        assert len(missing_keys) == 0, f"API missing context keys: {missing_keys}"
        
    def test_real_world_dataset_hcp(self):
        """Test API handles HCP dataset identically to CLI."""
        hcp_data = self.load_hcp_test_subset()
        
        cli_artifacts = self.run_cli_with_hcp(hcp_data)
        api_artifacts = self.run_api_with_hcp(hcp_data)
        
        self.assert_artifacts_identical(cli_artifacts, api_artifacts)
        
    def test_random_seed_reproducibility(self):
        """Verify consistent random seed handling between API and CLI."""
        test_data = self.load_test_dataset()
        seed = 12345
        
        # Run multiple times with same seed
        cli_run1 = self.run_cli_pipeline(test_data, random_state=seed)
        cli_run2 = self.run_cli_pipeline(test_data, random_state=seed)
        api_run1 = self.run_api_pipeline(test_data, random_state=seed)
        api_run2 = self.run_api_pipeline(test_data, random_state=seed)
        
        # Assert reproducibility within and across interfaces
        assert self.results_identical(cli_run1, cli_run2)
        assert self.results_identical(api_run1, api_run2)
        assert self.results_identical(cli_run1, api_run1)
```

**Step 2: Performance Regression Tests**
```python
def test_performance_regression(self):
    """Ensure EMUSESPipeline integration doesn't significantly impact API performance."""
    test_data = self.load_performance_test_dataset()
    
    # Measure current API performance (baseline)
    baseline_time = self.measure_api_execution_time(test_data)
    
    # Measure EMUSESPipeline integration performance  
    integration_time = self.measure_emuses_api_execution_time(test_data)
    
    # Assert performance overhead is acceptable (< 5%)
    overhead = (integration_time - baseline_time) / baseline_time
    assert overhead < 0.05, f"Performance regression: {overhead:.1%} overhead"
```

### Phase 3: Deployment and Monitoring

**Step 1: Feature Flag Implementation**
```python
# emuses/foundation_fastapi_service/pipeline_runner.py

class PipelineRunner:
    def __init__(self, job_manager, use_emuses_integration=True, **kwargs):
        """Initialize with EMUSESPipeline integration flag."""
        self.use_emuses_integration = use_emuses_integration
        # ... existing initialization
        
    async def _execute_pipeline_stages(self, context, progress_callback):
        """Execute pipeline with optional EMUSESPipeline integration."""
        if self.use_emuses_integration:
            return self._run_emuses_integrated_pipeline(context, progress_callback)
        else:
            return self._run_legacy_pipeline(context, progress_callback)  # Existing implementation
```

**Step 2: Monitoring and Validation**
```python
# Add logging and metrics for EMUSESPipeline integration
def _run_emuses_integrated_pipeline(self, context, progress_callback):
    """Execute pipeline using EMUSESPipeline with monitoring."""
    
    start_time = time.time()
    self.logger.info("Starting EMUSESPipeline integrated execution")
    
    try:
        result = self._run_pipeline_in_process(context, self.memory_limit_ratio)
        
        execution_time = time.time() - start_time
        self.logger.info(f"EMUSESPipeline execution completed in {execution_time:.2f}s")
        
        # Log context completeness metrics
        context_keys = len(result.keys())
        self.logger.info(f"Result context contains {context_keys} keys")
        
        return result
        
    except Exception as e:
        self.logger.error(f"EMUSESPipeline execution failed: {e}")
        # Optionally fall back to legacy implementation
        if self.fallback_on_failure:
            self.logger.warning("Falling back to legacy pipeline execution")
            return self._run_legacy_pipeline(context, progress_callback)
        raise
```

## Migration Strategy

### Development Phase
1. **Feature Branch**: Implement EMUSESPipeline integration on dedicated branch
2. **Unit Testing**: Comprehensive test suite for integration components
3. **Integration Testing**: CLI vs API equivalence validation
4. **Performance Testing**: Regression and load testing

### Staging Phase  
1. **Feature Flag**: Deploy with EMUSESPipeline integration disabled by default
2. **A/B Testing**: Run parallel executions comparing legacy vs integrated approaches
3. **Real-World Validation**: Test with production-like datasets
4. **Monitoring**: Track performance, error rates, and result consistency

### Production Phase
1. **Gradual Rollout**: Enable EMUSESPipeline integration for increasing percentage of requests
2. **Continuous Monitoring**: Track key metrics and user feedback
3. **Full Migration**: Switch to EMUSESPipeline integration as default
4. **Legacy Cleanup**: Remove old pipeline execution code after validation period

## Risk Mitigation

### Technical Risks
- **Performance Impact**: Mitigated by performance testing and gradual rollout
- **Context Compatibility**: Mitigated by comprehensive integration testing
- **Error Handling**: Mitigated by fallback mechanisms and extensive error testing

### Operational Risks
- **Production Issues**: Mitigated by feature flags and gradual rollout
- **User Experience**: Mitigated by maintaining API interface compatibility
- **Data Integrity**: Mitigated by numerical equivalence testing

## Success Metrics

### Technical Metrics
- ✅ **Numerical Equivalence**: API vs CLI results match within 1e-10 tolerance
- ✅ **Context Completeness**: API context contains all CLI context keys
- ✅ **Performance**: < 5% execution time overhead from integration
- ✅ **Reliability**: No increase in error rates

### Business Metrics
- ✅ **User Satisfaction**: No degradation in API user experience
- ✅ **Real-World Compatibility**: Complex datasets process successfully
- ✅ **Maintenance Efficiency**: Reduced technical debt and code duplication

---

*This implementation guide ensures the EMUSES FastAPI service achieves true API/CLI equivalence while maintaining production readiness and user experience.*
