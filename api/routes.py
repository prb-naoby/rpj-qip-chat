"""
API Routes for QIP Data Assistant.
Following exim-chat pattern with JWT authentication.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Any

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from api import auth_utils, database, chat_service
from api.intent_classifier import interpret_table_selection, generate_clarification_message, classify_user_intent
from app.job_manager import job_manager, JobStatus
from app.data_store import DatasetCatalog
from app.datasets import (
    list_all_cached_data,
    delete_cached_data,
    build_parquet_cache,
    build_parquet_cache_from_df,
    update_existing_parquet_cache,
    append_to_parquet_cache,
    get_target_table_info,
    apply_stored_transform,
    CachedDataInfo,
)
from app.qa_engine import PandasAIClient
from app.table_router import route_question_to_tables, format_routing_explanation
from app.data_analyzer import analyze_and_generate_transform, execute_transform, regenerate_with_feedback
from app import onedrive_config, onedrive_client
from app.settings import AppSettings, safe_resolve_path

import pandas as pd
from pathlib import Path
import json
import tempfile

router = APIRouter()
settings = AppSettings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


# =============================================================================
# Pydantic Models
# =============================================================================

class Token(BaseModel):
    access_token: str
    token_type: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    display_name: Optional[str] = None


class ChatRequest(BaseModel):
    question: str
    table_id: Optional[str] = None
    chat_id: str


class ChatResponse(BaseModel):
    response: str
    code: Optional[str] = None
    explanation: Optional[str] = None
    ui_components: List[dict] = []
    has_error: bool = False

class ChatListResponse(BaseModel):
    id: str
    title: str
    updated_at: str

class ChatHistoryResponse(BaseModel):
    chat: ChatListResponse
    messages: List[dict]

class CreateChatRequest(BaseModel):
    title: Optional[str] = "New Chat"


class TableInfo(BaseModel):
    cache_path: str
    display_name: str
    original_file: str
    sheet_name: Optional[str] = None
    n_rows: int
    n_cols: int
    cached_at: str
    file_size_mb: float
    description: Optional[str] = None


class TableRankRequest(BaseModel):
    question: str


class AnalyzeRequest(BaseModel):
    table_id: str
    user_description: Optional[str] = ""
    metadata: Optional[dict] = None


class TransformRequest(BaseModel):
    table_id: str
    transform_code: str
    display_name: Optional[str] = None
    replace_original: bool = False  # If True, overwrite original table; if False, create new table


class TransformPreviewResponse(BaseModel):
    preview_data: List[dict]
    columns: List[str]
    total_rows: int
    error: Optional[str] = None


class TransformConfirmResponse(BaseModel):
    cache_path: str
    n_rows: int
    n_cols: int
    message: str


class AppendRequest(BaseModel):
    target_table_id: str       # Existing table to append to
    source_table_id: str       # Uploaded temp table path
    description: str = ""      # User description for this batch


class AppendResponse(BaseModel):
    cache_path: str
    total_rows: int
    rows_added: int
    message: str
    error: Optional[str] = None


class AppendValidateRequest(BaseModel):
    source_table_id: str        # New data parquet path
    target_table_id: str        # Existing table to append to


class AppendValidateResponse(BaseModel):
    columns_match: bool                     # True if columns already match (no transform needed)
    compatible: bool                        # True if structure is compatible for transform
    issues: List[str]                       # List of column/structure differences
    target_has_transform: bool              # True if target has stored transform code
    transform_explanation: Optional[str]    # Natural language explanation of stored transform
    similarity_reason: Optional[str]        # LLM's explanation of compatibility
    target_columns: List[str]               # Columns in target table
    source_columns: List[str]               # Columns in source table


class AppendPreviewRequest(BaseModel):
    source_table_id: str
    target_table_id: str
    user_feedback: Optional[str] = None     # User feedback to fix transform


class AppendPreviewResponse(BaseModel):
    success: bool
    preview_data: List[dict]                # Transformed preview rows
    preview_columns: List[str]              # Column names after transform
    error: Optional[str] = None             # Error message if transform failed
    generated_code: Optional[str] = None    # The Python code generated (if applicable)


class AppendConfirmRequest(BaseModel):
    source_table_id: str
    target_table_id: str
    description: str = ""
    transform_code: Optional[str] = None    # Optional code to use (overrides stored)


class AppendGenerateTransformRequest(BaseModel):
    source_table_id: str
    target_table_id: str
    user_description: str = ""              # User's description of how to map columns



class ProfileUpdate(BaseModel):
    display_name: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


# =============================================================================
# Auth Dependencies
# =============================================================================

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Get current authenticated user from JWT token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = auth_utils.decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    user = database.get_user_by_username(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user


async def get_current_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Require admin role."""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# =============================================================================
# Auth Routes
# =============================================================================

