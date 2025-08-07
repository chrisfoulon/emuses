"""Model registry CLI commands.

This module provides command-line interface for model registry operations
including installation, listing, searching, and management.
"""
import logging
from pathlib import Path
from typing import Annotated, List, Optional, Union

import typer
from rich.console import Console
from rich.table import Table

from emuses.tools.local_model_registry import LocalModelRegistry
from .security import validate_path

logger = logging.getLogger(__name__)
console = Console()


def get_registry() -> Union[LocalModelRegistry, 'DatabaseModelRegistry']:
    """Get appropriate model registry based on deployment mode.
    
    Returns LocalModelRegistry for LOCAL mode, DatabaseModelRegistry
    for MULTI_USER/PRODUCTION modes with database and authentication.
    
    Returns
    -------
    Union[LocalModelRegistry, DatabaseModelRegistry]
        Appropriate registry instance for current deployment mode
    """
    try:
        from emuses.multi_user_service.deployment_config import (
            detect_deployment_mode, is_service_mode_enabled
        )
        
        # Check if multi-user service is enabled
        if not is_service_mode_enabled():
            return LocalModelRegistry()
        
        deployment_mode = detect_deployment_mode()
        
        if deployment_mode.value == "LOCAL":
            return LocalModelRegistry()
        
        # For MULTI_USER and PRODUCTION modes, inform user about API usage
        console.print("[yellow]ℹ️ Database mode detected. For database operations, please use the API endpoints or web interface.[/yellow]")
        console.print("[blue]ℹ️ CLI commands in multi-user mode are limited to local operations only.[/blue]")
        
        # For now, fall back to local mode for CLI operations
        # TODO: Implement proper CLI authentication in future versions
        return LocalModelRegistry()
            
    except ImportError:
        # Multi-user service not available, use local registry
        return LocalModelRegistry()
    except Exception as e:
        console.print(f"[yellow]⚠️ Error detecting deployment mode: {e}[/yellow]")
        return LocalModelRegistry()


def get_registry_with_params(registry_path: Optional[Path] = None, workspace_id: Optional[str] = None):
    """Get registry with additional parameters for database mode.
    
    Parameters
    ----------
    registry_path : Path, optional
        Custom registry path (only used in local mode)
    workspace_id : str, optional
        Workspace ID for database mode operations
        
    Returns
    -------
    Tuple[Union[LocalModelRegistry, DatabaseModelRegistry], dict]
        Registry instance and additional parameters for operations
    """
    registry = get_registry()
    extra_params = {}
    
    # For local registry, apply registry_path if provided
    if isinstance(registry, LocalModelRegistry) and registry_path:
        validated_path = Path(validate_path(str(registry_path)))
        registry = LocalModelRegistry(registry_path=validated_path)
    
    # For database registry, add workspace_id to params
    if hasattr(registry, 'db_session') and workspace_id:
        extra_params['workspace_id'] = workspace_id
    
    return registry, extra_params

# Create models command group
models_app = typer.Typer(
    name="models",
    help="Model registry commands for managing trained models",
    no_args_is_help=True
)


