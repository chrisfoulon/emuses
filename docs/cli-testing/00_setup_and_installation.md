# Setup and Installation Testing

## Prerequisites
Before testing EMUSES CLI functionality,### Testing Results Log

### Setup Test Results
| Test | Command | Status | Notes |
|------|---------|--------|-------|
| Direct CLI | `emuses --help` | ⚠️ | No visible output |
| Python module | `python -m emuses.cli --help` | ⚠️ | No visible output |
| Installation | `pip install -e .` | ✅ | Already installed (dev mode) |
| Dependencies | Core imports | ✅ | numpy, pandas, sklearn, typer OK |
| EMUSES import | `import emuses` | ✅ | Module imports successfully |
| Test data access | Path check | ⏳ | To test in next phase |
| Output directory | `/tmp/` setup | ✅ | Created and permissions set | ensure the environment is properly configured.

## 1. Environment Verification

### Check Current Environment
```bash
# Verify we're in the correct directory
pwd
# Expected: /mnt/c/Users/Tolhsadum/PycharmProjects/emuses

# Check Python version
python --version
# Expected: Python 3.11.x (as per project requirements)

# Verify we're in the right environment
which python
# Should show conda/venv python path, not system python
```

## 2. EMUSES Installation Check

### Test if emuses is installed
```bash
# Try to run emuses directly (this failed in initial testing)
emuses --help
```
**Expected Result**: ❌ This currently fails with "command not found"

### Install emuses in development mode
```bash
# Install in editable/development mode
pip install -e .

# Verify installation
pip list | grep emuses
```

### Alternative: Run via Python module
If direct `emuses` command doesn't work, use:
```bash
# This should work regardless
python -m emuses.cli --help
```

## 3. Dependencies Verification

### Check core dependencies
```bash
# Verify key packages are installed
python -c "import numpy, pandas, sklearn, typer; print('Core deps OK')"

# Check EMUSES-specific imports
python -c "import emuses; print(f'EMUSES version: {emuses.__version__ if hasattr(emuses, \"__version__\") else \"dev\"}')"
```

## 4. Test Data Access

### Verify access to battle-tested data paths
```bash
# Check if test data is accessible
ls -la "/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/"
```

If not accessible, we'll need to:
- Find alternative test data in the project
- Create minimal test datasets
- Document the limitation

## 5. Output Directory Setup

### Create test output directory (outside emuses/)
```bash
# Create temp directory for test outputs
mkdir -p /tmp/emuses_cli_test_outputs
chmod 755 /tmp/emuses_cli_test_outputs
```

## 6. Basic Functionality Smoke Test

### Test most basic command
```bash
# This should show help without errors
python -m emuses.cli --help
```

### Test models command (if it exists)
```bash
# Check if models subcommand exists
python -m emuses.cli models --help 2>&1 | head -10
```

## Testing Results Log

### Setup Test Results
| Test | Command | Status | Notes |
|------|---------|--------|-------|
| Direct CLI | `emuses --help` | ❌ | Command not found |
| Python module | `python -m emuses.cli --help` | ? | To test |
| Installation | `pip install -e .` | ? | To test |
| Dependencies | Core imports | ? | To test |
| Test data access | Path check | ? | May need alternatives |
| Output directory | `/tmp/` setup | ? | To test |

### Environment Details
- **OS**: WSL Ubuntu (Windows subsystem)  
- **Python**: 3.11.13 (miniforge environment)
- **Shell**: bash via wsl.exe
- **Working Directory**: `/mnt/c/Users/Tolhsadum/PycharmProjects/emuses`
- **Date**: 2025-08-31
- **EMUSES Install**: 0.9.0.dev0 (development mode)

### Next Steps
1. Complete setup verification
2. Resolve any installation issues  
3. Proceed to command discovery (01_command_discovery.md)
4. Run battle-tested command (02_basic_functionality_tests.md)

### Notes
- If direct `emuses` command fails, document and use `python -m emuses.cli` throughout
- If test data paths are inaccessible, identify alternatives in project test_data/
- Document any environment-specific workarounds needed
