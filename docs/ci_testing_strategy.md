# EMUSES CI/CD Testing Strategy

## 🎯 **Resource-Efficient Development CI**

EMUSES now uses a **smart, credit-saving CI strategy** designed for your GitHub Education account:

### **Development Pushes (Lightweight)**
- **File**: `.github/workflows/emuses_tests.yml`
- **Triggers**: All branches except `main`
- **Duration**: < 1 minute
- **Cost**: Minimal credits (~2-3 minutes per push)
- **Tests**: 
  - ✅ **13 parallelism utility tests** (core functionality)
  - ✅ **Syntax validation** (catches import errors)

### **Production Pushes (Comprehensive)**  
- **File**: `.github/workflows/production_tests.yml`
- **Triggers**: Only `main` branch + manual dispatch
- **Duration**: Up to 30 minutes
- **Cost**: Full credits (only when ready for production)
- **Tests**: 
  - ✅ **Full test suite** with PostgreSQL + Redis
  - ✅ **Security, integration, deployment tests**
  - ✅ **Coverage reporting**

## 🛠️ **Local Development Workflow**

### **Before Pushing - Save CI Credits**
```bash
# Run the same tests that CI will run (< 1 minute locally)
python scripts/dev_test_runner.py
```

### **Development Branch Strategy**
```bash
# Work on feature branches - triggers lightweight CI only
git checkout -b feature/my-feature
git push origin feature/my-feature  # ✅ Fast, cheap CI

# When ready for production
git checkout main
git merge feature/my-feature
git push origin main  # ✅ Full CI with all services
```

### **Manual Production Testing**
```bash
# Trigger comprehensive tests manually when needed
# Go to GitHub Actions → "Production CI" → "Run workflow"
```

## 📊 **Credit Usage Estimates**

| Scenario | Duration | Credits Used | When to Use |
|----------|----------|--------------|-------------|
| Development push | ~1 min | ~2-3 credits | Every push while developing |
| Production push | ~15-30 min | ~30-60 credits | Only when ready for production |
| Manual test run | ~10-20 min | ~20-40 credits | Before important merges |

## 🎛️ **Manual Test Categories**

You can run specific test categories manually to save credits:

- **`core`**: Model registry + essential tools (~5 min)
- **`security`**: Security audit tests (~8 min) 
- **`integration`**: Cross-system tests (~12 min)
- **`full`**: Complete test suite + coverage (~30 min)

## 🚀 **Best Practices**

1. **Develop on feature branches** - gets fast feedback
2. **Test locally first** - use `python scripts/dev_test_runner.py`
3. **Merge to main only when ready** - triggers full validation
4. **Use manual dispatch** for pre-merge validation when needed

This strategy gives you **fast development feedback** while **preserving GitHub credits** for when you really need comprehensive testing!
