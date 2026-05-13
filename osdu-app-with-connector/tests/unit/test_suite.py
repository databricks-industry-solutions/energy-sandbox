"""AdmeConnectorTests — base pytest class mirroring community_connector.LakeflowConnectTests.

Usage:
    class TestMyConnector(AdmeConnectorTests):
        connector_class = MyLakeflowConnect
        replay_config = {"base_url": "https://simulator.example.com", ...}
"""
from __future__ import annotations

import os
from typing import Type

import pytest

from connector.lakeflow.interface import LakeflowConnect

VALID_INGESTION_TYPES = {"snapshot", "cdc", "cdc_with_deletes", "append"}
CONNECTOR_TEST_MODE = os.environ.get("CONNECTOR_TEST_MODE", "simulate")


class AdmeConnectorTests:
    """Base test class for LakeflowConnect implementations.

    Subclass and set:
        connector_class  : the connector class (must subclass LakeflowConnect)
        replay_config    : dict of options for simulate/replay mode
    """

    connector_class: Type[LakeflowConnect] = None
    replay_config: dict = {}
    sample_records: int = 50
    allow_empty_first_read: frozenset = frozenset()

    connector: LakeflowConnect

    @classmethod
    def setup_class(cls) -> None:
        assert cls.connector_class is not None, "connector_class must be set"
        cls.connector = cls.connector_class(cls.replay_config)

    # ── Interface contract tests ───────────────────────────────────────────────

    def test_list_tables(self) -> None:
        tables = self.connector.list_tables()
        assert isinstance(tables, list), "list_tables must return a list"
        assert len(tables) > 0, "list_tables must return at least one table"
        for t in tables:
            assert isinstance(t, str), f"table name must be str, got {type(t)}"
            assert t.strip() == t, f"table name must not have leading/trailing whitespace: {t!r}"

    def test_list_tables_stable(self) -> None:
        """list_tables must be deterministic."""
        assert self.connector.list_tables() == self.connector.list_tables()

    def test_get_table_schema(self) -> None:
        for table in self.connector.list_tables():
            schema = self.connector.get_table_schema(table, {})
            assert isinstance(schema, list), f"{table}: schema must be a list"
            assert len(schema) > 0, f"{table}: schema must have at least one field"
            for field in schema:
                assert "name" in field, f"{table}: field missing 'name': {field}"
                assert "type" in field, f"{table}: field missing 'type': {field}"
                assert isinstance(field["name"], str)

    def test_get_table_schema_stable(self) -> None:
        for table in self.connector.list_tables():
            s1 = self.connector.get_table_schema(table, {})
            s2 = self.connector.get_table_schema(table, {})
            assert [f["name"] for f in s1] == [f["name"] for f in s2], f"{table}: schema not stable"

    def test_read_table_metadata(self) -> None:
        for table in self.connector.list_tables():
            meta = self.connector.read_table_metadata(table, {})
            assert isinstance(meta, dict), f"{table}: metadata must be dict"
            assert "primary_keys" in meta, f"{table}: metadata missing primary_keys"
            assert "ingestion_type" in meta, f"{table}: metadata missing ingestion_type"
            assert isinstance(meta["primary_keys"], list)
            assert meta["ingestion_type"] in VALID_INGESTION_TYPES, (
                f"{table}: invalid ingestion_type {meta['ingestion_type']!r}"
            )

    def test_read_table_metadata_primary_keys_in_schema(self) -> None:
        for table in self.connector.list_tables():
            meta = self.connector.read_table_metadata(table, {})
            schema_names = {f["name"] for f in self.connector.get_table_schema(table, {})}
            for pk in meta["primary_keys"]:
                assert pk in schema_names, (
                    f"{table}: primary_key {pk!r} not found in schema fields {schema_names}"
                )

    def test_read_table(self) -> None:
        for table in self.connector.list_tables():
            records, offset = self.connector.read_table(table, None, {})
            recs = list(records)
            meta = self.connector.read_table_metadata(table, {})
            if table not in self.allow_empty_first_read:
                assert len(recs) > 0, f"{table}: first read returned 0 records"
            for rec in recs:
                assert isinstance(rec, dict), f"{table}: record must be dict"
                for pk in meta["primary_keys"]:
                    assert pk in rec, f"{table}: record missing primary key {pk!r}"
                    assert rec[pk] is not None, f"{table}: primary key {pk!r} is None"

    def test_read_table_cursor_field_present(self) -> None:
        for table in self.connector.list_tables():
            meta = self.connector.read_table_metadata(table, {})
            cursor = meta.get("cursor_field")
            if not cursor:
                continue
            records, _ = self.connector.read_table(table, None, {})
            for rec in records:
                assert cursor in rec, f"{table}: record missing cursor_field {cursor!r}"

    def test_read_terminates(self) -> None:
        """Repeated calls to read_table must converge to a stable offset."""
        max_iters = 20
        for table in self.connector.list_tables():
            offset = None
            for _ in range(max_iters):
                records, new_offset = self.connector.read_table(table, offset, {})
                list(records)  # consume the iterator
                if new_offset == offset:
                    break
                offset = new_offset
            else:
                pytest.fail(
                    f"{table}: read_table did not converge after {max_iters} iterations"
                )

    def test_unknown_table_raises(self) -> None:
        with pytest.raises(Exception):
            self.connector.get_table_schema("__nonexistent_table__", {})
        with pytest.raises(Exception):
            self.connector.read_table_metadata("__nonexistent_table__", {})
        with pytest.raises(Exception):
            self.connector.read_table("__nonexistent_table__", None, {})
