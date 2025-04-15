import os
import time
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pickle
import optuna
from multiprocessing import Pool, cpu_count
from pathlib import Path
from bcblib.tools.arrays_utils import separate_clusters_and_extract_coords, find_centroid_and_check
from narwhals.selectors import categorical
from scipy.stats import mannwhitneyu, ttest_ind, mode, entropy
from sklearn.linear_model import LinearRegression
from tqdm import tqdm
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, GradientBoostingRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, Matern, WhiteKernel, RationalQuadratic
from sklearn.metrics import (mean_squared_error, mean_absolute_error, r2_score, confusion_matrix, 
                            accuracy_score, pairwise_distances, f1_score, precision_score, 
                            recall_score)
from sklearn.model_selection import KFold, GridSearchCV, cross_val_score
from pykrige.rk import Krige
from joblib import dump, Parallel, delayed
import GPy
import xgboost as xgb
import seaborn as sns


def fwhm_to_sigma(fwhm):
    """
    Convert Full Width at Half Maximum (FWHM) to sigma (standard deviation) of a Gaussian.

    Parameters:
        fwhm (float): The FWHM value.

    Returns:
        float: The corresponding sigma value.
    """
    return fwhm / (2 * np.sqrt(2 * np.log(2)))


def sigma_to_fwhm(sigma):
    """
    Convert sigma (standard deviation) of a Gaussian to Full Width at Half Maximum (FWHM).

    Parameters:
        sigma (float): The sigma value.

    Returns:
        float: The corresponding FWHM value.
    """
    return sigma * 2 * np.sqrt(2 * np.log(2))


def process_column(args):
    filtered_data, other_data, test_name, i = args
    try:
        # Check if one of the vectors is too short or all zeros.
        if len(filtered_data) < 3 or len(other_data) < 3 or np.all(filtered_data == 0) or np.all(other_data == 0):
            return i, np.nan, np.nan, np.nan

        if test_name == 'mann-whitney':
            # Using method='asymptotic' can sometimes help avoid tie issues.
            stat, pval = mannwhitneyu(filtered_data, other_data, method='asymptotic')
            # Compute a z-score conversion (if desired)
            n1 = len(filtered_data)
            n2 = len(other_data)
            mu_u = n1 * n2 / 2
            sigma_u = np.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
            z = (stat - mu_u) / sigma_u if sigma_u != 0 else np.nan
            r = z / np.sqrt(n1 + n2) if (n1+n2) != 0 else np.nan
            return i, z, pval, r

        elif test_name == 't-test':
            stat, pval = ttest_ind(filtered_data, other_data, equal_var=False)
            n1 = len(filtered_data)
            n2 = len(other_data)
            mean1, mean2 = np.mean(filtered_data), np.mean(other_data)
            std1, std2 = np.std(filtered_data, ddof=1), np.std(other_data, ddof=1)
            pooled_std = np.sqrt(((n1 - 1)*std1**2 + (n2 - 1)*std2**2) / (n1+n2-2)) if (n1+n2-2) != 0 else np.nan
            cohen_d = (mean1 - mean2) / pooled_std if pooled_std != 0 else np.nan
            return i, stat, pval, cohen_d

    except Exception as e:
        # Log the error if desired, then return NaN values for this column.
        print(f"Error processing column {i}: {e}")
        return i, np.nan, np.nan, np.nan


def input_matrix_stat_map(input_matrix, indices, test_name='mann-whitney', n_cores=-1):
    """
    Compute the statistical test for each element of the vectors in the input matrix filtered with indices
    with the corresponding element in the other vectors of the input matrix.
    Return the stat map, the p-val map, and the effect size map.
    The test is performed using the test_name parameter.

    Parameters
    ----------
    input_matrix : np.ndarray
        The input matrix where each row is a flattened input.
    indices : list or np.ndarray
        The indices of the columns to be tested against all other columns.
    test_name : str, optional
        The name of the statistical test to be performed. Options are 'mann-whitney' and 't-test'.
        Default is 'mann-whitney'.
    n_cores : int, optional
        The number of CPU cores to use for parallel processing. Default is -1 (use all available cores minus one).

    Returns
    -------
    stat_map : np.ndarray
        The map of the statistic values for each row.
    pval_map : np.ndarray
        The map of the p-value for each row.
    effect_size_map : np.ndarray
        The map of the effect size values for each row.
    """
    if n_cores == -1:
        n_cores = max(1, cpu_count() - 1)

    # Initialize the stat, p-value, and effect size maps
    stat_map = np.zeros(input_matrix.shape[1])
    pval_map = np.zeros(input_matrix.shape[1])
    effect_size_map = np.zeros(input_matrix.shape[1])

    filtered_matrix = input_matrix[indices, :]
    mask = np.ones(input_matrix.shape[0], dtype=bool)
    mask[indices] = False

    # Other matrix with remaining rows
    other_matrix = input_matrix[mask, :]

    # Create a pool of workers
    with Pool(processes=n_cores) as pool:
        tasks = [(filtered_matrix[:, i], other_matrix[:, i], test_name, i) for i in range(input_matrix.shape[1])]
        results = list(tqdm(pool.imap(process_column, tasks), total=len(tasks)))

    for i, stat, pval, effect_size in results:
        stat_map[i] = stat
        pval_map[i] = pval
        effect_size_map[i] = effect_size

    return stat_map, pval_map, effect_size_map

# TODO UNUSED FOR NOW
def create_cluster_representative_maps(array, discrete_embeddings, input_matrix, original_shape,
                                       test_name='mann-whitney'):
    """
    Create representative maps for each cluster in the array.
    Parameters
    ----------
    array : np.ndarray
        The array containing the clusters.
    discrete_embeddings : np.ndarray
        The discrete embeddings coordinates.
    input_matrix : np.ndarray
        The input matrix where each row is a flattened input.
    original_shape : tuple
        The original shape of the inputs.
    test_name : str, optional
        The name of the statistical test to be performed. Options are 'mann-whitney' and 't-test'.
        Default is 'mann-whitney'.

    Returns
    -------

    """
    # Separate the clusters and extract the coordinates
    # plot array
    clusters, indices_list = separate_clusters_and_extract_coords(array, discrete_embeddings)
    print(f"Found {len(clusters)} clusters")

    # Initialize lists to store the representative maps
    stat_maps = []
    pval_maps = []
    effect_size_maps = []
    # the centroids will just be returned for later use, they are not used for the stats or maps
    centroids = []

    # For each cluster, find the representative map
    for cluster, indices in zip(clusters, indices_list):
        # compute the maps
        stat_map, pval_map, effect_size_map = input_matrix_stat_map(input_matrix, indices, test_name)
        print(f'Shape of the maps: {stat_map.shape}')
        # reshape the maps (no need to use the function)
        stat_map = np.reshape(stat_map, original_shape)
        pval_map = np.reshape(pval_map, original_shape)
        effect_size_map = np.reshape(effect_size_map, original_shape)

        # add the maps to the list
        stat_maps.append(stat_map)
        pval_maps.append(pval_map)
        effect_size_maps.append(effect_size_map)

        # find the centroid of the cluster
        centroid = find_centroid_and_check(cluster)
        centroids.append(centroid)

    return stat_maps, pval_maps, effect_size_maps, centroids


