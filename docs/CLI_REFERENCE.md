# 🛠️ EMUSES CLI Complete Reference

**Comprehensive command-line interface reference for EMUSES neuroimaging analysis platform**

This reference covers all 33+ CLI commands with detailed parameters, examples, and use cases for neuroimaging research workflows.

## 📋 **Command Overview**

### **Quick Command Index**
| Category | Commands | Description |
|----------|----------|-------------|
| **Pipeline** | `full`, `umap`, `heatmap`, `inference` | Core analysis workflows |
| **Research** | `verify`, `info`, `cite`, `trace`, `reproduce`, `diff`, `compare`, `rerun` | Scientific reproducibility tools |
| **Registry** | `models *` (10 commands) | Model management and sharing |
| **Workspace** | `workspace *` (3 commands) | Team collaboration |
| **Admin** | `admin *` (6 commands) | System administration |
| **Utility** | `install-completion` | Shell integration |

---

## 🔬 **Pipeline Commands**

### `emuses full` - Complete Pipeline Analysis

Run the complete EMUSES analysis pipeline including UMAP, heatmap generation, and predictive modeling.

#### Syntax
```bash
emuses full OUTPUT_FOLDER INPUT_DATASET [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `OUTPUT_FOLDER` | path | Yes | Directory for analysis results |
| `INPUT_DATASET` | path | Yes | CSV file with neuroimaging features |
| `--scores` | path | Yes | CSV file with cognitive/behavioral scores |
| `--label_dataset` | path | No | CSV file with additional labels |
| `--n_neighbors` | int | No | UMAP n_neighbors parameter (default: 15) |
| `--min_dist` | float | No | UMAP min_dist parameter (default: 0.1) |
| `--n_jobs` | int | No | Number of parallel jobs (default: -1) |
| `--verbose` | flag | No | Enable detailed logging |
| `--config` | path | No | Custom configuration file |

#### Examples

**Basic Analysis with HCP Data**
```bash
emuses full my_analysis/ docs/examples/sample_data/hcp_input_data.csv \
  --scores docs/examples/sample_data/hcp_labels.csv
```
*Expected runtime: 3-5 minutes for HCP sample data*
*Output: UMAP embeddings, heatmaps, trained models in `my_analysis/`*

**Custom UMAP Parameters**
```bash
emuses full custom_analysis/ brain_features.csv \
  --scores cognitive_scores.csv \
  --n_neighbors 30 \
  --min_dist 0.05 \
  --verbose
```

**High-Performance Analysis**
```bash
emuses full fast_analysis/ large_dataset.csv \
  --scores scores.csv \
  --n_jobs 8
```

#### Use Cases
- **Initial Exploration**: Quick overview of brain-behavior relationships
- **Publication Analysis**: Complete analysis for research papers
- **Method Comparison**: Baseline analysis for comparing approaches

#### Output Structure
```
OUTPUT_FOLDER/
├── umap_embeddings.npy          # UMAP 2D coordinates
├── umap_model.pkl               # Trained UMAP model
├── heatmap_data.npy             # Correlation heatmap data
├── heatmap_visualization.png    # Heatmap visualization
├── models/                      # Trained predictive models
│   ├── model_manifest.json     # Model metadata
│   └── trained_model.pkl       # Serialized model
├── reports/                     # Analysis reports
│   ├── analysis_summary.md     # Human-readable summary
│   └── performance_metrics.json # Model performance
└── logs/                        # Execution logs
    └── pipeline_execution.log
