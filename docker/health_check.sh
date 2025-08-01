#!/bin/bash
set -e

# Health check script for EMUSES API service
# This script is called by Docker's HEALTHCHECK directive

# Default service URL
SERVICE_URL="http://localhost:${EMUSES_SERVICE_PORT:-8000}"

# Check if the health endpoint responds
if curl -f -s "${SERVICE_URL}/health" > /dev/null 2>&1; then
    echo "Health check passed"
    exit 0
else
    echo "Health check failed - service not responding"
    exit 1
fi