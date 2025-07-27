# EMUSES Multi-User LAD Implementation Context
**Companion to**: `MULTIUSER_LAD_PLAN.md`  
**Purpose**: Complete technical context for LAD session on multi-user service architecture  
**Branch**: `feat/multi-user-service` (future)

---

## 🔧 **CURRENT SINGLE-USER ARCHITECTURE ANALYSIS**

### **Service Lifecycle (Single-User)**:
```python
# Current auto-start pattern in emuses/cli/service_manager.py
class ServiceManager:
    def ensure_service_running(self):
        if not self.is_service_running():
            port = self.find_available_port()  # Starts at 8000, increments
            self.start_service(port)
        return self.get_service_url()

# Result: Each user gets isolated service instance
User A: http://localhost:8000 (PID 1234)
User B: http://localhost:8001 (PID 1235) 
User C: http://localhost:8002 (PID 1236)
```

### **Job Management (Single-User)**:
```python
# Current job handling in emuses/foundation_fastapi_service/job_manager.py
class JobManager:
    def __init__(self):
        self.jobs: Dict[str, JobStatus] = {}  # In-memory storage
        self.active_jobs: Set[str] = set()
    
    def submit_job(self, config: dict) -> str:
        job_id = str(uuid.uuid4())
        # No user context - single user assumed
        self.jobs[job_id] = JobStatus(id=job_id, status="pending", config=config)
        return job_id

# Current graceful shutdown (from Phase 1)
class SimpleShutdownHandler:
    def __init__(self, service_client, job_id):  # Single job context
        self.service_client = service_client
        self.job_id = job_id  # One job per CLI session
```

### **Data Storage (Single-User)**:
```python
# Current file-based storage pattern
output_folder = Path(args.output_folder)  # User specifies local path
models_path = output_folder / "models"
logs_path = output_folder / "log" 
# No user isolation - relies on file system permissions
```

---

## 🎯 **MULTI-USER ARCHITECTURE TRANSFORMATION**

### **Authentication System Implementation**:
```python
# NEW FILE: emuses/auth/models.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
import uuid
from datetime import datetime
from typing import Optional, List

class Base(DeclarativeBase):
    pass

class User(SQLAlchemyBaseUserTableUUID, Base):
    """Extended user model with EMUSES-specific fields."""
    __tablename__ = "users"
    
    # FastAPI-Users required fields (inherited)
    # id, email, hashed_password, is_active, is_superuser, is_verified
    
    # EMUSES-specific extensions
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    organization: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="user")  # user, admin, readonly, premium
    
    # Quota and limits
    max_concurrent_jobs: Mapped[int] = mapped_column(Integer, default=3)
    max_storage_gb: Mapped[int] = mapped_column(Integer, default=10)
    max_compute_hours_monthly: Mapped[int] = mapped_column(Integer, default=100)
    
    # Usage tracking
    current_storage_mb: Mapped[int] = mapped_column(Integer, default=0)
    compute_hours_used_this_month: Mapped[int] = mapped_column(Integer, default=0)
    last_reset_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    workspaces: Mapped[List["Workspace"]] = relationship("Workspace", back_populates="user")
    jobs: Mapped[List["TrainingJob"]] = relationship("TrainingJob", back_populates="user")

class UserSettings(Base):
    """User preferences and configuration."""
    __tablename__ = "user_settings"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    
    # Default EMUSES configuration preferences
    default_n_jobs: Mapped[int] = mapped_column(Integer, default=-1)
    default_optuna_trials: Mapped[int] = mapped_column(Integer, default=50)
    default_outer_folds: Mapped[int] = mapped_column(Integer, default=5)
    preferred_backend: Mapped[str] = mapped_column(String(50), default="loky")
    
    # Notification preferences
    email_on_job_completion: Mapped[bool] = mapped_column(Boolean, default=True)
    email_on_job_failure: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # UI preferences
    theme: Mapped[str] = mapped_column(String(50), default="light")
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")

# User database connection
async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)
```

