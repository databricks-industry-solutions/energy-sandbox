"""Phase A: mirror OSDU governance metadata (legal tags, entitlements, ACL hints) into Unity Catalog Delta tables."""

from connector.governance.sync import sync_governance_mirror

__all__ = ["sync_governance_mirror"]
