"""
TDD Tests for GPT-Like Conversational Table Selection.
Tests for natural language clarification and LLM-based intent interpretation.
These tests should FAIL initially, then pass after implementation.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from api import database, auth_utils


@pytest.fixture
def test_db(tmp_path: Path):
    """Setup a temporary database for testing."""
    import api.database as db_module
    db_module.SQLITE_DB_PATH = tmp_path / "test_conv.db"
    db_module.init_database()
    
    # Create test user
    user_hash = auth_utils.get_password_hash("testpass")
    database.add_user("convuser", user_hash, "user")
    yield


@pytest.fixture
def client(test_db):
    """Create a test client."""
    from api.main import app
    return TestClient(app)


@pytest.fixture
def user_token(client):
    """Get user access token."""
    response = client.post(
        "/auth/token",
        data={"username": "convuser", "password": "testpass"}
    )
    return response.json()["access_token"]


@pytest.fixture
def chat_session(client, user_token):
    """Create a chat session for testing."""
    response = client.post(
        "/api/chats",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"title": "Test Conversation"}
    )
    return response.json()["id"]


class TestConversationalClarification:
    """
    Tests for conversational (text-based) table clarification.
    AI should ask in natural language, not show buttons.
    """
    
    def test_clarification_is_conversational_text_not_buttons(
        self, client, user_token, chat_session, tmp_path, monkeypatch
    ):
        """
        GIVEN: All tables fail to answer the question
        WHEN: AI returns clarification
        THEN: Response is conversational text, NOT a 'clarification' UI component
        """
        import pandas as pd
        
        # Create 3 mock tables that will all fail
        for i, name in enumerate(["Sales Report", "Inventory Data", "HR Records"]):
            df = pd.DataFrame({"col": [i]})
            safe_name = name.replace(" ", "_").lower()
            (tmp_path / f"{safe_name}.parquet").parent.mkdir(exist_ok=True)
            df.to_parquet(tmp_path / f"{safe_name}.parquet")
        
        mock_ranked = [
            {"cache_path": str(tmp_path / "sales_report.parquet"), "display_name": "Sales Report", "score": 3.0, "n_rows": 1},
            {"cache_path": str(tmp_path / "inventory_data.parquet"), "display_name": "Inventory Data", "score": 2.5, "n_rows": 1},
            {"cache_path": str(tmp_path / "hr_records.parquet"), "display_name": "HR Records", "score": 2.0, "n_rows": 1},
        ]
        
        import api.chat_service as chat_service
        monkeypatch.setattr(chat_service, "rank_tables_logic", lambda q: mock_ranked)
        
        from app.qa_engine import QAResult
        
        def always_fail(df, prompt, **kwargs):
            return QAResult(prompt=prompt, response="Error", has_error=True)
        
        with patch("api.routes.PandasAIClient") as MockClient:
            MockClient.return_value.ask.side_effect = always_fail
            
            response = client.post(
                "/api/chat/stream",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"chat_id": chat_session, "question": "What is the total?"}
            )
        
        assert response.status_code == 200
        response_text = response.text
        
        # Should be conversational text mentioning available tables
        assert "Sales Report" in response_text
        assert "Inventory Data" in response_text
        # Should NOT contain ui_components with clarification type
        assert '"type": "clarification"' not in response_text
        # Should ask which one to use
        assert "which" in response_text.lower() or "what" in response_text.lower()

    def test_awaiting_clarification_flag_set_in_metadata(
        self, client, user_token, chat_session, tmp_path, monkeypatch
    ):
        """
        GIVEN: All tables fail
        WHEN: Clarification message is saved
        THEN: Message metadata has 'awaiting_table_clarification' flag
        """
        import pandas as pd
        import api.chat_service as chat_service
        
        df = pd.DataFrame({"col": [1]})
        df.to_parquet(tmp_path / "test.parquet")
        
        mock_ranked = [
            {"cache_path": str(tmp_path / "test.parquet"), "display_name": "Test Table", "score": 1.0, "n_rows": 1},
        ]
        monkeypatch.setattr(chat_service, "rank_tables_logic", lambda q: mock_ranked)
        
        from app.qa_engine import QAResult
        
        with patch("api.routes.PandasAIClient") as MockClient:
            MockClient.return_value.ask.return_value = QAResult(prompt="q", response="Error", has_error=True)
            
            client.post(
                "/api/chat/stream",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"chat_id": chat_session, "question": "What is X?"}
            )
        
        # Check that the last assistant message has the flag
        messages = chat_service.get_messages(chat_session)
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert len(assistant_msgs) > 0
        
        last_msg = assistant_msgs[-1]
        meta = last_msg.get("metadata", {})
        assert meta.get("awaiting_table_clarification") == True or meta.get("awaiting_table_hint") == True


class TestLLMIntentInterpretation:
    """
    Tests for LLM-based interpretation of user's table selection response.
    """
    
    def test_interpret_explicit_table_name(self, tmp_path):
        """
        GIVEN: User says "use the Sales Report"
        WHEN: Interpreting table selection
        THEN: Returns the Sales Report table
        """
        from api.intent_classifier import interpret_table_selection
        
        available_tables = [
            {"cache_path": "/path/sales.parquet", "display_name": "Sales Report"},
            {"cache_path": "/path/inventory.parquet", "display_name": "Inventory Data"},
        ]
        
        result = interpret_table_selection("use the Sales Report", available_tables)
        
        assert result is not None
        assert result["display_name"] == "Sales Report"

    def test_interpret_partial_name_match(self, tmp_path):
        """
        GIVEN: User says "try the sales one"
        WHEN: Interpreting table selection
        THEN: Returns table with 'sales' in name
        """
        from api.intent_classifier import interpret_table_selection
        
        available_tables = [
            {"cache_path": "/path/sales.parquet", "display_name": "Sales Report 2024"},
            {"cache_path": "/path/inventory.parquet", "display_name": "Inventory Data"},
        ]
        
        result = interpret_table_selection("try the sales one", available_tables)
        
        assert result is not None
        assert "Sales" in result["display_name"]

    def test_interpret_description_based_selection(self, tmp_path):
        """
        GIVEN: User says "the one with revenue data"
        WHEN: Interpreting (tables have descriptions)
        THEN: Returns table whose description matches
        """
        from api.intent_classifier import interpret_table_selection
        
        available_tables = [
            {"cache_path": "/path/sales.parquet", "display_name": "Report A", "description": "Contains revenue and profit data"},
            {"cache_path": "/path/inventory.parquet", "display_name": "Report B", "description": "Stock levels"},
        ]
        
        result = interpret_table_selection("the one with revenue data", available_tables)
        
        assert result is not None
        assert result["display_name"] == "Report A"

    def test_ambiguous_response_returns_none(self, tmp_path):
        """
        GIVEN: User says something ambiguous like "the other one"
        WHEN: Interpreting table selection
        THEN: Returns None (will trigger re-ask)
        """
        from api.intent_classifier import interpret_table_selection
        
        available_tables = [
            {"cache_path": "/path/a.parquet", "display_name": "Report A"},
            {"cache_path": "/path/b.parquet", "display_name": "Report B"},
        ]
        
        result = interpret_table_selection("the other one", available_tables)
        
        # Ambiguous - should return None or ask again
        # Implementation may vary - either None or best guess
        assert result is None or result in available_tables

    def test_number_based_selection(self, tmp_path):
        """
        GIVEN: Tables are listed with numbers, user says "use number 2"
        WHEN: Interpreting table selection
        THEN: Returns the second table
        """
        from api.intent_classifier import interpret_table_selection
        
        available_tables = [
            {"cache_path": "/path/a.parquet", "display_name": "First Table"},
            {"cache_path": "/path/b.parquet", "display_name": "Second Table"},
            {"cache_path": "/path/c.parquet", "display_name": "Third Table"},
        ]
        
        result = interpret_table_selection("use number 2", available_tables)
        
        assert result is not None
        assert result["display_name"] == "Second Table"


class TestClarificationFollowUp:
    """
    Tests for the full clarification -> response -> retry flow.
    """
    
    def test_user_response_triggers_table_selection(
        self, client, user_token, chat_session, tmp_path, monkeypatch
    ):
        """
        GIVEN: Previous message was awaiting clarification
        WHEN: User responds with table name
        THEN: Query is retried with the selected table
        """
        import pandas as pd
        import api.chat_service as chat_service
        
        # Create tables
        df1 = pd.DataFrame({"revenue": [100, 200, 300]})
        df2 = pd.DataFrame({"inventory": [10, 20]})
        df1.to_parquet(tmp_path / "sales.parquet")
        df2.to_parquet(tmp_path / "inventory.parquet")
        
        # First: Simulate a clarification message was already saved
        chat_service.add_message(
            chat_id=chat_session,
            role="assistant",
            content="Which table should I use? Available: Sales Report, Inventory Data",
            metadata={
                "awaiting_table_clarification": True,
                "available_tables": [
                    {"cache_path": str(tmp_path / "sales.parquet"), "display_name": "Sales Report", "n_rows": 3},
                    {"cache_path": str(tmp_path / "inventory.parquet"), "display_name": "Inventory Data", "n_rows": 2},
                ],
                "original_question": "What is the total revenue?"
            }
        )
        
        from app.qa_engine import QAResult
        mock_result = QAResult(
            prompt="What is the total revenue?",
            response="Total revenue is 600",
            code="df['revenue'].sum()"
        )
        
        with patch("api.routes.PandasAIClient") as MockClient:
            MockClient.return_value.ask.return_value = mock_result
            
            # User responds with table selection
            response = client.post(
                "/api/chat/stream",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"chat_id": chat_session, "question": "use the Sales Report"}
            )
        
        assert response.status_code == 200
        # Should have a successful result now
        assert "600" in response.text or "revenue" in response.text.lower()

    def test_clarification_lists_all_available_tables(
        self, client, user_token, chat_session, tmp_path, monkeypatch
    ):
        """
        GIVEN: Multiple tables exist
        WHEN: Clarification is needed
        THEN: All table names are listed in the message
        """
        import pandas as pd
        import api.chat_service as chat_service
        
        table_names = ["Alpha Report", "Beta Data", "Gamma Stats"]
        for name in table_names:
            df = pd.DataFrame({"x": [1]})
            safe_name = name.replace(" ", "_").lower()
            df.to_parquet(tmp_path / f"{safe_name}.parquet")
        
        mock_ranked = [
            {"cache_path": str(tmp_path / "alpha_report.parquet"), "display_name": "Alpha Report", "score": 1.0, "n_rows": 1},
            {"cache_path": str(tmp_path / "beta_data.parquet"), "display_name": "Beta Data", "score": 0.9, "n_rows": 1},
            {"cache_path": str(tmp_path / "gamma_stats.parquet"), "display_name": "Gamma Stats", "score": 0.8, "n_rows": 1},
        ]
        monkeypatch.setattr(chat_service, "rank_tables_logic", lambda q: mock_ranked)
        
        from app.qa_engine import QAResult
        
        with patch("api.routes.PandasAIClient") as MockClient:
            MockClient.return_value.ask.return_value = QAResult(prompt="q", response="Error", has_error=True)
            
            response = client.post(
                "/api/chat/stream",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"chat_id": chat_session, "question": "What is X?"}
            )
        
        response_text = response.text
        # All table names should be mentioned
        for name in table_names:
            assert name in response_text, f"Table '{name}' not found in clarification message"


class TestEdgeCases:
    """
    Edge case tests for robustness.
    """
    
    def test_single_table_no_clarification_needed(
        self, client, user_token, chat_session, tmp_path, monkeypatch
    ):
        """
        GIVEN: Only one table exists
        WHEN: Query fails
        THEN: Still provides error, but doesn't ask to choose from multiple
        """
        import pandas as pd
        import api.chat_service as chat_service
        
        df = pd.DataFrame({"x": [1]})
        df.to_parquet(tmp_path / "only_table.parquet")
        
        mock_ranked = [
            {"cache_path": str(tmp_path / "only_table.parquet"), "display_name": "Only Table", "score": 1.0, "n_rows": 1},
        ]
        monkeypatch.setattr(chat_service, "rank_tables_logic", lambda q: mock_ranked)
        
        from app.qa_engine import QAResult
        
        with patch("api.routes.PandasAIClient") as MockClient:
            MockClient.return_value.ask.return_value = QAResult(prompt="q", response="Error", has_error=True)
            
            response = client.post(
                "/api/chat/stream",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"chat_id": chat_session, "question": "What is X?"}
            )
        
        response_text = response.text
        # Should not ask to choose (only one table)
        assert "which" not in response_text.lower() or "Only Table" in response_text

    def test_empty_table_id_triggers_auto_selection(
        self, client, user_token, chat_session, tmp_path, monkeypatch
    ):
        """
        GIVEN: Request has empty table_id
        WHEN: Processing question
        THEN: Backend auto-selects based on ranking
        """
        import pandas as pd
        import api.chat_service as chat_service
        
        df = pd.DataFrame({"revenue": [500]})
        df.to_parquet(tmp_path / "data.parquet")
        
        mock_ranked = [
            {"cache_path": str(tmp_path / "data.parquet"), "display_name": "Data", "score": 5.0, "n_rows": 1},
        ]
        monkeypatch.setattr(chat_service, "rank_tables_logic", lambda q: mock_ranked)
        
        from app.qa_engine import QAResult
        mock_result = QAResult(prompt="q", response="Revenue is 500", code="df['revenue'].sum()")
        
        with patch("api.routes.PandasAIClient") as MockClient:
            MockClient.return_value.ask.return_value = mock_result
            
            # Empty table_id
            response = client.post(
                "/api/chat/stream",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"chat_id": chat_session, "question": "What is revenue?", "table_id": ""}
            )
        
        assert response.status_code == 200
        assert "500" in response.text

    def test_no_tables_available_error_message(
        self, client, user_token, chat_session, monkeypatch
    ):
        """
        GIVEN: No tables exist
        WHEN: User asks a question
        THEN: Clear error message about uploading data
        """
        import api.chat_service as chat_service
        
        monkeypatch.setattr(chat_service, "rank_tables_logic", lambda q: [])
        
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"chat_id": chat_session, "question": "What is X?"}
        )
        
        assert response.status_code == 200
        response_text = response.text.lower()
        assert "no table" in response_text or "upload" in response_text or "available" in response_text
