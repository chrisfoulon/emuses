# Multi-User Service Vault Integration - Implementation Context

## Phase 2 Integration Context

**Context Status**: ✅ **READY FOR IMPLEMENTATION**  
**Dependencies**: Phase 1 Multi-User Service Implementation (COMPLETED)  
**Integration Points**: Authentication system, Docker scripts, deployment workflows

## Current Implementation State

### Phase 1 Deliverables Available for Integration
- **UserManager Integration**: Complete admin CRUD operations using FastAPI-Users
- **Schema Compatibility**: UserCreate works with all AdminUserCreateRequest fields  
- **Error Handling**: Standardized HTTP status codes and comprehensive exception handling
- **Database Operations**: Real database state changes verified via integration tests
- **Quality Standards**: Flake8 compliant, comprehensive error handling

### Existing Secret Management Implementation
**File**: `emuses/multi_user_service/auth.py:25-47`
```python
def get_jwt_secret() -> str:
    """Get JWT secret from environment with validation."""
    jwt_secret = os.getenv("EMUSES_JWT_SECRET")
    if not jwt_secret:
        deployment_mode = os.getenv("EMUSES_DEPLOYMENT_MODE", "local")
        if deployment_mode != "local":
            raise ValueError(
                "EMUSES_JWT_SECRET environment variable is required for multi-user deployment"
            )
        jwt_secret = "development-secret-key-change-in-production"
    return jwt_secret
```

**Enhancement Strategy**: Extend this function to support Vault while maintaining existing fallback behavior.

## Vault Integration Architecture

### Multi-Source Secret Hierarchy
```python
# Priority order for secret retrieval
1. HashiCorp Vault (enterprise security)
2. Secure file (production standard)  
3. Environment variable (compatibility)
4. Development default (local only)
```

### Configuration Detection
```python
def vault_configured() -> bool:
    """Detect if Vault is properly configured."""
    return bool(
        os.getenv("VAULT_ADDR") and 
        (os.getenv("VAULT_TOKEN") or 
         (os.getenv("VAULT_ROLE_ID") and os.getenv("VAULT_SECRET_ID")))
    )
```

## Integration Points and Dependencies

### Level 1: Core Authentication Enhancement
**Files**: `emuses/multi_user_service/auth.py`
- **Existing Function**: `get_jwt_secret()` - Extend with Vault support
- **New Dependencies**: `hvac` library for Vault client
- **Integration**: Maintains existing FastAPI-Users integration

### Level 2: Configuration and Environment
**Environment Variables**:
```bash
# Vault Configuration (Optional)
VAULT_ADDR="http://127.0.0.1:8200"
VAULT_TOKEN="vault-token"
VAULT_NAMESPACE="emuses"                    # Optional
EMUSES_VAULT_SECRET_PATH="secret/emuses"   # Optional, defaults provided

# Alternative Authentication
VAULT_ROLE_ID="app-role-id"         # For AppRole auth
VAULT_SECRET_ID="app-secret-id"     # For AppRole auth
VAULT_AUTH_METHOD="token"           # token, approle, kubernetes

# Existing Fallbacks (Maintained)
EMUSES_JWT_SECRET_FILE="/path/to/jwt.secret"
EMUSES_JWT_SECRET="fallback-secret"
```

### Level 3: Docker and Script Integration
**Existing Scripts to Enhance**:
- `docker/scripts/generate-secrets.sh` - Add Vault storage option
- `docker/scripts/validate-security.sh` - Add Vault connectivity checks
- `docker/scripts/validate-deployment.sh` - Verify Vault integration
- `docker/scripts/health-check.sh` - Include Vault health status

**New Scripts**:
- `docker/scripts/setup-vault.sh` - Development Vault setup
- `docker/scripts/vault-backup.sh` - Vault secret backup procedures

## Working Integration Examples

### Enhanced Secret Retrieval
```python
def get_jwt_secret() -> str:
    """Enhanced JWT secret retrieval with multi-source support."""
    
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
    if os.getenv("EMUSES_DEPLOYMENT_MODE", "local") == "local":
        logger.warning("Using development JWT secret - configure secure secret for production")
        return "development-secret-key-change-in-production"
    
    raise ValueError(
        "No JWT secret configured. Configure Vault (VAULT_ADDR + VAULT_TOKEN), "
        "file (EMUSES_JWT_SECRET_FILE), or environment variable (EMUSES_JWT_SECRET)"
    )

def _get_secret_from_vault(secret_name: str) -> Optional[str]:
    """Retrieve specific secret from HashiCorp Vault."""
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

class VaultError(Exception):
    """Custom exception for Vault-related errors."""
    pass
```

