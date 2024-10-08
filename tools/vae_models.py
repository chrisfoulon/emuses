import torch
import torch.nn as nn
import torch.nn.functional as F

from enum import Enum


# Baseline VAE for 2D images
class BaselineEncoder2D(nn.Module):
    def __init__(self, input_dim, hidden_dim, latent_dim):
        super(BaselineEncoder2D, self).__init__()
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, stride=2, padding=1)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1)
        self.fc1 = nn.Linear(64 * 2 * 2, hidden_dim)
        self.fc2_mean = nn.Linear(hidden_dim, latent_dim)
        self.fc2_logvar = nn.Linear(hidden_dim, latent_dim)

    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = x.view(x.size(0), -1)
        h = F.relu(self.fc1(x))
        z_mean = self.fc2_mean(h)
        z_logvar = self.fc2_logvar(h)
        return z_mean, z_logvar


class BaselineDecoder2D(nn.Module):
    def __init__(self, latent_dim, hidden_dim, output_dim):
        super(BaselineDecoder2D, self).__init__()
        self.fc1 = nn.Linear(latent_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, 64 * 2 * 2)
        self.deconv1 = nn.ConvTranspose2d(64, 32, kernel_size=3, stride=2, padding=1, output_padding=1)
        self.deconv2 = nn.ConvTranspose2d(32, 1, kernel_size=3, stride=2, padding=1, output_padding=1)

    def forward(self, z):
        h = F.relu(self.fc1(z))
        h = F.relu(self.fc2(h))
        h = h.view(h.size(0), 64, 2, 2)
        h = F.relu(self.deconv1(h))
        x_recon = torch.sigmoid(self.deconv2(h))
        return x_recon


# Transformer-based VAE for 2D images
class TransformerEncoder2D(nn.Module):
    def __init__(self, input_dim, hidden_dim, latent_dim, num_heads=8, num_layers=6):
        super(TransformerEncoder2D, self).__init__()
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, stride=2, padding=1)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1)
        self.flatten = nn.Flatten()
        self.linear_proj = nn.Linear(64 * 2 * 2, hidden_dim)
        self.encoder_layer = nn.TransformerEncoderLayer(d_model=hidden_dim, nhead=num_heads, batch_first=True)
        self.transformer_encoder = nn.TransformerEncoder(self.encoder_layer, num_layers=num_layers)
        self.fc_mu = nn.Linear(hidden_dim, latent_dim)
        self.fc_logvar = nn.Linear(hidden_dim, latent_dim)

    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = self.flatten(x)
        x = self.linear_proj(x)
        x = self.transformer_encoder(x.unsqueeze(1)).squeeze(1)
        z_mean = self.fc_mu(x)
        z_logvar = self.fc_logvar(x)
        return z_mean, z_logvar


class TransformerDecoder2D(nn.Module):
    def __init__(self, latent_dim, hidden_dim, output_dim):
        super(TransformerDecoder2D, self).__init__()
        self.fc1 = nn.Linear(latent_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, 64 * 2 * 2)
        self.deconv1 = nn.ConvTranspose2d(64, 32,
                                          kernel_size=3, stride=2, padding=1, output_padding=1)
        self.deconv2 = nn.ConvTranspose2d(32, 1,
                                          kernel_size=3, stride=2, padding=1, output_padding=1)

    def forward(self, z):
        h = F.relu(self.fc1(z))
        h = F.relu(self.fc2(h))
        h = h.view(h.size(0), 64, 2, 2)
        h = F.relu(self.deconv1(h))
        x_recon = torch.sigmoid(self.deconv2(h))
        return x_recon


# Transformer-based VAE for tabular data
class TransformerEncoderTabular(nn.Module):
    def __init__(self, num_features, hidden_dim, latent_dim, num_heads=8, num_layers=6):
        super(TransformerEncoderTabular, self).__init__()
        self.embedding = nn.Linear(num_features, hidden_dim)
        self.transformer_encoder = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(hidden_dim, num_heads),
            num_layers
        )
        self.fc1 = nn.Linear(hidden_dim, latent_dim)
        self.fc2 = nn.Linear(hidden_dim, latent_dim)

    def forward(self, x):
        x = self.embedding(x)
        x = self.transformer_encoder(x.unsqueeze(1)).squeeze(1)
        z_mean = self.fc1(x)
        z_logvar = self.fc2(x)
        return z_mean, z_logvar


class TransformerDecoderTabular(nn.Module):
    def __init__(self, latent_dim, hidden_dim, num_features, num_heads=8, num_layers=6):
        super(TransformerDecoderTabular, self).__init__()
        self.fc1 = nn.Linear(latent_dim, hidden_dim)
        self.transformer_decoder = nn.TransformerDecoder(
            nn.TransformerDecoderLayer(hidden_dim, num_heads),
            num_layers
        )
        self.fc2 = nn.Linear(hidden_dim, num_features)

    def forward(self, z):
        h = F.relu(self.fc1(z))
        h = self.transformer_decoder(h.unsqueeze(1)).squeeze(1)
        x_recon = torch.sigmoid(self.fc2(h))
        return x_recon


