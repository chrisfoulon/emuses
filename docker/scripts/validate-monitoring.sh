#!/bin/bash

# EMUSES Monitoring System Validation Script
# Validates monitoring and observability configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📊 EMUSES Monitoring Validation${NC}"
echo "==============================="

# Track validation status
MONITORING_STATUS=0

# Function to print result
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        MONITORING_STATUS=1
    fi
}

# Check observability docker-compose configuration
echo "Validating monitoring configuration..."

if [ -f "docker-compose.observability.yml" ]; then
    print_result 0 "Observability docker-compose configuration exists"
    
    # Validate observability compose syntax
    if docker-compose -f docker-compose.observability.yml config >/dev/null 2>&1; then
        print_result 0 "Observability docker-compose syntax valid"
    else
        print_result 1 "Observability docker-compose syntax invalid"
    fi
else
    print_result 1 "Observability docker-compose configuration missing"
fi

# Check Prometheus configuration
echo "Validating Prometheus configuration..."

if [ -f "docker/observability/prometheus.yml" ]; then
    print_result 0 "Prometheus configuration exists"
else
    print_result 1 "Prometheus configuration missing"
fi

if [ -f "docker/observability/alerts.yml" ]; then
    print_result 0 "Prometheus alerts configuration exists"
else
    print_result 1 "Prometheus alerts configuration missing"
fi

# Check Grafana configuration
echo "Validating Grafana configuration..."

if [ -d "docker/observability/grafana/dashboards" ]; then
    dashboard_count=$(find docker/observability/grafana/dashboards -name "*.json" | wc -l)
    if [ $dashboard_count -gt 0 ]; then
        print_result 0 "Grafana dashboards configured ($dashboard_count dashboards)"
    else
        print_result 1 "No Grafana dashboards found"
    fi
else
    print_result 1 "Grafana dashboards directory missing"
fi

if [ -d "docker/observability/grafana/datasources" ]; then
    print_result 0 "Grafana datasources configured"
else
    print_result 1 "Grafana datasources configuration missing"
fi

# Check metrics integration
echo "Validating metrics integration..."

if grep -r "metrics" emuses/ >/dev/null 2>&1; then
    print_result 0 "Application metrics integration detected"
else
    print_result 1 "No application metrics integration found"
fi

# Test monitoring endpoints if services are running
echo "Testing monitoring endpoints..."

PROMETHEUS_PORT=${PROMETHEUS_PORT:-9090}
GRAFANA_PORT=${GRAFANA_PORT:-3000}

if timeout 5 nc -z localhost $PROMETHEUS_PORT 2>/dev/null; then
    if timeout 5 curl -s "http://localhost:$PROMETHEUS_PORT/api/v1/query?query=up" >/dev/null; then
        print_result 0 "Prometheus service responding"
    else
        print_result 1 "Prometheus service not responding correctly"
    fi
else
    echo -e "${YELLOW}⚠️  Prometheus not running (port $PROMETHEUS_PORT)${NC}"
fi

if timeout 5 nc -z localhost $GRAFANA_PORT 2>/dev/null; then
    if timeout 5 curl -s "http://localhost:$GRAFANA_PORT/api/health" >/dev/null; then
        print_result 0 "Grafana service responding"
    else
        print_result 1 "Grafana service not responding correctly"
    fi
else
    echo -e "${YELLOW}⚠️  Grafana not running (port $GRAFANA_PORT)${NC}"
fi

# Final status
echo
if [ $MONITORING_STATUS -eq 0 ]; then
    echo -e "${GREEN}🎉 Monitoring validation PASSED${NC}"
    exit 0
else
    echo -e "${RED}💥 Monitoring validation FAILED${NC}"
    exit 1
fi