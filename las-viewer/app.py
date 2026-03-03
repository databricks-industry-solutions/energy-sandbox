import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.db import db
from server.schema import CREATE_SCHEMA_SQL, seed_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await db.get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(CREATE_SCHEMA_SQL)
            await seed_data(conn)
        print("LAS Viewer DB initialised.")
    else:
        print("Running without Lakebase (demo mode).")
    yield
    if db._pool:
        await db._pool.close()


app = FastAPI(
    title="LAS Viewer — Powered by Databricks",
    version="1.0.0",
    lifespan=lifespan,
)

from server.routes.wells   import router as wells_router
from server.routes.logs    import router as logs_router
from server.routes.qc      import router as qc_router
from server.routes.recipes import router as recipes_router
from server.routes.advisor import router as advisor_router

app.include_router(wells_router,   prefix="/api")
app.include_router(logs_router,    prefix="/api")
app.include_router(qc_router,      prefix="/api")
app.include_router(recipes_router, prefix="/api")
app.include_router(advisor_router, prefix="/api")

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
        return {"status": "ok", "app": "LAS Viewer"}
