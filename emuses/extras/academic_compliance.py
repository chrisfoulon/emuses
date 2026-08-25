"""
Academic compliance manager for EMUSES research data.

This module provides AcademicComplianceManager class for handling academic
research compliance including IRB tracking, FAIR principles, funding
compliance, and academic attribution.
"""

import logging
import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Union, NamedTuple
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from emuses.multi_user_service.models import ModelRegistry, User
from emuses.extras.gdpr_compliance import GDPRComplianceManager

logger = logging.getLogger(__name__)


class AcademicComplianceError(Exception):
    """Custom exception for academic compliance-related errors."""
    pass


class IRBStatus(NamedTuple):
    """IRB approval status information."""
    study_id: str
    institution: str
    approval_number: Optional[str]
    status: str  # 'APPROVED', 'PENDING', 'EXPIRED', 'DENIED'
    approval_date: Optional[date]
    expiration_date: Optional[date]
    consent_scope: Dict[str, Any]


class FAIRCompliance(NamedTuple):
    """FAIR principles compliance assessment."""
    findable_score: int  # 0-100
    accessible_score: int  # 0-100
    interoperable_score: int  # 0-100
    reusable_score: int  # 0-100
    overall_score: int  # 0-100
    recommendations: List[str]


class FundingCompliance(NamedTuple):
    """Funding agency compliance information."""
    agency: str  # 'NIH', 'NSF', 'EU_HORIZON', etc.
    grant_number: str
    compliance_status: str  # 'COMPLIANT', 'PARTIAL', 'NON_COMPLIANT'
    requirements: Dict[str, Any]
    next_report_due: Optional[date]


class AcademicAuditLog:
    """Audit log model for academic compliance operations."""

    def __init__(self, user_id: str, action: str, details: Dict[str, Any],
                 institution_id: Optional[str] = None):
        """Initialize academic audit log entry."""
        self.user_id = user_id
        self.action = action
        self.details = details
        self.institution_id = institution_id
        self.timestamp = datetime.utcnow()
        self.id = str(uuid4())


