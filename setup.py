from setuptools import setup, find_packages

setup(
    name='emuses',
    version='0.6',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'emuses=emuses.scripts.main:main',
        ],
    },
    install_requires=[
        'numpy',
        'pandas',
        'Pillow',
        'scikit-learn',
        'scipy',
        'tqdm',
        'nibabel',
        'nilearn',
        'joblib',
        'statsmodels',
        'mne',
        'umap-learn',
        'matplotlib',
        'seaborn',
        'bcblib',
        'hdbscan',
        'pytest',
        'pybids',
        'plotly',
        'streamlit',
        'pykrige',
        'narwhals',
        'xgboost',
        'kaleido'
    ],
)