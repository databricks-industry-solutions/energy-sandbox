"""Tests for AdmeOsduLakeflowConnect — simulate and live modes.

Run:
    pytest tests/unit/adme_osdu/ -v                              # simulate (default)
    CONNECTOR_TEST_MODE=live pytest tests/unit/adme_osdu/ -v     # live (needs dev_config.json)
"""
from __future__ import annotations

import pytest

from connector.lakeflow.adme_osdu import AdmeOsduLakeflowConnect
from tests.unit.test_suite import AdmeConnectorTests


class TestAdmeOsduConnector(AdmeConnectorTests):
    """Full suite against simulate corpus (or live ADME when CONNECTOR_TEST_MODE=live)."""

    connector_class = AdmeOsduLakeflowConnect
    replay_config = {
        "base_url": "https://adme-simulator.example.com",
        "data_partition_id": "opendes",
        "access_token": "simulator-fake-token",
    }

    @classmethod
    def setup_class(cls) -> None:
        super().setup_class()

    # ── ADME-specific extra tests ──────────────────────────────────────────────

    def test_list_tables_includes_governance(self) -> None:
        tables = self.connector.list_tables()
        assert "legal_tags" in tables
        assert "entitlements" in tables

    def test_list_tables_includes_domains(self) -> None:
        tables = self.connector.list_tables()
        assert "wellbore" in tables
        assert "reservoir" in tables
        assert "rock_and_fluid" in tables

    def test_domain_tables_are_cdc(self) -> None:
        for table in ("wellbore", "reservoir", "rock_and_fluid"):
            meta = self.connector.read_table_metadata(table, {})
            assert meta["ingestion_type"] == "cdc", f"{table} should be cdc"
            assert meta["cursor_field"] == "modifyTime"
            assert "id" in meta["primary_keys"]

    def test_governance_tables_are_snapshot(self) -> None:
        for table in ("legal_tags", "entitlements"):
            meta = self.connector.read_table_metadata(table, {})
            assert meta["ingestion_type"] == "snapshot", f"{table} should be snapshot"

    def test_wellbore_records_have_osdu_fields(self) -> None:
        records, _ = self.connector.read_table("wellbore", None, {})
        recs = list(records)
        assert len(recs) > 0
        for r in recs:
            assert "id" in r
            assert "modifyTime" in r
            assert "kind" in r

    def test_legal_tags_have_expected_fields(self) -> None:
        records, offset = self.connector.read_table("legal_tags", None, {})
        recs = list(records)
        assert len(recs) > 0
        assert offset is None  # snapshot: no offset
        for r in recs:
            assert "legal_tag_name" in r
            assert "data_partition_id" in r

    def test_entitlements_have_expected_fields(self) -> None:
        records, offset = self.connector.read_table("entitlements", None, {})
        recs = list(records)
        assert len(recs) > 0
        assert offset is None
        for r in recs:
            assert "group_id" in r
            assert "group_name" in r

    def test_read_wellbore_twice_returns_same_stable_offset(self) -> None:
        """Second call with last offset == last offset should return empty (no new data)."""
        _, offset1 = self.connector.read_table("wellbore", None, {})
        records2, offset2 = self.connector.read_table("wellbore", offset1, {})
        recs2 = list(records2)
        # In simulate mode, no new records after first page → offset stable
        assert offset2 == offset1
        assert len(recs2) == 0
