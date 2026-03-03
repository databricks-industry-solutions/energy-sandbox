"""
BOP Guardian — static mock data for SAP ERP, crew, RUL predictions, and spare parts.
"""
from __future__ import annotations


# ── RUL Predictions ───────────────────────────────────────

RUL_PREDICTIONS = [
    {"asset_id": "BOP-ANN-01", "component_type": "ANNULAR",
     "predicted_rul_days": 142, "failure_prob_7d": 0.02, "failure_prob_30d": 0.08,
     "model_version": "rul_xgb_v3.1"},
    {"asset_id": "BOP-UPR-01", "component_type": "UPPER_PIPE_RAM",
     "predicted_rul_days": 210, "failure_prob_7d": 0.01, "failure_prob_30d": 0.04,
     "model_version": "rul_xgb_v3.1"},
    {"asset_id": "BOP-LPR-01", "component_type": "LOWER_PIPE_RAM",
     "predicted_rul_days": 195, "failure_prob_7d": 0.01, "failure_prob_30d": 0.05,
     "model_version": "rul_xgb_v3.1"},
    {"asset_id": "BOP-BSR-01", "component_type": "BLIND_SHEAR_RAM",
     "predicted_rul_days": 88, "failure_prob_7d": 0.06, "failure_prob_30d": 0.18,
     "model_version": "rul_xgb_v3.1"},
    {"asset_id": "POD-A", "component_type": "POD_A",
     "predicted_rul_days": 62, "failure_prob_7d": 0.09, "failure_prob_30d": 0.28,
     "model_version": "rul_xgb_v3.1"},
    {"asset_id": "POD-B", "component_type": "POD_B",
     "predicted_rul_days": 180, "failure_prob_7d": 0.01, "failure_prob_30d": 0.05,
     "model_version": "rul_xgb_v3.1"},
    {"asset_id": "PMP-01", "component_type": "PUMP",
     "predicted_rul_days": 45, "failure_prob_7d": 0.12, "failure_prob_30d": 0.38,
     "model_version": "rul_xgb_v3.1"},
    {"asset_id": "PMP-02", "component_type": "PUMP",
     "predicted_rul_days": 220, "failure_prob_7d": 0.008, "failure_prob_30d": 0.03,
     "model_version": "rul_xgb_v3.1"},
    {"asset_id": "ACC-01", "component_type": "ACCUMULATOR",
     "predicted_rul_days": 110, "failure_prob_7d": 0.03, "failure_prob_30d": 0.11,
     "model_version": "rul_xgb_v3.1"},
    {"asset_id": "PLC-01", "component_type": "PLC",
     "predicted_rul_days": 365, "failure_prob_7d": 0.002, "failure_prob_30d": 0.01,
     "model_version": "rul_xgb_v3.1"},
]

# ── Failure Patterns ──────────────────────────────────────

FAILURE_PATTERNS = [
    {"component_type": "ANNULAR", "anomaly_pattern": "PRESSURE_LEAK",
     "avg_ttf_days": 35, "failure_mode": "Packer element degradation",
     "fix_action": "Replace annular packer element (12-hr job, requires BOP pull)"},
    {"component_type": "BLIND_SHEAR_RAM", "anomaly_pattern": "SLOW_CLOSE",
     "avg_ttf_days": 21, "failure_mode": "Hydraulic seal wear / debris",
     "fix_action": "Replace ram seals and clean hydraulic passages (8-hr job)"},
    {"component_type": "POD_A", "anomaly_pattern": "COMM_LOSS",
     "avg_ttf_days": 14, "failure_mode": "MUX cable or solenoid valve failure",
     "fix_action": "Swap to Pod B, retrieve Pod A for repair (4-hr switchover)"},
    {"component_type": "PUMP", "anomaly_pattern": "HIGH_CURRENT",
     "avg_ttf_days": 28, "failure_mode": "Motor bearing wear / impeller damage",
     "fix_action": "Replace pump motor bearings (6-hr job, swap to backup pump)"},
    {"component_type": "ACCUMULATOR", "anomaly_pattern": "PRESSURE_DECAY",
     "avg_ttf_days": 42, "failure_mode": "Bladder leak or nitrogen loss",
     "fix_action": "Recharge nitrogen pre-charge, inspect bladders (4-hr job)"},
]

# ── SAP Work Orders ───────────────────────────────────────

