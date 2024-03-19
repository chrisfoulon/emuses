import numpy as np
from matplotlib import pyplot as plt
import matplotlib.colors as colors


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
        rescaled_embedding = rescaled_embedding * (1 - 2 * margin_rescaled) + margin_rescaled

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

def inverse_rescale_embedding(rescaled_embedding, margin=0, max_value=None, min_value=None):
    if margin != 0:
        # Reverse the margin scaling
        margin_rescaled = margin / 100
        rescaled_embedding = (rescaled_embedding - margin_rescaled) / (1 - 2 * margin_rescaled)

    # Perform the inverse of the rescaling operation
    embedding = rescaled_embedding * (max_value - min_value) + min_value

    return embedding


def project_embeddings(rescaled_embeddings, cells_per_dimension):
    # Convert the rescaled embedding coordinates to indices in the pixelated space
    indices = np.round(rescaled_embeddings * (cells_per_dimension - 1)).astype(int)

    # Create an array of zeros with the shape of the grid
    pixelated_space = np.zeros(cells_per_dimension, dtype=int)

    # Set the corresponding indices in the pixelated space to 1
    pixelated_space[tuple(indices.T)] = 1

    return pixelated_space


def compute_pixelated_space(rescaled_embedding, cells_per_dimension):
    rescaled_maximum_coords = np.max(rescaled_embedding, axis=0)

    # Create a grid of points in the N-dimensional space
    grid_points = [np.linspace(0, max_coord, num_cells) for max_coord, num_cells in
                   zip(rescaled_maximum_coords, cells_per_dimension)]

    # Create a grid of points in the N-dimensional space
    grid = np.meshgrid(*grid_points, indexing='ij')

    # Convert the grid to an array of points
    points = np.vstack(list(map(np.ravel, grid))).T

    # Create an array of zeros with the shape of the grid
    pixelated_space = np.zeros(cells_per_dimension, dtype=int)

    # Convert the rescaled embedding coordinates to indices in the pixelated space
    indices = np.round(rescaled_embedding * (np.array(cells_per_dimension) - 1)).astype(int)

    # compute the percentage of overlap (number of pixels that contain multiple points compared
    # with the total number of points). Just check the number of unique indices
    overlap = 1 - np.unique(indices, axis=0).shape[0] / rescaled_embedding.shape[0]
    overlap *= 100

    # Set the corresponding indices in the pixelated space to 1
    pixelated_space[tuple(indices.T)] = 1

    return pixelated_space, points, overlap


def optimize_pixel_space(rescaled_embedding, overlap_percentage):
    if overlap_percentage < 0 or overlap_percentage > 100:
        raise ValueError("Overlap percentage must be between 0 and 100[exclusive]")
    rescaled_maximum_coords = np.max(rescaled_embedding, axis=0)
    aspect_ratio = rescaled_maximum_coords / np.max(rescaled_maximum_coords)
    cells_per_dimension = np.array(aspect_ratio).astype(int)
    overlap = 100
    pixelated_space = None
    points = None
    prev_pixelated_space = None
    prev_points = None
    prev_overlap = None
    prev_cells_per_dimension = None
    factor_ratio = 2
    while overlap >= overlap_percentage:
        prev_pixelated_space = pixelated_space
        prev_points = points
        prev_overlap = overlap
        prev_cells_per_dimension = cells_per_dimension
        factor_ratio *= 2
        cells_per_dimension = np.array([dim * factor_ratio for dim in aspect_ratio]).astype(int)
        # print(f'\rTrying {cells_per_dimension} cells per dimension', end='')
        # print(f'Trying {cells_per_dimension} cells per dimension')
        pixelated_space, points, overlap = compute_pixelated_space(
            rescaled_embedding, cells_per_dimension=cells_per_dimension)
    lower_bound = prev_cells_per_dimension
    upper_bound = cells_per_dimension
    while np.any(upper_bound - lower_bound > 1):
        mid_point = (upper_bound + lower_bound) // 2
        pixelated_space, points, overlap = compute_pixelated_space(
            rescaled_embedding, cells_per_dimension=mid_point)
        if overlap > overlap_percentage:
            lower_bound = mid_point
        else:
            upper_bound = mid_point
            prev_pixelated_space = pixelated_space
            prev_points = points
            prev_overlap = overlap
            prev_cells_per_dimension = mid_point
    return prev_pixelated_space, prev_points, prev_overlap, prev_cells_per_dimension


def plot_embeddings(embeddings, title, rescaled_mode=False):
    if rescaled_mode:
        if np.any(embeddings < 0) or np.any(embeddings > 1):
            print("Some values are outside the [0, 1] interval and will not be displayed on the plot.")

    if embeddings.shape[1] == 2:
        plt.scatter(embeddings[:, 0], embeddings[:, 1], s=2)
        plt.axis('equal')  # Set the aspect ratio of the plot to be equal
        if rescaled_mode:
            plt.xlim(0, 1)
            plt.ylim(0, 1)
    elif embeddings.shape[1] == 3:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.scatter(embeddings[:, 0], embeddings[:, 1], embeddings[:, 2], s=2)
        ax.set_box_aspect([1, 1, 1])  # Set the aspect ratio of the 3D plot to be equal
        if rescaled_mode:
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.set_zlim(0, 1)
    else:
        raise ValueError(f'Plotting this number of dimensions {embeddings.shape[1]} of the embedding is not supported')
    plt.title(title)
    plt.show()
    plt.close()


