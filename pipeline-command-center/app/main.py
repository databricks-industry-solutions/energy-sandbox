"""
Pipeline Command Center — Entry Point
Midstream Oil & Gas Pipeline Command Center with Digital Twin.
"""

import sys, pathlib

# Ensure app directory is on the Python path for local imports
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from ui import render_app

if __name__ == "__main__":
    render_app()
else:
    render_app()
