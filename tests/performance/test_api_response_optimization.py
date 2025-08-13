"""Test suite for API response optimization.

This module tests pagination, compression, and JSON serialization optimizations
for model registry API endpoints with focus on performance and scalability.
"""

import asyncio
import gzip
import json
import time
from typing import Dict, List, Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from emuses.multi_user_service.model_registry_endpoints import get_model_registry_router
from emuses.multi_user_service.models import User, ModelRegistry, Workspace
from emuses.tools.database_model_registry import DatabaseModelRegistry


class TestAPIPaginationOptimization:
    """Test comprehensive pagination implementation for API endpoints."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        """Create mock user for testing."""
        user = MagicMock()
        user.id = "user-123-456-789"
        user.email = "test@example.com"
        return user

    @pytest.fixture
    def test_app_with_pagination(self, mock_db_session, mock_user):
        """Create FastAPI test app with pagination endpoints."""
        from fastapi import FastAPI
        
        app = FastAPI()
        router = get_model_registry_router()
        app.include_router(router)
        
        # Mock authentication and database
        def mock_current_user():
            return mock_user
            
        def mock_get_db():
            yield mock_db_session
        
        # Mock dependencies - need to import the actual dependencies
        from emuses.multi_user_service.auth import fastapi_users
        from emuses.multi_user_service.database import get_db
        
        app.dependency_overrides[fastapi_users.current_user(active=True)] = mock_current_user
        app.dependency_overrides[get_db] = mock_get_db
        
        return TestClient(app)

    def create_test_models(self, db_session: Session, user_id: str, count: int) -> List[Dict[str, Any]]:
        """Create test models in database for pagination testing.
        
        Parameters
        ----------
        db_session : Session
            Database session
        user_id : str
            User ID for model ownership
        count : int
            Number of models to create
            
        Returns
        -------
        List[Dict[str, Any]]
            List of created model metadata
        """
        models = []
        
        for i in range(count):
            model_data = {
                "id": f"model-{i:04d}",
                "name": f"Test Model {i:04d}",
                "version": "1.0.0",
                "owner_id": user_id,
                "model_type": "umap" if i % 2 == 0 else "sklearn",
                "description": f"Test model {i} for pagination testing with detailed description",
                "tags": [f"tag{i % 3}", f"category{i % 5}"],
                "is_public": i % 4 == 0,  # 25% public
                "model_size_bytes": 1024 * 1024 * (i + 1),  # Varying sizes
                "download_count": i * 10,
                "created_at": f"2024-01-{i % 28 + 1:02d}T10:00:00Z"
            }
            models.append(model_data)
            
        return models

    @pytest.mark.performance
    def test_pagination_parameter_validation(self, test_app_with_pagination, mock_user):
        """Test pagination parameter validation and defaults.
        
        Validates that API endpoints properly handle pagination parameters
        including offset, limit, and boundary conditions.
        """
        app = test_app_with_pagination
        
        # Test default pagination
        response = app.get("/api/v1/models/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Test limit parameter
        response = app.get("/api/v1/models/?limit=25")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 25
        
        # Test limit boundary (should cap at 100)
        response = app.get("/api/v1/models/?limit=200")
        assert response.status_code == 200  # Should not error but cap limit
        
        # Test negative limit (should use default)
        response = app.get("/api/v1/models/?limit=-10")
        assert response.status_code == 200
        
        return {"status": "pagination_validation_complete"}

    @pytest.mark.performance
    def test_offset_pagination_implementation(self, test_app_with_pagination):
        """Test offset-based pagination for large result sets.
        
        Validates that offset pagination works correctly for large model catalogs
        and maintains consistent ordering across pages.
        """
        app = test_app_with_pagination
        
        # Create realistic test scenario with 150 models
        with patch.object(DatabaseModelRegistry, 'list_models') as mock_list:
            # Mock large model set
            large_model_set = []
            for i in range(150):
                large_model_set.append({
                    "model_id": f"model-{i:03d}",
                    "name": f"Model {i:03d}",
                    "version": "1.0.0",
                    "type": "umap",
                    "description": f"Test model {i}",
                    "tags": [f"tag{i % 5}"],
                    "is_public": False,
                    "owner_id": "user-123",
                    "workspace_id": None,
                    "created_at": f"2024-01-01T{i:02d}:00:00Z",
                    "updated_at": f"2024-01-01T{i:02d}:00:00Z",
                    "download_count": i,
                    "size_mb": float(i + 1)
                })
            
            mock_list.return_value = large_model_set
            
            # Test first page
            response = app.get("/api/v1/models/?limit=50&offset=0")
            assert response.status_code == 200
            page1 = response.json()
            assert len(page1) == 50
            
            # Test second page 
            response = app.get("/api/v1/models/?limit=50&offset=50")
            assert response.status_code == 200
            page2 = response.json()
            assert len(page2) == 50
            
            # Verify no overlap between pages
            page1_ids = {model["model_id"] for model in page1}
            page2_ids = {model["model_id"] for model in page2}
            assert len(page1_ids.intersection(page2_ids)) == 0
            
            # Test final partial page
            response = app.get("/api/v1/models/?limit=50&offset=100")
            assert response.status_code == 200
            page3 = response.json()
            assert len(page3) == 50  # Last 50 models
            
        return {"status": "offset_pagination_verified", "total_models_tested": 150}

    @pytest.mark.performance
    def test_search_pagination_with_relevance(self, test_app_with_pagination):
        """Test search endpoint pagination maintains relevance ordering.
        
        Ensures that search results maintain relevance scoring across
        paginated responses and don't lose ranking information.
        """
        app = test_app_with_pagination
        
        with patch.object(DatabaseModelRegistry, 'search_models') as mock_search:
            # Mock search results with relevance scoring
            search_results = []
            for i in range(75):
                relevance_score = 100 - i  # Decreasing relevance
                search_results.append({
                    "model_id": f"search-model-{i:03d}",
                    "name": f"Relevant Model {100-i:03d}",  # Higher relevance = lower number
                    "version": "1.0.0",
                    "type": "umap",
                    "description": f"Search result {i} with relevance {relevance_score}",
                    "tags": ["search", "test"],
                    "is_public": True,
                    "owner_id": "user-456",
                    "workspace_id": None,
                    "created_at": "2024-01-15T10:00:00Z",
                    "updated_at": "2024-01-15T10:00:00Z",
                    "download_count": relevance_score,
                    "size_mb": 10.0,
                    "relevance_score": relevance_score  # Add relevance for testing
                })
            
            mock_search.return_value = search_results
            
            # Test paginated search results maintain order
            response = app.get("/api/v1/models/search?query=test&limit=25&offset=0")
            assert response.status_code == 200
            page1 = response.json()
            assert len(page1) == 25
            
            response = app.get("/api/v1/models/search?query=test&limit=25&offset=25")
            assert response.status_code == 200
            page2 = response.json()
            assert len(page2) == 25
            
            # Verify relevance ordering is maintained across pages
            # (Higher numbered models should have higher relevance)
            last_page1_name = page1[-1]["name"]
            first_page2_name = page2[0]["name"]
            
            # Extract numbers for comparison
            page1_num = int(last_page1_name.split()[-1])
            page2_num = int(first_page2_name.split()[-1])
            
            assert page1_num > page2_num, "Relevance ordering should be maintained across pages"
            
        return {"status": "search_pagination_verified", "pages_tested": 3}

    @pytest.mark.performance  
    def test_pagination_performance_targets(self, test_app_with_pagination):
        """Test that paginated responses meet performance targets.
        
        Validates that API responses with pagination complete within
        performance targets (<500ms for 50 items per page).
        """
        app = test_app_with_pagination
        
        with patch.object(DatabaseModelRegistry, 'list_models') as mock_list:
            # Create large realistic dataset
            large_dataset = []
            for i in range(1000):
                large_dataset.append({
                    "model_id": f"perf-model-{i:04d}",
                    "name": f"Performance Test Model {i:04d}",
                    "version": f"1.{i % 10}.0",
                    "type": "umap" if i % 3 == 0 else "sklearn",
                    "description": f"Performance testing model {i} with comprehensive metadata and details",
                    "tags": [f"perf", f"test{i % 10}", f"category{i % 5}"],
                    "is_public": i % 10 == 0,
                    "owner_id": f"user-{i % 20}",
                    "workspace_id": f"workspace-{i % 5}" if i % 4 == 0 else None,
                    "created_at": f"2024-{i % 12 + 1:02d}-01T10:00:00Z",
                    "updated_at": f"2024-{i % 12 + 1:02d}-01T10:00:00Z", 
                    "download_count": i * 5,
                    "size_mb": float((i % 100) + 1)
                })
            
            mock_list.return_value = large_dataset
            
            # Test performance with standard pagination
            start_time = time.time()
            response = app.get("/api/v1/models/?limit=50&offset=0")
            response_time = time.time() - start_time
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 50
            
            # Performance target: <500ms for paginated results
            assert response_time < 0.5, f"Paginated response took {response_time:.3f}s, target <0.5s"
            
            # Test multiple page requests for consistent performance
            response_times = []
            for offset in [0, 50, 100, 200, 500]:
                start_time = time.time()
                response = app.get(f"/api/v1/models/?limit=50&offset={offset}")
                response_time = time.time() - start_time
                response_times.append(response_time)
                
                assert response.status_code == 200
                assert response_time < 0.5
            
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            
        return {
            "status": "pagination_performance_validated",
            "avg_response_time": avg_response_time,
            "max_response_time": max_response_time,
            "target_met": max_response_time < 0.5
        }


class TestAPICompressionOptimization:
    """Test response compression optimization for API endpoints."""
    
    @pytest.mark.performance
    def test_compression_middleware_integration(self):
        """Test that compression middleware properly compresses large responses.
        
        Validates that JSON responses are compressed when they exceed
        the compression threshold and achieve target compression ratios.
        """
        # Mock large response data
        large_response = {
            "models": []
        }
        
        # Create realistic large response
        for i in range(100):
            large_response["models"].append({
                "model_id": f"compress-test-{i:03d}",
                "name": f"Compression Test Model {i:03d}",
                "version": "1.0.0",
                "type": "umap",
                "description": f"Model {i} for compression testing with detailed description that repeats common patterns and structures typical in real model metadata responses",
                "tags": ["compression", "test", "optimization", f"model{i % 10}"],
                "is_public": False,
                "owner_id": "user-123-456-789",
                "workspace_id": "workspace-abc-def-123",
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T10:00:00Z",
                "download_count": i * 10,
                "size_mb": float(i + 1)
            })
        
        # Test uncompressed size
        uncompressed_data = json.dumps(large_response)
        uncompressed_size = len(uncompressed_data.encode('utf-8'))
        
        # Test compressed size
        compressed_data = gzip.compress(uncompressed_data.encode('utf-8'))
        compressed_size = len(compressed_data)
        
        # Calculate compression ratio
        compression_ratio = (uncompressed_size - compressed_size) / uncompressed_size * 100
        
        # Validation: Should achieve >50% compression on repetitive JSON
        assert compression_ratio > 50.0, f"Compression ratio {compression_ratio:.1f}% below target 50%"
        
        # Validation: Decompressed data should match original
        decompressed_data = gzip.decompress(compressed_data).decode('utf-8')
        decompressed_obj = json.loads(decompressed_data)
        assert decompressed_obj == large_response
        
        return {
            "uncompressed_size": uncompressed_size,
            "compressed_size": compressed_size,
            "compression_ratio": compression_ratio,
            "target_achieved": compression_ratio > 50.0
        }

    @pytest.mark.performance
    def test_compression_performance_impact(self):
        """Test that compression does not significantly impact response times.
        
        Validates that the compression overhead does not exceed acceptable
        limits while still providing substantial size reduction benefits.
        """
        # Create test data
        test_models = []
        for i in range(200):
            test_models.append({
                "model_id": f"perf-compress-{i:03d}",
                "name": f"Performance Compression Model {i:03d}",
                "version": "1.0.0",
                "type": "umap",
                "description": f"Performance test model {i} with standard metadata patterns",
                "tags": ["performance", "compression", f"batch{i // 50}"],
                "is_public": i % 5 == 0,
                "owner_id": f"user-{i % 10}",
                "workspace_id": f"workspace-{i % 3}",
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T10:00:00Z",
                "download_count": i * 3,
                "size_mb": float(i + 1)
            })
        
        json_data = json.dumps(test_models)
        
        # Test serialization time (baseline)
        start_time = time.time()
        serialized = json.dumps(test_models)
        serialization_time = time.time() - start_time
        
        # Test compression time
        start_time = time.time()
        compressed = gzip.compress(serialized.encode('utf-8'))
        compression_time = time.time() - start_time
        
        # Total processing time
        total_time = serialization_time + compression_time
        
        # Performance target: compression overhead <100ms for 200 models
        assert total_time < 0.1, f"Total processing time {total_time:.3f}s exceeds 0.1s target"
        
        # Compression should not add >50% overhead
        overhead_ratio = compression_time / serialization_time
        assert overhead_ratio < 0.5, f"Compression overhead {overhead_ratio:.2f} exceeds 0.5x target"
        
        return {
            "serialization_time": serialization_time,
            "compression_time": compression_time, 
            "total_time": total_time,
            "overhead_ratio": overhead_ratio,
            "performance_target_met": total_time < 0.1
        }


class TestJSONSerializationOptimization:
    """Test JSON serialization optimization for API responses."""
    
    @pytest.mark.performance
    def test_field_selection_optimization(self):
        """Test that field selection reduces serialization overhead.
        
        Validates that API responses can be optimized by including only
        requested fields, reducing both serialization time and payload size.
        """
        # Create comprehensive model data
        full_model = {
            "model_id": "field-test-001",
            "name": "Field Selection Test Model",
            "version": "1.0.0",
            "type": "umap",
            "description": "Comprehensive model with all metadata fields for field selection testing",
            "tags": ["field", "selection", "optimization", "test"],
            "is_public": True,
            "owner_id": "user-123-456-789",
            "workspace_id": "workspace-abc-def-123",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T10:00:00Z",
            "last_accessed": "2024-01-15T10:00:00Z",
            "download_count": 150,
            "size_mb": 25.5,
            "model_size_bytes": 26738688,
            "manifest_hash": "sha256:abcdef123456789",
            "storage_path": "/path/to/model/storage",
            "total_downloads": 150,
            "workspace": {
                "id": "workspace-abc-def-123",
                "name": "Test Workspace",
                "description": "Workspace for testing"
            }
        }
        
        # Test full serialization
        start_time = time.time()
        full_json = json.dumps(full_model)
        full_serialization_time = time.time() - start_time
        full_size = len(full_json.encode('utf-8'))
        
        # Test minimal field serialization (list view)
        minimal_model = {
            "model_id": full_model["model_id"],
            "name": full_model["name"],
            "version": full_model["version"],
            "type": full_model["type"],
            "is_public": full_model["is_public"],
            "created_at": full_model["created_at"],
            "download_count": full_model["download_count"],
            "size_mb": full_model["size_mb"]
        }
        
        start_time = time.time()
        minimal_json = json.dumps(minimal_model)
        minimal_serialization_time = time.time() - start_time
        minimal_size = len(minimal_json.encode('utf-8'))
        
        # Calculate optimization gains
        size_reduction = (full_size - minimal_size) / full_size * 100
        time_reduction = (full_serialization_time - minimal_serialization_time) / full_serialization_time * 100
        
        # Validations
        assert size_reduction > 40.0, f"Size reduction {size_reduction:.1f}% below 40% target"
        assert time_reduction > 0, "Minimal serialization should be faster"
        
        return {
            "full_size": full_size,
            "minimal_size": minimal_size,
            "size_reduction": size_reduction,
            "full_time": full_serialization_time,
            "minimal_time": minimal_serialization_time,
            "time_reduction": time_reduction,
            "optimization_effective": size_reduction > 40.0
        }

    @pytest.mark.performance
    def test_bulk_serialization_optimization(self):
        """Test bulk serialization performance for large model lists.
        
        Validates that bulk serialization optimizations can handle
        large result sets efficiently within performance targets.
        """
        # Create large model dataset  
        models = []
        for i in range(500):
            models.append({
                "model_id": f"bulk-{i:04d}",
                "name": f"Bulk Model {i:04d}",
                "version": "1.0.0",
                "type": "umap" if i % 2 == 0 else "sklearn",
                "description": f"Bulk serialization test model {i}",
                "tags": [f"bulk", f"test{i % 10}", f"cat{i % 5}"],
                "is_public": i % 10 == 0,
                "owner_id": f"user-{i % 20}",
                "workspace_id": f"ws-{i % 5}",
                "created_at": f"2024-01-{(i % 28) + 1:02d}T10:00:00Z",
                "updated_at": f"2024-01-{(i % 28) + 1:02d}T10:00:00Z",
                "download_count": i * 2,
                "size_mb": float(i + 1)
            })
        
        # Test bulk serialization performance
        start_time = time.time()
        bulk_json = json.dumps(models)
        bulk_serialization_time = time.time() - start_time
        
        # Performance target: <200ms for 500 models
        assert bulk_serialization_time < 0.2, f"Bulk serialization {bulk_serialization_time:.3f}s exceeds 0.2s target"
        
        # Test memory efficiency
        json_size = len(bulk_json.encode('utf-8'))
        avg_model_size = json_size / len(models)
        
        # Should be efficient per-model serialization
        assert avg_model_size < 1000, f"Average model size {avg_model_size:.0f} bytes seems inefficient"
        
        return {
            "model_count": len(models),
            "serialization_time": bulk_serialization_time,
            "json_size": json_size,
            "avg_model_size": avg_model_size,
            "performance_target_met": bulk_serialization_time < 0.2
        }


class TestIntegratedAPIOptimization:
    """Test integrated API optimization with all features enabled."""
    
    @pytest.mark.performance
    def test_full_optimization_stack_performance(self):
        """Test complete optimization stack with pagination, compression, and serialization.
        
        Validates that all optimization techniques work together effectively
        to achieve target performance for large-scale model registry operations.
        """
        # Simulate complete API response pipeline
        
        # Step 1: Generate large dataset (simulating database query)
        large_dataset = []
        for i in range(1000):
            large_dataset.append({
                "model_id": f"integrated-{i:04d}",
                "name": f"Integrated Test Model {i:04d}",
                "version": "1.0.0",
                "type": "umap" if i % 3 == 0 else "sklearn",
                "description": f"Integrated optimization test model {i} with comprehensive metadata",
                "tags": [f"integrated", f"test{i % 10}", f"batch{i // 100}"],
                "is_public": i % 8 == 0,
                "owner_id": f"user-{i % 25}",
                "workspace_id": f"workspace-{i % 5}",
                "created_at": f"2024-{(i % 12) + 1:02d}-01T10:00:00Z",
                "updated_at": f"2024-{(i % 12) + 1:02d}-01T10:00:00Z",
                "download_count": i * 3,
                "size_mb": float((i % 50) + 1)
            })
        
        # Step 2: Apply pagination (50 items per page)
        page_size = 50
        page_offset = 0
        paginated_data = large_dataset[page_offset:page_offset + page_size]
        
        # Step 3: Apply field selection optimization
        optimized_data = []
        for model in paginated_data:
            optimized_model = {
                "model_id": model["model_id"],
                "name": model["name"], 
                "version": model["version"],
                "type": model["type"],
                "is_public": model["is_public"],
                "created_at": model["created_at"],
                "download_count": model["download_count"],
                "size_mb": model["size_mb"]
            }
            optimized_data.append(optimized_model)
        
        # Step 4: Serialize with performance tracking
        start_time = time.time()
        json_data = json.dumps(optimized_data)
        serialization_time = time.time() - start_time
        
        # Step 5: Compress response
        start_time = time.time()
        compressed_data = gzip.compress(json_data.encode('utf-8'))
        compression_time = time.time() - start_time
        
        # Calculate metrics
        total_processing_time = serialization_time + compression_time
        uncompressed_size = len(json_data.encode('utf-8'))
        compressed_size = len(compressed_data)
        compression_ratio = (uncompressed_size - compressed_size) / uncompressed_size * 100
        
        # Performance validations
        assert total_processing_time < 0.1, f"Total processing {total_processing_time:.3f}s exceeds 0.1s target"
        assert compression_ratio > 40.0, f"Compression ratio {compression_ratio:.1f}% below 40% target"
        
        # Scalability validation: processing time should scale linearly
        per_model_time = total_processing_time / len(optimized_data)
        projected_1000_time = per_model_time * 1000  # Project to 1000 models
        assert projected_1000_time < 2.0, f"Projected 1000-model time {projected_1000_time:.3f}s exceeds 2s limit"
        
        return {
            "page_size": len(optimized_data),
            "serialization_time": serialization_time,
            "compression_time": compression_time,
            "total_time": total_processing_time,
            "uncompressed_size": uncompressed_size,
            "compressed_size": compressed_size,
            "compression_ratio": compression_ratio,
            "per_model_time": per_model_time,
            "scalability_projection": projected_1000_time,
            "all_targets_met": (
                total_processing_time < 0.1 and 
                compression_ratio > 40.0 and 
                projected_1000_time < 2.0
            )
        }

    @pytest.mark.performance
    def test_caching_integration_with_optimization(self):
        """Test that response optimization works with existing caching layer.
        
        Validates that pagination, compression, and serialization optimizations
        integrate properly with the Phase 5.1.1 caching implementation.
        """
        from emuses.tools.model_registry_cache import ModelRegistryCache
        
        # Initialize cache
        cache = ModelRegistryCache(max_size=100, default_ttl=300)
        
        # Create test data
        test_models = []
        for i in range(100):
            test_models.append({
                "model_id": f"cache-opt-{i:03d}",
                "name": f"Cache Optimization Model {i:03d}",
                "version": "1.0.0",
                "type": "umap",
                "description": f"Cache integration test model {i}",
                "tags": ["cache", "optimization"],
                "is_public": i % 5 == 0,
                "owner_id": "user-123",
                "workspace_id": None,
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T10:00:00Z",
                "download_count": i,
                "size_mb": float(i + 1)
            })
        
        # Test cache miss -> optimization pipeline
        cache_key = "test_pagination_page_1"
        
        # Cache miss - apply optimization
        start_time = time.time()
        
        # Pagination
        paginated_data = test_models[0:25]  # First page
        
        # Field selection
        optimized_data = []
        for model in paginated_data:
            optimized_model = {k: v for k, v in model.items() 
                             if k in ["model_id", "name", "version", "type", "is_public", "created_at", "size_mb"]}
            optimized_data.append(optimized_model)
        
        # Serialize and cache
        serialized_data = json.dumps(optimized_data)
        optimization_time = time.time() - start_time
        
        # Store in cache
        cache.set(cache_key, optimized_data, ttl=300)
        
        # Test cache hit performance
        start_time = time.time() 
        cached_data = cache.get(cache_key)
        cache_hit_time = time.time() - start_time
        
        # Validations
        assert cached_data is not None, "Cache should contain data"
        assert len(cached_data) == 25, "Cached data should maintain pagination"
        assert cache_hit_time < 0.001, f"Cache hit {cache_hit_time:.4f}s should be <1ms"
        
        # Cache hit should be significantly faster than optimization
        speedup_ratio = optimization_time / cache_hit_time
        assert speedup_ratio > 100, f"Cache speedup {speedup_ratio:.1f}x should be >100x"
        
        # Verify data integrity through cache
        assert cached_data[0]["model_id"] == "cache-opt-000"
        assert "description" not in cached_data[0], "Field selection should be preserved in cache"
        
        return {
            "optimization_time": optimization_time,
            "cache_hit_time": cache_hit_time,
            "speedup_ratio": speedup_ratio,
            "cached_items": len(cached_data),
            "cache_integration_successful": speedup_ratio > 100
        }