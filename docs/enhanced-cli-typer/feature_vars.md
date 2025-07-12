# Enhanced CLI with Typer - Feature Variables

## Variable Map

```
FEATURE_SLUG=enhanced-cli-typer
PROJECT_NAME=emuses
FEATURE_TITLE=Enhanced CLI with Typer
BRANCH_NAME=feat/enhanced-cli-typer
CLI_MODULE_PATH=emuses/cli/main.py
LEGACY_CLI_PATH=emuses/scripts/main.py
SERVICE_MODULE_PATH=emuses/foundation_fastapi_service
COMMANDS=full,umap,clustering,heatmap,prediction
INTERACTIVE_MODE=guided workflow for novices
RICH_FEATURES=progress bars, colored output, table formatting
BACKWARD_COMPATIBILITY=100% command-line argument compatibility
SERVICE_INTEGRATION=HTTP client calls to FastAPI endpoints
SHELL_COMPLETION=bash,zsh,powershell
SPLIT=true
```

## Implementation Details

### Architecture
- **New CLI**: `emuses/cli/main.py` (single file, Typer-based)
- **Legacy CLI**: `emuses/scripts/main.py` (untouched, fallback)
- **Service Integration**: HTTP client calls to FastAPI service
- **Backward Compatibility**: 100% command-line argument compatibility

### Key Features
- Rich progress bars and colored output
- Shell completion for bash, zsh, powershell
- Interactive mode for novice users
- Enhanced error messages with preserved exit codes
- End-to-end execution (CLI manages FastAPI service internally)

### Commands to Implement
- `emuses full` - Complete pipeline (default)
- `emuses umap` - UMAP embedding only
- `emuses clustering` - Clustering on embeddings
- `emuses heatmap` - Heatmap generation
- `emuses prediction` - Prediction/inference
- `emuses interactive` - Guided workflow

### Design Decisions
- **Path Handling**: Typer-native with enhanced validation
- **Configuration**: Typer-native style for maintainability
- **Service Communication**: HTTP client calls for consistency
- **Error Handling**: Enhanced clarity, preserved exit codes
