# EMUSES Multi-User Service - Testing Commands

Copy these commands one by one and paste them into your terminal. 
Each section has clear separators and expected results.

## INITIAL SETUP - Configure for Your System

**Choose your platform and set variables accordingly:**

### For Linux/WSL:
```bash
export PROJECT_DIR="/home/chrisfoulon/neuro_apps/emuses"
export PYTHON_CMD="python"
export POSTGRES_SERVICE="postgresql"
export POSTGRES_USER="postgres"
export POSTGRES_SUDO="sudo -u postgres"
```

### For Windows (PowerShell):
```powershell
$env:PROJECT_DIR = "C:\path\to\your\emuses\project"
$env:PYTHON_CMD = "python"
$env:POSTGRES_SERVICE = "postgresql-x64-14"  # Adjust version as needed
$env:POSTGRES_USER = "postgres"
# No sudo equivalent needed on Windows
```

### For macOS:
```bash
export PROJECT_DIR="/Users/yourusername/path/to/emuses"
export PYTHON_CMD="python3"
export POSTGRES_SERVICE="postgresql"
export POSTGRES_USER="postgres"
export POSTGRES_SUDO="sudo -u postgres"
```

### Universal Settings (all platforms):
```bash
export EMUSES_TEST_DB_NAME="emuses_test"
export EMUSES_TEST_USER="emuses_user"
export EMUSES_TEST_PASS="emuses_pass"
export EMUSES_API_PORT="8000"
export EMUSES_JWT_SECRET="your-super-secret-jwt-key-for-testing-$(date +%s)"
```

---

## PHASE 1: Environment Setup and Basic Functionality

### 1.1 Navigate to project directory and verify setup
```bash
cd "$PROJECT_DIR"
pwd
git status
git branch
```
**Expected**: Should be in your EMUSES project directory on `feat/multi-user-service` branch

### 1.2 Check Python environment
```bash
python --version
pip list | grep -E '(fastapi|typer|rich|sqlalchemy|alembic|pytest)'
```
**Expected**: Python 3.11+, should see key packages listed
**If missing**: `pip install fastapi typer rich sqlalchemy alembic pytest asyncpg psycopg2-binary`

### 1.3 Test basic CLI functionality
```bash
python -m emuses --help
```
**Expected ✅**: Should show main CLI help with various commands
**If broken ❌**: ImportError means missing dependencies, ModuleNotFoundError means wrong directory

### 1.4 Test admin commands are available
```bash
python -m emuses admin --help
```
**Expected ✅**: Should show admin subcommands: add-user, list-users, set-quota, system-status, cancel-job, help
**If broken ❌**: 'admin' not found means CLI integration failed

### 1.5 Test comprehensive admin help
```bash
python -m emuses admin help
```
**Expected ✅**: Should show rich formatted help with authentication info, workflows, troubleshooting
**If broken ❌**: Check Rich library installation

---

## PHASE 2: Local Mode Testing (No Authentication)

