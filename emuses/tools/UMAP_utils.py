import hdbscan
import joblib
import optuna
from emuses.tools.UMAP_utils import inner_optimize_hdbscan
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

from emuses.tools.clustering_utils import evaluate_clustering_metrics
from emuses.tools.optim_utils import calculate_composite_score, suggest_parameters, calculate_score
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

"""
optim_dict_example = {
    'param': {
        'umap': {
            'min_dist': {'name': 'min_dist', 'low': 0.01, 'high': 0.5},
            'n_neighbors': {'name': 'n_neighbors', 'low': 5, 'high': 50, 'step': 5},
            'n_components': {'value': 2},
            'metric': {'name': 'metric', 'choices': ['euclidean', 'cosine']}
        },
        'hdbscan': {
            'min_cluster_size': {'name': 'min_cluster_size', 'low': 5, 'high': 50},
            'min_samples': {'name': 'min_samples', 'low': 1, 'high': 10}
        }
    },
    'metrics': {
        'umap': {
            'spread': {
                'weight': 1.0,
                'target': 0.6,
                'epsilon': 0.1  # Tolerance for deviation from target
            },
            'density_variability': {
                'weight': 1.2,
                'target': 0.4,
                'epsilon': 0.1  # Balancing compactness with spread
            },
            'entropy': {
                'weight': 1.5
            }
        },
        'hdbscan': {
            'cluster_persistence': {
                'weight': 2.0
            },
            'noise_ratio': {
                'weight': 1.0,
                'target': 0.1,
                'epsilon': 0.05  # Tolerance for low noise
            },
            'validity_index': {
                'weight': 1.5
            }
        }
    }
}

"""


def compute_spread(embedding):
    """
    Compute the spread of a given embedding.

    Parameters:
    embedding (np.ndarray): An array of shape (n_samples, n_dimensions).

    Returns:
    float: The computed spread.
    """
    # Compute variance along each dimension
    variances = np.var(embedding, axis=0)

    # Sum variances to get the spread
    spread = np.sum(variances)
    return spread


def compute_density_variability(embedding, n_neighbors=15):
    """
    Compute the density variability of an embedding.

    Parameters:
    embedding (np.ndarray): An array of shape (n_samples, n_dimensions).
    n_neighbors (int): Number of nearest neighbors to consider.

    Returns:
    float: Density variability of the embedding.
    """
    # Find nearest neighbors
    nbrs = NearestNeighbors(n_neighbors=n_neighbors, metric="euclidean").fit(embedding)
    distances, _ = nbrs.kneighbors(embedding)

    # Compute mean distance for each point (local density proxy)
    local_densities = np.mean(distances, axis=1)

    # Compute the standard deviation and mean of densities
    std_density = np.std(local_densities)
    mean_density = np.mean(local_densities)

    # Density variability (coefficient of variation)
    density_variability = std_density / mean_density # here we could add a tiny epsilon to avoid division by zero
    return density_variability


def compute_entropy(embedding, n_bins=20):
    """
    Compute the entropy of the point distribution in an embedding.

    Parameters:
    embedding (np.ndarray): An array of shape (n_samples, n_dimensions).
    n_bins (int): Number of bins along each dimension.

    Returns:
    float: The computed entropy.
    """
    # Create a histogram over the embedding space
    hist, edges = np.histogramdd(embedding, bins=n_bins)

    # Flatten the histogram and calculate probabilities
    hist_flat = hist.flatten()
    probabilities = hist_flat / np.sum(hist_flat)

    # Filter out zero probabilities
    probabilities = probabilities[probabilities > 0]

    # Compute Shannon entropy
    entropy = -np.sum(probabilities * np.log(probabilities))

    # Normalize entropy (optional)
    max_entropy = np.log(hist.size)
    normalized_entropy = entropy / max_entropy # here we could add a tiny epsilon to avoid division by zero

    return normalized_entropy


######################################################################
# --- Outer (UMAP) + Nested HDBSCAN Optimization Using optim_dict --- #
######################################################################

