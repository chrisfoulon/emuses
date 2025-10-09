# Task 4.2.4: Troubleshooting Guide for Common Preprocessing Issues

## Most Common Error: "No numeric data remaining after processing"

### Problem Description
This is the original issue that motivated the entire parameter implementation. It occurs when EMUSES cannot find numeric data to process after applying default preprocessing.

### Root Causes and Solutions

#### Cause 1: CSV files with headers (Most Common)
**Error Symptoms**:
- "No header row specified (header=None)"
- "Many columns were removed - formatting issue"
- "No numeric data remaining after processing"

**Solution**:
```bash
# Add header parameter to specify first row contains column names
--input_header 0
```

**Example**:
```bash
# Before (fails):
emuses inference data_with_headers.csv output/ --model /path/to/model

# After (works):
emuses inference data_with_headers.csv output/ --model /path/to/model --input_header 0
```

#### Cause 2: CSV files with sample IDs in first column
**Error Symptoms**:
- "No index column specified (index_col=None)"  
- "First column treated as feature instead of sample ID"
- "Dimension mismatch errors"

**Solution**:
```bash
# Add index column parameter to specify first column contains sample IDs
--input_index_column 0
```

**Example**:
```bash
# Before (fails):
emuses inference data_with_ids.csv output/ --model /path/to/model --input_header 0

# After (works):
emuses inference data_with_ids.csv output/ --model /path/to/model --input_header 0 --input_index_column 0
```

#### Cause 3: Wrong data orientation
**Error Symptoms**:
- "Unexpected number of features"
- "Shape mismatch between data and model"
- Model expects different data layout

**Solution**:
```bash
# If columns represent features (not samples), add orientation flag
--columns_are_features
```

**Example**:
```bash
# For feature matrix where each column is a feature:
emuses inference feature_matrix.csv output/ --model /path/to/model --input_header 0 --input_index_column 0 --columns_are_features
```

### Complete Solution Pattern
For most CSV files with both headers and sample IDs:
```bash
emuses inference your_data.csv output/ \
  --model /path/to/model \
  --input_header 0 \
  --input_index_column 0 \
  --columns_are_features
```

## Model Loading Issues

### Error: "Model not found" or "Invalid model path"

#### For Local Models
**Solution**: Verify model directory structure
```bash
# Check if model directory exists and contains required files
ls -la /path/to/your/model/
# Should contain: model files, metadata, etc.

# Correct path format:
--model /absolute/path/to/model/directory/
```

#### For Registry Models  
**Solution**: Verify model ID exists
```bash
# List available registry models
emuses list-models

# Use exact model ID from list:
--model-id "exact_model_id_from_registry"
```

### Error: "'NoneType' object is not subscriptable" 
**Problem**: This was a bug in inference mode architecture (now fixed)
**Solution**: Ensure you're using the updated version with inference mode separation

## Validation Mode Issues

### Error: "Validation mode requires scores file"
**Cause**: Using `--validate` flag without providing scores
**Solutions**:
```bash
# Option 1: Provide scores file
--scores /path/to/ground_truth.csv --scores_header 0 --scores_index_column 0 --validate

# Option 2: Remove validation flag for prediction-only mode
# (remove --validate from command)
```

### Error: "Scores file not found" 
**Solution**: Check scores file path and format
```bash
# Verify scores file exists
ls -la /path/to/scores.csv

# Ensure scores file format matches parameters
--scores /path/to/scores.csv --scores_header 0 --scores_index_column 0
```

## Data Format Issues

### Error: "Column 'X' not found"
**Cause**: Specified column doesn't exist in data
**Solution**: Check data structure first
```bash
# Examine your data structure:
head -n 5 your_data.csv

# Adjust column specifications based on actual data:
--inputs_columns "actual_column1,actual_column2,actual_column3"
```

### Error: "Parsing error" or "CSV reading failed"
**Cause**: Unusual CSV format or separator
**Solutions**:
```bash
# For different separators (semicolon, tab, etc.):
--arg_separator ";"    # For semicolon-separated files
--arg_separator "\t"   # For tab-separated files

# Check your file format first:
head -n 3 your_data.csv
```