### **Workspace Isolation System**:
```python
# NEW FILE: emuses/workspace/models.py
class Workspace(Base):
    """User workspace for organizing projects and datasets."""
    __tablename__ = "workspaces"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Storage configuration
    storage_path: Mapped[str] = mapped_column(String(512))  # e.g., /data/workspaces/{user_id}/{workspace_id}
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Sharing and collaboration (future enhancement)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    shared_with: Mapped[Optional[dict]] = mapped_column(JSON)  # {user_id: permission_level}
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user: Mapped[User] = relationship("User", back_populates="workspaces")
    datasets: Mapped[List["Dataset"]] = relationship("Dataset", back_populates="workspace", cascade="all, delete-orphan")
    jobs: Mapped[List["TrainingJob"]] = relationship("TrainingJob", back_populates="workspace", cascade="all, delete-orphan")

class Dataset(Base):
    """User datasets with metadata and versioning."""
    __tablename__ = "datasets"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # File information
    original_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(512))  # Relative to workspace storage
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    file_hash: Mapped[str] = mapped_column(String(64))  # SHA-256 for integrity
    
    # Dataset metadata
    dataset_type: Mapped[str] = mapped_column(String(50))  # features, labels, scores
    shape: Mapped[Optional[dict]] = mapped_column(JSON)  # {rows: int, cols: int}
    dtype_info: Mapped[Optional[dict]] = mapped_column(JSON)  # Column dtypes and stats
    
    # Versioning
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_dataset_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("datasets.id"))
    
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_accessed: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="datasets")
    jobs_using_dataset: Mapped[List["JobDatasetAssociation"]] = relationship("JobDatasetAssociation", back_populates="dataset")

class TrainingJob(Base):
    """User training jobs with full execution context."""
    __tablename__ = "training_jobs"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    
    # Job identification
    name: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON)  # User-defined tags for organization
    
    # Execution parameters
    job_type: Mapped[str] = mapped_column(String(50))  # full, umap, heatmap, prediction
    parameters: Mapped[dict] = mapped_column(JSON)  # Complete EMUSES configuration
    
    # Status tracking
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, queued, running, completed, failed, cancelled
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0)
    current_stage: Mapped[Optional[str]] = mapped_column(String(100))  # e.g., "umap_optimization", "heatmap_training"
    current_trial: Mapped[Optional[int]] = mapped_column(Integer)
    total_trials: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Execution context
    worker_id: Mapped[Optional[str]] = mapped_column(String(100))  # Celery worker ID
    execution_node: Mapped[Optional[str]] = mapped_column(String(100))  # Container/node info
    
    # Resource usage
    cpu_hours_used: Mapped[float] = mapped_column(Float, default=0.0)
    memory_peak_mb: Mapped[Optional[int]] = mapped_column(Integer)
    storage_used_mb: Mapped[int] = mapped_column(Integer, default=0)
    
    # Results and outputs
    results: Mapped[Optional[dict]] = mapped_column(JSON)  # Performance metrics, best parameters
    output_files: Mapped[Optional[dict]] = mapped_column(JSON)  # {file_type: file_path}
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_traceback: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    user: Mapped[User] = relationship("User", back_populates="jobs")
    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="jobs")
    datasets_used: Mapped[List["JobDatasetAssociation"]] = relationship("JobDatasetAssociation", back_populates="job")

class JobDatasetAssociation(Base):
    """Many-to-many relationship between jobs and datasets."""
    __tablename__ = "job_dataset_associations"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("training_jobs.id"), nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), nullable=False)
    usage_type: Mapped[str] = mapped_column(String(50))  # features, labels, scores
    
    job: Mapped[TrainingJob] = relationship("TrainingJob", back_populates="datasets_used")
    dataset: Mapped[Dataset] = relationship("Dataset", back_populates="jobs_using_dataset")
```

