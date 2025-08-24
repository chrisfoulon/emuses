# EMUSES Architecture

Technical design overview of the EMUSES neuroimaging analysis platform, covering system architecture, core components, and integration patterns.

## System Overview

EMUSES is built as a modular, multi-interface platform that supports three primary deployment modes:

- **Individual Research**: Local CLI and Python API for single-user analysis
- **Research Labs**: Multi-user FastAPI service with workspace isolation
- **Scientific Community**: Cloud-native deployment with model registry

## Core Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interfaces                         │
├─────────────────┬─────────────────┬─────────────────────────┤
│   CLI Interface │   Python API    │   REST API / Web UI    │
│                 │                 │                         │
│  emuses.cli.*   │  Direct Import  │  FastAPI Service       │
└─────────────────┴─────────────────┴─────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────┐
│                  Pipeline Engine                           │
├─────────────────┬─────────────────┬─────────────────────────┤
│  Pipeline Core  │   Stage System  │   Job Management        │
│                 │                 │                         │
│  emuses.        │  - UMAPStage    │  - Background Tasks     │
│  pipelines.*    │  - HeatmapStage │  - Queue Management     │
│                 │  - InferenceStage│  - Progress Tracking   │
└─────────────────┴─────────────────┴─────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────┐
│                   Core Services                            │
├─────────────────┬─────────────────┬─────────────────────────┤
│  Model Registry │   Observability │   Security & Auth       │
│                 │                 │                         │
│  - Local Storage│  - Logging      │  - User Management      │
│  - Database     │  - Metrics      │  - Token Management     │
│  - Cloud Sync   │  - Health Check │  - Quota Management     │
└─────────────────┴─────────────────┴─────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────┐
│                Infrastructure Layer                        │
├─────────────────┬─────────────────┬─────────────────────────┤
│   Data Storage  │   Compute       │   External Integration  │
│                 │                 │                         │
│  - File System  │  - CPU/GPU      │  - FSL, BIDS            │
│  - Database     │  - Memory Mgmt  │  - Cloud Providers      │
│  - Cloud Storage│  - Parallelism  │  - Container Platforms  │
└─────────────────┴─────────────────┴─────────────────────────┘
```

## Component Architecture

### 1. User Interface Layer

#### **CLI Interface (`emuses.cli.*`)**
- **Entry Point**: `emuses.cli.main.py`
- **Commands**: Analysis, workspace, model management, admin
- **Features**: Rich output, shell completion, interactive mode
- **Target Users**: Researchers, power users

**Key Components**:
```python
├── main.py              # CLI entry point and command routing
├── commands.py          # Core analysis commands
├── models_commands.py   # Model registry CLI
├── workspace_commands.py# Workspace management
├── admin_commands.py    # Administrative functions
├── service_manager.py   # Service lifecycle management
└── rich_features.py     # Enhanced terminal output
```

#### **Python API**
- **Direct Import**: Import EMUSES modules directly
- **Pipeline API**: High-level pipeline interface
- **Component API**: Access to individual stages and tools
- **Target Users**: Developers, advanced researchers

#### **REST API (`emuses.api.*`)**
- **Framework**: FastAPI with automatic OpenAPI documentation
- **Authentication**: JWT-based with role-based access control
- **Endpoints**: Pipeline execution, model management, workspace operations
- **Target Users**: Web applications, integrations

### 2. Pipeline Engine

#### **Pipeline Core (`emuses.pipelines.*`)**

**Main Components**:
- **`EMUSESPipeline`**: Orchestrates multi-stage analysis workflows
- **`PipelineConfig`**: Configuration management and validation
- **`PipelineStage`**: Base class for all analysis stages

**Pipeline Execution Flow**:
```python
Input Data → Preprocessing → UMAP → Clustering → Prediction → Results
     ↓            ↓           ↓         ↓           ↓         ↓
Configuration → Validation → Execution → Results → Storage → Output
```

#### **Stage System**

Each stage implements the `PipelineStage` interface:

**Key Stages**:
- **UMAPStage**: Dimensionality reduction with optimization
- **HeatmapStage**: Cross-validation and model training  
- **[InferenceStage](inference_stage.md)**: Unified prediction processing

```python
class PipelineStage:
    def validate_input(self, data: Any) -> bool
    def execute(self, data: Any, config: Dict) -> StageResult
    def get_outputs(self) -> Dict[str, Any]
    def cleanup(self) -> None
