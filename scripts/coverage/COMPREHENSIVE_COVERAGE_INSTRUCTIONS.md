# EMUSES Comprehensive Coverage Analysis Instructions

## Quick Start

```bash
# Default: 4 workers, 3 files per chunk
python comprehensive_coverage_analysis.py

# For your beast machine (72 cores, 128GB RAM):
python comprehensive_coverage_analysis.py --workers 72

# Aggressive mode: Use ALL cores with maximum parallelism
python comprehensive_coverage_analysis.py --aggressive

# Custom configuration
python comprehensive_coverage_analysis.py --workers 24 --chunk-size 2
```

## Performance Options

### **Standard Machine** (4-8 cores, 8-16GB RAM)
```bash
python comprehensive_coverage_analysis.py --workers 4    # Default
python comprehensive_coverage_analysis.py --workers 8    # Max recommended
```
**Expected Duration**: 15-30 minutes

### **High-End Workstation** (16-32 cores, 32-64GB RAM)  
```bash
python comprehensive_coverage_analysis.py --workers 16   # Conservative
python comprehensive_coverage_analysis.py --workers 24   # Aggressive
```
**Expected Duration**: 5-10 minutes

### **Beast Machine** (72 cores, 128GB RAM) 🏆
```bash
python comprehensive_coverage_analysis.py --workers 72           # Maximum workers
python comprehensive_coverage_analysis.py --workers 48 --chunk-size 1  # Max parallelism  
python comprehensive_coverage_analysis.py --aggressive          # Use ALL cores
```
**Expected Duration**: 2-5 minutes (!)

## What This Script Does

1. **Finds All Test Files**: Discovers all 155 test files in the project
2. **Cleans Artifacts**: Removes test artifacts (attack simulations, temp files) before and after
3. **Chunks Tests**: Breaks tests into small chunks (3 files each) to prevent resource exhaustion
4. **Runs Coverage**: Uses `coverage run` with parallel processing (4 workers max)
5. **No Timeouts**: Lets each chunk run as long as needed
6. **Combines Results**: Merges all coverage data into comprehensive report
7. **Generates Reports**: Creates both text and JSON coverage reports

## Script Features

### ✅ Comprehensive Coverage
- Processes ALL 155 test files (not just a sample)
- Measures coverage of ALL 21,464 lines of source code
- No timeouts - runs until complete

### ✅ Automatic Cleanup
- Removes test artifacts before analysis:
  - `attacks/` folders from security tests
  - `temp_*` files
  - Simulation and benchmark artifacts
  - Cache directories
- Cleans up after analysis completes

### ✅ Progress Tracking
- Real-time progress updates
- Shows successful/failed chunks
- Estimated completion time
- Detailed error reporting for failed chunks

### ✅ Resource Management
- Limited to 4 parallel workers to prevent system overload
- Small chunk size (3 files) to minimize memory usage
- Automatic cleanup of temporary coverage files

## Expected Output

### **Standard Run** (4 workers)
```
🧪 EMUSES Comprehensive Coverage Analysis
============================================================
⚠️  NO TIMEOUTS - This will run until completion
🔧 Configuration:
   Workers: 4 (detected 8 CPU cores)
   Chunk size: 3 test files per chunk
============================================================
```

### **Beast Mode** (72 workers) 🏆
```
🧪 EMUSES Comprehensive Coverage Analysis
============================================================
⚠️  NO TIMEOUTS - This will run until completion
🔧 Configuration:
   Workers: 72 (detected 72 CPU cores)
   Chunk size: 3 test files per chunk
🏆 BEAST MODE: High-performance parallel processing!
============================================================

📂 Discovering test files...
Found 155 test files
Created 52 chunks of 3 test files each
📈 Expected speedup: 18.0x faster than baseline

🚀 Running coverage analysis with 52 workers...
📊 Progress will be shown in real-time...
✅ Chunk  1: Completed successfully
✅ Chunk  2: Completed successfully
[... 50 more chunks completing rapidly ...]

📊 Chunk Processing Results (2.1 minutes)
✅ Successful: 52/52
❌ Failed: 0/52
```

### **Aggressive Mode** (ALL cores, 1 file per chunk)
```
🚀 AGGRESSIVE MODE ACTIVATED!
   Using ALL 72 CPU cores with 1 file per chunk
🏆 BEAST MODE: High-performance parallel processing!

Created 155 chunks of 1 test files each
📈 Expected speedup: 38.8x faster than baseline
🚀 Running coverage analysis with 72 workers...
```

## What to Do if Chunks Fail

Some chunks may fail due to:
- **Complex integration tests** that require specific setup
- **External dependencies** not available
- **Resource-intensive tests** that need more memory

**This is normal and expected.** The script will:
1. Continue processing other chunks
2. Report which chunks failed
3. Still generate coverage report from successful chunks
4. Show warnings about incomplete coverage

## File Cleanup Details

The script automatically removes these test artifacts:

### Security Test Artifacts
- Folders with names containing: `attacker`, `malicious`, command injection patterns
- Files/folders created by security vulnerability tests

### General Test Artifacts  
- `attacks/` and `test_attacks/` directories
- `temp_*` files and `*.tmp` files
- `.coverage*` files (temporary coverage data)
- `htmlcov/` directories
- `.pytest_cache/` and `__pycache__/` directories
- `simulation_*` and `benchmark_*` artifacts

### Git Integration
- Uses `git status --porcelain` to identify untracked files
- Only removes files matching cleanup patterns
- Preserves legitimate project files

## For Future Claude Sessions

1. **Run Analysis**: `python comprehensive_coverage_analysis.py`
2. **Check Results**: Look for final coverage percentages and any failed chunks
3. **Investigate Failures**: If many chunks fail, check system resources and dependencies
4. **Update Documentation**: Record actual coverage results in project documentation

## Troubleshooting

### Script Hangs on a Chunk
- **Normal**: Some test chunks take 5-10 minutes (complex integration tests)
- **Action**: Wait patiently, no timeout is set intentionally

### Many Chunks Fail
- **Check**: System resources (memory, disk space)
- **Check**: Required dependencies installed
- **Action**: Re-run script, often temporary issues resolve

### Low Coverage Results
- **Normal**: Some specialized modules have low coverage
- **Focus**: Check that core components (models, auth, registry) have good coverage
- **Target**: 40-60% overall is excellent for research software

### Coverage Files Not Found
- **Cause**: All chunks failed due to environment issues
- **Action**: Check pytest works manually: `pytest tests/security/test_auth.py -v`
- **Fix**: Resolve dependency or environment issues first

## Integration with Development Workflow

### Before Major Releases
1. Run comprehensive coverage analysis
2. Document coverage results
3. Identify any critical components with low coverage
4. Add targeted tests if needed

### After Test Suite Changes
1. Run analysis to verify coverage maintained
2. Check for new test artifacts to clean
3. Update coverage documentation

### CI/CD Integration
- **Local Testing**: Use this script for complete analysis
- **CI Pipeline**: Use faster subset testing to save resources
- **Release Pipeline**: Include comprehensive coverage in release validation

---
*Instructions for EMUSES Comprehensive Coverage Analysis*  
*No timeouts, complete analysis, automatic cleanup*  
*Expected runtime: 15-30 minutes for full 155 test files*