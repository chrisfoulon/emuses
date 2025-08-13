"""Model registry CLI commands.

This module provides command-line interface for model registry operations
including installation, listing, searching, and management.
"""
import logging
from pathlib import Path
from typing import Annotated, List, Optional

import typer
from rich.console import Console
from rich.table import Table

from emuses.tools.local_model_registry import LocalModelRegistry
from emuses.tools.model_registry_factory import ModelRegistryFactory, ErrorMessages
from emuses.tools.base_model_registry import BaseModelRegistry
from emuses.tools.storage_manager import StorageManager
from .security import validate_path

logger = logging.getLogger(__name__)
console = Console()


def get_registry(registry_path: Optional[Path] = None, 
                user_id: Optional[str] = None,
                workspace_id: Optional[str] = None) -> BaseModelRegistry:
    """Get appropriate model registry based on deployment mode using factory.
    
    Parameters
    ----------
    registry_path : Optional[Path]
        Custom registry path for local mode
    user_id : Optional[str]
        User ID for database/cloud modes
    workspace_id : Optional[str]
        Workspace ID for database/cloud modes
        
    Returns
    -------
    BaseModelRegistry
        Appropriate registry instance for current deployment mode
    """
    factory = ModelRegistryFactory()
    
    try:
        # Auto-detect mode and create registry
        registry = factory.create_registry(
            registry_path=registry_path,
            user_id=user_id,
            fallback=True
        )
        
        # Provide user feedback about mode
        if isinstance(registry, LocalModelRegistry):
            if registry_path:
                console.print(f"[blue]ℹ️ Using local registry at: {registry_path}[/blue]")
            else:
                console.print("[blue]ℹ️ Using local registry mode[/blue]")
        else:
            registry_type = registry.__class__.__name__
            console.print(f"[green]ℹ️ Using {registry_type} mode[/green]")
            
        return registry
        
    except Exception as e:
        error_msg = ErrorMessages.format_error(ErrorMessages.REGISTRY_CREATION_FAILED, error=str(e))
        console.print(f"[yellow]⚠️ {error_msg}[/yellow]")
        console.print(f"[blue]ℹ️ {ErrorMessages.FALLBACK_TO_LOCAL}[/blue]")
        return LocalModelRegistry(registry_path=registry_path)


def get_registry_with_params(registry_path: Optional[Path] = None, 
                            workspace_id: Optional[str] = None,
                            user_id: Optional[str] = None,
                            include_public: bool = True):
    """Get registry with additional parameters for cross-mode operations.
    
    Parameters
    ----------
    registry_path : Path, optional
        Custom registry path (only used in local mode)
    workspace_id : str, optional
        Workspace ID for database/cloud mode operations
    user_id : str, optional
        User ID for database/cloud mode operations
    include_public : bool, default=True
        Whether to include public models in results
        
    Returns
    -------
    Tuple[BaseModelRegistry, dict]
        Registry instance and additional parameters for operations
    """
    # Validate registry path if provided
    validated_path = None
    if registry_path:
        validated_path = Path(validate_path(str(registry_path)))
    
    # Get registry using factory
    registry = get_registry(
        registry_path=validated_path,
        user_id=user_id,
        workspace_id=workspace_id
    )
    
    # Build extra parameters for registry operations
    extra_params = {
        'user_id': user_id,
        'workspace_id': workspace_id,
        'include_public': include_public
    }
    
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
            
            # Display storage warning if present
            if "storage_warning" in result:
                warning = result["storage_warning"]
                if warning["level"] == "critical":
                    console.print(f"⚠️ [red bold]CRITICAL STORAGE WARNING[/red bold]: {warning['message']}")
                    console.print(f"   • Registry size: [yellow]{warning['registry_size_mb']:.1f} MB[/yellow]")
                    console.print(f"   • Available space: [red]{warning['available_space_mb']:.1f} MB[/red]")
                    console.print("   Consider cleaning up old models or freeing disk space.")
                elif warning["level"] == "warning":
                    console.print(f"⚠️ [yellow]STORAGE WARNING[/yellow]: {warning['message']}")
                    console.print(f"   • Registry size: [cyan]{warning['registry_size_mb']:.1f} MB[/cyan]")
                    console.print(f"   • Available space: [yellow]{warning['available_space_mb']:.1f} MB[/yellow]")
                    console.print("   Monitor disk usage to prevent storage issues.")
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
    registry_path: Annotated[Optional[Path], typer.Option("--registry", "-r", help="Custom registry path")] = None,
    workspace_id: Annotated[Optional[str], typer.Option("--workspace", "-w", help="Workspace ID (database/cloud modes)")] = None,
    user_id: Annotated[Optional[str], typer.Option("--user", "-u", help="User ID (database/cloud modes)")] = None,
    include_public: Annotated[bool, typer.Option("--public/--no-public", help="Include public models")] = True
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
        # Get registry with parameters
        registry, extra_params = get_registry_with_params(
            registry_path=registry_path,
            workspace_id=workspace_id,
            user_id=user_id,
            include_public=include_public
        )
        
        # Build filters for backward compatibility
        filters = {}
        if type_filter:
            filters["type"] = type_filter
        if tags:
            filters["tags"] = tags
        
        # Get models using new interface
        models = registry.list_models(filters=filters, **extra_params)
        
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


