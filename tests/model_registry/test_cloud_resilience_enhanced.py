"""Enhanced resilience tests for cloud provider failures - Task 3.7.1d.

This module provides comprehensive testing for cloud storage resilience including
failure scenarios, disaster recovery, network partitioning, and cascading failures.
"""
import pytest
import asyncio
import time
import random
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import tempfile
import shutil
import json
from datetime import datetime, timedelta
from uuid import uuid4

from emuses.tools.cloud_storage import S3StorageBackend, AzureBlobStorageBackend, GCSStorageBackend
from emuses.tools.cloud_model_registry import CloudModelRegistry
from emuses.multi_user_service.models import User, ModelRegistry


class TestCloudProviderFailureScenarios:
    """Test various cloud provider failure scenarios and recovery."""
    
    @pytest.fixture
    def resilient_storage_backend(self):
        """Create storage backend that simulates various failure modes."""
        backend = MagicMock(spec=S3StorageBackend)
        
        # Track failure scenarios
        backend._failure_state = {
            "network_failures": 0,
            "timeout_failures": 0, 
            "auth_failures": 0,
            "quota_failures": 0,
            "corruption_failures": 0,
            "total_calls": 0
        }
        
        async def simulate_failures(operation_type, *args, **kwargs):
            backend._failure_state["total_calls"] += 1
            call_count = backend._failure_state["total_calls"]
            
            # Simulate different failure patterns based on call count
            if call_count <= 3:
                # Network failures early on
                backend._failure_state["network_failures"] += 1
                raise ConnectionError("Network unreachable")
            elif call_count <= 5:
                # Timeout failures
                backend._failure_state["timeout_failures"] += 1
                raise TimeoutError("Operation timed out")
            elif call_count <= 6:
                # Authentication failure
                backend._failure_state["auth_failures"] += 1
                raise PermissionError("Authentication failed")
            elif call_count <= 7:
                # Quota exceeded
                backend._failure_state["quota_failures"] += 1
                raise Exception("Storage quota exceeded")
            elif call_count <= 8:
                # Data corruption
                backend._failure_state["corruption_failures"] += 1
                raise Exception("Data corruption detected")
            else:
                # Success after multiple failures
                await asyncio.sleep(0.01)  # Simulate successful operation delay
                if operation_type == "upload":
                    return f"s3://bucket/models/{args[1] if len(args) > 1 else 'test'}/model_bundle.tar.gz"
                elif operation_type == "signed_url":
                    return f"https://signed-url.example.com/{random.randint(1000, 9999)}"
                else:
                    return None
        
        # Assign failure simulation to operations
        async def upload_with_failures(*args, **kwargs):
            return await simulate_failures("upload", *args, **kwargs)
        
        async def download_with_failures(*args, **kwargs):
            return await simulate_failures("download", *args, **kwargs)
        
        async def delete_with_failures(*args, **kwargs):
            return await simulate_failures("delete", *args, **kwargs)
            
        async def signed_url_with_failures(*args, **kwargs):
            return await simulate_failures("signed_url", *args, **kwargs)
        
        backend.upload_model = upload_with_failures
        backend.download_model = download_with_failures
        backend.delete_model = delete_with_failures
        backend.generate_signed_url = signed_url_with_failures
        
        return backend
    
    @pytest.mark.asyncio
    async def test_retry_logic_with_exponential_backoff(self, resilient_storage_backend):
        """Test retry logic with exponential backoff for transient failures."""
        
        async def retry_with_backoff(operation, max_retries=5, base_delay=0.1):
            """Implement retry logic with exponential backoff."""
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await operation()
                except (ConnectionError, TimeoutError) as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                        await asyncio.sleep(min(delay, 2.0))  # Cap at 2 seconds for tests
                    continue
                except (PermissionError, Exception) as e:
                    # For test purposes, treat auth failures as transient too
                    # In production, you'd distinguish between transient and permanent failures
                    if "Authentication failed" in str(e) or "quota exceeded" in str(e).lower() or "corruption" in str(e).lower():
                        last_exception = e
                        if attempt < max_retries:
                            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                            await asyncio.sleep(min(delay, 2.0))
                            continue
                    # Other permanent errors should not be retried
                    raise
            
            raise last_exception
        
        # Test upload with retries
        start_time = time.time()
        
        try:
            result = await retry_with_backoff(
                lambda: resilient_storage_backend.upload_model(Path("/tmp/test"), str(uuid4()))
            )
            end_time = time.time()
            
            # Verify operation eventually succeeded
            assert result.startswith("s3://")
            
            # Verify retry attempts were made (should have taken time for retries)
            total_time = end_time - start_time
            assert total_time > 0.3  # At least some retry delay
            
            # Verify multiple failure types were encountered
            state = resilient_storage_backend._failure_state
            assert state["network_failures"] > 0
            assert state["timeout_failures"] > 0
            assert state["total_calls"] > 5  # Multiple attempts
            
            print(f"Retry test results:")
            print(f"  Total attempts: {state['total_calls']}")
            print(f"  Network failures: {state['network_failures']}")
            print(f"  Timeout failures: {state['timeout_failures']}")
            print(f"  Total time: {total_time:.3f}s")
            
        except Exception as e:
            pytest.fail(f"Retry logic failed: {e}")
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_pattern(self):
        """Test circuit breaker pattern to prevent cascading failures."""
        
        class CircuitBreaker:
            def __init__(self, failure_threshold=5, recovery_timeout=1.0):
                self.failure_threshold = failure_threshold
                self.recovery_timeout = recovery_timeout
                self.failure_count = 0
                self.last_failure_time = None
                self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
            
            async def call(self, operation):
                if self.state == "OPEN":
                    if time.time() - self.last_failure_time > self.recovery_timeout:
                        self.state = "HALF_OPEN"
                    else:
                        raise Exception("Circuit breaker OPEN")
                
                try:
                    result = await operation()
                    if self.state == "HALF_OPEN":
                        self.state = "CLOSED"
                        self.failure_count = 0
                    return result
                except Exception as e:
                    self.failure_count += 1
                    self.last_failure_time = time.time()
                    
                    if self.failure_count >= self.failure_threshold:
                        self.state = "OPEN"
                    
                    raise
        
        # Create failing backend
        failing_backend = MagicMock(spec=S3StorageBackend)
        call_count = 0
        
        async def always_fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 10:  # Fail for first 10 calls
                raise ConnectionError("Service unavailable")
            else:
                return "s3://bucket/success"
        
        failing_backend.upload_model = always_fail
        
        # Test circuit breaker
        circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
        
        # Phase 1: Circuit should close after threshold
        failures = 0
        for i in range(5):
            try:
                await circuit_breaker.call(
                    lambda: failing_backend.upload_model(Path("/tmp/test"), f"model-{i}")
                )
            except Exception:
                failures += 1
        
        assert circuit_breaker.state == "OPEN"
        assert failures >= 3
        
        # Phase 2: Circuit should remain open
        with pytest.raises(Exception, match="Circuit breaker OPEN"):
            await circuit_breaker.call(
                lambda: failing_backend.upload_model(Path("/tmp/test"), "blocked")
            )
        
        # Phase 3: After recovery timeout, should try half-open
        await asyncio.sleep(0.15)  # Wait for recovery timeout
        
        # This should still fail but move to half-open
        try:
            await circuit_breaker.call(
                lambda: failing_backend.upload_model(Path("/tmp/test"), "half-open-test")
            )
        except Exception:
            pass
        
        print(f"Circuit breaker test results:")
        print(f"  Final state: {circuit_breaker.state}")
        print(f"  Total failures: {circuit_breaker.failure_count}")
        print(f"  Backend calls: {call_count}")
        
        # Verify circuit breaker behavior
        assert circuit_breaker.failure_count > 0
        assert call_count < 15  # Circuit breaker should have prevented some calls
    
    @pytest.mark.asyncio
    async def test_multi_provider_failover(self):
        """Test failover between multiple cloud providers."""
        
        # Create primary and backup providers with different failure patterns
        primary = MagicMock(spec=S3StorageBackend)
        backup = MagicMock(spec=AzureBlobStorageBackend)
        tertiary = MagicMock(spec=GCSStorageBackend)
        
        # Primary always fails
        primary.upload_model = AsyncMock(side_effect=ConnectionError("Primary unavailable"))
        
        # Backup fails first few times, then succeeds
        backup_calls = 0
        async def backup_upload(*args, **kwargs):
            nonlocal backup_calls
            backup_calls += 1
            if backup_calls <= 2:
                raise TimeoutError("Backup timeout")
            return f"azure://container/models/{args[1]}/model_bundle.tar.gz"
        
        backup.upload_model = backup_upload
        
        # Tertiary always succeeds
        tertiary.upload_model = AsyncMock(
            return_value=lambda args: f"gs://bucket/models/{args[1]}/model_bundle.tar.gz"
        )
        
        # Implement failover logic
        providers = [
            ("primary", primary),
            ("backup", backup),
            ("tertiary", tertiary)
        ]
        
        async def upload_with_failover(model_path, model_id):
            last_error = None
            
            for provider_name, provider in providers:
                try:
                    print(f"Attempting upload with {provider_name} provider")
                    result = await provider.upload_model(model_path, model_id)
                    print(f"Success with {provider_name} provider")
                    return result, provider_name
                except Exception as e:
                    print(f"{provider_name} provider failed: {e}")
                    last_error = e
                    continue
            
            raise Exception(f"All providers failed. Last error: {last_error}")
        
        # Test failover
        result, used_provider = await upload_with_failover(Path("/tmp/test"), str(uuid4()))
        
        # Verify failover worked
        assert result.startswith("azure://")  # Should have used backup
        assert used_provider == "backup"
        assert backup_calls > 2  # Should have retried backup
        
        # Verify primary was attempted
        primary.upload_model.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_partial_failure_recovery(self):
        """Test recovery from partial failures during multi-part operations."""
        
        class PartialFailureBackend:
            def __init__(self):
                self.upload_attempts = {}
                self.failure_rate = 0.3  # 30% of operations fail
            
            async def upload_model(self, model_path, model_id):
                # Track attempts for this model
                if model_id not in self.upload_attempts:
                    self.upload_attempts[model_id] = 0
                
                self.upload_attempts[model_id] += 1
                
                # Simulate partial failure based on attempt number
                if self.upload_attempts[model_id] <= 2 and random.random() < self.failure_rate:
                    raise ConnectionError(f"Partial failure for {model_id}")
                
                return f"s3://bucket/models/{model_id}/model_bundle.tar.gz"
            
            async def download_model(self, storage_url, local_path):
                # Extract model_id from URL
                model_id = storage_url.split("/")[-2]
                
                if random.random() < self.failure_rate / 2:  # Lower failure rate for downloads
                    raise TimeoutError(f"Download timeout for {model_id}")
        
        backend = PartialFailureBackend()
        
        # Test multiple operations with partial failures
        models_to_process = [str(uuid4()) for _ in range(10)]
        
        async def robust_upload(model_id, max_retries=3):
            for attempt in range(max_retries):
                try:
                    return await backend.upload_model(Path(f"/tmp/{model_id}"), model_id)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff
        
        # Process models with retry logic
        start_time = time.time()
        results = await asyncio.gather(
            *[robust_upload(model_id) for model_id in models_to_process],
            return_exceptions=True
        )
        end_time = time.time()
        
        # Analyze results
        successful = sum(1 for r in results if isinstance(r, str) and r.startswith("s3://"))
        failed = sum(1 for r in results if isinstance(r, Exception))
        
        print(f"Partial failure recovery results:")
        print(f"  Total models: {len(models_to_process)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Success rate: {successful/len(models_to_process)*100:.1f}%")
        print(f"  Total time: {end_time - start_time:.3f}s")
        
        # Verify recovery effectiveness
        assert successful >= len(models_to_process) * 0.7  # At least 70% should succeed with retries
        assert successful > 0  # At least some should succeed
    
    @pytest.mark.asyncio
    async def test_network_partition_simulation(self):
        """Test behavior during network partitions and connectivity issues."""
        
        class NetworkPartitionBackend:
            def __init__(self):
                self.partition_active = False
                self.partition_start = None
                self.partition_duration = 2.0  # 2 second partition
                
            async def simulate_partition(self, duration=2.0):
                self.partition_active = True
                self.partition_start = time.time()
                self.partition_duration = duration
                
            async def upload_model(self, model_path, model_id):
                if self.partition_active:
                    if time.time() - self.partition_start < self.partition_duration:
                        raise ConnectionError("Network partition - no route to host")
                    else:
                        self.partition_active = False
                
                # Simulate normal operation
                await asyncio.sleep(0.1)
                return f"s3://bucket/models/{model_id}/model_bundle.tar.gz"
        
        backend = NetworkPartitionBackend()
        
        # Start network partition
        await backend.simulate_partition(1.0)  # 1 second partition
        
        async def upload_with_partition_handling(model_id):
            max_wait = 3.0  # Max time to wait for partition recovery
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                try:
                    return await backend.upload_model(Path("/tmp/test"), model_id)
                except ConnectionError as e:
                    if "partition" in str(e):
                        # Wait for partition to clear
                        await asyncio.sleep(0.2)
                        continue
                    else:
                        raise
            
            raise TimeoutError("Network partition lasted too long")
        
        # Test upload during partition
        start_time = time.time()
        result = await upload_with_partition_handling(str(uuid4()))
        end_time = time.time()
        
        # Verify operation succeeded after partition cleared
        assert result.startswith("s3://")
        
        # Verify operation took time to recover from partition
        total_time = end_time - start_time
        assert total_time > 1.0  # Should have taken at least 1 second (partition duration)
        assert total_time < 3.0  # But not too long
        
        print(f"Network partition recovery time: {total_time:.3f}s")


