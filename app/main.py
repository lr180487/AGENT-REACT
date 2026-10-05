

"""
Agent ReAct - FastAPI Application

Arquitectura:

    FRONTEND
        |
        v
    FASTAPI
        |
        +--> ANALYZER
        |
        +--> PROCESSOR
        |
        +--> RESPONSE
        |
        +--> RAG
        |
        +--> LLM
        |
        +--> CHATS
        |
        +--> DOCUMENTS
        |
        +--> WEBSOCKET /ws/langchain

Compatible con:
- Python 3.14
- uv
- Uvicorn
- Render
- Upstash Redis
- Upstash QStash
"""

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db.database import init_db


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
)

logger = logging.getLogger("app.main")


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

logger.info("BASE_DIR: %s", BASE_DIR)
logger.info("FRONTEND_DIR: %s", FRONTEND_DIR)


# ============================================================
# FRONTEND DETECTION
# ============================================================

frontend_dir: Path | None = None

if FRONTEND_DIR.exists() and FRONTEND_DIR.is_dir():
    frontend_dir = FRONTEND_DIR
    logger.info("✓ Frontend encontrado: %s", frontend_dir)
else:
    logger.warning("⚠ Frontend no encontrado: %s", FRONTEND_DIR)


# ============================================================
# ROUTER IMPORTS
# ============================================================

def load_router(module_name: str, router_name: str = "router"):
    """
    Carga un router de forma segura.

    Evita que un router opcional rompa completamente
    el arranque de FastAPI.
    """
    try:
        module = __import__(
            module_name,
            fromlist=[router_name],
        )

        router = getattr(module, router_name)

        logger.info("✓ %s cargado", module_name)

        return router

    except ImportError as exc:
        logger.warning(
            "⚠ Router %s no disponible: %s",
            module_name,
            exc,
        )

        return None

    except AttributeError as exc:
        logger.error(
            "✗ Router %s no contiene '%s': %s",
            module_name,
            router_name,
            exc,
        )

        return None

    except Exception:
        logger.exception(
            "✗ Error cargando router %s",
            module_name,
        )

        return None


# ============================================================
# ROUTERS
# ============================================================

health_router = load_router(
    "app.api.routes_health"
)

langchain_router = load_router(
    "app.api.routes_langchain"
)

analyzer_router = load_router(
    "app.api.routes_analyzer"
)

llm_router = load_router(
    "app.api.routes_llm"
)

chats_router = load_router(
    "app.api.routes_chats"
)

agent_router = load_router(
    "app.api.routes_agent"
)

documents_router = load_router(
    "app.api.routes_documents"
)

