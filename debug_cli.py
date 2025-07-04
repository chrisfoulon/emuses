#!/usr/bin/env python3
"""Debug script to test CLI execution step by step"""

import sys
import traceback
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test all necessary imports"""
    try:
        print("Testing imports...")
        from emuses.scripts.main import main
        print("✅ Main import successful")
        
        from emuses.config.optim_configs import optim_dict_hcp
        print("✅ UMAP config import successful")
        
        from emuses.config.optim_configs_predict import load_optim_dict_predict
        result = load_optim_dict_predict('optim_dict_predict')
        print("✅ Prediction config loading successful")
        
        from emuses.pipelines.emuses_pipeline import EMUSESPipeline
        print("✅ EMUSESPipeline import successful")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("🔧 Debugging CLI execution...")
    test_imports()
