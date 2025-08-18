# EMUSES Quick Setup Reference

## 🚀 **Choose Your Setup**

### **Local Mode (Solo Researcher)**
```bash
# Install and use immediately
pip install emuses
emuses full mydata.csv
# That's it! No authentication needed.
```

### **Multi-User Mode (Lab Server)**
```bash
# 1. Server Setup (one-time)
export EMUSES_DEPLOYMENT_MODE=multi_user
export DATABASE_URL="postgresql://user:pass@localhost/emuses"
export EMUSES_JWT_SECRET="your-secret-key"
alembic upgrade head
python -m uvicorn emuses.api.main:create_app --factory --host 0.0.0.0 --port 8000

# 2. Create Admin Account (one-time)
python create_admin_user.py
export EMUSES_ADMIN_TOKEN="your-admin-jwt-token"

# 3. Add Users
python -m emuses.cli admin add-user researcher@uni.edu -p SecurePass123

# 4. Users Connect
emuses full data.csv --service http://lab-server:8000 --token user-jwt-token
```

### **Production Mode (Enterprise)**
```bash
# 1. Docker Deployment
docker-compose -f docker-compose.prod.yml up -d

# 2. Same user management as Multi-User Mode
# 3. Users connect to https://emuses.your-domain.com
```

## 🔑 **Authentication Cheat Sheet**

### **Get JWT Token**
```bash
curl -X POST "http://server:8000/auth/jwt/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=user@example.com&password=password123"
```

### **Use Token with CLI**
```bash
export EMUSES_USER_TOKEN="eyJ..."
emuses full data.csv --service http://server:8000 --token $EMUSES_USER_TOKEN
```

## 👥 **Common Admin Commands**

```bash
# Create user
python -m emuses.cli admin add-user user@example.com -p Password123

# Set quotas  
python -m emuses.cli admin set-quota user@example.com storage_gb 100
python -m emuses.cli admin set-quota user@example.com concurrent_jobs 5

# List users
python -m emuses.cli admin list-users

# Check system
python -m emuses.cli admin system-status --detailed

# Cancel job
python -m emuses.cli admin cancel-job job-id
```

## 🔧 **Environment Variables Reference**

| Variable | Local Mode | Multi-User Mode | Production Mode |
|----------|------------|-----------------|-----------------|
| `EMUSES_DEPLOYMENT_MODE` | Not needed | `multi_user` | `production` |
| `DATABASE_URL` | Not needed | Required | Required |
| `EMUSES_JWT_SECRET` | Not needed | Required | Required |
| `EMUSES_SERVICE_URL` | Not needed | Server URL | Server URL |
| `EMUSES_ADMIN_TOKEN` | Not needed | Admin JWT | Admin JWT |
| `EMUSES_USER_TOKEN` | Not needed | User JWT | User JWT |

## 🆘 **Troubleshooting**

| Problem | Solution |
|---------|----------|
| "Connection refused" | Check if API service is running on correct port |
| "401 Unauthorized" | Get fresh JWT token with login command |
| "Import error" | Install missing dependencies: `pip install fastapi sqlalchemy alembic` |
| "Database error" | Check DATABASE_URL and run `alembic upgrade head` |
| "No users found" | Create admin user first, then regular users |

## 📋 **Migration Checklist**

### **Local → Multi-User**
- [ ] Set up shared server
- [ ] Install PostgreSQL
- [ ] Run database migrations
- [ ] Create admin account
- [ ] Add user accounts
- [ ] Update user CLI configurations

### **Multi-User → Production**
- [ ] Set up production infrastructure (Docker/Kubernetes)
- [ ] Configure load balancer and SSL
- [ ] Backup and migrate database
- [ ] Update DNS and user configurations
- [ ] Set up monitoring and logging
- [ ] Test disaster recovery procedures

This reference should give you everything you need for quick setup and daily administration!