#!/bin/bash

# EMUSES Deployment Health Check Script
# Validates that all services are healthy and responding correctly

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
API_HOST=${API_HOST:-localhost}
API_PORT=${API_PORT:-8000}
POSTGRES_HOST=${POSTGRES_HOST:-localhost}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}
NGINX_HOST=${NGINX_HOST:-localhost}
NGINX_PORT=${NGINX_PORT:-80}

# Health check timeout
TIMEOUT=${HEALTH_CHECK_TIMEOUT:-30}

echo "🏥 EMUSES Deployment Health Check"
echo "================================="

# Track overall health status
OVERALL_STATUS=0

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        OVERALL_STATUS=1
    fi
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check API Health Endpoint
echo
echo "Checking API Health..."
if timeout $TIMEOUT curl -f -s "http://${API_HOST}:${API_PORT}/api/v1/registry/health" > /dev/null; then
    print_status 0 "API health endpoint responding"
    
    # Check detailed health if available
    if HEALTH_RESPONSE=$(timeout $TIMEOUT curl -s "http://${API_HOST}:${API_PORT}/api/v1/registry/health/detailed" 2>/dev/null); then
        if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
            print_status 0 "API detailed health check passed"
        else
            print_status 1 "API detailed health check failed"
        fi
    else
        print_warning "Detailed health endpoint not available"
    fi
else
    print_status 1 "API health endpoint not responding"
fi

# Check Database Connectivity
echo
echo "Checking Database Connectivity..."
if command -v pg_isready >/dev/null 2>&1; then
    if pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U emuses_user >/dev/null 2>&1; then
        print_status 0 "PostgreSQL database accessible"
    else
        print_status 1 "PostgreSQL database not accessible"
    fi
else
    # Fallback to basic network connectivity check
    if timeout $TIMEOUT nc -z "$POSTGRES_HOST" "$POSTGRES_PORT" 2>/dev/null; then
        print_status 0 "PostgreSQL port accessible"
    else
        print_status 1 "PostgreSQL port not accessible"
    fi
fi

# Check Redis Connectivity
echo
echo "Checking Redis Connectivity..."
if command -v redis-cli >/dev/null 2>&1; then
    if timeout $TIMEOUT redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping | grep -q "PONG"; then
        print_status 0 "Redis server responding"
    else
        print_status 1 "Redis server not responding"
    fi
else
    # Fallback to basic network connectivity check
    if timeout $TIMEOUT nc -z "$REDIS_HOST" "$REDIS_PORT" 2>/dev/null; then
        print_status 0 "Redis port accessible"
    else
        print_status 1 "Redis port not accessible"
    fi
fi

# Check Nginx/Load Balancer
echo
echo "Checking Web Server..."
if timeout $TIMEOUT curl -f -s "http://${NGINX_HOST}:${NGINX_PORT}/api/v1/registry/health" > /dev/null; then
    print_status 0 "Web server proxying requests correctly"
else
    print_status 1 "Web server not responding or not proxying correctly"
fi

# Check Model Registry Specific Health
echo
echo "Checking Model Registry Health..."
if timeout $TIMEOUT curl -f -s "http://${API_HOST}:${API_PORT}/api/v1/registry/ready" > /dev/null; then
    print_status 0 "Model registry ready endpoint responding"
else
    print_status 1 "Model registry ready endpoint not responding"
fi

if timeout $TIMEOUT curl -f -s "http://${API_HOST}:${API_PORT}/api/v1/registry/live" > /dev/null; then
    print_status 0 "Model registry liveness endpoint responding"
else
    print_status 1 "Model registry liveness endpoint not responding"
fi

# Check Service Discovery Integration
echo
echo "Checking Service Discovery..."
if SERVICE_DISCOVERY=$(timeout $TIMEOUT curl -s "http://${API_HOST}:${API_PORT}/api/v1/registry/service-discovery" 2>/dev/null); then
    if echo "$SERVICE_DISCOVERY" | grep -q "healthy"; then
        print_status 0 "Service discovery integration healthy"
    else
        print_status 1 "Service discovery integration unhealthy"
    fi
else
    print_warning "Service discovery endpoint not available"
fi

# Check Storage Health
echo
echo "Checking Storage Health..."
if STORAGE_INFO=$(timeout $TIMEOUT curl -s "http://${API_HOST}:${API_PORT}/api/v1/models/storage" 2>/dev/null); then
    if echo "$STORAGE_INFO" | grep -q "available"; then
        print_status 0 "Storage system accessible"
    else
        print_status 1 "Storage system issues detected"
    fi
else
    print_warning "Storage endpoint not available"
fi

# Final Status Report
echo
echo "================================="
if [ $OVERALL_STATUS -eq 0 ]; then
    echo -e "${GREEN}🎉 All health checks PASSED${NC}"
    echo "Deployment is healthy and ready to serve requests"
    exit 0
else
    echo -e "${RED}💥 Some health checks FAILED${NC}"
    echo "Deployment has issues that need attention"
    exit 1
fi