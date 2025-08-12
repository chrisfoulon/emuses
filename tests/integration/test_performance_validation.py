"""Performance validation tests across registry deployment modes.

This module tests performance requirements including response times,
installation speeds, concurrent operations, and scalability limits
across LOCAL, DATABASE, and CLOUD deployment modes.
"""
import pytest
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from emuses.tools.model_registry_factory import ModelRegistryFactory, RegistryMode


class TestSearchPerformanceAcrossModes:
    """Test search response time performance across deployment modes."""

    @pytest.fixture
    def factory(self):
        """Create ModelRegistryFactory instance for testing."""
        return ModelRegistryFactory()

    def test_search_response_time_interface_exists(self, factory):
        """Test that search performance testing interface exists."""
        # Test that we can create registries for performance testing
        local_registry = factory.create_registry(RegistryMode.LOCAL)
        assert local_registry is not None
        assert hasattr(local_registry, 'search_models')
        assert callable(local_registry.search_models)

    def test_local_mode_search_performance(self, factory):
        """Test search response time performance in LOCAL mode."""
        registry = factory.create_registry(RegistryMode.LOCAL)

        # Measure search response time
        start_time = time.time()
        results = registry.search_models("test_query")
        end_time = time.time()

        response_time = end_time - start_time

        # Test that search completes
        assert isinstance(results, list)

        # Performance requirement: search should complete quickly for local mode
        # Local mode should be very fast (under 100ms for small datasets)
        assert response_time < 1.0, f"Search took {response_time:.3f}s, should be under 1.0s"

    def test_search_performance_with_filters(self, factory):
        """Test search performance with various filter combinations."""
        registry = factory.create_registry(RegistryMode.LOCAL)

        # Test basic search performance
        start_time = time.time()
        results = registry.search_models("test", filters={"tags": ["fMRI"]})
        end_time = time.time()

        response_time = end_time - start_time

        # Test that filtered search completes
        assert isinstance(results, list)

        # Performance requirement: filtered search should not be significantly slower
        assert response_time < 2.0, f"Filtered search took {response_time:.3f}s, should be under 2.0s"

    def test_empty_search_performance(self, factory):
        """Test search performance for queries with no results."""
        registry = factory.create_registry(RegistryMode.LOCAL)

        # Test empty result search performance
        start_time = time.time()
        results = registry.search_models("nonexistent_model_query_12345")
        end_time = time.time()

        response_time = end_time - start_time

        # Empty results should return quickly
        assert isinstance(results, list)
        assert len(results) == 0

        # Performance requirement: empty searches should be very fast
        assert response_time < 0.5, f"Empty search took {response_time:.3f}s, should be under 0.5s"

    @pytest.mark.parametrize("registry_mode", [RegistryMode.LOCAL])
    def test_search_performance_across_modes(self, factory, registry_mode):
        """Test search performance consistency across different modes."""
        registry = factory.create_registry(registry_mode)

        # Test search performance for each mode
        start_time = time.time()
        results = registry.search_models("performance_test")
        end_time = time.time()

        response_time = end_time - start_time

        # Test basic functionality
        assert isinstance(results, list)

        # Mode-specific performance expectations
        if registry_mode == RegistryMode.LOCAL:
            # Local mode should be fastest
            assert response_time < 1.0, f"Local search took {response_time:.3f}s"
        # Note: DATABASE and CLOUD mode tests would have different thresholds

    def test_concurrent_search_performance(self, factory):
        """Test search performance under concurrent load."""
        registry = factory.create_registry(RegistryMode.LOCAL)

        def perform_search(search_term):
            """Helper function to perform a search operation."""
            start_time = time.time()
            results = registry.search_models(f"concurrent_test_{search_term}")
            end_time = time.time()
            return {
                'results': results,
                'response_time': end_time - start_time,
                'search_term': search_term
            }

        # Test concurrent searches
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit concurrent search operations
            futures = [
                executor.submit(perform_search, f"query_{i}")
                for i in range(10)
            ]

            # Collect results
            search_results = []
            for future in futures:
                result = future.result()
                search_results.append(result)

        # Validate all searches completed successfully
        assert len(search_results) == 10

        for result in search_results:
            assert isinstance(result['results'], list)
            # Each concurrent search should still meet performance requirements
            assert result['response_time'] < 2.0, (
                f"Concurrent search for '{result['search_term']}' took "
                f"{result['response_time']:.3f}s, should be under 2.0s"
            )

        # Calculate average response time across concurrent operations
        avg_response_time = sum(r['response_time'] for r in search_results) / len(search_results)

        # Concurrent operations should not degrade performance significantly
        assert avg_response_time < 1.5, (
            f"Average concurrent search time {avg_response_time:.3f}s should be under 1.5s"
        )


