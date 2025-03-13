import numpy as np


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


