# Cloud Storage Troubleshooting Guide

## Overview

This guide provides troubleshooting steps for common issues encountered when deploying and using cloud storage with the EMUSES model registry system.

## Common Issues and Solutions

### 1. Authentication and Authorization Errors

#### AWS S3 Authentication Issues

**Symptoms:**
- `NoCredentialsError`: Unable to locate credentials
- `InvalidAccessKeyId`: The AWS Access Key Id you provided does not exist
- `SignatureDoesNotMatch`: Signature calculated does not match

**Solutions:**

1. **Verify AWS Credentials**
   ```bash
   # Check if credentials are properly set
   aws configure list
   
   # Test basic S3 access
   aws s3 ls s3://your-bucket-name/
   ```

2. **Environment Variable Configuration**
   ```bash
   export AWS_ACCESS_KEY_ID="your-access-key"
   export AWS_SECRET_ACCESS_KEY="your-secret-key"
   export AWS_DEFAULT_REGION="us-west-2"
   ```

3. **IAM Policy Requirements**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:GetObject",
           "s3:PutObject",
           "s3:DeleteObject",
           "s3:ListBucket",
           "s3:GetObjectVersion"
         ],
         "Resource": [
           "arn:aws:s3:::your-bucket-name",
           "arn:aws:s3:::your-bucket-name/*"
         ]
       }
     ]
   }
   ```

#### Azure Blob Storage Authentication Issues

**Symptoms:**
- `AuthenticationError`: Server failed to authenticate the request
- `InvalidStorageAccount`: The specified storage account is invalid

**Solutions:**

1. **Verify Connection String**
   ```bash
   # Test connection with Azure CLI
   az storage blob list --container-name your-container --connection-string "your-connection-string"
   ```

2. **Connection String Format**
   ```
   DefaultEndpointsProtocol=https;AccountName=accountname;AccountKey=accountkey;EndpointSuffix=core.windows.net
   ```

3. **Storage Account Permissions**
   - Ensure the account has Contributor or Storage Blob Data Contributor role
   - Check that the storage account allows access from your IP/network

#### Google Cloud Storage Authentication Issues

**Symptoms:**
- `DefaultCredentialsError`: Could not automatically determine credentials
- `Forbidden`: Access denied

**Solutions:**

1. **Service Account Setup**
   ```bash
   # Set up application default credentials
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
   
   # Test access
   gsutil ls gs://your-bucket-name/
   ```

2. **Required IAM Roles**
   - Storage Object Admin (for full access)
   - Storage Object Creator (for uploads)
   - Storage Object Viewer (for downloads)

### 2. Network and Connectivity Issues

#### Timeout Errors

**Symptoms:**
- `ConnectTimeoutError`: Connection timed out
- `ReadTimeoutError`: Read operation timed out

**Solutions:**

1. **Check Network Connectivity**
   ```bash
   # Test basic connectivity to AWS
   curl -I https://s3.amazonaws.com
   
   # Test Azure connectivity
   curl -I https://myaccount.blob.core.windows.net
   
   # Test GCS connectivity
   curl -I https://storage.googleapis.com
   ```

2. **Adjust Timeout Settings**
   ```python
   from emuses.extras.cloud_resilience import CloudOperationTimeout
   
   # Configure longer timeouts for slow networks
   timeout_config = CloudOperationTimeout(
       connection_timeout=30.0,  # 30 seconds
       read_timeout=60.0,        # 60 seconds
       total_timeout=600.0       # 10 minutes
   )
   ```

3. **Firewall and Proxy Configuration**
   - Ensure ports 443 (HTTPS) and 80 (HTTP) are open
   - Configure proxy settings if behind corporate firewall
   - Check if cloud storage domains are whitelisted

#### SSL/TLS Certificate Issues

**Symptoms:**
- `SSLError`: Certificate verification failed
- `SSLCertVerificationError`: Certificate does not match hostname

**Solutions:**

1. **Update Certificate Store**
   ```bash
   # Update system certificates (Ubuntu/Debian)
   sudo apt-get update && sudo apt-get install ca-certificates
   
   # Update certificates (CentOS/RHEL)
   sudo yum update ca-certificates
   ```

2. **Python SSL Configuration**
   ```python
   import ssl
   import certifi
   
   # Use certifi for certificate validation
   ssl_context = ssl.create_default_context(cafile=certifi.where())
   ```

### 3. Performance Issues

#### Slow Upload/Download Speeds

**Symptoms:**
- Long upload/download times
- Timeouts during large file transfers

**Solutions:**

1. **Enable Multipart Uploads**
   ```python
   # Configure multipart upload thresholds
   # (Implementation specific to cloud provider)
   MULTIPART_THRESHOLD = 100 * 1024 * 1024  # 100MB
   MULTIPART_CHUNKSIZE = 10 * 1024 * 1024   # 10MB chunks
   ```

2. **Use Transfer Acceleration (AWS)**
   ```python
   # Enable S3 Transfer Acceleration
   s3_backend = S3StorageBackend(
       bucket_name="your-bucket",
       access_key="your-key",
       secret_key="your-secret",
       region="us-west-2",
       use_accelerate_endpoint=True
   )
   ```

3. **Optimize Compression**
   ```bash
   # Check compressed bundle sizes
   ls -lh /tmp/model_bundles/
   
   # Monitor compression ratios in logs
   grep "compression_ratio" /var/log/emuses/model_registry.log
   ```

#### High Latency

**Solutions:**

1. **Choose Optimal Regions**
   - Deploy storage in regions closest to your users
   - Use multi-region deployment for global access

2. **Implement Caching**
   ```python
   # Enable local caching for frequently accessed models
   from emuses.extras.model_cache import ModelCache
   
   cache = ModelCache(
       backend="redis",
       ttl=3600,  # 1 hour
       max_size="1GB"
   )
   ```

### 4. Configuration Issues

#### Invalid Bucket/Container Names

**Symptoms:**
- `InvalidBucketName`: Bucket name contains invalid characters
- `ContainerNotFound`: Container does not exist

**Solutions:**

1. **AWS S3 Bucket Naming Rules**
   - 3-63 characters long
   - Only lowercase letters, numbers, and hyphens
   - Cannot start or end with hyphen
   - Cannot contain consecutive periods

2. **Azure Container Naming Rules**
   - 3-63 characters long
   - Only lowercase letters, numbers, and hyphens
   - Cannot start or end with hyphen
   - Cannot contain consecutive hyphens

3. **GCS Bucket Naming Rules**
   - 3-63 characters long
   - Only lowercase letters, numbers, and hyphens
   - Cannot start or end with hyphen
   - Cannot contain 'goog' substring

#### Region/Location Mismatches

**Symptoms:**
- `PermanentRedirect`: Bucket is in a different region
- `AccessDenied`: Cross-region access denied

**Solutions:**

1. **Verify Resource Locations**
   ```bash
   # Check S3 bucket region
   aws s3api get-bucket-location --bucket your-bucket-name
   
   # Check Azure storage account location
   az storage account show --name yourstorageaccount --query location
   ```

2. **Update Configuration**
   ```python
   # Ensure client region matches resource region
   backend = S3StorageBackend(
       bucket_name="your-bucket",
       region="us-west-2"  # Match actual bucket region
   )
   ```

### 5. Data Integrity Issues

#### Corrupted File Downloads

**Symptoms:**
- `ValueError`: Invalid model bundle format
- `EOFError`: Compressed file appears to be corrupted

**Solutions:**

1. **Enable Integrity Checks**
   ```python
   # Verify checksums during upload/download
   import hashlib
   
   def verify_file_integrity(file_path, expected_hash):
       with open(file_path, 'rb') as f:
           actual_hash = hashlib.sha256(f.read()).hexdigest()
       return actual_hash == expected_hash
   ```

2. **Retry Failed Transfers**
   ```python
   from emuses.extras.cloud_resilience import with_exponential_backoff
   
   @with_exponential_backoff(max_attempts=5)
   async def reliable_download(storage_url, target_path):
       await backend.download_model(storage_url, target_path)
   ```

## Diagnostic Commands

### 1. Configuration Validation

```bash
# Run comprehensive cloud configuration validation
python -m emuses.extras.cloud_validation validate --environment production --config config/cloud.json