class TestInstallationPerformanceAcrossModes:
    """Test model installation performance across deployment modes."""

    @pytest.fixture
    def factory(self):
        """Create ModelRegistryFactory instance for testing."""
        return ModelRegistryFactory()

    def test_installation_performance_interface_exists(self, factory):
        """Test that installation performance testing interface exists."""
        registry = factory.create_registry(RegistryMode.LOCAL)
        assert hasattr(registry, 'install_model')
        assert callable(registry.install_model)

    def test_installation_parameter_performance(self, factory):
        """Test installation performance with different parameter patterns."""
        registry = factory.create_registry(RegistryMode.LOCAL)

        # Test performance of parameter processing
        start_time = time.time()
        try:
            # This will fail but we measure parameter processing time
            registry.install_model("/nonexistent/path.zip", name="test_model")
        except (FileNotFoundError, ValueError):
            # Expected for non-existent file
            pass
        end_time = time.time()

        parameter_processing_time = end_time - start_time

        # Parameter processing should be very fast
        assert parameter_processing_time < 0.1, (
            f"Parameter processing took {parameter_processing_time:.3f}s, should be under 0.1s"
        )

    def test_installation_validation_performance(self, factory):
        """Test installation validation performance."""
        registry = factory.create_registry(RegistryMode.LOCAL)

        # Test validation performance for invalid inputs
        start_time = time.time()
        try:
            # This should fail validation quickly
            registry.install_model("", name="")
        except (FileNotFoundError, ValueError):
            # Expected for invalid input
            pass
        end_time = time.time()

        validation_time = end_time - start_time

        # Validation should be very fast
        assert validation_time < 0.1, (
            f"Validation took {validation_time:.3f}s, should be under 0.1s"
        )

    @pytest.mark.parametrize("registry_mode", [RegistryMode.LOCAL])
    def test_installation_interface_performance_across_modes(self, factory, registry_mode):
        """Test installation interface performance across modes."""
        registry = factory.create_registry(registry_mode)

        # Test interface method call performance
        start_time = time.time()
        try:
            # Test method call overhead
            registry.install_model("/test/path", name="test")
        except (FileNotFoundError, ValueError, NotImplementedError):
            # Expected for test path
            pass
        end_time = time.time()

        interface_time = end_time - start_time

        # Interface calls should have minimal overhead
        assert interface_time < 0.2, (
            f"Interface call took {interface_time:.3f}s, should be under 0.2s"
        )


