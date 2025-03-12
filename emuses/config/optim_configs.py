import json
import itertools
import copy
import numpy as np
import random


optim_dict_default = {
    'param': {
        'umap': {
            'min_dist': {'name': 'min_dist', 'low': 0.01, 'high': 0.5},
            'n_neighbors': {'name': 'n_neighbors', 'low': 5, 'high': 50, 'step': 5},
            'n_components': {'value': 2},
            'metric': {'name': 'metric', 'choices': ['euclidean']}
        },
        'hdbscan': {
            'min_cluster_size': {'name': 'min_cluster_size', 'low': 5, 'high': 50},
            'min_samples': {'name': 'min_samples', 'low': 1, 'high': 10}
        }
    },
    'metrics': {
        'umap': {
            # 'spread': {
            #     'weight': 1.0,
            #     'target': 0.3,
            #     "epsilon": 0.2
            # },
            'eigen_spread': {
                'weight': 1.0,
            },
            'density_variability': {
                'weight': 1.0,
                'target': 0.4,
                "epsilon": 0.2
            },
            'entropy': {
                'weight': 3,       # Increase the weight on entropy to drive down uniformity.
                'target': 0.6,       # Target lower entropy to encourage well-defined subregions.
                "epsilon": 0.25
            }
        },
        'hdbscan': {
            'cluster_persistence': {
                'weight': 2,       # Seems to maintain a stable (and reasonable) number of clusters.
            },
            'noise_ratio': {
                'weight': 1.0,
                'target': 0.9,       # Ensuring a low noise level (e.g., 10% noise).
                "epsilon": 0.05
            },
            'dbcv': {
                'weight': 1.0,       # High weight to ensure clusters are compact and well separated.
                'target': 1,
                'epsilon': 0.5       # Because 0.5 normalized is 0 in the raw DBCV score
            }
        }
    }
}



optim_dict_test = {
    'param': {
        "umap": {
            "min_dist": 0.04625027098983125,
            "n_neighbors": 5,
            "n_components": 2,
            "metric": "euclidean"
        },
        "hdbscan": {
            "min_cluster_size": 26,
            "min_samples": 1
        }
    },
    'metrics': {
        'umap': {
            'spread': {
                'weight': 1.0,       # Slightly reduced if you want clusters to be tighter.
                'target': 0.6,
                "epsilon": 0.3
            },
            'density_variability': {
                'weight': 1.0,
                'target': 0.4,
                "epsilon": 0.3
            },
            'entropy': {
                'weight': 3,       # Increase the weight on entropy to drive down uniformity.
                'target': 0.6,       # Target lower entropy to encourage well-defined subregions.
                "epsilon": 0.25
            }
        },
        'hdbscan': {
            'cluster_persistence': {
                'weight': 1.5       # Seems to maintain a stable (and reasonable) number of clusters.
            },
            'noise_ratio': {
                'weight': 1.0,
                'target': 0.9,       # Ensuring a low noise level (e.g., 10% noise).
                "epsilon": 0.25
            },
            'dbcv': {
                'weight': 1.0        # High weight to ensure clusters are compact and well separated.
            }
        }
    }
}


optim_dict_mnist = {
    'param': {
        'umap': {
            'min_dist': {'name': 'min_dist', 'value': 0.08393266179885042},
            'n_neighbors': {'name': 'n_neighbors', 'value': 5},
            'n_components': {'name': 'n_components', 'value': 2},
            'metric': {'name': 'metric', 'choices': ['euclidean']}
        },
        'hdbscan': {
            'min_cluster_size': {'name': 'min_cluster_size', 'value': 40},
            'min_samples': {'name': 'min_samples', 'value': 4}
        }
    },
    'metrics': {
        'umap': {
            'spread': {
                'weight': 1.0,
                'target': 0.6,
                'epsilon': 0.1
            },
            'density_variability': {
                'weight': 1.2,
                'target': 0.4,
                'epsilon': 0.1
            },
            'entropy': {
                'weight': 1.5
            }
        },
        'hdbscan': {
            'cluster_persistence': {
                'weight': 2.0
            },
            'noise_ratio': {
                'weight': 1.0,
                'target': 0.1,
                'epsilon': 0.05
            },
            'dbcv': {
                'weight': 1.5
            }
        }
    }
}


