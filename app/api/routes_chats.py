
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
=======

from __future__ import annotations

from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Query,
    status,
)

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
=======

router = APIRouter(
    prefix="/api/v1/chats",
    tags=["Chats"],
)


# ============================================================
# USER
# ============================================================

def get_user_id(
    x_user_id: Optional[str] = Header(
        None,
        alias="X-User-Id",
    )
):
    return x_user_id


# ============================================================
# SCHEMAS
# ============================================================

class ChatCreate(BaseModel):

    title: Optional[str] = Field(
        default="Nuevo chat",
        max_length=200,
    )

    provider: Optional[str] = None

    model: Optional[str] = None


class ChatPatch(BaseModel):

    title: Optional[str] = Field(
        default=None,
        max_length=200,
    )


class MessageCreate(BaseModel):

    role: str = Field(
        ...,
        pattern="^(user|assistant|system)$",
    )

    content: str = Field(
        ...,
        min_length=1,
    )

    tokens: Optional[int] = None

    meta: Optional[dict] = None


class MessagePatch(BaseModel):

    content: str = Field(
        ...,
        min_length=1,
    )


# ============================================================
# CHAT CREATE
# ============================================================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_chat(
    payload: ChatCreate,
    user_id=Depends(get_user_id),
    db: Session = Depends(get_db),
):

    chat = ChatService(db).create_chat(
        user_id=user_id,
        title=payload.title or "Nuevo chat",
        provider=payload.provider,
        model=payload.model,
    )

    return chat.to_dict()


# ============================================================
# CHAT LIST
# ============================================================

@router.get("")
def list_chats(
    q: Optional[str] = Query(None),
    limit: int = Query(
        50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
    include_archived: bool = False,
    user_id=Depends(get_user_id),
    db: Session = Depends(get_db),
):

    return ChatService(db).list_chats(
        user_id,
        q,
        limit,
        offset,
        include_archived,
    )


# ============================================================
# GET CHAT
# ============================================================

@router.get("/{chat_id}")
def get_chat(
    chat_id: str,
    user_id=Depends(get_user_id),
    db: Session = Depends(get_db),
):

    return ChatService(db).get_chat(
        chat_id,
        user_id,
    )


# ============================================================
# PATCH CHAT
# ============================================================

@router.patch("/{chat_id}")
def patch_chat(
    chat_id: str,
    payload: ChatPatch,
    user_id=Depends(get_user_id),
    db: Session = Depends(get_db),
):

    if payload.title:

        return ChatService(db).rename(
            chat_id,
            user_id,
            payload.title,
        )

    return ChatService(db).get_chat(
        chat_id,
        user_id,
    )


# ============================================================
# DELETE CHAT
# ============================================================

@router.delete(
    "/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_chat(
    chat_id: str,
    user_id=Depends(get_user_id),
    db: Session = Depends(get_db),
):

    ChatService(db).delete(
        chat_id,
        user_id,
    )

    return None


# ============================================================
# LIST MESSAGES
# ============================================================

@router.get("/{chat_id}/messages")
def list_messages(
    chat_id: str,
    limit: int = Query(
        30,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
    user_id=Depends(get_user_id),
    db: Session = Depends(get_db),
):

    result = MessageService(db).list_messages(
        chat_id,
        user_id,
        limit,
        offset,
    )

    return {
        **result,
        "chat_id": chat_id,
    }


# ============================================================
# CREATE MESSAGE
# ============================================================

@router.post(
    "/{chat_id}/messages",
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    chat_id: str,
    payload: MessageCreate,
    user_id=Depends(get_user_id),
    db: Session = Depends(get_db),
):

    return MessageService(db).add_message(
        chat_id,
        user_id,
        payload.role,
        payload.content,
        payload.tokens,
        payload.meta,
    )


# ============================================================
# EDIT MESSAGE
# ============================================================

@router.put("/{chat_id}/messages/{message_id}")
def update_message(
    chat_id: str,
    message_id: str,
    payload: MessagePatch,
    user_id=Depends(get_user_id),
    db: Session = Depends(get_db),
):

    return MessageService(db).edit_message(
        chat_id,
        user_id,
        message_id,
        payload.content,
    )


# ============================================================
# DELETE MESSAGE
# ============================================================

@router.delete(
    "/{chat_id}/messages/{message_id}",
)
def delete_message(
    chat_id: str,
    message_id: str,
    user_id=Depends(get_user_id),
    db: Session = Depends(get_db),
):

    return MessageService(db).delete_message(
        chat_id,
        user_id,
        message_id,
    )


# ============================================================
# ARCHIVE
# ============================================================

@router.post("/{chat_id}/archive")
def archive_chat(
    chat_id: str,
    user_id=Depends(get_user_id),
    db: Session = Depends(get_db),
):

    return ChatService(db).archive(
        chat_id,
        user_id,
    )


# ============================================================
# RESTORE
# ============================================================

@router.post("/{chat_id}/restore")
def restore_chat(
    chat_id: str,
    user_id=Depends(get_user_id),
    db: Session = Depends(get_db),
):

    return ChatService(db).restore(
        chat_id,
        user_id,
    )
