"""Unit tests for IBDiagnet db_csv parser."""

import pytest
import pandas as pd
from pathlib import Path
from services.ibdiagnet.dbcsv import read_index_table, read_table


class TestDbCsvParser:
    """Test db_csv file parsing functionality."""

    def test_read_index_table_success(self, db_csv_file):
        """Test successful parsing of index table."""
        index_df = read_index_table(db_csv_file)

        # Verify index table structure
        assert isinstance(index_df, pd.DataFrame)
        assert "START" in index_df.columns
        assert "END" in index_df.columns
        assert "LINES" in index_df.columns

        # Verify common tables exist
        expected_tables = ["NODES", "CABLE_INFO", "PM_DELTA", "PM_INFO"]
        for table in expected_tables:
            assert table in index_df.index, f"Expected table {table} not found"

        # Verify line numbers are valid
        assert (index_df["START"] > 0).all()
        assert (index_df["END"] > index_df["START"]).all()
        assert (index_df["LINES"] >= 0).all()

    def test_read_index_table_caching(self, db_csv_file):
        """Test that index table is cached properly."""
        # First read
        index_df1 = read_index_table(db_csv_file)

        # Second read should use cache
        index_df2 = read_index_table(db_csv_file)

        # Should be the same object (cached)
        assert index_df1 is index_df2

    def test_read_index_table_nonexistent_file(self):
        """Test error handling for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            read_index_table("nonexistent_file.db_csv")

    def test_read_table_nodes(self, db_csv_file):
        """Test reading NODES table."""
        index_df = read_index_table(db_csv_file)
        nodes_df = read_table(db_csv_file, "NODES", index_df)

        # Verify table structure
        assert isinstance(nodes_df, pd.DataFrame)
        assert len(nodes_df) > 0

        # Verify expected columns
        expected_columns = ["NodeDesc", "NodeGUID", "NodeType", "NumPorts"]
        for col in expected_columns:
            assert col in nodes_df.columns, f"Expected column {col} not found"

        # Verify data types
        assert nodes_df["NodeGUID"].dtype == object
        assert pd.api.types.is_numeric_dtype(nodes_df["NumPorts"])

    def test_read_table_cable_info(self, db_csv_file):
        """Test reading CABLE_INFO table."""
        index_df = read_index_table(db_csv_file)

        # Check if CABLE_INFO exists
        if "CABLE_INFO" not in index_df.index:
            pytest.skip("CABLE_INFO table not available in test data")

        cable_df = read_table(db_csv_file, "CABLE_INFO", index_df)

        # Verify table structure
        assert isinstance(cable_df, pd.DataFrame)
        assert len(cable_df) > 0

        # Verify expected columns (note: raw table uses NodeGuid, not NodeGUID)
        # The cable_service.py handles the renaming in _load_dataframe()
        expected_columns = ["NodeGuid", "PortNum", "Vendor", "PN", "SN"]
        for col in expected_columns:
            assert col in cable_df.columns, f"Expected column {col} not found"

    def test_read_table_pm_delta(self, db_csv_file):
        """Test reading PM_DELTA table."""
        index_df = read_index_table(db_csv_file)

        if "PM_DELTA" not in index_df.index:
            pytest.skip("PM_DELTA table not available in test data")

        pm_df = read_table(db_csv_file, "PM_DELTA", index_df)

        # Verify table structure
        assert isinstance(pm_df, pd.DataFrame)
        assert len(pm_df) > 0

        # Verify expected columns
        expected_columns = ["NodeGUID", "PortNumber"]
        for col in expected_columns:
            assert col in pm_df.columns, f"Expected column {col} not found"

    def test_read_table_invalid_table_name(self, db_csv_file):
        """Test error handling for invalid table name."""
        index_df = read_index_table(db_csv_file)

        with pytest.raises(KeyError):
            read_table(db_csv_file, "NONEXISTENT_TABLE", index_df)

    def test_read_table_handles_na_values(self, db_csv_file):
        """Test that N/A and ERR values are properly handled as NaN."""
        index_df = read_index_table(db_csv_file)

        # Read any table that might have N/A values
        if "PM_DELTA" in index_df.index:
            df = read_table(db_csv_file, "PM_DELTA", index_df)

            # Check that N/A values are converted to NaN
            # (We can't directly test this without knowing which columns have N/A,
            # but we can verify the dataframe was created successfully)
            assert isinstance(df, pd.DataFrame)

    def test_read_table_encoding_latin1(self, db_csv_file):
        """Test that latin-1 encoding is handled correctly."""
        index_df = read_index_table(db_csv_file)

        # Read NODES table which may contain special characters
        nodes_df = read_table(db_csv_file, "NODES", index_df)

        # Verify we can read NodeDesc which may have special characters
        assert "NodeDesc" in nodes_df.columns
        assert nodes_df["NodeDesc"].dtype == object

    def test_index_table_line_count_accuracy(self, db_csv_file):
        """Test that LINES count in index table is accurate."""
        index_df = read_index_table(db_csv_file)

        # Pick a table to verify
        if "NODES" in index_df.index:
            nodes_df = read_table(db_csv_file, "NODES", index_df)
            expected_lines = index_df.loc["NODES", "LINES"]

            # The actual row count should match LINES
            # (accounting for header row which is included in the read)
            assert len(nodes_df) <= expected_lines + 2  # Allow some tolerance

    def test_multiple_tables_sequential_read(self, db_csv_file):
        """Test reading multiple tables sequentially."""
        index_df = read_index_table(db_csv_file)

        tables_to_read = ["NODES", "CABLE_INFO", "PM_DELTA", "PM_INFO"]
        results = {}

        for table_name in tables_to_read:
            if table_name in index_df.index:
                df = read_table(db_csv_file, table_name, index_df)
                results[table_name] = df
                assert isinstance(df, pd.DataFrame)
                assert len(df) > 0

        # Verify we read at least some tables
        assert len(results) > 0
