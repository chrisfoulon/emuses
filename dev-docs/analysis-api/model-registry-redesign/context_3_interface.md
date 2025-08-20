# Model Registry Redesign - Phase 3 Interface Context

## Phase 3 Mission

**Integrate complete EMUSES model registry with all user interfaces (CLI, API, Inference) enabling seamless research workflows**

Phase 3 transforms the foundational complete model infrastructure into user-facing capabilities. This phase ensures researchers can easily work with complete models through familiar interfaces while maintaining full backward compatibility.

## Prerequisites from Previous Phases

### From Phase 1 Foundation
- **Complete Model Detection API**: `CompleteModelValidation` with diverse pipeline support
- **Atomic Transaction Framework**: Safe multi-step operations with rollback
- **Enhanced Registry Schema**: Complete and individual model support
- **Hash-based Indexing**: Efficient duplicate candidate identification

### From Phase 2 Deduplication  
- **Intelligent Deduplication Engine**: Config, content, and performance-based detection
- **User Interaction Framework**: Interactive and batch duplicate resolution
- **Performance Benchmarking**: Regression testing and monitoring
- **Concurrent Access Safety**: Mutex/locking for multi-user operations

## CLI Enhancement Architecture

### Enhanced Model Commands
```bash
# Complete model installation with intelligent duplicate handling
emuses models install /path/to/complete_model_output/
# → Interactive: "Potential duplicate detected (hcp_v1.2.1, 94% similar). Install anyway? [y/N/details]"
# → Result: "Installed: hcp_analysis_v1.2.3_abc123"

# Complete model information with component access
emuses models info hcp_analysis_v1.2.3_abc123
# → Shows: components, performance metrics, physical paths, duplicate relationships

# Component-level access within complete models  
emuses models components hcp_analysis_v1.2.3_abc123
# → Lists: umap, hdbscan, prediction_ensemble with individual access paths

# Registry cleanup and optimization
emuses models deduplicate
# → Interactive: "Found 3 duplicate groups. Review and remove? [y/N/details]"
```

### CLI User Experience Patterns
```python
class EnhancedModelsCLI:
    def install_complete_model(self, model_path: Path, options: InstallOptions) -> None:
        """Enhanced installation with duplicate handling"""
        
        # Phase 1: Detect complete model
        validation = model_io_manager.validate_model(model_path)
        if not validation.is_complete_model:
            console.print("⚠️  Individual components detected. Use --individual-mode or upgrade to complete model.")
            return
            
        # Phase 2: Check for duplicates  
        duplicates = deduplication_engine.detect_duplicates(validation)
        if duplicates and not options.force:
            resolution = self.prompt_duplicate_resolution(duplicates)
            if resolution == DuplicateResolutionOptions.SKIP_INSTALLATION:
                return
                
        # Phase 1: Install with atomic operations
        with registry.begin_transaction() as tx:
            model_id = registry.install_complete_model(validation, tx, options)
            console.print(f"✅ Installed: {model_id}")
```

## Inference Integration Architecture

### Complete EMUSES Model Class
```python
@dataclass
class CompleteEmusesModel:
    """Unified representation of complete EMUSES model for inference"""
    model_id: str
    registry: LocalModelRegistry
    _umap_model: Optional[Any] = None
    _hdbscan_model: Optional[Any] = None  
    _prediction_models: Optional[List[Any]] = None
    _embeddings: Optional[np.ndarray] = None
    _component_cache: Dict[str, Any] = field(default_factory=dict)
    
    def load_umap_model(self) -> Any:
        """Lazy load UMAP component with caching"""
        if self._umap_model is None:
            umap_path = self.registry.get_component_path(self.model_id, "umap")
            self._umap_model = joblib.load(umap_path)
        return self._umap_model
    
    def load_hdbscan_model(self) -> Any:
        """Lazy load HDBSCAN component with caching"""
        if self._hdbscan_model is None:
            hdbscan_path = self.registry.get_component_path(self.model_id, "hdbscan")
            self._hdbscan_model = joblib.load(hdbscan_path)
        return self._hdbscan_model
        
    def run_complete_inference(self, new_data: np.ndarray) -> InferenceResult:
        """Run full UMAP → HDBSCAN → Prediction pipeline"""
        # Load components on-demand
        umap_model = self.load_umap_model()
        hdbscan_model = self.load_hdbscan_model()
        prediction_models = self.load_prediction_models()
        
        # Run complete pipeline
        embeddings = umap_model.transform(new_data)
        cluster_labels = hdbscan_model.fit_predict(embeddings)
        predictions = self.ensemble_predict(prediction_models, embeddings, cluster_labels)
        
        return InferenceResult(
            embeddings=embeddings,
            cluster_labels=cluster_labels,
            predictions=predictions,
            model_id=self.model_id
        )
```