def train_model(train_coords, train_scores, test_coords, test_scores, score_name, output_folder,
                categorical=False, num_permutations=100, nb_fold=5, show_plot=False):
    """
    Train and evaluate a model using NumPy arrays for training and testing.

    Parameters:
      - train_coords: ndarray of shape (n_samples, n_features)
      - train_scores: ndarray of shape (n_samples,) or (n_samples, 1)
      - test_coords: ndarray of shape (n_test, n_features)
      - test_scores: ndarray of shape (n_test,) or (n_test, 1)
      - score_name: str, identifier for the current model (used for naming files)
      - output_folder: str or Path, where output files (models, metrics, plots) will be saved
      - categorical: bool, whether the target is categorical (classification) or continuous (regression)
      - num_permutations: int, number of permutations for k-fold cross-validation
      - nb_fold: int, number of folds in k-fold cross-validation
      - show_plot: bool, whether to display plots interactively

    Returns:
      None
    """
    os.makedirs(output_folder, exist_ok=True)

    if categorical:
        # --- Classification branch ---
        # Filter out test observations that have missing scores.
        mask = ~np.isnan(test_scores)
        num_removed = len(test_scores) - np.sum(mask)
        if num_removed > 0:
            print(f"Warning: {num_removed} test observations removed for score {score_name} because they have no value.")
        test_coords = test_coords[mask]
        test_scores = test_scores[mask]

        k = nb_fold
        permutation_metrics = []
        for perm in range(num_permutations):
            kf = KFold(n_splits=k, shuffle=True, random_state=perm)
            models = []
            accuracy_scores_train = []
            accuracy_scores_val = []
            for train_index, val_index in kf.split(train_coords):
                X_train, X_val = train_coords[train_index], train_coords[val_index]
                y_train, y_val = train_scores[train_index], train_scores[val_index]
                model = RandomForestClassifier(n_estimators=100, random_state=42)
                model.fit(X_train, y_train)
                models.append(model)
                y_val_pred = model.predict(X_val)
                y_train_pred = model.predict(X_train)
                accuracy_scores_val.append(accuracy_score(y_val, y_val_pred))
                accuracy_scores_train.append(accuracy_score(y_train, y_train_pred))
            permutation_metrics.append({
                'models': models,
                'accuracy_scores_train': accuracy_scores_train,
                'accuracy_scores_val': accuracy_scores_val,
            })
        best_permutation = max(permutation_metrics, key=lambda x: np.mean(x['accuracy_scores_val']))
        best_models = best_permutation['models']
        test_predictions = []
        for model in best_models:
            preds = model.predict(test_coords)
            test_predictions.append(preds)
        test_predictions = np.array(test_predictions)
        test_predictions_mode, _ = mode(test_predictions, axis=0)
        test_predictions = test_predictions_mode.flatten()
        acc_test = accuracy_score(test_scores, test_predictions)
        print(f'{score_name} - Avg Training Accuracy: {np.mean(best_permutation["accuracy_scores_train"]):.2f}')
        print(f'{score_name} - Test Accuracy: {acc_test:.2f}')
        # (Export models, metrics, and plots as before)
        # For example, you might save a confusion matrix plot:
        cm = confusion_matrix(test_scores, test_predictions)
        cm_percent = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis] * 100
        plt.figure(figsize=(10, 6))
        sns.heatmap(cm_percent, annot=True, fmt=".2f", cmap="Blues", cbar=False)
        plt.xlabel('Predicted Classes')
        plt.ylabel('Actual Classes')
        plt.title(f'Confusion Matrix - {score_name}\nAccuracy: {acc_test*100:.2f}%')
        plt.savefig(str(Path(output_folder) / f'{score_name}_confusion_matrix.png'))
        if show_plot:
            plt.show()
        plt.close()

    else:
        # --- Regression branch ---
        # Ensure regression targets are 2D: shape (n_samples, n_targets)
        if train_scores.ndim == 1:
            train_scores = train_scores.reshape(-1, 1)
            test_scores = test_scores.reshape(-1, 1)

        n_targets = train_scores.shape[1]
        all_test_predictions = {}  # Dictionary to store predictions per target
        r2_test_dict = {}  # Store test R² per target for plotting

        for t in range(n_targets):
            print(f"Training regression model for target column {t}...")
            y_train_t = train_scores[:, t]
            y_test_t = test_scores[:, t]
            # Filter out test observations with missing target values.
            mask = ~np.isnan(y_test_t)
            num_removed = len(y_test_t) - np.sum(mask)
            if num_removed > 0:
                print(f"Warning: {num_removed} test observations removed for target column {t} in score {score_name} because they have no value.")
            y_test_t = y_test_t[mask]
            test_coords_filtered = test_coords[mask]

            k = nb_fold
            permutation_metrics = []
            for perm in range(num_permutations):
                kf = KFold(n_splits=k, shuffle=True, random_state=perm)
                models = []
                r2_scores_train = []
                r2_scores_val = []
                normalized_mse_val_list = []
                mae_max_scores = []
                normalized_mae_train_list = []
                normalized_mse_train_list = []
                mae_max_train_list = []
                for train_index, val_index in kf.split(train_coords):
                    X_train, X_val = train_coords[train_index], train_coords[val_index]
                    y_train_cv = y_train_t[train_index]
                    y_val_cv = y_train_t[val_index]

                    model = RandomForestRegressor(n_estimators=100, random_state=42)
                    model.fit(X_train, y_train_cv)
                    models.append(model)

                    y_val_pred = model.predict(X_val)
                    y_train_pred = model.predict(X_train)

                    mse_val = mean_squared_error(y_val_cv, y_val_pred)
                    mae_val = mean_absolute_error(y_val_cv, y_val_pred)
                    min_score_t = np.min(y_train_t)
                    max_score_t = np.max(y_train_t)
                    range_of_values_t = max_score_t - min_score_t if max_score_t != min_score_t else 1
                    mae_max_val = (mae_val / max_score_t) * 100 if max_score_t != 0 else 0
                    normalized_mse_val = (mse_val / (range_of_values_t ** 2)) * 100

                    r2_val = r2_score(y_val_cv, y_val_pred)
                    r2_train = r2_score(y_train_cv, y_train_pred)

                    r2_scores_val.append(r2_val)
                    r2_scores_train.append(r2_train)
                    mae_max_scores.append(mae_max_val)
                    normalized_mse_val_list.append(normalized_mse_val)

                    normalized_mae_train = (mean_absolute_error(y_train_cv, y_train_pred) / range_of_values_t) * 100
                    normalized_mse_train = (mean_squared_error(y_train_cv, y_train_pred) / (range_of_values_t ** 2)) * 100
                    mae_max_train = (mean_absolute_error(y_train_cv, y_train_pred) / max_score_t) * 100 if max_score_t != 0 else 0

                    normalized_mae_train_list.append(normalized_mae_train)
                    normalized_mse_train_list.append(normalized_mse_train)
                    mae_max_train_list.append(mae_max_train)

                permutation_metrics.append({
                    'models': models,
                    'r2_scores_train': r2_scores_train,
                    'r2_scores_val': r2_scores_val,
                    'normalized_mse_val_list': normalized_mse_val_list,
                    'mae_max_scores': mae_max_scores,
                    'normalized_mae_train_list': normalized_mae_train_list,
                    'normalized_mse_train_list': normalized_mse_train_list,
                    'mae_max_train_list': mae_max_train_list,
                })

            best_permutation = max(permutation_metrics, key=lambda x: np.mean(x['r2_scores_val']))
            best_models = best_permutation['models']

            # Ensemble predictions for target t:
            pred_example = best_models[0].predict(test_coords_filtered)
            test_predictions_t = np.zeros_like(pred_example)
            for model in best_models:
                test_predictions_t += model.predict(test_coords_filtered)
            test_predictions_t /= len(best_models)

            # Compute evaluation metrics for target t
            mse_test = mean_squared_error(y_test_t, test_predictions_t)
            mae_test = mean_absolute_error(y_test_t, test_predictions_t)
            min_score_t = np.min(y_train_t)
            max_score_t = np.max(y_train_t)
            range_of_values_t = max_score_t - min_score_t if max_score_t != min_score_t else 1
            mae_max_test = (mae_test / max_score_t) * 100 if max_score_t != 0 else 0
            normalized_mse_test = (mse_test / (range_of_values_t ** 2)) * 100
            r2_test = r2_score(y_test_t, test_predictions_t)
            normalized_mae_test = (mae_test / range_of_values_t) * 100

            print(f"Target {t} - Avg Training R²: {np.mean(best_permutation['r2_scores_train']):.2f}")
            print(f"Target {t} - Test R²: {r2_test:.2f}")
            print(
                f"Target {t} - Normalized Test MSE: {normalized_mse_test:.2f}%, "
                f"Normalized Test MAE: {normalized_mae_test:.2f}%, Test MAE_max%: {mae_max_test:.2f}%")

            r2_test_dict[t] = r2_test
            all_test_predictions[t] = test_predictions_t

            # Save metrics for target t to Excel
            metrics_df = pd.DataFrame({
                'Fold': [str(i) for i in range(1, k + 1)],
                'Training R²': best_permutation['r2_scores_train'],
                'Validation R²': best_permutation['r2_scores_val'],
                'Normalized Validation MSE (%)': best_permutation['normalized_mse_val_list'],
                'MAE_max%': best_permutation['mae_max_scores'],
            })
            metrics_df['Normalized MAE (%)'] = best_permutation['normalized_mae_train_list']
            metrics_df.loc[k, 'Fold'] = 'Avg Training'
            metrics_df.loc[k, 'Training R²'] = np.mean(best_permutation['r2_scores_train'])
            metrics_df.loc[k, 'Normalized Validation MSE (%)'] = np.mean(best_permutation['normalized_mse_train_list'])
            metrics_df.loc[k, 'MAE_max%'] = np.mean(best_permutation['mae_max_train_list'])
            metrics_df.loc[k, 'Normalized MAE (%)'] = np.mean(best_permutation['normalized_mae_train_list'])
            metrics_df.loc[k + 1, 'Fold'] = 'Test Ensemble'
            metrics_df.loc[k + 1, 'Test R²'] = r2_test
            metrics_df.loc[k + 1, 'Normalized Validation MSE (%)'] = normalized_mse_test
            metrics_df.loc[k + 1, 'MAE_max%'] = mae_max_test
            metrics_df.loc[k + 1, 'Normalized MAE (%)'] = normalized_mae_test
            target_output_folder = os.path.join(output_folder, f'target_{t}')
            os.makedirs(target_output_folder, exist_ok=True)
            metrics_df.to_excel(os.path.join(target_output_folder, f'{score_name}_target_{t}_validation_metrics.xlsx'), index=False)

        # Plot figures for regression:
        if train_scores.shape[1] == 1:
            # Single-output: use test_predictions from that branch
            # (Assuming we have test_predictions from earlier; if not, we can use test_predictions_t)
            # Here we assume single-output so test_scores and test_predictions are 1D.
            plt.figure(figsize=(10, 6))
            plt.scatter(test_scores.flatten(), test_predictions_t.flatten(), alpha=0.6)
            plt.plot([test_scores.min(), test_scores.max()],
                     [test_scores.min(), test_scores.max()], 'k--', lw=2)
            plt.xlabel('Actual Scores')
            plt.ylabel('Predicted Scores')
            plt.title(f'Actual vs Predicted Scores - {score_name}\nR² = {r2_test:.2f}')
            plt.savefig(str(Path(output_folder) / f'{score_name}_prediction_plot.png'))
            if show_plot:
                plt.show()
            plt.close()

            plt.figure(figsize=(10, 6))
            plt.scatter(test_scores.flatten(), test_predictions_t.flatten(), alpha=0.6)
            plt.xlabel('Actual Scores')
            plt.ylabel('Predicted Scores')
            plt.title(f'Actual vs Predicted Scores\nCorrelation:'
                      f' {np.corrcoef(test_scores.flatten(), test_predictions_t.flatten())[0, 1]:.2f}')
            plt.savefig(str(Path(output_folder) / f'{score_name}_correlation_plot.png'))
            if show_plot:
                plt.show()
            plt.close()
        else:
            # Multi-output: plot each target separately.
            for t in range(n_targets):
                plt.figure(figsize=(10, 6))
                plt.scatter(test_scores[:, t], all_test_predictions[t], alpha=0.6)
                plt.plot([test_scores[:, t].min(), test_scores[:, t].max()],
                         [test_scores[:, t].min(), test_scores[:, t].max()], 'k--', lw=2)
                plt.xlabel('Actual Scores')
                plt.ylabel('Predicted Scores')
                plt.title(f'Target {t} - Actual vs Predicted Scores\nR² = {r2_test_dict[t]:.2f}')
                plt.savefig(str(Path(output_folder) / f'{score_name}_target_{t}_prediction_plot.png'))
                if show_plot:
                    plt.show()
                plt.close()

                plt.figure(figsize=(10, 6))
                plt.scatter(test_scores[:, t], all_test_predictions[t], alpha=0.6)
                plt.xlabel('Actual Scores')
                plt.ylabel('Predicted Scores')
                corr_val = np.corrcoef(test_scores[:, t], all_test_predictions[t])[0, 1]
                plt.title(f'Target {t} - Actual vs Predicted Scores\nCorrelation: {corr_val:.2f}')
                plt.savefig(str(Path(output_folder) / f'{score_name}_target_{t}_correlation_plot.png'))
                if show_plot:
                    plt.show()
                plt.close()


def train_and_test_model_per_label(train_embeddings, train_labels, test_embeddings, test_labels, output_folder,
                                   categorical=True, show_plot=False):
    """
    Train and test a model for each unique label in the training dataset.

    Uses NumPy arrays directly for calculations (models receive NumPy arrays) and uses DataFrames only for saving outputs.

    Parameters:
      - train_embeddings: ndarray of shape (n_samples, n_features)
      - train_labels: ndarray of shape (n_samples,)
      - test_embeddings: ndarray of shape (n_test, n_features)
      - test_labels: ndarray of shape (n_test,)
      - output_folder: str or Path, where outputs will be saved.
      - categorical: bool, whether the target is categorical.
      - show_plot: bool, whether to display plots interactively.

    Returns:
      None
    """
    print(f'Shape of train embeddings: {train_embeddings.shape}')

    # For model training, we work directly with the NumPy arrays.
    # For saving outputs (e.g., metrics), we can convert to DataFrames.
    # For one-vs-rest, we operate on the NumPy arrays directly.
    if categorical:
        unique_labels = np.unique(train_labels)
        for label in unique_labels:
            print(f"Training model for label {label} (One-vs-Rest)...")
            train_labels_bin = (train_labels == label).astype(int)
            test_labels_bin = (test_labels == label).astype(int)
            model_output_folder = Path(output_folder) / f'label_{label}'
            model_output_folder.mkdir(parents=True, exist_ok=True)
            train_model(train_embeddings, train_labels_bin, test_embeddings, test_labels_bin,
                        score_name=f'label_{label}', output_folder=model_output_folder,
                        categorical=True, num_permutations=100, nb_fold=5, show_plot=show_plot)
            print(f"Model for label {label} trained and saved.")

        print("Training multi-class classifier on all labels...")
        multi_output_folder = Path(output_folder) / 'multi_class_classifier'
        multi_output_folder.mkdir(parents=True, exist_ok=True)
        train_model(train_embeddings, train_labels, test_embeddings, test_labels,
                    score_name='all_labels', output_folder=multi_output_folder,
                    categorical=True, num_permutations=100, nb_fold=5, show_plot=show_plot)
        print("Multi-class classification completed and results saved.")
    else:
        print("Training regression model on continuous target variable...")
        regression_output_folder = Path(output_folder) / 'regression_model'
        regression_output_folder.mkdir(parents=True, exist_ok=True)
        train_model(train_embeddings, train_labels, test_embeddings, test_labels,
                    score_name='continuous_target', output_folder=regression_output_folder,
                    categorical=False, num_permutations=100, nb_fold=5, show_plot=show_plot)
        print("Regression model trained and results saved.")

# TODO UNUSED FOR NOW (except for the Kriging model)
def estimate_memory_size(n_points, dtype_size=8):
    """
    Estimate the memory size of the covariance matrix.

    Parameters:
    - n_points: Number of data points
    - dtype_size: Size of the data type (default is 8 bytes for float64)

    Returns:
    - Estimated memory size in bytes
    """
    return n_points ** 2 * dtype_size

# TODO UNUSED FOR NOW (except for the Kriging model)
def partition_dataset(coordinates, scores, max_batch_size):
    """
    Partition the dataset into smaller batches.

    Parameters:
    - coordinates: Array of coordinates
    - scores: Array of scores
    - max_batch_size: Maximum number of points per batch

    Returns:
    - List of (coordinates, scores) batches
    """
    batches = []
    for i in range(0, len(coordinates), max_batch_size):
        coord_batch = coordinates[i:i + max_batch_size]
        score_batch = scores[i:i + max_batch_size]
        batches.append((coord_batch, score_batch))
    return batches

