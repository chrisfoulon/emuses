# kernel_regression.py
from copy import deepcopy
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import json
import os
import time

import GPy
# Other imports
import hdbscan
import matplotlib.pyplot as plt
from joblib import Parallel, delayed, dump
from matplotlib import pyplot as plt
# SciPy imports
from scipy.spatial import ConvexHull, cKDTree
from scipy.spatial.distance import cdist
from scipy.stats import normaltest
# Scikit-learn imports
from sklearn.base import BaseEstimator, ClassifierMixin, RegressorMixin
from sklearn.decomposition import PCA
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                             confusion_matrix, f1_score, mean_absolute_error,
                             mean_squared_error, pairwise_distances,
                             precision_score, r2_score, recall_score,
                             roc_auc_score)
from sklearn.model_selection import KFold

from emuses.tools.correlation_maps_utils import calculate_correlation_grid
# EMUSES imports
from emuses.tools.output_utils import save_statistical_maps
from emuses.tools.stats_utils import input_matrix_stat_map


class KernelRegressor(BaseEstimator, RegressorMixin):
    """
    A simple kernel regression model for continuous outcomes based on the Nadaraya–Watson estimator.

    The prediction for a new sample x is computed as:

        y_hat(x) = (sum_i K(x, x_i) * y_i) / (sum_i K(x, x_i))

    where the Gaussian kernel is defined as:

        K(x, x_i) = exp( -0.5 * (||x - x_i|| / sigma)^2 )

    Parameters
    ----------
    sigma : float, default=1.0
        The bandwidth parameter for the Gaussian kernel. A lower sigma makes the kernel more local.
    kernel : str, default='gaussian'
        The type of kernel to use. Currently only 'gaussian' is supported.
    """

    def __init__(self, sigma=1.0, kernel="gaussian"):
        self.sigma = sigma
        self.kernel = kernel

    def fit(self, X, y):
        """
        Fit the kernel regressor using the training data.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            The input training data.
        y : array-like of shape (n_samples,)
            The continuous target values.

        Returns
        -------
        self : object
            Fitted estimator.
        """
        self.X_train = np.asarray(X)
        self.y_train = np.asarray(y)
        return self

    def predict(self, X):
        """
        Predict outcomes for the given test data.

        Parameters
        ----------
        X : array-like of shape (n_test_samples, n_features)
            Test data.

        Returns
        -------
        y_pred : array of shape (n_test_samples,)
            Predicted continuous outcomes.
        """
        X = np.asarray(X)
        predictions = []
        for x in X:
            distances = np.linalg.norm(self.X_train - x, axis=1)
            # Apply the appropriate kernel function based on self.kernel
            if self.kernel == "gaussian" or self.kernel is None:
                weights = np.exp(-0.5 * (distances / self.sigma) ** 2)
            else:
                # Default to Gaussian kernel if unknown kernel type is specified
                weights = np.exp(-0.5 * (distances / self.sigma) ** 2)
            weight_sum = np.sum(weights)
            if weight_sum == 0:
                prediction = 0  # Fallback value; adjust as needed
            else:
                prediction = np.sum(weights * self.y_train) / weight_sum
            predictions.append(prediction)
        return np.array(predictions)


class KernelLogisticRegressor(BaseEstimator, ClassifierMixin):
    """
    A simple kernel-based logistic regression model for binary classification.

    This model estimates the probability of the positive class at a new sample x by performing a weighted average
    of the binary training labels (0 or 1) using the same Gaussian kernel:

        p(x) = (sum_i K(x, x_i) * y_i) / (sum_i K(x, x_i))

    The predicted class is 1 if p(x) >= 0.5 and 0 otherwise.

    Parameters
    ----------
    sigma : float, default=1.0
        The bandwidth parameter for the Gaussian kernel.
    kernel : str, default='gaussian'
        The type of kernel to use.
    """

    def __init__(self, sigma=1.0, kernel="gaussian"):
        self.sigma = sigma
        self.kernel = kernel

    def fit(self, X, y):
        """
        Fit the kernel logistic regressor using the training data.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            The input training data.
        y : array-like of shape (n_samples,)
            The binary target labels (0 or 1).

        Returns
        -------
        self : object
            Fitted estimator.
        """
        self.X_train = np.asarray(X)
        # Ensure labels are floats (0.0 or 1.0) for computation.
        self.y_train = np.asarray(y).astype(float)

        # Store classes for sklearn compatibility
        self.classes_ = np.unique(y)

        # For multi-class compatibility, also create a mapping to class indices
        self.class_to_index_ = {cls: idx for idx, cls in enumerate(self.classes_)}

        return self

    def predict_proba(self, X):
        """
        Predict the probability of the positive class for each test sample.

        Parameters
        ----------
        X : array-like of shape (n_test_samples, n_features)
            Test data.

        Returns
        -------
        probas : array of shape (n_test_samples, n_classes)
            Predicted probabilities for each class.
        """
        X = np.asarray(X)
        probas_class1 = []
        for x in X:
            distances = np.linalg.norm(self.X_train - x, axis=1)

            # Apply the appropriate kernel function based on self.kernel
            if self.kernel == "gaussian" or self.kernel is None:
                weights = np.exp(-0.5 * (distances / self.sigma) ** 2)
            elif self.kernel == "epanechnikov":
                # Epanechnikov kernel: K(u) = 3/4 * (1-u^2) for |u| <= 1, 0 otherwise
                u = distances / self.sigma
                weights = np.zeros_like(u)
                mask = u <= 1
                weights[mask] = 0.75 * (1 - u[mask] ** 2)
            elif self.kernel == "triangular":
                # Triangular kernel: K(u) = (1-|u|) for |u| <= 1, 0 otherwise
                u = distances / self.sigma
                weights = np.zeros_like(u)
                mask = u <= 1
                weights[mask] = 1 - u[mask]
            else:
                # Default to Gaussian if unknown
                weights = np.exp(-0.5 * (distances / self.sigma) ** 2)

            weight_sum = np.sum(weights)
            if weight_sum == 0:
                proba = 0.0  # or another fallback value
            else:
                proba = np.sum(weights * self.y_train) / weight_sum

            # Clip to [0, 1] range to ensure valid probabilities
            proba = np.clip(proba, 0, 1)
            probas_class1.append(proba)

        # Convert to 2D array format that sklearn expects: [[1-p, p], [1-p, p], ...]
        probas_class1 = np.array(probas_class1)
        probas = np.vstack([1 - probas_class1, probas_class1]).T

        return probas

    def predict(self, X):
        """
        Predict binary class labels for the test data.

        Parameters
        ----------
        X : array-like of shape (n_test_samples, n_features)
            Test data.

        Returns
        -------
        labels : array of shape (n_test_samples,)
            Predicted class labels from self.classes_.
        """
        probas = self.predict_proba(X)
        # Get the predicted class using argmax
        indices = np.argmax(probas, axis=1)

        # Return actual class labels from self.classes_, not just binary indices
        return self.classes_[indices]


