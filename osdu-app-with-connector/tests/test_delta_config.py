"""Delta target FQN resolution (unified vs per-domain)."""

from connector.models.config import ConnectorRuntimeConfig, TableLayout


def _minimal_runtime(**delta_kwargs) -> ConnectorRuntimeConfig:
    base = {
        "base_url": "https://example.energy.azure.com",
        "data_partition_id": "opendes",
        "auth": {
            "tenant_id": "t",
            "adme_api_client_id": "a",
            "mode": "static_token",
            "static_access_token": "x",
        },
        "delta": {
            "catalog": "main",
            "schema": "adme",
        },
    }
    base["delta"] = {**base["delta"], **delta_kwargs}
    return ConnectorRuntimeConfig.model_validate(base)


def test_unified_fqn_ignores_domain():
    r = _minimal_runtime(
        table_layout=TableLayout.unified,
        bronze_table="adme_osdu_bronze_records",
        silver_table="adme_osdu_silver_records",
        checkpoint_table="adme_osdu_ingest_checkpoint",
    )
    assert r.delta.bronze_fqn() == "main.adme.adme_osdu_bronze_records"
    assert r.delta.bronze_fqn("wellbore") == "main.adme.adme_osdu_bronze_records"
    assert r.delta.silver_fqn() == "main.adme.adme_osdu_silver_records"
    assert r.delta.checkpoint_fqn() == "main.adme.adme_osdu_ingest_checkpoint"


def test_per_domain_fqn_requires_domain():
    r = _minimal_runtime(table_layout=TableLayout.per_domain)
    assert r.delta.bronze_fqn("Wellbore-A") == "main.adme.bronze_wellbore_a"
    assert r.delta.silver_fqn("reservoir") == "main.adme.silver_reservoir"
    assert r.delta.checkpoint_fqn("wellbore") == "main.adme.checkpoint_wellbore"


def test_entitlements_yaml_alias():
    r = _minimal_runtime(entitlements_groups_table="gov_legacy_name")
    assert r.delta.entitlements_table == "gov_legacy_name"
    assert r.delta.entitlements_fqn() == "main.adme.gov_legacy_name"


def test_sanitize_domain_table_suffix():
    from connector.models.config import DeltaTargetsConfig

    assert DeltaTargetsConfig.sanitize_domain_table_suffix("Wellbore-1") == "wellbore_1"
    assert DeltaTargetsConfig.sanitize_domain_table_suffix("!!!") == "domain"
