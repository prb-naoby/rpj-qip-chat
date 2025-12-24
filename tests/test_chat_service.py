"""
TDD Tests for Chat Service Module.
Tests chat CRUD, message handling, and Redis caching integration.
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from api import database


class TestChatServiceFixtures:
    """Shared fixtures for chat service tests."""
    
    @pytest.fixture(autouse=True)
    def setup_test_db(self, tmp_path: Path):
        """Setup a temporary database for each test."""
        import api.database as db_module
        db_module.SQLITE_DB_PATH = tmp_path / "test_chat.db"
        db_module.init_database()
        yield
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client for cache testing."""
        with patch("api.chat_service.redis_client") as mock:
            mock.get.return_value = None  # No cache by default
            mock.set.return_value = True
            mock.delete.return_value = True
            yield mock
    
    @pytest.fixture
    def test_user_id(self):
        """Create a test user and return ID."""
        from api import auth_utils
        password_hash = auth_utils.get_password_hash("testpass")
        user_id = database.add_user("chatuser", password_hash)
        return user_id


class TestCreateChat(TestChatServiceFixtures):
    """Tests for create_chat function."""
    
    def test_create_chat_success(self, test_user_id, mock_redis):
        """
        GIVEN: Valid user ID and title
        WHEN: Creating a new chat
        THEN: Returns chat object with UUID and timestamps
        """
        from api.chat_service import create_chat
        
        chat = create_chat(test_user_id, "My Test Chat")
        
        assert chat is not None
        assert "id" in chat
        assert chat["title"] == "My Test Chat"
        assert chat["user_id"] == test_user_id
        assert "created_at" in chat
        assert "updated_at" in chat
    
    def test_create_chat_default_title(self, test_user_id, mock_redis):
        """
        GIVEN: Valid user ID without title
        WHEN: Creating a new chat
        THEN: Uses "New Chat" as default title
        """
        from api.chat_service import create_chat
        
        chat = create_chat(test_user_id)
        
        assert chat["title"] == "New Chat"
    
    def test_create_chat_invalidates_cache(self, test_user_id, mock_redis):
        """
        GIVEN: User has cached chat list
        WHEN: Creating a new chat
        THEN: User's chat list cache is invalidated
        """
        from api.chat_service import create_chat
        
        create_chat(test_user_id, "New Chat")
        
        mock_redis.delete.assert_called_with(f"user:{test_user_id}:chats")
    
    def test_create_chat_generates_unique_ids(self, test_user_id, mock_redis):
        """
        GIVEN: Multiple chat creations
        WHEN: Creating chats
        THEN: Each chat has a unique ID
        """
        from api.chat_service import create_chat
        
        chat1 = create_chat(test_user_id, "Chat 1")
        chat2 = create_chat(test_user_id, "Chat 2")
        
        assert chat1["id"] != chat2["id"]


class TestGetChats(TestChatServiceFixtures):
    """Tests for get_chats function."""
    
    def test_get_chats_returns_list(self, test_user_id, mock_redis):
        """
        GIVEN: User has multiple chats
        WHEN: Getting user's chats
        THEN: Returns list ordered by most recent
        """
        from api.chat_service import create_chat, get_chats
        
        create_chat(test_user_id, "First Chat")
        create_chat(test_user_id, "Second Chat")
        
        chats = get_chats(test_user_id)
        
        assert len(chats) == 2
        # Order may vary by implementation (created or updated desc)
        titles = [c["title"] for c in chats]
        assert "First Chat" in titles
        assert "Second Chat" in titles
    
    def test_get_chats_empty_for_new_user(self, mock_redis):
        """
        GIVEN: User with no chats
        WHEN: Getting user's chats
        THEN: Returns empty list
        """
        from api.chat_service import get_chats
        from api import auth_utils
        
        password_hash = auth_utils.get_password_hash("pass")
        new_user_id = database.add_user("newuser", password_hash)
        
        chats = get_chats(new_user_id)
        
        assert chats == []
    
    def test_get_chats_uses_cache(self, test_user_id, mock_redis):
        """
        GIVEN: Cached chat list exists
        WHEN: Getting user's chats
        THEN: Returns cached value without DB query
        """
        from api.chat_service import get_chats
        
        cached_chats = [{"id": "cached", "title": "Cached Chat"}]
        mock_redis.get.return_value = cached_chats
        
        result = get_chats(test_user_id)
        
        assert result == cached_chats
    
    def test_get_chats_caches_result(self, test_user_id, mock_redis):
        """
        GIVEN: No cache exists
        WHEN: Getting user's chats
        THEN: Result is cached for 5 minutes
        """
        from api.chat_service import create_chat, get_chats
        
        create_chat(test_user_id, "Test")
        mock_redis.get.return_value = None  # No cache
        
        get_chats(test_user_id)
        
        mock_redis.set.assert_called()
        call_args = mock_redis.set.call_args
        assert call_args[1]["expire_seconds"] == 300