def nested_cv_kernel_regression(
    X,
    y,
    sigma_values,
    n_outer=5,
    n_inner=3,
    optimize_sigma=True,
    classification=False,
    random_state=42,
):
    """
    Perform nested cross-validation for kernel regression.

    Parameters:
    -----------
    X : numpy.ndarray
        Feature embeddings
    y : numpy.ndarray
        Target score
    sigma_values : list or array-like
        List of sigma values to try for optimization, or fixed sigma values for reproducibility
    n_outer : int
        Number of folds for outer CV
    n_inner : int
        Number of folds for inner CV
    optimize_sigma : bool, default=True
        If True, performs inner CV to find optimal sigma from sigma_values.
        If False, each fold in the ensemble uses the corresponding sigma from sigma_values
        directly (for reproducibility). If len(sigma_values)=1, that single value is used for all folds.
    classification : bool, default=False
        Whether to use KernelRegressor (False) or KernelLogisticRegressor (True)
    random_state : int
        Random seed for reproducibility

    Returns:
    --------
    list
        List of trained models (ensemble)
    list
        Performance results for each outer fold
    float
        Best sigma value
    list
        Sigma values used for each outer fold model
    """
    from sklearn.model_selection import KFold

    outer_cv = KFold(n_splits=n_outer, shuffle=True, random_state=random_state)
    inner_cv = KFold(n_splits=n_inner, shuffle=True, random_state=random_state + 1)

    trained_models = []
    performance_results = []
    best_sigmas = []
    unseen_preds_dict = {}

    # Create indices for outer CV
    outer_cv_indices = list(outer_cv.split(X))

    # Variable to keep track of current fold for fixed sigma values
    fold_counter = 0

    # Outer CV loop
    for train_idx, test_idx in outer_cv_indices:
        X_train_outer, X_test_outer = X[train_idx], X[test_idx]
        y_train_outer, y_test_outer = y[train_idx], y[test_idx]

        # Determine which sigma to use for this fold
        if optimize_sigma:
            # Inner CV to find best sigma
            best_sigma = None
            best_score = -np.inf

            for sigma in sigma_values:
                scores = []

                # Inner CV loop
                for inner_train_idx, inner_val_idx in inner_cv.split(X_train_outer):
                    X_train_inner, X_val_inner = (
                        X_train_outer[inner_train_idx],
                        X_train_outer[inner_val_idx],
                    )
                    y_train_inner, y_val_inner = (
                        y_train_outer[inner_train_idx],
                        y_train_outer[inner_val_idx],
                    )

                    # Train model with current sigma
                    if classification:
                        model = KernelLogisticRegressor(sigma=sigma)
                    else:
                        model = KernelRegressor(sigma=sigma)

                    model.fit(X_train_inner, y_train_inner)

                    # Evaluate on validation set
                    y_pred = model.predict(X_val_inner)
                    if classification:
                        from sklearn.metrics import balanced_accuracy_score

                        score = balanced_accuracy_score(y_val_inner, y_pred)
                    else:
                        score = r2_score(y_val_inner, y_pred)
                    scores.append(score)

                # Average score for this sigma
                mean_score = np.mean(scores)

                if mean_score > best_score:
                    best_score = mean_score
                    best_sigma = sigma
        else:
            # Fixed sigma mode - no optimization
            if len(sigma_values) == 1:
                # If only one sigma value provided, use it for all folds
                best_sigma = sigma_values[0]
            else:
                # If multiple fixed values, use them in sequence for each fold
                sigma_index = fold_counter % len(sigma_values)
                best_sigma = sigma_values[sigma_index]

        # Train model on full outer training set with best sigma
        best_sigmas.append(best_sigma)
        if classification:
            model = KernelLogisticRegressor(sigma=best_sigma)
        else:
            model = KernelRegressor(sigma=best_sigma)

        model.fit(X_train_outer, y_train_outer)
        trained_models.append(model)

        # Evaluate on outer test set
        y_pred = model.predict(X_test_outer)

        # Store predictions on test set
        for idx, pred in zip(test_idx, y_pred):
            unseen_preds_dict[idx] = (y[idx], pred)

        # Calculate and store performance metrics
        if classification:
            from sklearn.metrics import accuracy_score, balanced_accuracy_score

            acc = accuracy_score(y_test_outer, y_pred)
            bal_acc = balanced_accuracy_score(y_test_outer, y_pred)
            performance_results.append(
                {
                    "accuracy": acc,
                    "balanced_accuracy": bal_acc,
                    "best_sigma": best_sigma,
                }
            )
        else:
            mse = mean_squared_error(y_test_outer, y_pred)
            rmse = np.sqrt(mse)
            r2 = r2_score(y_test_outer, y_pred)
            performance_results.append(
                {"mse": mse, "rmse": rmse, "r2": r2, "best_sigma": best_sigma}
            )

        # Increment fold counter for fixed sigma mode
        fold_counter += 1

    # Determine overall best sigma (most frequently chosen)
    if len(set(best_sigmas)) > 0:
        best_sigma = max(set(best_sigmas), key=best_sigmas.count)
    else:
        best_sigma = sigma_values[0] if len(sigma_values) > 0 else None

    return trained_models, performance_results, best_sigma, best_sigmas


def ensemble_predict(models, X, is_classification=None):
    """
    Make predictions with an ensemble of models.

    Parameters:
    -----------
    models : list
        List of trained models
    X : numpy.ndarray
        Features to predict on
    is_classification : bool, optional
        If True, handle as classification problem (use predict_proba if available).
        If None, auto-detect based on model type.

    Returns:
    --------
    numpy.ndarray
        Mean prediction (probabilities for classification, values for regression)
    numpy.ndarray
        Standard deviation of predictions (uncertainty)
    """
    # Auto-detect classification if not specified
    if is_classification is None:
        # Check if first model has predict_proba (typical for classifiers)
        is_classification = hasattr(models[0], "predict_proba") and isinstance(
            models[0], ClassifierMixin
        )

    if is_classification and hasattr(models[0], "predict_proba"):
        try:
            # For binary classification
            if len(models[0].classes_) == 2:
                # Get probabilities for all classes from each model
                # Each element will be shape [n_samples, n_classes]
                all_probas = [model.predict_proba(X) for model in models]

                # Stack into 3D array: [n_models, n_samples, n_classes]
                stacked_probas = np.stack(all_probas, axis=0)

                # Calculate mean and std across models (axis=0)
                mean_probas = np.mean(stacked_probas, axis=0)  # [n_samples, n_classes]
                std_probas = np.std(stacked_probas, axis=0)  # [n_samples, n_classes]

                # For binary classification, return just the positive class probability
                # This maintains backward compatibility
                mean_proba = mean_probas[:, 1]  # Positive class probability
                std_proba = std_probas[:, 1]  # Std dev of positive class probability

                return mean_proba, std_proba

            # For multi-class classification
            else:
                # Get probabilities for all classes from each model
                all_probas = [model.predict_proba(X) for model in models]

                # Stack into 3D array: [n_models, n_samples, n_classes]
                stacked_probas = np.stack(all_probas, axis=0)

                # Calculate mean and std across models (axis=0)
                mean_probas = np.mean(stacked_probas, axis=0)
                std_probas = np.std(stacked_probas, axis=0)

                return mean_probas, std_probas

        except (IndexError, ValueError, AttributeError) as e:
            # If probability prediction fails, log the error and fall back to standard predictions
            print(
                f"Warning: Probability prediction failed with error: {e}. Falling back to standard predictions."
            )
            pass

    # Standard approach using direct predictions
    predictions = np.array([model.predict(X) for model in models])

    # For classification tasks with regular predictions,
    # we need to convert string/categorical predictions to numeric
    if is_classification:
        # Try to make predictions numeric if they aren't already
        if predictions.dtype.kind not in "ifc":  # integer, float, complex
            try:
                predictions = predictions.astype(float)
            except (ValueError, TypeError):
                # If conversion fails, leave as is
                pass

    # Calculate mean and std across all models
    mean_pred = np.mean(predictions, axis=0)
    std_pred = np.std(predictions, axis=0)

    return mean_pred, std_pred


