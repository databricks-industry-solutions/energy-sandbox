import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.gzip import GZipMiddleware

from server.db import db
from server.schema import CREATE_SCHEMA_SQL, seed_data, seed_osdu_wells, seed_wti_prices


async def _background_seed():
    """OSDU + WTI seeding can be slow (cold warehouse, external HTTP). Run after
    startup so the app comes up immediately and the UI is responsive even if
    these fail or take a while."""
    pool = await db.get_pool()
    if not pool:
        return
    try:
        async with pool.acquire() as conn:
            try:
                await asyncio.wait_for(seed_osdu_wells(conn), timeout=120)
                print("OSDU seed complete.")
            except asyncio.TimeoutError:
                print("OSDU seed timed out after 120s — continuing without it.")
            except Exception as e:
                print(f"OSDU seed failed: {e}")
            try:
                await asyncio.wait_for(seed_wti_prices(conn), timeout=60)
                print("WTI seed complete.")
            except asyncio.TimeoutError:
                print("WTI seed timed out after 60s — continuing without it.")
            except Exception as e:
                print(f"WTI seed failed: {e}")
    except Exception as e:
        print(f"Background seed crashed: {e}")


async def _warm_caches():
    """Pre-warm hot endpoints so the first user click on each tab is instant.
    Hits the in-process caches in wells.py / economics.py / governance.py.
    After the initial warm, re-fetches every 4 minutes so the cache never goes
    cold during a long demo session (governance TTL is 10 min, wells 60s,
    economics 2 min)."""
    import urllib.request
    base = "http://127.0.0.1:8000"
    urls = [
        "/api/wells",
        "/api/wells/alerts",
        "/api/economics/summary",
        "/api/economics/prices",
        "/api/governance/legal_tags",
        "/api/governance/audit",
        "/api/governance/co2",
        "/api/governance/personas",
        "/api/governance/uc_chain",
    ]

    async def hit_all(initial: bool = False):
        for u in urls:
            try:
                await asyncio.to_thread(urllib.request.urlopen, f"{base}{u}", None, 45)
            except Exception as e:
                if initial:
                    print(f"warm {u}: {type(e).__name__}")
        if initial:
            print("Cache warmup complete.")

    # Wait a moment so uvicorn is actually serving
    await asyncio.sleep(4)
    await hit_all(initial=True)
    # Keep warm forever
    while True:
        await asyncio.sleep(240)  # 4 min
        try:
            await hit_all()
        except Exception as e:
            print(f"periodic warmup error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await db.get_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(CREATE_SCHEMA_SQL)
            await seed_data(conn)
        print("Subsurface Intelligence DB initialised (LAS seeded). OSDU + WTI seeding running in background.")
        asyncio.create_task(_background_seed())
        asyncio.create_task(_warm_caches())
    else:
        print("Running without Lakebase (demo mode).")
    yield
    if db._pool:
        await db._pool.close()


app = FastAPI(
    title="Subsurface Intelligence — Powered by Databricks",
    version="1.0.0",
    lifespan=lifespan,
)

# Compress JSON responses larger than ~1 KB. Major win for log payloads and
# governance/economics aggregations: 5-10x smaller wire transfers.
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)

from server.routes.wells      import router as wells_router
from server.routes.logs       import router as logs_router
from server.routes.economics  import router as economics_router
from server.routes.governance import router as governance_router
from server.routes.genie      import router as genie_router
from server.routes.subsurface import router as subsurface_router
from server.routes.supervisor import router as supervisor_router

app.include_router(wells_router,      prefix="/api")
app.include_router(logs_router,       prefix="/api")
app.include_router(economics_router,  prefix="/api")
app.include_router(governance_router, prefix="/api")
app.include_router(genie_router,      prefix="/api")
app.include_router(subsurface_router, prefix="/api")
app.include_router(supervisor_router, prefix="/api")

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
