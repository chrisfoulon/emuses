from multiprocessing import Pool, cpu_count
import os
import pickle
from pathlib import Path

import matplotlib
from bcblib.tools.arrays_utils import separate_clusters_and_extract_coords, find_centroid_and_check
from narwhals.selectors import categorical
from scipy.stats import mannwhitneyu, ttest_ind, mode
from sklearn.linear_model import LinearRegression
from tqdm import tqdm
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, confusion_matrix, accuracy_score, \
    pairwise_distances
from sklearn.model_selection import KFold, GridSearchCV
import matplotlib.pyplot as plt
import seaborn as sns
from pykrige.rk import Krige
import xgboost as xgb


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

    # Check if one of the vectors is only zeros or if the length of one of them is smaller than 3
    if len(filtered_data) < 3 or len(other_data) < 3 or np.all(filtered_data == 0) or np.all(other_data == 0):
        return i, np.nan, np.nan, np.nan

    if test_name == 'mann-whitney':
        stat, pval = mannwhitneyu(filtered_data, other_data)
        # Convert U statistic to z-score
        n1 = len(filtered_data)
        n2 = len(other_data)
        mu_u = n1 * n2 / 2
        sigma_u = np.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
        z = (stat - mu_u) / sigma_u
        # Compute effect size
        r = z / np.sqrt(n1 + n2)
        return i, z, pval, r

    elif test_name == 't-test':
        n1 = len(filtered_data)
        n2 = len(other_data)
        stat, pval = ttest_ind(filtered_data, other_data, equal_var=False)
        # Compute effect size (Cohen's d) for unequal variances
        mean1, mean2 = np.mean(filtered_data), np.mean(other_data)
        std1, std2 = np.std(filtered_data, ddof=1), np.std(other_data, ddof=1)
        pooled_std = np.sqrt(((n1 - 1) * std1 ** 2 + (n2 - 1) * std2 ** 2) / (n1 + n2 - 2))
        cohen_d = (mean1 - mean2) / pooled_std
        return i, stat, pval, cohen_d

    else:
        raise ValueError(f"Invalid test name: {test_name}. Options are 'mann-whitney' and 't-test'.")


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
            pred_example = best_models[0].predict(test_coords)
            test_predictions_t = np.zeros_like(pred_example)
            for model in best_models:
                test_predictions_t += model.predict(test_coords)
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


def compute_gaussian_filter(embeddings, coord, sigma=1.0):
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
