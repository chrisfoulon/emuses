# EMUSES Deployment Scenarios Guide

## 🎯 **Understanding EMUSES Architecture**

EMUSES is designed to work in **three main scenarios**, each with different authentication, networking, and administration requirements. Think of it as a Swiss Army knife that adapts to your specific research environment.

### **Core Components Overview**

1. **FastAPI Service**: The web server that handles requests and responses
2. **Authentication System**: JWT tokens that identify users (like digital ID cards)
3. **Database**: Stores user accounts, jobs, and results
4. **CLI Tool**: Command-line interface that talks to the FastAPI service
5. **Admin Interface**: Special commands for managing users and system health

---

## 📱 **Scenario 1: Solo Researcher (Local Mode)**

**Who**: Individual researchers, students, small labs  
**Where**: Personal laptops, workstations, development environments  
**Authentication**: None required  
**Network**: Everything runs locally  

### **How It Works**
```
Your Computer:
┌─────────────────────────────────────┐
│  CLI Command: emuses full data.csv  │
│              ↓                      │
│  Auto-starts FastAPI service       │
│  (http://localhost:8000)            │
│              ↓                      │
│  Processes your data locally        │
│              ↓                      │
│  Results saved to local folder      │
└─────────────────────────────────────┘
```

### **Setup Instructions**

**1. Installation (one-time)**
```bash
# Install EMUSES
pip install emuses

# That's it! No database, no user accounts needed
```

**2. Daily Usage**
```bash
# Just run your analysis - everything else is automatic
emuses full mydata.csv --scores scores.csv

# The system:
# - Automatically starts a local web service
# - Processes your data
# - Saves results to your specified folder
# - Shuts down when done
```

**3. What Happens Behind the Scenes**
- EMUSES detects it's in "local mode" (no special environment variables)
- Starts FastAPI service on an available port (8000, 8001, etc.)
- No authentication required - you're the only user
- No database needed - results go directly to files
- Service automatically stops when CLI command finishes

### **When to Use This**
- ✅ Learning EMUSES
- ✅ Small datasets (< 1GB)
- ✅ Personal research projects
- ✅ Quick experiments and prototyping
- ✅ No need to share data or collaborate

---

## 🏢 **Scenario 2: Research Lab (Multi-User Mode)**

**Who**: Research labs, small teams, shared workstations  
**Where**: Lab servers, shared compute resources  
**Authentication**: Required (user accounts with passwords)  
**Network**: Shared server accessible to lab members  

### **How It Works**
```
Lab Network:
┌─────────────────┐    ┌─────────────────────────────────┐
│ Researcher A    │    │ Shared Lab Server               │
│ (laptop)        │───▶│ ┌─────────────────────────────┐ │
│ emuses command  │    │ │ FastAPI Service             │ │
└─────────────────┘    │ │ (http://lab-server:8000)    │ │
                       │ │ - User Authentication       │ │
┌─────────────────┐    │ │ - Job Queue Management      │ │
│ Researcher B    │    │ │ - Individual Workspaces     │ │
│ (workstation)   │───▶│ └─────────────────────────────┘ │
│ emuses command  │    │ ┌─────────────────────────────┐ │
└─────────────────┘    │ │ Database (PostgreSQL)       │ │
                       │ │ - User accounts             │ │
┌─────────────────┐    │ │ - Job history               │ │
│ Student C       │    │ │ - Results storage           │ │
│ (remote)        │───▶│ └─────────────────────────────┘ │
│ emuses command  │    └─────────────────────────────────┘
└─────────────────┘
```

### **Setup Instructions**

**1. Server Setup (Lab Administrator)**

**Install and Configure Database:**
```bash
# On lab server (Ubuntu example)
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Create EMUSES database
sudo -u postgres createdb emuses_lab
sudo -u postgres createuser emuses_admin -P  # Set password when prompted

# Grant permissions
sudo -u postgres psql
GRANT ALL PRIVILEGES ON DATABASE emuses_lab TO emuses_admin;
\q
```

**Install EMUSES:**
```bash
# Install EMUSES on server
pip install emuses

# Set up environment
export EMUSES_DEPLOYMENT_MODE=multi_user
export DATABASE_URL="postgresql://emuses_admin:your_password@localhost/emuses_lab"
export EMUSES_JWT_SECRET="your-very-secure-secret-key-here"

# Run database migrations
alembic upgrade head
```

