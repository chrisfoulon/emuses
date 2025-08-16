"""Workspace CLI commands for EMUSES multi-user service.

This module provides command-line interface for workspace management
including create, list, and select operations in multi-user deployments.
"""

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table

console = Console()
workspace_app = typer.Typer(help="Workspace management commands")


@workspace_app.command("list")
def list_workspaces(
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Authentication token"),
    service_url: Optional[str] = typer.Option(None, "--service-url", help="Multi-user service URL"),
):
    """List available workspaces for the current user."""
    try:
        from emuses.cli.service_client import ServiceClient
        
        client = ServiceClient(
            service_url=service_url,
            token=token
        )
        
        # Make API call to list workspaces
        response = client.get("/workspaces/")
        
        if response.status_code == 200:
            workspaces = response.json()
            
            if not workspaces:
                console.print("[yellow]No workspaces found[/yellow]")
                return
                
            table = Table(title="Available Workspaces")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Description", style="white")
            table.add_column("Created", style="dim")
            
            for workspace in workspaces:
                table.add_row(
                    workspace.get("id", ""),
                    workspace.get("name", ""),
                    workspace.get("description", "")[:50] + "..." if len(workspace.get("description", "")) > 50 else workspace.get("description", ""),
                    workspace.get("created_at", "")[:10] if workspace.get("created_at") else ""
                )
            
            console.print(table)
        else:
            console.print(f"[red]Error listing workspaces: {response.status_code}[/red]")
            if response.text:
                console.print(f"Details: {response.text}")
                
    except ImportError:
        console.print("[red]Multi-user service client not available[/red]")
        console.print("This command requires multi-user dependencies.")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@workspace_app.command("create") 
def create_workspace(
    name: str = typer.Argument(..., help="Workspace name"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Workspace description"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Authentication token"),
    service_url: Optional[str] = typer.Option(None, "--service-url", help="Multi-user service URL"),
):
    """Create a new workspace."""
    try:
        from emuses.cli.service_client import ServiceClient
        
        client = ServiceClient(
            service_url=service_url,
            token=token
        )
        
        # Prepare workspace data
        workspace_data = {
            "name": name,
            "description": description or f"Workspace: {name}"
        }
        
        # Make API call to create workspace
        response = client.post("/workspaces/", json=workspace_data)
        
        if response.status_code == 201:
            workspace = response.json()
            console.print(f"[green]✓[/green] Workspace created successfully!")
            console.print(f"  ID: {workspace.get('id')}")
            console.print(f"  Name: {workspace.get('name')}")
            console.print(f"  Description: {workspace.get('description')}")
        else:
            console.print(f"[red]Error creating workspace: {response.status_code}[/red]")
            if response.text:
                console.print(f"Details: {response.text}")
                
    except ImportError:
        console.print("[red]Multi-user service client not available[/red]")
        console.print("This command requires multi-user dependencies.")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@workspace_app.command("info")
def workspace_info(
    workspace_id: str = typer.Argument(..., help="Workspace ID"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Authentication token"),
    service_url: Optional[str] = typer.Option(None, "--service-url", help="Multi-user service URL"),
):
    """Show detailed information about a workspace."""
    try:
        from emuses.cli.service_client import ServiceClient
        
        client = ServiceClient(
            service_url=service_url,
            token=token
        )
        
        # Make API call to get workspace info
        response = client.get(f"/workspaces/{workspace_id}")
        
        if response.status_code == 200:
            workspace = response.json()
            
            console.print(f"[bold]Workspace Information[/bold]")
            console.print(f"  ID: [cyan]{workspace.get('id')}[/cyan]")
            console.print(f"  Name: [green]{workspace.get('name')}[/green]")
            console.print(f"  Description: {workspace.get('description')}")
            console.print(f"  Created: {workspace.get('created_at')}")
            console.print(f"  Updated: {workspace.get('updated_at')}")
            
            # Show usage statistics if available
            if 'stats' in workspace:
                stats = workspace['stats']
                console.print(f"\n[bold]Usage Statistics[/bold]")
                console.print(f"  Models: {stats.get('model_count', 0)}")
                console.print(f"  Datasets: {stats.get('dataset_count', 0)}")
                console.print(f"  Jobs: {stats.get('job_count', 0)}")
                
        elif response.status_code == 404:
            console.print(f"[red]Workspace '{workspace_id}' not found[/red]")
        else:
            console.print(f"[red]Error getting workspace info: {response.status_code}[/red]")
            if response.text:
                console.print(f"Details: {response.text}")
                
    except ImportError:
        console.print("[red]Multi-user service client not available[/red]")
        console.print("This command requires multi-user dependencies.")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    workspace_app()