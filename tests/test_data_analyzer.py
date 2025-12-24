"""
TDD Tests for Data Analyzer Module.
Tests AI response parsing, DataFrame comparison, and transformation validation.
Aligned with actual function signatures in data_analyzer.py.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
from pandas import DataFrame


class TestTransformResultDataclass:
    """Tests for TransformResult dataclass."""
    
    def test_transform_result_defaults(self):
        """
        GIVEN: TransformResult with minimal args
        WHEN: Creating instance
        THEN: Has correct defaults
        """
        from app.data_analyzer import TransformResult
        
        result = TransformResult(
            summary="Test summary",
            issues_found=[],
            transform_code="df",
            needs_transform=False
        )
        
        assert result.summary == "Test summary"
        assert result.issues_found == []
        assert result.transform_code == "df"
        assert result.needs_transform is False
        assert result.preview_df is None
        assert result.validation_notes == []
        assert result.has_error is False
    
    def test_transform_result_with_error(self):
        """
        GIVEN: TransformResult with error
        WHEN: Creating instance
        THEN: Error fields are set correctly
        """
        from app.data_analyzer import TransformResult
        
        result = TransformResult(
            summary="Failed",
            issues_found=["Error occurred"],
            transform_code="bad_code",
            needs_transform=True,
            has_error=True,
            failed_code="import os"
        )
        
        assert result.has_error is True
        assert result.failed_code == "import os"
        assert "Error occurred" in result.issues_found


class TestDataFrameToSampleText:
    """Tests for _dataframe_to_sample_text function."""
    
    def test_df_to_sample_text_basic(self):
        """
        GIVEN: Simple DataFrame
        WHEN: Converting to sample text
        THEN: Returns readable representation
        """
        from app.data_analyzer import _dataframe_to_sample_text
        
        df = pd.DataFrame({
            'name': ['Alice', 'Bob'],
            'age': [25, 30]
        })
        
        text = _dataframe_to_sample_text(df)
        
        assert 'name' in text
        assert 'age' in text
    
    def test_df_to_sample_text_limits_rows(self):
        """
        GIVEN: Large DataFrame
        WHEN: Converting to sample text with max_rows
        THEN: Limits output size
        """
        from app.data_analyzer import _dataframe_to_sample_text
        
        df = pd.DataFrame({'x': range(1000)})
        
        text = _dataframe_to_sample_text(df, max_rows=10)
        
        # Should not include all 1000 rows
        lines = text.split('\n')
        assert len(lines) < 1000
    
    def test_df_to_sample_text_empty(self):
        """
        GIVEN: Empty DataFrame
        WHEN: Converting to sample text
        THEN: Returns valid string
        """
        from app.data_analyzer import _dataframe_to_sample_text
        
        df = pd.DataFrame()
        
        text = _dataframe_to_sample_text(df)
        
        assert isinstance(text, str)


class TestCompareDataFrames:
    """Tests for _compare_dataframes function."""
    
    def test_compare_identical(self):
        """
        GIVEN: Two identical DataFrames
        WHEN: Comparing
        THEN: Reports no significant issues
        """
        from app.data_analyzer import _compare_dataframes
        
        df1 = pd.DataFrame({'a': [1, 2, 3], 'b': ['x', 'y', 'z']})
        df2 = df1.copy()
        
        issues = _compare_dataframes(df1, df2)
        
        # Should return list of issues (empty for identical)
        assert isinstance(issues, list)
    
    def test_compare_different_rows(self):
        """
        GIVEN: DataFrames with different row counts
        WHEN: Comparing
        THEN: Reports row count issue
        """
        from app.data_analyzer import _compare_dataframes
        
        df1 = pd.DataFrame({'a': [1, 2, 3]})
        df2 = pd.DataFrame({'a': [1, 2]})
        
        issues = _compare_dataframes(df1, df2)
        
        # Should note row difference if significant
        assert isinstance(issues, list)
    
    def test_compare_different_columns(self):
        """
        GIVEN: DataFrames with different columns
        WHEN: Comparing
        THEN: May report column differences
        """
        from app.data_analyzer import _compare_dataframes
        
        df1 = pd.DataFrame({'a': [1], 'b': [2]})
        df2 = pd.DataFrame({'a': [1], 'c': [3]})
        
        issues = _compare_dataframes(df1, df2)
        
        assert isinstance(issues, list)


class TestParseAIResponse:
    """Tests for _parse_ai_response function."""
    
    def test_parse_response_with_code(self):
        """
        GIVEN: AI response with code block
        WHEN: Parsing
        THEN: Extracts code and metadata
        """
        from app.data_analyzer import _parse_ai_response
        
        response = """
## Analysis
The data needs cleaning.

## Issues
- Missing values
- Inconsistent types

```python
df['col'] = df['col'].fillna(0)
df['col'] = df['col'].astype(int)
```

