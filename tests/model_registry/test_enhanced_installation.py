"""
Tests for Enhanced Installation Workflow with Deduplication Integration.

Tests the integration of deduplication engine with LocalModelRegistry.install_model()
to provide seamless duplicate detection and resolution during model installation.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch
from dataclasses import dataclass

from emuses.tools.model_io import CompleteModelValidation
from emuses.tools.local_model_registry import (
    LocalModelRegistry,
    DuplicateResolutionMode,
    InstallationOptions
)


@dataclass
class DuplicateMatch:
    """Represents a potential duplicate model match."""
    model_id: str
    similarity_score: float
    match_type: str  # 'configuration', 'content', 'performance'
    existing_model_info: dict


class TestEnhancedInstallationWorkflow:
    """Test enhanced installation workflow with deduplication integration."""

    def test_install_model_with_deduplication_check(self, tmp_path):
        """Test that install_model() automatically checks for duplicates and handles them."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        # Create test model directory with manifest
        model_dir = tmp_path / "test_model"
        model_dir.mkdir()

        manifest = {
            "name": "test_model",
            "version": "1.0.0",
            "model_type": "complete_emuses_model",
            "description": "Test model for deduplication"
        }
        (model_dir / "manifest.json").write_text(json.dumps(manifest))

        # Create validation result that should trigger duplicate detection
        validation_result = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="test_config_hash_123",
            content_hash="test_content_hash_abc",
            components_found={"umap": model_dir / "umap.pkl", "hdbscan": model_dir / "hdbscan.pkl"},
            missing_components=[],
            validation_errors=[],
            name="test_model",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test model for deduplication"
        )

        # Mock the ModelIOManager to return our test validation
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = validation_result
            mock_instance.install_model.return_value = "test_model_123"
            mock_modelio.return_value = mock_instance

            # Enhanced install should include deduplication detection
            options = InstallationOptions(duplicate_resolution=DuplicateResolutionMode.SKIP)
            result = registry.install_model_with_deduplication(
                model_path=model_dir,
                options=options
            )

            # Should succeed with duplicate check results
            assert result["status"] == "success"
            assert "duplicate_check" in result
            assert "duplicates_found" in result["duplicate_check"]

    def test_install_model_detects_configuration_duplicates(self, tmp_path):
        """Test that installation detects and reports configuration-based duplicates."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        # First, install a model to create a duplicate target
        existing_model_dir = tmp_path / "existing_model"
        existing_model_dir.mkdir()

        existing_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="duplicate_config_hash",
            content_hash="existing_content_hash",
            components_found={"umap": existing_model_dir / "umap.pkl"},
            missing_components=[],
            validation_errors=[],
            name="existing_model",
            version="1.0.0",
            type="complete_emuses_model",
            description="Existing model"
        )

        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = existing_validation
            mock_instance.install_model.return_value = "existing_model_123"
            mock_modelio.return_value = mock_instance

            # Install the existing model first
            registry.install_model(existing_model_dir, model_name="existing_model")

        # Now try to install a new model with the same configuration hash
        new_model_dir = tmp_path / "new_model"
        new_model_dir.mkdir()

        new_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="duplicate_config_hash",  # Same as existing
            content_hash="new_content_hash",
            components_found={"umap": new_model_dir / "umap.pkl"},
            missing_components=[],
            validation_errors=[],
            name="new_model",
            version="1.0.0",
            type="complete_emuses_model",
            description="New model with duplicate config"
        )

        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = new_validation
            mock_instance.install_model.return_value = "new_model_456"
            mock_modelio.return_value = mock_instance

            # Enhanced install should detect the duplicate
            options = InstallationOptions(duplicate_resolution=DuplicateResolutionMode.SKIP)
            result = registry.install_model_with_deduplication(
                model_path=new_model_dir,
                options=options
            )

            # Should detect duplicate and skip installation
            assert result["status"] == "skipped"
            assert result["reason"] == "duplicate_detected"
            assert len(result["duplicate_check"]["duplicates_found"]) >= 1
            assert result["duplicate_check"]["duplicates_found"][0]["match_type"] == "configuration"

    def test_install_model_force_installation_despite_duplicates(self, tmp_path):
        """Test force installation when duplicates are detected."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        # Create a model to install despite duplicates
        model_dir = tmp_path / "force_model"
        model_dir.mkdir()

        validation_result = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="some_config_hash",
            content_hash="some_content_hash",
            components_found={"umap": model_dir / "umap.pkl"},
            missing_components=[],
            validation_errors=[],
            name="force_model",
            version="1.0.0",
            type="complete_emuses_model",
            description="Model to force install"
        )

        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = validation_result
            mock_instance.install_model.return_value = "force_model_789"
            mock_modelio.return_value = mock_instance

            # Force installation despite any duplicates
            options = InstallationOptions(
                duplicate_resolution=DuplicateResolutionMode.FORCE,
                force_unique_id=True
            )
            result = registry.install_model_with_deduplication(
                model_path=model_dir,
                options=options
            )

            # Should succeed with force installation
            assert result["status"] == "success"
            assert result.get("forced_installation") is True
            assert "model_id" in result

    def test_install_model_with_batch_duplicate_decisions(self, tmp_path):
        """Test batch mode duplicate handling for programmatic usage."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        # Create model for batch processing
        model_dir = tmp_path / "batch_model"
        model_dir.mkdir()

        validation_result = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="batch_config_hash",
            content_hash="batch_content_hash",
            components_found={"umap": model_dir / "umap.pkl"},
            missing_components=[],
            validation_errors=[],
            name="batch_model",
            version="1.0.0",
            type="complete_emuses_model",
            description="Model for batch testing"
        )

        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = validation_result
            mock_instance.install_model.return_value = "batch_model_abc"
            mock_modelio.return_value = mock_instance

            # Batch mode with predefined decisions
            batch_decisions = {
                "configuration_duplicates": "force",
                "content_duplicates": "skip",
                "performance_duplicates": "ask_user"
            }

            options = InstallationOptions(
                duplicate_resolution=DuplicateResolutionMode.BATCH,
                batch_decisions=batch_decisions
            )

            result = registry.install_model_with_deduplication(
                model_path=model_dir,
                options=options
            )

            # Should handle batch decisions appropriately
            assert result["status"] in ["success", "skipped", "pending_user_decision"]
            assert "batch_processing" in result

    def test_install_model_atomic_operations_with_deduplication(self, tmp_path):
        """Test that deduplication workflow uses atomic operations."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        model_dir = tmp_path / "atomic_model"
        model_dir.mkdir()

        validation_result = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="atomic_config_hash",
            content_hash="atomic_content_hash",
            components_found={"umap": model_dir / "umap.pkl"},
            missing_components=[],
            validation_errors=[],
            name="atomic_model",
            version="1.0.0",
            type="complete_emuses_model",
            description="Model for atomic testing"
        )

        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = validation_result
            mock_instance.install_model.return_value = "atomic_model_def"
            mock_modelio.return_value = mock_instance

            # Begin a transaction for atomic installation
            transaction = registry.begin_transaction()

            options = InstallationOptions(duplicate_resolution=DuplicateResolutionMode.FORCE)
            result = registry.install_model_with_deduplication(
                model_path=model_dir,
                options=options,
                transaction=transaction
            )

            # Should succeed but not be committed yet
            assert result["status"] == "success"
            assert "transaction_id" in result

            # Commit the transaction
            commit_success = registry.commit_transaction(transaction)
            assert commit_success is True


