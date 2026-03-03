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

render_app()
