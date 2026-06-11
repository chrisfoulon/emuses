"""
Unit tests for spreadsheet_separator parameter in spreadsheet_to_input_df.

Tests various CSV separators (comma, semicolon, tab, pipe) and ensures
backward compatibility with default comma separator.
"""

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from emuses.tools.inputs_utils import spreadsheet_to_input_df


@pytest.fixture
def comma_csv(tmp_path):
    """Create a comma-separated CSV file."""
    csv_path = tmp_path / "data_comma.csv"
    csv_path.write_text("col1,col2,col3\n1,2,3\n4,5,6\n7,8,9")
    return csv_path


@pytest.fixture
def semicolon_csv(tmp_path):
    """Create a semicolon-separated CSV file (European format)."""
    csv_path = tmp_path / "data_semicolon.csv"
    csv_path.write_text("col1;col2;col3\n1;2;3\n4;5;6\n7;8;9")
    return csv_path


@pytest.fixture
def tab_csv(tmp_path):
    """Create a tab-separated CSV file."""
    csv_path = tmp_path / "data_tab.csv"
    csv_path.write_text("col1\tcol2\tcol3\n1\t2\t3\n4\t5\t6\n7\t8\t9")
    return csv_path


@pytest.fixture
def pipe_csv(tmp_path):
    """Create a pipe-separated CSV file."""
    csv_path = tmp_path / "data_pipe.csv"
    csv_path.write_text("col1|col2|col3\n1|2|3\n4|5|6\n7|8|9")
    return csv_path


@pytest.fixture
def excel_file(tmp_path):
    """Create an Excel file."""
    excel_path = tmp_path / "data.xlsx"
    df = pd.DataFrame({
        'col1': [1, 4, 7],
        'col2': [2, 5, 8],
        'col3': [3, 6, 9]
    })
    df.to_excel(excel_path, index=False)
    return excel_path


def test_default_comma_separator(comma_csv):
    """Test default comma separator (backward compatibility)."""
    df = spreadsheet_to_input_df(comma_csv, header=0, columns_are_features=True)

    # Should have 3 rows (data) and 3 columns (features)
    assert df.shape == (3, 3)
    assert list(df.columns) == ['col1', 'col2', 'col3']
    assert df['col1'].tolist() == [1, 4, 7]


def test_explicit_comma_separator(comma_csv):
    """Test explicitly setting comma separator."""
    df = spreadsheet_to_input_df(
        comma_csv,
        header=0,
        columns_are_features=True,
        spreadsheet_separator=","
    )

    assert df.shape == (3, 3)
    assert df['col1'].tolist() == [1, 4, 7]


def test_semicolon_separator(semicolon_csv):
    """Test semicolon separator (European CSV format)."""
    df = spreadsheet_to_input_df(
        semicolon_csv,
        header=0,
        columns_are_features=True,
        spreadsheet_separator=";"
    )

    assert df.shape == (3, 3)
    assert list(df.columns) == ['col1', 'col2', 'col3']
    assert df['col1'].tolist() == [1, 4, 7]


def test_tab_separator(tab_csv):
    """Test tab separator."""
    df = spreadsheet_to_input_df(
        tab_csv,
        header=0,
        columns_are_features=True,
        spreadsheet_separator="\t"
    )

    assert df.shape == (3, 3)
    assert list(df.columns) == ['col1', 'col2', 'col3']
    assert df['col1'].tolist() == [1, 4, 7]


def test_pipe_separator(pipe_csv):
    """Test pipe separator."""
    df = spreadsheet_to_input_df(
        pipe_csv,
        header=0,
        columns_are_features=True,
        spreadsheet_separator="|"
    )

    assert df.shape == (3, 3)
    assert list(df.columns) == ['col1', 'col2', 'col3']
    assert df['col1'].tolist() == [1, 4, 7]


def test_excel_ignores_separator(excel_file):
    """Test that Excel files ignore separator parameter."""
    # Excel should work regardless of separator value
    df = spreadsheet_to_input_df(
        excel_file,
        header=0,
        columns_are_features=True,
        spreadsheet_separator=";"  # Should be ignored for Excel
    )

    assert df.shape == (3, 3)
    assert list(df.columns) == ['col1', 'col2', 'col3']
    assert df['col1'].tolist() == [1, 4, 7]


def test_backward_compatibility_no_separator_parameter(comma_csv):
    """Test backward compatibility - calling without separator parameter."""
    # Should use default comma separator
    df = spreadsheet_to_input_df(comma_csv, header=0, columns_are_features=True)

    assert df.shape == (3, 3)
    assert df['col1'].tolist() == [1, 4, 7]


def test_wrong_separator_fails_gracefully(semicolon_csv):
    """Test that using wrong separator produces incorrect results (expected behavior)."""
    # Using comma separator on semicolon-separated file
    df = spreadsheet_to_input_df(
        semicolon_csv,
        header=0,
        columns_are_features=True,
        spreadsheet_separator=","  # Wrong separator
    )

    # Will parse entire line as single column (pandas behavior)
    # This is expected - we're not trying to auto-detect, user must specify correct separator
    assert df.shape[1] == 1  # Only one column detected


def test_separator_with_transpose(semicolon_csv):
    """Test separator with columns_are_features=False (transpose mode)."""
    df = spreadsheet_to_input_df(
        semicolon_csv,
        header=0,
        columns_are_features=False,  # Transpose
        spreadsheet_separator=";"
    )

    # Should transpose: 3 columns become 3 rows
    assert df.shape == (3, 3)


def test_separator_with_no_header(semicolon_csv):
    """Test separator with no header row."""
    # Create file without header
    csv_path = semicolon_csv.parent / "no_header.csv"
    csv_path.write_text("1;2;3\n4;5;6\n7;8;9")

    df = spreadsheet_to_input_df(
        csv_path,
        header=None,  # No header row
        columns_are_features=True,
        spreadsheet_separator=";"
    )

    assert df.shape == (3, 3)
    # Column names will be integers 0, 1, 2
    assert df[0].tolist() == [1, 4, 7]
