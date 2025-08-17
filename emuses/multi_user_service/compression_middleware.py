"""Response compression middleware for FastAPI.

This module provides gzip compression middleware for API responses to reduce
bandwidth usage and improve response times for large JSON payloads.
"""

import gzip
import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class CompressionMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for response compression.
    
    Automatically compresses responses when:
    - Content-Type is application/json
    - Response size exceeds minimum threshold
    - Client accepts gzip encoding
    - Response is successful (2xx status codes)
    
    Parameters
    ----------
    min_size : int, default=1024
        Minimum response size in bytes before compression is applied
    compression_level : int, default=6
        Gzip compression level (1-9, where 9 is most compressed)
        
    Attributes
    ----------
    min_size : int
        Minimum size threshold for compression
    compression_level : int
        Gzip compression level setting
    """
    
    def __init__(self, app, min_size: int = 1024, compression_level: int = 6):
        """Initialize compression middleware.
        
        Parameters
        ----------
        app : FastAPI
            FastAPI application instance
        min_size : int, default=1024
            Minimum response size in bytes for compression
        compression_level : int, default=6
            Gzip compression level (1-9)
        """
        super().__init__(app)
        self.min_size = min_size
        self.compression_level = compression_level
        logger.info(f"Initialized compression middleware (min_size={min_size}, level={compression_level})")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and compress response if applicable.
        
        Parameters
        ----------
        request : Request
            Incoming HTTP request
        call_next : Callable
            Next middleware or endpoint handler
            
        Returns
        -------
        Response
            Original or compressed HTTP response
        """
        response = await call_next(request)
        
        # Check if compression should be applied
        if not self._should_compress(request, response):
            return response
        
        # Get response content
        if hasattr(response, 'body') and response.body:
            content = response.body
        elif isinstance(response, JSONResponse):
            content = response.body
        else:
            return response
        
        # Skip compression if content is too small
        if len(content) < self.min_size:
            return response
        
        try:
            # Compress the content
            compressed_content = gzip.compress(content, compresslevel=self.compression_level)
            
            # Calculate compression ratio
            original_size = len(content)
            compressed_size = len(compressed_content)
            compression_ratio = (original_size - compressed_size) / original_size * 100
            
            logger.debug(f"Compressed response: {original_size}B -> {compressed_size}B ({compression_ratio:.1f}% reduction)")
            
            # Create new response with compressed content
            headers = dict(response.headers)
            headers['content-encoding'] = 'gzip'
            headers['content-length'] = str(compressed_size)
            
            # Remove any conflicting headers
            headers.pop('content-length', None)  # Let FastAPI handle this
            
            compressed_response = Response(
                content=compressed_content,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type
            )
            
            return compressed_response
            
        except Exception as e:
            logger.warning(f"Compression failed: {e}. Returning uncompressed response.")
            return response

    def _should_compress(self, request: Request, response: Response) -> bool:
        """Determine if response should be compressed.
        
        Parameters
        ----------
        request : Request
            HTTP request object
        response : Response
            HTTP response object
            
        Returns
        -------
        bool
            True if response should be compressed
        """
        # Check if client accepts gzip encoding
        accept_encoding = request.headers.get('accept-encoding', '').lower()
        if 'gzip' not in accept_encoding:
            return False
        
        # Only compress successful responses
        if response.status_code < 200 or response.status_code >= 300:
            return False
        
        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        if not content_type.startswith('application/json'):
            return False
        
        # Check if already compressed
        if response.headers.get('content-encoding'):
            return False
        
        return True


