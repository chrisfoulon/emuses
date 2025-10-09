# Error Handling and Edge Case Tests

## Overview
This document systematically tests error conditions, invalid inputs, and edge cases to evaluate the robustness and user-friendliness of EMUSES CLI error handling.

## Prerequisites
- Basic functionality testing completed
- At least one working command identified
- Understanding of expected input formats

## 1. Input Validation Tests

### 1.1 Missing Required Arguments
```bash
# Test commands without required arguments
python -m emuses.cli full 2>&1
# Expected: Clear error message about missing arguments

python -m emuses.cli full "/tmp/output" 2>&1  
# Expected: Error about missing input data file

# Test with only partial required args
python -m emuses.cli full "/tmp/output" "nonexistent.csv" 2>&1
# Expected: Error about missing data file
```

**Test Results:**
| Test Case | Error Message Quality | Exit Code | User Guidance |
|-----------|----------------------|-----------|---------------|
| No arguments | ⏳ | ⏳ | ⏳ |
| Missing data file | ⏳ | ⏳ | ⏳ |
| Partial arguments | ⏳ | ⏳ | ⏳ |

### 1.2 Invalid File Paths
```bash
# Non-existent input files
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/error_test" \
    "/nonexistent/path/data.csv" \
    2>&1

# Invalid output directory (no write permissions)
python -m emuses.cli full \
    "/root/no_permission" \
    "valid_data.csv" \
    2>&1

# Output directory that's a file
touch /tmp/emuses_cli_test_outputs/not_a_directory
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/not_a_directory" \
    "valid_data.csv" \
    2>&1
```

### 1.3 Invalid Data Formats
```bash
# Empty CSV file
touch /tmp/emuses_cli_test_outputs/empty.csv
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/empty_test" \
    "/tmp/emuses_cli_test_outputs/empty.csv" \
    2>&1

# Malformed CSV (different row lengths)
cat > /tmp/emuses_cli_test_outputs/malformed.csv << EOF
col1,col2,col3
1,2,3
4,5
6,7,8,9
EOF

python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/malformed_test" \
    "/tmp/emuses_cli_test_outputs/malformed.csv" \
    2>&1

# CSV with wrong headers  
cat > /tmp/emuses_cli_test_outputs/wrong_headers.csv << EOF
wrong,headers,here
1,2,3
4,5,6
EOF

python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/wrong_headers_test" \
    "/tmp/emuses_cli_test_outputs/wrong_headers.csv" \
    --columns_are_features \
    2>&1
```

## 2. Parameter Validation Tests

### 2.1 Invalid Parameter Values
```bash
# Invalid normalization method
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/invalid_norm" \
    "valid_data.csv" \
    --input_normalization "invalid_method" \
    2>&1

# Invalid header row number
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/invalid_header" \
    "valid_data.csv" \
    --input_header -1 \
    2>&1

# Invalid number of jobs (negative)
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/invalid_jobs" \
    "valid_data.csv" \
    --n_jobs -5 \
    2>&1

# Invalid number of jobs (too high)
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/too_many_jobs" \
    "valid_data.csv" \
    --n_jobs 10000 \
    2>&1
```

### 2.2 Conflicting Parameters
```bash
# Test parameter combinations that shouldn't work together
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/conflict_test" \
    "valid_data.csv" \
    --columns_are_features \
    --rows_are_features \
    2>&1

# Incompatible optimization settings
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/incompatible_optim" \
    "valid_data.csv" \
    --optim_dict nonexistent_dict \
    --optuna_trials 0 \
    2>&1
```

### 2.3 Resource Constraint Tests
```bash
# Unrealistic resource requests
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/high_memory" \
    "valid_data.csv" \
    --memory_limit 1TB \
    2>&1

# Zero trials (should be caught)
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/zero_trials" \
    "valid_data.csv" \
    --umap_trials 0 \
    --hdbscan_trials 0 \
    --optuna_trials 0 \
    2>&1
```

## 3. Runtime Error Tests

### 3.1 Insufficient Data Tests
```bash
# CSV with only one row
cat > /tmp/emuses_cli_test_outputs/one_row.csv << EOF
col1,col2,col3
1,2,3
EOF

python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/one_row_test" \
    "/tmp/emuses_cli_test_outputs/one_row.csv" \
    --columns_are_features \
    2>&1

# CSV with only one column
cat > /tmp/emuses_cli_test_outputs/one_col.csv << EOF
col1
1
2
3
EOF

python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/one_col_test" \
    "/tmp/emuses_cli_test_outputs/one_col.csv" \
    --columns_are_features \
    2>&1
```

### 3.2 Numerical Issues
```bash
# CSV with all zeros
cat > /tmp/emuses_cli_test_outputs/all_zeros.csv << EOF
col1,col2,col3
0,0,0
0,0,0
0,0,0
EOF

python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/all_zeros_test" \
    "/tmp/emuses_cli_test_outputs/all_zeros.csv" \
    --columns_are_features \
    2>&1

# CSV with NaN values
cat > /tmp/emuses_cli_test_outputs/with_nan.csv << EOF
col1,col2,col3
1,2,3
4,NaN,6
7,8,9
EOF

python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/with_nan_test" \
    "/tmp/emuses_cli_test_outputs/with_nan.csv" \
    --columns_are_features \
    2>&1

# CSV with infinite values
cat > /tmp/emuses_cli_test_outputs/with_inf.csv << EOF
col1,col2,col3
1,2,3
4,inf,6  
7,8,9
EOF

python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/with_inf_test" \
    "/tmp/emuses_cli_test_outputs/with_inf.csv" \
    --columns_are_features \
    2>&1
```

