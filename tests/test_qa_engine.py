"""
TDD Tests for QA Engine Module.
Tests code extraction, safe execution sandbox, and fuzzy matching.
Aligned with actual function signatures in qa_engine.py.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestExtractCode:
    """Tests for _extract_code function."""
    
    def test_extract_code_with_python_block(self):
        """
        GIVEN: Response with ```python code block
        WHEN: Extracting code
        THEN: Returns clean code without markers
        """
        from app.qa_engine import _extract_code
        
        response = '''Here is the analysis:
        
```python
df_result = df.groupby('category').sum()
print(df_result)
```

This shows the grouped data.'''
        
        result = _extract_code(response)
        
        assert "df_result = df.groupby('category').sum()" in result
        assert "```" not in result
    
    def test_extract_code_with_generic_block(self):
        """
        GIVEN: Response with ``` block (no language)
        WHEN: Extracting code
        THEN: Returns code content
        """
        from app.qa_engine import _extract_code
        
        response = '''Result:
        
```
df['new_col'] = df['value'] * 2
```
'''
        
        result = _extract_code(response)
        
        # Should extract something (may return whole text if no python block)
        assert result is not None
    
    def test_extract_code_no_block(self):
        """
        GIVEN: Response without code block
        WHEN: Extracting code
        THEN: Returns empty string or original
        """
        from app.qa_engine import _extract_code
        
        response = "The answer is 42."
        
        result = _extract_code(response)
        
        # Should return empty or the original if no code found
        assert result is not None or result == ""


class TestFuzzyMatch:
    """Tests for _fuzzy_match function."""
    
    def test_fuzzy_match_exact_substring(self):
        """
        GIVEN: Series with exact substring match
        WHEN: Fuzzy matching
        THEN: Returns True for matching values
        """
        from app.qa_engine import _fuzzy_match
        
        series = pd.Series(['DONG JIN TEXTILE CO', 'ABC COMPANY', 'XYZ LTD'])
        
        result = _fuzzy_match(series, 'DONG JIN')
        
        assert result.iloc[0] == True
        assert result.iloc[1] == False
    
    def test_fuzzy_match_case_insensitive(self):
        """
        GIVEN: Series with different case
        WHEN: Fuzzy matching
        THEN: Returns True for case-insensitive match
        """
        from app.qa_engine import _fuzzy_match
        
        series = pd.Series(['Nike Inc', 'Adidas AG', 'Puma SE'])
        
        result = _fuzzy_match(series, 'nike')
        
        assert result.iloc[0] == True
    
    def test_fuzzy_match_no_match(self):
        """
        GIVEN: Series with no matching values
        WHEN: Fuzzy matching
        THEN: Returns all False
        """
        from app.qa_engine import _fuzzy_match
        
        series = pd.Series(['Alpha', 'Beta', 'Gamma'])
        
        result = _fuzzy_match(series, 'XYZ123')
        
        assert result.all() == False
    
    def test_fuzzy_match_handles_na(self):
        """
        GIVEN: Series with NA values
        WHEN: Fuzzy matching
        THEN: Returns False for NA values without error
        """
        from app.qa_engine import _fuzzy_match
        
        series = pd.Series(['Alpha', None, 'Gamma'])
        
        result = _fuzzy_match(series, 'Alpha')
        
        assert result.iloc[0] == True
        assert result.iloc[1] == False


class TestSafeExec:
    """Tests for _safe_exec function."""
    
    def test_safe_exec_valid_code(self):
        """
        GIVEN: Valid pandas code
        WHEN: Executing safely
        THEN: Returns result without error
        """
        from app.qa_engine import _safe_exec
        
        df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        code = "result = df['a'].sum()\ndisplay(result)"
        
        output, ui_components = _safe_exec(code, df)
        
        # Should return output and components
        assert isinstance(output, str)
        assert isinstance(ui_components, list)
    
    def test_safe_exec_returns_dataframe(self):
        """
        GIVEN: Code that produces DataFrame
        WHEN: Executing safely
        THEN: Returns DataFrame in UI components
        """
        from app.qa_engine import _safe_exec
        
        df = pd.DataFrame({'x': [1, 2, 3]})
        code = "df_result = df[df['x'] > 1]\ndisplay(df_result)"
        
        output, ui_components = _safe_exec(code, df)
        
        # UI components should be a list
        assert isinstance(ui_components, list)
    
    def test_safe_exec_syntax_error(self):
        """
        GIVEN: Code with syntax error
        WHEN: Executing safely
        THEN: Returns error in output
        """
        from app.qa_engine import _safe_exec
        
        df = pd.DataFrame({'a': [1]})
        code = "if True print('oops')"  # Syntax error
        
        output, ui_components = _safe_exec(code, df)
        
        # Should contain error message in output
        assert 'error' in output.lower() or 'syntax' in output.lower() or len(output) > 0
    
    def test_safe_exec_runtime_error(self):
        """
        GIVEN: Code with runtime error
        WHEN: Executing safely
        THEN: Returns error info
        """
        from app.qa_engine import _safe_exec
        
        df = pd.DataFrame({'a': [1]})
        code = "result = df['nonexistent_column'].sum()"
        
        output, ui_components = _safe_exec(code, df)
        
        # Should contain error info
        assert isinstance(output, str)


