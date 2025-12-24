
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api.main import app
from app.data_analyzer import TransformResult

client = TestClient(app)

@pytest.fixture
def mock_user_auth():
    """Mock JWT auth using dependency override"""
    from api.routes import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {"username": "testuser", "role": "user", "id": 1}
    yield
    app.dependency_overrides = {}

@pytest.fixture
def mock_analyzer():
    """Mock the heavy AI analyzer logic"""
    with patch("api.routes.analyze_and_generate_transform") as mock:
        # success case
        mock.return_value = TransformResult(
            summary="Test Summary",
            issues_found=["Issue 1"],
            transform_code="df['new'] = 1",
            needs_transform=True,
            preview_df=None, 
            original_df=None,
            explanation="Test Explanation"
        )
        yield mock

@pytest.fixture
def mock_executor():
    """Mock the code execution logic"""
    with patch("api.routes.execute_transform") as mock:
        import pandas as pd
        df_result = pd.DataFrame({"col1": [1, 2], "new": [1, 1]})
        mock.return_value = (df_result, "")
        yield mock

def test_analyze_endpoint_stub(mock_user_auth, mock_analyzer):
    """Test that analyze endpoint works on cached table"""
    # Mock reading the parquet file (analyze now reads from cache)
    with patch("api.routes.pd.read_parquet") as mock_read:
        import pandas as pd
        mock_read.return_value = pd.DataFrame({"col1": [1, 2]})
        
        # Mock Path.exists to return True
        with patch("api.routes.Path.exists", return_value=True):
            response = client.post(
                "/api/files/analyze", 
                json={
                    "table_id": "dummy/path/file.parquet",
                    "user_description": "Clean this info"
                }
            )
        
    assert response.status_code == 200
    data = response.json()
    assert "needs_transform" in data
    assert "summary" in data
    assert "transform_code" in data
    assert data["summary"] == "Test Summary"
    assert data["needs_transform"] is True

def test_execute_transform_endpoint(mock_user_auth, mock_executor):
    """Test endpoint that executes proposed python code and returns preview"""
    with patch("api.routes.pd.read_parquet") as mock_read:
        import pandas as pd
        mock_read.return_value = pd.DataFrame({"col1": [1, 2]})
        
        with patch("api.routes.Path.exists", return_value=True):
            response = client.post(
                "/api/files/transform/preview",
                json={
                    "table_id": "dummy/path/file.parquet",
                    "transform_code": "df['new'] = 1"
                }
            )

    assert response.status_code == 200
    data = response.json()
    assert "preview_data" in data
    assert "columns" in data
    assert "total_rows" in data
    assert "new" in data["columns"]

def test_confirm_transform_endpoint_create_new(mock_user_auth):
    """Test final save of transformed data as NEW table (default behavior)"""
    with patch("api.routes.execute_transform") as mock_exec:
        import pandas as pd
        mock_exec.return_value = (pd.DataFrame({"col1": [1]}), "")
        
        with patch("api.routes.build_parquet_cache_from_df") as mock_cache:
            mock_cache.return_value = ("path/to/cache_v2.parquet", 1, 1)
            
            with patch("api.routes.pd.read_parquet") as mock_read:
                mock_read.return_value = pd.DataFrame({"col1": [1]})
                
                with patch("api.routes.Path.exists", return_value=True):
                    response = client.post(
                        "/api/files/transform/confirm",
                        json={
                            "table_id": "dummy/path/file.parquet",
                            "transform_code": "df['new'] = 1",
                            "display_name": "Cleaned Data",
                            "replace_original": False
                        }
                    )

    assert response.status_code == 200
    data = response.json()
    assert "cache_path" in data
    assert data["cache_path"] == "path/to/cache_v2.parquet"
    assert "new table" in data["message"]
    # Verify build_parquet_cache_from_df was called (not update)
    mock_cache.assert_called_once()


def test_confirm_transform_endpoint_replace_original(mock_user_auth):
    """
    Test REPLACING the original table instead of creating a new one.
    GIVEN: Existing table and valid transform code
    WHEN: Calling confirm_transform with replace_original=True
    THEN: update_existing_parquet_cache is called (not build_parquet_cache_from_df)
    """
    with patch("api.routes.execute_transform") as mock_exec:
        import pandas as pd
        mock_exec.return_value = (pd.DataFrame({"col1": [1]}), "")
        
        with patch("api.routes.update_existing_parquet_cache") as mock_update:
            mock_update.return_value = (1, 1)  # Returns (n_rows, n_cols)
            
            with patch("api.routes.pd.read_parquet") as mock_read:
                mock_read.return_value = pd.DataFrame({"col1": [1]})
                
                with patch("api.routes.Path.exists", return_value=True):
                    # Use a mock path object that has a string representation
                    with patch("api.routes.Path") as MockPath:
                        mock_path_instance = MagicMock()
                        mock_path_instance.exists.return_value = True
                        mock_path_instance.__str__.return_value = "dummy/path/file.parquet"
                        MockPath.return_value = mock_path_instance
                        
                        response = client.post(
                            "/api/files/transform/confirm",
                            json={
                                "table_id": "dummy/path/file.parquet",
                                "transform_code": "df['new'] = 1",
                                "replace_original": True
                            }
                        )

    assert response.status_code == 200
    data = response.json()
    assert "cache_path" in data
    # When replacing, the cache_path should be the original path
    assert "message" in data
    # Verify update function was called
    mock_update.assert_called_once()

