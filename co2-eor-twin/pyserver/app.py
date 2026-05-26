"""FastAPI sidecar for the CO2-EOR Digital Twin.

Runs alongside the Express twin server (Node, port 3001). This sidecar only
exposes the AI surface:

  POST /api/genie/ask{,_stream}
  GET  /api/genie/space
  POST /api/supervisor/decide
  GET  /api/supervisor/info
  GET  /api/supervisor/last_decision

The Express server proxies these paths to localhost:8001 so the React UI
sees a single /api origin.
"""
from __future__ import annotations

from fastapi import FastAPI

from pyserver.routes.genie import router as genie_router
from pyserver.routes.supervisor import router as supervisor_router


app = FastAPI(
    title="CO2-EOR Twin — AI Sidecar",
    version="0.1.0",
    description="Genie + Supervisor for the CO2-EOR Digital Twin.",
)

app.include_router(genie_router, prefix="/api")
app.include_router(supervisor_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "co2-eor-twin-ai-sidecar"}
