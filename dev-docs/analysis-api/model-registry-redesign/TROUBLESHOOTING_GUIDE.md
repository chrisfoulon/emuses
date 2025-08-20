# Model Registry Redesign - Troubleshooting Guide

## 🚨 Common Issues & Solutions

### Import and Dependency Issues

#### Issue 1: ModuleNotFoundError for Optional Dependencies
**Symptom**: 
```
ModuleNotFoundError: No module named 'fastapi_users'
ImportError: cannot import name 'User' from 'multi_user_service.models'
```

**Cause**: CI environment or local environment missing optional dependencies

**Solution**:
```python
# In conftest.py or test files
try:
    from multi_user_service.models import User
    from fastapi_users import FastAPIUsers
    MULTI_USER_AVAILABLE = True
except ImportError:
    MULTI_USER_AVAILABLE = False
    User = None
    FastAPIUsers = None

# In test files requiring optional dependencies
if not MULTI_USER_AVAILABLE:
    pytest.skip("multi-user-service not available", allow_module_level=True)
```

**Prevention**: Always check for optional dependencies before importing

#### Issue 2: ModelIOManager Base Path Error
**Symptom**:
```
TypeError: __init__() missing 1 required positional argument: 'base_path'
```

**Cause**: Creating ModelIOManager without required base_path parameter

**Solution**:
```python
# CORRECT: Always provide base_path
class LocalModelRegistry:
    def __init__(self, models_path: Path):
        self.models_path = models_path
        self.model_io = ModelIOManager(self.models_path)  # Provide base_path

# INCORRECT: Missing base_path
# self.model_io = ModelIOManager()  # This fails
```

**Prevention**: Check ModelIOManager constructor signature before instantiation

### Model Validation Issues

#### Issue 3: Manifest Format Incompatibility
**Symptom**:
```
KeyError: 'model_type'
ValidationError: Expected 'complete_emuses_model' format
```

**Cause**: Pipeline-generated manifests using old format, validate_model expecting new format

**Solution**: Use consistent manifest generation
```python
def _generate_manifest(self, model_path: Path) -> Dict[str, Any]:
    return {
        "model_id": str(uuid.uuid4()),
        "model_type": "complete_emuses_model",  # Use new format consistently
        "created_at": datetime.now(timezone.utc).isoformat(),
        "configuration_hash": self._calculate_config_hash(model_path),
        "content_hash": self._calculate_content_hash(model_path),
        # ... rest of standard format
    }
```

**Prevention**: Always generate manifests in the format that validate_model() expects

#### Issue 4: Hash Calculation Inconsistency
**Symptom**:
```
AssertionError: Hash mismatch between environments
Different hashes for same model content
```

**Cause**: Hash calculation affected by file system metadata, Python version, or binary differences

**Solution**: Use content-only hashing
```python
def _calculate_content_hash(self, model_path: Path) -> str:
    """Calculate hash based on file contents only, not metadata."""
    hash_md5 = hashlib.md5()
    
    # Sort files for consistent ordering
    model_files = sorted(model_path.glob("**/*"))
    
    for file_path in model_files:
        if file_path.is_file():
            # Hash file content, not metadata
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
    
    return f"md5:{hash_md5.hexdigest()}"
```

**Prevention**: Test hash consistency across environments

### Registry Operation Issues

#### Issue 5: Atomic Operation Failure
**Symptom**:
```
Registry left in inconsistent state after failure
Partial model installation with missing components
```

**Cause**: Multi-step operations failing mid-process without proper rollback

**Solution**: Implement atomic transactions
```python
class RegistryTransaction:
    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        self.backup_data = {}
        self.operations = []
    
    def __enter__(self):
        # Create backup of registry state
        self.backup_data = self._create_backup()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Exception occurred, rollback
            self._rollback()
            logger.error(f"Transaction rolled back due to: {exc_val}")
        # Normal exit, changes are committed
```

**Prevention**: Always use transaction context managers for multi-step operations

#### Issue 6: Concurrent Access Corruption
**Symptom**:
```
Registry corruption when multiple processes install simultaneously
Race conditions in registry updates
```

**Cause**: Multiple processes modifying registry without coordination

