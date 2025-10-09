# EMUSES Model Registry - Testing Checklist
## Comprehensive Feature Testing Guide

Based on the completed model-registry-redesign implementation, this checklist covers all implemented features for thorough testing.

## PREREQUISITES FOR TESTING

### 1. Environment Setup
- [ ] EMUSES installation available
- [ ] Access to real EMUSES training output folders
- [ ] Python environment with required dependencies

### 2. Test Data Requirements
- [ ] Complete EMUSES model folder (with manifest, UMAP, HDBSCAN, prediction components)
- [ ] Incomplete model folder (for validation testing)
- [ ] Sample input data for inference testing
- [ ] Multiple model folders for batch testing

## CORE REGISTRY FUNCTIONALITY

### Registry Installation & Setup
- [ ] Test default registry creation (~/.emuses/)
- [ ] Test custom registry path with --registry option
- [ ] Test registry initialization from scratch
- [ ] Verify registry directory structure creation

### Model Installation (install command)
```bash
# Basic installation
python -m emuses.cli models install /path/to/model

# Custom name installation  
python -m emuses.cli models install /path/to/model --name custom-model

# Custom registry location
python -m emuses.cli models install /path/to/model --registry /custom/path
```

**Test Cases:**
- [ ] Install valid complete EMUSES folder
- [ ] Attempt to install incomplete folder (should fail)
- [ ] Install with custom name
- [ ] Install duplicate model (deduplication)
- [ ] Install with custom registry path
- [ ] Test installation error messages for invalid folders

### Model Listing (list command)
```bash
# Basic listing
python -m emuses.cli models list

# Filtered listing
python -m emuses.cli models list --type emuses_model
python -m emuses.cli models list --tag neuroimaging
```

**Test Cases:**
- [ ] List models in empty registry
- [ ] List models after installing several
- [ ] Test type filtering
- [ ] Test tag filtering
- [ ] Verify table format and columns
- [ ] Test with custom registry path

### Model Information (info command)
```bash
python -m emuses.cli models info MODEL_ID
```

**Test Cases:**
- [ ] Get info for valid model ID
- [ ] Get info for invalid model ID (should error)
- [ ] Verify complete model information display
- [ ] Check manifest details display
- [ ] Verify component information (UMAP, HDBSCAN, prediction)
- [ ] Check feature model information (PCA, kPCA, autoencoder)
- [ ] Test with custom registry path

### Model Removal (remove command)
```bash
# Remove model completely
python -m emuses.cli models remove MODEL_ID

# Keep files on disk
python -m emuses.cli models remove MODEL_ID --keep-files
```

**Test Cases:**
- [ ] Remove model with confirmation
- [ ] Cancel removal when prompted
- [ ] Remove with --keep-files option
- [ ] Attempt to remove non-existent model
- [ ] Verify files deleted/preserved correctly
- [ ] Check registry index updated after removal

### Registry Status (status command)
```bash
python -m emuses.cli models status
```

**Test Cases:**
- [ ] Check status with empty registry
- [ ] Check status with multiple models
- [ ] Verify storage usage information
- [ ] Check model type statistics
- [ ] Verify newest/oldest model information

## CLI INFERENCE INTEGRATION

### Registry-Based Inference (--model-id option)
```bash
# NEW: Registry-based inference
python -m emuses.cli inference --model-id MODEL_ID --data input.csv

# Traditional file-based (should still work)
python -m emuses.cli inference --model /path/to/model --data input.csv
```

**Test Cases:**
- [ ] Run inference with valid model ID
- [ ] Test inference with invalid model ID (should error)
- [ ] Verify cannot use both --model and --model-id (mutual exclusivity)
- [ ] Test inference without model specification (should error)
- [ ] Verify registry lookup messaging (shows path resolution)
- [ ] Test inference with different output formats (csv, npy)
- [ ] Test inference with custom output path
- [ ] Verify InferenceStage integration works unchanged

### End-to-End Workflow Testing
```bash
# Complete workflow
python -m emuses.cli models install /path/to/trained/model
python -m emuses.cli models list
python -m emuses.cli models info MODEL_ID
python -m emuses.cli inference --model-id MODEL_ID --data test_data.csv
```

**Test Cases:**
- [ ] Complete install -> list -> info -> inference workflow
- [ ] Verify model ID persistence across operations
- [ ] Test workflow with multiple models
- [ ] Verify inference results are identical between --model and --model-id
- [ ] Test workflow error recovery (failed operations)

