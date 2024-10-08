import os

import torch
import torch.nn.functional as F
from tools.vae_models import VAE
from torch.optim import Adam
from tqdm import tqdm
import numpy as np
import matplotlib.pyplot as plt

from tools.visualisation import plot_latent_space


def vae_loss(data, recon_data, mu, logvar, beta):
    batch_size = data.size(0)
    mse = F.mse_loss(recon_data, data, reduction='sum') / batch_size
    kl = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp()) / batch_size
    return mse + beta * kl, mse, kl


def train_vae(
        vae,
        train_loader,
        val_loader,
        device,
        num_epochs=5000,
        learning_rate=1e-5,
        beta_start=0.1,
        beta_end=1.0,
        patience=500,
        min_delta=0.001,
        kl_anneal_epochs=10,
        val_interval=10,
        scheduler_step_size=100,
        scheduler_gamma=1.0
):
    optimizer = Adam(vae.parameters(), lr=learning_rate)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=scheduler_step_size, gamma=scheduler_gamma)
    best_train_loss = float('inf')
    epochs_no_improve = 0

    # Lists to store losses
    train_losses = []
    val_losses = []
    recon_losses = []
    kl_losses = []

    progress_bar = tqdm(range(num_epochs), desc='Training Progress', unit='epoch')

    # Beta scheduler for KL divergence term
    def kl_annealing(epoch):
        if epoch < kl_anneal_epochs:
            return beta_start + (beta_end - beta_start) * (epoch / kl_anneal_epochs)
        else:
            return beta_end

    last_val_loss = float('inf')

    for epoch in progress_bar:
        vae.train()
        train_loss = 0
        epoch_recon_loss_list = []
        epoch_kl_loss_list = []

        for batch_idx, (data, _) in enumerate(train_loader):
            data = data.to(device)
            optimizer.zero_grad()
            x_recon, z_mean, z_logvar = vae(data)
            beta = kl_annealing(epoch)
            loss, mse, kl = vae_loss(data, x_recon, z_mean, z_logvar, beta)
            epoch_recon_loss_list.append(mse.item())
            epoch_kl_loss_list.append(kl.item() * beta)
            loss.backward()
            train_loss += loss.item()
            optimizer.step()

        scheduler.step()  # Adjust learning rate

        train_loss /= len(train_loader)
        recon_loss_mean = np.mean(epoch_recon_loss_list)
        kl_loss_mean = np.mean(epoch_kl_loss_list)

        # Perform validation at specified intervals
        if (epoch + 1) % val_interval == 0 or epoch == num_epochs - 1:
            vae.eval()
            val_loss = 0
            with torch.no_grad():
                for data, _ in val_loader:
                    data = data.to(device)
                    x_recon, z_mean, z_logvar = vae(data)
                    beta = kl_annealing(epoch)
                    loss, mse, kl = vae_loss(data, x_recon, z_mean, z_logvar, beta)
                    val_loss += loss.item()
            val_loss /= len(val_loader)
            last_val_loss = val_loss
            val_losses.append(val_loss)

        # Store losses
        train_losses.append(train_loss)
        recon_losses.append(recon_loss_mean)
        kl_losses.append(kl_loss_mean)

        # Update progress bar description
        if train_loss < best_train_loss - min_delta:
            best_train_loss = train_loss
            epochs_no_improve = 0
            status_symbol = '↑'
        else:
            epochs_no_improve += 1
            status_symbol = '↓'

        progress_bar.set_postfix({
            'Train Loss': f'{train_loss:.4f}',
            'Recon Loss': f'{recon_loss_mean:.4f}',
            'KL Loss': f'{kl_loss_mean:.4f}',
            'Status': status_symbol,
            'Last Val Loss': f'{last_val_loss:.4f}'
        })

        # Early stopping
        if epochs_no_improve == patience:
            print('Early stopping triggered')
            break

    print("Training finished.")
    return train_losses, val_losses, recon_losses, kl_losses


def parameter_search(train_loader, val_loader, test_loader, device, param_grid, output_folder, model_type="baseline"):
    os.makedirs(output_folder, exist_ok=True)

    for params in param_grid:
        input_dim = params['input_dim']
        hidden_dim = params['hidden_dim']
        latent_dim = params['latent_dim']
        learning_rate = params['learning_rate']
        beta_start, beta_end = params['beta_tuple']
        num_epochs = params['num_epochs']
        patience = params['patience']
        min_delta = params['min_delta']
        kl_anneal_epochs = params['kl_anneal_epochs']
        val_interval = params['val_interval']
        scheduler_step_size = params['scheduler_step_size']
        scheduler_gamma = params['scheduler_gamma']

        vae = VAE(input_dim=input_dim, hidden_dim=hidden_dim, latent_dim=latent_dim, model_type=model_type).to(device)

        print(f"Training with parameters: hidden_dim={hidden_dim}, learning_rate={learning_rate}, "
              f"beta_start={beta_start}, beta_end={beta_end}, scheduler_gamma={scheduler_gamma}, "
              f"scheduler_step_size={scheduler_step_size}, kl_anneal_epochs={kl_anneal_epochs}, "
              f"patience={patience}, min_delta={min_delta}")

        train_losses, val_losses, recon_losses, kl_losses = train_vae(
            vae=vae,
            train_loader=train_loader,
            val_loader=val_loader,
            device=device,
            num_epochs=num_epochs,
            learning_rate=learning_rate,
            beta_start=beta_start,
            beta_end=beta_end,
            patience=patience,
            min_delta=min_delta,
            kl_anneal_epochs=kl_anneal_epochs,
            val_interval=val_interval,
            scheduler_step_size=scheduler_step_size,
            scheduler_gamma=scheduler_gamma
        )

        # Create filename abbreviations for the parameters
        param_str = (f"hd_{hidden_dim}_lr_{learning_rate}_bs_{beta_start}"
                     f"_be_{beta_end}_ss_{scheduler_step_size}_sg_{scheduler_gamma}")

        # Plot the losses
        plt.figure(figsize=(10, 6))
        plt.plot(train_losses, label='Train Loss')
        plt.plot(val_losses, label='Validation Loss')
        plt.plot(recon_losses, label='Reconstruction Loss')
        plt.plot(kl_losses, label='KL Divergence')
        plt.xlabel('Epoch')
        plt.ylabel('Loss')
        plt.legend()
        plt.title(f'Training and Validation Losses\nTrain Loss: {train_losses[-1]:.4f}')
        plt.savefig(os.path.join(output_folder, f"{param_str}_training_curves.png"))
        plt.close()

        # Plot the latent space
        plot_latent_space(vae, test_loader, device, output_folder, f"{param_str}_latent_space.png")
