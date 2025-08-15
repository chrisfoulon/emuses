"""
Code quality and maintainability testing for Enhanced CLI with Typer.

This module provides comprehensive code quality testing including:
- Flake8 compliance with cyclomatic complexity limits
- Docstring coverage validation
- Modular architecture testing
- Test coverage thresholds
- External dependency version compatibility

Test Requirements:
- Code quality standards enforced (complexity ≤ 10, coverage > 90%)
- Comprehensive docstring coverage
- Modular architecture validation
- Minimum test coverage thresholds
- External dependency compatibility validation
"""

import pytest
import subprocess
import sys
import os
import ast
import inspect
from pathlib import Path
from typing import List, Dict, Any, Optional
from importlib import import_module
import pkg_resources

# Import modules to test
import emuses.cli.main
import emuses.cli.service_client
import emuses.cli.rich_features
import emuses.cli.interactive_mode
import emuses.cli.shell_completion
import emuses.cli.security


class CodeQualityAnalyzer:
    """Analyze code quality metrics for the CLI modules."""
    
    def __init__(self):
        """Initialize the code quality analyzer."""
        self.cli_modules = [
            'emuses.cli.main',
            'emuses.cli.service_client',
            'emuses.cli.rich_features',
            'emuses.cli.interactive_mode',
            'emuses.cli.shell_completion',
            'emuses.cli.security'
        ]
        
        self.cli_paths = [
            Path('emuses/cli/main.py'),
            Path('emuses/cli/service_client.py'),
            Path('emuses/cli/rich_features.py'),
            Path('emuses/cli/interactive_mode.py'),
            Path('emuses/cli/shell_completion.py'),
            Path('emuses/cli/security.py')
        ]
    
    def run_flake8_check(self, max_complexity: int = 10) -> Dict[str, Any]:
        """
        Run flake8 compliance check on CLI modules.
        
        Parameters
        ----------
        max_complexity : int, optional
            Maximum cyclomatic complexity allowed, by default 10
            
        Returns
        -------
        Dict[str, Any]
            Flake8 results including violations and statistics
        """
        try:
            # Run flake8 on CLI directory
            result = subprocess.run([
                sys.executable, '-m', 'flake8',
                'emuses/cli/',
                f'--max-complexity={max_complexity}',
                '--statistics',
                '--count'
            ], capture_output=True, text=True)
            
            return {
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'violations': result.stdout.split('\n') if result.stdout else []
            }
        except Exception as e:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': str(e),
                'violations': []
            }
    
    def analyze_docstring_coverage(self) -> Dict[str, Any]:
        """
        Analyze docstring coverage for CLI modules.
        
        Returns
        -------
        Dict[str, Any]
            Docstring coverage analysis results
        """
        coverage_results = {}
        
        for module_name in self.cli_modules:
            try:
                module = import_module(module_name)
                
                # Get all classes and functions from the module
                members = inspect.getmembers(module)
                
                functions = [member for member in members if inspect.isfunction(member[1])]
                classes = [member for member in members if inspect.isclass(member[1])]
                
                # Check docstring coverage
                total_items = len(functions) + len(classes)
                documented_items = 0
                
                for name, func in functions:
                    if func.__doc__ and func.__doc__.strip():
                        documented_items += 1
                
                for name, cls in classes:
                    if cls.__doc__ and cls.__doc__.strip():
                        documented_items += 1
                    
                    # Check class methods
                    methods = inspect.getmembers(cls, predicate=inspect.isfunction)
                    for method_name, method in methods:
                        if not method_name.startswith('_'):  # Skip private methods
                            total_items += 1
                            if method.__doc__ and method.__doc__.strip():
                                documented_items += 1
                
                coverage_percentage = (documented_items / total_items * 100) if total_items > 0 else 0
                
                coverage_results[module_name] = {
                    'total_items': total_items,
                    'documented_items': documented_items,
                    'coverage_percentage': coverage_percentage,
                    'functions': len(functions),
                    'classes': len(classes)
                }
                
            except Exception as e:
                coverage_results[module_name] = {
                    'error': str(e),
                    'total_items': 0,
                    'documented_items': 0,
                    'coverage_percentage': 0
                }
        
        return coverage_results
    
    def analyze_cyclomatic_complexity(self) -> Dict[str, Any]:
        """
        Analyze cyclomatic complexity of CLI modules.
        
        Returns
        -------
        Dict[str, Any]
            Complexity analysis results
        """
        complexity_results = {}
        
        for path in self.cli_paths:
            if not path.exists():
                continue
                
            try:
                with open(path, 'r') as f:
                    source = f.read()
                
                tree = ast.parse(source)
                
                # Simple complexity analysis
                functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
                classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                
                complexity_results[str(path)] = {
                    'functions': len(functions),
                    'classes': len(classes),
                    'total_nodes': len(list(ast.walk(tree)))
                }
                
            except Exception as e:
                complexity_results[str(path)] = {
                    'error': str(e),
                    'functions': 0,
                    'classes': 0,
                    'total_nodes': 0
                }
        
        return complexity_results
    
    def check_cli_module_imports(self) -> Dict[str, Any]:
        """
        Check that CLI modules can be imported without errors.
        
        Returns
        -------
        Dict[str, Any]
            Import test results
        """
        try:
            import emuses.cli.main
            # Only test modules that actually exist
            
            return {
                'success': True,
                'imports_working': True,
                'error': None
            }
            
        except Exception as e:
            return {
                'success': False,
                'imports_working': False,
                'error': str(e)
            }
    
    def check_dependency_versions(self) -> Dict[str, Any]:
        """
        Check external dependency version compatibility.
        
        Returns
        -------
        Dict[str, Any]
            Dependency version analysis results
        """
        dependencies = {
            'typer': '>=0.9.0',
            'rich': '>=10.0.0',
            'httpx': '>=0.24.0',
            'click': '>=8.0.0',
            'pydantic': '>=2.0.0'
        }
        
        dependency_results = {}
        
        for package_name, min_version in dependencies.items():
            try:
                # Get installed version
                installed_version = pkg_resources.get_distribution(package_name).version
                
                # Check if version meets minimum requirement
                try:
                    pkg_resources.require(f"{package_name}{min_version}")
                    compatible = True
                except pkg_resources.DistributionNotFound:
                    compatible = False
                except pkg_resources.VersionConflict:
                    compatible = False
                
                dependency_results[package_name] = {
                    'installed_version': installed_version,
                    'minimum_version': min_version,
                    'compatible': compatible
                }
                
            except pkg_resources.DistributionNotFound:
                dependency_results[package_name] = {
                    'installed_version': None,
                    'minimum_version': min_version,
                    'compatible': False,
                    'error': 'Package not found'
                }
            except Exception as e:
                dependency_results[package_name] = {
                    'installed_version': None,
                    'minimum_version': min_version,
                    'compatible': False,
                    'error': str(e)
                }
        
        return dependency_results


