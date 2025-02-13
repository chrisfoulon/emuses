import hdbscan
import joblib
import optuna
from bcblib.tools.general_utils import save_json
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
import optuna.visualization as ov

from emuses.tools.clustering_utils import evaluate_clustering_metrics, inner_optimize_hdbscan
from emuses.tools.optim_utils import calculate_composite_score, suggest_parameters, calculate_score, auto_n_neighbors
from emuses.tools.visualisation import plot_embeddings, plot_clustering_interactive_with_hover


def evaluate_embedding_statistics(embeddings, metrics_config):
    """
    Evaluate the statistical properties of the UMAP embedding based on the provided metrics configuration.

    Parameters:
        embeddings (np.ndarray): Low-dimensional embeddings from UMAP.
        metrics_config (dict): Dictionary defining which metrics to compute (and any additional configuration).
            For example:
            {
                "spread": {"weight": 1.0, "target": 1.0, "epsilon": 0.1},
                "density_variability": {"weight": 1.2, "target": 0.4, "epsilon": 0.1},
                "entropy": {"weight": 1.5}
            }

    Returns:
        dict: Dictionary containing the computed metric values.
    """
    computed_metrics = {}
    for metric_name in metrics_config.keys():
        if metric_name in metric_functions:
            computed_metrics[metric_name] = metric_functions[metric_name](embeddings)
        else:
            print(f"Warning: No computation function defined for metric '{metric_name}'.")
    return computed_metrics


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
            'dbcv': {
                'weight': 1.5
            }
        }
    }
}

