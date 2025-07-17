"""
Entry point for running the EMUSES CLI as a module.

This module allows the CLI to be executed with `python -m emuses.cli`
without triggering the import-then-execute warning.
"""

from .main import main

if __name__ == "__main__":
    main()