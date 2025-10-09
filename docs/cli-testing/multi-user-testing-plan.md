# EMUSES Multi-User Service Testing Plan

## 📋 **Executive Summary**

This plan outlines comprehensive functional testing of EMUSES multi-user capabilities using Docker containers and separate terminal processes to simulate real-world usage scenarios with different user roles and permissions.

## 🏗️ **Architecture Overview**

**Current EMUSES Multi-User Stack:**
- **FastAPI Service**: Admin/workspace management backend
- **PostgreSQL**: User authentication, workspace data, model storage
- **Docker Compose**: Multi-environment orchestration (dev/staging/prod)
- **CLI Client**: Typer-based interface with admin/user commands
- **Authentication**: JWT tokens for admin access, role-based permissions

## 🧪 **Testing Strategy**

### Phase 1: Environment Setup
- **Objective**: Establish Docker-based multi-user testing environment
- **Duration**: 30 minutes
- **Terminal Count**: 3 (service + 2 clients)

### Phase 2: Service Validation
- **Objective**: Verify FastAPI service endpoints and health
- **Duration**: 15 minutes
- **Terminal Count**: 2 (service + test client)

### Phase 3: Multi-User Functional Testing
- **Objective**: Test admin/workspace commands with actual service
- **Duration**: 45 minutes
- **Terminal Count**: 4 (service + admin + 2 users)

### Phase 4: Permission & Security Testing
- **Objective**: Verify role-based access controls
- **Duration**: 30 minutes
- **Terminal Count**: 4 (service + admin + 2 users with different permissions)

## 🔧 **Phase 1: Environment Setup**

### Step 1.1: Choose Docker Environment
```bash
# Options available:
# 1. Development (docker-compose.yml) - Basic setup
# 2. Staging (docker-compose.staging.yml) - Full features with Redis
# 3. Production (docker-compose.production.yml) - Production hardened

# Recommended: Staging environment for comprehensive testing
COMPOSE_FILE="docker-compose.staging.yml"
```

### Step 1.2: Environment Configuration
```bash
# Terminal 1 (Setup)
cd /c/Users/Tolhsadum/PycharmProjects/emuses

# Check available environments
ls docker-compose*.yml

# Create environment file for testing
cp docker/environments/.env.staging.template .env.staging

# Edit critical variables (use test values)
# JWT_SECRET=test-secret-key-for-multi-user-testing
# POSTGRES_PASSWORD=test-password-123
# REDIS_PASSWORD=test-redis-password
```

### Step 1.3: Service Startup
```bash
# Terminal 1 (Service Management)
# Start services in staging mode
docker-compose -f docker-compose.staging.yml up -d

# Monitor startup logs
docker-compose -f docker-compose.staging.yml logs -f

# Wait for health checks to pass
# Expected services: api, postgres, redis, nginx
```

### Step 1.4: Service Health Verification
```bash
# Terminal 2 (Health Check)
# Check service status
docker-compose -f docker-compose.staging.yml ps

# Test API health endpoint
curl http://localhost:8000/api/v1/registry/health

# Test database connectivity
docker exec emuses-postgres-staging psql -U emuses_user -d emuses_db_staging -c "SELECT version();"

# Test Redis connectivity  
docker exec emuses-redis-staging redis-cli ping
```

## ⚡ **Phase 2: Service Validation**

### Step 2.1: API Endpoint Discovery
```bash
# Terminal 2 (API Testing)
# Test OpenAPI documentation
curl http://localhost:8000/docs

# Test API base endpoints
curl http://localhost:8000/api/v1/

# List available admin endpoints
curl http://localhost:8000/api/v1/admin/

# List available workspace endpoints
curl http://localhost:8000/api/v1/workspaces/
```

### Step 2.2: CLI-Service Integration Test
```bash
# Terminal 3 (CLI Testing)
cd /c/Users/Tolhsadum/PycharmProjects/emuses
conda activate emuses

# Test CLI can reach service
emuses admin --help

# Test connection (should show service discovery)
emuses admin status

# Verify workspace commands are available
emuses workspace --help
```

## 👥 **Phase 3: Multi-User Functional Testing**

### Step 3.1: Admin User Setup
```bash
# Terminal 2 (Admin Terminal)
cd /c/Users/Tolhsadum/PycharmProjects/emuses
conda activate emuses

# Create admin token (if required)
# This may involve database setup or API call
export EMUSES_ADMIN_TOKEN="admin-test-token"

# Test admin functionality
echo "=== ADMIN COMMANDS TESTING ==="
emuses admin status
emuses admin users list
emuses admin workspaces list
emuses admin system info
```

### Step 3.2: Create Test Users
```bash
# Terminal 2 (Admin Terminal - Continue)
# Create test users with different roles
echo "=== CREATING TEST USERS ==="

emuses admin users create \
  --username "data_scientist_1" \
  --email "ds1@emuses.test" \
  --role "data_scientist"

emuses admin users create \
  --username "analyst_1" \
  --email "analyst1@emuses.test" \
  --role "analyst"

emuses admin users create \
  --username "viewer_1" \
  --email "viewer1@emuses.test" \
  --role "viewer"

# List created users
emuses admin users list
```

### Step 3.3: Workspace Management
```bash
# Terminal 2 (Admin Terminal - Continue)
echo "=== WORKSPACE MANAGEMENT ==="

# Create test workspaces
emuses admin workspaces create \
  --name "research_project_1" \
  --description "Main research workspace" \
  --owner "data_scientist_1"

emuses admin workspaces create \
  --name "analysis_sandbox" \
  --description "Experimental analysis workspace" \
  --owner "analyst_1"

# List workspaces
emuses admin workspaces list

# Assign workspace permissions
emuses admin workspaces assign \
  --workspace "research_project_1" \
  --user "analyst_1" \
  --permission "read_write"

emuses admin workspaces assign \
  --workspace "research_project_1" \
  --user "viewer_1" \
  --permission "read_only"
```

