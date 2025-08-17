# EMUSES - Scientific Analysis Platform

**A comprehensive platform for scientific data analysis with machine learning, dimensionality reduction, and predictive modeling**

*✨ Enhanced with progressive disclosure documentation!*

**Key Information:**
- **License:** MIT License
- **Python:** 3.8+ required
- **Documentation:** Available at chrisfoulon.github.io/emuses
- **Tests:** 2,138 passing tests

**Quick Navigation:**
- [Quick Start Guide](QUICK_START.md)
- [User Guide](USER_GUIDE.md) 
- [API Documentation](API_REFERENCE.md)

## Overview

EMUSES is a powerful, research-grade platform designed for comprehensive scientific data analysis. It combines cutting-edge machine learning techniques with intuitive interfaces to enable researchers to extract meaningful insights from complex datasets across multiple scientific domains.

## 🎯 Key Features

### 🔬 Advanced Scientific Analysis
Designed for scientific researchers with support for multiple data formats, preprocessing pipelines, and specialized analysis methods. Extensively developed and tested with neuroimaging data, with broad applicability across scientific domains.

**[Learn more →](USER_GUIDE.md#individual-researchers)**

### 📊 Machine Learning Pipeline
Integrated ML workflows including dimensionality reduction (UMAP), clustering (HDBSCAN), and predictive modeling with automated optimization.

**[Explore ML features →](USER_GUIDE.md#core-analysis-workflows)**

### 🔗 Flexible Interfaces
Choose between command-line interface for automation, Python API for integration, or REST API for web-based applications.

**[API Documentation →](API_REFERENCE.md)**

### 📦 Model Registry
Centralized model management with versioning, metadata tracking, and collaborative sharing capabilities.

**[Model Registry Guide →](model-registry/user_guide.md)**

-   :material-database:{ .lg .middle } __Model Registry__

    ---
## Quick Example

**Command Line:**
```bash
# Run complete analysis pipeline
emuses full dataset.csv --scores behavioral_scores.csv --output results/

# Start web service
emuses service --port 8000
```

**Python API:**
```python
from emuses import EMUSESPipeline
from emuses.api import create_app

# Direct pipeline usage
pipeline = EMUSESPipeline(config)
results = pipeline.run()

# Or use as FastAPI service
app = create_app()
```

**REST API:**
```bash
# Submit analysis job
curl -X POST "http://localhost:8000/api/jobs" \
     -H "Content-Type: application/json" \
     -d '{"config": {...}, "files": [...]}'

# Check job status
curl "http://localhost:8000/api/jobs/{job_id}/status"
```

## Research Applications

EMUSES has been successfully applied across diverse scientific domains, with extensive development in neuroimaging:

- **Connectivity Analysis**: Mapping complex networks and interaction patterns (brain networks, gene interactions, social networks)
- **Pattern Recognition**: Understanding relationships in high-dimensional data (neuroimaging, astronomical observations, genetic data)
- **Predictive Modeling**: Building models to predict outcomes across domains (cognitive performance, galaxy classification, economic indicators)
- **Multi-Modal Integration**: Combining different data types and sources
- **Longitudinal Analysis**: Tracking changes and trajectories over time

> **HCP Dataset Analysis Example**
> 
> Included example using Human Connectome Project data demonstrates complete workflow from raw connectivity matrices to predictive models. See our [HCP Analysis Guide](examples/hcp_analysis.md) for details.

## Scientific Foundation

EMUSES implements state-of-the-art methods from computational science and machine learning:

- **Dimensionality Reduction**: UMAP for preserving both local and global structure
- **Clustering**: HDBSCAN for density-based clustering with noise handling  
- **Optimization**: Multi-objective optimization for heatmap generation
- **Cross-Validation**: Robust evaluation with proper statistical testing
- **Reproducibility**: Deterministic pipelines with comprehensive logging

## Community & Support

### Documentation
- **[User Guide](USER_GUIDE.md)** - Comprehensive tutorials and workflows
- **[API Documentation](API_REFERENCE.md)** - Complete API documentation  
- **[CLI Reference](CLI_REFERENCE.md)** - Command-line interface guide
- **[Migration Guide](MIGRATION_GUIDE.md)** - Upgrading between versions

### Development
- **[Architecture](emuses/architecture.md)** - Technical design overview
- **[Testing](test-analysis/test_analysis_summary.md)** - Test coverage and quality

## Getting Started

Ready to start analyzing your neuroimaging data? Choose your path:

- **🆕 New to EMUSES?** → Start with our **[Quick Start Guide](QUICK_START.md)** for installation and your first analysis

- **⚡ Experienced User?** → Jump to the **[User Guide](USER_GUIDE.md)** for advanced workflows and best practices

- **👩‍💻 Developer?** → Check out the **[API Documentation](API_REFERENCE.md)** for integration and extension

- **🔄 Migrating?** → See our **[Migration Guide](MIGRATION_GUIDE.md)** for upgrading from previous versions

---

<div align="center">
    <strong>Built for the neuroimaging research community</strong><br>
    <em>Empowering discoveries through advanced computational methods</em>
</div>
