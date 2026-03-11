"""
app/config.py
--------------
Central configuration for the BOP Guardian Streamlit app.
Lakebase credentials injected via Databricks App resource binding.
"""

import os
from dataclasses import dataclass, field


def _safe_int(env_var: str, default: int) -> int:
    raw = os.getenv(env_var, "")
    try:
        return int(raw) if raw else default
    except (ValueError, TypeError):
        return default


@dataclass(frozen=True)
class Config:
    # Lakebase / Postgres
    pg_host:     str = field(default_factory=lambda: os.getenv("PGHOST", "localhost"))
    pg_port:     int = field(default_factory=lambda: _safe_int("PGPORT", 5432))
    pg_database: str = field(default_factory=lambda: os.getenv("PGDATABASE_OVERRIDE",
                                                                os.getenv("PGDATABASE", "bop_guardian_app")))
    pg_user:     str = field(default_factory=lambda: os.getenv("PGUSER", "postgres"))
    pg_password: str = field(default_factory=lambda: os.getenv("PGPASSWORD", ""))

    # App
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "production"))


config = Config()