class ModelListCompressionMiddleware(BaseHTTPMiddleware):
    """Specialized compression middleware for model listing endpoints.
    
    Provides optimized compression settings specifically for model registry
    API responses which typically contain repetitive JSON structures.
    
    Parameters
    ----------
    min_size : int, default=512
        Lower threshold for model listings (typically more compressible)
    compression_level : int, default=7
        Higher compression level for repetitive model metadata
    """
    
    def __init__(self, app, min_size: int = 512, compression_level: int = 7):
        """Initialize model list compression middleware.
        
        Parameters
        ----------
        app : FastAPI
            FastAPI application instance
        min_size : int, default=512
            Minimum response size for compression
        compression_level : int, default=7
            Gzip compression level optimized for JSON lists
        """
        super().__init__(app)
        self.min_size = min_size
        self.compression_level = compression_level
        logger.info(f"Initialized model list compression middleware (min_size={min_size}, level={compression_level})")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and compress model listing responses.
        
        Parameters
        ----------
        request : Request
            Incoming HTTP request
        call_next : Callable
            Next middleware or endpoint handler
            
        Returns
        -------
        Response
            Original or compressed HTTP response
        """
        response = await call_next(request)
        
        # Only apply to model registry endpoints
        if not self._is_model_endpoint(request):
            return response
        
        # Apply same logic as base compression middleware
        if not self._should_compress(request, response):
            return response
        
        # Get response content
        content = self._get_response_content(response)
        if not content or len(content) < self.min_size:
            return response
        
        try:
            # Compress with optimized settings for model lists
            compressed_content = gzip.compress(content, compresslevel=self.compression_level)
            
            # Calculate and log compression metrics
            original_size = len(content)
            compressed_size = len(compressed_content)
            compression_ratio = (original_size - compressed_size) / original_size * 100
            
            logger.info(f"Model list compression: {original_size}B -> {compressed_size}B ({compression_ratio:.1f}% reduction)")
            
            # Create compressed response
            headers = dict(response.headers)
            headers['content-encoding'] = 'gzip'
            headers['x-compression-ratio'] = f"{compression_ratio:.1f}%"
            headers['x-original-size'] = str(original_size)
            
            compressed_response = Response(
                content=compressed_content,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type
            )
            
            return compressed_response
            
        except Exception as e:
            logger.error(f"Model list compression failed: {e}")
            return response

    def _is_model_endpoint(self, request: Request) -> bool:
        """Check if request is for a model listing endpoint.
        
        Parameters
        ----------
        request : Request
            HTTP request object
            
        Returns
        -------
        bool
            True if this is a model listing endpoint
        """
        path = request.url.path.lower()
        
        # Model listing endpoints
        model_endpoints = [
            '/api/v1/models/',
            '/api/v1/models/search',
            '/api/v1/models/list'  # Alternative endpoint name
        ]
        
        return any(path.startswith(endpoint) for endpoint in model_endpoints)

    def _should_compress(self, request: Request, response: Response) -> bool:
        """Determine if model list response should be compressed.
        
        Parameters
        ----------
        request : Request
            HTTP request object
        response : Response
            HTTP response object
            
        Returns
        -------
        bool
            True if response should be compressed
        """
        # Check if client accepts gzip encoding
        accept_encoding = request.headers.get('accept-encoding', '').lower()
        if 'gzip' not in accept_encoding:
            return False
        
        # Only compress successful responses
        if response.status_code < 200 or response.status_code >= 300:
            return False
        
        # Check content type (more lenient for model endpoints)
        content_type = response.headers.get('content-type', '').lower()
        if not (content_type.startswith('application/json') or 'json' in content_type):
            return False
        
        # Check if already compressed
        if response.headers.get('content-encoding'):
            return False
        
        return True

    def _get_response_content(self, response: Response) -> bytes:
        """Extract content from response object.
        
        Parameters
        ----------
        response : Response
            HTTP response object
            
        Returns
        -------
        bytes
            Response content as bytes, or empty bytes if unavailable
        """
        if hasattr(response, 'body') and response.body:
            return response.body
        elif isinstance(response, JSONResponse):
            return response.body
        else:
            return b""


def setup_compression_middleware(app, enable_model_optimization: bool = True):
    """Set up compression middleware on FastAPI application.
    
    Parameters
    ----------
    app : FastAPI
        FastAPI application instance to configure
    enable_model_optimization : bool, default=True
        Whether to enable specialized model list compression
    """
    logger.info("Setting up response compression middleware")
    
    if enable_model_optimization:
        # Add specialized model list compression
        app.add_middleware(ModelListCompressionMiddleware)
        logger.info("Added model list compression middleware")
    else:
        # Add general compression
        app.add_middleware(CompressionMiddleware)
        logger.info("Added general compression middleware")