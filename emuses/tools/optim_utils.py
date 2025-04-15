import numpy as np
import os
import time
import json

# Optuna imports
import optuna
from optuna.integration import OptunaSearchCV

# Scikit-learn imports
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import (RBF, Matern, WhiteKernel, 
                                             ConstantKernel, RationalQuadratic)
from sklearn.model_selection import KFold, cross_val_score
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

# Joblib imports
from joblib import dump, Parallel, delayed

# Local imports
# (emuses.tools.kernel_regression_utils will be imported where needed)


def suggest_parameters(trial, optim_dict):
    """
    Suggest parameters for UMAP and clustering based on the optim_dict.

    Parameters:
        trial (optuna.trial): Current trial object.
        optim_dict (dict): Dictionary defining the optimization configuration.

    Returns:
        dict: Suggested parameters for UMAP and clustering.
    """
    params = {}
    for model, model_params in optim_dict['param'].items():
        params[model] = {}
        for name, details in model_params.items():
            if not isinstance(details, dict):
                # TODO do we need some sanity checks here?
                params[model][name] = details
            elif 'value' in details:  # Fixed parameter
                params[model][name] = details['value']
            elif 'choices' in details:  # Categorical parameter
                params[model][name] = trial.suggest_categorical(
                    name=details['name'], choices=details['choices']
                )
            elif any(isinstance(details[key], float) for key in ['low', 'high', 'step'] if key in details):
                params[model][name] = trial.suggest_float(
                    name=details['name'],
                    low=details['low'],
                    high=details['high'],
                    step=details.get('step'),
                    log=details.get('log', False)
                )
            else:  # Integer parameter
                params[model][name] = trial.suggest_int(
                    name=details['name'],
                    low=details['low'],
                    high=details['high'],
                    step=details.get('step', 1),
                    log=details.get('log', False)
                )
    return params


def are_parameters_fixed(params_dict):
    """
    Returns True if every parameter in params_dict is fixed,
    i.e. if every parameter (assumed to be a dict) has a 'value' key,
    and does not have a 'low' or 'choices' entry.
    """
    for key, param in params_dict.items():
        if isinstance(param, dict):
            if 'value' in param:
                continue
            if 'low' in param or 'choices' in param:
                return False
        # If the parameter is not a dict, we assume it's fixed.
    return True



def auto_n_neighbors(n_samples, lower_bound=10, upper_bound=200):
    """
    Automatically compute a default number of neighbors based on the number of samples.

    Parameters:
        n_samples (int): Total number of data points.
        lower_bound (int): Minimum number of neighbors.
        upper_bound (int): Maximum number of neighbors.

    Returns:
        int: A recommended number of neighbors.
    """
    return int(max(lower_bound, min(upper_bound, np.sqrt(n_samples))))


