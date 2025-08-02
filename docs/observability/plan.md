# Observability & Monitoring System Implementation Plan

## Overview

Implement a comprehensive observability and monitoring system for EMUSES using OpenTelemetry, Prometheus, Grafana, and Tempo following 2025 industry best practices. The system will provide metrics, tracing, and logging capabilities across the multi-service architecture while maintaining minimal performance overhead.

## Implementation Strategy

### Phase 1: OpenTelemetry Foundation (Days 1-2)

#### Task 1.1: OpenTelemetry Base Configuration
**Duration**: 6 hours  
**Description**: Install and configure OpenTelemetry components

**Dependencies Installation**:
```python
# Add to requirements.txt
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
opentelemetry-instrumentation==0.42b0
opentelemetry-instrumentation-fastapi==0.42b0
opentelemetry-instrumentation-sqlalchemy==0.42b0
opentelemetry-instrumentation-httpx==0.42b0
opentelemetry-exporter-otlp==1.21.0
opentelemetry-semantic-conventions==0.42b0
prometheus-client==0.19.0
structlog==23.2.0
```

**Base Instrumentation Setup**:
```python
# emuses/observability/__init__.py
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

def setup_observability():
    # Configure resource information
    resource = Resource.create({
        "service.name": "emuses",
        "service.version": "0.7.0",
        "deployment.environment": os.getenv("EMUSES_DEPLOYMENT_MODE", "development")
    })
    
    # Setup tracing
    trace.set_tracer_provider(TracerProvider(resource=resource))
    tracer = trace.get_tracer(__name__)
    
    otlp_exporter = OTLPSpanExporter(
        endpoint="http://otel-collector:4317",
        insecure=True
    )
    span_processor = BatchSpanProcessor(otlp_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)
    
    # Setup metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint="http://otel-collector:4317",
            insecure=True
        ),
        export_interval_millis=5000
    )
    metrics.set_meter_provider(MeterProvider(
        resource=resource,
        metric_readers=[metric_reader]
    ))
```

#### Task 1.2: FastAPI Automatic Instrumentation
**Duration**: 4 hours  
**Description**: Implement automatic instrumentation for FastAPI services

**FastAPI Integration**:
```python
# emuses/foundation_fastapi_service/app.py
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from emuses.observability import setup_observability

# Initialize observability
setup_observability()

# Create FastAPI app
app = create_app()

# Automatic instrumentation
FastAPIInstrumentor.instrument_app(
    app,
    server_request_hook=request_hook,
    client_response_hook=response_hook
)

# Database instrumentation
if database_engine:
    SQLAlchemyInstrumentor().instrument(
        engine=database_engine,
        service="emuses-database"
    )

# HTTP client instrumentation
HTTPXClientInstrumentor().instrument()

def request_hook(span, scope):
    """Add custom attributes to incoming requests"""
    if hasattr(scope.get("user"), "id"):
        span.set_attribute("user.id", str(scope["user"].id))
    span.set_attribute("emuses.deployment_mode", 
                      os.getenv("EMUSES_DEPLOYMENT_MODE", "unknown"))

def response_hook(span, scope, response):
    """Add custom attributes to responses"""
    span.set_attribute("http.response.size", len(response.body))
```

#### Task 1.3: Structured Logging Implementation
**Duration**: 4 hours  
**Description**: Implement structured logging with correlation IDs

**Structured Logging Setup**:
```python
# emuses/observability/logging.py
import structlog
from opentelemetry import trace
import json
import sys

def setup_structured_logging():
    """Configure structured logging with OpenTelemetry correlation"""
    
    def add_trace_info(logger, method_name, event_dict):
        """Add trace information to log entries"""
        span = trace.get_current_span()
        if span != trace.INVALID_SPAN:
            span_context = span.get_span_context()
            event_dict["trace_id"] = format(span_context.trace_id, "032x")
            event_dict["span_id"] = format(span_context.span_id, "016x")
        return event_dict
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            add_trace_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

# Usage in application code
logger = structlog.get_logger(__name__)

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Add request context to all log entries"""
    with structlog.contextvars.clear_contextvars():
        structlog.contextvars.bind_contextvars(
            request_id=str(uuid.uuid4()),
            method=request.method,
            url=str(request.url),
            user_agent=request.headers.get("user-agent")
        )
        response = await call_next(request)
        return response
```

### Phase 2: Metrics Collection and Dashboards (Days 3-4)

#### Task 2.1: Custom Scientific Pipeline Metrics
**Duration**: 6 hours  
**Description**: Implement custom metrics for EMUSES scientific operations

