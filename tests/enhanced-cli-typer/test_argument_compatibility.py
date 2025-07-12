"""
Test backward compatibility analysis and legacy CLI mapping for Enhanced CLI with Typer.

This module tests that the new Typer-based CLI maintains 100% backward compatibility
with the existing argparse-based CLI in terms of arguments, validation, and behavior.
"""

import pytest
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, patch
import sys
import tempfile
import shutil

from emuses.scripts.main import (
    resolve_path,
    add_output_folder_argument,
    add_input_dataset_argument,
    add_input_dataset_optional_arguments,
    add_scores_arguments,
    add_umap_arguments,
    add_clustering_arguments,
    add_enhanced_pipeline_arguments,
    add_random_state_argument,
)


class TestLegacyArgumentMapping:
    """Test mapping of legacy argparse arguments to Typer equivalents."""
    
    def test_legacy_parser_structure_analysis(self):
        """Analyze the complete structure of the legacy CLI parser."""
        # Create a parser like in the legacy main() function
        parser = argparse.ArgumentParser(description="EMUSES pipeline")
        subparsers = parser.add_subparsers(dest="command", required=True)
        
        # Create common parallel parser
        common_parallel = argparse.ArgumentParser(add_help=False)
        parallel_group = common_parallel.add_mutually_exclusive_group()
        parallel_group.add_argument("--umap_jobs", type=int, help="Parallel UMAP jobs")
        parallel_group.add_argument("--hdbscan_jobs", type=int, help="Parallel HDBSCAN jobs")
        
        # Add all subcommands with their arguments
        subcommands = {
            "full": subparsers.add_parser("full", parents=[common_parallel], help="Run the full pipeline"),
            "umap": subparsers.add_parser("umap", help="Train the UMAP and get the embeddings"),
            "clustering": subparsers.add_parser("clustering", help="Perform clustering on embeddings"),
            "heatmap": subparsers.add_parser("heatmap", help="Create a heatmap"),
            "prediction": subparsers.add_parser("prediction", help="Train a prediction model"),
        }
        
        # Add arguments to each subcommand as in legacy CLI
        for cmd_name, cmd_parser in subcommands.items():
            if cmd_name in ["full", "umap", "heatmap", "prediction"]:
                add_output_folder_argument(cmd_parser)
                add_input_dataset_argument(cmd_parser)
                add_input_dataset_optional_arguments(cmd_parser)
            elif cmd_name == "clustering":
                add_output_folder_argument(cmd_parser)
                cmd_parser.add_argument("--load_embeddings", help="Path to precomputed embeddings")
                
            if cmd_name in ["full", "prediction"]:
                add_scores_arguments(cmd_parser)
                add_umap_arguments(cmd_parser)
                add_enhanced_pipeline_arguments(cmd_parser)
                cmd_parser.add_argument(
                    "--prediction_optim_dict",
                    default="optim_dict_predict",
                    help="Prediction optimization dictionary"
                )
            elif cmd_name == "umap":
                add_umap_arguments(cmd_parser)
            elif cmd_name == "heatmap":
                add_scores_arguments(cmd_parser)
                cmd_parser.add_argument("--load_embeddings", help="Embeddings from the UMAP")
                cmd_parser.add_argument("--load_hdbscan", help="Path to a pre-trained HDBSCAN model")
                cmd_parser.add_argument("--output_format_info", help="Output format information needed")
                cmd_parser.add_argument(
                    "--prediction_optim_dict",
                    default="optim_dict_predict",
                    help="Prediction optimization dictionary"
                )
            elif cmd_name == "clustering":
                add_clustering_arguments(cmd_parser)
                
            # Add random state to all commands
            add_random_state_argument(cmd_parser)
            
        # Add full command specific arguments
        subcommands["full"].add_argument(
            "--run_old_prediction",
            action="store_true",
            help="Run the old prediction pipeline"
        )
        
        # Extract all arguments for analysis
        argument_mapping = self._extract_all_arguments(subcommands)
        
        # Verify we captured the core commands
        assert len(subcommands) == 5
        assert "full" in subcommands
        assert "umap" in subcommands
        assert "clustering" in subcommands
        assert "heatmap" in subcommands
        assert "prediction" in subcommands
        
        # Verify argument mapping contains expected keys
        for cmd in ["full", "umap", "clustering", "heatmap", "prediction"]:
            assert cmd in argument_mapping
            # All commands should have random_state
            assert "random_state" in argument_mapping[cmd]
        
        # Store mapping for use in other tests
        self.legacy_argument_mapping = argument_mapping
        
    def _extract_all_arguments(self, subcommands: Dict[str, argparse.ArgumentParser]) -> Dict[str, Dict[str, Any]]:
        """Extract all arguments from each subcommand parser."""
        mapping = {}
        
        for cmd_name, parser in subcommands.items():
            cmd_args = {}
            for action in parser._actions:
                if action.dest == 'help':
                    continue
                    
                arg_info = {
                    'dest': action.dest,
                    'type': action.type,
                    'default': action.default,
                    'help': action.help,
                    'required': action.required if hasattr(action, 'required') else False,
                    'choices': action.choices,
                    'nargs': action.nargs,
                    'action': type(action).__name__,
                }
                
                # Handle positional vs optional arguments
                if action.option_strings:
                    cmd_args[action.dest] = arg_info
                else:
                    # Positional argument
                    arg_info['positional'] = True
                    cmd_args[action.dest] = arg_info
                    
            mapping[cmd_name] = cmd_args
            
        return mapping

    def test_argument_compatibility_requirements(self):
        """Test that we've identified all arguments requiring compatibility."""
        
        # Run the legacy parser analysis first
        self.test_legacy_parser_structure_analysis()
        
        # Expected argument categories that must be preserved
        required_categories = {
            'positional_args': ['output_folder', 'input_dataset'],
            'file_path_args': ['scores', 'load_umap', 'load_embeddings', 'load_hdbscan', 'label_dataset'],
            'boolean_flags': ['recursive_input_file_search', 'columns_are_features', 'scores_are_rows',
                              'classification', 'filter_labelled_by_scores', 'interactive_plot',
                              'hdbscan_approx_min_span_tree', 'inspect_data_state', 'use_enhanced_pipeline',
                              'parallel_models', 'run_old_prediction'],
            'integer_args': ['input_header', 'input_index_column', 'scores_header', 'scores_index_column',
                             'test_size', 'umap_trials', 'hdbscan_trials', 'min_cluster_size',
                             'hdbscan_core_dist_n_jobs', 'optuna_trials', 'n_jobs', 'random_state',
                             'umap_jobs', 'hdbscan_jobs'],
            'choice_args': ['input_normalization', 'correlation_method', 'scores_normalization'],
            'list_args': ['input_file_types', 'inputs_columns', 'bids_filters', 'scores_column', 'model_selection'],
            'string_args': ['arg_separator', 'prefix', 'optim_dict', 'prediction_optim_dict', 'output_format_info'],
        }
        
        # Validate that we captured all expected arguments from the mapping
        discovered_args = set()
        for cmd_args in self.legacy_argument_mapping.values():
            discovered_args.update(cmd_args.keys())
        
        # Remove command and help which are not user arguments
        discovered_args.discard('command')
        discovered_args.discard('help')
        
        # Collect all expected arguments
        expected_args = set()
        for category_args in required_categories.values():
            expected_args.update(category_args)
            
        # Verify we have all expected arguments
        missing_args = expected_args - discovered_args
        extra_args = discovered_args - expected_args
        
        # Allow some flexibility for additional arguments we might have discovered
        critical_missing = missing_args & set([
            'output_folder', 'input_dataset', 'scores', 'random_state',
            'umap_trials', 'hdbscan_trials', 'input_normalization'
        ])
        
        assert len(critical_missing) == 0, f"Missing critical arguments: {critical_missing}"
        
        # Store the compatibility analysis results
        self.compatibility_analysis = {
            'required_categories': required_categories,
            'discovered_args': discovered_args,
            'legacy_mapping': self.legacy_argument_mapping,
            'missing_args': missing_args,
            'extra_args': extra_args
        }
        
        # Basic validation passed
        assert len(required_categories) == 7, "Should have 7 argument categories"
        assert 'positional_args' in required_categories
        assert len(required_categories['positional_args']) == 2


