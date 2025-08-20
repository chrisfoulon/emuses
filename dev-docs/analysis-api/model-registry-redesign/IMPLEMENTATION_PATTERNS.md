# EMUSES Codebase Patterns & Conventions

## 🏗️ Architecture Patterns

### Model Registry Integration Pattern
```python
# STANDARD: Factory pattern with mode detection
class ModelRegistryFactory:
    @staticmethod
    def create_registry(mode: str = "local") -> BaseModelRegistry:
        if mode == "local":
            return LocalModelRegistry(models_path)
        elif mode == "database": 
            return DatabaseModelRegistry(database_url)
        # ...

# STANDARD: Unified interface across modes
class BaseModelRegistry(ABC):
    @abstractmethod
    def install_model(self, model_path: Path, **kwargs) -> str:
        pass
```

### Error Handling Patterns
```python
# STANDARD: Specific exception hierarchy
class EmusesError(Exception):
    """Base exception for EMUSES"""
    pass

class ModelRegistryError(EmusesError):
    """Registry-specific errors"""
    pass
    
class ModelValidationError(ModelRegistryError):
    """Model validation failures"""
    pass

# STANDARD: Context logging with structured data
logger.error(
    "Model validation failed", 
    extra={
        "model_path": str(model_path),
        "validation_errors": errors,
        "operation": "validate_model"
    },
    exc_info=True
)
```

## 🧪 Testing Patterns

### Test File Organization
```
tests/
├── {component}/                    # Component-based organization
│   ├── test_{feature}.py          # Feature-specific tests
│   ├── test_{feature}_integration.py  # Integration tests
│   └── conftest.py                # Component-specific fixtures
├── fixtures/                      # Shared test data
└── conftest.py                    # Global fixtures
```

### Test Naming Conventions
```python
# PATTERN: Descriptive test method names
def test_install_model_with_custom_name_creates_correct_directory_structure():
def test_validate_model_returns_error_for_missing_components():
def test_registry_transaction_rollback_restores_previous_state():

# PATTERN: Test class organization
class TestModelIOManager:
    """Tests for ModelIOManager functionality"""
    
    class TestValidateModel:
        """Tests for validate_model method"""
        
    class TestInstallModel:
        """Tests for install_model method"""
```

### Fixture Patterns
```python
# STANDARD: Use tmp_path for file operations
@pytest.fixture
def temp_registry(tmp_path):
    models_path = tmp_path / "models"
    models_path.mkdir()
    return LocalModelRegistry(models_path)

# STANDARD: Parameterized tests for multiple scenarios
@pytest.mark.parametrize("model_type,expected_components", [
    ("complete_emuses", ["umap", "hdbscan", "prediction"]),
    ("individual_umap", ["umap"]),
    ("individual_hdbscan", ["hdbscan"])
])
def test_model_component_detection(model_type, expected_components):
    # Test implementation
```

## 🎯 CLI Patterns

### Command Structure
```python
# STANDARD: Typer app organization
from typer import Typer

app = Typer(name="emuses", help="EMUSES neuroimaging analysis tool")
models_app = Typer(name="models", help="Model management commands")
app.add_typer(models_app)

# STANDARD: Command definition pattern
@models_app.command("install")
def install_model(
    model_path: Path = typer.Argument(..., help="Path to model directory"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Custom model name"),
    force: bool = typer.Option(False, "--force", "-f", help="Force installation")
):
    """Install a model into the registry."""
```

### User Interaction Patterns
```python
# STANDARD: Rich console for output
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Success messages
console.print("✅ Model installed successfully", style="green")

# Warning messages  
console.print("⚠️  Potential duplicate detected", style="yellow")

# Error messages
console.print("❌ Installation failed", style="red")

# Progress indicators
with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    console=console
) as progress:
    task = progress.add_task("Installing model...", total=None)
    # ... long operation
```

### Interactive Prompts
```python
# STANDARD: Typer prompt patterns
import typer

# Simple confirmation
if not typer.confirm("This will overwrite existing model. Continue?"):
    typer.echo("Installation cancelled")
    raise typer.Abort()

# Choice selection
choice = typer.prompt(
    "How to handle duplicate",
    type=typer.Choice(["skip", "replace", "rename"]),
    default="skip"
)
```

## 🔌 API Patterns

### FastAPI Endpoint Structure
```python
# STANDARD: Router organization
from fastapi import APIRouter, HTTPException, Depends

router = APIRouter(prefix="/api/v1/models", tags=["Models"])

# STANDARD: Request/Response models
class ModelInstallRequest(BaseModel):
    source_path: str
    install_name: Optional[str] = None
    force_duplicates: bool = False

class ModelInstallResponse(BaseModel):
    model_id: str
    status: str
    message: str

# STANDARD: Endpoint pattern with dependency injection
@router.post("/install", response_model=ModelInstallResponse)
async def install_model(
    request: ModelInstallRequest,
    registry: LocalModelRegistry = Depends(get_model_registry)
) -> ModelInstallResponse:
    """Install model into registry."""
    try:
        model_id = await registry.install_model(
            Path(request.source_path),
            name=request.install_name
        )
        return ModelInstallResponse(
            model_id=model_id,
            status="success", 
            message="Model installed successfully"
        )
    except ModelValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Model installation failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

### Dependency Injection Patterns
```python
# STANDARD: Registry factory dependency
def get_model_registry() -> LocalModelRegistry:
    """Get model registry instance."""
    return ModelRegistryFactory.create_registry()

