# emuses/inference/__init__.py

"""
EMUSES Inference API Integration Module

This module provides the main entry point for the EMUSES inference API,
offering a streamlined sklearn-like interface for EMUSES core UMAP dimensionality
reduction and clustering functionality.

Example usage:
    >>> from emuses.inference import EMUSESInferenceAPI
    >>> api = EMUSESInferenceAPI(model_dir="./models")
    >>> embeddings = api.fit_transform(X_train)
    >>> new_embeddings = api.transform(X_test)
    >>> cluster_labels = api.predict_clusters(X_test)

Features:
- Simple sklearn-like interface for UMAP and clustering
- Access to EMUSES feature engineering utilities
- Model persistence via ModelIOManager
- Integration with core EMUSES UMAPStage functionality
- No prediction modeling - focuses on dimensionality reduction
"""

from .api import EMUSESInferenceAPI

__all__ = ["EMUSESInferenceAPI", "create_inference_api", "get_default_config"]

# Version information
__version__ = "1.1.0"
__author__ = "EMUSES Development Team"
__description__ = "sklearn-like inference API for EMUSES core UMAP functionality"

# Configuration defaults
DEFAULT_CONFIG = {
    "model_dir": "./emuses_models",
    "random_state": 42,
    "umap_trials": 50,
    "umap_jobs": 1,
    "hdbscan_trials": 20,
    "hdbscan_jobs": 1,
    "hdbscan_approx_min_span_tree": True,
    "hdbscan_core_dist_n_jobs": -1,
    "enable_feature_engineering": False,
    "feature_methods": ["raw", "gwd"],
    "gwd_sigma": 0.1,
    "pcagwd_n_components": 10,
    "kernelpca_n_components": 30,
    "correlation_threshold": 0.25,
    "verbose": False,
}


def create_inference_api(**kwargs):
    """
    Create a new EMUSES inference API instance.

    Parameters
    ----------
    **kwargs
        Configuration parameters passed to EMUSESInferenceAPI

    Returns
    -------
    api : EMUSESInferenceAPI
        Configured API instance
    """
    return EMUSESInferenceAPI(**kwargs)


def get_default_config():
    """
    Get the default configuration for the inference API.

    Returns
    -------
    config : dict
        Default configuration dictionary
    """
    return DEFAULT_CONFIG.copy()


def create_api(**kwargs):
    """
    Create a new EMUSES inference API instance with default configuration.

    Parameters
    ----------
    **kwargs
        Additional configuration parameters to override defaults

    Returns
    -------
    api : EMUSESInferenceAPI
        Configured API instance

    Examples
    --------
    >>> from emuses.inference import create_api
    >>> api = create_api(random_state=123, model_dir="./my_models")
    >>> embeddings = api.fit_transform(X)
    >>> new_embeddings = api.transform(X_test)
    """
    config = DEFAULT_CONFIG.copy()
    config.update(kwargs)
    return EMUSESInferenceAPI(config=config)


def quick_fit_transform(X_train, X_test=None, **kwargs):
    """
    Convenience function for quick UMAP fitting and transformation.

    Parameters
    ----------
    X_train : array-like
        Training features
    X_test : array-like, optional
        Test features to transform
    **kwargs
        Additional configuration parameters

    Returns
    -------
    train_embeddings : np.ndarray
        Embeddings for X_train
    test_embeddings : np.ndarray, optional
        Embeddings for X_test (if provided)

    Examples
    --------
    >>> from emuses.inference import quick_fit_transform
    >>> train_emb, test_emb = quick_fit_transform(X_train, X_test, random_state=42)
    """
    api = create_api(**kwargs)
    train_embeddings = api.fit_transform(X_train)

    if X_test is not None:
        test_embeddings = api.transform(X_test)
        return train_embeddings, test_embeddings
    else:
        return train_embeddings


# Information about the API capabilities
API_INFO = {
    "description": "sklearn-like inference API for EMUSES core UMAP functionality",
    "features": [
        "UMAP dimensionality reduction with optimization",
        "HDBSCAN clustering integration",
        "Feature engineering utilities from EMUSES",
        "Model persistence via ModelIOManager",
        "sklearn-compatible interface",
        "Integration with core UMAPStage functionality",
    ],
    "core_functionality": [
        "UMAP dimensionality reduction",
        "HDBSCAN clustering",
        "Embedding rescaling and normalization",
    ],
    "feature_engineering": [
        "Raw coordinates",
        "Gaussian Weighted Distances (GWD)",
        "PCA + GWD features",
        "Kernel PCA + GWD features",
        "Correlation filtering",
    ],
}


def get_api_info():
    """
    Get information about the EMUSES inference API capabilities.

    Returns
    -------
    info : dict
        Dictionary containing API information and capabilities
    """
    return API_INFO.copy()


def check_requirements():
    """
    Check if all required dependencies are available for EMUSES core functionality.

    Returns
    -------
    status : dict
        Dictionary containing requirement check results
    """
    requirements = {
        "numpy": True,
        "pandas": True,
        "umap-learn": True,
        "hdbscan": True,
        "joblib": True,
        "scikit-learn": True,
    }

    missing = []

    try:
        import numpy

        requirements["numpy"] = True
    except ImportError:
        requirements["numpy"] = False
        missing.append("numpy")

    try:
        import pandas

        requirements["pandas"] = True
    except ImportError:
        requirements["pandas"] = False
        missing.append("pandas")

    try:
        import umap

        requirements["umap-learn"] = True
    except ImportError:
        requirements["umap-learn"] = False
        missing.append("umap-learn")

    try:
        import hdbscan

        requirements["hdbscan"] = True
    except ImportError:
        requirements["hdbscan"] = False
        missing.append("hdbscan")

    try:
        import joblib

        requirements["joblib"] = True
    except ImportError:
        requirements["joblib"] = False
        missing.append("joblib")

    try:
        import sklearn

        requirements["scikit-learn"] = True
    except ImportError:
        requirements["scikit-learn"] = False
        missing.append("scikit-learn")

    return {
        "requirements": requirements,
        "missing": missing,
        "all_satisfied": len(missing) == 0,
    }
