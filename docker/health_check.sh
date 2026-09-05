#!/bin/bash
# EMUSES Health Check Script

set -e

# Health check endpoint.
#
# /api/health, not /health: create_app() mounts the API under /api, so the bare
# path 404s. Measured in the built image -- /health returned 404 on every probe
# and /api/health returned 200 {"status":"healthy",...}. The container would have
# reported `unhealthy` forever, which in a compose or orchestrator setup means a
# restart loop rather than a visible error.
HEALTH_URL="http://localhost:${EMUSES_SERVICE_PORT:-8000}/api/health"

# Attempt health check with timeout
if curl -f -s --max-time 5 "$HEALTH_URL" > /dev/null 2>&1; then
    echo "✅ Health check passed"
    exit 0
else
    echo "❌ Health check failed"
    exit 1
fi