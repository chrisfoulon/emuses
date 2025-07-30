"""SQLAlchemy models for multi-user EMUSES service.

This module contains user authentication models extending FastAPI-Users
with EMUSES-specific fields for organization, roles, and resource quotas.
"""

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import Column, String, Float, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
import uuid


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
