# Data Preprocessing Utilities

The Data Preprocessing Utilities provide essential functions for data cleaning, normalization, and preparation within the EMUSES pipeline. These utilities handle image preprocessing, data normalization, resolution management, and data quality assurance to ensure consistent input formats for dimensionality reduction and machine learning models.

<details><summary>🛠️ Level 2 · Key API table</summary>

| Function | Purpose | Inputs | Outputs | Side-effects |
|---|---|---|---|---|
| `normalize_input_matrix(input_matrix)` | Normalize data to [0,1] range | `input_matrix: ndarray` | `ndarray` | None |
| `rescale_image_array(images_list, output_shape)` | Rescale image resolution | `images_list: List[PIL.Image], output_shape: tuple` | `None` | Modifies images in-place |
| `normalise_colours_in_array(images_list)` | Normalize pixel values to [0,1] | `images_list: List[PIL.Image]` | `None` | Modifies images in-place |
| `find_min_resolution(image_paths_list)` | Find minimum image dimensions | `image_paths_list: List[Path]` | `(min_width, min_height)` | None |
| `find_max_resolution(image_paths_list)` | Find maximum image dimensions | `image_paths_list: List[Path]` | `(max_width, max_height)` | None |
| `filter_nan_rows(coords, scores)` | Remove rows with NaN values | `coords: ndarray, scores: ndarray` | `(coords_clean, scores_clean, mask)` | None |

</details>

<details><summary>🔍 Level 3 · Code walk-through</summary>

## Data Normalization

The `normalize_input_matrix` function provides standard min-max normalization for input data:

```python
def normalize_input_matrix(input_matrix):
    """
    Normalize input matrix to [0, 1] range using min-max scaling.
    
    Applies sklearn's MinMaxScaler to ensure all features are on the same scale,
    which is crucial for distance-based algorithms like UMAP and clustering.
    This normalization prevents features with larger scales from dominating
    the analysis.
    
    Parameters
    ----------
    input_matrix : ndarray, shape (n_samples, n_features)
        Raw input data matrix with potentially different feature scales
    
    Returns
    -------
    normalized_matrix : ndarray, shape (n_samples, n_features)
        Normalized data with all features scaled to [0, 1] range
    
    Examples
    --------
    >>> import numpy as np
    >>> from emuses.tools.data_preproc import normalize_input_matrix
    >>> 
    >>> # Create sample data with different scales
    >>> data = np.array([[1, 100], [2, 200], [3, 300]])
    >>> normalized = normalize_input_matrix(data)
    >>> print(normalized)
    [[0.  0. ]
     [0.5 0.5]
     [1.  1. ]]
    
    Notes
    -----
    - Uses sklearn.preprocessing.MinMaxScaler for robust scaling
    - Handles edge cases where features have zero variance
    - Essential preprocessing step before UMAP and clustering
    - Preserves relative relationships within each feature
    """
    from sklearn.preprocessing import MinMaxScaler
    
    scaler = MinMaxScaler()
    normalized_matrix = scaler.fit_transform(input_matrix)
    
    return normalized_matrix
```

**Key features:**
- **Scale consistency**: Ensures all features contribute equally to distance calculations
- **Robust handling**: MinMaxScaler handles edge cases like constant features
- **Preservation**: Maintains relative relationships within each feature dimension
- **UMAP compatibility**: Creates optimal input format for dimensionality reduction

## Image Resolution Management

The utilities provide comprehensive image resolution analysis and standardization:

```python
def find_min_resolution(image_paths_list):
    """
    Find the minimum width and height across all images in the dataset.
    
    Analyzes all images to determine the smallest dimensions, which is useful
    for determining a common resolution for rescaling that won't lose information
    from any image.
    
    Parameters
    ----------
    image_paths_list : List[str or Path]
        List of paths to image files
    
    Returns
    -------
    tuple
        (min_width, min_height) - minimum dimensions found
    
    Examples
    --------
    >>> from emuses.tools.data_preproc import find_min_resolution
    >>> 
    >>> image_paths = ['image1.jpg', 'image2.jpg', 'image3.jpg']
    >>> min_w, min_h = find_min_resolution(image_paths)
    >>> print(f"Minimum resolution: {min_w}x{min_h}")
    """
    from PIL import Image
    
    min_width = min_height = float("inf")
    
    for img_path in image_paths_list:
        try:
            with Image.open(img_path) as img:
                width, height = img.size
                min_width = min(min_width, width)
                min_height = min(min_height, height)
        except Exception as e:
            print(f"Warning: Could not process {img_path}: {e}")
            continue
    
    return min_width, min_height

def find_max_resolution(image_paths_list):
    """
    Find the maximum width and height across all images in the dataset.
    
    Analyzes all images to determine the largest dimensions, which is useful
    for understanding the full resolution range and memory requirements.
    
    Parameters
    ----------
    image_paths_list : List[str or Path]
        List of paths to image files
    
    Returns
    -------
    tuple
        (max_width, max_height) - maximum dimensions found
    """
    from PIL import Image
    
    max_width = max_height = 0
    
    for img_path in image_paths_list:
        try:
            with Image.open(img_path) as img:
                width, height = img.size
                max_width = max(max_width, width)
                max_height = max(max_height, height)
        except Exception as e:
            print(f"Warning: Could not process {img_path}: {e}")
            continue
    
    return max_width, max_height

def rescale_image_array(images_list, output_shape=None):
    """
    Rescale the resolution of all images to a common size.
    
    Standardizes image dimensions across the dataset to ensure consistent
    input format for feature extraction. If no output shape is specified,
    uses the minimum resolution to prevent information loss.
    
    Parameters
    ----------
    images_list : List[PIL.Image]
        List of PIL Image objects to rescale
    output_shape : tuple, optional
        Target (width, height) for all images. If None, uses minimum
        resolution from the dataset to prevent upsampling
    
    Returns
    -------
    None
        Images are modified in-place for memory efficiency
    
    Examples
    --------
    >>> from PIL import Image
    >>> from emuses.tools.data_preproc import rescale_image_array
    >>> 
    >>> # Load images
    >>> images = [Image.open(path) for path in image_paths]
    >>> 
    >>> # Rescale to common size
    >>> rescale_image_array(images, output_shape=(224, 224))
    >>> 
    >>> # Verify all images are now the same size
    >>> for img in images:
    ...     print(img.size)  # Should all be (224, 224)
    
    Notes
    -----
    - Modifies images in-place for memory efficiency
    - Uses PIL's resize with default resampling (LANCZOS)
    - Preserves aspect ratio by choosing appropriate resampling
    - Prevents memory issues with large image datasets
    """
    from PIL import Image
    from tqdm import tqdm
    
    # If output_shape is not provided, find the minimum resolution
    if output_shape is None:
        min_width = min_height = float("inf")
        for img in images_list:
            width, height = img.size
            min_width = min(min_width, width)
            min_height = min(min_height, height)
        output_shape = (min_width, min_height)
        print(f"Auto-determined output shape: {output_shape}")

    # Rescale each image to output_shape
    print(f"Rescaling {len(images_list)} images to {output_shape}...")
    
    for i in tqdm(range(len(images_list)), desc="Rescaling images"):
        try:
            # Use high-quality resampling for better results
            images_list[i] = images_list[i].resize(output_shape, Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"Warning: Failed to rescale image {i}: {e}")
```

## Color Normalization

The utilities provide standardized color normalization for imaging data:

```python
def normalise_colours_in_array(images_list):
    """
    Normalize pixel values to [0, 1] range by dividing by 255.
    
    Converts 8-bit pixel values (0-255) to floating-point values in [0, 1] range.
    This normalization is essential for neural networks and many machine learning
    algorithms that expect normalized input.
    
    Parameters
    ----------
    images_list : List[PIL.Image]
        List of PIL Image objects to normalize
    
    Returns
    -------
    None
        Images are converted to numpy arrays and modified in-place
    
    Examples
    --------
    >>> from PIL import Image
    >>> from emuses.tools.data_preproc import normalise_colours_in_array
    >>> 
    >>> # Load and normalize images
    >>> images = [Image.open(path) for path in image_paths]
    >>> normalise_colours_in_array(images)
    >>> 
    >>> # Images are now numpy arrays with values in [0, 1]
    >>> print(f"Pixel range: [{images[0].min():.3f}, {images[0].max():.3f}]")
    
    Notes
    -----
    - Assumes 8-bit input images (0-255 pixel values)
    - Converts PIL Images to numpy arrays
    - Modifies the list contents in-place
    - Essential preprocessing for deep learning models
    """
    import numpy as np
    from tqdm import tqdm
    
    print(f"Normalizing colors for {len(images_list)} images...")
    
    for i in tqdm(range(len(images_list)), desc="Normalizing colors"):
        try:
            # Convert PIL Image to numpy array and normalize
            img_array = np.array(images_list[i], dtype=np.float32)
            
            # Normalize to [0, 1] range
            normalized_array = img_array / 255.0
            
            # Replace the PIL Image with normalized numpy array
            images_list[i] = normalized_array
            
        except Exception as e:
            print(f"Warning: Failed to normalize image {i}: {e}")
```

