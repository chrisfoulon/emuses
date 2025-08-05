"""
Shell completion for bash, zsh, and powershell.

This module provides comprehensive shell completion functionality including
completion script generation, command and argument completion, and file path
completion with security filtering.

Key Features:
- Completion scripts for bash, zsh, and powershell
- Command and argument completion
- File path completion with security filtering
- Cross-platform compatibility
"""

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import typer
from rich.console import Console


class ShellType(Enum):
    """Enumeration of supported shell types."""

    BASH = "bash"
    ZSH = "zsh"
    POWERSHELL = "powershell"


@dataclass
class CompletionContext:
    """Context information for completion."""

    command: str
    partial: str
    arguments: List[str] = field(default_factory=list)
    current_arg: Optional[str] = None
    position: int = 0


@dataclass
class CommandDefinition:
    """Definition of a command for completion."""

    name: str
    description: str
    arguments: List[str] = field(default_factory=list)
    subcommands: List[str] = field(default_factory=list)
    argument_values: Dict[str, List[str]] = field(default_factory=dict)


class ShellCompletionManager:
    """
    Shell completion manager for CLI applications.

    Manages completion script generation, command registration,
    and completion logic for multiple shell types.

    Attributes
    ----------
    supported_shells : List[Dict[str, str]]
        List of supported shell configurations
    script_generator : CompletionScriptGenerator
        Script generator for different shells
    command_completer : CommandCompleter
        Command completion handler
    file_completer : FilePathCompleter
        File path completion handler
    """

    def __init__(self):
        """
        Initialize the shell completion manager.

        Returns
        -------
        None
        """
        self.supported_shells = [
            {"name": "bash", "description": "Bash shell completion"},
            {"name": "zsh", "description": "Zsh shell completion"},
            {"name": "powershell", "description": "PowerShell completion"},
        ]

        self.script_generator = CompletionScriptGenerator()
        self.command_completer = CommandCompleter()
        self.file_completer = FilePathCompleter()
        self.console = Console()

        # Register default commands
        self._register_default_commands()

    def _register_default_commands(self):
        """
        Register default commands for completion.

        Returns
        -------
        None
        """
        # Register main commands
        self.register_command(
            "process",
            {
                "description": "Process data files",
                "arguments": ["--input", "--output", "--format", "--verbose"],
                "subcommands": [],
                "argument_values": {"--format": ["csv", "json", "parquet"]},
            },
        )

        self.register_command(
            "predict",
            {
                "description": "Make predictions",
                "arguments": ["--model", "--data", "--output"],
                "subcommands": [],
                "argument_values": {},
            },
        )

        self.register_command(
            "visualize",
            {
                "description": "Create visualizations",
                "arguments": ["--data", "--output", "--type"],
                "subcommands": [],
                "argument_values": {"--type": ["scatter", "line", "bar", "histogram"]},
            },
        )

        self.register_command(
            "interactive",
            {
                "description": "Start interactive mode",
                "arguments": ["--workflow"],
                "subcommands": [],
                "argument_values": {
                    "--workflow": ["data_processing", "model_training", "visualization"]
                },
            },
        )

    def get_supported_shells(self) -> List[Dict[str, str]]:
        """
        Get list of supported shells.

        Returns
        -------
        List[Dict[str, str]]
            List of supported shell configurations
        """
        return self.supported_shells.copy()

    def generate_completion_script(self, shell: str) -> str:
        """
        Generate completion script for specified shell.

        Parameters
        ----------
        shell : str
            Shell type (bash, zsh, powershell)

        Returns
        -------
        str
            Generated completion script

        Raises
        ------
        ValueError
            If shell type is not supported
        """
        if shell not in [s["name"] for s in self.supported_shells]:
            raise ValueError(f"Unsupported shell: {shell}")

        if shell == "bash":
            return self.script_generator.generate_bash_script("emuses")
        elif shell == "zsh":
            return self.script_generator.generate_zsh_script("emuses")
        elif shell == "powershell":
            return self.script_generator.generate_powershell_script("emuses")

        return ""

    def install_completion(self, shell: str, install_dir: Optional[str] = None) -> bool:
        """
        Install completion script for specified shell.

        Parameters
        ----------
        shell : str
            Shell type to install completion for
        install_dir : Optional[str], optional
            Directory to install completion script

        Returns
        -------
        bool
            True if installation was successful
        """
        try:
            script = self.generate_completion_script(shell)

            if install_dir is None:
                install_dir = self._get_default_install_dir(shell)

            # Create install directory if it doesn't exist
            Path(install_dir).mkdir(parents=True, exist_ok=True)

            # Write completion script
            script_path = Path(install_dir) / f"emuses_{shell}_completion"
            script_path.write_text(script)

            return True

        except Exception:
            return False

    def _get_default_install_dir(self, shell: str) -> str:
        """
        Get default installation directory for shell.

        Parameters
        ----------
        shell : str
            Shell type

        Returns
        -------
        str
            Default installation directory
        """
        home = Path.home()

        if shell == "bash":
            return str(home / ".bash_completion.d")
        elif shell == "zsh":
            return str(home / ".zsh" / "completions")
        elif shell == "powershell":
            return str(home / "Documents" / "PowerShell" / "Completions")

        return str(home / ".completions")

    def register_command(self, name: str, definition: Dict[str, Any]):
        """
        Register a command for completion.

        Parameters
        ----------
        name : str
            Command name
        definition : Dict[str, Any]
            Command definition with arguments and options

        Returns
        -------
        None
        """
        self.script_generator.register_command(name, definition)
        self.command_completer.register_command(name, definition.get("arguments", []))

        # Register argument values
        for arg, values in definition.get("argument_values", {}).items():
            self.command_completer.register_argument_values(name, arg, values)

    def get_command_completions(self, partial: str) -> List[str]:
        """
        Get command completions for partial input.

        Parameters
        ----------
        partial : str
            Partial command input

        Returns
        -------
        List[str]
            List of matching commands
        """
        return self.command_completer.complete_command(partial)

    def get_argument_completions(self, command: str, partial: str) -> List[str]:
        """
        Get argument completions for command.

        Parameters
        ----------
        command : str
            Command name
        partial : str
            Partial argument input

        Returns
        -------
        List[str]
            List of matching arguments
        """
        return self.command_completer.complete_arguments(command, partial)

    def get_file_completions(self, partial: str, **kwargs) -> List[str]:
        """
        Get file path completions.

        Parameters
        ----------
        partial : str
            Partial file path
        **kwargs
            Additional completion options

        Returns
        -------
        List[str]
            List of matching file paths
        """
        return self.file_completer.complete_path(partial, **kwargs)


