"""
SAP Business Data Cloud ↔ Databricks Delta Sharing integration layer.

Simulates bidirectional Delta Sharing:
  INBOUND  SAP BDC → Databricks : material pricing, equipment inventory, service contracts
  OUTBOUND Databricks → SAP BDC : production forecasts, cost estimates, MRP triggers
"""

import datetime as _dt

# ── Shared table registry ──────────────────────────────────────────────────
INBOUND_SHARES = [
    {
        "share_name": "sap_bdc_supply_chain",
        "provider": "SAP Business Data Cloud",
        "schema": "sap_norne_ops",
        "tables": [
            {"table": "material_pricing",   "rows": 18, "last_sync": "2026-02-24T08:00:00Z", "status": "ACTIVE", "description": "Material master pricing (drill bits, casing, chemicals, ESP)"},
            {"table": "equipment_inventory", "rows": 8,  "last_sync": "2026-02-24T08:00:00Z", "status": "ACTIVE", "description": "Norne equipment inventory (spares, in-use assets)"},
            {"table": "service_contracts",   "rows": 10, "last_sync": "2026-02-24T06:30:00Z", "status": "ACTIVE", "description": "Active service contracts (rig, wireline, workover, P&A)"},
            {"table": "vendor_lead_times",   "rows": 18, "last_sync": "2026-02-24T07:15:00Z", "status": "ACTIVE", "description": "Vendor delivery lead times per material category"},
        ],
        "recipient": "databricks_norne_workspace",
        "uc_catalog": "norne_digital_twin",
        "uc_schema": "sap_supply_chain",
    },
]

OUTBOUND_SHARES = [
    {
        "share_name": "norne_ops_forecast",
        "recipient": "SAP Business Data Cloud",
        "schema": "norne_digital_twin.ops_forecast",
        "tables": [
            {"table": "production_forecast",  "rows": 0, "last_sync": None, "status": "PENDING", "description": "Per-well production forecast (oil, gas, water rates)"},
            {"table": "material_requirements","rows": 0, "last_sync": None, "status": "PENDING", "description": "Material requirements planning (MRP) from operations schedule"},
            {"table": "cost_estimates",       "rows": 0, "last_sync": None, "status": "PENDING", "description": "Full-cycle cost estimates per well, per activity"},
            {"table": "procurement_triggers", "rows": 0, "last_sync": None, "status": "PENDING", "description": "Automated procurement triggers when inventory < threshold"},
        ],
        "uc_catalog": "norne_digital_twin",
        "uc_schema": "ops_forecast",
    },
]


def _now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def get_sharing_status() -> dict:
    """Return current Delta Sharing status for all shares."""
    return {
        "inbound": INBOUND_SHARES,
        "outbound": OUTBOUND_SHARES,
        "summary": {
            "total_inbound_tables": sum(len(s["tables"]) for s in INBOUND_SHARES),
            "total_outbound_tables": sum(len(s["tables"]) for s in OUTBOUND_SHARES),
            "active_inbound": sum(1 for s in INBOUND_SHARES for t in s["tables"] if t["status"] == "ACTIVE"),
            "pending_outbound": sum(1 for s in OUTBOUND_SHARES for t in s["tables"] if t["status"] == "PENDING"),
        },
        "uc_governance": {
            "catalog": "norne_digital_twin",
            "schemas": ["sap_supply_chain", "ops_forecast", "sim_results"],
            "access_control": "Unity Catalog row-level security",
            "audit_log": "system.access.audit",
        },
    }


def sync_outbound(run_id: str, operations: list, costs: dict,
                   well_timeseries: list) -> dict:
    """
    Simulate pushing forecast + cost data back to SAP BDC via Delta Sharing.
    Updates the outbound share status.
    """
    now = _now()
    events = []

    # Production forecast
    prod_rows = 0
    if well_timeseries:
        prod_rows = sum(len(ts) for ts in well_timeseries)
    _update_outbound("production_forecast", prod_rows, now)
    events.append({"table": "production_forecast", "rows": prod_rows,
                   "status": "SYNCED", "timestamp": now})

    # Material requirements
    mat_rows = len(operations)
    _update_outbound("material_requirements", mat_rows, now)
    events.append({"table": "material_requirements", "rows": mat_rows,
                   "status": "SYNCED", "timestamp": now})

    # Cost estimates
    cost_rows = len(costs.get("costed_operations", []))
    _update_outbound("cost_estimates", cost_rows, now)
    events.append({"table": "cost_estimates", "rows": cost_rows,
                   "status": "SYNCED", "timestamp": now})

    # Procurement triggers — check inventory vs. upcoming needs
    triggers = _check_procurement_triggers(operations)
    _update_outbound("procurement_triggers", len(triggers), now)
    events.append({"table": "procurement_triggers", "rows": len(triggers),
                   "status": "SYNCED", "timestamp": now})

    return {
        "run_id": run_id,
        "sync_timestamp": now,
        "events": events,
        "procurement_triggers": triggers,
    }


def _update_outbound(table_name, rows, timestamp):
    for share in OUTBOUND_SHARES:
        for t in share["tables"]:
            if t["table"] == table_name:
                t["rows"] = rows
                t["last_sync"] = timestamp
                t["status"] = "ACTIVE"


def _check_procurement_triggers(operations):
    """Check if upcoming operations require materials not in inventory."""
    from .costs import SAP_EQUIPMENT, SAP_MATERIALS, _COST_MODEL

    inv = {}
    for eq in SAP_EQUIPMENT:
        inv[eq["description"].split("(")[0].strip().lower()] = eq["qty"]

    triggers = []
    needed = {}
    for op in operations:
        model = _COST_MODEL.get(op["activity_type"], {})
        for mid, qty in model.get("materials", []):
            needed[mid] = needed.get(mid, 0) + qty

    for mid, qty in needed.items():
        mat = next((m for m in SAP_MATERIALS if m["material_id"] == mid), None)
        if mat and mat["unit_price_usd"] > 10000:
            triggers.append({
                "material_id": mid,
                "description": mat["description"],
                "qty_needed": qty,
                "unit_price": mat["unit_price_usd"],
                "total_value": qty * mat["unit_price_usd"],
                "lead_time_days": mat["lead_time_days"],
                "vendor": mat["vendor"],
                "priority": "HIGH" if mat["lead_time_days"] > 30 else "MEDIUM",
            })

    return triggers
