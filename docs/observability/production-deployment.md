# EMUSES Observability - Production Deployment Guide

This guide covers deploying the EMUSES observability system in production environments.

## Overview

The EMUSES observability system provides comprehensive monitoring for scientific pipelines with minimal performance overhead (<2%). It includes:

- **Prometheus metrics** for quantitative monitoring
- **Grafana dashboards** for visualization and alerting
- **Structured logging** with correlation IDs
- **HTTP request tracking** with middleware
- **Performance monitoring** for scientific workloads

## Quick Start

### 1. Start Observability Stack

```bash
# Start Prometheus, Grafana, and Node Exporter
docker-compose -f docker-compose.observability.yml up -d

# Or use the convenience script
./scripts/start-observability.sh
```

### 2. Access Dashboards

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **EMUSES Metrics**: http://localhost:8000/metrics

### 3. Configure Application

```python
# In your FastAPI application
from emuses.observability import setup_structured_logging

# Configure observability
setup_structured_logging(level='INFO')
```

## Production Configuration

### Environment Variables

```bash
# Logging configuration
LOG_LEVEL=INFO                    # INFO, DEBUG, WARNING, ERROR
STRUCTURED_LOGGING=true           # Enable structured logging
LOG_OUTPUT_FILE=/var/log/emuses/app.log  # Optional log file

# Metrics configuration  
PROMETHEUS_METRICS_ENABLED=true  # Enable Prometheus metrics
METRICS_PORT=8000                # Metrics endpoint port

# Performance settings
OBSERVABILITY_SAMPLE_RATE=1.0    # Sample rate for tracing (0.0-1.0)
```

### Docker Compose Production

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  emuses-api:
    image: emuses:production
    environment:
      - LOG_LEVEL=INFO
      - PROMETHEUS_METRICS_ENABLED=true
      - STRUCTURED_LOGGING=true
    volumes:
      - /var/log/emuses:/var/log/emuses
    networks:
      - emuses-network
      - observability
      
  prometheus:
    image: prom/prometheus:v2.47.0
    volumes:
      - ./docker/observability/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./docker/observability/alerts.yml:/etc/prometheus/alerts.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
      - '--web.enable-admin-api'
    ports:
      - "9090:9090"
    networks:
      - observability
      
  grafana:
    image: grafana/grafana:10.1.0
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_INSTALL_PLUGINS=grafana-piechart-panel,grafana-worldmap-panel
    volumes:
      - grafana-data:/var/lib/grafana
      - ./docker/observability/grafana/datasources:/etc/grafana/provisioning/datasources
      - ./docker/observability/grafana/dashboards:/etc/grafana/provisioning/dashboards  
    ports:
      - "3000:3000"
    networks:
      - observability

networks:
  emuses-network:
    driver: bridge
  observability:
    driver: bridge
    
volumes:
  prometheus-data:
  grafana-data:
```

### Kubernetes Deployment

```yaml
# k8s/observability-namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: emuses-observability
---
# k8s/prometheus-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: emuses-observability
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    
    rule_files:
      - "alerts.yml"
    
    scrape_configs:
      - job_name: 'emuses-api'
        static_configs:
          - targets: ['emuses-api:8000']
        metrics_path: /metrics
        scrape_interval: 30s
        
      - job_name: 'node-exporter'
        static_configs:
          - targets: ['node-exporter:9100']
---
# k8s/prometheus-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: emuses-observability
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: prometheus
        image: prom/prometheus:v2.47.0
        ports:
        - containerPort: 9090
        volumeMounts:
        - name: config-volume
          mountPath: /etc/prometheus
        - name: storage-volume
          mountPath: /prometheus
        command:
          - '/bin/prometheus'
          - '--config.file=/etc/prometheus/prometheus.yml'
          - '--storage.tsdb.path=/prometheus'
          - '--storage.tsdb.retention.time=30d'
          - '--web.enable-lifecycle'
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
      volumes:
      - name: config-volume
        configMap:
          name: prometheus-config
      - name: storage-volume
        persistentVolumeClaim:
          claimName: prometheus-pvc
---
# k8s/grafana-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
  namespace: emuses-observability
spec:
  replicas: 1
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      containers:
      - name: grafana
        image: grafana/grafana:10.1.0
        ports:
        - containerPort: 3000
        env:
        - name: GF_SECURITY_ADMIN_PASSWORD
          valueFrom:
            secretKeyRef:
              name: grafana-admin
              key: password
        volumeMounts:
        - name: grafana-storage
          mountPath: /var/lib/grafana
        - name: grafana-datasources
          mountPath: /etc/grafana/provisioning/datasources
        - name: grafana-dashboards
          mountPath: /etc/grafana/provisioning/dashboards
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: grafana-storage
        persistentVolumeClaim:
          claimName: grafana-pvc
      - name: grafana-datasources
        configMap:
          name: grafana-datasources
      - name: grafana-dashboards
        configMap:
          name: grafana-dashboards
```

## Monitoring Configuration

### Key Metrics to Monitor

```yaml
# Production alerting rules
groups:
  - name: emuses.rules
    rules:
    # API Health
    - alert: EMUSESAPIDown
      expr: up{job="emuses-api"} == 0
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "EMUSES API is down"
        
    # Pipeline Performance  
    - alert: PipelineHighLatency
      expr: histogram_quantile(0.95, emuses_pipeline_duration_seconds) > 300
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "Pipeline latency is high (95th percentile > 5 minutes)"
        
    # Pipeline Errors
    - alert: PipelineErrorRate
      expr: rate(emuses_pipeline_errors_total[5m]) > 0.1
      for: 2m
      labels:
        severity: warning
      annotations:
        summary: "High pipeline error rate (>10% in 5 minutes)"
        
    # Memory Usage
    - alert: HighMemoryUsage
      expr: emuses_memory_usage_bytes > 8e9  # 8GB
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High memory usage in pipeline (>8GB)"
        
    # System Resources
    - alert: HighCPUUsage
      expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High CPU usage (>80%)"
