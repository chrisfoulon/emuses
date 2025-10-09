# Command Discovery and Mapping

## Objective
Create a comprehensive map of all EMUSES CLI commands by comparing:
1. User-facing documentation (docs/CLI_REFERENCE.md)
2. Actual implementation (Typer commands in code)
3. Runtime help output

## 1. Documentation Analysis

### Extract Commands from CLI_REFERENCE.md
```bash
# Extract command examples from documentation
grep -n "emuses\s" docs/CLI_REFERENCE.md | head -20
```

### Key documented commands to verify:
- [ ] `emuses full` - Complete analysis pipeline
- [ ] `emuses umap` - Quick visualization  
- [ ] `emuses models list` - View models
- [ ] `emuses --help` - Get help
- [ ] Other commands from CLI_REFERENCE.md

## 2. Implementation Analysis

### Find all Typer command decorators
```bash
# Search for @app.command() decorators
grep -r "@.*\.command" emuses/cli/ --include="*.py"

# Alternative: search for def functions that might be commands  
grep -r "def.*(" emuses/cli/ --include="*.py" | grep -v "__"
```

### CLI Module Structure Analysis
```bash
# List all CLI modules
ls -la emuses/cli/

# Check main CLI entry point
head -20 emuses/cli/main.py

# Check for subcommand modules
ls -la emuses/cli/*commands.py
```

## 3. Runtime Discovery

### Get full help tree
```bash
# Main help
python -m emuses.cli --help > cli_help_main.txt

# Try to discover subcommands - these might exist:
python -m emuses.cli models --help > cli_help_models.txt 2>&1
python -m emuses.cli full --help > cli_help_full.txt 2>&1  
python -m emuses.cli umap --help > cli_help_umap.txt 2>&1
python -m emuses.cli admin --help > cli_help_admin.txt 2>&1
python -m emuses.cli workspace --help > cli_help_workspace.txt 2>&1

# Check for other potential subcommands based on module names
python -m emuses.cli service --help > cli_help_service.txt 2>&1
python -m emuses.cli interactive --help > cli_help_interactive.txt 2>&1
```

## 4. Cross-Reference Matrix

### Command Mapping Table
| Command | In Docs? | In Code? | Runtime Help? | Status | Notes |
|---------|----------|----------|---------------|--------|-------|
| `emuses --help` | ✅ | ✅ | ✅ | ✅ | Basic help working |
| `emuses full` | ✅ | ✅ | ✅ | ✅ | Main pipeline |
| `emuses umap` | ✅ | ✅ | ⏳ | ✅ | Visualization |
| `emuses models list` | ✅ | ✅ | ✅ | ✅ | Model registry |
| `emuses models` | ⚠️ | ✅ | ✅ | ✅ | Base models cmd (11+ subcommands) |
| `emuses admin` | ❌ | ✅ | ✅ | ⚠️ | Admin functions (undocumented) |
| `emuses workspace` | ❌ | ✅ | ✅ | ⚠️ | Workspace mgmt (undocumented) |
| `emuses heatmap` | ❌ | ✅ | ⏳ | ⚠️ | Create heatmap (undocumented) |
| `emuses inference` | ❌ | ✅ | ⏳ | ⚠️ | Run inference (undocumented) |
| `emuses verify` | ❌ | ✅ | ⏳ | ⚠️ | Verify model (undocumented) |
| `emuses info` | ❌ | ✅ | ⏳ | ⚠️ | Model info (undocumented) |
| `emuses cite` | ❌ | ✅ | ⏳ | ⚠️ | Citation (undocumented) |
| `emuses trace` | ❌ | ✅ | ⏳ | ⚠️ | Model provenance (undocumented) |
| `emuses reproduce` | ❌ | ✅ | ⏳ | ⚠️ | Reproduction guide (undocumented) |
| `emuses diff` | ❌ | ✅ | ⏳ | ⚠️ | Model diff (undocumented) |
| `emuses compare` | ❌ | ✅ | ⏳ | ⚠️ | Model compare (undocumented) |
| `emuses rerun` | ❌ | ✅ | ⏳ | ⚠️ | Rerun command (undocumented) |

### Legend
- ✅ Confirmed present
- ❌ Confirmed absent  
- ? Unknown/to be tested
- ⏳ Testing in progress
- ⚠️ Partial/issues found

## 5. Detailed Command Analysis

### For each discovered command, document:
1. **Full command syntax** from help output
2. **Required vs optional arguments**
3. **Subcommands** (if any)
4. **Examples** from help vs documentation
5. **Discrepancies** between docs and implementation

## 6. Discovery Results Log

### Main Commands Found
```
# To be filled in during testing
```

### Subcommands Found  
```
# To be filled in during testing
```

### Documentation Discrepancies
```
# To be filled in during testing
```

### Missing Commands
```
# Commands documented but not implemented
```

### Undocumented Commands
```
# Commands implemented but not documented
```

## 7. Next Steps Preparation

Based on discovery results:
1. **Priority commands** for basic functionality testing
2. **Command dependencies** (which need other commands to work)
3. **Data requirements** for each command
4. **Testing order** recommendations

### Recommended Testing Order
1. `emuses --help` (basic functionality)
2. `emuses models --help` (if exists)
3. `emuses full --help` (main pipeline help)
4. `emuses full` (battle-tested command)
5. Commands that use the trained model
6. Administrative/utility commands

## Files Generated
- `cli_help_main.txt` - Main help output
- `cli_help_*.txt` - Subcommand help outputs  
- `command_discovery_log.md` - Detailed findings

This discovery phase should take ~30 minutes and will inform all subsequent testing.
