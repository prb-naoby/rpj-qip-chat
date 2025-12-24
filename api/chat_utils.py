from __future__ import annotations
import os
import google.generativeai as genai
from api import chat_service

def init_gemini_client():
    """Initialize the Google GenAI client."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        # print("Warning: GOOGLE_API_KEY not found.") # Reduce log noise
        return None
    genai.configure(api_key=api_key)
    return genai

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

        model = client.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"""
        Generate a very short, concise title (max 4-5 words) for a chat session that starts with:
        User: {first_question}
        AI: {first_answer}
        
        The title should summarize the user's intent. Do not use quotes.
        """
        
        response = model.generate_content(prompt)
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
