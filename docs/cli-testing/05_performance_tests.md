# Performance Testing and Resource Analysis

## Overview
This document tests the performance characteristics of EMUSES CLI commands, identifies bottlenecks, and evaluates resource usage patterns.

## Prerequisites
- Basic functionality testing completed
- At least one working command with known runtime
- System monitoring tools available (htop, iostat, etc.)

## 1. Baseline Performance Measurements

### 1.1 Battle-Tested Command Baseline
```bash
# Baseline timing of the known working command
time python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/performance_baseline" \
    "/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv" \
    --columns_are_features \
    --input_header 0 \
    --input_index_column 0 \
    --input_normalization robust \
    --scores "/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv" \
    --scores_header 0 \
    --umap_trials 1 \
    --hdbscan_trials 1 \
    --optim_dict optim_dict_hcp \
    --hdbscan_jobs 16 \
    --prediction_optim_dict quick_train_dict \
    --optuna_trials 10 \
    --n_jobs 16 \
    2>&1 | tee "/tmp/emuses_cli_test_outputs/performance_baseline.log"
```

**Baseline Metrics:**
| Metric | Value | Notes |
|--------|-------|-------|
| Real time | ~2 minutes (expected) | Wall clock time |
| User time | ⏳ | CPU time in user mode |
| System time | ⏳ | CPU time in kernel mode |
| Max memory | ⏳ | Peak memory usage |
| CPU utilization | ⏳ | Average CPU usage |

### 1.2 System Resource Monitoring
```bash
# Monitor system resources during baseline run
# Run this in separate terminal while command executes:

# Memory usage over time
while true; do
    ps aux | grep "emuses" | grep -v grep >> /tmp/emuses_cli_test_outputs/memory_usage.log
    sleep 5
done &
MONITOR_PID=$!

# Run the command
# ... (baseline command) ...

# Stop monitoring  
kill $MONITOR_PID
```

## 2. Parameter Impact Analysis

### 2.1 Threading and Parallelization
```bash
# Test different job counts
for JOBS in 1 4 8 16 32; do
    echo "Testing with $JOBS jobs"
    time python -m emuses.cli full \
        "/tmp/emuses_cli_test_outputs/jobs_test_$JOBS" \
        "test_data.csv" \
        --n_jobs $JOBS \
        --hdbscan_jobs $JOBS \
        --optuna_trials 5 \
        2>&1 | tee "/tmp/emuses_cli_test_outputs/jobs_${JOBS}_performance.log"
done
```

**Threading Performance:**
| Job Count | Real Time | User Time | CPU Util | Memory Peak |
|-----------|-----------|-----------|----------|-------------|
| 1 | ⏳ | ⏳ | ⏳ | ⏳ |
| 4 | ⏳ | ⏳ | ⏳ | ⏳ |
| 8 | ⏳ | ⏳ | ⏳ | ⏳ |
| 16 | ⏳ | ⏳ | ⏳ | ⏳ |
| 32 | ⏳ | ⏳ | ⏳ | ⏳ |

### 2.2 Optimization Trial Impact
```bash
# Test different trial counts  
for TRIALS in 1 5 10 25 50; do
    echo "Testing with $TRIALS Optuna trials"
    time python -m emuses.cli full \
        "/tmp/emuses_cli_test_outputs/trials_test_$TRIALS" \
        "test_data.csv" \
        --optuna_trials $TRIALS \
        --umap_trials 1 \
        --hdbscan_trials 1 \
        2>&1 | tee "/tmp/emuses_cli_test_outputs/trials_${TRIALS}_performance.log"
done
```

**Optimization Trial Performance:**
| Trial Count | Real Time | Quality Score | Time/Trial | Diminishing Returns |
|-------------|-----------|---------------|------------|---------------------|
| 1 | ⏳ | ⏳ | ⏳ | N/A |
| 5 | ⏳ | ⏳ | ⏳ | ⏳ |
| 10 | ⏳ | ⏳ | ⏳ | ⏳ |
| 25 | ⏳ | ⏳ | ⏳ | ⏳ |
| 50 | ⏳ | ⏳ | ⏳ | ⏳ |

