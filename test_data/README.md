# EMUSES Test Data

This folder contains synthetic datasets designed for testing and demonstrating EMUSES pipeline functionality.

## 📁 Files

### Main Test Data (Synthetic, Optimized for Pipeline Testing)
- **`features.csv`** - 50 samples × 8 features - Input data matrix for EMUSES analysis
- **`regression_scores.csv`** - 50 continuous targets (0.68-0.93) - For single-target regression mode
- **`regression_scores_multitarget.csv`** - 50 samples × 2 targets (0.35-0.95) - For multi-target regression mode  
- **`classification_labels.csv`** - 50 binary labels (0/1) - For binary classification mode
- **`classification_labels_multiclass.csv`** - 50 multi-class labels (0,1,2,3) - For multi-class classification mode

### Swiss roll (added 2026-09-06, for the numerical regression suite)
- **`swiss_roll_features.csv`** - 300 samples × 3 coordinates
- **`swiss_roll_scores.csv`** - 300 continuous targets, range 4.76–14.04

**Why it exists.** The 50-sample fixtures above have no recoverable signal for
regression: the winning ElasticNet zeroes every coefficient in every fold, so the
prediction is a constant intercept and its score cannot respond to a change in the
embedding coordinates. This one has a target that is recoverable *by construction* —
`t` is each sample's own position along the roll — so the prediction path genuinely
reads the embedding (`Mean_Score` 0.9962). See `tests/regression/README.md`.

**The committed CSVs are authoritative, not this recipe.** They were produced once,
with scikit-learn 1.7.2, by:

```python
import numpy as np
from sklearn.datasets import make_swiss_roll
X, t = make_swiss_roll(n_samples=300, noise=0.0, random_state=42)
np.savetxt("test_data/swiss_roll_features.csv", X, delimiter=",", fmt="%.17g")
np.savetxt("test_data/swiss_roll_scores.csv", t, delimiter=",", fmt="%.17g")
```

`%.17g` round-trips the doubles exactly, so the files are a precise record of that
draw. Do **not** regenerate them to "refresh" the data: `make_swiss_roll` is not
guaranteed stable across scikit-learn versions, and a fixture that changes quietly
underneath a pinned baseline is the exact failure the regression suite exists to
catch. If they must be regenerated, re-record the baselines in the same commit and
say why.


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