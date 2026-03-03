"""
app/config.py
--------------
Central configuration for the ESP Predictive Maintenance Streamlit app.
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


def _safe_float(env_var: str, default: float) -> float:
    raw = os.getenv(env_var, "")
    try:
        return float(raw) if raw else default
    except (ValueError, TypeError):
        return default


@dataclass(frozen=True)
class Config:
    # ── Lakebase / Postgres ───────────────────────────────────
    pg_host:     str  = field(default_factory=lambda: os.getenv("PGHOST",     "localhost"))
    pg_port:     int  = field(default_factory=lambda: _safe_int("PGPORT", 5432))
    pg_database: str  = field(default_factory=lambda: os.getenv("PGDATABASE_OVERRIDE",
                                                                 os.getenv("PGDATABASE", "esp_pm_app")))
    pg_user:     str  = field(default_factory=lambda: os.getenv("PGUSER",     "postgres"))
    pg_password: str  = field(default_factory=lambda: os.getenv("PGPASSWORD", ""))

    # ── Databricks SQL warehouse (for Delta reads) ────────────
    databricks_host:          str = field(default_factory=lambda: os.getenv("DATABRICKS_HOST", ""))
    databricks_token:         str = field(default_factory=lambda: os.getenv("DATABRICKS_TOKEN", ""))
    databricks_warehouse_id:  str = field(default_factory=lambda: os.getenv("DATABRICKS_WAREHOUSE_ID", ""))

    # ── MLflow / AI ───────────────────────────────────────────
    claude_model_name:  str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL",
                                                                        "databricks-claude-sonnet-4-5"))

    # ── Alert thresholds ──────────────────────────────────────
    threshold_high:   float = field(default_factory=lambda: _safe_float("THRESHOLD_HIGH",   0.65))
    threshold_medium: float = field(default_factory=lambda: _safe_float("THRESHOLD_MEDIUM", 0.30))

    # ── App defaults ──────────────────────────────────────────
    default_time_window_days: int = field(default_factory=lambda: _safe_int("DEFAULT_WINDOW_DAYS", 7))
    page_size:                int = field(default_factory=lambda: _safe_int("PAGE_SIZE", 500))
    auto_refresh_sec:         int = field(default_factory=lambda: _safe_int("AUTO_REFRESH_SEC", 60))

    # ── UI ────────────────────────────────────────────────────
    app_title: str = "ESP Predictive Maintenance"
    app_icon:  str = "⚡"


config = Config()
