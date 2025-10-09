# EMUSES Admin Commands - Complete Usage Guide

This guide provides comprehensive usage examples, troubleshooting steps, and best practices for EMUSES admin commands in multi-user deployments.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication Setup](#authentication-setup)
3. [Enterprise Security](#enterprise-security)
4. [Command Usage Examples](#command-usage-examples)
5. [Common Workflows](#common-workflows)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)
8. [Emergency Procedures](#emergency-procedures)

## Getting Started

The EMUSES admin commands provide a comprehensive CLI interface for managing users, quotas, and system health in multi-user EMUSES deployments.

### Prerequisites

- EMUSES service running in multi-user or production mode
- Admin authentication token
- Appropriate network access to the EMUSES service

### Basic Command Structure

```bash
python -m emuses.cli admin <command> [arguments] [options]
```

### Available Commands

| Command | Purpose | Requires Auth |
|---------|---------|---------------|
| `help` | Display comprehensive help | No |
| `add-user` | Create new system user | Yes |
| `list-users` | Display all users | Yes |
| `set-quota` | Adjust user quotas | Yes |
| `system-status` | Monitor system health | Yes |
| `cancel-job` | Cancel stuck jobs | Yes |

## Authentication Setup

### Environment Variable (Recommended)

```bash
# Set admin token globally
export EMUSES_ADMIN_TOKEN="your-admin-token-here"

# Set service URL if not default
export EMUSES_SERVICE_URL="https://emuses.your-institution.edu"
```

### Command-Line Options

```bash
# Specify token per command
python -m emuses.cli admin list-users --token your-admin-token-here

# Specify custom service URL
python -m emuses.cli admin system-status --service-url http://localhost:8000 --token your-token
```

### Token Management

```bash
# Test token validity
python -m emuses.cli admin system-status

# If token is expired, you'll see:
# ❌ Service error: 401 Unauthorized
```

## Enterprise Security

EMUSES supports enterprise-grade security with HashiCorp Vault integration for secure secret management, audit trails, and compliance requirements.

### Vault Integration Overview

EMUSES provides multi-source secret management with the following priority hierarchy:
1. **HashiCorp Vault** (enterprise environments)
2. **Secure file** (production deployments)  
3. **Environment variable** (development/compatibility)
4. **Development default** (local development only)

**📚 Comprehensive Guides:**
- **[Vault Integration Guide](vault-integration-guide.md)** - Complete setup and configuration
- **[Enterprise Deployment Patterns](enterprise-deployment-patterns.md)** - Production architectures
- **[Security & Compliance Guide](security-compliance-guide.md)** - SOC 2, HIPAA, GDPR compliance

### Quick Vault Setup

```bash
# 1. Configure Vault access
export VAULT_ADDR="https://vault.company.com:8200"
export VAULT_TOKEN="your-vault-token"

# 2. Store EMUSES secrets in Vault
vault kv put secret/emuses \
  jwt_secret="$(openssl rand -base64 32)" \
  admin_password="SecureAdminPass123"

# 3. Verify Vault integration
python -m emuses.cli admin system-status
# Should show: "JWT secret loaded from HashiCorp Vault"

# 4. Start multi-user service with Vault
export EMUSES_DEPLOYMENT_MODE="multi_user"
python -m emuses.api.main --host 0.0.0.0 --port 8000
```

### Enhanced Security Commands

With Vault integration, admin commands automatically benefit from enterprise security:

```bash
# Commands work seamlessly with Vault-secured secrets
python -m emuses.cli admin add-user researcher@company.com --password SecurePass123
python -m emuses.cli admin list-users
python -m emuses.cli admin system-status --detailed

# Secret sources are logged for audit compliance
# Log output shows: "JWT secret loaded from HashiCorp Vault"
```

## Command Usage Examples

### User Management

#### Creating Users

```bash
# Basic user creation
python -m emuses.cli admin add-user researcher@university.edu --password SecurePass123

# Custom organization
python -m emuses.cli admin add-user postdoc@lab.edu -p MyPass456 -o "Neuroscience Lab"

# Create inactive user (for later activation)
python -m emuses.cli admin add-user intern@college.edu -p TempPass789 --inactive

# Create unverified user (requires email verification)
python -m emuses.cli admin add-user newuser@example.com -p Pass123 --unverified
```

#### Listing Users

```bash
# Default listing (10 users)
python -m emuses.cli admin list-users

# Extended listing
python -m emuses.cli admin list-users --limit 50

# Pagination for large systems
python -m emuses.cli admin list-users --skip 20 --limit 10

# For very large systems (1000+ users)
python -m emuses.cli admin list-users --skip 100 --limit 25
```

### Quota Management

#### Setting Storage Quotas

```bash
# Standard researcher allocation
python -m emuses.cli admin set-quota researcher@uni.edu storage_gb 50

# High-capacity user
python -m emuses.cli admin set-quota senior-researcher@uni.edu storage_gb 200

# Limited allocation for students
python -m emuses.cli admin set-quota student@uni.edu storage_gb 10
```

#### Managing Concurrent Jobs

```bash
# Standard allocation
python -m emuses.cli admin set-quota user@example.com concurrent_jobs 2

# Power user allocation
python -m emuses.cli admin set-quota poweruser@lab.edu concurrent_jobs 5

# Limited for shared systems
python -m emuses.cli admin set-quota intern@college.edu concurrent_jobs 1
```

#### Compute Hour Limits

```bash
# Monthly limit for researchers
python -m emuses.cli admin set-quota researcher@uni.edu compute_hours 500

# Generous allocation for long-running experiments
python -m emuses.cli admin set-quota phd-student@uni.edu compute_hours 1000

# Conservative limit for new users
python -m emuses.cli admin set-quota newuser@uni.edu compute_hours 100
```

### System Monitoring

#### Basic System Status

```bash
# Quick health check
python -m emuses.cli admin system-status

# Expected output:
# System Status: HEALTHY
# Components: ✅ database, ✅ api, ✅ background_tasks
# Metrics: total_users: 45, active_jobs: 12
```

#### Detailed System Status

```bash
# Comprehensive diagnostic
python -m emuses.cli admin system-status --detailed

# Includes:
# - Health check details
# - Job queue statistics
# - Resource utilization
```

#### Continuous Monitoring

```bash
# Monitor every 30 seconds
watch -n 30 'python -m emuses.cli admin system-status --detailed'

# Monitor with timestamp
while true; do
  echo "=== $(date) ==="
  python -m emuses.cli admin system-status
  sleep 60
done
```

### Job Management

#### Cancelling Jobs

```bash
# Get job ID from system status
python -m emuses.cli admin system-status --detailed

# Cancel with confirmation
python -m emuses.cli admin cancel-job 12345678-1234-1234-1234-123456789abc

# Emergency force cancellation (no confirmation)
python -m emuses.cli admin cancel-job abcd1234-5678-90ef-ghij-klmnopqrstuv --force
```

## Common Workflows

### New User Onboarding

```bash
# 1. Create user account
python -m emuses.cli admin add-user newuser@institution.edu -p TemporaryPass123 -o "Research Department"

# 2. Set appropriate quotas
python -m emuses.cli admin set-quota newuser@institution.edu storage_gb 25
python -m emuses.cli admin set-quota newuser@institution.edu concurrent_jobs 2
python -m emuses.cli admin set-quota newuser@institution.edu compute_hours 200

# 3. Verify user creation
python -m emuses.cli admin list-users --limit 5

# 4. Communicate credentials to user
echo "User created: newuser@institution.edu"
echo "Temporary password: TemporaryPass123"
echo "Please change password on first login"
```

### System Health Monitoring

```bash
# Daily health check routine
echo "=== Daily EMUSES Health Check ==="
python -m emuses.cli admin system-status --detailed

# Check for stuck jobs
if [[ $(python -m emuses.cli admin system-status | grep -c "running_jobs: [5-9]") -gt 0 ]]; then
  echo "WARNING: Many running jobs detected"
  python -m emuses.cli admin system-status --detailed
fi

# Check user activity
python -m emuses.cli admin list-users --limit 50 | grep -c "✅.*✅.*❌"
echo "Active users: $?"
```

### Quota Adjustment Campaign

```bash
# Bulk quota updates for user group
USERS=("user1@uni.edu" "user2@uni.edu" "user3@uni.edu")
NEW_STORAGE=100

for user in "${USERS[@]}"; do
  echo "Updating quota for $user..."
  python -m emuses.cli admin set-quota "$user" storage_gb $NEW_STORAGE
  if [ $? -eq 0 ]; then
    echo "✅ Success: $user"
  else
    echo "❌ Failed: $user"
  fi
done
```

### Emergency System Maintenance

```bash
# 1. Check system status
python -m emuses.cli admin system-status --detailed

# 2. Cancel all running jobs (if necessary)
# First get job IDs
python -m emuses.cli admin system-status --detailed | grep -A 20 "Job Queues"

# Cancel individual jobs (get IDs from status output)
# python -m emuses.cli admin cancel-job <job-id> --force

# 3. Verify system is clear
python -m emuses.cli admin system-status

# 4. Proceed with maintenance...
```

## Troubleshooting

### Authentication Issues

#### Problem: 401 Unauthorized

```bash
# Check token validity
python -m emuses.cli admin system-status

# Solutions:
# 1. Verify token is set correctly
echo $EMUSES_ADMIN_TOKEN

# 2. Check token format (should be JWT)
# 3. Verify you have admin privileges
# 4. Check token expiration
```

#### Problem: 403 Forbidden

```bash
# Your token is valid but lacks admin privileges
# Solutions:
# 1. Contact system administrator
# 2. Verify superuser status in database
# 3. Use correct admin token (not user token)
```

### Connection Issues

#### Problem: Connection refused

```bash
# Check service availability
curl -I http://localhost:8000/health

# Solutions:
# 1. Verify service is running
# 2. Check correct service URL
python -m emuses.cli admin system-status --service-url http://correct-host:8000

# 3. Check firewall rules
# 4. Verify network connectivity
```

#### Problem: Timeout errors

```bash
# Solutions:
# 1. Check system load
python -m emuses.cli admin system-status --detailed

# 2. Increase timeout (if supported)
# 3. Try during off-peak hours
# 4. Check database connectivity
```

### Command-Specific Issues

#### User Creation Failures

```bash
# Problem: Email already exists
# Solution: Check existing users first
python -m emuses.cli admin list-users | grep "user@example.com"

# Problem: Invalid email format
# Solution: Verify email format
echo "user@example.com" | grep -E '^[^@]+@[^@]+\.[^@]+$'

# Problem: Weak password
# Solution: Use stronger password (8+ chars, mixed case, numbers)
```

#### Quota Setting Failures

```bash
# Problem: Invalid quota type
# Valid types: storage_gb, concurrent_jobs, compute_hours
python -m emuses.cli admin set-quota user@example.com storage_gb 50  # ✅ Correct
python -m emuses.cli admin set-quota user@example.com disk_space 50  # ❌ Invalid

# Problem: User not found
# Solution: Verify user exists
python -m emuses.cli admin list-users | grep "user@example.com"
```

#### Job Cancellation Issues

```bash
# Problem: Job not found
# Solution: Verify job ID
python -m emuses.cli admin system-status --detailed | grep -A 10 "Job Queues"

# Problem: Job already completed
# Solution: Check job status first
python -m emuses.cli admin system-status --detailed
```

### System Performance Issues

#### High Load

```bash
# Diagnosis
python -m emuses.cli admin system-status --detailed

# Look for:
# - High number of running jobs
# - Database connection issues
# - Resource exhaustion

# Solutions:
# 1. Cancel non-essential jobs
# 2. Reduce concurrent job limits
# 3. Check system resources
```

#### Database Issues

```bash
# Symptoms:
# - Slow responses
# - Connection timeouts
# - Internal server errors

# Diagnosis:
python -m emuses.cli admin system-status --detailed

# Solutions:
# 1. Check database server status
# 2. Review database logs
# 3. Consider database maintenance
```

## Best Practices

### Security

1. **Token Management**
   - Rotate admin tokens regularly
   - Store tokens securely (environment variables)
   - Never commit tokens to version control
   - Use separate tokens for different environments

2. **User Management**
   - Use strong default passwords
   - Require password changes on first login
   - Regularly audit user accounts
   - Deactivate unused accounts

3. **Quota Management**
   - Monitor usage before adjusting quotas
   - Set reasonable defaults for new users
   - Document quota policies
   - Review quotas periodically

### Operational

1. **Monitoring**
   - Perform daily health checks
   - Set up automated monitoring alerts
   - Track key metrics over time
   - Document incidents and resolutions

2. **Maintenance**
   - Schedule regular maintenance windows
   - Test admin commands in staging first
   - Keep backups before major changes
   - Document all administrative actions

3. **Communication**
   - Notify users of quota changes
   - Announce maintenance windows
   - Provide user documentation
   - Maintain clear escalation procedures

### Automation

1. **Scripting Common Tasks**
   ```bash
   #!/bin/bash
   # daily-health-check.sh
   
   echo "=== EMUSES Daily Health Check $(date) ==="
   python -m emuses.cli admin system-status --detailed > daily-status.log
   
   # Check for issues and alert if needed
   if grep -q "❌" daily-status.log; then
     echo "WARNING: System issues detected"
     # Send alert email/notification
   fi
   ```

2. **Bulk Operations**
   ```bash
   # bulk-quota-update.sh
   while IFS= read -r user; do
     python -m emuses.cli admin set-quota "$user" storage_gb 100
   done < user-list.txt
   ```

## Emergency Procedures

### System Down

1. **Immediate Response**
   ```bash
   # Check system status
   python -m emuses.cli admin system-status
   
   # If unresponsive, check service directly
   curl -I http://service-host:8000/health
   ```

2. **Escalation Steps**
   - Check infrastructure logs
   - Contact system administrators
   - Follow incident response procedures

### Resource Exhaustion

1. **Immediate Actions**
   ```bash
   # Check running jobs
   python -m emuses.cli admin system-status --detailed
   
   # Cancel non-essential jobs
   python -m emuses.cli admin cancel-job <job-id> --force
   ```

2. **Long-term Solutions**
   - Review and adjust quotas
   - Implement stricter resource limits
   - Consider infrastructure scaling

### Security Incidents

1. **Suspected Compromise**
   ```bash
   # Check for suspicious activity
   python -m emuses.cli admin list-users | grep -E "(suspicious|unknown)"
   
   # Disable suspicious accounts
   # (Note: This would require additional endpoints)
   ```

2. **Response Actions**
   - Revoke compromised tokens
   - Reset affected user passwords
   - Review access logs
   - Follow security incident procedures

---

## Getting Help

- Use `python -m emuses.cli admin help` for built-in comprehensive guidance
- Use `python -m emuses.cli admin <command> --help` for command-specific help
- Check system logs for detailed error information
- Contact your EMUSES system administrator for complex issues

---

*This guide covers EMUSES multi-user service administration. For single-user deployments, many admin commands are not required or available.*