"""
API Routes for QIP Data Assistant.
Following exim-chat pattern with JWT authentication.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api import auth_utils, database, chat_service
from api.chat_utils import generate_chat_title
from api.intent_classifier import interpret_table_selection, generate_clarification_message, classify_user_intent
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
from app.settings import AppSettings

import pandas as pd
from pathlib import Path
import json

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
        cache_path = Path(table_id)
        if not cache_path.exists():
            raise HTTPException(status_code=404, detail="Table not found")
        
        df = pd.read_parquet(cache_path).head(rows)
        
        # Convert to JSON-serializable format
        return {
            "columns": list(df.columns),
            "data": df.fillna("").to_dict(orient="records"),
            "total_rows": len(df)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UpdateDescriptionRequest(BaseModel):
    description: Optional[str] = None
    column_descriptions: Optional[dict] = None


@router.patch("/api/tables/{table_id:path}")
async def update_table_description(
    table_id: str,
    request: UpdateDescriptionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update table description and column descriptions."""
    try:
        # Extract cache_id from cache_path (filename without extension)
        cache_path = Path(table_id)
        if not cache_path.exists():
            raise HTTPException(status_code=404, detail="Table not found")
        
        # Use the filename stem as cache_id
        cache_id = cache_path.stem
        
        # Update in catalog
        from app.data_store import DatasetCatalog
        catalog = DatasetCatalog()
        catalog.update_cached_sheet_metadata(
            cache_id=cache_id,
            description=request.description,
            column_descriptions=request.column_descriptions
        )
        
        return {"message": "Description updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/tables/{table_id:path}")
