# EMUSES Enterprise Deployment Patterns

**Production-ready deployment configurations for enterprise environments**

## **Essential Deployment Overview**

EMUSES supports multiple deployment patterns to meet enterprise requirements including high availability, security compliance, and scalability. This guide covers proven patterns for production deployments.

### Deployment Options

| Pattern | Use Case | Security Level | Complexity |
|---------|----------|----------------|------------|
| **Single Instance + Vault** | Small to medium teams | High | Low |
| **Load Balanced + Vault** | High availability | High | Medium |
| **Multi-Region + Vault** | Global organizations | Enterprise | High |
| **Kubernetes + Vault** | Container orchestration | Enterprise | High |

<details markdown="1">
<summary>🏢 **Enterprise Requirements Checklist**</summary>

Essential features for enterprise deployments:

- ✅ **Centralized Authentication**: LDAP, SAML, or OAuth integration
- ✅ **Secret Management**: HashiCorp Vault with audit trails
- ✅ **High Availability**: Load balancing and failover
- ✅ **Monitoring**: Metrics, logging, and alerting
- ✅ **Backup and Recovery**: Automated data protection
- ✅ **Compliance**: SOC 2, GDPR, HIPAA requirements
- ✅ **Network Security**: TLS, VPN, firewall rules
- ✅ **Resource Management**: Quotas, limits, scheduling

</details>

## **Pattern 1: Single Instance with Vault**

### Architecture Overview

Simple, secure deployment suitable for teams of 10-100 users.

```
[Users] → [Load Balancer] → [EMUSES Instance] → [PostgreSQL]
                                    ↓
                              [HashiCorp Vault]
```

<details markdown="1">
<summary>🚀 **Implementation Guide**</summary>

Complete setup for single-instance deployment:

```bash
# 1. Infrastructure Setup
# - 1 EMUSES server (4 CPU, 16GB RAM, 100GB SSD)
# - 1 PostgreSQL server (2 CPU, 8GB RAM, 500GB SSD)
# - 1 Vault server (2 CPU, 4GB RAM, 50GB SSD)
# - Load balancer (nginx, HAProxy, or cloud LB)

# 2. Vault Setup
vault server -config=vault.hcl &
vault operator init
vault operator unseal <key1> <key2> <key3>

# 3. PostgreSQL Setup
sudo -u postgres createdb emuses_production
sudo -u postgres createuser emuses_user

# 4. EMUSES Configuration
export VAULT_ADDR="https://vault.internal.company.com:8200"
export VAULT_TOKEN="production-token"
export DATABASE_URL="postgresql://emuses_user:password@db.internal:5432/emuses_production"
export EMUSES_DEPLOYMENT_MODE="multi_user"

# 5. Secret Management
vault kv put secret/emuses \
  jwt_secret="$(openssl rand -base64 32)" \
  postgres_password="SecurePassword123" \
  admin_password="AdminPassword456"

# 6. Start EMUSES
python -m emuses.api.main --host 0.0.0.0 --port 8000
```

**Capacity**: 10-100 concurrent users, 1000+ models, TB-scale data

</details>

<details markdown="1">
<summary>🔧 **Configuration Files**</summary>

Production configuration templates:

**vault.hcl**:
```hcl
storage "postgresql" {
  connection_url = "postgres://vault_user:password@vault-db:5432/vault?sslmode=require"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_cert_file = "/opt/vault/tls/cert.pem"
  tls_key_file  = "/opt/vault/tls/key.pem"
}

ui = true
log_level = "INFO"
api_addr = "https://vault.company.com:8200"
cluster_addr = "https://vault.company.com:8201"
```