### Docker Script Enhancement Example
```bash
# Enhanced generate-secrets.sh
#!/bin/bash
set -e

VAULT_INTEGRATION=${VAULT_INTEGRATION:-false}
SECRETS_DIR="$(dirname "$0")/../secrets"

if [ "$VAULT_INTEGRATION" = "true" ] && command -v vault &> /dev/null; then
    echo "🔐 Storing secrets in HashiCorp Vault..."
    
    # Verify Vault connection
    if ! vault status &> /dev/null; then
        echo "❌ Vault server not accessible at $VAULT_ADDR"
        exit 1
    fi
    
    # Generate and store secrets
    JWT_SECRET=$(openssl rand -base64 32)
    ADMIN_PASSWORD=$(openssl rand -base64 16)
    POSTGRES_PASSWORD=$(openssl rand -base64 24)
    
    vault kv put secret/emuses \
        jwt_secret="$JWT_SECRET" \
        admin_password="$ADMIN_PASSWORD" \
        postgres_password="$POSTGRES_PASSWORD"
    
    echo "✅ Secrets stored in Vault at: secret/emuses"
    echo "📝 Configure EMUSES with:"
    echo "   export VAULT_ADDR=$VAULT_ADDR"
    echo "   export VAULT_TOKEN=$VAULT_TOKEN"
    
else
    echo "📁 Generating traditional secrets file..."
    # Original file-based generation (existing code)
    mkdir -p "$SECRETS_DIR"
    # ... existing implementation
fi
```

## Testing and Validation Strategy

### Integration Test Scenarios
1. **Vault Available + Valid Config**: Secrets retrieved from Vault successfully
2. **Vault Available + Invalid Config**: Graceful fallback to file/environment
3. **Vault Unavailable**: Immediate fallback without blocking startup
4. **No Configuration**: Uses development defaults in local mode
5. **Multiple Auth Methods**: Token, AppRole, and Kubernetes authentication

### Mock Testing Framework
```python
# tests/multi_user_service/test_vault_integration.py
import pytest
from unittest.mock import patch, MagicMock

class TestVaultIntegration:
    
    @patch('hvac.Client')
    def test_vault_secret_retrieval_success(self, mock_vault_client):
        """Test successful secret retrieval from Vault."""
        # Setup mock
        mock_client = MagicMock()
        mock_vault_client.return_value = mock_client
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': {'jwt_secret': 'vault-secret-123'}}
        }
        
        # Test
        with patch.dict(os.environ, {
            'VAULT_ADDR': 'http://vault:8200',
            'VAULT_TOKEN': 'test-token'
        }):
            secret = get_jwt_secret()
            assert secret == 'vault-secret-123'
    
    def test_vault_fallback_to_file(self):
        """Test fallback to file when Vault unavailable."""
        # Test graceful fallback behavior
        # ...
```

## Security and Compliance Considerations

### Audit Trail Integration
```python
def audit_secret_access(source: str, success: bool, error: str = None):
    """Log secret access for compliance auditing."""
    audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": source,  # "vault", "file", "environment"
        "success": success,
        "error": error,
        "deployment_mode": os.getenv("EMUSES_DEPLOYMENT_MODE", "local")
    }
    
    logger.info(f"Secret access audit: {audit_entry}")
    # Could also send to external audit system
```

### Error Handling Standards
- **No Secret Exposure**: Never log actual secret values
- **Clear Error Messages**: Helpful troubleshooting without security leaks
- **Graceful Degradation**: System remains functional during Vault outages
- **Authentication Validation**: Proper Vault authentication verification

## Performance and Reliability

### Caching Strategy
```python
# Optional: Cache Vault secrets with TTL
class VaultSecretCache:
    def __init__(self, ttl_seconds=300):  # 5 minute cache
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get_cached_secret(self, key: str) -> Optional[str]:
        if key in self.cache:
            secret, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return secret
        return None
```

### Connection Pooling
- Reuse Vault client connections where possible
- Implement connection timeout and retry logic
- Graceful handling of network issues

## Deployment Scenarios

### Development Environment
```bash
# Quick development setup
export VAULT_ADDR="http://127.0.0.1:8200"
export VAULT_TOKEN="dev-root-token"
./docker/scripts/setup-vault.sh
```

### Production Environment
```bash
# Production Vault with AppRole authentication
export VAULT_ADDR="https://vault.company.com:8200"
export VAULT_ROLE_ID="emuses-prod-role"
export VAULT_SECRET_ID="secure-secret-id"
export VAULT_AUTH_METHOD="approle"
export EMUSES_VAULT_SECRET_PATH="secret/production/emuses"
```

### Hybrid Environment
```bash
# Vault for secrets, file for fallback
export VAULT_ADDR="https://vault.company.com:8200"
export VAULT_TOKEN="prod-token"
export EMUSES_JWT_SECRET_FILE="/etc/emuses/jwt.secret"  # Backup
```

## Quality Assurance Metrics

### Code Quality
- **Flake8 Compliance**: All new code passes linting
- **Type Hints**: Proper typing for Vault integration functions
- **Documentation**: NumPy-style docstrings for all new functions
- **Error Handling**: Comprehensive exception handling with proper logging

### Security Metrics
- **Secret Exposure**: Zero occurrences of secrets in logs or error messages
- **Authentication**: 100% validation of Vault authentication before secret access
- **Fallback Security**: Graceful degradation maintains security posture
- **Audit Coverage**: All secret access events properly logged

---

**Implementation Readiness**: ✅ **READY FOR PHASE 2**  
**Integration Points Identified**: Authentication system, Docker scripts, environment configuration  
**Testing Strategy Defined**: Mock testing, integration scenarios, security validation  
**Quality Standards**: Maintains existing code quality and security standards

**Next Steps**: Begin Task 2A.1 - Enhanced Secret Management implementation using established patterns and integration points.