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
            "type": {"choices": ["gwd", "pca_gwd", "kpca_gwd"]},
            # common
            "sigma_gwd": {"low": 0.05, "high": 0.2, "log": True},
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
        },
    }
}
