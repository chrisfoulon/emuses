"""
Security utilities for the EMUSES CLI.

This module provides security functions to protect against common vulnerabilities
including directory traversal attacks, command injection, and malicious input.

Key Features:
- Path validation with directory traversal protection
- Input sanitization to prevent injection attacks
- Secure file handling utilities
"""

import os
from pathlib import Path, PurePath
import re
import urllib.parse
from typing import Union


class SecurityError(Exception):
    """Custom exception for security-related errors."""
    pass


def _check_directory_traversal(path_str: str) -> None:
    """
    Check for directory traversal patterns in a path.
    
    Parameters
    ----------
    path_str : str
        The path string to check
        
    Raises
    ------
    SecurityError
        If directory traversal patterns are detected
    """
    # Common directory traversal patterns
    dangerous_patterns = [
        "..",
        "/..",
        "\\..\\",
        "../",
        "..\\",
        "%2e%2e",
        "%2e%2e%2f",
        "%2e%2e%5c",
        "..%2f",
        "..%5c",
    ]
    
    # Check for URL-encoded traversal attempts
    try:
        decoded_path = urllib.parse.unquote(path_str)
    except Exception:
        decoded_path = path_str
    
    # Check both original and decoded paths
    for pattern in dangerous_patterns:
        if pattern in path_str.lower() or pattern in decoded_path.lower():
            raise ValueError(f"Directory traversal detected: {pattern}")


def _check_sensitive_directories(normalized_path: str) -> None:
    """
    Check if path attempts to access sensitive directories.
    
    Parameters
    ----------
    normalized_path : str
        The normalized path to check
        
    Raises
    ------
    ValueError
        If access to sensitive directories is detected
    """
    sensitive_dirs = [
        "/etc/",
        "\\etc\\",
        "/sys/",
        "\\sys\\",
        "/proc/",
        "\\proc\\",
        "/dev/",
        "\\dev\\",
        "/root/",
        "\\root\\",
        "c:\\windows\\",
        "c:/windows/",
        "c:\\system32\\",
        "c:/system32/",
        "c:\\users\\administrator\\",
        "c:/users/administrator/",
    ]
    
    path_lower = normalized_path.lower()
    for sensitive_dir in sensitive_dirs:
        if path_lower.startswith(sensitive_dir):
            raise ValueError(f"Access to sensitive directory denied: {sensitive_dir}")
    
    # Additional check: detect if the path contains sensitive directory components anywhere
    sensitive_components = ["etc", "sys", "proc", "dev", "root", "windows", "system32"]
    path_parts = [part.lower() for part in normalized_path.replace("\\", "/").split("/")]
    
    for component in sensitive_components:
        if component in path_parts:
            raise ValueError(f"Access to sensitive directory component denied: {component}")


def validate_path(path_str: str) -> str:
    """
    Validate a path string for security vulnerabilities.
    
    This function checks for directory traversal attacks and other path-based
    security issues while preserving legitimate path formats.

    Parameters
    ----------
    path_str : str
        The path string to validate

    Returns
    -------
    str
        The validated path string

    Raises
    ------
    SecurityError
        If the path contains directory traversal attempts or other security issues
    ValueError
        If the path is empty or None

    Examples
    --------
    >>> validate_path("/home/user/data.txt")
    '/home/user/data.txt'
    
    >>> validate_path("../../../etc/passwd")  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    SecurityError: Directory traversal detected
    """
    if not path_str or path_str.strip() == "":
        raise ValueError("Path cannot be empty")
    
    # Special case for non-path identifiers
    if path_str.lower() in [
        "mnist",
        "digits_label_dataset",
        "input_matrix",
    ]:
        return path_str
    
    # Check for directory traversal patterns
    _check_directory_traversal(path_str)
    
    # Normalize and check sensitive directories
    normalized_path = os.path.normpath(path_str)
    _check_sensitive_directories(normalized_path)
    
    # Additional security checks
    if len(normalized_path) > 4096:  # Reasonable path length limit
        raise ValueError("Path too long")
    
    # Check for null bytes
    if "\x00" in path_str:
        raise ValueError("Null byte detected in path")
    
    return path_str


