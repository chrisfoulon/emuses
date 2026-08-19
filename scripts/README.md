# EMUSES Development Scripts & Project-Wide Validation

## 🎯 Purpose

This directory contains **development utilities for project-wide validation** of the EMUSES neuroimaging research platform. These tools are designed for comprehensive testing, coverage analysis, and deployment validation **outside the test suite**.

## 📁 Directory Structure

```
scripts/
├── test_runners/           # Comprehensive test execution utilities
│   ├── comprehensive_test_runner.py
│   ├── category_test_runner.py
│   └── TESTING_INSTRUCTIONS.md
├── coverage/               # Coverage analysis tools
│   ├── comprehensive_coverage_analysis.py
│   └── COMPREHENSIVE_COVERAGE_INSTRUCTIONS.md
├── dev_utils/              # Development utilities
└── README.md               # This file
```

## 🚀 Quick Start for Project-Wide Validation

### **For Humans**
```bash
# Run comprehensive test validation by category
python scripts/test_runners/comprehensive_test_runner.py --category security
python scripts/test_runners/comprehensive_test_runner.py --category model_registry
python scripts/test_runners/comprehensive_test_runner.py --all

# Run comprehensive coverage analysis  
python scripts/coverage/comprehensive_coverage_analysis.py --workers 8
```

### **For Claude Sessions**
When working on EMUSES and needing project-wide validation:

1. **🎯 READ THIS FIRST**: Use utilities in `/scripts` for project-wide validation
2. **❌ NEVER**: Run `subprocess.run(["pytest", ...])` from within test files
3. **✅ ALWAYS**: Use scripts for comprehensive testing and coverage analysis
4. **📖 REFERENCE**: Read instructions in each subdirectory before use

## 🧪 Testing Strategy

### **Test Categories with Timeout Management**
- **Security Tests** (~5-10 minutes): OWASP validation, authentication, permissions
- **Model Registry Tests** (~10-15 minutes): Local/database/cloud registry functionality  
- **Integration Tests** (~15-20 minutes): Cross-mode workflows, API endpoints
- **Deployment Tests** (~5-10 minutes): Environment validation, configuration checks
- **Performance Tests** (~10-15 minutes): Caching, query optimization, scalability

### **Why Category-Based Testing?**
- **Timeout Prevention**: Avoid 3+ hour meta-test hangs
- **Resource Management**: Prevent zombie process creation
- **Parallel Execution**: Run categories simultaneously on multi-core systems
- **Targeted Debugging**: Focus on specific component failures

## 🔍 Coverage Analysis

### **Comprehensive Coverage (60% Target)**
- **Total Lines**: 21,438 lines of neuroimaging research code
- **Current Coverage**: 60% (excellent for research software)
- **Focus Areas**: CLI, model registry, multi-user service, pipelines

### **Performance Optimization**
- **Standard Machine** (4-8 cores): 15-30 minutes
- **High-End Workstation** (16-32 cores): 5-10 minutes  
- **Beast Machine** (72+ cores): 2-5 minutes

## ⚠️ Anti-Patterns to Avoid

### **❌ Meta-Testing (Don't Do This)**
```python
# WRONG - Running pytest from within pytest
def test_something():
    subprocess.run(["pytest", "tests/security/"])  # Creates infinite recursion
```

### **✅ Proper Testing (Do This Instead)**
```python
# RIGHT - Test actual neuroimaging functionality
def test_brain_model_analysis():
    model = UMAPModel()
    result = model.fit_transform(brain_data)
    assert result.explained_variance > 0.8
```

### **✅ Deployment Validation (Do This Instead)**
```python
# RIGHT - Test deployment configuration
def test_neuroimaging_environment():
    config = NeuroimagingConfig()
    assert config.validate_atlas_paths()
    assert config.check_gpu_availability()
```

## 🛠️ Development Workflow Integration

### **Before Major Releases**
```bash
# Full validation pipeline
python scripts/test_runners/comprehensive_test_runner.py --all
python scripts/coverage/comprehensive_coverage_analysis.py --workers $(nproc)
```

### **Feature Development**
```bash
# Category-specific validation
python scripts/test_runners/category_test_runner.py --category model_registry
```

### **CI/CD Integration**
- **Local Development**: Use scripts for complete validation
- **CI Pipeline**: Use category-based testing for resource efficiency
- **Release Pipeline**: Full comprehensive validation required

## 📋 LAD Framework Compliance

### **Testing Guidelines** (see the `lad:lad-standards` skill)
- ✅ **API Endpoints**: Integration testing (real app + mocked external deps)
- ✅ **Research Logic**: Unit testing (complete isolation + mocks)  
- ✅ **Data Processing**: Unit testing (minimal deps + test fixtures)
- ❌ **Meta-Testing**: Avoid testing test infrastructure

### **Code Style Requirements**
- **Docstrings**: NumPy-style required for all functions/classes
- **Linting**: Flake8 compliance (max-complexity 10)
- **Testing**: TDD approach, component-aware strategies
- **Coverage**: 90%+ target for new code

## 🎓 For New Team Members

### **Understanding EMUSES Testing**
1. **Neuroimaging Focus**: We test brain analysis algorithms, not generic software
2. **Research Quality**: 60% coverage is excellent for research software
3. **Multi-Mode Support**: Tests work across LOCAL/DATABASE/CLOUD deployment modes
4. **Scientific Rigor**: Reproducibility and accuracy are paramount

### **Getting Started**
1. Read `/scripts/test_runners/TESTING_INSTRUCTIONS.md`
2. Read `/scripts/coverage/COMPREHENSIVE_COVERAGE_INSTRUCTIONS.md`
3. Run category tests to understand system components
4. Use coverage analysis to identify areas needing attention

## 🔧 Maintenance & Updates

### **When to Update Scripts**
- New test categories added to the system
- Performance optimization needs  
- Timeout issues in specific test categories
- New deployment modes or configurations

### **Script Improvement Guidelines**
- Maintain backward compatibility
- Add comprehensive logging and progress reporting
- Include error recovery and graceful degradation
- Document all configuration options

## 📞 Support & Troubleshooting

### **Common Issues**
- **Timeout Issues**: Use category-based testing instead of full suite
- **Zombie Processes**: Never run pytest from within pytest tests
- **Resource Exhaustion**: Adjust worker count based on system capabilities
- **Coverage Issues**: Focus on core neuroimaging functionality

### **For Claude Sessions**
- **Always check this README first** when doing project-wide validation
- **Use existing scripts** instead of creating new subprocess calls
- **Follow LAD framework guidelines** for testing approaches
- **Maintain scientific focus** in testing strategy

---

**Remember**: These scripts exist to **prevent meta-testing anti-patterns** while providing **comprehensive project validation** for the EMUSES neuroimaging research platform.

*Last Updated: 2025-08-15*  
*Maintained by: EMUSES Development Team*