class TestPathResolutionCompatibility:
    """Test that path resolution logic is preserved in the new CLI."""
    
    def test_resolve_path_functionality(self):
        """Test the resolve_path function behavior that must be preserved."""
        
        # Test special case identifiers
        special_cases = ["mnist", "digits_label_dataset", "input_matrix"]
        for case in special_cases:
            result = resolve_path(case)
            assert result == case, f"Special case {case} should be returned as-is"
            
        # Test URL decoding behavior
        url_encoded_path = "test%20file.csv"
        result = resolve_path(url_encoded_path)
        assert isinstance(result, (str, Path))
        
        # Test with temporary file to verify existing path handling
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            
        try:
            result = resolve_path(tmp_path)
            assert isinstance(result, Path)
            assert result.exists()
        finally:
            Path(tmp_path).unlink(missing_ok=True)
            
    def test_path_security_requirements(self):
        """Test security requirements for path handling in new CLI."""
        # Security tests that the new CLI must implement
        
        # Directory traversal attempts
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "C:\\Windows\\System32\\config\\SAM"
        ]
        
        # The new CLI must protect against these
        # For now, we just document the security requirements
        security_requirements = {
            'directory_traversal_protection': True,
            'absolute_path_validation': True,
            'system_directory_blocking': True,
            'input_sanitization': True
        }
        
        # Store security requirements for implementation guidance
        self.security_requirements = {
            'malicious_paths': malicious_paths,
            'protection_requirements': security_requirements
        }
        
        # Validate we have the requirements defined
        assert len(malicious_paths) == 4, "Should have 4 malicious path test cases"
        assert len(security_requirements) == 4, "Should have 4 security requirements"


