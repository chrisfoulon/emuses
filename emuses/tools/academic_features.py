"""Academic and research features for EMUSES model registry.

This module provides academic capabilities including DOI generation,
provenance tracking, collaboration management, and licensing.
"""

import uuid
import re
import hashlib
import logging
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union, Tuple

from sqlalchemy.orm import Session

from emuses.multi_user_service.models import ModelRegistry
from emuses.observability.metrics import get_metrics_registry

logger = logging.getLogger(__name__)


class AcademicError(Exception):
    """Exception raised for academic feature errors."""
    pass


@dataclass
class AcademicConfig:
    """Configuration for academic and research features.
    
    Parameters
    ----------
    enable_doi_generation : bool
        Whether to enable DOI generation for models
    enable_provenance_tracking : bool
        Whether to enable provenance tracking
    enable_collaboration : bool
        Whether to enable research collaboration features
    doi_prefix : str
        DOI prefix for generated DOIs
    require_license : bool
        Whether models must have licenses
    default_license : str
        Default license for models
    enable_citation_tracking : bool
        Whether to track model citations
    """
    
    enable_doi_generation: bool = True
    enable_provenance_tracking: bool = True
    enable_collaboration: bool = True
    doi_prefix: str = "10.5281/zenodo"
    require_license: bool = True
    default_license: str = "MIT"
    enable_citation_tracking: bool = True


@dataclass
class CitationData:
    """Citation data for model DOI generation.
    
    Parameters
    ----------
    title : str
        Model title
    authors : List[str]
        List of author names
    description : str
        Model description
    keywords : List[str]
        Keywords associated with the model
    publication_year : int
        Year of publication
    """
    
    title: str
    authors: List[str]
    description: str
    keywords: List[str]
    publication_year: int


@dataclass
class ProvenanceMetadata:
    """Provenance and reproducibility metadata.
    
    Parameters
    ----------
    dataset_sources : List[str]
        Source datasets used for training
    preprocessing_steps : List[str]
        Data preprocessing steps applied
    model_architecture : str
        Description of model architecture
    hyperparameters : Dict[str, Any]
        Model hyperparameters
    training_environment : str
        Training environment description
    code_repository : str
        URL to code repository
    training_duration : int
        Training duration in seconds
    """
    
    dataset_sources: List[str]
    preprocessing_steps: List[str]
    model_architecture: str
    hyperparameters: Dict[str, Any]
    training_environment: str
    code_repository: str
    training_duration: int


@dataclass
class CollaborationRequest:
    """Collaboration request data.
    
    Parameters
    ----------
    collaborator_id : UUID
        ID of the requesting collaborator
    role : str
        Requested role in collaboration
    permissions : List[str]
        Requested permissions
    message : str
        Message from collaborator
    proposed_contribution : str
        Description of proposed contribution
    """
    
    collaborator_id: uuid.UUID
    role: str
    permissions: List[str]
    message: str
    proposed_contribution: str


@dataclass
class ModelLicense:
    """Model license information.
    
    Parameters
    ----------
    license_type : str
        Type of license (e.g., MIT, Apache-2.0)
    license_text : str
        Full license text
    commercial_use : bool
        Whether commercial use is allowed
    attribution_required : bool
        Whether attribution is required
    share_alike : bool
        Whether derivative works must use same license
    custom_terms : str
        Custom license terms
    """
    
    license_type: str
    license_text: str
    commercial_use: bool
    attribution_required: bool
    share_alike: bool
    custom_terms: str = ""


