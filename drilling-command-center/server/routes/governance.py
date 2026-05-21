"""Governance endpoints: personas, legal tags, persona-filtered well views."""
import os
import time
from fastapi import APIRouter
from ..db import db

router = APIRouter()

CATALOG = os.getenv("ADME_CATALOG", "adme_adb_sbx_scus_dbx_ws_1")
SCHEMA  = os.getenv("ADME_SCHEMA", "adme_client_demo")
WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID", "186af4be97756033")

# Process-local cache for slow UC/marketplace queries. Warehouse cold-start
# + 2 queries can take 5-10s; legal-tags/audit/co2 only change on a slow cadence,
# so 10 min is fine and survives multi-tab demos. The startup warmup +
# periodic refresh keep the cache hot.
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_S = 600

def _cache_get(key: str):
    e = _CACHE.get(key)
    if e and time.time() - e[0] < _CACHE_TTL_S:
        return e[1]
    return None

def _cache_set(key: str, value: dict):
    _CACHE[key] = (time.time(), value)


@router.get("/governance/personas")
async def list_personas():
    return await db.fetch(
        "SELECT persona, label, allowed_fields, row_filter, description FROM las.persona_grants ORDER BY persona"
    )


@router.get("/governance/view/{persona}")
async def persona_view(persona: str):
    """Return a view of wells filtered/projected by the selected persona."""
    p = await db.fetchrow(
        "SELECT persona, label, allowed_fields, row_filter, description "
        "FROM las.persona_grants WHERE persona=$1", persona
    )
    if not p:
        return {"error": f"unknown persona {persona}"}

    allowed = [c.strip() for c in (p.get("allowed_fields") or "").split(",") if c.strip()]
    row_filter = p.get("row_filter")

    wells = await db.fetch(
        "SELECT well_id, well_name, field_name, basin, county, state, api_number, "
        "lat, lon, kb_elevation_ft, total_depth_ft, spud_date, well_type, status, "
        "quality_score, notes FROM las.wells ORDER BY well_id"
    )

    def filtered_row(w: dict) -> dict:
        if allowed == ["all"]:
            return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in w.items()}
        view = {"well_id": w["well_id"]}  # always visible
        for k in allowed:
            if k == "spud_date" and w.get(k):
                view[k] = w[k].isoformat() if hasattr(w[k], "isoformat") else w[k]
            else:
                view[k] = w.get(k)
        # Mask any column not in allowed as "—"
        for k in w.keys():
            if k not in view:
                view[k] = "🔒 redacted"
        return view

    def row_passes(w: dict) -> bool:
        if not row_filter:
            return True
        # Simple filter: "status IN ('gold','corrected')"
        if "status IN" in row_filter:
            import re
            m = re.search(r"status IN \(([^)]+)\)", row_filter)
            if m:
                allowed_statuses = [s.strip().strip("'\"") for s in m.group(1).split(",")]
                return w.get("status") in allowed_statuses
        return True

    visible = [filtered_row(w) for w in wells if row_passes(w)]

    return {
        "persona":          p["persona"],
        "label":            p["label"],
        "allowed_fields":   allowed,
        "row_filter":       row_filter,
        "description":      p["description"],
        "visible_count":    len(visible),
        "total_count":      len(wells),
        "redacted_count":   len(wells) - len(visible),
        "wells":            visible,
    }


@router.get("/governance/legal_tags")
async def legal_tags():
    """ADME legal tags + entitlement groups — live from Unity Catalog (cached 60s)."""
    cached = _cache_get("legal_tags")
    if cached:
        return cached
    try:
        from databricks import sql
        from databricks.sdk.core import Config
        cfg = Config()
        host = (os.getenv("DATABRICKS_HOST") or cfg.host or "").replace("https://", "").rstrip("/")
        with sql.connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
            credentials_provider=lambda: cfg.authenticate,
        ) as c, c.cursor() as cur:
            cur.execute(f"SELECT legal_tag_name, COALESCE(source, data_partition_id) AS description, is_valid FROM `{CATALOG}`.`{SCHEMA}`.gov_legal_tags LIMIT 20")
            rows = cur.fetchall_arrow().to_pylist()
            cur.execute(f"SELECT group_id, group_name, description FROM `{CATALOG}`.`{SCHEMA}`.gov_entitlements LIMIT 50")
            groups = cur.fetchall_arrow().to_pylist()
        out = {
            "source": f"{CATALOG}.{SCHEMA}",
            "legal_tags": rows,
            "entitlement_groups": groups[:15],
            "total_groups": len(groups),
        }
        _cache_set("legal_tags", out)
        return out
    except Exception as e:
        print(f"legal_tags fetch error: {e}")
        return {"source": f"{CATALOG}.{SCHEMA}", "legal_tags": [], "entitlement_groups": [], "error": str(e)}


