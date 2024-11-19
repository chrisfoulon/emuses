from pathlib import Path

import hdbscan
import joblib
import numpy as np
from sklearn.metrics import silhouette_score


def evaluate_hdbscan(filtered_coordinates, size_factor=0.5):
    """
    Automatically selects the best parameters for HDBSCAN clustering.

    Parameters:
    filtered_coordinates (np.array): Array of shape (n_samples, 2) containing the filtered coordinates.
    size_factor (float): Fraction of total data points to use as the upper bound for `min_cluster_size`.

    Returns:
    best_params (dict): Best parameters and corresponding metrics (stability, silhouette).
    best_clusterer (HDBSCAN object): Trained HDBSCAN model with the best parameters.
    """
    if filtered_coordinates.shape[0] <= 1:
        print("Insufficient data for clustering.")
        return None, {}

    # Determine dynamic range for min_cluster_size and min_samples
    n_samples = filtered_coordinates.shape[0]
    max_cluster_size = int(size_factor * n_samples)
    # TODO might need to adjust the number of clusters and numuber of values to test
    min_cluster_sizes = np.linspace(2, max(2, max_cluster_size), num=5, dtype=int).tolist()
    min_samples_list = [1, 2, 5, 10]

    best_score = -np.inf
    best_params = {}
    best_clusterer = None

    for min_cluster_size in min_cluster_sizes:
        for min_samples in min_samples_list:
            try:
                clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, min_samples=min_samples)
                labels = clusterer.fit_predict(filtered_coordinates)

                # Ignore results with no clusters
                if len(set(labels)) > 1:
                    stability = np.mean(clusterer.cluster_persistence_)
                    silhouette = silhouette_score(filtered_coordinates, labels)

                    # Combine metrics to select the best clustering
                    score = stability + silhouette
                    if score > best_score:
                        best_score = score
                        best_params = {
                            "min_cluster_size": min_cluster_size,
                            "min_samples": min_samples,
                            "stability": stability,
                            "silhouette": silhouette,
                            "score": score
                        }
                        best_clusterer = clusterer
            except ValueError as e:
                print(f"Failed for min_cluster_size={min_cluster_size}, min_samples={min_samples}: {e}")
                continue

    if best_params:
        print("Best parameters found:")
        print(best_params)
        with open("best_hdbscan_params.txt", "w") as file:
            file.write(str(best_params))
    else:
        print("No valid clustering found.")

    return best_clusterer, best_params


def cluster_coordinates(filtered_coordinates, size_factor=0.5):
    """
    Perform HDBSCAN clustering on filtered coordinates with automated parameter selection.

    Parameters:
    filtered_coordinates (np.array): Array of shape (n_samples, 2) containing the filtered coordinates.
    size_factor (float): Fraction of total data points to use as the upper bound for `min_cluster_size`.

    Returns:
    clusterer (HDBSCAN object): Trained HDBSCAN model with the best parameters.
    cluster_labels (np.array): Cluster labels for the filtered coordinates.
    best_params (dict): Best parameters and corresponding metrics.
    """
    if filtered_coordinates.shape[0] > 0:
        # Call the automated evaluation function to find the best parameters
        best_clusterer, best_params = evaluate_hdbscan(filtered_coordinates, size_factor=size_factor)

        if best_clusterer:
            # Use the best clusterer to generate labels
            cluster_labels = best_clusterer.labels_
        else:
            print("No valid clustering found. Returning empty labels.")
            cluster_labels = np.array([])
            best_params = {}
    else:
        print("Insufficient data for clustering.")
        best_clusterer = None
        cluster_labels = np.array([])
        best_params = {}

    return best_clusterer, cluster_labels, best_params


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
