# Feature Engineering Utilities

The Feature Engineering Utilities provide sklearn-compatible transformers for generating sophisticated features from UMAP embeddings and high-dimensional input data. These transformers enable the creation of multiple feature representations including raw coordinates, Gaussian-weighted distances (GWD), PCA-compressed GWD, Kernel PCA-compressed GWD, and correlation-filtered features that are optimized for various machine learning models within the EMUSES pipeline.

<details><summary>🛠️ Level 2 · Key API table</summary>

| Class/Function | Purpose | Inputs | Outputs | Side-effects |
|---|---|---|---|---|
| `RawCoords` | Pass-through transformer for raw coordinates | `X: ndarray` | `ndarray` | None |
| `GWD` | Gaussian-weighted distance features | `X: ndarray (n_samples, n_dims)` | `ndarray (n_samples, n_centers)` | Stores fit data internally |
| `PCAGWD` | PCA compression of GWD features | `X: ndarray` | `ndarray (n_samples, n_components)` | Fits PCA model internally |
| `KernelPCAGWD` | Non-linear compression of GWD via Kernel PCA | `X: ndarray` | `ndarray (n_samples, n_components)` | Fits Kernel PCA model internally |
| `CorrFilter` | Correlation-based feature selection for GWD | `X: ndarray, y: ndarray` | `ndarray (n_samples, n_selected)` | Computes correlation mask |

</details>

<details><summary>🔍 Level 3 · Code walk-through</summary>

## RawCoords Transformer

The `RawCoords` class serves as a pass-through transformer that maintains sklearn compatibility while preserving original coordinate features:

```python
class RawCoords(BaseEstimator, TransformerMixin):
    """
    Identity transformer for raw coordinates.
    
    This transformer serves as a baseline feature representation that passes
    input coordinates unchanged while maintaining sklearn pipeline compatibility.
    Commonly used as the first feature type in ensemble models.
    
    Parameters
    ----------
    None
    
    Returns
    -------
    X : ndarray, shape (n_samples, n_features)
        Input data unchanged
    """
    
    def fit(self, X, y=None):
        """No-op fit method for sklearn compatibility."""
        return self

    def transform(self, X):
        """Return input data unchanged."""
        return X
```

**Key applications:**
- Baseline feature representation in feature unions
- Preserving original embedding coordinates in ensemble models
- Maintaining sklearn pipeline compatibility for identity transformations

## Gaussian-Weighted Distance (GWD) Features

The `GWD` class generates distance-based features using Gaussian kernels, creating rich representations of local neighborhood structure:

```python
class GWD(BaseEstimator, TransformerMixin):
    """
    Gaussian-weighted distances to all training data points.
    
    Computes a kernel-based similarity matrix where each row represents
    the Gaussian-weighted distances from one sample to all training samples.
    This creates rich neighborhood features that capture local structure.
    
    Parameters
    ----------
    sigma : float, default=0.1
        Bandwidth parameter for Gaussian kernel. Smaller values create
        more localized features, larger values create smoother features.
    agg : str, default='none'
        Aggregation method for distance features:
        - 'none': Return full distance matrix (n_samples, n_training_points)
        - 'mean': Return mean distance per sample (n_samples, 1)
        - 'sum': Return sum of distances per sample (n_samples, 1)
    
    Returns
    -------
    W : ndarray, shape depends on agg parameter
        Gaussian-weighted distance features
    """
    
    def fit(self, X, y=None):
        """Store training data as reference points for distance computation."""
        self.fit_X_ = X.copy()
        return self

    def transform(self, X):
        """Compute Gaussian-weighted distances to training data."""
        # Compute squared Euclidean distances: d²(x_i, x_j)
        d2 = ((X[:, None, :] - self.fit_X_[None, :, :]) ** 2).sum(-1)
        # Apply Gaussian kernel: exp(-d²/(2σ²))
        W = np.exp(-d2 / (2 * self.sigma**2))
        
        if self.agg == "mean":
            return W.mean(1, keepdims=True)
        elif self.agg == "sum":
            return W.sum(1, keepdims=True)
        return W  # Full distance matrix
```