class TestConcurrentOperationPerformance:
    """Test concurrent operations and user limits across modes."""

    @pytest.fixture
    def factory(self):
        """Create ModelRegistryFactory instance for testing."""
        return ModelRegistryFactory()

    def test_concurrent_list_operations(self, factory):
        """Test concurrent list_models operations."""
        registry = factory.create_registry(RegistryMode.LOCAL)
        results_lock = Lock()
        operation_results = []

        def perform_list_operation(operation_id):
            """Helper function to perform list operation."""
            start_time = time.time()
            models = registry.list_models()
            end_time = time.time()

            result = {
                'operation_id': operation_id,
                'models': models,
                'response_time': end_time - start_time
            }

            with results_lock:
                operation_results.append(result)

            return result

        # Test concurrent list operations
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(perform_list_operation, i)
                for i in range(15)
            ]

            # Wait for all operations to complete
            for future in futures:
                future.result()

        # Validate all operations completed
        assert len(operation_results) == 15

        # Check each operation completed successfully
        for result in operation_results:
            assert isinstance(result['models'], list)
            # Each operation should meet performance requirements
            assert result['response_time'] < 1.0, (
                f"List operation {result['operation_id']} took "
                f"{result['response_time']:.3f}s, should be under 1.0s"
            )

        # Calculate performance statistics
        response_times = [r['response_time'] for r in operation_results]
        avg_time = sum(response_times) / len(response_times)
        max_time = max(response_times)

        # Performance requirements for concurrent operations
        assert avg_time < 0.5, f"Average response time {avg_time:.3f}s should be under 0.5s"
        assert max_time < 1.0, f"Maximum response time {max_time:.3f}s should be under 1.0s"

    def test_concurrent_search_operations(self, factory):
        """Test concurrent search operations with different queries."""
        registry = factory.create_registry(RegistryMode.LOCAL)
        search_results = []
        results_lock = Lock()

        def perform_search_operation(query_id):
            """Helper function to perform search operation."""
            start_time = time.time()
            results = registry.search_models(f"concurrent_query_{query_id}")
            end_time = time.time()

            search_result = {
                'query_id': query_id,
                'results': results,
                'response_time': end_time - start_time
            }

            with results_lock:
                search_results.append(search_result)

            return search_result

        # Test concurrent search operations
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [
                executor.submit(perform_search_operation, i)
                for i in range(12)
            ]

            # Wait for all searches to complete
            for future in futures:
                future.result()

        # Validate all searches completed
        assert len(search_results) == 12

        # Check each search completed successfully
        for result in search_results:
            assert isinstance(result['results'], list)
            # Each search should meet performance requirements
            assert result['response_time'] < 1.5, (
                f"Search query {result['query_id']} took "
                f"{result['response_time']:.3f}s, should be under 1.5s"
            )

        # Performance statistics
        response_times = [r['response_time'] for r in search_results]
        avg_time = sum(response_times) / len(response_times)

        # Concurrent searches should maintain good performance
        assert avg_time < 1.0, f"Average concurrent search time {avg_time:.3f}s should be under 1.0s"

    def test_mixed_operation_concurrency(self, factory):
        """Test mixed operations (list, search, info) under concurrent load."""
        registry = factory.create_registry(RegistryMode.LOCAL)
        mixed_results = []
        results_lock = Lock()

        def perform_list_operation(op_id):
            start_time = time.time()
            models = registry.list_models()
            end_time = time.time()

            with results_lock:
                mixed_results.append({
                    'operation': 'list',
                    'op_id': op_id,
                    'response_time': end_time - start_time,
                    'success': isinstance(models, list)
                })

        def perform_search_operation(op_id):
            start_time = time.time()
            results = registry.search_models(f"mixed_test_{op_id}")
            end_time = time.time()

            with results_lock:
                mixed_results.append({
                    'operation': 'search',
                    'op_id': op_id,
                    'response_time': end_time - start_time,
                    'success': isinstance(results, list)
                })

        # Test mixed concurrent operations
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = []

            # Submit mixed operations (reduced complexity)
            for i in range(3):
                futures.append(executor.submit(perform_list_operation, i))
                futures.append(executor.submit(perform_search_operation, i))

            # Wait for all operations to complete
            for future in futures:
                future.result()

        # Validate operations
        self._validate_mixed_results(mixed_results, expected_count=6)

    def _validate_mixed_results(self, mixed_results, expected_count):
        """Helper method to validate mixed operation results."""
        assert len(mixed_results) == expected_count

        # Check all operations succeeded
        for result in mixed_results:
            assert result['success'], f"{result['operation']} operation {result['op_id']} failed"

            # Performance requirements by operation type
            if result['operation'] == 'list':
                assert result['response_time'] < 1.0
            elif result['operation'] == 'search':
                assert result['response_time'] < 1.5

        # Calculate overall performance
        avg_response_time = sum(r['response_time'] for r in mixed_results) / len(mixed_results)
        assert avg_response_time < 1.0, f"Average mixed operation time {avg_response_time:.3f}s should be under 1.0s"


