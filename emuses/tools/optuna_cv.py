# emuses/tools/optuna_cv.py
# ---------------------------------------------------------------
#  Nested Optuna CV for EMUSES prediction models
#  – conditional search (features + model family)
# ---------------------------------------------------------------
import joblib
import numpy as np
import optuna

from sklearn.pipeline import Pipeline
from sklearn.model_selection import (
    KFold,
    StratifiedKFold,
    cross_val_score,
)

from emuses.config.optim_configs_predict import optim_dict_predict
from emuses.tools.optim_utils import suggest_parameters_conditional
from emuses.tools.models_utils import build_estimator, build_feature_union

# ---------------------------------------------------------------


def _objective_factory(X, y, task: str, inner_cv, optim_dict):
    """Return an Optuna objective that samples the *conditional* space."""
    scoring = "accuracy" if task == "clf" else "r2"

    def objective(trial):
        # 1 ─ sample hyper-parameters
        params = suggest_parameters_conditional(trial, optim_dict)

        # 2 ─ build feature transformer + estimator
        feats = build_feature_union(params["features"])
        est = build_estimator(params["model"], task)

        # 3 ─ cross-validate
        pipe = Pipeline([("feat", feats), ("est", est)])
        return cross_val_score(
            pipe, X, y, cv=inner_cv, scoring=scoring, n_jobs=-1
        ).mean()

    return objective


def nested_optuna_cv(
    X,
    y,
    task: str = "reg",  # "reg" or "clf"
    *,
    n_outer: int = 5,
    n_trials: int = 50,
    random_state: int = 42,
    target_tag: str = "target",
    output_folder: str = None,
    optim_dict=None,
):
    """
    Fully nested CV:
      outer K-fold  → unbiased score
      inner K-fold  → Optuna search
    Returns
    -------
    scores     : ndarray (n_outer,)
    pipelines  : list[Pipeline]  - best pipeline per outer fold
    """
    # Use provided optim_dict or fall back to default
    if optim_dict is None:
        optim_dict = optim_dict_predict

    outer_cv = (StratifiedKFold if task == "clf" else KFold)(
        n_splits=n_outer, shuffle=True, random_state=random_state
    )

    inner_cv = KFold(n_splits=5, shuffle=True, random_state=random_state)

    scores, pipelines = [], []

    for fold, (tr_idx, te_idx) in enumerate(outer_cv.split(X, y)):
        X_tr, y_tr = X[tr_idx], y[tr_idx]
        X_te, y_te = X[te_idx], y[te_idx]

        # ── run Optuna on *inner* CV ────────────────────────────
        storage_str = f"sqlite:///{output_folder}/optuna_{target_tag}.db"
        study = optuna.create_study(
            storage=storage_str, direction="maximize", load_if_exists=True
        )
        study.optimize(
            _objective_factory(X_tr, y_tr, task, inner_cv, optim_dict),
            n_trials=n_trials,
            show_progress_bar=False,
        )

        # ── refit best params on full outer-train split ────────
        best_params = suggest_parameters_conditional(study.best_trial, optim_dict)
        best_pipe = Pipeline(
            [
                ("feat", build_feature_union(best_params["features"])),
                ("est", build_estimator(best_params["model"], task)),
            ]
        ).fit(X_tr, y_tr)

        # ── evaluate on outer-test split ───────────────────────
        score = best_pipe.score(X_te, y_te)
        scores.append(score)
        pipelines.append(best_pipe)

        joblib.dump(best_pipe, f"best_pipeline_fold{fold}.joblib")

    return np.asarray(scores), pipelines
