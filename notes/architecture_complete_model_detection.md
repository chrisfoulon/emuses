# Complete Model Detection Architecture

## Current Task: 0A-Ext.1.a - Enhance ModelIOManager.validate_model()

### Context Analysis (From Current Implementation)
- Current `validate_model()` method: Lines 366-417 in model_io.py
- Returns: Dict with basic keys ["name", "version", "type", "description"]
- Focus: Manifest-based validation with directory structure detection
- Limitation: Treats all models as individual components

### Complete EMUSES Model Structure (From Context)
```
Complete Model Structure:
├── manifest.json                 # Model metadata and configuration  
├── umap_model.pkl               # UMAP dimensionality reduction
├── hdbscan_model.pkl            # HDBSCAN clustering  
├── prediction_ensemble/         # Prediction models directory
│   ├── model_1.pkl             
│   ├── model_2.pkl             
│   └── ...
├── embeddings.npy              # Generated embeddings  
├── cluster_labels.npy          # Cluster assignments
└── performance_metrics.json    # Model performance data
```

### Required Enhancement Design

#### New Return Type: CompleteModelValidation
```python
@dataclass
class CompleteModelValidation:
    is_complete_model: bool
    components_found: Dict[str, Path]  # {"umap": path, "hdbscan": path, "prediction": path}
    configuration_hash: str
    content_hash: str
    missing_components: List[str]
    validation_errors: List[str]
    
    # Backward compatibility
    name: str
    version: str  
    type: str
    description: str
```

#### Component Detection Logic
1. **UMAP Detection**: Look for `umap_model.pkl`, `*umap*.pkl` patterns
2. **HDBSCAN Detection**: Look for `hdbscan_model.pkl`, `*hdbscan*.pkl` patterns  
3. **Prediction Detection**: Look for `prediction_ensemble/` dir or `*prediction*.pkl` files
4. **Auxiliary Components**: embeddings.npy, cluster_labels.npy, performance_metrics.json

#### Hash Calculation Strategy
- **Configuration Hash**: Extract from manifest.json or pipeline metadata
- **Content Hash**: Combined hash of all component files + structure

### Integration Points
- Must maintain backward compatibility with existing `validate_model()` usage
- Should work with both complete models and individual components
- Must support diverse EMUSES versions (2.0.x, 2.1.x)

### Implementation Approach
1. Enhance existing method with optional `return_complete_info=False` parameter
2. When False: return current Dict format (backward compatibility)  
3. When True: return CompleteModelValidation dataclass
4. Internal logic always performs complete detection but formats output accordingly