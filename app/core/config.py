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
    # .strip() handles accidental newlines/spaces from HF Secrets.
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "").strip()
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/finance_agent"
    ).strip()

    # Logging & environment
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").strip().lower()

    # Request timeout (seconds) — abort requests slower than this
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "60"))

settings = Settings()