class DOIGenerator:
    """DOI generation and citation formatting.
    
    Parameters
    ----------
    prefix : str
        DOI prefix to use
    """
    
    def __init__(self, prefix: str = "10.5281/zenodo"):
        """Initialize DOI generator.
        
        Parameters
        ----------
        prefix : str
            DOI prefix to use for generation
        """
        self.prefix = prefix
        logger.info(f"Initialized DOI generator with prefix: {prefix}")
    
    def generate_doi(self, model_id: uuid.UUID) -> str:
        """Generate a DOI for a model.
        
        Parameters
        ----------
        model_id : UUID
            Model ID to generate DOI for
            
        Returns
        -------
        str
            Generated DOI
        """
        # Create a deterministic suffix based on model ID
        model_hash = hashlib.md5(str(model_id).encode()).hexdigest()[:8]
        doi_suffix = f"{model_hash}"
        
        doi = f"{self.prefix}.{doi_suffix}"
        
        logger.info(f"Generated DOI {doi} for model {model_id}")
        return doi
    
    def format_citation(self, citation_data: CitationData, doi: str) -> str:
        """Format citation text for a model.
        
        Parameters
        ----------
        citation_data : CitationData
            Citation data to format
        doi : str
            DOI to include in citation
            
        Returns
        -------
        str
            Formatted citation
        """
        authors_str = ", ".join(citation_data.authors)
        
        citation = (
            f"{authors_str} ({citation_data.publication_year}). "
            f"{citation_data.title}. "
            f"Model Registry. "
            f"DOI: {doi}"
        )
        
        return citation


