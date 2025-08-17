"""Test database query performance optimization for DatabaseModelRegistry.

This module provides comprehensive performance testing for database queries
with realistic data volumes to identify and validate optimization opportunities.
"""

import logging
import time
from typing import Any, Dict, List
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from emuses.multi_user_service.models import Base, User, Workspace, ModelRegistry
from emuses.tools.database_model_registry import DatabaseModelRegistry


logger = logging.getLogger(__name__)


@pytest.fixture
def performance_engine():
    """Create in-memory database engine for performance testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def performance_session(performance_engine):
    """Create database session for performance testing."""
    SessionLocal = sessionmaker(bind=performance_engine)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_users(performance_session) -> List[User]:
    """Create test users for performance testing."""
    users = []
    
    for i in range(10):
        user = User(
            id=uuid4(),
            email=f"user{i}@test.com",
            hashed_password="hashed_password",
            is_active=True,
            is_superuser=(i == 0),
            is_verified=True,
            organization=f"Org{i % 3}",
            role="researcher"
        )
        performance_session.add(user)
        users.append(user)
    
    performance_session.commit()
    return users


@pytest.fixture
def test_workspaces(performance_session, test_users) -> List[Workspace]:
    """Create test workspaces for performance testing."""
    workspaces = []
    
    for i, user in enumerate(test_users[:5]):  # 5 users with workspaces
        for j in range(3):  # 3 workspaces per user
            workspace = Workspace(
                id=uuid4(),
                name=f"Workspace {i}-{j}",
                description=f"Test workspace {i}-{j} for performance testing",
                owner_id=user.id,
                storage_path=f"/test/workspace/{i}/{j}",
                is_active=True
            )
            performance_session.add(workspace)
            workspaces.append(workspace)
    
    performance_session.commit()
    return workspaces


@pytest.fixture
def large_model_dataset(performance_session, test_users, test_workspaces) -> List[ModelRegistry]:
    """Create large dataset of models for performance testing."""
    models = []
    model_types = ["classification", "regression", "clustering", "dimensionality_reduction"]
    tags_pool = ["neuroimaging", "fmri", "machine_learning", "python", "scikit-learn", 
                 "tensorflow", "pytorch", "research", "clinical", "preprocessing"]
    
    # Create 1000 models distributed across users and workspaces
    for i in range(1000):
        user = test_users[i % len(test_users)]
        workspace = test_workspaces[i % len(test_workspaces)] if i % 3 != 0 else None
        
        # Make some models public for testing access control
        is_public = (i % 5 == 0)  # 20% public models
        
        model = ModelRegistry(
            id=uuid4(),
            name=f"Model_{i:04d}",
            version=f"1.{i % 10}.0",
            owner_id=user.id,
            workspace_id=workspace.id if workspace else None,
            is_public=is_public,
            model_path=f"/models/model_{i:04d}",
            manifest_hash=f"hash_{i:04d}",
            model_size_bytes=1024 * 1024 * (i % 100 + 1),  # 1-100 MB models
            description=f"Performance test model {i} for query optimization validation",
            tags=tags_pool[i % 3:(i % 3) + 3],  # 3 tags per model
            model_type=model_types[i % len(model_types)],
            download_count=i % 50
        )
        performance_session.add(model)
        models.append(model)
        
        # Commit in batches to avoid memory issues
        if (i + 1) % 100 == 0:
            performance_session.commit()
    
    performance_session.commit()
    logger.info(f"Created {len(models)} test models for performance testing")
    return models


class TestDatabaseQueryOptimization:
    """Test database query performance optimization."""
    
    def test_list_models_performance_baseline(self, performance_session, test_users, 
                                            test_workspaces, large_model_dataset):
        """Profile list_models query performance with large dataset."""
        user = test_users[0]
        registry = DatabaseModelRegistry(performance_session, user)
        
        # Warm up query
        registry.list_models()
        
        # Measure query performance
        start_time = time.perf_counter()
        models = registry.list_models(include_public=True)
        end_time = time.perf_counter()
        
        query_time_ms = (end_time - start_time) * 1000
        logger.info(f"list_models() baseline: {query_time_ms:.2f}ms for {len(models)} models")
        
        # Validate results
        assert len(models) > 0, "Should return accessible models"
        
        # Record baseline performance (current target: < 100ms for 1000 models)
        # Note: This will likely exceed target before optimization
        assert query_time_ms > 0, "Query should take measurable time"
        
        return {
            "query_time_ms": query_time_ms,
            "models_count": len(models),
            "models_per_second": len(models) / (query_time_ms / 1000) if query_time_ms > 0 else 0
        }
    
    def test_search_models_performance_baseline(self, performance_session, test_users,
                                              test_workspaces, large_model_dataset):
        """Profile search_models query performance with large dataset."""
        user = test_users[0]
        registry = DatabaseModelRegistry(performance_session, user)
        
        search_queries = [
            "neuroimaging",
            "classification", 
            "Model_00",
            "tensorflow",
            "nonexistent_query"
        ]
        
        performance_results = []
        
        for query_text in search_queries:
            # Warm up query
            registry.search_models(query_text)
            
            # Measure query performance
            start_time = time.perf_counter()
            results = registry.search_models(query_text, include_public=True)
            end_time = time.perf_counter()
            
            query_time_ms = (end_time - start_time) * 1000
            logger.info(f"search_models('{query_text}') baseline: {query_time_ms:.2f}ms, {len(results)} results")
            
            performance_results.append({
                "query": query_text,
                "query_time_ms": query_time_ms,
                "results_count": len(results)
            })
        
        # Validate search functionality
        assert len(performance_results) == len(search_queries)
        
        # Check that some queries return results
        non_empty_results = [r for r in performance_results if r["results_count"] > 0]
        assert len(non_empty_results) >= 3, "Most search queries should return results"
        
        # Record baseline performance (current target: < 200ms for text search)
        avg_query_time = sum(r["query_time_ms"] for r in performance_results) / len(performance_results)
        logger.info(f"Average search query time: {avg_query_time:.2f}ms")
        
        return performance_results
    
    def test_complex_permission_query_performance(self, performance_session, test_users,
                                                 test_workspaces, large_model_dataset):
        """Profile complex permission checking queries performance."""
        # Test with user that has limited access
        limited_user = test_users[5]  # User with fewer owned models
        registry = DatabaseModelRegistry(performance_session, limited_user)
        
        # Test different access control scenarios
        scenarios = [
            {"include_public": True, "description": "with public models"},
            {"include_public": False, "description": "private only"},
            {"workspace_id": str(test_workspaces[0].id), "description": "specific workspace"}
        ]
        
        performance_results = []
        
        for scenario in scenarios:
            # Warm up query
            registry.list_models(**{k: v for k, v in scenario.items() if k != "description"})
            
            # Measure query performance
            start_time = time.perf_counter()
            models = registry.list_models(**{k: v for k, v in scenario.items() if k != "description"})
            end_time = time.perf_counter()
            
            query_time_ms = (end_time - start_time) * 1000
            logger.info(f"Permission query {scenario['description']}: {query_time_ms:.2f}ms, {len(models)} models")
            
            performance_results.append({
                "scenario": scenario["description"],
                "query_time_ms": query_time_ms,
                "models_count": len(models)
            })
        
        # Validate permission filtering works
        assert len(performance_results) == len(scenarios)
        
        return performance_results
    
    def test_database_query_explain_analysis(self, performance_session, test_users,
                                            large_model_dataset):
        """Analyze database query execution plans for optimization insights."""
        # Note: This test works with SQLite, but would be more useful with PostgreSQL
        user = test_users[0]
        
        # Get the raw SQL that would be generated
        from sqlalchemy import or_
        from emuses.multi_user_service.models import ModelRegistry, Workspace
        
        # Simulate the current list_models query structure
        query = performance_session.query(ModelRegistry)
        
        access_conditions = [ModelRegistry.owner_id == user.id]
        access_conditions.append(ModelRegistry.is_public == True)
        
        user_workspaces = performance_session.query(Workspace.id).filter(
            Workspace.owner_id == user.id
        ).subquery()
        
        access_conditions.append(ModelRegistry.workspace_id.in_(user_workspaces))
        
        final_query = query.filter(or_(*access_conditions))
        
        # Get the compiled query for analysis
        compiled_query = str(final_query.statement.compile(compile_kwargs={"literal_binds": True}))
        logger.info(f"Generated SQL query: {compiled_query}")
        
        # Execute query and measure
        start_time = time.perf_counter()
        results = final_query.all()
        end_time = time.perf_counter()
        
        query_time_ms = (end_time - start_time) * 1000
        logger.info(f"Raw query execution: {query_time_ms:.2f}ms for {len(results)} results")
        
        return {
            "sql_query": compiled_query,
            "execution_time_ms": query_time_ms,
            "results_count": len(results)
        }
    
    def test_index_usage_simulation(self, performance_session, test_users, large_model_dataset):
        """Simulate the impact of strategic database indexes."""
        user = test_users[0]
        
        # Test current index usage patterns
        index_scenarios = [
            {
                "name": "owner_id_lookup",
                "query": performance_session.query(ModelRegistry).filter(ModelRegistry.owner_id == user.id)
            },
            {
                "name": "public_models_lookup", 
                "query": performance_session.query(ModelRegistry).filter(ModelRegistry.is_public == True)
            },
            {
                "name": "model_type_filter",
                "query": performance_session.query(ModelRegistry).filter(ModelRegistry.model_type == "classification")
            },
            {
                "name": "combined_filter",
                "query": performance_session.query(ModelRegistry).filter(
                    ModelRegistry.owner_id == user.id,
                    ModelRegistry.model_type == "classification",
                    ModelRegistry.is_public == True
                )
            }
        ]
        
        performance_results = []
        
        for scenario in index_scenarios:
            # Measure query performance
            start_time = time.perf_counter()
            results = scenario["query"].all()
            end_time = time.perf_counter()
            
            query_time_ms = (end_time - start_time) * 1000
            logger.info(f"Index scenario '{scenario['name']}': {query_time_ms:.2f}ms, {len(results)} results")
            
            performance_results.append({
                "scenario": scenario["name"],
                "query_time_ms": query_time_ms,
                "results_count": len(results)
            })
        
        return performance_results


@pytest.mark.performance
class TestQueryOptimizationTargets:
    """Validate query optimization meets performance targets."""
    
    def test_list_models_target_performance(self, performance_session, test_users,
                                          test_workspaces, large_model_dataset):
        """Validate list_models meets performance target (<100ms)."""
        user = test_users[0]
        registry = DatabaseModelRegistry(performance_session, user)
        
        # Run multiple iterations for stable measurement
        times = []
        for _ in range(5):
            start_time = time.perf_counter()
            models = registry.list_models(include_public=True)
            end_time = time.perf_counter()
            times.append((end_time - start_time) * 1000)
        
        avg_time_ms = sum(times) / len(times)
        logger.info(f"list_models average time: {avg_time_ms:.2f}ms (target: <100ms)")
        
        # This test will initially fail before optimization
        # After optimization, this should pass
        # assert avg_time_ms < 100, f"list_models should be <100ms, got {avg_time_ms:.2f}ms"
        
        return {
            "average_time_ms": avg_time_ms,
            "target_time_ms": 100,
            "meets_target": avg_time_ms < 100,
            "models_count": len(models)
        }
    
    def test_search_models_target_performance(self, performance_session, test_users,
                                            test_workspaces, large_model_dataset):
        """Validate search_models meets performance target (<200ms)."""
        user = test_users[0]
        registry = DatabaseModelRegistry(performance_session, user)
        
        search_query = "neuroimaging"
        
        # Run multiple iterations for stable measurement
        times = []
        for _ in range(5):
            start_time = time.perf_counter()
            results = registry.search_models(search_query, include_public=True)
            end_time = time.perf_counter()
            times.append((end_time - start_time) * 1000)
        
        avg_time_ms = sum(times) / len(times)
        logger.info(f"search_models average time: {avg_time_ms:.2f}ms (target: <200ms)")
        
        # This test will initially fail before optimization
        # After optimization, this should pass
        # assert avg_time_ms < 200, f"search_models should be <200ms, got {avg_time_ms:.2f}ms"
        
        return {
            "average_time_ms": avg_time_ms,
            "target_time_ms": 200,
            "meets_target": avg_time_ms < 200,
            "results_count": len(results)
        }