from __future__ import annotations
import os
from google import genai
from api import chat_service

def init_gemini_client():
    """Initialize the Google GenAI client (v1 SDK)."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[GEMINI-CLIENT] ERROR: GOOGLE_API_KEY environment variable not set")
        return None
    
    try:
        # v1 SDK uses Client(api_key=...)
        client = genai.Client(api_key=api_key)
        print("[GEMINI-CLIENT] Successfully initialized Gemini client")
        return client
    except Exception as e:
        print(f"[GEMINI-CLIENT] ERROR: Failed to initialize client: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_chat_title(
    first_question: str, 
    first_answer: str, 
    chat_id: str, 
    user_id: int
) -> str:
    """
    Generate a short, relevant title for the chat session based on the first interaction.
    Updates the session title in the database.
    """
    try:
        client = init_gemini_client()
        if not client:
            return "New Chat"

        # v1 SDK: client.models.generate_content
        prompt = f"""
        Generate a very short, concise title (max 4-5 words) for a chat session that starts with:
        User: {first_question}
        AI: {first_answer}
        
        The title should summarize the user's intent. Do not use quotes.
        """
        
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        title = response.text.strip()
        
        # Clean up title
        title = title.replace('"', '').replace("'", "")
        if len(title) > 50:
            title = title[:47] + "..."
            
        # Update database
        chat_service.update_chat(chat_id, user_id, title)
        
        return title
        
    except Exception as e:
        print(f"Error generating chat title: {e}")
        return "New Chat"


def generate_chat_title_from_conversation(conversation_pairs: list) -> str:
    """
    Generate a short, relevant title based on the entire conversation summary.
    Does not update the database - only returns the generated title.
    
    Args:
        conversation_pairs: List of dicts with 'question' and 'answer' keys
    """
    try:
        print(f"[TITLE-GEN] Starting generation with {len(conversation_pairs)} conversation pairs")
        client = init_gemini_client()
        if not client:
            print("[TITLE-GEN] No Gemini client available")
            return "New Chat"

        # Build conversation summary
        conversation_text = ""
        for i, pair in enumerate(conversation_pairs[:3], 1):  # Max 3 pairs
            conversation_text += f"Q{i}: {pair['question'][:100]}\n"
            conversation_text += f"A{i}: {pair['answer'][:100]}\n"

        print(f"[TITLE-GEN] Conversation summary:\n{conversation_text[:200]}...")

        prompt = f"""
        Generate a very short, concise title (max 4-5 words) summarizing this conversation:
        
        {conversation_text}
        
        The title should capture the main topic or intent. Do not use quotes.
        """
        
        print("[TITLE-GEN] Calling Gemini API...")
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        title = response.text.strip()
        print(f"[TITLE-GEN] Raw title from API: '{title}'")
        
        # Clean up title
        title = title.replace('"', '').replace("'", "")
        if len(title) > 50:
            title = title[:47] + "..."
        
        print(f"[TITLE-GEN] Final cleaned title: '{title}'")
        return title
        
    except Exception as e:
        print(f"[TITLE-GEN ERROR] {e}")
        import traceback
        traceback.print_exc()
        return "New Chat"
