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
            if 'value' in details:  # Fixed parameter
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
            "spread": {"weight": w1, "target": t1, "epsilon": e1},
            "density_variability": {"weight": w2, "target": t2, "epsilon": e2},
            "entropy": {"weight": w3, "target": t3, "epsilon": e3}
        },
        "hdbscan": {
            "cluster_persistence": {"weight": w4},
            "noise_ratio": {"weight": w5, "target": t5, "epsilon": e5},
            "validity_index": {"weight": w6}
        }
    }

    For each metric, if a target and epsilon are provided, the component is:
         weight * max(0, 1 - abs(metric_value - target) / epsilon)
    Otherwise, it is weight * metric_value.

    The final composite score is normalized by the total weight.

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
            target = config.get("target")
            epsilon = config.get("epsilon", 0.1)
            value = values_dict.get(metric_name)
            if value is None:
                continue
            if target is not None:
                component = weight * max(0, 1 - abs(value - target) / epsilon)
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

