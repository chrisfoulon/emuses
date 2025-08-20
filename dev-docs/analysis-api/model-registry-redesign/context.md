# Model Registry Redesign - Implementation Context

## Level 1: Plain English Summary

EMUSES generates complete machine learning models consisting of multiple interdependent components (UMAP dimensionality reduction, HDBSCAN clustering, and ensemble prediction models). Currently, the model registry incorrectly treats these components as separate "models" that can be installed individually. This creates duplicate installations, storage waste, and prevents users from sharing complete research analyses.

The redesign will treat complete EMUSES pipeline outputs as single installable units with intelligent deduplication based on training configuration and model content. Users will be able to install, share, and discover complete EMUSES models while the system prevents duplicate installations and provides access to physical model files for research purposes.

**Core Enhancement**: Transform from individual component registry to complete EMUSES model registry with content-based deduplication and intelligent model management.

## Level 2: Technical Architecture Overview

### **Complete EMUSES Model Concept**

A complete EMUSES model represents the entire output of a successful EMUSES pipeline run, containing:

| Component Type | Purpose | Files | Dependencies |
|----------------|---------|-------|--------------|
| **Dimensionality Reduction** | UMAP transform from high-dim features to 2D embeddings | `best_umap_model.joblib`, `embeddings.npy` | Training features |
| **Clustering** | HDBSCAN clustering of embeddings into meaningful groups | `hdbscan_model.joblib`, `cluster_labels.npy` | UMAP embeddings |
| **Prediction Ensemble** | Multi-target CV fold models for robust prediction | `target_N/best_pipeline_foldK.joblib` | UMAP embeddings |
| **Performance Context** | Cross-validation scores, optimization results | `performance_summary/` | All components |
| **Reproducibility** | Random seeds, data splits, configuration | `random_seeds.json`, `split_dataset/` | Pipeline execution |

### **Enhanced Registry Schema**

```python
# Current Schema (Individual Components)
{
  "model_id": "hdbscan_model_20250820_130405",
  "name": "hdbscan_model", 
  "type": "hdbscan",
  "version": "1.0.1"
}

# Enhanced Schema (Complete EMUSES Models)
{
  "model_id": "hcp_analysis_v1.2.3_abc123",
  "name": "HCP Psychological Analysis",
  "type": "emuses_complete_model",
  "version": "1.2.3",
  "content_hash": "sha256:abc123...",
  "config_hash": "sha256:def456...",
  "components": {
    "umap_model": {"path": "best_umap_model.joblib", "hash": "sha256:..."},
    "hdbscan_model": {"path": "hdbscan_model.joblib", "hash": "sha256:..."},
    "prediction_models": [/* CV fold models with hashes */],
    "embeddings": {"path": "embeddings.npy", "hash": "sha256:..."},
    "performance_data": {"path": "performance_summary/", "type": "directory"}
  }
}
```

### **Deduplication Strategy Architecture**

```python
# Three-tier deduplication approach:

# 1. Fast Configuration Check
config_signature = hash(training_config + data_source + hyperparameters)
existing_models = registry.find_by_config_hash(config_signature)

# 2. Content Verification  
content_signature = combined_hash(umap_hash + hdbscan_hash + prediction_hashes)
potential_duplicates = filter_by_content_similarity(existing_models)

# 3. User Decision Workflow
if potential_duplicates:
    action = prompt_user_decision(potential_duplicates, new_model_info)
    # Options: use_existing, install_variant, replace_existing, force_duplicate
```

## Level 3: Implementation Integration Examples

### **Enhanced ModelIOManager Integration**

