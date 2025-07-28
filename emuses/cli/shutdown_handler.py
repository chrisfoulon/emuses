"""
Graceful shutdown handler for EMUSES CLI operations.

This module provides a simple confirmation system for Ctrl+C interruptions,
showing current job status and allowing users to confirm or cancel shutdown.
"""

import asyncio
from typing import Optional


class SimpleShutdownHandler:
    """
    Handle Ctrl+C interruptions with status display and user confirmation.

    This handler provides immediate response to Ctrl+C by displaying current
    job progress and asking for user confirmation before terminating the process.
    """

    def __init__(self, service_client, job_id: str):
        """
        Initialize shutdown handler.

        Parameters
        ----------
        service_client : ServiceHTTPClient
            Client for communicating with the EMUSES service
        job_id : str
            ID of the current job being monitored
        """
        self.service_client = service_client
        self.job_id = job_id

    async def handle_interruption(self) -> bool:
        """
        Handle Ctrl+C with status display and confirmation.

        Shows current job status and asks user whether to stop or continue.
        Includes graceful degradation if service status is unavailable.

        Returns
        -------
        bool
            True if user wants to stop, False to continue execution
        """
        try:
            # Get current job status using existing service API
            status = await self.service_client.get_job_status(self.job_id)

            print("\n🛑 EMUSES process interrupted!")
            print(f"📊 Current: {status.get('message', 'Processing...')}")

            # Show progress if available
            if 'progress' in status:
                progress_pct = status['progress'] * 100 if status['progress'] <= 1 else status['progress']
                print(f"📈 Progress: {progress_pct:.1f}% complete")

            # Show current stage if available
            current_stage = status.get('current_stage')
            if current_stage:
                print(f"🔧 Stage: {current_stage}")

            print("\n⚠️  Stopping now will terminate current processing.")
            print("   Any completed results will be saved.")

            response = input("\n❓ Are you sure you want to stop? [y/N]: ").lower().strip()
            return response in ['y', 'yes']

        except Exception as e:
            # Graceful degradation if status check fails
            print("\n🛑 EMUSES process interrupted!")
            print(f"⚠️  Cannot determine current status: {e}")
            response = input("\n❓ Stop anyway? [y/N]: ").lower().strip()
            return response in ['y', 'yes']

    async def cleanup_and_stop(self):
        """
        Gracefully stop service and cleanup using existing patterns.

        Attempts to cancel the current job and stop the service cleanly.
        Includes fallback behavior if cleanup operations fail.
        """
        try:
            # Cancel current job (if possible)
            print("🛑 Cancelling current job...")
            await self.service_client.cancel_job(self.job_id)

            # Stop service using existing mechanism
            print("🛑 Stopping service...")
            from emuses.cli.service_manager import ServiceManager
            service_manager = ServiceManager()
            service_manager.stop_service()

            print("✅ Service stopped and cleaned up successfully")

        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")
            print("✅ Main process terminated")


class ShutdownError(Exception):
    """Exception raised when shutdown operations fail."""
    pass