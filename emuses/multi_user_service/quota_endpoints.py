"""Quota management endpoints for multi-user EMUSES service.

This module provides RESTful API endpoints for quota management including
user quota status, admin quota adjustments, and usage reporting functionality
with proper authentication and authorization.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from emuses.multi_user_service.auth import fastapi_users
from emuses.multi_user_service.database import get_async_session
from emuses.multi_user_service.models import User
from emuses.multi_user_service.quota_manager import QuotaManager

logger = logging.getLogger(__name__)


class QuotaStatusResponse(BaseModel):
    """User quota status response schema.

    Schema for returning current quota status and usage information.

    Attributes
    ----------
    concurrent_jobs : Dict[str, Any]
        Current concurrent jobs status and limits
    storage : Dict[str, Any]
        Storage usage and quota information
    compute : Dict[str, Any]
        Compute hours usage and quota information
    """

    concurrent_jobs: Dict[str, Any]
    storage: Dict[str, Any]
    compute: Dict[str, Any]


class QuotaAdjustmentRequest(BaseModel):
    """Admin quota adjustment request schema.

    Schema for admin requests to adjust user quotas.

    Attributes
    ----------
    user_id : UUID
        User ID to adjust quotas for
    quota_type : str
        Type of quota to adjust ('storage', 'compute', 'concurrent_jobs')
    new_value : float
        New quota value to set
    """

    user_id: UUID
    quota_type: str
    new_value: float


class UsageHistoryResponse(BaseModel):
    """Usage history response schema.

    Schema for returning historical usage data.

    Attributes
    ----------
    user_id : UUID
        User ID for the usage history
    storage_history : List[Dict[str, Any]]
        Historical storage usage data
    compute_history : List[Dict[str, Any]]
        Historical compute usage data
    """

    user_id: UUID
    storage_history: List[Dict[str, Any]]
    compute_history: List[Dict[str, Any]]


def create_quota_router() -> APIRouter:
    """Create quota management endpoints router.

    Returns
    -------
    APIRouter
        Configured router with quota management endpoints
    """
    router = APIRouter(prefix="/quota", tags=["quota"])
    quota_manager = QuotaManager()

    @router.get("/status", response_model=QuotaStatusResponse)
    async def get_quota_status(
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        db: AsyncSession = Depends(get_async_session),
    ):
        """Get current user's quota status and usage information.

        Parameters
        ----------
        current_user : User
            Currently authenticated user
        db : AsyncSession
            Database session

        Returns
        -------
        QuotaStatusResponse
            Current quota status and usage information
        """
        # Convert async session to sync for quota manager compatibility
        # In a real implementation, we'd update quota manager to use async
        from sqlalchemy.orm import Session

        sync_db = Session(bind=db.bind.sync_engine)
        try:
            concurrent_result = quota_manager.validate_concurrent_job_limit(
                sync_db, current_user.id
            )
            storage_usage = quota_manager.get_user_storage_usage(
                sync_db, current_user.id
            )
            compute_usage = quota_manager.get_user_compute_usage(
                sync_db, current_user.id
            )

            return QuotaStatusResponse(
                concurrent_jobs={
                    "current": concurrent_result.current_jobs,
                    "limit": concurrent_result.limit,
                    "is_valid": concurrent_result.is_valid,
                    "message": concurrent_result.message,
                },
                storage=storage_usage,
                compute=compute_usage,
            )
        finally:
            sync_db.close()

    @router.post("/admin/adjust")
    async def adjust_user_quota(
        request: QuotaAdjustmentRequest,
        current_user: User = Depends(
            fastapi_users.current_user(active=True, superuser=True)
        ),
        db: AsyncSession = Depends(get_async_session),
    ):
        """Adjust user quota (admin only).

        Parameters
        ----------
        request : QuotaAdjustmentRequest
            Quota adjustment request
        current_user : User
            Currently authenticated admin user
        db : AsyncSession
            Database session

        Returns
        -------
        Dict[str, str]
            Success message
        """
        # Implementation placeholder for admin quota adjustment
        return {
            "message": f"Quota {request.quota_type} adjusted for user {request.user_id}"
        }

    @router.get("/usage/history", response_model=UsageHistoryResponse)
    async def get_usage_history(
        days: int = 30,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        db: AsyncSession = Depends(get_async_session),
    ):
        """Get user's usage history.

        Parameters
        ----------
        days : int
            Number of days of history to retrieve
        current_user : User
            Currently authenticated user
        db : AsyncSession
            Database session

        Returns
        -------
        UsageHistoryResponse
            Historical usage data
        """
        # Implementation placeholder for usage history
        return UsageHistoryResponse(
            user_id=current_user.id, storage_history=[], compute_history=[]
        )

    @router.get("/admin/users-near-limit")
    async def get_users_near_quota_limit(
        threshold: float = 80.0,
        current_user: User = Depends(
            fastapi_users.current_user(active=True, superuser=True)
        ),
        db: AsyncSession = Depends(get_async_session),
    ):
        """Get users near quota limits (admin only).

        Parameters
        ----------
        threshold : float
            Percentage threshold for near-limit detection
        current_user : User
            Currently authenticated admin user
        db : AsyncSession
            Database session

        Returns
        -------
        List[Dict[str, Any]]
            Users near quota limits
        """
        # Convert async session to sync for quota manager compatibility
        from sqlalchemy.orm import Session

        sync_db = Session(bind=db.bind.sync_engine)
        try:
            users_near_limit = quota_manager.get_users_near_quota_limit(
                sync_db, threshold
            )
            return users_near_limit
        finally:
            sync_db.close()

    @router.post("/admin/reset")
    async def reset_user_quotas(
        user_id: Optional[UUID] = None,
        organization: Optional[str] = None,
        current_user: User = Depends(
            fastapi_users.current_user(active=True, superuser=True)
        ),
        db: AsyncSession = Depends(get_async_session),
    ):
        """Reset user quotas (admin only).

        Parameters
        ----------
        user_id : Optional[UUID]
            Specific user ID to reset (if None, resets all users)
        organization : Optional[str]
            Organization filter for batch reset
        current_user : User
            Currently authenticated admin user
        db : AsyncSession
            Database session

        Returns
        -------
        Dict[str, str]
            Success message
        """
        # Convert async session to sync for quota manager compatibility
        from sqlalchemy.orm import Session

        sync_db = Session(bind=db.bind.sync_engine)
        try:
            if user_id:
                quota_manager.reset_user_usage(sync_db, user_id)
                return {"message": f"Quotas reset for user {user_id}"}
            else:
                quota_manager.reset_all_users_usage(
                    sync_db, organization_filter=organization
                )
                org_msg = f" in organization {organization}" if organization else ""
                return {"message": f"Quotas reset for all users{org_msg}"}
        finally:
            sync_db.close()

    return router
