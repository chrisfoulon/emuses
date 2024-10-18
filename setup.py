from setuptools import setup, find_packages

setup(
    name='emuse',
    version='0.3',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'emuse=emuse.main:main',  # 'emuse' is the command, 'emuse.main:main' is the function to execute
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
        'plotly'
    ],
)