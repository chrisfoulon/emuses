# EMUSES Testing Guidelines & Best Practices Consolidation

## 🎯 **Purpose**
Comprehensive consolidation of all testing guidelines, best practices, and methodologies discovered during the test fixing initiative for systematic failure analysis.

## 📋 **Established Testing Guidelines**

### **1. Anti-Pattern Prevention** ⚠️
- **❌ NEVER**: Run `subprocess.run(["pytest", ...])` from within test files
- **❌ NEVER**: Create infinite loops in test workflows  
- **❌ NEVER**: Test the testing infrastructure itself (meta-testing)
- **✅ ALWAYS**: Test actual neuroimaging functionality
- **✅ ALWAYS**: Use `/scripts/test_runners/` for project-wide validation

### **2. API Usage Patterns** 🔧
- **Factory Patterns**: Always create instances before calling methods
  ```python
  # ✅ CORRECT
  factory = ModelRegistryFactory()
  registry = factory.create_registry()
  
  # ❌ WRONG  
  registry = ModelRegistryFactory.create_registry()
  ```

- **Configuration Management**: Use factory functions, not direct constructors
  ```python
  # ✅ CORRECT
  config = get_deployment_config()
  
  # ❌ WRONG
  config = DeploymentConfig()
  ```

- **Prometheus Metrics**: Access labeled metrics through `_metrics` dictionary
  ```python
  # ✅ CORRECT
  counter_data = {
      labels: metric._value.get() 
      for labels, metric in counter._metrics.items()
  }
  
  # ❌ WRONG
  counter_value = counter._value._value
  ```

### **3. LAD Framework Compliance** 🧪
- **Test research functionality, not test infrastructure**
- **Component-aware testing strategies**
- **NumPy docstrings and Flake8 compliance maintained**
- **90%+ coverage target preserved**
- **Focus on neuroimaging research logic**

### **4. Risk Assessment Framework** 📊
- **LOW RISK**: Test configuration issues (API usage, import patterns)
- **MEDIUM RISK**: Code logic issues (business logic bugs)
- **HIGH RISK**: Security vulnerabilities, data corruption issues
- **CRITICAL RISK**: Production-blocking functionality failures

### **5. Fix Methodology** 🔄
1. **Research Phase**: Investigate correct API usage patterns
2. **Pattern Identification**: Recognize recurring issues across test files
3. **Single Test Validation**: Fix one test to validate approach
4. **Batch Implementation**: Apply fixes systematically
5. **Comprehensive Validation**: Verify no regressions introduced

### **6. Quality Standards** ✅
- **Research Software**: 60-95% success rate is excellent
- **Production Software**: 95-99% success rate expected
- **Critical Categories**: Security, Deployment must be 100%
- **Non-blocking threshold**: <5% failure rate for non-critical features

### **7. Environment Considerations** 🌍
- **Database Dependencies**: PostgreSQL/Redis service requirements
- **Authentication Systems**: Multi-user service dependencies
- **External Services**: Cloud storage, API endpoint availability
- **Resource Constraints**: Memory, CPU, disk space limitations

### **8. Test Organization Principles** 📁
- **Category-based separation**: By functionality, not by test type
- **Timeout management**: Appropriate limits per category complexity
- **Dependency isolation**: Minimize cross-test dependencies
- **Clear naming conventions**: Descriptive test and file names

## 🔍 **Failure Analysis Framework**

### **Failure Classification System**
1. **API Usage Issues** (Low Risk)
   - Incorrect method calls
   - Missing required parameters
   - Wrong import patterns

2. **Environment/Dependency Issues** (Medium Risk)
   - Missing services (database, Redis)
   - Network connectivity problems
   - Resource limitations

3. **Business Logic Issues** (Medium Risk)
   - Incorrect test expectations
   - Algorithm implementation bugs
   - Data processing errors

4. **Integration Issues** (Medium-High Risk)
   - Cross-component communication failures
   - Configuration mismatches
   - Service coordination problems

5. **Security/Critical Issues** (High Risk)
   - Authentication failures
   - Permission boundary violations
   - Data integrity problems

### **Investigation Methodology**
1. **Error Message Analysis**: Extract root cause from traceback
2. **Pattern Recognition**: Identify similar failures across tests
3. **Environment Verification**: Check service dependencies
4. **Code Context Review**: Understand test purpose and expectations
5. **API Documentation Check**: Verify correct usage patterns

### **Fix Prioritization Matrix**
| Impact | Effort | Priority | Action |
|--------|--------|----------|---------|
| High | Low | P1 | Fix immediately |
| High | High | P2 | Plan systematic fix |
| Low | Low | P3 | Fix when convenient |
| Low | High | P4 | Document, consider deferring |

## 🧠 **Learned Patterns**

### **Common API Evolution Issues**
- **Prometheus Client**: Internal attribute access patterns change
- **Factory Patterns**: Static vs instance method evolution
- **Configuration Systems**: Constructor vs factory function changes

### **Environment-Specific Failures**
- **Database Connectivity**: Connection string, service availability
- **Authentication**: JWT tokens, session management
- **Resource Limits**: Memory constraints, timeout issues

### **Test Quality Indicators**
- **Clear Purpose**: Each test validates specific functionality
- **Minimal Dependencies**: Avoid complex setup requirements
- **Deterministic Results**: Consistent pass/fail behavior
- **Meaningful Assertions**: Test actual business value

## 📖 **Documentation Requirements**

### **For Each Failure**
1. **Error Classification**: Type, risk level, impact assessment
2. **Root Cause Analysis**: Technical details, context, dependencies
3. **Fix Strategy**: Approach, effort estimate, risk assessment
4. **Validation Plan**: How to verify fix effectiveness
5. **Prevention**: How to avoid similar issues in future

### **For Each Category**
1. **Overall Health**: Success rate, critical issues, trends
2. **Key Dependencies**: Required services, configurations
3. **Common Patterns**: Recurring failure types, solutions
4. **Recommendations**: Improvement strategies, maintenance needs

## 🎯 **Success Criteria**

### **Immediate Goals**
- **Critical Categories**: 100% success (Security, Deployment)
- **Core Categories**: >95% success (Model Registry, Integration)
- **Supporting Categories**: >80% success (CLI, Tools, etc.)

### **Quality Indicators**
- **No Regression**: Existing passing tests remain passing
- **Clear Documentation**: All failures analyzed and documented
- **Actionable Plans**: Specific steps for resolution
- **Sustainable Patterns**: Reusable methodologies established

---

*This consolidation serves as the foundation for systematic failure analysis and resolution planning.*