class TestBatchDuplicateHandling:
    """Test batch mode duplicate handling for API/programmatic usage."""

    def test_batch_duplicate_resolution_with_predefined_policies(self, tmp_path):
        """Test batch processing with predefined duplicate resolution policies."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        # First install an existing model to create duplicates
        existing_model_dir = tmp_path / "existing_batch_model"
        existing_model_dir.mkdir()
        
        existing_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="batch_config_hash",  # Same hash to trigger duplicate
            content_hash="batch_content_hash",
            components_found={"umap": existing_model_dir / "umap.pkl"},
            missing_components=[],
            validation_errors=[],
            name="existing_batch_model",
            version="1.0.0",
            type="complete_emuses_model",
            description="Existing model for batch testing"
        )
        
        # Install existing model first
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = existing_validation
            mock_instance.install_model.return_value = "existing_batch_model_123"
            mock_modelio.return_value = mock_instance
            
            registry.install_model(existing_model_dir)
        
        # Now install new model with same hash to trigger duplicates
        new_model_dir = tmp_path / "new_batch_model"
        new_model_dir.mkdir()
        
        validation_result = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="batch_config_hash",  # Same hash triggers duplicate
            content_hash="batch_content_hash",
            components_found={"umap": new_model_dir / "umap.pkl"},
            missing_components=[],
            validation_errors=[],
            name="batch_model",
            version="1.0.0",
            type="complete_emuses_model",
            description="Model for batch testing"
        )
        
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = validation_result
            mock_instance.install_model.return_value = "batch_model_123"
            mock_modelio.return_value = mock_instance
            
            # Define batch policies for different duplicate types
            batch_policies = {
                "configuration_duplicates": "skip",
                "content_duplicates": "force", 
                "performance_duplicates": "manual_review"
            }
            
            options = InstallationOptions(
                duplicate_resolution=DuplicateResolutionMode.BATCH,
                batch_policies=batch_policies
            )
            
            result = registry.install_model_with_batch_deduplication(
                model_path=new_model_dir,
                options=options
            )
            
            # Should execute batch policies without user interaction
            assert result["status"] in ["success", "skipped", "manual_review_required"]
            if "duplicate_check" in result and result["duplicate_check"]["has_duplicates"]:
                assert "batch_processing_log" in result
                assert "duplicate_decisions_applied" in result

    def test_batch_processing_multiple_models(self, tmp_path):
        """Test batch processing of multiple models with consistent policies."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        model_dirs = []
        for i in range(3):
            model_dir = tmp_path / f"batch_model_{i}"
            model_dir.mkdir()
            model_dirs.append(model_dir)
        
        batch_policies = {
            "configuration_hash_duplicates": "skip",
            "content_similarity_duplicates": "force",
            "performance_fingerprint_duplicates": "skip"
        }
        
        results = registry.batch_install_models_with_deduplication(
            model_paths=model_dirs,
            batch_policies=batch_policies
        )
        
        # Should process all models with consistent policy application
        assert len(results) == 3
        for result in results:
            assert "batch_policy_applied" in result
            assert result["status"] in ["success", "skipped"]

    def test_batch_mode_error_handling_and_partial_success(self, tmp_path):
        """Test batch mode handling of errors and partial success scenarios."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        # Create mix of valid and invalid model directories
        valid_model = tmp_path / "valid_batch_model"
        valid_model.mkdir()
        invalid_model = tmp_path / "invalid_batch_model"
        # Don't create invalid_model directory to simulate error
        
        batch_policies = {"all_duplicates": "skip"}
        
        results = registry.batch_install_models_with_deduplication(
            model_paths=[valid_model, invalid_model],
            batch_policies=batch_policies,
            continue_on_error=True
        )
        
        # Should handle errors gracefully in batch mode
        assert len(results) == 2
        assert any(r["status"] == "error" for r in results)
        assert any(r["status"] in ["success", "skipped"] for r in results)


class TestSemanticModelIdGeneration:
    """Test semantic model ID generation with meaningful versioning."""

    def test_generate_semantic_model_id_from_validation(self, tmp_path):
        """Test generation of meaningful model IDs from validation data."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        validation_result = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="semantic_config",
            content_hash="semantic_content",
            components_found={"umap": Path("model/umap.pkl"), "hdbscan": Path("model/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="hcp_analysis",
            version="2.1.0",
            type="complete_emuses_model",
            description="HCP analysis model with UMAP and HDBSCAN"
        )

        # Should generate semantic ID like: hcp_analysis_v2_1_0_semantic_config[:8]
        semantic_id = registry.generate_semantic_model_id(validation_result)

        assert semantic_id.startswith("hcp_analysis_v2_1_0")
        assert "semantic" in semantic_id or len(semantic_id.split('_')) >= 4
        assert len(semantic_id) <= 64  # Reasonable length limit

    def test_generate_unique_semantic_ids_for_duplicates(self, tmp_path):
        """Test that semantic IDs are made unique when duplicates exist."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        validation_result = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="duplicate_semantic",
            content_hash="duplicate_content",
            components_found={"umap": Path("model/umap.pkl")},
            missing_components=[],
            validation_errors=[],
            name="duplicate_test",
            version="1.0.0",
            type="complete_emuses_model",
            description="Duplicate semantic test"
        )

        # Generate multiple IDs - should be unique
        id1 = registry.generate_semantic_model_id(validation_result)
        id2 = registry.generate_semantic_model_id(validation_result, suffix_counter=2)

        assert id1 != id2
        assert id1.startswith("duplicate_test_v1_0_0")
        assert id2.startswith("duplicate_test_v1_0_0")

    def test_install_model_with_semantic_ids_integration(self, tmp_path):
        """Test that semantic IDs are used when installation option is enabled."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        model_dir = tmp_path / "semantic_integration_model"
        model_dir.mkdir()
        
        validation_result = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="semantic_integration_hash",
            content_hash="semantic_integration_content",
            components_found={"umap": model_dir / "umap.pkl"},
            missing_components=[],
            validation_errors=[],
            name="semantic_test",
            version="3.0.1",
            type="complete_emuses_model",
            description="Semantic ID integration test"
        )
        
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = validation_result
            
            # Mock install_model to verify semantic ID is passed
            mock_instance.install_model.return_value = "semantic_test_v3_0_1_semantic_"
            mock_modelio.return_value = mock_instance
            
            # Enable semantic IDs in installation options
            options = InstallationOptions(use_semantic_ids=True)
            
            result = registry.install_model_with_deduplication(
                model_path=model_dir,
                options=options
            )
            
            # Verify semantic ID was generated and passed to install_model
            mock_instance.install_model.assert_called_once()
            call_args = mock_instance.install_model.call_args
            
            # Should have been called with name parameter containing semantic ID
            assert 'name' in call_args.kwargs
            semantic_name = call_args.kwargs['name']
            assert semantic_name.startswith("semantic_test_v3_0_1")
            assert "semantic_" in semantic_name
            
            # Result should contain the semantic model ID
            assert result["status"] == "success"
            assert "semantic_test_v3_0_1" in result["model_id"]