# TODO UNUSED FOR NOW
def train_model_kriging(training_df, test_df, score_name, output_folder):
    os.makedirs(output_folder, exist_ok=True)

    # Drop rows with NaN values in the scores column
    training_df = training_df.dropna(subset=['scores'])
    test_df = test_df.dropna(subset=['scores'])

    # Extract coordinates and scores from training data
    train_coords = np.array([list(coord) for coord in training_df['embeddings']])
    train_scores = training_df['scores'].values

    # Extract coordinates and scores from test data
    test_coords = np.array([list(coord) for coord in test_df['embeddings']])
    test_scores = test_df['scores'].values

    # Determine the range of possible values
    min_score = min(np.min(train_scores), np.min(test_scores))
    max_score = max(np.max(train_scores), np.max(test_scores))
    range_of_values = max_score - min_score

    # Estimate memory requirements
    estimated_memory = estimate_memory_size(len(train_coords))
    estimated_memory_gb = estimated_memory / (1024 ** 3)
    print(f"Estimated memory size: {estimated_memory_gb:.2f} GB")

    # Set memory limit in GB
    memory_limit_gb = 10
    dtype_size = 8  # Size of float64

    if estimated_memory_gb > memory_limit_gb:
        # Use batching
        max_batch_points = int((memory_limit_gb * (1024 ** 3)) ** 0.5 / dtype_size)
        batches = partition_dataset(train_coords, train_scores, max_batch_points)
    else:
        # No batching needed
        batches = [(train_coords, train_scores)]

    # Number of folds for cross-validation
    k = 5

    # Lists to store validation metrics
    r2_scores_train = []
    r2_scores_val = []
    normalized_mse_val_list = []
    mae_max_scores = []
    normalized_mae_train_list = []
    normalized_mse_train_list = []
    mae_max_train_list = []
    models = []

    kf = KFold(n_splits=k, shuffle=True, random_state=42)

    for train_index, val_index in kf.split(train_coords):
        X_train, X_val = train_coords[train_index], train_coords[val_index]
        y_train, y_val = train_scores[train_index], train_scores[val_index]

        # Train model on each batch separately
        batch_models = []
        for coord_batch, score_batch in batches:
            model = Krige(method='universal', variogram_model='gaussian')
            model.fit(coord_batch, score_batch)
            batch_models.append(model)

        # Store the trained models
        models.append(batch_models)

        # Predict on training set
        y_train_pred = np.zeros(len(y_train))
        for model in batch_models:
            y_train_pred += model.predict(X_train)
        y_train_pred /= len(batch_models)

        # Predict on validation set
        y_val_pred = np.zeros(len(y_val))
        for model in batch_models:
            y_val_pred += model.predict(X_val)
        y_val_pred /= len(batch_models)

        # Evaluate on the validation set
        mse_val = mean_squared_error(y_val, y_val_pred)
        mae_val = mean_absolute_error(y_val, y_val_pred)
        mae_max_val = (mae_val / max_score) * 100
        normalized_mse_val = (mse_val / (range_of_values ** 2)) * 100
        r2_val = r2_score(y_val, y_val_pred)
        r2_train = r2_score(y_train, y_train_pred)

        mae_max_scores.append(mae_max_val)
        normalized_mse_val_list.append(normalized_mse_val)
        r2_scores_val.append(r2_val)
        r2_scores_train.append(r2_train)

        # Normalize errors
        normalized_mae_train = (mean_absolute_error(y_train, y_train_pred) / range_of_values) * 100
        normalized_mse_train = (mean_squared_error(y_train, y_train_pred) / (range_of_values ** 2)) * 100
        mae_max_train = (mean_absolute_error(y_train, y_train_pred) / max_score) * 100
        normalized_mae_train_list.append(normalized_mae_train)
        normalized_mse_train_list.append(normalized_mse_train)
        mae_max_train_list.append(mae_max_train)

    # Make predictions on the test data using the ensemble of models
    test_predictions = np.zeros(test_coords.shape[0])
    for batch_models in models:
        for model in batch_models:
            test_predictions += model.predict(test_coords)
    test_predictions /= len(models) * len(batch_models)

    # Calculate the Mean Squared Error, Mean Absolute Error, and R^2 on the test data
    mse_test = mean_squared_error(test_scores, test_predictions)
    mae_test = mean_absolute_error(test_scores, test_predictions)
    mae_max_test = (mae_test / max_score) * 100
    normalized_mse_test = (mse_test / (range_of_values ** 2)) * 100
    r2_test = r2_score(test_scores, test_predictions)

    # Normalize errors
    normalized_mae_test = (mae_test / range_of_values) * 100
    print(f'{score_name} - Avg Training R^2: {np.mean(r2_scores_train)}')
    print(
        f'{score_name} - Avg Normalized Training MSE: {np.mean(normalized_mse_train_list):.2f}%, Avg Normalized Training MAE: {np.mean(normalized_mae_train_list):.2f}%, Avg MAE_max% Training: {np.mean(mae_max_train_list):.2f}%')
    print(f'{score_name} - Test R^2: {r2_test}')
    print(
        f'{score_name} - Normalized Test MSE: {normalized_mse_test:.2f}%, Normalized Test MAE: {normalized_mae_test:.2f}%, Test MAE_max%: {mae_max_test:.2f}%')

    # Save the models
    for i, batch_models in enumerate(models):
        for j, model in enumerate(batch_models):
            model_path = os.path.join(output_folder, f'{score_name}_model_fold_{i}_batch_{j}.pkl')
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
            print(f'Model {i} batch {j} saved to {model_path}')

    # Save the validation metrics, including the ensembled test metrics, to a spreadsheet
    metrics_df = pd.DataFrame({
        'Fold': range(1, k + 1),
        'Training R^2': r2_scores_train,
        'Validation R^2': r2_scores_val,
        'Normalized Validation MSE (%)': normalized_mse_val_list,
        'MAE_max%': mae_max_scores,
    })
    metrics_df['Normalized MAE (%)'] = normalized_mae_train_list

    # Calculate and append the average training metrics
    avg_training_r2 = np.mean(r2_scores_train)
    avg_normalized_mae_train = np.mean(normalized_mae_train_list)
    avg_normalized_mse_train = np.mean(normalized_mse_train_list)
    avg_mae_max_train = np.mean(mae_max_train_list)
    metrics_df.loc[k, 'Fold'] = 'Avg Training'
    metrics_df.loc[k, 'Training R^2'] = avg_training_r2
    metrics_df.loc[k, 'Normalized Validation MSE (%)'] = avg_normalized_mse_train
    metrics_df.loc[k, 'MAE_max%'] = avg_mae_max_train
    metrics_df.loc[k, 'Normalized MAE (%)'] = avg_normalized_mae_train

    # Append the ensembled test metrics to the DataFrame
    metrics_df.loc[k + 1, 'Fold'] = 'Test Ensemble'
    metrics_df.loc[k + 1, 'Test R^2'] = r2_test
    metrics_df.loc[k + 1, 'Normalized Validation MSE (%)'] = normalized_mse_test
    metrics_df.loc[k + 1, 'MAE_max%'] = mae_max_test
    metrics_df.loc[k + 1, 'Normalized MAE (%)'] = normalized_mae_test

    # Save to Excel
    metrics_df.to_excel(os.path.join(output_folder, f'{score_name}_validation_metrics.xlsx'), index=False)

    # Plotting the correlation between actual and predicted scores
    plt.figure(figsize=(10, 6))
    plt.scatter(test_scores, test_predictions, alpha=0.6)
    plt.xlabel('Actual Scores')
    plt.ylabel('Predicted Scores')
    plt.title(
        f'Actual vs Predicted Scores - {score_name}\nCorrelation: {np.corrcoef(test_scores, test_predictions)[0, 1]:.2f}')
    plt.savefig(os.path.join(output_folder, f'{score_name}_correlation_plot.png'))
    plt.show()

# TODO UNUSED FOR NOW (except for the xgboost model)
def augment_data(embeddings, augmentation_factor=3):
    min = np.min(embeddings, axis=0)
    max = np.max(embeddings, axis=0)
    range = max - min
    noise_level = 0.01 * range
    augmented_embeddings = []
    for embedding in embeddings:
        for _ in range(augmentation_factor):
            noise = np.random.normal(0, noise_level, size=embedding.shape)
            augmented_embedding = embedding + noise
            augmented_embeddings.append(augmented_embedding)
    return np.array(augmented_embeddings)


# TODO UNUSED FOR NOW
def train_model_xgboost_with_fold_grid_search(training_df, test_df, score_name, output_folder, augmentation_factor=1):
    os.makedirs(output_folder, exist_ok=True)

    # Drop rows with NaN values in the scores column
    training_df = training_df.dropna(subset=['scores'])
    test_df = test_df.dropna(subset=['scores'])

    # Extract coordinates and scores from training data
    train_coords = np.array([list(coord) for coord in training_df['embeddings']])
    train_scores = training_df['scores'].values

    # Extract coordinates and scores from test data
    test_coords = np.array([list(coord) for coord in test_df['embeddings']])
    test_scores = test_df['scores'].values

    # Determine the range of possible values
    min_score = min(np.min(train_scores), np.min(test_scores))
    max_score = max(np.max(train_scores), np.max(test_scores))
    range_of_values = max_score - min_score

    # Define parameter grid for GridSearchCV
    param_grid = {
        'n_estimators': [100, 200, 300],
        'learning_rate': [0.01, 0.1, 0.2],
        'max_depth': [3, 5, 7],
        'min_child_weight': [1, 3, 5],
        'subsample': [0.8, 1.0],
        'colsample_bytree': [0.8, 1.0],
        'gamma': [0, 0.1, 0.2]
    }

    # Number of folds for cross-validation
    k = 5

    # Lists to store validation metrics
    r2_scores_train = []
    r2_scores_val = []
    normalized_mse_val_list = []
    mae_max_scores = []
    normalized_mae_train_list = []
    normalized_mse_train_list = []
    mae_max_train_list = []
    best_models = []

    kf = KFold(n_splits=k, shuffle=True, random_state=42)

    for train_index, val_index in kf.split(train_coords):
        X_train, X_val = train_coords[train_index], train_coords[val_index]
        y_train, y_val = train_scores[train_index], train_scores[val_index]

        # Augment the training data
        X_train_augmented = augment_data(X_train, augmentation_factor)
        y_train_augmented = np.repeat(y_train, augmentation_factor)

        print(f"Training data shape: {X_train_augmented.shape}")
        print(f"Training labels shape: {y_train_augmented.shape}")

        model = xgb.XGBRegressor(random_state=42)

        # Perform GridSearchCV within each fold
        grid_search = GridSearchCV(estimator=model, param_grid=param_grid, cv=3, scoring='r2', verbose=2, n_jobs=-1)
        grid_search.fit(X_train_augmented, y_train_augmented)

        print(f"Best parameters for fold: {grid_search.best_params_}")

        # Use the best model from grid search
        best_model = grid_search.best_estimator_
        best_model.fit(X_train_augmented, y_train_augmented)

        # Store the best model from each fold
        best_models.append(best_model)

        y_val_pred = best_model.predict(X_val)
        y_train_pred = best_model.predict(X_train)
        mse_val = mean_squared_error(y_val, y_val_pred)
        mae_val = mean_absolute_error(y_val, y_val_pred)
        mae_max_val = (mae_val / max_score) * 100
        normalized_mse_val = (mse_val / (range_of_values ** 2)) * 100
        r2_val = r2_score(y_val, y_val_pred)
        r2_train = r2_score(y_train, y_train_pred)

        mae_max_scores.append(mae_max_val)
        normalized_mse_val_list.append(normalized_mse_val)
        r2_scores_val.append(r2_val)
        r2_scores_train.append(r2_train)
        normalized_mae_train_list.append((mean_absolute_error(y_train, y_train_pred) / range_of_values) * 100)
        normalized_mse_train_list.append((mean_squared_error(y_train, y_train_pred) / (range_of_values ** 2)) * 100)
        mae_max_train_list.append((mean_absolute_error(y_train, y_train_pred) / max_score) * 100)

    # Make predictions on the test data using the ensemble of best models from each fold
    test_predictions = np.zeros(test_coords.shape[0])
    for model in best_models:
        test_predictions += model.predict(test_coords)
    test_predictions /= len(best_models)

    # Calculate the Mean Squared Error, Mean Absolute Error, and R^2 on the test data
    mse_test = mean_squared_error(test_scores, test_predictions)
    mae_test = mean_absolute_error(test_scores, test_predictions)
    mae_max_test = (mae_test / max_score) * 100
    normalized_mse_test = (mse_test / (range_of_values ** 2)) * 100
    r2_test = r2_score(test_scores, test_predictions)

    # Normalize errors
    normalized_mae_test = (mae_test / range_of_values) * 100
    print(f'{score_name} - Avg Training R^2: {np.mean(r2_scores_train)}')
    print(
        f'{score_name} - Avg Normalized Training MSE: {np.mean(normalized_mse_train_list):.2f}%, Avg Normalized Training MAE: {np.mean(normalized_mae_train_list):.2f}%, Avg MAE_max% Training: {np.mean(mae_max_train_list):.2f}%')
    print(f'{score_name} - Test R^2: {r2_test}')
    print(
        f'{score_name} - Normalized Test MSE: {normalized_mse_test:.2f}%, Normalized Test MAE: {normalized_mae_test:.2f}%, Test MAE_max%: {mae_max_test:.2f}%')

    # Save the best models
    for i, model in enumerate(best_models):
        model_path = os.path.join(output_folder, f'{score_name}_model_fold_{i}.pkl')
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        print(f'Model {i} saved to {model_path}')

    # Save the validation metrics, including the ensembled test metrics, to a spreadsheet
    metrics_df = pd.DataFrame({
        'Fold': range(1, k + 1),
        'Training R^2': r2_scores_train,
        'Validation R^2': r2_scores_val,
        'Normalized Validation MSE (%)': normalized_mse_val_list,
        'MAE_max%': mae_max_scores,
    })
    metrics_df['Normalized MAE (%)'] = normalized_mae_train_list

    # Calculate and append the average training metrics
    avg_training_r2 = np.mean(r2_scores_train)
    avg_normalized_mae_train = np.mean(normalized_mae_train_list)
    avg_normalized_mse_train = np.mean(normalized_mse_train_list)
    avg_mae_max_train = np.mean(mae_max_train_list)
    metrics_df.loc[k, 'Fold'] = 'Avg Training'
    metrics_df.loc[k, 'Training R^2'] = avg_training_r2
    metrics_df.loc[k, 'Normalized Validation MSE (%)'] = avg_normalized_mse_train
    metrics_df.loc[k, 'MAE_max%'] = avg_mae_max_train
    metrics_df.loc[k, 'Normalized MAE (%)'] = avg_normalized_mae_train

    # Append the ensembled test metrics to the DataFrame
    metrics_df.loc[k + 1, 'Fold'] = 'Test Ensemble'
    metrics_df.loc[k + 1, 'Test R^2'] = r2_test
    metrics_df.loc[k + 1, 'Normalized Validation MSE (%)'] = normalized_mse_test
    metrics_df.loc[k + 1, 'MAE_max%'] = mae_max_test
    metrics_df.loc[k + 1, 'Normalized MAE (%)'] = normalized_mae_test

    # Save to Excel
    metrics_df.to_excel(os.path.join(output_folder, f'{score_name}_validation_metrics.xlsx'), index=False)

    # Plotting the data
    plt.figure(figsize=(10, 6))
    plt.scatter(test_scores, test_predictions, alpha=0.6)
    plt.xlabel('Actual Scores')
    plt.ylabel('Predicted Scores')
    plt.title(f'Actual vs Predicted Scores - {score_name}\nR² = {r2_test:.2f}')
    plt.savefig(os.path.join(output_folder, f'{score_name}_prediction_plot.png'))
    plt.show()

    # Plotting the correlation between actual and predicted scores
    plt.figure(figsize=(10, 6))
    plt.scatter(test_scores, test_predictions, alpha=0.6)
    plt.xlabel('Actual Scores')
    plt.ylabel('Predicted Scores')
    plt.title(
        f'Actual vs Predicted Scores - {score_name}\nCorrelation: {np.corrcoef(test_scores, test_predictions)[0, 1]:.2f}')
    plt.savefig(os.path.join(output_folder, f'{score_name}_correlation_plot.png'))
    plt.show()


