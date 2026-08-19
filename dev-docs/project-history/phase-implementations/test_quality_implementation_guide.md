# EMUSES Test Quality Framework - Implementation Guide
*Practical procedures and quality gates for systematic test enhancement*

## Quick Start Checklist

### Framework Readiness Verification
- [ ] Read `TEST_QUALITY_FRAMEWORK.md` for methodology overview
- [ ] Verify `/test_data/` directory contains real data files
- [ ] Confirm `python scripts/dev_test_runner.py` operational
- [ ] Check git working directory is clean or properly documented

### Implementation Session Setup
- [ ] Create TodoWrite tracking for current enhancement session
- [ ] Identify enhancement target (coverage gaps, PDCA expansion, etc.)
- [ ] Create LAD baseline: `git add -A && git commit -m "baseline: [description]"`
- [ ] Document session objectives and success criteria

## Quality Gates Reference

### Pre-Implementation Gates

#### Development Test Validation Gate
```bash
# REQUIRED: Must pass before starting enhancements
python scripts/dev_test_runner.py

# Expected: 13/13 tests passing
# If failing: Address failures before proceeding with enhancements
```

#### Git State Validation Gate
```bash
# Check working directory status
git status

# Create baseline if needed
git add -A && git commit -m "baseline: pre-change checkpoint for [specific_description]"

# Document baseline commit
git rev-parse HEAD > .current_baseline
```

#### Data Availability Gate
```bash
# Verify real test data available for conversions
ls -la test_data/
# Required files:
# - features.csv (50×8 shape)
# - regression_scores_multitarget.csv (50×2 shape)
```

### During-Implementation Gates

#### Individual Change Validation Gate
```bash
# After each significant change
pytest [affected_test_files] -v --tb=short

# Expected: 100% pass rate maintained
# If failing: Debug and fix before continuing
```

#### Pattern Adherence Gate
- [ ] Real data conversion follows established setup_class pattern
- [ ] PDCA cycle documentation includes Plan/Do/Check/Act phases
- [ ] TodoWrite updates reflect actual progress
- [ ] Risk assessment completed for medium/high-risk changes

#### Progress Tracking Gate
- [ ] TodoWrite status reflects current state
- [ ] Implementation decisions documented
- [ ] Any deviations from standard patterns explained
- [ ] Success criteria progress measurable

### Post-Implementation Gates

#### Regression Prevention Gate
```bash
# REQUIRED: After completing enhancements
python scripts/dev_test_runner.py

# Expected: 13/13 tests still passing
# If degraded: Investigate and fix regressions immediately
```

#### Comprehensive Validation Gate
```bash
# For significant changes affecting multiple components
pytest -q --tb=short

# Expected: No increase in failure rates
# Document any expected changes in test outcomes
```

#### Documentation Completion Gate
- [ ] Enhancement results documented (cycle results, pattern usage)
- [ ] TodoWrite items marked completed
- [ ] Handover documentation updated if session ending
- [ ] Framework patterns validated or refined based on experience

## Maintenance Protocols

### Daily Maintenance (During Active Enhancement)

#### Morning Session Startup
1. **Context Review**: Read current TodoWrite status and handover docs
2. **System Validation**: Run `python scripts/dev_test_runner.py`
3. **Working State**: Verify git status and restore context if needed
4. **Target Confirmation**: Verify enhancement objectives still valid

#### End-of-Session Protocol
1. **Progress Documentation**: Update TodoWrite with completed items
2. **State Documentation**: Document any WIP or decisions made
3. **Quality Validation**: Ensure all quality gates passed
4. **Handover Preparation**: Update handover docs if session concluding

### Weekly Maintenance (Framework Health)

#### Framework Effectiveness Review
```bash
# Check framework usage patterns
git log --oneline --since="1 week ago" | grep -E "(baseline|PDCA|real data)"

# Review recent test success rates
python scripts/dev_test_runner.py
```

#### Pattern Validation Review
1. **Success Rate Analysis**: Review PDCA cycle outcomes over past week
2. **Pattern Effectiveness**: Identify which patterns worked best
3. **Framework Updates**: Document any needed procedure refinements
4. **Quality Metrics**: Track improvement trends

### Monthly Maintenance (Strategic Assessment)

#### Framework Evolution Assessment
1. **Comprehensive Metrics Review**:
   ```bash
   # Generate comprehensive coverage report
   python scripts/coverage/comprehensive_coverage_analysis.py --workers 8
   
   # Review test health trends
   pytest --collect-only | grep -c "test_"
   ```

2. **Pattern Library Updates**:
   - Document new successful patterns discovered
   - Refine existing patterns based on practical experience
   - Identify gaps in current pattern coverage

3. **Framework Documentation Updates**:
   - Update `TEST_QUALITY_FRAMEWORK.md` with validated improvements
   - Enhance `FRAMEWORK_IMPLEMENTATION_GUIDE.md` with new procedures
   - Document lessons learned and anti-patterns to avoid

## Standard Operating Procedures

### SOP 1: PDCA Cycle Implementation

#### Pre-Cycle Preparation
```bash
# 1. Create TodoWrite tracking
# TodoWrite: "PDCA Cycle [N]: [Description]" - in_progress

# 2. Risk assessment
# Low Risk: Simple test conversions, assertion updates
# Medium Risk: API changes, multi-component modifications  
# High Risk: Core functionality changes, architectural modifications

# 3. Create LAD baseline
git add -A && git commit -m "baseline: pre-change checkpoint for [specific_description]"
```

#### Cycle Execution
1. **PLAN**: Document target, approach, success criteria, risk level
2. **DO**: Apply changes following validated patterns, track progress
3. **CHECK**: Validate changes meet success criteria, no regressions
4. **ACT**: Document results, update TodoWrite, plan next steps

