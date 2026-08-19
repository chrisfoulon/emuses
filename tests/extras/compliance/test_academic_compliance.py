"""
Test cases for academic compliance manager.

Tests academic research compliance including IRB tracking, FAIR principles,
funding compliance, and academic attribution features.
"""

import pytest
from datetime import datetime, date
from unittest.mock import Mock, MagicMock
from uuid import uuid4, UUID

from emuses.tools.academic_compliance import (
    AcademicComplianceManager,
    AcademicComplianceError,
    IRBStatus,
    FAIRCompliance,
    FundingCompliance
)
from emuses.multi_user_service.models import ModelRegistry, User


class TestAcademicComplianceManager:
    """Test suite for academic compliance manager."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def mock_user(self):
        """Mock user for testing."""
        user = Mock(spec=User)
        user.id = uuid4()
        user.email = "researcher@university.edu"
        user.is_active = True
        return user

    @pytest.fixture
    def mock_model(self):
        """Mock model for testing."""
        model = Mock(spec=ModelRegistry)
        model.id = uuid4()
        model.name = "Brain Lesion Prediction Model"
        model.description = "A comprehensive machine learning model for predicting brain lesion outcomes"
        model.tags = ["neuroscience", "machine-learning", "medical"]
        model.is_public = True
        model.metadata = {"format": "ONNX", "version": "1.2.0"}
        model.created_at = datetime(2024, 1, 15)
        model.updated_at = datetime(2024, 3, 10)
        return model

    @pytest.fixture
    def academic_compliance_manager(self, mock_db_session, mock_user):
        """Academic compliance manager instance."""
        return AcademicComplianceManager(mock_db_session, mock_user)

    def test_initialization(self, academic_compliance_manager, mock_user):
        """Test academic compliance manager initialization."""
        assert academic_compliance_manager.current_user == mock_user
        assert hasattr(academic_compliance_manager, 'academic_audit_logs')
        assert len(academic_compliance_manager.academic_audit_logs) == 0

    def test_validate_orcid_valid(self, academic_compliance_manager):
        """Test ORCID validation with valid identifiers."""
        valid_orcids = [
            "0000-0000-0000-0000",
            "0000-0002-1825-0097",
            "0000-0001-5109-3700",
            "0000-0002-1694-233X"
        ]
        
        for orcid in valid_orcids:
            assert academic_compliance_manager.validate_orcid(orcid), f"Failed for {orcid}"

    def test_validate_orcid_invalid(self, academic_compliance_manager):
        """Test ORCID validation with invalid identifiers."""
        invalid_orcids = [
            "0000-0000-0000",  # Too short
            "0000-0000-0000-000Y",  # Invalid character
            "1234-5678-9012-3456",  # Invalid format
            "0000 0000 0000 0000",  # Spaces instead of dashes
            ""  # Empty string
        ]
        
        for orcid in invalid_orcids:
            assert not academic_compliance_manager.validate_orcid(orcid), f"Incorrectly validated {orcid}"

    def test_track_irb_approval_pending(self, academic_compliance_manager):
        """Test tracking IRB approval in pending status."""
        irb_status = academic_compliance_manager.track_irb_approval(
            study_id="STUDY_2024_001",
            institution="University Medical Center"
        )
        
        assert isinstance(irb_status, IRBStatus)
        assert irb_status.study_id == "STUDY_2024_001"
        assert irb_status.institution == "University Medical Center"
        assert irb_status.status == "PENDING"
        assert irb_status.approval_number is None
        assert irb_status.approval_date is None
        assert len(academic_compliance_manager.academic_audit_logs) == 1

    def test_track_irb_approval_approved(self, academic_compliance_manager):
        """Test tracking IRB approval in approved status."""
        approval_date = date(2024, 2, 15)
        expiration_date = date(2025, 12, 31)  # Future date
        
        irb_status = academic_compliance_manager.track_irb_approval(
            study_id="STUDY_2024_002",
            institution="Research Institute",
            approval_number="IRB-2024-002",
            approval_date=approval_date,
            expiration_date=expiration_date
        )
        
        assert irb_status.status == "APPROVED"
        assert irb_status.approval_number == "IRB-2024-002"
        assert irb_status.approval_date == approval_date
        assert irb_status.expiration_date == expiration_date

    def test_track_irb_approval_expired(self, academic_compliance_manager):
        """Test tracking IRB approval with expired status."""
        approval_date = date(2023, 1, 1)
        expiration_date = date(2023, 12, 31)  # Expired
        
        irb_status = academic_compliance_manager.track_irb_approval(
            study_id="STUDY_2023_001",
            institution="Academic Hospital",
            approval_number="IRB-2023-001",
            approval_date=approval_date,
            expiration_date=expiration_date
        )
        
        assert irb_status.status == "EXPIRED"

    def test_validate_consent_coverage_compliant(self, academic_compliance_manager):
        """Test consent coverage validation with compliant scenarios."""
        data_scope = {
            'requires_sharing': False,
            'secondary_analysis': False,
            'cross_border': False
        }
        consent_scope = {
            'data_collection': True,
            'data_sharing': False,
            'secondary_use': False,
            'international_transfer': False
        }
        
        result = academic_compliance_manager.validate_consent_coverage(data_scope, consent_scope)
        assert result is True

    def test_validate_consent_coverage_non_compliant(self, academic_compliance_manager):
        """Test consent coverage validation with non-compliant scenarios."""
        data_scope = {
            'requires_sharing': True,  # Requires sharing
            'secondary_analysis': False,
            'cross_border': False
        }
        consent_scope = {
            'data_collection': True,
            'data_sharing': False,  # Sharing not consented
            'secondary_use': False,
            'international_transfer': False
        }
        
        result = academic_compliance_manager.validate_consent_coverage(data_scope, consent_scope)
        assert result is False

    def test_assess_fair_compliance_high_score(self, academic_compliance_manager, mock_model):
        """Test FAIR compliance assessment with high-scoring model."""
        academic_compliance_manager.db_session.query.return_value.filter.return_value.first.return_value = mock_model
        
        metadata = {
            'schema': 'neuroimaging_standard',
            'validation_data': 'included'
        }
        
        fair_result = academic_compliance_manager.assess_fair_compliance(
            model_id=mock_model.id,
            metadata=metadata
        )
        
        assert isinstance(fair_result, FAIRCompliance)
        assert fair_result.findable_score >= 75  # Good metadata
        assert fair_result.accessible_score >= 70  # Public model
        assert fair_result.interoperable_score >= 60  # Some standards
        assert fair_result.reusable_score >= 50  # Some documentation
        assert fair_result.overall_score > 60

    def test_assess_fair_compliance_model_not_found(self, academic_compliance_manager):
        """Test FAIR compliance assessment with non-existent model."""
        academic_compliance_manager.db_session.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(AcademicComplianceError, match="Model .* not found"):
            academic_compliance_manager.assess_fair_compliance(model_id=str(uuid4()))

    def test_track_data_provenance_success(self, academic_compliance_manager):
        """Test successful data provenance tracking."""
        model_id = uuid4()
        source_datasets = ["dataset_001", "dataset_002"]
        processing_steps = [
            {'operation': 'preprocessing', 'tool': 'FSL'},
            {'operation': 'feature_extraction', 'tool': 'FreeSurfer'},
            {'operation': 'model_training', 'tool': 'scikit-learn'}
        ]
        quality_metrics = {
            'completeness': 98.5,
            'consistency': 95.2,
            'accuracy': 92.1
        }
        
        result = academic_compliance_manager.track_data_provenance(
            model_id=model_id,
            source_datasets=source_datasets,
            processing_steps=processing_steps,
            quality_metrics=quality_metrics
        )
        
        assert result['status'] == 'success'
        assert 'provenance_chain' in result
        provenance = result['provenance_chain']
        assert provenance['model_id'] == str(model_id)
        assert provenance['source_datasets'] == source_datasets
        assert len(provenance['processing_steps']) == 3
        assert provenance['quality_metrics'] == quality_metrics

    def test_track_data_provenance_missing_operation(self, academic_compliance_manager):
        """Test data provenance tracking with missing operation field."""
        model_id = uuid4()
        source_datasets = ["dataset_001"]
        processing_steps = [
            {'tool': 'FSL'},  # Missing 'operation' field
        ]
        
        with pytest.raises(AcademicComplianceError, match="Processing step .* missing 'operation' field"):
            academic_compliance_manager.track_data_provenance(
                model_id=model_id,
                source_datasets=source_datasets,
                processing_steps=processing_steps
            )

    def test_validate_funding_compliance_nih(self, academic_compliance_manager):
        """Test NIH funding compliance validation."""
        project_data = {
            'data_sharing_plan': True,
            'public_repository': True,
            'project_start_date': '2024-01-01T00:00:00'
        }
        
        compliance = academic_compliance_manager.validate_funding_compliance(
            agency='NIH',
            grant_number='R01-NS123456',
            project_data=project_data
        )
        
        assert isinstance(compliance, FundingCompliance)
        assert compliance.agency == 'NIH'
        assert compliance.grant_number == 'R01-NS123456'
        assert compliance.compliance_status == 'COMPLIANT'
        assert 'data_sharing_plan' in compliance.requirements
        assert compliance.next_report_due is not None

    def test_validate_funding_compliance_nsf_non_compliant(self, academic_compliance_manager):
        """Test NSF funding compliance validation with non-compliant project."""
        project_data = {
            'data_sharing_plan': False,  # Missing required DMP
            'project_start_date': '2024-01-01T00:00:00'
        }
        
        compliance = academic_compliance_manager.validate_funding_compliance(
            agency='NSF',
            grant_number='DBI-2024001',
            project_data=project_data
        )
        
        assert compliance.agency == 'NSF'
        assert compliance.compliance_status == 'PARTIAL'
        assert 'data_management_plan' in compliance.requirements

    def test_validate_funding_compliance_unsupported_agency(self, academic_compliance_manager):
        """Test funding compliance validation with unsupported agency."""
        with pytest.raises(AcademicComplianceError, match="Unsupported funding agency"):
            academic_compliance_manager.validate_funding_compliance(
                agency='UNKNOWN_AGENCY',
                grant_number='TEST-001',
                project_data={}
            )

    def test_generate_citation_metadata_apa(self, academic_compliance_manager, mock_model):
        """Test citation metadata generation in APA format."""
        academic_compliance_manager.db_session.query.return_value.filter.return_value.first.return_value = mock_model
        
        authors = [
            {'name': 'Smith, John', 'orcid': '0000-0002-1825-0097', 'affiliation': 'University A'},
            {'name': 'Doe, Jane', 'orcid': '0000-0001-5109-3700', 'affiliation': 'University B'}
        ]
        
        result = academic_compliance_manager.generate_citation_metadata(
            model_id=mock_model.id,
            authors=authors,
            citation_format='APA'
        )
        
        assert result['status'] == 'success'
        assert 'metadata' in result
        assert 'formatted_citations' in result
        
        metadata = result['metadata']
        assert metadata['title'] == mock_model.name
        assert len(metadata['authors']) == 2
        assert metadata['year'] == 2024
        
        apa_citation = result['formatted_citations']['APA']
        assert 'Smith, John, Doe, Jane' in apa_citation
        assert '(2024)' in apa_citation
        assert mock_model.name in apa_citation

    def test_generate_citation_metadata_bibtex(self, academic_compliance_manager, mock_model):
        """Test citation metadata generation in BibTeX format."""
        academic_compliance_manager.db_session.query.return_value.filter.return_value.first.return_value = mock_model
        
        authors = [{'name': 'Smith, John'}]
        
        result = academic_compliance_manager.generate_citation_metadata(
            model_id=mock_model.id,
            authors=authors,
            citation_format='BibTeX'
        )
        
        bibtex_citation = result['formatted_citations']['BibTeX']
        assert '@misc{' in bibtex_citation
        assert 'title={' + mock_model.name + '}' in bibtex_citation
        assert 'author={Smith, John}' in bibtex_citation
        assert 'year={2024}' in bibtex_citation

    def test_generate_citation_metadata_invalid_orcid(self, academic_compliance_manager, mock_model):
        """Test citation metadata generation with invalid ORCID."""
        academic_compliance_manager.db_session.query.return_value.filter.return_value.first.return_value = mock_model
        
        authors = [
            {'name': 'Smith, John', 'orcid': 'invalid-orcid'}
        ]
        
        with pytest.raises(AcademicComplianceError, match="Invalid ORCID"):
            academic_compliance_manager.generate_citation_metadata(
                model_id=mock_model.id,
                authors=authors
            )

    def test_generate_citation_metadata_missing_author_name(self, academic_compliance_manager, mock_model):
        """Test citation metadata generation with missing author name."""
        academic_compliance_manager.db_session.query.return_value.filter.return_value.first.return_value = mock_model
        
        authors = [
            {'orcid': '0000-0002-1825-0097'}  # Missing name
        ]
        
        with pytest.raises(AcademicComplianceError, match="Author .* missing 'name' field"):
            academic_compliance_manager.generate_citation_metadata(
                model_id=mock_model.id,
                authors=authors
            )

    def test_get_academic_audit_logs_no_filter(self, academic_compliance_manager):
        """Test retrieving academic audit logs without filters."""
        # Generate some audit logs
        academic_compliance_manager.track_irb_approval("STUDY_001", "University A")
        academic_compliance_manager.track_data_provenance(
            model_id=uuid4(),
            source_datasets=["ds1"],
            processing_steps=[{'operation': 'test'}]
        )
        
        logs = academic_compliance_manager.get_academic_audit_logs()
        assert len(logs) == 2
        assert all('id' in log for log in logs)
        assert all('timestamp' in log for log in logs)

    def test_get_academic_audit_logs_with_filters(self, academic_compliance_manager):
        """Test retrieving academic audit logs with filters."""
        # Generate different types of audit logs
        academic_compliance_manager.track_irb_approval("STUDY_001", "University A")
        academic_compliance_manager.track_data_provenance(
            model_id=uuid4(),
            source_datasets=["ds1"],
            processing_steps=[{'operation': 'test'}]
        )
        
        # Filter by action
        irb_logs = academic_compliance_manager.get_academic_audit_logs(action_filter="IRB")
        assert len(irb_logs) == 1
        assert 'IRB_TRACKING' in irb_logs[0]['action']
        
        provenance_logs = academic_compliance_manager.get_academic_audit_logs(action_filter="PROVENANCE")
        assert len(provenance_logs) == 1
        assert 'PROVENANCE_TRACKING' in provenance_logs[0]['action']

    def test_get_academic_audit_logs_limit(self, academic_compliance_manager):
        """Test audit log retrieval with limit."""
        # Generate multiple audit logs
        for i in range(5):
            academic_compliance_manager.track_irb_approval(f"STUDY_{i}", "University")
        
        logs = academic_compliance_manager.get_academic_audit_logs(limit=3)
        assert len(logs) == 3

    def test_error_handling_database_failure(self, academic_compliance_manager):
        """Test error handling with database failures."""
        # Mock database session to raise exception
        academic_compliance_manager.db_session.query.side_effect = Exception("Database connection failed")
        
        with pytest.raises(AcademicComplianceError):
            academic_compliance_manager.assess_fair_compliance(model_id=str(uuid4()))

    def test_academic_audit_log_structure(self, academic_compliance_manager):
        """Test academic audit log entry structure."""
        academic_compliance_manager.track_irb_approval(
            study_id="STUDY_TEST",
            institution="Test University"
        )
        
        logs = academic_compliance_manager.get_academic_audit_logs()
        assert len(logs) == 1
        
        log = logs[0]
        required_fields = ['id', 'user_id', 'action', 'details', 'institution_id', 'timestamp']
        for field in required_fields:
            assert field in log
            
        assert log['action'] == 'IRB_TRACKING'
        assert 'study_id' in log['details']
        assert log['details']['study_id'] == 'STUDY_TEST'


class TestAcademicComplianceIntegration:
    """Integration tests for academic compliance with existing systems."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session for integration testing."""
        return Mock()

    @pytest.fixture
    def mock_user(self):
        """Mock user for integration testing."""
        user = Mock(spec=User)
        user.id = uuid4()
        user.email = "integration@test.edu"
        return user

    @pytest.fixture
    def academic_compliance_manager(self, mock_db_session, mock_user):
        """Academic compliance manager for integration testing."""
        return AcademicComplianceManager(mock_db_session, mock_user)

    def test_gdpr_integration(self, academic_compliance_manager):
        """Test integration with GDPR compliance functionality."""
        # Academic compliance manager should inherit from GDPR manager
        assert hasattr(academic_compliance_manager, 'db_session')
        assert hasattr(academic_compliance_manager, 'current_user')
        
        # Should have academic audit logs and inherit GDPR functionality
        assert hasattr(academic_compliance_manager, 'academic_audit_logs')  # Academic logs
        assert hasattr(academic_compliance_manager, 'export_user_data')  # GDPR method

    def test_comprehensive_compliance_workflow(self, academic_compliance_manager, mock_db_session):
        """Test comprehensive academic compliance workflow."""
        model_id = uuid4()
        
        # Mock model for database query
        mock_model = Mock(spec=ModelRegistry)
        mock_model.id = model_id
        mock_model.name = "Comprehensive Test Model"
        mock_model.description = "A comprehensive test model for academic compliance validation"
        mock_model.tags = ["test", "comprehensive"]
        mock_model.is_public = True
        mock_model.metadata = {"format": "ONNX"}
        mock_model.created_at = datetime.now()
        mock_model.updated_at = datetime.now()
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_model
        
        # 1. Track IRB approval
        irb_status = academic_compliance_manager.track_irb_approval(
            study_id="COMPREHENSIVE_001",
            institution="Test University",
            approval_number="IRB-2024-001",
            approval_date=date.today()
        )
        assert irb_status.status == "APPROVED"
        
        # 2. Track data provenance
        provenance_result = academic_compliance_manager.track_data_provenance(
            model_id=model_id,
            source_datasets=["test_dataset"],
            processing_steps=[{'operation': 'test_processing'}]
        )
        assert provenance_result['status'] == 'success'
        
        # 3. Assess FAIR compliance
        fair_result = academic_compliance_manager.assess_fair_compliance(model_id=model_id)
        assert isinstance(fair_result, FAIRCompliance)
        
        # 4. Validate funding compliance
        funding_result = academic_compliance_manager.validate_funding_compliance(
            agency='NSF',
            grant_number='TEST-001',
            project_data={'data_management_plan': True}
        )
        assert funding_result.compliance_status == 'COMPLIANT'
        
        # 5. Generate citation metadata
        citation_result = academic_compliance_manager.generate_citation_metadata(
            model_id=model_id,
            authors=[{'name': 'Test Author'}]
        )
        assert citation_result['status'] == 'success'
        
        # Verify all operations were logged
        logs = academic_compliance_manager.get_academic_audit_logs()
        assert len(logs) == 5
        
        log_actions = [log['action'] for log in logs]
        expected_actions = [
            'CITATION_GENERATION',
            'FUNDING_COMPLIANCE', 
            'FAIR_ASSESSMENT',
            'PROVENANCE_TRACKING',
            'IRB_TRACKING'
        ]
        for action in expected_actions:
            assert action in log_actions