# Transformer-based VAE for 3D images
class TransformerEncoder3D(nn.Module):
    def __init__(self, input_dim, hidden_dim, latent_dim, num_heads=8, num_layers=6):
        super(TransformerEncoder3D, self).__init__()
        self.conv1 = nn.Conv3d(1, 32, kernel_size=3, stride=2, padding=1)
        self.conv2 = nn.Conv3d(32, 64, kernel_size=3, stride=2, padding=1)
        self.flatten = nn.Flatten()
        self.linear_proj = nn.Linear(64 * 4 * 4 * 4, hidden_dim)
        self.transformer_encoder = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(hidden_dim, num_heads),
            num_layers
        )
        self.fc1 = nn.Linear(hidden_dim, latent_dim)
        self.fc2 = nn.Linear(hidden_dim, latent_dim)

    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = self.flatten(x)
        x = F.relu(self.linear_proj(x))
        x = self.transformer_encoder(x.unsqueeze(1)).squeeze(1)
        z_mean = self.fc1(x)
        z_logvar = self.fc2(x)
        return z_mean, z_logvar


class TransformerDecoder3D(nn.Module):
    def __init__(self, latent_dim, hidden_dim, output_dim, num_heads=8, num_layers=6):
        super(TransformerDecoder3D, self).__init__()
        self.fc1 = nn.Linear(latent_dim, hidden_dim)
        self.transformer_decoder = nn.TransformerDecoder(
            nn.TransformerDecoderLayer(hidden_dim, num_heads),
            num_layers
        )
        self.linear_proj = nn.Linear(hidden_dim, 64 * 4 * 4 * 4)
        self.deconv1 = nn.ConvTranspose3d(64, 32, kernel_size=3, stride=2, padding=1, output_padding=1)
        self.deconv2 = nn.ConvTranspose3d(32, 1, kernel_size=3, stride=2, padding=1, output_padding=1)

    def forward(self, z):
        h = F.relu(self.fc1(z))
        h = self.transformer_decoder(h.unsqueeze(1)).squeeze(1)
        h = F.relu(self.linear_proj(h))
        h = h.view(h.size(0), 64, 4, 4, 4)
        h = F.relu(self.deconv1(h))
        x_recon = torch.sigmoid(self.deconv2(h))
        return x_recon


class VAEModelTypes(Enum):
    BASELINE_2D = ("2d", "basic", "basic_vae", "baseline", (BaselineEncoder2D, BaselineDecoder2D))
    TRANSFORMER_2D = ("2d_transformer", "transformer_2d", (TransformerEncoder2D, TransformerDecoder2D))
    TRANSFORMER_TABULAR = ("transformer_tabular", "tabular_transformer",
                           (TransformerEncoderTabular, TransformerDecoderTabular))
    TRANSFORMER_3D = ("3d_transformer", "transformer_3d", (TransformerEncoder3D, TransformerDecoder3D))

    @classmethod
    def get_model_classes(cls, model_type):
        model_type = model_type.lower()
        for item in cls:
            if model_type in item.value[:-1]:
                return item.value[-1]
        raise ValueError(f"Invalid model type: {model_type}")


# Unified VAE
class VAE(nn.Module):
    def __init__(self, input_dim, hidden_dim, latent_dim, model_type, **kwargs):
        super().__init__()
        if isinstance(model_type, str):
            encoder_class, decoder_class = VAEModelTypes.get_model_classes(model_type)
        elif isinstance(model_type, tuple):
            encoder_class, decoder_class = model_type
        else:
            raise ValueError("model_type must be either a string or a tuple of (encoder_class, decoder_class)")
        print(f"Using encoder: {encoder_class.__name__}, decoder: {decoder_class.__name__}")
        self.encoder = encoder_class(input_dim, hidden_dim, latent_dim, **kwargs)
        self.decoder = decoder_class(latent_dim, hidden_dim, input_dim, **kwargs)
        self.fc_mu = nn.Linear(hidden_dim, latent_dim)
        self.fc_logvar = nn.Linear(hidden_dim, latent_dim)

    def encode(self, x):
        z_mean, z_logvar = self.encoder(x)
        return z_mean, z_logvar

    def reparameterize(self, z_mean, z_logvar):
        std = torch.exp(0.5 * z_logvar)
        eps = torch.randn_like(std)
        return z_mean + eps * std

    def decode(self, z):
        return self.decoder(z)

    def forward(self, x):
        z_mean, z_logvar = self.encode(x)
        z = self.reparameterize(z_mean, z_logvar)
        x_recon = self.decode(z)
        return x_recon, z_mean, z_logvar


