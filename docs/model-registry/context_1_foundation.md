# Model Registry - Foundation & Local Mode Context

## Sub-Plan 1: Foundation & Local Mode Implementation

**Focus**: Local file-based registry and CLI integration  
**Duration**: 1 week  
**Dependencies**: ✅ Inference-pipeline completed, ModelIOManager available

## Verified Integration Points

### ModelIOManager Integration (✅ Available)
```python
# VERIFIED: Working integration pattern
from emuses.tools.model_io import ModelIOManager, ModelManifest

# Usage in LocalModelRegistry:
manager = ModelIOManager(base_path=model_dir)
try:
    manifest = manager.load_manifest(model_path)
    # manifest.name, manifest.version, manifest.model_type available
except FileNotFoundError:
    # Handle invalid model directories
```

### CLI Framework Integration (✅ Available)  
```python
# VERIFIED: Typer CLI structure supports command groups
from typer import Typer

models_app = Typer(help="Model registry operations")
main_app.add_typer(models_app, name="models")

@models_app.command(help="Install model from filesystem")
def install(model_path: Path, name: Optional[str] = None):
    # Implementation follows existing CLI patterns
```

### FileSystem Operations (✅ Standard Python)
```python
# Local registry storage structure:
# ~/.emuses/
# ├── models/
# │   ├── model-name-v1.0.0/     # Installed models  
# │   └── registry.json          # Local index
# └── config/
#     └── local_registry.yaml    # Configuration
```

## Implementation Components

### LocalModelRegistry Class
**Location**: `emuses/tools/local_model_registry.py`  
**Purpose**: File-based model discovery and installation  

**Key Methods**:
- `install_model(source_path, name=None)` - Copy and register model
- `list_models(filters=None)` - Query local registry with filtering
- `get_model_info(name, version="latest")` - Detailed model information
- `remove_model(name, version=None)` - Uninstall model
- `update_index()` - Rescan and rebuild registry

### CLI Commands Integration  
**Location**: `emuses/cli/main.py` (extend existing)  
**Pattern**: Add `models` command group to existing Typer app

**Commands**:
- `emuses models install /path/to/model --name custom-name`
- `emuses models list --type umap --tags neuroimaging`
- `emuses models info model-name --version 2.1.0`  
- `emuses models remove model-name`
- `emuses models update-index`

### Registry Index Management
**Location**: `~/.emuses/registry.json`  
**Purpose**: Fast model discovery without filesystem scanning

**Schema**:
```json
{
  "version": "1.0.0",
  "models": {
    "model-name-v1.0.0": {
      "name": "model-name",
      "version": "1.0.0", 
      "path": "/home/user/.emuses/models/model-name-v1.0.0",
      "manifest_hash": "sha256:...",
      "installed_at": "2025-08-07T10:30:00Z",
      "tags": ["fMRI", "motor-task"],
      "model_type": "full_pipeline",
      "size_mb": 145.2
    }
  }
}
```

## Integration with Existing Infrastructure

### Model Format Compatibility (✅ Verified)
**Dependency**: ModelIOManager validates model manifest  
**Integration**: LocalModelRegistry uses ModelIOManager for model validation

```python
# Validation workflow:
def install_model(self, source_path: Path, name: Optional[str] = None):
    # 1. Validate source has valid manifest
    manager = ModelIOManager(base_path=source_path.parent)
    manifest = manager.load_manifest(source_path)  # Raises if invalid
    
    # 2. Generate installation name
    install_name = name or f"{manifest.name}-v{manifest.version}"
    
    # 3. Copy to local registry
    target_path = self.models_dir / install_name
    shutil.copytree(source_path, target_path)
    
    # 4. Update registry index
    self._update_registry_index(install_name, manifest, target_path)
```

### CLI Security Integration (✅ Available)
**Dependency**: `emuses.cli.security.validate_path` function  
**Integration**: All path inputs validated for security

```python
from emuses.cli.security import validate_path

@models_app.command()
def install(model_path: Path, name: Optional[str] = None):
    # Security validation using existing patterns
    secure_path = validate_path(str(model_path))
    registry = LocalModelRegistry()
    registry.install_model(secure_path, name)
```

## Testing Strategy

### Unit Tests (`tests/model_registry/test_local_registry.py`)
- Registry file operations and index management
- Model installation and removal workflows  
- Version resolution and conflict handling
- Error handling for invalid models and paths

### Integration Tests (`tests/integration/test_local_registry_integration.py`)
- CLI command integration with registry operations
- ModelIOManager integration for manifest validation
- Cross-platform path handling and permissions

### File System Tests
- Registry directory creation and permissions
- Symlink handling for shared storage scenarios
- Cleanup and orphaned file management

## Success Criteria - Sub-Plan 1

**Functional Requirements**:
- [x] Local model installation from filesystem paths
- [x] Model discovery via `list` command with filtering
- [x] Model information display with manifest details
- [x] Model removal with registry cleanup
- [x] Index management with automatic updates

**Quality Requirements**:
- [x] All tests pass with >90% coverage
- [x] Flake8 compliance with NumPy docstrings
- [x] CLI security validation on all path inputs
- [x] Error handling for edge cases (invalid models, permissions)

**Integration Requirements**:
- [x] ModelIOManager integration for manifest validation
- [x] CLI framework integration without conflicts
- [x] File operations follow EMUSES security patterns
- [x] Compatible with existing inference pipeline workflows

This foundation provides the base registry functionality that subsequent sub-plans will extend with database and cloud capabilities.