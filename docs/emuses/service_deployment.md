# EMUSES Service Deployment

This guide covers deployment strategies for the EMUSES FastAPI service across different environments, from local development to production-scale deployments. The service is designed for flexible deployment with comprehensive configuration options and monitoring capabilities.

<details>
<summary><strong>🏠 Local Development Setup</strong></summary>

## Quick Start

### Prerequisites
```bash
# Install EMUSES with service dependencies
pip install emuses[service]

# Or install development dependencies
pip install -e .[dev,service]
```

### Auto-Start Local Service (Recommended)
The CLI automatically manages the local service:

```bash
# Service starts automatically when needed
emuses --input-dataset data/input.csv --scores data/scores.csv --output results/

# Check service status
emuses --health-check
```

### Manual Service Startup
For development and testing:

```bash
# Start service directly
python -m emuses.api.main

# Or using uvicorn
uvicorn emuses.api.main:create_app --host 0.0.0.0 --port 8000 --reload

# Enable development features
uvicorn emuses.api.main:create_app --host 0.0.0.0 --port 8000 --reload --log-level debug
```

### Development Configuration
Set environment variables for development:

```bash
# Enable testing mode (disables rate limiting)
export TESTING_MODE=true

# Configure job storage
export EMUSES_JOB_STORAGE="/tmp/emuses_dev_jobs"

# Disable rate limiting
export RATE_LIMITING_ENABLED=false

# Set log level
export LOG_LEVEL=debug
```

### Interactive API Exploration
Access API documentation:
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI Schema**: http://localhost:8000/api/openapi.json

</details>

<details>
<summary><strong>🐳 Containerized Deployment</strong></summary>

## Docker Deployment

### Basic Docker Setup
```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for neuroimaging
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libhdf5-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install EMUSES
RUN pip install -e .[service]

# Create non-root user
RUN useradd -m -u 1000 emuses && \
    mkdir -p /app/jobs /app/uploads && \
    chown -R emuses:emuses /app

USER emuses

# Configure service
ENV EMUSES_JOB_STORAGE=/app/jobs
ENV UPLOAD_DIRECTORY=/app/uploads
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "emuses.api.main:create_app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build and Run
```bash
# Build image
docker build -t emuses-service:latest .

# Run container
docker run -d \
  --name emuses-service \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data:ro \
  -v $(pwd)/results:/app/results \
  -e EMUSES_JOB_STORAGE=/app/results/jobs \
  emuses-service:latest

# Check service health
curl http://localhost:8000/api/health
```

### Docker Compose for Development
```yaml
# docker-compose.yml
version: '3.8'

services:
  emuses-service:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data:ro
      - ./results:/app/results
      - job_storage:/app/jobs
      - upload_storage:/app/uploads
    environment:
      - EMUSES_JOB_STORAGE=/app/jobs
      - UPLOAD_DIRECTORY=/app/uploads
      - RATE_LIMITING_ENABLED=true
      - LOG_LEVEL=info
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - emuses-service
    restart: unless-stopped

volumes:
  job_storage:
  upload_storage:
```

### Production Docker Configuration
```dockerfile
# Multi-stage build for production
FROM python:3.9-slim as builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.9-slim

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application
WORKDIR /app
COPY . .
RUN pip install --user -e .[service]

# Security hardening
RUN useradd -m -u 1000 emuses && \
    mkdir -p /app/jobs /app/uploads && \
    chown -R emuses:emuses /app && \
    chmod 750 /app

USER emuses

# Production configuration
ENV PYTHONPATH=/app
ENV EMUSES_JOB_STORAGE=/app/jobs
ENV UPLOAD_DIRECTORY=/app/uploads
ENV RATE_LIMITING_ENABLED=true
ENV LOG_LEVEL=info

EXPOSE 8000

