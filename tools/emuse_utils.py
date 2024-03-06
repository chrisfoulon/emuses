import numpy as np


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


class DiscreteLatentSpace:
    def __init__(self, trained_umap, raw_embeddings, margin=0):
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
