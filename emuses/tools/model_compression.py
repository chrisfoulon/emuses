"""Model compression system for EMUSES model registry.

This module provides advanced compression capabilities for model storage
optimization, including various compression algorithms and progressive
download strategies.
"""

import gzip
import bz2
import lzma
import tarfile
import tempfile
import shutil
import logging
import requests
import time
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union, Callable, Dict, Any
from fnmatch import fnmatch

logger = logging.getLogger(__name__)


class CompressionError(Exception):
    """Exception raised for compression operation errors."""
    pass


class CompressionMethod(Enum):
    """Available compression methods for model storage optimization."""
    
    GZIP = "gzip"
    BZIP2 = "bzip2" 
    LZMA = "lzma"


@dataclass
class CompressionConfig:
    """Configuration for model compression operations.
    
    Parameters
    ----------
    method : CompressionMethod
        Compression algorithm to use
    compression_level : int
        Compression level (1-9, higher is better compression but slower)
    exclude_patterns : List[str]
        File patterns to exclude from compression
    include_metadata : bool
        Whether to include metadata files in compressed archive
    """
    
    method: CompressionMethod = CompressionMethod.GZIP
    compression_level: int = 6
    exclude_patterns: List[str] = None
    include_metadata: bool = True
    
    def __post_init__(self):
        """Initialize default values after dataclass initialization."""
        if self.exclude_patterns is None:
            self.exclude_patterns = []


