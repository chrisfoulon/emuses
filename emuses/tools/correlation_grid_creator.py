"""
Correlation grid creation functionality for statistical analysis in HeatmapStage.

This module provides the CorrelationGridCreator class that generates GWD-based
correlation analysis with sigma optimization and multiple correlation methods.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from scipy.stats import pearsonr, spearmanr, pointbiserialr

from emuses.tools.stats_utils import compute_gwd_for_point, compute_sigma_median

logger = logging.getLogger(__name__)


class CorrelationGridCreator:
    """
    Creates correlation heatmaps using GWD-based correlation analysis with sigma optimization.

    Executes AFTER nested CV training when models are available in pipeline context.
    Supports multiple correlation methods and automatic sigma optimization.

    Parameters
    ----------
    grid_size : int, default=100
        Grid resolution (creates grid_size x grid_size coordinate grid)
    correlation_methods : list, default=["pearson", "spearman"]
        List of correlation methods to apply. Options: "pearson", "spearman", "point_biserial"
    sigma : float, optional
        Gaussian kernel bandwidth. If None, will be optimized automatically
    """

    VALID_CORRELATION_METHODS = ["pearson", "spearman", "point_biserial"]

    def __init__(self,
                 grid_size: int = 100,
                 correlation_methods: List[str] = None,
                 sigma: Optional[float] = None):
        self.grid_size = grid_size
        self.correlation_methods = correlation_methods or ["pearson", "spearman"]
        self.sigma = sigma

        # Validate correlation methods
        for method in self.correlation_methods:
            if method not in self.VALID_CORRELATION_METHODS:
                raise ValueError(f"Invalid correlation method: {method}. "
                                 f"Valid methods: {self.VALID_CORRELATION_METHODS}")

        # Validate sigma
        if sigma is not None and sigma <= 0:
            raise ValueError("Sigma must be positive")

        logger.info(f"CorrelationGridCreator initialized with grid_size={grid_size}, "
                    f"correlation_methods={self.correlation_methods}, sigma={sigma}")

    def optimize_sigma(self, embeddings: np.ndarray, method: str = "median", 
                       percentile: float = 50.0, scaling_factor: float = 1.0) -> float:
        """
        Optimize sigma parameter for GWD vector computation using median pairwise distance.

        Uses median pairwise distance heuristic, which provides robust bandwidth estimation
        for distance-based computations. The median is less sensitive to outliers than mean
        and provides good coverage of the data distribution for 2D embedding spaces.

        Parameters
        ----------
        embeddings : np.ndarray
            Training embeddings with shape (n_samples, 2)
        method : str, default="median"
            Sigma optimization method. Options: "median", "percentile"
        percentile : float, default=50.0
            Percentile to use for "percentile" method (median = 50th percentile).
            Range: [1.0, 99.0]. Lower values (25th) give smaller sigma for tighter kernels,
            higher values (75th) give larger sigma for broader influence.
        scaling_factor : float, default=1.0
            Multiplicative factor to adjust the computed sigma. 
            Values < 1.0 create tighter kernels, > 1.0 create broader kernels.

        Returns
        -------
        float
            Optimized sigma value (median pairwise distance with optional scaling)

        Raises
        ------
        ValueError
            If unknown optimization method is specified or invalid parameters
        """
        if method == "median":
            sigma = compute_sigma_median(embeddings, sample_size=0)
            sigma *= scaling_factor
            logger.info(f"Optimized sigma using median pairwise distance: {sigma:.4f}")
            
        elif method == "percentile":
            if not (1.0 <= percentile <= 99.0):
                raise ValueError(f"Percentile must be in range [1.0, 99.0], got: {percentile}")
            
            # Use compute_sigma_median with custom percentile via stats_utils patterns
            # For now, use the median function and apply percentile post-processing
            sigma_base = compute_sigma_median(embeddings, sample_size=0)
            
            # Compute pairwise distances for percentile calculation
            from scipy.spatial.distance import pdist
            distances = pdist(embeddings, metric='euclidean')
            sigma = np.percentile(distances, percentile)
            sigma *= scaling_factor
            
            logger.info(f"Optimized sigma using {percentile}th percentile pairwise distance: {sigma:.4f}")
            logger.info(f"  (median reference: {sigma_base:.4f}, scaling_factor: {scaling_factor})")
            
        else:
            raise ValueError(f"Unknown sigma optimization method: {method}. "
                             f"Currently supported: ['median', 'percentile']")
        
        # Validation and diagnostic logging
        if sigma <= 0:
            raise ValueError(f"Computed sigma must be positive, got: {sigma}")
        
        logger.info(f"Final optimized sigma: {sigma:.4f} for {len(embeddings)} embedding points")
        return sigma

    def compute_gwd_vectors_for_grid(self,
                                     grid_coords: np.ndarray,
                                     embeddings: np.ndarray) -> np.ndarray:
        """
        Compute GWD vectors for all grid points using compute_gwd_for_point.

        Parameters
        ----------
        grid_coords : np.ndarray
            Grid coordinates with shape (n_grid_points, 2)
        embeddings : np.ndarray
            Training embeddings with shape (n_samples, 2)

        Returns
        -------
        np.ndarray
            GWD vectors with shape (n_grid_points, n_samples)

        Raises
        ------
        ValueError
            If sigma is not set
        """
        if self.sigma is None:
            raise ValueError("Sigma must be set before computing GWD vectors. "
                             "Use optimize_sigma() or provide sigma during initialization.")

        logger.debug(f"Computing GWD vectors for {len(grid_coords)} grid points "
                     f"using sigma={self.sigma}")

        gwd_vectors = np.zeros((len(grid_coords), len(embeddings)))

        for i, coord in enumerate(grid_coords):
            gwd_vector = compute_gwd_for_point(embeddings, coord, self.sigma)
            gwd_vectors[i] = gwd_vector

        logger.debug(f"Computed GWD vectors shape: {gwd_vectors.shape}")
        return gwd_vectors

    def compute_correlations(self,
                             gwd_vectors: np.ndarray,
                             target_scores: np.ndarray,
                             methods: Optional[List[str]] = None) -> Dict[str, np.ndarray]:
        """
        Compute correlations between GWD vectors and target scores.

        Supports multiple correlation methods: Pearson, Spearman, point-biserial.

        Parameters
        ----------
        gwd_vectors : np.ndarray
            GWD vectors with shape (n_grid_points, n_samples)
        target_scores : np.ndarray
            Target scores with shape (n_samples,)
        methods : list, optional
            Correlation methods to compute. If None, uses self.correlation_methods

        Returns
        -------
        dict
            Dictionary mapping method names to correlation values
            Format: {method_name: np.ndarray with shape (n_grid_points,)}

        Raises
        ------
        ValueError
            If unknown correlation method is specified
        """
        methods = methods or self.correlation_methods
        correlations = {}

        logger.debug(f"Computing correlations for {len(methods)} methods "
                     f"with {len(gwd_vectors)} grid points")

        for method in methods:
            if method not in self.VALID_CORRELATION_METHODS:
                raise ValueError(f"Unknown correlation method: {method}. "
                                 f"Valid methods: {self.VALID_CORRELATION_METHODS}")

            method_correlations = np.zeros(len(gwd_vectors))

            for i, gwd_vector in enumerate(gwd_vectors):
                if method == "pearson":
                    corr, _ = pearsonr(gwd_vector, target_scores)
                elif method == "spearman":
                    corr, _ = spearmanr(gwd_vector, target_scores)
                elif method == "point_biserial":
                    # For point-biserial, we need binary data
                    # Convert target scores to binary using median split
                    binary_target = (target_scores > np.median(target_scores)).astype(int)
                    corr, _ = pointbiserialr(binary_target, gwd_vector)

                method_correlations[i] = corr if not np.isnan(corr) else 0.0

            correlations[method] = method_correlations
            logger.debug(f"{method} correlation range: "
                         f"[{np.min(method_correlations):.3f}, {np.max(method_correlations):.3f}]")

        return correlations

    def generate_coordinate_grid(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Generate coordinate grid for correlation analysis.

        Reuses the same grid generation logic as GridCreator for consistency.

        Parameters
        ----------
        embeddings : np.ndarray
            Rescaled UMAP embeddings with shape (n_samples, 2)

        Returns
        -------
        np.ndarray
            Grid coordinates with shape (grid_size*grid_size, 2)
        """
        if embeddings.ndim != 2 or embeddings.shape[1] != 2:
            raise ValueError(f"embeddings must have shape (n_samples, 2), got: {embeddings.shape}")

        logger.debug(f"Generating {self.grid_size}x{self.grid_size} coordinate grid")

        # Create coordinate ranges (0-1) with small padding based on data range
        x_min, x_max = max(0, np.min(embeddings[:, 0]) - 0.05), min(1, np.max(embeddings[:, 0]) + 0.05)
        y_min, y_max = max(0, np.min(embeddings[:, 1]) - 0.05), min(1, np.max(embeddings[:, 1]) + 0.05)

        x_coords = np.linspace(x_min, x_max, self.grid_size)
        y_coords = np.linspace(y_min, y_max, self.grid_size)

        # Create meshgrid and flatten to coordinate pairs
        X, Y = np.meshgrid(x_coords, y_coords)
        grid_coords = np.column_stack([X.ravel(), Y.ravel()])

        logger.debug(f"Generated grid coordinates shape: {grid_coords.shape}")
        return grid_coords

    def create_correlation_heatmaps(self,
                                    embeddings: np.ndarray,
                                    target_data: Dict[str, np.ndarray],
                                    output_folder: Path,
                                    optimize_sigma: bool = False,
                                    sigma_method: str = "median",
                                    sigma_percentile: float = 50.0,
                                    sigma_scaling_factor: float = 1.0) -> Dict:
        """
        Main interface: Create correlation heatmaps for all targets.

        Creates target_*/correlation-grids/ folder structure with artifacts.

        Parameters
        ----------
        embeddings : np.ndarray
            Rescaled embeddings (0-1 coordinates) from pipeline context
        target_data : dict
            Target variable data {target_name: scores, ...}
        output_folder : Path
            Base output directory
        optimize_sigma : bool, default=False
            Whether to optimize sigma automatically if not set
        sigma_method : str, default="median"
            Sigma optimization method. Options: "median", "percentile"
        sigma_percentile : float, default=50.0
            Percentile for percentile method (range: [1.0, 99.0])
        sigma_scaling_factor : float, default=1.0
            Multiplicative scaling factor for computed sigma

        Returns
        -------
        dict
            Results with artifact paths and metadata for all targets
        """
        output_folder = Path(output_folder)
        results = {
            'correlation_results': {},
            'grid_metadata': {
                'grid_size': self.grid_size,
                'correlation_methods': self.correlation_methods,
                'sigma': self.sigma,
                'sigma_optimized': False
            }
        }

        # Optimize sigma if requested and not set
        if optimize_sigma and self.sigma is None:
            self.sigma = self.optimize_sigma(embeddings, method=sigma_method, 
                                           percentile=sigma_percentile, 
                                           scaling_factor=sigma_scaling_factor)
            results['grid_metadata']['sigma'] = self.sigma
            results['grid_metadata']['sigma_optimized'] = True
            results['grid_metadata']['sigma_method'] = sigma_method
            results['grid_metadata']['sigma_percentile'] = sigma_percentile
            results['grid_metadata']['sigma_scaling_factor'] = sigma_scaling_factor

        # Generate coordinate grid once for all targets
        grid_coords = self.generate_coordinate_grid(embeddings)

        # Compute GWD vectors once for all targets
        gwd_vectors = self.compute_gwd_vectors_for_grid(grid_coords, embeddings)

        logger.info(f"Creating correlation heatmaps for {len(target_data)} targets")

        # Process each target separately
        for target_name, target_scores in target_data.items():
            logger.info(f"Processing target: {target_name}")

            try:
                # Create target-specific output directory
                target_output = output_folder / f"target_{target_name}" / "correlation-grids"
                target_output.mkdir(parents=True, exist_ok=True)

                # Compute correlations for all methods
                correlations = self.compute_correlations(gwd_vectors, target_scores)

                # Save correlation results
                artifacts = {}
                for method, correlation_values in correlations.items():
                    correlation_file = target_output / f"correlation_values_{method}.npy"
                    np.save(correlation_file, correlation_values)
                    artifacts[f'correlation_values_{method}'] = str(correlation_file)

                # Save grid coordinates
                grid_coords_path = target_output / "grid_coordinates.npy"
                np.save(grid_coords_path, grid_coords)
                artifacts['grid_coordinates'] = str(grid_coords_path)

                # Save metadata
                metadata = {
                    'target_name': target_name,
                    'grid_size': self.grid_size,
                    'correlation_methods': self.correlation_methods,
                    'sigma': self.sigma,
                    'sigma_optimized': results['grid_metadata']['sigma_optimized'],
                    'grid_points': len(grid_coords),
                    'correlations': {
                        method: {
                            'range': [float(np.min(values)), float(np.max(values))],
                            'mean': float(np.mean(values)),
                            'std': float(np.std(values))
                        }
                        for method, values in correlations.items()
                    },
                    'artifacts': artifacts
                }

                metadata_path = target_output / "correlation_metadata.json"
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                metadata['artifacts']['metadata'] = str(metadata_path)

                results['correlation_results'][target_name] = metadata

                logger.info(f"Created correlation heatmaps for target {target_name}")
                for method in correlations:
                    corr_range = metadata['correlations'][method]['range']
                    logger.info(f"  {method}: [{corr_range[0]:.3f}, {corr_range[1]:.3f}]")

            except Exception as e:
                logger.error(f"Failed to create correlation heatmaps for target {target_name}: {e}")
                results['correlation_results'][target_name] = {'error': str(e)}
                continue

        logger.info(f"Completed correlation heatmap generation for {len(results['correlation_results'])} targets")
        return results
