"""Storage management utilities for model registry.

This module provides storage threshold monitoring, disk space analysis,
and storage warnings for improved user experience.
"""
import logging
import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class StorageThreshold:
    """Configuration for storage usage thresholds.
    
    Attributes
    ----------
    warning_percent : float
        Percentage threshold for warning notifications (default: 80%)
    critical_percent : float
        Percentage threshold for critical notifications (default: 95%)
    enabled : bool
        Whether threshold monitoring is enabled (default: True)
    """
    warning_percent: float = 80.0
    critical_percent: float = 95.0
    enabled: bool = True
    
    def __post_init__(self):
        """Validate threshold configuration after initialization."""
        if self.critical_percent <= self.warning_percent:
            raise ValueError("Critical threshold must be greater than warning threshold")
        
        if not (0 <= self.warning_percent <= 100) or not (0 <= self.critical_percent <= 100):
            raise ValueError("Thresholds must be between 0 and 100")
    
    def is_valid(self) -> bool:
        """Validate threshold configuration.
        
        Returns
        -------
        bool
            True if configuration is valid
        """
        try:
            # Re-run validation
            if self.critical_percent <= self.warning_percent:
                return False
            if not (0 <= self.warning_percent <= 100) or not (0 <= self.critical_percent <= 100):
                return False
            return True
        except Exception:
            return False


@dataclass
class StorageWarning:
    """Storage warning information.
    
    Attributes
    ----------
    level : str
        Warning level ('warning' or 'critical')
    usage_percent : float
        Current storage usage percentage
    registry_size_mb : float
        Registry size in megabytes
    available_space_mb : float
        Available disk space in megabytes
    message : str
        Human-readable warning message
    """
    level: str
    usage_percent: float
    registry_size_mb: float
    available_space_mb: float
    message: str


class StorageManager:
    """Manages storage monitoring and threshold warnings for model registry.
    
    Provides disk space monitoring, usage calculations, and threshold-based
    warnings to improve user experience with storage management.
    
    Parameters
    ----------
    registry_path : Path
        Path to the model registry directory
    threshold : StorageThreshold, optional
        Storage threshold configuration (uses defaults if None)
        
    Attributes
    ----------
    registry_path : Path
        Path to the registry directory
    threshold : StorageThreshold
        Storage threshold configuration
    """
    
    def __init__(self, registry_path: Path, threshold: Optional[StorageThreshold] = None):
        """Initialize storage manager.
        
        Parameters
        ----------
        registry_path : Path
            Path to the model registry directory
        threshold : StorageThreshold, optional
            Storage threshold configuration
        """
        self.registry_path = Path(registry_path)
        self.threshold = threshold or StorageThreshold()
        
        logger.debug(f"Initialized storage manager for {self.registry_path}")
    
    def calculate_registry_size(self) -> int:
        """Calculate total size of registry directory in bytes.
        
        Returns
        -------
        int
            Total size in bytes
        """
        if not self.registry_path.exists():
            return 0
        
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(self.registry_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        if os.path.isfile(filepath) and not os.path.islink(filepath):
                            total_size += os.path.getsize(filepath)
                    except (OSError, FileNotFoundError):
                        # Handle files that might be deleted during traversal
                        continue
        except (OSError, FileNotFoundError) as e:
            logger.warning(f"Error calculating registry size: {e}")
            return 0
            
        return total_size
    
    def get_available_disk_space(self) -> Tuple[int, int, int]:
        """Get disk space information for registry location.
        
        Returns
        -------
        Tuple[int, int, int]
            Total disk space, used space, free space (all in bytes)
        """
        try:
            # Ensure directory exists for shutil.disk_usage
            if not self.registry_path.exists():
                self.registry_path.mkdir(parents=True, exist_ok=True)
            
            total, used, free = shutil.disk_usage(self.registry_path)
            return total, used, free
        except (OSError, FileNotFoundError) as e:
            logger.error(f"Error getting disk space: {e}")
            # Return zero values on error
            return 0, 0, 0
    
    def calculate_storage_usage_percent(self) -> float:
        """Calculate storage usage percentage of total disk.
        
        Returns
        -------
        float
            Storage usage percentage (0-100)
        """
        total, used, free = self.get_available_disk_space()
        
        if total == 0:
            return 0.0
            
        return (used / total) * 100.0
    
    def check_storage_thresholds(self) -> Optional[StorageWarning]:
        """Check if storage usage exceeds configured thresholds.
        
        Returns
        -------
        Optional[StorageWarning]
            Storage warning if threshold exceeded, None otherwise
        """
        if not self.threshold.enabled:
            return None
        
        usage_percent = self.calculate_storage_usage_percent()
        registry_size_bytes = self.calculate_registry_size()
        registry_size_mb = registry_size_bytes / (1024 * 1024)
        
        total, used, free = self.get_available_disk_space()
        available_space_mb = free / (1024 * 1024)
        
        if usage_percent >= self.threshold.critical_percent:
            message = (
                f"Critical: Registry storage at {usage_percent:.1f}% capacity. "
                f"Only {available_space_mb:.1f}MB available. Consider cleaning up old models."
            )
            return StorageWarning(
                level="critical",
                usage_percent=usage_percent,
                registry_size_mb=registry_size_mb,
                available_space_mb=available_space_mb,
                message=message
            )
        elif usage_percent >= self.threshold.warning_percent:
            message = (
                f"Warning: Registry storage at {usage_percent:.1f}% capacity. "
                f"{available_space_mb:.1f}MB available. Consider monitoring usage."
            )
            return StorageWarning(
                level="warning",
                usage_percent=usage_percent,
                registry_size_mb=registry_size_mb,
                available_space_mb=available_space_mb,
                message=message
            )
        
        return None
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Get comprehensive storage information.
        
        Returns
        -------
        Dict[str, Any]
            Dictionary containing storage information
        """
        registry_size_bytes = self.calculate_registry_size()
        registry_size_mb = registry_size_bytes / (1024 * 1024)
        
        total, used, free = self.get_available_disk_space()
        total_disk_gb = total / (1024 * 1024 * 1024)
        free_disk_mb = free / (1024 * 1024)
        usage_percent = self.calculate_storage_usage_percent()
        
        return {
            "registry_size_mb": registry_size_mb,
            "registry_size_bytes": registry_size_bytes,
            "total_disk_gb": total_disk_gb,
            "free_disk_mb": free_disk_mb,
            "usage_percent": usage_percent,
            "threshold_warning": self.threshold.warning_percent,
            "threshold_critical": self.threshold.critical_percent,
            "threshold_enabled": self.threshold.enabled
        }