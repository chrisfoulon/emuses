# Analysis API Enhancement - Implementation Context

## Level 1: Plain English Summary

EMUSES has comprehensive neuroimaging analysis functions (`run_kernel_heatmap_analysis` and `run_heatmap_analysis`) that generate statistical maps, effect size maps, and interactive visualizations. These functions are production-ready with 19-21 parameters each, but are only accessible through pipeline execution. The enhancement will expose these functions through FastAPI endpoints and CLI commands.

**Critical Infrastructure Issue**: ModelIOManager is missing `install_model()` and `validate_model()` methods that LocalModelRegistry expects, completely blocking model installation. Tests pass because they use mocks, hiding this missing implementation.

**Existing Infrastructure**: Mature FastAPI service, Typer CLI framework, comprehensive model registry database schema, artifact serving system, and security validation - all ready for extension.

## Level 2: API Integration Table

| Component | Purpose | Key Methods/Endpoints | Integration Points |
|-----------|---------|----------------------|-------------------|
| **Analysis Functions** | Generate statistical maps and visualizations | `run_kernel_heatmap_analysis()`, `run_heatmap_analysis()` | Pipeline stages, artifact generation |
| **FastAPI Service** | REST API endpoints | `POST /api/v1/analysis/{type}`, `GET /api/v1/analysis/{job_id}/artifacts/{filename}` | Authentication, artifact serving, job management |
| **CLI Commands** | Command-line interface | `emuses models analyze-kernel`, `emuses models analyze-correlation` | Typer integration, Rich console output |
| **ModelIOManager** | Model validation and installation | `validate_model()`, `install_model()` ⚠️ **MISSING** | LocalModelRegistry, artifact preservation |
| **Model Registry** | Analysis artifact storage | `install_model()`, `list_models()`, database persistence | Multi-user permissions, workspace isolation |
| **Artifact System** | Analysis result serving | File serving, permission control, format detection | FastAPI FileResponse, security validation |

## Level 3: Code Integration Examples

### **Analysis Function Signatures and Usage**

```python
# Location: /emuses/tools/kernel_regression_utils.py:641
def run_kernel_heatmap_analysis(
    embeddings,                    # np.ndarray: 2D latent space embeddings  
    scores_vectors_dict,           # dict: Score tags and binary vectors
    input_matrix,                  # np.ndarray: Original input data matrix
    output_folder,                 # str: Output directory path
    grid_size=100,                # int: Heatmap grid resolution
    sigma_range=None,             # List[float]: Kernel bandwidth range
    threshold=0.5,                # float: Confidence threshold
    uncertainty_penalty=0.5,      # float: Uncertainty weighting
    input_type="image",           # str: "image" | "nifti" | "spreadsheet"
    classification=False,         # bool: Regression vs classification
    # ... 11 additional parameters
) -> Tuple[Dict[str, Any], List[Dict]]:
    """Returns: (heatmap_data_dict, nested_cv_results)"""

# Location: /emuses/tools/correlation_maps_utils.py:205  
def run_heatmap_analysis(
    embeddings,                   # np.ndarray: 2D embeddings
    scores_vectors_dict,          # dict: Score vectors
    input_matrix,                 # np.ndarray: Original data
    output_folder,                # str: Output directory
    output_format_info,           # Various: Format specification
    clusterer,                    # object: Trained HDBSCAN clusterer
    cluster_labels,               # np.ndarray: Cluster assignments
    input_type="image",           # str: Input data type
    # ... 11 additional parameters  
) -> None:
    """Generates artifacts: effect_size maps, correlation grids, visualizations"""
```

### **FastAPI Endpoint Integration Pattern**

