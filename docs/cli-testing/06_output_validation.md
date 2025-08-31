# Output Validation and Data Integrity Tests

## Overview
This document validates that EMUSES CLI commands produce correct, consistent, and scientifically valid outputs. It focuses on data integrity, file format correctness, and result reproducibility.

## Prerequisites
- Basic functionality testing completed with successful outputs
- At least one trained model available for validation
- Understanding of expected output formats and structures

## 1. Output File Structure Validation

### 1.1 Required Output Files Check
```bash
# After running the battle-tested full pipeline, verify all expected outputs exist
BASE_DIR="/tmp/emuses_cli_test_outputs/model_registry_test"

echo "Checking output file structure..."
find "$BASE_DIR" -type f | sort > /tmp/emuses_cli_test_outputs/output_files_list.txt

# Check for expected file types
echo "Model files (.pkl, .joblib, .h5):"
find "$BASE_DIR" -name "*.pkl" -o -name "*.joblib" -o -name "*.h5" | head -10

echo "Data files (.csv, .npy, .npz):"  
find "$BASE_DIR" -name "*.csv" -o -name "*.npy" -o -name "*.npz" | head -10

echo "Plot files (.png, .svg, .html):"
find "$BASE_DIR" -name "*.png" -o -name "*.svg" -o -name "*.html" | head -10

echo "Configuration files (.json, .yaml):"
find "$BASE_DIR" -name "*.json" -o -name "*.yaml" -o -name "*.yml" | head -10
```

**File Structure Validation:**
| File Type | Expected Count | Actual Count | Missing Files | Extra Files |
|-----------|----------------|--------------|---------------|-------------|
| Model files | ⏳ | ⏳ | ⏳ | ⏳ |
| Data files | ⏳ | ⏳ | ⏳ | ⏳ |
| Plots | ⏳ | ⏳ | ⏳ | ⏳ |
| Configs | ⏳ | ⏳ | ⏳ | ⏳ |

### 1.2 File Size and Integrity Check
```bash
# Check file sizes are reasonable (not empty, not suspiciously large)
echo "File sizes analysis:"
find "$BASE_DIR" -type f -exec ls -lh {} \; | sort -k5 -hr | head -20 > /tmp/emuses_cli_test_outputs/file_sizes.txt

# Check for empty files (potential errors)
echo "Empty files (potential errors):"
find "$BASE_DIR" -type f -empty

# Check file integrity for common formats
echo "Checking CSV files integrity:"
for csv in $(find "$BASE_DIR" -name "*.csv" | head -5); do
    echo "File: $csv"
    head -3 "$csv" 2>&1 | head -1
    wc -l "$csv" 2>&1
    echo "---"
done
```

## 2. Data Format Validation

### 2.1 CSV Output Validation
```bash
# Validate CSV files have consistent format
for csv in $(find "$BASE_DIR" -name "*.csv" | head -10); do
    echo "Validating $csv..."
    
    # Check for consistent number of columns
    awk -F',' 'NR==1{cols=NF} NR>1&&NF!=cols{print "Line " NR ": " NF " columns, expected " cols; exit 1}' "$csv"
    if [ $? -eq 0 ]; then
        echo "  ✅ Column consistency: OK"
    else
        echo "  ❌ Column consistency: FAILED"
    fi
    
    # Check for header presence
    head -1 "$csv" | grep -q '[a-zA-Z]'
    if [ $? -eq 0 ]; then
        echo "  ✅ Header present: OK" 
    else
        echo "  ⚠️  Header present: No text in first row"
    fi
    
    # Check for numeric data (excluding header)
    tail -n +2 "$csv" | head -5 | awk -F',' '{for(i=1;i<=NF;i++) if($i!="" && $i!~/^-?[0-9]*\.?[0-9]+([eE][+-]?[0-9]+)?$/) print "Non-numeric: " $i}'
    
    echo "---"
done
```