# Use production WSGI server
CMD ["gunicorn", "emuses.api.main:create_app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

</details>

<details>
<summary><strong>☁️ Production Deployment Patterns</strong></summary>

## Load Balancer Configuration

### Nginx Reverse Proxy
```nginx
# nginx.conf
upstream emuses_backend {
    server emuses-service-1:8000;
    server emuses-service-2:8000;
    server emuses-service-3:8000;
}

server {
    listen 80;
    server_name emuses.research.org;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name emuses.research.org;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Large file support for neuroimaging data
    client_max_body_size 2G;
    client_body_timeout 300s;
    proxy_read_timeout 300s;
    proxy_connect_timeout 60s;
    proxy_send_timeout 300s;
    
    location /api/ {
        proxy_pass http://emuses_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for real-time updates
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    location /health {
        proxy_pass http://emuses_backend/api/health;
        access_log off;
    }
}
```

### HAProxy Configuration
```haproxy
# haproxy.cfg
global
    daemon
    maxconn 4096

defaults
    mode http
    timeout connect 5s
    timeout client 300s
    timeout server 300s
    option httplog

frontend emuses_frontend
    bind *:80
    bind *:443 ssl crt /etc/ssl/certs/emuses.pem
    redirect scheme https if !{ ssl_fc }
    
    # Rate limiting
    stick-table type ip size 100k expire 30s store http_req_rate(10s)
    http-request track-sc0 src
    http-request reject if { sc_http_req_rate(0) gt 100 }
    
    default_backend emuses_backend

backend emuses_backend
    balance roundrobin
    option httpchk GET /api/health
    
    server emuses1 emuses-service-1:8000 check
    server emuses2 emuses-service-2:8000 check
    server emuses3 emuses-service-3:8000 check
```

## Kubernetes Deployment

### Service Deployment
```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: emuses-service
  labels:
    app: emuses-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: emuses-service
  template:
    metadata:
      labels:
        app: emuses-service
    spec:
      containers:
      - name: emuses-service
        image: emuses-service:latest
        ports:
        - containerPort: 8000
        env:
        - name: EMUSES_JOB_STORAGE
          value: "/app/jobs"
        - name: UPLOAD_DIRECTORY
          value: "/app/uploads"
        - name: RATE_LIMITING_ENABLED
          value: "true"
        - name: LOG_LEVEL
          value: "info"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "8Gi"
            cpu: "4000m"
        volumeMounts:
        - name: job-storage
          mountPath: /app/jobs
        - name: upload-storage
          mountPath: /app/uploads
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: job-storage
        persistentVolumeClaim:
          claimName: emuses-jobs-pvc
      - name: upload-storage
        persistentVolumeClaim:
          claimName: emuses-uploads-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: emuses-service
spec:
  selector:
    app: emuses-service
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: emuses-jobs-pvc
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 100Gi

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: emuses-uploads-pvc
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 50Gi
```

### Ingress Configuration
```yaml
# k8s-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: emuses-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "2g"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "300"
spec:
  tls:
  - hosts:
    - emuses.research.org
    secretName: emuses-tls
  rules:
  - host: emuses.research.org
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

## Cloud Platform Deployment

### AWS ECS with Fargate
```json
{
  "family": "emuses-service",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "8192",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "emuses-service",
      "image": "your-registry/emuses-service:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "EMUSES_JOB_STORAGE", "value": "/app/jobs"},
        {"name": "UPLOAD_DIRECTORY", "value": "/app/uploads"},
        {"name": "RATE_LIMITING_ENABLED", "value": "true"}
      ],
      "mountPoints": [
        {
          "sourceVolume": "efs-jobs",
          "containerPath": "/app/jobs"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/emuses-service",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/api/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ],
  "volumes": [
    {
      "name": "efs-jobs",
      "efsVolumeConfiguration": {
        "fileSystemId": "fs-12345678",
        "transitEncryption": "ENABLED"
      }
    }
  ]
}
```

### Google Cloud Run
```yaml
# cloud-run-service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: emuses-service
  annotations:
    run.googleapis.com/ingress: all
    run.googleapis.com/execution-environment: gen2
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/cpu-throttling: "false"
        run.googleapis.com/memory: "8Gi"
        autoscaling.knative.dev/maxScale: "10"
    spec:
      containerConcurrency: 10
      timeoutSeconds: 300
      containers:
      - image: gcr.io/your-project/emuses-service:latest
        ports:
        - containerPort: 8000
        env:
        - name: EMUSES_JOB_STORAGE
          value: "/mnt/jobs"
        - name: UPLOAD_DIRECTORY
          value: "/mnt/uploads"
        resources:
          limits:
            cpu: "4"
            memory: "8Gi"
        volumeMounts:
        - name: jobs-volume
          mountPath: /mnt/jobs
        - name: uploads-volume
          mountPath: /mnt/uploads
      volumes:
      - name: jobs-volume
        nfs:
          server: FILESTORE_IP
          path: /jobs
      - name: uploads-volume
        nfs:
          server: FILESTORE_IP
          path: /uploads
```

</details>

## Configuration Management

### Environment Variables
```bash
# Core service configuration
EMUSES_JOB_STORAGE="/var/lib/emuses/jobs"          # Job storage directory
UPLOAD_DIRECTORY="/var/lib/emuses/uploads"          # Upload temporary storage
RATE_LIMITING_ENABLED="true"                        # Enable rate limiting
TESTING_MODE="false"                               # Disable testing mode

# Performance tuning
UVICORN_WORKERS="4"                                # Number of worker processes
UVICORN_MAX_REQUESTS="1000"                        # Requests per worker before restart
UVICORN_TIMEOUT_KEEP_ALIVE="5"                     # Keep-alive timeout

# Security configuration
CORS_ORIGINS="https://emuses.research.org"         # Allowed CORS origins
MAX_REQUEST_SIZE="2147483648"                      # 2GB request size limit
```

### Configuration File
```yaml
# emuses-service.yaml
service:
  host: "0.0.0.0"
  port: 8000
  workers: 4
  
storage:
  jobs_directory: "/var/lib/emuses/jobs"
  uploads_directory: "/var/lib/emuses/uploads"
  cleanup_after_days: 7.0
  
security:
  rate_limiting_enabled: true
  max_request_size: 2147483648  # 2GB
  cors_origins:
    - "https://emuses.research.org"
    - "https://api.emuses.org"
  
logging:
  level: "info"
  format: "json"
  file: "/var/log/emuses/service.log"
  
monitoring:
  health_check_interval: 30
  metrics_enabled: true
  prometheus_port: 9090
```

## Monitoring and Observability

### Health Checks
```bash
# Basic health check
curl http://localhost:8000/api/health

# Detailed service status
curl http://localhost:8000/api/v1/status

# Prometheus metrics
curl http://localhost:8000/api/metrics
```

### Logging Configuration
```python
# logging.yaml
version: 1
disable_existing_loggers: false

formatters:
  standard:
    format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
  json:
    class: pythonjsonlogger.jsonlogger.JsonFormatter
    format: "%(asctime)s %(name)s %(levelname)s %(message)s"

handlers:
  console:
    class: logging.StreamHandler
    formatter: standard
    stream: ext://sys.stdout
  
  file:
    class: logging.handlers.RotatingFileHandler
    formatter: json
    filename: /var/log/emuses/service.log
    maxBytes: 100000000  # 100MB
    backupCount: 5

loggers:
  emuses:
    level: INFO
    handlers: [console, file]
    propagate: false
  
  uvicorn:
    level: INFO
    handlers: [console, file]
    propagate: false

root:
  level: INFO
  handlers: [console, file]
```

### Performance Monitoring
```python
# Custom metrics collection
from prometheus_client import Counter, Histogram, Gauge

# Job metrics
job_submissions = Counter('emuses_jobs_submitted_total', 'Total job submissions')
job_duration = Histogram('emuses_job_duration_seconds', 'Job execution duration')
active_jobs = Gauge('emuses_active_jobs', 'Number of active jobs')

# API metrics
api_requests = Counter('emuses_api_requests_total', 'Total API requests', ['method', 'endpoint'])
api_duration = Histogram('emuses_api_request_duration_seconds', 'API request duration', ['method', 'endpoint'])
```

## Security Hardening

### SSL/TLS Configuration
```bash
# Generate self-signed certificate for development
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Production: Use Let's Encrypt with certbot
certbot certonly --webroot -w /var/www/emuses -d emuses.research.org
```

### Firewall Rules
```bash
# UFW configuration
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

# Specific service port (if needed)
ufw allow from 10.0.0.0/8 to any port 8000
```

### Container Security
```dockerfile
# Security-hardened container
FROM python:3.9-slim

# Create non-root user
RUN groupadd -r emuses && useradd -r -g emuses emuses

# Install security updates
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set secure permissions
COPY --chown=emuses:emuses . /app
RUN chmod -R 750 /app

USER emuses
WORKDIR /app

# Drop unnecessary privileges
USER emuses:emuses
```

## Troubleshooting

### Common Issues
1. **Port conflicts**: Check if port 8000 is already in use
2. **Permission errors**: Ensure proper file system permissions
3. **Memory issues**: Monitor memory usage for large datasets
4. **Network connectivity**: Verify firewall and network configuration

### Debugging Commands
```bash
# Check service logs
docker logs emuses-service

# Monitor resource usage
docker stats emuses-service

# Debug network connectivity
nc -zv localhost 8000

# Check disk space
df -h /var/lib/emuses/

# Monitor active connections
netstat -tulpn | grep :8000
```

### Performance Optimization
1. **Worker processes**: Scale based on CPU cores
2. **Memory allocation**: Monitor and adjust based on workload
3. **Disk I/O**: Use SSDs for job storage
4. **Network**: Optimize for large file transfers
5. **Caching**: Implement Redis for session management

The EMUSES service is designed for flexible deployment across various environments while maintaining security, performance, and reliability standards. Choose the deployment pattern that best fits your infrastructure requirements and scaling needs.

For API usage details, see [API Service Documentation](api_service.md).

For CLI integration patterns, see [CLI Service Integration](cli_service_integration.md).