@dataclass
class CompressionStats:
    """Statistics from model compression operations.
    
    Parameters
    ----------
    original_size : int
        Original size in bytes
    compressed_size : int
        Compressed size in bytes
    method : CompressionMethod
        Compression method used
    """
    
    original_size: int
    compressed_size: int
    method: CompressionMethod
    
    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio (compressed_size / original_size).
        
        Returns
        -------
        float
            Compression ratio, where lower values indicate better compression
        """
        if self.original_size == 0:
            return 0.0
        return self.compressed_size / self.original_size


class ModelCompressor:
    """Advanced model compression system for storage optimization.
    
    Provides multiple compression algorithms and strategies for reducing
    model storage requirements while maintaining integrity and accessibility.
    
    Parameters
    ----------
    config : CompressionConfig
        Compression configuration settings
        
    Attributes
    ----------
    config : CompressionConfig
        Current compression configuration
    """
    
    def __init__(self, config: CompressionConfig):
        """Initialize model compressor with configuration.
        
        Parameters
        ----------
        config : CompressionConfig
            Compression configuration settings
        """
        self.config = config
        logger.info(f"Initialized ModelCompressor with method: {config.method.value}")
    
    def compress_model(self, model_path: Path, output_path: Path) -> CompressionStats:
        """Compress a model directory into an optimized archive.
        
        Parameters
        ----------
        model_path : Path
            Path to model directory to compress
        output_path : Path
            Path where compressed archive will be saved
            
        Returns
        -------
        CompressionStats
            Statistics about the compression operation
            
        Raises
        ------
        CompressionError
            If compression operation fails
        """
        try:
            if not model_path.exists():
                raise CompressionError(f"Model path does not exist: {model_path}")
                
            if not model_path.is_dir():
                raise CompressionError(f"Model path is not a directory: {model_path}")
            
            # Calculate original size
            original_size = self._calculate_directory_size(model_path)
            
            # Create compressed archive
            self._create_compressed_archive(model_path, output_path)
            
            # Calculate compressed size
            compressed_size = output_path.stat().st_size
            
            stats = CompressionStats(
                original_size=original_size,
                compressed_size=compressed_size,
                method=self.config.method
            )
            
            logger.info(
                f"Compressed model: {model_path} -> {output_path} "
                f"(ratio: {stats.compression_ratio:.2f})"
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            raise CompressionError(f"Failed to compress model: {e}") from e
    
    def _calculate_directory_size(self, directory: Path) -> int:
        """Calculate total size of directory contents.
        
        Parameters
        ----------
        directory : Path
            Directory to calculate size for
            
        Returns
        -------
        int
            Total size in bytes
        """
        total_size = 0
        for file_path in directory.rglob("*"):
            if file_path.is_file() and not self._should_exclude_file(file_path):
                total_size += file_path.stat().st_size
        return total_size
    
    def _should_exclude_file(self, file_path: Path) -> bool:
        """Check if file should be excluded from compression.
        
        Parameters
        ----------
        file_path : Path
            File to check
            
        Returns
        -------
        bool
            True if file should be excluded
        """
        file_name = file_path.name
        for pattern in self.config.exclude_patterns:
            if fnmatch(file_name, pattern):
                return True
        return False
    
    def _create_compressed_archive(self, source_dir: Path, output_path: Path) -> None:
        """Create compressed archive of source directory.
        
        Parameters
        ----------
        source_dir : Path
            Source directory to compress
        output_path : Path
            Output path for compressed archive
        """
        # Determine compression mode based on method
        compression_modes = {
            CompressionMethod.GZIP: f"w:gz",
            CompressionMethod.BZIP2: f"w:bz2",
            CompressionMethod.LZMA: f"w:xz"
        }
        
        mode = compression_modes[self.config.method]
        
        # Only gzip supports compresslevel in tarfile
        if self.config.method == CompressionMethod.GZIP:
            tar_kwargs = {"compresslevel": self.config.compression_level}
        else:
            tar_kwargs = {}
        
        with tarfile.open(output_path, mode, **tar_kwargs) as tar:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file() and not self._should_exclude_file(file_path):
                    # Add file to archive with relative path
                    arcname = file_path.relative_to(source_dir)
                    tar.add(file_path, arcname=arcname)
                    
                    logger.debug(f"Added to archive: {arcname}")


@dataclass
class DownloadConfig:
    """Configuration for progressive download operations.
    
    Parameters
    ----------
    chunk_size : int
        Size of each download chunk in bytes
    max_concurrent_chunks : int
        Maximum number of concurrent downloads
    retry_attempts : int
        Number of retry attempts for failed downloads
    enable_resume : bool
        Whether to support resuming interrupted downloads
    timeout : int
        Download timeout in seconds
    """
    
    chunk_size: int = 8192
    max_concurrent_chunks: int = 4
    retry_attempts: int = 3
    enable_resume: bool = True
    timeout: int = 30


@dataclass
class DownloadProgress:
    """Progress tracking for model downloads.
    
    Parameters
    ----------
    total_bytes : int
        Total bytes to download
    downloaded_bytes : int
        Bytes downloaded so far
    chunks_completed : int
        Number of chunks completed
    chunks_total : int
        Total number of chunks
    """
    
    total_bytes: int = 0
    downloaded_bytes: int = 0
    chunks_completed: int = 0
    chunks_total: int = 0
    
    @property
    def progress_percentage(self) -> float:
        """Calculate download progress percentage.
        
        Returns
        -------
        float
            Progress percentage (0-100)
        """
        if self.total_bytes == 0:
            return 0.0
        return (self.downloaded_bytes / self.total_bytes) * 100.0
    
    @property
    def is_complete(self) -> bool:
        """Check if download is complete.
        
        Returns
        -------
        bool
            True if download is complete
        """
        return self.downloaded_bytes >= self.total_bytes


class ProgressiveDownloader:
    """Progressive downloader for large model files.
    
    Provides chunked downloading with resume capability, progress tracking,
    and bandwidth optimization for large model files.
    
    Parameters
    ----------
    config : DownloadConfig
        Download configuration settings
        
    Attributes
    ----------
    config : DownloadConfig
        Current download configuration
    """
    
    def __init__(self, config: DownloadConfig):
        """Initialize progressive downloader with configuration.
        
        Parameters
        ----------
        config : DownloadConfig
            Download configuration settings
        """
        self.config = config
        logger.info(f"Initialized ProgressiveDownloader with chunk_size: {config.chunk_size}")
    
    def download_model(
        self, 
        url: str, 
        output_path: Path,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None
    ) -> DownloadProgress:
        """Download a model file with progressive chunking and resume support.
        
        Parameters
        ----------
        url : str
            URL to download model from
        output_path : Path
            Path where downloaded file will be saved
        progress_callback : Callable, optional
            Callback function to track download progress
            
        Returns
        -------
        DownloadProgress
            Final download progress information
            
        Raises
        ------
        CompressionError
            If download operation fails
        """
        try:
            # Check if file exists for resume capability
            resume_byte = 0
            if self.config.enable_resume and output_path.exists():
                resume_byte = output_path.stat().st_size
                logger.info(f"Resuming download from byte {resume_byte}")
            
            # Prepare headers for range request if resuming
            headers = {}
            if resume_byte > 0:
                headers['Range'] = f'bytes={resume_byte}-'
            
            # Make initial request to get file size
            response = requests.get(
                url, 
                headers=headers, 
                stream=True, 
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            # Get total file size
            if 'content-length' in response.headers:
                content_length = int(response.headers['content-length'])
                if resume_byte > 0:
                    total_bytes = resume_byte + content_length
                else:
                    total_bytes = content_length
            else:
                total_bytes = 0
            
            # Initialize progress tracking
            progress = DownloadProgress(
                total_bytes=total_bytes,
                downloaded_bytes=resume_byte,
                chunks_completed=0,
                chunks_total=0
            )
            
            # Open file for writing (append mode if resuming)
            mode = 'ab' if resume_byte > 0 else 'wb'
            with open(output_path, mode) as f:
                for chunk in response.iter_content(chunk_size=self.config.chunk_size):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
                        progress.downloaded_bytes += len(chunk)
                        progress.chunks_completed += 1
                        
                        # Call progress callback if provided
                        if progress_callback:
                            progress_callback(progress)
                        
                        logger.debug(f"Downloaded chunk: {len(chunk)} bytes")
            
            # Update total bytes if we didn't have content-length header
            if progress.total_bytes == 0:
                progress.total_bytes = progress.downloaded_bytes
            
            logger.info(f"Download completed: {url} -> {output_path}")
            return progress
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Download failed: {e}")
            raise CompressionError(f"Failed to download model: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected download error: {e}")
            raise CompressionError(f"Unexpected download error: {e}") from e


class CDNProvider(Enum):
    """Available CDN providers for global model distribution."""
    
    CLOUDFLARE = "cloudflare"
    AMAZON_CLOUDFRONT = "amazon_cloudfront"
    AZURE_CDN = "azure_cdn"
    GOOGLE_CDN = "google_cdn"


@dataclass
class CDNConfig:
    """Configuration for CDN integration.
    
    Parameters
    ----------
    provider : CDNProvider
        CDN provider to use
    distribution_domain : str
        CDN distribution domain
    api_token : str
        API token for CDN provider
    enable_compression : bool
        Whether to enable CDN compression
    enable_caching : bool
        Whether to enable CDN caching
    cache_ttl : int
        Cache time-to-live in seconds
    """
    
    provider: CDNProvider = CDNProvider.CLOUDFLARE
    distribution_domain: str = ""
    api_token: str = ""
    enable_compression: bool = True
    enable_caching: bool = True
    cache_ttl: int = 3600


class CDNIntegration:
    """CDN integration for global model distribution.
    
    Provides integration with major CDN providers for global model distribution
    with edge caching, compression, and optimized delivery.
    
    Parameters
    ----------
    config : CDNConfig
        CDN configuration settings
        
    Attributes
    ----------
    config : CDNConfig
        Current CDN configuration
    """
    
    def __init__(self, config: CDNConfig):
        """Initialize CDN integration with configuration.
        
        Parameters
        ----------
        config : CDNConfig
            CDN configuration settings
        """
        self.config = config
        logger.info(f"Initialized CDNIntegration with provider: {config.provider.value}")
    
    def upload_to_cdn(self, file_path: Path, model_id: str) -> str:
        """Upload a model file to CDN for global distribution.
        
        Parameters
        ----------
        file_path : Path
            Local path to model file
        model_id : str
            Unique identifier for the model
            
        Returns
        -------
        str
            CDN URL for the uploaded model
            
        Raises
        ------
        CompressionError
            If CDN upload operation fails
        """
        try:
            if not file_path.exists():
                raise CompressionError(f"File does not exist: {file_path}")
            
            # Prepare upload based on provider
            if self.config.provider == CDNProvider.CLOUDFLARE:
                return self._upload_to_cloudflare(file_path, model_id)
            elif self.config.provider == CDNProvider.AMAZON_CLOUDFRONT:
                return self._upload_to_cloudfront(file_path, model_id)
            elif self.config.provider == CDNProvider.AZURE_CDN:
                return self._upload_to_azure_cdn(file_path, model_id)
            elif self.config.provider == CDNProvider.GOOGLE_CDN:
                return self._upload_to_google_cdn(file_path, model_id)
            else:
                raise CompressionError(f"Unsupported CDN provider: {self.config.provider}")
                
        except Exception as e:
            logger.error(f"CDN upload failed: {e}")
            raise CompressionError(f"Failed to upload to CDN: {e}") from e
    
    def get_cdn_url(self, model_id: str, region: Optional[str] = None) -> str:
        """Get optimized CDN URL for a model.
        
        Parameters
        ----------
        model_id : str
            Unique identifier for the model
        region : str, optional
            Preferred region for edge server selection
            
        Returns
        -------
        str
            Optimized CDN URL for the model
        """
        try:
            base_url = f"https://{self.config.distribution_domain}/models"
            
            # Add optimization parameters
            if self.config.enable_compression:
                base_url += "/optimized"
            
            # Construct final URL
            cdn_url = f"{base_url}/{model_id}.tar.gz"
            
            # Add region-specific edge server if specified
            if region:
                edge_url = self.select_optimal_edge_server(region)
                cdn_url = edge_url + f"/models/{model_id}.tar.gz"
            
            logger.info(f"Generated CDN URL for model {model_id}: {cdn_url}")
            return cdn_url
            
        except Exception as e:
            logger.error(f"Failed to generate CDN URL: {e}")
            raise CompressionError(f"Failed to generate CDN URL: {e}") from e
    
    def select_optimal_edge_server(self, location: str) -> str:
        """Select optimal edge server based on geographical location.
        
        Parameters
        ----------
        location : str
            Geographical location identifier
            
        Returns
        -------
        str
            Optimal edge server URL for the location
        """
        # Simple edge server selection logic
        edge_servers = {
            "us-east": f"https://us-east.{self.config.distribution_domain}",
            "us-west": f"https://us-west.{self.config.distribution_domain}",
            "eu-west": f"https://eu-west.{self.config.distribution_domain}",
            "eu-central": f"https://eu-central.{self.config.distribution_domain}",
            "asia-pacific": f"https://ap.{self.config.distribution_domain}",
            "asia-southeast": f"https://ap-se.{self.config.distribution_domain}"
        }
        
        # Return specific edge server or default
        return edge_servers.get(location, f"https://{self.config.distribution_domain}")
    
    def _upload_to_cloudflare(self, file_path: Path, model_id: str) -> str:
        """Upload model to Cloudflare CDN.
        
        Parameters
        ----------
        file_path : Path
            Local path to model file
        model_id : str
            Unique identifier for the model
            
        Returns
        -------
        str
            Cloudflare CDN URL
        """
        # Simulate Cloudflare API call
        headers = {
            "Authorization": f"Bearer {self.config.api_token}",
            "Content-Type": "application/octet-stream"
        }
        
        # Mock API endpoint
        api_url = f"https://api.cloudflare.com/client/v4/accounts/upload"
        
        with open(file_path, 'rb') as f:
            response = requests.post(
                api_url,
                headers=headers,
                files={'file': (f"{model_id}.tar.gz", f, 'application/gzip')},
                data={'path': f'models/{model_id}.tar.gz'}
            )
        
        response.raise_for_status()
        result = response.json()
        
        if result.get('success'):
            return result['result']['url']
        else:
            raise CompressionError("Cloudflare upload failed")
    
    def _upload_to_cloudfront(self, file_path: Path, model_id: str) -> str:
        """Upload model to Amazon CloudFront.
        
        Parameters
        ----------
        file_path : Path
            Local path to model file
        model_id : str
            Unique identifier for the model
            
        Returns
        -------
        str
            CloudFront CDN URL
        """
        # Simulate CloudFront/S3 upload and distribution
        cdn_url = f"https://{self.config.distribution_domain}/models/{model_id}.tar.gz"
        logger.info(f"Uploaded to CloudFront: {cdn_url}")
        return cdn_url
    
    def _upload_to_azure_cdn(self, file_path: Path, model_id: str) -> str:
        """Upload model to Azure CDN.
        
        Parameters
        ----------
        file_path : Path
            Local path to model file
        model_id : str
            Unique identifier for the model
            
        Returns
        -------
        str
            Azure CDN URL
        """
        # Simulate Azure CDN upload
        cdn_url = f"https://{self.config.distribution_domain}/models/{model_id}.tar.gz"
        logger.info(f"Uploaded to Azure CDN: {cdn_url}")
        return cdn_url
    
    def _upload_to_google_cdn(self, file_path: Path, model_id: str) -> str:
        """Upload model to Google Cloud CDN.
        
        Parameters
        ----------
        file_path : Path
            Local path to model file
        model_id : str
            Unique identifier for the model
            
        Returns
        -------
        str
            Google CDN URL
        """
        # Simulate Google CDN upload
        cdn_url = f"https://{self.config.distribution_domain}/models/{model_id}.tar.gz"
        logger.info(f"Uploaded to Google CDN: {cdn_url}")
        return cdn_url


class NetworkQuality(Enum):
    """Network quality levels for bandwidth adaptation."""
    
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class BandwidthConfig:
    """Configuration for bandwidth-adaptive downloads.
    
    Parameters
    ----------
    initial_chunk_size : int
        Initial chunk size in bytes
    min_chunk_size : int
        Minimum chunk size in bytes
    max_chunk_size : int
        Maximum chunk size in bytes
    speed_test_interval : float
        Interval between speed tests in seconds
    adaptation_threshold : float
        Threshold for triggering adaptation (percentage)
    """
    
    initial_chunk_size: int = 8192
    min_chunk_size: int = 1024
    max_chunk_size: int = 65536
    speed_test_interval: float = 30.0
    adaptation_threshold: float = 0.2


class BandwidthAdapter:
    """Bandwidth-adaptive download strategy optimizer.
    
    Dynamically adapts download strategies based on network conditions,
    connection quality, and available bandwidth for optimal performance.
    
    Parameters
    ----------
    config : BandwidthConfig
        Bandwidth adaptation configuration
        
    Attributes
    ----------
    config : BandwidthConfig
        Current bandwidth configuration
    current_chunk_size : int
        Currently used chunk size
    last_speed_test : float
        Timestamp of last speed test
    """
    
    def __init__(self, config: BandwidthConfig):
        """Initialize bandwidth adapter with configuration.
        
        Parameters
        ----------
        config : BandwidthConfig
            Bandwidth adaptation configuration settings
        """
        self.config = config
        self.current_chunk_size = config.initial_chunk_size
        self.last_speed_test = 0.0
        logger.info(f"Initialized BandwidthAdapter with initial chunk size: {config.initial_chunk_size}")
    
    def detect_network_quality(self, download_speed: float) -> NetworkQuality:
        """Detect network quality based on download speed.
        
        Parameters
        ----------
        download_speed : float
            Download speed in bytes per second
            
        Returns
        -------
        NetworkQuality
            Detected network quality level
        """
        # Convert bytes/sec to Mbps for thresholds
        speed_mbps = (download_speed * 8) / 1_000_000
        
        if speed_mbps >= 5.0:  # >= 5 Mbps
            return NetworkQuality.HIGH
        elif speed_mbps >= 1.0:  # >= 1 Mbps
            return NetworkQuality.MEDIUM
        else:  # < 1 Mbps
            return NetworkQuality.LOW
    
    def adapt_chunk_size(self, network_quality: NetworkQuality) -> int:
        """Adapt chunk size based on network quality.
        
        Parameters
        ----------
        network_quality : NetworkQuality
            Current network quality level
            
        Returns
        -------
        int
            Optimized chunk size in bytes
        """
        if network_quality == NetworkQuality.HIGH:
            new_chunk_size = self.config.max_chunk_size
        elif network_quality == NetworkQuality.MEDIUM:
            new_chunk_size = self.config.initial_chunk_size
        else:  # LOW quality
            new_chunk_size = self.config.min_chunk_size
        
        self.current_chunk_size = new_chunk_size
        logger.info(f"Adapted chunk size to {new_chunk_size} bytes for {network_quality.value} quality network")
        
        return new_chunk_size
    
    def measure_download_speed(self, test_url: str = "https://httpbin.org/bytes/1024") -> float:
        """Measure current download speed.
        
        Parameters
        ----------
        test_url : str
            URL to use for speed testing
            
        Returns
        -------
        float
            Download speed in bytes per second
        """
        try:
            start_time = time.time()
            
            response = requests.get(test_url, timeout=10)
            response.raise_for_status()
            
            total_bytes = 0
            for chunk in response.iter_content(chunk_size=1024):
                total_bytes += len(chunk)
            
            elapsed_time = time.time() - start_time
            
            if elapsed_time > 0:
                speed = total_bytes / elapsed_time
            else:
                speed = 0.0
            
            logger.info(f"Measured download speed: {speed:.2f} bytes/sec")
            return speed
            
        except Exception as e:
            logger.warning(f"Speed test failed: {e}")
            return 0.0
    
    def get_optimal_strategy(self, network_quality: NetworkQuality) -> Dict[str, Any]:
        """Get optimal download strategy for given network quality.
        
        Parameters
        ----------
        network_quality : NetworkQuality
            Current network quality level
            
        Returns
        -------
        Dict[str, Any]
            Optimal download strategy configuration
        """
        strategies = {
            NetworkQuality.HIGH: {
                "chunk_size": self.config.max_chunk_size,
                "concurrent_downloads": 4,
                "compression_enabled": True,
                "retry_attempts": 2,
                "timeout": 30
            },
            NetworkQuality.MEDIUM: {
                "chunk_size": self.config.initial_chunk_size,
                "concurrent_downloads": 2,
                "compression_enabled": True,
                "retry_attempts": 3,
                "timeout": 60
            },
            NetworkQuality.LOW: {
                "chunk_size": self.config.min_chunk_size,
                "concurrent_downloads": 1,
                "compression_enabled": True,
                "retry_attempts": 5,
                "timeout": 120
            }
        }
        
        strategy = strategies[network_quality]
        logger.info(f"Selected optimal strategy for {network_quality.value} network: {strategy}")
        
        return strategy
    
    def should_adapt(self, current_speed: float, previous_speed: float) -> bool:
        """Determine if adaptation is needed based on speed change.
        
        Parameters
        ----------
        current_speed : float
            Current download speed
        previous_speed : float
            Previous download speed
            
        Returns
        -------
        bool
            True if adaptation is recommended
        """
        if previous_speed == 0:
            return True
        
        speed_change = abs(current_speed - previous_speed) / previous_speed
        return speed_change > self.config.adaptation_threshold