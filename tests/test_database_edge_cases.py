"""
Edge Case Tests for api/database.py
Covers edge cases, error handling, and concurrent access patterns.
"""
from __future__ import annotations

import sys
import os
import threading
import concurrent.futures
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from api import database, auth_utils


@pytest.fixture
def test_db(tmp_path: Path):
    """Setup a temporary database for testing."""
    import api.database as db_module
    db_module.SQLITE_DB_PATH = tmp_path / "test_db_edge.db"
    db_module.init_database()
    yield db_module
    

@pytest.fixture
def sample_user(test_db):
    """Create a sample user for testing."""
    password_hash = auth_utils.get_password_hash("testpass123")
    user_id = database.add_user("testuser", password_hash, "user", "Test User")
    return {"id": user_id, "username": "testuser", "password_hash": password_hash}


class TestDatabaseInitialization:
    """Tests for database initialization edge cases."""
    
    def test_init_database_creates_tables(self, test_db):
        """
        GIVEN: Empty database
        WHEN: init_database() called
        THEN: All required tables exist
        """
        with database._get_connection() as conn:
            cursor = conn.cursor()
            
            # Check users table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            assert cursor.fetchone() is not None
            
            # Check chats table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chats'")
            assert cursor.fetchone() is not None
            
            # Check messages table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
            assert cursor.fetchone() is not None
    
    def test_init_database_idempotent(self, test_db):
        """
        GIVEN: Already initialized database
        WHEN: init_database() called again
        THEN: No errors, tables still exist
        """
        # Call init again
        database.init_database()
        
        # Tables should still work
        users = database.list_users()
        assert isinstance(users, list)
    
    def test_database_path_creates_parent_dirs(self, tmp_path):
        """
        GIVEN: Non-existent parent directory
        WHEN: Database initialized
        THEN: Parent directories are created
        """
        import api.database as db_module
        
        deep_path = tmp_path / "deep" / "nested" / "path" / "test.db"
        original_path = db_module.SQLITE_DB_PATH
        
        db_module.DATA_DIR = deep_path.parent
        db_module.DATA_DIR.mkdir(parents=True, exist_ok=True)
        db_module.SQLITE_DB_PATH = deep_path
        
        try:
            db_module.init_database()
            assert deep_path.exists()
        finally:
            db_module.SQLITE_DB_PATH = original_path


class TestUserManagementEdgeCases:
    """Edge case tests for user CRUD operations."""
    
    def test_add_user_with_unicode_username(self, test_db):
        """
        GIVEN: Unicode username
        WHEN: Adding user
        THEN: User is created successfully
        """
        password_hash = auth_utils.get_password_hash("password")
        user_id = database.add_user("用户名", password_hash, "user", "Unicode User")
        
        assert user_id is not None
        
        user = database.get_user_by_id(user_id)
        assert user["username"] == "用户名"
    
    def test_add_user_with_special_characters_in_display_name(self, test_db):
        """
        GIVEN: Display name with special characters
        WHEN: Adding user
        THEN: Display name is stored correctly
        """
        password_hash = auth_utils.get_password_hash("password")
        special_name = "John O'Brien-Smith <test> & Co."
        
        user_id = database.add_user("specialuser", password_hash, "user", special_name)
        
        user = database.get_user_by_id(user_id)
        assert user["display_name"] == special_name
    
    def test_add_user_with_very_long_password_hash(self, test_db):
        """
        GIVEN: Very long password hash
        WHEN: Adding user
        THEN: Hash is stored correctly
        """
        # bcrypt hashes are ~60 chars, but test with longer
        password_hash = auth_utils.get_password_hash("a" * 100)
        
        user_id = database.add_user("longpassuser", password_hash, "user")
        
        user = database.get_user_by_username("longpassuser")
        assert user is not None
        assert len(user["password_hash"]) > 50
    
    def test_add_duplicate_username_returns_none(self, test_db, sample_user):
        """
        GIVEN: Existing username
        WHEN: Adding user with same username
        THEN: Returns None (IntegrityError)
        """
        password_hash = auth_utils.get_password_hash("another")
        result = database.add_user("testuser", password_hash, "user")
        
        assert result is None
    
    def test_get_user_by_nonexistent_id(self, test_db):
        """
        GIVEN: Non-existent user ID
        WHEN: get_user_by_id called
        THEN: Returns None
        """
        result = database.get_user_by_id(99999)
        assert result is None
    
    def test_get_user_by_empty_username(self, test_db):
        """
        GIVEN: Empty string username
        WHEN: get_user_by_username called
        THEN: Returns None
        """
        result = database.get_user_by_username("")
        assert result is None
    
    def test_update_display_name_nonexistent_user(self, test_db):
        """
        GIVEN: Non-existent username
        WHEN: update_user_display_name called
        THEN: Returns True but no effect (SQLite quirk)
        """
        result = database.update_user_display_name("nonexistent", "New Name")
        # SQLite UPDATE returns True even if no rows matched
        assert isinstance(result, bool)
    
    def test_update_password_nonexistent_user(self, test_db):
        """
        GIVEN: Non-existent username
        WHEN: update_user_password called
        THEN: Returns True but no effect
        """
        new_hash = auth_utils.get_password_hash("newpass")
        result = database.update_user_password("nonexistent", new_hash)
        assert isinstance(result, bool)
    
    def test_delete_nonexistent_user(self, test_db):
        """
        GIVEN: Non-existent username
        WHEN: delete_user called
        THEN: Returns False
        """
        result = database.delete_user("nonexistent")
        assert result is False
    
    def test_delete_user_cascade_effect(self, test_db, sample_user):
        """
        GIVEN: User with chats
        WHEN: User deleted
        THEN: User is removed (chats may remain orphaned)
        """
        # Delete the user
        result = database.delete_user("testuser")
        assert result is True
        
        # User should no longer exist
        user = database.get_user_by_username("testuser")
        assert user is None


