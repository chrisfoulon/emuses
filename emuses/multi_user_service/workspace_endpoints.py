"""Workspace management endpoints for multi-user EMUSES service.

This module provides RESTful API endpoints for workspace management
including CRUD operations, dataset management, and user-scoped job endpoints
with proper authentication and user isolation.
"""

import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, FastAPI
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from emuses.multi_user_service.auth import fastapi_users
from emuses.multi_user_service.models import User, Workspace, Dataset, TrainingJob
from emuses.multi_user_service.database import get_async_session

logger = logging.getLogger(__name__)


class WorkspaceCreate(BaseModel):
    """Workspace creation schema.

    Schema for creating new workspaces with validation.

    Attributes
    ----------
    name : str
        Workspace name
    description : str, optional
        Workspace description
    """
    name: str
    description: Optional[str] = None


class WorkspaceUpdate(BaseModel):
    """Workspace update schema.

    Schema for updating existing workspaces.

    Attributes
    ----------
    name : str, optional
        Updated workspace name
    description : str, optional
        Updated workspace description
    is_active : bool, optional
        Whether workspace is active
    """
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class WorkspaceRead(BaseModel):
    """Workspace read schema for API responses.

    Schema for returning workspace information in API responses.

    Attributes
    ----------
    id : str
        Workspace UUID
    name : str
        Workspace name
    description : str, optional
        Workspace description
    owner_id : str
        Owner user UUID
    storage_path : str
        Workspace storage path
    is_active : bool
        Whether workspace is active
    created_at : datetime
        Creation timestamp
    updated_at : datetime
        Last update timestamp
    """
    id: str
    name: str
    description: Optional[str]
    owner_id: str
    storage_path: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetCreate(BaseModel):
    """Dataset creation schema.

    Schema for creating new datasets with validation.

    Attributes
    ----------
    name : str
        Dataset name
    description : str, optional
        Dataset description
    workspace_id : str
        Workspace UUID where dataset belongs
    file_path : str
        Path to dataset file
    version : str, optional
        Dataset version
    dataset_metadata : dict, optional
        Additional dataset metadata
    """
    name: str
    description: Optional[str] = None
    workspace_id: str
    file_path: str
    version: str = "1.0.0"
    dataset_metadata: Optional[dict] = None


class DatasetUpdate(BaseModel):
    """Dataset update schema.

    Schema for updating existing datasets.

    Attributes
    ----------
    name : str, optional
        Updated dataset name
    description : str, optional
        Updated dataset description
    version : str, optional
        Updated dataset version
    dataset_metadata : dict, optional
        Updated dataset metadata
    """
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    dataset_metadata: Optional[dict] = None


class DatasetRead(BaseModel):
    """Dataset read schema for API responses.

    Schema for returning dataset information in API responses.

    Attributes
    ----------
    id : str
        Dataset UUID
    name : str
        Dataset name
    description : str, optional
        Dataset description
    workspace_id : str
        Workspace UUID
    file_path : str
        Dataset file path
    file_size_bytes : int
        File size in bytes
    file_hash : str, optional
        File content hash
    version : str
        Dataset version
    dataset_metadata : dict, optional
        Dataset metadata
    created_at : datetime
        Creation timestamp
    updated_at : datetime
        Last update timestamp
    """
    id: str
    name: str
    description: Optional[str]
    workspace_id: str
    file_path: str
    file_size_bytes: int
    file_hash: Optional[str]
    version: str
    dataset_metadata: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingJobCreate(BaseModel):
    """Training job creation schema.

    Schema for creating new training jobs with validation.

    Attributes
    ----------
    name : str
        Job name
    description : str, optional
        Job description
    workspace_id : str
        Workspace UUID where job belongs
    job_config : dict, optional
        Job configuration parameters
    """
    name: str
    description: Optional[str] = None
    workspace_id: str
    job_config: Optional[dict] = None


class TrainingJobUpdate(BaseModel):
    """Training job update schema.

    Schema for updating existing training jobs.

    Attributes
    ----------
    name : str, optional
        Updated job name
    description : str, optional
        Updated job description
    job_config : dict, optional
        Updated job configuration
    status : str, optional
        Updated job status
    """
    name: Optional[str] = None
    description: Optional[str] = None
    job_config: Optional[dict] = None
    status: Optional[str] = None


