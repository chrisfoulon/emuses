import numpy as np
import matplotlib.pyplot as plt
import plotly
import plotly.graph_objs as go
from plotly.subplots import make_subplots


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


# Function to plot the clustering of the whole space
def plot_clustering(
    embeddings, clusterer, grid_x, grid_y, gaussian_matrix, filtered_indices,
    filtered_embeddings, cluster_labels, score_tag, highlight_points=True,
    show_plot=False, save_path=None
):
    """
    Plot the clustering of the entire embedding space, including heatmap and filtered points.

    Parameters:
    - embeddings (np.array): Array of embedding coordinates.
    - clusterer (HDBSCAN object): Trained clusterer.
    - grid_x (np.array): X-coordinates of the grid.
    - grid_y (np.array): Y-coordinates of the grid.
    - gaussian_matrix (np.array): Gaussian correlation matrix.
    - filtered_indices (np.array): Indices of filtered coordinates.
    - filtered_embeddings (np.array): Filtered embedding coordinates.
    - cluster_labels (np.array): Cluster labels for the filtered coordinates.
    - score_tag (str): Label tag for the current score.
    - highlight_points (bool): Whether to highlight filtered points.
    - show_plot (bool): Whether to display the plot.
    - save_path (str or Path): Path to save the plot image.

    Returns:
    - fig: Matplotlib figure object.
    """
    if clusterer is None:
        print("No clustering to plot.")
        return

    fig, axs = plt.subplots(1, 2, figsize=(20, 8))

    # Heatmap subplot
    cax = axs[0].imshow(
        gaussian_matrix.T, cmap='hot', interpolation='nearest', origin='lower',
        extent=[grid_x.min(), grid_x.max(), grid_y.min(), grid_y.max()]
    )
    axs[0].set_title(f'Gaussian Filter Heatmap for score {score_tag}')
    axs[0].set_xlabel('Coordinate X')
    axs[0].set_ylabel('Coordinate Y')
    fig.colorbar(cax, ax=axs[0])

    if highlight_points:
        # Highlight filtered points on the heatmap
        axs[0].scatter(filtered_embeddings[:, 0], filtered_embeddings[:, 1], color='red', s=10, label='Filtered points')
        axs[0].legend()

    # Plot the entire space with filtered points in color
    unfiltered_labels = np.full(embeddings.shape[0], -1)
    unfiltered_labels[filtered_indices] = cluster_labels
    scatter = axs[1].scatter(
        embeddings[:, 0], embeddings[:, 1], c=unfiltered_labels, cmap='viridis', alpha=0.3
    )
    axs[1].scatter(
        filtered_embeddings[:, 0], filtered_embeddings[:, 1], c=cluster_labels, cmap='viridis',
        edgecolor='k', s=50
    )
    axs[1].set_title('Filtered Coordinates and Clusters')
    axs[1].set_xlabel('Coordinate X')
    axs[1].set_ylabel('Coordinate Y')
    legend1 = axs[1].legend(*scatter.legend_elements(), title="Clusters")
    axs[1].add_artist(legend1)

    # Save the plot if a save path is provided
    if save_path:
        fig.savefig(save_path)
        print(f"Plot saved to {save_path}")

    # Show the plot if requested
    if show_plot:
        plt.show()

    # Return the figure object
    return fig


def plot_clustering_interactive_with_hover(embeddings, cluster_labels, output_path=None, show_plot=True, return_plot=False):
    """
    Plot the clustering of the entire embedding space interactively with hover functionality.

    Parameters:
    embeddings (np.array): Array of shape (n_samples, n_features) containing the embedding coordinates.
    cluster_labels (np.array): Array of cluster labels for each embedding.
    output_path (str or Path, optional): Path where the interactive plot will be saved. If None, the plot will not be saved.
    show_plot (bool, optional): If True, the plot will be displayed.
    return_plot (bool, optional): If True, the plot object will be returned.

    Returns:
    plotly.graph_objects.Figure or None: Returns the plot object if return_plot is True, otherwise returns None.
    """
    # Define unique cluster labels
    unique_labels = np.unique(cluster_labels)

    # Create a color map for the clusters
    cmap = plt.colormaps.get_cmap('tab20')

    # Create a Plotly figure with specified size to make it more balanced
    fig = make_subplots(rows=1, cols=1)
    fig.update_layout(width=800, height=800)  # Set width and height to make the plot more square

    # Plot each cluster with a distinct color
    for idx, k in enumerate(unique_labels):
        if k == -1:
            # Noise points: grey color
            color = 'rgba(128, 128, 128, 0.6)'  # Grey with reduced opacity
        else:
            # Get a color from the colormap
            color = f'rgba({cmap(idx / len(unique_labels))[0] * 255}, {cmap(idx / len(unique_labels))[1] * 255}, {cmap(idx / len(unique_labels))[2] * 255}, 0.75)'

        # Filter points for the current cluster
        class_member_mask = (cluster_labels == k)
        cluster_points = embeddings[class_member_mask]

        # Add a scatter trace for the current cluster
        fig.add_trace(
            go.Scatter(x=cluster_points[:, 0],
                       y=cluster_points[:, 1],
                       mode='markers',
                       marker=dict(color=color, size=5, line=dict(width=0.5, color='black')),
                       name=f'Cluster {k}' if k != -1 else 'Noise',
                       hoverinfo='text',
                       text=[f'Cluster {k}' for _ in range(len(cluster_points))])
        )

    # Update layout
    fig.update_layout(
        title='Interactive Clustering of the Whole Space',
        xaxis_title='Coordinate X',
        yaxis_title='Coordinate Y',
        showlegend=True,
        legend_title='Clusters',
        xaxis=dict(scaleanchor='y', scaleratio=1),  # Maintain the aspect ratio of the plot
        yaxis=dict(scaleanchor='x', scaleratio=1)   # Maintain the aspect ratio of the plot
    )

    # Optionally save the interactive plot
    if output_path:
        plotly.io.write_html(fig, output_path)
        print(f"Interactive plot saved at: {output_path}")

    # Show the interactive plot if requested
    if show_plot:
        fig.show()

    # Return the plot if requested
    if return_plot:
        return fig
    else:
        return None