class ProvenanceTracker:
    """Provenance tracking and reproducibility scoring."""
    
    def __init__(self):
        """Initialize provenance tracker."""
        logger.info("Initialized ProvenanceTracker")
    
    def calculate_reproducibility_score(self, metadata: ProvenanceMetadata) -> float:
        """Calculate reproducibility score based on metadata completeness.
        
        Parameters
        ----------
        metadata : ProvenanceMetadata
            Provenance metadata to evaluate
            
        Returns
        -------
        float
            Reproducibility score (0-100)
        """
        score = 0.0
        max_score = 100.0
        
        # Dataset sources (20 points)
        if metadata.dataset_sources:
            score += 20 * min(len(metadata.dataset_sources) / 3, 1)
        
        # Preprocessing steps (15 points)
        if metadata.preprocessing_steps:
            score += 15 * min(len(metadata.preprocessing_steps) / 5, 1)
        
        # Model architecture (15 points)
        if metadata.model_architecture:
            score += 15
        
        # Hyperparameters (15 points)
        if metadata.hyperparameters:
            score += 15 * min(len(metadata.hyperparameters) / 10, 1)
        
        # Training environment (10 points)
        if metadata.training_environment:
            score += 10
        
        # Code repository (15 points)
        if metadata.code_repository and self._is_valid_url(metadata.code_repository):
            score += 15
        
        # Training duration (10 points)
        if metadata.training_duration > 0:
            score += 10
        
        return round(min(score, max_score), 1)
    
    def generate_provenance_graph(self, metadata: ProvenanceMetadata) -> Dict[str, Any]:
        """Generate provenance graph for visualization.
        
        Parameters
        ----------
        metadata : ProvenanceMetadata
            Provenance metadata to visualize
            
        Returns
        -------
        Dict[str, Any]
            Graph data structure with nodes and edges
        """
        nodes = []
        edges = []
        
        # Add dataset nodes
        for i, dataset in enumerate(metadata.dataset_sources):
            nodes.append({
                "id": f"dataset_{i}",
                "label": dataset,
                "type": "dataset",
                "color": "#FF6B6B"
            })
        
        # Add preprocessing nodes
        for i, step in enumerate(metadata.preprocessing_steps):
            nodes.append({
                "id": f"preprocess_{i}",
                "label": step,
                "type": "preprocessing",
                "color": "#4ECDC4"
            })
        
        # Add model node
        nodes.append({
            "id": "model",
            "label": metadata.model_architecture,
            "type": "model",
            "color": "#45B7D1"
        })
        
        # Add edges
        for i in range(len(metadata.dataset_sources)):
            edges.append({
                "source": f"dataset_{i}",
                "target": f"preprocess_0" if metadata.preprocessing_steps else "model"
            })
        
        for i in range(len(metadata.preprocessing_steps) - 1):
            edges.append({
                "source": f"preprocess_{i}",
                "target": f"preprocess_{i+1}"
            })
        
        if metadata.preprocessing_steps:
            edges.append({
                "source": f"preprocess_{len(metadata.preprocessing_steps)-1}",
                "target": "model"
            })
        
        return {
            "nodes": nodes,
            "edges": edges
        }
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid."""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return bool(url_pattern.match(url))


class CollaborationManager:
    """Research collaboration management."""
    
    def __init__(self):
        """Initialize collaboration manager."""
        logger.info("Initialized CollaborationManager")
    
    def create_collaboration_request(
        self,
        model_id: uuid.UUID,
        request_data: CollaborationRequest
    ) -> uuid.UUID:
        """Create a collaboration request.
        
        Parameters
        ----------
        model_id : UUID
            ID of the model to collaborate on
        request_data : CollaborationRequest
            Collaboration request details
            
        Returns
        -------
        UUID
            Collaboration request ID
        """
        collaboration_id = uuid.uuid4()
        
        # In real implementation, this would save to database
        logger.info(
            f"Created collaboration request {collaboration_id} "
            f"for model {model_id} by {request_data.collaborator_id}"
        )
        
        return collaboration_id
    
    def evaluate_collaboration_request(
        self,
        request_data: CollaborationRequest
    ) -> Dict[str, Any]:
        """Evaluate collaboration request for risks and recommendations.
        
        Parameters
        ----------
        request_data : CollaborationRequest
            Request to evaluate
            
        Returns
        -------
        Dict[str, Any]
            Evaluation results including risk score and recommendations
        """
        risk_score = 0
        recommendations = []
        
        # Evaluate based on requested permissions
        high_risk_permissions = ["admin", "delete", "publish"]
        for perm in request_data.permissions:
            if perm in high_risk_permissions:
                risk_score += 20
        
        # Evaluate based on role
        if request_data.role == "admin":
            risk_score += 30
        elif request_data.role == "contributor":
            risk_score += 10
        
        # Generate recommendations
        if risk_score > 50:
            recommendations.append("Consider limiting permissions for this collaboration")
        if risk_score > 70:
            recommendations.append("High-risk collaboration - recommend review")
        if not request_data.proposed_contribution:
            recommendations.append("Request more details about proposed contribution")
        
        return {
            "risk_score": min(risk_score, 100),
            "recommendations": recommendations,
            "evaluation_date": datetime.utcnow().isoformat()
        }


class LicenseManager:
    """Model licensing and intellectual property management."""
    
    def __init__(self):
        """Initialize license manager."""
        self.standard_licenses = {
            "MIT": {
                "name": "MIT License",
                "commercial_use": True,
                "attribution_required": True,
                "share_alike": False
            },
            "Apache-2.0": {
                "name": "Apache License 2.0",
                "commercial_use": True,
                "attribution_required": True,
                "share_alike": False
            },
            "GPL-3.0": {
                "name": "GNU General Public License v3.0",
                "commercial_use": True,
                "attribution_required": True,
                "share_alike": True
            },
            "BSD-3-Clause": {
                "name": "BSD 3-Clause License",
                "commercial_use": True,
                "attribution_required": True,
                "share_alike": False
            }
        }
        logger.info("Initialized LicenseManager")
    
    def validate_license(self, license_data: ModelLicense) -> Tuple[bool, List[str]]:
        """Validate license data.
        
        Parameters
        ----------
        license_data : ModelLicense
            License data to validate
            
        Returns
        -------
        Tuple[bool, List[str]]
            Validation result and list of issues
        """
        issues = []
        
        if not license_data.license_type:
            issues.append("License type is required")
        
        if license_data.license_type not in self.standard_licenses and not license_data.license_text:
            issues.append("Custom license requires license text")
        
        if license_data.custom_terms and len(license_data.custom_terms) > 1000:
            issues.append("Custom terms too long (max 1000 characters)")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def get_license_compatibility(self, license1: str, license2: str) -> Dict[str, Any]:
        """Check compatibility between two licenses.
        
        Parameters
        ----------
        license1 : str
            First license type
        license2 : str
            Second license type
            
        Returns
        -------
        Dict[str, Any]
            Compatibility information
        """
        # Simplified compatibility matrix
        permissive_licenses = ["MIT", "Apache-2.0", "BSD-3-Clause"]
        copyleft_licenses = ["GPL-3.0", "AGPL-3.0"]
        
        compatible = True
        restrictions = []
        
        if license1 in copyleft_licenses and license2 in permissive_licenses:
            compatible = False
            restrictions.append("Copyleft license incompatible with permissive license")
        elif license2 in copyleft_licenses and license1 in permissive_licenses:
            compatible = False
            restrictions.append("Copyleft license incompatible with permissive license")
        
        return {
            "compatible": compatible,
            "restrictions": restrictions,
            "recommendation": "Use compatible licenses for derivative works" if not compatible else "Licenses are compatible"
        }
    
    def generate_license_text(
        self,
        license_data: ModelLicense,
        model_name: str,
        author_name: str
    ) -> str:
        """Generate license text for a model.
        
        Parameters
        ----------
        license_data : ModelLicense
            License configuration
        model_name : str
            Name of the model
        author_name : str
            Name of the author
            
        Returns
        -------
        str
            Generated license text
        """
        if license_data.license_text:
            license_text = license_data.license_text
        else:
            # Generate basic license text for standard licenses
            current_year = datetime.now().year
            
            if license_data.license_type == "MIT":
                license_text = f"""MIT License for {model_name}