### 2.1 Test system status in LOCAL mode
```bash
python -m emuses admin system-status
```
**Expected ✅**: Should show system status without requiring authentication
**Expected ❌**: Connection errors are normal (API service isn't running yet)

### 2.2 Test system status with detailed info
```bash
python -m emuses admin system-status --detailed
```
**Expected ✅**: Should attempt to fetch detailed system info
**Expected ❌**: Connection errors are expected without running API service

---

## PHASE 3: Database Setup and Migrations

### 3.1 Choose your database option

**OPTION A: SQLite (easier for testing)**
```bash
export EMUSES_DATABASE_URL="sqlite:///./emuses_test.db"
```

**OPTION B: PostgreSQL (production-like)**

*First install and start PostgreSQL:*
```bash
# Ubuntu/Debian:
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql

# macOS:
brew install postgresql
brew services start postgresql
```

*Create database and user:*
```bash
sudo -u postgres psql
```
*Then in PostgreSQL prompt:*
```sql
CREATE DATABASE emuses_test;
CREATE USER emuses_user WITH PASSWORD 'emuses_pass';
GRANT ALL PRIVILEGES ON DATABASE emuses_test TO emuses_user;
\q
```

*Set database URL:*
```bash
export EMUSES_DATABASE_URL="postgresql://emuses_user:emuses_pass@localhost/emuses_test"
```

### 3.2 Check Alembic configuration
```bash
ls -la alembic/
cat alembic.ini | grep sqlalchemy.url
```
**Expected ✅**: Should see alembic.ini and migrations directory

### 3.3 Run database migrations
```bash
alembic upgrade head
```
**Expected ✅**: Should create all tables (users, workspaces, datasets, training_jobs)
**If broken ❌**: Database connection error means check DATABASE_URL and database is running

### 3.4 Verify migration status
```bash
alembic current
alembic history
```
**Expected ✅**: Should show current migration and history

---

## PHASE 4: API Service Startup

**⚠️ IMPORTANT: Open a new terminal (Terminal #2) for the API service**

### 4.1 Start API service in MULTI_USER mode (Terminal #2)
```bash
cd /home/chrisfoulon/neuro_apps/emuses
export EMUSES_DEPLOYMENT_MODE=multi_user
export EMUSES_DATABASE_URL="sqlite:///./emuses_test.db"
export EMUSES_JWT_SECRET="your-super-secret-jwt-key-for-testing"
python -m uvicorn emuses.api.main:app --reload --host 0.0.0.0 --port 8000
```
**Expected ✅**: Should start without errors and show 'Application startup complete'
**If broken ❌**: Import errors = missing FastAPI deps, database errors = verify migrations ran

### 4.2 Test API health (back in Terminal #1)
```bash
curl http://localhost:8000/health
```
**Expected ✅**: Should return `{"status":"healthy"}`

### 4.3 Test API documentation
```bash
echo "Open browser to: http://localhost:8000/docs"
```
**Expected ✅**: Should show interactive API documentation with all endpoints including /admin/*

---

## PHASE 5: Multi-User Mode Admin Testing

### 5.1 Test system status with running API
```bash
export EMUSES_DEPLOYMENT_MODE=multi_user
python -m emuses admin system-status
```
**Expected ✅**: Should show system status with database and API components healthy
**If broken ❌**: Connection refused means API service not running on port 8000

### 5.2 Test detailed system status
```bash
python -m emuses admin system-status --detailed
```
**Expected ✅**: Should show comprehensive system metrics, job queues, health checks

### 5.3 Test user listing (should be empty initially)
```bash
python -m emuses admin list-users
```
**Expected ✅**: Should show 'No users found' or empty user table
**Expected ❌**: 401/403 errors are normal (no superuser yet)

---

## PHASE 6: Admin User Creation and Authentication

### 6.1 Create first admin user (superuser)

*Create Python script for superuser creation:*
```bash
cat > create_admin_user.py << 'EOF'
import asyncio
from emuses.multi_user_service.models import User
from emuses.multi_user_service.database import get_async_session
from emuses.multi_user_service.auth import UserManager, get_user_db
from fastapi_users.exceptions import UserAlreadyExists

async def create_superuser():
    session = await anext(get_async_session())
    user_db = await anext(get_user_db(session))
    user_manager = UserManager(user_db)
    
    try:
        user = await user_manager.create(
            {
                "email": "admin@emuses.local",
                "password": "admin123",
                "is_superuser": True,
                "is_verified": True,
                "organization": "EMUSES Admin"
            }
        )
        print(f"Superuser created: {user.email}")
    except UserAlreadyExists:
        print("Superuser already exists")
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(create_superuser())
EOF
```

*Run the script:*
```bash
python create_admin_user.py
```
**Expected ✅**: Should create admin@emuses.local superuser
**If broken ❌**: Check database connection and models

### 6.2 Get admin JWT token
```bash
curl -X POST "http://localhost:8000/auth/jwt/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin@emuses.local&password=admin123"
```
**Expected ✅**: Should return: `{"access_token":"eyJ...","token_type":"bearer"}`
**If broken ❌**: 400/401 means check credentials or user creation

### 6.3 Export admin token for CLI use
```bash
# Copy the access_token from above response and paste here:
export EMUSES_ADMIN_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```
**Replace with your actual token**

### 6.4 Test authenticated admin commands
```bash
python -m emuses admin list-users
```
**Expected ✅**: Should show the admin user you created
**If broken ❌**: Still 401/403 means token is invalid or expired

---

## PHASE 7: User Management Testing

### 7.1 Create regular users
```bash
python -m emuses admin add-user researcher@university.edu -p ResearchPass123 -o "University Research Lab"
```
**Expected ✅**: Should create user with success message

```bash
python -m emuses admin add-user student@college.edu -p StudentPass456 -o "Computer Science Dept" --inactive
```
**Expected ✅**: Should create inactive user

```bash
python -m emuses admin add-user postdoc@lab.edu -p PostdocPass789 -o "Neuroscience Lab"
```
**Expected ✅**: Should create active user

### 7.2 List all users
```bash
python -m emuses admin list-users
```
**Expected ✅**: Should show table with admin + 3 new users, with status indicators

### 7.3 Test pagination
```bash
python -m emuses admin list-users --limit 2
```
**Expected ✅**: Should show only 2 users

```bash
python -m emuses admin list-users --skip 2 --limit 5
```
**Expected ✅**: Should skip first 2 users, show remaining

---

## PHASE 8: Quota Management Testing

### 8.1 Set storage quotas
```bash
python -m emuses admin set-quota researcher@university.edu storage_gb 100
```
**Expected ✅**: Should show success message with quota update

```bash
python -m emuses admin set-quota student@college.edu storage_gb 25
```
**Expected ✅**: Should set lower quota for student

### 8.2 Set concurrent job limits
```bash
python -m emuses admin set-quota researcher@university.edu concurrent_jobs 5
```
**Expected ✅**: Should allow more concurrent jobs for researcher

```bash
python -m emuses admin set-quota student@college.edu concurrent_jobs 2
```
**Expected ✅**: Should limit student to 2 concurrent jobs

### 8.3 Set compute hour limits
```bash
python -m emuses admin set-quota researcher@university.edu compute_hours 1000
python -m emuses admin set-quota student@college.edu compute_hours 200
```
**Expected ✅**: Both should show success messages

### 8.4 Test invalid quota types
```bash
python -m emuses admin set-quota researcher@university.edu invalid_quota 50
```
**Expected ✅**: Should show error with valid quota types listed

---

## PHASE 9: Regular User Workflow Testing

### 9.1 Test user login
```bash
curl -X POST "http://localhost:8000/auth/jwt/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=researcher@university.edu&password=ResearchPass123"
```
**Expected ✅**: Should return access token for regular user

### 9.2 Export user token and test user endpoints
```bash
# Use token from above:
export EMUSES_USER_TOKEN="eyJ..."

# Test user workspace access:
curl -H "Authorization: Bearer $EMUSES_USER_TOKEN" http://localhost:8000/workspaces/
```
**Expected ✅**: Should return empty array `[]` (no workspaces yet)

### 9.3 Create user workspace
```bash
curl -X POST "http://localhost:8000/workspaces/" \
     -H "Authorization: Bearer $EMUSES_USER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name":"My Research Project","description":"Testing workspace creation"}'
```
**Expected ✅**: Should create workspace and return workspace object

### 9.4 List user workspaces
```bash
curl -H "Authorization: Bearer $EMUSES_USER_TOKEN" http://localhost:8000/workspaces/
```
**Expected ✅**: Should show the created workspace

---

## PHASE 10: Job Submission and Management Testing

### 10.1 Submit a test job
```bash
curl -X POST "http://localhost:8000/tasks/" \
     -H "Authorization: Bearer $EMUSES_USER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "config": {
         "pipeline_type": "full",
         "input_path": "/tmp/test_input",
         "output_path": "/tmp/test_output"
       }
     }'
```
**Expected ✅**: Should submit job and return task ID
**If broken ❌**: Check background task system integration

### 10.2 List user tasks
```bash
curl -H "Authorization: Bearer $EMUSES_USER_TOKEN" http://localhost:8000/tasks/
```
**Expected ✅**: Should show submitted task with status

### 10.3 Check system status shows running jobs
```bash
python -m emuses admin system-status --detailed
```
**Expected ✅**: Should show job in system metrics and queues

### 10.4 Test job cancellation
```bash
# Get job ID from step 10.1 output, then:
TASK_ID="your-task-id-here"
python -m emuses admin cancel-job $TASK_ID
```
**Expected ✅**: Should prompt for confirmation and cancel job

---

## PHASE 11: Production Mode Testing

**⚠️ IMPORTANT: Need to restart API service**

### 11.1 Stop and restart API service in PRODUCTION mode

*In Terminal #2 (API server): Press Ctrl+C to stop, then:*
```bash
export EMUSES_DEPLOYMENT_MODE=production
export EMUSES_DATABASE_URL="sqlite:///./emuses_test.db"
export EMUSES_JWT_SECRET="your-super-secret-jwt-key-for-testing"
python -m uvicorn emuses.api.main:app --reload --host 0.0.0.0 --port 8000
```
**Expected ✅**: Should start without errors

### 11.2 Test that admin commands require authentication
```bash
unset EMUSES_ADMIN_TOKEN
python -m emuses admin list-users
```
**Expected ✅**: Should show authentication error

### 11.3 Test with authentication
```bash
export EMUSES_ADMIN_TOKEN="eyJ..."  # Use your admin token from Phase 6
python -m emuses admin list-users
```
**Expected ✅**: Should work with proper authentication

---

## PHASE 12: CLI Integration Testing

### 12.1 Test CLI with service URL parameter
```bash
python -m emuses admin system-status --service-url http://localhost:8000
```
**Expected ✅**: Should connect to specific service URL

### 12.2 Test CLI with token parameter
```bash
python -m emuses admin list-users --token "$EMUSES_ADMIN_TOKEN" --service-url http://localhost:8000
```
**Expected ✅**: Should work with explicit token parameter

### 12.3 Test environment variable detection
```bash
export EMUSES_SERVICE_URL="http://localhost:8000"
python -m emuses admin system-status
```
**Expected ✅**: Should use environment variable for service URL

---

## PHASE 13: Error Handling and Edge Cases

### 13.1 Test with invalid token
```bash
export EMUSES_ADMIN_TOKEN="invalid-token"
python -m emuses admin list-users
```
**Expected ✅**: Should show clear authentication error message

### 13.2 Test connection failures
```bash
# Stop API service in Terminal #2 (Ctrl+C), then:
export EMUSES_ADMIN_TOKEN="valid-token"
python -m emuses admin system-status
```
**Expected ✅**: Should show connection error with helpful message

### 13.3 Test invalid user creation
```bash
# Restart API service first, then:
python -m emuses admin add-user invalid-email -p short
```
**Expected ✅**: Should show validation errors

### 13.4 Test duplicate user creation
```bash
python -m emuses admin add-user researcher@university.edu -p AnotherPass123
```
**Expected ✅**: Should show user already exists error

---

## PHASE 14: Documentation and Help Testing

### 14.1 Test command-specific help
```bash
python -m emuses admin add-user --help
```
**Expected ✅**: Should show detailed help with examples and parameter descriptions

```bash
python -m emuses admin set-quota --help
```
**Expected ✅**: Should show quota types and usage examples

### 14.2 Test comprehensive help command
```bash
python -m emuses admin help
```
**Expected ✅**: Should show rich formatted help with command overview, authentication requirements, workflows, troubleshooting

### 14.3 Review documentation files
```bash
ls -la docs/multi-user-service/
head -50 docs/multi-user-service/admin-guide.md
```
**Expected ✅**: Should show admin-guide.md and research-workflows.md with comprehensive content

---

## PHASE 15: Performance Testing

### 15.1 Create multiple users quickly
```bash
for i in {1..10}; do
  python -m emuses admin add-user "user${i}@test.com" -p "TestPass${i}23" -o "Test Org $i"
done
```
**Expected ✅**: Should create 10 users without errors
**Monitor Terminal #2 for any API errors**

### 15.2 Test large user listing
```bash
python -m emuses admin list-users --limit 50
```
**Expected ✅**: Should handle larger user lists efficiently

---

## Testing Results Template

Create a file to track results:
```bash
cat > testing-results.md << 'EOF'
# EMUSES Testing Results

## What Worked ✅
- [ ] Basic CLI functionality
- [ ] Database setup and migrations
- [ ] API service startup
- [ ] User creation and management
- [ ] Quota management
- [ ] Authentication flows
- [ ] Multi-mode deployment
- [ ] Error handling
- [ ] Documentation and help

## Issues Found ❌
1. 
2. 
3. 

## User Experience Notes
- Setup difficulty: _/10
- Admin workflow clarity: _/10  
- Error message helpfulness: _/10
- Documentation quality: _/10
EOF
```

---

## Emergency Reset Commands

If you get completely stuck:
```bash
# Stop API service (Ctrl+C in Terminal #2)
pkill -f uvicorn
unset EMUSES_DEPLOYMENT_MODE EMUSES_ADMIN_TOKEN EMUSES_SERVICE_URL
rm -f emuses_test.db create_admin_user.py
# Start fresh from Phase 3
```