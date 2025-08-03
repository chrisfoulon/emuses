#!/bin/bash
# EMUSES Production Startup Script

set -e

echo "🚀 Starting EMUSES Service..."

# Install EMUSES package
echo "📦 Installing EMUSES package..."
pip install -e .

# Check if we can import EMUSES
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
    exec gunicorn emuses.api.main:create_app \
        --factory \
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