## ADVANCED FEATURES

### Feature Augmentation Models
**Test Cases:**
- [ ] Install model with PCA components (if available)
- [ ] Install model with kPCA components (if available)  
- [ ] Install model with autoencoder components (if available)
- [ ] Verify feature model info displayed in model details
- [ ] Test backward compatibility with models without feature components
- [ ] Check feature model metadata in registry

### Model Validation System
**Test Cases:**
- [ ] Test with complete valid EMUSES folder
- [ ] Test with missing UMAP component (should fail)
- [ ] Test with missing HDBSCAN component (should fail)
- [ ] Test with missing prediction components (should fail)
- [ ] Test with corrupted manifest file (should fail)
- [ ] Test with invalid folder structure (should fail)
- [ ] Verify validation error messages are clear

### Performance & Storage
**Test Cases:**
- [ ] Measure registry lookup performance (get_model_path speed)
- [ ] Test with large number of models (10+)
- [ ] Test storage warning system (if near limits)
- [ ] Test deduplication for identical models
- [ ] Test concurrent registry access (if possible)

## ERROR HANDLING & EDGE CASES

### Registry Corruption Recovery
**Test Cases:**
- [ ] Test with corrupted registry index file
- [ ] Test with missing registry directory
- [ ] Test with permission issues
- [ ] Verify graceful error messages

### Path and Name Validation
**Test Cases:**
- [ ] Test with special characters in model names
- [ ] Test with very long model names
- [ ] Test with invalid path characters
- [ ] Test with non-existent paths

### Cross-Platform Compatibility
**Test Cases:**
- [ ] Test on Windows paths
- [ ] Test on Linux paths (if available)
- [ ] Test with network paths (if applicable)
- [ ] Test with spaces in paths

## INTEGRATION TESTING

### Multi-User Features (if database mode available)
**Test Cases:**
- [ ] Test user-scoped model access
- [ ] Test workspace model sharing
- [ ] Test API endpoints (if available)
- [ ] Test model download tracking

### API Integration (if available)
**Test Cases:**
- [ ] Test REST API model listing
- [ ] Test API model information retrieval
- [ ] Test API model registration
- [ ] Test API authentication/authorization

## REGRESSION TESTING

### Existing Functionality Preservation
**Test Cases:**
- [ ] Verify original --model option still works
- [ ] Test that InferenceStage behavior unchanged
- [ ] Verify no breaking changes to other CLI commands
- [ ] Test backward compatibility with existing scripts

### Documentation Verification
**Test Cases:**
- [ ] Verify CLI help messages are accurate
- [ ] Check that examples in documentation work
- [ ] Verify error messages match documentation
- [ ] Test all documented command options

## PERFORMANCE BENCHMARKS

### Speed Testing
- [ ] Registry lookup time (target: <10ms)
- [ ] Model installation time for various sizes
- [ ] List operation performance with many models
- [ ] Inference startup time with registry vs direct path

### Resource Usage
- [ ] Registry memory usage
- [ ] Storage space efficiency
- [ ] Network usage (multi-user mode)

## COMPLETION CHECKLIST

### Core Features ✅/❌
- [ ] Registry installation and setup
- [ ] Model installation with validation
- [ ] Model listing and filtering  
- [ ] Model information display
- [ ] Model removal
- [ ] Registry status and statistics

### CLI Integration ✅/❌
- [ ] --model-id option for inference
- [ ] Mutual exclusivity with --model option
- [ ] Error handling for invalid model IDs
- [ ] End-to-end workflow testing

### Advanced Features ✅/❌
- [ ] Feature model detection and display
- [ ] Model validation system
- [ ] Performance monitoring
- [ ] Storage management

### Quality Assurance ✅/❌
- [ ] Error handling and edge cases
- [ ] Cross-platform compatibility
- [ ] Regression testing
- [ ] Performance benchmarks

## TESTING COMMANDS REFERENCE

```bash
# Basic registry operations
python -m emuses.cli models install /path/to/model
python -m emuses.cli models list
python -m emuses.cli models info MODEL_ID
python -m emuses.cli models remove MODEL_ID

# Registry-based inference
python -m emuses.cli inference --model-id MODEL_ID --data input.csv

# Custom registry location
python -m emuses.cli models --registry /custom/path install /path/to/model

# Help and documentation
python -m emuses.cli models --help
python -m emuses.cli inference --help
```