**Start the Service:**
```bash
# Start EMUSES service (keeps running)
python -m uvicorn emuses.api.main:create_app --factory --host 0.0.0.0 --port 8000

# Service is now available at http://lab-server:8000
```

**2. Create User Accounts (Lab Administrator)**

```bash
# Create admin account (yourself)
python create_admin_user.py  # Creates admin@lab.edu

# Get admin token
curl -X POST "http://lab-server:8000/auth/jwt/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin@lab.edu&password=admin123"

# Export the token for admin commands
export EMUSES_ADMIN_TOKEN="eyJ..."  # Use token from above

# Create accounts for lab members
python -m emuses.cli admin add-user researcher1@university.edu -p SecurePass123 -o "Your Lab Name"
python -m emuses.cli admin add-user student1@university.edu -p StudentPass456 -o "Your Lab Name"
python -m emuses.cli admin add-user postdoc1@university.edu -p PostdocPass789 -o "Your Lab Name"

# Set quotas (optional)
python -m emuses.cli admin set-quota researcher1@university.edu storage_gb 100
python -m emuses.cli admin set-quota student1@university.edu storage_gb 25
python -m emuses.cli admin set-quota researcher1@university.edu concurrent_jobs 5
python -m emuses.cli admin set-quota student1@university.edu concurrent_jobs 2
```

**3. User Setup (Each Lab Member)**

**Install EMUSES on their machine:**
```bash
pip install emuses
```

**Configure to use lab server:**
```bash
# Set up environment to use lab server
export EMUSES_DEPLOYMENT_MODE=multi_user
export EMUSES_SERVICE_URL="http://lab-server:8000"

# Or create a config file they can source
echo 'export EMUSES_DEPLOYMENT_MODE=multi_user' >> ~/.emuses_config
echo 'export EMUSES_SERVICE_URL="http://lab-server:8000"' >> ~/.emuses_config
```

**4. Daily Usage (Lab Members)**

**First time - get authentication token:**
```bash
# Login to get token
curl -X POST "http://lab-server:8000/auth/jwt/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=researcher1@university.edu&password=SecurePass123"

# Save token for CLI use
export EMUSES_USER_TOKEN="eyJ..."  # Use token from login response
```

**Run analysis:**
```bash
# Run EMUSES with authentication
emuses full mydata.csv --service http://lab-server:8000 --token $EMUSES_USER_TOKEN

# Or if environment variables are set:
emuses full mydata.csv
```

### **What Happens Behind the Scenes**
1. **Authentication**: User credentials verified against database
2. **Workspace Isolation**: Each user gets their own data directory
3. **Job Queuing**: Multiple users can submit jobs simultaneously
4. **Resource Management**: Quotas prevent any user from overwhelming the system
5. **Data Security**: Users can only see their own data and results

### **When to Use This**
- ✅ Research labs with 3-20 users
- ✅ Shared compute resources
- ✅ Need user isolation and quotas
- ✅ Want job history and result tracking
- ✅ Medium to large datasets (1GB - 100GB)

---

## 🌐 **Scenario 3: Enterprise/Production (Production Mode)**

**Who**: Large institutions, multi-lab deployments, cloud environments  
**Where**: Production servers, cloud platforms, enterprise infrastructure  
**Authentication**: Strict (required for all operations)  
**Network**: Internet-accessible, high availability  