optim_dict_hcp = {
    'param': {
        'umap': {
            'min_dist': {'name': 'min_dist', 'value': 0.3628075254313345},
            'n_neighbors': {'name': 'n_neighbors', 'value': 10},
            'n_components': {'name': 'n_components', 'value': 2},
            'metric': {'name': 'metric', 'choices': ['euclidean']}
        },
        'hdbscan': {
            'min_cluster_size': {'name': 'min_cluster_size', 'value': 49},
            'min_samples': {'name': 'min_samples', 'value': 10}
        }
    },
    'metrics': {
        'umap': {
            'spread': {
                'weight': 1.0,
                'target': 0.6,
                'epsilon': 0.1
            },
            'density_variability': {
                'weight': 1.2,
                'target': 0.4,
                'epsilon': 0.1
            },
            'entropy': {
                'weight': 1.5
            }
        },
        'hdbscan': {
            'cluster_persistence': {
                'weight': 2.0
            },
            'noise_ratio': {
                'weight': 1.0,
                'target': 0.1,
                'epsilon': 0.05
            },
            'dbcv': {
                'weight': 1.0
            }
        }
    }
}


def generate_dynamic_metrics_configs(n_configs=10):
    """
    Generate a list of n_configs different metrics configurations for use in the composite score.

    Parameters:
        n_configs (int): The number of configurations to generate

    Returns:
        List[dict]: A list of metrics configurations, each with nested dictionaries
                    for "umap" and "hdbscan".
    """
    configs = []
    # Generate n_configs values for delta, entropy_target, and noise_ratio_target and min_penalty.
    deltas = np.linspace(-0.1, 0.1, n_configs)
    entropy_targets = np.linspace(0.2, 0.4, n_configs)
    noise_ratio_targets = np.linspace(0.8, 0.99, n_configs)
    min_penalties = np.linspace(0.4, 0.6, n_configs)

    for i in range(n_configs):
        delta = deltas[i]
        entropy_target = entropy_targets[i]
        noise_target = noise_ratio_targets[i]
        min_penalty_val = min_penalties[i]

        config = {
            "umap": {
                "spread": {
                    "weight": 1.0,
                    "target": 0.2 - delta,  # lower if delta is positive
                    "min_penalty": min_penalty_val
                },
                "density_variability": {
                    "weight": 1.5,
                    "target": 0.4 + delta,  # higher if delta is positive
                    "min_penalty": min_penalty_val
                },
                "entropy": {
                    "weight": 1.2,
                    "target": entropy_target,
                    "min_penalty": min_penalty_val
                }
            },
            "hdbscan": {
                "cluster_persistence": {
                    "weight": 1.0  # No target; raw value.
                },
                "noise_ratio": {
                    "weight": 1.0,
                    "target": noise_target,
                    "min_penalty": min_penalty_val
                },
                "dbcv": {
                    "weight": 1.0  # No target.
                }
            }
        }
        configs.append(config)
    return configs


# Example usage:
dynamic_optim_dict = generate_dynamic_metrics_configs(n_configs=50)
# for i, cfg in enumerate(dynamic_configs):
#     print(f"Config {i + 1}: {cfg}")

# Our default weights (for the weight portion only)
DEFAULT_WEIGHTS = {
    "umap": {
        "spread": 1.0,
        "density_variability": 1.5,
        "entropy": 1.2
    },
    "hdbscan": {
        "cluster_persistence": 1.0,
        "noise_ratio": 1.0,
        "dbcv": 1.0
    }
}


def generate_configs_from_candidates(cand_umap, cand_hdbscan, default_weights):
    """
    Given candidate multiplier dictionaries for UMAP and HDBSCAN (each mapping a metric name
    to a list of candidate multipliers), generate all possible configurations (the Cartesian product)
    and return them as a list of nested dictionaries.

    Each configuration is computed as:
        weight = default * candidate_multiplier,
    and default targets and a default min_penalty (here 0.5) are attached.
    """
    configs = []
    # For UMAP: get keys and candidate lists.
    umap_keys = list(cand_umap.keys())
    umap_candidate_lists = [cand_umap[k] for k in umap_keys]
    # For HDBSCAN:
    hdbscan_keys = list(cand_hdbscan.keys())
    hdbscan_candidate_lists = [cand_hdbscan[k] for k in hdbscan_keys]

    # Cartesian products:
    for umap_combo in itertools.product(*umap_candidate_lists):
        for hdbscan_combo in itertools.product(*hdbscan_candidate_lists):
            config = {
                "umap": {},
                "hdbscan": {}
            }
            # Set UMAP weights.
            for i, key in enumerate(umap_keys):
                config["umap"][key] = {
                    "weight": DEFAULT_WEIGHTS["umap"][key] * umap_combo[i],
                    "target": {  # fixed default targets
                        "spread": 0.2,
                        "density_variability": 0.4,
                        "entropy": 0.3
                    }[key],
                    "min_penalty": 0.5
                }
            # Set HDBSCAN weights.
            for j, key in enumerate(hdbscan_keys):
                if key in ["noise_ratio"]:
                    config["hdbscan"][key] = {
                        "weight": DEFAULT_WEIGHTS["hdbscan"][key] * hdbscan_combo[j],
                        "target": 0.9,
                        "min_penalty": 0.5
                    }
                else:
                    config["hdbscan"][key] = {
                        "weight": DEFAULT_WEIGHTS["hdbscan"][key] * hdbscan_combo[j]
                    }
            configs.append(config)
    return configs


