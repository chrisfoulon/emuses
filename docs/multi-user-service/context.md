# Multi-User EMUSES Service - Codebase Context

## Level 1: Plain English Summary

The EMUSES codebase provides a robust foundation for implementing multi-user functionality. The existing architecture centers around a production-ready FastAPI service with comprehensive job management, enterprise-grade HTTP client patterns, and sophisticated CLI integration. The system currently operates in single-user mode but demonstrates excellent patterns for extending to multi-user environments.

**Key Components**:
- **FastAPI Service**: Production-ready API with rate limiting, CORS, and comprehensive error handling
- **Job Management**: Thread-safe job lifecycle with UUID-based isolation and atomic operations
- **CLI Integration**: Service-oriented architecture with auto-start capabilities and comprehensive CLI features
- **Security Framework**: Path validation, input sanitization, and directory traversal protection
- **Testing Infrastructure**: Professional pytest framework with comprehensive fixtures

**Integration Strategy**: The existing 65% foundation allows for an **ENHANCE + BUILD NEW** approach, where authentication and user workspace isolation are added without disrupting current functionality. **User decisions have simplified the implementation**: minimal user models, progressive authentication scope, CLI admin tools, and hybrid background processing reduce complexity while maintaining full functionality.

## Level 2: Key API Integration Points

| Component | Current State | Integration Point | User Context Extension |
|-----------|---------------|-------------------|------------------------|
| **FastAPI App** | Single-user service with middleware stack | Add authentication middleware after CORS | JWT token validation, user context injection |
| **JobManager** | Thread-safe job management with file-based storage | Extend constructor with user workspace | User-scoped job directories, ownership validation |
| **ServiceHTTPClient** | Circuit breaker patterns with rate limiting | Add authentication headers in `_request()` | Token management, user session handling |
| **CLI Commands** | Typer-based commands with service routing | Extend `_convert_typer_args_to_service_config()` | User workspace parameters, deployment mode detection |
| **StorageDirectoryFactory** | Environment-aware directory creation | Add `create_user_job_storage(user_id)` | User-isolated storage paths with secure permissions |
| **Error Handling** | Standardized exception handlers with error codes | Add authentication error handlers | User-friendly auth error messages, token refresh logic |
| **Rate Limiting** | IP-based rate limiting with slowapi | Extend to user-based rate limiting | Per-user quotas, role-based limits |
| **Security Utilities** | Path validation and input sanitization | Extend with user context validation | User workspace boundary enforcement |

## Level 3: Code Integration Examples

### FastAPI Authentication Middleware Integration

```python
# Current app.py structure (lines 15-20)
app = FastAPI(title="EMUSES Foundation FastAPI Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"])
app.add_middleware(RequestSizeLimiterMiddleware, max_size=1024**3)

# Extension point for authentication middleware
from fastapi_users import FastAPIUsers
from emuses.auth.models import User
from emuses.auth.auth_backend import auth_backend

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])
current_active_user = fastapi_users.current_user(active=True)

# Add authentication middleware after CORS, before rate limiting
app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt")
```

### User-Aware Job Manager Extension

```python
# Current JobManager initialization (job_manager.py:45)
class JobManager:
    def __init__(self, base_directory: Path):
        self.base_directory = base_directory
        self._locks = {}
        self._locks_lock = threading.Lock()

# Extension for user context
class MultiUserJobManager(JobManager):
    def __init__(self, base_directory: Path, user_id: Optional[str] = None):
        if user_id:
            # User-scoped storage: {base}/users/{user_id}/jobs/
            user_workspace = base_directory / "users" / secure_user_id(user_id) / "jobs"
            user_workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
            super().__init__(user_workspace)
        else:
            super().__init__(base_directory)  # Backward compatibility
        self.user_id = user_id
```

### CLI Authentication Parameter Handling

```python
# Current CLI parameter conversion (main.py:80)
def _convert_typer_args_to_service_config(**kwargs) -> dict:
    config = {}
    # Convert typer args to service format
    return config

# Extension for deployment modes
def _convert_typer_args_to_service_config(**kwargs) -> dict:
    config = {}
    
    # Deployment mode detection
    deployment_mode = os.getenv("EMUSES_DEPLOYMENT_MODE", "local")
    config["deployment_mode"] = deployment_mode
    
    # Add authentication context for multi-user modes
    if deployment_mode in ["multi_user", "production"]:
        config["user_token"] = get_stored_user_token()
        config["service_url"] = kwargs.get("service") or get_default_service_url(deployment_mode)
    
    return config
```

