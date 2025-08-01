"""Admin CLI commands for EMUSES multi-user service.

This module provides command-line interface for administrative tasks including
user management, quota management, and system monitoring.
"""

import typer
import os
import json
import httpx
from typing import Optional, List
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns

# Using httpx for synchronous HTTP requests instead of async ServiceHTTPClient

console = Console()


class AdminClientError(Exception):
    """Exception raised for admin client errors.
    
    Matches ServiceClientError interface for compatibility.
    """
    pass


def make_admin_request(
    endpoint: str,
    method: str = "GET",
    json_data: dict = None,
    service_url: Optional[str] = None,
    token: Optional[str] = None
) -> httpx.Response:
    """Make synchronous HTTP request for admin operations.
    
    Args:
        endpoint: API endpoint (e.g., "/admin/users")
        method: HTTP method (GET, POST, PUT, DELETE)
        json_data: JSON payload for POST/PUT requests
        service_url: Service base URL (defaults to env var or localhost)
        token: Admin authentication token (defaults to env var)
        
    Returns:
        httpx.Response: HTTP response object
        
    Raises:
        AdminClientError: For connection or authentication errors
    """
    # Determine base URL
    base_url = (
        service_url or 
        os.getenv("EMUSES_SERVICE_URL") or 
        "http://localhost:8000"
    )
    
    # Determine auth token
    auth_token = token or os.getenv("EMUSES_ADMIN_TOKEN")
    
    # Prepare headers
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    # Construct full URL
    url = f"{base_url.rstrip('/')}{endpoint}"
    
    try:
        # Make synchronous request
        if method.upper() == "GET":
            response = httpx.get(url, headers=headers)
        elif method.upper() == "POST":
            response = httpx.post(url, headers=headers, json=json_data)
        elif method.upper() == "PUT":
            response = httpx.put(url, headers=headers, json=json_data)
        elif method.upper() == "DELETE":
            response = httpx.delete(url, headers=headers)
        else:
            raise AdminClientError(f"Unsupported HTTP method: {method}")
            
        return response
        
    except httpx.ConnectError as e:
        raise AdminClientError(f"Connection failed: {e}")
    except httpx.TimeoutException as e:
        raise AdminClientError(f"Request timeout: {e}")
    except Exception as e:
        raise AdminClientError(f"Request failed: {e}")

# Create admin sub-application
admin_app = typer.Typer(
    name="admin",
    help="""
    Administrative commands for EMUSES multi-user service.
    
    These commands allow system administrators to manage users, quotas, and monitor
    system health in multi-user EMUSES deployments. All commands require admin 
    authentication tokens in multi-user mode.
    
    Common usage patterns:
    • User management: add-user, list-users
    • System monitoring: system-status  
    • Resource management: set-quota
    • Job control: cancel-job
    
    Use 'emuses admin COMMAND --help' for detailed command help.
    """,
    no_args_is_help=True
)


