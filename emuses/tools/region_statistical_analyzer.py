"""
Region-based statistical analysis functionality for statistical maps in HeatmapStage.

This module provides the RegionStatisticalAnalyzer class that implements two-stage filtering,
HDBSCAN clustering within high-confidence regions, and statistical analysis via input_matrix_stat_map.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List

import hdbscan
import numpy as np

from emuses.tools.stats_utils import input_matrix_stat_map
from emuses.tools.output_utils import save_statistical_maps

logger = logging.getLogger(__name__)


class RegionStatisticalAnalyzer:
    """
    Creates statistical maps using two-stage filtering and region-based clustering analysis.

    Executes AFTER prediction and correlation grid creation with sophisticated region detection.
    Supports two-stage threshold filtering, HDBSCAN clustering, and statistical analysis.

    Parameters
    ----------
    visualization_threshold : float, default=0.2
        Confidence threshold for initial visualization filtering
    effect_size_threshold : float, default=0.5
        Prediction threshold for effect size filtering
    min_cluster_size : int, default=3
        Minimum cluster size for HDBSCAN clustering
    statistical_test : str, default="mann-whitney"
        Statistical test for input_matrix_stat_map. Options: "mann-whitney", "t-test"
    """

    VALID_STATISTICAL_TESTS = ["mann-whitney", "t-test"]

    def __init__(self,
                 visualization_threshold: float = 0.2,
                 effect_size_threshold: float = 0.5,
                 min_cluster_size: int = 3,
                 statistical_test: str = "mann-whitney"):
        # Validate thresholds
        if visualization_threshold < 0:
            raise ValueError("visualization_threshold must be non-negative")
        if effect_size_threshold < 0:
            raise ValueError("effect_size_threshold must be non-negative")
        if min_cluster_size <= 0:
            raise ValueError("min_cluster_size must be positive")

        # Validate statistical test
        if statistical_test not in self.VALID_STATISTICAL_TESTS:
            raise ValueError(f"Invalid statistical test: {statistical_test}. "
                             f"Valid tests: {self.VALID_STATISTICAL_TESTS}")

        self.visualization_threshold = visualization_threshold
        self.effect_size_threshold = effect_size_threshold
        self.min_cluster_size = min_cluster_size
        self.statistical_test = statistical_test

        logger.info(f"RegionStatisticalAnalyzer initialized with "
                    f"visualization_threshold={visualization_threshold}, "
                    f"effect_size_threshold={effect_size_threshold}, "
                    f"min_cluster_size={min_cluster_size}, "
                    f"statistical_test={statistical_test}")

    def apply_two_stage_filtering(self,
                                  grid_coords: np.ndarray,
                                  prediction_values: np.ndarray,
                                  confidence_values: np.ndarray) -> np.ndarray:
        """
        Apply two-stage threshold filtering for region selection.

        Implements visualization threshold (confidence) + effect size threshold (prediction)
        for identifying high-confidence regions suitable for clustering analysis.

        Parameters
        ----------
        grid_coords : np.ndarray
            Grid coordinates with shape (n_grid_points, 2)
        prediction_values : np.ndarray
            Prediction values with shape (n_grid_points,)
        confidence_values : np.ndarray
            Confidence values with shape (n_grid_points,)

        Returns
        -------
        np.ndarray
            Indices of grid points that pass both filtering stages
        """
        # Stage 1: Visualization threshold (confidence filtering)
        confidence_mask = confidence_values >= self.visualization_threshold

        # Stage 2: Effect size threshold (prediction filtering)
        effect_mask = prediction_values >= self.effect_size_threshold

        # Combine both filters
        combined_mask = confidence_mask & effect_mask
        filtered_indices = np.where(combined_mask)[0]

        logger.debug(f"Two-stage filtering: {len(filtered_indices)}/{len(grid_coords)} points passed")
        logger.debug(f"Confidence filter: {np.sum(confidence_mask)} points")
        logger.debug(f"Effect size filter: {np.sum(effect_mask)} points")

        return filtered_indices

    def perform_region_clustering(self, region_coords: np.ndarray) -> np.ndarray:
        """
        Perform HDBSCAN clustering within high-confidence regions.

        Applies density-based clustering to identify coherent regions within
        filtered coordinates for subsequent statistical analysis.

        Parameters
        ----------
        region_coords : np.ndarray
            Filtered region coordinates with shape (n_region_points, 2)

        Returns
        -------
        np.ndarray
            Cluster labels with shape (n_region_points,). Noise points have label -1
        """
        if len(region_coords) < self.min_cluster_size:
            logger.warning(f"Insufficient points for clustering: {len(region_coords)} < {self.min_cluster_size}")
            return np.full(len(region_coords), -1)

        logger.debug(f"Performing HDBSCAN clustering on {len(region_coords)} region points")

        # Create HDBSCAN clusterer
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=1  # Use default min_samples = 1
        )

        # Fit clustering model
        clusterer.fit(region_coords)

        cluster_labels = clusterer.labels_
        n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
        n_noise = list(cluster_labels).count(-1)

        logger.debug(f"HDBSCAN clustering result: {n_clusters} clusters, {n_noise} noise points")

        return cluster_labels

    def compute_statistical_analysis(self,
                                     input_matrix: np.ndarray,
                                     cluster_indices: List[np.ndarray]) -> Dict[str, Dict]:
        """
        Compute feature-space statistical analysis for clusters using input_matrix_stat_map.

        Performs statistical comparison for each cluster with ≥min_cluster_size points
        using input_matrix_stat_map to generate effect size maps.

        Parameters
        ----------
        input_matrix : np.ndarray
            Input matrix with shape (n_samples, n_features)
        cluster_indices : list of np.ndarray
            List of index arrays for each cluster

        Returns
        -------
        dict
            Statistical maps for each valid cluster
            Format: {"cluster_N": {"stat_map": array, "pval_map": array, "effect_size_map": array}}
        """
        statistical_maps = {}

        logger.debug(f"Computing statistical analysis for {len(cluster_indices)} clusters")

        for i, indices in enumerate(cluster_indices):
            if len(indices) < self.min_cluster_size:
                logger.debug(f"Skipping cluster {i}: {len(indices)} points < {self.min_cluster_size}")
                continue

            logger.debug(f"Processing cluster {i} with {len(indices)} points")

            try:
                # Compute statistical analysis using input_matrix_stat_map
                stat_map, pval_map, effect_size_map = input_matrix_stat_map(
                    input_matrix,
                    indices,
                    test_name=self.statistical_test
                )

                statistical_maps[f"cluster_{i}"] = {
                    "stat_map": stat_map,
                    "pval_map": pval_map,
                    "effect_size_map": effect_size_map
                }

                logger.debug(f"Cluster {i} effect size range: "
                             f"[{np.min(effect_size_map):.3f}, {np.max(effect_size_map):.3f}]")

            except Exception as e:
                logger.error(f"Failed to compute statistical analysis for cluster {i}: {e}")
                continue

        logger.info(f"Computed statistical analysis for {len(statistical_maps)} valid clusters")
        return statistical_maps

    def create_statistical_maps(self,
                                grid_coords: np.ndarray,
                                significance_values: np.ndarray,
                                input_matrix: np.ndarray,
                                target_data: Dict[str, np.ndarray],
                                output_folder: Path,
                                input_type: str,
                                output_format_info,
                                significance_source: str = 'prediction',
                                percentile_threshold: float = 5.0) -> Dict:
        """
        Enhanced interface: Create statistical maps with dual analysis and percentile thresholds.

        Creates target_*/{significance_source}-effects/ folder structure with artifacts.
        Supports symmetric percentile thresholds for both low and high significance regions.

        Parameters
        ----------
        grid_coords : np.ndarray
            Grid coordinates with shape (n_grid_points, 2)
        significance_values : np.ndarray
            Significance values for filtering (prediction×confidence or correlation values)
        input_matrix : np.ndarray
            Input matrix with shape (n_samples, n_features)
        target_data : dict
            Target variable data {target_name: scores, ...}
        output_folder : Path
            Base output directory
        input_type : str
            Data format type for save_statistical_maps ('nifti', 'image', 'spreadsheet')
        output_format_info : various
            Format info for save_statistical_maps (affine, shape, columns)
        significance_source : str, default='prediction'
            Source of significance values. Options: 'prediction', 'correlation'
            Determines output folder naming: prediction-effects/ or correlation-effects/
        percentile_threshold : float, default=5.0
            Percentile threshold for symmetric range (N% to (100-N)%).
            Creates low significance (< Nth percentile) and high significance (> (100-N)th percentile) regions

        Returns
        -------
        dict
            Results with artifact paths and metadata for all targets including dual significance regions
        """
        output_folder = Path(output_folder)

        # Validate significance source
        valid_sources = ['prediction', 'correlation']
        if significance_source not in valid_sources:
            raise ValueError(f"Invalid significance_source: {significance_source}. Valid options: {valid_sources}")

        # Validate percentile threshold
        if not (1.0 <= percentile_threshold <= 49.0):
            raise ValueError(f"percentile_threshold must be in range [1.0, 49.0], got: {percentile_threshold}")

        # Compute percentile thresholds
        low_threshold = np.percentile(significance_values, percentile_threshold)
        high_threshold = np.percentile(significance_values, 100 - percentile_threshold)

        results = {
            'statistical_results': {},
            'analysis_metadata': {
                'significance_source': significance_source,
                'percentile_threshold': percentile_threshold,
                'low_percentile_threshold': float(low_threshold),
                'high_percentile_threshold': float(high_threshold),
                'min_cluster_size': self.min_cluster_size,
                'statistical_test': self.statistical_test
            }
        }

        logger.info(f"Creating {significance_source} statistical maps for {len(target_data)} targets "
                    f"with {percentile_threshold}% percentile threshold")
        logger.info(f"Significance thresholds: low < {low_threshold:.4f}, high > {high_threshold:.4f}")

        # Identify low and high significance regions
        low_significance_mask = significance_values < low_threshold
        high_significance_mask = significance_values > high_threshold

        low_significance_indices = np.where(low_significance_mask)[0]
        high_significance_indices = np.where(high_significance_mask)[0]

        logger.info(f"Found {len(low_significance_indices)} low significance and "
                    f"{len(high_significance_indices)} high significance regions")

        # Process each target
        for target_name in target_data.keys():
            logger.info(f"Processing target: {target_name}")

            try:
                # Create target-specific output directory based on significance source
                folder_name = f"{significance_source}-effects"
                target_output = output_folder / f"target_{target_name}" / folder_name
                target_output.mkdir(parents=True, exist_ok=True)

                # Save low and high significance regions
                low_regions_path = target_output / "low_significance_regions.npy"
                high_regions_path = target_output / "high_significance_regions.npy"

                np.save(low_regions_path, low_significance_indices)
                np.save(high_regions_path, high_significance_indices)

                # Save metadata
                metadata = {
                    'target_name': target_name,
                    'significance_source': significance_source,
                    'percentile_threshold': percentile_threshold,
                    'low_percentile_threshold': float(low_threshold),
                    'high_percentile_threshold': float(high_threshold),
                    'low_significance_count': len(low_significance_indices),
                    'high_significance_count': len(high_significance_indices),
                    'total_regions': len(significance_values),
                    'artifacts': {
                        'low_significance_regions': str(low_regions_path),
                        'high_significance_regions': str(high_regions_path)
                    }
                }

                metadata_path = target_output / "metadata.json"
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                metadata['artifacts']['metadata'] = str(metadata_path)

                results['statistical_results'][target_name] = metadata

                logger.info(f"Created {significance_source} effects for target {target_name}: "
                            f"{len(low_significance_indices)} low + {len(high_significance_indices)} high regions")

            except Exception as e:
                logger.error(f"Failed to create {significance_source} effects for target {target_name}: {e}")
                results['statistical_results'][target_name] = {'error': str(e)}
                continue

        logger.info(f"Completed {significance_source} statistical maps for {len(results['statistical_results'])} targets")
        return results

    def create_region_statistical_maps(self,
                                       grid_coords: np.ndarray,
                                       prediction_values: np.ndarray,
                                       confidence_values: np.ndarray,
                                       input_matrix: np.ndarray,
                                       target_data: Dict[str, np.ndarray],
                                       output_folder: Path,
                                       input_type: str,
                                       output_format_info) -> Dict:
        """
        Main interface: Create region-based statistical maps for all targets.

        Implements complete workflow: two-stage filtering → region clustering → statistical analysis.
        Creates target_*/statistical-maps-*/ folder structure with artifacts.

        Parameters
        ----------
        grid_coords : np.ndarray
            Grid coordinates with shape (n_grid_points, 2)
        prediction_values : np.ndarray
            Prediction values with shape (n_grid_points,)
        confidence_values : np.ndarray
            Confidence values with shape (n_grid_points,)
        input_matrix : np.ndarray
            Input matrix with shape (n_samples, n_features)
        target_data : dict
            Target variable data {target_name: scores, ...}
        output_folder : Path
            Base output directory
        input_type : str
            Data format type for save_statistical_maps ('nifti', 'image', 'spreadsheet')
        output_format_info : various
            Format info for save_statistical_maps (affine, shape, columns)

        Returns
        -------
        dict
            Results with artifact paths and metadata for all targets
        """
        output_folder = Path(output_folder)
        results = {
            'statistical_results': {},
            'analysis_metadata': {
                'visualization_threshold': self.visualization_threshold,
                'effect_size_threshold': self.effect_size_threshold,
                'min_cluster_size': self.min_cluster_size,
                'statistical_test': self.statistical_test
            }
        }

        logger.info(f"Creating region-based statistical maps for {len(target_data)} targets")

        # Step 1: Apply two-stage filtering
        filtered_indices = self.apply_two_stage_filtering(
            grid_coords, prediction_values, confidence_values
        )

        if len(filtered_indices) == 0:
            logger.warning("No regions passed two-stage filtering")
            for target_name in target_data.keys():
                results['statistical_results'][target_name] = {
                    'clusters_analyzed': 0,
                    'message': 'No regions passed filtering thresholds'
                }
            return results

        # Step 2: Perform region clustering
        filtered_coords = grid_coords[filtered_indices]
        cluster_labels = self.perform_region_clustering(filtered_coords)

        # Extract cluster indices
        unique_clusters = set(cluster_labels)
        unique_clusters.discard(-1)  # Remove noise label
        cluster_indices = []
        for cluster_id in sorted(unique_clusters):
            cluster_mask = cluster_labels == cluster_id
            cluster_points = filtered_indices[cluster_mask]
            cluster_indices.append(cluster_points)

        logger.info(f"Found {len(cluster_indices)} clusters for statistical analysis")

        # Step 3: Process each target
        for target_name in target_data.keys():
            logger.info(f"Processing target: {target_name}")

            try:
                # Create target-specific output directory
                target_output = output_folder / f"target_{target_name}" / "statistical-maps-prediction"
                target_output.mkdir(parents=True, exist_ok=True)

                # Compute statistical analysis
                statistical_maps = self.compute_statistical_analysis(input_matrix, cluster_indices)

                if statistical_maps:
                    # Extract effect size maps for save_statistical_maps
                    effect_size_maps = {
                        cluster_name: data["effect_size_map"]
                        for cluster_name, data in statistical_maps.items()
                    }

                    # Save statistical maps using save_statistical_maps
                    save_statistical_maps(
                        effect_size_maps,
                        target_output,
                        input_type,
                        output_format_info,
                        filename_prefix="region_effect_size",
                        save_output=True,
                        generate_plots=False
                    )

                    # Save metadata
                    metadata = {
                        'target_name': target_name,
                        'clusters_analyzed': len(statistical_maps),
                        'filtering_results': {
                            'total_grid_points': len(grid_coords),
                            'points_after_filtering': len(filtered_indices),
                            'clusters_found': len(cluster_indices),
                            'valid_clusters': len(statistical_maps)
                        },
                        'thresholds': {
                            'visualization_threshold': self.visualization_threshold,
                            'effect_size_threshold': self.effect_size_threshold,
                            'min_cluster_size': self.min_cluster_size
                        },
                        'statistical_analysis': {
                            'test_method': self.statistical_test,
                            'clusters': {
                                cluster_name: {
                                    'effect_size_range': [float(np.min(data["effect_size_map"])),
                                                          float(np.max(data["effect_size_map"]))],
                                    'mean_effect_size': float(np.mean(data["effect_size_map"])),
                                    'std_effect_size': float(np.std(data["effect_size_map"]))
                                }
                                for cluster_name, data in statistical_maps.items()
                            }
                        }
                    }

                    metadata_path = target_output / "statistical_analysis_metadata.json"
                    with open(metadata_path, 'w') as f:
                        json.dump(metadata, f, indent=2)

                    results['statistical_results'][target_name] = metadata
                else:
                    results['statistical_results'][target_name] = {
                        'clusters_analyzed': 0,
                        'message': 'No clusters met minimum size requirements'
                    }

                logger.info(f"Created statistical maps for target {target_name}")

            except Exception as e:
                logger.error(f"Failed to create statistical maps for target {target_name}: {e}")
                results['statistical_results'][target_name] = {'error': str(e)}
                continue

        logger.info(f"Completed region-based statistical analysis for {len(results['statistical_results'])} targets")
        return results