**nginx.conf** (Load Balancer):
```nginx
upstream emuses_backend {
    server emuses1.internal.company.com:8000;
}

server {
    listen 443 ssl;
    server_name emuses.company.com;

    ssl_certificate /etc/ssl/certs/emuses.crt;
    ssl_certificate_key /etc/ssl/private/emuses.key;

    location / {
        proxy_pass http://emuses_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**docker-compose.yml**:
```yaml
version: '3.8'
services:
  emuses:
    image: emuses:production
    environment:
      - VAULT_ADDR=https://vault.company.com:8200
      - VAULT_TOKEN_FILE=/run/secrets/vault_token
      - DATABASE_URL=postgresql://emuses:password@postgres:5432/emuses
    secrets:
      - vault_token
    depends_on:
      - postgres

  postgres:
    image: postgres:14
    environment:
      - POSTGRES_DB=emuses
      - POSTGRES_USER=emuses
      - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
    secrets:
      - postgres_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

secrets:
  vault_token:
    external: true
  postgres_password:
    external: true

volumes:
  postgres_data:
```

</details>

## **Pattern 2: High Availability with Load Balancing**

### Architecture Overview

Multi-instance deployment for high availability and load distribution.

```
                     [Load Balancer]
                    /       |       \
        [EMUSES-1]         [EMUSES-2]         [EMUSES-3]
             |                  |                  |
        [Shared PostgreSQL] [Shared Storage] [HashiCorp Vault]
```

<details markdown="1">
<summary>⚖️ **Load Balancing Configuration**</summary>

Setup for high availability deployment:

```bash
# 1. Infrastructure Requirements
# - 3+ EMUSES instances (4 CPU, 16GB RAM each)
# - 1 PostgreSQL cluster (primary + standby)
# - 1 Vault cluster (3 nodes)
# - Shared storage (NFS, S3, etc.)
# - Load balancer with health checks

# 2. Database Cluster Setup
# Primary PostgreSQL
postgresql.conf:
    wal_level = replica
    max_wal_senders = 3
    wal_keep_segments = 32

# Standby PostgreSQL
recovery.conf:
    standby_mode = 'on'
    primary_conninfo = 'host=primary.db.company.com port=5432'

# 3. Vault Cluster Configuration
vault.hcl:
    storage "consul" {
      address = "consul.company.com:8500"
      path    = "vault/"
    }
    
    cluster_addr = "https://vault-node1:8201"
    api_addr = "https://vault.company.com:8200"

# 4. EMUSES Configuration (all instances)
export VAULT_ADDR="https://vault.company.com:8200"
export DATABASE_URL="postgresql://emuses:pass@primary.db.company.com:5432/emuses"
export SHARED_STORAGE_PATH="/mnt/emuses-shared"

# 5. Health Check Endpoint
# Each EMUSES instance provides /health endpoint for load balancer
curl https://emuses1.company.com:8000/health
# Returns: {"status": "healthy", "database": "connected", "vault": "accessible"}
```

**Capacity**: 100-1000 concurrent users, 10,000+ models, multi-TB data

</details>

<details markdown="1">
<summary>🔄 **Failover and Recovery**</summary>

Automated failover procedures:

```bash
# Load Balancer Health Checks
upstream emuses_cluster {
    server emuses1.company.com:8000 max_fails=3 fail_timeout=30s;
    server emuses2.company.com:8000 max_fails=3 fail_timeout=30s;
    server emuses3.company.com:8000 max_fails=3 fail_timeout=30s;
}

# Database Failover (automated with tools like Patroni)
# Vault Leader Election (automatic in cluster mode)

# Manual Recovery Procedures
# 1. Database Recovery
pg_basebackup -h primary.db.company.com -D /var/lib/postgresql/data -U replication -W

# 2. Vault Recovery
vault operator raft snapshot restore backup-20231215.snap

# 3. EMUSES Instance Recovery
systemctl restart emuses
python -m emuses.cli admin system-status --detailed
```

**Recovery Time**: < 5 minutes for instance failure, < 15 minutes for database failover

</details>

## **Pattern 3: Kubernetes Deployment**

### Architecture Overview

Container-orchestrated deployment with auto-scaling and service mesh.

<details markdown="1">
<summary>🚢 **Kubernetes Manifests**</summary>

Complete Kubernetes deployment:

**namespace.yaml**:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: emuses-production
  labels:
    name: emuses-production
```

**configmap.yaml**:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: emuses-config
  namespace: emuses-production
