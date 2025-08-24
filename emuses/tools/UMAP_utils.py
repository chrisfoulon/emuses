import warnings
from itertools import product
from pathlib import Path

import hdbscan
import joblib
import numpy as np
import optuna
import optuna.visualization as ov
import umap
from bcblib.tools.general_utils import save_json
from joblib import __version__ as joblib_version
from joblib import dump, load
from scipy.stats import entropy
from sklearn.manifold import trustworthiness
from sklearn.metrics import pairwise_distances, silhouette_score
from sklearn.neighbors import NearestNeighbors

from emuses.tools.clustering_utils import (evaluate_clustering_metrics,
                                           evaluate_hdbscan,
                                           inner_optimize_hdbscan)
from emuses.tools.model_io import ModelIOManager
from emuses.tools.optim_utils import (are_parameters_fixed, auto_n_neighbors,
                                      calculate_composite_score,
                                      calculate_score,
                                      compute_detailed_components,
                                      suggest_parameters)
from emuses.tools.visualisation import (plot_clustering_interactive_with_hover,
                                        plot_embeddings,
                                        save_optimization_log_plot)


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
            computed_metrics[metric_name] = float(
                metric_functions[metric_name](embeddings)
            )
        else:
            print(
                f"Warning: No computation function defined for metric '{metric_name}'."
            )
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
    max_variances = (ranges**2) / 4.0
    max_theoretical_spread = np.sum(max_variances)
    return (
        raw_spread / max_theoretical_spread
    )  # here we could add a tiny epsilon to avoid division by zero


def compute_eigen_spread(embeddings, normalized=True):
    """
    Compute the total spread of the embeddings using the eigenvalues of the covariance matrix,
    and compute an anisotropy ratio (smallest/largest eigenvalue).

    Parameters:
        embeddings (np.ndarray): Array of shape (n_samples, n_dimensions).
        normalized (bool): If True, normalize the total spread by the sum of eigenvalues.

    Returns:
        total_spread: Total variance (sum of eigenvalues) (normalized if requested).
        anisotropy_ratio: Ratio of the smallest eigenvalue to the largest.
    """
    # Compute the covariance matrix (columns as variables)
    cov_matrix = np.cov(embeddings, rowvar=False)
    # Compute eigenvalues
    eigenvalues, _ = np.linalg.eig(cov_matrix)
    # Sort in descending order (largest first)
    eigenvalues = np.sort(eigenvalues)[::-1]

    total_spread = np.sum(eigenvalues)
    if normalized and total_spread != 0:
        # Normalized total spread could be defined as fraction of total variance
        total_spread /= total_spread  # Always 1 when normalized in this trivial way.
        # You might instead want to leave it as raw variance for comparison
    # For anisotropy, we use the ratio of smallest to largest eigenvalue.
    anisotropy_ratio = eigenvalues[-1] / eigenvalues[0] if eigenvalues[0] > 0 else 0.0

    return anisotropy_ratio


def compute_density_variability(embeddings, n_neighbors=None, normalized=True):
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


def compute_entropy_old(embeddings, n_bins=20, normalized=True):
    """
    Compute the Shannon entropy of the point distribution in an embedding using a histogram-based approach.

    This method discretizes the continuous latent space into a grid by dividing the range of each dimension
    into 'n_bins' equally spaced intervals. The resulting multidimensional histogram counts the number of points
    falling into each cell, thereby approximating a discrete probability distribution over the latent space.

    The Shannon entropy is then calculated from this probability distribution:
        H = -∑ p_i * log(p_i)
    where p_i is the probability of a point falling into the i-th bin.

    The rationale for using this approach is:
      - It provides a simple, intuitive measure of how uniformly the data points are distributed.
      - A high entropy (close to 1 when normalized) indicates that points are spread nearly uniformly across the grid,
        suggesting a lack of distinct clusters or substructures.
      - A low entropy (close to 0) suggests that points are concentrated in a few regions, indicating the presence of
        well-defined clusters or substructures in the embedding.

    Note on binning:
      - 'n_bins' defines the number of equal intervals along each dimension, not the number of points per bin.
      - For a 2D embedding with n_bins=20, the space is divided into a 20x20 grid. This discretization is essential
        to approximate a continuous distribution with a discrete one for entropy calculation.

    If 'normalized' is True, the computed entropy is divided by the maximum possible entropy (log(total number of bins))
    so that the final value is scaled between 0 and 1. This normalized entropy makes it easier to compare different embeddings.

    Parameters:
        embeddings (np.ndarray): Array of shape (n_samples, n_dimensions) containing the embedding coordinates.
        n_bins (int): Number of bins along each dimension used for discretization.
        normalized (bool): Whether to return a normalized entropy value in [0, 1].

    Returns:
        float: The computed entropy. If normalized is False, the raw entropy is returned; if True, the normalized entropy is returned.
    """
    hist, _ = np.histogramdd(embeddings, bins=n_bins)
    hist_flat = hist.flatten()
    probabilities = hist_flat / (np.sum(hist_flat) + 1e-8)
    probabilities = probabilities[probabilities > 0]
    ent = -np.sum(probabilities * np.log(probabilities))
    if not normalized:
        return ent
    max_ent = np.log(hist.size)
    return ent / max_ent  # normalized entropy between 0 and 1