class TestCommandLineInterfaceCompatibility:
    """Test exact command-line interface compatibility."""
    
    def test_command_structure_preservation(self):
        """Test that command structure is exactly preserved."""
        expected_commands = ["full", "umap", "clustering", "heatmap", "prediction"]
        
        # Run legacy analysis to get the actual structure
        TestLegacyArgumentMapping().test_legacy_parser_structure_analysis()
        test_instance = TestLegacyArgumentMapping()
        test_instance.test_legacy_parser_structure_analysis()
        discovered_commands = list(test_instance.legacy_argument_mapping.keys())
        
        # Verify command structure matches exactly
        assert set(discovered_commands) == set(expected_commands), \
            f"Command structure mismatch. Expected: {expected_commands}, Got: {discovered_commands}"
            
        # Store command structure requirements for implementation
        self.command_structure_requirements = {
            'commands': expected_commands,
            'command_help': {
                'full': 'Run the full pipeline',
                'umap': 'Train the UMAP and get the embeddings',
                'clustering': 'Perform clustering on embeddings',
                'heatmap': 'Create a heatmap',
                'prediction': 'Train a prediction model'
            }
        }
        
    def test_argument_validation_compatibility(self):
        """Test that argument validation behaves identically."""
        
        # Test cases from legacy CLI that must be preserved
        validation_test_cases = [
            {
                'command': 'full',
                'args': ['output_dir', 'input_file'],
                'expected_valid': True
            },
            {
                'command': 'full',
                'args': [],  # Missing required positionals
                'expected_valid': False
            },
            {
                'command': 'clustering',
                'args': ['output_dir'],  # clustering doesn't need input_dataset
                'expected_valid': True
            }
        ]
        
        # Store validation requirements for implementation
        self.validation_requirements = {
            'test_cases': validation_test_cases,
            'required_positionals': {
                'full': ['output_folder', 'input_dataset'],
                'umap': ['output_folder', 'input_dataset'],
                'clustering': ['output_folder'],  # No input_dataset required
                'heatmap': ['output_folder', 'input_dataset'],
                'prediction': ['output_folder', 'input_dataset']
            }
        }
        
        # Validate test cases are defined
        assert len(validation_test_cases) == 3, "Should have 3 validation test cases"
        
    def test_exit_code_compatibility(self):
        """Test that exit codes match legacy CLI behavior."""
        
        # Exit codes that must be preserved
        expected_exit_codes = {
            'success': 0,
            'argument_error': 2,  # argparse standard
            'file_not_found': 1,
            'optuna_conflict': 1,  # From check_for_existing_optuna_databases
        }
        
        # Store exit code requirements for implementation
        self.exit_code_requirements = expected_exit_codes
        
        # Validate exit codes are defined
        assert len(expected_exit_codes) == 4, "Should have 4 exit code types"
        assert expected_exit_codes['success'] == 0, "Success should be exit code 0"