class AcademicComplianceManager(GDPRComplianceManager):
    """Manager for academic research compliance operations."""

    # Academic compliance validation patterns
    ORCID_PATTERN = re.compile(r'^0{4}-\d{4}-\d{4}-\d{3}[\dX]$')

    # Supported funding agencies
    FUNDING_AGENCIES = [
        'NIH', 'NSF', 'EU_HORIZON', 'WELLCOME', 'DFG', 'CIHR', 'ARC', 'JSPS'
    ]

    def __init__(self, db_session: Session, current_user: User):
        """Initialize academic compliance manager."""
        super().__init__(db_session, current_user)
        self.academic_audit_logs: List[AcademicAuditLog] = []

    def _log_academic_operation(self, action: str, details: Dict[str, Any],
                                institution_id: Optional[str] = None) -> None:
        """Log academic compliance operation for audit trail."""
        audit_entry = AcademicAuditLog(
            user_id=str(self.current_user.id),
            action=action,
            details=details,
            institution_id=institution_id
        )
        self.academic_audit_logs.append(audit_entry)

    def validate_orcid(self, orcid: str) -> bool:
        """Validate ORCID identifier format."""
        return bool(self.ORCID_PATTERN.match(orcid.strip()))

    def track_irb_approval(self, study_id: str, institution: str,
                           approval_number: Optional[str] = None,
                           approval_date: Optional[date] = None,
                           expiration_date: Optional[date] = None,
                           consent_scope: Optional[Dict[str, Any]] = None) -> IRBStatus:
        """Track IRB approval status for research study."""
        try:
            # Determine status based on approval information
            if approval_number and approval_date:
                if expiration_date and expiration_date < date.today():
                    status = 'EXPIRED'
                else:
                    status = 'APPROVED'
            else:
                status = 'PENDING'

            # Default consent scope
            if consent_scope is None:
                consent_scope = {
                    'data_collection': True,
                    'data_sharing': False,
                    'secondary_use': False,
                    'international_transfer': False
                }

            irb_status = IRBStatus(
                study_id=study_id,
                institution=institution,
                approval_number=approval_number,
                status=status,
                approval_date=approval_date,
                expiration_date=expiration_date,
                consent_scope=consent_scope
            )

            self._log_academic_operation(
                action='IRB_TRACKING',
                details={
                    'study_id': study_id,
                    'institution': institution,
                    'status': status,
                    'approval_number': approval_number
                }
            )

            return irb_status

        except Exception as e:
            logger.error(f"Failed to track IRB approval for study {study_id}: {str(e)}")
            raise AcademicComplianceError(f"IRB tracking failed: {str(e)}")

    def validate_consent_coverage(self, data_scope: Dict[str, Any],
                                  consent_scope: Dict[str, Any]) -> bool:
        """Validate that data usage is covered by informed consent."""
        try:
            # Check key consent areas
            consent_checks = [
                ('data_sharing', data_scope.get('requires_sharing', False)),
                ('secondary_use', data_scope.get('secondary_analysis', False)),
                ('international_transfer', data_scope.get('cross_border', False))
            ]

            for consent_key, data_requirement in consent_checks:
                if data_requirement and not consent_scope.get(consent_key, False):
                    logger.warning(f"Data usage requires {consent_key} but consent not obtained")
                    return False

            self._log_academic_operation(
                action='CONSENT_VALIDATION',
                details={
                    'data_scope': data_scope,
                    'consent_scope': consent_scope,
                    'validation_result': True
                }
            )

            return True

        except Exception as e:
            logger.error(f"Consent validation failed: {str(e)}")
            return False

    def assess_fair_compliance(self, model_id: Union[str, UUID],
                               metadata: Optional[Dict[str, Any]] = None) -> FAIRCompliance:
        """Assess FAIR principles compliance for a model."""
        try:
            # Get model from database
            if isinstance(model_id, str):
                model_id = UUID(model_id)

            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == model_id
            ).first()

            if not model:
                raise AcademicComplianceError(f"Model {model_id} not found")

            if metadata is None:
                metadata = {}

            # Assess components
            findable_score = self._assess_findable(model)
            accessible_score = self._assess_accessible(model)
            interoperable_score = self._assess_interoperable(model, metadata)
            reusable_score = self._assess_reusable(model, metadata)

            overall_score = int((findable_score + accessible_score +
                                interoperable_score + reusable_score) / 4)

            recommendations = self._generate_recommendations(model, metadata)

            fair_compliance = FAIRCompliance(
                findable_score=findable_score,
                accessible_score=accessible_score,
                interoperable_score=interoperable_score,
                reusable_score=reusable_score,
                overall_score=overall_score,
                recommendations=recommendations
            )

            self._log_academic_operation(
                action='FAIR_ASSESSMENT',
                details={
                    'model_id': str(model_id),
                    'overall_score': overall_score
                }
            )

            return fair_compliance

        except Exception as e:
            logger.error(f"FAIR assessment failed for model {model_id}: {str(e)}")
            raise AcademicComplianceError(f"FAIR assessment failed: {str(e)}")

    def _assess_findable(self, model: ModelRegistry) -> int:
        """Assess Findable component of FAIR principles."""
        score = 0
        if model.name and len(model.name) > 5:
            score += 25
        if model.description and len(model.description) > 50:
            score += 25
        if model.tags and len(model.tags) > 0:
            score += 25
        if model.id:
            score += 25
        return score

    def _assess_accessible(self, model: ModelRegistry) -> int:
        """Assess Accessible component of FAIR principles."""
        score = 0
        if model.is_public:
            score += 50
        score += 30  # Default protocols exist
        if model.metadata:
            score += 20
        return score

    def _assess_interoperable(self, model: ModelRegistry, metadata: Dict[str, Any]) -> int:
        """Assess Interoperable component of FAIR principles."""
        score = 0
        if hasattr(model, 'format') and model.format in ['ONNX', 'PyTorch', 'TensorFlow']:
            score += 40
        else:
            score += 20
        if metadata and 'schema' in metadata:
            score += 30
        score += 30  # EMUSES API
        return score

    def _assess_reusable(self, model: ModelRegistry, metadata: Dict[str, Any]) -> int:
        """Assess Reusable component of FAIR principles."""
        score = 0
        if hasattr(model, 'license') and model.license:
            score += 25
        if model.created_at and model.updated_at:
            score += 25
        if model.description and len(model.description) > 100:
            score += 25
        if metadata and 'validation_data' in metadata:
            score += 25
        return score

    def _generate_recommendations(self, model: ModelRegistry, metadata: Dict[str, Any]) -> List[str]:
        """Generate FAIR compliance recommendations."""
        recommendations = []

        if not model.name or len(model.name) <= 5:
            recommendations.append("Add descriptive model name")
        if not model.description or len(model.description) <= 50:
            recommendations.append("Add detailed description")
        if not model.tags or len(model.tags) == 0:
            recommendations.append("Add descriptive tags")
        if not model.is_public:
            recommendations.append("Consider making model public")
        if not model.metadata:
            recommendations.append("Add comprehensive metadata")
        if not metadata or 'schema' not in metadata:
            recommendations.append("Use standardized schemas")
        if not (hasattr(model, 'license') and model.license):
            recommendations.append("Add license information")

        return recommendations

    def track_data_provenance(self, model_id: Union[str, UUID],
                              source_datasets: List[str],
                              processing_steps: List[Dict[str, Any]],
                              quality_metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Track complete data lineage from raw data to model outputs."""
        try:
            if isinstance(model_id, str):
                model_id = UUID(model_id)

            # Validate processing steps
            for i, step in enumerate(processing_steps):
                if 'operation' not in step:
                    raise AcademicComplianceError(f"Processing step {i} missing 'operation' field")
                if 'timestamp' not in step:
                    step['timestamp'] = datetime.utcnow().isoformat()

            if quality_metrics is None:
                quality_metrics = {
                    'completeness': 95.0,
                    'consistency': 90.0,
                    'accuracy': 85.0
                }

            provenance_chain = {
                'model_id': str(model_id),
                'source_datasets': source_datasets,
                'processing_steps': processing_steps,
                'quality_metrics': quality_metrics,
                'provenance_id': str(uuid4()),
                'created_at': datetime.utcnow().isoformat(),
                'created_by': str(self.current_user.id)
            }

            self._log_academic_operation(
                action='PROVENANCE_TRACKING',
                details={
                    'model_id': str(model_id),
                    'source_count': len(source_datasets),
                    'processing_steps': len(processing_steps)
                }
            )

            return {
                'status': 'success',
                'provenance_chain': provenance_chain,
                'message': 'Data provenance successfully tracked'
            }

        except Exception as e:
            logger.error(f"Provenance tracking failed for model {model_id}: {str(e)}")
            raise AcademicComplianceError(f"Provenance tracking failed: {str(e)}")

    def validate_funding_compliance(self, agency: str, grant_number: str,
                                    project_data: Dict[str, Any]) -> FundingCompliance:
        """Validate funding agency compliance requirements."""
        try:
            if agency not in self.FUNDING_AGENCIES:
                raise AcademicComplianceError(f"Unsupported funding agency: {agency}")

            requirements = self._get_agency_requirements(agency)
            compliance_status = self._assess_compliance_status(agency, project_data)

            next_report_due = None
            if project_data.get('project_start_date'):
                next_report_due = self._calculate_next_report_due(
                    project_data['project_start_date'],
                    requirements.get('timeline_months', 12)
                )

            funding_compliance = FundingCompliance(
                agency=agency,
                grant_number=grant_number,
                compliance_status=compliance_status,
                requirements=requirements,
                next_report_due=next_report_due
            )

            self._log_academic_operation(
                action='FUNDING_COMPLIANCE',
                details={
                    'agency': agency,
                    'grant_number': grant_number,
                    'compliance_status': compliance_status
                }
            )

            return funding_compliance

        except Exception as e:
            logger.error(f"Funding compliance validation failed: {str(e)}")
            raise AcademicComplianceError(f"Funding compliance validation failed: {str(e)}")

    def _get_agency_requirements(self, agency: str) -> Dict[str, Any]:
        """Get funding agency specific requirements."""
        requirements_map = {
            'NIH': {
                'data_sharing_plan': True,
                'public_data_repository': True,
                'timeline_months': 12
            },
            'NSF': {
                'data_management_plan': True,
                'data_preservation': True,
                'timeline_months': 24
            },
            'EU_HORIZON': {
                'open_science_mandate': True,
                'fair_principles': True,
                'timeline_months': 6
            }
        }
        return requirements_map.get(agency, {'timeline_months': 12})

    def _assess_compliance_status(self, agency: str, project_data: Dict[str, Any]) -> str:
        """Assess compliance status for agency."""
        status_map = {
            'NIH': 'NON_COMPLIANT' if not project_data.get('data_sharing_plan') else 'COMPLIANT',
            'NSF': 'PARTIAL' if not project_data.get('data_management_plan') else 'COMPLIANT',
            'EU_HORIZON': 'PARTIAL' if not project_data.get('open_science_compliance') else 'COMPLIANT'
        }
        return status_map.get(agency, 'COMPLIANT')

    def _calculate_next_report_due(self, start_date_str: str, months: int) -> Optional[date]:
        """Calculate next report due date."""
        try:
            from dateutil.relativedelta import relativedelta
            start_date = datetime.fromisoformat(start_date_str).date()
            return start_date + relativedelta(months=months)
        except (ImportError, ValueError):
            return None

    def _validate_authors(self, authors: List[Dict[str, Any]]) -> None:
        """Validate author information."""
        for i, author in enumerate(authors):
            if 'name' not in author:
                raise AcademicComplianceError(f"Author {i} missing 'name' field")
            if 'orcid' in author and not self.validate_orcid(author['orcid']):
                raise AcademicComplianceError(f"Invalid ORCID for author {author['name']}")

    def _build_citation_metadata(self, model: ModelRegistry, model_id: UUID,
                                 authors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build citation metadata from model and author info."""
        return {
            'title': model.name,
            'authors': authors,
            'year': model.created_at.year if model.created_at else datetime.now().year,
            'model_id': str(model_id),
            'url': f"https://emuses.research.org/models/{model_id}",
            'publisher': 'EMUSES Research Platform'
        }

    def _generate_formatted_citations(self, citation_metadata: Dict[str, Any],
                                      model_id: UUID, citation_format: str) -> Dict[str, Any]:
        """Generate formatted citations in requested formats."""
        formatted_citations = {}
        if citation_format in ['APA', 'ALL']:
            formatted_citations['APA'] = self._format_apa_citation(citation_metadata)
        if citation_format in ['MLA', 'ALL']:
            formatted_citations['MLA'] = self._format_mla_citation(citation_metadata)
        if citation_format in ['BibTeX', 'ALL']:
            formatted_citations['BibTeX'] = self._format_bibtex_citation(citation_metadata, model_id)
        return formatted_citations

    def generate_citation_metadata(self, model_id: Union[str, UUID],
                                   authors: List[Dict[str, Any]],
                                   citation_format: str = 'APA') -> Dict[str, Any]:
        """Generate proper citation metadata for models and datasets."""
        try:
            if isinstance(model_id, str):
                model_id = UUID(model_id)

            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == model_id
            ).first()

            if not model:
                raise AcademicComplianceError(f"Model {model_id} not found")

            self._validate_authors(authors)
            citation_metadata = self._build_citation_metadata(model, model_id, authors)
            formatted_citations = self._generate_formatted_citations(
                citation_metadata, model_id, citation_format
            )

            self._log_academic_operation(
                action='CITATION_GENERATION',
                details={
                    'model_id': str(model_id),
                    'format': citation_format,
                    'author_count': len(authors)
                }
            )

            return {
                'status': 'success',
                'metadata': citation_metadata,
                'formatted_citations': formatted_citations,
                'message': 'Citation metadata generated successfully'
            }

        except Exception as e:
            logger.error(f"Citation generation failed for model {model_id}: {str(e)}")
            raise AcademicComplianceError(f"Citation generation failed: {str(e)}")

    def _format_apa_citation(self, metadata: Dict[str, Any]) -> str:
        """Format citation in APA style."""
        authors = metadata['authors']
        author_str = ', '.join([f"{a['name']}" for a in authors[:3]])
        if len(authors) > 3:
            author_str += ", et al."
        return (
            f"{author_str} ({metadata['year']}). "
            f"{metadata['title']}. EMUSES Research Platform. "
            f"Retrieved from {metadata['url']}"
        )

    def _format_mla_citation(self, metadata: Dict[str, Any]) -> str:
        """Format citation in MLA style."""
        authors = metadata['authors']
        author_str = authors[0]['name'] if authors else "Unknown"
        if len(authors) > 1:
            author_str += ", et al."
        return (
            f"{author_str}. \"{metadata['title']}.\" "
            f"EMUSES Research Platform, {metadata['year']}, "
            f"{metadata['url']}."
        )

    def _format_bibtex_citation(self, metadata: Dict[str, Any], model_id: UUID) -> str:
        """Format citation in BibTeX style."""
        authors = metadata['authors']
        author_bibtex = ' and '.join([a['name'] for a in authors])
        return f"""@misc{{emuses_{model_id.hex[:8]},
    title={{{metadata['title']}}},
    author={{{author_bibtex}}},
    year={{{metadata['year']}}},
    url={{{metadata['url']}}},
    note={{EMUSES Research Platform}}
}}"""

    def get_academic_audit_logs(self, user_id: Optional[str] = None,
                                action_filter: Optional[str] = None,
                                limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve academic compliance audit logs."""
        filtered_logs = self.academic_audit_logs

        if user_id:
            filtered_logs = [log for log in filtered_logs if log.user_id == user_id]

        if action_filter:
            filtered_logs = [log for log in filtered_logs
                             if action_filter.upper() in log.action.upper()]

        # Sort by timestamp (newest first) and limit
        filtered_logs.sort(key=lambda x: x.timestamp, reverse=True)
        filtered_logs = filtered_logs[:limit]

        return [
            {
                'id': log.id,
                'user_id': log.user_id,
                'action': log.action,
                'details': log.details,
                'institution_id': log.institution_id,
                'timestamp': log.timestamp.isoformat()
            }
            for log in filtered_logs
        ]