**Pipeline Metrics Implementation**:
```python
# emuses/observability/metrics.py
from opentelemetry import metrics
from typing import Dict, Any
import time

# Create meter
meter = metrics.get_meter(__name__)

# Scientific pipeline metrics
pipeline_duration = meter.create_histogram(
    "emuses_pipeline_duration_seconds",
    description="Duration of pipeline operations by stage",
    unit="s"
)

optimization_trials = meter.create_counter(
    "emuses_optimization_trials_total",
    description="Total number of optimization trials"
)

dataset_size = meter.create_histogram(
    "emuses_dataset_size_bytes",
    description="Size of datasets processed",
    unit="bytes"
)

memory_usage = meter.create_gauge(
    "emuses_memory_usage_bytes",
    description="Peak memory usage during operations",
    unit="bytes"
)

active_jobs = meter.create_gauge(
    "emuses_active_jobs",
    description="Number of currently active jobs"
)

class PipelineMetrics:
    """Context manager for pipeline operation metrics"""
    
    def __init__(self, stage_name: str, user_id: str = None):
        self.stage_name = stage_name
        self.user_id = user_id
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        labels = {"stage": self.stage_name}
        if self.user_id:
            labels["user_id"] = self.user_id
        if exc_type:
            labels["status"] = "error"
            labels["error_type"] = exc_type.__name__
        else:
            labels["status"] = "success"
            
        pipeline_duration.record(duration, labels)

# Usage in pipeline stages
# emuses/pipelines/umap_stage.py
from emuses.observability.metrics import PipelineMetrics, optimization_trials, memory_usage

class UMAPStage:
    def run(self, context):
        with PipelineMetrics("umap_optimization", context.get("user_id")):
            # Track optimization trials
            for trial in range(context.get("n_trials", 50)):
                optimization_trials.add(1, {"stage": "umap", "trial_type": "main"})
                
                # Track memory usage
                current_memory = psutil.Process().memory_info().rss
                memory_usage.set(current_memory, {"stage": "umap"})
                
                # Existing UMAP optimization logic
                result = self._run_optimization_trial(trial, context)
```

#### Task 2.2: Prometheus and Grafana Setup
**Duration**: 6 hours  
**Description**: Deploy Prometheus and Grafana with custom dashboards

**Docker Compose Enhancement**:
```yaml
# docker-compose.observability.yml
version: '3.8'

services:
  # Existing services
  api:
    environment:
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
      - OTEL_SERVICE_NAME=emuses-api
      - OTEL_RESOURCE_ATTRIBUTES=service.version=0.7.0

  # OpenTelemetry Collector
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.90.1
    container_name: emuses-otel-collector
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./observability/otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317"   # OTLP gRPC receiver
      - "4318:4318"   # OTLP HTTP receiver
      - "8889:8889"   # Prometheus metrics
    networks:
      - emuses-network

  # Prometheus
  prometheus:
    image: prom/prometheus:v2.48.0
    container_name: emuses-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./observability/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    networks:
      - emuses-network

  # Grafana
  grafana:
    image: grafana/grafana:10.2.2
    container_name: emuses-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana_data:/var/lib/grafana
      - ./observability/grafana/datasources:/etc/grafana/provisioning/datasources
      - ./observability/grafana/dashboards:/etc/grafana/provisioning/dashboards
    networks:
      - emuses-network

  # Tempo for distributed tracing
  tempo:
    image: grafana/tempo:2.3.1
    container_name: emuses-tempo
    command: [ "-config.file=/etc/tempo.yaml" ]
    volumes:
      - ./observability/tempo.yaml:/etc/tempo.yaml
      - tempo_data:/tmp/tempo
    ports:
      - "14250:14250"   # jaeger ingest
      - "3200:3200"     # tempo query
    networks:
      - emuses-network

volumes:
  prometheus_data:
  grafana_data:
  tempo_data:
```

