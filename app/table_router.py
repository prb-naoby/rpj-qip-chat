"""
Table Router Module
Uses LLM to intelligently route user questions to the most relevant tables.
"""
from __future__ import annotations

import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import pandas as pd
from openai import OpenAI

from .settings import AppSettings
from .datasets import CachedDataInfo, list_all_cached_data
from app.logger import get_chat_logger

settings = AppSettings()
logger = get_chat_logger()


@dataclass
class TableRanking:
    """Result of table routing."""
    table: CachedDataInfo
    score: int  # 0-100
    reason: str  # Short explanation


_ROUTER_PROMPT = """\
You are a data table router. Given a user question and available tables, rank which tables are most likely to answer the question.

## User Question:
{question}

## Available Tables:
{tables_context}

## Task:
Return a JSON array ranking the TOP 3 most relevant tables (or fewer if less than 3 tables exist).
Each item must have: "index" (1-based), "score" (0-100), "reason" (max 15 words).

## Rules:
- Score 80-100: Table clearly contains the data needed
- Score 50-79: Table might contain relevant data
- Score 0-49: Table unlikely to help
- Only include tables with score >= 30
- Be concise - max 15 words per reason

## Example Output:
```json
[
  {{"index": 1, "score": 95, "reason": "Contains RFT metrics by production line"}},
  {{"index": 3, "score": 60, "reason": "Has production data but unclear columns"}}
]
```

Return ONLY the JSON array, no other text.
"""


def _build_table_context(tables: List[CachedDataInfo]) -> str:
    """Build context string describing available tables."""
    lines = []
    for i, t in enumerate(tables, 1):
        # Get column names from parquet if possible
        columns = []
        try:
            df = pd.read_parquet(t.cache_path, columns=None)
            columns = list(df.columns)[:15]  # Limit to 15 columns
            if len(df.columns) > 15:
                columns.append(f"... +{len(df.columns) - 15} more")
        except Exception:
            columns = ["(unable to read columns)"]
        
        desc = t.description or "No description"
        if len(desc) > 100:
            desc = desc[:97] + "..."
        
        lines.append(
            f"{i}. **{t.display_name}** ({t.n_rows} rows)\n"
            f"   Description: {desc}\n"
            f"   Columns: {', '.join(columns)}"
        )
    
    return "\n\n".join(lines)


def route_question_to_tables(
    question: str,
    tables: List[CachedDataInfo] = None,
    api_key: str = None
) -> List[TableRanking]:
    """
    Use LLM to rank tables by relevance to the question.
    
    Args:
        question: User's question
        tables: List of available tables (if None, loads all cached tables)
        api_key: OpenAI API key (if None, uses settings)
    
    Returns:
        List of TableRanking sorted by score (highest first)
    """
    if tables is None:
        tables = list_all_cached_data()
    
    if not tables:
        logger.info("Router: No tables available")
        return []
    
    if len(tables) == 1:
        # Only one table - no need to route
        return [TableRanking(
            table=tables[0],
            score=100,
            reason="Only available table"
        )]
    
    api_key = api_key or settings.openai_api_key
    if not api_key:
        logger.warning("Router: No API key, falling back to first table")
        return [TableRanking(table=tables[0], score=50, reason="Fallback - no API key")]
    
    try:
        client = OpenAI(api_key=api_key)
        tables_context = _build_table_context(tables)
        
        logger.info(f"Router: Routing question '{question[:50]}...' across {len(tables)} tables")
        
        response = client.responses.create(
            model=settings.default_llm_model,
            instructions=_ROUTER_PROMPT.format(
                question=question,
                tables_context=tables_context
            ),
            input="Rank the tables and return JSON.",
        )
        
        raw_output = response.output_text.strip()
        logger.info(f"Router raw output: {raw_output[:200]}...")
        
        # Parse JSON
        rankings = _parse_router_response(raw_output, tables)
        
        if not rankings:
            # Fallback: return first table
            logger.warning("Router: Failed to parse, returning first table")
            return [TableRanking(table=tables[0], score=50, reason="Routing failed - using default")]
        
        return rankings
        
    except Exception as e:
        logger.error(f"Router error: {e}")
        # Fallback: return first table
        return [TableRanking(table=tables[0], score=50, reason=f"Error: {str(e)[:30]}")]


def _parse_router_response(raw: str, tables: List[CachedDataInfo]) -> List[TableRanking]:
    """Parse the LLM's JSON response into TableRanking objects."""
    # Clean up markdown code blocks if present
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0]
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0]
    
    raw = raw.strip()
    
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"Router: Invalid JSON: {raw[:100]}")
        return []
    
    if not isinstance(data, list):
        logger.warning("Router: Response is not a list")
        return []
    
    rankings = []
    for item in data:
        try:
            idx = int(item.get("index", 0)) - 1  # Convert to 0-based
            score = int(item.get("score", 0))
            reason = str(item.get("reason", ""))[:50]  # Limit reason length
            
            if 0 <= idx < len(tables) and score >= 30:
                rankings.append(TableRanking(
                    table=tables[idx],
                    score=score,
                    reason=reason
                ))
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Router: Skipping invalid item: {item}, error: {e}")
            continue
    
    # Sort by score descending
    rankings.sort(key=lambda x: x.score, reverse=True)
    
    # Limit to top 3
    return rankings[:3]


def format_routing_explanation(rankings: List[TableRanking]) -> str:
    """Format routing results for display in the explanation section."""
    if not rankings:
        return "No tables were found to match your question."
    
    if len(rankings) == 1 and rankings[0].reason == "Only available table":
        return f"Using '{rankings[0].table.display_name}' (the only available table)."
    
    lines = ["**Table Selection:**"]
    for r in rankings[:3]:
        lines.append(f"• {r.table.display_name} (score: {r.score}%): {r.reason}")
    
    return "\n".join(lines)
