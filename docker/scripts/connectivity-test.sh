#!/bin/bash

# EMUSES Deployment Connectivity Test Script
# Tests network connectivity between services in the deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration - can be overridden by environment variables
API_HOST=${API_HOST:-api}
API_PORT=${API_PORT:-8000}
POSTGRES_HOST=${POSTGRES_HOST:-postgres}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
REDIS_HOST=${REDIS_HOST:-redis}
REDIS_PORT=${REDIS_PORT:-6379}
NGINX_HOST=${NGINX_HOST:-nginx}
NGINX_HTTP_PORT=${NGINX_HTTP_PORT:-80}
NGINX_HTTPS_PORT=${NGINX_HTTPS_PORT:-443}

# Test timeout
TIMEOUT=${CONNECTIVITY_TIMEOUT:-10}

echo -e "${BLUE}🔗 EMUSES Connectivity Test${NC}"
echo "============================"

# Track overall connectivity status
CONNECTIVITY_STATUS=0

# Function to print test result
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        CONNECTIVITY_STATUS=1
    fi
}

# Function to print info
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Function to test TCP connectivity
test_tcp_connection() {
    local host=$1
    local port=$2
    local service_name=$3
    
    print_info "Testing TCP connection to $service_name ($host:$port)..."
    
    if timeout $TIMEOUT nc -z "$host" "$port" 2>/dev/null; then
        print_result 0 "$service_name TCP connection successful"
        return 0
    else
        print_result 1 "$service_name TCP connection failed"
        return 1
    fi
}

# Function to test HTTP connectivity
test_http_connection() {
    local url=$1
    local service_name=$2
    
    print_info "Testing HTTP connection to $service_name ($url)..."
    
    if timeout $TIMEOUT curl -f -s "$url" > /dev/null 2>&1; then
        print_result 0 "$service_name HTTP connection successful"
        return 0
    else
        print_result 1 "$service_name HTTP connection failed"
        return 1
    fi
}

# Function to test PostgreSQL connectivity
test_postgres_connection() {
    local host=$1
    local port=$2
    
    print_info "Testing PostgreSQL connection ($host:$port)..."
    
    # First test basic TCP connectivity
    if ! timeout $TIMEOUT nc -z "$host" "$port" 2>/dev/null; then
        print_result 1 "PostgreSQL TCP connection failed"
        return 1
    fi
    
    # Test PostgreSQL-specific connectivity if pg_isready is available
    if command -v pg_isready >/dev/null 2>&1; then
        if timeout $TIMEOUT pg_isready -h "$host" -p "$port" >/dev/null 2>&1; then
            print_result 0 "PostgreSQL service ready"
            return 0
        else
            print_result 1 "PostgreSQL service not ready"
            return 1
        fi
    else
        print_result 0 "PostgreSQL TCP connection successful (pg_isready not available)"
        return 0
    fi
}

# Function to test Redis connectivity
test_redis_connection() {
    local host=$1
    local port=$2
    
    print_info "Testing Redis connection ($host:$port)..."
    
    # First test basic TCP connectivity
    if ! timeout $TIMEOUT nc -z "$host" "$port" 2>/dev/null; then
        print_result 1 "Redis TCP connection failed"
        return 1
    fi
    
    # Test Redis-specific connectivity if redis-cli is available
    if command -v redis-cli >/dev/null 2>&1; then
        if timeout $TIMEOUT redis-cli -h "$host" -p "$port" ping 2>/dev/null | grep -q "PONG"; then
            print_result 0 "Redis service responding to ping"
            return 0
        else
            print_result 1 "Redis service not responding to ping"
            return 1
        fi
    else
        print_result 0 "Redis TCP connection successful (redis-cli not available)"
        return 0
    fi
}

echo
echo "Testing Basic Service Connectivity..."
echo "===================================="

# Test API service connectivity
test_tcp_connection "$API_HOST" "$API_PORT" "API Service"

# Test PostgreSQL connectivity
test_postgres_connection "$POSTGRES_HOST" "$POSTGRES_PORT"

# Test Redis connectivity  
test_redis_connection "$REDIS_HOST" "$REDIS_PORT"

# Test Nginx connectivity
test_tcp_connection "$NGINX_HOST" "$NGINX_HTTP_PORT" "Nginx HTTP"
test_tcp_connection "$NGINX_HOST" "$NGINX_HTTPS_PORT" "Nginx HTTPS"

echo
echo "Testing Service Integration..."
echo "============================="

# Test API through Nginx proxy
if timeout $TIMEOUT nc -z "$NGINX_HOST" "$NGINX_HTTP_PORT" 2>/dev/null; then
    test_http_connection "http://$NGINX_HOST:$NGINX_HTTP_PORT/api/v1/registry/health" "API via Nginx"
else
    print_result 1 "Cannot test API via Nginx - Nginx not accessible"
fi

# Test direct API access
if timeout $TIMEOUT nc -z "$API_HOST" "$API_PORT" 2>/dev/null; then
    test_http_connection "http://$API_HOST:$API_PORT/api/v1/registry/health" "Direct API Access"
else
    print_result 1 "Cannot test direct API access - API not accessible"
fi

echo
echo "Testing Cross-Service Communication..."
echo "====================================="

# Test if API can reach database (through API endpoint)
if timeout $TIMEOUT curl -s "http://$API_HOST:$API_PORT/api/v1/registry/health/detailed" 2>/dev/null | grep -q "database.*healthy"; then
    print_result 0 "API to database communication working"
else
    print_result 1 "API to database communication not working"
fi

# Test if API can reach Redis (through API endpoint if available)
if timeout $TIMEOUT curl -s "http://$API_HOST:$API_PORT/api/v1/registry/health/detailed" 2>/dev/null | grep -q "redis.*healthy"; then
    print_result 0 "API to Redis communication working"
else
    # This might not be implemented yet, so don't fail hard
    echo -e "${YELLOW}⚠️  API to Redis communication status unknown${NC}"
fi

echo
echo "Testing External Dependencies..."
echo "==============================="

# Test internet connectivity (for cloud features)
if timeout $TIMEOUT ping -c 1 8.8.8.8 >/dev/null 2>&1; then
    print_result 0 "Internet connectivity available"
else
    print_result 1 "No internet connectivity"
fi

# Test DNS resolution
if timeout $TIMEOUT nslookup github.com >/dev/null 2>&1; then
    print_result 0 "DNS resolution working"
else
    print_result 1 "DNS resolution not working"
fi

# Final Status Report
echo
echo "============================="
if [ $CONNECTIVITY_STATUS -eq 0 ]; then
    echo -e "${GREEN}🎉 All connectivity tests PASSED${NC}"
    echo "All services can communicate properly"
    exit 0
else
    echo -e "${RED}💥 Some connectivity tests FAILED${NC}"
    echo "Network connectivity issues detected"
    exit 1
fi