**Solution**: Implement file locking
```python
import fcntl
from contextlib import contextmanager

@contextmanager
def registry_lock(registry_path: Path):
    """Acquire exclusive lock on registry for safe concurrent access."""
    lock_path = registry_path / ".registry.lock"
    
    with open(lock_path, 'w') as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
```

**Prevention**: Always acquire locks before registry modifications

### Testing Issues

#### Issue 7: Test Isolation Failures
**Symptom**:
```
Tests pass individually but fail when run together
Shared state between test cases
```

**Cause**: Tests modifying global state or sharing resources

**Solution**: Use proper fixtures and cleanup
```python
@pytest.fixture
def isolated_registry(tmp_path):
    """Create isolated registry for each test."""
    registry_path = tmp_path / "test_registry"
    registry_path.mkdir()
    
    registry = LocalModelRegistry(registry_path)
    
    yield registry
    
    # Cleanup happens automatically with tmp_path
    
# Use the fixture in tests
def test_model_installation(isolated_registry):
    # Test has its own registry instance
    result = isolated_registry.install_model(test_model_path)
    assert result is not None
```

**Prevention**: Always use tmp_path fixtures for file operations, avoid global state

#### Issue 8: Performance Test Regression
**Symptom**:
```
Tests taking significantly longer than expected
Memory usage increasing during test runs
```

**Cause**: Large models in test fixtures, inefficient test setup

**Solution**: Use lightweight test fixtures
```python
@pytest.fixture
def minimal_test_model(tmp_path):
    """Create minimal model for testing, not full-size model."""
    model_path = tmp_path / "minimal_model"
    model_path.mkdir()
    
    # Create minimal files just for structure testing
    (model_path / "umap_model.pkl").write_bytes(b"fake_umap_data")
    (model_path / "hdbscan_model.pkl").write_bytes(b"fake_hdbscan_data")
    
    # Create manifest
    manifest = {
        "model_type": "complete_emuses_model",
        "created_at": datetime.now().isoformat()
    }
    (model_path / "manifest.json").write_text(json.dumps(manifest))
    
    return model_path
```

**Prevention**: Use minimal test fixtures, monitor test performance

### Integration Issues

#### Issue 9: CLI Command Not Found
**Symptom**:
```
Command 'emuses models install' not recognized
TypeError in CLI command execution
```

**Cause**: CLI commands not properly registered with Typer app

**Solution**: Verify command registration
```python
# Ensure command is properly added to app
from emuses.cli.models import models_app
from emuses.cli.main import app

app.add_typer(models_app, name="models")

# Verify command decorator is correct
@models_app.command("install")
def install_model_command(...):
    pass
```

**Prevention**: Test CLI commands with CliRunner in tests

#### Issue 10: API Endpoint Response Format Mismatch
**Symptom**:
```
422 Unprocessable Entity: Response validation error
Pydantic validation failed for response model
```

**Cause**: API endpoint returning data that doesn't match response model

**Solution**: Ensure response model matches actual data
```python
class ModelInfoResponse(BaseModel):
    model_id: str
    model_type: str
    created_at: datetime
    components: Dict[str, Any]
    
    class Config:
        # Allow extra fields for backward compatibility
        extra = "ignore"

@router.get("/models/{model_id}", response_model=ModelInfoResponse)
async def get_model_info(model_id: str):
    model_info = registry.get_model_info(model_id)
    
    # Ensure response matches model exactly
    return ModelInfoResponse(
        model_id=model_info.model_id,
        model_type=model_info.model_type,
        created_at=model_info.created_at,
        components=model_info.components
    )
```

**Prevention**: Validate response models match actual data structures

## 🔧 Debugging Techniques

### Enable Debug Logging
```python
import logging

# Enable debug logging for specific modules
logging.getLogger('emuses.tools.model_io').setLevel(logging.DEBUG)
logging.getLogger('emuses.tools.local_model_registry').setLevel(logging.DEBUG)

# Or enable for all EMUSES modules
logging.getLogger('emuses').setLevel(logging.DEBUG)
```