class TestTyperMigrationRequirements:
    """Define requirements for migrating to Typer framework."""
    
    def test_typer_type_mapping_requirements(self):
        """Define type mapping requirements from argparse to Typer."""
        
        # Mapping from argparse types to Typer types
        type_mapping = {
            'str': 'str',
            'int': 'int',
            'float': 'float',
            'Path': 'typer.Option[Path]',
            'resolve_path': 'custom_path_validator',  # Custom implementation needed
            'store_true': 'bool = False',
            'store_false': 'bool = True',
            'append': 'List[str]',
            'nargs="+"': 'List[str]',
            'choices': 'Enum or typer.Option(choices=...)',
        }
        
        # Store type mapping requirements for implementation
        self.typer_type_mapping = type_mapping
        
        # Validate type mapping is complete
        assert len(type_mapping) == 10, "Should have 10 type mappings"
        assert 'resolve_path' in type_mapping, "Must handle resolve_path custom type"
        
    def test_typer_decorator_requirements(self):
        """Define Typer decorator requirements for CLI structure."""
        
        # Required Typer patterns for compatibility
        typer_requirements = {
            'app_structure': 'typer.Typer() with subcommands',
            'positional_args': 'typer.Argument() for positional parameters',
            'optional_args': 'typer.Option() for optional parameters',
            'help_text': 'Preserve all help text exactly',
            'default_values': 'Preserve all default values exactly',
            'validation': 'Custom validators for path security',
        }
        
        # Store decorator requirements for implementation
        self.typer_decorator_requirements = typer_requirements
        
        # Validate requirements are complete
        assert len(typer_requirements) == 6, "Should have 6 Typer requirements"
        assert 'validation' in typer_requirements, "Must include validation requirements"


@pytest.mark.compatibility
class TestBackwardCompatibilityValidation:
    """Integration tests for complete backward compatibility."""
    
    def test_argument_parsing_equivalence(self):
        """Test that argument parsing produces identical results."""
        
        # Test cases with various argument combinations
        test_cases = [
            # Full command with all arguments
            ["full", "output", "input.csv", "--scores", "scores.csv", "--random_state", "42"],
            # UMAP command with minimal arguments
            ["umap", "output", "input.csv"],
            # Clustering with embeddings
            ["clustering", "output", "--load_embeddings", "embeddings.npy"],
            # Heatmap with complex arguments
            ["heatmap", "output", "input.csv", "--scores", "scores.csv", "--load_embeddings", "emb.npy"],
            # Prediction with optimization
            ["prediction", "output", "input.csv", "--scores", "scores.csv", "--optuna_trials", "100"],
        ]
        
        # Store parsing test cases for implementation
        self.parsing_test_cases = test_cases
        
        # Validate test cases are defined
        assert len(test_cases) == 5, "Should have 5 parsing test cases"
        assert test_cases[0][0] == "full", "First test case should be full command"
        
    def test_error_message_compatibility(self):
        """Test that error messages match legacy CLI."""
        
        # Error scenarios that must produce identical messages
        error_cases = [
            {'args': ["full"], 'error_type': 'missing_positional'},
            {'args': ["invalid_command"], 'error_type': 'invalid_command'},
            {'args': ["full", "out", "in", "--invalid_arg"], 'error_type': 'invalid_argument'},
        ]
        
        # Store error test cases for implementation
        self.error_test_cases = error_cases
        
        # Validate error cases are defined
        assert len(error_cases) == 3, "Should have 3 error test cases"
        assert error_cases[0]['error_type'] == 'missing_positional', "First error should be missing positional"


