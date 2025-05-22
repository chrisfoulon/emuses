"""
Helpers to instantiate regression / classification estimators
from the Optuna-sampled hyper-parameter dict.
"""

from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import ElasticNet, LogisticRegression

from emuses.tools.kernel_regression_utils import (
    KernelRegressor,
    KernelLogisticRegressor,
)

from sklearn.pipeline import FeatureUnion
from emuses.tools.features_utils import RawCoords, GWD
from sklearn.preprocessing import PolynomialFeatures


def build_feature_union(feat_cfg: dict):
    """
    Build a FeatureUnion from the feature hyper-parameter dict.
    Keys expected (all optional, default off unless present):
        sigma_gwd : float    - bandwidth for GWD
        poly_deg  : int ≥1   - polynomial expansion degree
        use_raw   : bool     - include raw coords (default True)
    """
    transformers = []

    # raw coordinates
    if feat_cfg.get("use_raw", True):
        transformers.append(("raw", RawCoords()))

    # Gaussian-weighted distances
    if "sigma_gwd" in feat_cfg:
        transformers.append(("gwd", GWD(sigma=feat_cfg["sigma_gwd"])))

    # polynomial expansion
    if feat_cfg.get("poly_deg", 1) > 1:
        transformers.append(
            (
                "poly",
                PolynomialFeatures(degree=feat_cfg["poly_deg"], include_bias=False),
            )
        )

    # Guarantee at least one transformer
    if not transformers:
        transformers.append(("raw", RawCoords()))

    return FeatureUnion(transformers)


def build_estimator(model_cfg: dict, task: str):
    """
    Parameters
    ----------
    model_cfg : dict
        The *model* sub-dict returned by
        `suggest_parameters_conditional`.  It **must** contain
        a key `"model_type"` and the type-specific hyper-parameters.

            e.g.  {
                      "model_type": "kernel",
                      "sigma": 0.08
                  }

    task : {"reg", "clf"}
        Regression or classification.

    Returns
    -------
    sklearn-compatible estimator – already initialised with the
    sampled hyper-parameters.
    """
    task = task.lower()
    if task not in {"reg", "clf"}:
        raise ValueError("task must be 'reg' or 'clf'")

    mtype = model_cfg["model_type"]

    # ─── Kernel models ───────────────────────────────────────────────
    if mtype == "kernel":
        sigma = model_cfg["sigma"]
        return (
            KernelRegressor(sigma=sigma)
            if task == "reg"
            else KernelLogisticRegressor(sigma=sigma)
        )

    # ─── Random forest ──────────────────────────────────────────────
    if mtype == "rf":
        n = model_cfg["n_estimators"]
        md = model_cfg["max_depth"]
        if task == "reg":
            return RandomForestRegressor(
                n_estimators=n, max_depth=md, n_jobs=-1, random_state=42
            )
        return RandomForestClassifier(
            n_estimators=n, max_depth=md, n_jobs=-1, random_state=42
        )

    # ─── Elastic / Logistic (linear models) ─────────────────────────
    if mtype == "elastic":
        if task == "reg":
            return ElasticNet(
                alpha=model_cfg["alpha"],
                l1_ratio=model_cfg["l1_ratio"],
                max_iter=5000,
            )
        # classification path
        return LogisticRegression(
            C=model_cfg["C"],
            penalty=model_cfg["penalty"],
            solver="saga",
            max_iter=5000,
            n_jobs=-1,
        )

    # ─── Unknown type ───────────────────────────────────────────────
    raise ValueError(f"Unsupported model_type '{mtype}'")
