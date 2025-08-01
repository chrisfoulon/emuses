#!/bin/bash
set -e

echo "Starting EMUSES API service..."

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
while ! python -c "
import asyncio
import asyncpg
import os

async def check_db():
    try:
        conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
        await conn.close()
        print('PostgreSQL is ready!')
        return True
    except Exception as e:
        print(f'PostgreSQL not ready: {e}')
        return False

result = asyncio.run(check_db())
exit(0 if result else 1)
"; do
    echo "PostgreSQL is unavailable - sleeping"
    sleep 2
done

# Run database migrations
echo "Running database migrations..."
python -c "
import asyncio
from emuses.multi_user_service.database import create_all_tables

async def setup_db():
    await create_all_tables()
    print('Database setup complete!')

asyncio.run(setup_db())
"

# Check if we're in development mode (for additional setup)
if [ "$EMUSES_DEPLOYMENT_MODE" = "development" ]; then
    echo "Development mode detected - additional setup may be performed here"
fi

# Ensure storage directory exists and has correct permissions
mkdir -p /app/storage /app/logs
chmod 755 /app/storage /app/logs

# Start the application with uvicorn
echo "Starting EMUSES API server..."
exec uvicorn emuses.api.main:app \
    --host "${EMUSES_SERVICE_HOST:-0.0.0.0}" \
    --port "${EMUSES_SERVICE_PORT:-8000}" \
    --workers "${EMUSES_MAX_WORKERS:-4}" \
    --access-log \
    --access-log-format '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s' \
    --log-level info