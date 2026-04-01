import os
from langchain_groq import ChatGroq
from app.core.config import settings

if settings.GROQ_API_KEY:
    os.environ["GROQ_API_KEY"] = settings.GROQ_API_KEY

def get_llm(model_id: str = "llama-3.3-70b-versatile"):
    """Factory function to get a configured ChatGroq instance for a specific model."""
    # Guard: Use a safe default if the model_id is malformed
    safe_model = model_id if model_id else "llama-3.3-70b-versatile"
    
    return ChatGroq(
        model=safe_model,
        temperature=0,
        max_tokens=None,
        max_retries=2,
    )
