"""
Full-cycle cost estimation engine.

Uses SAP Business Data Cloud supply chain / pricing data (via Delta Sharing)
to estimate costs for each well-level operation.
"""

# ── SAP Material Master (simulated — shared via Delta Sharing) ─────────────
SAP_MATERIALS = [
    {"material_id": "MAT-001", "description": "PDC Drill Bit 12.25\"",    "category": "Drilling",        "unit_price_usd": 45000,   "unit": "EA",  "lead_time_days": 14,  "vendor": "Schlumberger"},
    {"material_id": "MAT-002", "description": "Casing 13-3/8\" K-55",     "category": "Casing",          "unit_price_usd": 85,      "unit": "FT",  "lead_time_days": 21,  "vendor": "Tenaris"},
    {"material_id": "MAT-003", "description": "Casing 9-5/8\" L-80",      "category": "Casing",          "unit_price_usd": 72,      "unit": "FT",  "lead_time_days": 21,  "vendor": "Tenaris"},
    {"material_id": "MAT-004", "description": "Cement Class G",            "category": "Cementing",       "unit_price_usd": 18,      "unit": "SX",  "lead_time_days": 7,   "vendor": "Halliburton"},
    {"material_id": "MAT-005", "description": "Drilling Fluid — OBM",      "category": "Drilling",        "unit_price_usd": 280,     "unit": "BBL", "lead_time_days": 5,   "vendor": "M-I SWACO"},
    {"material_id": "MAT-006", "description": "Perforating Gun 4-1/2\"",   "category": "Completion",      "unit_price_usd": 12000,   "unit": "EA",  "lead_time_days": 10,  "vendor": "Schlumberger"},
    {"material_id": "MAT-007", "description": "Tubing 4-1/2\" L-80",      "category": "Completion",      "unit_price_usd": 55,      "unit": "FT",  "lead_time_days": 14,  "vendor": "Vallourec"},
    {"material_id": "MAT-008", "description": "Production Packer",         "category": "Completion",      "unit_price_usd": 28000,   "unit": "EA",  "lead_time_days": 21,  "vendor": "Baker Hughes"},
    {"material_id": "MAT-009", "description": "ESP Pump Assembly 400HP",   "category": "Artificial Lift", "unit_price_usd": 185000,  "unit": "EA",  "lead_time_days": 45,  "vendor": "Baker Hughes"},
    {"material_id": "MAT-010", "description": "ESP Motor 400HP",           "category": "Artificial Lift", "unit_price_usd": 95000,   "unit": "EA",  "lead_time_days": 45,  "vendor": "Baker Hughes"},
    {"material_id": "MAT-011", "description": "ESP Cable (flat)",           "category": "Artificial Lift", "unit_price_usd": 38,      "unit": "FT",  "lead_time_days": 30,  "vendor": "Baker Hughes"},
    {"material_id": "MAT-012", "description": "Scale Inhibitor — DETPMP",  "category": "Chemicals",       "unit_price_usd": 420,     "unit": "GAL", "lead_time_days": 7,   "vendor": "Clariant"},
    {"material_id": "MAT-013", "description": "Demulsifier",               "category": "Chemicals",       "unit_price_usd": 280,     "unit": "GAL", "lead_time_days": 7,   "vendor": "BASF"},
    {"material_id": "MAT-014", "description": "Corrosion Inhibitor",       "category": "Chemicals",       "unit_price_usd": 350,     "unit": "GAL", "lead_time_days": 7,   "vendor": "Clariant"},
    {"material_id": "MAT-015", "description": "Christmas Tree Assembly",   "category": "Wellhead",        "unit_price_usd": 450000,  "unit": "EA",  "lead_time_days": 60,  "vendor": "FMC Technologies"},
    {"material_id": "MAT-016", "description": "Subsea Flowline 6\"",      "category": "Facilities",      "unit_price_usd": 1200,    "unit": "FT",  "lead_time_days": 90,  "vendor": "Technip"},
    {"material_id": "MAT-017", "description": "Gas Compressor Module",     "category": "Injection",       "unit_price_usd": 2800000, "unit": "EA",  "lead_time_days": 120, "vendor": "Siemens"},
    {"material_id": "MAT-018", "description": "Gravel Pack Sand 20/40",    "category": "Completion",      "unit_price_usd": 45,      "unit": "SX",  "lead_time_days": 10,  "vendor": "Fairmount"},
]