class CompletionScriptGenerator:
    """
    Completion script generator for different shells.

    Generates shell-specific completion scripts with command
    and argument completion support.

    Attributes
    ----------
    shell_templates : Dict[str, str]
        Shell-specific completion templates
    command_registry : Dict[str, CommandDefinition]
        Registry of registered commands
    """

    def __init__(self):
        """
        Initialize the completion script generator.

        Returns
        -------
        None
        """
        self.shell_templates = {}
        self.command_registry = {}
        self._load_templates()

    def _load_templates(self):
        """
        Load completion script templates.

        Returns
        -------
        None
        """
        # Bash template
        self.shell_templates[
            "bash"
        ] = """
# Bash completion for {program}
_{program}_completion() {{
    local cur prev opts
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"

    # Get available commands
    commands="{commands}"

    # Command completion
    if [[ ${{COMP_CWORD}} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
        return 0
    fi

    # Argument completion based on command
    cmd="${{COMP_WORDS[1]}}"
    case "$cmd" in
{command_cases}
    esac

    return 0
}}

complete -F _{program}_completion {program}
"""

        # Zsh template
        self.shell_templates[
            "zsh"
        ] = """
#compdef {program}

_{program}() {{
    local context state line
    local -a commands

    commands=(
{command_list}
    )

    _arguments -C \\
        '1: :->command' \\
        '*: :->args' && return 0

    case $state in
        command)
            _describe 'commands' commands
            ;;
        args)
            case $line[1] in
{argument_cases}
            esac
            ;;
    esac
}}

_{program} "$@"
"""

        # PowerShell template
        self.shell_templates[
            "powershell"
        ] = """
# PowerShell completion for {program}
Register-ArgumentCompleter -Native -CommandName {program} -ScriptBlock {{
    param($wordToComplete, $commandAst, $cursorPosition)

    $commands = @({command_array})

    # Get the current command line
    $line = $commandAst.CommandElements

    if ($line.Count -eq 1) {{
        # Complete command names
        $commands | Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
            New-Object System.Management.Automation.CompletionResult $_, $_, 'ParameterValue', $_
        }}
    }} else {{
        # Complete arguments for specific commands
        $cmd = $line[1].Value
        switch ($cmd) {{
{powershell_cases}
        }}
    }}
}}
"""

    def register_command(self, name: str, definition: Dict[str, Any]):
        """
        Register a command with completion definition.

        Parameters
        ----------
        name : str
            Command name
        definition : Dict[str, Any]
            Command definition

        Returns
        -------
        None
        """
        self.command_registry[name] = CommandDefinition(
            name=name,
            description=definition.get("description", ""),
            arguments=definition.get("arguments", []),
            subcommands=definition.get("subcommands", []),
            argument_values=definition.get("argument_values", {}),
        )

    def get_registered_commands(self) -> Dict[str, CommandDefinition]:
        """
        Get all registered commands.

        Returns
        -------
        Dict[str, CommandDefinition]
            Dictionary of registered commands
        """
        return self.command_registry.copy()

    def generate_bash_script(self, program: str) -> str:
        """
        Generate bash completion script.

        Parameters
        ----------
        program : str
            Program name

        Returns
        -------
        str
            Bash completion script
        """
        commands = " ".join(self.command_registry.keys())
        command_cases = []

        for cmd_name, cmd_def in self.command_registry.items():
            if cmd_def.arguments:
                args = " ".join(cmd_def.arguments)
                case_block = f"""        {cmd_name})
            COMPREPLY=( $(compgen -W "{args}" -- "$cur") )
            ;;"""
                command_cases.append(case_block)

        return self.shell_templates["bash"].format(
            program=program, commands=commands, command_cases="\\n".join(command_cases)
        )

    def generate_zsh_script(self, program: str) -> str:
        """
        Generate zsh completion script.

        Parameters
        ----------
        program : str
            Program name

        Returns
        -------
        str
            Zsh completion script
        """
        command_list = []
        argument_cases = []

        for cmd_name, cmd_def in self.command_registry.items():
            command_list.append(f'        "{cmd_name}:{cmd_def.description}"')

            if cmd_def.arguments:
                args = " ".join([f"'{arg}'" for arg in cmd_def.arguments])
                case_block = f"""                {cmd_name})
                    _arguments {args}
                    ;;"""
                argument_cases.append(case_block)

        return self.shell_templates["zsh"].format(
            program=program,
            command_list="\\n".join(command_list),
            argument_cases="\\n".join(argument_cases),
        )

    def generate_powershell_script(self, program: str) -> str:
        """
        Generate PowerShell completion script.

        Parameters
        ----------
        program : str
            Program name

        Returns
        -------
        str
            PowerShell completion script
        """
        command_array = ", ".join([f'"{cmd}"' for cmd in self.command_registry.keys()])
        powershell_cases = []

        for cmd_name, cmd_def in self.command_registry.items():
            if cmd_def.arguments:
                args = ", ".join([f'"{arg}"' for arg in cmd_def.arguments])
                case_block = f"""            "{cmd_name}" {{
                @({args}) | Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
                    New-Object System.Management.Automation.CompletionResult $_, $_, 'ParameterValue', $_
                }}
            }}"""
                powershell_cases.append(case_block)

        return self.shell_templates["powershell"].format(
            program=program,
            command_array=command_array,
            powershell_cases="\\n".join(powershell_cases),
        )


