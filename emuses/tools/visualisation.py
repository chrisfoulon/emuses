import numpy as np
import matplotlib.pyplot as plt
import plotly
import plotly.graph_objs as go
import plotly.express as px
import plotly.io as pio
from bcblib.tools.general_utils import open_json
from plotly.subplots import make_subplots
import streamlit as st
from pathlib import Path


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


def plot_clustering_interactive_with_hover(embeddings, cluster_labels, output_path=None, show_plot=True,
                                           return_plot=False):
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


def plot_spreadsheet_stat_map(
    df_long,
    cluster,
    output_path=None,
    orientation='h',
    interactive=False,
    width=1200,
    height=None,
    title=None,
    show_plot=False,
    return_plot=False
):
    """
    Create a bar plot for a melted DataFrame of features and effect sizes.

    Parameters
    ----------
    df_long : pd.DataFrame
        Melted DataFrame with columns ['Feature', 'Effect Size'].
    cluster : str or int
        The cluster label, used in the plot title if not provided.
    output_path : str or Path, optional
        If provided, the figure is saved here.
        - If interactive=True and output_path ends with '.html', saves an interactive HTML file.
        - Otherwise, saves a static image (PNG, PDF, etc.) if a recognized extension is present.
    orientation : {'h', 'v'}, default='h'
        Orientation of the bars. 'h' for horizontal, 'v' for vertical.
    interactive : bool, default=False
        If True, create an interactive Plotly figure. Otherwise, create a static figure.
    width : int, default=1200
        Figure width in pixels.
    height : int or None, default=None
        Figure height in pixels. If None, an automatic height is used.
    title : str, optional
        Plot title. If None, uses a default title with the cluster.
    show_plot : bool, default=False
        If True and interactive=True, displays the plot in a browser.
        If True and interactive=False, note that Plotly does not automatically pop up a window,
        so you typically rely on the saved image.
    return_plot : bool, default=False
        If True, returns the Plotly figure object.

    Returns
    -------
    fig : plotly.graph_objects.Figure or None
        Returns the figure if return_plot is True, otherwise None.
    """
    if title is None:
        title = f"Effect Size Map for Cluster {cluster}"

    # Decide how to set x/y depending on orientation
    if orientation == 'h':
        x_col = 'Effect Size'
        y_col = 'Feature'
    else:
        x_col = 'Feature'
        y_col = 'Effect Size'

    fig = px.bar(
        df_long,
        x=x_col,
        y=y_col,
        orientation=orientation,
        title=title
    )

    # Adjust layout
    fig.update_layout(
        width=width,
        height=height if height else (25 * len(df_long) if orientation == 'h' else 800),
        margin=dict(l=100, r=50, b=50, t=80)
    )

    if output_path:
        output_path = str(output_path)  # ensure string
        if interactive:
            # If user wants HTML but didn't provide .html, we can auto-add
            if not output_path.lower().endswith('.html'):
                output_path += '.html'
            pio.write_html(fig, output_path)
            print(f"Interactive HTML saved to: {output_path}")
        else:
            # For a static image, rely on kaleido
            # If no recognized extension is present, default to .png
            valid_exts = ('.png', '.jpg', '.jpeg', '.svg', '.pdf')
            if not any(output_path.lower().endswith(ext) for ext in valid_exts):
                output_path += '.png'
            fig.write_image(output_path)
            print(f"Static bar chart saved to: {output_path}")

    if show_plot and interactive:
        fig.show()

    if return_plot:
        return fig
    else:
        return None


def load_umap_tabs(folder, prefix):
    folder = Path(folder)
    # Find all HTML files that start with the given prefix
    html_files = sorted(folder.glob(f"{prefix}*.html"))

    if not html_files:
        st.warning("No HTML files found with that prefix.")
        return

    # Optional filter: allow the user to type a search query
    search_query = st.text_input("Filter files by name:", "")
    if search_query:
        html_files = [f for f in html_files if search_query.lower() in f.name.lower()]

    # Create tab names by extracting the part after the prefix.
    # For example, if the file is "umap_1.html" and prefix is "umap", the tab title will be "1".
    tab_names = [f.stem.replace(prefix, "").strip("_") or f.stem for f in html_files]

    # Create a tab for each file
    tabs = st.tabs(tab_names)

    for tab, file in zip(tabs, html_files):
        with tab:
            html_content = file.read_text(encoding="utf-8")
            # Increase height and enable scrolling so the full plot is visible
            st.components.v1.html(html_content, height=1000, width=1200, scrolling=True)


