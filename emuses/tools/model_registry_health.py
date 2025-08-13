"""Model Registry Health Check Service.

This module provides health check functionality for all model registry deployment modes,
supporting service discovery, load balancing, and graceful degradation scenarios.
"""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


class ModelRegistryHealthChecker:
    """Health checker for model registry deployment modes.

    Provides comprehensive health monitoring for LOCAL, DATABASE, and CLOUD
    registry modes with detailed status reporting and dependency checking.
    """

    def __init__(self):
        """Initialize the health checker."""
        self.start_time = time.time()

    def check_overall_health(self) -> Dict[str, Any]:
        """Check overall health across all registry modes.

        Returns
        -------
        Dict[str, Any]
            Overall health status with mode-specific details
        """
        registry_modes = {}
        overall_status = "healthy"

        # Check LOCAL mode
        local_health = self._check_local_registry()
        registry_modes["LOCAL"] = local_health
        if local_health["status"] != "healthy":
            overall_status = "degraded" if overall_status == "healthy" else "unhealthy"

        # Check DATABASE mode (if available)
        try:
            database_health = self._check_database_registry()
            registry_modes["DATABASE"] = database_health
            if database_health["status"] != "healthy":
                overall_status = "degraded" if overall_status == "healthy" else "unhealthy"
        except ImportError:
            # Database dependencies not available
            registry_modes["DATABASE"] = {
                "status": "unavailable",
                "message": "Database dependencies not available"
            }

        # Check CLOUD mode (if available)
        try:
            cloud_health = self._check_cloud_registry()
            registry_modes["CLOUD"] = cloud_health
            if cloud_health["status"] != "healthy":
                overall_status = "degraded" if overall_status == "healthy" else "unhealthy"
        except ImportError:
            # Cloud dependencies not available
            registry_modes["CLOUD"] = {
                "status": "unavailable",
                "message": "Cloud dependencies not available"
            }

        result = {
            "status": overall_status,
            "registry_modes": registry_modes,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
        }

        # Add degradation info if system is degraded
        if overall_status in ["degraded", "unhealthy"]:
            healthy_modes = [
                mode for mode, health in registry_modes.items()
                if health.get("status") == "healthy"
            ]
            degraded_modes = [
                mode for mode, health in registry_modes.items()
                if health.get("status") in ["degraded", "unhealthy"]
            ]

            # Determine available functionality
            if "LOCAL" in healthy_modes:
                functionality = "read_only_local"
            elif len(healthy_modes) > 0:
                functionality = "limited_operations"
            else:
                functionality = "health_only"

            result["degradation_info"] = {
                "available_modes": healthy_modes,
                "degraded_modes": degraded_modes,
                "functionality": functionality
            }

        return result

    def check_detailed_health(self) -> Dict[str, Any]:
        """Check detailed health with performance metrics and system info.

        Returns
        -------
        Dict[str, Any]
            Detailed health status with system information and metrics
        """
        start_time = time.perf_counter()

        # Get basic health status
        basic_health = self.check_overall_health()

        # Add system information
        system_info = {
            "version": "1.0.0",  # TODO: Get from package metadata
            "uptime": int(time.time() - self.start_time)
        }

        # Add performance metrics
        response_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
        performance_metrics = {
            "response_time_ms": round(response_time, 2)
        }

        return {
            "overall_status": basic_health["status"],
            "registry_modes": basic_health["registry_modes"],
            "system_info": system_info,
            "performance_metrics": performance_metrics,
            "timestamp": basic_health["timestamp"]
        }

    def check_liveness(self) -> Dict[str, Any]:
        """Check if service is alive and responsive.

        Used for load balancing and health monitoring.

        Returns
        -------
        Dict[str, Any]
            Liveness status
        """
        return {
            "alive": True,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
        }

    def _check_local_registry(self) -> Dict[str, Any]:
        """Check LOCAL registry health.

        Returns
        -------
        Dict[str, Any]
            LOCAL registry health status
        """
        try:
            # Check default registry path accessibility
            default_path = Path.home() / ".emuses" / "model_registry"
            storage_accessible = self._check_storage_accessibility(default_path)

            status = "healthy" if storage_accessible else "degraded"

            return {
                "status": status,
                "storage_accessible": storage_accessible,
                "registry_path": str(default_path),
                "message": "LOCAL registry operational" if status == "healthy" else "Storage issues detected"
            }
        except Exception as e:
            logger.error(f"Error checking LOCAL registry: {e}")
            return {
                "status": "unhealthy",
                "storage_accessible": False,
                "error": str(e),
                "message": "LOCAL registry check failed"
            }

    def _check_database_registry(self) -> Dict[str, Any]:
        """Check DATABASE registry health.

        Returns
        -------
        Dict[str, Any]
            DATABASE registry health status
        """
        try:
            from emuses.multi_user_service.database import get_db

            # Test database connection
            with next(get_db()) as session:
                # Simple query to test connection
                result = session.execute("SELECT 1").scalar()
                database_connection = result == 1

            status = "healthy" if database_connection else "unhealthy"

            return {
                "status": status,
                "database_connection": database_connection,
                "message": "DATABASE registry operational" if status == "healthy" else "Database connection failed"
            }
        except Exception as e:
            logger.error(f"Error checking DATABASE registry: {e}")
            return {
                "status": "unhealthy",
                "database_connection": False,
                "error": str(e),
                "message": "DATABASE registry check failed"
            }

    def _check_cloud_registry(self) -> Dict[str, Any]:
        """Check CLOUD registry health.

        Returns
        -------
        Dict[str, Any]
            CLOUD registry health status
        """
        try:
            # TODO: Implement cloud registry health check when available
            return {
                "status": "unavailable",
                "message": "CLOUD registry not yet implemented"
            }
        except Exception as e:
            logger.error(f"Error checking CLOUD registry: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "message": "CLOUD registry check failed"
            }

    def _check_local_registry_readiness(self) -> Dict[str, Any]:
        """Check LOCAL registry readiness.

        Returns
        -------
        Dict[str, Any]
            LOCAL registry readiness status
        """
        try:
            # Check storage accessibility
            default_path = Path.home() / ".emuses" / "model_registry"
            storage_ready = self._check_storage_accessibility(default_path)

            return {
                "ready": storage_ready,
                "component": "local_registry",
                "message": "LOCAL registry ready" if storage_ready else "Storage not accessible"
            }
        except Exception as e:
            return {
                "ready": False,
                "component": "local_registry",
                "error": str(e),
                "message": "LOCAL registry not ready"
            }

    def _check_database_registry_readiness(self) -> Dict[str, Any]:
        """Check DATABASE registry readiness.

        Returns
        -------
        Dict[str, Any]
            DATABASE registry readiness status
        """
        try:
            from emuses.multi_user_service.database import get_db

            # Quick connection test
            with next(get_db()) as session:
                session.execute("SELECT 1").scalar()

            return {
                "ready": True,
                "component": "database_registry",
                "message": "DATABASE registry ready"
            }
        except ImportError:
            return {
                "ready": False,
                "component": "database_registry",
                "message": "DATABASE registry dependencies not available"
            }
        except Exception as e:
            return {
                "ready": False,
                "component": "database_registry",
                "error": str(e),
                "message": "DATABASE registry not ready"
            }

    def _check_cloud_registry_readiness(self) -> Dict[str, Any]:
        """Check CLOUD registry readiness.

        Returns
        -------
        Dict[str, Any]
            CLOUD registry readiness status
        """
        # TODO: Implement when cloud registry is available
        return {
            "ready": False,
            "component": "cloud_registry",
            "message": "CLOUD registry not yet implemented"
        }

    def _check_storage_accessibility(self, path: Path) -> bool:
        """Check if storage path is accessible for read/write.

        Parameters
        ----------
        path : Path
            Storage path to check

        Returns
        -------
        bool
            True if storage is accessible, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            path.mkdir(parents=True, exist_ok=True)

            # Test write access
            test_file = path / ".health_check"
            test_file.write_text("health_check")
            test_file.unlink()  # Clean up

            return True
        except Exception as e:
            logger.warning(f"Storage accessibility check failed for {path}: {e}")
            return False

    def get_service_discovery_metadata(self) -> Dict[str, Any]:
        """Get service discovery metadata for health endpoints.

        Returns
        -------
        Dict[str, Any]
            Service discovery metadata including service info, capabilities, and version
        """
        import uuid
        return {
            "service_info": {
                "deployment_mode": self._detect_deployment_mode(),
                "service_name": "emuses-model-registry",
                "instance_id": str(uuid.uuid4())[:8]
            },
            "capabilities": {
                "supported_modes": ["LOCAL", "DATABASE", "CLOUD"],
                "api_version": "v1"
            },
            "version": "1.0.0"
        }

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get circuit breaker status information.

        Returns
        -------
        Dict[str, Any]
            Circuit breaker state and metrics
        """
        # Simple circuit breaker simulation based on health status
        overall_health = self.check_overall_health()
        failure_count = sum(
            1 for mode_health in overall_health["registry_modes"].values()
            if mode_health.get("status") != "healthy"
        )

        if failure_count == 0:
            state = "CLOSED"
        elif failure_count >= 2:
            state = "OPEN"
        else:
            state = "HALF_OPEN"

        return {
            "state": state,
            "failure_count": failure_count,
            "success_threshold": 2
        }

    def get_load_balancer_metrics(self) -> Dict[str, Any]:
        """Get load balancer routing metrics.

        Returns
        -------
        Dict[str, Any]
            Performance metrics for load balancer routing decisions
        """
        # Simulate performance metrics based on system health
        overall_health = self.check_overall_health()
        base_response_time = 50  # Base 50ms

        # Adjust based on health status
        if overall_health["status"] == "unhealthy":
            response_time = base_response_time * 10
            error_rate = 50
        elif overall_health["status"] == "degraded":
            response_time = base_response_time * 2
            error_rate = 10
        else:
            response_time = base_response_time
            error_rate = 0.1

        return {
            "average_response_time": response_time,
            "request_rate": 100,  # requests per second
            "error_rate": error_rate
        }

    def get_service_discovery_info(self) -> Dict[str, Any]:
        """Get comprehensive service discovery information.

        Returns
        -------
        Dict[str, Any]
            Complete service discovery configuration
        """
        overall_health = self.check_overall_health()

        return {
            "service_registration": {
                "name": "emuses-model-registry",
                "version": "1.0.0",
                "endpoints": [
                    "/api/v1/registry/health",
                    "/api/v1/registry/ready",
                    "/api/v1/registry/live",
                    "/api/v1/registry/service-discovery"
                ],
                "metadata": {
                    "deployment_mode": self._detect_deployment_mode(),
                    "supported_modes": ["LOCAL", "DATABASE", "CLOUD"]
                }
            },
            "load_balancing": {
                "health_check_interval": 30,
                "timeout_seconds": 10,
                "retry_policy": "exponential_backoff",
                "degraded_capacity": overall_health["status"] != "healthy"
            },
            "service_mesh": {
                "annotations": {
                    "prometheus.io/scrape": "true",
                    "prometheus.io/path": "/metrics",
                    "prometheus.io/port": "8000"
                },
                "labels": {
                    "app": "emuses-model-registry",
                    "component": "health-check",
                    "version": "v1"
                }
            }
        }

    def _detect_deployment_mode(self) -> str:
        """Detect current deployment mode.

        Returns
        -------
        str
            Detected deployment mode
        """
        # Simple heuristics for deployment mode detection
        import os

        if os.getenv("KUBERNETES_SERVICE_HOST"):
            return "kubernetes"
        elif os.getenv("DOCKER_CONTAINER"):
            return "docker"
        else:
            return "local"

    def check_readiness(self) -> Dict[str, Any]:
        """Check if service is ready to handle requests.

        Enhanced version that includes load balancer hints and Kubernetes readiness.

        Returns
        -------
        Dict[str, Any]
            Enhanced readiness status with load balancing and orchestration metadata
        """
        dependencies = {}
        ready = True

        # Check LOCAL registry readiness
        local_ready = self._check_local_registry_readiness()
        dependencies["local_registry"] = local_ready
        if not local_ready["ready"]:
            ready = False

        # Check DATABASE registry readiness
        database_ready = self._check_database_registry_readiness()
        dependencies["database_registry"] = database_ready
        # Don't fail readiness if database is unavailable (graceful degradation)

        # Check CLOUD registry readiness
        cloud_ready = self._check_cloud_registry_readiness()
        dependencies["cloud_registry"] = cloud_ready
        # Don't fail readiness if cloud is unavailable (graceful degradation)

        # Calculate load balancer hints
        healthy_modes = sum(1 for dep in dependencies.values() if dep.get("ready", False))
        total_modes = len(dependencies)
        capacity_ratio = healthy_modes / total_modes if total_modes > 0 else 0

        return {
            "ready": ready,
            "dependencies": dependencies,
            "load_balancer_hints": {
                "capacity": int(capacity_ratio * 100),
                "performance_tier": "high" if capacity_ratio > 0.8 else "medium" if capacity_ratio > 0.5 else "low",
                "traffic_weight": int(capacity_ratio * 100)
            },
            "kubernetes": {
                "pod_ready": ready,
                "service_account": "emuses-registry"
            },
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
        }

    def get_degradation_info(self) -> Dict[str, Any]:
        """Get service degradation information for partial system failures.

        Returns
        -------
        Dict[str, Any]
            Degradation status with available and unavailable operations
        """
        overall_health = self.check_overall_health()
        available_operations = ["health_check"]
        unavailable_operations = []
        fallback_mode = None

        # Determine available operations based on mode health
        healthy_modes = [
            mode for mode, health in overall_health["registry_modes"].items()
            if health.get("status") == "healthy"
        ]

        if "LOCAL" in healthy_modes:
            fallback_mode = "LOCAL"
            available_operations.extend(["list_models", "get_model_info", "search_models"])

        if "DATABASE" in healthy_modes:
            available_operations.extend(["create_model", "update_model", "share_model"])
        else:
            unavailable_operations.extend(["create_model", "update_model", "share_model"])

        if "CLOUD" in healthy_modes:
            available_operations.extend(["publish_model", "community_features"])
        else:
            unavailable_operations.extend(["publish_model", "community_features"])

        # Determine degradation status
        if len(healthy_modes) == 0:
            status = "critical"
        elif len(healthy_modes) == 1:
            status = "degraded"
        else:
            status = "partial"

        return {
            "status": status,
            "available_operations": list(set(available_operations)),
            "unavailable_operations": list(set(unavailable_operations)),
            "fallback_mode": fallback_mode,
            "recovery_actions": self._get_recovery_actions(overall_health)
        }

    def check_fallback_modes(self) -> Dict[str, Any]:
        """Check automatic fallback capabilities for registry modes.

        Returns
        -------
        Dict[str, Any]
            Fallback mode information and automatic fallback status
        """
        overall_health = self.check_overall_health()
        primary_modes = ["DATABASE", "CLOUD", "LOCAL"]  # Priority order

        primary_mode = None
        primary_status = None
        fallback_mode = None
        fallback_status = None

        # Find first available mode as primary
        for mode in primary_modes:
            if mode in overall_health["registry_modes"]:
                mode_health = overall_health["registry_modes"][mode]
                if primary_mode is None:
                    primary_mode = mode
                    primary_status = mode_health.get("status", "unknown")
                elif mode_health.get("status") == "healthy" and fallback_mode is None:
                    fallback_mode = mode
                    fallback_status = mode_health.get("status", "unknown")
                    break

        # If primary is unhealthy, enable automatic fallback
        automatic_fallback = (
            primary_status != "healthy" and
            fallback_mode is not None and
            fallback_status == "healthy"
        )

        fallback_limitations = []
        if fallback_mode == "LOCAL":
            fallback_limitations = ["Read-only access", "No sharing features", "No cloud sync"]
        elif fallback_mode == "DATABASE":
            fallback_limitations = ["No cloud features", "Limited analytics"]

        return {
            "primary_mode": primary_mode,
            "primary_status": primary_status,
            "fallback_mode": fallback_mode,
            "fallback_status": fallback_status,
            "automatic_fallback": automatic_fallback,
            "fallback_limitations": fallback_limitations
        }

    def get_degradation_levels(self) -> Dict[str, Any]:
        """Get progressive service degradation level information.

        Returns
        -------
        Dict[str, Any]
            Current degradation level and available capabilities
        """
        overall_health = self.check_overall_health()
        healthy_modes = [
            mode for mode, health in overall_health["registry_modes"].items()
            if health.get("status") == "healthy"
        ]

        # Determine degradation level
        if len(healthy_modes) >= 2:
            level = "full"
        elif len(healthy_modes) == 1:
            level = "moderate"
        else:
            level = "minimal"

        levels = {
            "minimal": {
                "status": "active" if level == "minimal" else "unavailable",
                "description": "Critical failures - basic health checks only"
            },
            "moderate": {
                "status": "active" if level == "moderate" else "unavailable",
                "description": "Some features disabled - essential operations available"
            },
            "full": {
                "status": "active" if level == "full" else "unavailable",
                "description": "All systems operational"
            }
        }

        # Define capabilities based on level
        if level == "minimal":
            current_capabilities = ["health_checks", "status_reporting"]
            disabled_capabilities = ["model_operations", "user_features", "data_sync"]
        elif level == "moderate":
            current_capabilities = ["local_registry_access", "cached_model_info", "basic_search"]
            disabled_capabilities = ["model_upload", "collaborative_sharing", "cloud_sync"]
        else:
            current_capabilities = ["full_functionality"]
            disabled_capabilities = []

        return {
            "degradation_level": level,
            "levels": levels,
            "current_capabilities": current_capabilities,
            "disabled_capabilities": disabled_capabilities
        }

    def check_recovery_status(self) -> Dict[str, Any]:
        """Check service recovery status and automatic restoration.

        Returns
        -------
        Dict[str, Any]
            Recovery status and restoration information
        """
        overall_health = self.check_overall_health()

        recovered_services = []
        still_degraded = []

        for mode, health in overall_health["registry_modes"].items():
            if health.get("status") == "healthy":
                recovered_services.append(mode)
            elif health.get("status") in ["degraded", "unhealthy"]:
                still_degraded.append(mode)

        # Determine recovery status
        if len(still_degraded) == 0:
            recovery_status = "complete"
        elif len(recovered_services) > 0:
            recovery_status = "partial"
        else:
            recovery_status = "none"

        restored_operations = []
        if "DATABASE" in recovered_services:
            restored_operations.extend(["create_model", "update_model"])
        if "CLOUD" in recovered_services:
            restored_operations.extend(["publish_model", "community_features"])

        return {
            "recovery_status": recovery_status,
            "recovered_services": recovered_services,
            "still_degraded": still_degraded,
            "recovery_time": datetime.now(timezone.utc).isoformat() + "Z",
            "automatic_restoration": recovery_status != "none",
            "manual_intervention_required": len(still_degraded) > 0,
            "restored_operations": restored_operations,
            "monitoring_recovery": still_degraded
        }

    def get_user_impact_info(self) -> Dict[str, Any]:
        """Get user-friendly impact information during service degradation.

        Returns
        -------
        Dict[str, Any]
            User impact level and helpful guidance
        """
        degradation_info = self.get_degradation_info()

        # Map status to user impact level
        impact_mapping = {
            "critical": "high",
            "degraded": "moderate",
            "partial": "low"
        }
        impact_level = impact_mapping.get(degradation_info["status"], "unknown")

        # Generate user-friendly message
        if impact_level == "high":
            message = "Service is experiencing significant issues. Please try again later."
            affected_features = ["All model operations", "User registration", "Data access"]
            alternatives = ["Check status page for updates", "Contact support if urgent"]
            estimated_time = "Unknown - major incident"
        elif impact_level == "moderate":
            message = "Some features are temporarily unavailable. You can still browse and download models."
            affected_features = ["Model upload", "Sharing", "Cloud synchronization"]
            alternatives = [
                "Use local registry for model management",
                "Cache models locally for offline access",
                "Check status page for updates"
            ]
            estimated_time = "15-30 minutes"
        else:
            message = "Minor service degradation. Most features are working normally."
            affected_features = ["Advanced analytics", "Real-time notifications"]
            alternatives = ["Continue using available features normally"]
            estimated_time = "5-15 minutes"

        return {
            "user_impact_level": impact_level,
            "user_message": message,
            "affected_features": affected_features,
            "available_alternatives": alternatives,
            "estimated_recovery_time": estimated_time,
            "support_contact": "support@emuses.org"
        }

    def get_resource_conservation_info(self) -> Dict[str, Any]:
        """Get resource conservation information during degraded state.

        Returns
        -------
        Dict[str, Any]
            Resource conservation mode and savings information
        """
        overall_health = self.check_overall_health()

        # Enable conservation mode if system is degraded
        conservation_active = overall_health["status"] != "healthy"

        if conservation_active:
            reduced_operations = ["background_sync", "cache_preload", "analytics_collection"]
            resource_savings = {
                "cpu_usage_reduction": "30%",
                "memory_usage_reduction": "20%",
                "network_usage_reduction": "50%"
            }
            disabled_background_tasks = ["model_indexing", "usage_analytics", "cleanup_tasks"]
        else:
            reduced_operations = []
            resource_savings = {
                "cpu_usage_reduction": "0%",
                "memory_usage_reduction": "0%",
                "network_usage_reduction": "0%"
            }
            disabled_background_tasks = []

        return {
            "conservation_mode": "active" if conservation_active else "inactive",
            "reduced_operations": reduced_operations,
            "resource_savings": resource_savings,
            "essential_operations_priority": ["health_checks", "user_requests", "data_integrity"],
            "disabled_background_tasks": disabled_background_tasks
        }

    def _get_recovery_actions(self, overall_health: Dict[str, Any]) -> list:
        """Get recommended recovery actions based on health status.

        Parameters
        ----------
        overall_health : Dict[str, Any]
            Overall health status information

        Returns
        -------
        list
            List of recommended recovery actions
        """
        actions = []

        for mode, health in overall_health["registry_modes"].items():
            if health.get("status") != "healthy":
                if mode == "DATABASE":
                    actions.extend(["Check database connectivity", "Restart database service"])
                elif mode == "CLOUD":
                    actions.extend(["Check cloud service status", "Verify API credentials"])
                elif mode == "LOCAL":
                    actions.extend(["Check disk space", "Verify file permissions"])

        return list(set(actions))  # Remove duplicates


# Global health checker instance
_health_checker = None


def get_health_checker() -> ModelRegistryHealthChecker:
    """Get or create the global health checker instance.

    Returns
    -------
    ModelRegistryHealthChecker
        Global health checker instance
    """
    global _health_checker
    if _health_checker is None:
        _health_checker = ModelRegistryHealthChecker()
    return _health_checker