### Step 3.4: User 1 Testing (Data Scientist)
```bash
# Terminal 3 (User 1 - Data Scientist)
cd /c/Users/Tolhsadum/PycharmProjects/emuses
conda activate emuses

# Set user context (may involve token or login)
export EMUSES_USER_TOKEN="ds1-test-token"
export EMUSES_WORKSPACE="research_project_1"

echo "=== DATA SCIENTIST USER TESTING ==="

# Test workspace access
emuses workspace info

# Test workspace operations
emuses workspace list-models
emuses workspace upload --help
emuses workspace analyze --help

# Test data scientist specific commands
emuses predict --help
emuses train --help
emuses evaluate --help
```

### Step 3.5: User 2 Testing (Analyst)
```bash
# Terminal 4 (User 2 - Analyst)
cd /c/Users/Tolhsadum/PycharmProjects/emuses
conda activate emuses

# Set user context
export EMUSES_USER_TOKEN="analyst1-test-token"
export EMUSES_WORKSPACE="research_project_1"

echo "=== ANALYST USER TESTING ==="

# Test workspace access (should have read_write to research_project_1)
emuses workspace info
emuses workspace list-models

# Test analyst specific commands
emuses analyze --help
emuses visualize --help
emuses export --help

# Test access to own workspace
export EMUSES_WORKSPACE="analysis_sandbox"
emuses workspace info
```

## 🔒 **Phase 4: Permission & Security Testing**

### Step 4.1: Access Control Validation
```bash
# Terminal 3 (Data Scientist - Restricted Tests)
echo "=== ACCESS CONTROL TESTING ==="

# Try admin commands (should fail)
emuses admin users list  # Expected: Permission denied
emuses admin system info  # Expected: Permission denied

# Try accessing unauthorized workspace
export EMUSES_WORKSPACE="analysis_sandbox"
emuses workspace upload dummy_file.txt  # Expected: Access denied
```

### Step 4.2: Role-Based Permission Matrix
```bash
# Terminal 4 (Analyst - Permission Tests)
echo "=== ROLE-BASED PERMISSION TESTING ==="

# Test read_only workspace access
export EMUSES_WORKSPACE="research_project_1"
emuses workspace info  # Expected: Success
emuses workspace list-models  # Expected: Success

# Test write operations (should vary by permission level)
emuses workspace upload test_file.txt  # Expected: Success (has read_write)
emuses workspace delete-model model_123  # Expected: Check permission level
```

### Step 4.3: Token Validation Testing
```bash
# Terminal 2 (Admin - Security Tests)
echo "=== TOKEN VALIDATION TESTING ==="

# Test with invalid token
export EMUSES_ADMIN_TOKEN="invalid-token-123"
emuses admin status  # Expected: Authentication failed

# Test with no token
unset EMUSES_ADMIN_TOKEN
emuses admin status  # Expected: Authentication required

# Test token expiration (if applicable)
# This would require manipulating token timestamps
```

## 📊 **Results Documentation Plan**

### Test Results Structure
```
docs/cli-testing/multi-user-results/
├── phase1-setup/
│   ├── docker-services-status.txt
│   ├── health-check-results.txt
│   └── environment-config.txt
├── phase2-validation/
│   ├── api-endpoints-test.txt
│   ├── cli-service-integration.txt
│   └── service-discovery.txt
├── phase3-functional/
│   ├── admin-commands-results.txt
│   ├── user-creation-log.txt
│   ├── workspace-management-log.txt
│   ├── data-scientist-tests.txt
│   └── analyst-tests.txt
├── phase4-security/
│   ├── access-control-results.txt
│   ├── permission-matrix-validation.txt
│   └── token-validation-results.txt
└── summary/
    ├── command-success-matrix.csv
    ├── discovered-issues.md
    └── recommendations.md
```

### Success Criteria
- ✅ All Docker services start successfully
- ✅ CLI can communicate with FastAPI service
- ✅ Admin commands create/manage users and workspaces
- ✅ Users can access their permitted workspaces
- ✅ Role-based permissions are enforced
- ✅ Invalid tokens/permissions are rejected

### Expected Discoveries
- **Service Architecture**: How CLI authenticates with FastAPI
- **Token Management**: JWT token generation/validation process
- **Database Schema**: User/workspace/permission table structure
- **API Endpoints**: Complete list of multi-user service endpoints
- **Configuration**: Required environment variables and settings

## 🚀 **Execution Timeline**

**Total Estimated Time**: 2 hours

1. **Setup Phase** (30 min): Docker environment, service startup
2. **Validation Phase** (15 min): API health, CLI integration
3. **Functional Testing** (45 min): Multi-user scenarios, workspace management
4. **Security Testing** (30 min): Permission validation, token security

## 🔄 **Next Steps After Testing**

1. **Documentation Updates**: Update CLI_REFERENCE.md with multi-user findings
2. **Test Integration**: Add findings to automated test suite
3. **User Guide Updates**: Create multi-user deployment guide
4. **Issue Reporting**: Document any bugs or missing features discovered

---

**Note**: This plan assumes EMUSES multi-user service is fully implemented. If some features are missing, the testing will help identify what needs to be developed versus what's already functional.