def plot_embeddings(
    embeddings,
    cluster_labels=None,
    output_path=None,
    show_plot=True,
    return_plot=False,
    interactive=True,
    title='Embeddings',
    marker_size=5,
    opacity=0.75
):
    """
    Plot embeddings interactively or as static images with optional clustering and hover functionality.
    Supports both 2D and 3D embeddings:
      - If embeddings.shape[1] == 2, a 2D scatter plot is created.
      - If embeddings.shape[1] == 3, a 3D scatter plot is created.

    Parameters:
    - embeddings (np.array): Array of shape (n_samples, n_features) containing the embedding coordinates.
                             Must have n_features = 2 or 3.
    - cluster_labels (np.array or None, optional): Array of cluster labels for each embedding.
                                                   If None, all points are plotted as one group.
    - output_path (str or Path, optional):
        Path where the plot will be saved.
        If interactive=True and output_path ends with '.html', saves an interactive HTML file.
        If interactive=False, attempts to save a static image (e.g., '.png') using fig.write_image().
    - show_plot (bool, optional): If True, the plot will be displayed in a browser (if interactive=True).
                                  If interactive=False and show_plot=True, the function won't automatically show the plot,
                                  but you can open the saved image manually or handle it via return_plot.
    - return_plot (bool, optional): If True, returns the plotly figure object.
    - interactive (bool, optional): If True, create an interactive plot (HTML). If False, create a static image.
    - title (str, optional): Title for the plot.
    - marker_size (int, optional): Size of the markers.
    - opacity (float, optional): Opacity of the markers.

    Returns:
    - go.Figure or None: Returns the plot object if return_plot is True, otherwise None.

    Raises:
    - ValueError: If embeddings are not 2D or 3D.
    """
    if embeddings.ndim != 2 or embeddings.shape[1] not in [2, 3]:
        raise ValueError("Embeddings must be a 2D array with either 2 or 3 columns.")

    dims = embeddings.shape[1]
    is_3d = (dims == 3)

    # Handle cluster_labels optional
    if cluster_labels is None:
        cluster_labels = np.zeros(embeddings.shape[0], dtype=int)
        unique_labels = np.array([0])
    else:
        unique_labels = np.unique(cluster_labels)

    # Create a colormap from matplotlib
    cmap = plt.colormaps.get_cmap('tab20')

    # Initialize a figure
    fig = go.Figure()

    # Plot each cluster
    for idx, k in enumerate(unique_labels):
        class_member_mask = (cluster_labels == k)
        cluster_points = embeddings[class_member_mask]

        if k == -1:
            # Noise points: grey color
            color = 'rgba(128, 128, 128, 0.6)'
            name = 'Noise'
        else:
            # Map cluster index to a color
            r, g, b, a = cmap(idx / len(unique_labels))
            color = f'rgba({int(r*255)}, {int(g*255)}, {int(b*255)}, {opacity})'
            name = f'Cluster {k}' if len(unique_labels) > 1 else 'All Points'

        if is_3d:
            fig.add_trace(
                go.Scatter3d(
                    x=cluster_points[:, 0],
                    y=cluster_points[:, 1],
                    z=cluster_points[:, 2],
                    mode='markers',
                    marker=dict(color=color, size=marker_size, line=dict(width=0.5, color='black')),
                    name=name,
                    hoverinfo='text',
                    text=[name for _ in range(len(cluster_points))]
                )
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=cluster_points[:, 0],
                    y=cluster_points[:, 1],
                    mode='markers',
                    marker=dict(color=color, size=marker_size, line=dict(width=0.5, color='black')),
                    name=name,
                    hoverinfo='text',
                    text=[name for _ in range(len(cluster_points))]
                )
            )

    # Update layout depending on dimensionality
    if is_3d:
        fig.update_layout(
            title=title,
            showlegend=True,
            legend_title='Clusters',
            scene=dict(
                xaxis_title='Dimension 1',
                yaxis_title='Dimension 2',
                zaxis_title='Dimension 3',
                aspectmode='cube'
            )
        )
    else:
        fig.update_layout(
            title=title,
            xaxis_title='Dimension 1',
            yaxis_title='Dimension 2',
            showlegend=True,
            legend_title='Clusters',
            xaxis=dict(scaleanchor='y', scaleratio=1),
            yaxis=dict(scaleanchor='x', scaleratio=1)
        )

    # Save output
    if output_path:
        output_path = str(output_path)
        if interactive:
            # Save as HTML
            if not output_path.endswith('.html'):
                output_path += '.html'
            plotly.io.write_html(fig, output_path)
            print(f"Interactive plot saved at: {output_path}")
        else:
            # Save as a static image (requires kaleido)
            # Common formats: .png, .jpg, .jpeg, .svg, .pdf
            if not any(output_path.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg', '.pdf']):
                output_path += '.png'
            fig.write_image(output_path)
            print(f"Static image saved at: {output_path}")

    # Show plot
    if show_plot:
        if interactive:
            fig.show()
        else:
            # For a static image, we don't have an automatic show in the browser.
            # Inform the user to open the saved image manually or handle it via return_plot.
            print("Static mode: The plot is not displayed interactively. Open the saved image file to view.")

    # Return figure if requested
    if return_plot:
        return fig
    else:
        return None


def plot_statistical_map(data, title='', save_path=None, show_plot=False, return_plot=False):
    """
    Plot a 2D statistical map with options to display, save, and/or return the plot.

    Parameters:
    - data: ndarray
        2D array representing the statistical map to plot.
    - title: str, optional
        Title for the plot.
    - save_path: str or Path, optional
        Path where the plot will be saved. If None, the plot will not be saved.
    - show_plot: bool, optional
        If True, the plot will be displayed.
    - return_plot: bool, optional
        If True, the plot object will be returned. Note that the plot will not be closed if returned
        and needs to be manually closed after use.

    Returns:
    - plt.Figure or None
        Returns the plot object if return_plot is True, otherwise returns None.
    """
    if not save_path and not show_plot and not return_plot:
        raise ValueError("At least one output option (save, show, or return) must be specified.")

    fig, ax = plt.subplots()
    img = ax.imshow(data, cmap='hot', interpolation='nearest')
    ax.set_title(title)
    ax.set_xlabel('X-axis')
    ax.set_ylabel('Y-axis')
    plt.colorbar(img, label='Effect Size', ax=ax)

    if save_path:
        plt.savefig(save_path)
    if show_plot:
        plt.show()
    if return_plot:
        return fig
    else:
        plt.close(fig)


def plot_embeddings_old(embeddings, title='', save_path=None, show_plot=False, return_plot=False):
    """
    Plot UMAP embeddings as a scatter plot with options to display, save, and/or return the plot.

    Parameters:
    - embeddings: ndarray
        2D array representing the UMAP latent space (e.g., shape (n_samples, 2)).
    - title: str, optional
        Title for the plot.
    - save_path: str or Path, optional
        Path where the plot will be saved. If None, the plot will not be saved.
    - show_plot: bool, optional
        If True, the plot will be displayed.
    - return_plot: bool, optional
        If True, the plot object will be returned. Note that the plot will not be closed if returned
        and needs to be manually closed after use.

    Returns:
    - plt.Figure or None
        Returns the plot object if return_plot is True, otherwise returns None.

    Raises:
    - ValueError: If the embeddings array is not 2-dimensional.
    """
    if not save_path and not show_plot and not return_plot:
        raise ValueError("At least one output option (save, show, or return) must be specified.")

    if embeddings.ndim != 2 or embeddings.shape[1] != 2:
        raise ValueError("Embeddings should be a 2D array with shape (n_samples, 2).")

    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(embeddings[:, 0], embeddings[:, 1], s=10, alpha=0.7, cmap='viridis')
    ax.set_title(title)
    ax.set_xlabel('Dimension 1')
    ax.set_ylabel('Dimension 2')

    if save_path:
        plt.savefig(save_path, bbox_inches='tight')
    if show_plot:
        plt.show()
    if return_plot:
        return fig
    else:
        plt.close(fig)