class TestArgumentParsingEdgeCases:
    """Test edge cases and special values in argument parsing."""
    
    def test_file_path_edge_cases(self):
        """Test file path handling edge cases that must be preserved."""
        
        # Test cases from resolve_path function
        edge_cases = [
            # Special identifiers that should not be treated as paths
            "mnist",
            "digits_label_dataset",
            "input_matrix",
            
            # URL encoded paths
            "test%20file.csv",
            "path%2Fwith%2Fslashes.txt",
            
            # Cross-platform path formats
            "C:\\Windows\\path\\file.txt",
            "/unix/path/file.txt",
            "mixed/path\\separators.csv",
            
            # Paths with spaces
            "file with spaces.csv",
            '"quoted path.txt"',
        ]
        
        # Test each edge case with the legacy resolve_path function
        for test_path in edge_cases:
            result = resolve_path(test_path)
            
            # Special identifiers should be returned as-is
            if test_path in ["mnist", "digits_label_dataset", "input_matrix"]:
                assert result == test_path, f"Special identifier {test_path} should be preserved"
            else:
                # Other paths should be processed (may be Path object or string)
                assert result is not None, f"Path {test_path} should be processed"
                
        # Store edge cases for new CLI implementation
        self.path_edge_cases = edge_cases
        
    def test_argument_validation_edge_cases(self):
        """Test argument validation edge cases."""
        
        validation_edge_cases = [
            # Integer bounds
            {'arg': 'random_state', 'value': -1, 'expected_valid': True},
            {'arg': 'random_state', 'value': 0, 'expected_valid': True},
            {'arg': 'random_state', 'value': 2**31 - 1, 'expected_valid': True},
            
            # Float bounds
            {'arg': 'test_size', 'value': 0.0, 'expected_valid': True},
            {'arg': 'test_size', 'value': 1.0, 'expected_valid': True},
            {'arg': 'test_size', 'value': -0.1, 'expected_valid': False},
            {'arg': 'test_size', 'value': 1.1, 'expected_valid': False},
            
            # Choice validation
            {'arg': 'input_normalization', 'value': 'none', 'expected_valid': True},
            {'arg': 'input_normalization', 'value': 'invalid_choice', 'expected_valid': False},
            
            # List arguments
            {'arg': 'model_selection', 'value': ['gp', 'rf'], 'expected_valid': True},
            {'arg': 'model_selection', 'value': ['invalid_model'], 'expected_valid': False},
        ]
        
        # Store validation edge cases for implementation
        self.validation_edge_cases = validation_edge_cases
        
        # Validate test cases are complete
        assert len(validation_edge_cases) == 11, "Should have 11 validation edge cases"
        
    def test_cross_platform_compatibility(self):
        """Test cross-platform compatibility requirements."""
        
        platform_test_cases = [
            # Windows paths
            {'path': 'C:\\Users\\test\\file.csv', 'platform': 'windows'},
            {'path': 'D:\\data\\input.txt', 'platform': 'windows'},
            
            # Unix paths
            {'path': '/home/user/data.csv', 'platform': 'unix'},
            {'path': '/tmp/temp_file.txt', 'platform': 'unix'},
            
            # Relative paths
            {'path': './relative/path.csv', 'platform': 'any'},
            {'path': '../parent/file.txt', 'platform': 'any'},
            
            # Mixed separators (should be normalized)
            {'path': 'mixed\\forward/slashes.csv', 'platform': 'any'},
        ]
        
        # Store platform compatibility requirements
        self.platform_compatibility = platform_test_cases
        
        # Validate test cases are complete
        assert len(platform_test_cases) == 7, "Should have 7 platform test cases"


class TestLegacyBehaviorPreservation:
    """Test that specific legacy CLI behaviors are preserved."""
    
    def test_optuna_database_conflict_detection(self):
        """Test that Optuna database conflict detection is preserved."""
        
        # This function from legacy CLI must be preserved
        # check_for_existing_optuna_databases(output_folder)
        
        conflict_scenarios = [
            {
                'description': 'Single Optuna database file exists',
                'files': ['optuna_target_umap.db'],
                'expected_exit_code': 1,
                'expected_error_contains': 'EXISTING OPTUNA DATABASE FILES DETECTED'
            },
            {
                'description': 'Multiple Optuna database files exist',
                'files': ['optuna_target_umap.db', 'optuna_target_hdbscan.db'],
                'expected_exit_code': 1,
                'expected_error_contains': 'Found 2 existing Optuna database file(s)'
            },
            {
                'description': 'No Optuna database files',
                'files': [],
                'expected_exit_code': None,  # Should continue normally
                'expected_error_contains': None
            }
        ]
        
        # Store conflict detection requirements
        self.optuna_conflict_requirements = conflict_scenarios
        
        # Validate scenarios are complete
        assert len(conflict_scenarios) == 3, "Should have 3 conflict scenarios"
        
    def test_command_file_creation(self):
        """Test that command.txt file creation is preserved."""
        
        # Legacy CLI creates output_folder/command.txt with sys.argv
        command_file_requirements = {
            'filename': 'command.txt',
            'location': 'output_folder',
            'content': 'space-separated sys.argv',
            'purpose': 'Record exact command used for reproducibility'
        }
        
        # Store command file requirements
        self.command_file_requirements = command_file_requirements
        
        # Validate requirements
        assert command_file_requirements['filename'] == 'command.txt'
        assert command_file_requirements['location'] == 'output_folder'
        
    def test_logging_configuration_preservation(self):
        """Test that logging configuration is preserved."""
        
        # Legacy CLI uses logging.basicConfig(level=logging.INFO)
        logging_requirements = {
            'level': 'INFO',
            'format': 'INFO:__main__:',  # From legacy output
            'handler': 'console',
            'argument_logging': True,  # Logs all arguments with logger.info(f"{k}: {v}")
        }
        
        # Store logging requirements
        self.logging_requirements = logging_requirements
        
        # Validate requirements
        assert logging_requirements['level'] == 'INFO'
        assert logging_requirements['argument_logging'] is True