@admin_app.command("help")
def admin_help() -> None:
    """Display comprehensive help for admin commands and common workflows."""
    console.print()
    console.print(Panel(
        Text("EMUSES Admin Commands - Comprehensive Help", style="bold blue"),
        expand=False
    ))
    console.print()
    
    # Command overview
    help_table = Table(title="Available Commands")
    help_table.add_column("Command", style="cyan", width=15)
    help_table.add_column("Purpose", style="green")
    help_table.add_column("Example", style="yellow")
    
    help_table.add_row(
        "add-user", 
        "Create new system user",
        "emuses admin add-user user@lab.edu -p pass123"
    )
    help_table.add_row(
        "list-users",
        "Display all system users", 
        "emuses admin list-users --limit 20"
    )
    help_table.add_row(
        "set-quota",
        "Adjust user resource quotas",
        "emuses admin set-quota user@lab.edu storage_gb 100"
    )
    help_table.add_row(
        "system-status",
        "Monitor system health",
        "emuses admin system-status --detailed"
    )
    help_table.add_row(
        "cancel-job",
        "Cancel stuck or running jobs",
        "emuses admin cancel-job 12345678-abcd-..."
    )
    
    console.print(help_table)
    console.print()
    
    # Authentication info
    console.print(Panel(
        """
🔐 Authentication Requirements

• Multi-user mode: All commands require --token or stored admin token
• Local mode: Commands work without authentication
• Production mode: Admin token mandatory for security

Set admin token: export EMUSES_ADMIN_TOKEN=your_token_here
Or use: --token your_token_here with each command
        """.strip(),
        title="Authentication",
        border_style="yellow"
    ))
    console.print()
    
    # Common workflows
    console.print(Panel(
        """
📋 Common Admin Workflows

1. New User Setup:
   emuses admin add-user researcher@university.edu -p temp_password
   emuses admin set-quota researcher@university.edu storage_gb 50
   emuses admin set-quota researcher@university.edu concurrent_jobs 3

2. System Monitoring:
   emuses admin system-status --detailed
   emuses admin list-users --limit 50

3. Emergency Job Management:
   emuses admin system-status  # Check for stuck jobs
   emuses admin cancel-job <job-id> --force

4. Quota Management:
   emuses admin set-quota user@example.com storage_gb 100
   emuses admin set-quota user@example.com compute_hours 500
        """.strip(),
        title="Common Workflows",
        border_style="green"
    ))
    console.print()
    
    # Troubleshooting
    console.print(Panel(
        """
🔧 Troubleshooting

Connection Issues:
• Check service URL: --service-url http://localhost:8000
• Verify admin token is valid and not expired
• Ensure EMUSES service is running

Permission Errors:
• Confirm you have superuser/admin privileges
• Check token has admin scope
• Verify deployment mode allows admin operations

Command Failures:
• Use --help flag for detailed command syntax
• Check user email format and existence
• Verify quota types: storage_gb, concurrent_jobs, compute_hours
        """.strip(),
        title="Troubleshooting",
        border_style="red"
    ))
    console.print()


