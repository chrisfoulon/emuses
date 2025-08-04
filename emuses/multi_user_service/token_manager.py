"""Token management for EMUSES multi-user CLI authentication.

This module provides secure token storage, validation, and management
for CLI authentication in multi-user deployment modes.
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import jwt

logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """Token information structure.

    Attributes
    ----------
    access_token : str
        JWT access token
    token_type : str
        Token type (usually "bearer")
    expires_at : Optional[datetime]
        Token expiration timestamp
    user_id : Optional[str]
        User ID associated with the token
    email : Optional[str]
        User email associated with the token
    """

    access_token: str
    token_type: str = "bearer"
    expires_at: Optional[datetime] = None
    user_id: Optional[str] = None
    email: Optional[str] = None


class TokenManager:
    """Manages authentication tokens for CLI operations.

    Provides secure storage and validation of JWT tokens for multi-user
    authentication in CLI workflows.
    """

    def __init__(self, token_dir: Optional[Path] = None):
        """Initialize token manager.

        Parameters
        ----------
        token_dir : Optional[Path]
            Directory for token storage, defaults to ~/.emuses/
        """
        if token_dir is None:
            token_dir = Path.home() / ".emuses"

        self.token_dir = token_dir
        self.token_file = token_dir / "token.json"

        # Ensure directory exists with secure permissions
        self.token_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.token_dir, 0o700)  # Owner read/write/execute only

    def store_token(self, token_info: TokenInfo) -> None:
        """Store authentication token securely.

        Parameters
        ----------
        token_info : TokenInfo
            Token information to store

        Examples
        --------
        >>> manager = TokenManager()
        >>> token = TokenInfo(access_token="jwt_token", expires_at=datetime.now() + timedelta(hours=1))
        >>> manager.store_token(token)
        """
        token_data = {
            "access_token": token_info.access_token,
            "token_type": token_info.token_type,
            "expires_at": (
                token_info.expires_at.isoformat() if token_info.expires_at else None
            ),
            "user_id": token_info.user_id,
            "email": token_info.email,
            "stored_at": datetime.now().isoformat(),
        }

        try:
            with open(self.token_file, "w") as f:
                json.dump(token_data, f, indent=2)

            # Set secure file permissions
            os.chmod(self.token_file, 0o600)  # Owner read/write only

            logger.info("Authentication token stored successfully")

        except Exception as e:
            logger.error(f"Failed to store authentication token: {e}")
            raise

    def load_token(self) -> Optional[TokenInfo]:
        """Load stored authentication token.

        Returns
        -------
        Optional[TokenInfo]
            Stored token information or None if not found

        Examples
        --------
        >>> manager = TokenManager()
        >>> token = manager.load_token()
        >>> if token:
        ...     print(f"Token for user: {token.email}")
        """
        if not self.token_file.exists():
            return None

        try:
            with open(self.token_file, "r") as f:
                token_data = json.load(f)

            expires_at = None
            if token_data.get("expires_at"):
                expires_at = datetime.fromisoformat(token_data["expires_at"])

            return TokenInfo(
                access_token=token_data["access_token"],
                token_type=token_data.get("token_type", "bearer"),
                expires_at=expires_at,
                user_id=token_data.get("user_id"),
                email=token_data.get("email"),
            )

        except Exception as e:
            logger.warning(f"Failed to load authentication token: {e}")
            return None

    def clear_token(self) -> None:
        """Clear stored authentication token.

        Examples
        --------
        >>> manager = TokenManager()
        >>> manager.clear_token()
        """
        try:
            if self.token_file.exists():
                self.token_file.unlink()
                logger.info("Authentication token cleared")
        except Exception as e:
            logger.warning(f"Failed to clear authentication token: {e}")

    def is_token_valid(self, token_info: Optional[TokenInfo] = None) -> bool:
        """Check if token is valid and not expired.

        Parameters
        ----------
        token_info : Optional[TokenInfo]
            Token to validate, loads from storage if None

        Returns
        -------
        bool
            True if token is valid and not expired

        Examples
        --------
        >>> manager = TokenManager()
        >>> if manager.is_token_valid():
        ...     print("Token is valid")
        ... else:
        ...     print("Need to login")
        """
        if token_info is None:
            token_info = self.load_token()

        if not token_info:
            return False

        # Check if token is expired
        if token_info.expires_at and datetime.now() >= token_info.expires_at:
            logger.info("Token has expired")
            return False

        # Additional validation can be added here
        # (e.g., JWT signature validation)

        return True

    def decode_token_payload(
        self, token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Decode JWT token payload without verification.

        This is used to extract user information from tokens.
        For security validation, use proper JWT verification.

        Parameters
        ----------
        token : Optional[str]
            JWT token to decode, uses stored token if None

        Returns
        -------
        Optional[Dict[str, Any]]
            Token payload or None if decoding fails

        Examples
        --------
        >>> manager = TokenManager()
        >>> payload = manager.decode_token_payload()
        >>> if payload:
        ...     print(f"User ID: {payload.get('sub')}")
        """
        if token is None:
            token_info = self.load_token()
            if not token_info:
                return None
            token = token_info.access_token

        try:
            # Decode without verification to extract payload
            # Note: This is only for reading user info, not for validation
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload
        except Exception as e:
            logger.warning(f"Failed to decode token payload: {e}")
            return None

    def get_auth_header(self) -> Optional[str]:
        """Get authorization header value for HTTP requests.

        Returns
        -------
        Optional[str]
            Authorization header value or None if no valid token

        Examples
        --------
        >>> manager = TokenManager()
        >>> auth_header = manager.get_auth_header()
        >>> if auth_header:
        ...     headers = {"Authorization": auth_header}
        """
        token_info = self.load_token()
        if not token_info or not self.is_token_valid(token_info):
            return None

        return f"{token_info.token_type} {token_info.access_token}"
