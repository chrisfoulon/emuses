# kernel_regression.py
from copy import deepcopy
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import pyplot as plt

# SciPy imports
from scipy.spatial import ConvexHull, cKDTree
from scipy.stats import normaltest
from scipy.spatial.distance import cdist

# Scikit-learn imports
from sklearn.base import BaseEstimator, RegressorMixin, ClassifierMixin
from sklearn.model_selection import KFold
from sklearn.metrics import (accuracy_score, roc_auc_score, r2_score, mean_squared_error, 
                            mean_absolute_error, confusion_matrix, f1_score, precision_score, 
                            recall_score, pairwise_distances)
from sklearn.decomposition import PCA

# EMUSES imports
from emuses.tools.output_utils import save_statistical_maps
from emuses.tools.stats_utils import input_matrix_stat_map
from emuses.tools.correlation_maps_utils import calculate_correlation_grid

# Other imports
import hdbscan
from joblib import dump, Parallel, delayed
import GPy
import os
import json
import time


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

    def __init__(self, sigma=1.0, kernel='gaussian'):
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
            if self.kernel == 'gaussian' or self.kernel is None:
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
    """

    def __init__(self, sigma=1.0):
        self.sigma = sigma

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
        probas : array of shape (n_test_samples,)
            Predicted probabilities for class 1.
        """
        X = np.asarray(X)
        probas = []
        for x in X:
            distances = np.linalg.norm(self.X_train - x, axis=1)
            weights = np.exp(-0.5 * (distances / self.sigma) ** 2)
            weight_sum = np.sum(weights)
            if weight_sum == 0:
                proba = 0.0  # or another fallback value
            else:
                proba = np.sum(weights * self.y_train) / weight_sum
            probas.append(proba)
        return np.array(probas)

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
            Predicted binary labels (0 or 1).
        """
        probas = self.predict_proba(X)
        # Threshold the probability at 0.5.
        return (probas >= 0.5).astype(int)


def nested_cv_kernel_regression(X, y, sigma_values, n_outer=5, n_inner=3, random_state=42):
    """
    Perform nested cross-validation for kernel regression.
    
    Parameters:
    -----------
    X : numpy.ndarray
        Feature embeddings
    y : numpy.ndarray
        Target score
    sigma_values : list
        List of sigma values to try
    n_outer : int
        Number of folds for outer CV
    n_inner : int
        Number of folds for inner CV
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
    inner_cv = KFold(n_splits=n_inner, shuffle=True, random_state=random_state+1)
    
    trained_models = []
    performance_results = []
    best_sigmas = []
    
    # Outer CV loop
    for train_idx, test_idx in outer_cv.split(X):
        X_train_outer, X_test_outer = X[train_idx], X[test_idx]
        y_train_outer, y_test_outer = y[train_idx], y[test_idx]
        
        # Inner CV to find best sigma
        best_sigma = None
        best_score = -np.inf
        
        for sigma in sigma_values:
            scores = []
            
            # Inner CV loop
            for inner_train_idx, inner_val_idx in inner_cv.split(X_train_outer):
                X_train_inner, X_val_inner = X_train_outer[inner_train_idx], X_train_outer[inner_val_idx]
                y_train_inner, y_val_inner = y_train_outer[inner_train_idx], y_train_outer[inner_val_idx]
                
                # Train model with current sigma
                model = KernelRegressor(sigma=sigma)
                model.fit(X_train_inner, y_train_inner)
                
                # Evaluate on validation set
                y_pred = model.predict(X_val_inner)
                score = r2_score(y_val_inner, y_pred)
                scores.append(score)
            
            # Average score for this sigma
            mean_score = np.mean(scores)
            
            if mean_score > best_score:
                best_score = mean_score
                best_sigma = sigma
        
        # Train model on full outer training set with best sigma
        best_sigmas.append(best_sigma)
        model = KernelRegressor(sigma=best_sigma)
        model.fit(X_train_outer, y_train_outer)
        trained_models.append(model)
        
        # Evaluate on outer test set
        y_pred = model.predict(X_test_outer)
        mse = mean_squared_error(y_test_outer, y_pred)
        rmse = np.sqrt(mse)
        r2 = r2_score(y_test_outer, y_pred)
        
        performance_results.append({
            'mse': mse,
            'rmse': rmse,
            'r2': r2
        })
    
    # Determine overall best sigma (most frequently chosen)
    best_sigma = max(set(best_sigmas), key=best_sigmas.count)
    
    return trained_models, performance_results, best_sigma, best_sigmas

