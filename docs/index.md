# EMUSES - Neuroimaging Analysis Platform

<div align="center">

![EMUSES Logo](https://via.placeholder.com/200x80/3f51b5/ffffff?text=EMUSES)

**A comprehensive platform for neuroimaging data analysis with machine learning, dimensionality reduction, and predictive modeling**

[![GitHub](https://img.shields.io/github/license/chrisfoulon/emuses)](https://github.com/chrisfoulon/emuses/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://python.org)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://chrisfoulon.github.io/emuses)
[![Tests](https://img.shields.io/badge/tests-2138%20passing-green)](https://github.com/chrisfoulon/emuses)

[Quick Start](QUICK_START.md){ .md-button .md-button--primary }
[User Guide](USER_GUIDE.md){ .md-button }
[API Reference](API_REFERENCE.md){ .md-button }

</div>

## Overview

EMUSES is a powerful, research-grade platform designed for comprehensive neuroimaging data analysis. It combines cutting-edge machine learning techniques with intuitive interfaces to enable researchers to extract meaningful insights from complex brain imaging datasets.

### 🎯 Key Features

<div class="grid cards" markdown>

-   :material-brain:{ .lg .middle } __Advanced Neuroimaging Analysis__

    ---

    Built specifically for neuroimaging researchers with support for multiple data formats, preprocessing pipelines, and specialized analysis methods

    [:octicons-arrow-right-24: Learn more](USER_GUIDE.md#neuroimaging-workflows)

-   :material-chart-line:{ .lg .middle } __Machine Learning Pipeline__

    ---

    Integrated ML workflows including dimensionality reduction (UMAP), clustering (HDBSCAN), and predictive modeling with automated optimization

    [:octicons-arrow-right-24: Explore ML features](USER_GUIDE.md#machine-learning)

-   :material-api:{ .lg .middle } __Flexible Interfaces__

    ---

    Choose between command-line interface for automation, Python API for integration, or REST API for web-based applications

    [:octicons-arrow-right-24: API Documentation](API_REFERENCE.md)

-   :material-database:{ .lg .middle } __Model Registry__

    ---

    Centralized model management with versioning, metadata tracking, and collaborative sharing capabilities

    [:octicons-arrow-right-24: Model Registry Guide](docs/model-registry/README.md)

</div>

## Quick Example

=== "Command Line"

    ```bash
    # Run complete analysis pipeline
    emuses full dataset.csv --scores behavioral_scores.csv --output results/

    # Start web service
    emuses service --port 8000
    ```

=== "Python API"

    ```python
    from emuses import EMUSESPipeline
    from emuses.api import create_app

    # Direct pipeline usage
    pipeline = EMUSESPipeline(config)
    results = pipeline.run()

    # Or use as FastAPI service
    app = create_app()
    ```

=== "REST API"

    ```bash
    # Submit analysis job
    curl -X POST "http://localhost:8000/api/jobs" \
         -H "Content-Type: application/json" \
         -d '{"config": {...}, "files": [...]}'

    # Check job status
    curl "http://localhost:8000/api/jobs/{job_id}/status"
    ```

## Research Applications

EMUSES has been successfully applied to various neuroimaging research domains:

- **Functional Connectivity Analysis**: Mapping brain networks and connectivity patterns
- **Lesion-Symptom Mapping**: Understanding brain-behavior relationships
- **Predictive Modeling**: Building models to predict behavioral or clinical outcomes
- **Multi-Modal Integration**: Combining structural and functional neuroimaging data
- **Longitudinal Analysis**: Tracking changes over time

!!! example "HCP Dataset Analysis"
    
    Included example using Human Connectome Project data demonstrates complete workflow from raw connectivity matrices to predictive models. See our [HCP Analysis Guide](examples/hcp_analysis.md) for details.

## Scientific Foundation

EMUSES implements state-of-the-art methods from computational neuroscience and machine learning:

- **Dimensionality Reduction**: UMAP for preserving both local and global structure
- **Clustering**: HDBSCAN for density-based clustering with noise handling  
- **Optimization**: Multi-objective optimization for heatmap generation
- **Cross-Validation**: Robust evaluation with proper statistical testing
- **Reproducibility**: Deterministic pipelines with comprehensive logging

## Community & Support

<div class="grid" markdown>

<div markdown>
**Documentation**

- [User Guide](USER_GUIDE.md) - Comprehensive tutorials and workflows
- [API Reference](API_REFERENCE.md) - Complete API documentation  
- [CLI Reference](CLI_REFERENCE.md) - Command-line interface guide
- [Migration Guide](MIGRATION_GUIDE.md) - Upgrading between versions

</div>

<div markdown>
**Development**

- [Contributing](CONTRIBUTING.md) - How to contribute to EMUSES
- [Architecture](docs/emuses/architecture.md) - Technical design overview
- [Testing](docs/test-analysis/test_analysis_summary.md) - Test coverage and quality

</div>

</div>

## Getting Started

Ready to start analyzing your neuroimaging data? Choose your path:

<div class="grid cards" markdown>

-   **New to EMUSES?**
    
    Start with our [Quick Start Guide](QUICK_START.md) for installation and your first analysis

-   **Experienced User?**
    
    Jump to the [User Guide](USER_GUIDE.md) for advanced workflows and best practices

-   **Developer?**
    
    Check out the [API Reference](API_REFERENCE.md) for integration and extension

-   **Migrating?**
    
    See our [Migration Guide](MIGRATION_GUIDE.md) for upgrading from previous versions

</div>

---

<div align="center">
    <strong>Built for the neuroimaging research community</strong><br>
    <em>Empowering discoveries through advanced computational methods</em>
</div>
