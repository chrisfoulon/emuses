# Model Registry Redesign - Phase 2 Deduplication Context

## Phase 2 Mission  

**Implement intelligent deduplication system preventing duplicate complete models while providing performance optimization and user control**

Phase 2 builds on Phase 1's foundation to solve the critical problem of duplicate model storage. With complete EMUSES models potentially being hundreds of megabytes, intelligent deduplication becomes essential for storage efficiency and user experience.

## Prerequisites from Phase 1 Foundation

### Required Deliverables from Phase 1
- **Complete Model Detection API**: Working `ModelIOManager.validate_model()` with diverse pipeline support
- **Atomic Transaction Framework**: `RegistryTransaction` with rollback capability
- **Hash-based Indexing**: Configuration and content hashes for efficient duplicate candidate identification  
- **Enhanced Registry Schema**: Support for complete model metadata and component tracking

### Integration Interfaces Available
```python
# From Phase 1 Foundation:
class CompleteModelValidation:
    configuration_hash: str    # For config-based duplicate detection
    content_hash: str         # For content similarity analysis
    components_found: Dict[str, Path]  # For component-level comparison
    
class RegistryTransaction:
    def rollback(self) -> None  # For safe multi-step operations
```

## Deduplication Architecture

### Multi-Level Duplicate Detection Strategy

#### 1. Configuration-Based Detection (Exact Duplicates)
```python
class ConfigurationDuplicateDetector:
    def detect_config_duplicates(self, new_model: CompleteModelValidation) -> List[str]:
        """Find models with identical configuration hashes - exact duplicates"""
        return registry.find_by_config_hash(new_model.configuration_hash)
```

**Logic**: Models with identical pipeline configuration, data preprocessing, and parameters are exact duplicates regardless of training randomness.

#### 2. Content-Based Similarity (Near Duplicates)  
```python
class ContentSimilarityDetector:
    def detect_content_similarity(self, new_model: CompleteModelValidation, threshold: float = 0.95) -> List[DuplicateMatch]:
        """Find models with similar content hashes - potential near duplicates"""
        similar_models = []
        for existing_hash in registry.get_content_hashes():
            similarity = self.calculate_hash_similarity(new_model.content_hash, existing_hash) 
            if similarity >= threshold:
                similar_models.append(DuplicateMatch(model_id=..., similarity=similarity))
        return similar_models
```

**Logic**: Models with similar performance fingerprints and component characteristics may represent duplicate training runs.

#### 3. Performance Fingerprint Comparison (Functional Duplicates)
```python
class PerformanceFingerprintDetector:
    def detect_performance_duplicates(self, new_model: CompleteModelValidation) -> List[DuplicateMatch]:
        """Compare clustering quality and prediction accuracy patterns"""
        new_fingerprint = self.extract_performance_fingerprint(new_model)
        candidates = []
        for existing in registry.get_all_complete_models():
            existing_fingerprint = self.extract_performance_fingerprint(existing)
            similarity = self.compare_fingerprints(new_fingerprint, existing_fingerprint)
            if similarity >= 0.90:  # 90% functional similarity threshold
                candidates.append(DuplicateMatch(model_id=existing.id, similarity=similarity))
        return candidates
```

**Logic**: Models producing similar clustering patterns and prediction accuracy may be functionally equivalent even with different configurations.

## User Interaction Workflow

### Interactive Duplicate Resolution
```python
@dataclass
class DuplicateResolutionOptions:
    INSTALL_ANYWAY = "install"      # Install despite duplicates
    SKIP_INSTALLATION = "skip"      # Skip this installation
    REPLACE_EXISTING = "replace"    # Replace the duplicate with new version
    MERGE_METADATA = "merge"        # Combine metadata, keep best performing

class InteractiveDuplicateResolver:
    def resolve_duplicates(self, matches: List[DuplicateMatch]) -> DuplicateResolutionOptions:
        """Present user with clear choices for duplicate handling"""
        console.print("🔍 Potential duplicate models detected:")
        for match in matches:
            console.print(f"  • {match.model_id} (similarity: {match.similarity:.2%})")
            console.print(f"    Created: {match.created_at}, Performance: {match.performance_summary}")
        
        return Prompt.ask("How would you like to proceed?", choices=list(DuplicateResolutionOptions))
```

