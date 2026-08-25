"""Tests for academic and research features."""
import pytest
import uuid
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from sqlalchemy.orm import Session

from emuses.extras.academic_features import (
    AcademicFeatureManager,
    AcademicConfig,
    AcademicError,
    DOIGenerator,
    ProvenanceTracker,
    CollaborationManager,
    LicenseManager,
    CitationData,
    ProvenanceMetadata,
    CollaborationRequest,
    ModelLicense
)


class TestAcademicFeatureManager:
    """Tests for AcademicFeatureManager class."""
    
    @pytest.fixture
    def db_session(self):
        """Mock database session for testing."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def academic_config(self):
        """Create AcademicConfig for testing."""
        return AcademicConfig(
            enable_doi_generation=True,
            enable_provenance_tracking=True,
            enable_collaboration=True,
            doi_prefix="10.5281/zenodo",
            require_license=True,
            default_license="MIT",
            enable_citation_tracking=True
        )
    
    @pytest.fixture
    def academic_manager(self, db_session, academic_config):
        """Create AcademicFeatureManager instance."""
        return AcademicFeatureManager(db_session, academic_config)
    
    def test_academic_manager_initialization(self, academic_manager):
        """Test AcademicFeatureManager initialization."""
        assert academic_manager.db_session is not None
        assert academic_manager.config is not None
        assert isinstance(academic_manager.config, AcademicConfig)
        assert isinstance(academic_manager.doi_generator, DOIGenerator)
        assert isinstance(academic_manager.provenance_tracker, ProvenanceTracker)
        assert isinstance(academic_manager.collaboration_manager, CollaborationManager)
        assert isinstance(academic_manager.license_manager, LicenseManager)
    
    def test_generate_doi(self, academic_manager, db_session):
        """Test DOI generation for a model."""
        model_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        # Mock model exists
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.name = "test_model"
        mock_model.owner_id = user_id
        db_session.query().filter().first.return_value = mock_model
        
        citation_data = CitationData(
            title="Test ML Model",
            authors=["John Doe", "Jane Smith"],
            description="A test machine learning model for research",
            keywords=["machine-learning", "test", "research"],
            publication_year=2024
        )
        
        result = academic_manager.generate_doi(model_id, user_id, citation_data)
        
        assert result["success"] is True
        assert "doi" in result
        assert result["doi"].startswith("10.5281/zenodo")
        assert result["citation_format"] is not None
    
    def test_track_provenance(self, academic_manager, db_session):
        """Test provenance tracking for a model."""
        model_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        # Mock model exists
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.name = "test_model"
        db_session.query().filter().first.return_value = mock_model
        
        provenance_data = ProvenanceMetadata(
            dataset_sources=["iris", "wine"],
            preprocessing_steps=["standardization", "feature_selection"],
            model_architecture="random_forest",
            hyperparameters={"n_estimators": 100, "max_depth": 10},
            training_environment="Python 3.9, scikit-learn 1.0",
            code_repository="https://github.com/user/model-repo",
            training_duration=3600
        )
        
        result = academic_manager.track_provenance(model_id, user_id, provenance_data)
        
        assert result["success"] is True
        assert result["provenance_id"] is not None
        assert result["reproducibility_score"] > 0
    
    def test_create_collaboration(self, academic_manager, db_session):
        """Test creating research collaboration."""
        model_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        collaborator_id = uuid.uuid4()
        
        # Mock model exists
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.owner_id = owner_id
        db_session.query().filter().first.return_value = mock_model
        
        collaboration_data = CollaborationRequest(
            collaborator_id=collaborator_id,
            role="contributor",
            permissions=["read", "benchmark"],
            message="I'd like to collaborate on this model",
            proposed_contribution="Performance optimization"
        )
        
        result = academic_manager.create_collaboration(model_id, owner_id, collaboration_data)
        
        assert result["success"] is True
        assert result["collaboration_id"] is not None
        assert result["status"] == "pending"
    
    def test_set_model_license(self, academic_manager, db_session):
        """Test setting license for a model."""
        model_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        # Mock model exists
        mock_model = Mock()
        mock_model.id = model_id
        mock_model.owner_id = user_id
        db_session.query().filter().first.return_value = mock_model
        
        license_data = ModelLicense(
            license_type="Apache-2.0",
            license_text="Apache License 2.0...",
            commercial_use=True,
            attribution_required=True,
            share_alike=False,
            custom_terms="Model may not be used for harmful purposes"
        )
        
        result = academic_manager.set_model_license(model_id, user_id, license_data)
        
        assert result["success"] is True
        assert result["license_type"] == "Apache-2.0"
        assert result["commercial_use"] is True
    
    def test_get_citation_metrics(self, academic_manager, db_session):
        """Test retrieving citation metrics for a model."""
        model_id = uuid.uuid4()
        
        # Mock citation data
        mock_citations = [
            Mock(citing_paper="Paper 1", citation_date=datetime.utcnow()),
            Mock(citing_paper="Paper 2", citation_date=datetime.utcnow()),
            Mock(citing_paper="Paper 3", citation_date=datetime.utcnow())
        ]
        db_session.query().filter().all.return_value = mock_citations
        
        metrics = academic_manager.get_citation_metrics(model_id)
        
        assert metrics["total_citations"] == 3
        assert metrics["h_index"] >= 0
        assert "recent_citations" in metrics


class TestDOIGenerator:
    """Tests for DOI generator functionality."""
    
    @pytest.fixture
    def doi_generator(self):
        """Create DOI generator instance."""
        return DOIGenerator(prefix="10.5281/zenodo")
    
    def test_generate_doi(self, doi_generator):
        """Test DOI generation."""
        model_id = uuid.uuid4()
        doi = doi_generator.generate_doi(model_id)
        
        assert doi.startswith("10.5281/zenodo")
        # Check that DOI has the correct format
        parts = doi.split(".")
        assert len(parts) >= 3
        assert parts[-1]  # Should have a suffix
    
    def test_format_citation(self, doi_generator):
        """Test citation formatting."""
        citation_data = CitationData(
            title="Test Model",
            authors=["Author 1", "Author 2"],
            description="Test description",
            keywords=["test"],
            publication_year=2024
        )
        doi = "10.5281/zenodo.123456"
        
        citation = doi_generator.format_citation(citation_data, doi)
        
        assert "Author 1" in citation
        assert "Test Model" in citation
        assert "2024" in citation
        assert doi in citation


class TestProvenanceTracker:
    """Tests for provenance tracking functionality."""
    
    @pytest.fixture
    def provenance_tracker(self):
        """Create provenance tracker instance."""
        return ProvenanceTracker()
    
    def test_calculate_reproducibility_score(self, provenance_tracker):
        """Test reproducibility score calculation."""
        metadata = ProvenanceMetadata(
            dataset_sources=["iris"],
            preprocessing_steps=["standardization"],
            model_architecture="random_forest",
            hyperparameters={"n_estimators": 100},
            training_environment="Python 3.9",
            code_repository="https://github.com/user/repo",
            training_duration=3600
        )
        
        score = provenance_tracker.calculate_reproducibility_score(metadata)
        
        assert 0 <= score <= 100
        assert score > 50  # Should be high with good metadata
    
    def test_generate_provenance_graph(self, provenance_tracker):
        """Test provenance graph generation."""
        metadata = ProvenanceMetadata(
            dataset_sources=["iris", "wine"],
            preprocessing_steps=["standardization", "feature_selection"],
            model_architecture="random_forest",
            hyperparameters={},
            training_environment="Python 3.9",
            code_repository="",
            training_duration=0
        )
        
        graph = provenance_tracker.generate_provenance_graph(metadata)
        
        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) > 0


class TestCollaborationManager:
    """Tests for collaboration management functionality."""
    
    @pytest.fixture
    def collaboration_manager(self):
        """Create collaboration manager instance."""
        return CollaborationManager()
    
    def test_create_collaboration_request(self, collaboration_manager):
        """Test collaboration request creation."""
        request_data = CollaborationRequest(
            collaborator_id=uuid.uuid4(),
            role="contributor",
            permissions=["read", "benchmark"],
            message="Test collaboration",
            proposed_contribution="Testing"
        )
        
        collaboration_id = collaboration_manager.create_collaboration_request(
            uuid.uuid4(), request_data
        )
        
        assert collaboration_id is not None
        assert isinstance(collaboration_id, uuid.UUID)
    
    def test_evaluate_collaboration_request(self, collaboration_manager):
        """Test collaboration request evaluation."""
        request_data = CollaborationRequest(
            collaborator_id=uuid.uuid4(),
            role="contributor",
            permissions=["read"],
            message="Test",
            proposed_contribution="Testing"
        )
        
        evaluation = collaboration_manager.evaluate_collaboration_request(request_data)
        
        assert "risk_score" in evaluation
        assert "recommendations" in evaluation
        assert 0 <= evaluation["risk_score"] <= 100


class TestLicenseManager:
    """Tests for license management functionality."""
    
    @pytest.fixture
    def license_manager(self):
        """Create license manager instance."""
        return LicenseManager()
    
    def test_validate_license(self, license_manager):
        """Test license validation."""
        license_data = ModelLicense(
            license_type="MIT",
            license_text="MIT License...",
            commercial_use=True,
            attribution_required=True,
            share_alike=False,
            custom_terms=""
        )
        
        is_valid, issues = license_manager.validate_license(license_data)
        
        assert is_valid is True
        assert len(issues) == 0
    
    def test_get_license_compatibility(self, license_manager):
        """Test license compatibility checking."""
        license1 = "MIT"
        license2 = "Apache-2.0"
        
        compatibility = license_manager.get_license_compatibility(license1, license2)
        
        assert "compatible" in compatibility
        assert "restrictions" in compatibility
    
    def test_generate_license_text(self, license_manager):
        """Test license text generation."""
        license_data = ModelLicense(
            license_type="MIT",
            license_text="",
            commercial_use=True,
            attribution_required=True,
            share_alike=False,
            custom_terms="No harmful use"
        )
        
        license_text = license_manager.generate_license_text(license_data, "Test Model", "John Doe")
        
        assert "MIT" in license_text
        assert "Test Model" in license_text
        assert "John Doe" in license_text


class TestAcademicConfig:
    """Tests for AcademicConfig class."""
    
    def test_default_config(self):
        """Test default academic configuration."""
        config = AcademicConfig()
        
        assert config.enable_doi_generation is True
        assert config.enable_provenance_tracking is True
        assert config.doi_prefix == "10.5281/zenodo"
        assert config.default_license == "MIT"
    
    def test_custom_config(self):
        """Test custom academic configuration."""
        config = AcademicConfig(
            enable_doi_generation=False,
            doi_prefix="10.1000/custom",
            require_license=False,
            default_license="Apache-2.0"
        )
        
        assert config.enable_doi_generation is False
        assert config.doi_prefix == "10.1000/custom"
        assert config.require_license is False
        assert config.default_license == "Apache-2.0"


class TestCitationData:
    """Tests for CitationData dataclass."""
    
    def test_citation_data_initialization(self):
        """Test CitationData initialization."""
        citation = CitationData(
            title="Test Model",
            authors=["Author 1", "Author 2"],
            description="Test description",
            keywords=["ml", "test"],
            publication_year=2024
        )
        
        assert citation.title == "Test Model"
        assert len(citation.authors) == 2
        assert citation.publication_year == 2024


class TestProvenanceMetadata:
    """Tests for ProvenanceMetadata dataclass."""
    
    def test_provenance_metadata_initialization(self):
        """Test ProvenanceMetadata initialization."""
        metadata = ProvenanceMetadata(
            dataset_sources=["iris"],
            preprocessing_steps=["standardization"],
            model_architecture="random_forest",
            hyperparameters={"n_estimators": 100},
            training_environment="Python 3.9",
            code_repository="https://github.com/user/repo",
            training_duration=3600
        )
        
        assert len(metadata.dataset_sources) == 1
        assert metadata.model_architecture == "random_forest"
        assert metadata.training_duration == 3600


class TestCollaborationRequest:
    """Tests for CollaborationRequest dataclass."""
    
    def test_collaboration_request_initialization(self):
        """Test CollaborationRequest initialization."""
        request = CollaborationRequest(
            collaborator_id=uuid.uuid4(),
            role="contributor",
            permissions=["read", "write"],
            message="Test collaboration",
            proposed_contribution="Testing"
        )
        
        assert isinstance(request.collaborator_id, uuid.UUID)
        assert request.role == "contributor"
        assert len(request.permissions) == 2


class TestModelLicense:
    """Tests for ModelLicense dataclass."""
    
    def test_model_license_initialization(self):
        """Test ModelLicense initialization."""
        license_data = ModelLicense(
            license_type="MIT",
            license_text="MIT License...",
            commercial_use=True,
            attribution_required=True,
            share_alike=False,
            custom_terms=""
        )
        
        assert license_data.license_type == "MIT"
        assert license_data.commercial_use is True
        assert license_data.share_alike is False