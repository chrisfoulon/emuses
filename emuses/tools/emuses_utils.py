import os
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import umap
from joblib import dump, load
from matplotlib import pyplot as plt
from scipy.ndimage import gaussian_filter
from scipy.stats import mannwhitneyu, pearsonr, pointbiserialr, spearmanr
from statsmodels.stats.multitest import multipletests
from tqdm import tqdm

from emuses.tools.stats_utils import process_column
from emuses.tools.visualisation import plot_embeddings

# def rescale_embedding(embedding, margin=0, max_coordinates=None, min_coordinates=None):
#     if max_coordinates is None:
#         max_coordinates = np.max(embedding, axis=0)
#     if min_coordinates is None:
#         min_coordinates = np.min(embedding, axis=0)
#
#     # Rescale the embedding between 0 and 1
#     rescaled_embedding = (embedding - min_coordinates) / (max_coordinates - min_coordinates)
#
#     if margin != 0:
#         # Compute the margin in the rescaled space
#         margin_rescaled = margin / 100
#
#         # Subtract the margin from the maximum coordinates and add the margin to the minimum coordinates
#         rescaled_embedding = rescaled_embedding * (1 - 2 * margin_rescaled) + margin_rescaled
#
#     return rescaled_embedding


def rescale_embedding(embedding, margin=0, preset_max=None, preset_min=None):
    if preset_max is None:
        max_value = np.max(embedding)
    else:
        max_value = preset_max

    if preset_min is None:
        min_value = np.min(embedding)
    else:
        min_value = preset_min

    # Rescale the embedding between 0 and 1 while keeping proportions
    rescaled_embedding = (embedding - min_value) / (max_value - min_value)

    if margin != 0:
        # Compute the margin in the rescaled space
        margin_rescaled = margin / 100

        # Subtract the margin from the maximum coordinates and add the margin to the minimum coordinates
        rescaled_embedding = (
            rescaled_embedding * (1 - 2 * margin_rescaled) + margin_rescaled
        )

    return rescaled_embedding


# def inverse_rescale_embedding(rescaled_embedding, margin=0, max_coordinates=None, min_coordinates=None):
#     if margin != 0:
#         # Reverse the margin scaling
#         margin_rescaled = margin / 100
#         rescaled_embedding = (rescaled_embedding - margin_rescaled) / (1 - 2 * margin_rescaled)
#
#     # Perform the inverse of the rescaling operation
#     embedding = rescaled_embedding * (max_coordinates - min_coordinates) + min_coordinates
#
#     return embedding


def inverse_rescale_embedding(
    rescaled_embedding, margin=0, max_value=None, min_value=None
):
    if margin != 0:
        # Reverse the margin scaling
        margin_rescaled = margin / 100
        rescaled_embedding = (rescaled_embedding - margin_rescaled) / (
            1 - 2 * margin_rescaled
        )

    # Perform the inverse of the rescaling operation
    embedding = rescaled_embedding * (max_value - min_value) + min_value

    return embedding


def project_embeddings(rescaled_embeddings, cells_per_dimension):
    # Convert the rescaled embedding coordinates to indices in the discrete space
    indices = np.round(rescaled_embeddings * (cells_per_dimension - 1)).astype(int)

    # Create an array of zeros with the shape of the grid
    discrete_space = np.zeros(cells_per_dimension, dtype=int)

    # Set the corresponding indices in the discrete space to 1
    discrete_space[tuple(indices.T)] = 1

    return discrete_space


