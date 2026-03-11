"""
BOP Guardian — main entry point.
Databricks Apps: streamlit run app/main.py --server.port=8000
"""
import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from app.ui import render_app

# Bootstrap Lakebase schema and seed data on first startup
try:
    from app.db import is_connected, bootstrap_schema, seed_if_empty
    if is_connected():
        bootstrap_schema()
        seed_if_empty()
except Exception:
    pass  # App works fully in-memory when Lakebase is unavailable

render_app()