```python
# Expected implementation in /emuses/foundation_fastapi_service/app.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

class AnalysisRequest(BaseModel):
    model_path: str = Field(..., description="Path to trained model directory")
    analysis_type: str = Field(..., description="kernel or correlation", regex="^(kernel|correlation)$")
    output_folder: Optional[str] = Field(None, description="Custom output directory")
    
    # Analysis-specific parameters
    grid_size: int = Field(100, description="Heatmap grid resolution", ge=10, le=500)
    threshold: float = Field(0.5, description="Confidence threshold", ge=0.0, le=1.0)
    generate_plots: bool = Field(True, description="Generate visualization plots")
    
    # Advanced parameters with defaults
    sigma_range: Optional[List[float]] = Field(None, description="Kernel bandwidth range")
    effect_size_threshold: float = Field(0.5, ge=0.0, le=1.0)
    correlation_method: str = Field("pearson", regex="^(pearson|spearman)$")

class AnalysisResponse(BaseModel):
    job_id: str = Field(..., description="Unique analysis job identifier")
    status: str = Field(..., description="pending, running, completed, failed")
    analysis_type: str = Field(..., description="Type of analysis performed")
    created_at: str = Field(..., description="ISO timestamp of job creation")
    artifacts: Optional[List[str]] = Field(None, description="List of generated artifact filenames")

@app.post("/api/v1/analysis/kernel", status_code=201)
@conditional_rate_limit("10/hour")  
async def run_kernel_analysis(
    request: Request, analysis_request: AnalysisRequest
) -> AnalysisResponse:
    """Execute kernel regression heatmap analysis."""
    
    # Security validation
    model_path = Path(validate_path(analysis_request.model_path))
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="Model path not found")
    
    # Load model and metadata
    model_io = ModelIOManager(model_path.parent)
    model_data = model_io.load_model(model_path.name)
    
    # Parameter validation and preparation
    analysis_params = analysis_request.dict(exclude={'model_path', 'analysis_type'})
    
    # Execute analysis function
    try:
        heatmap_results, cv_results = run_kernel_heatmap_analysis(
            embeddings=model_data.metadata.embeddings,
            scores_vectors_dict=model_data.metadata.scores_vectors,
            input_matrix=model_data.metadata.input_matrix,
            output_folder=str(output_folder),
            **analysis_params
        )
        
        # Register analysis artifacts in model registry
        registry = get_model_registry()
        analysis_model_id = registry.install_analysis_artifacts(
            model_path=output_folder,
            parent_model_id=model_data.metadata.model_id,
            analysis_type="kernel_heatmap",
            results=heatmap_results
        )
        
        return AnalysisResponse(
            job_id=analysis_model_id,
            status="completed",
            analysis_type="kernel",
            created_at=datetime.now(timezone.utc).isoformat() + "Z",
            artifacts=list(heatmap_results.keys())
        )
        
    except Exception as e:
        logger.error(f"Analysis execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
```

### **CLI Command Integration Pattern**

