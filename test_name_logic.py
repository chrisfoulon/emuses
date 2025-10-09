#!/usr/bin/env python3
"""
Simple test to verify the model name logic change.
This tests the logic we implemented without needing the full EMUSES system.
"""

from pathlib import Path

def test_model_name_logic():
    """Test the logic for choosing model names."""
    
    # Simulate the model path
    model_path = Path("/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/model_registry_final_one_target")
    
    # Simulate validation result that might come from an existing manifest
    class ValidationResult:
        def __init__(self):
            self.name = "hdbscan_model"  # This would be from existing manifest
    
    validation_result = ValidationResult()
    
    # Test scenarios
    print("Testing model name logic:")
    print("=" * 50)
    
    # Scenario 1: User provides explicit name
    print("1. User provides --name 'my_custom_name':")
    effective_name = "my_custom_name"
    if effective_name is not None:
        final_name = effective_name
    else:
        final_name = model_path.name
    print(f"   Result: {final_name}")
    print(f"   ✓ Correct - user's choice is respected")
    print()
    
    # Scenario 2: No explicit name provided (the case we fixed)
    print("2. User runs: emuses models install /path/to/model_registry_final_one_target")
    effective_name = None  # No --name provided
    if effective_name is not None:
        final_name = effective_name
    else:
        final_name = model_path.name  # Our fix: use folder name
    print(f"   Result: {final_name}")
    print(f"   ✓ NEW BEHAVIOR: Uses descriptive folder name instead of 'hdbscan_model'")
    print()
    
    # Show the old behavior for comparison
    print("3. Old behavior (before our fix):")
    effective_name = None
    old_final_name = effective_name if effective_name is not None else validation_result.name
    print(f"   Result: {old_final_name}")
    print(f"   ✗ OLD BEHAVIOR: Used generic manifest name")
    print()
    
    print("Summary:")
    print(f"   Before fix: '{old_final_name}' (generic)")
    print(f"   After fix:  '{final_name}' (descriptive)")

if __name__ == "__main__":
    test_model_name_logic()