# Test specific provider configuration
python -m emuses.extras.cloud_validation test-connection --provider aws --config config/aws.json
```

### 2. Health Checks

```bash
# Run health checks for all configured providers
python -m emuses admin health-check --include-cloud

# Test specific storage operations
python -m emuses admin test-storage --provider s3 --operation upload,download,delete
```

### 3. Performance Testing

```bash
# Benchmark upload/download performance
python -m emuses admin benchmark-storage --size 100MB --iterations 5

# Test concurrent operations
python -m emuses admin test-concurrent --operations 10 --size 50MB
```

## Monitoring and Logging

### 1. Enable Debug Logging

```python
import logging

# Enable debug logging for cloud operations
logging.getLogger('emuses.extras.cloud_storage').setLevel(logging.DEBUG)
logging.getLogger('emuses.extras.cloud_resilience').setLevel(logging.DEBUG)
```

### 2. Monitor Key Metrics

```bash
# Monitor error rates
grep "ERROR" /var/log/emuses/cloud_storage.log | tail -20

# Check retry attempts
grep "retry" /var/log/emuses/cloud_storage.log | wc -l

# Monitor performance metrics
grep "duration_ms" /var/log/emuses/cloud_storage.log | tail -10
```

### 3. Alerting Configuration

Set up alerts for:
- High error rates (>5% of operations)
- Slow response times (>30 seconds for uploads)
- Authentication failures
- Circuit breaker activations

## Emergency Recovery Procedures

### 1. Backup and Recovery

```bash
# List available backups
python -m emuses admin list-backups --provider all