def evaluate_ensemble_on_test(models, X_test, y_test, classification=False):
    """
    Evaluate an ensemble of kernel regression (or logistic regression) models on the test set.

    Parameters
    ----------
    models : list
        List of trained kernel regression (or logistic regression) models.
    X_test : np.ndarray of shape (n_samples, n_features)
        Test data.
    y_test : np.ndarray of shape (n_samples,)
        True labels for test data.
    classification : bool, default=False
        If True, compute classification metrics; if False, compute regression metrics.

    Returns
    -------
    results : dict
        Dictionary containing:
            - 'mean_prediction': Ensemble mean prediction (as a list).
            - 'std_prediction': Ensemble prediction standard deviation (as a list).
            - Various performance metrics depending on task type.
            Plus, if classification:
                - 'accuracy', 'balanced_accuracy', 'confusion_matrix', 'roc_auc', 'f1_score', 'precision', 'recall'
            Otherwise (regression):
                - 'r2', 'mse', 'mae', 'normalized_mse_%', 'normalized_mae_%'
    """
    # Use the ensemble_predict function to get predictions and their standard deviation.
    mean_pred, std_pred = ensemble_predict(
        models, X_test, is_classification=classification
    )

    # Convert NumPy arrays to lists for JSON serialization.
    results = {
        "mean_prediction": mean_pred.tolist(),
        "std_prediction": std_pred.tolist(),
    }

    if classification:
        # For classification, we need to determine if we have class labels or probabilities
        if hasattr(models[0], "classes_"):
            classes = models[0].classes_
            n_classes = len(classes)
        else:
            classes = np.unique(y_test)
            n_classes = len(classes)

        # Check if we have probabilities (shape indicates a 2D array with class probabilities)
        if len(mean_pred.shape) > 1 and mean_pred.shape[1] > 1:
            # We have class probabilities, convert to class predictions
            y_pred_indices = np.argmax(mean_pred, axis=1)
            y_pred = classes[y_pred_indices]
        elif np.any((mean_pred > 0) & (mean_pred < 1)):
            # We have probability estimates for binary classification
            y_pred = (mean_pred >= 0.5).astype(int)
            # Map to actual class labels if available
            if hasattr(models[0], "classes_"):
                class_map = {0: models[0].classes_[0], 1: models[0].classes_[1]}
                y_pred = np.array([class_map[p] for p in y_pred])
        else:
            # mean_pred is already class predictions
            y_pred = mean_pred

        # Basic metrics
        try:
            results["accuracy"] = float(accuracy_score(y_test, y_pred))
            results["balanced_accuracy"] = float(
                balanced_accuracy_score(y_test, y_pred)
            )
        except Exception as e:
            results["metric_error"] = str(e)
            results["accuracy"] = None
            results["balanced_accuracy"] = None

        # Store confusion matrix
        try:
            cm = confusion_matrix(y_test, y_pred)
            results["confusion_matrix"] = cm.tolist()
        except Exception as e:
            results["confusion_matrix_error"] = str(e)

        # ROC AUC - only applies to binary classification with probability estimates
        if n_classes == 2:
            try:
                # Check if we have probability estimates
                if np.any((mean_pred > 0) & (mean_pred < 1)):
                    if len(mean_pred.shape) > 1:
                        # For multi-class format, use the positive class probability
                        prob_estimates = mean_pred[:, 1]
                    else:
                        # For binary format, use the probabilities directly
                        prob_estimates = mean_pred
                    results["roc_auc"] = float(roc_auc_score(y_test, prob_estimates))
                else:
                    results["roc_auc"] = None  # No probabilities available
            except Exception as e:
                results["roc_auc"] = None
                results["roc_auc_error"] = str(e)
        else:
            results["roc_auc"] = None  # Not applicable for multiclass

        # Determine the appropriate averaging method for multiclass vs binary
        average_param = "binary" if n_classes == 2 else "macro"

        try:
            results["f1_score"] = float(f1_score(y_test, y_pred, average=average_param))
            results["precision"] = float(
                precision_score(y_test, y_pred, average=average_param)
            )
            results["recall"] = float(
                recall_score(y_test, y_pred, average=average_param)
            )
        except Exception as e:
            # Handle potential errors in metric calculation
            results["metric_calculation_error"] = str(e)
            results["f1_score"] = None
            results["precision"] = None
            results["recall"] = None
    else:
        # Regression metrics
        from sklearn.metrics import (mean_absolute_error, mean_squared_error,
                                     r2_score)

        results["r2"] = float(r2_score(y_test, mean_pred))
        results["mse"] = float(mean_squared_error(y_test, mean_pred))
        results["mae"] = float(mean_absolute_error(y_test, mean_pred))
        # Normalize errors based on the range of y_test (could also use training set range)
        target_range = np.max(y_test) - np.min(y_test)
        if target_range == 0:
            normalized_mse = None
            normalized_mae = None
        else:
            normalized_mse = (results["mse"] / (target_range**2)) * 100
            normalized_mae = (results["mae"] / target_range) * 100
        results["normalized_mse_%"] = normalized_mse
        results["normalized_mae_%"] = normalized_mae

    return results


