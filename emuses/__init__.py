"""
EMUSES - Enhanced Multimodal Unified Statistical Embedding System

A comprehensive toolkit for multimodal neuroimaging analysis using
dimensionality reduction, clustering, and predictive modeling.
"""

import sys
import platform

__version__ = "0.9.0-dev"

# Version info tuple for programmatic access
__version_info__ = tuple(
    int(part) if part.isdigit() else part
    for part in __version__.replace('-', '.').split('.')
)


def _check_macos_dependencies():
    """
    Check for OpenMP dependency on macOS and provide helpful error message.

    XGBoost and other ML libraries require OpenMP for multi-threading,
    which is not included with macOS by default. This check runs on import
    to catch missing dependencies early with actionable instructions.

    Only runs on macOS (Darwin) systems - zero overhead on Linux/Windows.
    """
    if platform.system() != 'Darwin':
        return

    try:
        import xgboost  # noqa: F401
    except Exception as e:
        error_str = str(e)
        if 'libomp.dylib' in error_str or 'OpenMP runtime' in error_str:
            print("""
╔══════════════════════════════════════════════════════════════════╗
║                    EMUSES: macOS Setup Required                   ║
╠══════════════════════════════════════════════════════════════════╣
║  XGBoost requires OpenMP, which is not installed on your system.  ║
║                                                                   ║
║  To fix this (one-time setup):                                    ║
║                                                                   ║
║    brew install libomp                                            ║
║                                                                   ║
║  Then restart your Python environment.                            ║
║                                                                   ║
║  Why? macOS doesn't include OpenMP by default. This enables       ║
║  high-performance machine learning libraries to use all CPU cores.║
╚══════════════════════════════════════════════════════════════════╝
""", file=sys.stderr)
            raise RuntimeError(
                "macOS OpenMP dependency missing. "
                "Run: brew install libomp"
            ) from e


# Run dependency check on import (macOS only)
_check_macos_dependencies()

__all__ = ["__version__", "__version_info__"]
