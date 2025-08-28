"""
Tests for .npy fallback functionality in save_statistical_maps.

This module tests the enhanced save_statistical_maps function with .npy fallback
support for unsupported input_types.
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from emuses.tools.output_utils import save_statistical_maps


class TestSaveStatisticalMapsNpyFallback(unittest.TestCase):
    """Test .npy fallback functionality in save_statistical_maps."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create test statistical maps
        self.stat_maps = {
            "cluster_0": np.random.uniform(-1, 1, 100),
            "cluster_1": np.random.uniform(-0.5, 0.5, 100)
        }
    
    def test_npy_fallback_for_unsupported_input_type(self):
        """Test that unsupported input types fall back to .npy format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            # Test with an unsupported input type
            save_statistical_maps(
                stat_maps=self.stat_maps,
                output_folder=output_folder,
                input_type="unsupported_type",
                output_format_info=None,
                filename_prefix="test_fallback",
                save_output=True,
                generate_plots=False
            )
            
            # Should create .npy files for each cluster
            for cluster_name in self.stat_maps.keys():
                npy_file = output_folder / f"test_fallback_cluster_{cluster_name}.npy"
                self.assertTrue(npy_file.exists(), f"NPY file should exist for {cluster_name}")
                
                # Load and verify the saved data
                loaded_data = np.load(npy_file)
                np.testing.assert_array_equal(loaded_data, self.stat_maps[cluster_name])
    
    def test_npy_fallback_with_plots(self):
        """Test .npy fallback with plot generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            plots = save_statistical_maps(
                stat_maps=self.stat_maps,
                output_folder=output_folder,
                input_type="unsupported_type",
                output_format_info=None,
                filename_prefix="test_fallback",
                save_output=True,
                generate_plots=True
            )
            
            # Should return plots dictionary
            self.assertIsNotNone(plots)
            self.assertIn("cluster_0", plots)
            self.assertIn("cluster_1", plots)
            
            # Should create both .npy and .png files
            for cluster_name in self.stat_maps.keys():
                npy_file = output_folder / f"test_fallback_cluster_{cluster_name}.npy"
                png_file = output_folder / f"test_fallback_cluster_{cluster_name}_histogram.png"
                
                self.assertTrue(npy_file.exists(), f"NPY file should exist for {cluster_name}")
                self.assertTrue(png_file.exists(), f"PNG file should exist for {cluster_name}")
    
    def test_supported_input_types_still_work(self):
        """Test that supported input types still work as before."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            # Test with spreadsheet type (should work normally)
            columns = [f"feature_{i}" for i in range(100)]
            save_statistical_maps(
                stat_maps=self.stat_maps,
                output_folder=output_folder,
                input_type="spreadsheet",
                output_format_info=columns,
                filename_prefix="test_spreadsheet",
                save_output=True,
                generate_plots=False
            )
            
            # Should create CSV files, not .npy files
            for cluster_name in self.stat_maps.keys():
                csv_file = output_folder / f"test_spreadsheet_cluster_{cluster_name}.csv"
                npy_file = output_folder / f"test_spreadsheet_cluster_{cluster_name}.npy"
                
                self.assertTrue(csv_file.exists(), f"CSV file should exist for {cluster_name}")
                self.assertFalse(npy_file.exists(), f"NPY file should not exist for supported type")
    
    def test_npy_fallback_save_output_false(self):
        """Test .npy fallback when save_output is False."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            save_statistical_maps(
                stat_maps=self.stat_maps,
                output_folder=output_folder,
                input_type="unsupported_type",
                output_format_info=None,
                filename_prefix="test_nosave",
                save_output=False,
                generate_plots=False
            )
            
            # Should not create any files when save_output=False
            files_created = list(output_folder.glob("*"))
            self.assertEqual(len(files_created), 0, "No files should be created when save_output=False")


if __name__ == "__main__":
    unittest.main()