def compute_discrete_space(rescaled_embedding, cells_per_dimension, cells_values=1):
    rescaled_maximum_coords = np.max(rescaled_embedding, axis=0)

    # Create a grid of points in the N-dimensional space
    grid_points = [
        np.linspace(0, max_coord, num_cells)
        for max_coord, num_cells in zip(rescaled_maximum_coords, cells_per_dimension)
    ]

    # Create a grid of points in the N-dimensional space
    np.meshgrid(*grid_points, indexing="ij")

    # Create an array of zeros with the shape of the grid
    discrete_space = np.zeros(cells_per_dimension, dtype=int)

    # Convert the rescaled embedding coordinates to indices in the discrete space
    indices = np.round(rescaled_embedding * (np.array(cells_per_dimension) - 1)).astype(
        int
    )

    # compute the percentage of overlap (number of pixels that contain multiple points compared
    # with the total number of points). Just check the number of unique indices
    overlap = 1 - np.unique(indices, axis=0).shape[0] / rescaled_embedding.shape[0]
    overlap *= 100

    # Set the corresponding indices in the discrete space to 1
    discrete_space[tuple(indices.T)] = cells_values

    return discrete_space, indices, overlap


def optimize_discrete_space(rescaled_embedding, overlap_percentage):
    if overlap_percentage < 0 or overlap_percentage >= 100:
        raise ValueError("Overlap percentage must be between 0 and 100[exclusive]")
    rescaled_maximum_coords = np.max(rescaled_embedding, axis=0)
    aspect_ratio = rescaled_maximum_coords / np.max(rescaled_maximum_coords)
    cells_per_dimension = np.array(aspect_ratio).astype(int)
    overlap = 100
    discrete_space = None
    points = None
    prev_discrete_space = None
    prev_points = None
    prev_overlap = None
    prev_cells_per_dimension = None
    factor_ratio = 2
    while overlap >= overlap_percentage:
        prev_discrete_space = discrete_space
        prev_points = points
        prev_overlap = overlap
        prev_cells_per_dimension = cells_per_dimension
        factor_ratio *= 2
        cells_per_dimension = np.array(
            [dim * factor_ratio for dim in aspect_ratio]
        ).astype(int)
        # print(f'\rTrying {cells_per_dimension} cells per dimension', end='')
        # print(f'Trying {cells_per_dimension} cells per dimension')
        discrete_space, points, overlap = compute_discrete_space(
            rescaled_embedding, cells_per_dimension=cells_per_dimension
        )
    lower_bound = prev_cells_per_dimension
    upper_bound = cells_per_dimension
    while np.any(upper_bound - lower_bound > 1):
        mid_point = (upper_bound + lower_bound) // 2
        discrete_space, points, overlap = compute_discrete_space(
            rescaled_embedding, cells_per_dimension=mid_point
        )
        if overlap > overlap_percentage:
            lower_bound = mid_point
        else:
            upper_bound = mid_point
            prev_discrete_space = discrete_space
            prev_points = points
            prev_overlap = overlap
            prev_cells_per_dimension = mid_point
    return prev_discrete_space, prev_points, prev_overlap, prev_cells_per_dimension


def plot_embeddings_old(embeddings, title, rescaled_mode=False):
    if rescaled_mode:
        if np.any(embeddings < 0) or np.any(embeddings > 1):
            print(
                "Some values are outside the [0, 1] interval and will not be displayed on the plot."
            )

    if embeddings.shape[1] == 2:
        plt.scatter(embeddings[:, 0], embeddings[:, 1], s=2)
        plt.axis("equal")  # Set the aspect ratio of the plot to be equal
        if rescaled_mode:
            plt.xlim(0, 1)
            plt.ylim(0, 1)
    elif embeddings.shape[1] == 3:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        ax.scatter(embeddings[:, 0], embeddings[:, 1], embeddings[:, 2], s=2)
        ax.set_box_aspect([1, 1, 1])  # Set the aspect ratio of the 3D plot to be equal
        if rescaled_mode:
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.set_zlim(0, 1)
    else:
        raise ValueError(
            f"Plotting this number of dimensions {embeddings.shape[1]} of the embedding is not supported"
        )
    plt.title(title)
    plt.show()
    plt.close()