### **Enhanced Job Management with User Context**:
```python
# NEW FILE: emuses/jobs/multi_user_job_manager.py
from celery import Celery
from emuses.workspace.models import TrainingJob, User, Workspace
from emuses.auth.authentication import current_active_user
import asyncio
import psutil
from pathlib import Path

class MultiUserJobManager:
    """Enhanced job manager with user context and resource management."""
    
    def __init__(self, db_session: AsyncSession, celery_app: Celery):
        self.db = db_session
        self.celery = celery_app
    
    async def submit_job(
        self, 
        user: User, 
        workspace_id: uuid.UUID,
        job_config: dict,
        job_name: Optional[str] = None
    ) -> TrainingJob:
        """Submit job with user context and quota validation."""
        
        # 1. Validate user quotas
        await self._validate_user_quotas(user)
        
        # 2. Create workspace-isolated storage
        storage_path = await self._create_job_storage(user.id, workspace_id)
        
        # 3. Create job record
        job = TrainingJob(
            user_id=user.id,
            workspace_id=workspace_id,
            name=job_name or f"EMUSES Job {datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            job_type=job_config.get("job_type", "full"),
            parameters=job_config,
            status="pending",
            storage_path=str(storage_path)
        )
        
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        
        # 4. Queue for execution
        task = self.celery.send_task(
            "emuses.tasks.run_user_pipeline",
            args=[str(job.id), str(user.id), job_config],
            queue=self._get_user_queue(user)
        )
        
        job.worker_task_id = task.id
        job.status = "queued"
        job.queued_at = datetime.utcnow()
        await self.db.commit()
        
        return job
    
    async def _validate_user_quotas(self, user: User):
        """Validate user is within resource quotas."""
        # Check concurrent job limit
        active_jobs = await self.db.scalar(
            select(func.count(TrainingJob.id))
            .where(TrainingJob.user_id == user.id)
            .where(TrainingJob.status.in_(["pending", "queued", "running"]))
        )
        
        if active_jobs >= user.max_concurrent_jobs:
            raise HTTPException(
                status_code=429,
                detail=f"Maximum concurrent jobs ({user.max_concurrent_jobs}) reached"
            )
        
        # Check storage quota
        if user.current_storage_mb > user.max_storage_gb * 1024:
            raise HTTPException(
                status_code=507,
                detail=f"Storage quota ({user.max_storage_gb}GB) exceeded"
            )
        
        # Check monthly compute hours
        if user.compute_hours_used_this_month >= user.max_compute_hours_monthly:
            raise HTTPException(
                status_code=429,
                detail=f"Monthly compute quota ({user.max_compute_hours_monthly}h) exceeded"
            )
    
    async def _create_job_storage(self, user_id: uuid.UUID, workspace_id: uuid.UUID) -> Path:
        """Create isolated storage directory for job."""
        job_id = uuid.uuid4()
        storage_path = Path(f"/data/workspaces/{user_id}/{workspace_id}/jobs/{job_id}")
        storage_path.mkdir(parents=True, exist_ok=True)
        
        # Create standard subdirectories
        (storage_path / "input").mkdir(exist_ok=True)
        (storage_path / "output").mkdir(exist_ok=True)
        (storage_path / "models").mkdir(exist_ok=True)
        (storage_path / "logs").mkdir(exist_ok=True)
        
        return storage_path
    
    def _get_user_queue(self, user: User) -> str:
        """Determine appropriate queue based on user tier."""
        if user.role == "premium":
            return "high_priority"
        elif user.role == "admin":
            return "admin_queue"
        else:
            return "default_queue"
    
    async def get_user_jobs(
        self, 
        user: User, 
        workspace_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[TrainingJob]:
        """Get jobs for user with optional filtering."""
        query = select(TrainingJob).where(TrainingJob.user_id == user.id)
        
        if workspace_id:
            query = query.where(TrainingJob.workspace_id == workspace_id)
        if status:
            query = query.where(TrainingJob.status == status)
        
        query = query.order_by(TrainingJob.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def cancel_user_job(self, user: User, job_id: uuid.UUID) -> bool:
        """Cancel job with user ownership validation."""
        job = await self.db.get(TrainingJob, job_id)
        
        if not job or job.user_id != user.id:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.status not in ["pending", "queued", "running"]:
            raise HTTPException(status_code=400, detail="Job cannot be cancelled")
        
        # Cancel Celery task
        if job.worker_task_id:
            self.celery.control.revoke(job.worker_task_id, terminate=True)
        
        job.status = "cancelled"
        job.completed_at = datetime.utcnow()
        await self.db.commit()
        
        return True

# Enhanced shutdown handler for multi-user context
class MultiUserShutdownHandler:
    """Enhanced shutdown handler with user session awareness."""
    
    def __init__(self, service_client, user_session: dict, active_job_ids: List[str]):
        self.service_client = service_client
        self.user_session = user_session  # {user_id, session_id, workspace_id}
        self.active_job_ids = active_job_ids  # Only this user's jobs
    
    async def handle_interruption(self) -> bool:
        """Handle Ctrl+C with user-specific status display."""
        try:
            # Get status for user's jobs only
            user_jobs = []
            for job_id in self.active_job_ids:
                status = await self.service_client.get_job_status(job_id)
                if status:  # Job belongs to this user
                    user_jobs.append(status)
            
            print(f"\n🛑 EMUSES interrupted for user {self.user_session['user_id'][:8]}")
            
            if user_jobs:
                print(f"📊 Your active jobs:")
                for job in user_jobs:
                    print(f"  • {job.get('name', job['id'][:8])}: {job.get('progress', 0)}% complete")
            else:
                print("📊 No active jobs found")
            
            print(f"\n⚠️  Stopping will cancel YOUR jobs only.")
            print(f"   Other users' jobs will continue running.")
            
            response = input("\n❓ Cancel your jobs? [y/N]: ").lower().strip()
            return response in ['y', 'yes']
            
        except Exception as e:
            print(f"\n🛑 EMUSES interrupted!")
            print(f"⚠️  Cannot determine job status: {e}")
            response = input("\n❓ Cancel anyway? [y/N]: ").lower().strip()
            return response in ['y', 'yes']
    
    async def cleanup_and_stop(self):
        """Cancel only this user's jobs, leave others running."""
        try:
            cancelled_jobs = []
            for job_id in self.active_job_ids:
                try:
                    await self.service_client.cancel_job(job_id)
                    cancelled_jobs.append(job_id)
                except Exception as e:
                    print(f"⚠️  Could not cancel job {job_id[:8]}: {e}")
            
            if cancelled_jobs:
                print(f"✅ Cancelled {len(cancelled_jobs)} of your jobs")
            print("✅ Other users' jobs continue running")
            
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")
            print("✅ CLI session terminated")
```

