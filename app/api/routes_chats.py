from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.chat_service import ChatService
from app.services.message_service import MessageService

router = APIRouter(prefix="/api/v1/chats", tags=["Chats"])

def get_user_id(x_user_id: Optional[str] = Header(None, alias="X-User-Id")): return x_user_id

class ChatCreate(BaseModel):
    title: Optional[str] = Field("Nuevo chat", max_length=200)
    provider: Optional[str] = None
    model: Optional[str] = None
class ChatPatch(BaseModel): title: Optional[str] = Field(None, max_length=200)
class MessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)
    tokens: Optional[int] = None
    meta: Optional[dict] = None

@router.post("", status_code=status.HTTP_201_CREATED)
def create_chat(p: ChatCreate, user_id=Depends(get_user_id), db: Session=Depends(get_db)):
    return ChatService(db).create_chat(user_id, p.title or "Nuevo chat", p.provider, p.model).to_dict()
@router.get("")
def list_chats(q: Optional[str]=Query(None), limit: int=Query(50, ge=1, le=100), offset: int=0, include_archived: bool=False, user_id=Depends(get_user_id), db: Session=Depends(get_db)):
    return ChatService(db).list_chats(user_id, q, limit, offset, include_archived)
@router.get("/{chat_id}")
def get_chat(chat_id: str, user_id=Depends(get_user_id), db: Session=Depends(get_db)): return ChatService(db).get_chat(chat_id, user_id)
@router.patch("/{chat_id}")
def patch_chat(chat_id: str, p: ChatPatch, user_id=Depends(get_user_id), db: Session=Depends(get_db)):
    return ChatService(db).rename(chat_id, user_id, p.title) if p.title else ChatService(db).get_chat(chat_id, user_id)["chat"]
@router.delete("/{chat_id}", status_code=204)
def delete_chat(chat_id: str, user_id=Depends(get_user_id), db: Session=Depends(get_db)): ChatService(db).delete(chat_id, user_id)
@router.get("/{chat_id}/messages")
def list_messages(chat_id: str, limit: int=Query(30, ge=1, le=100), offset: int=0, user_id=Depends(get_user_id), db: Session=Depends(get_db)):
    return MessageService(db).list_messages(chat_id, user_id, limit, offset) | {"chat_id": chat_id}
@router.post("/{chat_id}/messages", status_code=201)
def create_message(chat_id: str, p: MessageCreate, user_id=Depends(get_user_id), db: Session=Depends(get_db)):
    return MessageService(db).add_message(chat_id, user_id, p.role, p.content, p.tokens, p.meta)
@router.post("/{chat_id}/archive")
def archive_chat(chat_id: str, user_id=Depends(get_user_id), db: Session=Depends(get_db)): return ChatService(db).archive(chat_id, user_id)
@router.post("/{chat_id}/restore")
def restore_chat(chat_id: str, user_id=Depends(get_user_id), db: Session=Depends(get_db)): return ChatService(db).restore(chat_id, user_id)