def compute_stats_on_smoothed_nplusone_dim_discrete_space(
    heatmap, scores, function="pearson", correction_method=None
):
    """
    Compute the statistics on the smoothed n+1 dimensional discrete space
    Parameters
    ----------
    heatmap : Heatmap
    scores : np.ndarray
    function : str
    correction_method : str

    Returns
    -------
    statistics : np.ndarray
        The computed statistics
    pvalues : np.ndarray
        The computed p-values
    corrected_pvalues : np.ndarray
        The corrected p-values
    reject : np.ndarray, bool
        The rejection of the null hypothesis

    """
    if heatmap.smoothed_nplusone_dim_discrete_space is None:
        raise ValueError(
            "The smoothed n+1 dim discrete space must be computed before the statistics"
        )

    # Replace all-zero vectors with nan
    smoothed_space = heatmap.smoothed_nplusone_dim_discrete_space.copy()
    # replace all the zero vectors (along dim 0) with nans
    smoothed_space[:, np.all(smoothed_space == 0, axis=0)] = np.nan

    function_mapping = {
        "pearson": pearsonr,
        "spearman": spearmanr,
        "pointbiserialr": pointbiserialr,
        "mannwhitney": mannwhitneyu,
    }

    if function not in function_mapping:
        raise ValueError(
            f"Invalid function. Expected one of: {list(function_mapping.keys())}"
        )

    stats = np.apply_along_axis(
        lambda x: (
            function_mapping[function](x, scores)
            if np.isfinite(x).all()
            else (np.nan, np.nan)
        ),
        0,
        smoothed_space,
    )

    statistics = stats[
        0
    ]  # assuming the first value in the stats array is the statistic

    pvalues = stats[1]  # assuming the second value in the stats array is the p-value

    if (
        correction_method and np.unique(pvalues).size > 1
    ):  # Check if all p-values are the same
        reject, corrected_pvalues, _, _ = multipletests(
            pvalues.flatten(), method=correction_method
        )
        # corrected_pvalues needs to be reshaped to the same shape as the pvalues
        corrected_pvalues = corrected_pvalues.reshape(pvalues.shape)
    else:
        reject, corrected_pvalues = None, None
        print("No correction method was provided or all p-values are the same")

    return statistics, pvalues, corrected_pvalues, reject


def compute_categorical_stats_on_smoothed_nplusone_dim_discrete_space(
    heatmap, scores, test_name="t-test", correction_method=None, ncores=-1
):
    """
    Compute the statistics on the smoothed n+1 dimensional discrete space
    Parameters
    ----------
    heatmap : Heatmap
    scores : np.ndarray
    test_name : str
    correction_method : str
    ncores : int

    Returns
    -------
    statistics : np.ndarray
        The computed statistics
    pvalues : np.ndarray
        The computed p-values
    corrected_pvalues : np.ndarray
        The corrected p-values
    reject : np.ndarray, bool
        The rejection of the null hypothesis

    """
    if heatmap.smoothed_nplusone_dim_discrete_space is None:
        raise ValueError(
            "The smoothed n+1 dim discrete space must be computed before the statistics"
        )

    # Replace all-zero vectors with nan
    smoothed_space = heatmap.smoothed_nplusone_dim_discrete_space.copy()
    # replace all the zero vectors (along dim 0) with nans
    smoothed_space[:, np.all(smoothed_space == 0, axis=0)] = np.nan

    if test_name not in {"t-test", "mann-whitney"}:
        raise ValueError(
            f"Invalid function. Expected one of: {list({'t-test', 'mann-whitney'})}"
        )

    if ncores == -1:
        ncores = os.cpu_count()

    with Pool(processes=ncores) as pool:
        tasks = [
            (smoothed_space[:, i, j], scores, test_name, (i, j))
            for i in range(smoothed_space.shape[1])
            for j in range(smoothed_space.shape[2])
        ]
        results = list(tqdm(pool.imap(process_column, tasks), total=len(tasks)))
    ind, statistics, pvalues, effect_size = zip(*results)
    statistics = np.array(statistics).reshape(
        smoothed_space.shape[1], smoothed_space.shape[2]
    )
    pvalues = np.array(pvalues).reshape(
        smoothed_space.shape[1], smoothed_space.shape[2]
    )
    effect_size = np.array(effect_size).reshape(
        smoothed_space.shape[1], smoothed_space.shape[2]
    )

    if (
        correction_method and np.unique(pvalues).size > 1
    ):  # Check if all p-values are the same
        reject, corrected_pvalues, _, _ = multipletests(
            pvalues.flatten(), method=correction_method
        )
        # corrected_pvalues needs to be reshaped to the same shape as the pvalues
        corrected_pvalues = corrected_pvalues.reshape(pvalues.shape)
    else:
        reject, corrected_pvalues = None, None
        print("No correction method was provided or all p-values are the same")

    return statistics, pvalues, corrected_pvalues, reject, effect_size