def ensemble_predict(models, X):
    """
    Make predictions with an ensemble of models.
    
    Parameters:
    -----------
    models : list
        List of trained models
    X : numpy.ndarray
        Features to predict on
        
    Returns:
    --------
    numpy.ndarray
        Mean prediction
    numpy.ndarray
        Standard deviation of predictions (uncertainty)
    """
    predictions = np.array([model.predict(X) for model in models])
    
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
            - 'std_prediction': Standard deviation of predictions (as a list).
            Plus, if classification:
                - 'accuracy', 'confusion_matrix', 'roc_auc', 'f1_score', 'precision', 'recall'
            Otherwise (regression):
                - 'r2', 'mse', 'mae', 'normalized_mse_%', 'normalized_mae_%'
    """
    # Use the ensemble_predict function to get predictions and their standard deviation.
    mean_pred, std_pred = ensemble_predict(models, X_test)
    # Convert NumPy arrays to lists for JSON serialization.
    results = {
        'mean_prediction': mean_pred.tolist(),
        'std_prediction': std_pred.tolist()
    }

    if classification:
        # Convert probabilities to predictions (threshold=0.5)
        y_pred = (mean_pred >= 0.5).astype(int)
        results['accuracy'] = float(accuracy_score(y_test, y_pred))
        results['confusion_matrix'] = confusion_matrix(y_test, y_pred).tolist()
        try:
            results['roc_auc'] = float(roc_auc_score(y_test, mean_pred))
        except Exception:
            results['roc_auc'] = None

        # Determine the appropriate averaging method for multiclass vs binary.
        average_param = 'binary'
        if len(np.unique(y_test)) > 2:
            average_param = 'macro'

        results['f1_score'] = float(f1_score(y_test, y_pred, average=average_param))
        results['precision'] = float(precision_score(y_test, y_pred, average=average_param))
        results['recall'] = float(recall_score(y_test, y_pred, average=average_param))
    else:
        # Regression metrics
        from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
        results['r2'] = float(r2_score(y_test, mean_pred))
        results['mse'] = float(mean_squared_error(y_test, mean_pred))
        results['mae'] = float(mean_absolute_error(y_test, mean_pred))
        # Normalize errors based on the range of y_test (could also use training set range)
        target_range = np.max(y_test) - np.min(y_test)
        if target_range == 0:
            normalized_mse = None
            normalized_mae = None
        else:
            normalized_mse = (results['mse'] / (target_range ** 2)) * 100
            normalized_mae = (results['mae'] / target_range) * 100
        results['normalized_mse_%'] = normalized_mse
        results['normalized_mae_%'] = normalized_mae

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
    input_type='image',
    classification=False,
    cluster_labels=None,
    effect_size_test='mann-whitney',
    highlight_points=True,
    show_plots=False,
    generate_plots=False,
    output_format_info=None,
    full_embeddings=None,
    clusterer=None,
    cluster_predict_method="kdtree",
    random_state=42
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
        combined_embeddings = full_embeddings if full_embeddings is not None else embeddings

    min_coords = combined_embeddings.min(axis=0)
    max_coords = combined_embeddings.max(axis=0)
    grid_x = np.linspace(min_coords[0], max_coords[0], grid_size)
    grid_y = np.linspace(min_coords[1], max_coords[1], grid_size)
    grid_points = np.array(np.meshgrid(grid_x, grid_y)).T.reshape(-1, 2)

    # Determine which embeddings to plot: use the union in label_dataset mode.
    if full_embeddings is not None and embeddings is not None and not np.array_equal(full_embeddings, embeddings):
        plot_embeddings_array = np.concatenate([full_embeddings, embeddings], axis=0)
    else:
        plot_embeddings_array = full_embeddings if full_embeddings is not None else embeddings

    heatmap_dict = {}
    cv_performance_all = []

    for score_tag, y in scores_vectors_dict.items():
        print(f"Processing score tag: {score_tag}...")

        # --- NEW CODE: Filter out datapoints with NaN in the current score ---
        mask = ~np.isnan(y)
        num_ignored = len(y) - np.sum(mask)
        if num_ignored > 0:
            print(f"Warning: {num_ignored} datapoints have been ignored for score tag '{score_tag}' because "
                  f"they don't have a value.")
        y_filtered = y[mask]
        embeddings_filtered = embeddings[mask]
        if input_matrix is not None:
            if len(input_matrix) == len(y):
                input_matrix_filtered = input_matrix[mask]
            else:
                print("Input matrix length does not match the score vector length; skipping input_matrix filtering.")
                input_matrix_filtered = input_matrix
        else:
            input_matrix_filtered = input_matrix
        # --------------------------------------------------------------------

        # Call nested CV and obtain unseen predictions using filtered training data.
        models, cv_perf, unseen_preds_dict, _ = nested_cv_kernel_regression(
            embeddings_filtered, y_filtered, sigma_values=sigma_range, n_outer=5, n_inner=5, classification=classification
        )

        for perf in cv_perf:
            perf['score_tag'] = score_tag
        cv_performance_all.extend(cv_perf)
        print(f"Trained {len(models)} models for score tag '{score_tag}'.")

        pred_models_perf_folder = output_folder / "prediction_models" / "kernel_regression_perf"
        pred_models_perf_folder.mkdir(parents=True, exist_ok=True)

        perf_df = pd.DataFrame(cv_perf)
        perf_path = pred_models_perf_folder / f"cv_performance_metrics_{score_tag}.csv"
        perf_df.to_csv(perf_path, index=False)
        print(f"Saved CV performance metrics for score tag '{score_tag}' to {perf_path}")

        # Save ensemble models.
        pred_models_folder = output_folder / "prediction_models" / "kernel_regression"
        pred_models_folder.mkdir(parents=True, exist_ok=True)
        for i, model in enumerate(models):
            model_filename = pred_models_folder / f"kernel_model_{score_tag}_fold_{i}.joblib"
            dump(model, model_filename)
            print(f"Saved kernel regression model for fold {i} at {model_filename}")

        # Ensemble predict on grid.
        mean_pred, std_pred = ensemble_predict(models, grid_points)
        mean_heatmap = mean_pred.reshape(grid_size, grid_size)
        std_heatmap = std_pred.reshape(grid_size, grid_size)

        # Compute a combined heatmap.
        combined_heatmap = mean_heatmap - uncertainty_penalty * std_heatmap

        # Generate main heatmap plot if requested.
        plot_obj = None
        if generate_plots:
            plt.figure(figsize=(8, 6))
            # Display the combined heatmap
            plt.imshow(
                combined_heatmap.T,
                origin='lower',
                extent=(min_coords[0], max_coords[0], min_coords[1], max_coords[1]),
                cmap='viridis',
                aspect='auto'
            )
            plt.colorbar(label='Combined Confidence')
            plt.title(f'Kernel Regression Combined Heatmap for Score {score_tag}')
            if highlight_points:
                # Plot all embeddings in red (the union if label_dataset mode).
                plt.scatter(
                    plot_embeddings_array[:, 0],
                    plot_embeddings_array[:, 1],
                    color='red', s=10, alpha=0.5,
                    label='All embeddings'
                )
            plt.savefig(output_folder / f'kernel_heatmap_{score_tag}.png')
            print(f"Saved combined heatmap for score '{score_tag}'")
            plot_obj = plt.g
        if input_matrix is not None:
            if len(input_matrix) == len(y):
                input_matrix_filtered = input_matrix[mask]
            else:
                print("Input matrix length does not match the score vector length; skipping input_matrix filtering.")
                input_matrix_filtered = input_matrix
        else:
            input_matrix_filtered = input_matrix
        # --------------------------------------------------------------------

        # Call nested CV and obtain unseen predictions using filtered training data.
        models, cv_perf, unseen_preds_dict, _ = nested_cv_kernel_regression(
            embeddings_filtered, y_filtered, sigma_values=sigma_range, n_outer=5, n_inner=5, classification=classification
        )

        for perf in cv_perf:
            perf['score_tag'] = score_tag
        cv_performance_all.extend(cv_perf)
        print(f"Trained {len(models)} models for score tag '{score_tag}'.")

        pred_models_perf_folder = output_folder / "prediction_models" / "kernel_regression_perf"
        pred_models_perf_folder.mkdir(parents=True, exist_ok=True)

        perf_df = pd.DataFrame(cv_perf)
        perf_path = pred_models_perf_folder / f"cv_performance_metrics_{score_tag}.csv"
        perf_df.to_csv(perf_path, index=False)
        print(f"Saved CV performance metrics for score tag '{score_tag}' to {perf_path}")

        # Save ensemble models.
        pred_models_folder = output_folder / "prediction_models" / "kernel_regression"
        pred_models_folder.mkdir(parents=True, exist_ok=True)
        for i, model in enumerate(models):
            model_filename = pred_models_folder / f"kernel_model_{score_tag}_fold_{i}.joblib"
            dump(model, model_filename)
            print(f"Saved kernel regression model for fold {i} at {model_filename}")

        # Ensemble predict on grid.
        mean_pred, std_pred = ensemble_predict(models, grid_points)
        mean_heatmap = mean_pred.reshape(grid_size, grid_size)
        std_heatmap = std_pred.reshape(grid_size, grid_size)

        # Compute a combined heatmap.
        combined_heatmap = mean_heatmap - uncertainty_penalty * std_heatmap

        # Generate main heatmap plot if requested.
        plot_obj = None
        if generate_plots:
            plt.figure(figsize=(8, 6))
            # Display the combined heatmap
            plt.imshow(
                combined_heatmap.T,
                origin='lower',
                extent=(min_coords[0], max_coords[0], min_coords[1], max_coords[1]),
                cmap='viridis',
                aspect='auto'
            )
            plt.colorbar(label='Combined Confidence')
            plt.title(f'Kernel Regression Combined Heatmap for Score {score_tag}')
            if highlight_points:
                # Plot all embeddings in red (the union if label_dataset mode).
                plt.scatter(
                    plot_embeddings_array[:, 0],
                    plot_embeddings_array[:, 1],
                    color='red', s=10, alpha=0.5,
                    label='All embeddings'
                )
            plt.savefig(output_folder / f'kernel_heatmap_{score_tag}.png')
            print(f"Saved combined heatmap for score '{score_tag}'")
            plot_obj = plt.gcf()
            plt.close()

        # Compute dynamic thresholds.
        all_unseen_preds = np.concatenate([pred for (_, pred) in unseen_preds_dict.values()])
        if not classification:
            # For regression: normality test to pick dynamic threshold
            stat_val, pvalue = normaltest(all_unseen_preds)
            if pvalue > 0.05:
                dynamic_threshold_high = np.mean(all_unseen_preds) + 2 * np.std(all_unseen_preds)
                dynamic_threshold_low = np.mean(all_unseen_preds) - 2 * np.std(all_unseen_preds)
            else:
                dynamic_threshold_high = np.percentile(all_unseen_preds, 95)
                dynamic_threshold_low = np.percentile(all_unseen_preds, 5)
            print(f"Dynamic thresholds for regression: high = {dynamic_threshold_high:.3f}, low = {dynamic_threshold_low:.3f} (normality p={pvalue:.3f})")
        else:
            dynamic_threshold_high = threshold
            dynamic_threshold_low = None

        # Use combined embeddings for full prediction if available.
        if full_embeddings is not None and not np.array_equal(full_embeddings, embeddings):
            full_pred, _ = ensemble_predict(models, combined_embeddings)
        else:
            full_pred, _ = ensemble_predict(models, embeddings)

        # Identify high and low prediction indices.
        high_pred_indices = np.where(full_pred > dynamic_threshold_high)[0]
        if dynamic_threshold_low is not None:
            low_pred_indices = np.where(full_pred < dynamic_threshold_low)[0]
        else:
            low_pred_indices = np.array([])

        # Process high-confidence points.
        effect_size_maps_high = {}
        if len(high_pred_indices) < 3:
            print(f"Not enough high-confidence points for score tag '{score_tag}' (n={len(high_pred_indices)}); skipping high effect size maps.")
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
                cluster_mask = (cluster_labels[high_pred_indices] == cluster)
                cluster_high_indices = high_pred_indices[cluster_mask]
                if len(cluster_high_indices) < 3:
                    print(f"Cluster {cluster} for score tag '{score_tag}' has fewer than 3 high-confidence points; skipping.")
                    continue

                print(f"Computing effect size map for high cluster {cluster} and score tag '{score_tag}'...")
                _, _, effect_size_map = input_matrix_stat_map(
                    input_matrix_filtered, cluster_high_indices, test_name=effect_size_test, n_cores=-1
                )
                effect_size_maps_high[cluster] = effect_size_map
                stat_maps_to_save = {cluster: effect_size_map}
                save_statistical_maps(
                    stat_maps=stat_maps_to_save,
                    output_folder=output_folder,
                    input_type=input_type,
                    output_format_info=output_format_info,
                    filename_prefix=f'effect_size_map_{score_tag}_cluster_{cluster}_high',
                    save_output=True,
                    generate_plots=generate_plots
                )
                print(f"Effect size map for high cluster {cluster} saved.")

                # Plot overlay for high cluster.
                plt.figure(figsize=(8, 6))
                # Display the combined heatmap as the background.
                plt.imshow(
                    combined_heatmap.T,
                    origin='lower',
                    extent=(min_coords[0], max_coords[0], min_coords[1], max_coords[1]),
                    cmap='viridis',
                    aspect='auto'
                )
                plt.colorbar(label='Combined Confidence')
                # Plot all embeddings (e.g., in red)
                plt.scatter(
                    plot_embeddings_array[:, 0],
                    plot_embeddings_array[:, 1],
                    color='red', s=10, alpha=0.5,
                    label='All embeddings'
                )
                # Plot only the significant points for the current cluster (e.g., in green)
                cluster_points = combined_embeddings[high_pred_indices][cluster_mask]
                plt.scatter(
                    cluster_points[:, 0],
                    cluster_points[:, 1],
                    facecolors='lime', edgecolors='k', s=30, alpha=1.0,
                    label='High cluster points'
                )
                plt.title(f"Heatmap Overlay with High Cluster {cluster} for score '{score_tag}'")
                plt.legend()
                overlay_path = output_folder / f"kernel_heatmap_{score_tag}_cluster_{cluster}_high_overlay.png"
                plt.savefig(overlay_path)
                print(f"Saved high overlay heatmap for score '{score_tag}' cluster '{cluster}' at {overlay_path}")
                plt.close()

                # Cluster-specific plot using the selected method.
                if cluster_predict_method == "fit_predict":
                    if clusterer is None:
                        raise ValueError("clusterer must be provided for fit_predict method.")
                    clusterer_copy = deepcopy(clusterer)
                    # Use combined_embeddings for re-clustering on the union.
                    combined_for_clustering = np.concatenate([combined_embeddings, grid_points], axis=0)
                    combined_labels = clusterer_copy.fit_predict(combined_for_clustering)
                    grid_pred = combined_labels[combined_embeddings.shape[0]:]
                elif cluster_predict_method == "approximate":
                    try:
                        grid_pred, _ = hdbscan.approximate_predict(clusterer, grid_points)
                    except Exception as e:
                        print(f"approximate_predict failed: {e}. Falling back to KDTree assignment.")
                        tree = cKDTree(combined_embeddings)
                        dist, idx = tree.query(grid_points, k=1)
                        grid_pred = cluster_labels[idx]
                elif cluster_predict_method == "kdtree":
                    tree = cKDTree(combined_embeddings)
                    dist, idx = tree.query(grid_points, k=1)
                    grid_pred = cluster_labels[idx]
                else:
                    raise ValueError(f"Unknown cluster_predict_method: {cluster_predict_method}")

                grid_mask = (grid_pred == cluster) & (combined_heatmap.flatten() > dynamic_threshold_high)
                grid_significant_points = grid_points[grid_mask]

                if len(grid_significant_points) >= 3 and generate_plots:
                    plt.figure(figsize=(8, 6))
                    # Display the combined heatmap as background.
                    plt.imshow(
                        combined_heatmap.T,
                        origin='lower',
                        extent=(min_coords[0], max_coords[0], min_coords[1], max_coords[1]),
                        cmap='viridis',
                        aspect='auto'
                    )
                    plt.colorbar(label='Combined Confidence')
                    # Plot the union of embeddings (both full and labelled) in red.
                    plt.scatter(
                        plot_embeddings_array[:, 0],
                        plot_embeddings_array[:, 1],
                        color='red', s=10, alpha=0.5,
                        label='All embeddings'
                    )
                    # Plot the high-confidence training points for this cluster (from embeddings).
                    train_sig_mask = (cluster_labels[high_pred_indices] == cluster)
                    # Use combined_embeddings for the training points as well.
                    train_significant_points = combined_embeddings[high_pred_indices][train_sig_mask]
                    plt.scatter(
                        train_significant_points[:, 0],
                        train_significant_points[:, 1],
                        facecolors='lime', edgecolors='k', s=30, alpha=1.0,
                        label='Significant points'
                    )
                    # Compute convex hull on the grid significant points.
                    try:
                        hull = ConvexHull(grid_significant_points)
                        hull_points = grid_significant_points[hull.vertices]
                        hull_points = np.concatenate([hull_points, hull_points[:1]], axis=0)
                        plt.plot(
                            hull_points[:, 0],
                            hull_points[:, 1],
                            'w--', lw=3,
                            label='Significant Zone Boundary'
                        )
                    except Exception as e:
                        print(f"Could not compute convex hull for cluster {cluster} on grid: {e}")

                    plt.title(f'Significant Zone for Score {score_tag} - Cluster {cluster}')
                    plt.legend()
                    cluster_out_path = output_folder / f'kernel_heatmap_{score_tag}_cluster_{cluster}_significant_zone.png'
                    plt.savefig(cluster_out_path)
                    print(f"Saved significant zone plot for score '{score_tag}' cluster '{cluster}' at {cluster_out_path}")
                    plt.close()

        # === Low-confidence branch (only for regression mode) ===
        effect_size_maps_low = {}
        if not classification:
            if len(low_pred_indices) < 3:
                print(f"Not enough low-confidence points for score tag '{score_tag}' (n={len(low_pred_indices)}); skipping low effect size maps.")
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
                    cluster_mask = (cluster_labels[low_pred_indices] == cluster)
                    cluster_low_indices = low_pred_indices[cluster_mask]
                    if len(cluster_low_indices) < 3:
                        print(f"Cluster {cluster} for score tag '{score_tag}' has fewer than 3 low-confidence points; skipping.")
                        continue
                    print(f"Computing effect size map for low cluster {cluster} and score tag '{score_tag}'...")
                    _, _, effect_size_map_low = input_matrix_stat_map(
                        input_matrix_filtered, cluster_low_indices, test_name=effect_size_test, n_cores=-1
                    )
                    effect_size_maps_low[cluster] = effect_size_map_low
                    stat_maps_to_save_low = {cluster: effect_size_map_low}
                    save_statistical_maps(
                        stat_maps=stat_maps_to_save_low,
                        output_folder=output_folder,
                        input_type=input_type,
                        output_format_info=output_format_info,
                        filename_prefix=f'effect_size_map_{score_tag}_cluster_{cluster}_low',
                        save_output=True,
                        generate_plots=generate_plots
                    )
                    print(f"Effect size map for low cluster {cluster} saved.")

                    # Plot overlay for low cluster.
                    plt.figure(figsize=(8, 6))
                    plt.imshow(
                        combined_heatmap.T,
                        origin='lower',
                        extent=(min_coords[0], max_coords[0], min_coords[1], max_coords[1]),
                        cmap='viridis',
                        aspect='auto'
                    )
                    plt.colorbar(label='Combined Confidence')
                    plt.scatter(
                        plot_embeddings_array[:, 0],
                        plot_embeddings_array[:, 1],
                        color='red', s=10, alpha=0.5,
                        label='All embeddings'
                    )
                    cluster_points_low = combined_embeddings[low_pred_indices][cluster_mask]
                    plt.scatter(
                        cluster_points_low[:, 0],
                        cluster_points_low[:, 1],
                        facecolors='cyan', edgecolors='k', s=30, alpha=1.0,
                        label='Low cluster points'
                    )
                    plt.title(f"Heatmap Overlay with Low Cluster {cluster} for score '{score_tag}'")
                    plt.legend()
                    overlay_path_low = output_folder / f"kernel_heatmap_{score_tag}_cluster_{cluster}_low_overlay.png"
                    plt.savefig(overlay_path_low)
                    print(f"Saved low overlay heatmap for score '{score_tag}' cluster '{cluster}' at {overlay_path_low}")
                    plt.close()

        # Gather uncertainty stats over the grid.
        grid_mean_uncertainty = float(np.mean(std_pred))
        grid_std_uncertainty = float(np.std(std_pred))

        # Save final results for this score tag.
        heatmap_dict[score_tag] = {
            'mean_heatmap': mean_heatmap,
            'std_heatmap': std_heatmap,
            'combined_heatmap': combined_heatmap,
            'grid_x': grid_x,
            'grid_y': grid_y,
            'models': models,
            'cv_performance': cv_perf,
            'effect_size': {
                'high': effect_size_maps_high,
                'low': effect_size_maps_low
            },
            'plot': plot_obj,
            'grid_mean_uncertainty': grid_mean_uncertainty,
            'grid_std_uncertainty': grid_std_uncertainty
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
        model.optimize(optimizer='lbfgs', 
                       max_iters=max_iter, 
                       messages=verbose,
                       ipython_notebook=False)
    except Exception as e:
        if verbose:
            print(f"First optimization attempt failed: {e}")
        try:
            # Try with a more robust but slower optimizer
            model.optimize(optimizer='scg', 
                           max_iters=max_iter,
                           messages=verbose,
                           ipython_notebook=False)
        except Exception as e:
            if verbose:
                print(f"Second optimization attempt failed: {e}")
            # Add small jitter to diagonal of the kernel matrix for numerical stability
            model.kern.add_jitter(1e-8)
            try:
                model.optimize_restarts(num_restarts=5, 
                                       optimizer='lbfgs',
                                       max_iters=max_iter//2,
                                       verbose=verbose)
            except:
                if verbose:
                    print("All optimization attempts failed. Using current model parameters.")
    
    return model


def train_prediction_models(embeddings, targets, score_names, output_folder=None, sigma_values=None, random_state=42):
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
        trained_models, performance_results, _, sigma_values_used = nested_cv_kernel_regression(
            embeddings, y, sigma_values, n_outer=5, n_inner=3, random_state=random_state
        )
        
        # Use the ensemble of models
        models.append(trained_models)
        
        # Print performance summary
        r2_scores = [result['r2'] for result in performance_results]
        mse_scores = [result['mse'] for result in performance_results]
        
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
                'mse': mse,
                'rmse': rmse,
                'r2': r2,
                'predictions': mean_pred,
                'uncertainty': std_pred
            }
        else:
            # For single models
            y_pred = models[i].predict(embeddings)
            
            # Calculate metrics
            mse = mean_squared_error(y_test, y_pred)
            rmse = np.sqrt(mse)
            r2 = r2_score(y_test, y_pred)
            
            results[score_name] = {
                'mse': mse,
                'rmse': rmse,
                'r2': r2,
                'predictions': y_pred
            }
    
    return results
