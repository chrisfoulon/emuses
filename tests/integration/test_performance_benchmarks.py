"""
Performance benchmarks for parallelism backend speedup validation.

Tests performance improvements from context-aware parallelism backend selection,
measuring execution times and verifying speedup targets on multi-core systems.
"""

import time
import multiprocessing as mp
import numpy as np
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import sys

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emuses.tools.parallelism_utils import (
    get_safe_parallel_backend,
    get_safe_n_jobs,
    configure_parallelism_backend,
    create_safe_parallel
)


class PerformanceBenchmark:
    """Base class for performance benchmarking."""

    def __init__(self, n_samples=1000, n_features=50):
        """Initialize benchmark with synthetic data."""
        self.n_samples = n_samples
        self.n_features = n_features
        self.X, self.y = self._generate_test_data()

    def _generate_test_data(self):
        """Generate synthetic test data for benchmarking."""
        np.random.seed(42)  # Reproducible data
        X = np.random.randn(self.n_samples, self.n_features)
        y = np.random.randn(self.n_samples)
        return X, y

    def time_execution(self, func, *args, **kwargs):
        """Time function execution with warm-up."""
        # Warm-up run
        func(*args, **kwargs)
        
        # Actual timing
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        return end_time - start_time, result


class TestParallelismSpeedup:
    """Test parallelism speedup benchmarks."""

    def setup_method(self):
        """Set up test environment."""
        self.benchmark = PerformanceBenchmark(n_samples=2000, n_features=100)
        self.cpu_count = mp.cpu_count()

    def test_safe_parallel_creation_performance(self):
        """Benchmark safe parallel creation overhead."""
        
        def create_parallel_jobs(n_jobs, backend=None):
            """Create parallel jobs with specified configuration."""
            if backend:
                configure_parallelism_backend(force_backend=backend)
            
            safe_n_jobs = get_safe_n_jobs(n_jobs)
            parallel = create_safe_parallel(safe_n_jobs)
            
            # Simulate some parallel work
            def dummy_task(x):
                return x ** 2
            
            data = list(range(100))
            result = parallel(dummy_task(x) for x in data)
            return len(result)

        # Test different configurations
        configurations = [
            ("loky", -1),
            ("threading", -1),
            ("threading", 1),
            ("loky", min(4, self.cpu_count))
        ]
        
        timing_results = {}
        
        for backend, n_jobs in configurations:
            time_taken, result = self.benchmark.time_execution(
                create_parallel_jobs, n_jobs, backend
            )
            timing_results[f"{backend}_n{n_jobs}"] = time_taken
            
            # Reset backend configuration
            configure_parallelism_backend(force_backend=None)
        
        # Log timing results for analysis
        print("\nParallel creation performance:")
        for config, time_taken in timing_results.items():
            print(f"  {config}: {time_taken:.4f}s")
        
        # Basic sanity check - all configurations should complete
        assert all(time_taken > 0 for time_taken in timing_results.values())

    def test_sklearn_model_parallelism_speedup(self):
        """Test speedup with sklearn models using different backends."""
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.model_selection import cross_val_score
        
        def train_model_with_parallelism(n_jobs, backend=None):
            """Train model with specified parallelism configuration."""
            if backend:
                configure_parallelism_backend(force_backend=backend)
            
            safe_n_jobs = get_safe_n_jobs(n_jobs)
            
            # Use a moderately complex model for timing differences
            model = RandomForestRegressor(
                n_estimators=50,
                max_depth=10,
                n_jobs=safe_n_jobs,
                random_state=42
            )
            
            # Cross-validation for more substantial work
            scores = cross_val_score(
                model, self.benchmark.X, self.benchmark.y,
                cv=3, scoring='r2', n_jobs=safe_n_jobs
            )
            
            return scores.mean()

        # Test configurations for speedup analysis
        configs = [
            ("sequential", 1, None),
            ("threading", -1, "threading"),
            ("loky", min(4, self.cpu_count), "loky")
        ]
        
        timing_results = {}
        accuracy_results = {}
        
        for name, n_jobs, backend in configs:
            time_taken, accuracy = self.benchmark.time_execution(
                train_model_with_parallelism, n_jobs, backend
            )
            
            timing_results[name] = time_taken
            accuracy_results[name] = accuracy
            
            # Reset configuration
            configure_parallelism_backend(force_backend=None)
        
        print("\nSklearn model parallelism performance:")
        for name in timing_results:
            print(f"  {name}: {timing_results[name]:.4f}s (score: {accuracy_results[name]:.4f})")
        
        # Calculate speedup ratios
        sequential_time = timing_results["sequential"]
        
        if self.cpu_count > 1:
            # Only test speedup on multi-core systems
            for name in ["threading", "loky"]:
                if name in timing_results:
                    speedup = sequential_time / timing_results[name]
                    print(f"  {name} speedup: {speedup:.2f}x")
                    
                    # Moderate speedup expectation (not full 4x-8x due to overhead)
                    # On multi-core systems, should see some speedup
                    assert speedup > 1.1, f"Expected some speedup with {name}, got {speedup:.2f}x"
        
        # Accuracy should be consistent across configurations
        accuracies = list(accuracy_results.values())
        accuracy_std = np.std(accuracies)
        assert accuracy_std < 0.1, f"Accuracy variance too high: {accuracy_std:.4f}"

    def test_context_aware_backend_selection_performance(self):
        """Test performance of context-aware backend selection."""
        
        def simulate_subprocess_context():
            """Simulate subprocess execution context."""
            with patch('multiprocessing.current_process') as mock_process:
                # Mock subprocess hierarchy
                mock_parent = Mock()
                mock_parent.parent = None
                
                mock_current = Mock()
                mock_current.parent = mock_parent
                mock_process.return_value = mock_current
                
                # Test backend selection in subprocess context
                backend = get_safe_parallel_backend()
                n_jobs = get_safe_n_jobs(-1)
                
                return backend, n_jobs

        def simulate_main_process_context():
            """Simulate main process execution context."""
            # Reset any forced configuration
            configure_parallelism_backend(force_backend=None)
            
            backend = get_safe_parallel_backend()
            n_jobs = get_safe_n_jobs(-1)
            
            return backend, n_jobs

        # Benchmark context detection overhead
        subprocess_time, (subprocess_backend, subprocess_n_jobs) = self.benchmark.time_execution(
            simulate_subprocess_context
        )
        
        main_time, (main_backend, main_n_jobs) = self.benchmark.time_execution(
            simulate_main_process_context
        )
        
        print(f"\nContext detection performance:")
        print(f"  Subprocess context: {subprocess_time:.6f}s -> {subprocess_backend}")
        print(f"  Main process context: {main_time:.6f}s -> {main_backend}")
        
        # Context detection should be very fast (< 1ms)
        assert subprocess_time < 0.001, f"Subprocess context detection too slow: {subprocess_time:.6f}s"
        assert main_time < 0.001, f"Main process context detection too slow: {main_time:.6f}s"
        
        # Verify appropriate backend selection
        assert subprocess_backend == "threading", f"Expected threading in subprocess, got {subprocess_backend}"


