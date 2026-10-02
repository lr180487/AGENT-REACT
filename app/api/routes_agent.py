from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.analyzer_service import AnalyzerService
from app.services.processor_service import ProcessorService
from app.services.response_service import ResponseService
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/agent",
    tags=["Agent"],
)


# ============================================================
# MODELOS
# ============================================================

class AgentRequest(BaseModel):
    """
    Solicitud principal al agente.
    """

    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Pregunta o instrucción enviada al agente.",
    )

    session_id: Optional[str] = Field(
        default=None,
        description="Identificador de sesión/memoria.",
    )

    conversation_id: Optional[str] = Field(
        default=None,
        description="Identificador de conversación.",
    )

    use_rag: bool = Field(
        default=True,
        description="Indica si el agente puede utilizar RAG.",
    )

    use_web: bool = Field(
        default=False,
        description="Indica si se permite búsqueda web mediante Tavily.",
    )

    use_google: bool = Field(
        default=False,
        description="Permite al agente usar Google Programmable Search.",
    )

    temperature: Optional[float] = Field(
        default=None,
        ge=0,
        le=2,
        description="Temperatura opcional del LLM.",
    )

    max_iterations: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Máximo de iteraciones del agente.",
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos adicionales.",
    )


class AgentResponse(BaseModel):
    """
    Respuesta estándar del agente.
    """

    success: bool

    request_id: str

    session_id: str

    conversation_id: Optional[str] = None

    message: str

    answer: str

    agent: dict[str, Any]

    tools_used: list[str] = Field(default_factory=list)

    sources: list[dict[str, Any]] = Field(default_factory=list)

    metadata: dict[str, Any] = Field(default_factory=dict)

    timestamp: str


class AgentStatusResponse(BaseModel):
    status: str
    agent: str
    version: str
    capabilities: list[str]
    timestamp: str


# ============================================================
# UTILIDADES
# ============================================================

def utc_now() -> str:
    """
    Devuelve timestamp UTC ISO-8601.
    """
    return datetime.now(timezone.utc).isoformat()


def generate_session_id() -> str:
    """
    Genera una sesión cuando el cliente no proporciona una.
    """
    return f"session_{uuid.uuid4().hex}"


def generate_request_id() -> str:
    """
    Identificador único para cada ejecución.
    """
    return f"req_{uuid.uuid4().hex}"


# ============================================================
# AGENT SERVICE
# ============================================================

async def execute_agent(request: AgentRequest, request_id: str, session_id: str, db: Session) -> dict[str, Any]:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    from app.services.agent_service import AgentConfigurationError, AgentService

    try:
        return await AgentService(db).run(
            message,
            session_id=session_id,
            conversation_id=request.conversation_id,
            use_rag=request.use_rag,
            use_web=request.use_web,
            use_google=request.use_google,
            max_iterations=request.max_iterations,
            temperature=request.temperature,
        )
    except AgentConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ============================================================
# ENDPOINT PRINCIPAL
# ============================================================

@router.post(
    "/run",
    response_model=AgentResponse,
    summary="Ejecutar agente ReAct",
    description=(
        "Ejecuta una solicitud contra el agente mediante un bucle LLM ReAct basado en tool-calling."
    ),
)
async def run_agent(request: AgentRequest, db: Session = Depends(get_db)) -> AgentResponse:

    request_id = generate_request_id()

    session_id = (
        request.session_id.strip()
        if request.session_id
        else generate_session_id()
    )

    result = await execute_agent(
        request=request,
        request_id=request_id,
        session_id=session_id,
        db=db,
    )

    return AgentResponse(
        success=True,
        request_id=request_id,
        session_id=session_id,
        conversation_id=request.conversation_id,
        message=request.message,
        answer=result["answer"],
        agent={
            "name": "agente_react_rag",
            "type": "react",
            "status": "ready",
        },
        tools_used=result["tools_used"],
        sources=result.get("sources", []),
        metadata={
            "mode": "llm-react-tool-calling",
            "provider": result.get("provider"),
            "model": result.get("model"),
            "iterations": result.get("iterations"),
            "tools_used": result.get("tools_used", []),
            "tool_trace": result.get("tool_trace", []),
            "analyzer": result.get("analyzer"),
        },
        timestamp=utc_now(),
    )


# ============================================================
# ENDPOINT COMPATIBILIDAD / CHAT
# ============================================================


