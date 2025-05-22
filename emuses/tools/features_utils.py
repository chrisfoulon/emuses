# emuses/tools/features_utils.py
import numpy as np
from scipy.spatial.distance import cdist
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import FunctionTransformer


class RawCoords(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X


class GWD(BaseEstimator, TransformerMixin):
    """
    Gaussian-Weighted-Distance matrix or summary stats.
    Parameters
    ----------
    sigma : float      - bandwidth
    aggregate : str    - 'none' | 'mean' | 'sum'
    """

    def __init__(self, sigma=0.05, aggregate="none"):
        self.sigma = sigma
        self.aggregate = aggregate

    def fit(self, X, y=None):
        self.X_fit_ = np.asarray(X)
        return self

    def transform(self, X):
        d2 = cdist(np.asarray(X), self.X_fit_, metric="sqeuclidean")
        K = np.exp(-0.5 * d2 / (self.sigma**2))
        if self.aggregate == "none":
            return K  # shape (n_samples , n_train)
        stat = K.mean(axis=1) if self.aggregate == "mean" else K.sum(axis=1)
        return stat.reshape(-1, 1)