### **Production Deployment Architecture**:
```python
# NEW FILE: emuses/deployment/docker_config.py
"""Production deployment configuration management."""

import os
from pathlib import Path
from typing import Optional

class ProductionConfig:
    """Production environment configuration."""
    
    # Database configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://emuses:password@postgres:5432/emuses")
    
    # Redis configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379")
    
    # Authentication
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY")  # Required in production
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
    
    # File storage
    DATA_ROOT: Path = Path(os.getenv("DATA_ROOT", "/app/data"))
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))
    
    # Worker configuration
    CELERY_BROKER_URL: str = REDIS_URL
    CELERY_RESULT_BACKEND: str = REDIS_URL
    WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "4"))
    
    # Rate limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_RPM", "60"))
    
    # Monitoring
    PROMETHEUS_ENABLED: bool = os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Email notifications (optional)
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: Optional[str] = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    
    @classmethod
    def validate(cls):
        """Validate required configuration for production."""
        required_vars = ["JWT_SECRET_KEY"]
        missing = [var for var in required_vars if not getattr(cls, var)]
        
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")
        
        # Ensure data directories exist
        cls.DATA_ROOT.mkdir(parents=True, exist_ok=True)
        (cls.DATA_ROOT / "workspaces").mkdir(exist_ok=True)
        (cls.DATA_ROOT / "uploads").mkdir(exist_ok=True)
        (cls.DATA_ROOT / "logs").mkdir(exist_ok=True)

# Docker health check endpoint
# NEW FILE: emuses/monitoring/health.py
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from emuses.database import get_session
import redis
import asyncio

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    """Comprehensive health check for production deployment."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # Database connectivity
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
            health_status["checks"]["database"] = "healthy"
    except Exception as e:
        health_status["checks"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Redis connectivity
    try:
        r = redis.from_url(ProductionConfig.REDIS_URL)
        r.ping()
        health_status["checks"]["redis"] = "healthy"
    except Exception as e:
        health_status["checks"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # File system access
    try:
        test_file = ProductionConfig.DATA_ROOT / "health_check.tmp"
        test_file.write_text("test")
        test_file.unlink()
        health_status["checks"]["filesystem"] = "healthy"
    except Exception as e:
        health_status["checks"]["filesystem"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    if health_status["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status

@router.get("/metrics")
async def get_metrics():
    """Prometheus-compatible metrics endpoint."""
    # This would integrate with prometheus_client
    # Return metrics in Prometheus format
    pass
```

