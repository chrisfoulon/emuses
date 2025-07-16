"""
Interactive mode with security and validation for enhanced CLI experience.

This module provides interactive workflow management, parameter validation,
secure file picking, configuration templates, and interactive parameter review
for improved user experience with guided workflows.

Key Features:
- Guided workflow prompts for common scenarios
- Parameter validation with security checks
- Secure file picker with permission handling
- Configuration templates for different use cases
- Interactive parameter review and confirmation
"""

import os
import re
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel


class WorkflowType(Enum):
    """Enumeration of available workflow types."""
    DATA_PROCESSING = "data_processing"
    MODEL_TRAINING = "model_training"
    VISUALIZATION = "visualization"
    ANALYSIS = "analysis"
    EXPORT = "export"


@dataclass
class ValidationResult:
    """Result of parameter validation."""
    is_valid: bool
    value: Any = None
    error_message: str = ""
    warnings: List[str] = field(default_factory=list)


@dataclass
class WorkflowStep:
    """Represents a step in a workflow."""
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    required: bool = True
    completed: bool = False


@dataclass
class WorkflowDefinition:
    """Defines a complete workflow."""
    name: str
    description: str
    steps: List[WorkflowStep] = field(default_factory=list)
    category: str = "general"
    version: str = "1.0"


class InteractiveWorkflowManager:
    """
    Interactive workflow manager for guided user experiences.
    
    Provides workflow management with step-by-step guidance,
    progress tracking, and context-aware prompts.
    
    Attributes
    ----------
    available_workflows : List[WorkflowDefinition]
        List of available workflow definitions
    current_workflow : Optional[Dict]
        Currently active workflow instance
    workflow_history : List[Dict]
        History of completed workflows
    """
    
    def __init__(self):
        """
        Initialize the interactive workflow manager.
        
        Returns
        -------
        None
        """
        self.available_workflows = self._load_default_workflows()
        self.current_workflow = None
        self.workflow_history = []
        self._current_step_index = 0
        self.console = Console()
    
    def _load_default_workflows(self) -> List[WorkflowDefinition]:
        """
        Load default workflow definitions.
        
        Returns
        -------
        List[WorkflowDefinition]
            List of default workflow definitions
        """
        workflows = []
        
        # Data Processing Workflow
        data_processing = WorkflowDefinition(
            name="data_processing",
            description="Process and analyze data files",
            category="data",
            steps=[
                WorkflowStep(
                    name="select_input",
                    description="Select input data file",
                    parameters={
                        "input_file": {"type": "file", "extensions": [".csv", ".json", ".txt"]},
                        "file_format": {"type": "choice", "options": ["csv", "json", "txt"]}
                    }
                ),
                WorkflowStep(
                    name="configure_processing",
                    description="Configure processing options",
                    parameters={
                        "processing_method": {"type": "choice", "options": ["standard", "advanced", "custom"]},
                        "output_format": {"type": "choice", "options": ["csv", "json", "parquet"]}
                    }
                ),
                WorkflowStep(
                    name="select_output",
                    description="Select output location",
                    parameters={
                        "output_file": {"type": "file", "mode": "write"},
                        "overwrite": {"type": "confirm", "default": False}
                    }
                )
            ]
        )
        workflows.append(data_processing)
        
        # Model Training Workflow
        model_training = WorkflowDefinition(
            name="model_training",
            description="Train machine learning models",
            category="ml",
            steps=[
                WorkflowStep(
                    name="select_dataset",
                    description="Select training dataset",
                    parameters={
                        "dataset_file": {"type": "file", "extensions": [".csv", ".parquet"]},
                        "target_column": {"type": "string"}
                    }
                ),
                WorkflowStep(
                    name="configure_model",
                    description="Configure model parameters",
                    parameters={
                        "model_type": {"type": "choice", "options": ["linear", "tree", "ensemble"]},
                        "validation_split": {"type": "numeric", "min": 0.1, "max": 0.5, "default": 0.2}
                    }
                ),
                WorkflowStep(
                    name="training_options",
                    description="Set training options",
                    parameters={
                        "epochs": {"type": "numeric", "min": 1, "max": 1000, "default": 10},
                        "save_model": {"type": "confirm", "default": True}
                    }
                )
            ]
        )
        workflows.append(model_training)
        
        # Visualization Workflow
        visualization = WorkflowDefinition(
            name="visualization",
            description="Create data visualizations",
            category="viz",
            steps=[
                WorkflowStep(
                    name="select_data",
                    description="Select data for visualization",
                    parameters={
                        "data_file": {"type": "file", "extensions": [".csv", ".json"]},
                        "columns": {"type": "string", "description": "Comma-separated column names"}
                    }
                ),
                WorkflowStep(
                    name="configure_plot",
                    description="Configure plot settings",
                    parameters={
                        "plot_type": {"type": "choice", "options": ["scatter", "line", "bar", "histogram"]},
                        "title": {"type": "string", "default": "Data Visualization"}
                    }
                ),
                WorkflowStep(
                    name="output_settings",
                    description="Configure output settings",
                    parameters={
                        "output_file": {"type": "file", "mode": "write", "extensions": [".png", ".pdf", ".svg"]},
                        "dpi": {"type": "numeric", "min": 72, "max": 300, "default": 150}
                    }
                )
            ]
        )
        workflows.append(visualization)
        
        return workflows
    
    def list_available_workflows(self) -> List[Dict[str, Any]]:
        """
        List all available workflows.
        
        Returns
        -------
        List[Dict[str, Any]]
            List of workflow information dictionaries
        """
        return [
            {
                "name": wf.name,
                "description": wf.description,
                "category": wf.category,
                "steps": len(wf.steps),
                "version": wf.version
            }
            for wf in self.available_workflows
        ]
    
    def start_workflow(self, workflow_name: str) -> str:
        """
        Start a new workflow.
        
        Parameters
        ----------
        workflow_name : str
            Name of the workflow to start
            
        Returns
        -------
        str
            Unique workflow instance ID
            
        Raises
        ------
        ValueError
            If workflow name is not found
        """
        # Find workflow definition
        workflow_def = None
        for wf in self.available_workflows:
            if wf.name == workflow_name:
                workflow_def = wf
                break
        
        if workflow_def is None:
            raise ValueError(f"Workflow '{workflow_name}' not found")
        
        # Create workflow instance
        workflow_id = str(uuid.uuid4())
        self.current_workflow = {
            "id": workflow_id,
            "name": workflow_name,
            "definition": workflow_def,
            "status": "active",
            "current_step": 0,
            "parameters": {},
            "start_time": None,
            "end_time": None
        }
        
        self._current_step_index = 0
        
        return workflow_id
    
    def get_current_step(self) -> Optional[Dict[str, Any]]:
        """
        Get the current workflow step.
        
        Returns
        -------
        Optional[Dict[str, Any]]
            Current step information or None if no active workflow
        """
        if not self.current_workflow:
            return None
        
        steps = self.current_workflow["definition"].steps
        if self._current_step_index >= len(steps):
            return None
        
        step = steps[self._current_step_index]
        return {
            "name": step.name,
            "description": step.description,
            "parameters": step.parameters,
            "required": step.required,
            "completed": step.completed,
            "index": self._current_step_index,
            "total_steps": len(steps)
        }
    
    def next_step(self) -> Optional[Dict[str, Any]]:
        """
        Move to the next workflow step.
        
        Returns
        -------
        Optional[Dict[str, Any]]
            Next step information or None if workflow is complete
        """
        if not self.current_workflow:
            return None
        
        steps = self.current_workflow["definition"].steps
        if self._current_step_index < len(steps) - 1:
            self._current_step_index += 1
            return self.get_current_step()
        
        return None
    
    def previous_step(self) -> Optional[Dict[str, Any]]:
        """
        Move to the previous workflow step.
        
        Returns
        -------
        Optional[Dict[str, Any]]
            Previous step information or None if at first step
        """
        if not self.current_workflow:
            return None
        
        if self._current_step_index > 0:
            self._current_step_index -= 1
            return self.get_current_step()
        
        return None
    
    def is_workflow_complete(self) -> bool:
        """
        Check if the current workflow is complete.
        
        Returns
        -------
        bool
            True if workflow is complete, False otherwise
        """
        if not self.current_workflow:
            return False
        
        steps = self.current_workflow["definition"].steps
        return self._current_step_index >= len(steps)
    
    def complete_workflow(self) -> Dict[str, Any]:
        """
        Complete the current workflow.
        
        Returns
        -------
        Dict[str, Any]
            Completed workflow summary
        """
        if not self.current_workflow:
            raise ValueError("No active workflow to complete")
        
        # Mark workflow as completed
        self.current_workflow["status"] = "completed"
        self.current_workflow["end_time"] = None
        
        # Add to history
        self.workflow_history.append(self.current_workflow.copy())
        
        # Create summary
        summary = {
            "id": self.current_workflow["id"],
            "name": self.current_workflow["name"],
            "status": "completed",
            "parameters": self.current_workflow["parameters"],
            "steps_completed": len(self.current_workflow["definition"].steps)
        }
        
        # Clear current workflow
        self.current_workflow = None
        self._current_step_index = 0
        
        return summary


