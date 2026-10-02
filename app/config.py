from __future__ import annotations

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "agente_react_rag"
    VERSION: str = "5.0.0"
    ENV: str = "development"

    DATABASE_URL: str = "sqlite:///./react_rag.db"
    REDIS_URL: Optional[str] = None
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    AGENT_TASK_SOFT_TIME_LIMIT: int = 300
    AGENT_TASK_TIME_LIMIT: int = 330
    RECONNECT_GRACE_SECONDS: int = 30

    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_BASE_URL: Optional[str] = None
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 2048
    AGENT_MAX_ITERATIONS: int = 5

    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    TAVILY_API_KEY: Optional[str] = None
    WEB_SEARCH_MAX_RESULTS: int = 5
    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_CSE_ID: Optional[str] = None
    GOOGLE_SAFESEARCH: str = "active"

    SECRET_KEY: str = "change-me-in-production"
    ENCRYPTION_KEY: str = "change-me-in-production"

    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 120
    RAG_MIN_SCORE: float = 0.20

    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_FILE_SIZE_MB: int = 25

    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), str(BASE_DIR / "app" / "api" / ".env")),
        extra="ignore",
    )


settings = Settings()
