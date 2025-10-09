"""Authentication backend and user management for multi-user EMUSES service.

This module provides JWT authentication using FastAPI-Users with EMUSES-specific
user management logic, token handling, and role-based access control.
"""

import logging
import os
from typing import Optional

from fastapi import Depends, Request, Response
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (AuthenticationBackend,
                                          BearerTransport, JWTStrategy)
from fastapi_users.db import SQLAlchemyUserDatabase

from emuses.multi_user_service.database import get_async_session
from emuses.multi_user_service.models import User

logger = logging.getLogger(__name__)


class VaultError(Exception):
    """Custom exception for Vault-related errors."""
    pass

# Authentication configuration


def vault_configured() -> bool:
    """Detect if HashiCorp Vault is properly configured.

    Returns
    -------
    bool
        True if Vault is configured with appropriate authentication
    """
    vault_addr = os.getenv("VAULT_ADDR")
    if not vault_addr:
        return False

    # Check for token authentication
    vault_token = os.getenv("VAULT_TOKEN")
    if vault_token:
        return True

    # Check for AppRole authentication
    vault_role_id = os.getenv("VAULT_ROLE_ID")
    vault_secret_id = os.getenv("VAULT_SECRET_ID")
    if vault_role_id and vault_secret_id:
        return True

    return False


def _get_secret_from_vault(secret_name: str) -> Optional[str]:
    """Retrieve specific secret from HashiCorp Vault.

    Parameters
    ----------
    secret_name : str
        Name of the secret to retrieve

    Returns
    -------
    Optional[str]
        Secret value if successful, None if failed
    """
    try:
        import hvac

        vault_addr = os.getenv("VAULT_ADDR")
        vault_token = os.getenv("VAULT_TOKEN")
        vault_path = os.getenv("EMUSES_VAULT_SECRET_PATH", "secret/emuses")

        client = hvac.Client(url=vault_addr, token=vault_token)

        if not client.is_authenticated():
            raise VaultError("Vault authentication failed")

        # Read secret from KV v2 engine
        response = client.secrets.kv.v2.read_secret_version(path=vault_path)
        secrets = response['data']['data']

        return secrets.get(secret_name)

    except ImportError:
        logger.error("hvac package not installed. Install with: pip install hvac")
        return None
    except Exception as e:
        logger.error(f"Vault secret retrieval failed: {e}")
        return None


def get_jwt_secret() -> str:
    """Enhanced JWT secret retrieval with multi-source support.

    Priority order:
    1. HashiCorp Vault (enterprise)
    2. Secure file (production)
    3. Environment variable (development)
    4. Development default (local only)

    Returns
    -------
    str
        JWT secret key

    Raises
    ------
    ValueError
        If no JWT secret is configured in non-local deployment modes
    """
    # 1. Try Vault first (enterprise)
    if vault_configured():
        try:
            vault_secret = _get_secret_from_vault("jwt_secret")
            if vault_secret:
                logger.info("JWT secret loaded from HashiCorp Vault")
                return vault_secret
        except VaultError as e:
            logger.warning(f"Vault configured but retrieval failed: {e}")

    # 2. Try secure file (production)
    secret_file = os.getenv("EMUSES_JWT_SECRET_FILE")
    if secret_file and os.path.exists(secret_file):
        try:
            with open(secret_file, 'r') as f:
                file_secret = f.read().strip()
                if file_secret:
                    logger.info("JWT secret loaded from secure file")
                    return file_secret
        except IOError as e:
            logger.warning(f"Secret file configured but unreadable: {e}")

    # 3. Environment variable (compatibility)
    env_secret = os.getenv("EMUSES_JWT_SECRET")
    if env_secret:
        logger.warning("JWT secret loaded from environment variable (less secure)")
        return env_secret

    # 4. Development default (local only)
    deployment_mode = os.getenv("EMUSES_DEPLOYMENT_MODE", "local")
    if deployment_mode == "local":
        logger.warning("Using development JWT secret - configure secure secret for production")
        return "development-secret-key-change-in-production"

    raise ValueError(
        "No JWT secret configured. Configure Vault (VAULT_ADDR + VAULT_TOKEN), "
        "file (EMUSES_JWT_SECRET_FILE), or environment variable (EMUSES_JWT_SECRET)"
    )


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
