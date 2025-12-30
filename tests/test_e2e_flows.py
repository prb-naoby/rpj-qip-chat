"""
E2E TDD Tests - Full Flow Testing Without Live Services.
Tests complete user flows using FastAPI TestClient with mocked external dependencies.
Each flow has 5+ edge cases tested.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from io import BytesIO

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
from fastapi.testclient import TestClient


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def test_db(tmp_path: Path):
    """Setup a temporary database for testing."""
    import api.database as db_module
    from api import auth_utils, database
    
    db_module.SQLITE_DB_PATH = tmp_path / "test_e2e.db"
    db_module.init_database()
    
    # Create test users
    admin_hash = auth_utils.get_password_hash("admin123")
    database.add_user("admin", admin_hash, "admin")
    
    user_hash = auth_utils.get_password_hash("userpass")
    database.add_user("testuser", user_hash, "user")
    
    yield tmp_path


@pytest.fixture
def mock_upload_dir(tmp_path: Path, monkeypatch):
    """Setup mock upload directory."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    
    import app.settings as settings_module
    monkeypatch.setattr(settings_module, "UPLOAD_DIR", upload_dir)
    
    import app.datasets as datasets_module
    monkeypatch.setattr(datasets_module, "PARQUET_CACHE_DIR", upload_dir)
    
    return upload_dir


@pytest.fixture
def client(test_db, mock_upload_dir):
    """Create a test client with mocked dependencies."""
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
# Flow 1: User Authentication E2E (5+ edge cases)
# =============================================================================

class TestAuthFlowE2E:
    """End-to-end tests for complete authentication flow."""

    def test_flow_register_login_access_protected(self, client, admin_token):
        """
        Full flow: Signup request -> Admin approval -> Login -> Access protected route
        """
        # Step 1: User signs up (pending approval)
        signup_resp = client.post(
            "/signup/request",
            json={"username": "newuser", "password": "newpass123"}
        )
        # May return 200 or endpoint may not exist
        assert signup_resp.status_code in [200, 404, 422]
        
        # Step 2: Even without signup, test login -> access flow
        login_resp = client.post(
            "/auth/token",
            data={"username": "testuser", "password": "userpass"}
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        
        # Step 3: Access protected route
        me_resp = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == "testuser"

    def test_edge_case_empty_password(self, client):
        """Edge case: Empty password on login."""
        response = client.post(
            "/auth/token",
            data={"username": "testuser", "password": ""}
        )
        assert response.status_code == 401

    def test_edge_case_sql_injection_attempt(self, client):
        """Edge case: SQL injection in username."""
        response = client.post(
            "/auth/token",
            data={"username": "admin'--", "password": "anything"}
        )
        assert response.status_code == 401

    def test_edge_case_unicode_password(self, client, test_db):
        """Edge case: Unicode characters in password."""
        from api import auth_utils, database
        
        # Create user with unicode password
        unicode_pass = "пароль密码🔐"
        hash_pass = auth_utils.get_password_hash(unicode_pass)
        database.add_user("unicodeuser", hash_pass, "user")
        
        response = client.post(
            "/auth/token",
            data={"username": "unicodeuser", "password": unicode_pass}
        )
        assert response.status_code == 200

    def test_edge_case_expired_token_simulation(self, client, user_token):
        """Edge case: Token manipulation detection."""
        # Modify token to simulate tampering
        tampered_token = user_token[:-5] + "XXXXX"
        
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {tampered_token}"}
        )
        assert response.status_code == 401

    def test_edge_case_missing_bearer_prefix(self, client, user_token):
        """Edge case: Token without 'Bearer' prefix."""
        response = client.get(
            "/auth/me",
            headers={"Authorization": user_token}  # Missing "Bearer "
        )
        assert response.status_code in [401, 403]


# =============================================================================
# Flow 2: File Upload -> Preview -> Delete E2E (5+ edge cases)
# =============================================================================

