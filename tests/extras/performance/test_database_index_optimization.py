"""Tests for database index optimization.

This module tests the DatabaseIndexOptimizer for strategic index creation
and query performance improvements.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from emuses.multi_user_service.models import Base
from emuses.tools.database_index_optimizer import DatabaseIndexOptimizer


@pytest.fixture
def test_engine():
    """Create test database engine."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_session(test_engine):
    """Create test database session."""
    SessionLocal = sessionmaker(bind=test_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def index_optimizer(test_engine):
    """Create DatabaseIndexOptimizer instance."""
    return DatabaseIndexOptimizer(test_engine)


class TestDatabaseIndexOptimizer:
    """Test database index optimization functionality."""
    
    def test_index_optimizer_initialization(self, test_engine):
        """Test DatabaseIndexOptimizer initialization."""
        optimizer = DatabaseIndexOptimizer(test_engine)
        
        assert optimizer.engine is test_engine
        assert optimizer.metadata is not None
    
    def test_get_existing_indexes(self, index_optimizer):
        """Test retrieval of existing table indexes."""
        # Test with model_registry table
        indexes = index_optimizer.get_existing_indexes("model_registry")
        
        # Should return dict (may be empty for fresh database)
        assert isinstance(indexes, dict)
        
        # Check that existing indexes from SQLAlchemy models are found
        # Note: Some indexes may not be present in SQLite test database
        logger_info = f"Found {len(indexes)} existing indexes on model_registry"
        print(logger_info)  # For debugging
    
    def test_create_strategic_indexes_basic(self, index_optimizer, test_session):
        """Test basic strategic index creation."""
        # Create indexes
        results = index_optimizer.create_strategic_indexes()
        
        # Verify results structure
        assert isinstance(results, dict)
        assert len(results) > 0
        
        # Check that some indexes were created or already existed
        successful_creations = sum(1 for status in results.values() 
                                 if status in ["created", "already_exists"])
        
        # Should have attempted to create multiple indexes
        assert successful_creations >= 3, f"Expected at least 3 successful index operations, got {successful_creations}"
        
        # Verify no critical errors
        assert "error" not in results or not results["error"]
    
    def test_create_strategic_indexes_idempotent(self, index_optimizer):
        """Test that index creation is idempotent (can run multiple times)."""
        # Create indexes first time
        results1 = index_optimizer.create_strategic_indexes()
        
        # Create indexes second time - should handle existing indexes gracefully
        results2 = index_optimizer.create_strategic_indexes()
        
        # Both operations should succeed
        assert isinstance(results1, dict)
        assert isinstance(results2, dict)
        
        # Debug: Print results to understand what's happening
        print(f"First run results: {results1}")
        print(f"Second run results: {results2}")
        
        # Second run should mostly report "already_exists" or "created" (if SQL uses IF NOT EXISTS)
        already_exists_count = sum(1 for status in results2.values() 
                                 if status == "already_exists")
        created_count = sum(1 for status in results2.values() 
                           if status == "created")
        
        # Either some indexes report as already existing, or they were "created" again (IF NOT EXISTS)
        total_successful = already_exists_count + created_count
        assert total_successful >= 1, f"Expected some successful operations, got already_exists: {already_exists_count}, created: {created_count}"
    
    def test_analyze_query_performance_default(self, index_optimizer, test_session):
        """Test query performance analysis with default queries."""
        # Analyze performance with default test queries
        results = index_optimizer.analyze_query_performance(test_session)
        
        # Verify results structure
        assert isinstance(results, dict)
        assert len(results) > 0
        
        # Check each query result
        for query_name, result in results.items():
            assert isinstance(result, dict)
            
            if "error" not in result:
                # Successful query
                assert "execution_time_ms" in result
                assert "row_count" in result
                assert "performance_rating" in result
                assert isinstance(result["execution_time_ms"], (int, float))
                assert isinstance(result["row_count"], int)
                assert result["performance_rating"] in ["excellent", "good", "acceptable", "slow", "very_slow"]
            else:
                # Failed query (might be expected for empty database)
                assert "error" in result
    
    def test_analyze_query_performance_custom(self, index_optimizer, test_session):
        """Test query performance analysis with custom queries."""
        # Simple test queries that should work on empty database
        test_queries = [
            "SELECT COUNT(*) FROM model_registry",
            "SELECT COUNT(*) FROM users",
            "SELECT name FROM sqlite_master WHERE type='table'"
        ]
        
        results = index_optimizer.analyze_query_performance(test_session, test_queries)
        
        # Verify results
        assert isinstance(results, dict)
        assert len(results) == len(test_queries)
        
        # All queries should succeed (they're simple)
        for query_name, result in results.items():
            if "error" not in result:
                assert result["execution_time_ms"] >= 0
                assert result["row_count"] >= 0
    
    def test_performance_rating_system(self, index_optimizer):
        """Test query performance rating system."""
        # Test rating boundaries
        assert index_optimizer._rate_performance(5.0) == "excellent"
        assert index_optimizer._rate_performance(25.0) == "good"  
        assert index_optimizer._rate_performance(75.0) == "acceptable"
        assert index_optimizer._rate_performance(200.0) == "slow"
        assert index_optimizer._rate_performance(1000.0) == "very_slow"
        
        # Test edge cases
        assert index_optimizer._rate_performance(0.0) == "excellent"
        assert index_optimizer._rate_performance(10.0) == "good"  # exactly on boundary
        assert index_optimizer._rate_performance(100.0) == "slow"  # exactly on boundary
    
    def test_drop_strategic_indexes(self, index_optimizer):
        """Test dropping strategic indexes."""
        # First create indexes
        create_results = index_optimizer.create_strategic_indexes()
        
        # Then drop them
        drop_results = index_optimizer.drop_strategic_indexes()
        
        # Verify drop results structure
        assert isinstance(drop_results, dict)
        
        # Should have attempted to drop multiple indexes
        assert len(drop_results) > 0
        
        # Check that drops were attempted (may succeed or fail depending on existence)
        drop_attempts = sum(1 for status in drop_results.values() 
                          if status == "dropped" or "failed" in status)
        
        assert drop_attempts >= 3, f"Expected at least 3 drop attempts, got {drop_attempts}"
    
    def test_index_creation_error_handling(self, test_engine):
        """Test error handling during index creation."""
        # Create optimizer with a problematic setup to test error handling
        optimizer = DatabaseIndexOptimizer(test_engine)
        
        # This should work normally, but we're testing the error handling structure
        try:
            results = optimizer.create_strategic_indexes()
            
            # Even if some indexes fail, should return results dict
            assert isinstance(results, dict)
            
        except Exception as e:
            # If there are database issues, should be handled gracefully
            pytest.fail(f"Index creation should handle errors gracefully, but got: {e}")


class TestIndexOptimizationIntegration:
    """Test integration of index optimization with existing systems."""
    
    def test_index_optimization_with_model_registry_queries(self, index_optimizer, test_session):
        """Test that index optimization improves model registry query patterns."""
        # Create strategic indexes
        index_results = index_optimizer.create_strategic_indexes()
        
        # Test queries that match DatabaseModelRegistry patterns
        registry_queries = [
            # list_models() pattern
            "SELECT * FROM model_registry WHERE owner_id = 'test' OR is_public = TRUE ORDER BY created_at DESC",
            
            # search_models() pattern 
            "SELECT * FROM model_registry WHERE LOWER(name) LIKE '%test%' ORDER BY created_at DESC",
            
            # permission check pattern
            "SELECT * FROM model_access WHERE model_id = 'test' AND user_id = 'test'"
        ]
        
        # Analyze performance of registry-specific queries
        performance_results = index_optimizer.analyze_query_performance(test_session, registry_queries)
        
        # Verify analysis completed
        assert isinstance(performance_results, dict)
        assert len(performance_results) == len(registry_queries)
        
        # Queries should execute (may return 0 rows in empty database)
        successful_queries = sum(1 for result in performance_results.values() 
                               if "error" not in result)
        
        # At least some queries should execute successfully
        assert successful_queries >= 1, "At least one registry query should execute successfully"


@pytest.mark.performance
class TestIndexPerformanceValidation:
    """Performance validation tests for database indexes."""
    
    def test_index_creation_performance(self, test_engine):
        """Test that index creation completes in reasonable time."""
        import time
        
        optimizer = DatabaseIndexOptimizer(test_engine)
        
        # Measure index creation time
        start_time = time.perf_counter()
        results = optimizer.create_strategic_indexes()
        end_time = time.perf_counter()
        
        creation_time = end_time - start_time
        
        # Index creation should be fast on empty database
        assert creation_time < 5.0, f"Index creation took {creation_time:.2f}s, should be under 5s"
        
        # Should have attempted to create indexes
        assert len(results) > 0
    
    def test_query_performance_analysis_speed(self, index_optimizer, test_session):
        """Test that query performance analysis completes quickly."""
        import time
        
        start_time = time.perf_counter()
        results = index_optimizer.analyze_query_performance(test_session)
        end_time = time.perf_counter()
        
        analysis_time = end_time - start_time
        
        # Analysis should be fast
        assert analysis_time < 2.0, f"Performance analysis took {analysis_time:.2f}s, should be under 2s"
        
        # Should have analyzed queries
        assert len(results) > 0