# ── SAP Service Contracts ──────────────────────────────────────────────────
SAP_SERVICES = [
    {"service_id": "SVC-001", "description": "Semi-sub Rig Day Rate",       "category": "Drilling",           "daily_rate_usd": 285000, "vendor": "Transocean",       "contract_end": "2028-12-31"},
    {"service_id": "SVC-002", "description": "Drilling Crew (day)",          "category": "Drilling",           "daily_rate_usd": 45000,  "vendor": "Equinor Services", "contract_end": "2027-06-30"},
    {"service_id": "SVC-003", "description": "Supply Vessel",                "category": "Logistics",          "daily_rate_usd": 42000,  "vendor": "Solstad Offshore", "contract_end": "2027-12-31"},
    {"service_id": "SVC-004", "description": "Cement Pump Unit + Crew",      "category": "Cementing",          "daily_rate_usd": 65000,  "vendor": "Halliburton",      "contract_end": "2028-06-30"},
    {"service_id": "SVC-005", "description": "Wireline Unit + Crew",         "category": "Completion",         "daily_rate_usd": 52000,  "vendor": "Schlumberger",     "contract_end": "2027-12-31"},
    {"service_id": "SVC-006", "description": "Workover Rig",                 "category": "Well Intervention",  "daily_rate_usd": 180000, "vendor": "Archer Well",      "contract_end": "2028-12-31"},
    {"service_id": "SVC-007", "description": "Chemical Injection Skid",      "category": "Production Chemistry","daily_rate_usd": 8500,  "vendor": "Clariant",         "contract_end": "2027-12-31"},
    {"service_id": "SVC-008", "description": "Platform Crane Ops",           "category": "Logistics",          "daily_rate_usd": 18000,  "vendor": "Mammoet",          "contract_end": "2028-12-31"},
    {"service_id": "SVC-009", "description": "ROV Ops (subsea)",             "category": "Subsea",             "daily_rate_usd": 35000,  "vendor": "DOF Subsea",       "contract_end": "2027-12-31"},
    {"service_id": "SVC-010", "description": "P&A Operations",               "category": "Abandonment",        "daily_rate_usd": 195000, "vendor": "Well-Safe Solutions","contract_end": "2029-12-31"},
]

# ── SAP Equipment Inventory ────────────────────────────────────────────────
SAP_EQUIPMENT = [
    {"equipment_id": "EQP-001", "description": "ESP Pump Assembly (spare)",  "status": "Available",         "location": "Mongstad Base",      "qty": 3,   "value_usd": 185000},
    {"equipment_id": "EQP-002", "description": "ESP Motor 400HP (spare)",    "status": "Available",         "location": "Mongstad Base",      "qty": 4,   "value_usd": 95000},
    {"equipment_id": "EQP-003", "description": "Christmas Tree (spare)",     "status": "Available",         "location": "Kristiansund Base",  "qty": 1,   "value_usd": 450000},
    {"equipment_id": "EQP-004", "description": "Perforating Gun Set",        "status": "Available",         "location": "Mongstad Base",      "qty": 8,   "value_usd": 12000},
    {"equipment_id": "EQP-005", "description": "Tubing 4-1/2\" (joints)",   "status": "Available",         "location": "Dusavik Base",       "qty": 450, "value_usd": 55},
    {"equipment_id": "EQP-006", "description": "Production Packer (spare)",  "status": "Available",         "location": "Mongstad Base",      "qty": 2,   "value_usd": 28000},
    {"equipment_id": "EQP-007", "description": "BOP Ram Assembly",           "status": "In Use — Norne A",  "location": "Offshore",           "qty": 1,   "value_usd": 3200000},
    {"equipment_id": "EQP-008", "description": "Scale Inhibitor Tank",       "status": "Available",         "location": "Norne FPSO",         "qty": 2,   "value_usd": 45000},
]


# ── Cost model per activity type ───────────────────────────────────────────
_COST_MODEL = {
    "DRILL":          {"services": [("SVC-001", 21), ("SVC-002", 21), ("SVC-003", 21)], "materials": [("MAT-001", 3), ("MAT-005", 800)],                           "fixed": 120000},
    "CASE_CEMENT":    {"services": [("SVC-001", 6), ("SVC-004", 4)],                     "materials": [("MAT-002", 5000), ("MAT-003", 8000), ("MAT-004", 500)],    "fixed": 45000},
    "PERFORATE":      {"services": [("SVC-005", 3)],                                     "materials": [("MAT-006", 4)],                                             "fixed": 25000},
    "COMPLETE":       {"services": [("SVC-005", 5), ("SVC-001", 3)],                     "materials": [("MAT-007", 8000), ("MAT-008", 1), ("MAT-015", 1), ("MAT-018", 200)], "fixed": 85000},
    "ESP_INSTALL":    {"services": [("SVC-006", 5), ("SVC-008", 3)],                     "materials": [("MAT-009", 1), ("MAT-010", 1), ("MAT-011", 8000)],         "fixed": 65000},
    "ESP_MAINTAIN":   {"services": [("SVC-006", 2)],                                     "materials": [],                                                            "fixed": 35000},
    "CHEM_TREAT":     {"services": [("SVC-007", 1)],                                     "materials": [("MAT-013", 50), ("MAT-014", 30)],                           "fixed": 8000},
    "SCALE_INHIB":    {"services": [("SVC-007", 2)],                                     "materials": [("MAT-012", 80)],                                             "fixed": 12000},
    "WORKOVER":       {"services": [("SVC-006", 7), ("SVC-003", 4), ("SVC-008", 3)],     "materials": [("MAT-007", 4000)],                                          "fixed": 150000},
    "WH_MAINTAIN":    {"services": [("SVC-008", 1)],                                     "materials": [],                                                            "fixed": 15000},
    "COMP_MAINTAIN":  {"services": [("SVC-008", 3)],                                     "materials": [],                                                            "fixed": 85000},
    "INJ_OPTIMIZE":   {"services": [],                                                    "materials": [],                                                            "fixed": 22000},
    "INTEGRITY_TEST": {"services": [("SVC-005", 1)],                                     "materials": [],                                                            "fixed": 18000},
}

