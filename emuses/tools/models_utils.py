"""
Helpers to instantiate regression / classification estimators
from the Optuna-sampled hyper-parameter dict.
"""

import logging
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import ElasticNet, LogisticRegression

from emuses.tools.kernel_regression_utils import (
    KernelRegressor,
    KernelLogisticRegressor,
)

from sklearn.pipeline import FeatureUnion
from emuses.tools.features_utils import RawCoords, GWD, PCAGWD, KernelPCAGWD, CorrFilter
from emuses.tools.ae_utils import AETransformer
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

logger = logging.getLogger(__name__)


def build_feature_union(feat_cfg: dict, pretrained_ae=None):
    """
    Build feature union from configuration with enhanced flexibility for feature combinations.

    Parameters
    ----------
    feat_cfg : dict
        Feature configuration dictionary. Key parameters:
        - feat_type: str
            Feature type to use. Options:
            - "raw_only": Only raw coordinates, no other features
            - "gwd": GWD features (default)
            - "pca_gwd": PCA-transformed GWD features
            - "kpca_gwd": Kernel PCA-transformed GWD features
            - "ae": Autoencoder features
        - use_raw: bool
            Whether to include raw coordinates alongside other features.
            Ignored when feat_type="raw_only" (default: True)
        - sigma_gwd: float
            GWD sigma parameter (required for GWD-based features)
        - Other feature-specific parameters as needed
    pretrained_ae : AETransformer, optional
        Pre-fitted AE transformer to use instead of training new one

    Returns
    -------
    sklearn.pipeline.FeatureUnion
        Configured feature union
    """
    steps = []
    feat_type = feat_cfg.get("feat_type", "gwd")
    use_raw = feat_cfg.get("use_raw", True)

    # Handle raw_only case - only raw coordinates, no other features
    if feat_type == "raw_only":
        logger.info("Building feature union with raw coordinates only")
        steps.append(("raw", RawCoords()))
        # Skip all other feature processing for raw_only
        if feat_cfg.get("poly_deg", 1) > 1:
            steps.append(
                ("poly", PolynomialFeatures(feat_cfg["poly_deg"], include_bias=False))
            )
        return FeatureUnion(steps)

    # For all other feature types, optionally include raw coordinates first
    if use_raw:
        logger.info("Including raw coordinates in feature union")
        steps.append(("raw", RawCoords()))

    # Handle different feature types
    if feat_type == "ae":
        # Autoencoder/VAE features - requires pretrained AE
        if pretrained_ae is not None:
            # Use the pre-fitted AE
            logger.info("Using pre-fitted AE transformer")
            steps.append(("ae", pretrained_ae))
        else:
            raise ValueError(
                "feat_type='ae' requires a pretrained autoencoder. "
                "In the HeatmapStage, AE pretraining should be automatically enabled when 'ae' "
                "features are detected in the optimization dictionary. If you're seeing this error, "
                "it may indicate an issue with the AE pretraining logic or you're using AE features "
                "in a custom context. Either enable AE pretraining in your configuration, "
                "provide a pretrained_ae parameter, or use a different feat_type."
            )
    else:
        # Traditional GWD-based features
        if "sigma_gwd" not in feat_cfg:
            raise KeyError(f"feat_type='{feat_type}' requires 'sigma_gwd' parameter")

        logger.info(f"Adding GWD features with sigma={feat_cfg['sigma_gwd']}")
        steps.append(("gwd", GWD(sigma=feat_cfg["sigma_gwd"], agg="none")))

        # optional correlation filter (only when corr_thr in dict)
        if "corr_thr" in feat_cfg:
            logger.info(
                f"Adding correlation filter with threshold={feat_cfg['corr_thr']}"
            )
            steps.append(("corr", CorrFilter(thr=feat_cfg["corr_thr"])))

        # optional PCA / KPCA
        if feat_type == "pca_gwd":
            # Handle both n_comp and var_thr approaches
            var_thr = feat_cfg.get("var_thr", None)
            n_comp = None if var_thr is not None else feat_cfg.get("n_comp")
            logger.info(f"Adding PCA-GWD with n_comp={n_comp}, var_thr={var_thr}")
            steps.append(
                (
                    "pca",
                    PCAGWD(sigma=feat_cfg["sigma_gwd"], n_comp=n_comp, var_thr=var_thr),
                )
            )
        elif feat_type == "kpca_gwd":
            kpca_gamma = feat_cfg.get("feat_gamma")
            if kpca_gamma is None:
                raise KeyError("KPCA-GWD feature type requires 'feat_gamma' parameter")
            logger.info(
                f"Adding KPCA-GWD with gamma={kpca_gamma}, n_comp={feat_cfg.get('n_comp')}"
            )
            steps.append(
                (
                    "kpca",
                    KernelPCAGWD(
                        sigma=feat_cfg["sigma_gwd"],
                        n_comp=feat_cfg.get("n_comp"),
                        kpca_gamma=kpca_gamma,
                    ),
                )
            )

    # optional polynomial lift
    if feat_cfg.get("poly_deg", 1) > 1:
        logger.info(f"Adding polynomial features with degree={feat_cfg['poly_deg']}")
        steps.append(
            ("poly", PolynomialFeatures(feat_cfg["poly_deg"], include_bias=False))
        )

    # Validate that we have at least one feature transformation
    if not steps:
        raise ValueError(
            "No feature transformations were added. Ensure that either feat_type='raw_only' "
            "or use_raw=True, or that appropriate feature parameters are provided."
        )

    logger.info(
        f"Built feature union with {len(steps)} steps: {[step[0] for step in steps]}"
    )
    return FeatureUnion(steps)
    return FeatureUnion(steps)