```

**Available Stages**:
- **`UMAPStage`**: Dimensionality reduction with parameter optimization
- **`HeatmapStage`**: Correlation analysis and kernel regression
- **`InferenceStage`**: Machine learning model training and prediction

#### **Job Management**

**Single-User Mode** (`foundation_fastapi_service.job_manager`):
- In-memory job tracking
- Local file storage
- Direct execution

**Multi-User Mode** (`multi_user_service.job_manager`):
- Database-backed job persistence
- User isolation and quota management
- Background task processing

### 3. Core Services

#### **Model Registry System**

**Architecture**: Factory pattern with multiple backends

```python
ModelRegistryFactory
├── LocalModelRegistry      # File-based storage
├── DatabaseModelRegistry   # PostgreSQL backend  
└── CloudModelRegistry     # Cloud provider integration
```

**Key Features**:
- **Versioning**: Semantic versioning with metadata tracking
- **Caching**: Multi-level caching with TTL and LRU eviction
- **Security**: Access control, audit logging, GDPR compliance
- **Performance**: Query optimization, batch operations, streaming

#### **Observability (`emuses.observability.*`)**

**Logging System**:
- **Structured Logging**: JSON format with contextual information
- **Pipeline Context**: Track analysis progress and performance
- **Error Handling**: Comprehensive error tracking and reporting

**Metrics Collection**:
- **Performance Metrics**: Execution times, memory usage, throughput
- **Business Metrics**: Analysis success rates, user activity
- **System Metrics**: Resource utilization, queue lengths

**Health Monitoring**:
- **Component Health**: Pipeline stages, services, external dependencies
- **Graceful Degradation**: Fallback mechanisms for component failures
- **Automated Recovery**: Self-healing capabilities

#### **Security & Authentication (`multi_user_service.auth.*`)**

**User Management**:
- **Authentication**: JWT tokens, OAuth integration
- **Authorization**: Role-based access control (RBAC)
- **User Lifecycle**: Registration, profile management, deactivation

**Security Features**:
- **Token Management**: Secure token generation, rotation, revocation
- **Rate Limiting**: API endpoint protection
- **Audit Logging**: Security event tracking
- **Data Isolation**: User workspace separation

### 4. Data Processing Tools (`emuses.tools.*`)

#### **Core Analysis Tools**
- **`UMAP_utils.py`**: UMAP implementation and optimization
- **`clustering_utils.py`**: HDBSCAN and alternative clustering methods
- **`stats_utils.py`**: Statistical analysis and validation
- **`features_utils.py`**: Feature selection and engineering

#### **Data Management**
- **`data_preproc.py`**: Data preprocessing and normalization
- **`model_io.py`**: Model serialization and versioning
- **`storage_manager.py`**: File system and cloud storage management

#### **Specialized Components**
- **`academic_compliance.py`**: Research reproducibility features
- **`cloud_resilience.py`**: Fault tolerance and recovery
- **`parallelism_utils.py`**: Parallel processing optimization

## Deployment Architectures

### 1. Local Development

**Single Process**:
```
CLI/Python → Pipeline Engine → Local Storage
```

**Development Server**:
```
FastAPI → Pipeline Engine → Local Storage + Database
```

### 2. Lab Deployment

**Multi-User Service**:
```
Load Balancer → FastAPI Instances → Shared Database + Storage
                     ↓
Background Workers → Job Queue → Pipeline Engine
```

### 3. Cloud-Native Deployment

**Kubernetes Architecture**:
```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Web Tier      │  │  Application    │  │   Data Tier     │
│                 │  │     Tier        │  │                 │
│ - Load Balancer │→ │ - API Pods      │→ │ - PostgreSQL    │
│ - Ingress       │  │ - Worker Pods   │  │ - Redis Cache   │
│ - TLS Termination│  │ - Job Scheduler │  │ - Cloud Storage │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Data Flow Architecture

### Analysis Pipeline Data Flow