def compute_stats_on_corrected_clusters(
    heatmap, scores, function="pearson", correction_method=None
):
    """
    Compute the statistics on clusters formed by identical vectors in the smoothed n+1 dimensional discrete space,
    correctly focusing on dimension 0 for identifying unique vectors.
    """
    if heatmap.smoothed_nplusone_dim_discrete_space is None:
        raise ValueError(
            "The smoothed n+1 dim discrete space must be computed before the statistics"
        )

    # Convert to float and replace zeros with NaN for calculation purposes
    smoothed_space = np.nan_to_num(
        heatmap.smoothed_nplusone_dim_discrete_space, nan=np.nan
    ).astype(float)

    # Reshape for a generic n-D case, keeping the first dimension separate
    original_shape = smoothed_space.shape  # Save original shape
    vectors = smoothed_space.reshape(
        smoothed_space.shape[0], -1
    ).T  # Transpose to make vectors along rows

    # Find unique rows (vectors) and their inverse indices to reconstruct the original array later
    unique_vectors, inverse_indices = np.unique(vectors, axis=0, return_inverse=True)

    print(f"unique_vectors shape: {unique_vectors.shape}")
    print(f"vectors shape: {vectors.shape}")

    function_mapping = {
        "pearson": pearsonr,
        "spearman": spearmanr,
        "mannwhitney": mannwhitneyu,
    }

    if function not in function_mapping:
        raise ValueError(
            f"Invalid function. Expected one of: {list(function_mapping.keys())}"
        )

    # Initialize arrays to hold the results for each unique vector
    statistics = np.empty(unique_vectors.shape[0])
    pvalues = np.empty(unique_vectors.shape[0])

    # Compute statistics for each unique vector
    for i, vector in enumerate(unique_vectors):
        if np.isnan(vector).all():
            statistics[i], pvalues[i] = np.nan, np.nan
        else:
            statistic, pvalue = function_mapping[function](vector, scores)
            statistics[i], pvalues[i] = statistic, pvalue

    # Applying correction if necessary
    if correction_method and not np.all(np.isnan(pvalues)):
        reject, corrected_pvalues, _, _ = multipletests(
            pvalues, method=correction_method
        )
    else:
        corrected_pvalues = np.full(pvalues.shape, np.nan)  # Initialize with NaN
        reject = np.full(
            pvalues.shape, False, dtype=bool
        )  # Assume no rejection if correction not applicable

    # Mapping results back to the original space
    final_statistics = statistics[inverse_indices].reshape(original_shape[1:])
    final_pvalues = pvalues[inverse_indices].reshape(original_shape[1:])
    final_corrected_pvalues = corrected_pvalues[inverse_indices].reshape(
        original_shape[1:]
    )
    final_reject = reject[inverse_indices].reshape(original_shape[1:])

    return final_statistics, final_pvalues, final_corrected_pvalues, final_reject


