#!/bin/bash
set -e

# EMUSES HashiCorp Vault Setup Script
# Provides development and production Vault setup for EMUSES secret management

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_MODE="${VAULT_MODE:-dev}"
VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
VAULT_DATA_DIR="${VAULT_DATA_DIR:-/tmp/vault-data}"

echo "🔐 Setting up HashiCorp Vault for EMUSES"
echo "Mode: $VAULT_MODE"
echo "Address: $VAULT_ADDR"

# Check if Vault is installed
if ! command -v vault &> /dev/null; then
    echo "❌ HashiCorp Vault not found in PATH"
    echo "📥 Install Vault:"
    echo "   https://developer.hashicorp.com/vault/downloads"
    echo "   or use: brew install vault (macOS)"
    echo "   or use: apt install vault (Ubuntu)"
    exit 1
fi

# Function to setup development Vault
setup_dev_vault() {
    echo "🚀 Starting Vault in development mode..."
    
    # Kill any existing Vault processes
    pkill vault || true
    sleep 2
    
    # Start Vault in development mode with fixed root token
    vault server -dev -dev-root-token-id="emuses-dev-token" &
    VAULT_PID=$!
    
    # Wait for Vault to start
    echo "⏳ Waiting for Vault to start..."
    sleep 3
    
    # Configure environment
    export VAULT_ADDR="http://127.0.0.1:8200"
    export VAULT_TOKEN="emuses-dev-token"
    
    # Verify connection
    if ! vault status &> /dev/null; then
        echo "❌ Failed to connect to Vault"
        kill $VAULT_PID 2>/dev/null || true
        exit 1
    fi
    
    echo "✅ Development Vault started successfully"
    
    # Store EMUSES secrets
    store_emuses_secrets
    
    # Create configuration script
    create_dev_config
    
    echo "🎉 Development Vault setup complete!"
    echo ""
    echo "📝 To use with EMUSES:"
    echo "   source vault-dev-config.sh"
    echo "   python -m emuses.cli admin create-superuser --email admin@dev.local"
    echo ""
    echo "🛑 To stop Vault:"
    echo "   kill $VAULT_PID"
}

# Function to setup production Vault
setup_prod_vault() {
    echo "🏭 Setting up production Vault configuration..."
    
    # Create Vault data directory
    mkdir -p "$VAULT_DATA_DIR"
    chmod 700 "$VAULT_DATA_DIR"
    
    # Create Vault configuration
    create_prod_config
    
    echo "✅ Production Vault configuration created"
    echo ""
    echo "📝 Next steps:"
    echo "1. Review vault.hcl configuration"
    echo "2. Start Vault: vault server -config=vault.hcl"
    echo "3. Initialize Vault: vault operator init"
    echo "4. Unseal Vault with generated keys"
    echo "5. Store EMUSES secrets: vault kv put secret/emuses ..."
    echo ""
    echo "📖 See documentation for complete production setup"
}

# Function to store EMUSES secrets in Vault
store_emuses_secrets() {
    echo "🔑 Storing EMUSES secrets in Vault..."
    
    # Generate secure secrets
    JWT_SECRET=$(openssl rand -base64 32)
    ADMIN_PASSWORD=$(openssl rand -base64 16)
    POSTGRES_PASSWORD=$(openssl rand -base64 24)
    BACKUP_KEY=$(openssl rand -base64 32)
    
    # Store in Vault
    vault kv put secret/emuses \
        jwt_secret="$JWT_SECRET" \
        admin_password="$ADMIN_PASSWORD" \
        postgres_password="$POSTGRES_PASSWORD" \
        backup_encryption_key="$BACKUP_KEY" \
        generated_date="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    
    echo "✅ EMUSES secrets stored at: secret/emuses"
    
    # Store admin credentials separately for reference
    echo "🔐 Generated admin credentials:"
    echo "   Admin Password: $ADMIN_PASSWORD"
    echo "   (Also stored in Vault at secret/emuses)"
}

