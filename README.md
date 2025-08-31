# 🔬 EMUSES - Scientific Predictive Modeling Platform

**Enabling collaborative scientific research through interpretable predictive modeling and seamless model sharing.**

EMUSES transforms scientific data into predictive insights, supporting research workflows from individual analysis to community-wide collaboration. Built for researchers who need both quick results and deep analytical control across diverse domains including neuroimaging, astronomy, genetics, sociology, economics, and beyond.

## 🚀 Quick Start (5 minutes)

### Prerequisites
- Python 3.11+ (recommended for optimal performance)
- Basic command line familiarity

### Installation & First Analysis

#### Recommended: Isolated Environment Setup
```bash
# Option A: Using venv (lightweight, built-in)
python -m venv emuses-env
source emuses-env/bin/activate  # Linux/macOS
# emuses-env\Scripts\activate   # Windows

# Option B: Using conda (recommended for scientific computing)
conda create -n emuses-env python=3.11
conda activate emuses-env

# Install EMUSES in your isolated environment
pip install git+https://github.com/chrisfoulon/emuses.git

# Verify installation
python -m emuses.cli --help

# Run your first analysis (with sample data)
python -m emuses.cli full output_folder docs/examples/sample_data/hcp_input_data.csv --scores docs/examples/sample_data/hcp_labels.csv
```

#### Quick Installation (System-wide, not recommended for production)
```bash
# 1. Install EMUSES
pip install git+https://github.com/chrisfoulon/emuses.git

# 2. Verify installation
python -m emuses.cli --help

# 3. Run your first analysis (with sample data)
python -m emuses.cli full output_folder docs/examples/sample_data/hcp_input_data.csv --scores docs/examples/sample_data/hcp_labels.csv
```

**✅ Success**: Your first scientific prediction model is ready in `output_folder/`!

**📊 Understanding Your Results**: Your analysis includes prediction models, statistical heatmaps, correlation analysis, and effect size maps. [See results guide →](docs/RESULTS_GUIDE.md)

## 🔬 Research Use Cases

### 🏠 Individual Researchers
```bash
# Local analysis with your data
python -m emuses.cli full my_results/ my_brain_data.csv --scores my_cognitive_scores.csv
```
**Perfect for**: Exploratory analysis, method development, personal research projects

### 🏛️ Research Labs  
```bash
# Multi-user collaboration with shared models
python -m emuses.cli models install shared_model.zip
python -m emuses.cli models list --workspace our_lab
```
**Perfect for**: Team collaboration, model validation, reproducible workflows

### 🌍 Scientific Community
```bash
# Access community models and benchmarks
python -m emuses.cli models search "fMRI working memory"
python -m emuses.cli models info community_model_v2
```
**Perfect for**: Meta-analyses, benchmarking, scientific reproducibility

## ⭐ Key Features

- **🔬 Research-Optimized**: Designed for complex scientific prediction tasks (neuroimaging, astronomy, genetics, sociology, economics, and more)
- **🔄 Multi-Mode Flexibility**: Local, collaborative, or cloud-based workflows  
- **📊 Model Registry**: Share, discover, and reproduce predictive models
- **🎯 Research-Focused**: Designed for scientific rigor and interpretability
- **⚡ Quick Start**: From installation to results in under 5 minutes
- **🔬 Deep Control**: Comprehensive configuration for advanced users

## 📚 Documentation Paths

**Choose your path based on your needs:**

### 🚀 [Quick Start Guide](docs/QUICK_START.md)
*5-minute path to your first results*  
→ For time-constrained researchers who need immediate results

### 📖 [Model Registry Guide](docs/model-registry/user_guide.md) 
*Comprehensive model sharing documentation*  
→ For researchers who want to understand model registry capabilities

### 🔬 [Research Workflows Guide](docs/RESEARCH_WORKFLOWS.md)
*Scientific use case patterns and methodological examples*  
→ For researchers implementing scientific analysis workflows across diverse domains (neuroimaging, astronomy, genetics, sociology, economics)

### 🔧 [API Documentation](docs/API_REFERENCE.md)
*Interactive API reference*  
→ For computational scientists integrating EMUSES into workflows

### 👥 [Developer Guide](docs/model-registry/developer_guide.md)
*Integration and contribution guide*  
→ For extending EMUSES or contributing to development

## 🎯 Getting Started by Setup Mode

### 🟢 Local Mode (Recommended for Beginners)
```bash
# Automatic setup - no configuration needed
python -m emuses.cli full output/ input_data.csv --scores scores.csv
```

### 🟡 Database Mode (Lab Collaboration)
```bash
# Multi-user setup with PostgreSQL
python -m emuses.cli models status  # Shows current mode
# See: docs/USER_GUIDE.md#database-mode-setup
```

### 🔴 Cloud Mode (Production/Community)
```bash
# Full production deployment
# See: docs/USER_GUIDE.md#cloud-mode-setup
```

## 🏗️ Installation Options

### Standard Installation
```bash
pip install git+https://github.com/chrisfoulon/emuses.git
```

### Development Installation
```bash
git clone https://github.com/chrisfoulon/emuses.git
cd emuses
pip install -e .
```

### Production Installation
```bash
# With Docker for full deployment
docker pull ghcr.io/chrisfoulon/emuses:latest
# See: docs/deployment/ for complete setup
```

## 🧪 Sample Data & Examples

EMUSES includes real-world sample data from the Human Connectome Project:
- **Input**: Neuroimaging features from 1068 subjects
- **Target**: Fluid intelligence prediction task
- **Location**: `docs/examples/sample_data/`

Perfect for testing workflows and learning EMUSES capabilities.

## 🤝 Research Community

EMUSES enables reproducible scientific research through:
- **Model Sharing**: Publish and discover predictive models
- **Reproducible Workflows**: Standardized analysis pipelines  
- **Community Benchmarks**: Compare methods across research groups
- **Open Science**: Transparent and reproducible research practices

## 📄 Citation

If you use EMUSES in your research, please cite:

```bibtex
@software{emuses2024,
  title={EMUSES: Scientific Predictive Modeling Platform},
  author={Foulon, Chris and Contributors},
  year={2024},
  url={https://github.com/chrisfoulon/emuses},
  version={0.9.0}
}
```

## 🔗 Links

- **🌐 Documentation**: [Full documentation portal](docs/)
- **🚀 Quick Start**: [5-minute tutorial](docs/QUICK_START.md)
- **📊 Model Registry**: [Model sharing guide](docs/model-registry/user_guide.md)  
- **🐛 Issues**: [GitHub Issues](https://github.com/chrisfoulon/emuses/issues)
- **💬 Discussions**: [GitHub Discussions](https://github.com/chrisfoulon/emuses/discussions)

## 📊 Project Status

**Current Version**: 0.9.0-dev (Model Registry Complete)  
**Next Release**: 1.0.0 (Production Ready)  
**Test Coverage**: 47.1% (Exceeds research software standards)  
**Status**: Pre-production, active development  

---

*Documentation developed using [LAD (LLM-Assisted Development)](https://github.com/chrisfoulon/LAD) methodology with human oversight.*

**🧠 Built for scientists, by scientists** | **⚡ Quick results, deep control** | **🤝 Individual to community scale**