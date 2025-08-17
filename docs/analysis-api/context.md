# Analysis API Enhancement - Technical Context

## Current Analysis Function Capabilities

### Existing Analysis Functions

#### 1. `run_kernel_heatmap_analysis()` (kernel_regression_utils.py)
**Location**: `emuses/tools/kernel_regression_utils.py:646`
**Purpose**: Kernel regression-based heatmap analysis with effect size calculation

**Key Parameters**:
```python
def run_kernel_heatmap_analysis(
    embeddings,                    # UMAP/embedding coordinates  
    scores_vectors_dict,           # Target variable vectors
    input_matrix,                  # Original data matrix (neuroimaging)
    output_folder,                # Output directory
    grid_size=100,                # Resolution of analysis grid
    sigma_range=None,             # Kernel width optimization range
    threshold=0.5,                # Statistical threshold
    uncertainty_penalty=0.5,      # Uncertainty weighting factor
    input_type="image",           # Data type (image, tabular)
    classification=False,         # Classification vs regression
    cluster_labels=None,          # Cluster assignments
    effect_size_test="mann-whitney",  # Effect size test method
    highlight_points=True,        # Point highlighting in visualization
    show_plots=False,            # Display plots during execution
    generate_plots=False,        # Generate plot files
    output_format_info=None,     # Output format configuration
    full_embeddings=None,        # Full embedding space
    clusterer=None,              # Clustering algorithm instance
    cluster_predict_method="kdtree",  # Cluster prediction method
    optimize_sigma=True,         # Automatic sigma optimization
    random_state=42              # Reproducibility seed
)
```

**Core Capabilities**:
- **Kernel Regression**: Nadaraya-Watson estimator for continuous outcome prediction
- **Effect Size Analysis**: Statistical significance testing with configurable methods
- **Spatial Mapping**: Grid-based analysis across embedding space
- **Uncertainty Quantification**: Model uncertainty assessment and visualization
- **Clustering Integration**: Analysis within cluster boundaries
- **Statistical Testing**: Multiple effect size test options (mann-whitney, t-test, etc.)

#### 2. `run_heatmap_analysis()` (correlation_maps_utils.py)
**Location**: `emuses/tools/correlation_maps_utils.py:205`
**Purpose**: Correlation-based heatmap analysis with statistical mapping

**Key Parameters**:
```python
def run_heatmap_analysis(
    embeddings,                   # UMAP/embedding coordinates
    scores_vectors_dict,          # Target variable vectors  
    input_matrix,                 # Original data matrix
    output_folder,               # Output directory
    output_format_info,          # Output format configuration
    clusterer,                   # Clustering algorithm instance
    cluster_labels,              # Cluster assignments
    input_type="image",          # Data type specification
    grid_size=100,               # Analysis grid resolution
    sigma=None,                  # Smoothing parameter
    show_plots=False,           # Plot display control
    generate_plots=False,       # Plot generation control
    highlight_points=True,      # Point highlighting
    effect_size_test="mann-whitney",  # Statistical test method
    random_state=42             # Reproducibility control
)
```

**Core Capabilities**:
- **Correlation Analysis**: Statistical correlation mapping across embedding space
- **Grid-Based Analysis**: Systematic analysis across defined resolution grid
- **Cluster-Aware Processing**: Analysis within and across cluster boundaries
- **Statistical Testing**: Effect size calculation with multiple test options
- **Visualization**: Comprehensive heatmap and statistical plot generation

### Technical Architecture Analysis

#### Function Integration Points

**Artifact Pipeline Integration**:
```python
# Both functions integrate with existing output system
from emuses.tools.output_utils import save_statistical_maps

# Standard artifact saving pattern used in both functions
save_statistical_maps(
    output_folder=output_folder,
    statistical_maps=analysis_results,
    format_info=output_format_info,
    metadata=analysis_metadata
)
```