data:
  VAULT_ADDR: "https://vault.company.com:8200"
  EMUSES_DEPLOYMENT_MODE: "multi_user"
  DATABASE_URL: "postgresql://emuses:password@postgres-service:5432/emuses"
```

**deployment.yaml**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: emuses-api
  namespace: emuses-production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: emuses-api
  template:
    metadata:
      labels:
        app: emuses-api
    spec:
      serviceAccountName: emuses-vault-auth
      containers:
      - name: emuses
        image: emuses:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: emuses-config
        env:
        - name: VAULT_ROLE
          value: "emuses-k8s-role"
        - name: VAULT_AUTH_METHOD
          value: "kubernetes"
        resources:
          requests:
            memory: "2Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

**service.yaml**:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: emuses-service
  namespace: emuses-production
spec:
  selector:
    app: emuses-api
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
  type: ClusterIP
```

**ingress.yaml**:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: emuses-ingress
  namespace: emuses-production
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
  - hosts:
    - emuses.company.com
    secretName: emuses-tls
  rules:
  - host: emuses.company.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: emuses-service
            port:
              number: 80
```

</details>

<details markdown="1">
<summary>🔐 **Vault Kubernetes Integration**</summary>

Configure Vault authentication for Kubernetes:

```bash
# 1. Enable Kubernetes auth in Vault
vault auth enable kubernetes

# 2. Configure Kubernetes auth
vault write auth/kubernetes/config \
    token_reviewer_jwt="$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)" \
    kubernetes_host="https://kubernetes.default.svc.cluster.local:443" \
    kubernetes_ca_cert=@/var/run/secrets/kubernetes.io/serviceaccount/ca.crt

# 3. Create role for EMUSES
vault write auth/kubernetes/role/emuses-k8s-role \
    bound_service_account_names=emuses-vault-auth \
    bound_service_account_namespaces=emuses-production \
    policies=emuses-policy \
    ttl=24h

# 4. Service Account
kubectl apply -f - << EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: emuses-vault-auth
  namespace: emuses-production
EOF

# 5. Deploy with auto-scaling
kubectl apply -f - << EOF
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: emuses-hpa
  namespace: emuses-production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: emuses-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
EOF
```

**Features**: Auto-scaling, service discovery, rolling updates, secret injection

</details>

## **Pattern 4: Multi-Region Global Deployment**

### Architecture Overview

Geographically distributed deployment for global organizations.

```
Region 1 (US-East)    Region 2 (EU-West)    Region 3 (Asia-Pacific)
[EMUSES Cluster]      [EMUSES Cluster]      [EMUSES Cluster]
       |                      |                      |
[Regional Vault]      [Regional Vault]      [Regional Vault]
       |                      |                      |
      [Global Database Replication and Data Sync]
```

<details markdown="1">
<summary>🌍 **Global Configuration**</summary>

Multi-region deployment strategy:

```bash
# 1. Global DNS and Load Balancing
# Route53, CloudFlare, or similar with geo-routing

# 2. Regional Vault Clusters
# US-East Vault
vault.us-east.hcl:
    storage "dynamodb" {
      region = "us-east-1"
      table  = "vault-storage-us-east"
    }
    
    seal "awskms" {
      region     = "us-east-1"
      kms_key_id = "alias/vault-unseal-us-east"
    }

# EU-West Vault
vault.eu-west.hcl:
    storage "dynamodb" {
      region = "eu-west-1"
      table  = "vault-storage-eu-west"
    }
    
    seal "awskms" {
      region     = "eu-west-1"
      kms_key_id = "alias/vault-unseal-eu-west"
    }

# 3. Database Replication
# PostgreSQL with streaming replication
primary_conninfo = 'host=primary.us-east.company.com port=5432'

# 4. Cross-Region Secret Replication
# Vault Enterprise replication or custom sync
vault write -f sys/replication/performance/primary/enable
vault write sys/replication/performance/primary/secondary-token id="eu-west"

# 5. Regional EMUSES Configuration
# US-East
export VAULT_ADDR="https://vault.us-east.company.com:8200"
export DATABASE_URL="postgresql://emuses:pass@db.us-east.company.com:5432/emuses"
export REGION="us-east-1"

