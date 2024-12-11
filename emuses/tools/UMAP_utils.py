import joblib
import optuna
from joblib import dump, load
from pathlib import Path
from itertools import product
import numpy as np
import umap
import warnings
from joblib import __version__ as joblib_version
from scipy.stats import entropy
from sklearn.manifold import trustworthiness
from sklearn.metrics import silhouette_score, pairwise_distances
from sklearn.neighbors import NearestNeighbors

from emuses.tools.emuses_utils import plot_embeddings


def evaluate_embedding_statistics(embeddings):
    """
    Evaluate statistical properties of the UMAP embedding.

    Parameters:
    - embeddings (np.ndarray): Low-dimensional embeddings from UMAP.

    Returns:
    - metrics (dict): Dictionary containing spread, density variability, entropy, and distance statistics.
    """
    # Spread: Total variance of the embedding
    spread = np.var(embeddings, axis=0).sum()

    # Density variability: Standard deviation of point densities
    nbrs = NearestNeighbors(n_neighbors=10).fit(embeddings)
    distances, _ = nbrs.kneighbors(embeddings)
    avg_distances = distances.mean(axis=1)
    density_variability = np.std(avg_distances)

    # Entropy: Distribution of points in space
    hist, _ = np.histogramdd(embeddings, bins=20)  # Create a 2D histogram
    point_entropy = entropy(hist.flatten())

    # Pairwise distance statistics
    pairwise_dists = pairwise_distances(embeddings)
    mean_distance = np.mean(pairwise_dists)
    std_distance = np.std(pairwise_dists)

    return {
        "spread": spread,
        "density_variability": density_variability,
        "entropy": point_entropy,
        "mean_distance": mean_distance,
        "std_distance": std_distance,
    }


def train_and_save_umap_with_bayesian_search(
    input_matrix,
    output_folder,
    param_ranges,
    n_trials=50,
    maximize_metrics=None,
    pref=None,
    **kwargs,
):
    """
    Train a UMAP model on the input matrix using Bayesian optimization to search for the best parameters.

    Parameters:
    - input_matrix: np.ndarray
        High-dimensional input data.
    - output_folder: str
        Directory where the model, embeddings, and input matrix will be saved.
    - param_ranges: dict
        Dictionary defining the ranges for each parameter.
        Example:
        {
            "n_neighbors": {"type": "int", "low": 5, "high": 50, "step": 5},
            "min_dist": {"type": "float", "low": 0.01, "high": 0.5},
            "spread": {"type": "float", "low": 1.0, "high": 5.0},
            "repulsion_strength": {"type": "float", "low": 0.1, "high": 2.0},
            "negative_sample_rate": {"type": "int", "low": 1, "high": 10},
            "learning_rate": {"type": "float", "low": 1.0, "high": 10.0},
        }
    - n_trials: int, optional
        Number of optimization trials.
    - maximize_metrics: dict, optional
        Dictionary specifying whether to maximize (True) or minimize (False) each metric.
    - pref: str, optional
        Prefix for the saved files.
    """
    def objective(trial, output_subfolder=None):
        # Suggest UMAP parameters dynamically from param_ranges
        params = {}
        for param_name, param_info in param_ranges.items():
            if param_info["type"] == "int":
                params[param_name] = trial.suggest_int(
                    param_name, param_info["low"], param_info["high"], step=param_info.get("step", 1)
                )
            elif param_info["type"] == "float":
                params[param_name] = trial.suggest_float(
                    param_name, param_info["low"], param_info["high"]
                )
            elif param_info["type"] == "categorical":
                params[param_name] = trial.suggest_categorical(
                    param_name, param_info["choices"]
                )

        # Train UMAP model with suggested parameters
        umap_model = umap.UMAP(**params, **kwargs)
        embeddings = umap_model.fit_transform(input_matrix)

        if output_subfolder:
            # save the plot of the embeddings
            plot_embeddings(embeddings, output_subfolder / f"embeddings_{trial.number}.png")

        # Evaluate metrics
        metrics = evaluate_embedding_statistics(embeddings)

        # Combine metrics into a single score
        score = 0
        for metric_name, maximize in maximize_metrics.items():
            metric_value = metrics[metric_name]
            score += metric_value if maximize else -metric_value

        return score

    # Run the optimization
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)

    # Retrieve the best parameters
    best_params = study.best_params
    print(f"Best Parameters: {best_params}")
    print(f"Best Objective Score: {study.best_value}")

    # Train the UMAP model with the best parameters
    umap_model = umap.UMAP(**best_params, **kwargs)
    embeddings = umap_model.fit_transform(input_matrix)

    # Save the model, embeddings, and input matrix
    prefix = f"{pref}_" if pref else ""
    model_filename = f"{prefix}umap_model.joblib"
    embeddings_filename = f"{prefix}embeddings.npy"
    input_matrix_filename = f"{prefix}input_matrix.npy"

    dump(umap_model, output_folder / model_filename)
    np.save(output_folder / embeddings_filename, embeddings)
    np.save(output_folder / input_matrix_filename, input_matrix)

    return (
        umap_model,
        embeddings,
        output_folder / model_filename,
        output_folder / embeddings_filename,
        output_folder / input_matrix_filename,
    )


def is_umap_file(umap_path):
    return str(umap_path).endswith('.joblib')


def load_umap_model(base_path, prefix='', model_name='umap_model', joblib_version=None, max_attempts=10):
    """
    Load a UMAP model based on the filename convention and system joblib version.

    Parameters:
    base_path (Path or str): The directory where UMAP models are saved.
    prefix (str): Prefix for the UMAP model filename.
    model_name (str): Base name of the model.
    joblib_version (str, optional): Version of joblib used in the saved file. If None, the current system joblib version is used.
    max_attempts (int): Maximum number of attempts to load different versions of the model.

    Returns:
    loaded_umap (object or None): Loaded UMAP model or None if loading failed.
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
    if filepath.exists() and is_umap_file(filepath):
        try:
            loaded_umap = joblib.load(filepath)
            print(f"Successfully loaded UMAP model from: {filepath}")
            return loaded_umap, filepath
        except Exception as e:
            print(f"Failed to load UMAP model from: {filepath}, due to: {e}")

    # If the initial file cannot be loaded, try numbered variations
    counter = 1
    while counter <= max_attempts:
        if prefix:
            numbered_filename = f"{prefix}_{model_name}_joblib{joblib_version}_{counter}.joblib"
        else:
            numbered_filename = f"{model_name}_joblib{joblib_version}_{counter}.joblib"
        numbered_filepath = base_path / numbered_filename
        if numbered_filepath.exists() and is_umap_file(numbered_filepath):
            try:
                loaded_umap = joblib.load(numbered_filepath)
                print(f"Successfully loaded UMAP model from: {numbered_filepath}")
                return loaded_umap, numbered_filepath
            except Exception as e:
                print(f"Failed to load UMAP model from: {numbered_filepath}, due to: {e}")
                counter += 1
        else:
            break

    if counter > max_attempts:
        raise RuntimeError(f"Failed to load UMAP model after {max_attempts} attempts. "
                           f"Either there are too many versions or another issue is preventing loading.")

    # Return None and the next available filename if all attempts fail
    if prefix:
        next_available_filename = f"{prefix}_{model_name}_joblib{current_joblib_version}_{counter}.joblib"
    else:
        next_available_filename = f"{model_name}_joblib{current_joblib_version}_{counter}.joblib"
    next_filepath = base_path / next_available_filename
    print(f"Returning next available filename: {next_filepath}")
    return None, next_filepath