### InferenceStage Integration
```python
class EnhancedInferenceStage:
    def __init__(self, registry: LocalModelRegistry):
        self.registry = registry
        self.model_cache: Dict[str, CompleteEmusesModel] = {}
    
    def load_complete_model(self, model_id: str) -> CompleteEmusesModel:
        """Load complete model with component caching"""
        if model_id not in self.model_cache:
            # Verify model exists and is complete
            model_info = self.registry.get_model_info(model_id)
            if model_info.model_type != "complete_emuses_model":
                raise ValueError(f"Model {model_id} is not a complete EMUSES model")
                
            self.model_cache[model_id] = CompleteEmusesModel(model_id, self.registry)
        
        return self.model_cache[model_id]
    
    def run_inference_with_complete_model(self, model_id: str, new_data_path: Path) -> InferenceResult:
        """Enhanced inference using complete model from registry"""
        complete_model = self.load_complete_model(model_id)
        new_data = self.load_inference_data(new_data_path)
        return complete_model.run_complete_inference(new_data)
```

## API Integration Architecture

### FastAPI Complete Model Endpoints
```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/models/complete", tags=["Complete Models"])

class CompleteModelInstallRequest(BaseModel):
    source_path: str
    install_name: Optional[str] = None
    force_duplicates: bool = False
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.INTERACTIVE

class CompleteModelInfo(BaseModel):
    model_id: str
    model_type: str = "complete_emuses_model"
    configuration_hash: str
    content_hash: str
    components: Dict[str, ComponentInfo]
    created_at: datetime
    performance_metrics: Dict[str, Any]
    physical_paths: Dict[str, str]  # For research access

@router.post("/install", response_model=str)
async def install_complete_model(
    request: CompleteModelInstallRequest,
    registry: LocalModelRegistry = Depends(get_registry)
) -> str:
    """Install complete EMUSES model with duplicate handling"""
    
    # Phase 1: Validate complete model
    validation = await model_io_manager.validate_model(Path(request.source_path))
    if not validation.is_complete_model:
        raise HTTPException(400, "Source path does not contain complete EMUSES model")
    
    # Phase 2: Handle duplicates according to policy
    duplicates = await deduplication_engine.detect_duplicates(validation)
    if duplicates and not request.force_duplicates:
        resolution = await batch_duplicate_handler.handle_duplicates(duplicates, request.duplicate_policy)
        if resolution.action == DuplicateAction.SKIP:
            raise HTTPException(409, f"Duplicate model detected: {duplicates[0].model_id}")
    
    # Install with atomic transaction
    with registry.begin_transaction() as tx:
        model_id = await registry.install_complete_model(validation, tx, request.install_name)
        return model_id

@router.get("/{model_id}/info", response_model=CompleteModelInfo)
async def get_complete_model_info(
    model_id: str,
    registry: LocalModelRegistry = Depends(get_registry)
) -> CompleteModelInfo:
    """Get complete model information with component details"""
    model_info = await registry.get_complete_model_info(model_id)
    if not model_info:
        raise HTTPException(404, f"Complete model {model_id} not found")
    return model_info

@router.get("/{model_id}/components/{component_type}")
async def get_component_access(
    model_id: str, 
    component_type: str,
    registry: LocalModelRegistry = Depends(get_registry)
) -> ComponentAccessInfo:
    """Provide access to individual components within complete model"""
    component_info = await registry.get_component_access(model_id, component_type)
    if not component_info:
        raise HTTPException(404, f"Component {component_type} not found in model {model_id}")
    return component_info
```