def generate_educated_weight_configs(n_configs=None, random_seed=42):
    """
    Generate a list of educated weight configurations (optim_dicts for the weight portion)
    by combining several scenarios.

    The scenarios are as follows:

    Scenario A: Focus on HDBSCAN cluster persistence & dbcv.
      - For HDBSCAN:
          cluster_persistence: candidate multipliers: [1.3, 1.5, 1.7, 2.0]
          dbcv: candidate multipliers: [1.3, 1.5, 1.7, 2.0]
          noise_ratio: candidate multipliers: [0.5, 0.8]
      - For UMAP: keep moderate values:
          spread: [0.8, 1.0]
          density_variability: [1.0, 1.2]
          entropy: [1.0]
      Sample 8 configurations.

    Scenario B: Focus on UMAP (increase density_variability; reduce spread and entropy).
      - For UMAP:
          spread: [0.5, 0.8]
          density_variability: [1.7, 2.0]
          entropy: [0.8, 1.0]
      - For HDBSCAN: defaults (all multipliers = [1.0])
      Sample 6 configurations.

    Scenario C: Balanced variation.
      - For all parameters, use candidate multipliers: [0.8, 1.0, 1.2]
      Sample 6 configurations.

    Scenario D: Focus on both UMAP density_variability and HDBSCAN (cluster_persistence & dbcv),
                while reducing spread, entropy, and noise_ratio.
      - For UMAP:
          spread: [0.5, 0.8]
          density_variability: [1.7, 2.0]
          entropy: [0.8]
      - For HDBSCAN:
          cluster_persistence: [1.5, 1.7]
          dbcv: [1.5, 1.7]
          noise_ratio: [0.5, 0.8]
      Sample 8 configurations.

    Scenario E: Focus on reducing noise_ratio weight.
      - For HDBSCAN:
          noise_ratio: [0.5, 0.8]
          others default ([1.0])
      - For UMAP:
          spread: [0.8, 1.0]
          density_variability: [0.8, 1.0]
          entropy: [1.0]
      Sample 4 configurations.

    Scenario F: Variation on one parameter at a time.
      - For each of the 6 parameters, vary it over candidate multipliers: [0.5, 0.8, 1.3, 1.7] while keeping others at default.
      This yields 6*4 = 24 configurations.
      **All 24 configurations are kept.**

    We then combine all scenarios, but we ensure that Scenario F appears first.
    Finally, we remove any duplicates and, if n_configs is specified, select exactly that many unique configurations.

    Parameters:
        n_configs (int, optional): If specified, return exactly n_configs unique configurations.
        random_seed (int): Seed for reproducibility.

    Returns:
        List[dict]: A list of educated optim_dict configurations (weights portion only).
    """
    random.seed(random_seed)
    np.random.seed(random_seed)

    scenarios = []

    # We'll generate scenarios as tuples: (scenario_name, config_list, sample_n)
    # Scenario F: Variation on one parameter at a time.
    base = {
        "umap": {"spread": 1.0, "density_variability": 1.5, "entropy": 1.2},
        "hdbscan": {"cluster_persistence": 1.0, "noise_ratio": 1.0, "dbcv": 1.0}
    }
    single_param_candidates = [0.5, 0.8, 1.3, 1.7]
    configs_F = []
    # For UMAP parameters:
    for metric in ["spread", "density_variability", "entropy"]:
        for cand in single_param_candidates:
            config = copy.deepcopy(base)
            config["umap"][metric] = cand * base["umap"][metric]
            configs_F.append(config)
    # For HDBSCAN parameters:
    for metric in ["cluster_persistence", "noise_ratio", "dbcv"]:
        for cand in single_param_candidates:
            config = copy.deepcopy(base)
            config["hdbscan"][metric] = cand * base["hdbscan"][metric]
            configs_F.append(config)
    # Total in F: 24 configurations.
    scenarios.append(("F", configs_F, len(configs_F)))  # Scenario F comes first.

    # Scenario A:
    cand_umap_A = {
        "spread": [0.8, 1.0],
        "density_variability": [1.0, 1.2],
        "entropy": [1.0]
    }
    cand_hdbscan_A = {
        "cluster_persistence": [1.3, 1.5, 1.7, 2.0],
        "noise_ratio": [0.5, 0.8],
        "dbcv": [1.3, 1.5, 1.7, 2.0]
    }
    configs_A = generate_configs_from_candidates(cand_umap_A, cand_hdbscan_A, DEFAULT_WEIGHTS)
    scenarios.append(("A", configs_A, 8))

    # Scenario B:
    cand_umap_B = {
        "spread": [0.5, 0.8],
        "density_variability": [1.7, 2.0],
        "entropy": [0.8, 1.0]
    }
    cand_hdbscan_B = {
        "cluster_persistence": [1.0],
        "noise_ratio": [1.0],
        "dbcv": [1.0]
    }
    configs_B = generate_configs_from_candidates(cand_umap_B, cand_hdbscan_B, DEFAULT_WEIGHTS)
    scenarios.append(("B", configs_B, 6))

    # Scenario C:
    cand_umap_C = {
        "spread": [0.8, 1.0, 1.2],
        "density_variability": [1.2, 1.5, 1.8],
        "entropy": [0.8, 1.0, 1.2]
    }
    cand_hdbscan_C = {
        "cluster_persistence": [0.8, 1.0, 1.2],
        "noise_ratio": [0.8, 1.0, 1.2],
        "dbcv": [0.8, 1.0, 1.2]
    }
    configs_C = generate_configs_from_candidates(cand_umap_C, cand_hdbscan_C, DEFAULT_WEIGHTS)
    scenarios.append(("C", configs_C, 6))

    # Scenario D:
    cand_umap_D = {
        "spread": [0.5, 0.8],
        "density_variability": [1.7, 2.0],
        "entropy": [0.8]
    }
    cand_hdbscan_D = {
        "cluster_persistence": [1.5, 1.7],
        "noise_ratio": [0.5, 0.8],
        "dbcv": [1.5, 1.7]
    }
    configs_D = generate_configs_from_candidates(cand_umap_D, cand_hdbscan_D, DEFAULT_WEIGHTS)
    scenarios.append(("D", configs_D, 8))

    # Scenario E:
    cand_umap_E = {
        "spread": [0.8, 1.0],
        "density_variability": [0.8, 1.0],
        "entropy": [1.0]
    }
    cand_hdbscan_E = {
        "cluster_persistence": [1.0],
        "noise_ratio": [0.5, 0.8],
        "dbcv": [1.0]
    }
    configs_E = generate_configs_from_candidates(cand_umap_E, cand_hdbscan_E, DEFAULT_WEIGHTS)
    scenarios.append(("E", configs_E, 4))

    # Combine scenarios in the order F, A, B, C, D, E.
    ordered_scenarios = sorted(scenarios, key=lambda x: {"F": 0, "A": 1, "B": 2, "C": 3, "D": 4, "E": 5}[x[0]])

    final_configs = []
    for scenario_name, config_list, sample_n in ordered_scenarios:
        if len(config_list) <= sample_n:
            sampled = config_list
        else:
            sampled = random.sample(config_list, sample_n)
        final_configs.extend(sampled)
        # print(f"Scenario {scenario_name}: sampled {len(sampled)} configurations out of {len(config_list)} available.")

    # Remove duplicates based on a canonical representation.
    seen = set()
    unique_configs = []
    for cfg in final_configs:
        # Create a canonical string representation.
        canon = json.dumps(cfg, sort_keys=True)
        if canon not in seen:
            seen.add(canon)
            unique_configs.append(cfg)

    # print(f"Total unique configurations: {len(unique_configs)}")

    # If n_configs is specified, randomly sample that many unique configurations.
    if n_configs is not None and len(unique_configs) > n_configs:
        unique_configs = random.sample(unique_configs, n_configs)

    return unique_configs