# EU-West
export VAULT_ADDR="https://vault.eu-west.company.com:8200"
export DATABASE_URL="postgresql://emuses:pass@db.eu-west.company.com:5432/emuses"
export REGION="eu-west-1"
```

**Benefits**: Low latency globally, data sovereignty compliance, disaster recovery

</details>

<details markdown="1">
<summary>🔄 **Data Synchronization**</summary>

Cross-region data management:

```bash
# 1. Model Registry Synchronization
# S3 Cross-Region Replication
aws s3api put-bucket-replication --bucket emuses-models-us-east --replication-configuration file://replication.json

# 2. Database Replication Strategy
# Read replicas in each region
pg_basebackup -h primary.us-east.company.com -D /var/lib/postgresql/replica -U replication

# 3. Conflict Resolution
# Last-writer-wins with timestamp-based resolution
UPDATE models SET updated_at = NOW() WHERE id = ? AND updated_at < ?

# 4. Health Monitoring Across Regions
# Global monitoring dashboard
python -m emuses.cli admin system-status --service-url https://emuses.us-east.company.com
python -m emuses.cli admin system-status --service-url https://emuses.eu-west.company.com
python -m emuses.cli admin system-status --service-url https://emuses.asia-pacific.company.com
```

**Consistency**: Eventual consistency with conflict resolution, strong consistency for critical data

</details>

## **Security and Compliance**

### Compliance Frameworks

<details markdown="1">
<summary>🛡️ **SOC 2 Compliance**</summary>

Implement SOC 2 Type II controls:

```bash
# 1. Access Controls
# Vault policies for least privilege
vault policy write emuses-readonly - << EOF
path "secret/data/emuses" {
  capabilities = ["read"]
}
EOF

# 2. Audit Logging
vault audit enable file file_path=/var/log/vault/audit.log

# 3. Encryption
# All data encrypted in transit and at rest
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365

# 4. Monitoring and Alerting
# Log analysis for security events
grep "FAILED" /var/log/vault/audit.log | jq '.time, .error'

# 5. Backup and Recovery
# Automated, encrypted backups
vault operator raft snapshot save emuses-backup-$(date +%Y%m%d).snap
gpg --encrypt --recipient admin@company.com emuses-backup-$(date +%Y%m%d).snap
```

**Controls**: CC1.1-CC9.3 implemented with Vault audit trails and monitoring

</details>

<details markdown="1">
<summary>🏥 **HIPAA Compliance**</summary>

Healthcare data protection requirements:

```bash
# 1. PHI Encryption
# All PHI encrypted with AES-256
export EMUSES_ENCRYPTION_KEY="$(openssl rand -base64 32)"
vault kv put secret/emuses phi_encryption_key="$EMUSES_ENCRYPTION_KEY"

# 2. Access Logging
# Detailed audit trail for PHI access
python -c "
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger('hipaa_audit')
logger.info('PHI accessed by user_id=123 for patient_id=456')
"

# 3. Minimum Necessary Standard
# Role-based access controls
vault write auth/ldap/groups/researchers policies="phi-research-readonly"
vault write auth/ldap/groups/clinicians policies="phi-clinical-readwrite"

# 4. Business Associate Agreements
# Document third-party integrations
echo "Vault Enterprise BAA: Documented and signed"
echo "Cloud Provider BAA: AWS/Azure/GCP BAA in place"
```

**Standards**: 45 CFR Part 160 and Part 164 compliance with encryption and audit

</details>

### Network Security

<details markdown="1">
<summary>🔒 **Network Segmentation**</summary>

Implement defense-in-depth networking:

```bash
# 1. VPC/Network Design
# EMUSES: 10.0.1.0/24 (DMZ)
# Database: 10.0.2.0/24 (Private)
# Vault: 10.0.3.0/24 (Private)
# Management: 10.0.4.0/24 (Admin)