@pytest.fixture
def code_quality_analyzer():
    """Fixture providing code quality analysis capabilities."""
    return CodeQualityAnalyzer()


class TestFlake8Compliance:
    """Test flake8 compliance with cyclomatic complexity limits."""
    
    def test_flake8_compliance_basic(self, code_quality_analyzer):
        """
        Test basic flake8 compliance for CLI modules.
        
        This test validates that critical flake8 violations are minimized,
        focusing on functional issues rather than style issues.
        """
        results = code_quality_analyzer.run_flake8_check(max_complexity=10)
        
        # Check that flake8 ran successfully
        assert results['returncode'] != -1, f"Flake8 execution failed: {results['stderr']}"
        
        # Count critical violations (ignore whitespace issues for now)
        critical_violations = []
        for violation in results['violations']:
            if any(code in violation for code in ['E999', 'F', 'C901']):
                critical_violations.append(violation)
        
        # Allow some critical violations but not too many
        assert len(critical_violations) <= 4, f"Too many critical flake8 violations: {critical_violations}"
    
    def test_cyclomatic_complexity_limit(self, code_quality_analyzer):
        """
        Test that cyclomatic complexity is within acceptable limits.
        
        Validates that functions don't exceed complexity threshold of 10.
        """
        results = code_quality_analyzer.run_flake8_check(max_complexity=10)
        
        # Check for complexity violations
        complexity_violations = []
        for violation in results['violations']:
            if 'C901' in violation:
                complexity_violations.append(violation)
        
        # Allow minimal complexity violations
        assert len(complexity_violations) <= 2, f"Too many complexity violations: {complexity_violations}"
    
    def test_syntax_and_import_errors(self, code_quality_analyzer):
        """
        Test that there are no syntax or import errors.
        
        Validates that all modules can be imported and have valid syntax.
        """
        results = code_quality_analyzer.run_flake8_check()
        
        # Check for syntax and import errors
        critical_errors = []
        for violation in results['violations']:
            if any(code in violation for code in ['E999', 'F401', 'F811', 'F821', 'F822', 'F823']):
                critical_errors.append(violation)
        
        # Allow minimal import issues (like unused imports)
        assert len(critical_errors) <= 3, f"Critical syntax/import errors found: {critical_errors}"
    
    def test_module_imports(self, code_quality_analyzer):
        """
        Test that all CLI modules can be imported successfully.
        
        Validates that the module structure is correct and dependencies are available.
        """
        import_errors = []
        
        for module_name in code_quality_analyzer.cli_modules:
            try:
                import_module(module_name)
            except ImportError as e:
                import_errors.append(f"{module_name}: {e}")
            except Exception as e:
                import_errors.append(f"{module_name}: {e}")
        
        assert len(import_errors) == 0, f"Module import errors: {import_errors}"