rag_router = load_router(
    "app.api.routes_rag"
)


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup / shutdown moderno de FastAPI.

    Reemplaza:
        @app.on_event("startup")
        @app.on_event("shutdown")
    """

    logger.info("========================================")
    logger.info("🚀 Agent ReAct iniciando")
    logger.info("========================================")

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    try:
        init_db()
        logger.info("✓ Base de datos inicializada")
    except Exception:
        logger.exception(
            "✗ Error inicializando la base de datos"
        )
        raise

    # --------------------------------------------------------
    # ENVIRONMENT
    # --------------------------------------------------------

    logger.info(
        "Environment: %s",
        getattr(
            settings,
            "ENVIRONMENT",
            os.getenv("ENVIRONMENT", "development"),
        ),
    )

    # --------------------------------------------------------
    # REDIS
    # --------------------------------------------------------

    redis_configured = getattr(
        settings,
        "redis_configured",
        bool(
            getattr(
                settings,
                "REDIS_URL",
                "",
            )
        ),
    )

    logger.info(
        "Upstash Redis: %s",
        "✓ configurado" if redis_configured else "⚠ no configurado",
    )

    # --------------------------------------------------------
    # QSTASH
    # --------------------------------------------------------

    qstash_configured = getattr(
        settings,
        "qstash_configured",
        bool(
            getattr(
                settings,
                "QSTASH_TOKEN",
                "",
            )
        ),
    )

    logger.info(
        "Upstash QStash: %s",
        "✓ configurado" if qstash_configured else "⚠ no configurado",
    )

    # --------------------------------------------------------
    # APPLICATION READY
    # --------------------------------------------------------

    logger.info("----------------------------------------")
    logger.info("ANALYZER : 10")
    logger.info("PROCESSOR : 7 + TRI")
    logger.info("RESPONSE : 5")
    logger.info("WebSocket: /ws/langchain")

    if frontend_dir:
        logger.info(
            "Frontend : %s",
            frontend_dir,
        )

    logger.info("========================================")

    yield

    # --------------------------------------------------------
    # SHUTDOWN
    # --------------------------------------------------------

    logger.info("🛑 Agent ReAct detenido")


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title=getattr(
        settings,
        "APP_NAME",
        "Agent ReAct",
    ),
    description=(
        "Agent ReAct con flujo "
        "ANALYZER → PROCESSOR → RESPONSE"
    ),
    version=getattr(
        settings,
        "APP_VERSION",
        "3.0.0",
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ============================================================
# CORS
# ============================================================

cors_origins = getattr(
    settings,
    "cors_origins_list",
    ["*"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROUTER REGISTRATION
# ============================================================

if health_router:
    app.include_router(
        health_router,
        prefix="/api/v1",
        tags=["Health"],
    )
    logger.info("✓ health_router en /api/v1")


if langchain_router:
    app.include_router(
        langchain_router,
    )
    logger.info(
        "✓ langchain_router en "
        "/ws/langchain y /api/langchain/status"
    )


if analyzer_router:
    app.include_router(
        analyzer_router,
        prefix="/api/v1/analyzer",
        tags=["Analyzer"],
    )
    logger.info(
        "✓ analyzer_router en /api/v1/analyzer"
    )


if llm_router:
    app.include_router(
        llm_router,
        prefix="/api/v1/llm",
        tags=["LLM"],
    )
    logger.info(
        "✓ llm_router en /api/v1/llm"
    )


if chats_router:
    app.include_router(
        chats_router,
        prefix="/api/v1/chats",
        tags=["Chats"],
    )
    logger.info(
        "✓ chats_router en /api/v1/chats"
    )


if agent_router:
    app.include_router(
        agent_router,
        prefix="/api/v1",
        tags=["Agent"],
    )
    logger.info(
        "✓ agent_router"
    )


if documents_router:
    app.include_router(
        documents_router,
        prefix="/api/v1",
        tags=["Documents"],
    )
    logger.info(
        "✓ documents_router"
    )


if rag_router:
    app.include_router(
        rag_router,
        prefix="/api/v1",
        tags=["RAG"],
    )
    logger.info(
        "✓ rag_router"
    )


# ============================================================
# HEALTH
# ============================================================

@app.get(
    "/health",
    tags=["Health"],
    include_in_schema=False,
)
async def health():
    return {
        "status": "ok",
        "service": "agent-react",
        "version": getattr(
            settings,
            "APP_VERSION",
            "3.0.0",
        ),
        "flow": (
            "ANALYZER (10) → "
            "PROCESSOR (7+tri) → "
            "RESPONSE (5)"
        ),
        "websocket": "/ws/langchain",
        "frontend": bool(frontend_dir),
    }


# ============================================================
# API HEALTH
# ============================================================

@app.get(
    "/api/health",
    tags=["Health"],
)
async def api_health():
    return {
        "status": "ok",
        "service": "agent-react",
        "database": "configured",
        "redis": getattr(
            settings,
            "redis_configured",
            False,
        ),
        "qstash": getattr(
            settings,
            "qstash_configured",
            False,
        ),
    }


# ============================================================
# FRONTEND ASSETS
# ============================================================

ASSET_FILES = {
    "llm-config.js",
    "script.js",
    "nuevo-chat.js",
    "chat.js",
    "agent-ws.js",
    "favicon.png",
    "favicon.svg",
    "favicon.ico",
    "logo.png",
}


def find_frontend_file(filename: str) -> Path | None:
    """
    Busca un archivo dentro del frontend.
    """

    if not frontend_dir:
        return None

    candidate = (
        frontend_dir / filename
    ).resolve()

    try:
        candidate.relative_to(
            frontend_dir.resolve()
        )
    except ValueError:
        return None

    if candidate.exists() and candidate.is_file():
        return candidate

    return None


@app.get(
    "/llm-config.js",
    include_in_schema=False,
)
async def llm_config():
    file = find_frontend_file(
        "llm-config.js"
    )

    if not file:
        return HTMLResponse(
            "llm-config.js no encontrado",
            status_code=404,
        )

    return FileResponse(
        str(file),
        media_type="application/javascript",
    )


@app.get(
    "/script.js",
    include_in_schema=False,
)
async def script():
    file = find_frontend_file(
        "script.js"
    )

    if not file:
        return HTMLResponse(
            "script.js no encontrado",
            status_code=404,
        )

    return FileResponse(
        str(file),
        media_type="application/javascript",
    )


@app.get(
    "/chat.js",
    include_in_schema=False,
)
async def chat_js():
    file = find_frontend_file(
        "chat.js"
    )

    if not file:
        return HTMLResponse(
            "chat.js no encontrado",
            status_code=404,
        )

    return FileResponse(
        str(file),
        media_type="application/javascript",
    )


@app.get(
    "/agent-ws.js",
    include_in_schema=False,
)
async def agent_ws_js():
    file = find_frontend_file(
        "agent-ws.js"
    )

    if not file:
        return HTMLResponse(
            "agent-ws.js no encontrado",
            status_code=404,
        )

    return FileResponse(
        str(file),
        media_type="application/javascript",
    )


# ============================================================
# FRONTEND HTML
# ============================================================

HTML_FILES = {
    "index.html",
    "interfaz.html",
    "nuevo-chat.html",
    "dashboard.html",
}


@app.get(
    "/frontend",
    include_in_schema=False,
)
@app.get(
    "/frontend/",
    include_in_schema=False,
)
async def frontend_home():
    if not frontend_dir:
        return HTMLResponse(
            "Frontend no encontrado",
            status_code=404,
        )

    for filename in (
        "index.html",
        "interfaz.html",
        "nuevo-chat.html",
        "dashboard.html",
    ):
        file = (
            frontend_dir / filename
        )

        if file.exists():
            return FileResponse(
                str(file)
            )

    return HTMLResponse(
        "No existe index.html",
        status_code=404,
    )


def create_html_handler(filename: str):
    async def handler():
        if not frontend_dir:
            return HTMLResponse(
                f"{filename} no encontrado",
                status_code=404,
            )

        file = (
            frontend_dir / filename
        )

        if not file.exists():
            return HTMLResponse(
                f"{filename} no encontrado",
                status_code=404,
            )

        return FileResponse(
            str(file),
            media_type="text/html",
        )

    return handler


for html_file in HTML_FILES:
    app.get(
        f"/{html_file}",
        include_in_schema=False,
    )(
        create_html_handler(html_file)
    )


# ============================================================
# ROOT
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
    tags=["Root"],
)
async def root():
    if frontend_dir:
        for filename in (
            "index.html",
            "interfaz.html",
            "nuevo-chat.html",
            "dashboard.html",
        ):
            file = (
                frontend_dir / filename
            )

            if file.exists():
                return FileResponse(
                    str(file),
                    media_type="text/html",
                )

    return HTMLResponse(
        content="""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Agent ReAct</title>
</head>
<body
    style="
        font-family: Arial, sans-serif;
        padding: 40px;
    "
>
    <h1>Agent ReAct</h1>

    <p>
        ANALYZER → PROCESSOR → RESPONSE
    </p>

    <ul>
        <li>
            <a href="/docs">
                API Docs
            </a>
        </li>

        <li>
            <a href="/health">
                Health
            </a>
        </li>

        <li>
            <a href="/api/health">
                API Health
            </a>
        </li>

        <li>
            <a href="/api/langchain/status">
                LangChain Status
            </a>
        </li>

        <li>
            <a href="/frontend/">
                Frontend
            </a>
        </li>
    </ul>
</body>
</html>
"""
    )


# ============================================================
# STATIC FRONTEND
# ============================================================

if frontend_dir:
    app.mount(
        "/frontend",
        StaticFiles(
            directory=str(frontend_dir),
            html=True,
        ),
        name="frontend",
    )

    logger.info(
        "✓ Frontend montado en /frontend → %s",
        frontend_dir,
    )


# ============================================================
# ROUTE DEBUG
# ============================================================

logger.info(
    "✓ FastAPI cargado con %d rutas",
    len(app.routes),
)



