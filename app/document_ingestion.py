"""
Document Ingestion Module
Handles traversing OneDrive folders and ingesting documents to Qdrant.
"""
from __future__ import annotations

import logging
import hashlib
import time
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

from app.settings import AppSettings
from app.onedrive_documents import list_document_files, download_file, get_file_details
from app.document_processor import process_document, is_supported_document
from app.qdrant_service import (
    ensure_collection_exists, upsert_chunks, 
    delete_document_chunks, get_document_ids, get_collection_info
)

logger = logging.getLogger("app.document_ingestion")

settings = AppSettings()

# Supported document extensions (non-Excel)
SUPPORTED_EXTENSIONS = {".pdf", ".ppt", ".pptx", ".png", ".jpg", ".jpeg"}


def _file_to_doc_id(file_id: str, last_modified: str) -> str:
    """Generate document ID from file ID and last modified timestamp."""
    content = f"{file_id}:{last_modified}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _filter_supported_files(files: List[Dict]) -> List[Dict]:
    """Filter files to only supported document types (non-Excel)."""
    supported = []
    for f in files:
        name = f.get("name", "").lower()
        ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
        if ext in SUPPORTED_EXTENSIONS:
            supported.append(f)
    return supported


# =============================================================================
# OneDrive File Discovery
# =============================================================================

def discover_documents(root_path: str = None) -> List[Dict[str, Any]]:
    """
    Discover all supported documents in OneDrive folder.
    
    Args:
        root_path: OneDrive folder path (defaults to settings.document_root_path)
        
    Returns:
        List of file metadata dicts
    """
    root_path = root_path or settings.document_root_path
    
    if not root_path:
        logger.warning("DOCUMENT_ROOT_PATH not configured")
        return []
    
    try:
        # Use document-specific file listing with correct extensions
        all_files = list_document_files(root_path)
        
        # Filter to supported types (already done by list_document_files, but double-check)
        supported = _filter_supported_files(all_files)
        
        logger.info("Discovered %d supported documents out of %d total files", 
                   len(supported), len(all_files))
        
        return supported
        
    except Exception as e:
        logger.error("Failed to discover documents: %s", e)
        return []


def get_local_inventory() -> Dict[str, Dict]:
    """
    Get inventory of already-ingested documents from Qdrant.
    
    Returns:
        Dict mapping doc_id to metadata
    """
    try:
        doc_ids = get_document_ids()
        return {doc_id: {"doc_id": doc_id} for doc_id in doc_ids}
    except Exception as e:
        logger.error("Failed to get local inventory: %s", e)
        return {}


# =============================================================================
# Document Ingestion
# =============================================================================

def ingest_single_document(
    file_info: Dict[str, Any],
    chunk_size: int = 800,
    chunk_overlap: int = 100
) -> Optional[Dict[str, Any]]:
    """
    Ingest a single document from OneDrive.
    
    Args:
        file_info: File metadata from OneDrive (must have downloadUrl, name, id)
        chunk_size: Target chunk size
        chunk_overlap: Overlap between chunks
        
    Returns:
        Ingestion result dict or None on failure
    """
    filename = file_info.get("name", "unknown")
    file_id = file_info.get("id", "")
    download_url = file_info.get("downloadUrl")
    last_modified = file_info.get("lastModified", "")
    
    logger.info("Ingesting document: %s", filename)
    
    # Generate doc_id
    doc_id = _file_to_doc_id(file_id, last_modified)
    
    try:
        # Refresh download URL if needed
        if not download_url:
            token = get_access_token()
            details = get_file_details(token, file_id)
            download_url = details.get("@microsoft.graph.downloadUrl")
        
        if not download_url:
            logger.error("No download URL for %s", filename)
            return {"error": "No download URL", "filename": filename}
        
        # Download file
        file_bytes = download_file(download_url)
        
        if not file_bytes:
            logger.error("Empty file content for %s", filename)
            return {"error": "Empty file", "filename": filename}
        
        # Process document
        result = process_document(file_bytes, filename, chunk_size, chunk_overlap)
        
        if not result or result.get("error"):
            return {"error": result.get("error", "Processing failed"), "filename": filename}
        
        if not result.get("chunks"):
            logger.warning("No chunks extracted from %s", filename)
            return {"warning": "No text extracted", "filename": filename, "doc_id": doc_id}
        
        # Prepare chunks for Qdrant
        chunks_for_upsert = []
        for i, chunk_text in enumerate(result["chunks"]):
            chunks_for_upsert.append({
                "text": chunk_text,
                "doc_id": doc_id,
                "chunk_index": i,
                "filename": filename,
                "doc_type": result["doc_type"],
                "path": file_info.get("path", ""),
                "web_url": file_info.get("webUrl", ""),
                "file_id": file_id
            })
        
        # Delete old chunks for this doc and upsert new ones
        delete_document_chunks(doc_id)
        upserted = upsert_chunks(chunks_for_upsert)
        
        return {
            "success": True,
            "filename": filename,
            "doc_id": doc_id,
            "chunks_count": upserted,
            "char_count": result.get("char_count", 0),
            "doc_type": result["doc_type"]
        }
        
    except Exception as e:
        logger.error("Failed to ingest %s: %s", filename, e)
        return {"error": str(e), "filename": filename}


