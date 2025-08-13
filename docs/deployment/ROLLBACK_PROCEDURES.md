# EMUSES Rollback Procedures

## Overview

This document provides comprehensive procedures for safely rolling back EMUSES deployments to previous versions. Follow these procedures carefully to minimize downtime and prevent data loss.

## Prerequisites

- Access to production/staging environment
- Database backup verification
- Git repository access with version tags
- Docker environment with necessary images

## Emergency Contacts

- **Primary Engineer**: [Your contact information]
- **Database Administrator**: [DBA contact information]  
- **Operations Team**: [Ops team contact information]
- **Management Escalation**: [Management contact information]

## Rollback Decision Matrix

### When to Rollback

- **Critical bugs** affecting core functionality
- **Security vulnerabilities** discovered in current version
- **Performance degradation** beyond acceptable thresholds
- **Data corruption** or integrity issues
- **Service unavailability** lasting more than agreed SLA

### When NOT to Rollback

- **Minor cosmetic issues** that don't affect functionality
- **Performance issues** that can be mitigated with configuration
- **Issues already being actively fixed** with ETA < 2 hours
- **User training issues** or misunderstandings

## Rollback Types

### 1. Emergency Rollback (< 15 minutes)

For critical issues requiring immediate action:

```bash
# Set environment
export ENVIRONMENT=production
export TARGET_VERSION=v1.2.3

# Emergency rollback (skips confirmations)
./docker/scripts/rollback-deployment.sh \
  --version $TARGET_VERSION \
  --environment $ENVIRONMENT \
  --force \
  --no-backup
```

**Use only when:**
- Service is completely down
- Data corruption is occurring
- Security breach is active

### 2. Standard Rollback (30-60 minutes)

For non-critical issues with time for proper procedure:

```bash
# Validate rollback target
./docker/scripts/validate-migration.sh rollback $TARGET_VERSION

# Execute rollback with full safety checks
./docker/scripts/rollback-deployment.sh \
  --version $TARGET_VERSION \
  --environment $ENVIRONMENT
```

### 3. Planned Rollback (During maintenance window)

For issues discovered during planned maintenance:

```bash
# Full validation and testing
./docker/scripts/validate-migration.sh rollback $TARGET_VERSION
./docker/scripts/validate-deployment.sh

# Execute rollback
./docker/scripts/rollback-deployment.sh \
  --version $TARGET_VERSION \
  --environment $ENVIRONMENT
```

## Detailed Rollback Process

### Phase 1: Assessment (5-10 minutes)

1. **Identify the Issue**
   - Document the problem clearly
   - Determine severity and impact
   - Identify affected users/services

2. **Determine Target Version**
   ```bash
   # List available versions
   ./docker/scripts/manage-versions.sh list
   
   # Show current version
   ./docker/scripts/manage-versions.sh current
   
   # Get info about target version
   ./docker/scripts/manage-versions.sh info v1.2.3
   ```

3. **Validate Rollback Safety**
   ```bash
   ./docker/scripts/validate-migration.sh rollback $TARGET_VERSION
   ```

### Phase 2: Preparation (10-15 minutes)

1. **Notify Stakeholders**
   - Send alert to monitoring channels
   - Notify users of potential service interruption
   - Alert operations team

2. **Validate Prerequisites**
   ```bash
   # Check system health
   ./docker/scripts/health-check.sh
   
   # Validate database state
   ./docker/scripts/validate-migration.sh state
   
   # Check backup availability
   ls -la /opt/emuses/backups/
   ```

3. **Create Rollback Plan**
   - Document current state
   - Plan communication timeline
   - Prepare rollback command

### Phase 3: Execution (15-30 minutes)

1. **Execute Rollback**
   ```bash
   # Standard rollback with backup
   ./docker/scripts/rollback-deployment.sh \
     --version $TARGET_VERSION \
     --environment $ENVIRONMENT
   ```

2. **Monitor Progress**
   - Watch rollback script output
   - Monitor system resources
   - Check application logs