def calculate_composite_score(metrics_values_nested, metrics_config_nested):
    """
    Calculate a composite score from computed metric values using a nested configuration.

    The expected format for both dictionaries is:

        metrics_values_nested = {
            "umap": {"spread": value1, "density_variability": value2, "entropy": value3},
            "hdbscan": {"cluster_persistence": value4, "noise_ratio": value5, "validity_index": value6}
        }

        metrics_config_nested = {
            "umap": {
                "spread": {"weight": w1, "target": t1, "epsilon": e1},          # Use hard mode if "epsilon" is provided.
                "density_variability": {"weight": w2, "target": t2, "min_penalty": mp2},  # Use linear mode if "min_penalty" is provided.
                "entropy": {"weight": w3, "target": t3, "epsilon": e3}           # Hard mode example.
            },
            "hdbscan": {
                "cluster_persistence": {"weight": w4},                          # No target; just raw contribution.
                "noise_ratio": {"weight": w5, "target": t5, "min_penalty": mp5},  # Linear mode.
                "validity_index": {"weight": w6}                                 # No target.
            }
        }

    For each metric with a target:
      - If "epsilon" is present, the component is computed as:
            weight * max(0, 1 - abs(metric_value - target) / epsilon)
      - If "min_penalty" is present (and epsilon is not), we assume a linear scaling. Assuming the metric is in [0,1],
        compute the maximum possible deviation as:
            max_dev = max(target, 1 - target)
        Then compute the normalized difference:
            normalized_diff = abs(metric_value - target) / max_dev
        And define a penalty that linearly scales from 1 (when deviation is 0) to min_penalty (when deviation is maximal):
            penalty = min_penalty + (1 - min_penalty) * (1 - normalized_diff)
        The component becomes:
            weight * metric_value * penalty

    For metrics without a target, the component is simply weight * metric_value.

    The final composite score is the sum of all components normalized by the sum of weights.

    Returns:
        float: Normalized composite score between 0 and 1.
    """
    total_score = 0.0
    total_weight = 0.0

    # Iterate over each group (e.g., "umap", "hdbscan")
    for group, config_dict in metrics_config_nested.items():
        values_dict = metrics_values_nested.get(group, {})
        for metric_name, config in config_dict.items():
            weight = config.get("weight", 1.0)
            value = values_dict.get(metric_name)
            if value is None:
                continue

            target = config.get("target")
            if target is not None:
                # If an "epsilon" key is present, use hard mode:
                if "epsilon" in config:
                    epsilon = config["epsilon"]
                    component = weight * max(0, 1 - abs(value - target) / epsilon)
                # Else if "min_penalty" is present, use linear scaling:
                elif "min_penalty" in config:
                    min_penalty = config["min_penalty"]
                    max_dev = max(target, 1 - target)
                    normalized_diff = abs(value - target) / max_dev if max_dev > 0 else 0
                    penalty = min_penalty + (1 - min_penalty) * (1 - normalized_diff)
                    component = weight * value * penalty
                else:
                    # Fallback: if target is specified but no scaling parameter, simply use weight * value.
                    component = weight * value
            else:
                component = weight * value

            total_score += component
            total_weight += weight

    return total_score / total_weight if total_weight > 0 else 0.0


def calculate_score(metrics, metrics_config):
    """
    Calculate a composite score from the computed metrics.
    For each metric, if a target and epsilon are specified, compute a score component as:
       weight * max(0, 1 - abs(value - target)/epsilon)
    Otherwise, just use weight * value.
    Sum over metrics.
    """
    composite_score = 0.0
    for metric_name, config in metrics_config.items():
        value = metrics.get(metric_name, 0)
        if "target" in config and "epsilon" in config:
            diff = abs(value - config["target"])
            # This formulation assumes that exceeding the epsilon will yield a zero (or negative) contribution.
            component = config["weight"] * max(0, 1 - diff / config["epsilon"])
        else:
            component = config["weight"] * value
        composite_score += component
    return composite_score


def compute_detailed_components(metrics_config, computed_metrics):
    """
    Compute detailed metric contributions from a configuration dictionary and computed metric values.

    Parameters:
        metrics_config (dict): Dictionary of metric configurations (each containing keys like 'weight', and optionally 'target', 'epsilon', or 'min_penalty').
        computed_metrics (dict): Dictionary of computed metric values.

    Returns:
        dict: Detailed contributions for each metric.
    """
    detailed = {}
    for metric, config in metrics_config.items():
        # Get the computed value, defaulting to 0 if missing.
        value = computed_metrics.get(metric)
        if value is None:
            print(f"Warning: Metric '{metric}' is missing; defaulting its value to 0.")
            value = 0
        target = config.get("target")
        if target is not None:
            if "epsilon" in config:
                component = config["weight"] * max(0, 1 - abs(value - target) / config["epsilon"])
            elif "min_penalty" in config:
                max_dev = max(target, 1 - target)
                normalized_diff = abs(value - target) / max_dev if max_dev > 0 else 0
                penalty = config["min_penalty"] + (1 - config["min_penalty"]) * (1 - normalized_diff)
                component = config["weight"] * value * penalty
            else:
                component = config["weight"] * value
        else:
            component = config["weight"] * value
        detailed[metric] = component
    return detailed


