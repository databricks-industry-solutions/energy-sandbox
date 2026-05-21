"""Read live OSDU well/reservoir/rock data from the UC silver tables hydrated
by the ADME connector pipeline (adme_adb_sbx_scus_dbx_ws_1.adme_client_demo).
Uses databricks-sql-connector with the app SP's default credentials."""
from __future__ import annotations

import os
from typing import Any

CATALOG = os.getenv("ADME_CATALOG", "adme_adb_sbx_scus_dbx_ws_1")
SCHEMA = os.getenv("ADME_SCHEMA", "adme_client_demo")
WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID", "186af4be97756033")


def _conn():
    from databricks import sql
    from databricks.sdk.core import Config

    cfg = Config()
    host = (os.getenv("DATABRICKS_HOST") or cfg.host or "").replace("https://", "").rstrip("/")
    return sql.connect(
        server_hostname=host,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
    )


def fetch_osdu_wells() -> list[dict[str, Any]]:
    """Return OSDU-sourced wellbore records shaped for las.wells insert."""
    try:
        with _conn() as c, c.cursor() as cur:
            cur.execute(f"""
                SELECT
                  record_id,
                  silver_payload:data.FacilityName::string AS name,
                  silver_payload:data.SpudDate::string AS spud,
                  silver_payload:data.ExtensionProperties.platformName::string AS platform,
                  silver_payload:data.ExtensionProperties.purpose::string AS purpose,
                  silver_payload:data.ExtensionProperties.discovery::string AS discovery,
                  silver_payload:data.ExtensionProperties.primaryReservoir::string AS reservoir_zone,
                  silver_payload:data.ExtensionProperties.drillingResult::string AS result,
                  silver_payload:data.ExtensionProperties.surfaceLatitude::double AS lat,
                  silver_payload:data.ExtensionProperties.surfaceLongitude::double AS lon,
                  silver_payload:data.ProjectedBottomHoleMeasuredDepth.value::double AS td_m,
                  silver_payload:data.ProjectedBottomHoleTrueVerticalDepth.value::double AS tvd_m
                FROM `{CATALOG}`.`{SCHEMA}`.silver_wellbore
            """)
            rows = cur.fetchall_arrow().to_pylist()
    except Exception as e:
        print(f"OSDU fetch failed (will run without OSDU wells): {e}")
        return []

    out = []
    for r in rows:
        rid = str(r.get("record_id") or "").split(":")[-1][:24] or "osdu-unknown"
        wid = f"OSDU-{rid}"
        td_m = r.get("td_m") or 3000.0
        td_ft = round(float(td_m) * 3.28084, 0)
        out.append({
            "well_id": wid,
            "well_name": r.get("name") or wid,
            "field_name": r.get("platform") or "OSDU",
            "basin": "North Sea" if (r.get("lat") or 0) > 55 else "OSDU-opendes",
            "county": r.get("platform") or "—",
            "state": r.get("discovery") or "—",
            "api_number": rid,
            "lat": r.get("lat"),
            "lon": r.get("lon"),
            "kb_elevation_ft": 80.0,
            "total_depth_ft": td_ft,
            "spud_date": (r.get("spud") or "")[:10] or None,
            "well_type": "deviated",
            "status": "gold" if (r.get("result") or "").lower() == "producer" else "corrected",
            "quality_score": 85 if (r.get("result") or "").lower() == "producer" else 70,
            "notes": f"ADME live · purpose={r.get('purpose')} · reservoir={r.get('reservoir_zone')} · result={r.get('result')}",
            "purpose": r.get("purpose"),
            "reservoir_zone": r.get("reservoir_zone"),
            "drilling_result": r.get("result"),
        })
    return out