def compute_entropy_range_mean(
    embeddings, n_bins_min=10, n_bins_max=50, steps=20, normalized=True
):
    """
    Compute the mean Shannon entropy of the point distribution in an embedding
    across a range of binning resolutions.

    By default, the function discretizes the continuous latent space into
    grids defined by bin counts from 'n_bins_min' to 'n_bins_max', in 'steps'
    equally spaced intervals, and computes the entropy at each bin count.

    The Shannon entropy is then calculated from each histogram-based probability distribution:
        H = -∑ p_i * log(p_i)
    where p_i is the probability of a point falling into the i-th bin.

    Finally, the function returns the mean of these entropy values over the entire range of bin counts.

    If 'normalized' is True, each entropy value is divided by the maximum possible
    entropy for that bin count (log(total number of bins)), so the final values are
    in [0, 1]. The mean is then computed from those normalized values.

    Parameters:
        embeddings (np.ndarray): Array of shape (n_samples, n_dimensions)
            containing the embedding coordinates.
        n_bins_min (int): Minimum number of bins along each dimension (default: 10).
        n_bins_max (int): Maximum number of bins along each dimension (default: 50).
        steps (int): Number of bin-count values to evaluate in the range (default: 20).
        normalized (bool): Whether to use normalized entropy ([0,1]) or raw entropy.

    Returns:
        float: The mean entropy value computed over all bin counts in the specified range.
    """
    bin_values = np.linspace(n_bins_min, n_bins_max, steps, dtype=int)
    entropies = []

    for n_bins in bin_values:
        hist, _ = np.histogramdd(embeddings, bins=n_bins)
        hist_flat = hist.flatten()
        probabilities = hist_flat / (np.sum(hist_flat) + 1e-8)
        probabilities = probabilities[probabilities > 0]

        raw_entropy = -np.sum(probabilities * np.log(probabilities))
        if normalized:
            max_ent = np.log(hist.size)  # total bins = n_bins^n_dimensions
            ent = raw_entropy / max_ent
        else:
            ent = raw_entropy

        entropies.append(ent)

    return float(np.mean(entropies))


######################################################################
# --- Outer (UMAP) + Nested HDBSCAN Optimization Using optim_dict --- #
######################################################################


metric_functions = {
    "spread": compute_spread,
    "eigen_spread": compute_eigen_spread,
    "density_variability": lambda emb: compute_density_variability(emb, n_neighbors=10),
    "entropy": lambda emb: compute_entropy_range_mean(emb),
    "mean_distance": lambda emb: np.mean(pairwise_distances(emb)),
    "std_distance": lambda emb: np.std(pairwise_distances(emb)),
}