**Mathematical foundation:**
- **Gaussian kernel**: `W[i,j] = exp(-||x_i - x_j||²/(2σ²))`
- **Similarity interpretation**: High values indicate similar points, low values indicate dissimilar points
- **Bandwidth control**: `σ` parameter controls locality vs. smoothness trade-off

**Key applications:**
- Creating locality-aware features for regression models
- Capturing neighborhood structure in embedding space
- Providing kernel-based similarity features for machine learning

## PCA-Compressed GWD Features

The `PCAGWD` class combines GWD computation with Principal Component Analysis for dimensionality reduction:

```python
class PCAGWD(BaseEstimator, TransformerMixin):
    """
    PCA compression of Gaussian-weighted distance matrix.
    
    Computes GWD features and applies PCA to reduce dimensionality while
    preserving maximum variance. Supports both fixed component count and
    variance threshold-based component selection.
    
    Parameters
    ----------
    sigma : float, default=0.1
        Gaussian kernel bandwidth parameter
    n_comp : int, optional
        Number of PCA components to retain (ignored if var_thr is set)
    var_thr : float, optional
        Cumulative variance threshold (0-1) for automatic component selection
    
    Returns
    -------
    X_pca : ndarray, shape (n_samples, n_components)
        PCA-transformed GWD features
    """
    
    def fit(self, X, y=None):
        """Fit PCA on GWD matrix computed from training data."""
        self._X_fit = X.copy()
        
        # Compute training GWD matrix
        d2 = ((X[:, None, :] - X[None, :, :]) ** 2).sum(-1)
        W = np.exp(-d2 / (2 * self.sigma**2))

        # Determine number of components
        n_comp = self.n_comp if self.var_thr is None else None
        self.pca_ = PCA(n_components=n_comp).fit(W)

        # Automatic component selection based on variance threshold
        if self.var_thr is not None:
            k = (np.searchsorted(
                np.cumsum(self.pca_.explained_variance_ratio_), 
                self.var_thr
            ) + 1)
            self.pca_ = PCA(n_components=k).fit(W)
        return self

    def transform(self, X):
        """Transform new data using fitted PCA model."""
        # Compute GWD between X and training data
        d2 = ((X[:, None, :] - self._X_fit[None, :, :]) ** 2).sum(-1)
        W = np.exp(-d2 / (2 * self.sigma**2))
        return self.pca_.transform(W)
```

**Key advantages:**
- **Dimensionality reduction**: Reduces high-dimensional GWD matrix to manageable size
- **Variance preservation**: Retains most informative distance patterns
- **Automatic component selection**: Supports variance threshold-based optimization
- **Computational efficiency**: Faster training and inference than full GWD

## Kernel PCA-Compressed GWD Features

The `KernelPCAGWD` class applies non-linear dimensionality reduction to GWD features using Kernel PCA:

```python
class KernelPCAGWD(BaseEstimator, TransformerMixin):
    """
    Non-linear compression of GWD via precomputed RBF Kernel PCA.
    
    Applies Kernel PCA to the GWD matrix using a precomputed RBF kernel,
    enabling non-linear feature compression that can capture complex
    neighborhood relationships in the embedding space.
    
    Parameters
    ----------
    sigma : float, default=0.1
        Gaussian kernel bandwidth for GWD computation
    n_comp : int, default=30
        Number of kernel PCA components to retain
    kpca_gamma : float, optional
        Kernel PCA gamma parameter (unused for precomputed kernels)
    
    Returns
    -------
    X_kpca : ndarray, shape (n_samples, n_components)
        Kernel PCA-transformed features
    """
    
    def fit(self, X, y=None):
        """Fit Kernel PCA on precomputed RBF kernel from GWD."""
        self._X_fit = X.copy()

        # Build RBF kernel matrix from GWD
        sq = ((X[:, None, :] - X[None, :, :]) ** 2).sum(-1)
        K = np.exp(-sq / (2 * self.sigma**2))

        # Fit Kernel PCA with precomputed kernel
        self.kpca_ = KernelPCA(
            n_components=self.n_comp,
            kernel="precomputed",
            eigen_solver="auto",
            remove_zero_eig=True,
        ).fit(K)
        return self

    def transform(self, X):
        """Transform new data using fitted Kernel PCA model."""
        # Compute GWD kernel rows between new X and training X
        sq = ((X[:, None, :] - self._X_fit[None, :, :]) ** 2).sum(-1)
        K_new = np.exp(-sq / (2 * self.sigma**2))
        return self.kpca_.transform(K_new)
```