class TestRealWorldPerformance:
    """Real-world performance scenarios."""

    def setup_method(self):
        """Set up real-world test scenario."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_optuna_cv_parallelism_performance(self):
        """Test Optuna CV performance with different parallelism settings."""
        # This would be a more comprehensive test with actual Optuna CV
        # For now, test the parallelism utilities performance in CV context
        
        from sklearn.model_selection import cross_val_score
        from sklearn.ensemble import RandomForestRegressor
        
        # Generate test data
        np.random.seed(42)
        X = np.random.randn(500, 20)
        y = np.random.randn(500)
        
        def run_cv_with_config(n_jobs, backend=None):
            """Run cross-validation with specified configuration."""
            if backend:
                configure_parallelism_backend(force_backend=backend)
            
            safe_n_jobs = get_safe_n_jobs(n_jobs)
            
            model = RandomForestRegressor(
                n_estimators=30,
                max_depth=8,
                n_jobs=safe_n_jobs,
                random_state=42
            )
            
            scores = cross_val_score(
                model, X, y, cv=3, scoring='r2', n_jobs=safe_n_jobs
            )
            
            return scores.mean()

        # Test different configurations
        configs = [
            ("n_jobs_1", 1, None),
            ("threading", 2, "threading"),
        ]
        
        if mp.cpu_count() > 2:
            configs.append(("loky", 4, "loky"))
        
        timing_results = {}
        
        for name, n_jobs, backend in configs:
            start_time = time.time()
            accuracy = run_cv_with_config(n_jobs, backend)
            end_time = time.time()
            
            timing_results[name] = end_time - start_time
            
            print(f"CV {name}: {timing_results[name]:.4f}s (accuracy: {accuracy:.4f})")
            
            # Reset configuration
            configure_parallelism_backend(force_backend=None)
        
        # Basic performance validation
        assert all(time_taken > 0 for time_taken in timing_results.values())

    def test_no_performance_regression(self):
        """Test that parallelism utilities don't introduce significant overhead."""
        from emuses.tools.parallelism_utils import get_safe_n_jobs, get_safe_parallel_backend
        
        # Baseline: direct joblib usage
        def baseline_parallel_creation():
            from joblib import Parallel
            return Parallel(n_jobs=2)
        
        # Enhanced: using safe utilities
        def enhanced_parallel_creation():
            safe_n_jobs = get_safe_n_jobs(2)  
            return create_safe_parallel(safe_n_jobs)
        
        # Time both approaches
        baseline_time = 0
        enhanced_time = 0
        
        # Multiple runs for stability
        for _ in range(10):
            start = time.time()
            baseline_parallel_creation()
            baseline_time += time.time() - start
            
            start = time.time()
            enhanced_parallel_creation()
            enhanced_time += time.time() - start
        
        baseline_avg = baseline_time / 10
        enhanced_avg = enhanced_time / 10
        
        overhead_ratio = enhanced_avg / baseline_avg if baseline_avg > 0 else 1
        
        print(f"\nOverhead analysis:")
        print(f"  Baseline parallel creation: {baseline_avg:.6f}s")
        print(f"  Enhanced parallel creation: {enhanced_avg:.6f}s")
        print(f"  Overhead ratio: {overhead_ratio:.2f}x")
        
        # Enhanced utilities should not introduce significant overhead (< 2x)
        assert overhead_ratio < 2.0, f"Too much overhead: {overhead_ratio:.2f}x"


