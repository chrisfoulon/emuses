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
from scipy.ndimage import label, binary_erosion

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
                # Use n_cores=1 to avoid daemonic processes conflict in pipeline context
                stat_map, pval_map, effect_size_map = input_matrix_stat_map(
                    input_matrix,
                    indices,
                    test_name=self.statistical_test,
                    n_cores=1
                )

                statistical_maps[f"cluster_{i}"] = {
                    "stat_map": stat_map,
                    "pval_map": pval_map,
                    "effect_size_map": effect_size_map,
                    "cluster_indices": indices  # Store cluster indices for visualization
                }

                logger.debug(f"Cluster {i} effect size range: "
                             f"[{np.min(effect_size_map):.3f}, {np.max(effect_size_map):.3f}]")

            except Exception as e:
                logger.error(f"Failed to compute statistical analysis for cluster {i}: {e}")
                continue

        logger.info(f"Computed statistical analysis for {len(statistical_maps)} valid clusters")
        return statistical_maps

    def _extract_region_boundary_points(self, mask: np.ndarray) -> np.ndarray:
        """
        Extract boundary points from a binary mask using erosion-based approach.

        Parameters
        ----------
        mask : np.ndarray
            Binary mask of significant region

        Returns
        -------
        np.ndarray
            Array of boundary points with shape (n_points, 2)
        """
        if not np.any(mask):
            return np.array([]).reshape(0, 2)

        # Find boundary by eroding mask and taking difference
        eroded = binary_erosion(mask)
        boundary = mask & ~eroded

        # Get boundary coordinates
        boundary_points = np.column_stack(np.where(boundary))
        return boundary_points

    def map_grid_to_training_samples(self,
                                     significance_values: np.ndarray,
                                     training_embeddings: np.ndarray,
                                     percentile_threshold: float,
                                     significance_source: str) -> Dict[str, np.ndarray]:
        """
        Map significant grid regions to training samples using region-based approach.

        COORDINATE SPACE: All operations in rescaled embedding space (0-1 range).
        Grid indices (0-grid_size) map directly to coordinates via simple linear scaling: coord = index/grid_size.

        DISCONNECTED REGIONS: Uses connected components to handle multiple disconnected regions,
        processing each region separately for point inclusion.

        Parameters
        ----------
        significance_values : np.ndarray
            Flat array of significance values with shape (grid_size²,)
        training_embeddings : np.ndarray
            Training sample coordinates in rescaled space (0-1 range) with shape (n_samples, 2)
        percentile_threshold : float
            Percentile threshold for significance filtering (e.g., 5.0 for 5%-95% range)
        significance_source : str
            Source type: 'prediction' (uses both high+low regions) or 'correlation' (high only)

        Returns
        -------
        dict
            Dictionary with 'high' and 'low' sample indices arrays
            (correlation only uses 'high', prediction uses both)
        """
        # Determine grid size from significance values
        grid_size = int(np.sqrt(len(significance_values)))
        if grid_size * grid_size != len(significance_values):
            raise ValueError(f"significance_values length {len(significance_values)} is not a perfect square")

        # Step 1: Create grid from flat values
        significance_grid = significance_values.reshape(grid_size, grid_size)

        # Step 2: Compute percentile thresholds
        high_threshold = np.percentile(significance_values, 100 - percentile_threshold)

        significant_sample_indices = {'high': [], 'low': []}

        # Step 3: Process high significance regions (both prediction & correlation)
        high_mask = significance_grid >= high_threshold
        if np.any(high_mask):
            # Find connected components in high significance regions
            labeled_regions, num_regions = label(high_mask)

            for region_id in range(1, num_regions + 1):  # Skip background (0)
                region_mask = (labeled_regions == region_id)
                region_coords = np.column_stack(np.where(region_mask))

                if len(region_coords) > 0:
                    # Convert grid indices to rescaled embedding coordinates (0-1 range)
                    # Simple linear mapping: coordinate = grid_index / grid_size
                    region_coords_scaled = region_coords / grid_size

                    # Create bounding box for efficiency
                    min_coords = region_coords_scaled.min(axis=0)
                    max_coords = region_coords_scaled.max(axis=0)

                    # Find training samples within bounding box
                    in_bounds = ((training_embeddings >= min_coords) &
                                 (training_embeddings <= max_coords)).all(axis=1)
                    candidate_indices = np.where(in_bounds)[0]

                    # For simple regions, use all candidates in bounding box
                    # (More sophisticated point-in-polygon could be added later)
                    significant_sample_indices['high'].extend(candidate_indices)

        # Step 4: Process low significance regions (prediction analysis only)
        if significance_source == 'prediction':
            low_threshold = np.percentile(significance_values, percentile_threshold)
            low_mask = significance_grid <= low_threshold
            if np.any(low_mask):
                # Find connected components in low significance regions
                labeled_regions, num_regions = label(low_mask)

                for region_id in range(1, num_regions + 1):  # Skip background (0)
                    region_mask = (labeled_regions == region_id)
                    region_coords = np.column_stack(np.where(region_mask))

                    if len(region_coords) > 0:
                        # Convert grid indices to rescaled embedding coordinates
                        region_coords_scaled = region_coords / grid_size

                        # Create bounding box
                        min_coords = region_coords_scaled.min(axis=0)
                        max_coords = region_coords_scaled.max(axis=0)

                        # Find training samples within bounding box
                        in_bounds = ((training_embeddings >= min_coords) &
                                     (training_embeddings <= max_coords)).all(axis=1)
                        candidate_indices = np.where(in_bounds)[0]

                        significant_sample_indices['low'].extend(candidate_indices)

        # Step 5: Remove duplicates and convert to numpy arrays
        for region_type in significant_sample_indices:
            significant_sample_indices[region_type] = np.unique(significant_sample_indices[region_type])

        logger.debug(f"Region mapping: {len(significant_sample_indices['high'])} high significance, "
                     f"{len(significant_sample_indices['low'])} low significance samples")

        return significant_sample_indices

    def _process_significance_region(self, region_type: str, sample_indices: np.ndarray,
                                     training_embeddings: np.ndarray, input_matrix: np.ndarray,
                                     target_name: str, target_output: Path, input_type: str,
                                     output_format_info, target_data: dict) -> int:
        """
        Process a single significance region (high or low) for statistical analysis.

        Parameters
        ----------
        region_type : str
            Type of region ('high' or 'low')
        sample_indices : np.ndarray
            Training sample indices within this significance region
        training_embeddings : np.ndarray
            Training sample coordinates
        input_matrix : np.ndarray
            Input matrix for statistical analysis
        target_name : str
            Target name for file naming
        target_output : Path
            Output directory path
        input_type : str
            Data format type
        output_format_info : various
            Format info for save_statistical_maps

        Returns
        -------
        int
            Number of clusters processed
        """
        if len(sample_indices) == 0:
            logger.warning(f"No {region_type} significance samples found for target {target_name}")
            return 0

        # Step 2: Apply HDBSCAN clustering to mapped samples
        if len(sample_indices) < self.min_cluster_size:
            logger.warning(f"Insufficient samples for clustering in {region_type} region: "
                           f"{len(sample_indices)} < {self.min_cluster_size}")
            return 0

        sample_coords = training_embeddings[sample_indices]
        cluster_labels = self.perform_region_clustering(sample_coords)

        # Extract cluster indices (map back to original sample space)
        unique_clusters = set(cluster_labels)
        unique_clusters.discard(-1)  # Remove noise label
        cluster_sample_indices = []

        for cluster_id in sorted(unique_clusters):
            cluster_mask = cluster_labels == cluster_id
            cluster_points = sample_indices[cluster_mask]
            if len(cluster_points) >= self.min_cluster_size:
                cluster_sample_indices.append(cluster_points)

        logger.info(f"Found {len(cluster_sample_indices)} valid clusters in {region_type} significance region")

        if not cluster_sample_indices:
            logger.warning(f"No clusters met minimum size requirements for {region_type} region")
            return 0

        # Step 3: Compute statistical analysis for each cluster
        statistical_maps = self.compute_statistical_analysis(input_matrix, cluster_sample_indices)

        if not statistical_maps:
            logger.warning(f"No valid clusters produced statistical maps for {region_type} region")
            return 0

        # Extract effect size maps for save_statistical_maps
        effect_size_maps = {}
        for cluster_name, data in statistical_maps.items():
            # Use simple cluster identifier and let save_statistical_maps handle the naming
            cluster_id = cluster_name.split('_')[1]  # Extract cluster number
            simple_cluster_id = f"{cluster_id}_{region_type}_{cluster_id}"
            effect_size_maps[simple_cluster_id] = data["effect_size_map"]

        # Step 4: Generate cluster overlay visualizations before saving maps
        try:
            self._generate_cluster_overlay_visualizations(
                statistical_maps, 
                target_name, 
                region_type,
                target_output,
                target_data,
                training_embeddings
            )
        except Exception as e:
            logger.error(f"Failed to generate cluster overlay visualizations: {e}")

        # Step 5: Save statistical maps using existing utility with proper prefix
        save_statistical_maps(
            effect_size_maps,
            target_output,
            input_type,
            output_format_info,
            filename_prefix=f"effect_size_map_{target_name}",
            save_output=True,
            generate_plots=False
        )

        return len(statistical_maps)

    def create_statistical_maps(self,
                                grid_coords: np.ndarray,
                                significance_values: np.ndarray,
                                input_matrix: np.ndarray,
                                target_data: Dict[str, np.ndarray],
                                output_folder: Path,
                                input_type: str,
                                output_format_info,
                                training_embeddings: np.ndarray,
                                significance_source: str = 'prediction',
                                percentile_threshold: float = 5.0) -> Dict:
        """
        Enhanced interface: Create statistical maps with complete contour detection workflow.

        Creates target_*/{significance_source}-effects/ folder structure with effect size maps.
        Implements full pipeline: grid→sample mapping, clustering, statistical analysis.

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
        training_embeddings : np.ndarray
            Training sample coordinates in rescaled space (0-1 range) with shape (n_samples, 2)
        significance_source : str, default='prediction'
            Source of significance values. Options: 'prediction', 'correlation'
            Determines output folder naming: prediction-effects/ or correlation-effects/
        percentile_threshold : float, default=5.0
            Percentile threshold for symmetric range (N% to (100-N)%).
            Creates low significance (< Nth percentile) and high significance (> (100-N)th percentile) regions

        Returns
        -------
        dict
            Results with artifact paths, effect size maps, and metadata for all targets
        """
        output_folder = Path(output_folder)

        # Validate significance source
        valid_sources = ['prediction', 'correlation']
        if significance_source not in valid_sources:
            raise ValueError(f"Invalid significance_source: {significance_source}. Valid options: {valid_sources}")

        # Validate percentile threshold
        if not (1.0 <= percentile_threshold <= 49.0):
            raise ValueError(f"percentile_threshold must be in range [1.0, 49.0], got: {percentile_threshold}")

        results = {
            'statistical_results': {},
            'analysis_metadata': {
                'significance_source': significance_source,
                'percentile_threshold': percentile_threshold,
                'min_cluster_size': self.min_cluster_size,
                'statistical_test': self.statistical_test
            }
        }

        logger.info(f"Creating {significance_source} statistical maps for {len(target_data)} targets "
                    f"with {percentile_threshold}% percentile threshold")

        # Step 1: Map grid regions to training sample indices using contour detection
        significant_sample_indices = self.map_grid_to_training_samples(
            significance_values=significance_values,
            training_embeddings=training_embeddings,
            percentile_threshold=percentile_threshold,
            significance_source=significance_source
        )

        logger.info(f"Mapped to training samples: {len(significant_sample_indices['high'])} high significance, "
                    f"{len(significant_sample_indices['low'])} low significance samples")

        # Process each target
        for target_name in target_data.keys():
            logger.info(f"Processing target: {target_name}")

            try:
                # Create target-specific output directory based on significance source
                folder_name = f"{significance_source}-effects"
                # Check if output_folder already contains target structure (e.g., .../target_0/)
                if output_folder.name.startswith(f"target_"):
                    # HeatmapStage already created target-specific folder
                    target_output = output_folder / folder_name
                else:
                    # Create target structure ourselves
                    target_output = output_folder / f"target_{target_name}" / folder_name
                target_output.mkdir(parents=True, exist_ok=True)

                target_results = {
                    'target_name': target_name,
                    'significance_source': significance_source,
                    'percentile_threshold': percentile_threshold,
                    'artifacts': {},
                    'clusters_processed': {}
                }

                # Process high and low significance regions
                region_types = ['high']
                if significance_source == 'prediction':
                    region_types.append('low')

                for region_type in region_types:
                    sample_indices = significant_sample_indices[region_type]
                    clusters_processed = self._process_significance_region(
                        region_type, sample_indices, training_embeddings, input_matrix,
                        target_name, target_output, input_type, output_format_info, target_data
                    )
                    target_results['clusters_processed'][region_type] = clusters_processed

                # Save significance region indices for reference
                high_regions_path = target_output / "high_significance_regions.npy"
                np.save(high_regions_path, significant_sample_indices['high'])
                target_results['artifacts']['high_significance_regions'] = str(high_regions_path)

                if significance_source == 'prediction':
                    low_regions_path = target_output / "low_significance_regions.npy"
                    np.save(low_regions_path, significant_sample_indices['low'])
                    target_results['artifacts']['low_significance_regions'] = str(low_regions_path)

                # Save metadata
                metadata_path = target_output / "metadata.json"
                with open(metadata_path, 'w') as f:
                    json.dump(target_results, f, indent=2)
                target_results['artifacts']['metadata'] = str(metadata_path)

                results['statistical_results'][target_name] = target_results

                total_clusters = sum(target_results['clusters_processed'].values())
                logger.info(f"Completed statistical analysis for target {target_name}: {total_clusters} total clusters processed")

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
                # Check if output_folder already contains target structure (e.g., .../target_0/)
                if output_folder.name.startswith(f"target_"):
                    # HeatmapStage already created target-specific folder
                    target_output = output_folder / "statistical-maps-prediction"
                else:
                    # Create target structure ourselves
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

    def _generate_cluster_overlay_visualizations(self, 
                                               statistical_maps: dict, 
                                               target_name: str, 
                                               region_type: str,
                                               target_output: Path,
                                               target_data: dict,
                                               training_embeddings: np.ndarray):
        """
        Generate cluster overlay visualizations for processed statistical maps.
        
        Creates overlay visualizations showing heatmap + highlighted cluster points,
        following the pattern from Task 3.3 in the analysis API plan.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Import visualization functions
            from emuses.tools.heatmap_visualization import (
                plot_prediction_cluster_overlay,
                plot_correlation_cluster_overlay
            )
            
            # Get target scores for scatter overlay
            target_scores = target_data[target_name]
            
            # Determine analysis type from method call context 
            # This is passed from the HeatmapStage based on which analysis is running
            if hasattr(self, '_current_analysis_type'):
                analysis_type = self._current_analysis_type
            else:
                # Fallback: infer from available data
                if hasattr(self, '_prediction_heatmap_data'):
                    analysis_type = "prediction"
                elif hasattr(self, '_correlation_heatmap_data'):
                    analysis_type = "correlation"
                else:
                    logger.warning("No heatmap data available for visualization")
                    return
            
            # Select appropriate data and plot function
            if analysis_type == "prediction" and hasattr(self, '_prediction_heatmap_data'):
                heatmap_values = self._prediction_heatmap_data
                plot_function = plot_prediction_cluster_overlay
            elif analysis_type == "correlation" and hasattr(self, '_correlation_heatmap_data'):
                heatmap_values = self._correlation_heatmap_data  
                plot_function = plot_correlation_cluster_overlay
            else:
                logger.warning(f"No {analysis_type} heatmap data available for visualization")
                return
                
            # Create visualizations folder
            viz_folder = target_output / "cluster_visualizations"
            viz_folder.mkdir(exist_ok=True)
            
            # Generate overlay for each processed cluster
            for cluster_name, cluster_data in statistical_maps.items():
                try:
                    cluster_indices = cluster_data["cluster_indices"]
                    cluster_id = cluster_name.split('_')[1]
                    
                    # Determine significance type and output filename based on analysis type
                    if analysis_type == "prediction":
                        significance_type = region_type  # high or low
                        filename = f"prediction_heatmap_{target_name}_cluster_{cluster_id}_{significance_type}_overlay.png"
                    else:  # correlation
                        significance_type = "high"  # Correlation only has high regions
                        filename = f"correlation_heatmap_{target_name}_cluster_{cluster_id}_high_overlay.png"
                    
                    output_path = viz_folder / filename
                    
                    # Generate cluster overlay visualization with function-specific parameters
                    if analysis_type == "prediction":
                        plot_function(
                            heatmap_values=heatmap_values,
                            training_embeddings=training_embeddings,
                            target_scores=target_scores,
                            cluster_sample_indices=cluster_indices,
                            cluster_name=f"Cluster {cluster_id}",
                            target_name=target_name,
                            significance_type=significance_type,
                            output_path=output_path,
                            show_plot=False
                        )
                    else:  # correlation
                        plot_function(
                            correlation_values=heatmap_values,
                            training_embeddings=training_embeddings,
                            target_scores=target_scores,
                            cluster_sample_indices=cluster_indices,
                            cluster_name=f"Cluster {cluster_id}",
                            target_name=target_name,
                            output_path=output_path,
                            show_plot=False
                        )
                    
                    logger.info(f"Generated cluster overlay: {filename}")
                    
                except Exception as e:
                    logger.error(f"Failed to generate overlay for {cluster_name}: {e}")
                    continue
                    
        except ImportError as e:
            logger.error(f"Failed to import visualization functions: {e}")
        except Exception as e:
            logger.error(f"Failed to generate cluster overlay visualizations: {e}")
