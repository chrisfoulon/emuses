"""Tests for model compression system."""
import pytest
import tempfile
import shutil
import pickle
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from emuses.tools.model_compression import (
    ModelCompressor,
    CompressionMethod,
    CompressionConfig,
    CompressionStats,
    CompressionError,
    ProgressiveDownloader,
    DownloadConfig,
    DownloadProgress,
    CDNIntegration,
    CDNConfig,
    CDNProvider,
    BandwidthAdapter,
    BandwidthConfig,
    NetworkQuality
)


class TestModelCompressor:
    """Tests for ModelCompressor class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def sample_model_dir(self, temp_dir):
        """Create a sample model directory structure."""
        model_dir = temp_dir / "test_model"
        model_dir.mkdir()
        
        # Create model files
        (model_dir / "model.pkl").write_bytes(pickle.dumps({"weights": [1, 2, 3, 4, 5] * 1000}))
        (model_dir / "config.json").write_text('{"param1": "value1", "param2": "value2"}')
        (model_dir / "metadata.yaml").write_text("version: 1.0\ntype: sklearn\n")
        
        return model_dir
    
    @pytest.fixture
    def compressor(self):
        """Create ModelCompressor instance."""
        config = CompressionConfig()
        return ModelCompressor(config)
    
    def test_compressor_initialization(self, compressor):
        """Test ModelCompressor initialization."""
        assert compressor.config is not None
        assert isinstance(compressor.config, CompressionConfig)
    
    def test_compress_model_basic(self, compressor, sample_model_dir, temp_dir):
        """Test basic model compression functionality."""
        output_path = temp_dir / "compressed_model.tar.gz"
        
        stats = compressor.compress_model(sample_model_dir, output_path)
        
        assert output_path.exists()
        assert stats.original_size > 0
        assert stats.compressed_size > 0
        assert stats.compression_ratio < 1.0
        assert stats.method == CompressionMethod.GZIP
    
    def test_compress_model_with_different_methods(self, compressor, sample_model_dir, temp_dir):
        """Test compression with different methods."""
        for method in [CompressionMethod.GZIP, CompressionMethod.BZIP2, CompressionMethod.LZMA]:
            compressor.config.method = method
            output_path = temp_dir / f"compressed_model_{method.value}.tar"
            
            stats = compressor.compress_model(sample_model_dir, output_path)
            
            assert output_path.exists()
            assert stats.method == method


class TestCompressionConfig:
    """Tests for CompressionConfig class."""
    
    def test_default_config(self):
        """Test default compression configuration."""
        config = CompressionConfig()
        
        assert config.method == CompressionMethod.GZIP
        assert config.compression_level == 6
        assert config.exclude_patterns == []
        assert config.include_metadata is True
    
    def test_custom_config(self):
        """Test custom compression configuration."""
        config = CompressionConfig(
            method=CompressionMethod.LZMA,
            compression_level=9,
            exclude_patterns=["*.tmp", "*.log"],
            include_metadata=False
        )
        
        assert config.method == CompressionMethod.LZMA
        assert config.compression_level == 9
        assert config.exclude_patterns == ["*.tmp", "*.log"]
        assert config.include_metadata is False


class TestCompressionStats:
    """Tests for CompressionStats class."""
    
    def test_stats_initialization(self):
        """Test CompressionStats initialization."""
        stats = CompressionStats(
            original_size=1000,
            compressed_size=600,
            method=CompressionMethod.GZIP
        )
        
        assert stats.original_size == 1000
        assert stats.compressed_size == 600
        assert stats.compression_ratio == 0.6
        assert stats.method == CompressionMethod.GZIP
    
    def test_compression_ratio_calculation(self):
        """Test compression ratio calculation."""
        stats = CompressionStats(
            original_size=2000,
            compressed_size=800,
            method=CompressionMethod.GZIP
        )
        
        assert stats.compression_ratio == 0.4
    
    def test_compression_ratio_zero_original_size(self):
        """Test compression ratio with zero original size."""
        stats = CompressionStats(
            original_size=0,
            compressed_size=100,
            method=CompressionMethod.GZIP
        )
        
        assert stats.compression_ratio == 0.0


class TestCompressionMethod:
    """Tests for CompressionMethod enum."""
    
    def test_compression_method_values(self):
        """Test CompressionMethod enum values."""
        assert CompressionMethod.GZIP.value == "gzip"
        assert CompressionMethod.BZIP2.value == "bzip2"
        assert CompressionMethod.LZMA.value == "lzma"


class TestProgressiveDownloader:
    """Tests for progressive download functionality."""
    
    @pytest.fixture
    def download_config(self):
        """Create DownloadConfig for testing."""
        return DownloadConfig(
            chunk_size=1024,
            max_concurrent_chunks=3,
            retry_attempts=2,
            enable_resume=True
        )
    
    @pytest.fixture
    def downloader(self, download_config):
        """Create ProgressiveDownloader instance."""
        return ProgressiveDownloader(download_config)
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    def test_downloader_initialization(self, downloader):
        """Test ProgressiveDownloader initialization."""
        assert downloader.config is not None
        assert isinstance(downloader.config, DownloadConfig)
    
    @patch('emuses.tools.model_compression.requests')
    def test_download_model_basic(self, mock_requests, downloader, temp_dir):
        """Test basic model download functionality."""
        # Create realistic test data
        test_data = b'a' * 1024 + b'b' * 1024  # 2048 bytes total
        chunks = [test_data[i:i+1024] for i in range(0, len(test_data), 1024)]
        
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '2048'}
        mock_response.iter_content = Mock(return_value=chunks)
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response
        
        url = "https://example.com/model.tar.gz"
        output_path = temp_dir / "downloaded_model.tar.gz"
        
        progress = downloader.download_model(url, output_path)
        
        assert output_path.exists()
        assert progress.total_bytes == 2048
        assert progress.downloaded_bytes == 2048
        assert progress.is_complete
    
    @patch('emuses.tools.model_compression.requests')
    def test_download_model_with_resume(self, mock_requests, downloader, temp_dir):
        """Test model download with resume capability."""
        # Create partially downloaded file
        initial_data = b"partial_data"  # 12 bytes
        output_path = temp_dir / "partial_model.tar.gz"
        output_path.write_bytes(initial_data)
        
        # Create remaining data 
        remaining_data = b'c' * 1012  # remaining bytes to make 1024 total
        
        # Mock response for range request
        mock_response = Mock()
        mock_response.status_code = 206  # Partial content
        mock_response.headers = {'content-length': '1012'}  # Remaining bytes
        mock_response.iter_content = Mock(return_value=[remaining_data])
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response
        
        url = "https://example.com/model.tar.gz"
        
        progress = downloader.download_model(url, output_path)
        
        assert output_path.exists()
        assert progress.downloaded_bytes == 1024  # 12 initial + 1012 downloaded
        assert progress.total_bytes == 1024  # 12 initial + 1012 from content-length


class TestDownloadConfig:
    """Tests for DownloadConfig class."""
    
    def test_default_config(self):
        """Test default download configuration."""
        config = DownloadConfig()
        
        assert config.chunk_size == 8192
        assert config.max_concurrent_chunks == 4
        assert config.retry_attempts == 3
        assert config.enable_resume is True
        assert config.timeout == 30
    
    def test_custom_config(self):
        """Test custom download configuration."""
        config = DownloadConfig(
            chunk_size=1024,
            max_concurrent_chunks=2,
            retry_attempts=1,
            enable_resume=False,
            timeout=60
        )
        
        assert config.chunk_size == 1024
        assert config.max_concurrent_chunks == 2
        assert config.retry_attempts == 1
        assert config.enable_resume is False
        assert config.timeout == 60


class TestDownloadProgress:
    """Tests for DownloadProgress class."""
    
    def test_progress_initialization(self):
        """Test DownloadProgress initialization."""
        progress = DownloadProgress(
            total_bytes=1000,
            downloaded_bytes=400,
            chunks_completed=2,
            chunks_total=5
        )
        
        assert progress.total_bytes == 1000
        assert progress.downloaded_bytes == 400
        assert progress.chunks_completed == 2
        assert progress.chunks_total == 5
        assert progress.progress_percentage == 40.0
        assert not progress.is_complete
    
    def test_progress_percentage_calculation(self):
        """Test progress percentage calculation."""
        progress = DownloadProgress(
            total_bytes=2000,
            downloaded_bytes=1500
        )
        
        assert progress.progress_percentage == 75.0
    
    def test_is_complete_property(self):
        """Test is_complete property."""
        # Not complete
        progress1 = DownloadProgress(total_bytes=1000, downloaded_bytes=500)
        assert not progress1.is_complete
        
        # Complete
        progress2 = DownloadProgress(total_bytes=1000, downloaded_bytes=1000)
        assert progress2.is_complete


class TestCDNIntegration:
    """Tests for CDN integration functionality."""
    
    @pytest.fixture
    def cdn_config(self):
        """Create CDNConfig for testing."""
        return CDNConfig(
            provider=CDNProvider.CLOUDFLARE,
            distribution_domain="cdn.example.com",
            api_token="test-token",
            enable_compression=True,
            enable_caching=True,
            cache_ttl=86400
        )
    
    @pytest.fixture
    def cdn_integration(self, cdn_config):
        """Create CDNIntegration instance."""
        return CDNIntegration(cdn_config)
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    def test_cdn_integration_initialization(self, cdn_integration):
        """Test CDNIntegration initialization."""
        assert cdn_integration.config is not None
        assert isinstance(cdn_integration.config, CDNConfig)
    
    @patch('emuses.tools.model_compression.requests')
    def test_upload_to_cdn_basic(self, mock_requests, cdn_integration, temp_dir):
        """Test basic CDN upload functionality."""
        # Create test file
        test_file = temp_dir / "test_model.tar.gz"
        test_file.write_bytes(b"test model data")
        
        # Mock CDN API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "result": {
                "url": "https://cdn.example.com/models/test_model.tar.gz"
            }
        }
        mock_requests.post.return_value = mock_response
        
        cdn_url = cdn_integration.upload_to_cdn(test_file, "test_model")
        
        assert cdn_url.startswith("https://cdn.example.com/")
        assert "test_model" in cdn_url
    
    @patch('emuses.tools.model_compression.requests')
    def test_get_cdn_url_with_optimization(self, mock_requests, cdn_integration):
        """Test getting optimized CDN URL."""
        model_id = "test_model_123"
        
        # Mock CDN API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "result": {
                "url": "https://cdn.example.com/models/optimized/test_model_123.tar.gz",
                "optimizations": ["compression", "caching"]
            }
        }
        mock_requests.get.return_value = mock_response
        
        cdn_url = cdn_integration.get_cdn_url(model_id)
        
        assert cdn_url.startswith("https://cdn.example.com/")
        assert "optimized" in cdn_url
    
    def test_select_optimal_edge_server(self, cdn_integration):
        """Test edge server selection based on location."""
        # Test different geographical locations
        locations = ["us-east", "eu-west", "asia-pacific"]
        
        for location in locations:
            edge_url = cdn_integration.select_optimal_edge_server(location)
            assert edge_url is not None
            assert isinstance(edge_url, str)
            assert "cdn.example.com" in edge_url


class TestCDNConfig:
    """Tests for CDNConfig class."""
    
    def test_default_config(self):
        """Test default CDN configuration."""
        config = CDNConfig()
        
        assert config.provider == CDNProvider.CLOUDFLARE
        assert config.distribution_domain == ""
        assert config.api_token == ""
        assert config.enable_compression is True
        assert config.enable_caching is True
        assert config.cache_ttl == 3600
    
    def test_custom_config(self):
        """Test custom CDN configuration."""
        config = CDNConfig(
            provider=CDNProvider.AMAZON_CLOUDFRONT,
            distribution_domain="d123456.cloudfront.net",
            api_token="aws-secret-token",
            enable_compression=False,
            enable_caching=False,
            cache_ttl=7200
        )
        
        assert config.provider == CDNProvider.AMAZON_CLOUDFRONT
        assert config.distribution_domain == "d123456.cloudfront.net"
        assert config.api_token == "aws-secret-token"
        assert config.enable_compression is False
        assert config.enable_caching is False
        assert config.cache_ttl == 7200


class TestCDNProvider:
    """Tests for CDNProvider enum."""
    
    def test_cdn_provider_values(self):
        """Test CDNProvider enum values."""
        assert CDNProvider.CLOUDFLARE.value == "cloudflare"
        assert CDNProvider.AMAZON_CLOUDFRONT.value == "amazon_cloudfront"
        assert CDNProvider.AZURE_CDN.value == "azure_cdn"
        assert CDNProvider.GOOGLE_CDN.value == "google_cdn"


class TestBandwidthAdapter:
    """Tests for bandwidth-adaptive download functionality."""
    
    @pytest.fixture
    def bandwidth_config(self):
        """Create BandwidthConfig for testing."""
        return BandwidthConfig(
            initial_chunk_size=8192,
            min_chunk_size=1024,
            max_chunk_size=65536,
            speed_test_interval=10.0,
            adaptation_threshold=0.1
        )
    
    @pytest.fixture
    def bandwidth_adapter(self, bandwidth_config):
        """Create BandwidthAdapter instance."""
        return BandwidthAdapter(bandwidth_config)
    
    def test_bandwidth_adapter_initialization(self, bandwidth_adapter):
        """Test BandwidthAdapter initialization."""
        assert bandwidth_adapter.config is not None
        assert isinstance(bandwidth_adapter.config, BandwidthConfig)
        assert bandwidth_adapter.current_chunk_size == bandwidth_adapter.config.initial_chunk_size
    
    def test_detect_network_quality_high_speed(self, bandwidth_adapter):
        """Test network quality detection for high-speed connections."""
        # Simulate high-speed network (10 Mbps)
        download_speed = 1_250_000  # 10 Mbps = 1.25 MB/s = 1,250,000 bytes/s
        quality = bandwidth_adapter.detect_network_quality(download_speed)
        
        assert quality == NetworkQuality.HIGH
    
    def test_detect_network_quality_medium_speed(self, bandwidth_adapter):
        """Test network quality detection for medium-speed connections."""
        # Simulate medium-speed network (2 Mbps)
        download_speed = 250_000  # 2 Mbps = 0.25 MB/s = 250,000 bytes/s
        quality = bandwidth_adapter.detect_network_quality(download_speed)
        
        assert quality == NetworkQuality.MEDIUM
    
    def test_detect_network_quality_low_speed(self, bandwidth_adapter):
        """Test network quality detection for low-speed connections."""
        # Simulate low-speed network (0.5 Mbps)
        download_speed = 62_500  # 0.5 Mbps = 0.0625 MB/s = 62,500 bytes/s
        quality = bandwidth_adapter.detect_network_quality(download_speed)
        
        assert quality == NetworkQuality.LOW
    
    def test_adapt_chunk_size_high_quality(self, bandwidth_adapter):
        """Test chunk size adaptation for high-quality network."""
        quality = NetworkQuality.HIGH
        new_chunk_size = bandwidth_adapter.adapt_chunk_size(quality)
        
        # Should use maximum chunk size for high-quality network
        assert new_chunk_size == bandwidth_adapter.config.max_chunk_size
        assert bandwidth_adapter.current_chunk_size == new_chunk_size
    
    def test_adapt_chunk_size_low_quality(self, bandwidth_adapter):
        """Test chunk size adaptation for low-quality network."""
        quality = NetworkQuality.LOW
        new_chunk_size = bandwidth_adapter.adapt_chunk_size(quality)
        
        # Should use minimum chunk size for low-quality network
        assert new_chunk_size == bandwidth_adapter.config.min_chunk_size
        assert bandwidth_adapter.current_chunk_size == new_chunk_size
    
    @patch('emuses.tools.model_compression.time')
    @patch('emuses.tools.model_compression.requests')
    def test_measure_download_speed(self, mock_requests, mock_time, bandwidth_adapter):
        """Test download speed measurement."""
        # Mock time progression
        mock_time.time.side_effect = [0.0, 1.0]  # 1 second elapsed
        
        # Mock response with known data size
        test_data = b'x' * 1024  # 1 KB
        mock_response = Mock()
        mock_response.iter_content.return_value = [test_data]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response
        
        speed = bandwidth_adapter.measure_download_speed()
        
        # Should measure 1 KB/s (1024 bytes in 1 second)
        assert speed == 1024.0
    
    def test_get_optimal_strategy_high_bandwidth(self, bandwidth_adapter):
        """Test optimal strategy selection for high bandwidth."""
        strategy = bandwidth_adapter.get_optimal_strategy(NetworkQuality.HIGH)
        
        assert strategy["chunk_size"] == bandwidth_adapter.config.max_chunk_size
        assert strategy["concurrent_downloads"] > 1
        assert strategy["compression_enabled"] is True
    
    def test_get_optimal_strategy_low_bandwidth(self, bandwidth_adapter):
        """Test optimal strategy selection for low bandwidth."""
        strategy = bandwidth_adapter.get_optimal_strategy(NetworkQuality.LOW)
        
        assert strategy["chunk_size"] == bandwidth_adapter.config.min_chunk_size
        assert strategy["concurrent_downloads"] == 1
        assert strategy["compression_enabled"] is True  # Still beneficial for slow connections


class TestBandwidthConfig:
    """Tests for BandwidthConfig class."""
    
    def test_default_config(self):
        """Test default bandwidth configuration."""
        config = BandwidthConfig()
        
        assert config.initial_chunk_size == 8192
        assert config.min_chunk_size == 1024
        assert config.max_chunk_size == 65536
        assert config.speed_test_interval == 30.0
        assert config.adaptation_threshold == 0.2
    
    def test_custom_config(self):
        """Test custom bandwidth configuration."""
        config = BandwidthConfig(
            initial_chunk_size=4096,
            min_chunk_size=512,
            max_chunk_size=32768,
            speed_test_interval=15.0,
            adaptation_threshold=0.15
        )
        
        assert config.initial_chunk_size == 4096
        assert config.min_chunk_size == 512
        assert config.max_chunk_size == 32768
        assert config.speed_test_interval == 15.0
        assert config.adaptation_threshold == 0.15


class TestNetworkQuality:
    """Tests for NetworkQuality enum."""
    
    def test_network_quality_values(self):
        """Test NetworkQuality enum values."""
        assert NetworkQuality.HIGH.value == "high"
        assert NetworkQuality.MEDIUM.value == "medium"
        assert NetworkQuality.LOW.value == "low"