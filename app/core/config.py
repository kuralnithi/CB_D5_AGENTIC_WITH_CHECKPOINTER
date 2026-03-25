import os
from pydantic_settings import BaseSettings

# load_dotenv() is called only when a .env file is present (local dev).
# In production (Hugging Face Spaces), secrets are injected as environment
# variables directly — no .env file is needed or committed.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class Settings(BaseSettings):
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/finance_agent"
    )

settings = Settings()