```python
# Current: Component-level validation
manager = ModelIOManager(model_path)
manifest = manager.validate_model(model_path)
# Returns: {"name": "hdbscan_model", "type": "hdbscan", ...}

# Enhanced: Complete model detection and validation
def validate_complete_emuses_model(self, model_path: Path) -> Dict[str, Any]:
    """
    Validate complete EMUSES model directory structure.
    
    Detects EMUSES pipeline outputs and validates all components.
    """
    components_found = {}
    
    # Core component detection
    if (model_path / "best_umap_model.joblib").exists():
        components_found["umap_model"] = {
            "path": "best_umap_model.joblib",
            "hash": self._calculate_file_hash(model_path / "best_umap_model.joblib")
        }
    
    if (model_path / "hdbscan_model.joblib").exists():
        components_found["hdbscan_model"] = {
            "path": "hdbscan_model.joblib", 
            "hash": self._calculate_file_hash(model_path / "hdbscan_model.joblib")
        }
    
    # Prediction model ensemble detection
    prediction_models = []
    for target_dir in model_path.glob("target_*"):
        for fold_model in target_dir.glob("best_pipeline_fold*.joblib"):
            prediction_models.append({
                "path": str(fold_model.relative_to(model_path)),
                "hash": self._calculate_file_hash(fold_model)
            })
    
    if prediction_models:
        components_found["prediction_models"] = prediction_models
    
    # Performance data detection
    if (model_path / "performance_summary").exists():
        components_found["performance_data"] = {
            "path": "performance_summary/",
            "type": "directory",
            "hash": self._calculate_directory_hash(model_path / "performance_summary")
        }
    
    # EMUSES model detection logic
    required_components = ["umap_model", "hdbscan_model", "prediction_models"]
    is_complete_emuses = all(comp in components_found for comp in required_components)
    
    if is_complete_emuses:
        # Load configuration for complete model identification
        config_hash = self._extract_config_hash(model_path)
        content_hash = self._calculate_combined_hash(components_found)
        
        return {
            "name": self._extract_model_name(model_path),
            "version": self._detect_version(model_path),
            "type": "emuses_complete_model",
            "description": f"Complete EMUSES model with {len(components_found)} components",
            "content_hash": content_hash,
            "config_hash": config_hash,
            "components": components_found
        }
    else:
        # Fallback to individual component validation
        return self._validate_individual_component(model_path)
```

### **Enhanced Registry Installation with Deduplication**

```python
# Enhanced LocalModelRegistry.install_model() with deduplication
def install_model(self, model_path: Path, name: Optional[str] = None, 
                  force_duplicate: bool = False) -> Dict[str, Any]:
    """
    Install complete EMUSES model with intelligent deduplication.
    
    Args:
        model_path: Path to complete EMUSES model directory
        name: Optional custom name
        force_duplicate: Skip deduplication checks
    """
    # Phase 1: Validate and analyze model
    model_io = ModelIOManager(self.models_path)
    manifest = model_io.validate_model(model_path)
    
    if manifest.get("type") != "emuses_complete_model":
        # Handle individual components or unsupported models
        return self._install_legacy_model(model_path, name)
    
    # Phase 2: Deduplication check (unless forced)
    if not force_duplicate:
        duplicates = self._find_potential_duplicates(manifest)
        if duplicates:
            return self._handle_duplicate_models(duplicates, manifest, model_path)
    
    # Phase 3: Install new complete model
    model_id = self._generate_semantic_model_id(manifest)
    installation_result = model_io.install_model(model_path, self.models_path, name=name)
    
    # Phase 4: Register in enhanced schema
    model_info = {
        "model_id": model_id,
        "name": manifest["name"],
        "type": "emuses_complete_model",
        "version": manifest["version"],
        "content_hash": manifest["content_hash"],
        "config_hash": manifest["config_hash"],
        "components": manifest["components"],
        "installed_at": datetime.now(timezone.utc).isoformat() + "Z",
        "source_path": str(model_path),
        "manifest": manifest
    }
    
    # Update registry index
    index = self._load_index()
    index["models"][model_id] = model_info
    self._save_index(index)
    
    return {
        "status": "success",
        "model_id": model_id,
        "name": manifest["name"],
        "action": "installed_new_model",
        "components_count": len(manifest["components"]),
        "message": f"Successfully installed complete EMUSES model '{manifest['name']}'"
    }

def _find_potential_duplicates(self, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find models with similar configuration or content."""
    index = self._load_index()
    duplicates = []
    
    for existing_id, existing_model in index["models"].items():
        if existing_model.get("type") != "emuses_complete_model":
            continue
            
        # Configuration-based similarity
        if existing_model.get("config_hash") == manifest.get("config_hash"):
            duplicates.append({
                "model_id": existing_id,
                "similarity_type": "config_identical",
                "model_info": existing_model
            })
            
        # Content-based similarity  
        elif existing_model.get("content_hash") == manifest.get("content_hash"):
            duplicates.append({
                "model_id": existing_id,
                "similarity_type": "content_identical", 
                "model_info": existing_model
            })
    
    return duplicates

def _handle_duplicate_models(self, duplicates: List[Dict], manifest: Dict, 
                           model_path: Path) -> Dict[str, Any]:
    """Handle duplicate model detection with user interaction."""
    
    # In CLI mode: prompt user for decision
    if self._is_interactive_mode():
        return self._interactive_duplicate_resolution(duplicates, manifest, model_path)
    
    # In API/batch mode: return duplicate information for client decision
    return {
        "status": "duplicate_detected",
        "duplicates": duplicates,
        "new_model_info": manifest,
        "available_actions": [
            "use_existing",
            "install_variant", 
            "replace_existing",
            "force_duplicate"
        ]
    }
```