class CommandCompleter:
    """
    Command completion handler.

    Handles completion for command names, arguments, and argument values
    with contextual awareness and caching.

    Attributes
    ----------
    commands : Dict[str, List[str]]
        Registered commands and their arguments
    arguments : Dict[str, Dict[str, List[str]]]
        Command arguments and their possible values
    completion_cache : Dict[str, List[str]]
        Cache for completion results
    """

    def __init__(self):
        """
        Initialize the command completer.

        Returns
        -------
        None
        """
        self.commands = {}
        self.arguments = {}
        self.completion_cache = {}

    def register_command(self, name: str, arguments: Optional[List[str]] = None):
        """
        Register a command with its arguments.

        Parameters
        ----------
        name : str
            Command name
        arguments : Optional[List[str]], optional
            List of command arguments

        Returns
        -------
        None
        """
        self.commands[name] = arguments or []
        if name not in self.arguments:
            self.arguments[name] = {}

    def register_argument_values(self, command: str, argument: str, values: List[str]):
        """
        Register possible values for a command argument.

        Parameters
        ----------
        command : str
            Command name
        argument : str
            Argument name
        values : List[str]
            Possible argument values

        Returns
        -------
        None
        """
        if command not in self.arguments:
            self.arguments[command] = {}

        self.arguments[command][argument] = values

    def complete_command(self, partial: str) -> List[str]:
        """
        Complete command names.

        Parameters
        ----------
        partial : str
            Partial command input

        Returns
        -------
        List[str]
            List of matching commands
        """
        cache_key = f"cmd:{partial}"
        if cache_key in self.completion_cache:
            return self.completion_cache[cache_key]

        matches = [cmd for cmd in self.commands.keys() if cmd.startswith(partial)]
        self.completion_cache[cache_key] = matches
        return matches

    def complete_arguments(self, command: str, partial: str) -> List[str]:
        """
        Complete command arguments.

        Parameters
        ----------
        command : str
            Command name
        partial : str
            Partial argument input

        Returns
        -------
        List[str]
            List of matching arguments
        """
        cache_key = f"arg:{command}:{partial}"
        if cache_key in self.completion_cache:
            return self.completion_cache[cache_key]

        if command not in self.commands:
            return []

        matches = [arg for arg in self.commands[command] if arg.startswith(partial)]
        self.completion_cache[cache_key] = matches
        return matches

    def complete_argument_values(
        self, command: str, argument: str, partial: str
    ) -> List[str]:
        """
        Complete argument values.

        Parameters
        ----------
        command : str
            Command name
        argument : str
            Argument name
        partial : str
            Partial value input

        Returns
        -------
        List[str]
            List of matching values
        """
        cache_key = f"val:{command}:{argument}:{partial}"
        if cache_key in self.completion_cache:
            return self.completion_cache[cache_key]

        if command not in self.arguments or argument not in self.arguments[command]:
            return []

        values = self.arguments[command][argument]
        matches = [val for val in values if val.startswith(partial)]
        self.completion_cache[cache_key] = matches
        return matches

    def get_completions(self, context: Dict[str, Any]) -> List[str]:
        """
        Get completions based on context.

        Parameters
        ----------
        context : Dict[str, Any]
            Completion context

        Returns
        -------
        List[str]
            List of completions
        """
        command = context.get("command", "")
        partial = context.get("partial", "")

        if not command:
            return self.complete_command(partial)

        return self.complete_arguments(command, partial)