def train_and_save_umap_optim_with_nested_clustering(
        input_matrix,
        output_folder,
        optim_dict,
        n_trials=50,
        n_inner_trials=20,
        pref=None,
        **kwargs,
):
    """
    Perform nested Bayesian optimization using a unified optim_dict.

    The outer loop optimizes UMAP parameters, and for each UMAP embedding the inner loop
    optimizes HDBSCAN parameters. The composite score is computed from both UMAP and HDBSCAN metrics.

    Parameters:
      input_matrix: np.ndarray, the high-dimensional data.
      output_folder: str or Path, where outputs are saved.
      optim_dict: dict, the unified optimization dictionary.
      n_trials: int, outer (UMAP) trials.
      n_inner_trials: int, inner (HDBSCAN) trials per UMAP trial.
      pref: str, optional prefix for saved files.
      **kwargs: additional parameters for UMAP.

    Returns:
      A tuple of best models, embeddings, file paths, and other outputs.
    """
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    print(f"Output folder set to: {output_folder}")

    def outer_objective(trial):
        # Use the unified optim_dict to suggest parameters for both UMAP and HDBSCAN.
        params_all = suggest_parameters(trial, optim_dict)
        umap_params = params_all["umap"]
        print(f"Trial {trial.number}: Suggested UMAP parameters: {umap_params}")

        # Train UMAP with the suggested parameters.
        umap_model = umap.UMAP(**umap_params, **kwargs)
        embeddings = umap_model.fit_transform(input_matrix)
        print(f"Trial {trial.number}: UMAP training completed.")

        # (Optional) Save a plot for this trial.
        trial_subfolder = output_folder / f"trial_{trial.number}"
        trial_subfolder.mkdir(parents=True, exist_ok=True)
        plot_path = trial_subfolder / f"embeddings_{trial.number}.png"
        plot_embeddings(embeddings, cluster_labels=None, output_path=plot_path, interactive=False, show_plot=False)
        print(f"Trial {trial.number}: Embedding plot saved at {plot_path}")

        # Evaluate UMAP metrics.
        umap_metrics = evaluate_embedding_statistics(embeddings)
        print(f"Trial {trial.number}: UMAP metrics: {umap_metrics}")
        umap_score = calculate_score(umap_metrics, optim_dict["metrics"]["umap"])
        print(f"Trial {trial.number}: UMAP score: {umap_score}")

        # Inner optimization: optimize HDBSCAN for this UMAP embedding.
        best_hdbscan_params, best_hdbscan_score, best_clusterer, best_labels, best_hdbscan_metrics = inner_optimize_hdbscan(
            embeddings, optim_dict, n_inner_trials=n_inner_trials
        )
        print(f"Trial {trial.number}: Best HDBSCAN parameters: {best_hdbscan_params}")
        print(f"Trial {trial.number}: Best HDBSCAN score: {best_hdbscan_score}")

        # Composite score: combine UMAP and HDBSCAN scores.
        composite_score = umap_score + best_hdbscan_score
        print(f"Trial {trial.number}: Composite score: {composite_score}")

        # Save extra info in the trial (user attributes).
        trial.set_user_attr("umap_params", umap_params)
        trial.set_user_attr("umap_metrics", umap_metrics)
        trial.set_user_attr("hdbscan_best_params", best_hdbscan_params)
        trial.set_user_attr("hdbscan_best_score", best_hdbscan_score)
        trial.set_user_attr("hdbscan_metrics", best_hdbscan_metrics)
        trial.set_user_attr("hdbscan_best_clusterer", best_clusterer)
        trial.set_user_attr("hdbscan_best_labels", best_labels)
        return composite_score

    # Outer optimization.
    outer_study = optuna.create_study(direction="maximize")
    print("Starting outer (UMAP) optimization...")
    outer_study.optimize(outer_objective, n_trials=n_trials)
    print("Outer optimization completed.")

    best_outer_trial = outer_study.best_trial
    best_umap_params = best_outer_trial.user_attrs["umap_params"]
    print(f"Best UMAP parameters: {best_umap_params}")

    # Retrain UMAP model using best parameters.
    best_umap_model = umap.UMAP(**best_umap_params, **kwargs)
    best_embeddings = best_umap_model.fit_transform(input_matrix)
    print("Trained UMAP model with best parameters.")

    # Retrieve the best HDBSCAN results from the best outer trial.
    best_hdbscan_params = best_outer_trial.user_attrs["hdbscan_best_params"]
    best_clusterer = best_outer_trial.user_attrs["hdbscan_best_clusterer"]
    best_labels = best_outer_trial.user_attrs["hdbscan_best_labels"]
    best_hdbscan_metrics = best_outer_trial.user_attrs["hdbscan_metrics"]
    print("Retrieved best HDBSCAN results from outer optimization.")

    # Save final models and outputs.
    prefix = f"{pref}_" if pref else ""
    umap_model_path = output_folder / f"{prefix}umap_model.joblib"
    embeddings_path = output_folder / f"{prefix}embeddings.npy"
    input_matrix_path = output_folder / f"{prefix}input_matrix.npy"
    cluster_model_path = output_folder / f"{prefix}hdbscan_model.joblib"
    cluster_labels_path = output_folder / f"{prefix}cluster_labels.npy"

    dump(best_umap_model, umap_model_path)
    np.save(embeddings_path, best_embeddings)
    np.save(input_matrix_path, input_matrix)
    dump(best_clusterer, cluster_model_path)
    np.save(cluster_labels_path, best_labels)

    print(f"UMAP model saved at: {umap_model_path}")
    print(f"Embeddings saved at: {embeddings_path}")
    print(f"Input matrix saved at: {input_matrix_path}")
    print(f"HDBSCAN model saved at: {cluster_model_path}")
    print(f"Cluster labels saved at: {cluster_labels_path}")

    return (
        best_umap_model,
        best_embeddings,
        umap_model_path,
        embeddings_path,
        best_clusterer,
        best_labels,
        cluster_model_path,
        cluster_labels_path,
        input_matrix_path
    )


