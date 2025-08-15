# EMUSES Comprehensive Testing Instructions

## 🎯 Purpose

This guide provides instructions for **comprehensive project-wide testing** of the EMUSES neuroimaging research platform using **category-based validation** that prevents timeout issues and meta-testing anti-patterns.

## 🚀 Quick Start

### **Basic Usage**
```bash
# List available test categories
python scripts/test_runners/comprehensive_test_runner.py --list

# Run specific category (recommended for development)
python scripts/test_runners/comprehensive_test_runner.py --category security

# Run all categories (for release validation)
python scripts/test_runners/comprehensive_test_runner.py --all

# Generate detailed report
python scripts/test_runners/comprehensive_test_runner.py --all --report test_results.json
```

### **Advanced Usage**
```bash
# Verbose output for debugging
python scripts/test_runners/comprehensive_test_runner.py --category model_registry --verbose

# Parallel execution (experimental - use with caution)
python scripts/test_runners/comprehensive_test_runner.py --all --parallel

# Run multiple specific categories
python scripts/test_runners/comprehensive_test_runner.py --category security
python scripts/test_runners/comprehensive_test_runner.py --category model_registry
python scripts/test_runners/comprehensive_test_runner.py --category integration
```

## 📊 Test Categories

### **🔥 High Priority Categories**
| Category | Description | Est. Time | Timeout |
|----------|-------------|-----------|---------|
| **security** | OWASP validation, authentication, permissions | 5-10 min | 15 min |
| **model_registry** | Local/database/cloud registry functionality | 10-15 min | 20 min |
| **integration** | Cross-mode workflows, API endpoints | 15-20 min | 25 min |
| **cli** | Command-line interface functionality | 10-15 min | 20 min |
| **foundation** | FastAPI service layer | 5-10 min | 15 min |
| **multi_user** | Multi-user authentication and workspaces | 10-15 min | 20 min |
| **pipelines** | Data processing pipelines | 10-15 min | 20 min |

### **📋 Medium Priority Categories**
| Category | Description | Est. Time | Timeout |
|----------|-------------|-----------|---------|
| **deployment** | Environment validation, configuration checks | 5-10 min | 15 min |
| **performance** | Caching, query optimization, scalability | 10-15 min | 20 min |
| **tools** | Neuroimaging analysis tools and utilities | 15-20 min | 25 min |

## 🎓 Testing Strategy for Neuroimaging Research

### **Why Category-Based Testing?**
1. **🚫 Prevents Meta-Testing Anti-Patterns**: No more `subprocess.run(["pytest"])` within tests
2. **⏰ Timeout Management**: Each category has appropriate timeout limits
3. **🔄 Resource Management**: Prevents zombie process creation
4. **🎯 Targeted Debugging**: Focus on specific component failures
5. **⚡ Parallel Capability**: Run multiple categories simultaneously

### **Scientific Focus Areas**
- **Brain Analysis Algorithms**: UMAP, clustering, prediction models
- **Multi-Modal Data**: fMRI, structural MRI, DTI processing
- **Research Workflows**: Model training, validation, sharing
- **Deployment Flexibility**: Local research → Lab collaboration → Public sharing

## 🔍 Interpreting Results

### **Success Indicators**
- ✅ **Category Status**: All high-priority categories should pass
- 📈 **Success Rate**: Target >95% for core categories
- ⏱️ **Performance**: Categories complete within estimated time
- 🧪 **Test Coverage**: Individual tests provide meaningful validation

### **Failure Response**
```bash
# If a category fails, run it individually with verbose output
python scripts/test_runners/comprehensive_test_runner.py --category security --verbose

# Check specific test files in the category
pytest tests/security/test_auth.py -v

# For timeout issues, check if category needs subdivision
```

### **Common Issues & Solutions**

| Issue | Symptoms | Solution |
|-------|----------|----------|
| **Timeout** | Category exceeds time limit | Run smaller subsets manually |
| **Environment** | Import/dependency errors | Check conda environment activation |
| **Database** | Connection failures | Verify PostgreSQL/Redis services |
| **Permissions** | File access errors | Check test artifact cleanup |

## 🛠️ Development Workflows

### **Feature Development**
```bash
# 1. Work on model registry feature
# 2. Run related category tests
python scripts/test_runners/comprehensive_test_runner.py --category model_registry

# 3. Run integration tests to check cross-component impact
python scripts/test_runners/comprehensive_test_runner.py --category integration

# 4. Before committing, run security tests
python scripts/test_runners/comprehensive_test_runner.py --category security
```

### **Release Preparation**
```bash
# 1. Full validation suite
python scripts/test_runners/comprehensive_test_runner.py --all --report release_validation.json

# 2. Review report for any issues
cat release_validation.json | jq '.summary'

# 3. Address any failures in high-priority categories
# 4. Re-run full suite to confirm fixes
```

