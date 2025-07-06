# HCP API Test Script Usage Guide

## Overview

The `test_hcp_api.py` script runs the HCP real-world example using the EMUSES FastAPI instead of the CLI `main.py`. It automatically detects your operating system and converts file paths appropriately.

## Extracted Paths from Original Command

**Original Linux Command:**
```bash
/home/chrisfoulon/neuro_apps/emuses/emuses/scripts/main.py full /gamma/GIN\ Dropbox/Chris\ Foulon/EMUSE/HCP_psy/is_it_running /gamma/GIN\ Dropbox/Chris\ Foulon/EMUSE/HCP_psy/selected_columns_data.csv --columns_are_features --input_header 0 --input_index_column 0 -inorm robust --scores /gamma/GIN\ Dropbox/Chris\ Foulon/EMUSE/HCP_psy/specific_columns_data.csv --scores_header 0 --scores_index_column 0 --interactive_plot --umap_trials 1 --hdbscan_trials 1 --optim_dict optim_dict_hcp --hdbscan_jobs 16 --prediction_optim_dict optim_dict_predict
```

**Extracted File Paths:**
- **Output folder**: `/gamma/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/is_it_running`
- **Features file**: `/gamma/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv`
- **Scores file**: `/gamma/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/specific_columns_data.csv`

## Path Conversion

### Windows (automatic)
- `/gamma` → `S:\`
- Forward slashes → Backslashes
- **Result**: `S:\GIN Dropbox\Chris Foulon\EMUSE\HCP_psy\...`

### Linux/macOS (automatic)
- Keeps original `/gamma/...` paths

## How to Run

### Prerequisites
1. Make sure the network drive is mounted:
   - **Windows**: Map `/gamma` to `S:\` drive
   - **Linux**: Ensure `/gamma` is accessible
2. Verify the data files exist at the expected locations
3. Have the EMUSES FastAPI service dependencies installed

### Execution
```bash
# Navigate to your EMUSES project directory
cd c:\Users\Tolhsadum\PycharmProjects\emuses

# Run the API test script
python test_hcp_api.py
```

## What the Script Does

1. **🖥️ OS Detection**: Automatically detects Windows/Linux/macOS
2. **📁 Path Conversion**: Converts `/gamma` paths to appropriate format
3. **🔍 File Validation**: Checks that input CSV files exist and are readable
4. **📊 Data Loading**: Loads the actual HCP data files
5. **🚀 API Execution**: Runs the same pipeline as CLI but via FastAPI PipelineRunner
6. **✅ Validation**: Confirms outputs are generated correctly

## Expected Output

```
🧪 HCP Real-World Example - API Execution Test
============================================================
🖥️ Detected OS: windows
📁 Base path: S:\GIN Dropbox\Chris Foulon\EMUSE\HCP_psy
🔍 Validating input files...
✅ features_file: S:\GIN Dropbox\Chris Foulon\EMUSE\HCP_psy\selected_columns_data.csv
   Shape preview: (1000, 100)
   Columns preview: ['feature_0', 'feature_1', 'feature_2', 'feature_3', 'feature_4']...
✅ scores_file: S:\GIN Dropbox\Chris Foulon\EMUSE\HCP_psy\specific_columns_data.csv
   Shape preview: (1000, 3)
   Columns preview: ['target_0', 'target_1', 'target_2']

📋 Equivalent CLI command:
===============================================================================
python emuses/scripts/main.py full \
  "S:\GIN Dropbox\Chris Foulon\EMUSE\HCP_psy\is_it_running" \
  "S:\GIN Dropbox\Chris Foulon\EMUSE\HCP_psy\selected_columns_data.csv" \
  --columns_are_features \
  --input_header 0 \
  --input_index_column 0 \
  -inorm robust \
  --scores "S:\GIN Dropbox\Chris Foulon\EMUSE\HCP_psy\specific_columns_data.csv" \
  --scores_header 0 \
  --scores_index_column 0 \
  --interactive_plot \
  --umap_trials 1 \
  --hdbscan_trials 1 \
  --optim_dict optim_dict_hcp \
  --hdbscan_jobs 16 \
  --prediction_optim_dict optim_dict_predict
===============================================================================

📊 Loading data and creating pipeline context...
✅ Features loaded: (1000, 100)
✅ Scores loaded: (1000, 3)
🚀 Running HCP pipeline via API...
✅ Created job: 550e8400-e29b-41d4-a716-446655440000
✅ Job directory: ./api_jobs_hcp/550e8400-e29b-41d4-a716-446655440000
⏳ Executing pipeline (this may take several minutes)...
✅ Pipeline execution completed!
   Result context keys: ['input_matrix', 'scores', 'embeddings', 'models', ...]
   Final job status: COMPLETED
✅ Generated 15 output files
   ✅ umap_model.pkl
   ✅ embeddings.npy
   ✅ prediction_results.json

🎉 HCP pipeline completed successfully via API!
📁 Results saved to: S:\GIN Dropbox\Chris Foulon\EMUSE\HCP_psy\is_it_running

✅ Test completed successfully!
```

## Troubleshooting

### File Not Found Errors
- **Windows**: Ensure `S:\` drive is mapped to the network location
- **Linux**: Ensure `/gamma` mount point is accessible
- Check that the CSV files actually exist at the specified paths

### Permission Errors
- Ensure you have read access to the input files
- Ensure you have write access to the output directory

### Memory/Performance Issues
- The script uses the same parameters as the original command (16 parallel jobs)
- Consider reducing `hdbscan_jobs` if you have limited CPU cores
- The pipeline may take 10-30 minutes depending on data size and hardware

## Comparison with CLI

This API approach provides:
- **Same Results**: Identical output to running via `main.py`
- **Better Monitoring**: Job status tracking and progress updates
- **Background Execution**: Non-blocking execution with timeouts
- **Error Handling**: Better error capture and reporting
- **Job Management**: Organized output directories with job IDs

The script validates that the API produces the same results as the CLI would, ensuring computational equivalence between the two execution methods.