**Statistical Testing Framework**:
```python
# Both functions use common statistical testing
effect_size_test options:
- "mann-whitney": Mann-Whitney U test (non-parametric)
- "t-test": Student's t-test (parametric)
- "wilcoxon": Wilcoxon signed-rank test
- "kruskal": Kruskal-Wallis test (multi-group)
```

**Data Flow Architecture**:
1. **Input Processing**: UMAP embeddings + target variables + original data
2. **Grid Generation**: Spatial grid across embedding space for analysis
3. **Statistical Analysis**: Effect size calculation at each grid point
4. **Visualization**: Heatmap generation with statistical overlays
5. **Artifact Storage**: Results saved through `save_statistical_maps()`

#### Dependency Analysis

**Core Dependencies**:
```python
# Scientific computing
import numpy as np
import pandas as pd
from scipy.stats import normaltest, mannwhitneyu, ttest_ind

# Machine learning
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.metrics import r2_score, mean_squared_error
import GPy  # Gaussian Process library

# Clustering
import hdbscan
from sklearn.decomposition import PCA

# Visualization
import matplotlib.pyplot as plt
import matplotlib

# EMUSES internal
from emuses.tools.output_utils import save_statistical_maps
from emuses.tools.stats_utils import input_matrix_stat_map
```

**Integration Requirements**:
- All dependencies already satisfied in EMUSES environment
- Functions are mature with extensive real-world usage
- No architectural changes required for API exposure

### Current Usage Context

#### Pipeline Integration
Both functions are currently used in:
- **Heatmap Stage**: `emuses/pipelines/heatmap_stage.py` calls these functions
- **Manual Analysis**: Researchers call functions directly from Python scripts
- **Research Workflows**: Integration with external analysis pipelines

#### Output Integration
**Artifact Pipeline** (`save_statistical_maps()`):
- Saves statistical maps in multiple formats (PNG, SVG, NPZ)
- Generates metadata files with analysis parameters
- Creates visualization summaries and statistical reports
- Integrates with EMUSES output directory structure

#### Parameter Complexity Analysis

**Common Parameters Across Functions**:
- `embeddings`: 2D UMAP coordinates (N x 2 array)
- `scores_vectors_dict`: Target variables dict {name: values}
- `input_matrix`: Original data (N x features)
- `output_folder`: Output directory path
- `grid_size`: Analysis resolution (typically 50-200)
- `effect_size_test`: Statistical test method
- `show_plots/generate_plots`: Visualization control

**Function-Specific Parameters**:
- **Kernel Analysis**: `sigma_range`, `uncertainty_penalty`, `optimize_sigma`
- **Correlation Analysis**: `sigma` (fixed smoothing), `clusterer` (required)

### API Design Considerations

#### Request/Response Model Design

**Common Request Parameters**:
```python
class AnalysisRequestBase(BaseModel):
    embeddings: List[List[float]]           # 2D coordinates
    scores_vectors: Dict[str, List[float]]   # Target variables
    input_matrix: List[List[float]]         # Original data
    grid_size: int = 100                    # Analysis resolution
    effect_size_test: str = "mann-whitney"  # Statistical test
    input_type: str = "image"               # Data type
    show_plots: bool = False                # Visualization control
    generate_plots: bool = True             # Plot generation
    random_state: int = 42                  # Reproducibility
```

**Kernel-Specific Parameters**:
```python
class KernelAnalysisRequest(AnalysisRequestBase):
    sigma_range: Optional[Tuple[float, float]] = None  # Auto-optimization range
    threshold: float = 0.5                             # Statistical threshold
    uncertainty_penalty: float = 0.5                   # Uncertainty weight
    classification: bool = False                        # Analysis type
    optimize_sigma: bool = True                         # Auto-optimization
```

**Correlation-Specific Parameters**:
```python
class CorrelationAnalysisRequest(AnalysisRequestBase):
    sigma: Optional[float] = None           # Fixed smoothing parameter
    clusterer_config: Optional[Dict] = None # Clustering configuration
```