def train_and_save_umap_optim(input_matrix, output_folder, optim_dict, n_trials=50, **kwargs):
    """
    Train a UMAP model with parameter optimization and save the results.

    Parameters:
        input_matrix (np.ndarray): Input data to train the UMAP model.
        output_folder (str or Path): Directory to save the model and embeddings.
        optim_dict (dict): Optimization dictionary defining parameters and metrics.
        n_trials (int): Number of optimization trials.
        **kwargs: Additional keyword arguments for the UMAP model.

    Returns:
        dict: Dictionary containing the best model, embeddings, and other outputs.
    """
    # Ensure output folder exists
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    # Define the objective function for Optuna
    def objective(trial):
        # Suggest parameters based on the optim_dict
        params = suggest_parameters(trial, optim_dict)

        # Train the UMAP model with suggested parameters
        umap_model = umap.UMAP(**params['umap'], **kwargs)
        embeddings = umap_model.fit_transform(input_matrix)

        # Calculate metrics
        metrics_values_dict = {
            'umap': evaluate_embedding_statistics(embeddings, optim_dict['metrics']['umap'])
        }

        # If clustering is part of the optimization, evaluate HDBSCAN metrics
        if 'hdbscan' in params:
            from clustering_utils import evaluate_hdbscan
            metrics_values_dict['hdbscan'] = evaluate_hdbscan(
                embeddings, params['hdbscan'], optim_dict['metrics']['hdbscan']
            )

        # Calculate the composite score
        composite_score = calculate_composite_score(optim_dict, metrics_values_dict)
        return composite_score

    # Initialize and run the Optuna study
    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=n_trials)

    # Retrieve the best parameters and score
    best_params = study.best_params
    best_score = study.best_value

    # Train the final UMAP model with the best parameters
    best_umap_model = umap.UMAP(**best_params['umap'], **kwargs)
    best_embeddings = best_umap_model.fit_transform(input_matrix)

    # Save the best model and embeddings
    dump(best_umap_model, output_folder / "best_umap_model.joblib")
    np.save(output_folder / "best_embeddings.npy", best_embeddings)

    return {
        'best_model': best_umap_model,
        'best_embeddings': best_embeddings,
        'best_params': best_params,
        'best_score': best_score,
        'output_folder': output_folder
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
            "repulsion_strength": {"type": "float", "low": 0.1, "high": 2.0},c
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