def optuna_model_selection(X, y, n_trials=100, n_jobs=-1, output_folder=None, feature_set_name=None,
                          metric='r2', n_splits=5, random_state=42, models=None):
    """
    Use Optuna to find the best model and hyperparameters for a regression task.
    
    Parameters:
    -----------
    X : numpy.ndarray
        Feature matrix
    y : numpy.ndarray
        Target values
    n_trials : int
        Number of Optuna trials to run
    n_jobs : int
        Number of parallel jobs for Optuna
    output_folder : str or Path
        Folder to save results
    feature_set_name : str
        Name of the feature set (for logging)
    metric : str
        Evaluation metric ('r2', 'neg_mean_squared_error', 'neg_mean_absolute_error')
    n_splits : int
        Number of cross-validation splits
    random_state : int
        Random seed for reproducibility
    models : list or None
        List of model types to try. If None, tries ['gp', 'rf', 'gb', 'kr']
        
    Returns:
    --------
    dict
        Results containing best model, parameters, and performance metrics
    """
    if models is None:
        models = ['gp', 'rf', 'gb', 'kr']
    
    # Set up cross-validation
    cv = KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    
    # Make sure y is 1D for sklearn compatibility
    if len(y.shape) > 1 and y.shape[1] == 1:
        y = y.ravel()
    
    # Define the objective function for Optuna
    def objective(trial):
        # Select model type
        model_name = trial.suggest_categorical('model_type', models)
        
        # Configure hyperparameters based on model type
        if model_name == 'gp':
            # GP model selection
            kernel_type = trial.suggest_categorical('kernel_type', ['rbf', 'matern', 'rational_quadratic'])
            noise_level = trial.suggest_float('noise_level', 1e-5, 1.0, log=True)
            
            if kernel_type == 'rbf':
                length_scale = trial.suggest_float('length_scale', 0.1, 10.0, log=True)
                kernel = RBF(length_scale=length_scale)
            elif kernel_type == 'matern':
                length_scale = trial.suggest_float('length_scale', 0.1, 10.0, log=True)
                nu = trial.suggest_categorical('nu', [0.5, 1.5, 2.5])
                kernel = Matern(length_scale=length_scale, nu=nu)
            else:  # rational quadratic
                length_scale = trial.suggest_float('length_scale', 0.1, 10.0, log=True)
                alpha = trial.suggest_float('alpha', 0.1, 2.0)
                kernel = RationalQuadratic(length_scale=length_scale, alpha=alpha)
                
            # Add white kernel for noise
            kernel = kernel + WhiteKernel(noise_level=noise_level)
            
            # Create GPR model
            model = GaussianProcessRegressor(
                kernel=kernel,
                n_restarts_optimizer=trial.suggest_int('n_restarts', 3, 10),
                random_state=random_state
            )
            
        elif model_name == 'rf':
            # Random Forest hyperparameters
            model = RandomForestRegressor(
                n_estimators=trial.suggest_int('n_estimators', 50, 500),
                max_depth=trial.suggest_int('max_depth', 3, 30),
                min_samples_split=trial.suggest_int('min_samples_split', 2, 20),
                min_samples_leaf=trial.suggest_int('min_samples_leaf', 1, 10),
                max_features=trial.suggest_categorical('max_features', ['sqrt', 'log2', None]),
                bootstrap=trial.suggest_categorical('bootstrap', [True, False]),
                random_state=random_state,
                n_jobs=1  # Use 1 here since we parallelize at the Optuna level
            )
            
        elif model_name == 'gb':
            # Gradient Boosting hyperparameters
            model = GradientBoostingRegressor(
                n_estimators=trial.suggest_int('n_estimators', 50, 500),
                learning_rate=trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                max_depth=trial.suggest_int('max_depth', 3, 15),
                min_samples_split=trial.suggest_int('min_samples_split', 2, 20),
                min_samples_leaf=trial.suggest_int('min_samples_leaf', 1, 10),
                subsample=trial.suggest_float('subsample', 0.6, 1.0),
                max_features=trial.suggest_categorical('max_features', ['sqrt', 'log2', None]),
                random_state=random_state
            )
            
        elif model_name == 'kr':
            # Kernel Regression hyperparameters
            kernel = trial.suggest_categorical('kernel', ['gaussian', 'epanechnikov', 'triangular'])
            bandwidth = trial.suggest_float('bandwidth', 0.01, 2.0, log=True)
            
            from emuses.tools.kernel_regression_utils import KernelRegressor
            model = KernelRegressor(kernel=kernel, sigma=bandwidth)
        
        # Evaluate with cross-validation
        if metric == 'r2':
            score = cross_val_score(model, X, y, cv=cv, scoring='r2', n_jobs=1)
            return np.mean(score)  # Higher is better
        elif metric == 'neg_mean_squared_error':
            score = cross_val_score(model, X, y, cv=cv, scoring='neg_mean_squared_error', n_jobs=1)
            return np.mean(score)  # Higher (less negative) is better
        elif metric == 'neg_mean_absolute_error':
            score = cross_val_score(model, X, y, cv=cv, scoring='neg_mean_absolute_error', n_jobs=1)
            return np.mean(score)  # Higher (less negative) is better
    
    # Create Optuna study
    study = optuna.create_study(direction='maximize')
    
    # Execute optimization
    start_time = time.time()
    study.optimize(objective, n_trials=n_trials, n_jobs=n_jobs)
    optimization_time = time.time() - start_time
    
    # Get best parameters and model
    best_params = study.best_params
    best_model_name = best_params['model_type']
    
    # Create the best model with optimized hyperparameters
    if best_model_name == 'gp':
        if best_params['kernel_type'] == 'rbf':
            kernel = RBF(length_scale=best_params['length_scale'])
        elif best_params['kernel_type'] == 'matern':
            kernel = Matern(length_scale=best_params['length_scale'], nu=best_params['nu'])
        else:  # rational quadratic
            kernel = RationalQuadratic(length_scale=best_params['length_scale'], alpha=best_params['alpha'])
            
        kernel = kernel + WhiteKernel(noise_level=best_params['noise_level'])
        
        best_model = GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=best_params['n_restarts'],
            random_state=random_state
        )
        
    elif best_model_name == 'rf':
        best_model = RandomForestRegressor(
            n_estimators=best_params['n_estimators'],
            max_depth=best_params['max_depth'],
            min_samples_split=best_params['min_samples_split'],
            min_samples_leaf=best_params['min_samples_leaf'],
            max_features=best_params['max_features'],
            bootstrap=best_params['bootstrap'],
            random_state=random_state,
            n_jobs=n_jobs  # Use all cores for the final model
        )
        
    elif best_model_name == 'gb':
        best_model = GradientBoostingRegressor(
            n_estimators=best_params['n_estimators'],
            learning_rate=best_params['learning_rate'],
            max_depth=best_params['max_depth'],
            min_samples_split=best_params['min_samples_split'],
            min_samples_leaf=best_params['min_samples_leaf'],
            subsample=best_params['subsample'],
            max_features=best_params['max_features'],
            random_state=random_state
        )
        
    elif best_model_name == 'kr':
        from emuses.tools.kernel_regression_utils import KernelRegressor
        best_model = KernelRegressor(kernel=best_params['kernel'], sigma=best_params['bandwidth'])
    
    # Train on the full dataset
    best_model.fit(X, y)
    
    # Evaluate on the full dataset
    y_pred = best_model.predict(X)
    r2 = r2_score(y, y_pred)
    mse = mean_squared_error(y, y_pred)
    mae = mean_absolute_error(y, y_pred)
    
    # Prepare results
    results = {
        'best_model_name': best_model_name,
        'best_params': best_params,
        'best_model': best_model,
        'best_trial': study.best_trial,
        'best_value': study.best_value,
        'r2': r2,
        'mse': mse,
        'mae': mae,
        'optimization_time': optimization_time,
        'n_trials': n_trials,
        'feature_set_name': feature_set_name
    }
    
    # Save results if output folder is provided
    if output_folder is not None:
        # Create folder if it doesn't exist
        os.makedirs(output_folder, exist_ok=True)
        
        # Generate filename based on feature set
        if feature_set_name:
            model_file = os.path.join(output_folder, f"best_model_{feature_set_name}.joblib")
            results_file = os.path.join(output_folder, f"model_selection_results_{feature_set_name}.json")
        else:
            model_file = os.path.join(output_folder, "best_model.joblib")
            results_file = os.path.join(output_folder, "model_selection_results.json")
        
        # Save model
        dump(best_model, model_file)
        
        # Save results (excluding model object)
        results_json = {k: v for k, v in results.items() if k != 'best_model'}
        with open(results_file, 'w') as f:
            json.dump(results_json, f, indent=2)
    
    return results


