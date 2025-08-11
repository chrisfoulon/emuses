"""Base model registry interface.

This module defines the abstract base class for all model registry implementations,
ensuring consistent method signatures and behavior across deployment modes.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

logger = logging.getLogger(__name__)


class BaseModelRegistry(ABC):
    """Abstract base class for model registry implementations.
    
    Defines the standard interface that all registry implementations must follow,
    ensuring consistent behavior across local, database, and cloud modes.
    
    This interface supports unified CLI commands and cross-mode compatibility
    for model management operations.
    """

    @abstractmethod
    def list_models(self, user_id: Optional[Union[UUID, str]] = None,
                   workspace_id: Optional[Union[UUID, str]] = None,
                   include_public: bool = True, **kwargs) -> List[Dict[str, Any]]:
        """List models available in the registry.
        
        Parameters
        ----------
        user_id : Optional[Union[UUID, str]]
            User ID for permission filtering (database/cloud modes)
        workspace_id : Optional[Union[UUID, str]]
            Workspace ID for workspace filtering (database/cloud modes)
        include_public : bool, default=True
            Whether to include public models in results
        **kwargs
            Additional mode-specific parameters
            
        Returns
        -------
        List[Dict[str, Any]]
            List of model metadata dictionaries
        """
        pass

    @abstractmethod
    def install_model(self, model_path: Path, model_name: str, version: str,
                     description: str = "", tags: Optional[List[str]] = None,
                     user_id: Optional[Union[UUID, str]] = None,
                     workspace_id: Optional[Union[UUID, str]] = None,
                     **kwargs) -> Dict[str, Any]:
        """Install a model into the registry.
        
        Parameters
        ----------
        model_path : Path
            Path to the model file or directory
        model_name : str
            Name of the model
        version : str
            Version string for the model
        description : str, default=""
            Description of the model
        tags : Optional[List[str]]
            Optional tags for categorization
        user_id : Optional[Union[UUID, str]]
            User ID for ownership (database/cloud modes)
        workspace_id : Optional[Union[UUID, str]]
            Workspace ID for workspace association (database/cloud modes)
        **kwargs
            Additional mode-specific parameters
            
        Returns
        -------
        Dict[str, Any]
            Installed model metadata
        """
        pass

    @abstractmethod
    def get_model_info(self, model_name: str, version: Optional[str] = None,
                      user_id: Optional[Union[UUID, str]] = None,
                      workspace_id: Optional[Union[UUID, str]] = None,
                      **kwargs) -> Optional[Dict[str, Any]]:
        """Get detailed information about a model.
        
        Parameters
        ----------
        model_name : str
            Name of the model
        version : Optional[str]
            Specific version to retrieve (latest if None)
        user_id : Optional[Union[UUID, str]]
            User ID for permission checking (database/cloud modes)
        workspace_id : Optional[Union[UUID, str]]
            Workspace ID for workspace filtering (database/cloud modes)
        **kwargs
            Additional mode-specific parameters
            
        Returns
        -------
        Optional[Dict[str, Any]]
            Model metadata or None if not found/accessible
        """
        pass

    @abstractmethod
    def search_models(self, query: str, limit: int = 20,
                     user_id: Optional[Union[UUID, str]] = None,
                     workspace_id: Optional[Union[UUID, str]] = None,
                     include_public: bool = True, **kwargs) -> List[Dict[str, Any]]:
        """Search for models matching query criteria.
        
        Parameters
        ----------
        query : str
            Search query string
        limit : int, default=20
            Maximum number of results to return
        user_id : Optional[Union[UUID, str]]
            User ID for permission filtering (database/cloud modes)
        workspace_id : Optional[Union[UUID, str]]
            Workspace ID for workspace filtering (database/cloud modes)
        include_public : bool, default=True
            Whether to include public models in results
        **kwargs
            Additional mode-specific parameters
            
        Returns
        -------
        List[Dict[str, Any]]
            List of matching model metadata
        """
        pass

    @abstractmethod
    def remove_model(self, model_name: str, version: Optional[str] = None,
                    user_id: Optional[Union[UUID, str]] = None,
                    workspace_id: Optional[Union[UUID, str]] = None,
                    **kwargs) -> bool:
        """Remove a model from the registry.
        
        Parameters
        ----------
        model_name : str
            Name of the model to remove
        version : Optional[str]
            Specific version to remove (all versions if None)
        user_id : Optional[Union[UUID, str]]
            User ID for permission checking (database/cloud modes)
        workspace_id : Optional[Union[UUID, str]]
            Workspace ID for workspace filtering (database/cloud modes)
        **kwargs
            Additional mode-specific parameters
            
        Returns
        -------
        bool
            True if model was removed successfully
        """
        pass

    @abstractmethod
    def get_model_file_path(self, model_name: str, version: Optional[str] = None,
                           user_id: Optional[Union[UUID, str]] = None,
                           workspace_id: Optional[Union[UUID, str]] = None,
                           **kwargs) -> Optional[Path]:
        """Get local file path to a model.
        
        Parameters
        ----------
        model_name : str
            Name of the model
        version : Optional[str]
            Specific version (latest if None)
        user_id : Optional[Union[UUID, str]]
            User ID for permission checking (database/cloud modes)
        workspace_id : Optional[Union[UUID, str]]
            Workspace ID for workspace filtering (database/cloud modes)
        **kwargs
            Additional mode-specific parameters
            
        Returns
        -------
        Optional[Path]
            Path to model file or None if not found/accessible
        """
        pass

    def get_registry_stats(self, user_id: Optional[Union[UUID, str]] = None,
                          workspace_id: Optional[Union[UUID, str]] = None,
                          **kwargs) -> Dict[str, Any]:
        """Get registry statistics.
        
        Default implementation that can be overridden by specific registries.
        
        Parameters
        ----------
        user_id : Optional[Union[UUID, str]]
            User ID for user-specific stats (database/cloud modes)
        workspace_id : Optional[Union[UUID, str]]
            Workspace ID for workspace stats (database/cloud modes)
        **kwargs
            Additional mode-specific parameters
            
        Returns
        -------
        Dict[str, Any]
            Registry statistics dictionary
        """
        models = self.list_models(user_id=user_id, workspace_id=workspace_id, **kwargs)
        return {
            'total_models': len(models),
            'model_names': list(set(m.get('name', '') for m in models)),
            'registry_type': self.__class__.__name__
        }

    def validate_model_access(self, model_name: str, version: Optional[str] = None,
                             user_id: Optional[Union[UUID, str]] = None,
                             access_level: str = 'read', **kwargs) -> bool:
        """Validate if user has access to a model.
        
        Default implementation that can be overridden by specific registries.
        
        Parameters
        ----------
        model_name : str
            Name of the model
        version : Optional[str]
            Specific version to check
        user_id : Optional[Union[UUID, str]]
            User ID for permission checking
        access_level : str, default='read'
            Required access level (read, write, admin, owner)
        **kwargs
            Additional mode-specific parameters
            
        Returns
        -------
        bool
            True if user has required access
        """
        # Default implementation: check if model exists and is accessible
        model_info = self.get_model_info(model_name, version=version,
                                        user_id=user_id, **kwargs)
        return model_info is not None