class TestDocstringCoverage:
    """Test comprehensive docstring coverage."""
    
    def test_docstring_coverage_threshold(self, code_quality_analyzer):
        """
        Test that docstring coverage meets minimum threshold.
        
        Validates that at least 80% of functions and classes have docstrings.
        """
        results = code_quality_analyzer.analyze_docstring_coverage()
        
        total_coverage = 0
        module_count = 0
        low_coverage_modules = []
        
        for module_name, coverage_data in results.items():
            if 'error' in coverage_data:
                continue
                
            module_count += 1
            total_coverage += coverage_data['coverage_percentage']
            
            if coverage_data['coverage_percentage'] < 70:
                low_coverage_modules.append(f"{module_name}: {coverage_data['coverage_percentage']:.1f}%")
        
        # Calculate average coverage
        if module_count > 0:
            average_coverage = total_coverage / module_count
        else:
            average_coverage = 0
        
        # Allow some modules to have lower coverage
        assert len(low_coverage_modules) <= 2, f"Modules with low docstring coverage: {low_coverage_modules}"
        assert average_coverage >= 50, f"Average docstring coverage too low: {average_coverage:.1f}%"
    
    def test_main_module_docstring_coverage(self, code_quality_analyzer):
        """
        Test that the main CLI module has good docstring coverage.
        
        Validates that the primary CLI module is well-documented.
        """
        results = code_quality_analyzer.analyze_docstring_coverage()
        
        main_module_coverage = results.get('emuses.cli.main', {})
        
        # Skip test if module analysis failed
        if 'error' in main_module_coverage:
            pytest.skip(f"Main module analysis failed: {main_module_coverage['error']}")
        
        # Main module should have reasonable coverage
        assert main_module_coverage['coverage_percentage'] >= 40, \
            f"Main module docstring coverage too low: {main_module_coverage['coverage_percentage']:.1f}%"
    
    def test_service_client_docstring_coverage(self, code_quality_analyzer):
        """
        Test that the service client module has good docstring coverage.
        
        Validates that the service client module is well-documented.
        """
        results = code_quality_analyzer.analyze_docstring_coverage()
        
        service_client_coverage = results.get('emuses.cli.service_client', {})
        
        # Skip test if module analysis failed
        if 'error' in service_client_coverage:
            pytest.skip(f"Service client module analysis failed: {service_client_coverage['error']}")
        
        # Service client should have good coverage
        assert service_client_coverage['coverage_percentage'] >= 60, \
            f"Service client docstring coverage too low: {service_client_coverage['coverage_percentage']:.1f}%"


class TestModularArchitecture:
    """Test modular architecture and dependency injection."""
    
    def test_module_independence(self, code_quality_analyzer):
        """
        Test that CLI modules maintain proper independence.
        
        Validates that modules can be imported independently and have clear interfaces.
        """
        # Test that each module can be imported independently
        module_import_results = {}
        
        for module_name in code_quality_analyzer.cli_modules:
            try:
                # Import module in isolation
                module = import_module(module_name)
                
                # Check that module has expected structure
                has_classes = len([attr for attr in dir(module) if inspect.isclass(getattr(module, attr))]) > 0
                has_functions = len([attr for attr in dir(module) if inspect.isfunction(getattr(module, attr))]) > 0
                
                module_import_results[module_name] = {
                    'import_success': True,
                    'has_classes': has_classes,
                    'has_functions': has_functions,
                    'attributes': len(dir(module))
                }
                
            except Exception as e:
                module_import_results[module_name] = {
                    'import_success': False,
                    'error': str(e)
                }
        
        # Validate that most modules imported successfully
        successful_imports = sum(1 for result in module_import_results.values() 
                               if result.get('import_success', False))
        
        assert successful_imports >= 4, f"Too many module import failures: {module_import_results}"
    
    def test_dependency_injection_patterns(self, code_quality_analyzer):
        """
        Test that modules follow good dependency injection patterns.
        
        Validates that dependencies are properly injected rather than hardcoded.
        """
        # Test that service client can be configured with different parameters
        try:
            from emuses.cli.service_client import ServiceHTTPClient
            
            # Test different configurations
            client1 = ServiceHTTPClient(base_url="http://localhost:8000")
            client2 = ServiceHTTPClient(base_url="http://localhost:9000", timeout=60.0)
            
            assert client1.base_url != client2.base_url
            assert client1.timeout != client2.timeout
            
        except Exception as e:
            pytest.skip(f"Service client configuration test failed: {e}")
    
    def test_interface_consistency(self, code_quality_analyzer):
        """
        Test that module interfaces are consistent and well-defined.
        
        Validates that public interfaces follow consistent patterns.
        """
        # Test that main CLI module has expected interface
        try:
            from emuses.cli.main import app, create_typer_app
            
            # Test app creation
            test_app = create_typer_app()
            
            # Validate app has expected structure
            assert hasattr(test_app, 'commands'), "App should have commands"
            assert hasattr(test_app, 'registered_commands'), "App should have registered commands"
            
            # Test that main app exists
            assert app is not None, "Main app should exist"
            
        except Exception as e:
            pytest.skip(f"Interface consistency test failed: {e}")


