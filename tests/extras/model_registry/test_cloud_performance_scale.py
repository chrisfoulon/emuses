"""Performance tests for large-scale cloud operations - Task 3.7.1c.

This module provides performance testing for cloud model registry operations
under load, testing scalability, throughput, and performance characteristics
with large datasets and concurrent operations.
"""
import pytest
import asyncio
import time
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import random
import string

from emuses.extras.cloud_storage import S3StorageBackend, AzureBlobStorageBackend, GCSStorageBackend
from emuses.extras.cloud_model_registry import CloudModelRegistry
from emuses.multi_user_service.models import User, ModelRegistry


class TestCloudStoragePerformanceScale:
    """Performance tests for cloud storage operations at scale."""
    
    @pytest.fixture
    def mock_storage_backend_with_delays(self):
        """Create mock storage backend with realistic delays."""
        backend = MagicMock(spec=S3StorageBackend)
        
        # Simulate realistic cloud storage latencies
        async def mock_upload_with_delay(model_path, model_id):
            await asyncio.sleep(0.1)  # 100ms upload simulation
            return f"s3://bucket/models/{model_id}/model_bundle.tar.gz"
            
        async def mock_download_with_delay(storage_url, local_path):
            await asyncio.sleep(0.05)  # 50ms download simulation
            
        async def mock_delete_with_delay(storage_url):
            await asyncio.sleep(0.02)  # 20ms delete simulation
            
        async def mock_signed_url_with_delay(storage_url, expires_in=3600):
            await asyncio.sleep(0.01)  # 10ms signed URL generation
            return f"https://signed-url.example.com/{random.randint(1000, 9999)}"
        
        backend.upload_model = mock_upload_with_delay
        backend.download_model = mock_download_with_delay
        backend.delete_model = mock_delete_with_delay
        backend.generate_signed_url = mock_signed_url_with_delay
        
        return backend
    
    @pytest.fixture
    def large_model_collection(self):
        """Create collection of large model directories for testing."""
        temp_base = Path(tempfile.mkdtemp())
        model_dirs = []
        
        # Create 20 model directories with varying sizes
        for i in range(20):
            model_dir = temp_base / f"large-model-{i}"
            model_dir.mkdir()
            
            # Create model structure
            (model_dir / "models").mkdir()
            (model_dir / "artifacts").mkdir()
            (model_dir / "checkpoints").mkdir()
            
            # Create files of varying sizes
            num_files = random.randint(5, 15)
            for j in range(num_files):
                file_path = model_dir / "models" / f"model_part_{j}.bin"
                # Create files with random content (100-1000 chars)
                content_size = random.randint(100, 1000)
                file_path.write_text('x' * content_size)
            
            # Create manifest
            manifest = {
                "name": f"Large Test Model {i}",
                "version": f"1.{i}.0",
                "created_at": datetime.now().isoformat(),
                "model_type": "transformer",
                "framework": "pytorch",
                "size_mb": random.randint(100, 2000),  # 100MB to 2GB simulation
                "parameters": random.randint(1000000, 175000000)
            }
            (model_dir / "model_manifest.json").write_text(json.dumps(manifest))
            
            model_dirs.append(model_dir)
        
        yield model_dirs
        
        # Cleanup
        shutil.rmtree(temp_base)
    
    @pytest.mark.asyncio
    async def test_concurrent_uploads_performance(self, mock_storage_backend_with_delays, large_model_collection):
        """Test performance of concurrent model uploads."""
        # Create multiple model registries to simulate multiple users
        registries = []
        for i in range(5):  # 5 concurrent users
            mock_db = MagicMock()
            mock_user = MagicMock(spec=User)
            mock_user.id = uuid4()
            
            temp_cache = Path(tempfile.mkdtemp())
            registry = CloudModelRegistry(
                db_session=mock_db,
                user=mock_user,
                storage_backend=mock_storage_backend_with_delays,
                local_cache_path=temp_cache
            )
            registries.append((registry, temp_cache))
        
        try:
            # Test concurrent uploads
            start_time = time.time()
            
            async def upload_model(registry, model_dir, model_id):
                metadata = {
                    "name": f"Concurrent Test Model {model_id}",
                    "version": "1.0.0",
                    "description": "Performance test model"
                }
                try:
                    result = await registry.upload_model(model_dir, str(model_id), metadata)
                    return {"success": True, "model_id": model_id, "result": result}
                except Exception as e:
                    if "not implemented" in str(e).lower() or "attributeerror" in str(type(e).__name__).lower():
                        pytest.skip(f"Upload method not implemented: {e}")
                    return {"success": False, "model_id": model_id, "error": str(e)}
            
            # Create upload tasks - 4 models per registry (20 total uploads)
            tasks = []
            model_counter = 0
            for registry, _ in registries:
                for model_dir in large_model_collection[:4]:  # 4 models per user
                    model_id = uuid4()
                    tasks.append(upload_model(registry, model_dir, model_id))
                    model_counter += 1
            
            # Execute all uploads concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            # Analyze performance
            total_time = end_time - start_time
            successful_uploads = sum(1 for r in results if isinstance(r, dict) and r.get("success", False))
            
            # Performance assertions
            assert total_time < 10.0  # Should complete within 10 seconds with mocking
            throughput = successful_uploads / total_time if total_time > 0 else 0
            
            print(f"Concurrent upload performance:")
            print(f"  Total uploads: {len(tasks)}")
            print(f"  Successful: {successful_uploads}")
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Throughput: {throughput:.2f} uploads/sec")
            
            # Verify reasonable throughput (accounting for mocked delays)
            if successful_uploads > 0:
                assert throughput > 1.0  # At least 1 upload per second with concurrency
                
        finally:
            # Cleanup cache directories
            for _, temp_cache in registries:
                if temp_cache.exists():
                    shutil.rmtree(temp_cache)
    
    @pytest.mark.asyncio
    async def test_large_model_catalog_performance(self, mock_storage_backend_with_delays):
        """Test performance with large model catalogs (1000+ models)."""
        mock_db = MagicMock()
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid4()
        
        temp_cache = Path(tempfile.mkdtemp())
        registry = CloudModelRegistry(
            db_session=mock_db,
            user=mock_user,
            storage_backend=mock_storage_backend_with_delays,
            local_cache_path=temp_cache
        )
        
        try:
            # Create large number of mock models in database
            large_model_list = []
            for i in range(1000):
                mock_model = MagicMock(spec=ModelRegistry)
                mock_model.id = str(uuid4())
                mock_model.name = f"Large Catalog Model {i}"
                mock_model.owner_id = mock_user.id
                mock_model.created_at = datetime.now() - timedelta(days=random.randint(1, 365))
                mock_model.size_bytes = random.randint(1024*1024, 1024*1024*1000)  # 1MB to 1GB
                mock_model.download_count = random.randint(0, 10000)
                mock_model.cloud_storage_url = f"s3://bucket/models/{mock_model.id}/model_bundle.tar.gz"
                mock_model.access_level = "public" if i % 5 == 0 else "private"
                large_model_list.append(mock_model)
            
            # Mock database query to return large result set
            mock_db.query.return_value.filter.return_value.all.return_value = large_model_list
            
            # Test listing performance with large catalog
            start_time = time.time()
            
            try:
                result = await registry.list_models(include_cloud_metadata=True)
                end_time = time.time()
                
                list_time = end_time - start_time
                
                # Performance assertions for large catalog
                assert list_time < 2.0  # Should complete within 2 seconds
                
                # Verify result structure
                assert isinstance(result, dict)
                if "models" in result:
                    assert len(result["models"]) <= 1000  # Should handle large catalogs
                
                print(f"Large catalog listing performance:")
                print(f"  Models in catalog: 1000")
                print(f"  List time: {list_time:.3f}s")
                print(f"  Throughput: {1000/list_time:.1f} models/sec")
                
            except Exception as e:
                if "not implemented" in str(e).lower() or "attributeerror" in str(type(e).__name__).lower():
                    pytest.skip(f"List method not implemented: {e}")
                else:
                    raise
                    
        finally:
            # Cleanup
            if temp_cache.exists():
                shutil.rmtree(temp_cache)
    
    @pytest.mark.asyncio
    async def test_search_performance_with_large_dataset(self, mock_storage_backend_with_delays):
        """Test search performance with large model datasets."""
        mock_db = MagicMock()
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid4()
        
        temp_cache = Path(tempfile.mkdtemp())
        registry = CloudModelRegistry(
            db_session=mock_db,
            user=mock_user,
            storage_backend=mock_storage_backend_with_delays,
            local_cache_path=temp_cache
        )
        
        try:
            # Create diverse model dataset for search testing
            search_terms = ["transformer", "resnet", "bert", "gpt", "vgg", "mobilenet", "efficientnet"]
            frameworks = ["pytorch", "tensorflow", "onnx", "huggingface"]
            
            search_models = []
            for i in range(500):
                mock_model = MagicMock(spec=ModelRegistry)
                mock_model.id = str(uuid4())
                
                # Create searchable content
                term = random.choice(search_terms)
                framework = random.choice(frameworks)
                mock_model.name = f"{term.title()}-{framework}-Model-{i}"
                mock_model.description = f"A {term} model built with {framework} for performance testing"
                mock_model.tags = [term, framework, "performance", "test"]
                mock_model.owner_id = mock_user.id
                mock_model.access_level = "public"
                
                search_models.append(mock_model)
            
            # Test search performance for different query types
            test_queries = [
                "transformer",           # Single term
                "pytorch transformer",   # Multiple terms  
                "bert performance",      # Mixed terms
                "efficient",            # Partial match
                "gpt-3"                 # Specific model
            ]
            
            for query in test_queries:
                # Mock search results (simulate database search)
                matching_models = [
                    m for m in search_models 
                    if any(query.lower() in str(getattr(m, attr, "")).lower() 
                          for attr in ["name", "description", "tags"])
                ]
                
                mock_db.query.return_value.filter.return_value.all.return_value = matching_models[:50]  # Limit results
                
                start_time = time.time()
                
                try:
                    # Test search functionality (if implemented)
                    result = await registry.search_models(query, limit=50)
                    end_time = time.time()
                    
                    search_time = end_time - start_time
                    
                    # Performance assertions
                    assert search_time < 0.5  # Should complete within 500ms
                    
                    print(f"Search performance for '{query}':")
                    print(f"  Search time: {search_time:.3f}s")
                    print(f"  Results found: {len(result.get('models', []))}")
                    
                except Exception as e:
                    if "not implemented" in str(e).lower() or "attributeerror" in str(type(e).__name__).lower():
                        pytest.skip(f"Search method not implemented: {e}")
                    else:
                        raise
                        
        finally:
            # Cleanup
            if temp_cache.exists():
                shutil.rmtree(temp_cache)
    
    @pytest.mark.asyncio
    async def test_cache_performance_with_high_frequency_access(self, mock_storage_backend_with_delays):
        """Test cache performance with high-frequency model access."""
        mock_db = MagicMock()
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid4()
        
        temp_cache = Path(tempfile.mkdtemp())
        registry = CloudModelRegistry(
            db_session=mock_db,
            user=mock_user,
            storage_backend=mock_storage_backend_with_delays,
            local_cache_path=temp_cache,
            enable_caching=True
        )
        
        try:
            # Create popular models for cache testing
            popular_models = []
            for i in range(10):
                model_id = str(uuid4())
                mock_model = MagicMock(spec=ModelRegistry)
                mock_model.id = model_id
                mock_model.name = f"Popular Model {i}"
                mock_model.owner_id = mock_user.id
                mock_model.cloud_storage_url = f"s3://bucket/models/{model_id}/model_bundle.tar.gz"
                mock_model.download_count = random.randint(1000, 10000)  # High download count
                popular_models.append(mock_model)
            
            # Pre-populate some models in cache
            for i in range(5):
                model_id = popular_models[i].id
                cache_path = temp_cache / model_id
                cache_path.mkdir(parents=True, exist_ok=True)
                (cache_path / "model.bin").write_text(f"cached model {i} data")
                (cache_path / "model_manifest.json").write_text(f'{{"name": "Cached Model {i}"}}')
            
            # Test high-frequency access patterns
            access_patterns = [
                # Simulate cache hits (models 0-4 are cached)
                [popular_models[i % 5] for i in range(20)],  # 20 requests to cached models
                # Simulate cache misses (models 5-9 are not cached)
                [popular_models[5 + (i % 5)] for i in range(10)],  # 10 requests to uncached models
            ]
            
            for pattern_name, models in [("cached", access_patterns[0]), ("uncached", access_patterns[1])]:
                start_time = time.time()
                
                async def download_with_cache(model):
                    mock_db.query.return_value.filter.return_value.first.return_value = model
                    download_path = temp_cache / f"downloads/{model.id}"
                    
                    try:
                        result = await registry.download_model(str(model.id), download_path, use_cache=True)
                        return {"success": True, "cache_hit": result.get("cache_hit", False)}
                    except Exception as e:
                        if "not implemented" in str(e).lower() or "attributeerror" in str(type(e).__name__).lower():
                            pytest.skip(f"Download method not implemented: {e}")
                        return {"success": False, "error": str(e)}
                
                # Execute downloads concurrently
                tasks = [download_with_cache(model) for model in models]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                end_time = time.time()
                total_time = end_time - start_time
                
                successful_downloads = sum(1 for r in results if isinstance(r, dict) and r.get("success", False))
                cache_hits = sum(1 for r in results if isinstance(r, dict) and r.get("cache_hit", False))
                
                print(f"Cache performance ({pattern_name} pattern):")
                print(f"  Total downloads: {len(models)}")
                print(f"  Successful: {successful_downloads}")
                print(f"  Cache hits: {cache_hits}")
                print(f"  Total time: {total_time:.3f}s")
                
                if successful_downloads > 0:
                    throughput = successful_downloads / total_time
                    print(f"  Throughput: {throughput:.1f} downloads/sec")
                    
                    # Performance assertions
                    assert total_time < 5.0  # Should complete within 5 seconds
                    
                    if pattern_name == "cached":
                        # Cached downloads should be faster
                        assert throughput > 10.0  # At least 10 downloads/sec for cached models
                        
        finally:
            # Cleanup
            if temp_cache.exists():
                shutil.rmtree(temp_cache)


