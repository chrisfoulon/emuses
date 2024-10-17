import numpy as np
import hdbscan
from pandas.core.common import random_state
from scipy.stats import pointbiserialr
from tools.stats_utils import compute_gaussian_filter


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
            if np.all(dist_vector == dist_vector[0]):  # Check if dist_vector is constant
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


# Function to perform HDBSCAN clustering on filtered coordinates
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
