"""
app/config.py
-------------
Central configuration for the ROP Prediction Streamlit app.
All values can be overridden via environment variables.
Lakebase connection credentials (PGHOST, PGUSER, PGPASSWORD) are
injected automatically by the Databricks App Lakebase resource.

NOTE: When using 'valueFrom' with a Lakebase database resource, the
injected value may not always match what the env-var name implies
(e.g. PGPORT may receive the hostname string). This module
uses safe parsing helpers to handle unexpected values gracefully.
"""

import os
from dataclasses import dataclass, field


def _safe_int(env_var: str, default: int) -> int:
    """Parse an env-var as int; return *default* if the value is missing or
    not a valid integer (Lakebase valueFrom can inject non-numeric strings)."""
    raw = os.getenv(env_var, "")
    try:
        return int(raw) if raw else default
    except (ValueError, TypeError):
        return default


@dataclass(frozen=True)
class Config:
    # ── Lakebase / Postgres ───────────────────────────────────
    pg_host:     str  = field(default_factory=lambda: os.getenv("PGHOST",     "localhost"))
    pg_port:     int  = field(default_factory=lambda: _safe_int("PGPORT", 5432))
    pg_database: str  = field(default_factory=lambda: os.getenv("PGDATABASE_OVERRIDE",
                                                                 os.getenv("PGDATABASE", "drilling_demo_app")))
    pg_user:     str  = field(default_factory=lambda: os.getenv("PGUSER",     "postgres"))
    pg_password: str  = field(default_factory=lambda: os.getenv("PGPASSWORD", ""))

    # ── MLflow ────────────────────────────────────────────────
    mlflow_model_name:     str  = field(default_factory=lambda: os.getenv("MLFLOW_MODEL_NAME", "rop_xgb_mseel"))
    mlflow_tracking_uri:   str  = field(default_factory=lambda: os.getenv("MLFLOW_TRACKING_URI", "databricks"))
    mlflow_experiment:     str  = field(default_factory=lambda: os.getenv("MLFLOW_EXP", "/Shared/ROP_Prediction_MSEEL"))

    # ── Hazard thresholds ─────────────────────────────────────
    rop_gap_threshold:    float = field(default_factory=lambda: float(os.getenv("ROP_GAP_THRESHOLD",  "20.0")))
    mse_high_threshold:   float = field(default_factory=lambda: float(os.getenv("MSE_HIGH_THRESHOLD", "150000.0")))
    mse_optimal_threshold:float = field(default_factory=lambda: float(os.getenv("MSE_OPT_THRESHOLD",  "50000.0")))

    # ── App defaults ──────────────────────────────────────────
    default_well:         str   = field(default_factory=lambda: os.getenv("DEFAULT_WELL",        "MIP_3H"))
    default_window_min:   int   = field(default_factory=lambda: int(os.getenv("DEFAULT_WINDOW",  "10080")))
    page_size:            int   = field(default_factory=lambda: int(os.getenv("PAGE_SIZE",        "5000")))
    auto_refresh_sec:     int   = field(default_factory=lambda: int(os.getenv("AUTO_REFRESH_SEC", "30")))

    # ── Well catalogue ────────────────────────────────────────
    known_wells: tuple = ("MIP_3H", "MIP_4H")

    # ── Bit / field constants ─────────────────────────────────
    bit_diameter_in: float = field(default_factory=lambda: float(os.getenv("BIT_DIAMETER_IN", "6.0")))

    # ── UI ────────────────────────────────────────────────────
    app_title: str = "ROP Prediction · MSEEL Demo"
    app_icon:  str = "🛢️"


# Singleton instance imported by all modules
config = Config()