# 2. Security Groups/Firewall Rules
# EMUSES (Web Tier)
iptables -A INPUT -p tcp --dport 443 -s 0.0.0.0/0 -j ACCEPT
iptables -A INPUT -p tcp --dport 8000 -s 10.0.0.0/16 -j ACCEPT

# Database (Data Tier)
iptables -A INPUT -p tcp --dport 5432 -s 10.0.1.0/24 -j ACCEPT

# Vault (Security Tier)
iptables -A INPUT -p tcp --dport 8200 -s 10.0.1.0/24 -j ACCEPT

# 3. VPN Access
# WireGuard or OpenVPN for admin access
wg genkey | tee privatekey | wg pubkey > publickey

# 4. Certificate Management
# Automated certificate rotation
certbot certonly --nginx -d emuses.company.com
```

**Protection**: Network isolation, encrypted communications, access controls

</details>

## **Monitoring and Operations**

### Comprehensive Monitoring

<details markdown="1">
<summary>📊 **Monitoring Stack**</summary>

Complete observability solution:

```bash
# 1. Prometheus Configuration
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'emuses'
    static_configs:
      - targets: ['emuses:8000']
    metrics_path: '/metrics'

  - job_name: 'vault'
    static_configs:
      - targets: ['vault:8200']
    metrics_path: '/v1/sys/metrics'

# 2. Grafana Dashboards
# EMUSES Application Metrics
curl -X POST \
  http://grafana:3000/api/dashboards/db \
  -H 'Content-Type: application/json' \
  -d @emuses-dashboard.json

# 3. Alertmanager Rules
# alerts.yml
groups:
- name: emuses
  rules:
  - alert: EMUSESDown
    expr: up{job="emuses"} == 0
    for: 1m
    annotations:
      summary: "EMUSES instance is down"

  - alert: VaultSealed
    expr: vault_core_unsealed == 0
    for: 1m
    annotations:
      summary: "Vault is sealed"

