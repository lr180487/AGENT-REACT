<<<<<<< HEAD
=======

"""
app/config.py

Configuración central de AGENT-REACT.

Incluye:

- PostgreSQL / SQLite
- Redis local
- Upstash Redis
- Celery Broker
- Celery Result Backend
- LLM
- RAG
- Web Search
- Google Search
- Seguridad
- Uploads
"""

>>>>>>> ebbf022 (feat: complete Agent ReAct architecture)
from __future__ import annotations

from pathlib import Path
from typing import Optional
<<<<<<< HEAD
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
=======
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================
# DIRECTORIOS
# ============================================================

APP_DIR = Path(__file__).resolve().parent

BASE_DIR = APP_DIR.parent


# ============================================================
# REDIS URL NORMALIZATION
# ============================================================

def normalize_redis_url(
    url: Optional[str],
) -> Optional[str]:
    """
    Normaliza URLs Redis.

    redis://
        Redis sin TLS.

    rediss://
        Redis con TLS.

    Para Upstash agregamos automáticamente:

        ssl_cert_reqs=CERT_REQUIRED
    """

    if not url:
        return url

    url = url.strip()

    # No modificar Redis normal
    if not url.lower().startswith("rediss://"):
        return url

    parsed = urlsplit(url)

    params = dict(
        parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )
    )

    # Upstash / Redis TLS
    params.setdefault(
        "ssl_cert_reqs",
        "CERT_REQUIRED",
    )

    query = urlencode(params)

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            query,
            parsed.fragment,
        )
    )


# ============================================================
# SETTINGS
# ============================================================

class Settings(BaseSettings):

    # ========================================================
    # APPLICATION
    # ========================================================

    APP_NAME: str = "AGENT-REACT"

    VERSION: str = "3.0.0"

    ENV: str = "development"

    DEBUG: bool = True


    # ========================================================
    # DATABASE
    # ========================================================

    DATABASE_URL: str = "sqlite:///./react_rag.db"

    DB_ECHO: bool = False


    # ========================================================
    # REDIS LOCAL
    # ========================================================

    REDIS_URL: Optional[str] = None


    # ========================================================
    # UPSTASH REDIS
    # ========================================================

    UPSTASH_REDIS_URL: Optional[str] = None

    UPSTASH_REDIS_HOST: Optional[str] = None

    UPSTASH_REDIS_PORT: int = 6379

    UPSTASH_REDIS_USERNAME: Optional[str] = "default"

    UPSTASH_REDIS_PASSWORD: Optional[str] = None

    UPSTASH_REDIS_TLS: bool = True


    # ========================================================
    # CELERY
    # ========================================================

    CELERY_BROKER_URL: Optional[str] = None

    CELERY_RESULT_BACKEND: Optional[str] = None


    # ========================================================
    # CELERY TASKS
    # ========================================================

    AGENT_TASK_SOFT_TIME_LIMIT: int = 300

    AGENT_TASK_TIME_LIMIT: int = 330

    AGENT_TASK_MAX_RETRIES: int = 3

    AGENT_TASK_RETRY_DELAY: int = 5

    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 1


    # ========================================================
    # CACHE
    # ========================================================

    CACHE_ENABLED: bool = True

    CACHE_TTL: int = 300

    CACHE_PREFIX: str = "agent-react:"


    # ========================================================
    # LLM
    # ========================================================

    LLM_PROVIDER: str = "openai"

    LLM_MODEL: str = "gpt-4o-mini"

    LLM_BASE_URL: Optional[str] = None

    LLM_TEMPERATURE: float = 0.2

    LLM_MAX_TOKENS: int = 2048


    # ========================================================
    # API KEYS
    # ========================================================

    OPENAI_API_KEY: Optional[str] = None

    ANTHROPIC_API_KEY: Optional[str] = None

    GEMINI_API_KEY: Optional[str] = None

    GROQ_API_KEY: Optional[str] = None


    # ========================================================
    # AGENT
    # ========================================================

    AGENT_MAX_ITERATIONS: int = 5

    AGENT_TIMEOUT: int = 120

    AGENT_ENABLE_MEMORY: bool = True

    AGENT_ENABLE_RAG: bool = True

    AGENT_ENABLE_WEB_SEARCH: bool = True

    AGENT_ENABLE_GOOGLE_SEARCH: bool = True


    # ========================================================
    # RAG
    # ========================================================

    EMBEDDING_MODEL: str = "text-embedding-3-small"

    EMBEDDING_DIM: int = 1536

    CHUNK_SIZE: int = 800

    CHUNK_OVERLAP: int = 120

    RAG_MIN_SCORE: float = 0.20


    # ========================================================
    # VECTOR DATABASE
    # ========================================================

    VECTOR_DB: str = "pgvector"

    PGVECTOR_ENABLED: bool = True


    # ========================================================
    # WEB SEARCH
    # ========================================================

    TAVILY_API_KEY: Optional[str] = None

    WEB_SEARCH_MAX_RESULTS: int = 5


    # ========================================================
    # GOOGLE SEARCH
    # ========================================================

    GOOGLE_API_KEY: Optional[str] = None

    GOOGLE_CSE_ID: Optional[str] = None

    GOOGLE_SAFESEARCH: str = "active"


    # ========================================================
    # SECURITY
    # ========================================================

    SECRET_KEY: str = "change-me-in-production"

    ENCRYPTION_KEY: str = "change-me-in-production"

    JWT_ALGORITHM: str = "HS256"

    JWT_EXPIRE_MINUTES: int = 60


    # ========================================================
    # UPLOADS
    # ========================================================

    UPLOAD_DIR: str = str(
        BASE_DIR / "uploads"
    )

    MAX_FILE_SIZE_MB: int = 25


    # ========================================================
    # PYDANTIC SETTINGS
    # ========================================================

    model_config = SettingsConfigDict(

        env_file=(
            str(BASE_DIR / ".env"),
            str(BASE_DIR / "app" / ".env"),
        ),

        env_file_encoding="utf-8",

        extra="ignore",

        case_sensitive=False,
    )