def build_estimator(model_cfg: dict, task: str, n_jobs: int = -1):
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
        kernel = model_cfg.get(
            "kernel", "gaussian"
        )  # Default to gaussian if not specified

        if task == "reg":
            return KernelRegressor(sigma=sigma, kernel=kernel)
        else:
            return KernelLogisticRegressor(sigma=sigma, kernel=kernel)

    # ─── Random forest ──────────────────────────────────────────────
    if mtype == "rf":
        n = model_cfg["n_estimators"]
        md = model_cfg["max_depth"]

        common_params = {
            "n_estimators": n,
            "max_depth": md,
            "n_jobs": n_jobs,
            "random_state": 42,
        }

        # Add additional parameters if present
        if "min_samples_split" in model_cfg:
            common_params["min_samples_split"] = model_cfg["min_samples_split"]
        if "min_samples_leaf" in model_cfg:
            common_params["min_samples_leaf"] = model_cfg["min_samples_leaf"]
        if "max_features" in model_cfg:
            common_params["max_features"] = model_cfg["max_features"]
        if "bootstrap" in model_cfg:
            common_params["bootstrap"] = model_cfg["bootstrap"]

        if task == "reg":
            return RandomForestRegressor(**common_params)
        else:
            # For clf, we might want to add class_weight='balanced' for imbalanced datasets
            clf_params = common_params.copy()
            clf_params["class_weight"] = model_cfg.get("class_weight", None)
            return RandomForestClassifier(**clf_params)

    # ─── Elastic / Logistic (linear models) ─────────────────────────
    if mtype == "elastic":
        if task == "reg":
            return ElasticNet(
                alpha=model_cfg["alpha"],
                l1_ratio=model_cfg["l1_ratio"],
                max_iter=10000,
            )
        # classification path
        return LogisticRegression(
            C=model_cfg["C"],
            penalty=model_cfg["penalty"],
            solver="saga",
            max_iter=10000,
            n_jobs=n_jobs,
            multi_class="auto",  # Handle both binary and multi-class automatically
        )

    # ─── Unknown type ───────────────────────────────────────────────
    raise ValueError(f"Unsupported model_type '{mtype}'")