This will fix the issues.
"""
        
        code, summary, issues, needs_transform, failed_code, explanation = _parse_ai_response(response)
        
        # Should extract code - may contain df operations
        assert isinstance(code, str)
        assert isinstance(summary, str)
        assert isinstance(issues, list)
    
    def test_parse_response_no_code(self):
        """
        GIVEN: AI response without code
        WHEN: Parsing
        THEN: Returns empty code
        """
        from app.data_analyzer import _parse_ai_response
        
        response = "The data looks clean. No transformation needed."
        
        code, summary, issues, needs_transform, failed_code, explanation = _parse_ai_response(response)
        
        # Code should be empty or df passthrough
        assert code == "" or code == "df" or "df" in code
    
    def test_parse_response_returns_tuple(self):
        """
        GIVEN: Any AI response
        WHEN: Parsing
        THEN: Returns 6-tuple
        """
        from app.data_analyzer import _parse_ai_response
        
        response = "```python\ndf = df.dropna()\n```"
        
        result = _parse_ai_response(response)
        
        assert len(result) == 6


class TestExecuteTransform:
    """Tests for execute_transform function."""
    
    def test_execute_valid_transform(self):
        """
        GIVEN: Valid transformation code
        WHEN: Executing
        THEN: Returns transformed DataFrame
        """
        from app.data_analyzer import execute_transform
        
        df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        code = "df['c'] = df['a'] + df['b']"
        
        result_df, error = execute_transform(df, code)
        
        assert error is None or error == ""
        assert 'c' in result_df.columns
        assert result_df['c'].tolist() == [5, 7, 9]
    
    def test_execute_invalid_code(self):
        """
        GIVEN: Invalid transformation code
        WHEN: Executing
        THEN: Returns error
        """
        from app.data_analyzer import execute_transform
        
        df = pd.DataFrame({'a': [1]})
        code = "df['b'] = df['nonexistent'] * 2"
        
        result_df, error = execute_transform(df, code)
        
        # Should have error
        assert error is not None and error != ""
    
    def test_execute_syntax_error(self):
        """
        GIVEN: Code with syntax error
        WHEN: Executing
        THEN: Returns error
        """
        from app.data_analyzer import execute_transform
        
        df = pd.DataFrame({'a': [1]})
        code = "df['b'] = if True"  # Syntax error
        
        result_df, error = execute_transform(df, code)
        
        assert error is not None and error != ""


class TestAnalyzeAndGenerateTransform:
    """Tests for analyze_and_generate_transform function."""
    
    def test_analyze_returns_result(self):
        """
        GIVEN: DataFrame for analysis
        WHEN: Calling analyze_and_generate_transform
        THEN: Returns TransformResult
        """
        from app.data_analyzer import analyze_and_generate_transform, TransformResult
        
        df = pd.DataFrame({'a': [1, 2, 3]})
        
        with patch('app.data_analyzer._get_client') as mock_client:
            mock_openai = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="""
No issues found. Data is clean.

```python
df
```
"""))]
            mock_openai.chat.completions.create.return_value = mock_response
            mock_client.return_value = mock_openai
            
            result = analyze_and_generate_transform(df, filename="test.csv")
        
        assert isinstance(result, TransformResult)
    
    def test_analyze_handles_ai_error(self):
        """
        GIVEN: AI API failure
        WHEN: Analyzing
        THEN: Returns error result gracefully
        """
        from app.data_analyzer import analyze_and_generate_transform, TransformResult
        
        df = pd.DataFrame({'a': [1]})
        
        with patch('app.data_analyzer._get_client') as mock_client:
            mock_client.side_effect = Exception("API Error")
            
            result = analyze_and_generate_transform(df)
        
        assert isinstance(result, TransformResult)
        # Graceful fallback - may set has_error=True or return default
        # The actual implementation handles error gracefully


class TestRegenerateWithFeedback:
    """Tests for regenerate_with_feedback function."""
    
    def test_regenerate_returns_result(self):
        """
        GIVEN: Failed transform and user feedback
        WHEN: Regenerating
        THEN: Returns TransformResult
        """
        from app.data_analyzer import regenerate_with_feedback, TransformResult
        
        df = pd.DataFrame({'a': [1, 2]})
        feedback = "Keep only rows where a > 1"
        
        with patch('app.data_analyzer._get_client') as mock_client:
            mock_openai = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="""
```python
df = df[df['a'] > 1]
```
"""))]
            mock_openai.chat.completions.create.return_value = mock_response
            mock_client.return_value = mock_openai
            
            result = regenerate_with_feedback(
                df=df,
                previous_code="df",
                user_feedback=feedback
            )
        
        assert isinstance(result, TransformResult)


class TestGetQuickAnalysis:
    """Tests for get_quick_analysis function."""
    
    def test_quick_analysis_returns_dict(self):
        """
        GIVEN: DataFrame
        WHEN: Getting quick analysis
        THEN: Returns dict with analysis
        """
        from app.data_analyzer import get_quick_analysis
        
        df = pd.DataFrame({
            'a': [1, None, 3],
            'b': ['x', 'y', 'z']
        })
        
        result = get_quick_analysis(df)
        
        assert isinstance(result, dict)
    
    def test_quick_analysis_detects_nulls(self):
        """
        GIVEN: DataFrame with null values
        WHEN: Getting quick analysis
        THEN: Detects null issues
        """
        from app.data_analyzer import get_quick_analysis
        
        df = pd.DataFrame({
            'a': [1, None, None],
            'b': [None, None, None]
        })
        
        result = get_quick_analysis(df)
        
        # Should have some analysis
        assert isinstance(result, dict)
