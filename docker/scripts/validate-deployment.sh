#!/bin/bash

# EMUSES Deployment Validation Script
# Comprehensive validation orchestrator for deployment verification

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALIDATION_TIMEOUT=${VALIDATION_TIMEOUT:-300}  # 5 minutes default
ENVIRONMENT=${ENVIRONMENT:-production}

# Validation flags
RUN_HEALTH_CHECK=${RUN_HEALTH_CHECK:-true}
RUN_CONNECTIVITY_TEST=${RUN_CONNECTIVITY_TEST:-true}
RUN_SECURITY_VALIDATION=${RUN_SECURITY_VALIDATION:-true}
RUN_PERFORMANCE_VALIDATION=${RUN_PERFORMANCE_VALIDATION:-true}
RUN_BACKUP_VALIDATION=${RUN_BACKUP_VALIDATION:-true}
RUN_MONITORING_VALIDATION=${RUN_MONITORING_VALIDATION:-true}

echo -e "${CYAN}🚀 EMUSES Deployment Validation${NC}"
echo -e "${CYAN}Environment: $ENVIRONMENT${NC}"
echo "================================="

# Track overall validation status
OVERALL_STATUS=0
VALIDATION_RESULTS=()

# Function to print section header
print_section() {
    echo
    echo -e "${BLUE}$1${NC}"
    echo "$(printf '=%.0s' $(seq 1 ${#1}))"
}

# Function to run validation step
run_validation() {
    local script_name=$1
    local description=$2
    local required=${3:-true}
    
    echo
    echo -e "${YELLOW}Running: $description${NC}"
    
    if [ -f "$SCRIPT_DIR/$script_name" ]; then
        if timeout $VALIDATION_TIMEOUT "$SCRIPT_DIR/$script_name"; then
            echo -e "${GREEN}✅ $description: PASSED${NC}"
            VALIDATION_RESULTS+=("✅ $description")
            return 0
        else
            echo -e "${RED}❌ $description: FAILED${NC}"
            VALIDATION_RESULTS+=("❌ $description")
            if [ "$required" = "true" ]; then
                OVERALL_STATUS=1
            fi
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️  $description: Script not found ($script_name)${NC}"
        VALIDATION_RESULTS+=("⚠️  $description (script not found)")
        if [ "$required" = "true" ]; then
            OVERALL_STATUS=1
        fi
        return 1
    fi
}

# Function to validate environment-specific configurations
validate_environment_config() {
    local env=$1
    
    print_section "Environment Configuration Validation ($env)"
    
    # Check if environment-specific docker-compose file exists
    case $env in
        production)
            if [ -f "docker-compose.production.yml" ]; then
                echo -e "${GREEN}✅ Production docker-compose configuration found${NC}"
            else
                echo -e "${RED}❌ Production docker-compose configuration missing${NC}"
                OVERALL_STATUS=1
            fi
            ;;
        staging)
            if [ -f "docker-compose.staging.yml" ]; then
                echo -e "${GREEN}✅ Staging docker-compose configuration found${NC}"
            else
                echo -e "${RED}❌ Staging docker-compose configuration missing${NC}"
                OVERALL_STATUS=1
            fi
            ;;
        development)
            if [ -f "docker-compose.yml" ]; then
                echo -e "${GREEN}✅ Development docker-compose configuration found${NC}"
            else
                echo -e "${RED}❌ Development docker-compose configuration missing${NC}"
                OVERALL_STATUS=1
            fi
            ;;
    esac
    
    # Check environment template exists
    if [ -f "docker/environments/.env.$env.template" ]; then
        echo -e "${GREEN}✅ Environment template found for $env${NC}"
    else
        echo -e "${RED}❌ Environment template missing for $env${NC}"
        OVERALL_STATUS=1
    fi
    
    # Validate environment variables if .env file exists
    if [ -f ".env.$env" ]; then
        echo -e "${GREEN}✅ Environment file found for $env${NC}"
        
        # Check critical environment variables
        local required_vars=("POSTGRES_PASSWORD" "JWT_SECRET" "EMUSES_DEPLOYMENT_MODE")
        for var in "${required_vars[@]}"; do
            if grep -q "^$var=" ".env.$env" 2>/dev/null; then
                echo -e "${GREEN}✅ Required variable $var is set${NC}"
            else
                echo -e "${RED}❌ Required variable $var is missing${NC}"
                OVERALL_STATUS=1
            fi
        done
    else
        echo -e "${YELLOW}⚠️  Environment file .env.$env not found (using defaults)${NC}"
    fi
}

# Function to check docker-compose configuration
validate_docker_compose() {
    print_section "Docker Compose Configuration Validation"
    
    local compose_file=""
    case $ENVIRONMENT in
        production) compose_file="docker-compose.production.yml" ;;
        staging) compose_file="docker-compose.staging.yml" ;;
        *) compose_file="docker-compose.yml" ;;
    esac
    
    if [ -f "$compose_file" ]; then
        echo -e "${GREEN}✅ Using docker-compose file: $compose_file${NC}"
        
        # Validate docker-compose syntax
        if docker-compose -f "$compose_file" config >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Docker-compose configuration syntax is valid${NC}"
        else
            echo -e "${RED}❌ Docker-compose configuration syntax is invalid${NC}"
            OVERALL_STATUS=1
        fi
    else
        echo -e "${RED}❌ Docker-compose file not found: $compose_file${NC}"
        OVERALL_STATUS=1
    fi
}

# Main validation sequence
print_section "Pre-Validation Checks"

# Validate environment configuration
validate_environment_config "$ENVIRONMENT"

# Validate docker-compose configuration
validate_docker_compose

# Core service validation
if [ "$RUN_HEALTH_CHECK" = "true" ]; then
    run_validation "health-check.sh" "Health Check Validation" true
fi

if [ "$RUN_CONNECTIVITY_TEST" = "true" ]; then
    run_validation "connectivity-test.sh" "Connectivity Test Validation" true
fi

# Security validation
if [ "$RUN_SECURITY_VALIDATION" = "true" ]; then
    run_validation "validate-security.sh" "Security Configuration Validation" true
fi

# Performance validation
if [ "$RUN_PERFORMANCE_VALIDATION" = "true" ]; then
    run_validation "validate-performance.sh" "Performance Baseline Validation" false
fi

# Backup validation
if [ "$RUN_BACKUP_VALIDATION" = "true" ]; then
    run_validation "validate-backup.sh" "Backup System Validation" false
fi

# Monitoring validation
if [ "$RUN_MONITORING_VALIDATION" = "true" ]; then
    run_validation "validate-monitoring.sh" "Monitoring System Validation" false
fi

# Final results summary
print_section "Validation Results Summary"

echo "Validation Results:"
for result in "${VALIDATION_RESULTS[@]}"; do
    echo "  $result"
done

echo
echo "Environment: $ENVIRONMENT"
echo "Total Validations: ${#VALIDATION_RESULTS[@]}"

if [ $OVERALL_STATUS -eq 0 ]; then
    echo -e "${GREEN}🎉 DEPLOYMENT VALIDATION PASSED${NC}"
    echo -e "${GREEN}All critical validations successful${NC}"
    echo -e "${GREEN}Deployment is ready for $ENVIRONMENT use${NC}"
    exit 0
else
    echo -e "${RED}💥 DEPLOYMENT VALIDATION FAILED${NC}"
    echo -e "${RED}Critical issues detected that must be resolved${NC}"
    echo -e "${RED}Deployment is NOT ready for $ENVIRONMENT use${NC}"
    exit 1
fi