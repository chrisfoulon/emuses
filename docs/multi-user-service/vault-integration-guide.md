# EMUSES Vault Integration Guide

**Enterprise-grade secret management for secure EMUSES deployments**

## **Essential Information**

EMUSES supports optional HashiCorp Vault integration for enterprise-grade secret management. This provides centralized secret storage, audit trails, and enhanced security for production deployments while maintaining full backward compatibility with existing configurations.

### Quick Start Options

| Deployment Type | Configuration Method | Security Level |
|-----------------|---------------------|----------------|
| **Development** | `./docker/scripts/setup-vault.sh --dev` | Development |
| **Production** | Vault server + environment variables | Enterprise |
| **Traditional** | File/environment secrets (existing) | Standard |

### Key Benefits

- **Centralized Secret Management**: All secrets stored in Vault with versioning
- **Audit Trails**: Complete log of secret access for compliance (SOC 2, PCI DSS)
- **Dynamic Secrets**: Foundation for automated secret rotation
- **Graceful Fallbacks**: Works without Vault for existing deployments

<details markdown="1">
<summary>🔧 **Development Quick Setup**</summary>

For local development with Vault integration:

```bash
# Install Vault (if not already installed)
# macOS: brew install vault
# Ubuntu: apt install vault
# Or download from: https://developer.hashicorp.com/vault/downloads

# Start development Vault with EMUSES secrets
cd /path/to/emuses
./docker/scripts/setup-vault.sh --dev

# Configure environment
source vault-dev-config.sh

# Verify integration
python -c "from emuses.multi_user_service.auth import get_jwt_secret; print('Secret source: Vault')"

# Start EMUSES with Vault integration
python -m emuses.api.main
```

**Result**: EMUSES will use Vault for secret management with full audit logging.

</details>

<details markdown="1">
<summary>🏭 **Production Deployment**</summary>

For production environments with existing Vault infrastructure:

```bash
# Configure Vault connection
export VAULT_ADDR="https://vault.company.com:8200"
export VAULT_TOKEN="your-production-token"
export EMUSES_VAULT_SECRET_PATH="secret/production/emuses"

# Alternative: AppRole authentication
export VAULT_ADDR="https://vault.company.com:8200"
export VAULT_ROLE_ID="emuses-prod-role"
export VAULT_SECRET_ID="secure-secret-id"
export VAULT_AUTH_METHOD="approle"

# Generate and store secrets in Vault
VAULT_INTEGRATION=true ./docker/scripts/generate-secrets.sh

# Deploy EMUSES
python -m emuses.api.main
```

**Security Features**: Enterprise audit trails, access policies, encrypted storage.

</details>

<details markdown="1">
<summary>💻 **Migration from File-Based Secrets**</summary>

Migrate existing deployments to Vault without downtime:

```bash
# Step 1: Backup existing secrets
cp /etc/emuses/secrets.env /etc/emuses/secrets.env.backup

# Step 2: Configure Vault connection
export VAULT_ADDR="https://vault.company.com:8200"
export VAULT_TOKEN="migration-token"

# Step 3: Import existing secrets to Vault
vault kv put secret/emuses \
  jwt_secret="$(grep JWT_SECRET /etc/emuses/secrets.env | cut -d'=' -f2)" \
  postgres_password="$(grep POSTGRES_PASSWORD /etc/emuses/secrets.env | cut -d'=' -f2)"

# Step 4: Update EMUSES configuration
export EMUSES_VAULT_SECRET_PATH="secret/emuses"

# Step 5: Restart EMUSES (will use Vault automatically)
systemctl restart emuses

# Step 6: Verify Vault integration
python -m emuses.cli admin system-status
```

**Fallback Safety**: If Vault becomes unavailable, EMUSES automatically falls back to file-based secrets.

</details>

## **Configuration Reference**

### Environment Variables

EMUSES uses a priority-based secret hierarchy. Configure any level based on your security requirements:

