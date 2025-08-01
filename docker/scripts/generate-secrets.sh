#!/bin/bash
set -e

# Script to generate secure secrets for EMUSES production deployment

SECRETS_DIR="$(dirname "$0")/../secrets"
SECRETS_FILE="$SECRETS_DIR/secrets.env"

echo "Generating EMUSES production secrets..."

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

# Create secrets file
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
echo "Generated admin credentials:"
echo "  Admin Password: $ADMIN_PASSWORD"
echo "  Admin Token: $ADMIN_TOKEN"
echo ""
echo "Save these credentials in a secure password manager!"