3. **Validate Success**
   ```bash
   # Verify deployment health
   ./docker/scripts/validate-deployment.sh
   
   # Check specific functionality
   curl -f http://localhost/api/v1/registry/health
   ```

### Phase 4: Verification (10-15 minutes)

1. **Functional Testing**
   - Test critical user workflows
   - Verify API endpoints
   - Check database connectivity
   - Validate model registry functionality

2. **Performance Validation**
   ```bash
   ./docker/scripts/validate-performance.sh
   ```

3. **Data Integrity Check**
   ```bash
   ./docker/scripts/validate-migration.sh state
   ```

### Phase 5: Recovery (15-30 minutes)

1. **Post-Rollback Communication**
   - Notify users service is restored
   - Update status page
   - Send all-clear to operations

2. **Incident Documentation**
   - Record rollback details
   - Document lessons learned
   - Update procedures if needed

3. **Plan Forward Fix**
   - Identify root cause
   - Plan proper fix
   - Schedule next deployment

## Database Rollback Considerations

### Migration Rollbacks

```bash
# Check current migration status
./docker/scripts/migrate-database.sh current

# Rollback to specific migration
./docker/scripts/migrate-database.sh backward --target abc123

# Validate database state
./docker/scripts/validate-migration.sh state
```

### Data Loss Scenarios

**High Risk Operations:**
- Column deletions
- Table drops
- Data type changes
- Constraint additions

**Medium Risk Operations:**
- Adding columns with defaults
- Index changes
- View modifications

**Low Risk Operations:**
- Adding new tables
- Adding nullable columns
- Creating indexes

## Monitoring During Rollback

### Key Metrics to Watch

1. **Response Times**
   - API endpoint latency
   - Database query performance
   - User interface responsiveness

2. **Error Rates**
   - HTTP 5xx errors
   - Database connection errors
   - Application exceptions

3. **Resource Utilization**
   - CPU usage
   - Memory consumption
   - Disk I/O
   - Network traffic

### Alerting

Ensure monitoring systems are configured to alert on:
- Service health changes
- Performance degradation
- Error rate spikes
- Resource exhaustion

## Rollback Validation Checklist

After completing rollback, verify:

- [ ] All services are running
- [ ] Health checks pass
- [ ] API endpoints respond correctly
- [ ] Database connectivity verified
- [ ] User authentication works
- [ ] Model registry functionality operational
- [ ] Monitoring systems show green status
- [ ] Performance within acceptable ranges
- [ ] No data corruption detected

## Common Issues and Solutions

### Rollback Fails to Start Services

```bash
# Check Docker status
docker ps -a

# Check logs
docker-compose -f docker-compose.production.yml logs

# Manual service restart
docker-compose -f docker-compose.production.yml up -d
```

### Database Migration Issues

```bash
# Check migration state
./docker/scripts/migrate-database.sh current

# Manual migration rollback
./docker/scripts/migrate-database.sh backward --target $PREVIOUS_MIGRATION

# Validate database
./docker/scripts/validate-migration.sh state
```

### Version Mismatch Issues

```bash
# Verify git state
git status
git describe --tags

# Force checkout if needed
git checkout --force $TARGET_VERSION

# Rebuild images
docker-compose build --no-cache
```

## Post-Rollback Actions

1. **Immediate (0-1 hour)**
   - Verify system stability
   - Monitor error rates
   - Respond to user reports

2. **Short-term (1-24 hours)**
   - Complete incident report
   - Plan fix for original issue
   - Review rollback effectiveness

3. **Long-term (1-7 days)**
   - Implement permanent fix
   - Update procedures based on lessons learned
   - Conduct post-mortem review

## Contact Information

For rollback assistance:
- **24/7 Operations**: [Phone number]
- **Emergency Escalation**: [Phone number]
- **Engineering Lead**: [Email/Phone]

## Related Documentation

- [ROLLBACK_CHECKLIST.md](./ROLLBACK_CHECKLIST.md)
- [Health Check Documentation](../monitoring/health-checks.md)
- [Database Migration Guide](../database/migration-procedures.md)