# Test Execution Baseline - Sun Aug 31 12:57:45 CEST 2025
## Security Category Results
FAILED tests/security/test_encryption_data_protection.py::TestPasswordSecurity::test_bcrypt_password_hashing - assert 0.7301426188259247 < 0.5
FAILED tests/security/test_registry_security_audit.py::TestLocalRegistrySecurity::test_index_corruption_resilience - AssertionError: assert 'error' in {'version': '1.0.0', 'created_at': None, 'last_updated': None, 'model_count': 0, 'registry_path': '/tmp/tmpx54miq6q/test_registry'}
======================== 2 failed, 143 passed in 6.82s =========================

## Tools Category Results
FAILED tests/tools/test_model_io_manifest.py::TestManifestUtilities::test_get_manifest_info - KeyError: 'model_info'
FAILED tests/tools/test_research_cli.py::TestResearchCLI::test_info_command_json_format - AssertionError: assert 'model_info' in {'compatibility': {'min_emuses_version': '2.0.0', 'python_version': '3.11+', 'required_packages': ['numpy', 'scipy', 'sklearn', 'pandas']}, 'created_at': '2025-08-31T12:58:57.657840', 'description': 'Test model for CLI testing', 'emuses_version': '1.0.0', 'file_integrity': {'test_model_v1_0_0_joblib1_5_1.joblib': {'modified': '2025-08-31T12:58:57.657840', 'sha256': '7754fc2c0307889a6f14cb281cd1c7da8f49d953bf6c94f8689aca2dd2e66acb', 'size': 124}}, 'model_type': 'sklearn_regressor', 'name': 'test_model', 'training_context': {'config_hash': 'no_config', 'dependencies': {'numpy': '1.26.4', 'pandas': '2.3.1', 'scipy': '1.12.0', 'sklearn': '1.7.1'}, 'random_seeds': {}}, 'version': '1.0.0'}
================== 3 failed, 97 passed, 3 warnings in 19.52s ===================

## Model Registry Category Results
Chunk 1: 3 failed, 71 passed
Chunk 2: 14 failed, 1 passed

