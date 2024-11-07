from pathlib import Path

import numpy as np
from pandas.core.common import random_state
from scipy.stats import pointbiserialr
from tools.stats_utils import compute_gaussian_filter

from tools.stats_utils import input_matrix_stat_map
from tools.output_utils import save_statistical_maps
from tools.visualisation import plot_statistical_map, plot_clustering


# Function to calculate point-biserial correlation for each point in the grid
def calculate_pointbiserial_grid(embeddings, train_labels_bin, grid_size, sigma=0.5):
    """
    Calculate point-biserial correlations over a grid to evaluate the relationship between the embeddings and the labels.

    Parameters:
    embeddings (np.array): Array of shape (n_samples, n_features) containing the embedding coordinates.
    train_labels_bin (np.array): Binary labels corresponding to each embedding.
    grid_size (int): Number of grid points along each dimension.
    sigma (float or list of floats): Standard deviation for the Gaussian filter used in distance computation.

    Returns:
    correlation_matrix (np.array): Correlation values for each grid point.
    grid_x (np.array): X-coordinates of the grid.
    grid_y (np.array): Y-coordinates of the grid.
    """
    min_coords = embeddings.min(axis=0)
    max_coords = embeddings.max(axis=0)

    grid_x = np.linspace(min_coords[0], max_coords[0], grid_size)
    grid_y = np.linspace(min_coords[1], max_coords[1], grid_size)

    grid_points = np.array(np.meshgrid(grid_x, grid_y)).T.reshape(-1, 2)

    correlation_matrix = np.zeros((grid_size, grid_size))

    if isinstance(sigma, (list, np.ndarray)):  # Multi-scale approach
        for s in sigma:
            temp_correlation_matrix = np.zeros((grid_size, grid_size))
            dist_vectors = np.array(
                [compute_gaussian_filter(embeddings, coord.reshape(1, -1), sigma=s) for coord in grid_points])
            for idx, coord in enumerate(grid_points):
                dist_vector = dist_vectors[idx]
                if np.all(dist_vector == dist_vector[0]):  # Check if dist_vector is constant
                    correlation = 0  # Set to 0 or np.nan if you prefer
                else:
                    correlation, _ = pointbiserialr(dist_vector, train_labels_bin)
                temp_correlation_matrix[idx // grid_size, idx % grid_size] = correlation
            correlation_matrix += temp_correlation_matrix
        correlation_matrix /= len(sigma)
    else:  # Single sigma approach
        dist_vectors = np.array(
            [compute_gaussian_filter(embeddings, coord.reshape(1, -1), sigma=sigma) for coord in grid_points])
        for idx, coord in enumerate(grid_points):
            dist_vector = dist_vectors[idx]
            # Check if dist_vector or train_labels_bin is close to 0
            if np.all(np.isclose(dist_vector, 0)) or np.all(np.isclose(train_labels_bin, 0)):
                correlation = 0  # Set to 0 or np.nan if you prefer
            else:
                correlation, _ = pointbiserialr(dist_vector, train_labels_bin)
            correlation_matrix[idx // grid_size, idx % grid_size] = correlation

    return correlation_matrix, grid_x, grid_y


# Function to calculate point-biserial correlation for each embedding
def calculate_pointbiserial(embeddings, train_labels_bin, sigma=0.5):
    """
    Calculate point-biserial correlations for each embedding.

    Parameters:
    embeddings (np.array): Array of shape (n_samples, n_features) containing the embedding coordinates.
    train_labels_bin (np.array): Binary labels corresponding to each embedding.
    sigma (float or list of floats): Standard deviation for the Gaussian filter used in distance computation.

    Returns:
    correlations (np.array): Correlation values for each embedding.
    """
    # correlations = np.full(embeddings.shape[0], np.nan)  # Initialize with np.nan to differentiate uncalculated values
    correlations = np.zeros(embeddings.shape[0])  # Initialize with zeros

    if isinstance(sigma, (list, np.ndarray)):  # Multi-scale approach
        for s in sigma:
            temp_correlations = np.zeros(embeddings.shape[0])
            for idx, embedding in enumerate(embeddings):
                dist_vector = compute_gaussian_filter(embeddings, embedding.reshape(1, -1), sigma=s)
                if np.all(dist_vector == dist_vector[0]):  # Check if dist_vector is constant
                    correlation = 0  # Set to 0 or np.nan if you prefer
                else:
                    correlation, _ = pointbiserialr(dist_vector, train_labels_bin)
                temp_correlations[idx] = correlation
            correlations += temp_correlations
        correlations /= len(sigma)
    else:  # Single sigma approach
        for idx, embedding in enumerate(embeddings):
            dist_vector = compute_gaussian_filter(embeddings, embedding.reshape(1, -1), sigma)
            if np.all(dist_vector == dist_vector[0]):  # Check if dist_vector is constant
                correlation = 0  # Set to 0 or np.nan if you prefer
            else:
                correlation, _ = pointbiserialr(dist_vector, train_labels_bin)
            correlations[idx] = correlation

    return correlations


# Function to filter coordinates based on correlations and optionally perform clustering
def filter_coordinates(coordinates, correlations, correlation_threshold=0.3):
    """
    Filter coordinates based on point-biserial correlation values.

    Parameters:
    coordinates (np.array): Array of shape (n_samples, 2) containing the coordinates.
    correlations (np.array): Array of shape (n_samples,) containing the correlation values for each coordinate.
    correlation_threshold (float): Correlation threshold for filtering points.

    Returns:
    filtered_coordinates (np.array): Filtered coordinates.
    filtered_indices (np.array): Indices of the filtered coordinates.

    Note:
    Ensure that the `correlation_threshold` is chosen carefully to retain relevant data points without excessive noise.
    """
    # Filter coordinates based on correlation threshold
    filtered_indices = np.where(correlations > correlation_threshold)[0]
    filtered_coordinates = coordinates[filtered_indices]

    return filtered_coordinates, filtered_indices


def run_heatmap_analysis(
    embeddings, scores_vectors_dict, input_matrix, output_folder, output_format_info, clusterer, cluster_labels,
    input_type='image',
    grid_size=100, sigma=None, correlation_threshold=0.3, highlight_points=True, show_plots=False,
    generate_plots=False
):
    """
    Run heatmap creation, point-biserial correlation, and statistical analysis on the provided embeddings.

    Parameters:
    - embeddings : np.ndarray
        Array of embeddings to analyze.
    - scores_vectors_dict : dict
        Dictionary containing score tags and their corresponding binary score vectors.
    - input_matrix : np.ndarray
        The original input data matrix used for analysis.
    - output_folder : str
        Path to the folder where results should be saved.
    - output_format_info : various
        Information needed to format the output. Could be an affine matrix (for NIfTI),
        an output shape (for images), or a list of column names (for spreadsheets).
    - clusterer : HDBSCAN object
        The trained clusterer (e.g., HDBSCAN model) used for clustering.
    - cluster_labels : np.ndarray
        Cluster labels from the clustering step for each point in the embedding.
    - input_type : str, optional
        Type of the input data ('image', 'nifti', 'spreadsheet').
    - grid_size : int, optional
        Size of the grid for point-biserial correlations.
    - sigma : float or list of floats
        Sigma value for Gaussian smoothing. This determines the scale of the distance computation.
    - correlation_threshold : float, optional
        Threshold for filtering coordinates based on correlation.
    - highlight_points : bool, optional
        Whether to highlight filtered points based on the correlation threshold.
    - show_plots : bool, optional
        Whether to display plots interactively.
    - generate_plots : bool, optional
        Whether to generate and return plots. Default is False.

    Returns:
    - plots : dict
        Dictionary containing plots per score_tag and cluster.
    """
    if sigma is None:
        sigma_percentage = np.array([0.005, 0.01, 0.02, 0.03])
        sigma = sigma_percentage / np.max(embeddings)

    plots = {} if generate_plots else None  # Dictionary to collect plots per score_tag

    for score_tag, train_labels_bin in scores_vectors_dict.items():
        # Step 1: Calculate point-biserial correlations over a grid
        print("Calculating point-biserial correlations over a grid...")
        correlation_matrix, grid_x, grid_y = calculate_pointbiserial_grid(
            embeddings, train_labels_bin, grid_size=grid_size, sigma=sigma
        )
        print(f"Point-biserial grid correlations for score {score_tag} calculated successfully.")

        # Step 2: Calculate point-biserial correlations for each embedding
        print("Calculating point-biserial correlations for each embedding...")
        correlations = calculate_pointbiserial(embeddings, train_labels_bin, sigma=sigma)
        print(f"Point-biserial correlations for score {score_tag} calculated successfully.")

        # Step 3: Filter coordinates based on correlation values
        print("Filtering coordinates based on correlation values...")
        filtered_coordinates, filtered_indices = filter_coordinates(
            embeddings, correlations, correlation_threshold=correlation_threshold
        )
        print(f"Filtered coordinates calculated successfully for score {score_tag}. Number of points after filtering: "
              f"{len(filtered_coordinates)}")

        # Step 4: Get cluster labels for filtered coordinates
        print("Getting cluster labels for filtered coordinates...")
        if filtered_coordinates.shape[0] > 0:
            filtered_cluster_labels = cluster_labels[filtered_indices]
            print("Cluster labels obtained successfully for filtered coordinates.")
        else:
            filtered_cluster_labels = np.array([])
            print("No filtered coordinates available for obtaining cluster labels.")

        # Step 5: Separate filtered coordinates by cluster and run statistical analysis
        unique_clusters = np.unique(filtered_cluster_labels)
        if generate_plots:
            plots[score_tag] = {}  # Initialize a dictionary for this score_tag's plots

        for cluster in unique_clusters:
            if cluster == -1:
                continue  # Skip noise points
            cluster_mask = (filtered_cluster_labels == cluster)
            cluster_indices = filtered_indices[cluster_mask]

            print(f"Running statistical analysis for cluster {cluster}...")
            # Run statistical analysis to get the effect_size_map
            stat_map, _, _ = input_matrix_stat_map(
                input_matrix, cluster_indices, test_name='mann-whitney', n_cores=-1
            )
            print(f"Statistical analysis for cluster {cluster} completed.")

            # Save the effect size map and generate plots if requested
            stat_maps_to_save = {cluster: stat_map}
            effect_size_plots = save_statistical_maps(
                stat_maps=stat_maps_to_save,
                output_folder=output_folder,
                input_type=input_type,
                output_format_info=output_format_info,
                filename_prefix=f'effect_size_map_score_{score_tag}_cluster_{cluster}',
                save_output=True,
                generate_plots=generate_plots
            )
            print(f"Effect size map saved for cluster {cluster} and score {score_tag}.")

            # Collect the effect size plot
            if generate_plots and effect_size_plots:
                plots[score_tag][cluster] = effect_size_plots[cluster]

        # Step 6: Plot clustering of the whole space
        if generate_plots and clusterer is not None and filtered_coordinates.shape[0] == filtered_cluster_labels.shape[0]:
            print("Plotting clustering of the whole space...")
            plot_fig = plot_clustering(
                embeddings=embeddings,
                clusterer=clusterer,
                grid_x=grid_x,
                grid_y=grid_y,
                gaussian_matrix=correlation_matrix,
                filtered_indices=filtered_indices,
                filtered_embeddings=filtered_coordinates,
                cluster_labels=filtered_cluster_labels,
                score_tag=score_tag,
                highlight_points=highlight_points,
                show_plot=show_plots,
                save_path=Path(output_folder) / f'clustering_plot_{score_tag}.png'
            )
            # Store the plot under the score_tag
            plots[score_tag]['clustering_plot'] = plot_fig
            print("Clustering plot created successfully.")
        else:
            print("Mismatch in dimensions or clustering failed. Skipping the plot.")

    return plots  # Return the collected plots if generate_plots is True
