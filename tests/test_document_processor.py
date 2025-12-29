"""
Test Document Processor Module (TDD)
Tests for PDF, PPT/PPTX, and image OCR processing.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO


class TestDocumentProcessor:
    """Test suite for document_processor module."""
    
    # -------------------------------------------------------------------------
    # PDF Processing Tests
    # -------------------------------------------------------------------------
    
    def test_extract_text_from_pdf_bytes(self):
        """Test extracting text from PDF bytes."""
        from app.document_processor import extract_text_from_pdf
        
        # Create a simple mock PDF bytes
        # In real implementation, would use actual PDF fixture
        mock_pdf_bytes = b"%PDF-1.4 mock content"
        
        with patch('app.document_processor.pypdf.PdfReader') as mock_reader:
            mock_page = Mock()
            mock_page.extract_text.return_value = "This is test content from PDF"
            mock_reader.return_value.pages = [mock_page]
            
            result = extract_text_from_pdf(mock_pdf_bytes)
            
            assert isinstance(result, str)
            assert "test content" in result.lower()
    
    def test_extract_text_from_pdf_multiple_pages(self):
        """Test extracting text from multi-page PDF."""
        from app.document_processor import extract_text_from_pdf
        
        mock_pdf_bytes = b"%PDF-1.4 mock content"
        
        with patch('app.document_processor.pypdf.PdfReader') as mock_reader:
            mock_pages = [Mock() for _ in range(3)]
            mock_pages[0].extract_text.return_value = "Page 1 content"
            mock_pages[1].extract_text.return_value = "Page 2 content"
            mock_pages[2].extract_text.return_value = "Page 3 content"
            mock_reader.return_value.pages = mock_pages
            
            result = extract_text_from_pdf(mock_pdf_bytes)
            
            assert "Page 1" in result
            assert "Page 2" in result
            assert "Page 3" in result
    
    def test_extract_text_from_pdf_empty(self):
        """Test handling empty PDF."""
        from app.document_processor import extract_text_from_pdf
        
        mock_pdf_bytes = b"%PDF-1.4 mock content"
        
        with patch('app.document_processor.pypdf.PdfReader') as mock_reader:
            mock_reader.return_value.pages = []
            
            result = extract_text_from_pdf(mock_pdf_bytes)
            
            assert result == ""
    
    def test_extract_text_from_pdf_error_handling(self):
        """Test PDF extraction error handling."""
        from app.document_processor import extract_text_from_pdf
        
        mock_pdf_bytes = b"invalid pdf content"
        
        with patch('app.document_processor.pypdf.PdfReader') as mock_reader:
            mock_reader.side_effect = Exception("Invalid PDF")
            
            result = extract_text_from_pdf(mock_pdf_bytes)
            
            assert result == ""
    
    # -------------------------------------------------------------------------
    # PPT/PPTX Processing Tests
    # -------------------------------------------------------------------------
    
    def test_extract_text_from_pptx_bytes(self):
        """Test extracting text from PPTX bytes."""
        from app.document_processor import extract_text_from_pptx
        
        mock_pptx_bytes = b"PK mock pptx content"
        
        with patch('app.document_processor.Presentation') as mock_pres:
            mock_shape = Mock()
            mock_shape.has_text_frame = True
            mock_shape.text_frame.text = "Slide content text"
            
            mock_slide = Mock()
            mock_slide.shapes = [mock_shape]
            
            mock_pres.return_value.slides = [mock_slide]
            
            result = extract_text_from_pptx(mock_pptx_bytes)
            
            assert isinstance(result, str)
            assert "Slide content" in result
    
    def test_extract_text_from_pptx_multiple_slides(self):
        """Test extracting text from multi-slide PPTX."""
        from app.document_processor import extract_text_from_pptx
        
        mock_pptx_bytes = b"PK mock pptx content"
        
        with patch('app.document_processor.Presentation') as mock_pres:
            slides = []
            for i in range(3):
                mock_shape = Mock()
                mock_shape.has_text_frame = True
                mock_shape.text_frame.text = f"Slide {i+1} text"
                mock_slide = Mock()
                mock_slide.shapes = [mock_shape]
                slides.append(mock_slide)
            
            mock_pres.return_value.slides = slides
            
            result = extract_text_from_pptx(mock_pptx_bytes)
            
            assert "Slide 1" in result
            assert "Slide 2" in result
            assert "Slide 3" in result
    
    def test_extract_text_from_pptx_no_text_shapes(self):
        """Test PPTX with shapes that have no text."""
        from app.document_processor import extract_text_from_pptx
        
        mock_pptx_bytes = b"PK mock pptx content"
        
        with patch('app.document_processor.Presentation') as mock_pres:
            mock_shape = Mock()
            mock_shape.has_text_frame = False
            
            mock_slide = Mock()
            mock_slide.shapes = [mock_shape]
            
            mock_pres.return_value.slides = [mock_slide]
            
            result = extract_text_from_pptx(mock_pptx_bytes)
            
            assert result == ""
    
    # -------------------------------------------------------------------------
    # Image OCR Tests (using Gemini LLM)
    # -------------------------------------------------------------------------
    
    def test_extract_text_from_image_png(self):
        """Test OCR extraction from PNG image using Gemini."""
        from app.document_processor import extract_text_from_image
        
        # Create mock PNG bytes (1x1 pixel)
        mock_png_bytes = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        
        with patch('app.document_processor._get_gemini_client') as mock_client:
            mock_response = Mock()
            mock_response.text = "Extracted text from image"
            mock_client.return_value.models.generate_content.return_value = mock_response
            
            result = extract_text_from_image(mock_png_bytes, "test.png")
            
            assert isinstance(result, str)
            assert "Extracted text" in result
    
    def test_extract_text_from_image_jpg(self):
        """Test OCR extraction from JPG image using Gemini."""
        from app.document_processor import extract_text_from_image
        
        mock_jpg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        
        with patch('app.document_processor._get_gemini_client') as mock_client:
            mock_response = Mock()
            mock_response.text = "OCR result from JPEG"
            mock_client.return_value.models.generate_content.return_value = mock_response
            
            result = extract_text_from_image(mock_jpg_bytes, "test.jpg")
            
            assert "OCR result" in result
    
    def test_extract_text_from_image_error_handling(self):
        """Test image OCR error handling."""
        from app.document_processor import extract_text_from_image
        
        mock_bytes = b'\x00' * 10
        
        with patch('app.document_processor._get_gemini_client') as mock_client:
            mock_client.return_value.models.generate_content.side_effect = Exception("API Error")
            
            result = extract_text_from_image(mock_bytes, "test.png")
            
            assert result == ""
    
    # -------------------------------------------------------------------------
    # Chunking Tests
    # -------------------------------------------------------------------------
    
    def test_chunk_text_basic(self):
        """Test basic text chunking."""
        from app.document_processor import chunk_text
        
        text = "This is a test. " * 100  # ~1600 chars
        
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        
        assert isinstance(chunks, list)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert len(chunk) <= 600  # chunk_size + overlap buffer
    
    def test_chunk_text_preserves_content(self):
        """Test that chunking preserves all content."""
        from app.document_processor import chunk_text
        
        text = "Word1 Word2 Word3 Word4 Word5 " * 20
        
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        
        # Verify all unique words appear in at least one chunk
        all_words = set(text.split())
        found_words = set()
        for chunk in chunks:
            found_words.update(chunk.split())
        
        assert all_words.issubset(found_words)
    
    def test_chunk_text_short_text(self):
        """Test chunking text shorter than chunk size."""
        from app.document_processor import chunk_text
        
        text = "Short text"
        
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        
        assert len(chunks) == 1
        assert chunks[0] == text
    
    def test_chunk_text_empty(self):
        """Test chunking empty text."""
        from app.document_processor import chunk_text
        
        chunks = chunk_text("", chunk_size=500, overlap=50)
        
        assert chunks == []
    
    # -------------------------------------------------------------------------
    # Document Type Detection Tests
    # -------------------------------------------------------------------------
    
    def test_get_document_type_pdf(self):
        """Test PDF document type detection."""
        from app.document_processor import get_document_type
        
        assert get_document_type("document.pdf") == "pdf"
        assert get_document_type("DOCUMENT.PDF") == "pdf"
    
    def test_get_document_type_pptx(self):
        """Test PPTX document type detection."""
        from app.document_processor import get_document_type
        
        assert get_document_type("slides.pptx") == "pptx"
        assert get_document_type("slides.ppt") == "ppt"
    
    def test_get_document_type_image(self):
        """Test image document type detection."""
        from app.document_processor import get_document_type
        
        assert get_document_type("photo.png") == "image"
        assert get_document_type("photo.jpg") == "image"
        assert get_document_type("photo.jpeg") == "image"
    
    def test_get_document_type_unsupported(self):
        """Test unsupported document type."""
        from app.document_processor import get_document_type
        
        assert get_document_type("data.xlsx") == "unsupported"
        assert get_document_type("data.csv") == "unsupported"
        assert get_document_type("script.py") == "unsupported"
    
    # -------------------------------------------------------------------------
    # Process Document (Main Entry Point) Tests
    # -------------------------------------------------------------------------
    
    def test_process_document_pdf(self):
        """Test processing PDF document."""
        from app.document_processor import process_document
        
        mock_pdf_bytes = b"%PDF-1.4 mock"
        
        with patch('app.document_processor.extract_text_from_pdf') as mock_extract:
            mock_extract.return_value = "PDF content " * 50
            
            with patch('app.document_processor.chunk_text') as mock_chunk:
                mock_chunk.return_value = ["chunk1", "chunk2"]
                
                result = process_document(mock_pdf_bytes, "test.pdf")
                
                assert result["filename"] == "test.pdf"
                assert result["doc_type"] == "pdf"
                assert len(result["chunks"]) == 2
    
    def test_process_document_pptx(self):
        """Test processing PPTX document."""
        from app.document_processor import process_document
        
        mock_pptx_bytes = b"PK mock pptx"
        
        with patch('app.document_processor.extract_text_from_pptx') as mock_extract:
            mock_extract.return_value = "PPTX content " * 50
            
            with patch('app.document_processor.chunk_text') as mock_chunk:
                mock_chunk.return_value = ["slide1", "slide2"]
                
                result = process_document(mock_pptx_bytes, "slides.pptx")
                
                assert result["filename"] == "slides.pptx"
                assert result["doc_type"] == "pptx"
                assert len(result["chunks"]) == 2
    
    def test_process_document_image(self):
        """Test processing image document."""
        from app.document_processor import process_document
        
        mock_png_bytes = b'\x89PNG' + b'\x00' * 100
        
        with patch('app.document_processor.extract_text_from_image') as mock_extract:
            mock_extract.return_value = "OCR text from image"
            
            with patch('app.document_processor.chunk_text') as mock_chunk:
                mock_chunk.return_value = ["ocr_chunk"]
                
                result = process_document(mock_png_bytes, "photo.png")
                
                assert result["filename"] == "photo.png"
                assert result["doc_type"] == "image"
    
    def test_process_document_unsupported(self):
        """Test processing unsupported document type."""
        from app.document_processor import process_document
        
        result = process_document(b"excel content", "data.xlsx")
        
        assert result is None or result.get("error") is not None


class TestDocumentProcessorIntegration:
    """Integration tests for document processor (requires real files)."""
    
    @pytest.mark.skip(reason="Requires real PDF fixture")
    def test_real_pdf_extraction(self, tmp_path):
        """Test with real PDF file."""
        # This test would use a real PDF fixture
        pass
    
    @pytest.mark.skip(reason="Requires real PPTX fixture")
    def test_real_pptx_extraction(self, tmp_path):
        """Test with real PPTX file."""
        # This test would use a real PPTX fixture
        pass