def run_kernel_heatmap_analysis(
    embeddings,
    scores_vectors_dict,
    input_matrix,
    output_folder,
    grid_size=100,
    sigma_range=None,
    threshold=0.5,
    uncertainty_penalty=0.5,
    input_type="image",
    classification=False,
    cluster_labels=None,
    effect_size_test="mann-whitney",
    highlight_points=True,
    show_plots=False,
    generate_plots=False,
    output_format_info=None,
    full_embeddings=None,
    clusterer=None,
    cluster_predict_method="kdtree",
    optimize_sigma=True,
    random_state=42,
):
    """
    Generate a kernel regression–based heatmap of predicted outcomes on a 2D latent space.

    For each score tag in `scores_vectors_dict`, this function:
      1. Performs nested cross-validation to train an ensemble of kernel regressors (or logistic regressors if classification=True).
      2. Uses the ensemble to predict on a grid spanning the latent space, forming a heatmap of ensemble mean predictions and an uncertainty map.
      3. Combines the mean and uncertainty into a single map: combined_heatmap = mean - (uncertainty_penalty * std).
      4. Determines a dynamic threshold for “high-confidence” predictions:
         - For regression (classification=False), a normality test is used to choose either mean+2*std or the 95th percentile.
         - For classification, the provided threshold is used.
         - In regression mode, an additional dynamic low threshold is computed (using mean-2*std or the 5th percentile) to identify clusters with deficit values.
      5. Optionally computes effect-size maps for each cluster (if at least 3 high- or low-confidence points exist in that cluster).
      6. If a fitted clusterer is provided, the function assigns cluster labels to grid points using one of several methods (kdtree, approximate, or fit_predict).
         The final cluster-specific plot overlays:
            - The background combined heatmap,
            - All embeddings as scatter points (if in label_dataset mode, the union of full_embeddings and embeddings),
            - The high-confidence (significant) training points for that cluster in lime (or low-confidence in cyan) with a black border,
            - And the boundary of the significant zone (convex hull).
      7. Returns a dictionary of heatmap data for each score tag and a list of nested CV performance results.

    Parameters
    ----------
    embeddings : np.ndarray of shape (n_samples, 2)
        The 2D embeddings used for training/prediction (for classic mode or the labelled dataset in label_dataset mode).
    scores_vectors_dict : dict
        Mapping from each score tag (string) to a 1D target vector (binary or continuous) corresponding to each row in embeddings.
    input_matrix : np.ndarray
        The original high-dimensional input data (each row corresponds to a sample), used for effect-size analysis.
    output_folder : str or Path
        Directory where outputs (models, plots, performance metrics, etc.) will be saved.
    grid_size : int, default=100
        Number of grid points along each dimension of the latent space.
    sigma_range : array-like, optional
        Candidate sigma values for kernel regression. If None, defaults to np.linspace(0.01, 0.2, num=8).
    threshold : float, default=0.5
        Threshold for classification tasks to define high-confidence predictions (ignored for regression).
    uncertainty_penalty : float, default=0.5
        Multiplier for penalizing regions with high uncertainty in the ensemble predictions.
    input_type : {'image', 'nifti', 'spreadsheet'}, default='image'
        Type of the input data, used for saving effect-size maps.
    classification : bool, default=False
        Whether to perform classification (kernel logistic regression) or regression (kernel regression).
    cluster_labels : np.ndarray, optional
        Cluster labels for each row in embeddings. If provided, effect-size maps and cluster-specific plots are computed.
    effect_size_test : str, default='mann-whitney'
        The statistical test to compute effect sizes; passed to input_matrix_stat_map.
    highlight_points : bool, default=True
        If True, scatter plot the embeddings on top of the heatmap in the main figure.
    show_plots : bool, default=False
        If True, call plt.show() to display plots interactively.
    generate_plots : bool, default=False
        If True, generate and save plot images.
    output_format_info : any, optional
        Extra information needed for formatting and saving effect-size maps (e.g., image shape or affine).
    full_embeddings : np.ndarray of shape (n_full, 2), optional
        In label_dataset mode, the unlabelled UMAP embeddings (used for grid definition and to display all points).
        In classic mode, if not provided, embeddings is used.
    clusterer : object, optional
        A fitted HDBSCAN object with prediction_data=True, so that its approximate_predict method can be used on new data.
    cluster_predict_method : str, default="kdtree"
        Method to use for assigning cluster labels to new grid points.

    Returns
    -------
    heatmap_dict : dict
        A dictionary mapping each score tag to a sub-dictionary containing:
            - 'mean_heatmap': 2D array (grid_size x grid_size) of ensemble mean predictions.
            - 'std_heatmap': 2D array (grid_size x grid_size) of ensemble standard deviations.
            - 'combined_heatmap': 2D array (grid_size x grid_size) computed as mean - uncertainty_penalty * std.
            - 'grid_x': 1D array of x-coordinates of the grid.
            - 'grid_y': 1D array of y-coordinates of the grid.
            - 'models': List of trained models from nested cross-validation.
            - 'cv_performance': List of performance dictionaries from the outer CV folds.
            - 'effect_size': Dictionary mapping 'high' and 'low' to effect-size maps for each cluster.
            - 'plot': The main matplotlib Figure object of the combined heatmap (or None).
            - 'grid_mean_uncertainty': Float, mean uncertainty over the grid.
            - 'grid_std_uncertainty': Float, standard deviation of uncertainty over the grid.
    cv_performance_all : list
        A list of dictionaries with CV performance results aggregated across all score tags.
    """
    # Default sigma range if not provided.
    if sigma_range is None:
        sigma_range = np.linspace(0.01, 0.2, num=8)

    # Ensure output folder exists.
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    # Use combined embeddings for grid creation.
    if full_embeddings is not None and embeddings is not None:
        combined_embeddings = np.concatenate([full_embeddings, embeddings], axis=0)
    else:
        combined_embeddings = (
            full_embeddings if full_embeddings is not None else embeddings
        )

    min_coords = combined_embeddings.min(axis=0)
    max_coords = combined_embeddings.max(axis=0)
    grid_x = np.linspace(min_coords[0], max_coords[0], grid_size)
    grid_y = np.linspace(min_coords[1], max_coords[1], grid_size)
    grid_points = np.array(np.meshgrid(grid_x, grid_y)).T.reshape(-1, 2)

    # Determine which embeddings to plot: use the union in label_dataset mode.
    if (
        full_embeddings is not None
        and embeddings is not None
        and not np.array_equal(full_embeddings, embeddings)
    ):
        plot_embeddings_array = np.concatenate([full_embeddings, embeddings], axis=0)
    else:
        plot_embeddings_array = (
            full_embeddings if full_embeddings is not None else embeddings
        )

    heatmap_dict = {}
    cv_performance_all = []

    for score_tag, y in scores_vectors_dict.items():
        print(f"Processing score tag: {score_tag}...")

        # --- Filter out datapoints with NaN in the current score ---
        mask = ~np.isnan(y)
        num_ignored = len(y) - np.sum(mask)
        if num_ignored > 0:
            print(
                f"Warning: {num_ignored} datapoints have been ignored for score tag '{score_tag}' because "
                f"they don't have a value."
            )
        y_filtered = y[mask]
        embeddings_filtered = embeddings[mask]
        if input_matrix is not None:
            if len(input_matrix) == len(y):
                input_matrix_filtered = input_matrix[mask]
            else:
                print(
                    "Input matrix length does not match the score vector length; skipping input_matrix filtering."
                )
                input_matrix_filtered = input_matrix
        else:
            input_matrix_filtered = input_matrix
        # --------------------------------------------------------------------

        # Auto-detect classification if not explicitly specified
        task_classification = classification
        if not task_classification and is_classification_target(y_filtered):
            print(
                f"Auto-detected classification task for '{score_tag}' based on target values."
            )
            task_classification = True

        # Call nested CV and obtain unseen predictions using filtered training data.
        models, cv_perf, best_sigma, best_sigmas = nested_cv_kernel_regression(
            embeddings_filtered,
            y_filtered,
            sigma_values=sigma_range,
            n_outer=5,
            n_inner=5,
            classification=task_classification,
            random_state=random_state,
        )

        # Extract unseen predictions from CV results for threshold calculation
        unseen_preds_dict = {}
        for i, model in enumerate(models):
            fold_test_idx = list(
                KFold(
                    n_splits=len(models), shuffle=True, random_state=random_state
                ).split(embeddings_filtered)
            )[i][1]
            fold_test_preds = (
                model.predict_proba(embeddings_filtered[fold_test_idx])
                if task_classification and hasattr(model, "predict_proba")
                else model.predict(embeddings_filtered[fold_test_idx])
            )

            # For binary classification, extract positive class probability
            if (
                task_classification
                and hasattr(model, "predict_proba")
                and isinstance(fold_test_preds, np.ndarray)
                and fold_test_preds.ndim == 2
            ):
                fold_test_preds = fold_test_preds[:, 1]  # Positive class probability

            for j, pred in enumerate(fold_test_preds):
                unseen_preds_dict[fold_test_idx[j]] = (
                    y_filtered[fold_test_idx[j]],
                    pred,
                )

        for perf in cv_perf:
            perf["score_tag"] = score_tag
        cv_performance_all.extend(cv_perf)
        print(f"Trained {len(models)} models for score tag '{score_tag}'.")

        pred_models_perf_folder = (
            output_folder / "prediction_models" / "kernel_regression_perf"
        )
        pred_models_perf_folder.mkdir(parents=True, exist_ok=True)

        perf_df = pd.DataFrame(cv_perf)
        perf_path = pred_models_perf_folder / f"cv_performance_metrics_{score_tag}.csv"
        perf_df.to_csv(perf_path, index=False)
        print(
            f"Saved CV performance metrics for score tag '{score_tag}' to {perf_path}"
        )

        # Save ensemble models.
        pred_models_folder = output_folder / "prediction_models" / "kernel_regression"
        pred_models_folder.mkdir(parents=True, exist_ok=True)
        for i, model in enumerate(models):
            model_filename = (
                pred_models_folder / f"kernel_model_{score_tag}_fold_{i}.joblib"
            )
            dump(model, model_filename)
            print(f"Saved kernel regression model for fold {i} at {model_filename}")

        # Ensemble predict on grid for visualization
        mean_pred, std_pred = ensemble_predict(
            models, grid_points, is_classification=task_classification
        )

        # Handle different return types from ensemble_predict for classification vs. regression
        if (
            task_classification
            and hasattr(models[0], "classes_")
            and len(models[0].classes_) > 2
        ):
            # For multi-class, mean_pred is shape [n_samples, n_classes]
            # Create a heatmap showing the highest probability class
            mean_heatmap = np.argmax(mean_pred, axis=1).reshape(grid_size, grid_size)

            # For uncertainty, use the max class probability (higher = more certain)
            max_probs = np.max(mean_pred, axis=1)
            std_heatmap = (1 - max_probs).reshape(
                grid_size, grid_size
            )  # Invert so higher = more uncertain
        else:
            # For binary classification or regression, results are already in the correct format
            mean_heatmap = mean_pred.reshape(grid_size, grid_size)
            std_heatmap = std_pred.reshape(grid_size, grid_size)

        # This section was removed to fix duplicate code

        # Compute a combined heatmap.
        combined_heatmap = mean_heatmap - uncertainty_penalty * std_heatmap

        # Generate main heatmap plot if requested.
        plot_obj = None
        if generate_plots:
            plt.figure(figsize=(8, 6))

            # Choose appropriate colormap and title based on task type
            cmap = "viridis"  # Default colormap
            colorbar_label = "Combined Confidence"
            title_prefix = "Kernel Regression"

            if task_classification:
                title_prefix = "Kernel Classification"
                if hasattr(models[0], "classes_") and len(models[0].classes_) > 2:
                    # For multi-class, use a discrete colormap
                    n_classes = len(models[0].classes_)
                    cmap = plt.cm.get_cmap("tab10", n_classes)
                    colorbar_label = "Predicted Class"

            # Display the combined heatmap
            im = plt.imshow(
                combined_heatmap.T,
                origin="lower",
                extent=(min_coords[0], max_coords[0], min_coords[1], max_coords[1]),
                cmap=cmap,
                aspect="auto",
            )

            # Create colorbar
            cbar = plt.colorbar(im, label=colorbar_label)

            # For multi-class classification, add class labels to colorbar
            if (
                task_classification
                and hasattr(models[0], "classes_")
                and len(models[0].classes_) > 2
            ):
                class_labels = models[0].classes_
                # Add colorbar ticks at class positions
                cbar.set_ticks(np.arange(len(class_labels)))
                cbar.set_ticklabels([f"Class {c}" for c in class_labels])

            plt.title(f"{title_prefix} Combined Heatmap for Score {score_tag}")

            if highlight_points:
                # Plot all embeddings in red (the union if label_dataset mode).
                plt.scatter(
                    plot_embeddings_array[:, 0],
                    plot_embeddings_array[:, 1],
                    color="red",
                    s=10,
                    alpha=0.5,
                    label="All embeddings",
                )
            plt.savefig(output_folder / f"kernel_heatmap_{score_tag}.png")
            print(f"Saved combined heatmap for score '{score_tag}'")
            plot_obj = plt.gcf()
            plt.close()

        # Compute dynamic thresholds based on task type
        all_unseen_preds = np.array([pred for (_, pred) in unseen_preds_dict.values()])

        if not task_classification:
            # For regression: use normality test to pick dynamic threshold
            stat_val, pvalue = normaltest(all_unseen_preds)
            if pvalue > 0.05:
                dynamic_threshold_high = np.mean(all_unseen_preds) + 2 * np.std(
                    all_unseen_preds
                )
                dynamic_threshold_low = np.mean(all_unseen_preds) - 2 * np.std(
                    all_unseen_preds
                )
            else:
                dynamic_threshold_high = np.percentile(all_unseen_preds, 95)
                dynamic_threshold_low = np.percentile(all_unseen_preds, 5)
            print(
                f"Dynamic thresholds for regression: high = {dynamic_threshold_high:.3f}, "
                f"low = {dynamic_threshold_low:.3f} (normality p={pvalue:.3f})"
            )
        else:
            # For classification tasks
            if hasattr(models[0], "classes_") and len(models[0].classes_) > 2:
                # Multi-class: use threshold on the max class probability
                dynamic_threshold_high = threshold
                dynamic_threshold_low = None
                print(
                    f"Using classification threshold: {threshold} for multi-class task"
                )
            else:
                # Binary classification: use the provided threshold for positive class probability
                dynamic_threshold_high = threshold
                dynamic_threshold_low = None
                print(f"Using classification threshold: {threshold} for binary task")

        # Use combined embeddings for full prediction if available.
        if full_embeddings is not None and not np.array_equal(
            full_embeddings, embeddings
        ):
            full_pred, full_std = ensemble_predict(
                models, combined_embeddings, is_classification=task_classification
            )
        else:
            full_pred, full_std = ensemble_predict(
                models, embeddings, is_classification=task_classification
            )

        # Identify high and low prediction indices based on task type
        if task_classification:
            if hasattr(models[0], "classes_") and len(models[0].classes_) > 2:
                # For multi-class, we need to identify points with high confidence in any class
                if isinstance(full_pred, np.ndarray) and full_pred.ndim > 1:
                    # Get the highest probability for each point
                    max_probs = np.max(full_pred, axis=1)
                    # Points with high confidence (probability > threshold)
                    high_pred_indices = np.where(max_probs > dynamic_threshold_high)[0]
                else:
                    # Fallback if we don't have probability format
                    high_pred_indices = np.arange(len(full_pred))
            else:
                # Binary classification - use positive class probability
                high_pred_indices = np.where(full_pred > dynamic_threshold_high)[0]

            # No low prediction indices for classification tasks
            low_pred_indices = np.array([])
        else:
            # For regression tasks, use standard threshold approach
            high_pred_indices = np.where(full_pred > dynamic_threshold_high)[0]
            if dynamic_threshold_low is not None:
                low_pred_indices = np.where(full_pred < dynamic_threshold_low)[0]
            else:
                low_pred_indices = np.array([])

        # Process high-confidence points.
        effect_size_maps_high = {}
        if len(high_pred_indices) < 3:
            print(
                f"Not enough high-confidence points for score tag '{score_tag}' (n={len(high_pred_indices)}); skipping high effect size maps."
            )
        else:
            # If cluster labels are provided, we can do effect-size maps and highlight clusters
            if cluster_labels is not None:
                high_clusters = cluster_labels[high_pred_indices]
                unique_high_clusters = np.unique(high_clusters)
            else:
                unique_high_clusters = []
            print("###############DEBUG################")
            print(f"Unique high clusters: {unique_high_clusters}")
            print("###############END DEBUG################")
            for cluster in unique_high_clusters:
                if cluster == -1:
                    continue
                cluster_mask = cluster_labels[high_pred_indices] == cluster
                cluster_high_indices = high_pred_indices[cluster_mask]
                if len(cluster_high_indices) < 3:
                    print(
                        f"Cluster {cluster} for score tag '{score_tag}' has fewer than 3 high-confidence points; skipping."
                    )
                    continue

                print(
                    f"Computing effect size map for high cluster {cluster} and score tag '{score_tag}'..."
                )
                _, _, effect_size_map = input_matrix_stat_map(
                    input_matrix_filtered,
                    cluster_high_indices,
                    test_name=effect_size_test,
                    n_cores=-1,
                )
                effect_size_maps_high[cluster] = effect_size_map
                stat_maps_to_save = {cluster: effect_size_map}
                save_statistical_maps(
                    stat_maps=stat_maps_to_save,
                    output_folder=output_folder,
                    input_type=input_type,
                    output_format_info=output_format_info,
                    filename_prefix=f"effect_size_map_{score_tag}_cluster_{cluster}_high",
                    save_output=True,
                    generate_plots=generate_plots,
                )
                print(f"Effect size map for high cluster {cluster} saved.")

                # Plot overlay for high cluster.
                plt.figure(figsize=(8, 6))
                # Display the combined heatmap as the background.
                plt.imshow(
                    combined_heatmap.T,
                    origin="lower",
                    extent=(min_coords[0], max_coords[0], min_coords[1], max_coords[1]),
                    cmap="viridis",
                    aspect="auto",
                )
                plt.colorbar(label="Combined Confidence")
                # Plot all embeddings (e.g., in red)
                plt.scatter(
                    plot_embeddings_array[:, 0],
                    plot_embeddings_array[:, 1],
                    color="red",
                    s=10,
                    alpha=0.5,
                    label="All embeddings",
                )
                # Plot only the significant points for the current cluster (e.g., in green)
                cluster_points = combined_embeddings[high_pred_indices][cluster_mask]
                plt.scatter(
                    cluster_points[:, 0],
                    cluster_points[:, 1],
                    facecolors="lime",
                    edgecolors="k",
                    s=30,
                    alpha=1.0,
                    label="High cluster points",
                )
                plt.title(
                    f"Heatmap Overlay with High Cluster {cluster} for score '{score_tag}'"
                )
                plt.legend()
                overlay_path = (
                    output_folder
                    / f"kernel_heatmap_{score_tag}_cluster_{cluster}_high_overlay.png"
                )
                plt.savefig(overlay_path)
                print(
                    f"Saved high overlay heatmap for score '{score_tag}' cluster '{cluster}' at {overlay_path}"
                )
                plt.close()

                # Cluster-specific plot using the selected method.
                if cluster_predict_method == "fit_predict":
                    if clusterer is None:
                        raise ValueError(
                            "clusterer must be provided for fit_predict method."
                        )
                    clusterer_copy = deepcopy(clusterer)
                    # Use combined_embeddings for re-clustering on the union.
                    combined_for_clustering = np.concatenate(
                        [combined_embeddings, grid_points], axis=0
                    )
                    combined_labels = clusterer_copy.fit_predict(
                        combined_for_clustering
                    )
                    grid_pred = combined_labels[combined_embeddings.shape[0] :]
                elif cluster_predict_method == "approximate":
                    try:
                        grid_pred, _ = hdbscan.approximate_predict(
                            clusterer, grid_points
                        )
                    except Exception as e:
                        print(
                            f"approximate_predict failed: {e}. Falling back to KDTree assignment."
                        )
                        tree = cKDTree(combined_embeddings)
                        dist, idx = tree.query(grid_points, k=1)
                        grid_pred = cluster_labels[idx]
                elif cluster_predict_method == "kdtree":
                    tree = cKDTree(combined_embeddings)
                    dist, idx = tree.query(grid_points, k=1)
                    grid_pred = cluster_labels[idx]
                else:
                    raise ValueError(
                        f"Unknown cluster_predict_method: {cluster_predict_method}"
                    )

                grid_mask = (grid_pred == cluster) & (
                    combined_heatmap.flatten() > dynamic_threshold_high
                )
                grid_significant_points = grid_points[grid_mask]

                if len(grid_significant_points) >= 3 and generate_plots:
                    plt.figure(figsize=(8, 6))
                    # Display the combined heatmap as background.
                    plt.imshow(
                        combined_heatmap.T,
                        origin="lower",
                        extent=(
                            min_coords[0],
                            max_coords[0],
                            min_coords[1],
                            max_coords[1],
                        ),
                        cmap="viridis",
                        aspect="auto",
                    )
                    plt.colorbar(label="Combined Confidence")
                    # Plot the union of embeddings (both full and labelled) in red.
                    plt.scatter(
                        plot_embeddings_array[:, 0],
                        plot_embeddings_array[:, 1],
                        color="red",
                        s=10,
                        alpha=0.5,
                        label="All embeddings",
                    )
                    # Plot the high-confidence training points for this cluster (from embeddings).
                    train_sig_mask = cluster_labels[high_pred_indices] == cluster
                    # Use combined_embeddings for the training points as well.
                    train_significant_points = combined_embeddings[high_pred_indices][
                        train_sig_mask
                    ]
                    plt.scatter(
                        train_significant_points[:, 0],
                        train_significant_points[:, 1],
                        facecolors="lime",
                        edgecolors="k",
                        s=30,
                        alpha=1.0,
                        label="Significant points",
                    )
                    # Compute convex hull on the grid significant points.
                    try:
                        hull = ConvexHull(grid_significant_points)
                        hull_points = grid_significant_points[hull.vertices]
                        hull_points = np.concatenate(
                            [hull_points, hull_points[:1]], axis=0
                        )
                        plt.plot(
                            hull_points[:, 0],
                            hull_points[:, 1],
                            "w--",
                            lw=3,
                            label="Significant Zone Boundary",
                        )
                    except Exception as e:
                        print(
                            f"Could not compute convex hull for cluster {cluster} on grid: {e}"
                        )

                    plt.title(
                        f"Significant Zone for Score {score_tag} - Cluster {cluster}"
                    )
                    plt.legend()
                    cluster_out_path = (
                        output_folder
                        / f"kernel_heatmap_{score_tag}_cluster_{cluster}_significant_zone.png"
                    )
                    plt.savefig(cluster_out_path)
                    print(
                        f"Saved significant zone plot for score '{score_tag}' cluster '{cluster}' at {cluster_out_path}"
                    )
                    plt.close()

        # === Low-confidence branch (only for regression mode) ===
        effect_size_maps_low = {}
        if not task_classification:
            if len(low_pred_indices) < 3:
                print(
                    f"Not enough low-confidence points for score tag '{score_tag}' (n={len(low_pred_indices)}); skipping low effect size maps."
                )
            else:
                if cluster_labels is not None:
                    low_clusters = cluster_labels[low_pred_indices]
                    unique_low_clusters = np.unique(low_clusters)
                else:
                    unique_low_clusters = []
                print("###############DEBUG################")
                print(f"Unique low clusters: {unique_low_clusters}")
                print("###############END DEBUG################")
                for cluster in unique_low_clusters:
                    if cluster == -1:
                        continue
                    cluster_mask = cluster_labels[low_pred_indices] == cluster
                    cluster_low_indices = low_pred_indices[cluster_mask]
                    if len(cluster_low_indices) < 3:
                        print(
                            f"Cluster {cluster} for score tag '{score_tag}' has fewer than 3 low-confidence points; skipping."
                        )
                        continue
                    print(
                        f"Computing effect size map for low cluster {cluster} and score tag '{score_tag}'..."
                    )
                    _, _, effect_size_map_low = input_matrix_stat_map(
                        input_matrix_filtered,
                        cluster_low_indices,
                        test_name=effect_size_test,
                        n_cores=-1,
                    )
                    effect_size_maps_low[cluster] = effect_size_map_low
                    stat_maps_to_save_low = {cluster: effect_size_map_low}
                    save_statistical_maps(
                        stat_maps=stat_maps_to_save_low,
                        output_folder=output_folder,
                        input_type=input_type,
                        output_format_info=output_format_info,
                        filename_prefix=f"effect_size_map_{score_tag}_cluster_{cluster}_low",
                        save_output=True,
                        generate_plots=generate_plots,
                    )
                    print(f"Effect size map for low cluster {cluster} saved.")

                    # Plot overlay for low cluster.
                    plt.figure(figsize=(8, 6))
                    plt.imshow(
                        combined_heatmap.T,
                        origin="lower",
                        extent=(
                            min_coords[0],
                            max_coords[0],
                            min_coords[1],
                            max_coords[1],
                        ),
                        cmap="viridis",
                        aspect="auto",
                    )
                    plt.colorbar(label="Combined Confidence")
                    plt.scatter(
                        plot_embeddings_array[:, 0],
                        plot_embeddings_array[:, 1],
                        color="red",
                        s=10,
                        alpha=0.5,
                        label="All embeddings",
                    )
                    cluster_points_low = combined_embeddings[low_pred_indices][
                        cluster_mask
                    ]
                    plt.scatter(
                        cluster_points_low[:, 0],
                        cluster_points_low[:, 1],
                        facecolors="cyan",
                        edgecolors="k",
                        s=30,
                        alpha=1.0,
                        label="Low cluster points",
                    )
                    plt.title(
                        f"Heatmap Overlay with Low Cluster {cluster} for score '{score_tag}'"
                    )
                    plt.legend()
                    overlay_path_low = (
                        output_folder
                        / f"kernel_heatmap_{score_tag}_cluster_{cluster}_low_overlay.png"
                    )
                    plt.savefig(overlay_path_low)
                    print(
                        f"Saved low overlay heatmap for score '{score_tag}' cluster '{cluster}' at {overlay_path_low}"
                    )
                    plt.close()

        # Gather uncertainty stats over the grid.
        grid_mean_uncertainty = float(np.mean(std_pred))
        grid_std_uncertainty = float(np.std(std_pred))

        # Save final results for this score tag.
        heatmap_dict[score_tag] = {
            "mean_heatmap": mean_heatmap,
            "std_heatmap": std_heatmap,
            "combined_heatmap": combined_heatmap,
            "grid_x": grid_x,
            "grid_y": grid_y,
            "models": models,
            "cv_performance": cv_perf,
            "effect_size": {"high": effect_size_maps_high, "low": effect_size_maps_low},
            "plot": plot_obj,
            "grid_mean_uncertainty": grid_mean_uncertainty,
            "grid_std_uncertainty": grid_std_uncertainty,
        }

    # Save aggregated CV performance.
    all_perf_df = pd.DataFrame(cv_performance_all)
    perf_path = output_folder / "cv_performance_metrics.csv"
    all_perf_df.to_csv(perf_path, index=False)
    print(f"Saved aggregated CV performance metrics to {perf_path}")

    return heatmap_dict, cv_performance_all


