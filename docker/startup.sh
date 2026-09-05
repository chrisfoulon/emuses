#!/bin/bash
# EMUSES Production Startup Script

set -e

echo "🚀 Starting EMUSES Service..."

# EMUSES is installed into /opt/venv at *build* time (see the Dockerfile), not here.
#
# This script used to run `pip install -e .` on every container start. It could
# never have worked: by this point the Dockerfile has switched to the non-root
# `emuses` user, and /opt/venv is root-owned -- the Dockerfile's chown covers /app
# only -- so pip died with
#   [Errno 13] Permission denied: '.../__editable___emuses_..._finder.py'
# It was broken a second way too: with no --no-deps it re-resolves emuses's
# unpinned requirements, which backtracks gpy to 1.10.0 and fails to build on 3.11
# (the same trap ci.yml documents). Installing at build time fixes both, and drops
# the requirement that a production container have a package index reachable at
# startup.
echo "🔍 Validating EMUSES installation..."
python -c "import emuses; print('✅ EMUSES imported successfully')"

# Run database migrations if needed
if [ "$EMUSES_DEPLOYMENT_MODE" = "production" ] && [ -n "$DATABASE_URL" ]; then
    echo "🗄️ Running database migrations..."
    # Add migration commands here when implemented
    # alembic upgrade head
fi

# Start the service based on deployment mode
if [ "$EMUSES_DEPLOYMENT_MODE" = "production" ]; then
    echo "🌐 Starting production server with gunicorn..."
    # `--factory` is a uvicorn flag; gunicorn has no such option and exits 2 with
    # "unrecognized arguments: --factory". gunicorn spells a factory by putting
    # call parentheses in the APP_MODULE instead, so the quotes here are load-bearing.
    # The production path had never been run, so this had never surfaced.
    exec gunicorn "emuses.api.main:create_app()" \
        --bind $EMUSES_SERVICE_HOST:$EMUSES_SERVICE_PORT \
        --workers 4 \
        --worker-class uvicorn.workers.UvicornWorker \
        --access-logfile - \
        --error-logfile - \
        --log-level info
else
    echo "🔧 Starting development server with uvicorn..."
    exec uvicorn emuses.api.main:create_app \
        --factory \
        --host $EMUSES_SERVICE_HOST \
        --port $EMUSES_SERVICE_PORT \
        --log-level info
fi