@models_app.command(help="Show model registry mode configuration and status")
def mode_info() -> None:
    """Show current model registry mode configuration and capabilities.
    
    Displays information about the current registry mode, its capabilities,
    configuration options, and mode-specific parameters.
    """
    try:
        factory = ModelRegistryFactory()
        
        console.print(f"\n[bold cyan]Model Registry Mode Configuration[/bold cyan]")
        
        # Detect current mode
        registry = factory.create_registry(fallback=True)
        registry_type = registry.__class__.__name__
        
        # Determine mode from registry type
        if isinstance(registry, LocalModelRegistry):
            from emuses.tools.model_registry_factory import RegistryMode
            mode = RegistryMode.LOCAL
        else:
            # For other registry types, we'd detect the mode here
            from emuses.tools.model_registry_factory import RegistryMode
            if "DatabaseModelRegistry" in registry_type:
                mode = RegistryMode.DATABASE
            elif "CloudModelRegistry" in registry_type:
                mode = RegistryMode.CLOUD
            else:
                mode = RegistryMode.LOCAL
        
        console.print(f"Current Mode: [green]{mode.value.upper()}[/green]")
        console.print(f"Registry Type: [blue]{registry_type}[/blue]")
        
        # Show mode configuration
        config = factory.get_mode_config(mode)
        console.print(f"\n[bold]Mode Configuration:[/bold]")
        console.print(f"  Requires Authentication: [yellow]{config['requires_auth']}[/yellow]")
        console.print(f"  Requires Database: [yellow]{config['requires_database']}[/yellow]")
        console.print(f"  Multi-User Support: [yellow]{config['supports_multi_user']}[/yellow]")
        console.print(f"  Cloud Storage Support: [yellow]{config['supports_cloud_storage']}[/yellow]")
        
        # Show capabilities
        console.print(f"\n[bold]Registry Capabilities:[/bold]")
        capabilities = ['list_models', 'install_model', 'get_model_info', 
                      'search_models', 'remove_model', 'get_model_file_path']
        
        for capability in capabilities:
            has_capability = factory.has_capability(registry, capability)
            status = "[green]✓[/green]" if has_capability else "[red]✗[/red]"
            console.print(f"  {capability}: {status}")
        
        # Show interface validation
        is_valid = factory.validate_interface(registry)
        validation_status = "[green]Valid[/green]" if is_valid else "[red]Invalid[/red]"
        console.print(f"\nInterface Validation: {validation_status}")
        
        # Show compatibility
        is_compatible = factory.is_compatible(registry, mode)
        compatibility_status = "[green]Compatible[/green]" if is_compatible else "[red]Incompatible[/red]"
        console.print(f"Mode Compatibility: {compatibility_status}")
        
        # Show CLI parameter help
        console.print(f"\n[bold]Available CLI Parameters:[/bold]")
        console.print("  [dim]--registry, -r[/dim]    Custom registry path (local mode)")
        console.print("  [dim]--workspace, -w[/dim]   Workspace ID (database/cloud modes)")
        console.print("  [dim]--user, -u[/dim]        User ID (database/cloud modes)")
        console.print("  [dim]--public/--no-public[/dim] Include public models")
        
        # Show mode-specific help
        if mode == RegistryMode.LOCAL:
            console.print(f"\n[bold blue]Local Mode Usage:[/bold blue]")
            console.print("  • Models stored in local filesystem")
            console.print("  • Use --registry to specify custom path")
            console.print("  • No authentication required")
        elif mode == RegistryMode.DATABASE:
            console.print(f"\n[bold green]Database Mode Usage:[/bold green]")
            console.print("  • Models stored in database with files")
            console.print("  • Use --workspace for workspace-specific operations")
            console.print("  • Use --user for user-specific operations")
            console.print("  • Authentication may be required")
        elif mode == RegistryMode.CLOUD:
            console.print(f"\n[bold magenta]Cloud Mode Usage:[/bold magenta]")
            console.print("  • Models stored in cloud with database metadata")
            console.print("  • Use --workspace for workspace-specific operations")
            console.print("  • Use --user for user-specific operations")
            console.print("  • Authentication required")
            console.print("  • Supports cloud storage tiers and CDN")
        
    except Exception as e:
        console.print(f"❌ Error getting mode information: [red]{str(e)}[/red]")
        raise typer.Exit(1)


