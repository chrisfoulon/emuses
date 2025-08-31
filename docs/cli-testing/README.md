# EMUSES CLI Testing Framework

## Overview
This directory contains a systematic approach to testing all EMUSES CLI functionality. The testing is designed to be comprehensive, reproducible, and well-documented.

## Testing Philosophy
Based on CLI testing best practices, we use a multi-layered approach:
1. **Discovery**: Map documented vs implemented commands
2. **Basic Functionality**: Test individual commands work as expected
3. **Integration**: Test command chains and workflows
4. **Edge Cases**: Test error conditions and invalid inputs
5. **Output Validation**: Verify generated files and data are correct

## Quick Start
1. Follow setup instructions in `00_setup_and_installation.md`
2. Run the battle-tested full pipeline in `02_basic_functionality_tests.md`
3. Use that trained model to test dependent commands
4. Document findings as you go

## Test Result Categories
- ✅ **Works**: Command executes successfully with expected output
- ❌ **Doesn't Exist**: Command documented but not implemented
- 🔧 **Broken**: Command exists but fails with error
- ⚠️ **Partial**: Command runs but output seems incomplete/suspicious  
- 🐌 **Performance**: Command works but unusably slow
- 🤔 **UX Issues**: Works but confusing output/interface

## File Structure
```
cli-testing/
├── README.md                     # This file
├── 00_setup_and_installation.md  # Environment setup & emuses installation
├── 01_command_discovery.md       # Documentation vs implementation mapping
├── 02_basic_functionality_tests.md # Core command testing (start here!)
├── 03_integration_tests.md       # Command workflows & pipelines  
├── 04_error_handling_tests.md    # Edge cases & error conditions
├── 05_performance_tests.md       # Resource usage & slow commands
├── 06_output_validation.md       # File/data output verification
└── test_data/                    # Sample inputs (external paths for now)
    └── expected_outputs/         # Reference outputs for comparison
```

## Testing Guidelines
- Always use absolute paths and external directories for test outputs
- Document exact commands run and their outputs
- Include confidence levels for error diagnoses  
- Clean up between tests when needed
- Note any environment-specific issues (OS, hardware, etc.)

## Battle-Tested Base Command
The following command trains a complete model and can be used to test most core features:

```bash
python -m emuses.cli full \
    "/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/model_registry_final_one_target" \
    "/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv" \
    --columns_are_features \
    --input_header 0 \
    --input_index_column 0 \
    --input_normalization robust \
    --scores "/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv" \
    --scores_header 0 \
    --interactive_plot \
    --umap_trials 1 \
    --hdbscan_trials 1 \
    --optim_dict optim_dict_hcp \
    --hdbscan_jobs 16 \
    --prediction_optim_dict quick_train_dict \
    --optuna_trials 10 \
    --n_jobs 16 \
    2>&1 | tee /tmp/emuses_test_full_pipeline.txt
```

This creates a trained model that can then be used to test registry, inference, and other dependent commands.
