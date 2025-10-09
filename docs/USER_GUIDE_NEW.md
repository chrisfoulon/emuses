# 📖 EMUSES Complete User Guide

**Comprehensive guide for scientific research with EMUSES - from first analysis to advanced research workflows**

This guide provides structured learning paths for researchers at all levels, complete workflow examples, and best practices for reproducible scientific research using EMUSES.

## 🎯 **Quick Navigation by Experience Level**

- **🆕 New to EMUSES?** → Start with [Essential Workflows](#essential-workflows) below
- **⚡ Experienced User?** → Jump to [Advanced Usage](#advanced-usage) (click to expand)
- **👩‍💻 Developer/Integrator?** → See [Technical Integration](#technical-integration) (click to expand)

**By Research Context:**
- [🔬 Individual Researchers](#individual-researchers) | [🏛️ Research Labs](#research-labs) | [🌍 Scientific Community](#scientific-community)

**Quick Links:** [📊 Understanding Results](RESULTS_GUIDE.md) | [🚀 Quick Start](QUICK_START.md) | [🔧 API Reference](API_REFERENCE.md)

---

## 🎯 **Essential Workflows**

Core EMUSES workflows that every user should know, regardless of technical background.

### **Your First Complete Analysis**

The most common EMUSES workflow - running a complete analysis pipeline:

```bash
# Standard analysis command (works for most research scenarios)
emuses full my_results/ my_data.csv --scores my_behavioral_scores.csv

# What you'll get:
# ✅ Prediction models trained on your data  
# ✅ Statistical heatmaps showing spatial patterns
# ✅ Effect size maps for scientific interpretation
# ✅ Interactive visualizations for data exploration
```

**Timeline**: 5-15 minutes depending on data size  
**Output**: Complete analysis ready for research interpretation  
**Next Step**: [Understanding your results](RESULTS_GUIDE.md)

### **Common Research Scenarios**

#### **Scenario 1: Brain-Behavior Analysis** (Most Common)
```bash
# Analyze relationship between brain connectivity and cognitive scores
emuses full brain_analysis/ connectivity_matrix.csv --scores cognitive_measures.csv
```

#### **Scenario 2: Multi-Target Analysis**
```bash  
# Multiple behavioral measures at once
emuses full multi_target_analysis/ brain_data.csv --scores multiple_measures.csv
```

#### **Scenario 3: Applying Trained Models to New Data**
```bash
# Use existing model on new subjects
emuses inference new_results/ new_subjects.csv --model trained_model_folder/
```

### **Understanding Your Analysis Results**

After analysis completes, you'll have several types of outputs:

| What You Get | Scientific Meaning | File Location |
|--------------|-------------------|---------------|
| **Prediction Models** | Trained models for your research question | `*.joblib` files |
| **Statistical Heatmaps** | Spatial patterns in your data | `prediction-heatmaps/`, `correlation-heatmaps/` |
| **Effect Size Maps** | Statistical significance findings | `prediction-effects/`, `correlation-effects/` |
| **Interactive Plots** | Data exploration tools | `*.html` files |

**📊 Detailed interpretation**: See [Results Guide](RESULTS_GUIDE.md) for complete explanation

<details markdown="1">
<summary>🔧 **Advanced Usage & Customization**</summary>

## **Parameter Customization**

### **UMAP Optimization for Different Research Goals**

**For Exploratory Analysis** (default settings work well):
```bash
emuses full exploration/ data.csv --scores behavioral.csv
```

**For High-Resolution Publication Analysis**:
```bash
emuses full publication/ data.csv --scores behavioral.csv \
  --n_neighbors 100 \
  --min_dist 0.001 \
  --random_state 42
```

**For Fast Preliminary Analysis**:
```bash
emuses full quick_test/ data.csv --scores behavioral.csv \
  --n_neighbors 10 \
  --min_dist 0.2 \
  --n_jobs -1
```

### **UMAP Parameter Guide**

| Parameter | Small Values | Large Values | Research Impact |
|-----------|-------------|-------------|-----------------|
| `n_neighbors` | 5-15: Local structure, fine details | 50-100: Global structure, smooth embedding | Controls local vs global pattern emphasis |
| `min_dist` | 0.001-0.01: Tight clusters | 0.1-0.5: Spread out points | Affects cluster separation in visualization |
| `n_components` | 2: Standard visualization | 3: 3D exploration | Dimensionality of output embedding |

### **Multi-User and Collaboration Workflows**

#### **Research Lab Shared Analysis**
```bash
# Start shared analysis server for team use
emuses service --port 8000 --shared-models /lab/shared/emuses_models/

# Team members can access via web interface
# http://your-lab-server:8000
```

#### **Model Registry for Reproducibility**
```bash
# Share your model with metadata
emuses registry publish my_analysis/ \
  --title "Brain-Cognition Analysis 2025" \
  --description "HCP dataset analysis for working memory research"

# Others can discover and use your model
emuses registry search "working memory"
emuses inference new_analysis/ new_data.csv --model-id "brain-cognition-2025"
```

### **Integration with Existing Workflows**

#### **Python API Integration**
```python
from emuses import EMUSESPipeline
from emuses.config import PipelineConfig

# Configure analysis programmatically
config = PipelineConfig(
    n_neighbors=50,
    min_dist=0.001, 
    random_state=42
)

# Run analysis in Python
pipeline = EMUSESPipeline(config)
results = pipeline.run(input_data, behavioral_scores)
```

#### **Batch Processing for Multiple Datasets**
```bash
# Process multiple datasets with consistent parameters
for dataset in dataset1 dataset2 dataset3; do
    emuses full results_${dataset}/ ${dataset}_data.csv \
      --scores ${dataset}_scores.csv \
      --n_neighbors 50 \
      --min_dist 0.001
done
```

#### **Integration with HPC/Cluster Systems**
```bash
# SLURM job example
#!/bin/bash
#SBATCH --job-name=emuses-analysis
#SBATCH --time=02:00:00
#SBATCH --mem=32GB
#SBATCH --cpus-per-task=8

module load python/3.11
source /path/to/emuses-env/bin/activate

emuses full $SCRATCH/results/ $SCRATCH/data.csv \
  --scores $SCRATCH/behavioral.csv \
  --n_jobs $SLURM_CPUS_PER_TASK
```

## **Performance Optimization**

### **Memory and Speed Considerations**

**For Large Datasets (>10,000 samples)**:
```bash
emuses full large_analysis/ big_data.csv --scores scores.csv \
  --n_jobs 8 \
  --memory_efficient
```

**For High-Dimensional Data (>10,000 features)**:  
```bash
emuses full highdim_analysis/ wide_data.csv --scores scores.csv \
  --feature_selection_method "variance_threshold" \
  --max_features 5000
```

### **Resource Monitoring**
```bash
# Monitor resource usage during analysis
emuses full analysis/ data.csv --scores scores.csv --verbose --profile
```

</details>

<details markdown="1">
<summary>🔬 **Research Applications & Best Practices**</summary>

## **Scientific Methodology Best Practices**

### **Reproducible Research Workflow**

#### **1. Environment Documentation**
Always document your analysis environment:
```bash
# Save environment specification
pip freeze > requirements.txt

# Or with conda
conda env export > environment.yml

# Include in research materials
emuses --version >> analysis_log.txt
```

#### **2. Parameter Documentation**
```bash
# Save complete analysis configuration
emuses full analysis/ data.csv --scores scores.csv \
  --config_save analysis_config.json \
  --random_state 42
```

#### **3. Data Provenance**
```bash
# Include data checksums for verification
sha256sum data.csv >> analysis_log.txt
sha256sum scores.csv >> analysis_log.txt
```

### **Statistical Considerations**

#### **Cross-Validation and Model Validation**
- **Built-in Nested CV**: EMUSES uses nested cross-validation by default
- **Performance Metrics**: Check `validation_*.json` files for model quality
- **Confidence Assessment**: Use confidence scores in prediction outputs

#### **Multiple Comparisons**
- **Effect Size Maps**: Include appropriate statistical corrections
- **Interpretation**: Focus on effect sizes, not just p-values
- **Replication**: Use model registry to enable replication studies

### **Publication Guidelines**

#### **Methods Section Template**
```
Statistical analysis was performed using EMUSES v[version] (github.com/chrisfoulon/emuses).
Dimensionality reduction used UMAP with n_neighbors=[X], min_dist=[Y]. 
Predictive modeling employed nested cross-validation with [Z] folds.
Effect size maps used [method] correction for multiple comparisons.
```

#### **Sharing Research Outputs**
```bash
# Prepare shareable research package
emuses package analysis/ --include-models --include-data --anonymize

# Generate research summary report  
emuses report analysis/ --format markdown --include-visualizations
```

### **Domain-Specific Applications**

#### **Neuroimaging Research**
- **Connectivity Analysis**: Use correlation heatmaps to identify network patterns
- **Lesion-Symptom Mapping**: Apply effect size maps to lesion data
- **Developmental Studies**: Track changes across age groups
- **Clinical Applications**: Biomarker discovery and validation

#### **Other Scientific Domains**
- **Genomics**: Gene expression patterns and pathway analysis
- **Social Sciences**: Behavioral patterns and demographic relationships
- **Economics**: Market analysis and economic indicator relationships  
- **Ecology**: Species distribution and environmental factor analysis

## **Troubleshooting & Support**

### **Common Issues and Solutions**

#### **Installation Problems**
```bash
# Clean installation if issues occur
pip uninstall emuses
pip cache purge
pip install --no-cache-dir git+https://github.com/chrisfoulon/emuses.git
```

#### **Memory Errors**
```bash
# Reduce memory usage
emuses full analysis/ data.csv --scores scores.csv \
  --n_jobs 1 \
  --memory_efficient \
  --max_features 5000
```

#### **Slow Performance**
```bash
# Optimize for speed
emuses full analysis/ data.csv --scores scores.csv \
  --n_neighbors 10 \
  --n_jobs -1 \
  --fast_mode
```

### **Getting Help**
- **Documentation**: Check [API Reference](API_REFERENCE.md) for detailed parameter descriptions
- **Examples**: See [examples/](examples/) directory for working code samples
- **Community**: GitHub discussions and issues for community support

</details>

<details markdown="1">
<summary>🔌 **Technical Integration & Advanced Topics**</summary>

## **API Integration**

### **FastAPI Service Deployment**

#### **Development Server**
```bash
# Start development server
emuses service --port 8000 --reload

# Access documentation at http://localhost:8000/docs
```

#### **Production Deployment**
```bash
# Production server with Gunicorn
pip install gunicorn
gunicorn emuses.foundation_fastapi_service.app:app \
  --workers 4 \
  --bind 0.0.0.0:8000 \
  --timeout 300
```

### **REST API Usage**

#### **Submit Analysis Job**
```bash
curl -X POST "http://localhost:8000/api/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "n_neighbors": 50,
      "min_dist": 0.001
    },
    "data_file": "path/to/data.csv",
    "scores_file": "path/to/scores.csv"
  }'
```

#### **Check Job Status**
```bash
curl "http://localhost:8000/api/jobs/{job_id}/status"
```

#### **Download Results**
```bash
curl "http://localhost:8000/api/jobs/{job_id}/results" -o results.zip
```

### **Python SDK Integration**

#### **Direct Pipeline Usage**
```python
from emuses import EMUSESPipeline
from emuses.config import PipelineConfig
import pandas as pd
import numpy as np

# Load your data
data = pd.read_csv('your_data.csv')
scores = pd.read_csv('your_scores.csv')

# Configure pipeline
config = PipelineConfig(
    output_folder='results/',
    n_neighbors=50,
    min_dist=0.001,
    random_state=42,
    n_jobs=8
)

# Run analysis
pipeline = EMUSESPipeline(config)
results = pipeline.run(data, scores)

# Access results
predictions = results['predictions']
models = results['models']
embeddings = results['embeddings']
```

#### **Async API Client**
```python
import asyncio
from emuses.client import EMUSESClient

async def run_analysis():
    client = EMUSESClient("http://localhost:8000")
    
    # Submit job
    job_id = await client.submit_analysis(
        data_file="data.csv",
        scores_file="scores.csv",
        config={"n_neighbors": 50}
    )
    
    # Monitor progress
    while True:
        status = await client.get_status(job_id)
        if status.completed:
            break
        await asyncio.sleep(5)
    
    # Download results
    results = await client.download_results(job_id)
    return results

results = asyncio.run(run_analysis())
```

## **Advanced Configuration**

### **Custom Pipeline Stages**

#### **Adding Custom Feature Extraction**
```python
from emuses.pipelines import PipelineStage

class CustomFeatureStage(PipelineStage):
    def run(self, context):
        # Custom feature processing
        features = self.extract_custom_features(context['input_data'])
        context['processed_features'] = features
        return context
        
    def extract_custom_features(self, data):
        # Your custom feature extraction logic
        return processed_data

# Integrate into pipeline
pipeline.add_stage('custom_features', CustomFeatureStage())
```

#### **Custom Optimization Parameters**
```python
# Define custom optimization space
custom_optim = {
    "param": {
        "model": {
            "model_type": {
                "choices": ["custom_model", "gaussian_process"]
            }
        },
        "features": {
            "custom_param": {
                "low": 0.1,
                "high": 1.0
            }
        }
    }
}

config = PipelineConfig(
    custom_optimization=custom_optim
)
```

### **Multi-User Service Configuration**

#### **Enterprise Deployment with HashiCorp Vault**
```yaml
# vault-config.yml
vault:
  address: "https://vault.company.com:8200"
  auth_method: "ldap"
  secret_path: "secret/emuses"

emuses:
  multi_user: true
  user_quotas:
    default_memory_gb: 32
    default_cpu_cores: 8
    max_jobs_per_user: 5
```

#### **User Management**
```bash
# Add user with specific quotas
emuses admin add-user researcher@company.com \
  --memory-quota 64 \
  --cpu-quota 16 \
  --password SecurePass123

# List active users and usage
emuses admin list-users --show-usage

# Monitor system resources
emuses admin system-status --detailed
```

### **Deployment Patterns**

#### **Kubernetes Deployment**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: emuses-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: emuses-api
  template:
    metadata:
      labels:
        app: emuses-api
    spec:
      containers:
      - name: emuses
        image: emuses:latest
        ports:
        - containerPort: 8000
        env:
        - name: EMUSES_CONFIG
          value: "/config/emuses.yml"
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "32Gi"
            cpu: "16"
```

#### **Docker Compose for Development**
```yaml
version: '3.8'
services:
  emuses-api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./results:/app/results
    environment:
      - PYTHONPATH=/app
      - EMUSES_LOG_LEVEL=INFO
    
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
      
  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: emuses
      POSTGRES_USER: emuses
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

</details>

---

## 🎯 **User-Specific Pathways**

### **🔬 Individual Researchers**
**Goal**: Personal analysis and method development

**Recommended Path**:
1. [Essential Workflows](#essential-workflows) → Run your first analysis
2. [Results Guide](RESULTS_GUIDE.md) → Understand your outputs  
3. [Advanced Usage](#advanced-usage) → Customize for your research
4. [Research Best Practices](#research-applications--best-practices) → Publication-ready workflows

### **🏛️ Research Labs**
**Goal**: Team collaboration and model sharing

**Recommended Path**:
1. [Essential Workflows](#essential-workflows) → Establish basic workflows
2. [Multi-User Workflows](#multi-user-and-collaboration-workflows) → Set up team environment
3. [Model Registry](#model-registry-for-reproducibility) → Enable sharing and reproduction
4. [Technical Integration](#technical-integration--advanced-topics) → API deployment

### **🌍 Scientific Community**  
**Goal**: Public sharing and benchmarking

**Recommended Path**:
1. [Research Best Practices](#research-applications--best-practices) → Ensure reproducibility
2. [Model Registry](#model-registry-for-reproducibility) → Share models publicly
3. [Publication Guidelines](#publication-guidelines) → Proper attribution
4. [Community Support](#getting-help) → Contribute to ecosystem

---

**Getting Help**:
- 📊 **Results Questions?** → [Results Guide](RESULTS_GUIDE.md)
- 🚀 **Quick Setup?** → [Quick Start](QUICK_START.md) 
- 🔧 **API Integration?** → [API Reference](API_REFERENCE.md)
- 🏛️ **Multi-User Setup?** → [Admin Guide](multi-user-service/admin-guide.md)

**Last Updated**: 2025-08-31  
**Version**: Progressive Disclosure Enhancement