---

## 🧪 **COMPREHENSIVE TESTING FRAMEWORK**

### **Multi-User Integration Tests**:
```python
# tests/integration/test_multi_user_scenarios.py
import pytest
import asyncio
from httpx import AsyncClient
from emuses.app import app
from emuses.database import get_session

class TestMultiUserIntegration:
    """Test realistic multi-user scenarios."""
    
    @pytest.mark.asyncio
    async def test_concurrent_users_different_workspaces(self):
        """Test multiple users working in isolated workspaces."""
        # Create 5 users
        users = []
        for i in range(5):
            user_data = {
                "email": f"researcher{i}@university.edu",
                "password": "secure_password",
                "organization": f"Lab {i}"
            }
            users.append(await self.create_test_user(user_data))
        
        # Each user submits job concurrently
        async def submit_user_job(user_token, dataset_name):
            async with AsyncClient(app=app, base_url="http://test") as ac:
                # Upload dataset
                dataset_response = await ac.post(
                    "/workspace/datasets/upload",
                    headers={"Authorization": f"Bearer {user_token}"},
                    files={"file": (dataset_name, self.generate_test_data())},
                    data={"name": dataset_name}
                )
                
                # Submit job
                job_response = await ac.post(
                    "/workspace/jobs",
                    headers={"Authorization": f"Bearer {user_token}"},
                    json={
                        "name": f"Job for {dataset_name}",
                        "parameters": {
                            "job_type": "full",
                            "n_jobs": 2,
                            "optuna_trials": 10
                        }
                    }
                )
                return job_response
        
        # Submit all jobs concurrently
        tasks = [
            submit_user_job(user["token"], f"dataset_{i}")
            for i, user in enumerate(users)
        ]
        responses = await asyncio.gather(*tasks)
        
        # Verify all submissions succeeded
        assert all(r.status_code == 201 for r in responses), "All job submissions should succeed"
        
        # Verify workspace isolation - each user sees only their job
        for i, user in enumerate(users):
            async with AsyncClient(app=app, base_url="http://test") as ac:
                jobs_response = await ac.get(
                    "/workspace/jobs",
                    headers={"Authorization": f"Bearer {user['token']}"}
                )
                user_jobs = jobs_response.json()
                assert len(user_jobs) == 1, f"User {i} should see exactly 1 job"
                assert user_jobs[0]["name"] == f"Job for dataset_{i}", "User should see correct job"
    
    @pytest.mark.asyncio 
    async def test_quota_enforcement_across_users(self):
        """Test quota limits work correctly with multiple users."""
        # Create user with quota limit of 2 jobs
        user = await self.create_test_user({
            "email": "quota_user@test.com",
            "password": "test123",
            "max_concurrent_jobs": 2
        })
        
        # Submit jobs up to quota
        job_responses = []
        for i in range(2):
            response = await self.submit_test_job(user["token"], f"job_{i}")
            assert response.status_code == 201
            job_responses.append(response)
        
        # Third job should be rejected due to quota
        response = await self.submit_test_job(user["token"], "job_overflow")
        assert response.status_code == 429
        assert "quota" in response.json()["detail"].lower()
        
        # Complete one job, then quota should allow new submission
        job_id = job_responses[0].json()["id"]
        await self.complete_test_job(job_id)
        
        response = await self.submit_test_job(user["token"], "job_after_completion")
        assert response.status_code == 201, "Should allow job after one completes"
    
    @pytest.mark.asyncio
    async def test_admin_access_controls(self):
        """Test admin users can access admin endpoints."""
        # Create admin and regular user
        admin_user = await self.create_test_user({
            "email": "admin@emuses.org",
            "password": "admin123",
            "role": "admin"
        })
        
        regular_user = await self.create_test_user({
            "email": "user@test.com", 
            "password": "user123",
            "role": "user"
        })
        
        # Admin should access admin endpoints
        async with AsyncClient(app=app, base_url="http://test") as ac:
            admin_response = await ac.get(
                "/admin/users",
                headers={"Authorization": f"Bearer {admin_user['token']}"}
            )
            assert admin_response.status_code == 200
            
            # Regular user should be denied
            user_response = await ac.get(
                "/admin/users",
                headers={"Authorization": f"Bearer {regular_user['token']}"}
            )
            assert user_response.status_code == 403

class TestWorkspaceIsolation:
    """Test workspace data isolation between users."""
    
    @pytest.mark.asyncio
    async def test_dataset_isolation(self):
        """Test users cannot access each other's datasets."""
        user1 = await self.create_test_user({"email": "user1@test.com"})
        user2 = await self.create_test_user({"email": "user2@test.com"})
        
        # User 1 uploads dataset
        async with AsyncClient(app=app, base_url="http://test") as ac:
            upload_response = await ac.post(
                "/workspace/datasets/upload",
                headers={"Authorization": f"Bearer {user1['token']}"},
                files={"file": ("data.csv", self.generate_test_data())},
                data={"name": "sensitive_data"}
            )
            dataset_id = upload_response.json()["id"]
        
        # User 2 should not be able to access User 1's dataset
        async with AsyncClient(app=app, base_url="http://test") as ac:
            access_response = await ac.get(
                f"/workspace/datasets/{dataset_id}",
                headers={"Authorization": f"Bearer {user2['token']}"}
            )
            assert access_response.status_code == 404, "User 2 should not find User 1's dataset"
            
            # User 2 should not see dataset in their list
            list_response = await ac.get(
                "/workspace/datasets",
                headers={"Authorization": f"Bearer {user2['token']}"}
            )
            datasets = list_response.json()
            assert len(datasets) == 0, "User 2 should see empty dataset list"
    
    @pytest.mark.asyncio
    async def test_job_results_isolation(self):
        """Test job results are isolated between users."""
        user1 = await self.create_test_user({"email": "user1@test.com"})
        user2 = await self.create_test_user({"email": "user2@test.com"})
        
        # User 1 submits and completes job
        job1_response = await self.submit_and_complete_job(user1["token"], "job1")
        job1_id = job1_response["id"]
        
        # User 2 should not be able to access User 1's job results
        async with AsyncClient(app=app, base_url="http://test") as ac:
            results_response = await ac.get(
                f"/workspace/jobs/{job1_id}/results",
                headers={"Authorization": f"Bearer {user2['token']}"}
            )
            assert results_response.status_code == 404, "User 2 should not access User 1's results"
```