class TrainingJobRead(BaseModel):
    """Training job read schema for API responses.

    Schema for returning training job information in API responses.

    Attributes
    ----------
    id : str
        Job UUID
    name : str
        Job name
    description : str, optional
        Job description
    owner_id : str
        Owner user UUID
    workspace_id : str
        Workspace UUID
    job_config : dict, optional
        Job configuration
    status : str
        Job status
    compute_hours_used : float
        Compute hours used
    storage_bytes_used : int
        Storage bytes used
    started_at : datetime, optional
        Job start timestamp
    completed_at : datetime, optional
        Job completion timestamp
    created_at : datetime
        Creation timestamp
    updated_at : datetime
        Last update timestamp
    """
    id: str
    name: str
    description: Optional[str]
    owner_id: str
    workspace_id: str
    job_config: Optional[dict]
    status: str
    compute_hours_used: float
    storage_bytes_used: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


def create_workspace_router() -> APIRouter:
    """Create workspace management router.

    Creates and configures the workspace management router with
    all CRUD endpoints and proper authentication.

    Returns
    -------
    APIRouter
        Configured workspace router
    """
    router = APIRouter(prefix="/workspaces", tags=["Workspaces"])

    @router.post("/", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
    async def create_workspace(
        workspace_data: WorkspaceCreate,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        session: AsyncSession = Depends(get_async_session)
    ):
        """Create a new workspace for the current user.

        Parameters
        ----------
        workspace_data : WorkspaceCreate
            Workspace creation data
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session

        Returns
        -------
        WorkspaceRead
            Created workspace information
        """
        # Create user-specific storage path
        from emuses.multi_user_service.job_manager import MultiUserJobManager
        job_manager = MultiUserJobManager()
        storage_path = job_manager.create_user_storage_path(current_user.id, "workspaces")

        # Create workspace
        workspace = Workspace(
            name=workspace_data.name,
            description=workspace_data.description,
            owner_id=current_user.id,
            storage_path=str(storage_path),
            is_active=True
        )

        session.add(workspace)
        await session.commit()
        await session.refresh(workspace)

        logger.info(f"Created workspace {workspace.id} for user {current_user.id}")
        return WorkspaceRead.from_orm(workspace)

    @router.get("/", response_model=List[WorkspaceRead])
    async def list_user_workspaces(
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        session: AsyncSession = Depends(get_async_session)
    ):
        """List all workspaces owned by the current user.

        Parameters
        ----------
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session

        Returns
        -------
        List[WorkspaceRead]
            List of user's workspaces
        """
        stmt = select(Workspace).where(Workspace.owner_id == current_user.id)
        result = await session.execute(stmt)
        workspaces = result.scalars().all()

        return [WorkspaceRead.from_orm(workspace) for workspace in workspaces]

    @router.get("/{workspace_id}", response_model=WorkspaceRead)
    async def get_workspace(
        workspace_id: UUID,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        session: AsyncSession = Depends(get_async_session)
    ):
        """Get a specific workspace by ID.

        Parameters
        ----------
        workspace_id : UUID
            Workspace UUID
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session

        Returns
        -------
        WorkspaceRead
            Workspace information

        Raises
        ------
        HTTPException
            If workspace not found or user doesn't own it
        """
        stmt = select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.owner_id == current_user.id
        )
        result = await session.execute(stmt)
        workspace = result.scalar_one_or_none()

        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found"
            )

        return WorkspaceRead.from_orm(workspace)

    @router.put("/{workspace_id}", response_model=WorkspaceRead)
    async def update_workspace(
        workspace_id: UUID,
        workspace_data: WorkspaceUpdate,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        session: AsyncSession = Depends(get_async_session)
    ):
        """Update a workspace.

        Parameters
        ----------
        workspace_id : UUID
            Workspace UUID
        workspace_data : WorkspaceUpdate
            Update data
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session

        Returns
        -------
        WorkspaceRead
            Updated workspace information

        Raises
        ------
        HTTPException
            If workspace not found or user doesn't own it
        """
        stmt = select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.owner_id == current_user.id
        )
        result = await session.execute(stmt)
        workspace = result.scalar_one_or_none()

        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found"
            )

        # Update fields
        update_data = workspace_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(workspace, field, value)

        workspace.updated_at = datetime.utcnow()

        await session.commit()
        await session.refresh(workspace)

        logger.info(f"Updated workspace {workspace.id} for user {current_user.id}")
        return WorkspaceRead.from_orm(workspace)

    @router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_workspace(
        workspace_id: UUID,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        session: AsyncSession = Depends(get_async_session)
    ):
        """Delete a workspace.

        Parameters
        ----------
        workspace_id : UUID
            Workspace UUID
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session

        Raises
        ------
        HTTPException
            If workspace not found or user doesn't own it
        """
        stmt = select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.owner_id == current_user.id
        )
        result = await session.execute(stmt)
        workspace = result.scalar_one_or_none()

        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found"
            )

        await session.delete(workspace)
        await session.commit()

        logger.info(f"Deleted workspace {workspace.id} for user {current_user.id}")

    return router


