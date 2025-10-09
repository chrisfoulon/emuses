# EMUSES Test Data

This folder contains synthetic datasets designed for testing and demonstrating EMUSES pipeline functionality.

## 📁 Files

### Main Test Data (Synthetic, Optimized for Pipeline Testing)
- **`features.csv`** - 50 samples × 8 features - Input data matrix for EMUSES analysis
- **`regression_scores.csv`** - 50 continuous targets (0.68-0.93) - For single-target regression mode
- **`regression_scores_multitarget.csv`** - 50 samples × 2 targets (0.35-0.95) - For multi-target regression mode  
- **`classification_labels.csv`** - 50 binary labels (0/1) - For binary classification mode
- **`classification_labels_multiclass.csv`** - 50 multi-class labels (0,1,2,3) - For multi-class classification mode


## 🎯 Usage Examples

### Regression Mode
```bash
python -m emuses.cli full ~/output_regression \
  test_data/features.csv \
  --columns_are_features \
  --input_normalization robust \
  --scores test_data/regression_scores.csv \
  --umap_trials 1 \
  --hdbscan_trials 1 \
  --optim_dict optim_dict_hcp \
  --prediction_optim_dict quick_train_dict \
  --optuna_trials 3 \
  --n_jobs 4
```

### Multi-Target Regression Mode
```bash
python -m emuses.cli full ~/output_multitarget \
  test_data/features.csv \
  --columns_are_features \
  --input_normalization robust \
  --scores test_data/regression_scores_multitarget.csv \
  --umap_trials 1 \
  --hdbscan_trials 1 \
  --optim_dict optim_dict_hcp \
  --prediction_optim_dict quick_train_dict \
  --optuna_trials 3 \
  --n_jobs 4
```

### Binary Classification Mode  
```bash
python -m emuses.cli full ~/output_classification \
  test_data/features.csv \
  --columns_are_features \
  --input_normalization robust \
  --scores test_data/classification_labels.csv \
  --umap_trials 1 \
  --hdbscan_trials 1 \
  --optim_dict optim_dict_hcp \
  --prediction_optim_dict quick_train_dict \
  --optuna_trials 3 \
  --n_jobs 4
```

### Multi-Class Classification Mode
```bash
python -m emuses.cli full ~/output_multiclass \
  test_data/features.csv \
  --columns_are_features \
  --input_normalization robust \
  --scores test_data/classification_labels_multiclass.csv \
  --umap_trials 1 \
  --hdbscan_trials 1 \
  --optim_dict optim_dict_hcp \
  --prediction_optim_dict quick_train_dict \
  --optuna_trials 3 \
  --n_jobs 4
```

## ⚡ Performance

- **Execution Time**: ~40-45 seconds per run
- **CI Compatible**: Fast enough for automated testing
- **Cross-Validation Stable**: 50 samples provide sufficient data for 5-fold CV
- **Complete Pipeline**: Generates full EMUSES model folders with all required components

## 🔧 Technical Details

### Data Characteristics
- **Sample Size**: 50 (optimal for testing - sufficient for ML algorithms, fast execution)
- **Feature Dimensions**: 8 (manageable complexity for visualization and debugging)
- **Data Orientation**: Standard ML format (rows=observations, columns=features)
- **Missing Values**: None (clean data for reliable testing)
- **Synthetic Generation**: Mathematically constructed with controlled variation

### Key Requirements for Usage
1. **Always use `--columns_are_features`** flag to ensure correct data orientation
2. **Minimum 3 Optuna trials** recommended for meaningful optimization
3. **50+ samples required** for stable cross-validation performance

### Why This Size?
The 50-sample size was chosen as the optimal balance:
- ✅ **Large enough**: Supports 5-fold cross-validation with sufficient samples per fold
- ✅ **Fast enough**: Completes full pipeline in under 1 minute for CI integration
- ✅ **Realistic enough**: Provides meaningful ML optimization and validation
- ✅ **Small enough**: Quick to understand, debug, and modify

## 🏗️ Generated During Pipeline Testing
These datasets were validated by running complete EMUSES pipelines successfully across all modes:
- **Single-target regression**: 50 continuous targets (0.68-0.93)
- **Multi-target regression**: 50 samples × 2 targets (0.35-0.95)
- **Binary classification**: 50 labels with classes 0,1
- **Multi-class classification**: 50 labels with classes 0,1,2,3
- All stages complete (UMAP, HDBSCAN, Heatmap, Inference)  
- All optimization methods working (Optuna hyperparameter search)
- All file outputs generated (models, visualizations, predictions)
- Both matplotlib memory leak and small dataset issues resolved

## 📊 Design Philosophy
These 50-sample synthetic datasets were designed to resolve common testing issues:
- ✅ Large enough for stable cross-validation (10+ samples per fold)
- ✅ Sufficient data for Optuna hyperparameter optimization
- ✅ Clear data orientation with documented flag usage
- ✅ Reliable pipeline execution that validates real functionality

The datasets provide comprehensive coverage for all EMUSES prediction modes while maintaining fast execution for testing.