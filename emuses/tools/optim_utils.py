

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


def normalize_spread(value, target=0.6, epsilon=0.05):
    """
    Normalize the spread metric to a 0-1 range, prioritizing values near the target.

    Parameters:
        value (float): The calculated spread value.
        target (float): The desired target value.
        epsilon (float): Tolerance range around the target.

    Returns:
        float: Normalized value between 0 and 1.
    """
    return max(0, 1 - abs(value - target) / epsilon)


def normalize_silhouette(value):
    """
    Normalize the silhouette score to the 0-1 range.

    Parameters:
        value (float): The silhouette score.

    Returns:
        float: Normalized value between 0 and 1.
    """
    return max(0, min(1, value))  # Silhouette scores are already bounded


def normalize_validity_index(value, max_value=1.0):
    """
    Normalize the validity index to the 0-1 range.

    Parameters:
        value (float): The validity index.
        max_value (float): The maximum expected value for the validity index.

    Returns:
        float: Normalized value between 0 and 1.
    """
    return min(1, value / max_value)


def calculate_composite_score(optim_dict, metrics_values_dict):
    """
    Calculate the normalized composite score by combining normalized metrics based on the `optim_dict`.

    Parameters:
        optim_dict (dict): Dictionary defining optimization configurations, including metrics.
        metrics_values_dict (dict): Dictionary of calculated metric values.

    Returns:
        float: Normalized composite score between 0 and 1.
    """
    total_score = 0
    max_score = 0
    metric_configs = optim_dict.get("metrics", {})

    for model, model_metrics in metric_configs.items():
        calculated_metrics = metrics_values_dict.get(model, {})

        for metric_name, metric_config in model_metrics.items():
            weight = metric_config.get("weight", 1.0)
            target = metric_config.get("target", None)

            # Retrieve the metric value
            metric_value = calculated_metrics.get(metric_name)
            if metric_value is None:
                continue  # Skip if the metric value is not provided

            # Custom normalization
            handler = globals().get(f"normalize_{metric_name}", None)
            if handler:
                normalized_value = handler(metric_value, **metric_config)
            elif target is not None:
                epsilon = metric_config.get("epsilon", 0.1)  # Default tolerance
                normalized_value = max(0, 1 - abs(metric_value - target) / epsilon)
            else:
                normalized_value = metric_value  # Assume the metric is already normalized

            # Update total score and maximum possible score
            total_score += weight * normalized_value
            max_score += weight  # Maximum contribution if normalized_value = 1

    # Normalize total score to [0, 1] range
    if max_score > 0:
        total_score /= max_score

    return total_score


def calculate_score(metrics, metrics_config):
    """
    Calculate a weighted score from computed metrics.
    For each metric:
      - If 'target' and 'epsilon' are defined, the score is weight*(1 - abs(value - target)/epsilon).
      - Otherwise, the score is simply weight * value.
    """
    score = 0.0
    for metric_name, config in metrics_config.items():
        if metric_name in metrics:
            value = metrics[metric_name]
            if 'target' in config and 'epsilon' in config:
                diff = abs(value - config['target'])
                # Here, if the difference exceeds epsilon, the score may become negative.
                metric_score = config['weight'] * (1 - diff / config['epsilon'])
            else:
                metric_score = config['weight'] * value
            score += metric_score
    return score
