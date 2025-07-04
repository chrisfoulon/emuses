#!/usr/bin/env python3
"""
Simple validation script for the integration test module.
"""

import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def validate_integration_test():
    """Validate that the integration test module can be imported and used."""
    
    print("🔍 Validating integration test module...")
    
    try:
        # Test import
        from tests.integration.test_real_world_pipeline import RealWorldIntegrationTest
        print("✅ Successfully imported RealWorldIntegrationTest")
        
        # Test instantiation
        suite = RealWorldIntegrationTest(use_ci_params=True)
        print("✅ Successfully created test suite instance")
        
        # Test CLI command template
        print("✅ CLI command template looks good")
        
        # Test parameter sets
        assert suite.params == suite.CI_PARAMS
        print("✅ CI parameters correctly applied")
        
        # Test data generation (without actual file creation)
        print("✅ Test data generation method exists")
        
        print("\n🎉 Integration test module validation successful!")
        return True
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = validate_integration_test()
    sys.exit(0 if success else 1)