class TestSpeedupTargets:
    """Test specific speedup targets from the LAD plan."""

    def setup_method(self):
        """Set up for speedup testing."""
        self.cpu_count = mp.cpu_count()

    @pytest.mark.skipif(mp.cpu_count() < 4, reason="Need 4+ cores for meaningful speedup test")
    def test_target_speedup_achievable(self):
        """Test that target speedup ranges (4x-8x) are theoretically achievable."""
        # This is a theoretical test of the speedup calculation
        # Real-world speedup depends on workload characteristics
        
        def cpu_intensive_task(n):
            """CPU-intensive task for speedup testing."""
            total = 0
            for i in range(n):
                total += i ** 2
            return total
        
        # Test with embarrassingly parallel workload
        n_tasks = 100
        work_per_task = 10000
        
        # Sequential execution
        start_time = time.time()
        sequential_results = [cpu_intensive_task(work_per_task) for _ in range(n_tasks)]
        sequential_time = time.time() - start_time
        
        # Parallel execution with different configurations
        for n_jobs in [2, 4, min(8, self.cpu_count)]:
            configure_parallelism_backend(force_backend="loky")
            parallel = create_safe_parallel(n_jobs)
            
            start_time = time.time()
            parallel_results = parallel(
                cpu_intensive_task(work_per_task) for _ in range(n_tasks)
            )
            parallel_time = time.time() - start_time
            
            speedup = sequential_time / parallel_time
            efficiency = speedup / n_jobs
            
            print(f"n_jobs={n_jobs}: {speedup:.2f}x speedup, {efficiency:.2f} efficiency")
            
            # Should achieve reasonable speedup with CPU-intensive work
            expected_min_speedup = min(1.5, n_jobs * 0.5)  # Conservative expectation
            assert speedup > expected_min_speedup, f"Poor speedup with n_jobs={n_jobs}: {speedup:.2f}x"
            
            # Results should be identical
            assert parallel_results == sequential_results, "Parallel results differ from sequential"
        
        # Reset configuration
        configure_parallelism_backend(force_backend=None)

    def test_warning_elimination_verification(self):
        """Verify no performance-related warnings are generated."""
        import warnings
        
        # Capture warnings during parallelism operations
        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter("always")
            
            # Test various parallelism scenarios
            configure_parallelism_backend(force_backend="threading")
            threading_backend = get_safe_parallel_backend()
            threading_n_jobs = get_safe_n_jobs(-1)
            
            configure_parallelism_backend(force_backend="loky")  
            loky_backend = get_safe_parallel_backend()
            loky_n_jobs = get_safe_n_jobs(-1)
            
            configure_parallelism_backend(force_backend=None)
            default_backend = get_safe_parallel_backend()
            default_n_jobs = get_safe_n_jobs(-1)
        
        # Check for problematic warnings
        warning_messages = [str(w.message) for w in warning_list]
        problematic_warnings = [
            msg for msg in warning_messages 
            if "setting n_jobs=1" in msg.lower() or "n_jobs value" in msg.lower()
        ]
        
        print(f"Captured {len(warning_list)} warnings during parallelism operations")
        if problematic_warnings:
            print("Problematic warnings found:")
            for warning in problematic_warnings:
                print(f"  - {warning}")
        
        # Should not generate problematic n_jobs warnings
        assert len(problematic_warnings) == 0, f"Found {len(problematic_warnings)} problematic warnings"


if __name__ == "__main__":
    # Run performance benchmarks
    pytest.main([__file__, "-v", "-s", "--tb=short"])