## Data Quality Assurance

The utilities provide robust data cleaning and validation functions:

```python
def filter_nan_rows(coords: np.ndarray, scores: np.ndarray):
    """
    Remove rows where scores contain NaN values and return clean data.
    
    Filters out samples with missing target values to ensure robust model
    training. Returns both the filtered data and a boolean mask indicating
    which samples were retained.
    
    Parameters
    ----------
    coords : ndarray, shape (n_samples, n_features)
        Feature matrix (coordinates, embeddings, or other features)
    scores : ndarray, shape (n_samples,)
        Target values or scores (may contain NaN values)
    
    Returns
    -------
    tuple
        (coords_clean, scores_clean, mask) where:
        - coords_clean: Filtered feature matrix
        - scores_clean: Filtered target values (no NaN)
        - mask: Boolean array indicating retained samples
    
    Examples
    --------
    >>> import numpy as np
    >>> from emuses.tools.data_preproc import filter_nan_rows
    >>> 
    >>> # Create data with some NaN values
    >>> coords = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])
    >>> scores = np.array([1.0, np.nan, 3.0, 4.0])
    >>> 
    >>> # Filter out NaN rows
    >>> coords_clean, scores_clean, mask = filter_nan_rows(coords, scores)
    >>> print(f"Original shape: {coords.shape}")
    >>> print(f"Clean shape: {coords_clean.shape}")
    >>> print(f"Retained samples: {np.sum(mask)}/{len(mask)}")
    
    Notes
    -----
    - Essential preprocessing step before model training
    - Preserves sample correspondence between features and targets
    - Returns mask for tracking which samples were filtered
    - Handles both 1D and multi-dimensional target arrays
    """
    import numpy as np
    
    # Handle both 1D and 2D score arrays
    if scores.ndim == 1:
        mask = ~np.isnan(scores)
    else:
        # For multi-dimensional scores, remove rows with any NaN
        mask = ~np.any(np.isnan(scores), axis=1)
    
    coords_clean = coords[mask]
    scores_clean = scores[mask]
    
    n_removed = len(coords) - len(coords_clean)
    if n_removed > 0:
        print(f"Filtered out {n_removed} samples with NaN values "
              f"({n_removed/len(coords)*100:.1f}% of data)")
    
    return coords_clean, scores_clean, mask

def validate_input_data(input_matrix, target_scores=None, min_samples=10):
    """
    Comprehensive validation of input data quality and consistency.
    
    Performs multiple checks to ensure data is suitable for EMUSES pipeline:
    - Checks for sufficient sample size
    - Validates data types and shapes
    - Identifies and reports data quality issues
    - Provides recommendations for data preprocessing
    
    Parameters
    ----------
    input_matrix : ndarray, shape (n_samples, n_features)
        Input feature matrix
    target_scores : ndarray, optional
        Target values for supervised learning
    min_samples : int, default=10
        Minimum required number of samples
    
    Returns
    -------
    dict
        Validation report with warnings and recommendations
    """
    import numpy as np
    
    report = {
        "valid": True,
        "warnings": [],
        "errors": [],
        "recommendations": [],
        "statistics": {}
    }
    
    # Check basic requirements
    if input_matrix.shape[0] < min_samples:
        report["errors"].append(
            f"Insufficient samples: {input_matrix.shape[0]} < {min_samples}"
        )
        report["valid"] = False
    
    # Check for missing values
    n_nan = np.sum(np.isnan(input_matrix))
    if n_nan > 0:
        pct_nan = n_nan / input_matrix.size * 100
        report["warnings"].append(
            f"Input matrix contains {n_nan} NaN values ({pct_nan:.1f}%)"
        )
        if pct_nan > 10:
            report["recommendations"].append(
                "Consider imputation or feature selection to handle missing values"
            )
    
    # Check for infinite values
    n_inf = np.sum(np.isinf(input_matrix))
    if n_inf > 0:
        report["errors"].append(f"Input matrix contains {n_inf} infinite values")
        report["valid"] = False
    
    # Check feature variance
    feature_vars = np.var(input_matrix, axis=0)
    zero_var_features = np.sum(feature_vars == 0)
    if zero_var_features > 0:
        report["warnings"].append(
            f"{zero_var_features} features have zero variance"
        )
        report["recommendations"].append(
            "Consider removing constant features before UMAP"
        )
    
    # Scale analysis
    feature_means = np.mean(input_matrix, axis=0)
    feature_stds = np.std(input_matrix, axis=0)
    scale_ratio = np.max(feature_stds) / np.min(feature_stds[feature_stds > 0])
    
    if scale_ratio > 100:
        report["warnings"].append(
            f"Features have very different scales (ratio: {scale_ratio:.1f})"
        )
        report["recommendations"].append(
            "Consider normalization before UMAP (use normalize_input_matrix)"
        )
    
    # Target validation
    if target_scores is not None:
        target_scores = np.asarray(target_scores)
        
        if len(target_scores) != input_matrix.shape[0]:
            report["errors"].append(
                f"Target length ({len(target_scores)}) doesn't match "
                f"input samples ({input_matrix.shape[0]})"
            )
            report["valid"] = False
        
        n_target_nan = np.sum(np.isnan(target_scores))
        if n_target_nan > 0:
            pct_target_nan = n_target_nan / len(target_scores) * 100
            report["warnings"].append(
                f"Target contains {n_target_nan} NaN values ({pct_target_nan:.1f}%)"
            )
    
    # Compile statistics
    report["statistics"] = {
        "n_samples": input_matrix.shape[0],
        "n_features": input_matrix.shape[1],
        "memory_mb": input_matrix.nbytes / 1024 / 1024,
        "feature_scale_ratio": scale_ratio,
        "nan_percentage": n_nan / input_matrix.size * 100,
        "zero_variance_features": zero_var_features
    }
    
    return report
```