### 2.2 Model File Validation
```bash
# Test that model files can be loaded
python3 << 'EOF'
import pickle
import joblib
import glob
import os

base_dir = "/tmp/emuses_cli_test_outputs/model_registry_test"

print("Testing model file loading...")

# Test pickle files
for pkl_file in glob.glob(os.path.join(base_dir, "**/*.pkl"), recursive=True):
    try:
        with open(pkl_file, 'rb') as f:
            obj = pickle.load(f)
        print(f"✅ {pkl_file}: Pickle loads OK, type: {type(obj).__name__}")
    except Exception as e:
        print(f"❌ {pkl_file}: Pickle load failed: {e}")

# Test joblib files  
for joblib_file in glob.glob(os.path.join(base_dir, "**/*.joblib"), recursive=True):
    try:
        obj = joblib.load(joblib_file)
        print(f"✅ {joblib_file}: Joblib loads OK, type: {type(obj).__name__}")
    except Exception as e:
        print(f"❌ {joblib_file}: Joblib load failed: {e}")
EOF
```

### 2.3 Plot File Validation  
```bash
# Check plot files are valid
echo "Validating plot files..."

# Check PNG files
for png in $(find "$BASE_DIR" -name "*.png" | head -5); do
    file "$png" | grep -q "PNG image"
    if [ $? -eq 0 ]; then
        echo "✅ $png: Valid PNG"
    else
        echo "❌ $png: Invalid PNG format"
    fi
done

# Check SVG files
for svg in $(find "$BASE_DIR" -name "*.svg" | head -5); do
    head -1 "$svg" | grep -q "<?xml\|<svg"
    if [ $? -eq 0 ]; then
        echo "✅ $svg: Valid SVG"
    else
        echo "❌ $svg: Invalid SVG format"  
    fi
done

# Check HTML files
for html in $(find "$BASE_DIR" -name "*.html" | head -5); do
    head -3 "$html" | grep -qi "<html\|<!DOCTYPE"
    if [ $? -eq 0 ]; then
        echo "✅ $html: Valid HTML"
    else
        echo "⚠️ $html: May not be valid HTML"
    fi
done
```

## 3. Scientific Result Validation

### 3.1 Data Range and Distribution Checks
```bash
# Check that results are in reasonable ranges
python3 << 'EOF'
import pandas as pd
import numpy as np
import glob
import os

base_dir = "/tmp/emuses_cli_test_outputs/model_registry_test"

print("Analyzing output data ranges and distributions...")

# Find CSV files with numeric results
csv_files = glob.glob(os.path.join(base_dir, "**/*.csv"), recursive=True)

for csv_file in csv_files[:5]:  # Limit to first 5 files
    try:
        df = pd.read_csv(csv_file, nrows=1000)  # Sample first 1000 rows
        print(f"\n📊 Analysis for {os.path.basename(csv_file)}:")
        print(f"   Shape: {df.shape}")
        
        # Check numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            print(f"   Numeric columns: {len(numeric_cols)}")
            
            # Check for extreme values  
            for col in numeric_cols[:3]:  # First 3 numeric columns
                col_data = df[col].dropna()
                if len(col_data) > 0:
                    print(f"   {col}: min={col_data.min():.4f}, max={col_data.max():.4f}, mean={col_data.mean():.4f}")
                    
                    # Check for suspicious values
                    if np.any(np.isinf(col_data)):
                        print(f"   ⚠️ {col}: Contains infinite values")
                    if np.any(np.isnan(col_data)):
                        print(f"   ⚠️ {col}: Contains NaN values")
                    if col_data.min() == col_data.max():
                        print(f"   ⚠️ {col}: All values are identical")
        else:
            print("   ⚠️ No numeric columns found")
            
    except Exception as e:
        print(f"❌ Error reading {csv_file}: {e}")
EOF
```

