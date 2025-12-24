"""
Unit tests for API authentication module.
TDD approach - testing auth_utils and auth endpoints.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import timedelta

from api import auth_utils, database


class TestAuthUtils:
    """Tests for auth_utils module."""
    
    def test_password_hash_and_verify(self):
        """Test password hashing and verification."""
        password = "test_password_123"
        hashed = auth_utils.get_password_hash(password)
        
        # Hash should be different from plain password
        assert hashed != password
        
        # Hash should start with bcrypt prefix
        assert hashed.startswith("$2")
        
        # Verification should succeed with correct password
        assert auth_utils.verify_password(password, hashed) is True
        
        # Verification should fail with wrong password
        assert auth_utils.verify_password("wrong_password", hashed) is False
    
    def test_create_access_token(self):
        """Test JWT token creation."""
        data = {"sub": "testuser", "role": "user"}
        token = auth_utils.create_access_token(data)
        
        # Token should be a non-empty string
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Token should have 3 parts (header.payload.signature)
        parts = token.split(".")
        assert len(parts) == 3
    
    def test_create_access_token_with_expiry(self):
        """Test JWT token creation with custom expiry."""
        data = {"sub": "testuser"}
        expires = timedelta(minutes=30)
        token = auth_utils.create_access_token(data, expires_delta=expires)
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_decode_valid_token(self):
        """Test decoding a valid JWT token."""
        data = {"sub": "testuser", "role": "admin"}
        token = auth_utils.create_access_token(data)
        
        decoded = auth_utils.decode_access_token(token)
        
        assert decoded is not None
        assert decoded["sub"] == "testuser"
        assert decoded["role"] == "admin"
        assert "exp" in decoded
    
    def test_decode_invalid_token(self):
        """Test decoding an invalid JWT token."""
        result = auth_utils.decode_access_token("invalid.token.here")
        assert result is None
    
    def test_decode_empty_token(self):
        """Test decoding an empty token."""
        result = auth_utils.decode_access_token("")
        assert result is None


class TestDatabase:
    """Tests for database module."""
    
    @pytest.fixture(autouse=True)
    def setup_test_db(self, tmp_path: Path):
        """Setup a temporary database for each test."""
        # Override the database path
        import api.database as db_module
        db_module.SQLITE_DB_PATH = tmp_path / "test_users.db"
        db_module.init_database()
        yield
    
    def test_init_database(self):
        """Test database initialization."""
        # Database file should exist after init
        assert database.SQLITE_DB_PATH.exists()
    
    def test_add_and_get_user(self):
        """Test adding and retrieving a user."""
        password_hash = auth_utils.get_password_hash("testpass")
        user_id = database.add_user("testuser", password_hash, "user")
        
        assert user_id is not None
        assert user_id > 0
        
        # Retrieve user
        user = database.get_user_by_username("testuser")
        
        assert user is not None
        assert user["username"] == "testuser"
        assert user["role"] == "user"
        assert user["password_hash"] == password_hash
    
    def test_add_duplicate_user(self):
        """Test adding a duplicate user returns None."""
        password_hash = auth_utils.get_password_hash("testpass")
        database.add_user("duplicate", password_hash)
        
        # Try to add same user again
        result = database.add_user("duplicate", password_hash)
        assert result is None
    
    def test_get_nonexistent_user(self):
        """Test getting a user that doesn't exist."""
        user = database.get_user_by_username("nonexistent")
        assert user is None
    
    def test_update_display_name(self):
        """Test updating user display name."""
        password_hash = auth_utils.get_password_hash("testpass")
        database.add_user("updateuser", password_hash)
        
        # Update display name
        success = database.update_user_display_name("updateuser", "New Name")
        assert success is True
        
        # Verify update
        user = database.get_user_by_username("updateuser")
        assert user["display_name"] == "New Name"
    
    def test_update_password(self):
        """Test updating user password."""
        old_hash = auth_utils.get_password_hash("oldpass")
        database.add_user("passuser", old_hash)
        
        # Update password
        new_hash = auth_utils.get_password_hash("newpass")
        success = database.update_user_password("passuser", new_hash)
        assert success is True
        
        # Verify update
        user = database.get_user_by_username("passuser")
        assert auth_utils.verify_password("newpass", user["password_hash"]) is True
        assert auth_utils.verify_password("oldpass", user["password_hash"]) is False
    
    def test_list_users(self):
        """Test listing all users."""
        password_hash = auth_utils.get_password_hash("testpass")
        database.add_user("user1", password_hash)
        database.add_user("user2", password_hash)
        database.add_user("user3", password_hash)
        
        users = database.list_users()
        
        assert len(users) == 3
        usernames = [u["username"] for u in users]
        assert "user1" in usernames
        assert "user2" in usernames
        assert "user3" in usernames
        
        # Password hash should not be in list
        for user in users:
            assert "password_hash" not in user
    
    def test_delete_user(self):
        """Test deleting a user."""
        password_hash = auth_utils.get_password_hash("testpass")
        database.add_user("deleteuser", password_hash)
        
        # Verify user exists
        assert database.get_user_by_username("deleteuser") is not None
        
        # Delete user
        success = database.delete_user("deleteuser")
        assert success is True
        
        # Verify user is gone
        assert database.get_user_by_username("deleteuser") is None
    
    def test_delete_nonexistent_user(self):
        """Test deleting a user that doesn't exist."""
        success = database.delete_user("nonexistent")
        assert success is False