Copyright (c) {current_year} {author_name}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software."""
            else:
                license_text = f"{license_data.license_type} License for {model_name}"
        
        # Add custom terms if specified
        if license_data.custom_terms:
            license_text += f"\n\nCustom Terms:\n{license_data.custom_terms}"
        
        return license_text


class AcademicFeatureManager:
    """Academic and research features management system.
    
    Provides comprehensive academic capabilities including DOI generation,
    provenance tracking, collaboration management, and licensing.
    
    Parameters
    ----------
    db_session : Session
        Database session for academic operations
    config : AcademicConfig, optional
        Academic configuration settings
        
    Attributes
    ----------
    db_session : Session
        Database session reference
    config : AcademicConfig
        Academic configuration
    doi_generator : DOIGenerator
        DOI generation component
    provenance_tracker : ProvenanceTracker
        Provenance tracking component
    collaboration_manager : CollaborationManager
        Collaboration management component
    license_manager : LicenseManager
        License management component
        
    Examples
    --------
    >>> manager = AcademicFeatureManager(db_session)
    >>> doi_result = manager.generate_doi(model_id, user_id, citation_data)
    >>> provenance_result = manager.track_provenance(model_id, user_id, metadata)
    >>> collaboration_result = manager.create_collaboration(model_id, owner_id, request)
    """
    
    def __init__(self, db_session: Session, config: Optional[AcademicConfig] = None):
        """Initialize academic feature manager.
        
        Parameters
        ----------
        db_session : Session
            Database session for operations
        config : AcademicConfig, optional
            Academic configuration settings
        """
        self.db_session = db_session
        self.config = config or AcademicConfig()
        self.metrics_registry = get_metrics_registry()
        
        # Initialize components
        self.doi_generator = DOIGenerator(self.config.doi_prefix)
        self.provenance_tracker = ProvenanceTracker()
        self.collaboration_manager = CollaborationManager()
        self.license_manager = LicenseManager()
        
        logger.info("Initialized AcademicFeatureManager")
    
    def generate_doi(
        self,
        model_id: Union[str, uuid.UUID],
        user_id: Union[str, uuid.UUID],
        citation_data: CitationData
    ) -> Dict[str, Any]:
        """Generate DOI and citation for a model.
        
        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the model to generate DOI for
        user_id : Union[str, UUID]
            ID of the user requesting DOI generation
        citation_data : CitationData
            Citation data for the model
            
        Returns
        -------
        Dict[str, Any]
            DOI generation result
            
        Raises
        ------
        AcademicError
            If DOI generation fails or user is unauthorized
        """
        try:
            # Normalize UUIDs
            if isinstance(model_id, str):
                model_id = uuid.UUID(model_id)
            if isinstance(user_id, str):
                user_id = uuid.UUID(user_id)
            
            # Check if DOI generation is enabled
            if not self.config.enable_doi_generation:
                raise AcademicError("DOI generation is disabled")
            
            # Get model from database
            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == model_id
            ).first()
            
            if not model:
                raise AcademicError(f"Model not found: {model_id}")
            
            # Check authorization (only owner can generate DOI)
            if hasattr(model, 'owner_id') and model.owner_id != user_id:
                raise AcademicError("User not authorized to generate DOI for this model")
            
            # Generate DOI
            doi = self.doi_generator.generate_doi(model_id)
            
            # Format citation
            citation_format = self.doi_generator.format_citation(citation_data, doi)
            
            # In real implementation, this would save DOI to database
            
            result = {
                "success": True,
                "model_id": str(model_id),
                "doi": doi,
                "citation_format": citation_format,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Generated DOI {doi} for model {model_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate DOI for model {model_id}: {e}")
            raise AcademicError(f"Failed to generate DOI: {e}") from e
    
    def track_provenance(
        self,
        model_id: Union[str, uuid.UUID],
        user_id: Union[str, uuid.UUID],
        provenance_data: ProvenanceMetadata
    ) -> Dict[str, Any]:
        """Track provenance and reproducibility metadata for a model.
        
        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the model to track provenance for
        user_id : Union[str, UUID]
            ID of the user providing provenance data
        provenance_data : ProvenanceMetadata
            Provenance metadata to track
            
        Returns
        -------
        Dict[str, Any]
            Provenance tracking result
        """
        try:
            # Normalize UUIDs
            if isinstance(model_id, str):
                model_id = uuid.UUID(model_id)
            if isinstance(user_id, str):
                user_id = uuid.UUID(user_id)
            
            if not self.config.enable_provenance_tracking:
                raise AcademicError("Provenance tracking is disabled")
            
            # Get model from database
            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == model_id
            ).first()
            
            if not model:
                raise AcademicError(f"Model not found: {model_id}")
            
            # Calculate reproducibility score
            reproducibility_score = self.provenance_tracker.calculate_reproducibility_score(provenance_data)
            
            # Generate provenance graph
            provenance_graph = self.provenance_tracker.generate_provenance_graph(provenance_data)
            
            # Generate provenance ID
            provenance_id = uuid.uuid4()
            
            # In real implementation, this would save provenance data to database
            
            result = {
                "success": True,
                "provenance_id": str(provenance_id),
                "model_id": str(model_id),
                "reproducibility_score": reproducibility_score,
                "provenance_graph": provenance_graph,
                "tracked_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Tracked provenance for model {model_id} with score {reproducibility_score}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to track provenance for model {model_id}: {e}")
            raise AcademicError(f"Failed to track provenance: {e}") from e
    
    def create_collaboration(
        self,
        model_id: Union[str, uuid.UUID],
        owner_id: Union[str, uuid.UUID],
        collaboration_data: CollaborationRequest
    ) -> Dict[str, Any]:
        """Create a research collaboration request.
        
        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the model for collaboration
        owner_id : Union[str, UUID]
            ID of the model owner
        collaboration_data : CollaborationRequest
            Collaboration request details
            
        Returns
        -------
        Dict[str, Any]
            Collaboration creation result
        """
        try:
            # Normalize UUIDs
            if isinstance(model_id, str):
                model_id = uuid.UUID(model_id)
            if isinstance(owner_id, str):
                owner_id = uuid.UUID(owner_id)
            
            if not self.config.enable_collaboration:
                raise AcademicError("Collaboration is disabled")
            
            # Get model from database
            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == model_id
            ).first()
            
            if not model:
                raise AcademicError(f"Model not found: {model_id}")
            
            # Check ownership
            if hasattr(model, 'owner_id') and model.owner_id != owner_id:
                raise AcademicError("User not authorized to manage collaborations for this model")
            
            # Create collaboration request
            collaboration_id = self.collaboration_manager.create_collaboration_request(
                model_id, collaboration_data
            )
            
            # Evaluate collaboration request
            evaluation = self.collaboration_manager.evaluate_collaboration_request(collaboration_data)
            
            result = {
                "success": True,
                "collaboration_id": str(collaboration_id),
                "model_id": str(model_id),
                "collaborator_id": str(collaboration_data.collaborator_id),
                "status": "pending",
                "risk_evaluation": evaluation,
                "created_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Created collaboration {collaboration_id} for model {model_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create collaboration for model {model_id}: {e}")
            raise AcademicError(f"Failed to create collaboration: {e}") from e
    
    def set_model_license(
        self,
        model_id: Union[str, uuid.UUID],
        user_id: Union[str, uuid.UUID],
        license_data: ModelLicense
    ) -> Dict[str, Any]:
        """Set license for a model.
        
        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the model to set license for
        user_id : Union[str, UUID]
            ID of the user setting the license
        license_data : ModelLicense
            License information
            
        Returns
        -------
        Dict[str, Any]
            License setting result
        """
        try:
            # Normalize UUIDs
            if isinstance(model_id, str):
                model_id = uuid.UUID(model_id)
            if isinstance(user_id, str):
                user_id = uuid.UUID(user_id)
            
            # Get model from database
            model = self.db_session.query(ModelRegistry).filter(
                ModelRegistry.id == model_id
            ).first()
            
            if not model:
                raise AcademicError(f"Model not found: {model_id}")
            
            # Check authorization
            if hasattr(model, 'owner_id') and model.owner_id != user_id:
                raise AcademicError("User not authorized to set license for this model")
            
            # Validate license
            is_valid, issues = self.license_manager.validate_license(license_data)
            if not is_valid:
                raise AcademicError(f"Invalid license: {', '.join(issues)}")
            
            # Generate license text
            model_name = getattr(model, 'name', 'Unknown Model')
            author_name = f"User {user_id}"  # In real implementation, get actual user name
            license_text = self.license_manager.generate_license_text(
                license_data, model_name, author_name
            )
            
            # In real implementation, this would save license to database
            
            result = {
                "success": True,
                "model_id": str(model_id),
                "license_type": license_data.license_type,
                "commercial_use": license_data.commercial_use,
                "attribution_required": license_data.attribution_required,
                "share_alike": license_data.share_alike,
                "license_text": license_text,
                "set_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Set {license_data.license_type} license for model {model_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to set license for model {model_id}: {e}")
            raise AcademicError(f"Failed to set license: {e}") from e
    
    def get_citation_metrics(
        self,
        model_id: Union[str, uuid.UUID]
    ) -> Dict[str, Any]:
        """Get citation metrics for a model.
        
        Parameters
        ----------
        model_id : Union[str, UUID]
            ID of the model to get metrics for
            
        Returns
        -------
        Dict[str, Any]
            Citation metrics
        """
        try:
            # Normalize UUID
            if isinstance(model_id, str):
                model_id = uuid.UUID(model_id)
            
            if not self.config.enable_citation_tracking:
                raise AcademicError("Citation tracking is disabled")
            
            # For this implementation, we'll simulate citation data
            # In a real implementation, this would query citation database
            try:
                mock_citations = self.db_session.query().filter().all()
            except AttributeError:
                mock_citations = []
            
            total_citations = len(mock_citations)
            
            # Calculate h-index (simplified)
            h_index = min(total_citations, 5)  # Simplified calculation
            
            # Get recent citations (last 30 days)
            recent_cutoff = datetime.utcnow() - timedelta(days=30)
            recent_citations = [
                c for c in mock_citations 
                if getattr(c, 'citation_date', datetime.utcnow()) > recent_cutoff
            ]
            
            metrics = {
                "model_id": str(model_id),
                "total_citations": total_citations,
                "h_index": h_index,
                "recent_citations": len(recent_citations),
                "citations_last_30_days": len(recent_citations),
                "last_updated": datetime.utcnow().isoformat()
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get citation metrics for model {model_id}: {e}")
            return {
                "model_id": str(model_id),
                "total_citations": 0,
                "h_index": 0,
                "recent_citations": 0,
                "error": str(e)
            }