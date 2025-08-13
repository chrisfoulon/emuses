"""Model Registry Health Check Endpoints.

This module provides health check endpoints specifically for model registry
monitoring, service discovery, and load balancing purposes.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from emuses.tools.model_registry_health import get_health_checker

logger = logging.getLogger(__name__)


def get_registry_health_router() -> APIRouter:
    """Get model registry health check router.

    Returns
    -------
    APIRouter
        Configured health check router with all endpoints
    """
    router = APIRouter(prefix="/api/v1/registry", tags=["Registry Health"])

    @router.get("/health", response_model=Dict[str, Any])
    async def registry_health_check(
        service_discovery: Optional[bool] = Query(False, description="Include service discovery metadata"),
        include_circuit_breaker: Optional[bool] = Query(False, description="Include circuit breaker status")
    ):
        """Check health status of model registry across all deployment modes.

        Provides overall health status with mode-specific details for monitoring
        and service discovery purposes.

        Parameters
        ----------
        service_discovery : bool, optional
            If True, include service discovery metadata in response
        include_circuit_breaker : bool, optional
            If True, include circuit breaker status information

        Returns
        -------
        Dict[str, Any]
            Health status including overall status and registry mode details
        """
        try:
            health_checker = get_health_checker()
            health_data = health_checker.check_overall_health()

            # Add service discovery metadata if requested
            if service_discovery:
                health_data.update(health_checker.get_service_discovery_metadata())

            # Add circuit breaker information if requested
            if include_circuit_breaker:
                health_data["circuit_breaker"] = health_checker.get_circuit_breaker_status()

            return health_data
        except Exception as e:
            logger.error(f"Error checking registry health: {str(e)}")
            # Return degraded status instead of failing completely
            return {
                "status": "unhealthy",
                "registry_modes": {},
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/health/detailed", response_model=Dict[str, Any])
    async def registry_detailed_health_check():
        """Check detailed health status with system information and metrics.

        Provides comprehensive health information including system details,
        performance metrics, and extended diagnostic information for load balancing.

        Returns
        -------
        Dict[str, Any]
            Detailed health status with system and performance information
        """
        try:
            health_checker = get_health_checker()
            detailed_health = health_checker.check_detailed_health()

            # Add load balancer metrics
            detailed_health["load_balancer_metrics"] = health_checker.get_load_balancer_metrics()

            return detailed_health
        except Exception as e:
            logger.error(f"Error checking detailed registry health: {str(e)}")
            return {
                "overall_status": "unhealthy",
                "registry_modes": {},
                "system_info": {},
                "performance_metrics": {},
                "load_balancer_metrics": {
                    "average_response_time": 0,
                    "request_rate": 0,
                    "error_rate": 100
                },
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/ready", response_model=Dict[str, Any])
    async def registry_readiness_check():
        """Check if registry is ready to handle requests.

        Used for service discovery and rolling deployments to determine
        when the service is ready to receive traffic.

        Returns
        -------
        Dict[str, Any]
            Readiness status with dependency information and load balancer hints
        """
        try:
            health_checker = get_health_checker()
            readiness = health_checker.check_readiness()

            # Return appropriate HTTP status
            status_code = 200 if readiness["ready"] else 503
            return JSONResponse(
                status_code=status_code,
                content=readiness
            )
        except Exception as e:
            logger.error(f"Error checking registry readiness: {str(e)}")
            return JSONResponse(
                status_code=503,
                content={
                    "ready": False,
                    "dependencies": {},
                    "load_balancer_hints": {
                        "capacity": 0,
                        "performance_tier": "degraded",
                        "traffic_weight": 0
                    },
                    "kubernetes": {
                        "pod_ready": False,
                        "service_account": "emuses-registry"
                    },
                    "error": str(e),
                    "timestamp": datetime.now().isoformat() + "Z"
                }
            )

    @router.get("/live", response_model=Dict[str, Any])
    async def registry_liveness_check():
        """Check if registry is alive and responsive.

        Used for load balancing and health monitoring to determine
        if the service is functioning properly.

        Returns
        -------
        Dict[str, Any]
            Liveness status
        """
        try:
            health_checker = get_health_checker()
            return health_checker.check_liveness()
        except Exception as e:
            logger.error(f"Error checking registry liveness: {str(e)}")
            return {
                "alive": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/service-discovery", response_model=Dict[str, Any])
    async def service_discovery_info():
        """Provide comprehensive service discovery and load balancing configuration.

        Used by service discovery systems, load balancers, and container orchestration
        platforms to configure traffic routing and service management.

        Returns
        -------
        Dict[str, Any]
            Service discovery configuration including registration info,
            load balancing settings, and service mesh metadata
        """
        try:
            health_checker = get_health_checker()
            return health_checker.get_service_discovery_info()
        except Exception as e:
            logger.error(f"Error retrieving service discovery info: {str(e)}")
            return {
                "service_registration": {
                    "name": "emuses-model-registry",
                    "version": "1.0.0",
                    "endpoints": [],
                    "metadata": {}
                },
                "load_balancing": {
                    "health_check_interval": 30,
                    "timeout_seconds": 10,
                    "retry_policy": "exponential_backoff",
                    "degraded_capacity": True
                },
                "service_mesh": {
                    "annotations": {},
                    "labels": {}
                },
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/degradation-status", response_model=Dict[str, Any])
    async def registry_degradation_status():
        """Get service degradation status for partial system failures.

        Returns
        -------
        Dict[str, Any]
            Degradation status with available and unavailable operations
        """
        try:
            health_checker = get_health_checker()
            return health_checker.get_degradation_info()
        except Exception as e:
            logger.error(f"Error retrieving degradation status: {str(e)}")
            return {
                "status": "critical",
                "available_operations": ["health_check"],
                "unavailable_operations": ["all_registry_operations"],
                "fallback_mode": None,
                "recovery_actions": ["Contact system administrator"],
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/fallback-status", response_model=Dict[str, Any])
    async def registry_fallback_status():
        """Get automatic fallback capabilities and current fallback mode.

        Returns
        -------
        Dict[str, Any]
            Fallback mode information and automatic fallback status
        """
        try:
            health_checker = get_health_checker()
            return health_checker.check_fallback_modes()
        except Exception as e:
            logger.error(f"Error checking fallback status: {str(e)}")
            return {
                "primary_mode": "unknown",
                "primary_status": "unhealthy",
                "fallback_mode": None,
                "fallback_status": None,
                "automatic_fallback": False,
                "fallback_limitations": ["Service unavailable"],
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/degradation-levels", response_model=Dict[str, Any])
    async def registry_degradation_levels():
        """Get progressive service degradation level information.

        Returns
        -------
        Dict[str, Any]
            Current degradation level and available capabilities
        """
        try:
            health_checker = get_health_checker()
            return health_checker.get_degradation_levels()
        except Exception as e:
            logger.error(f"Error retrieving degradation levels: {str(e)}")
            return {
                "degradation_level": "minimal",
                "levels": {
                    "minimal": {"status": "active", "description": "Critical system failure"},
                    "moderate": {"status": "unavailable", "description": "Service unavailable"},
                    "full": {"status": "unavailable", "description": "Service unavailable"}
                },
                "current_capabilities": ["health_checks"],
                "disabled_capabilities": ["all_operations"],
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/recovery-status", response_model=Dict[str, Any])
    async def registry_recovery_status():
        """Get service recovery status and automatic restoration information.

        Returns
        -------
        Dict[str, Any]
            Recovery status and restoration information
        """
        try:
            health_checker = get_health_checker()
            return health_checker.check_recovery_status()
        except Exception as e:
            logger.error(f"Error checking recovery status: {str(e)}")
            return {
                "recovery_status": "none",
                "recovered_services": [],
                "still_degraded": ["all_services"],
                "recovery_time": datetime.now().isoformat() + "Z",
                "automatic_restoration": False,
                "manual_intervention_required": True,
                "restored_operations": [],
                "monitoring_recovery": [],
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/user-impact", response_model=Dict[str, Any])
    async def registry_user_impact():
        """Get user-friendly impact information during service degradation.

        Returns
        -------
        Dict[str, Any]
            User impact level and helpful guidance
        """
        try:
            health_checker = get_health_checker()
            return health_checker.get_user_impact_info()
        except Exception as e:
            logger.error(f"Error retrieving user impact info: {str(e)}")
            return {
                "user_impact_level": "high",
                "user_message": "Service is currently unavailable. Please try again later.",
                "affected_features": ["All features"],
                "available_alternatives": ["Contact support"],
                "estimated_recovery_time": "Unknown",
                "support_contact": "support@emuses.org",
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/resource-conservation", response_model=Dict[str, Any])
    async def registry_resource_conservation():
        """Get resource conservation information during degraded state.

        Returns
        -------
        Dict[str, Any]
            Resource conservation mode and savings information
        """
        try:
            health_checker = get_health_checker()
            return health_checker.get_resource_conservation_info()
        except Exception as e:
            logger.error(f"Error retrieving resource conservation info: {str(e)}")
            return {
                "conservation_mode": "active",
                "reduced_operations": ["all_operations"],
                "resource_savings": {
                    "cpu_usage_reduction": "100%",
                    "memory_usage_reduction": "100%",
                    "network_usage_reduction": "100%"
                },
                "essential_operations_priority": ["health_checks"],
                "disabled_background_tasks": ["all_tasks"],
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    return router


def setup_registry_health_endpoints(app):
    """Set up registry health check endpoints on FastAPI application.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance to configure
    """
    logger.info("Setting up registry health check endpoints")

    router = get_registry_health_router()
    app.include_router(router)

    logger.info("Registry health check endpoints configured")
