from __future__ import annotations
import asyncio
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.rag.service import RAGService
from app.tools.web_search import WebSearchTool
from app.db.repositories.document_repository import DocumentRepository

class ProcessorService:
    """Orquestador de herramientas reales. No genera datos ficticios."""
    def __init__(self, db: Session):
        self.db = db
        self.rag_service = RAGService(db)
        self.document_repo = DocumentRepository(db)
        self.web = WebSearchTool()

    async def web_search(self, query: str):
        return await self.web.run(query)

    async def rag(self, query: str, chat_id: Optional[str] = None, top_k: int = 5):
        rows = await self.rag_service.search(query, top_k=top_k)
        return {"tool": "rag", "query": query, "store": self.db.bind.dialect.name,
                "chunks": [{"id": r["id"], "document_id": r["document_id"], "text": r["content"],
                            "score": float(r["score"]), "metadata": r.get("metadata_json") or {}} for r in rows],
                "filters": {"chat_id": chat_id}}

    async def database(self, query: str, chat_id: Optional[str] = None):
        rows = self.document_repo.search(query)
        return {"tool": "database", "query": query, "rows": [
            {"id": r.id, "document_id": r.document_id, "content": r.content} for r in rows
        ]}

    async def documents(self, query: str):
        docs = self.document_repo.list(20)
        q = query.lower()
        matches = [d for d in docs if q in d.original_filename.lower()]
        return {"tool": "documents", "query": query, "documents": [
            {"id": d.id, "filename": d.original_filename, "status": d.status, "chunks": len(d.chunks)} for d in matches
        ]}

    async def external_apis(self, query: str):
        return {"tool": "external_apis", "available": False,
                "error": "No hay un conector externo configurado. Se evita una llamada arbitraria/SSRF."}

    async def notifications(self, payload: dict[str, Any]):
        return {"tool": "notifications", "available": False,
                "message": "Las notificaciones deben dispararse desde un worker/canal configurado."}

    async def workflows(self, plan: list[dict]):
        return {"tool": "workflows", "available": False,
                "message": "No hay workflow engine configurado."}

    async def process(self, query: str, plan: list[dict], chat_id: Optional[str] = None):
        tasks = []
        for step in plan:
            tool = step.get("tool")
            if tool == "web_search": tasks.append(self.web_search(query))
            elif tool == "rag": tasks.append(self.rag(query, chat_id))
            elif tool == "database": tasks.append(self.database(query, chat_id))
            elif tool == "documents": tasks.append(self.documents(query))
            elif tool == "external_apis": tasks.append(self.external_apis(query))
        results = await asyncio.gather(*tasks) if tasks else []
        return {"tri_result": {"resultados": results, "fuentes": [r.get("tool") for r in results],
                                "total_items": sum(len(r.get("results", [])) + len(r.get("chunks", [])) + len(r.get("rows", [])) for r in results)},
                "resultados": results, "next": "PROCESSOR RESULT"}