class TestCloudStorageDataIntegrityResilience:
    """Test data integrity and consistency during failures."""
    
    @pytest.mark.asyncio
    async def test_data_corruption_detection_and_recovery(self):
        """Test detection and recovery from data corruption scenarios."""
        
        class CorruptionSimulatorBackend:
            def __init__(self):
                self.corruption_rate = 0.2  # 20% corruption rate
                self.checksums = {}
            
            async def upload_model(self, model_path, model_id):
                # Simulate checksum calculation
                import hashlib
                content = f"model-{model_id}-content"
                checksum = hashlib.md5(content.encode()).hexdigest()
                self.checksums[model_id] = checksum
                
                # Simulate corruption during upload
                if random.random() < self.corruption_rate:
                    raise Exception(f"Data corruption detected during upload: checksum mismatch")
                
                return f"s3://bucket/models/{model_id}/model_bundle.tar.gz"
            
            async def download_model(self, storage_url, local_path):
                # Extract model_id from URL
                model_id = storage_url.split("/")[-2]
                
                # Simulate corruption detection during download
                if random.random() < self.corruption_rate:
                    raise Exception(f"Downloaded data corrupted: checksum verification failed")
            
            async def verify_integrity(self, model_id):
                # Simulate integrity verification
                return model_id in self.checksums
        
        backend = CorruptionSimulatorBackend()
        
        async def reliable_upload_with_verification(model_id, max_retries=3):
            """Upload with integrity verification and retry on corruption."""
            for attempt in range(max_retries):
                try:
                    # Attempt upload
                    result = await backend.upload_model(Path(f"/tmp/{model_id}"), model_id)
                    
                    # Verify integrity
                    if await backend.verify_integrity(model_id):
                        return result
                    else:
                        raise Exception("Integrity verification failed")
                        
                except Exception as e:
                    if "corruption" in str(e).lower() and attempt < max_retries - 1:
                        print(f"Corruption detected on attempt {attempt + 1}, retrying...")
                        await asyncio.sleep(0.1)
                        continue
                    else:
                        raise
        
        # Test multiple uploads with corruption resilience
        test_models = [str(uuid4()) for _ in range(20)]
        
        results = await asyncio.gather(
            *[reliable_upload_with_verification(model_id) for model_id in test_models],
            return_exceptions=True
        )
        
        # Analyze integrity results
        successful = sum(1 for r in results if isinstance(r, str) and r.startswith("s3://"))
        corrupted = sum(1 for r in results if isinstance(r, Exception) and "corruption" in str(r))
        
        print(f"Data integrity resilience results:")
        print(f"  Total uploads: {len(test_models)}")
        print(f"  Successful: {successful}")
        print(f"  Corruption failures: {corrupted}")
        print(f"  Success rate: {successful/len(test_models)*100:.1f}%")
        
        # Verify corruption handling
        assert successful > 0  # Some should succeed despite corruption
        assert successful >= len(test_models) * 0.5  # At least 50% should succeed with retries
    
    @pytest.mark.asyncio
    async def test_atomic_operations_during_failures(self):
        """Test atomicity of operations during various failure scenarios."""
        
        class AtomicOperationBackend:
            def __init__(self):
                self.operations = {}  # Track operation states
                self.failure_during_commit = 0.3  # 30% chance of failure during commit
            
            async def begin_transaction(self, transaction_id):
                self.operations[transaction_id] = {"state": "STARTED", "operations": []}
            
            async def add_operation(self, transaction_id, operation):
                if transaction_id in self.operations:
                    self.operations[transaction_id]["operations"].append(operation)
            
            async def commit_transaction(self, transaction_id):
                if transaction_id not in self.operations:
                    raise Exception("Transaction not found")
                
                # Simulate failure during commit
                if random.random() < self.failure_during_commit:
                    self.operations[transaction_id]["state"] = "FAILED"
                    raise Exception("Transaction commit failed")
                
                self.operations[transaction_id]["state"] = "COMMITTED"
                return True
            
            async def rollback_transaction(self, transaction_id):
                if transaction_id in self.operations:
                    self.operations[transaction_id]["state"] = "ROLLED_BACK"
            
            async def upload_model_atomically(self, model_path, model_id):
                transaction_id = str(uuid4())
                
                try:
                    await self.begin_transaction(transaction_id)
                    await self.add_operation(transaction_id, f"upload:{model_id}")
                    await self.add_operation(transaction_id, f"metadata:{model_id}")
                    await self.commit_transaction(transaction_id)
                    
                    return f"s3://bucket/models/{model_id}/model_bundle.tar.gz"
                
                except Exception as e:
                    await self.rollback_transaction(transaction_id)
                    raise
        
        backend = AtomicOperationBackend()
        
        # Test atomic operations with failure handling
        test_models = [str(uuid4()) for _ in range(15)]
        
        async def safe_atomic_upload(model_id):
            try:
                return await backend.upload_model_atomically(Path(f"/tmp/{model_id}"), model_id)
            except Exception as e:
                return e
        
        results = await asyncio.gather(*[safe_atomic_upload(model_id) for model_id in test_models])
        
        # Analyze atomic operation results
        successful = sum(1 for r in results if isinstance(r, str))
        failed = sum(1 for r in results if isinstance(r, Exception))
        
        # Check transaction states
        committed = sum(1 for op in backend.operations.values() if op["state"] == "COMMITTED")
        rolled_back = sum(1 for op in backend.operations.values() if op["state"] == "ROLLED_BACK")
        
        print(f"Atomic operations resilience results:")
        print(f"  Total operations: {len(test_models)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Committed transactions: {committed}")
        print(f"  Rolled back transactions: {rolled_back}")
        
        # Verify atomic behavior
        assert committed == successful  # All successful operations should be committed
        assert rolled_back == failed    # All failed operations should be rolled back
        assert committed + rolled_back == len(test_models)  # All operations accounted for
        
        # No operations should be in intermediate state during failures
        intermediate_states = sum(1 for op in backend.operations.values() 
                                if op["state"] not in ["COMMITTED", "ROLLED_BACK"])
        assert intermediate_states == 0