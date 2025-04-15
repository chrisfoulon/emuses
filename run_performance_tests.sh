#!/bin/bash

# Set up the base paths
EMUSES_PATH="/gamma/Dropbox (GIN)/EMUSE/package/emuses"
HCP_PATH="/gamma/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy"
SCRIPT_PATH="$EMUSES_PATH/emuses/scripts/main.py"

echo "================================================================================"
echo "Starting EMUSES pipeline comparison tests with different scaling methods"
echo "================================================================================"

# Make sure the script is executable
chmod +x "$SCRIPT_PATH"

# Create output directories
mkdir -p "$HCP_PATH/model_comparison_minmax"
mkdir -p "$HCP_PATH/model_comparison_robust"

# Run model comparison with min-max scaling using main.py
echo "Running model selection with min-max scaling..."
python3 "$SCRIPT_PATH" full "$HCP_PATH/model_comparison_minmax" \
  "$HCP_PATH/selected_columns_data.csv" \
  --columns_are_features \
  --input_header 0 \
  --input_index_column 0 \
  -inorm min-max \
  --scores "$HCP_PATH/specific_columns_data.csv" \
  --scores_header 0 \
  --scores_index_column 0 \
  --interactive_plot \
  --umap_trials 1 \
  --hdbscan_trials 1 \
  --optim_dict optim_dict_hcp \
  --hdbscan_jobs 16 \
  --use_enhanced_pipeline \
  --optuna_trials 50 \
  --parallel_models \
  --n_jobs 60

# Run model comparison with robust scaling using main.py
echo "Running model selection with robust scaling..."
python3 "$SCRIPT_PATH" full "$HCP_PATH/model_comparison_robust" \
  "$HCP_PATH/selected_columns_data.csv" \
  --columns_are_features \
  --input_header 0 \
  --input_index_column 0 \
  -inorm robust \
  --scores "$HCP_PATH/specific_columns_data.csv" \
  --scores_header 0 \
  --scores_index_column 0 \
  --interactive_plot \
  --umap_trials 1 \
  --hdbscan_trials 1 \
  --optim_dict optim_dict_hcp \
  --hdbscan_jobs 16 \
  --use_enhanced_pipeline \
  --optuna_trials 50 \
  --parallel_models \
  --n_jobs 60

# Compare different scaling methods for the fully labelled mode (original pipeline)
echo "Running fully labelled mode with min-max scaling (original pipeline)..."
python3 "$SCRIPT_PATH" full "$HCP_PATH/debug_tabular_fully_labelled" \
  "$HCP_PATH/selected_columns_data.csv" \
  --columns_are_features \
  --input_header 0 \
  --input_index_column 0 \
  -inorm min-max \
  --scores "$HCP_PATH/specific_columns_data.csv" \
  --scores_header 0 \
  --scores_index_column 0 \
  --interactive_plot \
  --umap_trials 1 \
  --hdbscan_trials 1 \
  --optim_dict optim_dict_hcp \
  --hdbscan_jobs 16

# Run fully labelled mode with robust scaling (original pipeline)
echo "Running fully labelled mode with robust scaling (original pipeline)..."
python3 "$SCRIPT_PATH" full "$HCP_PATH/debug_tabular_fully_labelled_robust" \
  "$HCP_PATH/selected_columns_data.csv" \
  --columns_are_features \
  --input_header 0 \
  --input_index_column 0 \
  -inorm robust \
  --scores "$HCP_PATH/specific_columns_data.csv" \
  --scores_header 0 \
  --scores_index_column 0 \
  --interactive_plot \
  --umap_trials 1 \
  --hdbscan_trials 1 \
  --optim_dict optim_dict_hcp \
  --hdbscan_jobs 16

# Run the split labelled mode tests
echo "Running split labelled mode with enhanced pipeline..."
python3 "$SCRIPT_PATH" full "$HCP_PATH/debug_tabular_split_enhanced" \
  "$HCP_PATH/training_split_selected_columns.csv" \
  --columns_are_features \
  --input_header 0 \
  --input_index_column 0 \
  -inorm min-max \
  --label_dataset "$HCP_PATH/test_split_selected_columns.csv" \
  --scores "$HCP_PATH/test_split_specific_columns.csv" \
  --scores_header 0 \
  --interactive_plot \
  --umap_trials 1 \
  --hdbscan_trials 1 \
  --optim_dict optim_dict_hcp \
  --hdbscan_jobs 16 \
  --filter_labelled_by_scores \
  --test_size 0.0 \
  --use_enhanced_pipeline \
  --optuna_trials 50 \
  --parallel_models \
  --n_jobs 60

