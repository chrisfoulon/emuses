from setuptools import setup, find_packages

setup(
    name="emuses",
    version="0.7.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "emuses=emuses.scripts.main:main",
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
        "bcblib",
        
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
        
        # Development & Testing packages
        "pytest",
        "pytest-asyncio",
        
        # Data processing packages
        "narwhals",
        "optuna-dashboard",
    ],
)
