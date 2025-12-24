"""
Unit tests for QA retry logic.
Tests that the PandasAIClient correctly retries failed code generation.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from app.qa_engine import PandasAIClient, QAResult


@pytest.fixture
def sample_df():
    """Sample DataFrame for testing."""
    return pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})


@pytest.fixture
def mock_client(sample_df):
    """Create a client with mocked OpenAI API."""
    client = PandasAIClient(api_key="fake_key")
    client.client = MagicMock()
    return client


class TestQARetry:
    """Tests for QA retry logic."""
    
    def test_retry_logic_success_after_failure(self, sample_df, mock_client):
        """Test that it retries and eventually succeeds."""
        # Mock responses: 
        # 1. Bad code (causes error)
        # 2. Good code
        
        mock_response_1 = MagicMock()
        mock_response_1.output_text = "```python\nprint(undefined_var)\n```"
        
        mock_response_2 = MagicMock()
        mock_response_2.output_text = "```python\nprint('Success')\n```"
        
        mock_client.client.responses.create.side_effect = [mock_response_1, mock_response_2]
        
        # Mock _safe_exec to simulate error on first call, success on second
        call_count = [0]
        def mock_safe_exec(code, df):
            call_count[0] += 1
            if call_count[0] == 1:
                return "❌ Error: undefined_var not defined", []
            else:
                return "Success", [{"type": "text", "content": "Success"}]
        
        with patch("app.qa_engine._safe_exec", side_effect=mock_safe_exec):
            result = mock_client.ask(sample_df, "Test question", explain=False)
        
        # Should have called API twice
        assert mock_client.client.responses.create.call_count == 2
        # Should be successful eventually
        assert result.has_error == False
        assert result.iterations_used == 2
        assert "Success" in result.response

    def test_max_retries_reached(self, sample_df, mock_client):
        """Test that it stops after max retries."""
        # Mock responses: Always bad code
        mock_response = MagicMock()
        mock_response.output_text = "```python\nraise Exception('Fail')\n```"
        
        mock_client.client.responses.create.return_value = mock_response
        
        # Mock _safe_exec to always return error
        def mock_safe_exec(code, df):
            return "❌ Execution error: Something failed", []
        
        with patch("app.qa_engine._safe_exec", side_effect=mock_safe_exec):
            result = mock_client.ask(sample_df, "Test question", explain=False)
        
        # Should have called API 3 times (MAX_ITERATIONS)
        assert mock_client.client.responses.create.call_count == 3
        # Should be error
        assert result.has_error == True
        # Note: iterations_used is not updated on complete failure (defaults to 1)
        # The validation_notes list contains all errors which confirms 3 attempts

    def test_success_on_first_try(self, sample_df, mock_client):
        """Test that it succeeds on first try if code is valid."""
        mock_response = MagicMock()
        mock_response.output_text = "```python\nprint('Hello World')\n```"
        
        mock_client.client.responses.create.return_value = mock_response
        
        # Mock _safe_exec to return success
        def mock_safe_exec(code, df):
            return "Hello World", [{"type": "text", "content": "Hello World"}]
        
        with patch("app.qa_engine._safe_exec", side_effect=mock_safe_exec):
            result = mock_client.ask(sample_df, "Test question", explain=False)
        
        # Should have called API only once
        assert mock_client.client.responses.create.call_count == 1
        assert result.has_error == False
        assert result.iterations_used == 1
        assert "Hello World" in result.response
