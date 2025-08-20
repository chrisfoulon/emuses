# Model Registry Redesign - Phase 2: Deduplication & Installation

## Phase Overview

**Goal**: Implement intelligent deduplication system and enhanced installation workflow  
**Duration**: 1 week  
**Focus**: Duplicate detection algorithms and complete model installation UX  
**Dependencies**: ✅ Phase 1 foundation (complete model detection + atomic operations)

## Progress Tracking Protocol
**CRITICAL**: After completing any task:
1. Mark checkbox [x] in this plan immediately
2. Update TodoWrite status to "completed"
3. Run tests: `python scripts/dev_test_runner.py`
4. Update context_3_interface.md with deliverables

## Phase 2 Tasks

### Task 0A-Ext.3: Intelligent Deduplication System with Performance Testing 🔧 **DEDUPLICATION CORE**
**Test Path**: `tests/model_registry/test_deduplication.py`  
**Complexity**: L (Large - Core algorithm implementation)

- [ ] 0A-Ext.3.a: Implement configuration-based duplicate detection using config hashes
- [ ] 0A-Ext.3.b: Add content-based similarity detection using component hashes
- [ ] 0A-Ext.3.c: Create performance fingerprint comparison for model similarity assessment
- [ ] 0A-Ext.3.d: Implement duplicate resolution workflow with user decision points
- [ ] 0A-Ext.3.e: Add force duplicate installation option with appropriate warnings
- [ ] 0A-Ext.3.f: Implement performance benchmarking framework for deduplication operations

### Task 0A-Ext.4: Enhanced Installation Workflow with Concurrent Safety ⚠️ **USER EXPERIENCE**
**Test Path**: `tests/model_registry/test_enhanced_installation.py`  
**Complexity**: M (Medium - Installation workflow enhancement)

- [ ] 0A-Ext.4.a: Update `LocalModelRegistry.install_model()` with complete model support and atomic operations
- [ ] 0A-Ext.4.b: Implement interactive duplicate resolution for CLI users
- [ ] 0A-Ext.4.c: Add batch mode duplicate handling for API/programmatic usage
- [ ] 0A-Ext.4.d: Create semantic model ID generation with meaningful version detection
- [ ] 0A-Ext.4.e: Implement storage optimization with shared component storage where appropriate
- [ ] 0A-Ext.4.f: Add concurrent access testing and mutex/locking for registry operations

## Phase 2 Deliverables

### Primary Outputs
1. **Intelligent Deduplication Engine**: Configuration and content-based duplicate detection
2. **Performance Benchmarking Framework**: Continuous regression testing for operations
3. **Enhanced Installation Workflow**: Complete model installation with user interaction
4. **Concurrent Safety Framework**: Mutex/locking for multi-user registry operations

### Integration Contracts for Phase 3
```python
# Deduplication service interface
class DeduplicationEngine:
    def detect_duplicates(self, model_data: CompleteModelData) -> List[DuplicateMatch]:
        """Find potential duplicates with similarity scores"""
        
    def resolve_duplicates(self, matches: List[DuplicateMatch], resolution: DuplicateResolution) -> InstallationDecision:
        """Handle user duplicate resolution decisions"""

# Enhanced installation interface
class LocalModelRegistry:
    def install_complete_model_with_dedup(self, model_path: Path, options: InstallationOptions) -> InstallationResult:
        """Install complete model with intelligent duplicate handling"""
```

### Context Updates Required
**On Phase 2 completion, update `context_3_interface.md` with**:
- Deduplication engine capabilities and configuration options
- Installation workflow patterns and user interaction points
- Performance benchmarking results and optimization strategies
- Concurrent safety implementation and locking mechanisms

## Integration with Phase 1
**Uses from Foundation Phase**:
- Complete model detection API for analyzing candidate models
- Atomic transaction framework for safe installation operations
- Hash indexing system for efficient duplicate candidate identification
- Enhanced registry schema for storing deduplication metadata

## Testing Strategy

### Deduplication Logic (Unit Testing)
- **Approach**: Isolated testing with controlled model fixtures and hash scenarios
- **Focus**: Duplicate detection accuracy, false positive/negative rates, performance regression
- **Coverage Target**: 95% - critical for preventing storage waste

### Installation Workflow (Integration Testing)
- **Approach**: Real installation operations with user interaction simulation
- **Focus**: User experience, atomic operations, concurrent safety
- **Coverage Target**: 90% - essential for reliable operations

## Quality Gates

**Phase 2 Success Criteria**:
- ✅ Intelligent duplicate detection with <5% false positive rate
- ✅ Interactive duplicate resolution providing clear user choices
- ✅ Complete model installation workflow reliable and atomic
- ✅ Performance benchmarking showing <20% impact on operations
- ✅ Concurrent access safety with mutex/locking implementation

**Ready for Phase 3 when**:
- All deduplication algorithms tested with diverse model scenarios
- Installation workflow handles all user interaction patterns
- Performance benchmarks meet regression testing requirements
- Context files updated with working examples and patterns