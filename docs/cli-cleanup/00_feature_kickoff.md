# CLI Legacy Cleanup Feature

## Feature Overview

**Goal**: Remove deprecated and retired CLI commands to simplify the EMUSES command-line interface and reduce maintenance burden.

## Current State

**Commands to Remove:**
- `clustering` - Legacy command, functionality integrated into other stages
- `prediction` - Retired command (warning already displays: "WARNING: PredictionStage has been retired. Use 'heatmap' command for sophisticated prediction model training.")

**Commands to Keep:**
- `full` - Complete pipeline (UMAPStage + HeatmapStage)
- `umap` - UMAP training only
- `heatmap` - Prediction training only (replaces old prediction functionality)
- `inference` - Inference on trained models (to be implemented via flexible-inference-stage)

## Implementation Requirements

### Code Cleanup
- Remove command parsers and handlers from `emuses/scripts/main.py`
- Remove unused imports and utility functions
- Update command routing logic
- Clean up help text and documentation

### Documentation Updates
- Remove references to deprecated commands from all documentation
- Update CLI help text and command listings
- Create migration guide for users using deprecated commands
- Update API documentation and examples

## Success Criteria

- ✅ Deprecated commands removed from CLI
- ✅ No breaking changes for supported commands
- ✅ Updated documentation reflects current command set
- ✅ Clear migration path for affected users
- ✅ Reduced code complexity and maintenance burden

---
*Created: 2025-08-06*
*Priority: Low (Cleanup task)*
*Estimated Duration: 1 day*