SAP_WORK_ORDERS = [
    {"wo_id": "PM-400201", "equipment_id": "BOP-BSR-01", "description": "Blind shear ram seal inspection",
     "status": "OPEN", "priority": 1, "start_date": "2026-03-01", "finish_date": "2026-03-02",
     "failure_code": "BSR-SEAL-01", "maintenance_activity": "INSPECT", "rig_id": "RIG-SENTINEL"},
    {"wo_id": "PM-400202", "equipment_id": "PMP-01", "description": "Koomey pump motor bearing replacement",
     "status": "OPEN", "priority": 2, "start_date": "2026-03-03", "finish_date": "2026-03-03",
     "failure_code": "PMP-BRG-01", "maintenance_activity": "REPLACE", "rig_id": "RIG-SENTINEL"},
    {"wo_id": "PM-400203", "equipment_id": "POD-A", "description": "Pod A MUX cable diagnostic",
     "status": "IN_PROGRESS", "priority": 1, "start_date": "2026-02-27", "finish_date": "2026-02-28",
     "failure_code": "POD-COMM-01", "maintenance_activity": "DIAGNOSE", "rig_id": "RIG-SENTINEL"},
    {"wo_id": "PM-400204", "equipment_id": "ACC-01", "description": "Accumulator nitrogen pre-charge check",
     "status": "PLANNED", "priority": 3, "start_date": "2026-03-05", "finish_date": "2026-03-05",
     "failure_code": "", "maintenance_activity": "INSPECT", "rig_id": "RIG-SENTINEL"},
    {"wo_id": "PM-400205", "equipment_id": "BOP-ANN-01", "description": "Annular preventer function test",
     "status": "COMPLETED", "priority": 2, "start_date": "2026-02-20", "finish_date": "2026-02-20",
     "failure_code": "", "maintenance_activity": "TEST", "rig_id": "RIG-SENTINEL"},
    {"wo_id": "PM-400206", "equipment_id": "BOP-UPR-01", "description": "Upper pipe ram seal replacement",
     "status": "PLANNED", "priority": 3, "start_date": "2026-03-10", "finish_date": "2026-03-11",
     "failure_code": "RAM-SEAL-02", "maintenance_activity": "REPLACE", "rig_id": "RIG-SENTINEL"},
]

# ── SAP Spare Parts / BOM ────────────────────────────────

SAP_SPARES = [
    {"material_id": "MAT-5001", "description": "Annular packer element 18-3/4\"",
     "component_type": "ANNULAR", "available_qty": 2, "min_stock": 1,
     "lead_time_days": 14, "unit_price": 45000, "plant": "GOM-SHORE"},
    {"material_id": "MAT-5002", "description": "Ram seal kit — pipe ram",
     "component_type": "PIPE_RAM", "available_qty": 4, "min_stock": 2,
     "lead_time_days": 7, "unit_price": 12000, "plant": "GOM-SHORE"},
    {"material_id": "MAT-5003", "description": "BSR blade assembly",
     "component_type": "BLIND_SHEAR_RAM", "available_qty": 1, "min_stock": 1,
     "lead_time_days": 21, "unit_price": 85000, "plant": "GOM-SHORE"},
    {"material_id": "MAT-5004", "description": "BSR seal kit",
     "component_type": "BLIND_SHEAR_RAM", "available_qty": 3, "min_stock": 2,
     "lead_time_days": 10, "unit_price": 18000, "plant": "GOM-SHORE"},
    {"material_id": "MAT-5005", "description": "Koomey pump motor assembly",
     "component_type": "PUMP", "available_qty": 1, "min_stock": 1,
     "lead_time_days": 28, "unit_price": 62000, "plant": "GOM-SHORE"},
    {"material_id": "MAT-5006", "description": "Pump bearing kit",
     "component_type": "PUMP", "available_qty": 6, "min_stock": 3,
     "lead_time_days": 5, "unit_price": 3500, "plant": "GOM-SHORE"},
    {"material_id": "MAT-5007", "description": "Accumulator bladder 11-gal",
     "component_type": "ACCUMULATOR", "available_qty": 8, "min_stock": 4,
     "lead_time_days": 10, "unit_price": 2800, "plant": "GOM-SHORE"},
    {"material_id": "MAT-5008", "description": "MUX cable assembly 5000ft",
     "component_type": "POD", "available_qty": 1, "min_stock": 1,
     "lead_time_days": 35, "unit_price": 120000, "plant": "GOM-SHORE"},
    {"material_id": "MAT-5009", "description": "Solenoid valve — control pod",
     "component_type": "POD", "available_qty": 12, "min_stock": 6,
     "lead_time_days": 7, "unit_price": 4500, "plant": "GOM-SHORE"},
    {"material_id": "MAT-5010", "description": "PLC I/O module",
     "component_type": "PLC", "available_qty": 3, "min_stock": 2,
     "lead_time_days": 14, "unit_price": 8500, "plant": "GOM-SHORE"},
]

# ── Crew ──────────────────────────────────────────────────