## 4. Model-Specific Error Tests

### 4.1 Invalid Model Registry Operations
```bash
# Try to list models from non-existent registry
python -m emuses.cli models list --registry "/nonexistent/path" 2>&1

# Try to use corrupted model registry  
mkdir -p /tmp/emuses_cli_test_outputs/corrupted_registry
echo "invalid content" > /tmp/emuses_cli_test_outputs/corrupted_registry/model.pkl

python -m emuses.cli models list --registry "/tmp/emuses_cli_test_outputs/corrupted_registry" 2>&1
```

### 4.2 Mismatched Data for Trained Models
```bash
# If we have a trained model, test with incompatible data
# (Requires successful model from basic testing)

# Different number of features
cat > /tmp/emuses_cli_test_outputs/wrong_features.csv << EOF
col1,col2
1,2
3,4
EOF

# Try to use trained model with wrong feature count
python -m emuses.cli predict \
    --model "/tmp/emuses_cli_test_outputs/model_registry_test/best_model" \
    --data "/tmp/emuses_cli_test_outputs/wrong_features.csv" \
    2>&1
```

## 5. System Resource Error Tests

### 5.1 Disk Space Tests
```bash
# Fill up available space in test directory (carefully!)
# Note: Only do this in isolated test environment

# Create large file to consume space
# dd if=/dev/zero of=/tmp/emuses_cli_test_outputs/large_file bs=1M count=100 2>/dev/null

# Try to run analysis with limited disk space
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/disk_full_test" \
    "valid_data.csv" \
    2>&1

# Clean up
# rm -f /tmp/emuses_cli_test_outputs/large_file
```

### 5.2 Memory Constraint Tests
```bash
# Try to run with artificially limited memory
# (This might require ulimit or systemd-run depending on system)

# Run with single job to test memory handling
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/memory_test" \
    "large_data.csv" \
    --n_jobs 1 \
    --hdbscan_jobs 1 \
    2>&1
```

## 6. Interactive Mode Error Tests

### 6.1 Non-Interactive Environment
```bash
# Test interactive commands in non-interactive environment
echo "n" | python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/non_interactive" \
    "valid_data.csv" \
    --interactive_plot \
    2>&1

# Test with stdin closed
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/no_stdin" \
    "valid_data.csv" \
    --interactive_plot \
    </dev/null 2>&1
```

## 7. Signal Handling Tests

### 7.1 Graceful Interruption
```bash
# Test SIGINT handling (Ctrl+C)
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/interrupt_test" \
    "valid_data.csv" \
    2>&1 &

PID=$!
sleep 5
kill -INT $PID
wait $PID
echo "Exit code: $?"

# Check if cleanup occurred
ls -la "/tmp/emuses_cli_test_outputs/interrupt_test"
```

### 7.2 Forced Termination
```bash
# Test SIGTERM handling  
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/terminate_test" \
    "valid_data.csv" \
    2>&1 &

PID=$!
sleep 5
kill -TERM $PID
wait $PID
echo "Exit code: $?"
```

## 8. Error Message Quality Assessment

### 8.1 Error Message Criteria
For each error test, evaluate:
- **Clarity**: Is the error message understandable?
- **Actionability**: Does it tell the user what to do?  
- **Context**: Does it explain what went wrong?
- **Exit Codes**: Are they meaningful and consistent?

### 8.2 Error Message Examples
```bash
# Document actual error messages for analysis
# Good example: "Error: Input file 'data.csv' not found. Please check the file path."
# Bad example: "IndexError: list index out of range"
```

## 9. Error Test Results Summary

### ✅ Well-Handled Errors
| Error Type | Message Quality | Exit Code | Recovery Guidance |
|------------|-----------------|-----------|-------------------|
| | | | |

### ⚠️ Poor Error Messages  
| Error Type | Current Message | Suggested Improvement |
|------------|-----------------|----------------------|
| | | |

### ❌ Unhandled Exceptions
| Error Type | Exception | Impact | Priority |
|------------|-----------|--------|----------|
| | | | |

### 🔧 Error Recovery Issues
| Scenario | Problem | Suggested Fix |
|----------|---------|---------------|
| | | |

## 10. Edge Case Discovery

### 10.1 Boundary Conditions
- Minimum/maximum parameter values
- Empty or single-element datasets
- Very large datasets (within reason for testing)
- Unicode/special characters in file paths

### 10.2 Platform-Specific Issues
- Windows vs Linux path handling
- Case sensitivity issues  
- File permission differences
- Character encoding problems

## 11. Next Steps

Based on error testing results:
1. **High-priority fixes**: Unhandled exceptions, poor error messages
2. **User experience improvements**: Better guidance, clearer messages
3. **Robustness enhancements**: Better input validation, graceful degradation  
4. **Documentation updates**: Known limitations, troubleshooting guide

## Files Generated
- Error test logs for each scenario
- Error message quality assessment
- Recommended improvements document
- Edge case catalog

## Notes
- Be careful with system resource tests - don't damage the test environment
- Save all error outputs for analysis
- Document the exact command and environment for reproducible error cases
- Consider automating the good error tests for regression testing