def compute_distance_vector(embeddings, coord):
    """
    Compute the distance vector between the given coordinates and the input embeddings.

    Parameters:
    - embeddings: np.ndarray, shape (n, d)
        Array of embeddings
    - coord: np.ndarray, shape (d,)
        Coordinates of interest

    Returns:
    - Array of distances
    """
    return np.linalg.norm(embeddings - coord, axis=1)


def compute_gwd_for_point(embeddings, coord, sigma):
    """
    Compute the Gaussian filter values for the distances between the given coordinates and the input embeddings.

    Parameters:
    - embeddings: np.ndarray, shape (n, d)
        Array of embeddings
    - coord: np.ndarray, shape (d,)
        Coordinates of interest
    - sigma: float, optional, default=1.0
        Standard deviation for the Gaussian filter

    Returns:
    - Array of Gaussian filter values
    """
    distances = np.linalg.norm(embeddings - coord, axis=1)
    gaussian_values = np.exp(-0.5 * (distances / sigma) ** 2)
    return gaussian_values


def compute_all_gwd(embeddings, sigma):
    """
    Compute the Gaussian weighted distance vectors for all points in the embedding.

    Parameters:
        embeddings (np.ndarray): Array of shape (n_samples, n_features)
        sigma (float): The Gaussian kernel bandwidth.

    Returns:
        np.ndarray: A matrix of shape (n_samples, n_samples) where row i is the GWD vector for point i.
    """
    n = embeddings.shape[0]
    gwd_matrix = np.zeros((n, n))
    for i in range(n):
        gwd_matrix[i, :] = compute_gwd_for_point(embeddings, embeddings[i:i+1], sigma)
    return gwd_matrix


def compute_gwd_summary(embeddings, sigma, mode="basic"):
    """
    Compute summary statistics from Gaussian weighted distances (GWD) for each point in embeddings.

    Parameters:
        embeddings (np.ndarray): Array of shape (n_samples, n_features)
        sigma (float): Gaussian kernel bandwidth.
        mode (str): Which summary statistics to compute. Options are:
            "basic"     - returns effective number of neighbors (ESS) and weighted standard deviation.
            "extended"  - returns ESS, weighted mean distance, and weighted standard deviation.
            "full"      - returns ESS, weighted mean, weighted standard deviation, and optionally median distance.

    Returns:
        np.ndarray: Feature matrix of shape (n_samples, n_features_summary) depending on mode.
    """
    gwd_matrix = compute_all_gwd(embeddings, sigma)
    # Effective number of neighbors
    ess = (gwd_matrix.sum(axis=1) ** 2) / (np.square(gwd_matrix).sum(axis=1) + 1e-8)

    n_points = embeddings.shape[0]
    weighted_means = np.zeros(n_points)
    weighted_vars = np.zeros(n_points)
    medians = np.zeros(n_points)
    for i in range(n_points):
        distances = np.linalg.norm(embeddings - embeddings[i:i + 1], axis=1)
        weights = gwd_matrix[i, :]
        weighted_mean = np.sum(weights * distances) / (np.sum(weights) + 1e-8)
        weighted_means[i] = weighted_mean
        weighted_vars[i] = np.sum(weights * (distances - weighted_mean) ** 2) / (np.sum(weights) + 1e-8)
        medians[i] = np.median(distances)
    weighted_std = np.sqrt(weighted_vars)

    if mode == "basic":
        summary_features = np.column_stack((ess, weighted_std))
    elif mode == "extended":
        summary_features = np.column_stack((ess, weighted_means, weighted_std))
    elif mode == "full":
        summary_features = np.column_stack((ess, weighted_means, weighted_std, medians))
    else:
        raise ValueError(f"Mode {mode} is not supported. Choose 'basic', 'extended', or 'full'.")

    return summary_features


def compute_sigma_median(embeddings, sample_size=None):
    """
    Compute the median pairwise distance (sigma) from a set of embeddings.

    Parameters
    ----------
    embeddings : np.ndarray
        2D array of shape (n_samples, n_features), i.e., the coordinates in the latent space.
    sample_size : int or None
        If specified, randomly sample 'sample_size' points from the embeddings to speed up
        distance computation on very large datasets. If None, use all points.

    Returns
    -------
    float
        The median pairwise distance between the sampled points, or a default value if the
        resulting set is empty.
    """
    # If sample_size is provided and less than the total number of embeddings, sample accordingly.
    if sample_size is not None and sample_size < len(embeddings):
        idx = np.random.choice(len(embeddings), size=sample_size, replace=False)
        sub_embeddings = embeddings[idx]
    else:
        sub_embeddings = embeddings

    # If the sub_embeddings array is empty, return a default sigma (e.g., 1.0).
    if sub_embeddings.shape[0] == 0:
        return 1.0

    # Compute the pairwise distance matrix
    distance_matrix = pairwise_distances(sub_embeddings, sub_embeddings)

    # Extract the upper triangular part of the distance matrix (excluding the diagonal)
    distances = distance_matrix[np.triu_indices_from(distance_matrix, k=1)]

    # If there are no distances (which might happen if there is only one point), return default sigma.
    if distances.size == 0:
        return 1.0

    # Compute and return the median distance.
    median_dist = np.median(distances)
    return median_dist