#### Response Model Design

**Analysis Response Structure**:
```python
class AnalysisResponse(BaseModel):
    analysis_id: str                        # Unique analysis identifier
    output_folder: str                      # Results location
    statistical_maps: List[str]             # Generated map file paths
    metadata: Dict[str, Any]                # Analysis metadata
    execution_time: float                   # Processing duration
    parameters_used: Dict[str, Any]         # Final parameter values
    warnings: List[str] = []               # Any warnings generated
```

### CLI Integration Context

#### Existing CLI Framework
EMUSES uses Click framework for CLI commands:
```python
# Pattern from existing commands
@click.command()
@click.option('--param', help='Parameter description')
def existing_command(param):
    """Command description."""
    pass
```

#### New Command Structure
```bash
# Proposed CLI commands
emuses analysis kernel-heatmap --embeddings-file path.csv --scores-file scores.csv --output-dir results/
emuses analysis correlation-heatmap --embeddings-file path.csv --scores-file scores.csv --output-dir results/
```

#### Parameter File Support
For complex analysis parameters:
```yaml
# analysis_config.yaml
embeddings_file: "data/embeddings.csv"
scores_file: "data/scores.csv" 
input_matrix_file: "data/input_matrix.csv"
output_folder: "results/analysis"
grid_size: 100
effect_size_test: "mann-whitney"
kernel_params:
  sigma_range: [0.1, 2.0]
  uncertainty_penalty: 0.5
```

### Integration Strategy

#### API Endpoint Implementation
**FastAPI Endpoint Pattern**:
```python
@app.post("/analysis/kernel-heatmap/", response_model=AnalysisResponse)
async def kernel_heatmap_analysis(request: KernelAnalysisRequest):
    """Execute kernel regression heatmap analysis."""
    # Parameter validation
    # Function call with parameter mapping
    # Response formatting
    return analysis_response

@app.post("/analysis/correlation-heatmap/", response_model=AnalysisResponse)  
async def correlation_heatmap_analysis(request: CorrelationAnalysisRequest):
    """Execute correlation heatmap analysis."""
    # Implementation
    return analysis_response
```

#### Configuration Integration
**Pipeline Configuration Enhancement**:
```yaml
# Enhanced pipeline config
analysis:
  enable_effect_size_maps: true
  default_grid_size: 100
  default_effect_test: "mann-whitney"
  kernel_analysis:
    auto_optimize_sigma: true
    default_threshold: 0.5
  correlation_analysis:
    default_sigma: 1.0
    require_clustering: true
```

#### Error Handling Strategy
**Common Error Cases**:
- Invalid embedding dimensions
- Mismatched data sizes
- Missing required parameters for correlation analysis
- Insufficient memory for large grid sizes
- Invalid statistical test method

**Error Response Format**:
```python
class AnalysisError(BaseModel):
    error_type: str                         # Category of error
    message: str                           # Human-readable message
    details: Optional[Dict[str, Any]]      # Technical details
    suggestions: List[str] = []            # Resolution suggestions
```

### Testing Strategy Context

#### Existing Test Infrastructure
EMUSES has established test patterns:
- Integration tests for API endpoints with FastAPI TestClient
- Unit tests for analysis functions with mock data
- Fixture-based test data management

#### Analysis Function Test Requirements
**Test Data Requirements**:
- Small synthetic datasets for unit testing
- Realistic neuroimaging data for integration testing
- Edge case datasets (single points, identical values)
- Performance testing with large datasets

**Validation Approaches**:
- Output format validation against existing `save_statistical_maps()`
- Statistical correctness validation (known effect sizes)
- Parameter validation (invalid inputs, boundary conditions)
- Memory usage monitoring for large analyses

This context provides comprehensive understanding for implementing API and CLI interfaces that expose existing analysis capabilities while maintaining all current functionality and integration patterns.