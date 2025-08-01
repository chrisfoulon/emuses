"""Deployment mode configuration for EMUSES multi-user service.

This module provides deployment mode detection and configuration management
for three deployment modes: local, multi-user, and production.
"""

import os
import logging
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DeploymentMode(Enum):
    """Supported deployment modes for EMUSES service."""
    
    LOCAL = "local"
    MULTI_USER = "multi-user"
    PRODUCTION = "production"


@dataclass
class DeploymentConfig:
    """Configuration settings for each deployment mode.
    
    Attributes
    ----------
    mode : DeploymentMode
        Current deployment mode
    requires_auth : bool
        Whether authentication is required
    requires_database : bool
        Whether database connection is required
    service_url : Optional[str]
        Default service URL for this mode
    health_check_enabled : bool
        Whether health checks are enabled
    """
    
    mode: DeploymentMode
    requires_auth: bool
    requires_database: bool
    service_url: Optional[str] = None
    health_check_enabled: bool = True


def detect_deployment_mode() -> DeploymentMode:
    """Detect current deployment mode from environment variables.
    
    Returns
    -------
    DeploymentMode
        Detected deployment mode
        
    Examples
    --------
    >>> import os
    >>> os.environ["EMUSES_DEPLOYMENT_MODE"] = "production"
    >>> detect_deployment_mode()
    <DeploymentMode.PRODUCTION: 'production'>
    """
    mode_str = os.getenv("EMUSES_DEPLOYMENT_MODE", "local").lower()
    
    try:
        return DeploymentMode(mode_str)
    except ValueError:
        logger.warning(
            f"Unknown deployment mode '{mode_str}', defaulting to local mode"
        )
        return DeploymentMode.LOCAL


def get_deployment_config() -> DeploymentConfig:
    """Get configuration for current deployment mode.
    
    Returns
    -------
    DeploymentConfig
        Configuration for current deployment mode
        
    Examples
    --------
    >>> config = get_deployment_config()
    >>> config.mode
    <DeploymentMode.LOCAL: 'local'>
    >>> config.requires_auth
    False
    """
    mode = detect_deployment_mode()
    
    if mode == DeploymentMode.LOCAL:
        return DeploymentConfig(
            mode=mode,
            requires_auth=False,
            requires_database=False,
            service_url="http://localhost:8000",
            health_check_enabled=False,
        )
    elif mode == DeploymentMode.MULTI_USER:
        return DeploymentConfig(
            mode=mode,
            requires_auth=True,
            requires_database=True,
            service_url=os.getenv("EMUSES_SERVICE_URL", "http://localhost:8000"),
            health_check_enabled=True,
        )
    elif mode == DeploymentMode.PRODUCTION:
        return DeploymentConfig(
            mode=mode,
            requires_auth=True,
            requires_database=True,
            service_url=os.getenv("EMUSES_SERVICE_URL", "https://emuses.example.com"),
            health_check_enabled=True,
        )
    else:
        # This shouldn't happen due to enum validation, but be safe
        raise ValueError(f"Unsupported deployment mode: {mode}")


def validate_deployment_config(config: DeploymentConfig) -> Dict[str, Any]:
    """Validate deployment configuration and return validation results.
    
    Parameters
    ----------
    config : DeploymentConfig
        Configuration to validate
        
    Returns
    -------
    Dict[str, Any]
        Validation results with 'valid' boolean and 'errors' list
        
    Examples
    --------
    >>> config = get_deployment_config()
    >>> result = validate_deployment_config(config)
    >>> result['valid']
    True
    """
    errors = []
    
    # Validate required environment variables
    if config.requires_auth:
        if not os.getenv("JWT_SECRET"):
            errors.append("JWT_SECRET environment variable is required for authentication")
    
    if config.requires_database:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            errors.append("DATABASE_URL environment variable is required")
        else:
            # Basic URL validation
            try:
                parsed = urlparse(database_url)
                if not parsed.scheme or not parsed.netloc:
                    errors.append("DATABASE_URL must be a valid URL")
            except Exception as e:
                errors.append(f"Invalid DATABASE_URL: {e}")
    
    # Validate service URL
    if config.service_url:
        try:
            parsed = urlparse(config.service_url)
            if not parsed.scheme or not parsed.netloc:
                errors.append("Service URL must be a valid URL")
        except Exception as e:
            errors.append(f"Invalid service URL: {e}")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "config": config,
    }


def is_service_mode_enabled() -> bool:
    """Check if current deployment mode supports service operation.
    
    Returns
    -------
    bool
        True if service mode is enabled (multi-user or production)
        
    Examples
    --------
    >>> is_service_mode_enabled()
    False  # In local mode
    """
    mode = detect_deployment_mode()
    return mode in (DeploymentMode.MULTI_USER, DeploymentMode.PRODUCTION)


def get_service_discovery_url() -> Optional[str]:
    """Get service discovery URL for multi-user mode.
    
    Returns
    -------
    Optional[str]
        Service discovery URL or None if not in service mode
        
    Examples
    --------
    >>> get_service_discovery_url()
    'http://localhost:8000'  # In multi-user mode
    """
    config = get_deployment_config()
    
    if config.mode == DeploymentMode.LOCAL:
        return None
    
    return config.service_url


# Global configuration instance
deployment_config = get_deployment_config()