def optimize_gp_model(model, max_iter=300, verbose=True):
    """
    Optimizes GP model parameters with improved numerical stability.

    Parameters:
    -----------
    model : GPy.models.GPRegression
        The GP model to optimize.
    max_iter : int
        Maximum number of iterations for optimization.
    verbose : bool
        Whether to print optimization progress.

    Returns:
    --------
    model : GPy.models.GPRegression
        The optimized GP model.
    """
    # Set optimization parameters for better stability
    model.Gaussian_noise.variance.constrain_bounded(1e-6, 1.0, warning=False)

    # For numerical stability in the optimization
    try:
        # Use L-BFGS-B optimizer with careful parameterization
        model.optimize(
            optimizer="lbfgs",
            max_iters=max_iter,
            messages=verbose,
            ipython_notebook=False,
        )
    except Exception as e:
        if verbose:
            print(f"First optimization attempt failed: {e}")
        try:
            # Try with a more robust but slower optimizer
            model.optimize(
                optimizer="scg",
                max_iters=max_iter,
                messages=verbose,
                ipython_notebook=False,
            )
        except Exception as e:
            if verbose:
                print(f"Second optimization attempt failed: {e}")
            # Add small jitter to diagonal of the kernel matrix for numerical stability
            model.kern.add_jitter(1e-8)
            try:
                model.optimize_restarts(
                    num_restarts=5,
                    optimizer="lbfgs",
                    max_iters=max_iter // 2,
                    verbose=verbose,
                )
            except Exception:
                if verbose:
                    print(
                        "All optimization attempts failed. Using current model parameters."
                    )

    return model