@models_app.command(help="Install a model into the registry")
def install(
    model_path: Annotated[Path, typer.Argument(help="Path to model file or directory")],
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="Custom name for the model")] = None,
    registry_path: Annotated[Optional[Path], typer.Option("--registry", "-r", help="Custom registry path")] = None
) -> None:
    """Install a model into the local registry.
    
    Validates the model, installs it using ModelIOManager, and adds it to the registry index.
    
    Parameters
    ----------
    model_path : Path
        Path to the model file or directory to install
    name : str, optional
        Custom name for the model. If not provided, uses name from manifest.
    registry_path : Path, optional
        Custom registry location. If not provided, uses default location.
    """
    try:
        # Validate and resolve paths
        model_path = Path(validate_path(str(model_path)))
        if not model_path.exists():
            console.print(f"❌ Model file not found: [red]{model_path}[/red]")
            raise typer.Exit(1)
        
        # Get appropriate registry
        registry, extra_params = get_registry_with_params(registry_path=registry_path)
        
        console.print(f"Installing model from [cyan]{model_path}[/cyan]...")
        
        # Install model using local registry (simplified for CLI)
        result = registry.install_model(model_path, name=name)
        
        if result["status"] == "success":
            model_name = result.get('name', 'Unknown')
            model_id = result.get('model_id', 'Unknown')
            console.print(f"✅ Successfully installed model '[green]{model_name}[/green]' with ID [blue]{model_id}[/blue]")
        else:
            console.print(f"❌ Installation failed: [red]{result['message']}[/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"❌ Error installing model: [red]{str(e)}[/red]")
        raise typer.Exit(1)


@models_app.command(help="List models in the registry")
def list(
    type_filter: Annotated[Optional[str], typer.Option("--type", "-t", help="Filter by model type")] = None,
    tags: Annotated[Optional[List[str]], typer.Option("--tag", help="Filter by tags (can be repeated)")] = None,
    registry_path: Annotated[Optional[Path], typer.Option("--registry", "-r", help="Custom registry path")] = None
) -> None:
    """List models in the registry with optional filtering.
    
    Parameters
    ----------
    type_filter : str, optional
        Filter models by type (classification, detection, etc.)
    tags : List[str], optional  
        Filter models by tags (all specified tags must be present)
    registry_path : Path, optional
        Custom registry location. If not provided, uses default location.
    """
    try:
        if registry_path:
            registry_path = Path(validate_path(str(registry_path)))
        
        # Initialize registry
        registry = LocalModelRegistry(registry_path=registry_path)
        
        # Build filters
        filters = {}
        if type_filter:
            filters["type"] = type_filter
        if tags:
            filters["tags"] = tags
        
        # Get models
        models = registry.list_models(filters=filters)
        
        if not models:
            if filters:
                console.print("No models found matching the specified filters.")
            else:
                console.print("No models found in registry.")
            return
        
        # Create and display table
        table = Table(title=f"Model Registry ({len(models)} models)")
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Description", style="dim")
        table.add_column("Model ID", style="blue")
        
        for model in models:
            table.add_row(
                model.get("name", "Unknown"),
                model.get("version", "Unknown"),
                model.get("type", "Unknown"), 
                model.get("description", "")[:50] + ("..." if len(model.get("description", "")) > 50 else ""),
                model.get("model_id", "Unknown")
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"❌ Error listing models: [red]{str(e)}[/red]")
        raise typer.Exit(1)


@models_app.command(help="Get detailed information about a model")
def info(
    model_id: Annotated[str, typer.Argument(help="Model ID to get information for")],
    registry_path: Annotated[Optional[Path], typer.Option("--registry", "-r", help="Custom registry path")] = None
) -> None:
    """Get detailed information about a specific model.
    
    Parameters
    ----------
    model_id : str
        ID of the model to retrieve information for
    registry_path : Path, optional
        Custom registry location. If not provided, uses default location.
    """
    try:
        if registry_path:
            registry_path = Path(validate_path(str(registry_path)))
        
        # Initialize registry
        registry = LocalModelRegistry(registry_path=registry_path)
        
        # Get model info
        model_info = registry.get_model_info(model_id)
        
        if not model_info:
            console.print(f"❌ Model with ID '[red]{model_id}[/red]' not found")
            raise typer.Exit(1)
        
        # Display detailed information
        console.print(f"\n[bold cyan]Model Information[/bold cyan]")
        console.print(f"Name: [green]{model_info.get('name', 'Unknown')}[/green]")
        console.print(f"Model ID: [blue]{model_info.get('model_id', 'Unknown')}[/blue]")
        console.print(f"Version: [yellow]{model_info.get('version', 'Unknown')}[/yellow]")
        console.print(f"Type: [magenta]{model_info.get('type', 'Unknown')}[/magenta]")
        console.print(f"Description: {model_info.get('description', 'No description available')}")
        console.print(f"Installed: [dim]{model_info.get('installed_at', 'Unknown')}[/dim]")
        console.print(f"Source Path: [dim]{model_info.get('source_path', 'Unknown')}[/dim]")
        
        # Display tags if available
        tags = model_info.get("tags", [])
        if tags:
            console.print(f"Tags: [cyan]{', '.join(tags)}[/cyan]")
        
        # Display manifest info if available
        manifest = model_info.get("manifest", {})
        if manifest and isinstance(manifest, dict):
            console.print(f"\n[bold]Manifest Details:[/bold]")
            for key, value in manifest.items():
                if key not in ["name", "version", "type", "description"]:  # Skip already displayed
                    console.print(f"  {key}: {value}")
        
    except Exception as e:
        console.print(f"❌ Error getting model info: [red]{str(e)}[/red]")
        raise typer.Exit(1)


@models_app.command(help="Search for models by name or description")
def search(
    query: Annotated[str, typer.Argument(help="Search query")],
    registry_path: Annotated[Optional[Path], typer.Option("--registry", "-r", help="Custom registry path")] = None
) -> None:
    """Search for models by name, description, or tags.
    
    Parameters
    ----------
    query : str
        Search query string (case-insensitive)
    registry_path : Path, optional
        Custom registry location. If not provided, uses default location.
    """
    try:
        if registry_path:
            registry_path = Path(validate_path(str(registry_path)))
        
        # Initialize registry
        registry = LocalModelRegistry(registry_path=registry_path)
        
        # Search models
        results = registry.search_models(query)
        
        if not results:
            console.print(f"No models found matching '[yellow]{query}[/yellow]'")
            return
        
        # Create and display results table
        table = Table(title=f"Search Results for '{query}' ({len(results)} matches)")
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Description", style="dim")
        table.add_column("Model ID", style="blue")
        
        for model in results:
            table.add_row(
                model.get("name", "Unknown"),
                model.get("version", "Unknown"),
                model.get("type", "Unknown"),
                model.get("description", "")[:50] + ("..." if len(model.get("description", "")) > 50 else ""),
                model.get("model_id", "Unknown")
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"❌ Error searching models: [red]{str(e)}[/red]")
        raise typer.Exit(1)


@models_app.command(help="Show registry status and statistics")
def status(
    registry_path: Annotated[Optional[Path], typer.Option("--registry", "-r", help="Custom registry path")] = None
) -> None:
    """Show registry status and statistics.
    
    Parameters
    ----------
    registry_path : Path, optional
        Custom registry location. If not provided, uses default location.
    """
    try:
        if registry_path:
            registry_path = Path(validate_path(str(registry_path)))
        
        # Initialize registry
        registry = LocalModelRegistry(registry_path=registry_path)
        
        # Get registry info
        info = registry.get_registry_info()
        
        console.print(f"\n[bold cyan]Model Registry Status[/bold cyan]")
        console.print(f"Registry Path: [dim]{info.get('registry_path', 'Unknown')}[/dim]")
        console.print(f"Version: [yellow]{info.get('version', 'Unknown')}[/yellow]")
        console.print(f"Model Count: [green]{info.get('model_count', 0)}[/green]")
        console.print(f"Created: [dim]{info.get('created_at', 'Unknown')}[/dim]")
        console.print(f"Last Updated: [dim]{info.get('last_updated', 'Unknown')}[/dim]")
        
        if "error" in info:
            console.print(f"⚠️  Warning: [yellow]{info['error']}[/yellow]")
        
        # Validate registry
        is_valid, issues = registry.validate_index()
        if is_valid:
            console.print("✅ Registry index is valid")
        else:
            console.print("⚠️  Registry index issues found:")
            for issue in issues:
                console.print(f"  - [yellow]{issue}[/yellow]")
        
    except Exception as e:
        console.print(f"❌ Error getting registry status: [red]{str(e)}[/red]")
        raise typer.Exit(1)


@models_app.command(help="Remove a model from the registry")
def remove(
    model_id: Annotated[str, typer.Argument(help="Model ID to remove")],
    keep_files: Annotated[bool, typer.Option("--keep-files", help="Keep model files on disk")] = False,
    registry_path: Annotated[Optional[Path], typer.Option("--registry", "-r", help="Custom registry path")] = None
) -> None:
    """Remove a model from the registry.
    
    Parameters
    ----------
    model_id : str
        ID of the model to remove
    keep_files : bool, default=False
        If True, keeps model files on disk (only removes from index)
    registry_path : Path, optional
        Custom registry location. If not provided, uses default location.
    """
    try:
        if registry_path:
            registry_path = Path(validate_path(str(registry_path)))
        
        # Initialize registry
        registry = LocalModelRegistry(registry_path=registry_path)
        
        # Get model info before removal for display
        model_info = registry.get_model_info(model_id)
        if not model_info:
            console.print(f"❌ Model with ID '[red]{model_id}[/red]' not found")
            raise typer.Exit(1)
        
        # Confirm removal
        model_name = model_info.get("name", "Unknown")
        if not typer.confirm(f"Remove model '[cyan]{model_name}[/cyan]' (ID: {model_id})?"):
            console.print("Removal cancelled.")
            return
        
        # Remove model
        result = registry.remove_model(model_id, cleanup_files=not keep_files)
        
        if result["status"] == "success":
            action = "removed from registry" if keep_files else "removed completely"
            console.print(f"✅ Model '[green]{model_name}[/green]' {action}")
        else:
            console.print(f"❌ Removal failed: [red]{result['message']}[/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"❌ Error removing model: [red]{str(e)}[/red]")
        raise typer.Exit(1)


@models_app.command(help="Clean up orphaned model directories")
def cleanup(
    registry_path: Annotated[Optional[Path], typer.Option("--registry", "-r", help="Custom registry path")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be removed without actually removing")] = False
) -> None:
    """Clean up orphaned model directories.
    
    Removes model directories that exist on the filesystem but are not
    referenced in the registry index.
    
    Parameters
    ----------
    registry_path : Path, optional
        Custom registry location. If not provided, uses default location.
    dry_run : bool, default=False
        If True, shows what would be removed without actually removing files
    """
    try:
        if registry_path:
            registry_path = Path(validate_path(str(registry_path)))
        
        # Initialize registry
        registry = LocalModelRegistry(registry_path=registry_path)
        
        if dry_run:
            console.print("[yellow]DRY RUN MODE - No files will be removed[/yellow]")
            
            # Find orphaned directories manually for dry run
            index = registry._load_index()
            registered_models = set(index["models"].keys())
            orphaned_dirs = []
            
            if registry.models_path.exists():
                for model_dir in registry.models_path.iterdir():
                    if model_dir.is_dir() and model_dir.name not in registered_models:
                        orphaned_dirs.append(model_dir.name)
            
            if orphaned_dirs:
                console.print(f"Would remove {len(orphaned_dirs)} orphaned directories:")
                for dir_name in orphaned_dirs:
                    console.print(f"  - [red]{dir_name}[/red]")
            else:
                console.print("No orphaned directories found.")
        else:
            # Perform actual cleanup
            result = registry.cleanup_orphaned_models()
            
            if result["removed_directories"] > 0:
                console.print(f"✅ Removed {result['removed_directories']} orphaned directories:")
                for dir_name in result["directories"]:
                    console.print(f"  - [red]{dir_name}[/red]")
            else:
                console.print("No orphaned directories found to remove.")
            
            if result["status"] == "error":
                console.print(f"⚠️  Cleanup completed with errors: [yellow]{result.get('error', 'Unknown error')}[/yellow]")
        
    except Exception as e:
        console.print(f"❌ Error during cleanup: [red]{str(e)}[/red]")
        raise typer.Exit(1)


@models_app.command(help="Show information about database mode and API usage")
def api_info() -> None:
    """Show information about using model registry in database mode.
    
    Provides guidance on using the FastAPI endpoints for model registry
    operations in multi-user deployment modes.
    """
    try:
        from emuses.multi_user_service.deployment_config import (
            detect_deployment_mode, is_service_mode_enabled
        )
        
        if not is_service_mode_enabled():
            console.print("[blue]ℹ️ Multi-user service is disabled. Using local registry mode.[/blue]")
            console.print("[green]✅ All CLI commands are available for local operations.[/green]")
            return
            
        deployment_mode = detect_deployment_mode()
        
        console.print(f"\\n[bold cyan]EMUSES Model Registry - {deployment_mode.value.title()} Mode[/bold cyan]")
        
        if deployment_mode.value == "LOCAL":
            console.print("[green]✅ CLI commands fully supported in local mode[/green]")
        else:
            console.print("[yellow]⚠️ Database mode detected - CLI operations limited[/yellow]")
            console.print("\\n[bold]For database operations, use the FastAPI endpoints:[/bold]")
            console.print("")
            console.print("[cyan]📝 Register a model:[/cyan]")
            console.print("  POST /api/v1/models/register")
            console.print("")
            console.print("[cyan]📋 List models:[/cyan]")
            console.print("  GET /api/v1/models/")
            console.print("")
            console.print("[cyan]🔍 Search models:[/cyan]")
            console.print("  GET /api/v1/models/search?query=<search_term>")
            console.print("")
            console.print("[cyan]📊 Get model info:[/cyan]")
            console.print("  GET /api/v1/models/{model_id}")
            console.print("")
            console.print("[cyan]🔐 Manage permissions:[/cyan]")
            console.print("  GET/POST/DELETE /api/v1/models/{model_id}/permissions")
            console.print("")
            console.print("[blue]💡 Access API documentation at /api/docs when service is running[/blue]")
        
        console.print("\\n[bold]Current deployment configuration:[/bold]")
        console.print(f"  Mode: [yellow]{deployment_mode.value}[/yellow]")
        console.print(f"  Service enabled: [yellow]{is_service_mode_enabled()}[/yellow]")
        
    except ImportError:
        console.print("[green]✅ Multi-user service not available - using local registry mode[/green]")
        console.print("[green]✅ All CLI commands are fully functional[/green]")
    except Exception as e:
        console.print(f"[red]❌ Error checking deployment mode: {str(e)}[/red]")


@models_app.command(help="Show detailed registry statistics")
def stats(
    registry_path: Annotated[Optional[Path], typer.Option("--registry", "-r", help="Custom registry path")] = None
) -> None:
    """Show detailed registry statistics.
    
    Parameters
    ----------
    registry_path : Path, optional
        Custom registry location. If not provided, uses default location.
    """
    try:
        if registry_path:
            registry_path = Path(validate_path(str(registry_path)))
        
        # Initialize registry
        registry = LocalModelRegistry(registry_path=registry_path)
        
        # Get detailed stats
        stats = registry.get_registry_stats()
        
        console.print(f"\n[bold cyan]Detailed Registry Statistics[/bold cyan]")
        console.print(f"Registry Path: [dim]{stats.get('registry_path', 'Unknown')}[/dim]")
        console.print(f"Total Models: [green]{stats.get('total_models', 0)}[/green]")
        
        # Storage usage
        storage_mb = stats.get('storage_usage', 0) / (1024 * 1024)
        console.print(f"Storage Usage: [yellow]{storage_mb:.2f} MB[/yellow]")
        
        # Model types breakdown
        model_types = stats.get('model_types', {})
        if model_types:
            console.print(f"\n[bold]Models by Type:[/bold]")
            for model_type, count in model_types.items():
                console.print(f"  {model_type}: [cyan]{count}[/cyan]")
        
        # Temporal information
        if stats.get('newest_model'):
            console.print(f"\nNewest Model: [green]{stats['newest_model']}[/green]")
        if stats.get('oldest_model'):
            console.print(f"Oldest Model: [dim]{stats['oldest_model']}[/dim]")
        
        if "error" in stats:
            console.print(f"\n⚠️  Warning: [yellow]{stats['error']}[/yellow]")
        
    except Exception as e:
        console.print(f"❌ Error getting registry statistics: [red]{str(e)}[/red]")
        raise typer.Exit(1)