| Variable | Required | Purpose | Example |
|----------|----------|---------|---------|
| `VAULT_ADDR` | Yes* | Vault server URL | `https://vault.company.com:8200` |
| `VAULT_TOKEN` | Yes* | Vault authentication token | `hvs.CAESIJ...` (sensitive) |
| `VAULT_ROLE_ID` | No | AppRole authentication ID | `emuses-prod-role` |
| `VAULT_SECRET_ID` | No | AppRole secret ID | `secure-secret-id` (sensitive) |
| `EMUSES_VAULT_SECRET_PATH` | No | Vault secret path | `secret/production/emuses` |
| `EMUSES_JWT_SECRET_FILE` | No | Fallback file path | `/etc/emuses/jwt.secret` |
| `EMUSES_JWT_SECRET` | No | Fallback environment | `fallback-secret` (not recommended) |

**Priority Order**: Vault → File → Environment → Development Default

### Authentication Methods

<details markdown="1">
<summary>🔑 **Token Authentication (Recommended for Development)**</summary>

Simple token-based authentication suitable for development and testing:

```bash
# Configure token authentication
export VAULT_ADDR="http://127.0.0.1:8200"
export VAULT_TOKEN="dev-root-token"

# Verify connection
vault status

# EMUSES automatically detects and uses token authentication
python -m emuses.api.main
```

**Use Cases**: Development, testing, simple deployments
**Security**: Suitable for trusted environments

</details>

<details markdown="1">
<summary>🏢 **AppRole Authentication (Recommended for Production)**</summary>

Role-based authentication suitable for production deployments:

```bash
# Configure AppRole authentication
export VAULT_ADDR="https://vault.company.com:8200"
export VAULT_ROLE_ID="emuses-prod-role"
export VAULT_SECRET_ID="secure-secret-id"
export VAULT_AUTH_METHOD="approle"

# EMUSES automatically uses AppRole authentication
python -m emuses.api.main
```

**Use Cases**: Production, automated deployments, CI/CD
**Security**: Role-based access control with audit trails

</details>

<details markdown="1">
<summary>🔐 **Kubernetes Authentication (Advanced)**</summary>

Service account-based authentication for Kubernetes deployments:

```yaml
# kubernetes-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: emuses
spec:
  template:
    spec:
      serviceAccountName: emuses-vault-auth
      containers:
      - name: emuses
        env:
        - name: VAULT_ADDR
          value: "https://vault.company.com:8200"
        - name: VAULT_AUTH_METHOD
          value: "kubernetes"
        - name: VAULT_ROLE
          value: "emuses-k8s-role"
```

**Use Cases**: Kubernetes deployments, container orchestration
**Security**: Service account-based authentication

</details>

## **Vault Setup and Administration**

### Development Vault Setup

<details markdown="1">
<summary>🚀 **Automated Development Setup**</summary>

Use the provided script for quick development setup:

```bash
# Start development Vault server
./docker/scripts/setup-vault.sh --dev

# What this does:
# 1. Starts Vault in dev mode with fixed root token
# 2. Stores EMUSES secrets automatically
# 3. Creates environment configuration
# 4. Provides connection details

# Expected output:
# ✅ Development Vault started successfully
# 📝 To use with EMUSES:
#    source vault-dev-config.sh
#    python -m emuses.cli admin create-superuser --email admin@dev.local

# Stop development Vault
pkill vault
```

**Features**: Automatic secret population, development-friendly defaults

</details>

<details markdown="1">
<summary>⚙️ **Manual Development Setup**</summary>

For custom development configurations:

```bash
# Start Vault in development mode
vault server -dev -dev-root-token-id="my-dev-token" &

# Configure environment
export VAULT_ADDR="http://127.0.0.1:8200"
export VAULT_TOKEN="my-dev-token"

# Store EMUSES secrets
vault kv put secret/emuses \
  jwt_secret="$(openssl rand -base64 32)" \
  admin_password="DevAdmin123!" \
  postgres_password="DevDB123!"

# Configure EMUSES
export EMUSES_VAULT_SECRET_PATH="secret/emuses"
export EMUSES_DEPLOYMENT_MODE="multi_user"

# Start EMUSES
python -m emuses.api.main
```