def train_predictive_model_gpy(combined_features, target, output_folder, mode='regression',
                               cv_folds=5, random_state=42, n_restarts_optimizer=5,
                               sparse_threshold=None, num_inducing=10000):
    """
    Train a Gaussian Process predictive model using GPy with cross-validation.
    Optionally use the sparse version when the number of training points exceeds
    a given threshold.

    Parameters
    ----------
    combined_features : np.ndarray, shape (n_samples, n_features)
        The final feature matrix (e.g., UMAP embeddings concatenated with GWD summary features).
    target : np.ndarray, shape (n_samples,) or (n_samples, 1)
        For regression, continuous targets; for classification, discrete labels.
    output_folder : str or Path
        Directory in which to save diagnostic plots.
    mode : {'regression', 'classification'}, default='regression'
        Type of task.
    cv_folds : int, default=5
        Number of CV folds.
    random_state : int, default=42
        Random state for reproducibility.
    n_restarts_optimizer : int, default=5
        Number of restarts for hyperparameter optimization.
    sparse_threshold : int or None, default=None
        If not None and the training set size is above this value, the sparse version is used.
    num_inducing : int, default=100
        Number of inducing points to use if using the sparse method.

    Returns
    -------
    results : dict
        A dictionary containing:
            - 'final_model': The GP model fitted to all data.
            - 'cv_metrics': List of performance metrics per fold.
            - 'cv_predictions': List of predictions (and uncertainty estimates) for each CV fold.
            - 'full_predictions': Predictions (and uncertainty) for the full training set by the final model.
            - 'mode': The mode used.
    """
    # Ensure output folder exists.
    output_folder = os.path.abspath(output_folder)
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # We'll use KFold to partition the data.
    cv = KFold(n_splits=cv_folds, shuffle=True, random_state=random_state)

    cv_metrics = []
    cv_predictions = []
    fold = 0

    # For reproducibility, set seed for inducing point selection if using sparse models.
    np.random.seed(random_state)

    # Loop over CV folds.
    for train_idx, val_idx in cv.split(combined_features):
        X_train = combined_features[train_idx]
        X_val = combined_features[train_idx]
        # For GPy, targets should be 2D for regression.
        if mode == 'regression':
            y_train = target[train_idx].reshape(-1, 1)
            y_val = target[val_idx].reshape(-1, 1)
        else:
            y_train = target[train_idx]
            y_val = target[val_idx]

        # Choose model type based on training set size and the sparse_threshold.
        if (sparse_threshold is not None) and (X_train.shape[0] > sparse_threshold):
            # Use the sparse version with num_inducing points.
            if mode == 'regression':
                # Select inducing inputs randomly from X_train.
                inducing = X_train[np.random.choice(np.arange(X_train.shape[0]), size=num_inducing, replace=False)]
                model = GPy.models.SparseGPRegression(X_train, y_train, kernel=GPy.kern.RBF(input_dim=X_train.shape[1]),
                                                      Z=inducing)
            else:
                inducing = X_train[np.random.choice(np.arange(X_train.shape[0]), size=num_inducing, replace=False)]
                model = GPy.models.SparseGPClassification(X_train, y_train.reshape(-1, 1),
                                                          kernel=GPy.kern.RBF(input_dim=X_train.shape[1]),
                                                          Z=inducing)
        else:
            # Use the full GP model.
            if mode == 'regression':
                model = GPy.models.GPRegression(X_train, y_train, kernel=GPy.kern.RBF(input_dim=X_train.shape[1]))
            else:
                model = GPy.models.GPClassification(X_train, y_train.reshape(-1, 1),
                                                    kernel=GPy.kern.RBF(input_dim=X_train.shape[1]))

        # Optimize the model hyperparameters.
        model.optimize_restarts(num_restarts=n_restarts_optimizer, verbose=False)

        # Get predictions for the validation fold.
        if mode == 'regression':
            y_pred_mean, y_pred_var = model.predict(X_val)
            y_pred_std = np.sqrt(y_pred_var)
            fold_metrics = {
                'r2': r2_score(y_val, y_pred_mean),
                'mse': mean_squared_error(y_val, y_pred_mean),
                'mae': mean_absolute_error(y_val, y_pred_mean)
            }
            fold_pred = {'predictions': y_pred_mean.flatten(), 'uncertainty': y_pred_std.flatten()}
        else:
            # For classification, get probability predictions.
            # GPy’s GPClassification uses a Laplace approximation so that model.predict(X)
            # returns the probability for the positive class.
            y_pred_prob, _ = model.predict(X_val)
            y_pred = (y_pred_prob >= 0.5).astype(int)
            fold_metrics = {
                'accuracy': accuracy_score(y_val, y_pred),
                'f1': f1_score(y_val, y_pred, average='weighted'),
                'precision': precision_score(y_val, y_pred, average='weighted', zero_division=0),
                'recall': recall_score(y_val, y_pred, average='weighted')
            }
            # Uncertainty can be computed as the entropy of the predicted probability vector.
            uncertainties = np.array([entropy([p, 1 - p], base=2) for p in y_pred_prob.flatten()])
            fold_pred = {'predictions': y_pred.flatten(), 'probabilities': y_pred_prob.flatten(),
                         'uncertainty': uncertainties}

        cv_metrics.append(fold_metrics)
        cv_predictions.append(fold_pred)
        print(f"Fold {fold} {mode} metrics: {fold_metrics}")
        fold += 1

    # Train the final model on the full dataset.
    if mode == 'regression':
        y_full = target.reshape(-1, 1)
    else:
        y_full = target.reshape(-1, 1)

    if (sparse_threshold is not None) and (combined_features.shape[0] > sparse_threshold):
        inducing = combined_features[
            np.random.choice(np.arange(combined_features.shape[0]), size=num_inducing, replace=False)]
        if mode == 'regression':
            final_model = GPy.models.SparseGPRegression(combined_features, y_full,
                                                        kernel=GPy.kern.RBF(input_dim=combined_features.shape[1]),
                                                        Z=inducing)
        else:
            final_model = GPy.models.SparseGPClassification(combined_features, y_full,
                                                            kernel=GPy.kern.RBF(input_dim=combined_features.shape[1]),
                                                            Z=inducing)
    else:
        if mode == 'regression':
            final_model = GPy.models.GPRegression(combined_features, y_full,
                                                  kernel=GPy.kern.RBF(input_dim=combined_features.shape[1]))
        else:
            final_model = GPy.models.GPClassification(combined_features, y_full,
                                                      kernel=GPy.kern.RBF(input_dim=combined_features.shape[1]))

    final_model.optimize_restarts(num_restarts=n_restarts_optimizer, verbose=False)

    # Get predictions on the full dataset.
    if mode == 'regression':
        full_mean, full_var = final_model.predict(combined_features)
        full_std = np.sqrt(full_var)
        full_predictions = {'predictions': full_mean.flatten(), 'uncertainty': full_std.flatten()}
    else:
        full_prob, _ = final_model.predict(combined_features)
        full_pred = (full_prob >= 0.5).astype(int)
        full_uncertainty = np.array([entropy([p, 1 - p], base=2) for p in full_prob.flatten()])
        full_predictions = {'predictions': full_pred.flatten(), 'probabilities': full_prob.flatten(),
                            'uncertainty': full_uncertainty}

    # Save a diagnostic plot (e.g., predicted vs. actual for regression; histogram of uncertainty for classification)
    plt.figure()
    if mode == 'regression':
        plt.errorbar(np.arange(len(full_predictions['predictions'])), full_predictions['predictions'],
                     yerr=full_predictions['uncertainty'], fmt='o', alpha=0.5)
        plt.title("Final GP Regression Model Predictions with Uncertainty")
    else:
        plt.hist(full_predictions['uncertainty'], bins=30)
        plt.title("Histogram of Prediction Uncertainty (Entropy) - GP Classification")
    diag_path = os.path.join(output_folder, f"final_model_diagnostics_{mode}.png")
    plt.savefig(diag_path)
    plt.close()
    print(f"Final diagnostic plot saved to: {diag_path}")

    results = {
        'final_model': final_model,
        'cv_metrics': cv_metrics,
        'cv_predictions': cv_predictions,
        'full_predictions': full_predictions,
        'mode': mode
    }

    return results


def train_predictive_model_gpy(X, y, is_classification=False, sparse_threshold=500):
    """
    Train a predictive model using GPy.

    When the dataset is larger than `sparse_threshold`, the sparse
    version of the model is used.

    Parameters:
        X (np.ndarray): Input feature matrix.
        y (np.ndarray): Target vector (for regression, it should be (n, 1); for classification, binary values).
        is_classification (bool): Whether to perform classification.
        sparse_threshold (int): If the number of data points exceeds this threshold, use the sparse version.

    Returns:
        model: A trained GPy model.
    """
    import GPy
    # Choose the kernel (here we use a standard RBF kernel; you can customize this)
    kernel = GPy.kern.RBF(input_dim=X.shape[1], ARD=True)

    if not is_classification:
        # Regression case.
        if X.shape[0] > sparse_threshold:
            print("Training a sparse GP regression model...")
            model = GPy.models.SparseGPRegression(X, y, kernel=kernel)
        else:
            print("Training a standard GP regression model...")
            model = GPy.models.GPRegression(X, y, kernel=kernel)
    else:
        # Classification case.
        # Ensure y is of shape (n, 1) and contains binary values {0,1}.
        y = y.reshape(-1, 1)
        if X.shape[0] > sparse_threshold:
            print("Training a sparse GP classification model...")
            model = GPy.models.SparseGPClassification(X, y, kernel=kernel)
        else:
            print("Training a standard GP classification model...")
            model = GPy.models.GPClassification(X, y, kernel=kernel)

    # Optimize the model
    model.optimize(messages=True, max_iters=1000)
    return model