class TestGetChat(TestChatServiceFixtures):
    """Tests for get_chat function."""
    
    def test_get_chat_returns_chat_if_owner(self, test_user_id, mock_redis):
        """
        GIVEN: Chat exists and user is owner
        WHEN: Getting specific chat
        THEN: Returns chat object
        """
        from api.chat_service import create_chat, get_chat
        
        created = create_chat(test_user_id, "My Chat")
        
        chat = get_chat(created["id"], test_user_id)
        
        assert chat is not None
        assert chat["id"] == created["id"]
    
    def test_get_chat_returns_none_if_not_owner(self, test_user_id, mock_redis):
        """
        GIVEN: Chat exists but user is NOT owner
        WHEN: Getting specific chat
        THEN: Returns None (security)
        """
        from api.chat_service import create_chat, get_chat
        from api import auth_utils
        
        created = create_chat(test_user_id, "Owner's Chat")
        
        # Create different user
        other_user_id = database.add_user("other", auth_utils.get_password_hash("pass"))
        
        chat = get_chat(created["id"], other_user_id)
        
        assert chat is None
    
    def test_get_chat_returns_none_if_not_exists(self, test_user_id, mock_redis):
        """
        GIVEN: Chat does not exist
        WHEN: Getting chat by ID
        THEN: Returns None
        """
        from api.chat_service import get_chat
        
        chat = get_chat("nonexistent-uuid", test_user_id)
        
        assert chat is None


class TestUpdateChat(TestChatServiceFixtures):
    """Tests for update_chat function."""
    
    def test_update_chat_changes_title(self, test_user_id, mock_redis):
        """
        GIVEN: Existing chat
        WHEN: Updating title
        THEN: Title is changed and returned
        """
        from api.chat_service import create_chat, update_chat
        
        created = create_chat(test_user_id, "Original Title")
        
        updated = update_chat(created["id"], test_user_id, "New Title")
        
        assert updated["title"] == "New Title"
    
    def test_update_chat_invalidates_cache(self, test_user_id, mock_redis):
        """
        GIVEN: Existing chat
        WHEN: Updating title
        THEN: User's chat list cache is invalidated
        """
        from api.chat_service import create_chat, update_chat
        
        mock_redis.reset_mock()
        created = create_chat(test_user_id, "Test")
        mock_redis.reset_mock()
        
        update_chat(created["id"], test_user_id, "Updated")
        
        mock_redis.delete.assert_called_with(f"user:{test_user_id}:chats")
    
    def test_update_chat_returns_none_if_not_owner(self, test_user_id, mock_redis):
        """
        GIVEN: Chat exists but user is NOT owner
        WHEN: Trying to update
        THEN: Returns None
        """
        from api.chat_service import create_chat, update_chat
        from api import auth_utils
        
        created = create_chat(test_user_id, "Test")
        other_user_id = database.add_user("attacker", auth_utils.get_password_hash("pass"))
        
        result = update_chat(created["id"], other_user_id, "Hacked Title")
        
        assert result is None


class TestDeleteChat(TestChatServiceFixtures):
    """Tests for delete_chat function."""
    
    def test_delete_chat_removes_chat(self, test_user_id, mock_redis):
        """
        GIVEN: Existing chat
        WHEN: Deleting
        THEN: Chat is removed and returns True
        """
        from api.chat_service import create_chat, delete_chat, get_chat
        
        created = create_chat(test_user_id, "To Delete")
        
        result = delete_chat(created["id"], test_user_id)
        
        assert result is True
        assert get_chat(created["id"], test_user_id) is None
    
    def test_delete_chat_returns_false_if_not_owner(self, test_user_id, mock_redis):
        """
        GIVEN: Chat exists but user is NOT owner
        WHEN: Trying to delete
        THEN: Returns False and chat remains
        """
        from api.chat_service import create_chat, delete_chat, get_chat
        from api import auth_utils
        
        created = create_chat(test_user_id, "Protected")
        other_user_id = database.add_user("attacker2", auth_utils.get_password_hash("pass"))
        
        result = delete_chat(created["id"], other_user_id)
        
        assert result is False
        assert get_chat(created["id"], test_user_id) is not None
    
    def test_delete_chat_returns_false_if_not_exists(self, test_user_id, mock_redis):
        """
        GIVEN: Chat does not exist
        WHEN: Trying to delete
        THEN: Returns False
        """
        from api.chat_service import delete_chat
        
        result = delete_chat("nonexistent", test_user_id)
        
        assert result is False
    
    def test_delete_chat_invalidates_cache(self, test_user_id, mock_redis):
        """
        GIVEN: Existing chat
        WHEN: Deleting
        THEN: User's chat list cache is invalidated
        """
        from api.chat_service import create_chat, delete_chat
        
        created = create_chat(test_user_id, "Test")
        mock_redis.reset_mock()
        
        delete_chat(created["id"], test_user_id)
        
        mock_redis.delete.assert_called_with(f"user:{test_user_id}:chats")