# ============================================================
# CREATE SETTINGS
# ============================================================

settings = Settings()


# ============================================================
# UPSTASH RESOLUTION
# ============================================================

def resolve_redis_url() -> Optional[str]:
    """
    Determina qué Redis utilizar.

    Prioridad:

    1. UPSTASH_REDIS_URL
    2. REDIS_URL
    3. Redis construido desde HOST/PASSWORD
    """

    # --------------------------------------------------------
    # 1. Upstash URL
    # --------------------------------------------------------

    if settings.UPSTASH_REDIS_URL:

        return normalize_redis_url(
            settings.UPSTASH_REDIS_URL
        )


    # --------------------------------------------------------
    # 2. Redis URL general
    # --------------------------------------------------------

    if settings.REDIS_URL:

        return normalize_redis_url(
            settings.REDIS_URL
        )


    # --------------------------------------------------------
    # 3. Construir URL Upstash
    # --------------------------------------------------------

    if (
        settings.UPSTASH_REDIS_HOST
        and settings.UPSTASH_REDIS_PASSWORD
    ):

        scheme = (
            "rediss://"
            if settings.UPSTASH_REDIS_TLS
            else "redis://"
        )

        url = (
            f"{scheme}"
            f"{settings.UPSTASH_REDIS_USERNAME}:"
            f"{settings.UPSTASH_REDIS_PASSWORD}@"
            f"{settings.UPSTASH_REDIS_HOST}:"
            f"{settings.UPSTASH_REDIS_PORT}/0"
        )

        return normalize_redis_url(url)


    # --------------------------------------------------------
    # 4. Nada configurado
    # --------------------------------------------------------

    return None


# ============================================================
# RESOLVER REDIS PRINCIPAL
# ============================================================

REDIS_URL = resolve_redis_url()


# ============================================================
# CELERY BROKER
# ============================================================

CELERY_BROKER_URL = normalize_redis_url(
    settings.CELERY_BROKER_URL
) if settings.CELERY_BROKER_URL else REDIS_URL


# ============================================================
# CELERY RESULT BACKEND
# ============================================================

CELERY_RESULT_BACKEND = normalize_redis_url(
    settings.CELERY_RESULT_BACKEND
) if settings.CELERY_RESULT_BACKEND else REDIS_URL


# ============================================================
# EXPORTAR CONFIGURACIÓN
# ============================================================

settings.REDIS_URL = REDIS_URL

settings.CELERY_BROKER_URL = CELERY_BROKER_URL

settings.CELERY_RESULT_BACKEND = CELERY_RESULT_BACKEND


# ============================================================
# HELPERS
# ============================================================

def is_upstash_enabled() -> bool:
    """
    True cuando se está utilizando Upstash.
    """

    return bool(
        settings.UPSTASH_REDIS_URL
        or (
            settings.UPSTASH_REDIS_HOST
            and settings.UPSTASH_REDIS_PASSWORD
        )
    )


def redis_enabled() -> bool:
    """
    True cuando existe configuración Redis.
    """

    return bool(
        settings.REDIS_URL
    )


def get_redis_url() -> Optional[str]:
    """
    Devuelve la URL Redis efectiva.
    """

    return settings.REDIS_URL


def get_celery_broker_url() -> Optional[str]:
    """
    Devuelve el broker efectivo de Celery.
    """

    return settings.CELERY_BROKER_URL


def get_celery_backend_url() -> Optional[str]:
    """
    Devuelve el backend efectivo de Celery.
    """

    return settings.CELERY_RESULT_BACKEND
>>>>>>> ebbf022 (feat: complete Agent ReAct architecture)
