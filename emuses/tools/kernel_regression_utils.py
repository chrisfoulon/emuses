# kernel_regression.py
from pathlib import Path

import pandas as pd
from joblib import dump
from scipy.stats import normaltest
import numpy as np
from matplotlib import pyplot as plt
from sklearn.base import BaseEstimator, RegressorMixin, ClassifierMixin
from sklearn.model_selection import KFold
from sklearn.metrics import (accuracy_score, roc_auc_score, r2_score, mean_squared_error,
                             mean_absolute_error)

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
    """

    def __init__(self, sigma=1.0):
        self.sigma = sigma

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
            # Compute Euclidean distances from x to each training sample.
            distances = np.linalg.norm(self.X_train - x, axis=1)
            # Compute Gaussian kernel weights.
            weights = np.exp(-0.5 * (distances / self.sigma) ** 2)
            # Compute weighted average.
            prediction = np.sum(weights * self.y_train) / np.sum(weights)
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
            proba = np.sum(weights * self.y_train) / np.sum(weights)
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


def nested_cv_kernel_regression(X, y, sigma_values, n_outer=5, n_inner=5, classification=False):
    """
    Perform nested cross-validation to select the best kernel bandwidth (sigma) for kernel regression (or classification).

    The inner loop evaluates candidate sigma values using cross-validation on the outer training set.
    The best sigma is then used to train a model on the full outer training fold, and this process is repeated
    for each outer fold. The ensemble of outer models can then be used to make predictions.

    If return_performance is True, the function also computes performance measures on the outer test folds
    (using only unseen data) and returns these along with the trained models.

    Parameters
    ----------
    X : array-like of shape (n_samples, n_features)
        Input data.
    y : array-like of shape (n_samples,)
        Target values (continuous for regression or binary 0/1 for classification).
    sigma_values : list of float
        Candidate sigma (bandwidth) values to evaluate.
    n_outer : int, default=5
        Number of outer cross-validation folds.
    n_inner : int, default=5
        Number of inner cross-validation folds for hyperparameter tuning.
    classification : bool, default=False
        If True, uses KernelLogisticRegressor; otherwise, uses KernelRegressor.

    Returns
    -------
    outer_models : list
        List of models trained on each outer fold with the best sigma determined from the inner CV.
    performance_results : list (if return_performance is True)
        A list of dictionaries, one per outer fold, with performance measures.
        For classification: accuracy and roc_auc (if available).
        For regression: r2, mse, mae, normalized_mse_% and normalized_mae_%.
    """
    outer_kf = KFold(n_splits=n_outer, shuffle=True)
    outer_models = []
    performance_results = []
    fold_index = 0

    for train_index, test_index in outer_kf.split(X):
        X_train_outer, X_test_outer = X[train_index], X[test_index]
        y_train_outer, y_test_outer = y[train_index], y[test_index]

        # Inner CV to select best sigma
        inner_kf = KFold(n_splits=n_inner, shuffle=True)
        best_sigma = None
        best_score = -np.inf

        for sigma in sigma_values:
            inner_scores = []
            for inner_train_idx, inner_val_idx in inner_kf.split(X_train_outer):
                X_train_inner, X_val_inner = X_train_outer[inner_train_idx], X_train_outer[inner_val_idx]
                y_train_inner, y_val_inner = y_train_outer[inner_train_idx], y_train_outer[inner_val_idx]

                if classification:
                    model = KernelLogisticRegressor(sigma=sigma)
                    model.fit(X_train_inner, y_train_inner)
                    y_pred_inner = model.predict(X_val_inner)
                    score = accuracy_score(y_val_inner, y_pred_inner)
                else:
                    model = KernelRegressor(sigma=sigma)
                    model.fit(X_train_inner, y_train_inner)
                    y_pred_inner = model.predict(X_val_inner)
                    score = r2_score(y_val_inner, y_pred_inner)
                inner_scores.append(score)
            avg_score = np.mean(inner_scores)
            if avg_score > best_score:
                best_score = avg_score
                best_sigma = sigma

        # Train final model on outer training set with the best sigma from inner CV
        if classification:
            final_model = KernelLogisticRegressor(sigma=best_sigma)
        else:
            final_model = KernelRegressor(sigma=best_sigma)
        final_model.fit(X_train_outer, y_train_outer)
        outer_models.append(final_model)

        # Evaluate performance on the unseen outer test fold.
        if classification:
            y_pred_outer = final_model.predict(X_test_outer)
            acc = accuracy_score(y_test_outer, y_pred_outer)
            try:
                proba = final_model.predict_proba(X_test_outer)
                roc_auc = roc_auc_score(y_test_outer, proba)
            except Exception as e:
                roc_auc = None
            performance_results.append({
                'fold': fold_index,
                'accuracy': acc,
                'roc_auc': roc_auc
            })
        else:
            y_pred_outer = final_model.predict(X_test_outer)
            r2 = r2_score(y_test_outer, y_pred_outer)
            mse = mean_squared_error(y_test_outer, y_pred_outer)
            mae = mean_absolute_error(y_test_outer, y_pred_outer)
            target_range = np.max(y_train_outer) - np.min(y_train_outer)
            normalized_mse = (mse / (target_range ** 2)) * 100 if target_range != 0 else mse
            normalized_mae = (mae / target_range) * 100 if target_range != 0 else mae
            performance_results.append({
                'fold': fold_index,
                'r2': r2,
                'mse': mse,
                'mae': mae,
                'normalized_mse_%': normalized_mse,
                'normalized_mae_%': normalized_mae
            })
        fold_index += 1
    return outer_models, performance_results


def ensemble_predict(models, X):
    """
    Predict outcomes using an ensemble of kernel regression models.

    For regression, returns the mean prediction and the standard deviation across models.
    For classification, returns the mean predicted probability for class 1 and its standard deviation.

    Parameters
    ----------
    models : list
        List of trained kernel regression (or logistic regression) models.
    X : array-like of shape (n_samples, n_features)
        Test data.

    Returns
    -------
    mean_prediction : np.array of shape (n_samples,)
        Mean prediction (or probability) across models.
    std_prediction : np.array of shape (n_samples,)
        Standard deviation of predictions across models.
    """
    predictions = []
    for model in models:
        # For logistic regressor, use predict_proba if available.
        if hasattr(model, "predict_proba"):
            pred = model.predict_proba(X)
        else:
            pred = model.predict(X)
        predictions.append(pred)
    predictions = np.array(predictions)
    mean_prediction = predictions.mean(axis=0)
    std_prediction = predictions.std(axis=0)
    return mean_prediction, std_prediction


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
):
    """
    Generate a kernel regression–based heatmap of predicted outcomes.

    For each score tag in `scores_vectors_dict`, the function:
      1. Uses nested cross‑validation to train an ensemble of kernel regressors:
         (if `classification` is True, uses a kernel logistic regressor; otherwise, uses a kernel regressor).
      2. Saves the resulting models in a subfolder "prediction_models/kernel_regression" within the output folder.
      3. Computes predictions (i.e. estimated probabilities for classification or continuous outcomes for regression)
         at each point on a grid spanning the latent space.
      4. Computes the standard deviation of predictions across the ensemble.
      5. Forms a combined heatmap by subtracting (uncertainty_penalty × std) from the mean prediction.
      6. Optionally computes effect size maps for high-confidence points.
         For continuous targets, the threshold is determined dynamically using a normality test on the training predictions:
           - If the predictions are normally distributed (p > 0.05), the threshold is set at mean + 2*std.
           - Otherwise, the 95th percentile is used.
         (For classification the provided threshold is used.)
      7. Additionally, computes uncertainty measures (mean and std of the ensemble’s prediction standard deviations) on the grid.
      8. Returns both the heatmap dictionary and the CV performance results from the nested CV.

    Parameters
    ----------
    embeddings : np.ndarray
        A 2D array of shape (n_samples, 2) representing the latent space coordinates.
    scores_vectors_dict : dict
        Dictionary mapping each score tag (str) to a target score vector (binary or continuous) for each sample.
    input_matrix : np.ndarray
        The original input data matrix used for effect size analysis; each row corresponds to a sample.
    output_folder : str or Path
        Path to the directory where output heatmaps, effect size maps, and plots will be saved.
    grid_size : int, default=100
        The resolution of the grid for heatmap prediction; the grid will be grid_size x grid_size.
    sigma_range : array-like, optional
        Range of sigma values to use for kernel regression. If None, defaults to np.linspace(0.01, 0.2, num=8).
    threshold : float, default=0.5
        Threshold to determine high-confidence predictions; only used for classification.
    uncertainty_penalty : float, default=0.5
        Multiplier to penalize regions with high ensemble prediction uncertainty.
    input_type : str, default='image'
        The type of input data used for effect size analysis (e.g., 'image', 'nifti', 'spreadsheet').
    classification : bool, default=False
        If True, uses a kernel logistic regressor; otherwise, uses a kernel regressor.
    cluster_labels : np.ndarray, optional
        Array of cluster labels corresponding to the embeddings; used to compute effect size maps for each cluster.
    effect_size_test : str, default='mann-whitney'
        The statistical test to use for computing effect size maps.
    highlight_points : bool, default=True
        If True, the original embedding points will be highlighted on the heatmap plots.
    show_plots : bool, default=False
        If True, displays the heatmap plots interactively.
    generate_plots : bool, default=False
        If True, generates and saves plots of the combined heatmap and effect size maps.
    output_format_info : any, optional
        Additional info required for formatting the output (e.g., affine matrix, target shape, or column names).

    Returns
    -------
    heatmap_dict : dict
        Dictionary mapping each score tag to a dictionary with keys:
          'mean_heatmap': np.ndarray (grid_size x grid_size)
          'std_heatmap': np.ndarray (grid_size x grid_size)
          'combined_heatmap': np.ndarray (grid_size x grid_size)
          'grid_x': np.ndarray
          'grid_y': np.ndarray
          'models': list of CV-trained models
          'cv_performance': list of performance dictionaries from outer CV folds
          'effect_size': dict mapping cluster labels to effect size maps
          'plot': matplotlib Figure or None
          'grid_mean_uncertainty': float, mean uncertainty over grid predictions
          'grid_std_uncertainty': float, standard deviation of grid uncertainties
    cv_performance_all : list
        Aggregated list of performance results across all score tags.
    """
    if sigma_range is None:
        sigma_range = np.linspace(0.01, 0.2, num=8)

    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    # Create grid over latent space (assumes 2D embeddings)
    min_coords = embeddings.min(axis=0)
    max_coords = embeddings.max(axis=0)
    grid_x = np.linspace(min_coords[0], max_coords[0], grid_size)
    grid_y = np.linspace(min_coords[1], max_coords[1], grid_size)
    grid_points = np.array(np.meshgrid(grid_x, grid_y)).T.reshape(-1, 2)

    heatmap_dict = {}
    cv_performance_all = []

    for score_tag, y in scores_vectors_dict.items():
        print(f"Processing score tag: {score_tag}...")
        # Run nested CV to get models and their performance on unseen outer folds.
        models, cv_perf = nested_cv_kernel_regression(
            embeddings, y, sigma_values=sigma_range, n_outer=5, n_inner=5, classification=classification
        )
        for perf in cv_perf:
            perf['score_tag'] = score_tag
        cv_performance_all.extend(cv_perf)
        print(f"Trained {len(models)} models for score tag '{score_tag}'.")

        # Save kernel regression models in prediction_models/kernel_regression subfolder.
        pred_models_folder = output_folder / "prediction_models" / "kernel_regression"
        pred_models_folder.mkdir(parents=True, exist_ok=True)
        for i, model in enumerate(models):
            model_filename = pred_models_folder / f"kernel_model_{score_tag}_fold_{i}.joblib"
            dump(model, model_filename)
            print(f"Saved kernel regression model for fold {i} at {model_filename}")

        # Ensemble predict on the grid.
        mean_pred, std_pred = ensemble_predict(models, grid_points)
        mean_heatmap = mean_pred.reshape(grid_size, grid_size)
        std_heatmap = std_pred.reshape(grid_size, grid_size)

        # Compute a combined heatmap.
        combined_heatmap = mean_heatmap - uncertainty_penalty * std_heatmap

        # Optionally, generate a plot.
        plot_obj = None
        if generate_plots:
            plt.figure(figsize=(8, 6))
            plt.imshow(combined_heatmap.T, origin='lower',
                       extent=(min_coords[0], max_coords[0], min_coords[1], max_coords[1]),
                       cmap='viridis', aspect='auto')
            plt.colorbar(label='Combined Confidence')
            plt.title(f'Kernel Regression Combined Heatmap for Score {score_tag}')
            if highlight_points:
                plt.scatter(embeddings[:, 0], embeddings[:, 1], color='red', s=10, alpha=0.5)
            if show_plots:
                plt.show()
            plot_obj = plt.gcf()
            out_path = output_folder / f'kernel_heatmap_{score_tag}.png'
            plt.savefig(out_path)
            print(f"Saved combined heatmap for score '{score_tag}' at {out_path}")
            plt.close()

        # Compute ensemble predictions on the training embeddings for thresholding.
        train_pred_mean, _ = ensemble_predict(models, embeddings)

        # Determine dynamic threshold for continuous targets using a normality test.
        if not classification:
            stat_val, pvalue = normaltest(train_pred_mean)
            if pvalue > 0.05:
                dynamic_threshold = np.mean(train_pred_mean) + 2 * np.std(train_pred_mean)
            else:
                dynamic_threshold = np.percentile(train_pred_mean, 95)
            print(f"Dynamic threshold for high-confidence points: {dynamic_threshold:.3f} (normality p={pvalue:.3f})")
        else:
            dynamic_threshold = threshold

        high_pred_indices = np.where(train_pred_mean > dynamic_threshold)[0]
        if len(high_pred_indices) < 3:
            print(f"Not enough high-confidence points for score tag '{score_tag}' (n={len(high_pred_indices)}); skipping effect size maps.")
            effect_size_maps = {}
        else:
            high_clusters = cluster_labels[high_pred_indices] if cluster_labels is not None else None
            if high_clusters is not None:
                unique_clusters = np.unique(high_clusters)
            else:
                unique_clusters = []
            effect_size_maps = {}
            for cluster in unique_clusters:
                if cluster == -1:
                    continue
                cluster_high_indices = high_pred_indices[high_clusters == cluster]
                if len(cluster_high_indices) < 3:
                    print(f"Cluster {cluster} for score tag '{score_tag}' has fewer than 3 high-confidence points; skipping.")
                    continue
                print(f"Computing effect size map for cluster {cluster} and score tag '{score_tag}'...")
                _, _, effect_size_map = input_matrix_stat_map(
                    input_matrix, cluster_high_indices, test_name=effect_size_test, n_cores=-1
                )
                effect_size_maps[cluster] = effect_size_map
                stat_maps_to_save = {cluster: effect_size_map}
                save_statistical_maps(
                    stat_maps=stat_maps_to_save,
                    output_folder=output_folder,
                    input_type=input_type,
                    output_format_info=output_format_info,
                    filename_prefix=f'effect_size_map_{score_tag}_cluster_{cluster}',
                    save_output=True,
                    generate_plots=generate_plots
                )
                print(f"Effect size map for cluster {cluster} saved.")

        # Compute uncertainty measures on the grid predictions.
        grid_mean_uncertainty = np.mean(std_pred)
        grid_std_uncertainty = np.std(std_pred)

        heatmap_dict[score_tag] = {
            'mean_heatmap': mean_heatmap,
            'std_heatmap': std_heatmap,
            'combined_heatmap': combined_heatmap,
            'grid_x': grid_x,
            'grid_y': grid_y,
            'models': models,
            'cv_performance': cv_perf,
            'effect_size': effect_size_maps,
            'plot': plot_obj,
            'grid_mean_uncertainty': grid_mean_uncertainty,
            'grid_std_uncertainty': grid_std_uncertainty
        }

    # Save aggregated CV performance metrics across score tags.
    all_perf_df = pd.DataFrame(cv_performance_all)
    perf_path = output_folder / "cv_performance_metrics.csv"
    all_perf_df.to_csv(perf_path, index=False)
    print(f"Saved aggregated CV performance metrics to {perf_path}")

    return heatmap_dict, cv_performance_all

