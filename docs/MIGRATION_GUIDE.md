# 🔄 EMUSES Migration Guide

**Upgrade guidance for EMUSES version transitions**

This guide helps you migrate between EMUSES versions, ensuring smooth transitions while preserving your research data and models.

## 📋 Overview

### Current Version: 0.9.0 (Model Registry Complete)
### Next Version: 1.0.0 (Production Ready)

This migration guide covers:
- **Version 0.8.x → 0.9.0**: Model Registry integration
- **Version 0.9.x → 1.0.0**: Production readiness (upcoming)

## 🚀 0.8.x → 0.9.0 Migration

### What's New in 0.9.0
- **🏗️ Model Registry**: Complete model sharing and collaboration system
- **🤝 Multi-Mode Support**: Local, Database, and Cloud deployment modes
- **📊 Enhanced Storage Management**: Improved model organization and cleanup
- **🔍 Health Monitoring**: Comprehensive system health checks
- **🛡️ Improved Security**: Enhanced user isolation and validation

### Breaking Changes

#### 1. Configuration Structure Changes
**Old (0.8.x)**:
```bash
# Direct pipeline execution
python -m emuses.cli full output_folder input_data.csv --scores scores.csv
```

**New (0.9.0)**:
```bash
# Enhanced with model registry integration
python -m emuses.cli full output_folder input_data.csv --scores scores.csv
# Models are automatically registered after successful runs
```

#### 2. API Endpoints Updates
**Old (0.8.x)**:
```python
# Basic pipeline execution only
POST /api/pipeline/run
```

**New (0.9.0)**:
```python
# Enhanced endpoints with model registry
POST /api/v1/jobs/pipeline/full  # Pipeline execution
GET /api/v1/models               # Model registry access
GET /api/v1/workspaces          # Collaborative features
```

### Migration Steps

#### Step 1: Backup Your Data
```bash
# Create backup of existing work
mkdir -p ~/emuses_backup_$(date +%Y%m%d)
cp -r ~/.local/share/emuses ~/emuses_backup_$(date +%Y%m%d)/
cp -r your_analysis_results ~/emuses_backup_$(date +%Y%m%d)/
```

#### Step 2: Update EMUSES
```bash
# Uninstall old version
pip uninstall emuses

# Install new version
pip install git+https://github.com/chrisfoulon/emuses.git@v0.9.0
```

#### Step 3: Verify Installation
```bash
# Check version
python -m emuses.cli --version
# Should show: 0.9.0

# Test basic functionality
python -m emuses.cli models status
# Should show model registry status
```

#### Step 4: Migrate Existing Models (if applicable)
```bash
# Import your existing trained models into the registry
python -m emuses.cli models import your_model_directory/
```

### Compatibility Notes

#### ✅ Fully Compatible
- **Analysis Results**: All 0.8.x analysis outputs work in 0.9.0
- **Data Formats**: No changes to input CSV formats
- **Core Algorithms**: UMAP, heatmap, and prediction algorithms unchanged
- **CLI Commands**: Basic commands remain the same

#### ⚠️ Requires Attention
- **Custom Scripts**: Update API calls to use new endpoints
- **Configuration Files**: Some advanced config options have new names
- **Storage Locations**: Models now organized by registry (automatic migration)

## 🔮 0.9.x → 1.0.0 Migration (Upcoming)

### Planned Changes in 1.0.0
- **🔒 Enhanced Security**: Production-grade authentication
- **📈 Performance Optimizations**: Faster processing for large datasets
- **🌐 Full Cloud Integration**: Complete cloud deployment support
- **🧪 Extended Testing**: Comprehensive validation framework

### What to Expect
1. **Smoother Migration**: Lessons learned from 0.9.0 migration
2. **Automated Tools**: Migration scripts for complex transitions
3. **Backward Compatibility**: Strong compatibility with 0.9.x
4. **Production Features**: Enterprise-ready deployment options

## 🔧 Common Migration Issues

### Issue: Import Errors After Upgrade
**Problem**: `ModuleNotFoundError` for EMUSES modules

**Solution**:
```bash
# Clear Python cache
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -name "*.pyc" -delete

# Reinstall in clean environment
pip install --force-reinstall git+https://github.com/chrisfoulon/emuses.git
```

### Issue: Configuration Not Found
**Problem**: EMUSES can't find previous configuration

**Solution**:
```bash
# Check configuration location
python -m emuses.cli config show

# Reset to defaults if needed
python -m emuses.cli config reset
```

### Issue: Models Missing After Migration
**Problem**: Previously trained models not visible

**Solution**:
```bash
# Check model registry status
python -m emuses.cli models status

# Re-register models from backup
python -m emuses.cli models import ~/emuses_backup_*/analysis_results/
```

## 📊 Version Comparison Matrix

| Feature | 0.8.x | 0.9.0 | 1.0.0 (Planned) |
|---------|--------|--------|-----------------|
| Core Pipeline | ✅ | ✅ | ✅ |
| Model Registry | ❌ | ✅ | ✅ |
| Multi-User Support | ❌ | ✅ | ✅ |
| Cloud Deployment | ⚠️ | ✅ | ✅ |
| Health Monitoring | ❌ | ✅ | ✅ |
| Production Security | ❌ | ⚠️ | ✅ |
| Performance Optimization | ⚠️ | ✅ | ✅+ |

**Legend**: ✅ Full Support | ⚠️ Partial Support | ❌ Not Available

## 🆘 Getting Help

### Before Migration
1. **Read Release Notes**: Check GitHub releases for detailed changes
2. **Test in Isolation**: Try new version in separate environment first
3. **Backup Everything**: Always backup data and models before upgrading

### During Migration
1. **Follow Steps Sequentially**: Don't skip migration steps
2. **Check Each Step**: Verify each step before proceeding
3. **Document Issues**: Note any problems for support requests

### After Migration
1. **Test Core Workflows**: Verify your typical analysis patterns work
2. **Update Documentation**: Update any custom documentation or scripts
3. **Train Your Team**: Share migration experience with collaborators

### Support Channels
- **📖 Documentation**: [Model Registry Guide](model-registry/user_guide.md)
- **🐛 Issues**: [GitHub Issues](https://github.com/chrisfoulon/emuses/issues)
- **💬 Discussions**: [GitHub Discussions](https://github.com/chrisfoulon/emuses/discussions)
- **📧 Contact**: For enterprise migration support

## 🎯 Best Practices

### General Migration Guidelines
1. **Plan Ahead**: Schedule migration during low-activity periods
2. **Test Thoroughly**: Run comprehensive tests after migration
3. **Communicate**: Inform team members about planned upgrades
4. **Document Changes**: Keep record of configuration changes

### Research Continuity
1. **Version Pin**: Pin EMUSES version in research projects until completion
2. **Environment Isolation**: Use separate environments for different projects
3. **Result Validation**: Re-run critical analyses to ensure consistency
4. **Archive Versions**: Keep old versions available for reproducibility

---

**💡 Pro Tip**: For large research teams, consider staging migrations: test with one user first, then gradually roll out to the team.

**🔄 Updated**: This guide will be updated with each EMUSES release to provide the latest migration guidance.