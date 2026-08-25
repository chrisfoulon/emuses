"""Tests for model benchmarking system."""
import pytest
import uuid
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from sqlalchemy.orm import Session

from emuses.extras.model_benchmarking import (
    ModelBenchmarkingSystem,
    BenchmarkConfig,
    BenchmarkingError,
    BenchmarkResult,
    BenchmarkMetric,
    BenchmarkComparison,
    Leaderboard
)


class TestModelBenchmarkingSystem:
    """Tests for ModelBenchmarkingSystem class."""
    
    @pytest.fixture
    def db_session(self):
        """Mock database session for testing."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def benchmark_config(self):
        """Create BenchmarkConfig for testing."""
        return BenchmarkConfig(
            enable_automated_benchmarking=True,
            benchmark_timeout=300,
            max_concurrent_benchmarks=3,
            standard_datasets=["iris", "wine", "digits"],
            evaluation_metrics=["accuracy", "precision", "recall", "f1_score"],
            enable_leaderboards=True
        )
    
    @pytest.fixture
    def benchmarking_system(self, db_session, benchmark_config):
        """Create ModelBenchmarkingSystem instance."""
        return ModelBenchmarkingSystem(db_session, benchmark_config)
    
    def test_benchmarking_system_initialization(self, benchmarking_system):
        """Test ModelBenchmarkingSystem initialization."""
        assert benchmarking_system.db_session is not None
        assert benchmarking_system.config is not None
        assert isinstance(benchmarking_system.config, BenchmarkConfig)
    
    def test_run_benchmark_basic(self, benchmarking_system, db_session):
        """Test basic model benchmarking functionality."""
        model_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        # Mock model exists
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.name = "test_model"
        mock_model.model_type = "sklearn"
        db_session.query().filter().first.return_value = mock_model
        
        benchmark_config = {
            "dataset": "iris",
            "metrics": ["accuracy", "f1_score"],
            "cross_validation": True
        }
        
        result = benchmarking_system.run_benchmark(model_id, user_id, benchmark_config)
        
        assert result["status"] == "completed"
        assert result["model_id"] == str(model_id)
        assert "benchmark_id" in result
        assert "metrics" in result
        assert len(result["metrics"]) > 0
    
    def test_run_benchmark_unauthorized(self, benchmarking_system, db_session):
        """Test benchmarking model by unauthorized user."""
        model_id = uuid.uuid4()
        user_id = uuid.uuid4()
        wrong_user_id = uuid.uuid4()
        
        # Mock model owned by different user
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.owner_id = user_id  # Different from requester
        mock_model.is_public = False  # Make it private to trigger authorization check
        db_session.query().filter().first.return_value = mock_model
        
        benchmark_config = {"dataset": "iris"}
        
        with pytest.raises(BenchmarkingError):
            benchmarking_system.run_benchmark(model_id, wrong_user_id, benchmark_config)
    
    def test_get_benchmark_results(self, benchmarking_system, db_session):
        """Test retrieving benchmark results."""
        model_id = uuid.uuid4()
        
        # Mock benchmark results
        mock_results = [
            Mock(
                id=uuid.uuid4(),
                accuracy=0.95,
                f1_score=0.92,
                precision=0.94,
                recall=0.90,
                dataset="iris",
                created_at=datetime.utcnow()
            )
        ]
        db_session.query().filter().all.return_value = mock_results
        
        results = benchmarking_system.get_benchmark_results(model_id)
        
        assert len(results) == 1
        assert results[0]["accuracy"] == 0.95
        assert results[0]["dataset"] == "iris"
    
    def test_compare_models(self, benchmarking_system, db_session):
        """Test model comparison functionality."""
        model_ids = [uuid.uuid4(), uuid.uuid4()]
        
        # Mock benchmark results for comparison
        mock_results_1 = [Mock(accuracy=0.95, f1_score=0.92, dataset="iris")]
        mock_results_2 = [Mock(accuracy=0.88, f1_score=0.85, dataset="iris")]
        
        def mock_get_results(model_id, dataset=None):
            if model_id == model_ids[0]:
                return [{"accuracy": 0.95, "f1_score": 0.92}]
            return [{"accuracy": 0.88, "f1_score": 0.85}]
        
        benchmarking_system.get_benchmark_results = Mock(side_effect=mock_get_results)
        
        comparison = benchmarking_system.compare_models(model_ids, dataset="iris")
        
        assert len(comparison["models"]) == 2
        assert comparison["winner"]["model_id"] == str(model_ids[0])
        assert comparison["dataset"] == "iris"
    
    def test_get_leaderboard(self, benchmarking_system, db_session):
        """Test leaderboard generation."""
        # Mock leaderboard data as dictionaries (not Mock objects)
        mock_models = [
            {"id": str(uuid.uuid4()), "name": "Model A", "accuracy": 0.95},
            {"id": str(uuid.uuid4()), "name": "Model B", "accuracy": 0.88},
            {"id": str(uuid.uuid4()), "name": "Model C", "accuracy": 0.82}
        ]
        
        # Mock the benchmark results query
        benchmarking_system._get_leaderboard_data = Mock(return_value=mock_models)
        
        leaderboard = benchmarking_system.get_leaderboard(
            dataset="iris",
            metric="accuracy",
            limit=10
        )
        
        assert len(leaderboard["models"]) == 3
        assert leaderboard["models"][0]["accuracy"] == 0.95
        assert leaderboard["dataset"] == "iris"
        assert leaderboard["metric"] == "accuracy"
    
    def test_schedule_automated_benchmark(self, benchmarking_system):
        """Test scheduling automated benchmarking."""
        model_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        schedule_config = {
            "datasets": ["iris", "wine"],
            "frequency": "weekly",
            "metrics": ["accuracy", "f1_score"]
        }
        
        result = benchmarking_system.schedule_automated_benchmark(
            model_id, user_id, schedule_config
        )
        
        assert result["success"] is True
        assert result["model_id"] == str(model_id)
        assert "schedule_id" in result
        assert result["frequency"] == "weekly"


class TestBenchmarkConfig:
    """Tests for BenchmarkConfig class."""
    
    def test_default_config(self):
        """Test default benchmark configuration."""
        config = BenchmarkConfig()
        
        assert config.enable_automated_benchmarking is True
        assert config.benchmark_timeout == 600
        assert config.max_concurrent_benchmarks == 2
        assert "accuracy" in config.evaluation_metrics
        assert config.enable_leaderboards is True
    
    def test_custom_config(self):
        """Test custom benchmark configuration."""
        config = BenchmarkConfig(
            enable_automated_benchmarking=False,
            benchmark_timeout=300,
            max_concurrent_benchmarks=5,
            evaluation_metrics=["accuracy", "precision"],
            enable_leaderboards=False
        )
        
        assert config.enable_automated_benchmarking is False
        assert config.benchmark_timeout == 300
        assert config.max_concurrent_benchmarks == 5
        assert config.evaluation_metrics == ["accuracy", "precision"]
        assert config.enable_leaderboards is False


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""
    
    def test_benchmark_result_initialization(self):
        """Test BenchmarkResult initialization."""
        result = BenchmarkResult(
            benchmark_id=uuid.uuid4(),
            model_id=uuid.uuid4(),
            dataset="iris",
            metrics={"accuracy": 0.95, "f1_score": 0.92},
            execution_time=12.5,
            status="completed"
        )
        
        assert result.dataset == "iris"
        assert result.metrics["accuracy"] == 0.95
        assert result.execution_time == 12.5
        assert result.status == "completed"
    
    def test_benchmark_result_validation(self):
        """Test benchmark result validation."""
        with pytest.raises(ValueError):
            BenchmarkResult(
                benchmark_id=uuid.uuid4(),
                model_id=uuid.uuid4(),
                dataset="",  # Empty dataset should be invalid
                metrics={},
                execution_time=-1,  # Negative time should be invalid
                status="invalid_status"
            )


class TestBenchmarkMetric:
    """Tests for BenchmarkMetric dataclass."""
    
    def test_metric_initialization(self):
        """Test BenchmarkMetric initialization."""
        metric = BenchmarkMetric(
            name="accuracy",
            value=0.95,
            higher_is_better=True,
            description="Model accuracy percentage"
        )
        
        assert metric.name == "accuracy"
        assert metric.value == 0.95
        assert metric.higher_is_better is True
        assert metric.description == "Model accuracy percentage"
    
    def test_metric_comparison(self):
        """Test metric comparison functionality."""
        metric1 = BenchmarkMetric(name="accuracy", value=0.95, higher_is_better=True)
        metric2 = BenchmarkMetric(name="accuracy", value=0.88, higher_is_better=True)
        
        assert metric1.is_better_than(metric2) is True
        assert metric2.is_better_than(metric1) is False


class TestBenchmarkComparison:
    """Tests for BenchmarkComparison class."""
    
    def test_comparison_creation(self):
        """Test benchmark comparison creation."""
        model_ids = [uuid.uuid4(), uuid.uuid4()]
        results = {
            str(model_ids[0]): {"accuracy": 0.95, "f1_score": 0.92},
            str(model_ids[1]): {"accuracy": 0.88, "f1_score": 0.85}
        }
        
        comparison = BenchmarkComparison(
            model_ids=model_ids,
            dataset="iris",
            metric_results=results
        )
        
        assert len(comparison.model_ids) == 2
        assert comparison.dataset == "iris"
        assert comparison.metric_results[str(model_ids[0])]["accuracy"] == 0.95
    
    def test_find_winner(self):
        """Test finding the best performing model."""
        model_ids = [uuid.uuid4(), uuid.uuid4()]
        results = {
            str(model_ids[0]): {"accuracy": 0.95},
            str(model_ids[1]): {"accuracy": 0.88}
        }
        
        comparison = BenchmarkComparison(
            model_ids=model_ids,
            dataset="iris",
            metric_results=results
        )
        
        winner = comparison.find_winner("accuracy")
        assert winner["model_id"] == str(model_ids[0])
        assert winner["accuracy"] == 0.95


class TestLeaderboard:
    """Tests for Leaderboard class."""
    
    def test_leaderboard_creation(self):
        """Test leaderboard creation."""
        models = [
            {"id": uuid.uuid4(), "name": "Model A", "accuracy": 0.95},
            {"id": uuid.uuid4(), "name": "Model B", "accuracy": 0.88}
        ]
        
        leaderboard = Leaderboard(
            dataset="iris",
            metric="accuracy",
            models=models,
            last_updated=datetime.utcnow()
        )
        
        assert leaderboard.dataset == "iris"
        assert leaderboard.metric == "accuracy"
        assert len(leaderboard.models) == 2
        assert leaderboard.models[0]["accuracy"] == 0.95
    
    def test_leaderboard_sorting(self):
        """Test leaderboard model sorting."""
        models = [
            {"id": uuid.uuid4(), "name": "Model B", "accuracy": 0.88},
            {"id": uuid.uuid4(), "name": "Model A", "accuracy": 0.95},
            {"id": uuid.uuid4(), "name": "Model C", "accuracy": 0.82}
        ]
        
        leaderboard = Leaderboard(
            dataset="iris",
            metric="accuracy",
            models=models,
            last_updated=datetime.utcnow()
        )
        
        sorted_models = leaderboard.get_sorted_models(descending=True)
        assert sorted_models[0]["accuracy"] == 0.95  # Model A should be first
        assert sorted_models[1]["accuracy"] == 0.88  # Model B should be second
        assert sorted_models[2]["accuracy"] == 0.82  # Model C should be third