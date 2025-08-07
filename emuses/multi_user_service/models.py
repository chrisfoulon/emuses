"""SQLAlchemy models for multi-user EMUSES service.

This module contains user authentication models extending FastAPI-Users
with EMUSES-specific fields for organization, roles, and resource quotas.
"""

import uuid
from datetime import datetime

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import (JSON, BigInteger, Boolean, Column, DateTime, Float, ForeignKey,
                        Integer, String, Text)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    """User model extending FastAPI-Users with EMUSES-specific fields.

    Extends the base FastAPI-Users model with fields for organization
    membership, role-based access, and resource quota tracking.

    Attributes
    ----------
    organization : str
        Organization or institution name
    role : str
        User role (researcher, admin, student)
    storage_quota_gb : float
        Storage quota in gigabytes
    compute_quota_hours : float
        Compute time quota in hours
    storage_used_gb : float
        Current storage usage in gigabytes
    compute_used_hours : float
        Current compute time usage in hours
    """

    __tablename__ = "users"

    # EMUSES-specific fields
    organization = Column(String(255), nullable=False, index=True)
    role = Column(String(50), nullable=False, default="researcher", index=True)

    # Resource quota tracking
    storage_quota_gb = Column(Float, nullable=False, default=10.0)
    compute_quota_hours = Column(Float, nullable=False, default=100.0)
    storage_used_gb = Column(Float, nullable=False, default=0.0)
    compute_used_hours = Column(Float, nullable=False, default=0.0)

    # Relationships
    settings = relationship("UserSettings", back_populates="user", uselist=False)
    workspaces = relationship("Workspace", back_populates="owner")
    training_jobs = relationship("TrainingJob", back_populates="owner")
    registered_models = relationship("ModelRegistry", back_populates="owner")
    model_access = relationship(
        "ModelAccess", foreign_keys="ModelAccess.user_id", back_populates="user"
    )
    model_downloads = relationship("ModelDownload", back_populates="user")


class UserSettings(Base):
    """User preferences and configuration settings.

    Stores user-specific preferences for EMUSES pipeline defaults
    and notification settings.

    Attributes
    ----------
    user_id : UUID
        Foreign key to User model
    default_n_jobs : int
        Default number of parallel jobs
    default_optuna_trials : int
        Default number of Optuna optimization trials
    notification_email : bool
        Enable email notifications
    notification_slack : bool
        Enable Slack notifications
    ui_theme : str
        UI theme preference
    """

    __tablename__ = "user_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # EMUSES pipeline defaults
    default_n_jobs = Column(Integer, nullable=False, default=4)
    default_optuna_trials = Column(Integer, nullable=False, default=100)

    # Notification preferences
    notification_email = Column(Boolean, nullable=False, default=True)
    notification_slack = Column(Boolean, nullable=False, default=False)

    # UI preferences
    ui_theme = Column(String(20), nullable=False, default="light")

    # Relationships
    user = relationship("User", back_populates="settings")


class Workspace(Base):
    """User workspace model for organizing datasets and jobs.

    Provides user workspace isolation with secure storage path management
    and metadata organization for EMUSES datasets and training jobs.

    Attributes
    ----------
    id : UUID
        Primary key identifier
    name : str
        Workspace name
    description : str
        Optional workspace description
    owner_id : UUID
        Foreign key to User model
    storage_path : str
        File system path for workspace storage
    is_active : bool
        Whether workspace is active
    created_at : datetime
        Workspace creation timestamp
    updated_at : datetime
        Last update timestamp
    """

    __tablename__ = "workspaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    owner_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    storage_path = Column(String(512), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    owner = relationship("User", back_populates="workspaces")
    datasets = relationship(
        "Dataset", back_populates="workspace", cascade="all, delete-orphan"
    )
    training_jobs = relationship("TrainingJob", back_populates="workspace")
    models = relationship("ModelRegistry", back_populates="workspace")


class Dataset(Base):
    """Dataset model with versioning and integrity checking.

    Manages dataset metadata, file information, and versioning
    for EMUSES training data with workspace association.

    Attributes
    ----------
    id : UUID
        Primary key identifier
    name : str
        Dataset name
    description : str
        Optional dataset description
    file_path : str
        Path to dataset file
    file_size_bytes : int
        File size in bytes
    file_hash : str
        File content hash for integrity
    workspace_id : UUID
        Foreign key to Workspace model
    version : str
        Dataset version string
    dataset_metadata : dict
        Additional dataset metadata
    created_at : datetime
        Dataset creation timestamp
    updated_at : datetime
        Last update timestamp
    """

    __tablename__ = "datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    file_path = Column(String(512), nullable=False)
    file_size_bytes = Column(Integer, nullable=False, default=0)
    file_hash = Column(String(128), nullable=True)
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    version = Column(String(50), nullable=False, default="1.0.0")
    dataset_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="datasets")