### **Performance and Load Testing**:
```python
# tests/performance/test_multi_user_load.py
import pytest
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
import statistics

class TestMultiUserPerformance:
    """Test system performance under multi-user load."""
    
    @pytest.mark.asyncio
    async def test_concurrent_user_registration(self):
        """Test system handles concurrent user registrations."""
        start_time = time.time()
        
        # Simulate 50 users registering simultaneously
        async def register_user(user_id):
            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post("/auth/register", json={
                    "email": f"loadtest_user_{user_id}@test.com",
                    "password": "testpass123",
                    "organization": f"Test Org {user_id}"
                })
                return response.status_code, time.time() - start_time
        
        tasks = [register_user(i) for i in range(50)]
        results = await asyncio.gather(*tasks)
        
        # Analyze results
        status_codes = [result[0] for result in results]
        response_times = [result[1] for result in results]
        
        success_rate = sum(1 for code in status_codes if code == 201) / len(status_codes)
        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)
        
        assert success_rate >= 0.95, f"Success rate {success_rate:.2%} below 95%"
        assert avg_response_time < 2.0, f"Average response time {avg_response_time:.2f}s too high"
        assert max_response_time < 5.0, f"Max response time {max_response_time:.2f}s too high"
    
    @pytest.mark.asyncio
    async def test_concurrent_job_submissions(self):
        """Test system handles concurrent job submissions."""
        # Create 20 users
        users = []
        for i in range(20):
            user = await self.create_test_user({"email": f"concurrent_user_{i}@test.com"})
            users.append(user)
        
        # Each user submits 3 jobs concurrently
        async def submit_user_jobs(user_token, user_id):
            submission_times = []
            
            for job_num in range(3):
                start_time = time.time()
                response = await self.submit_test_job(user_token, f"user_{user_id}_job_{job_num}")
                submission_time = time.time() - start_time
                submission_times.append((response.status_code, submission_time))
            
            return submission_times
        
        # Submit all jobs concurrently (20 users × 3 jobs = 60 concurrent submissions)
        tasks = [submit_user_jobs(user["token"], i) for i, user in enumerate(users)]
        all_results = await asyncio.gather(*tasks)
        
        # Flatten results
        all_submissions = [item for sublist in all_results for item in sublist]
        status_codes = [result[0] for result in all_submissions]
        submission_times = [result[1] for result in all_submissions]
        
        success_rate = sum(1 for code in status_codes if code == 201) / len(status_codes)
        avg_submission_time = statistics.mean(submission_times)
        
        assert success_rate >= 0.90, f"Job submission success rate {success_rate:.2%} below 90%"
        assert avg_submission_time < 1.0, f"Average submission time {avg_submission_time:.2f}s too high"
    
    @pytest.mark.asyncio 
    async def test_database_performance_under_load(self):
        """Test database performance with concurrent operations."""
        # Create users and submit queries concurrently
        async def concurrent_database_ops():
            async with AsyncClient(app=app, base_url="http://test") as ac:
                # Simulate realistic user operations
                operations = [
                    ac.get("/workspace/datasets"),  # List datasets
                    ac.get("/workspace/jobs"),      # List jobs
                    ac.get("/workspace/jobs?status=running"),  # Filtered job list
                    ac.post("/workspace/jobs", json={"parameters": {"n_jobs": 1}})  # Submit job
                ]
                
                start_time = time.time()
                responses = await asyncio.gather(*operations, return_exceptions=True)
                total_time = time.time() - start_time
                
                return total_time, responses
        
        # Run operations for multiple users concurrently
        user_tokens = [
            (await self.create_test_user({"email": f"db_test_user_{i}@test.com"}))["token"]
            for i in range(10)
        ]
        
        tasks = [concurrent_database_ops() for _ in user_tokens]
        results = await asyncio.gather(*tasks)
        
        operation_times = [result[0] for result in results]
        avg_operation_time = statistics.mean(operation_times)
        
        assert avg_operation_time < 2.0, f"Database operations too slow: {avg_operation_time:.2f}s"
```

