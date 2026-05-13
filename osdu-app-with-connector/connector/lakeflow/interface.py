"""Minimal LakeflowConnect interface — mirrors databricks.labs.community_connector.
No PySpark dependency; schema expressed as list of SchemaField dicts."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, TypedDict


class SchemaField(TypedDict):
    name: str
    type: str
    nullable: bool


class LakeflowConnect(ABC):
    """Base interface every source connector must implement."""

    def __init__(self, options: dict[str, str]) -> None:
        self.options = options

    @abstractmethod
    def list_tables(self) -> list[str]:
        """Return names of all tables this connector exposes."""

    @abstractmethod
    def get_table_schema(self, table_name: str, table_options: dict[str, str]) -> list[SchemaField]:
        """Return field definitions for the given table."""

    @abstractmethod
    def read_table_metadata(self, table_name: str, table_options: dict[str, str]) -> dict:
        """Return dict with primary_keys, cursor_field, ingestion_type."""

    @abstractmethod
    def read_table(
        self,
        table_name: str,
        start_offset: dict | None,
        table_options: dict[str, str],
    ) -> tuple[Iterator[dict], dict | None]:
        """Return (records_iterator, end_offset). Pagination stops when end_offset == start_offset."""