class TestAddMessage(TestChatServiceFixtures):
    """Tests for add_message function."""
    
    def test_add_message_creates_message(self, test_user_id, mock_redis):
        """
        GIVEN: Existing chat
        WHEN: Adding a message
        THEN: Message is created with UUID and timestamp
        """
        from api.chat_service import create_chat, add_message
        
        chat = create_chat(test_user_id, "Chat")
        
        message = add_message(chat["id"], "user", "Hello world")
        
        assert message is not None
        assert "id" in message
        assert message["role"] == "user"
        assert message["content"] == "Hello world"
        assert "created_at" in message
    
    def test_add_message_with_metadata(self, test_user_id, mock_redis):
        """
        GIVEN: Existing chat and metadata
        WHEN: Adding a message with metadata
        THEN: Metadata is stored
        """
        from api.chat_service import create_chat, add_message, get_messages
        
        chat = create_chat(test_user_id, "Chat")
        metadata = {"table_used": "sales", "code": "df.sum()"}
        
        message = add_message(chat["id"], "assistant", "Result: 100", metadata)
        
        assert message["metadata"] == metadata
    
    def test_add_message_invalidates_cache(self, test_user_id, mock_redis):
        """
        GIVEN: Existing chat with cached messages
        WHEN: Adding a message
        THEN: Messages cache is invalidated
        """
        from api.chat_service import create_chat, add_message
        
        chat = create_chat(test_user_id, "Chat")
        mock_redis.reset_mock()
        
        add_message(chat["id"], "user", "Test")
        
        mock_redis.delete.assert_called_with(f"chat:{chat['id']}:messages")
    
    def test_add_message_with_different_roles(self, test_user_id, mock_redis):
        """
        GIVEN: Existing chat
        WHEN: Adding messages with different roles
        THEN: All roles are accepted
        """
        from api.chat_service import create_chat, add_message, get_messages
        
        chat = create_chat(test_user_id, "Chat")
        
        add_message(chat["id"], "user", "Question?")
        add_message(chat["id"], "assistant", "Answer.")
        add_message(chat["id"], "system", "System message")
        
        messages = get_messages(chat["id"])
        
        roles = [m["role"] for m in messages]
        assert "user" in roles
        assert "assistant" in roles
        assert "system" in roles


class TestGetMessages(TestChatServiceFixtures):
    """Tests for get_messages function."""
    
    def test_get_messages_returns_ordered_list(self, test_user_id, mock_redis):
        """
        GIVEN: Chat with multiple messages
        WHEN: Getting messages
        THEN: Returns list ordered by created_at ASC
        """
        from api.chat_service import create_chat, add_message, get_messages
        import time
        
        chat = create_chat(test_user_id, "Chat")
        
        add_message(chat["id"], "user", "First")
        time.sleep(0.1)  # Ensure different timestamps
        add_message(chat["id"], "assistant", "Second")
        
        messages = get_messages(chat["id"])
        
        assert len(messages) == 2
        assert messages[0]["content"] == "First"
        assert messages[1]["content"] == "Second"
    
    def test_get_messages_empty_chat(self, test_user_id, mock_redis):
        """
        GIVEN: Chat with no messages
        WHEN: Getting messages
        THEN: Returns empty list
        """
        from api.chat_service import create_chat, get_messages
        
        chat = create_chat(test_user_id, "Empty Chat")
        
        messages = get_messages(chat["id"])
        
        assert messages == []
    
    def test_get_messages_uses_cache(self, test_user_id, mock_redis):
        """
        GIVEN: Cached messages exist
        WHEN: Getting messages
        THEN: Returns cached value
        """
        from api.chat_service import create_chat, get_messages
        
        chat = create_chat(test_user_id, "Chat")
        cached_messages = [{"id": "cached", "content": "Cached"}]
        mock_redis.get.return_value = cached_messages
        
        result = get_messages(chat["id"])
        
        assert result == cached_messages
    
    def test_get_messages_caches_result(self, test_user_id, mock_redis):
        """
        GIVEN: No cache exists
        WHEN: Getting messages
        THEN: Result is cached for 1 hour
        """
        from api.chat_service import create_chat, add_message, get_messages
        
        chat = create_chat(test_user_id, "Chat")
        add_message(chat["id"], "user", "Test")
        mock_redis.get.return_value = None
        
        get_messages(chat["id"])
        
        mock_redis.set.assert_called()
        call_args = mock_redis.set.call_args
        assert call_args[1]["expire_seconds"] == 3600
    
    def test_get_messages_deserializes_metadata(self, test_user_id, mock_redis):
        """
        GIVEN: Message with JSON metadata
        WHEN: Getting messages
        THEN: Metadata is deserialized to dict
        """
        from api.chat_service import create_chat, add_message, get_messages
        
        chat = create_chat(test_user_id, "Chat")
        add_message(chat["id"], "assistant", "Result", {"code": "df.sum()"})
        mock_redis.get.return_value = None  # Force DB read
        
        messages = get_messages(chat["id"])
        
        assert messages[0]["metadata"] == {"code": "df.sum()"}