### Batch/API Duplicate Handling
```python
class BatchDuplicateHandler:
    def handle_duplicates_batch(self, matches: List[DuplicateMatch], policy: DuplicatePolicy) -> InstallationDecision:
        """Handle duplicates according to configured policy for API/batch usage"""
        if policy == DuplicatePolicy.SKIP_DUPLICATES:
            return InstallationDecision.SKIP
        elif policy == DuplicatePolicy.ALWAYS_INSTALL:
            return InstallationDecision.INSTALL_WITH_SUFFIX
        elif policy == DuplicatePolicy.REPLACE_IF_BETTER:
            best_match = self.find_best_performing(matches)
            return InstallationDecision.REPLACE if new_is_better else InstallationDecision.SKIP
```

## Performance Optimization Framework

### Benchmarking and Regression Testing
```python
class PerformanceBenchmark:
    def __init__(self):
        self.baseline_metrics = self.load_baseline_performance()
    
    def benchmark_operation(self, operation_name: str, operation: Callable) -> PerformanceResult:
        """Measure operation performance and compare to baseline"""
        start_time = time.perf_counter()
        memory_before = psutil.Process().memory_info().rss
        
        result = operation()
        
        end_time = time.perf_counter()
        memory_after = psutil.Process().memory_info().rss
        
        metrics = PerformanceResult(
            operation=operation_name,
            duration=end_time - start_time,
            memory_delta=memory_after - memory_before,
            baseline_duration=self.baseline_metrics.get(operation_name, {}).get('duration'),
            regression_threshold=1.2  # 20% performance degradation threshold
        )
        
        if metrics.is_regression():
            logger.warning(f"Performance regression detected in {operation_name}: {metrics.regression_percent:.1%}")
            
        return metrics
```

### Storage Optimization Strategies
```python
class StorageOptimizer:
    def optimize_complete_model_storage(self, model_data: CompleteModelData) -> OptimizationResult:
        """Optimize storage for complete models with component sharing where possible"""
        
        # Check for sharable components (identical UMAP/HDBSCAN models)
        sharable_components = self.find_sharable_components(model_data)
        
        if sharable_components:
            # Create hard links to shared components instead of duplicating
            return self.create_shared_component_installation(model_data, sharable_components)
        else:
            # Standard complete model installation
            return self.create_standard_installation(model_data)
```

## Concurrent Access Safety

### Mutex/Locking Implementation
```python
import threading
from contextlib import contextmanager

class RegistryLockManager:
    def __init__(self):
        self._locks: Dict[str, threading.RLock] = {}
        self._global_lock = threading.RLock()
    
    @contextmanager
    def model_lock(self, model_id: str):
        """Acquire lock for specific model operations"""
        with self._global_lock:
            if model_id not in self._locks:
                self._locks[model_id] = threading.RLock()
            model_lock = self._locks[model_id]
        
        with model_lock:
            yield
    
    @contextmanager 
    def registry_write_lock(self):
        """Acquire global write lock for registry modifications"""
        with self._global_lock:
            yield
```

### Concurrent Safety Testing
```python
class ConcurrentSafetyTester:
    def test_concurrent_installations(self):
        """Test multiple simultaneous complete model installations"""
        import concurrent.futures
        
        models = self.generate_test_models(count=5)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self.install_complete_model, model) for model in models]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Verify registry consistency after concurrent operations
        self.verify_registry_integrity()
```

## Integration Points for Phase 3

### CLI Integration Requirements
Phase 2 provides Phase 3 with:
- **Deduplication Engine API**: Complete duplicate detection and resolution workflow
- **Interactive Resolution**: User interaction patterns for CLI duplicate prompts
- **Performance Monitoring**: Benchmarking framework for operation monitoring
- **Concurrent Safety**: Lock management for multi-user registry operations

### Expected Phase 2 Deliverables to Phase 3
1. **Working Deduplication Engine**: Config, content, and performance-based duplicate detection
2. **User Interaction Framework**: Interactive and batch duplicate resolution workflows
3. **Performance Benchmarking**: Regression testing and optimization monitoring
4. **Concurrent Access Safety**: Mutex/locking preventing registry corruption

## Quality Assurance Focus

### Critical Testing Scenarios
1. **Duplicate Detection Accuracy**: Test with models of varying similarity levels
2. **Performance Regression**: Ensure <20% impact on registry operations
3. **Concurrent Safety**: Multiple simultaneous installations without corruption
4. **User Experience**: Clear duplicate resolution choices with appropriate information

### Success Validation
- Duplicate detection false positive rate <5% with diverse model scenarios
- Interactive duplicate resolution provides clear user choices and consequences  
- Performance benchmarking framework identifies regressions automatically
- Concurrent access testing passes with mutex/locking implementation