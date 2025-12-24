"""
Intent Classifier Module
Uses pattern matching and optional LLM for interpreting user responses.
Handles table selection from natural language.
"""
from __future__ import annotations

import re
from typing import Optional, List, Dict, Any


def interpret_table_selection(
    user_message: str,
    available_tables: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Interpret which table the user wants from their natural language response.
    
    Strategies (in order):
    1. Exact name match
    2. Partial name match (fuzzy)
    3. Number-based selection ("use number 2")
    4. Description-based match
    5. Keyword extraction
    
    Args:
        user_message: The user's response text
        available_tables: List of table dicts with keys: cache_path, display_name, description (optional)
        
    Returns:
        The matched table dict, or None if ambiguous/no match
    """
    if not available_tables:
        return None
    
    if len(available_tables) == 1:
        return available_tables[0]
    
    user_lower = user_message.lower().strip()
    
    # Strategy 1: Exact name match
    for table in available_tables:
        name = table.get("display_name", "").lower()
        if name and name in user_lower:
            return table
    
    # Strategy 2: Number-based selection ("use number 2", "option 1", "the second one")
    number_match = _extract_number_selection(user_lower, len(available_tables))
    if number_match is not None:
        return available_tables[number_match]
    
    # Strategy 3: Ordinal selection ("first", "second", "third")
    ordinal_match = _extract_ordinal_selection(user_lower, len(available_tables))
    if ordinal_match is not None:
        return available_tables[ordinal_match]
    
    # Strategy 4: Partial name match - find best matching table
    best_match = _find_best_partial_match(user_lower, available_tables)
    if best_match:
        return best_match
    
    # Strategy 5: Description-based match
    for table in available_tables:
        desc = table.get("description", "").lower()
        if desc:
            # Check if user's message has significant overlap with description
            user_words = set(user_lower.split())
            desc_words = set(desc.split())
            # Exclude common words
            common_words = {"the", "a", "an", "is", "are", "with", "for", "to", "of", "and", "or", "in", "on"}
            user_significant = user_words - common_words
            desc_significant = desc_words - common_words
            
            if user_significant & desc_significant:  # Intersection
                return table
    
    # No confident match
    return None


def _extract_number_selection(text: str, max_num: int) -> Optional[int]:
    """Extract number-based selection from text."""
    # Patterns like "number 2", "option 3", "#1", "use 2"
    patterns = [
        r'number\s*(\d+)',
        r'option\s*(\d+)',
        r'#(\d+)',
        r'use\s+(\d+)$',
        r'^(\d+)$',
        r'^\s*(\d+)\s*$'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            num = int(match.group(1))
            if 1 <= num <= max_num:
                return num - 1  # Convert to 0-indexed
    
    return None


def _extract_ordinal_selection(text: str, max_num: int) -> Optional[int]:
    """Extract ordinal-based selection like 'first', 'second', etc."""
    ordinals = {
        "first": 0, "1st": 0,
        "second": 1, "2nd": 1,
        "third": 2, "3rd": 2,
        "fourth": 3, "4th": 3,
        "fifth": 4, "5th": 4,
        "last": max_num - 1 if max_num > 0 else None,
    }
    
    for ordinal, index in ordinals.items():
        if ordinal in text and index is not None and index < max_num:
            return index
    
    return None


def _find_best_partial_match(
    user_text: str,
    tables: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Find the best partial match based on word overlap."""
    user_words = set(user_text.lower().split())
    # Remove common filler words
    stop_words = {"the", "a", "an", "use", "try", "check", "look", "at", "in", "for", "one", "please", "can", "you"}
    user_words = user_words - stop_words
    
    if not user_words:
        return None
    
    best_table = None
    best_score = 0
    
    for table in tables:
        name_words = set(table.get("display_name", "").lower().split())
        name_words = name_words - stop_words
        
        # Calculate overlap score
        overlap = user_words & name_words
        if overlap:
            score = len(overlap) / max(len(user_words), len(name_words))
            if score > best_score:
                best_score = score
                best_table = table
    
    # Only return if we have a reasonable confidence
    if best_score >= 0.3:
        return best_table
    
    return None


def classify_user_intent(
    user_message: str,
    previous_context: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Classify the user's intent from their message.
    
    Returns:
        Dict with keys:
        - intent: 'TABLE_SELECTION' | 'DATA_QUERY' | 'FOLLOW_UP' | 'CLARIFICATION_RESPONSE'
        - confidence: float 0-1
        - details: any extracted info
    """
    user_lower = user_message.lower().strip()
    
    # Check if this is a table selection response
    table_selection_keywords = [
        "use the", "try the", "use", "try", "check the",
        "look at", "the one with", "number", "option",
        "first", "second", "third", "last"
    ]
    
    is_table_selection = any(kw in user_lower for kw in table_selection_keywords)
    
    # Check if previous context was awaiting clarification
    if previous_context and previous_context.get("awaiting_table_clarification"):
        if is_table_selection or len(user_message.split()) <= 5:
            return {
                "intent": "CLARIFICATION_RESPONSE",
                "confidence": 0.9,
                "details": {"raw_response": user_message}
            }
    
    # Check for follow-up indicators
    follow_up_keywords = ["also", "and", "more", "what about", "how about", "show me more", "break down"]
    is_follow_up = any(kw in user_lower for kw in follow_up_keywords)
    
    if is_follow_up and previous_context and previous_context.get("last_used_table"):
        return {
            "intent": "FOLLOW_UP",
            "confidence": 0.8,
            "details": {"use_previous_table": True}
        }
    
    # Default: treat as a new data query
    return {
        "intent": "DATA_QUERY",
        "confidence": 0.7,
        "details": {}
    }


def format_table_list_for_clarification(tables: List[Dict[str, Any]]) -> str:
    """
    Format a list of tables for display in a clarification message.
    """
    lines = []
    for i, table in enumerate(tables, 1):
        name = table.get("display_name", "Unknown")
        rows = table.get("n_rows")
        
        # Only show rows if available and > 0
        if rows and isinstance(rows, int) and rows > 0:
            rows_str = f"({rows:,} baris)"
        else:
            rows_str = ""
        
        line = f"{i}. {name} {rows_str}".strip()
        lines.append(line)
    
    return "\n".join(lines)


def generate_clarification_message(
    tried_tables: List[str],
    available_tables: List[Dict[str, Any]],
    original_question: str
) -> str:
    """
    Generate a user-friendly clarification message in Indonesian.
    """
    table_list = format_table_list_for_clarification(available_tables)
    
    if len(available_tables) == 1:
        # Only one table available but query failed
        return f"""Maaf, saya tidak dapat menemukan informasi yang Anda minta dalam data yang tersedia.

Mungkin pertanyaan perlu disampaikan dengan cara berbeda, atau data yang diminta belum tersedia dalam tabel.

Silakan coba pertanyaan lain atau minta saya menampilkan data yang tersedia."""
    
    # Multiple tables available
    message = f"""Saya belum menemukan data yang sesuai dengan pertanyaan Anda.

Data yang tersedia:
{table_list}

Bisa tolong jelaskan lebih spesifik data mana yang ingin Anda analisis?"""

    return message
