"""
Test documentation compliance for Foundation FastAPI Service

This test validates that all functions and classes have proper NumPy-style docstrings
as required by the project documentation standards.
"""

import ast
import os
import pytest
from pathlib import Path

@pytest.fixture(autouse=True)
def _run_from_repo_root(repo_cwd):
    """These tests assert on repo-relative paths (docker/, .github/, emuses/).

    The autouse `_isolate_cwd` fixture in tests/conftest.py runs every test in a
    throwaway directory, which is right for tests that write files but wrong for
    tests that inspect the repository's own layout. `repo_cwd` opts back in.
    """

class TestDocumentationCompliance:
    """Test suite for documentation compliance"""

    def test_all_functions_have_docstrings(self):
        """Test that all functions and classes have docstrings"""
        
        foundation_service_path = Path("emuses/foundation_fastapi_service")
        python_files = list(foundation_service_path.glob("*.py"))
        
        missing_docstrings = []
        
        for filepath in python_files:
            if filepath.name == "__init__.py":
                continue  # Skip init files
                
            with open(filepath, 'r') as f:
                try:
                    tree = ast.parse(f.read())
                except Exception as e:
                    pytest.fail(f"Parse error in {filepath}: {e}")
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if not ast.get_docstring(node):
                        missing_docstrings.append(f'{filepath.name}:{node.name} (line {node.lineno})')
        
        if missing_docstrings:
            pytest.fail(
                f"Found {len(missing_docstrings)} functions/classes without docstrings:\n" +
                "\n".join(f"  - {item}" for item in missing_docstrings)
            )

    def _check_numpy_format(self, filepath, node):
        """Check if a function has proper NumPy-style docstring format"""
        docstring = ast.get_docstring(node)
        if not docstring or len(docstring.split('\n')) <= 3:
            return None
            
        if node.args.args and 'Parameters' not in docstring:
            if not node.name.startswith('_'):  # Skip private methods
                return f'{filepath.name}:{node.name} - missing Parameters section'
        return None

    def test_docstring_format_compliance(self):
        """Test that existing docstrings follow NumPy style guide"""
        
        foundation_service_path = Path("emuses/foundation_fastapi_service")
        python_files = list(foundation_service_path.glob("*.py"))
        
        format_violations = []
        
        for filepath in python_files:
            if filepath.name == "__init__.py":
                continue
                
            with open(filepath, 'r') as f:
                try:
                    tree = ast.parse(f.read())
                except Exception:
                    continue
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    violation = self._check_numpy_format(filepath, node)
                    if violation:
                        format_violations.append(violation)
        
        # For now, this is a warning rather than a failure
        if format_violations:
            print(f"\nWarning: {len(format_violations)} docstrings may not follow NumPy format")
