"""
Post-installation validation for EMUSES.

This module runs after pip install to validate the installation
and provide helpful feedback to users.
"""

import os
import sys
from pathlib import Path


def validate_installation():
    """Run validation after installation and provide user feedback."""
    print("\n🔍 EMUSES Installation Validation")
    print("=" * 35)

    try:
        # Import our validation utilities
        from emuses.utils.dependency_check import (check_critical_dependencies,
                                                   get_install_command)

        all_ok, missing = check_critical_dependencies()

        if all_ok:
            print("✅ All critical dependencies found!")
            print("\n🚀 You can now use EMUSES:")
            print("   CLI: python -m emuses.cli --help")
            print(
                "   API: uvicorn emuses.api.main:create_app --factory --host 127.0.0.1 --port 8000"
            )
            print("   Full validation: python validate_deps.py")

        else:
            print("⚠️  Some critical dependencies are missing:")
            for pkg in missing:
                print(f"   - {pkg}")
            print("\n📦 To complete installation:")
            print(f"   {get_install_command(missing)}")
            print("\n   Then run: python validate_deps.py")

    except ImportError as e:
        print("❌ Installation validation failed:")
        print(f"   {e}")
        print("\n🔧 Try installing with complete dependencies:")
        print("   pip install -r requirements.txt")

    print("\n" + "=" * 35)


def main():
    """Entry point for post-install validation."""
    # Only run if this seems to be a fresh installation
    # (avoid running during development imports)
    if len(sys.argv) > 1 and "install" in sys.argv:
        validate_installation()


if __name__ == "__main__":
    validate_installation()
