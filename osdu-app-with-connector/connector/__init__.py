"""
ADME / OSDU → Databricks connector framework.

Phase 1: metadata + file-pointer records (no seismic binary ingestion).

Import from subpackages explicitly, e.g. ``from connector.clients.adme_api import ADMEApiClient``.
The package root intentionally avoids importing clients/auth here to prevent circular imports
(``adme_api`` imports ``auth.providers``).
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