@router.get("/governance/co2")
async def co2_emissions(top: int = 12):
    """ESG layer — country CO2 emissions from the Rearc/World Bank Marketplace share (cached 60s)."""
    cached = _cache_get(f"co2:{top}")
    if cached:
        return cached
    cat    = os.getenv("WB_CO2_CATALOG", "rearc_co2_emissions_kt_world_bank_open_data")
    schema = os.getenv("WB_CO2_SCHEMA",  "fs_world_bank_data_weekly")
    table  = os.getenv("WB_CO2_TABLE",   "co2_emissions")
    fqn = f"`{cat}`.`{schema}`.`{table}`"

    try:
        from databricks import sql
        from databricks.sdk.core import Config
        cfg = Config()
        host = (os.getenv("DATABRICKS_HOST") or cfg.host or "").replace("https://", "").rstrip("/")
        with sql.connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
            credentials_provider=lambda: cfg.authenticate,
        ) as c, c.cursor() as cur:
            # Latest available year
            cur.execute(f"SELECT MAX(date) AS y FROM {fqn} WHERE amount_value IS NOT NULL")
            year = cur.fetchall()[0][0]
            cur.execute(f"""
                SELECT country_name, country_code, date AS year, amount_value AS co2_kt
                FROM {fqn}
                WHERE date = {year} AND amount_value IS NOT NULL
                  AND country_code IN ('USA','CHN','RUS','IND','SAU','GBR','NOR','ARE','BRA','IRQ','VEN','CAN','MEX','NGA','DZA')
                ORDER BY amount_value DESC
                LIMIT {int(top)}
            """)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            out = {
                "installed": True,
                "source": f"{cat}.{schema}.{table}",
                "year": year,
                "rows": rows,
            }
            _cache_set(f"co2:{top}", out)
            return out
    except Exception as e:
        return {"installed": False, "error": str(e), "rows": []}


@router.get("/governance/uc_chain")
async def uc_lineage_chain():
    """Static summary of the governance chain for the demo."""
    return {
        "chain": [
            {
                "step": "ADME",
                "title": "Source legal tag",
                "detail": "Records tagged in ADME with purposes, export-control flags and data partitions.",
                "examples": ["not-export-controlled", "oil-gas-wellbore", "opendes-public"],
            },
            {
                "step": "Unity Catalog",
                "title": "UC tag + grant",
                "detail": "Legal tag is mirrored to UC row-level tags; grants enforce USE SCHEMA / SELECT per persona.",
                "examples": ["SELECT ON SCHEMA → poc_users", "USE CATALOG → SP b4297c02…", "tag: legal.not-export"],
            },
            {
                "step": "Subsurface Intelligence",
                "title": "Persona-filtered view",
                "detail": "The app applies the allowed_fields / row_filter bound to the logged-in persona. SP falls back to OBO.",
                "examples": ["operator: full", "analyst: no PII", "external: status IN (gold, corrected) only"],
            },
        ],
    }


@router.get("/governance/audit")
async def audit_events(limit: int = 12):
    """Recent access events. Tries system.access.audit; falls back to synthetic."""
    cached = _cache_get(f"audit:{limit}")
    if cached:
        return cached
    try:
        from databricks import sql
        from databricks.sdk.core import Config
        cfg = Config()
        host = (os.getenv("DATABRICKS_HOST") or cfg.host or "").replace("https://", "").rstrip("/")
        with sql.connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
            credentials_provider=lambda: cfg.authenticate,
        ) as c, c.cursor() as cur:
            cur.execute(f"""
                SELECT event_time, user_identity.email AS actor, action_name AS action,
                       service_name AS service, response.status_code AS status
                FROM system.access.audit
                WHERE event_date >= current_date() - INTERVAL 1 DAY
                  AND service_name IN ('unityCatalog','sqlServerlessExecution','databrickssql','apps')
                ORDER BY event_time DESC LIMIT {int(limit)}
            """)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            for r in rows:
                if hasattr(r.get("event_time"), "isoformat"):
                    r["event_time"] = r["event_time"].isoformat()
            out = {"source": "system.access.audit", "events": rows, "synthetic": False}
            _cache_set(f"audit:{limit}", out)
            return out
    except Exception as e:
        # Fallback: deterministic synthetic events that still tell a real governance story
        import datetime as _dt
        now = _dt.datetime.utcnow()
        seeds = [
            ("operator@energy.com",   "getTable",   "unityCatalog",          200, "adme_osdu.bronze_wellbore"),
            ("analyst@energy.com",    "queryStart", "databrickssql",         200, "wellbore_search_source"),
            ("external@partner.com",  "queryStart", "databrickssql",         403, "row filter: status IN ('gold','corrected')"),
            ("operator@energy.com",   "updateRow",  "apps",                  200, "journal entry · BAKER-001"),
            ("svc-app@databricks",    "getTable",   "unityCatalog",          200, "gov_legal_tags"),
            ("analyst@energy.com",    "queryStart", "databrickssql",         200, "lat/lon column masked"),
            ("external@partner.com",  "getTable",   "unityCatalog",          403, "ADME legal-tag denied: export-controlled"),
            ("operator@energy.com",   "getTable",   "unityCatalog",          200, "silver_wellbore"),
            ("svc-app@databricks",    "getModel",   "modelServing",          200, "claude-3-5-sonnet (expert agent)"),
            ("analyst@energy.com",    "getTable",   "unityCatalog",          200, "wellbore_search_source"),
            ("operator@energy.com",   "queryStart", "databrickssql",         200, "geomechanics_curves"),
            ("external@partner.com",  "getTable",   "unityCatalog",          200, "wellbore_search_source"),
        ]
        events = []
        for i, (actor, action, service, status, target) in enumerate(seeds[:limit]):
            events.append({
                "event_time": (now - _dt.timedelta(minutes=2 + i * 7)).isoformat() + "Z",
                "actor": actor,
                "action": action,
                "service": service,
                "status": status,
                "target": target,
            })
        out = {"source": "synthetic", "events": events, "synthetic": True, "note": str(e)[:120]}
        _cache_set(f"audit:{limit}", out)
        return out
