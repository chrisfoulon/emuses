from multiprocessing import Pool, cpu_count
import os
import pickle
from pathlib import Path

import GPy
import matplotlib
from bcblib.tools.arrays_utils import separate_clusters_and_extract_coords, find_centroid_and_check
from narwhals.selectors import categorical
from scipy.stats import mannwhitneyu, ttest_ind, mode, entropy
from sklearn.linear_model import LinearRegression
from tqdm import tqdm
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, confusion_matrix, accuracy_score, \
    pairwise_distances, f1_score, precision_score, recall_score
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
        X_val = combined_features[val_idx]
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
                      test_embeddings=None, test_labels=None, sparse_threshold=500):
    """
    Placeholder pipeline function to test the new modular functions.

    This function:
      1. Extracts the VOI_vector from scores_vectors_dict.
      2. Runs robust nested CV (with iterative passes to narrow the sigma candidates)
         on the UMAP embeddings and VOI_vector to obtain candidate sigma values.
      3. Aggregates these candidate sigma values (using the median) as final_sigma.
      4. Uses final_sigma to compute the full GWD matrix and summary features.
      5. Forms combined_features by concatenating UMAP embeddings with GWD summaries.
      6. Creates a grid over the latent space.
      7. Evaluates performance (either on a held-out test set or via aggregated CV metrics).
      8. Computes and saves a Pearson correlation heatmap.
      9. Trains a predictive model using GPy (either regression or classification) on
         the combined_features and VOI_vector.
     10. Reports OOD performance from the GP model.

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

    Returns:
        dict: A dictionary containing outputs including the GWD matrix, summaries, combined features,
              grid coordinates, a heatmap dictionary, CV performance, final_sigma, test performance,
              and GP predictive model details.
    """
    import os
    from matplotlib import pyplot as plt
    import numpy as np
    from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
    # Import functions from elsewhere in the codebase.
    from emuses.tools.kernel_regression_utils import nested_cv_kernel_regression, ensemble_predict
    from emuses.tools.correlation_maps_utils import calculate_correlation_grid
    # Assume these functions are defined or imported:
    #   compute_all_gwd, compute_gwd_summary

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

    # For normalization.
    global_range = np.max(VOI_vector) - np.min(VOI_vector)

    # STEP 2: Run robust nested CV to obtain candidate sigma values.
    sigma_candidates = np.linspace(0.001, 0.5, num=50)
    outer_models, cv_perf, unseen_preds, sigma_values_list = nested_cv_kernel_regression(
        X=embeddings,
        y=VOI_vector,
        sigma_values=sigma_candidates,
        n_outer=5,
        n_inner=5,
        n_passes=5,  # iterative passes to refine candidate range
        convergence_tol=1e-3,  # tolerance for convergence
        classification=False
    )
    final_sigma = float(np.median(sigma_values_list))
    print("Final sigma selected for GWD calculation:", final_sigma)

    # STEP 3: Compute the full GWD matrix.
    print("Computing GWD matrix using final_sigma...")
    gwd_matrix = compute_all_gwd(embeddings, final_sigma)

    # STEP 4: Compute GWD summary features.
    print("Computing GWD summary features...")
    gwd_summaries = compute_gwd_summary(embeddings, final_sigma, mode="basic")
    print("GWD summaries shape:", gwd_summaries.shape)

    # STEP 5: Form combined feature matrix.
    combined_features = np.hstack((embeddings, gwd_summaries))
    print("Combined features shape (UMAP + GWD summary):", combined_features.shape)

    # Plot a histogram of the first summary feature.
    plt.figure()
    plt.hist(gwd_summaries[:, 0], bins=30)
    plt.title("Histogram of Effective Number of Neighbors (ESS)")
    plt.savefig(os.path.join(output_folder, "ess_histogram.png"))
    plt.close()

    # STEP 6: Create grid over the latent space.
    min_coords = np.min(embeddings, axis=0)
    max_coords = np.max(embeddings, axis=0)
    grid_x = np.linspace(min_coords[0], max_coords[0], grid_size)
    grid_y = np.linspace(min_coords[1], max_coords[1], grid_size)

    # STEP 7: Evaluate performance.
    test_performance = None
    if (test_embeddings is not None) and (test_labels is not None):
        if test_labels.ndim > 1:
            try:
                col_index = int(key.split('_')[1])
            except Exception:
                col_index = 0
            test_labels = test_labels[:, col_index]
        mean_pred, std_pred = ensemble_predict(outer_models, test_embeddings)
        r2 = r2_score(test_labels, mean_pred)
        mse = mean_squared_error(test_labels, mean_pred)
        mae = mean_absolute_error(test_labels, mean_pred)
        normalized_mse = (mse / (global_range ** 2)) * 100 if global_range != 0 else mse
        normalized_mae = (mae / global_range) * 100 if global_range != 0 else mae
        test_performance = {'r2': r2, 'mse': mse, 'mae': mae,
                            'normalized_mse_%': normalized_mse, 'normalized_mae_%': normalized_mae}
        print("Held-out Test Performance:", test_performance)
    else:
        if cv_perf and len(cv_perf) > 0:
            r2_vals = [perf.get('r2') for perf in cv_perf if 'r2' in perf]
            mse_vals = [perf.get('mse') for perf in cv_perf if 'mse' in perf]
            mae_vals = [perf.get('mae') for perf in cv_perf if 'mae' in perf]
            avg_r2 = np.mean(r2_vals) if r2_vals else None
            avg_mse = np.mean(mse_vals) if mse_vals else None
            avg_mae = np.mean(mae_vals) if mae_vals else None
            normalized_mse = (avg_mse / (
                        global_range ** 2)) * 100 if global_range != 0 and avg_mse is not None else avg_mse
            normalized_mae = (avg_mae / global_range) * 100 if global_range != 0 and avg_mae is not None else avg_mae
            test_performance = {'avg_r2_cv': avg_r2, 'avg_mse_cv': avg_mse, 'avg_mae_cv': avg_mae,
                                'normalized_mse_cv_%': normalized_mse, 'normalized_mae_cv_%': normalized_mae}
            print("Aggregated CV Performance:", test_performance)
        else:
            print("No validation performance available from CV.")

    # STEP 8: Compute Pearson correlation heatmap.
    correlation_heatmap, corr_grid_x, corr_grid_y = calculate_correlation_grid(
        embeddings=embeddings,
        train_labels=VOI_vector,
        grid_size=grid_size,
        sigma=final_sigma,
        correlation_method='pearson'
    )

    # Save the correlation heatmap.
    plt.figure()
    plt.imshow(correlation_heatmap, extent=(corr_grid_x.min(), corr_grid_x.max(),
                                            corr_grid_y.min(), corr_grid_y.max()),
               aspect='auto', origin='lower')
    plt.colorbar(label='Pearson Correlation')
    plt.title('Correlation Heatmap')
    plt.xlabel('UMAP X')
    plt.ylabel('UMAP Y')
    plt.savefig(os.path.join(output_folder, "correlation_heatmap.png"))
    plt.close()

    heatmap_dict = {
        'prediction_heatmap': None,
        'uncertainty_heatmap': None,
        'correlation_heatmap': {
            'heatmap': correlation_heatmap,
            'grid_x': corr_grid_x,
            'grid_y': corr_grid_y
        }
    }

    cv_performance_all = cv_perf if cv_perf else []

    # Display a summary.
    print("===== New Pipeline Test Summary =====")
    print(f"Final sigma for GWD: {final_sigma:.4f}")
    print("GWD matrix shape:", gwd_matrix.shape)
    print("GWD summaries shape:", gwd_summaries.shape)
    print("Combined features shape:", combined_features.shape)
    print("Grid X shape:", grid_x.shape, "Grid Y shape:", grid_y.shape)
    if test_performance:
        print("Performance metrics:")
        for metric, value in test_performance.items():
            print(f"  {metric}: {value:.4f}")
    else:
        print("No performance metrics evaluated.")
    print("===== End of Summary =====")

    # === STEP 9: Train predictive GP models with different feature sets ===
    import os
    import json
    from matplotlib import pyplot as plt
    from sklearn.decomposition import PCA
    from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

    # Define a function that computes a GWD matrix for the test set.
    # This computes a Gaussian weighted distance from each test sample to each train sample.
    def compute_all_gwd_test(test_embeddings, train_embeddings, sigma):
        from scipy.spatial.distance import cdist
        dists = cdist(test_embeddings, train_embeddings, metric='euclidean')
        return np.exp(-0.5 * (dists / sigma) ** 2)

    # Prepare training feature subsets.
    # (Assume: `embeddings` are your training UMAP embeddings, and `gwd_summaries` have been computed already.)
    features_4 = combined_features  # [embeddings (2) + GWD summaries (2)]
    features_3 = np.hstack((embeddings, gwd_summaries[:, :1]))  # [embeddings (2) + first summary (1)]
    features_2 = embeddings  # only embeddings
    features_gwd = gwd_summaries  # only GWD summaries

    # Fifth experiment: Use the full GWD matrix.
    # Each training sample’s GWD vector is its corresponding row in the gwd_matrix.
    # Note: gwd_matrix is (n_train, n_train); if n_train is large, you may consider further dimensionality reduction.
    full_gwd_vectors = gwd_matrix

    # Now, apply PCA to the full GWD vectors and choose enough components to explain at least 80% of the variance.
    pca = PCA(n_components=0.8,
              svd_solver='full')  # n_components as float selects the number of components needed for 80% var.
    pca_gwd_features = pca.fit_transform(full_gwd_vectors)
    print("PCA on full GWD vectors selected components:", pca.n_components_)

    # Put the feature sets into a dictionary.
    feature_sets = {
        "GP_4features": (features_4, "Combined Features (Embeddings + GWD summaries)"),
        "GP_3features": (features_3, "Embeddings + First GWD summary"),
        "GP_2features": (features_2, "Embeddings only"),
        "GP_GWDonly": (features_gwd, "GWD summaries only"),
        "GP_PCA_GWD": (pca_gwd_features, f"PCA on Full GWD vectors [{pca.n_components_} components]")
    }

    # Next, create the corresponding test feature sets.
    test_feature_sets = {}
    if test_embeddings is not None and test_labels is not None:
        # First, compute test GWD summaries for the test set.
        test_gwd_summaries = compute_gwd_summary(test_embeddings, final_sigma, mode="basic")
        test_features_4 = np.hstack((test_embeddings, test_gwd_summaries))
        test_features_3 = np.hstack((test_embeddings, test_gwd_summaries[:, :1]))
        test_features_2 = test_embeddings
        test_features_gwd = test_gwd_summaries

        # For the PCA on full GWD vectors experiment:
        # We must compute the full GWD vectors for each test sample relative to the training embeddings.
        test_full_gwd_vectors = compute_all_gwd_test(test_embeddings, embeddings, final_sigma)
        # Then project them using the PCA fitted on training full GWD vectors.
        test_pca_gwd_features = pca.transform(test_full_gwd_vectors)

        test_feature_sets = {
            "GP_4features": test_features_4,
            "GP_3features": test_features_3,
            "GP_2features": test_features_2,
            "GP_GWDonly": test_features_gwd,
            "GP_PCA_GWD": test_pca_gwd_features
        }
    else:
        print("Test embeddings/labels not provided; skipping test set evaluation for GP models.")

    # Train a GP model on each feature set and evaluate test performance.
    gp_performance_all = {}

    for fs_key, (train_fs, desc) in feature_sets.items():
        print(f"\n=== Training GP model using {desc} ===")
        # Train GP model using your provided GPy-based function.
        gp_model = train_predictive_model_gpy(
            X=train_fs,
            y=VOI_vector.reshape(-1, 1),
            is_classification=False,
            sparse_threshold=sparse_threshold
        )
        print(f"{fs_key}: GP Model trained.")

        # If test features are available, predict and compute performance.
        if test_feature_sets and fs_key in test_feature_sets:
            test_fs = test_feature_sets[fs_key]
            # For GPy, the predict method returns (mean, variance).
            gp_mean, gp_variance = gp_model.predict(test_fs)
            gp_predictions = gp_mean.ravel()
            gp_std = np.sqrt(gp_variance.ravel())

            # Compute metrics.
            gp_r2 = r2_score(test_labels, gp_predictions)
            gp_mse = mean_squared_error(test_labels, gp_predictions)
            gp_mae = mean_absolute_error(test_labels, gp_predictions)
            gp_perf = {'gp_r2': gp_r2, 'gp_mse': gp_mse, 'gp_mae': gp_mae}
            gp_performance_all[fs_key] = gp_perf
            print(f"{fs_key} Test Performance: {gp_perf}")
        else:
            print(f"{fs_key}: No test features provided; skipping performance evaluation.")

    # Optionally, save the performance results.
    output_perf_path = os.path.join(output_folder, "gp_performance_summary.json")
    with open(output_perf_path, "w") as f:
        json.dump(gp_performance_all, f, indent=4)
    print("Saved GP performance summary to", output_perf_path)

    # Finally, add the GP performance results to the outputs of the pipeline.
    final_results = {
        'gwd_matrix': gwd_matrix,
        'gwd_summaries': gwd_summaries,
        'combined_features': combined_features,
        'grid_x': grid_x,
        'grid_y': grid_y,
        'heatmap_dict': heatmap_dict,
        'cv_performance': cv_perf if cv_perf is not None else [],
        'final_sigma': final_sigma,
        'test_performance': test_performance,
        'gp_performance': gp_performance_all
    }

    return final_results