```python
# Expected implementation in /emuses/cli/models_commands.py
from rich.progress import Progress, SpinnerColumn, TextColumn

@models_app.command(help="Generate kernel regression heatmap analysis")
def analyze_kernel(
    model_path: Annotated[Path, typer.Argument(help="Path to trained model directory")],
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output directory")] = None,
    grid_size: Annotated[int, typer.Option("--grid-size", help="Heatmap grid resolution")] = 100,
    threshold: Annotated[float, typer.Option("--threshold", help="Confidence threshold")] = 0.5,
    plots: Annotated[bool, typer.Option("--plots/--no-plots", help="Generate visualization plots")] = True,
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing analysis")] = False
) -> None:
    """Generate kernel regression heatmap analysis for a trained model."""
    
    # Security and path validation
    model_path = Path(validate_path(str(model_path)))
    if not model_path.exists():
        console.print(f"❌ Model not found: [red]{model_path}[/red]")
        raise typer.Exit(1)
    
    # Load model metadata
    try:
        model_io = ModelIOManager(model_path.parent)
        model_data = model_io.load_model(model_path.name)
        console.print(f"📊 Loaded model: [green]{model_data.metadata.model_name}[/green]")
    except Exception as e:
        console.print(f"❌ Failed to load model: [red]{str(e)}[/red]")
        raise typer.Exit(1)
    
    # Setup output directory
    if output is None:
        output = model_path / "analysis_kernel"
    output.mkdir(parents=True, exist_ok=force)
    
    # Execute analysis with progress indicator
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Generating kernel heatmap analysis...", total=None)
        
        try:
            heatmap_results, cv_results = run_kernel_heatmap_analysis(
                embeddings=model_data.metadata.embeddings,
                scores_vectors_dict=model_data.metadata.scores_vectors,
                input_matrix=model_data.metadata.input_matrix,
                output_folder=str(output),
                grid_size=grid_size,
                threshold=threshold,
                generate_plots=plots
            )
            
            progress.update(task, description="Registering analysis artifacts...")
            
            # Register artifacts in model registry  
            registry = get_model_registry()
            analysis_id = registry.install_analysis_artifacts(
                model_path=output,
                parent_model_id=model_data.metadata.model_id,
                analysis_type="kernel_heatmap"
            )
            
            progress.complete_task(task)
            
        except Exception as e:
            progress.stop()
            console.print(f"❌ Analysis failed: [red]{str(e)}[/red]")
            raise typer.Exit(1)
    
    # Success output
    console.print(f"✅ Analysis completed: [green]{analysis_id}[/green]")
    console.print(f"📁 Output directory: [blue]{output}[/blue]")
    
    # Display artifact summary
    artifacts = list(output.glob("*.nii.gz")) + list(output.glob("*.png")) + list(output.glob("*.csv"))
    if artifacts:
        console.print(f"📄 Generated {len(artifacts)} artifact files")
```

### **ModelIOManager Missing Methods Implementation**

```python
# CRITICAL: Must implement in /emuses/tools/model_io.py

def validate_model(self, model_path: Path) -> Dict[str, Any]:
    """
    Validate model directory structure and return manifest information.
    
    Args:
        model_path: Path to model directory or file
        
    Returns:
        Dict with keys: name, version, type, description, integrity_hash
        
    Raises:
        ValueError: If model structure is invalid
        FileNotFoundError: If required model files are missing
    """
    if not model_path.exists():
        raise FileNotFoundError(f"Model path does not exist: {model_path}")
    
    if model_path.is_file():
        model_path = model_path.parent
    
    # Check for existing manifest
    manifest_path = model_path / "model_manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            # Validate manifest structure
            required_keys = ["name", "version", "model_type", "description"]
            if not all(key in manifest for key in required_keys):
                raise ValueError(f"Invalid manifest structure in {manifest_path}")
            
            # Verify file integrity if hash present
            if "integrity_hash" in manifest:
                current_hash = self._calculate_directory_hash(model_path)
                if current_hash != manifest["integrity_hash"]:
                    logger.warning(f"Integrity hash mismatch for {model_path}")
            
            return {
                "name": manifest["name"],
                "version": manifest["version"], 
                "type": manifest["model_type"],
                "description": manifest["description"]
            }
            
        except (json.JSONDecodeError, IOError) as e:
            raise ValueError(f"Failed to read manifest: {str(e)}")
    
    else:
        # Generate manifest from model files
        return self._generate_manifest_from_directory(model_path)

def install_model(self, source_path: Path, destination_path: Path, 
                 name: Optional[str] = None) -> str:
    """
    Install model from source to destination directory.
    
    Args:
        source_path: Path to source model directory/file
        destination_path: Base directory for model installation
        name: Optional custom name for the model
        
    Returns:
        Unique model_id string for the installed model
        
    Raises:
        ValueError: If source model is invalid
        PermissionError: If destination is not writable
        FileExistsError: If model already exists and force=False
    """
    # Validate source model
    manifest = self.validate_model(source_path)
    
    # Generate unique model ID
    model_name = name or manifest["name"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_id = f"{model_name}_{timestamp}_{uuid.uuid4().hex[:8]}"
    
    # Create destination directory
    destination_path.mkdir(parents=True, exist_ok=True)
    target_path = destination_path / model_id
    
    if target_path.exists():
        raise FileExistsError(f"Model already exists: {target_path}")
    
    # Copy model files
    try:
        if source_path.is_file():
            # Single file model
            target_path.mkdir()
            shutil.copy2(source_path, target_path / source_path.name)
        else:
            # Directory model  
            shutil.copytree(source_path, target_path)
        
        # Update manifest with installation metadata
        manifest_path = target_path / "model_manifest.json"
        updated_manifest = {
            **manifest,
            "installed_at": datetime.now(timezone.utc).isoformat() + "Z",
            "model_id": model_id,
            "installation_path": str(target_path),
            "integrity_hash": self._calculate_directory_hash(target_path)
        }
        
        with open(manifest_path, 'w') as f:
            json.dump(updated_manifest, f, indent=2)
        
        logger.info(f"Model installed successfully: {model_id}")
        return model_id
        
    except (shutil.Error, OSError, IOError) as e:
        # Cleanup on failure
        if target_path.exists():
            shutil.rmtree(target_path, ignore_errors=True)
        raise ValueError(f"Model installation failed: {str(e)}")

def _generate_manifest_from_directory(self, model_path: Path) -> Dict[str, Any]:
    """Generate manifest from model directory structure."""
    
    # Detect model type from files
    model_files = list(model_path.glob("*.pkl")) + list(model_path.glob("*.joblib"))
    if not model_files:
        raise ValueError(f"No model files found in {model_path}")
    
    # Basic manifest structure
    return {
        "name": model_path.name,
        "version": "1.0.0",
        "type": "unknown",  # Would need more sophisticated detection
        "description": f"Model from {model_path.name}",
        "created_at": datetime.now(timezone.utc).isoformat() + "Z"
    }

def _calculate_directory_hash(self, directory: Path) -> str:
    """Calculate SHA-256 hash of directory contents."""
    hasher = hashlib.sha256()
    
    for file_path in sorted(directory.rglob("*")):
        if file_path.is_file():
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            hasher.update(str(file_path.relative_to(directory)).encode())
    
    return hasher.hexdigest()
```

