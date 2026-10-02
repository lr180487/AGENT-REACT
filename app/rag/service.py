from __future__ import annotations
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import DocumentChunk
from app.rag.embeddings import EmbeddingService

class RAGService:
    def __init__(self, db: Session):
        self.db = db
        self.embeddings = EmbeddingService()

    async def search(self, query: str, top_k=5, document_id=None, min_score=0.0):
        qv = (await self.embeddings.embed([query]))[0]
        dialect = self.db.bind.dialect.name
        if dialect == "postgresql" and hasattr(DocumentChunk, "embedding_vector"):
            # pgvector cosine distance: 1 - distance = cosine similarity.
            stmt = text("""
                SELECT id, document_id, content, metadata_json,
                       1 - (embedding_vector <=> CAST(:embedding AS vector)) AS score
                FROM document_chunks
                WHERE embedding_vector IS NOT NULL
                  AND (:document_id IS NULL OR document_id = :document_id)
                ORDER BY embedding_vector <=> CAST(:embedding AS vector)
                LIMIT :top_k
            """)
            rows = self.db.execute(stmt, {"embedding": str(qv), "document_id": document_id, "top_k": top_k}).mappings().all()
            return [dict(r) for r in rows if float(r["score"]) >= min_score]

        query = self.db.query(DocumentChunk).filter(DocumentChunk.embedding_json.isnot(None))
        if document_id: query = query.filter(DocumentChunk.document_id == document_id)
        scored = []
        for chunk in query.all():
            score = self.embeddings.cosine(qv, chunk.embedding_json)
            if score >= min_score:
                scored.append({"id": chunk.id, "document_id": chunk.document_id, "content": chunk.content,
                               "metadata_json": chunk.metadata_json or {}, "score": score})
        return sorted(scored, key=lambda x: x["score"], reverse=True)[:top_k]