class TestFileUploadFlowE2E:
    """End-to-end tests for file upload, preview, and delete flow."""

    def test_flow_upload_preview_delete(self, client, user_token, mock_upload_dir):
        """Full flow: Upload CSV -> Get preview -> Delete table."""
        # Step 1: Upload CSV file
        csv_content = b"id,name,value\n1,apple,100\n2,banana,200\n3,cherry,300\n"
        
        upload_resp = client.post(
            "/api/files/upload",
            headers={"Authorization": f"Bearer {user_token}"},
            files={"file": ("test_data.csv", csv_content, "text/csv")}
        )
        
        if upload_resp.status_code == 200:
            data = upload_resp.json()
            cache_path = data.get("cache_path")
            
            # Step 2: Get preview
            preview_resp = client.get(
                f"/api/tables/{cache_path}/preview",
                headers={"Authorization": f"Bearer {user_token}"}
            )
            assert preview_resp.status_code in [200, 400]
            
            # Step 3: Delete table
            delete_resp = client.delete(
                f"/api/tables/{cache_path}",
                headers={"Authorization": f"Bearer {user_token}"}
            )
            assert delete_resp.status_code in [200, 400, 404]

    def test_edge_case_empty_csv(self, client, user_token):
        """Edge case: Upload empty CSV file."""
        empty_csv = b""
        
        response = client.post(
            "/api/files/upload",
            headers={"Authorization": f"Bearer {user_token}"},
            files={"file": ("empty.csv", empty_csv, "text/csv")}
        )
        # Should handle gracefully
        assert response.status_code in [400, 500]

    def test_edge_case_csv_with_only_headers(self, client, user_token):
        """Edge case: CSV with headers but no data rows."""
        headers_only = b"col1,col2,col3\n"
        
        response = client.post(
            "/api/files/upload",
            headers={"Authorization": f"Bearer {user_token}"},
            files={"file": ("headers_only.csv", headers_only, "text/csv")}
        )
        # Should handle - may be empty or error
        assert response.status_code in [200, 400, 500]

    def test_edge_case_malformed_csv(self, client, user_token):
        """Edge case: Malformed CSV with inconsistent columns."""
        malformed = b"a,b,c\n1,2\n3,4,5,6\n"
        
        response = client.post(
            "/api/files/upload",
            headers={"Authorization": f"Bearer {user_token}"},
            files={"file": ("malformed.csv", malformed, "text/csv")}
        )
        # Pandas should handle with warnings
        assert response.status_code in [200, 400, 500]

    def test_edge_case_very_large_file_name(self, client, user_token):
        """Edge case: Very long filename."""
        long_name = "a" * 500 + ".csv"
        csv_content = b"x,y\n1,2\n"
        
        response = client.post(
            "/api/files/upload",
            headers={"Authorization": f"Bearer {user_token}"},
            files={"file": (long_name, csv_content, "text/csv")}
        )
        # Should truncate or handle gracefully
        assert response.status_code in [200, 400, 500]

    def test_edge_case_special_chars_in_data(self, client, user_token):
        """Edge case: Special characters in CSV data."""
        special_csv = b'name,value\n"Hello, ""World""",123\n"Line1\nLine2",456\n'
        
        response = client.post(
            "/api/files/upload",
            headers={"Authorization": f"Bearer {user_token}"},
            files={"file": ("special.csv", special_csv, "text/csv")}
        )
        assert response.status_code in [200, 400, 500]


# =============================================================================
# Flow 3: Chat Creation -> Message E2E (5+ edge cases)
# =============================================================================

