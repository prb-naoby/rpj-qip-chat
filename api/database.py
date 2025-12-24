"""
Database module for user management.
SQLite-based user authentication following exim-chat pattern.
"""
from __future__ import annotations

import sqlite3
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator

from dotenv import load_dotenv

load_dotenv()

# Store in 'data' directory for Docker persistence
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SQLITE_DB_PATH = DATA_DIR / "qip_users.db"


@contextmanager
def _get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Get a database connection with row factory as a context manager."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_database() -> None:
    """Initialize the database with required tables."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            
            # Users table
            c.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                display_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # Chats table
            c.execute('''CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )''')

            # Messages table
            c.execute('''CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES chats (id) ON DELETE CASCADE
            )''')
            
            conn.commit()
            print(f"Successfully initialized SQLite database at {SQLITE_DB_PATH}")
    except sqlite3.Error as e:
        print(f"Failed to initialize SQLite database: {e}")


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get a user by username."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        print(f"Error getting user: {e}")
        return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get a user by ID."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = c.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        print(f"Error getting user by ID: {e}")
        return None


def add_user(username: str, password_hash: str, role: str = "user", display_name: str = None) -> Optional[int]:
    """Add a new user to the database."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO users (username, password_hash, role, display_name) VALUES (?, ?, ?, ?)",
                (username, password_hash, role, display_name or username)
            )
            user_id = c.lastrowid
            conn.commit()
            return user_id
    except sqlite3.IntegrityError:
        print(f"User {username} already exists")
        return None
    except sqlite3.Error as e:
        print(f"Error adding user: {e}")
        return None


def update_user_display_name(username: str, display_name: str) -> bool:
    """Update a user's display name."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute(
                "UPDATE users SET display_name = ? WHERE username = ?",
                (display_name, username)
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"Error updating display name: {e}")
        return False


def update_user_password(username: str, password_hash: str) -> bool:
    """Update a user's password."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (password_hash, username)
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"Error updating password: {e}")
        return False


def list_users() -> List[Dict[str, Any]]:
    """List all users (excluding password hash)."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id, username, role, display_name, created_at FROM users")
            rows = c.fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"Error listing users: {e}")
        return []


def delete_user(username: str) -> bool:
    """Delete a user by username."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM users WHERE username = ?", (username,))
            affected = c.rowcount
            conn.commit()
            return affected > 0
    except sqlite3.Error as e:
        print(f"Error deleting user: {e}")
        return False