def ingest_all_documents(
    dry_run: bool = False,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
    skip_existing: bool = True
) -> Dict[str, Any]:
    """
    Ingest all supported documents from OneDrive.
    
    Args:
        dry_run: If True, only discover files without ingesting
        chunk_size: Target chunk size
        chunk_overlap: Overlap between chunks
        skip_existing: Skip already-ingested documents
        
    Returns:
        Summary of ingestion results
    """
    # Ensure collection exists
    ensure_collection_exists()
    
    # Discover documents
    files = discover_documents()
    
    if not files:
        return {
            "total_files": 0,
            "message": "No supported documents found"
        }
    
    if dry_run:
        return {
            "mode": "dry_run",
            "total_files": len(files),
            "files": [
                {
                    "name": f["name"],
                    "path": f.get("path", ""),
                    "size_bytes": f.get("size", 0),
                    "id": f.get("id", "")
                }
                for f in files
            ]
        }
    
    # Get existing inventory if skipping
    existing_doc_ids: Set[str] = set()
    if skip_existing:
        existing_doc_ids = set(get_document_ids())
        logger.info("Found %d existing documents in Qdrant", len(existing_doc_ids))
    
    # Ingest each file
    results = {
        "total_files": len(files),
        "processed": 0,
        "skipped": 0,
        "success": 0,
        "failed": 0,
        "details": []
    }
    
    for file_info in files:
        file_id = file_info.get("id", "")
        last_modified = file_info.get("lastModified", "")
        doc_id = _file_to_doc_id(file_id, last_modified)
        
        # Skip if already exists
        if skip_existing and doc_id in existing_doc_ids:
            logger.debug("Skipping already-ingested: %s", file_info["name"])
            results["skipped"] += 1
            continue
        
        results["processed"] += 1
        
        # Ingest with rate limiting
        result = ingest_single_document(file_info, chunk_size, chunk_overlap)
        
        if result and result.get("success"):
            results["success"] += 1
        else:
            results["failed"] += 1
        
        results["details"].append(result)
        
        # Small delay to avoid rate limits
        time.sleep(0.5)
    
    # Get final collection stats
    collection_info = get_collection_info()
    results["collection_stats"] = collection_info
    
    logger.info("Ingestion complete: %d success, %d failed, %d skipped",
               results["success"], results["failed"], results["skipped"])
    
    return results


# =============================================================================
# Utility Functions
# =============================================================================

def get_ingestion_status() -> Dict[str, Any]:
    """Get current ingestion status."""
    collection_info = get_collection_info()
    doc_ids = get_document_ids()
    
    return {
        "collection": collection_info,
        "documents_count": len(doc_ids),
        "document_ids": doc_ids[:10],  # First 10 for preview
        "has_more": len(doc_ids) > 10
    }


def clear_all_documents() -> bool:
    """Clear all documents from collection."""
    try:
        from app.qdrant_service import delete_collection
        delete_collection()
        ensure_collection_exists()
        logger.info("Cleared all documents from collection")
        return True
    except Exception as e:
        logger.error("Failed to clear documents: %s", e)
        return False
