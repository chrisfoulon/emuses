optim_dict_predict = {
    "param": {
        "model": {
            # master switch
            "model_type": {"choices": ["kernel", "rf", "elastic"]},
            # per-model sub-spaces
            "kernel": {
                "sigma": {"low": 0.01, "high": 0.3, "log": True},
            },
            "rf": {
                "n_estimators": {"low": 50, "high": 400, "step": 50},
                "max_depth": {"low": 2, "high": 20},
            },
            "elastic": {
                # regression
                "alpha": {"low": 1e-4, "high": 10, "log": True},
                "l1_ratio": {"low": 0.0, "high": 1.0},
                # classification path
                "C": {"low": 0.01, "high": 100, "log": True},
                "penalty": {"choices": ["l1", "l2"]},
            },
        },
        "features": {
            # choose feature recipe
            "feat_type": {"choices": ["gwd", "pca_gwd", "kpca_gwd", "ae"]},
            # common for GWD-based features
            "sigma_gwd": {
                "low": 0.05,
                "high": 0.2,
                "log": True,
                "conditional_on": {"feat_type": ["gwd", "pca_gwd", "kpca_gwd"]},
            },
            "poly_deg": {"choices": [1, 2]},
            "use_raw": {"choices": [True, False]},
            # PCA / KPCA specific
            # linear PCA variant
            "n_comp": {
                "low": 10,
                "high": 80,
                "step": 10,
                "conditional_on": {"feat_type": ["pca_gwd", "kpca_gwd"]},
            },
            # OR adaptive-variance variant
            "var_thr": {
                "low": 0.75,
                "high": 0.95,
                "conditional_on": {"feat_type": ["pca_gwd"]},
            },
            # kpca-specific
            "feat_gamma": {
                "low": 0.5,
                "high": 5.0,
                "log": True,
                "conditional_on": {"feat_type": ["kpca_gwd"]},
            },
            # correlation filtering threshold
            "corr_thr": {
                "low": 0.15,
                "high": 0.35,
                "conditional_on": {"feat_type": ["gwd", "pca_gwd", "kpca_gwd"]},
            },
        },
    }
}


# emuses/config/optim_configs_predict_phase1.py
optim_dict_phase1 = {
    "param": {
        "model": {
            "model_type": {"choices": ["kernel", "rf", "elastic"]},
            "kernel": {"sigma": {"low": 0.05, "high": 0.15, "log": True}},
            "rf": {
                "n_estimators": {"low": 100, "high": 300, "step": 50},
                "max_depth": {"low": 3, "high": 10},
            },
            "elastic": {
                "alpha": {"low": 1e-4, "high": 1.0, "log": True},
                "l1_ratio": {"low": 0.1, "high": 0.9},
                "tol": {"value": 1e-3},
                "max_iter": {"value": 5000},
            },
        },
        "features": {
            "feat_type": {"choices": ["gwd", "pca_gwd"]},
            "sigma_gwd": {"low": 0.05, "high": 0.15, "log": True},
            "corr_thr": {"low": 0.10, "high": 0.30},
            "n_comp": {
                "low": 20,
                "high": 50,
                "step": 10,
                "conditional_on": {"feat_type": ["pca_gwd"]},
            },
        },
    }
}


# optim_configs_predict.py

optim_dict_corr_pca = {
    "param": {
        "model": {
            # same model choices as before
            "model_type": {"choices": ["kernel", "rf", "elastic"]},
            "kernel": {
                "sigma": {"low": 0.01, "high": 0.3, "log": True},
            },
            "rf": {
                "n_estimators": {"low": 50, "high": 400, "step": 50},
                "max_depth": {"low": 2, "high": 20},
            },
            "elastic": {
                "alpha": {"low": 1e-4, "high": 10, "log": True},
                "l1_ratio": {"low": 0.0, "high": 1.0},
                "C": {"low": 0.01, "high": 100, "log": True},
                "penalty": {"choices": ["l1", "l2"]},
            },
        },
        "features": {
            # only PCA and KPCA on the GWD matrix
            "feat_type": {"choices": ["pca_gwd", "kpca_gwd"]},
            # bandwidth for the underlying GWD computation
            "sigma_gwd": {"low": 0.05, "high": 0.2, "log": True},
            # optional polynomial lift
            "poly_deg": {"choices": [1, 2]},
            "use_raw": {"choices": [True, False]},
            # if you want to fix the number of components
            "n_comp": {
                "low": 10,
                "high": 80,
                "step": 10,
                "conditional_on": {"feat_type": ["pca_gwd", "kpca_gwd"]},
            },
            # PCA‐only adaptive variance threshold
            "var_thr": {
                "low": 0.75,
                "high": 0.95,
                "conditional_on": {"feat_type": ["pca_gwd"]},
            },
            # KPCA‐only RBF gamma
            "feat_gamma": {
                "low": 0.5,
                "high": 5.0,
                "log": True,
                "conditional_on": {"feat_type": ["kpca_gwd"]},
            },
            # correlation filtering threshold (applies to both PCA and KPCA pipelines)
            "corr_thr": {
                "low": 0.15,
                "high": 0.35,
                "conditional_on": {"feat_type": ["pca_gwd", "kpca_gwd"]},
            },
        },
    }
}


optim_dict_ae = {
    "param": {
        "model": {
            # same model choices as other configs
            "model_type": {"choices": ["kernel", "rf", "elastic"]},
            "kernel": {
                "sigma": {"low": 0.01, "high": 0.3, "log": True},
            },
            "rf": {
                "n_estimators": {"low": 50, "high": 400, "step": 50},
                "max_depth": {"low": 2, "high": 20},
            },
            "elastic": {
                "alpha": {"low": 1e-4, "high": 10, "log": True},
                "l1_ratio": {"low": 0.0, "high": 1.0},
                "C": {"low": 0.01, "high": 100, "log": True},
                "penalty": {"choices": ["l1", "l2"]},
            },
        },
        "features": {
            # Only AE features for direct comparison with PCA/KPCA approaches
            "feat_type": {"choices": ["ae"]},
            # optional polynomial lift
            "poly_deg": {"choices": [1, 2]},
            "use_raw": {"choices": [True, False]},
        },
    }
}


def load_optim_dict_predict(name):
    """
    Dynamically load a prediction optimization dictionary from this module.

    The name should correspond to a variable in this module (e.g., 'optim_dict_predict', 'optim_dict_phase1').
    If name does not contain an underscore, the function simply returns the variable from this module.
    If name contains underscores, it tries to split and process similar to the UMAP optim_dict loader.

    Parameters:
        name (str): Name of the prediction optimization dictionary to load.

    Returns:
        dict: The selected prediction optimization dictionary.

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
            raise ValueError(f"Variable '{base}' not found in optim_configs_predict.")
    else:
        raise ValueError(f"Variable '{name}' not found in optim_configs_predict.")