```

#### Related Commands
- [`emuses umap`](#emuses-umap) - UMAP stage only
- [`emuses models install`](#emuses-models-install) - Register results
- [`emuses reproduce`](#emuses-reproduce) - Generate reproduction guide

---

### `emuses umap` - UMAP Training and Embeddings

Train UMAP dimensionality reduction model and generate 2D embeddings for visualization and analysis.

#### Syntax
```bash
emuses umap OUTPUT_FOLDER INPUT_DATASET [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `OUTPUT_FOLDER` | path | Yes | Directory for UMAP outputs |
| `INPUT_DATASET` | path | Yes | CSV file with high-dimensional features |
| `--n_neighbors` | int | No | Number of neighbors (default: 15) |
| `--min_dist` | float | No | Minimum distance (default: 0.1) |
| `--n_components` | int | No | Output dimensions (default: 2) |
| `--metric` | string | No | Distance metric (default: 'euclidean') |
| `--random_state` | int | No | Random seed for reproducibility |
| `--verbose` | flag | No | Enable progress reporting |

#### Examples

**Basic UMAP with Default Parameters**
```bash
emuses umap umap_results/ brain_connectivity.csv
```

**High-Resolution UMAP for Publication**
```bash
emuses umap publication_umap/ connectivity_matrix.csv \
  --n_neighbors 50 \
  --min_dist 0.01 \
  --random_state 42
```

**3D UMAP for Interactive Visualization**
```bash
emuses umap 3d_embedding/ features.csv \
  --n_components 3 \
  --n_neighbors 20
```

#### Use Cases
- **Data Exploration**: Visualize high-dimensional neuroimaging patterns
- **Quality Control**: Identify outliers and data clustering
- **Preprocessing**: Dimensionality reduction for downstream analysis

#### Related Commands
- [`emuses full`](#emuses-full) - Complete pipeline including UMAP
- [`emuses heatmap`](#emuses-heatmap) - Use UMAP embeddings for heatmaps

---

### `emuses heatmap` - Heatmap Generation

Generate correlation heatmaps showing brain-behavior relationships in UMAP embedding space.

#### Syntax
```bash
emuses heatmap OUTPUT_FOLDER EMBEDDINGS [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `OUTPUT_FOLDER` | path | Yes | Directory for heatmap outputs |
| `EMBEDDINGS` | path | Yes | UMAP embeddings (.npy file) |
| `--scores` | path | Yes | Behavioral/cognitive scores CSV |
| `--stat_function` | string | No | Statistical function (default: 'correlation') |
| `--grid_resolution` | int | No | Heatmap resolution (default: 100) |
| `--colormap` | string | No | Matplotlib colormap (default: 'viridis') |
| `--threshold` | float | No | Significance threshold |

#### Examples

**Basic Correlation Heatmap**
```bash
emuses heatmap heatmap_output/ umap_embeddings.npy \
  --scores cognitive_scores.csv
```

**High-Resolution Publication Heatmap**
```bash
emuses heatmap publication_heatmap/ embeddings.npy \
  --scores scores.csv \
  --grid_resolution 200 \
  --colormap 'RdBu_r' \
  --threshold 0.01
```

#### Use Cases
- **Brain-Behavior Mapping**: Visualize cognitive-neural relationships
- **Hypothesis Generation**: Identify regions of interest
- **Results Presentation**: Publication-quality visualizations

---

### `emuses inference` - Model Inference

Run predictions on new data using trained EMUSES models.

#### Syntax
```bash
emuses inference MODEL_PATH DATA_PATH [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `MODEL_PATH` | path | Yes | Path to trained model directory |
| `DATA_PATH` | path | Yes | New data for prediction |
| `--output_path` | path | No | Output directory for results |
| `--validation_mode` | flag | No | Enable validation with known labels |
| `--output_format` | string | No | Output format: 'csv', 'json', 'npy' |
| `--verify_integrity` | flag | No | Verify model integrity before inference |
| `--batch_size` | int | No | Batch size for large datasets |

#### Examples

**Basic Inference**
```bash
emuses inference models/brain_classifier/ new_subjects.csv
```

**Validation Mode with Known Labels**
```bash
emuses inference models/my_model/ test_data.csv \
  --validation_mode \
  --output_format json
```

**Large Dataset Inference**
```bash
emuses inference models/production_model/ large_cohort.csv \
  --batch_size 32 \
  --output_path inference_results/
```

#### Use Cases
- **New Subject Prediction**: Apply trained models to new participants
- **Model Validation**: Test model performance on held-out data
- **Clinical Application**: Use research models for clinical prediction

---

## 🔬 **Research Utility Commands**

### `emuses verify` - Model Integrity Verification

Verify the integrity and completeness of trained models using manifest checksums.

#### Syntax
```bash
emuses verify MODEL_PATH [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `MODEL_PATH` | path | Yes | Path to model directory |
| `--strict` | flag | No | Enable strict verification mode |
| `--fix` | flag | No | Attempt to fix minor issues |
| `--report` | path | No | Save verification report |

#### Examples

**Basic Model Verification**
```bash
emuses verify models/brain_classifier/
```
*Output: ✅ Model integrity verified OR ❌ Issues found*

**Strict Verification with Report**
```bash
emuses verify models/published_model/ \
  --strict \
  --report verification_report.json
```

**Verification with Auto-Fix**
```bash
emuses verify models/damaged_model/ --fix
```

#### Use Cases
- **Quality Assurance**: Ensure model completeness before sharing
- **Troubleshooting**: Diagnose model corruption issues
- **Compliance**: Verify models meet publication standards

#### Verification Checks
- ✅ Model manifest presence and validity
- ✅ File checksum verification
- ✅ Required metadata completeness
- ✅ Model format compatibility
- ✅ Dependency version compatibility

---

### `emuses info` - Model Information and Metadata

Display comprehensive information about trained models including metadata, performance, and provenance.

#### Syntax
```bash
emuses info MODEL_PATH [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `MODEL_PATH` | path | Yes | Path to model directory |
| `--format` | string | No | Output format: 'text', 'json', 'yaml' |
| `--detailed` | flag | No | Include detailed technical information |
| `--performance` | flag | No | Show performance metrics |
| `--provenance` | flag | No | Show creation and modification history |

#### Examples

**Basic Model Information**
```bash
emuses info models/brain_classifier/
```

**Detailed JSON Output**
```bash
emuses info models/my_model/ \
  --format json \
  --detailed \
  --performance > model_info.json
```

**Provenance Tracking**
```bash
emuses info models/published_model/ --provenance
```

#### Sample Output
```
Model Information: brain_classifier_v1.2
=====================================
Created: 2024-08-16 14:30:15 UTC
EMUSES Version: 0.9.0
Data: HCP_motor_task (n=1068)
Performance: R² = 0.847, RMSE = 0.23

Training Parameters:
- UMAP neighbors: 15
- Min distance: 0.1
- Model type: Ridge Regression
- Cross-validation: 5-fold

Files:
✅ umap_model.pkl (2.3 MB)
✅ trained_model.pkl (0.8 MB) 
✅ model_manifest.json (verified)

Dependencies:
- Python 3.11.0
- scikit-learn 1.3.0
- umap-learn 0.5.3
```

#### Use Cases
- **Model Selection**: Compare available models
- **Reproducibility**: Understand model creation parameters
- **Documentation**: Generate model descriptions for papers

---

### `emuses cite` - Publication Citation Generation

Generate properly formatted citations for models, including software versions and data sources.

#### Syntax
```bash
emuses cite MODEL_PATH [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `MODEL_PATH` | path | Yes | Path to model directory |
| `--style` | string | No | Citation style: 'apa', 'mla', 'bibtex', 'nature' |
| `--include_data` | flag | No | Include data source citations |
| `--include_software` | flag | No | Include software dependency citations |
| `--output` | path | No | Save citation to file |

#### Examples

**BibTeX Citation**
```bash
emuses cite models/brain_classifier/ --style bibtex
```

**Complete Citation with Dependencies**
```bash
emuses cite models/published_model/ \
  --style apa \
  --include_data \
  --include_software \
  --output citations.txt
```

#### Sample Output (BibTeX)
```bibtex
@misc{brain_classifier_v1.2,
  title={Brain Classifier Model v1.2},
  author={Researcher, A. and Collaborator, B.},
  year={2024},
  note={EMUSES v0.9.0, trained on HCP motor task data},
  url={https://github.com/lab/models/brain_classifier_v1.2},
  doi={10.5281/zenodo.xxxxxx}
}

@article{hcp_reference,
  title={The WU-Minn Human Connectome Project},
  author={Van Essen, David C and others},
  journal={NeuroImage},
  volume={80},
  pages={62--79},
  year={2013}
}
```

#### Use Cases
- **Paper Writing**: Generate citations for methods sections
- **Reproducibility**: Proper attribution of models and data
- **Compliance**: Meet journal citation requirements

---

### `emuses trace` - Complete Model Provenance

Export complete provenance information including data lineage, processing steps, and software environment.

#### Syntax
```bash
emuses trace MODEL_PATH [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `MODEL_PATH` | path | Yes | Path to model directory |
| `--format` | string | No | Output format: 'json', 'yaml', 'rdf' |
| `--include_environment` | flag | No | Include complete software environment |
| `--include_data_lineage` | flag | No | Include data processing history |
| `--output` | path | No | Save provenance to file |

#### Examples

**Basic Provenance Export**
```bash
emuses trace models/brain_classifier/
```

**Complete Provenance with Environment**
```bash
emuses trace models/production_model/ \
  --format json \
  --include_environment \
  --include_data_lineage \
  --output model_provenance.json
```

#### Use Cases
- **Regulatory Compliance**: Complete audit trail
- **Scientific Reproducibility**: Full experimental record
- **Quality Assurance**: Track all processing steps

---

### `emuses reproduce` - Reproduction Guide Generation

Generate comprehensive guides for exactly reproducing model training and results.

#### Syntax
```bash
emuses reproduce MODEL_PATH [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `MODEL_PATH` | path | Yes | Path to model directory |
| `--output` | path | No | Output file path (default: model_dir/reproduction_guide.md) |
| `--include_environment` | flag | No | Include environment setup instructions |
| `--include_data_prep` | flag | No | Include data preparation steps |
| `--format` | string | No | Output format: 'markdown', 'html', 'pdf' |

#### Examples

**Basic Reproduction Guide**
```bash
emuses reproduce models/brain_classifier/
```

**Complete Reproduction with Environment**
```bash
emuses reproduce models/published_model/ \
  --include_environment \
  --include_data_prep \
  --output reproduction_guide.md
```

#### Sample Output
```markdown
# Model Reproduction Guide: brain_classifier_v1.2

## Environment Setup
### Required Software
- Python 3.11.0
- EMUSES 0.9.0
- Dependencies: [see requirements.txt]

### Installation Commands
```bash
pip install emuses==0.9.0
# Additional setup steps...
```

## Data Preparation
### Required Data
- HCP motor task dataset (1068 subjects)
- Cognitive scores: fluid intelligence

### Preprocessing Steps
1. Load raw connectivity matrices
2. Apply motion correction
3. Extract region-wise features

## Model Training
### Exact Command
```bash
emuses full brain_classifier_reproduction/ hcp_data.csv \
  --scores fluid_intelligence.csv \
  --n_neighbors 15 \
  --min_dist 0.1 \
  --random_state 42
```

## Verification
Expected outputs and checksums for verification
```

#### Use Cases
- **Research Reproducibility**: Enable exact replication
- **Method Sharing**: Help others use your approaches
- **Quality Control**: Verify reproduction procedures

---

### `emuses diff` - Model Modification Detection

Check for modifications since model creation and identify what has changed.

#### Syntax
```bash
emuses diff MODEL_PATH [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `MODEL_PATH` | path | Yes | Path to model directory |
| `--detailed` | flag | No | Show detailed change information |
| `--ignore_timestamps` | flag | No | Ignore timestamp-only changes |

#### Examples

**Basic Change Detection**
```bash
emuses diff models/brain_classifier/
```

**Detailed Change Analysis**
```bash
emuses diff models/modified_model/ --detailed
```

#### Use Cases
- **Quality Control**: Detect unauthorized modifications
- **Version Management**: Track model changes
- **Debugging**: Identify when models were altered

---

### `emuses compare` - Model Version Comparison

Compare two model versions to identify differences in parameters, performance, and structure.

#### Syntax
```bash
emuses compare MODEL1_PATH MODEL2_PATH [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `MODEL1_PATH` | path | Yes | Path to first model |
| `MODEL2_PATH` | path | Yes | Path to second model |
| `--output` | path | No | Save comparison report |
| `--detailed` | flag | No | Include detailed technical comparison |

#### Examples

**Basic Model Comparison**
```bash
emuses compare models/v1.0/ models/v1.1/
```

**Detailed Comparison with Report**
```bash
emuses compare models/baseline/ models/optimized/ \
  --detailed \
  --output comparison_report.md
```

#### Use Cases
- **Model Development**: Track improvements between versions
- **Method Comparison**: Compare different approaches
- **Quality Assurance**: Verify model updates

---

### `emuses rerun` - Command Re-execution

Rerun previously executed commands from their output folders, maintaining exact parameters.

#### Syntax
```bash
emuses rerun OUTPUT_FOLDER [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `OUTPUT_FOLDER` | path | Yes | Previous analysis output directory |
| `--force` | flag | No | Overwrite existing results |
| `--update_data` | flag | No | Use updated input data if available |

#### Examples

**Rerun Previous Analysis**
```bash
emuses rerun my_previous_analysis/
```

**Force Rerun with New Data**
```bash
emuses rerun old_analysis/ --force --update_data
```

#### Use Cases
- **Result Verification**: Confirm previous results
- **Parameter Recovery**: Rerun with same settings
- **Batch Processing**: Rerun multiple analyses

---

## 🗂️ **Model Registry Commands**

### `emuses models install` - Install Models

Install trained models into the EMUSES model registry for easy access and sharing.

#### Syntax
```bash
emuses models install SOURCE [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `SOURCE` | path | Yes | Model directory or .zip file |
| `--name` | string | No | Custom model name |
| `--registry` | path | No | Custom registry location |
| `--force` | flag | No | Overwrite existing model |
| `--verify` | flag | No | Verify model integrity after installation |

#### Examples

**Install from Directory**
```bash
emuses models install trained_models/brain_classifier/
```

**Install from ZIP with Custom Name**
```bash
emuses models install shared_model.zip \
  --name "team_brain_classifier_v2" \
  --verify
```

**Install to Custom Registry**
```bash
emuses models install model.zip \
  --registry /shared/lab_models/ \
  --force
```

#### Use Cases
- **Model Sharing**: Make models available to team
- **Model Organization**: Centralized model management
- **Version Control**: Track model versions

---

### `emuses models list` - List Available Models

Display models available in the registry with filtering and sorting options.

#### Syntax
```bash
emuses models list [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--registry` | path | No | Custom registry location |
| `--format` | string | No | Output format: 'table', 'json', 'csv' |
| `--filter` | string | No | Filter by name pattern |
| `--sort` | string | No | Sort by: 'name', 'date', 'size' |
| `--workspace` | string | No | Filter by workspace (multi-user mode) |

#### Examples

**Basic Model Listing**
```bash
emuses models list
```

**Filtered and Sorted**
```bash
emuses models list \
  --filter "*brain*" \
  --sort date \
  --format json
```

**Workspace-Specific (Multi-User)**
```bash
emuses models list --workspace neurology_lab
```

#### Sample Output
```
Available Models
================
Name                    Size    Created     Performance
brain_classifier_v1.2   3.1MB   2024-08-15  R²=0.847
motor_task_predictor    2.8MB   2024-08-14  R²=0.923
working_memory_model    4.2MB   2024-08-13  R²=0.756

Total: 3 models, 10.1MB
```

---

### `emuses models search` - Search Models

Search for models by name, description, or metadata with flexible filtering options.

#### Syntax
```bash
emuses models search QUERY [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `QUERY` | string | Yes | Search query (supports wildcards) |
| `--registry` | path | No | Custom registry location |
| `--format` | string | No | Output format: 'table', 'json', 'csv' |
| `--limit` | int | No | Maximum results to return |
| `--sort` | string | No | Sort by: 'relevance', 'date', 'name' |

#### Examples

**Basic Search**
```bash
emuses models search "brain"
```

**Advanced Search with Wildcards**
```bash
emuses models search "*motor*task*" --limit 10
```

**Search with JSON Output**
```bash
emuses models search "classifier" \
  --format json \
  --sort date
```

#### Use Cases
- **Model Discovery**: Find relevant models for research
- **Repository Browsing**: Explore available models
- **Metadata Search**: Find models with specific characteristics

---

### `emuses models status` - Registry Status

Display overall registry status, statistics, and health information.

#### Syntax
```bash
emuses models status [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--registry` | path | No | Custom registry location |
| `--detailed` | flag | No | Show detailed status information |
| `--format` | string | No | Output format: 'text', 'json' |

#### Examples

**Basic Registry Status**
```bash
emuses models status
```

**Detailed Status Information**
```bash
emuses models status --detailed --format json
```

#### Sample Output
```
Registry Status
===============
Mode: LOCAL
Location: ~/.local/share/emuses/models
Models: 15 installed
Total Size: 47.3 MB
Last Updated: 2024-08-16 14:30:15

Health: ✅ Healthy
- All models verified
- No orphaned files
- Storage within limits
```

---

### `emuses models remove` - Remove Models

Remove models from the registry with safety checks and backup options.

#### Syntax
```bash
emuses models remove MODEL_NAME [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `MODEL_NAME` | string | Yes | Name of model to remove |
| `--force` | flag | No | Skip confirmation prompts |
| `--backup` | flag | No | Create backup before removal |
| `--registry` | path | No | Custom registry location |

#### Examples

**Safe Model Removal**
```bash
emuses models remove old_model_v1
```

**Force Removal with Backup**
```bash
emuses models remove corrupted_model \
  --force \
  --backup
```

#### Use Cases
- **Cleanup**: Remove outdated or failed models
- **Space Management**: Free up storage space
- **Organization**: Maintain clean model registry

---

### `emuses models cleanup` - Registry Cleanup

Clean up orphaned files, temporary data, and corrupted model entries.

#### Syntax
```bash
emuses models cleanup [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--dry_run` | flag | No | Preview cleanup without making changes |
| `--registry` | path | No | Custom registry location |
| `--aggressive` | flag | No | Remove questionable files |
| `--backup` | flag | No | Backup before cleanup |

#### Examples

**Preview Cleanup (Safe)**
```bash
emuses models cleanup --dry_run
```

**Thorough Cleanup with Backup**
```bash
emuses models cleanup --aggressive --backup
```

#### Use Cases
- **Maintenance**: Regular registry maintenance
- **Recovery**: Fix corrupted registry state
- **Storage Optimization**: Remove unnecessary files

---

### `emuses models api-info` - Database Mode Information

Show information about database mode configuration and API usage.

#### Syntax
```bash
emuses models api-info [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--format` | string | No | Output format: 'text', 'json' |
| `--test_connection` | flag | No | Test database connectivity |

#### Examples

**Basic API Information**
```bash
emuses models api-info
```

**Test Database Connection**
```bash
emuses models api-info --test_connection
```

#### Sample Output
```
Database Mode Information
========================
Mode: DATABASE
Database URL: postgresql://localhost:5432/emuses
API Base URL: http://localhost:8000/api
Connection: ✅ Active

Available Endpoints:
- GET /api/v1/models - List models
- POST /api/v1/models - Upload model
- GET /api/v1/health - Health check

Authentication: Required for write operations
```

---

### `emuses models stats` - Detailed Registry Statistics

Show comprehensive statistics about registry usage, performance, and trends.

#### Syntax
```bash
emuses models stats [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--registry` | path | No | Custom registry location |
| `--format` | string | No | Output format: 'text', 'json', 'csv' |
| `--period` | string | No | Time period: 'day', 'week', 'month', 'all' |

#### Examples

**Basic Statistics**
```bash
emuses models stats
```

**Monthly Statistics in JSON**
```bash
emuses models stats --period month --format json
```

#### Sample Output
```
Registry Statistics
==================
Total Models: 15
Total Size: 47.3 MB
Average Model Size: 3.2 MB

Model Types:
- Classification: 8 models
- Regression: 5 models  
- Clustering: 2 models

Usage (Last 30 Days):
- Models Installed: 3
- Models Accessed: 47 times
- Most Popular: brain_classifier_v2 (12 uses)

Performance:
- Average Install Time: 2.3s
- Average Search Time: 0.1s
```

---

### `emuses models mode-info` - Registry Mode Configuration

Display detailed information about current registry mode and configuration.

#### Syntax
```bash
emuses models mode-info [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--format` | string | No | Output format: 'text', 'json' |
| `--check_requirements` | flag | No | Verify mode requirements |

#### Examples

**Basic Mode Information**
```bash
emuses models mode-info
```

**Verify Mode Requirements**
```bash
emuses models mode-info --check_requirements
```

#### Sample Output
```
Registry Mode Configuration
===========================
Current Mode: LOCAL
Auto-Detected: Yes
Available Modes: LOCAL, DATABASE, CLOUD

LOCAL Mode Configuration:
- Registry Path: ~/.local/share/emuses/models
- Storage Limit: None
- Multi-User: No
- Network Required: No

Requirements Check: ✅ All satisfied
- Python 3.11+: ✅ Found 3.11.0
- Disk Space: ✅ 15.2 GB available
- Permissions: ✅ Read/Write access
```

---

### `emuses models storage` - Storage Management

Show storage usage, manage thresholds, and provide cleanup recommendations.

#### Syntax
```bash
emuses models storage [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--registry` | path | No | Custom registry location |
| `--detailed` | flag | No | Show per-model storage breakdown |
| `--suggest_cleanup` | flag | No | Suggest cleanup actions |
| `--format` | string | No | Output format: 'text', 'json' |

#### Examples

**Basic Storage Information**
```bash
emuses models storage
```

**Detailed Storage with Cleanup Suggestions**
```bash
emuses models storage --detailed --suggest_cleanup
```

#### Sample Output
```
Storage Information
==================
Registry Location: ~/.local/share/emuses/models
Total Used: 47.3 MB
Available: 15.2 GB
Models: 15

Largest Models:
1. working_memory_complex_v3: 8.2 MB
2. brain_connectivity_atlas: 6.7 MB
3. motor_cortex_classifier: 4.9 MB

Cleanup Suggestions:
⚠️  3 models haven't been used in 90+ days (12.1 MB)
💡 2 temporary files can be removed (0.3 MB)
✅ No immediate action needed
```

---

## 👥 **Workspace Management Commands**

### `emuses workspace list` - List Available Workspaces

Display workspaces available to the current user for collaborative model development and sharing.

#### Syntax
```bash
emuses workspace list [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--format` | string | No | Output format: 'table', 'json', 'csv' |
| `--role` | string | No | Filter by role: 'owner', 'member', 'viewer' |
| `--active_only` | flag | No | Show only active workspaces |

#### Examples

**Basic Workspace Listing**
```bash
emuses workspace list
```

**JSON Format with Role Filter**
```bash
emuses workspace list --format json --role owner
```

#### Sample Output
```
Available Workspaces
===================
Name               Role     Members  Models  Last Activity
neurology_lab      Owner    8        15      2024-08-16
cognitive_research Member   12       23      2024-08-15
hcp_analysis       Viewer   45       67      2024-08-14
motor_cortex_team  Member   6        9       2024-08-13

Total: 4 workspaces
```

#### Use Cases
- **Collaboration Planning**: See available team workspaces
- **Access Management**: Understand your roles across workspaces
- **Project Organization**: Identify relevant research groups

---

### `emuses workspace create` - Create New Workspace

Create a new collaborative workspace for team model development and sharing.

#### Syntax
```bash
emuses workspace create WORKSPACE_NAME [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `WORKSPACE_NAME` | string | Yes | Name for the new workspace |
| `--description` | string | No | Workspace description |
| `--visibility` | string | No | Visibility: 'private', 'internal', 'public' |
| `--template` | string | No | Use workspace template |
| `--invite_members` | string | No | Comma-separated list of initial members |

#### Examples

**Basic Private Workspace**
```bash
emuses workspace create "my_research_lab" \
  --description "Neuroimaging research lab workspace"
```

**Public Workspace with Initial Members**
```bash
emuses workspace create "open_brain_models" \
  --description "Public brain modeling workspace" \
  --visibility public \
  --invite_members "colleague@university.edu,student@university.edu"
```

**Workspace from Template**
```bash
emuses workspace create "new_lab" \
  --template neuroimaging_lab \
  --visibility internal
```

#### Use Cases
- **Lab Setup**: Create workspace for new research groups
- **Project Organization**: Separate workspaces for different studies
- **Collaboration**: Shared spaces for model development

#### Workspace Features
- **Model Sharing**: Share and collaborate on trained models
- **Access Control**: Role-based permissions (owner/member/viewer)
- **Activity Tracking**: Monitor workspace activity and contributions
- **Resource Management**: Shared storage and compute quotas

---

### `emuses workspace info` - Workspace Details

Show detailed information about a specific workspace including members, models, and activity.

#### Syntax
```bash
emuses workspace info WORKSPACE_NAME [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `WORKSPACE_NAME` | string | Yes | Name of workspace to inspect |
| `--format` | string | No | Output format: 'text', 'json' |
| `--include_members` | flag | No | Include member details |
| `--include_models` | flag | No | Include model list |
| `--include_activity` | flag | No | Include recent activity |

#### Examples

**Basic Workspace Information**
```bash
emuses workspace info neurology_lab
```

**Complete Workspace Details**
```bash
emuses workspace info cognitive_research \
  --include_members \
  --include_models \
  --include_activity \
  --format json
```

#### Sample Output
```
Workspace Information: neurology_lab
====================================
Created: 2024-06-15
Owner: Dr. Jane Smith (jane.smith@university.edu)
Description: Neuroimaging research lab workspace
Visibility: Private

Statistics:
- Members: 8 (3 owners, 4 members, 1 viewer)
- Models: 15 trained models
- Storage Used: 234.7 MB
- Activity: 47 actions this month

Recent Models:
- motor_cortex_classifier_v3 (2024-08-16)
- working_memory_predictor_v2 (2024-08-15)  
- attention_network_model (2024-08-14)

Recent Activity:
- Aug 16: Model uploaded by Alex Chen
- Aug 15: New member added: Sarah Johnson
- Aug 14: Model shared externally

Permissions:
✅ Upload models
✅ Invite members
✅ Modify workspace settings
```

#### Use Cases
- **Workspace Management**: Monitor workspace health and usage
- **Member Coordination**: Understand team composition and activity
- **Resource Planning**: Track storage and model usage
- **Access Auditing**: Review permissions and member access

---

## 🔧 **Administrative Commands**

*Note: Admin commands require administrator privileges and are available in database/cloud deployment modes.*

### `emuses admin help` - Comprehensive Administrative Help

Display detailed help for administrative commands and common workflows.

#### Syntax
```bash
emuses admin help [COMMAND] [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `COMMAND` | string | No | Get help for specific admin command |
| `--workflows` | flag | No | Show common administrative workflows |
| `--examples` | flag | No | Include detailed examples |

#### Examples

**General Admin Help**
```bash
emuses admin help
```

**Specific Command Help**
```bash
emuses admin help add-user --examples
```

**Administrative Workflows**
```bash
emuses admin help --workflows
```

#### Use Cases
- **New Administrator Onboarding**: Learn admin command patterns
- **Workflow Reference**: Quick access to common procedures
- **Troubleshooting**: Get help with specific admin tasks

---

### `emuses admin add-user` - Create New User

Create a new user account in the EMUSES multi-user system.

#### Syntax
```bash
emuses admin add-user [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--username` | string | No | Username (interactive if not provided) |
| `--email` | string | No | User email address |
| `--role` | string | No | User role: 'user', 'admin', 'viewer' |
| `--quota` | string | No | Storage quota (e.g., '1GB', '500MB') |
| `--workspaces` | string | No | Comma-separated initial workspaces |
| `--send_invite` | flag | No | Send invitation email |
| `--batch_file` | path | No | CSV file for batch user creation |

#### Examples

**Interactive User Creation**
```bash
emuses admin add-user
```

**Complete User Setup**
```bash
emuses admin add-user \
  --username "jane_researcher" \
  --email "jane@university.edu" \
  --role "user" \
  --quota "2GB" \
  --workspaces "neurology_lab,cognitive_research" \
  --send_invite
```

**Batch User Creation**
```bash
emuses admin add-user --batch_file new_users.csv
```

#### Batch File Format (CSV)
```csv
username,email,role,quota,workspaces
john_smith,john@university.edu,user,1GB,neurology_lab
sarah_jones,sarah@institute.org,admin,5GB,"neurology_lab,cognitive_research"
```

#### Use Cases
- **Lab Onboarding**: Add new research team members
- **Course Setup**: Bulk create student accounts
- **Collaboration**: Add external collaborators

---

### `emuses admin list-users` - List System Users

Display all users in the system with filtering and detailed information options.

#### Syntax
```bash
emuses admin list-users [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--format` | string | No | Output format: 'table', 'json', 'csv' |
| `--role` | string | No | Filter by role: 'user', 'admin', 'viewer' |
| `--active_only` | flag | No | Show only active users |
| `--workspace` | string | No | Filter by workspace membership |
| `--sort` | string | No | Sort by: 'username', 'created', 'last_login' |
| `--include_stats` | flag | No | Include usage statistics |

#### Examples

**Basic User Listing**
```bash
emuses admin list-users
```

**Active Admins with Statistics**
```bash
emuses admin list-users \
  --role admin \
  --active_only \
  --include_stats \
  --format json
```

**Users in Specific Workspace**
```bash
emuses admin list-users \
  --workspace neurology_lab \
  --sort last_login
```

#### Sample Output
```
System Users
============
Username        Email                Role   Quota   Last Login   Models
jane_researcher jane@university.edu  user   2GB     2024-08-16   8
john_admin      john@admin.org       admin  10GB    2024-08-16   3
sarah_student   sarah@student.edu    user   1GB     2024-08-15   2
alex_viewer     alex@external.com    viewer 500MB   2024-08-10   0

Total: 4 users (2 users, 1 admin, 1 viewer)
Active: 4 | Inactive: 0
Total Quota Allocated: 13.5GB | Used: 8.2GB
```

#### Use Cases
- **User Management**: Monitor system user base
- **Resource Planning**: Track quota usage and allocation
- **Access Auditing**: Review user roles and permissions
- **Activity Monitoring**: Identify inactive users

---

### `emuses admin system-status` - System Health and Status

Display comprehensive system status including health, performance, and resource usage.

#### Syntax
```bash
emuses admin system-status [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--format` | string | No | Output format: 'text', 'json' |
| `--detailed` | flag | No | Include detailed component status |
| `--alerts_only` | flag | No | Show only alerts and warnings |
| `--export` | path | No | Export status report to file |

#### Examples

**Basic System Status**
```bash
emuses admin system-status
```

**Detailed Status with Export**
```bash
emuses admin system-status \
  --detailed \
  --export system_report.json
```

**Check for Alerts Only**
```bash
emuses admin system-status --alerts_only
```

#### Sample Output
```
EMUSES System Status
===================
Status: ✅ Healthy
Last Check: 2024-08-16 14:30:15 UTC
Uptime: 15 days, 8 hours

Components:
✅ Database: PostgreSQL 13.2 (Healthy)
✅ Redis: 6.2.6 (Healthy)  
✅ Model Registry: Active (15 models)
✅ API Server: Running (98.5% uptime)
✅ Background Jobs: 2 queued, 0 failed

Resources:
- CPU Usage: 23% (8 cores)
- Memory: 2.1GB / 8GB (26%)
- Disk: 47.3GB / 100GB (47%)
- Network: 12.3 Mbps avg

Users:
- Active Sessions: 12
- Total Users: 156
- New Users (24h): 3

Performance:
- Avg Response Time: 245ms
- API Requests/min: 127
- Model Uploads (24h): 8
- Inference Requests (24h): 234

Alerts: None
```

#### Use Cases
- **System Monitoring**: Regular health checks
- **Performance Tuning**: Identify bottlenecks
- **Capacity Planning**: Monitor resource usage trends
- **Issue Detection**: Early warning system

---

### `emuses admin set-quota` - User Quota Management

Set or modify storage quotas for individual users or user groups.

#### Syntax
```bash
emuses admin set-quota USERNAME QUOTA [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `USERNAME` | string | Yes | Username to modify |
| `QUOTA` | string | Yes | New quota (e.g., '2GB', '500MB', 'unlimited') |
| `--force` | flag | No | Apply even if over current usage |
| `--notify_user` | flag | No | Send notification to user |
| `--reason` | string | No | Reason for quota change |

#### Examples

**Basic Quota Update**
```bash
emuses admin set-quota jane_researcher 5GB
```

**Force Quota with Notification**
```bash
emuses admin set-quota john_student 1GB \
  --force \
  --notify_user \
  --reason "Course quota limit"
```

**Set Unlimited Quota**
```bash
emuses admin set-quota senior_researcher unlimited \
  --notify_user
```

#### Use Cases
- **Resource Management**: Adjust storage allocations
- **Course Management**: Set student quota limits
- **Project Scaling**: Increase quotas for large studies
- **Cost Control**: Manage cloud storage costs

---

### `emuses admin cancel-job` - Job Management

Cancel stuck, failed, or long-running jobs in the system.

#### Syntax
```bash
emuses admin cancel-job JOB_ID [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `JOB_ID` | string | Yes | Job ID to cancel |
| `--force` | flag | No | Force cancellation of running jobs |
| `--notify_user` | flag | No | Notify job owner of cancellation |
| `--reason` | string | No | Cancellation reason |
| `--cleanup` | flag | No | Clean up partial results |

#### Examples

**Cancel Stuck Job**
```bash
emuses admin cancel-job job_abc123 \
  --notify_user \
  --reason "Job stuck for >2 hours"
```

**Force Cancel with Cleanup**
```bash
emuses admin cancel-job job_xyz789 \
  --force \
  --cleanup \
  --notify_user
```

#### Job Management Workflow
```bash
# 1. List running jobs
emuses admin list-jobs --status running

# 2. Check specific job details  
emuses admin job-info job_abc123

# 3. Cancel if necessary
emuses admin cancel-job job_abc123 --reason "Resource limit exceeded"
```

#### Use Cases
- **Resource Management**: Free up stuck compute resources
- **System Maintenance**: Clean up failed jobs
- **Emergency Response**: Cancel problematic jobs quickly
- **User Support**: Help users with stuck analyses

---

## 🛠️ **Utility Commands**

### `emuses install-completion` - Shell Completion Setup

Install shell completion for enhanced command-line experience in bash, zsh, and fish shells.

#### Syntax
```bash
emuses install-completion [OPTIONS]
```

#### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--shell` | string | No | Target shell: 'bash', 'zsh', 'fish' (auto-detect if not specified) |
| `--path` | string | No | Custom installation path |
| `--show` | flag | No | Show completion script without installing |

#### Examples

**Auto-Install for Current Shell**
```bash
emuses install-completion
```

**Install for Specific Shell**
```bash
emuses install-completion --shell zsh
```

**Show Completion Script**
```bash
emuses install-completion --show
```

#### Installation Process
1. **Detection**: Automatically detects your current shell
2. **Installation**: Adds completion script to appropriate location
3. **Activation**: Instructions for activating in current session

#### Shell-Specific Instructions

**Bash**
```bash
# After installation, reload your shell or run:
source ~/.bashrc
```

**Zsh**  
```bash
# After installation, reload your shell or run:
source ~/.zshrc
```

**Fish**
```bash
# Completion is automatically available in new fish sessions
```

#### Features
- **Command Completion**: Tab-complete all EMUSES commands
- **Parameter Completion**: Complete option names and values
- **File Path Completion**: Smart completion for file arguments
- **Context Awareness**: Relevant completions based on command context

#### Use Cases
- **Productivity**: Faster command entry with tab completion
- **Discovery**: Learn available commands and options
- **Accuracy**: Reduce typing errors with auto-completion

---

## 📚 **Error Reference**

### Common Error Messages and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `Model not found` | Invalid model path | Check path with `emuses models list` |
| `Permission denied` | Insufficient privileges | Check file permissions or use admin mode |
| `Invalid data format` | Incorrect CSV structure | Verify headers and data types |
| `Database connection failed` | Database not accessible | Check `DATABASE_URL` and database status |
| `Registry mode mismatch` | Mode configuration issue | Run `emuses models mode-info --check_requirements` |
| `Storage quota exceeded` | User storage limit reached | Use `emuses models storage` and clean up models |
| `Model verification failed` | Corrupted or incomplete model | Run `emuses verify MODEL_PATH` for details |
| `Workspace not found` | Invalid workspace name | Check available workspaces with `emuses workspace list` |
| `Authentication required` | Multi-user mode requires login | Contact admin or check authentication setup |
| `Job execution timeout` | Analysis taking too long | Check system resources or contact admin |
| `Invalid manifest format` | Model metadata corrupted | Regenerate model or restore from backup |
| `Network connection error` | API server unreachable | Check server status and network connectivity |
| `Version compatibility issue` | EMUSES version mismatch | Update EMUSES or check version requirements |
| `Memory allocation error` | Insufficient system memory | Reduce batch size or use different hardware |
| `File format not supported` | Unsupported input format | Convert to CSV or check format requirements |

### Error Code Categories

#### Installation Errors (E100-199)
- **E101**: Missing dependencies
- **E102**: Python version incompatibility
- **E103**: Installation path issues

#### Data Format Errors (E200-299)
- **E201**: CSV parsing errors
- **E202**: Missing required columns
- **E203**: Data type mismatches

#### Model Registry Errors (E300-399)
- **E301**: Model installation failed
- **E302**: Registry corruption
- **E303**: Model verification failed

#### Authentication Errors (E400-499)
- **E401**: Authentication required
- **E403**: Insufficient permissions
- **E404**: User or resource not found

#### System Errors (E500-599)
- **E501**: Database connection issues
- **E502**: API server errors
- **E503**: Resource exhaustion

---

## 🔗 **Related Documentation**

- [User Guide](docs/USER_GUIDE.md) - Complete usage documentation
- [API Reference](docs/API_REFERENCE.md) - REST API documentation  
- [Research Workflows](docs/RESEARCH_WORKFLOWS.md) - Scientific use patterns
- [Admin Guide](docs/ADMIN_GUIDE.md) - System administration

---

*This CLI reference covers all EMUSES commands for comprehensive neuroimaging analysis workflows. For additional help, use `emuses [command] --help` or consult the complete User Guide.*