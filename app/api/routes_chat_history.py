"""
routes_chat_history.py — CRUD completo para historial de chat
Guarda, gestiona y edita cada chat + mensajes en PostgreSQL
+ scroll paginado por chat
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

# from app.db.database import get_db
# from app.db.models_chat import ChatSession, ChatMessage

router = APIRouter(prefix="/api/v1/chats", tags=["Chat History"])

# ---------- Pydantic ----------
class SessionCreate(BaseModel):
    title: Optional[str] = "Nuevo chat"
    provider: Optional[str] = None
    model: Optional[str] = None

class SessionUpdate(BaseModel):
    title: str = Field(..., max_length=200)

class MessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|bot|system)$")
    content: str
    tokens: Optional[int] = None
    meta: Optional[dict] = None

class MessageUpdate(BaseModel):
    content: str

# ---------- Mock DB (reemplazar por SQLAlchemy real) ----------
# Para demo sin DB, usamos memoria. En producción usar get_db.
_DB_SESSIONS: dict = {}
_DB_MESSAGES: dict = {}  # session_id -> list

def _mock_list_sessions():
    return sorted(_DB_SESSIONS.values(), key=lambda x: x["updated_at"], reverse=True)

# ---------- Endpoints ----------

@router.get("", summary="Listar historial de chats")
def list_chats(q: Optional[str] = None, limit: int = 50, offset: int = 0):
    # En prod: db.query(ChatSession).filter(...).offset(offset).limit(limit)
    sessions = _mock_list_sessions()
    if q:
        ql = q.lower()
        sessions = [s for s in sessions if ql in s["title"].lower()]
    total = len(sessions)
    return {"total": total, "items": sessions[offset: offset+limit]}

@router.post("", status_code=201, summary="Crear nuevo chat")
def create_chat(payload: SessionCreate):
    import uuid
    sid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    session = {
        "id": sid,
        "title": payload.title,
        "provider": payload.provider,
        "model": payload.model,
        "created_at": now,
        "updated_at": now,
        "message_count": 0
    }
    _DB_SESSIONS[sid] = session
    _DB_MESSAGES[sid] = []
    # En prod: db.add(ChatSession(...)); db.commit()
    return session

@router.get("/{session_id}", summary="Obtener chat con mensajes + scroll paginado")
def get_chat(session_id: str, limit: int = Query(50, ge=1, le=200), offset: int = 0):
    if session_id not in _DB_SESSIONS:
        raise HTTPException(404, "Chat no encontrado")
    msgs = _DB_MESSAGES.get(session_id, [])
    # scroll paginado: offset desde el final para cargar historial hacia arriba
    # frontend usa ?offset=0&limit=30 para últimos 30, luego offset+=30 al hacer scroll top
    total = len(msgs)
    # devolver slice paginado desde el final
    start = max(0, total - offset - limit)
    end = total - offset
    page = msgs[start:end]
    return {
        "session": _DB_SESSIONS[session_id],
        "messages": page,
        "total": total,
        "has_more": start > 0
    }

@router.put("/{session_id}", summary="Editar título del chat")
def update_chat(session_id: str, payload: SessionUpdate):
    if session_id not in _DB_SESSIONS:
        raise HTTPException(404, "Chat no encontrado")
    _DB_SESSIONS[session_id]["title"] = payload.title
    _DB_SESSIONS[session_id]["updated_at"] = datetime.utcnow().isoformat()
    return _DB_SESSIONS[session_id]

@router.delete("/{session_id}", status_code=204, summary="Eliminar chat completo")
def delete_chat(session_id: str):
    if session_id not in _DB_SESSIONS:
        raise HTTPException(404, "Chat no encontrado")
    del _DB_SESSIONS[session_id]
    _DB_MESSAGES.pop(session_id, None)
    return

@router.post("/{session_id}/messages", status_code=201, summary="Guardar mensaje")
def add_message(session_id: str, payload: MessageCreate):
    if session_id not in _DB_SESSIONS:
        raise HTTPException(404, "Chat no encontrado")
    import uuid
    mid = str(uuid.uuid4())
    msg = {
        "id": mid,
        "session_id": session_id,
        "role": payload.role,
        "content": payload.content,
        "tokens": payload.tokens,
        "meta": payload.meta,
        "created_at": datetime.utcnow().isoformat()
    }
    _DB_MESSAGES[session_id].append(msg)
    _DB_SESSIONS[session_id]["updated_at"] = datetime.utcnow().isoformat()
    _DB_SESSIONS[session_id]["message_count"] = len(_DB_MESSAGES[session_id])
    # auto-titular si es primer mensaje user
    if len(_DB_MESSAGES[session_id]) == 1 and payload.role == "user":
        _DB_SESSIONS[session_id]["title"] = payload.content[:40] + ("…" if len(payload.content) > 40 else "")
    return msg

@router.put("/{session_id}/messages/{message_id}", summary="Editar mensaje")
def edit_message(session_id: str, message_id: str, payload: MessageUpdate):
    msgs = _DB_MESSAGES.get(session_id)
    if not msgs:
        raise HTTPException(404, "Chat no encontrado")
    for m in msgs:
        if m["id"] == message_id:
            m["content"] = payload.content
            m["updated_at"] = datetime.utcnow().isoformat()
            return m
    raise HTTPException(404, "Mensaje no encontrado")

@router.delete("/{session_id}/messages/{message_id}", status_code=204, summary="Eliminar mensaje")
def delete_message(session_id: str, message_id: str):
    msgs = _DB_MESSAGES.get(session_id, [])
    before = len(msgs)
    _DB_MESSAGES[session_id] = [m for m in msgs if m["id"] != message_id]
    if len(_DB_MESSAGES[session_id]) == before:
        raise HTTPException(404, "Mensaje no encontrado")
    _DB_SESSIONS[session_id]["message_count"] = len(_DB_MESSAGES[session_id])
    return

# ---------- Integración con SQLAlchemy real (descomentar en prod) ----------
"""
@router.get("", ...)
def list_chats_real(db: Session = Depends(get_db), q=None, limit=50, offset=0):
    query = db.query(ChatSession)
    if q:
        query = query.filter(ChatSession.title.ilike(f"%{q}%"))
    total = query.count()
    items = query.order_by(ChatSession.updated_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": [s.to_dict() for s in items]}

# ... resto similar usando db.add / db.commit / db.delete
"""
