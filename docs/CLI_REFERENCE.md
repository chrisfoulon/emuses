# 🛠️ EMUSES CLI Complete Reference

**Comprehensive command-line interface reference for EMUSES scientific analysis platform**

This reference provides multi-level documentation for all CLI commands, from beginner tutorials to advanced optimization strategies.

---

## 📚 **Documentation Levels**

### 🟢 **Beginner Level** - Getting Started
- Basic commands with default settings
- Essential workflows for scientific analysis (neuroimaging examples)
- Preset optimization configurations
- Simple examples with sample data

### 🟡 **Intermediate Level** - Understanding the System  
- Parameter categories and functionality
- Optimization dictionary (`optim_dict`) mechanism
- Workflow customization and configuration
- Multi-stage pipeline usage

### 🔴 **Advanced Level** - Expert Configuration
- Custom optimization parameter design
- Performance tuning and resource management
- Multi-user and service deployment
- Integration with external systems

---

## 📋 **Command Overview**

### **Quick Command Index**
| Category | Commands | User Level | Description |
|----------|----------|------------|-------------|
| **Pipeline** | `full`, `umap`, `heatmap`, `inference` | 🟢 Beginner | Core analysis workflows |
| **Research** | `verify`, `info`, `cite`, `trace`, `reproduce`, `diff`, `compare`, `rerun` | 🟡 Intermediate | Scientific reproducibility tools |
| **Registry** | `models *` (11 commands) | 🟡 Intermediate | Model management and sharing |
| **Workspace** | `workspace *` (3 commands) | 🟡 Intermediate | Team collaboration |
| **Admin** | `admin *` (5 commands) | 🔴 Advanced | System administration |
| **Utility** | `install-completion` | 🟢 Beginner | Shell integration |

---

## 🟢 **Beginner Level: Essential Commands**

*Start here if you're new to EMUSES or scientific data analysis*

### `emuses full` - Complete Pipeline Analysis

Run the complete EMUSES analysis pipeline with sensible defaults.

#### Basic Usage
```bash
emuses full my_analysis/ brain_features.csv --scores cognitive_scores.csv
```

#### Essential Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `OUTPUT_FOLDER` | path | ✅ Required | Directory for analysis results |
| `INPUT_DATASET` | path | ✅ Required | CSV file with scientific features |
| `--scores` | path | ✅ Essential | CSV file with cognitive/behavioral scores |

#### Beginner Examples

**Example 1: Basic HCP Analysis**
```bash
# Using sample data (replace with your data files)
emuses full my_first_analysis/ \
  docs/examples/sample_data/hcp_input_data.csv \
  --scores docs/examples/sample_data/hcp_labels.csv
```
*Expected runtime: 3-5 minutes with sample data*
*Output: Complete analysis results in `my_first_analysis/` folder*

**Example 2: Quick Analysis with Different Data**
```bash
# Basic analysis with custom data
emuses full brain_cognition_study/ \
  my_brain_features.csv \
  --scores my_cognitive_scores.csv
```

### `emuses umap` - Dimensionality Reduction Only

Create UMAP embeddings without full pipeline.

#### Basic Usage
```bash
emuses umap embeddings_output/ brain_features.csv
```

#### When to Use
- **Exploratory analysis**: Quick visualization of high-dimensional data
- **Quality control**: Check data clustering before full analysis
- **Preprocessing**: Create embeddings for downstream analysis

### `emuses heatmap` - Visualization Generation

Generate correlation heatmaps from existing embeddings.

#### Basic Usage
```bash
emuses heatmap heatmap_output/ embeddings.npy --scores cognitive_scores.csv
```

---

## 🟡 **Intermediate Level: Understanding the System**

*For users who want to customize analysis and understand optimization*

### Understanding Optimization Configurations (`optim_dict`)

EMUSES uses sophisticated optimization configurations instead of direct parameter exposure. This provides better results while maintaining simplicity.

