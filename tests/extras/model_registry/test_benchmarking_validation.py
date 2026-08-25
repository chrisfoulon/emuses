"""Comprehensive validation testing for ModelBenchmarkingSystem - Task 3.7.2c.

This module provides validation testing for the ModelBenchmarkingSystem including
production-like scenarios, cross-validation consistency, performance benchmarks,
accuracy verification, and integration testing.
"""

import uuid
import time
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from emuses.multi_user_service.models import Base, User, Workspace, ModelRegistry
from emuses.extras.model_benchmarking import (
    ModelBenchmarkingSystem,
    BenchmarkConfig,
    BenchmarkingError,
    BenchmarkResult,
    BenchmarkMetric,
    BenchmarkComparison,
    Leaderboard,
    BenchmarkStatus
)


class TestBenchmarkingSystemValidation:
    """Comprehensive validation tests for ModelBenchmarkingSystem."""

    @pytest.fixture
    def validation_db_engine(self):
        """Create in-memory database for validation testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def validation_db_session(self, validation_db_engine):
        """Create database session for validation testing."""
        Session = sessionmaker(bind=validation_db_engine)
        session = Session()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def test_models_dataset(self, validation_db_session):
        """Create realistic dataset of models for validation testing."""
        # Create test users
        users = []
        for i in range(5):
            user = User(
                id=uuid.uuid4(),
                email=f"benchmark_user_{i}@testorg.com",
                hashed_password="hashed",
                is_active=True,
                is_superuser=False,
                is_verified=True,
                organization=f"BenchmarkOrg_{i}",
                role="researcher"
            )
            users.append(user)
            validation_db_session.add(user)

        # Create test workspace
        workspace = Workspace(
            id=uuid.uuid4(),
            name="benchmark-validation-workspace",
            description="Workspace for benchmarking validation tests",
            owner_id=users[0].id,
            storage_path="/test/benchmark/path",
            is_active=True
        )
        validation_db_session.add(workspace)

        # Create diverse model types for comprehensive testing
        models = []
        model_types = ["sklearn", "tensorflow", "pytorch", "xgboost", "custom"]
        model_categories = ["classification", "regression", "clustering", "deep_learning"]

        for i in range(20):  # 20 test models with different characteristics
            model = ModelRegistry(
                id=uuid.uuid4(),
                name=f"benchmark-model-{i}",
                description=f"Validation test model {i} using {model_types[i % len(model_types)]} "
                            f"for {model_categories[i % len(model_categories)]} tasks",
                owner_id=users[i % len(users)].id,
                workspace_id=workspace.id,
                is_public=(i % 3 == 0),  # Mix of public and private models
                model_path=f"/test/benchmark/models/model_{i}",
                model_type=model_types[i % len(model_types)],
                version=f"1.{i % 10}.0",
                model_size_bytes=(i + 1) * 2048 * 1024,  # 2MB to 40MB
                manifest_hash=f"benchmark_hash_{i}",
                tags=["benchmark", "validation", model_types[i % len(model_types)],
                      model_categories[i % len(model_categories)], f"test_{i % 5}"],
                created_at=datetime.utcnow() - timedelta(days=i % 60)  # Models created over 60 days
            )
            models.append(model)
            validation_db_session.add(model)

        validation_db_session.commit()

        return {
            "users": users,
            "workspace": workspace,
            "models": models
        }

    @pytest.fixture
    def production_config(self):
        """Production-like benchmark configuration."""
        return BenchmarkConfig(
            enable_automated_benchmarking=True,
            benchmark_timeout=300,  # 5 minutes
            max_concurrent_benchmarks=3,
            standard_datasets=["iris", "wine", "digits", "boston", "breast_cancer"],
            evaluation_metrics=["accuracy", "precision", "recall", "f1_score", "auc", "mae", "rmse"],
            enable_leaderboards=True,
            min_benchmark_samples=50
        )

    def test_benchmarking_system_comprehensive_validation(self, validation_db_session, test_models_dataset, production_config):
        """Test comprehensive benchmarking system functionality with realistic data."""
        benchmarking_system = ModelBenchmarkingSystem(validation_db_session, production_config)

        # Validate system initialization
        assert benchmarking_system.db_session is not None
        assert benchmarking_system.config == production_config
        assert benchmarking_system.config.enable_automated_benchmarking is True

        # Test benchmarking multiple models with different configurations
        test_models = test_models_dataset["models"][:10]  # Use first 10 models
        test_user = test_models_dataset["users"][0]

        successful_benchmarks = []
        benchmark_results = []

        for i, model in enumerate(test_models):
            datasets_to_test = ["iris", "wine", "digits"]
            for dataset in datasets_to_test:
                benchmark_config = {
                    "dataset": dataset,
                    "metrics": ["accuracy", "precision", "recall", "f1_score"],
                    "cross_validation": True
                }

                try:
                    result = benchmarking_system.run_benchmark(model.id, test_user.id, benchmark_config)

                    # Validate benchmark result structure
                    assert result["status"] == "completed"
                    assert result["model_id"] == str(model.id)
                    assert result["dataset"] == dataset
                    assert "benchmark_id" in result
                    assert "metrics" in result
                    assert "execution_time" in result

                    # Validate metrics are within realistic ranges
                    metrics = result["metrics"]
                    for metric_name, value in metrics.items():
                        assert 0.0 <= value <= 1.0, f"Metric {metric_name} value {value} out of range [0,1]"
                        assert isinstance(value, float), f"Metric {metric_name} should be float, got {type(value)}"

                    # Validate cross-validation flag
                    assert result["cross_validation"] is True

                    successful_benchmarks.append(result)
                    benchmark_results.append(result)

                except BenchmarkingError as e:
                    # Acceptable errors for private models or authorization issues
                    if "not authorized" not in str(e):
                        raise  # Re-raise unexpected errors

        # Validate that we have successful benchmarks
        assert len(successful_benchmarks) > 0, "No successful benchmarks completed"
        print(f"Completed {len(successful_benchmarks)} successful benchmarks across {len(test_models)} models")

        # Validate benchmark execution times are reasonable
        execution_times = [result["execution_time"] for result in successful_benchmarks]
        avg_execution_time = sum(execution_times) / len(execution_times)
        assert avg_execution_time < 1.0, f"Average execution time {avg_execution_time:.3f}s too high"
        assert all(t >= 0 for t in execution_times), "All execution times should be non-negative"

    def test_benchmarking_accuracy_consistency(self, validation_db_session, test_models_dataset, production_config):
        """Test benchmarking accuracy and consistency across multiple runs."""
        benchmarking_system = ModelBenchmarkingSystem(validation_db_session, production_config)

        # Select a test model and user
        test_model = test_models_dataset["models"][0]
        test_user = test_models_dataset["users"][0]

        # Run the same benchmark multiple times to check consistency
        benchmark_config = {
            "dataset": "iris",
            "metrics": ["accuracy", "precision", "recall", "f1_score"],
            "cross_validation": False
        }

        results = []
        for _ in range(5):  # Run 5 times
            result = benchmarking_system.run_benchmark(test_model.id, test_user.id, benchmark_config)
            results.append(result)

        # Validate consistency of results (simulated benchmarks should be deterministic)
        first_metrics = results[0]["metrics"]
        for result in results[1:]:
            current_metrics = result["metrics"]
            for metric_name in first_metrics.keys():
                assert abs(first_metrics[metric_name] - current_metrics[metric_name]) < 0.001, \
                    f"Metric {metric_name} inconsistent: {first_metrics[metric_name]} vs {current_metrics[metric_name]}"

        print(f"Benchmark consistency validated across 5 runs for model {test_model.name}")

    def test_model_comparison_validation(self, validation_db_session, test_models_dataset, production_config):
        """Test model comparison functionality with comprehensive validation."""
        benchmarking_system = ModelBenchmarkingSystem(validation_db_session, production_config)

        # Select multiple models for comparison
        test_models = test_models_dataset["models"][:5]
        model_ids = [model.id for model in test_models]

        # Test comparison across different datasets
        datasets = ["iris", "wine", "digits"]
        metrics = ["accuracy", "f1_score", "precision"]

        for dataset in datasets:
            comparison_result = benchmarking_system.compare_models(model_ids, dataset=dataset, metrics=metrics)

            # Validate comparison structure
            assert comparison_result["dataset"] == dataset
            assert comparison_result["metrics"] == metrics
            assert len(comparison_result["models"]) == len(model_ids)
            assert "winner" in comparison_result
            assert "comparison_date" in comparison_result

            # Validate each model in comparison has required metrics
            for model_data in comparison_result["models"]:
                assert "model_id" in model_data
                for metric in metrics:
                    assert metric in model_data
                    assert isinstance(model_data[metric], (int, float))
                    assert 0.0 <= model_data[metric] <= 1.0

            # Validate winner selection
            winner = comparison_result["winner"]
            assert "model_id" in winner
            assert winner["model_id"] in [str(model_id) for model_id in model_ids]

            # Winner should have the highest value for the primary metric
            primary_metric = metrics[0]
            winner_value = winner[primary_metric]
            all_values = [model_data[primary_metric] for model_data in comparison_result["models"]]
            assert winner_value >= max(all_values) - 0.001, "Winner should have highest or near-highest metric value"

            print(f"Model comparison validated for {dataset} dataset with {len(model_ids)} models")

    def test_leaderboard_generation_validation(self, validation_db_session, test_models_dataset, production_config):
        """Test leaderboard generation with comprehensive validation."""
        benchmarking_system = ModelBenchmarkingSystem(validation_db_session, production_config)

        # Test leaderboard for multiple datasets and metrics
        test_cases = [
            ("iris", "accuracy", 10),
            ("wine", "f1_score", 15),
            ("digits", "precision", 5),
            ("boston", "mae", 8)
        ]

        for dataset, metric, limit in test_cases:
            leaderboard = benchmarking_system.get_leaderboard(dataset=dataset, metric=metric, limit=limit)

            # Validate leaderboard structure
            assert leaderboard["dataset"] == dataset
            assert leaderboard["metric"] == metric
            assert "models" in leaderboard
            assert "total_models" in leaderboard
            assert "last_updated" in leaderboard

            # Validate models list
            models = leaderboard["models"]
            assert len(models) <= limit, f"Leaderboard should not exceed limit {limit}"
            assert leaderboard["total_models"] >= len(models), "Total models should be >= returned models"

            # Validate sorting (should be descending by default for most metrics)
            if len(models) > 1 and models:
                for i in range(len(models) - 1):
                    current_value = models[i].get(metric, 0)
                    next_value = models[i + 1].get(metric, 0)
                    assert current_value >= next_value, f"Leaderboard not properly sorted: {current_value} < {next_value}"

            # Validate timestamp parsing
            last_updated = datetime.fromisoformat(leaderboard["last_updated"])
            assert isinstance(last_updated, datetime), "last_updated should be parseable datetime"

            print(f"Leaderboard validation successful for {dataset}-{metric} (limit={limit})")

    def test_benchmark_configuration_validation(self, validation_db_session, test_models_dataset):
        """Test benchmarking system with various configuration scenarios."""
        test_model = test_models_dataset["models"][0]
        test_user = test_models_dataset["users"][0]

        # Test with disabled benchmarking
        disabled_config = BenchmarkConfig(enable_automated_benchmarking=False)
        disabled_system = ModelBenchmarkingSystem(validation_db_session, disabled_config)

        with pytest.raises(BenchmarkingError, match="Automated benchmarking is disabled"):
            disabled_system.run_benchmark(test_model.id, test_user.id, {"dataset": "iris"})

        # Test with disabled leaderboards
        no_leaderboard_config = BenchmarkConfig(enable_leaderboards=False)
        no_leaderboard_system = ModelBenchmarkingSystem(validation_db_session, no_leaderboard_config)

        with pytest.raises(BenchmarkingError, match="Leaderboards are disabled"):
            no_leaderboard_system.get_leaderboard("iris", "accuracy")

        # Test with custom metrics and datasets
        custom_config = BenchmarkConfig(
            standard_datasets=["custom_dataset_1", "custom_dataset_2"],
            evaluation_metrics=["custom_metric_1", "custom_metric_2", "accuracy"],
            benchmark_timeout=120,
            max_concurrent_benchmarks=1
        )
        custom_system = ModelBenchmarkingSystem(validation_db_session, custom_config)

        # Should work with custom configuration
        result = custom_system.run_benchmark(
            test_model.id, test_user.id,
            {"dataset": "custom_dataset_1", "metrics": ["custom_metric_1", "accuracy"]}
        )
        assert result["status"] == "completed"
        assert "custom_metric_1" in result["metrics"]

        print("Configuration validation completed successfully")

    def test_automated_scheduling_validation(self, validation_db_session, test_models_dataset, production_config):
        """Test automated benchmark scheduling functionality."""
        benchmarking_system = ModelBenchmarkingSystem(validation_db_session, production_config)

        test_model = test_models_dataset["models"][0]
        test_user = test_models_dataset["users"][0]

        # Test various scheduling configurations
        schedule_configs = [
            {
                "datasets": ["iris", "wine"],
                "frequency": "daily",
                "metrics": ["accuracy", "f1_score"]
            },
            {
                "datasets": ["digits"],
                "frequency": "weekly",
                "metrics": ["precision", "recall", "auc"]
            },
            {
                "frequency": "monthly",  # Should use default datasets and metrics
            }
        ]

        for i, schedule_config in enumerate(schedule_configs):
            result = benchmarking_system.schedule_automated_benchmark(
                test_model.id, test_user.id, schedule_config
            )

            # Validate scheduling response
            assert result["success"] is True
            assert result["model_id"] == str(test_model.id)
            assert result["user_id"] == str(test_user.id)
            assert "schedule_id" in result
            assert "next_run" in result
            assert "created_at" in result

            # Validate frequency
            expected_frequency = schedule_config.get("frequency", "weekly")
            assert result["frequency"] == expected_frequency

            # Validate datasets
            if "datasets" in schedule_config:
                assert result["datasets"] == schedule_config["datasets"]
            else:
                assert result["datasets"] == production_config.standard_datasets

            # Validate metrics
            if "metrics" in schedule_config:
                assert result["metrics"] == schedule_config["metrics"]
            else:
                assert result["metrics"] == production_config.evaluation_metrics

            # Validate timestamp parsing
            next_run = datetime.fromisoformat(result["next_run"])
            created_at = datetime.fromisoformat(result["created_at"])
            assert next_run > created_at, "Next run should be after creation time"

            print(f"Scheduling validation {i+1} completed successfully")

    def test_performance_benchmarks(self, validation_db_session, test_models_dataset, production_config):
        """Test performance characteristics of benchmarking operations."""
        benchmarking_system = ModelBenchmarkingSystem(validation_db_session, production_config)

        # Performance test: Single benchmark execution
        test_model = test_models_dataset["models"][0]
        test_user = test_models_dataset["users"][0]

        start_time = time.time()
        result = benchmarking_system.run_benchmark(
            test_model.id, test_user.id,
            {"dataset": "iris", "metrics": ["accuracy", "precision", "recall", "f1_score"]}
        )
        single_benchmark_time = time.time() - start_time

        # Single benchmark should complete quickly
        assert single_benchmark_time < 0.5, f"Single benchmark took {single_benchmark_time:.3f}s, too slow"
        assert result["execution_time"] < 0.1, f"Reported execution time {result['execution_time']:.3f}s too high"

        # Performance test: Batch benchmarking
        batch_models = test_models_dataset["models"][:5]

        start_time = time.time()
        batch_results = []

        for model in batch_models:
            try:
                result = benchmarking_system.run_benchmark(
                    model.id, test_user.id,
                    {"dataset": "iris", "metrics": ["accuracy", "f1_score"]}
                )
                batch_results.append(result)
            except BenchmarkingError:
                pass  # Skip authorization errors

        batch_time = time.time() - start_time

        # Batch benchmarking should scale reasonably
        if len(batch_results) > 0:
            avg_time_per_benchmark = batch_time / len(batch_results)
            assert avg_time_per_benchmark < 0.2, f"Average batch benchmark time {avg_time_per_benchmark:.3f}s too high"

        # Performance test: Model comparison
        model_ids = [model.id for model in test_models_dataset["models"][:5]]

        start_time = time.time()
        comparison = benchmarking_system.compare_models(model_ids, dataset="iris", metrics=["accuracy"])
        comparison_time = time.time() - start_time

        # Model comparison should be efficient
        assert comparison_time < 0.3, f"Model comparison took {comparison_time:.3f}s, too slow"
        assert len(comparison["models"]) <= len(model_ids)

        # Performance test: Leaderboard generation
        start_time = time.time()
        benchmarking_system.get_leaderboard("iris", "accuracy", limit=10)
        leaderboard_time = time.time() - start_time

        # Leaderboard generation should be efficient
        assert leaderboard_time < 0.2, f"Leaderboard generation took {leaderboard_time:.3f}s, too slow"

        print(f"Performance benchmarks completed: single={single_benchmark_time*1000:.1f}ms, "
              f"comparison={comparison_time*1000:.1f}ms, leaderboard={leaderboard_time*1000:.1f}ms")

    def test_edge_cases_and_error_handling(self, validation_db_session, test_models_dataset, production_config):
        """Test edge cases and error handling in benchmarking system."""
        benchmarking_system = ModelBenchmarkingSystem(validation_db_session, production_config)

        test_user = test_models_dataset["users"][0]

        # Test with non-existent model
        fake_model_id = uuid.uuid4()
        with pytest.raises(BenchmarkingError, match="Model not found"):
            benchmarking_system.run_benchmark(
                fake_model_id, test_user.id,
                {"dataset": "iris", "metrics": ["accuracy"]}
            )

        # Test with invalid dataset
        test_model = test_models_dataset["models"][0]
        result = benchmarking_system.run_benchmark(
            test_model.id, test_user.id,
            {"dataset": "nonexistent_dataset", "metrics": ["accuracy"]}
        )
        # Should still work (system handles unknown datasets gracefully)
        assert result["status"] == "completed"

        # Test with empty metrics list - system should use the provided empty list
        result = benchmarking_system.run_benchmark(
            test_model.id, test_user.id,
            {"dataset": "iris", "metrics": []}
        )
        # System uses exactly what was provided (empty list means no metrics computed)
        assert result["metrics"] == {}

        # Test with no metrics key - should use default metrics
        result = benchmarking_system.run_benchmark(
            test_model.id, test_user.id,
            {"dataset": "iris"}  # No metrics key
        )
        # Should use default metrics from config
        expected_default_metrics = production_config.evaluation_metrics
        assert len(result["metrics"]) >= len(expected_default_metrics)

        # Test comparison with single model
        comparison = benchmarking_system.compare_models([test_model.id], dataset="iris")
        assert len(comparison["models"]) == 1
        assert comparison["winner"]["model_id"] == str(test_model.id)

        # Test comparison with empty model list
        comparison = benchmarking_system.compare_models([], dataset="iris")
        assert len(comparison["models"]) == 0
        assert comparison["winner"]["model_id"] is None

        # Test leaderboard with very small limit
        leaderboard = benchmarking_system.get_leaderboard("iris", "accuracy", limit=1)
        assert len(leaderboard["models"]) <= 1

        print("Edge cases and error handling validation completed")


class TestBenchmarkDataStructureValidation:
    """Test validation for benchmark data structures."""

    def test_benchmark_result_comprehensive_validation(self):
        """Test comprehensive validation of BenchmarkResult structure."""
        # Valid benchmark result
        valid_result = BenchmarkResult(
            benchmark_id=uuid.uuid4(),
            model_id=uuid.uuid4(),
            dataset="validation_dataset",
            metrics={"accuracy": 0.95, "precision": 0.92, "recall": 0.89, "f1_score": 0.905},
            execution_time=15.7,
            status=BenchmarkStatus.COMPLETED.value
        )

        assert valid_result.dataset == "validation_dataset"
        assert len(valid_result.metrics) == 4
        assert valid_result.execution_time == 15.7
        assert valid_result.status == BenchmarkStatus.COMPLETED.value
        assert valid_result.error_message is None

        # Test various invalid scenarios
        invalid_cases = [
            # Empty dataset
            {"dataset": "", "execution_time": 10, "status": BenchmarkStatus.COMPLETED.value},
            # Whitespace-only dataset
            {"dataset": "   ", "execution_time": 10, "status": BenchmarkStatus.COMPLETED.value},
            # Negative execution time
            {"dataset": "test", "execution_time": -5.0, "status": BenchmarkStatus.COMPLETED.value},
            # Invalid status
            {"dataset": "test", "execution_time": 10, "status": "invalid_status"}
        ]

        for case in invalid_cases:
            with pytest.raises(ValueError):
                BenchmarkResult(
                    benchmark_id=uuid.uuid4(),
                    model_id=uuid.uuid4(),
                    dataset=case["dataset"],
                    metrics={},
                    execution_time=case["execution_time"],
                    status=case["status"]
                )

        # Test with error message
        failed_result = BenchmarkResult(
            benchmark_id=uuid.uuid4(),
            model_id=uuid.uuid4(),
            dataset="test_dataset",
            metrics={},
            execution_time=0.0,
            status=BenchmarkStatus.FAILED.value,
            error_message="Benchmark execution failed due to timeout"
        )

        assert failed_result.status == BenchmarkStatus.FAILED.value
        assert "timeout" in failed_result.error_message

    def test_benchmark_metric_comparison_validation(self):
        """Test comprehensive validation of BenchmarkMetric comparison logic."""
        # Higher-is-better metrics
        accuracy1 = BenchmarkMetric("accuracy", 0.95, higher_is_better=True, description="Model accuracy")
        accuracy2 = BenchmarkMetric("accuracy", 0.88, higher_is_better=True, description="Model accuracy")

        assert accuracy1.is_better_than(accuracy2) is True
        assert accuracy2.is_better_than(accuracy1) is False

        # Lower-is-better metrics
        error1 = BenchmarkMetric("error_rate", 0.05, higher_is_better=False, description="Model error rate")
        error2 = BenchmarkMetric("error_rate", 0.12, higher_is_better=False, description="Model error rate")

        assert error1.is_better_than(error2) is True
        assert error2.is_better_than(error1) is False

        # Equal values
        equal1 = BenchmarkMetric("f1_score", 0.85, higher_is_better=True)
        equal2 = BenchmarkMetric("f1_score", 0.85, higher_is_better=True)

        assert equal1.is_better_than(equal2) is False
        assert equal2.is_better_than(equal1) is False

        # Different metric names should raise error
        accuracy = BenchmarkMetric("accuracy", 0.95, higher_is_better=True)
        precision = BenchmarkMetric("precision", 0.90, higher_is_better=True)

        with pytest.raises(ValueError, match="Cannot compare different metrics"):
            accuracy.is_better_than(precision)

    def test_benchmark_comparison_comprehensive_validation(self):
        """Test comprehensive validation of BenchmarkComparison functionality."""
        model_ids = [uuid.uuid4() for _ in range(5)]

        # Create comprehensive metric results
        metric_results = {}
        for i, model_id in enumerate(model_ids):
            metric_results[str(model_id)] = {
                "accuracy": 0.80 + (i * 0.03),  # 0.80, 0.83, 0.86, 0.89, 0.92
                "precision": 0.75 + (i * 0.04),  # 0.75, 0.79, 0.83, 0.87, 0.91
                "recall": 0.78 + (i * 0.02),  # 0.78, 0.80, 0.82, 0.84, 0.86
                "f1_score": 0.76 + (i * 0.025)  # Calculated approximately
            }

        comparison = BenchmarkComparison(
            model_ids=model_ids,
            dataset="comprehensive_validation",
            metric_results=metric_results
        )

        # Test winner finding for different metrics
        accuracy_winner = comparison.find_winner("accuracy")
        assert accuracy_winner["model_id"] == str(model_ids[4])  # Last model has highest accuracy
        assert accuracy_winner["accuracy"] == 0.92

        precision_winner = comparison.find_winner("precision")
        assert precision_winner["model_id"] == str(model_ids[4])  # Last model has highest precision
        assert precision_winner["precision"] == 0.91

        # Test with metric that doesn't exist for all models
        partial_results = {
            str(model_ids[0]): {"special_metric": 0.5},
            str(model_ids[2]): {"special_metric": 0.8},
            str(model_ids[4]): {"special_metric": 0.3}
        }

        partial_comparison = BenchmarkComparison(
            model_ids=model_ids,
            dataset="partial_test",
            metric_results=partial_results
        )

        special_winner = partial_comparison.find_winner("special_metric")
        assert special_winner["model_id"] == str(model_ids[2])
        assert special_winner["special_metric"] == 0.8

        # Test with nonexistent metric
        empty_winner = comparison.find_winner("nonexistent_metric")
        assert empty_winner["model_id"] is None

    def test_leaderboard_comprehensive_validation(self):
        """Test comprehensive validation of Leaderboard functionality."""
        # Create realistic leaderboard data
        models = [
            {"id": str(uuid.uuid4()), "name": "TopModel", "accuracy": 0.98, "f1_score": 0.96, "created_at": "2023-01-15"},
            {"id": str(uuid.uuid4()), "name": "GoodModel", "accuracy": 0.94, "f1_score": 0.91, "created_at": "2023-02-10"},
            {"id": str(uuid.uuid4()), "name": "OkayModel", "accuracy": 0.89, "f1_score": 0.87, "created_at": "2023-03-05"},
            {"id": str(uuid.uuid4()), "name": "WeakModel", "accuracy": 0.76, "f1_score": 0.74, "created_at": "2023-04-01"},
            {"id": str(uuid.uuid4()), "name": "PoorModel", "accuracy": 0.65, "f1_score": 0.62, "created_at": "2023-04-15"}
        ]

        leaderboard = Leaderboard(
            dataset="comprehensive_validation",
            metric="accuracy",
            models=models,
            last_updated=datetime.utcnow()
        )

        # Test descending sort (default)
        sorted_desc = leaderboard.get_sorted_models(descending=True)
        assert len(sorted_desc) == 5
        assert sorted_desc[0]["accuracy"] == 0.98  # TopModel first
        assert sorted_desc[1]["accuracy"] == 0.94  # GoodModel second
        assert sorted_desc[-1]["accuracy"] == 0.65  # PoorModel last

        # Verify complete descending order
        for i in range(len(sorted_desc) - 1):
            current = sorted_desc[i]["accuracy"]
            next_val = sorted_desc[i + 1]["accuracy"]
            assert current >= next_val, f"Descending order violated: {current} < {next_val}"

        # Test ascending sort
        sorted_asc = leaderboard.get_sorted_models(descending=False)
        assert sorted_asc[0]["accuracy"] == 0.65  # PoorModel first in ascending
        assert sorted_asc[-1]["accuracy"] == 0.98  # TopModel last in ascending

        # Verify complete ascending order
        for i in range(len(sorted_asc) - 1):
            current = sorted_asc[i]["accuracy"]
            next_val = sorted_asc[i + 1]["accuracy"]
            assert current <= next_val, f"Ascending order violated: {current} > {next_val}"

        # Test with different metric
        f1_leaderboard = Leaderboard(
            dataset="f1_validation",
            metric="f1_score",
            models=models
        )

        f1_sorted = f1_leaderboard.get_sorted_models(descending=True)
        assert f1_sorted[0]["f1_score"] == 0.96
        assert f1_sorted[-1]["f1_score"] == 0.62

        # Test with models missing the target metric
        incomplete_models = [
            {"id": str(uuid.uuid4()), "name": "CompleteModel", "accuracy": 0.90},
            {"id": str(uuid.uuid4()), "name": "IncompleteModel"},  # Missing accuracy
            {"id": str(uuid.uuid4()), "name": "ZeroModel", "accuracy": 0.0}
        ]

        incomplete_leaderboard = Leaderboard(
            dataset="incomplete_test",
            metric="accuracy",
            models=incomplete_models
        )

        incomplete_sorted = incomplete_leaderboard.get_sorted_models(descending=True)
        assert incomplete_sorted[0]["accuracy"] == 0.90
        # Models without the metric are sorted by default value (0)
        remaining_models = incomplete_sorted[1:]
        for model in remaining_models:
            accuracy = model.get("accuracy", 0)
            assert accuracy == 0 or accuracy == 0.0  # Missing or zero accuracy


if __name__ == "__main__":
    pytest.main([__file__])
