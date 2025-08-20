# Model Registry Redesign - Phase 1: Foundation & Atomic Operations

## Phase Overview

**Goal**: Establish complete EMUSES model detection and atomic transaction framework  
**Duration**: 1 week  
**Focus**: Core model concept definition and registry data integrity  
**Dependencies**: ✅ Sub-Plan 0A ModelIOManager methods completed

## Progress Tracking Protocol
**CRITICAL**: After completing any task:
1. Mark checkbox [x] in this plan immediately
2. Update TodoWrite status to "completed"
3. Run tests: `python scripts/dev_test_runner.py`
4. Update context_2_deduplication.md with deliverables

## Phase 1 Tasks

### Task 0A-Ext.1: Complete Model Detection & Validation ⚠️ **CORE CONCEPT**
**Test Path**: `tests/model_registry/test_complete_model_detection.py`  
**Complexity**: L (Large - Core concept definition)

- [ ] 0A-Ext.1.a: Enhance `ModelIOManager.validate_model()` to detect complete EMUSES models with diverse real pipeline outputs
- [ ] 0A-Ext.1.b: Add complete model component discovery (UMAP + HDBSCAN + prediction ensembles)
- [ ] 0A-Ext.1.c: Implement configuration hash extraction from EMUSES pipeline metadata
- [ ] 0A-Ext.1.d: Add content hash calculation for complete model fingerprinting
- [ ] 0A-Ext.1.e: Create comprehensive validation for complete model structure integrity

### Task 0A-Ext.2: Enhanced Registry Schema with Atomic Operations ⚠️ **ATOMIC SAFETY**
**Test Path**: `tests/model_registry/test_enhanced_schema.py`  
**Complexity**: M (Medium - Data structure enhancement)

- [ ] 0A-Ext.2.a: Implement atomic transaction framework for multi-step registry operations
- [ ] 0A-Ext.2.b: Extend LocalModelRegistry to support complete model entries with rollback capability
- [ ] 0A-Ext.2.c: Add backward compatibility layer for existing individual component models
- [ ] 0A-Ext.2.d: Implement enhanced metadata storage with component tracking and hashes
- [ ] 0A-Ext.2.e: Add configuration and content hash indexing for efficient duplicate detection

## Phase 1 Deliverables

### Primary Outputs
1. **Complete Model Detection API**: Enhanced ModelIOManager with complete model validation
2. **Atomic Transaction Framework**: Registry operations with rollback capability
3. **Enhanced Registry Schema**: Support for both complete and individual models
4. **Hash-based Indexing**: Configuration and content hashes for efficient lookups

### Implementation Notes (From Sub-Plan 0A Experience)
**Critical Success Patterns**:
- Always provide `base_path` parameter when creating ModelIOManager instances
- Use conditional imports for optional dependencies (fastapi_users pattern)
- Generate manifests in consistent format that validate_model() expects
- Test with real EMUSES pipeline outputs across versions (2.0.x, 2.1.x)
- Use tmp_path fixtures for all file operations to ensure test isolation

### Integration Contracts for Phase 2
```python
# Complete model detection interface
class ModelIOManager:
    def validate_model(self, model_path: Path) -> CompleteModelValidation:
        """Enhanced validation returning complete model structure info"""
        
# Atomic operations interface  
class LocalModelRegistry:
    def begin_transaction(self) -> RegistryTransaction:
        """Start atomic operation with rollback capability"""
        
    def install_complete_model(self, model_data: CompleteModelData, transaction: RegistryTransaction) -> str:
        """Install complete model within atomic transaction"""
```

### Context Updates Required
**On Phase 1 completion, update `context_2_deduplication.md` with**:
- Complete model detection capabilities and supported formats
- Atomic transaction API for deduplication operations
- Enhanced registry schema supporting complete models
- Hash indexing system for efficient duplicate detection

## Testing Strategy

### Complete Model Detection (Unit + Integration)
- **Approach**: Test with diverse real EMUSES pipeline outputs
- **Focus**: Component discovery accuracy, hash calculation correctness
- **Coverage Target**: 95% - critical for correct identification

### Atomic Operations (Integration)  
- **Approach**: Real registry operations with transaction testing
- **Focus**: Data integrity, rollback correctness, concurrent safety
- **Coverage Target**: 95% - critical for data safety

## Quality Gates

**Phase 1 Success Criteria**:
- ✅ Complete model detection working with real EMUSES pipeline outputs
- ✅ Atomic transaction framework preventing data corruption
- ✅ Enhanced registry schema supporting both model types
- ✅ Hash indexing enabling efficient duplicate detection
- ✅ Backward compatibility maintained for existing workflows

**Ready for Phase 2 when**:
- All tasks completed and tested with `python scripts/dev_test_runner.py`
- Integration contracts implemented and validated with real data
- Context files updated with actual (not planned) deliverables
- Performance benchmarks established showing <5% regression
- Hash calculations consistent across environments
- Atomic operations tested under failure conditions

### Critical Implementation Resources
- `SESSION_HANDOVER.md`: Comprehensive handover documentation
- `IMPLEMENTATION_PATTERNS.md`: Proven codebase patterns and conventions
- `TROUBLESHOOTING_GUIDE.md`: Common issues and solutions from Sub-Plan 0A