#### Post-Cycle Validation
```bash
# Individual validation
pytest [affected_tests] -v --tb=short

# Regression prevention
python scripts/dev_test_runner.py

# Results documentation — write under dev-docs/, never the repo root.
# This line previously wrote to the root; following it produced 19 stray .md files
# that were deleted on 2026-08-19.
echo "PDCA Cycle [N] Results:" >> dev-docs/issues/pdca_cycle_[N]_results.md
```

### SOP 2: Real Data Conversion Implementation

#### Conversion Target Assessment
1. **Value Assessment**: Integration tests > unit tests > edge case tests
2. **Complexity Assessment**: Simple data replacement > complex setup changes
3. **Risk Assessment**: Low risk if maintaining existing test logic

#### Standard Conversion Pattern
```python
# Replace this pattern:
# data = np.random.rand(50, 8)
# targets = np.random.rand(50, 2)

# With this pattern:
@classmethod
def setup_class(cls):
    """Load real test data for validation."""
    project_root = Path(__file__).parent.parent.parent
    cls.features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
    cls.targets = pd.read_csv(project_root / 'test_data/regression_scores_multitarget.csv', header=None).values
    cls.train_coords = cls.features[:30, :2]  # First 2 features as coordinates
    cls.test_coords = cls.features[30:, :2]   # Last 20 samples for testing
    cls.train_targets = cls.targets[:30]       # Training targets
    cls.test_targets = cls.targets[30:]        # Test targets
```

#### Conversion Validation
- [ ] 100% pass rate maintained after conversion
- [ ] Test logic unchanged (only data source modified)
- [ ] Data shapes compatible with existing assertions
- [ ] No functional behavior changes introduced

### SOP 3: Coverage-Driven Enhancement

#### Coverage Analysis Procedure
```bash
# 1. Generate baseline coverage
pytest --cov=emuses --cov-report=term-missing tests/ -q | tail -n 20 > coverage_baseline.txt

# 2. Identify strategic gaps
# P1-Critical: InferenceStage (0% coverage)
# P2-High: Integration points, core pipelines
# P3-Medium: Validation and performance areas
# P4-Low: Edge cases and utilities

# 3. Plan targeted improvements
# Create new tests for uncovered critical functionality
# Apply real data conversion to enhance existing test realism
```

#### Strategic Test Creation
1. **Target Selection**: Focus on P1-Critical gaps first
2. **Test Design**: Use real data when testing integration points
3. **Pattern Application**: Follow established testing patterns in codebase
4. **Validation**: Ensure new tests contribute meaningfully to coverage

## Emergency Procedures

### Emergency Rollback Procedure
```bash
# If changes cause significant test failures or system instability

# 1. Immediate rollback to last known good state
git reset --hard [baseline_commit_hash]

# 2. Verify system restored
python scripts/dev_test_runner.py

# 3. Document rollback reason
echo "ROLLBACK: $(date) - [reason]" >> .rollback_log

# 4. Analyze failure and plan corrective approach
```

### Framework Malfunction Recovery
1. **Symptom Identification**: Framework procedures not working as expected
2. **Root Cause Analysis**: Review recent framework changes or external factors
3. **Corrective Action**: Implement fixes to framework procedures
4. **Validation**: Test corrective measures with low-risk scenarios
5. **Documentation**: Update framework docs to prevent recurrence

## Success Metrics and Monitoring

### Quantitative Success Indicators
- **Development Test Stability**: 13/13 tests consistently passing
- **Conversion Success Rate**: >95% successful real data conversions
- **PDCA Cycle Success**: >90% cycles meeting stated objectives
- **Regression Rate**: <5% introduction of new test failures

### Qualitative Success Indicators
- **Framework Adoption**: Regular use of documented procedures
- **Pattern Consistency**: Consistent application of validated patterns
- **Documentation Quality**: Clear, actionable, and current procedures
- **Session Continuity**: Effective handover between work sessions

### Monitoring Procedures
```bash
# Weekly framework health check
echo "Framework Health Check - $(date)" > framework_health.log

# Test stability monitoring
python scripts/dev_test_runner.py >> framework_health.log

# Pattern usage analysis
git log --oneline --since="1 week ago" | grep -E "(baseline|PDCA|real data)" >> framework_health.log

# Success rate calculation
# [Manual review of recent PDCA outcomes and conversions]
```

## Integration with EMUSES Development

### Compatibility with Existing Workflows
- **Git Branching**: Framework works with feature branches and main branch
- **Testing Infrastructure**: Leverages existing `scripts/dev_test_runner.py`
- **Data Management**: Uses established `/test_data/` directory structure
- **Documentation**: Integrates with `.lad/` documentation organization

### Claude Code Session Integration
- **TodoWrite**: Framework procedures include todo tracking for continuity
- **Context Optimization**: Structured handover enables fresh session resumption
- **Pattern Documentation**: Reusable procedures for consistent Claude application
- **Risk Management**: Safe experimentation compatible with Claude's capabilities

### Future Enhancement Integration
- **Scalability**: Framework procedures scale to larger codebases
- **Methodology Evolution**: Framework designed for continuous improvement
- **Tool Integration**: Compatible with additional testing and analysis tools
- **Community Adoption**: Procedures suitable for team or community use

---

**Implementation Status**: Ready for immediate use ✅
**Validation**: Based on comprehensive LAD Phase 04 practical experience
**Integration**: Seamlessly compatible with EMUSES development workflow

*Created: 2025-09-01 | Companion to TEST_QUALITY_FRAMEWORK.md*
*Ready for: Coverage-Driven Enhancement → PDCA Expansion → Advanced Integration*