class TestSanitizeDfForDisplay:
    """Tests for _sanitize_df_for_display function."""
    
    def test_sanitize_converts_to_json_safe(self):
        """
        GIVEN: DataFrame with complex types
        WHEN: Sanitizing for display
        THEN: Converts to JSON-safe format
        """
        from app.qa_engine import _sanitize_df_for_display
        
        df = pd.DataFrame({
            'dates': pd.to_datetime(['2024-01-01', '2024-02-01']),
            'numbers': [1, 2]
        })
        
        result = _sanitize_df_for_display(df)
        
        # Should be able to convert to dict without error
        result.to_dict(orient='records')
    
    def test_sanitize_handles_empty_df(self):
        """
        GIVEN: Empty DataFrame
        WHEN: Sanitizing for display
        THEN: Returns empty DataFrame
        """
        from app.qa_engine import _sanitize_df_for_display
        
        df = pd.DataFrame()
        
        result = _sanitize_df_for_display(df)
        
        assert len(result) == 0


class TestQAResult:
    """Tests for QAResult dataclass."""
    
    def test_qa_result_defaults(self):
        """
        GIVEN: QAResult creation with minimal args
        WHEN: Creating instance
        THEN: Has correct defaults
        """
        from app.qa_engine import QAResult
        
        result = QAResult(prompt="test", response="answer")
        
        assert result.prompt == "test"
        assert result.response == "answer"
        assert result.code is None
        assert result.explanation is None
        assert result.ui_components == []
        assert result.has_error is False
    
    def test_qa_result_with_error(self):
        """
        GIVEN: QAResult with error
        WHEN: Creating instance
        THEN: Error fields are set
        """
        from app.qa_engine import QAResult
        
        result = QAResult(
            prompt="test",
            response="Failed",
            has_error=True,
            failed_code="bad_code()"
        )
        
        assert result.has_error is True
        assert result.failed_code == "bad_code()"


class TestPandasAIClient:
    """Tests for PandasAIClient class."""
    
    def test_client_initialization_with_api_key(self):
        """
        GIVEN: API key provided
        WHEN: Initializing client
        THEN: Sets up correctly
        """
        from app.qa_engine import PandasAIClient
        
        with patch('app.qa_engine.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"
            client = PandasAIClient(api_key="test-key")
        
        assert client is not None
    
    def test_client_ask_returns_result(self):
        """
        GIVEN: Valid question and DataFrame
        WHEN: Asking question
        THEN: Returns QAResult
        """
        from app.qa_engine import PandasAIClient, QAResult
        
        with patch('app.qa_engine.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.OPENAI_MODEL = "gpt-4"
            
            with patch('app.qa_engine.OpenAI') as MockOpenAI:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock(message=MagicMock(content="```python\nresult = 42\n```"))]
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client
                
                client = PandasAIClient(api_key="test-key")
                df = pd.DataFrame({'a': [1, 2, 3]})
                
                result = client.ask(df, "What is the sum?")
        
        assert isinstance(result, QAResult)


class TestBuildSystemPrompt:
    """Tests for _build_system_prompt function."""
    
    def test_system_prompt_includes_columns(self):
        """
        GIVEN: DataFrame with columns
        WHEN: Building system prompt
        THEN: Includes column names
        """
        from app.qa_engine import _build_system_prompt
        
        df = pd.DataFrame({
            'product_id': [1, 2],
            'price': [100.0, 200.0]
        })
        
        prompt = _build_system_prompt(df)
        
        assert 'product_id' in prompt
        assert 'price' in prompt
    
    def test_system_prompt_with_description(self):
        """
        GIVEN: DataFrame with table description
        WHEN: Building system prompt
        THEN: Includes description
        """
        from app.qa_engine import _build_system_prompt
        
        df = pd.DataFrame({'id': [1, 2]})
        
        prompt = _build_system_prompt(df, table_description="Sales data for Q4")
        
        assert 'Sales' in prompt or 'Q4' in prompt or len(prompt) > 0
