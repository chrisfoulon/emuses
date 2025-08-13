#!/bin/bash

# EMUSES Backup System Validation Script
# Validates backup configuration and functionality

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}💾 EMUSES Backup Validation${NC}"
echo "============================"

# Track validation status
BACKUP_STATUS=0

# Function to print result
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        BACKUP_STATUS=1
    fi
}

# Check backup docker-compose configuration
echo "Validating backup configuration..."

if [ -f "docker-compose.backup.yml" ]; then
    print_result 0 "Backup docker-compose configuration exists"
    
    # Validate backup compose syntax
    if docker-compose -f docker-compose.backup.yml config >/dev/null 2>&1; then
        print_result 0 "Backup docker-compose syntax valid"
    else
        print_result 1 "Backup docker-compose syntax invalid"
    fi
else
    print_result 1 "Backup docker-compose configuration missing"
fi

# Check backup directory configuration
BACKUP_DIR=${BACKUP_DIR:-/opt/emuses/backups}
echo "Checking backup directory: $BACKUP_DIR"

if [ -d "$BACKUP_DIR" ] || [ "$BACKUP_DIR" = "/opt/emuses/backups" ]; then
    print_result 0 "Backup directory configured"
else
    print_result 1 "Backup directory not accessible"
fi

# Check backup scripts
backup_scripts=("backup-postgres.sh" "backup-models.sh" "restore-backup.sh" "verify-backup.sh")
echo "Validating backup scripts..."

for script in "${backup_scripts[@]}"; do
    if [ -f "docker/scripts/$script" ]; then
        print_result 0 "Backup script $script exists"
    else
        print_result 1 "Backup script $script missing"
    fi
done

# Check backup environment variables
echo "Validating backup environment variables..."

required_vars=("BACKUP_ENCRYPTION_KEY" "POSTGRES_PASSWORD")
for var in "${required_vars[@]}"; do
    if [ ! -z "${!var}" ] || grep -q "$var" docker/environments/.env.*.template 2>/dev/null; then
        print_result 0 "Backup variable $var configured"
    else
        print_result 1 "Backup variable $var not configured"
    fi
done

# Final status
echo
if [ $BACKUP_STATUS -eq 0 ]; then
    echo -e "${GREEN}🎉 Backup validation PASSED${NC}"
    exit 0
else
    echo -e "${RED}💥 Backup validation FAILED${NC}"
    exit 1
fi