class DiscreteLatentSpace:
    def __init__(self, trained_umap, raw_embeddings, margin=0):
        self.overlap = None
        self.pixelated_coords = None
        self.pixelated_embedding = None
        self.margin = margin
        self.trained_umap = trained_umap
        self.raw_embeddings = raw_embeddings
        self.max_coordinates = self.raw_embeddings.max()
        self.min_coordinates = self.raw_embeddings.min()
        self.rescaled_embeddings = self.rescale_embedding(raw_embeddings)
        self.cells_per_dimension = None
        self.heatmaps = {}

    """
    Embedding spaces transformatins
    """
    def rescale_embedding(self, embedding):
        return rescale_embedding(embedding, self.margin, self.max_coordinates, self.min_coordinates)

    def inverse_rescale_embedding(self, rescaled_embedding):
        return inverse_rescale_embedding(rescaled_embedding, self.margin, self.max_coordinates,
                                         self.min_coordinates)

    def create_pixelated_space(self, rescaled_embedding, overlap_percentage=None, cells_per_dimension=None):
        if cells_per_dimension is not None:
            self.pixelated_embedding, self.pixelated_coords, self.overlap = compute_pixelated_space(
                rescaled_embedding, cells_per_dimension)
            self.cells_per_dimension = cells_per_dimension
        else:
            self.pixelated_embedding, self.pixelated_coords, self.overlap, self.cells_per_dimension = (
                optimize_pixel_space(rescaled_embedding, overlap_percentage))
        print(f"There is an overlap of {self.overlap:.2f}% points in the pixelated space")
        print(f"The number of cells in the pixelated space is {np.prod(self.pixelated_embedding.shape)}")
        print(f'The shape of the pixelated space is {self.pixelated_embedding.shape}')
        print(f'Maximum in each dimension: {self.max_coordinates}')

    def pixelate_new_embedding(self, new_rescaled_embedding):
        pixelated_new_embedding, _, _ = compute_pixelated_space(
            new_rescaled_embedding, self.cells_per_dimension)
        return pixelated_new_embedding


    """
    Heatmap methods
    """
    def create_heatmap_spaces(self, embeddings, scores, name):
        embeddings = np.array(embeddings)
        scores = np.array(scores)

        if name in self.heatmaps:
            raise ValueError(f"A heatmap with the name {name} already exists")
        if embeddings.shape[0] == len(scores):
            self.heatmaps[name] = Heatmap(embeddings, scores)
        else:
            # make sure scores contains the indices of the embeddings and then filter the embeddings
            if all(isinstance(score, int) and 0 <= score < embeddings.shape[0] for score in scores):
                filtered_embeddings = embeddings[scores]
                self.heatmaps[name] = Heatmap(filtered_embeddings, scores)
            else:
                raise ValueError("The embeddings and the scores do not have the same length and the scores."
                                 " To create a heatmap with these embeddings, the scores must contain the "
                                 "indices of the embedding coordinates associated with the scores")
        # now we need to rescale the embeddings and create the pixelated space
        self.heatmaps[name].rescaled_embeddings = self.rescale_embedding(self.heatmaps[name].raw_embeddings)
        self.heatmaps[name].pixelated_coord = self.pixelate_new_embedding(self.heatmaps[name].rescaled_embeddings)

    """
    Plotting methods (might not be necessary later)
    """
    def plot_raw_embedding(self):
        plot_embeddings(self.raw_embeddings, 'Raw Embeddings')

    def plot_rescaled_embedding(self):
        plot_embeddings(self.rescaled_embeddings, 'Rescaled Embeddings', rescaled_mode=True)

    def plot_inverse_rescaled_embedding(self):
        inverse_rescaled_embedding = self.inverse_rescale_embedding(self.rescaled_embeddings)
        plot_embeddings(inverse_rescaled_embedding, 'Inverse Rescaled Embeddings')

    def plot_pixelated_embedding(self, cells_number=None, overlap_percentage=None):
        self.create_pixelated_space(self.rescaled_embeddings, cells_number, overlap_percentage)
        pixelated_embedding = self.pixelated_embedding
        if pixelated_embedding.ndim == 2:
            plt.figure(figsize=(10, 10))
            plt.imshow(pixelated_embedding.T, origin='lower', cmap='gray_r', aspect='auto')
        elif pixelated_embedding.ndim == 3:
            fig = plt.figure(figsize=(10, 10))
            ax = fig.add_subplot(111, projection='3d')
            ax.scatter(pixelated_embedding[:, 0], pixelated_embedding[:, 1], pixelated_embedding[:, 2])
            ax.set_box_aspect([1, 1, 1])  # Set the aspect ratio of the 3D plot to be equal
        else:
            raise ValueError(f'Plotting this number of dimensions {pixelated_embedding.ndim} of'
                             f' the embedding is not supported')
        plt.show()
        plt.close()


class Heatmap:
    def __init__(self, matched_embeddings, scores):
        """
        The Heatmap class is used to store the data necessary to create the heatmap in the
        pixelated space and the heatmap itself.
        Parameters
        ----------
        matched_embeddings: np.ndarray
            Coordinates in the raw embedding space of the matched points (same order as the scores)
        scores: np.ndarray
        """
        self._raw_embeddings = matched_embeddings
        self._scores = scores
        self._rescaled_embeddings = None
        self._pixelated_coord = None
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
            if rescaled_embeddings.shape != self._raw_embeddings.shape:
                raise ValueError("The rescaled embeddings must have the same shape as the raw embeddings")
            self._rescaled_embeddings = rescaled_embeddings

        @property
        def pixelated_coord(self):
            return self._pixelated_coord

        @pixelated_coord.setter
        def pixelated_coord(self, pixelated_coord):
            self._pixelated_coord = pixelated_coord
