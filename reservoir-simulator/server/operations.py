"""
Operations Engine — derives well-level operational activities from simulation results.

After each simulation run, analyzes per-well performance metrics to generate a
schedule of drilling, completion, artificial lift, chemical treatment, workover,
and maintenance activities — each mapped to SAP cost items.
"""

# ── Activity catalogue ────────────────────────────────────────────────────────
ACTIVITY_TYPES = {
    "DRILL":          {"name": "Drilling",                  "category": "D&C",                  "duration_days": 21, "color": "#E67E22"},
    "CASE_CEMENT":    {"name": "Casing & Cementing",        "category": "D&C",                  "duration_days": 6,  "color": "#E67E22"},
    "PERFORATE":      {"name": "Perforation",               "category": "D&C",                  "duration_days": 3,  "color": "#F39C12"},
    "COMPLETE":       {"name": "Completion & Testing",      "category": "D&C",                  "duration_days": 8,  "color": "#F39C12"},
    "ESP_INSTALL":    {"name": "ESP Installation",          "category": "Artificial Lift",       "duration_days": 5,  "color": "#3498DB"},
    "ESP_MAINTAIN":   {"name": "ESP Maintenance",           "category": "Artificial Lift",       "duration_days": 2,  "color": "#3498DB"},
    "CHEM_TREAT":     {"name": "Chemical Treatment",        "category": "Production Chemistry",  "duration_days": 1,  "color": "#9B59B6"},
    "SCALE_INHIB":    {"name": "Scale Inhibitor Squeeze",   "category": "Production Chemistry",  "duration_days": 2,  "color": "#9B59B6"},
    "WORKOVER":       {"name": "Workover",                  "category": "Well Intervention",     "duration_days": 7,  "color": "#E74C3C"},
    "WH_MAINTAIN":    {"name": "Wellhead Maintenance",      "category": "Maintenance",           "duration_days": 1,  "color": "#7F8C8D"},
    "COMP_MAINTAIN":  {"name": "Compressor Maintenance",    "category": "Injection",             "duration_days": 3,  "color": "#2980B9"},
    "INJ_OPTIMIZE":   {"name": "Injection Rate Optimization", "category": "Injection",           "duration_days": 2,  "color": "#2980B9"},
    "INTEGRITY_TEST": {"name": "Well Integrity Test",       "category": "Injection",             "duration_days": 1,  "color": "#2980B9"},
}


def derive_operations(well_timeseries: list, wells_config: list) -> list:
    """
    Derive well-level operational activities from simulation well time series.

    Parameters
    ----------
    well_timeseries : list[list[dict]]
        Per-timestep list of per-well production dicts (as stored by simulate.py).
    wells_config : list[dict]
        Well definitions from scenario config.

    Returns
    -------
    list[dict]
        Sorted activity records with well_name, type, timing, trigger reason, etc.
    """
    activities: list[dict] = []
    if not well_timeseries:
        return activities

    prod_wells = [w["name"] for w in wells_config if w.get("type") != "INJ"]
    inj_wells = [w["name"] for w in wells_config if w.get("type") == "INJ"]

    # ── Phase 1 — Drilling & Completion (pre-production) ───────────────────
    day_offset = 0
    for wname in prod_wells + inj_wells:
        for act_type in ("DRILL", "CASE_CEMENT", "PERFORATE", "COMPLETE"):
            at = ACTIVITY_TYPES[act_type]
            activities.append(_act(wname, act_type, at, day_offset,
                                   f"Initial {at['name'].lower()} — well {wname}"))
            day_offset += at["duration_days"]
        day_offset += 3  # inter-well gap

    # ── Phase 2 — Production-triggered activities ──────────────────────────
    well_series = _build_well_lookup(well_timeseries)

    for wname in prod_wells:
        wdata = well_series.get(wname, [])
        if not wdata:
            continue
        esp_installed = False
        last_chem = -365.0
        last_scale = -365.0
        last_wh = -365.0
        workover_done = False

        for wd in wdata:
            day = wd["day"]
            bhp = wd["bhp_bar"]
            oil = wd["oil_rate_stbd"]
            water = wd["water_rate_stbd"]
            wc = water / max(oil + water, 1) * 100

            # ESP when BHP drops below 160 bar
            if not esp_installed and bhp < 160:
                at = ACTIVITY_TYPES["ESP_INSTALL"]
                activities.append(_act(wname, "ESP_INSTALL", at, int(day),
                                       f"BHP fell to {bhp:.0f} bar (< 160 bar threshold)"))
                esp_installed = True

            # Chemical treatment at water cut > 25 %, every 180 d
            if wc > 25 and day - last_chem > 180:
                at = ACTIVITY_TYPES["CHEM_TREAT"]
                activities.append(_act(wname, "CHEM_TREAT", at, int(day),
                                       f"Water cut {wc:.1f}% > 25 % threshold"))
                last_chem = day

            # Scale inhibition at water cut > 10 %, annual
            if wc > 10 and day - last_scale > 365:
                at = ACTIVITY_TYPES["SCALE_INHIB"]
                activities.append(_act(wname, "SCALE_INHIB", at, int(day),
                                       f"Annual scale prevention (WC {wc:.1f}%)"))
                last_scale = day

            # Workover at water cut > 50 %, once
            if not workover_done and wc > 50:
                at = ACTIVITY_TYPES["WORKOVER"]
                activities.append(_act(wname, "WORKOVER", at, int(day),
                                       f"High water-cut workover (WC {wc:.1f}%)"))
                workover_done = True

            # Wellhead maintenance — annual
            if day - last_wh > 365:
                at = ACTIVITY_TYPES["WH_MAINTAIN"]
                activities.append(_act(wname, "WH_MAINTAIN", at, int(day),
                                       "Annual wellhead inspection"))
                last_wh = day

    # ── Phase 3 — Injection well activities ────────────────────────────────
    for wname in inj_wells:
        last_comp = -365.0
        last_integ = -730.0
        last_inj_opt = -545.0
        for i in range(len(well_timeseries)):
            day = (i + 1) * 91.25
            if day - last_comp > 365:
                at = ACTIVITY_TYPES["COMP_MAINTAIN"]
                activities.append(_act(wname, "COMP_MAINTAIN", at, int(day),
                                       "Scheduled compressor maintenance"))
                last_comp = day
            if day - last_integ > 730:
                at = ACTIVITY_TYPES["INTEGRITY_TEST"]
                activities.append(_act(wname, "INTEGRITY_TEST", at, int(day),
                                       "Biennial well integrity verification"))
                last_integ = day
            if day - last_inj_opt > 545:
                at = ACTIVITY_TYPES["INJ_OPTIMIZE"]
                activities.append(_act(wname, "INJ_OPTIMIZE", at, int(day),
                                       "Injection rate re-optimization"))
                last_inj_opt = day

    activities.sort(key=lambda a: (a["start_day"], a["well_name"]))
    return activities


# ── helpers ────────────────────────────────────────────────────────────────────

def _act(well_name, act_type, at, start_day, reason):
    return {
        "well_name": well_name,
        "activity_type": act_type,
        "activity_name": at["name"],
        "category": at["category"],
        "start_day": start_day,
        "duration_days": at["duration_days"],
        "end_day": start_day + at["duration_days"],
        "trigger_reason": reason,
        "color": at["color"],
    }


def _build_well_lookup(well_timeseries):
    lookup: dict[str, list] = {}
    for ts_results in well_timeseries:
        for wr in ts_results:
            lookup.setdefault(wr["well_name"], []).append(wr)
    return lookup
