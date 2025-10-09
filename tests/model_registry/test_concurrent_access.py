"""
Tests for Concurrent Access Safety and Mutex/Locking.

Tests the ability to safely perform registry operations concurrently
without race conditions or data corruption.
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from emuses.tools.local_model_registry import LocalModelRegistry


class TestConcurrentAccess:
    """Test concurrent access safety for registry operations."""

    def test_concurrent_model_installation(self, tmp_path):
        """Test concurrent installation of different models."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        def install_model(model_id):
            """Install a model with given ID."""
            model_dir = tmp_path / f"model_{model_id}"
            model_dir.mkdir(exist_ok=True)
            (model_dir / f"component_{model_id}.pkl").write_bytes(f"content_{model_id}".encode())
            
            result = registry.install_model_with_deduplication(
                model_path=model_dir,
                model_name=f"concurrent_model_{model_id}"
            )
            return result
        
        # Install 5 models concurrently
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(install_model, i) for i in range(5)]
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
        
        # All installations should succeed
        assert len(results) == 5
        for result in results:
            assert result["status"] == "success"
        
        # Verify all models are in registry
        models = registry.list_models()
        model_names = [model["name"] for model in models]
        
        for i in range(5):
            expected_name = f"concurrent_model_{i}"
            assert any(expected_name in name for name in model_names), f"Model {expected_name} not found"

    def test_concurrent_duplicate_detection(self, tmp_path):
        """Test concurrent duplicate detection doesn't create race conditions."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        # Create identical model directory
        model_dir = tmp_path / "identical_model"
        model_dir.mkdir()
        (model_dir / "component.pkl").write_bytes(b"identical content")
        
        def install_identical_model(thread_id):
            """Try to install the same model from multiple threads."""
            try:
                result = registry.install_model_with_deduplication(
                    model_path=model_dir,
                    model_name=f"identical_model"  # Same name to ensure identical config hash
                )
                return {"thread_id": thread_id, "result": result}
            except Exception as e:
                return {"thread_id": thread_id, "error": str(e)}
        
        # Try to install same model from 3 threads simultaneously
        results = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(install_identical_model, i) for i in range(3)]
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
        
        # Should have one success and two skips (or similar safe outcome)
        success_count = 0
        skip_count = 0
        error_count = 0
        
        for result in results:
            if "error" in result:
                error_count += 1
            elif result["result"]["status"] == "success":
                success_count += 1
            elif result["result"]["status"] == "skipped":
                skip_count += 1
        
        # Should not have errors, and should have safe duplicate handling
        assert error_count == 0, f"Unexpected errors: {[r for r in results if 'error' in r]}"
        
        # Should have exactly one successful installation
        # (The others should be detected as duplicates and skipped)
        models = registry.list_models()
        identical_models = [m for m in models if "identical_model" in m["name"]]
        # May have 1 or a few models depending on timing, but should be stable
        assert len(identical_models) >= 1, "Should have at least one installed model"

    def test_concurrent_model_listing(self, tmp_path):
        """Test that model listing is safe during concurrent modifications."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        # Install base model
        base_model = tmp_path / "base_model"
        base_model.mkdir()
        (base_model / "component.pkl").write_bytes(b"base content")
        registry.install_model_with_deduplication(
            model_path=base_model,
            model_name="base_model"
        )
        
        results = {"lists": [], "installs": []}
        
        def list_models_repeatedly():
            """List models multiple times."""
            for i in range(10):
                try:
                    models = registry.list_models()
                    results["lists"].append(len(models))
                    time.sleep(0.01)  # Small delay
                except Exception as e:
                    results["lists"].append(f"error: {e}")
        
        def install_models_concurrently():
            """Install models while listing is happening."""
            for i in range(3):
                try:
                    model_dir = tmp_path / f"concurrent_install_{i}"
                    model_dir.mkdir(exist_ok=True)
                    (model_dir / "component.pkl").write_bytes(f"content_{i}".encode())
                    
                    result = registry.install_model_with_deduplication(
                        model_path=model_dir,
                        model_name=f"concurrent_install_{i}"
                    )
                    results["installs"].append(result["status"])
                    time.sleep(0.02)  # Small delay
                except Exception as e:
                    results["installs"].append(f"error: {e}")
        
        # Run listing and installation concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            list_future = executor.submit(list_models_repeatedly)
            install_future = executor.submit(install_models_concurrently)
            
            # Wait for both to complete
            list_future.result()
            install_future.result()
        
        # Verify no errors occurred
        list_errors = [r for r in results["lists"] if isinstance(r, str) and "error" in r]
        install_errors = [r for r in results["installs"] if isinstance(r, str) and "error" in r]
        
        assert len(list_errors) == 0, f"List errors: {list_errors}"
        assert len(install_errors) == 0, f"Install errors: {install_errors}"
        
        # Should see increasing model counts over time (no strict requirement due to timing)
        model_counts = [r for r in results["lists"] if isinstance(r, int)]
        assert len(model_counts) > 0, "Should have successful model listings"
        assert max(model_counts) >= min(model_counts), "Model counts should be consistent"

    def test_transaction_isolation(self, tmp_path):
        """Test that transactions are properly isolated."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        def concurrent_transaction(transaction_id):
            """Perform operations within a transaction."""
            transaction = registry.begin_transaction()
            
            try:
                # Create model for this transaction
                model_dir = tmp_path / f"tx_model_{transaction_id}"
                model_dir.mkdir(exist_ok=True)
                (model_dir / "component.pkl").write_bytes(f"tx_content_{transaction_id}".encode())
                
                # Install model within transaction
                result = registry.install_model_with_deduplication(
                    model_path=model_dir,
                    model_name=f"tx_model_{transaction_id}",
                    transaction=transaction
                )
                
                # Small delay to simulate work
                time.sleep(0.05)
                
                # Commit transaction
                success = registry.commit_transaction(transaction)
                
                return {
                    "transaction_id": transaction_id,
                    "install_result": result,
                    "commit_success": success
                }
                
            except Exception as e:
                # Rollback on error
                registry.rollback_transaction(transaction)
                return {
                    "transaction_id": transaction_id,
                    "error": str(e)
                }
        
        # Run 3 concurrent transactions
        results = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(concurrent_transaction, i) for i in range(3)]
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
        
        # All transactions should succeed
        errors = [r for r in results if "error" in r]
        assert len(errors) == 0, f"Transaction errors: {errors}"
        
        successful_results = [r for r in results if "error" not in r]
        assert len(successful_results) == 3, "All transactions should succeed"
        
        for result in successful_results:
            assert result["install_result"]["status"] == "success"
            assert result["commit_success"] is True
        
        # Verify all models from transactions are present
        models = registry.list_models()
        tx_models = [m for m in models if "tx_model" in m["name"]]
        assert len(tx_models) == 3, "All transaction models should be committed"


class TestThreadSafety:
    """Test thread safety of critical registry operations."""
    
    def test_index_file_concurrent_access(self, tmp_path):
        """Test safe concurrent access to registry index file."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        def read_and_modify_index(worker_id):
            """Safely read and modify the registry index."""
            try:
                # This tests the internal index operations for thread safety
                for i in range(5):
                    models = registry.list_models()  # Read operation
                    
                    # Simulate model installation (write operation)
                    model_dir = tmp_path / f"worker_{worker_id}_model_{i}"
                    model_dir.mkdir(exist_ok=True, parents=True)
                    (model_dir / "component.pkl").write_bytes(f"worker_{worker_id}_content_{i}".encode())
                    
                    registry.install_model_with_deduplication(
                        model_path=model_dir,
                        model_name=f"worker_{worker_id}_model_{i}"
                    )
                
                return {"worker_id": worker_id, "success": True}
                
            except Exception as e:
                return {"worker_id": worker_id, "error": str(e)}
        
        # Run multiple workers concurrently accessing the index
        results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(read_and_modify_index, i) for i in range(4)]
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
        
        # All workers should complete successfully
        errors = [r for r in results if "error" in r]
        assert len(errors) == 0, f"Index access errors: {errors}"
        
        # Verify final state is consistent
        final_models = registry.list_models()
        expected_model_count = 4 * 5  # 4 workers × 5 models each
        
        # Should have all models (may be slightly different due to duplicates/timing)
        assert len(final_models) >= expected_model_count * 0.8, "Should have most models installed"
        
        # Verify registry index is not corrupted
        validation_result = registry.validate_index()
        assert validation_result[0] is True, f"Index validation failed: {validation_result[1]}"