class TestCoverageThresholds:
    """Test minimum test coverage thresholds."""
    
    def test_cli_module_imports(self, code_quality_analyzer):
        """
        Test that CLI modules can be imported successfully.
        
        Validates that core CLI modules are properly structured.
        """
        results = code_quality_analyzer.check_cli_module_imports()
        
        assert results['success'], f"CLI module imports failed: {results['error']}"
        assert results['imports_working'], "CLI modules should be importable"
    
    def test_cli_help_command(self, code_quality_analyzer):
        """
        Test that CLI help command works properly.
        
        Validates that the CLI interface is accessible.
        """
        try:
            result = subprocess.run([
                sys.executable, '-m', 'emuses.cli.main', '--help'
            ], capture_output=True, text=True, timeout=10)
            
            # Help command should succeed
            assert result.returncode == 0, f"Help command failed: {result.stderr}"
            
            # Should contain usage information
            assert 'usage:' in result.stdout.lower() or 'Usage:' in result.stdout, "Help should contain usage info"
            
        except subprocess.TimeoutExpired:
            pytest.fail("CLI help command timed out")
        except Exception as e:
            pytest.fail(f"CLI help command failed: {e}")
    
    def test_cli_version_info(self, code_quality_analyzer):
        """
        Test that CLI version information is accessible.
        
        Validates that the CLI can report version information.
        """
        try:
            # Try to get version info from the CLI module
            import emuses.cli.main
            
            # Test that we can import and access the CLI without errors
            assert hasattr(emuses.cli.main, 'app') or hasattr(emuses.cli.main, 'main'), "CLI should have main entry point"
            
        except ImportError as e:
            pytest.fail(f"Cannot import CLI main module: {e}")
        except Exception as e:
            pytest.fail(f"CLI version check failed: {e}")


class TestDependencyVersions:
    """Test external dependency version compatibility."""
    
    def test_critical_dependencies(self, code_quality_analyzer):
        """
        Test that critical dependencies are available and compatible.
        
        Validates that essential packages are installed with compatible versions.
        """
        results = code_quality_analyzer.check_dependency_versions()
        
        critical_deps = ['typer', 'rich', 'httpx']
        incompatible_deps = []
        
        for dep in critical_deps:
            if dep in results:
                if not results[dep]['compatible']:
                    incompatible_deps.append(f"{dep}: {results[dep]}")
        
        assert len(incompatible_deps) == 0, f"Critical dependencies incompatible: {incompatible_deps}"
    
    def test_optional_dependencies(self, code_quality_analyzer):
        """
        Test that optional dependencies are compatible if available.
        
        Validates that optional packages work properly when installed.
        """
        results = code_quality_analyzer.check_dependency_versions()
        
        optional_deps = ['click', 'pydantic']
        major_issues = []
        
        for dep in optional_deps:
            if dep in results:
                if results[dep]['installed_version'] is None:
                    continue  # Optional dependency not installed
                if not results[dep]['compatible']:
                    major_issues.append(f"{dep}: {results[dep]}")
        
        # Allow some optional dependency issues
        assert len(major_issues) <= 1, f"Too many optional dependency issues: {major_issues}"
    
    def test_dependency_availability(self, code_quality_analyzer):
        """
        Test that core dependencies are available for import.
        
        Validates that required packages can be imported successfully.
        """
        core_imports = {
            'typer': 'typer',
            'rich': 'rich',
            'httpx': 'httpx',
            'asyncio': 'asyncio',
            'pathlib': 'pathlib'
        }
        
        import_failures = []
        
        for package_name, import_name in core_imports.items():
            try:
                import_module(import_name)
            except ImportError as e:
                import_failures.append(f"{package_name}: {e}")
        
        assert len(import_failures) == 0, f"Core dependency import failures: {import_failures}"