### **Enhanced CLI Commands**

```python
# Enhanced CLI for complete EMUSES model management

@models_app.command(name="install", help="Install complete EMUSES model")
def install_complete_model(
    model_path: Annotated[Path, typer.Argument(help="Path to EMUSES model directory")],
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="Custom model name")] = None,
    force: Annotated[bool, typer.Option("--force", help="Skip deduplication checks")] = False,
    interactive: Annotated[bool, typer.Option("--interactive/--batch", help="Interactive duplicate resolution")] = True
) -> None:
    """Install complete EMUSES model with intelligent deduplication."""
    
    registry = get_registry()
    
    console.print(f"🔍 Analyzing EMUSES model at [cyan]{model_path}[/cyan]...")
    
    result = registry.install_model(model_path, name=name, force_duplicate=force)
    
    if result["status"] == "duplicate_detected":
        if interactive:
            action = handle_duplicate_interactive(result["duplicates"], result["new_model_info"])
            # Re-run installation with user's decision
            result = registry.install_model(model_path, name=name, action=action)
        else:
            console.print("❌ Duplicate models detected. Use --force to install anyway or run interactively.")
            display_duplicate_summary(result["duplicates"])
            raise typer.Exit(1)
    
    if result["status"] == "success":
        console.print(f"✅ Successfully installed complete EMUSES model")
        console.print(f"   Model ID: [green]{result['model_id']}[/green]")
        console.print(f"   Components: [blue]{result['components_count']}[/blue]")
        console.print(f"   Action: [yellow]{result['action']}[/yellow]")
    else:
        console.print(f"❌ Installation failed: {result.get('message', 'Unknown error')}")
        raise typer.Exit(1)

def handle_duplicate_interactive(duplicates: List[Dict], new_model: Dict) -> str:
    """Interactive duplicate resolution workflow."""
    
    console.print("\n🔍 [yellow]Duplicate Models Detected[/yellow]")
    console.print(f"New model: [cyan]{new_model['name']} v{new_model['version']}[/cyan]")
    
    table = Table(title="Similar Existing Models")
    table.add_column("Model ID", style="blue")
    table.add_column("Name", style="green") 
    table.add_column("Version", style="yellow")
    table.add_column("Similarity", style="red")
    
    for i, dup in enumerate(duplicates, 1):
        model_info = dup["model_info"]
        table.add_row(
            model_info["model_id"][:20] + "...",
            model_info["name"],
            model_info.get("version", "unknown"),
            dup["similarity_type"]
        )
    
    console.print(table)
    
    choices = [
        "use_existing: Use existing similar model",
        "install_variant: Install as new variant/version",
        "replace_existing: Replace existing model", 
        "force_duplicate: Install duplicate anyway"
    ]
    
    choice = typer.prompt(
        "\nHow would you like to proceed?",
        type=click.Choice([c.split(':')[0] for c in choices])
    )
    
    return choice

@models_app.command(name="info", help="Get detailed information about EMUSES model")
def model_info_enhanced(
    model_id: Annotated[str, typer.Argument(help="Model ID or name")],
    show_components: Annotated[bool, typer.Option("--components", help="Show component details")] = False,
    show_path: Annotated[bool, typer.Option("--path", help="Show physical file path")] = False
) -> None:
    """Enhanced model info for complete EMUSES models."""
    
    registry = get_registry()
    model = registry.get_model_info(model_id)
    
    if not model:
        console.print(f"❌ Model not found: [red]{model_id}[/red]")
        raise typer.Exit(1)
    
    # Basic model information
    console.print(f"\n📊 [green]{model['name']}[/green] (ID: {model['model_id']})")
    console.print(f"Version: [yellow]{model.get('version', 'unknown')}[/yellow]")
    console.print(f"Type: [blue]{model.get('type', 'unknown')}[/blue]")
    console.print(f"Description: {model.get('description', 'No description')}")
    
    if model.get("type") == "emuses_complete_model":
        # Enhanced information for complete models
        components = model.get("components", {})
        console.print(f"\n🧩 Components ({len(components)}):")
        
        if show_components:
            for comp_type, comp_info in components.items():
                if isinstance(comp_info, list):
                    console.print(f"  • [cyan]{comp_type}[/cyan]: {len(comp_info)} files")
                    for item in comp_info[:3]:  # Show first 3
                        console.print(f"    - {item['path']}")
                    if len(comp_info) > 3:
                        console.print(f"    ... and {len(comp_info) - 3} more")
                else:
                    console.print(f"  • [cyan]{comp_type}[/cyan]: {comp_info['path']}")
        else:
            for comp_type in components:
                comp_count = len(components[comp_type]) if isinstance(components[comp_type], list) else 1
                console.print(f"  • [cyan]{comp_type}[/cyan] ({comp_count} files)")
    
    if show_path:
        physical_path = registry.get_model_physical_path(model_id)
        console.print(f"\n📁 Physical Location: [blue]{physical_path}[/blue]")
```