## Normalization Issues

### Error: "Invalid normalization method"
**Solution**: Use correct normalization options
```bash
# Valid normalization methods:
--input_normalization none      # No normalization (default)
--input_normalization zscore    # Z-score (mean=0, std=1) 
--input_normalization min-max   # Scale to [0,1]
--input_normalization zero-max  # Scale to [0,max]
--input_normalization robust    # Robust scaling (recommended)
```

### Error: "Normalization failed" or "All values are the same"
**Cause**: Data has no variation (all identical values)
**Solution**: Check data quality and consider different normalization
```bash
# Use robust normalization for better handling of outliers/constants:
--input_normalization robust
```

## Output Issues

### Error: "Output path required" 
**Cause**: Missing required output parameter (security feature)
**Solution**: Always specify output path
```bash
# Output is required for data privacy:
emuses inference data.csv /path/to/output/ --model /path/to/model
```

### Error: "Permission denied" writing output
**Cause**: No write access to output directory
**Solutions**:
```bash
# Check directory exists and is writable:
ls -ld /path/to/output/
mkdir -p /path/to/output/  # Create if needed

# Use absolute paths:
emuses inference data.csv /absolute/path/to/output/ --model /path/to/model
```

## Performance Issues

### Slow Performance
**Solutions**:
```bash
# Use registry models (faster loading):
--model-id "model_id" instead of --model /long/path/

# Limit to essential columns:
--inputs_columns "feature1,feature2,feature3"

# Use efficient normalization:
--input_normalization robust  # Better than zscore for large datasets
```

### Memory Issues
**Solutions**:
```bash
# Filter to only labeled data:
--filter_labelled_by_scores

# Limit column selection:
--inputs_columns "essential_columns_only"

# Avoid recursive search unless necessary:
# (don't use --recursive-input-file-search for single files)
```

## Debugging Workflow

### Step 1: Check Data Structure
```bash
# Always start by examining your data:
head -n 5 your_data.csv
# Look for: headers, sample IDs, data orientation, separators
```

### Step 2: Start with Basic Parameters
```bash
# Begin with minimal working command:
emuses inference your_data.csv output/ --model /path/to/model --input_header 0 --input_index_column 0
```

### Step 3: Add Parameters Incrementally
```bash
# Add normalization if needed:
+ --columns_are_features --input_normalization robust

# Add validation if needed:  
+ --scores scores.csv --scores_header 0 --scores_index_column 0 --validate
```

### Step 4: Check Error Messages Carefully
- "No numeric data remaining" → Add `--input_header 0 --input_index_column 0`
- "Model not found" → Check model path/ID
- "Scores file not found" → Check scores file path or remove validation
- "Column not found" → Check column names and data structure

## Quick Reference: Parameter Checklist

### Essential Parameters (Always Check)
- [ ] Data file path (positional argument)
- [ ] Output path (positional argument) 
- [ ] Model source (`--model` OR `--model-id`)
- [ ] Input header (`--input_header 0` if CSV has headers)
- [ ] Input index column (`--input_index_column 0` if CSV has sample IDs)

### Data Structure Parameters (Check If Needed)
- [ ] Data orientation (`--columns_are_features` if columns = features)
- [ ] Normalization (`--input_normalization robust` for most cases)
- [ ] Column selection (`--inputs_columns` if using subset)

### Validation Parameters (Only If Validating)
- [ ] Scores file (`--scores /path/to/scores.csv`)
- [ ] Scores header (`--scores_header 0` if scores have headers)
- [ ] Scores index (`--scores_index_column 0` if scores have sample IDs)
- [ ] Validation flag (`--validate`)

## Success Indicators
**When inference runs successfully, you should see**:
- "Processed X samples across Y prediction targets"
- "Throughput: X.X samples/sec"
- Output files created in specified output directory
- No error messages about missing data or format issues