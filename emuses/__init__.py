"""
EMUSES - Enhanced Multimodal Unified Statistical Embedding System

A comprehensive toolkit for multimodal neuroimaging analysis using
dimensionality reduction, clustering, and predictive modeling.
"""

__version__ = "0.9.0-dev"

# Version info tuple for programmatic access
__version_info__ = tuple(
    int(part) if part.isdigit() else part
    for part in __version__.replace('-', '.').split('.')
)

__all__ = ["__version__", "__version_info__"]