```
1. Input Data Validation
   ├── Format validation (CSV, JSON)
   ├── Schema validation
   └── Quality checks

2. Preprocessing Pipeline
   ├── Missing data handling
   ├── Normalization (robust, z-score, min-max)
   ├── Feature selection
   └── Outlier detection

3. Analysis Stages
   ├── UMAP: Dimensionality reduction
   │   ├── Parameter optimization
   │   ├── Embedding generation
   │   └── Quality metrics
   │
   ├── Clustering: Pattern discovery
   │   ├── HDBSCAN clustering
   │   ├── Cluster validation
   │   └── Stability analysis
   │
   └── Prediction: ML modeling
       ├── Model training
       ├── Cross-validation
       └── Feature importance

4. Results Generation
   ├── Statistical summaries
   ├── Interactive visualizations
   ├── Exportable reports
   └── Model artifacts
```

### Model Registry Data Flow

```
Model Creation → Validation → Storage → Versioning → Distribution
      ↓              ↓           ↓          ↓           ↓
  - Training    - Schema     - Local    - Semantic  - Download
  - Metadata    - Quality    - Database - Tagging   - Sharing
  - Artifacts   - Testing    - Cloud    - History   - Discovery
```

## Configuration Management

### Configuration Hierarchy

```
1. Default Configuration (emuses/config/*)
2. System Configuration (/etc/emuses/)
3. User Configuration (~/.emuses/)
4. Project Configuration (./emuses.yaml)
5. Runtime Parameters (CLI/API arguments)
```

### Key Configuration Files

```
emuses.yaml                 # Main configuration
├── pipeline:
│   ├── stages: [umap, clustering, prediction]
│   ├── parallelism: auto
│   └── cache_size: 1GB
├── storage:
│   ├── local_path: ./results
│   ├── database_url: postgresql://...
│   └── cloud_backend: aws
└── security:
    ├── auth_required: true
    ├── rate_limiting: 100/hour
    └── audit_logging: true
```

## Performance Considerations

### Scalability Design

**Horizontal Scaling**:
- Stateless API design
- Queue-based job processing
- Database connection pooling
- Shared cache layers

**Vertical Scaling**:
- Memory-efficient algorithms
- GPU acceleration support
- Parallel processing optimization
- Resource-aware scheduling

### Optimization Strategies

**Memory Management**:
- Streaming data processing for large datasets
- Configurable memory limits per job
- Garbage collection optimization
- Memory mapping for large files

**Compute Optimization**:
- Automatic GPU detection and usage
- CPU core utilization optimization
- Algorithm parameter tuning
- Caching intermediate results

## Security Architecture

### Data Security

**At Rest**:
- Database encryption
- File system encryption
- Secure key management
- Access audit trails

**In Transit**:
- TLS/SSL encryption
- API authentication
- Secure token transmission
- Network isolation

### Application Security

**Input Validation**:
- Schema validation for all inputs
- SQL injection prevention
- Path traversal protection
- Rate limiting and DDoS protection

**Access Control**:
- Role-based permissions
- Resource-level access control
- Workspace isolation
- Admin privilege separation

## Integration Patterns

### External Tool Integration

**Neuroimaging Tools**:
- FSL pipeline integration
- BIDS dataset support
- Connectome Workbench compatibility
- Custom tool plugin architecture

**Cloud Providers**:
- AWS S3, EC2, Lambda integration
- Google Cloud Storage and Compute
- Azure Blob Storage and VMs
- Multi-cloud deployment support

### Development Integration

**CI/CD Support**:
- Docker containerization
- Kubernetes deployment
- GitHub Actions workflows
- Automated testing and validation

**Monitoring Integration**:
- Prometheus metrics export
- Grafana dashboard templates
- ELK stack logging integration
- Custom monitoring solutions

## Future Architecture Evolution

### Planned Enhancements

**Microservices Architecture**:
- Service decomposition
- Independent scaling
- Fault isolation
- Technology diversity

**Event-Driven Architecture**:
- Asynchronous processing
- Event sourcing
- CQRS pattern
- Real-time updates

**AI/ML Pipeline Enhancement**:
- AutoML capabilities
- Hyperparameter optimization
- Model performance monitoring
- Automated model retraining

This architecture provides a robust foundation for neuroimaging research while maintaining flexibility for future enhancements and scaling requirements.