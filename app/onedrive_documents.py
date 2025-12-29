"""
Document-specific OneDrive file listing.
Lists PDF, PPT, PPTX, PNG, JPG files instead of Excel files.
"""
from __future__ import annotations

import os
import time
from typing import List
from urllib.parse import quote

import requests

from app import onedrive_config as config
from app.settings import AppSettings

settings = AppSettings()

# Document extensions (non-Excel)
DOCUMENT_EXTENSIONS = [".pdf", ".ppt", ".pptx", ".png", ".jpg", ".jpeg"]


def get_access_token() -> str:
    """Get Azure AD access token via client credentials."""
    if not (config.MS_TENANT_ID and config.MS_CLIENT_ID and config.MS_CLIENT_SECRET):
        raise RuntimeError("OneDrive credentials not configured")

    token_url = f"https://login.microsoftonline.com/{config.MS_TENANT_ID}/oauth2/v2.0/token"
    payload = {
        "client_id": config.MS_CLIENT_ID,
        "client_secret": config.MS_CLIENT_SECRET,
        "grant_type": "client_credentials",
        "scope": config.GRAPH_SCOPE,
    }

    resp = requests.post(token_url, data=payload, timeout=10)
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("No access_token in response")
    return token


def _graph_get(url: str, token: str) -> dict:
    """GET request with retry on 429."""
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(5):
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", "2"))
            time.sleep(wait)
            continue
        if resp.status_code == 404:
            raise RuntimeError("Folder not found in OneDrive.")
        if resp.status_code == 403:
            raise RuntimeError("Access denied to OneDrive folder.")
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    return {}


def list_document_files(root_path: str = None) -> List[dict]:
    """
    List all document files (PDF, PPT, PPTX, PNG, JPG) in OneDrive folder.
    Recursively traverses child folders.
    
    Args:
        root_path: Override root path (defaults to DOCUMENT_ROOT_PATH)
        
    Returns:
        List of file metadata dicts
    """
    results: List[dict] = []
    
    # Use DOCUMENT_ROOT_PATH from settings, not ONEDRIVE_ROOT_PATH
    root_path = root_path or settings.document_root_path
    if not root_path:
        print("DOCUMENT_ROOT_PATH not configured")
        return results
    
    root_path = root_path.strip("/")
    encoded_path = quote(root_path, safe="/")
    drive_id = config.ONEDRIVE_DRIVE_ID
    
    if not drive_id:
        print("ONEDRIVE_DRIVE_ID not configured")
        return results

    token = get_access_token()

    # Get root folder
    root_url = f"{config.GRAPH_BASE_URL}/drives/{drive_id}/root:/{encoded_path}"
    try:
        root_item = _graph_get(root_url, token)
    except Exception as e:
        print(f"Failed to access root folder: {e}")
        return results

    if "id" not in root_item:
        print("Root folder not found")
        return results

    # Traverse folders using stack (depth-first)
    stack = [(root_item["id"], root_path)]
    while stack:
        parent_id, parent_path = stack.pop()
        next_url = f"{config.GRAPH_BASE_URL}/drives/{drive_id}/items/{parent_id}/children"

        while next_url:
            data = _graph_get(next_url, token)
            for item in data.get("value", []):
                name = item.get("name", "")
                item_id = item.get("id")
                if not item_id:
                    continue

                child_path = f"{parent_path}/{name}"

                # If folder, add to stack for traversal
                if item.get("folder"):
                    stack.append((item_id, child_path))
                    continue

                # Check if file has supported document extension
                if not any(name.lower().endswith(ext) for ext in DOCUMENT_EXTENSIONS):
                    continue

                results.append({
                    "id": item_id,
                    "name": name,
                    "path": child_path,
                    "size": item.get("size", 0),
                    "downloadUrl": item.get("@microsoft.graph.downloadUrl"),
                    "webUrl": item.get("webUrl"),
                    "lastModified": item.get("lastModifiedDateTime"),
                })

            next_url = data.get("@odata.nextLink")

    return results


def download_file(download_url: str) -> bytes:
    """Download file bytes."""
    resp = requests.get(download_url, timeout=300)
    if resp.status_code == 404:
        raise RuntimeError("Download URL expired or file not found.")
    if resp.status_code == 403:
        raise RuntimeError("Access denied. Download URL may have expired.")
    resp.raise_for_status()
    return resp.content


def get_file_details(file_id: str) -> dict:
    """Get file details by ID (useful for refreshing download URL)."""
    drive_id = config.ONEDRIVE_DRIVE_ID
    token = get_access_token()
    url = f"{config.GRAPH_BASE_URL}/drives/{drive_id}/items/{file_id}"
    return _graph_get(url, token)