# Restore from backup
python -m emuses admin restore-backup --backup-id backup-20250101-120000 --target-provider s3

# Verify data integrity after restore
python -m emuses admin verify-integrity --provider s3 --sample-size 100
```

### 2. Failover Procedures

```bash
# Switch to backup provider
python -m emuses admin failover --from s3 --to azure --verify

# Check failover status
python -m emuses admin failover-status

# Rollback if needed
python -m emuses admin rollback-failover --to s3
```

## Getting Help

### 1. Documentation Resources

- [API Documentation](API_REFERENCE.md)
- [Model Registry User Guide](model-registry/user_guide.md)
- [Multi-User Service Admin Guide](multi-user-service/admin-guide.md)

### 2. Support Channels

- GitHub Issues: Report bugs and feature requests
- Community Forum: Ask questions and share solutions
- Documentation: Check latest updates and examples

### 3. Diagnostic Information to Collect

When reporting issues, include:
- Cloud provider and region
- EMUSES version and configuration
- Error messages and stack traces
- Network configuration details
- Timing information for performance issues
- Steps to reproduce the issue

## Best Practices Summary

1. **Always use IAM roles with minimal required permissions**
2. **Enable logging and monitoring for all cloud operations**
3. **Implement retry logic with exponential backoff**
4. **Use regional deployments for better performance**
5. **Regularly test backup and recovery procedures**
6. **Monitor costs and usage patterns**
7. **Keep credentials secure and rotate regularly**
8. **Test configuration changes in staging environment first**

## Version Compatibility

| EMUSES Version | AWS SDK | Azure SDK | GCS SDK |
|----------------|---------|-----------|---------|
| 1.0.x          | 1.24.x  | 12.14.x   | 2.10.x  |
| 1.1.x          | 1.26.x  | 12.16.x   | 2.12.x  |
| 1.2.x          | 1.28.x  | 12.18.x   | 2.14.x  |

Always check compatibility matrices before upgrading dependencies.