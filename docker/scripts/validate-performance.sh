#!/bin/bash

# EMUSES Performance Baseline Validation Script
# Validates performance configuration and baseline metrics

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}⚡ EMUSES Performance Validation${NC}"
echo "================================="

# Track validation status
PERFORMANCE_STATUS=0

# Performance thresholds
API_RESPONSE_THRESHOLD=${API_RESPONSE_THRESHOLD:-2000}  # 2 seconds
DB_QUERY_THRESHOLD=${DB_QUERY_THRESHOLD:-1000}         # 1 second
MEMORY_THRESHOLD=${MEMORY_THRESHOLD:-80}               # 80% memory usage

# Function to print result
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        PERFORMANCE_STATUS=1
    fi
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Function to measure response time
measure_response_time() {
    local url=$1
    local description=$2
    local threshold=$3
    
    echo "Testing $description response time..."
    
    if command -v curl >/dev/null 2>&1; then
        # Measure response time in milliseconds
        response_time=$(curl -o /dev/null -s -w '%{time_total}' "$url" 2>/dev/null || echo "999")
        response_time_ms=$(echo "$response_time * 1000" | bc 2>/dev/null || echo "999000")
        response_time_ms=${response_time_ms%.*}  # Convert to integer
        
        if [ "$response_time_ms" -lt "$threshold" ]; then
            print_result 0 "$description responds in ${response_time_ms}ms (< ${threshold}ms)"
        else
            print_result 1 "$description responds in ${response_time_ms}ms (> ${threshold}ms)"
        fi
    else
        print_warning "curl not available for response time testing"
    fi
}

# Check Docker resource configurations
echo "Validating resource configurations..."

compose_files=(docker-compose.*.yml)
for compose_file in "${compose_files[@]}"; do
    if [ -f "$compose_file" ]; then
        if grep -q "resources:" "$compose_file"; then
            if grep -A 10 "resources:" "$compose_file" | grep -q "limits:"; then
                print_result 0 "Resource limits configured in $compose_file"
            else
                print_result 1 "Resource limits missing in $compose_file"
            fi
            
            if grep -A 10 "resources:" "$compose_file" | grep -q "reservations:"; then
                print_result 0 "Resource reservations configured in $compose_file"
            else
                print_warning "Resource reservations not configured in $compose_file"
            fi
        else
            print_result 1 "No resource constraints in $compose_file"
        fi
    fi
done

# Check performance-related configurations
echo "Validating performance configurations..."

# Check for Redis caching configuration
if grep -r "redis" docker-compose.*.yml >/dev/null 2>&1; then
    print_result 0 "Redis caching layer configured"
else
    print_result 1 "Redis caching layer not configured"
fi

# Check database connection pooling
if grep -r "pool" emuses/ >/dev/null 2>&1; then
    print_result 0 "Database connection pooling detected"
else
    print_warning "Database connection pooling not detected"
fi

# Check for performance monitoring
if [ -f "docker-compose.observability.yml" ]; then
    print_result 0 "Performance monitoring stack available"
else
    print_result 1 "Performance monitoring stack not configured"
fi

# Test API performance if services are running
echo "Testing API performance..."

API_HOST=${API_HOST:-localhost}
API_PORT=${API_PORT:-8000}

if timeout 5 nc -z "$API_HOST" "$API_PORT" 2>/dev/null; then
    echo "API service is running, testing performance..."
    
    # Test health endpoint response time
    measure_response_time "http://$API_HOST:$API_PORT/api/v1/registry/health" "Health endpoint" $API_RESPONSE_THRESHOLD
    
    # Test model listing endpoint response time if available
    measure_response_time "http://$API_HOST:$API_PORT/api/v1/models/" "Model listing endpoint" $API_RESPONSE_THRESHOLD
    
    # Test concurrent requests if ab (Apache Bench) is available
    if command -v ab >/dev/null 2>&1; then
        echo "Testing concurrent request handling..."
        concurrent_result=$(ab -n 10 -c 2 "http://$API_HOST:$API_PORT/api/v1/registry/health" 2>/dev/null | grep "Requests per second" || echo "0")
        if echo "$concurrent_result" | grep -q "[1-9]"; then
            print_result 0 "API handles concurrent requests"
        else
            print_result 1 "API concurrent request handling poor"
        fi
    else
        print_warning "Apache Bench (ab) not available for concurrent testing"
    fi
else
    print_warning "API service not running - cannot test performance"
fi

# Test database performance if accessible
echo "Testing database performance..."

POSTGRES_HOST=${POSTGRES_HOST:-localhost}
POSTGRES_PORT=${POSTGRES_PORT:-5432}

if timeout 5 nc -z "$POSTGRES_HOST" "$POSTGRES_PORT" 2>/dev/null; then
    if command -v pg_isready >/dev/null 2>&1; then
        # Measure database connection time
        start_time=$(date +%s%N)
        if pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" >/dev/null 2>&1; then
            end_time=$(date +%s%N)
            connection_time=$((($end_time - $start_time) / 1000000))  # Convert to milliseconds
            
            if [ "$connection_time" -lt "$DB_QUERY_THRESHOLD" ]; then
                print_result 0 "Database connection time: ${connection_time}ms"
            else
                print_result 1 "Database connection slow: ${connection_time}ms"
            fi
        else
            print_result 1 "Database connection failed"
        fi
    else
        print_warning "pg_isready not available for database testing"
    fi
else
    print_warning "Database not accessible - cannot test performance"
fi

# Check system resource usage if tools are available
echo "Checking system resource usage..."

if command -v free >/dev/null 2>&1; then
    memory_usage=$(free | grep Mem | awk '{printf "%.0f", ($3/$2) * 100}')
    if [ "$memory_usage" -lt "$MEMORY_THRESHOLD" ]; then
        print_result 0 "Memory usage: ${memory_usage}%"
    else
        print_result 1 "High memory usage: ${memory_usage}%"
    fi
else
    print_warning "Memory usage tools not available"
fi

if command -v df >/dev/null 2>&1; then
    disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$disk_usage" -lt 80 ]; then
        print_result 0 "Disk usage: ${disk_usage}%"
    else
        print_result 1 "High disk usage: ${disk_usage}%"
    fi
else
    print_warning "Disk usage tools not available"
fi

# Check for performance optimization features
echo "Validating performance optimizations..."

# Check for caching implementation
if grep -r "cache" emuses/ >/dev/null 2>&1; then
    print_result 0 "Caching implementation detected"
else
    print_result 1 "No caching implementation found"
fi

# Check for pagination support
if grep -r "limit\|offset\|page" emuses/ >/dev/null 2>&1; then
    print_result 0 "Pagination support detected"
else
    print_result 1 "Pagination support not found"
fi

# Check for compression
if grep -r "gzip\|compression" docker/ >/dev/null 2>&1; then
    print_result 0 "Response compression configured"
else
    print_result 1 "Response compression not configured"
fi

# Final status
echo
if [ $PERFORMANCE_STATUS -eq 0 ]; then
    echo -e "${GREEN}🎉 Performance validation PASSED${NC}"
    echo "Performance configuration meets baseline requirements"
    exit 0
else
    echo -e "${RED}💥 Performance validation FAILED${NC}"
    echo "Performance issues detected that may impact user experience"
    exit 1
fi