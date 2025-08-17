#!/bin/bash

# EMUSES Security Configuration Validation Script
# Validates security configurations and best practices

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔒 EMUSES Security Validation${NC}"
echo "=============================="

# Track validation status
SECURITY_STATUS=0

# Function to print result
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        SECURITY_STATUS=1
    fi
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check SSL/TLS configuration
echo "Validating SSL/TLS configuration..."

if [ -d "docker/ssl" ]; then
    print_result 0 "SSL directory exists"
    
    # Check for SSL certificate files (in production)
    if [ "$ENVIRONMENT" = "production" ]; then
        if [ -f "docker/ssl/emuses.crt" ] && [ -f "docker/ssl/emuses.key" ]; then
            print_result 0 "SSL certificates present"
        else
            print_result 1 "SSL certificates missing for production"
        fi
    else
        print_warning "SSL certificates not required for $ENVIRONMENT environment"
    fi
else
    print_result 1 "SSL directory missing"
fi

# Check environment variable security
echo "Validating environment variable security..."

# Check for secure password requirements
env_files=(docker/environments/.env.*.template)
for env_file in "${env_files[@]}"; do
    if [ -f "$env_file" ]; then
        # Check that sensitive variables use placeholders, not real values
        if grep -q "CHANGE_ME\|password_change_me\|secret_key_change_me" "$env_file"; then
            print_result 0 "Environment template uses secure placeholders"
        else
            print_result 1 "Environment template may contain hardcoded secrets"
        fi
        
        # Check for required security variables
        required_security_vars=("JWT_SECRET" "POSTGRES_PASSWORD" "BACKUP_ENCRYPTION_KEY")
        for var in "${required_security_vars[@]}"; do
            if grep -q "^$var=" "$env_file"; then
                print_result 0 "Security variable $var defined in $(basename "$env_file")"
            else
                print_result 1 "Security variable $var missing from $(basename "$env_file")"
            fi
        done
    fi
done

# Check database security configuration
echo "Validating database security..."

# Check for secure authentication method
compose_files=(docker-compose.*.yml)
for compose_file in "${compose_files[@]}"; do
    if [ -f "$compose_file" ]; then
        if grep -q "scram-sha-256" "$compose_file"; then
            print_result 0 "Database uses secure authentication (scram-sha-256)"
        else
            print_result 1 "Database authentication method not secure"
        fi
    fi
done

# Check for proper network isolation
echo "Validating network security..."

for compose_file in "${compose_files[@]}"; do
    if [ -f "$compose_file" ]; then
        # Check that services use custom networks (not default)
        if grep -q "networks:" "$compose_file" && ! grep -q "bridge" "$compose_file"; then
            print_result 0 "Services use custom networks"
        else
            print_warning "Consider using custom networks for better isolation"
        fi
        
        # Check for unnecessary port exposures
        exposed_ports=$(grep -c "ports:" "$compose_file" 2>/dev/null || echo 0)
        if [ "$exposed_ports" -le 3 ]; then
            print_result 0 "Minimal port exposure ($exposed_ports services)"
        else
            print_warning "Many ports exposed ($exposed_ports services) - review necessity"
        fi
    fi
done

# Check file permissions
echo "Validating file permissions..."

# Check that scripts are executable but not world-writable
script_files=(docker/scripts/*.sh)
insecure_permissions=0

for script in "${script_files[@]}"; do
    if [ -f "$script" ]; then
        perms=$(stat -c "%a" "$script" 2>/dev/null || echo "000")
        # Check if world-writable (last digit >= 2)
        if [ "${perms: -1}" -ge 2 ]; then
            print_result 1 "Script $script has insecure permissions ($perms)"
            insecure_permissions=1
        fi
    fi
done

if [ $insecure_permissions -eq 0 ]; then
    print_result 0 "Script file permissions secure"
fi

# Check for secrets in git
echo "Validating secrets management..."

# Check .gitignore for sensitive files
if [ -f ".gitignore" ]; then
    sensitive_patterns=(".env" "*.key" "*.crt" "secrets")
    gitignore_secure=1
    
    for pattern in "${sensitive_patterns[@]}"; do
        if grep -q "$pattern" .gitignore; then
            continue
        else
            print_result 1 "Sensitive pattern '$pattern' not in .gitignore"
            gitignore_secure=0
        fi
    done
    
    if [ $gitignore_secure -eq 1 ]; then
        print_result 0 "Sensitive files properly ignored by git"
    fi
else
    print_result 1 ".gitignore file missing"
fi

# Check Docker security best practices
echo "Validating Docker security..."

for compose_file in "${compose_files[@]}"; do
    if [ -f "$compose_file" ]; then
        # Check for resource limits
        if grep -q "limits:" "$compose_file"; then
            print_result 0 "Resource limits configured"
        else
            print_result 1 "Resource limits not configured"
        fi
        
        # Check for health checks
        if grep -q "healthcheck:" "$compose_file"; then
            print_result 0 "Health checks configured"
        else
            print_result 1 "Health checks not configured"
        fi
        
        # Check for restart policies
        if grep -q "restart:" "$compose_file"; then
            print_result 0 "Restart policies configured"
        else
            print_result 1 "Restart policies not configured"
        fi
    fi
done

# Check application security endpoints
echo "Validating application security endpoints..."

API_HOST=${API_HOST:-localhost}
API_PORT=${API_PORT:-8000}

# Test if security headers are implemented
if timeout 5 curl -I "http://$API_HOST:$API_PORT/api/v1/registry/health" 2>/dev/null | grep -i "x-"; then
    print_result 0 "Security headers detected"
else
    print_warning "Security headers not detected"
fi

# Final status
echo
if [ $SECURITY_STATUS -eq 0 ]; then
    echo -e "${GREEN}🎉 Security validation PASSED${NC}"
    echo "Security configuration meets requirements"
    exit 0
else
    echo -e "${RED}💥 Security validation FAILED${NC}"
    echo "Security issues detected that must be addressed"
    exit 1
fi