@router.post("/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get access token."""
    user = database.get_user_by_username(form_data.username)
    
    if not user or not auth_utils.verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=auth_utils.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_utils.create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/auth/me", response_model=UserOut)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """Get current user info."""
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "display_name": current_user.get("display_name") or current_user["username"],
        "role": current_user["role"]
    }


@router.patch("/auth/profile")
async def update_profile(
    profile: ProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update user's display name."""
    success = database.update_user_display_name(current_user["username"], profile.display_name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update profile")
    return {"message": "Profile updated successfully", "display_name": profile.display_name}


@router.patch("/auth/password")
async def change_password(
    passwords: PasswordChange,
    current_user: dict = Depends(get_current_user)
):
    """Change user's password."""
    if not auth_utils.verify_password(passwords.current_password, current_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    new_hash = auth_utils.get_password_hash(passwords.new_password)
    success = database.update_user_password(current_user["username"], new_hash)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update password")
    return {"message": "Password changed successfully"}


# =============================================================================
# Admin Routes - User Management
# =============================================================================

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"
    display_name: Optional[str] = None


class SignupRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


@router.get("/api/admin/users")
async def admin_list_users(current_user: dict = Depends(get_current_admin)):
    """List all users (admin only)."""
    return database.list_users()


@router.post("/api/admin/users")
async def admin_create_user(
    user: UserCreate,
    current_user: dict = Depends(get_current_admin)
):
    """Create a new user (admin only)."""
    password_hash = auth_utils.get_password_hash(user.password)
    user_id = database.add_user(user.username, password_hash, user.role, user.display_name)
    if not user_id:
        raise HTTPException(status_code=400, detail="Username already exists")
    return {"message": f"User '{user.username}' created", "id": user_id}


@router.delete("/api/admin/users/{username}")
async def admin_delete_user(
    username: str,
    current_user: dict = Depends(get_current_admin)
):
    """Delete a user (admin only)."""
    if username == current_user["username"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    success = database.delete_user(username)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"User '{username}' deleted"}


# =============================================================================
# Pending Users (Registration Approval)
# =============================================================================

@router.post("/auth/signup")
async def signup_request(signup: SignupRequest):
    """Submit a signup request for admin approval."""
    # Check if username already exists
    existing = database.get_user_by_username(signup.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    pending = database.check_pending_username_exists(signup.username)
    if pending:
        raise HTTPException(status_code=400, detail="Signup request already pending for this username")
    
    password_hash = auth_utils.get_password_hash(signup.password)
    success = database.add_pending_user(signup.username, password_hash, signup.email)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to submit signup request")
    
    return {"message": "Signup request submitted. Please wait for admin approval."}


@router.get("/api/admin/pending-users")
async def admin_list_pending_users(current_user: dict = Depends(get_current_admin)):
    """List all pending user registrations (admin only)."""
    return database.get_pending_users()


@router.post("/api/admin/pending-users/{user_id}/approve")
async def admin_approve_user(
    user_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """Approve a pending user registration (admin only)."""
    success = database.approve_pending_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pending user not found")
    return {"message": "User approved successfully"}


@router.post("/api/admin/pending-users/{user_id}/reject")
async def admin_reject_user(
    user_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """Reject a pending user registration (admin only)."""
    success = database.reject_pending_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pending user not found")
    return {"message": "User rejected"}


# =============================================================================
# Table Routes
# =============================================================================

@router.get("/api/tables", response_model=List[TableInfo])
async def list_tables(current_user: dict = Depends(get_current_user)):
    """List all cached tables."""
    cached_list = list_all_cached_data()
    
    return [
        TableInfo(
            cache_path=str(t.cache_path),
            display_name=t.display_name,
            original_file=t.original_file,
            sheet_name=t.sheet_name,
            n_rows=t.n_rows,
            n_cols=t.n_cols,
            cached_at=t.cached_at,
            file_size_mb=t.file_size_mb,
            description=t.description
        )
        for t in cached_list
    ]


@router.get("/api/tables/{table_id:path}/preview")
async def get_table_preview(
    table_id: str,
    rows: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get preview of a table."""
    try:
        # Validate path to prevent traversal attacks
        try:
            cache_path = safe_resolve_path(table_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid table path")
            
        if not cache_path.exists():
            raise HTTPException(status_code=404, detail="Table not found")
        
        # Offload pandas read to threadpool
        df = await run_in_threadpool(lambda: pd.read_parquet(cache_path).head(rows))
        
        # Convert to JSON-serializable format
        return {
            "columns": list(df.columns),
            "data": df.fillna("").to_dict(orient="records"),
            "total_rows": len(df)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to load table preview")


class UpdateDescriptionRequest(BaseModel):
    description: Optional[str] = None
    column_descriptions: Optional[dict] = None
    display_name: Optional[str] = None


@router.patch("/api/tables/{table_id:path}")
async def update_table_description(
    table_id: str,
    request: UpdateDescriptionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update table description and column descriptions."""
    try:
        # Validate path to prevent traversal attacks
        try:
            cache_path = safe_resolve_path(table_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid table path")
            
        if not cache_path.exists():
            raise HTTPException(status_code=404, detail="Table not found")
        
        # Use the filename stem as cache_id
        cache_id = cache_path.stem
        
        # Update in catalog (offload DB write)
        from app.data_store import DatasetCatalog
        catalog = DatasetCatalog()
        await run_in_threadpool(
            catalog.update_cached_sheet_metadata,
            cache_id=cache_id,
            description=request.description,
            column_descriptions=request.column_descriptions,
            display_name=request.display_name
        )
        
        return {"message": "Description updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update table")


@router.delete("/api/tables/{table_id:path}")
async def delete_table(
    table_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a cached table."""
    try:
        # Validate path to prevent traversal attacks
        try:
            cache_path = safe_resolve_path(table_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid table path")
            
        await run_in_threadpool(delete_cached_data, cache_path)
        return {"message": "Table deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete table")


@router.get("/api/tables/{table_id:path}/download")
async def download_table_csv(
    table_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Download a table as CSV file."""
    import io
    
    # Validate path to prevent traversal attacks
    try:
        cache_path = safe_resolve_path(table_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid table path")
        
    if not cache_path.exists():
        raise HTTPException(status_code=404, detail="Table not found")
    
    try:
        def _get_csv_content():
            df = pd.read_parquet(cache_path)
            output = io.StringIO()
            df.to_csv(output, index=False)
            output.seek(0)
            return output.getvalue()

        csv_content = await run_in_threadpool(_get_csv_content)
        
        # Get filename from cache path
        filename = cache_path.stem + ".csv"
        
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to download table")


@router.post("/api/tables/rank")
async def rank_tables(
    request: TableRankRequest,
    current_user: dict = Depends(get_current_user)
):
    """Rank tables by relevance to a question."""
    return chat_service.rank_tables_logic(request.question)


# =============================================================================
# Chat Routes
# =============================================================================

@router.get("/api/chats", response_model=List[ChatListResponse])
async def list_user_chats(current_user: dict = Depends(get_current_user)):
    """List all chat sessions for the user."""
    return chat_service.get_chats(current_user["id"])

class CreateChatRequest(BaseModel):
    title: str = "New Chat"

class UpdateChatRequest(BaseModel):
    title: str

@router.post("/api/chats", response_model=ChatListResponse)
async def create_chat(
    request: CreateChatRequest, 
    current_user: dict = Depends(get_current_user)
):
    """Create a new chat session."""
    chat = chat_service.create_chat(current_user["id"], request.title)
    if not chat:
        raise HTTPException(status_code=500, detail="Failed to create chat")
    return chat

@router.put("/api/chats/{chat_id}", response_model=ChatListResponse)
async def update_chat(
    chat_id: str,
    request: UpdateChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update a chat session's title."""
    chat = chat_service.update_chat(chat_id, current_user["id"], request.title)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found or update failed")
    return chat

@router.get("/api/chats/{chat_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    chat_id: str, 
    current_user: dict = Depends(get_current_user)
):
    """Get messsage history for a specific chat."""
    chat = chat_service.get_chat(chat_id, current_user["id"])
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    messages = chat_service.get_messages(chat_id)
    return {
        "chat": chat,
        "messages": messages
    }

@router.delete("/api/chats/{chat_id}")
async def delete_chat(
    chat_id: str, 
    current_user: dict = Depends(get_current_user)
):
    """Delete a chat session."""
    success = chat_service.delete_chat(chat_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found or failed to delete")
    return {"message": "Chat deleted"}

@router.post("/api/chat/ask", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """Ask a question about a table."""
    # PandasAI uses OpenAI - use openai_api_key
    openai_key = settings.openai_api_key
    if not openai_key:
        raise HTTPException(status_code=500, detail="OpenAI API Key not configured (required for PandasAI)")

    # Verify chat ownership
    chat = chat_service.get_chat(request.chat_id, current_user["id"])
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
        
    # Save User Message
    chat_service.add_message(
        chat_id=request.chat_id,
        role="user",
        content=request.question,
        metadata={"table_id": request.table_id}
    )
    
    try:
        # Smart Table Selection
        if not request.table_id:
            ranked = await run_in_threadpool(chat_service.rank_tables_logic, request.question)
            if not ranked:
                raise HTTPException(status_code=400, detail="No relevant tables found. Please upload data first.")
                
            top_match = ranked[0]
            # Auto-select if score is decent and significantly better than runner-up
            # OR if it's the only table
            is_confident = False
            if len(ranked) == 1:
                is_confident = True
            elif top_match['score'] >= 4.0 and (top_match['score'] - ranked[1]['score'] > 2.0):
                is_confident = True
                
            if is_confident:
                 request.table_id = top_match['cache_path']
            else:
                 # Ambiguous - we can't easily ask for clarification in a non-streaming POST
                 # So we default to top match but warn, or fail. 
                 # For simpler UX in non-streaming, let's just use top match but maybe append a note?
                 # Or better, just fail and tell frontend to ask user.
                 # Actually, non-streaming is legacy/fallback. Let's force selection.
                 request.table_id = top_match['cache_path'] 
                 # raise HTTPException(status_code=300, detail="Ambiguous query. Please select a table.")

        cache_path = Path(request.table_id)
        if not cache_path.exists():
            raise HTTPException(status_code=404, detail="Table not found")
        
        df = await run_in_threadpool(pd.read_parquet, cache_path)
        client = PandasAIClient(api_key=openai_key)
        
        result = await run_in_threadpool(client.ask, df, request.question)
        
        # Save Assistant Message
        chat_service.add_message(
            chat_id=request.chat_id,
            role="assistant",
            content=result.response or "",
            metadata={
                "code": result.code,
                "explanation": result.explanation,
                "components": result.st_components,
                "has_error": result.has_error
            }
        )
        
        return ChatResponse(
            response=result.response or "",
            code=result.code,
            explanation=result.explanation,
            st_components=result.st_components,
            has_error=result.has_error
        )
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        # Save Error Message
        chat_service.add_message(
            chat_id=request.chat_id,
            role="assistant",
            content=error_msg,
            metadata={"has_error": True}
        )
        return ChatResponse(
            response=error_msg,
            has_error=True
        )


@router.post("/api/chat/stream")
async def stream_chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Stream chat response with Server-Sent Events (SSE).
    Sends progress updates, then final result.
    """
    # PandasAI uses OpenAI - use openai_api_key
    openai_key = settings.openai_api_key
    if not openai_key:
        raise HTTPException(status_code=500, detail="OpenAI API Key not configured (required for PandasAI)")
        
    # Verify chat ownership
    chat = chat_service.get_chat(request.chat_id, current_user["id"])
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    # Save User Message immediately
    chat_service.add_message(
        chat_id=request.chat_id,
        role="user",
        content=request.question,
        metadata={"table_id": request.table_id}
    )
    
    async def generate():
        final_result_obj = None
        successful_table = None
        original_question = request.question
        try:
            # Retrieve Chat History first (needed for follow-up detection)
            history = chat_service.get_messages(request.chat_id)
            previous_history = history[:-1] if history else []
            
            # Check for sticky table context (follow-up detection)
            last_used_table = None
            awaiting_clarification = False
            clarification_context = None
            
            for msg in reversed(previous_history):
                meta = msg.get("metadata") or {}
                # Check for awaiting clarification first
                if meta.get("awaiting_table_clarification") or meta.get("awaiting_table_hint"):
                    awaiting_clarification = True
                    clarification_context = meta
                    break
                # Then check for sticky table
                if meta.get("last_used_table"):
                    last_used_table = {
                        "cache_path": meta["last_used_table"],
                        "display_name": meta.get("last_used_table_name", "Previous Table")
                    }
                    break
            
            # Handle clarification response
            if awaiting_clarification and clarification_context:
                available_tables = clarification_context.get("available_tables", [])
                if not available_tables:
                    # Fall back to re-ranking
                    available_tables = chat_service.rank_tables_logic("")
                
                # Interpret user's table selection from their response
                selected_table = interpret_table_selection(request.question, available_tables)
                
                if selected_table:
                    # User selected a table - use it
                    yield f"data: {json.dumps({'type': 'progress', 'message': 'Using ' + selected_table.get('display_name', 'selected table') + '...'})}\n\n"
                    # Use original question from context if available
                    original_question = clarification_context.get("original_question", request.question)
                    request.table_id = selected_table.get("cache_path")
                else:
                    # Could not interpret - ask again  
                    clarify_msg = "I'm not sure which table you mean. " + generate_clarification_message(
                        [], available_tables, request.question
                    )
                    yield f"data: {json.dumps({'type': 'result', 'response': clarify_msg})}\n\n"
                    chat_service.add_message(
                        chat_id=request.chat_id,
                        role="assistant",
                        content=clarify_msg,
                        metadata={
                            "awaiting_table_clarification": True,
                            "available_tables": available_tables,
                            "original_question": clarification_context.get("original_question", request.question)
                        }
                    )
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return
            
            # Smart Table Selection with LLM Router
            tables_to_try = []
            routing_explanation = ""
            
            # Search documents in parallel with table routing
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Searching documents...'})}\n\n"
            try:
                from app.qdrant_service import search_chunks
                doc_chunks = await run_in_threadpool(search_chunks, original_question, limit=5)
                relevant_chunks = [c for c in doc_chunks if c.get('score', 0) >= 0.60]
            except Exception as doc_err:
                print(f"[DEBUG] Document search failed: {doc_err}")
                doc_chunks = []
                relevant_chunks = []
            
            # Use LLM router to rank tables
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Analyzing question...'})}\n\n"
            router_rankings = await run_in_threadpool(route_question_to_tables, original_question)
            routing_explanation = format_routing_explanation(router_rankings)
            
            # Convert router rankings to the format expected by rest of code
            ranked = [{"cache_path": str(r.table.cache_path), "display_name": r.table.display_name, "score": r.score} for r in router_rankings]
            
            if request.table_id:
                # User specified table explicitly (or selected from clarification)
                display_name = "Selected Table"
                for t in ranked:
                    if t.get("cache_path") == request.table_id:
                        display_name = t.get("display_name", "Selected Table")
                        break
                tables_to_try = [{"cache_path": request.table_id, "display_name": display_name}]
            elif last_used_table:
                # Follow-up question: prioritize last used table
                tables_to_try = [last_used_table]
                for t in ranked[:2]:
                    if t.get("cache_path") != last_used_table.get("cache_path"):
                        tables_to_try.append(t)
                yield f"data: {json.dumps({'type': 'progress', 'message': 'Continuing with ' + last_used_table['display_name'] + '...'})}\n\n"
            else:
                # New conversation: use LLM-ranked tables
                if not ranked:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'No tables available. Please upload data first.'})}\n\n"
                    return
                tables_to_try = ranked[:3]
                if ranked:
                    yield f"data: {json.dumps({'type': 'progress', 'message': 'Selected: ' + ranked[0]['display_name'] + '...'})}\n\n"
            
            client = PandasAIClient(api_key=openai_key)
            result = None
            successful_table = None
            errors_log = []
            
            for table in tables_to_try:
                cache_path = Path(table['cache_path'])
                table_name = table.get('display_name', 'Unknown')
                print(f"[DEBUG] Trying: {table_name}, path={cache_path}, exists={cache_path.exists()}")
                
                if not cache_path.exists():
                    errors_log.append(f"{table_name}: File not found")
                    continue
                
                try:
                    yield f"data: {json.dumps({'type': 'progress', 'message': 'Trying ' + table_name + '...'})}\n\n"
                    df = await run_in_threadpool(pd.read_parquet, cache_path)
                    
                    attempt_result = await run_in_threadpool(client.ask, df, request.question, history=previous_history)
                    print(f"[DEBUG] QA Result: has_error={attempt_result.has_error}")
                    
                    if not attempt_result.has_error:
                        result = attempt_result
                        successful_table = table
                        break
                    else:
                        errors_log.append(f"{table_name}: Query failed")
                except Exception as e:
                    print(f"[DEBUG] Exception in ask(): {type(e).__name__}: {e}")
                    errors_log.append(f"{table_name}: {str(e)[:100]}")
            
            if not result or result.has_error:
                # Data analysis failed - try document-only response if we have relevant chunks
                if relevant_chunks:
                    doc_response = "Berdasarkan dokumen yang relevan:\n\n"
                    for i, chunk in enumerate(relevant_chunks[:3], 1):
                        doc_response += f"**{i}. {chunk.get('filename', 'Document')}:**\n{chunk.get('text', '')[:500]}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'result', 'response': doc_response, 'document_sources': [c.get('filename') for c in relevant_chunks[:3]]})}\n\n"
                    chat_service.add_message(
                        chat_id=request.chat_id,
                        role="assistant",
                        content=doc_response,
                        metadata={"document_only": True, "document_sources": [c.get('filename') for c in relevant_chunks[:3]]}
                    )
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return
                
                # No documents either - generate conversational clarification
                tried_names = [t.get('display_name', 'Unknown') for t in tables_to_try]
                all_tables = ranked if ranked else tables_to_try
                clarify_msg = await run_in_threadpool(generate_clarification_message, tried_names, all_tables, original_question)
                
                yield f"data: {json.dumps({'type': 'result', 'response': clarify_msg})}\n\n"
                chat_service.add_message(
                    chat_id=request.chat_id,
                    role="assistant",
                    content=clarify_msg,
                    metadata={
                        "awaiting_table_clarification": True,
                        "available_tables": all_tables,
                        "tried_tables": tried_names,
                        "original_question": original_question
                    }
                )
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return
            
            # Progress: Processing result
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Processing results...'})}\n\n"
            
            # Final result - include routing explanation
            combined_explanation = ""
            if routing_explanation:
                combined_explanation = routing_explanation + "\n\n"
            if result.explanation:
                combined_explanation += result.explanation
            
            # Enhance response with document context if available
            enhanced_response = result.response or ""
            document_sources = []
            if relevant_chunks:
                # Synthesize document context using LLM
                try:
                    from app.document_processor import _get_gemini_client
                    from app.settings import AppSettings
                    doc_settings = AppSettings()
                    
                    # Prepare context for LLM
                    chunk_texts = []
                    for chunk in relevant_chunks[:3]:
                        filename = chunk.get('filename', 'Document')
                        text = chunk.get('text', '')[:500]
                        chunk_texts.append(f"[{filename}]: {text}")
                        document_sources.append(filename)
                    
                    synthesis_prompt = f"""Berdasarkan hasil analisis data dan konteks dokumen berikut, berikan penjelasan yang koheren.

Pertanyaan pengguna: {original_question}

Hasil analisis data:
{result.response[:500] if result.response else 'Tidak ada hasil analisis.'}

Konteks dokumen yang relevan:
{chr(10).join(chunk_texts)}

Instruksi:
1. Jika konteks dokumen BERKAITAN dengan analisis data, jelaskan hubungannya secara ringkas
2. Jika konteks dokumen BERBEDA/TIDAK BERKAITAN, nyatakan dengan jelas:
   - "Analisis data menunjukkan: [ringkasan]"
   - "Sementara itu, dokumen menunjukkan: [ringkasan]"
3. Berikan penjelasan singkat dan padat (maksimal 4-5 kalimat)
4. Sebutkan nama dokumen sumber

Jawaban (dalam Bahasa Indonesia):"""

                    def _run_synthesis():
                        return gemini_client.models.generate_content(
                            model=doc_settings.gemini_llm_model,
                            contents=[synthesis_prompt]
                        )
                    synthesis_response = await run_in_threadpool(_run_synthesis)
                    
                    if synthesis_response.text:
                        doc_context = f"\n\n---\n📄 **Konteks Dokumen:**\n{synthesis_response.text.strip()}"
                        enhanced_response += doc_context
                        
                except Exception as synth_err:
                    print(f"[DEBUG] Document synthesis failed: {synth_err}")
                    # Fallback to simple list of sources
                    doc_context = f"\n\n---\n📄 **Dokumen terkait:** {', '.join(document_sources)}"
                    enhanced_response += doc_context
            
            final_data = {
                'type': 'result',
                'response': enhanced_response,
                'code': result.code,
                'explanation': combined_explanation or None,
                'ui_components': result.ui_components,
                'has_error': result.has_error,
                'document_sources': document_sources if document_sources else None
            }
            final_result_obj = result # Capture for saving
            yield f"data: {json.dumps(final_data, default=str)}\n\n"
            
            # Done signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            error_msg = str(e)
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
            # Save Error
            chat_service.add_message(
                chat_id=request.chat_id,
                role="assistant",
                content=f"Error: {error_msg}",
                metadata={"has_error": True}
            )
            return

        # Save Assistant Message (if successful)
        if final_result_obj and successful_table:
            chat_service.add_message(
                chat_id=request.chat_id,
                role="assistant",
                content=final_result_obj.response or "",
                metadata={
                    "code": final_result_obj.code,
                    "explanation": final_result_obj.explanation,
                    "ui_components": final_result_obj.ui_components,
                    "has_error": final_result_obj.has_error,
                    "last_used_table": successful_table.get("cache_path"),
                    "last_used_table_name": successful_table.get("display_name")
                }
            )
    
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


# =============================================================================
# OneDrive Routes
# =============================================================================

@router.get("/api/onedrive/status")
async def onedrive_status(current_user: dict = Depends(get_current_user)):
    """Check OneDrive configuration status."""
    is_ok, error_msg = onedrive_config.is_configured()
    return {
        "configured": is_ok,
        "error": error_msg if not is_ok else None,
        "root_path": onedrive_config.ONEDRIVE_ROOT_PATH if is_ok else None
    }


@router.get("/api/onedrive/files")
async def list_onedrive_files(
    subfolder: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List files from OneDrive. If subfolder is specified, list files in that subfolder only."""
    is_ok, error_msg = onedrive_config.is_configured()
    if not is_ok:
        raise HTTPException(status_code=400, detail=f"OneDrive not configured: {error_msg}")
    
    try:
        token = onedrive_client.get_access_token()
        if subfolder:
            files = onedrive_client.list_files_in_subfolder(token, subfolder)
        else:
            files = onedrive_client.list_files(token)
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/onedrive/subfolders")
async def list_onedrive_subfolders(current_user: dict = Depends(get_current_user)):
    """List immediate subfolders in OneDrive root path."""
    is_ok, error_msg = onedrive_config.is_configured()
    if not is_ok:
        raise HTTPException(status_code=400, detail=f"OneDrive not configured: {error_msg}")
    
    try:
        token = onedrive_client.get_access_token()
        subfolders = onedrive_client.list_subfolders(token)
        return subfolders
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class OneDriveUploadRequest(BaseModel):
    table_id: str
    subfolder: str
    filename: Optional[str] = None


@router.post("/api/onedrive/upload", status_code=202)
async def upload_to_onedrive(
    request: OneDriveUploadRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Upload a cached table to OneDrive.
    Returns 202 Accepted with a job ID.
    """
    # Define the heavy blocking function
    def _do_upload(table_id, filename, subfolder):
        cache_path = Path(table_id)
        if not cache_path.exists():
            raise Exception("Table not found")
            
        df = pd.read_parquet(cache_path)
        
        # Determine filename
        if filename:
            final_name = filename
            if not final_name.endswith('.xlsx'):
                final_name += '.xlsx'
        else:
            final_name = cache_path.stem + '.xlsx'
            
        # Write temp file and upload
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            df.to_excel(tmp.name, index=False)
            tmp_path = Path(tmp.name)
            
        try:
            result = onedrive_client.upload_file(tmp_path, final_name, subfolder)
            return {
                "success": True,
                "message": f"File '{final_name}' uploaded to {subfolder}",
                "web_url": result.get("webUrl")
            }
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    # Submit to job manager
    # Submit to job manager
    job_id = job_manager.submit_job(
        _do_upload, 
        current_user["id"],
        "onedrive_upload",
        request.table_id, 
        request.filename, 
        request.subfolder
    )
    
    return {"job_id": job_id, "message": "Upload started"}


@router.post("/api/onedrive/sheets")
async def get_onedrive_sheets(
    file_info: dict,
    current_user: dict = Depends(get_current_user)
):
    """Get sheet names from an OneDrive Excel file."""
    try:
        download_url = file_info.get("downloadUrl")
        file_id = file_info.get("fileId")
        
        # Refresh download URL if file_id is provided
        if file_id:
            print(f"[GetSheets] Refreshing download URL for file_id: {file_id}")
            token = onedrive_client.get_access_token()
            file_details = onedrive_client.get_file_details(token, file_id)
            fresh_url = file_details.get("@microsoft.graph.downloadUrl")
            if fresh_url:
                download_url = fresh_url
                print(f"[GetSheets] Got fresh download URL")
        
        if not download_url:
            raise HTTPException(status_code=400, detail="No download URL available. Please refresh the file list.")
        
        if not download_url:
            raise HTTPException(status_code=400, detail="No download URL available. Please refresh the file list.")
        
        file_bytes = await run_in_threadpool(onedrive_client.download_file, download_url)
        sheets = onedrive_client.get_excel_sheets(file_bytes)
        return {"sheets": sheets}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Request/Response models for load-sheet
class LoadSheetRequest(BaseModel):
    download_url: Optional[str] = None  # May be expired, optional
    file_id: Optional[str] = None       # Used to get fresh download URL
    filename: str
    sheet_name: Optional[str] = None
    display_name: str


class LoadSheetResponse(BaseModel):
    cache_path: str
    n_rows: int
    n_cols: int
    message: str


@router.post("/api/onedrive/load-sheet", response_model=LoadSheetResponse)
async def load_onedrive_sheet(
    request: LoadSheetRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Download a file from OneDrive, read the specified sheet, and cache as parquet.
    
    This is the main endpoint for loading data from OneDrive into the system.
    Supports both CSV and Excel files.
    """
    filename_lower = request.filename.lower()
    
    # Validate file type
    if not filename_lower.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Only CSV and Excel files are supported."
        )
    
    try:
        # Get fresh download URL if file_id is provided (recommended)
        download_url = request.download_url
        if request.file_id:
            print(f"[LoadSheet] Refreshing download URL for file_id: {request.file_id}")
            token = onedrive_client.get_access_token()
            try:
                file_details = onedrive_client.get_file_details(token, request.file_id)
                fresh_url = file_details.get("@microsoft.graph.downloadUrl")
                if fresh_url:
                    download_url = fresh_url
                    print(f"[LoadSheet] Got fresh download URL")
                else:
                    print(f"[LoadSheet] WARNING: No downloadUrl in file_details, using original")
            except Exception as e:
                print(f"[LoadSheet] Failed to get file details: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to refresh download URL: {str(e)}")
        
        if not download_url:
            raise HTTPException(status_code=400, detail="No download URL available. Please refresh the file list.")
        
        # Download file from OneDrive
        print(f"[LoadSheet] Downloading file from OneDrive...")
        # Download file from OneDrive
        print(f"[LoadSheet] Downloading file from OneDrive...")
        file_bytes = await run_in_threadpool(onedrive_client.download_file, download_url)
        print(f"[LoadSheet] Downloaded {len(file_bytes)} bytes")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LoadSheet] Download failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")
    
    try:
        # For Excel files, validate sheet exists
        if filename_lower.endswith((".xlsx", ".xls")):
            available_sheets = onedrive_client.get_excel_sheets(file_bytes)
            if request.sheet_name and request.sheet_name not in available_sheets:
                raise HTTPException(
                    status_code=400,
                    detail=f"Sheet '{request.sheet_name}' not found. Available sheets: {available_sheets}"
                )
        
        # Read file to DataFrame (offload heavy pandas read)
        df = await run_in_threadpool(
            onedrive_client.read_file_to_df,
            file_bytes, 
            request.filename, 
            sheet_name=request.sheet_name
        )
        
        # Cache as parquet (offload heavy write)
        cache_path, n_rows, n_cols = await run_in_threadpool(
            build_parquet_cache_from_df,
            df=df,
            display_name=request.display_name,
            original_file=request.filename,
            sheet_name=request.sheet_name,
            source_metadata={
                "source": "onedrive",
                "downloadUrl": request.download_url
            },
            temporary=True
        )
        
        return LoadSheetResponse(
            cache_path=str(cache_path),
            n_rows=n_rows,
            n_cols=n_cols,
            message=f"Sheet '{request.display_name}' successfully loaded and cached"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# File Upload Routes
# =============================================================================

@router.post("/api/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a file for processing."""
    # Ensure upload directory exists
    upload_dir = settings.upload_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file
    filename = file.filename or "unknown"
    if not filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Unsupported file type")
        
    file_path = upload_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
    
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
            
        # Build parquet cache (offload heavy processing)
        cache_path, n_rows, n_cols = await run_in_threadpool(
            build_parquet_cache,
            path=file_path,
            display_name=filename,
            source_metadata={"source": "upload", "original_name": filename}
        )
        
        return {
            "filename": filename,
            "size": len(content),
            "message": "File uploaded successfully",
            "cache_path": str(cache_path),
            "n_rows": n_rows,
            "n_cols": n_cols
        }
    except Exception as e:
        # cleanup
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/files/append", status_code=202)
async def append_to_table(
    request: AppendRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Append data from one table to another.
    Returns 202 Accepted with a job ID.
    """
    def _do_append(source_id, target_id, description):
        source_path = Path(source_id)
        target_path = Path(target_id)
        
        if not source_path.exists() or not target_path.exists():
            raise Exception("Table not found")
            
        source_df = pd.read_parquet(source_path)
        
        total_rows, rows_added, error_msg = append_to_parquet_cache(
            cache_path=target_path,
            new_df=source_df,
            description=description or "Data appended"
        )
        
        if error_msg:
            raise Exception(error_msg)
            
        return {
            "cache_path": str(target_path),
            "total_rows": total_rows,
            "rows_added": rows_added,
            "message": f"Successfully appended {rows_added} rows."
        }

    job_id = job_manager.submit_job(
        _do_append,
        current_user["id"],
        "append",
        request.source_table_id,
        request.target_table_id,
        request.description
    )
    
    return {"job_id": job_id, "message": "Append started"}


@router.post("/api/files/append/validate", response_model=AppendValidateResponse)
async def validate_append(
    request: AppendValidateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Validate if source data can be appended to target table.
    Uses LLM to check structure similarity if columns don't match.
    """
    try:
        target_path = Path(request.target_table_id)
        source_path = Path(request.source_table_id)
        
        if not target_path.exists():
            raise HTTPException(status_code=404, detail="Target table not found")
        if not source_path.exists():
            raise HTTPException(status_code=404, detail="Source table not found")
        
        # Get target table info
        target_info = get_target_table_info(target_path)
        target_columns = target_info["columns"]
        
        # Read source to get columns (offload)
        source_df = await run_in_threadpool(pd.read_parquet, source_path)
        source_columns = list(source_df.columns)
        
        # Check if columns already match
        columns_match = set(target_columns) == set(source_columns)
        
        if columns_match:
            return AppendValidateResponse(
                columns_match=True,
                compatible=True,
                issues=[],
                target_has_transform=bool(target_info["transform_code"]),
                transform_explanation=target_info["transform_explanation"],
                similarity_reason="Columns already match, no transformation needed.",
                target_columns=target_columns,
                source_columns=source_columns
            )
        
        # Columns don't match - check if target has transform
        has_transform = bool(target_info["transform_code"])
        
        # Generate issues list
        issues = []
        target_set = set(target_columns)
        source_set = set(source_columns)
        missing_in_source = target_set - source_set
        extra_in_source = source_set - target_set
        
        if missing_in_source:
            issues.append(f"Missing in source: {', '.join(sorted(missing_in_source))}")
        if extra_in_source:
            issues.append(f"Extra in source: {', '.join(sorted(extra_in_source))}")
        
        # Use LLM to check structure similarity
        similarity_reason = None
        compatible = False
        
        if has_transform:
            from openai import OpenAI
            app_settings = AppSettings()
            
            if app_settings.openai_api_key:
                try:
                    client = OpenAI(api_key=app_settings.openai_api_key)
                    source_sample = source_df.head(5).to_string()
                    
                    prompt = f"""Analisis apakah data baru ini bisa ditransformasi menggunakan logika yang sama dengan tabel target.

INFO TABEL TARGET:
- Penjelasan transformasi: {target_info['transform_explanation'] or 'Tidak ada penjelasan tersimpan'}
- Kolom akhir setelah transformasi: {target_columns}
- File asli: {target_info['original_file']}

DATA SUMBER BARU (sampel):
Kolom: {source_columns}
{source_sample}

PERTANYAAN: Apakah struktur data sumber ini mirip dengan apa yang dirancang untuk transformasi asli?
Jawab dengan "YES" atau "NO" diikuti penjelasan singkat (1-2 kalimat dalam Bahasa Indonesia)."""

                    def _run_llm_check():
                        return client.responses.create(
                            model=app_settings.default_llm_model,
                            input=prompt,
                        )

                    response = await run_in_threadpool(_run_llm_check)
                    
                    answer = response.output_text.strip() if response.output_text else ""
                    compatible = answer.upper().startswith("YES")
                    similarity_reason = answer
                    
                except Exception as e:
                    similarity_reason = f"Could not assess compatibility: {str(e)}"
                    compatible = False
            else:
                similarity_reason = "No API key configured for structure analysis."
                compatible = False
        else:
            similarity_reason = "Target table has no stored transform. Cannot auto-transform source data."
            compatible = False
        
        return AppendValidateResponse(
            columns_match=False,
            compatible=compatible,
            issues=issues,
            target_has_transform=has_transform,
            transform_explanation=target_info["transform_explanation"],
            similarity_reason=similarity_reason,
            target_columns=target_columns,
            source_columns=source_columns
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/files/append/preview-transform", status_code=202)
async def preview_append_transform(
    request: AppendPreviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Apply stored transform to source data and return preview.
    If user_feedback is provided, uses LLM to adjust the transform.
    Returns 202 Accepted with a job ID.
    """
    def _do_preview_transform(source_table_id, target_table_id, user_feedback):
        """Background job to preview transform."""
        try:
            target_path = Path(target_table_id)
            source_path = Path(source_table_id)
            
            if not target_path.exists():
                return {"success": False, "error": "Target table not found"}
            if not source_path.exists():
                return {"success": False, "error": "Source table not found"}
            
            # Get stored transform
            target_info = get_target_table_info(target_path)
            transform_code = target_info["transform_code"]
            
            if not transform_code:
                return {
                    "success": False,
                    "preview_data": [],
                    "preview_columns": [],
                    "error": "Target table has no stored transform code."
                }
            
            # Read source data
            source_df = pd.read_parquet(source_path)
            
            # If user provided feedback, regenerate the transform
            if user_feedback:
                result = regenerate_with_feedback(
                    df=source_df,
                    previous_code=transform_code,
                    user_feedback=user_feedback,
                    filename=str(source_path.name)
                )
                
                if result.has_error:
                    return {
                        "success": False,
                        "preview_data": [],
                        "preview_columns": [],
                        "error": f"Failed to adjust transform: {result.explanation}"
                    }
                
                transform_code = result.transform_code
            
            # Apply transform
            transformed_df, error = apply_stored_transform(
                source_df=source_df,
                transform_code=transform_code,
                preview_only=True,
                max_preview_rows=100
            )
            
            if error:
                return {
                    "success": False,
                    "preview_data": [],
                    "preview_columns": [],
                    "error": error
                }
            
            # Validate that transformed columns match target
            target_columns = set(target_info["columns"])
            transformed_columns = set(transformed_df.columns)
            
            if target_columns != transformed_columns:
                missing = target_columns - transformed_columns
                extra = transformed_columns - target_columns
                issue_parts = []
                if missing:
                    issue_parts.append(f"Missing: {', '.join(sorted(missing))}")
                if extra:
                    issue_parts.append(f"Extra: {', '.join(sorted(extra))}")
                
                return {
                    "success": False,
                    "preview_data": [],
                    "preview_columns": list(transformed_df.columns),
                    "error": f"Transform output doesn't match target schema. {'; '.join(issue_parts)}"
                }
            
            # Success!
            preview_data = transformed_df.head(20).fillna("").to_dict(orient="records")
            
            return {
                "success": True,
                "preview_data": preview_data,
                "preview_columns": list(transformed_df.columns),
                "error": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "preview_data": [],
                "preview_columns": [],
                "error": f"Preview transform failed: {str(e)}"
            }
    
    # Submit to job manager
    job_id = job_manager.submit_job(
        _do_preview_transform,
        current_user["id"],
        "preview_transform",
        request.source_table_id,
        request.target_table_id,
        request.user_feedback
    )
    
    return {"job_id": job_id, "message": "Preview transform started"}


@router.post("/api/files/append/confirm-transform", status_code=202)
async def confirm_append_transform(
    request: AppendConfirmRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Execute transform and append.
    Returns 202 Accepted with a job ID.
    """
    def _do_confirm_append(source_id, target_id, description, code):
        source_path = Path(source_id)
        target_path = Path(target_id)
        
        if not source_path.exists() or not target_path.exists():
            raise Exception("Table not found")
            
        # Get stored transform if not provided
        transform_code = code
        if not transform_code:
            target_info = get_target_table_info(target_path)
            transform_code = target_info.get("transform_code")
            
        if not transform_code:
            raise Exception("Target table has no stored transform code.")
            
        source_df = pd.read_parquet(source_path)
        
        transformed_df, error = apply_stored_transform(
            source_df=source_df,
            transform_code=transform_code,
            preview_only=False
        )
        
        if error:
            raise Exception(f"Transformation failed: {error}")
            
        total_rows, rows_added, append_error = append_to_parquet_cache(
            cache_path=target_path,
            new_df=transformed_df,
            description=description or "Data appended via transform",
            transform_code=transform_code if code else None,
            transform_explanation="User generated transform" if code else None
        )
        
        if append_error:
            raise Exception(append_error)
            
        return {
            "cache_path": str(target_path),
            "total_rows": total_rows,
            "rows_added": rows_added,
            "message": f"Successfully appended {rows_added} transformed rows."
        }

    job_id = job_manager.submit_job(
        _do_confirm_append,
        current_user["id"],
        "append",
        request.source_table_id,
        request.target_table_id,
        request.description,
        request.transform_code
    )
    
    return {"job_id": job_id, "message": "Append with transform started"}


@router.post("/api/files/append/generate-transform", status_code=202)
async def generate_append_transform(
    request: AppendGenerateTransformRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate a NEW transform that maps source data to target table's column structure.
    Uses LLM to analyze source data and create transformation code to match target schema.
    Returns 202 Accepted with a job ID.
    """
    def _do_generate_transform(source_table_id, target_table_id, user_description):
        """Background job to generate transform."""
        try:
            target_path = Path(target_table_id)
            source_path = Path(source_table_id)
            
            if not target_path.exists():
                return {"success": False, "error": "Target table not found"}
            if not source_path.exists():
                return {"success": False, "error": "Source table not found"}
            
            # Get target table info
            target_info = get_target_table_info(target_path)
            target_columns = target_info["columns"]
            
            # Read source data for analysis
            source_df = pd.read_parquet(source_path)
            source_sample = source_df.head(10).to_string()
            source_columns = list(source_df.columns)
            
            # Generate transform using LLM
            app_settings = AppSettings()
            
            if not app_settings.openai_api_key:
                return {
                    "success": False,
                    "preview_data": [],
                    "preview_columns": [],
                    "error": "No API key configured for transform generation."
                }
            
            from openai import OpenAI
            client = OpenAI(api_key=app_settings.openai_api_key)
            
            prompt = f"""Generate Python pandas code to transform source data to match target table schema.

TARGET TABLE SCHEMA (the columns we need to produce):
{target_columns}

SOURCE DATA SAMPLE:
Columns: {source_columns}
{source_sample}

USER GUIDANCE:
{user_description or 'No specific guidance provided. Please infer column mappings.'}

REQUIREMENTS:
1. Input DataFrame is named `df`
2. Output DataFrame must be named `normalized_df`
3. Output MUST have EXACTLY these columns: {target_columns}
4. Map source columns to target columns based on content, names, or user guidance
5. If a target column cannot be mapped, fill with empty string or appropriate default
6. Handle data type conversions as needed
7. Do NOT use inplace=True
8. Return ONLY valid Python code, no explanations

Generate the Python code:"""

            response = client.responses.create(
                model=app_settings.default_llm_model,
                input=prompt,
            )
            
            if not response.output_text:
                return {
                    "success": False,
                    "preview_data": [],
                    "preview_columns": [],
                    "error": "LLM returned empty response"
                }
            
            # Extract code from response
            transform_code = response.output_text.strip()
            
            # Clean up code if wrapped in markdown
            if "```python" in transform_code:
                transform_code = transform_code.split("```python")[1].split("```")[0].strip()
            elif "```" in transform_code:
                transform_code = transform_code.split("```")[1].split("```")[0].strip()
            
            # Apply the generated transform
            transformed_df, error = apply_stored_transform(
                source_df=source_df,
                transform_code=transform_code,
                preview_only=True,
                max_preview_rows=100
            )
            
            if error:
                return {
                    "success": False,
                    "preview_data": [],
                    "preview_columns": [],
                    "error": f"Generated transform failed: {error}\n\nCode:\n{transform_code[:500]}..."
                }
            
            # Validate columns match
            if set(transformed_df.columns) != set(target_columns):
                missing = set(target_columns) - set(transformed_df.columns)
                extra = set(transformed_df.columns) - set(target_columns)
                issue_parts = []
                if missing:
                    issue_parts.append(f"Missing: {', '.join(sorted(missing))}")
                if extra:
                    issue_parts.append(f"Extra: {', '.join(sorted(extra))}")
                
                return {
                    "success": False,
                    "preview_data": [],
                    "preview_columns": list(transformed_df.columns),
                    "error": f"Generated transform doesn't produce correct schema. {'; '.join(issue_parts)}"
                }
            
            # Success!
            preview_data = transformed_df.head(20).fillna("").to_dict(orient="records")
            
            return {
                "success": True,
                "preview_data": preview_data,
                "preview_columns": list(transformed_df.columns),
                "error": None,
                "generated_code": transform_code
            }
            
        except Exception as e:
            return {
                "success": False,
                "preview_data": [],
                "preview_columns": [],
                "error": f"Transform generation failed: {str(e)}"
            }
    
    # Submit to job manager
    job_id = job_manager.submit_job(
        _do_generate_transform,
        current_user["id"],
        "generate_transform",
        request.source_table_id,
        request.target_table_id,
        request.user_description
    )
    
    return {"job_id": job_id, "message": "Transform generation started"}



@router.post("/api/files/analyze", status_code=202)
async def analyze_file(
    request: AnalyzeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze values in a background job.
    Returns 202 with job_id.
    """
    logger.info(f"Analyze request received with metadata: {request.metadata}")
    def _do_analyze(table_id, user_desc):
        cache_path = Path(table_id)
        if not cache_path.exists():
            raise Exception("Table not found")
        
        # Read full dataframe (sync execution in thread)
        df = pd.read_parquet(cache_path)
        
        # Call AI Analyzer
        # Since we are already in a thread (job executor), we can call sync functions
        # But analyze_and_generate_transform is async? No, let's check.
        # It's imported from app.data_analyzer.
        
        # Wait, analyze_and_generate_transform might be async definition?
        # If it is async, we can't call it easily from ThreadPoolExecutor without new loop.
        # Let's verify app/data_analyzer.py... I haven't read it.
        # Assuming it is sync or I need to handle it.
        
        # Actually I can just check if I can see it?
        # I'll blindly attempt to run it synchronously. 
        # If it returns a coroutine, I messed up.
        # Most of my "AI" calls use run_in_threadpool which implies the underlying functions are sync (blocking I/O).
        # Yes, PandasAIClient puts requests to OpenAI which are sync by default unless AsyncOpenAI is used.
        # app/qa_engine.py showed OpenAI(api_key=...) which is synchronous client.
        
        from app.data_analyzer import analyze_and_generate_transform
        
        # run_in_threadpool in the original code suggested it was blocking.
        # So I can just call it directly here.
        
        result = analyze_and_generate_transform(
            df=df,
            filename=str(cache_path.name),
            user_description=user_desc
        )
        
        # Serialize response
        preview_data = []
        preview_columns = []
        transformed_preview_id = None
        
        if result.preview_df is not None and not result.preview_df.empty:
            preview_data = result.preview_df.fillna("").to_dict(orient="records")
            preview_columns = list(result.preview_df.columns)
            
            # Save transformed preview to a temp parquet for state recovery
            import hashlib
            import tempfile
            cache_hash = hashlib.md5(f"{table_id}_transformed".encode()).hexdigest()[:12]
            transformed_cache_path = Path(tempfile.gettempdir()) / f"transformed_{cache_hash}.parquet"
            result.preview_df.to_parquet(transformed_cache_path, index=False)
            transformed_preview_id = str(transformed_cache_path)
            logger.info(f"Saved transformed preview to: {transformed_preview_id}")
            
        return {
            "summary": result.summary,
            "issues_found": result.issues_found,
            "transform_code": result.transform_code,
            "needs_transform": result.needs_transform,
            "validation_notes": result.validation_notes,
            "explanation": result.explanation,
            "preview_data": preview_data,
            "preview_columns": preview_columns,
            "transformed_preview_id": transformed_preview_id,
            "has_error": result.has_error
        }

    # Build metadata for recovery
    job_metadata = request.metadata or {}
    if "displayName" not in job_metadata:
        job_metadata["displayName"] = Path(request.table_id).stem
    job_metadata["previewTableId"] = request.table_id

    job_id = job_manager.submit_job(
        _do_analyze,
        current_user["id"],
        "analyze",
        request.table_id,
        request.user_description,
        metadata=job_metadata
    )
    
    return {"job_id": job_id, "message": "Analysis started"}


@router.post("/api/files/transform/preview", status_code=202)
async def preview_transform(
    request: TransformRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Execute transformation code and return preview without saving.
    Returns 202 Accepted with a job ID.
    """
    def _do_transform_preview(table_id, transform_code):
        """Background job to preview transform."""
        try:
            cache_path = Path(table_id)
            if not cache_path.exists():
                return {
                    "preview_data": [],
                    "columns": [],
                    "total_rows": 0,
                    "error": "Table not found"
                }
            
            df = pd.read_parquet(cache_path)
            
            # Execute transform
            transformed_df, error = execute_transform(df, transform_code)
            
            if error:
                return {
                    "preview_data": [],
                    "columns": [],
                    "total_rows": 0,
                    "error": error
                }
                
            # Success
            preview_df = transformed_df.head(20).fillna("")
            
            return {
                "preview_data": preview_df.to_dict(orient="records"),
                "columns": list(transformed_df.columns),
                "total_rows": len(transformed_df),
                "error": None
            }
            
        except Exception as e:
            return {
                "preview_data": [],
                "columns": [],
                "total_rows": 0,
                "error": f"Transform preview failed: {str(e)}"
            }
    
    # Submit to job manager
    job_id = job_manager.submit_job(
        _do_transform_preview,
        current_user["id"],
        "transform_preview",
        request.table_id,
        request.transform_code
    )
    
    return {"job_id": job_id, "message": "Transform preview started"}


@router.post("/api/files/transform/confirm", status_code=202)
async def confirm_transform(
    request: TransformRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Confirm and apply a transformation properly.
    Returns 202 Accepted with a job ID.
    """
    def _do_confirm_transform(table_id, code, display_name, replace_original, parent_id):
        cache_path = Path(table_id)
        if not cache_path.exists():
            raise Exception("Table not found")
            
        df = pd.read_parquet(cache_path)
        transformed_df, error = execute_transform(df, code)
        
        if error:
            raise Exception(f"Transformation failed: {error}")
            
        if replace_original:
            n_rows, n_cols = update_existing_parquet_cache(
                cache_path=cache_path,
                df=transformed_df,
                transform_code=code,
                display_name=display_name
            )
            final_path = cache_path
            msg = "Table updated successfully"
        else:
            original_name = cache_path.stem.split('_', 1)[-1]  # naïve approach
            final_display_name = display_name or f"{original_name} (Cleaned)"
            
            new_cache_path, n_rows, n_cols = build_parquet_cache_from_df(
                df=transformed_df,
                display_name=final_display_name,
                original_file=str(cache_path),
                source_metadata={
                    "source": "transform",
                    "parent_table_id": parent_id,
                },
                transform_code=code
            )
            final_path = new_cache_path
            msg = "New table created successfully"
            
        return {
            "cache_path": str(final_path),
            "n_rows": n_rows,
            "n_cols": n_cols,
            "message": msg
        }

    job_id = job_manager.submit_job(
        _do_confirm_transform,
        current_user["id"],
        "transform",
        request.table_id,
        request.transform_code,
        request.display_name,
        request.replace_original,
        request.table_id
    )
    
    return {"job_id": job_id, "message": "Transformation started"}




class RefineRequest(BaseModel):
    table_id: str
    transform_code: str
    feedback: str


@router.post("/api/files/transform/refine")
async def refine_transform(
    request: RefineRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Refine transformation code based on user feedback.
    """
    """
    Refine transformation code based on user feedback.
    """
    def _do_refine_transform(table_id, transform_code, feedback):
        cache_path = Path(table_id)
        if not cache_path.exists():
            raise Exception("Table not found")
        
        df = pd.read_parquet(cache_path)
        
        # Call AI to regenerate
        result = regenerate_with_feedback(
            df=df,
            previous_code=transform_code,
            user_feedback=feedback,
            filename=str(cache_path.name)
        )
        
        # Preview data if available
        preview_data = []
        preview_columns = []
        if result.preview_df is not None:
            preview_data = result.preview_df.fillna("").to_dict(orient="records")
            preview_columns = list(result.preview_df.columns)
            
        return {
            "summary": result.summary,
            "issues_found": result.issues_found,
            "transform_code": result.transform_code,
            "needs_transform": result.needs_transform,
            "validation_notes": result.validation_notes,
            "explanation": result.explanation,
            "preview_data": preview_data,
            "preview_columns": preview_columns,
            "has_error": result.has_error
        }

    job_id = job_manager.submit_job(
        _do_refine_transform,
        current_user["id"],
        "refine",
        request.table_id,
        request.transform_code,
        request.feedback,
        metadata={
            "displayName": f"Refine: {request.feedback[:30]}...",
            "feedback": request.feedback
        }
    )
    
    return {"job_id": job_id, "message": "Refinement job started"}


# =============================================================================
# Document Context Retrieval Routes
# =============================================================================

class DocumentSearchRequest(BaseModel):
    query: str
    limit: int = 5


class DocumentSearchResult(BaseModel):
    id: Any
    score: float
    text: str
    filename: str
    doc_id: str
    chunk_index: int
    path: str
    web_url: str


class DocumentSearchResponse(BaseModel):
    results: List[DocumentSearchResult]
    query: str
    total_results: int


@router.post("/api/documents/ingest/dry-run")
async def documents_ingest_dry_run(
    current_user: dict = Depends(get_current_user)
):
    """
    Dry run: Discover documents in DOCUMENT_ROOT_PATH without ingesting.
    Returns list of files that would be processed.
    """
    from app.document_ingestion import ingest_all_documents
    
    try:
        result = ingest_all_documents(dry_run=True)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/documents/ingest", status_code=202)
async def documents_ingest_all(
    skip_existing: bool = True,
    current_user: dict = Depends(get_current_admin)
):
    """
    Trigger full document ingestion background job.
    Returns 202 Accepted with a job ID.
    """
    from app.document_ingestion import ingest_all_documents
    
    def _do_ingest(skip):
        return ingest_all_documents(dry_run=False, skip_existing=skip)

    job_id = job_manager.submit_job(_do_ingest, current_user["id"], "ingest", skip_existing)
    return {"job_id": job_id, "message": "Document ingestion started"}

@router.post("/api/documents/ingest/dry-run", status_code=202)
async def documents_ingest_dry_run(current_user: dict = Depends(get_current_admin)):
    """Dry run ingestion in background."""
    from app.document_ingestion import ingest_all_documents
    
    def _do_dry_run():
        return ingest_all_documents(dry_run=True)
        
    job_id = job_manager.submit_job(_do_dry_run, current_user["id"], "ingest_dry_run")
    return {"job_id": job_id, "message": "Dry run started"}

# Job Status Endpoint
@router.get("/api/jobs")
async def list_jobs(
    type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List all background jobs (visible to all users)."""
    jobs = job_manager.get_user_jobs(current_user["id"], job_type=type)
    
    # Enrich jobs with username for owner identification
    for job in jobs:
        job_user_id = job.get("user_id")
        if job_user_id:
            user = database.get_user_by_id(job_user_id)
            if user:
                job["user_username"] = user.get("username")
                job["user_email"] = user.get("email")
            else:
                job["user_username"] = f"User #{job_user_id}"
    
    return jobs

@router.get("/api/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get status of a background job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.delete("/api/jobs/{job_id}")
async def delete_job(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a specific job."""
    try:
        job_manager.delete_job(job_id, current_user["id"])
        return {"message": "Job deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/api/jobs/clear")
async def clear_jobs(
    period: str = "all",
    current_user: dict = Depends(get_current_user)
):
    """Clear jobs by period: hour, today, 3days, or all."""
    from datetime import datetime, timedelta
    
    now = datetime.now()
    if period == "hour":
        cutoff = now - timedelta(hours=1)
    elif period == "today":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "3days":
        cutoff = now - timedelta(days=3)
    else:
        cutoff = None  # Clear all
    
    count = job_manager.clear_user_jobs(current_user["id"], cutoff)
    return {"message": f"Cleared {count} jobs"}


@router.post("/api/documents/search", response_model=DocumentSearchResponse)
async def documents_search(
    request: DocumentSearchRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Search ingested documents using hybrid search (semantic + keyword).
    Returns relevant document chunks.
    """
    from app.qdrant_service import search_chunks
    
    try:
        results = search_chunks(request.query, limit=request.limit)
        
        return DocumentSearchResponse(
            results=[DocumentSearchResult(**r) for r in results],
            query=request.query,
            total_results=len(results)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/documents/status")
async def documents_status(
    current_user: dict = Depends(get_current_user)
):
    """
    Get document ingestion status: collection info and document count.
    """
    from app.document_ingestion import get_ingestion_status
    
    try:
        return get_ingestion_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/documents/clear")
async def documents_clear(
    current_user: dict = Depends(get_current_admin)  # Admin only
):
    """
    Clear all ingested documents from Qdrant collection.
    """
    from app.document_ingestion import clear_all_documents
    
    try:
        success = clear_all_documents()
        if success:
            return {"message": "All documents cleared successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear documents")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