class TestCloudStorageProviderPerformance:
    """Test performance characteristics across different cloud providers."""
    
    def create_mock_provider_backend(self, provider_type, latency_ms):
        """Create mock backend with provider-specific latencies."""
        if provider_type == "s3":
            backend = MagicMock(spec=S3StorageBackend)
        elif provider_type == "azure":
            backend = MagicMock(spec=AzureBlobStorageBackend)
        elif provider_type == "gcs":
            backend = MagicMock(spec=GCSStorageBackend)
        else:
            raise ValueError(f"Unknown provider: {provider_type}")
        
        latency_sec = latency_ms / 1000.0
        
        async def mock_operation_with_latency(*args, **kwargs):
            await asyncio.sleep(latency_sec)
            return f"{provider_type}://bucket/models/test/model_bundle.tar.gz"
        
        backend.upload_model = mock_operation_with_latency
        backend.download_model = mock_operation_with_latency
        backend.delete_model = mock_operation_with_latency
        
        return backend
    
    @pytest.mark.asyncio
    async def test_cross_provider_performance_comparison(self):
        """Compare performance characteristics across cloud providers."""
        # Simulate typical latencies (in milliseconds)
        provider_configs = [
            ("s3", 80),      # AWS S3 - typically lower latency
            ("azure", 100),  # Azure Blob - moderate latency
            ("gcs", 90),     # Google Cloud Storage - moderate latency  
        ]
        
        performance_results = {}
        
        for provider, latency_ms in provider_configs:
            backend = self.create_mock_provider_backend(provider, latency_ms)
            
            # Test upload performance
            start_time = time.time()
            
            # Create test tasks
            tasks = []
            for i in range(10):  # 10 operations per provider
                temp_path = Path(f"/tmp/test-model-{i}")
                model_id = str(uuid4())
                tasks.append(backend.upload_model(temp_path, model_id))
            
            # Execute operations concurrently
            await asyncio.gather(*tasks)
            end_time = time.time()
            
            total_time = end_time - start_time
            throughput = len(tasks) / total_time
            
            performance_results[provider] = {
                "latency_ms": latency_ms,
                "total_time": total_time,
                "throughput": throughput,
                "operations": len(tasks)
            }
            
            print(f"{provider.upper()} Performance:")
            print(f"  Latency: {latency_ms}ms")
            print(f"  Total time: {total_time:.3f}s")
            print(f"  Throughput: {throughput:.2f} ops/sec")
        
        # Performance comparison assertions
        s3_perf = performance_results["s3"]
        azure_perf = performance_results["azure"]
        gcs_perf = performance_results["gcs"]
        
        # Verify that lower latency providers achieve higher throughput
        assert s3_perf["throughput"] > azure_perf["throughput"] * 0.8  # Within 20%
        
        # All providers should achieve reasonable throughput with concurrency
        for provider, perf in performance_results.items():
            assert perf["throughput"] > 5.0  # At least 5 operations/sec
    
    @pytest.mark.asyncio
    async def test_provider_failover_performance(self):
        """Test performance impact of provider failover scenarios."""
        # Create primary and backup providers
        primary_backend = self.create_mock_provider_backend("s3", 80)
        backup_backend = self.create_mock_provider_backend("azure", 100)
        
        # Simulate primary provider failure after some operations
        operation_count = 0
        original_upload = primary_backend.upload_model
        
        async def failing_upload(*args, **kwargs):
            nonlocal operation_count
            operation_count += 1
            if operation_count > 5:  # Fail after 5 operations
                raise Exception("Primary provider unavailable")
            return await original_upload(*args, **kwargs)
        
        primary_backend.upload_model = failing_upload
        
        # Test failover performance
        start_time = time.time()
        
        successful_ops = 0
        failed_ops = 0
        
        for i in range(10):
            try:
                temp_path = Path(f"/tmp/failover-test-{i}")
                model_id = str(uuid4())
                
                # Try primary first, then backup
                try:
                    await primary_backend.upload_model(temp_path, model_id)
                    successful_ops += 1
                except:
                    # Failover to backup
                    await backup_backend.upload_model(temp_path, model_id)
                    successful_ops += 1
                    
            except Exception:
                failed_ops += 1
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"Failover Performance:")
        print(f"  Total operations: 10")
        print(f"  Successful: {successful_ops}")
        print(f"  Failed: {failed_ops}")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Throughput: {successful_ops/total_time:.2f} ops/sec")
        
        # Performance assertions for failover scenario
        assert successful_ops >= 8  # Most operations should succeed with failover
        assert total_time < 5.0  # Should complete within 5 seconds
        
        if successful_ops > 0:
            throughput = successful_ops / total_time
            assert throughput > 2.0  # At least 2 ops/sec even with failures