def sanitize_input(input_str: str) -> str:
    """
    Sanitize input strings to prevent injection attacks.
    
    This function removes or escapes potentially dangerous characters
    while preserving legitimate input. For highly malicious input,
    it raises an error instead of attempting sanitization.

    Parameters
    ----------
    input_str : str
        The input string to sanitize

    Returns
    -------
    str
        The sanitized input string

    Raises
    ------
    ValueError
        If input is None or contains highly malicious content

    Examples
    --------
    >>> sanitize_input("normal_string")
    'normal_string'
    
    >>> sanitize_input("string; rm -rf /")  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ValueError: Malicious input detected
    """
    if input_str is None:
        raise ValueError("Input cannot be None")
    
    if not isinstance(input_str, str):
        input_str = str(input_str)
    
    # URL decode the input to check for encoded malicious patterns
    try:
        decoded_input = urllib.parse.unquote(input_str)
    except Exception:
        decoded_input = input_str
    
    # Check for highly malicious patterns in both original and decoded input
    malicious_patterns = [
        "rm -rf",
        "del ",
        "rmdir ",
        "format ",
        "$(",
        "`",
        "| del",
        "& rmdir",
        "</script>",
        "<script>",
        "<>",  # HTML/XML injection
        "script",  # Script injection
        "/etc/",
        "\\etc\\",
        "system32",
        "windows\\system32",
    ]
    
    # Check both original and decoded versions
    for pattern in malicious_patterns:
        if pattern in input_str.lower() or pattern in decoded_input.lower():
            raise ValueError(f"Malicious input detected: contains '{pattern}'")
    
    # Check for control characters (especially null bytes)
    if any(ord(c) < 32 for c in input_str if c not in ['\t', '\n', '\r', ' ']):
        raise ValueError("Invalid control characters detected")
    
    # Remove or replace dangerous characters
    # Remove shell metacharacters
    dangerous_chars = [";", "&", "|", "$", "(", ")", "{", "}", "[", "]"]
    
    sanitized = input_str
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, "")
    
    # Remove control characters except common whitespace
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', sanitized)
    
    # Limit length to prevent buffer overflow
    if len(sanitized) > 10000:
        sanitized = sanitized[:10000]
    
    return sanitized.strip()


def secure_file_exists(file_path: Union[str, Path]) -> bool:
    """
    Securely check if a file exists.
    
    This function safely checks for file existence while protecting
    against path traversal and other security issues.

    Parameters
    ----------
    file_path : Union[str, Path]
        The file path to check

    Returns
    -------
    bool
        True if the file exists and is accessible, False otherwise

    Examples
    --------
    >>> secure_file_exists("existing_file.txt")  # doctest: +SKIP
    True
    
    >>> secure_file_exists("nonexistent_file.txt")  # doctest: +SKIP
    False
    """
    try:
        if isinstance(file_path, str):
            validated_path = validate_path(file_path)
            path_obj = Path(validated_path)
        else:
            path_obj = file_path
        
        # Check if path exists and is a file
        return path_obj.exists() and path_obj.is_file()
    
    except (SecurityError, ValueError, OSError):
        return False


def secure_mkdir(dir_path: Union[str, Path]) -> bool:
    """
    Securely create a directory.
    
    This function safely creates directories while protecting
    against path traversal and other security issues.

    Parameters
    ----------
    dir_path : Union[str, Path]
        The directory path to create

    Returns
    -------
    bool
        True if the directory was created or already exists, False otherwise

    Examples
    --------
    >>> secure_mkdir("safe_directory")  # doctest: +SKIP
    True
    """
    try:
        if isinstance(dir_path, str):
            validated_path = validate_path(dir_path)
            path_obj = Path(validated_path)
        else:
            path_obj = dir_path
        
        # Create directory if it doesn't exist
        path_obj.mkdir(parents=True, exist_ok=True)
        return True
    
    except (SecurityError, ValueError, OSError):
        return False


def is_safe_filename(filename: str) -> bool:
    """
    Check if a filename is safe to use.
    
    This function validates filenames to prevent security issues
    with file operations.

    Parameters
    ----------
    filename : str
        The filename to validate

    Returns
    -------
    bool
        True if the filename is safe, False otherwise

    Examples
    --------
    >>> is_safe_filename("data.txt")
    True
    
    >>> is_safe_filename("../../../etc/passwd")
    False
    """
    try:
        # Check if it's just a filename (no path components)
        if os.path.sep in filename or "/" in filename or "\\" in filename:
            return False
        
        # Validate the filename
        validate_path(filename)
        
        # Additional filename-specific checks
        if filename.startswith("."):
            return False  # Hidden files
        
        if len(filename) > 255:  # Common filesystem limit
            return False
        
        # Check for reserved names on Windows
        reserved_names = [
            "CON", "PRN", "AUX", "NUL",
            "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
            "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
        ]
        
        if filename.upper().split(".")[0] in reserved_names:
            return False
        
        return True
    
    except (SecurityError, ValueError):
        return False
