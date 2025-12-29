"""
Embeddings Module
Handles Gemini embeddings and BM25 sparse vector generation.
"""
from __future__ import annotations

import logging
import random
import time
from enum import Enum
from threading import Lock
from typing import List, Sequence, Dict

import google.genai as genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.settings import AppSettings

logger = logging.getLogger("app.embeddings")

settings = AppSettings()

# Gemini client singleton
_CLIENT_LOCK = Lock()
_CLIENT = None

# BM25 model singleton
_BM25_LOCK = Lock()
_BM25_MODEL = None

# Configuration
EMBED_BATCH_SIZE = 20
EMBED_MAX_RETRIES = 3


class EmbeddingTask(str, Enum):
    """Embedding task types for Gemini."""
    DOCUMENT = "retrieval_document"
    QUERY = "retrieval_query"


def _get_client() -> genai.Client:
    """Get or create Gemini client singleton."""
    global _CLIENT
    if _CLIENT is None:
        with _CLIENT_LOCK:
            if _CLIENT is None:
                if not settings.gemini_api_key:
                    raise RuntimeError("GEMINI_API_KEY is not configured.")
                _CLIENT = genai.Client(api_key=settings.gemini_api_key)
    return _CLIENT


def _get_bm25_model():
    """Lazy load BM25 model."""
    global _BM25_MODEL
    if _BM25_MODEL is None:
        with _BM25_LOCK:
            if _BM25_MODEL is None:
                from fastembed import SparseTextEmbedding
                _BM25_MODEL = SparseTextEmbedding(model_name="Qdrant/bm25")
                logger.info("Loaded BM25 model for sparse vectors")
    return _BM25_MODEL


def ensure_embeddings_ready() -> None:
    """Ensure the Gemini client can be initialized."""
    _get_client()
    logger.info("Gemini embeddings client ready")


# =============================================================================
# Gemini Dense Embeddings
# =============================================================================

def embed_texts(
    texts: Sequence[str],
    *,
    task: EmbeddingTask = EmbeddingTask.DOCUMENT,
) -> List[List[float]]:
    """
    Generate embeddings for multiple texts using Gemini.
    
    Args:
        texts: List of texts to embed
        task: Embedding task type (DOCUMENT or QUERY)
        
    Returns:
        List of embedding vectors
    """
    if not texts:
        return []

    client = _get_client()
    vectors: List[List[float]] = []

    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = [t or "" for t in texts[start:start + EMBED_BATCH_SIZE]]
        
        for attempt in range(1, EMBED_MAX_RETRIES + 1):
            try:
                response = client.models.embed_content(
                    model=settings.embed_model,
                    contents=batch,
                    config=genai_types.EmbedContentConfig(
                        output_dimensionality=settings.embed_dim,
                        task_type=task.value,
                    ),
                )
                
                embeddings = response.embeddings or []
                if len(embeddings) != len(batch):
                    raise RuntimeError("Embedding response size mismatch.")
                
                vectors.extend([embed.values or [] for embed in embeddings])
                break
                
            except genai_errors.ClientError as exc:
                if attempt >= EMBED_MAX_RETRIES:
                    raise
                wait = 1 + attempt * 2
                logger.warning("Embedding client error (attempt %d/%d): %s", attempt, EMBED_MAX_RETRIES, exc)
                time.sleep(wait)
                
            except Exception as exc:
                if attempt >= EMBED_MAX_RETRIES:
                    raise
                wait = 2 ** attempt + random.uniform(0, 1)
                logger.warning("Embedding error (attempt %d/%d): %s", attempt, EMBED_MAX_RETRIES, exc)
                time.sleep(wait)

    return vectors


def embed_text(text: str, task: EmbeddingTask = EmbeddingTask.DOCUMENT) -> List[float]:
    """
    Generate embedding for a single text.
    
    Args:
        text: Text to embed
        task: Embedding task type
        
    Returns:
        Embedding vector
    """
    results = embed_texts([text], task=task)
    return results[0] if results else [0.0] * settings.embed_dim


def embed_query(query: str) -> List[float]:
    """
    Generate embedding for a search query.
    
    Args:
        query: Search query text
        
    Returns:
        Query embedding vector
    """
    return embed_text(query, task=EmbeddingTask.QUERY)


# =============================================================================
# BM25 Sparse Vectors
# =============================================================================

def generate_bm25_vector(text: str) -> Dict:
    """
    Generate BM25 sparse vector from text.
    
    Args:
        text: Text to generate sparse vector for
        
    Returns:
        Dict with 'indices' and 'values' keys
    """
    if not text or not text.strip():
        return {"indices": [], "values": []}

    try:
        model = _get_bm25_model()
        embeddings = list(model.embed([text]))
        
        if not embeddings:
            return {"indices": [], "values": []}

        sparse_vector = embeddings[0]
        return {
            "indices": sparse_vector.indices.tolist(),
            "values": sparse_vector.values.tolist(),
        }
    except Exception as exc:
        logger.warning(f"Failed to generate BM25 vector: {exc}")
        return {"indices": [], "values": []}