_SVC_MAP = {s["service_id"]: s for s in SAP_SERVICES}
_MAT_MAP = {m["material_id"]: m for m in SAP_MATERIALS}


def estimate_activity_cost(activity_type: str) -> dict:
    """Estimate cost for a single activity using SAP pricing data."""
    model = _COST_MODEL.get(activity_type, {"services": [], "materials": [], "fixed": 0})

    svc_cost, svc_detail = 0.0, []
    for sid, days in model["services"]:
        svc = _SVC_MAP.get(sid)
        if svc:
            c = svc["daily_rate_usd"] * days
            svc_cost += c
            svc_detail.append({"service_id": sid, "description": svc["description"],
                               "days": days, "daily_rate": svc["daily_rate_usd"],
                               "total": c, "vendor": svc["vendor"]})

    mat_cost, mat_detail = 0.0, []
    for mid, qty in model["materials"]:
        mat = _MAT_MAP.get(mid)
        if mat:
            c = mat["unit_price_usd"] * qty
            mat_cost += c
            mat_detail.append({"material_id": mid, "description": mat["description"],
                               "qty": qty, "unit": mat["unit"],
                               "unit_price": mat["unit_price_usd"], "total": c,
                               "vendor": mat["vendor"],
                               "lead_time_days": mat["lead_time_days"]})

    fixed = model["fixed"]
    return {
        "total_cost_usd": svc_cost + mat_cost + fixed,
        "service_cost_usd": svc_cost,
        "material_cost_usd": mat_cost,
        "fixed_cost_usd": fixed,
        "service_details": svc_detail,
        "material_details": mat_detail,
    }


def estimate_full_cycle_costs(operations: list) -> dict:
    """Estimate full-cycle costs for all operations in a run."""
    well_costs: dict = {}
    cat_costs: dict = {}
    total = 0.0
    costed = []

    for op in operations:
        cd = estimate_activity_cost(op["activity_type"])
        c = cd["total_cost_usd"]
        wn = op["well_name"]
        cat = op["category"]

        wc = well_costs.setdefault(wn, {"total": 0.0, "categories": {}})
        wc["total"] += c
        wc["categories"][cat] = wc["categories"].get(cat, 0) + c

        cat_costs[cat] = cat_costs.get(cat, 0) + c
        total += c
        costed.append({**op, **cd})

    return {
        "total_cost_usd": total,
        "well_costs": well_costs,
        "category_costs": cat_costs,
        "costed_operations": costed,
        "sap_materials_used": len({m["material_id"] for co in costed for m in co.get("material_details", [])}),
        "sap_services_used":  len({s["service_id"]  for co in costed for s in co.get("service_details", [])}),
    }


def compute_lifting_costs(well_costs: dict, well_timeseries: list) -> dict:
    """Compute lifting cost $/BOE and full-cycle $/BOE per well."""
    cum_prod: dict = {}
    if well_timeseries:
        for wr in well_timeseries[-1]:
            boe = wr.get("cum_oil_stb", 0) + wr.get("cum_gas_mscf", 0) / 6
            cum_prod[wr["well_name"]] = {"cum_oil": wr.get("cum_oil_stb", 0),
                                          "cum_gas": wr.get("cum_gas_mscf", 0),
                                          "cum_boe": boe}

    opex_cats = {"Artificial Lift", "Production Chemistry", "Well Intervention",
                 "Maintenance", "Injection"}
    result = {}
    for wn, wc in well_costs.items():
        p = cum_prod.get(wn, {"cum_boe": 0})
        boe = p.get("cum_boe", 0)
        opex = sum(wc["categories"].get(c, 0) for c in opex_cats)
        result[wn] = {
            "total_opex_usd": round(opex),
            "total_cost_usd": round(wc["total"]),
            "cum_boe": round(boe),
            "lifting_cost_per_boe": round(opex / boe, 2) if boe else 0,
            "full_cycle_cost_per_boe": round(wc["total"] / boe, 2) if boe else 0,
        }
    return result
