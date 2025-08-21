"""Tests for enhanced registry schema with atomic operations."""

import json
import pytest
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch
from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from emuses.tools.local_model_registry import LocalModelRegistry, TransactionState, RegistryOperation, RegistryTransaction


class TestAtomicTransactionFramework:
    """Test atomic transaction framework for registry operations."""
    
    @pytest.fixture
    def temp_registry(self, tmp_path):
        """Create a temporary registry for testing."""
        registry_path = tmp_path / "test_registry"
        return LocalModelRegistry(registry_path)
    
    @pytest.fixture
    def sample_model_dir(self, tmp_path):
        """Create a sample model directory for testing."""
        model_dir = tmp_path / "sample_model"
        model_dir.mkdir()
        
        # Create manifest
        manifest = {
            "name": "test_model",
            "version": "1.0.0",
            "model_type": "complete_emuses_model",
            "description": "Test model for atomic operations"
        }
        with open(model_dir / "manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)
        
        # Create model components
        (model_dir / "umap_model.pkl").touch()
        (model_dir / "hdbscan_model.pkl").touch()
        
        pred_dir = model_dir / "prediction_ensemble"
        pred_dir.mkdir()
        (pred_dir / "model_1.pkl").touch()
        (pred_dir / "model_2.pkl").touch()
        
        return model_dir
    
    def test_begin_transaction_creates_transaction(self, temp_registry):
        """Test that begin_transaction creates a valid transaction object."""
        transaction = temp_registry.begin_transaction()
        
        assert isinstance(transaction, RegistryTransaction)
        assert transaction.transaction_id is not None
        assert len(transaction.transaction_id) > 0
        assert transaction.state == TransactionState.PENDING
        assert isinstance(transaction.operations, list)
        assert len(transaction.operations) == 0
        assert isinstance(transaction.rollback_data, dict)
    
    def test_transaction_id_uniqueness(self, temp_registry):
        """Test that each transaction gets a unique ID."""
        transaction1 = temp_registry.begin_transaction()
        transaction2 = temp_registry.begin_transaction()
        
        assert transaction1.transaction_id != transaction2.transaction_id
    
    def test_install_model_with_transaction_success(self, temp_registry, sample_model_dir):
        """Test successful model installation within a transaction."""
        transaction = temp_registry.begin_transaction()
        
        # Install model within transaction
        result = temp_registry.install_model(
            sample_model_dir, 
            name="transactional_test",
            transaction=transaction
        )
        
        assert result["status"] == "success"
        
        # Model should not be visible until transaction is committed
        models_before_commit = temp_registry.list_models()
        model_ids_before = [m["model_id"] for m in models_before_commit]
        assert result["model_id"] not in model_ids_before
        
        # Commit transaction
        commit_success = temp_registry.commit_transaction(transaction)
        assert commit_success is True
        assert transaction.state == TransactionState.COMMITTED
        
        # Model should now be visible
        models_after_commit = temp_registry.list_models()
        model_ids_after = [m["model_id"] for m in models_after_commit]
        assert result["model_id"] in model_ids_after
    
    def test_install_model_with_transaction_rollback(self, temp_registry, sample_model_dir):
        """Test model installation rollback on transaction failure."""
        transaction = temp_registry.begin_transaction()
        
        # Install model within transaction
        result = temp_registry.install_model(
            sample_model_dir,
            name="rollback_test", 
            transaction=transaction
        )
        
        assert result["status"] == "success"
        model_id = result["model_id"]
        
        # Verify model files were created
        model_path = temp_registry.models_path / model_id
        assert model_path.exists()
        
        # Rollback transaction
        rollback_success = temp_registry.rollback_transaction(transaction)
        assert rollback_success is True
        assert transaction.state == TransactionState.ROLLED_BACK
        
        # Model should be removed from filesystem
        assert not model_path.exists()
        
        # Model should not be in registry
        models = temp_registry.list_models()
        model_ids = [m["model_id"] for m in models]
        assert model_id not in model_ids
    
    def test_backward_compatibility_without_transaction(self, temp_registry, sample_model_dir):
        """Test that install_model still works without transaction parameter."""
        # Install model without transaction (backward compatibility)
        result = temp_registry.install_model(sample_model_dir, model_name="compat_test")
        
        assert result["status"] == "success"
        
        # Model should be immediately visible (no transaction)
        models = temp_registry.list_models()
        model_ids = [m["model_id"] for m in models]
        assert result["model_id"] in model_ids
    
    def test_transaction_rollback_on_filesystem_error(self, temp_registry, sample_model_dir):
        """Test automatic rollback when filesystem operations fail."""
        transaction = temp_registry.begin_transaction()
        
        # Mock filesystem error during model installation
        with patch('shutil.copytree', side_effect=OSError("Simulated filesystem error")):
            result = temp_registry.install_model(
                sample_model_dir,
                name="error_test",
                transaction=transaction
            )
            
            assert result["status"] == "error"
            assert "filesystem error" in result["message"].lower()
        
        # Transaction should be automatically rolled back
        assert transaction.state == TransactionState.ROLLED_BACK
        
        # No partial files should remain
        error_files = list(temp_registry.models_path.glob("*error_test*"))
        assert len(error_files) == 0
    
    def test_transaction_rollback_on_index_corruption(self, temp_registry, sample_model_dir):
        """Test rollback when registry index update fails."""
        transaction = temp_registry.begin_transaction()
        
        # Install model successfully first
        result = temp_registry.install_model(
            sample_model_dir,
            name="index_error_test",
            transaction=transaction
        )
        assert result["status"] == "success"
        
        # Mock index save error during commit
        with patch.object(temp_registry, '_save_index', side_effect=OSError("Index write error")):
            commit_success = temp_registry.commit_transaction(transaction)
            assert commit_success is False
        
        # Transaction should be rolled back
        assert transaction.state == TransactionState.ROLLED_BACK
        
        # Model files should be cleaned up
        model_path = temp_registry.models_path / result["model_id"]
        assert not model_path.exists()
    
    def test_concurrent_transaction_safety(self, temp_registry, sample_model_dir):
        """Test that concurrent transactions don't interfere with each other."""
        transaction1 = temp_registry.begin_transaction()
        transaction2 = temp_registry.begin_transaction()
        
        # Install different models in separate transactions
        result1 = temp_registry.install_model(
            sample_model_dir,
            name="concurrent_test_1",
            transaction=transaction1
        )
        
        result2 = temp_registry.install_model(
            sample_model_dir,
            name="concurrent_test_2", 
            transaction=transaction2
        )
        
        assert result1["status"] == "success"
        assert result2["status"] == "success"
        
        # Commit first transaction, rollback second
        commit1 = temp_registry.commit_transaction(transaction1)
        rollback2 = temp_registry.rollback_transaction(transaction2)
        
        assert commit1 is True
        assert rollback2 is True
        
        # Only first model should remain
        models = temp_registry.list_models()
        model_ids = [m["model_id"] for m in models]
        assert result1["model_id"] in model_ids
        assert result2["model_id"] not in model_ids
    
    def test_multiple_operations_in_single_transaction(self, temp_registry, tmp_path):
        """Test multiple model operations within a single transaction."""
        transaction = temp_registry.begin_transaction()
        
        # Create multiple test models
        models = []
        for i in range(3):
            model_dir = tmp_path / f"multi_model_{i}"
            model_dir.mkdir()
            
            manifest = {
                "name": f"multi_test_{i}",
                "version": "1.0.0",
                "model_type": "umap_model", 
                "description": f"Multi-op test model {i}"
            }
            with open(model_dir / "manifest.json", 'w') as f:
                json.dump(manifest, f)
            
            (model_dir / "umap_model.pkl").touch()
            models.append(model_dir)
        
        # Install all models in the same transaction
        results = []
        for i, model_dir in enumerate(models):
            result = temp_registry.install_model(
                model_dir,
                name=f"multi_op_test_{i}",
                transaction=transaction
            )
            assert result["status"] == "success"
            results.append(result)
        
        # All models should be pending (not visible)
        models_list = temp_registry.list_models()
        assert len(models_list) == 0
        
        # Commit transaction
        commit_success = temp_registry.commit_transaction(transaction)
        assert commit_success is True
        
        # All models should now be visible
        models_list = temp_registry.list_models()
        assert len(models_list) == 3
        
        installed_ids = [m["model_id"] for m in models_list]
        for result in results:
            assert result["model_id"] in installed_ids