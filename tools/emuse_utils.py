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


# def pixelate_embedding(rescaled_embedding, cells_number=None, overlap_percentage=None):
#     if overlap_percentage is not None and cells_number is None:
#         cells_number = 1
#         prev_cells_number = cells_number
#         print(f'\rNumber of cells: {prev_cells_number}', end='')
#         while True:
#             print(f'\rNumber of cells: {prev_cells_number}', end='')
#             pixelated_space, points, overlap, cells_per_dimension, rescaled_maximum_coords = pixelate_embedding(
#                 rescaled_embedding, cells_number=cells_number)
#             prev_pixelated_space = pixelated_space
#             prev_points = points
#             prev_overlap = overlap
#             prev_cells_per_dimension = cells_per_dimension
#             prev_rescaled_maximum_coords = rescaled_maximum_coords
#             if overlap <= overlap_percentage:
#                 cells_number_temp = cells_number
#                 while overlap <= overlap_percentage:
#                     print(f'\rNumber of cells: {cells_number_temp}', end='')
#                     cells_number_temp -= (cells_number_temp - prev_cells_number) / 2
#                     prev_pixelated_space = pixelated_space
#                     prev_points = points
#                     prev_overlap = overlap
#                     prev_cells_per_dimension = cells_per_dimension
#                     prev_rescaled_maximum_coords = rescaled_maximum_coords
#                     pixelated_space, points, overlap, cells_per_dimension, rescaled_maximum_coords = (
#                         pixelate_embedding(rescaled_embedding, cells_number=cells_number_temp))
#                 print()
#                 print(f'Final number of cells: {prev_cells_number}')
#                 return prev_pixelated_space, prev_points, prev_overlap, prev_cells_per_dimension, prev_rescaled_maximum_coords
#             prev_cells_number = cells_number
#             cells_number *= 2
#     else:
#         rescaled_maximum_coords = np.max(rescaled_embedding, axis=0)
#         dimensions = len(rescaled_maximum_coords)
#
#         # Calculate the aspect ratio
#         aspect_ratio = rescaled_maximum_coords / np.max(rescaled_maximum_coords)
#
#         # Compute the number of cells in each dimension while maintaining the aspect ratio
#         cells_per_dimension = np.round((cells_number ** (1 / dimensions)) * aspect_ratio).astype(int)
#
#         # Create a grid of points in the N-dimensional space
#         grid_points = [np.linspace(0, max_coord, num_cells) for max_coord, num_cells in
#                        zip(rescaled_maximum_coords, cells_per_dimension)]
#
#         # Create a grid of points in the N-dimensional space
#         grid = np.meshgrid(*grid_points, indexing='ij')
#
#         # Convert the grid to an array of points
#         points = np.vstack(list(map(np.ravel, grid))).T
#
#         # Create an array of zeros with the shape of the grid
#         pixelated_space = np.zeros(cells_per_dimension, dtype=int)
#
#         # Convert the rescaled embedding coordinates to indices in the pixelated space
#         indices = np.round(rescaled_embedding * (cells_per_dimension - 1)).astype(int)
#
#         # compute the percentage of overlap (number of pixels that contain multiple points compared
#         # with the total number of points). Just check the number of unique indices
#         overlap = 1 - np.unique(indices, axis=0).shape[0] / rescaled_embedding.shape[0]
#         overlap *= 100
#
#         # Set the corresponding indices in the pixelated space to 1
#         pixelated_space[tuple(indices.T)] = 1
#
#         return pixelated_space, points, overlap, cells_per_dimension, rescaled_maximum_coords


def compute_pixelated_space(rescaled_embedding, cells_number):
    # TODO When used without the optimisation function, it doesn't give the best results
    rescaled_maximum_coords = np.max(rescaled_embedding, axis=0)
    dimensions = len(rescaled_maximum_coords)

    # Calculate the aspect ratio
    aspect_ratio = rescaled_maximum_coords / np.max(rescaled_maximum_coords)

    # Compute the number of cells in each dimension while maintaining the aspect ratio
    cells_per_dimension = np.round((cells_number ** (1 / dimensions)) * aspect_ratio).astype(int)

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
    indices = np.round(rescaled_embedding * (cells_per_dimension - 1)).astype(int)

    # compute the percentage of overlap (number of pixels that contain multiple points compared
    # with the total number of points). Just check the number of unique indices
    overlap = 1 - np.unique(indices, axis=0).shape[0] / rescaled_embedding.shape[0]
    overlap *= 100

    # Set the corresponding indices in the pixelated space to 1
    pixelated_space[tuple(indices.T)] = 1

    return pixelated_space, points, overlap, cells_per_dimension, rescaled_maximum_coords