### HTTP Client Authentication Integration

```python
# Current HTTP client request method (service_client.py:120)
async def _request(self, method: str, endpoint: str, **kwargs):
    url = f"{self.base_url}/{endpoint.lstrip('/')}"
    kwargs.setdefault('timeout', self.timeout)
    
# Extension for authentication
async def _request(self, method: str, endpoint: str, **kwargs):
    url = f"{self.base_url}/{endpoint.lstrip('/')}"
    kwargs.setdefault('timeout', self.timeout)
    
    # Add authentication headers
    if self.auth_token:
        kwargs.setdefault('headers', {})['Authorization'] = f'Bearer {self.auth_token}'
    
    # Add user context to request
    if self.user_id:
        kwargs.setdefault('headers', {})['X-User-ID'] = self.user_id
```

### Environment-Based Configuration Extension

```python
# Current environment configuration (app.py:10-12)
TESTING_MODE = os.getenv("TESTING_MODE", "false").lower() == "true"
RATE_LIMITING_ENABLED = os.getenv("RATE_LIMITING_ENABLED", "true").lower() == "true"

# Multi-user configuration extension
class DeploymentConfig:
    deployment_mode: str = os.getenv("EMUSES_DEPLOYMENT_MODE", "local")
    auth_required: bool = deployment_mode in ["multi_user", "production"]
    local_mode: bool = deployment_mode == "local"
    
    # Database configuration (for multi-user modes)
    database_url: Optional[str] = os.getenv("DATABASE_URL") if auth_required else None
    # Redis removed based on Decision #4: Hybrid background processing approach
    
    # JWT configuration
    jwt_secret: Optional[str] = os.getenv("JWT_SECRET") if auth_required else None
```

## Maintenance Opportunities in Target Files

### High Priority (Address During Implementation)
- [ ] `foundation_fastapi_service/app.py:25` - CORS allows all origins (`allow_origins=["*"]`) - harden for production
- [ ] `cli/service_manager.py:150` - Hard-coded localhost binding - make configurable for production deployment
- [ ] `foundation_fastapi_service/job_manager.py:200` - Global job storage without user isolation - extend for multi-user

### Medium Priority (Consider for Boy Scout Rule)
- [ ] `cli/service_client.py:45` - Exception handling could be more specific for authentication errors
- [ ] `foundation_fastapi_service/models.py:30` - Job models lack user ownership fields - extend for multi-user
- [ ] `cli/main.py:60` - CLI lacks deployment mode detection - add environment-based mode switching

## Integration Architecture Summary

The existing codebase demonstrates production-ready patterns that align well with multi-user requirements:

**Strengths for Multi-User Extension**:
- Thread-safe job management with atomic operations
- Comprehensive security validation and input sanitization  
- Service-oriented architecture with clear separation of concerns
- Environment-based configuration with testing mode support
- Rich error handling with standardized response formats
- Professional testing framework with comprehensive fixtures

**Extension Strategy (Revised Based on User Decisions)**:
- **Authentication Layer**: Add FastAPI-Users middleware with progressive authentication scope (local=none, multi-user=selective, production=full)
- **User Workspace Isolation**: Extend JobManager with user-scoped storage directories using minimal user models
- **CLI Multi-Mode Support**: Add deployment mode detection and authentication parameter handling
- **Database Integration**: Simple user models with basic preferences (n_jobs, optuna_trials defaults)
- **Background Processing**: Hybrid approach using ProcessPoolExecutor (no Celery/Redis complexity)
- **Admin Interface**: CLI-based admin tools for research server environments
- **Backward Compatibility**: Maintain existing single-user workflows unchanged

**Simplified Implementation Benefits**:
- **Reduced complexity**: 6-8 days (from 10-14 days)
- **Lower maintenance**: No complex web dashboards or distributed task systems
- **Research-focused**: Architecture optimized for actual EMUSES usage patterns
- **Future-proof**: Can upgrade to more complex systems if needs evolve

The architecture supports gradual rollout with three deployment modes (local/multi-user/production) while preserving 100% backward compatibility with existing CLI workflows.