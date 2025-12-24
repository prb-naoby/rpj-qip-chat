"""
Chat Service Module
Handles persistence for chat sessions and messages using SQLite.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any
import sqlite3
from api.database import _get_connection
from app.datasets import list_all_cached_data
from app.redis_client import redis_client

def rank_tables_logic(question: str) -> List[Dict[str, Any]]:
    """Rank tables based on question relevance."""
    cached_list = list_all_cached_data()
    if not cached_list:
        return []
    
    question_lower = question.lower()
    words = [w for w in question_lower.split() if len(w) > 3]
    
    ranked = []
    for table in cached_list:
        score = 0.0
        
        # Match in display name
        name_lower = table.display_name.lower()
        for word in words:
            if word in name_lower:
                score += 2.0
        
        # Match in description
        if table.description:
            desc_lower = table.description.lower()
            for word in words:
                if word in desc_lower:
                    score += 1.0
        
        ranked.append({
            "cache_path": str(table.cache_path),
            "display_name": table.display_name,
            "n_rows": table.n_rows,
            "score": score,
            "description": table.description
        })
    
    ranked.sort(key=lambda x: (-x["score"], x["display_name"]))
    return ranked


def create_chat(user_id: int, title: str = "New Chat") -> Dict[str, Any]:
    """Create a new chat session."""
    chat_id = str(uuid.uuid4())
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO chats (id, user_id, title) VALUES (?, ?, ?)",
                (chat_id, user_id, title)
            )
            conn.commit()
            
            # Return the created chat object
            chat = {
                "id": chat_id,
                "user_id": user_id,
                "title": title,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            # Invalidate user chats cache
            redis_client.delete(f"user:{user_id}:chats")
            return chat
    except sqlite3.Error as e:
        print(f"Error creating chat: {e}")
        return None

def get_chats(user_id: int) -> List[Dict[str, Any]]:
    """List all chats for a user, ordered by most recent update."""
    cache_key = f"user:{user_id}:chats"
    cached = redis_client.get(cache_key)
    if cached:
        return cached

    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT * FROM chats WHERE user_id = ? ORDER BY updated_at DESC", 
                (user_id,)
            )
            rows = c.fetchall()
            results = [dict(row) for row in rows]
            redis_client.set(cache_key, results, expire_seconds=300) # Cache for 5 mins
            return results
    except sqlite3.Error as e:
        print(f"Error listing chats: {e}")
        return []

def get_chat(chat_id: str, user_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific chat session securely (verifying user ownership)."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            # Verify ownership
            c.execute("SELECT * FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id))
            row = c.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        print(f"Error getting chat: {e}")
        return None


def update_chat(chat_id: str, user_id: int, title: str) -> Optional[Dict[str, Any]]:
    """Update a chat session (e.g. rename)."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute(
                "UPDATE chats SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (title, chat_id, user_id)
            )
            if c.rowcount > 0:
                conn.commit()
                # Invalidate user chats cache
                redis_client.delete(f"user:{user_id}:chats")
                return get_chat(chat_id, user_id)
            return None
    except sqlite3.Error as e:
        print(f"Error updating chat: {e}")
        return None

def delete_chat(chat_id: str, user_id: int) -> bool:
    """Delete a chat session."""
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            # Verify ownership and delete
            c.execute("DELETE FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id))
            affected = c.rowcount
            conn.commit()
            if affected > 0:
                redis_client.delete(f"user:{user_id}:chats")
            return affected > 0
    except sqlite3.Error as e:
        print(f"Error deleting chat: {e}")
        return False

def add_message(chat_id: str, role: str, content: str, metadata: Dict = None) -> Dict[str, Any]:
    """Add a message to a chat."""
    msg_id = str(uuid.uuid4())
    metadata_json = json.dumps(metadata) if metadata else None
    
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute(
                """INSERT INTO messages (id, chat_id, role, content, metadata) 
                   VALUES (?, ?, ?, ?, ?)""",
                (msg_id, chat_id, role, content, metadata_json)
            )
            
            # Update parent chat's updated_at
            c.execute(
                "UPDATE chats SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (chat_id,)
            )
            
            conn.commit()

            # Invalidate caches
            redis_client.delete(f"chat:{chat_id}:messages")
            # Also invalidate chats list because updated_at changed
            # We need user_id to invalidate user chats list efficiently. 
            # Ideally we'd have user_id, but here we might just let it expire or fetch chat first.
            # Optimized: Just expire the messages cache. The chat list update timestamp might be slightly stale in list view until refresh, which is acceptable.
            
            return {
                "id": msg_id,
                "chat_id": chat_id,
                "role": role,
                "content": content,
                "metadata": metadata,
                "created_at": datetime.now().isoformat()
            }
    except sqlite3.Error as e:
        print(f"Error adding message: {e}")
        return None

def get_messages(chat_id: str) -> List[Dict[str, Any]]:
    """Get all messages for a chat."""
    cache_key = f"chat:{chat_id}:messages"
    cached = redis_client.get(cache_key)
    if cached:
        return cached

    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at ASC",
                (chat_id,)
            )
            rows = c.fetchall()
            
            # Parse metadata JSON
            results = []
            for row in rows:
                d = dict(row)
                if d.get("metadata"):
                    try:
                        d["metadata"] = json.loads(d["metadata"])
                    except:
                        d["metadata"] = {}
                results.append(d)
                
            redis_client.set(cache_key, results, expire_seconds=3600) # Cache for 1 hour
            return results
    except sqlite3.Error as e:
        print(f"Error getting messages: {e}")
        return []