## Maintenance Opportunities in Target Files

### High Priority (Address During Implementation)
- [ ] `/emuses/tools/model_io.py` - **Missing critical methods**: `install_model()` and `validate_model()` (BLOCKING)
- [ ] `/tests/model_registry/` - **Test gap**: Integration tests using real ModelIOManager instead of mocks

### Medium Priority (Consider for Boy Scout Rule)
- [ ] `/emuses/tools/correlation_maps_utils.py:205` - **Complex parameters**: 19 parameters could benefit from configuration object
- [ ] `/emuses/tools/kernel_regression_utils.py:641` - **Complex parameters**: 21 parameters could benefit from configuration object
- [ ] `/emuses/foundation_fastapi_service/app.py` - **Documentation**: API schema documentation for analysis endpoints

### Integration Architecture Notes

**Request Flow Pattern**:
```
API Request → Security Validation → Parameter Validation → Model Loading → 
Analysis Execution → Artifact Generation → Registry Installation → Response
```

**Artifact Storage Pattern**:
```
Model Directory/
├── model_manifest.json          # Model metadata
├── analysis_kernel/             # Analysis artifacts directory
│   ├── heatmap_data.json       # Analysis results
│   ├── stat_map_cluster_0.nii.gz
│   ├── stat_map_cluster_0.png
│   └── performance_metrics.json
└── analysis_correlation/        # Alternative analysis type
    └── ...
```

**Database Integration Pattern**:
```python
# Analysis artifacts as specialized model registry entries
model_registry.install_model(
    model_path=analysis_artifacts_path,
    name=f"{parent_model_name}_analysis_kernel",
    version="1.0.0",
    model_type="analysis_artifact_kernel",
    tags=["analysis", "heatmap", "kernel_regression"],
    metadata={
        "parent_model_id": parent_model_id,
        "analysis_parameters": analysis_params,
        "performance_metrics": cv_results
    }
)
```

This context provides comprehensive integration guidance for implementing the Analysis API Enhancement while addressing the critical ModelIOManager infrastructure issue that blocks current model installation workflows.