---

## 📚 **IMPLEMENTATION DEPENDENCIES AND REFERENCES**

### **Required Python Packages**:
```python
# Core FastAPI and authentication
fastapi[all]>=0.104.0                        # Latest FastAPI with all features
fastapi-users[sqlalchemy,oauth]>=12.1.0      # Complete user management system
uvicorn[standard]>=0.24.0                    # Production ASGI server

# Database and ORM
sqlalchemy[asyncio]>=2.0.0                   # Async SQLAlchemy ORM
alembic>=1.12.0                              # Database migrations
asyncpg>=0.28.0                              # Async PostgreSQL driver
psycopg2-binary>=2.9.0                       # PostgreSQL adapter (backup)

# Authentication and security
passlib[bcrypt]>=1.7.4                       # Password hashing
python-jose[cryptography]>=3.3.0             # JWT handling
python-multipart>=0.0.6                      # Form data parsing

# Background tasks and caching
celery[redis]>=5.3.0                         # Distributed task queue
redis>=5.0.0                                 # In-memory data store
flower>=2.0.0                                # Celery monitoring

# File handling and storage
aiofiles>=23.2.0                             # Async file operations
python-magic>=0.4.27                         # File type detection

# Monitoring and logging
prometheus-client>=0.17.0                    # Metrics collection
structlog>=23.1.0                            # Structured logging
sentry-sdk[fastapi]>=1.32.0                  # Error tracking (optional)

# Development and testing
pytest>=7.4.0                                # Testing framework
pytest-asyncio>=0.21.0                       # Async test support
httpx>=0.25.0                                # Async HTTP client for tests
factory-boy>=3.3.0                           # Test data factories
```

