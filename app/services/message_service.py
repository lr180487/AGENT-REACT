# message_service.py — Mensajes + flujo guardar USER / ASSISTANT
from sqlalchemy.orm import Session
from typing import Optional

from app.db.repositories.chat_repository import ChatRepository
from app.db.repositories.message_repository import MessageRepository
from app.db.repositories.memory_repository import MemoryRepository

class MessageService:
    def __init__(self, db: Session):
        self.db = db
        self.chats = ChatRepository(db)
        self.msgs = MessageRepository(db)
        self.memory = MemoryRepository(db)

    def list_messages(self, chat_id: str, user_id: Optional[str], limit=50, offset=0):
        self.chats.validate_owner(chat_id, user_id)
        total, items = self.msgs.list(chat_id, limit, offset)
        has_more = (offset + limit) < total
        return {"total": total, "messages": [m.to_dict() for m in items], "has_more": has_more}

    def add_message(self, chat_id: str, user_id: Optional[str], role: str, content: str, tokens=None, meta=None):
        self.chats.validate_owner(chat_id, user_id)
        msg = self.msgs.create(chat_id, role, content, tokens, meta)
        # actualizar memoria simple: append resumen
        mem = self.memory.get_by_chat(chat_id)
        summary = (mem.summary or "") + f"\n{role}: {content[:120]}"
        self.memory.upsert(chat_id, summary=summary[-2000:])
        return msg.to_dict()

    def edit_message(self, chat_id: str, user_id: Optional[str], message_id: str, content: str):
        self.chats.validate_owner(chat_id, user_id)
        msg = self.msgs.get(message_id)
        if not msg or msg.chat_id != chat_id:
            from fastapi import HTTPException
            raise HTTPException(404, "Mensaje no encontrado en este chat")
        return self.msgs.update(message_id, content).to_dict()

    def delete_message(self, chat_id: str, user_id: Optional[str], message_id: str):
        self.chats.validate_owner(chat_id, user_id)
        msg = self.msgs.get(message_id)
        if not msg or msg.chat_id != chat_id:
            from fastapi import HTTPException
            raise HTTPException(404, "Mensaje no encontrado")
        self.msgs.delete(message_id)
        return {"deleted": message_id}
