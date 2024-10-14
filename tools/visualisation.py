import os

import numpy as np
import matplotlib.pyplot as plt
import torch
from matplotlib.lines import Line2D


def plot_embeddings_with_values(embeddings_dict, colour_dict, size_dict=None, name_dict=None, scale_colours=False,
                                scale_sizes=False, output_path=None, colourbar_label=None, subplot_title_center=True):
    """
    Plot the embeddings of the labels and each model with colours representing the distances and sizes representing distance.

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
    subplot_title_center : bool, optional
        Place the labels embedding plot at the center subplot, by default True
    """
    # Determine the grid size based on the number of models
    grid_size = int(np.ceil(np.sqrt(len(embeddings_dict))))
    print(f'Grid size: {grid_size}')

    # Create a figure and a set of subplots
    fig, axes = plt.subplots(grid_size, grid_size, figsize=(8 * grid_size, 6 * grid_size))

    # Flatten the axes for easier indexing
    axes = axes.flatten() if grid_size > 1 else [axes]

    # Determine which subplot should contain the labels (center subplot by default)
    label_index = len(axes) // 2 if subplot_title_center else 0

    # Plot the label embeddings in the selected subplot
    scatter = axes[label_index].scatter(embeddings_dict['labels'][:, 0], embeddings_dict['labels'][:, 1], s=5)
    axes[label_index].set_title('UMAP Embedding of ground truth labels')
    cbar = fig.colorbar(scatter, ax=axes[label_index])
    cbar.set_ticks([])  # Remove the numbers from the colorbar
    cbar.solids.set(alpha=0)  # Make the colorbar itself invisible
    cbar.ax.set_facecolor('white')

    # Initialize a counter for the models
    model_counter = 0

    # Plot the embeddings with colors representing the distances and sizes representing distance
    for model_name, model_embedding in embeddings_dict.items():
        if model_name != 'labels':
            # Calculate the index of the subplot for the current model
            model_index = (label_index + model_counter + 1) % len(axes)

            # Scale colours if required
            colours = colour_dict[model_name]
            if scale_colours:
                colours = (colours - np.min(colours)) / (np.max(colours) - np.min(colours))

            # Scale sizes if required
            sizes = size_dict[model_name] if size_dict else None
            if sizes is not None and scale_sizes:
                sizes = sizes * 100

            scatter = axes[model_index].scatter(model_embedding[:, 0], model_embedding[:, 1], c=colours, s=sizes,
                                                alpha=0.7)
            axes[model_index].set_title(f'{name_dict[model_name] if name_dict else model_name}')
            fig.colorbar(scatter, ax=axes[model_index], label=colourbar_label)

            # Increment the model counter
            model_counter += 1

    # Adjust the spacing between subplots and the margins
    plt.subplots_adjust(left=0.05, right=0.95, bottom=0.05, top=0.95, wspace=0.2, hspace=0.3)

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


# Function to plot the clustering of the whole space
def plot_clustering(embeddings, clusterer):
    """
    Plot the clustering of the entire embedding space.

    Parameters:
    embeddings (np.array): Array of shape (n_samples, n_features) containing the embedding coordinates.
    clusterer (HDBSCAN object): Trained HDBSCAN model used for clustering.

    Note:
    Ensure the `clusterer` object is properly trained before passing it to avoid runtime errors.
    """
    if clusterer is None:
        print("No clustering to plot.")
        return

    fig, ax = plt.subplots(figsize=(10, 8))
    unique_labels = np.unique(clusterer.labels_)

    # Use the new colormap method in Matplotlib
    cmap = plt.colormaps.get_cmap('tab20')

    # Plot the data points
    for idx, k in enumerate(unique_labels):
        if k == -1:
            # Noise points: grey color with reduced opacity
            color = [0.5, 0.5, 0.5, 0.4]  # Grey with reduced opacity
        else:
            # Get a color from the colormap
            color = cmap(idx / len(unique_labels))  # Get a distinct color based on the index

        class_member_mask = (clusterer.labels_ == k)
        xy = embeddings[class_member_mask]
        ax.plot(xy[:, 0], xy[:, 1], 'o', markerfacecolor=color,
                markeredgecolor='k', markersize=4, alpha=0.75)

    # Customize the legend
    # Commenting out the existing static legend code
    # ax.legend(handles=legend_elements, title='Clusters', loc='center left', bbox_to_anchor=(1, 0.5))

    # Dynamic legend placement based on the number of clusters
    if len(unique_labels) > 10:
        ax.legend(handles=legend_elements, title='Clusters', loc='best', fontsize='small')
    else:
        ax.legend(handles=legend_elements, title='Clusters', loc='center left', bbox_to_anchor=(1, 0.5))

    ax.set_title('Clustering of the Whole Space')
    ax.set_xlabel('Coordinate X')
    ax.set_ylabel('Coordinate Y')

    plt.show()