async def delete_table(
    table_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a cached table."""
    try:
        cache_path = Path(table_id)
        delete_cached_data(cache_path)
        return {"message": "Table deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tables/{table_id:path}/download")
async def download_table_csv(
    table_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Download a table as CSV file."""
    import io
    
    cache_path = Path(table_id)
    if not cache_path.exists():
        raise HTTPException(status_code=404, detail="Table not found")
    
    try:
        df = pd.read_parquet(cache_path)
        
        # Convert to CSV
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        # Get filename from cache path
        filename = cache_path.stem + ".csv"
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    api_key = settings.google_api_key
    if not api_key:
        raise HTTPException(status_code=500, detail="Google API Key not configured")

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
            ranked = chat_service.rank_tables_logic(request.question)
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
        
        df = pd.read_parquet(cache_path)
        client = PandasAIClient(api_key=api_key)
        
        result = client.ask(df, request.question)
        
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
    api_key = settings.google_api_key or settings.openai_api_key
    if not api_key:
        raise HTTPException(status_code=500, detail="No AI API Key configured")
        
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
            
            # Use LLM router to rank tables
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Analyzing question...'})}\n\n"
            router_rankings = route_question_to_tables(original_question)
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
            
            client = PandasAIClient(api_key=api_key)
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
                    df = pd.read_parquet(cache_path)
                    
                    attempt_result = client.ask(df, request.question, history=previous_history)
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
                # All tables failed - generate conversational clarification
                tried_names = [t.get('display_name', 'Unknown') for t in tables_to_try]
                all_tables = ranked if ranked else tables_to_try
                clarify_msg = generate_clarification_message(tried_names, all_tables, original_question)
                
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
            
            final_data = {
                'type': 'result',
                'response': result.response or "",
                'code': result.code,
                'explanation': combined_explanation or None,
                'ui_components': result.ui_components,
                'has_error': result.has_error
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
            
            # Auto-generate title for new chats
            if not previous_history and chat.get("title") == "New Chat":
                try:
                    generate_chat_title(
                        original_question,
                        final_result_obj.response or "Chat",
                        request.chat_id,
                        current_user["id"]
                    )
                except Exception as e:
                    print(f"Failed to auto-generate title: {e}")
    
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
async def list_onedrive_files(current_user: dict = Depends(get_current_user)):
    """List files from OneDrive."""
    is_ok, error_msg = onedrive_config.is_configured()
    if not is_ok:
        raise HTTPException(status_code=400, detail=f"OneDrive not configured: {error_msg}")
    
    try:
        token = onedrive_client.get_access_token()
        files = onedrive_client.list_files(token)
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        
        file_bytes = onedrive_client.download_file(download_url)
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
        file_bytes = onedrive_client.download_file(download_url)
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
        
        # Read file to DataFrame
        df = onedrive_client.read_file_to_df(
            file_bytes, 
            request.filename, 
            sheet_name=request.sheet_name
        )
        
        # Cache as parquet
        cache_path, n_rows, n_cols = build_parquet_cache_from_df(
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
            
        # Build parquet cache
        cache_path, n_rows, n_cols = build_parquet_cache(
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


@router.post("/api/files/append", response_model=AppendResponse)
async def append_to_table(
    request: AppendRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Append new data from an uploaded source table to an existing target table.
    
    This endpoint:
    1. Reads the source (new upload) and target tables
    2. Validates that column structures match exactly
    3. Appends the source data to target
    4. Returns natural language error if columns don't match
    """
    try:
        target_path = Path(request.target_table_id)
        source_path = Path(request.source_table_id)
        
        if not target_path.exists():
            raise HTTPException(status_code=404, detail="Target table not found")
        if not source_path.exists():
            raise HTTPException(status_code=404, detail="Source table not found")
        
        # Read source data
        source_df = pd.read_parquet(source_path)
        
        # Append to target
        total_rows, rows_added, error_msg = append_to_parquet_cache(
            cache_path=target_path,
            new_df=source_df,
            description=request.description or "Data appended"
        )
        
        if error_msg:
            # Return natural language error to user
            return AppendResponse(
                cache_path=str(target_path),
                total_rows=0,
                rows_added=0,
                message="Append failed",
                error=error_msg
            )
        
        # Success - optionally delete source temp file
        # source_path.unlink()  # Uncomment if you want to auto-delete
        
        return AppendResponse(
            cache_path=str(target_path),
            total_rows=total_rows,
            rows_added=rows_added,
            message=f"Successfully appended {rows_added} rows. Total rows: {total_rows}",
            error=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        
        # Read source to get columns
        source_df = pd.read_parquet(source_path)
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
                    
                    prompt = f"""Analyze if this new data can be transformed using the same logic as the target table.

TARGET TABLE INFO:
- Transform explanation: {target_info['transform_explanation'] or 'No explanation stored'}
- Final columns after transform: {target_columns}
- Original file: {target_info['original_file']}

NEW SOURCE DATA (sample):
Columns: {source_columns}
{source_sample}

QUESTION: Is this source data structurally similar to what the original transform was designed for?
Answer with "YES" or "NO" followed by a brief explanation (1-2 sentences)."""

                    response = client.responses.create(
                        model=app_settings.default_llm_model,
                        input=prompt,
                    )
                    
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


@router.post("/api/files/append/preview-transform", response_model=AppendPreviewResponse)
async def preview_append_transform(
    request: AppendPreviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Apply stored transform to source data and return preview.
    If user_feedback is provided, uses LLM to adjust the transform.
    """
    try:
        target_path = Path(request.target_table_id)
        source_path = Path(request.source_table_id)
        
        if not target_path.exists():
            raise HTTPException(status_code=404, detail="Target table not found")
        if not source_path.exists():
            raise HTTPException(status_code=404, detail="Source table not found")
        
        # Get stored transform
        target_info = get_target_table_info(target_path)
        transform_code = target_info["transform_code"]
        
        if not transform_code:
            return AppendPreviewResponse(
                success=False,
                preview_data=[],
                preview_columns=[],
                error="Target table has no stored transform code."
            )
        
        # Read source data
        source_df = pd.read_parquet(source_path)
        
        # If user provided feedback, regenerate the transform
        if request.user_feedback:
            result = regenerate_with_feedback(
                df=source_df,
                previous_code=transform_code,
                user_feedback=request.user_feedback,
                filename=str(source_path.name)
            )
            
            if result.has_error:
                return AppendPreviewResponse(
                    success=False,
                    preview_data=[],
                    preview_columns=[],
                    error=f"Failed to adjust transform: {result.explanation}"
                )
            
            transform_code = result.transform_code
        
        # Apply transform
        transformed_df, error = apply_stored_transform(
            source_df=source_df,
            transform_code=transform_code,
            preview_only=True,
            max_preview_rows=100
        )
        
        if error:
            return AppendPreviewResponse(
                success=False,
                preview_data=[],
                preview_columns=[],
                error=error
            )
        
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
            
            return AppendPreviewResponse(
                success=False,
                preview_data=[],
                preview_columns=list(transformed_df.columns),
                error=f"Transform output doesn't match target schema. {'; '.join(issue_parts)}"
            )
        
        # Success!
        preview_data = transformed_df.head(20).fillna("").to_dict(orient="records")
        
        return AppendPreviewResponse(
            success=True,
            preview_data=preview_data,
            preview_columns=list(transformed_df.columns),
            error=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/files/append/confirm-transform", response_model=AppendResponse)
async def confirm_append_transform(
    request: AppendConfirmRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Apply stored transform to full source data and append to target.
    """
    try:
        target_path = Path(request.target_table_id)
        source_path = Path(request.source_table_id)
        
        if not target_path.exists():
            raise HTTPException(status_code=404, detail="Target table not found")
        if not source_path.exists():
            raise HTTPException(status_code=404, detail="Source table not found")
        
        # Get transform code from request, or fallback to stored
        transform_code = request.transform_code
        if not transform_code:
            # Fallback to stored transform
            target_info = get_target_table_info(target_path)
            transform_code = target_info.get("transform_code")
        
        if not transform_code:
            return AppendResponse(
                cache_path=str(target_path),
                total_rows=0,
                rows_added=0,
                message="Append failed",
                error="Target table has no stored transform code."
            )
        
        # Read source data (full)
        source_df = pd.read_parquet(source_path)
        
        # Apply transform to full data
        transformed_df, error = apply_stored_transform(
            source_df=source_df,
            transform_code=transform_code,
            preview_only=False
        )
        
        if error:
            return AppendResponse(
                cache_path=str(target_path),
                total_rows=0,
                rows_added=0,
                message="Transform failed",
                error=error
            )
        
        # Now append transformed data
        total_rows, rows_added, append_error = append_to_parquet_cache(
            cache_path=target_path,
            new_df=transformed_df,
            description=request.description or "Data appended via transform",
            transform_code=transform_code if request.transform_code else None,
            transform_explanation="User generated transform" if request.transform_code else None
        )
        
        if append_error:
            return AppendResponse(
                cache_path=str(target_path),
                total_rows=0,
                rows_added=0,
                message="Append failed after transform",
                error=append_error
            )
        
        return AppendResponse(
            cache_path=str(target_path),
            total_rows=total_rows,
            rows_added=rows_added,
            message=f"Successfully transformed and appended {rows_added} rows. Total: {total_rows}",
            error=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/files/append/generate-transform", response_model=AppendPreviewResponse)
async def generate_append_transform(
    request: AppendGenerateTransformRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate a NEW transform that maps source data to target table's column structure.
    Uses LLM to analyze source data and create transformation code to match target schema.
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
        
        # Read source data for analysis
        source_df = pd.read_parquet(source_path)
        source_sample = source_df.head(10).to_string()
        source_columns = list(source_df.columns)
        
        # Generate transform using LLM
        app_settings = AppSettings()
        
        if not app_settings.openai_api_key:
            return AppendPreviewResponse(
                success=False,
                preview_data=[],
                preview_columns=[],
                error="No API key configured for transform generation."
            )
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=app_settings.openai_api_key)
            
            prompt = f"""Generate Python pandas code to transform source data to match target table schema.

TARGET TABLE SCHEMA (the columns we need to produce):
{target_columns}

SOURCE DATA SAMPLE:
Columns: {source_columns}
{source_sample}

USER GUIDANCE:
{request.user_description or 'No specific guidance provided. Please infer column mappings.'}

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
                return AppendPreviewResponse(
                    success=False,
                    preview_data=[],
                    preview_columns=[],
                    error="LLM returned empty response"
                )
            
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
                return AppendPreviewResponse(
                    success=False,
                    preview_data=[],
                    preview_columns=[],
                    error=f"Generated transform failed: {error}\n\nCode:\n{transform_code[:500]}..."
                )
            
            # Validate columns match
            if set(transformed_df.columns) != set(target_columns):
                missing = set(target_columns) - set(transformed_df.columns)
                extra = set(transformed_df.columns) - set(target_columns)
                issue_parts = []
                if missing:
                    issue_parts.append(f"Missing: {', '.join(sorted(missing))}")
                if extra:
                    issue_parts.append(f"Extra: {', '.join(sorted(extra))}")
                
                return AppendPreviewResponse(
                    success=False,
                    preview_data=[],
                    preview_columns=list(transformed_df.columns),
                    error=f"Generated transform doesn't produce correct schema. {'; '.join(issue_parts)}"
                )
            
            # Success!
            preview_data = transformed_df.head(20).fillna("").to_dict(orient="records")
            
            return AppendPreviewResponse(
                success=True,
                preview_data=preview_data,
                preview_columns=list(transformed_df.columns),
                error=None,
                generated_code=transform_code
            )
            
        except Exception as e:
            return AppendPreviewResponse(
                success=False,
                preview_data=[],
                preview_columns=[],
                error=f"Transform generation failed: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/files/analyze")
async def analyze_file(
    request: AnalyzeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze values in a cached table and generate transformation code.
    Reads from existing parquet cache.
    """
    try:
        cache_path = Path(request.table_id)
        if not cache_path.exists():
            raise HTTPException(status_code=404, detail="Table not found")
        
        # Read full dataframe for analysis (or sample if too large)
        # analyze_and_generate_transform handles sampling internally but needs a DF
        df = pd.read_parquet(cache_path)
        
        # Call AI Analyzer
        result = analyze_and_generate_transform(
            df=df,
            filename=str(cache_path.name),
            user_description=request.user_description
        )
        
        # Serialize response manually since Pydantic might not like numpy types
        # And we don't need to send the full DFs back, just preview
        preview_data = []
        if result.preview_df is not None:
            preview_data = result.preview_df.fillna("").to_dict(orient="records")
            
        return {
            "summary": result.summary,
            "issues_found": result.issues_found,
            "transform_code": result.transform_code,
            "needs_transform": result.needs_transform,
            "validation_notes": result.validation_notes,
            "explanation": result.explanation,
            "preview_data": preview_data,
            "has_error": result.has_error
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/files/transform/preview", response_model=TransformPreviewResponse)
async def preview_transform(
    request: TransformRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Execute transformation code and return preview without saving.
    """
    try:
        cache_path = Path(request.table_id)
        if not cache_path.exists():
            raise HTTPException(status_code=404, detail="Table not found")
        
        df = pd.read_parquet(cache_path)
        
        # Execute transform
        transformed_df, error = execute_transform(df, request.transform_code)
        
        if error:
            return TransformPreviewResponse(
                preview_data=[],
                columns=[],
                total_rows=0,
                error=error
            )
            
        # Success
        preview_df = transformed_df.head(20).fillna("")
        
        return TransformPreviewResponse(
            preview_data=preview_df.to_dict(orient="records"),
            columns=list(transformed_df.columns),
            total_rows=len(transformed_df)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/files/transform/confirm", response_model=TransformConfirmResponse)
async def confirm_transform(
    request: TransformRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Execute transformation and save.
    If replace_original=True, overwrites the existing parquet file.
    If replace_original=False (default), creates a new cached table.
    """
    try:
        cache_path = Path(request.table_id)
        if not cache_path.exists():
            raise HTTPException(status_code=404, detail="Table not found")
        
        df = pd.read_parquet(cache_path)
        
        # Execute transform (on full data)
        transformed_df, error = execute_transform(df, request.transform_code)
        
        if error:
            raise HTTPException(status_code=400, detail=f"Transformation failed: {error}")
        
        if request.replace_original:
            # REPLACE mode: Overwrite the existing parquet file
            n_rows, n_cols = update_existing_parquet_cache(
                cache_path=cache_path,
                df=transformed_df,
                transform_code=request.transform_code,
                display_name=request.display_name
            )
            
            return TransformConfirmResponse(
                cache_path=str(cache_path),
                n_rows=n_rows,
                n_cols=n_cols,
                message="Transformation applied and table updated successfully"
            )
        else:
            # CREATE NEW mode: Create a new cached table (original behavior)
            original_name = cache_path.stem.split('_', 1)[-1]  # naïve approach
            display_name = request.display_name or f"{original_name} (Cleaned)"
            
            new_cache_path, n_rows, n_cols = build_parquet_cache_from_df(
                df=transformed_df,
                display_name=display_name,
                original_file=str(cache_path),  # Trace lineage
                source_metadata={
                    "source": "transform",
                    "parent_table_id": request.table_id,
                    "transform_code": request.transform_code
                }
            )
            
            return TransformConfirmResponse(
                cache_path=str(new_cache_path),
                n_rows=n_rows,
                n_cols=n_cols,
                message="Transformation applied and saved as new table"
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




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
    try:
        cache_path = Path(request.table_id)
        if not cache_path.exists():
            raise HTTPException(status_code=404, detail="Table not found")
        
        df = pd.read_parquet(cache_path)
        
        # Call AI to regenerate
        result = regenerate_with_feedback(
            df=df,
            previous_code=request.transform_code,
            user_feedback=request.feedback,
            filename=str(cache_path.name)
        )
        
        # Preview data if available
        preview_data = []
        if result.preview_df is not None:
            preview_data = result.preview_df.fillna("").to_dict(orient="records")
            
        return {
            "summary": result.summary,
            "issues_found": result.issues_found,
            "transform_code": result.transform_code,
            "needs_transform": result.needs_transform,
            "validation_notes": result.validation_notes,
            "explanation": result.explanation,
            "preview_data": preview_data,
            "has_error": result.has_error
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