class WorkflowPrompt:
    """
    Workflow prompt handler for user interactions.
    
    Provides various prompt types with validation and history tracking
    for interactive workflow steps.
    
    Attributes
    ----------
    prompt_history : List[Dict]
        History of user interactions
    current_context : Dict
        Current prompt context and state
    """
    
    def __init__(self):
        """
        Initialize the workflow prompt handler.
        
        Returns
        -------
        None
        """
        self.prompt_history = []
        self.current_context = {}
        self.console = Console()
    
    def prompt_text(self, message: str, default: Optional[str] = None) -> str:
        """
        Prompt for text input.
        
        Parameters
        ----------
        message : str
            Prompt message to display
        default : Optional[str], optional
            Default value if user provides no input
            
        Returns
        -------
        str
            User input text
        """
        result = typer.prompt(message, default=default)
        
        # Record in history
        self.prompt_history.append({
            "type": "text",
            "message": message,
            "result": result,
            "default": default
        })
        
        return result
    
    def prompt_choice(self, message: str, choices: List[str], default: Optional[str] = None) -> str:
        """
        Prompt for choice selection.
        
        Parameters
        ----------
        message : str
            Prompt message to display
        choices : List[str]
            Available choices
        default : Optional[str], optional
            Default choice if user provides no input
            
        Returns
        -------
        str
            Selected choice
        """
        # Display choices
        choice_text = " / ".join(choices)
        full_message = f"{message} ({choice_text})"
        
        while True:
            result = typer.prompt(full_message, default=default)
            
            if result in choices:
                break
            
            typer.echo(f"Invalid choice. Please select from: {choice_text}")
        
        # Record in history
        self.prompt_history.append({
            "type": "choice",
            "message": message,
            "choices": choices,
            "result": result,
            "default": default
        })
        
        return result
    
    def prompt_confirm(self, message: str, default: bool = False) -> bool:
        """
        Prompt for confirmation.
        
        Parameters
        ----------
        message : str
            Confirmation message
        default : bool, optional
            Default value if user provides no input
            
        Returns
        -------
        bool
            User confirmation result
        """
        result = typer.confirm(message, default=default)
        
        # Record in history
        self.prompt_history.append({
            "type": "confirm",
            "message": message,
            "result": result,
            "default": default
        })
        
        return result
    
    def prompt_path(self, message: str, must_exist: bool = True) -> str:
        """
        Prompt for file/directory path.
        
        Parameters
        ----------
        message : str
            Prompt message
        must_exist : bool, optional
            Whether path must exist, by default True
            
        Returns
        -------
        str
            File/directory path
        """
        while True:
            result = typer.prompt(message)
            
            if not must_exist:
                break
            
            if os.path.exists(result):
                break
            
            typer.echo(f"Path does not exist: {result}")
        
        # Record in history
        self.prompt_history.append({
            "type": "path",
            "message": message,
            "result": result,
            "must_exist": must_exist
        })
        
        return result