### Use Rich Console for Interactive Debugging
```python
from rich.console import Console
from rich import inspect

console = Console()

# Inspect objects during debugging
console.print("Registry state:")
inspect(registry, methods=True)

# Pretty print complex data structures
console.print(model_validation_result)
```

### Test with Real Data
```python
# Use real EMUSES pipeline output for testing
def test_with_real_pipeline_output():
    real_model_path = Path("tests/fixtures/real_emuses_output")
    
    validation = manager.validate_model(real_model_path)
    assert validation.is_complete_model
    
    # Test with different EMUSES versions
    for version in ["2.0.1", "2.1.0"]:
        version_path = Path(f"tests/fixtures/emuses_v{version}_output")
        if version_path.exists():
            validation = manager.validate_model(version_path)
            assert validation.is_complete_model
```

## 📊 Performance Monitoring

### Monitor Registry Operations
```python
import time
import psutil
from typing import Dict, Any

class PerformanceMonitor:
    def __init__(self):
        self.metrics: Dict[str, Any] = {}
    
    @contextmanager
    def monitor_operation(self, operation_name: str):
        """Monitor performance of registry operations."""
        start_time = time.perf_counter()
        start_memory = psutil.Process().memory_info().rss
        
        try:
            yield
        finally:
            end_time = time.perf_counter()
            end_memory = psutil.Process().memory_info().rss
            
            self.metrics[operation_name] = {
                'duration': end_time - start_time,
                'memory_delta': end_memory - start_memory,
                'timestamp': time.time()
            }
            
            # Log if operation is slower than expected
            if self.metrics[operation_name]['duration'] > 5.0:  # 5 second threshold
                logger.warning(
                    f"Slow operation detected: {operation_name} took "
                    f"{self.metrics[operation_name]['duration']:.2f}s"
                )

# Usage
monitor = PerformanceMonitor()

with monitor.monitor_operation("complete_model_validation"):
    result = manager.validate_model(large_model_path)
```

### Registry Health Checks
```python
def check_registry_health(registry: LocalModelRegistry) -> Dict[str, Any]:
    """Perform comprehensive registry health check."""
    health_report = {
        "status": "healthy",
        "issues": [],
        "metrics": {}
    }
    
    try:
        # Check registry accessibility
        models = registry.list_models()
        health_report["metrics"]["model_count"] = len(models)
        
        # Check for corrupted entries
        corrupted = []
        for model_id in models:
            try:
                info = registry.get_model_info(model_id)
                if not Path(info.physical_path).exists():
                    corrupted.append(model_id)
            except Exception as e:
                corrupted.append(model_id)
                
        if corrupted:
            health_report["issues"].append(f"Corrupted models: {corrupted}")
            health_report["status"] = "degraded"
            
        # Check disk space
        disk_usage = psutil.disk_usage(registry.models_path)
        if disk_usage.free < 1_000_000_000:  # Less than 1GB free
            health_report["issues"].append("Low disk space")
            health_report["status"] = "warning"
            
    except Exception as e:
        health_report["status"] = "unhealthy"
        health_report["issues"].append(f"Health check failed: {str(e)}")
    
    return health_report
```

## 📞 When to Seek Help

### Escalation Criteria
1. **Data Loss Risk**: Any issue that could corrupt existing model registry
2. **Performance Regression**: Operations taking >5x normal time
3. **Integration Failures**: Breaking changes affecting other EMUSES components
4. **Security Issues**: Potential for unauthorized model access or modification

### Information to Gather
- Full error traceback with context
- EMUSES version and Python environment details
- Registry state before/after issue
- Steps to reproduce the problem
- Expected vs actual behavior

### Temporary Workarounds
```python
# If atomic operations are failing, implement basic backup
def backup_registry_before_operation(registry_path: Path):
    backup_path = registry_path.parent / f"{registry_path.name}_backup_{int(time.time())}"
    shutil.copytree(registry_path, backup_path)
    return backup_path

# If hash calculations are inconsistent, use simpler approach temporarily  
def simple_content_hash(file_path: Path) -> str:
    """Simplified hash calculation for debugging."""
    return hashlib.md5(file_path.read_bytes()).hexdigest()
```

Remember: When in doubt, preserve data integrity over feature completeness. It's better to fail safely than to corrupt the registry.