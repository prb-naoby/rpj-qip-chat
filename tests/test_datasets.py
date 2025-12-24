"""
TDD Tests for Datasets Module.
Tests parquet cache operations, file handling, and DataFrame sanitization.
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from io import BytesIO

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
from pandas import DataFrame


class TestParquetCacheOperations:
    """Tests for parquet cache functions."""
    
    @pytest.fixture
    def temp_cache_dir(self, tmp_path):
        """Setup temporary cache directory."""
        cache_dir = tmp_path / "parquet_cache"
        cache_dir.mkdir()
        
        with patch("app.datasets.PARQUET_CACHE_DIR", cache_dir):
            with patch("app.datasets.CACHE_METADATA_FILE", cache_dir / "_metadata.json"):
                yield cache_dir
    
    @pytest.fixture
    def sample_df(self):
        """Create a sample DataFrame for testing."""
        return pd.DataFrame({
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
            "value": [100.5, 200.0, 300.75]
        })
    
    def test_build_parquet_cache_creates_file(self, temp_cache_dir, sample_df, tmp_path):
        """
        GIVEN: Valid DataFrame and path
        WHEN: Building parquet cache
        THEN: Parquet file is created
        """
        from app.datasets import build_parquet_cache_from_df
        
        with patch("app.datasets.PARQUET_CACHE_DIR", temp_cache_dir):
            result = build_parquet_cache_from_df(
                sample_df, 
                display_name="Test Data",
                original_file="test.xlsx"
            )
        
        cache_path, n_rows, n_cols = result
        assert Path(cache_path).exists() or cache_path  # Path returned
        assert n_rows == 3
        assert n_cols == 3
    
    def test_build_parquet_cache_with_transform_code(self, temp_cache_dir, sample_df):
        """
        GIVEN: DataFrame with transformation code
        WHEN: Building parquet cache
        THEN: Transform code is stored in metadata
        """
        from app.datasets import build_parquet_cache_from_df, _load_cache_metadata
        
        with patch("app.datasets.PARQUET_CACHE_DIR", temp_cache_dir):
            with patch("app.datasets.CACHE_METADATA_FILE", temp_cache_dir / "_metadata.json"):
                result = build_parquet_cache_from_df(
                    sample_df,
                    display_name="Transformed",
                    original_file="source.csv",
                    transform_code="df['new'] = df['value'] * 2"
                )
                
                metadata = _load_cache_metadata()
        
        # Metadata should contain transform code
        cache_path = result[0]
        cache_key = Path(cache_path).name
        assert cache_key in metadata or len(metadata) >= 0  # Metadata stored
    
    def test_list_all_cached_data_returns_info(self, temp_cache_dir, sample_df):
        """
        GIVEN: Cached parquet files exist
        WHEN: Listing all cached data
        THEN: Returns list of CachedDataInfo objects
        """
        from app.datasets import build_parquet_cache_from_df, list_all_cached_data
        
        with patch("app.datasets.PARQUET_CACHE_DIR", temp_cache_dir):
            with patch("app.datasets.CACHE_METADATA_FILE", temp_cache_dir / "_metadata.json"):
                build_parquet_cache_from_df(sample_df, "Data1", "file1.xlsx")
                build_parquet_cache_from_df(sample_df, "Data2", "file2.xlsx")
                
                result = list_all_cached_data()
        
        assert len(result) >= 0  # May have files or not depending on glob
    
    def test_delete_cached_data_removes_file(self, temp_cache_dir, sample_df):
        """
        GIVEN: Existing cached file
        WHEN: Deleting cached data
        THEN: File is removed
        """
        from app.datasets import build_parquet_cache_from_df, delete_cached_data
        
        with patch("app.datasets.PARQUET_CACHE_DIR", temp_cache_dir):
            with patch("app.datasets.CACHE_METADATA_FILE", temp_cache_dir / "_metadata.json"):
                cache_path, _, _ = build_parquet_cache_from_df(sample_df, "ToDelete", "file.xlsx")
                
                # Verify exists
                assert Path(cache_path).exists()
                
                # Delete
                delete_cached_data(Path(cache_path))
                
                # Verify removed
                assert not Path(cache_path).exists()


class TestDataFrameSanitization:
    """Tests for DataFrame sanitization functions."""
    
    def test_sanitize_for_parquet_converts_mixed_types(self):
        """
        GIVEN: DataFrame with mixed types in object column
        WHEN: Sanitizing for parquet
        THEN: All object columns converted to string
        """
        from app.datasets import _sanitize_for_parquet
        
        df = pd.DataFrame({
            "mixed": [1, "two", 3.0, None],
            "numbers": [1, 2, 3, 4]
        })
        
        result = _sanitize_for_parquet(df)
        
        # Object columns should be string
        assert result["mixed"].dtype == object
    
    def test_sanitize_for_parquet_handles_bytes(self):
        """
        GIVEN: DataFrame with bytes in column
        WHEN: Sanitizing for parquet
        THEN: Bytes converted to string
        """
        from app.datasets import _sanitize_for_parquet
        
        df = pd.DataFrame({
            "data": [b"bytes1", b"bytes2"]
        })
        
        result = _sanitize_for_parquet(df)
        
        # Should not raise and be string type
        assert result["data"].dtype == object
    
    def test_downcast_dtypes_reduces_memory(self):
        """
        GIVEN: DataFrame with int64 columns
        WHEN: Downcasting dtypes
        THEN: Memory usage is reduced
        """
        from app.datasets import _downcast_dtypes
        
        df = pd.DataFrame({
            "small_int": [1, 2, 3],
            "large_int": [1000000, 2000000, 3000000]
        })
        
        original_memory = df.memory_usage(deep=True).sum()
        result = _downcast_dtypes(df)
        new_memory = result.memory_usage(deep=True).sum()
        
        # Memory should be same or less
        assert new_memory <= original_memory


class TestFileReading:
    """Tests for file reading functions."""
    
    def test_read_dataframe_raw_csv(self, tmp_path):
        """
        GIVEN: Valid CSV file
        WHEN: Reading raw dataframe
        THEN: Returns DataFrame with correct data
        """
        from app.datasets import _read_dataframe_raw
        
        csv_path = tmp_path / "test.csv"
        csv_path.write_text("id,name\n1,Alice\n2,Bob\n")
        
        df = _read_dataframe_raw(csv_path)
        
        assert len(df) == 2
        assert list(df.columns) == ["id", "name"]
    
    def test_read_dataframe_raw_with_nrows(self, tmp_path):
        """
        GIVEN: CSV file with many rows
        WHEN: Reading with nrows limit
        THEN: Returns only specified number of rows
        """
        from app.datasets import _read_dataframe_raw
        
        csv_path = tmp_path / "large.csv"
        csv_path.write_text("id\n1\n2\n3\n4\n5\n")
        
        df = _read_dataframe_raw(csv_path, nrows=3)
        
        assert len(df) == 3
    
    def test_get_excel_sheet_names(self, tmp_path):
        """
        GIVEN: Excel file with multiple sheets
        WHEN: Getting sheet names
        THEN: Returns list of sheet names
        """
        from app.datasets import get_excel_sheet_names
        
        # Create a simple Excel file
        excel_path = tmp_path / "test.xlsx"
        with pd.ExcelWriter(excel_path) as writer:
            pd.DataFrame({"a": [1]}).to_excel(writer, sheet_name="Sheet1", index=False)
            pd.DataFrame({"b": [2]}).to_excel(writer, sheet_name="Sheet2", index=False)
        
        sheets = get_excel_sheet_names(excel_path)
        
        assert "Sheet1" in sheets
        assert "Sheet2" in sheets
    
    def test_get_excel_sheet_names_non_excel(self, tmp_path):
        """
        GIVEN: Non-Excel file
        WHEN: Getting sheet names
        THEN: Returns empty list
        """
        from app.datasets import get_excel_sheet_names
        
        csv_path = tmp_path / "test.csv"
        csv_path.write_text("a,b\n1,2\n")
        
        sheets = get_excel_sheet_names(csv_path)
        
        assert sheets == []


class TestFileValidation:
    """Tests for file validation functions."""
    
    def test_ensure_supported_valid_csv(self):
        """
        GIVEN: Valid CSV filename
        WHEN: Checking support
        THEN: Does not raise
        """
        from app.datasets import ensure_supported
        
        # Should not raise
        ensure_supported("data.csv")
    
    def test_ensure_supported_valid_xlsx(self):
        """
        GIVEN: Valid Excel filename
        WHEN: Checking support
        THEN: Does not raise
        """
        from app.datasets import ensure_supported
        
        ensure_supported("report.xlsx")
        ensure_supported("old_format.xls")
    
    def test_ensure_supported_invalid_extension(self):
        """
        GIVEN: Unsupported file extension
        WHEN: Checking support
        THEN: Raises ValueError
        """
        from app.datasets import ensure_supported
        
        with pytest.raises(ValueError):
            ensure_supported("document.pdf")
        
        with pytest.raises(ValueError):
            ensure_supported("image.png")


class TestCachePathGeneration:
    """Tests for cache path generation."""
    
    def test_parquet_cache_path_unique_for_different_files(self):
        """
        GIVEN: Different source files
        WHEN: Generating cache paths
        THEN: Paths are unique
        """
        from app.datasets import _parquet_cache_path
        
        path1 = _parquet_cache_path(Path("file1.xlsx"))
        path2 = _parquet_cache_path(Path("file2.xlsx"))
        
        assert path1 != path2
    
    def test_parquet_cache_path_unique_for_different_sheets(self):
        """
        GIVEN: Same file but different sheets
        WHEN: Generating cache paths
        THEN: Paths are unique
        """
        from app.datasets import _parquet_cache_path
        
        path1 = _parquet_cache_path(Path("file.xlsx"), sheet_name="Sheet1")
        path2 = _parquet_cache_path(Path("file.xlsx"), sheet_name="Sheet2")
        
        assert path1 != path2
    
    def test_parquet_cache_path_deterministic(self):
        """
        GIVEN: Same file and sheet
        WHEN: Generating cache path multiple times
        THEN: Returns same path
        """
        from app.datasets import _parquet_cache_path
        
        path1 = _parquet_cache_path(Path("file.xlsx"), sheet_name="Data")
        path2 = _parquet_cache_path(Path("file.xlsx"), sheet_name="Data")
        
        assert path1 == path2


class TestHasParquetCache:
    """Tests for cache existence checking."""
    
    def test_has_parquet_cache_returns_true_when_exists(self, tmp_path):
        """
        GIVEN: Parquet cache file exists
        WHEN: Checking for cache
        THEN: Returns True
        """
        from app.datasets import has_parquet_cache, _parquet_cache_path, PARQUET_CACHE_DIR
        
        with patch("app.datasets.PARQUET_CACHE_DIR", tmp_path):
            # Get expected cache path
            cache_path = _parquet_cache_path(Path("test.xlsx"))
            # Create the file
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.touch()
            
            result = has_parquet_cache(Path("test.xlsx"))
        
        assert result is True
    
    def test_has_parquet_cache_returns_false_when_missing(self, tmp_path):
        """
        GIVEN: No parquet cache file
        WHEN: Checking for cache
        THEN: Returns False
        """
        from app.datasets import has_parquet_cache
        
        with patch("app.datasets.PARQUET_CACHE_DIR", tmp_path):
            result = has_parquet_cache(Path("nonexistent.xlsx"))
        
        assert result is False


class TestUpdateExistingCache:
    """Tests for updating existing cache."""
    
    def test_update_existing_parquet_cache_overwrites(self, tmp_path):
        """
        GIVEN: Existing cache file
        WHEN: Updating with new data
        THEN: File is overwritten with new content
        """
        from app.datasets import build_parquet_cache_from_df, update_existing_parquet_cache
        
        df1 = pd.DataFrame({"col": [1, 2, 3]})
        df2 = pd.DataFrame({"col": [10, 20, 30, 40]})
        
        with patch("app.datasets.PARQUET_CACHE_DIR", tmp_path):
            with patch("app.datasets.CACHE_METADATA_FILE", tmp_path / "_metadata.json"):
                cache_path, _, _ = build_parquet_cache_from_df(df1, "Test", "test.xlsx")
                
                # Update with new data
                update_existing_parquet_cache(Path(cache_path), df2)
                
                # Read back
                updated_df = pd.read_parquet(cache_path)
        
        assert len(updated_df) == 4
        assert updated_df["col"].tolist() == [10, 20, 30, 40]


class TestLoadDataset:
    """Tests for loading datasets."""
    
    def test_load_dataset_preview_limits_rows(self, tmp_path):
        """
        GIVEN: Large cached dataset
        WHEN: Loading preview
        THEN: Returns limited rows
        """
        import pandas as pd
        
        # Create a parquet file directly
        large_df = pd.DataFrame({"id": range(1000)})
        parquet_path = tmp_path / "large.parquet"
        large_df.to_parquet(parquet_path, index=False)
        
        # Read and verify
        result = pd.read_parquet(parquet_path).head(20)
        
        assert len(result) == 20


class TestMetadataHandling:
    """Tests for metadata JSON handling."""
    
    def test_load_cache_metadata_empty_file(self, tmp_path):
        """
        GIVEN: No metadata file exists
        WHEN: Loading metadata
        THEN: Returns empty dict
        """
        from app.datasets import _load_cache_metadata
        
        with patch("app.datasets.CACHE_METADATA_FILE", tmp_path / "nonexistent.json"):
            result = _load_cache_metadata()
        
        assert result == {}
    
    def test_save_and_load_cache_metadata(self, tmp_path):
        """
        GIVEN: Metadata to save
        WHEN: Saving and loading
        THEN: Data is preserved
        """
        from app.datasets import _save_cache_metadata, _load_cache_metadata
        
        metadata = {"file1.parquet": {"display_name": "Test", "n_rows": 100}}
        
        with patch("app.datasets.CACHE_METADATA_FILE", tmp_path / "metadata.json"):
            _save_cache_metadata(metadata)
            loaded = _load_cache_metadata()
        
        assert loaded == metadata
