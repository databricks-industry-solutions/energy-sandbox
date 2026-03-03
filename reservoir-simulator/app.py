import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.db import db
from server.schema import CREATE_SCHEMA_SQL, seed_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_schema(CREATE_SCHEMA_SQL)
    await seed_data()
    print("Res Sim V2 — Digital Twin DB initialised (SQLite).")
    yield


app = FastAPI(
    title="Res Sim V2 — Reservoir & Operations Digital Twin",
    version="2.0.0",
    lifespan=lifespan,
)

from server.routes.scenarios import router as scenarios_router
from server.routes.simulate import router as simulate_router
from server.routes.results import router as results_router
from server.routes.economics import router as economics_router
from server.routes.agent import router as agent_router
from server.routes.operations import router as operations_router
from server.routes.costs import router as costs_router
from server.routes.delta_sharing import router as delta_sharing_router
from server.routes.compare import router as compare_router

app.include_router(scenarios_router, prefix="/api")
app.include_router(simulate_router, prefix="/api")
app.include_router(simulate_router)  # WebSocket at root /ws/simulate/{run_id}
app.include_router(results_router, prefix="/api")
app.include_router(economics_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(operations_router, prefix="/api")
app.include_router(costs_router, prefix="/api")
app.include_router(delta_sharing_router, prefix="/api")
app.include_router(compare_router, prefix="/api")

# Serve React SPA
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    assets = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets):
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(os.path.join(frontend_dist, "index.html"))
else:
    @app.get("/")
    async def root():
        return {"status": "ok", "app": "Res Sim V2 — Digital Twin"}
