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
from emuses.tools.features_utils import RawCoords, GWD, PCAGWD, KernelPCAGWD
from sklearn.preprocessing import PolynomialFeatures


def build_feature_union(feat_cfg: dict):
    steps = []

    # 1) Always (optionally) include the raw coordinates
    if feat_cfg.get("use_raw", False):
        steps.append(("raw", RawCoords()))

    ftype = feat_cfg["type"]  # 'gwd' | 'pca_gwd' | 'kpca_gwd'
    sigma = feat_cfg["sigma_gwd"]
    poly_deg = feat_cfg["poly_deg"]

    if ftype == "gwd":
        steps.append(("gwd", GWD(sigma=sigma, agg="none")))

    elif ftype == "pca_gwd":
        # PCA-based reduction of the GWD matrix
        var_thr = feat_cfg.get("var_thr", None)
        n_comp = None if var_thr is not None else feat_cfg.get("n_comp")
        steps.append(("pca_gwd", PCAGWD(sigma=sigma, n_comp=n_comp, var_thr=var_thr)))

    elif ftype == "kpca_gwd":
        # Kernel‐PCA compression of the GWD matrix
        kpca_gamma = feat_cfg.get("feat_gamma")
        if kpca_gamma is None:
            raise KeyError("KPCA-GWD feature type requires 'feat_gamma' parameter")
        steps.append(
            (
                "kpca_gwd",
                KernelPCAGWD(
                    sigma=sigma,
                    n_comp=feat_cfg.get("n_comp"),
                    kpca_gamma=kpca_gamma,
                ),
            )
        )
    else:
        raise ValueError(f"Unknown feature type: {ftype!r}")

    # 3) Add polynomial lifting if requested
    if poly_deg > 1:
        steps.append(("poly", PolynomialFeatures(poly_deg, include_bias=False)))

    return FeatureUnion(steps)


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
    sklearn-compatible estimator - already initialised with the
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
