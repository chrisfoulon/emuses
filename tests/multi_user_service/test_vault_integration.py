"""Tests for HashiCorp Vault integration in multi-user service.

This module tests the Vault integration functionality including:
- Secret retrieval from Vault
- Fallback behavior when Vault unavailable
- Configuration validation
- Authentication handling
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from emuses.multi_user_service.auth import get_jwt_secret


class TestVaultIntegration:
    """Test Vault integration functionality."""

    @patch('hvac.Client')
    def test_vault_secret_retrieval_success(self, mock_hvac_client):
        """Test successful secret retrieval from Vault.

        Validates that when Vault is properly configured and accessible,
        secrets are retrieved from Vault successfully.
        """
        # Setup mock Vault client
        mock_client = MagicMock()
        mock_hvac_client.return_value = mock_client
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': {'jwt_secret': 'vault-secret-123'}}
        }

        # Test with Vault configuration
        with patch.dict(os.environ, {
            'VAULT_ADDR': 'http://vault:8200',
            'VAULT_TOKEN': 'test-token',
            'EMUSES_DEPLOYMENT_MODE': 'multi_user'
        }, clear=True):
            secret = get_jwt_secret()
            assert secret == 'vault-secret-123'

        # Verify Vault client was called correctly
        mock_hvac_client.assert_called_with(
            url='http://vault:8200',
            token='test-token'
        )
        mock_client.is_authenticated.assert_called_once()
        mock_client.secrets.kv.v2.read_secret_version.assert_called_once()

    def test_vault_fallback_to_environment(self):
        """Test fallback to environment variable when Vault unavailable.

        Validates graceful degradation when Vault is configured but
        not accessible, falling back to environment variable.
        """
        with patch.dict(os.environ, {
            'VAULT_ADDR': 'http://vault:8200',
            'VAULT_TOKEN': 'test-token',
            'EMUSES_JWT_SECRET': 'fallback-secret',
            'EMUSES_DEPLOYMENT_MODE': 'multi_user'
        }, clear=True):
            # Mock Vault as unavailable
            with patch('hvac.Client') as mock_hvac_client:
                mock_hvac_client.side_effect = Exception("Vault unavailable")

                secret = get_jwt_secret()
                assert secret == 'fallback-secret'

    def test_development_mode_default(self):
        """Test development default when no configuration present.

        Validates that in local/development mode, a development secret
        is returned when no other configuration is available.
        """
        with patch.dict(os.environ, {
            'EMUSES_DEPLOYMENT_MODE': 'local'
        }, clear=True):
            secret = get_jwt_secret()
            assert secret == 'development-secret-key-change-in-production'

    def test_production_mode_requires_configuration(self):
        """Test that production mode requires proper secret configuration.

        Validates that in production mode, an error is raised when
        no secret configuration is available.
        """
        with patch.dict(os.environ, {
            'EMUSES_DEPLOYMENT_MODE': 'multi_user'
        }, clear=True):
            with pytest.raises(ValueError, match="No JWT secret configured"):
                get_jwt_secret()


class TestVaultConfiguration:
    """Test Vault configuration validation."""

    def test_vault_configured_detection(self):
        """Test Vault configuration detection logic.

        Validates that Vault configuration is properly detected
        when appropriate environment variables are set.
        """
        # Test with token authentication
        with patch.dict(os.environ, {
            'VAULT_ADDR': 'http://vault:8200',
            'VAULT_TOKEN': 'test-token'
        }, clear=True):
            from emuses.multi_user_service.auth import vault_configured
            assert vault_configured() is True

        # Test with AppRole authentication
        with patch.dict(os.environ, {
            'VAULT_ADDR': 'http://vault:8200',
            'VAULT_ROLE_ID': 'role-id',
            'VAULT_SECRET_ID': 'secret-id'
        }, clear=True):
            assert vault_configured() is True

        # Test incomplete configuration
        with patch.dict(os.environ, {
            'VAULT_ADDR': 'http://vault:8200'
        }, clear=True):
            assert vault_configured() is False

    @patch('hvac.Client')
    def test_vault_authentication_failure(self, mock_hvac_client):
        """Test handling of Vault authentication failures.

        Validates that authentication failures are handled gracefully
        and appropriate fallback behavior is triggered.
        """
        mock_client = MagicMock()
        mock_hvac_client.return_value = mock_client
        mock_client.is_authenticated.return_value = False

        with patch.dict(os.environ, {
            'VAULT_ADDR': 'http://vault:8200',
            'VAULT_TOKEN': 'invalid-token',
            'EMUSES_JWT_SECRET': 'fallback-secret',
            'EMUSES_DEPLOYMENT_MODE': 'multi_user'
        }, clear=True):
            secret = get_jwt_secret()
            assert secret == 'fallback-secret'


class TestSecretHierarchy:
    """Test multi-source secret hierarchy."""

    def test_file_based_fallback(self):
        """Test fallback to file-based secrets.

        Validates that when Vault is not configured, the system
        falls back to file-based secret storage.
        """
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('file-based-secret')
            tmp_file.flush()

            try:
                with patch.dict(os.environ, {
                    'EMUSES_JWT_SECRET_FILE': tmp_file.name,
                    'EMUSES_DEPLOYMENT_MODE': 'multi_user'
                }, clear=True):
                    secret = get_jwt_secret()
                    assert secret == 'file-based-secret'
            finally:
                os.unlink(tmp_file.name)

    def test_secret_source_priority(self):
        """Test that secret sources are prioritized correctly.

        Validates that Vault takes priority over file, which takes
        priority over environment variables.
        """
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('file-secret')
            tmp_file.flush()

            try:
                # All sources configured, Vault should win
                with patch.dict(os.environ, {
                    'VAULT_ADDR': 'http://vault:8200',
                    'VAULT_TOKEN': 'vault-token',
                    'EMUSES_JWT_SECRET_FILE': tmp_file.name,
                    'EMUSES_JWT_SECRET': 'env-secret',
                    'EMUSES_DEPLOYMENT_MODE': 'multi_user'
                }, clear=True):
                    with patch('hvac.Client') as mock_hvac_client:
                        mock_client = MagicMock()
                        mock_hvac_client.return_value = mock_client
                        mock_client.is_authenticated.return_value = True
                        mock_client.secrets.kv.v2.read_secret_version.return_value = {
                            'data': {'data': {'jwt_secret': 'vault-secret'}}
                        }

                        secret = get_jwt_secret()
                        assert secret == 'vault-secret'

                # Vault unavailable, file should win over environment
                with patch.dict(os.environ, {
                    'EMUSES_JWT_SECRET_FILE': tmp_file.name,
                    'EMUSES_JWT_SECRET': 'env-secret',
                    'EMUSES_DEPLOYMENT_MODE': 'multi_user'
                }, clear=True):
                    secret = get_jwt_secret()
                    assert secret == 'file-secret'

            finally:
                os.unlink(tmp_file.name)