@router.post("/run/async", status_code=202, summary="Encolar ejecución ReAct en Celery")
async def run_agent_async(request: AgentRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.services.execution_manager import execution_manager
    request_id = generate_request_id()
    session_id = request.session_id.strip() if request.session_id else generate_session_id()
    run_id = execution_manager.create_run(
        session_id=session_id, conversation_id=request.conversation_id,
        message=request.message.strip(), metadata=request.metadata,
    )
    try:
        task_id = execution_manager.dispatch(run_id, {
            "message": request.message.strip(), "session_id": session_id,
            "conversation_id": request.conversation_id, "use_rag": request.use_rag,
            "use_web": request.use_web, "use_google": request.use_google,
            "max_iterations": request.max_iterations, "temperature": request.temperature,
        })
    except Exception as exc:
        execution_manager.mark_finished(run_id, "failed")
        raise HTTPException(status_code=503, detail=f"No se pudo encolar la ejecución: {exc}") from exc
    return {
        "success": True, "request_id": request_id, "run_id": run_id, "task_id": task_id,
        "status": "queued", "session_id": session_id,
        "events_url": f"/api/v1/agent/runs/{run_id}/events",
    }

@router.post(
    "/chat",
    response_model=AgentResponse,
    summary="Enviar mensaje al agente",
)
async def agent_chat(request: AgentRequest, db: Session = Depends(get_db)) -> AgentResponse:
    """
    Alias de /run para clientes frontend que prefieran
    una semántica de chat.
    """

    return await run_agent(request, db)


# ============================================================
# STATUS
# ============================================================

@router.get(
    "/status",
    response_model=AgentStatusResponse,
    summary="Estado del agente",
)
async def agent_status() -> AgentStatusResponse:

    from app.config import settings
    llm_configured = bool(
        (settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY)
        or (settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY)
        or settings.LLM_PROVIDER in {"ollama", "custom", "openai-compatible"}
    )
    return AgentStatusResponse(
        status="ready" if llm_configured else "configuration_required",
        agent="agente_react_rag",
        version="1.0.0",
        capabilities=[
            "react-tool-calling",
            "iterative-tool-loop",
            "rag",
            "memory",
            "web_search",
            "google_search",
            "document_search",
            "openai-compatible-llm",
        ],
        timestamp=utc_now(),
    )


# ============================================================
# HEALTH ESPECÍFICO DEL AGENTE
# ============================================================

@router.get(
    "/health",
    summary="Health check del agente",
)
async def agent_health() -> dict[str, Any]:

    return {
        "status": "ok",
        "service": "agent",
        "agent": "agente_react_rag",
        "timestamp": utc_now(),
    }


# ============================================================
# RESET DE SESIÓN
# ============================================================

@router.delete(
    "/session/{session_id}",
    summary="Eliminar sesión del agente",
)
async def delete_agent_session(session_id: str) -> dict[str, Any]:

    if not session_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id inválido.",
        )

    # --------------------------------------------------------
    # Posteriormente:
    #
    # await memory.delete(session_id)
    # await redis.delete(...)
    #
    # --------------------------------------------------------

    return {
        "success": True,
        "session_id": session_id,
        "message": "Sesión marcada para eliminación.",
        "timestamp": utc_now(),
    }

# ============================================================
# EXECUTION / CANCEL / REPLAY
# ============================================================

@router.get("/runs/{run_id}", summary="Consultar ejecución del agente")
async def get_agent_run(run_id: str) -> dict[str, Any]:
    from app.services.execution_manager import execution_manager, RunNotFound
    run = execution_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    return run


@router.get("/runs/{run_id}/events", summary="Recuperar eventos persistidos")
async def get_agent_events(run_id: str, after: int = 0, limit: int = 500) -> dict[str, Any]:
    from app.services.execution_manager import execution_manager
    run = execution_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    events = execution_manager.events_after(run_id, after=max(0, after))[:max(1, min(limit, 1000))]
    return {"run_id": run_id, "events": events, "last_sequence": events[-1]["sequence"] if events else after}


@router.post("/runs/{run_id}/cancel", summary="Cancelar ejecución del agente")
@router.delete("/runs/{run_id}", summary="Cancelar ejecución del agente")
async def cancel_agent_run(run_id: str) -> dict[str, Any]:
    from app.services.execution_manager import execution_manager, RunNotFound
    try:
        await execution_manager.cancel(run_id, reason="api_cancel")
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada") from exc
    return {"success": True, "run_id": run_id, "status": "cancelling", "timestamp": utc_now()}


# ============================================================
# WEBSOCKET STREAMING + RECONEXIÓN DEL AGENTE
# ============================================================