**Prometheus Configuration**:
```yaml
# observability/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alerts.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'emuses-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    
  - job_name: 'otel-collector'
    static_configs:
      - targets: ['otel-collector:8889']

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

#### Task 2.3: Custom Grafana Dashboards
**Duration**: 6 hours  
**Description**: Create comprehensive dashboards for EMUSES monitoring

**System Overview Dashboard**:
```json
{
  "dashboard": {
    "title": "EMUSES System Overview",
    "panels": [
      {
        "title": "API Request Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(http_requests_total{job=\"emuses-api\"}[5m])",
            "legendFormat": "{{method}} {{handler}}"
          }
        ]
      },
      {
        "title": "Pipeline Execution Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(emuses_pipeline_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile - {{stage}}"
          }
        ]
      },
      {
        "title": "Active Scientific Jobs",
        "type": "gauge",
        "targets": [
          {
            "expr": "emuses_active_jobs",
            "legendFormat": "Active Jobs"
          }
        ]
      },
      {
        "title": "Memory Usage by Stage",
        "type": "graph",
        "targets": [
          {
            "expr": "emuses_memory_usage_bytes / 1024 / 1024",
            "legendFormat": "{{stage}} Memory (MB)"
          }
        ]
      }
    ]
  }
}
```

**Scientific Pipeline Dashboard**:
```json
{
  "dashboard": {
    "title": "EMUSES Scientific Pipeline Performance",
    "panels": [
      {
        "title": "UMAP Optimization Time",
        "type": "heatmap",
        "targets": [
          {
            "expr": "increase(emuses_pipeline_duration_seconds_bucket{stage=\"umap_optimization\"}[1h])",
            "legendFormat": "{{le}}"
          }
        ]
      },
      {
        "title": "Optimization Trials per Hour",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(emuses_optimization_trials_total[1h]) * 3600",
            "legendFormat": "{{stage}} trials/hour"
          }
        ]
      },
      {
        "title": "Dataset Size Distribution",
        "type": "histogram",
        "targets": [
          {
            "expr": "histogram_quantile(0.5, rate(emuses_dataset_size_bytes_bucket[1h]))",
            "legendFormat": "Median dataset size"
          }
        ]
      }
    ]
  }
}
```

### Phase 3: Distributed Tracing (Days 5-6)

#### Task 3.1: Tempo Integration and Custom Spans
**Duration**: 6 hours  
**Description**: Implement distributed tracing for scientific workflows

**Custom Tracing for Scientific Operations**:
```python
# emuses/observability/tracing.py
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
import functools

tracer = trace.get_tracer(__name__)

