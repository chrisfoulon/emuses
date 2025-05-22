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
            # GWD bandwidth
            "sigma_gwd": {"low": 0.02, "high": 0.25, "log": True},
            # optional polynomial degree
            "poly_deg": {"low": 1, "high": 3, "step": 1},
            "use_raw": {"choices": [True, False]},
        },
    }
}
