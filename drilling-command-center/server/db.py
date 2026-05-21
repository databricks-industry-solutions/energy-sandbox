"""In-process DuckDB backend that mimics the asyncpg surface the routes expect.

Routes call `db.fetch / fetchrow / execute / executemany` with Postgres-style
$N placeholders and `las.<table>` references. We rewrite those to DuckDB's
syntax on the fly. No Lakebase, no external Postgres — everything runs in
the app's memory and seeds on startup.

Async is faked via `asyncio.to_thread` so the existing FastAPI handlers don't
need to change.
"""
from __future__ import annotations

import asyncio
import os
import re
import threading
from typing import Any, Iterable

import duckdb


_CAST_NUMERIC_RE = re.compile(r"::\s*numeric", re.IGNORECASE)
_NOW_RE = re.compile(r"\bNOW\s*\(\s*\)", re.IGNORECASE)
_ON_CONFLICT_INDEX_RE = re.compile(r"ON CONFLICT \(([^)]+)\)", re.IGNORECASE)


def _rewrite_sql(sql: str) -> str:
    """Translate Postgres dialect to DuckDB-compatible SQL. DuckDB supports
    `schema.table` natively, so we leave `las.` prefixes intact."""
    s = _CAST_NUMERIC_RE.sub("", sql)
    s = _NOW_RE.sub("CURRENT_TIMESTAMP", s)
    return s


def _args(params: Iterable[Any]) -> list:
    out = []
    for p in params:
        # DuckDB's python binding handles datetime/date/None/str/numbers natively
        out.append(p)
    return out


class _DuckStore:
    """Wrapper around a DuckDB connection. Reads use per-call cursors so they
    can run concurrently from FastAPI worker threads (DuckDB supports concurrent
    cursors on a single connection for SELECTs). Writes still serialize through
    a lock so the seed/journal path stays correct."""

    def __init__(self) -> None:
        path = os.environ.get("DCC_DB_PATH", ":memory:")
        self._conn = duckdb.connect(path)
        self._write_lock = threading.Lock()

    def execute(self, sql: str, params: tuple = ()) -> None:
        sql = _rewrite_sql(sql)
        with self._write_lock:
            self._conn.execute(sql, _args(params))

    def executemany(self, sql: str, seq_of_params) -> None:
        sql = _rewrite_sql(sql)
        with self._write_lock:
            self._conn.executemany(sql, [_args(p) for p in seq_of_params])

    def fetch(self, sql: str, params: tuple = ()) -> list[dict]:
        sql = _rewrite_sql(sql)
        # Per-call cursor — no global lock for reads. Multiple FastAPI workers
        # can hit DuckDB simultaneously without queueing.
        cur = self._conn.cursor()
        cur.execute(sql, _args(params))
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]

    def fetchrow(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self.fetch(sql, params)
        return rows[0] if rows else None

    def executescript(self, sql: str) -> None:
        sql = _rewrite_sql(sql)
        with self._write_lock:
            for stmt in _split_ddl(sql):
                if stmt.strip():
                    self._conn.execute(stmt)


def _split_ddl(script: str) -> list[str]:
    """Split a multi-statement DDL script by semicolons at top level."""
    parts, buf, in_str = [], [], False
    for ch in script:
        if ch == "'":
            in_str = not in_str
        if ch == ";" and not in_str:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts


_store: _DuckStore | None = None


def _get_store() -> _DuckStore:
    global _store
    if _store is None:
        _store = _DuckStore()
    return _store


# ─────────── Async surface the routes expect ───────────────────────────────

async def get_pool():
    """Return a truthy value so callers can distinguish 'has DB' from None."""
    return _get_store()


async def fetch(sql: str, *args) -> list[dict]:
    store = _get_store()
    try:
        return await asyncio.to_thread(store.fetch, sql, tuple(args))
    except Exception as e:
        print(f"fetch error: {e}\nSQL: {sql[:200]}\nargs: {args}")
        return []


async def fetchrow(sql: str, *args) -> dict | None:
    store = _get_store()
    try:
        return await asyncio.to_thread(store.fetchrow, sql, tuple(args))
    except Exception as e:
        print(f"fetchrow error: {e}\nSQL: {sql[:200]}\nargs: {args}")
        return None


async def execute(sql: str, *args) -> None:
    store = _get_store()
    try:
        await asyncio.to_thread(store.execute, sql, tuple(args))
    except Exception as e:
        print(f"execute error: {e}\nSQL: {sql[:200]}\nargs: {args}")


async def executemany(sql: str, args_list) -> None:
    store = _get_store()
    try:
        await asyncio.to_thread(store.executemany, sql, list(args_list))
    except Exception as e:
        print(f"executemany error: {e}\nSQL: {sql[:200]}")


# Connection-context shim so `async with pool.acquire() as conn: await conn.execute(...)`
# continues to work.


class _ConnShim:
    def __init__(self, store: _DuckStore) -> None:
        self._store = store

    async def execute(self, sql: str, *args) -> None:
        # Route handlers sometimes pass full multi-statement DDL scripts here.
        if ";" in sql and not args:
            await asyncio.to_thread(self._store.executescript, sql)
        else:
            await asyncio.to_thread(self._store.execute, sql, tuple(args))

    async def executemany(self, sql: str, args_list) -> None:
        await asyncio.to_thread(self._store.executemany, sql, list(args_list))

    async def fetch(self, sql: str, *args) -> list[dict]:
        return await asyncio.to_thread(self._store.fetch, sql, tuple(args))

    async def fetchrow(self, sql: str, *args) -> dict | None:
        return await asyncio.to_thread(self._store.fetchrow, sql, tuple(args))

    async def fetchval(self, sql: str, *args):
        row = await self.fetchrow(sql, *args)
        if not row:
            return None
        return next(iter(row.values()), None)


class _AcquireCtx:
    def __init__(self, store: _DuckStore) -> None:
        self._store = store

    async def __aenter__(self) -> _ConnShim:
        return _ConnShim(self._store)

    async def __aexit__(self, *exc) -> None:
        return None


class _PoolShim:
    """Mimics asyncpg.Pool minimal surface used by app.py lifespan."""

    def __init__(self, store: _DuckStore) -> None:
        self._store = store

    def acquire(self) -> _AcquireCtx:
        return _AcquireCtx(self._store)

    async def close(self) -> None:
        return None


async def get_pool():  # type: ignore[no-redef]
    return _PoolShim(_get_store())


class _DB:
    fetch = staticmethod(fetch)
    fetchrow = staticmethod(fetchrow)
    execute = staticmethod(execute)
    executemany = staticmethod(executemany)
    get_pool = staticmethod(get_pool)
    _pool = None  # satisfies app.py close path


db = _DB()
