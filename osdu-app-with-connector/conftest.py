"""Root conftest: inject test stubs before any connector imports.

Stubs provide minimal implementations of packages unavailable offline:
  - azure.core.credentials / azure.identity  (not needed in static_token mode)
  - tenacity                                  (passthrough, no real retrying)
  - respx                                     (httpx.Client.send patcher)
"""
from __future__ import annotations

import sys
from pathlib import Path

_STUBS = str(Path(__file__).parent / "tests" / "stubs")
if _STUBS not in sys.path:
    sys.path.insert(0, _STUBS)