### Analysis API Integration Points
```python
class AnalysisAPIIntegration:
    """Integration between complete model registry and analysis endpoints"""
    
    async def load_model_for_analysis(self, model_id: str) -> CompleteEmusesModel:
        """Load complete model for analysis operations"""
        return await self.inference_stage.load_complete_model(model_id)
    
    async def run_model_based_kernel_analysis(self, request: ModelBasedAnalysisRequest) -> AnalysisResult:
        """Run kernel analysis using existing complete model"""
        # Load complete model from registry
        complete_model = await self.load_model_for_analysis(request.complete_model_id)
        
        # Use model's UMAP and HDBSCAN for consistent analysis space
        new_data = await self.load_analysis_data(request.new_data_path)
        embeddings = complete_model.load_umap_model().transform(new_data)
        clusters = complete_model.load_hdbscan_model().fit_predict(embeddings)
        
        # Run kernel heatmap analysis
        analysis_result = await run_kernel_heatmap_analysis(
            embeddings=embeddings,
            cluster_labels=clusters,
            **request.analysis_parameters
        )
        
        # Associate result with complete model
        analysis_result.source_model_id = request.complete_model_id
        analysis_result.model_version = complete_model.get_model_version()
        
        return analysis_result
```

## Migration and Backward Compatibility

### Migration Strategy
```python
class RegistryMigrationManager:
    def __init__(self, registry: LocalModelRegistry):
        self.registry = registry
        
    def migrate_individual_to_complete_models(self) -> MigrationReport:
        """Migrate existing individual components to complete model format where possible"""
        
        # Find related individual components (same training session)
        component_groups = self.find_related_components()
        migration_report = MigrationReport()
        
        for group in component_groups:
            if self.is_complete_group(group):
                # Create complete model from individual components
                complete_model_id = self.create_complete_model_from_components(group)
                migration_report.successful_migrations.append(complete_model_id)
            else:
                # Keep as individual components
                migration_report.individual_components_retained.extend(group.component_ids)
        
        return migration_report
    
    def validate_migration_safety(self) -> List[MigrationRisk]:
        """Assess migration risks before proceeding"""
        risks = []
        
        # Check for storage space requirements
        complete_model_storage = self.estimate_complete_model_storage()
        if complete_model_storage > self.get_available_storage() * 0.8:
            risks.append(MigrationRisk.INSUFFICIENT_STORAGE)
            
        # Check for potential data loss
        orphaned_components = self.find_orphaned_components()
        if orphaned_components:
            risks.append(MigrationRisk.ORPHANED_COMPONENTS)
            
        return risks
```

### Legacy Compatibility Mode
```python
class LegacyCompatibilityLayer:
    """Maintains backward compatibility for existing individual component workflows"""
    
    def handle_individual_component_request(self, component_type: str, component_id: str) -> ComponentResponse:
        """Handle requests for individual components within complete models"""
        
        # Check if component is part of a complete model
        complete_model_id = self.find_parent_complete_model(component_id)
        
        if complete_model_id:
            # Provide component access through complete model
            return self.get_component_from_complete_model(complete_model_id, component_type)
        else:
            # Handle as legacy individual component
            return self.get_individual_component(component_id)
```

## Quality Assurance and Success Metrics

### User Experience Validation
```python
class UserExperienceValidator:
    def validate_cli_workflows(self) -> ValidationResult:
        """Test CLI workflows for both new and existing users"""
        
        scenarios = [
            self.test_new_user_complete_model_workflow,
            self.test_existing_user_individual_component_workflow,
            self.test_migration_from_individual_to_complete,
            self.test_duplicate_resolution_clarity,
            self.test_component_access_within_complete_models
        ]
        
        results = []
        for scenario in scenarios:
            result = scenario()
            results.append(result)
            
        return ValidationResult.aggregate(results)
```

### Integration Success Criteria
- **CLI Intuitive**: Both new complete model users and existing individual component users can accomplish their goals
- **API Comprehensive**: Programmatic complete model management supports all research workflow patterns
- **Inference Optimized**: Complete model loading performance maintains existing characteristics
- **Migration Seamless**: Existing individual component workflows continue working with clear upgrade paths
- **Analysis Integration**: Complete model registry enables model-based analysis workflows

### Performance Benchmarks
- CLI operations maintain <200ms response time for interactive commands
- API endpoints respond within existing SLA requirements  
- Inference loading complete models <5 seconds for typical model sizes
- Migration operations complete without data loss or corruption
- Analysis API integration adds <10% overhead to existing analysis workflows