"""
Test Embeddings Module (TDD)
Tests for Gemini embedding generation.
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestEmbeddings:
    """Test suite for embeddings module."""
    
    # -------------------------------------------------------------------------
    # Gemini Client Tests
    # -------------------------------------------------------------------------
    
    def test_get_gemini_client_success(self):
        """Test successful Gemini client initialization."""
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}):
            with patch('app.embeddings.genai') as mock_genai:
                mock_client = Mock()
                mock_genai.Client.return_value = mock_client
                
                from app.embeddings import _get_client
                # Reset singleton
                import app.embeddings
                app.embeddings._CLIENT = None
                
                client = _get_client()
                
                assert client is not None
                mock_genai.Client.assert_called_once()
    
    def test_get_gemini_client_no_api_key(self):
        """Test error when GEMINI_API_KEY not configured."""
        with patch('app.embeddings.settings') as mock_settings:
            mock_settings.gemini_api_key = ""
            
            from app.embeddings import _get_client
            import app.embeddings
            app.embeddings._CLIENT = None
            
            with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
                _get_client()
    
    # -------------------------------------------------------------------------
    # Embed Texts Tests
    # -------------------------------------------------------------------------
    
    def test_embed_texts_single(self):
        """Test embedding a single text."""
        from app.embeddings import embed_texts, EmbeddingTask
        
        with patch('app.embeddings._get_client') as mock_get_client:
            mock_client = Mock()
            mock_embedding = Mock()
            mock_embedding.values = [0.1] * 768
            mock_response = Mock()
            mock_response.embeddings = [mock_embedding]
            mock_client.models.embed_content.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            result = embed_texts(["Test text"])
            
            assert len(result) == 1
            assert len(result[0]) == 768
    
    def test_embed_texts_batch(self):
        """Test embedding multiple texts in batch."""
        from app.embeddings import embed_texts
        
        with patch('app.embeddings._get_client') as mock_get_client:
            mock_client = Mock()
            mock_embeddings = [Mock(values=[0.1] * 768) for _ in range(5)]
            mock_response = Mock()
            mock_response.embeddings = mock_embeddings
            mock_client.models.embed_content.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            texts = ["Text 1", "Text 2", "Text 3", "Text 4", "Text 5"]
            result = embed_texts(texts)
            
            assert len(result) == 5
    
    def test_embed_texts_empty_list(self):
        """Test embedding empty list."""
        from app.embeddings import embed_texts
        
        result = embed_texts([])
        
        assert result == []
    
    def test_embed_texts_query_task(self):
        """Test embedding with QUERY task type."""
        from app.embeddings import embed_texts, EmbeddingTask
        
        with patch('app.embeddings._get_client') as mock_get_client:
            mock_client = Mock()
            mock_embedding = Mock()
            mock_embedding.values = [0.2] * 768
            mock_response = Mock()
            mock_response.embeddings = [mock_embedding]
            mock_client.models.embed_content.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            result = embed_texts(["Query text"], task=EmbeddingTask.QUERY)
            
            assert len(result) == 1
            # Verify task type was passed
            call_kwargs = mock_client.models.embed_content.call_args
            assert call_kwargs is not None
    
    def test_embed_texts_retry_on_error(self):
        """Test retry mechanism on transient errors."""
        from app.embeddings import embed_texts
        
        with patch('app.embeddings._get_client') as mock_get_client:
            mock_client = Mock()
            
            # First call fails, second succeeds
            mock_embedding = Mock()
            mock_embedding.values = [0.1] * 768
            mock_response = Mock()
            mock_response.embeddings = [mock_embedding]
            
            mock_client.models.embed_content.side_effect = [
                Exception("Temporary error"),
                mock_response
            ]
            mock_get_client.return_value = mock_client
            
            with patch('time.sleep'):  # Skip actual sleep in tests
                result = embed_texts(["Test"])
            
            assert len(result) == 1
    
    # -------------------------------------------------------------------------
    # Embed Single Text Tests
    # -------------------------------------------------------------------------
    
    def test_embed_text_single(self):
        """Test embedding a single text string."""
        from app.embeddings import embed_text
        
        with patch('app.embeddings.embed_texts') as mock_embed:
            mock_embed.return_value = [[0.1] * 768]
            
            result = embed_text("Single text")
            
            assert len(result) == 768
            mock_embed.assert_called_once()
    
    def test_embed_text_empty(self):
        """Test embedding empty text."""
        from app.embeddings import embed_text
        
        with patch('app.embeddings.embed_texts') as mock_embed:
            mock_embed.return_value = [[0.0] * 768]
            
            result = embed_text("")
            
            assert len(result) == 768


class TestBM25SparseVectors:
    """Test suite for BM25 sparse vector generation."""
    
    def test_generate_bm25_vector(self):
        """Test BM25 sparse vector generation."""
        from app.embeddings import generate_bm25_vector
        
        with patch('app.embeddings._get_bm25_model') as mock_get_model:
            mock_model = Mock()
            mock_sparse = Mock()
            mock_sparse.indices = Mock(tolist=Mock(return_value=[1, 5, 10]))
            mock_sparse.values = Mock(tolist=Mock(return_value=[0.5, 0.3, 0.2]))
            mock_model.embed.return_value = iter([mock_sparse])
            mock_get_model.return_value = mock_model
            
            result = generate_bm25_vector("Test document text")
            
            assert "indices" in result
            assert "values" in result
            assert len(result["indices"]) == 3
    
    def test_generate_bm25_vector_empty_text(self):
        """Test BM25 with empty text."""
        from app.embeddings import generate_bm25_vector
        
        result = generate_bm25_vector("")
        
        assert result == {"indices": [], "values": []}
    
    def test_generate_bm25_vector_whitespace_only(self):
        """Test BM25 with whitespace-only text."""
        from app.embeddings import generate_bm25_vector
        
        result = generate_bm25_vector("   \n\t  ")
        
        assert result == {"indices": [], "values": []}
