# Configuration Isolation Guide for EMUSES Testing

## Key Configuration Conflicts to Watch For

### 1. Environment Variables (Major Clash Risk)

**Problem**: Environment variables persist across commands and can cause unexpected behavior.

**Critical Variables**:
```bash
EMUSES_DEPLOYMENT_MODE=local|multi_user|production
EMUSES_DATABASE_URL=sqlite:///path or postgresql://...
EMUSES_JWT_SECRET=your-secret-key
EMUSES_ADMIN_TOKEN=jwt-token-here
EMUSES_SERVICE_URL=http://localhost:8000
```

**Isolation Strategy**:
```bash
# Before each major test phase, explicitly unset and reset:
unset EMUSES_DEPLOYMENT_MODE
unset EMUSES_DATABASE_URL  
unset EMUSES_JWT_SECRET
unset EMUSES_ADMIN_TOKEN
unset EMUSES_SERVICE_URL

# Then set only what you need for that specific test
export EMUSES_DEPLOYMENT_MODE=local  # or whatever you're testing
```

### 2. Database State (Persistent Data)

**Problem**: Created users, workspaces, and jobs persist between tests.

**What Accumulates**:
- User accounts (admin@emuses.local, researcher@university.edu, etc.)
- JWT tokens (become invalid over time)
- Workspaces and datasets
- Background jobs/tasks

**Isolation Options**:

**Option A: Fresh Database Per Test Phase**
```bash
# Before major test phases:
rm emuses_test.db  # if using SQLite
# OR drop/recreate PostgreSQL database
alembic upgrade head  # recreate tables
```

**Option B: Keep Data, Reset Auth**
```bash
# Just reset authentication between auth mode tests:
unset EMUSES_ADMIN_TOKEN
# Get fresh token when needed
```

### 3. API Service State (Running Process)

**Problem**: API service keeps running with old configuration.

**Critical Restarts Needed**:
- When changing `EMUSES_DEPLOYMENT_MODE`
- When changing `EMUSES_DATABASE_URL`
- When changing `EMUSES_JWT_SECRET`

**Isolation Strategy**:
```bash
# In API terminal, always restart when switching modes:
# Ctrl+C to stop
export EMUSES_DEPLOYMENT_MODE=new_mode
python -m uvicorn emuses.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. JWT Token Expiration

**Problem**: Tokens expire and cause 401 errors that look like bugs.

**Default Expiration**: Typically 1 hour (check our JWT config)

**Symptoms**:
- Commands work initially, then start failing with 401
- Error messages might not clearly indicate token expiration

**Isolation Strategy**:
```bash
# Get fresh token before each major test phase:
curl -X POST "http://localhost:8000/auth/jwt/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin@emuses.local&password=admin123"
export EMUSES_ADMIN_TOKEN="new-token-here"
```

## Recommended Test Isolation Points

### Clean Slate Reset (Between Major Phases)
```bash
# 1. Kill API service (Ctrl+C in Terminal #2)
# 2. Clean environment
unset EMUSES_DEPLOYMENT_MODE EMUSES_DATABASE_URL EMUSES_JWT_SECRET 
unset EMUSES_ADMIN_TOKEN EMUSES_SERVICE_URL
# 3. Optional: Fresh database
rm emuses_test.db  # if using SQLite
# 4. Set new config for next phase
```

### Quick Auth Reset (Between Auth Tests)
```bash
# Just reset auth tokens, keep data:
unset EMUSES_ADMIN_TOKEN
# API service can keep running
```

### Mode Switch Reset (LOCAL → MULTI_USER → PRODUCTION)
```bash
# 1. Stop API service
# 2. Change EMUSES_DEPLOYMENT_MODE
# 3. Restart API service
# 4. Get fresh tokens if switching to auth mode
```

## Specific Conflict Scenarios

### Scenario 1: Testing LOCAL → MULTI_USER
**Problem**: CLI might try to authenticate when it shouldn't or vice versa.

**Safe Transition**:
```bash
# Test LOCAL mode first
unset EMUSES_DEPLOYMENT_MODE  # defaults to LOCAL
python -m emuses admin system-status  # should work without auth

# Switch to MULTI_USER
export EMUSES_DEPLOYMENT_MODE=multi_user
# Restart API service with this mode
# Get admin token
# Test with auth
```

### Scenario 2: Testing Different Databases
**Problem**: Alembic tracks migrations per database, mixed state.

**Safe Transition**:
```bash
# SQLite → PostgreSQL
export EMUSES_DATABASE_URL="postgresql://..."
alembic upgrade head  # run migrations on new DB
# All users will be gone, need to recreate admin
```

### Scenario 3: Testing Token vs No Token
**Problem**: Environment variable set but testing no-auth scenario.

**Safe Transition**:
```bash
# Test with token
export EMUSES_ADMIN_TOKEN="valid-token"
python -m emuses admin list-users

# Test without token (should fail in multi-user mode)
unset EMUSES_ADMIN_TOKEN
python -m emuses admin list-users  # should show auth error
```

### Scenario 4: Testing Connection Failures
**Problem**: API service state vs CLI expectations.

**Safe Test**:
```bash
# Test CLI when API is down
# Stop API service first
export EMUSES_ADMIN_TOKEN="valid-token"  # token exists but can't connect
python -m emuses admin system-status  # should show connection error

# Restart API and retest
```

## Configuration Verification Commands

Before each test phase, verify your configuration:

```bash
# Check environment
echo "Mode: $EMUSES_DEPLOYMENT_MODE"
echo "DB: $EMUSES_DATABASE_URL" 
echo "Token set: ${EMUSES_ADMIN_TOKEN:+YES}"
echo "Service URL: $EMUSES_SERVICE_URL"

# Check API service
curl -s http://localhost:8000/health || echo "API not responding"

# Check database
ls -la emuses_test.db || echo "SQLite DB not found"
# OR
psql $EMUSES_DATABASE_URL -c "SELECT 1;" || echo "PostgreSQL not accessible"

# Check token validity (if set)
if [[ -n "$EMUSES_ADMIN_TOKEN" ]]; then
    curl -H "Authorization: Bearer $EMUSES_ADMIN_TOKEN" \
         http://localhost:8000/users/me || echo "Token invalid/expired"
fi
```

## Recommended Testing Sequence with Isolation

1. **Phase 1-2 (LOCAL mode)**: No isolation needed, no auth/database
2. **Phase 3 (Database)**: Clean slate, pick SQLite OR PostgreSQL
3. **Phase 4-5 (API + Multi-user)**: Restart API, fresh tokens
4. **Phase 6-10 (Full workflow)**: Keep running, refresh tokens as needed
5. **Phase 11 (Production mode)**: RESTART API with new mode
6. **Phase 12-15 (Edge cases)**: Quick auth resets, keep API running

## Emergency Reset (When Confused)

If you get stuck with weird errors:

```bash
# Nuclear reset
pkill -f uvicorn  # kill API service
unset EMUSES_DEPLOYMENT_MODE EMUSES_DATABASE_URL EMUSES_JWT_SECRET 
unset EMUSES_ADMIN_TOKEN EMUSES_SERVICE_URL
rm -f emuses_test.db  # if using SQLite
rm -f create_admin_user.py

# Start fresh from Phase 3 (Database Setup)
```

This should help you avoid most configuration conflicts!