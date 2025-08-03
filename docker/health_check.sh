#!/bin/bash
# EMUSES Health Check Script

set -e

# Health check endpoint
HEALTH_URL="http://localhost:${EMUSES_SERVICE_PORT:-8000}/health"

# Attempt health check with timeout
if curl -f -s --max-time 5 "$HEALTH_URL" > /dev/null 2>&1; then
    echo "✅ Health check passed"
    exit 0
else
    echo "❌ Health check failed"
    exit 1
fi