### **How It Works**
```
Enterprise Network:
                     ┌─── Load Balancer ────┐
Internet             │   (nginx/HAProxy)    │
   │                 └──────────┬───────────┘
   │                            │
   ▼                            ▼
┌─────────────────┐    ┌─────────────────────────────────┐
│ Remote          │    │ Production Server Cluster       │
│ Researchers     │───▶│ ┌─────────────────────────────┐ │
│ (worldwide)     │    │ │ FastAPI Service (HA)        │ │
└─────────────────┘    │ │ - Strict Authentication     │ │
                       │ │ - Role-based Access         │ │
┌─────────────────┐    │ │ - API Rate Limiting         │ │
│ Institution A   │    │ │ - Audit Logging             │ │
│ Lab Network     │───▶│ └─────────────────────────────┘ │
└─────────────────┘    │ ┌─────────────────────────────┐ │
                       │ │ Database Cluster            │ │
┌─────────────────┐    │ │ - PostgreSQL Primary/Replica│ │
│ Institution B   │    │ │ - Automated Backups         │ │
│ Cloud VMs       │───▶│ │ - Performance Monitoring    │ │
└─────────────────┘    │ └─────────────────────────────┘ │
                       │ ┌─────────────────────────────┐ │
                       │ │ Background Workers          │ │
                       │ │ - Redis Task Queue          │ │
                       │ │ - Celery Workers            │ │
                       │ │ - Auto-scaling              │ │
                       │ └─────────────────────────────┘ │
                       └─────────────────────────────────┘
```

### **Setup Instructions**

**1. Infrastructure Setup (DevOps/IT Team)**

**Docker Compose Deployment:**
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  emuses-api:
    image: emuses/api:latest
    environment:
      - EMUSES_DEPLOYMENT_MODE=production
      - DATABASE_URL=postgresql://emuses:${DB_PASSWORD}@postgres:5432/emuses
      - EMUSES_JWT_SECRET=${JWT_SECRET}
      - REDIS_URL=redis://redis:6379
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    volumes:
      - ./data:/app/data
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=emuses
      - POSTGRES_USER=emuses
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - emuses-api
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

**Environment Variables (.env file):**
```bash
DB_PASSWORD=your-very-secure-database-password
JWT_SECRET=your-extremely-secure-jwt-secret-key
EMUSES_DEPLOYMENT_MODE=production
```

**Deploy:**
```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Check health
curl https://emuses.your-institution.edu/health
```

**2. Initial Administration (System Administrator)**

**Create Super Admin:**
```python
# create_super_admin.py
import asyncio
from emuses.multi_user_service.auth import UserManager, get_user_db
from emuses.multi_user_service.database import get_async_session

async def create_super_admin():
    session = await anext(get_async_session())
    user_db = await anext(get_user_db(session))
    user_manager = UserManager(user_db)
    
    admin = await user_manager.create({
        "email": "sysadmin@your-institution.edu",
        "password": "SecureAdminPassword123!",
        "is_superuser": True,
        "is_verified": True,
        "organization": "System Administration",
        "role": "admin"
    })
    print(f"Super admin created: {admin.email}")
    await session.close()

asyncio.run(create_super_admin())
```

**3. Organization Setup (Institution Administrators)**

**Create Lab Administrators:**
```bash
# Get super admin token
export EMUSES_ADMIN_TOKEN="..."  # From login

# Create lab admins
python -m emuses.cli admin add-user lab1-admin@institution.edu -p LabAdminPass123 -o "Neuroscience Lab" --role admin
python -m emuses.cli admin add-user lab2-admin@institution.edu -p LabAdminPass456 -o "Computer Science Lab" --role admin

# Set institutional quotas
python -m emuses.cli admin set-quota lab1-admin@institution.edu storage_gb 1000
python -m emuses.cli admin set-quota lab1-admin@institution.edu concurrent_jobs 20
```

**4. Lab Setup (Lab Administrators)**

**Each lab admin creates their users:**
```bash
# Lab admin logs in
export EMUSES_ADMIN_TOKEN="..."  # Lab admin token

# Create lab members
python -m emuses.cli admin add-user researcher1@institution.edu -p ResearchPass123 -o "Neuroscience Lab"
python -m emuses.cli admin add-user postdoc1@institution.edu -p PostdocPass456 -o "Neuroscience Lab"
python -m emuses.cli admin add-user student1@institution.edu -p StudentPass789 -o "Neuroscience Lab"

# Set appropriate quotas
python -m emuses.cli admin set-quota researcher1@institution.edu storage_gb 200
python -m emuses.cli admin set-quota researcher1@institution.edu concurrent_jobs 10
python -m emuses.cli admin set-quota student1@institution.edu storage_gb 50
python -m emuses.cli admin set-quota student1@institution.edu concurrent_jobs 3
```

**5. User Setup (Researchers)**

**Install EMUSES:**
```bash
pip install emuses
```

