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

from emuses.tools.visualisation import plot_embeddings


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
    - output_folder: str or Path
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
    - **kwargs: additional keyword arguments
        Additional parameters to pass to UMAP.
    """
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)  # Ensure output folder exists
    print(f"Output folder set to: {output_folder}")

    def objective(trial):
        print(f"Starting trial {trial.number + 1}/{n_trials}")
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

        print(f"Trial {trial.number + 1}: Suggested parameters: {params}")

        # Train UMAP model with suggested parameters
        umap_model = umap.UMAP(**params, **kwargs)
        embeddings = umap_model.fit_transform(input_matrix)
        print(f"Trial {trial.number + 1}: UMAP training completed.")

        # Define subfolder for this trial's outputs
        trial_subfolder = output_folder / f"trial_{trial.number}"
        trial_subfolder.mkdir(parents=True, exist_ok=True)
        print(f"Trial {trial.number + 1}: Created subfolder at {trial_subfolder}")

        # Save the plot of the embeddings as a static image (interactive=False)
        plot_embeddings(
            embeddings,
            cluster_labels=None,  # No clustering labels during optimization
            output_path=trial_subfolder / f"embeddings_{trial.number}.png",
            show_plot=False,
            return_plot=False,
            interactive=False  # Save as static image
        )
        print(f"Trial {trial.number + 1}: Saved plot at {trial_subfolder / f'embeddings_{trial.number}.png'}")

        # Evaluate metrics
        metrics = evaluate_embedding_statistics(embeddings)
        print(f"Trial {trial.number + 1}: Evaluated metrics: {metrics}")

        # Combine metrics into a single score
        score = 0
        if maximize_metrics:
            for metric_name, maximize in maximize_metrics.items():
                metric_value = metrics.get(metric_name, 0)
                if maximize:
                    score += metric_value
                else:
                    score -= metric_value
            print(f"Trial {trial.number + 1}: Combined score: {score}")

        return score

    # Initialize Optuna study
    study = optuna.create_study(direction="maximize")
    print("Optuna study created.")

    # Run optimization
    study.optimize(objective, n_trials=n_trials)
    print("Optuna optimization completed.")

    # Retrieve the best parameters
    best_params = study.best_params
    best_score = study.best_value
    print(f"Best Parameters: {best_params}")
    print(f"Best Objective Score: {best_score}")

    # Train the UMAP model with the best parameters
    best_umap_model = umap.UMAP(**best_params, **kwargs)
    best_embeddings = best_umap_model.fit_transform(input_matrix)
    print("Trained UMAP model with best parameters.")

    # Save the model, embeddings, and input matrix
    prefix = f"{pref}_" if pref else ""
    model_filename = f"{prefix}umap_model.joblib"
    embeddings_filename = f"{prefix}embeddings.npy"
    input_matrix_filename = f"{prefix}input_matrix.npy"

    dump(best_umap_model, output_folder / model_filename)
    print(f"UMAP model saved at: {output_folder / model_filename}")

    np.save(output_folder / embeddings_filename, best_embeddings)
    print(f"Embeddings saved at: {output_folder / embeddings_filename}")

    np.save(output_folder / input_matrix_filename, input_matrix)
    print(f"Input matrix saved at: {output_folder / input_matrix_filename}")

    return (
        best_umap_model,
        best_embeddings,
        output_folder / model_filename,
        output_folder / embeddings_filename,
        output_folder / input_matrix_filename,
    )


def is_umap_file(umap_path):
    return str(umap_path).endswith('.joblib')


def load_umap_model(base_path, prefix='', model_name='umap_model', joblib_version=None):
    """
    Load a UMAP model based on the filename convention and local joblib version.
    If loading the specified joblib version fails, try all others in the directory.

    Parameters:
    -----------
    base_path : Path or str
        The directory where UMAP models are saved.
    prefix : str
        Prefix for the UMAP model filename.
    model_name : str
        Base name of the model.
    joblib_version : str, optional
        Version of joblib used in the saved file. If None, the current system joblib version is used.

    Returns:
    --------
    loaded_umap : object or None
        Loaded UMAP model or None if loading failed.
    filepath : Path
        Path of the loaded file or next available filename if loading failed.
    """
    base_path = Path(base_path)

    # If no joblib_version is provided, use the current local version
    current_joblib_version = joblib.__version__
    if joblib_version is None or not joblib_version:
        joblib_version = current_joblib_version

    if prefix:
        filename = f"{prefix}_{model_name}_joblib{joblib_version}.joblib"
    else:
        filename = f"{model_name}_joblib{joblib_version}.joblib"

    filepath = base_path / filename

    # Try the main file first
    if filepath.exists() and is_umap_file(filepath):
        try:
            loaded_umap = joblib.load(filepath)
            print(f"Successfully loaded UMAP model from: {filepath}")
            return loaded_umap, filepath
        except Exception as e:
            print(f"Failed to load UMAP model from: {filepath}, due to: {e}")
    else:
        print(f"No model found at: {filepath}")

    # If the exact file didn't load, try all other files in the directory that match the pattern:
    # Pattern: {prefix_}model_name_joblib{someversion}.joblib or with the prefix if provided.
    pattern = f"{prefix}_{model_name}_joblib*.joblib" if prefix else f"{model_name}_joblib*.joblib"
    candidate_files = list(base_path.glob(pattern))

    # Sort candidates to try a deterministic order (optional)
    candidate_files.sort()

    for candidate in candidate_files:
        # Skip the one we already tried
        if candidate == filepath:
            continue
        if is_umap_file(candidate):
            try:
                loaded_umap = joblib.load(candidate)
                print(f"Successfully loaded UMAP model from: {candidate}")
                return loaded_umap, candidate
            except Exception as e:
                print(f"Failed to load UMAP model from: {candidate}, due to: {e}")

    # If none could be loaded, suggest next filename using current joblib version
    if prefix:
        next_filename = f"{prefix}_{model_name}_joblib{current_joblib_version}.joblib"
    else:
        next_filename = f"{model_name}_joblib{current_joblib_version}.joblib"
    next_filepath = base_path / next_filename
    print(f"No suitable model found. Returning next available filename: {next_filepath}")
    return None, next_filepath
