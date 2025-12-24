"""
TDD Tests for OneDrive Client Module.
Tests API integration with mocked HTTP requests.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import BytesIO

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
import requests


class TestGetAccessToken:
    """Tests for access token acquisition."""
    
    def test_get_access_token_success(self):
        """
        GIVEN: Valid credentials configured
        WHEN: Requesting access token
        THEN: Returns token string
        """
        from app import onedrive_client
        
        with patch.object(onedrive_client.config, "MS_TENANT_ID", "tenant123"):
            with patch.object(onedrive_client.config, "MS_CLIENT_ID", "client123"):
                with patch.object(onedrive_client.config, "MS_CLIENT_SECRET", "secret123"):
                    with patch("app.onedrive_client.requests.post") as mock_post:
                        mock_post.return_value.json.return_value = {
                            "access_token": "test_token_12345"
                        }
                        mock_post.return_value.raise_for_status = MagicMock()
                        
                        token = onedrive_client.get_access_token()
        
        assert token == "test_token_12345"
    
    def test_get_access_token_missing_credentials(self):
        """
        GIVEN: Missing credentials
        WHEN: Requesting access token
        THEN: Raises RuntimeError
        """
        from app import onedrive_client
        
        with patch.object(onedrive_client.config, "MS_TENANT_ID", ""):
            with patch.object(onedrive_client.config, "MS_CLIENT_ID", ""):
                with patch.object(onedrive_client.config, "MS_CLIENT_SECRET", ""):
                    with pytest.raises(RuntimeError, match="not configured"):
                        onedrive_client.get_access_token()
    
    def test_get_access_token_no_token_in_response(self):
        """
        GIVEN: API returns response without token
        WHEN: Requesting access token
        THEN: Raises RuntimeError
        """
        from app import onedrive_client
        
        with patch.object(onedrive_client.config, "MS_TENANT_ID", "tenant"):
            with patch.object(onedrive_client.config, "MS_CLIENT_ID", "client"):
                with patch.object(onedrive_client.config, "MS_CLIENT_SECRET", "secret"):
                    with patch("app.onedrive_client.requests.post") as mock_post:
                        mock_post.return_value.json.return_value = {}
                        mock_post.return_value.raise_for_status = MagicMock()
                        
                        with pytest.raises(RuntimeError, match="No access_token"):
                            onedrive_client.get_access_token()


class TestGraphGet:
    """Tests for Graph API GET requests."""
    
    def test_graph_get_success(self):
        """
        GIVEN: Valid URL and token
        WHEN: Making GET request
        THEN: Returns JSON response
        """
        from app.onedrive_client import _graph_get
        
        with patch("app.onedrive_client.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"data": "test"}
            mock_get.return_value.raise_for_status = MagicMock()
            
            result = _graph_get("https://graph.microsoft.com/test", "token123")
        
        assert result == {"data": "test"}
    
    def test_graph_get_retries_on_429(self):
        """
        GIVEN: API returns 429 (rate limit)
        WHEN: Making GET request
        THEN: Retries with backoff
        """
        from app.onedrive_client import _graph_get
        
        with patch("app.onedrive_client.requests.get") as mock_get:
            with patch("app.onedrive_client.time.sleep") as mock_sleep:
                # First call returns 429, second succeeds
                mock_response_429 = MagicMock()
                mock_response_429.status_code = 429
                mock_response_429.headers = {"Retry-After": "1"}
                
                mock_response_ok = MagicMock()
                mock_response_ok.status_code = 200
                mock_response_ok.json.return_value = {"success": True}
                mock_response_ok.raise_for_status = MagicMock()
                
                mock_get.side_effect = [mock_response_429, mock_response_ok]
                
                result = _graph_get("https://graph.microsoft.com/test", "token")
        
        assert result == {"success": True}
        mock_sleep.assert_called()
    
    def test_graph_get_404_raises_error(self):
        """
        GIVEN: File not found (404)
        WHEN: Making GET request
        THEN: Raises RuntimeError with helpful message
        """
        from app.onedrive_client import _graph_get
        
        with patch("app.onedrive_client.requests.get") as mock_get:
            mock_get.return_value.status_code = 404
            
            with pytest.raises(RuntimeError, match="not found"):
                _graph_get("https://graph.microsoft.com/test", "token")
    
    def test_graph_get_403_raises_error(self):
        """
        GIVEN: Access denied (403)
        WHEN: Making GET request
        THEN: Raises RuntimeError with helpful message
        """
        from app.onedrive_client import _graph_get
        
        with patch("app.onedrive_client.requests.get") as mock_get:
            mock_get.return_value.status_code = 403
            
            with pytest.raises(RuntimeError, match="Access denied"):
                _graph_get("https://graph.microsoft.com/test", "token")


class TestListFiles:
    """Tests for listing OneDrive files."""
    
    def test_list_files_success(self):
        """
        GIVEN: OneDrive folder with Excel/CSV files
        WHEN: Listing files
        THEN: Returns list of file info dicts
        """
        from app.onedrive_client import list_files
        from app import onedrive_client
        
        mock_root = {"id": "root123"}
        mock_children = {
            "value": [
                {
                    "id": "file1",
                    "name": "data.xlsx",
                    "size": 1024,
                    "@microsoft.graph.downloadUrl": "https://download/1",
                    "webUrl": "https://web/1",
                    "lastModifiedDateTime": "2024-01-01T00:00:00Z"
                },
                {
                    "id": "file2",
                    "name": "report.csv",
                    "size": 512,
                    "@microsoft.graph.downloadUrl": "https://download/2"
                }
            ]
        }
        
        with patch.object(onedrive_client.config, "ONEDRIVE_ROOT_PATH", "/test"):
            with patch.object(onedrive_client.config, "ONEDRIVE_DRIVE_ID", "drive123"):
                with patch.object(onedrive_client.config, "GRAPH_BASE_URL", "https://graph"):
                    with patch.object(onedrive_client.config, "SUPPORTED_EXTENSIONS", [".xlsx", ".csv"]):
                        with patch("app.onedrive_client._graph_get") as mock_get:
                            mock_get.side_effect = [mock_root, mock_children]
                            
                            result = list_files("token123")
        
        assert len(result) == 2
        assert result[0]["name"] == "data.xlsx"
        assert result[1]["name"] == "report.csv"
    
    def test_list_files_filters_unsupported(self):
        """
        GIVEN: Folder with mixed file types
        WHEN: Listing files
        THEN: Only supported extensions are returned
        """
        from app.onedrive_client import list_files
        from app import onedrive_client
        
        mock_root = {"id": "root123"}
        mock_children = {
            "value": [
                {"id": "1", "name": "data.xlsx"},
                {"id": "2", "name": "image.png"},  # Should be filtered
                {"id": "3", "name": "doc.pdf"},    # Should be filtered
                {"id": "4", "name": "report.csv"}
            ]
        }
        
        with patch.object(onedrive_client.config, "ONEDRIVE_ROOT_PATH", "/test"):
            with patch.object(onedrive_client.config, "ONEDRIVE_DRIVE_ID", "drive"):
                with patch.object(onedrive_client.config, "GRAPH_BASE_URL", "https://graph"):
                    with patch.object(onedrive_client.config, "SUPPORTED_EXTENSIONS", [".xlsx", ".csv"]):
                        with patch("app.onedrive_client._graph_get") as mock_get:
                            mock_get.side_effect = [mock_root, mock_children]
                            
                            result = list_files("token")
        
        names = [f["name"] for f in result]
        assert "data.xlsx" in names
        assert "report.csv" in names
        assert "image.png" not in names
        assert "doc.pdf" not in names
    
    def test_list_files_empty_folder(self):
        """
        GIVEN: Empty OneDrive folder
        WHEN: Listing files
        THEN: Returns empty list
        """
        from app.onedrive_client import list_files
        from app import onedrive_client
        
        mock_root = {"id": "root123"}
        mock_children = {"value": []}
        
        with patch.object(onedrive_client.config, "ONEDRIVE_ROOT_PATH", "/test"):
            with patch.object(onedrive_client.config, "ONEDRIVE_DRIVE_ID", "drive"):
                with patch.object(onedrive_client.config, "GRAPH_BASE_URL", "https://graph"):
                    with patch("app.onedrive_client._graph_get") as mock_get:
                        mock_get.side_effect = [mock_root, mock_children]
                        
                        result = list_files("token")
        
        assert result == []
    
    def test_list_files_handles_exception(self):
        """
        GIVEN: API error
        WHEN: Listing files
        THEN: Returns empty list gracefully
        """
        from app.onedrive_client import list_files
        from app import onedrive_client
        
        with patch.object(onedrive_client.config, "ONEDRIVE_ROOT_PATH", "/test"):
            with patch.object(onedrive_client.config, "ONEDRIVE_DRIVE_ID", "drive"):
                with patch.object(onedrive_client.config, "GRAPH_BASE_URL", "https://graph"):
                    with patch("app.onedrive_client._graph_get") as mock_get:
                        mock_get.side_effect = Exception("Network error")
                        
                        result = list_files("token")
        
        assert result == []


class TestDownloadFile:
    """Tests for file download."""
    
    def test_download_file_success(self):
        """
        GIVEN: Valid download URL
        WHEN: Downloading file
        THEN: Returns file bytes
        """
        from app.onedrive_client import download_file
        
        with patch("app.onedrive_client.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.content = b"file content here"
            mock_get.return_value.raise_for_status = MagicMock()
            
            result = download_file("https://download/file.xlsx")
        
        assert result == b"file content here"
    
    def test_download_file_404_raises_error(self):
        """
        GIVEN: Expired or invalid download URL
        WHEN: Downloading file
        THEN: Raises RuntimeError
        """
        from app.onedrive_client import download_file
        
        with patch("app.onedrive_client.requests.get") as mock_get:
            mock_get.return_value.status_code = 404
            
            with pytest.raises(RuntimeError, match="expired"):
                download_file("https://download/expired.xlsx")
    
    def test_download_file_403_raises_error(self):
        """
        GIVEN: Access denied
        WHEN: Downloading file
        THEN: Raises RuntimeError
        """
        from app.onedrive_client import download_file
        
        with patch("app.onedrive_client.requests.get") as mock_get:
            mock_get.return_value.status_code = 403
            
            with pytest.raises(RuntimeError, match="Access denied"):
                download_file("https://download/forbidden.xlsx")


class TestGetExcelSheets:
    """Tests for getting Excel sheet names."""
    
    def test_get_excel_sheets_returns_names(self):
        """
        GIVEN: Valid Excel file bytes
        WHEN: Getting sheet names
        THEN: Returns list of sheet names
        """
        from app.onedrive_client import get_excel_sheets
        
        # Create actual Excel bytes
        df = pd.DataFrame({"col": [1, 2, 3]})
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Sheet1", index=False)
            df.to_excel(writer, sheet_name="DataSheet", index=False)
        
        result = get_excel_sheets(buffer.getvalue())
        
        assert "Sheet1" in result
        assert "DataSheet" in result
    
    def test_get_excel_sheets_invalid_data(self):
        """
        GIVEN: Invalid/corrupted file bytes
        WHEN: Getting sheet names
        THEN: Returns empty list
        """
        from app.onedrive_client import get_excel_sheets
        
        result = get_excel_sheets(b"not an excel file")
        
        assert result == []


class TestReadFileToDf:
    """Tests for reading files to DataFrame."""
    
    def test_read_csv_to_df(self):
        """
        GIVEN: CSV file bytes
        WHEN: Reading to DataFrame
        THEN: Returns correct DataFrame
        """
        from app.onedrive_client import read_file_to_df
        
        csv_bytes = b"id,name\n1,Alice\n2,Bob\n"
        
        df = read_file_to_df(csv_bytes, "data.csv")
        
        assert len(df) == 2
        assert list(df.columns) == ["id", "name"]
    
    def test_read_excel_to_df(self):
        """
        GIVEN: Excel file bytes
        WHEN: Reading to DataFrame
        THEN: Returns correct DataFrame
        """
        from app.onedrive_client import read_file_to_df
        
        # Create Excel bytes
        source_df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
        buffer = BytesIO()
        source_df.to_excel(buffer, index=False)
        
        df = read_file_to_df(buffer.getvalue(), "data.xlsx")
        
        assert len(df) == 2
        assert "col1" in df.columns
    
    def test_read_excel_specific_sheet(self):
        """
        GIVEN: Excel file with multiple sheets
        WHEN: Reading specific sheet
        THEN: Returns data from that sheet
        """
        from app.onedrive_client import read_file_to_df
        
        # Create Excel with multiple sheets
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            pd.DataFrame({"first": [1]}).to_excel(writer, sheet_name="Sheet1", index=False)
            pd.DataFrame({"second": [2]}).to_excel(writer, sheet_name="Sheet2", index=False)
        
        df = read_file_to_df(buffer.getvalue(), "data.xlsx", sheet_name="Sheet2")
        
        assert "second" in df.columns
    
    def test_read_with_nrows_limit(self):
        """
        GIVEN: Large CSV
        WHEN: Reading with nrows limit
        THEN: Returns limited rows
        """
        from app.onedrive_client import read_file_to_df
        
        csv_bytes = b"id\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n"
        
        df = read_file_to_df(csv_bytes, "large.csv", nrows=5)
        
        assert len(df) == 5
    
    def test_read_unsupported_format_raises(self):
        """
        GIVEN: Unsupported file format
        WHEN: Reading to DataFrame
        THEN: Raises ValueError
        """
        from app.onedrive_client import read_file_to_df
        
        with pytest.raises(ValueError, match="Unsupported file"):
            read_file_to_df(b"some bytes", "document.pdf")


class TestGetFileDetails:
    """Tests for getting file details by ID."""
    
    def test_get_file_details_success(self):
        """
        GIVEN: Valid file ID
        WHEN: Getting file details
        THEN: Returns file metadata dict
        """
        from app.onedrive_client import get_file_details
        from app import onedrive_client
        
        with patch.object(onedrive_client.config, "ONEDRIVE_DRIVE_ID", "drive123"):
            with patch.object(onedrive_client.config, "GRAPH_BASE_URL", "https://graph"):
                with patch("app.onedrive_client._graph_get") as mock_get:
                    mock_get.return_value = {
                        "id": "file123",
                        "name": "test.xlsx",
                        "@microsoft.graph.downloadUrl": "https://download"
                    }
                    
                    result = get_file_details("token", "file123")
        
        assert result["id"] == "file123"
        assert "@microsoft.graph.downloadUrl" in result


class TestUploadFile:
    """Tests for file upload."""
    
    def test_upload_file_success(self, tmp_path):
        """
        GIVEN: Valid local file
        WHEN: Uploading to OneDrive
        THEN: Returns success response
        """
        from app.onedrive_client import upload_file
        from app import onedrive_client
        
        # Create test file
        test_file = tmp_path / "upload.xlsx"
        test_file.write_bytes(b"file content")
        
        with patch.object(onedrive_client.config, "ONEDRIVE_ROOT_PATH", "/uploads"):
            with patch.object(onedrive_client.config, "ONEDRIVE_DRIVE_ID", "drive"):
                with patch.object(onedrive_client.config, "GRAPH_BASE_URL", "https://graph"):
                    with patch("app.onedrive_client.get_access_token", return_value="token"):
                        with patch("app.onedrive_client.requests.put") as mock_put:
                            mock_put.return_value.status_code = 201
                            mock_put.return_value.json.return_value = {
                                "id": "new_file_id",
                                "name": "upload.xlsx"
                            }
                            mock_put.return_value.raise_for_status = MagicMock()
                            
                            result = upload_file(test_file, "upload.xlsx")
        
        assert result["id"] == "new_file_id"