"""


def compute_spread(embeddings, normalized=True):
    """
    Compute the spread (total variance) of the embedding.

    If normalized is True, the spread is divided by the maximum theoretical spread,
    where the maximum for each dimension is (range^2)/4.

    Parameters:
        embeddings (np.ndarray): Array of shape (n_samples, n_dimensions).
        normalized (bool): Whether to return a normalized value between 0 and 1.

    Returns:
        float: Spread (raw if normalized=False, normalized if True).
    """
    # Compute raw spread (sum of variances)
    raw_spread = np.sum(np.var(embeddings, axis=0))
    if not normalized:
        return raw_spread
    # Compute ranges along each dimension (max - min)
    ranges = np.ptp(embeddings, axis=0)
    # Maximum variance per dimension is (range^2)/4
    max_variances = (ranges ** 2) / 4.0
    max_theoretical_spread = np.sum(max_variances)
    return raw_spread / max_theoretical_spread # here we could add a tiny epsilon to avoid division by zero


def compute_density_variability(embeddings, n_neighbors=None, normalized=True, alpha=3.0, beta=1.0):
    """
    Compute the density variability of an embedding.

    The raw density variability is the coefficient of variation of the average distance to
    n_neighbors nearest neighbors. If n_neighbors is not provided, it is computed automatically
    based on the dataset size. Then, if normalized is True, the raw value is mapped to [0, 1]
    using a transformation based on the observed min and max.

    Parameters:
        embeddings (np.ndarray): Array of shape (n_samples, n_dimensions).
        n_neighbors (int, optional): Number of nearest neighbors. If None, computed automatically.
        normalized (bool): Whether to return a normalized value between 0 and 1.
        alpha (float): Parameter for the logistic (sigmoid) transformation (if used).
        beta (float): Parameter that defines the midpoint of the logistic transformation.

    Returns:
        float: Density variability, with 1 being best (most uniform).
    """
    if n_neighbors is None:
        n_neighbors = auto_n_neighbors(embeddings.shape[0])

    nbrs = NearestNeighbors(n_neighbors=n_neighbors, metric="euclidean").fit(embeddings)
    distances, _ = nbrs.kneighbors(embeddings)
    local_densities = np.mean(distances, axis=1)
    raw_cv = np.std(local_densities) / (np.mean(local_densities) + 1e-8)

    if not normalized:
        return raw_cv

    # Instead of a fixed sigmoid, we can also try a relative normalization approach:
    d_min = np.min(local_densities)
    d_max = np.max(local_densities)
    if d_max + d_min < 1e-8:
        return 1.0
    max_cv = (d_max - d_min) / (d_max + d_min)
    if max_cv < 1e-8:
        return 1.0
    normalized_cv = 1 - (raw_cv / max_cv)
    return max(0, min(1, normalized_cv))


def compute_entropy(embeddings, n_bins=20, normalized=True):
    """
    Compute the Shannon entropy of the point distribution in an embedding.

    If normalized is True, the entropy is divided by the maximum entropy (log of the number of histogram bins),
    so that the returned value is between 0 and 1.

    Parameters:
        embeddings (np.ndarray): Array of shape (n_samples, n_dimensions).
        n_bins (int): Number of bins along each dimension.
        normalized (bool): Whether to return a normalized value.

    Returns:
        float: Entropy (raw if normalized=False, normalized if True).
    """
    hist, _ = np.histogramdd(embeddings, bins=n_bins)
    hist_flat = hist.flatten()
    probabilities = hist_flat / (np.sum(hist_flat) + 1e-8)
    probabilities = probabilities[probabilities > 0]
    ent = -np.sum(probabilities * np.log(probabilities))
    if not normalized:
        return ent
    max_ent = np.log(hist.size)
    return ent / max_ent # here we could add a tiny epsilon to avoid division by zero


######################################################################
# --- Outer (UMAP) + Nested HDBSCAN Optimization Using optim_dict --- #
######################################################################


metric_functions = {
    "spread": compute_spread,
    "density_variability": lambda emb: compute_density_variability(emb, n_neighbors=10),
    "entropy": lambda emb: compute_entropy(emb, n_bins=20),
    "mean_distance": lambda emb: np.mean(pairwise_distances(emb)),
    "std_distance": lambda emb: np.std(pairwise_distances(emb))
}


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
    optimizes HDBSCAN parameters. A composite score is computed from both UMAP and HDBSCAN
    metrics (by merging their metric dictionaries and using a composite scoring function)
    to reflect both the properties of the latent space and its clusterability.

    Trial details (parameters, metrics, and composite scores) are logged to a JSON file.
    An interactive clustering plot (HTML) is also generated for the best trial.

    Additionally, the best UMAP model is saved to disk as soon as a new best composite score is achieved.

    Parameters:
      input_matrix: np.ndarray, the high-dimensional data.
      output_folder: str or Path, where outputs are saved.
      optim_dict: dict, the unified optimization dictionary.
      n_trials: int, number of outer (UMAP) trials.
      n_inner_trials: int, number of inner (HDBSCAN) trials per UMAP trial.
      pref: str, optional prefix for saved files.
      **kwargs: additional parameters for UMAP.

    Returns:
      A tuple of:
        - best_umap_model,
        - best_embeddings,
        - umap_model_path,
        - embeddings_path,
        - best_clusterer,
        - best_labels,
        - cluster_model_path,
        - cluster_labels_path,
        - input_matrix_path.
    """
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    print(f"Output folder set to: {output_folder}")

    # Folder to store static plots for each trial.
    output_plot_folder = output_folder / "plots"
    output_plot_folder.mkdir(parents=True, exist_ok=True)

    # Define path for the best UMAP model file.
    best_model_path = output_folder / (f"{pref}_best_umap_model.joblib" if pref else "best_umap_model.joblib")

    # List to store trial log information.
    trial_logs = []

    # Global variable to track best composite score.
    best_score_so_far = -float("inf")

    def save_best_model_callback(study, trial):
        nonlocal best_score_so_far
        # When a new best trial is found, retrain the model on the full data and save it.
        if trial.value > best_score_so_far:
            best_score_so_far = trial.value
            best_umap_params = trial.user_attrs["umap_params"]
            # Train the model using these parameters.
            best_model = umap.UMAP(**best_umap_params, **kwargs)
            best_model.fit(input_matrix)
            dump(best_model, best_model_path)
            print(f"New best model saved (trial {trial.number} with score {trial.value}) at {best_model_path}")

    def outer_objective(trial):
        # Suggest parameters for UMAP (and HDBSCAN).
        params_all = suggest_parameters(trial, optim_dict)
        umap_params = params_all["umap"]
        print(f"Trial {trial.number}: Suggested UMAP parameters: {umap_params}")

        # Train UMAP with the suggested parameters.
        umap_model = umap.UMAP(**umap_params, **kwargs)
        embeddings = umap_model.fit_transform(input_matrix)
        print(f"Trial {trial.number}: UMAP training completed.")

        # Save a static plot for this trial.
        plot_path = output_plot_folder / f"embeddings_{trial.number}.png"
        plot_embeddings(embeddings, cluster_labels=None, output_path=plot_path,
                        interactive=False, show_plot=False)
        print(f"Trial {trial.number}: Embedding plot saved at {plot_path}")

        # Evaluate UMAP metrics.
        umap_metrics = evaluate_embedding_statistics(embeddings, optim_dict["metrics"]["umap"])
        print(f"Trial {trial.number}: UMAP metrics: {umap_metrics}")

        # Inner optimization: optimize HDBSCAN for this UMAP embedding.
        (best_hdbscan_params, best_hdbscan_score, best_clusterer, best_labels,
         best_hdbscan_metrics) = inner_optimize_hdbscan(embeddings, optim_dict, n_inner_trials=n_inner_trials)
        print(f"Trial {trial.number}: Best HDBSCAN parameters: {best_hdbscan_params}")
        print(f"Trial {trial.number}: Best HDBSCAN score: {best_hdbscan_score}")

        # Combine metrics from both UMAP and HDBSCAN.
        combined_metrics = {
            "umap": umap_metrics,
            "hdbscan": best_hdbscan_metrics
        }
        # Compute a composite score that weights all metrics together.
        composite_score = calculate_composite_score(optim_dict, combined_metrics)
        print(f"Trial {trial.number}: Composite score: {composite_score}")

        # Log trial details.
        trial_info = {
            "trial_number": trial.number,
            "umap_params": umap_params,
            "umap_metrics": umap_metrics,
            "hdbscan_best_params": best_hdbscan_params,
            "hdbscan_metrics": best_hdbscan_metrics,
            "composite_score": composite_score
        }
        trial_logs.append(trial_info)

        # Save extra info in the trial.
        trial.set_user_attr("umap_params", umap_params)
        trial.set_user_attr("umap_metrics", umap_metrics)
        trial.set_user_attr("hdbscan_best_params", best_hdbscan_params)
        trial.set_user_attr("hdbscan_best_score", best_hdbscan_score)
        trial.set_user_attr("hdbscan_metrics", best_hdbscan_metrics)
        trial.set_user_attr("hdbscan_best_clusterer", best_clusterer)
        trial.set_user_attr("hdbscan_best_labels", best_labels)

        return composite_score

    # Create the study with the callback.
    outer_study = optuna.create_study(direction="maximize")
    print("Starting outer (UMAP) optimization...")
    outer_study.optimize(outer_objective, n_trials=n_trials, callbacks=[save_best_model_callback])
    print("Outer optimization completed.")

    # Retrieve best trial information.
    best_outer_trial = outer_study.best_trial
    best_umap_params = best_outer_trial.user_attrs["umap_params"]
    best_composite_score = outer_study.best_value
    best_hdbscan_params = best_outer_trial.user_attrs["hdbscan_best_params"]

    print(f"Best composite score: {best_composite_score}")
    print(f"Best UMAP parameters: {best_umap_params}")
    print(f"Best HDBSCAN parameters (from best trial): {best_hdbscan_params}")

    # Retrain the best UMAP model on the full input data.
    best_umap_model = umap.UMAP(**best_umap_params, **kwargs)
    best_embeddings = best_umap_model.fit_transform(input_matrix)
    print("Trained UMAP model with best parameters.")

    # Retrieve the best HDBSCAN results.
    best_clusterer = best_outer_trial.user_attrs["hdbscan_best_clusterer"]
    best_labels = best_outer_trial.user_attrs["hdbscan_best_labels"]
    # best_hdbscan_metrics = best_outer_trial.user_attrs["hdbscan_metrics"]
    print("Retrieved best HDBSCAN results from outer optimization.")

    # Save an interactive clustering plot for the best trial.
    best_clustering_plot_path = output_folder / (f"{pref}_best_clustering.html" if pref else "best_clustering.html")
    plot_clustering_interactive_with_hover(
        best_embeddings,
        best_labels,
        output_path=best_clustering_plot_path,
        show_plot=False,
        return_plot=False
    )
    print(f"Interactive clustering plot saved at: {best_clustering_plot_path}")

    # Define file paths for final outputs.
    prefix = f"{pref}_" if pref else ""
    umap_model_path = output_folder / f"{prefix}umap_model.joblib"
    embeddings_path = output_folder / f"{prefix}embeddings.npy"
    input_matrix_path = output_folder / f"{prefix}input_matrix.npy"
    cluster_model_path = output_folder / f"{prefix}hdbscan_model.joblib"
    cluster_labels_path = output_folder / f"{prefix}cluster_labels.npy"

    # Save the final UMAP model, embeddings, input matrix, and clustering results.
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

    # Save the trial logs to a JSON file.
    log_path = output_folder / "parameter_search_log.json"
    save_json(log_path, trial_logs)
    print(f"Parameter search log saved at: {log_path}")

    # Optionally, generate and save an optimization history plot using Optuna's visualization:
    fig = ov.plot_optimization_history(outer_study)
    fig.write_html(str(output_folder / "optimization_history.html"))
    print(f"Optimization history plot saved at: {output_folder / 'optimization_history.html'}")

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
