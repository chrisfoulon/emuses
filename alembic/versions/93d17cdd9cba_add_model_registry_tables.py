"""Add model registry tables

Revision ID: 93d17cdd9cba
Revises: 34df19297160
Create Date: 2025-08-07 14:45:27.175591

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93d17cdd9cba'
down_revision: Union[str, None] = '34df19297160'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add model registry tables to the database."""
    # Create model_registry table
    op.create_table(
        'model_registry',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('owner_id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.UUID(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        
        # Storage and integrity
        sa.Column('model_path', sa.Text(), nullable=False),
        sa.Column('manifest_hash', sa.String(length=64), nullable=False),
        sa.Column('model_size_bytes', sa.BigInteger(), nullable=True),
        
        # Metadata
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('model_type', sa.String(length=50), nullable=True),
        
        # Usage tracking
        sa.Column('download_count', sa.Integer(), nullable=False),
        sa.Column('last_accessed', sa.DateTime(), nullable=True),
        
        # Constraints and keys
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for performance
    op.create_index('ix_model_registry_name', 'model_registry', ['name'])
    op.create_index('ix_model_registry_owner_id', 'model_registry', ['owner_id'])
    op.create_index('ix_model_registry_workspace_id', 'model_registry', ['workspace_id'])
    op.create_index('ix_model_registry_is_public', 'model_registry', ['is_public'])
    op.create_index('ix_model_registry_model_type', 'model_registry', ['model_type'])
    op.create_index('ix_model_registry_created_at', 'model_registry', ['created_at'])
    
    # Unique constraint for name+version within workspace (allows same name/version across workspaces)
    op.create_index('ix_model_registry_unique_name_version_workspace', 'model_registry', 
                   ['name', 'version', 'workspace_id'], unique=True)
    
    # Create model_access table for permissions
    op.create_table(
        'model_access',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('model_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('access_level', sa.String(length=20), nullable=False),
        sa.Column('granted_by_id', sa.UUID(), nullable=False),
        sa.Column('granted_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        
        # Constraints and keys
        sa.ForeignKeyConstraint(['model_id'], ['model_registry.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['granted_by_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for access table
    op.create_index('ix_model_access_model_id', 'model_access', ['model_id'])
    op.create_index('ix_model_access_user_id', 'model_access', ['user_id'])
    op.create_index('ix_model_access_access_level', 'model_access', ['access_level'])
    
    # Unique constraint to prevent duplicate access grants
    op.create_index('ix_model_access_unique_model_user', 'model_access', 
                   ['model_id', 'user_id'], unique=True)
    
    # Create model_downloads table for usage tracking
    op.create_table(
        'model_downloads',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('model_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('downloaded_at', sa.DateTime(), nullable=False),
        sa.Column('download_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('download_method', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        
        # Constraints and keys
        sa.ForeignKeyConstraint(['model_id'], ['model_registry.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for downloads table
    op.create_index('ix_model_downloads_model_id', 'model_downloads', ['model_id'])
    op.create_index('ix_model_downloads_user_id', 'model_downloads', ['user_id'])
    op.create_index('ix_model_downloads_downloaded_at', 'model_downloads', ['downloaded_at'])


def downgrade() -> None:
    """Remove model registry tables from the database."""
    # Drop tables in reverse order (to handle foreign key constraints)
    op.drop_table('model_downloads')
    op.drop_table('model_access')
    op.drop_table('model_registry')
