"""ADME HTTP simulator — serves corpus JSON as fake ADME API responses."""
from connector.simulator.http_mock import adme_simulator, configure_routes

__all__ = ["adme_simulator", "configure_routes"]
