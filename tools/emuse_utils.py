import numpy as np
from matplotlib import pyplot as plt
import matplotlib.colors as colors


def rescale_embedding(embedding, margin=0, max_coordinates=None, min_coordinates=None):
    if max_coordinates is None:
        max_coordinates = np.max(embedding, axis=0)
    if min_coordinates is None:
        min_coordinates = np.min(embedding, axis=0)

    # Rescale the embedding between 0 and 1
    rescaled_embedding = (embedding - min_coordinates) / (max_coordinates - min_coordinates)

    if margin != 0:
        # Compute the margin in the rescaled space
        margin_rescaled = margin / 100

        # Subtract the margin from the maximum coordinates and add the margin to the minimum coordinates
        rescaled_embedding = rescaled_embedding * (1 - 2 * margin_rescaled) + margin_rescaled

    return rescaled_embedding


def inverse_rescale_embedding(rescaled_embedding, margin=0, max_coordinates=None, min_coordinates=None):
    if margin != 0:
        # Reverse the margin scaling
        margin_rescaled = margin / 100
        rescaled_embedding = (rescaled_embedding - margin_rescaled) / (1 - 2 * margin_rescaled)

    # Perform the inverse of the rescaling operation
    embedding = rescaled_embedding * (max_coordinates - min_coordinates) + min_coordinates

    return embedding


def pixelate_embedding(rescaled_embedding, cells_number=None, overlap_percentage=None):
    if overlap_percentage is not None and cells_number is None:
        cells_number = 1
        prev_cells_number = cells_number
        print(f'\rNumber of cells: {prev_cells_number}', end='')
        while True:
            print(f'\rNumber of cells: {prev_cells_number}', end='')
            pixelated_space, points, overlap = pixelate_embedding(rescaled_embedding, cells_number=cells_number)
            if overlap <= overlap_percentage:
                cells_number_temp = cells_number
                prev_pixelated_space, prev_points, prev_overlap = pixelated_space, points, overlap
                while overlap <= overlap_percentage:
                    print(f'\rNumber of cells: {prev_cells_number}', end='')
                    cells_number_temp -= (cells_number_temp - prev_cells_number) / 2
                    prev_pixelated_space, prev_points, prev_overlap = pixelated_space, points, overlap
                    pixelated_space, points, overlap = pixelate_embedding(rescaled_embedding,
                                                                          cells_number=cells_number_temp)
                print()
                print(f'Final number of cells: {prev_cells_number}')
                return prev_pixelated_space, prev_points, prev_overlap
            prev_cells_number = cells_number
            cells_number *= 2
    else:
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

        return pixelated_space, points, overlap


def plot_embeddings(embeddings, title):
    if embeddings.shape[1] == 2:
        plt.scatter(embeddings[:, 0], embeddings[:, 1])
    elif embeddings.shape[1] == 3:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.scatter(embeddings[:, 0], embeddings[:, 1], embeddings[:, 2])
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
        self.rescaled_embeddings = self._rescale_embedding(raw_embeddings)

    def get_maximums(self):
        return self.raw_embeddings.max(axis=0)

    def get_minimums(self):
        return self.raw_embeddings.min(axis=0)

    def _rescale_embedding(self, embedding):
        return rescale_embedding(embedding, self.margin, self.max_coordinates, self.min_coordinates)

    def inverse_rescale_embedding(self, rescaled_embedding):
        return inverse_rescale_embedding(rescaled_embedding, self.margin, self.max_coordinates,
                                         self.min_coordinates)

    def pixelate_embedding(self, rescaled_embedding, cells_number=None, overlap_percentage=None):
        self.pixelated_embedding, self.pixelated_coords, self.overlap = (
            pixelate_embedding(rescaled_embedding, cells_number, overlap_percentage))
        print(f"The is an overlap of {self.overlap:.2f}% points in the pixelated space")

    def plot_raw_embedding(self):
        plot_embeddings(self.raw_embeddings, 'Raw Embeddings')

    def plot_rescaled_embedding(self):
        plot_embeddings(self.rescaled_embeddings, 'Rescaled Embeddings')

    def plot_inverse_rescaled_embedding(self):
        inverse_rescaled_embedding = self.inverse_rescale_embedding(self.rescaled_embeddings)
        plot_embeddings(inverse_rescaled_embedding, 'Inverse Rescaled Embeddings')

    def plot_pixelated_embedding(self, cells_number=None, overlap_percentage=None):
        self.pixelate_embedding(self.rescaled_embeddings, cells_number, overlap_percentage)
        pixelated_embedding = self.pixelated_embedding
        if pixelated_embedding.ndim == 2:
            plt.figure(figsize=(10, 10))
            plt.imshow(pixelated_embedding.T, origin='lower', cmap='gray_r')
        elif pixelated_embedding.ndim == 3:
            fig = plt.figure(figsize=(10, 10))
            ax = fig.add_subplot(111, projection='3d')
            ax.scatter(pixelated_embedding[:, 0], pixelated_embedding[:, 1], pixelated_embedding[:, 2])
        else:
            raise ValueError(f'Plotting this number of dimensions {pixelated_embedding.ndim} of'
                             f' the embedding is not supported')
        plt.show()
        plt.close()
