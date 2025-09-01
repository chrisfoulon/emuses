# EMUSES Multi-User Service Testing Strategy

> **Status**: Ready for Implementation  
> **Date**: Current Session  
> **Context**: Comprehensive functional testing plan for EMUSES multi-user service integration

## Executive Summary

This document provides a complete strategy for testing EMUSES multi-user service functionality, including service startup, authentication, CLI integration, and comprehensive functional validation.

## Architecture Overview

### Service Components
- **FastAPI Service**: Multi-user backend with JWT authentication
- **PostgreSQL Database**: User data and quota management
- **Redis Cache**: Session and performance optimization
- **CLI Integration**: Admin and user commands via REST API

### Authentication Stack
- **FastAPI-Users**: Industry-standard authentication framework
- **JWT Tokens**: Bearer token authentication
- **Role-Based Access**: Admin/superuser vs. regular user permissions

## Testing Strategy

### Phase 1: Service Infrastructure Testing

#### 1.1 Docker Compose Service Startup
```bash
# Test basic service startup
cd /c/Users/Tolhsadum/PycharmProjects/emuses
docker-compose up -d

# Verify services are running
docker-compose ps

# Check service health
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/registry/health
```

#### 1.2 Authentication Service Validation
```bash
# Test authentication endpoints
curl http://localhost:8000/auth/status
curl http://localhost:8000/auth/jwt/login

# Verify API documentation
curl http://localhost:8000/docs
```

### Phase 2: User Management Testing

#### 2.1 Admin User Creation and Token Generation
```bash
# First, create admin user via database or registration endpoint
# Then obtain admin token for CLI commands

# Test token validation
curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8000/auth/validate
```

#### 2.2 CLI Admin Commands Functional Testing
```bash
# Test each admin command with real service running
emuses admin add-user --email test@example.com --password secret123 --organization "Test Org"
emuses admin list-users --token $ADMIN_TOKEN
emuses admin system-status --token $ADMIN_TOKEN
emuses admin set-quota user@example.com storage_gb 50.0 --token $ADMIN_TOKEN
```

### Phase 3: Multi-User Workflow Testing

#### 3.1 Multiple User Authentication
- Create multiple test users with different roles
- Test authentication flows for each user type
- Validate permission boundaries

#### 3.2 Workspace Isolation Testing
```bash
# Test workspace commands for different users
emuses workspace create test-workspace-1 --token $USER1_TOKEN
emuses workspace create test-workspace-1 --token $USER2_TOKEN  # Should succeed or handle isolation
emuses workspace list --token $USER1_TOKEN
emuses workspace list --token $USER2_TOKEN
```

#### 3.3 Quota Enforcement Testing
- Test storage limits
- Test concurrent job limits
- Test compute hour tracking
- Validate quota exceeded scenarios

### Phase 4: Service Integration Testing

#### 4.1 Service Dependency Testing
- Test CLI behavior when service is offline
- Test graceful service startup/shutdown
- Test connection error handling

#### 4.2 Database Integration Testing
- Verify user data persistence
- Test quota tracking accuracy
- Validate authentication token lifecycle

## Implementation Plan

### Step 1: Environment Setup
1. **Create test environment configuration**
2. **Set up Docker services with test data**
3. **Configure authentication secrets**

### Step 2: Service Startup Testing
1. **Start multi-user services via Docker Compose**
2. **Verify all endpoints are accessible**
3. **Test health checks and service discovery**

### Step 3: Authentication Flow Testing
1. **Create admin user via API or database**
2. **Generate JWT tokens for different user types**
3. **Test CLI authentication with real tokens**

### Step 4: Multi-User CLI Testing
1. **Test all admin commands with service running**
2. **Test workspace commands with multiple users**
3. **Validate permission enforcement**

### Step 5: Edge Case and Error Testing
1. **Test service offline scenarios**
2. **Test invalid token handling**
3. **Test quota limit enforcement**

## Testing Tools and Setup

### Required Services
```yaml
# docker-compose.yml services needed
services:
  - api          # Main FastAPI service
  - postgres     # User database
  - redis        # Session cache (staging/production)
  - nginx        # Load balancer (optional for testing)
```

### Environment Variables
```bash
# Required for multi-user testing
EMUSES_DEPLOYMENT_MODE=multi_user
DATABASE_URL=postgresql+asyncpg://emuses_user:password@localhost:5432/emuses_db
JWT_SECRET=your-secret-key-here
POSTGRES_PASSWORD=secure-password
```

### Test Data Requirements
- **Admin User**: Superuser with full permissions
- **Regular Users**: Multiple users with different organizations
- **Test Workspaces**: Sample workspace data
- **Quota Test Data**: Users near/at quota limits

## Expected Outcomes

### Service Functionality
- ✅ **All services start cleanly via Docker Compose**
- ✅ **Authentication endpoints respond correctly**
- ✅ **Database migrations run successfully**
- ✅ **Health checks pass for all services**

### CLI Integration
- ✅ **All admin commands work with running service**
- ✅ **Authentication token validation works**
- ✅ **Error messages are clear and actionable**
- ✅ **Service connection failures are handled gracefully**

### Multi-User Features
- ✅ **User creation and management functions correctly**
- ✅ **Quota tracking and enforcement works**
- ✅ **Workspace isolation is properly implemented**
- ✅ **Role-based permissions are enforced**

## Risk Assessment

### High Risk Areas
1. **Service Startup Dependencies**: Complex service orchestration
2. **Authentication Configuration**: JWT secret management
3. **Database Migrations**: Schema compatibility
4. **Network Configuration**: Port conflicts and connectivity

### Mitigation Strategies
1. **Use staging Docker Compose configuration**
2. **Test with fresh database instance**
3. **Validate all environment variables before testing**
4. **Use isolated network configuration**

## Success Criteria

### Functional Requirements
- [ ] **Service Stack Startup**: All services start and respond to health checks
- [ ] **Authentication Flow**: JWT token generation and validation works
- [ ] **CLI Admin Commands**: All admin commands execute successfully with service
- [ ] **Multi-User Operations**: Multiple users can perform operations simultaneously
- [ ] **Quota Management**: Quota tracking and enforcement functions correctly

### Technical Requirements
- [ ] **Performance**: Service responds within 5 seconds for all operations
- [ ] **Reliability**: Service handles connection failures gracefully
- [ ] **Security**: Authentication and authorization work as designed
- [ ] **Scalability**: Multiple concurrent users don't interfere with each other

## Next Steps

### Immediate Actions
1. **Set up test environment with Docker Compose**
2. **Create admin user and generate initial JWT token**
3. **Test basic service connectivity and health**

### Sequential Testing Plan
1. **Phase 1**: Service startup and health validation
2. **Phase 2**: Authentication and user management testing
3. **Phase 3**: CLI command functional testing with live service
4. **Phase 4**: Multi-user workflow and isolation testing
5. **Phase 5**: Edge case and error scenario testing

## Documentation Updates

### After Testing Completion
- [ ] **Update CLI_REFERENCE.md with multi-user examples**
- [ ] **Document service setup requirements**
- [ ] **Create troubleshooting guide for common issues**
- [ ] **Add multi-user workflow examples**

---

**Testing Framework**: Comprehensive functional testing with live services  
**Validation Method**: Real service integration with Docker Compose  
**Coverage**: Complete multi-user workflow including authentication, permissions, and CLI integration