### 2.3 Data Size Scaling
```bash
# Create datasets of different sizes for testing
# Small dataset (100 samples)
head -101 "original_data.csv" > /tmp/emuses_cli_test_outputs/small_data.csv

# Medium dataset (1000 samples) 
head -1001 "original_data.csv" > /tmp/emuses_cli_test_outputs/medium_data.csv

# Large dataset (if available - use full dataset)
cp "original_data.csv" /tmp/emuses_cli_test_outputs/large_data.csv

# Test each size
for SIZE in small medium large; do
    echo "Testing $SIZE dataset"
    time python -m emuses.cli full \
        "/tmp/emuses_cli_test_outputs/size_test_$SIZE" \
        "/tmp/emuses_cli_test_outputs/${SIZE}_data.csv" \
        --columns_are_features \
        --optuna_trials 5 \
        2>&1 | tee "/tmp/emuses_cli_test_outputs/size_${SIZE}_performance.log"
done
```

**Data Scaling Performance:**
| Dataset Size | Samples | Features | Real Time | Memory Peak | Scaling Factor |
|--------------|---------|----------|-----------|-------------|----------------|
| Small | ~100 | ⏳ | ⏳ | ⏳ | 1.0x |
| Medium | ~1000 | ⏳ | ⏳ | ⏳ | ⏳ |
| Large | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |

## 3. Individual Command Performance

### 3.1 Command Timing Breakdown
```bash
# Time individual commands if they exist separately
time python -m emuses.cli umap "input_data.csv" "/tmp/emuses_cli_test_outputs/umap_only" 2>&1

time python -m emuses.cli cluster "umap_results" "/tmp/emuses_cli_test_outputs/cluster_only" 2>&1

time python -m emuses.cli predict "model_data" "/tmp/emuses_cli_test_outputs/predict_only" 2>&1

time python -m emuses.cli models list --registry "/tmp/emuses_cli_test_outputs/model_registry_test" 2>&1
```

**Individual Command Performance:**
| Command | Real Time | Memory | CPU | Notes |
|---------|-----------|--------|-----|-------|
| umap | ⏳ | ⏳ | ⏳ | ⏳ |
| cluster | ⏳ | ⏳ | ⏳ | ⏳ |
| predict | ⏳ | ⏳ | ⏳ | ⏳ |
| models list | ⏳ | ⏳ | ⏳ | ⏳ |

### 3.2 Startup Time Analysis
```bash
# Measure CLI startup overhead
time python -m emuses.cli --help >/dev/null 2>&1

time python -m emuses.cli models --help >/dev/null 2>&1

# Compare with no-op Python script
time python -c "import sys; sys.exit(0)" 2>&1
```

**Startup Performance:**
| Command | Real Time | Notes |
|---------|-----------|-------|
| --help | ⏳ | Base CLI overhead |
| models --help | ⏳ | Subcommand overhead |
| python no-op | ⏳ | Python baseline |

## 4. Memory Usage Analysis

### 4.1 Memory Profiling
```bash
# Install memory profiler if available
# pip install memory-profiler

# Profile memory usage of main command
python -m memory_profiler -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/memory_profile" \
    "test_data.csv" \
    --optuna_trials 2 \
    2>&1 | tee "/tmp/emuses_cli_test_outputs/memory_profile.log"
```

### 4.2 Memory Leak Detection
```bash
# Run multiple iterations to detect memory leaks
for i in {1..5}; do
    echo "Iteration $i"
    python -m emuses.cli full \
        "/tmp/emuses_cli_test_outputs/leak_test_$i" \
        "small_data.csv" \
        --optuna_trials 2 \
        2>&1
    
    # Check memory usage
    ps aux | grep python | grep -v grep >> /tmp/emuses_cli_test_outputs/memory_iterations.log
    
    # Clean up outputs to avoid disk space issues
    rm -rf "/tmp/emuses_cli_test_outputs/leak_test_$i"
done
```

## 5. I/O Performance Analysis

### 5.1 File I/O Patterns
```bash
# Monitor I/O during execution using iostat (if available)
iostat -x 1 > /tmp/emuses_cli_test_outputs/iostat.log &
IOSTAT_PID=$!

python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/io_test" \
    "test_data.csv" \
    --optuna_trials 5 \
    2>&1 | tee "/tmp/emuses_cli_test_outputs/io_test.log"

kill $IOSTAT_PID
```

### 5.2 Output File Analysis
```bash
# Analyze output file sizes and creation patterns
find "/tmp/emuses_cli_test_outputs/performance_baseline" -type f -exec ls -lh {} \; | sort -k5 -hr > /tmp/emuses_cli_test_outputs/output_files.log

# Check if outputs are compressed/optimized
file /tmp/emuses_cli_test_outputs/performance_baseline/* >> /tmp/emuses_cli_test_outputs/file_types.log
```

## 6. Resource Constraint Testing