def train_prediction_models(
    embeddings,
    targets,
    score_names,
    output_folder=None,
    sigma_values=None,
    random_state=42,
):
    """
    Train kernel regression models for each target score.

    Parameters:
    -----------
    embeddings : numpy.ndarray
        Feature embeddings to use for prediction (X)
    targets : numpy.ndarray
        Target scores array with each column representing a different score (y)
    score_names : list
        Names of the scores/targets
    output_folder : pathlib.Path or str, optional
        Path to save models if specified
    sigma_values : list or None, optional
        List of sigma values to try. If None, uses default range
    random_state : int, optional
        Random seed for reproducibility

    Returns:
    --------
    list
        List of trained KernelRegressor models for each score
    """
    if sigma_values is None:
        # Default sigma values to try
        sigma_values = [0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]

    models = []

    # Create output folder if it doesn't exist
    if output_folder is not None:
        os.makedirs(output_folder, exist_ok=True)

    # Train a model for each score
    for i, score_name in enumerate(score_names):
        print(f"Training model for {score_name}...")

        # Extract the target score
        y = targets[:, i]
        # Use nested cross-validation to find the best sigma and train models
        trained_models, performance_results, _, sigma_values_used = (
            nested_cv_kernel_regression(
                embeddings,
                y,
                sigma_values,
                n_outer=5,
                n_inner=3,
                random_state=random_state,
            )
        )

        # Use the ensemble of models
        models.append(trained_models)

        # Print performance summary
        r2_scores = [result["r2"] for result in performance_results]
        mse_scores = [result["mse"] for result in performance_results]

        print(f"  Mean R²: {np.mean(r2_scores):.3f} ± {np.std(r2_scores):.3f}")
        print(f"  Mean MSE: {np.mean(mse_scores):.3f} ± {np.std(mse_scores):.3f}")
        print(f"  Sigma values used: {sigma_values_used}")

    return models