def optuna_feature_set_comparison(X_sets, y, output_folder, feature_set_names=None,
                                n_trials=100, n_jobs=-1, metric='r2', n_splits=5, 
                                random_state=42, models=None):
    """
    Compare different feature sets using Optuna to find the best model for each.
    
    Parameters:
    -----------
    X_sets : list of numpy.ndarray
        List of feature matrices to compare
    y : numpy.ndarray
        Target values
    output_folder : str or Path
        Folder to save results
    feature_set_names : list of str
        Names for each feature set
    n_trials : int
        Number of Optuna trials per feature set
    n_jobs : int
        Number of parallel jobs
    metric : str
        Evaluation metric
    n_splits : int
        Number of CV splits
    random_state : int
        Random seed
    models : list or None
        List of model types to try
        
    Returns:
    --------
    dict
        Results for each feature set and overall comparison
    """
    if feature_set_names is None:
        feature_set_names = [f"feature_set_{i}" for i in range(len(X_sets))]
    
    if len(X_sets) != len(feature_set_names):
        raise ValueError("Number of feature sets must match number of feature set names")
    
    # Create output folder
    os.makedirs(output_folder, exist_ok=True)
    
    # Function to process a single feature set
    def process_feature_set(X, name):
        return optuna_model_selection(
            X, y, 
            n_trials=n_trials,
            n_jobs=n_jobs // len(X_sets) if n_jobs > 0 else -1,  # Divide cores among feature sets
            output_folder=output_folder,
            feature_set_name=name,
            metric=metric,
            n_splits=n_splits,
            random_state=random_state,
            models=models
        )
    
    # Process all feature sets in parallel
    if n_jobs != 1:  # Use parallelization
        results_list = Parallel(n_jobs=min(len(X_sets), n_jobs))(
            delayed(process_feature_set)(X, name) 
            for X, name in zip(X_sets, feature_set_names)
        )
    else:  # Sequential processing
        results_list = [process_feature_set(X, name) for X, name in zip(X_sets, feature_set_names)]
    
    # Organize results by feature set
    results = {name: result for name, result in zip(feature_set_names, results_list)}
    
    # Find the best overall feature set based on metric
    best_feature_set = max(results.items(), key=lambda x: x[1]['best_value'])[0]
    best_model_overall = results[best_feature_set]['best_model']
    
    # Compile summary
    summary = {
        'best_feature_set': best_feature_set,
        'feature_set_comparison': {name: {
            'best_model': res['best_model_name'],
            'best_value': res['best_value'],
            'r2': res['r2'],
            'mse': res['mse'],
            'mae': res['mae'],
            'time': res['optimization_time']
        } for name, res in results.items()},
        'best_model_overall': best_model_overall
    }
    
    # Save summary
    summary_file = os.path.join(output_folder, "feature_set_comparison_summary.json")
    with open(summary_file, 'w') as f:
        json.dump({k: v for k, v in summary.items() if k != 'best_model_overall'}, f, indent=2)
    
    # Save best overall model
    best_model_file = os.path.join(output_folder, "best_model_overall.joblib")
    dump(best_model_overall, best_model_file)
    
    return {**summary, 'full_results': results}


