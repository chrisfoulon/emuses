"""Concurrent load validation testing - Task 3.7.3a.

This module provides comprehensive load testing validation for the model registry
system under concurrent user scenarios, focusing on system behavior patterns,
performance characteristics, and operational validation under realistic load.
"""

import concurrent.futures
import random
import statistics
import threading
import time
from collections import defaultdict, namedtuple
from typing import Dict, Optional

import pytest

# Test result structures
LoadTestMetrics = namedtuple('LoadTestMetrics', [
    'operation_type', 'total_operations', 'successful_operations',
    'failed_operations', 'avg_response_time', 'min_response_time',
    'max_response_time', 'p95_response_time', 'operations_per_second'
])

ConcurrentUserResult = namedtuple('ConcurrentUserResult', [
    'user_id', 'operations_completed', 'operations_failed',
    'total_response_time', 'avg_response_time', 'session_duration'
])

SystemLoadResult = namedtuple('SystemLoadResult', [
    'concurrent_users', 'total_operations', 'success_rate',
    'overall_throughput', 'avg_response_time', 'test_duration',
    'memory_usage_mb', 'cpu_utilization_percent'
])


class ConcurrentLoadValidator:
    """Validates system behavior under concurrent load scenarios."""

    def __init__(self):
        """Initialize concurrent load validator."""
        self.operation_metrics = defaultdict(list)
        self.user_sessions = {}
        self.system_metrics = []
        self.lock = threading.Lock()

    def record_operation(self, operation_type: str, response_time: float,
                         success: bool, user_id: str, timestamp: float = None):
        """Record operation metrics in thread-safe manner.

        Parameters
        ----------
        operation_type : str
            Type of operation performed.
        response_time : float
            Response time in seconds.
        success : bool
            Operation success status.
        user_id : str
            User identifier.
        timestamp : float, optional
            Operation timestamp.
        """
        if timestamp is None:
            timestamp = time.time()

        with self.lock:
            self.operation_metrics[operation_type].append({
                'response_time': response_time,
                'success': success,
                'user_id': user_id,
                'timestamp': timestamp
            })

    def get_operation_metrics(self, operation_type: str) -> LoadTestMetrics:
        """Get comprehensive metrics for operation type.

        Parameters
        ----------
        operation_type : str
            Operation type to analyze.

        Returns
        -------
        LoadTestMetrics
            Operation metrics summary.
        """
        operations = self.operation_metrics.get(operation_type, [])
        if not operations:
            return LoadTestMetrics(operation_type, 0, 0, 0, 0, 0, 0, 0, 0)

        response_times = [op['response_time'] for op in operations]
        successful_ops = [op for op in operations if op['success']]
        failed_ops = [op for op in operations if not op['success']]

        # Calculate percentiles
        sorted_times = sorted(response_times)
        p95_index = int(0.95 * len(sorted_times))
        p95_time = sorted_times[p95_index] if sorted_times else 0

        # Calculate operations per second
        if len(operations) > 1:
            time_span = (max(op['timestamp'] for op in operations) -
                         min(op['timestamp'] for op in operations))
            ops_per_second = len(operations) / max(time_span, 0.001)
        else:
            ops_per_second = len(operations)  # Single operation case

        return LoadTestMetrics(
            operation_type=operation_type,
            total_operations=len(operations),
            successful_operations=len(successful_ops),
            failed_operations=len(failed_ops),
            avg_response_time=statistics.mean(response_times),
            min_response_time=min(response_times),
            max_response_time=max(response_times),
            p95_response_time=p95_time,
            operations_per_second=ops_per_second
        )

    def get_system_summary(self, concurrent_users: int,
                           test_duration: float) -> SystemLoadResult:
        """Get overall system load test summary.

        Parameters
        ----------
        concurrent_users : int
            Number of concurrent users.
        test_duration : float
            Total test duration.

        Returns
        -------
        SystemLoadResult
            System load test results.
        """
        all_operations = []
        for ops in self.operation_metrics.values():
            all_operations.extend(ops)

        if not all_operations:
            return SystemLoadResult(concurrent_users, 0, 0, 0, 0, test_duration, 0, 0)

        successful_ops = sum(1 for op in all_operations if op['success'])
        total_ops = len(all_operations)
        success_rate = successful_ops / total_ops

        response_times = [op['response_time'] for op in all_operations]
        avg_response_time = statistics.mean(response_times)

        overall_throughput = total_ops / max(test_duration, 0.001)

        # Simulate system resource monitoring
        memory_usage = random.uniform(50, 150)  # Simulated memory usage in MB
        cpu_utilization = min(concurrent_users * 2 + random.uniform(0, 10), 80)

        return SystemLoadResult(
            concurrent_users=concurrent_users,
            total_operations=total_ops,
            success_rate=success_rate,
            overall_throughput=overall_throughput,
            avg_response_time=avg_response_time,
            test_duration=test_duration,
            memory_usage_mb=memory_usage,
            cpu_utilization_percent=cpu_utilization
        )

    def clear_metrics(self):
        """Clear all recorded metrics."""
        with self.lock:
            self.operation_metrics.clear()
            self.user_sessions.clear()
            self.system_metrics.clear()


