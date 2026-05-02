"""Azure Entra auth. Import explicitly: ``from connector.auth.providers import AuthProvider``."""

# Intentionally empty: eager ``from .providers import …`` here causes a partial-import
# cycle when the notebook does ``from connector.auth.providers import AuthProvider``
# (parent ``connector.auth`` runs __init__ before ``providers`` is fully executed).

__all__: list[str] = []