class TestInteractiveDuplicateResolution:
    """Test interactive CLI duplicate resolution functionality."""

    def test_interactive_duplicate_resolution_prompt_user(self, tmp_path):
        """Test that interactive mode prompts user for duplicate resolution decisions."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        # Install an existing model first
        existing_model_dir = tmp_path / "existing_model"
        existing_model_dir.mkdir()
        
        existing_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="interactive_test_hash",
            content_hash="existing_content_hash",
            components_found={"umap": existing_model_dir / "umap.pkl"},
            missing_components=[],
            validation_errors=[],
            name="existing_model",
            version="1.0.0",
            type="complete_emuses_model",
            description="Existing model for interactive test"
        )
        
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = existing_validation
            mock_instance.install_model.return_value = "existing_model_123"
            mock_modelio.return_value = mock_instance
            
            # Install existing model
            registry.install_model(existing_model_dir, model_name="existing_model")
        
        # Now try to install a duplicate with interactive resolution
        new_model_dir = tmp_path / "new_model"
        new_model_dir.mkdir()
        
        new_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="interactive_test_hash",  # Same hash - duplicate
            content_hash="new_content_hash",
            components_found={"umap": new_model_dir / "umap.pkl"},
            missing_components=[],
            validation_errors=[],
            name="new_model",
            version="1.0.0",
            type="complete_emuses_model",
            description="New model with duplicate config"
        )
        
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = new_validation
            mock_instance.install_model.return_value = "new_model_456"
            mock_modelio.return_value = mock_instance
            
            # Mock user input to simulate CLI interaction
            with patch('builtins.input', return_value='s') as mock_input:  # 's' for skip
                options = InstallationOptions(duplicate_resolution=DuplicateResolutionMode.INTERACTIVE)
                result = registry.install_model_with_interactive_resolution(
                    model_path=new_model_dir,
                    options=options
                )
                
                # Should have prompted user for decision
                mock_input.assert_called_once()
                
                # Should skip installation based on user choice
                assert result["status"] == "skipped"
                assert result["reason"] == "user_chose_skip"
                assert "user_decision" in result

    def test_interactive_duplicate_resolution_force_decision(self, tmp_path):
        """Test interactive resolution when user chooses to force installation."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        # Install existing model
        existing_model_dir = tmp_path / "existing_model"
        existing_model_dir.mkdir()
        
        existing_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="force_test_hash",
            content_hash="existing_content_hash",
            components_found={"umap": existing_model_dir / "umap.pkl"},
            missing_components=[],
            validation_errors=[],
            name="existing_model",
            version="1.0.0",
            type="complete_emuses_model",
            description="Existing model"
        )
        
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = existing_validation
            mock_instance.install_model.return_value = "existing_model_123"
            mock_modelio.return_value = mock_instance
            
            registry.install_model(existing_model_dir, model_name="existing_model")
        
        # Try to install duplicate with user choosing to force
        new_model_dir = tmp_path / "new_model"
        new_model_dir.mkdir()
        
        new_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="force_test_hash",  # Same hash
            content_hash="new_content_hash",
            components_found={"umap": new_model_dir / "umap.pkl"},
            missing_components=[],
            validation_errors=[],
            name="new_model",
            version="1.0.0",
            type="complete_emuses_model",
            description="New model for force test"
        )
        
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = new_validation
            mock_instance.install_model.return_value = "new_model_456"
            mock_modelio.return_value = mock_instance
            
            # Mock user input - 'f' for force installation
            with patch('builtins.input', return_value='f') as mock_input:
                options = InstallationOptions(duplicate_resolution=DuplicateResolutionMode.INTERACTIVE)
                result = registry.install_model_with_interactive_resolution(
                    model_path=new_model_dir,
                    options=options
                )
                
                # Should have prompted user and forced installation
                mock_input.assert_called_once()
                assert result["status"] == "success"
                assert result["forced_installation"] is True
                assert result["user_decision"] == "force"

    def test_interactive_duplicate_resolution_view_details(self, tmp_path):
        """Test interactive resolution when user wants to view duplicate details."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        # Install existing model
        existing_model_dir = tmp_path / "existing_model"
        existing_model_dir.mkdir()
        
        existing_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="details_test_hash",
            content_hash="existing_content_hash",
            components_found={"umap": existing_model_dir / "umap.pkl"},
            missing_components=[],
            validation_errors=[],
            name="detailed_model",
            version="1.5.2",
            type="complete_emuses_model",
            description="Model with detailed info"
        )
        
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = existing_validation
            mock_instance.install_model.return_value = "detailed_model_123"
            mock_modelio.return_value = mock_instance
            
            registry.install_model(existing_model_dir, model_name="detailed_model")
        
        # Try to install duplicate
        new_model_dir = tmp_path / "new_model"
        new_model_dir.mkdir()
        
        new_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="details_test_hash",  # Same hash
            content_hash="new_content_hash",
            components_found={"umap": new_model_dir / "umap.pkl"},
            missing_components=[],
            validation_errors=[],
            name="new_model",
            version="1.0.0",
            type="complete_emuses_model",
            description="New model"
        )
        
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = new_validation
            mock_instance.install_model.return_value = "new_model_456"
            mock_modelio.return_value = mock_instance
            
            # Mock user viewing details then skipping
            with patch('builtins.input', side_effect=['d', 's']) as mock_input:  # 'd' for details, 's' for skip
                with patch('builtins.print') as mock_print:  # Capture print output
                    options = InstallationOptions(duplicate_resolution=DuplicateResolutionMode.INTERACTIVE)
                    result = registry.install_model_with_interactive_resolution(
                        model_path=new_model_dir,
                        options=options
                    )
                    
                    # Should have prompted twice (details, then decision)
                    assert mock_input.call_count == 2
                    
                    # Should have printed duplicate details
                    print_calls = [call.args[0] for call in mock_print.call_args_list]
                    detail_prints = [call for call in print_calls if "detailed_model" in str(call)]
                    assert len(detail_prints) > 0  # Should have printed details about existing model
                    
                    # Final decision should be skip
                    assert result["status"] == "skipped"
                    assert result["user_decision"] == "skip"