class DiscreteLatentSpace:
    def __init__(self, trained_umap, raw_embeddings=None, margin=0):
        self.overlap = None
        self.margin = margin
        self.trained_umap = trained_umap
        # if raw_embeddings is None, either we can load the trained UMAP model and get the embeddings, the UMAP is
        # already loaded, or we throw an error
        if raw_embeddings is None:
            if isinstance(trained_umap, str) or isinstance(trained_umap, os.PathLike):
                print("Loading the trained UMAP model to get the embeddings")
                self.trained_umap = load(trained_umap)
            else:
                if not isinstance(trained_umap, umap.UMAP):
                    raise ValueError(
                        "The raw embeddings must be provided if the trained UMAP model is not"
                    )
            self.raw_embeddings = self.trained_umap.embedding_
        else:
            self.raw_embeddings = raw_embeddings
        self.max_coordinates = self.raw_embeddings.max()
        self.min_coordinates = self.raw_embeddings.min()
        self.rescaled_embeddings = self.rescale_embedding(self.raw_embeddings)
        self.discrete_space = None
        self.discrete_embeddings = None
        self.cells_per_dimension = None
        self.heatmaps = {}

    """
    Getters setters
    """

    @property
    def trained_umap(self):
        return self._trained_umap

    @trained_umap.setter
    def trained_umap(self, trained_umap):
        self._trained_umap = trained_umap

    """
    Embedding spaces transformations
    """

    def rescale_embedding(self, embedding):
        return rescale_embedding(
            embedding, self.margin, self.max_coordinates, self.min_coordinates
        )

    def inverse_rescale_embedding(self, rescaled_embedding):
        return inverse_rescale_embedding(
            rescaled_embedding, self.margin, self.max_coordinates, self.min_coordinates
        )

    def create_discrete_space(
        self, rescaled_embedding, overlap_percentage=None, cells_per_dimension=None
    ):
        if cells_per_dimension is not None:
            self.discrete_space, self.discrete_embeddings, self.overlap = (
                compute_discrete_space(rescaled_embedding, cells_per_dimension)
            )
            self.cells_per_dimension = cells_per_dimension
        else:
            (
                self.discrete_space,
                self.discrete_embeddings,
                self.overlap,
                self.cells_per_dimension,
            ) = optimize_discrete_space(rescaled_embedding, overlap_percentage)
        print(
            f"There is an overlap of {self.overlap:.2f}% points in the discrete space"
        )
        print(
            f"The number of cells in the discrete space is {np.prod(self.discrete_space.shape)}"
        )
        print(f"The shape of the discrete space is {self.discrete_space.shape}")
        print(f"Maximum in each dimension: {self.max_coordinates}")

    def pixelate_new_embedding(self, new_rescaled_embedding):
        discrete_new_embedding, _, _ = compute_discrete_space(
            new_rescaled_embedding, self.cells_per_dimension
        )
        return discrete_new_embedding

    """
    Heatmap methods
    """

    def create_heatmap_spaces(
        self, embeddings_scores_df, name, smoothing_fwhm=None, smoothing_sigma=None
    ):
        """
        Create a heatmap from a DataFrame with embeddings and scores.

        Parameters
        ----------
        embeddings_scores_df : pandas.DataFrame
            DataFrame with two columns: one with embeddings (tuples or arrays), and the other with scores.
        name : str
            The name to assign to the heatmap.
        smoothing_sigma : float, optional
            The standard deviation of the Gaussian kernel used for smoothing the heatmap, by default None
        smoothing_fwhm : float, optional
            The full width at half maximum of the Gaussian kernel used for smoothing the heatmap, by default 10

        """
        if name in self.heatmaps:
            raise ValueError(f"A heatmap with the name {name} already exists")

        if embeddings_scores_df.shape[1] != 2:
            raise ValueError(
                "The DataFrame must contain exactly two columns: one for embeddings and one for scores."
            )

        # Extract embeddings and scores from the DataFrame
        embeddings_col_name, scores_col_name = embeddings_scores_df.columns
        embeddings = np.array(
            [tuple(row) for row in embeddings_scores_df[embeddings_col_name]]
        )
        scores = np.array(embeddings_scores_df[scores_col_name])

        if embeddings.shape[0] != len(scores):
            raise ValueError("The number of embeddings and scores must be the same.")

        # Create a Heatmap instance and store it
        self.heatmaps[name] = Heatmap(embeddings, scores)
        print(f"Created heatmap {name}")

        # Rescale embeddings and compute discrete space
        rescaled_embeddings = self.rescale_embedding(self.heatmaps[name].raw_embeddings)
        self.heatmaps[name].rescaled_embeddings = rescaled_embeddings
        (
            self.heatmaps[name].discrete_embedding,
            self.heatmaps[name].discrete_coord,
            _,
        ) = compute_discrete_space(rescaled_embeddings, self.cells_per_dimension)
        print(f"Created heatmap rescaled and discrete space {name}")
        print(f"Type of self.heatmaps[name]: {type(self.heatmaps[name])}")
        print(f"Discrete space type: {type(self.heatmaps[name].discrete_embedding)}")
        self.heatmaps[name].compute_smoothed_nplusone_dim_discrete_space(
            smoothing_fwhm=smoothing_fwhm, smoothing_sigma=smoothing_sigma
        )

    def delete_heatmap(self, name):
        if name in self.heatmaps:
            del self.heatmaps[name]
        else:
            print(f"delete_heatmap: No heatmap with the name {name} exists")

    def __getstate__(self):
        state = self.__dict__.copy()
        if "trained_umap" in state and not isinstance(
            state["trained_umap"], (str, os.PathLike)
        ):
            state["trained_umap"] = (
                None  # Exclude the UMAP model from being saved if it's not a path
            )
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        if "trained_umap" not in state or state["trained_umap"] is None:
            self.trained_umap = None  # Allow for manual setting later

    def save(self, filename):
        """
        Save the entire DiscreteLatentSpace object to a file using joblib.
        """
        dump(self, filename)

    @staticmethod
    def load(filename):
        """
        Load a DiscreteLatentSpace object from a file.
        """
        return load(filename)

    """
    Plotting methods (might not be necessary later)
    """

    def plot_raw_embedding(self):
        plot_embeddings(self.raw_embeddings, "Raw Embeddings")

    def plot_rescaled_embedding(self):
        plot_embeddings(
            self.rescaled_embeddings, "Rescaled Embeddings", rescaled_mode=True
        )

    def plot_inverse_rescaled_embedding(self):
        inverse_rescaled_embedding = self.inverse_rescale_embedding(
            self.rescaled_embeddings
        )
        plot_embeddings(inverse_rescaled_embedding, "Inverse Rescaled Embeddings")

    def plot_discrete_embedding(
        self, overlap_percentage=None, cells_per_dimension=None, heatmap_name=None
    ):
        # Check if the heatmap_name exists in the heatmaps dictionary
        if heatmap_name is not None and heatmap_name not in self.heatmaps:
            raise ValueError(f"No heatmap with the name {heatmap_name} exists")
        if self.discrete_space is None:
            if overlap_percentage is None:
                self.create_discrete_space(
                    self.rescaled_embeddings, cells_per_dimension
                )
            else:
                self.create_discrete_space(self.rescaled_embeddings, overlap_percentage)
        discrete_embedding = self.discrete_space

        if discrete_embedding.ndim == 2:
            plt.figure(figsize=(10, 10))
            plt.imshow(
                discrete_embedding.T, origin="lower", cmap="gray_r", aspect="auto"
            )
            plt.axis("scaled")
            if heatmap_name is not None:
                heatmap_discrete_coords = self.heatmaps[heatmap_name].discrete_coord
                plt.scatter(
                    heatmap_discrete_coords[:, 0],
                    heatmap_discrete_coords[:, 1],
                    color="r",
                    s=50,
                )

        elif discrete_embedding.ndim == 3:
            fig = plt.figure(figsize=(10, 10))
            ax = fig.add_subplot(111, projection="3d")
            ax.scatter(
                discrete_embedding[:, 0],
                discrete_embedding[:, 1],
                discrete_embedding[:, 2],
            )
            if heatmap_name is not None:
                heatmap_discrete_coords = self.heatmaps[heatmap_name].discrete_coord
                ax.scatter(
                    heatmap_discrete_coords[:, 0],
                    heatmap_discrete_coords[:, 1],
                    heatmap_discrete_coords[:, 2],
                    color="r",
                    s=2,
                )
            ax.set_box_aspect(
                [1, 1, 1]
            )  # Set the aspect ratio of the 3D plot to be equal
        else:
            raise ValueError(
                f"Plotting this number of dimensions {discrete_embedding.ndim} of the embedding is not supported"
            )
        plt.show()
        plt.close()

    def plot_heatmap(self, heatmap_name, smoothing_fwhm=10, output_folder=None):
        if heatmap_name not in self.heatmaps:
            raise ValueError(f"No heatmap with the name {heatmap_name} exists")
        heatmap = self.heatmaps[heatmap_name]
        if heatmap.heatmap is None:
            if heatmap.smoothed_nplusone_dim_discrete_space is None:
                heatmap.compute_smoothed_nplusone_dim_discrete_space(
                    smoothing_fwhm=smoothing_fwhm
                )
            print(
                f"Max value in the smoothed_nplusone_dim_discrete_space: "
                f"{np.max(heatmap.smoothed_nplusone_dim_discrete_space)}"
            )
            heatmap.generate_heatmap("mean")

        plt.figure(figsize=(10, 10))
        plt.imshow(heatmap.heatmap.T, origin="lower", cmap="viridis", aspect="auto")
        plt.colorbar()
        plt.axis("scaled")
        if output_folder is not None:
            plt.savefig(Path(output_folder, f"{heatmap_name}_heatmap.png"))
        plt.show()
        plt.close()


