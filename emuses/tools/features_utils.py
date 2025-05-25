# emuses/tools/features_utils.py
import numpy as np
from scipy.spatial.distance import cdist
from sklearn.base import BaseEstimator, TransformerMixin

# emuses/tools/features_utils.py
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.decomposition import PCA, KernelPCA


class RawCoords(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X


# ───────────────────────────────────────────────────────────────
class GWD(BaseEstimator, TransformerMixin):
    """Gaussian-weighted distances to all data-or grid points."""

    def __init__(self, sigma=0.1, agg="none"):  # agg: none|mean|sum
        self.sigma, self.agg = sigma, agg

    def fit(self, X, y=None):
        self.fit_X_ = X.copy()
        return self

    def transform(self, X):
        d2 = ((X[:, None, :] - self.fit_X_[None, :, :]) ** 2).sum(-1)
        W = np.exp(-d2 / (2 * self.sigma**2))  # shape (n, m)
        if self.agg == "mean":
            return W.mean(1, keepdims=True)
        if self.agg == "sum":
            return W.sum(1, keepdims=True)
        return W  # (n_samples, n_centres)


# ───────────────────────────────────────────────────────────────
class PCAGWD(BaseEstimator, TransformerMixin):
    def __init__(self, sigma=0.1, n_comp=None, var_thr=None):
        self.sigma = sigma
        self.n_comp = n_comp  # ignored if var_thr is not None
        self.var_thr = var_thr  # float in (0,1) or None

    def fit(self, X, y=None):
        d2 = ((X[:, None, :] - X[None, :, :]) ** 2).sum(-1)
        W = np.exp(-d2 / (2 * self.sigma**2))

        n_comp = self.n_comp if self.var_thr is None else None
        self.pca_ = PCA(n_components=n_comp).fit(W)

        if self.var_thr is not None:
            k = (
                np.searchsorted(
                    np.cumsum(self.pca_.explained_variance_ratio_), self.var_thr
                )
                + 1
            )
            self.pca_ = PCA(n_components=k).fit(W)  # refit with chosen k
        return self

    def transform(self, X):
        d2 = (X[:, None, :] - self.pca_.mean_.reshape(1, -1, 1))[:, :, 0] ** 2
        W = np.exp(-d2 / (2 * self.sigma**2))
        return self.pca_.transform(W)


# ───────────────────────────────────────────────────────────────
class KernelPCAGWD(BaseEstimator, TransformerMixin):
    """
    Non-linear compression of Gaussian-Weighted Distance (GWD)
    via Kernel PCA on a precomputed RBF kernel.
    """

    def __init__(self, sigma=0.1, n_comp=30, kpca_gamma=None):
        self.sigma = sigma
        self.n_comp = n_comp
        self.kpca_gamma = kpca_gamma  # unused when kernel='precomputed'

    def fit(self, X, y=None):
        """
        X : array, shape (n_train, n_dim)
            The original 2-D (or ND) coordinates.
        """
        self._X_fit = X.copy()

        # 1) build RBF kernel matrix of pairwise GWD
        sq = ((X[:, None, :] - X[None, :, :]) ** 2).sum(-1)
        K = np.exp(-sq / (2 * self.sigma**2))  # shape (n_train, n_train)

        # 2) fit KernelPCA with a precomputed kernel
        self.kpca_ = KernelPCA(
            n_components=self.n_comp,
            kernel="precomputed",
            eigen_solver="auto",
            remove_zero_eig=True,
        ).fit(K)

        return self

    def transform(self, X):
        """
        X : array, shape (n_new, n_dim)
            New coordinates to map into the same kernel‐PCA subspace.
        """
        # 1) compute GWD rows between new X and training X
        sq = ((X[:, None, :] - self._X_fit[None, :, :]) ** 2).sum(-1)
        K_new = np.exp(-sq / (2 * self.sigma**2))  # shape (n_new, n_train)

        # 2) project
        return self.kpca_.transform(K_new)


# ───────────────────────────────────────────────────────────────
class CorrFilter(BaseEstimator, TransformerMixin):
    """
    Keep GWD columns whose |Pearson r| w/ y >= threshold.
    Uses only the current training fold – no leakage.
    """

    def __init__(self, thr: float = 0.25):
        self.thr = thr  # Optuna will tune this

    def fit(self, X, y):
        # X shape (n, d), y shape (n,) or (n,1)
        y = y.ravel()
        r = np.abs(np.corrcoef(X, y, rowvar=False)[-1, :-1])
        self.mask_ = r >= self.thr
        # if nothing survives, keep the best single column
        if not self.mask_.any():
            self.mask_[np.argmax(r)] = True
        return self

    def transform(self, X):
        return X[:, self.mask_]
