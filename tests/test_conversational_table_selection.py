"""
TDD Tests for Conversational Table Selection (ChatGPT-Style UX).
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


class TestSilentFallbackLoop:
    """
    Phase 1: When no table_id is provided, AI should try top 3 tables silently.
    """
    
    def test_no_table_id_tries_first_table_on_success(
        self, client, user_token, chat_session, tmp_path, monkeypatch
    ):
        """
        Given: No table_id, top-ranked table can answer the question
        When: User asks a question
        Then: AI returns answer, mentions which table was used
        """
        import pandas as pd
        
        # Create mock table
        df = pd.DataFrame({"sales": [100, 200, 300]})
        cache_path = tmp_path / "sales_data.parquet"
        df.to_parquet(cache_path)
        
        # Mock rank_tables_logic to return our test table
        mock_ranked = [
            {"cache_path": str(cache_path), "display_name": "Sales Data", "score": 5.0, "n_rows": 3},
        ]
        
        import api.chat_service as chat_service
        monkeypatch.setattr(chat_service, "rank_tables_logic", lambda q: mock_ranked)
        
        # Mock PandasAIClient to return success
        from app.qa_engine import QAResult
        mock_result = QAResult(
            prompt="total sales",
            response="Total sales: 600",
            code="df['sales'].sum()",
            ui_components=[{"type": "stat", "value": 600, "label": "Total"}]
        )
        
        with patch("api.routes.PandasAIClient") as MockClient:
            MockClient.return_value.ask.return_value = mock_result
            
            response = client.post(
                "/api/chat/stream",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"chat_id": chat_session, "question": "What are total sales?"}
            )
        
        assert response.status_code == 200
        # Check SSE events
        events = response.text.split("\n\n")
        result_event = [e for e in events if "result" in e]
        assert len(result_event) > 0
        assert "600" in response.text or "Total" in response.text
    
    def test_first_table_fails_tries_second_table(
        self, client, user_token, chat_session, tmp_path, monkeypatch
    ):
        """
        Given: No table_id, first table query fails, second succeeds
        When: User asks a question
        Then: AI silently tries second table, returns answer
        """
        import pandas as pd
        
        # Create two mock tables
        df1 = pd.DataFrame({"inventory": [10, 20]})  # Wrong table
        df2 = pd.DataFrame({"sales": [100, 200, 300]})  # Right table
        
        cache1 = tmp_path / "inventory.parquet"
        cache2 = tmp_path / "sales.parquet"
        df1.to_parquet(cache1)
        df2.to_parquet(cache2)
        
        mock_ranked = [
            {"cache_path": str(cache1), "display_name": "Inventory", "score": 4.0, "n_rows": 2},
            {"cache_path": str(cache2), "display_name": "Sales", "score": 3.5, "n_rows": 3},
        ]
        
        import api.chat_service as chat_service
        monkeypatch.setattr(chat_service, "rank_tables_logic", lambda q: mock_ranked)
        
        from app.qa_engine import QAResult
        call_count = [0]
        
        def mock_ask(df, prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First table fails
                return QAResult(prompt=prompt, response="Error: Column 'sales' not found", has_error=True)
            else:
                # Second table succeeds
                return QAResult(prompt=prompt, response="Total: 600", code="df['sales'].sum()")
        
        with patch("api.routes.PandasAIClient") as MockClient:
            MockClient.return_value.ask.side_effect = mock_ask
            
            response = client.post(
                "/api/chat/stream",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"chat_id": chat_session, "question": "What are total sales?"}
            )
        
        assert response.status_code == 200
        assert call_count[0] == 2  # Tried 2 tables
        assert "600" in response.text or "Total" in response.text
    
    def test_all_tables_fail_asks_for_clarification(
        self, client, user_token, chat_session, tmp_path, monkeypatch
    ):
        """
        Given: No table_id, all 3 tables fail
        When: User asks a question
        Then: AI explains what it tried and asks for help
        """
        import pandas as pd
        
        # Create 3 mock tables
        for i, name in enumerate(["t1", "t2", "t3"]):
            df = pd.DataFrame({"col": [i]})
            (tmp_path / f"{name}.parquet").parent.mkdir(exist_ok=True)
            df.to_parquet(tmp_path / f"{name}.parquet")
        
        mock_ranked = [
            {"cache_path": str(tmp_path / "t1.parquet"), "display_name": "Table 1", "score": 3.0, "n_rows": 1},
            {"cache_path": str(tmp_path / "t2.parquet"), "display_name": "Table 2", "score": 2.5, "n_rows": 1},
            {"cache_path": str(tmp_path / "t3.parquet"), "display_name": "Table 3", "score": 2.0, "n_rows": 1},
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
                json={"chat_id": chat_session, "question": "What is X?"}
            )
        
        assert response.status_code == 200
        # Should mention tables tried and ask for help
        assert "Table 1" in response.text or "tried" in response.text.lower()


class TestFollowUpDetection:
    """
    Phase 2: AI should detect if user's follow-up is about the same data.
    """
    
    def test_follow_up_uses_same_table_when_related(
        self, client, user_token, chat_session, tmp_path, monkeypatch
    ):
        """
        Given: Previous question used "Sales" table
        When: User asks "Show me the breakdown"
        Then: AI uses the same table (no re-ranking)
        """
        import pandas as pd
        
        df = pd.DataFrame({"sales": [100, 200], "region": ["A", "B"]})
        cache = tmp_path / "sales.parquet"
        df.to_parquet(cache)
        
        # Simulate previous message that set last_used_table
        import api.chat_service as chat_service
        chat_service.add_message(
            chat_id=chat_session,
            role="assistant",
            content="Total: 300",
            metadata={"last_used_table": str(cache), "table_name": "Sales"}
        )
        
        from app.qa_engine import QAResult
        mock_result = QAResult(prompt="breakdown", response="A: 100, B: 200", code="...")
        
        with patch("api.routes.PandasAIClient") as MockClient:
            MockClient.return_value.ask.return_value = mock_result
            
            # This should NOT call rank_tables_logic because it's a follow-up
            with patch.object(chat_service, "rank_tables_logic") as mock_rank:
                response = client.post(
                    "/api/chat/stream",
                    headers={"Authorization": f"Bearer {user_token}"},
                    json={"chat_id": chat_session, "question": "Show me the breakdown"}
                )
                
                # If follow-up detection works, rank_tables_logic should NOT be called
                # (Implementation will determine this - test may need adjustment)
    
    def test_new_topic_triggers_re_ranking(
        self, client, user_token, chat_session, tmp_path, monkeypatch
    ):
        """
        Given: Previous question used "Sales" table
        When: User asks "What about inventory levels?"
        Then: AI detects new topic, ranks tables again
        """
        # This test validates that intent detection recognizes topic switch
        pass  # Placeholder - implementation will define exact behavior


class TestIntentClassification:
    """
    Unit tests for intent classification logic.
    """
    
    def test_classify_same_data_intent(self):
        """Test that follow-up phrases are classified as SAME_DATA."""
        # This will test a helper function once implemented
        test_cases = [
            ("Show me more details", "SAME_DATA"),
            ("Break it down by region", "SAME_DATA"),
            ("What about last month?", "SAME_DATA"),
            ("Now show inventory data", "NEW_DATA"),
            ("Check the HR report", "NEW_DATA"),
        ]
        # Placeholder - will import and test classify_intent() once implemented
        pass
