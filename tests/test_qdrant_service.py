"""
Test Qdrant Service Module (TDD)
Tests for Qdrant operations including collection management and search.
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestQdrantService:
    """Test suite for qdrant_service module."""
    
    # -------------------------------------------------------------------------
    # Collection Management Tests
    # -------------------------------------------------------------------------
    
    def test_ensure_collection_exists_creates_new(self):
        """Test creating a new collection."""
        with patch('app.qdrant_service._get_qdrant_client') as mock_get_client:
            mock_client = Mock()
            mock_collections = Mock()
            mock_collections.collections = []
            mock_client.get_collections.return_value = mock_collections
            mock_get_client.return_value = mock_client
            
            from app.qdrant_service import ensure_collection_exists
            ensure_collection_exists("test_collection")
            
            mock_client.create_collection.assert_called_once()
    
    def test_ensure_collection_exists_already_exists(self):
        """Test when collection already exists."""
        with patch('app.qdrant_service._get_qdrant_client') as mock_get_client:
            mock_client = Mock()
            mock_collection = Mock()
            mock_collection.name = "test_collection"
            mock_collections = Mock()
            mock_collections.collections = [mock_collection]
            mock_client.get_collections.return_value = mock_collections
            mock_get_client.return_value = mock_client
            
            from app.qdrant_service import ensure_collection_exists
            ensure_collection_exists("test_collection")
            
            mock_client.create_collection.assert_not_called()
    
    def test_get_collection_info(self):
        """Test getting collection info."""
        with patch('app.qdrant_service._get_qdrant_client') as mock_get_client:
            mock_client = Mock()
            mock_info = Mock()
            mock_info.points_count = 100
            mock_info.vectors_count = 100
            mock_info.status = Mock(value="green")
            mock_client.get_collection.return_value = mock_info
            mock_get_client.return_value = mock_client
            
            from app.qdrant_service import get_collection_info
            result = get_collection_info("test_collection")
            
            assert result["points_count"] == 100
            assert result["status"] == "green"
    
    # -------------------------------------------------------------------------
    # Document Operations Tests
    # -------------------------------------------------------------------------
    
    def test_upsert_chunks(self):
        """Test upserting document chunks."""
        with patch('app.qdrant_service._get_qdrant_client') as mock_get_client:
            with patch('app.qdrant_service.embed_text') as mock_embed:
                with patch('app.qdrant_service.generate_bm25_vector') as mock_bm25:
                    mock_client = Mock()
                    mock_get_client.return_value = mock_client
                    mock_embed.return_value = [0.1] * 768
                    mock_bm25.return_value = {"indices": [1, 2], "values": [0.5, 0.3]}
                    
                    from app.qdrant_service import upsert_chunks
                    
                    chunks = [
                        {"text": "Chunk 1", "doc_id": "doc1", "chunk_index": 0, "filename": "test.pdf"},
                        {"text": "Chunk 2", "doc_id": "doc1", "chunk_index": 1, "filename": "test.pdf"}
                    ]
                    
                    result = upsert_chunks(chunks, "test_collection")
                    
                    assert result == 2
                    mock_client.upsert.assert_called()
    
    def test_upsert_chunks_empty(self):
        """Test upserting empty chunk list."""
        from app.qdrant_service import upsert_chunks
        
        result = upsert_chunks([], "test_collection")
        
        assert result == 0
    
    def test_delete_document_chunks(self):
        """Test deleting document chunks."""
        with patch('app.qdrant_service._get_qdrant_client') as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client
            
            from app.qdrant_service import delete_document_chunks
            
            result = delete_document_chunks("doc123", "test_collection")
            
            assert result is True
            mock_client.delete.assert_called_once()
    
    def test_get_document_ids(self):
        """Test getting document IDs."""
        with patch('app.qdrant_service._get_qdrant_client') as mock_get_client:
            mock_client = Mock()
            mock_points = [
                Mock(payload={"doc_id": "doc1"}),
                Mock(payload={"doc_id": "doc2"}),
                Mock(payload={"doc_id": "doc1"})  # Duplicate
            ]
            mock_client.scroll.return_value = (mock_points, None)
            mock_get_client.return_value = mock_client
            
            from app.qdrant_service import get_document_ids
            
            result = get_document_ids("test_collection")
            
            assert len(result) == 2  # Unique IDs
            assert "doc1" in result
            assert "doc2" in result
    
    # -------------------------------------------------------------------------
    # Search Tests
    # -------------------------------------------------------------------------
    
    def test_search_chunks(self):
        """Test hybrid search for chunks."""
        with patch('app.qdrant_service._get_qdrant_client') as mock_get_client:
            with patch('app.qdrant_service.embed_query') as mock_embed:
                with patch('app.qdrant_service.generate_bm25_vector') as mock_bm25:
                    mock_client = Mock()
                    mock_point = Mock()
                    mock_point.id = 12345
                    mock_point.score = 0.85
                    mock_point.payload = {
                        "text": "Found chunk text",
                        "doc_id": "doc1",
                        "filename": "test.pdf",
                        "chunk_index": 0
                    }
                    mock_results = Mock()
                    mock_results.points = [mock_point]
                    mock_client.query_points.return_value = mock_results
                    mock_get_client.return_value = mock_client
                    mock_embed.return_value = [0.1] * 768
                    mock_bm25.return_value = {"indices": [1, 2], "values": [0.5, 0.3]}
                    
                    from app.qdrant_service import search_chunks
                    
                    results = search_chunks("test query", limit=5, collection_name="test_collection")
                    
                    assert len(results) == 1
                    assert results[0]["score"] == 0.85
                    assert results[0]["text"] == "Found chunk text"
    
    def test_search_chunks_empty_results(self):
        """Test search with no results."""
        with patch('app.qdrant_service._get_qdrant_client') as mock_get_client:
            with patch('app.qdrant_service.embed_query') as mock_embed:
                with patch('app.qdrant_service.generate_bm25_vector') as mock_bm25:
                    mock_client = Mock()
                    mock_results = Mock()
                    mock_results.points = []
                    mock_client.query_points.return_value = mock_results
                    mock_get_client.return_value = mock_client
                    mock_embed.return_value = [0.1] * 768
                    mock_bm25.return_value = {"indices": [], "values": []}
                    
                    from app.qdrant_service import search_chunks
                    
                    results = search_chunks("unknown query")
                    
                    assert results == []
    
    def test_search_chunks_error_handling(self):
        """Test search error handling."""
        with patch('app.qdrant_service._get_qdrant_client') as mock_get_client:
            with patch('app.qdrant_service.embed_query') as mock_embed:
                with patch('app.qdrant_service.generate_bm25_vector') as mock_bm25:
                    mock_client = Mock()
                    mock_client.query_points.side_effect = Exception("Connection error")
                    mock_get_client.return_value = mock_client
                    mock_embed.return_value = [0.1] * 768
                    mock_bm25.return_value = {"indices": [], "values": []}
                    
                    from app.qdrant_service import search_chunks
                    
                    results = search_chunks("query")
                    
                    assert results == []


class TestDocumentIngestion:
    """Test suite for document_ingestion module."""
    
    def test_discover_documents(self):
        """Test document discovery from OneDrive."""
        with patch('app.document_ingestion.get_access_token') as mock_token:
            with patch('app.document_ingestion.list_files') as mock_list:
                mock_token.return_value = "test_token"
                mock_list.return_value = [
                    {"id": "1", "name": "doc.pdf", "path": "/docs/doc.pdf"},
                    {"id": "2", "name": "slides.pptx", "path": "/docs/slides.pptx"},
                    {"id": "3", "name": "data.xlsx", "path": "/docs/data.xlsx"},  # Should be filtered
                    {"id": "4", "name": "image.png", "path": "/docs/image.png"}
                ]
                
                from app.document_ingestion import discover_documents
                
                with patch('app.document_ingestion.settings') as mock_settings:
                    mock_settings.document_root_path = "/docs"
                    result = discover_documents()
                
                assert len(result) == 3  # Excludes xlsx
                names = [f["name"] for f in result]
                assert "doc.pdf" in names
                assert "slides.pptx" in names
                assert "image.png" in names
                assert "data.xlsx" not in names
    
    def test_ingest_single_document_success(self):
        """Test successful single document ingestion."""
        with patch('app.document_ingestion.get_access_token'):
            with patch('app.document_ingestion.download_file') as mock_download:
                with patch('app.document_ingestion.process_document') as mock_process:
                    with patch('app.document_ingestion.delete_document_chunks'):
                        with patch('app.document_ingestion.upsert_chunks') as mock_upsert:
                            mock_download.return_value = b"PDF content"
                            mock_process.return_value = {
                                "filename": "test.pdf",
                                "doc_type": "pdf",
                                "chunks": ["chunk1", "chunk2"],
                                "char_count": 100
                            }
                            mock_upsert.return_value = 2
                            
                            from app.document_ingestion import ingest_single_document
                            
                            file_info = {
                                "id": "file123",
                                "name": "test.pdf",
                                "downloadUrl": "https://example.com/download",
                                "lastModified": "2024-01-01T00:00:00Z"
                            }
                            
                            result = ingest_single_document(file_info)
                            
                            assert result["success"] is True
                            assert result["chunks_count"] == 2
    
    def test_ingest_all_documents_dry_run(self):
        """Test dry run mode for ingestion."""
        with patch('app.document_ingestion.ensure_collection_exists'):
            with patch('app.document_ingestion.discover_documents') as mock_discover:
                mock_discover.return_value = [
                    {"id": "1", "name": "doc.pdf", "path": "/docs", "size": 1000},
                    {"id": "2", "name": "slides.pptx", "path": "/docs", "size": 2000}
                ]
                
                from app.document_ingestion import ingest_all_documents
                
                result = ingest_all_documents(dry_run=True)
                
                assert result["mode"] == "dry_run"
                assert result["total_files"] == 2
                assert len(result["files"]) == 2
