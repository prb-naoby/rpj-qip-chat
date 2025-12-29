from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

UPLOAD_DIR = BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

CATALOG_DB = BASE_DIR / "data" / "catalog.db"
DEFAULT_LLM_MODEL = os.getenv("PANDASAI_LLM_MODEL", "gpt-5-mini")
UPLOAD_MAX_MB = int(os.getenv("UPLOAD_MAX_MB", 25))

class AppSettings:
    """Simple settings accessor to keep imports tidy."""

    base_dir: Path = BASE_DIR
    upload_dir: Path = UPLOAD_DIR
    catalog_db: Path = CATALOG_DB
    default_llm_model: str = DEFAULT_LLM_MODEL
    upload_max_mb: int = UPLOAD_MAX_MB
    
    # API Keys (from environment)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    
    # Document Retrieval Settings (Qdrant + Gemini)
    qdrant_url: str = os.getenv("QDRANT_URL", "")
    qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    embed_model: str = os.getenv("EMBED_MODEL", "gemini-embedding-001")
    gemini_llm_model: str = os.getenv("GEMINI_LLM_MODEL", "gemini-2.0-flash-lite")
    embed_dim: int = int(os.getenv("EMBED_DIM", "3072"))
    
    # Document Ingestion Settings
    document_root_path: str = os.getenv("DOCUMENT_ROOT_PATH", "")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "qip_documents")