# Function to create development configuration
create_dev_config() {
    cat > vault-dev-config.sh << 'EOF'
#!/bin/bash
# EMUSES Development Vault Configuration
# Source this file to configure EMUSES for Vault integration

export VAULT_ADDR="http://127.0.0.1:8200"
export VAULT_TOKEN="emuses-dev-token"
export EMUSES_VAULT_SECRET_PATH="secret/emuses"
export EMUSES_DEPLOYMENT_MODE="multi_user"

echo "✅ EMUSES configured for development Vault"
echo "🔍 Vault status: $(vault status -format=json | jq -r .sealed && echo 'unsealed' || echo 'sealed')"
echo "📍 Vault address: $VAULT_ADDR"
echo "🗂️  Secret path: $EMUSES_VAULT_SECRET_PATH"
EOF
    
    chmod +x vault-dev-config.sh
    echo "📄 Created vault-dev-config.sh"
}

# Function to create production configuration
create_prod_config() {
    cat > vault.hcl << EOF
# EMUSES Production Vault Configuration

storage "file" {
  path = "$VAULT_DATA_DIR"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
  # For production, enable TLS:
  # tls_cert_file = "/path/to/cert.pem"
  # tls_key_file  = "/path/to/key.pem"
}

ui = true

# Clustering configuration (for HA)
# cluster_addr = "https://vault.company.com:8201"
# api_addr = "https://vault.company.com:8200"

# Logging
log_level = "INFO"
log_format = "json"

# Telemetry (optional)
# telemetry {
#   prometheus_retention_time = "30s"
#   disable_hostname = true
# }
EOF

    cat > vault-prod-config.sh << 'EOF'
#!/bin/bash
# EMUSES Production Vault Configuration Template
# Customize these variables for your environment

export VAULT_ADDR="https://vault.company.com:8200"
# export VAULT_TOKEN="your-production-token"
# OR use AppRole authentication:
# export VAULT_ROLE_ID="your-app-role-id"
# export VAULT_SECRET_ID="your-secret-id"
# export VAULT_AUTH_METHOD="approle"

export EMUSES_VAULT_SECRET_PATH="secret/production/emuses"
export EMUSES_DEPLOYMENT_MODE="multi_user"
export DATABASE_URL="postgresql://user:pass@localhost/emuses_prod"

echo "⚠️  Configure production Vault credentials before sourcing this file"
EOF
    
    chmod +x vault-prod-config.sh
    echo "📄 Created vault.hcl and vault-prod-config.sh"
}

# Function to test Vault integration
test_vault_integration() {
    echo "🧪 Testing Vault integration..."
    
    if ! vault status &> /dev/null; then
        echo "❌ Vault not accessible at $VAULT_ADDR"
        return 1
    fi
    
    # Test secret retrieval
    if vault kv get secret/emuses &> /dev/null; then
        echo "✅ EMUSES secrets accessible in Vault"
    else
        echo "⚠️  EMUSES secrets not found in Vault"
        echo "Run with --store-secrets to populate Vault"
    fi
    
    # Test authentication
    if vault auth -method=token &> /dev/null; then
        echo "✅ Vault authentication working"
    else
        echo "❌ Vault authentication failed"
        return 1
    fi
    
    echo "🎉 Vault integration test complete"
}

# Function to clean up development environment
cleanup_dev() {
    echo "🧹 Cleaning up development Vault..."
    pkill vault || true
    rm -f vault-dev-config.sh
    echo "✅ Cleanup complete"
}

# Main script logic
case "${1:-}" in
    --dev)
        setup_dev_vault
        ;;
    --prod)
        setup_prod_vault
        ;;
    --test)
        test_vault_integration
        ;;
    --cleanup)
        cleanup_dev
        ;;
    --help)
        echo "EMUSES Vault Setup Script"
        echo ""
        echo "Usage:"
        echo "  $0 --dev      Setup development Vault (default)"
        echo "  $0 --prod     Create production Vault configuration"
        echo "  $0 --test     Test Vault integration"
        echo "  $0 --cleanup  Clean up development environment"
        echo "  $0 --help     Show this help"
        echo ""
        echo "Environment variables:"
        echo "  VAULT_MODE      dev or prod (default: dev)"
        echo "  VAULT_ADDR      Vault server address"
        echo "  VAULT_DATA_DIR  Vault data directory (prod mode)"
        ;;
    *)
        echo "🔐 EMUSES Vault Setup (default: development mode)"
        echo "Use --help for options"
        setup_dev_vault
        ;;
esac