@router.websocket("/ws")
async def agent_websocket(websocket: WebSocket, db: Session = Depends(get_db)):
    """WebSocket durable: FastAPI coordina; Celery ejecuta; eventos se leen desde DB."""
    from app.services.execution_manager import execution_manager, RunNotFound

    await websocket.accept()
    active_run_id: str | None = None

    async def stream_run(run_id: str, after: int = 0):
        nonlocal active_run_id
        active_run_id = run_id
        idle_rounds = 0
        while True:
            events = execution_manager.events_after(run_id, after=after)
            if events:
                idle_rounds = 0
                for event in events:
                    seq = int(event.get("sequence", after))
                    if seq <= after:
                        continue
                    after = seq
                    await websocket.send_json(event)
                    if event.get("type") in {"done", "cancelled", "error"}:
                        return
            else:
                idle_rounds += 1
            state = execution_manager.get_run(run_id)
            if state and state.get("status") in {"completed", "cancelled", "failed"}:
                # Recupera cualquier evento final que haya sido confirmado después del último poll.
                tail = execution_manager.events_after(run_id, after=after)
                for event in tail:
                    after = int(event.get("sequence", after))
                    await websocket.send_json(event)
                return
            await asyncio.sleep(0.35 if idle_rounds < 10 else 1.0)

    try:
        while True:
            payload = await websocket.receive_json()
            mtype = payload.get("type", "start")

            if mtype == "ping":
                await websocket.send_json({"type": "pong", "timestamp": utc_now()})
                continue

            if mtype == "cancel":
                run_id = payload.get("run_id")
                if not run_id:
                    await websocket.send_json({"type": "error", "code": "RUN_ID_REQUIRED", "message": "run_id es obligatorio"})
                    continue
                try:
                    await execution_manager.cancel(run_id, reason="websocket_cancel")
                    await websocket.send_json({"type": "cancel_requested", "run_id": run_id})
                except RunNotFound:
                    await websocket.send_json({"type": "error", "code": "RUN_NOT_FOUND", "message": "Ejecución no encontrada", "run_id": run_id})
                continue

            if mtype == "resume":
                run_id = payload.get("run_id")
                after = int(payload.get("after", 0) or 0)
                if not run_id:
                    await websocket.send_json({"type": "error", "code": "RUN_ID_REQUIRED", "message": "run_id es obligatorio"})
                    continue
                try:
                    if not execution_manager.get_run(run_id):
                        raise RunNotFound(run_id)
                    await websocket.send_json({"type": "resumed", "run_id": run_id, "after": after})
                    await stream_run(run_id, after)
                    active_run_id = None
                except RunNotFound:
                    await websocket.send_json({"type": "error", "code": "RUN_NOT_FOUND", "message": "Ejecución no encontrada", "run_id": run_id})
                continue

            if mtype not in {"start", "chat", "message", "execute"}:
                await websocket.send_json({"type": "error", "code": "UNKNOWN_MESSAGE_TYPE", "message": f"Tipo no soportado: {mtype}"})
                continue

            request = AgentRequest.model_validate(payload)
            request_id = generate_request_id()
            session_id = request.session_id.strip() if request.session_id else generate_session_id()
            run_id = execution_manager.create_run(
                session_id=session_id,
                conversation_id=request.conversation_id,
                message=request.message.strip(),
                metadata=request.metadata,
            )
            task_payload = {
                "message": request.message.strip(), "session_id": session_id,
                "conversation_id": request.conversation_id, "use_rag": request.use_rag,
                "use_web": request.use_web, "use_google": request.use_google,
                "max_iterations": request.max_iterations, "temperature": request.temperature,
            }
            try:
                task_id = execution_manager.dispatch(run_id, task_payload)
            except Exception as exc:
                execution_manager.mark_finished(run_id, "failed")
                await websocket.send_json({"type": "error", "code": "DISPATCH_ERROR", "message": str(exc), "run_id": run_id})
                continue

            await websocket.send_json({"type": "accepted", "request_id": request_id, "session_id": session_id, "run_id": run_id, "task_id": task_id, "dispatcher": "celery"})
            await stream_run(run_id, 0)
            active_run_id = None

    except WebSocketDisconnect:
        if active_run_id:
            await execution_manager.disconnect(active_run_id)
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "code": "WS_ERROR", "message": str(exc)})
        except Exception:
            pass
        if active_run_id:
            await execution_manager.disconnect(active_run_id)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