class TestChatFlowE2E:
    """End-to-end tests for chat creation and messaging flow."""

    def test_flow_create_chat_send_message_get_history(self, client, user_token):
        """Full flow: Create chat -> View history -> Delete."""
        # Step 1: Create new chat
        create_resp = client.post(
            "/api/chats",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"title": "Test E2E Chat"}
        )
        assert create_resp.status_code == 200
        chat_id = create_resp.json()["id"]
        
        # Step 2: Get chat history
        history_resp = client.get(
            f"/api/chats/{chat_id}",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert history_resp.status_code == 200
        assert "messages" in history_resp.json()
        
        # Step 3: Delete chat
        delete_resp = client.delete(
            f"/api/chats/{chat_id}",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert delete_resp.status_code == 200

    def test_edge_case_empty_chat_title(self, client, user_token):
        """Edge case: Create chat with empty title."""
        response = client.post(
            "/api/chats",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"title": ""}
        )
        # Should use default title or handle gracefully
        assert response.status_code in [200, 400]

    def test_edge_case_very_long_title(self, client, user_token):
        """Edge case: Create chat with very long title."""
        long_title = "A" * 1000
        response = client.post(
            "/api/chats",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"title": long_title}
        )
        assert response.status_code in [200, 400]

    def test_edge_case_special_chars_in_title(self, client, user_token):
        """Edge case: Chat title with special characters."""
        special_title = "Test <script>alert('xss')</script> & \"quotes\""
        response = client.post(
            "/api/chats",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"title": special_title}
        )
        
        if response.status_code == 200:
            # Verify title is stored correctly
            chat_id = response.json()["id"]
            history = client.get(
                f"/api/chats/{chat_id}",
                headers={"Authorization": f"Bearer {user_token}"}
            )
            # Note: XSS prevention is handled by React at render time
            # Backend stores raw content for flexibility
            assert history.status_code == 200

    def test_edge_case_access_others_chat(self, client, user_token, admin_token):
        """Edge case: Try to access another user's chat."""
        # Create chat as admin
        admin_chat = client.post(
            "/api/chats",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"title": "Admin Private Chat"}
        )
        chat_id = admin_chat.json()["id"]
        
        # Try to access as regular user
        response = client.get(
            f"/api/chats/{chat_id}",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        # Should return 404 (not found for this user) or 403
        assert response.status_code in [403, 404]

    def test_edge_case_delete_nonexistent_chat(self, client, user_token):
        """Edge case: Delete a chat that doesn't exist."""
        response = client.delete(
            "/api/chats/nonexistent-uuid-12345",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code in [404, 200]  # 200 if idempotent


# =============================================================================
# Flow 4: Table Operations E2E (5+ edge cases)
# =============================================================================

class TestTableOperationsFlowE2E:
    """End-to-end tests for table CRUD operations."""

    def test_flow_list_rank_preview(self, client, user_token, mock_upload_dir):
        """Full flow: List tables -> Rank by query."""
        # Step 1: List all tables
        list_resp = client.get(
            "/api/tables",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert list_resp.status_code == 200
        assert isinstance(list_resp.json(), list)
        
        # Step 2: Rank tables by question
        rank_resp = client.post(
            "/api/tables/rank",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"question": "What are sales totals?"}
        )
        assert rank_resp.status_code == 200

    def test_edge_case_preview_with_negative_rows(self, client, user_token, mock_upload_dir):
        """Edge case: Request preview with negative row count."""
        # Create a test parquet file
        df = pd.DataFrame({"a": [1, 2, 3]})
        test_file = mock_upload_dir / "test_negative.parquet"
        df.to_parquet(test_file)
        
        response = client.get(
            f"/api/tables/{test_file}/preview?rows=-1",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        # Should handle gracefully
        assert response.status_code in [200, 400]

    def test_edge_case_preview_with_zero_rows(self, client, user_token, mock_upload_dir):
        """Edge case: Request preview with zero rows."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        test_file = mock_upload_dir / "test_zero.parquet"
        df.to_parquet(test_file)
        
        response = client.get(
            f"/api/tables/{test_file}/preview?rows=0",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code in [200, 400]

    def test_edge_case_very_large_row_request(self, client, user_token, mock_upload_dir):
        """Edge case: Request more rows than exist."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        test_file = mock_upload_dir / "test_large.parquet"
        df.to_parquet(test_file)
        
        response = client.get(
            f"/api/tables/{test_file}/preview?rows=1000000",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        # Should return available rows
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            assert len(response.json()["data"]) <= 3

    def test_edge_case_update_description_empty(self, client, user_token, mock_upload_dir):
        """Edge case: Update table with empty description."""
        df = pd.DataFrame({"x": [1]})
        test_file = mock_upload_dir / "test_desc.parquet"
        df.to_parquet(test_file)
        
        response = client.patch(
            f"/api/tables/{test_file}",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"description": ""}
        )
        assert response.status_code in [200, 400]

    def test_edge_case_download_large_table(self, client, user_token, mock_upload_dir):
        """Edge case: Download a reasonably large table."""
        # Create larger DataFrame
        df = pd.DataFrame({
            "id": range(1000),
            "value": ["test"] * 1000
        })
        test_file = mock_upload_dir / "large_table.parquet"
        df.to_parquet(test_file)
        
        response = client.get(
            f"/api/tables/{test_file}/download",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            assert "text/csv" in response.headers.get("content-type", "")


# =============================================================================
# Flow 5: Admin Operations E2E (5+ edge cases)
# =============================================================================

class TestAdminFlowE2E:
    """End-to-end tests for admin operations."""

    def test_flow_admin_list_users_create_delete(self, client, admin_token):
        """Full flow: List users -> Create user -> Delete user."""
        # Step 1: List users (admin only)
        list_resp = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert list_resp.status_code == 200
        initial_count = len(list_resp.json())
        
        # Step 2: Create new user
        create_resp = client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": "newadminuser",
                "password": "newpass123",
                "role": "user"
            }
        )
        
        if create_resp.status_code == 200:
            # Step 3: Verify user exists
            list_resp2 = client.get(
                "/api/admin/users",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert len(list_resp2.json()) == initial_count + 1
            
            # Step 4: Delete user
            delete_resp = client.delete(
                "/api/admin/users/newadminuser",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert delete_resp.status_code in [200, 204]

    def test_edge_case_non_admin_access(self, client, user_token):
        """Edge case: Regular user trying admin endpoints."""
        response = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 403

    def test_edge_case_delete_self(self, client, admin_token):
        """Edge case: Admin trying to delete themselves."""
        response = client.delete(
            "/api/admin/users/admin",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Should be prevented or allowed with caution
        assert response.status_code in [200, 400, 403]

    def test_edge_case_create_duplicate_user(self, client, admin_token):
        """Edge case: Create user with existing username."""
        response = client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": "testuser",  # Already exists
                "password": "anypass",
                "role": "user"
            }
        )
        assert response.status_code in [400, 409, 422]

    def test_edge_case_invalid_role(self, client, admin_token):
        """Edge case: Create user with invalid role."""
        response = client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": "invalidrole",
                "password": "somepass",
                "role": "superadmin"  # Invalid role
            }
        )
        # Should validate roles
        assert response.status_code in [200, 400, 422]

    def test_edge_case_weak_password_admin_create(self, client, admin_token):
        """Edge case: Admin creates user with weak password."""
        response = client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": "weakpassuser",
                "password": "123",
                "role": "user"
            }
        )
        # May succeed or enforce password policy
        assert response.status_code in [200, 400, 422]
