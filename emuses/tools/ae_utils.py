# emuses/tools/ae_utils.py
"""
Autoencoder and Variational Autoencoder implementations for feature learning
in the EMUSES pipeline. These models can learn compressed representations
of high-dimensional input features.
"""

import logging

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class SimpleAE(nn.Module):
    """
    Simple Autoencoder with one hidden layer.

    Parameters
    ----------
    input_dim : int
        Dimensionality of input features
    hidden_dim : int
        Dimensionality of the bottleneck/latent space
    """

    def __init__(self, input_dim, hidden_dim):
        super().__init__()
        self.encoder = nn.Sequential(nn.Linear(input_dim, hidden_dim), nn.ReLU())
        self.decoder = nn.Sequential(nn.Linear(hidden_dim, input_dim), nn.Sigmoid())

    def forward(self, x):
        """
        Forward pass through the autoencoder.

        Parameters
        ----------
        x : torch.Tensor
            Input tensor of shape (batch_size, input_dim)

        Returns
        -------
        tuple
            (reconstructed, encoded) tensors
        """
        z = self.encoder(x)
        return self.decoder(z), z


class VAE(nn.Module):
    """
    Variational Autoencoder implementation.

    Parameters
    ----------
    input_dim : int
        Dimensionality of input features
    hidden_dim : int
        Dimensionality of the latent space
    """

    def __init__(self, input_dim, hidden_dim):
        super().__init__()
        # Encoder to mean and log-variance
        self.fc_mu = nn.Linear(input_dim, hidden_dim)
        self.fc_logvar = nn.Linear(input_dim, hidden_dim)

        # Decoder
        self.decoder = nn.Sequential(nn.Linear(hidden_dim, input_dim), nn.Sigmoid())

    def reparameterize(self, mu, logvar):
        """
        Reparameterization trick for VAE.

        Parameters
        ----------
        mu : torch.Tensor
            Mean tensor
        logvar : torch.Tensor
            Log variance tensor

        Returns
        -------
        torch.Tensor
            Sampled latent vector
        """
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def forward(self, x):
        """
        Forward pass through the VAE.

        Parameters
        ----------
        x : torch.Tensor
            Input tensor of shape (batch_size, input_dim)

        Returns
        -------
        tuple
            (reconstructed, mu, logvar) tensors
        """
        mu = self.fc_mu(x)
        logvar = self.fc_logvar(x)
        z = self.reparameterize(mu, logvar)
        return self.decoder(z), mu, logvar


class ImprovedAE(nn.Module):
    """
    A multi-layer autoencoder with configurable depth.

    Parameters
    ----------
    input_dim : int
        Number of input features.
    hidden_dim : int
        Size of the bottleneck layer.
    ae_depth : int
        Total number of encoder (and decoder) linear layers.
        Must be >= 2. Layers will linearly taper from input_dim to hidden_dim.
    dropout : float
        Dropout probability between layers.
    """

    def __init__(self, input_dim, hidden_dim, ae_depth=2, dropout=0.1):
        super().__init__()
        assert ae_depth >= 2, "ae_depth must be at least 2"

        # Compute intermediate dims by linearly interpolating between input_dim and hidden_dim
        dims = [input_dim]
        for i in range(1, ae_depth):
            # floor division to get intermediate dims
            interp = input_dim + (hidden_dim - input_dim) * i // (ae_depth - 1)
            dims.append(int(interp))
        # dims[-1] should equal hidden_dim
        assert dims[-1] == hidden_dim

        # Build encoder: dims[0]→dims[1]→…→dims[-1]
        enc_layers = []
        for in_d, out_d in zip(dims[:-1], dims[1:]):
            enc_layers += [
                nn.Linear(in_d, out_d),
                nn.LayerNorm(out_d),
                nn.LeakyReLU(0.2),
                nn.Dropout(dropout),
            ]
        self.encoder = nn.Sequential(*enc_layers)

        # Build decoder: reverse dims list
        dec_layers = []
        for in_d, out_d in zip(dims[::-1][:-1], dims[::-1][1:]):
            dec_layers += [
                nn.Linear(in_d, out_d),
                nn.LayerNorm(out_d),
                nn.LeakyReLU(0.2),
                nn.Dropout(dropout),
            ]
        # final activation identity to match standardized data
        dec_layers[-1] = nn.Identity()
        self.decoder = nn.Sequential(*dec_layers)

    def forward(self, x):
        """
        Forward pass through the improved autoencoder.

        Parameters
        ----------
        x : torch.Tensor
            Input tensor of shape (batch_size, input_dim)

        Returns
        -------
        tuple
            (reconstructed, encoded) tensors
        """
        z = self.encoder(x)
        return self.decoder(z), z


def ae_loss(recon_x, x):
    """MSE reconstruction loss for standard autoencoder."""
    return F.mse_loss(recon_x, x)


def vae_loss(recon_x, x, mu, logvar, beta=1.0):
    """
    VAE loss combining reconstruction loss and KL divergence.

    Parameters
    ----------
    recon_x : torch.Tensor
        Reconstructed input
    x : torch.Tensor
        Original input
    mu : torch.Tensor
        Mean from encoder
    logvar : torch.Tensor
        Log variance from encoder
    beta : float
        Weight for KL divergence term

    Returns
    -------
    torch.Tensor
        Total VAE loss
    """
    # Reconstruction loss
    recon_loss = F.mse_loss(recon_x, x)

    # KL divergence
    kld = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())

    return recon_loss + beta * kld