def new_pipeline_test(embeddings, combined_input_matrix, scores_vectors_dict, output_folder,
                      grid_size=100, dataset_type='image', cluster_labels=None, full_embeddings=None,
                      test_embeddings=None, test_labels=None, sparse_threshold=500,
                      run_parallel=True, n_jobs=-1, optuna_trials=50, model_selection=None):
    """
    Enhanced pipeline function with robust model selection and parallel training.

    This function:
      1. Extracts the VOI_vector from scores_vectors_dict.
      2. Runs robust nested CV with Optuna optimization to determine optimal kernel and sigma
         for Kernel Regression on the UMAP embeddings and VOI_vector.
      3. Aggregates candidate sigma values to obtain a robust final_sigma.
      4. Uses final_sigma to compute the full GWD matrix and summary features.
      5. Forms combined_features by concatenating UMAP embeddings with GWD summaries.
      6. Creates multiple feature sets for evaluation.
      7. Uses Optuna to optimize hyperparameters for multiple model types across feature sets.
      8. Trains models in parallel when possible.
      9. Evaluates performance on test set or via cross-validation.
      10. Aggregates and compares results across models and feature sets.

    Parameters:
        embeddings (np.ndarray): UMAP embeddings for the labelled (training) data.
        combined_input_matrix (np.ndarray): The original high-dimensional input.
        scores_vectors_dict (dict): Dictionary mapping VOI score tags to target vectors.
        output_folder (str or Path): Directory to save outputs.
        grid_size (int): Grid resolution for heatmap generation.
        dataset_type (str): Type of input data ('image', etc.).
        cluster_labels (np.ndarray): Optional cluster labels.
        full_embeddings (np.ndarray): Full UMAP embeddings (if available).
        test_embeddings (np.ndarray, optional): Test set UMAP embeddings.
        test_labels (np.ndarray, optional): Test set labels (possibly multi-dimensional).
        sparse_threshold (int): Threshold to switch to the sparse GP model version.
        run_parallel (bool): Whether to train models in parallel.
        n_jobs (int): Number of processes for parallel execution (-1 for all cores).
        optuna_trials (int): Number of trials for Optuna optimization per model/feature set.
        model_selection (list): Model types to try. If None, uses ['gp', 'rf', 'gb', 'kr', 'xgb'].

    Returns:
        dict: A dictionary containing outputs including the GWD matrix, summaries, combined features,
              grid coordinates, a heatmap dictionary, CV performance, final_sigma, test performance,
              and model comparison results.
    """
    import os
    from matplotlib import pyplot as plt
    import numpy as np
    import optuna
    from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
    from sklearn.model_selection import KFold
    import time
    import joblib
    from joblib import Parallel, delayed
    import json
    
    # Import functions from elsewhere in the codebase
    from emuses.tools.kernel_regression_utils import KernelRegressor, nested_cv_kernel_regression, ensemble_predict
    from emuses.tools.correlation_maps_utils import calculate_correlation_grid
    
    # Set default model selection if not provided
    if model_selection is None:
        model_selection = ['gp', 'rf', 'gb', 'kr', 'xgb']
    
    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    
    print("========== Starting Enhanced EMUSES Pipeline ==========")
    start_time = time.time()

    # STEP 1: Extract VOI_vector from scores_vectors_dict.
    if len(scores_vectors_dict) == 0:
        raise ValueError("scores_vectors_dict is empty; cannot extract VOI_vector.")
    elif len(scores_vectors_dict) == 1:
        key = next(iter(scores_vectors_dict))
        VOI_vector = np.array(scores_vectors_dict[key])
    else:
        key = sorted(scores_vectors_dict.keys())[0]
        VOI_vector = np.array(scores_vectors_dict[key])
    print("Using VOI_vector from key:", key)

    # For normalization
    global_range = np.max(VOI_vector) - np.min(VOI_vector)
    
    # STEP 2: Use Optuna to find optimal kernel and sigma with nested CV
    print("Starting Optuna optimization to find robust sigma for GWD calculation...")
    
    # Define the objective function for Optuna
    def objective(trial):
        # Define nested cross-validation structure
        n_outer = 5
        n_inner = 3
        
        # Initialize list to store best sigma values from each outer fold
        sigma_values = []
        r2_scores = []
        
        # Outer cross-validation loop
        outer_cv = KFold(n_splits=n_outer, shuffle=True, random_state=42)
        
        for train_idx, test_idx in outer_cv.split(embeddings):
            X_train_outer, X_test_outer = embeddings[train_idx], embeddings[test_idx]
            y_train_outer, y_test_outer = VOI_vector[train_idx], VOI_vector[test_idx]
            
            # Inner cross-validation loop to find best sigma for this outer fold
            best_r2 = -np.inf
            best_sigma = None
            
            # Suggest hyperparameters to try
            kernel_type = trial.suggest_categorical('kernel', ['gaussian', 'epanechnikov', 'triangular'])
            # Ensure we sample a wide range of potential sigma values
            sigma = trial.suggest_float('sigma', 0.001, 1.0, log=True)
            
            # Inner cross-validation
            inner_cv = KFold(n_splits=n_inner, shuffle=True, random_state=42)
            inner_scores = []
            
            for inner_train_idx, inner_val_idx in inner_cv.split(X_train_outer):
                X_train_inner = X_train_outer[inner_train_idx]
                X_val_inner = X_train_outer[inner_val_idx]
                y_train_inner = y_train_outer[inner_train_idx]
                y_val_inner = y_train_outer[inner_val_idx]
                
                # Train KR model with these hyperparameters
                kr_model = KernelRegressor(kernel=kernel_type, sigma=sigma)
                kr_model.fit(X_train_inner, y_train_inner)
                
                # Evaluate on validation set
                y_val_pred = kr_model.predict(X_val_inner)
                inner_score = r2_score(y_val_inner, y_val_pred)
                inner_scores.append(inner_score)
            
            # Average inner CV score for this hyperparameter set
            avg_inner_score = np.mean(inner_scores)
            
            if avg_inner_score > best_r2:
                best_r2 = avg_inner_score
                best_sigma = sigma
            
            # Store the best sigma from this outer fold
            sigma_values.append(best_sigma)
            
            # Also evaluate the best model on the outer test fold
            kr_model = KernelRegressor(kernel=kernel_type, sigma=best_sigma)
            kr_model.fit(X_train_outer, y_train_outer)
            y_test_pred = kr_model.predict(X_test_outer)
            outer_r2 = r2_score(y_test_outer, y_test_pred)
            r2_scores.append(outer_r2)
        
        # Return the average R2 score across all outer folds
        return np.mean(r2_scores)
    
    # Create Optuna study
    study = optuna.create_study(direction='maximize')
    
    # Run Optuna optimization with defined number of trials
    print(f"Running Optuna optimization with {optuna_trials} trials...")
    start_time_optuna = time.time()
    study.optimize(objective, n_trials=optuna_trials)
    optimization_time = time.time() - start_time_optuna
    print(f"Optuna optimization completed in {optimization_time:.1f} seconds")
    
    # Get best parameters
    best_params = study.best_params
    print(f"Best kernel type: {best_params['kernel']}")
    print(f"Best sigma: {best_params['sigma']:.5f}")
    
    # Run final nested CV with best parameters to get robust estimate of sigma
    print(f"Running nested CV with best parameters to get final sigma...")
    
    # Use the existing nested_cv_kernel_regression function with a narrow range around best sigma
    sigma_values = np.linspace(best_params['sigma'] * 0.5, best_params['sigma'] * 1.5, num=20)
    
    # Import the kernel_regression_utils to get access to nested_cv_kernel_regression
    from emuses.tools.kernel_regression_utils import nested_cv_kernel_regression
    
    # Call nested_cv_kernel_regression without the kernel parameter since it's not expected
    outer_models, cv_perf, unseen_preds, sigma_values_list = nested_cv_kernel_regression(
        X=embeddings,
        y=VOI_vector,
        sigma_values=sigma_values,
        n_outer=5,
        n_inner=3,
        n_passes=3,  # Reduced number of passes since we already have a good sigma range
        convergence_tol=1e-3,
        classification=False
    )
    
    # Calculate final sigma using a robust approach
    # We use median instead of mean for better robustness to outliers
    final_sigma = float(np.median(sigma_values_list))
    print(f"Final sigma selected for GWD calculation: {final_sigma:.5f}")
    
    # Create a plot of the sigma values distribution
    plt.figure(figsize=(8, 5))
    plt.hist(sigma_values_list, bins=15)
    plt.axvline(final_sigma, color='red', linestyle='--', label=f'Final σ: {final_sigma:.5f}')
    plt.title('Distribution of Optimal Sigma Values Across Folds')
    plt.xlabel('Sigma Value')
    plt.ylabel('Frequency')
    plt.legend()
    plt.savefig(os.path.join(output_folder, 'sigma_distribution.png'))
    plt.close()

    # STEP 3: Compute the full GWD matrix
    print("Computing GWD matrix using final_sigma...")
    gwd_matrix = compute_all_gwd(embeddings, final_sigma)

    # STEP 4: Compute GWD summary features
    print("Computing GWD summary features...")
    gwd_summaries = compute_gwd_summary(embeddings, final_sigma, mode="basic")
    print(f"GWD summaries shape: {gwd_summaries.shape}")

    # STEP 5: Create multiple feature sets for evaluation
    print("Creating multiple feature sets for model evaluation...")
    
    # Prepare training feature subsets
    features_4 = np.hstack((embeddings, gwd_summaries))  # [embeddings (2) + GWD summaries (2)]
    features_3 = np.hstack((embeddings, gwd_summaries[:, :1]))  # [embeddings (2) + first summary (1)]
    features_2 = embeddings  # only embeddings
    features_gwd = gwd_summaries  # only GWD summaries

    # Use PCA to reduce dimensionality of the full GWD matrix
    print("Applying PCA to full GWD matrix...")
    from sklearn.decomposition import PCA
    pca = PCA(n_components=0.8, svd_solver='full')  # Select components for 80% variance
    pca_gwd_features = pca.fit_transform(gwd_matrix)
    print(f"PCA on full GWD vectors selected {pca.n_components_} components")

    # Store all feature sets in a dictionary
    feature_sets = {
        "combined_features": (features_4, "Combined Features (Embeddings + GWD summaries)"),
        "embeddings_with_ess": (features_3, "Embeddings + First GWD summary (ESS)"),
        "embeddings_only": (features_2, "Embeddings only"),
        "gwd_summaries_only": (features_gwd, "GWD summaries only"),
        "pca_gwd": (pca_gwd_features, f"PCA on Full GWD matrix [{pca.n_components_} components]")
    }
    
    # Create test feature sets if test data is available
    test_feature_sets = {}
    if test_embeddings is not None and test_labels is not None:
        print("Creating test feature sets...")
        # Compute test GWD summaries
        test_gwd_summaries = compute_gwd_summary(test_embeddings, final_sigma, mode="basic")
        test_features_4 = np.hstack((test_embeddings, test_gwd_summaries))
        test_features_3 = np.hstack((test_embeddings, test_gwd_summaries[:, :1]))
        test_features_2 = test_embeddings
        test_features_gwd = test_gwd_summaries

        # Compute full GWD for test data
        test_full_gwd = compute_all_gwd_test(test_embeddings, embeddings, final_sigma)
        # Transform with PCA fitted on training GWD
        test_pca_gwd_features = pca.transform(test_full_gwd)

        test_feature_sets = {
            "combined_features": test_features_4,
            "embeddings_with_ess": test_features_3,
            "embeddings_only": test_features_2,
            "gwd_summaries_only": test_features_gwd,
            "pca_gwd": test_pca_gwd_features
        }
    
    # STEP 6: Run parallel model optimization and training using Optuna
    print("\n===== Starting Parallel Model Optimization and Training =====")
    
    # Create a directory for model outputs
    models_dir = os.path.join(output_folder, "models")
    os.makedirs(models_dir, exist_ok=True)
    
    # Define function to optimize and train a single model on a feature set
    def optimize_train_model(feature_set_name, X_train, y_train, X_test=None, y_test=None):
        print(f"Starting optimization for {feature_set_name}...")
        feature_set_dir = os.path.join(models_dir, feature_set_name)
        os.makedirs(feature_set_dir, exist_ok=True)
        
        # Use the optuna_model_selection function to find the best model
        results = optuna_model_selection(
            X=X_train,
            y=y_train,
            n_trials=optuna_trials,
            n_jobs=1,  # Use 1 job here because we parallelize at a higher level
            output_folder=feature_set_dir,
            feature_set_name=feature_set_name,
            metric='r2',
            n_splits=5,
            random_state=42,
            models=model_selection
        )
        
        # If test data is available, evaluate on it
        if X_test is not None and y_test is not None:
            # Get predictions from the best model
            y_pred = results['best_model'].predict(X_test)
            
            # Calculate test metrics
            test_r2 = r2_score(y_test, y_pred)
            test_mse = mean_squared_error(y_test, y_pred)
            test_mae = mean_absolute_error(y_test, y_pred)
            
            # Store test results
            test_results = {
                'test_r2': test_r2,
                'test_mse': test_mse,
                'test_mae': test_mae,
                'normalized_mse': (test_mse / (global_range ** 2)) * 100 if global_range != 0 else test_mse,
                'normalized_mae': (test_mae / global_range) * 100 if global_range != 0 else test_mae
            }
            
            # Add test results to the overall results
            results.update({'test_metrics': test_results})
            
            # Create scatter plot of actual vs predicted values
            plt.figure(figsize=(10, 8))
            plt.scatter(y_test, y_pred, alpha=0.6)
            plt.plot([min(y_test), max(y_test)], [min(y_test), max(y_test)], 'r--')
            plt.xlabel('Actual Values')
            plt.ylabel('Predicted Values')
            plt.title(f'{feature_set_name} - {results["best_model_name"]}\nTest R²: {test_r2:.4f}')
            plt.savefig(os.path.join(feature_set_dir, f'test_predictions_{results["best_model_name"]}.png'))
            plt.close()
        
        # Save final results
        results_file = os.path.join(feature_set_dir, 'optimization_results.json')
        with open(results_file, 'w') as f:
            # Convert non-serializable objects to strings
            serializable_results = {k: (str(v) if not isinstance(v, (str, int, float, bool, list, dict)) else v) 
                                   for k, v in results.items() if k != 'best_model'}
            json.dump(serializable_results, f, indent=2)
        
        # Save the best model
        model_file = os.path.join(feature_set_dir, f'best_model_{results["best_model_name"]}.joblib')
        joblib.dump(results['best_model'], model_file)
        
        return feature_set_name, results
    
    # Prepare tasks for parallel execution
    parallel_tasks = []
    for fs_name, (fs_data, fs_desc) in feature_sets.items():
        if test_feature_sets and fs_name in test_feature_sets:
            # If test data is available
            test_fs_data = test_feature_sets[fs_name]
            if isinstance(test_labels, dict):
                # If test_labels is a dictionary, use the same key as training
                test_y = test_labels[key] if key in test_labels else None
            else:
                test_y = test_labels
            task = (fs_name, fs_data, VOI_vector, test_fs_data, test_y)
        else:
            # If no test data
            task = (fs_name, fs_data, VOI_vector, None, None)
        parallel_tasks.append(task)
    
    # Execute tasks in parallel or sequentially
    all_results = {}
    if run_parallel and n_jobs != 1:
        print(f"Running optimization in parallel with {n_jobs} jobs...")
        results = Parallel(n_jobs=n_jobs)(
            delayed(optimize_train_model)(fs_name, X, y, X_test, y_test) 
            for fs_name, X, y, X_test, y_test in parallel_tasks
        )
        all_results = dict(results)
    else:
        print("Running optimization sequentially...")
        for fs_name, X, y, X_test, y_test in parallel_tasks:
            fs_name, result = optimize_train_model(fs_name, X, y, X_test, y_test)
            all_results[fs_name] = result
    
    # STEP 7: Summarize and compare model performances
    print("\n===== Model Performance Summary =====")
    summary = {}
    
    # Create summary dataframes
    import pandas as pd
    summary_rows = []
    
    for fs_name, result in all_results.items():
        fs_desc = feature_sets[fs_name][1]
        best_model = result['best_model_name']
        cv_r2 = result['r2']
        
        # Get test metrics if available
        test_metrics = result.get('test_metrics', {})
        test_r2 = test_metrics.get('test_r2', 'N/A')
        
        # Add to summary rows
        row = {
            'Feature Set': fs_name,
            'Description': fs_desc,
            'Best Model': best_model,
            'CV R²': cv_r2,
            'Test R²': test_r2
        }
        summary_rows.append(row)
        
        # Add to summary dictionary
        summary[fs_name] = {
            'description': fs_desc,
            'best_model': best_model,
            'cv_r2': cv_r2,
            'test_metrics': test_metrics
        }
    
    # Create and save summary dataframe
    summary_df = pd.DataFrame(summary_rows)
    summary_df.sort_values(by='Test R²' if 'Test R²' in summary_df.columns and any(x != 'N/A' for x in summary_df['Test R²']) else 'CV R²', 
                          ascending=False, inplace=True)
    summary_df.to_csv(os.path.join(output_folder, 'model_performance_summary.csv'), index=False)
    
    # Print summary
    print("\nModel Performance Summary (sorted by performance):")
    print(summary_df)
    
    # Find best overall model and feature set
    if test_feature_sets:
        # Use test R² if available
        best_fs = max(summary.items(), key=lambda x: x[1]['test_metrics'].get('test_r2', -float('inf')) 
                      if x[1]['test_metrics'] else -float('inf'))[0]
    else:
        # Use CV R² otherwise
        best_fs = max(summary.items(), key=lambda x: x[1]['cv_r2'])[0]
    
    best_model_name = summary[best_fs]['best_model']
    print(f"\nBest overall combination: {best_fs} with {best_model_name}")
    print(f"Description: {summary[best_fs]['description']}")
    
    if test_feature_sets:
        test_metrics = summary[best_fs]['test_metrics']
        print(f"Test R²: {test_metrics['test_r2']:.4f}")
        print(f"Test MSE: {test_metrics['test_mse']:.4f}")
        print(f"Test MAE: {test_metrics['test_mae']:.4f}")
        print(f"Normalized MSE: {test_metrics['normalized_mse']:.2f}%")
        print(f"Normalized MAE: {test_metrics['normalized_mae']:.2f}%")
    
    # Create a bar chart comparing R² across feature sets
    plt.figure(figsize=(12, 6))
    if test_feature_sets and any('test_metrics' in result and result['test_metrics'] for result in all_results.values()):
        # Compare test R² if available
        bars = plt.bar(
            [feature_sets[fs_name][1] for fs_name in summary_df['Feature Set']],
            [summary[fs_name]['test_metrics']['test_r2'] if summary[fs_name]['test_metrics'] else 0 
             for fs_name in summary_df['Feature Set']]
        )
        plt.title('Test R² Comparison Across Feature Sets')
        plt.ylabel('Test R²')
    else:
        # Compare CV R² otherwise
        bars = plt.bar(
            [feature_sets[fs_name][1] for fs_name in summary_df['Feature Set']],
            [summary[fs_name]['cv_r2'] for fs_name in summary_df['Feature Set']]
        )
        plt.title('Cross-Validation R² Comparison Across Feature Sets')
        plt.ylabel('CV R²')
    
    # Add model names as text on the bars
    for i, bar in enumerate(bars):
        fs_name = summary_df['Feature Set'].iloc[i]
        plt.text(i, bar.get_height() + 0.01, summary[fs_name]['best_model'], 
                ha='center', va='bottom', rotation=0, fontsize=8)
    
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, 'feature_set_comparison.png'))
    plt.close()
    
    # STEP 8: Compute correlation heatmap
    print("\nComputing correlation heatmap...")
    correlation_heatmap, corr_grid_x, corr_grid_y = calculate_correlation_grid(
        embeddings=embeddings,
        train_labels=VOI_vector,
        grid_size=grid_size,
        sigma=final_sigma,
        correlation_method='pearson'
    )

    # Save the correlation heatmap
    plt.figure(figsize=(10, 8))
    plt.imshow(correlation_heatmap, extent=(corr_grid_x.min(), corr_grid_x.max(),
                                            corr_grid_y.min(), corr_grid_y.max()),
               aspect='auto', origin='lower', cmap='coolwarm')
    plt.colorbar(label='Pearson Correlation')
    plt.title('Correlation Heatmap')
    plt.xlabel('UMAP Dimension 1')
    plt.ylabel('UMAP Dimension 2')
    plt.savefig(os.path.join(output_folder, "correlation_heatmap.png"))
    plt.close()

    # STEP 9: Prepare and return final results
    total_time = time.time() - start_time
    print(f"\n===== Pipeline completed in {total_time:.1f} seconds ({total_time/60:.1f} minutes) =====")
    
    final_results = {
        'gwd_matrix': gwd_matrix,
        'gwd_summaries': gwd_summaries,
        'combined_features': features_4,
        'feature_sets': {name: data for name, (data, _) in feature_sets.items()},
        'pca_components': pca.n_components_,
        'pca_explained_variance': pca.explained_variance_ratio_.sum(),
        'correlation_heatmap': {
            'heatmap': correlation_heatmap,
            'grid_x': corr_grid_x,
            'grid_y': corr_grid_y
        },
        'final_sigma': final_sigma,
        'model_results': summary,
        'best_feature_set': best_fs,
        'best_model': best_model_name,
        'pipeline_time': total_time
    }
    
    # Save final results summary
    with open(os.path.join(output_folder, 'pipeline_results_summary.json'), 'w') as f:
        # Convert non-serializable objects to strings
        serializable_results = {
            k: (str(v) if not isinstance(v, (str, int, float, bool, list, dict)) else v)
            for k, v in final_results.items() 
            if k not in ['gwd_matrix', 'gwd_summaries', 'combined_features', 'feature_sets', 
                         'correlation_heatmap']
        }
        json.dump(serializable_results, f, indent=2)
    
    return final_results