### **Integration with Inference and Analysis API**

```python
# Enhanced inference integration for complete EMUSES models
class InferenceStage:
    def load_complete_emuses_model(self, model_id: str) -> 'CompleteEmusesModel':
        """Load complete EMUSES model for inference."""
        
        registry = get_model_registry()
        model_info = registry.get_model_info(model_id)
        
        if model_info.get("type") != "emuses_complete_model":
            raise ValueError(f"Model {model_id} is not a complete EMUSES model")
        
        model_path = registry.get_model_physical_path(model_id)
        
        # Load all components
        umap_model = joblib.load(model_path / "best_umap_model.joblib")
        hdbscan_model = joblib.load(model_path / "hdbscan_model.joblib")
        
        # Load prediction model ensemble
        prediction_models = []
        for comp in model_info["components"]["prediction_models"]:
            model_file = model_path / comp["path"]
            prediction_models.append(joblib.load(model_file))
        
        return CompleteEmusesModel(
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            prediction_models=prediction_models,
            model_id=model_id,
            model_info=model_info
        )

# Integration with Analysis API Enhancement
@app.post("/api/v1/analysis/inference")
async def run_inference_on_complete_model(
    model_id: Annotated[str, Body(..., description="Complete EMUSES model ID")],
    input_data: Annotated[UploadFile, File(..., description="Input data for inference")]
) -> InferenceResponse:
    """Run inference using complete EMUSES model."""
    
    # Load complete model from registry
    inference_stage = InferenceStage(config=current_config)
    complete_model = inference_stage.load_complete_emuses_model(model_id)
    
    # Process input data through complete pipeline
    # UMAP → HDBSCAN → Prediction ensemble
    results = complete_model.predict(input_data)
    
    return InferenceResponse(
        model_id=model_id,
        predictions=results.predictions,
        embeddings=results.embeddings,
        cluster_assignments=results.clusters,
        confidence_scores=results.confidence
    )
```

This implementation context provides comprehensive integration examples for transforming EMUSES model registry from individual component management to complete model management with intelligent deduplication and enhanced user workflows.