# Example usage:
educated_configs = generate_educated_weight_configs(n_configs=None, random_seed=42)


def load_optim_dict(name):
    """
    Dynamically load an optimization dictionary from this module.

    The name should be formatted as "<base>_<param>" where:
      - <base> is the name of a variable in this module.
      - <param> is interpreted depending on the type of the variable:
            * If <base> is a list, <param> is converted to an integer index.
            * If <base> is a function, <param> is passed as a parameter (attempted conversion to int if possible).
      - If name does not contain an underscore, the function simply returns the variable from this module.

    Parameters:
        name (str): Name of the optimization dictionary to load or parameterized form.

    Returns:
        dict: The selected optimization dictionary.

    Raises:
        ValueError: If the variable is not found or if processing fails.
    """
    globals_dict = globals()

    # First, check if the full name exists.
    if name in globals_dict:
        return globals_dict[name]

    # Otherwise, try to split at the last underscore.
    if "_" in name:
        base, param = name.rsplit("_", 1)
        if base in globals_dict:
            obj = globals_dict[base]
            try:
                if isinstance(obj, list):
                    idx = int(param)
                    return obj[idx]
                elif callable(obj):
                    try:
                        param_val = int(param)
                    except ValueError:
                        param_val = param
                    return obj(param_val)
                else:
                    return obj
            except Exception as e:
                raise ValueError(f"Error processing {name}: {e}")
        else:
            raise ValueError(f"Variable '{base}' not found in optim_configs.")
    else:
        raise ValueError(f"Variable '{name}' not found in optim_configs.")
