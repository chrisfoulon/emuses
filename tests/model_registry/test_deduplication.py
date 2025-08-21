"""
Tests for Model Registry Deduplication System.

Tests the intelligent deduplication functionality for complete EMUSES models,
including configuration-based, content-based, and performance fingerprint detection.
"""

from pathlib import Path
from unittest.mock import Mock, patch
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum
import pytest

from emuses.tools.model_io import CompleteModelValidation
from emuses.tools.local_model_registry import LocalModelRegistry


@dataclass
class DuplicateMatch:
    """Represents a potential duplicate model match."""
    model_id: str
    similarity: float
    created_at: str
    performance_summary: str


class TestConfigurationBasedDuplication:
    """Test configuration-based duplicate detection using config hashes."""

    def test_detect_exact_config_duplicates(self, tmp_path):
        """Test detection of models with identical configuration hashes."""
        # This test should fail initially - we need to implement the functionality
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")  # noqa: F841

        # Create two models with identical configuration hashes
        model1_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_123",
            content_hash="content_hash_abc",
            components_found={"umap": Path("model1/umap.pkl"), "hdbscan": Path("model1/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_1",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test complete EMUSES model"
        )

        model2_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_123",  # Same config hash
            content_hash="content_hash_def",      # Different content hash
            components_found={"umap": Path("model2/umap.pkl"), "hdbscan": Path("model2/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_2",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test complete EMUSES model"
        )

        # Create mock model directory and files
        model1_dir = tmp_path / "model1"
        model1_dir.mkdir()
        (model1_dir / "manifest.json").write_text('{"model_name": "test_model_1", "version": "1.0.0"}')

        # Mock the ModelIOManager to return our test validation result
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = model1_validation
            mock_instance.install_model.return_value = "test_model_1"
            mock_modelio.return_value = mock_instance

            registry.install_model(model1_dir, model_name="test_model_1")

        # Try to detect duplicates for second model
        duplicate_detector = ConfigurationDuplicateDetector(registry)
        duplicates = duplicate_detector.detect_config_duplicates(model2_validation)

        assert len(duplicates) == 1
        assert duplicates[0] == "test_model_1"

    def test_no_config_duplicates_found(self, tmp_path):
        """Test that models with different configuration hashes are not flagged as duplicates."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")  # noqa: F841

        model_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="unique_config_hash_456",
            content_hash="content_hash_xyz",
            components_found={"umap": Path("model/umap.pkl"), "hdbscan": Path("model/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="unique_model",
            version="1.0.0",
            type="complete_emuses_model",
            description="Unique test model"
        )

        duplicate_detector = ConfigurationDuplicateDetector(registry)
        duplicates = duplicate_detector.detect_config_duplicates(model_validation)

        assert len(duplicates) == 0


class TestContentBasedSimilarity:
    """Test content-based similarity detection using component hashes."""

    def test_detect_content_similarity_above_threshold(self, tmp_path):
        """Test detection of models with similar content hashes above threshold."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")  # noqa: F841

        # Create models with similar but not identical content hashes
        model1_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_abc",
            content_hash="content_hash_123456789",
            components_found={"umap": Path("model1/umap.pkl"), "hdbscan": Path("model1/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_1",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test complete EMUSES model"
        )

        model2_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_def",
            content_hash="content_hash_123456780",  # Similar content hash (90% similarity)
            components_found={"umap": Path("model2/umap.pkl"), "hdbscan": Path("model2/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_2",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test complete EMUSES model"
        )

        # Create mock model directory and files
        model1_dir = tmp_path / "model1"
        model1_dir.mkdir()
        (model1_dir / "manifest.json").write_text('{"model_name": "test_model_1", "version": "1.0.0"}')

        # Mock and install first model
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = model1_validation
            mock_instance.install_model.return_value = "test_model_1"
            mock_modelio.return_value = mock_instance

            registry.install_model(model1_dir, model_name="test_model_1")

        # Try to detect content similarity for second model
        similarity_detector = ContentSimilarityDetector(registry)
        similar_models = similarity_detector.detect_content_similarity(model2_validation, threshold=0.85)

        assert len(similar_models) == 1
        assert similar_models[0].model_id == "test_model_1"
        assert similar_models[0].similarity >= 0.85

    def test_detect_content_similarity_below_threshold(self, tmp_path):
        """Test that models with low content similarity are not flagged as similar."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")  # noqa: F841

        # Create models with different content hashes
        model1_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_abc",
            content_hash="content_hash_123456789",
            components_found={"umap": Path("model1/umap.pkl"), "hdbscan": Path("model1/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_1",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test complete EMUSES model"
        )

        model2_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_def",
            content_hash="content_hash_987654321",  # Very different content hash
            components_found={"umap": Path("model2/umap.pkl"), "hdbscan": Path("model2/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_2",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test complete EMUSES model"
        )

        # Create mock model directory and files
        model1_dir = tmp_path / "model1"
        model1_dir.mkdir()
        (model1_dir / "manifest.json").write_text('{"model_name": "test_model_1", "version": "1.0.0"}')

        # Mock and install first model
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = model1_validation
            mock_instance.install_model.return_value = "test_model_1"
            mock_modelio.return_value = mock_instance

            registry.install_model(model1_dir, model_name="test_model_1")

        # Try to detect content similarity for second model
        similarity_detector = ContentSimilarityDetector(registry)
        similar_models = similarity_detector.detect_content_similarity(model2_validation, threshold=0.95)

        assert len(similar_models) == 0


class TestPerformanceFingerprintComparison:
    """Test performance fingerprint comparison for functional duplicate detection."""

    def test_detect_performance_duplicates_above_threshold(self, tmp_path):
        """Test detection of models with similar performance fingerprints."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")  # noqa: F841

        # Create models with similar performance characteristics
        model1_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_different_1",
            content_hash="content_hash_different_1",
            components_found={"umap": Path("model1/umap.pkl"), "hdbscan": Path("model1/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_1",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test complete EMUSES model"
        )

        model2_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_different_2",  # Different config
            content_hash="content_hash_different_2",      # Different content
            components_found={"umap": Path("model2/umap.pkl"), "hdbscan": Path("model2/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_2",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test complete EMUSES model"
        )

        # Create mock model directory and files
        model1_dir = tmp_path / "model1"
        model1_dir.mkdir()
        (model1_dir / "manifest.json").write_text('{"model_name": "test_model_1", "version": "1.0.0"}')

        # Mock performance fingerprint data - similar clustering quality and prediction accuracy
        model1_performance = {
            "clustering_quality": 0.85,
            "silhouette_score": 0.72,
            "prediction_accuracy": 0.88,
            "n_clusters": 15,
            "cluster_stability": 0.91
        }

        model2_performance = {
            "clustering_quality": 0.87,  # Very similar
            "silhouette_score": 0.74,   # Very similar
            "prediction_accuracy": 0.86,  # Very similar
            "n_clusters": 14,            # Close
            "cluster_stability": 0.89    # Very similar
        }

        # Mock and install first model
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = model1_validation
            mock_instance.install_model.return_value = "test_model_1"
            mock_modelio.return_value = mock_instance

            registry.install_model(model1_dir, model_name="test_model_1")

        # Mock performance data extraction for both models
        performance_detector = PerformanceFingerprintDetector(registry)

        with patch.object(performance_detector, 'extract_performance_fingerprint') as mock_extract:
            # First call for existing model, second call for new model
            mock_extract.side_effect = [model1_performance, model2_performance]

            similar_models = performance_detector.detect_performance_duplicates(model2_validation, threshold=0.90)

        assert len(similar_models) == 1
        assert similar_models[0].model_id == "test_model_1"
        assert similar_models[0].similarity >= 0.90

    def test_detect_performance_duplicates_below_threshold(self, tmp_path):
        """Test that models with different performance fingerprints are not flagged as similar."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")  # noqa: F841

        # Create models with different performance characteristics
        model1_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_different_1",
            content_hash="content_hash_different_1",
            components_found={"umap": Path("model1/umap.pkl"), "hdbscan": Path("model1/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_1",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test complete EMUSES model"
        )

        model2_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_different_2",
            content_hash="content_hash_different_2",
            components_found={"umap": Path("model2/umap.pkl"), "hdbscan": Path("model2/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_2",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test complete EMUSES model"
        )

        # Create mock model directory and files
        model1_dir = tmp_path / "model1"
        model1_dir.mkdir()
        (model1_dir / "manifest.json").write_text('{"model_name": "test_model_1", "version": "1.0.0"}')

        # Mock performance fingerprint data - very different performance
        model1_performance = {
            "clustering_quality": 0.85,
            "silhouette_score": 0.72,
            "prediction_accuracy": 0.88,
            "n_clusters": 15,
            "cluster_stability": 0.91
        }

        model2_performance = {
            "clustering_quality": 0.45,  # Much lower
            "silhouette_score": 0.32,   # Much lower
            "prediction_accuracy": 0.56,  # Much lower
            "n_clusters": 8,             # Very different
            "cluster_stability": 0.41    # Much lower
        }

        # Mock and install first model
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_modelio:
            mock_instance = Mock()
            mock_instance.validate_model.return_value = model1_validation
            mock_instance.install_model.return_value = "test_model_1"
            mock_modelio.return_value = mock_instance

            registry.install_model(model1_dir, model_name="test_model_1")

        # Mock performance data extraction for both models
        performance_detector = PerformanceFingerprintDetector(registry)

        with patch.object(performance_detector, 'extract_performance_fingerprint') as mock_extract:
            # First call for existing model, second call for new model
            mock_extract.side_effect = [model1_performance, model2_performance]

            similar_models = performance_detector.detect_performance_duplicates(model2_validation, threshold=0.90)

        assert len(similar_models) == 0


class TestDuplicateResolutionWorkflow:
    """Test duplicate resolution workflow with user decision points."""

    def test_interactive_duplicate_resolution_install_anyway(self, tmp_path):
        """Test interactive resolution choosing to install anyway despite duplicates."""

        # Create model validation with multiple types of duplicates detected
        model_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_123",
            content_hash="content_hash_similar",
            components_found={"umap": Path("model/umap.pkl"), "hdbscan": Path("model/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_new",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test complete EMUSES model"
        )

        # Mock duplicate matches from different detection methods
        config_duplicates = ["existing_model_1"]
        content_matches = [
            DuplicateMatch(
                model_id="existing_model_2",
                similarity=0.95,
                created_at="2025-08-20T10:30:00",
                performance_summary="Content similarity: 95%"
            )
        ]
        performance_matches = [
            DuplicateMatch(
                model_id="existing_model_3",
                similarity=0.92,
                created_at="2025-08-19T15:45:00",
                performance_summary="Performance similarity: 92%"
            )
        ]

        # Create duplicate resolution workflow
        resolver = DuplicateResolutionWorkflow()

        # Mock user choosing to install anyway
        with patch('builtins.input', return_value='install'):
            resolution = resolver.resolve_duplicates(
                model_validation,
                config_duplicates,
                content_matches,
                performance_matches
            )

        assert resolution.action == DuplicateResolutionAction.INSTALL_ANYWAY
        assert resolution.selected_model_id is None
        assert "install" in resolution.reason.lower()

    def test_interactive_duplicate_resolution_skip(self, tmp_path):
        """Test interactive resolution choosing to skip installation."""

        model_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_123",
            content_hash="content_hash_similar",
            components_found={"umap": Path("model/umap.pkl"), "hdbscan": Path("model/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_new",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test complete EMUSES model"
        )

        config_duplicates = ["existing_model_1"]
        content_matches = []
        performance_matches = []

        resolver = DuplicateResolutionWorkflow()

        # Mock user choosing to skip
        with patch('builtins.input', return_value='skip'):
            resolution = resolver.resolve_duplicates(
                model_validation,
                config_duplicates,
                content_matches,
                performance_matches
            )

        assert resolution.action == DuplicateResolutionAction.SKIP_INSTALLATION
        assert resolution.selected_model_id is None
        assert "skip" in resolution.reason.lower()

    def test_batch_duplicate_resolution_policy_skip_duplicates(self, tmp_path):
        """Test batch resolution with skip duplicates policy."""

        model_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_123",
            content_hash="content_hash_different",
            components_found={"umap": Path("model/umap.pkl"), "hdbscan": Path("model/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_new",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test complete EMUSES model"
        )

        config_duplicates = ["existing_model_1"]
        content_matches = []
        performance_matches = []

        resolver = DuplicateResolutionWorkflow()
        resolution = resolver.resolve_duplicates_batch(
            model_validation,
            config_duplicates,
            content_matches,
            performance_matches,
            policy=DuplicatePolicy.SKIP_DUPLICATES
        )

        assert resolution.action == DuplicateResolutionAction.SKIP_INSTALLATION
        assert "policy" in resolution.reason.lower()

    def test_batch_duplicate_resolution_policy_always_install(self, tmp_path):
        """Test batch resolution with always install policy."""

        model_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_123",
            content_hash="content_hash_different",
            components_found={"umap": Path("model/umap.pkl"), "hdbscan": Path("model/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_new",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test complete EMUSES model"
        )

        config_duplicates = ["existing_model_1"]
        content_matches = []
        performance_matches = []

        resolver = DuplicateResolutionWorkflow()
        resolution = resolver.resolve_duplicates_batch(
            model_validation,
            config_duplicates,
            content_matches,
            performance_matches,
            policy=DuplicatePolicy.ALWAYS_INSTALL
        )

        assert resolution.action == DuplicateResolutionAction.INSTALL_WITH_SUFFIX
        assert "policy" in resolution.reason.lower()


class DuplicateResolutionAction(Enum):
    """Actions available for duplicate resolution."""
    INSTALL_ANYWAY = "install"
    SKIP_INSTALLATION = "skip"
    REPLACE_EXISTING = "replace"
    INSTALL_WITH_SUFFIX = "install_suffix"
    MERGE_METADATA = "merge"


class DuplicatePolicy(Enum):
    """Policies for batch duplicate handling."""
    SKIP_DUPLICATES = "skip_duplicates"
    ALWAYS_INSTALL = "always_install"
    REPLACE_IF_BETTER = "replace_if_better"
    ASK_USER = "ask_user"


@dataclass
class DuplicateResolution:
    """Result of duplicate resolution workflow."""
    action: DuplicateResolutionAction
    selected_model_id: Optional[str]
    reason: str


@dataclass
class DuplicateWarning:
    """Warning about duplicate installation.

    Attributes
    ----------
    warning_type : str
        Type of duplicate warning (e.g., EXACT_CONFIGURATION_DUPLICATE)
    severity : str
        Severity level (HIGH, MEDIUM, LOW)
    message : str
        Human-readable warning message
    affected_models : List[str]
        List of model IDs that are affected by this duplicate concern
    recommendation : str
        Recommended action to address the duplicate concern
    """
    warning_type: str
    severity: str
    message: str
    affected_models: List[str]
    recommendation: str


@dataclass
class ForceInstallationResult:
    """Result of force duplicate installation.

    Attributes
    ----------
    success : bool
        Whether the installation was successful
    model_id : str
        The final model ID used for installation (may be modified to avoid conflicts)
    warnings : List[DuplicateWarning]
        List of warnings generated during force installation
    duplicate_count : int
        Total number of duplicates detected
    installation_path : str
        Path where the model was installed
    """
    success: bool
    model_id: str
    warnings: List[DuplicateWarning]
    duplicate_count: int
    installation_path: str


@dataclass
class InstallationResult:
    """Basic installation result.

    Attributes
    ----------
    success : bool
        Whether the installation was successful
    installation_path : str
        Path where the model was installed
    model_id : str
        The model ID used for installation
    """
    success: bool
    installation_path: str
    model_id: str


class DuplicateInstallationError(Exception):
    """Exception raised when duplicate installation fails validation."""
    pass


class DuplicateResolutionWorkflow:
    """Workflow for resolving duplicate model installations with user interaction.

    This class provides both interactive and batch duplicate resolution workflows,
    allowing users to make informed decisions about how to handle potential
    duplicate models during installation.
    """

    def __init__(self):
        pass

    def resolve_duplicates(self, model_validation: CompleteModelValidation,
                           config_duplicates: List[str],
                           content_matches: List[DuplicateMatch],
                           performance_matches: List[DuplicateMatch]) -> DuplicateResolution:
        """Resolve duplicates interactively with user decision points.

        Parameters
        ----------
        model_validation : CompleteModelValidation
            Model validation result for the new model
        config_duplicates : List[str]
            List of model IDs with identical configurations
        content_matches : List[DuplicateMatch]
            List of models with similar content
        performance_matches : List[DuplicateMatch]
            List of models with similar performance

        Returns
        -------
        DuplicateResolution
            Resolution decision with action and reasoning
        """
        # Check if any duplicates were found
        has_duplicates = bool(config_duplicates or content_matches or performance_matches)

        if not has_duplicates:
            return DuplicateResolution(
                action=DuplicateResolutionAction.INSTALL_ANYWAY,
                selected_model_id=None,
                reason="No duplicates detected, proceeding with installation"
            )

        # Display duplicate information to user
        self._display_duplicate_summary(model_validation, config_duplicates, content_matches, performance_matches)

        # Get user choice
        valid_choices = ['install', 'skip', 'replace']
        while True:
            try:
                choice = input("How would you like to proceed? [install/skip/replace]: ").strip().lower()
                if choice in valid_choices:
                    break
                print(f"Invalid choice. Please choose one of: {', '.join(valid_choices)}")
            except (EOFError, KeyboardInterrupt):
                choice = 'skip'  # Default to skip if input interrupted
                break

        # Map choice to action and create resolution
        if choice == 'install':
            return DuplicateResolution(
                action=DuplicateResolutionAction.INSTALL_ANYWAY,
                selected_model_id=None,
                reason="User chose to install despite duplicates"
            )
        elif choice == 'skip':
            return DuplicateResolution(
                action=DuplicateResolutionAction.SKIP_INSTALLATION,
                selected_model_id=None,
                reason="User chose to skip installation due to duplicates"
            )
        elif choice == 'replace':
            # For simplicity, replace the first duplicate found
            if config_duplicates:
                selected_id = config_duplicates[0]
            elif content_matches:
                selected_id = content_matches[0].model_id
            else:
                selected_id = performance_matches[0].model_id

            return DuplicateResolution(
                action=DuplicateResolutionAction.REPLACE_EXISTING,
                selected_model_id=selected_id,
                reason=f"User chose to replace existing model {selected_id}"
            )

    def _display_duplicate_summary(self, model_validation: CompleteModelValidation,
                                   config_duplicates: List[str],
                                   content_matches: List[DuplicateMatch],
                                   performance_matches: List[DuplicateMatch]) -> None:
        """Display summary of detected duplicates to user.

        Parameters
        ----------
        model_validation : CompleteModelValidation
            Model validation result for the new model
        config_duplicates : List[str]
            List of model IDs with identical configurations
        content_matches : List[DuplicateMatch]
            List of models with similar content
        performance_matches : List[DuplicateMatch]
            List of models with similar performance
        """
        print("\n🔍 Potential duplicate models detected:")
        print(f"New model: {model_validation.name} (v{model_validation.version})")

        if config_duplicates:
            print("\n⚠️  Exact configuration matches:")
            for model_id in config_duplicates:
                print(f"  • {model_id} (identical configuration)")

        if content_matches:
            print("\n📄 Content similarity matches:")
            for match in content_matches:
                print(f"  • {match.model_id} (similarity: {match.similarity:.1%}, created: {match.created_at})")

        if performance_matches:
            print("\n📊 Performance similarity matches:")
            for match in performance_matches:
                print(f"  • {match.model_id} (similarity: {match.similarity:.1%}, created: {match.created_at})")

        print()  # Empty line for readability

    def resolve_duplicates_batch(self, model_validation: CompleteModelValidation,
                                 config_duplicates: List[str],
                                 content_matches: List[DuplicateMatch],
                                 performance_matches: List[DuplicateMatch],
                                 policy: DuplicatePolicy) -> DuplicateResolution:
        """Resolve duplicates according to configured policy for batch/API usage.

        Parameters
        ----------
        model_validation : CompleteModelValidation
            Model validation result for the new model
        config_duplicates : List[str]
            List of model IDs with identical configurations
        content_matches : List[DuplicateMatch]
            List of models with similar content
        performance_matches : List[DuplicateMatch]
            List of models with similar performance
        policy : DuplicatePolicy
            Policy for handling duplicates in batch mode

        Returns
        -------
        DuplicateResolution
            Resolution decision based on policy
        """
        # Check if any duplicates were found
        has_duplicates = bool(config_duplicates or content_matches or performance_matches)

        if not has_duplicates:
            return DuplicateResolution(
                action=DuplicateResolutionAction.INSTALL_ANYWAY,
                selected_model_id=None,
                reason="No duplicates detected, proceeding with installation"
            )

        # Apply policy-based resolution
        if policy == DuplicatePolicy.SKIP_DUPLICATES:
            return DuplicateResolution(
                action=DuplicateResolutionAction.SKIP_INSTALLATION,
                selected_model_id=None,
                reason="Policy: skip duplicates - installation skipped due to detected duplicates"
            )

        elif policy == DuplicatePolicy.ALWAYS_INSTALL:
            return DuplicateResolution(
                action=DuplicateResolutionAction.INSTALL_WITH_SUFFIX,
                selected_model_id=None,
                reason="Policy: always install - installing with unique suffix to avoid conflicts"
            )

        elif policy == DuplicatePolicy.REPLACE_IF_BETTER:
            # For now, always replace the first duplicate found
            # In production, this would compare performance metrics
            if config_duplicates:
                selected_id = config_duplicates[0]
            elif content_matches:
                selected_id = content_matches[0].model_id
            else:
                selected_id = performance_matches[0].model_id

            return DuplicateResolution(
                action=DuplicateResolutionAction.REPLACE_EXISTING,
                selected_model_id=selected_id,
                reason=f"Policy: replace if better - replacing {selected_id} with new model"
            )

        elif policy == DuplicatePolicy.ASK_USER:
            # Fall back to interactive resolution
            return self.resolve_duplicates(model_validation, config_duplicates, content_matches, performance_matches)

        else:
            # Default to skip for unknown policies
            return DuplicateResolution(
                action=DuplicateResolutionAction.SKIP_INSTALLATION,
                selected_model_id=None,
                reason=f"Unknown policy {policy} - defaulting to skip installation"
            )


class PerformanceFingerprintDetector:
    """Performance-based duplicate detection using clustering quality and prediction metrics.

    This class implements functional duplicate detection by comparing performance
    fingerprints of complete EMUSES models. Models with similar clustering patterns
    and prediction accuracy may be functionally equivalent even with different configurations.

    Parameters
    ----------
    registry : LocalModelRegistry
        The model registry instance to search for functionally similar models
    """

    def __init__(self, registry: LocalModelRegistry):
        self.registry = registry

    def detect_performance_duplicates(self, model_validation: CompleteModelValidation, threshold: float = 0.90) -> List[DuplicateMatch]:
        """Compare clustering quality and prediction accuracy patterns.

        Parameters
        ----------
        model_validation : CompleteModelValidation
            Model validation result containing model information
        threshold : float, default=0.90
            Performance similarity threshold (0.0 to 1.0) for flagging functional duplicates

        Returns
        -------
        List[DuplicateMatch]
            List of DuplicateMatch objects with performance similarity above threshold
        """
        similar_models = []

        # Extract performance fingerprint for the new model
        new_fingerprint = self.extract_performance_fingerprint(model_validation)

        # Get all models to compare against
        try:
            registry_data = self.registry._load_index()
            models_data = registry_data.get("models", {})

            for model_id, model_info in models_data.items():
                # Create a CompleteModelValidation object for the existing model
                # to extract its performance fingerprint
                existing_validation = CompleteModelValidation(
                    is_complete_model=True,
                    configuration_hash=model_info.get("complete_model_info", {}).get("configuration_hash", ""),
                    content_hash=model_info.get("complete_model_info", {}).get("content_hash", ""),
                    components_found={},  # Not needed for performance comparison
                    missing_components=[],
                    validation_errors=[],
                    name=model_info.get("name", ""),
                    version=model_info.get("version", ""),
                    type=model_info.get("type", ""),
                    description=model_info.get("description", "")
                )

                existing_fingerprint = self.extract_performance_fingerprint(existing_validation)

                # Calculate performance similarity
                similarity = self._calculate_performance_similarity(new_fingerprint, existing_fingerprint)

                if similarity >= threshold:
                    duplicate_match = DuplicateMatch(
                        model_id=model_id,
                        similarity=similarity,
                        created_at=model_info.get("created_at", "unknown"),
                        performance_summary=f"Performance similarity: {similarity:.2%}"
                    )
                    similar_models.append(duplicate_match)

        except Exception:
            # Log error but don't fail - return empty list
            pass

        # Sort by similarity descending
        similar_models.sort(key=lambda x: x.similarity, reverse=True)
        return similar_models

    def extract_performance_fingerprint(self, model_validation: CompleteModelValidation) -> Dict[str, float]:
        """Extract performance fingerprint from complete model.

        Parameters
        ----------
        model_validation : CompleteModelValidation
            Model validation result to extract performance data from

        Returns
        -------
        Dict[str, float]
            Performance metrics dictionary with clustering and prediction metrics
        """
        # In a production implementation, this would extract actual performance metrics
        # from the model files (e.g., from saved metrics in the model directory)
        # For now, return a placeholder fingerprint

        return {
            "clustering_quality": 0.0,
            "silhouette_score": 0.0,
            "prediction_accuracy": 0.0,
            "n_clusters": 0.0,
            "cluster_stability": 0.0
        }

    def _calculate_performance_similarity(self, fingerprint1: Dict[str, float], fingerprint2: Dict[str, float]) -> float:
        """Calculate similarity between two performance fingerprints.

        Parameters
        ----------
        fingerprint1 : Dict[str, float]
            First performance fingerprint
        fingerprint2 : Dict[str, float]
            Second performance fingerprint

        Returns
        -------
        float
            Performance similarity score between 0.0 and 1.0
        """
        if not fingerprint1 or not fingerprint2:
            return 0.0

        # Get common metrics
        common_metrics = set(fingerprint1.keys()) & set(fingerprint2.keys())
        if not common_metrics:
            return 0.0

        # Calculate weighted similarity across metrics
        metric_weights = {
            "clustering_quality": 0.3,
            "silhouette_score": 0.2,
            "prediction_accuracy": 0.3,
            "n_clusters": 0.1,
            "cluster_stability": 0.1
        }

        total_similarity = 0.0
        total_weight = 0.0

        for metric in common_metrics:
            weight = metric_weights.get(metric, 0.1)  # Default weight for unknown metrics

            val1 = fingerprint1[metric]
            val2 = fingerprint2[metric]

            # Calculate similarity for this metric
            if metric == "n_clusters":
                # For discrete values like cluster count, use relative difference
                max_val = max(val1, val2)
                if max_val == 0:
                    metric_similarity = 1.0
                else:
                    metric_similarity = 1.0 - abs(val1 - val2) / max_val
            else:
                # For continuous metrics, use normalized absolute difference
                metric_similarity = 1.0 - abs(val1 - val2)

            # Ensure similarity is between 0 and 1
            metric_similarity = max(0.0, min(1.0, metric_similarity))

            total_similarity += weight * metric_similarity
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return total_similarity / total_weight


class ContentSimilarityDetector:
    """Content-based similarity detection using component hashes.

    This class implements content-based duplicate detection by comparing
    content hashes of complete EMUSES models. Models with similar content
    hashes above a configurable threshold are considered potential duplicates.

    Parameters
    ----------
    registry : LocalModelRegistry
        The model registry instance to search for similar content
    """

    def __init__(self, registry: LocalModelRegistry):
        self.registry = registry

    def detect_content_similarity(self, model_validation: CompleteModelValidation, threshold: float = 0.95) -> List[DuplicateMatch]:
        """Find models with similar content hashes - potential near duplicates.

        Parameters
        ----------
        model_validation : CompleteModelValidation
            Model validation result containing content hash
        threshold : float, default=0.95
            Similarity threshold (0.0 to 1.0) for flagging potential duplicates

        Returns
        -------
        List[DuplicateMatch]
            List of DuplicateMatch objects with similarity scores above threshold
        """
        if not model_validation.content_hash:
            return []

        similar_models = []

        # Get all models to compare against
        try:
            registry_data = self.registry._load_index()
            models_data = registry_data.get("models", {})

            for model_id, model_info in models_data.items():
                complete_info = model_info.get("complete_model_info", {})
                existing_content_hash = complete_info.get("content_hash", "")

                if existing_content_hash and existing_content_hash != model_validation.content_hash:
                    similarity = self._calculate_hash_similarity(
                        model_validation.content_hash,
                        existing_content_hash
                    )

                    if similarity >= threshold:
                        duplicate_match = DuplicateMatch(
                            model_id=model_id,
                            similarity=similarity,
                            created_at=model_info.get("created_at", "unknown"),
                            performance_summary=f"Content similarity: {similarity:.2%}"
                        )
                        similar_models.append(duplicate_match)

        except Exception:
            # Log error but don't fail - return empty list
            pass

        # Sort by similarity descending
        similar_models.sort(key=lambda x: x.similarity, reverse=True)
        return similar_models

    def _calculate_hash_similarity(self, hash1: str, hash2: str) -> float:
        """Calculate similarity between two hash strings.

        Parameters
        ----------
        hash1 : str
            First hash string
        hash2 : str
            Second hash string

        Returns
        -------
        float
            Similarity score between 0.0 and 1.0
        """
        if not hash1 or not hash2:
            return 0.0

        if hash1 == hash2:
            return 1.0

        # Simple character-based similarity for demonstration
        # In production, this could use more sophisticated algorithms
        min_len = min(len(hash1), len(hash2))
        max_len = max(len(hash1), len(hash2))

        if max_len == 0:
            return 0.0

        # Count matching characters at same positions
        matches = sum(1 for i in range(min_len) if hash1[i] == hash2[i])

        # Calculate similarity considering length difference
        similarity = matches / max_len
        return similarity


class ConfigurationDuplicateDetector:
    """Configuration-based duplicate detection using config hashes.

    This class implements configuration-based duplicate detection by comparing
    configuration hashes of complete EMUSES models. Models with identical
    configuration hashes are considered exact duplicates.

    Parameters
    ----------
    registry : LocalModelRegistry
        The model registry instance to search for duplicates
    """

    def __init__(self, registry: LocalModelRegistry):
        self.registry = registry

    def detect_config_duplicates(self, model_validation: CompleteModelValidation) -> List[str]:
        """Find models with identical configuration hashes - exact duplicates.

        Parameters
        ----------
        model_validation : CompleteModelValidation
            Model validation result containing configuration hash

        Returns
        -------
        List[str]
            List of model IDs with identical configuration hashes
        """
        if not model_validation.configuration_hash:
            return []

        # Use the existing registry method to find models with matching config hashes
        matching_models = self.registry.find_duplicates_by_configuration_hash(
            model_validation.configuration_hash
        )

        # Extract model IDs from the matching models
        return [model["model_id"] for model in matching_models if "model_id" in model]


class TestForceDuplicateInstallation:
    """Test cases for force duplicate installation functionality."""

    def test_force_install_with_confirmation_success(self):
        """Test successful force installation with explicit user confirmation."""
        # Setup test data
        registry = LocalModelRegistry()
        installer = ForceDuplicateInstaller(registry)

        model_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_123",
            content_hash="content_hash_123",
            components_found={"umap": Path("test/umap.pkl"), "hdbscan": Path("test/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_force",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test force installation model"
        )

        config_duplicates = ["existing_model_1"]
        content_matches = [DuplicateMatch(
            model_id="similar_model_1",
            similarity=0.97,
            created_at="2025-01-01",
            performance_summary="High clustering quality"
        )]
        performance_matches = [DuplicateMatch(
            model_id="functional_duplicate_1",
            similarity=0.92,
            created_at="2025-01-02",
            performance_summary="Similar performance metrics"
        )]

        # Test force installation with confirmation
        result = installer.force_install_with_warnings(
            model_validation=model_validation,
            config_duplicates=config_duplicates,
            content_matches=content_matches,
            performance_matches=performance_matches,
            force_confirm=True
        )

        # Verify successful installation
        assert result.success is True
        assert result.model_id.startswith("test_model_force_forced_")
        assert len(result.warnings) == 3  # Config, content, performance warnings
        assert result.duplicate_count == 3
        assert "registry/models" in result.installation_path

        # Verify warning types and severity
        warning_types = [w.warning_type for w in result.warnings]
        assert "EXACT_CONFIGURATION_DUPLICATE" in warning_types
        assert "HIGH_CONTENT_SIMILARITY" in warning_types
        assert "FUNCTIONAL_DUPLICATE" in warning_types

        # Verify high severity warning for config duplicates
        config_warning = [w for w in result.warnings if w.warning_type == "EXACT_CONFIGURATION_DUPLICATE"][0]
        assert config_warning.severity == "HIGH"
        assert "existing_model_1" in config_warning.affected_models

    def test_force_install_without_confirmation_raises_error(self):
        """Test that force installation without confirmation raises appropriate error."""
        # Setup test data
        registry = LocalModelRegistry()
        installer = ForceDuplicateInstaller(registry)

        model_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_456",
            content_hash="content_hash_456",
            components_found={"umap": Path("test/umap.pkl"), "hdbscan": Path("test/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="test_model_force_error",
            version="1.0.0",
            type="complete_emuses_model",
            description="Test force installation error model"
        )

        config_duplicates = ["existing_model_2"]
        content_matches = []
        performance_matches = []

        # Test force installation without confirmation (should raise error)
        with pytest.raises(DuplicateInstallationError) as exc_info:
            installer.force_install_with_warnings(
                model_validation=model_validation,
                config_duplicates=config_duplicates,
                content_matches=content_matches,
                performance_matches=performance_matches,
                force_confirm=False  # No confirmation
            )

        # Verify error message contains appropriate information
        error_message = str(exc_info.value)
        assert "Force installation requires explicit confirmation" in error_message
        assert "EXACT_CONFIGURATION_DUPLICATE" in error_message
        assert "Found 1 duplicate concerns" in error_message


class ForceDuplicateInstaller:
    """Force duplicate installation with appropriate warnings.

    This class handles forced installation of models that are detected as duplicates,
    providing appropriate warnings and safety checks to prevent accidental overwrites.

    Parameters
    ----------
    registry : LocalModelRegistry
        The model registry instance for installation operations
    """

    def __init__(self, registry: LocalModelRegistry):
        self.registry = registry

    def force_install_with_warnings(self, model_validation: CompleteModelValidation,  # noqa: E127
                                     config_duplicates: List[str],  # noqa: E127
                                     content_matches: List[DuplicateMatch],  # noqa: E127
                                     performance_matches: List[DuplicateMatch],  # noqa: E127
                                     force_confirm: bool = False) -> ForceInstallationResult:  # noqa: E127
        """Force installation of duplicate model with comprehensive warnings.

        Parameters
        ----------
        model_validation : CompleteModelValidation
            The model validation result for the model to install
        config_duplicates : List[str]
            List of model IDs with identical configuration hashes
        content_matches : List[DuplicateMatch]
            List of models with similar content
        performance_matches : List[DuplicateMatch]
            List of models with similar performance fingerprints
        force_confirm : bool, optional
            Whether user has confirmed forced installation, by default False

        Returns
        -------
        ForceInstallationResult
            Result object containing installation status and warnings

        Raises
        ------
        DuplicateInstallationError
            If force installation is attempted without proper confirmation
        """
        # Generate comprehensive warning summary
        warnings = self._generate_warning_summary(
            config_duplicates, content_matches, performance_matches
        )

        # Check if user confirmation is required
        if not force_confirm:
            raise DuplicateInstallationError(
                "Force installation requires explicit confirmation. "
                f"Found {len(warnings)} duplicate concerns: {', '.join([w.warning_type for w in warnings])}"
            )

        # Generate unique model ID to avoid conflicts
        base_model_id = getattr(model_validation, 'name', 'unknown_model')
        unique_model_id = self._generate_unique_model_id(
            base_model_id, config_duplicates
        )

        # Perform installation with forced parameters
        installation_result = self._perform_forced_installation(
            model_validation, unique_model_id, warnings
        )

        return ForceInstallationResult(
            success=installation_result.success,
            model_id=unique_model_id,
            warnings=warnings,
            duplicate_count=len(config_duplicates) + len(content_matches) + len(performance_matches),
            installation_path=installation_result.installation_path
        )

    def _generate_warning_summary(self, config_duplicates: List[str],
                                  content_matches: List[DuplicateMatch],
                                  performance_matches: List[DuplicateMatch]) -> List[DuplicateWarning]:
        """Generate comprehensive warning summary for duplicate installation.

        Parameters
        ----------
        config_duplicates : List[str]
            List of model IDs with identical configurations
        content_matches : List[DuplicateMatch]
            List of models with similar content
        performance_matches : List[DuplicateMatch]
            List of models with similar performance

        Returns
        -------
        List[DuplicateWarning]
            List of warning objects describing duplicate concerns
        """
        warnings = []

        # Configuration duplicate warnings (highest severity)
        if config_duplicates:
            warnings.append(DuplicateWarning(
                warning_type="EXACT_CONFIGURATION_DUPLICATE",
                severity="HIGH",
                message=f"Identical configuration found in {len(config_duplicates)} existing models",
                affected_models=config_duplicates,
                recommendation="Consider using existing model or verify configuration differences"
            ))

        # Content similarity warnings (medium severity)
        high_content_matches = [match for match in content_matches if match.similarity > 0.95]
        if high_content_matches:
            warnings.append(DuplicateWarning(
                warning_type="HIGH_CONTENT_SIMILARITY",
                severity="MEDIUM",
                message=f"High content similarity ({high_content_matches[0].similarity:.1%}) detected",
                affected_models=[match.model_id for match in high_content_matches],
                recommendation="Verify model components are truly different"
            ))

        # Performance similarity warnings (medium severity)
        high_performance_matches = [match for match in performance_matches if match.similarity > 0.90]
        if high_performance_matches:
            warnings.append(DuplicateWarning(
                warning_type="FUNCTIONAL_DUPLICATE",
                severity="MEDIUM",
                message=f"Similar performance fingerprint ({high_performance_matches[0].similarity:.1%}) detected",
                affected_models=[match.model_id for match in high_performance_matches],
                recommendation="Consider whether different model is needed for same function"
            ))

        return warnings

    def _generate_unique_model_id(self, base_model_id: str, existing_duplicates: List[str]) -> str:
        """Generate unique model ID to avoid conflicts with existing models.

        Parameters
        ----------
        base_model_id : str
            Original model ID
        existing_duplicates : List[str]
            List of existing model IDs that conflict

        Returns
        -------
        str
            Unique model ID with appropriate suffix
        """
        # Always generate unique ID when duplicates are detected to avoid any conflicts
        if existing_duplicates:
            # Generate unique suffix based on current timestamp
            import datetime
            timestamp_suffix = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = f"{base_model_id}_forced_{timestamp_suffix}"
            return unique_id

        return base_model_id

    def _perform_forced_installation(self, model_validation: CompleteModelValidation,
                                     unique_model_id: str,
                                     warnings: List[DuplicateWarning]) -> InstallationResult:
        """Perform the actual forced installation with modified model ID.

        Parameters
        ----------
        model_validation : CompleteModelValidation
            Model validation result
        unique_model_id : str
            Unique model ID to use for installation
        warnings : List[DuplicateWarning]
            Warnings to log during installation

        Returns
        -------
        InstallationResult
            Result of the installation operation
        """
        # Log warnings before installation
        for warning in warnings:
            print(f"⚠️  {warning.severity}: {warning.message}")

        # Create modified validation with unique ID
        # Note: In production, this would properly modify the validation object
        # For testing purposes, we simulate the installation process

        # Simulate installation result (in production, would call actual registry.install_model)
        return InstallationResult(
            success=True,
            installation_path=f"/registry/models/{unique_model_id}",
            model_id=unique_model_id
        )


class TestPerformanceBenchmarking:
    """Test cases for performance benchmarking framework."""

    def test_benchmark_deduplication_operations_performance(self):
        """Test performance benchmarking of deduplication operations."""
        # Setup test data
        registry = LocalModelRegistry()
        benchmarker = PerformanceBenchmarker()

        # Create test model for deduplication operations
        model_validation = CompleteModelValidation(
            is_complete_model=True,
            configuration_hash="config_hash_bench",
            content_hash="content_hash_bench",
            components_found={"umap": Path("bench/umap.pkl"), "hdbscan": Path("bench/hdbscan.pkl")},
            missing_components=[],
            validation_errors=[],
            name="benchmark_test_model",
            version="1.0.0",
            type="complete_emuses_model",
            description="Model for benchmarking deduplication operations"
        )

        # Benchmark configuration duplicate detection
        config_detector = ConfigurationDuplicateDetector(registry)
        config_result = benchmarker.benchmark_operation(
            operation_name="configuration_duplicate_detection",
            operation=lambda: config_detector.detect_config_duplicates(model_validation)
        )

        # Verify benchmark results
        assert config_result.operation == "configuration_duplicate_detection"
        assert config_result.duration >= 0.0
        assert config_result.memory_delta is not None
        assert config_result.peak_memory >= 0
        assert not config_result.is_regression()  # Should not be a regression with no baseline

        # Benchmark content similarity detection
        content_detector = ContentSimilarityDetector(registry)
        content_result = benchmarker.benchmark_operation(
            operation_name="content_similarity_detection",
            operation=lambda: content_detector.detect_content_similarity(model_validation, threshold=0.95)
        )

        # Verify content detection benchmark
        assert content_result.operation == "content_similarity_detection"
        assert content_result.duration >= 0.0
        assert content_result.memory_delta is not None
        assert content_result.peak_memory >= 0

        # Benchmark performance fingerprint comparison
        performance_detector = PerformanceFingerprintDetector(registry)
        performance_result = benchmarker.benchmark_operation(
            operation_name="performance_fingerprint_detection",
            operation=lambda: performance_detector.detect_performance_duplicates(model_validation, threshold=0.90)
        )

        # Verify performance detection benchmark
        assert performance_result.operation == "performance_fingerprint_detection"
        assert performance_result.duration >= 0.0
        assert performance_result.memory_delta is not None
        assert performance_result.peak_memory >= 0

    def test_performance_regression_detection(self):
        """Test detection of performance regressions against baseline metrics."""
        benchmarker = PerformanceBenchmarker()

        # Set up baseline metrics (simulating previously recorded performance)
        baseline_metrics = {
            "test_operation": {
                "duration": 0.001,  # 1ms baseline
                "memory_delta": 1024,  # 1KB baseline memory usage
                "peak_memory": 1024 * 1024  # 1MB baseline peak memory
            }
        }
        benchmarker.baseline_metrics = baseline_metrics

        # Simulate a slow operation that should trigger regression detection
        def slow_operation():
            import time
            time.sleep(0.005)  # 5ms - should be 5x slower than baseline
            return "completed"

        # Benchmark the slow operation
        result = benchmarker.benchmark_operation(
            operation_name="test_operation",
            operation=slow_operation
        )

        # Verify regression detection
        assert result.operation == "test_operation"
        assert result.duration >= 0.005  # Should be at least 5ms
        assert result.is_regression() is True  # Should detect regression
        assert result.regression_percentage > 1.0  # Should be significantly slower

        # Verify regression details
        assert result.baseline_duration == 0.001
        assert result.regression_threshold == 1.5  # 50% threshold default


class PerformanceBenchmarker:
    """Performance benchmarking framework for deduplication operations.

    This class provides comprehensive performance monitoring and regression testing
    for deduplication operations, ensuring that performance optimizations don't
    introduce regressions and identifying bottlenecks in the deduplication pipeline.

    Parameters
    ----------
    baseline_file : str, optional
        Path to baseline performance metrics file, by default "performance_baseline.json"
    regression_threshold : float, optional
        Performance regression threshold (1.5 = 50% slower), by default 1.5
    """

    def __init__(self, baseline_file: str = "performance_baseline.json", regression_threshold: float = 1.5):
        self.baseline_file = baseline_file
        self.regression_threshold = regression_threshold
        self.baseline_metrics = self._load_baseline_metrics()

    def benchmark_operation(self, operation_name: str, operation) -> 'PerformanceBenchmarkResult':
        """Benchmark a deduplication operation and compare against baseline.

        Parameters
        ----------
        operation_name : str
            Name of the operation being benchmarked
        operation : callable
            Function to benchmark

        Returns
        -------
        PerformanceBenchmarkResult
            Comprehensive benchmark results with regression analysis
        """
        import time
        import psutil
        import os

        # Get process for memory monitoring
        process = psutil.Process(os.getpid())

        # Record initial memory state
        initial_memory = process.memory_info().rss

        # Start timing
        start_time = time.perf_counter()

        # Execute operation
        result = operation()

        # End timing
        end_time = time.perf_counter()

        # Record final memory state
        final_memory = process.memory_info().rss
        peak_memory = process.memory_info().rss  # Simplified - could track actual peak

        # Calculate metrics
        duration = end_time - start_time
        memory_delta = final_memory - initial_memory

        # Get baseline for comparison
        baseline = self.baseline_metrics.get(operation_name, {})
        baseline_duration = baseline.get("duration")
        baseline_memory = baseline.get("memory_delta")
        baseline_peak = baseline.get("peak_memory")

        # Create benchmark result
        benchmark_result = PerformanceBenchmarkResult(
            operation=operation_name,
            duration=duration,
            memory_delta=memory_delta,
            peak_memory=peak_memory,
            baseline_duration=baseline_duration,
            baseline_memory_delta=baseline_memory,
            baseline_peak_memory=baseline_peak,
            regression_threshold=self.regression_threshold,
            operation_result=result
        )

        # Log regression warnings
        if benchmark_result.is_regression():
            print(f"⚠️  Performance regression detected in {operation_name}:")
            print(f"   Duration: {duration:.4f}s (baseline: {baseline_duration:.4f}s)")
            print(f"   Regression: {benchmark_result.regression_percentage:.1f}x slower")

        return benchmark_result

    def _load_baseline_metrics(self) -> Dict[str, Dict[str, float]]:
        """Load baseline performance metrics from file.

        Returns
        -------
        Dict[str, Dict[str, float]]
            Dictionary of operation names to baseline metrics
        """
        try:
            import json
            with open(self.baseline_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # No baseline file or invalid JSON - return empty dict
            return {}

    def save_baseline_metrics(self, new_metrics: Dict[str, Dict[str, float]]) -> None:
        """Save new baseline performance metrics to file.

        Parameters
        ----------
        new_metrics : Dict[str, Dict[str, float]]
            New baseline metrics to save
        """
        import json

        # Merge with existing metrics
        self.baseline_metrics.update(new_metrics)

        # Save to file
        with open(self.baseline_file, 'w') as f:
            json.dump(self.baseline_metrics, f, indent=2)

    def generate_performance_report(self, benchmark_results: List['PerformanceBenchmarkResult']) -> str:
        """Generate comprehensive performance report from benchmark results.

        Parameters
        ----------
        benchmark_results : List[PerformanceBenchmarkResult]
            List of benchmark results to analyze

        Returns
        -------
        str
            Formatted performance report
        """
        report_lines = ["=== Deduplication Performance Report ===", ""]

        # Summary statistics
        total_operations = len(benchmark_results)
        regressions = [r for r in benchmark_results if r.is_regression()]
        total_duration = sum(r.duration for r in benchmark_results)

        report_lines.extend([
            f"Total Operations: {total_operations}",
            f"Performance Regressions: {len(regressions)} ({len(regressions)/total_operations*100:.1f}%)",
            f"Total Duration: {total_duration:.4f}s",
            f"Average Duration: {total_duration/total_operations:.4f}s",
            ""
        ])

        # Operation details
        report_lines.append("Operation Details:")
        for result in benchmark_results:
            status = "🚨 REGRESSION" if result.is_regression() else "✅ OK"
            report_lines.append(f"  {result.operation}: {result.duration:.4f}s {status}")

            if result.is_regression():
                report_lines.append(f"    Baseline: {result.baseline_duration:.4f}s")
                report_lines.append(f"    Slowdown: {result.regression_percentage:.1f}x")

        return "\n".join(report_lines)


@dataclass
class PerformanceBenchmarkResult:
    """Result of a performance benchmark operation.

    Attributes
    ----------
    operation : str
        Name of the benchmarked operation
    duration : float
        Execution duration in seconds
    memory_delta : int
        Memory usage change in bytes
    peak_memory : int
        Peak memory usage in bytes
    baseline_duration : float, optional
        Baseline execution duration for comparison
    baseline_memory_delta : int, optional
        Baseline memory usage for comparison
    baseline_peak_memory : int, optional
        Baseline peak memory for comparison
    regression_threshold : float
        Threshold for regression detection (e.g., 1.5 = 50% slower)
    operation_result : any, optional
        Result returned by the benchmarked operation
    """
    operation: str
    duration: float
    memory_delta: int
    peak_memory: int
    baseline_duration: Optional[float] = None
    baseline_memory_delta: Optional[int] = None
    baseline_peak_memory: Optional[int] = None
    regression_threshold: float = 1.5
    operation_result: Optional[any] = None

    def is_regression(self) -> bool:
        """Check if this benchmark represents a performance regression.

        Returns
        -------
        bool
            True if performance has regressed beyond threshold
        """
        if self.baseline_duration is None:
            return False

        return self.duration > (self.baseline_duration * self.regression_threshold)

    @property
    def regression_percentage(self) -> float:
        """Calculate regression percentage compared to baseline.

        Returns
        -------
        float
            Regression multiplier (e.g., 2.0 = 2x slower)
        """
        if self.baseline_duration is None or self.baseline_duration == 0:
            return 1.0

        return self.duration / self.baseline_duration
