# EMUSES Admin Functions Testing Plan

**Purpose**: Document and test admin panel features in multi-user deployment mode
**Date**: 2025-10-06
**Status**: Pre-testing setup phase

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Command Categories](#command-categories)
3. [Remote Setup Guide](#remote-setup-guide)
4. [Testing Procedures](#testing-procedures)
5. [Test Results Template](#test-results-template)
6. [Troubleshooting](#troubleshooting)

---

## Executive Summary

### What This Document Covers

This document provides a structured plan for testing EMUSES admin panel functions that require multi-user deployment configuration. These features are distinct from single-user pipeline operations and require:

- Multi-user deployment mode (`EMUSES_DEPLOYMENT_MODE=multi_user`)
- PostgreSQL database connection
- FastAPI service running
- Authentication tokens
- Remote server access via SSH

### Testing Scope

**Already Tested (Single-User Mode)**
- Pipeline commands: `full`, `umap`, `heatmap`, `inference`
- Model registry (local mode): `install`, `list`, `info`, `search`
- Basic CLI functionality

**Requires Testing (Multi-User Mode)**
- Admin panel commands: user management, quotas, system monitoring
- Workspace management commands
- Service-based execution
- Authentication and token handling

### Key Isolation Strategy

The remote setup will use:
- Separate Python virtual environment
- Non-default port (8001 instead of 8000)
- Isolated environment variables
- Separate PostgreSQL database
- No conflicts with local single-user installation

---

## Command Categories

### Category 1: Admin User Management

These commands manage user accounts in multi-user deployments.

#### `emuses admin add-user`

**Purpose**: Create new user accounts
**Requirements**:
- Multi-user mode enabled
- Database connection
- Admin authentication token

**Test Cases**:
1. Create basic user with email and password
2. Create user with custom organization
3. Create inactive user (--inactive flag)
4. Create unverified user (--unverified flag)
5. Attempt to create duplicate user (should fail)
6. Create user without admin token (should fail)

**Expected Behavior**:
- Success: User created with UUID, default quotas assigned
- Failure: Clear error messages for validation failures

---

#### `emuses admin list-users`

**Purpose**: Display all system users
**Requirements**:
- Multi-user mode enabled
- Database connection
- Admin authentication token

**Test Cases**:
1. List default 10 users
2. List with custom limit (--limit 50)
3. List with pagination (--skip 20 --limit 10)
4. List without authentication (should fail)

**Expected Behavior**:
- Formatted table with user ID, email, organization, status flags
- Pagination working correctly
- Clear authentication error if token missing

---

#### `emuses admin set-quota`

**Purpose**: Adjust user resource quotas
**Requirements**:
- Multi-user mode enabled
- Database connection
- Admin authentication token
- Valid user email/ID

**Test Cases**:
1. Set storage quota (storage_gb)
2. Set concurrent job limit (concurrent_jobs)
3. Set compute hours (compute_hours)
4. Attempt invalid quota type (should fail)
5. Set quota for non-existent user (should fail)

**Expected Behavior**:
- Quota updated successfully
- Changes reflected in user profile
- Validation errors for invalid inputs

---

### Category 2: System Monitoring

#### `emuses admin system-status`

**Purpose**: Display system health and metrics
**Requirements**:
- Multi-user mode enabled
- Service running
- Admin authentication token

**Test Cases**:
1. Basic status check
2. Detailed status (--detailed flag)
3. Check during high load
4. Check with no jobs running

**Expected Behavior**:
- System status (healthy/degraded/critical)
- Component status (database, API, background tasks)
- Job queue statistics in detailed mode

---

#### `emuses admin cancel-job`

**Purpose**: Cancel running or stuck jobs
**Requirements**:
- Multi-user mode enabled
- Service running
- Admin authentication token
- Active job ID

**Test Cases**:
1. Cancel job with confirmation prompt
2. Force cancel without prompt (--force)
3. Cancel non-existent job (should fail gracefully)
4. Cancel already completed job

**Expected Behavior**:
- Job terminated and cleaned up
- Status updated to 'cancelled'
- Clear error for invalid job IDs

---

### Category 3: Workspace Management

#### `emuses workspace create`

**Purpose**: Create new team workspace
**Requirements**:
- Multi-user mode enabled
- Database connection
- Authentication token

**Test Cases**:
1. Create workspace with name only
2. Create workspace with description
3. Create duplicate workspace (behavior?)

**Expected Behavior**:
- Workspace created with UUID
- Visible in workspace list
- Owner has full permissions

---

#### `emuses workspace list`

**Purpose**: View available workspaces
**Requirements**:
- Multi-user mode enabled
- Database connection
- Authentication token

**Test Cases**:
1. List user's workspaces
2. List with no workspaces created
3. List after creating multiple workspaces

**Expected Behavior**:
- Formatted table with workspace info
- Shows only user's accessible workspaces

---

#### `emuses workspace info`

**Purpose**: Get detailed workspace information
**Requirements**:
- Multi-user mode enabled
- Database connection
- Authentication token
- Valid workspace ID

**Test Cases**:
1. Get info for owned workspace
2. Get info for shared workspace
3. Get info for non-existent workspace (should fail)
4. Get info without permission (should fail)

**Expected Behavior**:
- Complete workspace details
- Usage statistics if available
- Permission denied for unauthorized access

---

### Category 4: Model Registry (Multi-User Mode)

These commands work differently in multi-user mode vs local mode.

#### `emuses models list --workspace`

**Purpose**: List models in specific workspace
**Requirements**:
- Multi-user mode enabled
- Database connection
- Authentication token

**Test Cases**:
1. List models in user workspace
2. List with --public flag (include public models)
3. List with --no-public flag
4. List in empty workspace

**Expected Behavior**:
- Workspace-scoped model list
- Public models included based on flag
- Empty list if no models

---

### Category 5: Deployment Mode Detection

#### Documentation Consistency Check

**Purpose**: Verify documentation matches actual behavior

**Test Areas**:
1. Environment variable naming (`EMUSES_DEPLOYMENT_MODE`)
2. Mode values (`local`, `multi_user` vs `multi-user`)
3. Required variables for each mode
4. Default behavior when mode not set

**Documentation Sources**:
- CLI_REFERENCE.md
- admin-guide.md
- deployment_config.py
- README.md
- INSTALLATION.md

---

## Remote Setup Guide

### Prerequisites

**Local Machine Requirements**:
- SSH access to remote server
- SSH keys configured
- Terminal multiplexer recommended (tmux/screen)

**Remote Server Requirements**:
- Linux system with Python 3.11+
- PostgreSQL database
- Network access to database
- Sufficient storage space
- sudo/admin access (for initial setup)

---

### Step 1: Initial Server Connection

```bash
# Connect to remote server
ssh user@remote-server.example.com

# Create dedicated directory for multi-user setup
mkdir -p ~/emuses-multi-user
cd ~/emuses-multi-user
```

---

### Step 2: Python Environment Setup

```bash
# Create isolated virtual environment
python3.11 -m venv emuses-multi-user-env

# Activate environment
source emuses-multi-user-env/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install EMUSES
pip install git+https://github.com/chrisfoulon/emuses.git

# Verify installation
python -m emuses.cli --version
```

---

### Step 3: PostgreSQL Database Setup

```bash
# Option A: Use existing PostgreSQL server
# Check if PostgreSQL is available
psql --version

# Option B: Install PostgreSQL (if needed)
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE emuses_multi_user_test;
CREATE USER emuses_test_admin WITH PASSWORD 'secure_test_password';
GRANT ALL PRIVILEGES ON DATABASE emuses_multi_user_test TO emuses_test_admin;
EOF

# Verify connection
psql -h localhost -U emuses_test_admin -d emuses_multi_user_test -c "SELECT version();"
```

---

### Step 4: Environment Configuration

```bash
# Create environment configuration file
cat > ~/.emuses-multi-user-env << 'EOF'
# EMUSES Multi-User Testing Environment

# Deployment mode (both formats supported)
export EMUSES_DEPLOYMENT_MODE="multi_user"
# Alternative: export EMUSES_DEPLOYMENT_MODE="multi-user"

# Database connection
export DATABASE_URL="postgresql://emuses_test_admin:secure_test_password@localhost/emuses_multi_user_test"

# JWT secret for authentication
export EMUSES_JWT_SECRET="test_jwt_secret_$(openssl rand -base64 32)"

# Service URL (non-default port to avoid conflicts)
export EMUSES_SERVICE_URL="http://localhost:8001"

# Admin token (will be set after first user creation)
# export EMUSES_ADMIN_TOKEN="will_be_set_later"

# Optional: Redis for caching (if available)
# export REDIS_URL="redis://localhost:6379/0"
EOF

# Load environment variables
source ~/.emuses-multi-user-env

# Verify configuration
env | grep EMUSES
```

---

### Step 5: Database Migrations

```bash
# Initialize database schema
python -m emuses.multi_user_service.init_db

# Or use Alembic if available
# alembic upgrade head

# Verify database tables
psql -h localhost -U emuses_test_admin -d emuses_multi_user_test -c "\dt"
```

---

### Step 6: Start Multi-User Service

```bash
# Start service on non-default port
# Option A: Direct Python
python -m uvicorn emuses.api.main:app --host 0.0.0.0 --port 8001 &

# Option B: Using emuses service command (if available)
# python -m emuses.cli service start --port 8001 &

# Save PID for later
echo $! > service.pid

# Wait for service to start
sleep 5

# Verify service is running
curl http://localhost:8001/api/health

# Expected response:
# {"status":"healthy","timestamp":"..."}
```

---

### Step 7: Create Initial Admin User

```bash
# Create first admin user (bootstrap)
python -m emuses.cli admin add-user \
  admin@test.local \
  --password "Admin123Test!" \
  --organization "Test Organization" \
  --service-url http://localhost:8001

# Expected output:
# ✅ User created successfully!
#   ID: <uuid>
#   Email: admin@test.local
#   Organization: Test Organization
#   Active: True
#   Verified: True
```

---

### Step 8: Obtain Admin Token

```bash
# Login to get admin token
# This step depends on authentication implementation
# Option A: Using CLI if login command exists
# python -m emuses.cli login admin@test.local

# Option B: Using API directly
curl -X POST http://localhost:8001/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.local","password":"Admin123Test!"}'

# Expected response:
# {"access_token":"<jwt_token>","token_type":"bearer"}

# Save token to environment
export EMUSES_ADMIN_TOKEN="<jwt_token_from_response>"

# Update environment file
echo "export EMUSES_ADMIN_TOKEN=\"$EMUSES_ADMIN_TOKEN\"" >> ~/.emuses-multi-user-env
```

---

### Step 9: Verification

```bash
# Verify admin commands work
python -m emuses.cli admin system-status \
  --service-url http://localhost:8001 \
  --token "$EMUSES_ADMIN_TOKEN"

# Expected output:
# System Status: HEALTHY
# Components: ✅ database, ✅ api, ✅ background_tasks

# List users (should show admin user)
python -m emuses.cli admin list-users \
  --service-url http://localhost:8001 \
  --token "$EMUSES_ADMIN_TOKEN"

# Expected output:
# System Users table with admin@test.local
```

---

### Step 10: Testing Session Script

Create a script for easy test session startup:

```bash
cat > ~/emuses-multi-user/start-test-session.sh << 'EOF'
#!/bin/bash
# EMUSES Multi-User Test Session Starter

echo "🚀 Starting EMUSES Multi-User Test Session"
echo "=========================================="

# Navigate to test directory
cd ~/emuses-multi-user

# Activate virtual environment
source emuses-multi-user-env/bin/activate

# Load environment variables
source ~/.emuses-multi-user-env

# Check if service is running
if pgrep -f "uvicorn emuses.api.main:app" > /dev/null; then
    echo "✅ Service already running"
else
    echo "🔄 Starting service..."
    python -m uvicorn emuses.api.main:app --host 0.0.0.0 --port 8001 > service.log 2>&1 &
    echo $! > service.pid
    sleep 5

    if curl -s http://localhost:8001/api/health > /dev/null; then
        echo "✅ Service started successfully"
    else
        echo "❌ Service failed to start - check service.log"
        exit 1
    fi
fi

# Display environment
echo ""
echo "Environment Configuration:"
echo "  Deployment Mode: $EMUSES_DEPLOYMENT_MODE"
echo "  Service URL: $EMUSES_SERVICE_URL"
echo "  Database: $DATABASE_URL"
echo "  Admin Token: ${EMUSES_ADMIN_TOKEN:0:20}..."
echo ""
echo "🎯 Ready for testing!"
echo "Try: python -m emuses.cli admin --help"
EOF

chmod +x ~/emuses-multi-user/start-test-session.sh
```

---

## Testing Procedures

### General Testing Protocol

For each command in the test plan:

1. **Setup Phase**
   - Ensure environment variables are loaded
   - Verify service is running
   - Confirm authentication token is valid

2. **Execution Phase**
   - Run command with specified parameters
   - Record exact command used
   - Copy full output (stdout and stderr)

3. **Verification Phase**
   - Check exit code (0 for success)
   - Verify expected behavior occurred
   - Check database state if applicable
   - Look for error messages or warnings

4. **Documentation Phase**
   - Record results in template below
   - Note any unexpected behavior
   - Document error messages
   - Suggest improvements if needed

---

### Test Execution Checklist

Before starting tests:

```bash
# 1. Load environment
source ~/.emuses-multi-user-env

# 2. Verify service health
curl http://localhost:8001/api/health

# 3. Verify authentication
python -m emuses.cli admin system-status \
  --service-url http://localhost:8001 \
  --token "$EMUSES_ADMIN_TOKEN"

# 4. Create test log directory
mkdir -p ~/emuses-multi-user/test-logs
cd ~/emuses-multi-user/test-logs
```

---

## Test Results Template

### Template for Each Command Test

Copy this template for each command you test:

```markdown
---
## Test: [Command Name]

**Date**: YYYY-MM-DD
**Tester**: [Your Name]
**Test Number**: [Sequential number]

### Command Tested
```bash
[Exact command used]
```

### Environment
- Deployment Mode: [local/multi_user/production]
- Service URL: [URL]
- Token Used: [Yes/No]
- Database: [Connection string or "N/A"]

### Expected Behavior
[What should happen]

### Actual Output
```
[Paste complete output here]
```

### Exit Code
[0 for success, non-zero for error]

### Result
- [ ] ✅ PASS - Works as expected
- [ ] ⚠️ PARTIAL - Works with issues
- [ ] ❌ FAIL - Does not work
- [ ] 🔧 NEEDS_FIX - Requires code changes

### Issues Identified
1. [Issue description if any]
2. [Issue description if any]

### Documentation Consistency
- [ ] Command syntax matches CLI_REFERENCE.md
- [ ] Behavior matches admin-guide.md
- [ ] Error messages are clear and helpful
- [ ] Help text is accurate

### Recommendations
[Any suggestions for improvement]

### Additional Notes
[Any other relevant information]

---
```

---

## Example Test Session

Here's an example of testing the `admin add-user` command:

```markdown
---
## Test: admin add-user

**Date**: 2025-10-06
**Tester**: Chris Foulon
**Test Number**: 001

### Command Tested
```bash
python -m emuses.cli admin add-user \
  test.researcher@university.edu \
  --password "SecurePass123!" \
  --organization "Test Research Lab" \
  --service-url http://localhost:8001 \
  --token "$EMUSES_ADMIN_TOKEN"
```

### Environment
- Deployment Mode: multi_user
- Service URL: http://localhost:8001
- Token Used: Yes
- Database: postgresql://localhost/emuses_multi_user_test

### Expected Behavior
- User should be created successfully
- UUID should be generated
- Default quotas should be assigned
- Success message should be displayed

### Actual Output
```
Creating user...
✅ User created successfully!

ID: 12345678-1234-1234-1234-123456789abc
Email: test.researcher@university.edu
Organization: Test Research Lab
Active: True
Verified: True
```

### Exit Code
0

### Result
- [x] ✅ PASS - Works as expected
- [ ] ⚠️ PARTIAL - Works with issues
- [ ] ❌ FAIL - Does not work
- [ ] 🔧 NEEDS_FIX - Requires code changes

### Issues Identified
None

### Documentation Consistency
- [x] Command syntax matches CLI_REFERENCE.md
- [x] Behavior matches admin-guide.md
- [x] Error messages are clear and helpful
- [x] Help text is accurate

### Recommendations
None - working perfectly

### Additional Notes
- User appears in database correctly
- Default quotas were applied: 10GB storage, 2 concurrent jobs
- Email verification was skipped (--verified flag default)

---
```

---

## Troubleshooting

### Common Issues and Solutions

#### Issue: Service Won't Start

**Symptoms**:
```bash
curl http://localhost:8001/api/health
# curl: (7) Failed to connect to localhost port 8001: Connection refused
```

**Solutions**:
1. Check if port is already in use:
   ```bash
   lsof -i :8001
   netstat -tuln | grep 8001
   ```

2. Check service logs:
   ```bash
   tail -f service.log
   ```

3. Try starting service in foreground for debugging:
   ```bash
   python -m uvicorn emuses.api.main:app --host 0.0.0.0 --port 8001
   ```

4. Verify environment variables:
   ```bash
   env | grep EMUSES
   env | grep DATABASE_URL
   ```

---

#### Issue: Authentication Failures

**Symptoms**:
```bash
python -m emuses.cli admin list-users
# ❌ Service error: 401 Unauthorized
```

**Solutions**:
1. Verify token is set:
   ```bash
   echo $EMUSES_ADMIN_TOKEN
   ```

2. Check token expiration:
   ```bash
   # Token might have expired - get new one
   curl -X POST http://localhost:8001/api/v1/auth/token \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@test.local","password":"Admin123Test!"}'
   ```

3. Verify token in environment file:
   ```bash
   grep EMUSES_ADMIN_TOKEN ~/.emuses-multi-user-env
   ```

4. Try explicit token parameter:
   ```bash
   python -m emuses.cli admin list-users \
     --token "$EMUSES_ADMIN_TOKEN"
   ```

---

#### Issue: Database Connection Errors

**Symptoms**:
```bash
# Error: could not connect to database
# FATAL: password authentication failed
```

**Solutions**:
1. Verify database is running:
   ```bash
   sudo systemctl status postgresql
   # or
   pgrep -u postgres
   ```

2. Test database connection manually:
   ```bash
   psql -h localhost -U emuses_test_admin -d emuses_multi_user_test
   ```

3. Check DATABASE_URL format:
   ```bash
   echo $DATABASE_URL
   # Should be: postgresql://user:pass@host/dbname
   ```

4. Verify database permissions:
   ```bash
   sudo -u postgres psql -c "\du emuses_test_admin"
   ```

---

#### Issue: Command Not Found

**Symptoms**:
```bash
python -m emuses.cli admin --help
# ModuleNotFoundError: No module named 'emuses.cli.admin_commands'
```

**Solutions**:
1. Verify you're in correct virtual environment:
   ```bash
   which python
   echo $VIRTUAL_ENV
   ```

2. Reinstall EMUSES:
   ```bash
   pip install --force-reinstall git+https://github.com/chrisfoulon/emuses.git
   ```

3. Check EMUSES version:
   ```bash
   python -m emuses.cli --version
   ```

---

#### Issue: Deployment Mode Not Recognized

**Symptoms**:
```bash
# Warning: Unknown deployment mode 'multi_user', defaulting to local mode
```

**Solutions**:
1. Check environment variable format:
   ```bash
   # Try both formats
   export EMUSES_DEPLOYMENT_MODE="multi_user"
   # or
   export EMUSES_DEPLOYMENT_MODE="multi-user"
   ```

2. Verify normalization is working:
   ```bash
   python -c "from emuses.multi_user_service.deployment_config import detect_deployment_mode; print(detect_deployment_mode())"
   ```

3. Check for typos:
   ```bash
   env | grep -i deploy
   ```

---

#### Issue: Permission Denied Errors

**Symptoms**:
```bash
# ❌ Error: 403 Forbidden
# You don't have permission to perform this action
```

**Solutions**:
1. Verify user is admin/superuser:
   ```bash
   psql -h localhost -U emuses_test_admin -d emuses_multi_user_test \
     -c "SELECT email, is_superuser FROM users WHERE email='admin@test.local';"
   ```

2. Use admin token, not regular user token
   ```bash
   # Ensure EMUSES_ADMIN_TOKEN is set to admin user's token
   ```

3. Check command requires admin privileges:
   ```bash
   python -m emuses.cli admin COMMAND --help
   # Look for "Requires admin authentication token" in help text
   ```

---

### Diagnostic Commands

Quick diagnostic script to check system state:

```bash
cat > ~/emuses-multi-user/diagnose.sh << 'EOF'
#!/bin/bash
echo "🔍 EMUSES Multi-User Diagnostic Check"
echo "====================================="

echo ""
echo "1. Environment Variables:"
env | grep EMUSES || echo "  ⚠️ No EMUSES variables set"
env | grep DATABASE_URL || echo "  ⚠️ DATABASE_URL not set"

echo ""
echo "2. Virtual Environment:"
if [ -n "$VIRTUAL_ENV" ]; then
    echo "  ✅ Active: $VIRTUAL_ENV"
else
    echo "  ❌ Not activated"
fi

echo ""
echo "3. Service Status:"
if curl -s http://localhost:8001/api/health > /dev/null 2>&1; then
    echo "  ✅ Service responding"
    curl -s http://localhost:8001/api/health | python -m json.tool
else
    echo "  ❌ Service not responding"
fi

echo ""
echo "4. Database Connection:"
if psql -h localhost -U emuses_test_admin -d emuses_multi_user_test -c "SELECT 1;" > /dev/null 2>&1; then
    echo "  ✅ Database accessible"
else
    echo "  ❌ Database connection failed"
fi

echo ""
echo "5. EMUSES Installation:"
if python -m emuses.cli --version > /dev/null 2>&1; then
    echo "  ✅ EMUSES installed"
    python -m emuses.cli --version
else
    echo "  ❌ EMUSES not found"
fi

echo ""
echo "6. Admin Token:"
if [ -n "$EMUSES_ADMIN_TOKEN" ]; then
    echo "  ✅ Token set (${#EMUSES_ADMIN_TOKEN} chars)"
else
    echo "  ❌ Token not set"
fi

echo ""
echo "====================================="
EOF

chmod +x ~/emuses-multi-user/diagnose.sh
```

Run diagnostics:
```bash
./diagnose.sh
```

---

## Post-Testing Cleanup

After completing all tests:

### Stop Services

```bash
# Stop FastAPI service
if [ -f service.pid ]; then
    kill $(cat service.pid)
    rm service.pid
fi

# Verify stopped
curl http://localhost:8001/api/health
# Should fail with connection refused
```

### Archive Test Results

```bash
# Create archive of test logs
cd ~/emuses-multi-user
tar -czf test-results-$(date +%Y%m%d).tar.gz test-logs/

# Copy to local machine
# From your local machine:
# scp user@remote:~/emuses-multi-user/test-results-*.tar.gz .
```

### Optional: Clean Database

```bash
# If you want to start fresh for next test session
sudo -u postgres psql << EOF
DROP DATABASE IF EXISTS emuses_multi_user_test;
CREATE DATABASE emuses_multi_user_test;
GRANT ALL PRIVILEGES ON DATABASE emuses_multi_user_test TO emuses_test_admin;
EOF
```

### Keep Environment for Future Tests

```bash
# Don't delete the virtual environment or config files
# They can be reused for future testing sessions
# Just run start-test-session.sh to resume testing
```

---

## Documentation Consistency Analysis

### Areas to Verify

1. **Environment Variable Naming**
   - [ ] `EMUSES_DEPLOYMENT_MODE` consistent across docs
   - [ ] Both `multi_user` and `multi-user` supported
   - [ ] Documentation mentions both formats

2. **Command Syntax**
   - [ ] CLI_REFERENCE.md matches actual command signatures
   - [ ] admin-guide.md examples are runnable
   - [ ] Help text matches documentation

3. **Authentication Flow**
   - [ ] Token acquisition documented
   - [ ] Token usage in commands explained
   - [ ] Token storage recommendations provided

4. **Deployment Modes**
   - [ ] Local mode clearly distinguished
   - [ ] Multi-user mode requirements listed
   - [ ] Production mode differences explained

5. **Error Messages**
   - [ ] Clear and actionable
   - [ ] Match documentation
   - [ ] Include troubleshooting hints

---

## Success Criteria

This testing plan is successful when:

- [ ] All admin commands tested in multi-user mode
- [ ] Documentation inconsistencies identified and documented
- [ ] Working examples for each command collected
- [ ] Clear separation between local and multi-user modes
- [ ] Troubleshooting section covers common issues
- [ ] Test results can guide bug fixes and documentation updates

---

## Next Steps

After completing testing:

1. **Create Issue Reports**
   - File GitHub issues for any bugs found
   - Include test output and environment details
   - Reference this testing plan document

2. **Update Documentation**
   - Fix any inconsistencies found
   - Add working examples from tests
   - Update troubleshooting sections

3. **Improve Error Messages**
   - Make unclear messages more helpful
   - Add context to error outputs
   - Include troubleshooting hints

4. **Enhance Admin Commands**
   - Add missing features identified during testing
   - Improve command ergonomics
   - Add helpful defaults

---

**Document Version**: 1.0
**Last Updated**: 2025-10-06
**Maintained By**: EMUSES Development Team