class Heatmap:
    def __init__(self, matched_embeddings, scores):
        """
        The Heatmap class is used to store the data necessary to create the heatmap in the
        discrete space and the heatmap itself.
        IMPORTANT NOTE: The matched_embeddings must be in the same order and size as the scores.
        Parameters
        ----------
        matched_embeddings: np.ndarray
            Coordinates in the raw embedding space of the matched points (same order as the scores)
        scores: np.ndarray
            Scores of the matched points (same order as the matched_embeddings)
        """
        print(f"Shape of matched embeddings: {matched_embeddings.shape}")
        # Check for NaNs or Infs in the scores
        if np.isnan(scores).any() or np.isinf(scores).any():
            print(
                "Warning: NaNs or Infs found in scores. Removing corresponding scores and matched_embeddings."
            )

            # Get indices where scores are not NaN or Inf
            valid_indices = np.where(~np.isnan(scores) & ~np.isinf(scores))

            # Only keep valid scores and matched_embeddings
            scores = scores[valid_indices]
            matched_embeddings = matched_embeddings[valid_indices]
        print(
            f"Shape of matched embeddings after removing NaNs and Infs: {matched_embeddings.shape}"
        )
        self._raw_embeddings = matched_embeddings
        self._scores = scores
        self.rescaled_embeddings = None
        self.discrete_coord = None
        self.discrete_embedding = None
        self.sigma = None
        self._smoothed_nplusone_dim_discrete_space = None
        self._heatmap = None

    @property
    def raw_embeddings(self):
        return self._raw_embeddings

    @property
    def scores(self):
        return self._scores

    @property
    def rescaled_embeddings(self):
        return self._rescaled_embeddings

    @rescaled_embeddings.setter
    def rescaled_embeddings(self, rescaled_embeddings):
        if (
            rescaled_embeddings is not None
            and rescaled_embeddings.shape != self._raw_embeddings.shape
        ):
            raise ValueError(
                "The rescaled embeddings must have the same shape as the raw embeddings: "
                f" {self._raw_embeddings.shape} vs {rescaled_embeddings.shape}"
            )
        self._rescaled_embeddings = rescaled_embeddings

    @property
    def discrete_coord(self):
        return self._discrete_coord

    @discrete_coord.setter
    def discrete_coord(self, discrete_coord):
        self._discrete_coord = discrete_coord

    @property
    def discrete_embedding(self):
        return self._discrete_embedding

    @discrete_embedding.setter
    def discrete_embedding(self, discrete_embedding):
        print(
            f"Setting discrete embedding with shape "
            f"{discrete_embedding.shape if discrete_embedding is not None else None}"
        )
        self._discrete_embedding = discrete_embedding

    @property
    def sigma(self):
        return self._sigma

    @sigma.setter
    def sigma(self, sigma):
        self._sigma = sigma

    @property
    def smoothed_nplusone_dim_discrete_space(self):
        return self._smoothed_nplusone_dim_discrete_space

    def compute_smoothed_nplusone_dim_discrete_space(
        self,
        smoothing_sigma=None,
        smoothing_fwhm=None,
        mode="reflect",
        rescale_values=True,
    ):
        if self.discrete_embedding is None:
            raise ValueError(
                "The discrete embedding must be computed before the smoothed n+1 dim discrete space"
            )
        if smoothing_sigma is not None and smoothing_fwhm is not None:
            raise ValueError("Only one of the smoothing parameters can be provided")
        if smoothing_sigma is None and smoothing_fwhm is None:
            raise ValueError("A smoothing parameter must be provided")
        self.sigma = (
            smoothing_sigma
            if smoothing_sigma is not None
            else smoothing_fwhm / (2 * np.sqrt(2 * np.log(2)))
        )
        print(f"Smoothing the discrete space with a sigma of {self.sigma}")

        # Create an array of zeros with an extra dimension for the number of coordinates
        smoothed_space = np.zeros(
            (len(self.discrete_coord),) + self.discrete_embedding.shape
        )
        print(f"Shape of the smoothed space: {smoothed_space.shape}")

        # Set the corresponding indices in the smoothed_space to 1
        for i, coord in enumerate(self.discrete_coord):
            smoothed_space[(i,) + tuple(coord)] = 1

        sigma_tuple = (0,) + (self.sigma,) * (smoothed_space.ndim - 1)

        print(f"Sigma tuple: {sigma_tuple}")

        # Smooth the smoothed_space along all axes except the first one
        smoothed_space_nplusone = gaussian_filter(
            smoothed_space, sigma=sigma_tuple, mode=mode
        )

        if rescale_values:
            # rescale between 0 and 1
            self._smoothed_nplusone_dim_discrete_space = (
                smoothed_space_nplusone - np.min(smoothed_space_nplusone)
            ) / (np.max(smoothed_space_nplusone) - np.min(smoothed_space_nplusone))
        else:
            self._smoothed_nplusone_dim_discrete_space = smoothed_space_nplusone
        # self._smoothed_nplusone_dim_discrete_space = smoothed_space
        print(
            f"Shape of the smoothed n+1 dim discrete space: {self._smoothed_nplusone_dim_discrete_space.shape}"
        )

    @property
    def heatmap(self):
        return self._heatmap

    def generate_heatmap(self, function):
        if self._smoothed_nplusone_dim_discrete_space is None:
            raise ValueError(
                "The smoothed n+1 dim discrete space must be computed before the heatmap"
            )
        function_mapping = {
            "mean": np.mean,
            "median": np.median,
            "max": np.max,
            "std": np.std,
            "sum": np.sum,
        }
        if function not in function_mapping:
            raise ValueError(
                f"Invalid function. Expected one of: {list(function_mapping.keys())}"
            )
        self._heatmap = function_mapping[function](
            self._smoothed_nplusone_dim_discrete_space, axis=0
        )

    def get_embeddings_scores(self):
        """
        Returns a structured numpy array with the rescaled embeddings
        and their associated scores.
        """
        if self._rescaled_embeddings is None or self._scores is None:
            raise ValueError(
                "The rescaled embeddings and scores must be computed before they can be retrieved."
            )

        # Create a structured numpy array
        structured_array = np.zeros(
            len(self._rescaled_embeddings),
            dtype=[
                ("rescaled_embeddings", float, self._rescaled_embeddings.shape[1]),
                ("scores", float),
            ],
        )

        # Fill the structured array with the rescaled embeddings and scores
        structured_array["rescaled_embeddings"] = self._rescaled_embeddings
        structured_array["scores"] = self._scores

        return structured_array