**Configure for production service:**
```bash
# Set up for production service
export EMUSES_DEPLOYMENT_MODE=production
export EMUSES_SERVICE_URL="https://emuses.your-institution.edu"

# Or add to shell profile
echo 'export EMUSES_DEPLOYMENT_MODE=production' >> ~/.bashrc
echo 'export EMUSES_SERVICE_URL="https://emuses.your-institution.edu"' >> ~/.bashrc
```

**6. Daily Usage (Researchers)**

**Authentication and job submission:**
```bash
# Login (get fresh token)
curl -X POST "https://emuses.your-institution.edu/auth/jwt/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=researcher1@institution.edu&password=ResearchPass123"

# Save token
export EMUSES_USER_TOKEN="eyJ..."

# Submit job
emuses full large_dataset.csv --service https://emuses.your-institution.edu --token $EMUSES_USER_TOKEN

# Check job status
emuses status job-id-here --service https://emuses.your-institution.edu --token $EMUSES_USER_TOKEN
```

### **What Happens Behind the Scenes**
1. **High Availability**: Multiple server instances handle requests
2. **Security**: All operations require valid JWT tokens
3. **Monitoring**: System health and performance continuously tracked
4. **Scalability**: Background workers auto-scale based on job queue size
5. **Audit Trail**: All user actions logged for compliance
6. **Data Protection**: Enterprise-grade backup and recovery

### **When to Use This**
- ✅ Universities with multiple departments
- ✅ Multi-institutional collaborations
- ✅ Cloud deployments (AWS, Azure, GCP)
- ✅ Need compliance and audit trails
- ✅ Large datasets (100GB+)
- ✅ High availability requirements

---

## 🔑 **Authentication System Explained**

### **How JWT Tokens Work**
Think of JWT tokens like temporary ID badges:

1. **Login**: User provides email/password
2. **Verification**: System checks credentials against database
3. **Token Creation**: System creates a signed "badge" (JWT token)
4. **Token Usage**: User includes badge with every request
5. **Token Validation**: System verifies badge is authentic and not expired

```
User Login Flow:
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ 1. User enters  │───▶│ 2. System       │───▶│ 3. System       │
│ email/password  │    │ checks database │    │ creates JWT     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
┌─────────────────┐    ┌─────────────────┐            ▼
│ 5. User can now │◀───│ 4. JWT token    │    
│ make requests   │    │ returned to user│    
└─────────────────┘    └─────────────────┘    
```

### **Role-Based Access**
- **User**: Can manage their own data and jobs
- **Admin**: Can manage users in their organization
- **Super Admin**: Can manage entire system

### **Token Expiration and Renewal**
- Tokens expire after 24 hours (configurable)
- Users must login again to get fresh tokens
- Prevents unauthorized access if token is compromised

---

## 🚀 **Quick Start Decision Tree**

**Use this to decide which scenario fits your needs:**

```
Are you working alone or with 1-2 people?
├─ YES → Use Local Mode (Scenario 1)
└─ NO
   │
   Do you have a dedicated lab server?
   ├─ YES → Use Multi-User Mode (Scenario 2)
   └─ NO
      │
      Do you need internet access or have >20 users?
      ├─ YES → Use Production Mode (Scenario 3)
      └─ NO → Start with Multi-User Mode, upgrade later
```

## 🔧 **Migration Between Scenarios**

**From Local → Multi-User:**
1. Set up shared server with database
2. Export existing results
3. Create user accounts
4. Import results to user workspaces

**From Multi-User → Production:**
1. Set up production infrastructure
2. Backup database
3. Configure high availability
4. Update user configurations

## 📚 **Common Administrative Tasks**

### **Check System Health**
```bash
python -m emuses.cli admin system-status --detailed
```

### **Monitor User Activity**
```bash
python -m emuses.cli admin list-users --limit 50
```

### **Adjust User Quotas**
```bash
python -m emuses.cli admin set-quota user@example.com storage_gb 200
python -m emuses.cli admin set-quota user@example.com concurrent_jobs 5
```

### **Cancel Stuck Jobs**
```bash
python -m emuses.cli admin cancel-job job-id-here
```

This guide should give you a clear understanding of how EMUSES adapts to different deployment scenarios and how the FastAPI authentication system works in each case!