def evaluate_models(models, embeddings, targets, score_names):
    """
    Evaluate trained kernel regression models on test data.

    Parameters:
    -----------
    models : list
        List of trained KernelRegressor models (or lists of models for ensembles)
    embeddings : numpy.ndarray
        Feature embeddings to use for prediction (X_test)
    targets : numpy.ndarray
        Target scores array with each column representing a different score (y_test)
    score_names : list
        Names of the scores/targets

    Returns:
    --------
    dict
        Dictionary of evaluation results for each score
    """
    results = {}

    for i, score_name in enumerate(score_names):
        # Extract the target score
        y_test = targets[:, i]

        # Check if we have a single model or an ensemble
        if isinstance(models[i], list):
            # For ensemble models
            mean_pred, std_pred = ensemble_predict(models[i], embeddings)

            # Calculate metrics
            mse = mean_squared_error(y_test, mean_pred)
            rmse = np.sqrt(mse)
            r2 = r2_score(y_test, mean_pred)

            results[score_name] = {
                "mse": mse,
                "rmse": rmse,
                "r2": r2,
                "predictions": mean_pred,
                "uncertainty": std_pred,
            }
        else:
            # For single models
            y_pred = models[i].predict(embeddings)

            # Calculate metrics
            mse = mean_squared_error(y_test, y_pred)
            rmse = np.sqrt(mse)
            r2 = r2_score(y_test, y_pred)

            results[score_name] = {
                "mse": mse,
                "rmse": rmse,
                "r2": r2,
                "predictions": y_pred,
            }

    return results


