from __future__ import annotations
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.analyzer_service import AnalyzerService
from app.services.processor_service import ProcessorService
from app.services.response_service import ResponseService

router = APIRouter(prefix="/api/v1/analyzer", tags=["Analyzer → Processor → Response"])
class AnalyzeRequest(BaseModel): text: str = Field(..., min_length=1); chat_id: Optional[str]=None; history: Optional[List[Dict[str, Any]]]=None
class ProcessorRequest(BaseModel): query: str = Field(..., min_length=1); plan: List[Dict[str, Any]]; chat_id: Optional[str]=None
class ExecuteRequest(BaseModel): text: str = Field(..., min_length=1); chat_id: Optional[str]=None; history: Optional[List[Dict[str, Any]]]=None

@router.post("/analyze")
async def analyze(req: AnalyzeRequest): return AnalyzerService().analyze(req.text, req.chat_id, req.history or [])
@router.post("/process")
async def process_endpoint(req: ProcessorRequest, db: Session=Depends(get_db)): return await ProcessorService(db).process(req.query, req.plan, req.chat_id)
@router.post("/execute")
async def execute(req: ExecuteRequest, db: Session=Depends(get_db)):
    analyzer = AnalyzerService().analyze(req.text, req.chat_id, req.history or [])
    processor = await ProcessorService(db).process(req.text, analyzer["plan"], req.chat_id)
    return ResponseService().build(req.text, analyzer, processor)
