"""
External plotting functions for heatmap analysis visualization.

These functions provide standalone visualization capabilities for prediction and 
correlation heatmaps with UMAP scatter overlays and cluster highlighting.
Designed for GUI integration flexibility as they are NOT class methods.
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Optional, Union, Dict, Any


def plot_prediction_heatmap(
    heatmap_values: np.ndarray,
    training_embeddings: np.ndarray,
    target_scores: np.ndarray,
    target_name: str,
    output_path: Optional[Union[str, Path]] = None,
    show_plot: bool = False,
    grid_size: int = 100,
    figsize: tuple = (12, 8),
    cmap_heatmap: str = "hot",
    cmap_scatter: str = "viridis"
) -> plt.Figure:
    """
    Plot prediction heatmap with UMAP scatter overlay.
    
    Creates base heatmap using prediction×confidence values with scatter overlay
    of training embeddings colored by target scores. Pattern from visualisation.py 
    plot_clustering() function.
    
    Args:
        heatmap_values: Flattened heatmap values (grid_size² length)
        training_embeddings: Training sample coordinates (N, 2)
        target_scores: Target values for training samples (N,)
        target_name: Name of target variable for labeling
        output_path: Path to save PNG file (optional)
        show_plot: Whether to display plot
        grid_size: Size of heatmap grid (default 100)
        figsize: Figure size tuple
        cmap_heatmap: Colormap for heatmap background
        cmap_scatter: Colormap for scatter points
        
    Returns:
        matplotlib Figure object
    """
    # Reshape heatmap values to grid
    if len(heatmap_values) != grid_size * grid_size:
        raise ValueError(f"Expected {grid_size * grid_size} heatmap values, got {len(heatmap_values)}")
    
    heatmap_grid = heatmap_values.reshape(grid_size, grid_size)
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot heatmap background using imshow
    # Embeddings are in 0-1 range, so extent matches
    im = ax.imshow(
        heatmap_grid.T,  # Transpose for proper orientation
        cmap=cmap_heatmap,
        interpolation="nearest",
        origin="lower",
        extent=[0, 1, 0, 1],  # Match embedding coordinate space
        alpha=0.7  # Semi-transparent for overlay visibility
    )
    
    # Add colorbar for heatmap
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Prediction × Confidence", rotation=270, labelpad=20)
    
    # Scatter overlay of training embeddings colored by target scores
    scatter = ax.scatter(
        training_embeddings[:, 0],
        training_embeddings[:, 1],
        c=target_scores,
        cmap=cmap_scatter,
        s=30,  # Point size
        alpha=0.8,
        edgecolors='black',
        linewidth=0.5
    )
    
    # Add colorbar for scatter points
    cbar_scatter = plt.colorbar(scatter, ax=ax, shrink=0.8, pad=0.1)
    cbar_scatter.set_label(f"Target: {target_name}", rotation=270, labelpad=20)
    
    # Set labels and title
    ax.set_xlabel("UMAP Dimension 1")
    ax.set_ylabel("UMAP Dimension 2") 
    ax.set_title(f"Prediction Heatmap: {target_name}")
    
    # Ensure proper aspect ratio
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect('equal')
    
    # Save if path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
    
    # Show if requested
    if show_plot:
        plt.show()
    
    # Close figure to free memory
    plt.close(fig)
    
    return fig


def plot_prediction_cluster_overlay(
    heatmap_values: np.ndarray,
    training_embeddings: np.ndarray,
    target_scores: np.ndarray,
    cluster_sample_indices: np.ndarray,
    cluster_name: str,
    target_name: str,
    significance_type: str,  # 'high' or 'low'
    output_path: Optional[Union[str, Path]] = None,
    show_plot: bool = False,
    grid_size: int = 100,
    figsize: tuple = (12, 8),
    cmap_heatmap: str = "hot"
) -> plt.Figure:
    """
    Plot prediction heatmap with highlighted significant cluster overlay.
    
    Same base heatmap + highlight significant cluster points with different colors.
    All training points shown in grey, cluster points colored. Pattern from
    visualisation.py plot_clustering() lines 188-204.
    
    Args:
        heatmap_values: Flattened heatmap values (grid_size² length)
        training_embeddings: Training sample coordinates (N, 2)
        target_scores: Target values for training samples (N,)
        cluster_sample_indices: Indices of samples in significant cluster
        cluster_name: Name of cluster for labeling
        target_name: Name of target variable for labeling
        significance_type: 'high' or 'low' significance region
        output_path: Path to save PNG file (optional)
        show_plot: Whether to display plot
        grid_size: Size of heatmap grid (default 100)
        figsize: Figure size tuple
        cmap_heatmap: Colormap for heatmap background
        
    Returns:
        matplotlib Figure object
    """
    # Reshape heatmap values to grid
    if len(heatmap_values) != grid_size * grid_size:
        raise ValueError(f"Expected {grid_size * grid_size} heatmap values, got {len(heatmap_values)}")
    
    heatmap_grid = heatmap_values.reshape(grid_size, grid_size)
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot heatmap background using imshow
    im = ax.imshow(
        heatmap_grid.T,  # Transpose for proper orientation
        cmap=cmap_heatmap,
        interpolation="nearest",
        origin="lower",
        extent=[0, 1, 0, 1],  # Match embedding coordinate space
        alpha=0.6  # More transparent for cluster visibility
    )
    
    # Add colorbar for heatmap
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Prediction × Confidence", rotation=270, labelpad=20)
    
    # Plot all training points in grey (background)
    ax.scatter(
        training_embeddings[:, 0],
        training_embeddings[:, 1],
        c='lightgrey',
        s=20,
        alpha=0.4,
        label='Training samples'
    )
    
    # Highlight cluster points with colors based on target scores
    if len(cluster_sample_indices) > 0:
        cluster_embeddings = training_embeddings[cluster_sample_indices]
        cluster_targets = target_scores[cluster_sample_indices]
        
        # Color cluster points by target values
        scatter = ax.scatter(
            cluster_embeddings[:, 0],
            cluster_embeddings[:, 1],
            c=cluster_targets,
            cmap='viridis',
            s=60,  # Larger points to stand out
            alpha=0.9,
            edgecolors='black',
            linewidth=1,
            label=f'{cluster_name} ({significance_type} significance)'
        )
        
        # Add colorbar for cluster points
        cbar_scatter = plt.colorbar(scatter, ax=ax, shrink=0.8, pad=0.1)
        cbar_scatter.set_label(f"Target: {target_name}", rotation=270, labelpad=20)
    
    # Set labels and title
    ax.set_xlabel("UMAP Dimension 1")
    ax.set_ylabel("UMAP Dimension 2")
    ax.set_title(f"Prediction Cluster Overlay: {target_name} - {cluster_name} ({significance_type})")
    
    # Add legend
    ax.legend(loc='upper right')
    
    # Ensure proper aspect ratio
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1) 
    ax.set_aspect('equal')
    
    # Save if path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
    
    # Show if requested
    if show_plot:
        plt.show()
    
    # Close figure to free memory
    plt.close(fig)
    
    return fig


def plot_correlation_heatmap(
    correlation_values: np.ndarray,
    training_embeddings: np.ndarray,
    target_scores: np.ndarray,
    target_name: str,
    correlation_method: str = "pearson",
    output_path: Optional[Union[str, Path]] = None,
    show_plot: bool = False,
    grid_size: int = 100,
    figsize: tuple = (12, 8),
    cmap_heatmap: str = "RdBu_r",
    cmap_scatter: str = "viridis"
) -> plt.Figure:
    """
    Plot correlation heatmap with UMAP scatter overlay.
    
    Creates base heatmap using correlation values with scatter overlay
    of training embeddings colored by target scores. Shows UMAP's learned
    manifold structure correlation with target.
    
    Args:
        correlation_values: Flattened correlation values (grid_size² length)
        training_embeddings: Training sample coordinates (N, 2)
        target_scores: Target values for training samples (N,)
        target_name: Name of target variable for labeling
        correlation_method: Correlation method used (default "pearson")
        output_path: Path to save PNG file (optional)
        show_plot: Whether to display plot
        grid_size: Size of heatmap grid (default 100)
        figsize: Figure size tuple
        cmap_heatmap: Colormap for correlation heatmap (diverging)
        cmap_scatter: Colormap for scatter points
        
    Returns:
        matplotlib Figure object
    """
    # Reshape correlation values to grid
    if len(correlation_values) != grid_size * grid_size:
        raise ValueError(f"Expected {grid_size * grid_size} correlation values, got {len(correlation_values)}")
    
    correlation_grid = correlation_values.reshape(grid_size, grid_size)
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Use symmetric color scale centered at 0 for correlations
    vmax = max(abs(np.nanmin(correlation_values)), abs(np.nanmax(correlation_values)))
    vmin = -vmax
    
    # Plot correlation heatmap background using imshow
    im = ax.imshow(
        correlation_grid.T,  # Transpose for proper orientation
        cmap=cmap_heatmap,
        interpolation="nearest",
        origin="lower",
        extent=[0, 1, 0, 1],  # Match embedding coordinate space
        alpha=0.7,  # Semi-transparent for overlay visibility
        vmin=vmin,
        vmax=vmax
    )
    
    # Add colorbar for heatmap
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label(f"{correlation_method.title()} Correlation", rotation=270, labelpad=20)
    
    # Scatter overlay of training embeddings colored by target scores
    scatter = ax.scatter(
        training_embeddings[:, 0],
        training_embeddings[:, 1],
        c=target_scores,
        cmap=cmap_scatter,
        s=30,  # Point size
        alpha=0.8,
        edgecolors='black',
        linewidth=0.5
    )
    
    # Add colorbar for scatter points
    cbar_scatter = plt.colorbar(scatter, ax=ax, shrink=0.8, pad=0.1)
    cbar_scatter.set_label(f"Target: {target_name}", rotation=270, labelpad=20)
    
    # Set labels and title
    ax.set_xlabel("UMAP Dimension 1")
    ax.set_ylabel("UMAP Dimension 2")
    ax.set_title(f"Correlation Heatmap: {target_name} ({correlation_method.title()})")
    
    # Ensure proper aspect ratio
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect('equal')
    
    # Save if path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
    
    # Show if requested
    if show_plot:
        plt.show()
    
    # Close figure to free memory
    plt.close(fig)
    
    return fig


def plot_correlation_cluster_overlay(
    correlation_values: np.ndarray,
    training_embeddings: np.ndarray,
    target_scores: np.ndarray,
    cluster_sample_indices: np.ndarray,
    cluster_name: str,
    target_name: str,
    correlation_method: str = "pearson",
    output_path: Optional[Union[str, Path]] = None,
    show_plot: bool = False,
    grid_size: int = 100,
    figsize: tuple = (12, 8),
    cmap_heatmap: str = "RdBu_r"
) -> plt.Figure:
    """
    Plot correlation heatmap with highlighted significant cluster overlay.
    
    Same base correlation heatmap + highlight significant cluster points with 
    different colors. All training points shown in grey, cluster points colored.
    Only high significance regions are meaningful for correlation analysis.
    
    Args:
        correlation_values: Flattened correlation values (grid_size² length)
        training_embeddings: Training sample coordinates (N, 2)
        target_scores: Target values for training samples (N,)
        cluster_sample_indices: Indices of samples in significant cluster
        cluster_name: Name of cluster for labeling
        target_name: Name of target variable for labeling
        correlation_method: Correlation method used (default "pearson")
        output_path: Path to save PNG file (optional)
        show_plot: Whether to display plot
        grid_size: Size of heatmap grid (default 100)
        figsize: Figure size tuple
        cmap_heatmap: Colormap for correlation heatmap (diverging)
        
    Returns:
        matplotlib Figure object
    """
    # Reshape correlation values to grid
    if len(correlation_values) != grid_size * grid_size:
        raise ValueError(f"Expected {grid_size * grid_size} correlation values, got {len(correlation_values)}")
    
    correlation_grid = correlation_values.reshape(grid_size, grid_size)
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Use symmetric color scale centered at 0 for correlations
    vmax = max(abs(np.nanmin(correlation_values)), abs(np.nanmax(correlation_values)))
    vmin = -vmax
    
    # Plot correlation heatmap background using imshow
    im = ax.imshow(
        correlation_grid.T,  # Transpose for proper orientation
        cmap=cmap_heatmap,
        interpolation="nearest", 
        origin="lower",
        extent=[0, 1, 0, 1],  # Match embedding coordinate space
        alpha=0.6,  # More transparent for cluster visibility
        vmin=vmin,
        vmax=vmax
    )
    
    # Add colorbar for heatmap
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label(f"{correlation_method.title()} Correlation", rotation=270, labelpad=20)
    
    # Plot all training points in grey (background)
    ax.scatter(
        training_embeddings[:, 0],
        training_embeddings[:, 1],
        c='lightgrey',
        s=20,
        alpha=0.4,
        label='Training samples'
    )
    
    # Highlight cluster points with colors based on target scores
    if len(cluster_sample_indices) > 0:
        cluster_embeddings = training_embeddings[cluster_sample_indices]
        cluster_targets = target_scores[cluster_sample_indices]
        
        # Color cluster points by target values
        scatter = ax.scatter(
            cluster_embeddings[:, 0],
            cluster_embeddings[:, 1],
            c=cluster_targets,
            cmap='viridis',
            s=60,  # Larger points to stand out
            alpha=0.9,
            edgecolors='black',
            linewidth=1,
            label=f'{cluster_name} (high correlation)'
        )
        
        # Add colorbar for cluster points
        cbar_scatter = plt.colorbar(scatter, ax=ax, shrink=0.8, pad=0.1)
        cbar_scatter.set_label(f"Target: {target_name}", rotation=270, labelpad=20)
    
    # Set labels and title
    ax.set_xlabel("UMAP Dimension 1")
    ax.set_ylabel("UMAP Dimension 2")
    ax.set_title(f"Correlation Cluster Overlay: {target_name} - {cluster_name} ({correlation_method.title()})")
    
    # Add legend
    ax.legend(loc='upper right')
    
    # Ensure proper aspect ratio
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect('equal')
    
    # Save if path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
    
    # Show if requested
    if show_plot:
        plt.show()
    
    # Close figure to free memory
    plt.close(fig)
    
    return fig