class ParameterValidator:
    """
    Parameter validation with security checks.
    
    Provides comprehensive parameter validation including security
    checks for injection attacks, path traversal, and other threats.
    
    Attributes
    ----------
    validation_rules : Dict
        Custom validation rules
    security_checks : Dict
        Security validation configuration
    """
    
    def __init__(self):
        """
        Initialize the parameter validator.
        
        Returns
        -------
        None
        """
        self.validation_rules = {}
        self.security_checks = {
            "sql_injection_patterns": [
                r"(?i)(union|select|insert|update|delete|drop|create|alter|exec|execute)",
                r"(?i)(script|javascript|vbscript|onload|onerror|onclick)",
                r"(?i)(\$\(|`|<script|</script>)"
            ],
            "path_traversal_patterns": [
                r"\.\.[\\/]",
                r"[\\/]\.\.[\\/]",
                r"\.\./",
                r"\.\.\\",
            ],
            "command_injection_patterns": [
                r"(?i)(\$\(|`|;\s*rm|;\s*del|;\s*format|;\s*shutdown)",
                r"(?i)(&&|\|\||;)\s*(rm|del|format|shutdown|reboot)",
                r"(?i)(\${.*}|\$\{.*\})"
            ]
        }
    
    def validate_file_path(self, path: str) -> ValidationResult:
        """
        Validate file path with security checks.
        
        Parameters
        ----------
        path : str
            File path to validate
            
        Returns
        -------
        ValidationResult
            Validation result with security assessment
        """
        # Security checks first
        security_result = self._check_path_security(path)
        if not security_result.is_valid:
            return security_result
        
        # Check if path exists
        if not os.path.exists(path):
            return ValidationResult(
                is_valid=False,
                error_message=f"Path does not exist: {path}"
            )
        
        # Check if path is accessible
        if not os.access(path, os.R_OK):
            return ValidationResult(
                is_valid=False,
                error_message=f"Path is not readable: {path}"
            )
        
        return ValidationResult(
            is_valid=True,
            value=path
        )
    
    def _check_path_security(self, path: str) -> ValidationResult:
        """
        Check path for security vulnerabilities.
        
        Parameters
        ----------
        path : str
            Path to check
            
        Returns
        -------
        ValidationResult
            Security validation result
        """
        # Check for path traversal
        for pattern in self.security_checks["path_traversal_patterns"]:
            if re.search(pattern, path):
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Path contains security risks (path traversal): {path}"
                )
        
        # Check for absolute paths to system directories
        system_paths = ["/etc", "/sys", "/proc", "/root", "C:\\Windows", "C:\\System32"]
        for sys_path in system_paths:
            if path.startswith(sys_path):
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Access to system directory not allowed: {path}"
                )
        
        return ValidationResult(is_valid=True, value=path)
    
    def validate_numeric(self, value: Any, min_value: Optional[float] = None, 
                        max_value: Optional[float] = None) -> ValidationResult:
        """
        Validate numeric parameter.
        
        Parameters
        ----------
        value : Any
            Value to validate
        min_value : Optional[float], optional
            Minimum allowed value
        max_value : Optional[float], optional
            Maximum allowed value
            
        Returns
        -------
        ValidationResult
            Validation result
        """
        # Try to convert to float
        try:
            if isinstance(value, str):
                numeric_value = float(value)
            elif isinstance(value, (int, float)):
                numeric_value = float(value)
            else:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Value is not numeric: {value}"
                )
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                error_message=f"Cannot convert to numeric: {value}"
            )
        
        # Check range
        if min_value is not None and numeric_value < min_value:
            return ValidationResult(
                is_valid=False,
                error_message=f"Value {numeric_value} is below minimum {min_value}"
            )
        
        if max_value is not None and numeric_value > max_value:
            return ValidationResult(
                is_valid=False,
                error_message=f"Value {numeric_value} is above maximum {max_value}"
            )
        
        return ValidationResult(
            is_valid=True,
            value=numeric_value
        )
    
    def validate_string(self, value: str, min_length: Optional[int] = None,
                       max_length: Optional[int] = None) -> ValidationResult:
        """
        Validate string parameter with security checks.
        
        Parameters
        ----------
        value : str
            String value to validate
        min_length : Optional[int], optional
            Minimum string length
        max_length : Optional[int], optional
            Maximum string length
            
        Returns
        -------
        ValidationResult
            Validation result
        """
        if not isinstance(value, str):
            return ValidationResult(
                is_valid=False,
                error_message=f"Value is not a string: {value}"
            )
        
        # Security checks
        security_result = self._check_string_security(value)
        if not security_result.is_valid:
            return security_result
        
        # Length checks
        if min_length is not None and len(value) < min_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"String length {len(value)} is below minimum {min_length}"
            )
        
        if max_length is not None and len(value) > max_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"String length {len(value)} is above maximum {max_length}"
            )
        
        return ValidationResult(
            is_valid=True,
            value=value
        )
    
    def _check_string_security(self, value: str) -> ValidationResult:
        """
        Check string for security vulnerabilities.
        
        Parameters
        ----------
        value : str
            String to check
            
        Returns
        -------
        ValidationResult
            Security validation result
        """
        # Check for SQL injection patterns
        for pattern in self.security_checks["sql_injection_patterns"]:
            if re.search(pattern, value):
                return ValidationResult(
                    is_valid=False,
                    error_message="String contains potentially malicious content (SQL injection)"
                )
        
        # Check for command injection patterns
        for pattern in self.security_checks["command_injection_patterns"]:
            if re.search(pattern, value):
                return ValidationResult(
                    is_valid=False,
                    error_message="String contains potentially malicious content (command injection)"
                )
        
        return ValidationResult(is_valid=True, value=value)