### 3.2 UMAP Results Validation
```bash
# Validate UMAP results if they exist
python3 << 'EOF'
import pandas as pd
import numpy as np
import glob
import os

base_dir = "/tmp/emuses_cli_test_outputs/model_registry_test"

# Look for UMAP coordinate files
umap_files = glob.glob(os.path.join(base_dir, "**/*umap*.csv"), recursive=True)
umap_files.extend(glob.glob(os.path.join(base_dir, "**/coordinates*.csv"), recursive=True))

print("Validating UMAP results...")

for umap_file in umap_files:
    try:
        df = pd.read_csv(umap_file)
        print(f"\n🗺️ UMAP file: {os.path.basename(umap_file)}")
        print(f"   Shape: {df.shape}")
        
        # Check for 2D coordinates (most common UMAP output)
        coord_cols = [col for col in df.columns if 'umap' in col.lower() or 'coord' in col.lower()]
        if len(coord_cols) >= 2:
            print(f"   Coordinate columns: {coord_cols[:2]}")
            
            # Check coordinate ranges (UMAP typically produces values roughly in [-15, 15])
            x_col, y_col = coord_cols[0], coord_cols[1]
            x_range = (df[x_col].min(), df[x_col].max())  
            y_range = (df[y_col].min(), df[y_col].max())
            
            print(f"   X range: {x_range[0]:.2f} to {x_range[1]:.2f}")
            print(f"   Y range: {y_range[0]:.2f} to {y_range[1]:.2f}")
            
            # Validate ranges are reasonable for UMAP
            if abs(x_range[0]) > 50 or abs(x_range[1]) > 50:
                print("   ⚠️ X coordinates seem unusually large for UMAP")
            if abs(y_range[0]) > 50 or abs(y_range[1]) > 50:
                print("   ⚠️ Y coordinates seem unusually large for UMAP")
                
            # Check for clustering (points shouldn't all be identical)
            if x_range[0] == x_range[1] or y_range[0] == y_range[1]:
                print("   ❌ All coordinates are identical - UMAP may have failed")
            else:
                print("   ✅ Coordinate variation looks reasonable")
        else:
            print("   ❌ No coordinate columns found")
            
    except Exception as e:
        print(f"❌ Error validating {umap_file}: {e}")
EOF
```

### 3.3 Clustering Results Validation
```bash
# Validate clustering results
python3 << 'EOF'
import pandas as pd
import numpy as np
import glob
import os

base_dir = "/tmp/emuses_cli_test_outputs/model_registry_test"

# Look for clustering results
cluster_files = glob.glob(os.path.join(base_dir, "**/*cluster*.csv"), recursive=True)
cluster_files.extend(glob.glob(os.path.join(base_dir, "**/*hdbscan*.csv"), recursive=True))

print("Validating clustering results...")

for cluster_file in cluster_files:
    try:
        df = pd.read_csv(cluster_file)
        print(f"\n🔍 Cluster file: {os.path.basename(cluster_file)}")
        print(f"   Shape: {df.shape}")
        
        # Look for cluster label columns
        cluster_cols = [col for col in df.columns if 'cluster' in col.lower() or 'label' in col.lower()]
        
        for cluster_col in cluster_cols[:2]:  # Check first 2 cluster columns
            labels = df[cluster_col].dropna()
            unique_labels = sorted(labels.unique())
            
            print(f"   Column '{cluster_col}':")
            print(f"     Unique labels: {unique_labels}")
            print(f"     Number of clusters: {len([l for l in unique_labels if l >= 0])}")  # Exclude noise (-1)
            
            # Check for reasonable clustering
            if len(unique_labels) == 1:
                print("     ⚠️ Only one cluster found - clustering may have failed")
            elif len(unique_labels) > len(labels) * 0.8:  
                print("     ⚠️ Too many clusters - may be over-clustering")
            else:
                print("     ✅ Cluster count seems reasonable")
                
            # Check cluster size distribution
            cluster_sizes = labels.value_counts()
            print(f"     Largest cluster: {cluster_sizes.max()} samples")
            print(f"     Smallest cluster: {cluster_sizes.min()} samples")
            
    except Exception as e:
        print(f"❌ Error validating {cluster_file}: {e}")
EOF
```