#### What is `optim_dict`?
The `--optim_dict` parameter references predefined optimization configurations that control:
- **UMAP parameters**: n_neighbors, min_dist, metric selection
- **HDBSCAN parameters**: min_cluster_size, min_samples  
- **Optimization metrics**: How to evaluate parameter quality
- **Search strategies**: How to explore parameter space

#### Available Preset Configurations

**`optim_dict_default`** - Balanced optimization (Default)
- Good for most neuroimaging datasets
- Moderate exploration of parameter space
- Balances clustering quality with speed

**`optim_dict_hcp`** - Optimized for HCP-style data
- Best for high-quality, preprocessed neuroimaging data  
- Fixed parameters proven effective on HCP datasets
- Faster execution with known-good settings

**`optim_dict_range`** - Better for noisy data
- Broader parameter exploration 
- Less focus on entropy optimization (hard to optimize with noisy data)
- More robust clustering for challenging datasets

**`optim_dict_hard`** - Intensive optimization
- Narrower n_neighbors exploration (5-45 → 5-45 with step 20)
- Slightly lower entropy focus for more stable optimization
- Longer runtime but potentially better results

### `emuses full` - Complete Parameter Reference

#### Data Input Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `OUTPUT_FOLDER` | path | - | **Required.** Analysis results directory |
| `INPUT_DATASET` | path | - | **Required.** Scientific features CSV |
| `--scores` | path | None | **Essential.** Behavioral/cognitive scores CSV |
| `--label-dataset` | path | None | Additional labeled dataset |

#### Optimization Configuration  
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--optim_dict` | string | optim_dict_default | Optimization configuration preset |
| `--umap_trials` | integer | 50 | Number of UMAP optimization trials |
| `--hdbscan_trials` | integer | 20 | Number of HDBSCAN optimization trials |

#### Execution Control
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--test_size` | float | 0.2 | Train/test split ratio |
| `--random_state` | integer | 42 | Random seed for reproducibility |
| `--n_jobs` | integer | -1 | Parallel processing (-1 = all cores) |

#### Advanced Features
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--use_enhanced_pipeline` | flag | False | Enable Optuna model optimization |
| `--optuna_trials` | integer | 60 | Optuna optimization trials per model |
| `--interactive` | flag | False | Interactive mode with prompts |

#### Service Integration
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--service` | flag | False | Use remote service execution |
| `--service-url` | string | None | Remote service URL |
| `--token` | string | None | Authentication token |

#### Intermediate Examples

**Example 1: HCP-Optimized Analysis**
```bash
emuses full hcp_analysis/ \
  brain_connectivity.csv \
  --scores fluid_intelligence.csv \
  --optim_dict optim_dict_hcp \
  --random_state 42
```

**Example 2: Noisy Data Analysis**
```bash
emuses full noisy_data_analysis/ \
  messy_brain_features.csv \
  --scores behavioral_scores.csv \
  --optim_dict optim_dict_range \
  --umap_trials 100
```

**Example 3: Enhanced Pipeline with Model Optimization**
```bash
emuses full comprehensive_analysis/ \
  brain_features.csv \
  --scores cognitive_battery.csv \
  --use_enhanced_pipeline \
  --optuna_trials 100 \
  --n_jobs 8
```

### Model Registry Commands

#### `emuses models list` - View Available Models
```bash
emuses models list                    # List all models
emuses models list --workspace lab1   # Filter by workspace
```

#### `emuses models install` - Register New Models
```bash
emuses models install trained_model/ --name "Brain Age Predictor"
```

#### `emuses models info` - Get Model Details
```bash
emuses models info model_id_or_name
```

### Workspace Management Commands

#### `emuses workspace create` - Create Team Workspace
```bash
emuses workspace create "Lab Analysis" \
  --description "Shared workspace for lab analysis projects"
```

#### `emuses workspace list` - View Available Workspaces
```bash
emuses workspace list
```

---

## 🔴 **Advanced Level: Expert Configuration**

*For system administrators and advanced users who need full control*

### Custom Optimization Configuration