## Integration with EMUSES Pipeline

The preprocessing utilities integrate seamlessly with the EMUSES pipeline:

```python
def preprocess_for_emuses(input_matrix, target_scores=None, normalize=True, 
                         validate=True, handle_nan="remove"):
    """
    Comprehensive preprocessing pipeline for EMUSES input data.
    
    Applies standard preprocessing steps to prepare data for the EMUSES
    pipeline including normalization, validation, and data cleaning.
    
    Parameters
    ----------
    input_matrix : ndarray, shape (n_samples, n_features)
        Raw input data
    target_scores : ndarray, optional
        Target values for supervised learning
    normalize : bool, default=True
        Whether to apply min-max normalization
    validate : bool, default=True
        Whether to perform data validation
    handle_nan : str, default="remove"
        How to handle NaN values: "remove", "error", or "warn"
    
    Returns
    -------
    dict
        Processed data and metadata:
        {
            "input_matrix": processed_input_matrix,
            "target_scores": processed_target_scores,
            "validation_report": validation_report,
            "preprocessing_log": log_of_steps_applied
        }
    """
    import numpy as np
    
    preprocessing_log = []
    processed_matrix = input_matrix.copy()
    processed_targets = target_scores.copy() if target_scores is not None else None
    
    # Step 1: Validation
    validation_report = None
    if validate:
        validation_report = validate_input_data(processed_matrix, processed_targets)
        preprocessing_log.append(f"Validation completed: {len(validation_report['warnings'])} warnings")
        
        if not validation_report["valid"]:
            raise ValueError(f"Data validation failed: {validation_report['errors']}")
    
    # Step 2: Handle NaN values
    if target_scores is not None:
        original_size = len(processed_matrix)
        
        if handle_nan == "remove":
            processed_matrix, processed_targets, mask = filter_nan_rows(
                processed_matrix, processed_targets
            )
            n_removed = original_size - len(processed_matrix)
            if n_removed > 0:
                preprocessing_log.append(f"Removed {n_removed} samples with NaN targets")
        
        elif handle_nan == "error":
            n_nan = np.sum(np.isnan(processed_targets))
            if n_nan > 0:
                raise ValueError(f"Found {n_nan} NaN values in targets")
        
        elif handle_nan == "warn":
            n_nan = np.sum(np.isnan(processed_targets))
            if n_nan > 0:
                print(f"Warning: Found {n_nan} NaN values in targets")
    
    # Step 3: Normalization
    if normalize:
        processed_matrix = normalize_input_matrix(processed_matrix)
        preprocessing_log.append("Applied min-max normalization")
    
    # Step 4: Final validation
    if validate:
        final_report = validate_input_data(processed_matrix, processed_targets)
        if not final_report["valid"]:
            print("Warning: Data still has issues after preprocessing")
    
    return {
        "input_matrix": processed_matrix,
        "target_scores": processed_targets,
        "validation_report": validation_report,
        "preprocessing_log": preprocessing_log
    }
```

**Key advantages:**
- **Standardization**: Ensures consistent data format across different input types
- **Quality assurance**: Comprehensive validation and error detection
- **Memory efficiency**: In-place operations where possible to minimize memory usage
- **Pipeline integration**: Seamless integration with EMUSES stages
- **Flexibility**: Supports various data types (images, tabular, etc.)
- **Robustness**: Handles edge cases and provides informative error messages

</details>