def compute_all_gwd_test(test_embeddings, train_embeddings, sigma):
    """
    Compute the Gaussian weighted distances between test embeddings and training embeddings.
    
    Parameters:
        test_embeddings (np.ndarray): Array of shape (n_test, n_features)
        train_embeddings (np.ndarray): Array of shape (n_train, n_features)
        sigma (float): The Gaussian kernel bandwidth
        
    Returns:
        np.ndarray: Matrix of shape (n_test, n_train) with GWD values
    """
    from scipy.spatial.distance import cdist
    
    # Compute pairwise distances between test and training embeddings
    distances = cdist(test_embeddings, train_embeddings, metric='euclidean')
    
    # Apply Gaussian kernel
    gwd = np.exp(-0.5 * (distances / sigma) ** 2)
    
    return gwd


def optuna_model_selection(X, y, n_trials=50, n_jobs=1, output_folder=None, feature_set_name="features", metric='r2', n_splits=5, random_state=42, models=None):
    """
    Use Optuna to find the best model and hyperparameters for a given feature set.
    
    Parameters:
        X (np.ndarray): Feature matrix
        y (np.ndarray): Target vector
        n_trials (int): Number of Optuna trials
        n_jobs (int): Number of parallel jobs
        output_folder (str): Folder to save results
        feature_set_name (str): Name of the feature set (for logging)
        metric (str): Metric to optimize ('r2', 'mse', 'mae')
        n_splits (int): Number of cross-validation splits
        random_state (int): Random seed
        models (list): List of models to try. Options: 'gp', 'rf', 'gb', 'kr', 'xgb', 'lgb', 'et', 'svr'
                      If None, uses ['gp', 'rf', 'gb', 'kr', 'xgb']
    
    Returns:
        dict: Results dictionary containing best model, scores, and parameters
    """
    import numpy as np
    import optuna
    import time
    from sklearn.model_selection import cross_val_score, KFold
    from sklearn.metrics import make_scorer, r2_score, mean_squared_error, mean_absolute_error
    import matplotlib.pyplot as plt
    import os
    import joblib
    
    # Set default models if not provided
    if models is None:
        models = ['gp', 'rf', 'gb', 'kr', 'xgb']
    
    # Set up output folder
    if output_folder:
        os.makedirs(output_folder, exist_ok=True)
    
    # Define metric
    if metric == 'r2':
        scorer = make_scorer(r2_score)
        direction = 'maximize'
    elif metric == 'mse':
        scorer = make_scorer(mean_squared_error, greater_is_better=False)
        direction = 'minimize'
    elif metric == 'mae':
        scorer = make_scorer(mean_absolute_error, greater_is_better=False)
        direction = 'minimize'
    else:
        raise ValueError(f"Unknown metric: {metric}")
    
    # Define cross-validation
    cv = KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    
    # Define objective function
    def objective(trial):
        # Select model type
        model_type = trial.suggest_categorical('model_type', models)
        
        # Set model-specific hyperparameters
        if model_type == 'gp':
            # Gaussian Process
            from sklearn.gaussian_process import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import RBF, WhiteKernel, ConstantKernel, Matern, ExpSineSquared
            
            # Instead of using suggest_categorical, use a fixed option first and
            # set other parameters based on this fixed choice
            kernel_option = trial.suggest_categorical('kernel_option', ['rbf', 'matern'])
            
            if kernel_option == 'rbf':
                length_scale = trial.suggest_float('length_scale', 0.01, 10.0, log=True)
                kernel = RBF(length_scale=length_scale)
            else:  # matern
                length_scale = trial.suggest_float('length_scale', 0.01, 10.0, log=True)
                nu = trial.suggest_float('nu', 0.5, 2.5)
                kernel = Matern(length_scale=length_scale, nu=nu)
            
            # Add constant kernel
            use_constant = trial.suggest_categorical('use_constant', [True, False])
            if use_constant:
                constant_value = trial.suggest_float('constant_value', 0.1, 10.0, log=True)
                kernel = ConstantKernel(constant_value) * kernel
            
            # Add white kernel for noise
            use_white = trial.suggest_categorical('use_white', [True, False])
            if use_white:
                noise_level = trial.suggest_float('noise_level', 1e-10, 1.0, log=True)
                kernel += WhiteKernel(noise_level=noise_level)
            
            # Check if we need a sparse GP
            if X.shape[0] > 500:  # For larger datasets, use sparse GP
                alpha = trial.suggest_float('alpha', 1e-10, 1.0, log=True)
                model = GaussianProcessRegressor(kernel=kernel, alpha=alpha, random_state=random_state)
            else:
                alpha = trial.suggest_float('alpha', 1e-10, 1.0, log=True)
                model = GaussianProcessRegressor(kernel=kernel, alpha=alpha, random_state=random_state)
        
        elif model_type == 'rf':
            # Random Forest
            from sklearn.ensemble import RandomForestRegressor
            
            n_estimators = trial.suggest_int('n_estimators', 50, 300)
            max_depth = trial.suggest_int('max_depth', 3, 20)
            min_samples_split = trial.suggest_int('min_samples_split', 2, 20)
            min_samples_leaf = trial.suggest_int('min_samples_leaf', 1, 10)
            max_features = trial.suggest_categorical('max_features', ['sqrt', 'log2', None])
            
            model = RandomForestRegressor(
                n_estimators=n_estimators,
                max_depth=max_depth,
                min_samples_split=min_samples_split,
                min_samples_leaf=min_samples_leaf,
                max_features=max_features,
                random_state=random_state,
                n_jobs=1  # We're already parallelizing at a higher level
            )
        
        elif model_type == 'gb':
            # Gradient Boosting
            from sklearn.ensemble import GradientBoostingRegressor
            
            n_estimators = trial.suggest_int('n_estimators', 50, 300)
            learning_rate = trial.suggest_float('learning_rate', 0.01, 0.3, log=True)
            max_depth = trial.suggest_int('max_depth', 3, 10)
            min_samples_split = trial.suggest_int('min_samples_split', 2, 20)
            min_samples_leaf = trial.suggest_int('min_samples_leaf', 1, 10)
            subsample = trial.suggest_float('subsample', 0.5, 1.0)
            
            model = GradientBoostingRegressor(
                n_estimators=n_estimators,
                learning_rate=learning_rate,
                max_depth=max_depth,
                min_samples_split=min_samples_split,
                min_samples_leaf=min_samples_leaf,
                subsample=subsample,
                random_state=random_state
            )
        
        elif model_type == 'kr':
            # Kernel Regression (custom implementation)
            from emuses.tools.kernel_regression_utils import KernelRegressor
            
            kernel_type = trial.suggest_categorical('kernel_type', ['gaussian', 'epanechnikov', 'triangular'])
            sigma = trial.suggest_float('sigma', 0.01, 2.0, log=True)
            
            model = KernelRegressor(kernel=kernel_type, sigma=sigma)
        
        elif model_type == 'xgb':
            # XGBoost
            try:
                import xgboost as xgb
                
                n_estimators = trial.suggest_int('n_estimators', 50, 300)
                learning_rate = trial.suggest_float('learning_rate', 0.01, 0.3, log=True)
                max_depth = trial.suggest_int('max_depth', 3, 10)
                min_child_weight = trial.suggest_int('min_child_weight', 1, 10)
                subsample = trial.suggest_float('subsample', 0.5, 1.0)
                colsample_bytree = trial.suggest_float('colsample_bytree', 0.5, 1.0)
                
                model = xgb.XGBRegressor(
                    n_estimators=n_estimators,
                    learning_rate=learning_rate,
                    max_depth=max_depth,
                    min_child_weight=min_child_weight,
                    subsample=subsample,
                    colsample_bytree=colsample_bytree,
                    random_state=random_state,
                    n_jobs=1  # We're already parallelizing at a higher level
                )
            except ImportError:
                print("XGBoost not installed, skipping XGBoost model")
                return float('-inf') if direction == 'maximize' else float('inf')
        
        elif model_type == 'lgb':
            # LightGBM
            try:
                import lightgbm as lgb
                
                n_estimators = trial.suggest_int('n_estimators', 50, 300)
                learning_rate = trial.suggest_float('learning_rate', 0.01, 0.3, log=True)
                max_depth = trial.suggest_int('max_depth', 3, 10)
                num_leaves = trial.suggest_int('num_leaves', 10, 100)
                min_child_samples = trial.suggest_int('min_child_samples', 5, 50)
                subsample = trial.suggest_float('subsample', 0.5, 1.0)
                
                model = lgb.LGBMRegressor(
                    n_estimators=n_estimators,
                    learning_rate=learning_rate,
                    max_depth=max_depth,
                    num_leaves=num_leaves,
                    min_child_samples=min_child_samples,
                    subsample=subsample,
                    random_state=random_state,
                    n_jobs=1  # We're already parallelizing at a higher level
                )
            except ImportError:
                print("LightGBM not installed, skipping LightGBM model")
                return float('-inf') if direction == 'maximize' else float('inf')
        
        elif model_type == 'et':
            # Extra Trees
            from sklearn.ensemble import ExtraTreesRegressor
            
            n_estimators = trial.suggest_int('n_estimators', 50, 300)
            max_depth = trial.suggest_int('max_depth', 3, 20)
            min_samples_split = trial.suggest_int('min_samples_split', 2, 20)
            min_samples_leaf = trial.suggest_int('min_samples_leaf', 1, 10)
            max_features = trial.suggest_categorical('max_features', ['sqrt', 'log2', None])
            
            model = ExtraTreesRegressor(
                n_estimators=n_estimators,
                max_depth=max_depth,
                min_samples_split=min_samples_split,
                min_samples_leaf=min_samples_leaf,
                max_features=max_features,
                random_state=random_state,
                n_jobs=1  # We're already parallelizing at a higher level
            )
        
        elif model_type == 'svr':
            # Support Vector Regression
            from sklearn.svm import SVR
            
            kernel = trial.suggest_categorical('kernel', ['linear', 'poly', 'rbf', 'sigmoid'])
            C = trial.suggest_float('C', 0.1, 100.0, log=True)
            epsilon = trial.suggest_float('epsilon', 0.01, 1.0, log=True)
            
            if kernel in ['poly', 'rbf', 'sigmoid']:
                gamma = trial.suggest_categorical('gamma', ['scale', 'auto'])
                model = SVR(kernel=kernel, C=C, epsilon=epsilon, gamma=gamma)
            else:
                model = SVR(kernel=kernel, C=C, epsilon=epsilon)
        
        else:
            raise ValueError(f"Unknown model type: {model_type}")
        
        # Calculate cross-validation score
        try:
            scores = cross_val_score(model, X, y, cv=cv, scoring=scorer, n_jobs=1)
            
            if metric == 'r2':
                return np.mean(scores)
            else:  # MSE or MAE (lower is better)
                return -np.mean(scores)  # Negate because Optuna minimizes by default
        except Exception as e:
            print(f"Error in CV: {e}")
            return float('-inf') if direction == 'maximize' else float('inf')
    
    # Create study with pruner
    pruner = optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=5)
    study = optuna.create_study(direction=direction, pruner=pruner)
    
    # Run optimization
    start_time = time.time()
    study.optimize(objective, n_trials=n_trials, n_jobs=n_jobs)
    optimization_time = time.time() - start_time
    
    # Get best parameters and model
    best_params = study.best_params
    best_model_type = best_params['model_type']
    
    # Train the best model on all data
    print(f"\nBest model for {feature_set_name}: {best_model_type}")
    print(f"Best parameters: {best_params}")
    
    # Recreate and train the best model
    if best_model_type == 'gp':
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import RBF, WhiteKernel, ConstantKernel, Matern
        
        # Set up kernel
        if best_params['kernel_option'] == 'rbf':
            kernel = RBF(length_scale=best_params['length_scale'])
        else:  # matern
            kernel = Matern(length_scale=best_params['length_scale'], nu=best_params['nu'])
        
        # Add constant kernel if used
        if best_params.get('use_constant', False):
            kernel = ConstantKernel(best_params['constant_value']) * kernel
        
        # Add white kernel if used
        if best_params.get('use_white', False):
            kernel += WhiteKernel(noise_level=best_params['noise_level'])
        
        alpha = best_params['alpha']
        best_model = GaussianProcessRegressor(kernel=kernel, alpha=alpha, random_state=random_state)
    
    elif best_model_type == 'rf':
        from sklearn.ensemble import RandomForestRegressor
        
        best_model = RandomForestRegressor(
            n_estimators=best_params['n_estimators'],
            max_depth=best_params['max_depth'],
            min_samples_split=best_params['min_samples_split'],
            min_samples_leaf=best_params['min_samples_leaf'],
            max_features=best_params['max_features'],
            random_state=random_state,
            n_jobs=n_jobs
        )
    
    elif best_model_type == 'gb':
        from sklearn.ensemble import GradientBoostingRegressor
        
        best_model = GradientBoostingRegressor(
            n_estimators=best_params['n_estimators'],
            learning_rate=best_params['learning_rate'],
            max_depth=best_params['max_depth'],
            min_samples_split=best_params['min_samples_split'],
            min_samples_leaf=best_params['min_samples_leaf'],
            subsample=best_params['subsample'],
            random_state=random_state
        )
    
    elif best_model_type == 'kr':
        from emuses.tools.kernel_regression_utils import KernelRegressor
        
        best_model = KernelRegressor(
            kernel=best_params['kernel_type'],
            sigma=best_params['sigma']
        )
    
    elif best_model_type == 'xgb':
        import xgboost as xgb
        
        best_model = xgb.XGBRegressor(
            n_estimators=best_params['n_estimators'],
            learning_rate=best_params['learning_rate'],
            max_depth=best_params['max_depth'],
            min_child_weight=best_params['min_child_weight'],
            subsample=best_params['subsample'],
            colsample_bytree=best_params['colsample_bytree'],
            random_state=random_state,
            n_jobs=n_jobs
        )
    
    elif best_model_type == 'lgb':
        import lightgbm as lgb
        
        best_model = lgb.LGBMRegressor(
            n_estimators=best_params['n_estimators'],
            learning_rate=best_params['learning_rate'],
            max_depth=best_params['max_depth'],
            num_leaves=best_params['num_leaves'],
            min_child_samples=best_params['min_child_samples'],
            subsample=best_params['subsample'],
            random_state=random_state,
            n_jobs=n_jobs
        )
    
    elif best_model_type == 'et':
        from sklearn.ensemble import ExtraTreesRegressor
        
        best_model = ExtraTreesRegressor(
            n_estimators=best_params['n_estimators'],
            max_depth=best_params['max_depth'],
            min_samples_split=best_params['min_samples_split'],
            min_samples_leaf=best_params['min_samples_leaf'],
            max_features=best_params['max_features'],
            random_state=random_state,
            n_jobs=n_jobs
        )
    
    elif best_model_type == 'svr':
        from sklearn.svm import SVR
        
        if 'gamma' in best_params:
            best_model = SVR(
                kernel=best_params['kernel'],
                C=best_params['C'],
                epsilon=best_params['epsilon'],
                gamma=best_params['gamma']
            )
        else:
            best_model = SVR(
                kernel=best_params['kernel'],
                C=best_params['C'],
                epsilon=best_params['epsilon']
            )
    
    # Train the best model on all data
    best_model.fit(X, y)
    
    # Create cross-validation visualization
    if output_folder:
        # Plot optimization history
        plt.figure(figsize=(10, 6))
        optuna.visualization.matplotlib.plot_optimization_history(study)
        plt.title(f'Optimization History for {feature_set_name}')
        plt.tight_layout()
        plt.savefig(os.path.join(output_folder, f'optimization_history_{best_model_type}.png'))
        plt.close()
        
        # Plot parameter importances
        plt.figure(figsize=(10, 6))
        try:
            optuna.visualization.matplotlib.plot_param_importances(study)
            plt.title(f'Parameter Importances for {feature_set_name}')
            plt.tight_layout()
            plt.savefig(os.path.join(output_folder, f'param_importances_{best_model_type}.png'))
        except Exception as e:
            print(f"Error plotting parameter importances: {e}")
        plt.close()
        
        # Plot model comparison if multiple models were tried
        if len(models) > 1:
            model_scores = {}
            for trial in study.trials:
                model_type = trial.params.get('model_type')
                score = trial.value
                if model_type not in model_scores:
                    model_scores[model_type] = []
                model_scores[model_type].append(score)
            
            plt.figure(figsize=(10, 6))
            box_data = [model_scores[model] for model in model_scores.keys() if model_scores[model]]
            plt.boxplot(box_data, labels=[model for model in model_scores.keys() if model_scores[model]])
            plt.title(f'Model Comparison for {feature_set_name}')
            plt.ylabel('Score (higher is better)' if direction == 'maximize' else 'Score (lower is better)')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(os.path.join(output_folder, 'model_comparison.png'))
            plt.close()
    
    # Get cross-validation score for the best model
    cv_scores = cross_val_score(best_model, X, y, cv=cv, scoring=scorer, n_jobs=n_jobs)
    
    if metric == 'r2':
        final_score = np.mean(cv_scores)
    else:  # MSE or MAE
        final_score = -np.mean(cv_scores)
    
    print(f"Final {metric} score: {final_score}")
    print(f"Optimization time: {optimization_time:.2f} seconds")
    
    # Prepare results dictionary
    results = {
        'best_model': best_model,
        'best_model_name': best_model_type,
        'best_params': best_params,
        'cv_scores': cv_scores.tolist(),
        'r2': np.mean(cv_scores) if metric == 'r2' else None,
        'mse': -np.mean(cv_scores) if metric == 'mse' else None,
        'mae': -np.mean(cv_scores) if metric == 'mae' else None,
        'optimization_time': optimization_time,
        'feature_set': feature_set_name
    }
    
    return results


