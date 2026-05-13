# connector-dev

Expert agent for developing and modifying the ADME OSDU LakeflowConnect connector.

## Scope

Modifications are restricted to:
- `connector/lakeflow/interface.py` — `LakeflowConnect` ABC and `SchemaField`
- `connector/lakeflow/adme_osdu.py` — `AdmeOsduLakeflowConnect` implementation
- `connector/simulator/http_mock.py` — HTTP mock routes
- `connector/simulator/corpus/*.json` — corpus fixture data
- `connector_spec.yaml` — Unity Catalog connection spec

Do NOT modify `connector/clients/`, `connector/auth/`, `connector/models/`, `connector/domains/`, `connector/governance/` unless explicitly instructed.

## LakeflowConnect Contract

```python
class LakeflowConnect(ABC):
    def __init__(self, options: dict[str, str]) -> None: ...
    def list_tables(self) -> list[str]: ...
    def get_table_schema(self, table_name: str, table_options: dict[str, str]) -> list[SchemaField]: ...
    def read_table_metadata(self, table_name: str, table_options: dict[str, str]) -> dict: ...
    def read_table(self, table_name: str, start_offset: dict | None, table_options: dict[str, str]) -> tuple[Iterator[dict], dict | None]: ...
```

`read_table` pagination terminates when `end_offset == start_offset` (returned offset unchanged).

## ADME Tables

| Table | Type | Ingestion | Cursor |
|-------|------|-----------|--------|
| wellbore | domain | cdc | modifyTime |
| reservoir | domain | cdc | modifyTime |
| rock_and_fluid | domain | cdc | modifyTime |
| legal_tags | governance | snapshot | None |
| entitlements | governance | snapshot | None |

## Domain Record Structure (after `_flatten_record`)

`id`, `kind`, `version`, `createTime`, `createUser`, `modifyTime`, `modifyUser`, `acl_viewers`, `acl_owners`, `legal_tags`, `legal_status`, `data` (map<string,string>)

## Incremental Filter

Domain tables use `incremental_filter_template: "modifyTime:[{watermark} TO *]"`. When a watermark is present, this becomes the `query` field in the ADME search request body, filtering records newer than the watermark.

## Auth Modes (for tests)

Always use `static_token` mode in simulator tests — set `access_token` in options. Production uses `managed_identity` or `service_principal`.