# 4. Log Aggregation
# Elasticsearch + Logstash + Kibana (ELK)
filebeat.yml:
inputs:
- type: log
  paths:
    - /var/log/emuses/*.log
    - /var/log/vault/*.log
  fields:
    service: emuses
```

**Metrics**: Application performance, infrastructure health, security events

</details>

<details markdown="1">
<summary>🚨 **Incident Response**</summary>

Automated incident response procedures:

```bash
# 1. Alert Escalation
# PagerDuty or similar integration
curl -X POST https://events.pagerduty.com/v2/enqueue \
  -H 'Content-Type: application/json' \
  -d '{
    "routing_key": "EMUSES_ROUTING_KEY",
    "event_action": "trigger",
    "payload": {
      "summary": "EMUSES System Critical Alert",
      "source": "monitoring.company.com",
      "severity": "critical"
    }
  }'

# 2. Automated Recovery
# Health check and recovery script
#!/bin/bash
if ! curl -sf http://emuses:8000/health; then
  echo "EMUSES unhealthy, attempting restart"
  systemctl restart emuses
  sleep 30
  if ! curl -sf http://emuses:8000/health; then
    echo "EMUSES still unhealthy, escalating"
    # Send alert to on-call engineer
  fi
fi

# 3. Runbook Automation
# Automated diagnostic collection
collect_diagnostics() {
  python -m emuses.cli admin system-status --detailed > diagnostics.log
  vault status >> diagnostics.log
  ps aux | grep emuses >> diagnostics.log
  df -h >> diagnostics.log
}
```

**Response**: Automated detection, escalation, and recovery procedures

</details>

## **Performance and Scaling**

### Performance Optimization

<details markdown="1">
<summary>⚡ **Performance Tuning**</summary>

Optimize for production workloads:

```bash
# 1. Database Optimization
# PostgreSQL configuration
postgresql.conf:
    shared_buffers = 256MB
    effective_cache_size = 1GB
    maintenance_work_mem = 64MB
    checkpoint_completion_target = 0.9
    wal_buffers = 16MB
    default_statistics_target = 100

# 2. Application Tuning
# Gunicorn configuration
gunicorn_config.py:
    bind = "0.0.0.0:8000"
    workers = 4
    worker_class = "uvicorn.workers.UvicornWorker"
    worker_connections = 1000
    max_requests = 10000
    max_requests_jitter = 1000

# 3. Cache Configuration
# Redis for session and result caching
export REDIS_URL="redis://cache.company.com:6379"
export CACHE_TTL=3600

# 4. Connection Pooling
# Database connection pooling
export DATABASE_POOL_SIZE=20
export DATABASE_MAX_OVERFLOW=30
export DATABASE_POOL_TIMEOUT=30

# 5. Performance Monitoring
# Application performance monitoring
python -c "
import time
start = time.time()
from emuses.multi_user_service.auth import get_jwt_secret
secret = get_jwt_secret()
print(f'Secret retrieval time: {(time.time() - start)*1000:.2f}ms')
"
```

**Targets**: < 100ms API response, < 50ms secret retrieval, 99.9% uptime

</details>

### Auto-Scaling Configuration

<details markdown="1">
<summary>📈 **Horizontal Scaling**</summary>

Automatic scaling based on demand:

```bash
# 1. Kubernetes HPA (shown earlier)
# 2. AWS Auto Scaling Group
aws autoscaling create-auto-scaling-group \
  --auto-scaling-group-name emuses-asg \
  --launch-template LaunchTemplateName=emuses-template \
  --min-size 2 \
  --max-size 10 \
  --desired-capacity 3 \
  --target-group-arns arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/emuses-tg/50dc6c495c0c9188

# 3. Scaling Policies
aws autoscaling put-scaling-policy \
  --auto-scaling-group-name emuses-asg \
  --policy-name scale-up \
  --policy-type TargetTrackingScaling \
  --target-tracking-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ASGAverageCPUUtilization"
    }
  }'

# 4. Database Read Replicas
# Automatic read replica creation
aws rds create-db-instance-read-replica \
  --db-instance-identifier emuses-read-replica-1 \
  --source-db-instance-identifier emuses-primary

# 5. Load Testing
# Validate scaling behavior
artillery run load-test.yml
```

**Scaling**: Auto-scale 2-10 instances based on CPU/memory, add read replicas for database scaling

</details>

## **Cost Optimization**

### Resource Management

<details markdown="1">
<summary>💰 **Cost Control Strategies**</summary>

Optimize costs while maintaining performance:

```bash
# 1. Right-Sizing Resources
# Monitor actual usage
kubectl top nodes
kubectl top pods -n emuses-production

# 2. Reserved Instances
# AWS Reserved Instances for predictable workloads
aws ec2 purchase-reserved-instances-offering \
  --reserved-instances-offering-id <offering-id> \
  --instance-count 3

# 3. Spot Instances for Development
# Use spot instances for non-production workloads
aws ec2 request-spot-instances \
  --spot-price "0.50" \
  --instance-count 2 \
  --type "one-time" \
  --launch-specification '{
    "ImageId": "ami-12345678",
    "InstanceType": "t3.large",
    "KeyName": "emuses-key"
  }'

# 4. Storage Optimization
# Lifecycle policies for model storage
aws s3api put-bucket-lifecycle-configuration \
  --bucket emuses-models \
  --lifecycle-configuration '{
    "Rules": [{
      "Id": "ArchiveOldModels",
      "Status": "Enabled",
      "Transitions": [{
        "Days": 30,
        "StorageClass": "STANDARD_IA"
      }, {
        "Days": 90,
        "StorageClass": "GLACIER"
      }]
    }]
  }'

# 5. Cost Monitoring
# Tag resources for cost allocation
aws ec2 create-tags \
  --resources i-1234567890abcdef0 \
  --tags Key=Project,Value=EMUSES Key=Environment,Value=Production
```

**Savings**: 30-50% cost reduction through right-sizing, reserved capacity, and lifecycle management

</details>

---

**🏢 This guide provides production-ready enterprise deployment patterns for secure, scalable, and compliant EMUSES deployments with HashiCorp Vault integration.**

---

*EMUSES Enterprise Deployment Patterns - Production Architecture Guide*