```

### Dashboard Configuration

Key dashboards included:

1. **System Overview Dashboard**
   - API request rates and latencies
   - System resource usage (CPU, memory, disk)
   - Active job counts
   - Error rates and alerts

2. **Scientific Pipeline Dashboard**  
   - Pipeline execution times by stage
   - Optimization trial success rates
   - Dataset processing volumes
   - Memory usage patterns

### Log Aggregation

For production log aggregation, consider integrating with:

```yaml
# ELK Stack integration
logging:
  driver: "json-file"
  options:
    max-size: "100m"
    max-file: "5"
    
# Fluent Bit configuration
[INPUT]
    Name              tail
    Path              /var/log/emuses/*.log
    Parser            json
    Tag               emuses.*
    Refresh_Interval  5

[OUTPUT]
    Name  es
    Match emuses.*
    Host  elasticsearch
    Port  9200
    Index emuses-logs
```

## Security Considerations

### Authentication

```yaml
# Grafana LDAP integration
[auth.ldap]
enabled = true
config_file = /etc/grafana/ldap.toml

# Basic auth for Prometheus (production)
basic_auth_users:
  admin: $2a$12$hNf2lSsxfm0.i4a.1kVpSOVyBMOrt4erY8d5qms.ZELQqAWDdMnyy
```

### Network Security

```yaml
# Network policies for Kubernetes
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: observability-network-policy
  namespace: emuses-observability
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: emuses-production
    ports:
    - protocol: TCP
      port: 9090
    - protocol: TCP
      port: 3000
```

### Data Retention

```yaml
# Prometheus retention policy
command:
  - '--storage.tsdb.retention.time=30d'
  - '--storage.tsdb.retention.size=50GB'
  
# Log rotation
/var/log/emuses/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

## Performance Optimization

### Resource Allocation

```yaml
# Container resource limits
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "1000m"
    
# JVM settings for high-throughput scenarios
environment:
  - JAVA_OPTS=-Xmx2g -XX:+UseG1GC -XX:MaxGCPauseMillis=200
```

### Monitoring Overhead

The observability system is designed for <2% performance overhead:

- **Metrics collection**: 0.0026ms per operation
- **Structured logging**: 0.0147ms per log message  
- **Pipeline simulation**: 1.02% overhead (well under 2% target)

### Scaling Considerations

```yaml
# Horizontal Pod Autoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: emuses-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: emuses-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## Troubleshooting

### Common Issues

1. **Metrics not appearing in Grafana**
   ```bash
   # Check Prometheus targets
   curl http://localhost:9090/api/v1/targets
   
   # Verify EMUSES metrics endpoint
   curl http://localhost:8000/metrics
   ```

2. **High memory usage in observability**
   ```bash
   # Check Prometheus memory usage
   docker stats prometheus
   
   # Reduce retention if needed
   --storage.tsdb.retention.time=7d
   ```

3. **Log correlation issues**
   ```python
   # Verify correlation ID middleware
   from emuses.observability.logging import get_logger
   logger = get_logger(__name__)
   logger.info("Test correlation", request_id="test-123")
   ```

### Health Checks

```bash
# Observability health check script
#!/bin/bash

echo "Checking observability stack health..."

# Check Prometheus
if curl -s http://localhost:9090/-/healthy > /dev/null; then
    echo "✅ Prometheus: healthy"
else
    echo "❌ Prometheus: unhealthy"
fi

# Check Grafana  
if curl -s http://localhost:3000/api/health > /dev/null; then
    echo "✅ Grafana: healthy"
else
    echo "❌ Grafana: unhealthy"
fi

# Check EMUSES metrics
if curl -s http://localhost:8000/metrics | grep -q "emuses_"; then
    echo "✅ EMUSES metrics: available"
else
    echo "❌ EMUSES metrics: unavailable"
fi
```

## Maintenance

### Backup Procedures

```bash
# Backup Grafana dashboards
docker exec grafana grafana-cli admin export-dashboard > backup-dashboards.json

# Backup Prometheus configuration
cp docker/observability/prometheus.yml backup/

# Database backup (if using external storage)
kubectl exec -n emuses-observability prometheus-0 -- \
  tar -czf /prometheus/prometheus-backup-$(date +%Y%m%d).tar.gz /prometheus/data
```

### Updates and Upgrades

```bash
# Update observability stack
docker-compose -f docker-compose.observability.yml pull
docker-compose -f docker-compose.observability.yml up -d

# Rolling update in Kubernetes
kubectl rollout restart deployment/prometheus -n emuses-observability
kubectl rollout restart deployment/grafana -n emuses-observability
```

## Support and Monitoring

For production support:

1. **Monitor the monitors**: Set up alerting for observability components
2. **Regular health checks**: Automated monitoring of monitoring systems
3. **Performance baselines**: Establish baseline metrics for comparison
4. **Incident response**: Clear procedures for observability system failures

The EMUSES observability system provides comprehensive monitoring with minimal overhead, ensuring your scientific workloads can be monitored effectively in production environments.