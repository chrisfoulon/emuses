#!/bin/bash
set -e

# Enhanced script to generate secure secrets for EMUSES production deployment
# Supports both traditional file-based secrets and HashiCorp Vault integration

SECRETS_DIR="$(dirname "$0")/../secrets"
SECRETS_FILE="$SECRETS_DIR/secrets.env"
VAULT_INTEGRATION="${VAULT_INTEGRATION:-false}"
VAULT_PATH="${VAULT_PATH:-secret/emuses}"

echo "🔐 Generating EMUSES production secrets..."
echo "Vault integration: $VAULT_INTEGRATION"

# Create secrets directory if it doesn't exist
mkdir -p "$SECRETS_DIR"

# Function to generate a secure random string
generate_secret() {
    local length=${1:-32}
    openssl rand -hex "$length"
}

# Function to generate a secure password
generate_password() {
    local length=${1:-16}
    openssl rand -base64 "$length" | tr -d "=+/" | cut -c1-${length}
}

# Generate secrets
JWT_SECRET=$(generate_secret 32)
POSTGRES_PASSWORD=$(generate_password 24)
ADMIN_PASSWORD=$(generate_password 16)
ADMIN_TOKEN=$(generate_secret 32)
DATA_ENCRYPTION_KEY=$(generate_secret 32)
SESSION_SECRET_KEY=$(generate_secret 32)
BACKUP_ENCRYPTION_KEY=$(generate_secret 32)

# Function to store secrets in HashiCorp Vault
store_secrets_in_vault() {
    echo "🏦 Storing secrets in HashiCorp Vault..."
    
    # Verify Vault connection
    if ! vault status &> /dev/null; then
        echo "❌ Cannot connect to Vault at ${VAULT_ADDR:-'(not set)'}"
        echo "💡 Ensure Vault is running and VAULT_ADDR/VAULT_TOKEN are set"
        exit 1
    fi
    
    # Store secrets in Vault
    vault kv put "$VAULT_PATH" \
        jwt_secret="$JWT_SECRET" \
        postgres_password="$POSTGRES_PASSWORD" \
        admin_password="$ADMIN_PASSWORD" \
        admin_token="$ADMIN_TOKEN" \
        data_encryption_key="$DATA_ENCRYPTION_KEY" \
        session_secret_key="$SESSION_SECRET_KEY" \
        backup_encryption_key="$BACKUP_ENCRYPTION_KEY" \
        generated_date="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    
    echo "✅ Secrets stored in Vault at: $VAULT_PATH"
    
    # Create Vault configuration file
    cat > "$SECRETS_DIR/vault-config.env" << EOF
# EMUSES Vault Configuration
# Source this file to configure EMUSES for Vault integration

export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
export VAULT_TOKEN="${VAULT_TOKEN:-your-vault-token}"
export EMUSES_VAULT_SECRET_PATH="$VAULT_PATH"
export EMUSES_DEPLOYMENT_MODE="multi_user"

echo "✅ EMUSES configured for Vault integration"
echo "🔍 Vault status: \$(vault status &>/dev/null && echo 'accessible' || echo 'not accessible')"
echo "📍 Vault path: $VAULT_PATH"
EOF
    
    chmod 600 "$SECRETS_DIR/vault-config.env"
    
    echo "📝 Vault configuration created: $SECRETS_DIR/vault-config.env"
    echo ""
    echo "🚀 To use with EMUSES:"
    echo "   source $SECRETS_DIR/vault-config.env"
    echo "   python -m emuses.cli admin create-superuser"
}

# Function to store secrets in traditional file
store_secrets_in_file() {
    echo "📁 Storing secrets in traditional file..."
    create_secrets_file
}

# Create traditional secrets file
create_secrets_file() {
cat > "$SECRETS_FILE" << EOF
# EMUSES Production Secrets
# Generated on $(date)
# WARNING: Keep this file secure and never commit to version control

# =============================================================================
# CRITICAL SECURITY SECRETS
# =============================================================================

JWT_SECRET=$JWT_SECRET
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
ADMIN_PASSWORD=$ADMIN_PASSWORD
ADMIN_TOKEN=$ADMIN_TOKEN

# =============================================================================
# EMAIL SECRETS (Fill in manually)
# =============================================================================

SMTP_PASSWORD=

# =============================================================================
# EXTERNAL SERVICE SECRETS (Fill in manually if needed)
# =============================================================================

EXTERNAL_API_KEY=
OAUTH_CLIENT_SECRET=

# =============================================================================
# ENCRYPTION KEYS
# =============================================================================

DATA_ENCRYPTION_KEY=$DATA_ENCRYPTION_KEY
SESSION_SECRET_KEY=$SESSION_SECRET_KEY

# =============================================================================
# BACKUP ENCRYPTION
# =============================================================================

BACKUP_ENCRYPTION_KEY=$BACKUP_ENCRYPTION_KEY

# =============================================================================
# MONITORING SECRETS (Fill in manually if needed)
# =============================================================================

MONITORING_API_KEY=
EOF

# Set secure permissions
chmod 600 "$SECRETS_FILE"

echo "Secrets generated successfully!"
echo "File location: $SECRETS_FILE"
echo ""
echo "IMPORTANT SECURITY NOTES:"
echo "1. The secrets file has been created with secure permissions (600)"
echo "2. Review and fill in any manual secrets (SMTP_PASSWORD, etc.)"
echo "3. Never commit this file to version control"
echo "4. Store backups of this file in a secure location"
echo "5. Rotate secrets regularly for enhanced security"
echo ""
# Store secrets based on integration method
if [ "$VAULT_INTEGRATION" = "true" ] && command -v vault &> /dev/null; then
    store_secrets_in_vault
else
    store_secrets_in_file
fi

echo ""
echo "🔑 Generated admin credentials:"
echo "  Admin Password: $ADMIN_PASSWORD"
echo "  Admin Token: $ADMIN_TOKEN"
echo ""
echo "💾 Save these credentials in a secure password manager!"

if [ "$VAULT_INTEGRATION" = "true" ]; then
    echo ""
    echo "🏦 Vault Integration Notes:"
    echo "• Secrets are stored in Vault and file for backup"
    echo "• Use vault-config.env to configure EMUSES for Vault"
    echo "• Vault provides audit trails and centralized secret management"
fi

# Set secure permissions and finish
chmod 600 "$SECRETS_FILE"

}

echo ""
echo "✅ Secret generation complete!"
echo "📍 File location: $SECRETS_FILE"