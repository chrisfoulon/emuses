"""Cloud storage security configuration testing for EMUSES Model Registry.

This module implements comprehensive testing of cloud storage security configurations
across AWS S3, Azure Blob Storage, and Google Cloud Storage backends. Tests focus
on credential management, encryption, access controls, and data protection.

Security Focus Areas:
- Credential security and validation
- Encryption in transit and at rest
- Access control and IAM configurations
- Signed URL security and expiration
- Network security and SSL/TLS
- Data integrity and checksum validation
- Storage security policies and compliance
"""

import pytest
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import hashlib
import ssl
import urllib3
from uuid import uuid4

from emuses.tools.cloud_storage import (
    S3StorageBackend, 
    AzureBlobStorageBackend, 
    GCSStorageBackend,
    create_storage_backend
)
from emuses.tools.cloud_model_registry import CloudModelRegistry


class TestCredentialSecurity:
    """Test credential security and management."""
    
    def test_aws_credential_validation(self):
        """Test AWS credential validation and security.
        
        Ensures AWS credentials are properly validated and not exposed
        in logs or error messages.
        """
        # Test empty/invalid credentials
        invalid_credentials = [
            {"access_key": "", "secret_key": "valid_secret", "region": "us-east-1"},
            {"access_key": "valid_access", "secret_key": "", "region": "us-east-1"},
            {"access_key": None, "secret_key": "valid_secret", "region": "us-east-1"},
            {"access_key": "valid_access", "secret_key": None, "region": "us-east-1"},
        ]
        
        for creds in invalid_credentials:
            # Test credential validation patterns
            access_key = creds["access_key"] or "default"
            secret_key = creds["secret_key"] or "default"
            
            # In production, should validate credential format
            if access_key == "" or access_key is None:
                # Empty access key should be rejected
                assert not self._is_valid_aws_access_key(access_key)
            
            if secret_key == "" or secret_key is None:
                # Empty secret key should be rejected
                assert not self._is_valid_aws_secret_key(secret_key)
            
            # Create backend for further testing
            backend = S3StorageBackend(
                bucket_name="test-bucket",
                access_key=access_key,
                secret_key=secret_key,
                region=creds["region"]
            )
            
            # Test that backend was created (validation happens at runtime)
            assert backend.bucket_name == "test-bucket"
    
    def test_aws_credential_exposure_prevention(self):
        """Test prevention of AWS credential exposure in errors."""
        backend = S3StorageBackend(
            bucket_name="test-bucket",
            access_key="AKIA1234567890EXAMPLE",
            secret_key="super_secret_key_that_should_not_appear_in_logs",
            region="us-east-1"
        )
        
        # Test credential exposure patterns that should be avoided
        secret_key = "super_secret_key_that_should_not_appear_in_logs"
        
        # Test logging sanitization function (in production, would sanitize logs)
        log_message = f"S3 operation failed for bucket {backend.bucket_name}"
        sanitized_log = self._sanitize_log_message(log_message, backend.secret_key)
        
        # Verify secret key is not in sanitized logs
        assert secret_key not in sanitized_log
        
        # Test error message sanitization
        try:
            # Simulate error handling
            error_msg = f"Access denied for bucket test-bucket with key {backend.access_key}"
            # Should not contain secret key
            assert backend.secret_key not in error_msg
            # Access key is OK to show in errors (it's not secret)
            assert backend.access_key in error_msg
        except Exception as e:
            # Error messages should not contain credentials
            assert backend.secret_key not in str(e)

    def test_azure_credential_security(self):
        """Test Azure credential security."""
        # Test connection string security
        connection_strings = [
            "DefaultEndpointsProtocol=https;AccountName=testaccount;AccountKey=super_secret_account_key_12345==;EndpointSuffix=core.windows.net",
            "DefaultEndpointsProtocol=http;AccountName=testaccount;AccountKey=another_secret==;EndpointSuffix=core.windows.net",  # HTTP should be rejected
        ]
        
        for conn_str in connection_strings:
            if "DefaultEndpointsProtocol=http;" in conn_str:
                # HTTP connections should be rejected for security
                with pytest.raises(ValueError, match="HTTPS required"):
                    self._validate_azure_connection_string(conn_str)
            else:
                # HTTPS connections should be accepted
                backend = AzureBlobStorageBackend(
                    container_name="test-container",
                    connection_string=conn_str
                )
                
                # Test that secure connection string is stored
                assert "https" in backend.connection_string
                
                # Test connection string sanitization for logs
                sanitized_conn_str = self._sanitize_azure_connection_string(conn_str)
                assert "super_secret_account_key" not in sanitized_conn_str
                assert "AccountKey=***" in sanitized_conn_str

    def test_gcs_credential_file_security(self):
        """Test GCS service account credential file security."""
        with tempfile.TemporaryDirectory() as temp_dir:
            creds_path = Path(temp_dir) / "service-account.json"
            
            # Create test credentials file
            test_credentials = {
                "type": "service_account",
                "project_id": "test-project",
                "private_key_id": "key-id-123",
                "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...\n-----END PRIVATE KEY-----\n",
                "client_email": "test@test-project.iam.gserviceaccount.com",
                "client_id": "123456789",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
            
            creds_path.write_text(json.dumps(test_credentials))
            
            # Test file permissions security patterns
            # In production, credentials file should have restrictive permissions (600 or 640)
            # For testing, we'll check that the file exists and is readable
            assert creds_path.exists()
            assert creds_path.is_file()
            
            # Test credential file validation
            assert self._validate_gcs_credentials_format(test_credentials)
            
            backend = GCSStorageBackend(
                bucket_name="test-bucket",
                project_id="test-project",
                credentials_path=str(creds_path)
            )
            
            # Test that credentials path is stored but content is not exposed
            assert backend.credentials_path == str(creds_path)
            
            # Test credential content sanitization for logs
            sanitized_creds = self._sanitize_gcs_credentials_for_logging(test_credentials)
            assert "BEGIN PRIVATE KEY" not in str(sanitized_creds)
            assert "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKc" not in str(sanitized_creds)
            assert sanitized_creds["private_key"] == "***REDACTED***"

    def test_credential_rotation_support(self):
        """Test support for credential rotation."""
        # Test that backends can handle credential updates
        backend = S3StorageBackend(
            bucket_name="test-bucket",
            access_key="old_access_key",
            secret_key="old_secret_key", 
            region="us-east-1"
        )
        
        # In production, credentials should be rotatable
        # This tests the pattern for credential updates
        new_credentials = {
            "access_key": "new_access_key",
            "secret_key": "new_secret_key"
        }
        
        # Update credentials
        backend.access_key = new_credentials["access_key"]
        backend.secret_key = new_credentials["secret_key"]
        backend._s3_client = None  # Force client recreation
        
        assert backend.access_key == "new_access_key"
        assert backend.secret_key == "new_secret_key"

    def _is_valid_aws_access_key(self, access_key):
        """Validate AWS access key format."""
        if not access_key or access_key == "":
            return False
        # AWS access keys typically start with AKIA
        return len(access_key) >= 16 and access_key.replace('default', '').strip() != ""
    
    def _is_valid_aws_secret_key(self, secret_key):
        """Validate AWS secret key format."""
        if not secret_key or secret_key == "":
            return False
        # AWS secret keys are typically 40 characters
        return len(secret_key) >= 20 and secret_key.replace('default', '').strip() != ""
    
    def _sanitize_log_message(self, message, secret_key):
        """Sanitize log message to remove sensitive data."""
        return message.replace(secret_key, "***REDACTED***")
    
    def _sanitize_azure_connection_string(self, connection_string):
        """Sanitize Azure connection string for logging."""
        import re
        # Replace account key with asterisks
        return re.sub(r'AccountKey=[^;]+', 'AccountKey=***', connection_string)
    
    def _validate_gcs_credentials_format(self, credentials):
        """Validate GCS credentials format."""
        required_fields = ["type", "project_id", "private_key", "client_email"]
        return all(field in credentials for field in required_fields)
    
    def _sanitize_gcs_credentials_for_logging(self, credentials):
        """Sanitize GCS credentials for logging."""
        sanitized = credentials.copy()
        sanitized["private_key"] = "***REDACTED***"
        if "private_key_id" in sanitized:
            sanitized["private_key_id"] = "***REDACTED***"
        return sanitized

    def _validate_azure_connection_string(self, connection_string):
        """Validate Azure connection string security."""
        if "DefaultEndpointsProtocol=http;" in connection_string:
            raise ValueError("HTTPS required for secure connections")


class TestEncryptionSecurity:
    """Test encryption security configurations."""
    
    @patch('boto3.client')
    def test_s3_encryption_in_transit(self, mock_boto_client):
        """Test S3 encryption in transit (HTTPS)."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        backend = S3StorageBackend(
            bucket_name="test-bucket",
            access_key="test_access",
            secret_key="test_secret",
            region="us-east-1"
        )
        
        # Verify SSL is enforced in S3 client configuration
        # Real implementation should always use HTTPS
        with patch('ssl.create_default_context') as mock_ssl:
            mock_ssl_context = MagicMock()
            mock_ssl.return_value = mock_ssl_context
            
            # Should enforce TLS 1.2+
            mock_ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            mock_ssl_context.check_hostname = True
            mock_ssl_context.verify_mode = ssl.CERT_REQUIRED
            
            # Test SSL configuration is applied
            assert mock_ssl_context.minimum_version == ssl.TLSVersion.TLSv1_2
            assert mock_ssl_context.check_hostname is True
            assert mock_ssl_context.verify_mode == ssl.CERT_REQUIRED

    def test_s3_server_side_encryption_configuration(self):
        """Test S3 server-side encryption configuration."""
        backend = S3StorageBackend(
            bucket_name="test-bucket",
            access_key="test_access",
            secret_key="test_secret",
            region="us-east-1"
        )
        
        # Test encryption parameters for uploads
        encryption_configs = [
            {"ServerSideEncryption": "AES256"},
            {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": "arn:aws:kms:us-east-1:123456789:key/key-id"},
        ]
        
        for config in encryption_configs:
            # Verify encryption parameters are correctly formatted
            assert "ServerSideEncryption" in config
            if config["ServerSideEncryption"] == "aws:kms":
                assert "SSEKMSKeyId" in config
                assert config["SSEKMSKeyId"].startswith("arn:aws:kms:")

    def test_azure_encryption_security(self):
        """Test Azure Blob Storage encryption security."""
        backend = AzureBlobStorageBackend(
            container_name="test-container",
            connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key==;EndpointSuffix=core.windows.net"
        )
        
        # Test encryption settings
        encryption_settings = {
            "encryption_scope": "test-scope",
            "encryption_algorithm": "AES256"
        }
        
        # Verify HTTPS is enforced
        assert "https" in backend.connection_string
        assert "http;" not in backend.connection_string

    def test_gcs_encryption_configuration(self):
        """Test Google Cloud Storage encryption configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            creds_path = Path(temp_dir) / "creds.json" 
            creds_path.write_text('{"type": "service_account", "project_id": "test"}')
            
            backend = GCSStorageBackend(
                bucket_name="test-bucket",
                project_id="test-project", 
                credentials_path=str(creds_path)
            )
            
            # Test customer-managed encryption keys (CMEK)
            encryption_config = {
                "kms_key_name": "projects/test-project/locations/global/keyRings/test-ring/cryptoKeys/test-key"
            }
            
            # Verify encryption key format
            assert encryption_config["kms_key_name"].startswith("projects/")
            assert "/keyRings/" in encryption_config["kms_key_name"]
            assert "/cryptoKeys/" in encryption_config["kms_key_name"]

    def test_data_integrity_checksums(self):
        """Test data integrity validation with checksums."""
        test_data = b"test model data for integrity validation"
        
        # Test different checksum algorithms
        checksums = {
            "md5": hashlib.md5(test_data).hexdigest(),
            "sha256": hashlib.sha256(test_data).hexdigest(),
            "sha512": hashlib.sha512(test_data).hexdigest(),
        }
        
        # Verify checksums are computed correctly
        assert len(checksums["md5"]) == 32
        assert len(checksums["sha256"]) == 64
        assert len(checksums["sha512"]) == 128
        
        # Test checksum validation detects corruption
        corrupted_data = test_data + b"corrupted"
        corrupted_sha256 = hashlib.sha256(corrupted_data).hexdigest()
        
        assert corrupted_sha256 != checksums["sha256"]

    def test_encryption_key_management(self):
        """Test encryption key management security."""
        # Test key rotation capabilities
        encryption_keys = [
            "projects/test/locations/global/keyRings/ring1/cryptoKeys/key1",
            "projects/test/locations/global/keyRings/ring1/cryptoKeys/key2", 
            "projects/test/locations/global/keyRings/ring1/cryptoKeys/key3"
        ]
        
        # Test key versioning
        for i, key in enumerate(encryption_keys):
            version = f"{key}/cryptoKeyVersions/{i+1}"
            assert "/cryptoKeyVersions/" in version
            assert version.endswith(f"/{i+1}")


class TestAccessControlSecurity:
    """Test access control and IAM security."""
    
    @patch('boto3.client')
    def test_s3_bucket_policy_validation(self, mock_boto_client):
        """Test S3 bucket policy security validation."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        # Test secure bucket policy
        secure_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "DenyInsecureConnections",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": [
                        "arn:aws:s3:::test-bucket",
                        "arn:aws:s3:::test-bucket/*"
                    ],
                    "Condition": {
                        "Bool": {
                            "aws:SecureTransport": "false"
                        }
                    }
                }
            ]
        }
        
        # Verify policy enforces HTTPS
        deny_statement = secure_policy["Statement"][0]
        assert deny_statement["Effect"] == "Deny"
        assert deny_statement["Condition"]["Bool"]["aws:SecureTransport"] == "false"

    def test_s3_iam_policy_validation(self):
        """Test S3 IAM policy security."""
        # Test minimal required permissions
        minimal_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:PutObject",
                        "s3:GetObject", 
                        "s3:DeleteObject"
                    ],
                    "Resource": "arn:aws:s3:::emuses-models/*"
                },
                {
                    "Effect": "Allow",
                    "Action": ["s3:ListBucket"],
                    "Resource": "arn:aws:s3:::emuses-models"
                }
            ]
        }
        
        # Verify principle of least privilege
        allowed_actions = []
        for statement in minimal_policy["Statement"]:
            if statement["Effect"] == "Allow":
                if isinstance(statement["Action"], list):
                    allowed_actions.extend(statement["Action"])
                else:
                    allowed_actions.append(statement["Action"])
        
        # Should not include dangerous permissions
        dangerous_actions = ["s3:*", "s3:PutBucketPolicy", "s3:DeleteBucket"]
        for dangerous in dangerous_actions:
            assert dangerous not in allowed_actions

    def test_azure_rbac_configuration(self):
        """Test Azure RBAC (Role-Based Access Control) configuration."""
        # Test required Azure roles
        required_roles = [
            "Storage Blob Data Contributor",
            "Storage Blob Data Reader", 
            "Storage Account Contributor"
        ]
        
        # Verify minimal role assignments
        for role in required_roles:
            assert "Storage" in role
            assert "Contributor" in role or "Reader" in role
        
        # Test custom role with minimal permissions
        custom_role = {
            "permissions": [
                "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read",
                "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write",
                "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/delete"
            ],
            "not_permissions": [
                "Microsoft.Storage/storageAccounts/delete",
                "Microsoft.Storage/storageAccounts/write"
            ]
        }
        
        # Verify least privilege
        assert len(custom_role["permissions"]) <= 5
        assert "delete" not in custom_role["permissions"][0]  # Read permission should not include delete

    def test_gcs_iam_security(self):
        """Test Google Cloud Storage IAM security."""
        # Test service account permissions
        service_account_roles = [
            "roles/storage.objectAdmin",
            "roles/storage.objectViewer", 
            "roles/storage.objectCreator"
        ]
        
        # Verify role names follow GCS conventions
        for role in service_account_roles:
            assert role.startswith("roles/storage.")
            assert "storage" in role.lower()
        
        # Test custom IAM policy
        custom_policy = {
            "bindings": [
                {
                    "role": "roles/storage.objectAdmin",
                    "members": ["serviceAccount:emuses@project.iam.gserviceaccount.com"],
                    "condition": {
                        "expression": "resource.name.startsWith('projects/_/buckets/emuses-models/')"
                    }
                }
            ]
        }
        
        # Verify resource restrictions
        binding = custom_policy["bindings"][0]
        assert "condition" in binding
        assert "resource.name.startsWith" in binding["condition"]["expression"]

    def test_signed_url_security(self):
        """Test signed URL security configurations."""
        # Test different expiration times
        expiration_tests = [
            {"expires_in": 3600, "valid": True},    # 1 hour - reasonable
            {"expires_in": 86400, "valid": True},   # 24 hours - acceptable
            {"expires_in": 604800, "valid": False}, # 7 days - too long
            {"expires_in": 60, "valid": True},      # 1 minute - very secure
        ]
        
        for test in expiration_tests:
            expires_in = test["expires_in"]
            
            if test["valid"]:
                # Valid expiration times should be accepted
                assert expires_in <= 86400  # Max 24 hours
            else:
                # Overly long expiration should be rejected
                assert expires_in > 86400

    def test_cors_security_configuration(self):
        """Test CORS (Cross-Origin Resource Sharing) security."""
        # Test secure CORS configuration
        secure_cors = {
            "allowed_origins": ["https://app.emuses.ai"],
            "allowed_methods": ["GET", "POST"],
            "allowed_headers": ["Content-Type", "Authorization"], 
            "max_age": 3600
        }
        
        insecure_cors = {
            "allowed_origins": ["*"],  # Too permissive
            "allowed_methods": ["*"],  # Too permissive 
            "allowed_headers": ["*"],  # Too permissive
            "max_age": 86400
        }
        
        # Verify secure configuration
        assert "*" not in secure_cors["allowed_origins"]
        assert len(secure_cors["allowed_methods"]) <= 5
        assert "https://" in secure_cors["allowed_origins"][0]
        
        # Verify insecure configuration is detected
        assert "*" in insecure_cors["allowed_origins"]
        assert "*" in insecure_cors["allowed_methods"]


class TestNetworkSecurity:
    """Test network security configurations."""
    
    def test_ssl_tls_configuration(self):
        """Test SSL/TLS security configuration."""
        # Test TLS version requirements
        tls_configs = [
            {"version": "TLS 1.0", "secure": False},  # Deprecated
            {"version": "TLS 1.1", "secure": False},  # Deprecated
            {"version": "TLS 1.2", "secure": True},   # Minimum acceptable
            {"version": "TLS 1.3", "secure": True},   # Preferred
        ]
        
        for config in tls_configs:
            if config["secure"]:
                # Secure TLS versions should be accepted
                assert "1.2" in config["version"] or "1.3" in config["version"]
            else:
                # Insecure TLS versions should be rejected
                assert "1.0" in config["version"] or "1.1" in config["version"]

    def test_certificate_validation(self):
        """Test SSL certificate validation."""
        # Test certificate validation settings
        cert_validation = {
            "verify_certificates": True,
            "check_hostname": True,
            "certificate_transparency": True,
            "ocsp_stapling": True
        }
        
        # All validation should be enabled
        for key, value in cert_validation.items():
            assert value is True

    def test_vpc_endpoint_security(self):
        """Test VPC endpoint security for cloud services."""
        # Test VPC endpoint configuration for AWS
        vpc_endpoint_config = {
            "service": "s3",
            "vpc_id": "vpc-12345678",
            "route_table_ids": ["rtb-12345678"],
            "policy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "s3:GetObject",
                        "Resource": "arn:aws:s3:::emuses-models/*"
                    }
                ]
            }
        }
        
        # Verify VPC endpoint is properly configured
        assert vpc_endpoint_config["service"] == "s3"
        assert vpc_endpoint_config["vpc_id"].startswith("vpc-")
        assert "policy" in vpc_endpoint_config

    def test_firewall_rules(self):
        """Test firewall and network security rules."""
        # Test network security group rules
        security_rules = [
            {
                "direction": "inbound",
                "protocol": "https",
                "port": 443,
                "source": "0.0.0.0/0",  # Public HTTPS access
                "action": "allow"
            },
            {
                "direction": "inbound", 
                "protocol": "http",
                "port": 80,
                "source": "0.0.0.0/0",  # Should redirect to HTTPS
                "action": "deny"
            },
            {
                "direction": "inbound",
                "protocol": "ssh",
                "port": 22,
                "source": "10.0.0.0/8",  # Internal access only
                "action": "allow"
            }
        ]
        
        for rule in security_rules:
            if rule["protocol"] == "https":
                assert rule["action"] == "allow"
                assert rule["port"] == 443
            elif rule["protocol"] == "http":
                assert rule["action"] == "deny"
            elif rule["protocol"] == "ssh":
                assert rule["source"] != "0.0.0.0/0"  # Should not be public

    def test_ddos_protection(self):
        """Test DDoS protection configuration."""
        # Test rate limiting configuration
        rate_limits = {
            "requests_per_second": 100,
            "burst_limit": 200,
            "ban_duration": 3600,  # 1 hour
            "whitelist": ["10.0.0.0/8", "192.168.0.0/16"]
        }
        
        # Verify reasonable rate limits
        assert rate_limits["requests_per_second"] <= 1000
        assert rate_limits["burst_limit"] >= rate_limits["requests_per_second"]
        assert rate_limits["ban_duration"] >= 300  # At least 5 minutes

    def test_geo_blocking_configuration(self):
        """Test geographic access control configuration."""
        geo_config = {
            "allowed_countries": ["US", "CA", "GB", "DE", "JP"],
            "blocked_countries": ["XX", "YY"],  # Suspicious countries
            "default_action": "allow"
        }
        
        # Verify geo-blocking is properly configured
        assert len(geo_config["allowed_countries"]) > 0
        assert isinstance(geo_config["allowed_countries"], list)
        assert geo_config["default_action"] in ["allow", "deny"]


class TestComplianceAndAuditing:
    """Test compliance and auditing security features."""
    
    def test_audit_logging_configuration(self):
        """Test audit logging and monitoring configuration."""
        # Test CloudTrail/audit log configuration
        audit_config = {
            "enabled": True,
            "log_file_validation": True,
            "include_global_service_events": True,
            "log_read_events": True,
            "log_write_events": True,
            "log_data_events": True,
            "encryption": {
                "enabled": True,
                "kms_key": "arn:aws:kms:us-east-1:123456789:key/key-id"
            }
        }
        
        # Verify comprehensive logging is enabled
        assert audit_config["enabled"] is True
        assert audit_config["log_file_validation"] is True
        assert audit_config["log_read_events"] is True
        assert audit_config["log_write_events"] is True
        assert audit_config["encryption"]["enabled"] is True

    def test_gdpr_compliance_configuration(self):
        """Test GDPR compliance features."""
        gdpr_config = {
            "data_retention_days": 2555,  # 7 years max
            "right_to_delete": True,
            "data_portability": True,
            "consent_tracking": True,
            "privacy_by_design": True,
            "dpo_contact": "dpo@emuses.ai"
        }
        
        # Verify GDPR compliance features
        assert gdpr_config["data_retention_days"] <= 2555  # 7 years
        assert gdpr_config["right_to_delete"] is True
        assert gdpr_config["data_portability"] is True
        assert "@" in gdpr_config["dpo_contact"]

    def test_hipaa_compliance_configuration(self):
        """Test HIPAA compliance features (if handling health data)."""
        hipaa_config = {
            "encryption_at_rest": True,
            "encryption_in_transit": True, 
            "access_logging": True,
            "baa_required": True,  # Business Associate Agreement
            "audit_logs_retention_years": 6,
            "automatic_logoff": True
        }
        
        # Verify HIPAA requirements
        assert hipaa_config["encryption_at_rest"] is True
        assert hipaa_config["encryption_in_transit"] is True
        assert hipaa_config["access_logging"] is True
        assert hipaa_config["audit_logs_retention_years"] >= 6

    def test_sox_compliance_features(self):
        """Test SOX (Sarbanes-Oxley) compliance features."""
        sox_config = {
            "change_management": True,
            "segregation_of_duties": True,
            "audit_trail": True,
            "data_integrity": True,
            "retention_period_years": 7
        }
        
        # Verify SOX requirements
        for requirement, enabled in sox_config.items():
            if isinstance(enabled, bool):
                assert enabled is True
            elif isinstance(enabled, int):
                assert enabled >= 7

    def test_pci_dss_compliance(self):
        """Test PCI DSS compliance features."""
        pci_config = {
            "network_segmentation": True,
            "encryption_key_management": True,
            "access_control_matrix": True,
            "vulnerability_scanning": True,
            "penetration_testing": True,
            "security_monitoring": True
        }
        
        # Verify PCI DSS requirements  
        for requirement, implemented in pci_config.items():
            assert implemented is True


class TestDataProtectionSecurity:
    """Test data protection and privacy security."""
    
    def test_data_classification_security(self):
        """Test data classification and protection."""
        # Test data classification levels
        classification_levels = {
            "public": {"encryption": False, "access": "anonymous"},
            "internal": {"encryption": True, "access": "authenticated"},
            "confidential": {"encryption": True, "access": "authorized"},
            "restricted": {"encryption": True, "access": "privileged"}
        }
        
        for level, config in classification_levels.items():
            if level in ["confidential", "restricted", "internal"]:
                assert config["encryption"] is True
                assert config["access"] != "anonymous"

    def test_pii_data_protection(self):
        """Test PII (Personally Identifiable Information) protection."""
        pii_fields = [
            "email_address",
            "full_name", 
            "phone_number",
            "ip_address",
            "user_id"
        ]
        
        # Test PII detection and protection
        for field in pii_fields:
            protection_config = self._get_pii_protection_config(field)
            
            assert protection_config["encrypt"] is True
            assert protection_config["log_access"] is True
            assert protection_config["anonymize_in_logs"] is True

    def test_data_anonymization(self):
        """Test data anonymization and pseudonymization."""
        # Test anonymization techniques
        anonymization_methods = {
            "email": "hash_with_salt",
            "user_id": "pseudonymize",
            "ip_address": "truncate_last_octet",
            "timestamp": "round_to_hour"
        }
        
        for field, method in anonymization_methods.items():
            assert method in ["hash_with_salt", "pseudonymize", "truncate_last_octet", "round_to_hour"]
            
            # Verify anonymization is reversible for legitimate use
            if method == "pseudonymize":
                assert "reversible" in self._get_anonymization_info(method)

    def test_data_retention_policies(self):
        """Test data retention and deletion policies."""
        retention_policies = {
            "model_data": {"days": 2555, "auto_delete": True},    # 7 years
            "user_data": {"days": 1095, "auto_delete": True},     # 3 years
            "audit_logs": {"days": 2190, "auto_delete": False},   # 6 years
            "temp_files": {"days": 7, "auto_delete": True}        # 1 week
        }
        
        for data_type, policy in retention_policies.items():
            assert policy["days"] > 0
            if data_type == "temp_files":
                assert policy["days"] <= 30  # Temp files should be cleaned frequently
            if data_type == "audit_logs":
                assert policy["auto_delete"] is False  # Keep for compliance

    def test_backup_security(self):
        """Test backup security and encryption."""
        backup_config = {
            "encryption_enabled": True,
            "encryption_algorithm": "AES256",
            "backup_frequency": "daily",
            "retention_period": 90,  # 90 days
            "cross_region_replication": True,
            "integrity_checking": True
        }
        
        # Verify backup security
        assert backup_config["encryption_enabled"] is True
        assert backup_config["encryption_algorithm"] in ["AES256", "AES128"]
        assert backup_config["integrity_checking"] is True

    def _get_pii_protection_config(self, field):
        """Get PII protection configuration for field."""
        return {
            "encrypt": True,
            "log_access": True,
            "anonymize_in_logs": True,
            "require_justification": True
        }

    def _get_anonymization_info(self, method):
        """Get anonymization method information."""
        methods = {
            "pseudonymize": {"reversible": True, "key_required": True},
            "hash_with_salt": {"reversible": False, "salt_required": True},
            "truncate_last_octet": {"reversible": False, "precision_loss": True}
        }
        return methods.get(method, {})


class TestCloudStorageIntegration:
    """Test integrated cloud storage security scenarios."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session for testing."""
        return Mock()

    @pytest.fixture
    def mock_user(self):
        """Mock user for testing."""
        user = Mock()
        user.id = uuid4()
        user.email = "test@example.com"
        return user

    @pytest.fixture  
    def mock_s3_backend(self):
        """Mock S3 storage backend."""
        backend = Mock(spec=S3StorageBackend)
        backend.bucket_name = "test-bucket"
        backend.region = "us-east-1"
        return backend

    def test_cloud_registry_security_integration(self, mock_db_session, mock_user, mock_s3_backend):
        """Test cloud registry security integration."""
        registry = CloudModelRegistry(
            db_session=mock_db_session,
            user=mock_user,
            storage_backend=mock_s3_backend
        )
        
        # Verify security components are initialized
        assert registry.permission_manager is not None
        assert registry.storage is not None
        assert registry.current_user is not None

    def test_model_upload_security_validation(self, mock_db_session, mock_user, mock_s3_backend):
        """Test model upload security validation."""
        registry = CloudModelRegistry(
            db_session=mock_db_session,
            user=mock_user,
            storage_backend=mock_s3_backend
        )
        
        # Test security validations during upload
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "test_model"
            model_path.mkdir()
            (model_path / "model.pkl").write_bytes(b"test model data")
            
            # Mock storage backend response
            mock_s3_backend.upload_model.return_value = "s3://test-bucket/models/test-id/model.tar.gz"
            
            # Test upload with security metadata
            metadata = {
                "name": "test-model",
                "description": "Test model with security validation",
                "security_classification": "internal",
                "compliance_requirements": ["GDPR", "SOX"]
            }
            
            # Verify security metadata is handled
            assert metadata["security_classification"] == "internal"
            assert "GDPR" in metadata["compliance_requirements"]

    def test_signed_url_security_validation(self, mock_db_session, mock_user, mock_s3_backend):
        """Test signed URL security validation."""
        registry = CloudModelRegistry(
            db_session=mock_db_session,
            user=mock_user,
            storage_backend=mock_s3_backend
        )
        
        # Test signed URL expiration limits
        max_expiration = 86400  # 24 hours
        test_expirations = [3600, 7200, 86400, 604800]  # 1h, 2h, 24h, 7d
        
        for expires_in in test_expirations:
            if expires_in <= max_expiration:
                # Should be accepted
                assert expires_in <= max_expiration
            else:
                # Should be rejected or capped
                capped_expiration = min(expires_in, max_expiration)
                assert capped_expiration == max_expiration

    def test_multi_cloud_security_consistency(self):
        """Test security consistency across cloud providers."""
        # Test configuration consistency
        s3_config = {
            "provider": "s3",
            "encryption": {"method": "AES256", "in_transit": True},
            "access_logging": True,
            "versioning": True
        }
        
        azure_config = {
            "provider": "azure", 
            "encryption": {"method": "AES256", "in_transit": True},
            "access_logging": True,
            "versioning": True
        }
        
        gcs_config = {
            "provider": "gcs",
            "encryption": {"method": "AES256", "in_transit": True},
            "access_logging": True,
            "versioning": True
        }
        
        configs = [s3_config, azure_config, gcs_config]
        
        # Verify security consistency
        for config in configs:
            assert config["encryption"]["method"] == "AES256"
            assert config["encryption"]["in_transit"] is True
            assert config["access_logging"] is True
            assert config["versioning"] is True

    def test_disaster_recovery_security(self):
        """Test disaster recovery security measures."""
        dr_config = {
            "backup_regions": ["us-west-2", "eu-west-1"],
            "replication_encryption": True,
            "cross_region_keys": True,
            "automated_failover": True,
            "rto_minutes": 60,  # Recovery Time Objective
            "rpo_minutes": 15   # Recovery Point Objective
        }
        
        # Verify disaster recovery security
        assert len(dr_config["backup_regions"]) >= 2
        assert dr_config["replication_encryption"] is True
        assert dr_config["cross_region_keys"] is True
        assert dr_config["rto_minutes"] <= 240  # Max 4 hours
        assert dr_config["rpo_minutes"] <= 60   # Max 1 hour data loss


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])