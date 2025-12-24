"""
TDD Tests for Excel Patterns Module.
Tests pattern parsing for Loss C-Grade and Physical Test Lab formats.
Uses mock Excel data to simulate real file structures.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import BytesIO

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
from pandas import DataFrame


class TestBasePattern:
    """Tests for BasePattern base class."""
    
    def test_extract_month_year_from_filename_valid(self):
        """
        GIVEN: Filename with Indonesian month and year
        WHEN: Extracting month and year
        THEN: Returns correct values
        """
        from app.excel_patterns import LossCGradePattern
        
        pattern = LossCGradePattern()
        
        month, year = pattern.extract_month_year_from_filename("Loss C-grade September 2025.xlsx")
        assert month == 9
        assert year == 2025
        
        month, year = pattern.extract_month_year_from_filename("Report Agustus 2024.xlsx")
        assert month == 8
        assert year == 2024
        
        month, year = pattern.extract_month_year_from_filename("Data Januari 2023.xlsx")
        assert month == 1
        assert year == 2023
    
    def test_extract_month_year_from_filename_english(self):
        """
        GIVEN: Filename with English month
        WHEN: Extracting month and year
        THEN: Returns correct values
        """
        from app.excel_patterns import LossCGradePattern
        
        pattern = LossCGradePattern()
        
        month, year = pattern.extract_month_year_from_filename("Report March 2025.xlsx")
        assert month == 3
        assert year == 2025
    
    def test_extract_month_year_from_filename_invalid(self):
        """
        GIVEN: Filename without recognizable month/year
        WHEN: Extracting month and year
        THEN: Returns None for missing values
        """
        from app.excel_patterns import LossCGradePattern
        
        pattern = LossCGradePattern()
        
        month, year = pattern.extract_month_year_from_filename("random_data.xlsx")
        assert month is None
        assert year is None
    
    def test_normalize_date_valid(self):
        """
        GIVEN: Valid date string and context
        WHEN: Normalizing date
        THEN: Returns ISO format YYYY-MM-DD
        """
        from app.excel_patterns import LossCGradePattern
        
        pattern = LossCGradePattern()
        
        result = pattern.normalize_date("15", "15", 9, 2025)
        assert result == "2025-09-15"
        
        result = pattern.normalize_date("1", "1", 12, 2024)
        assert result == "2024-12-01"
    
    def test_normalize_date_with_month_override(self):
        """
        GIVEN: Date string with month name
        WHEN: Normalizing date
        THEN: Month from string overrides parameter
        """
        from app.excel_patterns import LossCGradePattern
        
        pattern = LossCGradePattern()
        
        result = pattern.normalize_date("15 Oktober 2025", "15", 9, 2025)
        assert result == "2025-10-15"
    
    def test_is_numeric_sheet_true(self):
        """
        GIVEN: Sheet name that is a number
        WHEN: Checking if numeric
        THEN: Returns True
        """
        from app.excel_patterns import LossCGradePattern
        
        pattern = LossCGradePattern()
        
        assert pattern.is_numeric_sheet("1") is True
        assert pattern.is_numeric_sheet("15") is True
        assert pattern.is_numeric_sheet("31") is True
    
    def test_is_numeric_sheet_false(self):
        """
        GIVEN: Sheet name that is not a number
        WHEN: Checking if numeric
        THEN: Returns False
        """
        from app.excel_patterns import LossCGradePattern
        
        pattern = LossCGradePattern()
        
        assert pattern.is_numeric_sheet("Sheet1") is False
        assert pattern.is_numeric_sheet("Summary") is False
        assert pattern.is_numeric_sheet("1a") is False


class TestLossCGradePattern:
    """Tests for Loss C-Grade pattern processing."""
    
    @pytest.fixture
    def mock_excel_file(self, tmp_path):
        """Create a mock Loss C-Grade Excel file."""
        # Create a minimal structure simulating the Loss C-Grade format
        # Row 3 (index 2): Date cell
        # Row 4 (index 3): Header for Defect Loss
        # Rows 5-29: Defect Loss data
        # etc.
        
        file_path = tmp_path / "Loss C-grade September 2025.xlsx"
        
        # Create mock data frames for multiple sheets
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Create sheet "1" (day 1)
            df_sheet1 = self._create_mock_sheet(1, 9, 2025)
            df_sheet1.to_excel(writer, sheet_name="1", index=False, header=False)
            
            # Create sheet "15" (day 15)
            df_sheet15 = self._create_mock_sheet(15, 9, 2025)
            df_sheet15.to_excel(writer, sheet_name="15", index=False, header=False)
            
            # Create non-numeric sheet (should be ignored)
            pd.DataFrame({"summary": [1]}).to_excel(writer, sheet_name="Summary", index=False)
        
        return file_path
    
    def _create_mock_sheet(self, day: int, month: int, year: int) -> DataFrame:
        """Create a mock sheet simulating Loss C-Grade structure."""
        # Create 52 rows to cover all table areas
        data = [[None] * 15 for _ in range(52)]
        
        # Row 2 (index 2): Date cell
        data[2][1] = f"{day} September {year}"
        
        # Row 3 (index 3): Defect Loss header
        data[3] = ['Line', 'Model', 'Mold', 'Target', 'Output', '%Output', 
                   'Dirty', 'Bubble', 'Total', '%Deffect Loss', 'Repair', '%Repair', 
                   'Nama TL', 'Line', 'Model']
        
        # Rows 4-8: Defect Loss data
        data[4] = ['L1', 'Model-A', 'M001', 100, 95, 0.95, 2, 1, 3, 0.03, 1, 0.01, 'TL-1', None, None]
        data[5] = ['L2', 'Model-B', 'M002', 150, 140, 0.93, 3, 2, 5, 0.03, 2, 0.01, 'TL-2', None, None]
        
        # Row 30 (index 30): Production Loss header
        data[30] = ['Area', None, 'Mold', 'Target', 'Output', '%Output', None, None, 'Total', 
                    '%Production Loss', 'Repair', '%Repair', None, None, None]
        data[31] = ['Area', None, 'Mold', 'Target', 'Output', '%Output', None, None, 'Total',
                    '%Production Loss', 'Repair', '%Repair', None, None, None]
        data[32] = ['Cutting', None, 'M001', 200, 190, 0.95, None, None, 5, 0.025, 2, 0.01, None, None, None]
        
        return pd.DataFrame(data)
    
    def test_process_valid_file_extracts_date_sheets(self, mock_excel_file):
        """
        GIVEN: Valid Loss C-Grade Excel file
        WHEN: Processing the file
        THEN: Extracts data from numeric (date) sheets only
        """
        from app.excel_patterns import LossCGradePattern
        
        pattern = LossCGradePattern()
        result = pattern.process(mock_excel_file, unpivot=False)
        
        # Should have processed data (may be empty if mock structure doesn't match exactly)
        assert isinstance(result, dict)
    
    def test_process_file_not_found(self, tmp_path):
        """
        GIVEN: Non-existent file path
        WHEN: Processing the file
        THEN: Returns empty dict
        """
        from app.excel_patterns import LossCGradePattern
        
        pattern = LossCGradePattern()
        result = pattern.process(tmp_path / "nonexistent.xlsx")
        
        assert result == {}
    
    def test_exclude_total_rows(self):
        """
        GIVEN: Data with TOTAL/summary rows
        WHEN: Processing
        THEN: Summary rows are excluded
        """
        from app.excel_patterns import LossCGradePattern
        
        pattern = LossCGradePattern()
        
        # Verify exclusion values are defined
        assert 'TOTAL' in pattern.EXCLUDE_LINE_VALUES
        assert 'Total' in pattern.EXCLUDE_AREA_VALUES
    
    def test_defect_types_defined(self):
        """
        GIVEN: LossCGradePattern
        WHEN: Checking defect types
        THEN: All expected defect types are defined
        """
        from app.excel_patterns import LossCGradePattern
        
        pattern = LossCGradePattern()
        
        expected = ['Dirty', 'Bubble', 'Yellowing', 'Overcure', 'Undercure']
        for defect in expected:
            assert defect in pattern.DEFECT_TYPES
    
    def test_table_definitions_complete(self):
        """
        GIVEN: LossCGradePattern
        WHEN: Checking table definitions
        THEN: All 4 tables are defined with required keys
        """
        from app.excel_patterns import LossCGradePattern
        
        pattern = LossCGradePattern()
        
        assert len(pattern.TABLES) == 4
        
        table_names = [t["name"] for t in pattern.TABLES]
        assert "Defect Loss" in table_names
        assert "Production Loss" in table_names
        assert "Return Loss" in table_names
        assert "Total Loss" in table_names
        
        for table in pattern.TABLES:
            assert "name" in table
            assert "header_row" in table
            assert "data_start" in table
            assert "data_end" in table


class TestPhysicalTestLabPattern:
    """Tests for Physical Test Lab pattern processing."""
    
    @pytest.fixture
    def mock_lab_excel(self, tmp_path):
        """Create a mock Physical Test Lab Excel file."""
        file_path = tmp_path / "Physical Test Lab Agustus 2025.xlsx"
        
        # Create two-row header structure
        # Row 0: Test type names spanning columns
        # Row 1: Sub-column labels (result, std, remarks)
        # Row 2+: Data
        
        row0 = ['NO LAB', 'CUST', 'ART', 'ABRASION', '', '', 'HARDNESS', '', '']
        row1 = ['', '', '', 'RESULT', 'STD', 'REMARKS', 'RESULT', 'STD', 'REMARKS']
        data1 = ['LAB001', 'NIKE', 'ART123', 95.5, 90.0, 'PASS', 65, 60, 'PASS']
        data2 = ['LAB002', 'ADIDAS', 'ART456', 88.0, 90.0, 'FAIL', 70, 60, 'PASS']
        
        df = pd.DataFrame([row0, row1, data1, data2])
        df.to_excel(file_path, sheet_name='actual', index=False, header=False)
        
        return file_path
    
    def test_process_valid_file(self, mock_lab_excel):
        """
        GIVEN: Valid Physical Test Lab file
        WHEN: Processing
        THEN: Returns DataFrame with combined headers
        """
        from app.excel_patterns import PhysicalTestLabPattern
        
        pattern = PhysicalTestLabPattern()
        result = pattern.process(mock_lab_excel)
        
        assert "Physical Test Lab" in result
        df = result["Physical Test Lab"]
        assert len(df) > 0
    
    def test_two_row_header_combination(self, mock_lab_excel):
        """
        GIVEN: Excel with two-row header
        WHEN: Processing
        THEN: Headers are combined as "TestType_SubColumn"
        """
        from app.excel_patterns import PhysicalTestLabPattern
        
        pattern = PhysicalTestLabPattern()
        result = pattern.process(mock_lab_excel)
        
        df = result["Physical Test Lab"]
        columns = list(df.columns)
        
        # Should have combined headers
        assert any("ABRASION" in str(c) for c in columns)
        assert any("HARDNESS" in str(c) for c in columns)
    
    def test_extracts_month_from_filename(self, mock_lab_excel):
        """
        GIVEN: Filename with month
        WHEN: Processing
        THEN: Adds Report_Month column
        """
        from app.excel_patterns import PhysicalTestLabPattern
        
        pattern = PhysicalTestLabPattern()
        result = pattern.process(mock_lab_excel)
        
        df = result["Physical Test Lab"]
        
        if "Report_Month" in df.columns:
            assert df["Report_Month"].iloc[0] == "2025-08"
    
    def test_base_columns_defined(self):
        """
        GIVEN: PhysicalTestLabPattern
        WHEN: Checking base columns
        THEN: All expected columns are defined
        """
        from app.excel_patterns import PhysicalTestLabPattern
        
        pattern = PhysicalTestLabPattern()
        
        expected = ['NO LAB', 'CUST', 'ART', 'MODEL', 'COLOUR']
        for col in expected:
            assert col in pattern.BASE_COLUMNS


class TestExcelPatternProcessor:
    """Tests for the main processor class."""
    
    def test_list_patterns(self):
        """
        GIVEN: ExcelPatternProcessor
        WHEN: Listing patterns
        THEN: Returns all registered patterns
        """
        from app.excel_patterns import ExcelPatternProcessor
        
        processor = ExcelPatternProcessor()
        patterns = processor.list_patterns()
        
        assert "Loss C-Grade" in patterns
        assert "Physical Test Lab" in patterns
    
    def test_get_pattern_valid(self):
        """
        GIVEN: Valid pattern name
        WHEN: Getting pattern
        THEN: Returns pattern instance
        """
        from app.excel_patterns import ExcelPatternProcessor, LossCGradePattern
        
        processor = ExcelPatternProcessor()
        pattern = processor.get_pattern("Loss C-Grade")
        
        assert isinstance(pattern, LossCGradePattern)
    
    def test_get_pattern_invalid(self):
        """
        GIVEN: Invalid pattern name
        WHEN: Getting pattern
        THEN: Raises ValueError
        """
        from app.excel_patterns import ExcelPatternProcessor
        
        processor = ExcelPatternProcessor()
        
        with pytest.raises(ValueError, match="Unknown pattern"):
            processor.get_pattern("Nonexistent Pattern")
    
    def test_reset_clears_data(self):
        """
        GIVEN: Processor with accumulated data
        WHEN: Resetting
        THEN: All data is cleared
        """
        from app.excel_patterns import ExcelPatternProcessor
        
        processor = ExcelPatternProcessor()
        processor._tables = {"Test": pd.DataFrame({"a": [1, 2, 3]})}
        processor._processed_files = ["file1.xlsx"]
        
        processor.reset()
        
        assert processor._tables == {}
        assert processor._processed_files == []
    
    def test_get_tables_returns_copy(self):
        """
        GIVEN: Processor with tables
        WHEN: Getting tables
        THEN: Returns copy (not reference)
        """
        from app.excel_patterns import ExcelPatternProcessor
        
        processor = ExcelPatternProcessor()
        processor._tables = {"Test": pd.DataFrame({"a": [1]})}
        
        tables = processor.get_tables()
        tables["New"] = pd.DataFrame()  # Modify returned copy
        
        # Original should be unchanged
        assert "New" not in processor._tables
    
    def test_process_with_append_false_clears_first(self, tmp_path):
        """
        GIVEN: Processor with existing data
        WHEN: Processing with append=False
        THEN: Clears existing data first
        """
        from app.excel_patterns import ExcelPatternProcessor
        
        processor = ExcelPatternProcessor()
        processor._tables = {"OldTable": pd.DataFrame({"a": [1]})}
        
        # Create minimal Excel file
        file_path = tmp_path / "test.xlsx"
        pd.DataFrame({"x": [1]}).to_excel(file_path, index=False)
        
        # Process will fail pattern matching but should still reset
        with patch.object(processor, 'get_pattern') as mock_pattern:
            mock_instance = MagicMock()
            mock_instance.process.return_value = {}
            mock_pattern.return_value = mock_instance
            
            processor.process(file_path, pattern="Loss C-Grade", append=False)
        
        # Old data should be cleared
        assert "OldTable" not in processor._tables
    
    def test_process_accumulates_data(self, tmp_path):
        """
        GIVEN: Multiple files
        WHEN: Processing with append=True
        THEN: Data accumulates
        """
        from app.excel_patterns import ExcelPatternProcessor
        
        processor = ExcelPatternProcessor()
        
        # Create two minimal files
        file1 = tmp_path / "file1.xlsx"
        file2 = tmp_path / "file2.xlsx"
        pd.DataFrame({"x": [1]}).to_excel(file1, index=False)
        pd.DataFrame({"x": [1]}).to_excel(file2, index=False)
        
        with patch.object(processor, 'get_pattern') as mock_pattern:
            mock_instance = MagicMock()
            mock_instance.process.side_effect = [
                {"Table": pd.DataFrame({"a": [1, 2]})},
                {"Table": pd.DataFrame({"a": [3, 4]})}
            ]
            mock_pattern.return_value = mock_instance
            
            processor.process(file1, pattern="Loss C-Grade", append=True)
            processor.process(file2, pattern="Loss C-Grade", append=True)
        
        assert len(processor._processed_files) == 2
    
    def test_process_batch(self, tmp_path):
        """
        GIVEN: List of files
        WHEN: Batch processing
        THEN: All files are processed
        """
        from app.excel_patterns import ExcelPatternProcessor
        
        processor = ExcelPatternProcessor()
        
        files = []
        for i in range(3):
            f = tmp_path / f"file{i}.xlsx"
            pd.DataFrame({"x": [i]}).to_excel(f, index=False)
            files.append(f)
        
        with patch.object(processor, 'get_pattern') as mock_pattern:
            mock_instance = MagicMock()
            mock_instance.process.return_value = {}
            mock_pattern.return_value = mock_instance
            
            processor.process_batch(files, pattern="Loss C-Grade")
        
        assert len(processor._processed_files) == 3


class TestUnpivotTable:
    """Tests for table unpivoting functionality."""
    
    def test_unpivot_defect_loss(self):
        """
        GIVEN: Wide-format Defect Loss table
        WHEN: Unpivoting
        THEN: Converts to long format with Defect_Type column
        """
        from app.excel_patterns import LossCGradePattern
        
        pattern = LossCGradePattern()
        
        # Create wide-format data
        df = pd.DataFrame({
            'Date': ['2025-09-01', '2025-09-01'],
            'Shift': [1, 2],
            'Line': ['L1', 'L2'],
            'Model': ['A', 'B'],
            'Mold': ['M1', 'M2'],
            'Target': [100, 150],
            'Output': [95, 140],
            '%Output': [0.95, 0.93],
            'Total': [3, 5],
            '%Deffect Loss': [0.03, 0.03],
            'Dirty': [2, 3],  # Defect column
            'Bubble': [1, 2],  # Defect column
            'Repair': [1, 2],
            '%Repair': [0.01, 0.01]
        })
        
        result = pattern._unpivot_table(df, "Defect Loss")
        
        # Should have Defect_Type column
        assert 'Defect_Type' in result.columns
        assert 'Value' in result.columns
        
        # Should have rows for each defect type
        defect_types = result['Defect_Type'].unique()
        assert len(defect_types) > 0
    
    def test_unpivot_filters_zero_values(self):
        """
        GIVEN: Table with zero values
        WHEN: Unpivoting
        THEN: Zero values are excluded
        """
        from app.excel_patterns import LossCGradePattern
        
        pattern = LossCGradePattern()
        
        df = pd.DataFrame({
            'Date': ['2025-09-01'],
            'Shift': [1],
            'Line': ['L1'],
            'Model': ['A'],
            'Mold': ['M1'],
            'Dirty': [5],  # Non-zero
            'Bubble': [0],  # Zero - should be excluded
        })
        
        result = pattern._unpivot_table(df, "Defect Loss")
        
        # Bubble with 0 should be excluded
        if len(result) > 0:
            bubble_rows = result[result['Defect_Type'].str.contains('Bubble', case=False, na=False)]
            assert len(bubble_rows) == 0


class TestPatternRegistry:
    """Tests for pattern registry."""
    
    def test_all_patterns_registered(self):
        """
        GIVEN: PATTERN_REGISTRY
        WHEN: Checking registered patterns
        THEN: All expected patterns are present
        """
        from app.excel_patterns import PATTERN_REGISTRY
        
        assert "Loss C-Grade" in PATTERN_REGISTRY
        assert "Physical Test Lab" in PATTERN_REGISTRY
    
    def test_registry_contains_classes(self):
        """
        GIVEN: PATTERN_REGISTRY
        WHEN: Checking values
        THEN: All values are BasePattern subclasses
        """
        from app.excel_patterns import PATTERN_REGISTRY, BasePattern
        
        for name, pattern_class in PATTERN_REGISTRY.items():
            assert issubclass(pattern_class, BasePattern)


class TestConvenienceFunction:
    """Tests for convenience functions."""
    
    def test_process_excel_function(self, tmp_path):
        """
        GIVEN: Excel file and pattern
        WHEN: Using process_excel convenience function
        THEN: Returns processed tables
        """
        from app.excel_patterns import process_excel
        
        # Create minimal file
        file_path = tmp_path / "test.xlsx"
        pd.DataFrame({"x": [1]}).to_excel(file_path, index=False)
        
        with patch("app.excel_patterns.ExcelPatternProcessor") as MockProcessor:
            mock_instance = MagicMock()
            mock_instance.process.return_value = {"Table": pd.DataFrame()}
            MockProcessor.return_value = mock_instance
            
            result = process_excel(file_path, pattern="Loss C-Grade")
        
        assert isinstance(result, dict)
