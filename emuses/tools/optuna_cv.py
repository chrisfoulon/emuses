# emuses/tools/optuna_cv.py
# ---------------------------------------------------------------
#  Nested Optuna CV for EMUSES prediction models
#  – conditional search (features + model family)
# ---------------------------------------------------------------
import joblib
import logging
import numpy as np
import optuna
import time
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

# Import new model I/O system
from .model_io import ModelIOManager

logger = logging.getLogger(__name__)

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


def _objective_factory(X, y, task: str, inner_cv, optim_dict, pretrained_ae=None):
    """Return an Optuna objective that samples the *conditional* space."""
    # Use appropriate scoring metric based on the task
    if task == "clf":
        # For classification tasks
        if len(np.unique(y)) == 2:  # Binary classification
            scoring = (
                "balanced_accuracy"  # More robust than accuracy for imbalanced data
            )
        else:  # Multi-class classification
            scoring = "balanced_accuracy"  # Good default for multi-class
    else:
        # For regression tasks
        scoring = "r2"

    def objective(trial):
        # 1 ─ sample hyper-parameters
        params = suggest_parameters_conditional(trial, optim_dict)

        # 2 ─ build feature transformer + estimator
        feats = build_feature_union(params["features"], pretrained_ae=pretrained_ae)
        est = build_estimator(params["model"], task)

        # 3 ─ cross-validate
        pipe = Pipeline([("feat", feats), ("est", est)])

        try:
            scores = cross_val_score(
                pipe, X, y, cv=inner_cv, scoring=scoring, n_jobs=-1
            )
            # Store individual CV scores in trial for metadata
            trial.set_user_attr("cv_scores", scores.tolist())
            trial.set_user_attr("cv_mean", scores.mean())
            trial.set_user_attr("cv_std", scores.std())
            trial.set_user_attr("scoring_metric", scoring)

            return scores.mean()
        except Exception as e:
            logger.warning(f"Cross-validation failed for trial {trial.number}: {e}")
            trial.set_user_attr("error", str(e))
            return float("-inf")  # Return worst possible score on error

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
    pretrained_ae=None,
):
    """
    Fully nested CV:
      outer K-fold  → unbiased score
      inner K-fold  → Optuna search

    Parameters
    ----------
    X : array-like, shape (n_samples, n_features)
        Training input samples.
    y : array-like, shape (n_samples,)
        Target values.
    task : str, default="reg"
        Task type, either "reg" for regression or "clf" for classification.
    n_outer : int, default=5
        Number of outer cross-validation folds.
    n_trials : int, default=50
        Number of Optuna trials per inner CV.
    random_state : int, default=42
        Random state for reproducibility.
    target_tag : str, default="target"
        Tag for target variable, used in output file naming.
    output_folder : str, default=None
        Folder to save output files.
    optim_dict : dict, default=None
        Optimization parameter space dictionary.
    pretrained_ae : object, default=None
        Pretrained autoencoder for feature extraction.

    Returns
    -------
    scores : ndarray, shape (n_outer,)
        Scores for each outer fold.
    pipelines : list[Pipeline]
        Best pipeline for each outer fold.
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
        logger.info(f"Processing outer fold {fold + 1}/{n_outer} for {target_tag}")
        fold_start_time = time.time()

        X_tr, y_tr = X[tr_idx], y[tr_idx]
        X_te, y_te = X[te_idx], y[te_idx]

        # ── run Optuna on *inner* CV ────────────────────────────
        storage_str = f"sqlite:///{output_folder}/optuna_{target_tag}.db"
        study_name = f"{target_tag}_fold_{fold}"

        study = optuna.create_study(
            study_name=study_name,
            storage=storage_str,
            direction="maximize",
            load_if_exists=True,
        )

        optimization_start = time.time()
        study.optimize(
            _objective_factory(X_tr, y_tr, task, inner_cv, optim_dict, pretrained_ae),
            n_trials=n_trials,
            show_progress_bar=False,
        )
        optimization_time = time.time() - optimization_start

        logger.info(
            f"Optuna optimization completed for fold {fold}: "
            f"{len(study.trials)} trials, best value: {study.best_value:.4f}, "
            f"time: {optimization_time:.2f}s"
        )

        # ── refit best params on full outer-train split ────────
        best_params = suggest_parameters_conditional(study.best_trial, optim_dict)
        best_pipe = Pipeline(
            [
                (
                    "feat",
                    build_feature_union(
                        best_params["features"], pretrained_ae=pretrained_ae
                    ),
                ),
                ("est", build_estimator(best_params["model"], task)),
            ]
        ).fit(X_tr, y_tr)

        # ── evaluate on outer-test split ───────────────────────
        score = best_pipe.score(X_te, y_te)
        scores.append(score)
        pipelines.append(best_pipe)

        fold_time = time.time() - fold_start_time
        logger.info(
            f"Fold {fold} completed: outer test score = {score:.4f}, "
            f"total time: {fold_time:.2f}s"
        )

        # Save pipeline using enhanced model I/O system
        if output_folder:
            try:
                # Create target-specific directory
                target_dir = Path(output_folder) / target_tag
                target_dir.mkdir(parents=True, exist_ok=True)

                model_manager = ModelIOManager(target_dir)

                # Get inner CV scores from the best trial
                inner_cv_scores = study.best_trial.user_attrs.get("cv_scores", [])

                saved_path = model_manager.save_model(
                    model=best_pipe,
                    model_name=f"best_pipeline_fold{fold}",
                    model_type="sklearn_pipeline",
                    description=f"Best pipeline for {target_tag} fold {fold}/{n_outer} "
                    f"(outer score: {score:.4f}, inner CV: {study.best_value:.4f})",
                    tags=["cv", "pipeline", f"fold_{fold}", target_tag, task],
                    config=best_params,
                    # Enhanced Optuna metadata
                    optuna_study=study,
                    optuna_trial=study.best_trial,
                    # CV metadata
                    cv_score=score,  # Outer fold score
                    cv_scores=inner_cv_scores,  # Inner CV scores
                    cv_folds=n_outer,
                    fold_index=fold,
                )

                logger.info(f"Saved pipeline with Optuna metadata: {saved_path}")

            except Exception as e:
                logger.error(f"Failed to save pipeline for fold {fold}: {e}")
                # Fallback to simple joblib save
                fallback_path = (
                    target_dir / f"best_pipeline_{target_tag}_fold{fold}.joblib"
                )
                joblib.dump(best_pipe, fallback_path)
                logger.info(f"Saved pipeline using fallback method: {fallback_path}")
        else:
            # Fallback to current directory if no output folder specified
            fallback_path = f"best_pipeline_{target_tag}_fold{fold}.joblib"
            joblib.dump(best_pipe, fallback_path)
            logger.info(f"Saved pipeline to current directory: {fallback_path}")

    return np.asarray(scores), pipelines


def load_cv_models(
    output_folder: str, target_tag: str, fold_indices: Optional[List[int]] = None
) -> List[Dict[str, Any]]:
    """
    Load saved CV models with their Optuna metadata.

    Args:
        output_folder: Folder where models were saved
        target_tag: Target variable tag used during saving
        fold_indices: Specific fold indices to load (if None, loads all)

    Returns:
        List of dictionaries containing model artifacts and metadata
    """
    target_dir = Path(output_folder) / target_tag

    if not target_dir.exists():
        logger.error(f"Target directory not found: {target_dir}")
        return []

    model_manager = ModelIOManager(target_dir)
    loaded_models = []

    try:
        # List all CV pipeline models
        all_models = model_manager.list_models(
            model_type="sklearn_pipeline", tags=["cv", "pipeline"]
        )

        for model_info in all_models:
            metadata = model_info["metadata"]
            fold_idx = metadata.get("fold_index")

            # Filter by fold indices if specified
            if fold_indices is not None and fold_idx not in fold_indices:
                continue

            # Load the actual model
            model_name = f"best_pipeline_fold{fold_idx}"
            artifact = model_manager.load_model(model_name, "sklearn_pipeline")

            if artifact:
                model_data = {
                    "fold_index": fold_idx,
                    "artifact": artifact,
                    "outer_score": metadata.get("cv_score"),
                    "inner_cv_scores": metadata.get("cv_scores", []),
                    "optuna_study": metadata.get("optuna_study"),
                    "best_params": metadata.get("processed_params"),
                    "description": metadata.get("description"),
                    "tags": metadata.get("tags", []),
                }
                loaded_models.append(model_data)
                logger.info(f"Loaded model for fold {fold_idx}")
            else:
                logger.warning(f"Failed to load model for fold {fold_idx}")

    except Exception as e:
        logger.error(f"Error loading CV models: {e}")

    # Sort by fold index
    loaded_models.sort(key=lambda x: x["fold_index"])
    return loaded_models


def analyze_cv_results(
    output_folder: str, target_tag: str, verbose: bool = True
) -> Dict[str, Any]:
    """
    Analyze the results of nested CV with Optuna optimization.

    Args:
        output_folder: Folder where models were saved
        target_tag: Target variable tag used during saving
        verbose: Whether to print detailed results

    Returns:
        Dictionary containing analysis results
    """
    loaded_models = load_cv_models(output_folder, target_tag)

    if not loaded_models:
        logger.error("No models found for analysis")
        return {}

    # Extract scores and metadata
    outer_scores = [
        model["outer_score"]
        for model in loaded_models
        if model["outer_score"] is not None
    ]
    inner_scores = [
        model["inner_cv_scores"] for model in loaded_models if model["inner_cv_scores"]
    ]

    # Optuna study statistics
    optuna_stats = []
    for model in loaded_models:
        study_metadata = model.get("optuna_study")
        if study_metadata:
            optuna_stats.append(
                {
                    "fold": model["fold_index"],
                    "n_trials": study_metadata.n_trials,
                    "best_value": study_metadata.best_value,
                    "best_params": (
                        study_metadata.best_trial.params
                        if study_metadata.best_trial
                        else {}
                    ),
                }
            )

    # Calculate summary statistics
    results = {
        "target_tag": target_tag,
        "n_folds": len(loaded_models),
        "outer_cv_scores": outer_scores,
        "outer_cv_mean": np.mean(outer_scores) if outer_scores else None,
        "outer_cv_std": np.std(outer_scores) if outer_scores else None,
        "inner_cv_scores": inner_scores,
        "optuna_statistics": optuna_stats,
        "loaded_models": loaded_models,
    }

    if verbose:
        print(f"\n=== Nested CV Results for {target_tag} ===")
        print(f"Number of folds: {results['n_folds']}")
        if results["outer_cv_mean"] is not None:
            print(
                f"Outer CV Score: {results['outer_cv_mean']:.4f} ± {results['outer_cv_std']:.4f}"
            )

        print(f"\nPer-fold results:")
        for i, (score, stats) in enumerate(zip(outer_scores, optuna_stats)):
            print(
                f"  Fold {i}: outer={score:.4f}, inner_best={stats['best_value']:.4f}, "
                f"trials={stats['n_trials']}"
            )

        print(f"\nOptuna optimization summary:")
        if optuna_stats:
            total_trials = sum(s["n_trials"] for s in optuna_stats)
            mean_inner_best = np.mean([s["best_value"] for s in optuna_stats])
            print(f"  Total trials across all folds: {total_trials}")
            print(f"  Mean inner CV best score: {mean_inner_best:.4f}")

    return results


def get_best_model_across_folds(
    output_folder: str, target_tag: str, criterion: str = "outer_score"
) -> Optional[Dict[str, Any]]:
    """
    Get the best model across all CV folds based on specified criterion.

    Args:
        output_folder: Folder where models were saved
        target_tag: Target variable tag used during saving
        criterion: Criterion for selecting best model ("outer_score" or "inner_score")

    Returns:
        Dictionary containing the best model and its metadata
    """
    loaded_models = load_cv_models(output_folder, target_tag)

    if not loaded_models:
        return None

    if criterion == "outer_score":
        best_model = max(loaded_models, key=lambda x: x["outer_score"] or -np.inf)
    elif criterion == "inner_score":
        best_model = max(
            loaded_models,
            key=lambda x: (
                x["optuna_study"].best_value if x["optuna_study"] else -np.inf
            ),
        )
    else:
        raise ValueError(f"Unknown criterion: {criterion}")

    logger.info(
        f"Best model (by {criterion}): fold {best_model['fold_index']}, "
        f"score = {best_model['outer_score']:.4f}"
    )

    return best_model
