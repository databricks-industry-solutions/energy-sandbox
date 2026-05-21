"""Real Lakebase Postgres client — used only for write-heavy persistence
(journal, alerts, persona state). Reads for the main scene still come from
DuckDB. Env vars auto-injected by the Databricks Apps `database` resource
binding; the app SP gets a PG role automatically."""
from __future__ import annotations

import asyncio
import os
from typing import Any

import asyncpg


_pool: asyncpg.Pool | None = None
_lock = asyncio.Lock()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


SCHEMA = """
CREATE SCHEMA IF NOT EXISTS dcc;

CREATE TABLE IF NOT EXISTS dcc.journal (
    entry_id     BIGSERIAL PRIMARY KEY,
    well_id      VARCHAR(64),
    author       VARCHAR(128),
    depth_md     DOUBLE PRECISION,
    note         TEXT,
    ai_summary   TEXT,
    entered_ts   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_journal_well ON dcc.journal(well_id, entered_ts DESC);

CREATE TABLE IF NOT EXISTS dcc.alerts (
    alert_id     BIGSERIAL PRIMARY KEY,
    well_id      VARCHAR(64),
    severity     VARCHAR(16),
    category     VARCHAR(32),
    title        VARCHAR(128),
    detail       TEXT,
    depth_md     DOUBLE PRECISION,
    ack_by       VARCHAR(128),
    ack_ts       TIMESTAMPTZ,
    raised_ts    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_well ON dcc.alerts(well_id);
"""


async def get_pool() -> asyncpg.Pool | None:
    global _pool
    if _pool is not None:
        return _pool
    host = _env("PGHOST")
    if not host:
        return None
    async with _lock:
        if _pool is not None:
            return _pool
        try:
            port = int(_env("PGPORT", "5432"))
            db = _env("PGDATABASE", "drilling_cc")
            user = _env("PGUSER")
            password = _env("PGPASSWORD") or user
            # If PGUSER is a JWT (long, two dots), the role is the `sub` claim
            role = user
            if user and len(user) > 100 and user.count(".") == 2:
                import base64
                import json as _json
                try:
                    payload = user.split(".")[1]
                    payload += "=" * (-len(payload) % 4)
                    claims = _json.loads(base64.b64decode(payload))
                    role = claims.get("sub") or user
                    # When PGUSER is the JWT, also use it as password if PGPASSWORD wasn't set
                    if password == user:
                        password = user
                except Exception:
                    pass
            print(f"Lakebase connect host={host} port={port} db={db} role={role[:40]}")
            _pool = await asyncpg.create_pool(
                host=host, port=port, database=db,
                user=role, password=password,
                ssl="require", min_size=1, max_size=5,
                command_timeout=20,
            )
            async with _pool.acquire() as conn:
                await conn.execute(SCHEMA)
            print("Lakebase schema ready.")
        except Exception as e:
            print(f"Lakebase connect failed: {e}")
            _pool = None
    return _pool


async def fetch(sql: str, *args) -> list[dict[str, Any]]:
    pool = await get_pool()
    if not pool:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"Lakebase fetch error: {e}")
        return []


async def execute(sql: str, *args) -> None:
    pool = await get_pool()
    if not pool:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(sql, *args)
    except Exception as e:
        print(f"Lakebase execute error: {e}")
