from fastapi import APIRouter, HTTPException, Depends
import asyncio
from app.schemas.finance import AnalyzeRequest, AnalyzeResponse
from app.services.agent_service import analyze_stock
from app.core.security import get_current_user
from typing import Dict, Any

router = APIRouter()

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_endpoint(
    request: AnalyzeRequest, 
    user_payload: Dict[str, Any] = Depends(get_current_user)
):
    try:
        # Security: Ensure the user is not trying to hijack another user's thread
        user_id = user_payload.get("sub")
        if not request.thread_id.startswith(f"user_{user_id}"):
            raise HTTPException(status_code=403, detail="Unauthorized thread access")

        # Use our async service with support for thread-id (PostgreSQL checkpointing)
        result = await analyze_stock(request.query, request.thread_id, request.model_id)
        return AnalyzeResponse(result=result)
    except HTTPException as e:
        raise e
    except Exception as e:
        # Production tip: Log the exception details for debugging.
        raise HTTPException(status_code=500, detail=str(e))

