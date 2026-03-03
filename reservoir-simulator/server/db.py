"""
SQLite-backed async DB layer.
Uses Python built-in sqlite3 via asyncio.to_thread — zero extra dependencies.
Database file: /tmp/reservoir_sim.db
"""
import sqlite3
import asyncio
import os

_DB_PATH = os.environ.get("SQLITE_PATH", "/tmp/reservoir_sim.db")
_conn = None


def _get_conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _conn.commit()
    return _conn


def _sync_execute(sql, args=()):
    conn = _get_conn()
    cur = conn.execute(sql, args)
    conn.commit()
    return cur.lastrowid


def _sync_executescript(ddl):
    conn = _get_conn()
    conn.executescript(ddl)
    conn.commit()


def _sync_fetch(sql, args=()):
    conn = _get_conn()
    rows = conn.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def _sync_fetchrow(sql, args=()):
    conn = _get_conn()
    row = conn.execute(sql, args).fetchone()
    return dict(row) if row else None


def _sync_fetchval(sql, args=()):
    conn = _get_conn()
    row = conn.execute(sql, args).fetchone()
    return row[0] if row else None


async def execute(sql, *args):
    return await asyncio.to_thread(_sync_execute, sql, args)


async def executemany(sql, args_list):
    def _fn():
        conn = _get_conn()
        conn.executemany(sql, args_list)
        conn.commit()
    await asyncio.to_thread(_fn)


async def fetch(sql, *args):
    return await asyncio.to_thread(_sync_fetch, sql, args)


async def fetchrow(sql, *args):
    return await asyncio.to_thread(_sync_fetchrow, sql, args)


async def fetchval(sql, *args):
    return await asyncio.to_thread(_sync_fetchval, sql, args)


async def init_schema(ddl):
    await asyncio.to_thread(_sync_executescript, ddl)


class _DB:
    fetch = staticmethod(fetch)
    fetchrow = staticmethod(fetchrow)
    execute = staticmethod(execute)
    executemany = staticmethod(executemany)
    fetchval = staticmethod(fetchval)
    init_schema = staticmethod(init_schema)


db = _DB()
