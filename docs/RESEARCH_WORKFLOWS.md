# 🔬 EMUSES Research Workflows Guide

**Potential scientific use case patterns for research with EMUSES**

> **⚠️ Important Disclaimers**:
> - **These are AI-generated examples** that illustrate potential integration patterns
> - **External preprocessing scripts are conceptual examples** - user implementation required
> - **Workflows are not guaranteed to work** - they show possible research directions
> - **EMUSES core purpose**: Building predictive models from neuroimaging features
> - **Validation required**: Always test thoroughly with your specific data and requirements

This guide provides potential workflow ideas for scientific research applications, showing how EMUSES might integrate with neuroimaging analysis pipelines for predictive modeling tasks.

## 📋 **Basic Example Workflows**

This guide shows a few basic examples of how EMUSES might be used for predictive modeling with neuroimaging data. These are AI-generated conceptual examples to illustrate potential research directions.

### **Available Examples**
- [🧠 **Structural MRI**](#structural-mri-workflows) - Cortical thickness prediction example
- [🌊 **Functional Connectivity**](#basic-functional-connectivity-example) - Connectivity-based prediction example  
- [📊 **Basic Model Comparison**](#cross-study-comparison) - Comparing different approaches

---

<details markdown="1">
<summary>🧠 **Data Modality Workflows** - MRI, fMRI, DTI, and multi-modal analysis patterns</summary>

*Comprehensive workflows organized by neuroimaging data type and acquisition method*

## 🧠 **Structural MRI Workflows**

### **Cortical Thickness Analysis**

**Research Question**: How does cortical thickness relate to cognitive performance?

#### **Data Preparation**
```bash
# Assuming FreeSurfer processed data (recon-all completed)

> **⚠️ Prerequisites**: This workflow assumes you have:
> - FreeSurfer installed and subjects processed with recon-all
> - Custom data extraction scripts (examples shown, not provided)
> - Cognitive/behavioral data in compatible format

# Extract cortical thickness using FreeSurfer
aparcstats2table --subjects sub-001 sub-002 sub-003 \
  --hemi lh \
  --meas thickness \
  --parc aparc \
  --tablefile lh_thickness.txt

aparcstats2table --subjects sub-001 sub-002 sub-003 \
  --hemi rh \
  --meas thickness \
  --parc aparc \
  --tablefile rh_thickness.txt

# Combine hemispheres and format for EMUSES (user implementation)
# python combine_thickness_data.py \
#   --lh_file lh_thickness.txt \
#   --rh_file rh_thickness.txt \
#   --output cortical_thickness_features.csv
```

#### **EMUSES Predictive Modeling**
```bash
# Build predictive model from cortical thickness to cognitive scores
emuses full cortical_thickness_analysis/ \
  cortical_thickness_features.csv \
  --scores cognitive_scores.csv

# Apply trained model to new data
emuses inference cortical_thickness_analysis/ \
  new_subject_thickness.csv \
  --output predictions.csv
```

> **Note**: EMUSES creates predictive models that can predict cognitive scores from brain features. The analysis includes UMAP dimensionality reduction and various machine learning algorithms to find the best brain-behavior relationships.

### **Volumetric Analysis Workflow**

**Research Question**: Brain volume changes in neurodegenerative disease

```bash
# Extract volumetric features from T1-weighted images
python extract_volumes.py \
  --input_dir processed_t1/ \
  --atlas AAL \
  --output volumetric_features.csv

# Disease classification analysis
emuses full volume_disease_analysis/ \
  --optim_dict optim_dict_range \
  volumetric_features.csv \
  --scores disease_labels.csv \ \
# Validate on independent cohort
emuses inference volume_disease_analysis/ \
  validation_cohort_volumes.csv \
  --validate \
  --output validation_results.csv
```

---

## 🌊 **Basic Functional Connectivity Example**

### **Resting-State Connectivity Prediction**

**Potential Research Question**: Can functional connectivity patterns predict cognitive scores?

#### **Data Preparation Concept**
```python
# Example: Extract connectivity features (requires nilearn implementation)
# This is a conceptual example - actual implementation varies by study

from nilearn.connectome import ConnectivityMeasure
import numpy as np

# Assuming you have extracted time series from ROIs
# connectivity_measure = ConnectivityMeasure(kind='correlation')
# connectivity_matrices = connectivity_measure.fit_transform(time_series_list)
# 
# # Convert to feature matrix for EMUSES
# # Extract upper triangle of correlation matrices
# features = []
# for matrix in connectivity_matrices:
#     upper_tri = matrix[np.triu_indices_from(matrix, k=1)]
#     features.append(upper_tri)
# 
# # Save as CSV for EMUSES
# pd.DataFrame(features).to_csv('connectivity_features.csv', index=False)
```

#### **EMUSES Predictive Analysis**
```bash
# Build predictive model from connectivity to cognitive measures
emuses full connectivity_analysis/ \
  connectivity_features.csv \
  --scores cognitive_scores.csv

# Apply model to new subjects
emuses inference connectivity_analysis/ \
  new_connectivity_data.csv \
  --output connectivity_predictions.csv
```

---

## 🔬 **Cross-Study Comparison**

### **Basic Model Comparison**

**Potential Research Question**: Comparing different EMUSES configurations on the same dataset

```bash
# Train models with different optimization approaches
emuses full model_approach_a/ \
  brain_features.csv \
  --scores behavioral_scores.csv \
  --optim_dict optim_dict_default

emuses full model_approach_b/ \
  brain_features.csv \
  --scores behavioral_scores.csv \
  --optim_dict optim_dict_range

# Compare model performance
emuses compare model_approach_a/ \
            model_approach_b/
```

> **Note**: This shows how to compare different EMUSES optimization configurations on the same dataset. The `compare` command will show differences in model performance and configuration.

---

## 🔗 **Related Documentation**

- **[CLI Reference](CLI_REFERENCE.md)** - Complete command-line interface documentation
- **[User Guide](USER_GUIDE.md)** - Comprehensive usage guide with learning paths
- **[Quick Start Guide](QUICK_START.md)** - 5-minute tutorial for immediate results

---

*This guide provides AI-generated conceptual examples of potential EMUSES research applications. These workflows illustrate possible integration patterns but require validation and custom implementation for actual research use.*