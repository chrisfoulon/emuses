"""Model Registry Health Check Endpoints.

This module provides health check endpoints specifically for model registry
monitoring, service discovery, and load balancing purposes.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from emuses.tools.model_registry_health import get_health_checker

logger = logging.getLogger(__name__)


class RecoveryTestRequest(BaseModel):
    """Request model for recovery test execution."""
    test_type: str


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

    @router.get("/disaster-recovery/backup-status", response_model=Dict[str, Any])
    async def disaster_recovery_backup_status():
        """Get backup validation status and integrity information.

        Returns
        -------
        Dict[str, Any]
            Backup validation status and recovery objectives
        """
        try:
            health_checker = get_health_checker()
            return health_checker.validate_backups()
        except Exception as e:
            logger.error(f"Error retrieving backup status: {str(e)}")
            return {
                "backup_status": "error",
                "backup_integrity": "unknown",
                "backup_locations": {},
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/disaster-recovery/restoration-plan", response_model=Dict[str, Any])
    async def disaster_recovery_restoration_plan():
        """Get service restoration plan with dependency-aware ordering.

        Returns
        -------
        Dict[str, Any]
            Detailed restoration plan with priority ordering
        """
        try:
            health_checker = get_health_checker()
            return health_checker.get_restoration_plan()
        except Exception as e:
            logger.error(f"Error retrieving restoration plan: {str(e)}")
            return {
                "restoration_priority": [],
                "dependency_requirements": {},
                "total_estimated_time_minutes": 0,
                "parallel_restoration_possible": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/disaster-recovery/procedure", response_model=Dict[str, Any])
    async def disaster_recovery_procedure(
        failure_type: str = Query(..., description="Type of failure (database_corruption, local_storage_failure, complete_system_failure, configuration_loss)")
    ):
        """Get specific recovery procedure based on failure type.

        Parameters
        ----------
        failure_type : str
            Type of failure to get recovery procedure for

        Returns
        -------
        Dict[str, Any]
            Detailed recovery procedure for the specific failure type
        """
        try:
            health_checker = get_health_checker()
            return health_checker.get_recovery_procedure(failure_type)
        except Exception as e:
            logger.error(f"Error retrieving recovery procedure: {str(e)}")
            return {
                "procedure_name": "error_procedure",
                "steps": ["Contact technical support"],
                "estimated_time_minutes": 0,
                "automation_available": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/disaster-recovery/emergency-contacts", response_model=Dict[str, Any])
    async def disaster_recovery_emergency_contacts():
        """Get emergency contact information for disaster scenarios.

        Returns
        -------
        Dict[str, Any]
            Emergency contact information and escalation procedures
        """
        try:
            health_checker = get_health_checker()
            return health_checker.get_emergency_contacts()
        except Exception as e:
            logger.error(f"Error retrieving emergency contacts: {str(e)}")
            return {
                "emergency_contacts": [],
                "escalation_matrix": {},
                "communication_channels": {},
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/disaster-recovery/business-impact", response_model=Dict[str, Any])
    async def disaster_recovery_business_impact():
        """Assess business impact of current service status.

        Returns
        -------
        Dict[str, Any]
            Business impact assessment and risk evaluation
        """
        try:
            health_checker = get_health_checker()
            return health_checker.assess_business_impact()
        except Exception as e:
            logger.error(f"Error assessing business impact: {str(e)}")
            return {
                "impact_assessment": {
                    "affected_users": 0,
                    "total_users": 0,
                    "impact_level": "unknown"
                },
                "sla_impact": {
                    "current_availability": "unknown",
                    "sla_breach_risk": "unknown",
                    "regulatory_compliance": "unknown"
                },
                "business_continuity": {
                    "essential_operations": "unknown",
                    "data_integrity": "unknown",
                    "backup_systems": "unknown"
                },
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.post("/disaster-recovery/run-test", response_model=Dict[str, Any])
    async def disaster_recovery_run_test(request: RecoveryTestRequest):
        """Execute disaster recovery test procedure.

        Parameters
        ----------
        request : RecoveryTestRequest
            Request containing test type to execute

        Returns
        -------
        Dict[str, Any]
            Recovery test execution results
        """
        try:
            health_checker = get_health_checker()
            return health_checker.execute_recovery_test(request.test_type)
        except Exception as e:
            logger.error(f"Error executing recovery test: {str(e)}")
            return {
                "test_name": "Error",
                "test_results": {"error": str(e)},
                "success": False,
                "test_session_id": "error",
                "execution_time": datetime.now().isoformat() + "Z",
                "test_type": request.test_type,
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/disaster-recovery/progress/{session_id}", response_model=Dict[str, Any])
    async def disaster_recovery_progress(session_id: str):
        """Get recovery operation progress for monitoring.

        Parameters
        ----------
        session_id : str
            Recovery session identifier

        Returns
        -------
        Dict[str, Any]
            Recovery progress information and status
        """
        try:
            health_checker = get_health_checker()
            return health_checker.get_recovery_progress(session_id)
        except Exception as e:
            logger.error(f"Error retrieving recovery progress: {str(e)}")
            return {
                "session_id": session_id,
                "recovery_status": "error",
                "completion_percentage": 0,
                "current_step": "error",
                "steps_completed": [],
                "estimated_completion": "unknown",
                "last_update": datetime.now().isoformat() + "Z",
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

    @router.get("/disaster-recovery/post-recovery-validation", response_model=Dict[str, Any])
    async def disaster_recovery_post_recovery_validation():
        """Validate system health and functionality after recovery.

        Returns
        -------
        Dict[str, Any]
            Post-recovery validation results and system status
        """
        try:
            health_checker = get_health_checker()
            return health_checker.validate_post_recovery()
        except Exception as e:
            logger.error(f"Error performing post-recovery validation: {str(e)}")
            return {
                "validation_status": "failed",
                "validation_checks": {},
                "system_operational": False,
                "performance_metrics": {},
                "recommendations": ["Contact technical support"],
                "validation_timestamp": datetime.now().isoformat() + "Z",
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
