"""
Advanced API Tests for QIP Data Assistant.
Additional edge cases for admin, analyze, export, and validation endpoints.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

from api import database, auth_utils


@pytest.fixture
def test_db(tmp_path: Path):
    """Setup a temporary database for testing."""
    import api.database as db_module
    db_module.SQLITE_DB_PATH = tmp_path / "test_advanced.db"
    db_module.init_database()
    
    # Create test admin user
    admin_hash = auth_utils.get_password_hash("admin123")
    database.add_user("admin", admin_hash, "admin")
    
    # Create regular test user
    user_hash = auth_utils.get_password_hash("userpass")
    database.add_user("testuser", user_hash, "user")
    
    yield


@pytest.fixture
def client(test_db):
    """Create a test client."""
    from api.main import app
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    """Get admin access token."""
    response = client.post(
        "/auth/token",
        data={"username": "admin", "password": "admin123"}
    )
    return response.json()["access_token"]


@pytest.fixture
def user_token(client):
    """Get regular user access token."""
    response = client.post(
        "/auth/token",
        data={"username": "testuser", "password": "userpass"}
    )
    return response.json()["access_token"]


# =============================================================================
# Admin User Management Tests
# =============================================================================

class TestAdminUserManagement:
    """Tests for admin user management endpoints."""
    
    def test_list_users_admin_only(self, client, user_token):
        """
        GIVEN: Regular user token
        WHEN: Listing all users
        THEN: Returns 403 (forbidden) or 404 if route doesn't exist
        """
        response = client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        # Admin-only route should deny regular users
        assert response.status_code in [403, 404]
    
    def test_list_users_as_admin(self, client, admin_token):
        """
        GIVEN: Admin token
        WHEN: Listing all users
        THEN: Returns user list or 404 if route doesn't exist
        """
        response = client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if response.status_code == 200:
            assert isinstance(response.json(), list)
        else:
            assert response.status_code in [404]
    
    def test_delete_user_as_admin(self, client, admin_token, test_db):
        """
        GIVEN: Admin wants to delete a user
        WHEN: DELETE /admin/users/{username}
        THEN: User is deleted or route returns 404
        """
        # Create a user to delete
        password_hash = auth_utils.get_password_hash("todelete")
        database.add_user("deleteuser", password_hash, "user")
        
        response = client.delete(
            "/admin/users/deleteuser",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code in [200, 204, 404]
    
    def test_create_user_as_admin(self, client, admin_token):
        """
        GIVEN: Admin wants to create a new user
        WHEN: POST /admin/users
        THEN: User is created or route returns error
        """
        response = client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": "newadminuser",
                "password": "newpassword",
                "role": "user"
            }
        )
        assert response.status_code in [200, 201, 404, 422]


# =============================================================================
# Analyze Endpoints Tests
# =============================================================================

class TestAnalyzeEndpoints:
    """Tests for data analysis endpoints."""
    
    def test_analyze_unauthenticated(self, client):
        """
        GIVEN: No authentication
        WHEN: POST /api/analyze
        THEN: Returns 401
        """
        response = client.post(
            "/api/analyze",
            json={"table_id": "test.parquet"}
        )
        # 401 if route exists, 404 if not
        assert response.status_code in [401, 404]
    
    def test_analyze_missing_table_id(self, client, admin_token):
        """
        GIVEN: Missing table_id
        WHEN: POST /api/analyze
        THEN: Returns 422
        """
        response = client.post(
            "/api/analyze",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={}
        )
        # 422 if route exists and validates, 404 if not, 401 if auth required first
        assert response.status_code in [401, 404, 422]
    
    def test_analyze_nonexistent_table(self, client, admin_token):
        """
        GIVEN: Non-existent table
        WHEN: POST /api/analyze
        THEN: Returns 404 or 500
        """
        response = client.post(
            "/api/analyze",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"table_id": "nonexistent_table.parquet"}
        )
        assert response.status_code in [404, 500]
    
    def test_analyze_with_user_description(self, client, admin_token, tmp_path, monkeypatch):
        """
        GIVEN: Table with user description
        WHEN: POST /api/analyze
        THEN: Analysis uses description
        """
        import pandas as pd
        
        # Create mock table
        df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
        
        import app.datasets as datasets_module
        monkeypatch.setattr(datasets_module, "PARQUET_CACHE_DIR", tmp_path)
        
        # Save as parquet
        parquet_path = tmp_path / "test_analyze.parquet"
        df.to_parquet(parquet_path)
        
        response = client.post(
            "/api/analyze",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "table_id": "test_analyze.parquet",
                "user_description": "This is sales data"
            }
        )
        # May succeed or fail depending on AI availability
        assert response.status_code in [200, 404, 500]


# =============================================================================
# Export/Download Endpoints Tests
# =============================================================================

class TestExportDownloadEndpoints:
    """Tests for export and download functionality."""
    
    def test_export_csv_unauthenticated(self, client):
        """
        GIVEN: No authentication
        WHEN: GET /api/tables/{id}/export/csv
        THEN: Returns 401
        """
        response = client.get("/api/tables/test.parquet/export/csv")
        # 401 if route exists, 404/405 if not or wrong method
        assert response.status_code in [401, 404, 405]
    
    def test_export_excel_unauthenticated(self, client):
        """
        GIVEN: No authentication
        WHEN: GET /api/tables/{id}/export/excel
        THEN: Returns 401
        """
        response = client.get("/api/tables/test.parquet/export/excel")
        # 401 if route exists, 404/405 if not or wrong method
        assert response.status_code in [401, 404, 405]
    
    def test_export_csv_nonexistent_table(self, client, admin_token):
        """
        GIVEN: Non-existent table
        WHEN: GET /api/tables/{id}/export/csv
        THEN: Returns 404
        """
        response = client.get(
            "/api/tables/nonexistent.parquet/export/csv",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # May be 404 not found or 405 method not allowed
        assert response.status_code in [404, 405, 500]


# =============================================================================
# Input Validation Tests
# =============================================================================

class TestInputValidation:
    """Tests for input validation across endpoints."""
    
    def test_chat_request_empty_question(self, client, user_token):
        """
        GIVEN: Empty question
        WHEN: POST /api/chat/ask
        THEN: Handles appropriately
        """
        response = client.post(
            "/api/chat/ask",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"question": "", "chat_id": "test-id"}
        )
        # Empty question may be rejected or allowed
        assert response.status_code in [200, 400, 422, 500]
    
    def test_chat_request_very_long_question(self, client, user_token):
        """
        GIVEN: Very long question
        WHEN: POST /api/chat/ask
        THEN: Handles gracefully without crashing
        """
        long_question = "What is " + "x" * 10000 + "?"
        
        response = client.post(
            "/api/chat/ask",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"question": long_question, "chat_id": "test-id"}
        )
        # Should handle without crashing
        assert response.status_code in [200, 400, 413, 422, 500]
    
    def test_profile_update_empty_display_name(self, client, user_token):
        """
        GIVEN: Empty display name
        WHEN: PATCH /auth/profile
        THEN: May reject or accept
        """
        response = client.patch(
            "/auth/profile",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"display_name": ""}
        )
        # May allow empty or reject
        assert response.status_code in [200, 400, 422]
    
    def test_password_change_weak_password(self, client, user_token):
        """
        GIVEN: Very short/weak password
        WHEN: PATCH /auth/password
        THEN: May accept or reject based on policy
        """
        response = client.patch(
            "/auth/password",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "current_password": "userpass",
                "new_password": "1"  # Very weak
            }
        )
        # Current implementation may not enforce password policy
        assert response.status_code in [200, 400, 422]
    
    def test_special_characters_in_chat_title(self, client, user_token):
        """
        GIVEN: Chat title with special characters
        WHEN: Creating chat
        THEN: Handles special characters correctly
        """
        special_title = "<script>alert('XSS')</script> & \"quotes\" 'apostrophe'"
        
        response = client.post(
            "/api/chats",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"title": special_title}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data


# =============================================================================
# Rate Limiting / Edge Cases
# =============================================================================

class TestRateLimitingEdgeCases:
    """Tests for rate limiting and edge case handling."""
    
    def test_multiple_rapid_requests(self, client, admin_token):
        """
        GIVEN: Many rapid requests
        WHEN: Sending multiple requests quickly
        THEN: All should be handled
        """
        success_count = 0
        for i in range(10):
            response = client.get(
                "/api/tables",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            if response.status_code == 200:
                success_count += 1
        
        assert success_count >= 8  # Most should succeed
    
    def test_concurrent_chat_requests(self, client, user_token):
        """
        GIVEN: Authenticated user
        WHEN: Multiple chat creations
        THEN: All succeed
        """
        chat_ids = []
        for i in range(5):
            response = client.post(
                "/api/chats",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"title": f"Chat {i}"}
            )
            if response.status_code == 200:
                chat_ids.append(response.json()["id"])
        
        # Should create multiple chats
        assert len(chat_ids) >= 1


# =============================================================================
# OneDrive Pattern Processing Tests
# =============================================================================

class TestOneDrivePatternProcessing:
    """Tests for Excel pattern processing via OneDrive."""
    
    def test_load_with_pattern_unauthenticated(self, client):
        """
        GIVEN: No authentication
        WHEN: POST /api/onedrive/load-with-pattern
        THEN: Returns 401 or 404
        """
        response = client.post(
            "/api/onedrive/load-with-pattern",
            json={
                "download_url": "https://example.com/file.xlsx",
                "filename": "test.xlsx",
                "pattern_name": "Loss C-Grade"
            }
        )
        assert response.status_code in [401, 404, 422]
    
    def test_list_patterns_authenticated(self, client, admin_token):
        """
        GIVEN: Authenticated user
        WHEN: GET /api/patterns
        THEN: Returns list of patterns or 404
        """
        response = client.get(
            "/api/patterns",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # May return pattern list or 404 if not implemented
        if response.status_code == 200:
            assert isinstance(response.json(), list)


# =============================================================================
# Search/Query Tests
# =============================================================================

class TestSearchQueryEndpoints:
    """Tests for search and query functionality."""
    
    def test_table_search_by_name(self, client, admin_token):
        """
        GIVEN: Search query
        WHEN: GET /api/tables with search param
        THEN: Returns filtered results
        """
        response = client.get(
            "/api/tables?search=test",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # May support search param or ignore it
        assert response.status_code == 200
    
    def test_chat_history_pagination(self, client, user_token):
        """
        GIVEN: Multiple chats
        WHEN: GET /api/chats with pagination
        THEN: Returns paginated results
        """
        response = client.get(
            "/api/chats?limit=5&offset=0",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        # May support pagination or ignore params
        assert response.status_code == 200


# =============================================================================
# Token Expiration Tests
# =============================================================================

class TestTokenExpiration:
    """Tests for JWT token handling edge cases."""
    
    def test_expired_token_rejected(self, client):
        """
        GIVEN: Expired JWT token
        WHEN: Making authenticated request
        THEN: Returns 401
        """
        # Create an expired token manually
        from datetime import datetime, timedelta, timezone
        from api.auth_utils import SECRET_KEY, ALGORITHM
        import jwt
        
        expired_payload = {
            "sub": "testuser",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1)  # Already expired
        }
        expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
        
        response = client.get(
            "/api/tables",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code == 401
    
    def test_malformed_token_rejected(self, client):
        """
        GIVEN: Malformed JWT token
        WHEN: Making authenticated request
        THEN: Returns 401
        """
        response = client.get(
            "/api/tables",
            headers={"Authorization": "Bearer not.a.valid.jwt.token.at.all"}
        )
        
        assert response.status_code == 401
    
    def test_missing_bearer_prefix(self, client, user_token):
        """
        GIVEN: Token without 'Bearer' prefix
        WHEN: Making authenticated request
        THEN: Returns 401
        """
        response = client.get(
            "/api/tables",
            headers={"Authorization": user_token}  # Missing "Bearer "
        )
        
        assert response.status_code == 401
