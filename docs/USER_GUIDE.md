# 📖 EMUSES Complete User Guide

**Comprehensive guide for scientific research with EMUSES - from first analysis to advanced research workflows**

This guide provides structured learning paths for researchers at all levels, complete workflow examples, and best practices for reproducible scientific research using EMUSES, with extensive neuroimaging examples.

## 🎯 **Quick Navigation**

### **By User Type**
- [🔬 **Individual Researchers**](#individual-researchers) - Personal analysis and method development
- [🏛️ **Research Labs**](#research-labs) - Team collaboration and model sharing  
- [🌍 **Scientific Community**](#scientific-community) - Public sharing and benchmarking
- [⚙️ **System Administrators**](#system-administrators) - Deployment and management

### **By Task**
- [🚀 **Getting Started**](#getting-started) - Installation and first analysis
- [📊 **Core Analysis Workflows**](#core-analysis-workflows) - Full pipeline and individual stages
- [🔬 **Research Reproducibility**](#research-reproducibility) - Scientific best practices
- [🤝 **Collaboration**](#collaboration) - Team workflows and sharing
- [🔌 **Integration**](#integration) - API usage and custom tools
- [🛠️ **Advanced Topics**](#advanced-topics) - Performance and customization

---

## 🚀 **Getting Started**

### **Installation & Setup**

#### **Prerequisites**
```bash
# Check Python version (3.11+ required)
python --version

# Verify you have pip
pip --version
```

#### **Installation**
```bash
# Install EMUSES
pip install git+https://github.com/chrisfoulon/emuses.git

# Verify installation
emuses --help
```

#### **First Analysis (5 minutes)**
```bash
# Navigate to a working directory
mkdir emuses_workspace
cd emuses_workspace

# Run your first analysis with sample data
emuses full my_first_analysis/ \
  docs/examples/sample_data/hcp_input_data.csv \
  --scores docs/examples/sample_data/hcp_labels.csv

# Expected output: Analysis completes in 3-5 minutes
# Results saved to my_first_analysis/ directory
```

#### **Verify Results**
```bash
# Check what was created
ls my_first_analysis/

# View analysis summary
cat my_first_analysis/reports/analysis_summary.md

# Check model registry
emuses models list
```

### **Understanding Your Results**

Your first analysis creates several important outputs:

```
my_first_analysis/
├── umap_embeddings.npy          # 2D brain network coordinates
├── umap_model.pkl               # Trained UMAP model
├── heatmap_data.npy             # Brain-behavior correlations
├── heatmap_visualization.png    # Visual correlation map
├── models/                      # Trained predictive models
│   ├── model_manifest.json     # Model metadata
│   └── trained_model.pkl       # Prediction model
└── reports/
    ├── analysis_summary.md     # Human-readable summary
    └── performance_metrics.json # Model performance stats
```

**Key Insights from Results**:
- **UMAP Embeddings**: Show how brain patterns cluster
- **Heatmap**: Reveals which brain regions predict behavior
- **Model Performance**: R² score indicates prediction accuracy
- **Manifest**: Contains full reproducibility information

---

<details markdown="1">
<summary>🔬 **Research Contexts** - Choose your research environment and workflow</summary>

*Audience-specific guidance for different research contexts and team structures*

## 🔬 **Individual Researchers**

*Perfect for: Personal analysis, method development, exploratory research*

### **Your Research Environment**

As an individual researcher, EMUSES automatically configures for **Local Mode**:
- ✅ No setup required - works immediately after installation
- ✅ All models stored locally (`~/.local/share/emuses/models`)
- ✅ Full privacy - no network connectivity needed
- ✅ Complete reproducibility with local version control

### **Common Individual Workflows**

#### **Workflow 1: Exploratory Data Analysis**

**Goal**: Understand your neuroimaging dataset patterns

```bash
# Step 1: Quick visualization with UMAP only
emuses umap exploration_umap/ my_brain_data.csv \
  --n_neighbors 30 \
  --min_dist 0.01

# Step 2: Examine clustering patterns
# Open exploration_umap/umap_visualization.png

# Step 3: If patterns look good, run correlation analysis
emuses heatmap brain_behavior_map/ exploration_umap/umap_embeddings.npy \
  --scores my_cognitive_scores.csv \
  --grid_resolution 150
```

**Expected Timeline**: 10-15 minutes  
**Use When**: New dataset, quality control, hypothesis generation

#### **Workflow 2: Hypothesis Testing**

**Goal**: Test specific brain-behavior relationships

```bash
# Step 1: Full analysis with specific parameters
emuses full hypothesis_test/ brain_features.csv \
  --scores target_behavior.csv \
  --n_neighbors 15 \
  --min_dist 0.1 \
  --verbose

# Step 2: Examine model performance
emuses info hypothesis_test/models/trained_model.pkl

# Step 3: Generate reproduction guide for methods section
emuses reproduce hypothesis_test/models/trained_model.pkl \
  --include_environment \
  --output methods_section.md

# Step 4: Create citation for references
emuses cite hypothesis_test/models/trained_model.pkl \
  --style apa \
  --include_data \
  --output references.txt
```

**Expected Timeline**: 5-10 minutes  
**Use When**: Testing specific hypotheses, preparing publications

#### **Workflow 3: Method Development**

**Goal**: Develop and test new analysis approaches

```bash
# Step 1: Baseline analysis
emuses full baseline_method/ data.csv --scores scores.csv

# Step 2: Modified parameters analysis
emuses full modified_method/ data.csv \
  --scores scores.csv \
  --n_neighbors 50 \
  --min_dist 0.001

# Step 3: Compare approaches
emuses compare baseline_method/models/trained_model.pkl \
            modified_method/models/trained_model.pkl \
  --detailed \
  --output method_comparison.md

# Step 4: Verify reproducibility
emuses verify baseline_method/models/trained_model.pkl
emuses verify modified_method/models/trained_model.pkl
```

**Expected Timeline**: 15-30 minutes  
**Use When**: Developing new methods, optimizing parameters

### **Best Practices for Individual Research**

#### **Data Organization**
```bash
# Organize projects by study
mkdir -p ~/research/studies/motor_cortex_study
cd ~/research/studies/motor_cortex_study

# Keep raw data separate from analysis
mkdir -p data/raw data/processed results

# Use descriptive analysis names
emuses full results/motor_cortex_connectivity_v1/ \
  data/processed/connectivity_matrix.csv \
  --scores data/processed/motor_scores.csv
```

#### **Version Control Integration**
```bash
# Initialize git repository
git init

# Track analysis scripts and configurations
git add *.sh *.json *.md

# Commit before major analyses
git commit -m "Baseline analysis configuration"

# After analysis, track key results
git add results/*/reports/analysis_summary.md
git add results/*/models/model_manifest.json
git commit -m "Motor cortex baseline analysis completed"
```

#### **Reproducibility Workflow**
```bash
# Always generate reproduction guides
emuses reproduce results/analysis_v1/models/trained_model.pkl

# Verify model integrity regularly
emuses verify results/analysis_v1/models/trained_model.pkl

# Document analysis pipeline
emuses trace results/analysis_v1/models/trained_model.pkl \
  --include_environment \
  --output analysis_provenance.json
```

---

## 🏛️ **Research Labs**

*Perfect for: Team collaboration, shared resources, multi-user environments*

### **Lab Setup & Administration**

#### **Setting Up Database Mode**

**Prerequisites**:
- PostgreSQL database server
- Shared storage (NFS, or cloud storage)
- Network connectivity between lab members

```bash
# 1. Administrator setup
sudo -u postgres createdb emuses_lab_registry
sudo -u postgres createuser emuses_admin --pwprompt

# 2. Configure environment for all lab members
export EMUSES_DATABASE_URL="postgresql://emuses_admin:password@lab-server:5432/emuses_lab_registry"
export EMUSES_DEPLOYMENT_MODE="multi-user"

# 3. Initialize database schema
emuses models init-db

# 4. Verify database mode
emuses models mode-info --check_requirements
```

#### **User Management**

**Adding Lab Members**:
```bash
# Add research staff
emuses admin add-user \
  --username "jane_postdoc" \
  --email "jane@university.edu" \
  --role "user" \
  --quota "5GB" \
  --workspaces "neurology_lab,motor_cortex_project" \
  --send_invite

# Add students with limited access
emuses admin add-user \
  --username "student_001" \
  --email "student@university.edu" \
  --role "viewer" \
  --quota "1GB" \
  --workspaces "training_workspace"

# Batch add multiple users
emuses admin add-user --batch_file new_semester_students.csv
```

**Monitoring Lab Usage**:
```bash
# Check lab-wide statistics
emuses admin system-status --detailed

# Monitor user activity
emuses admin list-users --include_stats --workspace neurology_lab

# Track resource usage
emuses models storage --detailed --suggest_cleanup
```

### **Collaborative Workflows**

#### **Workflow 1: Shared Model Development**

**Scenario**: Team developing brain connectivity analysis

```bash
# Lab member 1: Initial analysis
emuses workspace create "connectivity_project" \
  --description "Multi-modal brain connectivity analysis" \
  --visibility internal

emuses full connectivity_v1/ hcp_connectivity.csv \
  --scores cognitive_battery.csv \
  --workspace connectivity_project

emuses models install connectivity_v1/models/trained_model.pkl \
  --workspace connectivity_project \
  --name "baseline_connectivity_model"

# Lab member 2: Model refinement
emuses workspace list --role member
emuses models list --workspace connectivity_project

# Download baseline model
emuses models info baseline_connectivity_model
emuses inference baseline_connectivity_model new_subjects.csv \
  --output refined_predictions.csv

# Compare with improved approach
emuses full connectivity_v2/ enhanced_features.csv \
  --scores cognitive_battery.csv \
  --workspace connectivity_project

emuses compare connectivity_v1/models/trained_model.pkl \
            connectivity_v2/models/trained_model.pkl \
  --output team_model_comparison.md

# Lab member 3: Independent validation
emuses models list --workspace connectivity_project
emuses inference connectivity_v2_model validation_dataset.csv
```

#### **Workflow 2: Reproducible Research Pipeline**

**Scenario**: Lab establishing standardized analysis protocol

```bash
# 1. Principal Investigator: Create standard protocol
emuses workspace create "lab_standard_pipeline" \
  --description "Standardized neuroimaging analysis protocol" \
  --template standard_analysis

# 2. Create reference analysis
emuses full reference_analysis/ reference_dataset.csv \
  --scores reference_scores.csv \
  --workspace lab_standard_pipeline \
  --config lab_standard_config.json

# 3. Generate comprehensive documentation
emuses reproduce reference_analysis/models/trained_model.pkl \
  --include_environment \
  --include_data_prep \
  --output lab_protocol_v1.md

emuses trace reference_analysis/models/trained_model.pkl \
  --include_data_lineage \
  --output reference_provenance.json

# 4. Team members: Follow standard protocol
emuses rerun reference_analysis/ \
  --update_data new_project_data.csv \
  --workspace my_project

# 5. Quality assurance
emuses verify my_project/models/trained_model.pkl
emuses compare reference_analysis/models/trained_model.pkl \
            my_project/models/trained_model.pkl
```

### **Lab Administration Workflows**

#### **Regular Maintenance**

**Weekly Maintenance**:
```bash
# System health check
emuses admin system-status --alerts_only

# Storage cleanup
emuses models cleanup --dry_run
emuses models storage --suggest_cleanup

# User activity review
emuses admin list-users --sort last_login | head -20
```

**Monthly Review**:
```bash
# Generate lab statistics report
emuses admin system-status --detailed --export monthly_report.json
emuses models stats --period month --format csv > monthly_usage.csv

# Resource planning
emuses admin list-users --include_stats | grep "quota.*90%"

# Archive old models
emuses models list | grep "2024-06" | xargs -I {} emuses models remove {} --backup
```

#### **Troubleshooting Common Issues**

**User Can't Access Models**:
```bash
# Check user permissions
emuses admin list-users --username jane_postdoc
emuses workspace info neurology_lab --include_members

# Fix workspace access
emuses workspace add-member neurology_lab jane_postdoc --role member
```

**System Performance Issues**:
```bash
# Check resource usage
emuses admin system-status --detailed

# Cancel stuck jobs
emuses admin list-jobs --status running
emuses admin cancel-job job_abc123 --reason "System maintenance"

# Clean up orphaned files
emuses models cleanup --aggressive --backup
```

---

## 🌍 **Scientific Community**

*Perfect for: Public model sharing, benchmarking, meta-analyses*

### **Cloud Mode Setup**

**Prerequisites**:
- Cloud database (PostgreSQL)
- Cloud storage (S3, Azure, etc.)
- Production monitoring setup

```bash
# 1. Configure cloud environment
export EMUSES_DEPLOYMENT_MODE="production"
export EMUSES_DATABASE_URL="postgresql://user:pass@cloud-db:5432/emuses"
export EMUSES_REDIS_URL="redis://cloud-redis:6379/0"
export EMUSES_STORAGE_BACKEND="s3"
export AWS_S3_BUCKET="emuses-public-models"

# 2. Initialize cloud deployment
emuses models init-cloud

# 3. Verify cloud mode
emuses models mode-info --check_requirements
```

### **Community Workflows**

#### **Workflow 1: Publishing Research Models**

**Scenario**: Making models available for scientific community

```bash
# 1. Develop model with comprehensive documentation
emuses full public_motor_model/ motor_task_data.csv \
  --scores motor_performance.csv \
  --config publication_config.json

# 2. Comprehensive verification
emuses verify public_motor_model/models/trained_model.pkl --strict

# 3. Generate publication materials
emuses cite public_motor_model/models/trained_model.pkl \
  --style nature \
  --include_data \
  --include_software \
  --output publication_citation.txt

emuses reproduce public_motor_model/models/trained_model.pkl \
  --include_environment \
  --include_data_prep \
  --format markdown \
  --output reproduction_guide.md

# 4. Create comprehensive model information
emuses info public_motor_model/models/trained_model.pkl \
  --format json \
  --detailed \
  --performance \
  --provenance > model_metadata.json

# 5. Publish to community
emuses models publish public_motor_model/models/trained_model.pkl \
  --workspace community \
  --visibility public \
  --description "Motor cortex task prediction model (HCP n=1068)" \
  --tags "motor,cortex,hcp,prediction" \
  --license "CC-BY-4.0"
```

#### **Workflow 2: Community Benchmarking**

**Scenario**: Comparing methods across research groups

```bash
# 1. Discover community models
emuses models search "motor cortex" --workspace community
emuses models search "working memory" --limit 20 --sort relevance

# 2. Download models for comparison
emuses models install community_motor_model_v2 \
  --workspace benchmarking

emuses models install stanford_motor_classifier \
  --workspace benchmarking

# 3. Run benchmark comparison
emuses inference community_motor_model_v2 benchmark_dataset.csv \
  --output community_predictions.csv

emuses inference stanford_motor_classifier benchmark_dataset.csv \
  --output stanford_predictions.csv

# 4. Compare performance
emuses compare community_motor_model_v2 \
            stanford_motor_classifier \
  --benchmark_data benchmark_dataset.csv \
  --output benchmark_comparison.md

# 5. Contribute benchmark results
emuses models publish benchmark_comparison.md \
  --workspace community \
  --type "benchmark_report" \
  --description "Motor cortex model comparison (n=500)"
```

#### **Workflow 3: Meta-Analysis**

**Scenario**: Analyzing models across multiple studies

```bash
# 1. Collect models from multiple sources
emuses models search "fMRI working memory" \
  --workspace community \
  --format json > working_memory_models.json

# 2. Download and analyze each model
cat working_memory_models.json | jq -r '.models[].name' | while read model; do
  emuses models install "$model" --workspace meta_analysis
  emuses info "$model" --format json > "meta_analysis/${model}_info.json"
done

# 3. Extract performance metrics
python extract_meta_metrics.py meta_analysis/ > meta_analysis_results.csv

# 4. Generate meta-analysis report
emuses models publish meta_analysis_results.csv \
  --workspace community \
  --type "meta_analysis" \
  --description "Working memory fMRI models meta-analysis (k=23)"
```

---

</details>

<details markdown="1">
<summary>📊 **Core Workflows** - Analysis pipelines and scientific reproducibility</summary>

*Complete analysis workflows, reproducibility best practices, and collaborative research methods*

## 📊 **Core Analysis Workflows**

### **Full Pipeline Analysis**

The complete EMUSES pipeline combines dimensionality reduction, correlation analysis, and predictive modeling:

#### **Standard Full Pipeline**

```bash
# Basic full analysis
emuses full analysis_output/ input_features.csv \
  --scores cognitive_scores.csv \
  --verbose

# Timeline: 3-8 minutes depending on data size
# Output: Complete analysis with all components
```

#### **Customized Pipeline Parameters**

```bash
# High-resolution analysis for publication
emuses full publication_analysis/ brain_features.csv \
  --scores behavioral_measures.csv \
  --n_neighbors 50 \
  --min_dist 0.001 \
  --n_jobs 8 \
  --config publication_config.json

# Fast exploratory analysis
emuses full quick_exploration/ features.csv \
  --scores scores.csv \
  --n_neighbors 10 \
  --min_dist 0.2 \
  --n_jobs -1
```

### **Individual Stage Analysis**

#### **UMAP Dimensionality Reduction**

**When to use**: Data exploration, quality control, visualization

```bash
# Basic UMAP for visualization
emuses umap visualization_umap/ brain_connectivity.csv

# High-resolution UMAP for publication
emuses umap publication_umap/ connectivity_matrix.csv \
  --n_neighbors 100 \
  --min_dist 0.001 \
  --random_state 42

# 3D UMAP for interactive exploration
emuses umap 3d_exploration/ features.csv \
  --n_components 3 \
  --n_neighbors 30
```

**UMAP Parameter Guide**:
- **n_neighbors**: 
  - Small (5-15): Local structure, fine details
  - Large (50-100): Global structure, smooth embedding
- **min_dist**:
  - Small (0.001-0.01): Tight clusters, detailed structure
  - Large (0.1-0.5): Spread out points, general structure

#### **Heatmap Generation**

**When to use**: Brain-behavior correlation analysis, hypothesis testing

```bash
# Basic correlation heatmap
emuses heatmap correlation_map/ umap_embeddings.npy \
  --scores cognitive_data.csv

# High-resolution publication heatmap
emuses heatmap publication_heatmap/ embeddings.npy \
  --scores behavior_scores.csv \
  --grid_resolution 200 \
  --colormap "RdBu_r" \
  --threshold 0.01

# Multi-score heatmap analysis
emuses heatmap multi_score_analysis/ embeddings.npy \
  --scores multiple_measures.csv \
  --stat_function "correlation"
```

#### **Model Inference**

**When to use**: Applying trained models to new data

```bash
# Basic inference on new subjects
emuses inference trained_model/ new_subjects.csv

# Validation mode with known labels
emuses inference model_directory/ test_data.csv \
  --validation_mode \
  --output_format json

# Batch inference for large datasets
emuses inference production_model/ large_cohort.csv \
  --batch_size 64 \
  --output_path batch_predictions/
```

### **Quality Control Workflows**

#### **Data Quality Assessment**

```bash
# Step 1: Quick UMAP visualization
emuses umap qc_umap/ raw_data.csv

# Step 2: Check for outliers (visually inspect qc_umap/umap_visualization.png)

# Step 3: If outliers found, re-run with cleaned data
emuses umap clean_umap/ cleaned_data.csv

# Step 4: Proceed with full analysis if quality looks good
emuses full final_analysis/ cleaned_data.csv --scores scores.csv
```

#### **Model Validation**

```bash
# Step 1: Split data for validation
python split_data.py full_dataset.csv --train_ratio 0.8

# Step 2: Train on training set
emuses full training_analysis/ train_data.csv --scores train_scores.csv

# Step 3: Test on validation set
emuses inference training_analysis/models/trained_model.pkl validation_data.csv \
  --validation_mode \
  --output validation_results.json

# Step 4: Check performance
python analyze_validation.py validation_results.json
```

---

## 🔬 **Research Reproducibility**

### **Model Verification & Integrity**

#### **Comprehensive Model Verification**

```bash
# Basic integrity check
emuses verify analysis_results/models/trained_model.pkl

# Strict verification with detailed report
emuses verify publication_model/ \
  --strict \
  --report verification_report.json

# Automated verification with fix attempt
emuses verify potentially_corrupted_model/ --fix
```

#### **Model Information & Metadata**

```bash
# Basic model information
emuses info brain_classifier/models/trained_model.pkl

# Detailed technical information
emuses info complex_model/ \
  --format json \
  --detailed \
  --performance \
  --provenance > complete_model_info.json

# Performance-focused summary
emuses info trained_model/ --performance
```

### **Provenance & Traceability**

#### **Complete Provenance Tracking**

```bash
# Basic provenance export
emuses trace analysis_model/ --format json

# Comprehensive provenance with environment
emuses trace production_model/ \
  --format json \
  --include_environment \
  --include_data_lineage \
  --output complete_provenance.json

# RDF format for semantic web
emuses trace research_model/ \
  --format rdf \
  --output model_provenance.rdf
```

#### **Reproducibility Documentation**

```bash
# Generate reproduction guide
emuses reproduce published_model/ \
  --include_environment \
  --include_data_prep \
  --output reproduction_instructions.md

# Create publication-ready methods section
emuses reproduce neuroimaging_model/ \
  --format markdown \
  --include_environment \
  --output methods_section.md

# Generate complete reproduction package
emuses reproduce study_model/ \
  --include_environment \
  --include_data_prep \
  --format html \
  --output reproduction_package.html
```

### **Citation & Attribution**

#### **Generate Proper Citations**

```bash
# APA style citation
emuses cite brain_model/ --style apa

# BibTeX for LaTeX documents
emuses cite research_model/ \
  --style bibtex \
  --include_data \
  --include_software \
  --output references.bib

# Nature journal format
emuses cite published_model/ \
  --style nature \
  --include_data \
  --output nature_refs.txt

# Complete citation package
emuses cite comprehensive_model/ \
  --style apa \
  --include_data \
  --include_software \
  --output complete_citations.txt
```

### **Version Control & Comparison**

#### **Model Version Management**

```bash
# Check for modifications
emuses diff original_model/ --detailed

# Compare model versions
emuses compare model_v1/ model_v2/ \
  --detailed \
  --output version_comparison.md

# Track changes over time
emuses diff baseline_model/ > changes_log.txt
git add changes_log.txt
git commit -m "Model changes documented"
```

#### **Rerun Previous Analyses**

```bash
# Rerun exact previous analysis
emuses rerun previous_analysis_output/

# Rerun with updated data
emuses rerun old_analysis/ \
  --update_data new_dataset.csv \
  --force

# Rerun for verification
emuses rerun published_analysis/ \
  --output verification_run/
```

---

## 🤝 **Collaboration**

### **Workspace Management**

#### **Creating Collaborative Workspaces**

```bash
# Create research lab workspace
emuses workspace create "neuroimaging_lab" \
  --description "Collaborative neuroimaging research workspace" \
  --visibility internal \
  --invite_members "colleague1@uni.edu,colleague2@uni.edu"

# Create public research workspace
emuses workspace create "open_brain_models" \
  --description "Public brain modeling workspace" \
  --visibility public \
  --template community_research

# Create project-specific workspace
emuses workspace create "motor_cortex_study" \
  --description "Motor cortex connectivity study" \
  --visibility private
```

#### **Workspace Collaboration Workflows**

```bash
# Join existing workspace
emuses workspace list --role member

# Contribute models to workspace
emuses models install my_analysis/models/trained_model.pkl \
  --workspace neuroimaging_lab \
  --name "connectivity_classifier_v2"

# Share analysis with team
emuses workspace info neuroimaging_lab --include_models

# Download team models
emuses models list --workspace neuroimaging_lab
emuses models install team_baseline_model \
  --workspace my_local_copy
```

### **Model Sharing Workflows**

#### **Sharing Models Between Researchers**

```bash
# Export model for sharing
emuses models export my_trained_model \
  --output shared_model.zip \
  --include_data_sample

# Share via email/file transfer
# Recipient installs shared model:
emuses models install shared_model.zip \
  --verify

# Test shared model
emuses inference shared_model_name test_data.csv
```

#### **Lab-Wide Model Distribution**

```bash
# Lab administrator: Create standard model
emuses models install reference_analysis/models/trained_model.pkl \
  --workspace lab_standard \
  --name "lab_reference_model_v1"

# Lab members: Access standard model
emuses models list --workspace lab_standard
emuses models install lab_reference_model_v1

# Use standard model for new analyses
emuses inference lab_reference_model_v1 my_new_data.csv
```

---

</details>

<details markdown="1">
<summary>⚙️ **Advanced Features** - Integration, customization, and performance optimization</summary>

*API integration, custom tool development, performance tuning, and advanced configuration options*

## 🔌 **Integration**

### **API Integration**

#### **Python Integration Examples**

**Complete Analysis Workflow**:
```python
import requests
import pandas as pd
import numpy as np
from pathlib import Path

class EmusesWorkflow:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def run_complete_analysis(self, features_csv, scores_csv, 
                             output_dir="./results"):
        """Run complete EMUSES analysis workflow"""
        
        # 1. Submit analysis job
        job = self.submit_full_pipeline(features_csv, scores_csv)
        print(f"Analysis submitted: {job['job_id']}")
        
        # 2. Monitor progress
        result = self.wait_for_completion(job['job_id'])
        print(f"Analysis completed in {result['timing']['total_duration_seconds']}s")
        
        # 3. Download all results
        artifacts = self.download_artifacts(job['job_id'], output_dir)
        print(f"Downloaded {len(artifacts)} result files")
        
        # 4. Load key results
        results = self.load_results(output_dir)
        return results
    
    def submit_full_pipeline(self, features_file, scores_file, **kwargs):
        """Submit full pipeline analysis"""
        url = f"{self.base_url}/api/v1/jobs/pipeline/full"
        
        with open(features_file, 'rb') as f_feat, open(scores_file, 'rb') as f_scores:
            files = {
                'features_file': f_feat,
                'scores_file': f_scores
            }
            response = self.session.post(url, files=files, data=kwargs)
            response.raise_for_status()
            return response.json()
    
    def wait_for_completion(self, job_id, polling_interval=30):
        """Wait for job completion with progress updates"""
        url = f"{self.base_url}/api/v1/jobs/{job_id}/status"
        
        while True:
            response = self.session.get(url)
            status_data = response.json()
            
            if status_data['status'] == 'completed':
                return status_data
            elif status_data['status'] == 'failed':
                raise Exception(f"Analysis failed: {status_data.get('error', {}).get('message')}")
            
            # Show progress
            if 'progress' in status_data:
                progress = status_data['progress']
                print(f"Progress: {progress['completion_percentage']}% - {progress['current_stage']}")
            
            time.sleep(polling_interval)
    
    def download_artifacts(self, job_id, output_dir):
        """Download all analysis artifacts"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Get artifact list
        artifacts_url = f"{self.base_url}/api/v1/jobs/{job_id}/artifacts"
        response = self.session.get(artifacts_url)
        artifacts = response.json()['artifacts']
        
        # Download each artifact
        downloaded = []
        for artifact in artifacts:
            download_url = f"{self.base_url}{artifact['download_url']}"
            file_response = self.session.get(download_url)
            
            file_path = output_path / artifact['filename']
            with open(file_path, 'wb') as f:
                f.write(file_response.content)
            
            downloaded.append(str(file_path))
            print(f"Downloaded: {artifact['filename']} ({artifact['size']})")
        
        return downloaded
    
    def load_results(self, output_dir):
        """Load analysis results into Python objects"""
        output_path = Path(output_dir)
        results = {}
        
        # Load UMAP embeddings
        embeddings_file = output_path / "umap_embeddings.npy"
        if embeddings_file.exists():
            results['umap_embeddings'] = np.load(embeddings_file)
        
        # Load heatmap data
        heatmap_file = output_path / "heatmap_data.npy" 
        if heatmap_file.exists():
            results['heatmap_data'] = np.load(heatmap_file)
        
        # Load performance metrics
        metrics_file = output_path / "performance_metrics.json"
        if metrics_file.exists():
            with open(metrics_file) as f:
                results['performance'] = json.load(f)
        
        return results

# Usage example
workflow = EmusesWorkflow()

# Run complete analysis
results = workflow.run_complete_analysis(
    'brain_connectivity.csv',
    'cognitive_scores.csv',
    job_name='python_integration_test',
    n_neighbors=20
)

# Access results
print(f"UMAP embeddings shape: {results['umap_embeddings'].shape}")
print(f"Model R²: {results['performance']['r_squared']}")

# Use embeddings for custom visualization
import matplotlib.pyplot as plt
plt.scatter(results['umap_embeddings'][:, 0], 
           results['umap_embeddings'][:, 1])
plt.title('UMAP Brain Network Embedding')
plt.show()
```

#### **R Integration Examples**

**Complete R Workflow**:
```r
library(httr)
library(jsonlite)
library(ggplot2)

# EMUSES R Client Class
EmusesClient <- R6::R6Class("EmusesClient",
  public = list(
    base_url = NULL,
    
    initialize = function(base_url = "http://localhost:8000") {
      self$base_url <- base_url
    },
    
    submit_analysis = function(features_file, scores_file, ...) {
      url <- paste0(self$base_url, "/api/v1/jobs/pipeline/full")
      
      # Prepare form data
      body <- list(
        features_file = upload_file(features_file),
        scores_file = upload_file(scores_file)
      )
      
      # Add optional parameters
      extra_params <- list(...)
      body <- c(body, extra_params)
      
      # Submit request
      response <- POST(url, body = body, encode = "multipart")
      stop_for_status(response)
      
      return(content(response, "parsed"))
    },
    
    wait_for_completion = function(job_id, polling_interval = 30) {
      url <- paste0(self$base_url, "/api/v1/jobs/", job_id, "/status")
      
      repeat {
        response <- GET(url)
        status_data <- content(response, "parsed")
        
        if (status_data$status == "completed") {
          return(status_data)
        } else if (status_data$status == "failed") {
          stop(paste("Analysis failed:", status_data$error$message))
        }
        
        # Show progress
        if (!is.null(status_data$progress)) {
          cat(sprintf("Progress: %d%% - %s\n", 
                      status_data$progress$completion_percentage,
                      status_data$progress$current_stage))
        }
        
        Sys.sleep(polling_interval)
      }
    },
    
    download_artifacts = function(job_id, output_dir = "./results") {
      dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)
      
      # Get artifact list
      artifacts_url <- paste0(self$base_url, "/api/v1/jobs/", job_id, "/artifacts")
      response <- GET(artifacts_url)
      artifacts <- content(response, "parsed")$artifacts
      
      # Download each artifact
      downloaded <- c()
      for (artifact in artifacts) {
        download_url <- paste0(self$base_url, artifact$download_url)
        file_response <- GET(download_url)
        
        file_path <- file.path(output_dir, artifact$filename)
        writeBin(content(file_response, "raw"), file_path)
        
        downloaded <- c(downloaded, file_path)
        cat(sprintf("Downloaded: %s (%s)\n", artifact$filename, artifact$size))
      }
      
      return(downloaded)
    },
    
    load_embeddings = function(output_dir) {
      # Note: This requires numpy file reading capability
      # For R, consider using reticulate package or convert to CSV
      embeddings_file <- file.path(output_dir, "umap_embeddings.npy")
      
      if (file.exists(embeddings_file)) {
        # Using reticulate to read numpy files
        np <- reticulate::import("numpy")
        embeddings <- np$load(embeddings_file)
        return(as.matrix(embeddings))
      }
      
      return(NULL)
    }
  )
)

# Usage example
client <- EmusesClient$new()

# Submit analysis
job <- client$submit_analysis(
  "brain_connectivity.csv",
  "cognitive_scores.csv",
  job_name = "r_integration_test",
  n_neighbors = 15
)

cat("Job submitted:", job$job_id, "\n")

# Wait for completion
result <- client$wait_for_completion(job$job_id)
cat("Analysis completed!\n")

# Download results
artifacts <- client$download_artifacts(job$job_id, "r_results")

# Load and visualize embeddings
embeddings <- client$load_embeddings("r_results")
if (!is.null(embeddings)) {
  # Create UMAP visualization
  df <- data.frame(
    UMAP1 = embeddings[, 1],
    UMAP2 = embeddings[, 2]
  )
  
  p <- ggplot(df, aes(x = UMAP1, y = UMAP2)) +
    geom_point(alpha = 0.6) +
    theme_minimal() +
    labs(title = "UMAP Brain Network Embedding",
         subtitle = "Generated via EMUSES API")
  
  print(p)
}
```

### **Custom Tool Integration**

#### **Jupyter Notebook Integration**

```python
# emuses_jupyter_utils.py
import ipywidgets as widgets
from IPython.display import display, Image, HTML
import matplotlib.pyplot as plt
import seaborn as sns

class EmusesNotebook:
    def __init__(self, workflow_client):
        self.client = workflow_client
        self.current_job = None
        
    def interactive_analysis(self):
        """Create interactive widget for EMUSES analysis"""
        
        # File upload widgets
        features_upload = widgets.FileUpload(
            accept='.csv',
            description='Brain Features CSV'
        )
        
        scores_upload = widgets.FileUpload(
            accept='.csv', 
            description='Cognitive Scores CSV'
        )
        
        # Parameter widgets
        n_neighbors_slider = widgets.IntSlider(
            value=15, min=5, max=100,
            description='UMAP Neighbors'
        )
        
        min_dist_slider = widgets.FloatLogSlider(
            value=0.1, base=10, min=-3, max=0,
            description='UMAP Min Distance'
        )
        
        # Analysis button
        analyze_button = widgets.Button(
            description='Run Analysis',
            button_style='success'
        )
        
        # Progress bar
        progress_bar = widgets.IntProgress(
            value=0, min=0, max=100,
            description='Analysis Progress'
        )
        
        # Output area
        output_area = widgets.Output()
        
        def on_analyze_clicked(b):
            with output_area:
                output_area.clear_output()
                
                if not features_upload.value or not scores_upload.value:
                    print("Please upload both files")
                    return
                
                # Save uploaded files
                with open('temp_features.csv', 'wb') as f:
                    f.write(features_upload.value[0]['content'])
                with open('temp_scores.csv', 'wb') as f:
                    f.write(scores_upload.value[0]['content'])
                
                # Submit analysis
                try:
                    job = self.client.submit_full_pipeline(
                        'temp_features.csv',
                        'temp_scores.csv',
                        n_neighbors=n_neighbors_slider.value,
                        min_dist=min_dist_slider.value
                    )
                    
                    self.current_job = job['job_id']
                    print(f"Analysis submitted: {job['job_id']}")
                    
                    # Monitor progress
                    self.monitor_progress(progress_bar, output_area)
                    
                except Exception as e:
                    print(f"Error: {e}")
        
        analyze_button.on_click(on_analyze_clicked)
        
        # Layout
        ui = widgets.VBox([
            widgets.HTML("<h3>EMUSES Interactive Analysis</h3>"),
            features_upload,
            scores_upload,
            n_neighbors_slider,
            min_dist_slider,
            analyze_button,
            progress_bar,
            output_area
        ])
        
        display(ui)
    
    def monitor_progress(self, progress_bar, output_area):
        """Monitor analysis progress with live updates"""
        import time
        
        while True:
            status = self.client.session.get(
                f"{self.client.base_url}/api/v1/jobs/{self.current_job}/status"
            ).json()
            
            if 'progress' in status:
                progress_bar.value = status['progress']['completion_percentage']
            
            if status['status'] == 'completed':
                with output_area:
                    print("✅ Analysis completed!")
                    self.display_results()
                break
            elif status['status'] == 'failed':
                with output_area:
                    print(f"❌ Analysis failed: {status.get('error', {}).get('message')}")
                break
            
            time.sleep(5)
    
    def display_results(self):
        """Display analysis results in notebook"""
        
        # Download and display results
        artifacts = self.client.download_artifacts(self.current_job, 'notebook_results')
        
        # Load and display UMAP visualization
        embeddings_file = 'notebook_results/umap_embeddings.npy'
        if os.path.exists(embeddings_file):
            embeddings = np.load(embeddings_file)
            
            plt.figure(figsize=(10, 8))
            plt.scatter(embeddings[:, 0], embeddings[:, 1], alpha=0.6)
            plt.title('UMAP Brain Network Embedding')
            plt.xlabel('UMAP 1')
            plt.ylabel('UMAP 2')
            plt.show()
        
        # Display heatmap if available
        heatmap_file = 'notebook_results/heatmap_visualization.png'
        if os.path.exists(heatmap_file):
            display(HTML("<h4>Brain-Behavior Correlation Heatmap</h4>"))
            display(Image(heatmap_file))

# Usage in Jupyter notebook
from emuses_integration import EmusesWorkflow
from emuses_jupyter_utils import EmusesNotebook

# Initialize
workflow = EmusesWorkflow()
notebook = EmusesNotebook(workflow)

# Display interactive interface
notebook.interactive_analysis()
```

---

## 🛠️ **Advanced Topics**

### **Performance Optimization**

#### **Large Dataset Optimization**

```bash
# For large datasets (>10GB), use optimized parameters
emuses full large_dataset_analysis/ huge_connectivity.csv \
  --scores cognitive_data.csv \
  --n_jobs 16 \
  --batch_size 1000 \
  --memory_limit 32GB

# Use staged approach for very large datasets
emuses umap large_umap/ huge_features.csv \
  --n_neighbors 15 \
  --batch_mode \
  --checkpoint_interval 1000

emuses heatmap large_heatmap/ large_umap/umap_embeddings.npy \
  --scores scores.csv \
  --grid_resolution 50  # Reduced for memory
```

#### **HPC Cluster Integration**

**SLURM Integration Example**:
```bash
#!/bin/bash
#SBATCH --job-name=emuses_analysis
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=16
#SBATCH --time=4:00:00
#SBATCH --mem=64GB

# Load modules
module load python/3.11
module load emuses/0.9.0

# Set up environment
export EMUSES_N_JOBS=16
export EMUSES_MEMORY_LIMIT=60GB

# Run analysis
emuses full ${SLURM_JOB_ID}_analysis/ \
  $1 \
  --scores $2 \
  --n_jobs $SLURM_NTASKS \
  --config hpc_config.json

# Copy results to shared storage
cp -r ${SLURM_JOB_ID}_analysis/ /shared/results/
```

#### **Memory Management**

```bash
# Monitor memory usage during analysis
emuses full memory_monitored/ large_data.csv \
  --scores scores.csv \
  --memory_monitor \
  --memory_limit 16GB

# Use memory-efficient algorithms for large data
emuses full efficient_analysis/ big_dataset.csv \
  --scores scores.csv \
  --algorithm memory_efficient \
  --chunk_size 1000
```

### **Custom Configurations**

#### **Advanced Configuration Files**

**publication_config.json**:
```json
{
  "analysis": {
    "random_seed": 42,
    "reproducible_mode": true,
    "validation_split": 0.2
  },
  "umap": {
    "n_neighbors": 50,
    "min_dist": 0.001,
    "n_components": 2,
    "metric": "euclidean",
    "n_epochs": 1000
  },
  "heatmap": {
    "grid_resolution": 200,
    "interpolation": "cubic",
    "colormap": "RdBu_r",
    "significance_threshold": 0.001
  },
  "modeling": {
    "algorithms": ["ridge", "lasso", "elastic_net"],
    "cross_validation": {
      "folds": 10,
      "stratified": true
    },
    "hyperparameter_tuning": {
      "method": "grid_search",
      "scoring": "r2"
    }
  },
  "output": {
    "save_intermediate": true,
    "compression": true,
    "formats": ["pkl", "json", "csv"]
  }
}
```

**hpc_config.json**:
```json
{
  "performance": {
    "n_jobs": -1,
    "memory_limit": "60GB",
    "chunk_size": 5000,
    "use_gpu": false
  },
  "checkpointing": {
    "enabled": true,
    "interval": 1000,
    "directory": "/tmp/emuses_checkpoints"
  },
  "logging": {
    "level": "INFO",
    "file": "analysis.log",
    "include_performance": true
  }
}
```

### **Extension Development**

#### **Custom Analysis Stages**

```python
# custom_stage.py
from emuses.pipelines.pipeline_stage import PipelineStage
import numpy as np

class CustomAnalysisStage(PipelineStage):
    """Custom analysis stage for specialized processing"""
    
    def __init__(self, custom_param1=10, custom_param2=0.5):
        super().__init__()
        self.custom_param1 = custom_param1
        self.custom_param2 = custom_param2
    
    def run(self, input_data, **kwargs):
        """Run custom analysis"""
        
        # Custom processing logic
        processed_data = self.custom_algorithm(input_data)
        
        # Save results
        output_path = kwargs.get('output_path', 'custom_output/')
        self.save_results(processed_data, output_path)
        
        return {
            'processed_data': processed_data,
            'output_path': output_path,
            'parameters': {
                'custom_param1': self.custom_param1,
                'custom_param2': self.custom_param2
            }
        }
    
    def custom_algorithm(self, data):
        """Implement your custom algorithm"""
        # Example: custom dimensionality reduction
        U, S, Vt = np.linalg.svd(data, full_matrices=False)
        reduced_data = U[:, :self.custom_param1] * S[:self.custom_param1]
        return reduced_data
    
    def save_results(self, data, output_path):
        """Save custom results"""
        import os
        os.makedirs(output_path, exist_ok=True)
        np.save(f"{output_path}/custom_results.npy", data)

# Usage
from custom_stage import CustomAnalysisStage

# Run custom stage
custom_stage = CustomAnalysisStage(custom_param1=20, custom_param2=0.8)
results = custom_stage.run(my_data, output_path='custom_analysis/')
```

#### **Plugin Integration**

```python
# emuses_plugin.py
from emuses.tools.model_registry_factory import ModelRegistryFactory

class CustomModelRegistry:
    """Custom model registry integration"""
    
    def register_custom_model(self, model_path, metadata):
        """Register model with custom metadata"""
        
        registry = ModelRegistryFactory.create_registry()
        
        # Add custom metadata
        enhanced_metadata = {
            **metadata,
            'custom_field': 'custom_value',
            'analysis_type': 'custom_analysis'
        }
        
        return registry.install_model(model_path, metadata=enhanced_metadata)
    
    def search_custom_models(self, query, custom_filters=None):
        """Search with custom filters"""
        
        registry = ModelRegistryFactory.create_registry()
        results = registry.search_models(query)
        
        # Apply custom filters
        if custom_filters:
            filtered_results = []
            for model in results:
                if self.matches_custom_criteria(model, custom_filters):
                    filtered_results.append(model)
            return filtered_results
        
        return results
    
    def matches_custom_criteria(self, model, filters):
        """Custom filtering logic"""
        # Implement custom filtering
        return True

# Usage
custom_registry = CustomModelRegistry()
custom_registry.register_custom_model('my_model/', {'type': 'special'})
```

---

</details>

<details markdown="1">
<summary>🆘 **Support Resources** - Troubleshooting, FAQ, and additional documentation</summary>

*Common issues, solutions, frequently asked questions, and links to additional resources*

## 🆘 **Troubleshooting & FAQ**

### **Common Issues**

#### **Installation Problems**

**Issue**: `ImportError: No module named 'emuses'`
```bash
# Solution 1: Check Python environment
which python
pip list | grep emuses

# Solution 2: Reinstall
pip uninstall emuses
pip install git+https://github.com/chrisfoulon/emuses.git

# Solution 3: Check virtual environment
python -m venv emuses_env
source emuses_env/bin/activate  # Linux/Mac
pip install git+https://github.com/chrisfoulon/emuses.git
```

**Issue**: `Permission denied` errors
```bash
# Solution 1: Install in user space
pip install --user git+https://github.com/chrisfoulon/emuses.git

# Solution 2: Check file permissions
ls -la ~/.local/share/emuses/
chmod -R 755 ~/.local/share/emuses/

# Solution 3: Use virtual environment
python -m venv emuses_env
source emuses_env/bin/activate
pip install git+https://github.com/chrisfoulon/emuses.git
```

#### **Data Format Issues**

**Issue**: `Invalid data format` errors
```bash
# Check CSV structure
head -5 your_data.csv
emuses verify-data your_data.csv  # If available

# Common fixes:
# 1. Ensure CSV has headers
# 2. Check for missing values
# 3. Verify subject ID column exists
# 4. Ensure numeric data is properly formatted
```

**Issue**: `Memory allocation error`
```bash
# Solution 1: Reduce data size
emuses full analysis/ data_subset.csv --scores scores.csv

# Solution 2: Use batch processing
emuses full analysis/ large_data.csv \
  --scores scores.csv \
  --batch_size 500 \
  --memory_limit 8GB

# Solution 3: Use HPC resources
# Submit to cluster with more memory
```

#### **Performance Issues**

**Issue**: Analysis taking too long
```bash
# Solution 1: Use parallel processing
emuses full analysis/ data.csv \
  --scores scores.csv \
  --n_jobs 8

# Solution 2: Reduce UMAP parameters
emuses full analysis/ data.csv \
  --scores scores.csv \
  --n_neighbors 10 \
  --min_dist 0.2

# Solution 3: Monitor resource usage
top -p $(pgrep -f emuses)
```

#### **Model Registry Issues**

**Issue**: `Model not found` errors
```bash
# Check available models
emuses models list

# Check model registry status
emuses models status

# Verify model installation
emuses models info model_name

# Reinstall if corrupted
emuses models remove model_name
emuses models install original_model_path/
```

### **Frequently Asked Questions**

#### **General Usage**

**Q: How do I know if my analysis completed successfully?**
```bash
# Check analysis status
emuses models list  # Should show your model
ls analysis_output/  # Should contain results

# Verify model integrity
emuses verify analysis_output/models/trained_model.pkl

# Check performance metrics
emuses info analysis_output/models/trained_model.pkl --performance
```

**Q: How do I share my models with collaborators?**
```bash
# Method 1: Export model package
emuses models export my_model --output shared_model.zip

# Method 2: Use workspace (multi-user mode)
emuses models install my_model --workspace shared_workspace

# Method 3: Generate reproduction guide
emuses reproduce my_model --output reproduction_guide.md
```

**Q: How do I reproduce a published analysis?**
```bash
# If reproduction guide is available
# Follow instructions in reproduction_guide.md

# If model is available
emuses models install published_model.zip
emuses rerun published_model/ --update_data my_data.csv

# Verify reproduction
emuses compare original_results/ reproduced_results/
```

#### **Technical Questions**

**Q: What data formats does EMUSES accept?**
- **Input Features**: CSV files with subjects as rows, features as columns
- **Scores**: CSV files with subject IDs and target variables
- **Requirements**: Headers required, no missing values in key columns

**Q: How much memory does EMUSES need?**
- **Small datasets** (<1000 subjects): 2-4 GB RAM
- **Medium datasets** (1000-5000 subjects): 8-16 GB RAM  
- **Large datasets** (>5000 subjects): 32+ GB RAM
- **Use `--memory_limit` parameter for control**

**Q: Can I run EMUSES on a cluster?**
```bash
# Yes! Use SLURM/PBS integration
sbatch emuses_job.sh input_data.csv scores.csv

# Or use API for distributed processing
python cluster_submit.py --data data.csv --scores scores.csv
```

### **Getting Help**

#### **Documentation Resources**
- **[CLI Reference](CLI_REFERENCE.md)**: Complete command documentation
- **[API Documentation](API_REFERENCE.md)**: REST API documentation
- **[Quick Start Guide](QUICK_START.md)**: 5-minute tutorial

#### **Community Support**
- **GitHub Issues**: [Report bugs and request features](https://github.com/chrisfoulon/emuses/issues)
- **GitHub Discussions**: [Ask questions and share experiences](https://github.com/chrisfoulon/emuses/discussions)
- **Documentation**: [Complete user guides](docs/)

#### **Diagnostic Commands**
```bash
# System information
emuses --version
emuses models mode-info --check_requirements

# Registry status
emuses models status --detailed

# Health check (if API server running)
curl http://localhost:8000/api/health
```

---

## 🔗 **Related Documentation**

- **[CLI Reference](CLI_REFERENCE.md)** - Complete command-line interface reference
- **[API Documentation](API_REFERENCE.md)** - REST API documentation for integration
- **[Quick Start Guide](QUICK_START.md)** - 5-minute tutorial for immediate results
- **[Research Workflows](RESEARCH_WORKFLOWS.md)** - Scientific use case patterns
- **[Admin Guide](ADMIN_GUIDE.md)** - System administration and deployment
- **[Migration Guide](MIGRATION_GUIDE.md)** - Version upgrade guidance

---

*This comprehensive user guide covers all aspects of EMUSES usage from individual research to large-scale collaborative projects. For specific technical details, consult the CLI or API references. For additional help, visit our GitHub repository or community discussions.*

</details>