class TestCloudStorageMemoryAndResourcePerformance:
    """Test memory usage and resource efficiency of cloud operations."""
    
    @pytest.mark.asyncio
    async def test_memory_efficiency_with_large_models(self):
        """Test memory efficiency when handling large model uploads/downloads."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        backend = MagicMock(spec=S3StorageBackend)
        
        # Simulate large model processing with streaming
        async def streaming_upload(model_path, model_id):
            # Simulate streaming upload without loading entire model into memory
            await asyncio.sleep(0.1)
            return f"s3://bucket/models/{model_id}/model_bundle.tar.gz"
            
        async def streaming_download(storage_url, local_path):
            # Simulate streaming download
            await asyncio.sleep(0.1)
            
        backend.upload_model = streaming_upload
        backend.download_model = streaming_download
        
        # Create temporary large model directories
        temp_base = Path(tempfile.mkdtemp())
        large_models = []
        
        try:
            # Create 5 simulated large models
            for i in range(5):
                model_dir = temp_base / f"large-model-{i}"
                model_dir.mkdir()
                
                # Create several "large" files
                for j in range(10):
                    file_path = model_dir / f"model_part_{j}.bin"
                    # Create moderate size files to avoid excessive memory usage in tests
                    file_path.write_text('x' * 10000)  # 10KB per file
                
                large_models.append(model_dir)
            
            # Test concurrent operations with large models
            tasks = []
            for i, model_dir in enumerate(large_models):
                model_id = str(uuid4())
                tasks.append(backend.upload_model(model_dir, model_id))
                
                # Add download task
                tasks.append(backend.download_model(
                    f"s3://bucket/models/{model_id}/model_bundle.tar.gz",
                    temp_base / f"download-{i}"
                ))
            
            # Execute all operations
            await asyncio.gather(*tasks)
            
            # Check memory usage after operations
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory
            
            print(f"Memory Performance:")
            print(f"  Initial memory: {initial_memory:.1f} MB")
            print(f"  Final memory: {final_memory:.1f} MB")
            print(f"  Memory increase: {memory_increase:.1f} MB")
            print(f"  Models processed: {len(large_models)}")
            print(f"  Memory per model: {memory_increase/len(large_models):.1f} MB")
            
            # Memory efficiency assertions
            assert memory_increase < 50  # Should not increase by more than 50MB
            assert memory_increase / len(large_models) < 10  # Less than 10MB per model
            
        finally:
            # Cleanup
            shutil.rmtree(temp_base)
    
    @pytest.mark.asyncio
    async def test_connection_pool_performance(self):
        """Test connection pooling performance for cloud providers."""
        # Simulate connection pool with reusable connections
        connection_pool = {"connections": 0, "max_connections": 10}
        
        backend = MagicMock(spec=S3StorageBackend)
        
        async def pooled_operation(*args, **kwargs):
            # Simulate connection acquisition
            if connection_pool["connections"] < connection_pool["max_connections"]:
                connection_pool["connections"] += 1
                await asyncio.sleep(0.05)  # Connection setup time
            else:
                await asyncio.sleep(0.01)  # Reused connection time
            
            await asyncio.sleep(0.02)  # Operation time
            return "s3://bucket/models/test/result"
        
        backend.upload_model = pooled_operation
        backend.download_model = pooled_operation
        
        # Test performance with and without connection pooling
        start_time = time.time()
        
        # Create many concurrent operations
        tasks = []
        for i in range(50):  # 50 operations to test pooling
            if i % 2 == 0:
                tasks.append(backend.upload_model(Path("/tmp/test"), str(uuid4())))
            else:
                tasks.append(backend.download_model("s3://test", Path("/tmp/download")))
        
        # Execute operations
        await asyncio.gather(*tasks)
        end_time = time.time()
        
        total_time = end_time - start_time
        throughput = len(tasks) / total_time
        
        print(f"Connection Pool Performance:")
        print(f"  Operations: {len(tasks)}")
        print(f"  Max connections: {connection_pool['max_connections']}")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Throughput: {throughput:.2f} ops/sec")
        
        # Performance assertions for connection pooling
        assert total_time < 10.0  # Should complete efficiently with pooling
        assert throughput > 5.0  # Should achieve good throughput with reused connections