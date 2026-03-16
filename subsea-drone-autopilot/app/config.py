"""Configuration for Subsea Drone Autopilot App."""

import os

# Databricks
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")
WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID", "")

# LLM / Agent
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "databricks-claude-sonnet-4-6")
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", f"/serving-endpoints/{CLAUDE_MODEL}/invocations")

# Vector Search (RAG)
VS_ENDPOINT = os.getenv("VECTOR_SEARCH_ENDPOINT", "subsea-manuals-vs")
VS_INDEX = os.getenv("VECTOR_SEARCH_INDEX", "subsea.manuals.chunk_index")

# Lakebase (injected by app.yaml resource binding)
PG_HOST = os.getenv("PGHOST", "localhost")
PG_PORT = os.getenv("PGPORT", "5432")
PG_USER = os.getenv("PGUSER", "subsea_app")
PG_PASSWORD = os.getenv("PGPASSWORD", "")
PG_DATABASE = os.getenv("PGDATABASE", "subsea_ops")

# Catalog
CATALOG = "oil_pump_monitor_catalog"
SCHEMA = "subsea"
