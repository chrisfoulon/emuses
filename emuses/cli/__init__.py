"""EMUSES CLI module."""

from .security import SecurityError, sanitize_input, validate_path

__all__ = [
    "validate_path",
    "sanitize_input",
    "SecurityError",
]


# Main CLI components available via lazy import to avoid module import warnings
# when running as `python -m emuses.cli.main`
def _get_main_components():
    """Lazy import of main CLI components to avoid sys.modules conflicts."""
    from .main import app, create_typer_app, secure_path_resolver
    return app, create_typer_app, secure_path_resolver