echo "================================================================================"
echo "All tests complete! Generating performance comparison report..."
echo "================================================================================"

# Create a report directory
REPORT_DIR="$HCP_PATH/performance_comparison_report"
mkdir -p "$REPORT_DIR"

# Copy performance files to the report directory for analysis
cp "$HCP_PATH/debug_tabular_fully_labelled/gp_performance_summary.json" "$REPORT_DIR/fully_labelled_minmax_gp_performance.json"
cp "$HCP_PATH/debug_tabular_fully_labelled_robust/gp_performance_summary.json" "$REPORT_DIR/fully_labelled_robust_gp_performance.json"
cp "$HCP_PATH/model_comparison_minmax/pipeline_results_summary.json" "$REPORT_DIR/model_comparison_minmax_summary.json"
cp "$HCP_PATH/model_comparison_robust/pipeline_results_summary.json" "$REPORT_DIR/model_comparison_robust_summary.json"
cp "$HCP_PATH/debug_tabular_split_enhanced/pipeline_results_summary.json" "$REPORT_DIR/split_enhanced_summary.json"

# Copy prediction performance files and model comparison data
cp "$HCP_PATH/debug_tabular_fully_labelled/prediction_performance/prediction_performance.json" "$REPORT_DIR/fully_labelled_minmax_prediction_performance.json"
cp "$HCP_PATH/debug_tabular_fully_labelled_robust/prediction_performance/prediction_performance.json" "$REPORT_DIR/fully_labelled_robust_prediction_performance.json"
cp "$HCP_PATH/model_comparison_minmax/model_performance_summary.csv" "$REPORT_DIR/model_comparison_minmax_summary.csv"
cp "$HCP_PATH/model_comparison_robust/model_performance_summary.csv" "$REPORT_DIR/model_comparison_robust_summary.csv"
cp "$HCP_PATH/debug_tabular_split_enhanced/model_performance_summary.csv" "$REPORT_DIR/split_enhanced_summary.csv"

echo "Performance files copied to $REPORT_DIR"
echo "You can now analyze the results to compare the performance of different scaling methods and models."

# Create a simple consolidated report
echo "=== PERFORMANCE COMPARISON REPORT ===" > "$REPORT_DIR/consolidated_report.txt"
echo "" >> "$REPORT_DIR/consolidated_report.txt"
echo "This report compares the performance of different models and scaling methods." >> "$REPORT_DIR/consolidated_report.txt"
echo "" >> "$REPORT_DIR/consolidated_report.txt"

echo "1. Enhanced Pipeline Model Selection Results" >> "$REPORT_DIR/consolidated_report.txt"
echo "----------------------------------" >> "$REPORT_DIR/consolidated_report.txt"
echo "Min-Max Scaling:" >> "$REPORT_DIR/consolidated_report.txt"
echo "$(cat $REPORT_DIR/model_comparison_minmax_summary.json)" >> "$REPORT_DIR/consolidated_report.txt"
echo "" >> "$REPORT_DIR/consolidated_report.txt"
echo "Robust Scaling:" >> "$REPORT_DIR/consolidated_report.txt"
echo "$(cat $REPORT_DIR/model_comparison_robust_summary.json)" >> "$REPORT_DIR/consolidated_report.txt"
echo "" >> "$REPORT_DIR/consolidated_report.txt"

echo "2. Original Pipeline GP Performance" >> "$REPORT_DIR/consolidated_report.txt"
echo "----------------------------------" >> "$REPORT_DIR/consolidated_report.txt"
echo "Min-Max Scaling:" >> "$REPORT_DIR/consolidated_report.txt"
echo "$(cat $REPORT_DIR/fully_labelled_minmax_gp_performance.json)" >> "$REPORT_DIR/consolidated_report.txt"
echo "" >> "$REPORT_DIR/consolidated_report.txt"
echo "Robust Scaling:" >> "$REPORT_DIR/consolidated_report.txt"
echo "$(cat $REPORT_DIR/fully_labelled_robust_gp_performance.json)" >> "$REPORT_DIR/consolidated_report.txt"
echo "" >> "$REPORT_DIR/consolidated_report.txt"

echo "3. Split Labelled Mode Results" >> "$REPORT_DIR/consolidated_report.txt"
echo "----------------------------------" >> "$REPORT_DIR/consolidated_report.txt"
echo "$(cat $REPORT_DIR/split_enhanced_summary.json)" >> "$REPORT_DIR/consolidated_report.txt"

echo "Consolidated report created at $REPORT_DIR/consolidated_report.txt"