def train_and_save_umap_optim_with_nested_clustering(
    input_matrix,
    output_folder,
    optim_dict,
    n_trials=50,
    n_inner_trials=20,
    pref=None,
    n_jobs=4,
    parallel_mode="umap",  # "umap" or "hdbscan"
    inner_n_jobs=4,
    random_state=42,
    clusterer_random_state=None,
    approx_min_span_tree=True,  # For reproducibility (False = reproducible but 10-100x slower)
    core_dist_n_jobs=-1,  # For reproducibility (1 = reproducible)
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
      input_matrix : np.ndarray
          The high-dimensional data.
      output_folder : str or Path
          Where outputs (models, embeddings, logs, plots) are saved.
      optim_dict : dict
          The unified optimization dictionary (with keys "param" and "metrics").
      n_trials : int, default=50
          Number of outer (UMAP) trials.
      n_inner_trials : int, default=20
          Number of inner (HDBSCAN) trials per UMAP trial.
      pref : str, optional
          Prefix for saved files.
      n_jobs : int, default=4
            Number of parallel jobs for Optuna.
      parallel_mode : str, default="umap"
            Whether to parallelize the outer optimization ("umap") or inner optimization ("hdbscan").
      inner_n_jobs : int, default=4
            Number of parallel jobs for inner optimization
      random_state : int, default=42
            Random seed for UMAP for reproducibility.
      clusterer_random_state : int, optional
            Random seed for HDBSCAN clustering. If None, uses the same as random_state.
      approx_min_span_tree : bool, default=True
            Whether to use approximate minimum spanning tree in HDBSCAN.
            Setting to False ensures reproducibility but at a significant performance cost (10-100x slower).
      core_dist_n_jobs : int, default=-1
            Number of parallel jobs for core distance calculations in HDBSCAN.
            Setting to 1 ensures reproducibility but at a performance cost.

      **kwargs :
          Additional parameters for UMAP.

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

    # Define paths for saving the best model, embeddings, and input matrix.
    best_model_path = output_folder / (
        f"{pref}_best_umap_model.joblib" if pref else "best_umap_model.joblib"
    )
    best_embeddings_path = output_folder / (
        f"{pref}_embeddings.npy" if pref else "embeddings.npy"
    )
    input_matrix_path = output_folder / (
        f"{pref}_input_matrix.npy" if pref else "input_matrix.npy"
    )

    # Extract parameter dictionaries for UMAP and HDBSCAN.
    umap_params_dict = optim_dict["param"]["umap"]
    hdbscan_params_dict = optim_dict["param"]["hdbscan"]

    # Check if parameters are fixed.
    umap_fixed = are_parameters_fixed(umap_params_dict)
    hdbscan_fixed = are_parameters_fixed(hdbscan_params_dict)
    if umap_fixed and hdbscan_fixed:
        print(
            "All parameters are fixed – running a single trial (n_trials=1, n_inner_trials=1) instead of full optimization."
        )
        n_trials = 1
        n_inner_trials = 1

    # List to store trial log information.
    trial_logs = []
    best_score_so_far = -float("inf")
    best_clusterer = None
    best_labels = None

    def save_best_model_callback(study, trial):
        nonlocal best_score_so_far
        # Only proceed if the trial has the required user attribute.
        if "umap_params" not in trial.user_attrs:
            print(
                f"Trial {trial.number} does not have 'umap_params' set; skipping callback."
            )
            return
        if trial.value > best_score_so_far:
            best_score_so_far = trial.value
            best_umap_params = trial.user_attrs["umap_params"]
            best_model = umap.UMAP(**best_umap_params, **kwargs)
            best_model.fit(input_matrix)

            # Use ModelIOManager for saving
            manager = ModelIOManager(output_folder)
            manager.save_model(
                model=best_model,
                model_name="best_umap_model",
                model_type="emuses_umap_component",
                config=best_umap_params,
                description=f"EMUSES dimensionality reduction component: UMAP embedding optimized "
                f"for neuroimaging analysis (trial {trial.number}, score: {trial.value:.4f})",
                tags=["optimization", "best_model", f"trial_{trial.number}"],
            )
            print(
                f"New best model saved (trial {trial.number} with score {trial.value}) using ModelIOManager"
            )

    def outer_objective(trial):
        nonlocal best_score_so_far, best_clusterer, best_labels

        # Suggest parameters for UMAP and HDBSCAN.
        params_all = suggest_parameters(trial, optim_dict)
        umap_params = params_all["umap"]

        print(f"Trial {trial.number}: Suggested UMAP parameters: {umap_params}")

        # Train UMAP with the suggested parameters and random_state
        umap_params_with_random_state = {**umap_params, "random_state": random_state}
        umap_model = umap.UMAP(**umap_params_with_random_state, **kwargs)
        embeddings = umap_model.fit_transform(input_matrix)
        print(f"Trial {trial.number}: UMAP training completed.")

        # Evaluate UMAP metrics.
        umap_metrics = evaluate_embedding_statistics(
            embeddings, optim_dict["metrics"]["umap"]
        )
        print(f"Trial {trial.number}: UMAP metrics: {umap_metrics}")

        # Get the clusterer random state
        clusterer_rs = (
            clusterer_random_state
            if clusterer_random_state is not None
            else random_state
        )

        # Get reproducibility parameters from kwargs if available
        approx_min_span_tree = kwargs.get("approx_min_span_tree", True)
        core_dist_n_jobs = kwargs.get("core_dist_n_jobs", -1)

        # Inner optimization: optimize HDBSCAN for this UMAP embedding.
        if parallel_mode == "hdbscan":
            (
                best_hdbscan_params,
                best_hdbscan_score,
                best_clusterer_trial,
                best_labels_trial,
                best_hdbscan_metrics,
            ) = inner_optimize_hdbscan(
                embeddings,
                optim_dict,
                n_inner_trials=n_inner_trials,
                n_jobs=inner_n_jobs,
                random_state=clusterer_rs,
                approx_min_span_tree=approx_min_span_tree,
                core_dist_n_jobs=core_dist_n_jobs,
            )
        else:
            (
                best_hdbscan_params,
                best_hdbscan_score,
                best_clusterer_trial,
                best_labels_trial,
                best_hdbscan_metrics,
            ) = inner_optimize_hdbscan(
                embeddings,
                optim_dict,
                n_inner_trials=n_inner_trials,
                random_state=clusterer_rs,
                approx_min_span_tree=approx_min_span_tree,
                core_dist_n_jobs=core_dist_n_jobs,
            )

        print(f"Trial {trial.number}: Best HDBSCAN parameters: {best_hdbscan_params}")
        print(f"Trial {trial.number}: Best HDBSCAN score: {best_hdbscan_score}")

        # Generate an interactive clustering plot for the inner-loop best clustering.
        interactive_plot_path = output_plot_folder / f"interactive_{trial.number}.html"
        plot_clustering_interactive_with_hover(
            embeddings,
            best_labels_trial,
            output_path=interactive_plot_path,
            show_plot=False,
            return_plot=True,
        )
        print(
            f"Trial {trial.number}: Interactive clustering plot saved at {interactive_plot_path}"
        )

        # Combine metrics from both UMAP and HDBSCAN.
        combined_metrics = {"umap": umap_metrics, "hdbscan": best_hdbscan_metrics}
        # Compute composite score.
        composite_score = calculate_composite_score(
            combined_metrics, optim_dict["metrics"]
        )
        print(f"Trial {trial.number}: Composite score: {composite_score}")

        # Log detailed UMAP metric contributions.
        detailed_umap = compute_detailed_components(
            optim_dict["metrics"]["umap"], umap_metrics
        )
        trial.set_user_attr("detailed_umap_components", detailed_umap)

        detailed_hdbscan = compute_detailed_components(
            optim_dict["metrics"]["hdbscan"], best_hdbscan_metrics
        )
        trial.set_user_attr("detailed_hdbscan_components", detailed_hdbscan)

        # Set trial user attributes for UMAP parameters and metrics (only JSON serializable data)
        trial.set_user_attr("umap_params", umap_params)
        trial.set_user_attr("umap_metrics", umap_metrics)
        trial.set_user_attr("hdbscan_metrics", best_hdbscan_metrics)
        trial.set_user_attr("composite_score", composite_score)
        trial.set_user_attr("hdbscan_best_params", best_hdbscan_params)
        # Do not store the raw HDBSCAN model or labels (non-serializable objects)

        # Append trial log information.
        trial_info = {
            "trial_number": trial.number,
            "umap_params": umap_params,
            "umap_metrics": umap_metrics,
            "detailed_umap_components": detailed_umap,
            "hdbscan_best_params": best_hdbscan_params,
            "hdbscan_metrics": best_hdbscan_metrics,
            "detailed_hdbscan_components": detailed_hdbscan,
            "composite_score": composite_score,
            "interactive_plot": interactive_plot_path.as_posix(),
        }
        trial_logs.append(trial_info)

        # Save best model immediately if a new best composite score is found.
        if composite_score > best_score_so_far:
            best_score_so_far = composite_score
            best_clusterer = best_clusterer_trial
            best_labels = best_labels_trial

            # Use ModelIOManager for saving UMAP model
            manager = ModelIOManager(output_folder)
            manager.save_model(
                model=umap_model,
                model_name="best_umap_model",
                model_type="umap",
                config=umap_params,
                description=f"Best UMAP model from trial {trial.number} with composite score {composite_score}",
                tags=["optimization", "best_model", f"trial_{trial.number}"],
            )

            # Save embeddings using numpy
            np.save(best_embeddings_path, embeddings)
            print(
                f"New best UMAP model saved using ModelIOManager (Trial {trial.number}, Score: {best_score_so_far})"
            )

        return composite_score

    # Set up Optuna storage - use network-safe location if needed
    from emuses.utils.network_drive_detection import \
        setup_optuna_storage_with_cleanup_info

    storage_url, temp_sqlite_location = setup_optuna_storage_with_cleanup_info(
        "umap_nested_optimization", output_folder
    )

    # Run the outer optimization using the storage backend for parallelization.
    outer_study = optuna.create_study(
        direction="maximize",
        storage=storage_url,
        study_name="umap_nested_optimization",
        load_if_exists=True,
        sampler=optuna.samplers.TPESampler(seed=random_state),
    )
    print("Starting outer (UMAP) optimization...")
    if parallel_mode == "umap":
        outer_study.optimize(outer_objective, n_trials=n_trials, n_jobs=n_jobs)
    else:
        outer_study.optimize(outer_objective, n_trials=n_trials, n_jobs=1)
    print("Outer optimization completed.")

    # Retrieve best trial information.
    best_outer_trial = outer_study.best_trial
    best_umap_params = best_outer_trial.user_attrs["umap_params"]
    best_composite_score = outer_study.best_value
    # Instead of retrieving the clusterer and labels from the trial (which were not stored),
    # we use the global best_clusterer and best_labels variables.
    print(f"Best composite score: {best_composite_score}")
    print(f"Best UMAP parameters: {best_umap_params}")
    print(
        f"Best HDBSCAN parameters (from best trial): {best_outer_trial.user_attrs.get('hdbscan_best_params', 'N/A')}"
    )

    # Save best trial info to a JSON file.
    best_trial_info = {
        "trial_number": best_outer_trial.number,
        "param": {
            "umap": best_umap_params,
            "hdbscan": best_outer_trial.user_attrs.get("hdbscan_best_params", None),
        },
        "composite_score": best_composite_score,
        "metrics": {
            "umap": best_outer_trial.user_attrs.get("umap_metrics"),
            "hdbscan": best_outer_trial.user_attrs.get("hdbscan_metrics"),
        },
        "detailed": {
            "umap": best_outer_trial.user_attrs.get("detailed_umap_components"),
            "hdbscan": best_outer_trial.user_attrs.get("detailed_hdbscan_components"),
        },
    }
    log_path_best = output_folder / "best_trial_info.json"
    save_json(log_path_best, best_trial_info)
    print(f"Best trial info saved at: {log_path_best}")

    # Load the best UMAP model and embeddings that were saved during optimization.
    print("Loading best UMAP model and embeddings from saved files.")

    # Use ModelIOManager for loading
    manager = ModelIOManager(output_folder)
    umap_artifact = manager.load_model(model_name="best_umap_model", model_type="umap")

    if umap_artifact:
        best_umap_model = umap_artifact.model
        print(f"Successfully loaded UMAP model: {umap_artifact.metadata.description}")
    else:
        # Fallback to legacy loading
        print("Falling back to legacy loading method")
        best_umap_model = load(best_model_path)

    best_embeddings = np.load(best_embeddings_path)

    # Use the global best_clusterer and best_labels as determined during optimization.
    print("Retrieved best HDBSCAN results from outer optimization.")

    # Save an interactive clustering plot for the best trial.
    best_clustering_plot_path = output_folder / (
        f"{pref}_best_clustering.html" if pref else "best_clustering.html"
    )
    plot_clustering_interactive_with_hover(
        best_embeddings,
        best_labels,
        output_path=best_clustering_plot_path,
        show_plot=False,
        return_plot=False,
    )
    print(f"Interactive clustering plot saved at: {best_clustering_plot_path}")

    # Define final file paths.
    prefix = f"{pref}_" if pref else ""
    cluster_model_path = output_folder / f"{prefix}hdbscan_model.joblib"
    cluster_labels_path = output_folder / f"{prefix}cluster_labels.npy"

    # Save the final outputs using new I/O system where applicable
    np.save(best_model_path.parent / f"{prefix}embeddings.npy", best_embeddings)
    np.save(input_matrix_path, input_matrix)

    # Save HDBSCAN model using ModelIOManager directly
    hdbscan_manager = ModelIOManager(cluster_model_path.parent)
    hdbscan_manager.save_model(
        model=best_clusterer,
        model_name="hdbscan_model",
        model_type="hdbscan",
        config={
            "min_cluster_size": getattr(best_clusterer, "min_cluster_size", None),
            "min_samples": getattr(best_clusterer, "min_samples", None),
            "cluster_selection_epsilon": getattr(
                best_clusterer, "cluster_selection_epsilon", 0.0
            ),
            "max_cluster_size": getattr(best_clusterer, "max_cluster_size", None),
            "metric": getattr(best_clusterer, "metric", "euclidean"),
            "alpha": getattr(best_clusterer, "alpha", 1.0),
            "algorithm": getattr(best_clusterer, "algorithm", "best"),
            "leaf_size": getattr(best_clusterer, "leaf_size", 40),
            "cluster_selection_method": getattr(
                best_clusterer, "cluster_selection_method", "eom"
            ),
        },
        description=f"HDBSCAN clustering model with {getattr(best_clusterer, 'min_cluster_size', 'unknown')} min_cluster_size",
        tags=["clustering", "hdbscan", "optimization"],
        prefix=prefix.rstrip("_") if prefix else "",
    )

    np.save(cluster_labels_path, best_labels)

    print(f"UMAP model saved at: {best_model_path}")
    print(f"Embeddings saved at: {best_model_path.parent / f'{prefix}embeddings.npy'}")
    print(f"Input matrix saved at: {input_matrix_path}")
    print(f"HDBSCAN model saved at: {cluster_model_path}")
    print(f"Cluster labels saved at: {cluster_labels_path}")

    # Save the trial logs to a JSON file.
    log_path = output_folder / "parameter_search_log.json"
    save_json(log_path, trial_logs)
    print(f"Parameter search log saved at: {log_path}")

    # Generate and save an optimization history plot using Optuna's visualization.
    fig = ov.plot_optimization_history(outer_study)
    fig.write_html(str(output_folder / "optimization_history.html"))
    print(
        f"Optimization history plot saved at: {output_folder / 'optimization_history.html'}"
    )

    save_optimization_log_plot(
        trial_logs=trial_logs,
        optim_dict=optim_dict,
        output_folder=output_folder,
        plot_filename="optimization_log_plot.png",
    )

    # Clean up temporary SQLite location if it was used
    if temp_sqlite_location is not None:
        from emuses.utils.network_drive_detection import \
            cleanup_temp_sqlite_location

        cleanup_temp_sqlite_location(temp_sqlite_location, output_folder)

    return (
        best_umap_model,
        best_embeddings,
        best_model_path,
        best_model_path.parent / f"{prefix}embeddings.npy",
        best_clusterer,
        best_labels,
        cluster_model_path,
        cluster_labels_path,
        input_matrix_path,
    )


def train_and_save_umap_optim(
    input_matrix, output_folder, optim_dict, n_trials=50, random_state=42, **kwargs
):
    """
    Train a UMAP model with parameter optimization and save the results.

    Parameters:
        input_matrix (np.ndarray): Input data to train the UMAP model.
        output_folder (str or Path): Directory to save the model and embeddings.
        optim_dict (dict): Optimization dictionary defining parameters and metrics.
        n_trials (int): Number of optimization trials.
        random_state (int): Random seed for reproducibility.
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
        umap_params = params["umap"].copy()
        # Ensure random_state is set for reproducibility
        if "random_state" not in umap_params:
            umap_params["random_state"] = random_state
        umap_model = umap.UMAP(**umap_params, **kwargs)
        embeddings = umap_model.fit_transform(input_matrix)

        # Calculate metrics
        metrics_values_dict = {
            "umap": evaluate_embedding_statistics(
                embeddings, optim_dict["metrics"]["umap"]
            )
        }

        # If clustering is part of the optimization, evaluate HDBSCAN metrics
        if "hdbscan" in params:
            # Use the imported evaluate_hdbscan function
            metrics_values_dict["hdbscan"] = evaluate_hdbscan(
                embeddings, params["hdbscan"], optim_dict["metrics"]["hdbscan"]
            )

        # Calculate the composite score
        composite_score = calculate_composite_score(optim_dict, metrics_values_dict)
        return composite_score

    # Initialize and run the Optuna study with reproducible sampler
    sampler = optuna.samplers.TPESampler(seed=random_state)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=n_trials)

    # Retrieve the best parameters and score
    best_params = study.best_params
    best_score = study.best_value

    # Train the final UMAP model with the best parameters
    umap_params = best_params["umap"].copy()
    # Ensure random_state is set for reproducibility
    if "random_state" not in umap_params:
        umap_params["random_state"] = random_state
    best_umap_model = umap.UMAP(**umap_params, **kwargs)
    best_embeddings = best_umap_model.fit_transform(input_matrix)

    # Save the best model and embeddings using new I/O system
    manager = ModelIOManager(output_folder)
    umap_filepath = manager.save_model(
        model=best_umap_model,
        model_name="best_umap_model",
        model_type="umap",
        config={"best_params": best_params, "n_trials": n_trials},
        description=f"Best UMAP model from {n_trials} trials with score {best_score}",
        tags=["optimization", "final_model"],
    )

    np.save(output_folder / "best_embeddings.npy", best_embeddings)
    print(f"UMAP model saved using ModelIOManager: {umap_filepath}")
    print(f"Embeddings saved at: {output_folder / 'best_embeddings.npy'}")

    return {
        "best_model": best_umap_model,
        "best_embeddings": best_embeddings,
        "best_params": best_params,
        "best_score": best_score,
        "output_folder": output_folder,
    }


def train_and_save_umap_with_bayesian_search(
    input_matrix,
    output_folder,
    param_ranges,
    n_trials=50,
    maximize_metrics=None,
    pref=None,
    random_state=42,
    optuna_seed=None,
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
    - random_state: int, default=42
        Random seed for model training for reproducibility.
    - optuna_seed: int, optional
        Random seed for Optuna hyperparameter optimization. If None, uses random_state.
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
                    param_name,
                    param_info["low"],
                    param_info["high"],
                    step=param_info.get("step", 1),
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

        # Train UMAP model with suggested parameters and set random_state
        umap_params = {**params, "random_state": random_state}
        umap_model = umap.UMAP(**umap_params, **kwargs)
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
            interactive=False,  # Save as static image
        )
        print(
            f"Trial {trial.number + 1}: Saved plot at {trial_subfolder / f'embeddings_{trial.number}.png'}"
        )

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

    # Initialize Optuna study with seed for reproducibility
    if optuna_seed is None:
        optuna_seed = random_state
    study = optuna.create_study(
        direction="maximize", sampler=optuna.samplers.TPESampler(seed=optuna_seed)
    )
    print("Optuna study created with seed for reproducibility.")

    # Run optimization
    study.optimize(objective, n_trials=n_trials)
    print("Optuna optimization completed.")

    # Retrieve the best parameters
    best_params = study.best_params
    best_score = study.best_value
    print(f"Best Parameters: {best_params}")
    print(f"Best Objective Score: {best_score}")

    # Train the UMAP model with the best parameters and random_state
    best_params_with_random_state = {**best_params, "random_state": random_state}
    best_umap_model = umap.UMAP(**best_params_with_random_state, **kwargs)
    best_embeddings = best_umap_model.fit_transform(input_matrix)
    print("Trained UMAP model with best parameters and consistent random state.")

    # Save the model, embeddings, and input matrix using new I/O system
    prefix = f"{pref}_" if pref else ""

    # Save UMAP model using ModelIOManager
    manager = ModelIOManager(output_folder)
    umap_filepath = manager.save_model(
        model=best_umap_model,
        model_name=f"{prefix}umap_model" if prefix else "umap_model",
        model_type="umap",
        config={
            "best_params": best_params,
            "n_trials": n_trials,
            "maximize_metrics": maximize_metrics,
        },
        description=f"Best UMAP model from Bayesian search with {n_trials} trials",
        tags=(
            ["bayesian_optimization", "final_model", pref]
            if pref
            else ["bayesian_optimization", "final_model"]
        ),
    )
    print(f"UMAP model saved using ModelIOManager: {umap_filepath}")

    # Save embeddings and input matrix
    embeddings_filename = f"{prefix}embeddings.npy"
    input_matrix_filename = f"{prefix}input_matrix.npy"

    np.save(output_folder / embeddings_filename, best_embeddings)
    print(f"Embeddings saved at: {output_folder / embeddings_filename}")

    np.save(output_folder / input_matrix_filename, input_matrix)
    print(f"Input matrix saved at: {output_folder / input_matrix_filename}")

    return (
        best_umap_model,
        best_embeddings,
        umap_filepath,
        output_folder / embeddings_filename,
        output_folder / input_matrix_filename,
    )


def is_umap_file(umap_path):
    return str(umap_path).endswith(".joblib")


def load_umap_model(
    base_path, prefix="", model_name="umap_model", joblib_version_override=None
):
    """
    Load a UMAP model using the enhanced model I/O system.

    Parameters:
    -----------
    base_path : Path or str
        The directory or file where the UMAP model is saved.
    prefix : str
        Prefix for the UMAP model filename.
    model_name : str
        Base name of the model.
    joblib_version_override : str, optional
        Specific joblib version to use in filename. If None, uses current joblib version.

    Returns:
    --------
    loaded_umap : object or None
        Loaded UMAP model or None if loading failed.
    filepath : Path
        Path of the loaded file or next available filename if loading failed.
    """
    base_path = Path(base_path)

    # If base_path is a file, attempt to load it directly using legacy method.
    if base_path.is_file():
        try:
            loaded_umap = joblib.load(base_path)
            print(f"Successfully loaded UMAP model from file: {base_path}")
            return loaded_umap, base_path
        except Exception as e:
            print(f"Failed to load UMAP model from file: {base_path}, due to: {e}")

    # Try to load using the new model I/O system first
    try:
        manager = ModelIOManager(base_path)

        # Construct model name with prefix if provided
        full_model_name = f"{prefix}_{model_name}" if prefix else model_name

        artifact = manager.load_model(model_name=full_model_name, model_type="umap")

        if artifact:
            print(
                f"Successfully loaded UMAP model using ModelIOManager: {artifact.filepath}"
            )
            if hasattr(artifact.metadata, "description"):
                print(f"Model description: {artifact.metadata.description}")
            return artifact.model, artifact.filepath
        else:
            print(f"No UMAP model found with name: {full_model_name}")

    except Exception as e:
        print(f"Failed to load UMAP model using new I/O system: {e}")

    # Fallback to legacy loading method
    current_joblib_version = joblib.__version__
    effective_joblib_version = (
        joblib_version_override if joblib_version_override else current_joblib_version
    )

    if prefix:
        filename = f"{prefix}_{model_name}_joblib{effective_joblib_version}.joblib"
    else:
        filename = f"{model_name}_joblib{effective_joblib_version}.joblib"

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

    # Try other versions in the directory
    pattern = (
        f"{prefix}_{model_name}_joblib*.joblib"
        if prefix
        else f"{model_name}_joblib*.joblib"
    )
    candidate_files = list(base_path.glob(pattern))
    candidate_files.sort()
    for candidate in candidate_files:
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
    print(
        f"No suitable model found. Returning next available filename: {next_filepath}"
    )
    return None, next_filepath
