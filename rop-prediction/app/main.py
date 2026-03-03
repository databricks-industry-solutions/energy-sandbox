"""
app/main.py
------------
Thin entry-point for the Databricks App.
Databricks App runtime runs:  streamlit run app/main.py --server.port=8000 ...
"""

import sys
from pathlib import Path

# Ensure the project root is on sys.path so 'from app.xxx import ...' works
# when Streamlit runs this file directly.
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from app.ui import render_app

render_app()
