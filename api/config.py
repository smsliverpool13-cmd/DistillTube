from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Groq
    groq_api_key: str = ""

    # Nomic AI (embeddings)
    nomic_api_key: str = ""

    # Qdrant Cloud
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "transcripts"

    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""

    # FastAPI
    fastapi_port: int = 8000
    fastapi_reload: bool = True

    # Frontend
    next_public_api_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