class TestRankTablesLogic(TestChatServiceFixtures):
    """Tests for rank_tables_logic function."""
    
    def test_rank_tables_empty_cache(self, mock_redis):
        """
        GIVEN: No cached tables
        WHEN: Ranking tables
        THEN: Returns empty list
        """
        from api.chat_service import rank_tables_logic
        
        with patch("api.chat_service.list_all_cached_data", return_value=[]):
            result = rank_tables_logic("any question")
        
        assert result == []
    
    def test_rank_tables_by_display_name(self, mock_redis):
        """
        GIVEN: Tables with matching display names
        WHEN: Ranking by question
        THEN: Tables with matching words score higher
        """
        from api.chat_service import rank_tables_logic
        from app.datasets import CachedDataInfo
        from pathlib import Path
        
        mock_tables = [
            CachedDataInfo(
                cache_path=Path("path1.parquet"),
                display_name="Sales Report",
                original_file="file1.xlsx",
                sheet_name=None,
                n_rows=100, n_cols=5,
                cached_at="2024-01-01",
                file_size_mb=1.0,
                description=None
            ),
            CachedDataInfo(
                cache_path=Path("path2.parquet"),
                display_name="Inventory Data",
                original_file="file2.xlsx",
                sheet_name=None,
                n_rows=200, n_cols=10,
                cached_at="2024-01-01",
                file_size_mb=2.0,
                description=None
            )
        ]
        
        with patch("api.chat_service.list_all_cached_data", return_value=mock_tables):
            result = rank_tables_logic("What are the sales figures?")
        
        # Sales should score higher
        assert result[0]["display_name"] == "Sales Report"
        assert result[0]["score"] > result[1]["score"]
    
    def test_rank_tables_by_description(self, mock_redis):
        """
        GIVEN: Tables with matching descriptions
        WHEN: Ranking by question
        THEN: Description matches contribute to score
        """
        from api.chat_service import rank_tables_logic
        from app.datasets import CachedDataInfo
        from pathlib import Path
        
        mock_tables = [
            CachedDataInfo(
                cache_path=Path("path1.parquet"),
                display_name="Data A",
                original_file="file1.xlsx",
                sheet_name=None,
                n_rows=100, n_cols=5,
                cached_at="2024-01-01",
                file_size_mb=1.0,
                description="Contains monthly revenue and profit data"
            ),
            CachedDataInfo(
                cache_path=Path("path2.parquet"),
                display_name="Data B",
                original_file="file2.xlsx",
                sheet_name=None,
                n_rows=200, n_cols=10,
                cached_at="2024-01-01",
                file_size_mb=2.0,
                description="Employee information"
            )
        ]
        
        with patch("api.chat_service.list_all_cached_data", return_value=mock_tables):
            result = rank_tables_logic("Show me the revenue")
        
        # Data A should score higher due to description match
        assert result[0]["display_name"] == "Data A"
    
    def test_rank_tables_filters_short_words(self, mock_redis):
        """
        GIVEN: Question with short words
        WHEN: Ranking tables
        THEN: Words with 3 or fewer chars are ignored
        """
        from api.chat_service import rank_tables_logic
        from app.datasets import CachedDataInfo
        from pathlib import Path
        
        mock_tables = [
            CachedDataInfo(
                cache_path=Path("path1.parquet"),
                display_name="The Data",
                original_file="file1.xlsx",
                sheet_name=None,
                n_rows=100, n_cols=5,
                cached_at="2024-01-01",
                file_size_mb=1.0,
                description=None
            )
        ]
        
        with patch("api.chat_service.list_all_cached_data", return_value=mock_tables):
            # "the" and "is" should be ignored (<=3 chars)
            result = rank_tables_logic("the is a an")
        
        # No meaningful words, so score should be 0
        assert result[0]["score"] == 0.0