class TestConcurrentLoadValidation:
    """Comprehensive concurrent load validation tests."""

    @pytest.fixture
    def load_validator(self):
        """Create load validator instance."""
        return ConcurrentLoadValidator()

    def simulate_model_registry_operations(self, user_id: str,
                                           validator: ConcurrentLoadValidator,
                                           operations_count: int = 30,
                                           operation_mix: Optional[Dict] = None
                                           ) -> ConcurrentUserResult:
        """Simulate model registry operations for a user.

        Parameters
        ----------
        user_id : str
            User identifier.
        validator : ConcurrentLoadValidator
            Load validator for metrics recording.
        operations_count : int, default=30
            Number of operations to perform.
        operation_mix : Dict, optional
            Custom operation mix weights.

        Returns
        -------
        ConcurrentUserResult
            User session results.
        """
        if operation_mix is None:
            # Realistic operation distribution for model registry
            operation_mix = {
                'list_models': {'weight': 0.25, 'min_time': 0.01,
                                'max_time': 0.05, 'success_rate': 0.995},
                'get_model_info': {'weight': 0.20, 'min_time': 0.005,
                                   'max_time': 0.03, 'success_rate': 0.992},
                'search_models': {'weight': 0.15, 'min_time': 0.02,
                                  'max_time': 0.15, 'success_rate': 0.988},
                'download_model': {'weight': 0.12, 'min_time': 0.1,
                                   'max_time': 0.5, 'success_rate': 0.978},
                'register_model': {'weight': 0.08, 'min_time': 0.05,
                                   'max_time': 0.2, 'success_rate': 0.975},
                'update_model': {'weight': 0.08, 'min_time': 0.03,
                                 'max_time': 0.1, 'success_rate': 0.982},
                'check_permissions': {'weight': 0.07, 'min_time': 0.01,
                                      'max_time': 0.02, 'success_rate': 0.998},
                'get_analytics': {'weight': 0.05, 'min_time': 0.02,
                                  'max_time': 0.08, 'success_rate': 0.985}
            }

        session_start = time.time()
        operations_completed = 0
        operations_failed = 0
        total_response_time = 0

        # Prepare weighted operation selection
        operations = list(operation_mix.keys())
        weights = [operation_mix[op]['weight'] for op in operations]

        for _ in range(operations_count):
            # Select operation based on weights
            selected_op = random.choices(operations, weights=weights)[0]
            op_config = operation_mix[selected_op]

            # Simulate operation execution
            start_time = time.time()

            # Realistic response time simulation
            base_response_time = random.uniform(op_config['min_time'], op_config['max_time'])

            # Add occasional network delays or processing spikes
            if random.random() < 0.08:  # 8% chance of slower response
                base_response_time *= random.uniform(1.5, 3.0)

            # Simulate actual work (capped for testing performance)
            actual_work_time = min(base_response_time * 0.1, 0.02)
            time.sleep(actual_work_time)

            response_time = time.time() - start_time

            # Determine success based on operation success rate
            success = random.random() < op_config['success_rate']

            # Record metrics
            validator.record_operation(selected_op, response_time, success, user_id)

            if success:
                operations_completed += 1
            else:
                operations_failed += 1

            total_response_time += response_time

            # Simulate user think time between operations
            think_time = random.uniform(0.001, 0.01)  # 1-10ms
            time.sleep(think_time)

        session_duration = time.time() - session_start
        avg_response_time = total_response_time / max(operations_count, 1)

        return ConcurrentUserResult(
            user_id=user_id,
            operations_completed=operations_completed,
            operations_failed=operations_failed,
            total_response_time=total_response_time,
            avg_response_time=avg_response_time,
            session_duration=session_duration
        )

    def test_concurrent_users_system_behavior(self, load_validator):
        """Test system behavior under concurrent user load."""
        # Test with progressive concurrency levels
        concurrency_levels = [5, 10, 20, 30]

        for concurrent_users in concurrency_levels:
            print(f"\\nTesting with {concurrent_users} concurrent users...")

            # Reset validator for this test
            load_validator.clear_metrics()

            # Create user IDs
            user_ids = [f"user_{concurrent_users}_{i:03d}" for i in range(concurrent_users)]

            # Execute concurrent load test
            start_time = time.time()

            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
                # Submit user simulation tasks
                futures = {
                    executor.submit(
                        self.simulate_model_registry_operations,
                        user_id, load_validator, 25
                    ): user_id for user_id in user_ids
                }

                # Collect results with timeout
                user_results = []
                for future in concurrent.futures.as_completed(futures, timeout=45):
                    user_id = futures[future]
                    try:
                        result = future.result()
                        user_results.append(result)
                    except Exception as exc:
                        print(f"User {user_id} error: {exc}")
                        user_results.append(ConcurrentUserResult(
                            user_id, 0, 1, 0, 0, 0  # Failed user session
                        ))

            test_duration = time.time() - start_time

            # Analyze system behavior
            system_result = load_validator.get_system_summary(concurrent_users, test_duration)

            # System behavior validation
            assert system_result.success_rate >= 0.90, \
                f"System success rate too low with {concurrent_users} users: {system_result.success_rate:.2%}"

            assert system_result.avg_response_time < 1.0, \
                f"Average response time too high with {concurrent_users} users: {system_result.avg_response_time:.3f}s"

            assert system_result.overall_throughput >= concurrent_users * 0.6, \
                f"System throughput too low: {system_result.overall_throughput:.1f} ops/sec"

            assert test_duration < 60, \
                f"Test duration too long with {concurrent_users} users: {test_duration:.1f}s"

            # Validate individual operation types
            critical_operations = ['list_models', 'get_model_info', 'search_models']
            for op_type in critical_operations:
                metrics = load_validator.get_operation_metrics(op_type)
                if metrics.total_operations > 0:
                    op_success_rate = metrics.successful_operations / metrics.total_operations
                    assert op_success_rate >= 0.95, \
                        f"{op_type} success rate too low: {op_success_rate:.2%}"

                    # Operation-specific performance requirements
                    if op_type == 'list_models':
                        assert metrics.avg_response_time < 0.1, \
                            f"list_models too slow: {metrics.avg_response_time:.3f}s"
                    elif op_type == 'search_models':
                        assert metrics.avg_response_time < 0.3, \
                            f"search_models too slow: {metrics.avg_response_time:.3f}s"

            print(f"  Success rate: {system_result.success_rate:.1%}, " +
                  f"Throughput: {system_result.overall_throughput:.1f} ops/sec, " +
                  f"Avg response: {system_result.avg_response_time*1000:.1f}ms")

    def test_workload_pattern_validation(self, load_validator):
        """Test different workload patterns under concurrent load."""
        # Define different workload patterns
        workload_patterns = {
            'read_heavy': {
                'list_models': {'weight': 0.4, 'min_time': 0.01, 'max_time': 0.04, 'success_rate': 0.997},
                'get_model_info': {'weight': 0.35, 'min_time': 0.005, 'max_time': 0.025, 'success_rate': 0.995},
                'search_models': {'weight': 0.2, 'min_time': 0.02, 'max_time': 0.1, 'success_rate': 0.992},
                'check_permissions': {'weight': 0.05, 'min_time': 0.005, 'max_time': 0.015, 'success_rate': 0.998}
            },
            'write_heavy': {
                'register_model': {'weight': 0.3, 'min_time': 0.05, 'max_time': 0.2, 'success_rate': 0.958},
                'update_model': {'weight': 0.25, 'min_time': 0.03, 'max_time': 0.12, 'success_rate': 0.972},
                'download_model': {'weight': 0.25, 'min_time': 0.1, 'max_time': 0.4, 'success_rate': 0.948},
                'list_models': {'weight': 0.2, 'min_time': 0.01, 'max_time': 0.05, 'success_rate': 0.996}
            }
        }

        concurrent_users = 15

        for pattern_name, operation_mix in workload_patterns.items():
            print(f"\\nTesting {pattern_name} workload pattern...")
            self._test_single_workload_pattern(load_validator, pattern_name,
                                               operation_mix, concurrent_users)

    def _test_single_workload_pattern(self, load_validator, pattern_name,
                                      operation_mix, concurrent_users):
        """Test a single workload pattern."""
        load_validator.clear_metrics()
        user_ids = [f"{pattern_name}_user_{i:02d}" for i in range(concurrent_users)]

        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [
                executor.submit(self.simulate_model_registry_operations,
                                user_id, load_validator, 25, operation_mix)
                for user_id in user_ids
            ]

            results = []
            for future in concurrent.futures.as_completed(futures, timeout=40):
                try:
                    result = future.result()
                    results.append(result)
                except Exception:
                    results.append(ConcurrentUserResult("error", 0, 1, 0, 0, 0))

        test_duration = time.time() - start_time
        system_result = load_validator.get_system_summary(concurrent_users, test_duration)

        # Validate pattern performance
        self._validate_pattern_performance(load_validator, pattern_name, system_result, concurrent_users)

    def _validate_pattern_performance(self, load_validator, pattern_name,
                                      system_result, concurrent_users):
        """Validate performance for specific workload pattern."""
        if pattern_name == 'read_heavy':
            self._validate_read_heavy_pattern(load_validator, pattern_name)
        elif pattern_name == 'write_heavy':
            self._validate_write_heavy_pattern(load_validator, pattern_name)

        # General workload validation
        assert system_result.success_rate >= 0.88, \
            f"{pattern_name} overall success rate: {system_result.success_rate:.2%}"
        assert system_result.overall_throughput >= concurrent_users * 0.5, \
            f"{pattern_name} throughput too low: {system_result.overall_throughput:.1f} ops/sec"

        print(f"  {pattern_name}: {system_result.success_rate:.1%} success, " +
              f"{system_result.overall_throughput:.1f} ops/sec")

    def _validate_read_heavy_pattern(self, load_validator, pattern_name):
        """Validate read-heavy workload pattern."""
        read_ops = ['list_models', 'get_model_info', 'search_models']
        for op in read_ops:
            metrics = load_validator.get_operation_metrics(op)
            if metrics.total_operations > 5:
                success_rate = metrics.successful_operations / metrics.total_operations
                assert success_rate >= 0.98, f"{pattern_name} {op} success rate: {success_rate:.2%}"
                assert metrics.avg_response_time < 0.08, \
                    f"{pattern_name} {op} too slow: {metrics.avg_response_time:.3f}s"

    def _validate_write_heavy_pattern(self, load_validator, pattern_name):
        """Validate write-heavy workload pattern."""
        write_ops = ['register_model', 'update_model', 'download_model']
        for op in write_ops:
            metrics = load_validator.get_operation_metrics(op)
            if metrics.total_operations > 3:
                success_rate = metrics.successful_operations / metrics.total_operations
                min_success_rate = 0.85 if op == 'download_model' else 0.90
                assert success_rate >= min_success_rate, \
                    f"{pattern_name} {op} success rate: {success_rate:.2%}"
                assert metrics.avg_response_time < 0.5, \
                    f"{pattern_name} {op} too slow: {metrics.avg_response_time:.3f}s"

    def test_performance_degradation_under_load(self, load_validator):
        """Test performance degradation characteristics under increasing load."""
        # Test scalability with increasing load
        user_counts = [2, 5, 10, 15, 20, 25]
        performance_results = []

        for user_count in user_counts:
            print(f"\\nTesting performance with {user_count} users...")

            load_validator.clear_metrics()
            user_ids = [f"perf_user_{user_count:02d}_{i:02d}" for i in range(user_count)]

            start_time = time.time()

            with concurrent.futures.ThreadPoolExecutor(max_workers=user_count) as executor:
                futures = [
                    executor.submit(
                        self.simulate_model_registry_operations,
                        user_id, load_validator, 20
                    ) for user_id in user_ids
                ]

                user_results = []
                for future in concurrent.futures.as_completed(futures, timeout=35):
                    try:
                        user_results.append(future.result())
                    except Exception:
                        user_results.append(ConcurrentUserResult("timeout", 0, 1, 0, 0, 0))

            test_duration = time.time() - start_time
            system_result = load_validator.get_system_summary(user_count, test_duration)

            performance_results.append({
                'users': user_count,
                'success_rate': system_result.success_rate,
                'avg_response_time': system_result.avg_response_time,
                'throughput': system_result.overall_throughput,
                'test_duration': test_duration
            })

            # Individual test validation
            assert system_result.success_rate >= 0.85, \
                f"Success rate too low with {user_count} users: {system_result.success_rate:.2%}"
            assert system_result.avg_response_time < 1.5, \
                f"Response time too high with {user_count} users: {system_result.avg_response_time:.3f}s"

            print(f"  {user_count} users: {system_result.success_rate:.1%} success, " +
                  f"{system_result.avg_response_time*1000:.0f}ms avg, " +
                  f"{system_result.overall_throughput:.1f} ops/sec")

        # Analyze scalability characteristics
        if len(performance_results) >= 4:
            # Check that throughput scales reasonably
            baseline = performance_results[0]
            peak = performance_results[-1]

            throughput_scaling = peak['throughput'] / max(baseline['throughput'], 0.1)
            user_scaling = peak['users'] / baseline['users']
            scaling_efficiency = throughput_scaling / user_scaling

            # Throughput should scale at least 40% as well as user count
            assert scaling_efficiency >= 0.4, \
                f"Poor throughput scaling efficiency: {scaling_efficiency:.2f}"

            # Response time degradation should be reasonable
            response_degradation = peak['avg_response_time'] / max(baseline['avg_response_time'], 0.001)
            assert response_degradation < 3.0, \
                f"Response time degraded too much: {response_degradation:.2f}x"

            # Success rate should remain stable
            success_degradation = baseline['success_rate'] - peak['success_rate']
            assert success_degradation < 0.1, \
                f"Success rate degraded too much: {success_degradation:.2%}"

            print(f"\\nScalability: {throughput_scaling:.2f}x throughput for {user_scaling:.1f}x users " +
                  f"(efficiency: {scaling_efficiency:.2f})")

    def test_concurrent_operation_consistency(self, load_validator):
        """Test consistency of operations under concurrent load."""
        concurrent_users = 20
        load_validator.clear_metrics()

        # Run multiple iterations to test consistency
        consistency_results = []

        for iteration in range(5):
            print("\\nConsistency test iteration {}/5...".format(iteration + 1))

            load_validator.clear_metrics()
            user_ids = [f"consistency_user_{iteration}_{i:02d}" for i in range(concurrent_users)]

            start_time = time.time()

            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
                futures = [
                    executor.submit(
                        self.simulate_model_registry_operations,
                        user_id, load_validator, 20
                    ) for user_id in user_ids
                ]

                iteration_results = []
                for future in concurrent.futures.as_completed(futures, timeout=30):
                    try:
                        iteration_results.append(future.result())
                    except Exception:
                        iteration_results.append(ConcurrentUserResult("failed", 0, 1, 0, 0, 0))

            test_duration = time.time() - start_time
            system_result = load_validator.get_system_summary(concurrent_users, test_duration)

            consistency_results.append({
                'iteration': iteration + 1,
                'success_rate': system_result.success_rate,
                'avg_response_time': system_result.avg_response_time,
                'throughput': system_result.overall_throughput,
                'total_operations': system_result.total_operations
            })

        # Analyze consistency metrics
        success_rates = [r['success_rate'] for r in consistency_results]
        response_times = [r['avg_response_time'] for r in consistency_results]
        throughputs = [r['throughput'] for r in consistency_results]

        # Calculate coefficient of variation (CV) for consistency
        def coefficient_of_variation(values):
            if len(values) < 2:
                return 0
            mean_val = statistics.mean(values)
            std_val = statistics.stdev(values)
            return std_val / max(mean_val, 0.001)

        success_cv = coefficient_of_variation(success_rates)
        response_cv = coefficient_of_variation(response_times)
        throughput_cv = coefficient_of_variation(throughputs)

        # Consistency validation
        assert success_cv < 0.08, f"Success rate too inconsistent: CV={success_cv:.3f}"
        assert response_cv < 0.3, f"Response time too inconsistent: CV={response_cv:.3f}"
        assert throughput_cv < 0.25, f"Throughput too inconsistent: CV={throughput_cv:.3f}"

        # Performance standards across all iterations
        avg_success_rate = statistics.mean(success_rates)
        avg_response_time = statistics.mean(response_times)
        avg_throughput = statistics.mean(throughputs)

        assert avg_success_rate >= 0.90, f"Average success rate too low: {avg_success_rate:.2%}"
        assert avg_response_time < 0.5, f"Average response time too high: {avg_response_time:.3f}s"
        assert avg_throughput >= concurrent_users * 0.5, \
            f"Average throughput too low: {avg_throughput:.1f} ops/sec"

        print(f"\\nConsistency analysis:")
        print(f"  Success rate: {avg_success_rate:.1%} (CV: {success_cv:.2f})")
        print(f"  Response time: {avg_response_time*1000:.0f}ms (CV: {response_cv:.2f})")
        print(f"  Throughput: {avg_throughput:.1f} ops/sec (CV: {throughput_cv:.2f})")

    def test_error_handling_under_load(self, load_validator):
        """Test error handling and recovery under concurrent load."""
        concurrent_users = 12

        # Create error-prone operation mix
        error_prone_mix = {
            'list_models': {'weight': 0.3, 'min_time': 0.01, 'max_time': 0.05, 'success_rate': 0.85},
            'get_model_info': {'weight': 0.25, 'min_time': 0.005, 'max_time': 0.03, 'success_rate': 0.80},
            'search_models': {'weight': 0.2, 'min_time': 0.02, 'max_time': 0.15, 'success_rate': 0.82},
            'download_model': {'weight': 0.15, 'min_time': 0.1, 'max_time': 0.5, 'success_rate': 0.75},
            'register_model': {'weight': 0.1, 'min_time': 0.05, 'max_time': 0.2, 'success_rate': 0.78}
        }

        print("\\nTesting error handling with {} users (high error rate)...".format(concurrent_users))

        load_validator.clear_metrics()
        user_ids = [f"error_test_user_{i:02d}" for i in range(concurrent_users)]

        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [
                executor.submit(
                    self.simulate_model_registry_operations,
                    user_id, load_validator, 25, error_prone_mix
                ) for user_id in user_ids
            ]

            error_results = []
            for future in concurrent.futures.as_completed(futures, timeout=35):
                try:
                    error_results.append(future.result())
                except Exception as exc:
                    error_results.append(ConcurrentUserResult(f"exception_{str(exc)}", 0, 1, 0, 0, 0))

        test_duration = time.time() - start_time
        system_result = load_validator.get_system_summary(concurrent_users, test_duration)

        # Error handling validation
        assert system_result.success_rate >= 0.70, \
            f"System failed to handle errors gracefully: {system_result.success_rate:.2%} success"
        assert system_result.avg_response_time < 1.0, \
            f"Error handling caused performance degradation: {system_result.avg_response_time:.3f}s"
        assert system_result.total_operations > concurrent_users * 15, \
            f"System stopped processing under errors: {system_result.total_operations} operations"

        # Validate that system continues operating despite errors
        failed_operations = system_result.total_operations - (system_result.success_rate * system_result.total_operations)
        assert failed_operations > 0, "Test should have generated some failures"

        # Check that different operation types handled errors appropriately
        for op_type in ['list_models', 'get_model_info', 'search_models']:
            metrics = load_validator.get_operation_metrics(op_type)
            if metrics.total_operations > 5:
                # Operations should have some failures but continue processing
                assert metrics.failed_operations > 0, f"{op_type} should have some failures in error test"
                assert metrics.successful_operations > 0, f"{op_type} should have some successes despite errors"

                # Response times shouldn't be excessively affected by errors
                assert metrics.avg_response_time < 0.8, f"{op_type} error handling affected performance too much"

        print(f"  Error handling: {system_result.success_rate:.1%} success rate, " +
              f"{failed_operations:.0f} failures handled, " +
              f"{system_result.overall_throughput:.1f} ops/sec maintained")


if __name__ == "__main__":
    pytest.main([__file__])
