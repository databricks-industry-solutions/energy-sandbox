from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from ..agent import run_agent, proactive_scan

router = APIRouter()


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    model: Optional[str] = "databricks-claude-sonnet-4-6"


class ScanRequest(BaseModel):
    pass


@router.post("/agent/chat")
async def chat(req: ChatRequest):
    """Send a conversation to the Genie agent and get a response."""
    try:
        messages = [m.model_dump() for m in req.messages]
        result = await run_agent(messages, model=req.model)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/scan")
async def scan():
    """Trigger a proactive field-wide anomaly scan."""
    try:
        result = await proactive_scan()
        if result is None:
            return {"status": "nominal", "message": "All pumps within normal parameters"}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/quick-status")
async def quick_status():
    """Fast status check — runs agent with a brief field overview prompt."""
    try:
        result = await run_agent([
            {"role": "user", "content":
             "Give me a quick field status: check all pumps, identify any issues, "
             "and list the top 3 priorities right now. Keep it brief."}
        ])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
