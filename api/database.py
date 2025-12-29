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
                requested_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Migration: Add requested_at column if not exists
            c.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in c.fetchall()]
            if 'requested_at' not in columns:
                c.execute("ALTER TABLE users ADD COLUMN requested_at TIMESTAMP")
                print("Added requested_at column to users table")
            
            # Pending Users table (for registration approval)
            c.execute('''CREATE TABLE IF NOT EXISTS pending_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                password_hash TEXT NOT NULL,
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
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


# -----------------------------------------------------------------------------
# Pending Users (Registration Approval Workflow)
# -----------------------------------------------------------------------------

def add_pending_user(username: str, password_hash: str, email: str = None) -> bool:
    """Add a user registration request for admin approval."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO pending_users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, password_hash)
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False
    except sqlite3.Error as e:
        print(f"Error adding pending user: {e}")
        return False


def get_pending_users() -> List[Dict[str, Any]]:
    """Get all pending registration requests."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute("""SELECT id, username, email, requested_at, status 
                        FROM pending_users WHERE status = 'pending' 
                        ORDER BY requested_at DESC""")
            rows = c.fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"Error getting pending users: {e}")
        return []


def get_pending_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get a pending user by ID."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM pending_users WHERE id = ?", (user_id,))
            row = c.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        print(f"Error getting pending user: {e}")
        return None


def approve_pending_user(user_id: int) -> bool:
    """Approve a pending user and move them to users table."""
    try:
        pending = get_pending_user_by_id(user_id)
        if not pending:
            return False
        
        with _get_connection() as conn:
            c = conn.cursor()
            requested_at = pending.get('requested_at')
            c.execute(
                """INSERT INTO users (username, password_hash, role, requested_at, created_at) 
                   VALUES (?, ?, 'user', ?, CURRENT_TIMESTAMP)""",
                (pending['username'], pending['password_hash'], requested_at)
            )
            c.execute("UPDATE pending_users SET status = 'approved' WHERE id = ?", (user_id,))
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"Error approving user: {e}")
        return False


def reject_pending_user(user_id: int) -> bool:
    """Reject a pending user request."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE pending_users SET status = 'rejected' WHERE id = ?", (user_id,))
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"Error rejecting user: {e}")
        return False


def check_pending_username_exists(username: str) -> bool:
    """Check if username exists in pending users."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM pending_users WHERE username = ? AND status = 'pending'", (username,))
            return c.fetchone() is not None
    except sqlite3.Error as e:
        print(f"Error checking pending username: {e}")
        return False
