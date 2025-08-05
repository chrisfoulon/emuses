"""Authentication endpoints for multi-user EMUSES service.

This module provides authentication endpoints using FastAPI-Users routers
including registration, login, logout, and user management functionality.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, EmailStr

from emuses.multi_user_service.auth import fastapi_users, get_auth_backend
from emuses.multi_user_service.database import get_async_session
from emuses.multi_user_service.models import User

logger = logging.getLogger(__name__)


class UserCreate(BaseModel):
    """User creation schema with EMUSES-specific fields.

    Extends the base FastAPI-Users user creation schema with
    organization and role information.
    """

    email: EmailStr
    password: str
    organization: str = "Default Organization"
    role: str = "researcher"
    storage_quota_gb: float = 10.0
    compute_quota_hours: float = 100.0


class UserRead(BaseModel):
    """User read schema for API responses.

    Defines which user fields are returned in API responses,
    excluding sensitive information like passwords.
    """

    id: str
    email: str
    organization: str
    role: str
    storage_quota_gb: float
    compute_quota_hours: float
    storage_used_gb: float
    compute_used_hours: float
    is_active: bool
    is_superuser: bool
    is_verified: bool


class UserUpdate(BaseModel):
    """User update schema for profile modifications.

    Allows users to update their profile information,
    excluding sensitive fields like quotas.
    """

    organization: Optional[str] = None
    password: Optional[str] = None


def get_auth_router() -> APIRouter:
    """Get JWT authentication router.

    Returns FastAPI-Users authentication router with JWT backend
    for login and logout functionality.

    Returns
    -------
    APIRouter
        Configured authentication router
    """
    auth_backend = get_auth_backend()
    return fastapi_users.get_auth_router(auth_backend)


def get_register_router() -> APIRouter:
    """Get user registration router.

    Returns FastAPI-Users registration router with EMUSES-specific
    user creation schema.

    Returns
    -------
    APIRouter
        Configured registration router
    """
    return fastapi_users.get_register_router(UserRead, UserCreate)


def get_users_router() -> APIRouter:
    """Get user management router.

    Returns FastAPI-Users router for user profile management
    including reading and updating user information.

    Returns
    -------
    APIRouter
        Configured users router
    """
    return fastapi_users.get_users_router(UserRead, UserUpdate)


def setup_auth_endpoints(app: FastAPI) -> None:
    """Set up authentication endpoints on FastAPI application.

    Adds all authentication-related routers to the FastAPI app
    with appropriate prefixes and tags.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance to configure
    """
    logger.info("Setting up authentication endpoints")

    # Get routers
    auth_router = get_auth_router()
    register_router = get_register_router()
    users_router = get_users_router()

    # Add routers to app with prefixes
    app.include_router(auth_router, prefix="/auth/jwt", tags=["Authentication"])

    app.include_router(register_router, prefix="/auth", tags=["Authentication"])

    app.include_router(users_router, prefix="/users", tags=["Users"])

    # Add custom endpoints
    setup_custom_auth_endpoints(app)

    logger.info("Authentication endpoints configured")


def setup_custom_auth_endpoints(app: FastAPI) -> None:
    """Set up custom authentication endpoints.

    Adds EMUSES-specific authentication endpoints beyond the
    standard FastAPI-Users functionality.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance to configure
    """
    router = APIRouter(prefix="/auth", tags=["Authentication"])

    @router.get("/validate")
    async def validate_token(
        user: User = Depends(fastapi_users.current_user(active=True)),
    ):
        """Validate JWT token and return user information.

        Parameters
        ----------
        user : User
            Current authenticated user

        Returns
        -------
        dict
            User validation information
        """
        return {
            "valid": True,
            "user_id": str(user.id),
            "email": user.email,
            "organization": user.organization,
            "role": user.role,
        }

    @router.get("/status")
    async def auth_status():
        """Get authentication system status.

        Returns information about the current authentication
        configuration and availability.

        Returns
        -------
        dict
            Authentication status information
        """
        return {
            "authentication": "enabled",
            "backend": "jwt",
            "registration": "enabled",
        }

    app.include_router(router)
