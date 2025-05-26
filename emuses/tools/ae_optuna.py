# emuses/tools/ae_optuna.py
"""
Specialized Optuna optimization for Autoencoder and VAE pretraining.
This module handles AE/VAE hyperparameter optimization separately from
the main prediction pipeline.
"""

import numpy as np
import optuna
import logging
from sklearn.model_selection import KFold
from sklearn.metrics import mean_squared_error

from emuses.tools.ae_utils import AETransformer
from emuses.tools.optim_utils import suggest_parameters
from emuses.config.optim_configs_ae import load_optim_dict_ae

logger = logging.getLogger(__name__)


def ae_objective_factory(X, cv_folds=5, random_state=42, optim_dict=None):
    """
    Create an Optuna objective function for AE/VAE optimization.

    The objective minimizes reconstruction error via cross-validation.

    Parameters
    ----------
    X : array-like of shape (n_samples, n_features)
        Input data for reconstruction
    cv_folds : int, optional
        Number of cross-validation folds
    random_state : int, optional
        Random seed for reproducibility
    optim_dict : dict, optional
        Optimization dictionary. If None, loads default AE config.

    Returns
    -------
    callable
        Objective function for Optuna optimization
    """
    # Load optim_dict if not provided
    if optim_dict is None:
        optim_dict = load_optim_dict_ae("default")

    def objective(trial):
        # Sample AE hyperparameters using optim_dict mechanism
        params = suggest_parameters(trial, optim_dict)

        # Extract parameters with defaults for compatibility
        ae_type = params.get("ae_type", "ae")
        hidden_dim = params.get("ae_hidden_dim", 64)
        lr = params.get("ae_lr", 1e-3)
        epochs = params.get("ae_epochs", 100)
        batch_size = params.get("ae_batch_size", 32)
        weight_decay = params.get("ae_weight_decay", 0.0)

        # VAE-specific parameter (only used if ae_type is "vae")
        beta = params.get("vae_beta", 1.0)

        # ImprovedAE-specific parameters
        ae_depth = params.get("ae_depth", 2)
        dropout = params.get("ae_dropout", 0.1)

        # Create AE transformer with sampled parameters
        ae_transformer = AETransformer(
            ae_type=ae_type,
            hidden_dim=hidden_dim,
            beta=beta,
            lr=lr,
            epochs=epochs,
            batch_size=batch_size,
            ae_depth=ae_depth,
            dropout=dropout,
            weight_decay=weight_decay,
            random_state=random_state,
        )

        # Cross-validation for reconstruction error
        cv = KFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
        reconstruction_errors = []

        for train_idx, val_idx in cv.split(X):
            X_train_fold, X_val_fold = X[train_idx], X[val_idx]

            # Fit AE on training fold
            ae_transformer.fit(X_train_fold)

            # Compute reconstruction error on validation fold
            recon_error = ae_transformer.get_reconstruction_error(X_val_fold)
            reconstruction_errors.append(np.mean(recon_error))

        # Return mean reconstruction error (to be minimized)
        return np.mean(reconstruction_errors)

    return objective


def optimize_ae_pretraining(X, n_trials=200, output_folder=None, random_state=42):
    """
    Run Optuna optimization for AE/VAE pretraining.

    Parameters
    ----------
    X : array-like of shape (n_samples, n_features)
        Input data for AE training
    n_trials : int, optional
        Number of Optuna trials
    output_folder : str, optional
        Directory to save optimization results
    random_state : int, optional
        Random seed for reproducibility

    Returns
    -------
    dict
        Dictionary containing:
        - 'best_params': Best hyperparameters found
        - 'best_score': Best reconstruction error achieved
        - 'fitted_ae': Fitted AE transformer with best parameters
    """
    logger.info(f"Starting AE/VAE pretraining optimization with {n_trials} trials")

    # Create Optuna study
    storage_str = None
    if output_folder:
        storage_str = f"sqlite:///{output_folder}/optuna_ae_pretraining.db"

    study = optuna.create_study(
        direction="minimize",  # Minimize reconstruction error
        storage=storage_str,
        study_name="ae_pretraining",
        load_if_exists=True,
    )

    # Run optimization
    objective = ae_objective_factory(X, random_state=random_state)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    # Get best parameters and fit final model
    best_params = study.best_trial.params

    logger.info(f"Best AE parameters: {best_params}")
    logger.info(f"Best reconstruction error: {study.best_value:.4f}")

    # Fit AE with best parameters on full dataset
    best_ae = AETransformer(
        ae_type=best_params["ae_type"],
        hidden_dim=best_params["ae_hidden_dim"],
        beta=best_params.get("vae_beta", 1.0),
        lr=best_params["ae_lr"],
        epochs=best_params["ae_epochs"],
        batch_size=best_params["ae_batch_size"],
        ae_depth=best_params.get("ae_depth", 2),
        dropout=best_params.get("ae_dropout", 0.1),
        weight_decay=best_params.get("ae_weight_decay", 0.0),
        random_state=random_state,
    )

    best_ae.fit(X)

    return {
        "best_params": best_params,
        "best_score": study.best_value,
        "fitted_ae": best_ae,
        "study": study,
    }


def create_ae_feature_transformer(ae_results):
    """
    Create a feature transformer using pre-optimized AE parameters.

    Parameters
    ----------
    ae_results : dict
        Results from optimize_ae_pretraining

    Returns
    -------
    AETransformer
        Configured but unfitted AE transformer
    """
    params = ae_results["best_params"]

    return AETransformer(
        ae_type=params["ae_type"],
        hidden_dim=params["ae_hidden_dim"],
        beta=params.get("vae_beta", 1.0),
        lr=params["ae_lr"],
        epochs=params["ae_epochs"],
        batch_size=params["ae_batch_size"],
        ae_depth=params.get("ae_depth", 2),
        dropout=params.get("ae_dropout", 0.1),
        weight_decay=params.get("ae_weight_decay", 0.0),
    )