**Technical details:**
- **Precomputed kernel**: Uses GWD matrix as precomputed RBF kernel
- **Non-linear mapping**: Captures non-linear relationships in distance space
- **Eigen decomposition**: Automatic eigenvalue-based component selection
- **Transform capability**: Supports out-of-sample transformation

## Correlation-Based Feature Selection

The `CorrFilter` class performs supervised feature selection based on correlation with target variables:

```python
class CorrFilter(BaseEstimator, TransformerMixin):
    """
    Correlation-based feature selection for GWD features.
    
    Selects GWD columns whose absolute Pearson correlation with the
    target variable exceeds a specified threshold. Prevents data leakage
    by computing correlations only on training data.
    
    Parameters
    ----------
    thr : float, default=0.25
        Minimum absolute correlation threshold for feature selection
    
    Returns
    -------
    X_filtered : ndarray, shape (n_samples, n_selected_features)
        Correlation-filtered features
    """
    
    def fit(self, X, y):
        """Compute correlation mask based on training data."""
        y = y.ravel()
        # Compute absolute Pearson correlations
        r = np.abs(np.corrcoef(X, y, rowvar=False)[-1, :-1])
        self.mask_ = r >= self.thr
        
        # Ensure at least one feature is selected
        if not self.mask_.any():
            self.mask_[np.argmax(r)] = True
        return self

    def transform(self, X):
        """Apply correlation mask to filter features."""
        return X[:, self.mask_]
```

**Key features:**
- **Supervised selection**: Uses target correlation for feature relevance
- **Leakage prevention**: Fits only on training data within CV folds
- **Fallback mechanism**: Always selects at least the most correlated feature
- **Threshold optimization**: Threshold can be optimized via Optuna hyperparameter search

## Integration with EMUSES Pipeline

These transformers integrate seamlessly with the EMUSES pipeline through the `models_utils.build_feature_union()` function:

```python
def build_feature_union(feat_cfg: dict, pretrained_ae=None):
    """
    Build sklearn FeatureUnion from configuration.
    
    Parameters
    ----------
    feat_cfg : dict
        Feature configuration specifying which transformers to include
    pretrained_ae : object, optional
        Pre-trained autoencoder for AE-based features
    
    Returns
    -------
    FeatureUnion
        Combined feature extraction pipeline
    """
    transformers = []
    
    if feat_cfg.get("raw_coords", False):
        transformers.append(("raw", RawCoords()))
    
    if feat_cfg.get("gwd", False):
        transformers.append(("gwd", GWD(
            sigma=feat_cfg.get("gwd_sigma", 0.1),
            agg=feat_cfg.get("gwd_agg", "none")
        )))
    
    if feat_cfg.get("pca_gwd", False):
        transformers.append(("pca_gwd", PCAGWD(
            sigma=feat_cfg.get("pca_gwd_sigma", 0.1),
            var_thr=feat_cfg.get("pca_gwd_var_thr", 0.95)
        )))
    
    if feat_cfg.get("kpca_gwd", False):
        transformers.append(("kpca_gwd", KernelPCAGWD(
            sigma=feat_cfg.get("kpca_gwd_sigma", 0.1),
            n_comp=feat_cfg.get("kpca_gwd_n_comp", 30)
        )))
    
    return FeatureUnion(transformers)
```

**Pipeline integration:**
- **Optuna optimization**: All parameters can be optimized via hyperparameter search
- **Cross-validation compatibility**: Transformers handle train/test splits correctly
- **Feature union support**: Multiple transformers can be combined in parallel
- **Preprocessing integration**: Works with StandardScaler and other sklearn preprocessors

</details>