# STANDARD: User context dependency (when available)
async def get_current_user(token: str = Depends(oauth2_scheme)) -> Optional[User]:
    """Get current authenticated user."""
    # Implementation depends on auth system availability
```

## 📊 Data Patterns

### Configuration Management
```python
# STANDARD: Pydantic settings
from pydantic_settings import BaseSettings

class EmusesSettings(BaseSettings):
    models_path: Path = Path.home() / ".emuses" / "models"
    registry_mode: str = "local"  # local, database, cloud
    log_level: str = "INFO"
    
    class Config:
        env_prefix = "EMUSES_"
        case_sensitive = False

# STANDARD: Global settings instance
settings = EmusesSettings()
```

### Model Metadata Schema
```python
# STANDARD: Model registry entry format
{
    "model_id": "hcp_analysis_v1.2.3_abc123",
    "model_type": "complete_emuses_model",  # or "individual_umap", etc.
    "configuration_hash": "sha256:...",
    "content_hash": "sha256:...",
    "components": {
        "umap": {"path": "umap_model.pkl", "hash": "sha256:..."},
        "hdbscan": {"path": "hdbscan_model.pkl", "hash": "sha256:..."},
        "prediction": {"path": "prediction_ensemble/", "hash": "sha256:..."}
    },
    "metadata": {
        "created_at": "2025-08-20T...",
        "pipeline_version": "2.1.0",
        "training_data_hash": "sha256:...",
        "performance_metrics": {...}
    },
    "physical_path": "/path/to/model/directory"
}
```

## 🔧 Development Workflow Patterns

### Git Workflow
```bash
# STANDARD: Feature branch development
git checkout -b feature/specific-feature-name
# ... development work
git add -A
git commit -m "feat: specific feature implementation with clear description"
git push --set-upstream origin feature/specific-feature-name
```

### Testing Workflow
```bash
# STANDARD: Pre-push testing sequence
python scripts/dev_test_runner.py                    # Quick validation
pytest tests/specific_module/ -xvs                   # Targeted testing  
python scripts/test_runners/comprehensive_test_runner.py --all  # Full validation
```

### Code Quality Patterns
```python
# STANDARD: Docstring format (NumPy style)
def validate_model(self, model_path: Path) -> CompleteModelValidation:
    """Validate complete EMUSES model structure and components.
    
    Parameters
    ----------
    model_path : Path
        Path to the model directory to validate
        
    Returns
    -------
    CompleteModelValidation
        Validation result with component information and hashes
        
    Raises
    ------
    ModelValidationError
        If model structure is invalid or components are missing
        
    Examples
    --------
    >>> manager = ModelIOManager(models_path)
    >>> result = manager.validate_model(Path("./my_model"))
    >>> if result.is_complete_model:
    ...     print(f"Valid complete model with {len(result.components_found)} components")
    """
```

## 🚨 Anti-Patterns to Avoid

### Don't Do These
```python
# AVOID: Subprocess calls to pytest from within tests
def test_something():
    result = subprocess.run(["pytest", "other_test.py"])  # DON'T DO THIS
    
# AVOID: Hardcoded paths
model_path = "/home/user/.emuses/models"  # DON'T DO THIS
model_path = settings.models_path  # DO THIS INSTEAD

# AVOID: Silent error handling
try:
    result = risky_operation()
except Exception:
    pass  # DON'T DO THIS - at least log the error

# AVOID: Mixed sync/async without proper handling
async def async_function():
    sync_function()  # This might block the event loop
```

### Performance Considerations
```python
# PREFER: Lazy loading for large models
@property
def umap_model(self):
    if self._umap_model is None:
        self._umap_model = joblib.load(self.umap_path)
    return self._umap_model

# PREFER: Context managers for resource handling
with registry.begin_transaction() as tx:
    model_id = registry.install_model(model_data, tx)
    # Transaction automatically committed or rolled back
```

## 📝 Documentation Patterns

### README Structure
```markdown
# Component Name

Brief description of what this component does.

## Quick Start
Basic usage example

## Installation
If applicable

## API Reference
Key classes and methods

## Examples
Common use cases

## Testing
How to run tests
```

### Code Comments
```python
# GOOD: Explain why, not what
# Use content-based hashing to detect functionally similar models
# even when training randomness produces different file checksums
content_hash = self._calculate_content_hash(model_components)

# GOOD: Complex logic explanation  
# EMUSES models have interdependent components: UMAP transforms input data,
# HDBSCAN clusters the transformed data, predictions use both embeddings
# and cluster assignments. Components cannot be mixed between models.
if not self._validate_component_compatibility(components):
    raise ModelValidationError("Incompatible model components detected")
```

These patterns have been proven through the Sub-Plan 0A implementation and reflect EMUSES project conventions established over time.