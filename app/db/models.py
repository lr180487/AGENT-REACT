from __future__ import annotations

import uuid
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # SQLite/dev fallback
    Vector = None


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    chats: Mapped[list["Chat"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Chat(Base):
    __tablename__ = "chats"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), default="Nuevo chat")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    provider: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(128))
    meta: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped[User | None] = relationship(back_populates="chats")
    messages: Mapped[list["Message"]] = relationship(back_populates="chat", cascade="all, delete-orphan", order_by="Message.created_at")
    memory: Mapped["ChatMemory | None"] = relationship(back_populates="chat", uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        return {"chat_id": self.id, "user_id": self.user_id, "title": self.title, "is_archived": self.is_archived,
                "provider": self.provider, "model": self.model,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
                "message_count": len(self.messages) if self.messages else 0}


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    tokens: Mapped[int | None] = mapped_column(Integer)
    meta: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    chat: Mapped[Chat] = relationship(back_populates="messages")

    def to_dict(self):
        return {"message_id": self.id, "chat_id": self.chat_id, "role": self.role, "content": self.content,
                "tokens": self.tokens, "meta": self.meta, "created_at": self.created_at.isoformat() if self.created_at else None}


class ChatMemory(Base):
    __tablename__ = "chat_memories"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), unique=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    vector_ids: Mapped[list | None] = mapped_column(JSON)
    extra: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    chat: Mapped[Chat] = relationship(back_populates="memory")

    def to_dict(self):
        return {"chat_id": self.chat_id, "summary": self.summary, "updated_at": self.updated_at.isoformat() if self.updated_at else None}


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    extension: Mapped[str] = mapped_column(String(16))
    content_type: Mapped[str | None] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(1000))
    size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    embedding_json: Mapped[list | None] = mapped_column(JSON)
    # On PostgreSQL this column is replaced/created by migration as vector(1536).
    embedding_vector = mapped_column(Vector(1536) if Vector else JSON, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    document: Mapped[Document] = relationship(back_populates="chunks")


Index("ix_document_chunks_document_index", DocumentChunk.document_id, DocumentChunk.chunk_index)