### 6.1 Limited Memory Environment
```bash
# Test with memory limits (using ulimit if supported)
ulimit -v 2000000  # ~2GB virtual memory limit
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/limited_memory" \
    "medium_data.csv" \
    --n_jobs 1 \
    --optuna_trials 3 \
    2>&1 | tee "/tmp/emuses_cli_test_outputs/limited_memory.log"
```

### 6.2 CPU Constraint Testing  
```bash
# Test with CPU limits (using cpulimit if available)
# cpulimit -l 50 python -m emuses.cli full ...

# Or test single-threaded performance
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/single_thread" \
    "test_data.csv" \
    --n_jobs 1 \
    --hdbscan_jobs 1 \
    --optuna_trials 5 \
    2>&1 | tee "/tmp/emuses_cli_test_outputs/single_thread.log"
```

## 7. Performance Regression Testing

### 7.1 Reproducible Benchmarks
```bash
# Create standardized benchmark that can be run regularly
cat > /tmp/emuses_cli_test_outputs/benchmark.sh << 'EOF'
#!/bin/bash
echo "EMUSES Performance Benchmark - $(date)"
echo "System: $(uname -a)"
echo "Python: $(python --version)"

time python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/benchmark_result" \
    "benchmark_data.csv" \
    --columns_are_features \
    --optuna_trials 5 \
    --n_jobs 4 \
    2>&1
EOF

chmod +x /tmp/emuses_cli_test_outputs/benchmark.sh
```

### 7.2 Performance Comparison
```bash
# Run benchmark multiple times for consistency
for run in {1..3}; do
    echo "Benchmark run $run"
    ./benchmark.sh > "/tmp/emuses_cli_test_outputs/benchmark_run_$run.log"
done

# Calculate average, min, max times
```

## 8. Performance Optimization Recommendations

### 8.1 Bottleneck Analysis
Based on testing, identify:
- **CPU-bound operations**: High CPU usage, little I/O wait
- **I/O-bound operations**: High I/O wait, low CPU usage  
- **Memory-bound operations**: High memory usage, potential swapping
- **Network-bound operations**: If any network calls are made

### 8.2 Optimization Opportunities
| Area | Current Performance | Potential Improvement | Implementation Complexity |
|------|--------------------|-----------------------|--------------------------|
| Parallelization | ⏳ | ⏳ | ⏳ |
| Memory usage | ⏳ | ⏳ | ⏳ |
| I/O efficiency | ⏳ | ⏳ | ⏳ |
| Algorithm efficiency | ⏳ | ⏳ | ⏳ |

## 9. Performance Test Results Summary

### ✅ Good Performance Areas
```
# Areas where performance meets expectations
```

### ⚠️ Performance Concerns
```
# Areas with suboptimal performance
```

### 🐌 Performance Bottlenecks  
```
# Critical performance issues
```

### 📈 Scaling Characteristics
```
# How performance scales with data size, parameters, resources
```

## 10. Hardware and Environment Impact

### 10.1 System Specifications
```bash
# Document test system specs
echo "CPU Info:" > /tmp/emuses_cli_test_outputs/system_specs.txt
lscpu >> /tmp/emuses_cli_test_outputs/system_specs.txt
echo -e "\nMemory Info:" >> /tmp/emuses_cli_test_outputs/system_specs.txt
free -h >> /tmp/emuses_cli_test_outputs/system_specs.txt
echo -e "\nDisk Info:" >> /tmp/emuses_cli_test_outputs/system_specs.txt  
df -h /tmp >> /tmp/emuses_cli_test_outputs/system_specs.txt
```

### 10.2 Environment Variables Impact
```bash
# Test with different environment configurations
export OMP_NUM_THREADS=1
time python -m emuses.cli full "/tmp/emuses_cli_test_outputs/omp_1" "test_data.csv" --optuna_trials 3 2>&1

export OMP_NUM_THREADS=4  
time python -m emuses.cli full "/tmp/emuses_cli_test_outputs/omp_4" "test_data.csv" --optuna_trials 3 2>&1
```

## 11. Next Steps

Based on performance testing results:
1. **Optimization priorities**: Focus on the biggest bottlenecks
2. **Resource recommendations**: Optimal hardware/configuration guidance  
3. **Parameter tuning**: Recommended settings for different use cases
4. **Scaling limits**: Maximum practical data sizes and complexity

## Files Generated
- Performance logs for all tests
- System resource usage data  
- Benchmark scripts for regression testing
- Performance analysis report
- Optimization recommendations

## Notes
- Performance testing can be time-consuming - prioritize based on basic functionality results
- System load during testing can affect results - note other processes running
- Multiple runs may be needed for statistical significance
- Document all system specifications and conditions for reproducibility