### **CI/CD Integration**
```bash
# Local pre-push validation
python scripts/test_runners/comprehensive_test_runner.py --category security
python scripts/test_runners/comprehensive_test_runner.py --category model_registry

# Full CI validation (in CI pipeline)
python scripts/test_runners/comprehensive_test_runner.py --all --report ci_results.json
```

## 📋 Best Practices

### **✅ Do This**
- **Category-first approach**: Always run specific categories during development
- **Progressive validation**: Start with security, then your feature area, then integration
- **Report generation**: Use `--report` for detailed analysis and debugging
- **Verbose debugging**: Use `--verbose` when investigating failures

### **❌ Avoid This**
- **Running full suite frequently**: Use category-based testing for regular development
- **Ignoring timeouts**: Investigate timeout issues rather than just re-running
- **Meta-testing**: Never run pytest from within pytest tests
- **Skipping security**: Always run security category before major changes

### **🧠 Neuroimaging-Specific Guidelines**
- **Test with realistic data**: Use representative brain imaging datasets
- **Validate scientific accuracy**: Ensure algorithms produce scientifically valid results
- **Cross-mode compatibility**: Test local/database/cloud deployment modes
- **Performance considerations**: Monitor memory usage with large neuroimaging datasets

## 🔧 Troubleshooting

### **Environment Issues**
```bash
# Check Python environment
python --version
which python

# Verify EMUSES installation
python -c "import emuses; print(emuses.__version__)"

# Check test dependencies
pip list | grep pytest
```

### **Database Issues**
```bash
# Check database connectivity (for multi-user tests)
python -c "from emuses.multi_user_service.database import get_database_url; print(get_database_url())"

# Reset test database if needed
python scripts/dev_utils/reset_test_database.py  # If this utility exists
```

### **Performance Issues**
```bash
# Check system resources
free -h  # Memory usage
df -h    # Disk space
nproc    # CPU cores

# Adjust parallelism if needed
python scripts/test_runners/comprehensive_test_runner.py --category tools  # Instead of --parallel
```

## 📚 Integration with Other Tools

### **Coverage Analysis**
```bash
# Run tests first, then coverage
python scripts/test_runners/comprehensive_test_runner.py --category model_registry
python scripts/coverage/comprehensive_coverage_analysis.py --workers 8
```

### **LAD Framework Compliance**
- **Testing Strategy**: Follows LAD guidelines for component-aware testing
- **Documentation**: NumPy-style docstrings required
- **Code Style**: Flake8 compliance with max-complexity 10
- **Coverage Target**: 90%+ for new code, 60%+ overall

### **Model Registry Integration**
- Tests validate all registry modes (LOCAL/DATABASE/CLOUD)
- Cross-mode migration and compatibility testing
- Performance validation for large model collections
- Security testing for multi-user scenarios

## 🎯 For Claude Sessions

### **Always Read This First**
When working on EMUSES and needing project-wide validation:

1. **🎯 Use these scripts** for comprehensive testing
2. **❌ Never run** `subprocess.run(["pytest", ...])` from within test files
3. **📊 Focus on categories** relevant to your current work
4. **📖 Check results** and address failures systematically

### **Common Claude Tasks**
```bash
# Implementing new model registry feature
python scripts/test_runners/comprehensive_test_runner.py --category model_registry

# Adding security features
python scripts/test_runners/comprehensive_test_runner.py --category security

# Working on CLI commands
python scripts/test_runners/comprehensive_test_runner.py --category cli

# Before completing any major feature
python scripts/test_runners/comprehensive_test_runner.py --all
```

### **Anti-Pattern Prevention**
- ✅ **Correct**: Use these scripts for project-wide validation
- ❌ **Wrong**: Create subprocess calls within test files
- ✅ **Correct**: Test actual neuroimaging functionality
- ❌ **Wrong**: Test pytest infrastructure itself

## 🔬 Scientific Context

### **EMUSES Testing Philosophy**
EMUSES is a **neuroimaging research platform** that enables:
- **Individual researchers**: Local model development and analysis
- **Research labs**: Collaborative model sharing with workspace isolation
- **Scientific community**: Public model registry with peer review

### **Quality Standards**
- **Research-grade reliability**: 60% coverage is excellent for research software
- **Scientific reproducibility**: Consistent results across deployment modes
- **Performance standards**: Suitable for large neuroimaging datasets
- **Collaboration support**: Multi-user workflows with proper isolation

---

**Remember**: These testing tools exist to ensure the **scientific integrity** and **collaborative effectiveness** of the EMUSES neuroimaging research platform.

*For questions or issues, check the troubleshooting section or refer to the main project documentation.*