### 3.4 Prediction Results Validation
```bash
# Validate prediction/scoring results
python3 << 'EOF'
import pandas as pd
import numpy as np
import glob
import os

base_dir = "/tmp/emuses_cli_test_outputs/model_registry_test"

# Look for prediction results
pred_files = glob.glob(os.path.join(base_dir, "**/*predict*.csv"), recursive=True)
pred_files.extend(glob.glob(os.path.join(base_dir, "**/*score*.csv"), recursive=True))

print("Validating prediction results...")

for pred_file in pred_files:
    try:
        df = pd.read_csv(pred_file)
        print(f"\n📊 Prediction file: {os.path.basename(pred_file)}")
        print(f"   Shape: {df.shape}")
        
        # Look for prediction/score columns
        pred_cols = [col for col in df.columns if any(keyword in col.lower() 
                    for keyword in ['predict', 'score', 'prob', 'target'])]
        
        for pred_col in pred_cols[:3]:  # Check first 3 prediction columns
            values = df[pred_col].dropna()
            
            print(f"   Column '{pred_col}':")
            print(f"     Range: {values.min():.4f} to {values.max():.4f}")
            print(f"     Mean: {values.mean():.4f}, Std: {values.std():.4f}")
            
            # Check for reasonable prediction values
            if values.min() == values.max():
                print("     ⚠️ All predictions are identical")
            elif np.any(np.isinf(values)) or np.any(np.isnan(values)):
                print("     ❌ Contains invalid values (inf/nan)")
            else:
                print("     ✅ Prediction values look reasonable")
                
            # For probability-like scores, check if they're in [0,1]
            if 'prob' in pred_col.lower() and (values.min() < 0 or values.max() > 1):
                print("     ⚠️ Probabilities outside [0,1] range")
                
    except Exception as e:
        print(f"❌ Error validating {pred_file}: {e}")
EOF
```

## 4. Reproducibility Testing

### 4.1 Deterministic Output Testing
```bash
# Test if results are reproducible with same parameters
echo "Testing reproducibility..."

# Run same command twice with identical parameters
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/repro_test_1" \
    "test_data.csv" \
    --columns_are_features \
    --input_normalization robust \
    --umap_trials 1 \
    --hdbscan_trials 1 \
    --optuna_trials 3 \
    --n_jobs 1 \
    --random_state 42 \
    2>&1 > /tmp/emuses_cli_test_outputs/repro_1.log

python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/repro_test_2" \
    "test_data.csv" \
    --columns_are_features \
    --input_normalization robust \
    --umap_trials 1 \
    --hdbscan_trials 1 \
    --optuna_trials 3 \
    --n_jobs 1 \
    --random_state 42 \
    2>&1 > /tmp/emuses_cli_test_outputs/repro_2.log

# Compare outputs
echo "Comparing reproducibility results..."
# This would need to be adapted based on actual output structure
```

### 4.2 Cross-Platform Validation
```bash
# Document platform-specific information
echo "Platform information:" > /tmp/emuses_cli_test_outputs/platform_info.txt
uname -a >> /tmp/emuses_cli_test_outputs/platform_info.txt
python --version >> /tmp/emuses_cli_test_outputs/platform_info.txt
python -c "import numpy; print(f'NumPy: {numpy.__version__}')" >> /tmp/emuses_cli_test_outputs/platform_info.txt
python -c "import pandas; print(f'Pandas: {pandas.__version__}')" >> /tmp/emuses_cli_test_outputs/platform_info.txt
python -c "import sklearn; print(f'Scikit-learn: {sklearn.__version__}')" >> /tmp/emuses_cli_test_outputs/platform_info.txt
```

## 5. Output Quality Metrics

