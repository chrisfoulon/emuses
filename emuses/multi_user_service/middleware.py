"""Authentication middleware integration for multi-user EMUSES service.

This module provides middleware integration functions to add authentication
to the existing FastAPI application with proper positioning and backward
compatibility.
"""

import logging
import os
from typing import Any, Callable, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPBearer

from emuses.multi_user_service.auth import (fastapi_users,
                                            get_current_active_user,
                                            get_current_user_optional)
from emuses.multi_user_service.models import User

logger = logging.getLogger(__name__)

# Security scheme for optional authentication
security = HTTPBearer(auto_error=False)


def get_deployment_mode() -> str:
    """Get current deployment mode from environment.

    Returns
    -------
    str
        Deployment mode (local, multi-user, production)
    """
    return os.getenv("EMUSES_DEPLOYMENT_MODE", "local")


def setup_authentication_middleware(app: FastAPI) -> None:
    """Set up authentication middleware on existing FastAPI app.

    Adds authentication middleware after CORS but before other middleware,
    preserving existing error handling patterns and maintaining backward
    compatibility.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance to configure
    """
    deployment_mode = get_deployment_mode()

    logger.info(f"Setting up authentication middleware for mode: {deployment_mode}")

    if deployment_mode == "local":
        # In local mode, no special middleware needed
        # Authentication is optional and handled by dependencies
        logger.info("Local mode: Authentication middleware optional")
        return

    # For multi-user and production modes, we could add middleware here
    # For now, we rely on dependency injection for authentication
    logger.info(f"Authentication configured for {deployment_mode} mode")


def get_conditional_auth_dependency() -> Callable:
    """Get authentication dependency based on deployment mode.

    Returns appropriate authentication dependency function based on
    the current deployment mode configuration.

    Returns
    -------
    Callable
        Authentication dependency function
    """
    deployment_mode = get_deployment_mode()

    if deployment_mode == "local":
        # In local mode, return optional authentication
        return get_current_user_optional
    elif deployment_mode == "multi-user":
        # In multi-user mode, require active users
        return get_current_active_user
    elif deployment_mode == "production":
        # In production mode, require active users
        return get_current_active_user
    else:
        # Default to optional authentication
        logger.warning(
            f"Unknown deployment mode: {deployment_mode}, using optional auth"
        )
        return get_current_user_optional


async def get_user_context(
    request: Request, user: Optional[User] = Depends(get_conditional_auth_dependency())
) -> Optional[User]:
    """Get user context for request processing.

    This dependency function provides user context to endpoints based on
    the deployment mode, allowing for optional or required authentication.

    Parameters
    ----------
    request : Request
        FastAPI request object
    user : Optional[User]
        User from authentication dependency

    Returns
    -------
    Optional[User]
        User context if authenticated, None otherwise
    """
    deployment_mode = get_deployment_mode()

    if deployment_mode == "local":
        # In local mode, user is always optional
        return user
    else:
        # In multi-user/production modes, user might be required
        # depending on the specific endpoint requirements
        return user


def require_authentication(user: User = Depends(get_current_active_user)) -> User:
    """Dependency that requires authentication regardless of deployment mode.

    Use this dependency for endpoints that always require authentication,
    such as user management or admin functions.

    Parameters
    ----------
    user : User
        User from authentication dependency

    Returns
    -------
    User
        Authenticated user

    Raises
    ------
    HTTPException
        If user is not authenticated
    """
    return user


def optional_authentication(
    user: Optional[User] = Depends(get_current_user_optional),
) -> Optional[User]:
    """Dependency for optional authentication.

    Use this dependency for endpoints that can work with or without
    authentication, providing enhanced functionality when authenticated.

    Parameters
    ----------
    user : Optional[User]
        User from optional authentication dependency

    Returns
    -------
    Optional[User]
        Authenticated user if available, None otherwise
    """
    return user


def create_user_scoped_dependency(base_dependency: Callable) -> Callable:
    """Create a user-scoped version of a dependency.

    Wraps an existing dependency to include user context, allowing
    for user-specific behavior in multi-user scenarios.

    Parameters
    ----------
    base_dependency : Callable
        Base dependency function to wrap

    Returns
    -------
    Callable
        User-scoped dependency function
    """

    async def user_scoped_dependency(
        user: Optional[User] = Depends(get_conditional_auth_dependency()),
        base_result: Any = Depends(base_dependency),
    ):
        """User-scoped wrapper for base dependency.

        Parameters
        ----------
        user : Optional[User]
            Current user context
        base_result : Any
            Result from base dependency

        Returns
        -------
        tuple
            (user, base_result) tuple for user-scoped operations
        """
        return user, base_result

    return user_scoped_dependency