class FilePathCompleter:
    """
    File path completion handler.

    Provides secure file path completion with extension filtering,
    directory navigation, and security validation.

    Attributes
    ----------
    allowed_extensions : List[str]
        List of allowed file extensions
    base_directory : Optional[str]
        Base directory for relative path completion
    security_patterns : List[str]
        Patterns to filter for security
    """

    def __init__(self, base_directory: Optional[str] = None):
        """
        Initialize the file path completer.

        Parameters
        ----------
        base_directory : Optional[str], optional
            Base directory for relative paths

        Returns
        -------
        None
        """
        self.allowed_extensions = [
            ".txt",
            ".csv",
            ".json",
            ".xml",
            ".yaml",
            ".yml",
            ".parquet",
        ]
        self.base_directory = base_directory
        self.security_patterns = [
            r"\.\./",  # Path traversal
            r"\.\.\\\\",  # Windows path traversal
            r"^/etc/",  # System directories
            r"^/sys/",
            r"^/proc/",
            r"^C:\\\\Windows",
            r"^C:\\\\System32",
        ]

    def complete_path(self, partial_path: str, **kwargs) -> List[str]:
        """
        Complete file paths with filtering.

        Parameters
        ----------
        partial_path : str
            Partial file path to complete
        **kwargs
            Additional completion options

        Returns
        -------
        List[str]
            List of matching file paths
        """
        allowed_extensions = kwargs.get("allowed_extensions", self.allowed_extensions)
        directories_only = kwargs.get("directories_only", False)
        security_filter = kwargs.get("security_filter", True)

        # Security filtering
        if security_filter and self._is_security_risk(partial_path):
            return []

        # Expand path
        if partial_path.startswith("~"):
            partial_path = os.path.expanduser(partial_path)

        # Handle relative paths
        if not os.path.isabs(partial_path) and self.base_directory:
            partial_path = os.path.join(self.base_directory, partial_path)

        # Split into directory and filename parts
        if os.path.isdir(partial_path):
            search_dir = partial_path
            partial_name = ""
        else:
            search_dir = os.path.dirname(partial_path) or "."
            partial_name = os.path.basename(partial_path)

        # Find matching files/directories
        matches = []

        try:
            if os.path.exists(search_dir):
                for item in os.listdir(search_dir):
                    if item.startswith(partial_name):
                        full_path = os.path.join(search_dir, item)

                        # Directory filtering
                        if directories_only and not os.path.isdir(full_path):
                            continue

                        # Extension filtering
                        if not directories_only and allowed_extensions:
                            if os.path.isfile(full_path):
                                ext = os.path.splitext(item)[1].lower()
                                if ext not in [e.lower() for e in allowed_extensions]:
                                    continue

                        # Security filtering
                        if security_filter and self._is_security_risk(full_path):
                            continue

                        matches.append(full_path)

        except (OSError, PermissionError):
            # Handle permission errors gracefully
            pass

        return sorted(matches)

    def _is_security_risk(self, path: str) -> bool:
        """
        Check if path poses security risk.

        Parameters
        ----------
        path : str
            Path to check

        Returns
        -------
        bool
            True if path is a security risk
        """
        for pattern in self.security_patterns:
            if re.search(pattern, path):
                return True

        return False
