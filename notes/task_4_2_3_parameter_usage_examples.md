# Task 4.2.3: Parameter Usage Patterns and Examples

## Common Usage Scenarios

### Scenario 1: Basic CSV File with Headers
**Problem**: CSV file has column headers in first row, sample IDs in first column
**Solution**: Use header and index column parameters
```bash
emuses inference data_with_headers.csv /path/to/output \
  --model /path/to/trained/model \
  --input_header 0 \
  --input_index_column 0
```

### Scenario 2: Normalized Data Processing
**Problem**: Input data needs robust normalization, columns represent features
**Solution**: Use normalization and data orientation parameters
```bash
emuses inference raw_features.csv /path/to/output \
  --model /path/to/trained/model \
  --input_header 0 \
  --input_index_column 0 \
  --columns_are_features \
  --input_normalization robust
```

### Scenario 3: Validation Mode with Ground Truth
**Problem**: Want to validate model predictions against known scores
**Solution**: Use validation mode with scores file
```bash
emuses inference test_data.csv /path/to/output \
  --model /path/to/trained/model \
  --input_header 0 \
  --input_index_column 0 \
  --scores validation_scores.csv \
  --scores_header 0 \
  --scores_index_column 0 \
  --validate
```

### Scenario 4: Registry Model with Classification
**Problem**: Using registered model for classification instead of regression
**Solution**: Use model registry and classification mode
```bash
emuses inference features.csv /path/to/output \
  --model-id "my_classification_model_v1" \
  --input_header 0 \
  --input_index_column 0 \
  --columns_are_features \
  --classification
```

### Scenario 5: Advanced Data Processing
**Problem**: Complex data with specific column selection and normalization
**Solution**: Use advanced parameter combinations
```bash
emuses inference complex_data.csv /path/to/output \
  --model /path/to/trained/model \
  --input_header 0 \
  --input_index_column 0 \
  --inputs_columns "feature1,feature2,feature3" \
  --input_normalization zscore \
  --columns_are_features
```

## Parameter Pattern Groups

### File Structure Parameters (Essential)
These parameters handle basic CSV file structure:
```bash
--input_header 0               # First row contains headers
--input_index_column 0         # First column contains sample IDs
--scores_header 0              # Scores file has headers  
--scores_index_column 0        # Scores file has sample IDs
```

### Data Orientation Parameters
These parameters specify how data is arranged:
```bash
--columns_are_features         # Each column = one feature (common)
                              # Default: each row = one feature
--scores_are_rows             # Each row = one score observation
                              # Default: each column = one score
```

### Normalization Parameters
These parameters control data preprocessing:
```bash
--input_normalization robust   # Robust scaling (recommended for outliers)
--input_normalization zscore   # Z-score normalization (mean=0, std=1) 
--input_normalization min-max  # Min-max scaling to [0,1]
--input_normalization zero-max # Zero-max scaling to [0,max]
--input_normalization none     # No normalization (default)

--scores_normalization zscore  # Apply normalization to validation scores
```

### Column Selection Parameters
These parameters filter data columns:
```bash
--inputs_columns "col1,col2,col3"    # Use specific input columns
--scores_column "score1,score2"      # Use specific score columns  
--filter_labelled_by_scores          # Only use samples with scores
```

### Mode Selection Parameters
These parameters control inference behavior:
```bash
--classification              # Classification mode (discrete outputs)
                              # Default: regression mode (continuous outputs)
--validate                    # Force validation mode (requires --scores)
```

### File Discovery Parameters (Advanced)
These parameters control how input files are found:
```bash
--recursive-input-file-search          # Search subdirectories
--input_file_types "csv,tsv"          # Limit to specific file types
--bids_filters "task-rest,ses-01"     # BIDS dataset filtering
--arg_separator ";"                    # Use semicolon instead of comma
```

## Common Parameter Combinations

### Beginner Pattern (Most Common)
For basic CSV files with headers and sample IDs:
```bash
emuses inference data.csv output/ \
  --model /path/to/model \
  --input_header 0 \
  --input_index_column 0
```

### Data Science Pattern
For feature matrices requiring normalization:
```bash
emuses inference features.csv output/ \
  --model /path/to/model \
  --input_header 0 \
  --input_index_column 0 \
  --columns_are_features \
  --input_normalization robust
```

### Validation Pattern  
For model evaluation with ground truth:
```bash
emuses inference test_data.csv output/ \
  --model /path/to/model \
  --input_header 0 \
  --input_index_column 0 \
  --scores ground_truth.csv \
  --scores_header 0 \
  --scores_index_column 0 \
  --validate
```

### Production Pattern
For registry models with specific preprocessing:
```bash
emuses inference production_data.csv output/ \
  --model-id "production_model_v2" \
  --input_header 0 \
  --input_index_column 0 \
  --columns_are_features \
  --input_normalization robust \
  --inputs_columns "feature1,feature2,feature3"
```

## Error Prevention Guide

### Required Parameters
Always specify these for basic functionality:
- Input data path (positional argument)
- Output path (positional argument)
- Model source (`--model` OR `--model-id`)

### Critical Parameter Pairs
These parameters work together and should be used consistently:
- `--input_header` + `--input_index_column` for structured CSV files
- `--scores` + `--scores_header` + `--scores_index_column` for validation
- `--columns_are_features` + appropriate normalization for feature matrices

### Validation Dependencies
- `--validate` requires `--scores` parameter
- `--scores_*` parameters require `--scores` parameter
- `--model` and `--model-id` are mutually exclusive (use one, not both)

## Performance Optimization Tips

### Memory Efficiency
```bash
# For large datasets, avoid loading unnecessary columns
--inputs_columns "essential_feature1,essential_feature2"

# Filter to only needed observations
--filter_labelled_by_scores
```

### Processing Speed
```bash
# Use robust normalization for better numerical stability
--input_normalization robust

# Avoid recursive search unless necessary
# (default behavior is more efficient for single files)
```

### Model Registry Performance
```bash
# Registry models load faster than path-based models
--model-id "optimized_model_v1"  # Faster
# vs
--model /long/path/to/model/     # Slower for large models
```

## Troubleshooting Common Issues

### "No numeric data remaining after processing"
**Cause**: Usually header/index column not specified for CSV files
**Solution**: Add header and index parameters:
```bash
# Add these parameters:
--input_header 0 --input_index_column 0
```

### "Scores file not found" 
**Cause**: Validation mode requires scores file
**Solution**: Either provide scores or remove validation:
```bash
# Option 1: Add scores file
--scores /path/to/scores.csv --scores_header 0 --scores_index_column 0

# Option 2: Remove validation mode (remove --validate flag)
```

### "Model not found"
**Cause**: Invalid model path or model ID
**Solution**: Verify model location:
```bash
# For local models, check path exists:
ls -la /path/to/model/

# For registry models, list available models:
emuses list-models
```

### "Column not found"
**Cause**: Specified column doesn't exist in data
**Solution**: Check data structure and adjust column parameters:
```bash
# Check your data structure first:
head -n 3 your_data.csv

# Then adjust column specifications accordingly
```