class AETransformer(BaseEstimator, TransformerMixin):
    """
    Sklearn-compatible wrapper for autoencoder and VAE feature extraction.

    Parameters
    ----------
    ae_type : str
        Type of autoencoder: "ae", "improved_ae", or "vae"
    hidden_dim : int
        Dimensionality of the latent space
    beta : float, optional
        Beta parameter for VAE (weight of KL divergence)
    lr : float, optional
        Learning rate for training
    epochs : int, optional
        Number of training epochs
    batch_size : int, optional
        Batch size for training
    device : str, optional
        PyTorch device ("cpu" or "cuda")
    random_state : int, optional
        Random seed for reproducibility
    ae_depth : int, optional
        Number of layers in the improved autoencoder (only used for "improved_ae")
    dropout : float, optional
        Dropout probability for improved autoencoder (only used for "improved_ae")
    weight_decay : float, optional
        Weight decay (L2 regularization) for optimizer
    """

    def __init__(
        self,
        ae_type="ae",
        hidden_dim=64,
        beta=1.0,
        lr=1e-3,
        epochs=50,
        batch_size=64,
        device="cpu",
        random_state=42,
        ae_depth=2,
        dropout=0.1,
        weight_decay=0.0,
    ):
        self.ae_type = ae_type
        self.hidden_dim = hidden_dim
        self.beta = beta
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.device = device
        self.random_state = random_state
        self.ae_depth = ae_depth
        self.dropout = dropout
        self.weight_decay = weight_decay

        # Initialize components
        self.model = None
        self.scaler = StandardScaler()
        self.optimizer = None

    def _create_model(self, input_dim):
        """Create the autoencoder model."""
        if self.ae_type == "ae":
            return SimpleAE(input_dim, self.hidden_dim)
        elif self.ae_type == "improved_ae":
            return ImprovedAE(input_dim, self.hidden_dim, self.ae_depth, self.dropout)
        elif self.ae_type == "vae":
            return VAE(input_dim, self.hidden_dim)
        else:
            raise ValueError(f"Unknown ae_type: {self.ae_type}")

    def _create_dataloader(self, X):
        """Create PyTorch DataLoader from input data."""
        X_tensor = torch.FloatTensor(X).to(self.device)
        dataset = torch.utils.data.TensorDataset(X_tensor)
        return torch.utils.data.DataLoader(
            dataset,
            batch_size=self.batch_size,
            shuffle=True,
            generator=torch.Generator().manual_seed(self.random_state),
        )

    def fit(self, X, y=None):
        """
        Fit the autoencoder to the data.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            Training data
        y : Ignored
            Not used, present for API consistency

        Returns
        -------
        self : AETransformer
            Returns self for method chaining
        """
        # Set random seeds for reproducibility
        torch.manual_seed(self.random_state)
        np.random.seed(self.random_state)

        # Standardize input features
        X_scaled = self.scaler.fit_transform(X)

        # Create model and optimizer
        input_dim = X_scaled.shape[1]
        self.model = self._create_model(input_dim).to(self.device)
        self.optimizer = torch.optim.Adam(
            self.model.parameters(), lr=self.lr, weight_decay=self.weight_decay
        )

        # Add learning rate scheduler for improved training
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=10, verbose=False
        )

        # Create data loader
        dataloader = self._create_dataloader(X_scaled)

        # Training loop
        self.model.train()
        for epoch in range(self.epochs):
            epoch_loss = 0.0
            for batch_idx, (batch_data,) in enumerate(dataloader):
                self.optimizer.zero_grad()

                if self.ae_type == "ae" or self.ae_type == "improved_ae":
                    recon, _ = self.model(batch_data)
                    loss = ae_loss(recon, batch_data)
                elif self.ae_type == "vae":
                    recon, mu, logvar = self.model(batch_data)
                    loss = vae_loss(recon, batch_data, mu, logvar, self.beta)

                loss.backward()
                self.optimizer.step()
                epoch_loss += loss.item()

            # Update learning rate scheduler
            avg_loss = epoch_loss / len(dataloader)
            self.scheduler.step(avg_loss)

            if epoch % 10 == 0:
                logger.debug(f"Epoch {epoch}/{self.epochs}, Loss: {avg_loss:.4f}")

        return self

    def transform(self, X):
        """
        Transform data to latent space representation.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            Data to transform

        Returns
        -------
        ndarray of shape (n_samples, hidden_dim)
            Latent space representation
        """
        if self.model is None:
            raise ValueError("Model must be fitted before transform")

        # Standardize input using fitted scaler
        X_scaled = self.scaler.transform(X)
        X_tensor = torch.FloatTensor(X_scaled).to(self.device)

        # Encode to latent space
        self.model.eval()
        with torch.no_grad():
            if self.ae_type == "ae" or self.ae_type == "improved_ae":
                _, z = self.model(X_tensor)
                return z.cpu().numpy()
            elif self.ae_type == "vae":
                # For VAE, use the mean of the latent distribution
                mu = self.model.fc_mu(X_tensor)
                return mu.cpu().numpy()

    def fit_transform(self, X, y=None):
        """Fit the model and transform the data in one step."""
        return self.fit(X, y).transform(X)

    def get_reconstruction_error(self, X):
        """
        Compute reconstruction error for anomaly detection.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            Input data

        Returns
        -------
        ndarray of shape (n_samples,)
            Reconstruction error per sample
        """
        if self.model is None:
            raise ValueError(
                "Model must be fitted before computing reconstruction error"
            )

        X_scaled = self.scaler.transform(X)
        X_tensor = torch.FloatTensor(X_scaled).to(self.device)

        self.model.eval()
        with torch.no_grad():
            if self.ae_type == "ae" or self.ae_type == "improved_ae":
                recon, _ = self.model(X_tensor)
            elif self.ae_type == "vae":
                recon, _, _ = self.model(X_tensor)

            # Compute MSE per sample
            mse = F.mse_loss(recon, X_tensor, reduction="none").mean(dim=1)
            return mse.cpu().numpy()
