"""
Qdrant Service Module
Handles Qdrant vector database operations for document storage and search.
"""
from __future__ import annotations

import logging
import hashlib
from typing import List, Dict, Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, SparseVectorParams, SparseIndexParams,
    Distance, PointStruct, Filter, FieldCondition, MatchValue,
    Prefetch, FusionQuery, SparseVector
)

from app.settings import AppSettings
from app.embeddings import embed_text, embed_query, generate_bm25_vector, EmbeddingTask

logger = logging.getLogger("app.qdrant_service")

settings = AppSettings()

# Vector names
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "bm25"

# Qdrant client singleton
_qdrant_client: Optional[QdrantClient] = None


def _get_qdrant_client() -> QdrantClient:
    """Get or create Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        if not settings.qdrant_url:
            raise ValueError("QDRANT_URL is not configured.")
        
        logger.info("Connecting to Qdrant at %s", settings.qdrant_url)
        _qdrant_client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            timeout=60
        )
    return _qdrant_client


def _text_to_point_id(text: str) -> int:
    """Generate a consistent point ID from text using SHA1."""
    sha1 = hashlib.sha1(text.encode()).hexdigest()
    return int(sha1[:16], 16)


# =============================================================================
# Collection Management
# =============================================================================

def ensure_collection_exists(collection_name: str = None) -> None:
    """
    Ensure the document chunks collection exists with hybrid vector config.
    
    Args:
        collection_name: Name of collection (defaults to settings.qdrant_collection)
    """
    collection_name = collection_name or settings.qdrant_collection
    client = _get_qdrant_client()
    
    try:
        collections = client.get_collections()
        existing = [c.name for c in collections.collections]
        
        if collection_name not in existing:
            logger.info("Creating collection: %s", collection_name)
            client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    DENSE_VECTOR_NAME: VectorParams(
                        size=settings.embed_dim,
                        distance=Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    SPARSE_VECTOR_NAME: SparseVectorParams(
                        index=SparseIndexParams(on_disk=False)
                    )
                }
            )
            
            # Create payload indexes for efficient filtering
            client.create_payload_index(
                collection_name=collection_name,
                field_name="doc_id",
                field_schema="keyword"
            )
            client.create_payload_index(
                collection_name=collection_name,
                field_name="filename",
                field_schema="keyword"
            )
            logger.info("Collection %s created with hybrid vectors", collection_name)
        else:
            logger.debug("Collection %s already exists", collection_name)
            
    except Exception as e:
        logger.error("Failed to ensure collection: %s", e)
        raise


def delete_collection(collection_name: str = None) -> bool:
    """Delete a collection."""
    collection_name = collection_name or settings.qdrant_collection
    client = _get_qdrant_client()
    
    try:
        client.delete_collection(collection_name)
        logger.info("Deleted collection: %s", collection_name)
        return True
    except Exception as e:
        logger.warning("Failed to delete collection %s: %s", collection_name, e)
        return False


def get_collection_info(collection_name: str = None) -> Optional[Dict]:
    """Get collection statistics."""
    collection_name = collection_name or settings.qdrant_collection
    client = _get_qdrant_client()
    
    try:
        info = client.get_collection(collection_name)
        return {
            "name": collection_name,
            "points_count": info.points_count,
            "vectors_count": info.vectors_count,
            "status": info.status.value if info.status else "unknown"
        }
    except Exception as e:
        logger.warning("Failed to get collection info: %s", e)
        return None


# =============================================================================
# Document Operations
# =============================================================================

def upsert_chunks(
    chunks: List[Dict[str, Any]],
    collection_name: str = None
) -> int:
    """
    Upsert document chunks to Qdrant.
    
    Args:
        chunks: List of chunk dicts with keys:
            - text: Chunk text content
            - doc_id: Parent document ID
            - chunk_index: Index of chunk in document
            - filename: Source filename
            - ... (any other metadata)
        collection_name: Target collection
        
    Returns:
        Number of chunks upserted
    """
    if not chunks:
        return 0
    
    collection_name = collection_name or settings.qdrant_collection
    client = _get_qdrant_client()
    
    # Prepare points
    points = []
    texts = [c["text"] for c in chunks]
    
    # Generate embeddings in batch
    dense_vectors = []
    for text in texts:
        vec = embed_text(text, task=EmbeddingTask.DOCUMENT)
        dense_vectors.append(vec)
    
    for i, chunk in enumerate(chunks):
        # Generate point ID from doc_id + chunk_index
        point_id_str = f"{chunk['doc_id']}_{chunk.get('chunk_index', i)}"
        point_id = _text_to_point_id(point_id_str)
        
        # Generate sparse vector
        sparse = generate_bm25_vector(chunk["text"])
        
        # Build payload
        payload = {
            "doc_id": chunk["doc_id"],
            "chunk_index": chunk.get("chunk_index", i),
            "text": chunk["text"],
            "filename": chunk.get("filename", ""),
            "doc_type": chunk.get("doc_type", ""),
            "path": chunk.get("path", ""),
            "web_url": chunk.get("web_url", ""),
        }
        
        points.append(PointStruct(
            id=point_id,
            vector={
                DENSE_VECTOR_NAME: dense_vectors[i],
                SPARSE_VECTOR_NAME: SparseVector(
                    indices=sparse["indices"],
                    values=sparse["values"]
                )
            },
            payload=payload
        ))
    
    # Upsert in batches
    batch_size = 100
    for start in range(0, len(points), batch_size):
        batch = points[start:start + batch_size]
        client.upsert(collection_name=collection_name, points=batch, wait=True)
    
    logger.info("Upserted %d chunks to %s", len(points), collection_name)
    return len(points)


def delete_document_chunks(doc_id: str, collection_name: str = None) -> bool:
    """
    Delete all chunks for a document.
    
    Args:
        doc_id: Document ID to delete
        collection_name: Target collection
        
    Returns:
        True if successful
    """
    collection_name = collection_name or settings.qdrant_collection
    client = _get_qdrant_client()
    
    try:
        client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
            wait=True
        )
        logger.info("Deleted chunks for doc_id: %s", doc_id)
        return True
    except Exception as e:
        logger.error("Failed to delete chunks for %s: %s", doc_id, e)
        return False


def get_document_ids(collection_name: str = None) -> List[str]:
    """Get all unique document IDs in collection."""
    collection_name = collection_name or settings.qdrant_collection
    client = _get_qdrant_client()
    
    doc_ids = set()
    offset = None
    
    try:
        while True:
            points, offset = client.scroll(
                collection_name=collection_name,
                limit=500,
                with_payload=["doc_id"],
                with_vectors=False,
                offset=offset
            )
            
            for point in points:
                if point.payload and "doc_id" in point.payload:
                    doc_ids.add(point.payload["doc_id"])
            
            if offset is None:
                break
                
    except Exception as e:
        logger.error("Failed to get document IDs: %s", e)
    
    return list(doc_ids)


# =============================================================================
# Search Operations
# =============================================================================

def search_chunks(
    query: str,
    limit: int = 5,
    collection_name: str = None
) -> List[Dict[str, Any]]:
    """
    Search for relevant chunks using hybrid search (dense + sparse + RRF fusion).
    Falls back to dense-only search if BM25 is unavailable.
    
    Args:
        query: Search query text
        limit: Maximum number of results
        collection_name: Target collection
        
    Returns:
        List of matching chunks with scores
    """
    collection_name = collection_name or settings.qdrant_collection
    client = _get_qdrant_client()
    
    # Generate query embeddings
    dense_vector = embed_query(query)
    sparse_vector = generate_bm25_vector(query)
    
    # Check if BM25 is available
    has_bm25 = sparse_vector.get("indices") and len(sparse_vector["indices"]) > 0
    
    try:
        if has_bm25:
            # Hybrid search with RRF fusion
            results = client.query_points(
                collection_name=collection_name,
                prefetch=[
                    Prefetch(
                        query=dense_vector,
                        using=DENSE_VECTOR_NAME,
                        limit=limit * 2
                    ),
                    Prefetch(
                        query=SparseVector(
                            indices=sparse_vector["indices"],
                            values=sparse_vector["values"]
                        ),
                        using=SPARSE_VECTOR_NAME,
                        limit=limit * 2
                    )
                ],
                query=FusionQuery(fusion="rrf"),
                limit=limit,
                with_payload=True
            )
        else:
            # Dense-only search (fallback when BM25 unavailable)
            logger.warning("BM25 unavailable, using dense-only search")
            results = client.query_points(
                collection_name=collection_name,
                query=dense_vector,
                using=DENSE_VECTOR_NAME,
                limit=limit,
                with_payload=True
            )
        
        formatted = []
        for point in results.points:
            formatted.append({
                "id": point.id,
                "score": point.score,
                "text": point.payload.get("text", ""),
                "doc_id": point.payload.get("doc_id", ""),
                "filename": point.payload.get("filename", ""),
                "chunk_index": point.payload.get("chunk_index", 0),
                "path": point.payload.get("path", ""),
                "web_url": point.payload.get("web_url", "")
            })
        
        return formatted
        
    except Exception as e:
        logger.error("Search failed: %s", e)
        return []

