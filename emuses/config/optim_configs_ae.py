# emuses/config/optim_configs_ae.py
"""
Optuna hyperparameter configuration for Autoencoder and Variational Autoencoder
feature extraction. This configuration is used to optimize AE/VAE architectures
and training parameters for representation learning.
"""

optim_dict_ae = {
    "param": {
        "ae": {
            "ae_type": {"choices": ["ae", "improved_ae", "vae"]},
            "ae_hidden_dim": {"low": 4, "high": 128, "step": 4},  # size of bottleneck
            # VAE-specific parameters (always sampled, but only used if ae_type is "vae")
            "vae_beta": {
                "low": 0.1,
                "high": 1.0,
                "log": False,
            },
            # ImprovedAE-specific parameters (always sampled, but only used if ae_type is "improved_ae")
            "ae_depth": {
                "low": 2,
                "high": 6,
                "step": 1,
            },
            "ae_dropout": {
                "low": 0.0,
                "high": 0.5,
                "log": False,
            },
            # Training hyperparameters
            "ae_lr": {
                "low": 1e-5,
                "high": 1e-2,
                "log": True,
            },  # Lower min for improved training
            "ae_epochs": {
                "low": 50,
                "high": 200,
                "step": 10,
            },  # More epochs for better training
            "ae_batch_size": {"choices": [16, 32, 64]},
            "ae_weight_decay": {
                "low": 1e-6,
                "high": 1e-3,
                "log": True,
            },  # L2 regularization
        }
    }
}


def load_optim_dict_ae(name):
    """
    Load a named autoencoder optimization dictionary.

    Parameters
    ----------
    name : str
        The name of the optimization configuration to load

    Returns
    -------
    dict
        The optimization dictionary for the specified configuration
    """
    configs = {
        "default": optim_dict_ae,
        "ae": optim_dict_ae,
    }

    if name not in configs:
        raise ValueError(
            f"Unknown AE optimization config: {name}. Available: {list(configs.keys())}"
        )

    return configs[name]