async def _get_user_workspace(workspace_id: UUID, user_id: UUID, session: AsyncSession) -> Workspace:
    """Get workspace owned by user or raise 404."""
    stmt = select(Workspace).where(
        Workspace.id == workspace_id,
        Workspace.owner_id == user_id
    )
    result = await session.execute(stmt)
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    return workspace


async def _get_user_dataset(dataset_id: UUID, user_id: UUID, session: AsyncSession) -> Dataset:
    """Get dataset owned by user or raise 404."""
    stmt = select(Dataset).join(Workspace).where(
        Dataset.id == dataset_id,
        Workspace.owner_id == user_id
    )
    result = await session.execute(stmt)
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    return dataset


async def _get_user_training_job(job_id: UUID, user_id: UUID, session: AsyncSession) -> TrainingJob:
    """Get training job owned by user or raise 404."""
    stmt = select(TrainingJob).join(Workspace).where(
        TrainingJob.id == job_id,
        Workspace.owner_id == user_id
    )
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training job not found"
        )
    return job


def create_dataset_router() -> APIRouter:
    """Create dataset management router.

    Creates and configures the dataset management router with
    all CRUD endpoints and proper authentication.

    Returns
    -------
    APIRouter
        Configured dataset router
    """
    router = APIRouter(prefix="/datasets", tags=["Datasets"])

    @router.post("/", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
    async def create_dataset(
        dataset_data: DatasetCreate,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        session: AsyncSession = Depends(get_async_session)
    ):
        """Create a new dataset in user's workspace.

        Parameters
        ----------
        dataset_data : DatasetCreate
            Dataset creation data
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session

        Returns
        -------
        DatasetRead
            Created dataset information
        """
        # Validate workspace ownership
        workspace_id = UUID(dataset_data.workspace_id)
        await _get_user_workspace(workspace_id, current_user.id, session)

        # Calculate file size if file exists
        import os
        file_size = 0
        if os.path.exists(dataset_data.file_path):
            file_size = os.path.getsize(dataset_data.file_path)

        # Create dataset
        dataset = Dataset(
            name=dataset_data.name,
            description=dataset_data.description,
            workspace_id=workspace_id,
            file_path=dataset_data.file_path,
            file_size_bytes=file_size,
            version=dataset_data.version,
            dataset_metadata=dataset_data.dataset_metadata
        )

        session.add(dataset)
        await session.commit()
        await session.refresh(dataset)

        logger.info(f"Created dataset {dataset.id} in workspace {workspace_id} for user {current_user.id}")
        return DatasetRead.from_orm(dataset)

    @router.get("/", response_model=List[DatasetRead])
    async def list_datasets(
        workspace_id: Optional[UUID] = None,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        session: AsyncSession = Depends(get_async_session)
    ):
        """List datasets for the current user.

        Parameters
        ----------
        workspace_id : UUID, optional
            Filter by specific workspace
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session

        Returns
        -------
        List[DatasetRead]
            List of user's datasets
        """
        if workspace_id:
            # List datasets in specific workspace
            await _get_user_workspace(workspace_id, current_user.id, session)
            stmt = select(Dataset).where(Dataset.workspace_id == workspace_id)
        else:
            # List all datasets in user's workspaces
            stmt = select(Dataset).join(Workspace).where(Workspace.owner_id == current_user.id)

        result = await session.execute(stmt)
        datasets = result.scalars().all()

        return [DatasetRead.from_orm(dataset) for dataset in datasets]

    @router.get("/{dataset_id}", response_model=DatasetRead)
    async def get_dataset(
        dataset_id: UUID,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        session: AsyncSession = Depends(get_async_session)
    ):
        """Get a specific dataset by ID.

        Parameters
        ----------
        dataset_id : UUID
            Dataset UUID
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session

        Returns
        -------
        DatasetRead
            Dataset information

        Raises
        ------
        HTTPException
            If dataset not found or user doesn't own it
        """
        dataset = await _get_user_dataset(dataset_id, current_user.id, session)
        return DatasetRead.from_orm(dataset)

    @router.put("/{dataset_id}", response_model=DatasetRead)
    async def update_dataset(
        dataset_id: UUID,
        dataset_data: DatasetUpdate,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        session: AsyncSession = Depends(get_async_session)
    ):
        """Update a dataset.

        Parameters
        ----------
        dataset_id : UUID
            Dataset UUID
        dataset_data : DatasetUpdate
            Update data
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session

        Returns
        -------
        DatasetRead
            Updated dataset information

        Raises
        ------
        HTTPException
            If dataset not found or user doesn't own it
        """
        dataset = await _get_user_dataset(dataset_id, current_user.id, session)

        # Update fields
        update_data = dataset_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(dataset, field, value)

        dataset.updated_at = datetime.utcnow()

        await session.commit()
        await session.refresh(dataset)

        logger.info(f"Updated dataset {dataset.id} for user {current_user.id}")
        return DatasetRead.from_orm(dataset)

    @router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_dataset(
        dataset_id: UUID,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        session: AsyncSession = Depends(get_async_session)
    ):
        """Delete a dataset.

        Parameters
        ----------
        dataset_id : UUID
            Dataset UUID
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session

        Raises
        ------
        HTTPException
            If dataset not found or user doesn't own it
        """
        dataset = await _get_user_dataset(dataset_id, current_user.id, session)

        await session.delete(dataset)
        await session.commit()

        logger.info(f"Deleted dataset {dataset.id} for user {current_user.id}")

    return router


def create_training_job_router() -> APIRouter:
    """Create training job management router.

    Creates and configures the training job management router with
    all CRUD endpoints and proper authentication.

    Returns
    -------
    APIRouter
        Configured training job router
    """
    router = APIRouter(prefix="/jobs", tags=["Training Jobs"])

    @router.post("/", response_model=TrainingJobRead, status_code=status.HTTP_201_CREATED)
    async def create_training_job(
        job_data: TrainingJobCreate,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        session: AsyncSession = Depends(get_async_session)
    ):
        """Create a new training job in user's workspace.

        Parameters
        ----------
        job_data : TrainingJobCreate
            Training job creation data
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session

        Returns
        -------
        TrainingJobRead
            Created training job information
        """
        # Validate workspace ownership
        workspace_id = UUID(job_data.workspace_id)
        await _get_user_workspace(workspace_id, current_user.id, session)

        # Create training job
        job = TrainingJob(
            name=job_data.name,
            description=job_data.description,
            owner_id=current_user.id,
            workspace_id=workspace_id,
            job_config=job_data.job_config,
            status="pending"
        )

        session.add(job)
        await session.commit()
        await session.refresh(job)

        logger.info(f"Created training job {job.id} in workspace {workspace_id} for user {current_user.id}")
        return TrainingJobRead.from_orm(job)

    @router.get("/", response_model=List[TrainingJobRead])
    async def list_training_jobs(
        workspace_id: Optional[UUID] = None,
        status: Optional[str] = None,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        session: AsyncSession = Depends(get_async_session)
    ):
        """List training jobs for the current user.

        Parameters
        ----------
        workspace_id : UUID, optional
            Filter by specific workspace
        status : str, optional
            Filter by job status
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session

        Returns
        -------
        List[TrainingJobRead]
            List of user's training jobs
        """
        if workspace_id:
            # List jobs in specific workspace
            await _get_user_workspace(workspace_id, current_user.id, session)
            stmt = select(TrainingJob).where(TrainingJob.workspace_id == workspace_id)
        else:
            # List all jobs in user's workspaces
            stmt = select(TrainingJob).join(Workspace).where(Workspace.owner_id == current_user.id)

        if status:
            stmt = stmt.where(TrainingJob.status == status)

        result = await session.execute(stmt)
        jobs = result.scalars().all()

        return [TrainingJobRead.from_orm(job) for job in jobs]

    @router.get("/{job_id}", response_model=TrainingJobRead)
    async def get_training_job(
        job_id: UUID,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        session: AsyncSession = Depends(get_async_session)
    ):
        """Get a specific training job by ID.

        Parameters
        ----------
        job_id : UUID
            Training job UUID
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session

        Returns
        -------
        TrainingJobRead
            Training job information

        Raises
        ------
        HTTPException
            If job not found or user doesn't own it
        """
        job = await _get_user_training_job(job_id, current_user.id, session)
        return TrainingJobRead.from_orm(job)

    @router.put("/{job_id}", response_model=TrainingJobRead)
    async def update_training_job(
        job_id: UUID,
        job_data: TrainingJobUpdate,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        session: AsyncSession = Depends(get_async_session)
    ):
        """Update a training job.

        Parameters
        ----------
        job_id : UUID
            Training job UUID
        job_data : TrainingJobUpdate
            Update data
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session

        Returns
        -------
        TrainingJobRead
            Updated training job information

        Raises
        ------
        HTTPException
            If job not found or user doesn't own it
        """
        job = await _get_user_training_job(job_id, current_user.id, session)

        # Update fields
        update_data = job_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(job, field, value)

        job.updated_at = datetime.utcnow()

        await session.commit()
        await session.refresh(job)

        logger.info(f"Updated training job {job.id} for user {current_user.id}")
        return TrainingJobRead.from_orm(job)

    @router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def cancel_training_job(
        job_id: UUID,
        current_user: User = Depends(fastapi_users.current_user(active=True)),
        session: AsyncSession = Depends(get_async_session)
    ):
        """Cancel/delete a training job.

        Parameters
        ----------
        job_id : UUID
            Training job UUID
        current_user : User
            Current authenticated user
        session : AsyncSession
            Database session

        Raises
        ------
        HTTPException
            If job not found or user doesn't own it
        """
        job = await _get_user_training_job(job_id, current_user.id, session)

        # Mark as cancelled instead of deleting for audit trail
        job.status = "cancelled"
        job.updated_at = datetime.utcnow()

        await session.commit()

        logger.info(f"Cancelled training job {job.id} for user {current_user.id}")

    return router


def setup_workspace_endpoints(app: FastAPI) -> None:
    """Set up workspace, dataset, training job, quota, and task endpoints on FastAPI application.

    Adds workspace, dataset, training job management, quota management, and
    background task management routers to the FastAPI app.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance to configure
    """
    logger.info("Setting up workspace, dataset, training job, quota, and task endpoints")

    workspace_router = create_workspace_router()
    dataset_router = create_dataset_router()
    job_router = create_training_job_router()
    
    # Import and create quota endpoints
    from emuses.multi_user_service.quota_endpoints import create_quota_router
    quota_router = create_quota_router()
    
    # Import and create task endpoints
    from emuses.multi_user_service.task_endpoints import create_task_router
    task_router = create_task_router()
    
    # Import and create admin endpoints
    from emuses.multi_user_service.admin_endpoints import create_admin_router
    admin_router = create_admin_router()

    app.include_router(workspace_router)
    app.include_router(dataset_router)
    app.include_router(job_router)
    app.include_router(quota_router)
    app.include_router(task_router)
    app.include_router(admin_router)

    logger.info("Workspace, dataset, training job, quota, task, and admin endpoints configured")