def trace_pipeline_stage(stage_name: str):
    """Decorator for tracing pipeline stages"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(
                f"pipeline.{stage_name}",
                attributes={
                    "pipeline.stage": stage_name,
                    "pipeline.function": func.__name__
                }
            ) as span:
                try:
                    # Add context information
                    if args and hasattr(args[0], '__dict__'):
                        context = args[0]
                        if hasattr(context, 'get'):
                            user_id = context.get('user_id')
                            if user_id:
                                span.set_attribute("user.id", str(user_id))
                            
                            dataset_name = context.get('dataset_name')
                            if dataset_name:
                                span.set_attribute("dataset.name", dataset_name)
                    
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                    
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
                    
        return wrapper
    return decorator

# Usage in pipeline stages
from emuses.observability.tracing import trace_pipeline_stage

class UMAPStage(PipelineStage):
    @trace_pipeline_stage("umap_optimization")
    def run(self, context):
        with tracer.start_as_current_span("umap.parameter_optimization") as span:
            span.set_attribute("optuna.n_trials", context.get("n_trials", 50))
            span.set_attribute("umap.n_neighbors_range", str(context.get("n_neighbors_range")))
            
            # Existing UMAP logic with detailed tracing
            for trial_num in range(context.get("n_trials", 50)):
                with tracer.start_as_current_span(f"umap.trial_{trial_num}") as trial_span:
                    trial_span.set_attribute("trial.number", trial_num)
                    # Run optimization trial
                    result = self._run_trial(trial_num, context)
                    trial_span.set_attribute("trial.score", result.score)
```

#### Task 3.2: Trace Correlation and Sampling
**Duration**: 4 hours  
**Description**: Configure intelligent sampling and correlation

**Sampling Configuration**:
```python
# emuses/observability/sampling.py
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased, StaticSampler, Decision
from opentelemetry.trace import TraceFlags
import random

class ScientificWorkflowSampler:
    """Custom sampler for scientific workloads"""
    
    def __init__(self):
        self.default_sampler = TraceIdRatioBased(0.1)  # 10% sampling
        self.error_sampler = StaticSampler(Decision.RECORD_AND_SAMPLE)
        self.scientific_sampler = TraceIdRatioBased(0.5)  # 50% for scientific ops
        
    def should_sample(self, context, trace_id, name, kind=None, attributes=None, links=None, trace_state=None):
        # Always sample errors
        if attributes and attributes.get("error") == "true":
            return self.error_sampler.should_sample(context, trace_id, name, kind, attributes, links, trace_state)
        
        # Higher sampling for scientific operations
        if name.startswith("pipeline.") or name.startswith("umap.") or name.startswith("hdbscan."):
            return self.scientific_sampler.should_sample(context, trace_id, name, kind, attributes, links, trace_state)
        
        # Default sampling for everything else
        return self.default_sampler.should_sample(context, trace_id, name, kind, attributes, links, trace_state)
```

### Phase 4: Alerting and Production Readiness (Day 7)

#### Task 4.1: Alerting Rules Configuration
**Duration**: 4 hours  
**Description**: Implement comprehensive alerting for operational issues

**Prometheus Alerting Rules**:
```yaml
# observability/alerts.yml
groups:
  - name: emuses.alerts
    rules:
      # System health alerts
      - alert: EMUSESAPIDown
        expr: up{job="emuses-api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "EMUSES API is down"
          description: "EMUSES API has been down for more than 1 minute"

      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors per second"

      # Scientific workflow alerts
      - alert: LongRunningPipeline
        expr: emuses_pipeline_duration_seconds > 3600
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Pipeline running longer than expected"
          description: "Pipeline {{ $labels.stage }} has been running for over 1 hour"

      - alert: HighMemoryUsage
        expr: emuses_memory_usage_bytes / 1024 / 1024 / 1024 > 16
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage in pipeline"
          description: "Pipeline stage {{ $labels.stage }} using {{ $value }}GB memory"

      # Multi-user service alerts
      - alert: AuthenticationFailureSpike
        expr: rate(http_requests_total{handler="/auth/jwt/login", status="401"}[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High authentication failure rate"
          description: "Authentication failures: {{ $value }} per second"
```

#### Task 4.2: Dashboard Provisioning and Documentation
**Duration**: 4 hours  
**Description**: Finalize dashboard configuration and create operational documentation

**Grafana Dashboard Provisioning**:
```yaml
# observability/grafana/dashboards/dashboard.yml
apiVersion: 1

providers:
  - name: 'EMUSES Dashboards'
    orgId: 1
    folder: 'EMUSES'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
```

**Operational Documentation**:
```markdown
# EMUSES Observability Operations Guide

## Dashboard Access
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090
- Tempo: http://localhost:3200

## Key Metrics to Monitor
1. **API Health**: Request rate, error rate, response time
2. **Scientific Pipelines**: Execution time, memory usage, optimization trials
3. **System Resources**: CPU, memory, disk usage
4. **User Activity**: Authentication rates, workspace usage

## Alert Response Procedures
1. **Critical Alerts**: Immediate response required (< 5 minutes)
2. **Warning Alerts**: Response within 30 minutes
3. **Info Alerts**: Review during business hours

## Troubleshooting Guide
- High error rates: Check application logs with correlation IDs
- Long-running pipelines: Review resource allocation and dataset size
- Authentication issues: Verify JWT token configuration and database connectivity
```

## Configuration Files Summary

### New Observability Files
1. `observability/otel-collector-config.yaml` - OpenTelemetry Collector configuration
2. `observability/prometheus.yml` - Prometheus scraping configuration
3. `observability/alerts.yml` - Alerting rules
4. `observability/tempo.yaml` - Tempo tracing configuration
5. `observability/grafana/datasources/` - Grafana data source configuration
6. `observability/grafana/dashboards/` - Pre-built dashboard definitions
7. `docker-compose.observability.yml` - Observability stack deployment

### Enhanced Application Files
1. `emuses/observability/__init__.py` - Core observability setup
2. `emuses/observability/metrics.py` - Custom metrics implementation
3. `emuses/observability/tracing.py` - Custom tracing utilities
4. `emuses/observability/logging.py` - Structured logging configuration
5. `emuses/observability/sampling.py` - Intelligent sampling strategies

### Modified Existing Files
1. `emuses/foundation_fastapi_service/app.py` - OpenTelemetry integration
2. `emuses/pipelines/umap_stage.py` - Custom metrics and tracing
3. `emuses/pipelines/heatmap_stage.py` - Pipeline instrumentation
4. `requirements.txt` - Observability dependencies

## Success Validation

### Functional Validation
- [ ] All services emit metrics to Prometheus
- [ ] Distributed traces appear in Tempo
- [ ] Grafana dashboards display real-time data
- [ ] Alerts trigger correctly for test scenarios
- [ ] Correlation IDs link logs, metrics, and traces

### Performance Validation
- [ ] < 5% performance overhead from instrumentation
- [ ] Dashboard queries respond in < 1 second
- [ ] Trace collection doesn't impact scientific computations
- [ ] Memory usage of observability stack < 2GB

### Operational Validation
- [ ] Alerts integrate with notification channels
- [ ] Dashboard permissions work correctly
- [ ] Data retention policies function as configured
- [ ] Backup and restore procedures documented

This implementation plan provides comprehensive observability for EMUSES while maintaining performance standards and enabling operational excellence for production deployments.