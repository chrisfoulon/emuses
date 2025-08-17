# 🚀 EMUSES Quick Start Guide

**From installation to your first scientific prediction in 5 minutes.**

## Prerequisites (30 seconds)

- **Python 3.11+** installed
- **Basic command line** familiarity  
- **Your data** (or use our sample HCP dataset)

## Installation (1 minute)

```bash
# Install EMUSES
pip install git+https://github.com/chrisfoulon/emuses.git

# Verify installation
python -m emuses.cli --help
```

✅ **Success indicator**: You should see EMUSES command help

## First Analysis (3 minutes)

### Option 1: With Sample Data (Fastest)

```bash
# Run complete analysis with HCP sample data
python -m emuses.cli full my_first_analysis/ docs/examples/sample_data/hcp_input_data.csv --scores docs/examples/sample_data/hcp_labels.csv
```

### Option 2: With Your Data

```bash
# Run with your scientific data
python -m emuses.cli full output_folder/ your_brain_data.csv --scores your_cognitive_scores.csv
```

**Expected output**: Analysis runs for 1-3 minutes, creates results in `output_folder/`

## Explore Results (1 minute)

```bash
# Check what was created
ls output_folder/
# You should see: models/, visualizations/, reports/

# View your first predictive model
python -m emuses.cli models list
```

## Setup Modes (Pick Your Workflow)

### 🟢 Local Mode (Current - Perfect for Individual Research)
✅ **Already running** - No additional setup needed  
**Best for**: Personal analysis, method development, quick exploration

```bash
# Verify local mode is active
python -m emuses.cli models status
# Should show: "Mode: LOCAL"

# All models stored locally in ~/.local/share/emuses/
ls ~/.local/share/emuses/models/
```

### 🟡 Database Mode (Lab Collaboration)
**Setup for team sharing with PostgreSQL backend**

```bash
# 1. Install PostgreSQL (if not already available)
# Ubuntu/Debian: sudo apt install postgresql postgresql-contrib
# macOS: brew install postgresql

# 2. Create EMUSES database
sudo -u postgres createdb emuses_registry
sudo -u postgres createuser emuses_user --pwprompt

# 3. Set environment variables
export EMUSES_DATABASE_URL="postgresql://emuses_user:password@localhost:5432/emuses_registry"

# 4. Initialize database schema
python -m emuses.cli models init-db

# 5. Verify database mode
python -m emuses.cli models status
# Should show: "Mode: DATABASE"

# 6. Test model sharing
python -m emuses.cli models list --workspace your_lab_name
```

**Best for**: Team projects, shared models, reproducible workflows

### 🔴 Cloud Mode (Production/Community)
**Setup for production deployment with full monitoring**

```bash
# 1. Configure cloud database (PostgreSQL + Redis)
export EMUSES_DATABASE_URL="postgresql://user:pass@cloud-db:5432/emuses"
export EMUSES_REDIS_URL="redis://cloud-redis:6379/0"

# 2. Set up cloud storage (optional)
export EMUSES_STORAGE_BACKEND="s3"
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export EMUSES_S3_BUCKET="emuses-models"

# 3. Initialize cloud deployment
python -m emuses.cli models init-cloud

# 4. Start with monitoring (production)
uvicorn emuses.api.main:create_app --factory --host 0.0.0.0 --port 8000 \
  --workers 4 --log-config logging.json

# 5. Verify cloud mode
python -m emuses.cli models status
# Should show: "Mode: CLOUD"

# 6. Test community features
python -m emuses.cli models search "fMRI working memory"
python -m emuses.cli models publish my_model --public
```

**Best for**: Community sharing, large-scale analysis, production research

### 🔄 Switching Between Modes

```bash
# Switch to database mode
export EMUSES_DATABASE_URL="postgresql://localhost/emuses"
python -m emuses.cli models status  # Now shows DATABASE

# Switch back to local mode  
unset EMUSES_DATABASE_URL
python -m emuses.cli models status  # Now shows LOCAL

# Check what mode you're currently in
python -m emuses.cli models status --verbose
```

## What's Next?

### Immediate Next Steps
- **Explore your results**: Open `output_folder/` and examine predictions
- **Try model registry**: `python -m emuses.cli models --help`
- **Check API docs**: See [API Documentation](API_REFERENCE.md)

### Learning Paths

#### 📊 **For Data Analysis Focus**
1. [Model Registry Guide - Basic Usage](docs/model-registry/user_guide.md#basic-model-operations)
2. [Analysis Pipeline Documentation](docs/emuses/core_pipeline_overview.md)
3. [UMAP Stage Guide](docs/emuses/umap_stage.md)

#### 🔬 **For Research Workflows**
1. [Model Registry - Collaborative Features](docs/model-registry/user_guide.md#database-mode)
2. [Model Sharing Guide](docs/model-registry/user_guide.md)
3. [Multi-User Service Guide](docs/multi-user-service/research-workflows.md)

#### 💻 **For Integration/Development**
1. [API Documentation](API_REFERENCE.md) - Static docs, or start server for interactive docs at `/api/docs`
2. [Developer Guide](docs/model-registry/developer_guide.md)
3. [Python API Examples](docs/model-registry/api_reference.md)

## Common First Questions

### "How do I format my data?"
- **Input data**: CSV with subjects as rows, features as columns
- **Scores**: CSV with subject IDs and target variables
- **Example**: See `docs/examples/sample_data/` for HCP format

### "What analysis does EMUSES do?"
- **UMAP dimensionality reduction** for visualization
- **Predictive modeling** with multiple ML algorithms
- **Model optimization** with hyperparameter tuning
- **Results visualization** with interpretable outputs

### "How do I share models with my lab?"
```bash
# Package your model for sharing
python -m emuses.cli models export my_model

# Lab members can install it
python -m emuses.cli models install your_model.zip
```

### "Can I use this in my Python scripts?"
```python
# Yes! Full Python API available
from emuses.tools.model_registry_factory import ModelRegistryFactory

registry = ModelRegistryFactory.create_registry()
models = registry.list_models()
```

## Troubleshooting

### Installation Issues
```bash
# Update pip and try again
pip install --upgrade pip
pip install git+https://github.com/chrisfoulon/emuses.git
```

### Data Format Issues
- Ensure CSV files have headers
- Check that subject IDs match between input and scores files
- Verify no missing values in critical columns

### Performance Issues
- For large datasets, consider database mode
- Use `--n_jobs` parameter to control parallel processing
- Monitor memory usage with `--verbose` flag

## Need Help?

- **📖 Documentation**: [Model Registry Guide](docs/model-registry/user_guide.md)
- **🐛 Issues**: [GitHub Issues](https://github.com/chrisfoulon/emuses/issues)
- **💬 Questions**: [GitHub Discussions](https://github.com/chrisfoulon/emuses/discussions)
- **🔧 API Reference**: [API Documentation](API_REFERENCE.md)

---

**⚡ Quick tip**: Start with sample data to learn EMUSES, then move to your own datasets. The workflow patterns are identical!
