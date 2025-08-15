# COMPREHENSIVE TEST FAILURE ANALYSIS
## 📊 **Failure Summary by Category**

**Overall**: 42 failures out of 1234 tests

- **model_registry**: 2 failures (97.2% success)
- **integration**: 1 failures (94.9% success)
- **cli**: 10 failures (66.7% success)
- **foundation**: 10 failures (94.7% success)
- **multi_user**: 10 failures (84.1% success)
- **tools**: 3 failures (97.0% success)
- **pipelines**: 6 failures (76.0% success)

## 🔍 **Failure Classification**

### **Api Usage** (1 failures)

- **test_loop_scope** (cli)
  - File: `unknown`
  - Error: AssertionError - Typer app not implemented yet

### **Environment** (1 failures)

- **test_loop_scope** (integration)
  - File: `tests/integration/test_cli_api_parallelism.py`
  - Error: FileNotFoundError - [Errno 2] No such file or directory: '/home/chrisfoulon/neuro_apps/emuses'

### **Business Logic** (1 failures)

- **test_loop_scope** (model_registry)
  - File: `tests/model_registry/test_academic_features.py`
  - Error: AssertionError - read_heavy search_models success rate: 97.40%

### **Integration** (1 failures)

- **test_loop_scope** (foundation)
  - File: `tests/foundation_fastapi_service/test_api_endpoints_integration.py`
  - Error: AssertionError - 404 == 404

### **Configuration** (3 failures)

- **test_loop_scope** (multi_user)
  - File: `unknown`
  - Error: AssertionError - Regex pattern did not match.

- **test_loop_scope** (tools)
  - File: `tests/tools/test_disaster_recovery.py`
  - Error: AssertionError - assert '❌' in ''

- **test_loop_scope** (pipelines)
  - File: `tests/pipelines/test_inference_progress_simple.py`
  - Error: Unknown - No error message found
