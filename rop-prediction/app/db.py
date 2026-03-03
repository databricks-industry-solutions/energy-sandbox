"""
app/db.py
----------
SQLAlchemy engine builder for the Lakebase Postgres connection.

Authentication strategy:
  1. If PGUSER contains a long JWT token (>100 chars) -- the "valueFrom: database"
     injection path -- extract the subject as username and use the JWT as password.
  2. If DATABRICKS_CLIENT_ID / DATABRICKS_CLIENT_SECRET are present, perform
     M2M OAuth to get an access token and use that as the password.
  3. Fall back to plain PGUSER / PGPASSWORD (local dev mode).

The database name is forced to PGDATABASE env var (default "drilling_demo_app")
because the Lakebase resource injection may set PGDATABASE to "databricks_postgres".

Token refresh:  The engine is rebuilt every 45 minutes so that the
M2M OAuth token stays valid (Lakebase tokens expire after ~1 hour).
"""

from __future__ import annotations

import base64
import json
import os
import time
import threading
import uuid
from contextlib import contextmanager
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

from app.config import config

# ---- Lakebase token helpers -------------------------------------------------

# Token refresh interval (seconds).  Lakebase M2M tokens last ~1 hour;
# refresh at 45 minutes to avoid races.
_TOKEN_REFRESH_SEC = 45 * 60

_engine_lock = threading.Lock()
_engine: Engine | None = None
_engine_created_at: float = 0.0


def _extract_username(token: str) -> str:
    """Extract the 'sub' claim from a JWT token."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.b64decode(payload))
        return data.get("sub", "app_user")
    except Exception:
        return "app_user"


def _generate_lakebase_credentials() -> tuple[str, str]:
    """Return (username, password) for Lakebase connection.

    Priority:
      1. PGUSER is a JWT (>100 chars) -- valueFrom: database path
      2. SDK generate_database_credential
      3. M2M OAuth (client_credentials)
      4. Plain PGUSER / PGPASSWORD (local dev)
    """
    # 1. Env-injected JWT token
    user_raw = os.environ.get("PGUSER", "")
    if len(user_raw) > 100:
        return _extract_username(user_raw), user_raw

    # 2. SDK generate_database_credential
    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        cred = w.database.generate_database_credential(
            request_id=str(uuid.uuid4()),
            instance_names=["drilling-demo-lakebase"],
        )
        token = cred.token
        username = _extract_username(token)
        print(f"[db] Lakebase credential generated for: {username}")
        return username, token
    except Exception as e:
        print(f"[db] SDK generate_database_credential failed: {e}")

    # 3. M2M OAuth fallback
    try:
        import urllib.request
        import urllib.parse
        ws_host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
        if ws_host and not ws_host.startswith("http"):
            ws_host = f"https://{ws_host}"
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
                    print(f"[db] M2M OAuth token obtained for: {username}")
                    return username, token
    except Exception as e:
        print(f"[db] M2M OAuth failed: {e}")

    # 4. Plain fallback (local dev)
    return config.pg_user, config.pg_password


# ---- Engine construction ----------------------------------------------------

def _build_dsn() -> str:
    """Construct the Postgres DSN with Lakebase-aware authentication."""
    host = os.environ.get("PGHOST", config.pg_host)
    # Force our database name (Lakebase may inject "databricks_postgres")
    database = os.environ.get("PGDATABASE_OVERRIDE", config.pg_database)
    raw_port = os.environ.get("PGPORT", str(config.pg_port))
    try:
        port = int(raw_port)
    except (ValueError, TypeError):
        port = 5432

    user, password = _generate_lakebase_credentials()

    # URL-encode user and password (JWTs contain special characters)
    user_enc = quote_plus(user)
    pass_enc = quote_plus(password)

    dsn = f"postgresql+psycopg2://{user_enc}:{pass_enc}@{host}:{port}/{database}"
    print(f"[db] Connecting to: {host}:{port}/{database} user={user[:40]}...")
    return dsn


def _create_engine() -> Engine:
    """Create a fresh SQLAlchemy engine with a new OAuth token."""
    dsn = _build_dsn()
    engine = create_engine(
        dsn,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        pool_recycle=300,
        pool_pre_ping=True,
        echo=False,
        connect_args={
            "connect_timeout": 10,
            "application_name": "rop_prediction_app",
            "sslmode": "require",
        },
    )
    return engine


def get_engine() -> Engine:
    """
    Return a SQLAlchemy engine, refreshing the token when it is about to
    expire.  Thread-safe: only one thread rebuilds the engine at a time.

    The engine is rebuilt every _TOKEN_REFRESH_SEC seconds (default 45 min)
    so that the M2M OAuth token stays fresh.  Stale engines are disposed
    of cleanly to release pooled connections.
    """
    global _engine, _engine_created_at

    now = time.monotonic()
    if _engine is not None and (now - _engine_created_at) < _TOKEN_REFRESH_SEC:
        return _engine

    with _engine_lock:
        # Double-check inside the lock
        now = time.monotonic()
        if _engine is not None and (now - _engine_created_at) < _TOKEN_REFRESH_SEC:
            return _engine

        old_engine = _engine
        try:
            _engine = _create_engine()
            _engine_created_at = now
            print(f"[db] Engine created/refreshed at {time.strftime('%H:%M:%S UTC', time.gmtime())}")
        except Exception as e:
            print(f"[db] Engine creation failed: {e}")
            # If we had a previous engine, keep it as a fallback
            if old_engine is not None:
                return old_engine
            raise

        # Dispose the old engine's pool (close stale connections)
        if old_engine is not None:
            try:
                old_engine.dispose()
                print("[db] Old engine disposed.")
            except Exception:
                pass

        return _engine


@contextmanager
def get_conn():
    """Context manager yielding a SQLAlchemy connection from the pool."""
    engine = get_engine()
    with engine.connect() as conn:
        yield conn


def health_check() -> bool:
    """Return True if Lakebase is reachable, False otherwise.

    On auth failure, force an immediate engine refresh and retry once.
    """
    global _engine_created_at
    try:
        with get_conn() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        err_str = str(e)
        if "Invalid authorization" in err_str or "FATAL" in err_str:
            # Token likely expired -- force refresh on next call
            print("[db] Auth failure detected -- forcing engine refresh.")
            _engine_created_at = 0.0
            try:
                with get_conn() as conn:
                    conn.execute(text("SELECT 1"))
                print("[db] Reconnected after token refresh.")
                return True
            except Exception as e2:
                print(f"[db] Health check failed after refresh: {e2}")
                return False
        print(f"[db] Health check failed: {e}")
        return False
