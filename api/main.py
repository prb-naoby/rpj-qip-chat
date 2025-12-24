"""
FastAPI Application Entry Point for QIP Data Assistant.
Main application with CORS, database init, and router configuration.
Following exim-chat pattern.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from api import database, auth_utils
from api.routes import router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    print("Initializing database...")
    database.init_database()
    
    # Validate API keys
    openai_key = os.getenv("OPENAI_API_KEY", "")
    google_key = os.getenv("GOOGLE_API_KEY", "")
    
    if not openai_key and not google_key:
        print("WARNING: No AI API keys configured (OPENAI_API_KEY or GOOGLE_API_KEY)")
        print("   Chat functionality will not work until API keys are set.")
    else:
        if openai_key:
            print(f"[OK] OpenAI API key configured (ends with ...{openai_key[-4:]})")
        if google_key:
            print(f"[OK] Google API key configured (ends with ...{google_key[-4:]})")
    
    # Create default admin if not exists
    admin_user = database.get_user_by_username("admin")
    if not admin_user:
        print("Creating default admin user...")
        admin_pwd = auth_utils.get_password_hash("admin123")
        database.add_user("admin", admin_pwd, "admin")
        print("Admin user created (username: admin, password: admin123)")
    
    print("QIP Data Assistant API ready!")
    
    yield
    
    # Shutdown
    print("Shutting down QIP Data Assistant API...")


app = FastAPI(
    title="QIP Data Assistant API",
    description="API for QIP Data Assistant with chat, table management, and OneDrive integration",
    version="1.0.0",
    lifespan=lifespan
)


# CORS Configuration
cors_origins_env = os.getenv("CORS_ORIGINS", "*")
if cors_origins_env == "*":
    origins = ["*"]
else:
    origins = [origin.strip() for origin in cors_origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https?://.*",  # Allow any origin as fallback
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Mount Routes
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to QIP Data Assistant API"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