class SecureFilePicker:
    """
    Secure file picker with permission handling.
    
    Provides secure file selection with extension validation,
    size checks, and permission verification.
    
    Attributes
    ----------
    allowed_extensions : List[str]
        List of allowed file extensions
    max_file_size : int
        Maximum file size in bytes
    base_directory : Optional[str]
        Base directory for file operations
    """
    
    def __init__(self, base_directory: Optional[str] = None):
        """
        Initialize the secure file picker.
        
        Parameters
        ----------
        base_directory : Optional[str], optional
            Base directory for file operations
            
        Returns
        -------
        None
        """
        self.allowed_extensions = ['.txt', '.csv', '.json', '.xml', '.yaml', '.yml']
        self.max_file_size = 100 * 1024 * 1024  # 100MB default
        self.base_directory = base_directory
        self.console = Console()
    
    def select_file(self, prompt: str, allowed_extensions: Optional[List[str]] = None) -> str:
        """
        Select a file with security validation.
        
        Parameters
        ----------
        prompt : str
            Prompt message for file selection
        allowed_extensions : Optional[List[str]], optional
            List of allowed file extensions
            
        Returns
        -------
        str
            Selected file path
        """
        if allowed_extensions is None:
            allowed_extensions = self.allowed_extensions
        
        while True:
            file_path = typer.prompt(prompt)
            
            # Security and validation checks
            if not self._validate_file_selection(file_path, allowed_extensions):
                continue
            
            return file_path
    
    def _validate_file_selection(self, file_path: str, allowed_extensions: List[str]) -> bool:
        """
        Validate file selection.
        
        Parameters
        ----------
        file_path : str
            File path to validate
        allowed_extensions : List[str]
            Allowed file extensions
            
        Returns
        -------
        bool
            True if file is valid for selection
        """
        # Check if file exists
        if not os.path.exists(file_path):
            typer.echo(f"File does not exist: {file_path}")
            return False
        
        # Check file extension
        if not self.is_extension_allowed(file_path, allowed_extensions):
            typer.echo(f"File extension not allowed. Allowed: {', '.join(allowed_extensions)}")
            return False
        
        # Check file size
        if not self.is_file_size_valid(file_path):
            typer.echo(f"File size exceeds maximum allowed size")
            return False
        
        # Check file permissions
        if not self.check_file_permissions(file_path, 'read'):
            typer.echo(f"File is not readable: {file_path}")
            return False
        
        return True
    
    def is_extension_allowed(self, filename: str, allowed_extensions: List[str]) -> bool:
        """
        Check if file extension is allowed.
        
        Parameters
        ----------
        filename : str
            File name or path
        allowed_extensions : List[str]
            List of allowed extensions
            
        Returns
        -------
        bool
            True if extension is allowed
        """
        file_ext = Path(filename).suffix.lower()
        return file_ext in [ext.lower() for ext in allowed_extensions]
    
    def is_file_size_valid(self, file_path: str, max_size_mb: Optional[float] = None) -> bool:
        """
        Check if file size is within limits.
        
        Parameters
        ----------
        file_path : str
            Path to file
        max_size_mb : Optional[float], optional
            Maximum size in MB, uses default if None
            
        Returns
        -------
        bool
            True if file size is valid
        """
        if max_size_mb is None:
            max_size_bytes = self.max_file_size
        else:
            max_size_bytes = max_size_mb * 1024 * 1024
        
        try:
            file_size = os.path.getsize(file_path)
            return file_size <= max_size_bytes
        except OSError:
            return False
    
    def check_file_permissions(self, file_path: str, access_type: str) -> bool:
        """
        Check file permissions.
        
        Parameters
        ----------
        file_path : str
            Path to file or directory
        access_type : str
            Type of access ('read', 'write', 'execute')
            
        Returns
        -------
        bool
            True if access is allowed
        """
        access_map = {
            'read': os.R_OK,
            'write': os.W_OK,
            'execute': os.X_OK
        }
        
        if access_type not in access_map:
            return False
        
        return os.access(file_path, access_map[access_type])


