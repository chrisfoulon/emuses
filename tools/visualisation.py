import os

import numpy as np
import matplotlib.pyplot as plt
import torch


def plot_embeddings_with_values(embeddings_dict, colour_dict, size_dict=None, name_dict=None, scale_colours=False,
                                scale_sizes=False, output_path=None, colourbar_label=None):
    """
    Plot the embeddings of the labels and each model with colours representing the distances and sizes representing distance

    Parameters
    ----------
    embeddings_dict : dict
        A dictionary containing the embeddings of the labels and each model
    colour_dict : dict
        A dictionary containing the colours for each model
    size_dict : dict, optional
        A dictionary containing the sizes for each model, by default None
    name_dict : dict, optional
        A dictionary containing the names for each model, by default None
    scale_colours : bool, optional
        A boolean indicating whether to scale the colours, by default False
    scale_sizes : bool, optional
        A boolean indicating whether to scale the sizes, by default False
    output_path : str, optional
        The path to save the plot, by default None
    colourbar_label : str, optional
        The label for the colourbar, by default None
    """
    # Determine the grid size based on the number of models
    grid_size = int(np.ceil(np.sqrt(len(embeddings_dict))))
    print(f'Grid size: {grid_size}')

    # Create a figure and a set of subplots
    fig, axes = plt.subplots(grid_size, grid_size, figsize=(8 * grid_size, 6 * grid_size))

    # Flatten the axes for easier indexing
    if grid_size > 1:
        # Flatten the axes for easier indexing
        axes = axes.flatten()
    else:
        # If there's only one subplot, put axes in a list to enable iteration
        axes = [axes]

    # Calculate the index of the center subplot
    center_index = len(axes) // 2

    # Plot the label embeddings in the center subplot
    scatter = axes[center_index].scatter(embeddings_dict['labels'][:, 0], embeddings_dict['labels'][:, 1], s=5)
    axes[center_index].set_title('UMAP Embedding of ground truth labels')
    cbar = fig.colorbar(scatter, ax=axes[center_index])
    cbar.set_ticks([])  # Remove the numbers from the colorbar
    # cbar.outline.set_visible(False)  # Make the colorbar outline invisible
    cbar.solids.set(alpha=0)  # Make the colorbar itself invisible
    cbar.ax.set_facecolor('white')

    # Initialize a counter for the models
    model_counter = 0

    # Plot the embeddings with colors representing the distances and sizes representing distance
    for model_name, model_embedding in embeddings_dict.items():
        if model_name != 'labels':
            # Calculate the index of the subplot for the current model
            model_index = (center_index + model_counter + 1) % len(axes)

            # Scale colours if required
            colours = colour_dict[model_name]
            if scale_colours:
                colours = (colours - np.min(colours)) / (np.max(colours) - np.min(colours))

            # Scale sizes if required
            sizes = size_dict[model_name] if size_dict else None
            if sizes is not None and scale_sizes:
                sizes = sizes * 100
            scatter = axes[model_index].scatter(model_embedding[:, 0], model_embedding[:, 1], c=colours, s=sizes)
            axes[model_index].set_title(f'{name_dict[model_name] if name_dict else model_name}')
            fig.colorbar(scatter, ax=axes[model_index], label=colourbar_label)

            # Increment the model counter
            model_counter += 1

    # Adjust the spacing between subplots and the margins
    plt.subplots_adjust(left=0.05, right=0.95, bottom=0.05, top=0.95, wspace=0.05, hspace=0.1)

    # Save the plot if output_path is provided
    if output_path is not None:
        plt.savefig(output_path)

    plt.show()


def plot_latent_space(vae, test_loader, device, output_folder, filename):
    vae.eval()
    z_means = []
    labels = []
    with torch.no_grad():
        for data, label in test_loader:
            data = data.to(device)
            z_mean, z_logvar = vae.encoder(data)
            z_means.append(z_mean)
            labels.append(label)

    z_means = torch.cat(z_means).cpu().numpy()
    labels = torch.cat(labels).numpy()

    plt.figure(figsize=(10, 8))
    plt.scatter(z_means[:, 0], z_means[:, 1], c=labels, cmap='tab10')
    plt.colorbar(label='Digit Label')
    plt.xlabel('Latent Dimension 1')
    plt.ylabel('Latent Dimension 2')
    plt.title('Latent Space Visualization')
    plt.savefig(os.path.join(output_folder, filename))
    plt.close()
