"""
Service manager for automatically starting and managing the FastAPI service.

This module provides clean service lifecycle management with automatic startup,
health checking, and graceful shutdown capabilities.
"""

import asyncio
import atexit
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

import psutil

from .service_client import ServiceClientError, ServiceHTTPClient

logger = logging.getLogger(__name__)


class ServiceManager:
    """
    Manages the FastAPI service lifecycle with auto-start capabilities.

    This class provides clean service management that doesn't defeat the purpose
    of having an API while enabling seamless CLI integration.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        startup_timeout: float = 30.0,
        shutdown_timeout: float = 10.0,
        auto_start: bool = True,
        background_mode: bool = True,
    ):
        """
        Initialize the service manager.

        Parameters
        ----------
        host : str, optional
            Service host address, by default "127.0.0.1"
        port : int, optional
            Service port number, by default 8000
        startup_timeout : float, optional
            Timeout for service startup in seconds, by default 30.0
        shutdown_timeout : float, optional
            Timeout for service shutdown in seconds, by default 10.0
        auto_start : bool, optional
            Whether to automatically start the service if not running, by default True
        background_mode : bool, optional
            Whether to run service in background daemon mode, by default True
        """
        self.host = host
        self.port = port
        self.startup_timeout = startup_timeout
        self.shutdown_timeout = shutdown_timeout
        self.auto_start = auto_start
        self.background_mode = background_mode

        self._process: Optional[subprocess.Popen] = None
        self._service_client: Optional[ServiceHTTPClient] = None
        self._shutdown_registered = False
        self._lock = threading.Lock()

        # Register cleanup on exit
        if not self._shutdown_registered:
            atexit.register(self._cleanup_on_exit)
            self._shutdown_registered = True

    def _cleanup_on_exit(self):
        """Clean up resources on program exit."""
        if self._process and self._process.poll() is None:
            try:
                self._shutdown_service()
            except Exception as e:
                logger.debug(f"Error during cleanup: {e}")

    def is_port_available(self, host: str, port: int) -> bool:
        """
        Check if a port is available for binding.

        Parameters
        ----------
        host : str
            Host address to check
        port : int
            Port number to check

        Returns
        -------
        bool
            True if port is available, False otherwise
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                return result != 0
        except Exception:
            return False

    def find_available_port(
        self, host: str = "127.0.0.1", start_port: int = 8000, max_attempts: int = 100
    ) -> int:
        """
        Find an available port starting from start_port.

        Parameters
        ----------
        host : str, optional
            Host address to check, by default "127.0.0.1"
        start_port : int, optional
            Starting port number, by default 8000
        max_attempts : int, optional
            Maximum number of ports to try, by default 100

        Returns
        -------
        int
            Available port number

        Raises
        ------
        RuntimeError
            If no available port is found within max_attempts
        """
        for port in range(start_port, start_port + max_attempts):
            if self.is_port_available(host, port):
                return port
        raise RuntimeError(
            f"No available port found in range {start_port}-{start_port + max_attempts - 1}"
        )

    def find_service_process(self) -> Optional[psutil.Process]:
        """
        Find existing service process by port.

        Returns
        -------
        Optional[psutil.Process]
            Process object if found, None otherwise
        """
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    # Check if process is running uvicorn with our service
                    cmdline = proc.info["cmdline"]
                    if cmdline and len(cmdline) > 0:
                        cmdline_str = " ".join(cmdline)
                        if (
                            "uvicorn" in cmdline_str
                            and "emuses.foundation_fastapi_service.app" in cmdline_str
                            and f"--port {self.port}" in cmdline_str
                        ):
                            return proc
                        # Also check for direct python execution
                        if (
                            "python" in cmdline_str
                            and "emuses/foundation_fastapi_service/app.py"
                            in cmdline_str
                        ):
                            return proc
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.debug(f"Error finding service process: {e}")
        return None

    async def is_service_healthy(self) -> bool:
        """
        Check if the service is healthy and responding.

        Returns
        -------
        bool
            True if service is healthy, False otherwise
        """
        try:
            if not self._service_client:
                self._service_client = ServiceHTTPClient(
                    base_url=f"http://{self.host}:{self.port}", timeout=5.0
                )
            return await self._service_client.check_service_health()
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False

    def _start_service_process(self) -> subprocess.Popen:
        """
        Start the service process.

        Returns
        -------
        subprocess.Popen
            The started process

        Raises
        ------
        RuntimeError
            If service fails to start
        """
        # Get the project root directory
        project_root = Path(__file__).parent.parent.parent

        # Construct the command to start the service
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "emuses.foundation_fastapi_service.app:app",
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--log-level",
            "info",
        ]

        if self.background_mode:
            # Run in background mode
            env = os.environ.copy()
            env["PYTHONPATH"] = str(project_root)

            # Start process with minimal output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=project_root,
                env=env,
                # Make it a daemon process
                start_new_session=True,
            )
        else:
            # Run in foreground for debugging
            process = subprocess.Popen(cmd, cwd=project_root, env=os.environ.copy())

        return process

    def _shutdown_service(self):
        """Shutdown the managed service process."""
        with self._lock:
            if self._process and self._process.poll() is None:
                try:
                    # Try graceful shutdown first
                    self._process.terminate()

                    # Wait for graceful shutdown
                    try:
                        self._process.wait(timeout=self.shutdown_timeout)
                    except subprocess.TimeoutExpired:
                        # Force kill if graceful shutdown fails
                        self._process.kill()
                        self._process.wait()

                    logger.info("Service process stopped")
                except Exception as e:
                    logger.error(f"Error stopping service: {e}")
                finally:
                    self._process = None

    async def ensure_service_running(self) -> bool:
        """
        Ensure the service is running, starting it if necessary.

        Returns
        -------
        bool
            True if service is running and healthy, False otherwise
        """
        # Check if service is already running and healthy
        if await self.is_service_healthy():
            logger.debug("Service is already running and healthy")
            return True

        # Check if auto-start is enabled
        if not self.auto_start:
            logger.info("Service is not running and auto-start is disabled")
            return False

        # Check if port is available
        if not self.is_port_available(self.host, self.port):
            # Port is occupied, check if it's our service
            existing_process = self.find_service_process()
            if existing_process:
                logger.info(
                    f"Found existing service process (PID: {existing_process.pid})"
                )
                # Wait a bit and check health again
                await asyncio.sleep(2)
                return await self.is_service_healthy()
            else:
                logger.error(f"Port {self.port} is occupied by another process")
                return False

        logger.info(f"Starting FastAPI service on {self.host}:{self.port}")

        with self._lock:
            try:
                # Start the service process
                self._process = self._start_service_process()

                # Wait for service to become healthy
                start_time = time.time()
                while time.time() - start_time < self.startup_timeout:
                    # Check if process is still alive
                    if self._process.poll() is not None:
                        # Process died, get error output
                        _, stderr = self._process.communicate()
                        error_msg = stderr.decode() if stderr else "Unknown error"
                        logger.error(f"Service process died: {error_msg}")
                        return False

                    # Check if service is healthy
                    if await self.is_service_healthy():
                        logger.info("Service started successfully")
                        return True

                    await asyncio.sleep(0.5)

                # Timeout reached
                logger.error(
                    f"Service failed to start within {self.startup_timeout} seconds"
                )
                self._shutdown_service()
                return False

            except Exception as e:
                logger.error(f"Failed to start service: {e}")
                self._shutdown_service()
                return False

    async def get_service_client(self) -> Optional[ServiceHTTPClient]:
        """
        Get a service client if the service is running.

        Returns
        -------
        Optional[ServiceHTTPClient]
            Service client if available, None otherwise
        """
        if await self.ensure_service_running():
            if not self._service_client:
                self._service_client = ServiceHTTPClient(
                    base_url=f"http://{self.host}:{self.port}"
                )
            return self._service_client
        return None

    @asynccontextmanager
    async def managed_service(self):
        """
        Context manager for service lifecycle management.

        Yields
        ------
        ServiceHTTPClient
            Service client for the managed service
        """
        client = await self.get_service_client()
        if client:
            try:
                yield client
            finally:
                pass  # Keep service running for subsequent requests
        else:
            raise ServiceClientError("Failed to start or connect to service")

    def stop_service(self):
        """Stop the managed service."""
        self._shutdown_service()

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the service status.

        Returns
        -------
        Dict[str, Any]
            Service status information
        """
        info = {
            "host": self.host,
            "port": self.port,
            "auto_start": self.auto_start,
            "background_mode": self.background_mode,
            "process_running": self._process is not None
            and self._process.poll() is None,
            "port_available": self.is_port_available(self.host, self.port),
        }

        if self._process:
            info["process_pid"] = self._process.pid
            info["process_returncode"] = self._process.poll()

        return info


# Global service manager instance
_service_manager: Optional[ServiceManager] = None


def get_service_manager(**kwargs) -> ServiceManager:
    """
    Get the global service manager instance.

    Parameters
    ----------
    **kwargs
        Configuration arguments for ServiceManager

    Returns
    -------
    ServiceManager
        Global service manager instance
    """
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager(**kwargs)
    return _service_manager


async def ensure_service_available() -> bool:
    """
    Ensure the service is available, starting it if necessary.

    Returns
    -------
    bool
        True if service is available, False otherwise
    """
    manager = get_service_manager()
    return await manager.ensure_service_running()


async def get_service_client() -> Optional[ServiceHTTPClient]:
    """
    Get a service client, starting service if necessary.

    Returns
    -------
    Optional[ServiceHTTPClient]
        Service client if available, None otherwise
    """
    manager = get_service_manager()
    return await manager.get_service_client()