### **Key Implementation Files to Study**:
```bash
# Current service architecture (for extension)
emuses/foundation_fastapi_service/app.py         # Main FastAPI app structure
emuses/foundation_fastapi_service/models.py      # Current data models
emuses/foundation_fastapi_service/job_manager.py # Single-user job management

# Authentication and security patterns
emuses/cli/security.py                           # Current security utilities
emuses/cli/service_client.py                     # Client authentication

# Configuration and database
emuses/pipelines/pipeline_config.py              # Configuration management
emuses/cli/service_manager.py                    # Service lifecycle

# CLI integration points
emuses/cli/main.py                               # CLI entry points
emuses/cli/commands.py                           # Command structure

# Testing frameworks
tests/foundation_fastapi_service/                # Service testing patterns
tests/enhanced-cli-typer/                        # CLI testing patterns
```

### **Database Migration Strategy**:
```python
# migrations/env.py - Alembic configuration
from alembic import context
from sqlalchemy import engine_from_config, pool
from emuses.auth.models import Base as AuthBase
from emuses.workspace.models import Base as WorkspaceBase

# Combine all model bases for migration detection
target_metadata = [AuthBase.metadata, WorkspaceBase.metadata]

# Migration script example
# migrations/versions/001_create_user_tables.py
"""Create user authentication tables

Revision ID: 001
Revises: 
Create Date: 2025-07-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Create users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(320), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(1024), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_superuser', sa.Boolean(), default=False),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('full_name', sa.String(255)),
        sa.Column('organization', sa.String(255)),
        sa.Column('role', sa.String(50), default='user'),
        sa.Column('max_concurrent_jobs', sa.Integer(), default=3),
        sa.Column('max_storage_gb', sa.Integer(), default=10),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # Create indexes
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_role', 'users', ['role'])

def downgrade():
    op.drop_table('users')
```

### **Container Deployment Configuration**:
```yaml
# kubernetes/emuses-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: emuses-api
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
      containers:
      - name: emuses-api
        image: emuses/api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: emuses-secrets
              key: database-url
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: emuses-secrets
              key: jwt-secret
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
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

---
apiVersion: v1
kind: Service
metadata:
  name: emuses-api-service
spec:
  selector:
    app: emuses-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

---

**🎯 This comprehensive context provides all necessary technical details for implementing production-grade multi-user EMUSES service with authentication, workspace isolation, and scalable deployment architecture.**