def is_classification_target(y):
    """
    Determine if a target variable indicates a classification task.

    Parameters:
    -----------
    y : array-like
        Target variable

    Returns:
    --------
    bool
        True if the target appears to be for a classification task,
        False if it appears to be for regression.
    """
    # Convert to numpy array
    y = np.asarray(y)

    # Skip if y is empty
    if len(y) == 0:
        return False

    # Check if y contains only integers
    all_integer = np.all(np.equal(np.mod(y, 1), 0))

    # Check if the number of unique values is small (typical for classification)
    n_unique = len(np.unique(y))
    small_n_unique = n_unique <= 10  # Arbitrary threshold

    # Check if the number of unique values is very small compared to the size
    # (heuristic: less than 5% of the data points are unique values)
    ratio_unique = n_unique / len(y)
    very_small_ratio = ratio_unique < 0.05 and n_unique > 1

    # Check if values are common classification targets (0, 1) or (1, 2, ...)
    binary_01 = set(np.unique(y)) == {0, 1}
    one_indexed = set(np.unique(y)) == set(range(1, n_unique + 1))
    zero_indexed = set(np.unique(y)) == set(range(0, n_unique))

    # Rule: If all values are integers, and either the number of unique values is small
    # or the values match common classification patterns, classify as classification
    return all_integer and (
        small_n_unique or binary_01 or one_indexed or zero_indexed or very_small_ratio
    )