def save_optimization_log_plot(trial_logs, optim_dict, output_folder=".",
                               plot_filename="optimization_log_plot.png"):
    """
    Generate and save a plot showing the evolution of normalized UMAP parameters and metric contributions
    across trials, using parameter ranges and metric keys extracted directly from optim_dict.

    Parameters:
      trial_logs: either a list/dictionary of trial logs or a path to a JSON file containing them.
      optim_dict (dict): The optimization dictionary, e.g. optim_dict_default.
         It must contain:
           - 'param': {'umap': {parameter_name: { 'low': value, 'high': value, ... }, ...}}
           - 'metrics': {'umap': {metric_name: { ... }, ...}}
      output_folder (str or Path): Folder where the plot image will be saved.
      plot_filename (str): Name of the output plot file.

    Returns:
      None. Saves the plot to the specified output folder.
    """
    # Load trial_logs if a path is provided.
    if isinstance(trial_logs, (str, Path)):
        trial_logs = open_json(trial_logs)

    # Extract UMAP parameter ranges from optim_dict['param']['umap'].
    optim_param_ranges = {}
    for param, details in optim_dict.get("param", {}).get("umap", {}).items():
        if isinstance(details, dict) and "low" in details and "high" in details:
            optim_param_ranges[param] = (details["low"], details["high"])

    # Extract UMAP metric keys from optim_dict['metrics']['umap'].
    metric_keys = list(optim_dict.get("metrics", {}).get("umap", {}).keys())

    trial_numbers = []
    composite_scores = []
    normalized_params = {param: [] for param in optim_param_ranges.keys()}
    detailed_components = {metric: [] for metric in metric_keys}

    # Process each trial log.
    for log in trial_logs:
        trial_numbers.append(log.get("trial_number"))
        composite_scores.append(log.get("composite_score"))
        umap_params = log.get("umap_params", {})

        # Normalize each parameter using its defined range.
        for param, (low, high) in optim_param_ranges.items():
            if param in umap_params:
                val = umap_params[param]
                norm_val = (val - low) / (high - low) if high != low else np.nan
                normalized_params[param].append(norm_val)
            else:
                normalized_params[param].append(np.nan)

        # Get detailed metric components from the trial log (if available).
        dcomp = log.get("detailed_umap_components", {})
        for metric in metric_keys:
            detailed_components[metric].append(dcomp.get(metric, np.nan))

    # Create the plot.
    fig, (ax_params, ax_metrics) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    # Plot normalized UMAP parameters.
    for param, norm_vals in normalized_params.items():
        ax_params.plot(trial_numbers, norm_vals, marker='o', linestyle='-', label=f"{param} (norm)")
    ax_params.set_ylabel("Normalized Parameter Value")
    ax_params.set_title("Evolution of Normalized UMAP Parameters")
    ax_params.legend()
    ax_params.grid(True)

    # Plot composite score (black) and detailed UMAP metric components.
    ax_metrics.plot(trial_numbers, composite_scores, marker='o', linestyle='-',
                    linewidth=2, color='black', label="Composite Score")
    for metric, comp_vals in detailed_components.items():
        ax_metrics.plot(trial_numbers, comp_vals, marker='o', linestyle='--', label=f"{metric} component")
    ax_metrics.set_xlabel("Trial Number")
    ax_metrics.set_ylabel("Metric Contribution")
    ax_metrics.set_title("Evolution of Composite Score and UMAP Metric Components")
    ax_metrics.legend()
    ax_metrics.grid(True)

    plt.tight_layout()

    # Save the plot.
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    save_path = output_folder / plot_filename
    plt.savefig(save_path)
    plt.close(fig)
    print(f"Optimization log plot saved at: {save_path}")