CREW = [
    {"crew_id": "C-001", "name": "James McAllister", "role": "Subsea Engineer",
     "company": "Oceaneering", "shift": "Day", "zone": "BOP_CONTROL_ROOM",
     "is_on_rig": True, "certs": ["BOP_MAINT_LEVEL_III", "SUBSEA_SPECIALIST"]},
    {"crew_id": "C-002", "name": "Maria Santos", "role": "Drilling Engineer",
     "company": "Operator", "shift": "Day", "zone": "DRILLER_CABIN",
     "is_on_rig": True, "certs": ["WELL_CONTROL_LEVEL_IV", "BOP_TEST_CERTIFIED"]},
    {"crew_id": "C-003", "name": "Robert Chen", "role": "BOP Technician",
     "company": "BOP OEM", "shift": "Day", "zone": "DRILL_FLOOR",
     "is_on_rig": True, "certs": ["BOP_MAINT_LEVEL_II", "HYDRAULIC_SPECIALIST"]},
    {"crew_id": "C-004", "name": "Ahmed Al-Rashid", "role": "Toolpusher",
     "company": "Operator", "shift": "Day", "zone": "DRILL_FLOOR",
     "is_on_rig": True, "certs": ["WELL_CONTROL_LEVEL_III"]},
    {"crew_id": "C-005", "name": "Sarah Thompson", "role": "Subsea Engineer",
     "company": "Oceaneering", "shift": "Night", "zone": "QUARTERS",
     "is_on_rig": True, "certs": ["BOP_MAINT_LEVEL_III", "SUBSEA_SPECIALIST"]},
    {"crew_id": "C-006", "name": "Kevin O'Brien", "role": "Electrician",
     "company": "Rig Crew", "shift": "Day", "zone": "ENGINE_ROOM",
     "is_on_rig": True, "certs": ["ELECTRICAL_HV", "PLC_CERTIFIED"]},
    {"crew_id": "C-007", "name": "David Park", "role": "OIM",
     "company": "Operator", "shift": "Day", "zone": "OIM_OFFICE",
     "is_on_rig": True, "certs": ["WELL_CONTROL_LEVEL_IV", "OIM_CERTIFIED"]},
    {"crew_id": "C-008", "name": "Lisa Wagner", "role": "HSE Advisor",
     "company": "Operator", "shift": "Day", "zone": "HSE_OFFICE",
     "is_on_rig": True, "certs": ["NEBOSH", "BOSIET"]},
]

INTERVENTION_ETA = {
    "BOP_CONTROL_ROOM": 2,
    "DRILL_FLOOR": 5,
    "DRILLER_CABIN": 3,
    "ENGINE_ROOM": 8,
    "OIM_OFFICE": 6,
    "HSE_OFFICE": 7,
    "QUARTERS": 15,
}


def get_qualified_bop_crew() -> list[dict]:
    bop_certs = {"BOP_MAINT_LEVEL_II", "BOP_MAINT_LEVEL_III", "SUBSEA_SPECIALIST",
                 "HYDRAULIC_SPECIALIST", "BOP_TEST_CERTIFIED"}
    return [c for c in CREW if any(cert in bop_certs for cert in c.get("certs", []))]


def get_intervention_eta(crew_member: dict) -> int:
    return INTERVENTION_ETA.get(crew_member.get("zone", ""), 20)


def get_spares_for_component(component_type: str) -> list[dict]:
    type_map = {
        "ANNULAR": ["ANNULAR"], "UPPER_PIPE_RAM": ["PIPE_RAM"],
        "LOWER_PIPE_RAM": ["PIPE_RAM"], "BLIND_SHEAR_RAM": ["BLIND_SHEAR_RAM"],
        "POD_A": ["POD"], "POD_B": ["POD"], "PUMP": ["PUMP"],
        "ACCUMULATOR": ["ACCUMULATOR"], "PLC": ["PLC"],
    }
    part_types = type_map.get(component_type, [])
    return [s for s in SAP_SPARES if s["component_type"] in part_types]


def get_wo_for_equipment(equipment_id: str) -> list[dict]:
    return [wo for wo in SAP_WORK_ORDERS if wo["equipment_id"] == equipment_id]


def get_sap_kpis() -> dict:
    open_wos = sum(1 for w in SAP_WORK_ORDERS if w["status"] in ("OPEN", "IN_PROGRESS"))
    crit_wos = sum(1 for w in SAP_WORK_ORDERS if w["priority"] == 1 and w["status"] != "COMPLETED")
    total_inv = sum(s["available_qty"] * s["unit_price"] for s in SAP_SPARES)
    low_stock = sum(1 for s in SAP_SPARES if s["available_qty"] <= s["min_stock"])
    return {
        "open_wos": open_wos,
        "critical_wos": crit_wos,
        "total_inventory_value": total_inv,
        "low_stock_items": low_stock,
        "crew_on_rig": sum(1 for c in CREW if c["is_on_rig"]),
        "bop_qualified_crew": len(get_qualified_bop_crew()),
    }
