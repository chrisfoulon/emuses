"""Model registry factory for unified cross-mode interface.

This module provides a factory pattern for creating appropriate model registry
instances based on deployment mode, with automatic detection and fallback logic.
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union
from uuid import UUID

from emuses.tools.base_model_registry import BaseModelRegistry

logger = logging.getLogger(__name__)


class RegistryMode(Enum):
    """Registry deployment modes."""
    LOCAL = "local"
    DATABASE = "database" 
    CLOUD = "cloud"


class ModelRegistryError(Exception):
    """Base exception for model registry factory operations."""
    pass


class RegistryCreationError(ModelRegistryError):
    """Exception for registry creation failures."""
    pass


class RegistryValidationError(ModelRegistryError):
    """Exception for registry validation failures."""
    pass


class RegistryModeError(ModelRegistryError):
    """Exception for mode-specific operation errors."""
    pass


class ErrorMessages:
    """Centralized error messages for consistent cross-mode reporting."""
    
    # General errors
    REGISTRY_CREATION_FAILED = "Failed to create registry: {error}"
    INTERFACE_VALIDATION_FAILED = "Registry interface validation failed"
    MODE_REQUIREMENTS_NOT_MET = "Requirements not met for mode: {mode}"
    FALLBACK_TO_LOCAL = "Falling back to local registry mode"
    
    # Mode detection errors
    MODE_DETECTION_FAILED = "Error detecting deployment mode: {error}"
    SERVICE_MODE_UNAVAILABLE = "Multi-user service not available"
    DATABASE_COMPONENTS_MISSING = "Database components not available for mode {mode}"
    CLOUD_COMPONENTS_MISSING = "Cloud storage components not available"
    
    # Authentication errors
    AUTH_REQUIRED = "Authentication required for {mode} mode"
    INVALID_USER_ID = "Invalid user ID: {user_id}"
    INVALID_WORKSPACE_ID = "Invalid workspace ID: {workspace_id}"
    ACCESS_DENIED = "Access denied for operation: {operation}"
    PERMISSION_DENIED = "Permission denied for model: {model_name}"
    
    # Model operation errors
    MODEL_NOT_FOUND = "Model not found: {model_name}"
    MODEL_ALREADY_EXISTS = "Model already exists: {model_name}"
    MODEL_INSTALLATION_FAILED = "Failed to install model: {model_name} - {error}"
    MODEL_REMOVAL_FAILED = "Failed to remove model: {model_name} - {error}"
    INVALID_MODEL_PATH = "Invalid model path: {path}"
    
    # Search and listing errors
    SEARCH_FAILED = "Search operation failed: {error}"
    LISTING_FAILED = "Failed to list models: {error}"
    INVALID_QUERY = "Invalid search query: {query}"
    
    # Configuration errors
    INVALID_REGISTRY_PATH = "Invalid registry path: {path}"
    DATABASE_CONNECTION_FAILED = "Database connection failed: {error}"
    CLOUD_STORAGE_ERROR = "Cloud storage error: {error}"
    CONFIGURATION_INVALID = "Invalid configuration for mode: {mode}"
    
    # Version and compatibility errors
    VERSION_NOT_FOUND = "Version not found: {version} for model {model_name}"
    INCOMPATIBLE_VERSION = "Incompatible version: {version}"
    MIGRATION_FAILED = "Failed to migrate between modes: {error}"
    
    @classmethod
    def format_error(cls, template: str, **kwargs) -> str:
        """Format error message with provided parameters.
        
        Parameters
        ----------
        template : str
            Error message template
        **kwargs
            Parameters to format into template
            
        Returns
        -------
        str
            Formatted error message
        """
        try:
            return template.format(**kwargs)
        except KeyError as e:
            return f"{template} (formatting error: missing {e})"


class ModelRegistryFactory:
    """Factory for creating model registry instances across deployment modes.
    
    Provides unified interface for creating appropriate registry implementations
    based on deployment configuration with automatic mode detection and 
    graceful fallback handling.
    
    Examples
    --------
    >>> factory = ModelRegistryFactory()
    >>> registry = factory.create_registry()  # Auto-detect mode
    >>> registry = factory.create_registry(RegistryMode.LOCAL)  # Explicit mode
    """
    
    def __init__(self):
        """Initialize model registry factory."""
        self._mode_configs = self._initialize_mode_configs()
        
    def _initialize_mode_configs(self) -> Dict[RegistryMode, Dict[str, Any]]:
        """Initialize configuration for each registry mode.
        
        Returns
        -------
        Dict[RegistryMode, Dict[str, Any]]
            Mode configurations
        """
        return {
            RegistryMode.LOCAL: {
                'requires_auth': False,
                'requires_database': False,
                'supports_multi_user': False,
                'supports_cloud_storage': False,
                'registry_class': 'LocalModelRegistry',
                'module': 'emuses.tools.local_model_registry'
            },
            RegistryMode.DATABASE: {
                'requires_auth': True,
                'requires_database': True,
                'supports_multi_user': True,
                'supports_cloud_storage': False,
                'registry_class': 'DatabaseModelRegistry',
                'module': 'emuses.tools.database_model_registry'
            },
            RegistryMode.CLOUD: {
                'requires_auth': True,
                'requires_database': True,
                'supports_multi_user': True,
                'supports_cloud_storage': True,
                'registry_class': 'CloudModelRegistry',
                'module': 'emuses.tools.cloud_model_registry'
            }
        }
    
    def create_registry(self, mode: Optional[RegistryMode] = None,
                       registry_path: Optional[Path] = None,
                       db_session: Optional[Any] = None,
                       user_id: Optional[Union[UUID, str]] = None,
                       cloud_config: Optional[Dict[str, Any]] = None,
                       fallback: bool = True,
                       **kwargs) -> BaseModelRegistry:
        """Create appropriate registry instance for specified or detected mode.
        
        Parameters
        ----------
        mode : Optional[RegistryMode]
            Explicit registry mode. If None, auto-detects from environment
        registry_path : Optional[Path]
            Custom registry path for local mode
        db_session : Optional[Any]
            Database session for database/cloud modes
        user_id : Optional[Union[UUID, str]]
            User ID for database/cloud modes
        cloud_config : Optional[Dict[str, Any]]
            Cloud configuration for cloud mode
        fallback : bool, default=True
            Whether to fallback to local mode on errors
        **kwargs
            Additional mode-specific parameters
            
        Returns
        -------
        BaseModelRegistry
            Appropriate registry instance
            
        Raises
        ------
        RegistryCreationError
            If registry creation fails and fallback is disabled
        """
        try:
            # Auto-detect mode if not specified
            if mode is None:
                mode = self._detect_deployment_mode()
                
            logger.info(f"Creating registry for mode: {mode.value}")
            
            # Validate mode configuration
            if not self._validate_mode_requirements(mode, **kwargs):
                if fallback:
                    logger.warning(ErrorMessages.format_error(
                        ErrorMessages.MODE_REQUIREMENTS_NOT_MET, mode=mode.value
                    ) + " - " + ErrorMessages.FALLBACK_TO_LOCAL)
                    mode = RegistryMode.LOCAL
                else:
                    raise RegistryCreationError(ErrorMessages.format_error(
                        ErrorMessages.MODE_REQUIREMENTS_NOT_MET, mode=mode.value
                    ))
            
            # Create registry instance
            registry = self._create_registry_instance(
                mode, registry_path=registry_path, db_session=db_session,
                user_id=user_id, cloud_config=cloud_config, **kwargs
            )
            
            # Validate interface
            if not self.validate_interface(registry):
                if fallback:
                    logger.warning(ErrorMessages.INTERFACE_VALIDATION_FAILED + " - " + ErrorMessages.FALLBACK_TO_LOCAL)
                    return self._create_local_registry(registry_path)
                else:
                    raise RegistryValidationError(ErrorMessages.INTERFACE_VALIDATION_FAILED)
                    
            return registry
            
        except Exception as e:
            if fallback and mode != RegistryMode.LOCAL:
                logger.warning(ErrorMessages.format_error(
                    ErrorMessages.REGISTRY_CREATION_FAILED, error=str(e)
                ) + " - " + ErrorMessages.FALLBACK_TO_LOCAL)
                return self._create_local_registry(registry_path)
            else:
                raise RegistryCreationError(ErrorMessages.format_error(
                    ErrorMessages.REGISTRY_CREATION_FAILED, error=str(e)
                )) from e
    
    def _detect_deployment_mode(self) -> RegistryMode:
        """Detect deployment mode from environment.
        
        Returns
        -------
        RegistryMode
            Detected deployment mode
        """
        try:
            from emuses.multi_user_service.deployment_config import (
                detect_deployment_mode, is_service_mode_enabled, DeploymentMode
            )
            
            if not is_service_mode_enabled():
                return RegistryMode.LOCAL
                
            deployment_mode = detect_deployment_mode()
            
            # Map deployment modes to registry modes
            if deployment_mode == DeploymentMode.LOCAL:
                return RegistryMode.LOCAL
            elif deployment_mode == DeploymentMode.MULTI_USER:
                return RegistryMode.DATABASE
            elif deployment_mode == DeploymentMode.PRODUCTION:
                return RegistryMode.CLOUD
            else:
                return RegistryMode.LOCAL
                
        except ImportError:
            logger.debug(ErrorMessages.SERVICE_MODE_UNAVAILABLE + ", using LOCAL mode")
            return RegistryMode.LOCAL
        except Exception as e:
            logger.warning(ErrorMessages.format_error(
                ErrorMessages.MODE_DETECTION_FAILED, error=str(e)
            ) + ", using LOCAL mode")
            return RegistryMode.LOCAL
    
    def _validate_mode_requirements(self, mode: RegistryMode, **kwargs) -> bool:
        """Validate that requirements for specified mode are met.
        
        Parameters
        ----------
        mode : RegistryMode
            Registry mode to validate
        **kwargs
            Parameters to validate against requirements
            
        Returns
        -------
        bool
            True if all requirements are met
        """
        config = self._mode_configs[mode]
        
        # Check database requirement
        if config['requires_database']:
            if 'db_session' not in kwargs or kwargs['db_session'] is None:
                try:
                    # Try to import database components
                    from emuses.multi_user_service.models import User
                    from sqlalchemy.orm import Session
                except ImportError:
                    logger.debug(ErrorMessages.format_error(
                        ErrorMessages.DATABASE_COMPONENTS_MISSING, mode=mode.value
                    ))
                    return False
        
        # Check cloud storage requirement  
        if mode == RegistryMode.CLOUD:
            try:
                from emuses.tools.cloud_storage import CloudStorageBackend
            except ImportError:
                logger.debug(ErrorMessages.CLOUD_COMPONENTS_MISSING)
                return False
                
        return True
    
    def _create_registry_instance(self, mode: RegistryMode, **kwargs) -> BaseModelRegistry:
        """Create registry instance for specified mode.
        
        Parameters
        ----------
        mode : RegistryMode
            Registry mode
        **kwargs
            Registry-specific parameters
            
        Returns
        -------
        BaseModelRegistry
            Registry instance
        """
        if mode == RegistryMode.LOCAL:
            return self._create_local_registry(kwargs.get('registry_path'))
        elif mode == RegistryMode.DATABASE:
            return self._create_database_registry(
                kwargs.get('db_session'), kwargs.get('user_id')
            )
        elif mode == RegistryMode.CLOUD:
            return self._create_cloud_registry(
                kwargs.get('db_session'), kwargs.get('user_id'),
                kwargs.get('cloud_config')
            )
        else:
            raise RegistryCreationError(f"Unsupported registry mode: {mode}")
    
    def _create_local_registry(self, registry_path: Optional[Path] = None) -> BaseModelRegistry:
        """Create local registry instance.
        
        Parameters
        ----------
        registry_path : Optional[Path]
            Custom registry path
            
        Returns
        -------
        BaseModelRegistry
            Local registry instance
        """
        from emuses.tools.local_model_registry import LocalModelRegistry
        return LocalModelRegistry(registry_path=registry_path)
    
    def _create_database_registry(self, db_session: Optional[Any] = None,
                                 user_id: Optional[Union[UUID, str]] = None) -> BaseModelRegistry:
        """Create database registry instance.
        
        Parameters
        ----------
        db_session : Optional[Any]
            Database session
        user_id : Optional[Union[UUID, str]]
            User ID
            
        Returns
        -------
        BaseModelRegistry
            Database registry instance
        """
        from emuses.tools.database_model_registry import DatabaseModelRegistry
        return DatabaseModelRegistry(db_session=db_session, user_id=user_id)
    
    def _create_cloud_registry(self, db_session: Optional[Any] = None,
                              user_id: Optional[Union[UUID, str]] = None,
                              cloud_config: Optional[Dict[str, Any]] = None) -> BaseModelRegistry:
        """Create cloud registry instance.
        
        Parameters
        ----------
        db_session : Optional[Any]
            Database session
        user_id : Optional[Union[UUID, str]]
            User ID
        cloud_config : Optional[Dict[str, Any]]
            Cloud configuration
            
        Returns
        -------
        BaseModelRegistry
            Cloud registry instance
        """
        from emuses.tools.cloud_model_registry import CloudModelRegistry
        return CloudModelRegistry(
            db_session=db_session, user_id=user_id,
            cloud_config=cloud_config or {}
        )
    
    def get_mode_config(self, mode: RegistryMode) -> Dict[str, Any]:
        """Get configuration for specified mode.
        
        Parameters
        ----------
        mode : RegistryMode
            Registry mode
            
        Returns
        -------
        Dict[str, Any]
            Mode configuration
        """
        return self._mode_configs[mode].copy()
    
    def has_capability(self, registry: BaseModelRegistry, capability: str) -> bool:
        """Check if registry has specified capability.
        
        Parameters
        ----------
        registry : BaseModelRegistry
            Registry instance to check
        capability : str
            Capability name to check
            
        Returns
        -------
        bool
            True if registry has the capability
        """
        return hasattr(registry, capability) and callable(getattr(registry, capability))
    
    def validate_interface(self, registry: BaseModelRegistry) -> bool:
        """Validate that registry implements the BaseModelRegistry interface.
        
        Parameters
        ----------
        registry : BaseModelRegistry
            Registry instance to validate
            
        Returns
        -------
        bool
            True if registry implements required interface
        """
        required_methods = [
            'list_models', 'install_model', 'get_model_info',
            'search_models', 'remove_model', 'get_model_file_path'
        ]
        
        for method in required_methods:
            if not self.has_capability(registry, method):
                logger.warning(f"Registry missing required method: {method}")
                return False
                
        return True
    
    def is_compatible(self, registry: BaseModelRegistry, mode: RegistryMode) -> bool:
        """Check if registry is compatible with specified mode.
        
        Parameters
        ----------
        registry : BaseModelRegistry
            Registry instance to check
        mode : RegistryMode
            Target mode for compatibility check
            
        Returns
        -------
        bool
            True if registry is compatible with mode
        """
        # Check if registry type matches expected type for mode
        config = self._mode_configs[mode]
        expected_class = config['registry_class']
        
        return registry.__class__.__name__ == expected_class