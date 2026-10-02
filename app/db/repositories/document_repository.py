from sqlalchemy.orm import Session
from app.db.models import Document, DocumentChunk

class DocumentRepository:
    def __init__(self, db: Session): self.db = db
    def get(self, document_id): return self.db.query(Document).filter(Document.id == document_id).first()
    def list(self, limit=50): return self.db.query(Document).order_by(Document.created_at.desc()).limit(limit).all()
    def add(self, document): self.db.add(document); self.db.commit(); self.db.refresh(document); return document
    def replace_chunks(self, document_id, chunks):
        self.db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete(synchronize_session=False)
        self.db.add_all(chunks); self.db.commit()
    def search(self, query):
        q = f"%{query}%"
        return self.db.query(DocumentChunk).filter(DocumentChunk.content.ilike(q)).limit(20).all()