@admin_app.command("add-user")
def add_user(
    email: str = typer.Argument(..., help="User email address"),
    password: str = typer.Option(..., "--password", "-p", help="User password"),
    organization: str = typer.Option("EMUSES Users", "--organization", "-o", help="User organization"),
    service_url: Optional[str] = typer.Option(None, "--service-url", "-s", help="Service URL"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Admin authentication token"),
    active: bool = typer.Option(True, "--active/--inactive", help="Whether user is active"),
    verified: bool = typer.Option(True, "--verified/--unverified", help="Whether user is verified")
) -> None:
    """Create a new user in the system.
    
    This command creates a new user with the specified email, password, and organization.
    The user will be created with default quotas and can be activated immediately or later.
    
    Requirements:
    • Admin authentication token (multi-user/production mode)
    • Valid email address (must be unique)
    • Secure password (recommended: 8+ characters)
    
    Default Settings:
    • Organization: "EMUSES Users" (can be customized with -o)
    • Active: True (user can log in immediately)
    • Verified: True (email verification skipped)
    • Default quotas: 10GB storage, 2 concurrent jobs, 100 compute hours
    
    Examples:
        # Basic user creation
        emuses admin add-user researcher@university.edu -p SecurePass123
        
        # Custom organization and initial inactive state
        emuses admin add-user intern@lab.edu -p TempPass456 -o "Research Lab" --inactive
        
        # Create unverified user (requires email verification)
        emuses admin add-user newuser@example.com -p Pass789 --unverified
    
    After Creation:
    • User can immediately log in (if active and verified)
    • Consider setting custom quotas with 'set-quota' command
    • User will have a default workspace created automatically
    """
    try:
        # Create service client
        # Create service client with proper defaults
        client_kwargs = {}
        if service_url is not None:
            client_kwargs['base_url'] = service_url
        if token is not None:
            client_kwargs['auth_token'] = token
        client = ServiceHTTPClient(**client_kwargs)
        
        # Prepare user creation request
        user_data = {
            "email": email,
            "password": password,
            "organization": organization,
            "is_active": active,
            "is_verified": verified
        }
        
        with console.status("Creating user..."):
            response = client.post("/admin/users", json=user_data)
            
        if response.status_code == 201:
            user_info = response.json()
            console.print(Panel(
                f"✅ User created successfully!\n\n"
                f"ID: {user_info['id']}\n"
                f"Email: {user_info['email']}\n"
                f"Organization: {user_info['organization']}\n"
                f"Active: {user_info['is_active']}\n"
                f"Verified: {user_info['is_verified']}",
                title="User Creation Success",
                border_style="green"
            ))
        elif response.status_code == 409:
            console.print(Panel(
                f"❌ User with email '{email}' already exists",
                title="User Creation Failed",
                border_style="red"
            ))
            raise typer.Exit(1)
        else:
            console.print(Panel(
                f"❌ Failed to create user: {response.text}",
                title="User Creation Failed",
                border_style="red"
            ))
            raise typer.Exit(1)
            
    except AdminClientError as e:
        console.print(Panel(
            f"❌ Service error: {e}",
            title="Connection Error",
            border_style="red"
        ))
        raise typer.Exit(1)
    except Exception as e:
        console.print(Panel(
            f"❌ Unexpected error: {e}",
            title="Error",
            border_style="red"
        ))
        raise typer.Exit(1)


@admin_app.command("list-users")
def list_users(
    service_url: Optional[str] = typer.Option(None, "--service-url", "-s", help="Service URL"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Admin authentication token"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of users to display"),
    skip: int = typer.Option(0, "--skip", help="Number of users to skip")
) -> None:
    """List all users in the system.
    
    This command displays a formatted table of all users with their key information
    including ID, email, organization, and status flags. Use pagination options
    to manage large user lists effectively.
    
    Information Displayed:
    • User ID (truncated for readability)
    • Email address
    • Organization name
    • Active status (✅/❌)
    • Verified status (✅/❌)
    • Superuser status (✅/❌)
    
    Pagination:
    • --limit: Maximum users to display (default: 10)
    • --skip: Number of users to skip (for pagination)
    
    Examples:
        # List first 10 users (default)
        emuses admin list-users
        
        # List up to 50 users
        emuses admin list-users --limit 50
        
        # Skip first 20 users, show next 10
        emuses admin list-users --skip 20 --limit 10
        
        # Large system pagination
        emuses admin list-users --skip 100 --limit 25
    
    Tip: For large systems (100+ users), use pagination to avoid overwhelming output.
    """
    try:
        # Create service client with proper defaults
        client_kwargs = {}
        if service_url is not None:
            client_kwargs['base_url'] = service_url
        if token is not None:
            client_kwargs['auth_token'] = token
        client = ServiceHTTPClient(**client_kwargs)
        
        with console.status("Fetching users..."):
            response = client.get(f"/admin/users?skip={skip}&limit={limit}")
            
        if response.status_code == 200:
            users = response.json()
            
            if not users:
                console.print("No users found.")
                return
                
            # Create table
            table = Table(title="System Users")
            table.add_column("ID", style="cyan")
            table.add_column("Email", style="green")
            table.add_column("Organization", style="blue")
            table.add_column("Active", style="yellow")
            table.add_column("Verified", style="magenta")
            table.add_column("Superuser", style="red")
            
            for user in users:
                table.add_row(
                    str(user['id'])[:8] + "...",
                    user['email'],
                    user['organization'],
                    "✅" if user['is_active'] else "❌",
                    "✅" if user['is_verified'] else "❌",
                    "✅" if user['is_superuser'] else "❌"
                )
            
            console.print(table)
        else:
            console.print(Panel(
                f"❌ Failed to fetch users: {response.text}",
                title="Error",
                border_style="red"
            ))
            raise typer.Exit(1)
            
    except AdminClientError as e:
        console.print(Panel(
            f"❌ Service error: {e}",
            title="Connection Error",
            border_style="red"
        ))
        raise typer.Exit(1)
    except Exception as e:
        console.print(Panel(
            f"❌ Unexpected error: {e}",
            title="Error",
            border_style="red"
        ))
        raise typer.Exit(1)


@admin_app.command("system-status")
def system_status(
    service_url: Optional[str] = typer.Option(None, "--service-url", "-s", help="Service URL"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Admin authentication token"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed system information")
) -> None:
    """Display system status and health information.
    
    This command provides a comprehensive overview of system health, component status,
    and key operational metrics. Use --detailed for extended diagnostic information.
    
    Basic Information:
    • Overall system status (healthy/degraded/critical)
    • Component status (database, API, background tasks)
    • Key metrics (users, jobs, system resources)
    
    Detailed Information (--detailed flag):
    • Health check results for all components
    • Job queue statistics (pending, running, completed, failed)
    • Extended system diagnostics
    
    Status Indicators:
    • ✅ Healthy: Component operating normally
    • ❌ Unhealthy: Component has issues requiring attention
    
    Examples:
        # Quick system overview
        emuses admin system-status
        
        # Comprehensive diagnostic report
        emuses admin system-status --detailed
        
        # Monitor system during high load
        watch -n 30 'emuses admin system-status --detailed'
    
    Use Cases:
    • Daily health checks
    • Troubleshooting system issues
    • Performance monitoring
    • Pre-maintenance system verification
    """
    try:
        # Create service client with proper defaults
        client_kwargs = {}
        if service_url is not None:
            client_kwargs['base_url'] = service_url
        if token is not None:
            client_kwargs['auth_token'] = token
        client = ServiceHTTPClient(**client_kwargs)
        
        with console.status("Fetching system status..."):
            # Get system status
            status_response = client.get("/admin/system/status")
            health_response = client.get("/admin/system/health") if detailed else None
            queues_response = client.get("/admin/system/job-queues") if detailed else None
            
        if status_response.status_code == 200:
            status_data = status_response.json()
            
            # Display main status
            status_color = "green" if status_data['status'] == "healthy" else "red"
            console.print(Panel(
                f"Status: {status_data['status'].upper()}\n"
                f"Timestamp: {status_data['timestamp']}\n",
                title="System Status",
                border_style=status_color
            ))
            
            # Display components
            components_table = Table(title="System Components")
            components_table.add_column("Component", style="cyan")
            components_table.add_column("Status", style="green")
            
            for component, status in status_data['components'].items():
                status_icon = "✅" if status == "healthy" else "❌"
                components_table.add_row(component, f"{status_icon} {status}")
            
            console.print(components_table)
            
            # Display metrics
            metrics_table = Table(title="System Metrics")
            metrics_table.add_column("Metric", style="blue")
            metrics_table.add_column("Value", style="yellow")
            
            for metric, value in status_data['metrics'].items():
                metrics_table.add_row(metric.replace('_', ' ').title(), str(value))
            
            console.print(metrics_table)
            
            # Display detailed information if requested
            if detailed and health_response and health_response.status_code == 200:
                health_data = health_response.json()
                
                health_table = Table(title="Health Checks")
                health_table.add_column("Check", style="cyan")
                health_table.add_column("Status", style="green")
                
                for check, status in health_data['checks'].items():
                    status_icon = "✅" if status else "❌"
                    health_table.add_row(check.replace('_', ' ').title(), status_icon)
                
                console.print(health_table)
                
            if detailed and queues_response and queues_response.status_code == 200:
                queues_data = queues_response.json()
                
                queues_table = Table(title="Job Queues")
                queues_table.add_column("Status", style="cyan")
                queues_table.add_column("Count", style="yellow")
                
                queues_table.add_row("Total Jobs", str(queues_data['total_jobs']))
                queues_table.add_row("Pending", str(queues_data['pending_jobs']))
                queues_table.add_row("Running", str(queues_data['running_jobs']))
                queues_table.add_row("Completed", str(queues_data['completed_jobs']))
                queues_table.add_row("Failed", str(queues_data['failed_jobs']))
                
                console.print(queues_table)
        else:
            console.print(Panel(
                f"❌ Failed to fetch system status: {status_response.text}",
                title="Error",
                border_style="red"
            ))
            raise typer.Exit(1)
            
    except AdminClientError as e:
        console.print(Panel(
            f"❌ Service error: {e}",
            title="Connection Error",
            border_style="red"
        ))
        raise typer.Exit(1)
    except Exception as e:
        console.print(Panel(
            f"❌ Unexpected error: {e}",
            title="Error",
            border_style="red"
        ))
        raise typer.Exit(1)


@admin_app.command("set-quota")
def set_quota(
    user_email: str = typer.Argument(..., help="User email address"),
    quota_type: str = typer.Argument(..., help="Quota type (storage_gb, concurrent_jobs, compute_hours)"),
    value: float = typer.Argument(..., help="New quota value"),
    service_url: Optional[str] = typer.Option(None, "--service-url", "-s", help="Service URL"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Admin authentication token")
) -> None:
    """Set user quota value.
    
    This command adjusts a user's resource quota for the specified type. Quotas control
    how much system resources each user can consume to ensure fair usage and prevent
    system overload.
    
    Supported Quota Types:
    • storage_gb: Maximum storage space in gigabytes
    • concurrent_jobs: Maximum number of simultaneous running jobs
    • compute_hours: Maximum compute hours per billing period
    
    Quota Guidelines:
    • storage_gb: Typical range 10-500GB (depends on system capacity)
    • concurrent_jobs: Usually 1-10 (depends on system resources)
    • compute_hours: Often 100-1000 hours/month (depends on policy)
    
    Examples:
        # Set storage quota to 50GB
        emuses admin set-quota researcher@university.edu storage_gb 50.0
        
        # Allow 5 concurrent jobs for power user
        emuses admin set-quota poweruser@lab.edu concurrent_jobs 5
        
        # Set monthly compute hour limit
        emuses admin set-quota student@college.edu compute_hours 200
        
        # Remove limits (set very high values)
        emuses admin set-quota admin@system.edu storage_gb 9999
    
    Best Practices:
    • Monitor usage before adjusting quotas
    • Consider system capacity when setting limits
    • Communicate quota changes to affected users
    • Use reasonable defaults for new users
    """
    # Validate quota type
    valid_quota_types = ["storage_gb", "concurrent_jobs", "compute_hours"]
    if quota_type not in valid_quota_types:
        console.print(Panel(
            f"❌ Invalid quota type '{quota_type}'\nValid types: {', '.join(valid_quota_types)}",
            title="Invalid Quota Type",
            border_style="red"
        ))
        raise typer.Exit(1)
    
    try:
        # Create service client with proper defaults
        client_kwargs = {}
        if service_url is not None:
            client_kwargs['base_url'] = service_url
        if token is not None:
            client_kwargs['auth_token'] = token
        client = ServiceHTTPClient(**client_kwargs)
        
        # First, get user ID by email (this would need user lookup endpoint)
        # For now, use email as user_id (this is simplified)
        # TODO: Implement user lookup by email
        
        quota_data = {
            "user_id": user_email,  # Simplified - should be actual UUID
            "quota_type": quota_type,
            "new_value": value
        }
        
        with console.status(f"Setting {quota_type} quota to {value} for {user_email}..."):
            response = client.post("/admin/quota/adjust", json=quota_data)
            
        if response.status_code == 200:
            result = response.json()
            console.print(Panel(
                f"✅ Quota updated successfully!\n\n"
                f"User: {user_email}\n"
                f"Quota Type: {quota_type}\n"
                f"New Value: {value}\n"
                f"Message: {result.get('message', 'Updated')}",
                title="Quota Update Success",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"❌ Failed to set quota: {response.text}",
                title="Quota Update Failed",
                border_style="red"
            ))
            raise typer.Exit(1)
            
    except AdminClientError as e:
        console.print(Panel(
            f"❌ Service error: {e}",
            title="Connection Error",
            border_style="red"
        ))
        raise typer.Exit(1)
    except Exception as e:
        console.print(Panel(
            f"❌ Unexpected error: {e}",
            title="Error",
            border_style="red"
        ))
        raise typer.Exit(1)


@admin_app.command("cancel-job")
def cancel_job(
    job_id: str = typer.Argument(..., help="Job ID to cancel"),
    service_url: Optional[str] = typer.Option(None, "--service-url", "-s", help="Service URL"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Admin authentication token"),
    force: bool = typer.Option(False, "--force", "-f", help="Force cancellation without confirmation")
) -> None:
    """Cancel a stuck or running job.
    
    This command forcibly cancels a job by ID, terminating any running processes
    and cleaning up associated resources. Use with caution as this will immediately
    stop job execution and may result in data loss.
    
    When to Use:
    • Jobs stuck in 'running' state for extended periods
    • Runaway processes consuming excessive resources
    • Emergency system maintenance requirements
    • Jobs that failed to respond to normal cancellation
    
    Safety Features:
    • Confirmation prompt (unless --force is used)
    • Detailed job ID validation
    • Graceful cleanup of associated resources
    
    Examples:
        # Cancel with confirmation prompt
        emuses admin cancel-job 12345678-1234-1234-1234-123456789abc
        
        # Force cancellation without confirmation (emergency use)
        emuses admin cancel-job 12345678-1234-1234-1234-123456789abc --force
        
        # Get job ID from system status first
        emuses admin system-status --detailed
        emuses admin cancel-job <job-id-from-status>
    
    Warnings:
    • This will immediately terminate running processes
    • May result in partial results or data corruption
    • Users will lose any unsaved progress
    • Consider communicating with job owner first
    
    After Cancellation:
    • Job status will be marked as 'cancelled'
    • Associated resources will be cleaned up
    • User will be notified of the cancellation
    """
    if not force:
        proceed = typer.confirm(f"Are you sure you want to cancel job {job_id}?")
        if not proceed:
            console.print("Job cancellation aborted.")
            return
    
    try:
        # Create service client with proper defaults
        client_kwargs = {}
        if service_url is not None:
            client_kwargs['base_url'] = service_url
        if token is not None:
            client_kwargs['auth_token'] = token
        client = ServiceHTTPClient(**client_kwargs)
        
        with console.status(f"Cancelling job {job_id}..."):
            # Use task cancellation endpoint
            response = client.post(f"/tasks/{job_id}/cancel")
            
        if response.status_code == 200:
            console.print(Panel(
                f"✅ Job cancelled successfully!\n\n"
                f"Job ID: {job_id}\n"
                f"Status: Cancelled",
                title="Job Cancellation Success",
                border_style="green"
            ))
        elif response.status_code == 404:
            console.print(Panel(
                f"❌ Job not found: {job_id}\n"
                f"Please check the job ID and try again.",
                title="Job Not Found",
                border_style="red"
            ))
            raise typer.Exit(1)
        else:
            console.print(Panel(
                f"❌ Failed to cancel job: {response.text}",
                title="Job Cancellation Failed",
                border_style="red"
            ))
            raise typer.Exit(1)
            
    except AdminClientError as e:
        console.print(Panel(
            f"❌ Service error: {e}",
            title="Connection Error",
            border_style="red"
        ))
        raise typer.Exit(1)
    except Exception as e:
        console.print(Panel(
            f"❌ Unexpected error: {e}",
            title="Error",
            border_style="red"
        ))
        raise typer.Exit(1)
