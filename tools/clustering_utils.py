from pathlib import Path

import hdbscan
import joblib
import numpy as np


def cluster_coordinates(filtered_coordinates, min_cluster_size=5):
    """
    Perform HDBSCAN clustering on filtered coordinates.

    Parameters:
    filtered_coordinates (np.array): Array of shape (n_samples, 2) containing the filtered coordinates.
    min_cluster_size (int): Minimum cluster size for HDBSCAN.

    Returns:
    clusterer (HDBSCAN object): Trained HDBSCAN model.
    cluster_labels (np.array): Cluster labels for the filtered coordinates.
    """
    # Perform HDBSCAN clustering on filtered coordinates
    if filtered_coordinates.shape[0] > 0:
        try:
            clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size)
            cluster_labels = clusterer.fit_predict(filtered_coordinates)
        except ValueError as e:
            print(f"Clustering failed due to insufficient data: {e}")
            clusterer = None
            cluster_labels = np.array([])
    else:
        print("Insufficient data for clustering.")
        clusterer = None
        cluster_labels = np.array([])

    return clusterer, cluster_labels


def save_hdbscan_model(clusterer, output_folder, prefix='', model_name='hdbscan_model', joblib_version=None):
    """
    Save an HDBSCAN model to a file based on the filename convention and system joblib version.

    Parameters:
    clusterer (HDBSCAN object): Trained HDBSCAN model to save.
    output_folder (Path or str): The directory where the HDBSCAN model will be saved.
    prefix (str): Prefix for the HDBSCAN model filename.
    model_name (str): Base name of the model.
    joblib_version (str, optional): Version of joblib used in the saved file. If None, the current system joblib version is used.

    Returns:
    filepath (Path): Path of the saved model file.
    """
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    if joblib_version is None or not joblib_version:
        joblib_version = joblib.__version__
    if prefix:
        filename = f"{prefix}_{model_name}_joblib{joblib_version}.joblib"
    else:
        filename = f"{model_name}_joblib{joblib_version}.joblib"
    filepath = output_folder / filename

    # Save the HDBSCAN model to a file
    try:
        joblib.dump(clusterer, filepath)
        print(f"Saved HDBSCAN model to: {filepath}")
    except Exception as e:
        print(f"Failed to save HDBSCAN model: {e}")

    return filepath


def is_hdbscan_file(filepath):
    """
    Check if a file is an HDBSCAN model file based on the filename convention.

    Parameters:
    filepath (Path or str): Path to the file to check.

    Returns:
    is_hdbscan (bool): True if the file is an HDBSCAN model file, False otherwise.
    """
    return str(filepath).endswith('.joblib')


def load_hdbscan_model(base_path, prefix='', model_name='hdbscan_model', joblib_version=None, max_attempts=10):
    """
    Load an HDBSCAN model based on the filename convention and system joblib version.

    Parameters:
    base_path (Path or str): The directory where HDBSCAN models are saved.
    prefix (str): Prefix for the HDBSCAN model filename.
    model_name (str): Base name of the model.
    joblib_version (str, optional): Version of joblib used in the saved file. If None, the current system joblib version is used.
    max_attempts (int): Maximum number of attempts to load different versions of the model.

    Returns:
    loaded_hdbscan (object or None): Loaded HDBSCAN model or None if loading failed.
    filepath (Path): Path of the loaded or next available filename.
    """
    base_path = Path(base_path)
    if joblib_version is None or not joblib_version:
        joblib_version = joblib.__version__
    current_joblib_version = joblib.__version__
    if prefix:
        filename_pattern = f"{prefix}_{model_name}_joblib{joblib_version}.joblib"
    else:
        filename_pattern = f"{model_name}_joblib{joblib_version}.joblib"
    filepath = base_path / filename_pattern

    # Try to load the file with the given filename convention
    if filepath.exists() and is_hdbscan_file(filepath):
        try:
            loaded_hdbscan = joblib.load(filepath)
            print(f"Successfully loaded HDBSCAN model from: {filepath}")
            return loaded_hdbscan, filepath
        except Exception as e:
            print(f"Failed to load HDBSCAN model: {e}")
            loaded_hdbscan = None
    else:
        print(f"No HDBSCAN model found at: {filepath}")
        loaded_hdbscan = None

    return loaded_hdbscan, filepath
