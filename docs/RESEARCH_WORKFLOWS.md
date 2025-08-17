# 🔬 EMUSES Research Workflows Guide

**Specialized scientific use case patterns for research with EMUSES**

This guide provides detailed workflows for specific types of scientific research, from connectivity analysis to clinical prediction, with real-world neuroimaging examples and best practices for reproducible science.

## 📋 **Quick Navigation by Research Type**

### **By Data Modality**
- [🧠 **Structural MRI**](#structural-mri-workflows) - Morphometry, cortical thickness, volumetric analysis
- [🌊 **Functional MRI**](#functional-mri-workflows) - Task activation, resting-state connectivity
- [⚡ **DTI/DWI**](#dti-dwi-workflows) - White matter tractography and connectivity
- [🔗 **Multi-Modal**](#multi-modal-workflows) - Combined structural-functional analysis

### **By Research Question**
- [🎯 **Task-Based Studies**](#task-based-studies) - Motor, cognitive, language tasks
- [🔄 **Connectivity Analysis**](#connectivity-analysis) - Network connectivity patterns
- [🏥 **Clinical Prediction**](#clinical-prediction) - Disease classification, outcome prediction
- [👥 **Population Studies**](#population-studies) - Developmental, aging, group differences
- [🧬 **Biomarker Discovery**](#biomarker-discovery) - Diagnostic and prognostic markers

### **By Analysis Approach**
- [📊 **Exploratory Analysis**](#exploratory-analysis) - Hypothesis generation, pattern discovery
- [🧪 **Hypothesis Testing**](#hypothesis-testing) - Confirmatory analysis, replication
- [📈 **Longitudinal Studies**](#longitudinal-studies) - Change over time, trajectories
- [🔬 **Meta-Analysis**](#meta-analysis) - Cross-study synthesis, model comparison

---

## 🧠 **Structural MRI Workflows**

### **Cortical Thickness Analysis**

**Research Question**: How does cortical thickness relate to cognitive performance?

#### **Data Preparation**
```bash
# Assuming FreeSurfer processed data

> **📝 Note**: This document has been updated to reflect the actual EMUSES CLI interface. 
> EMUSES uses preset optimization configurations (`--optim_dict`) rather than direct parameter exposure.
> For detailed parameter information, see the [CLI Reference](CLI_REFERENCE.md).


# Extract cortical thickness measures per region
python extract_cortical_thickness.py \
  --freesurfer_dir subjects/ \
  --parcellation desikan \
  --output cortical_thickness_features.csv

# Prepare cognitive scores
python prepare_cognitive_data.py \
  --input raw_cognitive_data.xlsx \
  --output cognitive_scores.csv \
  --standardize
```

#### **EMUSES Analysis**
```bash
# Full pipeline analysis
emuses full cortical_thickness_analysis/ \
  cortical_thickness_features.csv \
  --scores cognitive_scores.csv \ \
# Generate comprehensive documentation
emuses reproduce cortical_thickness_analysis/models/trained_model.pkl \
  --include_environment \
  --output cortical_thickness_methods.md

emuses cite cortical_thickness_analysis/models/trained_model.pkl \
  --style nature \
  --include_data \
  --output cortical_thickness_refs.txt
```

#### **Result Interpretation**
```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Load results
embeddings = np.load('cortical_thickness_analysis/umap_embeddings.npy')
heatmap_data = np.load('cortical_thickness_analysis/heatmap_data.npy')

# Visualize cortical thickness patterns
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

# UMAP embedding
ax1.scatter(embeddings[:, 0], embeddings[:, 1], alpha=0.6)
ax1.set_title('Cortical Thickness Patterns')
ax1.set_xlabel('UMAP 1')
ax1.set_ylabel('UMAP 2')

# Correlation heatmap
im = ax2.imshow(heatmap_data, cmap='RdBu_r', aspect='auto')
ax2.set_title('Thickness-Cognition Correlations')
plt.colorbar(im, ax=ax2)

plt.tight_layout()
plt.savefig('cortical_thickness_results.png', dpi=300)
```

#### **Clinical Translation**
```bash
# Apply model to new clinical cohort
emuses inference cortical_thickness_analysis/models/trained_model.pkl \
  new_patient_data.csv \
  --output clinical_predictions.csv \
  --validation_mode

# Generate clinical report
python generate_clinical_report.py \
  --predictions clinical_predictions.csv \
  --model_info cortical_thickness_analysis/models/model_manifest.json \
  --output clinical_report.html
```

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
emuses inference volume_disease_analysis/models/trained_model.pkl \
  validation_cohort_volumes.csv \
  --validation_mode \
  --output validation_results.json
```

---

## 🌊 **Functional MRI Workflows**

### **Task-Based fMRI Analysis**

**Research Question**: Motor cortex activation patterns predict motor performance

#### **GLM-Based Feature Extraction**
```bash
# First-level GLM analysis (using FSL/SPM)
# Extract activation maps for each subject
python extract_task_activation.py \
  --fmri_dir motor_task_fmri/ \
  --design_matrix motor_task_design.mat \
  --contrast motor_vs_rest \
  --output motor_activation_features.csv
```

#### **EMUSES Analysis Pipeline**
```bash
# Analyze activation-behavior relationships
emuses full motor_task_analysis/ \
  motor_activation_features.csv \
  --scores motor_performance_scores.csv \ \ \
# Generate detailed model information
emuses info motor_task_analysis/models/trained_model.pkl \
  --detailed \
  --performance \
  --provenance \
  --format json > motor_model_info.json
```

#### **Advanced Analysis Configuration**
```json
// task_fmri_config.json
{
  "analysis": {
    "random_seed": 42,
    "cross_validation": {
      "folds": 10,
      "stratified": false
    }
  },
  "umap": {
    "n_neighbors": 20,
    "min_dist": 0.08,
    "n_components": 2,
    "metric": "correlation"
  },
  "heatmap": {
    "grid_resolution": 150,
    "interpolation": "cubic",
    "significance_threshold": 0.001
  },
  "modeling": {
    "algorithms": ["ridge", "lasso"],
    "hyperparameter_tuning": true
  }
}
```

#### **Publication-Ready Analysis**
```bash
# Generate publication materials
emuses reproduce motor_task_analysis/models/trained_model.pkl \
  --include_environment \
  --include_data_prep \
  --format markdown \
  --output motor_task_methods_section.md

# Create citation
emuses cite motor_task_analysis/models/trained_model.pkl \
  --style apa \
  --include_data \
  --include_software \
  --output motor_task_citations.txt

# Compare with alternative approaches
emuses compare motor_task_analysis/models/trained_model.pkl \
            alternative_method/models/trained_model.pkl \
  --detailed \
  --output method_comparison.md
```

### **Resting-State Connectivity Analysis**

**Research Question**: Default mode network connectivity predicts cognitive flexibility

#### **Connectivity Matrix Preparation**
```python
# connectivity_extraction.py
import numpy as np
from nilearn import datasets, connectome

# Load atlas
atlas = datasets.fetch_atlas_harvard_oxford('cort-maxprob-thr25-2mm')

# Extract time series and compute connectivity
def extract_connectivity(fmri_file, atlas_img):
    from nilearn.input_data import NiftiLabelsMasker
    from sklearn.covariance import LedoitWolf
    
    # Extract time series
    masker = NiftiLabelsMasker(
        labels_img=atlas_img, 
        standardize=True,
        memory='nilearn_cache'
    )
    time_series = masker.fit_transform(fmri_file)
    
    # Compute correlation matrix
    estimator = connectome.ConnectivityMeasure(
        kind='correlation',
        cov_estimator=LedoitWolf()
    )
    correlation_matrix = estimator.fit_transform([time_series])[0]
    
    # Extract upper triangle (avoiding diagonal)
    mask = np.triu(np.ones_like(correlation_matrix, dtype=bool), k=1)
    connectivity_features = correlation_matrix[mask]
    
    return connectivity_features

# Process all subjects
connectivity_data = []
for subject_file in fmri_files:
    features = extract_connectivity(subject_file, atlas.maps)
    connectivity_data.append(features)

# Save connectivity matrix
connectivity_df = pd.DataFrame(connectivity_data)
connectivity_df.to_csv('resting_state_connectivity.csv', index=False)
```

#### **EMUSES Connectivity Analysis**
```bash
# Analyze connectivity-cognition relationships
emuses full resting_state_analysis/ \
  resting_state_connectivity.csv \
  --scores cognitive_flexibility_scores.csv \ \
# Detailed analysis of results
emuses info resting_state_analysis/models/trained_model.pkl \
  --performance \
  --detailed

# Generate network visualization
python visualize_connectivity_results.py \
  --embeddings resting_state_analysis/umap_embeddings.npy \
  --heatmap resting_state_analysis/heatmap_data.npy \
  --atlas harvard_oxford \
  --output network_visualization.html
```

#### **Network-Specific Analysis**
```bash
# Extract default mode network specifically
python extract_dmn_connectivity.py \
  --connectivity_file resting_state_connectivity.csv \
  --network_definition dmn_regions.txt \
  --output dmn_connectivity.csv

# Focused DMN analysis
emuses full dmn_specific_analysis/ \
  dmn_connectivity.csv \
  --scores cognitive_flexibility_scores.csv \ \
# Compare full brain vs DMN-specific models
emuses compare resting_state_analysis/models/trained_model.pkl \
            dmn_specific_analysis/models/trained_model.pkl \
  --detailed \
  --output brain_vs_dmn_comparison.md
```

---

## ⚡ **DTI/DWI Workflows**

### **White Matter Connectivity Analysis**

**Research Question**: White matter integrity and reading performance

#### **Tractography-Based Analysis**
```bash
# Extract white matter connectivity (using MRtrix3)
# Generate connectivity matrices from tractography
python extract_structural_connectivity.py \
  --tractography_dir dwi_tractography/ \
  --parcellation freesurfer \
  --metric fa_weighted \
  --output structural_connectivity.csv

# Analyze white matter-reading relationships
emuses full white_matter_reading/ \
  structural_connectivity.csv \
  --scores reading_performance.csv \ \ \
```

#### **Tract-Specific Analysis**
```bash
# Extract specific white matter tracts
python extract_major_tracts.py \
  --dwi_dir processed_dwi/ \
  --tracts "arcuate,uncinate,cingulum" \
  --metrics "fa,md,rd,ad" \
  --output tract_metrics.csv

# Reading-specific tract analysis
emuses full reading_tracts_analysis/ \
  tract_metrics.csv \
  --scores reading_scores.csv \ \
# Generate tract visualization
python visualize_tract_results.py \
  --results reading_tracts_analysis/ \
  --tract_atlas white_matter_atlas.nii.gz \
  --output tract_visualization.png
```

#### **Clinical Application**
```bash
# Apply to dyslexia classification
emuses inference reading_tracts_analysis/models/trained_model.pkl \
  dyslexia_cohort_tracts.csv \
  --output dyslexia_predictions.csv \
  --validation_mode

# Generate clinical report
python generate_reading_report.py \
  --predictions dyslexia_predictions.csv \
  --model_path reading_tracts_analysis/ \
  --output dyslexia_assessment_report.pdf
```

---

## 🔗 **Multi-Modal Workflows**

### **Structure-Function Integration**

**Research Question**: How do structural and functional brain networks relate to cognition?

#### **Multi-Modal Data Integration**
```python
# multimodal_integration.py
import pandas as pd
import numpy as np

# Load different modalities
structural_data = pd.read_csv('cortical_thickness_features.csv')
functional_data = pd.read_csv('resting_state_connectivity.csv')
dwi_data = pd.read_csv('white_matter_metrics.csv')

# Ensure same subjects across modalities
common_subjects = set(structural_data.index) & set(functional_data.index) & set(dwi_data.index)
print(f"Common subjects across modalities: {len(common_subjects)}")

# Combine modalities
multimodal_features = pd.concat([
    structural_data.loc[common_subjects].add_prefix('struct_'),
    functional_data.loc[common_subjects].add_prefix('func_'),
    dwi_data.loc[common_subjects].add_prefix('dwi_')
], axis=1)

# Save integrated dataset
multimodal_features.to_csv('multimodal_features.csv')
```

#### **Integrated Analysis**
```bash
# Multi-modal analysis
emuses full multimodal_cognition_analysis/ \
  multimodal_features.csv \
  --scores comprehensive_cognitive_battery.csv \ \ \
# Compare with individual modalities
emuses compare structural_only_analysis/models/trained_model.pkl \
            multimodal_cognition_analysis/models/trained_model.pkl \
  --detailed \
  --output modality_comparison.md
```

#### **Advanced Multi-Modal Configuration**
```json
// multimodal_config.json
{
  "analysis": {
    "feature_selection": {
      "enabled": true,
      "method": "variance_threshold",
      "threshold": 0.01
    },
    "preprocessing": {
      "scaling": "standard",
      "feature_groups": {
        "structural": {"prefix": "struct_", "weight": 1.0},
        "functional": {"prefix": "func_", "weight": 1.0}, 
        "diffusion": {"prefix": "dwi_", "weight": 1.0}
      }
    }
  },
  "umap": {
    "n_neighbors": 25,
    "min_dist": 0.05,
    "metric": "euclidean",
    "n_components": 2
  },
  "modeling": {
    "algorithms": ["ridge", "elastic_net"],
    "cross_validation": {
      "folds": 5,
      "stratified": false
    }
  }
}
```

---

## 🎯 **Task-Based Studies**

### **Working Memory Task Analysis**

**Research Question**: N-back task activation patterns predict working memory capacity

#### **Task Design and Analysis**
```bash
# Extract n-back activation patterns
python extract_nback_activation.py \
  --fmri_dir nback_task_fmri/ \
  --contrast "2back_vs_0back" \
  --roi_atlas brodmann \
  --output nback_activation_features.csv

# Working memory capacity analysis
emuses full working_memory_analysis/ \
  nback_activation_features.csv \
  --scores working_memory_capacity.csv \ \
```

#### **Load-Dependent Analysis**
```bash
# Analyze load-dependent activation
python extract_load_effects.py \
  --fmri_dir nback_task_fmri/ \
  --contrasts "1back,2back,3back" \
  --output load_dependent_activation.csv

# Load effects analysis
emuses full load_effects_analysis/ \
  load_dependent_activation.csv \
  --scores working_memory_capacity.csv \
# Compare load conditions
emuses compare working_memory_analysis/models/trained_model.pkl \
            load_effects_analysis/models/trained_model.pkl \
  --output load_comparison.md
```

### **Language Task Analysis**

**Research Question**: Sentence comprehension networks and reading ability

```bash
# Extract language activation
python extract_language_activation.py \
  --fmri_dir sentence_comprehension_fmri/ \
  --contrast "sentences_vs_wordlists" \
  --language_rois left_hemisphere_language \
  --output language_activation_features.csv

# Reading ability analysis
emuses full language_reading_analysis/ \
  language_activation_features.csv \
  --scores reading_comprehension_scores.csv \ \
# Hemispheric lateralization analysis
python analyze_lateralization.py \
  --results language_reading_analysis/ \
  --atlas language_parcellation \
  --output lateralization_report.html
```

---

## 🔄 **Connectivity Analysis**

### **Dynamic Functional Connectivity**

**Research Question**: Time-varying connectivity patterns and cognitive flexibility

#### **Dynamic Connectivity Extraction**
```python
# dynamic_connectivity.py
from nilearn.connectome import ConnectivityMeasure
import numpy as np

def extract_dynamic_connectivity(time_series, window_size=50, step=10):
    """Extract dynamic connectivity using sliding window"""
    
    n_timepoints = time_series.shape[0]
    connectivity_matrices = []
    
    for start in range(0, n_timepoints - window_size, step):
        end = start + window_size
        window_ts = time_series[start:end, :]
        
        # Compute correlation for this window
        conn_measure = ConnectivityMeasure(kind='correlation')
        conn_matrix = conn_measure.fit_transform([window_ts])[0]
        
        # Extract upper triangle
        mask = np.triu(np.ones_like(conn_matrix, dtype=bool), k=1)
        connectivity_matrices.append(conn_matrix[mask])
    
    return np.array(connectivity_matrices)

# Process all subjects
dynamic_conn_data = []
for subject_file in fmri_files:
    time_series = extract_time_series(subject_file)
    dynamic_conn = extract_dynamic_connectivity(time_series)
    
    # Summarize dynamic connectivity (e.g., variance across windows)
    connectivity_variance = np.var(dynamic_conn, axis=0)
    dynamic_conn_data.append(connectivity_variance)

# Save dynamic connectivity features
dynamic_df = pd.DataFrame(dynamic_conn_data)
dynamic_df.to_csv('dynamic_connectivity_features.csv', index=False)
```

#### **Dynamic Connectivity Analysis**
```bash
# Analyze dynamic connectivity patterns
emuses full dynamic_connectivity_analysis/ \
  dynamic_connectivity_features.csv \
  --scores cognitive_flexibility_scores.csv \ \ \
# Compare with static connectivity
emuses compare static_connectivity_analysis/models/trained_model.pkl \
            dynamic_connectivity_analysis/models/trained_model.pkl \
  --detailed \
  --output static_vs_dynamic_comparison.md
```

### **Graph Theory Analysis**

**Research Question**: Network topology measures predict cognitive performance

```python
# graph_metrics.py
import networkx as nx
import numpy as np
import pandas as pd

def compute_graph_metrics(connectivity_matrix, threshold=0.1):
    """Compute graph theory metrics from connectivity matrix"""
    
    # Threshold and binarize
    adj_matrix = (np.abs(connectivity_matrix) > threshold).astype(int)
    
    # Create graph
    G = nx.from_numpy_array(adj_matrix)
    
    # Compute metrics
    metrics = {
        'clustering_coefficient': nx.average_clustering(G),
        'path_length': nx.average_shortest_path_length(G) if nx.is_connected(G) else np.inf,
        'global_efficiency': nx.global_efficiency(G),
        'modularity': nx.community.modularity(G, nx.community.greedy_modularity_communities(G)),
        'small_worldness': compute_small_worldness(G),
        'degree_centrality': np.mean(list(nx.degree_centrality(G).values())),
        'betweenness_centrality': np.mean(list(nx.betweenness_centrality(G).values()))
    }
    
    return metrics

# Process connectivity matrices
graph_metrics_data = []
for conn_file in connectivity_files:
    conn_matrix = np.load(conn_file)
    metrics = compute_graph_metrics(conn_matrix)
    graph_metrics_data.append(metrics)

# Save graph metrics
graph_df = pd.DataFrame(graph_metrics_data)
graph_df.to_csv('graph_theory_metrics.csv', index=False)
```

```bash
# Graph theory analysis
emuses full graph_theory_analysis/ \
  graph_theory_metrics.csv \
  --scores cognitive_composite_scores.csv \ \
# Network topology visualization
python visualize_graph_results.py \
  --results graph_theory_analysis/ \
  --connectivity_matrices connectivity_data/ \
  --output network_topology_visualization.html
```

---

## 🏥 **Clinical Prediction**

### **Disease Classification**

**Research Question**: Alzheimer's disease classification using multimodal imaging

#### **Clinical Data Preparation**
```python
# clinical_data_prep.py
import pandas as pd
from sklearn.preprocessing import StandardScaler

# Load clinical and demographic data
demographics = pd.read_csv('subject_demographics.csv')
cognitive_scores = pd.read_csv('cognitive_assessments.csv')
imaging_features = pd.read_csv('multimodal_imaging_features.csv')

# Merge datasets
clinical_data = demographics.merge(cognitive_scores, on='subject_id')
clinical_data = clinical_data.merge(imaging_features, on='subject_id')

# Create diagnosis labels
diagnosis_mapping = {
    'CN': 0,  # Cognitively Normal
    'MCI': 1, # Mild Cognitive Impairment
    'AD': 2   # Alzheimer's Disease
}
clinical_data['diagnosis_numeric'] = clinical_data['diagnosis'].map(diagnosis_mapping)

# Prepare features and labels
features = clinical_data.drop(['subject_id', 'diagnosis', 'diagnosis_numeric'], axis=1)
labels = clinical_data[['subject_id', 'diagnosis_numeric']]

# Save prepared data
features.to_csv('alzheimer_features.csv', index=False)
labels.to_csv('alzheimer_labels.csv', index=False)
```

#### **Classification Analysis**
```bash
# Alzheimer's classification
emuses full alzheimer_classification/ \
  alzheimer_features.csv \
  --scores alzheimer_labels.csv \ \ \
# Model validation on independent cohort
emuses inference alzheimer_classification/models/trained_model.pkl \
  validation_cohort_features.csv \
  --validation_mode \
  --output validation_predictions.csv

# Generate clinical validation report
python generate_clinical_validation.py \
  --predictions validation_predictions.csv \
  --true_labels validation_labels.csv \
  --output clinical_validation_report.html
```

#### **Clinical Configuration**
```json
// clinical_classification_config.json
{
  "analysis": {
    "random_seed": 42,
    "stratified_sampling": true,
    "class_balancing": "smote"
  },
  "cross_validation": {
    "folds": 10,
    "stratified": true,
    "scoring": ["accuracy", "f1_weighted", "roc_auc"]
  },
  "modeling": {
    "algorithms": ["logistic", "random_forest", "svm"],
    "hyperparameter_tuning": {
      "method": "grid_search",
      "cv_folds": 3
    }
  },
  "evaluation": {
    "metrics": ["confusion_matrix", "classification_report", "roc_curve"],
    "save_probabilities": true
  }
}
```

### **Outcome Prediction**

**Research Question**: Predicting treatment response in depression

```bash
# Treatment response prediction
emuses full depression_treatment_prediction/ \
  baseline_brain_features.csv \
  --scores treatment_response_scores.csv \ \ \
# Longitudinal analysis
python analyze_treatment_trajectory.py \
  --baseline_results depression_treatment_prediction/ \
  --followup_data followup_assessments.csv \
  --output treatment_trajectory_analysis.html

# Clinical decision support
python generate_treatment_recommendations.py \
  --model depression_treatment_prediction/models/trained_model.pkl \
  --patient_data new_patient_features.csv \
  --output treatment_recommendation.pdf
```

---

## 👥 **Population Studies**

### **Developmental Analysis**

**Research Question**: Brain-behavior development across adolescence

#### **Age-Related Analysis**
```bash
# Cross-sectional developmental analysis
emuses full adolescent_development/ \
  adolescent_brain_features.csv \
  --scores adolescent_cognitive_scores.csv \ \ \
# Age-stratified analysis
python stratify_by_age.py \
  --data adolescent_brain_features.csv \
  --scores adolescent_cognitive_scores.csv \
  --age_bins "12-14,15-17,18-20" \
  --output age_stratified_data/

# Analyze each age group
for age_group in "12-14" "15-17" "18-20"; do
  emuses full "development_${age_group}/" \
    "age_stratified_data/${age_group}_features.csv" \
    --scores "age_stratified_data/${age_group}_scores.csv" \
done

# Compare developmental patterns
python compare_developmental_patterns.py \
  --results_dirs "development_*/" \
  --output developmental_comparison_report.html
```

#### **Longitudinal Trajectory Analysis**
```bash
# Longitudinal developmental data
python prepare_longitudinal_data.py \
  --timepoints "baseline,1year,2year" \
  --features longitudinal_brain_data.csv \
  --scores longitudinal_cognitive_data.csv \
  --output longitudinal_features.csv

# Trajectory analysis
emuses full longitudinal_development/ \
  longitudinal_features.csv \
  --scores longitudinal_change_scores.csv \
# Predict developmental trajectories
emuses inference longitudinal_development/models/trained_model.pkl \
  new_baseline_data.csv \
  --output predicted_trajectories.csv
```

### **Aging Studies**

**Research Question**: Healthy aging patterns in brain networks

```bash
# Healthy aging analysis
emuses full healthy_aging_analysis/ \
  aging_brain_features.csv \
  --scores aging_cognitive_scores.csv \ \ \
# Age group comparisons
python compare_age_groups.py \
  --young_data young_adults_features.csv \
  --older_data older_adults_features.csv \
  --output age_group_comparison.html

# Successful aging prediction
python predict_successful_aging.py \
  --baseline_data baseline_features.csv \
  --outcome_data successful_aging_outcomes.csv \
  --model_results healthy_aging_analysis/ \
  --output successful_aging_predictions.csv
```

---

## 🧬 **Biomarker Discovery**

### **Diagnostic Biomarkers**

**Research Question**: Brain imaging biomarkers for early Parkinson's disease

#### **Feature Discovery Pipeline**
```bash
# Comprehensive feature extraction
python extract_comprehensive_features.py \
  --structural_data pd_structural_features.csv \
  --functional_data pd_functional_features.csv \
  --dti_data pd_dti_features.csv \
  --output pd_comprehensive_features.csv

# Biomarker discovery analysis
emuses full parkinsons_biomarkers/ \
  pd_comprehensive_features.csv \
  --scores pd_diagnosis_labels.csv \ \ \
# Feature importance analysis
python analyze_feature_importance.py \
  --results parkinsons_biomarkers/ \
  --feature_names pd_feature_names.txt \
  --output biomarker_importance_report.html
```

#### **Biomarker Validation**
```bash
# Independent cohort validation
emuses inference parkinsons_biomarkers/models/trained_model.pkl \
  independent_pd_cohort.csv \
  --validation_mode \
  --output biomarker_validation.csv

# Multi-site validation
python multi_site_validation.py \
  --model parkinsons_biomarkers/models/trained_model.pkl \
  --site_data "site1.csv,site2.csv,site3.csv" \
  --output multi_site_validation_report.html

# Biomarker generalizability
emuses compare parkinsons_biomarkers/models/trained_model.pkl \
            external_validation_model/models/trained_model.pkl \
  --benchmark_data external_test_set.csv \
  --output biomarker_generalizability.md
```

### **Prognostic Biomarkers**

**Research Question**: Predicting cognitive decline in mild cognitive impairment

```bash
# Longitudinal progression analysis
python prepare_progression_data.py \
  --baseline_features mci_baseline_features.csv \
  --followup_outcomes mci_progression_outcomes.csv \
  --followup_period "24_months" \
  --output mci_progression_data.csv

# Progression prediction
emuses full mci_progression_prediction/ \
  mci_progression_data.csv \
  --scores mci_progression_labels.csv \
# Time-to-event analysis
python survival_analysis.py \
  --baseline_features mci_baseline_features.csv \
  --time_to_event mci_conversion_times.csv \
  --model_results mci_progression_prediction/ \
  --output survival_analysis_report.html
```

---

## 📊 **Exploratory Analysis**

### **Hypothesis Generation**

**Research Question**: Discovering novel brain-behavior relationships

#### **Data-Driven Discovery**
```bash
# Exploratory analysis with minimal assumptions
emuses full exploratory_discovery/ \
  comprehensive_brain_features.csv \
  --scores comprehensive_behavioral_battery.csv \ \ \
# Pattern discovery
python discover_patterns.py \
  --embeddings exploratory_discovery/umap_embeddings.npy \
  --heatmap exploratory_discovery/heatmap_data.npy \
  --feature_names brain_feature_names.txt \
  --output discovered_patterns.html

# Hypothesis generation
python generate_hypotheses.py \
  --patterns discovered_patterns.html \
  --literature_database neuroimaging_literature.db \
  --output research_hypotheses.md
```

#### **Clustering Analysis**
```python
# clustering_analysis.py
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics import silhouette_score
import numpy as np

# Load UMAP embeddings
embeddings = np.load('exploratory_discovery/umap_embeddings.npy')

# Try different clustering approaches
clustering_results = {}

# K-means clustering
for k in range(2, 11):
    kmeans = KMeans(n_clusters=k, random_state=42)
    labels = kmeans.fit_predict(embeddings)
    silhouette = silhouette_score(embeddings, labels)
    clustering_results[f'kmeans_{k}'] = {
        'labels': labels,
        'silhouette': silhouette
    }

# DBSCAN clustering
dbscan = DBSCAN(eps=0.5, min_samples=5)
dbscan_labels = dbscan.fit_predict(embeddings)
clustering_results['dbscan'] = {
    'labels': dbscan_labels,
    'n_clusters': len(set(dbscan_labels)) - (1 if -1 in dbscan_labels else 0)
}

# Visualize clustering results
import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 3, figsize=(15, 10))
axes = axes.ravel()

for i, (method, result) in enumerate(clustering_results.items()):
    if i < len(axes):
        ax = axes[i]
        scatter = ax.scatter(embeddings[:, 0], embeddings[:, 1], 
                           c=result['labels'], cmap='tab10', alpha=0.6)
        ax.set_title(f'{method}')
        ax.set_xlabel('UMAP 1')
        ax.set_ylabel('UMAP 2')

plt.tight_layout()
plt.savefig('clustering_analysis.png', dpi=300)
```

### **Quality Control and Outlier Detection**

```bash
# Quality control analysis
emuses umap qc_analysis/ raw_brain_features.csv \ \
# Outlier detection
python detect_outliers.py \
  --embeddings qc_analysis/umap_embeddings.npy \
  --original_data raw_brain_features.csv \
  --threshold 3.0 \
  --output outlier_report.html

# Clean dataset analysis
emuses full cleaned_analysis/ cleaned_brain_features.csv \
  --scores behavioral_scores.csv \
# Compare raw vs cleaned results
emuses compare raw_analysis/models/trained_model.pkl \
            cleaned_analysis/models/trained_model.pkl \
  --output quality_control_comparison.md
```

---

## 🧪 **Hypothesis Testing**

### **Confirmatory Analysis**

**Research Question**: Replicating published brain-behavior relationships

#### **Replication Study Design**
```bash
# Load published model for replication
emuses models install published_study_model.zip \
  --name "original_study_model"

# Apply to replication dataset
emuses inference original_study_model \
  replication_dataset_features.csv \
  --validation_mode \
  --output replication_results.csv

# Train model on replication data
emuses full replication_analysis/ \
  replication_dataset_features.csv \
  --scores replication_behavioral_scores.csv \
# Compare original and replication results
emuses compare original_study_model \
            replication_analysis/models/trained_model.pkl \
  --detailed \
  --output replication_comparison.md
```

#### **Statistical Validation**
```python
# replication_validation.py
import pandas as pd
import numpy as np
from scipy import stats

# Load results
original_results = pd.read_csv('original_study_results.csv')
replication_results = pd.read_csv('replication_results.csv')

# Effect size comparison
original_r2 = original_results['r_squared'].iloc[0]
replication_r2 = replication_results['r_squared'].iloc[0]

# Statistical tests
effect_size_diff = abs(original_r2 - replication_r2)
replication_success = effect_size_diff < 0.1  # Within 10% of original

# Correlation between predicted and actual
correlation, p_value = stats.pearsonr(
    replication_results['predicted'],
    replication_results['actual']
)

print(f"Original R²: {original_r2:.3f}")
print(f"Replication R²: {replication_r2:.3f}")
print(f"Difference: {effect_size_diff:.3f}")
print(f"Replication Success: {replication_success}")
print(f"Correlation: {correlation:.3f} (p={p_value:.3f})")
```

### **Multi-Site Validation**

**Research Question**: Cross-site generalizability of brain-behavior models

```bash
# Train model on Site 1 data
emuses full site1_model/ \
  site1_features.csv \
  --scores site1_scores.csv \
# Test on other sites
for site in "site2" "site3" "site4"; do
  emuses inference site1_model/models/trained_model.pkl \
    "${site}_features.csv" \
    --validation_mode \
    --output "${site}_predictions.csv"
done

# Multi-site validation analysis
python multi_site_validation_analysis.py \
  --training_site site1 \
  --test_sites "site2,site3,site4" \
  --output multi_site_validation_report.html

# Site-specific model comparison
python compare_site_models.py \
  --models "site1_model,site2_model,site3_model,site4_model" \
  --cross_validation_results site_cv_results/ \
  --output site_comparison.html
```

---

## 📈 **Longitudinal Studies**

### **Change Detection**

**Research Question**: Brain changes associated with cognitive training

#### **Longitudinal Data Preparation**
```python
# longitudinal_prep.py
import pandas as pd

# Load timepoint data
baseline = pd.read_csv('baseline_features.csv')
post_training = pd.read_csv('post_training_features.csv')
followup = pd.read_csv('followup_features.csv')

# Calculate change scores
change_baseline_to_post = post_training.set_index('subject_id') - baseline.set_index('subject_id')
change_post_to_followup = followup.set_index('subject_id') - post_training.set_index('subject_id')

# Add prefix to distinguish change types
change_baseline_to_post = change_baseline_to_post.add_prefix('change_train_')
change_post_to_followup = change_post_to_followup.add_prefix('change_maintain_')

# Combine change scores
longitudinal_changes = pd.concat([
    change_baseline_to_post,
    change_post_to_followup
], axis=1)

longitudinal_changes.to_csv('longitudinal_change_features.csv')
```

#### **Change Analysis**
```bash
# Analyze training-related changes
emuses full cognitive_training_changes/ \
  longitudinal_change_features.csv \
  --scores cognitive_improvement_scores.csv \
# Predict maintenance of gains
emuses inference cognitive_training_changes/models/trained_model.pkl \
  new_trainees_changes.csv \
  --output predicted_maintenance.csv

# Visualize change patterns
python visualize_longitudinal_changes.py \
  --results cognitive_training_changes/ \
  --timepoints "baseline,post_training,followup" \
  --output longitudinal_visualization.html
```

### **Trajectory Modeling**

**Research Question**: Developmental trajectories of executive function

```bash
# Trajectory feature extraction
python extract_trajectory_features.py \
  --longitudinal_data executive_function_longitudinal.csv \
  --trajectory_method "polynomial_fit" \
  --degree 2 \
  --output trajectory_features.csv

# Trajectory analysis
emuses full executive_trajectories/ \
  trajectory_features.csv \
  --scores executive_function_outcomes.csv \
# Predict future development
python predict_developmental_trajectory.py \
  --model executive_trajectories/models/trained_model.pkl \
  --baseline_data new_subjects_baseline.csv \
  --prediction_timepoints "1year,2year,3year" \
  --output predicted_development.csv
```

---

## 🔬 **Meta-Analysis**

### **Cross-Study Model Comparison**

**Research Question**: Comparing working memory models across studies

#### **Model Collection and Standardization**
```bash
# Download community models
emuses models search "working memory" --workspace community > wm_models.json

# Install models for comparison
cat wm_models.json | jq -r '.models[].name' | while read model; do
  emuses models install "$model" --workspace meta_analysis
done

# Standardize feature formats
python standardize_model_features.py \
  --models_dir meta_analysis/ \
  --reference_atlas brodmann \
  --output standardized_features/
```

#### **Meta-Analysis Pipeline**
```bash
# Extract model information
emuses models list --workspace meta_analysis --format json > installed_models.json

# Compare all models on standard dataset
python meta_analysis_comparison.py \
  --models installed_models.json \
  --test_data standard_wm_dataset.csv \
  --output meta_analysis_results.csv

# Statistical meta-analysis
python statistical_meta_analysis.py \
  --comparison_results meta_analysis_results.csv \
  --study_characteristics study_info.csv \
  --output meta_analysis_report.html
```

#### **Publication Meta-Model**
```bash
# Create ensemble model from meta-analysis
python create_ensemble_model.py \
  --models_list meta_analysis_models.json \
  --weights meta_analysis_weights.csv \
  --output ensemble_working_memory_model/

# Validate ensemble model
emuses inference ensemble_working_memory_model/ \
  independent_validation_set.csv \
  --validation_mode \
  --output ensemble_validation.csv

# Publish meta-model
emuses models publish ensemble_working_memory_model/ \
  --workspace community \
  --visibility public \
  --description "Meta-analysis ensemble model for working memory prediction" \
  --tags "working_memory,meta_analysis,ensemble"
```

### **Effect Size Meta-Analysis**

**Research Question**: Effect sizes of brain-behavior relationships across studies

```python
# effect_size_meta_analysis.py
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

def compute_effect_sizes(studies_data):
    """Compute effect sizes across studies"""
    
    effect_sizes = []
    for study in studies_data:
        # Load study results
        study_info = emuses_info(study['model_path'])
        
        r_squared = study_info['performance']['r_squared']
        n_subjects = study_info['data']['n_subjects']
        
        # Convert R² to Cohen's f²
        f_squared = r_squared / (1 - r_squared)
        
        # Compute confidence interval
        se = np.sqrt((4 * f_squared) / n_subjects)
        ci_lower = f_squared - 1.96 * se
        ci_upper = f_squared + 1.96 * se
        
        effect_sizes.append({
            'study': study['name'],
            'effect_size': f_squared,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'n_subjects': n_subjects,
            'r_squared': r_squared
        })
    
    return pd.DataFrame(effect_sizes)

def random_effects_meta_analysis(effect_sizes_df):
    """Perform random effects meta-analysis"""
    
    # Calculate weights
    effect_sizes_df['weight'] = 1 / (effect_sizes_df['ci_upper'] - effect_sizes_df['ci_lower'])**2
    
    # Weighted mean effect size
    weighted_mean = np.average(effect_sizes_df['effect_size'], 
                              weights=effect_sizes_df['weight'])
    
    # Heterogeneity statistics
    Q = np.sum(effect_sizes_df['weight'] * 
               (effect_sizes_df['effect_size'] - weighted_mean)**2)
    
    return {
        'pooled_effect_size': weighted_mean,
        'heterogeneity_Q': Q,
        'n_studies': len(effect_sizes_df)
    }

# Load study data
studies = load_meta_analysis_studies('working_memory_studies.json')

# Compute effect sizes
effect_sizes = compute_effect_sizes(studies)

# Meta-analysis
meta_results = random_effects_meta_analysis(effect_sizes)

print(f"Pooled effect size: {meta_results['pooled_effect_size']:.3f}")
print(f"Heterogeneity Q: {meta_results['heterogeneity_Q']:.3f}")

# Forest plot
plt.figure(figsize=(10, 8))
y_pos = np.arange(len(effect_sizes))

plt.errorbar(effect_sizes['effect_size'], y_pos,
            xerr=[effect_sizes['effect_size'] - effect_sizes['ci_lower'],
                  effect_sizes['ci_upper'] - effect_sizes['effect_size']],
            fmt='o', capsize=5)

plt.axvline(meta_results['pooled_effect_size'], color='red', linestyle='--',
           label=f"Pooled Effect Size: {meta_results['pooled_effect_size']:.3f}")

plt.yticks(y_pos, effect_sizes['study'])
plt.xlabel('Effect Size (Cohen\'s f²)')
plt.title('Meta-Analysis: Brain-Behavior Effect Sizes')
plt.legend()
plt.tight_layout()
plt.savefig('meta_analysis_forest_plot.png', dpi=300)
```

---

## 📋 **Research Workflow Templates**

### **Standard Operating Procedures**

#### **Template 1: Task fMRI Analysis**
```bash
#!/bin/bash
# task_fmri_sop.sh - Standard Operating Procedure for Task fMRI Analysis

set -e  # Exit on error

# Configuration
TASK_NAME=$1
CONTRAST=$2
OUTPUT_DIR="task_fmri_${TASK_NAME}_$(date +%Y%m%d)"

echo "Starting Task fMRI Analysis: $TASK_NAME"
echo "Contrast: $CONTRAST"
echo "Output Directory: $OUTPUT_DIR"

# Step 1: Extract activation features
python extract_task_activation.py \
  --fmri_dir "fmri_data/${TASK_NAME}/" \
  --contrast "$CONTRAST" \
  --atlas "brodmann" \
  --output "${OUTPUT_DIR}/activation_features.csv"

# Step 2: Run EMUSES analysis
emuses full "$OUTPUT_DIR/" \
  "${OUTPUT_DIR}/activation_features.csv" \
  --scores "behavioral_data/${TASK_NAME}_scores.csv" \
# Step 3: Generate documentation
emuses reproduce "${OUTPUT_DIR}/models/trained_model.pkl" \
  --include_environment \
  --output "${OUTPUT_DIR}/methods_section.md"

emuses cite "${OUTPUT_DIR}/models/trained_model.pkl" \
  --style "nature" \
  --include_data \
  --output "${OUTPUT_DIR}/citations.txt"

# Step 4: Quality control
emuses verify "${OUTPUT_DIR}/models/trained_model.pkl" \
  --strict \
  --report "${OUTPUT_DIR}/qc_report.json"

echo "Task fMRI Analysis Complete: $OUTPUT_DIR"
```

#### **Template 2: Clinical Prediction Pipeline**
```bash
#!/bin/bash
# clinical_prediction_sop.sh - Clinical Prediction Standard Pipeline

STUDY_NAME=$1
DISEASE_TYPE=$2
OUTPUT_DIR="clinical_${DISEASE_TYPE}_$(date +%Y%m%d)"

# Data preparation
python prepare_clinical_data.py \
  --study_name "$STUDY_NAME" \
  --disease_type "$DISEASE_TYPE" \
  --output_features "${OUTPUT_DIR}/clinical_features.csv" \
  --output_labels "${OUTPUT_DIR}/clinical_labels.csv"

# Clinical analysis
emuses full "$OUTPUT_DIR/" \
  "${OUTPUT_DIR}/clinical_features.csv" \
  --scores "${OUTPUT_DIR}/clinical_labels.csv" \
# Cross-validation
python clinical_cross_validation.py \
  --model "${OUTPUT_DIR}/models/trained_model.pkl" \
  --features "${OUTPUT_DIR}/clinical_features.csv" \
  --labels "${OUTPUT_DIR}/clinical_labels.csv" \
  --output "${OUTPUT_DIR}/cv_results.json"

# Clinical report generation
python generate_clinical_report.py \
  --results "$OUTPUT_DIR/" \
  --study_info "study_metadata/${STUDY_NAME}.json" \
  --output "${OUTPUT_DIR}/clinical_report.html"
```

### **Reproducibility Checklist**

#### **Pre-Analysis Checklist**
```bash
# reproducibility_checklist.sh
echo "EMUSES Reproducibility Checklist"
echo "================================"

# 1. Version control
echo "1. Checking version control..."
git status
if [ $? -ne 0 ]; then
  echo "WARNING: Not in a git repository"
fi

# 2. Environment documentation
echo "2. Documenting environment..."
pip freeze > requirements.txt
python --version > python_version.txt
emuses --version > emuses_version.txt

# 3. Random seed setting
echo "3. Setting random seeds..."
export EMUSES_RANDOM_SEED=42
export PYTHONHASHSEED=42

# 4. Data integrity check
echo "4. Checking data integrity..."
python check_data_integrity.py --data_dir data/

# 5. Configuration backup
echo "5. Backing up configuration..."
cp config.json "config_backup_$(date +%Y%m%d_%H%M%S).json"

echo "Reproducibility checklist complete!"
```

#### **Post-Analysis Checklist**
```bash
# post_analysis_checklist.sh
ANALYSIS_DIR=$1

echo "Post-Analysis Reproducibility Checklist"
echo "======================================="

# 1. Model verification
echo "1. Verifying model integrity..."
emuses verify "${ANALYSIS_DIR}/models/trained_model.pkl" --strict

# 2. Reproduction guide generation
echo "2. Generating reproduction guide..."
emuses reproduce "${ANALYSIS_DIR}/models/trained_model.pkl" \
  --include_environment \
  --include_data_prep \
  --output "${ANALYSIS_DIR}/reproduction_guide.md"

# 3. Provenance documentation
echo "3. Documenting provenance..."
emuses trace "${ANALYSIS_DIR}/models/trained_model.pkl" \
  --include_data_lineage \
  --output "${ANALYSIS_DIR}/provenance.json"

# 4. Citation generation
echo "4. Generating citations..."
emuses cite "${ANALYSIS_DIR}/models/trained_model.pkl" \
  --style "bibtex" \
  --include_data \
  --include_software \
  --output "${ANALYSIS_DIR}/references.bib"

# 5. Results archival
echo "5. Archiving results..."
tar -czf "${ANALYSIS_DIR}_archive.tar.gz" "$ANALYSIS_DIR"

echo "Post-analysis checklist complete!"
```

---

## 🔗 **Related Documentation**

- **[CLI Reference](docs/CLI_REFERENCE.md)** - Complete command-line interface documentation
- **[API Reference](docs/API_REFERENCE.md)** - REST API documentation for integration
- **[User Guide](docs/USER_GUIDE.md)** - Comprehensive usage guide with learning paths
- **[Quick Start Guide](docs/QUICK_START.md)** - 5-minute tutorial for immediate results
- **[Admin Guide](docs/ADMIN_GUIDE.md)** - System administration and deployment
- **[Migration Guide](docs/MIGRATION_GUIDE.md)** - Version upgrade guidance

---

*This research workflows guide provides specialized patterns for scientific research with EMUSES, with extensive neuroimaging examples. Each workflow includes real-world examples, best practices, and reproducibility guidelines. For additional scientific use cases or custom workflow development, consult the User Guide or contribute to the community discussions.*