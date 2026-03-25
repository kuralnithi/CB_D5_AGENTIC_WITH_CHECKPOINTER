from fastapi import APIRouter, HTTPException
import asyncio
from app.schemas.finance import AnalyzeRequest, AnalyzeResponse
from app.services.agent_service import analyze_stock

router = APIRouter()

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_endpoint(request: AnalyzeRequest):
    try:
        # Use our async service with support for thread-id (PostgreSQL checkpointing)
        result = await analyze_stock(request.query, request.thread_id)
        return AnalyzeResponse(result=result)
    except Exception as e:
        # Production tip: Log the exception details for debugging.
        raise HTTPException(status_code=500, detail=str(e))

