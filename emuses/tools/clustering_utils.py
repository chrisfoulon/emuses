from pathlib import Path

import hdbscan
import joblib
import numpy as np
import optuna
from hdbscan import validity
from sklearn.metrics import silhouette_score

from emuses.tools.optim_utils import calculate_score, suggest_parameters, calculate_composite_score


def compute_cluster_persistence(clusterer, normalized=True, max_value=1.0):
    """
    Compute the mean persistence of clusters from an HDBSCAN clusterer.

    If normalized is True, the persistence is divided by max_value (capped at 1).

    In the special case where every point is labeled as noise, this function returns 0,
    because even if the underlying persistence values might be high (or undefined),
    we do not want to reward an all-noise clustering.

    Parameters:
        clusterer: A fitted HDBSCAN object.
        normalized (bool): Whether to return a normalized value.
        max_value (float): The maximum expected persistence value.

    Returns:
        float: Cluster persistence (or 0 if all points are noise).
    """
    # Check if labels are available and all points are noise.
    if hasattr(clusterer, 'labels_') and np.all(clusterer.labels_ == -1):
        return 0.0

    # Compute the raw persistence.
    if hasattr(clusterer, 'cluster_persistence_') and len(clusterer.cluster_persistence_) > 0:
        persistence = np.mean(clusterer.cluster_persistence_)
    else:
        persistence = 0.0

    if not normalized:
        return persistence
    return min(1, persistence / max_value)



def compute_noise_ratio(labels, normalized=True):
    """
    Compute the noise ratio of the clustering.

    If normalized is True, returns 1 - (noise ratio), so that 1 is best (no noise)
    and 0 is worst (all noise).

    Parameters:
        labels (np.ndarray): Cluster labels (-1 indicates noise).
        normalized (bool): Whether to return a normalized value.

    Returns:
        float: Noise ratio (or normalized noise score).
    """
    noise_points = np.sum(labels == -1)
    total_points = len(labels)
    raw_ratio = noise_points / total_points if total_points > 0 else 0.0
    if not normalized:
        return raw_ratio
    return 1 - raw_ratio


def compute_dbcv(embeddings, labels, normalized=True):
    """
    Compute the DBCV score using HDBSCAN's validity module.

    Parameters:
        embeddings (np.ndarray): The original input data (or appropriate feature matrix).
        labels (np.ndarray): Cluster labels obtained from HDBSCAN.
        normalized (bool): If True, transforms the score from [-1,1] to [0,1].

    Returns:
        float: The DBCV score (normalized if requested).
    """
    embeddings = np.asarray(embeddings, dtype=np.float64)
    dbcv_score = validity.validity_index(embeddings, labels)
    if normalized:
        return (dbcv_score + 1) / 2
    return dbcv_score


def evaluate_clustering_metrics(clusterer, embeddings, metrics_config=None):
    """
    Evaluate clustering metrics based on a provided configuration.

    Parameters:
        clusterer (HDBSCAN object): Fitted HDBSCAN clusterer.
        embeddings (np.ndarray): The embedding coordinates.
        metrics_config (dict, optional): Dictionary defining which metrics to compute.
            For example, optim_dict["metrics"]["hdbscan"]. If None, defaults to:
                {"noise_ratio": {}, "dbcv": {}}

    Returns:
        dict: Computed clustering metrics.
    """
    labels = clusterer.labels_
    computed_metrics = {}

    # Set default configuration if none provided.
    if metrics_config is None:
        metrics_config = {"noise_ratio": {}, "dbcv": {}, "cluster_persistence": {}}

    # Loop over the metrics requested in the config.
    for metric_name in metrics_config.keys():
        if metric_name == "noise_ratio":
            computed_metrics["noise_ratio"] = compute_noise_ratio(labels)
        elif metric_name in ("dbcv"):
            # We assume here that dbcv and validity_index refer to the same computation.
            computed_metrics["dbcv"] = compute_dbcv(embeddings, labels)
        elif metric_name == "cluster_persistence":
            computed_metrics["cluster_persistence"] = compute_cluster_persistence(clusterer)
        else:
            # If you add more metrics in the future, handle them here.
            print(f"Warning: No computation defined for metric '{metric_name}'.")

    return computed_metrics


###########################################################
# --- Inner (HDBSCAN) Optimization Using optim_dict --- #
###########################################################

def inner_optimize_hdbscan(embeddings, optim_dict, n_inner_trials=20):
    """
    For a given UMAP embedding, optimize HDBSCAN parameters.

    Parameters:
      embeddings: np.ndarray (the UMAP latent space)
      optim_dict: dict, the full optimization dictionary. Expected to have:
                  optim_dict["param"]["hdbscan"] and optim_dict["metrics"]["hdbscan"].
      n_inner_trials: int, number of inner trials.

    Returns:
      best_params, best_score, best_clusterer, best_labels, best_metrics
    """
    # Enforce the correct key for HDBSCAN parameters.
    if "hdbscan" not in optim_dict["param"]:
        raise ValueError("The optimization dictionary must have a 'hdbscan' key in optim_dict['param'].")

    inner_optim_dict = {
        "param": {"hdbscan": optim_dict["param"]["hdbscan"]},
        "metrics": {"hdbscan": optim_dict["metrics"]["hdbscan"]}
    }

    def inner_objective(inner_trial):
        params_all = suggest_parameters(inner_trial, inner_optim_dict)
        hdbscan_params = params_all.get("hdbscan", params_all)
        clusterer = hdbscan.HDBSCAN(**hdbscan_params)
        clusterer.fit(embeddings)
        metrics = evaluate_clustering_metrics(clusterer, embeddings, inner_optim_dict["metrics"]["hdbscan"])
        # Wrap the metrics under the "hdbscan" key to match the nested configuration
        score = calculate_composite_score({"hdbscan": metrics},
                                          inner_optim_dict["metrics"])
        return score

    inner_study = optuna.create_study(direction="maximize")
    inner_study.optimize(inner_objective, n_trials=n_inner_trials)

    best_params = inner_study.best_params
    best_score = inner_study.best_value

    # If best_params is empty (which can happen if all parameters are fixed), fall back to the fixed dict.
    if not best_params:
        best_params = inner_optim_dict["param"]["hdbscan"]

    best_hdbscan_params = best_params.get("hdbscan", best_params)

    # Re-train best HDBSCAN model using the best parameters.
    best_clusterer = hdbscan.HDBSCAN(**best_hdbscan_params)
    best_labels = best_clusterer.fit_predict(embeddings)
    best_metrics = evaluate_clustering_metrics(best_clusterer, embeddings)
    return best_params, best_score, best_clusterer, best_labels, best_metrics



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
    # TODO might need to adjust the number of clusters and number of values to test
    # min_cluster_sizes = np.linspace(2, max(2, max_cluster_size), num=5, dtype=int).tolist()
    min_cluster_sizes = [5]
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

    return best_clusterer, best_params


def cluster_coordinates(filtered_coordinates, size_factor=0.5):
    """
    Perform HDBSCAN clustering on filtered coordinates with automated parameter selection.

    Parameters:
    filtered_coordinates (np.array): Array of shape (n_samples, 2) containing the filtered coordinates.
    size_factor (float): Fraction of total data points to use as the upper bound for `min_cluster_size`.

    Returns:
    best_clusterer (HDBSCAN object): Trained HDBSCAN model with the best parameters.
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