class TrainingJob(Base):
    """Training job model with user ownership and resource tracking.

    Extends existing job concepts with user ownership, workspace association,
    and resource usage tracking for multi-user EMUSES environment.

    Attributes
    ----------
    id : UUID
        Primary key identifier
    name : str
        Job name
    description : str
        Optional job description
    owner_id : UUID
        Foreign key to User model
    workspace_id : UUID
        Foreign key to Workspace model
    job_config : dict
        Job configuration parameters
    status : str
        Job status (pending, running, completed, failed)
    compute_hours_used : float
        Compute time used in hours
    storage_bytes_used : int
        Storage used in bytes
    started_at : datetime
        Job start timestamp
    completed_at : datetime
        Job completion timestamp
    created_at : datetime
        Job creation timestamp
    updated_at : datetime
        Last update timestamp
    """

    __tablename__ = "training_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    owner_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    job_config = Column(JSON, nullable=True)
    status = Column(String(50), nullable=False, default="pending", index=True)
    compute_hours_used = Column(Float, nullable=False, default=0.0)
    storage_bytes_used = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    owner = relationship("User", back_populates="training_jobs")
    workspace = relationship("Workspace", back_populates="training_jobs")


class ModelRegistry(Base):
    """Model registry for storing and managing trained models.

    Provides multi-user model storage with workspace isolation,
    permission management, and usage tracking for EMUSES models.

    Attributes
    ----------
    id : UUID
        Primary key identifier
    name : str
        Model name
    version : str
        Model version string
    owner_id : UUID
        Foreign key to User model (model owner)
    workspace_id : UUID
        Foreign key to Workspace model (optional, for workspace models)
    is_public : bool
        Whether model is publicly accessible
    created_at : datetime
        Model registration timestamp
    updated_at : datetime
        Last update timestamp
    model_path : str
        Filesystem path to model files
    manifest_hash : str
        SHA-256 hash of model manifest for integrity
    model_size_bytes : int
        Model size in bytes
    description : str
        Optional model description
    tags : list
        Model tags for categorization
    model_type : str
        Type of model (classification, regression, etc.)
    download_count : int
        Number of times model has been downloaded
    last_accessed : datetime
        Last access timestamp
    """

    __tablename__ = "model_registry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    version = Column(String(50), nullable=False)
    owner_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=True, index=True
    )
    is_public = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Storage and integrity
    model_path = Column(Text, nullable=False)
    manifest_hash = Column(String(64), nullable=False)
    model_size_bytes = Column(BigInteger, nullable=True)

    # Metadata
    description = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)
    model_type = Column(String(50), nullable=True, index=True)

    # Usage tracking
    download_count = Column(Integer, nullable=False, default=0)
    last_accessed = Column(DateTime, nullable=True)

    # Relationships
    owner = relationship("User", back_populates="registered_models")
    workspace = relationship("Workspace", back_populates="models")
    access_grants = relationship(
        "ModelAccess", back_populates="model", cascade="all, delete-orphan"
    )
    downloads = relationship(
        "ModelDownload", back_populates="model", cascade="all, delete-orphan"
    )


class ModelAccess(Base):
    """Model access permissions for multi-user model sharing.

    Manages granular permissions for model access across users
    with support for different access levels and expiration.

    Attributes
    ----------
    id : UUID
        Primary key identifier
    model_id : UUID
        Foreign key to ModelRegistry
    user_id : UUID
        Foreign key to User (user being granted access)
    access_level : str
        Access level (read, write, admin, owner)
    granted_by_id : UUID
        Foreign key to User (user who granted access)
    granted_at : datetime
        When access was granted
    expires_at : datetime
        Optional access expiration time
    """

    __tablename__ = "model_access"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(
        UUID(as_uuid=True),
        ForeignKey("model_registry.id"),
        nullable=False,
        index=True
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    access_level = Column(String(20), nullable=False, index=True)
    granted_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    granted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    # Relationships
    model = relationship("ModelRegistry", back_populates="access_grants")
    user = relationship("User", foreign_keys=[user_id], back_populates="model_access")
    granted_by = relationship("User", foreign_keys=[granted_by_id])


class ModelDownload(Base):
    """Model download tracking for usage analytics.

    Tracks model downloads for analytics and usage monitoring
    with metadata about download context and user information.

    Attributes
    ----------
    id : UUID
        Primary key identifier
    model_id : UUID
        Foreign key to ModelRegistry
    user_id : UUID
        Foreign key to User
    downloaded_at : datetime
        Download timestamp
    download_size_bytes : int
        Size of downloaded content in bytes
    download_method : str
        Download method (api, cli, web)
    user_agent : str
        User agent string from download request
    """

    __tablename__ = "model_downloads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(
        UUID(as_uuid=True),
        ForeignKey("model_registry.id"),
        nullable=False,
        index=True
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    downloaded_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    download_size_bytes = Column(BigInteger, nullable=True)
    download_method = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Relationships
    model = relationship("ModelRegistry", back_populates="downloads")
    user = relationship("User", back_populates="model_downloads")
