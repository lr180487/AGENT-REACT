
"""
main.py — Backend ANALYZER → PROCESSOR → RESPONSE (corregido para frontend)
Sincronizado con interfaz.html / nuevo-chat.html — corrige 404 en /llm-config.js, /script.js, /favicon.*
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
from contextlib import asynccontextmanager
from app.db.database import init_db
import logging

# --- Routers ---
try:
    from app.api.routes_analyzer import router as analyzer_router
except ImportError:
    analyzer_router = None

try:
    from app.api.routes_langchain import router as langchain_router
except ImportError:
    langchain_router = None

try:
    from app.api.routes_llm import router as llm_router
except ImportError:
    llm_router = None

try:
    from app.api.routes_chats import router as chats_router
except ImportError:
    chats_router = None

try:
    from app.api.routes_health import router as health_router
except ImportError:
    health_router = None

"""
app/main.py
Backend ANALYZER → PROCESSOR → RESPONSE

Correcciones:
- GET / ya no devuelve 404.
- El root se registra ANTES del catch-all.
- Frontend detectado de forma portable Windows/Linux.
- /frontend/* funciona.
- Assets JS/CSS/PNG/SVG/ICO funcionan desde /.
- /interfaz.html funciona.
- /nuevo-chat.html funciona.
- /dashboard.html funciona.
- /index.html funciona.
- /llm-config.js funciona.
- /script.js funciona.
- /favicon.* funciona.
- No se usa /home/user como ruta fija.
- Se elimina la duplicación de /health.
"""

from pathlib import Path
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.db.database import init_db


# ============================================================
# LOGGING
# ============================================================


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- App ---
app = FastAPI(
    title="Backend ANALYZER → PROCESSOR → RESPONSE",
    description="""
    **Flujo:** Usuario → FastAPI → ANALYZER (10) → PROCESSOR (7 + tri) → RESPONSE (5) → USER (WS/Frontend)
    **WebSocket:** WS /ws/langchain cada 2s + GET /api/langchain/status


# ============================================================
# DIRECTORIOS
# ============================================================

# app/main.py
APP_DIR = Path(__file__).resolve().parent

# raíz del proyecto
BASE_DIR = APP_DIR.parent

# frontend/
FRONTEND_DIR = BASE_DIR / "frontend"


logger.info(f"BASE_DIR: {BASE_DIR}")
logger.info(f"FRONTEND_DIR: {FRONTEND_DIR}")


# ============================================================
# VALIDACIÓN FRONTEND
# ============================================================

if FRONTEND_DIR.exists():
    logger.info(f"✓ Frontend encontrado: {FRONTEND_DIR}")
else:
    logger.warning(f"⚠ Frontend no encontrado: {FRONTEND_DIR}")


# ============================================================
# IMPORTACIÓN DE ROUTERS
# ============================================================

try:
    from app.api.routes_analyzer import router as analyzer_router
except ImportError as exc:
    analyzer_router = None
    logger.warning(f"⚠ analyzer_router no disponible: {exc}")


try:
    from app.api.routes_langchain import router as langchain_router
except ImportError as exc:
    langchain_router = None
    logger.warning(f"⚠ langchain_router no disponible: {exc}")


try:
    from app.api.routes_llm import router as llm_router
except ImportError as exc:
    llm_router = None
    logger.warning(f"⚠ llm_router no disponible: {exc}")


try:
    from app.api.routes_chats import router as chats_router
except ImportError as exc:
    chats_router = None
    logger.warning(f"⚠ chats_router no disponible: {exc}")


try:
    from app.api.routes_health import router as health_router
except ImportError as exc:
    health_router = None
    logger.warning(f"⚠ health_router no disponible: {exc}")


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Backend ANALYZER → PROCESSOR → RESPONSE",
    description="""
    Flujo:

    Usuario
        ↓
    FastAPI
        ↓
    ANALYZER
        ↓
    PROCESSOR
        ↓
    RESPONSE
        ↓
    USER / FRONTEND / WEBSOCKET

    WebSocket:
    /ws/langchain

    LangChain:
    /api/langchain/status
    """,
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)




# ============================================================
# CORS
# ============================================================


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Routers (ANTES de estáticos) ---
if health_router:
    app.include_router(health_router, prefix="/api/v1", tags=["Health"])
    logger.info("✓ health_router en /api/v1")

if langchain_router:
    app.include_router(langchain_router)
    logger.info("✓ langchain_router en /ws/langchain y /api/langchain/status")


# ============================================================
# API ROUTERS
# ============================================================

if health_router:
    app.include_router(
        health_router,
        prefix="/api/v1",
        tags=["Health"],
    )
    logger.info("✓ health_router en /api/v1")


if langchain_router:
    app.include_router(langchain_router)
    logger.info(
        "✓ langchain_router en /ws/langchain "
        "y /api/langchain/status"
    )


if analyzer_router:
    app.include_router(analyzer_router)
    logger.info("✓ analyzer_router en /api/v1/analyzer")





if llm_router:
    app.include_router(llm_router)
    logger.info("✓ llm_router en /api/v1/llm")




if chats_router:
    app.include_router(chats_router)
    logger.info("✓ chats_router en /api/v1/chats")


try:
    from app.api.routes_agent import router as agent_router
    app.include_router(agent_router, prefix="/api/v1")
    logger.info("✓ agent_router")
except ImportError:
    pass

try:
    from app.api.routes_documents import router as documents_router
    app.include_router(documents_router, prefix="/api/v1")
    logger.info("✓ documents_router")
except ImportError:
    pass

try:
    from app.api.routes_rag import router as rag_router
    app.include_router(rag_router, prefix="/api/v1")
    logger.info("✓ rag_router")
except ImportError:
    pass

# --- Frontend estático CORREGIDO ---
# Candidatos (Windows: C:\users\lreyn\downloads\agent-react\agente_react_rag\frontend
#          Linux: /home/user/agente_react_rag/frontend)
FRONTEND_CANDIDATES = [
    Path("/home/user/agente_react_rag/frontend"),
    Path(__file__).resolve().parent.parent / "frontend",
    Path(__file__).resolve().parents[2] / "agente_react_rag" / "frontend",
    Path(__file__).resolve().parent / "frontend",
]

frontend_dir = None
for cand in FRONTEND_CANDIDATES:
    if cand.exists() and (cand / "index.html").exists():
        frontend_dir = cand
        break

# Fallback para desarrollo Windows: si no se encuentra, usa el directorio del proyecto actual
if not frontend_dir:
    # Intenta BASE_DIR / frontend (para snippet original)
    base_candidate = Path(__file__).resolve().parent.parent / "frontend"
    if base_candidate.exists():
        frontend_dir = base_candidate

root_dir = Path("/home/user")
BASE_DIR = Path(__file__).resolve().parent.parent

# Montajes corregidos:
# 1) /frontend → sirve todo el frontend con html=True (index.html automático)
if frontend_dir:
    app.mount("/frontend", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    logger.info(f"✓ Frontend en /frontend → {frontend_dir} (html=True)")

# 2) /static → compatibilidad con rutas antiguas
if (root_dir / "interfaz.html").exists():
    app.mount("/static", StaticFiles(directory=str(root_dir)), name="static")
    logger.info("✓ Static en /static → /home/user")
elif frontend_dir:
    # Si no hay root_dir, monta frontend también en /static para fallback
    app.mount("/static", StaticFiles(directory=str(frontend_dir), html=True), name="static-fallback")
    logger.info(f"✓ Static fallback en /static → {frontend_dir}")

@app.get("/health", tags=["Health"], include_in_schema=False)
def root_health():
    return {"status": "ok", "service": "agente_react_rag", "version": "3.0.0"}

# --- Archivos estáticos en root CORREGIDOS (evita 404 en /llm-config.js, /script.js, /favicon.*) ---
# El error era: interfaz.html pide src="llm-config.js" → GET /llm-config.js 404 porque solo montamos /frontend y /static
# Solución: rutas directas para assets comunes + catch-all para cualquier archivo del frontend

ASSET_FILES = [
    "llm-config.js", "script.js", "nuevo-chat.js", "chat.js",
    "favicon.png", "favicon.svg", "favicon.ico", "logo.png",
]

for asset in ASSET_FILES:
    def _make_asset_handler(fname):
        async def _asset():
            for base in [frontend_dir, root_dir, BASE_DIR / "frontend"]:
                if base and (base / fname).exists():
                    return FileResponse(str(base / fname))
            return HTMLResponse(f"404 {fname} no encontrado", status_code=404)
        return _asset
    app.get(f"/{asset}", tags=["Frontend-Assets"])(_make_asset_handler(asset))

# También servir cualquier archivo .js/.css/.png/.svg/.ico del frontend en root (catch-all)
@app.get("/{full_path:path}", tags=["Frontend-CatchAll"], include_in_schema=False)
async def serve_frontend_assets(request: Request, full_path: str):
    # No interferir con /api, /ws, /docs, /redoc, /openapi.json, /health
    if full_path in {"health"} or full_path.startswith(("api/", "ws/", "docs", "redoc", "openapi.json")):
        return HTMLResponse("Not found", status_code=404)
    # Solo servir archivos con extensión conocida
    if "." not in full_path or full_path.startswith("frontend/") or full_path.startswith("static/"):
        return HTMLResponse("Not found", status_code=404)
    # Busca en frontend_dir y root_dir
    for base in [frontend_dir, root_dir, BASE_DIR / "frontend"]:
        if base:
            candidate = base / full_path
            # Evita path traversal
            try:
                candidate.resolve().relative_to(base.resolve())
            except ValueError:
                continue
            if candidate.exists() and candidate.is_file():
                return FileResponse(str(candidate))
    # No encontrado → 404 pero no interfiere con API
    # Si pide html sin extensión, intenta con .html
    if "." not in full_path:
        for base in [frontend_dir, root_dir]:
            if base and (base / f"{full_path}.html").exists():
                return FileResponse(str(base / f"{full_path}.html"))
    return HTMLResponse(f"404 {full_path} no encontrado", status_code=404)

# --- Root ---
@app.get("/", response_class=HTMLResponse, tags=["Root"])
async def root():
    for cand in [
        frontend_dir / "index.html" if frontend_dir else None,
        frontend_dir / "dashboard.html" if frontend_dir else None,
        root_dir / "interfaz.html",
        BASE_DIR / "frontend" / "index.html",
        frontend_dir / "interfaz.html" if frontend_dir else None,
    ]:
        if cand and cand.exists():
            return FileResponse(str(cand))
    return HTMLResponse(content="""
    <html><body style="font-family:monospace;padding:32px">
    <h3>Backend ANALYZER → PROCESSOR → RESPONSE 2.1</h3>
    <p>Flow: ANALYZER (10) → PROCESSOR (7+tri) → RESPONSE (5) → USER</p>
    <ul>
      <li><a href="/docs">/docs</a></li>
      <li><a href="/api/langchain/status">/api/langchain/status</a> · WS <code>/ws/langchain</code></li>
      <li><a href="/frontend/">/frontend/</a> | <a href="/interfaz.html">/interfaz.html</a> | <a href="/nuevo-chat.html">/nuevo-chat.html</a></li>
    </ul>
    </body></html>
    """)

# Rutas directas para HTML principales (sincronización con interfaz.html, nuevo-chat.html)
for fname in ["interfaz.html", "nuevo-chat.html", "dashboard.html", "index.html"]:
    def _make_handler(name):
        async def _handler():
            for base in [frontend_dir, root_dir, BASE_DIR / "frontend"]:
                if base and (base / name).exists():
                    return FileResponse(str(base / name))
            return HTMLResponse(f"<h1>404 {name} no encontrado</h1>", status_code=404)
        return _handler
    app.get(f"/{fname}", response_class=HTMLResponse, tags=["Frontend"])(_make_handler(fname))
    app.get(f"/{fname.replace('.html','')}", response_class=HTMLResponse, tags=["Frontend"])(_make_handler(fname))

@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "ok",
        "flow": "ANALYZER (10) → PROCESSOR (7+tri) → RESPONSE (5) → USER → WS",
        "analyzer": "10 pasos",
        "processor": "7 ramas + tri",
        "response": "5 apartados",
        "websocket": "/ws/langchain",
        "frontend": "/frontend/ , /interfaz.html , /nuevo-chat.html , /llm-config.js , /script.js",
    }

@app.on_event("startup")
async def on_startup():
    init_db()
    logger.info("🚀 Backend 3.0 — ANALYZER 10 | PROCESSOR 7 | RESPONSE 5 | WS /ws/langchain")
    if frontend_dir:
        logger.info(f"   Frontend: {frontend_dir} → /frontend/ + / + /static + /llm-config.js etc.")

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("🛑 Backend detenido")


# ------------------------------------------------------------
# AGENT
# ------------------------------------------------------------

try:
    from app.api.routes_agent import router as agent_router

    app.include_router(
        agent_router,
        prefix="/api/v1",
    )

    logger.info("✓ agent_router")

except ImportError as exc:
    logger.warning(f"⚠ agent_router no disponible: {exc}")


# ------------------------------------------------------------
# DOCUMENTS
# ------------------------------------------------------------

try:
    from app.api.routes_documents import router as documents_router

    app.include_router(
        documents_router,
        prefix="/api/v1",
    )

    logger.info("✓ documents_router")

except ImportError as exc:
    logger.warning(f"⚠ documents_router no disponible: {exc}")


# ------------------------------------------------------------
# RAG
# ------------------------------------------------------------

try:
    from app.api.routes_rag import router as rag_router

    app.include_router(
        rag_router,
        prefix="/api/v1",
    )

    logger.info("✓ rag_router")

except ImportError as exc:
    logger.warning(f"⚠ rag_router no disponible: {exc}")


# ============================================================
# FRONTEND: /frontend
# ============================================================

if FRONTEND_DIR.exists():

    app.mount(
        "/frontend",
        StaticFiles(
            directory=str(FRONTEND_DIR),
            html=True,
        ),
        name="frontend",
    )

    logger.info(
        f"✓ Frontend montado en /frontend → {FRONTEND_DIR}"
    )


# ============================================================
# FUNCIÓN AUXILIAR PARA BUSCAR ARCHIVOS
# ============================================================

def find_frontend_file(filename: str) -> Path | None:
    """
    Busca un archivo primero en frontend/
    y luego en la raíz del proyecto.
    """

    candidates = [
        FRONTEND_DIR / filename,
        BASE_DIR / filename,
    ]

    for candidate in candidates:

        if candidate.exists() and candidate.is_file():
            return candidate

    return None


# ============================================================
# ROOT /
#
# IMPORTANTE:
# Esta ruta DEBE estar antes del catch-all.
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
    tags=["Root"],
)
async def root():

    # Prioridad 1: frontend/index.html
    index_file = find_frontend_file("index.html")

    if index_file:
        return FileResponse(
            str(index_file),
            media_type="text/html",
        )

    # Prioridad 2: frontend/interfaz.html
    interfaz_file = find_frontend_file("interfaz.html")

    if interfaz_file:
        return FileResponse(
            str(interfaz_file),
            media_type="text/html",
        )

    # Prioridad 3: dashboard.html
    dashboard_file = find_frontend_file("dashboard.html")

    if dashboard_file:
        return FileResponse(
            str(dashboard_file),
            media_type="text/html",
        )

    # Fallback
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <title>Agent React</title>
        </head>
        <body style="
            font-family: Arial, sans-serif;
            padding: 40px;
        ">
            <h1>Backend ANALYZER → PROCESSOR → RESPONSE</h1>

            <p>Backend funcionando correctamente.</p>

            <ul>
                <li>
                    <a href="/docs">
                        Swagger /docs
                    </a>
                </li>

                <li>
                    <a href="/redoc">
                        ReDoc
                    </a>
                </li>

                <li>
                    <a href="/health">
                        /health
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
        """,
        status_code=200,
    )


# ============================================================
# HEALTH
# ============================================================

@app.get(
    "/health",
    tags=["Health"],
)
async def health():

    return {
        "status": "ok",
        "service": "agent-react",
        "version": "3.0.0",
        "flow": (
            "ANALYZER (10) → "
            "PROCESSOR (7+tri) → "
            "RESPONSE (5) → "
            "USER"
        ),
        "websocket": "/ws/langchain",
        "frontend": "/frontend/",
    }


# ============================================================
# HTML PRINCIPALES
# ============================================================

FRONTEND_HTML_FILES = [
    "index.html",
    "interfaz.html",
    "nuevo-chat.html",
    "dashboard.html",
    "chat.html",
    "interfaz-nuevo-chat.html",
]


def create_html_handler(filename: str):

    async def handler():

        file_path = find_frontend_file(filename)

        if file_path:

            return FileResponse(
                str(file_path),
                media_type="text/html",
            )

        return HTMLResponse(
            content=f"""
            <h1>404</h1>
            <p>{filename} no encontrado.</p>
            """,
            status_code=404,
        )

    return handler


for filename in FRONTEND_HTML_FILES:

    # /archivo.html
    app.add_api_route(
        f"/{filename}",
        create_html_handler(filename),
        methods=["GET"],
        response_class=HTMLResponse,
        tags=["Frontend"],
    )

    # /archivo
    route_without_extension = filename.removesuffix(".html")

    app.add_api_route(
        f"/{route_without_extension}",
        create_html_handler(filename),
        methods=["GET"],
        response_class=HTMLResponse,
        tags=["Frontend"],
    )


# ============================================================
# ASSETS DIRECTOS
# ============================================================

ASSET_FILES = [
    "llm-config.js",
    "script.js",
    "chat.js",
    "agent-ws.js",
    "nuevo-chat.js",
    "style.css",
    "styles.css",
    "favicon.png",
    "favicon.svg",
    "favicon.ico",
    "logo.png",
]


def create_asset_handler(filename: str):

    async def handler():

        file_path = find_frontend_file(filename)

        if file_path:

            return FileResponse(
                str(file_path)
            )

        return HTMLResponse(
            content=f"404 {filename} no encontrado",
            status_code=404,
        )

    return handler


for filename in ASSET_FILES:

    app.add_api_route(
        f"/{filename}",
        create_asset_handler(filename),
        methods=["GET"],
        tags=["Frontend Assets"],
    )


# ============================================================
# CATCH-ALL
#
# IMPORTANTE:
# Esta ruta SIEMPRE debe quedar AL FINAL.
# ============================================================

@app.get(
    "/{full_path:path}",
    include_in_schema=False,
)
async def serve_frontend_files(full_path: str):

    # ---------------------------------------------
    # Nunca interceptar API
    # ---------------------------------------------

    reserved_prefixes = (
        "api/",
        "ws/",
        "docs",
        "redoc",
        "openapi.json",
        "frontend/",
    )

    if full_path == "":
        return HTMLResponse(
            "Not Found",
            status_code=404,
        )

    if full_path.startswith(reserved_prefixes):
        return HTMLResponse(
            "Not Found",
            status_code=404,
        )

    # ---------------------------------------------
    # Seguridad contra Path Traversal
    # ---------------------------------------------

    for base in [
        FRONTEND_DIR,
        BASE_DIR,
    ]:

        if not base.exists():
            continue

        candidate = base / full_path

        try:

            candidate.resolve().relative_to(
                base.resolve()
            )

        except ValueError:
            continue

        if candidate.exists() and candidate.is_file():

            return FileResponse(
                str(candidate)
            )

    # ---------------------------------------------
    # Intentar .html
    # ---------------------------------------------

    if "." not in full_path:

        for base in [
            FRONTEND_DIR,
            BASE_DIR,
        ]:

            candidate = base / f"{full_path}.html"

            if candidate.exists():

                return FileResponse(
                    str(candidate),
                    media_type="text/html",
                )

    return HTMLResponse(
        content=f"404 {full_path} no encontrado",
        status_code=404,
    )


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def on_startup():

    try:
        init_db()
        logger.info("✓ Base de datos inicializada")

    except Exception as exc:
        logger.exception(
            f"⚠ Error inicializando DB: {exc}"
        )

    logger.info(
        "🚀 Backend 3.0 iniciado"
    )

    logger.info(
        "   ANALYZER 10"
    )

    logger.info(
        "   PROCESSOR 7 + TRI"
    )

    logger.info(
        "   RESPONSE 5"
    )

    logger.info(
        "   WebSocket: /ws/langchain"
    )

    logger.info(
        f"   Frontend: {FRONTEND_DIR}"
    )

    logger.info(
        "   Root: /"
    )

    logger.info(
        "   Assets: /llm-config.js /script.js /favicon.*"
    )


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def on_shutdown():

    logger.info(
        "🛑 Backend detenido"
    )