# def optimize_pixel_space(rescaled_embedding, overlap_percentage):
#     cells_number = len(rescaled_embedding[0])
#     prev_cells_number = cells_number
#     print(f'\rNumber of cells: {prev_cells_number}', end='')
#     while True:
#         print(f'\rNumber of cells: {prev_cells_number}', end='')
#         pixelated_space, points, overlap, cells_per_dimension, rescaled_maximum_coords = compute_pixelated_space(
#             rescaled_embedding, cells_number=cells_number)
#         prev_pixelated_space = pixelated_space
#         prev_points = points
#         prev_overlap = overlap
#         prev_cells_per_dimension = cells_per_dimension
#         prev_rescaled_maximum_coords = rescaled_maximum_coords
#         if overlap <= overlap_percentage:
#             cells_number_temp = cells_number
#             while overlap <= overlap_percentage:
#                 print(f'\rNumber of cells: {cells_number_temp}', end='')
#                 cells_number_temp -= (cells_number_temp - prev_cells_number) / 2
#                 prev_pixelated_space = pixelated_space
#                 prev_points = points
#                 prev_overlap = overlap
#                 prev_cells_per_dimension = cells_per_dimension
#                 prev_rescaled_maximum_coords = rescaled_maximum_coords
#                 pixelated_space, points, overlap, cells_per_dimension, rescaled_maximum_coords = (
#                     compute_pixelated_space(rescaled_embedding, cells_number=cells_number_temp))
#             print()
#             print(f'Final number of cells: {cells_number_temp}')
#             return prev_pixelated_space, prev_points, prev_overlap, prev_cells_per_dimension, prev_rescaled_maximum_coords
#         prev_cells_number = cells_number
#         cells_number *= 2


def optimize_pixel_space(rescaled_embedding, overlap_percentage):
    if overlap_percentage < 0 or overlap_percentage > 100:
        raise ValueError("Overlap percentage must be between 0 and 100[exclusive]")
    cells_number = len(rescaled_embedding[0])
    overlap = 100
    cells_number_temp = 0
    pixelated_space, points, cells_per_dimension, rescaled_maximum_coords = None, None, None, None
    while overlap > overlap_percentage:
        cells_number_temp = cells_number
        cells_number *= 2
        pixelated_space, points, overlap, cells_per_dimension, rescaled_maximum_coords = compute_pixelated_space(
            rescaled_embedding, cells_number=cells_number)
    # here overlap <= overlap_percentage, now we need to find the optimal number of cells
    # using a binary search until the step is smaller than 1 so we return the last pixelated space
    # that has an overlap smaller than the desired overlap_percentage
    interval = cells_number - cells_number_temp
    prev_pixelated_space = None
    prev_points = None
    prev_overlap = None
    prev_cells_per_dimension = None
    prev_rescaled_maximum_coords = None
    while interval > 1:
        prev_pixelated_space = pixelated_space
        prev_points = points
        prev_overlap = overlap
        prev_cells_per_dimension = cells_per_dimension
        prev_rescaled_maximum_coords = rescaled_maximum_coords
        interval //= 2
        print(f'\rOverlap > percentage before: {overlap > overlap_percentage} | ', end='')
        if overlap > overlap_percentage:
            cells_number += interval
        else:
            cells_number -= interval
        pixelated_space, points, overlap, cells_per_dimension, rescaled_maximum_coords = compute_pixelated_space(
            rescaled_embedding, cells_number=cells_number)
        # print(f'\rOverlap > percentage after: {overlap > overlap_percentage}', end='')
    if overlap > overlap_percentage:
        return prev_pixelated_space, prev_points, prev_overlap, prev_cells_per_dimension, prev_rescaled_maximum_coords
    else:
        return pixelated_space, points, overlap, cells_per_dimension, rescaled_maximum_coords


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
        self.max_coordinates = self.get_maximums()
        self.min_coordinates = self.get_minimums()
        self.rescaled_embeddings = self.rescale_embedding(raw_embeddings)

    def get_maximums(self):
        return self.raw_embeddings.max()

    def get_minimums(self):
        return self.raw_embeddings.min()

    def rescale_embedding(self, embedding):
        return rescale_embedding(embedding, self.margin, self.max_coordinates, self.min_coordinates)

    def inverse_rescale_embedding(self, rescaled_embedding):
        return inverse_rescale_embedding(rescaled_embedding, self.margin, self.max_coordinates,
                                         self.min_coordinates)

    def pixelate_embedding(self, rescaled_embedding, cells_number=None, overlap_percentage=None):
        if overlap_percentage is None:
            self.pixelated_embedding, self.pixelated_coords, self.overlap, _, _ = (
                compute_pixelated_space(rescaled_embedding, cells_number))
        else:
            self.pixelated_embedding, self.pixelated_coords, self.overlap, _, _ = (
                optimize_pixel_space(rescaled_embedding, overlap_percentage))
        print(f"The is an overlap of {self.overlap:.2f}% points in the pixelated space")
        print(f"The number of cells in the pixelated space is {np.prod(self.pixelated_embedding.shape)}")
        print(f'The shape of the pixelated space is {self.pixelated_embedding.shape}')
        print(f'Maximum in each dimension: {self.max_coordinates}')

    def plot_raw_embedding(self):
        plot_embeddings(self.raw_embeddings, 'Raw Embeddings')

    def plot_rescaled_embedding(self):
        plot_embeddings(self.rescaled_embeddings, 'Rescaled Embeddings', rescaled_mode=True)

    def plot_inverse_rescaled_embedding(self):
        inverse_rescaled_embedding = self.inverse_rescale_embedding(self.rescaled_embeddings)
        plot_embeddings(inverse_rescaled_embedding, 'Inverse Rescaled Embeddings')

    def plot_pixelated_embedding(self, cells_number=None, overlap_percentage=None):
        self.pixelate_embedding(self.rescaled_embeddings, cells_number, overlap_percentage)
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
