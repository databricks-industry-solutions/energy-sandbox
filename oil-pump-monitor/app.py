import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.db import db
from server.schema import CREATE_SCHEMA_SQL, INSERT_DEMO_PUMPS_SQL
from server.simulator import PumpSimulator

simulator: PumpSimulator = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global simulator
    pool = await db.get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(CREATE_SCHEMA_SQL)
            await conn.execute(INSERT_DEMO_PUMPS_SQL)
        print("Database schema initialized")
        asyncio.create_task(db.start_refresh_loop())
        simulator = PumpSimulator(db, interval_seconds=2.0)
        await simulator.start()
    else:
        print("Running in demo mode (no Lakebase connection)")

    yield

    if simulator:
        await simulator.stop()
    if db._pool:
        await db._pool.close()

app = FastAPI(
    title="Oil Pump Vibration Monitor",
    description="Real-time vibration monitoring for Bakken Formation fracking pumps, North Dakota",
    version="1.0.0",
    lifespan=lifespan,
)

from server.routes.pumps import router as pumps_router
from server.routes.agent import router as agent_router
app.include_router(pumps_router, prefix="/api")
app.include_router(agent_router, prefix="/api")

# Serve React frontend
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dir):
    assets_dir = os.path.join(frontend_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index_path = os.path.join(frontend_dir, "index.html")
        return FileResponse(index_path)
else:
    @app.get("/")
    async def root():
        return {"status": "ok", "message": "Oil Pump Vibration Monitor API"}