**Flexibility**: Custom token, paths, and secret values

</details>

### Production Vault Configuration

<details markdown="1">
<summary>🏭 **Production Vault Server**</summary>

Configure Vault for production use:

```bash
# Create Vault configuration
cat > vault.hcl << EOF
storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_cert_file = "/path/to/cert.pem"
  tls_key_file  = "/path/to/key.pem"
}

ui = true
log_level = "INFO"
EOF

# Start Vault server
vault server -config=vault.hcl &

# Initialize Vault (first time only)
vault operator init

# Unseal Vault (after restart)
vault operator unseal <unseal-key-1>
vault operator unseal <unseal-key-2>
vault operator unseal <unseal-key-3>

# Create EMUSES secrets
vault kv put secret/production/emuses \
  jwt_secret="$(openssl rand -base64 32)" \
  postgres_password="SecureProductionPassword" \
  admin_password="SecureAdminPassword"
```

**Security**: TLS encryption, sealed storage, access policies

</details>

<details markdown="1">
<summary>🔒 **Access Policies and Security**</summary>

Configure fine-grained access control:

```bash
# Create EMUSES-specific policy
vault policy write emuses-policy - << EOF
path "secret/data/emuses" {
  capabilities = ["read"]
}

path "secret/metadata/emuses" {
  capabilities = ["list", "read"]
}
EOF

# Create AppRole for EMUSES
vault auth enable approle

vault write auth/approle/role/emuses-prod \
  token_policies="emuses-policy" \
  token_ttl=1h \
  token_max_ttl=4h \
  bind_secret_id=true

# Get role credentials
vault read auth/approle/role/emuses-prod/role-id
vault write -f auth/approle/role/emuses-prod/secret-id
```

**Benefits**: Least privilege access, audit trails, credential rotation

</details>

## **Troubleshooting and Support**

### Common Issues

<details markdown="1">
<summary>🚨 **Vault Connection Issues**</summary>

**Problem**: `Cannot connect to Vault at http://127.0.0.1:8200`

```bash
# Diagnose connection
vault status

# Check Vault server status
ps aux | grep vault

# Verify network connectivity
curl -I $VAULT_ADDR/v1/sys/health

# Common solutions:
# 1. Start Vault server: vault server -dev
# 2. Check VAULT_ADDR: export VAULT_ADDR="http://127.0.0.1:8200"
# 3. Verify firewall rules
# 4. Check TLS configuration
```

**Automatic Fallback**: EMUSES falls back to file/environment secrets when Vault is unavailable.

</details>

<details markdown="1">
<summary>🔐 **Authentication Failures**</summary>

**Problem**: `Vault authentication failed`

```bash
# Check token validity
vault token lookup

# Verify authentication method
echo "Auth method: $VAULT_AUTH_METHOD"
echo "Token: ${VAULT_TOKEN:0:10}..." # Show first 10 chars only

# Test manual authentication
vault auth -method=token

# Common solutions:
# 1. Refresh expired token
# 2. Verify role permissions
# 3. Check AppRole credentials
# 4. Review Vault policies
```

**Graceful Degradation**: EMUSES continues operation with fallback secrets.

</details>

<details markdown="1">
<summary>📦 **Missing Dependencies**</summary>

**Problem**: `hvac package not installed`

```bash
# Install Vault client library
pip install hvac>=1.0.0

# Or install with EMUSES
pip install -e .[vault]  # If vault extras group exists

# Verify installation
python -c "import hvac; print('hvac version:', hvac.__version__)"

# Alternative: Update requirements
echo "hvac>=1.0.0" >> requirements.txt
pip install -r requirements.txt
```