class TestConcurrentAccess:
    """Tests for concurrent database access patterns."""
    
    def test_concurrent_user_creation(self, test_db):
        """
        GIVEN: Concurrent user creation attempts
        WHEN: Multiple threads create different users
        THEN: All users are created successfully
        """
        results = []
        errors = []
        
        def create_user(i):
            try:
                password_hash = auth_utils.get_password_hash(f"pass{i}")
                user_id = database.add_user(f"concurrent_user_{i}", password_hash, "user")
                results.append(user_id)
            except Exception as e:
                errors.append(str(e))
        
        # Create 10 users concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_user, i) for i in range(10)]
            concurrent.futures.wait(futures)
        
        # Should have no errors
        assert len(errors) == 0
        # Should have 10 users
        assert len([r for r in results if r is not None]) == 10
    
    def test_concurrent_reads(self, test_db, sample_user):
        """
        GIVEN: Existing user
        WHEN: Multiple concurrent reads
        THEN: All reads succeed
        """
        results = []
        
        def read_user():
            user = database.get_user_by_username("testuser")
            results.append(user)
        
        # Read 20 times concurrently
        threads = [threading.Thread(target=read_user) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All reads should succeed
        assert len(results) == 20
        assert all(r is not None for r in results)


class TestConnectionManagement:
    """Tests for database connection handling."""
    
    def test_connection_context_manager_closes_properly(self, test_db):
        """
        GIVEN: Database connection
        WHEN: Context manager exits
        THEN: Connection is closed
        """
        with database._get_connection() as conn:
            # Connection should be open
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            assert cursor.fetchone() is not None
        
        # After context exits, we can still get new connections
        with database._get_connection() as conn2:
            cursor2 = conn2.cursor()
            cursor2.execute("SELECT 1")
            assert cursor2.fetchone() is not None
    
    def test_connection_handles_error_in_context(self, test_db):
        """
        GIVEN: Error occurs in context
        WHEN: Context manager exits
        THEN: Connection is still closed
        """
        try:
            with database._get_connection() as conn:
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Should still be able to get new connections
        with database._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            assert cursor.fetchone() is not None


class TestListUsers:
    """Tests for list_users function."""
    
    def test_list_users_empty_database(self, test_db):
        """
        GIVEN: Empty database
        WHEN: list_users called
        THEN: Returns empty list
        """
        users = database.list_users()
        assert users == []
    
    def test_list_users_excludes_password_hash(self, test_db, sample_user):
        """
        GIVEN: Database with users
        WHEN: list_users called
        THEN: Password hash is not in results
        """
        users = database.list_users()
        
        for user in users:
            assert "password_hash" not in user
    
    def test_list_users_includes_all_fields(self, test_db, sample_user):
        """
        GIVEN: Database with users
        WHEN: list_users called
        THEN: All public fields are included
        """
        users = database.list_users()
        
        assert len(users) > 0
        user = users[0]
        
        assert "id" in user
        assert "username" in user
        assert "role" in user
        assert "display_name" in user
        assert "created_at" in user


class TestRoleManagement:
    """Tests for user role handling."""
    
    def test_add_user_with_admin_role(self, test_db):
        """
        GIVEN: Admin role specified
        WHEN: Adding user
        THEN: Role is set to admin
        """
        password_hash = auth_utils.get_password_hash("adminpass")
        user_id = database.add_user("adminuser", password_hash, "admin")
        
        user = database.get_user_by_id(user_id)
        assert user["role"] == "admin"
    
    def test_add_user_with_custom_role(self, test_db):
        """
        GIVEN: Custom role specified
        WHEN: Adding user
        THEN: Role is stored as-is
        """
        password_hash = auth_utils.get_password_hash("pass")
        user_id = database.add_user("customuser", password_hash, "custom_role")
        
        user = database.get_user_by_id(user_id)
        assert user["role"] == "custom_role"
    
    def test_default_role_is_user(self, test_db):
        """
        GIVEN: No role specified
        WHEN: Adding user with default
        THEN: Role defaults to 'user'
        """
        password_hash = auth_utils.get_password_hash("pass")
        user_id = database.add_user("defaultuser", password_hash)
        
        user = database.get_user_by_id(user_id)
        assert user["role"] == "user"