Advanced users can create custom `optim_dict` configurations by understanding the internal structure.

#### Configuration Structure
```python
{
    "param": {
        "umap": {
            "min_dist": {"name": "min_dist", "low": 0.0, "high": 0.5},
            "n_neighbors": {"name": "n_neighbors", "low": 5, "high": 45, "step": 10},
            "n_components": {"value": 2},  # Fixed at 2D
            "metric": {"name": "metric", "choices": ["euclidean"]}
        },
        "hdbscan": {
            "min_cluster_size": {"name": "min_cluster_size", "low": 5, "high": 50},
            "min_samples": {"name": "min_samples", "low": 1, "high": 10}
        }
    },
    "metrics": {
        "umap": {
            "eigen_spread": {"weight": 2.0},
            "density_variability": {"weight": 1.0, "target": 0.4, "epsilon": 0.2},
            "entropy": {"weight": 3.0, "target": 0.6, "epsilon": 0.25}
        },
        "hdbscan": {
            "cluster_persistence": {"weight": 2},
            "noise_ratio": {"weight": 1.0, "target": 0.9, "epsilon": 0.05},
            "dbcv": {"weight": 1.0, "target": 1, "epsilon": 0.5}
        }
    }
}
```

#### Parameter Types
- **Range parameters**: `{"low": X, "high": Y}` - Continuous optimization range
- **Step parameters**: `{"low": X, "high": Y, "step": Z}` - Discrete steps  
- **Choice parameters**: `{"choices": [A, B, C]}` - Categorical selection
- **Fixed parameters**: `{"value": X}` - No optimization

#### Metric Optimization
- **weight**: Importance of this metric in overall score
- **target**: Desired value for the metric  
- **epsilon**: Tolerance around target value

### Administrative Commands

#### `emuses admin add-user` - Create System User
```bash
emuses admin add-user username \
  --email user@institution.edu \
  --role researcher
```

#### `emuses admin system-status` - Monitor System Health  
```bash
emuses admin system-status
```

#### `emuses admin set-quota` - Manage Resource Limits
```bash
emuses admin set-quota username --storage 100GB --compute 50hours
```

### Performance and Resource Management

#### High-Performance Analysis Setup
```bash
emuses full large_study_analysis/ \
  massive_dataset.csv \
  --scores comprehensive_battery.csv \
  --optim_dict optim_dict_hard \
  --umap_trials 200 \
  --optuna_trials 150 \
  --parallel_model_training \
  --n_jobs 16 \
  --umap_jobs 8 \
  --hdbscan_jobs 4
```

#### Service-Based Execution
```bash
emuses full distributed_analysis/ \
  brain_features.csv \
  --scores cognitive_scores.csv \
  --service \
  --service-url https://emuses-cluster.institution.edu \
  --token $EMUSES_TOKEN \
  --service-timeout 7200
```

---

## 🔗 **Related Documentation**

- **[User Guide](docs/USER_GUIDE.md)** - Complete usage documentation
- **[API Reference](docs/API_REFERENCE.md)** - REST API documentation  
- **[Research Workflows](docs/RESEARCH_WORKFLOWS.md)** - Scientific use patterns
- **[Admin Guide](docs/ADMIN_GUIDE.md)** - System administration

---

## 💡 **Getting Help**

### Command-Specific Help
```bash
emuses COMMAND --help           # Get help for any command
emuses models SUBCOMMAND --help # Get help for subcommands
```

### Troubleshooting
- **Parameter errors**: Check required vs optional parameters above
- **Data format issues**: Ensure CSV files have proper headers and formatting
- **Performance problems**: Reduce `--umap_trials` and `--optuna_trials` for faster execution
- **Memory issues**: Use `--n_jobs 1` to reduce parallel processing

### Support Resources
- **GitHub Issues**: [Report bugs and request features](https://github.com/chrisfoulon/emuses/issues)
- **Documentation**: [Complete user guides](docs/)
- **Sample Data**: [Example datasets and workflows](docs/examples/)