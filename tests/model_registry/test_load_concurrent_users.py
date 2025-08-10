"""Comprehensive load testing with concurrent users and operations - Task 3.7.3a.

This module provides comprehensive load testing for the model registry system
under realistic concurrent user scenarios, testing system behavior, performance
degradation, resource utilization, and stability under load.
"""

import asyncio
import concurrent.futures
import json
import random
import string
import tempfile
import threading
import time
import uuid
from collections import defaultdict, namedtuple
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emuses.multi_user_service.models import Base, User, Workspace, ModelRegistry
from emuses.tools.database_model_registry import DatabaseModelRegistry
from emuses.tools.model_permission_manager import ModelPermissionManager
from emuses.tools.model_analytics import ModelAnalytics
from emuses.tools.advanced_search import AdvancedModelSearch, SearchConfig
from emuses.tools.community_model_manager import CommunityModelManager


# Load test metrics tracking
LoadTestMetrics = namedtuple('LoadTestMetrics', [
    'operation_count', 'success_count', 'error_count', 
    'total_time', 'avg_response_time', 'min_response_time', 
    'max_response_time', 'concurrent_users', 'operations_per_second'
])

UserSession = namedtuple('UserSession', [
    'user_id', 'workspace_id', 'session_start', 'operations_completed',
    'errors_encountered', 'total_response_time'
])


class LoadTestRunner:
    """Orchestrates concurrent load testing scenarios."""
    
    def __init__(self, db_session, max_workers=50):
        """Initialize load test runner.
        
        Parameters
        ----------
        db_session : sqlalchemy.orm.Session
            Database session for testing.
        max_workers : int, default=50
            Maximum concurrent worker threads.
        """
        self.db_session = db_session
        self.max_workers = max_workers
        self.metrics = defaultdict(list)
        self.active_sessions = {}
        self.lock = threading.Lock()
        
    def record_operation(self, operation_type: str, response_time: float, 
                        success: bool, user_id: str):
        """Record operation metrics thread-safely.
        
        Parameters
        ----------
        operation_type : str
            Type of operation performed.
        response_time : float
            Response time in seconds.
        success : bool
            Whether operation succeeded.
        user_id : str
            User ID performing operation.
        """
        with self.lock:
            self.metrics[operation_type].append({
                'response_time': response_time,
                'success': success,
                'user_id': user_id,
                'timestamp': time.time()
            })
    
    def get_metrics_summary(self, operation_type: str) -> LoadTestMetrics:
        """Calculate comprehensive metrics summary.
        
        Parameters
        ----------
        operation_type : str
            Operation type to summarize.
            
        Returns
        -------
        LoadTestMetrics
            Comprehensive metrics summary.
        """
        operations = self.metrics[operation_type]
        if not operations:
            return LoadTestMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0)
        
        response_times = [op['response_time'] for op in operations]
        successes = [op for op in operations if op['success']]
        errors = [op for op in operations if not op['success']]
        
        # Calculate time window for ops/second
        if len(operations) > 1:
            time_window = max(op['timestamp'] for op in operations) - \
                         min(op['timestamp'] for op in operations)
            ops_per_second = len(operations) / max(time_window, 0.001)
        else:
            ops_per_second = 0
        
        unique_users = len(set(op['user_id'] for op in operations))
        
        return LoadTestMetrics(
            operation_count=len(operations),
            success_count=len(successes),
            error_count=len(errors),
            total_time=sum(response_times),
            avg_response_time=sum(response_times) / len(response_times),
            min_response_time=min(response_times),
            max_response_time=max(response_times),
            concurrent_users=unique_users,
            operations_per_second=ops_per_second
        )
    
    def create_user_session(self, user: User, workspace: Workspace) -> UserSession:
        """Create user session for tracking.
        
        Parameters
        ----------
        user : User
            User model instance.
        workspace : Workspace
            Workspace model instance.
            
        Returns
        -------
        UserSession
            User session tracking object.
        """
        session = UserSession(
            user_id=str(user.id),
            workspace_id=str(workspace.id),
            session_start=time.time(),
            operations_completed=0,
            errors_encountered=0,
            total_response_time=0.0
        )
        self.active_sessions[str(user.id)] = session
        return session


