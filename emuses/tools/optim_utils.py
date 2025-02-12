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


def calculate_composite_score(optim_dict, metrics_values_dict):
    """
    Calculate the normalized composite score by combining normalized metrics based on the optim_dict.

    For each metric, if a target and epsilon are specified, the component is:
         weight * max(0, 1 - abs(value - target) / epsilon)
    Otherwise, it is simply weight * value.

    Returns a value between 0 and 1.
    """
    total_score = 0
    max_score = 0
    metric_configs = optim_dict.get("metrics", {})
    for model, model_metrics in metric_configs.items():
        calculated_metrics = metrics_values_dict.get(model, {})
        for metric_name, metric_config in model_metrics.items():
            weight = metric_config.get("weight", 1.0)
            target = metric_config.get("target", None)
            metric_value = calculated_metrics.get(metric_name)
            if metric_value is None:
                continue
            if target is not None:
                epsilon = metric_config.get("epsilon", 0.1)
                component = weight * max(0, 1 - abs(metric_value - target) / epsilon)
            else:
                component = weight * metric_value
            total_score += component
            max_score += weight
    return total_score / max_score if max_score > 0 else 0


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