@models_app.command(help="Show storage usage and threshold information")
def storage(
    registry_path: Annotated[Optional[Path], typer.Option("--registry", "-r", help="Custom registry path")] = None
) -> None:
    """Show storage usage and threshold information.
    
    Displays disk usage, registry size, and storage threshold status
    to help users manage their model storage effectively.
    
    Parameters
    ----------
    registry_path : Path, optional
        Custom registry location. If not provided, uses default location.
    """
    try:
        if registry_path:
            registry_path = Path(validate_path(str(registry_path)))
        
        # Initialize storage manager (or get from registry)
        if registry_path:
            storage_manager = StorageManager(registry_path)
        else:
            # Use default location
            default_path = Path.home() / ".emuses" / "model_registry"
            storage_manager = StorageManager(default_path)
        
        # Get storage information
        info = storage_manager.get_storage_info()
        
        # Display storage overview
        console.print(f"\n[bold cyan]Storage Information[/bold cyan]")
        console.print(f"Registry Path: [dim]{storage_manager.registry_path}[/dim]")
        console.print(f"Registry Size: [green]{info['registry_size_mb']:.1f} MB[/green] ({info['registry_size_bytes']:,} bytes)")
        console.print(f"Total Disk Space: [cyan]{info['total_disk_gb']:.1f} GB[/cyan]")
        console.print(f"Available Space: [blue]{info['free_disk_mb']:.1f} MB[/blue]")
        console.print(f"Disk Usage: [yellow]{info['usage_percent']:.1f}%[/yellow]")
        
        # Display threshold information
        console.print(f"\n[bold yellow]Storage Thresholds[/bold yellow]")
        console.print(f"Warning Threshold: [yellow]{info['threshold_warning']:.0f}%[/yellow]")
        console.print(f"Critical Threshold: [red]{info['threshold_critical']:.0f}%[/red]")
        console.print(f"Monitoring: [{'green' if info['threshold_enabled'] else 'red'}]{'Enabled' if info['threshold_enabled'] else 'Disabled'}[/{'green' if info['threshold_enabled'] else 'red'}]")
        
        # Check current status and show warnings
        warning = storage_manager.check_storage_thresholds()
        if warning:
            console.print(f"\n[bold]Current Status:[/bold]")
            if warning.level == "critical":
                console.print(f"🚨 [red bold]CRITICAL[/red bold]: {warning.message}")
                console.print("   [red]Immediate action recommended:[/red]")
                console.print("   • Clean up old or unused models")
                console.print("   • Free up disk space")
                console.print("   • Consider moving models to external storage")
            elif warning.level == "warning":
                console.print(f"⚠️  [yellow]WARNING[/yellow]: {warning.message}")
                console.print("   [yellow]Monitoring recommended:[/yellow]")
                console.print("   • Monitor disk usage regularly")
                console.print("   • Plan for disk cleanup if usage continues to grow")
                console.print("   • Consider setting up alerts for critical levels")
        else:
            console.print(f"\n[green]✅ Storage levels are healthy[/green]")
        
        # Storage recommendations
        console.print(f"\n[bold]Storage Management Tips:[/bold]")
        console.print("• Use '[cyan]emuses models list[/cyan]' to see all installed models")
        console.print("• Remove unused models to free space")
        console.print("• Monitor storage regularly to prevent issues")
        console.print("• Consider archiving older models externally")
        
    except Exception as e:
        console.print(f"❌ Error getting storage information: [red]{str(e)}[/red]")
        raise typer.Exit(1)