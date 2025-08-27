from setuptools import setup, find_packages
import subprocess
import sys
from packaging import version


def get_bcblib_requirement():
    """
    Determine bcblib installation method with intelligent fallback strategy.
    
    Priority:
    1. PyPI if version >= required
    2. Main branch if version >= required
    3. Dev branch (latest development)
    """
    required_version = "0.5.0"  # Updated to match new dev branch version
    
    try:
        # Check PyPI version first
        result = subprocess.run([
            sys.executable, "-m", "pip", "index", "versions", "bcblib"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if 'Available versions:' in line:
                    versions_str = line.split('Available versions:')[1].strip()
                    available_versions = [v.strip() for v in versions_str.split(',')]
                    if available_versions:
                        latest_pypi = available_versions[0]
                        if version.parse(latest_pypi) >= version.parse(required_version):
                            print(f"Using bcblib {latest_pypi} from PyPI")
                            return f"bcblib>={required_version}"
                    break
    
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass
    
    # Check main branch version via GitHub API
    try:
        import urllib.request
        import urllib.parse
        
        # Get main branch setup.py content
        url = "https://raw.githubusercontent.com/chrisfoulon/BCBlib/main/setup.py"
        with urllib.request.urlopen(url, timeout=10) as response:
            content = response.read().decode('utf-8')
            
        # Extract version from setup.py content
        for line in content.split('\n'):
            if 'version=' in line and 'Update the version number' in line:
                # Extract version string like "version='0.4.1'"
                version_part = line.split('version=')[1].split(',')[0].strip()
                main_version = version_part.strip('\'"')
                
                if version.parse(main_version) >= version.parse(required_version):
                    print(f"Using bcblib {main_version} from GitHub main branch")
                    return "bcblib @ git+https://github.com/chrisfoulon/BCBlib.git@main"
                break
                
    except Exception:
        pass
    
    # Fallback to dev branch (latest development version)
    print(f"Using bcblib latest from GitHub dev branch (requires >={required_version})")
    return "bcblib @ git+https://github.com/chrisfoulon/BCBlib.git@dev"


setup(
    name="emuses",
    version="0.9.0-dev",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "emuses=emuses.cli.main:main",
        ],
    },
    install_requires=[
        # Core Python packages
        "numpy",
        "pandas",
        "Pillow",
        "scikit-learn",
        "scipy",
        "tqdm",
        "joblib",
        "matplotlib",
        "seaborn",
        
        # Neuroimaging packages
        "nibabel",
        "nilearn",
        "mne",
        "pybids",
        get_bcblib_requirement(),
        
        # Machine Learning packages
        "umap-learn",
        "hdbscan",
        "xgboost",
        "statsmodels",
        "pykrige",
        "gpy",
        "optuna",
        "optuna-integration[sklearn]",
        "torch",
        "lightgbm",
        
        # Web Framework & API packages (Critical for service)
        "fastapi",
        "fastapi-users[sqlalchemy,oauth]",
        "uvicorn",
        "slowapi",
        "python-multipart",
        
        # CLI packages (Critical for CLI)
        "typer",
        "requests",
        "httpx",
        "psutil",
        
        # Visualization & UI packages
        "plotly",
        "streamlit",
        "kaleido",
        
        # Data processing packages
        "narwhals",
        "optuna-dashboard",
        
        # Observability packages (Critical for service)
        "prometheus-client>=0.19.0",
        "structlog>=23.2.0",
    ],
    extras_require={
        # Cloud storage support
        "cloud": [
            "boto3",
            "azure-storage-blob",
            "google-cloud-storage",
        ],
        
        # Caching support
        "cache": [
            "redis>=5.0.0",
            "pymemcache>=4.0.0",
        ],
        
        # Enterprise features
        "enterprise": [
            "hvac>=1.0.0",  # HashiCorp Vault integration
        ],
        
        # Development and testing
        "dev": [
            "pytest",
            "pytest-asyncio",
            "moto[s3]>=5.1.0",
            "testcontainers>=4.0.0",
            "pytest-servers>=0.5.0",
        ],
        
        # All optional features
        "all": [
            "boto3",
            "azure-storage-blob",
            "google-cloud-storage",
            "redis>=5.0.0",
            "pymemcache>=4.0.0",
            "hvac>=1.0.0",
        ],
    },
)