class TestConcurrentUserLoadTesting:
    """Comprehensive load testing with concurrent users and operations."""
    
    @pytest.fixture
    def load_db_engine(self):
        """Create in-memory database for load testing."""
        # Configure SQLite for thread safety in concurrent testing
        engine = create_engine(
            "sqlite:///:memory:",
            pool_pre_ping=True,
            poolclass=StaticPool,
            connect_args={
                'check_same_thread': False,
                'timeout': 20,
                'isolation_level': None
            },
            echo=False
        )
        Base.metadata.create_all(engine)
        return engine
    
    @pytest.fixture
    def load_db_session(self, load_db_engine):
        """Create database session for load testing."""
        Session = sessionmaker(bind=load_db_engine)
        session = Session()
        try:
            yield session
        finally:
            session.close()
    
    @pytest.fixture
    def load_test_runner(self, load_db_session):
        """Create load test runner."""
        return LoadTestRunner(load_db_session, max_workers=50)
    
    @pytest.fixture
    def concurrent_users_dataset(self, load_db_session):
        """Create dataset with multiple concurrent users for load testing."""
        users = []
        workspaces = []
        models = []
        
        # Create 25 users with different organizations and roles
        organizations = [f"LoadTestOrg_{i}" for i in range(5)]
        roles = ["researcher", "admin", "analyst", "developer", "manager"]
        
        for i in range(25):
            user = User(
                id=uuid.uuid4(),
                email=f"loadtest_user_{i}@{organizations[i % len(organizations)]}.com",
                hashed_password=f"hashed_password_{i}",
                is_active=True,
                is_superuser=(i % 10 == 0),  # Every 10th user is superuser
                is_verified=True,
                organization=organizations[i % len(organizations)],
                role=roles[i % len(roles)]
            )
            users.append(user)
            load_db_session.add(user)
        
        # Create workspaces for each user
        for i, user in enumerate(users):
            workspace = Workspace(
                id=uuid.uuid4(),
                name=f"loadtest-workspace-{i}",
                description=f"Load test workspace for user {i}",
                owner_id=user.id,
                storage_path=f"/test/load/{user.id}",
                is_active=True
            )
            workspaces.append(workspace)
            load_db_session.add(workspace)
        
        # Create diverse models for each workspace
        model_types = ["sklearn", "tensorflow", "pytorch", "xgboost", "lightgbm"]
        categories = ["classification", "regression", "clustering", "nlp", "cv"]
        
        for i in range(100):  # 4 models per user on average
            user_idx = i % len(users)
            workspace_idx = user_idx  # Each user has one workspace
            
            model = ModelRegistry(
                id=uuid.uuid4(),
                name=f"concurrent-load-model-{i:03d}",
                description=f"Load test model {i} for concurrent operations testing",
                owner_id=users[user_idx].id,
                workspace_id=workspaces[workspace_idx].id,
                is_public=(i % 3 == 0),  # 33% public models
                model_path=f"/test/load/models/model_{i:03d}",
                model_type=model_types[i % len(model_types)],
                version=f"1.{i % 10}.{i % 3}",
                model_size_bytes=(i + 1) * 512 * 1024,  # 512KB to 50MB
                manifest_hash=f"concurrent_load_hash_{i:03d}",
                tags=["load", "concurrent", model_types[i % len(model_types)],
                      categories[i % len(categories)], f"batch_{i // 10}"],
                created_at=datetime.utcnow() - timedelta(days=(i % 100))
            )
            models.append(model)
            load_db_session.add(model)
        
        load_db_session.commit()
        
        return {
            "users": users,
            "workspaces": workspaces, 
            "models": models
        }
    
    def simulate_user_operations(self, user: User, workspace: Workspace, 
                                models: List[ModelRegistry], runner: LoadTestRunner,
                                operations_per_user: int = 20) -> Dict:
        """Simulate realistic user operations under load.
        
        Parameters
        ----------
        user : User
            User performing operations.
        workspace : Workspace
            User's workspace.
        models : List[ModelRegistry]
            Available models for operations.
        runner : LoadTestRunner
            Load test metrics runner.
        operations_per_user : int, default=20
            Number of operations per user.
            
        Returns
        -------
        Dict
            User operation results summary.
        """
        session = runner.create_user_session(user, workspace)
        results = {
            'user_id': str(user.id),
            'operations': [],
            'total_time': 0,
            'success_count': 0,
            'error_count': 0
        }
        
        # For SQLite threading limitations, use process-isolated approach
        # Create database session with thread-safe configuration
        Session = sessionmaker(bind=runner.db_session.bind, expire_on_commit=False)
        user_db_session = Session()
        
        try:
            # Initialize user-specific components
            registry = DatabaseModelRegistry(user_db_session, user)
            permission_manager = ModelPermissionManager(user_db_session)
            analytics = ModelAnalytics(user_db_session)
            
            # Simulate realistic user behavior patterns
            operation_types = [
                ('list_models', 0.25),      # 25% - Most common operation
                ('get_model', 0.20),        # 20% - View model details
                ('search_models', 0.15),    # 15% - Search operations
                ('download_model', 0.12),   # 12% - Download models
                ('register_model', 0.08),   # 8% - Register new models
                ('update_model', 0.08),     # 8% - Update existing models
                ('check_permissions', 0.07),# 7% - Permission checks
                ('get_analytics', 0.05)     # 5% - Analytics queries
            ]
            
            for op_num in range(operations_per_user):
                # Select operation based on realistic probability distribution
                rand_val = random.random()
                cumulative_prob = 0
                selected_operation = 'list_models'  # fallback
                
                for op_type, prob in operation_types:
                    cumulative_prob += prob
                    if rand_val <= cumulative_prob:
                        selected_operation = op_type
                        break
                
                # Execute operation with timing
                start_time = time.time()
                success = True
                operation_result = None
                
                try:
                    if selected_operation == 'list_models':
                        operation_result = registry.list_models(include_public=True)
                        
                    elif selected_operation == 'get_model':
                        if models:
                            model = random.choice(models)
                            operation_result = registry.get_model(str(model.id))
                    
                    elif selected_operation == 'search_models':
                        search_terms = ['sklearn', 'tensorflow', 'classification', 
                                      'regression', 'model', 'test']
                        query = random.choice(search_terms)
                        operation_result = registry.search_models(query, max_results=10)
                    
                    elif selected_operation == 'download_model':
                        if models:
                            model = random.choice([m for m in models if m.is_public])
                            if model:
                                # Simulate download operation (without actual file I/O)
                                analytics.record_download(str(model.id), str(user.id), 
                                                       {"client": "load_test"})
                                operation_result = True
                    
                    elif selected_operation == 'register_model':
                        # Simulate registering a new model
                        new_model_data = {
                            "name": f"user_{user.id}_model_{op_num}",
                            "description": f"Load test model from user {user.id}",
                            "model_type": random.choice(["sklearn", "tensorflow", "pytorch"]),
                            "version": "1.0.0",
                            "tags": ["load_test", "concurrent"]
                        }
                        # Simulate model registration (metadata only)
                        operation_result = True
                    
                    elif selected_operation == 'update_model':
                        user_models = [m for m in models if m.owner_id == user.id]
                        if user_models:
                            model = random.choice(user_models)
                            # Simulate model update
                            operation_result = True
                    
                    elif selected_operation == 'check_permissions':
                        if models:
                            model = random.choice(models)
                            operation_result = permission_manager.check_access(
                                str(model.id), str(user.id), "read")
                    
                    elif selected_operation == 'get_analytics':
                        if models:
                            model = random.choice(models)
                            operation_result = analytics.get_model_stats(str(model.id), "7d")
                
                except Exception as e:
                    success = False
                    operation_result = str(e)
                
                end_time = time.time()
                response_time = end_time - start_time
                
                # Record metrics
                runner.record_operation(selected_operation, response_time, success, str(user.id))
                
                # Update user results
                results['operations'].append({
                    'operation': selected_operation,
                    'success': success,
                    'response_time': response_time,
                    'result_summary': str(type(operation_result).__name__) if success else operation_result
                })
                
                if success:
                    results['success_count'] += 1
                else:
                    results['error_count'] += 1
                
                results['total_time'] += response_time
                
                # Add small random delay to simulate realistic user behavior
                time.sleep(random.uniform(0.001, 0.01))  # 1-10ms thinking time
        
        finally:
            user_db_session.close()
        
        return results
    
    def test_concurrent_users_system_load(self, load_db_session, concurrent_users_dataset, load_test_runner):
        """Test system behavior under concurrent user load."""
        users = concurrent_users_dataset["users"]
        workspaces = concurrent_users_dataset["workspaces"]
        models = concurrent_users_dataset["models"]
        
        # Test with different concurrency levels
        concurrency_levels = [5, 10, 20, 25]  # Progressive load testing
        
        for concurrent_users in concurrency_levels:
            print(f"\\nTesting with {concurrent_users} concurrent users...")
            
            # Select subset of users for this test
            test_users = users[:concurrent_users]
            test_workspaces = workspaces[:concurrent_users]
            
            # Reset metrics for this test
            load_test_runner.metrics.clear()
            
            # Execute concurrent operations
            start_time = time.time()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
                # Submit user simulation tasks
                future_to_user = {
                    executor.submit(
                        self.simulate_user_operations,
                        user, test_workspaces[i], models, load_test_runner, 15
                    ): user for i, user in enumerate(test_users)
                }
                
                # Collect results
                user_results = []
                for future in concurrent.futures.as_completed(future_to_user):
                    user = future_to_user[future]
                    try:
                        result = future.result(timeout=30)  # 30 second timeout per user
                        user_results.append(result)
                    except concurrent.futures.TimeoutError:
                        print(f"User {user.id} timed out")
                        user_results.append({
                            'user_id': str(user.id),
                            'error': 'timeout',
                            'success_count': 0,
                            'error_count': 1
                        })
                    except Exception as exc:
                        print(f"User {user.id} generated exception: {exc}")
                        user_results.append({
                            'user_id': str(user.id),
                            'error': str(exc),
                            'success_count': 0,
                            'error_count': 1
                        })
            
            total_time = time.time() - start_time
            
            # Analyze results
            total_operations = sum(len(ur.get('operations', [])) for ur in user_results)
            total_successes = sum(ur.get('success_count', 0) for ur in user_results)
            total_errors = sum(ur.get('error_count', 0) for ur in user_results)
            
            success_rate = total_successes / max(total_operations, 1)
            throughput = total_operations / max(total_time, 0.001)
            
            # Performance assertions
            assert success_rate >= 0.95, f"Success rate too low with {concurrent_users} users: {success_rate:.2%}"
            assert total_time < 60, f"Total execution time too long with {concurrent_users} users: {total_time:.1f}s"
            assert throughput >= concurrent_users * 0.5, f"Throughput too low: {throughput:.1f} ops/sec"
            
            # Validate key operations performed well
            operation_metrics = {}
            for operation_type in ['list_models', 'get_model', 'search_models']:
                metrics = load_test_runner.get_metrics_summary(operation_type)
                operation_metrics[operation_type] = metrics
                
                if metrics.operation_count > 0:
                    # Performance thresholds
                    assert metrics.avg_response_time < 1.0, \
                        f"{operation_type} avg response time too high: {metrics.avg_response_time:.3f}s"
                    assert metrics.success_count / metrics.operation_count >= 0.98, \
                        f"{operation_type} success rate too low: {metrics.success_count}/{metrics.operation_count}"
            
            print(f"  Results: {total_operations} ops, {success_rate:.1%} success, " + \
                  f"{throughput:.1f} ops/sec, {total_time:.1f}s total")
    
    def test_mixed_workload_stress_testing(self, load_db_session, concurrent_users_dataset, load_test_runner):
        """Test system under mixed workload with different operation types."""
        users = concurrent_users_dataset["users"]
        workspaces = concurrent_users_dataset["workspaces"]
        models = concurrent_users_dataset["models"]
        
        # Define workload patterns
        workload_patterns = [
            ("read_heavy", {"list_models": 0.4, "get_model": 0.3, "search_models": 0.2, "get_analytics": 0.1}),
            ("write_heavy", {"register_model": 0.3, "update_model": 0.3, "download_model": 0.2, "list_models": 0.2}),
            ("mixed_balanced", {"list_models": 0.2, "get_model": 0.15, "search_models": 0.15, "register_model": 0.15,
                               "download_model": 0.15, "update_model": 0.1, "get_analytics": 0.1})
        ]
        
        for workload_name, operation_weights in workload_patterns:
            print(f"\\nTesting {workload_name} workload pattern...")
            
            # Reset metrics
            load_test_runner.metrics.clear()
            
            # Execute mixed workload with 15 users
            test_users = users[:15]
            test_workspaces = workspaces[:15]
            
            start_time = time.time()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                # Submit tasks with custom operation weights
                futures = []
                for i, user in enumerate(test_users):
                    future = executor.submit(
                        self._execute_weighted_operations,
                        user, test_workspaces[i], models, load_test_runner,
                        operation_weights, 25
                    )
                    futures.append(future)
                
                # Wait for completion
                results = []
                for future in concurrent.futures.as_completed(futures, timeout=45):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as exc:
                        results.append({'error': str(exc), 'success_count': 0, 'error_count': 1})
            
            total_time = time.time() - start_time
            
            # Analyze workload performance
            total_operations = sum(len(r.get('operations', [])) for r in results)
            total_successes = sum(r.get('success_count', 0) for r in results)
            success_rate = total_successes / max(total_operations, 1)
            
            # Workload-specific assertions
            if workload_name == "read_heavy":
                # Read operations should be fast
                read_ops = ['list_models', 'get_model', 'search_models']
                for op in read_ops:
                    metrics = load_test_runner.get_metrics_summary(op)
                    if metrics.operation_count > 0:
                        assert metrics.avg_response_time < 0.5, \
                            f"Read operation {op} too slow: {metrics.avg_response_time:.3f}s"
            
            elif workload_name == "write_heavy":
                # Write operations may be slower but should still complete
                write_ops = ['register_model', 'update_model', 'download_model']
                for op in write_ops:
                    metrics = load_test_runner.get_metrics_summary(op)
                    if metrics.operation_count > 0:
                        assert metrics.avg_response_time < 2.0, \
                            f"Write operation {op} too slow: {metrics.avg_response_time:.3f}s"
            
            # General performance requirements
            assert success_rate >= 0.93, f"{workload_name} success rate too low: {success_rate:.2%}"
            assert total_time < 50, f"{workload_name} total time too long: {total_time:.1f}s"
            
            print(f"  {workload_name}: {success_rate:.1%} success, {total_time:.1f}s")
    
    def _execute_weighted_operations(self, user: User, workspace: Workspace, 
                                   models: List[ModelRegistry], runner: LoadTestRunner,
                                   operation_weights: Dict[str, float], 
                                   num_operations: int) -> Dict:
        """Execute operations according to specified weights.
        
        Parameters
        ----------
        user : User
            User performing operations.
        workspace : Workspace
            User's workspace.
        models : List[ModelRegistry]
            Available models.
        runner : LoadTestRunner
            Metrics runner.
        operation_weights : Dict[str, float]
            Operation type weights.
        num_operations : int
            Number of operations to perform.
            
        Returns
        -------
        Dict
            Operation results.
        """
        # Create fresh database session with thread-safe configuration
        Session = sessionmaker(bind=runner.db_session.bind, expire_on_commit=False)
        user_db_session = Session()
        
        results = {
            'user_id': str(user.id),
            'operations': [],
            'success_count': 0,
            'error_count': 0
        }
        
        try:
            registry = DatabaseModelRegistry(user_db_session, user)
            analytics = ModelAnalytics(user_db_session)
            permission_manager = ModelPermissionManager(user_db_session)
            
            # Convert weights to operation selection
            operations = list(operation_weights.keys())
            weights = list(operation_weights.values())
            
            for _ in range(num_operations):
                # Select operation based on weights
                selected_op = random.choices(operations, weights=weights)[0]
                
                start_time = time.time()
                success = True
                
                try:
                    # Execute operation (similar to simulate_user_operations)
                    if selected_op == 'list_models':
                        result = registry.list_models(include_public=True)
                    elif selected_op == 'get_model' and models:
                        model = random.choice(models)
                        result = registry.get_model(str(model.id))
                    elif selected_op == 'search_models':
                        query = random.choice(['test', 'model', 'sklearn'])
                        result = registry.search_models(query)
                    elif selected_op == 'register_model':
                        # Simulate registration
                        result = True
                    elif selected_op == 'download_model' and models:
                        model = random.choice([m for m in models if m.is_public])
                        if model:
                            analytics.record_download(str(model.id), str(user.id), {})
                        result = True
                    elif selected_op == 'update_model':
                        # Simulate update
                        result = True
                    elif selected_op == 'get_analytics' and models:
                        model = random.choice(models)
                        result = analytics.get_model_stats(str(model.id))
                    else:
                        result = True
                        
                except Exception:
                    success = False
                    result = None
                
                response_time = time.time() - start_time
                runner.record_operation(selected_op, response_time, success, str(user.id))
                
                results['operations'].append({
                    'operation': selected_op,
                    'success': success,
                    'response_time': response_time
                })
                
                if success:
                    results['success_count'] += 1
                else:
                    results['error_count'] += 1
                
                # Small delay
                time.sleep(random.uniform(0.001, 0.005))
        
        finally:
            user_db_session.close()
        
        return results
    
    def test_database_connection_pooling_load(self, load_db_session, concurrent_users_dataset, load_test_runner):
        """Test database connection handling under concurrent load."""
        users = concurrent_users_dataset["users"]
        models = concurrent_users_dataset["models"]
        
        # Test database-intensive operations
        def database_intensive_operations(user_id: str, iterations: int) -> Dict:
            """Perform database-intensive operations.
            
            Parameters
            ----------
            user_id : str
                User identifier.
            iterations : int
                Number of iterations to perform.
                
            Returns
            -------
            Dict
                Operation results.
            """
            Session = sessionmaker(bind=load_test_runner.db_session.bind, expire_on_commit=False)
            session = Session()
            
            results = {'success_count': 0, 'error_count': 0, 'operations': []}
            
            try:
                for i in range(iterations):
                    start_time = time.time()
                    success = True
                    
                    try:
                        # Multiple database queries in succession
                        model_count = session.query(ModelRegistry).count()
                        public_models = session.query(ModelRegistry).filter(
                            ModelRegistry.is_public == True).limit(10).all()
                        user_models = session.query(ModelRegistry).filter(
                            ModelRegistry.owner_id == user_id).limit(5).all()
                        
                        # Simulate some processing
                        time.sleep(0.001)
                        
                    except Exception as e:
                        success = False
                        print(f"Database error for user {user_id}: {e}")
                    
                    response_time = time.time() - start_time
                    load_test_runner.record_operation('database_query', response_time, success, user_id)
                    
                    results['operations'].append({
                        'iteration': i,
                        'success': success,
                        'response_time': response_time
                    })
                    
                    if success:
                        results['success_count'] += 1
                    else:
                        results['error_count'] += 1
            
            finally:
                session.close()
            
            return results
        
        # Test with 20 concurrent users doing database operations
        test_users = users[:20]
        load_test_runner.metrics.clear()
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(database_intensive_operations, str(user.id), 30)
                for user in test_users
            ]
            
            results = []
            for future in concurrent.futures.as_completed(futures, timeout=60):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    results.append({'error': str(exc), 'success_count': 0, 'error_count': 1})
        
        total_time = time.time() - start_time
        
        # Analyze database performance
        db_metrics = load_test_runner.get_metrics_summary('database_query')
        
        total_db_operations = sum(len(r.get('operations', [])) for r in results)
        total_successes = sum(r.get('success_count', 0) for r in results)
        success_rate = total_successes / max(total_db_operations, 1)
        
        # Database performance assertions
        assert success_rate >= 0.98, f"Database success rate too low: {success_rate:.2%}"
        assert db_metrics.avg_response_time < 0.1, \
            f"Average database response time too high: {db_metrics.avg_response_time:.3f}s"
        assert total_time < 45, f"Database load test took too long: {total_time:.1f}s"
        
        print(f"Database load test: {total_db_operations} queries, " + \
              f"{success_rate:.1%} success, avg {db_metrics.avg_response_time*1000:.1f}ms")
    
    def test_memory_usage_under_load(self, load_db_session, concurrent_users_dataset, load_test_runner):
        """Test memory usage patterns under concurrent load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        users = concurrent_users_dataset["users"]
        models = concurrent_users_dataset["models"]
        
        # Execute memory-intensive operations
        def memory_intensive_operations(user: User, iterations: int):
            """Perform operations that may consume memory."""
            Session = sessionmaker(bind=load_test_runner.db_session.bind, expire_on_commit=False)
            session = Session()
            
            try:
                registry = DatabaseModelRegistry(session, user)
                search_config = SearchConfig(backend_type="database", max_results=100)
                search = AdvancedModelSearch(session, search_config)
                
                for i in range(iterations):
                    # Operations that may accumulate memory
                    models_list = registry.list_models(include_public=True)
                    search_results = search.search("test model sklearn", max_results=50)
                    
                    # Clear any local references
                    del models_list, search_results
                    
                    if i % 10 == 0:
                        # Periodic memory check
                        current_memory = process.memory_info().rss / 1024 / 1024
                        load_test_runner.record_operation(
                            'memory_check', current_memory, True, str(user.id))
            
            finally:
                session.close()
        
        # Run with 15 users
        test_users = users[:15]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            futures = [
                executor.submit(memory_intensive_operations, user, 40)
                for user in test_users
            ]
            
            # Wait for completion
            for future in concurrent.futures.as_completed(futures, timeout=60):
                try:
                    future.result()
                except Exception as exc:
                    print(f"Memory test error: {exc}")
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory usage assertions
        assert memory_increase < 100, f"Memory increase too high: {memory_increase:.1f}MB"
        assert final_memory < 500, f"Total memory usage too high: {final_memory:.1f}MB"
        
        print(f"Memory usage: {initial_memory:.1f}MB -> {final_memory:.1f}MB " + \
              f"(+{memory_increase:.1f}MB)")
    
    def test_system_stability_extended_load(self, load_db_session, concurrent_users_dataset, load_test_runner):
        """Test system stability under extended load periods."""
        users = concurrent_users_dataset["users"]
        models = concurrent_users_dataset["models"]
        
        # Extended load test - lower concurrency but longer duration
        def sustained_user_activity(user: User, duration_seconds: int) -> Dict:
            """Simulate sustained user activity over time.
            
            Parameters
            ----------
            user : User
                User performing sustained activity.
            duration_seconds : int
                Duration of activity in seconds.
                
            Returns
            -------
            Dict
                Activity results.
            """
            Session = sessionmaker(bind=load_test_runner.db_session.bind, expire_on_commit=False)
            session = Session()
            
            results = {'operations_completed': 0, 'errors': 0, 'start_time': time.time()}
            
            try:
                registry = DatabaseModelRegistry(session, user)
                analytics = ModelAnalytics(session)
                
                end_time = time.time() + duration_seconds
                
                while time.time() < end_time:
                    start_op_time = time.time()
                    success = True
                    
                    try:
                        # Alternate between different operations
                        op_type = results['operations_completed'] % 4
                        
                        if op_type == 0:
                            result = registry.list_models()
                        elif op_type == 1 and models:
                            model = random.choice(models)
                            result = registry.get_model(str(model.id))
                        elif op_type == 2:
                            result = registry.search_models("test")
                        else:
                            if models:
                                model = random.choice(models)
                                result = analytics.get_model_stats(str(model.id))
                    
                    except Exception as e:
                        success = False
                        results['errors'] += 1
                    
                    response_time = time.time() - start_op_time
                    load_test_runner.record_operation('sustained_op', response_time, success, str(user.id))
                    
                    results['operations_completed'] += 1
                    
                    # Realistic user pacing
                    time.sleep(random.uniform(0.1, 0.3))  # 100-300ms between operations
            
            finally:
                session.close()
            
            results['total_duration'] = time.time() - results['start_time']
            return results
        
        # Test with 10 users over 30 seconds (sustained load)
        test_users = users[:10]
        load_test_runner.metrics.clear()
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(sustained_user_activity, user, 30)
                for user in test_users
            ]
            
            results = []
            for future in concurrent.futures.as_completed(futures, timeout=45):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    results.append({'error': str(exc), 'operations_completed': 0, 'errors': 1})
        
        total_time = time.time() - start_time
        
        # Analyze sustained load results
        total_operations = sum(r.get('operations_completed', 0) for r in results)
        total_errors = sum(r.get('errors', 0) for r in results)
        success_rate = (total_operations - total_errors) / max(total_operations, 1)
        
        sustained_metrics = load_test_runner.get_metrics_summary('sustained_op')
        
        # Stability assertions
        assert success_rate >= 0.95, f"Sustained load success rate too low: {success_rate:.2%}"
        assert sustained_metrics.avg_response_time < 0.5, \
            f"Sustained load avg response time too high: {sustained_metrics.avg_response_time:.3f}s"
        assert total_time < 40, f"Sustained load test exceeded time limit: {total_time:.1f}s"
        
        # Check for performance degradation over time
        time_sorted_ops = sorted(load_test_runner.metrics['sustained_op'], key=lambda x: x['timestamp'])
        if len(time_sorted_ops) >= 20:
            early_ops = time_sorted_ops[:len(time_sorted_ops)//3]
            late_ops = time_sorted_ops[-len(time_sorted_ops)//3:]
            
            early_avg = sum(op['response_time'] for op in early_ops) / len(early_ops)
            late_avg = sum(op['response_time'] for op in late_ops) / len(late_ops)
            
            # Performance shouldn't degrade by more than 50%
            degradation_ratio = late_avg / max(early_avg, 0.001)
            assert degradation_ratio < 1.5, \
                f"Performance degraded too much: {degradation_ratio:.2f}x slower"
        
        print(f"Sustained load: {total_operations} ops over {total_time:.1f}s, " + \
              f"{success_rate:.1%} success, avg {sustained_metrics.avg_response_time*1000:.1f}ms")


if __name__ == "__main__":
    pytest.main([__file__])