class ConfigurationTemplateManager:
    """
    Configuration template management for different use cases.
    
    Manages configuration templates with parameter definitions,
    validation rules, and application logic.
    
    Attributes
    ----------
    templates : Dict[str, Dict]
        Available configuration templates
    template_directory : Optional[str]
        Directory for custom templates
    """
    
    def __init__(self, template_directory: Optional[str] = None):
        """
        Initialize the configuration template manager.
        
        Parameters
        ----------
        template_directory : Optional[str], optional
            Directory for custom templates
            
        Returns
        -------
        None
        """
        self.templates = self._load_default_templates()
        self.template_directory = template_directory
        self.console = Console()
        
        # Load custom templates if directory is specified
        if template_directory and os.path.exists(template_directory):
            self._load_custom_templates()
    
    def _load_default_templates(self) -> Dict[str, Dict]:
        """
        Load default configuration templates.
        
        Returns
        -------
        Dict[str, Dict]
            Default templates dictionary
        """
        templates = {}
        
        # Data Processing Template
        templates['data_processing'] = {
            'name': 'data_processing',
            'description': 'Standard data processing configuration',
            'parameters': {
                'input_file': {
                    'type': 'string',
                    'description': 'Input data file path',
                    'required': True
                },
                'output_file': {
                    'type': 'string',
                    'description': 'Output file path',
                    'required': True
                },
                'processing_method': {
                    'type': 'choice',
                    'options': ['standard', 'advanced', 'custom'],
                    'default': 'standard',
                    'description': 'Processing method to use'
                },
                'chunk_size': {
                    'type': 'integer',
                    'default': 1000,
                    'min': 1,
                    'max': 10000,
                    'description': 'Processing chunk size'
                }
            }
        }
        
        # Model Training Template
        templates['model_training'] = {
            'name': 'model_training',
            'description': 'Machine learning model training configuration',
            'parameters': {
                'dataset_file': {
                    'type': 'string',
                    'description': 'Training dataset file path',
                    'required': True
                },
                'model_type': {
                    'type': 'choice',
                    'options': ['linear', 'tree', 'ensemble', 'neural'],
                    'default': 'linear',
                    'description': 'Type of model to train'
                },
                'validation_split': {
                    'type': 'float',
                    'default': 0.2,
                    'min': 0.1,
                    'max': 0.5,
                    'description': 'Validation set split ratio'
                },
                'max_epochs': {
                    'type': 'integer',
                    'default': 100,
                    'min': 1,
                    'max': 1000,
                    'description': 'Maximum training epochs'
                }
            }
        }
        
        # Visualization Template
        templates['visualization'] = {
            'name': 'visualization',
            'description': 'Data visualization configuration',
            'parameters': {
                'data_file': {
                    'type': 'string',
                    'description': 'Data file for visualization',
                    'required': True
                },
                'plot_type': {
                    'type': 'choice',
                    'options': ['scatter', 'line', 'bar', 'histogram', 'boxplot'],
                    'default': 'scatter',
                    'description': 'Type of plot to create'
                },
                'output_format': {
                    'type': 'choice',
                    'options': ['png', 'pdf', 'svg', 'html'],
                    'default': 'png',
                    'description': 'Output format for visualization'
                },
                'width': {
                    'type': 'integer',
                    'default': 800,
                    'min': 200,
                    'max': 2000,
                    'description': 'Plot width in pixels'
                },
                'height': {
                    'type': 'integer',
                    'default': 600,
                    'min': 200,
                    'max': 2000,
                    'description': 'Plot height in pixels'
                }
            }
        }
        
        return templates
    
    def _load_custom_templates(self):
        """
        Load custom templates from template directory.
        
        Returns
        -------
        None
        """
        if not self.template_directory:
            return
        
        for filename in os.listdir(self.template_directory):
            if filename.endswith('.json'):
                template_path = os.path.join(self.template_directory, filename)
                try:
                    with open(template_path, 'r') as f:
                        template_data = json.load(f)
                    
                    template_name = template_data.get('name', filename[:-5])
                    self.templates[template_name] = template_data
                    
                except (json.JSONDecodeError, IOError) as e:
                    typer.echo(f"Warning: Could not load template {filename}: {e}")
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """
        List all available templates.
        
        Returns
        -------
        List[Dict[str, Any]]
            List of template information
        """
        return [
            {
                'name': template['name'],
                'description': template['description'],
                'parameters': list(template['parameters'].keys())
            }
            for template in self.templates.values()
        ]
    
    def load_template(self, template_name: str) -> Dict[str, Any]:
        """
        Load a specific template.
        
        Parameters
        ----------
        template_name : str
            Name of template to load
            
        Returns
        -------
        Dict[str, Any]
            Template configuration
            
        Raises
        ------
        ValueError
            If template is not found
        """
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")
        
        return self.templates[template_name].copy()
    
    def apply_template(self, template_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply a template with given parameters.
        
        Parameters
        ----------
        template_name : str
            Name of template to apply
        parameters : Dict[str, Any]
            Parameter values to apply
            
        Returns
        -------
        Dict[str, Any]
            Applied configuration
        """
        template = self.load_template(template_name)
        config = {}
        
        # Apply parameters
        for param_name, param_value in parameters.items():
            if param_name in template['parameters']:
                config[param_name] = param_value
        
        # Add defaults for missing parameters
        for param_name, param_def in template['parameters'].items():
            if param_name not in config and 'default' in param_def:
                config[param_name] = param_def['default']
        
        return config
    
    def save_template(self, template_data: Dict[str, Any]) -> bool:
        """
        Save a custom template.
        
        Parameters
        ----------
        template_data : Dict[str, Any]
            Template data to save
            
        Returns
        -------
        bool
            True if template was saved successfully
        """
        template_name = template_data.get('name')
        if not template_name:
            return False
        
        # Add to in-memory templates
        self.templates[template_name] = template_data
        
        # Save to file if template directory is specified
        if self.template_directory:
            os.makedirs(self.template_directory, exist_ok=True)
            template_path = os.path.join(self.template_directory, f"{template_name}.json")
            
            try:
                with open(template_path, 'w') as f:
                    json.dump(template_data, f, indent=2)
                return True
            except IOError:
                return False
        
        return True


class InteractiveParameterReview:
    """
    Interactive parameter review and confirmation.
    
    Provides parameter review session with validation,
    modification, and confirmation capabilities.
    
    Attributes
    ----------
    parameters : Dict[str, Dict]
        Parameters for review
    review_history : List[Dict]
        History of review sessions
    """
    
    def __init__(self):
        """
        Initialize the interactive parameter review.
        
        Returns
        -------
        None
        """
        self.parameters = {}
        self.review_history = []
        self.console = Console()
        self._validator = ParameterValidator()
        self._review_complete = False
    
    def add_parameter(self, name: str, value: Any, description: str = "") -> None:
        """
        Add a parameter for review.
        
        Parameters
        ----------
        name : str
            Parameter name
        value : Any
            Parameter value
        description : str, optional
            Parameter description
            
        Returns
        -------
        None
        """
        self.parameters[name] = {
            'value': value,
            'description': description,
            'validated': False,
            'modified': False
        }
    
    def get_parameters(self) -> Dict[str, Dict]:
        """
        Get all parameters for review.
        
        Returns
        -------
        Dict[str, Dict]
            Parameters dictionary
        """
        return self.parameters.copy()
    
    def modify_parameter(self, name: str, new_value: Any) -> None:
        """
        Modify a parameter value.
        
        Parameters
        ----------
        name : str
            Parameter name
        new_value : Any
            New parameter value
            
        Returns
        -------
        None
        """
        if name in self.parameters:
            self.parameters[name]['value'] = new_value
            self.parameters[name]['modified'] = True
            self.parameters[name]['validated'] = False
    
    def validate_parameter(self, name: str) -> bool:
        """
        Validate a specific parameter.
        
        Parameters
        ----------
        name : str
            Parameter name
            
        Returns
        -------
        bool
            True if parameter is valid
        """
        if name not in self.parameters:
            return False
        
        param = self.parameters[name]
        value = param['value']
        
        # Basic validation based on type
        if isinstance(value, str):
            result = self._validator.validate_string(value)
        elif isinstance(value, (int, float)):
            result = self._validator.validate_numeric(value)
        elif isinstance(value, str) and os.path.sep in value:
            # Treat as file path
            result = self._validator.validate_file_path(value)
        else:
            result = ValidationResult(is_valid=True, value=value)
        
        param['validated'] = result.is_valid
        return result.is_valid
    
    def validate_all_parameters(self) -> bool:
        """
        Validate all parameters.
        
        Returns
        -------
        bool
            True if all parameters are valid
        """
        all_valid = True
        for name in self.parameters:
            if not self.validate_parameter(name):
                all_valid = False
        
        return all_valid
    
    def conduct_review(self) -> bool:
        """
        Conduct an interactive parameter review session.
        
        Returns
        -------
        bool
            True if review was completed successfully
        """
        if not self.parameters:
            return True
        
        # Display parameters
        table = Table(title="Parameter Review")
        table.add_column("Name")
        table.add_column("Value")
        table.add_column("Description")
        
        for name, param in self.parameters.items():
            table.add_row(name, str(param['value']), param['description'])
        
        self.console.print(table)
        
        # Confirm parameters
        confirmed = typer.confirm("Are these parameters correct?")
        
        if confirmed:
            self._review_complete = True
            
            # Record review session
            self.review_history.append({
                'timestamp': None,
                'parameters': self.parameters.copy(),
                'status': 'completed'
            })
        
        return confirmed
    
    def is_review_complete(self) -> bool:
        """
        Check if review is complete.
        
        Returns
        -------
        bool
            True if review is complete
        """
        return self._review_complete
    
    def generate_summary(self) -> Dict[str, Any]:
        """
        Generate a summary of the parameter review.
        
        Returns
        -------
        Dict[str, Any]
            Review summary
        """
        return {
            'total_count': len(self.parameters),
            'validated_count': sum(1 for p in self.parameters.values() if p['validated']),
            'modified_count': sum(1 for p in self.parameters.values() if p['modified']),
            'parameters': self.parameters.copy(),
            'review_complete': self._review_complete
        }