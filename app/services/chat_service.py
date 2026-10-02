# chat_service.py — Lógica de negocio para chats
from typing import Optional
from sqlalchemy.orm import Session
from app.db.repositories.chat_repository import ChatRepository
from app.db.repositories.memory_repository import MemoryRepository

class ChatService:
    def __init__(self, db: Session):
        self.db = db
        self.chats = ChatRepository(db)
        self.memory = MemoryRepository(db)

    def create_chat(self, user_id: Optional[str], title: str = "Nuevo chat", provider=None, model=None):
        chat = self.chats.create(user_id, title, provider, model)
        # crear memoria vacía
        self.memory.upsert(chat.id, summary="", vector_ids=[])
        return chat

    def list_chats(self, user_id: Optional[str], q=None, limit=50, offset=0, include_archived=False):
        total, items = self.chats.list_by_user(user_id, include_archived, q, limit, offset)
        return {"total": total, "items": [c.to_dict() for c in items]}

    def get_chat(self, chat_id: str, user_id: Optional[str]):
        chat = self.chats.validate_owner(chat_id, user_id)
        mem = self.memory.get_by_chat(chat_id)
        return {"chat": chat.to_dict(), "memory": mem.to_dict() if mem else None}

    def rename(self, chat_id: str, user_id: Optional[str], title: str):
        self.chats.validate_owner(chat_id, user_id)
        return self.chats.update_title(chat_id, title).to_dict()

    def archive(self, chat_id: str, user_id: Optional[str]):
        self.chats.validate_owner(chat_id, user_id)
        return self.chats.archive(chat_id).to_dict()

    def restore(self, chat_id: str, user_id: Optional[str]):
        self.chats.validate_owner(chat_id, user_id)
        return self.chats.restore(chat_id).to_dict()

    def delete(self, chat_id: str, user_id: Optional[str]):
        self.chats.validate_owner(chat_id, user_id)
        self.chats.delete(chat_id)
        return {"deleted": chat_id}