def compute_all_gwd(embeddings, sigma):
    """
    Compute the Gaussian weighted distances between all embeddings.
    
    Parameters:
        embeddings (np.ndarray): Array of shape (n_samples, n_features)
        sigma (float): The Gaussian kernel bandwidth
        
    Returns:
        np.ndarray: Matrix of shape (n_samples, n_samples) with GWD values
    """
    from scipy.spatial.distance import pdist, squareform
    
    n_samples = embeddings.shape[0]
    
    # Compute pairwise distances
    distances = squareform(pdist(embeddings, metric='euclidean'))
    
    # Apply Gaussian kernel
    gwd = np.exp(-0.5 * (distances / sigma) ** 2)
    
    return gwd


def compute_gwd_summary(embeddings, sigma, mode="basic"):
    """
    Compute summary features from the Gaussian weighted distances matrix.
    
    Parameters:
        embeddings (np.ndarray): Array of shape (n_samples, n_features)
        sigma (float): The Gaussian kernel bandwidth
        mode (str): Type of summary to compute ('basic', 'extended')
        
    Returns:
        np.ndarray: Matrix of shape (n_samples, n_summary_features) with summary features
    """
    import numpy as np
    
    # Compute the full GWD matrix
    gwd_matrix = compute_all_gwd(embeddings, sigma)
    
    # Basic summaries (always included)
    ess = np.sum(gwd_matrix, axis=1)  # Effective sample size
    entropy = -np.sum(gwd_matrix * np.log(gwd_matrix + 1e-10), axis=1)  # Entropy
    
    if mode == "basic":
        # Return only the basic summaries
        return np.column_stack((ess, entropy))
    
    elif mode == "extended":
        # Additional summary features
        mean_dist = np.mean(gwd_matrix, axis=1)  # Mean GWD
        median_dist = np.median(gwd_matrix, axis=1)  # Median GWD
        max_dist = np.max(gwd_matrix, axis=1)  # Max GWD
        min_dist = np.min(gwd_matrix, axis=1)  # Min GWD (excluding self)
        std_dist = np.std(gwd_matrix, axis=1)  # Standard deviation of GWD
        
        # Combine all summaries
        return np.column_stack((ess, entropy, mean_dist, median_dist, max_dist, min_dist, std_dist))
    
    else:
        raise ValueError(f"Unknown mode: {ode}")