**Optional Dependency**: EMUSES works without hvac, falling back to traditional secrets.

</details>

### Performance and Monitoring

<details markdown="1">
<summary>📊 **Vault Performance Monitoring**</summary>

Monitor Vault integration performance:

```bash
# Check secret retrieval timing
time python -c "from emuses.multi_user_service.auth import get_jwt_secret; get_jwt_secret()"

# Monitor Vault server metrics
vault read sys/metrics

# EMUSES system status with Vault
python -m emuses.cli admin system-status --detailed

# Expected secret retrieval: < 100ms
# Expected Vault connection: < 50ms
```

**Performance Targets**: Sub-100ms secret retrieval, minimal startup overhead

</details>

<details markdown="1">
<summary>🔍 **Audit Trail Analysis**</summary>

Review Vault audit logs for compliance:

```bash
# Enable audit logging
vault audit enable file file_path=/vault/logs/audit.log

# Query secret access
grep "secret/emuses" /vault/logs/audit.log | jq '.time, .request.path, .auth.display_name'

# EMUSES access patterns
grep "emuses" /vault/logs/audit.log | jq -c '{time: .time, user: .auth.display_name, action: .request.operation}'

# Compliance reporting
cat /vault/logs/audit.log | jq -r 'select(.request.path | contains("secret/emuses")) | "\(.time) \(.auth.display_name) \(.request.operation)"' | sort
```

**Compliance**: SOC 2, PCI DSS audit trail requirements

</details>

## **Best Practices and Security**

### Security Recommendations

<details markdown="1">
<summary>🛡️ **Production Security Checklist**</summary>

Essential security measures for production deployments:

```bash
# ✅ TLS encryption
export VAULT_ADDR="https://vault.company.com:8200"  # Use HTTPS

# ✅ Least privilege access
vault policy write emuses-readonly - << EOF
path "secret/data/emuses" {
  capabilities = ["read"]
}
EOF

# ✅ Token rotation
vault write auth/approle/role/emuses token_ttl=1h token_max_ttl=4h

# ✅ Audit logging
vault audit enable file file_path=/secure/vault-audit.log

# ✅ Secret rotation
vault kv put secret/emuses jwt_secret="$(openssl rand -base64 32)"

# ✅ Access monitoring
grep "secret/emuses" /secure/vault-audit.log | tail -10
```

**Security Standards**: Enterprise-grade protection with audit compliance

</details>

<details markdown="1">
<summary>⚡ **Performance Optimization**</summary>

Optimize Vault integration for production workloads:

```bash
# Connection pooling configuration
export VAULT_CLIENT_TIMEOUT=30
export VAULT_MAX_RETRIES=3

# Caching configuration (if implemented)
export VAULT_SECRET_TTL=300  # 5 minute cache

# Monitor performance
time python -c "from emuses.multi_user_service.auth import get_jwt_secret; print(get_jwt_secret())"

# Load balancing (multiple Vault servers)
export VAULT_ADDR="https://vault-lb.company.com:8200"
```

**Performance**: Sub-100ms response times, connection reuse, caching

</details>

### Operational Procedures

<details markdown="1">
<summary>🔄 **Secret Rotation**</summary>

Automate secret rotation for enhanced security:

```bash
#!/bin/bash
# rotate-emuses-secrets.sh

# Generate new JWT secret
NEW_JWT_SECRET=$(openssl rand -base64 32)

# Store in Vault with versioning
vault kv put secret/emuses jwt_secret="$NEW_JWT_SECRET"

# Restart EMUSES to pick up new secret
systemctl restart emuses

# Verify secret rotation
python -m emuses.cli admin system-status

echo "Secret rotation completed: $(date)"
```

**Automation**: Schedule weekly/monthly rotation, automated verification

</details>

<details markdown="1">
<summary>💾 **Backup and Recovery**</summary>

Backup Vault data for disaster recovery:

```bash
# Backup Vault data
vault operator raft snapshot save emuses-backup-$(date +%Y%m%d).snap

# Store backup securely
aws s3 cp emuses-backup-$(date +%Y%m%d).snap s3://emuses-backups/vault/

# Recovery procedure
vault operator raft snapshot restore emuses-backup-20231215.snap

# Verify recovery
vault kv get secret/emuses
```

**Recovery**: Complete disaster recovery procedures, encrypted backups

</details>

## **Migration and Integration**

### Migrating from Traditional Secrets

<details markdown="1">
<summary>🔄 **Zero-Downtime Migration**</summary>

Migrate existing deployments without service interruption:

```bash
# Phase 1: Prepare Vault
export VAULT_ADDR="https://vault.company.com:8200"
export VAULT_TOKEN="migration-token"

# Phase 2: Import existing secrets
vault kv put secret/emuses \
  jwt_secret="$(cat /etc/emuses/jwt.secret)" \
  postgres_password="$(grep POSTGRES_PASSWORD /etc/emuses/secrets.env | cut -d'=' -f2)"

# Phase 3: Configure dual-source (Vault + fallback)
export EMUSES_VAULT_SECRET_PATH="secret/emuses"
export EMUSES_JWT_SECRET_FILE="/etc/emuses/jwt.secret"  # Fallback

# Phase 4: Rolling restart
systemctl reload emuses  # Uses Vault, falls back to file if needed

# Phase 5: Verify Vault usage
python -c "import logging; logging.basicConfig(level=logging.INFO); from emuses.multi_user_service.auth import get_jwt_secret; get_jwt_secret()"
# Should log: "JWT secret loaded from HashiCorp Vault"

# Phase 6: Remove file fallback (optional)
unset EMUSES_JWT_SECRET_FILE
```

**Safety**: Dual-source configuration ensures no downtime during migration

</details>

### CI/CD Integration

<details markdown="1">
<summary>🔧 **Automated Deployment**</summary>

Integrate Vault with deployment pipelines:

```yaml
# .github/workflows/deploy-emuses.yml
name: Deploy EMUSES with Vault

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - name: Authenticate to Vault
      uses: hashicorp/vault-action@v2
      with:
        url: ${{ secrets.VAULT_ADDR }}
        method: approle
        roleId: ${{ secrets.VAULT_ROLE_ID }}
        secretId: ${{ secrets.VAULT_SECRET_ID }}
        secrets: |
          secret/data/emuses jwt_secret | JWT_SECRET

    - name: Deploy EMUSES
      env:
        VAULT_ADDR: ${{ secrets.VAULT_ADDR }}
        VAULT_TOKEN: ${{ steps.auth.outputs.vault-token }}
      run: |
        export EMUSES_VAULT_SECRET_PATH="secret/emuses"
        docker run -e VAULT_ADDR -e VAULT_TOKEN -e EMUSES_VAULT_SECRET_PATH emuses:latest
```

**Automation**: Secure credential injection, automated deployments

</details>

## **Support and Resources**

### Getting Help

- **Built-in Help**: `python -m emuses.cli admin help`
- **System Status**: `python -m emuses.cli admin system-status --detailed`
- **Vault Documentation**: [HashiCorp Vault Docs](https://developer.hashicorp.com/vault/docs)
- **EMUSES Issues**: Contact your system administrator

### Additional Resources

- **Vault Installation**: [Official Download](https://developer.hashicorp.com/vault/downloads)
- **Security Best Practices**: [Vault Security Guide](https://developer.hashicorp.com/vault/tutorials/security)
- **Enterprise Features**: Contact HashiCorp for Vault Enterprise
- **EMUSES Multi-User Guide**: `docs/multi-user-service/admin-guide.md`

---

**🔒 This guide provides comprehensive Vault integration for secure, auditable, enterprise-grade EMUSES deployments while maintaining full backward compatibility with existing configurations.**

---

*EMUSES Vault Integration Guide - Enterprise Security Documentation*