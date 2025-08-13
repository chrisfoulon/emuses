"""Optimized JSON serialization for model registry responses.

This module provides performance-optimized serialization for model metadata
with field selection, caching, and bulk operations support.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Any, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SerializationMode(Enum):
    """Serialization mode for different API response contexts."""
    
    LIST = "list"           # Minimal fields for list views
    SEARCH = "search"       # Search-optimized with relevance info
    DETAIL = "detail"       # Full model information
    EXPORT = "export"       # Complete model data for export


@dataclass
class FieldSet:
    """Defines which fields to include for different serialization modes.
    
    Attributes
    ----------
    fields : Set[str]
        Set of field names to include in serialization
    description : str
        Human-readable description of this field set
    """
    fields: Set[str]
    description: str


class ModelFieldSets:
    """Predefined field sets for different model serialization contexts."""
    
    # Minimal fields for list views
    LIST_VIEW = FieldSet(
        fields={
            "model_id", "name", "version", "type", "is_public", 
            "created_at", "download_count", "size_mb"
        },
        description="Minimal fields for model listing"
    )
    
    # Search results with relevance
    SEARCH_VIEW = FieldSet(
        fields={
            "model_id", "name", "version", "type", "description",
            "tags", "is_public", "created_at", "download_count", 
            "size_mb", "relevance_score"
        },
        description="Search results with relevance information"
    )
    
    # Detailed view with workspace info
    DETAIL_VIEW = FieldSet(
        fields={
            "model_id", "name", "version", "type", "description", "tags",
            "is_public", "owner_id", "workspace_id", "workspace",
            "created_at", "updated_at", "last_accessed",
            "download_count", "total_downloads", "size_mb", 
            "model_size_bytes", "manifest_hash"
        },
        description="Complete model information"
    )
    
    # Export with all metadata
    EXPORT_VIEW = FieldSet(
        fields={
            "model_id", "name", "version", "type", "description", "tags",
            "is_public", "owner_id", "workspace_id", "workspace",
            "created_at", "updated_at", "last_accessed",
            "download_count", "total_downloads", "size_mb", 
            "model_size_bytes", "manifest_hash", "storage_path"
        },
        description="Complete model data for export"
    )


class OptimizedModelSerializer:
    """High-performance JSON serializer for model registry responses.
    
    Provides field selection, bulk serialization, and performance optimizations
    specifically designed for model metadata structures.
    
    Parameters
    ----------
    default_mode : SerializationMode, default=SerializationMode.LIST
        Default serialization mode when none specified
    enable_caching : bool, default=True
        Whether to enable serialization result caching
    """
    
    def __init__(
        self, 
        default_mode: SerializationMode = SerializationMode.LIST,
        enable_caching: bool = True
    ):
        """Initialize optimized model serializer.
        
        Parameters
        ----------
        default_mode : SerializationMode
            Default mode for serialization
        enable_caching : bool
            Whether to cache serialization results
        """
        self.default_mode = default_mode
        self.enable_caching = enable_caching
        self._cache = {} if enable_caching else None
        
        # Map serialization modes to field sets
        self._mode_fields = {
            SerializationMode.LIST: ModelFieldSets.LIST_VIEW,
            SerializationMode.SEARCH: ModelFieldSets.SEARCH_VIEW,
            SerializationMode.DETAIL: ModelFieldSets.DETAIL_VIEW,
            SerializationMode.EXPORT: ModelFieldSets.EXPORT_VIEW
        }
        
        logger.info(f"Initialized optimized model serializer (mode={default_mode.value}, caching={enable_caching})")

    def serialize_model(
        self, 
        model_data: Dict[str, Any], 
        mode: Optional[SerializationMode] = None,
        additional_fields: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """Serialize a single model with field selection.
        
        Parameters
        ----------
        model_data : Dict[str, Any]
            Raw model data dictionary
        mode : SerializationMode, optional
            Serialization mode (uses default if None)
        additional_fields : Set[str], optional
            Additional fields to include beyond mode defaults
            
        Returns
        -------
        Dict[str, Any]
            Optimized model representation
        """
        mode = mode or self.default_mode
        
        # Get field set for this mode
        field_set = self._mode_fields[mode]
        fields_to_include = field_set.fields.copy()
        
        # Add any additional fields requested
        if additional_fields:
            fields_to_include.update(additional_fields)
        
        # Generate cache key if caching enabled
        cache_key = None
        if self._cache is not None:
            cache_key = self._generate_cache_key(model_data.get("model_id", ""), mode, additional_fields)
            if cache_key in self._cache:
                return self._cache[cache_key]
        
        # Perform field selection and optimization
        optimized_model = self._select_fields(model_data, fields_to_include)
        optimized_model = self._optimize_field_values(optimized_model)
        
        # Cache result if enabled
        if cache_key and self._cache is not None:
            self._cache[cache_key] = optimized_model
        
        return optimized_model

    def serialize_model_list(
        self,
        models_data: List[Dict[str, Any]],
        mode: Optional[SerializationMode] = None,
        additional_fields: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        """Serialize a list of models with bulk optimizations.
        
        Parameters
        ----------
        models_data : List[Dict[str, Any]]
            List of raw model data dictionaries
        mode : SerializationMode, optional
            Serialization mode for all models
        additional_fields : Set[str], optional
            Additional fields to include for all models
            
        Returns
        -------
        List[Dict[str, Any]]
            List of optimized model representations
        """
        if not models_data:
            return []
        
        mode = mode or self.default_mode
        
        # Get field set for bulk operation
        field_set = self._mode_fields[mode]
        fields_to_include = field_set.fields.copy()
        
        if additional_fields:
            fields_to_include.update(additional_fields)
        
        logger.debug(f"Bulk serializing {len(models_data)} models in {mode.value} mode")
        
        # Bulk serialize with optimizations
        serialized_models = []
        for model_data in models_data:
            # Use single model serialization but skip individual caching
            optimized_model = self._select_fields(model_data, fields_to_include)
            optimized_model = self._optimize_field_values(optimized_model)
            serialized_models.append(optimized_model)
        
        return serialized_models

    def serialize_to_json(
        self,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        mode: Optional[SerializationMode] = None,
        additional_fields: Optional[Set[str]] = None,
        ensure_ascii: bool = False
    ) -> str:
        """Serialize models directly to JSON string with optimizations.
        
        Parameters
        ----------
        data : Union[Dict[str, Any], List[Dict[str, Any]]]
            Model data (single model or list)
        mode : SerializationMode, optional
            Serialization mode
        additional_fields : Set[str], optional
            Additional fields to include
        ensure_ascii : bool, default=False
            Whether to ensure ASCII-only output
            
        Returns
        -------
        str
            JSON string representation
        """
        # Serialize the data structure
        if isinstance(data, list):
            serialized_data = self.serialize_model_list(data, mode, additional_fields)
        else:
            serialized_data = self.serialize_model(data, mode, additional_fields)
        
        # Convert to JSON with optimizations
        return json.dumps(
            serialized_data,
            ensure_ascii=ensure_ascii,
            separators=(',', ':'),  # Compact JSON
            default=self._json_default
        )

    def clear_cache(self):
        """Clear serialization cache."""
        if self._cache is not None:
            self._cache.clear()
            logger.debug("Serialization cache cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics.
        
        Returns
        -------
        Dict[str, int]
            Cache statistics including size and hit counts
        """
        if self._cache is None:
            return {"enabled": False, "size": 0}
        
        return {
            "enabled": True,
            "size": len(self._cache),
            "max_size": 1000  # Could be configurable
        }

    def _select_fields(self, model_data: Dict[str, Any], fields: Set[str]) -> Dict[str, Any]:
        """Select only specified fields from model data.
        
        Parameters
        ----------
        model_data : Dict[str, Any]
            Complete model data
        fields : Set[str]
            Fields to include
            
        Returns
        -------
        Dict[str, Any]
            Filtered model data
        """
        return {
            field: model_data[field] 
            for field in fields 
            if field in model_data
        }

    def _optimize_field_values(self, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize field values for JSON serialization.
        
        Parameters
        ----------
        model_data : Dict[str, Any]
            Model data to optimize
            
        Returns
        -------
        Dict[str, Any]
            Model data with optimized values
        """
        optimized = model_data.copy()
        
        # Convert datetime objects to ISO strings
        for field, value in optimized.items():
            if isinstance(value, datetime):
                optimized[field] = value.isoformat() + "Z"
            elif value is None:
                # Remove null values to reduce payload size
                continue
            elif isinstance(value, list) and not value:
                # Remove empty lists
                continue
        
        # Remove fields with None values to reduce size
        optimized = {k: v for k, v in optimized.items() if v is not None}
        
        return optimized

    def _generate_cache_key(
        self, 
        model_id: str, 
        mode: SerializationMode, 
        additional_fields: Optional[Set[str]]
    ) -> str:
        """Generate cache key for serialized model.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        mode : SerializationMode
            Serialization mode
        additional_fields : Set[str], optional
            Additional fields
            
        Returns
        -------
        str
            Cache key
        """
        fields_key = ""
        if additional_fields:
            fields_key = "_" + "_".join(sorted(additional_fields))
        
        return f"{model_id}_{mode.value}{fields_key}"

    def _json_default(self, obj):
        """JSON serialization default handler for special types.
        
        Parameters
        ----------
        obj : Any
            Object to serialize
            
        Returns
        -------
        Any
            Serializable representation
        """
        if isinstance(obj, datetime):
            return obj.isoformat() + "Z"
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class PaginatedResponseSerializer:
    """Specialized serializer for paginated API responses.
    
    Provides consistent pagination metadata along with optimized
    model list serialization.
    
    Parameters
    ----------
    model_serializer : OptimizedModelSerializer, optional
        Model serializer instance (creates default if None)
    """
    
    def __init__(self, model_serializer: Optional[OptimizedModelSerializer] = None):
        """Initialize paginated response serializer.
        
        Parameters
        ----------
        model_serializer : OptimizedModelSerializer, optional
            Model serializer to use
        """
        self.model_serializer = model_serializer or OptimizedModelSerializer()
        logger.info("Initialized paginated response serializer")

    def serialize_paginated_response(
        self,
        models: List[Dict[str, Any]],
        total_count: Optional[int] = None,
        page_size: int = 50,
        page_offset: int = 0,
        mode: SerializationMode = SerializationMode.LIST,
        additional_fields: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """Serialize paginated model response with metadata.
        
        Parameters
        ----------
        models : List[Dict[str, Any]]
            List of model data
        total_count : int, optional
            Total number of models available
        page_size : int, default=50
            Number of items per page
        page_offset : int, default=0
            Starting offset for this page
        mode : SerializationMode, default=SerializationMode.LIST
            Serialization mode for models
        additional_fields : Set[str], optional
            Additional fields to include
            
        Returns
        -------
        Dict[str, Any]
            Paginated response with metadata
        """
        # Serialize the models
        serialized_models = self.model_serializer.serialize_model_list(
            models, mode, additional_fields
        )
        
        # Build pagination metadata
        pagination = {
            "page_size": page_size,
            "page_offset": page_offset,
            "current_count": len(serialized_models),
            "has_more": len(serialized_models) == page_size  # Simple heuristic
        }
        
        if total_count is not None:
            pagination["total_count"] = total_count
            pagination["has_more"] = (page_offset + len(serialized_models)) < total_count
            pagination["total_pages"] = (total_count + page_size - 1) // page_size
            pagination["current_page"] = (page_offset // page_size) + 1
        
        return {
            "models": serialized_models,
            "pagination": pagination,
            "serialization_mode": mode.value
        }


# Global serializer instances for reuse
_default_serializer = None
_paginated_serializer = None


def get_model_serializer(use_caching: bool = True) -> OptimizedModelSerializer:
    """Get or create default model serializer instance.
    
    Parameters
    ----------
    use_caching : bool, default=True
        Whether to enable serialization caching
        
    Returns
    -------
    OptimizedModelSerializer
        Default serializer instance
    """
    global _default_serializer
    if _default_serializer is None or _default_serializer.enable_caching != use_caching:
        _default_serializer = OptimizedModelSerializer(enable_caching=use_caching)
    return _default_serializer


def get_paginated_serializer() -> PaginatedResponseSerializer:
    """Get or create default paginated response serializer.
    
    Returns
    -------
    PaginatedResponseSerializer
        Default paginated serializer instance
    """
    global _paginated_serializer
    if _paginated_serializer is None:
        _paginated_serializer = PaginatedResponseSerializer(get_model_serializer())
    return _paginated_serializer