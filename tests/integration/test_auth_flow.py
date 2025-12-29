import pytest
import requests
import uuid

BASE_URL = "http://localhost:1234"

@pytest.fixture
def admin_token():
    """Get admin token for tests."""
    # Assuming default admin exists: admin/admin123
    response = requests.post(f"{BASE_URL}/auth/token", data={
        "username": "admin",
        "password": "admin123"
    })
    
    if response.status_code != 200:
        # Try to create admin if not exists (though main.py does this on startup)
        # This part assumes admin is already there as per main.py logic
        pytest.fail(f"Could not login as admin. Status: {response.status_code}, Body: {response.text}")
        
    return response.json()["access_token"]

def test_full_auth_flow(admin_token):
    """
    Test the complete auth lifecycle:
    1. Public signup (created as pending)
    2. Try login (should fail)
    3. Admin lists pending users
    4. Admin approves user
    5. User login (should succeed)
    6. Admin deletes user
    """
    
    # Generate unique test user
    random_id = str(uuid.uuid4())[:8]
    username = f"testuser_{random_id}"
    password = "testpassword123"
    email = f"test_{random_id}@example.com"
    
    print(f"\nTesting with user: {username}")
    
    # 1. Signup
    print("1. Signup...")
    signup_resp = requests.post(f"{BASE_URL}/auth/signup", json={
        "username": username,
        "password": password,
        "email": email
    })
    assert signup_resp.status_code == 200
    assert "Signup request submitted" in signup_resp.json()["message"]
    
    # 2. Try Login (Should fail as user is pending/not in users table)
    print("2. Try login (pending)...")
    login_resp = requests.post(f"{BASE_URL}/auth/token", data={
        "username": username,
        "password": password
    })
    # Expect 401 because user is not in 'users' table yet
    assert login_resp.status_code == 401
    
    # 3. Admin lists pending users
    print("3. Admin list pending...")
    pending_resp = requests.get(
        f"{BASE_URL}/api/admin/pending-users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert pending_resp.status_code == 200
    pending_users = pending_resp.json()
    
    # Verify our user is in the list
    found_pending = next((u for u in pending_users if u["username"] == username), None)
    assert found_pending is not None
    user_id = found_pending["id"]
    
    # 4. Admin approves user
    print(f"4. Admin approve user {user_id}...")
    approve_resp = requests.post(
        f"{BASE_URL}/api/admin/pending-users/{user_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert approve_resp.status_code == 200
    
    # 5. User login (Should now succeed)
    print("5. User login (active)...")
    login_success_resp = requests.post(f"{BASE_URL}/auth/token", data={
        "username": username,
        "password": password
    })
    assert login_success_resp.status_code == 200
    token_data = login_success_resp.json()
    assert "access_token" in token_data
    
    # Verify user profile
    user_token = token_data["access_token"]
    profile_resp = requests.get(
        f"{BASE_URL}/auth/me",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert profile_resp.status_code == 200
    assert profile_resp.json()["username"] == username
    
    # 6. Admin deletes user
    print("6. Admin delete user...")
    # First get the real user ID from the user list (since pending ID might differ from user ID)
    users_resp = requests.get(
        f"{BASE_URL}/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    users_list = users_resp.json()
    active_user = next((u for u in users_list if u["username"] == username), None)
    assert active_user is not None
    # active_user_id = active_user["id"] # Not needed as delete takes username
    
    delete_resp = requests.delete(
        f"{BASE_URL}/api/admin/users/{username}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert delete_resp.status_code == 200
    
    # Verify deletion by trying to login again
    print("7. Verify deletion...")
    final_login = requests.post(f"{BASE_URL}/auth/token", data={
        "username": username,
        "password": password
    })
    assert final_login.status_code == 401

if __name__ == "__main__":
    # Allow running directly for debugging
    try:
        # Need to fetch token manually if running as script
        resp = requests.post(f"{BASE_URL}/auth/token", data={"username": "admin", "password": "admin123"})
        if resp.status_code != 200:
            raise Exception(f"Admin login failed: {resp.status_code} - {resp.text}")
            
        admin_tok = resp.json()["access_token"]
        test_full_auth_flow(admin_tok)
        print("\nSUCCESS: Test Passed Successfully!")
    except Exception as e:
        print(f"\nFAILURE: Test Failed: {e}")
        exit(1)
