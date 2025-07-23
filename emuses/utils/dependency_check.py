"""
Lightweight dependency checking utilities for EMUSES.

This module provides fast dependency validation that can be integrated
into normal CLI and API startup without adding significant overhead.
"""

import importlib
import sys
from typing import List, Tuple, Optional
import warnings


def check_critical_dependencies() -> Tuple[bool, List[str]]:
    """
    Quick check of only the most critical dependencies.
    
    This is designed to be fast enough to run on CLI startup
    without adding noticeable delay.
    
    Returns
    -------
    Tuple[bool, List[str]]
        (all_critical_ok, missing_packages)
    """
    # Only check the most critical packages that would cause immediate failures
    critical_deps = {
        # CLI essentials
        'typer': 'CLI framework',
        'requests': 'HTTP client for service communication',
        
        # API service essentials (if using service mode)
        'fastapi': 'API framework',
        'uvicorn': 'ASGI server',
        'python_multipart': 'File upload support',
    }
    
    missing = []
    
    for module, description in critical_deps.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(module)
    
    return len(missing) == 0, missing


def get_install_command(missing_packages: List[str]) -> str:
    """Generate pip install command for missing packages."""
    # Map import names to package names where they differ
    package_mapping = {
        'python_multipart': 'python-multipart',
        'optuna.integration': 'optuna-integration[sklearn]',
        'pytest_asyncio': 'pytest-asyncio',
    }
    
    packages = [package_mapping.get(pkg, pkg) for pkg in missing_packages]
    return f"pip install {' '.join(packages)}"


def validate_on_cli_startup(show_warnings: bool = True) -> bool:
    """
    Lightweight validation suitable for CLI startup.
    
    Parameters
    ----------
    show_warnings : bool
        Whether to show warning messages for missing dependencies
        
    Returns
    -------
    bool
        True if all critical dependencies are available
    """
    all_ok, missing = check_critical_dependencies()
    
    if not all_ok and show_warnings:
        print("⚠️  Missing critical dependencies detected:")
        for pkg in missing:
            print(f"   - {pkg}")
        print(f"\nTo fix: {get_install_command(missing)}")
        print("Note: EMUSES may not function correctly until these are installed.\n")
    
    return all_ok


def validate_for_service_mode() -> bool:
    """
    Check dependencies specifically needed for FastAPI service mode.
    
    Returns
    -------
    bool
        True if service mode dependencies are available
    """
    service_deps = ['fastapi', 'uvicorn', 'slowapi', 'python_multipart']
    
    missing = []
    for dep in service_deps:
        try:
            importlib.import_module(dep)
        except ImportError:
            missing.append(dep)
    
    if missing:
        print("❌ FastAPI service mode dependencies missing:")
        for pkg in missing:
            print(f"   - {pkg}")
        print(f"\nTo fix: {get_install_command(missing)}")
        return False
    
    return True


def smart_import_with_help(module_name: str, package_name: Optional[str] = None, 
                          help_message: Optional[str] = None):
    """
    Import a module with helpful error message if it fails.
    
    Parameters
    ----------
    module_name : str
        Name of module to import
    package_name : str, optional
        Package name for pip install (if different from module)
    help_message : str, optional
        Custom help message
        
    Returns
    -------
    module or None
        The imported module, or None if import failed
    """
    try:
        return importlib.import_module(module_name)
    except ImportError as e:
        pkg_name = package_name or module_name
        default_msg = f"Missing dependency: {module_name}"
        
        if help_message:
            print(f"❌ {help_message}")
        else:
            print(f"❌ {default_msg}")
            
        print(f"   Install with: pip install {pkg_name}")
        print(f"   Original error: {e}")
        return None


# Quick validation that can be called from anywhere
def check_optuna_integration() -> bool:
    """
    Check if optuna-integration[sklearn] is available.
    
    Returns
    -------
    bool
        True if optuna integration is available
    """
    try:
        import optuna.integration
        return True
    except ImportError:
        return False


def validate_ml_dependencies() -> Tuple[bool, List[str]]:
    """
    Check ML dependencies that might be needed for pipeline execution.
    
    Returns
    -------
    Tuple[bool, List[str]]
        (all_ok, missing_packages)
    """
    ml_deps = {
        'optuna': 'Hyperparameter optimization',
        'optuna.integration': 'Optuna-sklearn integration',
        'torch': 'Deep learning framework',
        'lightgbm': 'Gradient boosting algorithms',
    }
    
    missing = []
    for module, description in ml_deps.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(module)
    
    return len(missing) == 0, missing


def quick_validate() -> bool:
    """
    Ultra-fast validation of core dependencies.
    
    This is designed to be called from CLI entry points without
    adding noticeable startup delay.
    """
    try:
        import typer, requests
        return True
    except ImportError:
        return False