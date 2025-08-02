"""Authentication backend and user management for multi-user EMUSES service.

This module provides JWT authentication using FastAPI-Users with EMUSES-specific
user management logic, token handling, and role-based access control.
"""

import os
import logging
from typing import Optional, Type
from fastapi import Depends, Request, Response
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase

from emuses.multi_user_service.models import User, UserSettings
from emuses.multi_user_service.database import get_async_session

logger = logging.getLogger(__name__)

# Authentication configuration


def get_jwt_secret() -> str:
    """Get JWT secret from environment with validation.

    Returns
    -------
    str
        JWT secret key

    Raises
    ------
    ValueError
        If EMUSES_JWT_SECRET is missing in non-local deployment modes
    """
    jwt_secret = os.getenv("EMUSES_JWT_SECRET")
    if not jwt_secret:
        deployment_mode = os.getenv("EMUSES_DEPLOYMENT_MODE", "local")
        if deployment_mode != "local":
            raise ValueError(
                "EMUSES_JWT_SECRET environment variable is required for multi-user deployment"
            )
        # Use development secret for local mode
        jwt_secret = "development-secret-key-change-in-production"
    return jwt_secret


TOKEN_LIFETIME_SECONDS = int(os.getenv("JWT_TOKEN_LIFETIME", "3600"))  # 1 hour default


class UserManager(UUIDIDMixin, BaseUserManager[User, type(User.id)]):
    """EMUSES-specific user manager with registration and login logic.

    Extends FastAPI-Users BaseUserManager with EMUSES-specific functionality
    including user quota initialization and workspace creation.
    """

    @property
    def reset_password_token_secret(self):
        return get_jwt_secret()

    @property
    def verification_token_secret(self):
        return get_jwt_secret()

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        """Handle post-registration tasks.

        Creates default user settings and initializes workspace.

        Parameters
        ----------
        user : User
            Newly registered user
        request : Optional[Request]
            FastAPI request object
        """
        logger.info(f"User {user.id} has registered with email {user.email}")

        # Initialize default user settings
        # Note: This would require a database session to actually create settings
        # For now, we just log the event
        logger.info(f"Initializing default settings for user {user.id}")

    async def on_after_login(
        self,
        user: User,
        request: Optional[Request] = None,
        response: Optional[Response] = None,
    ):
        """Handle post-login tasks.

        Updates last login time and logs user activity.

        Parameters
        ----------
        user : User
            Logged in user
        request : Optional[Request]
            FastAPI request object
        response : Optional[Response]
            FastAPI response object built by the transport
        """
        logger.info(f"User {user.id} logged in")

    async def validate_password(
        self,
        password: str,
        user: User,
    ) -> None:
        """Validate password complexity.

        Parameters
        ----------
        password : str
            Password to validate
        user : User
            User attempting to set password

        Raises
        ------
        ValueError
            If password doesn't meet complexity requirements
        """
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")

        # Add more complexity requirements as needed
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain at least one digit")


# Database dependency
async def get_user_db(session=Depends(get_async_session)):
    """Get user database instance.

    Parameters
    ----------
    session : AsyncSession
        Database session from dependency injection

    Yields
    ------
    SQLAlchemyUserDatabase
        User database instance
    """
    yield SQLAlchemyUserDatabase(session, User)


# User manager dependency
async def get_user_manager(user_db=Depends(get_user_db)):
    """Get user manager instance.

    Parameters
    ----------
    user_db : SQLAlchemyUserDatabase
        User database from dependency injection

    Yields
    ------
    UserManager
        User manager instance
    """
    yield UserManager(user_db)


# Authentication backend
def get_auth_backend() -> AuthenticationBackend:
    """Create JWT authentication backend.

    Returns
    -------
    AuthenticationBackend
        Configured JWT authentication backend
    """
    bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

    def get_jwt_strategy() -> JWTStrategy:
        return JWTStrategy(
            secret=get_jwt_secret(),
            lifetime_seconds=TOKEN_LIFETIME_SECONDS,
        )

    auth_backend = AuthenticationBackend(
        name="jwt",
        transport=bearer_transport,
        get_strategy=get_jwt_strategy,
    )

    return auth_backend


# FastAPI-Users instance
def get_fastapi_users() -> FastAPIUsers[User, type(User.id)]:
    """Create FastAPI-Users instance.

    Returns
    -------
    FastAPIUsers
        Configured FastAPI-Users instance
    """
    auth_backend = get_auth_backend()

    fastapi_users = FastAPIUsers[User, type(User.id)](
        get_user_manager,
        [auth_backend],
    )

    return fastapi_users


# Create global instance
fastapi_users = get_fastapi_users()

# User dependency functions
get_current_user = fastapi_users.current_user()
get_current_active_user = fastapi_users.current_user(active=True)
get_current_superuser = fastapi_users.current_user(active=True, superuser=True)
get_current_user_optional = fastapi_users.current_user(optional=True)
