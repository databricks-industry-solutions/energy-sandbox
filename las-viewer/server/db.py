import os
import asyncpg
import asyncio
import base64
import json
import uuid

_pool = None
_refresh_task = None


def _extract_username(token: str) -> str:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.b64decode(payload))
        return data.get("sub", "app_user")
    except Exception:
        return "app_user"


def _generate_lakebase_token() -> tuple[str, str]:
    """Return (username, password) for Lakebase.

    Priority:
    1. PGUSER env var contains a JWT (>100 chars) — the valueFrom: database path
    2. SDK generate_database_credential (requires databricks-sdk >= 0.81.0)
    3. M2M OAuth via client_credentials (DATABRICKS_HOST + CLIENT_ID + CLIENT_SECRET)
    """
    # 1. Env-injected JWT token (valueFrom: database happy path)
    user_raw = os.environ.get("PGUSER", "")
    if len(user_raw) > 100:
        return _extract_username(user_raw), user_raw

    # 2. SDK generate_database_credential (requires SDK >= 0.81.0)
    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        cred = w.database.generate_database_credential(
            request_id=str(uuid.uuid4()),
            instance_names=["las-viewer-db"],
        )
        token = cred.token
        username = _extract_username(token)
        print(f"Lakebase credential generated for: {username}")
        return username, token
    except Exception as e:
        print(f"SDK generate_database_credential failed: {e}")

    # 3. M2M OAuth fallback (DATABRICKS_HOST + CLIENT_ID + CLIENT_SECRET)
    try:
        import urllib.request
        import urllib.parse
        ws_host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
        client_id = os.environ.get("DATABRICKS_CLIENT_ID", "")
        client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET", "")
        if ws_host and client_id and client_secret:
            data = urllib.parse.urlencode({
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "all-apis",
            }).encode()
            req = urllib.request.Request(
                f"{ws_host}/oidc/v1/token",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                token_data = json.loads(resp.read())
                token = token_data.get("access_token", "")
                if len(token) > 50:
                    username = _extract_username(token)
                    print(f"M2M OAuth token obtained for: {username}")
                    return username, token
    except Exception as e:
        print(f"M2M OAuth failed: {e}")

    # 4. Last resort: use whatever PGUSER contains (likely wrong but try)
    return user_raw, user_raw


async def _token_refresh_loop():
    """Refresh Lakebase token every 50 minutes (tokens expire after 1 hour)."""
    global _pool
    while True:
        await asyncio.sleep(50 * 60)
        try:
            old = _pool
            _pool = None
            if old:
                await old.close()
            await get_pool()
            print("Lakebase token refreshed.")
        except Exception as e:
            print(f"Token refresh error: {e}")


async def get_pool():
    global _pool, _refresh_task
    if _pool:
        return _pool
    host = os.environ.get("PGHOST")
    if not host:
        return None
    try:
        raw_port = os.environ.get("PGPORT", "5432")
        try:
            port = int(raw_port)
        except (ValueError, TypeError):
            port = 5432
        db = "postgres"
        username, password = await asyncio.to_thread(_generate_lakebase_token)
        print(f"Connecting to Lakebase: {host}:{port} db={db} user={username}")
        _pool = await asyncpg.create_pool(
            host=host,
            port=port,
            database=db,
            user=username,
            password=password,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        if _refresh_task is None or _refresh_task.done():
            _refresh_task = asyncio.create_task(_token_refresh_loop())
        return _pool
    except Exception as e:
        print(f"DB connection failed: {e}")
        return None


async def fetch(sql: str, *args):
    pool = await get_pool()
    if not pool:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"DB fetch error: {e}")
        return []


async def fetchrow(sql: str, *args):
    pool = await get_pool()
    if not pool:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(sql, *args)
            return dict(row) if row else None
    except Exception as e:
        print(f"DB fetchrow error: {e}")
        return None


async def execute(sql: str, *args):
    pool = await get_pool()
    if not pool:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(sql, *args)
    except Exception as e:
        print(f"DB execute error: {e}")


async def executemany(sql: str, args_list):
    pool = await get_pool()
    if not pool:
        return
    try:
        async with pool.acquire() as conn:
            await conn.executemany(sql, args_list)
    except Exception as e:
        print(f"DB executemany error: {e}")


class _DB:
    fetch = staticmethod(fetch)
    fetchrow = staticmethod(fetchrow)
    execute = staticmethod(execute)
    executemany = staticmethod(executemany)
    get_pool = staticmethod(get_pool)


db = _DB()