### 5.1 Statistical Validation
```bash
# Generate statistical summaries of outputs
python3 << 'EOF'
import pandas as pd
import numpy as np
import glob
import os
from scipy import stats

base_dir = "/tmp/emuses_cli_test_outputs/model_registry_test"

print("Statistical validation of outputs...")

# Generate comprehensive statistics for all CSV outputs
csv_files = glob.glob(os.path.join(base_dir, "**/*.csv"), recursive=True)

for csv_file in csv_files[:3]:  # Limit for testing
    try:
        df = pd.read_csv(csv_file)
        numeric_df = df.select_dtypes(include=[np.number])
        
        if len(numeric_df.columns) > 0:
            print(f"\n📈 Statistical summary for {os.path.basename(csv_file)}:")
            print(numeric_df.describe())
            
            # Check for statistical anomalies
            for col in numeric_df.columns[:3]:  # First 3 numeric columns
                data = numeric_df[col].dropna()
                if len(data) > 10:
                    # Test for normality (for diagnostic purposes)
                    try:
                        stat, p_value = stats.normaltest(data)
                        print(f"   {col} normality test p-value: {p_value:.4f}")
                    except:
                        pass
                        
                    # Check for outliers using IQR
                    Q1, Q3 = np.percentile(data, [25, 75])
                    IQR = Q3 - Q1
                    outliers = data[(data < Q1 - 1.5*IQR) | (data > Q3 + 1.5*IQR)]
                    if len(outliers) > 0:
                        print(f"   {col}: {len(outliers)} potential outliers ({len(outliers)/len(data)*100:.1f}%)")
                        
    except Exception as e:
        print(f"Error in statistical analysis of {csv_file}: {e}")
EOF
```

## 6. Comparison with Expected Results

### 6.1 Reference Data Comparison (if available)
```bash
# If we have reference results, compare against them
# This section would be adapted based on available reference data

echo "Reference comparison testing..."
# Compare key metrics against known good results
# This would require having baseline/reference outputs
```

### 6.2 Sanity Checks
```bash
# Basic sanity checks for scientific validity
python3 << 'EOF'
import pandas as pd
import numpy as np
import glob
import os

base_dir = "/tmp/emuses_cli_test_outputs/model_registry_test"

print("Running sanity checks on outputs...")

# Check that sample counts are consistent across files
csv_files = glob.glob(os.path.join(base_dir, "**/*.csv"), recursive=True)
sample_counts = {}

for csv_file in csv_files:
    try:
        df = pd.read_csv(csv_file, nrows=0)  # Just get the shape
        df_full = pd.read_csv(csv_file)
        sample_counts[os.path.basename(csv_file)] = len(df_full)
    except Exception as e:
        print(f"Error reading {csv_file}: {e}")

if sample_counts:
    print("Sample counts across files:")
    for file, count in sample_counts.items():
        print(f"  {file}: {count} samples")
    
    # Check if counts are consistent (they should be for most EMUSES outputs)
    unique_counts = set(sample_counts.values())
    if len(unique_counts) == 1:
        print("✅ Sample counts are consistent across files")
    else:
        print(f"⚠️ Inconsistent sample counts: {unique_counts}")
EOF
```

## 7. Output Validation Results Summary

### ✅ Valid Outputs
| File Type | Status | Quality Score | Notes |
|-----------|--------|---------------|-------|
| CSV files | ⏳ | ⏳ | ⏳ |
| Model files | ⏳ | ⏳ | ⏳ |
| Plots | ⏳ | ⏳ | ⏳ |
| Configs | ⏳ | ⏳ | ⏳ |

### ❌ Invalid Outputs
| File | Issue | Severity | Impact |
|------|-------|----------|--------|
| | | | |

### ⚠️ Quality Concerns  
| Output | Issue | Recommendation |
|--------|-------|----------------|
| | | |

### 🔬 Scientific Validity
| Analysis | Result | Confidence | Notes |
|----------|--------|------------|-------|
| UMAP coordinates | ⏳ | ⏳ | ⏳ |
| Clustering results | ⏳ | ⏳ | ⏳ |
| Predictions | ⏳ | ⏳ | ⏳ |
| Statistical properties | ⏳ | ⏳ | ⏳ |

## 8. Next Steps

Based on output validation results:
1. **Critical Issues**: Fix any invalid outputs or corrupted files
2. **Quality Improvements**: Address low-quality or suspicious results  
3. **Documentation**: Update docs with output format specifications
4. **Validation Scripts**: Create automated validation for future testing

## Files Generated
- Output validation reports
- Statistical summaries  
- File integrity checks
- Reproducibility test results
- Quality metrics documentation

## Notes
- Output validation is critical for scientific software - prioritize this testing
- Save reference outputs from successful runs for future comparison
- Document the expected ranges and characteristics of all output types
- Consider creating automated validation scripts for continuous testing