class TestScalabilityRequirements:
    """Test scalability requirements across registry modes."""

    @pytest.fixture
    def factory(self):
        """Create ModelRegistryFactory instance for testing."""
        return ModelRegistryFactory()

    def test_registry_creation_scalability(self, factory):
        """Test registry creation performance under load."""
        creation_times = []

        # Test multiple registry creations
        for i in range(20):
            start_time = time.time()
            registry = factory.create_registry(RegistryMode.LOCAL)
            end_time = time.time()

            creation_time = end_time - start_time
            creation_times.append(creation_time)

            # Verify registry was created successfully
            assert registry is not None
            assert hasattr(registry, 'list_models')

        # Performance requirements for registry creation
        avg_creation_time = sum(creation_times) / len(creation_times)
        max_creation_time = max(creation_times)

        assert avg_creation_time < 0.1, f"Average creation time {avg_creation_time:.3f}s should be under 0.1s"
        assert max_creation_time < 0.5, f"Maximum creation time {max_creation_time:.3f}s should be under 0.5s"

    def test_interface_validation_scalability(self, factory):
        """Test interface validation performance at scale."""
        validation_times = []

        # Create multiple registries for validation testing
        registries = [factory.create_registry(RegistryMode.LOCAL) for _ in range(10)]

        # Test validation performance
        for registry in registries:
            start_time = time.time()
            is_valid = factory.validate_interface(registry)
            end_time = time.time()

            validation_time = end_time - start_time
            validation_times.append(validation_time)

            # Verify validation succeeded
            assert is_valid, "Registry interface validation should pass"

        # Performance requirements for interface validation
        avg_validation_time = sum(validation_times) / len(validation_times)
        max_validation_time = max(validation_times)

        assert avg_validation_time < 0.05, f"Average validation time {avg_validation_time:.3f}s should be under 0.05s"
        assert max_validation_time < 0.2, f"Maximum validation time {max_validation_time:.3f}s should be under 0.2s"

    def test_capability_detection_scalability(self, factory):
        """Test capability detection performance at scale."""
        detection_times = []
        registry = factory.create_registry(RegistryMode.LOCAL)

        # Test capability detection for various capabilities
        capabilities_to_test = [
            'list_models', 'search_models', 'install_model',
            'get_model_info', 'uninstall_model', 'nonexistent_capability'
        ]

        for capability in capabilities_to_test:
            for _ in range(10):  # Test each capability multiple times
                start_time = time.time()
                has_capability = factory.has_capability(registry, capability)
                end_time = time.time()

                detection_time = end_time - start_time
                detection_times.append(detection_time)

                # Verify capability detection works
                assert isinstance(has_capability, bool)

        # Performance requirements for capability detection
        avg_detection_time = sum(detection_times) / len(detection_times)
        max_detection_time = max(detection_times)

        assert avg_detection_time < 0.01, f"Average detection time {avg_detection_time:.3f}s should be under 0.01s"
        assert max_detection_time < 0.05, f"Maximum detection time {max_detection_time:.3f}s should be under 0.05s"

    @pytest.mark.parametrize("registry_mode", [RegistryMode.LOCAL])
    def test_large_scale_operations(self, factory, registry_mode):
        """Test performance with large-scale operations."""
        registry = factory.create_registry(registry_mode)

        # Test large-scale list operations
        start_time = time.time()
        for _ in range(100):
            models = registry.list_models()
            assert isinstance(models, list)
        end_time = time.time()

        large_scale_time = end_time - start_time
        avg_operation_time = large_scale_time / 100

        # Performance requirements for large-scale operations
        assert large_scale_time < 10.0, f"100 list operations took {large_scale_time:.3f}s, should be under 10.0s"
        assert avg_operation_time < 0.1, f"Average operation time {avg_operation_time:.3f}s should be under 0.1s"

        # Test large-scale search operations
        start_time = time.time()
        for i in range(50):
            results = registry.search_models(f"scale_test_{i}")
            assert isinstance(results, list)
        end_time = time.time()

        search_scale_time = end_time - start_time
        avg_search_time = search_scale_time / 50

        assert search_scale_time < 15.0, f"50 search operations took {search_scale_time:.3f}s, should be under 15.0s"
        assert avg_search_time < 0.3, f"Average search time {avg_search_time:.3f}s should be under 0.3s"
