from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.rag.service import RAGService
from app.config import settings

router=APIRouter(prefix="/rag",tags=["RAG"])
class RAGSearchRequest(BaseModel): query:str=Field(...,min_length=1); top_k:int=Field(5,ge=1,le=50); document_id:str|None=None; session_id:str|None=None; min_score:float=Field(0,ge=0,le=1)
class RAGContextRequest(RAGSearchRequest): max_context_chars:int=Field(12000,ge=1000,le=100000)

def now(): return datetime.now(timezone.utc).isoformat()
@router.post("/search")
async def search(req:RAGSearchRequest,db:Session=Depends(get_db)):
    rows=await RAGService(db).search(req.query,req.top_k,req.document_id,req.min_score)
    return {"success":True,"query":req.query,"results":[{"chunk_id":r["id"],"document_id":r["document_id"],"content":r["content"],"score":float(r["score"]),"metadata":r.get("metadata_json") or {}} for r in rows],"total":len(rows),"top_k":req.top_k,"retrieval_method":"pgvector" if db.bind.dialect.name=="postgresql" else "local-vector-fallback","timestamp":now()}
@router.post("/context")
async def context(req:RAGContextRequest,db:Session=Depends(get_db)):
    rows=await RAGService(db).search(req.query,req.top_k,req.document_id,req.min_score); text="\n\n".join(f"[{i+1}] {r['content']}" for i,r in enumerate(rows)); trunc=len(text)>req.max_context_chars
    return {"success":True,"query":req.query,"context":text[:req.max_context_chars],"sources":rows,"total_sources":len(rows),"truncated":trunc,"timestamp":now()}
@router.get("/status")
def status(db:Session=Depends(get_db)):
    from app.db.models import Document,DocumentChunk
    return {"status":"ok","vector_store":"pgvector" if db.bind.dialect.name=="postgresql" else "sqlite/local","embedding_model":settings.EMBEDDING_MODEL,"embedding_dimension":settings.EMBEDDING_DIM,"indexed_documents":db.query(Document).count(),"indexed_chunks":db.query(DocumentChunk).count(),"timestamp":now()}
